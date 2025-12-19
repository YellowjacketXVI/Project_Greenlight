"""
Greenlight Director Module

The Director pipeline transforms a script into a visual script with frame notations,
camera placements, and visual prompts for storyboard generation.

Pipeline Flow:
    Script (scripts/script.md) → Director Pipeline → Visual Script (visual_script.json)

Key Components:
    - DirectingPipeline: Main visual script generation engine
    - FrameCountConsensus: 3-judge consensus for frame count per scene
    - CameraPlacementAgent: Camera angle and shot type selection
    - VisualPromptGenerator: Image generation prompt creation

Directory Structure:
    /prompts/               - Externalized prompt templates
        /01_scene_parsing/  - Scene chunking prompts
        /02_frame_count/    - Frame count consensus prompts
        /03_frame_points/   - Frame point determination prompts
        /04_camera/         - Camera placement prompts
        /05_visual_prompts/ - Visual prompt generation prompts
    /agents/                - Director-specific agents

Scene.Frame.Camera Notation:
    Format: {scene}.{frame}.c{letter}
    Examples: 1.1.cA, 2.3.cB, 8.15.cC

Outputs:
    - visual_script.json: Frame notations with camera and prompts
    - storyboard/prompts.json: Editable prompts for storyboard generation
"""

# Re-export main pipeline for convenience
from greenlight.pipelines.directing_pipeline import (
    DirectingPipeline,
    DirectingInput,
    VisualScriptOutput,
)

__all__ = [
    'DirectingPipeline',
    'DirectingInput',
    'VisualScriptOutput',
]

