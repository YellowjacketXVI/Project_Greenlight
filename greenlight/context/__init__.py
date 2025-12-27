"""
Greenlight Context Module

Enhanced context engine with RAG capabilities, vector search, and agentic search.

Story Pipeline v3.0 additions:
- ContextCompiler: Compiles minimal context packets (~250 words per agent)
- ThreadTracker: Tracks narrative threads across scenes (~50 words)
- AgentContextDelivery: Prepares context for specific agent types

Context System v4.0 additions:
- ContextManager: Unified facade orchestrating all context subsystems
- ContextValidator: Early validation of context integrity
- SceneSummarizer: Cross-scene context summarization
- BudgetProfile: Configurable token budgets per pipeline/agent
- RelationshipContextBuilder: Automatic relationship context surfacing
- AttentionWeightedAssembler: Focal entity priority boosting
"""

from .context_engine import ContextEngine, ContextQuery, ContextResult, SceneContext
from .context_assembler import (
    ContextAssembler,
    ContextSource,
    ContextItem,
    AssembledContext,
    BudgetProfile,
    RelationshipContextBuilder,
    RelationshipContext,
    AttentionWeightedAssembler,
    create_assembler_for_pipeline,
    create_attention_assembler,
    build_relationship_context,
)
from .vector_store import VectorStore
from .keyword_index import KeywordIndex
from .context_compiler import ContextCompiler
from .thread_tracker import ThreadTracker
from .agent_context_delivery import AgentContextDelivery, SceneOutline

# v4.0 additions
from .context_validator import (
    ContextValidator,
    ContextValidationResult,
    ContextValidationIssue,
    ValidationLevel,
    validate_context,
    validate_world_config,
    find_unknown_references,
)
from .context_manager import (
    ContextManager,
    ContextEvent,
    ContextSnapshot,
    ContextRequest,
    get_context_manager,
    set_project,
    get_world_config,
    invalidate_context,
    validate_context as validate_context_manager,
)
from .scene_summarizer import (
    SceneSummarizer,
    SceneSummary,
    ActSummary,
    CharacterArc,
    NarrativeThread,
    SummaryLevel,
    create_summarizer,
    summarize_script,
)
from .director_context_compiler import (
    DirectorContextCompiler,
    DirectorContextPacket,
    CompressedProjectContext,
    CompressedSceneContext,
    CompressedFrameContext,
    CompressedCameraContext,
    DirectorContextLevel,
    create_director_compiler,
)
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
    # Core context engine
    'ContextEngine',
    'ContextQuery',
    'ContextResult',
    'SceneContext',
    'ContextSource',
    'VectorStore',
    'KeywordIndex',

    # Context assembly
    'ContextAssembler',
    'ContextItem',
    'AssembledContext',
    'BudgetProfile',
    'AttentionWeightedAssembler',
    'create_assembler_for_pipeline',
    'create_attention_assembler',

    # Relationship context
    'RelationshipContextBuilder',
    'RelationshipContext',
    'build_relationship_context',

    # Story Pipeline v3.0
    'ContextCompiler',
    'ThreadTracker',
    'AgentContextDelivery',
    'SceneOutline',

    # Context validation (v4.0)
    'ContextValidator',
    'ContextValidationResult',
    'ContextValidationIssue',
    'ValidationLevel',
    'validate_context',
    'validate_world_config',
    'find_unknown_references',

    # Context management (v4.0)
    'ContextManager',
    'ContextEvent',
    'ContextSnapshot',
    'ContextRequest',
    'get_context_manager',
    'set_project',
    'get_world_config',
    'invalidate_context',

    # Scene summarization (v4.0)
    'SceneSummarizer',
    'SceneSummary',
    'ActSummary',
    'CharacterArc',
    'NarrativeThread',
    'SummaryLevel',
    'create_summarizer',
    'summarize_script',

    # Director context compression (v4.0)
    'DirectorContextCompiler',
    'DirectorContextPacket',
    'CompressedProjectContext',
    'CompressedSceneContext',
    'CompressedFrameContext',
    'CompressedCameraContext',
    'DirectorContextLevel',
    'create_director_compiler',

    # Character temporal/demographic context (v4.0)
    'CharacterTemporalContextBuilder',
    'CharacterDemographics',
    'TimelineAppearance',
    'StoryTimeline',
    'AgeCategory',
    'create_temporal_context_builder',
    'get_character_appearance_for_scene',
    'validate_character_demographics',
]

