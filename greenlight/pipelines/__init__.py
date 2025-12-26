"""
Greenlight Pipelines Module

Processing pipelines for story development and cinematic direction.

Pipeline Flow:
1. StoryPipeline (Writer): Pitch → Script (scripts/script.md)
2. DirectingPipeline (Director): Script → Visual_Script (frame notations, camera, prompts)

OPTIMIZATIONS (v2.1):
- Batch processing for frame prompts
- Configurable concurrency per pipeline phase
- Early validation checkpoints

NOTE: Deprecated pipelines (v2, v3, shot_pipeline, quality_pipeline) have been removed.
"""

from .story_pipeline import (
    StoryPipeline,
    StoryInput,
    StoryOutput,
    Scene,
    TransitionType,
    SceneWeight,
    CharacterArc,
    PlotPoint,
)
from .directing_pipeline import DirectingPipeline, DirectingInput, VisualScriptOutput
from .shot_list_extractor import (
    ShotListExtractor,
    ShotEntry,
    SceneGroup,
    ShotList,
    StoryboardPromptGenerator,
)

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
    # Prompt Quality Validation (pre-generation)
    PromptQualityValidator,
    create_prompt_validator,
    validate_frame_prompt,
    # Cinematic Consistency Validation (post-generation)
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
    # 180-degree rule / Screen Direction
    ScreenPosition,
    CharacterScreenPosition,
    # Shot Rhythm
    ShotCategory,
    ShotRhythmEntry,
)

__all__ = [
    # Story Pipeline (Writer)
    'StoryPipeline',
    'StoryInput',
    'StoryOutput',
    'Scene',
    'TransitionType',
    'SceneWeight',
    'CharacterArc',
    'PlotPoint',
    # Directing Pipeline (Director)
    'DirectingPipeline',
    'DirectingInput',
    'VisualScriptOutput',
    # Shot list extraction
    'ShotListExtractor',
    'ShotEntry',
    'SceneGroup',
    'ShotList',
    'StoryboardPromptGenerator',
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
    # Optimization - Early Validation
    'EarlyValidator',
    'ValidationResult',
    'ValidationIssue',
    'ValidationSeverity',
    'create_validator',
    'validate_scene',
    'validate_frame',
    # Prompt Quality Validation (pre-generation)
    'PromptQualityValidator',
    'create_prompt_validator',
    'validate_frame_prompt',
    # Context Aggregation (hierarchical consistency)
    'ContextAggregator',
    'ContextLevel',
    'ProjectContext',
    'SceneContext',
    'FrameContext',
    'CameraContext',
    'LightingState',
    'EstablishedElement',
    'create_context_aggregator',
    # 180-degree rule / Screen Direction
    'ScreenPosition',
    'CharacterScreenPosition',
    # Shot Rhythm
    'ShotCategory',
    'ShotRhythmEntry',
]

