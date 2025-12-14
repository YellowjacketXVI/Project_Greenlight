"""
Greenlight Scene Outline Agent - Story Pipeline v3.0

Creates scene-level outlines with goals and character states.
NO beat breakdown - just high-level scene structure.

The outline agent:
1. Takes winning concept + steal list
2. Generates scene outlines with:
   - Scene goal (what must happen)
   - Key moment (the memorable image/beat)
   - Character entry/exit states
   - Location and tension level
3. Outputs SceneOutline objects for prose agents

This is the "what" not the "how" - prose agents discover the beats.
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

from greenlight.core.logging_config import get_logger
from greenlight.context.agent_context_delivery import AgentContextDelivery, SceneOutline

logger = get_logger("agents.scene_outline")


@dataclass
class StoryOutline:
    """Complete story outline with all scenes."""
    scenes: List[SceneOutline]
    total_scenes: int
    winning_concept: str
    steal_list: List[str]
    
    def get_scene(self, scene_number: int) -> Optional[SceneOutline]:
        """Get scene by number (1-indexed)."""
        for scene in self.scenes:
            if scene.scene_number == scene_number:
                return scene
        return None


class SceneOutlineAgent:
    """
    Agent that creates scene-level outlines from a winning concept.
    
    Key principle: Outlines define WHAT happens, not HOW.
    The prose agent discovers the beats organically.
    """
    
    SYSTEM_PROMPT = """You are a story architect. You create scene-level outlines that define:
- What must happen in each scene (the goal)
- The key memorable moment (the image that sticks)
- How characters enter and exit emotionally
- The tension level (1-10)

You do NOT specify:
- Dialogue
- Specific beats or actions
- How the scene unfolds

Let the writer discover the journey. You define the destination."""
    
    def __init__(self, llm_caller: Callable, num_scenes: int = 8):
        self.llm_caller = llm_caller
        self.num_scenes = num_scenes
    
    async def generate_outline(
        self,
        delivery: AgentContextDelivery,
        winning_concept: str,
        steal_list: List[str]
    ) -> StoryOutline:
        """
        Generate complete story outline.
        
        Args:
            delivery: AgentContextDelivery with compressed context
            winning_concept: The winning story concept
            steal_list: Elements that must be incorporated
            
        Returns:
            StoryOutline with all scenes
        """
        context_text = delivery.for_outline_agent(winning_concept, steal_list)
        
        steal_text = "\n".join(f"- {item}" for item in steal_list) if steal_list else "None"
        
        prompt = f"""{context_text}

Generate a {self.num_scenes}-scene outline. For each scene, provide:

SCENE [N]:
LOCATION: [location tag]
CHARACTERS: [character tags, comma-separated]
GOAL: [what must happen - one sentence]
KEY MOMENT: [the memorable image/beat - one sentence]
ENTRY STATES: [character: emotional state, ...]
EXIT STATES: [character: emotional state, ...]
TENSION: [1-10]

STEAL LIST ITEMS TO INCORPORATE:
{steal_text}

Distribute steal list items across scenes naturally. Each item should appear in at least one scene.

Output {self.num_scenes} scenes in order."""

        try:
            response = await self.llm_caller(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=2000
            )
            
            scenes = self._parse_outline(response, steal_list)
            
            return StoryOutline(
                scenes=scenes,
                total_scenes=len(scenes),
                winning_concept=winning_concept,
                steal_list=steal_list
            )
        except Exception as e:
            logger.error(f"Scene outline generation failed: {e}")
            # Return minimal outline on error
            return StoryOutline(
                scenes=[],
                total_scenes=0,
                winning_concept=winning_concept,
                steal_list=steal_list
            )
    
    def _parse_outline(
        self,
        response: str,
        steal_list: List[str]
    ) -> List[SceneOutline]:
        """Parse LLM response into SceneOutline objects."""
        scenes = []
        
        # Split by scene markers
        scene_pattern = r'SCENE\s*\[?(\d+)\]?:?(.*?)(?=SCENE\s*\[?\d+\]?:|$)'
        matches = re.findall(scene_pattern, response, re.DOTALL | re.IGNORECASE)
        
        for scene_num_str, scene_text in matches:
            scene_num = int(scene_num_str)
            
            # Parse fields
            location = self._extract_field(scene_text, "LOCATION")
            characters = self._extract_list(scene_text, "CHARACTERS")
            goal = self._extract_field(scene_text, "GOAL")
            key_moment = self._extract_field(scene_text, "KEY MOMENT")
            entry_states = self._extract_states(scene_text, "ENTRY STATES")
            exit_states = self._extract_states(scene_text, "EXIT STATES")
            tension = self._extract_int(scene_text, "TENSION", default=5)

            # Determine which steal elements apply to this scene
            scene_steals = []
            scene_text_lower = scene_text.lower()
            for steal in steal_list:
                if any(word in scene_text_lower for word in steal.lower().split() if len(word) > 3):
                    scene_steals.append(steal)

            scenes.append(SceneOutline(
                scene_number=scene_num,
                location=location,
                characters=characters,
                goal=goal,
                key_moment=key_moment,
                entry_states=entry_states,
                exit_states=exit_states,
                tension=tension,
                steal_elements=scene_steals
            ))

        return scenes

    def _extract_field(self, text: str, field_name: str) -> str:
        """Extract a single field value."""
        pattern = rf'{field_name}:\s*(.+?)(?=\n[A-Z]|\n\n|$)'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_list(self, text: str, field_name: str) -> List[str]:
        """Extract a comma-separated list."""
        value = self._extract_field(text, field_name)
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]

    def _extract_states(self, text: str, field_name: str) -> Dict[str, str]:
        """Extract character states as dict."""
        value = self._extract_field(text, field_name)
        if not value:
            return {}

        states = {}
        # Parse "CHAR: state, CHAR2: state2" format
        pairs = re.findall(r'(\w+):\s*([^,]+)', value)
        for char, state in pairs:
            states[char.strip()] = state.strip()
        return states

    def _extract_int(self, text: str, field_name: str, default: int = 0) -> int:
        """Extract an integer field."""
        value = self._extract_field(text, field_name)
        try:
            return int(re.search(r'\d+', value).group())
        except (AttributeError, ValueError):
            return default
