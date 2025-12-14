"""
Greenlight Function Router

Routes LLM calls to appropriate providers based on function type.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

from greenlight.core.constants import LLMFunction, LLMProvider
from greenlight.core.config import GreenlightConfig, get_config
from greenlight.core.logging_config import get_logger
from .llm_config import LLMManager

logger = get_logger("llm.router")


@dataclass
class RoutingStats:
    """Statistics for a routing path."""
    function: LLMFunction
    provider: str
    call_count: int = 0
    total_tokens: int = 0
    total_time: float = 0.0
    error_count: int = 0
    last_used: Optional[datetime] = None
    
    @property
    def avg_time(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_time / self.call_count
    
    @property
    def error_rate(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.error_count / self.call_count


class FunctionRouter:
    """
    Routes LLM function calls to appropriate providers.
    
    Features:
    - Function-based routing
    - Usage statistics tracking
    - Dynamic provider selection
    - Cost optimization hints
    """
    
    def __init__(
        self,
        llm_manager: LLMManager = None,
        config: GreenlightConfig = None
    ):
        """
        Initialize the function router.
        
        Args:
            llm_manager: LLM manager instance
            config: Greenlight configuration
        """
        self.config = config or get_config()
        self.llm_manager = llm_manager or LLMManager(self.config)
        self._stats: Dict[LLMFunction, RoutingStats] = {}
        self._initialize_stats()
    
    def _initialize_stats(self) -> None:
        """Initialize statistics for all functions."""
        for function in LLMFunction:
            mapping = self.config.function_mappings.get(function)
            provider = mapping.primary_config.provider.value if mapping else "unknown"
            self._stats[function] = RoutingStats(
                function=function,
                provider=provider
            )
    
    async def route(
        self,
        function: LLMFunction,
        prompt: str,
        system_prompt: str = "",
        **kwargs
    ) -> str:
        """
        Route a function call to the appropriate LLM.

        Args:
            function: Function type
            prompt: User prompt
            system_prompt: System prompt
            **kwargs: Additional parameters

        Returns:
            LLM response
        """
        import time
        start_time = time.time()

        stats = self._stats.get(function)

        # Log the request
        logger.info(f"🔄 Routing {function.value} to LLM...")
        logger.debug(f"Prompt preview: {prompt[:200]}...")

        try:
            response = await self.llm_manager.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                function=function,
                **kwargs
            )

            elapsed = time.time() - start_time

            # Update stats
            if stats:
                stats.call_count += 1
                stats.total_time += elapsed
                stats.last_used = datetime.now()

            logger.info(f"✓ {function.value} completed in {elapsed:.2f}s ({len(response)} chars)")
            logger.debug(f"Response preview: {response[:300]}...")

            return response

        except Exception as e:
            if stats:
                stats.error_count += 1
            logger.error(f"❌ {function.value} failed: {e}")
            raise
    
    def get_stats(self, function: LLMFunction = None) -> Dict[str, Any]:
        """
        Get routing statistics.
        
        Args:
            function: Specific function, or None for all
            
        Returns:
            Statistics dictionary
        """
        if function:
            stats = self._stats.get(function)
            if stats:
                return {
                    'function': stats.function.value,
                    'provider': stats.provider,
                    'call_count': stats.call_count,
                    'avg_time': stats.avg_time,
                    'error_rate': stats.error_rate
                }
            return {}
        
        return {
            func.value: {
                'provider': s.provider,
                'call_count': s.call_count,
                'avg_time': s.avg_time,
                'error_rate': s.error_rate
            }
            for func, s in self._stats.items()
        }
    
    def get_recommended_provider(
        self,
        function: LLMFunction
    ) -> str:
        """
        Get recommended provider based on performance.
        
        Args:
            function: Function type
            
        Returns:
            Recommended provider name
        """
        mapping = self.config.function_mappings.get(function)
        if mapping:
            return mapping.primary_config.provider.value
        return "unknown"
    
    def estimate_cost(
        self,
        function: LLMFunction,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Estimate cost for a function call.
        
        Args:
            function: Function type
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens
            
        Returns:
            Estimated cost in USD
        """
        # Simplified cost estimation
        # Real implementation would use actual provider pricing
        cost_per_1k = {
            LLMProvider.ANTHROPIC: 0.015,
            LLMProvider.OPENAI: 0.01,
            LLMProvider.GOOGLE: 0.0005,
        }
        
        mapping = self.config.function_mappings.get(function)
        if mapping:
            provider = mapping.primary_config.provider
            rate = cost_per_1k.get(provider, 0.01)
            total_tokens = input_tokens + output_tokens
            return (total_tokens / 1000) * rate
        
        return 0.0

