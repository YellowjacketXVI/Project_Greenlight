"""
Greenlight Concurrency Manager

Configurable semaphore management for pipeline phases.
Optimizes concurrency based on task complexity and model cost.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Any
from contextlib import asynccontextmanager

from greenlight.core.logging_config import get_logger

logger = get_logger("pipelines.concurrency")


class PipelinePhase(Enum):
    """Pipeline execution phases with different concurrency needs."""
    # Story Pipeline phases
    STORY_ARCHITECTURE = "story_architecture"     # Heavy Opus calls - low concurrency
    SCENE_GENERATION = "scene_generation"         # Heavy generation - low concurrency
    CONSENSUS_VOTING = "consensus_voting"         # Light Haiku calls - high concurrency
    QUALITY_ASSURANCE = "quality_assurance"       # Mixed - medium concurrency
    TAG_EXTRACTION = "tag_extraction"             # Light - high concurrency

    # Director Pipeline phases
    FRAME_COUNTING = "frame_counting"             # Light consensus - high concurrency
    FRAME_MARKING = "frame_marking"               # Medium - medium concurrency
    FRAME_PROMPTS = "frame_prompts"               # Medium Sonnet - medium concurrency
    FRAME_VALIDATION = "frame_validation"         # Light - high concurrency

    # Reference Pipeline phases
    REFERENCE_GENERATION = "reference_generation" # Image gen - low (rate limits)
    REFERENCE_ANALYSIS = "reference_analysis"     # Vision - medium concurrency

    # Generic phases
    LIGHT_TASK = "light_task"                     # Haiku/Flash - 8 concurrent
    MEDIUM_TASK = "medium_task"                   # Sonnet - 4 concurrent
    HEAVY_TASK = "heavy_task"                     # Opus - 2 concurrent
    DEFAULT = "default"                           # Fallback - 5 concurrent


@dataclass
class PhaseConfig:
    """Configuration for a pipeline phase."""
    max_concurrent: int
    description: str = ""
    model_tier: str = "medium"  # low, medium, high (complexity)


# Default phase configurations
DEFAULT_PHASE_CONFIGS: Dict[PipelinePhase, PhaseConfig] = {
    # Story Pipeline - Heavy operations need low concurrency
    PipelinePhase.STORY_ARCHITECTURE: PhaseConfig(
        max_concurrent=2,
        description="Plot and character architecture (Opus)",
        model_tier="high"
    ),
    PipelinePhase.SCENE_GENERATION: PhaseConfig(
        max_concurrent=2,
        description="Scene prose generation (Opus)",
        model_tier="high"
    ),
    PipelinePhase.CONSENSUS_VOTING: PhaseConfig(
        max_concurrent=10,
        description="10-agent tag consensus (Haiku)",
        model_tier="low"
    ),
    PipelinePhase.QUALITY_ASSURANCE: PhaseConfig(
        max_concurrent=5,
        description="Quality pattern agents (Sonnet)",
        model_tier="medium"
    ),
    PipelinePhase.TAG_EXTRACTION: PhaseConfig(
        max_concurrent=8,
        description="Tag extraction and validation (Haiku)",
        model_tier="low"
    ),

    # Director Pipeline
    PipelinePhase.FRAME_COUNTING: PhaseConfig(
        max_concurrent=8,
        description="Frame count consensus voting (Haiku)",
        model_tier="low"
    ),
    PipelinePhase.FRAME_MARKING: PhaseConfig(
        max_concurrent=4,
        description="Frame boundary marking (Sonnet)",
        model_tier="medium"
    ),
    PipelinePhase.FRAME_PROMPTS: PhaseConfig(
        max_concurrent=4,
        description="Frame prompt generation (Sonnet)",
        model_tier="medium"
    ),
    PipelinePhase.FRAME_VALIDATION: PhaseConfig(
        max_concurrent=6,
        description="Frame validation (Haiku)",
        model_tier="low"
    ),

    # Reference Pipeline
    PipelinePhase.REFERENCE_GENERATION: PhaseConfig(
        max_concurrent=2,
        description="Image generation (Replicate rate limits)",
        model_tier="image"
    ),
    PipelinePhase.REFERENCE_ANALYSIS: PhaseConfig(
        max_concurrent=4,
        description="Vision analysis (Gemini)",
        model_tier="medium"
    ),

    # Generic phases
    PipelinePhase.LIGHT_TASK: PhaseConfig(
        max_concurrent=8,
        description="Light tasks (Haiku/Flash)",
        model_tier="low"
    ),
    PipelinePhase.MEDIUM_TASK: PhaseConfig(
        max_concurrent=4,
        description="Medium tasks (Sonnet)",
        model_tier="medium"
    ),
    PipelinePhase.HEAVY_TASK: PhaseConfig(
        max_concurrent=2,
        description="Heavy tasks (Opus)",
        model_tier="high"
    ),
    PipelinePhase.DEFAULT: PhaseConfig(
        max_concurrent=5,
        description="Default fallback",
        model_tier="medium"
    ),
}


class ConcurrencyManager:
    """
    Manages concurrency limits for different pipeline phases.

    Features:
    - Per-phase semaphore configuration
    - Dynamic limit adjustment
    - Usage statistics
    - Automatic model tier detection
    """

    _instance: Optional['ConcurrencyManager'] = None

    @classmethod
    def get_instance(cls) -> 'ConcurrencyManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def __init__(
        self,
        custom_configs: Dict[PipelinePhase, PhaseConfig] = None
    ):
        """
        Initialize the concurrency manager.

        Args:
            custom_configs: Override default phase configurations
        """
        self._configs = {**DEFAULT_PHASE_CONFIGS}
        if custom_configs:
            self._configs.update(custom_configs)

        self._semaphores: Dict[PipelinePhase, asyncio.Semaphore] = {}
        self._active_counts: Dict[PipelinePhase, int] = {}
        self._total_counts: Dict[PipelinePhase, int] = {}
        self._wait_times: Dict[PipelinePhase, float] = {}

    def get_semaphore(self, phase: PipelinePhase) -> asyncio.Semaphore:
        """
        Get semaphore for a pipeline phase.

        Args:
            phase: Pipeline phase

        Returns:
            Configured semaphore for the phase
        """
        if phase not in self._semaphores:
            config = self._configs.get(phase, self._configs[PipelinePhase.DEFAULT])
            self._semaphores[phase] = asyncio.Semaphore(config.max_concurrent)
            self._active_counts[phase] = 0
            self._total_counts[phase] = 0
            self._wait_times[phase] = 0.0

            logger.debug(
                f"Created semaphore for {phase.value}: "
                f"max_concurrent={config.max_concurrent}"
            )

        return self._semaphores[phase]

    @asynccontextmanager
    async def acquire(self, phase: PipelinePhase):
        """
        Acquire a slot for the given phase.

        Usage:
            async with manager.acquire(PipelinePhase.FRAME_PROMPTS):
                await do_work()

        Args:
            phase: Pipeline phase
        """
        import time
        start_wait = time.time()

        semaphore = self.get_semaphore(phase)

        async with semaphore:
            wait_time = time.time() - start_wait

            # Update stats
            self._active_counts[phase] = self._active_counts.get(phase, 0) + 1
            self._total_counts[phase] = self._total_counts.get(phase, 0) + 1
            self._wait_times[phase] = self._wait_times.get(phase, 0.0) + wait_time

            if wait_time > 0.1:  # Only log significant waits
                logger.debug(
                    f"Acquired {phase.value} slot after {wait_time:.2f}s wait "
                    f"(active: {self._active_counts[phase]})"
                )

            try:
                yield
            finally:
                self._active_counts[phase] -= 1

    def get_limit(self, phase: PipelinePhase) -> int:
        """Get current concurrency limit for a phase."""
        config = self._configs.get(phase, self._configs[PipelinePhase.DEFAULT])
        return config.max_concurrent

    def set_limit(self, phase: PipelinePhase, limit: int) -> None:
        """
        Dynamically adjust concurrency limit for a phase.

        Note: This creates a new semaphore, so only call between batches.

        Args:
            phase: Pipeline phase
            limit: New concurrency limit
        """
        config = self._configs.get(phase, PhaseConfig(limit, "Custom"))
        self._configs[phase] = PhaseConfig(
            max_concurrent=limit,
            description=config.description,
            model_tier=config.model_tier
        )

        # Reset semaphore
        if phase in self._semaphores:
            del self._semaphores[phase]

        logger.info(f"Updated {phase.value} concurrency limit to {limit}")

    def get_active_count(self, phase: PipelinePhase) -> int:
        """Get current active task count for a phase."""
        return self._active_counts.get(phase, 0)

    def get_stats(self) -> Dict[str, Any]:
        """Get concurrency statistics."""
        stats = {}
        for phase in PipelinePhase:
            config = self._configs.get(phase)
            if config:
                total = self._total_counts.get(phase, 0)
                wait = self._wait_times.get(phase, 0.0)
                stats[phase.value] = {
                    "max_concurrent": config.max_concurrent,
                    "model_tier": config.model_tier,
                    "active": self._active_counts.get(phase, 0),
                    "total_acquisitions": total,
                    "avg_wait_time": f"{(wait / total):.3f}s" if total > 0 else "0s"
                }
        return stats

    def get_recommended_limit(self, model_tier: str) -> int:
        """
        Get recommended concurrency limit based on model tier.

        Args:
            model_tier: 'low' (Haiku), 'medium' (Sonnet), 'high' (Opus)

        Returns:
            Recommended concurrency limit
        """
        recommendations = {
            "low": 8,      # Haiku/Flash - cheap, fast
            "medium": 4,   # Sonnet - balanced
            "high": 2,     # Opus - expensive, slow
            "image": 2,    # Image gen - rate limited
        }
        return recommendations.get(model_tier, 5)


# Convenience functions
def get_concurrency_manager() -> ConcurrencyManager:
    """Get the global concurrency manager."""
    return ConcurrencyManager.get_instance()


@asynccontextmanager
async def with_phase_limit(phase: PipelinePhase):
    """
    Convenience context manager for phase-limited execution.

    Usage:
        async with with_phase_limit(PipelinePhase.FRAME_PROMPTS):
            await generate_prompt()
    """
    manager = get_concurrency_manager()
    async with manager.acquire(phase):
        yield


def get_phase_limit(phase: PipelinePhase) -> int:
    """Get concurrency limit for a phase."""
    return get_concurrency_manager().get_limit(phase)


def set_phase_limit(phase: PipelinePhase, limit: int) -> None:
    """Set concurrency limit for a phase."""
    get_concurrency_manager().set_limit(phase, limit)
