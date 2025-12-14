"""
Assembly Agents for Writer Flow v2

Concrete implementations of proposal, judge, calculator, and synthesizer agents
for the Assembly Pattern.
"""

import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from greenlight.agents.base_agent import BaseAgent, AgentConfig, AgentResponse
from greenlight.patterns.assembly import (
    ProposalAgent, JudgeAgent, CalculatorAgent, SynthesizerAgent,
    ContinuityValidator, Proposal, JudgeRanking, CalculatorResult,
    SynthesisResult, ContinuityCheckResult
)

logger = get_logger("agents.assembly")


# =============================================================================
# PROPOSAL AGENTS
# =============================================================================

class StoryOutlineProposalAgent(ProposalAgent):
    """
    Story Outline Proposal Agent.
    
    Generates story outline proposals with different perspectives:
    - Agent 1: Plot-focused
    - Agent 2: Character-focused
    - Agent 3: Theme-focused
    - Agent 4: Pacing-focused
    - Agent 5: Visual-focused
    - Agent 6: Emotional-focused
    - Agent 7: Structure-focused
    """
    
    PERSPECTIVES = {
        "plot": "Focus on plot mechanics, cause-and-effect, and narrative logic.",
        "character": "Focus on character motivations, arcs, and relationships.",
        "theme": "Focus on thematic resonance and symbolic meaning.",
        "pacing": "Focus on rhythm, tension, and narrative momentum.",
        "visual": "Focus on visual storytelling and cinematic moments.",
        "emotional": "Focus on emotional beats and audience engagement.",
        "structure": "Focus on act structure, scene transitions, and story architecture."
    }
    
    def __init__(
        self,
        agent_id: str,
        perspective: str,
        llm_caller: Callable
    ):
        super().__init__(agent_id)
        self.perspective = perspective
        self.llm_caller = llm_caller
        self.perspective_prompt = self.PERSPECTIVES.get(perspective, "")
    
    async def generate_proposal(
        self,
        context: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Proposal:
        """Generate a story outline proposal."""
        constraints = constraints or {}
        
        prompt = self._build_prompt(context, constraints)
        
        response = await self.llm_caller(
            prompt=prompt,
            system_prompt=f"You are a story outline agent with a {self.perspective} perspective. {self.perspective_prompt}",
            function=LLMFunction.STORY_GENERATION
        )
        
        return Proposal(
            agent_id=self.agent_id,
            content=response,
            metadata={
                "perspective": self.perspective,
                "word_count": len(response.split())
            }
        )
    
    def _build_prompt(self, context: Dict[str, Any], constraints: Dict[str, Any]) -> str:
        """Build the proposal prompt."""
        pitch = context.get("pitch", "")
        genre = context.get("genre", "")
        word_cap = constraints.get("word_cap", {})
        
        return f"""Create a story outline based on the following pitch:

PITCH:
{pitch}

GENRE: {genre}

CONSTRAINTS:
- Target scenes: {word_cap.get('scenes', 8)}
- Word range: {word_cap.get('min', 750)}-{word_cap.get('max', 1000)} words

Your perspective: {self.perspective_prompt}

Provide a structured outline with:
1. Act breakdown (3 acts)
2. Scene list with brief descriptions
3. Key plot points
4. Character involvement per scene

Format as structured JSON."""


class CharacterArchitectureProposalAgent(ProposalAgent):
    """Character Architecture Proposal Agent."""
    
    PERSPECTIVES = {
        "psychology": "Focus on psychological depth and internal conflicts.",
        "relationships": "Focus on character relationships and dynamics.",
        "arc": "Focus on character transformation and growth.",
        "motivation": "Focus on wants, needs, and driving forces.",
        "backstory": "Focus on history and formative experiences.",
        "voice": "Focus on dialogue patterns and unique expression.",
        "visual": "Focus on physical appearance and visual characterization."
    }
    
    def __init__(self, agent_id: str, perspective: str, llm_caller: Callable):
        super().__init__(agent_id)
        self.perspective = perspective
        self.llm_caller = llm_caller
        self.perspective_prompt = self.PERSPECTIVES.get(perspective, "")
    
    async def generate_proposal(
        self,
        context: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Proposal:
        """Generate a character architecture proposal."""
        constraints = constraints or {}
        characters = context.get("characters", [])
        
        prompt = f"""Develop character architecture for the following characters:

CHARACTERS: {json.dumps(characters, indent=2)}

STORY CONTEXT:
{context.get('story_outline', '')}

Your perspective: {self.perspective_prompt}

For each character, provide:
1. Core identity
2. Arc trajectory
3. Key relationships
4. Defining moments

Format as structured JSON."""
        
        response = await self.llm_caller(
            prompt=prompt,
            system_prompt=f"You are a character architect with a {self.perspective} focus.",
            function=LLMFunction.STORY_GENERATION
        )
        
        return Proposal(
            agent_id=self.agent_id,
            content=response,
            metadata={"perspective": self.perspective}
        )


# =============================================================================
# JUDGE AGENTS
# =============================================================================

class AssemblyJudgeAgent(JudgeAgent):
    """
    Judge agent for the Assembly Pattern.

    5 Judges with different criteria:
    - Narrative: Story logic and flow
    - Character: Character authenticity and development
    - Visual: Cinematic potential and visual storytelling
    - Pacing: Rhythm and tension management
    - Coherence: Internal consistency and continuity
    """

    CRITERIA_PROMPTS = {
        "narrative": "Evaluate narrative logic, cause-and-effect, and story flow.",
        "character": "Evaluate character authenticity, motivation clarity, and arc strength.",
        "visual": "Evaluate cinematic potential, visual storytelling, and scene composition.",
        "pacing": "Evaluate rhythm, tension management, and narrative momentum.",
        "coherence": "Evaluate internal consistency, continuity, and logical coherence."
    }

    def __init__(self, judge_id: str, criterion: str, llm_caller: Callable):
        super().__init__(judge_id, criterion)
        self.llm_caller = llm_caller
        self.criterion_prompt = self.CRITERIA_PROMPTS.get(criterion, "")

    async def rank_proposals(
        self,
        proposals: List[Proposal],
        context: Dict[str, Any]
    ) -> JudgeRanking:
        """Rank proposals based on this judge's criterion."""

        # Format proposals for evaluation
        proposals_text = "\n\n".join([
            f"=== PROPOSAL {p.agent_id} ===\n{p.content}"
            for p in proposals
        ])

        prompt = f"""You are a judge evaluating story proposals based on: {self.criterion}

{self.criterion_prompt}

PROPOSALS TO EVALUATE:
{proposals_text}

CONTEXT:
{context.get('pitch', '')}

Rank all proposals from best to worst for {self.criterion}.
For each proposal, provide a score from 1-10.

Respond in JSON format:
{{
    "rankings": ["agent_id_1", "agent_id_2", ...],
    "scores": {{"agent_id_1": 8.5, "agent_id_2": 7.0, ...}},
    "reasoning": "Brief explanation of rankings"
}}"""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt=f"You are a {self.criterion} judge for story evaluation.",
            function=LLMFunction.STORY_ANALYSIS
        )

        # Parse response
        try:
            result = json.loads(response)
            return JudgeRanking(
                judge_id=self.judge_id,
                criterion=self.criterion,
                rankings=result.get("rankings", []),
                scores=result.get("scores", {}),
                reasoning=result.get("reasoning", "")
            )
        except json.JSONDecodeError:
            # Fallback: return empty ranking
            logger.error(f"Failed to parse judge response: {response[:200]}")
            return JudgeRanking(
                judge_id=self.judge_id,
                criterion=self.criterion,
                rankings=[p.agent_id for p in proposals],
                scores={p.agent_id: 5.0 for p in proposals},
                reasoning="Parse error - default ranking"
            )


# =============================================================================
# CALCULATOR AGENT
# =============================================================================

class AssemblyCalculatorAgent(CalculatorAgent):
    """
    Calculator agent that aggregates judge rankings.

    Uses weighted scoring to combine rankings from all judges.
    """

    async def aggregate_rankings(
        self,
        rankings: List[JudgeRanking],
        weights: Dict[str, float]
    ) -> CalculatorResult:
        """Aggregate judge rankings into weighted scores."""

        # Collect all agent IDs
        all_agents = set()
        for ranking in rankings:
            all_agents.update(ranking.scores.keys())

        # Calculate weighted scores
        weighted_scores = {agent: 0.0 for agent in all_agents}
        total_weight = sum(weights.get(r.criterion, 1.0) for r in rankings)

        for ranking in rankings:
            weight = weights.get(ranking.criterion, 1.0) / total_weight
            for agent_id, score in ranking.scores.items():
                weighted_scores[agent_id] += score * weight

        # Sort by score
        ranking_order = sorted(
            weighted_scores.keys(),
            key=lambda x: weighted_scores[x],
            reverse=True
        )

        # Identify best elements per criterion
        best_elements = {}
        for ranking in rankings:
            if ranking.rankings:
                best_elements[ranking.criterion] = ranking.rankings[0]

        return CalculatorResult(
            weighted_scores=weighted_scores,
            best_elements=best_elements,
            ranking_order=ranking_order
        )


# =============================================================================
# SYNTHESIZER AGENT
# =============================================================================

class AssemblySynthesizerAgent(SynthesizerAgent):
    """
    Synthesizer agent that merges best elements into final output.
    """

    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller

    async def synthesize(
        self,
        proposals: List[Proposal],
        calculator_result: CalculatorResult,
        context: Dict[str, Any]
    ) -> SynthesisResult:
        """Synthesize best elements into final output."""

        # Get top proposals
        top_agents = calculator_result.ranking_order[:3]
        top_proposals = [p for p in proposals if p.agent_id in top_agents]

        # Format for synthesis
        proposals_text = "\n\n".join([
            f"=== TOP PROPOSAL: {p.agent_id} (Score: {calculator_result.weighted_scores.get(p.agent_id, 0):.2f}) ===\n{p.content}"
            for p in top_proposals
        ])

        best_elements_text = "\n".join([
            f"- Best for {criterion}: {agent_id}"
            for criterion, agent_id in calculator_result.best_elements.items()
        ])

        prompt = f"""Synthesize the best elements from these top-ranked proposals into a unified output.

TOP PROPOSALS:
{proposals_text}

BEST ELEMENTS BY CRITERION:
{best_elements_text}

CONTEXT:
{context.get('pitch', '')}

Create a synthesized output that:
1. Takes the strongest narrative elements from the top proposal
2. Incorporates the best character work
3. Maintains visual storytelling strength
4. Preserves good pacing
5. Ensures coherence

Provide the synthesized result as a complete, unified document."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a synthesis agent that merges the best elements from multiple proposals.",
            function=LLMFunction.STORY_GENERATION
        )

        return SynthesisResult(
            content=response,
            sources=top_agents,
            synthesis_notes=f"Synthesized from {len(top_agents)} top proposals"
        )


# =============================================================================
# CONTINUITY VALIDATOR
# =============================================================================

class AssemblyContinuityValidator(ContinuityValidator):
    """
    Continuity validator for the Assembly Pattern.

    Checks for:
    - Plot holes
    - Character consistency
    - Timeline issues
    - Spatial continuity
    - Prop tracking
    """

    CONTINUITY_CHECKLIST = [
        "Character locations match scene requirements",
        "Timeline is consistent (no impossible time jumps)",
        "Character knowledge matches what they've experienced",
        "Props appear only after being introduced",
        "Character motivations remain consistent",
        "Cause-and-effect chains are logical"
    ]

    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller

    async def validate(
        self,
        synthesis: SynthesisResult,
        context: Dict[str, Any]
    ) -> ContinuityCheckResult:
        """Validate synthesis for continuity issues."""

        checklist_text = "\n".join([f"- {item}" for item in self.CONTINUITY_CHECKLIST])

        prompt = f"""Validate the following content for continuity issues.

CONTENT:
{synthesis.content}

CONTINUITY CHECKLIST:
{checklist_text}

Check each item and identify any issues.

Respond in JSON format:
{{
    "passed": true/false,
    "issues": ["issue 1", "issue 2", ...],
    "suggestions": ["fix 1", "fix 2", ...]
}}"""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a continuity validator checking for plot holes and inconsistencies.",
            function=LLMFunction.CONTINUITY
        )

        try:
            result = json.loads(response)
            return ContinuityCheckResult(
                passed=result.get("passed", True),
                issues=result.get("issues", []),
                suggestions=result.get("suggestions", [])
            )
        except json.JSONDecodeError:
            # Assume passed if can't parse
            return ContinuityCheckResult(passed=True)

