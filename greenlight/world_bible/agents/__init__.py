"""
World Bible Agents Module

Agents specific to the World Bible pipeline.

Re-exports from the main agents module for convenience.
Feature-specific agents will be added here as they are extracted.
"""

# Re-export relevant agents from main agents module
from greenlight.agents.profile_template_agent import ProfileTemplateAgent
from greenlight.agents.brainstorm_agents import (
    PitchEnrichmentAgent,
    GenreCalibrationAgent,
    CharacterLensAgent,
    BehaviorValidatorAgent,
)

__all__ = [
    'ProfileTemplateAgent',
    'PitchEnrichmentAgent',
    'GenreCalibrationAgent',
    'CharacterLensAgent',
    'BehaviorValidatorAgent',
]

