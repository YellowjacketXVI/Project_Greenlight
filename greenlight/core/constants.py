"""
Greenlight Constants

Global constants used throughout the Project Greenlight system.
"""

from enum import Enum, auto
from typing import Dict, List

# =============================================================================
# VERSION INFO
# =============================================================================
VERSION = "2.0.0"
PROJECT_NAME = "Project Greenlight"

# =============================================================================
# TAG SYSTEM CONSTANTS
# =============================================================================

class TagCategory(Enum):
    """Categories for story element tags."""
    CHARACTER = "character"
    LOCATION = "location"
    PROP = "prop"
    CONCEPT = "concept"
    EVENT = "event"

class TagPrefix(Enum):
    """Standard prefixes for tag types."""
    CHARACTER = "CHAR_"
    LOCATION = "LOC_"
    PROP = "PROP_"
    CONCEPT = "CONCEPT_"
    EVENT = "EVENT_"
    ENVIRONMENT = "ENV_"

# Tag validation regex pattern
TAG_PATTERN = r'\[([A-Z][A-Z0-9_]*)\]'
TAG_FORMAT_PATTERN = r'^[A-Z][A-Z0-9_]*$'

# Directional suffixes for locations
DIRECTION_SUFFIXES = ['_DIR_N', '_DIR_E', '_DIR_S', '_DIR_W']
VALID_DIRECTIONS = ['N', 'E', 'S', 'W']

# Consensus threshold for multi-agent tag validation
# 60% = 3/5 agents must agree for a tag to be accepted
TAG_CONSENSUS_THRESHOLD = 0.6

# =============================================================================
# VISUAL STYLE CONSTANTS
# =============================================================================

class VisualStyle(Enum):
    """Visual style options for storyboard generation."""
    LIVE_ACTION = "live_action"
    ANIME = "anime"
    ANIMATION_2D = "animation_2d"
    ANIMATION_3D = "animation_3d"
    MIXED_REALITY = "mixed_reality"

VISUAL_STYLE_NAMES = {
    VisualStyle.LIVE_ACTION: "Live Action",
    VisualStyle.ANIME: "Anime",
    VisualStyle.ANIMATION_2D: "2D Animation",
    VisualStyle.ANIMATION_3D: "3D Animation",
    VisualStyle.MIXED_REALITY: "Mixed Reality",
}

# =============================================================================
# SCENE/FRAME/CAMERA NOTATION
# =============================================================================

class NotationType(Enum):
    """Types of notation in the director pipeline."""
    SCENE = "scene"
    FRAME = "frame"
    CAMERA = "camera"

# =============================================================================
# ID SYSTEM - Hierarchical Naming Convention
# =============================================================================
#
# Hierarchy: Scene → Frame → Camera
#
# ## Scene.Frame.Camera Notation System (CANONICAL)
#
# The unified notation format is: `{scene}.{frame}.c{letter}`
#
# | Component | Position | Format | Examples |
# |-----------|----------|--------|----------|
# | Scene     | X.x.x    | Integer | 1, 2, 8 |
# | Frame     | x.X.x    | Integer | 1.1, 1.2, 2.3 |
# | Camera    | x.x.X    | Letter  | 1.1.cA, 1.2.cB, 2.3.cC |
#
# Format:
#   Scene:  {scene_number}           (e.g., 1, 2, 8)
#   Frame:  {scene}.{frame}          (e.g., 1.1, 1.2, 2.3)
#   Camera: {scene}.{frame}.c{letter} (e.g., 1.1.cA, 1.1.cB, 2.3.cC)
#   Beat:   scene.{N}.{XX}           (e.g., scene.1.01) - for beat markers
#
# Examples:
#   1                       - Scene 1
#   1.1                     - Scene 1, Frame 1
#   1.1.cA                  - Scene 1, Frame 1, Camera A
#   1.1.cB                  - Scene 1, Frame 1, Camera B (different angle)
#   1.2.cA                  - Scene 1, Frame 2, Camera A
#   2.1.cA                  - Scene 2, Frame 1, Camera A
#   scene.1.01              - Beat marker: Scene 1, Beat 1
#
# Director Pipeline operates at Camera level:
#   Input:  Frames (1.1, 1.2, 2.1)
#   Output: Cameras (1.1.cA, 1.1.cB, 1.2.cA, 1.2.cB, 1.2.cC)

# ID Patterns (Canonical Format per .augment-guidelines)
SCENE_ID_PATTERN = r'^(\d+)$'  # Just scene number: 1, 2, 8
FRAME_ID_PATTERN = r'^(\d+)\.(\d+)$'  # scene.frame: 1.1, 2.3
CAMERA_ID_PATTERN = r'^(\d+)\.(\d+)\.c([A-Z])$'  # scene.frame.cX: 1.1.cA
BEAT_ID_PATTERN = r'^scene\.(\d+)\.(\d+)$'  # Beat marker: scene.1.01

# Legacy notation patterns (for backward compatibility)
LEGACY_SCENE_NOTATION_PATTERN = r'\(S(\d{2})\)'
LEGACY_FRAME_NOTATION_PATTERN = r'\(F(\d{2})\)'
LEGACY_CAMERA_NOTATION_PATTERN = r'\(c([A-Z])\)'
LEGACY_FULL_NOTATION_PATTERN = r'\(S(\d{2})\)\.\(F(\d{2})\)\.\(c([A-Z])\)'
LEGACY_FRAME_ID_PATTERN = r'^(\d+)\.frame\.(\d+)$'  # Old 1.frame.01 format

# Camera angle identifiers
CAMERA_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']

# =============================================================================
# STORY STRUCTURE CONSTANTS
# =============================================================================

class StoryLayer(Enum):
    """Layers in the story building engine."""
    PLOT_ARCHITECTURE = "plot_architecture"
    CHARACTER_ARCHITECTURE = "character_architecture"
    STORY_NOVELLING = "story_novelling"
    CONTINUITY_VALIDATION = "continuity_validation"
    MOTIVATIONAL_COHERENCE = "motivational_coherence"

class SceneBoundaryType(Enum):
    """Types of scene boundaries."""
    LOCATION_CHANGE = "location_change"
    TIME_JUMP = "time_jump"
    POV_SHIFT = "pov_shift"
    NARRATIVE_BREAK = "narrative_break"

class ValidationStatus(Enum):
    """Status of validation checks."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVISION = "needs_revision"

# Act structure percentages (3-act structure)
ACT_STRUCTURE = {
    1: 0.25,  # Act 1: 25% (setup)
    2: 0.50,  # Act 2: 50% (confrontation)
    3: 0.25,  # Act 3: 25% (resolution)
}

# =============================================================================
# QUALITY CHECK CONSTANTS
# =============================================================================

class IssueLevel(Enum):
    """Severity levels for quality issues."""
    CRITICAL = "critical"    # Must fix
    WARNING = "warning"      # Should fix
    SUGGESTION = "suggestion"  # Nice to fix

# Vague words to flag in prompts
VAGUE_WORDS = {
    "beautiful", "nice", "good", "bad", "great", "amazing", "wonderful",
    "lovely", "pretty", "ugly", "interesting", "cool", "awesome",
    "terrible", "horrible", "fantastic", "incredible", "stunning",
    "gorgeous", "magnificent", "spectacular"
}

# Symbolic/abstract terms to flag
SYMBOLIC_TERMS = {
    "mysterious", "enigmatic", "ethereal", "transcendent", "sublime",
    "profound", "ineffable", "indescribable", "otherworldly"
}

# =============================================================================
# LLM CONFIGURATION CONSTANTS
# =============================================================================

class LLMProvider(Enum):
    """Supported LLM providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    GROK = "grok"
    LOCAL = "local"

class LLMFunction(Enum):
    """Functions that can be routed to specific LLMs."""
    STORY_GENERATION = "story_generation"
    STORY_ANALYSIS = "story_analysis"
    BEAT_WRITING = "beat_writing"
    DIRECTOR = "director"
    TAG_VALIDATION = "tag_validation"
    CONTINUITY = "continuity"
    RESEARCH = "research"
    ASSISTANT_REASONING = "assistant_reasoning"
    QUICK_RESPONSE = "quick_response"
    # Assistant bridge functions
    ASSISTANT = "assistant"  # Main assistant chat responses
    ASSISTANT_QUERY = "assistant_query"  # Context-aware query handling
    ASSISTANT_COMMAND = "assistant_command"  # Command interpretation

# Default token limits
DEFAULT_MAX_TOKENS = 4096
CONTEXT_WINDOW_LIMIT = 100000

# =============================================================================
# FILE PATHS AND NAMES
# =============================================================================

# Standard file names
WORLD_BIBLE_FILE = "WORLD_BIBLE.json"
STORY_DOCUMENT_FILE = "STORY_DOCUMENT.md"
STORYBOARD_PROMPTS_FILE = "storyboard_prompts.md"
SCENE_STRUCTURE_FILE = "scene_structure.json"
FRAME_COMPOSITION_FILE = "frame_composition.json"
PLOT_OUTLINE_FILE = "plot_outline.json"
CHARACTER_ARCS_FILE = "character_arcs.json"
QUALITY_REPORT_FILE = "quality_check_report.json"

# Directory names
SEASONS_DIR_PREFIX = "SEASON_"
EPISODES_DIR_PREFIX = "EPISODE_"
CHUNKS_DIR = "chunks"
REFERENCES_DIR = "references"
GENERATED_DIR = "generated"

# =============================================================================
# PROJECT DIRECTORY STRUCTURE
# =============================================================================
# Standard project directory scaffolding
# All processes should use these constants for consistency

# Base directories (shared across all project types)
PROJECT_BASE_DIRS = [
    "world_bible",      # Core story definitions: pitch.md, world_config.json, style_guide.md
    "characters",       # Character JSON definition files
    "locations",        # Location JSON definition files
    "assets",           # Visual assets and resources
    "references",       # Reference images organized by tag: references/{TAG}/
]

# Single project directories (in addition to base)
PROJECT_SINGLE_DIRS = [
    "scripts",          # Story scripts: script.md
    "beats",            # Story beats: beat_sheet.json, plot_structure.json
    "shots",            # Shot breakdowns
    "prompts",          # Generated prompts
    "storyboards",      # Storyboard layouts
    "storyboard_output",  # Generated storyboard images
]

# Series episode directories (per episode)
PROJECT_EPISODE_DIRS = [
    "scripts",
    "beats",
    "shots",
    "prompts",
    "storyboards",
]

# Hidden/system directories
PROJECT_SYSTEM_DIRS = [
    ".health",          # Health reports and diagnostics
    ".cache",           # Vector cache storage
    ".archive",         # Archived/deprecated content
]

# Reference subdirectory structure
# References are organized by TAG: references/{TAG}/
# e.g., references/CHAR_MEI/, references/LOC_TEAHOUSE/, references/PROP_SWORD/
# Each tag directory contains:
#   - Reference images (*.png, *.jpg, *.jpeg, *.webp)
#   - .key file (stores path to starred/key reference)
#   - .labeled file (tracks which images have been auto-labeled)

def get_reference_dir_for_tag(project_path, tag: str):
    """Get the reference directory for a specific tag.

    Args:
        project_path: Path to project root
        tag: Tag name (e.g., 'CHAR_MEI', 'LOC_TEAHOUSE')

    Returns:
        Path to the tag's reference directory
    """
    from pathlib import Path
    ref_dir = Path(project_path) / REFERENCES_DIR / tag
    ref_dir.mkdir(parents=True, exist_ok=True)
    return ref_dir

def ensure_project_structure(project_path, is_series: bool = False):
    """Ensure all standard project directories exist.

    Args:
        project_path: Path to project root
        is_series: Whether this is a series project

    Returns:
        List of created directories
    """
    from pathlib import Path
    project_path = Path(project_path)
    created = []

    # Create base directories
    for dir_name in PROJECT_BASE_DIRS:
        dir_path = project_path / dir_name
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            created.append(str(dir_path))

    # Create single project directories (if not series)
    if not is_series:
        for dir_name in PROJECT_SINGLE_DIRS:
            dir_path = project_path / dir_name
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                created.append(str(dir_path))

    # Create system directories
    for dir_name in PROJECT_SYSTEM_DIRS:
        dir_path = project_path / dir_name
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            created.append(str(dir_path))

    return created

