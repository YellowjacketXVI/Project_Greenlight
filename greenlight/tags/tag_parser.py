"""
Greenlight Tag Parser

Parses and validates story element tags from text content.
Includes spatial positioning system for visual continuity.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple, Dict
from enum import Enum

from greenlight.core.constants import (
    TAG_PATTERN,
    TAG_FORMAT_PATTERN,
    TagCategory,
    TagPrefix,
    DIRECTION_SUFFIXES,
    VALID_DIRECTIONS
)
from greenlight.core.exceptions import InvalidTagFormatError


@dataclass
class FramePosition:
    """Spatial position within a frame for visual continuity.

    Uses screen coordinates where:
    - x: -1.0 (left) to 1.0 (right), 0.0 is center
    - y: -1.0 (bottom) to 1.0 (top), 0.0 is center
    - z: 0.0 (foreground) to 1.0 (background)

    Also tracks spatial relationships relative to camera direction.
    """
    x: float = 0.0  # Horizontal position in frame (-1.0 to 1.0)
    y: float = 0.0  # Vertical position in frame (-1.0 to 1.0)
    z: float = 0.5  # Depth in frame (0.0 foreground to 1.0 background)

    # Spatial descriptors for continuity
    screen_side: str = "center"  # left, center, right
    screen_height: str = "middle"  # bottom, middle, top
    depth_layer: str = "mid"  # foreground, mid, background

    # Relative to camera direction
    compass_position: Optional[str] = None  # N, NE, E, SE, S, SW, W, NW relative to camera

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'screen_side': self.screen_side,
            'screen_height': self.screen_height,
            'depth_layer': self.depth_layer,
            'compass_position': self.compass_position
        }


@dataclass
class ParsedTag:
    """Represents a parsed tag with metadata and spatial positioning."""
    raw: str                    # Original tag with brackets, e.g., [CHAR_MEI]
    name: str                   # Tag name without brackets, e.g., CHAR_MEI
    category: TagCategory       # Inferred category
    position: int               # Position in source text (for parsing order)

    # Directional metadata
    is_directional: bool = False
    direction: Optional[str] = None  # N, E, S, W for directional tags
    base_name: Optional[str] = None  # Base name for directional tags

    # Spatial positioning in frame
    frame_position: Optional[FramePosition] = None

    def __hash__(self):
        return hash(self.raw)

    def __eq__(self, other):
        if isinstance(other, ParsedTag):
            return self.raw == other.raw
        return False


class TagParser:
    """
    Parses tags from text content and validates their format.

    Tag Format: [PREFIX_NAME] (e.g., [CHAR_MEI], [LOC_PALACE], [PROP_SWORD])
    - Must start with uppercase letter
    - Can contain uppercase letters, numbers, underscores
    - Special prefixes indicate category (CHAR_, LOC_, PROP_, etc.)
    - Directional suffix: _DIR_N, _DIR_E, _DIR_S, _DIR_W
    """
    
    def __init__(self):
        self._tag_pattern = re.compile(TAG_PATTERN)
        self._format_pattern = re.compile(TAG_FORMAT_PATTERN)
    
    def parse_text(self, text: str) -> List[ParsedTag]:
        """
        Extract all tags from text.
        
        Args:
            text: Text content to parse
            
        Returns:
            List of ParsedTag objects in order of appearance
        """
        tags = []
        seen_positions = set()
        
        for match in self._tag_pattern.finditer(text):
            position = match.start()
            if position in seen_positions:
                continue
            seen_positions.add(position)
            
            raw = match.group(0)  # e.g., [CHAR_MEI]
            name = match.group(1)  # TAG_NAME
            
            tag = self._create_parsed_tag(raw, name, position)
            tags.append(tag)
        
        return tags
    
    def parse_single(self, tag_str: str) -> ParsedTag:
        """
        Parse a single tag string.
        
        Args:
            tag_str: Tag string (with or without brackets)
            
        Returns:
            ParsedTag object
            
        Raises:
            InvalidTagFormatError: If tag format is invalid
        """
        # Normalize - add brackets if missing
        if not tag_str.startswith('['):
            tag_str = f'[{tag_str}]'
        
        match = self._tag_pattern.match(tag_str)
        if not match:
            raise InvalidTagFormatError(tag_str, TAG_PATTERN)
        
        return self._create_parsed_tag(tag_str, match.group(1), 0)
    
    def _create_parsed_tag(
        self,
        raw: str,
        name: str,
        position: int
    ) -> ParsedTag:
        """Create a ParsedTag with inferred metadata."""
        # Check for directional suffix
        is_directional = False
        direction = None
        base_name = None
        
        for suffix in DIRECTION_SUFFIXES:
            if name.endswith(suffix):
                is_directional = True
                direction = suffix[-1]  # N, E, S, or W
                base_name = name[:-len(suffix)]
                break
        
        # Infer category from prefix
        category = self._infer_category(name)
        
        return ParsedTag(
            raw=raw,
            name=name,
            category=category,
            position=position,
            is_directional=is_directional,
            direction=direction,
            base_name=base_name
        )
    
    def _infer_category(self, name: str) -> TagCategory:
        """Infer tag category from name prefix."""
        if name.startswith(TagPrefix.LOCATION.value):
            return TagCategory.LOCATION
        elif name.startswith(TagPrefix.PROP.value):
            return TagCategory.PROP
        elif name.startswith(TagPrefix.CONCEPT.value):
            return TagCategory.CONCEPT
        elif name.startswith(TagPrefix.EVENT.value):
            return TagCategory.EVENT
        else:
            # Default to character for unprefixed tags
            return TagCategory.CHARACTER
    
    def validate_format(self, tag_name: str) -> bool:
        """
        Validate that a tag name matches the expected format.
        
        Args:
            tag_name: Tag name without brackets
            
        Returns:
            True if valid, False otherwise
        """
        return bool(self._format_pattern.match(tag_name))
    
    def extract_unique_tags(self, text: str) -> Set[str]:
        """
        Extract unique tag names from text.
        
        Args:
            text: Text content to parse
            
        Returns:
            Set of unique tag names (without brackets)
        """
        return {tag.name for tag in self.parse_text(text)}
    
    def get_tags_by_category(
        self,
        text: str,
        category: TagCategory
    ) -> List[ParsedTag]:
        """
        Get all tags of a specific category from text.
        
        Args:
            text: Text content to parse
            category: Category to filter by
            
        Returns:
            List of matching ParsedTag objects
        """
        return [
            tag for tag in self.parse_text(text)
            if tag.category == category
        ]
    
    def replace_tags(
        self,
        text: str,
        replacements: dict
    ) -> str:
        """
        Replace tags in text with new values.

        Args:
            text: Original text
            replacements: Dict mapping old tag names to new tag names

        Returns:
            Text with replaced tags
        """
        result = text
        for old_name, new_name in replacements.items():
            old_tag = f'[{old_name}]'
            new_tag = f'[{new_name}]'
            result = result.replace(old_tag, new_tag)
        return result

    def extract_categorized_tags(
        self,
        text: str,
        valid_tags: Optional[Set[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Extract and categorize tags from text into character, location, and prop lists.

        Args:
            text: Text content to parse for tags
            valid_tags: Optional set of valid tags to filter against

        Returns:
            Dict with keys: "characters", "locations", "props"
            Each value is a list of unique tag names (without brackets)
        """
        result = {"characters": [], "locations": [], "props": []}

        for tag in self.parse_text(text):
            # Skip if not in valid_tags (when provided)
            if valid_tags and tag.name not in valid_tags:
                continue

            if tag.category == TagCategory.CHARACTER:
                if tag.name not in result["characters"]:
                    result["characters"].append(tag.name)
            elif tag.category == TagCategory.LOCATION:
                if tag.name not in result["locations"]:
                    result["locations"].append(tag.name)
            elif tag.category == TagCategory.PROP:
                if tag.name not in result["props"]:
                    result["props"].append(tag.name)

        return result


# Module-level singleton for convenience
_default_parser = None


def get_tag_parser() -> TagParser:
    """Get the default TagParser instance."""
    global _default_parser
    if _default_parser is None:
        _default_parser = TagParser()
    return _default_parser


def extract_categorized_tags(
    text: str,
    valid_tags: Optional[Set[str]] = None
) -> Dict[str, List[str]]:
    """
    Convenience function to extract categorized tags from text.

    Args:
        text: Text content to parse for tags
        valid_tags: Optional set of valid tags to filter against

    Returns:
        Dict with keys: "characters", "locations", "props"
    """
    return get_tag_parser().extract_categorized_tags(text, valid_tags)


class SpatialPositionCalculator:
    """
    Calculates spatial positions in frame based on camera direction and spatial relationships.

    This enables visual continuity by maintaining consistent spatial relationships:
    - If camera faces West and character enters from North, they appear on the right
    - If camera faces East and character enters from North, they appear on the left
    - Props and locations maintain consistent positions relative to camera direction
    """

    # Compass direction mappings (0° = North, clockwise)
    COMPASS_ANGLES = {
        'N': 0,
        'NE': 45,
        'E': 90,
        'SE': 135,
        'S': 180,
        'SW': 225,
        'W': 270,
        'NW': 315
    }

    # Reverse mapping
    ANGLE_TO_COMPASS = {v: k for k, v in COMPASS_ANGLES.items()}

    @staticmethod
    def calculate_frame_position(
        element_compass_direction: str,
        camera_facing_direction: str,
        depth: float = 0.5,
        vertical_offset: float = 0.0
    ) -> FramePosition:
        """
        Calculate where an element appears in frame based on its compass position
        relative to the camera's facing direction.

        Formula:
        1. Get element's compass angle (0-360°)
        2. Get camera's facing angle (0-360°)
        3. Calculate relative angle: (element_angle - camera_angle + 180) % 360
        4. Convert relative angle to screen position:
           - 0° (behind camera) → not visible
           - 90° (camera's right) → screen right (x = 1.0)
           - 180° (in front) → screen center (x = 0.0)
           - 270° (camera's left) → screen left (x = -1.0)

        Args:
            element_compass_direction: Where element is (N, NE, E, SE, S, SW, W, NW)
            camera_facing_direction: Where camera faces (N, E, S, W)
            depth: Depth in frame (0.0 = foreground, 1.0 = background)
            vertical_offset: Vertical offset (-1.0 to 1.0)

        Returns:
            FramePosition with calculated coordinates

        Example:
            Camera facing West (270°), door is to the North (0°):
            - Relative angle: (0 - 270 + 180) % 360 = 270° (camera's left)
            - Screen position: x = -1.0 (left side)
            - Result: Door appears on left side of frame

            Camera facing East (90°), same door to the North (0°):
            - Relative angle: (0 - 90 + 180) % 360 = 90° (camera's right)
            - Screen position: x = 1.0 (right side)
            - Result: Door appears on right side of frame
        """
        # Get angles
        element_angle = SpatialPositionCalculator.COMPASS_ANGLES.get(
            element_compass_direction.upper(), 0
        )
        camera_angle = SpatialPositionCalculator.COMPASS_ANGLES.get(
            camera_facing_direction.upper(), 0
        )

        # Calculate relative angle (what direction is element from camera's POV)
        # Add 180 because camera faces forward, so forward is 180° from camera position
        relative_angle = (element_angle - camera_angle + 180) % 360

        # Convert to screen coordinates
        # 0° = directly ahead (center)
        # 90° = to the right
        # 180° = behind (not visible)
        # 270° = to the left

        # Calculate x position using sine (left-right)
        # sin(90°) = 1.0 (right), sin(270°) = -1.0 (left), sin(0°/180°) = 0.0 (center)
        import math
        x = math.sin(math.radians(relative_angle))

        # Calculate visibility (elements behind camera have low visibility)
        # cos(0°) = 1.0 (ahead), cos(180°) = -1.0 (behind)
        visibility = math.cos(math.radians(relative_angle))

        # Clamp x to valid range
        x = max(-1.0, min(1.0, x))

        # Determine screen side
        if x < -0.33:
            screen_side = "left"
        elif x > 0.33:
            screen_side = "right"
        else:
            screen_side = "center"

        # Determine screen height
        y = vertical_offset
        if y < -0.33:
            screen_height = "bottom"
        elif y > 0.33:
            screen_height = "top"
        else:
            screen_height = "middle"

        # Determine depth layer
        if depth < 0.33:
            depth_layer = "foreground"
        elif depth > 0.66:
            depth_layer = "background"
        else:
            depth_layer = "mid"

        return FramePosition(
            x=round(x, 3),
            y=round(y, 3),
            z=round(depth, 3),
            screen_side=screen_side,
            screen_height=screen_height,
            depth_layer=depth_layer,
            compass_position=element_compass_direction.upper()
        )

    @staticmethod
    def calculate_relative_position(
        from_direction: str,
        to_direction: str
    ) -> str:
        """
        Calculate relative position between two compass directions.

        Args:
            from_direction: Starting direction (N, E, S, W, etc.)
            to_direction: Target direction

        Returns:
            Relative position description (e.g., "to the right", "behind", "ahead left")
        """
        from_angle = SpatialPositionCalculator.COMPASS_ANGLES.get(from_direction.upper(), 0)
        to_angle = SpatialPositionCalculator.COMPASS_ANGLES.get(to_direction.upper(), 0)

        relative = (to_angle - from_angle) % 360

        # Map to relative descriptions
        if relative < 22.5 or relative >= 337.5:
            return "directly ahead"
        elif 22.5 <= relative < 67.5:
            return "ahead right"
        elif 67.5 <= relative < 112.5:
            return "to the right"
        elif 112.5 <= relative < 157.5:
            return "behind right"
        elif 157.5 <= relative < 202.5:
            return "directly behind"
        elif 202.5 <= relative < 247.5:
            return "behind left"
        elif 247.5 <= relative < 292.5:
            return "to the left"
        else:  # 292.5 <= relative < 337.5
            return "ahead left"

    @staticmethod
    def get_opposite_direction(direction: str) -> str:
        """Get opposite compass direction."""
        opposites = {
            'N': 'S', 'S': 'N',
            'E': 'W', 'W': 'E',
            'NE': 'SW', 'SW': 'NE',
            'NW': 'SE', 'SE': 'NW'
        }
        return opposites.get(direction.upper(), direction)

    @staticmethod
    def rotate_direction(direction: str, degrees: int) -> str:
        """
        Rotate a compass direction by specified degrees.

        Args:
            direction: Starting direction
            degrees: Degrees to rotate (positive = clockwise)

        Returns:
            New direction after rotation
        """
        current_angle = SpatialPositionCalculator.COMPASS_ANGLES.get(direction.upper(), 0)
        new_angle = (current_angle + degrees) % 360

        # Find closest compass direction
        closest = min(
            SpatialPositionCalculator.COMPASS_ANGLES.items(),
            key=lambda x: min(abs(x[1] - new_angle), 360 - abs(x[1] - new_angle))
        )
        return closest[0]

