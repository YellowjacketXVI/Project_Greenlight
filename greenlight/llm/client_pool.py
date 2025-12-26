"""
Greenlight API Client Pool

Singleton pattern for API client management.
Reduces connection overhead by reusing client instances.
"""

import threading
from typing import Dict, Optional, Any
from enum import Enum

from greenlight.core.logging_config import get_logger

logger = get_logger("llm.client_pool")


class ClientPool:
    """
    Thread-safe singleton pool for API clients.

    Maintains one instance per provider to avoid repeated initialization.
    Clients are lazily instantiated on first use.
    """

    _instance: Optional['ClientPool'] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'ClientPool':
        """Get or create singleton pool instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the pool (for testing or reconfiguration)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._clients.clear()
            cls._instance = None

    def __init__(self):
        """Initialize the client pool."""
        self._clients: Dict[str, Any] = {}
        self._client_lock = threading.RLock()
        self._initialization_count: Dict[str, int] = {}

    def get_anthropic(self, **kwargs) -> 'AnthropicClient':
        """
        Get the Anthropic client instance.

        Args:
            **kwargs: Override default client settings

        Returns:
            Shared AnthropicClient instance
        """
        return self._get_or_create('anthropic', **kwargs)

    def get_gemini(self, **kwargs) -> 'GeminiClient':
        """
        Get the Gemini client instance.

        Args:
            **kwargs: Override default client settings

        Returns:
            Shared GeminiClient instance
        """
        return self._get_or_create('gemini', **kwargs)

    def get_grok(self, **kwargs) -> 'GrokClient':
        """
        Get the Grok client instance.

        Args:
            **kwargs: Override default client settings

        Returns:
            Shared GrokClient instance
        """
        return self._get_or_create('grok', **kwargs)

    def get_replicate(self, **kwargs) -> 'ReplicateClient':
        """
        Get the Replicate client instance.

        Args:
            **kwargs: Override default client settings

        Returns:
            Shared ReplicateClient instance
        """
        return self._get_or_create('replicate', **kwargs)

    def get_by_provider(self, provider: str, **kwargs) -> Any:
        """
        Get client by provider name.

        Args:
            provider: Provider name ('anthropic', 'gemini', 'grok', 'replicate')
            **kwargs: Override default client settings

        Returns:
            Appropriate client instance
        """
        provider = provider.lower()
        if provider in ('anthropic', 'claude'):
            return self.get_anthropic(**kwargs)
        elif provider in ('gemini', 'google'):
            return self.get_gemini(**kwargs)
        elif provider in ('grok', 'xai'):
            return self.get_grok(**kwargs)
        elif provider == 'replicate':
            return self.get_replicate(**kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _get_or_create(self, provider: str, **kwargs) -> Any:
        """
        Get or create a client for the specified provider.

        Args:
            provider: Provider identifier
            **kwargs: Client initialization arguments

        Returns:
            Client instance
        """
        # Generate key including any override settings
        key = self._make_key(provider, kwargs)

        with self._client_lock:
            if key not in self._clients:
                self._clients[key] = self._create_client(provider, **kwargs)
                self._initialization_count[provider] = \
                    self._initialization_count.get(provider, 0) + 1

                logger.debug(
                    f"Created {provider} client (total initializations: "
                    f"{self._initialization_count[provider]})"
                )

            return self._clients[key]

    def _make_key(self, provider: str, kwargs: dict) -> str:
        """Generate a cache key for the provider + settings combination."""
        if not kwargs:
            return provider

        # Include significant settings in key
        significant_keys = ['timeout', 'show_spinner']
        settings = tuple(
            (k, kwargs[k])
            for k in sorted(significant_keys)
            if k in kwargs
        )
        return f"{provider}:{hash(settings)}"

    def _create_client(self, provider: str, **kwargs) -> Any:
        """Create a new client instance."""
        # Import here to avoid circular imports
        from .api_clients import (
            AnthropicClient,
            GeminiClient,
            GrokClient,
            ReplicateClient
        )

        creators = {
            'anthropic': AnthropicClient,
            'gemini': GeminiClient,
            'grok': GrokClient,
            'replicate': ReplicateClient
        }

        creator = creators.get(provider)
        if creator is None:
            raise ValueError(f"Unknown provider: {provider}")

        return creator(**kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._client_lock:
            return {
                'active_clients': len(self._clients),
                'providers': list(set(k.split(':')[0] for k in self._clients.keys())),
                'initialization_counts': dict(self._initialization_count)
            }

    def clear_provider(self, provider: str) -> None:
        """Clear cached client for a specific provider."""
        with self._client_lock:
            keys_to_remove = [
                k for k in self._clients.keys()
                if k == provider or k.startswith(f"{provider}:")
            ]
            for key in keys_to_remove:
                del self._clients[key]
                logger.debug(f"Cleared client: {key}")


# Convenience functions for direct access
def get_anthropic(**kwargs) -> 'AnthropicClient':
    """Get shared Anthropic client."""
    return ClientPool.get_instance().get_anthropic(**kwargs)


def get_gemini(**kwargs) -> 'GeminiClient':
    """Get shared Gemini client."""
    return ClientPool.get_instance().get_gemini(**kwargs)


def get_grok(**kwargs) -> 'GrokClient':
    """Get shared Grok client."""
    return ClientPool.get_instance().get_grok(**kwargs)


def get_replicate(**kwargs) -> 'ReplicateClient':
    """Get shared Replicate client."""
    return ClientPool.get_instance().get_replicate(**kwargs)


def get_client(provider: str, **kwargs) -> Any:
    """Get shared client by provider name."""
    return ClientPool.get_instance().get_by_provider(provider, **kwargs)
