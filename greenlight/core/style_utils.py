"""
Unified Style Utilities for Project Greenlight.

Single source of truth for visual style handling across the codebase.
All style-related logic should use these functions instead of duplicating.

Usage:
    from greenlight.core.style_utils import get_style_suffix, map_visual_style

    # Get full style suffix for image generation
    suffix = get_style_suffix(project_path)

    # Map visual_style enum to description
    desc = map_visual_style("anime")
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any

from greenlight.core.logging_config import get_logger

logger = get_logger("core.style_utils")


# =============================================================================
# VISUAL STYLE MAPPINGS (Canonical Definitions)
# =============================================================================

VISUAL_STYLE_MAPPINGS: Dict[str, str] = {
    "live_action": (
        "live action, photorealistic cinematography, 8k quality, dynamic lighting, "
        "RAW photo, DSLR quality, real human actors, NOT 3D animation, NOT CGI, "
        "NOT cartoon, NOT anime, NOT illustrated, realistic skin texture, "
        "natural human proportions, film photography"
    ),
    "anime": (
        "anime style, cel-shaded, vibrant colors, expressive characters, bold linework, "
        "stylized proportions, clean vector art, high contrast colors, dynamic action lines"
    ),
    "animation_2d": (
        "hand-drawn 2D animation, traditional animation aesthetic, painted backgrounds, "
        "fluid motion, artistic linework, watercolor textures, gouache painting, illustrated"
    ),
    "animation_3d": (
        "3D CGI rendering, subsurface scattering, global illumination, volumetric lighting, "
        "high-poly models, realistic textures, ray tracing, cinematic 3D animation"
    ),
    "mixed_reality": (
        "mixed reality, seamless blend of live action and CGI, photorealistic integration, "
        "matched lighting, HDR compositing, practical and digital fusion, photoreal CGI characters"
    ),
}

# Default visual style when none is specified
DEFAULT_VISUAL_STYLE = "live_action"


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def map_visual_style(visual_style: Optional[str]) -> str:
    """Map a visual_style value to its full description.

    Args:
        visual_style: The visual style key (e.g., "anime", "live_action")

    Returns:
        Full description string for prompt generation
    """
    if not visual_style:
        visual_style = DEFAULT_VISUAL_STYLE

    return VISUAL_STYLE_MAPPINGS.get(visual_style, VISUAL_STYLE_MAPPINGS[DEFAULT_VISUAL_STYLE])


def load_world_config(project_path: Path) -> Dict[str, Any]:
    """Load world_config.json from a project.

    Args:
        project_path: Path to the project root directory

    Returns:
        Dictionary containing world config, or empty dict if not found
    """
    world_config_path = Path(project_path) / "world_bible" / "world_config.json"

    if not world_config_path.exists():
        logger.debug(f"No world_config.json found at {world_config_path}")
        return {}

    try:
        return json.loads(world_config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error loading world_config.json: {e}")
        return {}


def get_style_suffix(
    project_path: Optional[Path] = None,
    world_config: Optional[Dict[str, Any]] = None
) -> str:
    """Build a complete style suffix for image generation prompts.

    This is the canonical function for generating style suffixes.
    Combines visual_style mapping with style_notes, lighting, and vibe.

    Args:
        project_path: Path to project (used to load world_config if not provided)
        world_config: Pre-loaded world_config dict (optional, avoids re-reading)

    Returns:
        Complete style suffix string for prompt generation

    Example:
        >>> get_style_suffix(Path("/projects/MyProject"))
        "live action, photorealistic cinematography, 8k quality... Cinematic noir. Lighting: Low key dramatic. Mood: Tense and mysterious"
    """
    # Load world config if not provided
    if world_config is None:
        if project_path is None:
            return map_visual_style(DEFAULT_VISUAL_STYLE)
        world_config = load_world_config(project_path)

    if not world_config:
        return map_visual_style(DEFAULT_VISUAL_STYLE)

    # Extract style components
    visual_style = world_config.get("visual_style", DEFAULT_VISUAL_STYLE)
    style_notes = world_config.get("style_notes", "")
    lighting = world_config.get("lighting", "")
    vibe = world_config.get("vibe", "")

    # Build suffix parts
    parts = [map_visual_style(visual_style)]

    if style_notes:
        parts.append(style_notes)

    if lighting:
        parts.append(f"Lighting: {lighting}")

    if vibe:
        parts.append(f"Mood: {vibe}")

    return ". ".join(parts)


def get_visual_style(
    project_path: Optional[Path] = None,
    world_config: Optional[Dict[str, Any]] = None
) -> str:
    """Get the raw visual_style value from world_config.

    Args:
        project_path: Path to project (used to load world_config if not provided)
        world_config: Pre-loaded world_config dict (optional)

    Returns:
        Visual style key (e.g., "anime", "live_action")
    """
    if world_config is None:
        if project_path is None:
            return DEFAULT_VISUAL_STYLE
        world_config = load_world_config(project_path)

    return world_config.get("visual_style", DEFAULT_VISUAL_STYLE)


def get_style_notes(
    project_path: Optional[Path] = None,
    world_config: Optional[Dict[str, Any]] = None
) -> str:
    """Get the style_notes from world_config.

    Args:
        project_path: Path to project (used to load world_config if not provided)
        world_config: Pre-loaded world_config dict (optional)

    Returns:
        Style notes string, or empty string if not set
    """
    if world_config is None:
        if project_path is None:
            return ""
        world_config = load_world_config(project_path)

    return world_config.get("style_notes", "")


def get_available_styles() -> Dict[str, str]:
    """Get all available visual styles and their descriptions.

    Returns:
        Dictionary mapping style keys to their descriptions
    """
    return VISUAL_STYLE_MAPPINGS.copy()


def validate_visual_style(style: str) -> bool:
    """Check if a visual style value is valid.

    Args:
        style: The style to validate

    Returns:
        True if valid, False otherwise
    """
    return style in VISUAL_STYLE_MAPPINGS


# =============================================================================
# PORTFOLIO LOOK SHEET STYLE (Neutral, No Story Elements)
# =============================================================================

NEUTRAL_STUDIO_LIGHTING = (
    "Professional studio lighting with soft, even illumination. "
    "Clean white or light gray backdrop. Neutral color temperature. "
    "No dramatic shadows, no mood lighting, no colored gels."
)


def get_portfolio_style_suffix(
    project_path: Optional[Path] = None,
    world_config: Optional[Dict[str, Any]] = None
) -> str:
    """Build a NEUTRAL style suffix for portfolio look sheets.

    Unlike get_style_suffix(), this function excludes story-driven elements:
    - NO lighting from world_config (uses neutral studio lighting)
    - NO mood/vibe from world_config
    - NO style_notes that may contain story context

    Only preserves the visual rendering style (live_action, anime, etc.)
    to maintain artistic consistency.

    Args:
        project_path: Path to project (used to load world_config if not provided)
        world_config: Pre-loaded world_config dict (optional)

    Returns:
        Neutral style suffix for portfolio look sheet generation

    Example:
        >>> get_portfolio_style_suffix(Path("/projects/MyProject"))
        "live action, photorealistic cinematography, 8k quality... Professional studio lighting..."
    """
    # Load world config if not provided
    if world_config is None:
        if project_path is None:
            visual_style = DEFAULT_VISUAL_STYLE
        else:
            world_config = load_world_config(project_path)
            visual_style = world_config.get("visual_style", DEFAULT_VISUAL_STYLE) if world_config else DEFAULT_VISUAL_STYLE
    else:
        visual_style = world_config.get("visual_style", DEFAULT_VISUAL_STYLE)

    # Build suffix with ONLY visual style + neutral studio lighting
    parts = [
        map_visual_style(visual_style),
        NEUTRAL_STUDIO_LIGHTING
    ]

    return ". ".join(parts)
