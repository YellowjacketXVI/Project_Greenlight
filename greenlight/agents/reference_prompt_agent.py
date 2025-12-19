"""
Reference Prompt Agent

Generates optimized, detailed multi-angle reference sheet prompts for tags
using Gemini 2.5 Flash for cost efficiency.

Supports category-specific prompt generation:
- Characters: Multi-angle character sheets with identity consistency
- Locations: Directional views (N/E/S/W) with spatial relationships
- Props: Multi-angle product shots with material details
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import TagCategory

logger = get_logger("agents.reference_prompt")


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
    reference_prompts: Optional[Dict[str, str]] = None  # {"north": ..., "east": ..., etc.}
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReferencePromptAgent:
    """
    Agent for generating optimized reference image prompts.

    Uses Gemini 2.5 Flash for cost-efficient prompt generation.
    Generates category-specific prompts based on tag context from world_config.json.
    """

    # Gemini 2.5 Flash model ID (updated Dec 2025)
    MODEL_ID = "gemini-2.5-flash-preview-05-20"
    MODEL_ID_FALLBACK = "gemini-2.0-flash"  # Fallback if preview model unavailable

    def __init__(
        self,
        api_key: Optional[str] = None,
        context_engine: Optional[Any] = None
    ):
        """
        Initialize the ReferencePromptAgent.

        Args:
            api_key: Gemini API key (defaults to env var)
            context_engine: Optional ContextEngine for world context
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._context_engine = context_engine

        if not self.api_key:
            logger.warning("No Gemini API key found. ReferencePromptAgent will not function.")

    def set_context_engine(self, context_engine: Any) -> None:
        """Set or update the ContextEngine instance."""
        self._context_engine = context_engine

    def _get_world_style(self) -> str:
        """Get world style context from ContextEngine."""
        if self._context_engine is None:
            return ""
        try:
            return self._context_engine.get_world_style()
        except Exception:
            return ""

    def _call_gemini(self, prompt: str, system_prompt: str = "") -> str:
        """Call Gemini 2.5 Flash API with fallback to stable model."""
        from greenlight.llm.api_clients import GeminiClient

        client = GeminiClient(api_key=self.api_key, show_spinner=False)

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        # Try primary model first, fall back to stable model if unavailable
        for model_id in [self.MODEL_ID, self.MODEL_ID_FALLBACK]:
            try:
                response = client.generate_text(
                    prompt=full_prompt,
                    temperature=0.7,
                    max_tokens=4096,
                    model=model_id
                )
                return response.text
            except Exception as e:
                if "404" in str(e) or "not found" in str(e).lower():
                    logger.warning(f"Model {model_id} not available, trying fallback...")
                    continue
                raise

        raise RuntimeError(f"All Gemini models failed: {self.MODEL_ID}, {self.MODEL_ID_FALLBACK}")

    async def generate_character_prompt(
        self,
        tag: str,
        character_data: Dict[str, Any]
    ) -> ReferencePromptResult:
        """
        Generate a multi-angle character sheet prompt.

        Args:
            tag: Character tag (e.g., CHAR_MEI)
            character_data: Character data from world_config.json

        Returns:
            ReferencePromptResult with reference_sheet_prompt
        """
        try:
            world_style = self._get_world_style()

            # Build character context
            char_context = self._build_character_context(tag, character_data)

            system_prompt = """You are an expert at creating detailed image generation prompts
for character reference sheets. Your prompts should be specific, visual, and optimized
for AI image generation models like Seedream and FLUX."""

            prompt = f"""Generate a detailed multi-angle CHARACTER REFERENCE SHEET prompt for:

TAG: [{tag}]
{char_context}

WORLD STYLE: {world_style if world_style else "Cinematic, detailed, professional"}

Create a comprehensive prompt that specifies:

1. VIEWS TO INCLUDE:
   - Front view (face forward, neutral expression)
   - 3/4 left view (45 degrees left)
   - 3/4 right view (45 degrees right)
   - Profile left (90 degrees left)
   - Profile right (90 degrees right)
   - Back view (full back)

2. DETAILS TO CAPTURE:
   - Facial features and expressions
   - Full body proportions and posture
   - Costume/clothing details with colors
   - Hair style, color, and texture
   - Distinguishing marks or accessories

3. LAYOUT SPECIFICATIONS:
   - Top row: 6 head/face rotation frames (1:1 ratio each)
   - Bottom row: 5 full body rotation frames (2:5 ratio each)
   - Clean white/neutral background
   - Consistent lighting across all views
   - Label each view angle

Output ONLY the final prompt text, ready for image generation. No explanations."""

            response = self._call_gemini(prompt, system_prompt)

            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.CHARACTER,
                prompt_type=ReferencePromptType.CHARACTER_SHEET,
                success=True,
                reference_sheet_prompt=response.strip(),
                metadata={"model": self.MODEL_ID}
            )

        except Exception as e:
            logger.error(f"Failed to generate character prompt for {tag}: {e}")
            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.CHARACTER,
                prompt_type=ReferencePromptType.CHARACTER_SHEET,
                success=False,
                error=str(e)
            )

    def _build_character_context(self, tag: str, data: Dict[str, Any]) -> str:
        """Build character context string from data for reference image generation.

        Simplified structure focusing on visual attributes only:
        - age, ethnicity, appearance, costume

        Excludes non-visual fields (emotional_tells, physicality) that don't
        contribute to reference sheet generation.
        """
        parts = [f"NAME: {data.get('name', tag.replace('CHAR_', '').replace('_', ' ').title())}"]

        # Check for character_visuals consolidated field first
        character_visuals = data.get("character_visuals", {})
        if character_visuals:
            if character_visuals.get("age"):
                parts.append(f"AGE: {character_visuals['age']}")
            if character_visuals.get("ethnicity"):
                parts.append(f"ETHNICITY: {character_visuals['ethnicity']}")
            if character_visuals.get("appearance"):
                parts.append(f"APPEARANCE: {character_visuals['appearance']}")
            if character_visuals.get("costume"):
                parts.append(f"COSTUME: {character_visuals['costume']}")
            return "\n".join(parts)

        # Fallback: Try identity/visual nested schema
        identity = data.get("identity", {})
        visual = data.get("visual", {})

        if identity or visual:
            if identity.get("age"):
                parts.append(f"AGE: {identity['age']}")
            if identity.get("ethnicity"):
                parts.append(f"ETHNICITY: {identity['ethnicity']}")
            if visual.get("appearance"):
                parts.append(f"APPEARANCE: {visual['appearance']}")
            if visual.get("costume_default"):
                parts.append(f"COSTUME: {visual['costume_default']}")
            return "\n".join(parts)

        # Fallback: Legacy flat fields (most common in current world_config.json)
        if data.get("age"):
            parts.append(f"AGE: {data['age']}")
        if data.get("ethnicity"):
            parts.append(f"ETHNICITY: {data['ethnicity']}")
        if data.get("appearance") or data.get("visual_appearance"):
            appearance = data.get("appearance") or data.get("visual_appearance", "")
            parts.append(f"APPEARANCE: {appearance}")
        elif data.get("description"):
            # Last resort: use description as appearance
            parts.append(f"APPEARANCE: {data['description']}")
        if data.get("costume"):
            parts.append(f"COSTUME: {data['costume']}")

        return "\n".join(parts)

    async def generate_location_prompts(
        self,
        tag: str,
        location_data: Dict[str, Any]
    ) -> ReferencePromptResult:
        """
        Generate directional prompts for a location (N/E/S/W).

        Args:
            tag: Location tag (e.g., LOC_PALACE)
            location_data: Location data from world_config.json

        Returns:
            ReferencePromptResult with reference_prompts dict
        """
        try:
            world_style = self._get_world_style()
            loc_context = self._build_location_context(tag, location_data)

            system_prompt = """You are an expert at creating detailed image generation prompts
for location reference images. Your prompts should capture spatial relationships,
architectural details, and atmosphere for consistent scene generation."""

            prompt = f"""Generate FOUR directional reference prompts for this location:

TAG: [{tag}]
{loc_context}

WORLD STYLE: {world_style if world_style else "Cinematic, detailed, professional"}

Create prompts for each cardinal direction. The NORTH view is the primary/default view.
Subsequent directions should describe how the view changes when rotating from North.

Output as JSON with this exact structure:
{{
    "north": "Detailed prompt for North view (primary/default view)...",
    "east": "Turn 90 degrees right from North. Detailed prompt showing...",
    "south": "Turn 180 degrees from North. Detailed prompt showing...",
    "west": "Turn 90 degrees left from North. Detailed prompt showing..."
}}

Each prompt should include:
- Spatial layout and architectural elements visible from that direction
- Lighting conditions and atmosphere
- Key landmarks or features visible from that angle
- Depth and perspective cues
- Style consistency notes

Output ONLY the JSON, no explanations."""

            response = self._call_gemini(prompt, system_prompt)

            # Parse JSON response
            try:
                # Clean up response
                text = response.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]

                prompts = json.loads(text.strip())

                # Validate structure
                required_keys = {"north", "east", "south", "west"}
                if not required_keys.issubset(prompts.keys()):
                    raise ValueError(f"Missing directional keys. Got: {prompts.keys()}")

            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse location prompts JSON: {e}")
                # Fallback: use response as north prompt
                prompts = {
                    "north": response.strip(),
                    "east": f"East view of [{tag}]: Turn 90 degrees right from the primary view.",
                    "south": f"South view of [{tag}]: Turn 180 degrees from the primary view.",
                    "west": f"West view of [{tag}]: Turn 90 degrees left from the primary view."
                }

            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.LOCATION,
                prompt_type=ReferencePromptType.LOCATION_DIRECTIONAL,
                success=True,
                reference_prompts=prompts,
                metadata={"model": self.MODEL_ID}
            )

        except Exception as e:
            logger.error(f"Failed to generate location prompts for {tag}: {e}")
            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.LOCATION,
                prompt_type=ReferencePromptType.LOCATION_DIRECTIONAL,
                success=False,
                error=str(e)
            )

    def _build_location_context(self, tag: str, data: Dict[str, Any]) -> str:
        """Build location context string from data."""
        parts = [f"NAME: {data.get('name', tag.replace('LOC_', '').replace('_', ' ').title())}"]

        if data.get("description"):
            parts.append(f"DESCRIPTION: {data['description']}")
        if data.get("spatial_layout"):
            parts.append(f"SPATIAL LAYOUT: {data['spatial_layout']}")
        if data.get("architectural_style"):
            parts.append(f"ARCHITECTURAL STYLE: {data['architectural_style']}")
        if data.get("atmosphere"):
            parts.append(f"ATMOSPHERE: {data['atmosphere']}")
        if data.get("lighting"):
            parts.append(f"LIGHTING: {data['lighting']}")
        if data.get("key_features"):
            features = data['key_features']
            if isinstance(features, list):
                features = ", ".join(features)
            parts.append(f"KEY FEATURES: {features}")

        # Existing directional views if any
        directional = data.get("directional_views", {})
        if directional:
            for direction, desc in directional.items():
                parts.append(f"{direction.upper()} VIEW NOTES: {desc}")

        return "\n".join(parts)

    async def generate_prop_prompt(
        self,
        tag: str,
        prop_data: Dict[str, Any]
    ) -> ReferencePromptResult:
        """
        Generate a multi-angle prop reference sheet prompt.

        Args:
            tag: Prop tag (e.g., PROP_SWORD)
            prop_data: Prop data from world_config.json

        Returns:
            ReferencePromptResult with reference_sheet_prompt
        """
        try:
            world_style = self._get_world_style()
            prop_context = self._build_prop_context(tag, prop_data)

            system_prompt = """You are an expert at creating detailed image generation prompts
for prop/object reference sheets. Your prompts should capture materials, scale,
and functional details for consistent prop generation."""

            prompt = f"""Generate a detailed multi-angle PROP REFERENCE SHEET prompt for:

TAG: [{tag}]
{prop_context}

WORLD STYLE: {world_style if world_style else "Cinematic, detailed, professional"}

Create a comprehensive prompt that specifies:

1. VIEWS TO INCLUDE:
   - Front view (primary angle)
   - Side view left
   - Side view right
   - Top view (bird's eye)
   - Back view
   - Detail shots (close-ups of key features)

2. DETAILS TO CAPTURE:
   - Material properties (metal, wood, fabric, etc.)
   - Surface textures and finishes
   - Color palette and variations
   - Scale reference (show relative size)
   - Functional elements and mechanisms
   - Wear, damage, or unique characteristics

3. LAYOUT SPECIFICATIONS:
   - Clean white/neutral background
   - Consistent lighting (soft, even illumination)
   - Product photography style
   - Label each view angle
   - Include scale reference where appropriate

Output ONLY the final prompt text, ready for image generation. No explanations."""

            response = self._call_gemini(prompt, system_prompt)

            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.PROP,
                prompt_type=ReferencePromptType.PROP_SHEET,
                success=True,
                reference_sheet_prompt=response.strip(),
                metadata={"model": self.MODEL_ID}
            )

        except Exception as e:
            logger.error(f"Failed to generate prop prompt for {tag}: {e}")
            return ReferencePromptResult(
                tag=tag,
                category=TagCategory.PROP,
                prompt_type=ReferencePromptType.PROP_SHEET,
                success=False,
                error=str(e)
            )

    def _build_prop_context(self, tag: str, data: Dict[str, Any]) -> str:
        """Build prop context string from data."""
        parts = [f"NAME: {data.get('name', tag.replace('PROP_', '').replace('_', ' ').title())}"]

        if data.get("description"):
            parts.append(f"DESCRIPTION: {data['description']}")
        if data.get("materials"):
            materials = data['materials']
            if isinstance(materials, list):
                materials = ", ".join(materials)
            parts.append(f"MATERIALS: {materials}")
        if data.get("purpose"):
            parts.append(f"PURPOSE: {data['purpose']}")
        if data.get("size") or data.get("dimensions"):
            parts.append(f"SIZE: {data.get('size') or data.get('dimensions')}")
        if data.get("distinguishing_features"):
            parts.append(f"DISTINGUISHING FEATURES: {data['distinguishing_features']}")
        if data.get("condition"):
            parts.append(f"CONDITION: {data['condition']}")

        return "\n".join(parts)

    async def generate_prompt(
        self,
        tag: str,
        category: TagCategory,
        entity_data: Dict[str, Any]
    ) -> ReferencePromptResult:
        """
        Generate reference prompt(s) for any tag category.

        Main entry point that routes to category-specific methods.

        Args:
            tag: Tag identifier (e.g., CHAR_MEI, LOC_PALACE, PROP_SWORD)
            category: Tag category
            entity_data: Entity data from world_config.json

        Returns:
            ReferencePromptResult
        """
        if category == TagCategory.CHARACTER:
            return await self.generate_character_prompt(tag, entity_data)
        elif category == TagCategory.LOCATION:
            return await self.generate_location_prompts(tag, entity_data)
        elif category == TagCategory.PROP:
            return await self.generate_prop_prompt(tag, entity_data)
        else:
            # Unsupported category - return error
            return ReferencePromptResult(
                tag=tag,
                category=category,
                prompt_type=ReferencePromptType.CHARACTER_SHEET,
                success=False,
                error=f"Unsupported category: {category.value}"
            )

    async def generate_all_prompts(
        self,
        entities: Dict[str, Dict[str, Any]],
        category: TagCategory
    ) -> List[ReferencePromptResult]:
        """
        Generate prompts for multiple entities of the same category.

        Args:
            entities: Dict mapping tag -> entity_data
            category: Tag category for all entities

        Returns:
            List of ReferencePromptResult
        """
        import asyncio

        tasks = [
            self.generate_prompt(tag, category, data)
            for tag, data in entities.items()
        ]

        return await asyncio.gather(*tasks)
