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
    """
    frame_id: str  # e.g., "1.2" (scene.frame format)
    scene_number: int
    frame_number: int
    original_text: str
    camera_notation: str = ""  # e.g., "[1.2.cA] (Wide)"
    position_notation: str = ""
    lighting_notation: str = ""
    prompt: str = ""  # 250 word max
    cameras: List[str] = field(default_factory=list)  # List of camera IDs: ["1.2.cA", "1.2.cB"]
    # Extracted tags for reference image lookup
    tags: Dict[str, List[str]] = field(default_factory=dict)  # {"characters": [], "locations": [], "props": []}
    # Location direction for directional reference image selection (NORTH, EAST, SOUTH, WEST)
    location_direction: str = "NORTH"

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
                            "prompt": frame.prompt,
                            "tags": frame.tags if frame.tags else {"characters": [], "locations": [], "props": []},
                            # Location direction for directional reference image selection
                            "location_direction": frame.location_direction if frame.location_direction else "NORTH",
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
        """Get frame count via 3-judge consensus.

        Frame count is determined autonomously based on scene content.
        No artificial limits - the LLM consensus determines optimal count.
        """
        prompt = f"""Determine the optimal frame count for this scene.

SCENE:
{scene_text}

SCENE NUMBER: {scene_num}
MEDIA TYPE: {data.get('media_type', 'standard')}

Consider:
- Key narrative moments that need visual capture
- Character moments requiring close-ups
- Establishing shots needed
- Transitions and movements
- Emotional turning points
- Scene complexity and pacing needs

Each frame should be:
- Visually distinct from others
- Narratively meaningful
- Worth the 250-word prompt investment

Respond with ONLY a number representing the optimal frame count for this scene."""

        # Run 3 judges in parallel
        tasks = [
            self.llm_caller(
                prompt=prompt,
                system_prompt="You are a director determining frame counts. Respond with only a number.",
                function=LLMFunction.STORY_ANALYSIS
            )
            for _ in range(3)
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Parse votes
        votes = []
        for resp in responses:
            if isinstance(resp, Exception):
                continue
            try:
                num = int(re.search(r'\d+', str(resp)).group())
                # Ensure at least 1 frame, no upper limit
                votes.append(max(1, num))
            except (ValueError, AttributeError):
                votes.append(4)  # Default

        if not votes:
            return 4  # Default frame count if all judges fail

        # Best of 3: most common, or median if all different
        from collections import Counter
        vote_counts = Counter(votes)
        most_common = vote_counts.most_common(1)[0]

        if most_common[1] >= 2:
            return most_common[0]
        else:
            return int(median(votes))

    async def _determine_frame_points(
        self,
        scene_text: str,
        frame_count: int,
        scene_num: int
    ) -> List[FrameBoundary]:
        """Determine frame boundaries with 2-iteration collaboration."""
        prompt_template = """Mark frame points for this scene.

SCENE:
{scene_text}

FRAME COUNT: {frame_count}

{other_proposals}

For each of the {frame_count} frames:
1. Identify the START point (quote the text where frame begins)
2. Identify the END point (quote the text where frame ends)
3. Describe what this frame captures

Output format:
FRAME 1:
  START: "exact text quote where frame 1 begins"
  END: "exact text quote where frame 1 ends"
  CAPTURES: what this frame shows

FRAME 2:
  START: "exact text quote"
  END: "exact text quote"
  CAPTURES: ...

Continue for all {frame_count} frames. Ensure frames are sequential and don't overlap."""

        # Iteration 1
        prompt1 = prompt_template.format(
            scene_text=scene_text,
            frame_count=frame_count,
            other_proposals=""
        )

        response1 = await self.llm_caller(
            prompt=prompt1,
            system_prompt="You are a collaborative frame marker identifying frame boundaries.",
            function=LLMFunction.STORY_ANALYSIS
        )

        # Iteration 2 with first response as context
        prompt2 = prompt_template.format(
            scene_text=scene_text,
            frame_count=frame_count,
            other_proposals=f"OTHER AGENT'S PROPOSALS:\n{response1}"
        )

        response2 = await self.llm_caller(
            prompt=prompt2,
            system_prompt="You are a collaborative frame marker refining frame boundaries.",
            function=LLMFunction.STORY_ANALYSIS
        )

        # Parse boundaries from response2 (refined version)
        return self._parse_frame_boundaries(response2, frame_count)

    def _parse_frame_boundaries(
        self,
        response: str,
        frame_count: int
    ) -> List[FrameBoundary]:
        """Parse frame boundaries from LLM response."""
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
        """Insert frame markers into scene text."""
        prompt = f"""Insert frame markers into this scene.

ORIGINAL SCENE:
{scene_text}

FRAME BOUNDARIES:
{self._format_boundaries(boundaries)}

SCENE NUMBER: {scene_num}

Insert the following markers using scene.frame.camera notation:
1. At each frame start:
   (/scene_frame_chunk_start/)
   [{scene_num}.FRAME_NUMBER.cA] (Shot Type)

2. At each frame end:
   (/scene_frame_chunk_end/)

Use frame IDs in scene.frame format: [{scene_num}.1.cA], [{scene_num}.2.cA], etc.
The notation is: [scene.frame.camera] where camera starts with cA.

Output the full scene text with all markers inserted.
Preserve ALL original text - only ADD markers."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a text markup agent inserting frame markers.",
            function=LLMFunction.STORY_GENERATION
        )

        return response

    def _format_boundaries(self, boundaries: List[FrameBoundary]) -> str:
        """Format boundaries for prompt."""
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
        """Insert visual prompts for each frame with explicit tag and location direction output."""
        world_config = data.get("world_config", {})
        visual_style = data.get("visual_style", "")

        # Format character tags with descriptions
        characters = world_config.get("characters", [])
        char_tags_section = "\n".join([
            f"  [{c.get('tag', '')}]: {c.get('visual_description', c.get('appearance', ''))}"
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

        prompt = f"""Write frame prompts for this marked scene with EXPLICIT TAG NOTATION.

MARKED SCENE:
{marked_text}

VISUAL STYLE:
{visual_style}

AVAILABLE TAGS (USE THESE EXACTLY IN YOUR PROMPTS):

CHARACTERS:
{char_tags_section if char_tags_section else "  (none)"}

LOCATIONS:
{loc_tags_section if loc_tags_section else "  (none)"}

PROPS:
{prop_tags_section if prop_tags_section else "  (none)"}

WORD CAP PER PROMPT: 250 words MAXIMUM

For each frame marker, output in this EXACT format:

[{scene_num}.1.cA] (Shot Type)
TAGS: [CHAR_X], [LOC_Y], [PROP_Z]
LOCATION_DIRECTION: NORTH
PROMPT: Your 250-word-max visual description using tags in brackets...

CRITICAL REQUIREMENTS:
1. Every character visible in the frame MUST use their [CHAR_TAG] notation in the PROMPT
2. The location MUST use its [LOC_TAG] notation in the PROMPT
3. Any visible props MUST use their [PROP_TAG] notation in the PROMPT
4. TAGS line: List ALL tags that appear in this frame (comma-separated, in brackets)
5. LOCATION_DIRECTION: Which direction the camera is facing within the location:
   - NORTH: Default/establishing view (main entrance perspective)
   - EAST: Camera facing east within the location
   - SOUTH: Camera facing south within the location
   - WEST: Camera facing west within the location
   Choose based on what's visible in the frame and camera position.
6. Only ONE location direction per frame (the primary camera orientation)

Example output:
[{scene_num}.1.cA] (Wide)
TAGS: [CHAR_MEI], [CHAR_MADAME_CHOU], [LOC_TEAHOUSE_INTERIOR], [PROP_TEA_SET]
LOCATION_DIRECTION: NORTH
PROMPT: Wide establishing shot of [LOC_TEAHOUSE_INTERIOR] from the north entrance. [CHAR_MEI] kneels in the center foreground, her silk robes pooling around her. [CHAR_MADAME_CHOU] stands in the doorway screen right, silhouetted against morning light. The [PROP_TEA_SET] rests on a low table between them...

Continue for all frames. Use cA as the primary camera for each frame."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a visual prompt writer for cinematic storyboarding. Always use explicit [TAG] notation for all characters, locations, and props.",
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

        # Primary pattern: New format with TAGS and LOCATION_DIRECTION
        # [1.2.cA] (Wide)
        # TAGS: [CHAR_X], [LOC_Y]
        # LOCATION_DIRECTION: NORTH
        # PROMPT: ...
        new_format_pattern = r'\[(\d+)\.(\d+)\.c([A-Z])\]\s*\(([^)]+)\)\s*(?:c[A-Z]\.\s*[A-Z\s]+\.\s*)?TAGS:\s*([^\n]+)\s*LOCATION_DIRECTION:\s*(NORTH|EAST|SOUTH|WEST)\s*PROMPT:\s*(.+?)(?=\[\d+\.\d+\.c[A-Z]\]|\(/scene_frame_chunk_end/\)|$)'
        new_matches = re.findall(new_format_pattern, response, re.DOTALL | re.IGNORECASE)

        if new_matches:
            for match in new_matches:
                scene_n = int(match[0])
                frame_n = int(match[1])
                camera_letter = match[2]
                shot_type = match[3].strip()
                tags_line = match[4].strip()
                location_direction = match[5].strip().upper()
                prompt_text = match[6].strip()

                # Parse tags from TAGS line
                extracted_tags = self._extract_tags_from_line(tags_line, valid_tags)

                # Clean up prompt text
                prompt_text = re.sub(r'\(/scene_frame_chunk_start/\).*', '', prompt_text, flags=re.DOTALL).strip()
                prompt_text = re.sub(r'\n\s*\n\s*\n', '\n\n', prompt_text)

                # Enforce 250 word cap
                words = prompt_text.split()
                if len(words) > 250:
                    prompt_text = " ".join(words[:250])

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
                if len(words) > 250:
                    prompt_text = " ".join(words[:250])

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
                if len(words) > 250:
                    prompt_text = " ".join(words[:250])

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
                if len(words) > 250:
                    prompt_text = " ".join(words[:250])

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
        result = {"characters": [], "locations": [], "props": []}

        # Find all bracketed tags
        tag_pattern = r'\[([A-Z]+_[A-Z0-9_]+)\]'
        found_tags = re.findall(tag_pattern, tags_line)

        for tag in found_tags:
            # Validate against world_config if available
            if valid_tags and tag not in valid_tags:
                continue

            if tag.startswith("CHAR_"):
                if tag not in result["characters"]:
                    result["characters"].append(tag)
            elif tag.startswith("LOC_"):
                if tag not in result["locations"]:
                    result["locations"].append(tag)
            elif tag.startswith("PROP_"):
                if tag not in result["props"]:
                    result["props"].append(tag)

        return result

    def _extract_tags_from_prompt_text(self, prompt: str, valid_tags: set) -> Dict[str, List[str]]:
        """Extract tags from prompt text (fallback when no explicit TAGS line).

        Args:
            prompt: The prompt text to search for tags
            valid_tags: Set of valid tags from world_config

        Returns:
            Dict with categorized tags: {"characters": [], "locations": [], "props": []}
        """
        result = {"characters": [], "locations": [], "props": []}

        # Find all bracketed tags in prompt
        tag_pattern = r'\[([A-Z]+_[A-Z0-9_]+)\]'
        found_tags = re.findall(tag_pattern, prompt)

        for tag in found_tags:
            if valid_tags and tag not in valid_tags:
                continue

            if tag.startswith("CHAR_"):
                if tag not in result["characters"]:
                    result["characters"].append(tag)
            elif tag.startswith("LOC_"):
                if tag not in result["locations"]:
                    result["locations"].append(tag)
            elif tag.startswith("PROP_"):
                if tag not in result["props"]:
                    result["props"].append(tag)

        return result

    # =========================================================================
    # STEP 3: PARALLEL NOTATION INSERTION
    # =========================================================================

    async def _add_notations_parallel(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add camera/placement notations to all frames in parallel."""
        logger.info("Step 3: Adding camera/placement notations in parallel...")

        processed_scenes = data["processed_scenes"]
        world_config = data.get("world_config", {})

        # Collect all frames from all scenes
        all_frames = []
        for scene in processed_scenes:
            all_frames.extend(scene.frames)

        if not all_frames:
            logger.warning("No frames to add notations to")
            return data

        # Process all frames in parallel
        tasks = [
            self._add_frame_notations(frame, world_config)
            for frame in all_frames
        ]

        notated_frames = await asyncio.gather(*tasks, return_exceptions=True)

        # Update frames in scenes
        frame_idx = 0
        for scene in processed_scenes:
            for i in range(len(scene.frames)):
                if frame_idx < len(notated_frames):
                    result = notated_frames[frame_idx]
                    if not isinstance(result, Exception):
                        scene.frames[i] = result
                    frame_idx += 1

        data["processed_scenes"] = processed_scenes
        logger.info(f"Added notations to {len(all_frames)} frames")

        return data

    async def _add_frame_notations(
        self,
        frame: FrameChunk,
        world_config: Dict[str, Any]
    ) -> FrameChunk:
        """Add camera, position, and lighting notations to a single frame.

        Uses scene.frame.camera notation:
        - Frame ID: scene.frame (e.g., 1.2)
        - Camera ID: scene.frame.camera (e.g., 1.2.cA)
        """
        # Get location info
        locations = world_config.get("locations", [])
        loc_info = "\n".join([
            f"[{l.get('tag', '')}]: {l.get('description', '')}\n  Directional views: {l.get('directional_views', {})}"
            for l in locations
        ])

        # Use scene.frame.camera notation
        camera_id = frame.primary_camera_id  # e.g., "1.2.cA"

        prompt = f"""Add camera and placement notations to this frame.

FRAME NOTATION: [{camera_id}]
SCENE: {frame.scene_number}
FRAME: {frame.frame_number}

EXISTING PROMPT:
{frame.prompt}

WORLD CONFIG LOCATIONS:
{loc_info}

Add the following notations using scene.frame.camera format [{camera_id}]:

1. [CAM: ...] - Camera instruction
   Include: Shot type, angle, movement, lens suggestion
   Example: [CAM: Medium close-up, slight low angle, static, 85mm]

2. [POS: ...] - Character positioning
   Include: Each character and their screen position
   Use: screen left, screen right, center, foreground, background
   Example: [POS: CHAR_PROTAGONIST center, CHAR_ANTAGONIST screen right background]

3. [LIGHT: ...] - Lighting instruction
   Include: Key light, fill, atmosphere
   Example: [LIGHT: Chiaroscuro, key from east window, dramatic shadows]

Output ONLY the three notations, one per line:
[CAM: ...]
[POS: ...]
[LIGHT: ...]"""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a cinematographer adding technical notations using scene.frame.camera format.",
            function=LLMFunction.STORY_ANALYSIS
        )

        # Parse notations from response
        cam_match = re.search(r'\[CAM:\s*([^\]]+)\]', response)
        pos_match = re.search(r'\[POS:\s*([^\]]+)\]', response)
        light_match = re.search(r'\[LIGHT:\s*([^\]]+)\]', response)

        frame.camera_notation = f"[CAM: {cam_match.group(1).strip()}]" if cam_match else "[CAM: Medium shot, eye level]"
        frame.position_notation = f"[POS: {pos_match.group(1).strip()}]" if pos_match else "[POS: Center frame]"
        frame.lighting_notation = f"[LIGHT: {light_match.group(1).strip()}]" if light_match else "[LIGHT: Natural lighting]"

        return frame

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

        # Build the visual script
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

                frame_block = f"""
(/scene_frame_chunk_start/)

[{camera_id}] (Frame)
{frame.camera_notation}
{frame.position_notation}
{frame.lighting_notation}
[PROMPT: {frame.prompt}]

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

        Uses Claude Sonnet 4.5 (hardcoded) for consistent quality.
        """
        logger.info("Step 5: Validating and refining frames...")

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

        # Update output
        visual_output.scenes = validated_scenes
        visual_output.total_frames = total_new_frames

        logger.info(f"Frame validation complete: {total_new_frames} frames after validation")

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

        # Build the validation prompt
        system_prompt = self._build_frame_validation_system_prompt(all_tags, world_config)
        user_prompt = self._build_frame_validation_user_prompt(frame, scene_number)

        try:
            # Use Claude Opus 4.5 (hardcoded for high-quality frame validation)
            client = AnthropicClient()
            response = client.generate_text(
                prompt=user_prompt,
                system=system_prompt,
                model="claude-opus-4-5-20251101",
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

2. **Multi-Subject Frame Detection**
   - Identify if the frame describes multiple distinct viewpoints that cannot be captured by a single camera
   - A frame needs splitting when it describes what multiple cameras would see
   - Single-subject frames showing one perspective do NOT need splitting

   ### SPATIAL IMPOSSIBILITY DETECTION
   Recognize when subjects are physically too far apart to be captured in a single camera shot:
   - Subjects in different rooms, buildings, or separated by walls/barriers
   - Subjects on different floors or elevation levels
   - Subjects separated by significant distance (across a street, opposite ends of a large space)
   - Subjects in different locations entirely (one inside, one outside)
   - When the description mentions "meanwhile" or "at the same time" for different locations

   ### MULTI-VIEWPOINT RECOGNITION
   Identify when a scene description implies multiple distinct perspectives or focal points:
   - Descriptions that show one subject's facial expression AND another subject's reaction across the room
   - Scenes describing what one character sees AND what another character sees simultaneously
   - Descriptions requiring both wide environmental context AND intimate close-up detail
   - Action sequences where multiple subjects perform simultaneous actions in different areas
   - Dialogue scenes where both speakers' reactions need to be visible but they face away from each other

   ### PERSPECTIVE CONFLICTS
   Detect when the described action requires incompatible camera angles or focal lengths:
   - Close-up emotional reactions combined with wide establishing shots in the same description
   - Descriptions requiring both front-facing and back-facing views of subjects
   - Scenes needing both overhead/bird's eye AND ground-level perspectives
   - Descriptions mixing macro detail (hands, eyes) with full-body or environmental framing
   - When the narrative focus shifts between subjects who cannot be framed together

3. **Frame Splitting Decision**
   - If splitting is needed, determine appropriate camera angles (cA, cB, cC, etc.)
   - Each split frame should describe what is visible from ONE camera position
   - Maintain scene continuity across split frames

   ### CAMERA ANGLE DETERMINATION PRINCIPLES
   - **Two subjects, same space, facing each other**: Usually 2 cameras (over-shoulder or alternating singles)
   - **Two subjects, different spaces**: Always split - one camera per location
   - **Group scene with clear focal subject**: May work as single wide shot, or split for reaction shots
   - **Action with multiple simultaneous events**: Split based on narrative importance of each event
   - **Emotional beat requiring intimacy**: Dedicate a camera to the close-up, separate from context
   - **Environmental establishing + character focus**: Consider splitting wide establishing from character coverage

   ### WHEN NOT TO SPLIT
   - Subjects are close enough to frame together naturally
   - A single camera angle can capture all described action
   - The description is from a single observer's perspective
   - Wide shots that intentionally show spatial relationships between subjects

4. **Prompt Rewriting**
   - Rewrite prompts to describe single camera viewpoints
   - Ensure each prompt clearly describes what is visible from that specific angle
   - Preserve all relevant tags in the rewritten prompts
   - Each rewritten prompt should specify what is IN FRAME for that camera position

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

