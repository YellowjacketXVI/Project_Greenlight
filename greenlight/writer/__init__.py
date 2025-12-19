"""
Greenlight Writer Module

The Writer pipeline transforms a pitch into a complete script with scenes.

Pipeline Flow:
    Pitch (pitch.md) → Writer Pipeline → Script (scripts/script.md)

Key Components:
    - StoryPipeline: Main 4-layer story building engine
    - ConsensusTagExtractor: 5-agent consensus for tag extraction
    - SceneGenerator: Converts plot points to scenes
    - QualityOrchestrator: Quality assurance patterns

Directory Structure:
    /prompts/           - Externalized prompt templates
        /01_parsing/    - Input parsing prompts
        /02_tags/       - Tag extraction prompts
        /03_plot/       - Plot architecture prompts
        /04_character/  - Character architecture prompts
        /05_scenes/     - Scene generation prompts
        /06_quality/    - Quality assurance prompts
    /agents/            - Writer-specific agents
    writer_pipeline.py  - Main pipeline (re-exported from pipelines/)

Outputs:
    - scripts/script.md: Final script with scene notation
    - world_config.json: Extracted tags and world data
"""

# Re-export main pipeline for convenience
from greenlight.pipelines.story_pipeline import (
    StoryPipeline,
    StoryInput,
    StoryOutput,
    PlotPoint,
    CharacterArc,
    Scene,
)

# Re-export tag extraction
from greenlight.tags import (
    ConsensusTagger,
    ConsensusResult,
    TagOrchestrator,
)

__all__ = [
    # Pipeline
    'StoryPipeline',
    'StoryInput',
    'StoryOutput',
    'PlotPoint',
    'CharacterArc',
    'Scene',
    # Tags
    'ConsensusTagger',
    'ConsensusResult',
    'TagOrchestrator',
]

