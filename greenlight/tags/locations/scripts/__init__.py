"""
Location Scripts Module

Contains location-specific processing scripts:
- location_directional_consensus.py - Directional tag selection
- location_spatial_continuity.py - Spatial continuity tracking
"""

# Re-export from parent tags module for convenience
from greenlight.tags.directional_consensus import (
    DirectionalTagConsensus,
    SpatialAnchorDetector,
    DirectionalConsensusResult,
    AnchorConsensusResult,
    DirectionalTagVote,
    SpatialAnchor
)
from greenlight.tags.spatial_continuity import (
    SpatialElement,
    ShotSpatialContext,
    SpatialContinuityValidator,
    SpatialRelationship
)

__all__ = [
    'DirectionalTagConsensus',
    'SpatialAnchorDetector',
    'DirectionalConsensusResult',
    'AnchorConsensusResult',
    'DirectionalTagVote',
    'SpatialAnchor',
    'SpatialElement',
    'ShotSpatialContext',
    'SpatialContinuityValidator',
    'SpatialRelationship',
]

