"""
Greenlight World Bible Module

The World Bible pipeline researches and expands extracted tags into detailed
profiles for characters, locations, and props.

Pipeline Flow:
    Validated Tags → World Bible Pipeline → world_config.json

Key Components:
    - WorldBiblePipeline: Main research and synthesis engine
    - CharacterResearchAgent: 5 research agents → 3 judges → synthesize
    - LocationResearchAgent: 3 research agents → 3 judges → synthesize
    - PropResearchAgent: 2 research agents → 2 judges → synthesize
    - PhysiologicalTellsAgent: Generates emotional_tells for characters

Directory Structure:
    /prompts/               - Externalized prompt templates
        /01_character/      - Character research prompts
        /02_location/       - Location research prompts
        /03_prop/           - Prop research prompts
        /04_global/         - Global context prompts
        /05_synthesis/      - Profile synthesis prompts
        /06_continuity/     - Cross-tag relationship validation
    /agents/                - World Bible-specific agents

Architecture:
    - Chunked-per-tag: Each tag gets its own research pipeline
    - Parallel processing: All tags of same type processed together
    - Judge consensus: Multiple judges validate research quality

Outputs:
    - world_config.json: Complete world bible with all profiles
"""

# Re-export main pipeline for convenience
from greenlight.pipelines.world_bible_pipeline import (
    WorldBiblePipeline,
    WorldBibleInput,
    WorldBibleOutput,
)

__all__ = [
    'WorldBiblePipeline',
    'WorldBibleInput',
    'WorldBibleOutput',
]

