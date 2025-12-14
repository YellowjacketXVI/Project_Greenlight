"""
Greenlight Patterns Module

Contains orchestration patterns for multi-agent collaboration.
"""

from greenlight.patterns.assembly import (
    AssemblyPattern,
    AssemblyConfig,
    Proposal,
    JudgeRanking,
    CalculatorResult,
    SynthesisResult,
)
from greenlight.patterns.steal_list import (
    StealListAggregator,
    StealElement,
    StealCategory,
    StealListResult,
)

# Quality patterns are imported from the quality submodule
# Use: from greenlight.patterns.quality import QualityOrchestrator, etc.

__all__ = [
    'AssemblyPattern',
    'AssemblyConfig',
    'Proposal',
    'JudgeRanking',
    'CalculatorResult',
    'SynthesisResult',
    # Steal list (Story Pipeline v3.0)
    'StealListAggregator',
    'StealElement',
    'StealCategory',
    'StealListResult',
]

