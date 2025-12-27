"""
Retry utilities with exponential backoff.

Provides decorators and utilities for retrying failed operations,
particularly useful for external API calls (LLM providers, image generation).
"""

import asyncio
import functools
import random
from typing import Callable, TypeVar, Any, Optional, Tuple, Type
from dataclasses import dataclass

from greenlight.core.logging_config import get_logger

logger = get_logger("core.retry")

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Multiplier for exponential backoff
    jitter: bool = True  # Add random jitter to prevent thundering herd
    jitter_range: Tuple[float, float] = (0.5, 1.5)  # Jitter multiplier range
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        Exception,  # Default: retry all exceptions
    )


# Default configuration
DEFAULT_RETRY_CONFIG = RetryConfig()


def calculate_delay(
    attempt: int,
    config: RetryConfig
) -> float:
    """
    Calculate delay before next retry attempt.

    Uses exponential backoff with optional jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds before next attempt
    """
    # Exponential backoff: base_delay * (exponential_base ^ attempt)
    delay = config.base_delay * (config.exponential_base ** attempt)

    # Cap at maximum delay
    delay = min(delay, config.max_delay)

    # Add jitter if enabled
    if config.jitter:
        jitter_multiplier = random.uniform(*config.jitter_range)
        delay *= jitter_multiplier

    return delay


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> Callable:
    """
    Decorator for synchronous functions with retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Multiplier for exponential backoff
        jitter: Whether to add random jitter
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Optional callback called on each retry with (exception, attempt)

    Returns:
        Decorated function with retry behavior

    Example:
        @retry(max_retries=3, base_delay=1.0)
        def call_api():
            return requests.get("https://api.example.com")
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )

                        if on_retry:
                            on_retry(e, attempt)

                        import time
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_retries + 1} attempts failed. "
                            f"Last error: {e}"
                        )

            # Raise the last exception if all retries failed
            if last_exception:
                raise last_exception

            # This shouldn't happen, but just in case
            raise RuntimeError("Retry logic failed unexpectedly")

        return wrapper
    return decorator


def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> Callable:
    """
    Decorator for async functions with retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Multiplier for exponential backoff
        jitter: Whether to add random jitter
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Optional callback called on each retry with (exception, attempt)

    Returns:
        Decorated async function with retry behavior

    Example:
        @async_retry(max_retries=3, base_delay=1.0)
        async def call_llm():
            return await client.generate(prompt)
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )

                        if on_retry:
                            on_retry(e, attempt)

                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_retries + 1} attempts failed. "
                            f"Last error: {e}"
                        )

            # Raise the last exception if all retries failed
            if last_exception:
                raise last_exception

            # This shouldn't happen, but just in case
            raise RuntimeError("Retry logic failed unexpectedly")

        return wrapper
    return decorator


async def retry_async_call(
    func: Callable[..., T],
    *args: Any,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    **kwargs: Any
) -> T:
    """
    Retry an async function call with exponential backoff.

    This is a functional alternative to the decorator approach,
    useful when you can't modify the function definition.

    Args:
        func: Async function to call
        *args: Positional arguments for the function
        config: Retry configuration (uses defaults if not provided)
        on_retry: Optional callback called on each retry
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the function call

    Example:
        result = await retry_async_call(
            client.generate,
            prompt,
            config=RetryConfig(max_retries=5)
        )
    """
    config = config or DEFAULT_RETRY_CONFIG
    last_exception: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e

            if attempt < config.max_retries:
                delay = calculate_delay(attempt, config)
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )

                if on_retry:
                    on_retry(e, attempt)

                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {config.max_retries + 1} attempts failed. "
                    f"Last error: {e}"
                )

    if last_exception:
        raise last_exception

    raise RuntimeError("Retry logic failed unexpectedly")


# Common retry configurations for different use cases
LLM_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)

IMAGE_GENERATION_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    base_delay=5.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True
)

QUICK_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    base_delay=0.5,
    max_delay=5.0,
    exponential_base=2.0,
    jitter=True
)
