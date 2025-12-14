"""
Tests for Tag Parser Module

Tests for greenlight/tags/tag_parser.py
"""

import pytest

from greenlight.tags.tag_parser import (
    TagParser,
    Tag,
    TagCategory,
    extract_tags,
    validate_tag_format,
    parse_directional_tag
)


class TestTagParser:
    """Tests for TagParser class."""
    
    def test_extract_simple_tags(self, sample_story_text):
        """Test extracting simple tags from text."""
        parser = TagParser()
        tags = parser.extract(sample_story_text)
        
        assert len(tags) > 0
        tag_names = [t.name for t in tags]
        assert "MARCUS" in tag_names
        assert "ELENA" in tag_names
    
    def test_extract_location_tags(self, sample_story_text):
        """Test extracting location tags."""
        parser = TagParser()
        tags = parser.extract(sample_story_text)
        
        location_tags = [t for t in tags if t.category == TagCategory.LOCATION]
        assert len(location_tags) >= 1
    
    def test_extract_directional_tags(self, sample_story_text):
        """Test extracting directional location tags."""
        parser = TagParser()
        tags = parser.extract(sample_story_text)
        
        directional_tags = [t for t in tags if "_DIR_" in t.name]
        assert len(directional_tags) >= 1
    
    def test_extract_prop_tags(self, sample_story_text):
        """Test extracting prop tags."""
        parser = TagParser()
        tags = parser.extract(sample_story_text)
        
        prop_tags = [t for t in tags if t.category == TagCategory.PROP]
        assert len(prop_tags) >= 1
    
    def test_extract_concept_tags(self, sample_story_text):
        """Test extracting concept tags."""
        parser = TagParser()
        tags = parser.extract(sample_story_text)
        
        concept_tags = [t for t in tags if t.category == TagCategory.CONCEPT]
        assert len(concept_tags) >= 1
    
    def test_extract_event_tags(self, sample_story_text):
        """Test extracting event tags."""
        parser = TagParser()
        tags = parser.extract(sample_story_text)
        
        event_tags = [t for t in tags if t.category == TagCategory.EVENT]
        assert len(event_tags) >= 1
    
    def test_no_duplicate_tags(self, sample_story_text):
        """Test that duplicate tags are not returned."""
        text = "[MARCUS] meets [MARCUS] at the [LOC_WAREHOUSE]"
        parser = TagParser()
        tags = parser.extract(text)
        
        marcus_tags = [t for t in tags if t.name == "MARCUS"]
        assert len(marcus_tags) == 1


class TestTagValidation:
    """Tests for tag validation."""
    
    def test_valid_tag_format(self):
        """Test valid tag formats."""
        assert validate_tag_format("MARCUS") is True
        assert validate_tag_format("LOC_WAREHOUSE") is True
        assert validate_tag_format("LOC_WAREHOUSE_DIR_N") is True
        assert validate_tag_format("PROP_ARTIFACT") is True
    
    def test_invalid_tag_format(self):
        """Test invalid tag formats."""
        assert validate_tag_format("marcus") is False  # lowercase
        assert validate_tag_format("123TAG") is False  # starts with number
        assert validate_tag_format("TAG-NAME") is False  # hyphen
        assert validate_tag_format("") is False  # empty


class TestDirectionalTags:
    """Tests for directional tag parsing."""
    
    def test_parse_directional_tag_north(self):
        """Test parsing north directional tag."""
        result = parse_directional_tag("LOC_WAREHOUSE_DIR_N")
        
        assert result is not None
        assert result["base_location"] == "LOC_WAREHOUSE"
        assert result["direction"] == "N"
    
    def test_parse_directional_tag_south(self):
        """Test parsing south directional tag."""
        result = parse_directional_tag("LOC_CANYON_DIR_S")
        
        assert result is not None
        assert result["base_location"] == "LOC_CANYON"
        assert result["direction"] == "S"
    
    def test_parse_non_directional_tag(self):
        """Test parsing non-directional tag returns None."""
        result = parse_directional_tag("LOC_WAREHOUSE")
        
        assert result is None
    
    def test_parse_character_tag(self):
        """Test parsing character tag returns None."""
        result = parse_directional_tag("MARCUS")
        
        assert result is None


class TestTagCategory:
    """Tests for tag categorization."""
    
    def test_character_category(self):
        """Test character tag categorization."""
        parser = TagParser()
        tag = parser.parse_single("[MARCUS]")
        
        assert tag.category == TagCategory.CHARACTER
    
    def test_location_category(self):
        """Test location tag categorization."""
        parser = TagParser()
        tag = parser.parse_single("[LOC_WAREHOUSE]")
        
        assert tag.category == TagCategory.LOCATION
    
    def test_prop_category(self):
        """Test prop tag categorization."""
        parser = TagParser()
        tag = parser.parse_single("[PROP_ARTIFACT]")
        
        assert tag.category == TagCategory.PROP
    
    def test_concept_category(self):
        """Test concept tag categorization."""
        parser = TagParser()
        tag = parser.parse_single("[CONCEPT_REDEMPTION]")
        
        assert tag.category == TagCategory.CONCEPT
    
    def test_event_category(self):
        """Test event tag categorization."""
        parser = TagParser()
        tag = parser.parse_single("[EVENT_ATTACK]")
        
        assert tag.category == TagCategory.EVENT

