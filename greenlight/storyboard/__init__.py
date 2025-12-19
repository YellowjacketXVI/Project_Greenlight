"""
Greenlight Storyboard Module

Image generation and storyboard output from visual prompts.

Pipeline Flow:
    Visual Script (visual_script.json) → Storyboard Generation → storyboard_output/

Key Components:
    - ImageHandler: Core image generation with Seedream/Gemini
    - StoryboardLabeler: Adds scene.frame.camera labels to images
    - ThumbnailManager: Generates thumbnails for gallery view
    - ShotListExtractor: Extracts shot list from visual script

Directory Structure:
    /prompts/               - Externalized prompt templates
        /01_style/          - Style suffix generation prompts
        /02_composition/    - Composition guidance prompts
    /generators/            - Image generation utilities

Image Generation Flow:
    1. Read prompts from storyboard/prompts.json (editable by user)
    2. Get style suffix from world_config.json via ImageHandler.get_style_suffix()
    3. Generate with Seedream 4.5 (blank-first pattern)
    4. Label with scene.frame.camera notation
    5. Save to storyboard_output/{scene}.{frame}.c{letter}.png

Seedream Blank-First Pattern:
    - Always insert blank image at desired dimension (16:9 at 2K) as first input
    - Reference images come after the dimensional block
"""

# Re-export core components
from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageResult
from greenlight.core.storyboard_labeler import (
    label_storyboard_media,
    get_frame_ids_from_visual_script,
    get_unlabeled_media,
)
from greenlight.core.thumbnail_manager import ThumbnailManager
from greenlight.pipelines.shot_list_extractor import (
    ShotListExtractor,
    ShotEntry,
    SceneGroup,
    ShotList,
    StoryboardPromptGenerator,
)

__all__ = [
    'ImageHandler',
    'ImageRequest',
    'ImageResult',
    'label_storyboard_media',
    'get_frame_ids_from_visual_script',
    'get_unlabeled_media',
    'ThumbnailManager',
    'ShotListExtractor',
    'ShotEntry',
    'SceneGroup',
    'ShotList',
    'StoryboardPromptGenerator',
]

