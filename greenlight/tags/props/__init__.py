"""
Greenlight Tags - Props Module

Prop tag extraction, validation, and reference generation.

Structure:
    /prompts/
        /01_extraction/     - Tag extraction prompts
        /02_validation/     - Tag validation prompts
        /03_enrichment/     - Profile enrichment prompts
    /scripts/
        prop_tagger.py      - Prop-specific tagging logic
    /reference_scripts/
        prop_reference_generator.py - Prop reference image generation
    prop_tag_manager.py - Main prop tag manager
"""

from greenlight.tags.props.prop_tag_manager import PropTagManager

__all__ = [
    'PropTagManager',
]

