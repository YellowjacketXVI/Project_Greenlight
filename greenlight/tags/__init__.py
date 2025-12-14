"""
Greenlight Tags Module

Standardized tag system for tracking characters, locations, props, and concepts
throughout the story development pipeline.

Includes spatial continuity system for maintaining visual coherence across shots.
"""

from .tag_parser import TagParser, ParsedTag, FramePosition, SpatialPositionCalculator
from .tag_registry import TagRegistry, TagEntry
from .tag_validator import TagValidator, ValidationResult
from .consensus_tagger import ConsensusTagger, ConsensusResult
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
from .tag_reference_system import (
    TagReferenceSystem,
    TagReferenceRegistry,
    TagReferenceEntry,
    TenAgentConsensusTagger,
    ReferencePromptGenerator,
    ValidatedTagSet,
    ReferenceImageStatus
)

__all__ = [
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
]

