"""
Writer Agents Module

Agents specific to the Writer pipeline.

Re-exports from the main agents module for convenience.
Feature-specific agents will be added here as they are extracted.
"""

# Re-export relevant agents from main agents module
from greenlight.agents.prose_agent import ProseAgent
from greenlight.agents.scene_outline_agent import SceneOutlineAgent
from greenlight.agents.brainstorm_agents import (
    PitchEnrichmentAgent,
    GenreCalibrationAgent,
    CharacterLensAgent,
    BehaviorValidatorAgent,
)

__all__ = [
    'ProseAgent',
    'SceneOutlineAgent',
    'PitchEnrichmentAgent',
    'GenreCalibrationAgent',
    'CharacterLensAgent',
    'BehaviorValidatorAgent',
]

