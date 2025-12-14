"""
Tests for Coherence Validator - Story Pipeline v3.0

Tests:
- State consistency validation
- Thread resolution validation
- Steal list integration validation
- Emotional arc validation
- Transition validation
"""

import pytest
from greenlight.patterns.quality.coherence_validator import (
    CoherenceValidator,
    CoherenceReport,
    CoherenceIssue,
)
from greenlight.context.thread_tracker import ThreadTracker
from greenlight.context.agent_context_delivery import SceneOutline
from greenlight.agents.prose_agent import ProseResult


class TestCoherenceValidator:
    """Test coherence validator."""
    
    @pytest.fixture
    def validator(self):
        """Create test validator."""
        return CoherenceValidator(steal_list=["Lin's awareness", "tea ceremony"])
    
    @pytest.fixture
    def sample_prose_results(self):
        """Create sample prose results."""
        return [
            ProseResult(
                scene_number=1,
                prose="Lin stands in the temple, her awareness sharp. The tea ceremony begins.",
                word_count=12,
                exit_states={"CHAR_LIN": "focused"},
                new_threads=[], resolved_threads=[], new_setups=[]
            ),
            ProseResult(
                scene_number=2,
                prose="The ceremony continues. Lin moves with purpose through the garden.",
                word_count=11,
                exit_states={"CHAR_LIN": "determined"},
                new_threads=[], resolved_threads=[], new_setups=[]
            ),
        ]
    
    @pytest.fixture
    def sample_outlines(self):
        """Create sample outlines."""
        return [
            SceneOutline(
                scene_number=1,
                location="LOC_TEMPLE",
                characters=["CHAR_LIN"],
                goal="Establish Lin",
                key_moment="Awareness awakens",
                entry_states={"CHAR_LIN": "uncertain"},
                exit_states={"CHAR_LIN": "focused"},
                tension=3
            ),
            SceneOutline(
                scene_number=2,
                location="LOC_GARDEN",
                characters=["CHAR_LIN"],
                goal="Lin takes action",
                key_moment="Decision made",
                entry_states={"CHAR_LIN": "focused"},
                exit_states={"CHAR_LIN": "determined"},
                tension=5
            ),
        ]
    
    @pytest.fixture
    def tracker(self):
        """Create test tracker."""
        tracker = ThreadTracker()
        tracker.add_thread("Lin's journey")
        return tracker
    
    def test_validate_returns_report(self, validator, sample_prose_results, sample_outlines, tracker):
        """Test that validate returns a CoherenceReport."""
        report = validator.validate(sample_prose_results, sample_outlines, tracker)
        
        assert isinstance(report, CoherenceReport)
        assert isinstance(report.score, float)
        assert 0.0 <= report.score <= 1.0
    
    def test_validate_detects_unresolved_threads(self, validator, sample_prose_results, sample_outlines, tracker):
        """Test detection of unresolved threads."""
        report = validator.validate(sample_prose_results, sample_outlines, tracker)
        
        # Should detect unresolved "Lin's journey" thread
        unresolved = [i for i in report.issues if i.issue_type == "unresolved_thread"]
        assert len(unresolved) >= 1
    
    def test_validate_detects_steal_integration(self, validator, sample_prose_results, sample_outlines, tracker):
        """Test detection of steal list integration."""
        report = validator.validate(sample_prose_results, sample_outlines, tracker)
        
        # Both steal items should be found in prose
        missing_steal = [i for i in report.issues if i.issue_type == "missing_steal"]
        assert len(missing_steal) == 0  # Both "awareness" and "tea ceremony" are in prose
    
    def test_validate_detects_missing_steal(self, sample_prose_results, sample_outlines, tracker):
        """Test detection of missing steal items."""
        validator = CoherenceValidator(steal_list=["dragon fire", "ancient scroll"])
        report = validator.validate(sample_prose_results, sample_outlines, tracker)
        
        # Neither steal item is in prose
        missing_steal = [i for i in report.issues if i.issue_type == "missing_steal"]
        assert len(missing_steal) == 2
    
    def test_validate_stats(self, validator, sample_prose_results, sample_outlines, tracker):
        """Test that stats are populated."""
        report = validator.validate(sample_prose_results, sample_outlines, tracker)
        
        assert report.stats["total_scenes"] == 2
        assert report.stats["total_words"] == 23
        assert "steal_list_size" in report.stats


class TestCoherenceIssue:
    """Test CoherenceIssue dataclass."""
    
    def test_to_dict(self):
        """Test serialization."""
        issue = CoherenceIssue(
            issue_type="state_mismatch",
            severity="warning",
            scene_number=2,
            description="Test issue",
            suggested_fix="Fix it"
        )
        
        d = issue.to_dict()
        assert d["type"] == "state_mismatch"
        assert d["severity"] == "warning"
        assert d["scene"] == 2


class TestCoherenceReport:
    """Test CoherenceReport dataclass."""
    
    def test_critical_issues(self):
        """Test filtering critical issues."""
        report = CoherenceReport(
            is_valid=False,
            score=0.5,
            issues=[
                CoherenceIssue("a", "critical", 1, "Critical issue"),
                CoherenceIssue("b", "warning", 2, "Warning issue"),
            ]
        )
        
        assert len(report.critical_issues) == 1
        assert len(report.warnings) == 1

