"""
Notation Patterns for Directing Phase

Regex patterns for frame notation system in Visual_Script output.

## Scene.Frame.Camera Notation System

The unified notation format is: `{scene}.{frame}.{camera}`

| Component | Position | Format | Examples |
|-----------|----------|--------|----------|
| Scene     | X.x.x    | Integer | 1.x.x, 2.x.x, 8.x.x |
| Frame     | x.X.x    | Integer | x.1.x, x.2.x, x.15.x |
| Camera    | x.x.X    | Letter  | x.x.cA, x.x.cB, x.x.cC |

Full ID Examples:
- 1.1.cA = Scene 1, Frame 1, Camera A
- 1.2.cB = Scene 1, Frame 2, Camera B
- 2.3.cC = Scene 2, Frame 3, Camera C
"""

import re
from typing import Dict, Pattern, Tuple, Optional


# =============================================================================
# SCENE.FRAME.CAMERA NOTATION PATTERNS
# =============================================================================

SCENE_FRAME_CAMERA_PATTERNS: Dict[str, str] = {
    # Full camera ID: [1.2.cA]
    "full_id": r"\[(\d+)\.(\d+)\.c([A-Z])\]",
    # Full ID with shot type: [1.2.cA] (Wide)
    "full_id_with_type": r"\[(\d+)\.(\d+)\.c([A-Z])\]\s*\(([^)]+)\)",
    # Scene.frame only: 1.2
    "scene_frame": r"(\d+)\.(\d+)",
    # Camera block: [1.1.cA] (Wide) cA. PROMPT...
    "camera_block": r"\[(\d+\.\d+\.c[A-Z])\]\s*\(([^)]+)\)\s*c[A-Z]\.\s*([^\[]+)",
    # Scene marker: ## Scene 1: (SCENE-ONLY ARCHITECTURE - no beat markers)
    "scene_marker": r"##\s*Scene\s+(\d+):",
}


# =============================================================================
# REGEX PATTERNS FOR DIRECTING PHASE (Legacy + New)
# =============================================================================

REGEX_PATTERNS: Dict[str, str] = {
    # Frame identification - OLD format (deprecated, for backward compatibility)
    "frame_id": r"\{frame_(\d+)\.(\d+)\}",
    # Frame identification - NEW format (scene.frame.camera)
    "frame_id_new": r"\[(\d+)\.(\d+)\.c([A-Z])\]",

    # Scene frame chunk delimiters
    "frame_chunk_start": r"\(/scene_frame_chunk_start/\)",
    "frame_chunk_end": r"\(/scene_frame_chunk_end/\)",

    # Technical notations
    "camera": r"\[CAM:\s*([^\]]+)\]",
    "position": r"\[POS:\s*([^\]]+)\]",
    "lighting": r"\[LIGHT:\s*([^\]]+)\]",
    "prompt": r"\[PROMPT:\s*([^\]]+)\]",

    # Tag patterns - all 6 canonical prefixes (mandatory brackets per notation standard)
    "character_tag": r"\[CHAR_[A-Z0-9_]+\]",
    "location_tag": r"\[LOC_[A-Z0-9_]+\]",
    "prop_tag": r"\[PROP_[A-Z0-9_]+\]",
    "concept_tag": r"\[CONCEPT_[A-Z0-9_]+\]",
    "event_tag": r"\[EVENT_[A-Z0-9_]+\]",
    "environment_tag": r"\[ENV_[A-Z0-9_]+\]",

    # Generic pattern to match any tag with canonical prefix
    "any_tag": r"\[(CHAR_|LOC_|PROP_|CONCEPT_|EVENT_|ENV_)[A-Z0-9_]+\]",

    # Tag patterns for extraction (with capture groups)
    "tag_bracketed": r"\[([A-Z][A-Z0-9_]+)\]",
    "tag_char": r"\[(CHAR_[A-Z0-9_]+)\]",
    "tag_loc": r"\[(LOC_[A-Z0-9_]+)\]",
    "tag_prop": r"\[(PROP_[A-Z0-9_]+)\]",
    "tag_concept": r"\[(CONCEPT_[A-Z0-9_]+)\]",
    "tag_event": r"\[(EVENT_[A-Z0-9_]+)\]",
    "tag_env": r"\[(ENV_[A-Z0-9_]+)\]",

    # Scene markers
    "scene_break": r"---\s*SCENE\s+(\d+)\s*---",
    "scene_header": r"^##\s+Scene\s+(\d+)",
}


# =============================================================================
# FRAME NOTATION MARKERS
# =============================================================================

FRAME_NOTATION_MARKERS = {
    # NEW scene.frame.camera format (canonical)
    "frame_id_template": "[{scene}.{frame}.c{camera}]",
    # DEPRECATED: Old format - kept for reference only, do not use
    # "frame_id_template_deprecated": "{{frame_{scene}.{frame}}}",
    "chunk_start": "(/scene_frame_chunk_start/)",
    "chunk_end": "(/scene_frame_chunk_end/)",
    "camera_template": "[CAM: {instruction}]",
    "position_template": "[POS: {positions}]",
    "lighting_template": "[LIGHT: {lighting}]",
    "prompt_template": "[PROMPT: {prompt}]",
    # Camera block template with shot type
    "camera_block_template": "[{scene}.{frame}.c{camera}] ({shot_type})",
}


# =============================================================================
# COMPILED PATTERNS
# =============================================================================

def get_compiled_patterns() -> Dict[str, Pattern]:
    """Get compiled regex patterns for efficient matching."""
    return {
        name: re.compile(pattern, re.MULTILINE)
        for name, pattern in REGEX_PATTERNS.items()
    }


# =============================================================================
# PATTERN UTILITIES
# =============================================================================

def extract_frame_id(text: str) -> list:
    """Extract all frame IDs from text (supports both old and new formats)."""
    # Try new format first: [1.2.cA]
    new_pattern = re.compile(REGEX_PATTERNS["frame_id_new"])
    new_matches = new_pattern.findall(text)
    if new_matches:
        return new_matches

    # Fallback to old format: {frame_1.2}
    old_pattern = re.compile(REGEX_PATTERNS["frame_id"])
    return old_pattern.findall(text)


def extract_camera_ids(text: str) -> list:
    """Extract all scene.frame.camera IDs from text.

    Returns list of tuples: (scene, frame, camera_letter)
    """
    pattern = re.compile(SCENE_FRAME_CAMERA_PATTERNS["full_id"])
    return pattern.findall(text)


def extract_frame_chunks(text: str) -> list:
    """Extract all frame chunks from text."""
    start_pattern = re.compile(REGEX_PATTERNS["frame_chunk_start"])
    end_pattern = re.compile(REGEX_PATTERNS["frame_chunk_end"])

    chunks = []
    starts = list(start_pattern.finditer(text))
    ends = list(end_pattern.finditer(text))

    for start, end in zip(starts, ends):
        chunk_text = text[start.end():end.start()].strip()
        chunks.append(chunk_text)

    return chunks


def parse_camera_id(camera_id: str) -> Optional[Tuple[int, int, str]]:
    """Parse a camera ID string into components.

    Args:
        camera_id: Camera ID like "1.2.cA" or "[1.2.cA]"

    Returns:
        Tuple of (scene, frame, camera_letter) or None if invalid
    """
    # Remove brackets if present
    clean_id = camera_id.strip("[]")

    match = re.match(r"(\d+)\.(\d+)\.c([A-Z])", clean_id)
    if match:
        return (int(match.group(1)), int(match.group(2)), match.group(3))
    return None


def format_camera_id(scene_num: int, frame_num: int, camera_letter: str = "A") -> str:
    """Format a camera ID in scene.frame.camera format.

    Args:
        scene_num: Scene number (1-based)
        frame_num: Frame number (1-based)
        camera_letter: Camera letter (A, B, C, etc.)

    Returns:
        Camera ID like "1.2.cA"
    """
    return f"{scene_num}.{frame_num}.c{camera_letter}"


def format_camera_notation_block(scene_num: int, frame_num: int,
                                  camera_letter: str = "A",
                                  shot_type: str = "Wide") -> str:
    """Format a full camera notation block.

    Returns:
        Notation like "[1.2.cA] (Wide)"
    """
    return f"[{scene_num}.{frame_num}.c{camera_letter}] ({shot_type})"


def format_frame_id(scene_num: int, frame_num: int) -> str:
    """Format a frame ID string (OLD format - DEPRECATED).

    ⚠️ DEPRECATED: This function uses the old {frame_X.Y} format.
    Use format_camera_id() or format_camera_block() for new scene.frame.camera format.

    See DEPRECATION_PLAN.md for migration instructions.
    """
    import warnings
    warnings.warn(
        "format_frame_id() uses deprecated {frame_X.Y} format. "
        "Use format_camera_id() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return f"{{frame_{scene_num}.{frame_num}}}"


def format_frame_id_new(scene_num: int, frame_num: int) -> str:
    """Format a frame ID in new scene.frame format."""
    return f"{scene_num}.{frame_num}"


def format_camera_notation(instruction: str) -> str:
    """Format a camera notation string."""
    return f"[CAM: {instruction}]"


def format_position_notation(positions: str) -> str:
    """Format a position notation string."""
    return f"[POS: {positions}]"


def format_lighting_notation(lighting: str) -> str:
    """Format a lighting notation string."""
    return f"[LIGHT: {lighting}]"


def format_prompt_notation(prompt: str) -> str:
    """Format a prompt notation string."""
    return f"[PROMPT: {prompt}]"

