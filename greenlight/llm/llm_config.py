"""
Greenlight LLM Manager

Manages LLM provider connections and API calls.

OPTIMIZATIONS (v2.1):
- Response caching with hash-based keys and TTL
- Complexity-based model routing for cost optimization
- Singleton client pool for reduced connection overhead
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import os
import asyncio
import time

from greenlight.core.config import LLMConfig, GreenlightConfig, get_config
from greenlight.core.constants import LLMProvider, LLMFunction
from greenlight.core.exceptions import LLMError, LLMProviderError, ContentBlockedError
from greenlight.core.logging_config import get_logger
from greenlight.core.env_loader import ensure_env_loaded

# Import optimization modules
from .response_cache import LLMResponseCache, get_cache
from .complexity_router import ComplexityRouter, TaskComplexity, get_optimal_model

logger = get_logger("llm.manager")


def _load_env():
    """Load environment variables from .env file."""
    return ensure_env_loaded()


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config
        # Load .env before checking for API key
        _load_env()
        self._api_key = os.environ.get(config.api_key_env)
        if not self._api_key:
            logger.warning(f"API key not found: {config.api_key_env}")
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """Generate a response from the LLM."""
        pass
    
    @property
    def is_available(self) -> bool:
        """Check if the provider is available."""
        return self._api_key is not None


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        try:
            import anthropic
            
            client = anthropic.AsyncAnthropic(api_key=self._api_key)
            
            message = await client.messages.create(
                model=self.config.model,
                max_tokens=max_tokens or self.config.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature if temperature is not None else self.config.temperature
            )
            
            return message.content[0].text
            
        except Exception as e:
            raise LLMProviderError("anthropic", str(e))


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider."""
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        try:
            import openai
            
            client = openai.AsyncOpenAI(api_key=self._api_key)
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = await client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature if temperature is not None else self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise LLMProviderError("openai", str(e))


class GoogleProvider(BaseLLMProvider):
    """Google Gemini provider."""

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        try:
            import google.generativeai as genai

            genai.configure(api_key=self._api_key)
            model = genai.GenerativeModel(self.config.model)

            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

            response = await asyncio.to_thread(
                model.generate_content,
                full_prompt,
                generation_config={
                    "temperature": temperature if temperature is not None else self.config.temperature,
                    "max_output_tokens": max_tokens or self.config.max_tokens
                }
            )

            # Check if content was blocked before accessing response.text
            # finish_reason: 0=UNSPECIFIED, 1=STOP(normal), 2=MAX_TOKENS, 3=SAFETY, 4=RECITATION, 5=OTHER
            if not response.candidates:
                # Check prompt_feedback for block reason
                block_reason = "UNKNOWN"
                if hasattr(response, 'prompt_feedback'):
                    feedback = response.prompt_feedback
                    if hasattr(feedback, 'block_reason'):
                        block_reason = str(feedback.block_reason)

                logger.warning(f"Google Gemini blocked content: {block_reason}")
                raise ContentBlockedError("google", f"block_reason: {block_reason}")

            # Check if candidates exist but have no valid parts (blocked content)
            if response.candidates:
                candidate = response.candidates[0]
                # Check finish_reason - 3=SAFETY, 4=RECITATION indicate blocked content
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason in (3, 4):
                    reason_map = {3: "SAFETY", 4: "RECITATION"}
                    block_reason = reason_map.get(candidate.finish_reason, "UNKNOWN")
                    logger.warning(f"Google Gemini blocked content: finish_reason={block_reason}")
                    raise ContentBlockedError("google", f"finish_reason: {block_reason}")

                # Check if parts are empty (another indicator of blocked content)
                if not candidate.content or not candidate.content.parts:
                    logger.warning(f"Google Gemini returned empty content: finish_reason={candidate.finish_reason}")
                    raise ContentBlockedError("google", f"Empty content with finish_reason={candidate.finish_reason}")

            return response.text

        except ContentBlockedError:
            # Re-raise ContentBlockedError without wrapping
            raise
        except Exception as e:
            error_msg = str(e)
            # Check if error message indicates blocked content or empty response
            if "PROHIBITED_CONTENT" in error_msg or "block_reason" in error_msg:
                logger.warning(f"Google Gemini blocked content (from exception): {error_msg}")
                raise ContentBlockedError("google", error_msg)
            # Check for empty parts error (can happen with finish_reason=1 but no content)
            if "response.text" in error_msg and "valid `Part`" in error_msg:
                logger.warning(f"Google Gemini returned no valid parts: {error_msg}")
                raise ContentBlockedError("google", f"No valid parts in response: {error_msg}")
            raise LLMProviderError("google", error_msg)


class GrokProvider(BaseLLMProvider):
    """xAI Grok provider."""

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        try:
            import httpx

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.config.model,
                        "messages": messages,
                        "max_tokens": max_tokens or self.config.max_tokens,
                        "temperature": temperature if temperature is not None else self.config.temperature
                    },
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]

        except Exception as e:
            raise LLMProviderError("grok", str(e))


class LLMManager:
    """
    Manages LLM providers and routes requests.

    Features:
    - Multiple provider support
    - Function-based routing
    - Automatic fallback
    - Response caching with TTL (hash-based)
    - Complexity-based model routing for cost optimization
    """

    PROVIDER_CLASSES = {
        LLMProvider.ANTHROPIC: AnthropicProvider,
        LLMProvider.OPENAI: OpenAIProvider,
        LLMProvider.GOOGLE: GoogleProvider,
        LLMProvider.GROK: GrokProvider,
    }

    def __init__(
        self,
        config: GreenlightConfig = None,
        enable_cache: bool = True,
        cache_ttl: float = 3600.0,
        enable_complexity_routing: bool = True
    ):
        """
        Initialize the LLM manager.

        Args:
            config: Greenlight configuration
            enable_cache: Enable response caching (default True)
            cache_ttl: Cache time-to-live in seconds (default 1 hour)
            enable_complexity_routing: Enable complexity-based model routing
        """
        self.config = config or get_config()
        self._providers: Dict[str, BaseLLMProvider] = {}

        # Initialize caching
        self._cache_enabled = enable_cache and self.config.enable_caching
        if self._cache_enabled:
            self._cache = get_cache(ttl=cache_ttl, enabled=True)
            logger.info(f"LLM response cache enabled (TTL: {cache_ttl}s)")
        else:
            self._cache = None

        # Initialize complexity routing
        self._complexity_routing_enabled = enable_complexity_routing
        if enable_complexity_routing:
            self._complexity_router = ComplexityRouter()
            logger.info("Complexity-based model routing enabled")
        else:
            self._complexity_router = None

        # Stats tracking
        self._call_count = 0
        self._cache_hits = 0
        self._total_time = 0.0

        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize all configured providers."""
        for name, llm_config in self.config.llm_configs.items():
            provider_class = self.PROVIDER_CLASSES.get(llm_config.provider)
            if provider_class:
                self._providers[name] = provider_class(llm_config)
                logger.debug(f"Initialized provider: {name}")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        function: LLMFunction = None,
        temperature: float = None,
        max_tokens: int = None,
        use_cache: bool = True,
        complexity_override: TaskComplexity = None
    ) -> str:
        """
        Generate a response using the appropriate LLM.

        Automatically falls back to Grok if content is blocked by the primary provider.
        Uses response caching and complexity-based model routing for optimization.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            function: Function type for routing
            temperature: Override temperature
            max_tokens: Override max tokens
            use_cache: Whether to use response caching (default True)
            complexity_override: Manual complexity override for model selection

        Returns:
            Generated response text
        """
        start_time = time.time()
        self._call_count += 1

        # Get provider for function
        provider = self._get_provider_for_function(function)

        if not provider:
            raise LLMError("No available LLM provider")

        # Get optimal model based on complexity if routing enabled
        model = provider.config.model
        if self._complexity_routing_enabled and self._complexity_router:
            optimal_model = self._complexity_router.get_model(
                function=function,
                provider=provider.config.provider.value,
                complexity=complexity_override
            )
            # Only override if we have a valid optimal model
            if optimal_model:
                model = optimal_model
                logger.debug(f"Complexity router selected model: {model}")

        # Check cache first
        if use_cache and self._cache_enabled and self._cache:
            func_str = function.value if function else ""
            temp = temperature if temperature is not None else provider.config.temperature

            cached_response = self._cache.get(
                prompt=prompt,
                system_prompt=system_prompt,
                function=func_str,
                model=model,
                temperature=temp
            )

            if cached_response is not None:
                self._cache_hits += 1
                elapsed = time.time() - start_time
                logger.info(f"💾 Cache hit for {func_str or 'request'} ({elapsed:.3f}s)")
                return cached_response

        logger.debug(f"Using provider for {function}: {model}")

        try:
            response = await provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )

            # Cache the response
            if use_cache and self._cache_enabled and self._cache:
                func_str = function.value if function else ""
                temp = temperature if temperature is not None else provider.config.temperature
                token_estimate = len(response.split()) * 1.3  # Rough estimate

                self._cache.set(
                    prompt=prompt,
                    response=response,
                    system_prompt=system_prompt,
                    function=func_str,
                    model=model,
                    temperature=temp,
                    token_count=int(token_estimate)
                )

            elapsed = time.time() - start_time
            self._total_time += elapsed

            return response

        except ContentBlockedError as e:
            # Content was blocked - try Grok as fallback
            logger.warning(f"⚠️  Content blocked by {e.details.get('provider')}: {e.details.get('reason')}")

            grok_provider = self._get_grok_provider()

            # Only fallback if Grok is available and different from current provider
            if grok_provider and grok_provider != provider:
                logger.info(f"🔄 Routing blocked content to Grok for retry...")

                try:
                    response = await grok_provider.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    logger.info(f"✓ Grok successfully processed blocked content ({len(response)} chars)")

                    # Cache the Grok response too
                    if use_cache and self._cache_enabled and self._cache:
                        func_str = function.value if function else ""
                        temp = temperature if temperature is not None else 0.7
                        self._cache.set(
                            prompt=prompt,
                            response=response,
                            system_prompt=system_prompt,
                            function=func_str,
                            model="grok-4",
                            temperature=temp
                        )

                    return response
                except Exception as grok_error:
                    logger.error(f"❌ Grok fallback also failed: {grok_error}")
                    raise LLMError(f"Content blocked by primary provider and Grok fallback failed: {grok_error}")
            else:
                if not grok_provider:
                    logger.error("❌ No Grok provider available for fallback")
                    raise LLMError(f"Content blocked and no Grok fallback available: {e}")
                else:
                    logger.error("❌ Grok was the primary provider that blocked content")
                    raise  # Re-raise original error

    def get_stats(self) -> Dict[str, Any]:
        """Get LLM manager statistics including cache performance."""
        stats = {
            "total_calls": self._call_count,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": f"{(self._cache_hits / self._call_count * 100):.1f}%" if self._call_count > 0 else "0%",
            "total_time": f"{self._total_time:.2f}s",
            "avg_time_per_call": f"{(self._total_time / self._call_count):.3f}s" if self._call_count > 0 else "0s",
        }

        if self._cache:
            stats["cache"] = self._cache.get_stats()

        if self._complexity_router:
            stats["complexity_routing"] = self._complexity_router.get_stats()

        return stats

    def clear_cache(self) -> None:
        """Clear the response cache."""
        if self._cache:
            self._cache.invalidate(clear_all=True)
            logger.info("LLM response cache cleared")
    
    def _get_provider_for_function(
        self,
        function: LLMFunction = None
    ) -> Optional[BaseLLMProvider]:
        """Get the appropriate provider for a function."""
        if function and function in self.config.function_mappings:
            mapping = self.config.function_mappings[function]

            # Try primary
            for name, provider in self._providers.items():
                if provider.config == mapping.primary_config and provider.is_available:
                    return provider

            # Try fallback
            if mapping.fallback_config:
                for name, provider in self._providers.items():
                    if provider.config == mapping.fallback_config and provider.is_available:
                        return provider

        # Return first available provider
        for provider in self._providers.values():
            if provider.is_available:
                return provider

        return None

    def _get_grok_provider(self) -> Optional[BaseLLMProvider]:
        """
        Get Grok provider for content-blocked fallback.

        Returns:
            Grok provider if available, None otherwise
        """
        for name, provider in self._providers.items():
            if provider.config.provider == LLMProvider.GROK and provider.is_available:
                logger.debug(f"Found Grok provider: {name}")
                return provider
        logger.debug("No Grok provider available for fallback")
        return None

