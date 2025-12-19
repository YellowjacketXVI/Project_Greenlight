"""
Writer Prompts Module

Externalized prompts for the Writer pipeline, organized by execution phase.

Prompt Organization:
    01_parsing/     - Input parsing and cleaning
    02_tags/        - Tag extraction and consensus
    03_plot/        - Plot architecture generation
    04_character/   - Character architecture generation
    05_scenes/      - Scene generation from plot points
    06_quality/     - Quality assurance and validation

Usage:
    from greenlight.core.prompt_loader import PromptLoader
    
    # Load a prompt
    prompt = PromptLoader.load("writer/prompts/03_plot", "plot_architecture_prompt")
    
    # Load with TAG_NAMING_RULES injected
    prompt = PromptLoader.load_with_tag_rules("writer/prompts/02_tags", "tag_extraction_prompt")
"""

__all__ = []

