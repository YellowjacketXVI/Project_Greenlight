"""
Greenlight Context Aggregator

Hierarchical context system for maintaining consistency across scenes, frames, and cameras.
Context cascades from root (world/project) → scene → frame → camera, with each level
inheriting and building upon parent context.

Architecture:
```
ProjectContext (world_config, visual_style, characters, locations)
    └── SceneContext (time, location, weather, characters_present, established_elements)
            └── FrameContext (shot_type, focal_subject, lighting_state, camera_position)
                    └── CameraContext (angle, lens, specific_framing)
```

Each level:
1. Inherits all parent context
2. Can override specific elements (e.g., lighting changes within a scene)
3. Tracks what has been "established" vs "new" for continuity
4. Provides aggregated context string for prompt generation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple
from enum import Enum
from collections import deque
import copy


class ContextLevel(Enum):
    """Hierarchy levels for context."""
    PROJECT = "project"
    SCENE = "scene"
    FRAME = "frame"
    CAMERA = "camera"


class ScreenPosition(Enum):
    """Screen position for 180-degree rule tracking."""
    LEFT = "screen-left"
    CENTER = "screen-center"
    RIGHT = "screen-right"
    UNKNOWN = "unknown"


class ShotCategory(Enum):
    """Shot type categories for rhythm analysis."""
    WIDE = "wide"           # Establishing, full, extreme wide
    MEDIUM = "medium"       # Medium, cowboy, two-shot
    CLOSE = "close"         # Close-up, extreme close-up
    INSERT = "insert"       # Detail shots, cutaways
    POV = "pov"             # Point-of-view
    REACTION = "reaction"   # Reaction shots


@dataclass
class CharacterScreenPosition:
    """Tracks a character's screen position for 180-degree rule."""
    tag: str
    position: ScreenPosition
    established_frame: str  # Frame where position was established
    facing_direction: str = ""  # Which way character is facing (left/right)


@dataclass
class ShotRhythmEntry:
    """Entry in shot rhythm history for pacing analysis."""
    frame_id: str
    category: ShotCategory
    shot_type: str  # Original shot type string


@dataclass
class EstablishedElement:
    """An element that has been visually established in prior frames."""
    tag: str
    first_appearance: str  # Frame ID where first shown (e.g., "1.1.cA")
    description: str  # How it was shown
    last_shown: str  # Most recent frame ID
    consistency_notes: List[str] = field(default_factory=list)
    screen_position: ScreenPosition = ScreenPosition.UNKNOWN


@dataclass
class LightingState:
    """Current lighting state that should be consistent across frames."""
    time_of_day: str = ""
    key_light_direction: str = ""  # e.g., "from east", "overhead"
    key_light_quality: str = ""  # e.g., "harsh", "soft", "diffused"
    fill_light: str = ""
    atmosphere: str = ""  # e.g., "hazy", "clear", "foggy"
    color_temperature: str = ""  # e.g., "warm", "cool", "neutral"
    practical_lights: List[str] = field(default_factory=list)  # e.g., ["lanterns", "candles"]

    def to_prompt_string(self) -> str:
        """Convert lighting state to prompt-friendly string."""
        parts = []
        if self.time_of_day:
            parts.append(f"{self.time_of_day} lighting")
        if self.key_light_direction:
            parts.append(f"key light {self.key_light_direction}")
        if self.key_light_quality:
            parts.append(f"{self.key_light_quality} light quality")
        if self.atmosphere:
            parts.append(f"{self.atmosphere} atmosphere")
        if self.practical_lights:
            parts.append(f"practical lights: {', '.join(self.practical_lights)}")
        return ". ".join(parts) if parts else ""


@dataclass
class ProjectContext:
    """Root-level context from world_config."""
    visual_style: str = ""
    style_notes: str = ""
    media_type: str = "standard"

    # All available entities
    characters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    locations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    props: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Global constraints
    global_constraints: List[str] = field(default_factory=list)

    @classmethod
    def from_world_config(cls, world_config: Dict[str, Any]) -> "ProjectContext":
        """Create ProjectContext from world_config dict."""
        ctx = cls(
            visual_style=world_config.get("visual_style", ""),
            style_notes=world_config.get("style_notes", ""),
            media_type=world_config.get("media_type", "standard"),
        )

        # Index characters by tag
        for char in world_config.get("characters", []):
            if tag := char.get("tag"):
                ctx.characters[tag] = char

        # Index locations by tag
        for loc in world_config.get("locations", []):
            if tag := loc.get("tag"):
                ctx.locations[tag] = loc

        # Index props by tag
        for prop in world_config.get("props", []):
            if tag := prop.get("tag"):
                ctx.props[tag] = prop

        return ctx


@dataclass
class SceneContext:
    """Scene-level context that applies to all frames in the scene."""
    scene_number: int
    parent: ProjectContext

    # Scene-specific settings
    location_tag: str = ""
    location_direction: str = "NORTH"  # Current camera orientation within location
    time_of_day: str = ""
    weather: str = ""
    atmosphere: str = ""

    # Characters present in this scene
    characters_present: Set[str] = field(default_factory=set)
    props_present: Set[str] = field(default_factory=set)

    # Lighting established for this scene
    lighting: LightingState = field(default_factory=LightingState)

    # Elements established during this scene (for continuity)
    established_elements: Dict[str, EstablishedElement] = field(default_factory=dict)

    # Scene-specific constraints
    scene_constraints: List[str] = field(default_factory=list)

    # Tracking
    frame_count: int = 0
    current_frame: int = 0

    # 180-degree rule: Character screen positions
    character_positions: Dict[str, CharacterScreenPosition] = field(default_factory=dict)
    axis_of_action: str = ""  # Describes the imaginary line (e.g., "CHAR_A to CHAR_B")

    # Shot rhythm tracking for pacing
    shot_history: List[ShotRhythmEntry] = field(default_factory=list)

    def get_character_info(self, tag: str) -> Dict[str, Any]:
        """Get character info from parent context."""
        return self.parent.characters.get(tag, {})

    def get_location_info(self) -> Dict[str, Any]:
        """Get current location info from parent context."""
        return self.parent.locations.get(self.location_tag, {})

    def mark_element_established(
        self,
        tag: str,
        frame_id: str,
        description: str
    ) -> None:
        """Mark an element as visually established."""
        if tag in self.established_elements:
            self.established_elements[tag].last_shown = frame_id
        else:
            self.established_elements[tag] = EstablishedElement(
                tag=tag,
                first_appearance=frame_id,
                description=description,
                last_shown=frame_id
            )

    def is_established(self, tag: str) -> bool:
        """Check if an element has been established."""
        return tag in self.established_elements

    def get_continuity_context(self) -> str:
        """Get continuity context string for prompts."""
        parts = []

        if self.established_elements:
            established_chars = [
                e for t, e in self.established_elements.items()
                if t.startswith("CHAR_")
            ]
            if established_chars:
                parts.append("ESTABLISHED CHARACTERS (maintain consistency):")
                for elem in established_chars:
                    parts.append(f"  [{elem.tag}]: First shown in {elem.first_appearance}")

        return "\n".join(parts)

    # =========================================================================
    # 180-DEGREE RULE / SCREEN DIRECTION TRACKING
    # =========================================================================

    def establish_character_position(
        self,
        tag: str,
        position: ScreenPosition,
        frame_id: str,
        facing: str = ""
    ) -> None:
        """Establish a character's screen position for 180-degree rule."""
        self.character_positions[tag] = CharacterScreenPosition(
            tag=tag,
            position=position,
            established_frame=frame_id,
            facing_direction=facing
        )

    def establish_axis_of_action(
        self,
        char_a: str,
        char_b: str,
        frame_id: str
    ) -> None:
        """Establish the axis of action between two characters.

        This defines the 180-degree line that cameras should not cross.
        """
        self.axis_of_action = f"{char_a} to {char_b}"

        # If not already positioned, set default positions
        if char_a not in self.character_positions:
            self.establish_character_position(
                char_a, ScreenPosition.LEFT, frame_id, facing="right"
            )
        if char_b not in self.character_positions:
            self.establish_character_position(
                char_b, ScreenPosition.RIGHT, frame_id, facing="left"
            )

    def get_character_screen_position(self, tag: str) -> Optional[ScreenPosition]:
        """Get established screen position for a character."""
        if tag in self.character_positions:
            return self.character_positions[tag].position
        return None

    def get_screen_direction_constraints(self) -> List[str]:
        """Get 180-degree rule constraints for prompts."""
        constraints = []

        if self.axis_of_action:
            constraints.append(f"AXIS OF ACTION: {self.axis_of_action}")
            constraints.append("Camera must stay on one side of this line (180° rule)")

        for tag, pos in self.character_positions.items():
            constraint = f"[{tag}] established at {pos.position.value}"
            if pos.facing_direction:
                constraint += f", facing {pos.facing_direction}"
            constraints.append(constraint)

        return constraints

    # =========================================================================
    # SHOT RHYTHM / PACING ANALYSIS
    # =========================================================================

    def record_shot(self, frame_id: str, shot_type: str) -> None:
        """Record a shot for rhythm analysis."""
        category = self._categorize_shot(shot_type)
        self.shot_history.append(ShotRhythmEntry(
            frame_id=frame_id,
            category=category,
            shot_type=shot_type
        ))

    def _categorize_shot(self, shot_type: str) -> ShotCategory:
        """Categorize a shot type string."""
        shot_lower = shot_type.lower()

        if any(w in shot_lower for w in ["wide", "establishing", "full", "extreme wide", "master"]):
            return ShotCategory.WIDE
        elif any(w in shot_lower for w in ["close", "closeup", "close-up", "tight", "ecu", "extreme close"]):
            return ShotCategory.CLOSE
        elif any(w in shot_lower for w in ["insert", "detail", "cutaway"]):
            return ShotCategory.INSERT
        elif any(w in shot_lower for w in ["pov", "point of view", "subjective"]):
            return ShotCategory.POV
        elif any(w in shot_lower for w in ["reaction", "listening"]):
            return ShotCategory.REACTION
        else:
            return ShotCategory.MEDIUM

    def get_shot_rhythm_analysis(self) -> Dict[str, Any]:
        """Analyze shot rhythm for pacing recommendations."""
        if len(self.shot_history) < 2:
            return {"recommendations": [], "pattern": [], "variety_score": 1.0}

        # Get recent shots (last 5)
        recent = self.shot_history[-5:]
        pattern = [entry.category.value for entry in recent]

        # Calculate variety score (unique categories / total)
        unique_categories = len(set(pattern))
        variety_score = unique_categories / len(pattern)

        recommendations = []

        # Check for monotonous patterns
        if len(recent) >= 3:
            last_three = [e.category for e in recent[-3:]]
            if len(set(last_three)) == 1:
                recommendations.append(
                    f"WARNING: 3 consecutive {last_three[0].value} shots - consider varying shot type"
                )

        # Suggest based on current pattern
        last_shot = recent[-1].category if recent else None

        if last_shot == ShotCategory.WIDE:
            recommendations.append("SUGGEST: Follow wide with medium or close-up to build intimacy")
        elif last_shot == ShotCategory.CLOSE:
            if len(recent) >= 2 and recent[-2].category == ShotCategory.CLOSE:
                recommendations.append("SUGGEST: Break up consecutive close-ups with medium or reaction")
        elif last_shot == ShotCategory.MEDIUM:
            if len(recent) >= 4 and all(e.category == ShotCategory.MEDIUM for e in recent[-4:]):
                recommendations.append("SUGGEST: 4+ mediums - add visual variety with close-up or wide")

        # Check for establishing shot at scene start
        if len(self.shot_history) == 1 and self.shot_history[0].category != ShotCategory.WIDE:
            recommendations.append("NOTE: Scene didn't start with establishing shot - intentional?")

        return {
            "recommendations": recommendations,
            "pattern": pattern,
            "variety_score": variety_score,
            "total_shots": len(self.shot_history)
        }

    def get_next_shot_suggestions(self) -> List[str]:
        """Get suggestions for the next shot based on rhythm."""
        analysis = self.get_shot_rhythm_analysis()

        if not self.shot_history:
            return ["Consider starting with Wide/Establishing shot"]

        suggestions = []
        last_shot = self.shot_history[-1].category

        # Shot flow recommendations
        shot_flow = {
            ShotCategory.WIDE: ["Medium", "Close-up (to isolate subject)"],
            ShotCategory.MEDIUM: ["Close-up", "Wide (to re-establish)", "Reaction"],
            ShotCategory.CLOSE: ["Medium (pull back)", "Reaction", "Insert/Detail"],
            ShotCategory.INSERT: ["Medium", "Close-up (on character reaction)"],
            ShotCategory.POV: ["Reaction (of POV character)", "Medium"],
            ShotCategory.REACTION: ["Close-up", "Medium", "POV"]
        }

        if last_shot in shot_flow:
            suggestions.extend(shot_flow[last_shot])

        # Add variety warnings to suggestions
        suggestions.extend(analysis.get("recommendations", []))

        return suggestions

    def to_prompt_context(self) -> str:
        """Generate context string for frame prompts."""
        lines = []

        # Scene identification
        lines.append(f"SCENE {self.scene_number} CONTEXT:")

        # Location
        if self.location_tag:
            loc_info = self.get_location_info()
            loc_name = loc_info.get("name", self.location_tag)
            lines.append(f"  Location: [{self.location_tag}] - {loc_name}")
            lines.append(f"  Camera Orientation: {self.location_direction}")

        # Time and atmosphere
        if self.time_of_day:
            lines.append(f"  Time: {self.time_of_day}")
        if self.weather:
            lines.append(f"  Weather: {self.weather}")
        if self.atmosphere:
            lines.append(f"  Atmosphere: {self.atmosphere}")

        # Lighting state
        if lighting_str := self.lighting.to_prompt_string():
            lines.append(f"  Lighting: {lighting_str}")

        # Characters present with screen positions
        if self.characters_present:
            char_list = []
            for tag in self.characters_present:
                char_info = self.get_character_info(tag)
                name = char_info.get("name", tag)
                position = self.get_character_screen_position(tag)
                if position and position != ScreenPosition.UNKNOWN:
                    char_list.append(f"[{tag}] ({name}) @ {position.value}")
                else:
                    char_list.append(f"[{tag}] ({name})")
            lines.append(f"  Characters: {', '.join(char_list)}")

        # 180-degree rule / Axis of action
        if self.axis_of_action:
            lines.append(f"  AXIS OF ACTION: {self.axis_of_action} (maintain 180° rule)")

        # Shot rhythm info
        if self.shot_history:
            rhythm = self.get_shot_rhythm_analysis()
            if rhythm.get("recommendations"):
                lines.append(f"  PACING NOTE: {rhythm['recommendations'][0]}")

        # Continuity notes
        if self.established_elements:
            lines.append("  CONTINUITY: Maintain visual consistency with established elements")

        return "\n".join(lines)


@dataclass
class FrameContext:
    """Frame-level context that applies to all cameras in the frame."""
    frame_id: str  # e.g., "1.2"
    frame_number: int
    parent: SceneContext

    # Frame-specific settings
    shot_type: str = ""  # e.g., "Wide", "Medium", "Close-up"
    focal_subjects: List[str] = field(default_factory=list)  # Primary subjects in frame

    # Frame can override scene lighting for specific effect
    lighting_override: Optional[LightingState] = None

    # Position/blocking notes
    blocking_notes: str = ""

    # What happened in previous frame (for continuity)
    previous_frame_summary: str = ""

    # Camera positions used
    cameras: List[str] = field(default_factory=list)

    @property
    def scene_number(self) -> int:
        return self.parent.scene_number

    @property
    def effective_lighting(self) -> LightingState:
        """Get effective lighting (override or parent)."""
        return self.lighting_override or self.parent.lighting

    def inherit_from_previous(self, previous: "FrameContext") -> None:
        """Inherit relevant context from previous frame."""
        if previous:
            self.previous_frame_summary = f"Previous frame ({previous.frame_id}): {previous.shot_type}"
            # Carry forward any lighting changes
            if previous.lighting_override:
                self.lighting_override = copy.deepcopy(previous.lighting_override)

    def to_prompt_context(self) -> str:
        """Generate context string for camera prompts."""
        lines = []

        # Include parent scene context
        lines.append(self.parent.to_prompt_context())
        lines.append("")

        # Frame-specific context
        lines.append(f"FRAME {self.frame_id} CONTEXT:")
        if self.shot_type:
            lines.append(f"  Shot Type: {self.shot_type}")
        if self.focal_subjects:
            lines.append(f"  Focal Subjects: {', '.join(self.focal_subjects)}")
        if self.blocking_notes:
            lines.append(f"  Blocking: {self.blocking_notes}")
        if self.previous_frame_summary:
            lines.append(f"  Continuity: {self.previous_frame_summary}")

        return "\n".join(lines)


@dataclass
class CameraContext:
    """Camera-level context for a specific angle/shot."""
    camera_id: str  # e.g., "1.2.cA"
    camera_letter: str  # e.g., "A", "B", "C"
    parent: FrameContext

    # Camera-specific settings
    angle: str = ""  # e.g., "eye level", "high angle", "low angle"
    lens: str = ""  # e.g., "35mm wide", "85mm", "100mm macro"
    movement: str = ""  # e.g., "static", "slow push", "tracking"

    # What this camera sees that others don't
    unique_elements: List[str] = field(default_factory=list)

    # Position in space
    position_description: str = ""  # e.g., "over shoulder of CHAR_MEI"

    @property
    def scene_number(self) -> int:
        return self.parent.scene_number

    @property
    def frame_number(self) -> int:
        return self.parent.frame_number

    def to_prompt_context(self) -> str:
        """Generate full cascaded context for this camera's prompt."""
        lines = []

        # Include full parent chain
        lines.append(self.parent.to_prompt_context())
        lines.append("")

        # Camera-specific context
        lines.append(f"CAMERA [{self.camera_id}] SPECIFICS:")
        if self.angle:
            lines.append(f"  Angle: {self.angle}")
        if self.lens:
            lines.append(f"  Lens: {self.lens}")
        if self.movement:
            lines.append(f"  Movement: {self.movement}")
        if self.position_description:
            lines.append(f"  Position: {self.position_description}")
        if self.unique_elements:
            lines.append(f"  Unique to this angle: {', '.join(self.unique_elements)}")

        return "\n".join(lines)


class ContextAggregator:
    """
    Manages hierarchical context for a directing session.

    Tracks context at each level and provides aggregated context
    for prompt generation, ensuring consistency across frames.

    Features:
    - Hierarchical context (Project → Scene → Frame → Camera)
    - 180-degree rule / screen direction tracking
    - Shot rhythm analysis for visual variety
    - Cross-scene continuity for multi-scene sequences
    """

    def __init__(self, world_config: Dict[str, Any]):
        """Initialize with world config."""
        self.project_context = ProjectContext.from_world_config(world_config)
        self.scenes: Dict[int, SceneContext] = {}
        self.current_scene: Optional[SceneContext] = None
        self.current_frame: Optional[FrameContext] = None

        # Cross-scene continuity tracking
        self.global_character_positions: Dict[str, CharacterScreenPosition] = {}
        self.scene_sequence: List[int] = []  # Order of scenes processed
        self.cross_scene_continuity: Dict[str, Any] = {}  # Shared state across scenes

    def start_scene(
        self,
        scene_number: int,
        location_tag: str = "",
        time_of_day: str = "",
        weather: str = "",
        atmosphere: str = "",
        characters: List[str] = None,
        inherit_from_previous: bool = True
    ) -> SceneContext:
        """Start a new scene context.

        Args:
            scene_number: Scene number
            location_tag: Location tag
            time_of_day: Time of day string
            weather: Weather conditions
            atmosphere: Scene atmosphere
            characters: List of character tags in this scene
            inherit_from_previous: Whether to inherit continuity from previous scene
        """
        scene_ctx = SceneContext(
            scene_number=scene_number,
            parent=self.project_context,
            location_tag=location_tag,
            time_of_day=time_of_day,
            weather=weather,
            atmosphere=atmosphere,
            characters_present=set(characters) if characters else set()
        )

        # Initialize lighting from time of day
        scene_ctx.lighting = self._infer_lighting_from_time(time_of_day, weather)

        # Cross-scene continuity: inherit character positions if same characters
        if inherit_from_previous and self.scene_sequence:
            prev_scene_num = self.scene_sequence[-1]
            prev_scene = self.scenes.get(prev_scene_num)

            if prev_scene:
                # Check for shared characters between scenes
                shared_chars = scene_ctx.characters_present & prev_scene.characters_present

                if shared_chars:
                    # Inherit positions for shared characters
                    for char_tag in shared_chars:
                        if char_tag in prev_scene.character_positions:
                            prev_pos = prev_scene.character_positions[char_tag]
                            scene_ctx.character_positions[char_tag] = CharacterScreenPosition(
                                tag=char_tag,
                                position=prev_pos.position,
                                established_frame=prev_pos.established_frame,
                                facing_direction=prev_pos.facing_direction
                            )

                    # Store cross-scene continuity info
                    self.cross_scene_continuity[f"{prev_scene_num}->{scene_number}"] = {
                        "shared_characters": list(shared_chars),
                        "same_location": prev_scene.location_tag == location_tag,
                        "time_transition": f"{prev_scene.time_of_day} -> {time_of_day}"
                    }

                # Inherit axis of action if same two-character scene
                if prev_scene.axis_of_action:
                    axis_chars = prev_scene.axis_of_action.split(" to ")
                    if len(axis_chars) == 2:
                        if axis_chars[0] in shared_chars and axis_chars[1] in shared_chars:
                            scene_ctx.axis_of_action = prev_scene.axis_of_action

        # Track scene sequence
        self.scene_sequence.append(scene_number)
        self.scenes[scene_number] = scene_ctx
        self.current_scene = scene_ctx

        return scene_ctx

    def start_frame(
        self,
        frame_number: int,
        shot_type: str = "",
        focal_subjects: List[str] = None
    ) -> FrameContext:
        """Start a new frame within current scene."""
        if not self.current_scene:
            raise ValueError("No active scene. Call start_scene first.")

        frame_id = f"{self.current_scene.scene_number}.{frame_number}"

        frame_ctx = FrameContext(
            frame_id=frame_id,
            frame_number=frame_number,
            parent=self.current_scene,
            shot_type=shot_type,
            focal_subjects=focal_subjects or []
        )

        # Inherit from previous frame if exists
        if self.current_frame and self.current_frame.scene_number == self.current_scene.scene_number:
            frame_ctx.inherit_from_previous(self.current_frame)

        self.current_frame = frame_ctx
        self.current_scene.current_frame = frame_number

        return frame_ctx

    def add_camera(
        self,
        camera_letter: str,
        angle: str = "",
        lens: str = "",
        movement: str = "",
        position: str = ""
    ) -> CameraContext:
        """Add a camera to the current frame."""
        if not self.current_frame:
            raise ValueError("No active frame. Call start_frame first.")

        camera_id = f"{self.current_frame.frame_id}.c{camera_letter}"

        camera_ctx = CameraContext(
            camera_id=camera_id,
            camera_letter=camera_letter,
            parent=self.current_frame,
            angle=angle,
            lens=lens,
            movement=movement,
            position_description=position
        )

        self.current_frame.cameras.append(camera_id)

        return camera_ctx

    def mark_established(self, tag: str, description: str) -> None:
        """Mark an element as established in the current frame."""
        if self.current_scene and self.current_frame:
            self.current_scene.mark_element_established(
                tag=tag,
                frame_id=self.current_frame.frame_id + ".cA",
                description=description
            )

    def update_lighting(
        self,
        time_of_day: str = None,
        key_direction: str = None,
        atmosphere: str = None
    ) -> None:
        """Update lighting state for current scene."""
        if not self.current_scene:
            return

        if time_of_day:
            self.current_scene.lighting.time_of_day = time_of_day
        if key_direction:
            self.current_scene.lighting.key_light_direction = key_direction
        if atmosphere:
            self.current_scene.lighting.atmosphere = atmosphere

    def get_context_for_prompt(self, camera_id: str = None) -> str:
        """Get aggregated context string for prompt generation."""
        if camera_id and self.current_frame:
            # Parse camera letter from ID
            parts = camera_id.split(".")
            if len(parts) >= 3:
                camera_letter = parts[2].replace("c", "")
                camera_ctx = self.add_camera(camera_letter)
                return camera_ctx.to_prompt_context()

        if self.current_frame:
            return self.current_frame.to_prompt_context()

        if self.current_scene:
            return self.current_scene.to_prompt_context()

        return ""

    def get_consistency_constraints(self) -> List[str]:
        """Get list of consistency constraints based on established elements."""
        constraints = []

        if not self.current_scene:
            return constraints

        # Time consistency
        if self.current_scene.time_of_day:
            time_constraints = self._get_time_constraints(self.current_scene.time_of_day)
            constraints.extend(time_constraints)

        # Character consistency
        for tag in self.current_scene.characters_present:
            if self.current_scene.is_established(tag):
                elem = self.current_scene.established_elements[tag]
                constraints.append(
                    f"[{tag}] must match appearance from {elem.first_appearance}"
                )

        # Location consistency
        if self.current_scene.location_tag:
            constraints.append(
                f"Location [{self.current_scene.location_tag}] must be consistent "
                f"with {self.current_scene.location_direction} view"
            )

        # 180-degree rule constraints
        screen_direction = self.current_scene.get_screen_direction_constraints()
        constraints.extend(screen_direction)

        # Cross-scene continuity constraints
        cross_scene = self.get_cross_scene_constraints()
        constraints.extend(cross_scene)

        return constraints

    def get_cross_scene_constraints(self) -> List[str]:
        """Get cross-scene continuity constraints."""
        constraints = []

        if not self.current_scene or len(self.scene_sequence) < 2:
            return constraints

        scene_num = self.current_scene.scene_number
        prev_scene_num = self.scene_sequence[-2] if self.scene_sequence[-1] == scene_num else None

        if prev_scene_num:
            key = f"{prev_scene_num}->{scene_num}"
            if key in self.cross_scene_continuity:
                cont = self.cross_scene_continuity[key]

                if cont.get("shared_characters"):
                    chars = ", ".join(cont["shared_characters"])
                    constraints.append(
                        f"CROSS-SCENE CONTINUITY: [{chars}] carry over from Scene {prev_scene_num}"
                    )

                if cont.get("same_location"):
                    constraints.append(
                        f"SAME LOCATION as Scene {prev_scene_num} - maintain spatial consistency"
                    )

                if cont.get("time_transition"):
                    constraints.append(f"TIME TRANSITION: {cont['time_transition']}")

        return constraints

    def get_previous_scene(self) -> Optional[SceneContext]:
        """Get the previous scene context if available."""
        if len(self.scene_sequence) >= 2 and self.current_scene:
            if self.scene_sequence[-1] == self.current_scene.scene_number:
                prev_num = self.scene_sequence[-2]
                return self.scenes.get(prev_num)
        return None

    def establish_screen_positions_from_prompt(
        self,
        prompt: str,
        frame_id: str,
        characters: List[str]
    ) -> None:
        """Parse prompt text to establish character screen positions.

        Looks for keywords like "screen-left", "screen-right", "facing right", etc.
        """
        if not self.current_scene:
            return

        prompt_lower = prompt.lower()

        for char_tag in characters:
            char_tag_lower = char_tag.lower()

            # Look for position indicators near character mention
            if char_tag_lower in prompt_lower or char_tag.replace("_", " ").lower() in prompt_lower:
                position = ScreenPosition.UNKNOWN
                facing = ""

                # Check for explicit positions
                if "screen-left" in prompt_lower or "screen left" in prompt_lower:
                    position = ScreenPosition.LEFT
                elif "screen-right" in prompt_lower or "screen right" in prompt_lower:
                    position = ScreenPosition.RIGHT
                elif "center" in prompt_lower or "centered" in prompt_lower:
                    position = ScreenPosition.CENTER

                # Check for facing direction
                if "facing right" in prompt_lower or "looks right" in prompt_lower:
                    facing = "right"
                elif "facing left" in prompt_lower or "looks left" in prompt_lower:
                    facing = "left"

                if position != ScreenPosition.UNKNOWN:
                    self.current_scene.establish_character_position(
                        char_tag, position, frame_id, facing
                    )

    def get_shot_suggestions_for_scene(self) -> Dict[str, Any]:
        """Get shot type suggestions for current scene based on rhythm."""
        if not self.current_scene:
            return {"suggestions": [], "analysis": {}}

        suggestions = self.current_scene.get_next_shot_suggestions()
        analysis = self.current_scene.get_shot_rhythm_analysis()

        return {
            "suggestions": suggestions,
            "analysis": analysis,
            "total_shots_in_scene": len(self.current_scene.shot_history)
        }

    def _infer_lighting_from_time(self, time_of_day: str, weather: str = "") -> LightingState:
        """Infer lighting state from time of day."""
        lighting = LightingState(time_of_day=time_of_day)

        time_lower = time_of_day.lower()

        if any(t in time_lower for t in ["dawn", "sunrise", "early morning"]):
            lighting.key_light_direction = "from east"
            lighting.key_light_quality = "soft golden"
            lighting.color_temperature = "warm"
            lighting.atmosphere = "hazy morning"

        elif any(t in time_lower for t in ["morning"]):
            lighting.key_light_direction = "from east"
            lighting.key_light_quality = "bright soft"
            lighting.color_temperature = "neutral warm"

        elif any(t in time_lower for t in ["noon", "midday"]):
            lighting.key_light_direction = "overhead"
            lighting.key_light_quality = "harsh"
            lighting.color_temperature = "neutral"

        elif any(t in time_lower for t in ["afternoon"]):
            lighting.key_light_direction = "from west"
            lighting.key_light_quality = "warm"
            lighting.color_temperature = "warm"

        elif any(t in time_lower for t in ["golden hour", "sunset", "dusk"]):
            lighting.key_light_direction = "from west low"
            lighting.key_light_quality = "golden soft"
            lighting.color_temperature = "very warm"
            lighting.atmosphere = "golden haze"

        elif any(t in time_lower for t in ["evening", "twilight"]):
            lighting.key_light_direction = "ambient"
            lighting.key_light_quality = "dim"
            lighting.color_temperature = "cool blue"

        elif any(t in time_lower for t in ["night", "midnight"]):
            lighting.key_light_direction = "moonlight from above" if not weather else "ambient"
            lighting.key_light_quality = "soft dim"
            lighting.color_temperature = "cool blue"
            lighting.practical_lights = ["lanterns", "candles"]

        # Weather modifications
        if weather:
            weather_lower = weather.lower()
            if "overcast" in weather_lower or "cloudy" in weather_lower:
                lighting.key_light_quality = "diffused soft"
                lighting.atmosphere = "overcast"
            elif "fog" in weather_lower or "mist" in weather_lower:
                lighting.atmosphere = "foggy diffused"
            elif "rain" in weather_lower:
                lighting.atmosphere = "rain wet reflections"

        return lighting

    def _get_time_constraints(self, time_of_day: str) -> List[str]:
        """Get physical constraints based on time of day."""
        constraints = []
        time_lower = time_of_day.lower()

        if any(t in time_lower for t in ["night", "midnight", "evening"]):
            constraints.append("NO direct sunlight - night scene")
            constraints.append("Moon and practical lights (lanterns, candles) for illumination")
            constraints.append("Cool blue color temperature unless near warm light source")

        elif any(t in time_lower for t in ["dawn", "sunrise"]):
            constraints.append("Sun position: low on eastern horizon")
            constraints.append("Long shadows stretching west")
            constraints.append("Golden/orange tones in sky and highlights")

        elif any(t in time_lower for t in ["noon", "midday"]):
            constraints.append("Sun position: directly overhead")
            constraints.append("Minimal shadows (directly under objects)")
            constraints.append("Harsh light, high contrast")

        elif any(t in time_lower for t in ["sunset", "dusk", "golden hour"]):
            constraints.append("Sun position: low on western horizon")
            constraints.append("Long shadows stretching east")
            constraints.append("Golden/orange warm tones dominate")

        return constraints


def create_context_aggregator(world_config: Dict[str, Any]) -> ContextAggregator:
    """Create a context aggregator instance."""
    return ContextAggregator(world_config)
