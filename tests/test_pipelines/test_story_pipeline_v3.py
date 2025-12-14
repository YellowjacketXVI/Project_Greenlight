"""
Tests for Story Pipeline v3.0 - Prose-First Generation

Tests:
- Scene outline agent
- Prose agent
- Pipeline orchestration
- Validation
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from greenlight.agents.scene_outline_agent import SceneOutlineAgent, StoryOutline
from greenlight.agents.prose_agent import ProseAgent, ProseOrchestrator, ProseResult
from greenlight.context.agent_context_delivery import AgentContextDelivery, SceneOutline
from greenlight.context.context_compiler import ContextCompiler
from greenlight.context.thread_tracker import ThreadTracker
from greenlight.pipelines.story_pipeline_v3 import (
    StoryPipelineV3,
    StoryPipelineV3Config,
    StoryPipelineV3Output,
)


class TestSceneOutlineAgent:
    """Test scene outline agent."""
    
    @pytest.fixture
    def mock_llm_caller(self):
        """Create mock LLM caller."""
        async def caller(prompt, system_prompt, max_tokens):
            return """SCENE [1]:
LOCATION: LOC_TEMPLE
CHARACTERS: CHAR_HERO, CHAR_MENTOR
GOAL: Hero receives the quest
KEY MOMENT: Mentor reveals the prophecy
ENTRY STATES: CHAR_HERO: uncertain
EXIT STATES: CHAR_HERO: determined
TENSION: 4

SCENE [2]:
LOCATION: LOC_FOREST
CHARACTERS: CHAR_HERO
GOAL: Hero faces first challenge
KEY MOMENT: Discovery of hidden power
ENTRY STATES: CHAR_HERO: determined
EXIT STATES: CHAR_HERO: confident
TENSION: 6"""
        return caller
    
    @pytest.fixture
    def agent(self, mock_llm_caller):
        """Create test agent."""
        return SceneOutlineAgent(mock_llm_caller, num_scenes=2)
    
    @pytest.fixture
    def delivery(self):
        """Create test delivery."""
        compiler = ContextCompiler(
            world_config={
                "title": "Test",
                "logline": "A test story",
                "themes": "Testing",
                "characters": [],
                "locations": []
            },
            pitch="Test pitch"
        )
        return AgentContextDelivery(compiler=compiler, tracker=ThreadTracker())
    
    @pytest.mark.asyncio
    async def test_generate_outline(self, agent, delivery):
        """Test outline generation."""
        outline = await agent.generate_outline(
            delivery=delivery,
            winning_concept="A hero's journey",
            steal_list=["Lin's awareness"]
        )
        
        assert isinstance(outline, StoryOutline)
        assert len(outline.scenes) == 2
        assert outline.scenes[0].scene_number == 1
        assert outline.scenes[0].goal != ""


class TestProseAgent:
    """Test prose agent."""
    
    @pytest.fixture
    def mock_llm_caller(self):
        """Create mock LLM caller."""
        async def caller(prompt, system_prompt, max_tokens):
            return """The hero steps into the ancient temple, dust motes dancing in shafts of golden light. 
            Stone pillars rise around them, carved with symbols older than memory. The mentor waits 
            at the altar, robes flowing like water. Their eyes meet, and in that moment, everything changes.
            The prophecy unfolds in whispered words, each syllable heavy with destiny."""
        return caller
    
    @pytest.fixture
    def agent(self, mock_llm_caller):
        """Create test agent."""
        return ProseAgent(mock_llm_caller)
    
    @pytest.fixture
    def delivery(self):
        """Create test delivery."""
        compiler = ContextCompiler(
            world_config={
                "title": "Test",
                "logline": "A test story",
                "themes": "Testing",
                "characters": [],
                "locations": []
            },
            pitch="Test pitch"
        )
        return AgentContextDelivery(compiler=compiler, tracker=ThreadTracker())
    
    @pytest.fixture
    def sample_outline(self):
        """Create sample scene outline."""
        return SceneOutline(
            scene_number=1,
            location="LOC_TEMPLE",
            characters=["CHAR_HERO"],
            goal="Hero receives quest",
            key_moment="Prophecy revealed",
            tension=4
        )
    
    @pytest.mark.asyncio
    async def test_generate_scene(self, agent, delivery, sample_outline):
        """Test scene prose generation."""
        result = await agent.generate_scene(delivery, sample_outline, total_scenes=8)
        
        assert isinstance(result, ProseResult)
        assert result.scene_number == 1
        assert result.word_count > 0
        assert "temple" in result.prose.lower()


class TestProseOrchestrator:
    """Test prose orchestrator."""
    
    @pytest.fixture
    def mock_llm_caller(self):
        """Create mock LLM caller."""
        call_count = 0
        async def caller(prompt, system_prompt, max_tokens):
            nonlocal call_count
            call_count += 1
            return f"Scene {call_count} prose. The hero continues their journey through the land."
        return caller
    
    @pytest.fixture
    def orchestrator(self, mock_llm_caller):
        """Create test orchestrator."""
        return ProseOrchestrator(mock_llm_caller)
    
    @pytest.fixture
    def delivery(self):
        """Create test delivery."""
        compiler = ContextCompiler(
            world_config={"title": "Test", "logline": "Test", "themes": "Test", "characters": [], "locations": []},
            pitch="Test"
        )
        return AgentContextDelivery(compiler=compiler, tracker=ThreadTracker())
    
    @pytest.fixture
    def sample_outlines(self):
        """Create sample outlines."""
        return [
            SceneOutline(scene_number=i, location="LOC_TEST", characters=["CHAR_HERO"],
                        goal=f"Goal {i}", key_moment=f"Moment {i}", tension=5)
            for i in range(1, 4)
        ]
    
    @pytest.mark.asyncio
    async def test_generate_all_scenes(self, orchestrator, delivery, sample_outlines):
        """Test generating all scenes."""
        results = await orchestrator.generate_all_scenes(delivery, sample_outlines)
        
        assert len(results) == 3
        assert all(isinstance(r, ProseResult) for r in results)
    
    def test_compile_script(self, orchestrator):
        """Test script compilation."""
        results = [
            ProseResult(scene_number=1, prose="Scene 1 prose.", word_count=3, exit_states={}, new_threads=[], resolved_threads=[], new_setups=[]),
            ProseResult(scene_number=2, prose="Scene 2 prose.", word_count=3, exit_states={}, new_threads=[], resolved_threads=[], new_setups=[]),
        ]
        
        script = orchestrator.compile_script(results)
        
        assert "# Script" in script
        assert "## Scene 1" in script
        assert "## Scene 2" in script

