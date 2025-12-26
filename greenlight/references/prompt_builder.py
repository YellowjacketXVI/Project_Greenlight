"""
Reference Prompt Builder

Template-based prompt generation for reference images.
Replaces the LLM-based ReferencePromptAgent for efficiency.

No LLM calls required - uses structured templates with entity data.

v4.0 Enhancements:
- Race/ethnicity context for accurate character depiction
- Age-appropriate appearance modifiers
- Timeline support for flashback scenes
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import TagCategory

logger = get_logger("references.prompt_builder")


class ReferencePromptType(Enum):
    """Types of reference prompts."""
    CHARACTER_SHEET = "character_sheet"
    LOCATION_DIRECTIONAL = "location_directional"
    PROP_SHEET = "prop_sheet"


@dataclass
class ReferencePromptResult:
    """Result from reference prompt generation."""
    tag: str
    category: TagCategory
    prompt_type: ReferencePromptType
    success: bool
    # For characters/props: single multi-view prompt
    reference_sheet_prompt: Optional[str] = None
    # For locations: directional prompts
    reference_prompts: Optional[Dict[str, str]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReferencePromptBuilder:
    """
    Template-based prompt builder for reference images.

    Generates structured prompts without LLM calls.
    Uses entity data from world_config.json directly.

    v4.0: Now includes race/ethnicity and age context for accurate depictions.
    """

    def __init__(
        self,
        context_engine: Optional[Any] = None,
        style_suffix: str = "",
        world_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the prompt builder.

        Args:
            context_engine: Optional ContextEngine for world context
            style_suffix: Visual style suffix to append
            world_config: Optional world config for temporal context
        """
        self._context_engine = context_engine
        self._style_suffix = style_suffix
        self._world_config = world_config
        self._temporal_builder = None

    def set_context_engine(self, context_engine: Any) -> None:
        """Set or update the ContextEngine instance."""
        self._context_engine = context_engine

    def _get_temporal_builder(self):
        """Get or create CharacterTemporalContextBuilder."""
        if self._temporal_builder is None:
            try:
                from greenlight.context.character_temporal_context import CharacterTemporalContextBuilder

                # Get world_config from context engine or stored config
                world_config = self._world_config
                if world_config is None and self._context_engine:
                    try:
                        world_config = self._context_engine.get_world_config() or {}
                    except Exception:
                        world_config = {}

                if world_config:
                    self._temporal_builder = CharacterTemporalContextBuilder(world_config)
            except ImportError:
                logger.warning("CharacterTemporalContextBuilder not available")

        return self._temporal_builder

    def _build_race_ethnicity_context(self, tag: str, character_data: Dict[str, Any]) -> str:
        """
        Build race/ethnicity context string for accurate character depiction.

        Args:
            tag: Character tag
            character_data: Character data from world_config

        Returns:
            Formatted race/ethnicity string for prompt
        """
        parts = []

        # Direct fields from character_data
        race = character_data.get("race", "")
        ethnicity = character_data.get("ethnicity", "")
        nationality = character_data.get("nationality", "")

        # Check identity section (newer format)
        identity = character_data.get("identity", {})
        if not race and identity.get("ethnicity"):
            ethnicity = identity["ethnicity"]
        if not race and identity.get("race"):
            race = identity["race"]

        # Use temporal builder if available (can infer from world setting)
        temporal = self._get_temporal_builder()
        if temporal and not race:
            demo = temporal.get_character_demographics(tag)
            if demo:
                race = demo.race
                ethnicity = ethnicity or demo.ethnicity

        # Build context string
        if race:
            parts.append(race)
        if ethnicity and ethnicity != race:
            parts.append(f"({ethnicity})")

        # Add race-specific visual cues if available
        if race and temporal:
            race_chars = temporal.RACE_CHARACTERISTICS.get(race, {})
            if race_chars:
                cues = []
                if race_chars.get("eye_shape"):
                    cues.append(race_chars["eye_shape"])
                if race_chars.get("hair") and "hair" not in character_data.get("description", "").lower():
                    cues.append(race_chars["hair"])
                if cues:
                    parts.append(f"[{', '.join(cues)}]")

        return " ".join(parts) if parts else ""

    def _build_age_context(self, tag: str, character_data: Dict[str, Any], time_offset: int = 0) -> str:
        """
        Build age context string for age-appropriate depiction.

        Args:
            tag: Character tag
            character_data: Character data from world_config
            time_offset: Years offset from story start (for flashbacks)

        Returns:
            Formatted age string for prompt
        """
        # Get age from character data
        age = character_data.get("age")
        if not age:
            identity = character_data.get("identity", {})
            age = identity.get("age")

        if not age:
            return ""

        # Apply time offset for flashbacks
        if time_offset:
            age = max(0, int(age) + time_offset)

        # Get age category and modifiers
        temporal = self._get_temporal_builder()
        if temporal:
            demo = temporal.get_character_demographics(tag)
            if demo:
                age_cat = demo.get_age_category(int(age))
                age_mods = temporal.AGE_MODIFIERS.get(age_cat, {})

                parts = [f"Age {age}"]
                if age_mods.get("face"):
                    parts.append(f"({age_mods['face']})")
                if age_mods.get("general"):
                    parts.append(age_mods["general"])

                return " - ".join(parts)

        return f"Age {age}"

    def _build_physical_baseline(self, tag: str, character_data: Dict[str, Any]) -> str:
        """
        Build physical baseline description (skin, hair, eyes, build).

        Args:
            tag: Character tag
            character_data: Character data from world_config

        Returns:
            Formatted physical description
        """
        parts = []

        # Check direct fields
        if skin := character_data.get("skin_tone"):
            parts.append(f"{skin} skin")
        if hair := character_data.get("hair_color"):
            parts.append(f"{hair} hair")
        if eyes := character_data.get("eye_color"):
            parts.append(f"{eyes} eyes")
        if height := character_data.get("height"):
            parts.append(f"{height}")
        if build := character_data.get("build"):
            parts.append(f"{build} build")

        # Check visual section (newer format)
        visual = character_data.get("visual", {})
        if not parts:
            if skin := visual.get("skin_tone"):
                parts.append(f"{skin} skin")
            if hair := visual.get("hair_color"):
                parts.append(f"{hair} hair")
            if eyes := visual.get("eye_color"):
                parts.append(f"{eyes} eyes")

        # Get from temporal builder if not in direct data
        if not parts:
            temporal = self._get_temporal_builder()
            if temporal:
                demo = temporal.get_character_demographics(tag)
                if demo:
                    baseline = demo.get_physical_baseline()
                    if baseline:
                        return baseline

        return ", ".join(parts) if parts else ""

    def _get_style_suffix(self) -> str:
        """Get style suffix from context engine or default."""
        if self._style_suffix:
            return self._style_suffix

        if self._context_engine:
            try:
                # Use neutral portfolio style for reference sheets
                from greenlight.core.style_utils import get_portfolio_style_suffix
                project_path = getattr(self._context_engine, '_project_path', None)
                if project_path:
                    return get_portfolio_style_suffix(project_path=project_path)
            except Exception:
                pass

        return "Professional studio lighting with soft, even illumination. Clean white backdrop."

    def build_character_prompt(
        self,
        tag: str,
        character_data: Dict[str, Any],
        time_offset: int = 0
    ) -> ReferencePromptResult:
        """
        Build a multi-angle portfolio look sheet prompt for a character.

        Args:
            tag: Character tag (e.g., CHAR_MEI)
            character_data: Character data from world_config.json
            time_offset: Years offset for flashback scenes (negative = younger)

        Returns:
            ReferencePromptResult with reference_sheet_prompt
        """
        try:
            name = character_data.get('name', tag.replace('CHAR_', '').replace('_', ' ').title())
            style = self._get_style_suffix()

            # === NEW: Build race/ethnicity and age context ===
            race_context = self._build_race_ethnicity_context(tag, character_data)
            age_context = self._build_age_context(tag, character_data, time_offset)
            physical_baseline = self._build_physical_baseline(tag, character_data)

            # Build demographic section
            demographic_parts = []
            if race_context:
                demographic_parts.append(f"Race/Ethnicity: {race_context}")
            if age_context:
                demographic_parts.append(age_context)
            if physical_baseline:
                demographic_parts.append(f"Physical: {physical_baseline}")

            demographic_section = "\n".join(demographic_parts) if demographic_parts else ""

            # Extract additional physical attributes
            physical_parts = []

            # Identity section
            identity = character_data.get("identity", {})

            # Visual section
            visual = character_data.get("visual", {})
            if visual.get("appearance"):
                physical_parts.append(f"Appearance: {visual['appearance']}")
            if visual.get("costume_default"):
                physical_parts.append(f"Costume: {visual['costume_default']}")
            if visual.get("distinguishing_marks"):
                physical_parts.append(f"Distinguishing marks: {visual['distinguishing_marks']}")

            # Distinguishing features (list format)
            if features := character_data.get("distinguishing_features"):
                if isinstance(features, list):
                    features = ", ".join(features)
                physical_parts.append(f"Distinguishing features: {features}")

            # Legacy fields fallback
            if not identity and not visual:
                if character_data.get("description"):
                    physical_parts.append(f"Description: {character_data['description']}")
                if character_data.get("appearance"):
                    physical_parts.append(f"Appearance: {character_data['appearance']}")
                if character_data.get("costume"):
                    physical_parts.append(f"Costume: {character_data['costume']}")

            physical_desc = ". ".join(physical_parts) if physical_parts else ""

            # Combine demographic and physical description
            full_description_parts = []
            if demographic_section:
                full_description_parts.append(demographic_section)
            if physical_desc:
                full_description_parts.append(physical_desc)

            full_description = "\n\n".join(full_description_parts) if full_description_parts else "Character reference"

            # Build the prompt with enhanced context
            prompt = f"""Character portfolio look sheet for [{tag}] - {name}.

{full_description}

Multi-angle reference sheet layout:
- Top row: 6 head/face views (front, 3/4 left, 3/4 right, profile left, profile right, back)
- Bottom row: 5 full body views showing rotation from front to back
- Clean white background with professional studio lighting
- Neutral expression, clear view of costume and distinguishing features
- Each view labeled with angle
- IMPORTANT: Maintain consistent racial/ethnic features across all views
- IMPORTANT: Age-appropriate features and proportions for specified age

{style}"""

            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.CHARACTER,
                prompt_type=ReferencePromptType.CHARACTER_SHEET,
                success=True,
                reference_sheet_prompt=prompt.strip(),
                metadata={
                    "method": "template_v4",
                    "race_context": race_context,
                    "age_context": age_context,
                    "time_offset": time_offset
                }
            )

        except Exception as e:
            logger.error(f"Failed to build character prompt for {tag}: {e}")
            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.CHARACTER,
                prompt_type=ReferencePromptType.CHARACTER_SHEET,
                success=False,
                error=str(e)
            )

    def build_location_prompts(
        self,
        tag: str,
        location_data: Dict[str, Any]
    ) -> ReferencePromptResult:
        """
        Build directional prompts for a location (N/E/S/W).

        Args:
            tag: Location tag (e.g., LOC_PALACE)
            location_data: Location data from world_config.json

        Returns:
            ReferencePromptResult with reference_prompts dict
        """
        try:
            name = location_data.get('name', tag.replace('LOC_', '').replace('_', ' ').title())

            # Extract location details
            description = location_data.get("description", "")
            spatial = location_data.get("spatial_layout", "")
            architecture = location_data.get("architectural_style", "")
            atmosphere = location_data.get("atmosphere", "")
            lighting = location_data.get("lighting", "")
            features = location_data.get("key_features", [])
            if isinstance(features, list):
                features = ", ".join(features)

            # Build base context
            context_parts = [f"[{tag}] - {name}"]
            if description:
                context_parts.append(description)
            if architecture:
                context_parts.append(f"Architectural style: {architecture}")
            if atmosphere:
                context_parts.append(f"Atmosphere: {atmosphere}")
            if features:
                context_parts.append(f"Key features: {features}")

            base_context = ". ".join(context_parts)

            # Get existing directional notes if any
            directional = location_data.get("directional_views", {})

            # Build directional prompts
            prompts = {
                "north": f"""North view (primary establishing shot) of {base_context}.
{directional.get('north', 'Main entrance perspective, showing primary architectural features.')}
{f'Lighting: {lighting}' if lighting else 'Natural lighting appropriate to the setting.'}""",

                "east": f"""East view of {base_context}.
Camera facing east within the location. {directional.get('east', 'View showing eastern features and architecture.')}
Maintain consistent lighting and atmosphere with north view.""",

                "south": f"""South view of {base_context}.
Camera facing south, opposite from main entrance. {directional.get('south', 'View showing southern features and depth.')}
Maintain consistent lighting and atmosphere with north view.""",

                "west": f"""West view of {base_context}.
Camera facing west within the location. {directional.get('west', 'View showing western features and architecture.')}
Maintain consistent lighting and atmosphere with north view."""
            }

            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.LOCATION,
                prompt_type=ReferencePromptType.LOCATION_DIRECTIONAL,
                success=True,
                reference_prompts=prompts,
                metadata={"method": "template"}
            )

        except Exception as e:
            logger.error(f"Failed to build location prompts for {tag}: {e}")
            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.LOCATION,
                prompt_type=ReferencePromptType.LOCATION_DIRECTIONAL,
                success=False,
                error=str(e)
            )

    def build_prop_prompt(
        self,
        tag: str,
        prop_data: Dict[str, Any]
    ) -> ReferencePromptResult:
        """
        Build a multi-angle portfolio look sheet prompt for a prop.

        Args:
            tag: Prop tag (e.g., PROP_SWORD)
            prop_data: Prop data from world_config.json

        Returns:
            ReferencePromptResult with reference_sheet_prompt
        """
        try:
            name = prop_data.get('name', tag.replace('PROP_', '').replace('_', ' ').title())
            style = self._get_style_suffix()

            # Extract prop details
            prop_parts = []
            if prop_data.get("description"):
                prop_parts.append(prop_data['description'])
            if prop_data.get("materials"):
                materials = prop_data['materials']
                if isinstance(materials, list):
                    materials = ", ".join(materials)
                prop_parts.append(f"Materials: {materials}")
            if prop_data.get("size") or prop_data.get("dimensions"):
                prop_parts.append(f"Size: {prop_data.get('size') or prop_data.get('dimensions')}")
            if prop_data.get("distinguishing_features"):
                prop_parts.append(f"Features: {prop_data['distinguishing_features']}")
            if prop_data.get("condition"):
                prop_parts.append(f"Condition: {prop_data['condition']}")

            prop_desc = ". ".join(prop_parts) if prop_parts else "Prop reference"

            # Build the prompt
            prompt = f"""Prop portfolio look sheet for [{tag}] - {name}.

{prop_desc}

Multi-angle reference sheet layout:
- Front view (primary angle)
- Side view left and right
- Top view (bird's eye)
- Back view
- Detail shots of key features
- Scale reference included
- Clean white background with professional studio lighting
- Product photography style with soft, even illumination
- Each view labeled with angle

{style}"""

            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.PROP,
                prompt_type=ReferencePromptType.PROP_SHEET,
                success=True,
                reference_sheet_prompt=prompt.strip(),
                metadata={"method": "template"}
            )

        except Exception as e:
            logger.error(f"Failed to build prop prompt for {tag}: {e}")
            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.PROP,
                prompt_type=ReferencePromptType.PROP_SHEET,
                success=False,
                error=str(e)
            )

    def build_prompt(
        self,
        tag: str,
        category: TagCategory,
        entity_data: Dict[str, Any]
    ) -> ReferencePromptResult:
        """
        Build reference prompt(s) for any tag category.

        Main entry point that routes to category-specific methods.

        Args:
            tag: Tag identifier (e.g., CHAR_MEI, LOC_PALACE, PROP_SWORD)
            category: Tag category
            entity_data: Entity data from world_config.json

        Returns:
            ReferencePromptResult
        """
        if category == TagCategory.CHARACTER:
            return self.build_character_prompt(tag, entity_data)
        elif category == TagCategory.LOCATION:
            return self.build_location_prompts(tag, entity_data)
        elif category == TagCategory.PROP:
            return self.build_prop_prompt(tag, entity_data)
        else:
            return ReferencePromptResult(
                tag=tag,
                category=category,
                prompt_type=ReferencePromptType.CHARACTER_SHEET,
                success=False,
                error=f"Unsupported category: {category.value}"
            )

    def build_all_prompts(
        self,
        entities: Dict[str, Dict[str, Any]],
        category: TagCategory
    ) -> List[ReferencePromptResult]:
        """
        Build prompts for multiple entities of the same category.

        Args:
            entities: Dict mapping tag -> entity_data
            category: Tag category for all entities

        Returns:
            List of ReferencePromptResult
        """
        return [
            self.build_prompt(tag, category, data)
            for tag, data in entities.items()
        ]


# Convenience function matching the old agent interface
def build_reference_prompt(
    tag: str,
    category: TagCategory,
    entity_data: Dict[str, Any],
    context_engine: Optional[Any] = None
) -> ReferencePromptResult:
    """
    Build a reference prompt without LLM calls.

    Drop-in replacement for ReferencePromptAgent.generate_prompt().
    """
    builder = ReferencePromptBuilder(context_engine=context_engine)
    return builder.build_prompt(tag, category, entity_data)
