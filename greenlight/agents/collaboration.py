"""
Collaborative Execution Framework

Enables two agents to engage in structured dialogue for iterative refinement
and deep exploration of complex problems.

Two collaboration modes:
1. SOCRATIC_COLLABORATION: Iterative refinement through dialectical questioning
2. ROLEPLAY_COLLABORATION: Embodied perspective-taking for authenticity validation
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import time
import asyncio

from greenlight.core.logging_config import get_logger
from .base_agent import BaseAgent, AgentConfig, AgentResponse

logger = get_logger("agents.collaboration")


class CollaborationMode(Enum):
    """Collaboration execution modes."""
    SOCRATIC = "socratic_collaboration"
    ROLEPLAY = "roleplay_collaboration"


@dataclass
class CollaborationConfig:
    """Configuration for collaborative execution."""
    mode: CollaborationMode
    agent_a_name: str
    agent_b_name: str
    max_iterations: int = 5
    convergence_threshold: float = 0.85
    temperature_a: Optional[float] = None
    temperature_b: Optional[float] = None
    system_prompt_a: str = ""
    system_prompt_b: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollaborationTurn:
    """A single turn in collaborative dialogue."""
    turn_number: int
    agent_name: str
    prompt: str
    response: str
    reasoning: str
    tokens_used: int
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollaborationResult:
    """Result of collaborative execution."""
    success: bool
    mode: CollaborationMode
    turns: List[CollaborationTurn]
    final_output: str
    convergence_achieved: bool
    iterations_completed: int
    total_time: float
    total_tokens: int
    dialogue_transcript: str
    insights: Dict[str, Any]
    errors: List[str] = field(default_factory=list)


class CollaborationAgent(BaseAgent):
    """
    Manages collaborative execution between two agents.
    
    Supports two modes:
    - SOCRATIC: Iterative refinement through critique and validation
    - ROLEPLAY: Embodied perspective-taking for authenticity validation
    """
    
    def __init__(self, llm_caller=None):
        """Initialize collaboration agent."""
        config = AgentConfig(
            name="CollaborationAgent",
            description="Manages collaborative dialogue between agents",
            system_prompt="You are a collaboration orchestrator managing dialogue between agents."
        )
        super().__init__(config, llm_caller)
    
    async def execute_socratic(
        self,
        agent_a: BaseAgent,
        agent_b: BaseAgent,
        goal: str,
        config: CollaborationConfig
    ) -> CollaborationResult:
        """
        Execute Socratic collaboration.
        
        Agent A (Ideator) proposes ideas.
        Agent B (Pragmatist) critiques and validates.
        Iterate until convergence.
        """
        turns = []
        current_idea = ""
        total_tokens = 0
        start_time = time.time()
        
        logger.info(f"Starting Socratic collaboration: {goal}")
        
        for iteration in range(config.max_iterations):
            # Phase 1: Agent A ideates/refines
            if iteration == 0:
                prompt_a = f"Generate a creative solution to: {goal}"
            else:
                prompt_a = f"Refine your idea based on feedback:\n{last_critique}"
            
            response_a = await agent_a.execute({'prompt': prompt_a})
            current_idea = response_a.content
            turns.append(CollaborationTurn(
                turn_number=len(turns) + 1,
                agent_name=agent_a.name,
                prompt=prompt_a,
                response=current_idea,
                reasoning="Ideation/Refinement",
                tokens_used=response_a.tokens_used,
                execution_time=response_a.execution_time
            ))
            total_tokens += response_a.tokens_used
            
            # Phase 2: Agent B critiques
            prompt_b = f"Analyze this idea:\n{current_idea}\n\nProvide pragmatic critique."
            response_b = await agent_b.execute({'prompt': prompt_b})
            last_critique = response_b.content
            turns.append(CollaborationTurn(
                turn_number=len(turns) + 1,
                agent_name=agent_b.name,
                prompt=prompt_b,
                response=last_critique,
                reasoning="Pragmatic Critique",
                tokens_used=response_b.tokens_used,
                execution_time=response_b.execution_time
            ))
            total_tokens += response_b.tokens_used
            
            # Check convergence
            if self._check_socratic_convergence(turns, config):
                logger.info(f"Socratic convergence achieved in {iteration + 1} iterations")
                return CollaborationResult(
                    success=True,
                    mode=CollaborationMode.SOCRATIC,
                    turns=turns,
                    final_output=current_idea,
                    convergence_achieved=True,
                    iterations_completed=iteration + 1,
                    total_time=time.time() - start_time,
                    total_tokens=total_tokens,
                    dialogue_transcript=self._build_transcript(turns),
                    insights=self._extract_socratic_insights(turns)
                )
        
        logger.info(f"Socratic collaboration completed without convergence after {config.max_iterations} iterations")
        return CollaborationResult(
            success=True,
            mode=CollaborationMode.SOCRATIC,
            turns=turns,
            final_output=current_idea,
            convergence_achieved=False,
            iterations_completed=config.max_iterations,
            total_time=time.time() - start_time,
            total_tokens=total_tokens,
            dialogue_transcript=self._build_transcript(turns),
            insights=self._extract_socratic_insights(turns)
        )
    
    async def execute_roleplay(
        self,
        agent_a: BaseAgent,
        agent_b: BaseAgent,
        context: str,
        character: str,
        config: CollaborationConfig
    ) -> CollaborationResult:
        """
        Execute Roleplay collaboration.
        
        Agent A (Roleplay) embodies character/perspective.
        Agent B (Instructor) guides exploration.
        Extract insights from dialogue.
        """
        turns = []
        total_tokens = 0
        start_time = time.time()
        
        logger.info(f"Starting Roleplay collaboration: {character}")
        
        # Phase 1: Agent B sets scene
        prompt_b = f"Set scene for roleplay:\nContext: {context}\nCharacter: {character}"
        response_b = await agent_b.execute({'prompt': prompt_b})
        turns.append(CollaborationTurn(
            turn_number=1,
            agent_name=agent_b.name,
            prompt=prompt_b,
            response=response_b.content,
            reasoning="Scene Setting",
            tokens_used=response_b.tokens_used,
            execution_time=response_b.execution_time
        ))
        total_tokens += response_b.tokens_used
        
        # Dialogue loop
        for iteration in range(config.max_iterations):
            # Agent A responds in-character
            prompt_a = f"Respond in-character as {character}:\n{turns[-1].response}"
            response_a = await agent_a.execute({'prompt': prompt_a})
            turns.append(CollaborationTurn(
                turn_number=len(turns) + 1,
                agent_name=agent_a.name,
                prompt=prompt_a,
                response=response_a.content,
                reasoning="In-Character Response",
                tokens_used=response_a.tokens_used,
                execution_time=response_a.execution_time
            ))
            total_tokens += response_a.tokens_used
            
            # Agent B guides deeper
            prompt_b = f"Ask follow-up to deepen exploration:\nPrevious: {turns[-1].response}"
            response_b = await agent_b.execute({'prompt': prompt_b})
            turns.append(CollaborationTurn(
                turn_number=len(turns) + 1,
                agent_name=agent_b.name,
                prompt=prompt_b,
                response=response_b.content,
                reasoning="Guided Exploration",
                tokens_used=response_b.tokens_used,
                execution_time=response_b.execution_time
            ))
            total_tokens += response_b.tokens_used
        
        logger.info(f"Roleplay collaboration completed after {config.max_iterations} iterations")
        return CollaborationResult(
            success=True,
            mode=CollaborationMode.ROLEPLAY,
            turns=turns,
            final_output="",
            convergence_achieved=True,
            iterations_completed=config.max_iterations,
            total_time=time.time() - start_time,
            total_tokens=total_tokens,
            dialogue_transcript=self._build_transcript(turns),
            insights=self._extract_roleplay_insights(turns)
        )
    
    def _check_socratic_convergence(
        self,
        turns: List[CollaborationTurn],
        config: CollaborationConfig
    ) -> bool:
        """Check if Socratic collaboration has converged."""
        if len(turns) < 4:
            return False
        
        # Compare last two Agent B responses for similarity
        b_responses = [t.response for t in turns if "Pragmatic" in t.reasoning]
        if len(b_responses) < 2:
            return False
        
        # Simple similarity check (could be enhanced)
        similarity = self._calculate_similarity(b_responses[-1], b_responses[-2])
        return similarity > config.convergence_threshold
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0-1)."""
        # Simple word overlap similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _build_transcript(self, turns: List[CollaborationTurn]) -> str:
        """Build readable dialogue transcript."""
        transcript = ""
        for turn in turns:
            transcript += f"\n{turn.agent_name} (Turn {turn.turn_number}):\n"
            transcript += f"{turn.response}\n"
        return transcript
    
    def _extract_socratic_insights(self, turns: List[CollaborationTurn]) -> Dict:
        """Extract insights from Socratic dialogue."""
        return {
            'refinement_count': len([t for t in turns if 'Refinement' in t.reasoning]),
            'critique_points': len([t for t in turns if 'Critique' in t.reasoning]),
            'total_turns': len(turns),
            'dialogue_quality': 'structured'
        }
    
    def _extract_roleplay_insights(self, turns: List[CollaborationTurn]) -> Dict:
        """Extract insights from Roleplay dialogue."""
        return {
            'character_responses': len([t for t in turns if 'In-Character' in t.reasoning]),
            'exploration_depth': len([t for t in turns if 'Exploration' in t.reasoning]),
            'total_turns': len(turns),
            'dialogue_quality': 'embodied'
        }
    
    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Not used - use execute_socratic or execute_roleplay directly."""
        raise NotImplementedError("Use execute_socratic or execute_roleplay")
    
    def parse_response(self, response: str) -> Any:
        """Not used."""
        raise NotImplementedError()

