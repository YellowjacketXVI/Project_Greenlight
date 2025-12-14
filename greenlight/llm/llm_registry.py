"""
Greenlight LLM Registry

Central registry of all available LLM models with their configurations.
Ported from Prometheus Director with enhancements.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from greenlight.llm.api_clients import (
    AnthropicClient,
    BaseAPIClient,
    GeminiClient,
    GrokClient,
    load_env,
)


# ============================================================================
#  LLM INFO DATACLASS
# ============================================================================

@dataclass
class LLMInfo:
    """Complete information about an LLM model."""

    id: str
    name: str
    provider: str  # "anthropic", "google", "xai"
    model: str  # Actual model identifier for API
    description: str = ""
    env_key: str = ""  # Primary environment variable for API key
    alt_env_keys: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    context_window: int = 128000
    max_output_tokens: int = 8192
    default_temperature: float = 0.7
    supports_system_prompt: bool = True
    supports_streaming: bool = False
    api_version: str = ""
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def is_available(self) -> bool:
        """Check if API key is configured for this LLM."""
        load_env()
        if os.getenv(self.env_key):
            return True
        for alt_key in self.alt_env_keys:
            if os.getenv(alt_key):
                return True
        return False

    def get_api_key(self) -> Optional[str]:
        """Get the API key for this LLM."""
        load_env()
        key = os.getenv(self.env_key)
        if key:
            return key
        for alt_key in self.alt_env_keys:
            key = os.getenv(alt_key)
            if key:
                return key
        return None

    def get_api_params(self, prompt: str, system: Optional[str] = None,
                       max_tokens: Optional[int] = None,
                       temperature: Optional[float] = None) -> Dict[str, Any]:
        """Build API call parameters for this LLM."""
        params = {
            "prompt": prompt,
            "model": self.model,
            "max_tokens": max_tokens or self.max_output_tokens,
            "temperature": temperature or self.default_temperature,
        }
        if self.supports_system_prompt and system:
            params["system"] = system
        return params


# ============================================================================
#  LLM REGISTRY
# ============================================================================

LLM_REGISTRY: Dict[str, LLMInfo] = {
    # Anthropic Claude Models
    "claude-opus": LLMInfo(
        id="claude-opus",
        name="Claude Opus 4.5",
        provider="anthropic",
        model="claude-opus-4-5-20251101",
        description="Premium model - maximum intelligence with practical performance",
        env_key="ANTHROPIC_API_KEY",
        alt_env_keys=["CLAUDE_API_KEY"],
        capabilities=["text", "reasoning", "complex", "vision"],
        context_window=200000,
        max_output_tokens=32000,
        default_temperature=0.7,
        supports_system_prompt=True,
        api_version="2023-06-01"
    ),
    "claude-sonnet": LLMInfo(
        id="claude-sonnet",
        name="Claude Sonnet 4.5",
        provider="anthropic",
        model="claude-sonnet-4-5-20250929",
        description="Smart model for complex agents and coding tasks",
        env_key="ANTHROPIC_API_KEY",
        alt_env_keys=["CLAUDE_API_KEY"],
        capabilities=["text", "reasoning", "vision"],
        context_window=200000,
        max_output_tokens=16000,
        default_temperature=0.7,
        supports_system_prompt=True,
        api_version="2023-06-01"
    ),
    "claude-haiku": LLMInfo(
        id="claude-haiku",
        name="Claude Haiku 4.5",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        description="Fastest model with near-frontier intelligence",
        env_key="ANTHROPIC_API_KEY",
        alt_env_keys=["CLAUDE_API_KEY"],
        capabilities=["text", "reasoning"],
        context_window=200000,
        max_output_tokens=8192,
        default_temperature=0.7,
        supports_system_prompt=True,
        api_version="2023-06-01"
    ),

    # Google Gemini Models
    "gemini-flash": LLMInfo(
        id="gemini-flash",
        name="Gemini 2.5 Flash",
        provider="google",
        model="gemini-2.5-flash",
        description="Fast, efficient text generation with 1M context",
        env_key="GEMINI_API_KEY",
        alt_env_keys=["GOOGLE_API_KEY"],
        capabilities=["text", "vision", "code"],
        context_window=1048576,
        max_output_tokens=65536,
        default_temperature=0.7,
        supports_system_prompt=False,
        supports_streaming=True
    ),
    "gemini-pro": LLMInfo(
        id="gemini-pro",
        name="Gemini 3 Pro",
        provider="google",
        model="gemini-3-pro-preview",
        description="Advanced reasoning with vision and image generation",
        env_key="GEMINI_API_KEY",
        alt_env_keys=["GOOGLE_API_KEY"],
        capabilities=["text", "vision", "image_gen", "reasoning"],
        context_window=1048576,
        max_output_tokens=65536,
        default_temperature=0.7,
        supports_system_prompt=False,
        supports_streaming=True
    ),

    # xAI Grok Models
    "grok-4": LLMInfo(
        id="grok-4",
        name="Grok 4 Latest Reasoning",
        provider="xai",
        model="grok-4",
        description="Most intelligent reasoning model with native tool use",
        env_key="XAI_API_KEY",
        alt_env_keys=["GROK_API_KEY"],
        capabilities=["text", "reasoning", "tools", "search"],
        context_window=131072,
        max_output_tokens=16384,
        default_temperature=0.7,
        supports_system_prompt=True,
        supports_streaming=True
    ),
    "grok-3-fast": LLMInfo(
        id="grok-3-fast",
        name="Grok 3 Fast",
        provider="xai",
        model="grok-3-fast",
        description="Cost-efficient reasoning model",
        env_key="XAI_API_KEY",
        alt_env_keys=["GROK_API_KEY"],
        capabilities=["text", "reasoning"],
        context_window=131072,
        max_output_tokens=16384,
        default_temperature=0.7,
        supports_system_prompt=True,
        supports_streaming=True
    ),

    # Validation Profiles
    "claude-haiku-validator": LLMInfo(
        id="claude-haiku-validator",
        name="Claude Haiku Validator",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        description="Claude Haiku optimized for chunk validation",
        env_key="ANTHROPIC_API_KEY",
        alt_env_keys=["CLAUDE_API_KEY"],
        capabilities=["text", "validation", "json"],
        context_window=200000,
        max_output_tokens=500,
        default_temperature=0.0,
        supports_system_prompt=True,
        api_version="2023-06-01",
        extra_params={"validation_mode": True, "strict_json": True}
    ),
}



# ============================================================================
#  LLM CONFIG
# ============================================================================

@dataclass
class LLMConfig:
    """Runtime configuration for a selected LLM."""

    provider: str
    model: str
    api_key: Optional[str] = None
    max_tokens: int = 8192
    temperature: float = 0.7
    name: str = ""
    supports_system_prompt: bool = True
    llm_info: Optional[LLMInfo] = None

    @classmethod
    def from_llm_info(cls, info: LLMInfo) -> "LLMConfig":
        """Create config from LLMInfo."""
        return cls(
            provider=info.provider,
            model=info.model,
            api_key=info.get_api_key(),
            max_tokens=info.max_output_tokens,
            temperature=info.default_temperature,
            name=info.name,
            supports_system_prompt=info.supports_system_prompt,
            llm_info=info
        )

    def get_api_params(self, prompt: str, system: Optional[str] = None,
                       max_tokens: Optional[int] = None,
                       temperature: Optional[float] = None) -> Dict[str, Any]:
        """Build API call parameters."""
        if self.llm_info:
            return self.llm_info.get_api_params(
                prompt=prompt,
                system=system,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature
            )

        params = {
            "prompt": prompt,
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
        }
        if self.supports_system_prompt and system:
            params["system"] = system
        return params


# ============================================================================
#  SELECTION FUNCTIONS
# ============================================================================

def list_available_llms(show_unavailable: bool = False) -> List[LLMInfo]:
    """List all available LLMs (those with configured API keys)."""
    available = []
    for llm in LLM_REGISTRY.values():
        if llm.is_available() or show_unavailable:
            available.append(llm)
    return available


def get_llm_by_id(llm_id: str) -> Optional[LLMConfig]:
    """Get LLM config by ID without interactive selection."""
    llm = LLM_REGISTRY.get(llm_id.lower())
    if llm and llm.is_available():
        return LLMConfig.from_llm_info(llm)
    return None


def get_llm_client(config: LLMConfig) -> BaseAPIClient:
    """Get an API client instance for the given LLM config."""
    if config.provider == "google":
        return GeminiClient(api_key=config.api_key)
    elif config.provider == "anthropic":
        return AnthropicClient(api_key=config.api_key)
    elif config.provider == "xai":
        return GrokClient(api_key=config.api_key)
    else:
        raise ValueError(f"Unknown provider: {config.provider}")


def generate_text(config: LLMConfig, prompt: str, system: str = None,
                  temperature: float = None, max_tokens: int = None):
    """Generate text using the configured LLM.

    Convenience function that handles client creation and API calls.
    """
    from greenlight.llm.api_clients import TextResponse

    client = get_llm_client(config)
    params = config.get_api_params(
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature
    )

    temp = params.get("temperature", config.temperature)
    tokens = params.get("max_tokens", config.max_tokens)
    model = params.get("model", config.model)
    sys_prompt = params.get("system")

    if config.provider == "google":
        full_prompt = f"{sys_prompt}\n\n{prompt}" if sys_prompt else prompt
        return client.generate_text(full_prompt, temperature=temp, max_tokens=tokens, model=model)
    elif config.provider == "anthropic":
        return client.generate_text(prompt, system=sys_prompt, max_tokens=tokens, model=model)
    elif config.provider == "xai":
        return client.generate_text(prompt, system=sys_prompt, temperature=temp, max_tokens=tokens, model=model)
    else:
        raise ValueError(f"Unknown provider: {config.provider}")

