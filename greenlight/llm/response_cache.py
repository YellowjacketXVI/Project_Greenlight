"""
Greenlight LLM Response Cache

Hash-based caching for LLM responses with TTL support.
Reduces redundant API calls by caching identical prompts.
"""

import hashlib
import json
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Any
from pathlib import Path

from greenlight.core.logging_config import get_logger

logger = get_logger("llm.cache")


@dataclass
class CacheEntry:
    """A cached LLM response entry."""
    response: str
    timestamp: float
    model: str
    token_count: int = 0
    hit_count: int = 0

    def is_expired(self, ttl: float) -> bool:
        """Check if entry has expired."""
        return time.time() - self.timestamp > ttl


@dataclass
class CacheStats:
    """Statistics for cache performance."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_tokens_saved: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": f"{self.hit_rate:.2%}",
            "tokens_saved": self.total_tokens_saved
        }


class LLMResponseCache:
    """
    Thread-safe LLM response cache with TTL and size limits.

    Features:
    - Hash-based key generation from prompt + system + function
    - Configurable TTL (default 1 hour)
    - Max size with LRU eviction
    - Optional persistence to disk
    - Hit/miss statistics
    """

    # Singleton instance
    _instance: Optional['LLMResponseCache'] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, **kwargs) -> 'LLMResponseCache':
        """Get or create singleton cache instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        with cls._lock:
            cls._instance = None

    def __init__(
        self,
        ttl: float = 3600.0,  # 1 hour default
        max_size: int = 500,
        persist_path: Optional[Path] = None,
        enabled: bool = True
    ):
        """
        Initialize the response cache.

        Args:
            ttl: Time-to-live in seconds (default 1 hour)
            max_size: Maximum cache entries
            persist_path: Optional path for disk persistence
            enabled: Whether caching is enabled
        """
        self.ttl = ttl
        self.max_size = max_size
        self.persist_path = persist_path
        self.enabled = enabled

        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: list = []  # For LRU tracking
        self._lock = threading.RLock()
        self._stats = CacheStats()

        # Load from disk if persistence enabled
        if persist_path and persist_path.exists():
            self._load_from_disk()

    def _generate_key(
        self,
        prompt: str,
        system_prompt: str = "",
        function: str = "",
        model: str = "",
        temperature: float = 0.7
    ) -> str:
        """
        Generate a unique cache key from prompt components.

        Uses SHA-256 hash truncated to 16 chars for efficiency.
        Includes temperature in key since it affects output.
        """
        # Normalize inputs
        content = json.dumps({
            "prompt": prompt.strip(),
            "system": system_prompt.strip(),
            "function": function,
            "model": model,
            "temp": round(temperature, 2)
        }, sort_keys=True)

        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(
        self,
        prompt: str,
        system_prompt: str = "",
        function: str = "",
        model: str = "",
        temperature: float = 0.7
    ) -> Optional[str]:
        """
        Get cached response if available and not expired.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            function: LLM function name
            model: Model identifier
            temperature: Generation temperature

        Returns:
            Cached response or None
        """
        if not self.enabled:
            return None

        key = self._generate_key(prompt, system_prompt, function, model, temperature)

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired(self.ttl):
                # Remove expired entry
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._stats.misses += 1
                self._stats.evictions += 1
                return None

            # Cache hit - update access order for LRU
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            entry.hit_count += 1
            self._stats.hits += 1
            self._stats.total_tokens_saved += entry.token_count

            logger.debug(f"Cache hit for key {key[:8]}... (hits: {entry.hit_count})")
            return entry.response

    def set(
        self,
        prompt: str,
        response: str,
        system_prompt: str = "",
        function: str = "",
        model: str = "",
        temperature: float = 0.7,
        token_count: int = 0
    ) -> None:
        """
        Cache a response.

        Args:
            prompt: User prompt
            response: LLM response to cache
            system_prompt: System prompt
            function: LLM function name
            model: Model identifier
            temperature: Generation temperature
            token_count: Estimated token count for stats
        """
        if not self.enabled:
            return

        key = self._generate_key(prompt, system_prompt, function, model, temperature)

        with self._lock:
            # Evict oldest entries if at capacity
            while len(self._cache) >= self.max_size and self._access_order:
                oldest_key = self._access_order.pop(0)
                if oldest_key in self._cache:
                    del self._cache[oldest_key]
                    self._stats.evictions += 1

            # Add new entry
            self._cache[key] = CacheEntry(
                response=response,
                timestamp=time.time(),
                model=model,
                token_count=token_count
            )
            self._access_order.append(key)

            logger.debug(f"Cached response for key {key[:8]}... ({len(response)} chars)")

    def invalidate(
        self,
        prompt: str = None,
        function: str = None,
        clear_all: bool = False
    ) -> int:
        """
        Invalidate cache entries.

        Args:
            prompt: Specific prompt to invalidate
            function: Invalidate all entries for a function
            clear_all: Clear entire cache

        Returns:
            Number of entries removed
        """
        with self._lock:
            if clear_all:
                count = len(self._cache)
                self._cache.clear()
                self._access_order.clear()
                logger.info(f"Cache cleared ({count} entries)")
                return count

            # Function-based invalidation requires scanning
            if function:
                # We don't store function in entry, so this requires
                # maintaining a secondary index - skip for now
                pass

            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                **self._stats.to_dict(),
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl,
                "enabled": self.enabled
            }

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items()
                if v.is_expired(self.ttl)
            ]

            for key in expired_keys:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._stats.evictions += 1

            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

            return len(expired_keys)

    def _load_from_disk(self) -> None:
        """Load cache from disk persistence."""
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            with open(self.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for key, entry_data in data.get('entries', {}).items():
                entry = CacheEntry(
                    response=entry_data['response'],
                    timestamp=entry_data['timestamp'],
                    model=entry_data.get('model', ''),
                    token_count=entry_data.get('token_count', 0)
                )

                # Only load non-expired entries
                if not entry.is_expired(self.ttl):
                    self._cache[key] = entry
                    self._access_order.append(key)

            logger.info(f"Loaded {len(self._cache)} cache entries from disk")

        except Exception as e:
            logger.warning(f"Failed to load cache from disk: {e}")

    def save_to_disk(self) -> None:
        """Save cache to disk for persistence."""
        if not self.persist_path:
            return

        try:
            with self._lock:
                data = {
                    'entries': {
                        k: {
                            'response': v.response,
                            'timestamp': v.timestamp,
                            'model': v.model,
                            'token_count': v.token_count
                        }
                        for k, v in self._cache.items()
                        if not v.is_expired(self.ttl)
                    }
                }

            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persist_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)

            logger.info(f"Saved {len(data['entries'])} cache entries to disk")

        except Exception as e:
            logger.warning(f"Failed to save cache to disk: {e}")


# Convenience function for quick access
def get_cache(**kwargs) -> LLMResponseCache:
    """Get the global cache instance."""
    return LLMResponseCache.get_instance(**kwargs)
