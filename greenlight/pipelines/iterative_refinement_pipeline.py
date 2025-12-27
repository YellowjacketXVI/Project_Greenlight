"""
Iterative Refinement Pipeline

A proper loop-based refinement system:
1. Generate all images in batch (Pass 1)
2. Evaluate each image against expected output
3. Apply correction edits with issues as NEGATIVE prompts (Pass 2)
4. Re-evaluate and apply final polish if needed (Pass 3)
5. Max 3 loops per image, stop early if score threshold met

Key improvement: Issues become negative prompts to prevent repetition
"""

import asyncio
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
from greenlight.agents.frame_evaluation_agent import (
    FrameEvaluationAgent, FrameContext, FrameEvaluation, FixPriority, FixCategory
)


@dataclass
class FrameSpec:
    """Specification for a single frame."""
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
class RefinementState:
    """Tracks refinement state for a single frame."""
    spec: FrameSpec
    current_image: Optional[Path] = None
    current_score: float = 0.0
    pass_number: int = 0
    evaluations: list[FrameEvaluation] = field(default_factory=list)
    image_versions: list[Path] = field(default_factory=list)
    is_complete: bool = False


class IterativeRefinementPipeline:
    """
    Pipeline that refines images through evaluation-driven edit loops.
    Each pass uses previous issues as negative prompts.
    """

    MAX_PASSES = 3
    COMPLETION_THRESHOLD = 8.0  # Stop refining if score >= this
    REGENERATION_THRESHOLD = 4.0  # Score below this = full regenerate

    def __init__(self, project_path: Path, model: ImageModel = ImageModel.P_IMAGE_EDIT):
        self.project_path = project_path
        self.model = model
        self.handler = ImageHandler(project_path)
        self.evaluator = FrameEvaluationAgent()
        self.output_dir = project_path / "storyboard_output" / "iterative_refinement"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def refine_batch(self, frame_specs: list[FrameSpec]) -> list[RefinementState]:
        """
        Refine a batch of frames through iterative passes.
        """
        print(f"\n{'='*60}")
        print("ITERATIVE REFINEMENT PIPELINE")
        print(f"Processing {len(frame_specs)} frames, max {self.MAX_PASSES} passes each")
        print(f"{'='*60}\n")

        # Initialize states
        states = [RefinementState(spec=spec) for spec in frame_specs]

        # Run refinement passes
        for pass_num in range(1, self.MAX_PASSES + 1):
            print(f"\n{'='*60}")
            print(f"PASS {pass_num} OF {self.MAX_PASSES}")
            print(f"{'='*60}\n")

            # Process frames that aren't complete yet
            incomplete = [s for s in states if not s.is_complete]
            if not incomplete:
                print("All frames complete!")
                break

            print(f"Frames to process: {len(incomplete)}")

            # Generate/Edit phase
            if pass_num == 1:
                await self._generate_pass(states)
            else:
                await self._edit_pass(states, pass_num)

            # Evaluation phase
            await self._evaluate_pass(states)

            # Check completion
            self._check_completion(states)

            # Print pass summary
            self._print_pass_summary(states, pass_num)

        # Final summary
        self._print_final_summary(states)
        self._save_report(states)

        return states

    async def _generate_pass(self, states: list[RefinementState]):
        """Pass 1: Generate all base images."""
        print("GENERATING BASE IMAGES...")
        print("-" * 40)

        for state in states:
            state.pass_number = 1
            output_path = self.output_dir / f"{state.spec.frame_id.replace('.', '_')}_p1.png"

            # Combine refs
            refs = state.spec.character_refs + state.spec.location_refs

            if not refs:
                print(f"  [{state.spec.frame_id}] SKIPPED - no reference images for P-Edit")
                continue

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
                print(f"  [{state.spec.frame_id}] Generated ({result.generation_time_ms}ms)")
            else:
                print(f"  [{state.spec.frame_id}] FAILED: {result.error}")

    async def _edit_pass(self, states: list[RefinementState], pass_num: int):
        """Pass 2+: Apply correction edits based on evaluation."""
        print(f"APPLYING CORRECTION EDITS (Pass {pass_num})...")
        print("-" * 40)

        for state in states:
            if state.is_complete or not state.current_image:
                continue

            # Get latest evaluation
            if not state.evaluations:
                continue

            eval_result = state.evaluations[-1]

            # Check if needs full regeneration vs edit
            if eval_result.needs_regeneration or eval_result.overall_score < self.REGENERATION_THRESHOLD:
                await self._regenerate_frame(state, pass_num)
            else:
                await self._edit_frame(state, pass_num)

    async def _regenerate_frame(self, state: RefinementState, pass_num: int):
        """Regenerate a frame from scratch with improved prompt."""
        eval_result = state.evaluations[-1]

        # Build negative prompt from issues
        negatives = self._build_negative_prompt(eval_result)

        # Enhanced prompt with negatives
        enhanced_prompt = state.spec.prompt
        if negatives:
            enhanced_prompt += f"\n\nAVOID THESE ISSUES:\n{negatives}"

        output_path = self.output_dir / f"{state.spec.frame_id.replace('.', '_')}_p{pass_num}.png"
        refs = state.spec.character_refs + state.spec.location_refs

        result = await self.handler.generate(ImageRequest(
            prompt=enhanced_prompt,
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
            state.pass_number = pass_num
            print(f"  [{state.spec.frame_id}] REGENERATED ({result.generation_time_ms}ms)")
        else:
            print(f"  [{state.spec.frame_id}] Regenerate FAILED: {result.error}")

    async def _edit_frame(self, state: RefinementState, pass_num: int):
        """Apply targeted edits to improve the frame."""
        eval_result = state.evaluations[-1]

        # Build edit prompt from fix tasks
        edit_prompt = self._build_edit_prompt(eval_result)
        if not edit_prompt:
            print(f"  [{state.spec.frame_id}] No edits needed")
            return

        # Build negative prompt from issues
        negatives = self._build_negative_prompt(eval_result)
        if negatives:
            edit_prompt += f"\n\nDO NOT:\n{negatives}"

        output_path = self.output_dir / f"{state.spec.frame_id.replace('.', '_')}_p{pass_num}.png"

        # Use current image + character ref
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

        if result.success:
            state.current_image = output_path
            state.image_versions.append(output_path)
            state.pass_number = pass_num
            print(f"  [{state.spec.frame_id}] EDITED ({result.generation_time_ms}ms)")
        else:
            print(f"  [{state.spec.frame_id}] Edit FAILED: {result.error}")

    def _build_negative_prompt(self, eval_result: FrameEvaluation) -> str:
        """Build negative prompt from evaluation issues."""
        negatives = []

        for task in eval_result.fix_tasks:
            # Convert issue to negative instruction
            issue = task.issue.lower()

            # Extract key problems
            if "two people" in issue or "multiple people" in issue or "extra person" in issue:
                negatives.append("- Do NOT show multiple people or extra figures")
            if "wrong clothing" in issue or "sweater" in issue or "modern" in issue:
                negatives.append("- Do NOT show modern clothing, sweaters, or casual wear")
            if "seated" in issue or "sitting" in issue:
                negatives.append("- Do NOT show character seated or sitting")
            if "wrong character" in issue or "wrong gender" in issue or "man instead" in issue:
                negatives.append("- Do NOT show wrong gender or different character")
            if "night" in issue or "wrong time" in issue:
                negatives.append("- Do NOT show nighttime or wrong time of day")
            if "cgi" in issue or "artificial" in issue:
                negatives.append("- Do NOT create CGI or artificial looking images")

        # Deduplicate
        negatives = list(set(negatives))
        return "\n".join(negatives[:5])  # Max 5 negatives

    def _build_edit_prompt(self, eval_result: FrameEvaluation) -> str:
        """Build edit prompt from fix tasks."""
        if not eval_result.fix_tasks:
            return ""

        # Take top 2 priority fixes
        top_fixes = eval_result.fix_tasks[:2]

        changes = []
        preserves = set()

        for fix in top_fixes:
            changes.append(f"- {fix.fix_instruction}")
            preserves.update(fix.preserve_elements)

        prompt = "APPLY THESE CORRECTIONS:\n" + "\n".join(changes)

        if preserves:
            prompt += f"\n\nPRESERVE: {', '.join(preserves)}"

        return prompt

    async def _evaluate_pass(self, states: list[RefinementState]):
        """Evaluate all frames with continuity context."""
        print("\nEVALUATING FRAMES...")
        print("-" * 40)

        for i, state in enumerate(states):
            if not state.current_image or not state.current_image.exists():
                continue

            # Get adjacent frames for continuity
            prev_state = states[i-1] if i > 0 else None
            next_state = states[i+1] if i < len(states)-1 else None

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

            evaluation = self.evaluator.evaluate_frame(context)
            state.evaluations.append(evaluation)
            state.current_score = evaluation.overall_score

            # Print result
            issues = len(evaluation.fix_tasks)
            status = "REGEN" if evaluation.needs_regeneration else ("EDIT" if issues > 0 else "OK")
            print(f"  [{state.spec.frame_id}] Score: {evaluation.overall_score:.1f}/10 [{status}] - {issues} issues")

    def _check_completion(self, states: list[RefinementState]):
        """Mark frames as complete if they meet threshold."""
        for state in states:
            if state.current_score >= self.COMPLETION_THRESHOLD:
                state.is_complete = True
            elif state.pass_number >= self.MAX_PASSES:
                state.is_complete = True  # Max passes reached

    def _print_pass_summary(self, states: list[RefinementState], pass_num: int):
        """Print summary after each pass."""
        print(f"\n--- PASS {pass_num} SUMMARY ---")

        complete = sum(1 for s in states if s.is_complete)
        total_score = sum(s.current_score for s in states if s.current_image)
        count = sum(1 for s in states if s.current_image)
        avg = total_score / count if count > 0 else 0

        print(f"Complete: {complete}/{len(states)}")
        print(f"Average Score: {avg:.1f}/10")

    def _print_final_summary(self, states: list[RefinementState]):
        """Print final summary."""
        print(f"\n{'='*60}")
        print("FINAL RESULTS")
        print(f"{'='*60}\n")

        for state in states:
            if not state.current_image:
                print(f"[{state.spec.frame_id}] FAILED - no image generated")
                continue

            # Show score progression
            scores = [e.overall_score for e in state.evaluations]
            score_str = " -> ".join(f"{s:.1f}" for s in scores)

            improvement = scores[-1] - scores[0] if len(scores) > 1 else 0
            imp_str = f"(+{improvement:.1f})" if improvement > 0 else f"({improvement:.1f})" if improvement < 0 else ""

            print(f"[{state.spec.frame_id}] {score_str} {imp_str} - {len(state.image_versions)} versions")

    def _save_report(self, states: list[RefinementState]):
        """Save detailed report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "model": self.model.value,
            "max_passes": self.MAX_PASSES,
            "completion_threshold": self.COMPLETION_THRESHOLD,
            "frames": []
        }

        for state in states:
            frame_report = {
                "frame_id": state.spec.frame_id,
                "final_image": str(state.current_image) if state.current_image else None,
                "final_score": state.current_score,
                "passes_used": state.pass_number,
                "is_complete": state.is_complete,
                "score_progression": [e.overall_score for e in state.evaluations],
                "image_versions": [str(p) for p in state.image_versions]
            }
            report["frames"].append(frame_report)

        report_path = self.output_dir / f"refinement_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved: {report_path}")


async def run_iterative_refinement(
    project_path: Path,
    frame_specs: list[FrameSpec],
    model: ImageModel = ImageModel.P_IMAGE_EDIT
) -> list[RefinementState]:
    """Run the iterative refinement pipeline."""
    pipeline = IterativeRefinementPipeline(project_path, model)
    return await pipeline.refine_batch(frame_specs)
