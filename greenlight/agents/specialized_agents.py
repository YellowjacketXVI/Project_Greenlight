"""
Greenlight Specialized Agents

Concrete implementations of agents for specific tasks:
- Tag Validation Agents (5 perspectives)
- Story Building Agents
- Director Pipeline Agents
- Quality Check Agents
"""

from typing import Any, Dict, List, Optional
import json

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from .base_agent import BaseAgent, AgentConfig, AgentResponse
from .prompts import AgentPromptLibrary

logger = get_logger("agents.specialized")


class TagValidationAgent(BaseAgent):
    """
    Agent for tag validation with a specific perspective.
    
    Perspectives:
    - story_critical: Story-impacting elements
    - landmark_locations: Significant locations
    - character_defining: Character identity elements
    - world_building: World rules and culture
    - visual_anchors: Recurring visual elements
    """
    
    PERSPECTIVES = [
        "story_critical",
        "landmark_locations", 
        "character_defining",
        "world_building",
        "visual_anchors"
    ]
    
    def __init__(self, perspective: str, llm_caller=None):
        if perspective not in self.PERSPECTIVES:
            raise ValueError(f"Invalid perspective: {perspective}. Must be one of {self.PERSPECTIVES}")
        
        prompts = AgentPromptLibrary.get_tag_validation_prompts()
        
        config = AgentConfig(
            name=f"TagValidator_{perspective}",
            description=f"Tag validation agent with {perspective} perspective",
            llm_function=LLMFunction.TAG_VALIDATION,
            system_prompt=f"You are a tag extraction specialist focusing on {perspective.replace('_', ' ')} elements."
        )
        
        super().__init__(config, llm_caller)
        self.perspective = perspective
        self.prompt_template = prompts[perspective]
    
    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Execute tag extraction for the given text."""
        source_text = input_data.get('text', '')
        
        prompt = AgentPromptLibrary.render(
            self.prompt_template,
            source_text=source_text
        )
        
        try:
            response = await self.call_llm(prompt)
            tags = self.parse_response(response)
            
            return AgentResponse.success_response(
                content={'tags': tags, 'perspective': self.perspective},
                raw_response=response
            )
        except Exception as e:
            logger.error(f"Tag validation failed: {e}")
            return AgentResponse.error_response(str(e))
    
    def parse_response(self, response: str) -> List[str]:
        """Parse tags from LLM response."""
        import re
        tag_pattern = r'\[([A-Z][A-Z0-9_]*)\]'
        return list(set(re.findall(tag_pattern, response)))


class StoryBuildingAgent(BaseAgent):
    """
    Agent for story building tasks.
    
    Tasks:
    - pitch_analysis: Analyze pitch and extract narrative elements
    - prose_generation: Generate prose for story sequences
    """
    
    TASKS = ["pitch_analysis", "prose_generation"]
    
    def __init__(self, task: str, llm_caller=None):
        if task not in self.TASKS:
            raise ValueError(f"Invalid task: {task}. Must be one of {self.TASKS}")
        
        prompts = AgentPromptLibrary.get_story_prompts()
        
        config = AgentConfig(
            name=f"StoryBuilder_{task}",
            description=f"Story building agent for {task}",
            llm_function=LLMFunction.STORY_GENERATION,
            system_prompt="You are a master storyteller crafting compelling narratives."
        )
        
        super().__init__(config, llm_caller)
        self.task = task
        self.prompt_template = prompts[task]
    
    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Execute story building task."""
        try:
            prompt = AgentPromptLibrary.render(self.prompt_template, **input_data)
            response = await self.call_llm(prompt)
            parsed = self.parse_response(response)
            
            return AgentResponse.success_response(
                content=parsed,
                raw_response=response
            )
        except Exception as e:
            logger.error(f"Story building failed: {e}")
            return AgentResponse.error_response(str(e))
    
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse story building response."""
        if self.task == "pitch_analysis":
            try:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
            return {'raw_analysis': response}
        else:
            return {'prose': response}


class DirectorAgent(BaseAgent):
    """
    Agent for director pipeline tasks.

    Tasks:
    - frame_composer: Break scenes into visual frames
    - camera_evaluator: Evaluate camera shot options
    - shot_director: Craft detailed cinematic direction
    """

    TASKS = ["frame_composer", "camera_evaluator", "shot_director"]

    def __init__(self, task: str, llm_caller=None):
        if task not in self.TASKS:
            raise ValueError(f"Invalid task: {task}. Must be one of {self.TASKS}")

        prompts = AgentPromptLibrary.get_director_prompts()

        config = AgentConfig(
            name=f"Director_{task}",
            description=f"Director agent for {task}",
            llm_function=LLMFunction.DIRECTOR,
            system_prompt="You are an expert film director with deep knowledge of cinematography."
        )

        super().__init__(config, llm_caller)
        self.task = task
        self.prompt_template = prompts[task]

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Execute director task."""
        try:
            prompt = AgentPromptLibrary.render(self.prompt_template, **input_data)
            response = await self.call_llm(prompt)
            parsed = self.parse_response(response)

            return AgentResponse.success_response(
                content=parsed,
                raw_response=response
            )
        except Exception as e:
            logger.error(f"Director task failed: {e}")
            return AgentResponse.error_response(str(e))

    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse director response (expects JSON)."""
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return {'raw_response': response}


class LocationViewAgent(BaseAgent):
    """
    Agent for generating location directional views.

    Directions: north, east, south, west
    """

    DIRECTIONS = ["north", "east", "south", "west"]

    def __init__(self, direction: str, llm_caller=None):
        if direction not in self.DIRECTIONS:
            raise ValueError(f"Invalid direction: {direction}. Must be one of {self.DIRECTIONS}")

        prompts = AgentPromptLibrary.get_location_prompts()

        config = AgentConfig(
            name=f"LocationView_{direction}",
            description=f"Location view generator for {direction} direction",
            llm_function=LLMFunction.STORY_GENERATION,
            system_prompt="You are a world-building expert creating consistent location descriptions."
        )

        super().__init__(config, llm_caller)
        self.direction = direction
        self.prompt_template = prompts[direction]

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Generate location view for the specified direction."""
        try:
            prompt = AgentPromptLibrary.render(self.prompt_template, **input_data)
            response = await self.call_llm(prompt)

            return AgentResponse.success_response(
                content={'direction': self.direction, 'description': response.strip()},
                raw_response=response
            )
        except Exception as e:
            logger.error(f"Location view generation failed: {e}")
            return AgentResponse.error_response(str(e))

    def parse_response(self, response: str) -> str:
        """Parse location view response."""
        return response.strip()


class TagClassificationAgent(BaseAgent):
    """Agent for classifying tags into categories."""

    def __init__(self, llm_caller=None):
        prompts = AgentPromptLibrary.get_tag_validation_prompts()

        config = AgentConfig(
            name="TagClassifier",
            description="Classifies tags into categories",
            llm_function=LLMFunction.TAG_VALIDATION,
            system_prompt="You are a tag classification specialist."
        )

        super().__init__(config, llm_caller)
        self.prompt_template = prompts["classification"]

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Classify a tag into a category."""
        tag_name = input_data.get('tag_name', '')

        prompt = AgentPromptLibrary.render(
            self.prompt_template,
            tag_name=tag_name
        )

        try:
            response = await self.call_llm(prompt)
            category = self.parse_response(response)

            return AgentResponse.success_response(
                content={'tag': tag_name, 'category': category},
                raw_response=response
            )
        except Exception as e:
            logger.error(f"Tag classification failed: {e}")
            return AgentResponse.error_response(str(e))

    def parse_response(self, response: str) -> str:
        """Parse category from response."""
        response = response.strip().upper()
        valid_categories = ["CHARACTER", "LOCATION", "PROP", "CONCEPT", "EVENT"]
        for cat in valid_categories:
            if cat in response:
                return cat
        return "UNKNOWN"

