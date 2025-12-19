"""
Greenlight Tags Module

Standardized tag system for tracking characters, locations, props, and concepts
throughout the story development pipeline.

Structure:
    /characters/    - Character tag extraction and reference generation
    /locations/     - Location tags, directional consensus, spatial continuity
    /props/         - Prop tag extraction and reference generation
    /events/        - Event tag extraction
    /plots/         - Plot/concept tag extraction
    /relationships/ - Relationship mapping between entities
    /shared/        - Shared utilities (parser, registry, validator)

The TagOrchestrator provides a unified interface for all tag operations.
"""

# Core utilities (backward compatible imports)
from .tag_parser import TagParser, ParsedTag, FramePosition, SpatialPositionCalculator
from .tag_registry import TagRegistry, TagEntry
from .tag_validator import TagValidator, ValidationResult
from .consensus_tagger import ConsensusTagger, ConsensusResult, AgentExtraction

# Spatial and directional
from .spatial_continuity import (
    SpatialElement,
    ShotSpatialContext,
    SpatialContinuityValidator,
    SpatialRelationship
)
from .directional_consensus import (
    DirectionalTagConsensus,
    SpatialAnchorDetector,
    DirectionalConsensusResult,
    AnchorConsensusResult,
    DirectionalTagVote,
    SpatialAnchor
)

# Tag reference system
from .tag_reference_system import (
    TagReferenceSystem,
    TagReferenceRegistry,
    TagReferenceEntry,
    TenAgentConsensusTagger,
    ReferencePromptGenerator,
    ValidatedTagSet,
    ReferenceImageStatus
)

# New modular tag managers
from .tag_orchestrator import TagOrchestrator, UnifiedExtractionResult
from .characters import CharacterTagManager
from .locations import LocationTagManager
from .props import PropTagManager
from .events import EventTagManager
from .plots import PlotTagManager
from .relationships import RelationshipTagManager

__all__ = [
    # Core utilities
    'TagParser',
    'ParsedTag',
    'FramePosition',
    'SpatialPositionCalculator',
    'TagRegistry',
    'TagEntry',
    'TagValidator',
    'ValidationResult',
    'ConsensusTagger',
    'ConsensusResult',
    'AgentExtraction',

    # Spatial and directional
    'SpatialElement',
    'ShotSpatialContext',
    'SpatialContinuityValidator',
    'SpatialRelationship',
    'DirectionalTagConsensus',
    'SpatialAnchorDetector',
    'DirectionalConsensusResult',
    'AnchorConsensusResult',
    'DirectionalTagVote',
    'SpatialAnchor',

    # Tag Reference System
    'TagReferenceSystem',
    'TagReferenceRegistry',
    'TagReferenceEntry',
    'TenAgentConsensusTagger',
    'ReferencePromptGenerator',
    'ValidatedTagSet',
    'ReferenceImageStatus',

    # New modular system
    'TagOrchestrator',
    'UnifiedExtractionResult',
    'CharacterTagManager',
    'LocationTagManager',
    'PropTagManager',
    'EventTagManager',
    'PlotTagManager',
    'RelationshipTagManager',
]

