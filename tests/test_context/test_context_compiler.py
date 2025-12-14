"""
Tests for ContextCompiler - Story Pipeline v3.0 context compression.

Tests:
- Story seed compilation (~50 words)
- Character card compilation (~40 words each)
- Location card compilation (~30 words each)
- Token estimation accuracy
- Project loading
"""

import pytest
from pathlib import Path
from greenlight.context.context_compiler import (
    ContextCompiler,
    _truncate_to_words,
    _extract_core_trait,
    STORY_SEED_WORD_LIMIT,
    CHARACTER_CARD_WORD_LIMIT,
    LOCATION_CARD_WORD_LIMIT,
)


class TestTruncation:
    """Test word truncation utilities."""
    
    def test_truncate_short_text(self):
        """Short text should not be truncated."""
        text = "This is short"
        result = _truncate_to_words(text, 10)
        assert result == text
    
    def test_truncate_long_text(self):
        """Long text should be truncated with ellipsis."""
        text = "one two three four five six seven eight nine ten"
        result = _truncate_to_words(text, 5)
        assert result == "one two three four five..."
        assert len(result.split()) == 5  # 5 words (last has "..." appended)
    
    def test_extract_core_trait(self):
        """Should extract first sentence."""
        text = "She is brave. She fights for justice. She never gives up."
        result = _extract_core_trait(text, 5)
        assert "brave" in result
        assert "justice" not in result


class TestContextCompiler:
    """Test ContextCompiler class."""
    
    @pytest.fixture
    def sample_world_config(self):
        """Sample world config for testing."""
        return {
            "title": "Test Story",
            "logline": "A hero's journey through darkness to find light.",
            "themes": "Redemption, Hope, Sacrifice",
            "characters": [
                {
                    "tag": "CHAR_HERO",
                    "name": "Alex",
                    "role": "protagonist",
                    "backstory": "A former soldier haunted by past mistakes.",
                    "want": "To find redemption",
                    "need": "To forgive themselves"
                },
                {
                    "tag": "CHAR_MENTOR",
                    "name": "Sage",
                    "role": "mentor",
                    "backstory": "An ancient guide with hidden secrets."
                }
            ],
            "locations": [
                {
                    "tag": "LOC_TEMPLE",
                    "name": "Ancient Temple",
                    "description": "A crumbling stone structure filled with mystery.",
                    "atmosphere": "Eerie and sacred"
                }
            ],
            "props": [
                {
                    "tag": "PROP_SWORD",
                    "name": "Ancestral Blade",
                    "significance": "Symbol of the hero's lineage and duty."
                }
            ]
        }
    
    @pytest.fixture
    def sample_pitch(self):
        """Sample pitch text."""
        return "A fallen hero must confront their past to save the future."
    
    def test_initialization(self, sample_world_config, sample_pitch):
        """Test compiler initializes and compiles context."""
        compiler = ContextCompiler(
            world_config=sample_world_config,
            pitch=sample_pitch
        )
        
        assert compiler.story_seed != ""
        assert len(compiler.character_cards) == 2
        assert len(compiler.location_cards) == 1
        assert len(compiler.prop_cards) == 1
    
    def test_story_seed_word_limit(self, sample_world_config, sample_pitch):
        """Story seed should be within word limit."""
        compiler = ContextCompiler(
            world_config=sample_world_config,
            pitch=sample_pitch
        )
        
        word_count = len(compiler.story_seed.split())
        assert word_count <= STORY_SEED_WORD_LIMIT + 1  # +1 for "..."
    
    def test_character_card_word_limit(self, sample_world_config, sample_pitch):
        """Character cards should be within word limit."""
        compiler = ContextCompiler(
            world_config=sample_world_config,
            pitch=sample_pitch
        )
        
        for tag, card in compiler.character_cards.items():
            word_count = len(card.split())
            assert word_count <= CHARACTER_CARD_WORD_LIMIT + 1
    
    def test_location_card_word_limit(self, sample_world_config, sample_pitch):
        """Location cards should be within word limit."""
        compiler = ContextCompiler(
            world_config=sample_world_config,
            pitch=sample_pitch
        )
        
        for tag, card in compiler.location_cards.items():
            word_count = len(card.split())
            assert word_count <= LOCATION_CARD_WORD_LIMIT + 1
    
    def test_get_relevant_cards(self, sample_world_config, sample_pitch):
        """Should return only relevant cards for a scene."""
        compiler = ContextCompiler(
            world_config=sample_world_config,
            pitch=sample_pitch
        )
        
        result = compiler.get_relevant_cards(
            character_tags=["CHAR_HERO"],
            location_tag="LOC_TEMPLE"
        )
        
        assert "CHAR_HERO" in result
        assert "LOC_TEMPLE" in result
        assert "CHAR_MENTOR" not in result
    
    def test_token_estimation(self, sample_world_config, sample_pitch):
        """Token estimation should return reasonable values."""
        compiler = ContextCompiler(
            world_config=sample_world_config,
            pitch=sample_pitch
        )
        
        estimates = compiler.estimate_tokens()
        
        assert estimates["story_seed"] > 0
        assert estimates["character_cards"] > 0
        assert estimates["total"] > 0
        assert estimates["total"] < 1000  # Should be compressed

