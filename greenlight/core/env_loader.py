"""
Centralized environment variable loading for Project Greenlight.

This module ensures .env is loaded once and consistently across the entire application.
Import this module early in the application startup to ensure env vars are available.

Usage:
    from greenlight.core.env_loader import ensure_env_loaded
    ensure_env_loaded()
"""

import os
from pathlib import Path
from typing import Optional

_env_loaded = False


def get_project_root() -> Path:
    """Get the project root directory (where .env is located)."""
    # This file is at greenlight/core/env_loader.py
    # Project root is 2 levels up
    return Path(__file__).parent.parent.parent


def ensure_env_loaded(override: bool = True) -> bool:
    """
    Ensure environment variables from .env are loaded.

    Args:
        override: If True, override existing environment variables (default: True)
                  This ensures .env values take precedence over empty system vars

    Returns:
        True if .env was loaded, False if already loaded or file not found
    """
    global _env_loaded

    if _env_loaded:
        return False

    try:
        from dotenv import load_dotenv
    except ImportError:
        # dotenv not installed, rely on system env vars
        return False

    env_path = get_project_root() / ".env"

    if not env_path.exists():
        return False

    # Always use override=True to ensure .env values take precedence
    # This handles cases where system has empty string env vars
    load_dotenv(env_path, override=True)
    _env_loaded = True
    return True


def get_api_key(key_name: str, fallback_keys: Optional[list[str]] = None) -> Optional[str]:
    """
    Get an API key from environment, with fallback options.

    Args:
        key_name: Primary environment variable name
        fallback_keys: List of fallback variable names to try

    Returns:
        API key value or None if not found
    """
    ensure_env_loaded()

    value = os.getenv(key_name)
    if value:
        return value

    if fallback_keys:
        for fallback in fallback_keys:
            value = os.getenv(fallback)
            if value:
                return value

    return None


# Common API key getters with fallbacks
def get_google_api_key() -> Optional[str]:
    """Get Google/Gemini API key."""
    return get_api_key("GOOGLE_API_KEY", ["GEMINI_API_KEY"])


def get_anthropic_api_key() -> Optional[str]:
    """Get Anthropic API key."""
    return get_api_key("ANTHROPIC_API_KEY")


def get_replicate_api_key() -> Optional[str]:
    """Get Replicate API key."""
    return get_api_key("REPLICATE_API_TOKEN", ["REPLICATE_API_KEY"])


def get_together_api_key() -> Optional[str]:
    """Get Together AI API key."""
    return get_api_key("TOGETHER_API_KEY")


def get_xai_api_key() -> Optional[str]:
    """Get xAI API key."""
    return get_api_key("XAI_API_KEY")


# Load env on module import
ensure_env_loaded()
