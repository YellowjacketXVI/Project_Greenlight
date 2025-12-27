"""
Storyboard Refinement Pipeline

A batch processing pipeline that:
1. Generates frames sequentially with continuity awareness
2. Evaluates each frame against prompt + adjacent frames
3. Groups frames by scene for chunked editing
4. Applies targeted fixes in priority order
5. Re-evaluates to confirm improvements

Key concepts:
- Continuity chunks: Groups of 3 frames (N-1, N, N+1) evaluated together
- Scene coherence: All frames in a scene share visual consistency
- Layered editing: Apply critical fixes first, then major, then minor
"""

import asyncio
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
from greenlight.agents.frame_evaluation_agent import (
    FrameEvaluationAgent, FrameContext, FrameEvaluation, FixPriority
)


@dataclass
class FrameSpec:
    """Specification for a single frame to generate."""
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
class GeneratedFrame:
    """A generated frame with its evaluation."""
    spec: FrameSpec
    image_path: Path
    evaluation: Optional[FrameEvaluation] = None
    generation_time_ms: int = 0
    edit_history: list[str] = field(default_factory=list)


@dataclass
class StoryboardBatch:
    """A batch of frames to process together."""
    frames: list[GeneratedFrame]
    scene_id: str

    def get_frame(self, frame_id: str) -> Optional[GeneratedFrame]:
        for f in self.frames:
            if f.spec.frame_id == frame_id:
                return f
        return None

    def get_adjacent(self, frame_id: str) -> tuple[Optional[GeneratedFrame], Optional[GeneratedFrame]]:
        """Get previous and next frames for continuity."""
        idx = None
        for i, f in enumerate(self.frames):
            if f.spec.frame_id == frame_id:
                idx = i
                break

        if idx is None:
            return None, None

        prev_frame = self.frames[idx - 1] if idx > 0 else None
        next_frame = self.frames[idx + 1] if idx < len(self.frames) - 1 else None
        return prev_frame, next_frame


class StoryboardRefinementPipeline:
    """
    Pipeline for generating and refining storyboard frames with
    evaluation-driven editing and continuity checking.
    """

    REGENERATION_THRESHOLD = 4.0  # Score below this triggers regeneration
    EDIT_THRESHOLD = 7.0  # Score below this triggers editing
    MAX_EDIT_PASSES = 2  # Maximum edit iterations per frame

    def __init__(self, project_path: Path, model: ImageModel = ImageModel.P_IMAGE_EDIT):
        self.project_path = project_path
        self.model = model
        self.handler = ImageHandler(project_path)
        self.evaluator = FrameEvaluationAgent()
        self.output_dir = project_path / "storyboard_output" / "refinement_pipeline"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def process_batch(self, frame_specs: list[FrameSpec]) -> StoryboardBatch:
        """
        Process a batch of frames through the full pipeline:
        1. Generate all frames
        2. Evaluate with continuity
        3. Apply fixes in chunks
        4. Re-evaluate
        """
        print(f"\n{'='*60}")
        print(f"STORYBOARD REFINEMENT PIPELINE")
        print(f"Processing {len(frame_specs)} frames")
        print(f"{'='*60}\n")

        # Group by scene
        scene_id = frame_specs[0].scene_id if frame_specs else "1"
        batch = StoryboardBatch(frames=[], scene_id=scene_id)

        # Phase 1: Generate all frames
        print("PHASE 1: INITIAL GENERATION")
        print("-" * 40)
        for spec in frame_specs:
            frame = await self._generate_frame(spec)
            batch.frames.append(frame)
            print(f"  [{spec.frame_id}] Generated in {frame.generation_time_ms}ms")

        # Phase 2: Evaluate all frames with continuity context
        print("\nPHASE 2: EVALUATION WITH CONTINUITY")
        print("-" * 40)
        await self._evaluate_batch(batch)

        # Print evaluation summary
        self._print_evaluation_summary(batch)

        # Phase 3: Apply fixes based on evaluation
        print("\nPHASE 3: APPLYING FIXES")
        print("-" * 40)
        await self._apply_batch_fixes(batch)

        # Phase 4: Re-evaluate to confirm improvements
        print("\nPHASE 4: RE-EVALUATION")
        print("-" * 40)
        await self._evaluate_batch(batch)
        self._print_evaluation_summary(batch)

        # Save results
        self._save_batch_report(batch)

        return batch

    async def _generate_frame(self, spec: FrameSpec) -> GeneratedFrame:
        """Generate a single frame."""
        output_path = self.output_dir / f"{spec.frame_id.replace('.', '_')}_v1.png"

        # Combine character and location refs
        refs = spec.character_refs + spec.location_refs

        result = await self.handler.generate(ImageRequest(
            prompt=spec.prompt,
            model=self.model,
            reference_images=refs[:4],  # Max 4 refs
            output_path=output_path,
            aspect_ratio="16:9",
            prefix_type="create",
            add_clean_suffix=True
        ))

        return GeneratedFrame(
            spec=spec,
            image_path=output_path if result.success else None,
            generation_time_ms=result.generation_time_ms
        )

    async def _evaluate_batch(self, batch: StoryboardBatch):
        """Evaluate all frames with continuity context."""
        for frame in batch.frames:
            if not frame.image_path or not frame.image_path.exists():
                continue

            # Get adjacent frames for continuity
            prev_frame, next_frame = batch.get_adjacent(frame.spec.frame_id)

            context = FrameContext(
                frame_id=frame.spec.frame_id,
                generated_image_path=frame.image_path,
                original_prompt=frame.spec.prompt,
                visual_description=frame.spec.visual_description,
                character_refs=frame.spec.character_refs,
                location_refs=frame.spec.location_refs,
                scene_id=frame.spec.scene_id,
                location_name=frame.spec.location,
                time_of_day=frame.spec.time_of_day,
                characters_in_frame=frame.spec.characters,
                prev_frame_path=prev_frame.image_path if prev_frame else None,
                prev_frame_description=prev_frame.spec.visual_description if prev_frame else None,
                next_frame_path=next_frame.image_path if next_frame else None,
                next_frame_description=next_frame.spec.visual_description if next_frame else None
            )

            frame.evaluation = self.evaluator.evaluate_frame(context)
            print(f"  [{frame.spec.frame_id}] Score: {frame.evaluation.overall_score}/10" +
                  (" (REGENERATE)" if frame.evaluation.needs_regeneration else ""))

    async def _apply_batch_fixes(self, batch: StoryboardBatch):
        """Apply fixes to frames that need them."""
        for frame in batch.frames:
            if not frame.evaluation:
                continue

            score = frame.evaluation.overall_score

            if frame.evaluation.needs_regeneration or score < self.REGENERATION_THRESHOLD:
                # Regenerate from scratch with improved prompt
                print(f"  [{frame.spec.frame_id}] Regenerating (score: {score})")
                await self._regenerate_frame(frame, batch)

            elif score < self.EDIT_THRESHOLD and frame.evaluation.fix_tasks:
                # Apply targeted edits
                print(f"  [{frame.spec.frame_id}] Applying edits (score: {score})")
                await self._edit_frame(frame, batch)
            else:
                print(f"  [{frame.spec.frame_id}] Good enough (score: {score})")

    async def _regenerate_frame(self, frame: GeneratedFrame, batch: StoryboardBatch):
        """Regenerate a frame with an enhanced prompt."""
        # Get adjacent frames for context
        prev_frame, next_frame = batch.get_adjacent(frame.spec.frame_id)

        # Build enhanced prompt with continuity notes
        continuity_notes = []
        if prev_frame and prev_frame.image_path:
            continuity_notes.append(f"PREVIOUS FRAME: {prev_frame.spec.visual_description}")
        if next_frame and next_frame.image_path:
            continuity_notes.append(f"NEXT FRAME: {next_frame.spec.visual_description}")

        enhanced_prompt = frame.spec.prompt
        if continuity_notes:
            enhanced_prompt += "\n\nCONTINUITY CONTEXT:\n" + "\n".join(continuity_notes)

        # Version the output
        version = len(frame.edit_history) + 2
        output_path = self.output_dir / f"{frame.spec.frame_id.replace('.', '_')}_v{version}.png"

        refs = frame.spec.character_refs + frame.spec.location_refs

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
            frame.image_path = output_path
            frame.edit_history.append(f"regenerated_v{version}")
            frame.generation_time_ms = result.generation_time_ms

    async def _edit_frame(self, frame: GeneratedFrame, batch: StoryboardBatch):
        """Apply targeted edits based on evaluation."""
        # Generate edit prompt from evaluation
        edit_prompt = self.evaluator.generate_edit_prompt(
            frame.evaluation,
            max_fixes=2  # Focus on top 2 issues
        )

        if not edit_prompt:
            return

        # Version the output
        version = len(frame.edit_history) + 2
        output_path = self.output_dir / f"{frame.spec.frame_id.replace('.', '_')}_v{version}.png"

        # Include character ref for consistency
        refs = [frame.image_path] + frame.spec.character_refs[:1]

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
            frame.image_path = output_path
            frame.edit_history.append(f"edited_v{version}")
            frame.generation_time_ms = result.generation_time_ms

    def _print_evaluation_summary(self, batch: StoryboardBatch):
        """Print a summary of all evaluations."""
        print("\n  EVALUATION SUMMARY:")
        print("  " + "-" * 50)

        total_score = 0
        count = 0

        for frame in batch.frames:
            if frame.evaluation:
                score = frame.evaluation.overall_score
                total_score += score
                count += 1

                status = "OK" if score >= self.EDIT_THRESHOLD else ("EDIT" if score >= self.REGENERATION_THRESHOLD else "REGEN")
                issues = len(frame.evaluation.fix_tasks)

                print(f"  [{frame.spec.frame_id}] {score:4.1f}/10 [{status:5}] - {issues} issues")

        if count > 0:
            avg = total_score / count
            print("  " + "-" * 50)
            print(f"  AVERAGE: {avg:.1f}/10")

    def _save_batch_report(self, batch: StoryboardBatch):
        """Save a JSON report of the batch processing."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "scene_id": batch.scene_id,
            "model": self.model.value,
            "frames": []
        }

        for frame in batch.frames:
            frame_report = {
                "frame_id": frame.spec.frame_id,
                "image_path": str(frame.image_path) if frame.image_path else None,
                "generation_time_ms": frame.generation_time_ms,
                "edit_history": frame.edit_history
            }

            if frame.evaluation:
                frame_report["evaluation"] = {
                    "score": frame.evaluation.overall_score,
                    "needs_regeneration": frame.evaluation.needs_regeneration,
                    "strengths": frame.evaluation.strengths,
                    "issues": [
                        {
                            "category": t.category.value,
                            "priority": t.priority.name,
                            "issue": t.issue
                        }
                        for t in frame.evaluation.fix_tasks
                    ]
                }

            report["frames"].append(frame_report)

        report_path = self.output_dir / f"batch_report_{batch.scene_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to: {report_path}")


# Convenience function to run the pipeline
async def run_refinement_pipeline(
    project_path: Path,
    frame_specs: list[FrameSpec],
    model: ImageModel = ImageModel.P_IMAGE_EDIT
) -> StoryboardBatch:
    """Run the full refinement pipeline on a batch of frames."""
    pipeline = StoryboardRefinementPipeline(project_path, model)
    return await pipeline.process_batch(frame_specs)
