"""
Parallel Healing Pipeline for Storyboard Generation

This pipeline runs ALONGSIDE frame generation, analyzing and healing frames
for continuity in sliding windows of 3 frames. As soon as 3 consecutive
frames are generated, the healing process kicks in.

Architecture:
┌─────────────────────────────────────────────────────────────────────┐
│                    PARALLEL PROCESSING                               │
├─────────────────────────────────────────────────────────────────────┤
│  GENERATION QUEUE          │         HEALING QUEUE                  │
│  ─────────────────         │         ─────────────                  │
│  Frame 1 → Generated ──────┼──────→  [1,2,3] Analyze                │
│  Frame 2 → Generated       │              ↓                         │
│  Frame 3 → Generated ──────┼──────→  Heal if needed                 │
│  Frame 4 → Generating      │              ↓                         │
│  Frame 5 → Pending    ─────┼──────→  [2,3,4] Analyze (parallel)     │
│  ...                       │              ↓                         │
│                            │         Continue healing...            │
└─────────────────────────────────────────────────────────────────────┘

Key Features:
- Async queues connect generation and healing workers
- 3-frame sliding window for continuity analysis
- Gemini analyzes: character consistency, lighting, clothing, flow
- Edit-capable models can heal; others get analysis feedback
- Scene boundaries respected (don't analyze across scenes)
- Full story/character context passed to analysis
"""

import asyncio
import json
import base64
import httpx
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Dict, List
from datetime import datetime
from enum import Enum

from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
from greenlight.core.logging_config import get_logger

logger = get_logger("pipelines.parallel_healing")


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class HealingStatus(Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    HEALING = "healing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class GeneratedFrame:
    """A frame that has been generated and is ready for healing analysis."""
    frame_id: str
    scene_id: str
    image_path: Path
    prompt: str
    visual_description: str = ""
    camera_notation: str = ""
    characters: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    character_refs: List[Path] = field(default_factory=list)
    healing_status: HealingStatus = HealingStatus.PENDING
    healing_score: float = 0.0
    healing_notes: str = ""
    healed_path: Optional[Path] = None


@dataclass
class HealingWindow:
    """A window of 3 frames to analyze together for continuity."""
    frames: List[GeneratedFrame]
    target_frame_idx: int  # Which frame (0, 1, or 2) is the focus for healing
    scene_id: str

    @property
    def target_frame(self) -> GeneratedFrame:
        return self.frames[self.target_frame_idx]

    @property
    def window_id(self) -> str:
        return f"{self.frames[0].frame_id}-{self.frames[-1].frame_id}"


@dataclass
class ContinuityIssue:
    """An issue found in continuity analysis."""
    category: str  # character, clothing, lighting, composition, flow
    severity: str  # critical, major, minor
    affected_frame: str
    issue: str
    fix_instruction: str


@dataclass
class WindowAnalysis:
    """Result of analyzing a 3-frame window."""
    window_id: str
    continuity_score: float
    passed: bool
    issues: List[ContinuityIssue] = field(default_factory=list)
    frame_scores: Dict[str, float] = field(default_factory=dict)
    summary: str = ""


# =============================================================================
# CONTINUITY ANALYSIS AGENT
# =============================================================================

class ContinuityAnalysisAgent:
    """Analyzes 3-frame windows for continuity issues using Gemini."""

    ANALYSIS_PROMPT = '''You are a professional film continuity supervisor analyzing a 3-frame storyboard sequence.

## STORY CONTEXT
{story_context}

## SCENE CONTEXT
Scene: {scene_id}
Location: {location}
Time of Day: {time_of_day}
Mood: {mood}

## CHARACTER REFERENCE (if provided)
The reference image shows how this character SHOULD look. Compare the storyboard frames against this reference.

## FRAMES IN SEQUENCE
Frame 1 ({frame_1_id}): {frame_1_desc}
Frame 2 ({frame_2_id}): {frame_2_desc}  [TARGET FRAME]
Frame 3 ({frame_3_id}): {frame_3_desc}

## YOUR TASK
Analyze these 3 consecutive frames for CONTINUITY and CONSISTENCY.
Focus especially on Frame 2 (the target frame) - does it flow naturally from Frame 1 and into Frame 3?

Check for:
1. CHARACTER CONSISTENCY - Same person looks the same across all 3 frames?
2. CLOTHING CONSISTENCY - Same outfit, same state (if disheveled, stays disheveled)?
3. LIGHTING CONSISTENCY - Same time of day, same lighting direction?
4. POSE/POSITION FLOW - Natural progression of movement/position?
5. STYLE CONSISTENCY - Same visual style, same quality level?

Score each frame 1-10 and identify specific issues that need fixing.

## OUTPUT FORMAT (JSON only)
```json
{{
    "continuity_score": 7.5,
    "passed": false,
    "summary": "Brief overall assessment of the 3-frame sequence",
    "frame_scores": {{
        "{frame_1_id}": 8.0,
        "{frame_2_id}": 6.5,
        "{frame_3_id}": 8.0
    }},
    "issues": [
        {{
            "category": "character",
            "severity": "critical",
            "affected_frame": "{frame_2_id}",
            "issue": "Character's face differs significantly from frames 1 and 3",
            "fix_instruction": "Regenerate to match the character's appearance in adjacent frames"
        }}
    ]
}}
```

Categories: character, clothing, lighting, composition, flow
Severity: critical (must fix), major (should fix), minor (polish)

If continuity_score >= 8 and no critical issues, set passed: true.

ANALYZE THE SEQUENCE:'''

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set - healing analysis disabled")

    def analyze_window(
        self,
        window: HealingWindow,
        story_context: str,
        scene_context: Dict[str, str],
        character_refs: List[Path] = None
    ) -> WindowAnalysis:
        """Analyze a 3-frame window for continuity issues."""
        if not self.api_key:
            return WindowAnalysis(
                window_id=window.window_id,
                continuity_score=7.0,
                passed=True,
                summary="Healing analysis skipped - no API key"
            )

        prompt = self.ANALYSIS_PROMPT.format(
            story_context=story_context[:500] if story_context else "Not provided",
            scene_id=window.scene_id,
            location=scene_context.get("location", "Unknown"),
            time_of_day=scene_context.get("time_of_day", "Unknown"),
            mood=scene_context.get("mood", ""),
            frame_1_id=window.frames[0].frame_id,
            frame_1_desc=window.frames[0].prompt[:200],
            frame_2_id=window.frames[1].frame_id,
            frame_2_desc=window.frames[1].prompt[:200],
            frame_3_id=window.frames[2].frame_id,
            frame_3_desc=window.frames[2].prompt[:200],
        )

        # Build image list: character refs first, then the 3 frames
        images = []
        if character_refs:
            for ref in character_refs[:2]:
                if ref.exists():
                    images.append(ref)

        for frame in window.frames:
            if frame.image_path.exists():
                images.append(frame.image_path)

        try:
            response = self._call_gemini(prompt, images)
            return self._parse_analysis(response, window.window_id)
        except Exception as e:
            logger.error(f"Window analysis failed: {e}")
            return WindowAnalysis(
                window_id=window.window_id,
                continuity_score=5.0,
                passed=False,
                summary=f"Analysis error: {e}"
            )

    def _call_gemini(self, prompt: str, image_paths: List[Path]) -> str:
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

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
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

    def _parse_analysis(self, response: str, window_id: str) -> WindowAnalysis:
        """Parse analysis response."""
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            issues = []
            for issue_data in data.get("issues", []):
                issues.append(ContinuityIssue(
                    category=issue_data.get("category", "unknown"),
                    severity=issue_data.get("severity", "minor"),
                    affected_frame=issue_data.get("affected_frame", ""),
                    issue=issue_data.get("issue", ""),
                    fix_instruction=issue_data.get("fix_instruction", "")
                ))

            return WindowAnalysis(
                window_id=window_id,
                continuity_score=data.get("continuity_score", 5.0),
                passed=data.get("passed", False),
                issues=issues,
                frame_scores=data.get("frame_scores", {}),
                summary=data.get("summary", "")
            )
        except Exception as e:
            logger.warning(f"Analysis parse error: {e}")
            return WindowAnalysis(
                window_id=window_id,
                continuity_score=5.0,
                passed=False,
                summary=f"Parse error: {e}"
            )


# =============================================================================
# PARALLEL HEALING PIPELINE
# =============================================================================

class ParallelHealingPipeline:
    """
    Runs parallel to frame generation, healing frames in 3-frame windows.

    Usage:
        pipeline = ParallelHealingPipeline(project_path, image_model)

        # Start the healing worker
        healing_task = asyncio.create_task(pipeline.healing_worker())

        # As frames are generated, add them to the queue
        await pipeline.add_frame(generated_frame)
        await pipeline.add_frame(generated_frame_2)
        await pipeline.add_frame(generated_frame_3)  # Triggers first healing window

        # When generation is done, signal completion
        await pipeline.finish()
        await healing_task  # Wait for healing to complete
    """

    TARGET_SCORE = 7.5  # Minimum score to pass without healing
    MAX_HEALING_ATTEMPTS = 2  # Max healing iterations per frame

    def __init__(
        self,
        project_path: Path,
        image_model: ImageModel = ImageModel.SEEDREAM,
        log_callback: Callable[[str], None] = None,
        story_context: str = "",
        world_config: Dict[str, Any] = None
    ):
        self.project_path = Path(project_path)
        self.image_model = image_model
        self.log = log_callback or (lambda msg: logger.info(msg))
        self.story_context = story_context
        self.world_config = world_config or {}

        self.output_dir = self.project_path / "storyboard_output" / "generated"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Archive directory for original frames that get healed
        self.archive_dir = self.project_path / "storyboard_output" / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        self.handler = ImageHandler(project_path=self.project_path)
        self.analyzer = ContinuityAnalysisAgent()

        # Archived frames tracking (for frontend to display as thumbnails)
        self.archived_frames: Dict[str, Path] = {}

        # Queues and state
        self.frame_queue: asyncio.Queue[GeneratedFrame] = asyncio.Queue()
        self.pending_frames: List[GeneratedFrame] = []
        self.healed_frames: Dict[str, GeneratedFrame] = {}
        self.generation_complete = asyncio.Event()

        # Scene tracking
        self.current_scene: Optional[str] = None
        self.scene_frames: Dict[str, List[GeneratedFrame]] = {}

        # Statistics
        self.windows_analyzed = 0
        self.frames_healed = 0
        self.total_healing_time = 0.0

        # Check if model supports editing
        self.supports_editing = image_model in [
            ImageModel.P_IMAGE_EDIT,
            ImageModel.FLUX_2_PRO,
            ImageModel.SEEDREAM
        ]

    async def add_frame(self, frame: GeneratedFrame):
        """Add a newly generated frame to the healing queue."""
        await self.frame_queue.put(frame)

    async def finish(self):
        """Signal that generation is complete."""
        self.generation_complete.set()

    async def healing_worker(self):
        """
        Background worker that processes frames for healing.

        Runs continuously, pulling frames from the queue and triggering
        healing analysis when 3 consecutive frames are available.
        """
        self.log("🔧 [HEALING] Worker started - waiting for frames...")
        self.log(f"   Model: {self.image_model.value} | Edit support: {self.supports_editing}")
        self.log(f"   Target score: {self.TARGET_SCORE}/10 | Max attempts: {self.MAX_HEALING_ATTEMPTS}")

        frames_received = 0

        while True:
            # Check if we should exit
            if self.generation_complete.is_set() and self.frame_queue.empty():
                # Process any remaining frames
                if len(self.pending_frames) >= 2:
                    self.log(f"🔧 [HEALING] Processing {len(self.pending_frames)} remaining frames...")
                    await self._process_final_window()
                break

            try:
                # Get next frame with timeout
                frame = await asyncio.wait_for(
                    self.frame_queue.get(),
                    timeout=1.0
                )

                frames_received += 1
                self.log(f"🔧 [HEALING] Received frame {frame.frame_id} (#{frames_received} in queue, {len(self.pending_frames)+1} pending)")

                # Track by scene
                if frame.scene_id not in self.scene_frames:
                    self.scene_frames[frame.scene_id] = []
                self.scene_frames[frame.scene_id].append(frame)

                # Handle scene change
                if self.current_scene and frame.scene_id != self.current_scene:
                    self.log(f"🔧 [HEALING] Scene change detected: {self.current_scene} → {frame.scene_id}")
                    # Process remaining frames from previous scene
                    if len(self.pending_frames) >= 2:
                        await self._process_final_window()
                    self.pending_frames = []

                self.current_scene = frame.scene_id
                self.pending_frames.append(frame)

                # When we have 3 frames, analyze the window
                if len(self.pending_frames) >= 3:
                    self.log(f"🔧 [HEALING] ═══════════════════════════════════════")
                    self.log(f"🔧 [HEALING] 3 frames ready - triggering analysis!")
                    await self._analyze_and_heal_window()
                else:
                    self.log(f"🔧 [HEALING] Waiting for more frames... ({len(self.pending_frames)}/3)")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Healing worker error: {e}")
                self.log(f"⚠️ [HEALING] Error: {e}")
                continue

        self.log(f"🔧 [HEALING] ═══════════════════════════════════════")
        self.log(f"🔧 [HEALING] Worker complete!")
        self.log(f"   📊 Windows analyzed: {self.windows_analyzed}")
        self.log(f"   🩹 Frames healed: {self.frames_healed}")
        self.log(f"   📁 Frames archived: {len(self.archived_frames)}")
        self.log(f"   ⏱️ Total time: {self.total_healing_time:.1f}s")

    async def _analyze_and_heal_window(self):
        """Analyze current 3-frame window and heal if needed."""
        if len(self.pending_frames) < 3:
            return

        # Take the first 3 frames as a window
        window_frames = self.pending_frames[:3]
        window = HealingWindow(
            frames=window_frames,
            target_frame_idx=1,  # Focus on middle frame
            scene_id=self.current_scene
        )

        self.log(f"🔧 [HEALING] Analyzing window: [{window_frames[0].frame_id}] → [{window_frames[1].frame_id}] → [{window_frames[2].frame_id}]")
        self.log(f"   Target frame (middle): {window_frames[1].frame_id}")

        # Get character refs for this window
        char_refs = self._get_character_refs(window_frames)
        if char_refs:
            self.log(f"   Character refs: {[p.name for p in char_refs]}")

        # Build scene context
        locations = self.world_config.get("locations", [])
        scene_context = {
            "location": locations[0].get("name", "") if locations else "",
            "time_of_day": self.world_config.get("lighting", ""),
            "mood": self.world_config.get("vibe", "")
        }

        # Analyze
        self.log(f"🔧 [HEALING] Sending to Gemini for continuity analysis...")
        start_time = datetime.now()
        analysis = self.analyzer.analyze_window(
            window,
            self.story_context,
            scene_context,
            char_refs
        )
        self.windows_analyzed += 1

        analysis_time = (datetime.now() - start_time).total_seconds()
        self.total_healing_time += analysis_time

        # Verbose result logging
        status_emoji = "✅" if analysis.passed else "🩹"
        self.log(f"{status_emoji} [HEALING] Analysis complete in {analysis_time:.1f}s")
        self.log(f"   Score: {analysis.continuity_score:.1f}/10 | {'PASS' if analysis.passed else 'NEEDS HEALING'}")

        if analysis.summary:
            self.log(f"   Summary: {analysis.summary[:100]}...")

        # Log individual frame scores
        if analysis.frame_scores:
            for fid, score in analysis.frame_scores.items():
                score_emoji = "✓" if score >= self.TARGET_SCORE else "⚠"
                self.log(f"   {score_emoji} {fid}: {score:.1f}/10")

        # Log issues found
        if analysis.issues:
            self.log(f"   Issues found: {len(analysis.issues)}")
            for issue in analysis.issues:
                severity_emoji = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(issue.severity, "⚪")
                self.log(f"   {severity_emoji} [{issue.severity.upper()}] {issue.category}: {issue.issue[:60]}...")

        # Heal if needed
        if not analysis.passed and analysis.issues:
            await self._heal_frames(window, analysis, char_refs)
        elif analysis.passed:
            self.log(f"🔧 [HEALING] No healing needed - continuity is good!")

        # Store results
        for frame in window_frames:
            frame.healing_status = HealingStatus.COMPLETE
            frame.healing_score = analysis.frame_scores.get(frame.frame_id, analysis.continuity_score)
            self.healed_frames[frame.frame_id] = frame

        # Slide the window - remove first frame, keep last 2
        self.pending_frames = self.pending_frames[1:]
        self.log(f"🔧 [HEALING] Window complete. Sliding to next... ({len(self.pending_frames)} frames pending)")

    async def _heal_frames(
        self,
        window: HealingWindow,
        analysis: WindowAnalysis,
        char_refs: List[Path]
    ):
        """Apply healing edits to frames with issues, archiving originals."""
        if not self.supports_editing:
            self.log(f"⚠️ [HEALING] Skipped - {self.image_model.value} doesn't support editing")
            return

        # Group issues by frame
        issues_by_frame: Dict[str, List[ContinuityIssue]] = {}
        for issue in analysis.issues:
            if issue.affected_frame not in issues_by_frame:
                issues_by_frame[issue.affected_frame] = []
            issues_by_frame[issue.affected_frame].append(issue)

        self.log(f"🩹 [HEALING] Healing {len(issues_by_frame)} frame(s)...")

        # Heal each affected frame
        for frame_id, issues in issues_by_frame.items():
            # Find the frame
            target_frame = None
            for f in window.frames:
                if f.frame_id == frame_id:
                    target_frame = f
                    break

            if not target_frame:
                continue

            # Build healing prompt
            critical = [i for i in issues if i.severity == "critical"]
            major = [i for i in issues if i.severity == "major"]
            fixes = critical + major[:2]

            if not fixes:
                continue

            self.log(f"🩹 [HEALING] Healing frame: {frame_id}")
            for fix in fixes:
                self.log(f"   → {fix.fix_instruction[:60]}...")

            heal_prompt = "HEAL THIS FRAME FOR CONTINUITY:\n"
            for fix in fixes:
                heal_prompt += f"- {fix.fix_instruction}\n"

            # Add adjacent frames as context
            heal_prompt += "\nMATCH CONTINUITY WITH: adjacent frames in sequence"
            heal_prompt += "\nPRESERVE: overall composition, character identity, lighting direction"

            # Generate healed version - save to same location as original
            clean_id = frame_id.replace("[", "").replace("]", "")
            original_path = target_frame.image_path
            healed_path = self.output_dir / f"{clean_id}.png"  # Same name as original

            # Use original + adjacent frames as references
            refs = [target_frame.image_path]
            for f in window.frames:
                if f.frame_id != frame_id and f.image_path.exists():
                    refs.append(f.image_path)
            if char_refs:
                refs.extend(char_refs[:1])

            try:
                # First, archive the original image
                if original_path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive_name = f"{clean_id}_v{timestamp}.png"
                    archive_path = self.archive_dir / archive_name

                    # Move original to archive
                    import shutil
                    shutil.copy2(original_path, archive_path)
                    self.archived_frames[frame_id] = archive_path
                    self.log(f"   📁 Archived original: {archive_name}")

                # Generate healed version
                self.log(f"   🎨 Generating healed version...")
                result = await self.handler.generate(ImageRequest(
                    prompt=heal_prompt,
                    model=self.image_model,
                    reference_images=refs[:4],
                    output_path=healed_path,
                    aspect_ratio="16:9",
                    prefix_type="edit",
                    add_clean_suffix=True
                ))

                if result.success:
                    target_frame.healed_path = healed_path
                    target_frame.healing_notes = f"Healed: {', '.join(f.issue[:30] for f in fixes)}"
                    self.frames_healed += 1
                    self.log(f"   ✅ Healed successfully → {healed_path.name}")
                else:
                    self.log(f"   ❌ Healing failed: {result.error}")

            except Exception as e:
                logger.error(f"Healing error for {frame_id}: {e}")
                self.log(f"   ❌ Error: {e}")

    async def _process_final_window(self):
        """Process remaining frames at end of scene/generation."""
        if len(self.pending_frames) < 2:
            return

        # For 2 remaining frames, analyze them as a pair
        # Pad with the last frame repeated for context
        window_frames = self.pending_frames[-2:]
        if len(window_frames) == 2:
            window_frames = window_frames + [window_frames[-1]]  # Repeat last

        window = HealingWindow(
            frames=window_frames,
            target_frame_idx=0,  # Focus on first of remaining
            scene_id=self.current_scene
        )

        self.log(f"[HEALING] Final window: {self.pending_frames[0].frame_id}-{self.pending_frames[-1].frame_id}")

        char_refs = self._get_character_refs(window_frames)
        scene_context = {
            "location": "",
            "time_of_day": self.world_config.get("lighting", ""),
            "mood": self.world_config.get("vibe", "")
        }

        analysis = self.analyzer.analyze_window(
            window,
            self.story_context,
            scene_context,
            char_refs
        )
        self.windows_analyzed += 1

        self.log(f"  Score: {analysis.continuity_score:.1f}/10")

        for frame in self.pending_frames:
            frame.healing_status = HealingStatus.COMPLETE
            frame.healing_score = analysis.frame_scores.get(frame.frame_id, analysis.continuity_score)
            self.healed_frames[frame.frame_id] = frame

    def _get_character_refs(self, frames: List[GeneratedFrame]) -> List[Path]:
        """Get character reference images for the frames."""
        refs = []
        seen_chars = set()

        for frame in frames:
            for char in frame.characters:
                if char in seen_chars:
                    continue
                seen_chars.add(char)

                char_dir = self.project_path / "references" / char
                if char_dir.exists():
                    key_file = char_dir / ".key"
                    if key_file.exists():
                        key_name = key_file.read_text().strip()
                        key_path = char_dir / key_name
                        if key_path.exists():
                            refs.append(key_path)

        return refs[:2]  # Max 2 character refs

    def get_statistics(self) -> Dict[str, Any]:
        """Get healing statistics."""
        return {
            "windows_analyzed": self.windows_analyzed,
            "frames_healed": self.frames_healed,
            "frames_archived": len(self.archived_frames),
            "total_healing_time": self.total_healing_time,
            "avg_time_per_window": self.total_healing_time / max(1, self.windows_analyzed),
            "healed_frame_ids": list(self.healed_frames.keys()),
            "archived_frames": {fid: str(path) for fid, path in self.archived_frames.items()}
        }

    def get_archived_frames(self) -> List[Dict[str, str]]:
        """Get list of archived frames for frontend display."""
        archived = []
        for frame_id, path in self.archived_frames.items():
            if path.exists():
                archived.append({
                    "frame_id": frame_id,
                    "path": str(path),
                    "filename": path.name
                })
        return archived


# =============================================================================
# INTEGRATION HELPER
# =============================================================================

def create_generated_frame(
    frame_data: Dict[str, Any],
    image_path: Path,
    project_path: Path
) -> GeneratedFrame:
    """Helper to create a GeneratedFrame from frame data dict."""
    frame_id = frame_data.get("frame_id", "unknown")
    scene_id = str(frame_data.get("_scene_num", frame_id.split(".")[0] if "." in frame_id else "1"))

    tags = frame_data.get("tags", {})
    characters = tags.get("characters", []) if isinstance(tags, dict) else []
    locations = tags.get("locations", []) if isinstance(tags, dict) else []

    # Get character refs
    char_refs = []
    refs_dir = project_path / "references"
    for char in characters:
        char_dir = refs_dir / char
        if char_dir.exists():
            key_file = char_dir / ".key"
            if key_file.exists():
                key_name = key_file.read_text().strip()
                key_path = char_dir / key_name
                if key_path.exists():
                    char_refs.append(key_path)

    return GeneratedFrame(
        frame_id=frame_id,
        scene_id=scene_id,
        image_path=image_path,
        prompt=frame_data.get("prompt", ""),
        visual_description=frame_data.get("visual_description", ""),
        camera_notation=frame_data.get("camera_notation", ""),
        characters=characters,
        locations=locations,
        character_refs=char_refs
    )


# =============================================================================
# VERSION CONTROL SYSTEM
# =============================================================================

@dataclass
class FrameVersion:
    """A single version of a frame."""
    version_id: str  # Unique ID (timestamp-based)
    frame_id: str
    image_path: Path
    created_at: datetime
    iteration: int  # Which healing iteration (1, 2, 3...)
    is_compressed: bool = False
    compressed_path: Optional[Path] = None
    healing_notes: str = ""
    continuity_score: float = 0.0
    file_size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "frame_id": self.frame_id,
            "image_path": str(self.image_path),
            "created_at": self.created_at.isoformat(),
            "iteration": self.iteration,
            "is_compressed": self.is_compressed,
            "compressed_path": str(self.compressed_path) if self.compressed_path else None,
            "healing_notes": self.healing_notes,
            "continuity_score": self.continuity_score,
            "file_size_bytes": self.file_size_bytes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FrameVersion":
        return cls(
            version_id=data["version_id"],
            frame_id=data["frame_id"],
            image_path=Path(data["image_path"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            iteration=data["iteration"],
            is_compressed=data.get("is_compressed", False),
            compressed_path=Path(data["compressed_path"]) if data.get("compressed_path") else None,
            healing_notes=data.get("healing_notes", ""),
            continuity_score=data.get("continuity_score", 0.0),
            file_size_bytes=data.get("file_size_bytes", 0)
        )


@dataclass
class Checkpoint:
    """A checkpoint representing a specific state of all frames."""
    checkpoint_id: str
    name: str
    created_at: datetime
    description: str
    frame_versions: Dict[str, str]  # frame_id -> version_id
    total_frames: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "frame_versions": self.frame_versions,
            "total_frames": self.total_frames
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        return cls(
            checkpoint_id=data["checkpoint_id"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            description=data["description"],
            frame_versions=data["frame_versions"],
            total_frames=data["total_frames"]
        )


class FrameVersionManager:
    """
    Manages version control for storyboard frames.

    Features:
    - Track all versions of each frame
    - Create/restore checkpoints
    - Auto-compress old archives (>3 iterations)
    - Proxy thumbnails for compressed archives
    """

    COMPRESS_AFTER_ITERATIONS = 3
    THUMBNAIL_SIZE = (320, 180)  # 16:9 thumbnail
    COMPRESSION_QUALITY = 60  # JPEG quality for old archives

    def __init__(self, project_path: Path, log_callback: Optional[Callable] = None):
        self.project_path = project_path
        self.log = log_callback or (lambda msg: logger.info(msg))

        # Directories
        self.archive_dir = project_path / "storyboard_output" / "archive"
        self.generated_dir = project_path / "storyboard_output" / "generated"
        self.compressed_dir = project_path / "storyboard_output" / "archive" / "compressed"
        self.thumbnails_dir = project_path / "storyboard_output" / "archive" / "thumbnails"
        self.version_db_path = project_path / "storyboard_output" / "version_history.json"

        # Ensure directories exist
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.compressed_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

        # Load or initialize version database
        self.versions: Dict[str, List[FrameVersion]] = {}  # frame_id -> list of versions
        self.checkpoints: List[Checkpoint] = []
        self._load_database()

    def _load_database(self):
        """Load version history from disk."""
        if self.version_db_path.exists():
            try:
                data = json.loads(self.version_db_path.read_text(encoding="utf-8"))

                # Load versions
                for frame_id, version_list in data.get("versions", {}).items():
                    self.versions[frame_id] = [
                        FrameVersion.from_dict(v) for v in version_list
                    ]

                # Load checkpoints
                self.checkpoints = [
                    Checkpoint.from_dict(cp) for cp in data.get("checkpoints", [])
                ]

                self.log(f"📂 [VERSION] Loaded {len(self.versions)} frames, {len(self.checkpoints)} checkpoints")
            except Exception as e:
                logger.error(f"Failed to load version database: {e}")
                self.versions = {}
                self.checkpoints = []
        else:
            # Scan existing archive for versions
            self._scan_existing_archives()

    def _scan_existing_archives(self):
        """Scan archive directory to build initial version database."""
        if not self.archive_dir.exists():
            return

        self.log(f"📂 [VERSION] Scanning existing archives...")

        for archive_file in self.archive_dir.glob("*.png"):
            # Parse filename: {frame_id}_v{timestamp}.png
            name = archive_file.stem
            if "_v" not in name:
                continue

            parts = name.rsplit("_v", 1)
            if len(parts) != 2:
                continue

            frame_id = parts[0]
            timestamp_str = parts[1]

            try:
                created_at = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                created_at = datetime.fromtimestamp(archive_file.stat().st_mtime)

            if frame_id not in self.versions:
                self.versions[frame_id] = []

            # Calculate iteration number
            iteration = len(self.versions[frame_id]) + 1

            version = FrameVersion(
                version_id=f"{frame_id}_{timestamp_str}",
                frame_id=frame_id,
                image_path=archive_file,
                created_at=created_at,
                iteration=iteration,
                file_size_bytes=archive_file.stat().st_size if archive_file.exists() else 0
            )

            self.versions[frame_id].append(version)

        # Sort versions by date
        for frame_id in self.versions:
            self.versions[frame_id].sort(key=lambda v: v.created_at)
            # Re-number iterations
            for i, v in enumerate(self.versions[frame_id]):
                v.iteration = i + 1

        self._save_database()
        self.log(f"📂 [VERSION] Found {sum(len(v) for v in self.versions.values())} archived versions")

    def _save_database(self):
        """Save version history to disk."""
        data = {
            "versions": {
                fid: [v.to_dict() for v in versions]
                for fid, versions in self.versions.items()
            },
            "checkpoints": [cp.to_dict() for cp in self.checkpoints]
        }

        self.version_db_path.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8"
        )

    def add_version(
        self,
        frame_id: str,
        image_path: Path,
        healing_notes: str = "",
        continuity_score: float = 0.0
    ) -> FrameVersion:
        """
        Add a new version of a frame to the archive.

        Returns the created FrameVersion.
        """
        if frame_id not in self.versions:
            self.versions[frame_id] = []

        iteration = len(self.versions[frame_id]) + 1
        timestamp = datetime.now()
        version_id = f"{frame_id}_v{timestamp.strftime('%Y%m%d_%H%M%S')}"

        # Archive the image
        archive_name = f"{frame_id.replace('[', '').replace(']', '')}_v{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
        archive_path = self.archive_dir / archive_name

        import shutil
        if image_path.exists():
            shutil.copy2(image_path, archive_path)

        version = FrameVersion(
            version_id=version_id,
            frame_id=frame_id,
            image_path=archive_path,
            created_at=timestamp,
            iteration=iteration,
            healing_notes=healing_notes,
            continuity_score=continuity_score,
            file_size_bytes=archive_path.stat().st_size if archive_path.exists() else 0
        )

        self.versions[frame_id].append(version)
        self.log(f"📂 [VERSION] Added v{iteration} for {frame_id}")

        # Check if we need to compress old versions
        self._compress_old_versions(frame_id)

        self._save_database()
        return version

    def _compress_old_versions(self, frame_id: str):
        """Compress versions older than COMPRESS_AFTER_ITERATIONS."""
        versions = self.versions.get(frame_id, [])
        if len(versions) <= self.COMPRESS_AFTER_ITERATIONS:
            return

        # Compress versions beyond the threshold
        versions_to_compress = versions[:-self.COMPRESS_AFTER_ITERATIONS]

        try:
            from PIL import Image
        except ImportError:
            self.log("⚠️ [VERSION] PIL not available for compression")
            return

        for version in versions_to_compress:
            if version.is_compressed:
                continue

            if not version.image_path.exists():
                continue

            try:
                # Create compressed version
                compressed_name = f"{version.version_id}_compressed.jpg"
                compressed_path = self.compressed_dir / compressed_name

                # Create thumbnail
                thumbnail_name = f"{version.version_id}_thumb.jpg"
                thumbnail_path = self.thumbnails_dir / thumbnail_name

                with Image.open(version.image_path) as img:
                    # Convert to RGB if necessary
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')

                    # Save compressed version
                    img.save(compressed_path, "JPEG", quality=self.COMPRESSION_QUALITY)

                    # Create thumbnail
                    img.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                    img.save(thumbnail_path, "JPEG", quality=85)

                # Calculate savings
                original_size = version.file_size_bytes
                compressed_size = compressed_path.stat().st_size
                savings = ((original_size - compressed_size) / original_size * 100) if original_size > 0 else 0

                # Remove original, keep compressed
                version.image_path.unlink()

                # Update version
                version.is_compressed = True
                version.compressed_path = compressed_path
                version.image_path = thumbnail_path  # Point to thumbnail for quick access

                self.log(f"📦 [VERSION] Compressed {version.version_id} ({savings:.0f}% saved)")

            except Exception as e:
                logger.error(f"Failed to compress {version.version_id}: {e}")

    def get_versions(self, frame_id: str) -> List[FrameVersion]:
        """Get all versions of a frame, sorted by iteration (newest first)."""
        versions = self.versions.get(frame_id, [])
        return sorted(versions, key=lambda v: v.iteration, reverse=True)

    def get_all_frame_versions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get version info for all frames."""
        return {
            frame_id: [v.to_dict() for v in self.get_versions(frame_id)]
            for frame_id in self.versions
        }

    def restore_version(self, frame_id: str, version_id: str) -> bool:
        """
        Restore a specific version of a frame.

        Copies the archived version back to the generated directory.
        """
        versions = self.versions.get(frame_id, [])
        target_version = None

        for v in versions:
            if v.version_id == version_id:
                target_version = v
                break

        if not target_version:
            self.log(f"❌ [VERSION] Version {version_id} not found")
            return False

        # Get source path (compressed or original)
        if target_version.is_compressed and target_version.compressed_path:
            source_path = target_version.compressed_path
        else:
            source_path = target_version.image_path

        if not source_path.exists():
            self.log(f"❌ [VERSION] Source file not found: {source_path}")
            return False

        # Destination is the current generated frame
        clean_id = frame_id.replace("[", "").replace("]", "")
        dest_path = self.generated_dir / f"{clean_id}.png"

        # Archive current version before overwriting
        if dest_path.exists():
            self.add_version(frame_id, dest_path, healing_notes="Pre-restore backup")

        import shutil
        try:
            # If compressed (JPEG), convert back to PNG
            if target_version.is_compressed:
                from PIL import Image
                with Image.open(source_path) as img:
                    img.save(dest_path, "PNG")
            else:
                shutil.copy2(source_path, dest_path)

            self.log(f"✅ [VERSION] Restored {frame_id} to version {target_version.iteration}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore version: {e}")
            self.log(f"❌ [VERSION] Restore failed: {e}")
            return False

    def create_checkpoint(self, name: str, description: str = "") -> Checkpoint:
        """
        Create a checkpoint of the current state of all frames.

        A checkpoint records which version each frame is at.
        """
        frame_versions = {}

        # Record current state
        for frame_id in self.versions:
            versions = self.get_versions(frame_id)
            if versions:
                # Latest version is the current state
                frame_versions[frame_id] = versions[0].version_id

        # Also check for frames that haven't been healed (no archive)
        for img_file in self.generated_dir.glob("*.png"):
            frame_id = img_file.stem
            if frame_id not in frame_versions:
                # Create a version entry for this frame
                version = self.add_version(frame_id, img_file, healing_notes="Checkpoint snapshot")
                frame_versions[frame_id] = version.version_id

        checkpoint = Checkpoint(
            checkpoint_id=f"cp_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name=name,
            created_at=datetime.now(),
            description=description,
            frame_versions=frame_versions,
            total_frames=len(frame_versions)
        )

        self.checkpoints.append(checkpoint)
        self._save_database()

        self.log(f"✅ [VERSION] Created checkpoint '{name}' with {checkpoint.total_frames} frames")
        return checkpoint

    def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Restore all frames to a specific checkpoint state.
        """
        target_checkpoint = None
        for cp in self.checkpoints:
            if cp.checkpoint_id == checkpoint_id:
                target_checkpoint = cp
                break

        if not target_checkpoint:
            self.log(f"❌ [VERSION] Checkpoint {checkpoint_id} not found")
            return False

        self.log(f"🔄 [VERSION] Restoring checkpoint '{target_checkpoint.name}'...")

        restored = 0
        failed = 0

        for frame_id, version_id in target_checkpoint.frame_versions.items():
            if self.restore_version(frame_id, version_id):
                restored += 1
            else:
                failed += 1

        self.log(f"✅ [VERSION] Restored {restored} frames, {failed} failed")
        return failed == 0

    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """Get all checkpoints, sorted by date (newest first)."""
        sorted_checkpoints = sorted(self.checkpoints, key=lambda cp: cp.created_at, reverse=True)
        return [cp.to_dict() for cp in sorted_checkpoints]

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint (doesn't delete the actual files)."""
        for i, cp in enumerate(self.checkpoints):
            if cp.checkpoint_id == checkpoint_id:
                del self.checkpoints[i]
                self._save_database()
                self.log(f"🗑️ [VERSION] Deleted checkpoint '{cp.name}'")
                return True
        return False

    def get_thumbnail_path(self, version_id: str) -> Optional[Path]:
        """Get thumbnail path for a version (for compressed archives)."""
        thumbnail_path = self.thumbnails_dir / f"{version_id}_thumb.jpg"
        if thumbnail_path.exists():
            return thumbnail_path
        return None

    def get_full_image_path(self, version_id: str) -> Optional[Path]:
        """Get the best available image path for a version."""
        # Find the version
        for frame_id, versions in self.versions.items():
            for v in versions:
                if v.version_id == version_id:
                    if v.is_compressed and v.compressed_path and v.compressed_path.exists():
                        return v.compressed_path
                    elif v.image_path.exists():
                        return v.image_path
        return None

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics for version control."""
        total_versions = sum(len(v) for v in self.versions.values())
        compressed_count = sum(
            1 for versions in self.versions.values()
            for v in versions if v.is_compressed
        )

        # Calculate storage
        archive_size = sum(f.stat().st_size for f in self.archive_dir.glob("*.png") if f.exists())
        compressed_size = sum(f.stat().st_size for f in self.compressed_dir.glob("*.jpg") if f.exists())
        thumbnail_size = sum(f.stat().st_size for f in self.thumbnails_dir.glob("*.jpg") if f.exists())

        return {
            "total_frames_tracked": len(self.versions),
            "total_versions": total_versions,
            "compressed_versions": compressed_count,
            "uncompressed_versions": total_versions - compressed_count,
            "total_checkpoints": len(self.checkpoints),
            "storage": {
                "archive_mb": archive_size / (1024 * 1024),
                "compressed_mb": compressed_size / (1024 * 1024),
                "thumbnails_mb": thumbnail_size / (1024 * 1024),
                "total_mb": (archive_size + compressed_size + thumbnail_size) / (1024 * 1024)
            }
        }
