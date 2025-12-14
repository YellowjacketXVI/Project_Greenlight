"""
Agnostic_Core_OS OmniMind Module

OmniMind is the Context Library for Agnostic_Core_OS - providing:
- Memory management (short-term, long-term, preferences)
- Context retrieval and assembly
- Decision engine for autonomous actions
- Suggestion engine for proactive assistance
- Self-healing and error handoff
- Vector caching with weighted entries

Architecture:
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGNOSTIC_CORE_OS (Engine)                            │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      OMNI_MIND (Context Library)                  │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │   Memory    │  │  Context    │  │  Decision   │               │  │
│  │  │   System    │  │  Engine     │  │  Engine     │               │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │  Suggestion │  │  Self-Heal  │  │   Vector    │               │  │
│  │  │   Engine    │  │   Queue     │  │   Cache     │               │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  RuntimeDaemon operates OmniMind as the context provider                │
└─────────────────────────────────────────────────────────────────────────┘

The RuntimeDaemon in Agnostic_Core_OS operates OmniMind, using it as the
central context library for all connected applications.
"""

# Core OmniMind components
from .omni_mind import OmniMind, OmniMindConfig, OmniMindMode
from .memory import Memory, MemoryEntry, MemoryType
from .context_engine import ContextEngine, ContextQuery, ContextResult, ContextSource
from .decision_engine import DecisionEngine, Decision, DecisionType, DecisionConfidence
from .suggestion_engine import SuggestionEngine, Suggestion, SuggestionType
from .self_heal import SelfHealQueue, SelfHealTask, TaskPriority, TaskStatus

# Re-export from core_routing for convenience
from ..core_routing import (
    VectorCache, CacheEntry, CacheEntryType, VectorWeight,
    HealthLogger, LogCategory,
    ErrorHandoff, ErrorSeverity
)

__all__ = [
    # Core
    'OmniMind',
    'OmniMindConfig',
    'OmniMindMode',
    # Memory
    'Memory',
    'MemoryEntry',
    'MemoryType',
    # Context
    'ContextEngine',
    'ContextQuery',
    'ContextResult',
    'ContextSource',
    # Decision
    'DecisionEngine',
    'Decision',
    'DecisionType',
    'DecisionConfidence',
    # Suggestion
    'SuggestionEngine',
    'Suggestion',
    'SuggestionType',
    # Self-Heal
    'SelfHealQueue',
    'SelfHealTask',
    'TaskPriority',
    'TaskStatus',
    # Vector Cache (from core_routing)
    'VectorCache',
    'CacheEntry',
    'CacheEntryType',
    'VectorWeight',
    # Health Logger (from core_routing)
    'HealthLogger',
    'LogCategory',
    # Error Handoff (from core_routing)
    'ErrorHandoff',
    'ErrorSeverity',
]

