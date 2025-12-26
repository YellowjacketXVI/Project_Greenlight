"""
Greenlight API Clients

Unified API clients for all LLM providers.
Ported from Prometheus Director with enhancements.

Supports:
- Anthropic Claude (Opus, Sonnet, Haiku 4.5)
- Google Gemini (2.5 Flash, 3 Pro)
- xAI Grok (4, 3-Fast)
- Replicate (Seedream 4.5)
"""

from __future__ import annotations

import base64
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib import error, request

from greenlight.core.logging_config import get_logger

logger = get_logger("llm.api_clients")


# ============================================================================
#  THINKING SPINNER
# ============================================================================

class ThinkingSpinner:
    """Animated spinner that shows while waiting for API response."""

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    THINKING_MESSAGES = [
        "is thinking", "is pondering", "is contemplating", "is processing",
        "is analyzing", "is crafting response", "is working on it",
    ]

    def __init__(self, model_name: str = "AI"):
        self.model_name = model_name
        self.running = False
        self.thread = None
        self.start_time = 0
        self._message_index = 0
        self._enabled = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    def _get_elapsed_str(self) -> str:
        elapsed = time.time() - self.start_time
        if elapsed < 60:
            return f"{elapsed:.0f}s"
        return f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

    def _spin(self):
        if not self._enabled:
            return
        frame_idx = 0
        last_message_change = time.time()
        while self.running:
            if time.time() - last_message_change > 8:
                self._message_index = (self._message_index + 1) % len(self.THINKING_MESSAGES)
                last_message_change = time.time()
            spinner = self.SPINNER_FRAMES[frame_idx % len(self.SPINNER_FRAMES)]
            message = self.THINKING_MESSAGES[self._message_index]
            elapsed = self._get_elapsed_str()
            status = f"\r  {spinner} {self.model_name} {message}... [{elapsed}]"
            sys.stdout.write(status + " " * 10)
            sys.stdout.flush()
            frame_idx += 1
            time.sleep(0.1)
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()

    def start(self):
        if not self._enabled:
            return
        self.running = True
        self.start_time = time.time()
        self._message_index = 0
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
            self.thread = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


# ============================================================================
#  EXCEPTIONS
# ============================================================================

class APIError(Exception):
    """Base exception for API errors."""
    def __init__(self, message: str, status_code: int = None, response: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""
    pass


class APITimeoutError(APIError):
    """Raised when API request times out."""
    pass


class ContentRejectionError(APIError):
    """Raised when content is rejected due to policy violations."""
    pass


# Content rejection indicators (case-insensitive patterns)
CONTENT_REJECTION_PATTERNS = [
    "content policy",
    "safety filter",
    "content filter",
    "cannot generate",
    "unable to generate",
    "i cannot",
    "i'm unable",
    "violates",
    "inappropriate",
    "harmful content",
    "not allowed",
]


def is_content_rejection(text: str) -> bool:
    """Check if response text indicates content rejection."""
    if not text or len(text.strip()) < 10:
        return True  # Empty or very short responses are treated as rejections
    text_lower = text.lower()
    for pattern in CONTENT_REJECTION_PATTERNS:
        if pattern in text_lower:
            return True
    return False


# ============================================================================
#  RESPONSE TYPES
# ============================================================================

@dataclass
class TextResponse:
    """Response from text generation API."""
    text: str
    model: str
    usage: Optional[Dict] = None
    raw_response: Optional[Dict] = None


@dataclass
class ImageResponse:
    """Response from image generation API."""
    images: List[Tuple[bytes, str]]  # List of (image_data, mime_type)
    model: str
    raw_response: Optional[Dict] = None


@dataclass
class AnalysisResponse:
    """Response from visual analysis API."""
    text: str
    model: str
    parsed_json: Optional[Dict] = None
    raw_response: Optional[Dict] = None


# ============================================================================
#  BASE CLIENT
# ============================================================================

class BaseAPIClient:
    """Base class for API clients with common functionality."""

    MODEL_DISPLAY_NAME = "API"

    def __init__(self, api_key: str, timeout: int = None, show_spinner: bool = True):
        if not api_key:
            raise ValueError(f"{self.__class__.__name__} requires an API key")
        self.api_key = api_key
        self.timeout = timeout
        self.show_spinner = show_spinner
        self._last_request_time = 0.0

    def _make_request(self, url: str, body: Dict, headers: Dict,
                      method: str = "POST", spinner_name: str = None,
                      max_retries: int = 3) -> Dict:
        """Make HTTP request with error handling and spinner."""
        data = json.dumps(body).encode("utf-8")
        display_name = spinner_name or self.MODEL_DISPLAY_NAME

        for attempt in range(max_retries):
            req = request.Request(url, data=data, headers=headers, method=method)
            spinner = None
            if self.show_spinner:
                spinner = ThinkingSpinner(display_name)
                spinner.start()

            try:
                with request.urlopen(req, timeout=self.timeout) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    return result
            except error.HTTPError as e:
                msg = e.read().decode("utf-8", errors="ignore")
                if e.code >= 500 and attempt < max_retries - 1:
                    wait_time = 10 * (attempt + 1)
                    if spinner:
                        spinner.stop()
                    logger.warning(f"Server error ({e.code}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise APIError(f"HTTP {e.code}: {msg}", e.code, msg)
            except error.URLError as e:
                if "timed out" in str(e.reason).lower():
                    raise APITimeoutError(f"Request timed out: {e.reason}")
                raise APIError(f"URL error: {e.reason}")
            finally:
                if spinner:
                    spinner.stop()

    def _encode_image(self, image_path: Path) -> Tuple[str, str]:
        """Encode image file to base64 with mime type."""
        suffix = image_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp"
        }
        mime_type = mime_types.get(suffix, "image/jpeg")
        data_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return data_b64, mime_type

    def _parse_json_from_text(self, text: str) -> Optional[Dict]:
        """Parse JSON from text, handling markdown code blocks."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None



# ============================================================================
#  GEMINI CLIENT
# ============================================================================

class GeminiClient(BaseAPIClient):
    """Client for Google Gemini API."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    MODEL_DISPLAY_NAME = "Gemini"
    TEXT_MODEL = "gemini-2.5-flash"
    VISION_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str = None, timeout: int = None, show_spinner: bool = True):
        api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        super().__init__(api_key, timeout, show_spinner)

    def _get_headers(self) -> Dict:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

    def generate_text(self, prompt: str, temperature: float = 0.7,
                      max_tokens: int = 8192, model: str = None) -> TextResponse:
        """Generate text using Gemini."""
        model = model or self.TEXT_MODEL
        url = f"{self.BASE_URL}/{model}:generateContent"

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        result = self._make_request(url, body, self._get_headers())

        text = ""
        candidates = result.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                text = parts[0].get("text", "")

        return TextResponse(text=text, model=model, raw_response=result)

    def analyze_image(self, image_path: Union[Path, str], prompt: str,
                      return_json: bool = False) -> AnalysisResponse:
        """Analyze an image using Gemini vision."""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        data_b64, mime_type = self._encode_image(image_path)
        url = f"{self.BASE_URL}/{self.VISION_MODEL}:generateContent"

        body = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": data_b64}}
                ]
            }],
            "generationConfig": {
                "temperature": 0.1 if return_json else 0.7,
                "maxOutputTokens": 4096
            }
        }

        result = self._make_request(url, body, self._get_headers())

        text = ""
        candidates = result.get("candidates", [])
        if candidates:
            for part in candidates[0].get("content", {}).get("parts", []):
                if "text" in part:
                    text += part["text"]

        parsed = self._parse_json_from_text(text) if return_json else None
        return AnalysisResponse(text=text, parsed_json=parsed, model=self.VISION_MODEL, raw_response=result)


# ============================================================================
#  ANTHROPIC CLIENT
# ============================================================================

class AnthropicClient(BaseAPIClient):
    """Client for Anthropic Claude API."""

    BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
    MODEL_DISPLAY_NAME = "Claude"

    AVAILABLE_MODELS = {
        "claude-opus": "claude-opus-4-5-20251101",
        "claude-sonnet": "claude-sonnet-4-5-20250929",
        "claude-haiku": "claude-haiku-4-5-20251001",
    }

    def __init__(self, api_key: str = None, timeout: int = None, show_spinner: bool = True):
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        super().__init__(api_key, timeout, show_spinner)

    def _get_headers(self) -> Dict:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

    def generate_text(self, prompt: str, system: str = None,
                      max_tokens: int = 8192, model: str = None) -> TextResponse:
        """Generate text using Claude."""
        model = model or self.DEFAULT_MODEL
        url = f"{self.BASE_URL}/messages"

        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }

        if system:
            body["system"] = system

        result = self._make_request(url, body, self._get_headers())

        text = ""
        content = result.get("content", [])
        if content:
            text = content[0].get("text", "")

        usage = result.get("usage", {})
        return TextResponse(text=text, model=model, usage=usage, raw_response=result)

    def generate_with_conversation(self, messages: List[Dict], system: str = None,
                                   max_tokens: int = 8192, model: str = None) -> TextResponse:
        """Generate text with full conversation history."""
        model = model or self.DEFAULT_MODEL
        url = f"{self.BASE_URL}/messages"

        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages
        }

        if system:
            body["system"] = system

        result = self._make_request(url, body, self._get_headers())

        text = ""
        content = result.get("content", [])
        if content:
            text = content[0].get("text", "")

        return TextResponse(text=text, model=model, usage=result.get("usage"), raw_response=result)



# ============================================================================
#  GROK CLIENT (xAI)
# ============================================================================

class GrokClient(BaseAPIClient):
    """Client for xAI Grok API."""

    BASE_URL = "https://api.x.ai/v1"
    DEFAULT_MODEL = os.getenv("GROK_MODEL", "grok-4")
    MODEL_DISPLAY_NAME = "Grok"

    AVAILABLE_MODELS = {
        "grok-4": "grok-4",
        "grok-3-fast": "grok-3-fast",
    }

    def __init__(self, api_key: str = None, timeout: int = None, show_spinner: bool = True):
        api_key = api_key or os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
        super().__init__(api_key, timeout, show_spinner)

    def _get_headers(self) -> Dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "ProjectGreenlight/2.0",
            "Accept": "application/json",
        }

    def generate_text(self, prompt: str, system: Optional[str] = None,
                      max_tokens: int = 8192, temperature: float = 0.7,
                      model: str = None) -> TextResponse:
        """Generate text using Grok via chat completions."""
        model = model or self.DEFAULT_MODEL
        url = f"{self.BASE_URL}/chat/completions"

        messages: List[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        result = self._make_request(url, body, self._get_headers(), spinner_name=self.MODEL_DISPLAY_NAME)

        text = ""
        choices = result.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "".join(part.get("text", "") for part in content)

        usage = result.get("usage", {})
        return TextResponse(text=text, model=model, usage=usage, raw_response=result)


# ============================================================================
#  REPLICATE CLIENT (Seedream 4.5)
# ============================================================================

class ReplicateClient(BaseAPIClient):
    """Client for Replicate API (Seedream 4.5 image generation)."""

    BASE_URL = "https://api.replicate.com/v1"
    MODEL_ID = "bytedance/seedream-4.5"
    MODEL_DISPLAY_NAME = "Seedream"

    def __init__(self, api_key: str = None, timeout: int = None, show_spinner: bool = True):
        api_key = api_key or os.getenv("REPLICATE_API_TOKEN")
        super().__init__(api_key, timeout, show_spinner)

    def _get_headers(self, wait: bool = True) -> Dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        if wait:
            headers["Prefer"] = "wait"
        return headers

    def generate_image(self, prompt: str, ref_images: List[Dict] = None,
                       aspect_ratio: str = "16:9", negative_prompt: str = None) -> ImageResponse:
        """Generate image using Seedream 4.5.

        Args:
            prompt: The image generation prompt
            ref_images: List of reference images with data and mime_type
            aspect_ratio: Target aspect ratio (e.g., "16:9")
            negative_prompt: Elements to avoid in the generated image
        """
        image_input = []

        # Add reference images
        if ref_images:
            for img in ref_images:
                mime = img.get("mime_type", "image/jpeg")
                data = img.get("data", "")
                image_input.append(f"data:{mime};base64,{data}")

        input_params = {
            "prompt": prompt,
            "size": "2K",
            "aspect_ratio": "match_input_image" if image_input else aspect_ratio
        }

        if image_input:
            input_params["image_input"] = image_input

        # Add negative prompt if provided
        if negative_prompt:
            input_params["negative_prompt"] = negative_prompt

        url = f"{self.BASE_URL}/models/{self.MODEL_ID}/predictions"
        body = {"input": input_params}

        result = self._make_request(url, body, self._get_headers(wait=True))

        # Handle async polling if needed
        if result.get("status") in ("starting", "processing"):
            result = self._poll_for_completion(result)

        # Extract images from output URLs
        images = []
        for img_url in result.get("output", []):
            try:
                img_data = self._download_image(img_url)
                images.append((img_data, "image/png"))
            except Exception as e:
                logger.warning(f"Failed to download image: {e}")

        return ImageResponse(images=images, model=self.MODEL_ID, raw_response=result)

    def _poll_for_completion(self, initial_result: Dict, max_wait: int = 300) -> Dict:
        """Poll for async prediction completion."""
        poll_url = initial_result.get("urls", {}).get("get")
        if not poll_url:
            poll_url = f"{self.BASE_URL}/predictions/{initial_result['id']}"

        headers = {"Authorization": f"Bearer {self.api_key}"}
        start_time = time.time()

        while time.time() - start_time < max_wait:
            req = request.Request(poll_url, headers=headers)
            with request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            status = result.get("status", "")
            if status == "succeeded":
                return result
            elif status in ("failed", "canceled"):
                raise APIError(f"Prediction {status}: {result.get('error', 'Unknown')}")

            time.sleep(2)

        raise APITimeoutError(f"Prediction timed out after {max_wait}s")

    def _download_image(self, url: str) -> bytes:
        """Download image from URL."""
        req = request.Request(url)
        with request.urlopen(req, timeout=60) as resp:
            return resp.read()


# ============================================================================
#  UNIFIED IMAGE GENERATOR
# ============================================================================

class UnifiedImageGenerator:
    """Unified interface for image generation across multiple backends."""

    def __init__(self, primary: str = "seedream", fallback: str = "gemini"):
        """Initialize with primary and fallback backends.

        Args:
            primary: Primary backend ("seedream" or "gemini")
            fallback: Fallback backend if primary fails
        """
        self.primary = primary
        self.fallback = fallback
        self._clients: Dict[str, BaseAPIClient] = {}

    def _get_client(self, backend: str) -> BaseAPIClient:
        """Get or create client for backend."""
        if backend not in self._clients:
            if backend == "seedream":
                self._clients[backend] = ReplicateClient()
            elif backend == "gemini":
                self._clients[backend] = GeminiClient()
            else:
                raise ValueError(f"Unknown backend: {backend}")
        return self._clients[backend]

    def generate(self, prompt: str, ref_images: List[Dict] = None,
                 aspect_ratio: str = "16:9", use_fallback: bool = True) -> ImageResponse:
        """Generate image using primary backend with optional fallback.

        Args:
            prompt: Image generation prompt
            ref_images: Optional reference images for consistency
            aspect_ratio: Aspect ratio (e.g., "16:9", "1:1")
            use_fallback: Whether to try fallback on primary failure

        Returns:
            ImageResponse with generated images
        """
        try:
            client = self._get_client(self.primary)
            if isinstance(client, ReplicateClient):
                return client.generate_image(prompt, ref_images, aspect_ratio)
            else:
                # Gemini image generation would go here
                raise NotImplementedError("Gemini image generation not yet implemented")
        except Exception as e:
            if use_fallback and self.fallback:
                logger.warning(f"Primary backend failed: {e}. Trying fallback...")
                try:
                    client = self._get_client(self.fallback)
                    if isinstance(client, ReplicateClient):
                        return client.generate_image(prompt, ref_images, aspect_ratio)
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {fallback_error}")
                    raise
            raise


# ============================================================================
#  CONVENIENCE FUNCTIONS
# ============================================================================

def load_env():
    """Load environment variables from .env file."""
    from greenlight.core.env_loader import ensure_env_loaded
    return ensure_env_loaded()


def get_available_providers() -> Dict[str, bool]:
    """Check which API providers are available."""
    return {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")),
        "google": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "xai": bool(os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")),
        "replicate": bool(os.getenv("REPLICATE_API_TOKEN")),
    }


def get_default_client(provider: str = None) -> BaseAPIClient:
    """Get a default client for the specified or first available provider.

    Args:
        provider: Optional provider name ("anthropic", "google", "xai", "replicate")

    Returns:
        Configured API client
    """
    load_env()
    available = get_available_providers()

    if provider:
        if not available.get(provider):
            raise ValueError(f"Provider {provider} not configured")
        if provider == "anthropic":
            return AnthropicClient()
        elif provider == "google":
            return GeminiClient()
        elif provider == "xai":
            return GrokClient()
        elif provider == "replicate":
            return ReplicateClient()

    # Return first available
    for prov, is_available in available.items():
        if is_available:
            return get_default_client(prov)

    raise ValueError("No API providers configured. Please set API keys in .env file.")


# ============================================================================
#  GROK 4 CONTENT REJECTION FALLBACK
# ============================================================================

def generate_text_with_fallback(
    prompt: str,
    system: str = None,
    max_tokens: int = 8192,
    temperature: float = 0.7,
    model: str = None,
    primary_client: BaseAPIClient = None,
    fallback_to_grok: bool = True
) -> TextResponse:
    """
    Generate text with automatic fallback to Grok 4 on content rejection.

    This function wraps LLM text generation and automatically falls back to
    Grok 4 when the primary model returns empty results, content policy
    violations, or rejection errors.

    Args:
        prompt: The prompt to send
        system: Optional system prompt
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        model: Model to use (if primary_client supports it)
        primary_client: Primary API client to use (defaults to AnthropicClient)
        fallback_to_grok: Whether to fall back to Grok 4 on rejection

    Returns:
        TextResponse from either primary or fallback model
    """
    # Use Anthropic as default primary client
    if primary_client is None:
        primary_client = AnthropicClient()

    # Try primary model first
    try:
        if isinstance(primary_client, AnthropicClient):
            response = primary_client.generate_text(
                prompt=prompt,
                system=system,
                max_tokens=max_tokens,
                model=model
            )
        elif isinstance(primary_client, GeminiClient):
            # Gemini doesn't support system prompt separately
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            response = primary_client.generate_text(
                prompt=full_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                model=model
            )
        elif isinstance(primary_client, GrokClient):
            response = primary_client.generate_text(
                prompt=prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                model=model
            )
        else:
            # Generic fallback
            response = primary_client.generate_text(prompt=prompt, max_tokens=max_tokens)

        # Check for content rejection
        if not is_content_rejection(response.text):
            return response

        logger.warning(f"Content rejection detected from {response.model}, falling back to Grok 4")

    except (APIError, ContentRejectionError) as e:
        logger.warning(f"Primary model error: {e}, falling back to Grok 4")

    # Fall back to Grok 4 if enabled
    if fallback_to_grok:
        try:
            grok_client = GrokClient()
            grok_response = grok_client.generate_text(
                prompt=prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                model="grok-4"
            )
            logger.info("Grok 4 fallback successful")
            return grok_response
        except Exception as e:
            logger.error(f"Grok 4 fallback also failed: {e}")
            raise ContentRejectionError(f"Both primary and Grok 4 fallback failed: {e}")

    # If fallback disabled, raise the original error
    raise ContentRejectionError("Content rejected and fallback disabled")
