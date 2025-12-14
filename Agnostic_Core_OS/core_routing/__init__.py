"""
Agnostic_Core_OS Core Routing Module

Vector routing, caching, health logging, and error handoff for self-healing.
These are standalone versions of the OmniMind components, allowing
Agnostic_Core_OS to operate independently.
"""

from .vector_cache import VectorCache, CacheEntry, CacheEntryType, VectorWeight
from .health_logger import HealthLogger, HealthLogEntry, HealthStatus, LogCategory, NotationDefinition
from .error_handoff import ErrorHandoff, ErrorTranscript, ErrorSeverity, GuidanceTask, HandoffStatus

__all__ = [
    # Vector Cache
    "VectorCache",
    "CacheEntry",
    "CacheEntryType",
    "VectorWeight",
    # Health Logger
    "HealthLogger",
    "HealthLogEntry",
    "HealthStatus",
    "LogCategory",
    "NotationDefinition",
    # Error Handoff
    "ErrorHandoff",
    "ErrorTranscript",
    "ErrorSeverity",
    "GuidanceTask",
    "HandoffStatus",
]

