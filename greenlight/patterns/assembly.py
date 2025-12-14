"""
Assembly Pattern for Writer Flow v2

The Assembly Pattern orchestrates multi-agent collaboration through:
1. Parallel Proposals - Multiple agents generate competing proposals
2. Judges - 5 judges rank proposals on different criteria
3. Calculator - Aggregates rankings into weighted scores
4. Synthesizer - Merges best elements into final output
5. Continuity Loop - Validates and iterates (max 3 times)
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, TypeVar, Generic
from enum import Enum

from greenlight.core.logging_config import get_logger

logger = get_logger("patterns.assembly")

T = TypeVar('T')


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Proposal:
    """A proposal from a proposal agent."""
    agent_id: str
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    
@dataclass
class JudgeRanking:
    """Ranking from a single judge."""
    judge_id: str
    criterion: str
    rankings: List[str]  # Ordered list of agent_ids, best first
    scores: Dict[str, float] = field(default_factory=dict)  # agent_id -> score
    reasoning: str = ""


@dataclass
class CalculatorResult:
    """Aggregated result from the calculator."""
    weighted_scores: Dict[str, float]  # agent_id -> weighted score
    best_elements: Dict[str, Any]  # criterion -> best element
    ranking_order: List[str]  # agent_ids in order of total score
    

@dataclass
class SynthesisResult:
    """Result from the synthesizer."""
    content: Any
    sources: List[str]  # agent_ids that contributed
    synthesis_notes: str = ""


@dataclass
class ContinuityCheckResult:
    """Result from continuity validation."""
    passed: bool
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class AssemblyConfig:
    """Configuration for the Assembly Pattern."""
    max_continuity_iterations: int = 3
    parallel_proposals: bool = True
    judge_weights: Dict[str, float] = field(default_factory=lambda: {
        "narrative": 1.0,
        "character": 1.0,
        "visual": 1.0,
        "pacing": 1.0,
        "coherence": 1.0,
    })
    require_all_judges: bool = True
    synthesis_strategy: str = "merge_best"  # merge_best, weighted_blend, top_pick


# =============================================================================
# ABSTRACT BASE CLASSES
# =============================================================================

class ProposalAgent(ABC):
    """Base class for proposal-generating agents."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
    
    @abstractmethod
    async def generate_proposal(
        self, 
        context: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Proposal:
        """Generate a proposal based on context."""
        pass


class JudgeAgent(ABC):
    """Base class for judge agents."""
    
    def __init__(self, judge_id: str, criterion: str):
        self.judge_id = judge_id
        self.criterion = criterion
    
    @abstractmethod
    async def rank_proposals(
        self,
        proposals: List[Proposal],
        context: Dict[str, Any]
    ) -> JudgeRanking:
        """Rank proposals based on this judge's criterion."""
        pass


class CalculatorAgent(ABC):
    """Base class for the calculator agent."""
    
    @abstractmethod
    async def aggregate_rankings(
        self,
        rankings: List[JudgeRanking],
        weights: Dict[str, float]
    ) -> CalculatorResult:
        """Aggregate judge rankings into weighted scores."""
        pass


class SynthesizerAgent(ABC):
    """Base class for the synthesizer agent."""
    
    @abstractmethod
    async def synthesize(
        self,
        proposals: List[Proposal],
        calculator_result: CalculatorResult,
        context: Dict[str, Any]
    ) -> SynthesisResult:
        """Synthesize best elements into final output."""
        pass


class ContinuityValidator(ABC):
    """Base class for continuity validation."""

    @abstractmethod
    async def validate(
        self,
        synthesis: SynthesisResult,
        context: Dict[str, Any]
    ) -> ContinuityCheckResult:
        """Validate synthesis for continuity issues."""
        pass


# =============================================================================
# ASSEMBLY PATTERN ORCHESTRATOR
# =============================================================================

class AssemblyPattern:
    """
    Orchestrates the Assembly Pattern workflow.

    Flow:
    1. Parallel Proposals → 2. Judges → 3. Calculator → 4. Synthesizer → 5. Continuity Loop
    """

    def __init__(
        self,
        proposal_agents: List[ProposalAgent],
        judge_agents: List[JudgeAgent],
        calculator: CalculatorAgent,
        synthesizer: SynthesizerAgent,
        continuity_validator: ContinuityValidator = None,
        config: AssemblyConfig = None
    ):
        self.proposal_agents = proposal_agents
        self.judge_agents = judge_agents
        self.calculator = calculator
        self.synthesizer = synthesizer
        self.continuity_validator = continuity_validator
        self.config = config or AssemblyConfig()

        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable) -> None:
        """Set callback for progress updates."""
        self._progress_callback = callback

    def _report_progress(self, stage: str, detail: str = "") -> None:
        """Report progress to callback."""
        if self._progress_callback:
            self._progress_callback({"stage": stage, "detail": detail})

    async def execute(
        self,
        context: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> SynthesisResult:
        """
        Execute the full Assembly Pattern.

        Args:
            context: Context for proposal generation
            constraints: Optional constraints for proposals

        Returns:
            Final synthesized result
        """
        constraints = constraints or {}

        # Stage 1: Generate proposals in parallel
        self._report_progress("proposals", "Generating parallel proposals...")
        proposals = await self._generate_proposals(context, constraints)
        logger.info(f"Generated {len(proposals)} proposals")

        # Stage 2: Judge proposals
        self._report_progress("judging", "Judges evaluating proposals...")
        rankings = await self._judge_proposals(proposals, context)
        logger.info(f"Received {len(rankings)} judge rankings")

        # Stage 3: Calculate aggregated scores
        self._report_progress("calculating", "Aggregating rankings...")
        calc_result = await self.calculator.aggregate_rankings(
            rankings, self.config.judge_weights
        )
        logger.info(f"Top ranked: {calc_result.ranking_order[:3]}")

        # Stage 4: Synthesize
        self._report_progress("synthesizing", "Synthesizing best elements...")
        synthesis = await self.synthesizer.synthesize(
            proposals, calc_result, context
        )

        # Stage 5: Continuity loop
        if self.continuity_validator:
            synthesis = await self._continuity_loop(synthesis, context)

        self._report_progress("complete", "Assembly complete")
        return synthesis

    async def _generate_proposals(
        self,
        context: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> List[Proposal]:
        """Generate proposals from all proposal agents."""
        if self.config.parallel_proposals:
            # Run all agents in parallel
            tasks = [
                agent.generate_proposal(context, constraints)
                for agent in self.proposal_agents
            ]
            proposals = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions
            valid_proposals = []
            for i, result in enumerate(proposals):
                if isinstance(result, Exception):
                    logger.error(f"Proposal agent {i} failed: {result}")
                else:
                    valid_proposals.append(result)
            return valid_proposals
        else:
            # Sequential execution
            proposals = []
            for agent in self.proposal_agents:
                try:
                    proposal = await agent.generate_proposal(context, constraints)
                    proposals.append(proposal)
                except Exception as e:
                    logger.error(f"Proposal agent {agent.agent_id} failed: {e}")
            return proposals

    async def _judge_proposals(
        self,
        proposals: List[Proposal],
        context: Dict[str, Any]
    ) -> List[JudgeRanking]:
        """Have all judges rank the proposals."""
        # Run judges in parallel
        tasks = [
            judge.rank_proposals(proposals, context)
            for judge in self.judge_agents
        ]
        rankings = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_rankings = []
        for i, result in enumerate(rankings):
            if isinstance(result, Exception):
                logger.error(f"Judge {i} failed: {result}")
                if self.config.require_all_judges:
                    raise RuntimeError(f"Required judge failed: {result}")
            else:
                valid_rankings.append(result)

        return valid_rankings

    async def _continuity_loop(
        self,
        synthesis: SynthesisResult,
        context: Dict[str, Any]
    ) -> SynthesisResult:
        """Run continuity validation loop."""
        for iteration in range(self.config.max_continuity_iterations):
            self._report_progress(
                "continuity",
                f"Validation iteration {iteration + 1}/{self.config.max_continuity_iterations}"
            )

            check = await self.continuity_validator.validate(synthesis, context)

            if check.passed:
                logger.info(f"Continuity passed on iteration {iteration + 1}")
                return synthesis

            logger.warning(f"Continuity issues: {check.issues}")

            # Add issues to context for re-synthesis
            context["continuity_issues"] = check.issues
            context["continuity_suggestions"] = check.suggestions

            # Re-synthesize with feedback
            # Note: In a full implementation, this would re-run synthesis
            # with the continuity feedback incorporated

        logger.warning("Max continuity iterations reached")
        return synthesis

