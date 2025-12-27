"""
Advanced Storyboard Pipeline with Agentic Refinement

This pipeline adds AI-powered analysis and correction to storyboard generation:
1. Generate initial frames with selected image model
2. Gemini analyzes each frame against script context
3. Correction loop: Identify issues -> Apply edits -> Re-evaluate
4. Batch coherency check across all frames in each scene
5. Final coherency-based corrections if needed

Supports any image model, with edit-capable models (P-Image-Edit) getting
the full correction loop, and other models getting analysis-only feedback.
"""

import asyncio
import json
import base64
import httpx
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime

from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
from greenlight.core.logging_config import get_logger

logger = get_logger("pipelines.advanced_storyboard")


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class FrameContext:
    """Full context for a frame from the visual script."""
    frame_id: str
    scene_id: str
    prompt: str
    visual_description: str = ""
    camera_notation: str = ""
    position_notation: str = ""
    lighting_notation: str = ""
    characters: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    props: list[str] = field(default_factory=list)
    location_direction: str = "NORTH"


@dataclass
class SceneContext:
    """Context for a scene from the script."""
    scene_id: str
    scene_title: str = ""
    location: str = ""
    time_of_day: str = ""
    mood: str = ""
    script_excerpt: str = ""
    visual_style: str = ""


@dataclass
class CorrectionTask:
    """A specific correction to apply."""
    category: str  # character, clothing, pose, lighting, composition, continuity
    priority: str  # critical, major, minor
    issue: str
    fix_instruction: str


@dataclass
class FrameAnalysis:
    """Result of Gemini frame analysis."""
    score: float
    passed: bool
    analysis: str
    corrections: list[CorrectionTask] = field(default_factory=list)


@dataclass
class CoherencyIssue:
    """A coherency issue between frames."""
    frames_affected: list[str]
    category: str
    severity: str
    issue: str
    fix_instruction: str


@dataclass
class BatchCoherencyResult:
    """Result of batch coherency analysis."""
    coherency_score: float
    passed: bool
    issues: list[CoherencyIssue] = field(default_factory=list)
    frame_notes: dict[str, str] = field(default_factory=dict)
    summary: str = ""


@dataclass
class FrameResult:
    """Final result for a frame."""
    frame_id: str
    image_path: Optional[Path]
    score: float
    iteration: int
    corrections_applied: list[str] = field(default_factory=list)
    passed: bool = False
    analysis: str = ""


# =============================================================================
# GEMINI ANALYSIS AGENT
# =============================================================================

class GeminiAnalysisAgent:
    """Agent that uses Gemini to analyze frames against script context."""

    ANALYSIS_PROMPT = '''You are a professional film director analyzing a storyboard frame.

## SCENE CONTEXT
Scene: {scene_id} - {scene_title}
Location: {location}
Time of Day: {time_of_day}
Mood: {mood}
Visual Style: {visual_style}

Script/Context:
"{script_excerpt}"

## FRAME SPECIFICATION
Frame ID: {frame_id}
Characters Expected: {characters}
Camera: {camera_notation}
Position: {position_notation}
Lighting: {lighting_notation}

## GENERATION PROMPT (What was requested)
{prompt}

## YOUR TASK
Analyze the GENERATED IMAGE against the script context and frame specification.

Score the frame 1-10 based on:
- Does it match the script context and mood?
- Is the shot type/framing correct?
- Are characters correct (right person, right clothing, right pose)?
- Is lighting/time of day correct?
- Is it cinematic quality?

If score < 8, identify specific corrections needed.

## OUTPUT FORMAT (JSON only)
```json
{{
    "score": 7.5,
    "passed": false,
    "analysis": "Brief description of what's good and what's wrong",
    "corrections": [
        {{
            "category": "character",
            "priority": "critical",
            "issue": "Shows a man but should be young Asian woman",
            "fix_instruction": "Change to young Asian woman with long black hair"
        }}
    ]
}}
```

Categories: character, clothing, pose, lighting, composition, continuity, props
Priorities: critical (must fix), major (should fix), minor (polish)

If score >= 8 and no critical issues, set passed: true and corrections: []

ANALYZE THE IMAGE:'''

    COHERENCY_PROMPT = '''You are a professional film continuity supervisor analyzing storyboard frames.

## SCENE CONTEXT
Scene: {scene_id} - {scene_title}
Location: {location}
Time of Day: {time_of_day}
Characters: {characters}

Script Context:
"{script_excerpt}"

## FRAMES TO ANALYZE
{frame_descriptions}

## YOUR TASK
Analyze ALL frames together for COHERENCY and CONSISTENCY:

1. CHARACTER CONSISTENCY - Same person looks same across frames?
2. CLOTHING CONSISTENCY - Same outfit across frames?
3. LIGHTING CONSISTENCY - Same time of day/lighting direction?
4. LOCATION CONSISTENCY - Same place looks consistent?
5. STYLE CONSISTENCY - Same visual style throughout?
6. CONTINUITY FLOW - Frames flow naturally as sequence?

## OUTPUT FORMAT (JSON only)
```json
{{
    "coherency_score": 8.5,
    "passed": true,
    "summary": "Brief overall assessment",
    "frame_notes": {{
        "1.5": "Good - character consistent",
        "1.6": "Issue - lighting differs"
    }},
    "issues": [
        {{
            "frames_affected": ["1.5", "1.6"],
            "category": "lighting",
            "severity": "major",
            "issue": "Lighting direction changes between frames",
            "fix_instruction": "Regenerate 1.6 with same lighting as 1.5"
        }}
    ]
}}
```

Categories: character, clothing, lighting, location, style, continuity
Severity: critical, major, minor

If coherency_score >= 8 and no critical issues, set passed: true.

ANALYZE THESE FRAMES:'''

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")

    def analyze_frame(
        self,
        image_path: Path,
        frame_context: FrameContext,
        scene_context: SceneContext,
        character_refs: list[Path] = None
    ) -> FrameAnalysis:
        """Analyze a single frame against its context."""
        prompt = self.ANALYSIS_PROMPT.format(
            scene_id=scene_context.scene_id,
            scene_title=scene_context.scene_title,
            location=scene_context.location,
            time_of_day=scene_context.time_of_day,
            mood=scene_context.mood,
            visual_style=scene_context.visual_style,
            script_excerpt=scene_context.script_excerpt,
            frame_id=frame_context.frame_id,
            characters=", ".join(frame_context.characters) or "None specified",
            camera_notation=frame_context.camera_notation or "Not specified",
            position_notation=frame_context.position_notation or "Not specified",
            lighting_notation=frame_context.lighting_notation or "Not specified",
            prompt=frame_context.prompt
        )

        images = [image_path]
        if character_refs:
            for ref in character_refs[:2]:
                if ref.exists():
                    images.append(ref)

        response = self._call_gemini(prompt, images)
        return self._parse_analysis(response)

    def check_batch_coherency(
        self,
        frames: list[tuple[str, Path, str]],
        scene_context: SceneContext,
        character_refs: list[Path] = None
    ) -> BatchCoherencyResult:
        """Check coherency across multiple frames."""
        frame_descriptions = []
        for frame_id, path, desc in frames:
            frame_descriptions.append(f"Frame {frame_id}: {desc}")

        prompt = self.COHERENCY_PROMPT.format(
            scene_id=scene_context.scene_id,
            scene_title=scene_context.scene_title,
            location=scene_context.location,
            time_of_day=scene_context.time_of_day,
            characters=", ".join(set()),  # Will be filled from frames
            script_excerpt=scene_context.script_excerpt,
            frame_descriptions="\n".join(frame_descriptions)
        )

        images = []
        if character_refs:
            for ref in character_refs[:2]:
                if ref.exists():
                    images.append(ref)

        for frame_id, path, desc in frames:
            if path and path.exists():
                images.append(path)

        response = self._call_gemini(prompt, images)
        return self._parse_coherency(response)

    def _call_gemini(self, prompt: str, image_paths: list[Path]) -> str:
        """Call Gemini with images."""
        parts = []

        for img_path in image_paths:
            if img_path.exists():
                with open(img_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")

                suffix = img_path.suffix.lower()
                mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(suffix, "image/png")

                parts.append({
                    "inline_data": {"mime_type": mime, "data": img_data}
                })

        parts.append({"text": prompt})

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096}
        }

        with httpx.Client(timeout=180.0) as client:
            response = client.post(url, json=body, headers=headers)
            response.raise_for_status()
            result = response.json()

        text = ""
        for part in result.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            if "text" in part:
                text += part["text"]
        return text

    def _parse_analysis(self, response: str) -> FrameAnalysis:
        """Parse analysis response."""
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            corrections = []
            for c in data.get("corrections", []):
                corrections.append(CorrectionTask(
                    category=c.get("category", "unknown"),
                    priority=c.get("priority", "minor"),
                    issue=c.get("issue", ""),
                    fix_instruction=c.get("fix_instruction", "")
                ))

            return FrameAnalysis(
                score=data.get("score", 5.0),
                passed=data.get("passed", False),
                analysis=data.get("analysis", ""),
                corrections=corrections
            )
        except Exception as e:
            logger.warning(f"Analysis parse error: {e}")
            return FrameAnalysis(score=5.0, passed=False, analysis=f"Parse error: {e}")

    def _parse_coherency(self, response: str) -> BatchCoherencyResult:
        """Parse coherency response."""
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            issues = []
            for issue_data in data.get("issues", []):
                issues.append(CoherencyIssue(
                    frames_affected=issue_data.get("frames_affected", []),
                    category=issue_data.get("category", "unknown"),
                    severity=issue_data.get("severity", "minor"),
                    issue=issue_data.get("issue", ""),
                    fix_instruction=issue_data.get("fix_instruction", "")
                ))

            return BatchCoherencyResult(
                coherency_score=data.get("coherency_score", 5.0),
                passed=data.get("passed", False),
                issues=issues,
                frame_notes=data.get("frame_notes", {}),
                summary=data.get("summary", "")
            )
        except Exception as e:
            logger.warning(f"Coherency parse error: {e}")
            return BatchCoherencyResult(coherency_score=5.0, passed=False, summary=f"Parse error: {e}")


# =============================================================================
# ADVANCED STORYBOARD PIPELINE
# =============================================================================

class AdvancedStoryboardPipeline:
    """
    Advanced storyboard pipeline with Gemini analysis and correction loops.

    Features:
    - Initial generation with any image model
    - Per-frame Gemini analysis against script context
    - Correction loops for edit-capable models (P-Image-Edit)
    - Batch coherency checking within scenes
    - Detailed logging and progress reporting
    """

    MAX_CORRECTIONS = 3  # Max correction rounds per frame
    TARGET_SCORE = 8.0   # Score threshold to pass

    def __init__(
        self,
        project_path: Path,
        image_model: ImageModel = ImageModel.SEEDREAM,
        log_callback: Callable[[str], None] = None,
        progress_callback: Callable[[float], None] = None,
        stage_callback: Callable[[str, str, str], None] = None
    ):
        self.project_path = Path(project_path)
        self.image_model = image_model
        self.log = log_callback or (lambda msg: print(msg))
        self.progress = progress_callback or (lambda p: None)
        self.stage = stage_callback or (lambda n, s, m: None)

        self.output_dir = self.project_path / "storyboard_output" / "generated"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.handler = ImageHandler(project_path=self.project_path)
        self.analyzer = GeminiAnalysisAgent()

        # Check if model supports editing
        self.supports_editing = image_model in [
            ImageModel.P_IMAGE_EDIT,
            ImageModel.FLUX_2_PRO,
            ImageModel.SEEDREAM
        ]

    async def process_frames(
        self,
        frames: list[dict],
        world_config: dict,
        scene_contexts: dict[str, SceneContext] = None
    ) -> tuple[list[FrameResult], dict]:
        """
        Process frames through the advanced pipeline.

        Args:
            frames: List of frame dicts from visual_script.json
            world_config: World config with character/location data
            scene_contexts: Optional pre-built scene contexts

        Returns:
            Tuple of (results list, metrics dict)
        """
        total_frames = len(frames)
        self.log(f"[ADVANCED] Processing {total_frames} frames with {self.image_model.value}")
        self.log(f"  Edit mode: {'Enabled' if self.supports_editing else 'Analysis only'}")
        self.log(f"  Target score: {self.TARGET_SCORE}/10")
        self.stage("Initialization", "complete", f"{total_frames} frames loaded")

        results: list[FrameResult] = []
        scene_results: dict[str, list[FrameResult]] = {}

        # Group frames by scene
        frames_by_scene: dict[str, list[dict]] = {}
        for frame in frames:
            scene_id = self._get_scene_id(frame)
            if scene_id not in frames_by_scene:
                frames_by_scene[scene_id] = []
            frames_by_scene[scene_id].append(frame)

        # Process each scene
        total_processed = 0
        for scene_id, scene_frames in frames_by_scene.items():
            self.log(f"\n--- Scene {scene_id} ({len(scene_frames)} frames) ---")

            # Get or build scene context
            scene_context = None
            if scene_contexts and scene_id in scene_contexts:
                scene_context = scene_contexts[scene_id]
            else:
                scene_context = self._build_scene_context(scene_id, scene_frames, world_config)

            scene_results[scene_id] = []

            # Process each frame in scene
            for frame in scene_frames:
                result = await self._process_single_frame(
                    frame, scene_context, world_config
                )
                results.append(result)
                scene_results[scene_id].append(result)

                total_processed += 1
                self.progress(0.1 + (total_processed / total_frames) * 0.7)

            # Batch coherency check for this scene
            if len(scene_results[scene_id]) >= 2:
                self.log(f"  Checking scene {scene_id} coherency...")
                await self._check_scene_coherency(
                    scene_results[scene_id],
                    scene_context,
                    world_config
                )

        # Calculate final metrics
        metrics = self._calculate_metrics(results)
        self._print_summary(results, metrics)

        self.stage("Complete", "complete", f"{metrics['passed']}/{metrics['total']} passed")
        self.progress(1.0)

        return results, metrics

    async def _process_single_frame(
        self,
        frame: dict,
        scene_context: SceneContext,
        world_config: dict
    ) -> FrameResult:
        """Process a single frame with generation and correction loop."""
        frame_id = frame.get("frame_id", "unknown")
        prompt = frame.get("prompt", "")

        self.log(f"  [{frame_id}] Generating...")

        # Build frame context
        frame_context = FrameContext(
            frame_id=frame_id,
            scene_id=scene_context.scene_id,
            prompt=prompt,
            visual_description=frame.get("visual_description", ""),
            camera_notation=frame.get("camera_notation", ""),
            position_notation=frame.get("position_notation", ""),
            lighting_notation=frame.get("lighting_notation", ""),
            characters=frame.get("tags", {}).get("characters", []),
            locations=frame.get("tags", {}).get("locations", []),
            props=frame.get("tags", {}).get("props", []),
            location_direction=frame.get("location_direction", "NORTH")
        )

        # Get reference images
        reference_images = self._get_reference_images(frame_context, world_config)
        character_refs = [r for r in reference_images if "CHAR_" in str(r)]

        # Initial generation
        clean_id = frame_id.replace("[", "").replace("]", "")
        output_path = self.output_dir / f"{clean_id}.png"

        gen_result = await self.handler.generate(ImageRequest(
            prompt=prompt,
            model=self.image_model,
            reference_images=reference_images,
            output_path=output_path,
            aspect_ratio="16:9",
            prefix_type="generate",
            add_clean_suffix=True
        ))

        if not gen_result.success:
            self.log(f"    [X] Generation failed: {gen_result.error}")
            return FrameResult(frame_id, None, 0, 0, [], False, gen_result.error)

        current_image = output_path
        corrections_applied = []

        # Analysis and correction loop
        for iteration in range(1, self.MAX_CORRECTIONS + 1):
            # Analyze with Gemini
            analysis = self.analyzer.analyze_frame(
                current_image,
                frame_context,
                scene_context,
                character_refs
            )

            self.log(f"    [{iteration}] Score: {analysis.score:.1f}/10 | {'PASS' if analysis.passed else 'NEEDS FIX'}")

            if analysis.passed or analysis.score >= self.TARGET_SCORE:
                return FrameResult(
                    frame_id, current_image, analysis.score, iteration,
                    corrections_applied, True, analysis.analysis
                )

            if not analysis.corrections:
                self.log(f"    No corrections identified")
                break

            # Apply corrections if model supports editing
            if not self.supports_editing:
                self.log(f"    (Edit not supported for {self.image_model.value})")
                return FrameResult(
                    frame_id, current_image, analysis.score, iteration,
                    [], False, analysis.analysis
                )

            # Build correction prompt
            edit_prompt = self._build_correction_prompt(analysis.corrections, frame_context)
            edit_output = self.output_dir / f"{clean_id}_v{iteration + 1}.png"

            edit_result = await self.handler.generate(ImageRequest(
                prompt=edit_prompt,
                model=self.image_model,
                reference_images=[current_image] + character_refs[:1],
                output_path=edit_output,
                aspect_ratio="16:9",
                prefix_type="edit",
                add_clean_suffix=True
            ))

            if edit_result.success:
                current_image = edit_output
                corrections_applied.extend([c.fix_instruction for c in analysis.corrections[:2]])
                self.log(f"    Applied {len(analysis.corrections)} correction(s)")
            else:
                self.log(f"    Edit failed: {edit_result.error}")
                break

        # Final analysis
        final_analysis = self.analyzer.analyze_frame(
            current_image, frame_context, scene_context, character_refs
        )

        return FrameResult(
            frame_id, current_image, final_analysis.score,
            iteration, corrections_applied,
            final_analysis.passed or final_analysis.score >= self.TARGET_SCORE,
            final_analysis.analysis
        )

    async def _check_scene_coherency(
        self,
        scene_results: list[FrameResult],
        scene_context: SceneContext,
        world_config: dict
    ):
        """Check and log coherency for a scene's frames."""
        frames = []
        for result in scene_results:
            if result.image_path and result.image_path.exists():
                frames.append((
                    result.frame_id,
                    result.image_path,
                    result.analysis[:100] if result.analysis else ""
                ))

        if len(frames) < 2:
            return

        # Get character refs for comparison
        char_refs = []
        for char in world_config.get("characters", []):
            tag = char.get("tag", "")
            ref_dir = self.project_path / "references" / tag
            if ref_dir.exists():
                key_file = ref_dir / ".key"
                if key_file.exists():
                    key_name = key_file.read_text().strip()
                    key_path = ref_dir / key_name
                    if key_path.exists():
                        char_refs.append(key_path)

        coherency = self.analyzer.check_batch_coherency(frames, scene_context, char_refs[:2])

        self.log(f"  Scene coherency: {coherency.coherency_score:.1f}/10")
        if coherency.issues:
            for issue in coherency.issues:
                self.log(f"    [{issue.severity.upper()}] {issue.category}: {issue.issue[:50]}...")

    def _get_scene_id(self, frame: dict) -> str:
        """Extract scene ID from frame."""
        frame_id = frame.get("frame_id", "")
        if "." in frame_id:
            return frame_id.split(".")[0]
        return frame.get("scene_number", frame.get("_scene_num", "1"))

    def _build_scene_context(
        self,
        scene_id: str,
        frames: list[dict],
        world_config: dict
    ) -> SceneContext:
        """Build scene context from frames and world config."""
        # Extract common elements from frames
        locations = set()
        for frame in frames:
            tags = frame.get("tags", {})
            for loc in tags.get("locations", []):
                locations.add(loc)

        location_name = ""
        if locations:
            loc_tag = list(locations)[0]
            for loc in world_config.get("locations", []):
                if loc.get("tag") == loc_tag:
                    location_name = loc.get("name", loc_tag)
                    break

        # Get visual style
        visual_style = world_config.get("visual_style", "cinematic photorealistic")

        return SceneContext(
            scene_id=scene_id,
            scene_title=f"Scene {scene_id}",
            location=location_name,
            time_of_day=world_config.get("lighting", ""),
            mood=world_config.get("vibe", ""),
            visual_style=visual_style
        )

    def _get_reference_images(
        self,
        frame_context: FrameContext,
        world_config: dict
    ) -> list[Path]:
        """Get reference images for frame."""
        refs = []
        refs_dir = self.project_path / "references"

        # Character refs
        for char_tag in frame_context.characters:
            char_dir = refs_dir / char_tag
            if char_dir.exists():
                key_file = char_dir / ".key"
                if key_file.exists():
                    key_name = key_file.read_text().strip()
                    key_path = char_dir / key_name
                    if key_path.exists():
                        refs.append(key_path)

        # Location refs
        for loc_tag in frame_context.locations:
            loc_dir = refs_dir / loc_tag
            if loc_dir.exists():
                # Try direction-specific
                direction = frame_context.location_direction.lower()
                for f in loc_dir.glob(f"*_{direction}_*.png"):
                    refs.append(f)
                    break
                else:
                    # Fall back to any
                    for f in loc_dir.glob("*.png"):
                        refs.append(f)
                        break

        return refs[:4]  # Max 4 refs

    def _build_correction_prompt(
        self,
        corrections: list[CorrectionTask],
        frame_context: FrameContext
    ) -> str:
        """Build edit prompt from corrections."""
        critical = [c for c in corrections if c.priority == "critical"]
        major = [c for c in corrections if c.priority == "major"]
        fixes = critical + major[:2]

        prompt = f"""APPLY THESE CORRECTIONS:
"""
        for fix in fixes:
            prompt += f"- {fix.fix_instruction}\n"

        # Add negatives
        negatives = []
        for c in fixes:
            issue = c.issue.lower()
            if "man" in issue and "woman" in c.fix_instruction.lower():
                negatives.append("male figure, man")
            if "modern" in issue:
                negatives.append("modern clothing")

        if negatives:
            prompt += f"\nAVOID: {', '.join(set(negatives))}"

        prompt += f"\n\nPRESERVE: overall composition, lighting direction"

        return prompt

    def _calculate_metrics(self, results: list[FrameResult]) -> dict:
        """Calculate pipeline metrics."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        valid = [r for r in results if r.image_path]
        avg_score = sum(r.score for r in valid) / max(1, len(valid))
        total_corrections = sum(len(r.corrections_applied) for r in results)

        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
            "avg_score": avg_score,
            "total_corrections": total_corrections
        }

    def _print_summary(self, results: list[FrameResult], metrics: dict):
        """Print final summary."""
        self.log(f"\n{'='*60}")
        self.log("ADVANCED STORYBOARD RESULTS")
        self.log(f"{'='*60}")

        for r in results:
            status = "[OK]" if r.passed else "[X]"
            self.log(f"{status} {r.frame_id}: {r.score:.1f}/10 (iter: {r.iteration})")

        self.log(f"\nPassed: {metrics['passed']}/{metrics['total']} ({metrics['pass_rate']:.0f}%)")
        self.log(f"Average Score: {metrics['avg_score']:.1f}/10")
        self.log(f"Total Corrections: {metrics['total_corrections']}")


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

async def run_advanced_storyboard(
    project_path: Path,
    image_model: ImageModel = ImageModel.SEEDREAM,
    max_frames: int = None,
    log_callback: Callable[[str], None] = None
) -> tuple[list[FrameResult], dict]:
    """
    Run advanced storyboard pipeline on a project.

    Args:
        project_path: Path to project directory
        image_model: Image model to use
        max_frames: Optional limit on frames to process
        log_callback: Optional logging callback

    Returns:
        Tuple of (results list, metrics dict)
    """
    project_path = Path(project_path)

    # Load visual script
    vs_path = project_path / "storyboard" / "visual_script.json"
    if not vs_path.exists():
        raise FileNotFoundError(f"Visual script not found: {vs_path}")

    visual_script = json.loads(vs_path.read_text(encoding="utf-8"))

    # Extract frames
    frames = []
    for scene in visual_script.get("scenes", []):
        for frame in scene.get("frames", []):
            frame["_scene_num"] = scene.get("scene_number", "1")
            frames.append(frame)

    if max_frames:
        frames = frames[:max_frames]

    # Load world config
    world_config = {}
    wc_path = project_path / "world_bible" / "world_config.json"
    if wc_path.exists():
        world_config = json.loads(wc_path.read_text(encoding="utf-8"))

    # Run pipeline
    pipeline = AdvancedStoryboardPipeline(
        project_path=project_path,
        image_model=image_model,
        log_callback=log_callback
    )

    return await pipeline.process_frames(frames, world_config)
