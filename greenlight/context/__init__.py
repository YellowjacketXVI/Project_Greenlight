"""
Greenlight Context Module

Core context utilities for tracking and temporal context delivery.
"""

from .thread_tracker import ThreadTracker
from .character_temporal_context import (
    CharacterTemporalContextBuilder,
    CharacterDemographics,
    TimelineAppearance,
    StoryTimeline,
    AgeCategory,
    create_temporal_context_builder,
    get_character_appearance_for_scene,
    validate_character_demographics,
)

__all__ = [
    'ThreadTracker',
    # Character temporal context
    'CharacterTemporalContextBuilder',
    'CharacterDemographics',
    'TimelineAppearance',
    'StoryTimeline',
    'AgeCategory',
    'create_temporal_context_builder',
    'get_character_appearance_for_scene',
    'validate_character_demographics',
]
