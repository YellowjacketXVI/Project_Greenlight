"""
Profile Template Agent - Maps image analysis to world_config.json profiles.

This agent takes the output from Gemini 2.5 image analysis and generates
a structured character profile that can be directly written to world_config.json.

Pipeline: Image Analysis (ImageAnalysisResult) → ProfileTemplateAgent → world_config.json update

See .augment-guidelines for the UnifiedReferenceScript API specification.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from greenlight.core.logging_config import get_logger

if TYPE_CHECKING:
    from greenlight.context.context_engine import ContextEngine
    from greenlight.omni_mind.autonomous_agent import ImageAnalysisResult

logger = get_logger("agents.profile_template")


# Character profile template matching world_config.json schema
CHARACTER_PROFILE_TEMPLATE = {
    "tag": "",
    "name": "",
    "role": "",
    "age": "",
    "ethnicity": "",
    "backstory": "",
    "visual_appearance": "",
    "costume": "",
    "physicality": "",
    "personality": "",
    "speech_style": "",
    "emotional_tells": {},
    "relationships": {},
    "arc": {}
}


@dataclass
class ProfileGenerationResult:
    """Result from profile generation."""
    success: bool
    profile: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class ProfileTemplateAgent:
    """
    Agent that maps image analysis output to world_config.json character profiles.
    
    Uses Gemini 2.5 Flash to interpret image analysis and generate structured
    profile data that matches the CharacterProfile schema.
    
    Usage:
        agent = ProfileTemplateAgent(context_engine)
        profile = await agent.generate_character_profile(tag, image_analysis)
        await agent.update_world_config(tag, profile, project_path)
    """
    
    # System prompt for profile generation
    SYSTEM_PROMPT = """You are a character profile generator for a visual storytelling system.

Given an image analysis of a character, generate a structured character profile that matches
the world_config.json schema. Focus on visual and physical attributes that can be observed
from the image.

IMPORTANT:
- Only include information that can be reasonably inferred from the image
- For fields that cannot be determined from the image, leave them empty
- Be specific and detailed about visual appearance, costume, and physicality
- Use descriptive language suitable for image generation prompts

Output ONLY valid JSON matching this schema:
{
    "name": "Character name if visible/inferable, otherwise empty",
    "role": "protagonist/antagonist/supporting/background",
    "age": "Estimated age range (e.g., 'mid-20s', 'elderly')",
    "ethnicity": "Apparent ethnicity/heritage",
    "visual_appearance": "Detailed physical description: face, hair, build, distinguishing features",
    "costume": "Detailed clothing/outfit description",
    "physicality": "Posture, movement style, body language observed",
    "personality": "Personality traits suggested by expression/pose",
    "emotional_tells": {
        "current_emotion": "Description of how this emotion manifests physically"
    }
}"""

    def __init__(
        self,
        context_engine: Optional["ContextEngine"] = None,
        model: str = "gemini-2.5-flash-preview-05-20"
    ):
        """
        Initialize the ProfileTemplateAgent.
        
        Args:
            context_engine: Optional ContextEngine for world context
            model: LLM model to use for profile generation
        """
        self._context_engine = context_engine
        self._model = model
    
    async def generate_character_profile(
        self,
        tag: str,
        image_analysis: "ImageAnalysisResult"
    ) -> Dict[str, Any]:
        """
        Generate a character profile from image analysis.
        
        Args:
            tag: Character tag (e.g., "CHAR_MEI")
            image_analysis: Result from Gemini image analysis
            
        Returns:
            Dict matching CharacterProfile schema
        """
        if not image_analysis.success:
            logger.warning(f"Image analysis failed for {tag}: {image_analysis.error}")
            return self._create_empty_profile(tag)
        
        # Build prompt from image analysis
        prompt = self._build_generation_prompt(tag, image_analysis)
        
        try:
            from greenlight.llm.api_clients import GeminiClient
            client = GeminiClient()
            
            response = await client.generate_text_async(
                prompt=prompt,
                system=self.SYSTEM_PROMPT,
                model=self._model,
                temperature=0.3
            )
            
            if not response:
                logger.error(f"Empty response from LLM for {tag}")
                return self._create_empty_profile(tag)
            
            # Parse JSON response
            profile = self._parse_profile_response(tag, response)
            return profile
            
        except Exception as e:
            logger.error(f"Profile generation failed for {tag}: {e}")
            return self._create_empty_profile(tag)
    
    def _build_generation_prompt(
        self,
        tag: str,
        analysis: "ImageAnalysisResult"
    ) -> str:
        """Build the prompt for profile generation."""
        prompt_parts = [
            f"Generate a character profile for tag: {tag}",
            "",
            "IMAGE ANALYSIS RESULTS:",
            f"Description: {analysis.description}",
        ]

        # Add character details if available
        if analysis.character_details:
            prompt_parts.append("")
            prompt_parts.append("CHARACTER DETAILS FROM ANALYSIS:")
            for char_tag, details in analysis.character_details.items():
                prompt_parts.append(f"  {char_tag}:")
                for key, value in details.items():
                    prompt_parts.append(f"    {key}: {value}")

        # Add style analysis if available
        if analysis.style_analysis:
            prompt_parts.append("")
            prompt_parts.append("STYLE ANALYSIS:")
            for key, value in analysis.style_analysis.items():
                prompt_parts.append(f"  {key}: {value}")

        # Add symbolic notation if available
        if analysis.symbolic_notation:
            prompt_parts.append("")
            prompt_parts.append(f"SYMBOLIC NOTATION: {analysis.symbolic_notation}")

        prompt_parts.append("")
        prompt_parts.append("Generate a complete character profile JSON based on this analysis.")

        return "\n".join(prompt_parts)

    def _parse_profile_response(self, tag: str, response: str) -> Dict[str, Any]:
        """Parse the LLM response into a profile dict."""
        # Clean response - extract JSON if wrapped in markdown
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        try:
            profile = json.loads(response)
            # Ensure tag is set
            profile["tag"] = tag
            return profile
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse profile JSON for {tag}: {e}")
            return self._create_empty_profile(tag)

    def _create_empty_profile(self, tag: str) -> Dict[str, Any]:
        """Create an empty profile with just the tag."""
        profile = CHARACTER_PROFILE_TEMPLATE.copy()
        profile["tag"] = tag
        profile["name"] = tag.replace("CHAR_", "").replace("_", " ").title()
        return profile

    async def update_world_config(
        self,
        tag: str,
        profile: Dict[str, Any],
        project_path: Path
    ) -> bool:
        """
        Update world_config.json with the generated profile.

        Args:
            tag: Character tag
            profile: Generated profile dict
            project_path: Path to project root

        Returns:
            True if update successful
        """
        config_path = project_path / "world_bible" / "world_config.json"

        if not config_path.exists():
            logger.error(f"world_config.json not found at {config_path}")
            return False

        try:
            # Load existing config
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Find and update character
            characters = config.get("characters", [])
            updated = False

            for i, char in enumerate(characters):
                if char.get("tag") == tag:
                    # Merge profile into existing character (preserve existing fields)
                    for key, value in profile.items():
                        if value:  # Only update non-empty values
                            characters[i][key] = value
                    updated = True
                    break

            if not updated:
                # Add new character
                characters.append(profile)
                config["characters"] = characters

                # Update all_tags if present
                if "all_tags" in config and tag not in config["all_tags"]:
                    config["all_tags"].append(tag)

            # Write back
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info(f"Updated world_config.json with profile for {tag}")
            return True

        except Exception as e:
            logger.error(f"Failed to update world_config.json: {e}")
            return False

