"""
Quality Prompts Module

Externalized prompts for quality assurance agents, organized by agent type.

Prompt Organization:
    01_telescope/       - Narrative coherence checking
    02_inquisitor/      - Technical validation (multi-agent panel)
    03_continuity/      - Continuity tracking and validation
    04_constellation/   - Relationship mapping between elements
    05_anchor/          - Notation validation (tags, scene.frame.camera)
    06_coherence/       - Character motivation coherence

Usage:
    from greenlight.core.prompt_loader import PromptLoader
    
    # Load a prompt
    prompt = PromptLoader.load("quality/prompts/01_telescope", "narrative_coherence_prompt")
    
    # Load with TAG_NAMING_RULES injected
    prompt = PromptLoader.load_with_tag_rules("quality/prompts/05_anchor", "notation_validation_prompt")
"""

__all__ = []

