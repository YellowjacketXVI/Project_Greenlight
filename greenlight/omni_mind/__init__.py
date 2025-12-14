"""
Greenlight Omni Mind Module

Central AI intelligence for natural language task execution, decision making,
proactive suggestions, and self-healing capabilities.

This module integrates with Agnostic_Core_OS's OmniMind as the underlying
context library, while providing Greenlight-specific extensions.

Core Vector Routing (via Agnostic_Core_OS):
- VectorCache: Heavy vector caching (1MB) for error transcripts and notations
- HealthLogger: Health monitoring and markdown report generation
- ErrorHandoff: Error flagging, code handoff, and guidance task creation

Advanced User System:
- TerminalLogger: Separate terminal log for agent process output
- UserPreferencesLibrary: LoRA library for user preferences
- PermissionManager: Three-tier permissions for data sharing
- KeyChain: Track and log vectored key retrievals
- SelfHealQueue: Auto-implementation task queue
- DeveloperCommunication: User notes to developer
- CommunityModelManager: Git community model integration
- OmniMindRequestInterface: UI for symbolic notation requests
- DevelopersLogPipeline: Development reports, updates, and capability tracking

Integration with Agnostic_Core_OS:
- OmniMind context library is operated by RuntimeDaemon
- Memory, ContextEngine, DecisionEngine, SuggestionEngine from Agnostic_Core_OS
- Greenlight extends with project-specific capabilities
"""

# Agnostic_Core_OS OmniMind integration (core context library)
from Agnostic_Core_OS.omni_mind import (
    OmniMind as CoreOmniMind,
    OmniMindConfig as CoreOmniMindConfig,
    OmniMindMode as CoreOmniMindMode,
    Memory as CoreMemory,
    MemoryType as CoreMemoryType,
    ContextEngine as CoreContextEngine,
    ContextQuery as CoreContextQuery,
    ContextResult as CoreContextResult,
    DecisionEngine as CoreDecisionEngine,
    SuggestionEngine as CoreSuggestionEngine,
    SelfHealQueue as CoreSelfHealQueue,
)

# Greenlight-specific OmniMind extensions
from .omni_mind_core import OmniMindCore
from .omni_mind import OmniMind, AssistantMode, AssistantResponse
from .memory import AssistantMemory, MemoryEntry
from .decision_engine import DecisionEngine
from .suggestion_engine import SuggestionEngine
from .tool_executor import ToolExecutor, ToolResult, ToolCategory, ToolDeclaration
from .vector_cache import VectorCache, CacheEntry, CacheEntryType, VectorWeight
from .project_health import ProjectHealthLogger, HealthLogEntry, HealthStatus, LogCategory, NotationDefinition
from .error_handoff import ErrorHandoff, ErrorTranscript, ErrorSeverity, GuidanceTask, HandoffStatus
from .usage_metrics import UsageMetricsLogger, MetricEntry, MetricType

# Advanced User System
from .terminal_logger import TerminalLogger, TerminalEntry, LogLevel, TrackedProcess, ProcessStatus
from .user_preferences import UserPreferencesLibrary, ScriptedLoRA, LoRACategory
from .permissions import PermissionManager, PermissionTier, LogShareLevel, UpdateChannel, FlaggedRequest
from .key_chain import KeyChain, TrackedKey, KeyAccessLog, KeyType, AccessLevel
from .self_heal_queue import SelfHealQueue, SelfHealTask, TaskPriority, TaskStatus, TaskCategory
from .developer_comm import DeveloperCommunication, DeveloperNote, NoteType, NoteStatus, NotePriority, FlagAnalysis
from .community_model import CommunityModelManager, DataContribution, ContributionType, ContributionStatus, UpdateInfo
from .request_interface import OmniMindRequestInterface, SymbolicNotationParser, ParsedRequest, RequestResult, RequestType
from .developers_log import (
    DevelopersLogPipeline, UpdateEntry, UpdateType, Capability, CapabilityStatus,
    VersionInfo, ReportType
)
from .gemini_power import (
    GeminiPower, VectorTask, VectorTaskType, VectorCommand, CommandScope,
    InitStatus, InitPhase, GeminiResponse, create_gemini_power
)
from .self_guidance import (
    SelfGuidance, LLMPicker, GuidanceConfig, GuidanceMode, DecisionType,
    LLMRole, LLMSelection, Decision
)
from .assistant_bridge import (
    GreenlightAssistantBridge, GreenlightBridgeConfig, LLMClientAdapter
)
from .process_library import (
    ProcessLibrary, ProcessDefinition, ProcessExecution, ProcessCategory, ProcessStatus
)
from .process_monitor import (
    ProcessMonitor, MonitorEvent, MonitorEventType, TrackedProcess, get_process_monitor
)
from .error_reporter import (
    ErrorReporter, AugmentTranscript, ErrorCategory, TranscriptLevel,
    SelfHealStatus, ErrorContext, SelfHealAttempt
)
from .self_healer import (
    SelfHealer, HealingPattern, HealResult, HealingAction, HealingRule
)
from .conversation_manager import (
    ConversationManager, ConversationMessage, MemoryVector,
    ProjectContext, MessageRole, ContextType
)
from .project_primer import (
    ProjectPrimer, SymbolicEntry, SymbolType, PathStatus, BrokenPath
)
from .symbolic_registry import (
    SymbolicRegistry, SymbolDefinition, SymbolOrigin, LearningEvent
)

__all__ = [
    # Agnostic_Core_OS OmniMind (core context library)
    'CoreOmniMind',
    'CoreOmniMindConfig',
    'CoreOmniMindMode',
    'CoreMemory',
    'CoreMemoryType',
    'CoreContextEngine',
    'CoreContextQuery',
    'CoreContextResult',
    'CoreDecisionEngine',
    'CoreSuggestionEngine',
    'CoreSelfHealQueue',
    # Greenlight Core
    'OmniMindCore',
    'OmniMind',
    'AssistantMode',
    'AssistantResponse',
    # Memory
    'AssistantMemory',
    'MemoryEntry',
    # Engines
    'DecisionEngine',
    'SuggestionEngine',
    # Tools
    'ToolExecutor',
    'ToolResult',
    'ToolCategory',
    'ToolDeclaration',
    # Vector Cache
    'VectorCache',
    'CacheEntry',
    'CacheEntryType',
    'VectorWeight',
    # Health Logger
    'ProjectHealthLogger',
    'HealthLogEntry',
    'HealthStatus',
    'LogCategory',
    'NotationDefinition',
    # Error Handoff
    'ErrorHandoff',
    'ErrorTranscript',
    'ErrorSeverity',
    'GuidanceTask',
    'HandoffStatus',
    # Usage Metrics
    'UsageMetricsLogger',
    'MetricEntry',
    'MetricType',
    # Terminal Logger
    'TerminalLogger',
    'TerminalEntry',
    'LogLevel',
    'TrackedProcess',
    'ProcessStatus',
    # User Preferences
    'UserPreferencesLibrary',
    'ScriptedLoRA',
    'LoRACategory',
    # Permissions
    'PermissionManager',
    'PermissionTier',
    'LogShareLevel',
    'UpdateChannel',
    'FlaggedRequest',
    # Key Chain
    'KeyChain',
    'TrackedKey',
    'KeyAccessLog',
    'KeyType',
    'AccessLevel',
    # Self-Heal Queue
    'SelfHealQueue',
    'SelfHealTask',
    'TaskPriority',
    'TaskStatus',
    'TaskCategory',
    # Developer Communication
    'DeveloperCommunication',
    'DeveloperNote',
    'NoteType',
    'NoteStatus',
    'NotePriority',
    'FlagAnalysis',
    # Community Model
    'CommunityModelManager',
    'DataContribution',
    'ContributionType',
    'ContributionStatus',
    'UpdateInfo',
    # Request Interface
    'OmniMindRequestInterface',
    'SymbolicNotationParser',
    'ParsedRequest',
    'RequestResult',
    'RequestType',
    # Developers Log Pipeline
    'DevelopersLogPipeline',
    'UpdateEntry',
    'UpdateType',
    'Capability',
    'CapabilityStatus',
    'VersionInfo',
    'ReportType',
    # Gemini Power
    'GeminiPower',
    'VectorTask',
    'VectorTaskType',
    'VectorCommand',
    'CommandScope',
    'InitStatus',
    'InitPhase',
    'GeminiResponse',
    'create_gemini_power',
    # Self-Guidance
    'SelfGuidance',
    'LLMPicker',
    'GuidanceConfig',
    'GuidanceMode',
    'DecisionType',
    'LLMRole',
    'LLMSelection',
    'Decision',
    # Assistant Bridge
    'GreenlightAssistantBridge',
    'GreenlightBridgeConfig',
    'LLMClientAdapter',
    # Process Library
    'ProcessLibrary',
    'ProcessDefinition',
    'ProcessExecution',
    'ProcessCategory',
    'ProcessStatus',
    # Process Monitor
    'ProcessMonitor',
    'MonitorEvent',
    'MonitorEventType',
    'TrackedProcess',
    'get_process_monitor',
    # Error Reporter (Augment Integration)
    'ErrorReporter',
    'AugmentTranscript',
    'ErrorCategory',
    'TranscriptLevel',
    'SelfHealStatus',
    'ErrorContext',
    'SelfHealAttempt',
    # Self-Healer
    'SelfHealer',
    'HealingPattern',
    'HealResult',
    'HealingAction',
    'HealingRule',
    # Conversation Manager
    'ConversationManager',
    'ConversationMessage',
    'MemoryVector',
    'ProjectContext',
    'MessageRole',
    'ContextType',
    # Project Primer
    'ProjectPrimer',
    'SymbolicEntry',
    'SymbolType',
    'PathStatus',
    'BrokenPath',
    # Symbolic Registry
    'SymbolicRegistry',
    'SymbolDefinition',
    'SymbolOrigin',
    'LearningEvent',
]

