"""
Greenlight Prose Agent - Story Pipeline v3.0

Generates organic prose for each scene (150-250 words).

The prose agent:
1. Receives scene outline (goal, key moment, states)
2. Receives ThreadTracker context for continuity
3. Writes pure prose - NO beat markers, NO technical notation
4. Discovers the beats naturally through writing
5. Updates ThreadTracker after generation

Key principle: The writer discovers the story through writing.
Beats are extracted AFTER prose generation, not before.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

from greenlight.core.logging_config import get_logger
from greenlight.context.agent_context_delivery import AgentContextDelivery, SceneOutline
from greenlight.context.thread_tracker import ThreadTracker

logger = get_logger("agents.prose")


@dataclass
class ProseResult:
    """Result from prose generation."""
    scene_number: int
    prose: str
    word_count: int
    exit_states: Dict[str, str]
    new_threads: List[str]
    resolved_threads: List[str]
    new_setups: List[str]
    
    @property
    def is_valid(self) -> bool:
        """Check if prose meets word count requirements."""
        return 100 <= self.word_count <= 300


class ProseAgent:
    """
    Agent that generates organic prose for a single scene.
    
    Key principles:
    - Write pure prose, no markers
    - Discover beats through writing
    - Maintain continuity via ThreadTracker
    - 150-250 words per scene
    """
    
    SYSTEM_PROMPT = """You are a prose writer. You write vivid, emotionally resonant scenes.

Your writing:
- Uses present tense, active voice
- Shows rather than tells
- Creates sensory, visceral moments
- Flows naturally without markers or labels
- Captures character interiority

You do NOT:
- Use beat markers or technical notation
- Write dialogue tags like "he said angrily"
- Explain emotions - show them through action
- Break the fourth wall

Write the scene as pure prose. Let the story breathe."""

    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller
    
    async def generate_scene(
        self,
        delivery: AgentContextDelivery,
        outline: SceneOutline,
        total_scenes: int
    ) -> ProseResult:
        """
        Generate prose for a single scene.
        
        Args:
            delivery: AgentContextDelivery with compressed context
            outline: SceneOutline with goal, key moment, states
            total_scenes: Total number of scenes in story
            
        Returns:
            ProseResult with prose and metadata
        """
        context_text = delivery.for_prose_agent(outline, total_scenes)
        
        prompt = f"""{context_text}

Write scene {outline.scene_number} of {total_scenes}.

REQUIREMENTS:
- 150-250 words of pure prose
- No beat markers or technical notation
- Present tense, active voice
- Show the key moment: "{outline.key_moment}"
- Move characters from entry to exit states
- Incorporate any steal elements naturally

Write the scene now:"""

        try:
            response = await self.llm_caller(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=600
            )
            
            prose = self._clean_prose(response)
            word_count = len(prose.split())
            
            # Extract any new threads or setups from the prose
            new_threads, resolved, new_setups = self._analyze_prose(prose, outline)
            
            return ProseResult(
                scene_number=outline.scene_number,
                prose=prose,
                word_count=word_count,
                exit_states=outline.exit_states,
                new_threads=new_threads,
                resolved_threads=resolved,
                new_setups=new_setups
            )
        except Exception as e:
            logger.error(f"Prose generation failed for scene {outline.scene_number}: {e}")
            return ProseResult(
                scene_number=outline.scene_number,
                prose=f"[ERROR: {str(e)}]",
                word_count=0,
                exit_states={},
                new_threads=[],
                resolved_threads=[],
                new_setups=[]
            )
    
    def _clean_prose(self, response: str) -> str:
        """Clean up LLM response to pure prose."""
        # Remove any markdown or formatting
        prose = response.strip()
        
        # Remove common prefixes
        prefixes = ["Scene:", "SCENE:", "Here is", "Here's"]
        for prefix in prefixes:
            if prose.startswith(prefix):
                prose = prose[len(prefix):].strip()
        
        return prose
    
    def _analyze_prose(
        self,
        prose: str,
        outline: SceneOutline
    ) -> tuple[List[str], List[str], List[str]]:
        """Analyze prose for threads and setups."""
        # This is a simplified analysis - could be enhanced with LLM
        new_threads = []
        resolved = []
        new_setups = []
        
        # Check if steal elements were incorporated (potential setups)
        for steal in outline.steal_elements:
            key_words = [w for w in steal.lower().split() if len(w) > 3]
            if any(w in prose.lower() for w in key_words):
                new_setups.append(f"Setup from steal: {steal}")
        
        return new_threads, resolved, new_setups


class ProseOrchestrator:
    """
    Orchestrates prose generation for all scenes.

    Generates scenes sequentially to maintain continuity via ThreadTracker.
    """

    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller
        self.agent = ProseAgent(llm_caller)

    async def generate_all_scenes(
        self,
        delivery: AgentContextDelivery,
        outlines: List[SceneOutline]
    ) -> List[ProseResult]:
        """
        Generate prose for all scenes sequentially.

        Args:
            delivery: AgentContextDelivery with compressed context
            outlines: List of SceneOutline objects

        Returns:
            List of ProseResult objects
        """
        results = []
        total_scenes = len(outlines)

        for outline in outlines:
            logger.info(f"Generating prose for scene {outline.scene_number}/{total_scenes}")

            result = await self.agent.generate_scene(delivery, outline, total_scenes)
            results.append(result)

            # Update tracker for next scene
            delivery.tracker.update_from_scene(
                prose=result.prose,
                exit_states=result.exit_states,
                new_tension=outline.tension
            )

            # Add any new threads/setups
            for thread in result.new_threads:
                delivery.tracker.add_thread(thread)
            for setup in result.new_setups:
                delivery.tracker.add_setup(setup)
            for resolved in result.resolved_threads:
                delivery.tracker.resolve_thread(resolved)

        logger.info(f"Generated {len(results)} scenes, total words: {sum(r.word_count for r in results)}")
        return results

    def compile_script(self, results: List[ProseResult]) -> str:
        """
        Compile all prose results into a single script.

        Args:
            results: List of ProseResult objects

        Returns:
            Complete script as markdown
        """
        lines = ["# Script\n"]

        for result in results:
            lines.append(f"## Scene {result.scene_number}\n")
            lines.append(result.prose)
            lines.append("\n---\n")

        return "\n".join(lines)
