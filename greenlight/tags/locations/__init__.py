"""
Greenlight Tags - Locations Module

Location tag extraction, directional consensus, and spatial continuity.

Structure:
    /prompts/
        /01_extraction/     - Tag extraction prompts
        /02_validation/     - Tag validation prompts
        /03_directional/    - Directional tag selection prompts
        /04_spatial/        - Spatial anchor detection prompts
    /scripts/
        location_tagger.py              - Location-specific tagging logic
        location_directional_consensus.py - Directional tag selection
        location_spatial_continuity.py  - Spatial continuity tracking
    /reference_scripts/
        location_reference_generator.py - Location reference image generation
    location_tag_manager.py - Main location tag manager
"""

from greenlight.tags.locations.location_tag_manager import LocationTagManager

__all__ = [
    'LocationTagManager',
]

