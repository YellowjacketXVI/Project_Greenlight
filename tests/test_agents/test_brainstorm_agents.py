"""
Tests for Brainstorm Agents - Story Pipeline v3.0

Tests:
- Philosophy configurations
- Agent initialization
- Proposal generation
- Orchestrator parallel execution
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from greenlight.agents.brainstorm_agents import (
    BrainstormAgent,
    BrainstormOrchestrator,
    BrainstormPhilosophy,
    BrainstormPhilosophyConfig,
    PHILOSOPHY_CONFIGS,
)
from greenlight.patterns.assembly import Proposal


class TestPhilosophyConfigs:
    """Test philosophy configurations."""
    
    def test_all_philosophies_have_configs(self):
        """All philosophies should have configurations."""
        for philosophy in BrainstormPhilosophy:
            assert philosophy in PHILOSOPHY_CONFIGS
    
    def test_config_structure(self):
        """Configs should have required fields."""
        for philosophy, config in PHILOSOPHY_CONFIGS.items():
            assert config.name != ""
            assert config.focus != ""
            assert config.system_prompt != ""
            assert len(config.key_questions) >= 2


class TestBrainstormAgent:
    """Test individual brainstorm agent."""
    
    @pytest.fixture
    def mock_llm_caller(self):
        """Create mock LLM caller."""
        async def caller(prompt, system_prompt, max_tokens):
            return "A compelling story about transformation and growth."
        return caller
    
    @pytest.fixture
    def agent(self, mock_llm_caller):
        """Create test agent."""
        return BrainstormAgent(
            philosophy=BrainstormPhilosophy.CHARACTER_FIRST,
            llm_caller=mock_llm_caller
        )
    
    def test_agent_initialization(self, agent):
        """Test agent initializes correctly."""
        assert agent.philosophy == BrainstormPhilosophy.CHARACTER_FIRST
        assert agent.agent_id == "brainstorm_character_first"
        assert agent.config.name == "Character-first"
    
    @pytest.mark.asyncio
    async def test_generate_proposal(self, agent):
        """Test proposal generation."""
        context = {"context_text": "Test story seed about a hero."}
        
        proposal = await agent.generate_proposal(context)
        
        assert isinstance(proposal, Proposal)
        assert proposal.agent_id == "brainstorm_character_first"
        assert proposal.content != ""
        assert proposal.metadata["philosophy"] == "character_first"
    
    @pytest.mark.asyncio
    async def test_generate_proposal_with_delivery(self, mock_llm_caller):
        """Test proposal generation with AgentContextDelivery."""
        from greenlight.context.context_compiler import ContextCompiler
        from greenlight.context.thread_tracker import ThreadTracker
        from greenlight.context.agent_context_delivery import AgentContextDelivery
        
        # Create minimal compiler
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
        delivery = AgentContextDelivery(compiler=compiler, tracker=ThreadTracker())
        
        agent = BrainstormAgent(
            philosophy=BrainstormPhilosophy.THEME_FIRST,
            llm_caller=mock_llm_caller
        )
        
        proposal = await agent.generate_proposal({"delivery": delivery})
        
        assert proposal.content != ""
        assert proposal.metadata["philosophy"] == "theme_first"


class TestBrainstormOrchestrator:
    """Test brainstorm orchestrator."""
    
    @pytest.fixture
    def mock_llm_caller(self):
        """Create mock LLM caller that returns different responses."""
        call_count = 0
        async def caller(prompt, system_prompt, max_tokens):
            nonlocal call_count
            call_count += 1
            return f"Concept {call_count}: A unique story approach."
        return caller
    
    @pytest.fixture
    def orchestrator(self, mock_llm_caller):
        """Create test orchestrator."""
        return BrainstormOrchestrator(mock_llm_caller)
    
    def test_orchestrator_has_5_agents(self, orchestrator):
        """Orchestrator should have 5 agents."""
        assert len(orchestrator.agents) == 5
    
    def test_get_philosophies(self, orchestrator):
        """Should return all philosophy names."""
        philosophies = orchestrator.get_philosophies()
        assert len(philosophies) == 5
        assert "character_first" in philosophies
        assert "conflict_first" in philosophies
    
    @pytest.mark.asyncio
    async def test_generate_concepts(self, orchestrator):
        """Test parallel concept generation."""
        from greenlight.context.context_compiler import ContextCompiler
        from greenlight.context.thread_tracker import ThreadTracker
        from greenlight.context.agent_context_delivery import AgentContextDelivery
        
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
        delivery = AgentContextDelivery(compiler=compiler, tracker=ThreadTracker())
        
        proposals = await orchestrator.generate_concepts(delivery)
        
        assert len(proposals) == 5
        assert all(isinstance(p, Proposal) for p in proposals)
        # Each proposal should have unique content
        contents = [p.content for p in proposals]
        assert len(set(contents)) == 5  # All unique

