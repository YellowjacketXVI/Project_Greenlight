"""
Greenlight Configuration Module

Contains configuration for word caps, notation patterns, and procedural generation.
"""

from greenlight.config.word_caps import (
    WORD_CAPS,
    OUTPUT_BUDGETS,
    FRAME_PROMPT_CAP,
    get_word_cap,
    get_output_budget,
)

from greenlight.config.notation_patterns import (
    REGEX_PATTERNS,
    FRAME_NOTATION_MARKERS,
)

from greenlight.config.api_dictionary import (
    lookup_model,
    lookup_by_symbol,
    get_image_models,
    get_text_models,
    get_model_summary,
    MODEL_SYMBOLS,
    ALL_MODELS,
    APIProvider,
    ModelCapability,
    ModelEntry,
)

__all__ = [
    'WORD_CAPS',
    'OUTPUT_BUDGETS',
    'FRAME_PROMPT_CAP',
    'get_word_cap',
    'get_output_budget',
    'REGEX_PATTERNS',
    'FRAME_NOTATION_MARKERS',
    # API Dictionary
    'lookup_model',
    'lookup_by_symbol',
    'get_image_models',
    'get_text_models',
    'get_model_summary',
    'MODEL_SYMBOLS',
    'ALL_MODELS',
    'APIProvider',
    'ModelCapability',
    'ModelEntry',
]

