"""
Greenlight Spatial Continuity System

Maintains visual continuity across shots by tracking spatial relationships,
camera directions, and element positions in frame.

Key Concepts:
- Camera Direction: Where the camera is facing (N, E, S, W)
- Element Position: Where elements are in world space (compass directions)
- Frame Position: Where elements appear on screen (x, y, z coordinates)
- 180° Rule: Maintain consistent screen direction for moving subjects
- Eyeline Matching: Characters looking at each other maintain correct screen positions
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

from .tag_parser import FramePosition, SpatialPositionCalculator


class SpatialRelationship(Enum):
    """Types of spatial relationships between elements."""
    FACING = "facing"  # Two elements facing each other
    BESIDE = "beside"  # Side by side
    BEHIND = "behind"  # One behind the other
    IN_FRONT = "in_front"  # One in front of the other
    ABOVE = "above"  # Vertically above
    BELOW = "below"  # Vertically below


@dataclass
class SpatialElement:
    """An element with spatial properties in a scene."""
    tag_name: str
    category: str  # character, location, prop
    compass_position: str  # N, NE, E, SE, S, SW, W, NW
    frame_position: Optional[FramePosition] = None
    facing_direction: Optional[str] = None  # Direction element is facing
    is_moving: bool = False
    movement_direction: Optional[str] = None  # Direction of movement


@dataclass
class ShotSpatialContext:
    """Spatial context for a single shot."""
    shot_id: str
    camera_direction: str  # N, E, S, W - where camera is facing
    location_tag: str
    location_direction: Optional[str] = None  # For directional location tags
    
    elements: List[SpatialElement] = field(default_factory=list)
    relationships: List[Tuple[str, SpatialRelationship, str]] = field(default_factory=list)
    
    # Continuity tracking
    previous_shot_id: Optional[str] = None
    maintains_180_rule: bool = True
    screen_direction: Optional[str] = None  # left_to_right, right_to_left
    
    def add_element(
        self,
        tag_name: str,
        category: str,
        compass_position: str,
        facing_direction: Optional[str] = None,
        depth: float = 0.5,
        vertical_offset: float = 0.0
    ) -> SpatialElement:
        """Add an element and calculate its frame position."""
        frame_pos = SpatialPositionCalculator.calculate_frame_position(
            element_compass_direction=compass_position,
            camera_facing_direction=self.camera_direction,
            depth=depth,
            vertical_offset=vertical_offset
        )
        
        element = SpatialElement(
            tag_name=tag_name,
            category=category,
            compass_position=compass_position,
            frame_position=frame_pos,
            facing_direction=facing_direction
        )
        
        self.elements.append(element)
        return element
    
    def get_element(self, tag_name: str) -> Optional[SpatialElement]:
        """Get element by tag name."""
        for elem in self.elements:
            if elem.tag_name == tag_name:
                return elem
        return None
    
    def calculate_relationship(
        self,
        element1_tag: str,
        element2_tag: str
    ) -> Optional[SpatialRelationship]:
        """Calculate spatial relationship between two elements."""
        elem1 = self.get_element(element1_tag)
        elem2 = self.get_element(element2_tag)
        
        if not elem1 or not elem2:
            return None
        
        # Check if facing each other
        if elem1.facing_direction and elem2.facing_direction:
            opposite = SpatialPositionCalculator.get_opposite_direction(elem1.facing_direction)
            if opposite == elem2.facing_direction:
                return SpatialRelationship.FACING
        
        # Check relative positions
        if elem1.frame_position and elem2.frame_position:
            x_diff = abs(elem1.frame_position.x - elem2.frame_position.x)
            z_diff = elem1.frame_position.z - elem2.frame_position.z
            
            if x_diff < 0.3:  # Similar x position
                if z_diff > 0.2:
                    return SpatialRelationship.BEHIND
                elif z_diff < -0.2:
                    return SpatialRelationship.IN_FRONT
            else:
                return SpatialRelationship.BESIDE
        
        return None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'shot_id': self.shot_id,
            'camera_direction': self.camera_direction,
            'location_tag': self.location_tag,
            'location_direction': self.location_direction,
            'elements': [
                {
                    'tag_name': e.tag_name,
                    'category': e.category,
                    'compass_position': e.compass_position,
                    'frame_position': e.frame_position.to_dict() if e.frame_position else None,
                    'facing_direction': e.facing_direction,
                    'is_moving': e.is_moving,
                    'movement_direction': e.movement_direction
                }
                for e in self.elements
            ],
            'maintains_180_rule': self.maintains_180_rule,
            'screen_direction': self.screen_direction
        }


class SpatialContinuityValidator:
    """
    Validates spatial continuity across shots.

    Checks:
    - 180° Rule: Characters maintain consistent screen positions
    - Eyeline Matching: Characters looking at each other have correct positions
    - Movement Direction: Moving subjects maintain screen direction
    - Spatial Consistency: Elements don't teleport between shots
    """

    def __init__(self):
        self.shot_contexts: Dict[str, ShotSpatialContext] = {}

    def add_shot_context(self, context: ShotSpatialContext) -> None:
        """Add a shot context for tracking."""
        self.shot_contexts[context.shot_id] = context

    def validate_180_rule(
        self,
        shot1: ShotSpatialContext,
        shot2: ShotSpatialContext,
        character1_tag: str,
        character2_tag: str
    ) -> Tuple[bool, str]:
        """
        Validate 180° rule between two shots.

        The 180° rule states that if two characters are facing each other,
        they should maintain consistent screen positions across cuts.

        Example:
            Shot 1: Camera facing East
            - Character A at North → appears on left (x = -0.7)
            - Character B at South → appears on right (x = 0.7)

            Shot 2: Camera facing West (reverse angle)
            - Character A at North → appears on RIGHT (x = 0.7)
            - Character B at South → appears on LEFT (x = -0.7)
            - This VIOLATES 180° rule (positions flipped)

            Shot 2 (correct): Camera facing North or South
            - Maintains left/right relationship

        Returns:
            Tuple of (is_valid, explanation)
        """
        elem1_shot1 = shot1.get_element(character1_tag)
        elem2_shot1 = shot1.get_element(character2_tag)
        elem1_shot2 = shot2.get_element(character1_tag)
        elem2_shot2 = shot2.get_element(character2_tag)

        if not all([elem1_shot1, elem2_shot1, elem1_shot2, elem2_shot2]):
            return True, "Characters not in both shots"

        # Get frame positions
        pos1_shot1 = elem1_shot1.frame_position
        pos2_shot1 = elem2_shot1.frame_position
        pos1_shot2 = elem1_shot2.frame_position
        pos2_shot2 = elem2_shot2.frame_position

        if not all([pos1_shot1, pos2_shot1, pos1_shot2, pos2_shot2]):
            return True, "Frame positions not calculated"

        # Check if left/right relationship is maintained
        # In shot 1: is char1 left of char2?
        char1_left_of_char2_shot1 = pos1_shot1.x < pos2_shot1.x
        # In shot 2: is char1 still left of char2?
        char1_left_of_char2_shot2 = pos1_shot2.x < pos2_shot2.x

        if char1_left_of_char2_shot1 == char1_left_of_char2_shot2:
            return True, "180° rule maintained - screen positions consistent"
        else:
            return False, (
                f"180° rule VIOLATED - {character1_tag} and {character2_tag} "
                f"flipped screen positions between shots. "
                f"Shot {shot1.shot_id}: {character1_tag} {'left' if char1_left_of_char2_shot1 else 'right'} of {character2_tag}. "
                f"Shot {shot2.shot_id}: {character1_tag} {'left' if char1_left_of_char2_shot2 else 'right'} of {character2_tag}."
            )

    def validate_eyeline_match(
        self,
        shot1: ShotSpatialContext,
        shot2: ShotSpatialContext,
        character_tag: str
    ) -> Tuple[bool, str]:
        """
        Validate eyeline matching for a character across shots.

        If a character is looking at something in shot 1, their eyeline
        should match the position of that thing in shot 2.

        Returns:
            Tuple of (is_valid, explanation)
        """
        elem_shot1 = shot1.get_element(character_tag)
        elem_shot2 = shot2.get_element(character_tag)

        if not elem_shot1 or not elem_shot2:
            return True, "Character not in both shots"

        if not elem_shot1.facing_direction or not elem_shot2.facing_direction:
            return True, "Facing direction not specified"

        # Calculate where character is looking in each shot
        look_pos_shot1 = SpatialPositionCalculator.calculate_frame_position(
            element_compass_direction=elem_shot1.facing_direction,
            camera_facing_direction=shot1.camera_direction
        )

        look_pos_shot2 = SpatialPositionCalculator.calculate_frame_position(
            element_compass_direction=elem_shot2.facing_direction,
            camera_facing_direction=shot2.camera_direction
        )

        # Check if eyeline direction is consistent
        eyeline_consistent = (
            (look_pos_shot1.x < 0 and look_pos_shot2.x < 0) or
            (look_pos_shot1.x > 0 and look_pos_shot2.x > 0) or
            (abs(look_pos_shot1.x) < 0.2 and abs(look_pos_shot2.x) < 0.2)
        )

        if eyeline_consistent:
            return True, f"Eyeline match maintained for {character_tag}"
        else:
            return False, (
                f"Eyeline mismatch for {character_tag} - "
                f"looking {look_pos_shot1.screen_side} in shot {shot1.shot_id}, "
                f"but {look_pos_shot2.screen_side} in shot {shot2.shot_id}"
            )

    def suggest_camera_direction(
        self,
        previous_shot: ShotSpatialContext,
        character1_tag: str,
        character2_tag: str
    ) -> List[str]:
        """
        Suggest valid camera directions for next shot that maintain 180° rule.

        Returns:
            List of valid camera directions (N, E, S, W)
        """
        elem1 = previous_shot.get_element(character1_tag)
        elem2 = previous_shot.get_element(character2_tag)

        if not elem1 or not elem2:
            return ['N', 'E', 'S', 'W']

        # Get compass positions
        pos1 = elem1.compass_position
        pos2 = elem2.compass_position

        # Calculate valid camera positions
        valid_directions = []

        for direction in ['N', 'E', 'S', 'W']:
            # Test if this direction maintains the relationship
            test_pos1 = SpatialPositionCalculator.calculate_frame_position(pos1, direction)
            test_pos2 = SpatialPositionCalculator.calculate_frame_position(pos2, direction)

            # Check if left/right relationship matches previous shot
            if elem1.frame_position and elem2.frame_position:
                prev_relationship = elem1.frame_position.x < elem2.frame_position.x
                new_relationship = test_pos1.x < test_pos2.x

                if prev_relationship == new_relationship:
                    valid_directions.append(direction)

        return valid_directions if valid_directions else ['N', 'E', 'S', 'W']

