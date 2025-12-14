"""
Story Pipeline v2 - Assembly-Based Story Building Engine

Uses the Assembly Pattern for story generation:
- Layer 1: 7 Story Outline Agents (Parallel)
- Layer 2: 7 Character Architecture Agents (Parallel)
- Layer 3: 5 Judges Rank All Elements
- Layer 4: Calculator + Synthesizer + Continuity Loop

Output: Script_v1 (fully written story within word cap)
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from greenlight.pipelines.base_pipeline import BasePipeline, PipelineStep, PipelineResult
from greenlight.patterns.assembly import (
    AssemblyPattern, AssemblyConfig, Proposal, JudgeRanking,
    ProposalAgent, JudgeAgent, ContinuityValidator, ContinuityCheckResult
)
from greenlight.agents.assembly_agents import (
    AssemblyCalculatorAgent, AssemblySynthesizerAgent
)
from greenlight.config.word_caps import WORD_CAPS, get_word_cap

logger = get_logger("pipelines.story_v2")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class StoryPipelineInput:
    """Input for Story Pipeline v2."""
    pitch_text: str
    world_config: Dict[str, Any]  # From World Bible Pipeline
    validated_tags: Dict[str, List[str]]
    media_type: str = "standard"
    genre: str = ""
    title: str = ""
    visual_style: str = "live_action"
    style_notes: str = ""


@dataclass
class ScriptOutput:
    """Output from Story Pipeline - Script (scripts/script.md)."""
    title: str
    genre: str
    media_type: str
    word_count: int

    # Story structure
    act_structure: Dict[int, List[str]] = field(default_factory=dict)
    plot_points: List[Dict[str, Any]] = field(default_factory=list)
    scenes: List[Dict[str, Any]] = field(default_factory=list)

    # Character work
    character_arcs: List[Dict[str, Any]] = field(default_factory=list)

    # Full script content
    script_content: str = ""

    # Metadata
    synthesis_sources: List[str] = field(default_factory=list)
    continuity_passed: bool = False
    iterations_used: int = 0


# =============================================================================
# STORY OUTLINE PROPOSAL AGENTS
# =============================================================================

class StoryOutlineAgent(ProposalAgent):
    """
    Story Outline Proposal Agent.
    
    7 agents with different perspectives:
    1. Plot-focused
    2. Character-focused
    3. Theme-focused
    4. Pacing-focused
    5. Visual-focused
    6. Emotional-focused
    7. Structure-focused
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
        """Generate a story outline proposal."""
        constraints = constraints or {}
        word_cap = constraints.get("word_cap", get_word_cap("standard"))
        
        # Format world config for prompt
        world_config = context.get("world_config", {})
        characters = world_config.get("characters", [])
        locations = world_config.get("locations", [])
        props = world_config.get("props", [])
        
        char_summary = "\n".join([
            f"- [{c.get('tag', '')}]: {c.get('name', '')} - {c.get('role', '')}"
            for c in characters
        ])
        loc_summary = "\n".join([
            f"- [{l.get('tag', '')}]: {l.get('name', '')}"
            for l in locations
        ])
        prop_summary = "\n".join([
            f"- [{p.get('tag', '')}]: {p.get('name', '')}"
            for p in props
        ])
        
        prompt = f"""Create a complete story outline for this pitch.

PITCH:
{context.get('pitch_text', '')}

AVAILABLE CHARACTERS:
{char_summary}

AVAILABLE LOCATIONS:
{loc_summary}

AVAILABLE PROPS:
{prop_summary}

MEDIA TYPE: {context.get('media_type', 'standard')}
WORD CAP: {word_cap.get('min', 750)}-{word_cap.get('max', 1000)} words
TARGET SCENES: {word_cap.get('scenes', 8)}

YOUR PERSPECTIVE: {self.perspective_prompt}

Create a story outline including:

1. THREE-ACT STRUCTURE
   - Act 1 (Setup, ~25%): World, characters, inciting incident
   - Act 2 (Confrontation, ~50%): Rising action, midpoint, complications
   - Act 3 (Resolution, ~25%): Climax, falling action, resolution

2. KEY PLOT POINTS (with position 0.0-1.0):
   - Opening Image (0.0)
   - Inciting Incident (~0.12)
   - First Plot Point (~0.25)
   - Midpoint (~0.50)
   - Second Plot Point (~0.75)
   - Climax (~0.90)
   - Resolution (~1.0)

3. SCENE BREAKDOWN
   For each scene:
   - Scene number and title
   - Location tag
   - Characters present
   - Scene purpose
   - Key beats (3-5 per scene)

Output as structured JSON."""
        
        response = await self.llm_caller(
            prompt=prompt,
            system_prompt=f"You are a story architect with a {self.perspective} perspective. {self.perspective_prompt}",
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


# =============================================================================
# CHARACTER ARCHITECTURE PROPOSAL AGENTS
# =============================================================================

class CharacterArchitectureAgent(ProposalAgent):
    """
    Character Architecture Proposal Agent.

    7 agents with different perspectives on character development.
    """

    PERSPECTIVES = {
        "psychology": "Focus on psychological depth and internal conflicts.",
        "relationships": "Focus on character relationships and dynamics.",
        "arc": "Focus on character transformation and growth.",
        "motivation": "Focus on wants, needs, and driving forces.",
        "backstory": "Focus on history and formative experiences.",
        "voice": "Focus on dialogue patterns and unique expression.",
        "behavior": "Focus on physical behavior and decision patterns."
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
        """Generate character architecture proposal."""
        story_outlines = context.get("story_outlines", [])
        world_config = context.get("world_config", {})
        characters = world_config.get("characters", [])

        # Format story outlines
        outlines_text = "\n\n".join([
            f"=== OUTLINE {i+1} ===\n{outline}"
            for i, outline in enumerate(story_outlines)
        ])

        # Format characters with enhanced schema
        chars_text = json.dumps(characters, indent=2)

        prompt = f"""Refine the character architecture for these story proposals.

STORY OUTLINES:
{outlines_text}

CHARACTERS (with enhanced schema):
{chars_text}

YOUR PERSPECTIVE: {self.perspective_prompt}

For each major character, provide:

1. ARC REFINEMENT
   - Starting emotional state
   - Key turning points
   - Ending emotional state
   - Growth or regression demonstrated

2. RELATIONSHIP DYNAMICS
   - Key relationships and their evolution
   - Power dynamics between characters
   - Unspoken tensions

3. KEY CHARACTER MOMENTS
   - 3-5 moments that define this character
   - How these moments reveal internal voice
   - Physical behavior in these moments

4. INTERNAL VOICE APPLICATION
   - What are they thinking at key plot points?
   - What are they hiding?
   - What blind spots affect their decisions?

5. DECISION HEURISTIC APPLICATION
   - What values drive their choices?
   - Where do they act against type? Why?

Output as structured JSON."""

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
# STORY JUDGES
# =============================================================================

class StoryJudgeAgent(JudgeAgent):
    """
    Judge agent for story proposals.

    5 Judges:
    - Narrative Coherence
    - Character Authenticity
    - Emotional Impact
    - Thematic Resonance
    - Pacing & Structure
    """

    CRITERIA = {
        "narrative": "Evaluate narrative logic, cause-and-effect, and story flow.",
        "character": "Evaluate character authenticity, motivation clarity, and arc strength.",
        "emotional": "Evaluate emotional impact, audience engagement, and catharsis.",
        "thematic": "Evaluate thematic resonance, symbolic depth, and meaning.",
        "pacing": "Evaluate pacing, rhythm, tension management, and structure."
    }

    def __init__(self, judge_id: str, criterion: str, llm_caller: Callable):
        super().__init__(judge_id, criterion)
        self.llm_caller = llm_caller
        self.criterion_description = self.CRITERIA.get(criterion, "")

    async def rank_proposals(
        self,
        proposals: List[Proposal],
        context: Dict[str, Any]
    ) -> JudgeRanking:
        """Rank story proposals."""
        proposals_text = "\n\n".join([
            f"=== PROPOSAL {p.agent_id} ({p.metadata.get('perspective', '')}) ===\n{p.content}"
            for p in proposals
        ])

        prompt = f"""Judge these story proposals on: {self.criterion}

{self.criterion_description}

PROPOSALS:
{proposals_text}

PITCH CONTEXT:
{context.get('pitch_text', '')}

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
            return JudgeRanking(
                judge_id=self.judge_id,
                criterion=self.criterion,
                rankings=[p.agent_id for p in proposals],
                scores={p.agent_id: 5.0 for p in proposals}
            )

