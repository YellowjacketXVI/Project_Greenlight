"""
Tests for ThreadTracker - Story Pipeline v3.0 continuity tracking.

Tests:
- Thread management (add, resolve)
- Setup/payoff tracking
- Context generation (~50 words)
- Scene updates
- Serialization
"""

import pytest
from greenlight.context.thread_tracker import ThreadTracker


class TestThreadTracker:
    """Test ThreadTracker class."""
    
    def test_initialization(self):
        """Test default initialization."""
        tracker = ThreadTracker()
        
        assert tracker.active_threads == []
        assert tracker.setups_awaiting_payoff == []
        assert tracker.last_line == ""
        assert tracker.tension_level == 5
        assert tracker.current_scene == 0
    
    def test_add_thread(self):
        """Test adding threads."""
        tracker = ThreadTracker()
        tracker.add_thread("Mei's secret plan")
        tracker.add_thread("Lin unaware")
        
        assert len(tracker.active_threads) == 2
        assert "Mei's secret plan" in tracker.active_threads
    
    def test_add_duplicate_thread(self):
        """Duplicate threads should not be added."""
        tracker = ThreadTracker()
        tracker.add_thread("test thread")
        tracker.add_thread("test thread")
        
        assert len(tracker.active_threads) == 1
    
    def test_resolve_thread(self):
        """Test resolving threads."""
        tracker = ThreadTracker()
        tracker.add_thread("test thread")
        tracker.resolve_thread("test thread")
        
        assert len(tracker.active_threads) == 0
    
    def test_add_setup(self):
        """Test adding setups."""
        tracker = ThreadTracker()
        tracker.add_setup("orchid symbolism introduced")
        
        assert len(tracker.setups_awaiting_payoff) == 1
    
    def test_payoff_setup(self):
        """Test paying off setups."""
        tracker = ThreadTracker()
        tracker.add_setup("orchid symbolism")
        tracker.payoff_setup("orchid symbolism")
        
        assert len(tracker.setups_awaiting_payoff) == 0
    
    def test_to_context_word_limit(self):
        """Context output should be ~50 words or less."""
        tracker = ThreadTracker()
        tracker.add_thread("Thread one")
        tracker.add_thread("Thread two")
        tracker.add_setup("Setup one")
        tracker.last_line = "The sun set over the mountains, casting long shadows."
        tracker.tension_level = 7
        
        context = tracker.to_context()
        word_count = len(context.split())
        
        # Should be under 60 words (allowing some flexibility)
        assert word_count < 60
    
    def test_to_context_format(self):
        """Context should have expected format."""
        tracker = ThreadTracker()
        tracker.add_thread("test thread")
        tracker.tension_level = 8
        
        context = tracker.to_context()
        
        assert "THREADS:" in context
        assert "TENSION: 8/10" in context
    
    def test_update_from_scene(self):
        """Test updating tracker after scene generation."""
        tracker = ThreadTracker()
        
        prose = "The hero walked into the sunset. A new day awaited."
        exit_states = {"CHAR_HERO": "hopeful"}
        
        tracker.update_from_scene(prose, exit_states, new_tension=6)
        
        assert tracker.current_scene == 1
        assert tracker.tension_level == 6
        assert "awaited" in tracker.last_line
        assert tracker.character_states["CHAR_HERO"] == "hopeful"
    
    def test_extract_last_line(self):
        """Test last line extraction."""
        tracker = ThreadTracker()
        
        prose = "First sentence. Second sentence. Third sentence!"
        tracker.update_from_scene(prose)
        
        assert "Third sentence" in tracker.last_line
    
    def test_serialization(self):
        """Test to_dict and from_dict."""
        tracker = ThreadTracker()
        tracker.add_thread("test thread")
        tracker.add_setup("test setup")
        tracker.tension_level = 7
        tracker.current_scene = 3
        
        data = tracker.to_dict()
        restored = ThreadTracker.from_dict(data)
        
        assert restored.active_threads == tracker.active_threads
        assert restored.setups_awaiting_payoff == tracker.setups_awaiting_payoff
        assert restored.tension_level == tracker.tension_level
        assert restored.current_scene == tracker.current_scene
    
    def test_reset(self):
        """Test tracker reset."""
        tracker = ThreadTracker()
        tracker.add_thread("test")
        tracker.add_setup("setup")
        tracker.tension_level = 9
        tracker.current_scene = 5
        
        tracker.reset()
        
        assert len(tracker.active_threads) == 0
        assert len(tracker.setups_awaiting_payoff) == 0
        assert tracker.tension_level == 5
        assert tracker.current_scene == 0
    
    def test_unresolved_count(self):
        """Test unresolved setup count."""
        tracker = ThreadTracker()
        tracker.add_setup("setup 1")
        tracker.add_setup("setup 2")
        tracker.add_setup("setup 3")
        tracker.payoff_setup("setup 1")
        
        assert tracker.get_unresolved_count() == 2

