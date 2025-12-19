"""
Greenlight Tags - Shared Utilities

Shared utilities used across all tag types:
- TagParser: Parse and validate tag format
- TagRegistry: Central registry for all tags
- TagValidator: Validate tags against registry
- ConsensusTagger: Base consensus tagger (5 agents, 80% threshold)
- ConsensusResult: Result from consensus extraction
- AgentExtraction: Single agent extraction result

These are re-exported from the parent tags module for convenience.
The actual implementations remain in the parent directory for backward compatibility.
"""

# Re-export from parent module
from greenlight.tags.tag_parser import (
    TagParser,
    ParsedTag,
    FramePosition,
    SpatialPositionCalculator
)
from greenlight.tags.tag_registry import TagRegistry, TagEntry
from greenlight.tags.tag_validator import TagValidator, ValidationResult, ValidationIssue
from greenlight.tags.consensus_tagger import ConsensusTagger, ConsensusResult, AgentExtraction

__all__ = [
    # Parser
    'TagParser',
    'ParsedTag',
    'FramePosition',
    'SpatialPositionCalculator',
    # Registry
    'TagRegistry',
    'TagEntry',
    # Validator
    'TagValidator',
    'ValidationResult',
    'ValidationIssue',
    # Consensus
    'ConsensusTagger',
    'ConsensusResult',
    'AgentExtraction',
]

