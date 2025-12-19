"""
Director Prompts Module

Externalized prompts for the Director pipeline, organized by execution phase.

Prompt Organization:
    01_scene_parsing/   - Scene chunking and parsing
    02_frame_count/     - Frame count consensus (3 judges)
    03_frame_points/    - Frame point determination
    04_camera/          - Camera placement and shot types
    05_visual_prompts/  - Visual prompt generation (250 word cap)

Usage:
    from greenlight.core.prompt_loader import PromptLoader
    
    # Load a prompt
    prompt = PromptLoader.load("director/prompts/04_camera", "camera_placement_prompt")
    
    # Load with TAG_NAMING_RULES injected
    prompt = PromptLoader.load_with_tag_rules("director/prompts/05_visual_prompts", "frame_prompt_prompt")
"""

__all__ = []

