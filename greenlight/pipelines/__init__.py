"""
Greenlight Pipelines Module

Processing pipelines for AI-powered cinematic storyboard generation.

Main Pipeline:
- CondensedVisualPipeline: Pitch → Visual Script + Storyboard (6-pass architecture)
  - Pass 1: World Building (characters, locations, props, style)
  - Pass 2: Reference Generation (visual references for entities)
  - Pass 3: Key Frame Generation (anchor frames with full references)
  - Pass 4: Continuity Pass (fill frames with prior context)
  - Pass 5: Visual Prompts (detailed prompts for each frame)
  - Pass 6: Storyboard Generation (final image generation)

Support Pipelines:
- AdvancedStoryboardPipeline: Enhanced storyboard with healing
- ParallelHealingPipeline: Frame version management and continuity healing
"""

# Main Pipeline
from .condensed_visual_pipeline import (
    CondensedVisualPipeline,
    CondensedPipelineInput,
    CondensedPipelineOutput,
    StoryPhaseOutput,
    FrameAnchor,
    run_condensed_pipeline,
)

# Data classes for visual pipeline
from .unified_visual_pipeline import (
    VisualWorldConfig,
    VisualCharacter,
    VisualLocation,
    VisualProp,
    InlineFrame,
    UnifiedScene,
)

# Support pipelines
from .advanced_storyboard_pipeline import AdvancedStoryboardPipeline
from .parallel_healing_pipeline import (
    FrameVersionManager,
    ParallelHealingPipeline,
)

# Base pipeline
from .base_pipeline import BasePipeline, PipelineStatus

# Optimization modules
from .batch_processor import (
    BatchProcessor,
    BatchResult,
    BatchItem,
    BatchType,
    create_batch_processor,
)
from .concurrency_manager import (
    ConcurrencyManager,
    PipelinePhase,
    PhaseConfig,
    get_concurrency_manager,
    with_phase_limit,
    get_phase_limit,
    set_phase_limit,
)
from .early_validation import (
    EarlyValidator,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
    create_validator,
    validate_scene,
    validate_frame,
    PromptQualityValidator,
    create_prompt_validator,
    validate_frame_prompt,
    CinematicConsistencyValidator,
    create_cinematic_validator,
    validate_frame_sequence,
)
from .context_aggregator import (
    ContextAggregator,
    ContextLevel,
    ProjectContext,
    SceneContext,
    FrameContext,
    CameraContext,
    LightingState,
    EstablishedElement,
    create_context_aggregator,
    ScreenPosition,
    CharacterScreenPosition,
    ShotCategory,
    ShotRhythmEntry,
)

__all__ = [
    # Main Pipeline
    'CondensedVisualPipeline',
    'CondensedPipelineInput',
    'CondensedPipelineOutput',
    'StoryPhaseOutput',
    'FrameAnchor',
    'run_condensed_pipeline',
    # Data classes
    'VisualWorldConfig',
    'VisualCharacter',
    'VisualLocation',
    'VisualProp',
    'InlineFrame',
    'UnifiedScene',
    # Support pipelines
    'AdvancedStoryboardPipeline',
    'FrameVersionManager',
    'ParallelHealingPipeline',
    # Base
    'BasePipeline',
    'PipelineStatus',
    # Optimization - Batch Processing
    'BatchProcessor',
    'BatchResult',
    'BatchItem',
    'BatchType',
    'create_batch_processor',
    # Optimization - Concurrency
    'ConcurrencyManager',
    'PipelinePhase',
    'PhaseConfig',
    'get_concurrency_manager',
    'with_phase_limit',
    'get_phase_limit',
    'set_phase_limit',
    # Validation
    'EarlyValidator',
    'ValidationResult',
    'ValidationIssue',
    'ValidationSeverity',
    'create_validator',
    'validate_scene',
    'validate_frame',
    'PromptQualityValidator',
    'create_prompt_validator',
    'validate_frame_prompt',
    'CinematicConsistencyValidator',
    'create_cinematic_validator',
    'validate_frame_sequence',
    # Context Aggregation
    'ContextAggregator',
    'ContextLevel',
    'ProjectContext',
    'SceneContext',
    'FrameContext',
    'CameraContext',
    'LightingState',
    'EstablishedElement',
    'create_context_aggregator',
    'ScreenPosition',
    'CharacterScreenPosition',
    'ShotCategory',
    'ShotRhythmEntry',
]

