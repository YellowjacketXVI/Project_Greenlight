"""
Tests for Spatial Positioning System

Validates the mathematical formulas for calculating frame positions
based on camera direction and element compass positions.
"""

import pytest
import math
from greenlight.tags import (
    SpatialPositionCalculator,
    FramePosition,
    ShotSpatialContext,
    SpatialContinuityValidator
)


class TestSpatialPositionCalculator:
    """Test the core spatial positioning formulas."""
    
    def test_door_on_north_wall_camera_west(self):
        """Door on north wall appears on LEFT when camera faces west."""
        pos = SpatialPositionCalculator.calculate_frame_position(
            element_compass_direction="N",
            camera_facing_direction="W"
        )
        
        assert pos.x < 0, "Door should be on left side"
        assert pos.screen_side == "left"
        assert abs(pos.x - (-1.0)) < 0.1, f"Expected x ≈ -1.0, got {pos.x}"
    
    def test_door_on_north_wall_camera_east(self):
        """Door on north wall appears on RIGHT when camera faces east."""
        pos = SpatialPositionCalculator.calculate_frame_position(
            element_compass_direction="N",
            camera_facing_direction="E"
        )
        
        assert pos.x > 0, "Door should be on right side"
        assert pos.screen_side == "right"
        assert abs(pos.x - 1.0) < 0.1, f"Expected x ≈ 1.0, got {pos.x}"
    
    def test_door_on_north_wall_camera_north(self):
        """Door on north wall appears CENTER when camera faces north."""
        pos = SpatialPositionCalculator.calculate_frame_position(
            element_compass_direction="N",
            camera_facing_direction="N"
        )
        
        assert abs(pos.x) < 0.1, "Door should be centered"
        assert pos.screen_side == "center"
    
    def test_opposite_directions(self):
        """Test opposite direction calculation."""
        assert SpatialPositionCalculator.get_opposite_direction("N") == "S"
        assert SpatialPositionCalculator.get_opposite_direction("E") == "W"
        assert SpatialPositionCalculator.get_opposite_direction("NE") == "SW"
    
    def test_relative_position_descriptions(self):
        """Test relative position descriptions."""
        # From North, East is to the right
        rel = SpatialPositionCalculator.calculate_relative_position("N", "E")
        assert "right" in rel.lower()
        
        # From North, West is to the left
        rel = SpatialPositionCalculator.calculate_relative_position("N", "W")
        assert "left" in rel.lower()
        
        # From North, South is behind
        rel = SpatialPositionCalculator.calculate_relative_position("N", "S")
        assert "behind" in rel.lower()
    
    def test_rotation(self):
        """Test direction rotation."""
        # Rotate North 90° clockwise = East
        result = SpatialPositionCalculator.rotate_direction("N", 90)
        assert result == "E"
        
        # Rotate East 90° clockwise = South
        result = SpatialPositionCalculator.rotate_direction("E", 90)
        assert result == "S"
        
        # Rotate North 180° = South
        result = SpatialPositionCalculator.rotate_direction("N", 180)
        assert result == "S"


class TestShotSpatialContext:
    """Test shot spatial context and element positioning."""
    
    def test_add_element_calculates_position(self):
        """Adding element should calculate its frame position."""
        shot = ShotSpatialContext(
            shot_id="S01F01",
            camera_direction="E",
            location_tag="LOC_ROOM"
        )
        
        element = shot.add_element(
            tag_name="CHAR_ALICE",
            category="character",
            compass_position="N"
        )
        
        assert element.frame_position is not None
        assert element.frame_position.x > 0  # North is to the right when camera faces East
    
    def test_two_characters_facing_each_other(self):
        """Test two characters positioned opposite each other."""
        shot = ShotSpatialContext(
            shot_id="S01F01",
            camera_direction="E",
            location_tag="LOC_ROOM"
        )
        
        alice = shot.add_element("CHAR_ALICE", "character", "N")
        bob = shot.add_element("CHAR_BOB", "character", "S")
        
        # Alice should be on right, Bob on left (when camera faces East)
        assert alice.frame_position.x > bob.frame_position.x
    
    def test_calculate_relationship(self):
        """Test spatial relationship calculation."""
        shot = ShotSpatialContext(
            shot_id="S01F01",
            camera_direction="E",
            location_tag="LOC_ROOM"
        )
        
        shot.add_element("CHAR_ALICE", "character", "N", facing_direction="S")
        shot.add_element("CHAR_BOB", "character", "S", facing_direction="N")
        
        relationship = shot.calculate_relationship("CHAR_ALICE", "CHAR_BOB")
        # Should detect they're facing each other
        assert relationship is not None


class TestSpatialContinuityValidator:
    """Test 180° rule and continuity validation."""
    
    def test_180_rule_maintained(self):
        """Test that 180° rule is maintained across valid shots."""
        # Shot 1: Camera facing East
        shot1 = ShotSpatialContext("S01F01", "E", "LOC_ROOM")
        shot1.add_element("CHAR_ALICE", "character", "N")  # Right side
        shot1.add_element("CHAR_BOB", "character", "S")    # Left side
        
        # Shot 2: Camera facing North (maintains relationship)
        shot2 = ShotSpatialContext("S01F02", "N", "LOC_ROOM")
        shot2.add_element("CHAR_ALICE", "character", "N")
        shot2.add_element("CHAR_BOB", "character", "S")
        
        validator = SpatialContinuityValidator()
        is_valid, explanation = validator.validate_180_rule(
            shot1, shot2, "CHAR_ALICE", "CHAR_BOB"
        )
        
        assert is_valid, f"180° rule should be maintained: {explanation}"
    
    def test_180_rule_violated(self):
        """Test that 180° rule violation is detected."""
        # Shot 1: Camera facing East
        shot1 = ShotSpatialContext("S01F01", "E", "LOC_ROOM")
        shot1.add_element("CHAR_ALICE", "character", "N")  # Right side
        shot1.add_element("CHAR_BOB", "character", "S")    # Left side
        
        # Shot 2: Camera facing West (VIOLATES - flips positions)
        shot2 = ShotSpatialContext("S01F02", "W", "LOC_ROOM")
        shot2.add_element("CHAR_ALICE", "character", "N")  # Now LEFT side
        shot2.add_element("CHAR_BOB", "character", "S")    # Now RIGHT side
        
        validator = SpatialContinuityValidator()
        is_valid, explanation = validator.validate_180_rule(
            shot1, shot2, "CHAR_ALICE", "CHAR_BOB"
        )
        
        assert not is_valid, "180° rule violation should be detected"
        assert "VIOLATED" in explanation

