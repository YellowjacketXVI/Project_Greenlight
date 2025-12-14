"""
Agnostic_Core_OS - Vector-Native Runtime Environment

A platform-agnostic runtime environment providing:
- Runtime Daemon: Background service managing persistent state
- App Registry: Track and manage connected applications
- Event Bus: Inter-app communication via pub/sub
- App SDK: Clean interface for apps to connect
- Vector-to-Language translation (natural ↔ notation)
- LLM Handshake protocols for AI-powered interactions
- Iteration validation with max 100 cycles
- Token-efficient context logging
- Self-healing integration with OmniMind
- Memory vectorization for procedural UI crafting
- User profile management with workflow patterns
- LoRA-compatible dataset generation

Directory Structure:
    runtime/        - Runtime daemon, app registry, event bus, SDK
    core/           - Core platform infrastructure
    protocols/      - LLM handshake and communication protocols
    translators/    - Vector ↔ Natural language translators
    validators/     - Iteration and output validators
    memory/         - Vector memory, UI network, profiles, datasets
    engines/        - Image, audio, live analyze, comparison learning
    procedural/     - Notation library, file browser, context index
    logs/           - Token-efficient context logs
    tests/          - Test scripts and validation
"""

from .core.platform import AgnosticCorePlatform
from .translators.vector_language import VectorLanguageTranslator, VectorNotation
from .translators.systems_translator import (
    SystemsTranslatorIndex,
    SystemInfo,
    BuildParameters,
    OSType,
    Architecture,
    ShellType,
    get_systems_translator,
)
from .core.file_ops import FileOperations, FileInfo, get_file_ops
from .core.process_runner import (
    ProcessRunner,
    ProcessResult,
    ProcessStatus,
    get_process_runner,
)
from .core.vector_auth import (
    VectorKeyAuth,
    VectorKey,
    AccessLevel,
    AuthResult,
    get_vector_auth,
)
from .core.core_lock import (
    CoreLock,
    CoreFile,
    CoreScope,
    Capability,
    CORE_FILES,
    CORE_GUIDELINES,
    get_core_lock,
)
from .protocols.llm_handshake import LLMHandshake, HandshakeConfig, HandshakeResult
from .validators.iteration_validator import IterationValidator, ValidationResult
from .core.context_logger import TokenEfficientLogger, ContextReport

# Memory System
from .memory.vector_memory import (
    VectorMemory,
    MemoryEntry,
    MemoryType,
    MemoryPriority,
    get_vector_memory,
)
from .memory.ui_network import (
    UINetworkCrafter,
    UIComponent,
    UILayout,
    UICustomization,
    ComponentType,
)
from .memory.user_profile import (
    UserProfileManager,
    UserProfile,
    WorkflowPattern,
    ProfilePreference,
    WorkflowType,
)
from .memory.dataset_crafter import (
    DatasetCrafter,
    DatasetEntry,
    DatasetFormat,
    LoRADataset,
)

# Engines
from .engines.image_engine import (
    ImageEngine,
    ImageVector,
    ImageComparison,
    SafeTensorFormat,
    ImageType,
    get_image_engine,
)
from .engines.audio_engine import (
    AudioEngine,
    AudioVector,
    AudioComparison,
    WaveformData,
    AudioType,
    AudioFormat,
    get_audio_engine,
)
from .engines.live_analyze_engine import (
    LiveAnalyzeEngine,
    FlashFeature,
    SampleReplication,
    AnalysisReport,
    AnalysisMode,
    FeatureType,
    ReplicationMode,
    get_live_engine,
)
from .engines.comparison_learning import (
    ComparisonLearning,
    LearningReport,
    VectorDelta,
    IterationResult,
    ComparisonType,
    LearningPhase,
)

# Procedural System
from .procedural.notation_library import (
    NotationLibrary,
    NotationEntry,
    NotationType,
    NotationScope,
    get_notation_library,
)
from .procedural.file_browser import (
    VectorFileBrowser,
    FileVector,
    DirectoryVector,
    BrowseResult,
    FileCategory,
    get_file_browser,
)
from .procedural.context_index import (
    ContextIndex,
    IndexEntry,
    SearchResult,
    IndexScope,
    IndexEntryType,
    get_context_index,
)

# Runtime System
from .runtime.daemon import RuntimeDaemon, DaemonState, DaemonConfig
from .runtime.app_registry import AppRegistry, AppInfo, AppState
from .runtime.event_bus import EventBus, Event, EventHandler, EventPriority
from .runtime.sdk import AppSDK, AppConnection, get_runtime_daemon, set_runtime_daemon
from .runtime.health_monitor import HealthMonitor, RuntimeHealth, HealthStatus, HealthIssue

# Core Routing (Self-Healing)
from .core_routing.vector_cache import VectorCache, CacheEntry, CacheEntryType, VectorWeight
from .core_routing.health_logger import HealthLogger, HealthLogEntry, LogCategory, NotationDefinition
from .core_routing.error_handoff import ErrorHandoff, ErrorTranscript, ErrorSeverity, GuidanceTask, HandoffStatus

__all__ = [
    # Core Platform
    "AgnosticCorePlatform",
    # Vector Translators
    "VectorLanguageTranslator",
    "VectorNotation",
    # Systems Translator
    "SystemsTranslatorIndex",
    "SystemInfo",
    "BuildParameters",
    "OSType",
    "Architecture",
    "ShellType",
    "get_systems_translator",
    # File Operations
    "FileOperations",
    "FileInfo",
    "get_file_ops",
    # Process Runner
    "ProcessRunner",
    "ProcessResult",
    "ProcessStatus",
    "get_process_runner",
    # Protocols
    "LLMHandshake",
    "HandshakeConfig",
    "HandshakeResult",
    # Validators
    "IterationValidator",
    "ValidationResult",
    # Logging
    "TokenEfficientLogger",
    "ContextReport",
    # Memory System
    "VectorMemory",
    "MemoryEntry",
    "MemoryType",
    "MemoryPriority",
    "get_vector_memory",
    # UI Network
    "UINetworkCrafter",
    "UIComponent",
    "UILayout",
    "UICustomization",
    "ComponentType",
    # User Profile
    "UserProfileManager",
    "UserProfile",
    "WorkflowPattern",
    "ProfilePreference",
    "WorkflowType",
    # Dataset Crafter
    "DatasetCrafter",
    "DatasetEntry",
    "DatasetFormat",
    "LoRADataset",
    # Image Engine
    "ImageEngine",
    "ImageVector",
    "ImageComparison",
    "SafeTensorFormat",
    "ImageType",
    "get_image_engine",
    # Audio Engine
    "AudioEngine",
    "AudioVector",
    "AudioComparison",
    "WaveformData",
    "AudioType",
    "AudioFormat",
    "get_audio_engine",
    # Live Analyze Engine
    "LiveAnalyzeEngine",
    "FlashFeature",
    "SampleReplication",
    "AnalysisReport",
    "AnalysisMode",
    "FeatureType",
    "ReplicationMode",
    "get_live_engine",
    # Comparison Learning
    "ComparisonLearning",
    "LearningReport",
    "VectorDelta",
    "IterationResult",
    "ComparisonType",
    "LearningPhase",
    # Vector Auth
    "VectorKeyAuth",
    "VectorKey",
    "AccessLevel",
    "AuthResult",
    "get_vector_auth",
    # Core Lock
    "CoreLock",
    "CoreFile",
    "CoreScope",
    "Capability",
    "CORE_FILES",
    "CORE_GUIDELINES",
    "get_core_lock",
    # Notation Library
    "NotationLibrary",
    "NotationEntry",
    "NotationType",
    "NotationScope",
    "get_notation_library",
    # File Browser
    "VectorFileBrowser",
    "FileVector",
    "DirectoryVector",
    "BrowseResult",
    "FileCategory",
    "get_file_browser",
    # Context Index
    "ContextIndex",
    "IndexEntry",
    "SearchResult",
    "IndexScope",
    "IndexEntryType",
    "get_context_index",
    # Runtime System
    "RuntimeDaemon",
    "DaemonState",
    "DaemonConfig",
    "AppRegistry",
    "AppInfo",
    "AppState",
    "EventBus",
    "Event",
    "EventHandler",
    "EventPriority",
    "AppSDK",
    "AppConnection",
    "get_runtime_daemon",
    "set_runtime_daemon",
    "HealthMonitor",
    "RuntimeHealth",
    "HealthStatus",
    "HealthIssue",
    # Core Routing (Self-Healing)
    "VectorCache",
    "CacheEntry",
    "CacheEntryType",
    "VectorWeight",
    "HealthLogger",
    "HealthLogEntry",
    "LogCategory",
    "NotationDefinition",
    "ErrorHandoff",
    "ErrorTranscript",
    "ErrorSeverity",
    "GuidanceTask",
    "HandoffStatus",
    # Version
    "__version__",
]

__version__ = "0.5.0"  # Runtime Environment Release

