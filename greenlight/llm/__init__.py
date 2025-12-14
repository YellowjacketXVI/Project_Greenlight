"""
Greenlight LLM Module

LLM integration layer with provider implementations and function-to-LLM routing.
Supports: Anthropic Claude, Google Gemini, xAI Grok, Replicate Seedream
"""

# API Clients
from .api_clients import (
    APIError,
    APITimeoutError,
    AnalysisResponse,
    AnthropicClient,
    BaseAPIClient,
    GeminiClient,
    GrokClient,
    ImageResponse,
    RateLimitError,
    ReplicateClient,
    TextResponse,
    ThinkingSpinner,
    UnifiedImageGenerator,
    get_available_providers,
    get_default_client,
    load_env,
)

# LLM Registry
from .llm_registry import (
    LLM_REGISTRY,
    LLMConfig,
    LLMInfo,
    generate_text,
    get_llm_by_id,
    get_llm_client,
    list_available_llms,
)

# Legacy imports for compatibility
from .llm_config import LLMManager
from .function_router import FunctionRouter

__all__ = [
    # API Clients
    'BaseAPIClient',
    'GeminiClient',
    'AnthropicClient',
    'GrokClient',
    'ReplicateClient',
    'UnifiedImageGenerator',
    'ThinkingSpinner',
    # Response Types
    'TextResponse',
    'ImageResponse',
    'AnalysisResponse',
    # Exceptions
    'APIError',
    'RateLimitError',
    'APITimeoutError',
    # Registry
    'LLMInfo',
    'LLMConfig',
    'LLM_REGISTRY',
    'list_available_llms',
    'get_llm_by_id',
    'get_llm_client',
    'generate_text',
    # Utilities
    'load_env',
    'get_available_providers',
    'get_default_client',
    # Legacy
    'LLMManager',
    'FunctionRouter',
]

