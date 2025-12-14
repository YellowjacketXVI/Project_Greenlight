"""
Tests for AgentContextDelivery - Story Pipeline v3.0 agent context preparation.

Tests:
- Brainstorm agent context (~200 words)
- Judge agent context (~1100 words for 5 concepts)
- Outline agent context (~350 words)
- Prose agent context (~260 words)
- Token estimation
"""

import pytest
from greenlight.context.context_compiler import ContextCompiler
from greenlight.context.thread_tracker import ThreadTracker
from greenlight.context.agent_context_delivery import (
    AgentContextDelivery,
    SceneOutline,
)


class TestSceneOutline:
    """Test SceneOutline dataclass."""
    
    def test_to_context(self):
        """Test scene outline context generation."""
        outline = SceneOutline(
            scene_number=1,
            location="LOC_TEMPLE",
            characters=["CHAR_HERO", "CHAR_MENTOR"],
            goal="Hero receives the quest",
            key_moment="Mentor reveals the prophecy",
            entry_states={"CHAR_HERO": "uncertain"},
            exit_states={"CHAR_HERO": "determined"},
            tension=4,
            steal_elements=["Lin's silent awareness"]
        )
        
        context = outline.to_context()
        
        assert "SCENE 1:" in context
        assert "LOC_TEMPLE" in context
        assert "CHAR_HERO" in context
        assert "Hero receives the quest" in context
        assert "TENSION: 4/10" in context
        assert "MUST INCLUDE:" in context


class TestAgentContextDelivery:
    """Test AgentContextDelivery class."""
    
    @pytest.fixture
    def sample_compiler(self):
        """Create a sample compiler."""
        world_config = {
            "title": "Test Story",
            "logline": "A hero's journey through darkness.",
            "themes": "Redemption, Hope",
            "visual_style": "cinematic",
            "vibe": "epic, emotional",
            "characters": [
                {
                    "tag": "CHAR_HERO",
                    "name": "Alex",
                    "role": "protagonist",
                    "backstory": "A former soldier."
                }
            ],
            "locations": [
                {
                    "tag": "LOC_TEMPLE",
                    "name": "Ancient Temple",
                    "description": "A sacred place."
                }
            ]
        }
        return ContextCompiler(world_config=world_config, pitch="Test pitch")
    
    @pytest.fixture
    def delivery(self, sample_compiler):
        """Create delivery instance."""
        return AgentContextDelivery(
            compiler=sample_compiler,
            tracker=ThreadTracker()
        )
    
    def test_for_brainstorm_agent(self, delivery):
        """Test brainstorm agent context."""
        context = delivery.for_brainstorm_agent(
            philosophy="Character-first",
            focus="internal transformation"
        )
        
        assert "STORY SEED" in context
        assert "CHARACTERS" in context
        assert "Character-first" in context
        assert "internal transformation" in context
        
        # Should be ~200 words
        word_count = len(context.split())
        assert word_count < 300
    
    def test_for_judge_agent(self, delivery):
        """Test judge agent context."""
        concepts = [
            "Concept A: A story about redemption.",
            "Concept B: A story about sacrifice.",
            "Concept C: A story about hope."
        ]
        
        context = delivery.for_judge_agent(concepts)
        
        assert "STORY SEED" in context
        assert "CONCEPT A" in context
        assert "CONCEPT B" in context
        assert "JUDGING CRITERIA" in context
        assert "STEAL" in context
    
    def test_for_outline_agent(self, delivery):
        """Test outline agent context."""
        context = delivery.for_outline_agent(
            winning_concept="A hero's journey to redemption.",
            steal_list=["Lin's silent awareness", "Orchid symbolism"]
        )
        
        assert "STORY SEED" in context
        assert "WINNING CONCEPT" in context
        assert "MUST INCLUDE" in context
        assert "Lin's silent awareness" in context
        assert "CHARACTERS" in context
        assert "LOCATIONS" in context
    
    def test_for_prose_agent(self, delivery):
        """Test prose agent context."""
        outline = SceneOutline(
            scene_number=1,
            location="LOC_TEMPLE",
            characters=["CHAR_HERO"],
            goal="Hero arrives at temple",
            key_moment="First glimpse of the artifact",
            tension=3
        )
        
        context = delivery.for_prose_agent(outline, total_scenes=8)
        
        assert "STORY SEED" in context
        assert "SCENE CONTEXT" in context
        assert "SCENE GOAL" in context
        assert "Write scene 1 of 8" in context
        assert "150-250 words" in context
        
        # Should be ~260 words
        word_count = len(context.split())
        assert word_count < 400
    
    def test_for_prose_agent_with_tracker(self, delivery):
        """Test prose agent context includes tracker."""
        delivery.tracker.add_thread("test thread")
        delivery.tracker.tension_level = 7
        
        outline = SceneOutline(
            scene_number=2,
            location="LOC_TEMPLE",
            characters=["CHAR_HERO"],
            goal="Continue journey",
            key_moment="Discovery",
            tension=5
        )
        
        context = delivery.for_prose_agent(outline, total_scenes=8)
        
        assert "CONTINUITY" in context
        assert "THREADS:" in context
    
    def test_estimate_total_tokens(self, delivery):
        """Test token estimation."""
        estimates = delivery.estimate_total_tokens(
            num_scenes=8,
            num_concepts=5,
            num_judges=3
        )
        
        assert "phase_1_brainstorm" in estimates
        assert "phase_4_prose" in estimates
        assert "total" in estimates
        assert estimates["total"] < 50000  # Should be compressed

