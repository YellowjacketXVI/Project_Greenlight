"""
Greenlight LLM Manager

Manages LLM provider connections and API calls.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import os
import asyncio

from greenlight.core.config import LLMConfig, GreenlightConfig, get_config
from greenlight.core.constants import LLMProvider, LLMFunction
from greenlight.core.exceptions import LLMError, LLMProviderError, ContentBlockedError
from greenlight.core.logging_config import get_logger

logger = get_logger("llm.manager")


def _load_env():
    """Load environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        # Try multiple locations
        for env_path in [Path(".env"), Path("../.env"), Path(__file__).parent.parent.parent / ".env"]:
            if env_path.exists():
                load_dotenv(env_path)
                logger.debug(f"Loaded .env from {env_path}")
                return True
        return False
    except ImportError:
        logger.warning("python-dotenv not installed. Using system environment variables.")
        return False


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
    - Response caching (optional)
    """
    
    PROVIDER_CLASSES = {
        LLMProvider.ANTHROPIC: AnthropicProvider,
        LLMProvider.OPENAI: OpenAIProvider,
        LLMProvider.GOOGLE: GoogleProvider,
        LLMProvider.GROK: GrokProvider,
    }
    
    def __init__(self, config: GreenlightConfig = None):
        """
        Initialize the LLM manager.
        
        Args:
            config: Greenlight configuration
        """
        self.config = config or get_config()
        self._providers: Dict[str, BaseLLMProvider] = {}
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
        max_tokens: int = None
    ) -> str:
        """
        Generate a response using the appropriate LLM.

        Automatically falls back to Grok if content is blocked by the primary provider.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            function: Function type for routing
            temperature: Override temperature
            max_tokens: Override max tokens

        Returns:
            Generated response text
        """
        # Get provider for function
        provider = self._get_provider_for_function(function)

        if not provider:
            raise LLMError("No available LLM provider")

        logger.debug(f"Using provider for {function}: {provider.config.model}")

        try:
            return await provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
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

