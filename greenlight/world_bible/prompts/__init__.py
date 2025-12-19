"""
World Bible Prompts Module

Externalized prompts for the World Bible pipeline, organized by entity type.

Prompt Organization:
    01_character/   - Character research and profile generation
    02_location/    - Location research and profile generation
    03_prop/        - Prop research and profile generation
    04_global/      - Global context and world rules
    05_synthesis/   - Profile synthesis and merging
    06_continuity/  - Cross-tag relationship validation

Usage:
    from greenlight.core.prompt_loader import PromptLoader
    
    # Load a prompt
    prompt = PromptLoader.load("world_bible/prompts/01_character", "character_research_prompt")
    
    # Load with TAG_NAMING_RULES injected
    prompt = PromptLoader.load_with_tag_rules("world_bible/prompts/01_character", "character_profile_prompt")
"""

__all__ = []

