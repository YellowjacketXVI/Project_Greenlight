"""
Greenlight Pipelines Module

Processing pipelines for story development, shot planning, and cinematic direction.

Pipeline Flow (Writer_Flow_v2):
1. StoryPipeline (Writer): Pitch → Script (scripts/script.md)
2. DirectingPipeline (Director): Script → Visual_Script (frame notations, camera, prompts)

NOTE: Novelization pipeline and old DirectorPipeline have been removed.
"""

from .story_pipeline import StoryPipeline
from .shot_pipeline import ShotPipeline
from .directing_pipeline import DirectingPipeline, DirectingInput, VisualScriptOutput
from .quality_pipeline import QualityPipeline
from .shot_list_extractor import (
    ShotListExtractor,
    ShotEntry,
    SceneGroup,
    ShotList,
    StoryboardPromptGenerator,
)
from .story_pipeline_v3 import (
    StoryPipelineV3,
    StoryPipelineV3Config,
    StoryPipelineV3Output,
)

__all__ = [
    'StoryPipeline',
    'ShotPipeline',
    'DirectingPipeline',
    'DirectingInput',
    'VisualScriptOutput',
    'QualityPipeline',
    # Shot list extraction
    'ShotListExtractor',
    'ShotEntry',
    'SceneGroup',
    'ShotList',
    'StoryboardPromptGenerator',
    # Story Pipeline v3.0
    'StoryPipelineV3',
    'StoryPipelineV3Config',
    'StoryPipelineV3Output',
]

