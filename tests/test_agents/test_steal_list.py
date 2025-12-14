"""
Tests for Steal List Judge and Aggregator - Story Pipeline v3.0

Tests:
- Judge vote parsing
- Judge panel evaluation
- Steal list aggregation (2+ threshold)
- Integration validation
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from greenlight.agents.steal_list_judge import (
    StealListJudge,
    JudgePanel,
    JudgeVote,
    StealListJudgeConfig,
    JUDGE_CONFIGS,
)
from greenlight.patterns.steal_list import (
    StealListAggregator,
    StealElement,
    StealCategory,
    StealListResult,
)
from greenlight.patterns.assembly import Proposal


class TestJudgeVote:
    """Test JudgeVote dataclass."""
    
    def test_get_winner(self):
        """Should return first ranked concept."""
        vote = JudgeVote(
            judge_id="test",
            rankings=["concept_b", "concept_a", "concept_c"],
            reasoning="Test",
            steal_elements=[]
        )
        assert vote.get_winner() == "concept_b"
    
    def test_get_points(self):
        """Should convert rankings to points."""
        vote = JudgeVote(
            judge_id="test",
            rankings=["a", "b", "c", "d", "e"],
            reasoning="Test",
            steal_elements=[]
        )
        points = vote.get_points()
        assert points["a"] == 5
        assert points["b"] == 4
        assert points["e"] == 1


class TestStealListJudge:
    """Test individual steal list judge."""
    
    @pytest.fixture
    def mock_llm_caller(self):
        """Create mock LLM caller."""
        async def caller(prompt, system_prompt, max_tokens):
            return """RANKING: B, A, C, D, E
REASONING: Concept B has the strongest narrative arc.
STEAL: Lin's silent awareness | The orchid symbolism | The final confrontation"""
        return caller
    
    @pytest.fixture
    def judge(self, mock_llm_caller):
        """Create test judge."""
        return StealListJudge(JUDGE_CONFIGS[0], mock_llm_caller)
    
    @pytest.fixture
    def sample_concepts(self):
        """Create sample concepts."""
        return [
            Proposal(agent_id=f"concept_{chr(97+i)}", content=f"Concept {chr(65+i)}")
            for i in range(5)
        ]
    
    @pytest.mark.asyncio
    async def test_evaluate(self, judge, sample_concepts):
        """Test judge evaluation."""
        vote = await judge.evaluate(sample_concepts, "Test context")
        
        assert isinstance(vote, JudgeVote)
        assert len(vote.rankings) == 5
        assert len(vote.steal_elements) == 3
        assert "Lin's silent awareness" in vote.steal_elements


class TestJudgePanel:
    """Test judge panel orchestration."""
    
    @pytest.fixture
    def mock_llm_caller(self):
        """Create mock LLM caller with varied responses."""
        call_count = 0
        async def caller(prompt, system_prompt, max_tokens):
            nonlocal call_count
            call_count += 1
            # All judges agree on winner but have different steal elements
            if call_count == 1:
                return """RANKING: A, B, C, D, E
REASONING: Strong character arc.
STEAL: Lin's awareness | Orchid symbolism"""
            elif call_count == 2:
                return """RANKING: A, C, B, D, E
REASONING: Emotional resonance.
STEAL: Orchid symbolism | Final confrontation"""
            else:
                return """RANKING: A, B, D, C, E
REASONING: Visual storytelling.
STEAL: Lin's awareness | Visual motif"""
        return caller
    
    @pytest.fixture
    def panel(self, mock_llm_caller):
        """Create test panel."""
        return JudgePanel(mock_llm_caller)
    
    @pytest.fixture
    def sample_concepts(self):
        """Create sample concepts."""
        return [
            Proposal(agent_id=f"brainstorm_{chr(97+i)}", content=f"Concept {chr(65+i)}")
            for i in range(5)
        ]
    
    @pytest.mark.asyncio
    async def test_evaluate_concepts(self, panel, sample_concepts):
        """Test panel evaluation."""
        result = await panel.evaluate_concepts(sample_concepts, "Test context")
        
        assert "winner" in result
        assert "votes" in result
        assert "steal_list" in result
        assert "scores" in result
        assert len(result["votes"]) == 3


class TestStealListAggregator:
    """Test steal list aggregation."""
    
    @pytest.fixture
    def aggregator(self):
        """Create test aggregator."""
        return StealListAggregator(threshold=2)
    
    @pytest.fixture
    def sample_votes(self):
        """Create sample votes with overlapping steal elements."""
        return [
            JudgeVote("j1", [], "", ["Lin's awareness", "Orchid symbolism"]),
            JudgeVote("j2", [], "", ["Orchid symbolism", "Final confrontation"]),
            JudgeVote("j3", [], "", ["Lin's awareness", "Visual motif"]),
        ]
    
    def test_aggregate_threshold(self, aggregator, sample_votes):
        """Elements with 2+ mentions should be included."""
        result = aggregator.aggregate(sample_votes)
        
        assert isinstance(result, StealListResult)
        # "Lin's awareness" and "Orchid symbolism" have 2+ mentions
        required = result.get_required_elements()
        assert len(required) == 2
    
    def test_categorization(self, aggregator):
        """Should categorize elements correctly."""
        category = aggregator._categorize("The character's emotional transformation")
        assert category == StealCategory.CHARACTER
        
        category = aggregator._categorize("The visual motif of shadows")
        assert category == StealCategory.VISUAL
    
    def test_validate_integration(self, aggregator, sample_votes):
        """Should validate steal list integration."""
        result = aggregator.aggregate(sample_votes)
        
        output = "Lin showed awareness of the situation. The orchid symbolism was clear."
        validation = aggregator.validate_integration(result, output)
        
        assert validation["valid"] == True
        assert validation["integration_score"] == 1.0

