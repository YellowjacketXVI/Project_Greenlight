"""
Greenlight References Module

Reference image management integrated with the tag system.
Includes template-based prompt building (no LLM calls).
"""

from .reference_manager import ReferenceManager
from .prompt_builder import (
    ReferencePromptBuilder,
    ReferencePromptResult,
    ReferencePromptType,
    build_reference_prompt,
)

__all__ = [
    'ReferenceManager',
    # Template-based prompt building (replaces ReferencePromptAgent)
    'ReferencePromptBuilder',
    'ReferencePromptResult',
    'ReferencePromptType',
    'build_reference_prompt',
]

