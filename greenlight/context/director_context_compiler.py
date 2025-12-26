"""
Greenlight Director Context Compiler

Extends context compression to the Directing Pipeline.
Provides token-efficient context packets for frame generation.

Features:
- Scene-level context compression
- Frame-level focal entity context
- Hierarchical context inheritance (project → scene → frame)
- Visual style and notation compression
- Camera-specific context optimization
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from greenlight.core.logging_config import get_logger
from greenlight.utils.unicode_utils import count_tokens_estimate

logger = get_logger("context.director_compiler")


class DirectorContextLevel(Enum):
    """Context levels for the directing pipeline."""
    PROJECT = "project"  # ~100 tokens: visual style, global constraints
    SCENE = "scene"      # ~150 tokens: location, characters, time, atmosphere
    FRAME = "frame"      # ~100 tokens: shot type, focal subjects, blocking
    CAMERA = "camera"    # ~50 tokens: angle, lens, specific framing


@dataclass
class CompressedProjectContext:
    """Compressed project-level context (~100 tokens)."""
    visual_style: str  # e.g., "Ink wash painting. Soft watercolor edges."
    media_type: str    # e.g., "manga", "film", "animation"
    notation_reminder: str  # Brief notation format reminder

    def to_string(self) -> str:
        parts = [
            f"STYLE: {self.visual_style}",
            f"MEDIA: {self.media_type}",
            self.notation_reminder
        ]
        return " | ".join(parts)


@dataclass
class CompressedSceneContext:
    """Compressed scene-level context (~150 tokens)."""
    scene_number: int
    location_card: str      # ~30 words
    characters_card: str    # ~40 words (names + screen positions)
    time_atmosphere: str    # ~20 words
    lighting_summary: str   # ~20 words
    continuity_note: str    # ~20 words

    def to_string(self) -> str:
        return f"""SCENE {self.scene_number}:
LOC: {self.location_card}
CHARS: {self.characters_card}
TIME/ATM: {self.time_atmosphere}
LIGHT: {self.lighting_summary}
CONT: {self.continuity_note}"""


@dataclass
class CompressedFrameContext:
    """Compressed frame-level context (~100 tokens)."""
    frame_id: str           # e.g., "3.2"
    shot_type: str          # e.g., "Medium two-shot"
    focal_subjects: str     # ~20 words
    blocking: str           # ~30 words
    previous_frame: str     # ~20 words
    rhythm_note: str        # ~10 words

    def to_string(self) -> str:
        return f"""FRAME {self.frame_id}:
SHOT: {self.shot_type}
FOCUS: {self.focal_subjects}
BLOCK: {self.blocking}
PREV: {self.previous_frame}
RHYTHM: {self.rhythm_note}"""


@dataclass
class CompressedCameraContext:
    """Compressed camera-level context (~50 tokens)."""
    camera_id: str      # e.g., "3.2.cA"
    angle: str          # e.g., "Eye level, slight low"
    lens: str           # e.g., "50mm, shallow DOF"
    position: str       # e.g., "Over [CHAR_MEI] shoulder"

    def to_string(self) -> str:
        return f"[{self.camera_id}] {self.angle}. {self.lens}. {self.position}"


@dataclass
class DirectorContextPacket:
    """Complete context packet for a camera prompt (~400 tokens total)."""
    project: CompressedProjectContext
    scene: CompressedSceneContext
    frame: CompressedFrameContext
    camera: CompressedCameraContext
    focal_entity_context: str = ""  # Detailed context for focal character/location

    def to_prompt_context(self) -> str:
        """Generate full context string for prompt."""
        parts = [
            "=== DIRECTOR CONTEXT ===",
            self.project.to_string(),
            "",
            self.scene.to_string(),
            "",
            self.frame.to_string(),
            "",
            self.camera.to_string(),
        ]

        if self.focal_entity_context:
            parts.append("")
            parts.append("=== FOCAL ENTITY ===")
            parts.append(self.focal_entity_context)

        return "\n".join(parts)

    @property
    def token_count(self) -> int:
        return count_tokens_estimate(self.to_prompt_context())


class DirectorContextCompiler:
    """
    Compiles context for the Directing Pipeline with 85-90% token reduction.

    Transforms verbose world_config and aggregator context into minimal
    ~400-token packets optimized for frame/camera prompt generation.

    Usage:
        compiler = DirectorContextCompiler(world_config)

        # Compile scene context once
        scene_ctx = compiler.compile_scene(scene_data)

        # Compile frame context for each frame
        for frame in frames:
            frame_ctx = compiler.compile_frame(frame_data, scene_ctx)

            # Compile camera context for each camera
            for camera in frame.cameras:
                packet = compiler.compile_camera(camera_data, frame_ctx)
                prompt_context = packet.to_prompt_context()
    """

    def __init__(
        self,
        world_config: Dict[str, Any],
        max_entity_context: int = 200  # Max tokens for focal entity
    ):
        """
        Initialize the director context compiler.

        Args:
            world_config: World configuration dictionary
            max_entity_context: Maximum tokens for focal entity context
        """
        self.world_config = world_config
        self.max_entity_context = max_entity_context

        # Pre-compile project context (doesn't change)
        self._project_context = self._compile_project_context()

        # Character/location cards cache
        self._entity_cards: Dict[str, str] = {}
        self._build_entity_cards()

    def _compile_project_context(self) -> CompressedProjectContext:
        """Compile project-level context."""
        visual_style = self.world_config.get("visual_style", "")
        style_notes = self.world_config.get("style_notes", "")

        # Compress to ~30 words
        style_text = f"{visual_style}. {style_notes}"
        if len(style_text.split()) > 30:
            style_text = " ".join(style_text.split()[:30]) + "..."

        media_type = self.world_config.get("media_type", "standard")

        notation = "Tags: [CHAR_X], [LOC_X]. Frames: [scene.frame.cLetter]"

        return CompressedProjectContext(
            visual_style=style_text,
            media_type=media_type,
            notation_reminder=notation
        )

    def _build_entity_cards(self) -> None:
        """Build compressed entity cards for quick lookup."""
        # Character cards (~40 words each)
        for char in self.world_config.get("characters", []):
            tag = char.get("tag", "")
            if not tag:
                continue

            name = char.get("name", tag.replace("CHAR_", ""))
            visual_desc = char.get("visual_description", "")[:100]

            self._entity_cards[tag] = f"[{tag}] ({name}): {visual_desc}"

        # Location cards (~30 words each)
        for loc in self.world_config.get("locations", []):
            tag = loc.get("tag", "")
            if not tag:
                continue

            name = loc.get("name", tag.replace("LOC_", ""))
            desc = loc.get("description", "")[:80]

            self._entity_cards[tag] = f"[{tag}] ({name}): {desc}"

    def compile_scene(
        self,
        scene_number: int,
        location_tag: str,
        characters: List[str],
        time_of_day: str = "",
        weather: str = "",
        atmosphere: str = "",
        lighting_state: Dict[str, str] = None,
        established_elements: List[str] = None,
        character_positions: Dict[str, str] = None
    ) -> CompressedSceneContext:
        """
        Compile scene-level context.

        Args:
            scene_number: Scene number
            location_tag: Location tag
            characters: Character tags in scene
            time_of_day: Time of day string
            weather: Weather conditions
            atmosphere: Scene atmosphere
            lighting_state: Lighting state dict
            established_elements: Previously established elements
            character_positions: Screen positions for 180° rule

        Returns:
            CompressedSceneContext
        """
        # Location card
        location_card = self._entity_cards.get(
            location_tag,
            f"[{location_tag}]"
        )[:80]

        # Characters card with positions
        char_parts = []
        for char_tag in characters[:5]:  # Max 5 characters
            char_name = char_tag.replace("CHAR_", "")
            position = ""
            if character_positions and char_tag in character_positions:
                position = f"@{character_positions[char_tag]}"
            char_parts.append(f"[{char_tag}]{position}")
        characters_card = ", ".join(char_parts)

        # Time/atmosphere
        time_atm_parts = []
        if time_of_day:
            time_atm_parts.append(time_of_day)
        if weather:
            time_atm_parts.append(weather)
        if atmosphere:
            time_atm_parts.append(atmosphere)
        time_atmosphere = ". ".join(time_atm_parts)[:60]

        # Lighting summary
        lighting_parts = []
        if lighting_state:
            if lighting_state.get("key_light_direction"):
                lighting_parts.append(f"Key: {lighting_state['key_light_direction']}")
            if lighting_state.get("color_temperature"):
                lighting_parts.append(lighting_state["color_temperature"])
            if lighting_state.get("atmosphere"):
                lighting_parts.append(lighting_state["atmosphere"])
        lighting_summary = ". ".join(lighting_parts)[:50] if lighting_parts else "Standard lighting"

        # Continuity note
        continuity_parts = []
        if established_elements:
            continuity_parts.append(f"Established: {', '.join(established_elements[:3])}")
        continuity_note = ". ".join(continuity_parts)[:50] if continuity_parts else "—"

        return CompressedSceneContext(
            scene_number=scene_number,
            location_card=location_card,
            characters_card=characters_card,
            time_atmosphere=time_atmosphere,
            lighting_summary=lighting_summary,
            continuity_note=continuity_note
        )

    def compile_frame(
        self,
        scene_number: int,
        frame_number: int,
        shot_type: str,
        focal_subjects: List[str],
        blocking_notes: str = "",
        previous_frame_summary: str = "",
        rhythm_suggestion: str = ""
    ) -> CompressedFrameContext:
        """
        Compile frame-level context.

        Args:
            scene_number: Scene number
            frame_number: Frame number
            shot_type: Shot type string
            focal_subjects: Primary subjects in frame
            blocking_notes: Blocking/positioning notes
            previous_frame_summary: Summary of previous frame
            rhythm_suggestion: Shot rhythm suggestion

        Returns:
            CompressedFrameContext
        """
        frame_id = f"{scene_number}.{frame_number}"

        # Focal subjects
        focal_parts = []
        for subject in focal_subjects[:3]:
            if subject.startswith("CHAR_") or subject.startswith("LOC_") or subject.startswith("PROP_"):
                focal_parts.append(f"[{subject}]")
            else:
                focal_parts.append(subject)
        focal_str = ", ".join(focal_parts) if focal_parts else "—"

        # Blocking
        blocking = blocking_notes[:60] if blocking_notes else "Standard blocking"

        # Previous frame
        previous = previous_frame_summary[:40] if previous_frame_summary else "—"

        # Rhythm
        rhythm = rhythm_suggestion[:30] if rhythm_suggestion else "—"

        return CompressedFrameContext(
            frame_id=frame_id,
            shot_type=shot_type,
            focal_subjects=focal_str,
            blocking=blocking,
            previous_frame=previous,
            rhythm_note=rhythm
        )

    def compile_camera(
        self,
        scene_number: int,
        frame_number: int,
        camera_letter: str,
        angle: str = "",
        lens: str = "",
        position_description: str = ""
    ) -> CompressedCameraContext:
        """
        Compile camera-level context.

        Args:
            scene_number: Scene number
            frame_number: Frame number
            camera_letter: Camera letter (A, B, C...)
            angle: Camera angle
            lens: Lens info
            position_description: Camera position

        Returns:
            CompressedCameraContext
        """
        camera_id = f"{scene_number}.{frame_number}.c{camera_letter}"

        return CompressedCameraContext(
            camera_id=camera_id,
            angle=angle or "Eye level",
            lens=lens or "Standard",
            position=position_description or "Standard position"
        )

    def compile_full_packet(
        self,
        scene_context: CompressedSceneContext,
        frame_context: CompressedFrameContext,
        camera_context: CompressedCameraContext,
        focal_entity: str = None
    ) -> DirectorContextPacket:
        """
        Compile complete context packet for camera prompt.

        Args:
            scene_context: Compiled scene context
            frame_context: Compiled frame context
            camera_context: Compiled camera context
            focal_entity: Optional focal entity tag for detailed context

        Returns:
            DirectorContextPacket
        """
        # Get focal entity context if specified
        focal_context = ""
        if focal_entity:
            focal_context = self._get_focal_entity_context(focal_entity)

        return DirectorContextPacket(
            project=self._project_context,
            scene=scene_context,
            frame=frame_context,
            camera=camera_context,
            focal_entity_context=focal_context
        )

    def _get_focal_entity_context(self, tag: str) -> str:
        """Get detailed context for focal entity."""
        # Character context
        if tag.startswith("CHAR_"):
            for char in self.world_config.get("characters", []):
                if char.get("tag") == tag:
                    parts = [f"[{tag}] FOCUS:"]

                    if visual := char.get("visual_description"):
                        parts.append(f"Visual: {visual[:100]}")

                    if physicality := char.get("physicality"):
                        if isinstance(physicality, dict):
                            phys_parts = []
                            if posture := physicality.get("posture"):
                                phys_parts.append(f"Posture: {posture}")
                            if movement := physicality.get("movement"):
                                phys_parts.append(f"Movement: {movement}")
                            if phys_parts:
                                parts.append(". ".join(phys_parts)[:80])

                    return "\n".join(parts)[:self.max_entity_context]

        # Location context
        elif tag.startswith("LOC_"):
            for loc in self.world_config.get("locations", []):
                if loc.get("tag") == tag:
                    parts = [f"[{tag}] FOCUS:"]

                    if desc := loc.get("description"):
                        parts.append(f"Description: {desc[:100]}")

                    if visual := loc.get("visual_description"):
                        parts.append(f"Visual: {visual[:100]}")

                    return "\n".join(parts)[:self.max_entity_context]

        return self._entity_cards.get(tag, "")

    def get_project_context(self) -> CompressedProjectContext:
        """Get the compiled project context."""
        return self._project_context

    def get_entity_card(self, tag: str) -> str:
        """Get compressed entity card for a tag."""
        return self._entity_cards.get(tag, f"[{tag}]")

    def get_stats(self) -> Dict[str, Any]:
        """Get compiler statistics."""
        return {
            "entity_cards": len(self._entity_cards),
            "project_context_tokens": count_tokens_estimate(self._project_context.to_string()),
            "max_entity_context": self.max_entity_context
        }


# Convenience function
def create_director_compiler(world_config: Dict[str, Any]) -> DirectorContextCompiler:
    """Create a director context compiler."""
    return DirectorContextCompiler(world_config)
