"""
References Prompts Module

Externalized prompts for reference image generation.

Prompt Organization:
    01_character/   - Character reference sheet prompts
    02_location/    - Location directional view prompts
    03_prop/        - Prop reference sheet prompts
    04_analysis/    - Image analysis prompts (for generate-from-image)

Usage:
    from greenlight.core.prompt_loader import PromptLoader
    
    # Load a prompt
    prompt = PromptLoader.load("references/prompts/01_character", "character_sheet_prompt")
    
    # Load with TAG_NAMING_RULES injected
    prompt = PromptLoader.load_with_tag_rules("references/prompts/01_character", "character_reference_prompt")
"""

__all__ = []

