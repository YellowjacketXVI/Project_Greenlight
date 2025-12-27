"""
Directing Pipeline - Visual Script Generation Engine

Transforms Script into Visual_Script with frame notations, camera placements,
and visual prompts. Uses parallel scene processing for efficiency.

## Notation Validation Note

IMPORTANT: Notation validation (scene.frame.camera format, tag formats) is handled
by AnchorAgent in the Writer Pipeline's QA phase (QualityOrchestrator Phase 4).
The Director Pipeline assumes the input script has already been validated.

If notation issues are found in Director output, they should be traced back to
the Writer Pipeline's QA phase. See NOTATION_STANDARDS.md for details.

## Scene.Frame.Camera Notation System

The unified notation format is: `{scene}.{frame}.{camera}`

| Component | Position | Format | Examples |
|-----------|----------|--------|----------|
| Scene     | X.x.x    | Integer | 1.x.x, 2.x.x, 8.x.x |
| Frame     | x.X.x    | Integer | x.1.x, x.2.x, x.15.x |
| Camera    | x.x.X    | Letter  | x.x.cA, x.x.cB, x.x.cC |

Full ID Examples:
- 1.1.cA = Scene 1, Frame 1, Camera A
- 1.2.cB = Scene 1, Frame 2, Camera B
- 2.3.cC = Scene 2, Frame 3, Camera C

Flow:
1. Scene Chunking - Split Script into individual scenes
2. Per-Scene Processing (Parallel):
   - Frame Count Consensus (3 judges, best of 3)
   - Frame Point Determination (2 iterations, collaboration)
   - Frame Marking with scene.frame.camera notation
   - Frame Prompt Insertion (250 word cap per prompt)
3. Camera/Placement Insertion (Parallel per frame)

Output: Visual_Script with regex-targetable frame notations
"""

import asyncio
import re
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Tuple
from statistics import median

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from greenlight.pipelines.base_pipeline import BasePipeline, PipelineStep, PipelineResult
from greenlight.config.notation_patterns import (
    REGEX_PATTERNS, FRAME_NOTATION_MARKERS,
    extract_frame_id, extract_frame_chunks
)
from greenlight.agents.prompts import AgentPromptLibrary

logger = get_logger("pipelines.directing")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DirectingInput:
    """Input for Directing Pipeline."""
    script: str  # Full story script from Writer Pipeline (scripts/script.md)
    world_config: Dict[str, Any]  # World bible data
    visual_style: str = ""  # From pitch
    style_notes: str = ""
    media_type: str = "standard"


@dataclass
class FrameBoundary:
    """Defines where a frame starts and ends."""
    frame_number: int
    start_text: str  # Quote from text where frame begins
    end_text: str  # Quote from text where frame ends
    captures: str  # Description of what frame shows


@dataclass
class FrameChunk:
    """A processed frame chunk with all notations.

    Uses scene.frame.camera notation:
    - frame_id: "1.2" (scene.frame)
    - camera_id: "1.2.cA" (scene.frame.camera)

    Two-tier description system:
    - visual_description: Rich cinematic storytelling for the visual script
      (emotional context, narrative intent, lighting motivation, atmosphere)
    - prompt: Concise image generation prompt (what the camera literally sees)
    """
    frame_id: str  # e.g., "1.2" (scene.frame format)
    scene_number: int
    frame_number: int
    original_text: str
    camera_notation: str = ""  # e.g., "[1.2.cA] (Wide)"
    position_notation: str = ""
    lighting_notation: str = ""
    # Rich visual storytelling description for visual_script (emotional, narrative context)
    visual_description: str = ""
    # Concise prompt for image generation (50 words max, what camera sees)
    prompt: str = ""
    cameras: List[str] = field(default_factory=list)  # List of camera IDs: ["1.2.cA", "1.2.cB"]
    # Extracted tags for reference image lookup
    tags: Dict[str, List[str]] = field(default_factory=dict)  # {"characters": [], "locations": [], "props": []}
    # Location direction for directional reference image selection (NORTH, EAST, SOUTH, WEST)
    location_direction: str = "NORTH"
    # Video motion prompt for AI video generation (describes camera and subject movement)
    motion_prompt: str = ""
    # Emotional beat for this frame
    beat: str = ""

    @property
    def primary_camera_id(self) -> str:
        """Get the primary camera ID (first camera, usually cA)."""
        if self.cameras:
            return self.cameras[0]
        return f"{self.scene_number}.{self.frame_number}.cA"

    def extract_tags_from_prompt(self, all_tags: List[str]) -> None:
        """Extract tags from prompt text and categorize them.

        Args:
            all_tags: List of all valid tags from world_config (e.g., ["CHAR_PROTAGONIST", "LOC_MAIN_STREET"])
        """
        self.tags = {"characters": [], "locations": [], "props": []}

        # Combine prompt and position notation for tag extraction
        text_to_search = f"{self.prompt} {self.position_notation}"

        for tag in all_tags:
            # Check for tag in brackets [TAG] or as CHAR_TAG, LOC_TAG, PROP_TAG
            if f"[{tag}]" in text_to_search or tag in text_to_search:
                if tag.startswith("CHAR_"):
                    if tag not in self.tags["characters"]:
                        self.tags["characters"].append(tag)
                elif tag.startswith("LOC_"):
                    if tag not in self.tags["locations"]:
                        self.tags["locations"].append(tag)
                elif tag.startswith("PROP_"):
                    if tag not in self.tags["props"]:
                        self.tags["props"].append(tag)


@dataclass
class ProcessedScene:
    """A scene after frame processing."""
    scene_number: int
    original_text: str
    frame_count: int
    frame_boundaries: List[FrameBoundary] = field(default_factory=list)
    marked_text: str = ""
    frames: List[FrameChunk] = field(default_factory=list)


@dataclass
class VisualScriptOutput:
    """Output from Directing Pipeline."""
    visual_script: str  # Complete marked-up script
    scenes: List[ProcessedScene] = field(default_factory=list)
    total_frames: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the visual script output to a dictionary.

        The frame_id uses full scene.frame.camera notation (e.g., "1.2.cA")
        for compatibility with the storyboard pipeline.

        Two-tier description system:
        - visual_description: Rich cinematic storytelling (for visual script reading)
        - prompt: Concise image generation prompt (for AI image generators)
        """
        return {
            "visual_script": self.visual_script,
            "total_frames": self.total_frames,
            "total_scenes": len(self.scenes),
            "metadata": self.metadata,
            "scenes": [
                {
                    "scene_number": scene.scene_number,
                    "frame_count": scene.frame_count,
                    "frames": [
                        {
                            # Use primary_camera_id for full scene.frame.camera notation (e.g., "1.2.cA")
                            "frame_id": frame.primary_camera_id,
                            "scene_number": frame.scene_number,
                            "frame_number": frame.frame_number,
                            # Also include all cameras for multi-camera frames
                            "cameras": frame.cameras if frame.cameras else [frame.primary_camera_id],
                            "camera_notation": frame.camera_notation,
                            "position_notation": frame.position_notation,
                            "lighting_notation": frame.lighting_notation,
                            # Rich visual storytelling for visual script
                            "visual_description": frame.visual_description if frame.visual_description else "",
                            # Concise prompt for image generation
                            "prompt": frame.prompt,
                            # Emotional beat
                            "beat": frame.beat if frame.beat else "",
                            "tags": frame.tags if frame.tags else {"characters": [], "locations": [], "props": []},
                            # Location direction for directional reference image selection
                            "location_direction": frame.location_direction if frame.location_direction else "NORTH",
                            # Video motion prompt for AI video generation
                            "motion_prompt": frame.motion_prompt if frame.motion_prompt else "",
                        }
                        for frame in scene.frames
                    ]
                }
                for scene in self.scenes
            ]
        }

    def to_markdown(self) -> str:
        """Convert the visual script output to markdown format."""
        lines = []
        lines.append("# Visual Script")
        lines.append("")
        lines.append(f"**Total Scenes:** {len(self.scenes)}")
        lines.append(f"**Total Frames:** {self.total_frames}")
        lines.append("")

        # Add each scene
        for scene in self.scenes:
            lines.append(f"## Scene {scene.scene_number}")
            lines.append("")

            # Add frames using scene.frame.camera notation
            for frame in scene.frames:
                # Use primary camera ID in scene.frame.camera format (e.g., "3.1.cA")
                camera_id = frame.primary_camera_id

                # Extract shot type from camera_notation if available
                shot_type = "Frame"
                if frame.camera_notation:
                    import re
                    shot_match = re.search(r'\[CAM:\s*([^,\]]+)', frame.camera_notation)
                    if shot_match:
                        shot_type = shot_match.group(1).strip()

                lines.append(f"### [{camera_id}] ({shot_type})")
                lines.append("")
                if frame.camera_notation:
                    lines.append(f"**Camera:** {frame.camera_notation}")
                if frame.position_notation:
                    lines.append(f"**Position:** {frame.position_notation}")
                if frame.lighting_notation:
                    lines.append(f"**Lighting:** {frame.lighting_notation}")
                if frame.prompt:
                    lines.append("")
                    lines.append(frame.prompt)
                lines.append("")

        # If no scenes but we have visual_script, just return that
        if not self.scenes and self.visual_script:
            return self.visual_script

        return "\n".join(lines)


# =============================================================================
# DIRECTING PIPELINE
# =============================================================================

class DirectingPipeline(BasePipeline[DirectingInput, VisualScriptOutput]):
    """
    Directing Pipeline - Transforms Script into Visual_Script.

    Uses parallel processing for scenes and frames.
    """

    def __init__(self, llm_caller: Callable = None):
        self.llm_caller = llm_caller
        super().__init__(name="DirectingPipeline")

    def _define_steps(self) -> None:
        """Define the pipeline steps."""
        self._steps = [
            PipelineStep(name="chunk_scenes", description="Split script into scenes"),
            PipelineStep(name="process_scenes", description="Process scenes in parallel"),
            PipelineStep(name="add_notations", description="Add camera/placement notations"),
            PipelineStep(name="assemble_output", description="Compile Visual_Script"),
            PipelineStep(name="validate_frames", description="Validate and refine frames"),
        ]
    
    async def _execute_step(
        self,
        step: PipelineStep,
        input_data: Any,
        context: Dict[str, Any]
    ) -> Any:
        """Execute a pipeline step."""
        handlers = {
            "chunk_scenes": self._chunk_scenes,
            "process_scenes": self._process_scenes_parallel,
            "add_notations": self._add_notations_parallel,
            "assemble_output": self._assemble_visual_script,
            "validate_frames": self._validate_frames,
        }
        handler = handlers.get(step.name)
        if handler:
            return await handler(input_data, context)
        return input_data
    
    # =========================================================================
    # STEP 1: SCENE CHUNKING
    # =========================================================================
    
    async def _chunk_scenes(
        self,
        input_data: DirectingInput,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Split Script into individual scenes.

        SCENE-ONLY ARCHITECTURE:
        - Primary format (script.md): ## Scene X: (continuous prose)
        - No beat markers - scenes contain continuous prose
        - Director creates frames from scenes using scene.frame.camera notation

        Handles multiple script formats:
        1. Primary format (script.md): ## Scene X: Title
        2. Legacy format: --- SCENE X --- or SCENE X:
        """
        logger.info("Step 1: Chunking script into scenes...")

        script = input_data.script
        scenes = []

        # Try Format 1: Writer output format (## Scene X: Title)
        # This is the primary format from script.md (scene-only, no beats)
        scene_pattern_new = r'##\s*Scene\s+(\d+):'
        new_matches = list(re.finditer(scene_pattern_new, script, flags=re.IGNORECASE))

        if new_matches:
            logger.info(f"Detected scene-only format (## Scene X:) with {len(new_matches)} scenes")
            for i, match in enumerate(new_matches):
                scene_num = int(match.group(1))
                start_pos = match.start()
                # End at next scene or end of script
                end_pos = new_matches[i + 1].start() if i + 1 < len(new_matches) else len(script)
                scene_text = script[start_pos:end_pos].strip()
                scenes.append({
                    "scene_number": scene_num,
                    "text": scene_text
                })

        # Try Format 2: Legacy format (--- SCENE X --- or SCENE X:)
        if not scenes:
            legacy_pattern = r'(?:---\s*SCENE\s+(\d+)\s*---|SCENE\s+(\d+):)'
            parts = re.split(legacy_pattern, script, flags=re.IGNORECASE)

            current_scene_num = 0
            for i, part in enumerate(parts):
                if part is None:
                    continue
                if part.isdigit():
                    current_scene_num = int(part)
                elif part.strip() and current_scene_num > 0:
                    scenes.append({
                        "scene_number": current_scene_num,
                        "text": part.strip()
                    })

            if scenes:
                logger.info(f"Detected legacy format (--- SCENE X ---) with {len(scenes)} scenes")

        # Fallback: treat entire script as one scene
        if not scenes:
            logger.warning("No scene markers found, treating entire script as one scene")
            scenes = [{"scene_number": 1, "text": script.strip()}]

        logger.info(f"Found {len(scenes)} scenes total")

        return {
            "input": input_data,
            "scenes": scenes,
            "world_config": input_data.world_config,
            "visual_style": input_data.visual_style,
            "media_type": input_data.media_type,
        }

    # =========================================================================
    # STEP 2: PARALLEL SCENE PROCESSING
    # =========================================================================

    async def _process_scenes_parallel(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process all scenes in parallel."""
        logger.info("Step 2: Processing scenes in parallel...")

        scenes = data["scenes"]

        # Process all scenes in parallel
        tasks = [
            self._process_single_scene(scene, data)
            for scene in scenes
        ]

        processed_scenes = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any failures
        valid_scenes = []
        for i, result in enumerate(processed_scenes):
            if isinstance(result, Exception):
                logger.error(f"Scene {i+1} processing failed: {result}")
                # Create minimal processed scene
                valid_scenes.append(ProcessedScene(
                    scene_number=scenes[i]["scene_number"],
                    original_text=scenes[i]["text"],
                    frame_count=1,
                    marked_text=scenes[i]["text"]
                ))
            else:
                valid_scenes.append(result)

        data["processed_scenes"] = valid_scenes
        logger.info(f"Processed {len(valid_scenes)} scenes")

        return data

    async def _process_single_scene(
        self,
        scene: Dict[str, Any],
        data: Dict[str, Any]
    ) -> ProcessedScene:
        """Process a single scene through frame pipeline."""
        scene_num = scene["scene_number"]
        scene_text = scene["text"]

        # 2a: Frame Count Consensus (3 judges)
        frame_count = await self._frame_count_consensus(scene_text, scene_num, data)

        # 2b: Frame Point Determination (2 iterations)
        frame_boundaries = await self._determine_frame_points(
            scene_text, frame_count, scene_num
        )

        # 2c: Frame Marking
        marked_text = await self._mark_frames(
            scene_text, frame_boundaries, scene_num
        )

        # 2d: Frame Prompt Insertion
        frames = await self._insert_frame_prompts(
            marked_text, frame_boundaries, scene_num, data
        )

        return ProcessedScene(
            scene_number=scene_num,
            original_text=scene_text,
            frame_count=frame_count,
            frame_boundaries=frame_boundaries,
            marked_text=marked_text,
            frames=frames
        )

    async def _frame_count_consensus(
        self,
        scene_text: str,
        scene_num: int,
        data: Dict[str, Any]
    ) -> int:
        """Get frame count via KEY STORY BEAT analysis.

        Focuses on essential narrative moments that require distinct images.
        Emotional nuances and micro-expressions are handled by video, not stills.

        A frame should capture:
        - Location/setting establishment (1 per location change)
        - Key character actions (physical movements that change the scene)
        - Important story revelations or turning points
        - Significant prop interactions

        NOT separate frames:
        - Emotional reactions (video handles facial expressions)
        - POV/reaction shot pairs (combine into single frame)
        - Atmospheric details (include in establishing shots)
        - Multiple angles of same moment (use single best angle)
        """
        prompt = f"""Analyze this scene to determine the MINIMUM frames needed for storyboarding.

SCENE:
{scene_text}

SCENE NUMBER: {scene_num}
MEDIA TYPE: {data.get('media_type', 'standard')}

## STORYBOARD FRAME PHILOSOPHY

You are creating a STORYBOARD, not a shot list. A storyboard captures KEY STORY BEATS only.
Emotional nuances, reaction shots, and micro-expressions are handled by AI VIDEO generation later.

## WHAT REQUIRES A SEPARATE FRAME

| Frame Type | When to Use | Example |
|------------|-------------|---------|
| ESTABLISHING | New location or significant time change | "The brothel at dawn" |
| ACTION | Character performs key physical action | "She opens the letter" |
| REVELATION | Story-changing moment or discovery | "He sees the jade pendant" |
| INTERACTION | Two+ characters in meaningful exchange | "They sit across the table" |
| TRANSITION | Major scene shift within same location | "Later that evening..." |
| REACTION | Character reacts to something shown in adjacent frame | "Her face falls upon reading" |

## REACTION SHOTS - SPECIAL RULE

Reaction shots are ONLY valid as part of shot/reverse-shot sequences:
- Frame N: Show what triggers the reaction (letter content, another character's action, a discovery)
- Frame N+1: Show the character's reaction

A reaction frame MUST be paired with the trigger frame. Never include a standalone reaction.
Example valid sequence: [Mei reads letter] → [Mei's shocked expression]
Example INVALID: [Mei looks shocked] (without showing what she's reacting to)

## WHAT DOES NOT NEED A SEPARATE FRAME

- Standalone emotional reactions (must be paired with trigger)
- POV shots (include what's seen in the observer's frame)
- Detail shots of body parts (hands, feet, eyes) unless plot-critical
- Atmospheric mood shots (incorporated into establishing shots)
- Multiple angles of same action (pick the best one)
- Isolated prop shots (props should appear WITH characters using them)
- Isolated location shots beyond the establishing frame

## CONTINUITY RULES

1. **Shot Variety**: Never plan 3+ consecutive frames with same shot type (e.g., no 3 medium shots in a row)
2. **Character Alternation**: In multi-character scenes, alternate focus between characters (max 3 consecutive frames of same character)
3. **Props With Characters**: Props are only shown when a character is interacting with them (no isolated prop close-ups)
4. **One Establishing Shot**: Each location gets ONE establishing wide shot, not multiple atmosphere shots
5. **Combine Context**: Location details, lighting, atmosphere all go in the establishing shot

## FRAME COUNT GUIDELINES

| Scene Length | Typical Frame Count |
|--------------|---------------------|
| Short (under 200 words) | 3-5 frames |
| Medium (200-400 words) | 5-8 frames |
| Long (400+ words) | 8-12 frames |

Maximum: 12 frames per scene. If you think you need more, you're fragmenting too much.

## ANALYSIS

1. Identify location changes (each = 1 establishing frame)
2. Count key physical actions that change the visual state
3. Mark story revelations or turning points
4. Count meaningful character interactions

## OUTPUT FORMAT

KEY BEATS:
1. [Beat description] - TYPE: [ESTABLISHING/ACTION/REVELATION/INTERACTION/TRANSITION]
2. [Beat description] - TYPE: [type]
...

FINAL FRAME COUNT: [number]

Be CONSERVATIVE. Each frame should show something VISUALLY DIFFERENT from the previous frame.
If two moments can be captured in one image, combine them."""

        # Single comprehensive analysis
        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a storyboard artist determining key frames. Focus on essential story beats only. Emotional details are handled by video generation. Be conservative - fewer, better frames.",
            function=LLMFunction.STORY_ANALYSIS
        )

        # Extract frame count from response
        try:
            # Look for "FINAL FRAME COUNT: X" pattern
            match = re.search(r'FINAL\s+FRAME\s+COUNT:\s*(\d+)', response, re.IGNORECASE)
            if match:
                count = int(match.group(1))
                # Cap at 12 frames per scene max
                return max(3, min(count, 12))

            # Fallback: find last number in response
            numbers = re.findall(r'\d+', response)
            if numbers:
                count = int(numbers[-1])
                return max(3, min(count, 12))
        except (ValueError, AttributeError):
            pass

        # Default based on scene length - conservative defaults
        word_count = len(scene_text.split())
        if word_count < 200:
            return 4
        elif word_count < 400:
            return 6
        else:
            return 8

    async def _determine_frame_points(
        self,
        scene_text: str,
        frame_count: int,
        scene_num: int
    ) -> List[FrameBoundary]:
        """Determine frame boundaries for key story beats.

        Focuses on essential visual moments that advance the story.
        Emotional nuances are handled by video generation, not separate frames.
        """
        prompt = f"""Determine the {frame_count} KEY FRAMES for this scene.

SCENE:
{scene_text}

TARGET FRAME COUNT: {frame_count}

## STORYBOARD FRAME PHILOSOPHY

Each frame should capture a DISTINCT VISUAL STATE. If two moments look similar, combine them.
Emotions, reactions, and micro-expressions are added by AI video - don't make separate frames for them.

## FRAME TYPES

| Type | Shot | Use For |
|------|------|---------|
| ESTABLISHING | Wide/Medium Wide | New location, time change, scene opening |
| ACTION | Medium/Medium Wide | Character doing something physical |
| INTERACTION | Medium/Two-Shot | Characters engaged with each other |
| REVELATION | Medium/Close-up | Discovery, realization, important moment |
| TRANSITION | Wide | Scene shifts, time jumps |
| REACTION | Close-up/Medium | Character reacting (MUST follow trigger frame) |

## REACTION SHOTS - SHOT/REVERSE-SHOT RULE

Reactions are valid ONLY when paired with trigger:
- Frame N: The trigger (what causes the reaction)
- Frame N+1: The reaction (character's response)

VALID: [Letter reveals betrayal] → [Mei's shocked face]
INVALID: [Mei looks shocked] (no trigger shown)

When creating reaction frames, always ensure the previous frame shows the cause.

## WHAT TO COMBINE (NOT separate frames)

- Observer + what they observe = ONE frame showing both (unless reaction shot follows)
- Character + their emotion = ONE frame (video animates expression)
- Detail + context = ONE frame with detail visible in scene
- Props + characters = Show props ONLY when characters interact with them
- Location + atmosphere = ONE establishing shot includes all environment details

## CONTINUITY RULES (MUST FOLLOW)

1. **Shot Variety**: Vary shot types - never use the same shot type 3+ times consecutively
   BAD: MS → MS → MS → MS
   GOOD: WS → MS → CU → MS → WS

2. **Character Alternation**: In scenes with multiple characters, alternate between them
   BAD: 5 frames of Mei, then 5 frames of Lin
   GOOD: Mei → Lin → Mei → Lin (or two-shots)

3. **No Isolated Props**: Props appear WITH the character using them, not alone
   BAD: "Close-up of the jade hairpin" (alone)
   GOOD: "Mei's hand adjusting the jade hairpin in her hair"

4. **Single Establishing Shot**: Each location gets ONE establishing shot
   BAD: Wide of brothel → Medium of brothel interior → Wide of receiving hall
   GOOD: Wide establishing shot of brothel receiving hall (covers it all)

## OUTPUT FORMAT

For each frame:

FRAME 1:
  START: "exact quote where frame begins"
  END: "exact quote where frame ends"
  BEAT_TYPE: [ESTABLISHING/ACTION/INTERACTION/REVELATION/TRANSITION]
  SHOT_TYPE: [WS/MWS/MS/MCU/CU/TWO-SHOT]
  CAMERA_ANGLE: [Eye Level / Low Angle / High Angle]
  CAPTURES: [What this single image shows - under 30 words]

FRAME 2:
  START: "exact quote"
  END: "exact quote"
  BEAT_TYPE: [type]
  SHOT_TYPE: [shot]
  CAMERA_ANGLE: [angle]
  CAPTURES: [description]

Continue for all {frame_count} frames.

## EXAMPLES OF GOOD FRAME CAPTURES

- "Wide shot of the brothel interior at dawn, Mei visible near the window"
- "Medium shot of Mei and Lin sitting across from each other at tea table"
- "Mei opening a letter, her expression curious, candlelight in background"

## AVOID

- Multiple frames for the same visual moment from different angles
- Separate frames for emotions (one frame shows character, video adds emotion)
- POV + reaction as separate frames (combine or pick most important)
- Atmospheric details as standalone frames (include in establishing shots)
- Consecutive same shot types (vary between WS/MS/CU)
- Long runs of same character (alternate in multi-character scenes)
- Isolated prop close-ups (props with characters only)"""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a storyboard artist identifying key frames. Focus on story beats, not micro-shots. Each frame should be visually distinct. Emotions and reactions are handled by video generation.",
            function=LLMFunction.STORY_ANALYSIS
        )

        # Parse boundaries with enhanced data
        return self._parse_frame_boundaries_enhanced(response, frame_count)

    def _parse_frame_boundaries_enhanced(
        self,
        response: str,
        frame_count: int
    ) -> List[FrameBoundary]:
        """Parse frame boundaries from LLM response.

        Extracts: START, END, BEAT_TYPE, SHOT_TYPE, CAMERA_ANGLE, CAPTURES
        Encodes shot/camera info into the captures field for downstream use.
        Falls back to legacy MOMENT_TYPE format if BEAT_TYPE not found.
        """
        boundaries = []

        # New pattern for visual moment format with MULTI_CAM support
        visual_moment_pattern = r'FRAME\s+(\d+):\s*\n\s*START:\s*["\']?([^"\'\n]+)["\']?\s*\n\s*END:\s*["\']?([^"\'\n]+)["\']?\s*\n\s*MOMENT_TYPE:\s*([^\n]+)\s*\n\s*SHOT_TYPE:\s*([^\n]+)\s*\n\s*CAMERA_ANGLE:\s*([^\n]+)\s*\n\s*MULTI_CAM:\s*(true|false)\s*\n\s*(?:CAMERAS_NEEDED:\s*([^\n]+(?:\n(?!\s*CAPTURES).*)*)\s*)?CAPTURES:\s*([^\n]+)'

        visual_matches = re.findall(visual_moment_pattern, response, re.DOTALL | re.IGNORECASE)

        if visual_matches:
            for match in visual_matches:
                frame_num = int(match[0])
                start_text = match[1].strip()
                end_text = match[2].strip()
                moment_type = match[3].strip()
                shot_type = match[4].strip()
                camera_angle = match[5].strip()
                is_multi_cam = match[6].strip().lower() == 'true'
                cameras_needed = match[7].strip() if len(match) > 7 and match[7] else ""
                captures = match[8].strip() if len(match) > 8 else ""

                if is_multi_cam and cameras_needed:
                    # Parse and expand multi-camera moments into separate boundaries
                    # Format: "cA: description, cB: description, cC: description"
                    cam_parts = re.findall(r'c([A-Z]):\s*([^,]+?)(?=,\s*c[A-Z]:|$)', cameras_needed)
                    for cam_letter, cam_desc in cam_parts:
                        cam_captures = f"[SHOT:{shot_type}|ANGLE:{camera_angle}|MOMENT:{moment_type}|CAM:c{cam_letter}] {cam_desc.strip()}"
                        boundaries.append(FrameBoundary(
                            frame_number=frame_num,
                            start_text=start_text,
                            end_text=end_text,
                            captures=cam_captures
                        ))
                else:
                    # Single camera frame
                    enhanced_captures = f"[SHOT:{shot_type}|ANGLE:{camera_angle}|MOMENT:{moment_type}] {captures}"
                    boundaries.append(FrameBoundary(
                        frame_number=frame_num,
                        start_text=start_text,
                        end_text=end_text,
                        captures=enhanced_captures
                    ))

        # Fallback to legacy BEAT_TYPE pattern if visual moment pattern fails
        if not boundaries:
            enhanced_pattern = r'FRAME\s+(\d+):\s*\n\s*START:\s*["\']?([^"\'\n]+)["\']?\s*\n\s*END:\s*["\']?([^"\'\n]+)["\']?\s*\n\s*BEAT_TYPE:\s*([^\n]+)\s*\n\s*SHOT_TYPE:\s*([^\n]+)\s*\n\s*CAMERA_ANGLE:\s*([^\n]+)\s*\n\s*CAPTURES:\s*([^\n]+(?:\n(?!\s*(?:FRAME|SEQUENCING)).*)*)\s*(?:SEQUENCING_NOTE:\s*([^\n]+(?:\n(?!\s*FRAME).*)*)?)?'

            matches = re.findall(enhanced_pattern, response, re.DOTALL | re.IGNORECASE)

            if matches:
                for match in matches:
                    frame_num = int(match[0])
                    start_text = match[1].strip()
                    end_text = match[2].strip()
                    beat_type = match[3].strip()
                    shot_type = match[4].strip()
                    camera_angle = match[5].strip()
                    captures = match[6].strip()

                    enhanced_captures = f"[SHOT:{shot_type}|ANGLE:{camera_angle}|BEAT:{beat_type}] {captures}"

                    boundaries.append(FrameBoundary(
                        frame_number=frame_num,
                        start_text=start_text,
                        end_text=end_text,
                        captures=enhanced_captures
                    ))

        # Final fallback to simple pattern
        if not boundaries:
            return self._parse_frame_boundaries(response, frame_count)

        # Ensure we have the right number of boundaries
        while len(boundaries) < frame_count:
            pos = len(boundaries) + 1
            if pos == 1:
                default_shot = "WS"
                default_angle = "Eye Level"
                default_beat = "ESTABLISHING"
            elif pos == frame_count:
                default_shot = "MS"
                default_angle = "Eye Level"
                default_beat = "TRANSITION"
            else:
                default_shot = "MS"
                default_angle = "Eye Level"
                default_beat = "ACTION"

            boundaries.append(FrameBoundary(
                frame_number=pos,
                start_text="",
                end_text="",
                captures=f"[SHOT:{default_shot}|ANGLE:{default_angle}|BEAT:{default_beat}] Frame {pos}"
            ))

        return boundaries[:frame_count]

    def _parse_frame_boundaries(
        self,
        response: str,
        frame_count: int
    ) -> List[FrameBoundary]:
        """Parse frame boundaries from LLM response (legacy simple format)."""
        boundaries = []

        # Pattern to match FRAME N: blocks
        frame_pattern = r'FRAME\s+(\d+):\s*\n\s*START:\s*["\']?([^"\']+)["\']?\s*\n\s*END:\s*["\']?([^"\']+)["\']?\s*\n\s*CAPTURES:\s*(.+?)(?=FRAME\s+\d+:|$)'

        matches = re.findall(frame_pattern, response, re.DOTALL | re.IGNORECASE)

        for match in matches:
            frame_num = int(match[0])
            boundaries.append(FrameBoundary(
                frame_number=frame_num,
                start_text=match[1].strip(),
                end_text=match[2].strip(),
                captures=match[3].strip()
            ))

        # Ensure we have the right number of boundaries
        while len(boundaries) < frame_count:
            boundaries.append(FrameBoundary(
                frame_number=len(boundaries) + 1,
                start_text="",
                end_text="",
                captures=f"Frame {len(boundaries) + 1}"
            ))

        return boundaries[:frame_count]

    async def _mark_frames(
        self,
        scene_text: str,
        boundaries: List[FrameBoundary],
        scene_num: int
    ) -> str:
        """Insert frame markers into scene text with shot type from boundary analysis."""
        # Extract shot metadata from boundaries for marker insertion
        frame_shots = self._extract_shot_metadata_from_boundaries(boundaries)

        prompt = f"""Insert frame markers into this scene with SPECIFIC SHOT TYPES.

ORIGINAL SCENE:
{scene_text}

FRAME BOUNDARIES WITH SHOT SPECIFICATIONS:
{self._format_boundaries_with_shots(boundaries, frame_shots)}

SCENE NUMBER: {scene_num}

Insert the following markers using scene.frame.camera notation:
1. At each frame start:
   (/scene_frame_chunk_start/)
   [{scene_num}.FRAME_NUMBER.cA] (SHOT_TYPE, CAMERA_ANGLE)

2. At each frame end:
   (/scene_frame_chunk_end/)

IMPORTANT: Use the EXACT shot type and camera angle specified for each frame!
Example: [{scene_num}.1.cA] (WIDE, Eye Level)
         [{scene_num}.2.cA] (MEDIUM, Low Angle)

Use frame IDs in scene.frame format: [{scene_num}.1.cA], [{scene_num}.2.cA], etc.
The notation is: [scene.frame.camera] where camera starts with cA.

Output the full scene text with all markers inserted.
Preserve ALL original text - only ADD markers."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a text markup agent inserting frame markers with precise shot types.",
            function=LLMFunction.STORY_GENERATION
        )

        return response

    def _extract_shot_metadata_from_boundaries(
        self,
        boundaries: List[FrameBoundary]
    ) -> Dict[int, Dict[str, str]]:
        """Extract shot type and camera angle from boundary captures.

        Looks for encoded format: [SHOT:type|ANGLE:angle|BEAT:beat]
        """
        metadata = {}
        for b in boundaries:
            shot_match = re.search(r'\[SHOT:([^|]+)\|ANGLE:([^|]+)\|BEAT:([^\]]+)\]', b.captures)
            if shot_match:
                metadata[b.frame_number] = {
                    "shot_type": shot_match.group(1).strip(),
                    "camera_angle": shot_match.group(2).strip(),
                    "beat_type": shot_match.group(3).strip()
                }
            else:
                # Default based on frame position
                if b.frame_number == 1:
                    metadata[b.frame_number] = {
                        "shot_type": "WIDE",
                        "camera_angle": "Eye Level",
                        "beat_type": "ESTABLISHING"
                    }
                else:
                    metadata[b.frame_number] = {
                        "shot_type": "MEDIUM",
                        "camera_angle": "Eye Level",
                        "beat_type": "CONTINUATION"
                    }
        return metadata

    def _format_boundaries_with_shots(
        self,
        boundaries: List[FrameBoundary],
        frame_shots: Dict[int, Dict[str, str]]
    ) -> str:
        """Format boundaries with shot specifications for prompt."""
        lines = []
        for b in boundaries:
            shots = frame_shots.get(b.frame_number, {})
            shot_type = shots.get("shot_type", "MEDIUM")
            camera_angle = shots.get("camera_angle", "Eye Level")
            beat_type = shots.get("beat_type", "")

            lines.append(f"FRAME {b.frame_number}:")
            lines.append(f"  START: \"{b.start_text}\"")
            lines.append(f"  END: \"{b.end_text}\"")
            lines.append(f"  SHOT_TYPE: {shot_type}")
            lines.append(f"  CAMERA_ANGLE: {camera_angle}")
            lines.append(f"  BEAT: {beat_type}")
            # Clean captures of metadata encoding for cleaner display
            clean_captures = re.sub(r'\[SHOT:[^\]]+\]\s*', '', b.captures)
            clean_captures = re.sub(r'\[FLOW:[^\]]+\]\s*', '', clean_captures)
            lines.append(f"  CAPTURES: {clean_captures.strip()}")
            lines.append("")
        return "\n".join(lines)

    def _format_boundaries(self, boundaries: List[FrameBoundary]) -> str:
        """Format boundaries for prompt (legacy simple format)."""
        lines = []
        for b in boundaries:
            lines.append(f"FRAME {b.frame_number}:")
            lines.append(f"  START: \"{b.start_text}\"")
            lines.append(f"  END: \"{b.end_text}\"")
            lines.append(f"  CAPTURES: {b.captures}")
            lines.append("")
        return "\n".join(lines)

    async def _insert_frame_prompts(
        self,
        marked_text: str,
        boundaries: List[FrameBoundary],
        scene_num: int,
        data: Dict[str, Any]
    ) -> List[FrameChunk]:
        """Insert visual prompts for each frame with explicit tag and location direction output.

        Uses hierarchical context aggregation to ensure consistency across frames.
        Context flows: Scene → Frame → Camera
        """
        world_config = data.get("world_config", {})
        visual_style = data.get("visual_style", "")

        # Initialize context aggregator for this scene
        from greenlight.pipelines.context_aggregator import ContextAggregator
        context_agg = ContextAggregator(world_config)

        # Extract scene metadata for context (enhanced extraction)
        scene_metadata = self._extract_scene_metadata_from_text(marked_text)

        # Start scene context
        scene_ctx = context_agg.start_scene(
            scene_number=scene_num,
            location_tag=scene_metadata.get("location_tag", ""),
            time_of_day=scene_metadata.get("time", ""),
            weather=scene_metadata.get("weather", ""),
            atmosphere=scene_metadata.get("atmosphere", ""),
            characters=scene_metadata.get("characters", [])
        )

        # Get consistency constraints for this scene
        consistency_constraints = context_agg.get_consistency_constraints()
        constraints_text = "\n".join([f"  - {c}" for c in consistency_constraints]) if consistency_constraints else "  (none)"

        # Get scene context for prompt
        scene_context_str = scene_ctx.to_prompt_context()

        # Add scene heading and lighting hints to context
        scene_heading = scene_metadata.get("scene_heading", "")
        lighting_hint = scene_metadata.get("lighting_hint", "")

        # Build enhanced scene context with heading and lighting
        if scene_heading:
            scene_context_str = f"SCENE SETTING: {scene_heading}\n{scene_context_str}"
        if lighting_hint:
            scene_context_str += f"\n  LIGHTING CUE: {lighting_hint}"

        # Build time consistency constraint
        time_of_day = scene_metadata.get("time", "")
        if time_of_day:
            if "evening" in time_of_day.lower() or "night" in time_of_day.lower():
                constraints_text += f"\n  - TIME CONSTRAINT: This is {time_of_day} - use appropriate darkness, indoor lighting (lamps/lanterns), NO bright daylight"
            elif "morning" in time_of_day.lower():
                constraints_text += f"\n  - TIME CONSTRAINT: This is {time_of_day} - use warm morning sunlight, NO moon, NO night sky"
            elif "afternoon" in time_of_day.lower():
                constraints_text += f"\n  - TIME CONSTRAINT: This is {time_of_day} - use afternoon sunlight, warm tones"

        # Format character tags with descriptions
        # Note: world_config uses 'description' field for characters
        characters = world_config.get("characters", [])
        char_tags_section = "\n".join([
            f"  [{c.get('tag', '')}]: {c.get('description', c.get('visual_description', c.get('appearance', '')))}"
            for c in characters if c.get('tag')
        ])

        # Format location tags with descriptions
        locations = world_config.get("locations", [])
        loc_tags_section = "\n".join([
            f"  [{l.get('tag', '')}]: {l.get('description', '')}"
            for l in locations if l.get('tag')
        ])

        # Format prop tags with descriptions
        props = world_config.get("props", [])
        prop_tags_section = "\n".join([
            f"  [{p.get('tag', '')}]: {p.get('description', '')}"
            for p in props if p.get('tag')
        ])

        # Extract period/era context from world_config for period-accurate prompts
        world_rules = world_config.get("world_rules", "")
        lighting_style = world_config.get("lighting", "")
        vibe = world_config.get("vibe", "")

        # Build period context section dynamically
        period_context = ""
        if world_rules:
            # Extract first 2 sentences of world_rules for period context
            rules_sentences = world_rules.split(". ")[:2]
            period_context = ". ".join(rules_sentences)
            if period_context and not period_context.endswith("."):
                period_context += "."

        prompt = f"""Write TWO-TIER frame descriptions for visual moments using EXPLICIT TAG NOTATION.

## SCENE CONTEXT
{scene_context_str}

## SCENE CONTENT
{marked_text}

## VISUAL STYLE
{visual_style}

## WORLD CONTEXT
{period_context if period_context else "Contemporary setting"}

## LIGHTING STYLE
{lighting_style if lighting_style else "Natural, cinematic lighting"}

## AVAILABLE TAGS
CHARACTERS: {char_tags_section if char_tags_section else "(none)"}
LOCATIONS: {loc_tags_section if loc_tags_section else "(none)"}
PROPS: {prop_tags_section if prop_tags_section else "(none)"}

## TWO-TIER DESCRIPTION SYSTEM

Each frame needs TWO descriptions:

### 1. VISUAL_DESCRIPTION (Rich Storytelling - 100-150 words)
The director's vision with full cinematic context:
- Emotional beat and narrative intent
- Lighting motivation and atmosphere
- Visual subtext and symbolism
- Character blocking and spatial relationships
- How this shot connects to the story

### 2. PROMPT (Detailed - 80-120 words)
A complete image generation prompt with ALL visual details needed to render this frame:

**REQUIRED STRUCTURE (follow this order):**
1. SHOT TYPE & ANGLE: "Wide shot, eye level" or "Close-up, low angle looking up"
2. SUBJECT WITH FULL COSTUME: Always include complete outfit description from character data - fabric, color, style, accessories
3. ACTION/POSE: Specific body position and what they're doing
4. SETTING DETAILS: Architectural elements, props, environmental layers (foreground/midground/background)
5. LIGHTING: Direction, quality, color temperature - match the LIGHTING STYLE and time of day
6. ATMOSPHERE: Weather, particles, mood - match the world's vibe
7. PERIOD/WORLD ACCURACY: Match the WORLD CONTEXT above - use period-appropriate clothing, architecture, props, lighting sources

### CRITICAL PROMPT RULES

**WORLD CONSISTENCY:**
- ALL clothing, architecture, and props must match the WORLD CONTEXT provided above
- Use period-appropriate lighting sources (no electric lights in historical settings)
- Match the established visual style and atmosphere

**TIME CONSISTENCY:**
- If scene is morning/dawn: use warm sunrise lighting - NEVER "moon", "moonlight", "night"
- If scene is evening/night: use appropriate night lighting - NEVER "bright daylight", "sunrise"
- Maintain consistent time of day throughout the scene

**CHARACTER COSTUME ANCHORING:**
- NEVER write just "[CHAR_TAG]" alone - ALWAYS include full costume description
- Pull costume details from the character descriptions provided above
- Include: fabric type, color, condition, accessories
- Make costumes specific and visual, not generic

**COMPOSITION:**
- Specify exact positions: "screen-left", "center frame", "in foreground"
- Include depth layers when relevant: foreground element, subject, background
- For POV shots: clearly indicate the viewing perspective

## VISUAL MOMENT TYPES

| Type | Shot | Purpose |
|------|------|---------|
| DETAIL | ECU/INSERT | Isolated poetry - hands, feet, objects, light |
| POV | Medium/Wide | What a character literally sees |
| REACTION | CU | Character's face/expression responding |
| CONTEXT | Wide | Character in environment, scale, isolation |
| CROSS_CUT | Varies | Alternating observer ↔ observed |

## CROSS-CUTTING RULE

When Character A observes Character B:
- X.cA: Subject doing action (the observed)
- X.cB: Observer watching (the watcher)
- X.cC: POV detail (what watcher focuses on)

## OUTPUT FORMAT

[{scene_num}.X.cA] (Shot Type, Angle)
TAGS: [CHAR_X], [LOC_Y], [PROP_Z]
LOCATION_DIRECTION: NORTH
BEAT: [Emotional beat - Longing/Tension/Intimacy/Discovery/etc.]
VISUAL_DESCRIPTION: Rich cinematic storytelling with emotional context, lighting motivation, visual subtext, and narrative connection. This is the director's vision explaining WHY this shot matters and what it communicates beyond the literal image. Include atmosphere, mood, and how this moment fits the scene's emotional arc. (100-150 words)
PROMPT: Complete image generation prompt following the REQUIRED STRUCTURE above. Include shot type, full costume description, action, setting details, lighting direction, atmosphere, and world-appropriate elements. (80-120 words)

## EXAMPLE OUTPUT (format demonstration - use YOUR project's tags and world context)

[{scene_num}.1.cA] (ECU, Eye Level)
TAGS: [LOC_LU_XIAN_BROTHEL]
LOCATION_DIRECTION: EAST
BEAT: Atmosphere - establishing poetic mood
VISUAL_DESCRIPTION: The opening shot fragments the world into texture and light before we see any character. Morning sunlight creeps across aged wooden floorboards, each plank telling stories of countless footsteps. The warm golden strips create a visual rhythm - light, shadow, light - that will echo throughout the scene. This is [CHAR_MEI]'s world reduced to its essence: beautiful surfaces, trapped in routine patterns. The floor has been polished by servants until it gleams, much like Mei herself has been polished for presentation. Starting with this detail rather than the character invites us into a contemplative, intimate space.
PROMPT: Extreme close-up, eye level. Polished aged wooden floorboards inside [LOC_LU_XIAN_BROTHEL], honey-patina timber planks worn smooth by generations. Warm golden sunrise light streaming through unseen lattice window, casting geometric shadow strips across the wood grain. Dust motes suspended in light beams. Traditional Chinese interior, dark timber architecture. Dawn atmosphere, soft diffused morning glow.

[{scene_num}.1.cB] (ECU, Eye Level)
TAGS: [CHAR_MEI]
LOCATION_DIRECTION: EAST
BEAT: Vulnerability - intimate character detail
VISUAL_DESCRIPTION: We discover [CHAR_MEI] through the most vulnerable part of her body - her bare feet. In this world where she is valued only for what men see and desire, her feet touching the floor is a private moment. The golden light that painted the floorboards now paints her skin, connecting her to her environment. She is literally grounded here, in this room, on this morning of her last day of freedom. The strips of light crossing her feet foreshadow the cage of her circumstances - beauty trapped between bars of gold.
PROMPT: Extreme close-up, eye level. [CHAR_MEI]'s bare feet on polished wooden floorboards, pale porcelain skin against dark honey-colored timber. Hem of flowing pale silk sleeping robe visible at ankles, delicate fabric pooling on floor. Strips of warm golden sunrise light painting geometric patterns across her skin and the wood. Small jade anklet on left ankle. Traditional Chinese interior. Dawn, soft morning glow from lattice window.

[{scene_num}.1.cC] (Medium Wide, Low Angle)
TAGS: [CHAR_MEI], [LOC_LU_XIAN_BROTHEL], [PROP_BAMBOO_SLEEPING_MAT]
LOCATION_DIRECTION: EAST
BEAT: Isolation - character in space
VISUAL_DESCRIPTION: Finally we see [CHAR_MEI] in full context, but the low angle grants her dignity despite her circumstances. She kneels at the edge of her sleeping mat, silhouetted against morning light streaming through the window - a figure suspended between rest and waking, between her current life and what tomorrow brings. The side profile keeps her expression partially hidden, maintaining mystery. The vast empty space of the room emphasizes her isolation; she is a small figure in a large cage. The mat behind her represents the only space that is truly hers.
PROMPT: Medium wide shot, low angle looking up. Side profile of [CHAR_MEI] in flowing pale silk sleeping robe with loose sash, lustrous black hair unbound cascading past her waist, kneeling at edge of [PROP_BAMBOO_SLEEPING_MAT]. Warm sunrise light streaming through carved lattice window behind her, silhouetting her graceful form. Traditional Chinese bedroom in [LOC_LU_XIAN_BROTHEL], dark timber beams, silk curtains, bronze incense burner trailing thin smoke. Dawn, golden rim light on her figure, deep shadows in room corners.

[{scene_num}.4.cA] (Wide, Eye Level)
TAGS: [CHAR_LIN], [LOC_FLORIST_SHOP], [PROP_GARDENING_TOOLS]
LOCATION_DIRECTION: NORTH
BEAT: Cross-cut - the observed subject
VISUAL_DESCRIPTION: [CHAR_LIN] exists in a completely different visual world than Mei - open air, natural light, honest work. He tends his flowers with the same patience and gentleness that Mei has observed and idealized from her window. His worn gardening tools speak of years of labor, hands that create rather than perform. The morning sun catches the chrysanthemums he coaxes toward light, mirroring his own nature: growing things toward life rather than selling them. He is unaware of being watched, unperformed, authentic - everything Mei is not allowed to be.
PROMPT: Wide shot, eye level. [CHAR_LIN] in worn tan cotton work tunic with cloth belt, loose brown trousers, simple cloth headband holding back sun-lightened brown hair in loose topknot, bent over ceramic flower pots at [LOC_FLORIST_SHOP]. Wooden shopfront with sliding screens open, clay pots overflowing with white chrysanthemums and pink peonies. [PROP_GARDENING_TOOLS] - pruning shears, watering vessel - on worn wooden counter. Warm golden sunrise light flooding the street corner, long morning shadows. Traditional Chinese street architecture, paper lanterns on bamboo poles. Dawn, outdoor scene.

[{scene_num}.4.cB] (CU, High Angle)
TAGS: [CHAR_MEI]
LOCATION_DIRECTION: EAST
BEAT: Cross-cut - the observer watching
VISUAL_DESCRIPTION: The high angle looking down on [CHAR_MEI] reinforces her hidden, voyeuristic position. Half her face is shadowed by the curtain she hides behind, creating visual duality - the public self she shows the world, and the private longing she conceals. Her eyes are the focal point, carrying years of silent observation. She watches [CHAR_LIN] with an intensity that borders on devotion, having built an entire fantasy of tenderness from glimpses through her window. This is not mere curiosity but a lifeline - proof that gentleness exists somewhere in the world.
PROMPT: Close-up, high angle looking down. [CHAR_MEI] in pale silk sleeping robe, lustrous black hair loosely pinned with single jade hairpin, peering from behind sheer silk curtain at carved rosewood terrace railing. Dark amber almond eyes intent and watchful, pale moonlight-white skin, subtle longing in expression. Half her face in shadow from curtain, half illuminated by warm morning light from window. Traditional Chinese terrace with carved peony motifs on railing, potted orchids in foreground. Dawn interior, intimate lighting.

[{scene_num}.4.cC] (ECU, Eye Level)
TAGS: [CHAR_LIN], [PROP_GARDENING_TOOLS]
LOCATION_DIRECTION: NORTH
BEAT: Cross-cut - POV detail focus
VISUAL_DESCRIPTION: This is what [CHAR_MEI] actually focuses on: [CHAR_LIN]'s hands. Not his face, not his body as her clients evaluate hers, but his hands - patient, weathered, gentle as they prune dead growth to make room for new life. The metaphor is not lost: she too has dead growth that needs pruning, and she wonders if hands like his could help her grow. This extreme close-up isolates the detail that carries all her hope - the possibility of being touched with care rather than transaction.
PROMPT: Extreme close-up, eye level, POV from above through lattice window. [CHAR_LIN]'s weathered tan hands with calloused fingers and soil-stained nails, gently holding bronze pruning shears from [PROP_GARDENING_TOOLS], carefully trimming white chrysanthemum stems. Soft petals catching warm golden sunrise light. Worn cloth sleeve of tan work tunic visible at wrist. Outdoor flower shop setting below, ceramic pots with blooming flowers. Dawn, morning light creating gentle shadows on his working hands.

Continue for all visual moments. Include BOTH rich VISUAL_DESCRIPTION and detailed PROMPT (80-120 words) for each frame."""

        # Build system prompt with dynamic world context
        system_prompt = f"""You are an expert visual prompt writer for AI image generation, specializing in world-accurate cinematic storyboarding.

CORE RULES:
1. TAGS MUST STAY INTACT: Write [CHAR_X], [LOC_Y], [PROP_Z] exactly as provided - never expand or replace them
2. COSTUME DETAILS ARE MANDATORY: Every character mention includes full outfit description (fabric, color, condition, accessories)
3. WORLD ACCURACY IS NON-NEGOTIABLE: Match the world context, period, and visual style provided - no anachronistic elements
4. LIGHTING IS DIRECTIONAL: Specify light source direction, quality, color temperature, and shadow behavior
5. PROMPTS ARE 80-120 WORDS: Rich enough for image generation, not sparse summaries

WORLD CONTEXT FOR THIS PROJECT:
{period_context if period_context else "Contemporary/modern setting"}

LIGHTING STYLE FOR THIS PROJECT:
{lighting_style if lighting_style else "Natural cinematic lighting"}

STRUCTURE EVERY PROMPT:
Shot Type → Subject with Costume → Action/Pose → Setting Details → Lighting → Atmosphere → World-Appropriate Elements

SHOT VARIETY IS CRITICAL:
- Start scenes with WIDE/ESTABLISHING shots to set context
- Mix shot types: Wide → Medium → Close-up → Extreme Close-up → Wide
- NEVER use more than 2 consecutive medium shots
- Include at least 1 close-up per 5 frames for emotional impact
- Use ECU (extreme close-up) for detail shots: hands, eyes, objects

AVOID:
- Bare character tags without costume ([CHAR_X] alone - WRONG)
- Generic lighting ("natural light" - TOO VAGUE)
- Anachronistic elements that don't match the world context
- Emotional abstractions in PROMPT section (save those for VISUAL_DESCRIPTION)
- Prompts under 60 words (TOO SPARSE)
- Shot monotony (3+ consecutive same shot types)"""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt=system_prompt,
            function=LLMFunction.STORY_GENERATION
        )

        # Parse frames from response (now extracts TAGS and LOCATION_DIRECTION)
        return self._parse_frame_chunks(response, scene_num, boundaries, world_config)

    def _parse_frame_chunks(
        self,
        response: str,
        scene_num: int,
        boundaries: List[FrameBoundary],
        world_config: Optional[Dict[str, Any]] = None
    ) -> List[FrameChunk]:
        """Parse frame chunks from prompted response with tag and location direction extraction.

        Supports multiple notation formats:
        - Format 1: [1.2.cA] (Wide) TAGS: [...] LOCATION_DIRECTION: X PROMPT: ...
        - Format 2: [1.2.cA] (Wide) cA. PROMPT TEXT...
        - Format 3: {frame_1.2} [PROMPT: ...]
        """
        frames = []

        # Build set of valid tags from world_config for validation
        valid_tags = set()
        if world_config:
            for char in world_config.get("characters", []):
                if char.get("tag"):
                    valid_tags.add(char["tag"])
            for loc in world_config.get("locations", []):
                if loc.get("tag"):
                    valid_tags.add(loc["tag"])
            for prop in world_config.get("props", []):
                if prop.get("tag"):
                    valid_tags.add(prop["tag"])

        # Primary pattern: Two-tier format with VISUAL_DESCRIPTION and PROMPT
        # [1.2.cA] (Wide, Eye Level)
        # TAGS: [CHAR_X], [LOC_Y]
        # LOCATION_DIRECTION: NORTH
        # BEAT: Emotional beat description
        # VISUAL_DESCRIPTION: Rich cinematic storytelling...
        # PROMPT: Concise image generation prompt...
        two_tier_pattern = r'\[(\d+)\.(\d+)\.c([A-Z])\]\s*\(([^)]+)\)\s*TAGS:\s*([^\n]+)\s*LOCATION_DIRECTION:\s*(NORTH|EAST|SOUTH|WEST)\s*(?:BEAT:\s*([^\n]+)\s*)?VISUAL_DESCRIPTION:\s*(.+?)\s*PROMPT:\s*(.+?)(?=\[\d+\.\d+\.c[A-Z]\]|\(/scene_frame_chunk_end/\)|$)'
        two_tier_matches = re.findall(two_tier_pattern, response, re.DOTALL | re.IGNORECASE)

        if two_tier_matches:
            for match in two_tier_matches:
                scene_n = int(match[0])
                frame_n = int(match[1])
                camera_letter = match[2]
                shot_type = match[3].strip()
                tags_line = match[4].strip()
                location_direction = match[5].strip().upper()
                beat = match[6].strip() if len(match) > 6 and match[6] else ""
                visual_description = match[7].strip() if len(match) > 7 and match[7] else ""
                prompt_text = match[8].strip() if len(match) > 8 else ""

                # Parse tags from TAGS line
                extracted_tags = self._extract_tags_from_line(tags_line, valid_tags)

                # Clean up visual_description and prompt
                visual_description = re.sub(r'\(/scene_frame_chunk_start/\).*', '', visual_description, flags=re.DOTALL).strip()
                visual_description = re.sub(r'\n\s*\n\s*\n', '\n\n', visual_description)
                prompt_text = re.sub(r'\(/scene_frame_chunk_start/\).*', '', prompt_text, flags=re.DOTALL).strip()
                prompt_text = re.sub(r'\n\s*\n\s*\n', '\n\n', prompt_text)

                # Enforce word caps (expanded for richer prompts)
                vis_words = visual_description.split()
                if len(vis_words) > 200:
                    visual_description = " ".join(vis_words[:200])

                prompt_words = prompt_text.split()
                if len(prompt_words) > 150:
                    prompt_text = " ".join(prompt_words[:150])

                if prompt_text:
                    camera_id = f"{scene_n}.{frame_n}.c{camera_letter}"
                    frames.append(FrameChunk(
                        frame_id=f"{scene_n}.{frame_n}",
                        scene_number=scene_n,
                        frame_number=frame_n,
                        original_text="",
                        camera_notation=f"[{camera_id}] ({shot_type})",
                        visual_description=visual_description,
                        prompt=prompt_text,
                        cameras=[camera_id],
                        tags=extracted_tags,
                        location_direction=location_direction,
                        beat=beat
                    ))

        # Fallback: Legacy format with BEAT, LIGHTING, MOTION, PROMPT (no VISUAL_DESCRIPTION)
        if not frames:
            cinematic_pattern = r'\[(\d+)\.(\d+)\.c([A-Z])\]\s*\(([^)]+)\)\s*TAGS:\s*([^\n]+)\s*LOCATION_DIRECTION:\s*(NORTH|EAST|SOUTH|WEST)\s*(?:BEAT:\s*([^\n]+)\s*)?(?:LIGHTING:\s*([^\n]+)\s*)?(?:CONTINUITY_FROM:\s*[^\n]*\s*)?(?:MOTION:\s*([^\n]+)\s*)?PROMPT:\s*(.+?)(?=\[\d+\.\d+\.c[A-Z]\]|\(/scene_frame_chunk_end/\)|$)'
            cinematic_matches = re.findall(cinematic_pattern, response, re.DOTALL | re.IGNORECASE)

            for match in cinematic_matches:
                scene_n = int(match[0])
                frame_n = int(match[1])
                camera_letter = match[2]
                shot_type = match[3].strip()
                tags_line = match[4].strip()
                location_direction = match[5].strip().upper()
                beat = match[6].strip() if len(match) > 6 and match[6] else ""
                lighting = match[7].strip() if len(match) > 7 and match[7] else ""
                motion_prompt = match[8].strip() if len(match) > 8 and match[8] else ""
                prompt_text = match[9].strip() if len(match) > 9 else ""

                extracted_tags = self._extract_tags_from_line(tags_line, valid_tags)
                prompt_text = re.sub(r'\(/scene_frame_chunk_start/\).*', '', prompt_text, flags=re.DOTALL).strip()

                # Enforce 150 word cap (expanded for richer prompts)
                words = prompt_text.split()
                if len(words) > 150:
                    prompt_text = " ".join(words[:150])

                if prompt_text:
                    camera_id = f"{scene_n}.{frame_n}.c{camera_letter}"
                    frames.append(FrameChunk(
                        frame_id=f"{scene_n}.{frame_n}",
                        scene_number=scene_n,
                        frame_number=frame_n,
                        original_text="",
                        camera_notation=f"[{camera_id}] ({shot_type})",
                        lighting_notation=lighting,
                        prompt=prompt_text,
                        cameras=[camera_id],
                        tags=extracted_tags,
                        location_direction=location_direction,
                        motion_prompt=motion_prompt,
                        beat=beat
                    ))

        # Legacy pattern: Format without BEAT/LIGHTING (backward compatibility)
        # [1.2.cA] (Wide)
        # TAGS: [CHAR_X], [LOC_Y]
        # LOCATION_DIRECTION: NORTH
        # MOTION: Camera and subject movement description
        # PROMPT: ...
        if not frames:
            legacy_pattern = r'\[(\d+)\.(\d+)\.c([A-Z])\]\s*\(([^)]+)\)\s*(?:c[A-Z]\.\s*[A-Z\s]+\.\s*)?TAGS:\s*([^\n]+)\s*LOCATION_DIRECTION:\s*(NORTH|EAST|SOUTH|WEST)\s*(?:CONTINUITY_FROM:\s*[^\n]*\s*)?(?:MOTION:\s*([^\n]+)\s*)?PROMPT:\s*(.+?)(?=\[\d+\.\d+\.c[A-Z]\]|\(/scene_frame_chunk_end/\)|$)'
            legacy_matches = re.findall(legacy_pattern, response, re.DOTALL | re.IGNORECASE)

            for match in legacy_matches:
                scene_n = int(match[0])
                frame_n = int(match[1])
                camera_letter = match[2]
                shot_type = match[3].strip()
                tags_line = match[4].strip()
                location_direction = match[5].strip().upper()
                motion_prompt = match[6].strip() if len(match) > 6 and match[6] else ""
                prompt_text = match[7].strip() if len(match) > 7 else match[6].strip()

                # Parse tags from TAGS line
                extracted_tags = self._extract_tags_from_line(tags_line, valid_tags)

                # Clean up prompt text
                prompt_text = re.sub(r'\(/scene_frame_chunk_start/\).*', '', prompt_text, flags=re.DOTALL).strip()
                prompt_text = re.sub(r'\n\s*\n\s*\n', '\n\n', prompt_text)

                # Enforce 150 word cap (expanded for richer prompts)
                words = prompt_text.split()
                if len(words) > 150:
                    prompt_text = " ".join(words[:150])

                if prompt_text:
                    camera_id = f"{scene_n}.{frame_n}.c{camera_letter}"
                    frames.append(FrameChunk(
                        frame_id=f"{scene_n}.{frame_n}",
                        scene_number=scene_n,
                        frame_number=frame_n,
                        original_text="",
                        camera_notation=f"[{camera_id}] ({shot_type})",
                        prompt=prompt_text,
                        cameras=[camera_id],
                        tags=extracted_tags,
                        location_direction=location_direction,
                        motion_prompt=motion_prompt
                    ))

        # Fallback Pattern 1: [scene.frame.cX] (ShotType) with content (no explicit TAGS/DIRECTION)
        if not frames:
            pattern1 = r'\[(\d+)\.(\d+)\.c([A-Z])\]\s*\(([^)]+)\)\s*(?:c[A-Z]\.\s*)?(.+?)(?=\[\d+\.\d+\.c[A-Z]\]|\(/scene_frame_chunk_end/\)|$)'
            matches1 = re.findall(pattern1, response, re.DOTALL)

            for match in matches1:
                scene_n = int(match[0])
                frame_n = int(match[1])
                camera_letter = match[2]
                shot_type = match[3].strip()
                content = match[4].strip()

                # Try to extract TAGS and LOCATION_DIRECTION from content
                tags_match = re.search(r'TAGS:\s*([^\n]+)', content, re.IGNORECASE)
                direction_match = re.search(r'LOCATION_DIRECTION:\s*(NORTH|EAST|SOUTH|WEST)', content, re.IGNORECASE)
                prompt_match = re.search(r'PROMPT:\s*(.+)', content, re.DOTALL | re.IGNORECASE)

                if prompt_match:
                    prompt_text = prompt_match.group(1).strip()
                else:
                    # Use entire content as prompt if no PROMPT: marker
                    prompt_text = content

                # Extract tags
                if tags_match:
                    extracted_tags = self._extract_tags_from_line(tags_match.group(1), valid_tags)
                else:
                    # Fallback: extract tags from prompt text
                    extracted_tags = self._extract_tags_from_prompt_text(prompt_text, valid_tags)

                # Extract location direction
                location_direction = direction_match.group(1).upper() if direction_match else "NORTH"

                # Clean up prompt
                prompt_text = re.sub(r'TAGS:\s*[^\n]+\n?', '', prompt_text, flags=re.IGNORECASE)
                prompt_text = re.sub(r'LOCATION_DIRECTION:\s*(NORTH|EAST|SOUTH|WEST)\n?', '', prompt_text, flags=re.IGNORECASE)
                prompt_text = re.sub(r'\(/scene_frame_chunk_start/\).*', '', prompt_text, flags=re.DOTALL).strip()
                prompt_text = re.sub(r'\n\s*\n\s*\n', '\n\n', prompt_text)

                words = prompt_text.split()
                if len(words) > 150:
                    prompt_text = " ".join(words[:150])

                if prompt_text:
                    camera_id = f"{scene_n}.{frame_n}.c{camera_letter}"
                    frames.append(FrameChunk(
                        frame_id=f"{scene_n}.{frame_n}",
                        scene_number=scene_n,
                        frame_number=frame_n,
                        original_text="",
                        camera_notation=f"[{camera_id}] ({shot_type})",
                        prompt=prompt_text,
                        cameras=[camera_id],
                        tags=extracted_tags,
                        location_direction=location_direction
                    ))

        # Fallback Pattern 2: [PROMPT: ...] blocks
        if not frames:
            prompt_pattern = r'\[(\d+)\.(\d+)\.c([A-Z])\][^\[]*\[PROMPT:\s*([^\]]+)\]'
            matches2 = re.findall(prompt_pattern, response, re.DOTALL)

            for match in matches2:
                scene_n = int(match[0])
                frame_n = int(match[1])
                camera_letter = match[2]
                prompt_text = match[3].strip()

                extracted_tags = self._extract_tags_from_prompt_text(prompt_text, valid_tags)

                words = prompt_text.split()
                if len(words) > 150:
                    prompt_text = " ".join(words[:150])

                camera_id = f"{scene_n}.{frame_n}.c{camera_letter}"
                frames.append(FrameChunk(
                    frame_id=f"{scene_n}.{frame_n}",
                    scene_number=scene_n,
                    frame_number=frame_n,
                    original_text="",
                    camera_notation=f"[{camera_id}] (Frame)",
                    prompt=prompt_text,
                    cameras=[camera_id],
                    tags=extracted_tags,
                    location_direction="NORTH"
                ))

        # Fallback Pattern 3: old {frame_1.2} format
        if not frames:
            old_pattern = r'\{frame_(\d+)\.(\d+)\}\s*\[PROMPT:\s*([^\]]+)\]'
            old_matches = re.findall(old_pattern, response, re.DOTALL)

            for match in old_matches:
                scene_n = int(match[0])
                frame_n = int(match[1])
                prompt_text = match[2].strip()

                extracted_tags = self._extract_tags_from_prompt_text(prompt_text, valid_tags)

                words = prompt_text.split()
                if len(words) > 150:
                    prompt_text = " ".join(words[:150])

                camera_id = f"{scene_n}.{frame_n}.cA"
                frames.append(FrameChunk(
                    frame_id=f"{scene_n}.{frame_n}",
                    scene_number=scene_n,
                    frame_number=frame_n,
                    original_text="",
                    camera_notation=f"[{camera_id}] (Wide)",
                    prompt=prompt_text,
                    cameras=[camera_id],
                    tags=extracted_tags,
                    location_direction="NORTH"
                ))

        # Final fallback: create from boundaries
        if not frames and boundaries:
            logger.warning(f"No frames parsed for scene {scene_num}, creating from {len(boundaries)} boundaries")
            for boundary in boundaries:
                camera_id = f"{scene_num}.{boundary.frame_number}.cA"
                prompt_text = boundary.captures if boundary.captures else f"Frame {boundary.frame_number}"
                extracted_tags = self._extract_tags_from_prompt_text(prompt_text, valid_tags)

                frames.append(FrameChunk(
                    frame_id=f"{scene_num}.{boundary.frame_number}",
                    scene_number=scene_num,
                    frame_number=boundary.frame_number,
                    original_text="",
                    camera_notation=f"[{camera_id}] (Frame)",
                    prompt=prompt_text,
                    cameras=[camera_id],
                    tags=extracted_tags,
                    location_direction="NORTH"
                ))

        logger.info(f"Parsed {len(frames)} frames for scene {scene_num}")
        return frames

    def _extract_tags_from_line(self, tags_line: str, valid_tags: set) -> Dict[str, List[str]]:
        """Extract and categorize tags from a TAGS: line.

        Args:
            tags_line: The content after "TAGS:" (e.g., "[CHAR_MEI], [LOC_PALACE], [PROP_SWORD]")
            valid_tags: Set of valid tags from world_config

        Returns:
            Dict with categorized tags: {"characters": [], "locations": [], "props": []}
        """
        from greenlight.tags.tag_parser import extract_categorized_tags
        return extract_categorized_tags(tags_line, valid_tags)

    def _extract_tags_from_prompt_text(self, prompt: str, valid_tags: set) -> Dict[str, List[str]]:
        """Extract tags from prompt text (fallback when no explicit TAGS line).

        Args:
            prompt: The prompt text to search for tags
            valid_tags: Set of valid tags from world_config

        Returns:
            Dict with categorized tags: {"characters": [], "locations": [], "props": []}
        """
        from greenlight.tags.tag_parser import extract_categorized_tags
        return extract_categorized_tags(prompt, valid_tags)

    # =========================================================================
    # STEP 3: PARALLEL NOTATION INSERTION
    # =========================================================================

    async def _add_notations_parallel(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance frames with position notations and cross-scene continuity.

        NOTE: Shot type, camera angle, and lighting are already determined in
        _determine_frame_points and _insert_frame_prompts. This step only adds:
        1. Character position notations (screen-left, screen-right, etc.)
        2. Cross-scene continuity tracking
        3. Depth of field guidance
        """
        logger.info("Step 3: Adding position notations and continuity tracking...")

        processed_scenes = data["processed_scenes"]
        world_config = data.get("world_config", {})

        # Cross-scene continuity tracking
        scene_continuity = {
            "last_scene_end_positions": {},  # Character positions at end of last scene
            "established_palette": None,  # Color palette from first scene
            "time_of_day_progression": [],  # Track time changes
            "last_location": None,  # For transition awareness
        }

        for scene_idx, scene in enumerate(processed_scenes):
            is_first_scene = (scene_idx == 0)
            is_last_scene = (scene_idx == len(processed_scenes) - 1)
            prev_scene = processed_scenes[scene_idx - 1] if scene_idx > 0 else None

            # Detect scene transitions
            transition_type = self._detect_scene_transition(scene, prev_scene, world_config)

            for frame_idx, frame in enumerate(scene.frames):
                is_first_frame = (frame_idx == 0)
                is_last_frame = (frame_idx == len(scene.frames) - 1)

                # Enhance frame with position notation if missing
                if not frame.position_notation or frame.position_notation == "[POS: Center frame]":
                    frame.position_notation = self._generate_position_notation(
                        frame, scene_continuity, is_first_frame
                    )

                # Add depth of field guidance based on shot type
                if "[DOF:" not in frame.prompt:
                    dof_guidance = self._get_depth_of_field_guidance(frame)
                    if dof_guidance:
                        frame.prompt = f"{frame.prompt} {dof_guidance}"

                # Track positions for continuity (last frame of scene)
                if is_last_frame:
                    self._update_scene_continuity(frame, scene_continuity)

                # Add transition guidance for first frame of new scene
                if is_first_frame and transition_type and not is_first_scene:
                    transition_note = f"[TRANSITION: {transition_type}] "
                    if transition_note not in frame.prompt:
                        frame.prompt = transition_note + frame.prompt

        data["processed_scenes"] = processed_scenes
        logger.info(f"Enhanced {sum(len(s.frames) for s in processed_scenes)} frames with continuity tracking")

        return data

    def _detect_scene_transition(
        self,
        current_scene: ProcessedScene,
        prev_scene: Optional[ProcessedScene],
        world_config: Dict[str, Any]
    ) -> Optional[str]:
        """Detect the type of transition between scenes."""
        if not prev_scene:
            return None

        # Extract location tags from scenes
        current_loc = None
        prev_loc = None

        for frame in current_scene.frames[:1]:  # First frame
            for loc in frame.tags.get("locations", []):
                current_loc = loc
                break

        for frame in prev_scene.frames[-1:]:  # Last frame
            for loc in frame.tags.get("locations", []):
                prev_loc = loc
                break

        if current_loc and prev_loc:
            if current_loc != prev_loc:
                # Location change
                curr_is_interior = "INTERIOR" in current_loc or "ROOM" in current_loc or "HOUSE" in current_loc
                prev_is_interior = "INTERIOR" in prev_loc or "ROOM" in prev_loc or "HOUSE" in prev_loc

                if curr_is_interior and not prev_is_interior:
                    return "Exterior to Interior - adjust lighting for enclosed space"
                elif not curr_is_interior and prev_is_interior:
                    return "Interior to Exterior - adjust for natural daylight"
                else:
                    return "Location change - establish new geography"

        return None

    def _generate_position_notation(
        self,
        frame: FrameChunk,
        continuity: Dict[str, Any],
        is_first_frame: bool
    ) -> str:
        """Generate position notation with continuity awareness."""
        chars = frame.tags.get("characters", [])

        if not chars:
            return "[POS: No characters - environmental shot]"

        positions = []
        established_positions = continuity.get("last_scene_end_positions", {})

        for i, char in enumerate(chars):
            if char in established_positions and not is_first_frame:
                # Maintain established position
                pos = established_positions[char]
                positions.append(f"{char} {pos} (maintaining)")
            else:
                # Assign new position based on character index
                if len(chars) == 1:
                    positions.append(f"{char} center-frame")
                elif i == 0:
                    positions.append(f"{char} screen-left")
                else:
                    positions.append(f"{char} screen-right")

        return f"[POS: {', '.join(positions)}]"

    def _get_depth_of_field_guidance(self, frame: FrameChunk) -> str:
        """Generate depth of field guidance based on shot type."""
        shot_type = ""
        if frame.camera_notation:
            match = re.search(r'\(([^)]+)\)', frame.camera_notation)
            if match:
                shot_type = match.group(1).lower()

        # Extract beat type if present
        beat = ""
        beat_match = re.search(r'\[BEAT:\s*([^\]]+)\]', frame.prompt)
        if beat_match:
            beat = beat_match.group(1).lower()

        # DOF guidance based on shot type and beat
        if "extreme close" in shot_type or "ecu" in shot_type:
            return "[DOF: Extremely shallow - only eyes/detail in focus, everything else bokeh]"
        elif "close" in shot_type:
            return "[DOF: Shallow depth of field - face sharp, background soft bokeh]"
        elif "intimacy" in beat or "emotional" in beat:
            return "[DOF: Shallow - subject isolated from background with gentle bokeh]"
        elif "wide" in shot_type or "establishing" in shot_type:
            return "[DOF: Deep focus - entire scene sharp from foreground to background]"
        elif "medium" in shot_type:
            return "[DOF: Moderate depth - subject and immediate surroundings in focus]"
        elif "ots" in shot_type or "over-the-shoulder" in shot_type:
            return "[DOF: Shallow - foreground shoulder soft, background subject sharp]"

        return ""

    def _update_scene_continuity(
        self,
        frame: FrameChunk,
        continuity: Dict[str, Any]
    ) -> None:
        """Update continuity tracking from the last frame of a scene."""
        # Extract character positions from position notation
        if frame.position_notation:
            for char in frame.tags.get("characters", []):
                if "screen-left" in frame.position_notation and char in frame.position_notation:
                    continuity["last_scene_end_positions"][char] = "screen-left"
                elif "screen-right" in frame.position_notation and char in frame.position_notation:
                    continuity["last_scene_end_positions"][char] = "screen-right"
                elif "center" in frame.position_notation:
                    continuity["last_scene_end_positions"][char] = "center"

        # Track location
        if frame.tags.get("locations"):
            continuity["last_location"] = frame.tags["locations"][0]

    # =========================================================================
    # STEP 4: ASSEMBLE VISUAL SCRIPT
    # =========================================================================

    async def _assemble_visual_script(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> VisualScriptOutput:
        """Assemble the final Visual_Script output."""
        logger.info("Step 4: Assembling Visual_Script...")

        processed_scenes = data["processed_scenes"]

        # Get all tags from world_config for tag extraction
        world_config = data.get("world_config", {})
        all_tags = world_config.get("all_tags", [])

        # If all_tags not available, build from characters, locations, props
        if not all_tags:
            for char in world_config.get("characters", []):
                if char.get("tag"):
                    all_tags.append(char["tag"])
            for loc in world_config.get("locations", []):
                if loc.get("tag"):
                    all_tags.append(loc["tag"])
            for prop in world_config.get("props", []):
                if prop.get("tag"):
                    all_tags.append(prop["tag"])

        # Build the visual script with two-tier descriptions
        script_parts = []
        total_frames = 0

        for scene in processed_scenes:
            script_parts.append(f"\n--- SCENE {scene.scene_number} ---\n")

            # Add each frame with its notations using scene.frame.camera format
            for frame in scene.frames:
                total_frames += 1

                # Extract tags from prompt for reference image lookup
                if all_tags:
                    frame.extract_tags_from_prompt(all_tags)
                    if frame.tags.get("characters") or frame.tags.get("locations") or frame.tags.get("props"):
                        logger.debug(f"Frame {frame.frame_id} tags: {frame.tags}")

                # Use primary camera ID in scene.frame.camera format
                camera_id = frame.primary_camera_id  # e.g., "1.2.cA"

                # Build tags string for display
                tags_list = []
                for char in frame.tags.get("characters", []):
                    tags_list.append(f"[{char}]")
                for loc in frame.tags.get("locations", []):
                    tags_list.append(f"[{loc}]")
                for prop in frame.tags.get("props", []):
                    tags_list.append(f"[{prop}]")
                tags_str = ", ".join(tags_list) if tags_list else ""

                # Build frame block with rich visual storytelling
                frame_block = f"""
(/scene_frame_chunk_start/)

[{camera_id}] {frame.camera_notation}
TAGS: {tags_str}
LOCATION_DIRECTION: {frame.location_direction}
BEAT: {frame.beat if frame.beat else ""}

**VISUAL DESCRIPTION:**
{frame.visual_description if frame.visual_description else frame.prompt}

**PROMPT:** {frame.prompt}

(/scene_frame_chunk_end/)
"""
                script_parts.append(frame_block)

            # Add the marked scene text
            script_parts.append(f"\n{scene.marked_text}\n")

        visual_script = "\n".join(script_parts)

        logger.info(f"Visual_Script assembled: {len(processed_scenes)} scenes, {total_frames} frames")

        return VisualScriptOutput(
            visual_script=visual_script,
            scenes=processed_scenes,
            total_frames=total_frames,
            metadata={
                "media_type": data.get("media_type", "standard"),
                "visual_style": data.get("visual_style", ""),
                "style_notes": data.get("style_notes", ""),
            }
        )

    # =========================================================================
    # STEP 5: FRAME VALIDATION AGENT
    # =========================================================================

    async def _validate_frames(
        self,
        visual_output: VisualScriptOutput,
        context: Dict[str, Any]
    ) -> VisualScriptOutput:
        """Validate and refine frames using Claude Sonnet 4.5.

        This step performs:
        1. Tag extraction & validation - ensures all tags follow notation standards
        2. Multi-subject frame detection - identifies frames with multiple viewpoints
        3. Frame splitting - splits multi-subject frames into appropriate camera angles
        4. Prompt rewriting - rewrites prompts to describe single camera viewpoints
        5. Prompt quality validation - time consistency, physical reality, composition
        6. Cinematic consistency validation - 180° rule, shot rhythm, cross-scene continuity

        Uses Claude Sonnet 4.5 (hardcoded) for consistent quality.
        """
        logger.info("Step 5: Validating and refining frames...")

        # Import validators
        from greenlight.pipelines.early_validation import (
            PromptQualityValidator,
            ValidationSeverity,
            CinematicConsistencyValidator
        )

        # First pass: Prompt quality validation (pre-LLM)
        world_config = context.get("world_config", {})
        prompt_validator = PromptQualityValidator(world_config)

        quality_issues_found = 0
        quality_fixes_applied = 0

        for scene in visual_output.scenes:
            # Extract scene metadata (time of day, etc.)
            scene_metadata = self._extract_scene_metadata(scene, context)

            for frame in scene.frames:
                # Validate prompt quality
                quality_result = prompt_validator.validate_prompt(
                    prompt=frame.prompt,
                    frame_id=frame.primary_camera_id,
                    scene_metadata=scene_metadata,
                    lighting_notation=frame.lighting_notation
                )

                if quality_result.issues:
                    quality_issues_found += len(quality_result.issues)
                    for issue in quality_result.issues:
                        if issue.severity == ValidationSeverity.ERROR:
                            logger.warning(f"Frame {frame.primary_camera_id}: {issue.code} - {issue.message}")
                        else:
                            logger.info(f"Frame {frame.primary_camera_id}: {issue.code} - {issue.message}")

                    # Auto-fix if possible
                    fixable = [i for i in quality_result.issues if i.auto_fixable]
                    if fixable:
                        frame.prompt = prompt_validator.auto_fix_prompt(
                            frame.prompt,
                            fixable,
                            scene_metadata
                        )
                        quality_fixes_applied += len(fixable)
                        logger.info(f"Auto-fixed {len(fixable)} issues in frame {frame.primary_camera_id}")

        if quality_issues_found > 0:
            logger.info(f"Prompt quality check: {quality_issues_found} issues found, {quality_fixes_applied} auto-fixed")

        # Import here to avoid circular imports
        from greenlight.llm.api_clients import AnthropicClient

        # Get world config for tag context
        world_config = context.get("world_config", {})
        all_tags = world_config.get("all_tags", [])

        # Build tag context from world config if not available
        if not all_tags:
            for char in world_config.get("characters", []):
                if char.get("tag"):
                    all_tags.append(char["tag"])
            for loc in world_config.get("locations", []):
                if loc.get("tag"):
                    all_tags.append(loc["tag"])
            for prop in world_config.get("props", []):
                if prop.get("tag"):
                    all_tags.append(prop["tag"])

        # Process each scene's frames
        validated_scenes = []
        total_new_frames = 0

        for scene in visual_output.scenes:
            validated_frames = []

            for frame in scene.frames:
                # Validate and potentially split this frame
                result_frames = await self._validate_single_frame(
                    frame=frame,
                    scene_number=scene.scene_number,
                    all_tags=all_tags,
                    world_config=world_config
                )
                validated_frames.extend(result_frames)

            # Update scene with validated frames
            scene.frames = validated_frames
            scene.frame_count = len(validated_frames)
            total_new_frames += len(validated_frames)
            validated_scenes.append(scene)

        # Update output with validated frames
        visual_output.scenes = validated_scenes
        visual_output.total_frames = total_new_frames

        logger.info(f"LLM frame validation complete: {total_new_frames} frames after validation")

        # =====================================================================
        # CINEMATIC CONSISTENCY VALIDATION (POST-GENERATION)
        # Validates 180° rule, shot rhythm, and cross-scene continuity
        # =====================================================================
        logger.info("Running cinematic consistency validation...")

        cinematic_validator = CinematicConsistencyValidator()
        total_cinematic_issues = 0
        total_cinematic_fixes = 0

        for scene_idx, scene in enumerate(visual_output.scenes):
            # Convert FrameChunk objects to dicts for validator
            frame_dicts = []
            for frame in scene.frames:
                # Extract shot type from camera_notation
                shot_type = "medium"
                if frame.camera_notation:
                    import re as _re
                    shot_match = _re.search(r'\(([^)]+)\)', frame.camera_notation)
                    if shot_match:
                        shot_type = shot_match.group(1).strip()

                frame_dicts.append({
                    "frame_id": frame.primary_camera_id,
                    "prompt": frame.prompt,
                    "shot_type": shot_type,
                    "tags": frame.tags,
                    "camera_notation": frame.camera_notation,
                    "position_notation": frame.position_notation,
                    "lighting_notation": frame.lighting_notation,
                    "location_direction": frame.location_direction
                })

            # Validate frame sequence for this scene
            fixed_frame_dicts, issues = cinematic_validator.validate_frame_sequence(
                frames=frame_dicts,
                scene_number=scene.scene_number,
                auto_fix=True
            )

            # Log issues found
            for issue in issues:
                if issue.severity == ValidationSeverity.ERROR:
                    logger.warning(f"Scene {scene.scene_number}: {issue.code} - {issue.message}")
                else:
                    logger.info(f"Scene {scene.scene_number}: {issue.code} - {issue.message}")

            total_cinematic_issues += len(issues)

            # Apply fixes back to FrameChunk objects
            for i, fixed_dict in enumerate(fixed_frame_dicts):
                if i < len(scene.frames):
                    # Update prompt if it was fixed
                    if fixed_dict.get("prompt") != scene.frames[i].prompt:
                        scene.frames[i].prompt = fixed_dict["prompt"]
                        total_cinematic_fixes += 1

            # Note: cinematic_validator preserves character positions for cross-scene continuity
            # The next scene will automatically inherit positions from this one

        if total_cinematic_issues > 0:
            logger.info(
                f"Cinematic consistency check: {total_cinematic_issues} issues found, "
                f"{total_cinematic_fixes} auto-fixed"
            )
        else:
            logger.info("Cinematic consistency check: No issues found")

        logger.info(f"Frame validation complete: {total_new_frames} frames validated")

        return visual_output

    async def _validate_single_frame(
        self,
        frame: FrameChunk,
        scene_number: int,
        all_tags: List[str],
        world_config: Dict[str, Any]
    ) -> List[FrameChunk]:
        """Validate a single frame and split if needed.

        Returns a list of frames (1 if no split needed, multiple if split).
        """
        from greenlight.llm.api_clients import AnthropicClient
        from greenlight.core.config import get_config

        # Build the validation prompt
        system_prompt = self._build_frame_validation_system_prompt(all_tags, world_config)
        user_prompt = self._build_frame_validation_user_prompt(frame, scene_number)

        try:
            # Get model from config (defaults to claude-haiku-4.5 if not specified)
            config = get_config()
            specialized_models = config.raw_config.get("specialized_models", {})
            frame_validation_config = specialized_models.get("frame_validation", {})
            model = frame_validation_config.get("model", "claude-haiku-4-5-20251001")

            client = AnthropicClient()
            response = client.generate_text(
                prompt=user_prompt,
                system=system_prompt,
                model=model,
                max_tokens=4096
            )

            # Parse the response
            result = self._parse_frame_validation_response(
                response.text,
                frame,
                scene_number
            )

            return result

        except Exception as e:
            logger.warning(f"Frame validation failed for {frame.frame_id}: {e}")
            # Return original frame if validation fails
            return [frame]

    def _build_frame_validation_system_prompt(
        self,
        all_tags: List[str],
        world_config: Dict[str, Any]
    ) -> str:
        """Build the system prompt for frame validation."""

        # Get tag naming rules from AgentPromptLibrary
        tag_rules = AgentPromptLibrary.TAG_NAMING_RULES

        # Build character/location context
        char_context = []
        for char in world_config.get("characters", []):
            tag = char.get("tag", "")
            name = char.get("name", "")
            if tag and name:
                char_context.append(f"- [{tag}]: {name}")

        loc_context = []
        for loc in world_config.get("locations", []):
            tag = loc.get("tag", "")
            name = loc.get("name", "")
            if tag and name:
                loc_context.append(f"- [{tag}]: {name}")

        prop_context = []
        for prop in world_config.get("props", []):
            tag = prop.get("tag", "")
            name = prop.get("name", "")
            if tag and name:
                prop_context.append(f"- [{tag}]: {name}")

        return f"""You are a Frame Validation Agent for a visual storytelling system.

{tag_rules}

## SCENE.FRAME.CAMERA NOTATION

The canonical format is: {{scene}}.{{frame}}.c{{letter}}
- Scene: Integer (1, 2, 3...)
- Frame: Integer (1, 2, 3...)
- Camera: Letter prefixed with 'c' (cA, cB, cC...)

Examples: 1.1.cA, 2.3.cB, 3.5.cC

## AVAILABLE TAGS IN THIS PROJECT

### Characters:
{chr(10).join(char_context) if char_context else "No characters defined"}

### Locations:
{chr(10).join(loc_context) if loc_context else "No locations defined"}

### Props:
{chr(10).join(prop_context) if prop_context else "No props defined"}

## YOUR RESPONSIBILITIES

1. **Tag Extraction & Validation**
   - Identify all tags present in the frame prompt
   - Ensure tags follow the notation standards (prefix + uppercase + underscores)
   - Flag any malformed or missing tags

2. **CROSS-CUTTING DETECTION (PRIORITY)**
   Detect when one character OBSERVES another - these need multi-camera treatment:

   ### OBSERVATION PATTERNS (ALWAYS SPLIT):
   - "X watches/observes/sees Y" → Split into: Y doing action (cA), X watching (cB), POV of what X sees (cC)
   - "From X's perspective" or "X's POV" → Dedicated POV camera
   - "X peering/spying/looking at Y" → Observer close-up + observed subject
   - "While X [does action], Y [reacts]" → Parallel cameras for each subject

   ### VISUAL POETRY FRAGMENTATION (ALWAYS SPLIT):
   When a prompt describes multiple visual details that should be isolated shots:
   - "Light falls on floor AND on character's feet" → Separate detail shots (floor, feet)
   - "Hand touches curtain, revealing view below" → Hand detail + POV through window
   - "Character's face AND their hands doing action" → Face close-up + hand detail

3. **Multi-Subject Frame Detection**
   - Identify if the frame describes multiple distinct viewpoints that cannot be captured by a single camera
   - A frame needs splitting when it describes what multiple cameras would see
   - Single-subject frames showing one perspective do NOT need splitting

   ### SPATIAL IMPOSSIBILITY DETECTION
   - Subjects in different rooms, buildings, or separated by walls/barriers
   - Subjects on different floors or elevation levels (looking down from window to street below)
   - Subjects separated by significant distance (across a street, opposite ends of a large space)
   - When the description mentions "meanwhile" or "at the same time" for different locations

   ### PERSPECTIVE CONFLICTS
   - Close-up emotional reactions combined with wide establishing shots in the same description
   - Descriptions requiring both front-facing and back-facing views of subjects
   - Descriptions mixing macro detail (hands, eyes, feet) with full-body or environmental framing
   - When the narrative focus shifts between subjects who cannot be framed together

4. **Frame Splitting Decision**
   - If splitting is needed, determine appropriate camera angles (cA, cB, cC, etc.)
   - Each split frame should describe what is visible from ONE camera position
   - Maintain scene continuity across split frames

   ### SPLITTING PATTERNS:
   | Pattern | Split Into |
   |---------|------------|
   | Observer + Observed | cA: Subject action, cB: Observer face, cC: POV detail |
   | Detail progression | cA: First detail, cB: Second detail, cC: Context |
   | Cross-cutting dialogue | cA: Speaker, cB: Listener reaction |
   | POV + Reaction | cA: What character sees, cB: Character's face responding |

   ### WHEN NOT TO SPLIT
   - Subjects are close enough to frame together naturally
   - A single camera angle can capture all described action
   - Wide shots that intentionally show spatial relationships between subjects
   - Simple single-subject detail shots

5. **Prompt Rewriting - KEEP CONCISE**
   - Rewrite prompts to describe single camera viewpoints
   - Keep rewritten prompts UNDER 50 WORDS
   - Each prompt describes what ONE camera literally sees
   - Preserve all relevant tags in the rewritten prompts

   ### CONCISE STYLE EXAMPLES:
   - "Close up of [CHAR_MEI]'s bare feet on wooden floor, golden light strips"
   - "View through parted curtains showing [CHAR_LIN]'s flower shop below, spying perspective"
   - "[CHAR_LIN] bent over clay pots with gardening tools, wide angle"

## OUTPUT FORMAT

Respond with valid JSON:
```json
{{
  "needs_split": true/false,
  "validation_notes": "Brief explanation of validation findings",
  "extracted_tags": ["TAG_1", "TAG_2"],
  "frames": [
    {{
      "camera_suffix": "cA",
      "prompt": "Rewritten prompt for this camera angle",
      "tags": ["TAG_1", "TAG_2"],
      "location_direction": "NORTH"
    }}
  ]
}}
```

**location_direction** indicates which direction the camera is facing within the location:
- NORTH: Default/establishing view (main entrance perspective)
- EAST: Camera facing east within the location
- SOUTH: Camera facing south within the location
- WEST: Camera facing west within the location

If no split is needed, return a single frame in the "frames" array with the validated/corrected prompt.
"""

    def _build_frame_validation_user_prompt(
        self,
        frame: FrameChunk,
        scene_number: int
    ) -> str:
        """Build the user prompt for frame validation."""
        # Get current tags as formatted string
        current_tags = []
        if frame.tags:
            current_tags.extend(frame.tags.get("characters", []))
            current_tags.extend(frame.tags.get("locations", []))
            current_tags.extend(frame.tags.get("props", []))
        tags_str = ", ".join([f"[{t}]" for t in current_tags]) if current_tags else "(none extracted)"

        return f"""Validate and analyze this frame:

**Frame ID:** {frame.frame_id}
**Scene:** {scene_number}
**Current Camera:** {frame.primary_camera_id}

**Camera Notation:** {frame.camera_notation}
**Position Notation:** {frame.position_notation}
**Lighting Notation:** {frame.lighting_notation}
**Current Tags:** {tags_str}
**Location Direction:** {frame.location_direction}

**Prompt:**
{frame.prompt}

Analyze this frame for:
1. Are all tags properly formatted? Verify against the prompt content.
2. Does this frame describe multiple distinct viewpoints that should be split?
3. If splitting, what camera angles are needed? Assign appropriate location_direction to each.
4. Provide validated/rewritten prompt(s) with correct tags and location_direction.

Respond with JSON only."""

    def _parse_frame_validation_response(
        self,
        response_text: str,
        original_frame: FrameChunk,
        scene_number: int
    ) -> List[FrameChunk]:
        """Parse the validation response and create frame(s)."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                logger.warning("No JSON found in validation response")
                return [original_frame]

            data = json.loads(json_match.group())

            frames_data = data.get("frames", [])
            if not frames_data:
                return [original_frame]

            result_frames = []
            base_frame_num = original_frame.frame_number

            for i, frame_data in enumerate(frames_data):
                camera_suffix = frame_data.get("camera_suffix", f"c{chr(65 + i)}")
                new_prompt = frame_data.get("prompt", original_frame.prompt)
                tags = frame_data.get("tags", [])
                # Preserve location_direction from original frame or use from validation data
                location_direction = frame_data.get("location_direction", original_frame.location_direction)

                # Create new frame
                new_frame = FrameChunk(
                    frame_id=f"{scene_number}.{base_frame_num}",
                    scene_number=scene_number,
                    frame_number=base_frame_num,
                    original_text=original_frame.original_text,
                    camera_notation=f"[{scene_number}.{base_frame_num}.{camera_suffix}]",
                    position_notation=original_frame.position_notation,
                    lighting_notation=original_frame.lighting_notation,
                    prompt=new_prompt,
                    cameras=[f"{scene_number}.{base_frame_num}.{camera_suffix}"],
                    tags={
                        "characters": [t for t in tags if t.startswith("CHAR_")],
                        "locations": [t for t in tags if t.startswith("LOC_")],
                        "props": [t for t in tags if t.startswith("PROP_")],
                    },
                    location_direction=location_direction
                )
                result_frames.append(new_frame)

            # Log if frame was split
            if len(result_frames) > 1:
                logger.info(
                    f"Frame {original_frame.frame_id} split into {len(result_frames)} cameras: "
                    f"{[f.primary_camera_id for f in result_frames]}"
                )

            return result_frames

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse validation JSON: {e}")
            return [original_frame]
        except Exception as e:
            logger.warning(f"Error parsing validation response: {e}")
            return [original_frame]

    def _extract_scene_metadata_from_text(self, text: str) -> Dict[str, Any]:
        """Extract scene metadata from raw text for context aggregation.

        Used during prompt generation to initialize scene context.
        Enhanced to better capture scene heading, time, location, and atmosphere.

        Returns:
            Dict with: time, location_tag, weather, atmosphere, characters, scene_heading
        """
        metadata = {
            "time": "",
            "location_tag": "",
            "weather": "",
            "atmosphere": "",
            "characters": [],
            "scene_heading": "",
            "lighting_hint": ""
        }

        text_lower = text.lower()

        # Extract scene heading (first line after ## Scene X:)
        heading_match = re.search(r'^## Scene \d+:?\s*\n(.+?)(?:\n\n|\n[A-Z\[])', text, re.MULTILINE)
        if heading_match:
            metadata["scene_heading"] = heading_match.group(1).strip()
            # Check heading for time indicators
            heading_lower = metadata["scene_heading"].lower()
            for time_phrase in ["late evening", "early morning", "late afternoon", "early evening",
                                "late night", "early night", "mid-morning", "mid-afternoon"]:
                if time_phrase in heading_lower:
                    metadata["time"] = time_phrase
                    break

        # Extract time of day (priority order - explicit first, then contextual)
        time_patterns = [
            (r'\*\*time:\*\*\s*([^\n*]+)', 1),
            (r'time:\s*([^\n]+)', 1),
            # Look in scene heading explicitly
            (r'## Scene \d+:?\s*\n[^\n]*\b(late evening|early morning|late afternoon|evening|morning|night|afternoon|dawn|dusk)\b', 1),
            # Then general text
            (r'\b(dawn|sunrise|early morning)\b', 0),
            (r'\b(morning|mid-morning)\b', 0),
            (r'\b(noon|midday|high noon)\b', 0),
            (r'\b(afternoon|late afternoon)\b', 0),
            (r'\b(dusk|sunset|golden hour|twilight)\b', 0),
            (r'\b(evening|early evening|late evening)\b', 0),
            (r'\b(night|midnight|late night)\b', 0),
        ]

        if not metadata["time"]:  # Only if not already set from heading
            for pattern, group in time_patterns:
                match = re.search(pattern, text_lower if group == 0 else text, re.IGNORECASE)
                if match:
                    metadata["time"] = match.group(group).strip() if group else match.group(0)
                    break

        # Extract ALL location tags (first one is primary)
        loc_matches = re.findall(r'\[(LOC_[A-Z0-9_]+(?:_DIR_[NSEW])?)\]', text)
        if loc_matches:
            # Use first location as primary, strip direction suffix for tag
            primary_loc = loc_matches[0]
            # Handle LOC_X_DIR_W format
            base_loc = re.sub(r'_DIR_[NSEW]$', '', primary_loc)
            metadata["location_tag"] = base_loc
            # Check for explicit direction in tag
            dir_match = re.search(r'_DIR_([NSEW])$', primary_loc)
            if dir_match:
                metadata["location_direction"] = dir_match.group(1)

        # Extract ALL character tags (preserve order of appearance)
        char_matches = re.findall(r'\[(CHAR_[A-Z_]+)\]', text)
        # Deduplicate while preserving order
        seen = set()
        metadata["characters"] = []
        for c in char_matches:
            if c not in seen:
                seen.add(c)
                metadata["characters"].append(c)

        # Extract weather (more comprehensive)
        weather_patterns = [
            (r'rain(?:ing|y)?', 'rainy'),
            (r'storm(?:ing|y)?', 'stormy'),
            (r'fog(?:gy)?', 'foggy'),
            (r'mist(?:y)?', 'misty'),
            (r'snow(?:ing|y)?', 'snowy'),
            (r'cloud(?:y|s)', 'cloudy'),
            (r'sunn(?:y|shine)', 'sunny'),
            (r'overcast', 'overcast'),
            (r'clear\s*(?:sky|weather|day|night)', 'clear'),
        ]
        for pattern, weather in weather_patterns:
            if re.search(pattern, text_lower):
                metadata["weather"] = weather
                break

        # Extract atmosphere/mood (enhanced)
        atmosphere_patterns = [
            (r'tense|tension|anxious', 'tense'),
            (r'peaceful|serene|calm|quiet', 'peaceful'),
            (r'chaotic|frantic|frenzied', 'chaotic'),
            (r'ominous|foreboding|threatening', 'ominous'),
            (r'romantic|intimate|loving', 'romantic'),
            (r'melanchol(?:ic|y)|sad|sorrowful', 'melancholic'),
            (r'hopeful|optimistic', 'hopeful'),
            (r'mysterious|enigmatic', 'mysterious'),
            (r'warm|cozy|comfort', 'warm'),
            (r'cold|chilling|bleak', 'cold'),
        ]
        for pattern, atmosphere in atmosphere_patterns:
            if re.search(pattern, text_lower):
                metadata["atmosphere"] = atmosphere
                break

        # Extract lighting hints from text
        lighting_patterns = [
            (r'oil lamp', 'oil lamp light'),
            (r'lantern', 'lantern light'),
            (r'candle', 'candlelight'),
            (r'firelight|fire\s*light', 'firelight'),
            (r'moonlight|moon\s*light', 'moonlight'),
            (r'sunlight|sun\s*light', 'sunlight'),
            (r'golden light|golden sun', 'golden light'),
            (r'afternoon light|afternoon sun', 'afternoon light'),
            (r'morning light|morning sun', 'morning light'),
            (r'shadows? danc', 'dancing shadows'),
            (r'dim(?:ly)?\s*lit', 'dim lighting'),
            (r'bright(?:ly)?\s*lit', 'bright lighting'),
        ]
        lighting_hints = []
        for pattern, hint in lighting_patterns:
            if re.search(pattern, text_lower):
                lighting_hints.append(hint)
        if lighting_hints:
            metadata["lighting_hint"] = ", ".join(lighting_hints[:3])  # Max 3 hints

        return metadata

    def _extract_scene_metadata(
        self,
        scene: ProcessedScene,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract metadata from a scene for validation purposes.

        Parses the scene's original text to extract:
        - Time of day (morning, afternoon, evening, night, etc.)
        - Location
        - Weather/atmosphere
        - Any explicit lighting notes

        Returns:
            Dict with extracted metadata
        """
        metadata = {
            "time": "",
            "location": "",
            "weather": "",
            "atmosphere": ""
        }

        text = scene.original_text.lower()

        # Extract time of day from scene header or content
        time_patterns = [
            (r'\*\*time:\*\*\s*([^\n*]+)', 1),  # **Time:** format
            (r'time:\s*([^\n]+)', 1),  # Time: format
            (r'\b(dawn|sunrise|early morning)\b', 0),
            (r'\b(morning|mid-morning)\b', 0),
            (r'\b(noon|midday|high noon)\b', 0),
            (r'\b(afternoon|late afternoon)\b', 0),
            (r'\b(dusk|sunset|golden hour|twilight)\b', 0),
            (r'\b(evening|early evening)\b', 0),
            (r'\b(night|midnight|late night)\b', 0),
        ]

        for pattern, group in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["time"] = match.group(group).strip() if group else match.group(0)
                break

        # Extract location from scene header
        loc_patterns = [
            (r'\*\*location:\*\*\s*([^\n*]+)', 1),
            (r'location:\s*([^\n]+)', 1),
            (r'\[LOC_([A-Z_]+)\]', 1),
        ]

        for pattern, group in loc_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["location"] = match.group(group).strip()
                break

        # Extract weather/atmosphere keywords
        weather_keywords = ["rain", "storm", "fog", "mist", "snow", "cloudy", "sunny", "overcast"]
        for keyword in weather_keywords:
            if keyword in text:
                metadata["weather"] = keyword
                break

        atmosphere_keywords = ["tense", "peaceful", "chaotic", "serene", "ominous", "romantic"]
        for keyword in atmosphere_keywords:
            if keyword in text:
                metadata["atmosphere"] = keyword
                break

        return metadata

