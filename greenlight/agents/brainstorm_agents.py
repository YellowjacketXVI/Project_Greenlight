"""
Greenlight Brainstorm Agents - Story Pipeline v3.0

5 philosophy-based brainstorm agents that generate competing story concepts:
- Character-first: Internal transformation focus
- Conflict-first: External struggle focus
- Theme-first: Meaning/message focus
- Relationship-first: Connection/bond focus
- Sensory-first: Atmosphere/visual focus

Each agent receives compressed context (~200 words) and outputs a 150-200 word
story concept pitch based on their unique storytelling philosophy.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from greenlight.patterns.assembly import ProposalAgent, Proposal
from greenlight.context.agent_context_delivery import AgentContextDelivery

logger = get_logger("agents.brainstorm")


class BrainstormPhilosophy(Enum):
    """Storytelling philosophies for brainstorm agents."""
    CHARACTER_FIRST = "character_first"
    CONFLICT_FIRST = "conflict_first"
    THEME_FIRST = "theme_first"
    RELATIONSHIP_FIRST = "relationship_first"
    SENSORY_FIRST = "sensory_first"


@dataclass
class BrainstormPhilosophyConfig:
    """Configuration for a brainstorm philosophy."""
    name: str
    focus: str
    system_prompt: str
    key_questions: List[str]


# Philosophy configurations
PHILOSOPHY_CONFIGS: Dict[BrainstormPhilosophy, BrainstormPhilosophyConfig] = {
    BrainstormPhilosophy.CHARACTER_FIRST: BrainstormPhilosophyConfig(
        name="Character-first",
        focus="the protagonist's internal transformation",
        system_prompt=(
            "You are a character-driven storyteller. You believe the best stories "
            "emerge from deep character psychology. Every plot point should reveal "
            "or challenge who the protagonist truly is."
        ),
        key_questions=[
            "What is the protagonist's deepest wound?",
            "What lie do they believe about themselves?",
            "What truth must they accept to transform?"
        ]
    ),
    BrainstormPhilosophy.CONFLICT_FIRST: BrainstormPhilosophyConfig(
        name="Conflict-first",
        focus="the central power struggle and opposition",
        system_prompt=(
            "You are a conflict-driven storyteller. You believe stories are forged "
            "in the crucible of opposition. The antagonist's pressure reveals the "
            "protagonist's true nature."
        ),
        key_questions=[
            "What does the antagonist want that threatens the protagonist?",
            "What escalating obstacles force impossible choices?",
            "What is the ultimate confrontation?"
        ]
    ),
    BrainstormPhilosophy.THEME_FIRST: BrainstormPhilosophyConfig(
        name="Theme-first",
        focus="what the story means and says about life",
        system_prompt=(
            "You are a theme-driven storyteller. You believe stories should illuminate "
            "universal truths. Every scene should explore the central question the "
            "story asks about human existence."
        ),
        key_questions=[
            "What question about life does this story ask?",
            "How do different characters embody different answers?",
            "What does the ending say about the theme?"
        ]
    ),
    BrainstormPhilosophy.RELATIONSHIP_FIRST: BrainstormPhilosophyConfig(
        name="Relationship-first",
        focus="the key emotional bonds between characters",
        system_prompt=(
            "You are a relationship-driven storyteller. You believe the heart of "
            "every story is the connection between people. Plot exists to test, "
            "strain, and ultimately transform relationships."
        ),
        key_questions=[
            "What is the central relationship that drives the story?",
            "How does this relationship change from beginning to end?",
            "What moment crystallizes the relationship's transformation?"
        ]
    ),
    BrainstormPhilosophy.SENSORY_FIRST: BrainstormPhilosophyConfig(
        name="Sensory-first",
        focus="atmosphere, texture, and visual storytelling",
        system_prompt=(
            "You are a sensory-driven storyteller. You believe stories should be "
            "felt before they are understood. Atmosphere, imagery, and visceral "
            "experience create emotional truth."
        ),
        key_questions=[
            "What is the dominant visual/sensory motif?",
            "How does the environment reflect the emotional journey?",
            "What single image captures the story's essence?"
        ]
    )
}


class BrainstormAgent(ProposalAgent):
    """
    A brainstorm agent with a specific storytelling philosophy.
    
    Generates a 150-200 word story concept pitch based on compressed context.
    """
    
    def __init__(
        self,
        philosophy: BrainstormPhilosophy,
        llm_caller: Callable,
        agent_id: str = None
    ):
        agent_id = agent_id or f"brainstorm_{philosophy.value}"
        super().__init__(agent_id)
        
        self.philosophy = philosophy
        self.config = PHILOSOPHY_CONFIGS[philosophy]
        self.llm_caller = llm_caller
    
    async def generate_proposal(
        self,
        context: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Proposal:
        """
        Generate a story concept proposal.
        
        Args:
            context: Must contain 'delivery' (AgentContextDelivery) or 'context_text'
            constraints: Optional constraints (word_limit, etc.)
            
        Returns:
            Proposal with story concept
        """
        constraints = constraints or {}
        word_limit = constraints.get("word_limit", 200)

        # Get context text
        if "delivery" in context:
            delivery: AgentContextDelivery = context["delivery"]
            context_text = delivery.for_brainstorm_agent(
                philosophy=self.config.name,
                focus=self.config.focus
            )
        elif "context_text" in context:
            context_text = context["context_text"]
        else:
            raise ValueError("Context must contain 'delivery' or 'context_text'")

        # Build prompt
        questions_text = "\n".join(f"- {q}" for q in self.config.key_questions)
        prompt = f"""{context_text}

KEY QUESTIONS TO CONSIDER:
{questions_text}

Generate a {word_limit}-word story concept pitch that:
1. Emphasizes {self.config.focus}
2. Answers the key questions above
3. Creates a compelling narrative hook
4. Suggests clear story beats without listing them

Write in present tense, active voice. Be specific, not generic."""

        try:
            response = await self.llm_caller(
                prompt=prompt,
                system_prompt=self.config.system_prompt,
                max_tokens=500
            )

            return Proposal(
                agent_id=self.agent_id,
                content=response,
                metadata={
                    "philosophy": self.philosophy.value,
                    "focus": self.config.focus
                }
            )
        except Exception as e:
            logger.error(f"Brainstorm agent {self.agent_id} failed: {e}")
            return Proposal(
                agent_id=self.agent_id,
                content=f"[ERROR: {str(e)}]",
                metadata={"error": str(e)}
            )


class BrainstormOrchestrator:
    """
    Orchestrates all 5 brainstorm agents in parallel.

    Returns 5 competing story concepts for judge evaluation.
    """

    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller
        self.agents = [
            BrainstormAgent(philosophy, llm_caller)
            for philosophy in BrainstormPhilosophy
        ]

    async def generate_concepts(
        self,
        delivery: AgentContextDelivery,
        constraints: Dict[str, Any] = None
    ) -> List[Proposal]:
        """
        Generate 5 competing story concepts in parallel.

        Args:
            delivery: AgentContextDelivery with compressed context
            constraints: Optional constraints for all agents

        Returns:
            List of 5 Proposals, one from each philosophy
        """
        context = {"delivery": delivery}

        tasks = [
            agent.generate_proposal(context, constraints)
            for agent in self.agents
        ]

        proposals = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        results = []
        for i, proposal in enumerate(proposals):
            if isinstance(proposal, Exception):
                logger.error(f"Agent {self.agents[i].agent_id} raised: {proposal}")
                results.append(Proposal(
                    agent_id=self.agents[i].agent_id,
                    content=f"[ERROR: {str(proposal)}]",
                    metadata={"error": str(proposal)}
                ))
            else:
                results.append(proposal)

        logger.info(f"Generated {len(results)} brainstorm concepts")
        return results

    def get_philosophies(self) -> List[str]:
        """Get list of philosophy names."""
        return [p.value for p in BrainstormPhilosophy]

