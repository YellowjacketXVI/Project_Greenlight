"""
Continuity-Focused Storyboard Pipeline

Generates and refines storyboard frames until achieving target continuity score.
Key features:
- Batch continuity scoring (frame-to-frame consistency)
- Loop until 80% target achieved OR max iterations
- Prioritizes worst-scoring frames for refinement
- Tracks continuity breaks between adjacent frames
"""

import asyncio
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from enum import Enum

from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
from greenlight.agents.frame_evaluation_agent import (
    FrameEvaluationAgent, FrameContext, FrameEvaluation, FixPriority
)


class FrameStatus(Enum):
    PENDING = "pending"
    GENERATING = "generating"
    EVALUATING = "evaluating"
    REFINING = "refining"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class FrameSpec:
    """Specification for a frame to generate."""
    frame_id: str
    prompt: str
    visual_description: str
    scene_id: str
    location: str
    time_of_day: str
    characters: list[str]
    character_refs: list[Path] = field(default_factory=list)
    location_refs: list[Path] = field(default_factory=list)


@dataclass
class FrameState:
    """Current state of a frame in the pipeline."""
    spec: FrameSpec
    status: FrameStatus = FrameStatus.PENDING
    current_image: Optional[Path] = None
    current_score: float = 0.0
    continuity_score: float = 0.0  # Score vs adjacent frames
    iteration: int = 0
    evaluations: list[FrameEvaluation] = field(default_factory=list)
    image_versions: list[Path] = field(default_factory=list)
    continuity_issues: list[str] = field(default_factory=list)


@dataclass
class BatchMetrics:
    """Metrics for the entire batch."""
    avg_score: float = 0.0
    avg_continuity: float = 0.0
    min_score: float = 0.0
    frames_above_threshold: int = 0
    total_frames: int = 0
    continuity_breaks: list[tuple[str, str, str]] = field(default_factory=list)  # (frame1, frame2, issue)

    @property
    def batch_continuity_percent(self) -> float:
        """Overall batch continuity as percentage."""
        if self.total_frames == 0:
            return 0.0
        return (self.avg_continuity / 10.0) * 100


class ContinuityPipeline:
    """
    Pipeline that generates storyboard frames and refines until
    achieving target continuity score across all frames.
    """

    TARGET_SCORE = 8.0  # 80% = 8.0/10
    MAX_ITERATIONS = 4  # Max refinement loops
    MAX_FRAME_ATTEMPTS = 3  # Max attempts per individual frame

    def __init__(
        self,
        project_path: Path,
        model: ImageModel = ImageModel.P_IMAGE_EDIT,
        target_score: float = 8.0
    ):
        self.project_path = project_path
        self.model = model
        self.TARGET_SCORE = target_score
        self.handler = ImageHandler(project_path)
        self.evaluator = FrameEvaluationAgent()
        self.output_dir = project_path / "storyboard_output" / "continuity_pipeline"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_with_continuity(
        self,
        frame_specs: list[FrameSpec]
    ) -> tuple[list[FrameState], BatchMetrics]:
        """
        Main entry point: Generate frames and refine until target continuity reached.
        Returns final states and metrics.
        """
        print(f"\n{'='*70}")
        print("CONTINUITY-FOCUSED STORYBOARD PIPELINE")
        print(f"Target: {self.TARGET_SCORE}/10 ({self.TARGET_SCORE*10}%) continuity")
        print(f"Frames: {len(frame_specs)} | Max iterations: {self.MAX_ITERATIONS}")
        print(f"{'='*70}\n")

        # Initialize states
        states = [FrameState(spec=spec) for spec in frame_specs]

        # Main refinement loop
        iteration = 0
        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            print(f"\n{'='*70}")
            print(f"ITERATION {iteration}/{self.MAX_ITERATIONS}")
            print(f"{'='*70}\n")

            # Step 1: Generate/Refine frames that need work
            await self._process_frames(states, iteration)

            # Step 2: Evaluate all frames with continuity context
            await self._evaluate_batch_continuity(states)

            # Step 3: Calculate batch metrics
            metrics = self._calculate_metrics(states)
            self._print_iteration_summary(states, metrics, iteration)

            # Step 4: Check if target reached
            if metrics.avg_continuity >= self.TARGET_SCORE:
                print(f"\n*** TARGET REACHED: {metrics.avg_continuity:.1f}/10 ***")
                break

            # Step 5: Identify frames needing refinement
            frames_to_refine = self._identify_refinement_targets(states, metrics)
            if not frames_to_refine:
                print("\nNo more frames can be refined (max attempts reached)")
                break

            print(f"\nFrames targeted for refinement: {[s.spec.frame_id for s in frames_to_refine]}")

        # Final summary
        final_metrics = self._calculate_metrics(states)
        self._print_final_summary(states, final_metrics)
        self._save_report(states, final_metrics)

        return states, final_metrics

    async def _process_frames(self, states: list[FrameState], iteration: int):
        """Generate or refine frames based on their current state."""
        print("PROCESSING FRAMES...")
        print("-" * 50)

        for state in states:
            # Skip if already at max attempts
            if state.iteration >= self.MAX_FRAME_ATTEMPTS:
                continue

            # Skip if already above threshold
            if state.current_score >= self.TARGET_SCORE and state.continuity_score >= self.TARGET_SCORE:
                continue

            if state.current_image is None:
                # First generation
                await self._generate_frame(state, iteration)
            else:
                # Refinement
                await self._refine_frame(state, iteration)

    async def _generate_frame(self, state: FrameState, iteration: int):
        """Generate initial frame."""
        state.status = FrameStatus.GENERATING
        state.iteration = iteration

        output_path = self.output_dir / f"{state.spec.frame_id.replace('.', '_')}_i{iteration}.png"
        refs = state.spec.character_refs + state.spec.location_refs

        if not refs:
            print(f"  [{state.spec.frame_id}] SKIPPED - no reference images")
            state.status = FrameStatus.FAILED
            return

        result = await self.handler.generate(ImageRequest(
            prompt=state.spec.prompt,
            model=self.model,
            reference_images=refs[:4],
            output_path=output_path,
            aspect_ratio="16:9",
            prefix_type="create",
            add_clean_suffix=True
        ))

        if result.success:
            state.current_image = output_path
            state.image_versions.append(output_path)
            state.status = FrameStatus.EVALUATING
            print(f"  [{state.spec.frame_id}] Generated ({result.generation_time_ms}ms)")
        else:
            state.status = FrameStatus.FAILED
            print(f"  [{state.spec.frame_id}] FAILED: {result.error}")

    async def _refine_frame(self, state: FrameState, iteration: int):
        """Refine a frame based on evaluation feedback."""
        state.status = FrameStatus.REFINING
        state.iteration = iteration

        if not state.evaluations:
            return

        eval_result = state.evaluations[-1]
        output_path = self.output_dir / f"{state.spec.frame_id.replace('.', '_')}_i{iteration}.png"

        # Build edit prompt from issues
        edit_prompt = self._build_refinement_prompt(state, eval_result)

        # Decide: regenerate or edit
        if eval_result.needs_regeneration or eval_result.overall_score < 4.0:
            # Full regeneration with negative prompts
            refs = state.spec.character_refs + state.spec.location_refs
            result = await self.handler.generate(ImageRequest(
                prompt=edit_prompt,
                model=self.model,
                reference_images=refs[:4],
                output_path=output_path,
                aspect_ratio="16:9",
                prefix_type="create",
                add_clean_suffix=True
            ))
            action = "REGENERATED"
        else:
            # Targeted edit
            refs = [state.current_image] + state.spec.character_refs[:1]
            result = await self.handler.generate(ImageRequest(
                prompt=edit_prompt,
                model=self.model,
                reference_images=refs,
                output_path=output_path,
                aspect_ratio="16:9",
                prefix_type="edit",
                add_clean_suffix=True
            ))
            action = "EDITED"

        if result.success:
            state.current_image = output_path
            state.image_versions.append(output_path)
            state.status = FrameStatus.EVALUATING
            print(f"  [{state.spec.frame_id}] {action} ({result.generation_time_ms}ms)")
        else:
            print(f"  [{state.spec.frame_id}] Refine FAILED: {result.error}")

    def _build_refinement_prompt(self, state: FrameState, eval_result: FrameEvaluation) -> str:
        """Build a refinement prompt from evaluation issues."""
        # Start with original prompt
        base_prompt = state.spec.prompt

        # Add fixes as positive instructions
        fixes = []
        for task in eval_result.fix_tasks[:3]:
            fixes.append(f"- {task.fix_instruction}")

        # Build negative prompt from issues
        negatives = []
        for task in eval_result.fix_tasks:
            issue = task.issue.lower()
            if "two people" in issue or "multiple" in issue or "extra" in issue:
                negatives.append("multiple people, extra figures, crowd")
            if "wrong gender" in issue or "man instead" in issue:
                negatives.append("wrong gender, male when should be female")
            if "sweater" in issue or "modern" in issue:
                negatives.append("modern clothing, sweaters, casual wear")
            if "night" in issue or "dark" in issue:
                negatives.append("nighttime, dark lighting, evening")
            if "seated" in issue or "sitting" in issue:
                negatives.append("seated pose, sitting down")

        # Add continuity issues
        for issue in state.continuity_issues:
            negatives.append(issue)

        # Build final prompt
        prompt = base_prompt
        if fixes:
            prompt += "\n\nCRITICAL FIXES TO APPLY:\n" + "\n".join(fixes)
        if negatives:
            prompt += "\n\nAVOID (negative prompt): " + ", ".join(set(negatives))

        return prompt

    async def _evaluate_batch_continuity(self, states: list[FrameState]):
        """Evaluate all frames with focus on continuity between adjacent frames."""
        print("\nEVALUATING BATCH CONTINUITY...")
        print("-" * 50)

        for i, state in enumerate(states):
            if not state.current_image or not state.current_image.exists():
                continue

            # Get adjacent frames
            prev_state = states[i-1] if i > 0 else None
            next_state = states[i+1] if i < len(states)-1 else None

            # Build context with adjacents
            context = FrameContext(
                frame_id=state.spec.frame_id,
                generated_image_path=state.current_image,
                original_prompt=state.spec.prompt,
                visual_description=state.spec.visual_description,
                character_refs=state.spec.character_refs,
                location_refs=state.spec.location_refs,
                scene_id=state.spec.scene_id,
                location_name=state.spec.location,
                time_of_day=state.spec.time_of_day,
                characters_in_frame=state.spec.characters,
                prev_frame_path=prev_state.current_image if prev_state and prev_state.current_image else None,
                prev_frame_description=prev_state.spec.visual_description if prev_state else None,
                next_frame_path=next_state.current_image if next_state and next_state.current_image else None,
                next_frame_description=next_state.spec.visual_description if next_state else None
            )

            # Evaluate
            evaluation = self.evaluator.evaluate_frame(context)
            state.evaluations.append(evaluation)
            state.current_score = evaluation.overall_score

            # Calculate continuity score (based on continuity category issues)
            continuity_issues = [t for t in evaluation.fix_tasks if t.category.value == "continuity"]
            if continuity_issues:
                # Penalize for continuity breaks
                state.continuity_score = max(0, evaluation.overall_score - len(continuity_issues))
                state.continuity_issues = [t.issue for t in continuity_issues]
            else:
                state.continuity_score = evaluation.overall_score
                state.continuity_issues = []

            # Print result
            status_icon = "[OK]" if state.current_score >= self.TARGET_SCORE else "[--]"
            print(f"  {status_icon} [{state.spec.frame_id}] Score: {state.current_score:.1f} | Continuity: {state.continuity_score:.1f}")

    def _calculate_metrics(self, states: list[FrameState]) -> BatchMetrics:
        """Calculate batch-wide metrics."""
        valid_states = [s for s in states if s.current_image]
        if not valid_states:
            return BatchMetrics(total_frames=len(states))

        scores = [s.current_score for s in valid_states]
        continuity_scores = [s.continuity_score for s in valid_states]

        # Find continuity breaks
        breaks = []
        for i in range(len(states) - 1):
            if states[i].continuity_issues:
                for issue in states[i].continuity_issues:
                    breaks.append((states[i].spec.frame_id, states[i+1].spec.frame_id if i+1 < len(states) else "end", issue))

        return BatchMetrics(
            avg_score=sum(scores) / len(scores),
            avg_continuity=sum(continuity_scores) / len(continuity_scores),
            min_score=min(scores),
            frames_above_threshold=sum(1 for s in scores if s >= self.TARGET_SCORE),
            total_frames=len(states),
            continuity_breaks=breaks
        )

    def _identify_refinement_targets(self, states: list[FrameState], metrics: BatchMetrics) -> list[FrameState]:
        """Identify which frames need refinement."""
        targets = []
        for state in states:
            # Skip if at max attempts
            if state.iteration >= self.MAX_FRAME_ATTEMPTS:
                continue
            # Skip if already good
            if state.current_score >= self.TARGET_SCORE and state.continuity_score >= self.TARGET_SCORE:
                continue
            # Skip if no image
            if not state.current_image:
                continue
            targets.append(state)

        # Sort by score (worst first)
        targets.sort(key=lambda s: s.continuity_score)
        return targets

    def _print_iteration_summary(self, states: list[FrameState], metrics: BatchMetrics, iteration: int):
        """Print summary after each iteration."""
        print(f"\n--- ITERATION {iteration} SUMMARY ---")
        print(f"Average Score: {metrics.avg_score:.1f}/10")
        print(f"Average Continuity: {metrics.avg_continuity:.1f}/10 ({metrics.batch_continuity_percent:.0f}%)")
        print(f"Frames Above Target: {metrics.frames_above_threshold}/{metrics.total_frames}")

        if metrics.continuity_breaks:
            print(f"Continuity Breaks: {len(metrics.continuity_breaks)}")

    def _print_final_summary(self, states: list[FrameState], metrics: BatchMetrics):
        """Print final summary."""
        print(f"\n{'='*70}")
        print("FINAL RESULTS")
        print(f"{'='*70}\n")

        for state in states:
            if not state.current_image:
                print(f"[{state.spec.frame_id}] FAILED")
                continue

            # Score progression
            scores = [e.overall_score for e in state.evaluations]
            progression = " → ".join(f"{s:.1f}" for s in scores)
            status = "[OK]" if state.current_score >= self.TARGET_SCORE else "[X]"

            print(f"{status} [{state.spec.frame_id}] {progression} (iterations: {state.iteration})")

        print(f"\n{'='*70}")
        print(f"BATCH CONTINUITY: {metrics.avg_continuity:.1f}/10 ({metrics.batch_continuity_percent:.0f}%)")
        print(f"TARGET: {self.TARGET_SCORE}/10 ({self.TARGET_SCORE*10:.0f}%)")
        print(f"STATUS: {'ACHIEVED' if metrics.avg_continuity >= self.TARGET_SCORE else 'NOT ACHIEVED'}")
        print(f"{'='*70}")

    def _save_report(self, states: list[FrameState], metrics: BatchMetrics):
        """Save detailed report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "model": self.model.value,
            "target_score": self.TARGET_SCORE,
            "final_metrics": {
                "avg_score": metrics.avg_score,
                "avg_continuity": metrics.avg_continuity,
                "continuity_percent": metrics.batch_continuity_percent,
                "frames_above_threshold": metrics.frames_above_threshold,
                "total_frames": metrics.total_frames,
                "target_achieved": metrics.avg_continuity >= self.TARGET_SCORE
            },
            "frames": []
        }

        for state in states:
            frame_data = {
                "frame_id": state.spec.frame_id,
                "final_image": str(state.current_image) if state.current_image else None,
                "final_score": state.current_score,
                "continuity_score": state.continuity_score,
                "iterations": state.iteration,
                "score_progression": [e.overall_score for e in state.evaluations],
                "image_versions": [str(p) for p in state.image_versions],
                "continuity_issues": state.continuity_issues
            }
            report["frames"].append(frame_data)

        report_path = self.output_dir / f"continuity_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved: {report_path}")


# Public API
async def generate_storyboard_with_continuity(
    project_path: Path,
    frame_specs: list[FrameSpec],
    model: ImageModel = ImageModel.P_IMAGE_EDIT,
    target_score: float = 8.0
) -> tuple[list[FrameState], BatchMetrics]:
    """
    Generate a storyboard batch with continuity-focused refinement.

    Args:
        project_path: Path to project
        frame_specs: List of frame specifications
        model: Image generation model to use
        target_score: Target continuity score (default 8.0 = 80%)

    Returns:
        Tuple of (frame states, batch metrics)
    """
    pipeline = ContinuityPipeline(project_path, model, target_score)
    return await pipeline.generate_with_continuity(frame_specs)
