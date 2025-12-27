"""
Startup validation and environment checks.

Validates required API keys and configuration at application startup.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationResult:
    """Result of environment validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# Required API keys - at least one LLM provider must be configured
REQUIRED_LLM_KEYS = [
    ("ANTHROPIC_API_KEY", "Anthropic Claude"),
    ("GEMINI_API_KEY", "Google Gemini"),
    ("GOOGLE_API_KEY", "Google Gemini (alternative)"),
    ("OPENAI_API_KEY", "OpenAI"),
    ("XAI_API_KEY", "xAI Grok"),
]

# Optional but recommended keys
OPTIONAL_KEYS = [
    ("REPLICATE_API_TOKEN", "Replicate (image generation)"),
]


def validate_environment() -> ValidationResult:
    """
    Validate the environment configuration.

    Checks:
    - At least one LLM provider API key is set
    - Optional keys are present (warnings if missing)

    Returns:
        ValidationResult with validation status and any errors/warnings
    """
    errors = []
    warnings = []

    # Check for at least one LLM provider
    llm_keys_found = []
    for key_name, provider_name in REQUIRED_LLM_KEYS:
        value = os.environ.get(key_name)
        if value and value.strip():
            llm_keys_found.append(provider_name)

    if not llm_keys_found:
        errors.append(
            "No LLM provider API key found. Set at least one of: "
            + ", ".join(key for key, _ in REQUIRED_LLM_KEYS)
        )

    # Check optional keys
    for key_name, description in OPTIONAL_KEYS:
        value = os.environ.get(key_name)
        if not value or not value.strip():
            warnings.append(f"{key_name} not set - {description} will be unavailable")

    # Check for Gemini key specifically (preferred provider)
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not gemini_key:
        warnings.append(
            "GEMINI_API_KEY not set - Gemini is the preferred provider for story generation"
        )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def get_available_providers() -> List[str]:
    """
    Get list of available LLM providers based on configured API keys.

    Returns:
        List of provider names that have valid API keys
    """
    providers = []

    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("anthropic")

    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        providers.append("gemini")

    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")

    if os.environ.get("XAI_API_KEY"):
        providers.append("grok")

    return providers


def check_image_generation_available() -> bool:
    """Check if image generation is available."""
    return bool(os.environ.get("REPLICATE_API_TOKEN"))
