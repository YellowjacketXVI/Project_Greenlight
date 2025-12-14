"""
Greenlight Steal List Judge - Story Pipeline v3.0

Judges that rank story concepts and extract "steal" elements from non-winning concepts.

The steal list mechanism works like a professional writers' room:
- 3 judges rank 5 concepts
- Each judge identifies 2-3 elements worth "stealing" from non-winning concepts
- Elements mentioned by 2+ judges are added to the final steal list
- The winning concept must incorporate all steal list items

This ensures good ideas aren't lost just because another concept won.
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

from greenlight.core.logging_config import get_logger
from greenlight.patterns.assembly import Proposal

logger = get_logger("agents.steal_judge")


@dataclass
class JudgeVote:
    """A judge's vote on story concepts."""
    judge_id: str
    rankings: List[str]  # Ordered list of concept IDs, best first
    reasoning: str
    steal_elements: List[str]  # Elements worth stealing from non-winners
    
    def get_winner(self) -> str:
        """Get the top-ranked concept ID."""
        return self.rankings[0] if self.rankings else ""
    
    def get_points(self) -> Dict[str, int]:
        """Convert rankings to points (5 for 1st, 4 for 2nd, etc.)."""
        points = {}
        for i, concept_id in enumerate(self.rankings):
            points[concept_id] = 5 - i  # 5, 4, 3, 2, 1
        return points


@dataclass
class StealListJudgeConfig:
    """Configuration for a steal list judge."""
    judge_id: str
    focus: str  # What this judge prioritizes
    system_prompt: str


# Judge configurations - 3 judges with different focuses
JUDGE_CONFIGS: List[StealListJudgeConfig] = [
    StealListJudgeConfig(
        judge_id="judge_narrative",
        focus="narrative structure and story momentum",
        system_prompt=(
            "You are a narrative structure expert. You evaluate stories based on "
            "their dramatic arc, pacing, and how effectively they build tension "
            "and deliver satisfying payoffs."
        )
    ),
    StealListJudgeConfig(
        judge_id="judge_emotional",
        focus="emotional resonance and character truth",
        system_prompt=(
            "You are an emotional truth expert. You evaluate stories based on "
            "how deeply they connect with audiences, the authenticity of character "
            "emotions, and the power of key emotional moments."
        )
    ),
    StealListJudgeConfig(
        judge_id="judge_visual",
        focus="visual storytelling and cinematic potential",
        system_prompt=(
            "You are a visual storytelling expert. You evaluate stories based on "
            "their imagery, atmosphere, and how well they translate to visual "
            "medium with memorable, iconic moments."
        )
    )
]


class StealListJudge:
    """
    A judge that ranks concepts and extracts steal elements.
    
    Each judge:
    1. Ranks all 5 concepts from best to worst
    2. Provides reasoning for their ranking
    3. Identifies 2-3 elements worth "stealing" from non-winning concepts
    """
    
    def __init__(
        self,
        config: StealListJudgeConfig,
        llm_caller: Callable
    ):
        self.config = config
        self.llm_caller = llm_caller
    
    async def evaluate(
        self,
        concepts: List[Proposal],
        context_text: str
    ) -> JudgeVote:
        """
        Evaluate concepts and return vote with steal elements.
        
        Args:
            concepts: List of Proposal objects from brainstorm agents
            context_text: Story seed and character context
            
        Returns:
            JudgeVote with rankings and steal elements
        """
        # Build concepts text
        concepts_text = ""
        for i, concept in enumerate(concepts):
            letter = chr(65 + i)  # A, B, C, D, E
            concepts_text += f"\n[CONCEPT {letter}] ({concept.agent_id}):\n{concept.content}\n"
        
        prompt = f"""{context_text}

CONCEPTS TO EVALUATE:
{concepts_text}

EVALUATION FOCUS: {self.config.focus}

Evaluate these concepts and provide:

1. RANKING: Rank all concepts from best to worst (A, B, C, D, E)
2. REASONING: Brief explanation of your ranking (2-3 sentences)
3. STEAL LIST: Identify 2-3 specific elements from NON-WINNING concepts that are too good to lose. These should be concrete story elements (a character moment, a visual image, a thematic beat) that could enhance the winning concept.

Format your response EXACTLY as:
RANKING: [letter], [letter], [letter], [letter], [letter]
REASONING: [your reasoning]
STEAL: [element 1] | [element 2] | [element 3]"""

        try:
            response = await self.llm_caller(
                prompt=prompt,
                system_prompt=self.config.system_prompt,
                max_tokens=400
            )
            
            return self._parse_response(response, concepts)
        except Exception as e:
            logger.error(f"Judge {self.config.judge_id} failed: {e}")
            # Return default vote on error
            return JudgeVote(
                judge_id=self.config.judge_id,
                rankings=[c.agent_id for c in concepts],
                reasoning=f"Error: {str(e)}",
                steal_elements=[]
            )

    def _parse_response(
        self,
        response: str,
        concepts: List[Proposal]
    ) -> JudgeVote:
        """Parse LLM response into JudgeVote."""
        # Create letter -> agent_id mapping
        letter_to_id = {
            chr(65 + i): concept.agent_id
            for i, concept in enumerate(concepts)
        }

        # Parse ranking
        ranking_match = re.search(r'RANKING:\s*([A-E](?:\s*,\s*[A-E])*)', response, re.IGNORECASE)
        if ranking_match:
            letters = re.findall(r'[A-E]', ranking_match.group(1).upper())
            rankings = [letter_to_id.get(l, l) for l in letters]
        else:
            # Default to original order
            rankings = [c.agent_id for c in concepts]

        # Parse reasoning
        reasoning_match = re.search(r'REASONING:\s*(.+?)(?=STEAL:|$)', response, re.DOTALL | re.IGNORECASE)
        reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

        # Parse steal elements
        steal_match = re.search(r'STEAL:\s*(.+?)$', response, re.DOTALL | re.IGNORECASE)
        if steal_match:
            steal_text = steal_match.group(1).strip()
            steal_elements = [s.strip() for s in steal_text.split('|') if s.strip()]
        else:
            steal_elements = []

        return JudgeVote(
            judge_id=self.config.judge_id,
            rankings=rankings,
            reasoning=reasoning,
            steal_elements=steal_elements
        )


class JudgePanel:
    """
    Orchestrates 3 judges to evaluate concepts and build steal list.

    The panel:
    1. Runs all 3 judges in parallel
    2. Aggregates rankings to determine winner
    3. Collects steal elements (2+ mentions = included)
    """

    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller
        self.judges = [
            StealListJudge(config, llm_caller)
            for config in JUDGE_CONFIGS
        ]

    async def evaluate_concepts(
        self,
        concepts: List[Proposal],
        context_text: str
    ) -> Dict[str, Any]:
        """
        Run all judges and aggregate results.

        Args:
            concepts: List of Proposal objects from brainstorm agents
            context_text: Story seed and character context

        Returns:
            Dict with:
                - winner: Proposal (winning concept)
                - votes: List[JudgeVote]
                - steal_list: List[str] (elements mentioned by 2+ judges)
                - scores: Dict[str, int] (total points per concept)
        """
        # Run judges in parallel
        tasks = [
            judge.evaluate(concepts, context_text)
            for judge in self.judges
        ]
        votes = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        valid_votes = []
        for vote in votes:
            if isinstance(vote, Exception):
                logger.error(f"Judge raised exception: {vote}")
            else:
                valid_votes.append(vote)

        # Aggregate scores
        scores: Dict[str, int] = {}
        for vote in valid_votes:
            for concept_id, points in vote.get_points().items():
                scores[concept_id] = scores.get(concept_id, 0) + points

        # Determine winner
        winner_id = max(scores, key=scores.get) if scores else concepts[0].agent_id
        winner = next((c for c in concepts if c.agent_id == winner_id), concepts[0])

        # Build steal list (elements mentioned by 2+ judges)
        element_counts: Dict[str, int] = {}
        for vote in valid_votes:
            for element in vote.steal_elements:
                # Normalize element for comparison
                normalized = element.lower().strip()
                element_counts[element] = element_counts.get(element, 0) + 1

        steal_list = [
            element for element, count in element_counts.items()
            if count >= 2
        ]

        logger.info(f"Judge panel: winner={winner_id}, steal_list={len(steal_list)} items")

        return {
            "winner": winner,
            "votes": valid_votes,
            "steal_list": steal_list,
            "scores": scores
        }
