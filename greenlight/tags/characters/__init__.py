"""
Greenlight Tags - Characters Module

Character tag extraction, validation, and reference generation.

Structure:
    /prompts/
        /01_extraction/     - Tag extraction prompts
        /02_validation/     - Tag validation prompts
        /03_enrichment/     - Profile enrichment prompts
    /scripts/
        character_tagger.py - Character-specific tagging logic
    /reference_scripts/
        character_reference_generator.py - Character reference image generation
    character_tag_manager.py - Main character tag manager
"""

from greenlight.tags.characters.character_tag_manager import CharacterTagManager

__all__ = [
    'CharacterTagManager',
]

