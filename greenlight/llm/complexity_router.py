"""
Greenlight Task Complexity Router

Routes LLM calls to optimal models based on task complexity.
Reduces costs by using cheaper models for simple tasks.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Any, Callable

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger

logger = get_logger("llm.complexity_router")


class TaskComplexity(Enum):
    """Task complexity levels for model routing."""
    LOW = "low"           # Voting, validation, simple extraction
    MEDIUM = "medium"     # Parsing, analysis, frame description
    HIGH = "high"         # Generation, creative writing, arcs


@dataclass
class ModelTier:
    """Configuration for a model tier."""
    anthropic: str       # Claude model for this tier
    gemini: str          # Gemini model for this tier
    grok: str            # Grok model for this tier
    cost_multiplier: float = 1.0  # Relative cost


# Model tiers mapped to complexity levels
MODEL_TIERS: Dict[TaskComplexity, ModelTier] = {
    TaskComplexity.LOW: ModelTier(
        anthropic="claude-haiku-4-5-20251001",
        gemini="gemini-2.5-flash",
        grok="grok-4-fast",  # Grok 4 Fast for light tasks
        cost_multiplier=1.0
    ),
    TaskComplexity.MEDIUM: ModelTier(
        anthropic="claude-sonnet-4-5-20250929",
        gemini="gemini-2.5-flash",
        grok="grok-4-fast",  # Grok 4 Fast for medium tasks
        cost_multiplier=10.0
    ),
    TaskComplexity.HIGH: ModelTier(
        anthropic="claude-opus-4-5-20251101",
        gemini="gemini-3-pro",
        grok="grok-4",  # Full Grok 4 for complex tasks
        cost_multiplier=75.0
    ),
}


# Function to complexity mapping
FUNCTION_COMPLEXITY: Dict[LLMFunction, TaskComplexity] = {
    # LOW complexity - simple tasks
    LLMFunction.TAG_VALIDATION: TaskComplexity.LOW,
    LLMFunction.QUICK_RESPONSE: TaskComplexity.LOW,

    # MEDIUM complexity - analysis and parsing
    LLMFunction.STORY_ANALYSIS: TaskComplexity.MEDIUM,
    LLMFunction.CONTINUITY: TaskComplexity.MEDIUM,
    LLMFunction.DIRECTOR: TaskComplexity.MEDIUM,
    LLMFunction.ASSISTANT_QUERY: TaskComplexity.MEDIUM,
    LLMFunction.ASSISTANT_COMMAND: TaskComplexity.MEDIUM,

    # HIGH complexity - generation
    LLMFunction.STORY_GENERATION: TaskComplexity.HIGH,
    LLMFunction.BEAT_WRITING: TaskComplexity.HIGH,
    LLMFunction.RESEARCH: TaskComplexity.HIGH,
    LLMFunction.ASSISTANT_REASONING: TaskComplexity.HIGH,
    LLMFunction.ASSISTANT: TaskComplexity.HIGH,
}


class ComplexityRouter:
    """
    Routes tasks to appropriate models based on complexity.

    Features:
    - Automatic complexity detection from function type
    - Manual complexity override for fine-grained control
    - Cost tracking and optimization hints
    - Provider preference with fallback
    """

    def __init__(
        self,
        preferred_provider: str = "anthropic",
        default_complexity: TaskComplexity = TaskComplexity.MEDIUM
    ):
        """
        Initialize the complexity router.

        Args:
            preferred_provider: Preferred provider ('anthropic', 'gemini', 'grok')
            default_complexity: Default complexity for unmapped functions
        """
        self.preferred_provider = preferred_provider.lower()
        self.default_complexity = default_complexity
        self._call_stats: Dict[TaskComplexity, int] = {
            TaskComplexity.LOW: 0,
            TaskComplexity.MEDIUM: 0,
            TaskComplexity.HIGH: 0
        }
        self._cost_savings: float = 0.0

    def get_complexity(
        self,
        function: Optional[LLMFunction] = None,
        override: Optional[TaskComplexity] = None
    ) -> TaskComplexity:
        """
        Get task complexity for routing.

        Args:
            function: LLM function type
            override: Manual complexity override

        Returns:
            TaskComplexity level
        """
        if override is not None:
            return override

        if function is not None:
            return FUNCTION_COMPLEXITY.get(function, self.default_complexity)

        return self.default_complexity

    def get_model(
        self,
        function: Optional[LLMFunction] = None,
        provider: Optional[str] = None,
        complexity: Optional[TaskComplexity] = None
    ) -> str:
        """
        Get the optimal model for a task.

        Args:
            function: LLM function type (for auto complexity detection)
            provider: Provider preference override
            complexity: Manual complexity override

        Returns:
            Model identifier string
        """
        # Determine complexity
        task_complexity = self.get_complexity(function, complexity)

        # Get model tier
        tier = MODEL_TIERS[task_complexity]

        # Select provider
        provider = (provider or self.preferred_provider).lower()

        # Get model for provider
        if provider in ('anthropic', 'claude'):
            model = tier.anthropic
        elif provider in ('gemini', 'google'):
            model = tier.gemini
        elif provider in ('grok', 'xai'):
            model = tier.grok
        else:
            # Default to anthropic
            model = tier.anthropic

        # Track stats
        self._call_stats[task_complexity] += 1

        # Calculate savings if we downgraded from HIGH
        if task_complexity != TaskComplexity.HIGH:
            high_cost = MODEL_TIERS[TaskComplexity.HIGH].cost_multiplier
            actual_cost = tier.cost_multiplier
            self._cost_savings += (high_cost - actual_cost)

        logger.debug(
            f"Routed {function.value if function else 'unknown'} -> "
            f"{task_complexity.value} complexity -> {model}"
        )

        return model

    def get_recommended_model_for_task(
        self,
        task_type: str,
        provider: Optional[str] = None
    ) -> str:
        """
        Get recommended model for common task types.

        Args:
            task_type: Description of task type
            provider: Provider preference

        Returns:
            Model identifier
        """
        # Map common task descriptions to complexity
        low_tasks = {
            'voting', 'consensus', 'validation', 'extraction',
            'tag', 'count', 'simple', 'quick', 'check'
        }
        high_tasks = {
            'generation', 'creative', 'writing', 'story', 'arc',
            'character', 'prose', 'novel'
        }

        task_lower = task_type.lower()

        if any(t in task_lower for t in low_tasks):
            complexity = TaskComplexity.LOW
        elif any(t in task_lower for t in high_tasks):
            complexity = TaskComplexity.HIGH
        else:
            complexity = TaskComplexity.MEDIUM

        return self.get_model(complexity=complexity, provider=provider)

    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        total_calls = sum(self._call_stats.values())

        return {
            'calls_by_complexity': {
                k.value: v for k, v in self._call_stats.items()
            },
            'total_calls': total_calls,
            'estimated_cost_savings': f"${self._cost_savings:.2f}",
            'low_complexity_ratio': (
                self._call_stats[TaskComplexity.LOW] / total_calls
                if total_calls > 0 else 0.0
            )
        }

    def suggest_optimization(
        self,
        function: LLMFunction,
        current_model: str
    ) -> Optional[str]:
        """
        Suggest a more cost-efficient model if available.

        Args:
            function: Current function type
            current_model: Currently configured model

        Returns:
            Suggested model or None if already optimal
        """
        optimal = self.get_model(function)

        # Check if current is more expensive than needed
        current_tier = None
        optimal_tier = None

        for tier in MODEL_TIERS.values():
            if current_model in (tier.anthropic, tier.gemini, tier.grok):
                current_tier = tier
            if optimal in (tier.anthropic, tier.gemini, tier.grok):
                optimal_tier = tier

        if current_tier and optimal_tier:
            if current_tier.cost_multiplier > optimal_tier.cost_multiplier:
                return optimal

        return None


# Singleton instance
_router: Optional[ComplexityRouter] = None


def get_complexity_router(**kwargs) -> ComplexityRouter:
    """Get or create the global complexity router."""
    global _router
    if _router is None:
        _router = ComplexityRouter(**kwargs)
    return _router


def get_optimal_model(
    function: Optional[LLMFunction] = None,
    provider: str = "anthropic",
    complexity: Optional[TaskComplexity] = None
) -> str:
    """
    Convenience function to get optimal model for a task.

    Args:
        function: LLM function type
        provider: Preferred provider
        complexity: Manual complexity override

    Returns:
        Model identifier string
    """
    return get_complexity_router().get_model(function, provider, complexity)
