"""
Greenlight Character Temporal Context

Handles character demographics and timeline-aware appearances:
- Race/ethnicity for accurate visual representation
- Age at different points in the story
- Timeline-based appearance variations (younger/older)
- Physical changes over time (scars, hair, weight, etc.)

Ensures consistent, age-appropriate character depictions across all frames.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import re

from greenlight.core.logging_config import get_logger

logger = get_logger("context.character_temporal")


class AgeCategory(Enum):
    """Age categories for visual reference."""
    CHILD = "child"           # 0-12
    ADOLESCENT = "adolescent" # 13-17
    YOUNG_ADULT = "young_adult"  # 18-25
    ADULT = "adult"           # 26-45
    MIDDLE_AGED = "middle_aged"  # 46-60
    ELDERLY = "elderly"       # 61+


@dataclass
class CharacterDemographics:
    """
    Character demographic information for accurate visual representation.

    This data should be included in world_config characters for proper
    context generation.
    """
    tag: str
    name: str

    # Core demographics
    race: str = ""              # e.g., "East Asian", "Chinese", "Japanese", "Korean"
    ethnicity: str = ""         # More specific if needed
    nationality: str = ""       # Country/region of origin

    # Age information
    base_age: int = 0           # Age at story start
    birth_year: Optional[int] = None  # For timeline calculations

    # Physical baseline
    skin_tone: str = ""         # e.g., "fair", "olive", "tan", "dark"
    hair_color_natural: str = ""  # Natural hair color
    eye_color: str = ""         # Eye color
    height: str = ""            # e.g., "petite", "average", "tall"
    build: str = ""             # e.g., "slender", "athletic", "stocky"

    # Distinguishing features (permanent)
    distinguishing_features: List[str] = field(default_factory=list)

    # Age-specific appearance notes
    appearance_by_age: Dict[str, str] = field(default_factory=dict)
    # e.g., {"child": "round-faced, short hair", "adult": "angular features, long hair"}

    def get_age_category(self, age: int = None) -> AgeCategory:
        """Get age category for given age or base age."""
        age = age or self.base_age

        if age <= 12:
            return AgeCategory.CHILD
        elif age <= 17:
            return AgeCategory.ADOLESCENT
        elif age <= 25:
            return AgeCategory.YOUNG_ADULT
        elif age <= 45:
            return AgeCategory.ADULT
        elif age <= 60:
            return AgeCategory.MIDDLE_AGED
        else:
            return AgeCategory.ELDERLY

    def get_race_context(self) -> str:
        """Get formatted race/ethnicity context for prompts."""
        parts = []

        if self.race:
            parts.append(self.race)
        if self.ethnicity and self.ethnicity != self.race:
            parts.append(f"({self.ethnicity})")
        if self.nationality:
            parts.append(f"from {self.nationality}")

        return " ".join(parts) if parts else ""

    def get_physical_baseline(self) -> str:
        """Get physical baseline description."""
        parts = []

        if self.skin_tone:
            parts.append(f"{self.skin_tone} skin")
        if self.hair_color_natural:
            parts.append(f"{self.hair_color_natural} hair")
        if self.eye_color:
            parts.append(f"{self.eye_color} eyes")
        if self.height:
            parts.append(f"{self.height} height")
        if self.build:
            parts.append(f"{self.build} build")

        return ", ".join(parts) if parts else ""


@dataclass
class TimelineAppearance:
    """Character appearance at a specific point in timeline."""
    age: int
    age_category: AgeCategory

    # Appearance at this age
    appearance_notes: str = ""
    hair_style: str = ""
    hair_color: str = ""  # May differ from natural (dyed, grayed)
    facial_features: str = ""
    body_changes: str = ""
    clothing_style: str = ""

    # Acquired features by this age
    scars: List[str] = field(default_factory=list)
    tattoos: List[str] = field(default_factory=list)
    other_changes: List[str] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Convert to context string for prompts."""
        parts = [f"Age {self.age} ({self.age_category.value}):"]

        if self.appearance_notes:
            parts.append(f"  {self.appearance_notes}")
        if self.hair_style or self.hair_color:
            hair = f"{self.hair_color} {self.hair_style}".strip()
            if hair:
                parts.append(f"  Hair: {hair}")
        if self.facial_features:
            parts.append(f"  Face: {self.facial_features}")
        if self.body_changes:
            parts.append(f"  Body: {self.body_changes}")
        if self.scars:
            parts.append(f"  Scars: {', '.join(self.scars)}")

        return "\n".join(parts)


@dataclass
class StoryTimeline:
    """Timeline information for a story."""
    story_start_year: Optional[int] = None
    current_scene_year: Optional[int] = None
    time_period: str = ""  # e.g., "Ancient China", "1920s Shanghai"

    # Scene-specific time offsets
    scene_time_offsets: Dict[int, int] = field(default_factory=dict)
    # e.g., {1: 0, 5: -10, 10: 5} means scene 5 is 10 years before start


class CharacterTemporalContextBuilder:
    """
    Builds timeline-aware character context for accurate visual representation.

    Ensures characters are depicted with:
    - Correct race/ethnicity features
    - Age-appropriate appearance
    - Timeline-consistent changes (scars, aging, etc.)

    Usage:
        builder = CharacterTemporalContextBuilder(world_config)

        # Get context for a specific scene
        context = builder.get_character_appearance_context(
            "CHAR_MEI",
            scene_number=5,
            time_offset=-10  # 10 years before main story
        )
    """

    # Age-related appearance modifiers
    AGE_MODIFIERS = {
        AgeCategory.CHILD: {
            "face": "round, soft features, youthful proportions",
            "skin": "smooth, unblemished",
            "body": "small, developing",
            "general": "childlike innocence in expression"
        },
        AgeCategory.ADOLESCENT: {
            "face": "features becoming more defined, possible acne",
            "skin": "young, may have adolescent skin issues",
            "body": "gangly, still developing",
            "general": "youthful energy, sometimes awkward"
        },
        AgeCategory.YOUNG_ADULT: {
            "face": "defined features, at peak attractiveness",
            "skin": "smooth, healthy glow",
            "body": "fully developed, energetic",
            "general": "vitality and youthful confidence"
        },
        AgeCategory.ADULT: {
            "face": "mature features, subtle lines beginning",
            "skin": "healthy, slight signs of age",
            "body": "mature, settled physique",
            "general": "confident, established presence"
        },
        AgeCategory.MIDDLE_AGED: {
            "face": "visible wrinkles, possible gray at temples",
            "skin": "showing age, possible spots",
            "body": "possible weight changes, less taut",
            "general": "wisdom in expression, dignified bearing"
        },
        AgeCategory.ELDERLY: {
            "face": "deep wrinkles, sagging, age spots",
            "skin": "thin, weathered, wrinkled",
            "body": "possible frailty, stooped posture",
            "general": "elderly dignity, lived experience visible"
        }
    }

    # Race/ethnicity visual characteristics (for accurate representation)
    RACE_CHARACTERISTICS = {
        "East Asian": {
            "eye_shape": "almond-shaped, epicanthic fold",
            "hair": "straight black hair typical",
            "skin_range": "fair to light tan",
            "facial_structure": "flat facial profile, high cheekbones"
        },
        "Chinese": {
            "eye_shape": "almond-shaped eyes with single or double eyelid",
            "hair": "straight black hair",
            "skin_range": "fair to olive",
            "facial_structure": "varied, often round or oval face"
        },
        "Japanese": {
            "eye_shape": "almond-shaped, often with double eyelid",
            "hair": "straight black or dark brown",
            "skin_range": "fair to light",
            "facial_structure": "often softer features"
        },
        "Korean": {
            "eye_shape": "almond-shaped, often monolid",
            "hair": "straight black hair",
            "skin_range": "fair, often pale",
            "facial_structure": "often high cheekbones, v-line jaw"
        },
        "Southeast Asian": {
            "eye_shape": "almond-shaped, varied eyelid types",
            "hair": "straight to wavy black hair",
            "skin_range": "tan to brown",
            "facial_structure": "varied, often broader nose"
        },
        "South Asian": {
            "eye_shape": "large, expressive",
            "hair": "black, thick, often wavy",
            "skin_range": "light brown to dark brown",
            "facial_structure": "varied features"
        },
        "Middle Eastern": {
            "eye_shape": "large, often dark",
            "hair": "dark, often thick and wavy",
            "skin_range": "olive to brown",
            "facial_structure": "strong nose, defined features"
        },
        "African": {
            "eye_shape": "varied",
            "hair": "tightly coiled to wavy",
            "skin_range": "light brown to dark",
            "facial_structure": "varied, often fuller lips"
        },
        "European": {
            "eye_shape": "varied",
            "hair": "varied colors and textures",
            "skin_range": "fair to olive",
            "facial_structure": "varied"
        },
        "Latin American": {
            "eye_shape": "varied",
            "hair": "varied, often dark",
            "skin_range": "varied, mestizo common",
            "facial_structure": "mixed heritage visible"
        }
    }

    def __init__(self, world_config: Dict[str, Any]):
        """
        Initialize with world configuration.

        Args:
            world_config: World configuration dictionary
        """
        self.world_config = world_config
        self._demographics: Dict[str, CharacterDemographics] = {}
        self._timeline = self._build_timeline()
        self._build_demographics()

    def _build_timeline(self) -> StoryTimeline:
        """Build story timeline from world_config."""
        world_details = self.world_config.get("world_details", {})
        time_period = world_details.get("time_period", {})

        return StoryTimeline(
            time_period=time_period.get("era", self.world_config.get("time_period", ""))
        )

    def _build_demographics(self) -> None:
        """Build demographics from world_config characters."""
        for char in self.world_config.get("characters", []):
            tag = char.get("tag", "")
            if not tag:
                continue

            # Extract demographics from character data
            demographics = CharacterDemographics(
                tag=tag,
                name=char.get("name", tag.replace("CHAR_", "")),
                race=char.get("race", ""),
                ethnicity=char.get("ethnicity", ""),
                nationality=char.get("nationality", ""),
                base_age=char.get("age", 0),
                birth_year=char.get("birth_year"),
                skin_tone=char.get("skin_tone", ""),
                hair_color_natural=char.get("hair_color", ""),
                eye_color=char.get("eye_color", ""),
                height=char.get("height", ""),
                build=char.get("build", ""),
                distinguishing_features=char.get("distinguishing_features", []),
                appearance_by_age=char.get("appearance_by_age", {})
            )

            # If race not specified, try to infer from setting
            if not demographics.race:
                demographics.race = self._infer_race_from_setting(char)

            self._demographics[tag] = demographics

    def _infer_race_from_setting(self, char: Dict[str, Any]) -> str:
        """Infer race from world setting if not specified."""
        # Check world_details for cultural context
        world_details = self.world_config.get("world_details", {})
        cultural = world_details.get("cultural_context", {})

        # Check time_period and world_rules for hints
        time_period = self.world_config.get("time_period", "")
        world_rules = self.world_config.get("world_rules", "")

        setting_text = f"{time_period} {world_rules}".lower()

        # Infer from setting keywords
        if any(kw in setting_text for kw in ["china", "chinese", "dynasty", "tang", "ming", "qing", "han"]):
            return "Chinese"
        elif any(kw in setting_text for kw in ["japan", "japanese", "samurai", "shogun", "edo", "meiji"]):
            return "Japanese"
        elif any(kw in setting_text for kw in ["korea", "korean", "joseon", "goryeo"]):
            return "Korean"
        elif any(kw in setting_text for kw in ["east asia", "asian"]):
            return "East Asian"
        elif any(kw in setting_text for kw in ["india", "indian", "hindu", "mughal"]):
            return "South Asian"
        elif any(kw in setting_text for kw in ["arabia", "arab", "persian", "ottoman"]):
            return "Middle Eastern"
        elif any(kw in setting_text for kw in ["africa", "african"]):
            return "African"
        elif any(kw in setting_text for kw in ["europe", "european", "medieval", "victorian"]):
            return "European"

        return ""

    def get_character_demographics(self, tag: str) -> Optional[CharacterDemographics]:
        """Get demographics for a character."""
        return self._demographics.get(tag)

    def get_character_age_at_scene(
        self,
        tag: str,
        scene_number: int = None,
        time_offset: int = 0
    ) -> int:
        """
        Get character's age at a specific scene.

        Args:
            tag: Character tag
            scene_number: Scene number (for scene-specific offsets)
            time_offset: Years offset from story start

        Returns:
            Character's age at that point
        """
        demo = self._demographics.get(tag)
        if not demo:
            return 0

        base_age = demo.base_age

        # Apply scene-specific offset if available
        if scene_number and scene_number in self._timeline.scene_time_offsets:
            time_offset = self._timeline.scene_time_offsets[scene_number]

        return max(0, base_age + time_offset)

    def get_appearance_at_age(
        self,
        tag: str,
        age: int = None,
        time_offset: int = 0
    ) -> TimelineAppearance:
        """
        Get character appearance at a specific age.

        Args:
            tag: Character tag
            age: Specific age (if None, uses base_age + offset)
            time_offset: Years offset from base age

        Returns:
            TimelineAppearance for that age
        """
        demo = self._demographics.get(tag)
        if not demo:
            return TimelineAppearance(age=0, age_category=AgeCategory.ADULT)

        # Calculate age
        if age is None:
            age = demo.base_age + time_offset
        age = max(0, age)

        age_category = demo.get_age_category(age)

        # Get age modifiers
        modifiers = self.AGE_MODIFIERS.get(age_category, {})

        # Build appearance
        appearance = TimelineAppearance(
            age=age,
            age_category=age_category,
            appearance_notes=demo.appearance_by_age.get(age_category.value, ""),
            hair_color=demo.hair_color_natural,
            facial_features=modifiers.get("face", "")
        )

        # Apply aging effects
        if age_category in [AgeCategory.MIDDLE_AGED, AgeCategory.ELDERLY]:
            if demo.hair_color_natural and "black" in demo.hair_color_natural.lower():
                appearance.hair_color = f"{demo.hair_color_natural} with gray"

        return appearance

    def get_character_appearance_context(
        self,
        tag: str,
        scene_number: int = None,
        time_offset: int = 0,
        include_race: bool = True,
        include_age_details: bool = True
    ) -> str:
        """
        Get full character appearance context for a scene.

        This is the primary method for getting character visual context.

        Args:
            tag: Character tag
            scene_number: Current scene number
            time_offset: Years offset from story start
            include_race: Include race/ethnicity context
            include_age_details: Include age-specific details

        Returns:
            Formatted context string for image prompts
        """
        demo = self._demographics.get(tag)
        if not demo:
            return f"[{tag}]: No demographic data available"

        # Get age at this point
        age = self.get_character_age_at_scene(tag, scene_number, time_offset)
        appearance = self.get_appearance_at_age(tag, age)

        parts = [f"[{tag}] ({demo.name}):"]

        # Race/ethnicity
        if include_race:
            race_context = demo.get_race_context()
            if race_context:
                parts.append(f"  Race/Ethnicity: {race_context}")

                # Add race-specific visual characteristics
                race_chars = self.RACE_CHARACTERISTICS.get(demo.race, {})
                if race_chars:
                    char_notes = []
                    if race_chars.get("eye_shape"):
                        char_notes.append(f"eyes: {race_chars['eye_shape']}")
                    if race_chars.get("hair"):
                        char_notes.append(f"hair: {race_chars['hair']}")
                    if char_notes:
                        parts.append(f"  Racial features: {', '.join(char_notes)}")

        # Age
        if include_age_details:
            parts.append(f"  Age: {age} ({appearance.age_category.value})")

            # Age-appropriate modifiers
            age_mods = self.AGE_MODIFIERS.get(appearance.age_category, {})
            if age_mods:
                parts.append(f"  Age appearance: {age_mods.get('general', '')}")

        # Physical baseline
        baseline = demo.get_physical_baseline()
        if baseline:
            parts.append(f"  Physical: {baseline}")

        # Distinguishing features
        if demo.distinguishing_features:
            parts.append(f"  Distinguishing: {', '.join(demo.distinguishing_features)}")

        # Hair at this age
        if appearance.hair_color:
            parts.append(f"  Hair: {appearance.hair_color}")

        return "\n".join(parts)

    def get_scene_character_context(
        self,
        character_tags: List[str],
        scene_number: int = None,
        time_offset: int = 0,
        focal_character: str = None
    ) -> str:
        """
        Get appearance context for all characters in a scene.

        Args:
            character_tags: List of character tags
            scene_number: Scene number
            time_offset: Years offset
            focal_character: Primary character (gets more detail)

        Returns:
            Combined character appearance context
        """
        parts = ["=== CHARACTER APPEARANCES ==="]

        # Add time context if offset
        if time_offset != 0:
            if time_offset < 0:
                parts.append(f"(Scene set {abs(time_offset)} years BEFORE main story)")
            else:
                parts.append(f"(Scene set {time_offset} years AFTER story start)")

        for tag in character_tags:
            include_full = (tag == focal_character)
            context = self.get_character_appearance_context(
                tag,
                scene_number=scene_number,
                time_offset=time_offset,
                include_race=True,
                include_age_details=include_full
            )
            parts.append("")
            parts.append(context)

        return "\n".join(parts)

    def validate_character_demographics(self) -> Dict[str, List[str]]:
        """
        Validate that characters have proper demographic info.

        Returns:
            Dict of character tags to list of missing fields
        """
        issues: Dict[str, List[str]] = {}

        for tag, demo in self._demographics.items():
            char_issues = []

            if not demo.race:
                char_issues.append("race not specified")
            if not demo.base_age:
                char_issues.append("age not specified")
            if not demo.skin_tone:
                char_issues.append("skin_tone not specified")
            if not demo.hair_color_natural:
                char_issues.append("hair_color not specified")
            if not demo.eye_color:
                char_issues.append("eye_color not specified")

            if char_issues:
                issues[tag] = char_issues

        return issues

    def get_recommended_character_fields(self) -> Dict[str, str]:
        """Get recommended fields for character demographic data."""
        return {
            "race": "e.g., 'Chinese', 'Japanese', 'Korean', 'East Asian', 'European'",
            "ethnicity": "More specific ethnic background if relevant",
            "age": "Age at story start (integer)",
            "skin_tone": "e.g., 'fair', 'olive', 'tan', 'dark', 'porcelain'",
            "hair_color": "Natural hair color, e.g., 'black', 'brown', 'auburn'",
            "eye_color": "e.g., 'brown', 'dark brown', 'hazel'",
            "height": "e.g., 'petite', 'average', 'tall'",
            "build": "e.g., 'slender', 'athletic', 'stocky', 'curvy'",
            "distinguishing_features": "List of permanent features like scars, birthmarks",
            "appearance_by_age": "Dict of age_category -> appearance notes for flashbacks"
        }


# Convenience functions
def create_temporal_context_builder(world_config: Dict[str, Any]) -> CharacterTemporalContextBuilder:
    """Create a character temporal context builder."""
    return CharacterTemporalContextBuilder(world_config)


def get_character_appearance_for_scene(
    world_config: Dict[str, Any],
    character_tags: List[str],
    scene_number: int = None,
    time_offset: int = 0
) -> str:
    """
    Quick function to get character appearance context.

    Args:
        world_config: World configuration
        character_tags: Characters in scene
        scene_number: Scene number
        time_offset: Years offset from story start

    Returns:
        Formatted appearance context
    """
    builder = CharacterTemporalContextBuilder(world_config)
    return builder.get_scene_character_context(
        character_tags, scene_number, time_offset
    )


def validate_character_demographics(world_config: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Validate character demographic completeness.

    Args:
        world_config: World configuration

    Returns:
        Dict of character tags to list of missing fields
    """
    builder = CharacterTemporalContextBuilder(world_config)
    return builder.validate_character_demographics()
