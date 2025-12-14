"""
Greenlight ID System - Hierarchical Naming Convention

Establishes clear definitions for Scene, Frame, and Camera identifiers
across all pipelines and data structures.

## Scene.Frame.Camera Notation System (CANONICAL)

The unified notation format is: `{scene}.{frame}.c{letter}`

| Component | Position | Format | Examples |
|-----------|----------|--------|----------|
| Scene     | X.x.x    | Integer | 1, 2, 8 |
| Frame     | x.X.x    | Integer | 1.1, 1.2, 2.3 |
| Camera    | x.x.X    | Letter  | 1.1.cA, 1.2.cB, 2.3.cC |

Hierarchy:
    Scene → Frame → Camera

Format:
    Scene:  {scene_number}           (e.g., 1, 2, 8)
    Frame:  {scene}.{frame}          (e.g., 1.1, 1.2, 2.3)
    Camera: {scene}.{frame}.c{letter} (e.g., 1.1.cA, 1.1.cB, 2.3.cC)

Examples:
    1                       - Scene 1
    1.1                     - Scene 1, Frame 1
    1.1.cA                  - Scene 1, Frame 1, Camera A
    1.1.cB                  - Scene 1, Frame 1, Camera B (different angle, same frame)
    1.2.cA                  - Scene 1, Frame 2, Camera A
    2.1.cA                  - Scene 2, Frame 1, Camera A

Director Pipeline operates at Camera level:
    Input:  Frames (1.1, 1.2, 2.1)
    Output: Cameras (1.1.cA, 1.1.cB, 1.2.cA, 1.2.cB, 1.2.cC)

Beat Marker Format: ## Beat: scene.{N}.{XX} (e.g., ## Beat: scene.1.01)
Scene Marker Format: ## Scene {N}: (e.g., ## Scene 1:)
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum


class IDType(Enum):
    """Type of identifier."""
    SCENE = "scene"
    FRAME = "frame"
    CAMERA = "camera"
    UNKNOWN = "unknown"


@dataclass
class ParsedID:
    """Parsed hierarchical ID.

    Uses canonical Scene.Frame.Camera notation:
    - Scene: {scene_number} (e.g., 1, 2, 8)
    - Frame: {scene}.{frame} (e.g., 1.1, 1.2, 2.3)
    - Camera: {scene}.{frame}.c{letter} (e.g., 1.1.cA, 1.2.cB)
    """
    id_type: IDType
    scene_number: int
    frame_number: Optional[int] = None
    camera_letter: Optional[str] = None
    raw_id: str = ""
    beat_number: Optional[int] = None  # For beat markers: scene.X.XX

    def __str__(self) -> str:
        """Return the canonical ID string."""
        if self.id_type == IDType.SCENE:
            # If we have a beat number, return beat ID format
            if self.beat_number is not None:
                return f"scene.{self.scene_number}.{self.beat_number:02d}"
            # Otherwise, scene ID is just the scene number
            return str(self.scene_number)
        elif self.id_type == IDType.FRAME:
            # Frame ID: scene.frame (e.g., 1.1, 2.3)
            return f"{self.scene_number}.{self.frame_number}"
        elif self.id_type == IDType.CAMERA:
            # Camera ID: scene.frame.cX (e.g., 1.1.cA)
            return f"{self.scene_number}.{self.frame_number}.c{self.camera_letter}"
        return self.raw_id

    @property
    def scene_id(self) -> str:
        """Get the scene ID for this element (just the scene number)."""
        return str(self.scene_number)

    @property
    def frame_id(self) -> str:
        """Get the frame ID for this element.

        Format: {scene}.{frame} (e.g., 1.1, 2.3)
        """
        if self.frame_number is None:
            return f"{self.scene_number}.1"
        return f"{self.scene_number}.{self.frame_number}"

    @property
    def camera_id(self) -> str:
        """Get the camera ID for this element.

        Format: {scene}.{frame}.c{letter} (e.g., 1.1.cA, 2.3.cB)
        """
        if self.camera_letter is None:
            return f"{self.scene_number}.{self.frame_number or 1}.cA"
        return f"{self.scene_number}.{self.frame_number or 1}.c{self.camera_letter}"

    @property
    def beat_id(self) -> str:
        """Get the beat ID for this element.

        Format: scene.{N}.{XX} (e.g., scene.1.01)
        Used in beat markers: ## Beat: scene.1.01
        """
        beat = self.beat_number or self.frame_number or 1
        return f"scene.{self.scene_number}.{beat:02d}"


class IDParser:
    """Parser for hierarchical IDs.

    Canonical Scene.Frame.Camera Notation:
    - Scene: Just an integer (e.g., 1, 2, 8)
    - Frame: {scene}.{frame} (e.g., 1.1, 2.3)
    - Camera: {scene}.{frame}.c{letter} (e.g., 1.1.cA, 2.3.cB)
    - Beat Marker: scene.{N}.{XX} (e.g., scene.1.01)
    """

    # Canonical regex patterns per .augment-guidelines
    CAMERA_PATTERN = re.compile(r'^(\d+)\.(\d+)\.c([A-Z])$')  # 1.1.cA
    FRAME_PATTERN = re.compile(r'^(\d+)\.(\d+)$')  # 1.1 (scene.frame)
    SCENE_PATTERN = re.compile(r'^(\d+)$')  # Just scene number
    BEAT_PATTERN = re.compile(r'^scene\.(\d+)\.(\d+)$')  # scene.1.01

    # Legacy patterns for backward compatibility
    LEGACY_BEAT_PATTERN = re.compile(r'^S(\d+)B(\d+)$')  # S01B01
    LEGACY_SHOT_PATTERN = re.compile(r'^(\d+)\.(\d+)([a-z]?)$')  # 1.1, 1.1a
    LEGACY_FRAME_PATTERN = re.compile(r'^(\d+)\.frame\.(\d+)$')  # Old 1.frame.01 format

    @classmethod
    def parse(cls, id_string: str) -> ParsedID:
        """
        Parse an ID string into its components.

        Args:
            id_string: ID to parse (e.g., "1.1.cA", "1.1", "1", "scene.1.01")

        Returns:
            ParsedID with extracted components
        """
        id_string = id_string.strip()
        # Remove brackets if present (e.g., "[1.1.cA]" -> "1.1.cA")
        if id_string.startswith('[') and id_string.endswith(']'):
            id_string = id_string[1:-1]
        
        # Try camera pattern first (most specific): 1.1.cA
        match = cls.CAMERA_PATTERN.match(id_string)
        if match:
            return ParsedID(
                id_type=IDType.CAMERA,
                scene_number=int(match.group(1)),
                frame_number=int(match.group(2)),
                camera_letter=match.group(3),
                raw_id=id_string
            )

        # Try beat pattern: scene.1.01
        match = cls.BEAT_PATTERN.match(id_string)
        if match:
            return ParsedID(
                id_type=IDType.SCENE,
                scene_number=int(match.group(1)),
                beat_number=int(match.group(2)),
                raw_id=id_string
            )

        # Try legacy frame pattern: 1.frame.01 (deprecated)
        match = cls.LEGACY_FRAME_PATTERN.match(id_string)
        if match:
            return ParsedID(
                id_type=IDType.FRAME,
                scene_number=int(match.group(1)),
                frame_number=int(match.group(2)),
                raw_id=id_string
            )

        # Try canonical frame pattern: 1.1 (scene.frame)
        match = cls.FRAME_PATTERN.match(id_string)
        if match:
            return ParsedID(
                id_type=IDType.FRAME,
                scene_number=int(match.group(1)),
                frame_number=int(match.group(2)),
                raw_id=id_string
            )

        # Try scene pattern: just a number
        match = cls.SCENE_PATTERN.match(id_string)
        if match:
            return ParsedID(
                id_type=IDType.SCENE,
                scene_number=int(match.group(1)),
                raw_id=id_string
            )

        # Try legacy beat pattern (S01B01)
        match = cls.LEGACY_BEAT_PATTERN.match(id_string)
        if match:
            return ParsedID(
                id_type=IDType.SCENE,
                scene_number=int(match.group(1)),
                beat_number=int(match.group(2)),
                raw_id=id_string
            )

        # Try legacy shot pattern (1.1a - lowercase camera letter)
        match = cls.LEGACY_SHOT_PATTERN.match(id_string)
        if match:
            scene = int(match.group(1))
            frame = int(match.group(2))
            suffix = match.group(3)

            if suffix:
                # Has letter suffix - treat as camera
                return ParsedID(
                    id_type=IDType.CAMERA,
                    scene_number=scene,
                    frame_number=frame,
                    camera_letter=suffix.upper(),
                    raw_id=id_string
                )
            # Note: Without suffix, this would match FRAME_PATTERN above

        # Unknown format
        return ParsedID(
            id_type=IDType.UNKNOWN,
            scene_number=0,
            raw_id=id_string
        )

    @classmethod
    def is_valid_camera_id(cls, id_string: str) -> bool:
        """Check if string is a valid camera ID."""
        return bool(cls.CAMERA_PATTERN.match(id_string))

    @classmethod
    def is_valid_frame_id(cls, id_string: str) -> bool:
        """Check if string is a valid frame ID."""
        return bool(cls.FRAME_PATTERN.match(id_string))

    @classmethod
    def is_valid_scene_id(cls, id_string: str) -> bool:
        """Check if string is a valid scene ID."""
        return bool(cls.SCENE_PATTERN.match(id_string))


class IDGenerator:
    """Generator for hierarchical IDs.

    Canonical Scene.Frame.Camera Notation:
    - Scene: {scene_number} (e.g., 1, 2, 8)
    - Frame: {scene}.{frame} (e.g., 1.1, 2.3)
    - Camera: {scene}.{frame}.c{letter} (e.g., 1.1.cA, 2.3.cB)
    - Beat: scene.{N}.{XX} (e.g., scene.1.01) - for beat markers
    """

    @staticmethod
    def scene_id(scene_number: int) -> str:
        """Generate a scene ID (just the scene number)."""
        return str(scene_number)

    @staticmethod
    def beat_id(scene_number: int, beat_number: int = 1) -> str:
        """Generate a beat ID for beat markers.

        Format: scene.{N}.{XX} (e.g., scene.1.01)
        Used in: ## Beat: scene.1.01
        """
        return f"scene.{scene_number}.{beat_number:02d}"

    @staticmethod
    def frame_id(scene_number: int, frame_number: int) -> str:
        """Generate a frame ID.

        Format: {scene}.{frame} (e.g., 1.1, 2.3)
        """
        return f"{scene_number}.{frame_number}"

    @staticmethod
    def camera_id(scene_number: int, frame_number: int, camera_letter: str) -> str:
        """Generate a camera ID.

        Format: {scene}.{frame}.c{letter} (e.g., 1.1.cA, 2.3.cB)
        """
        return f"{scene_number}.{frame_number}.c{camera_letter.upper()}"

    @staticmethod
    def camera_block(scene_number: int, frame_number: int, camera_letter: str, shot_type: str = "Wide") -> str:
        """Generate a camera block notation.

        Format: [{scene}.{frame}.c{letter}] ({shot_type})
        Example: [1.1.cA] (Wide)
        """
        return f"[{scene_number}.{frame_number}.c{camera_letter.upper()}] ({shot_type})"

    @staticmethod
    def next_camera_letter(existing_cameras: list) -> str:
        """
        Get the next camera letter for a frame.

        Args:
            existing_cameras: List of existing camera IDs for this frame

        Returns:
            Next available camera letter (A, B, C, etc.)
        """
        if not existing_cameras:
            return 'A'

        # Extract letters from existing cameras
        letters = []
        for cam_id in existing_cameras:
            parsed = IDParser.parse(cam_id)
            if parsed.camera_letter:
                letters.append(parsed.camera_letter)

        if not letters:
            return 'A'

        # Find next letter
        last_letter = max(letters)
        next_ord = ord(last_letter) + 1

        if next_ord > ord('Z'):
            raise ValueError("Exceeded maximum camera letters (A-Z)")

        return chr(next_ord)


def convert_legacy_to_new(legacy_id: str) -> str:
    """
    Convert legacy ID format to canonical Scene.Frame.Camera format.

    Examples:
        S01B01 → scene.1.01 (beat marker)
        1.frame.01 → 1.1 (frame ID)
        1.1a → 1.1.cA (camera ID)
        1 → 1 (scene ID)
    """
    parsed = IDParser.parse(legacy_id)
    return str(parsed)


def get_hierarchy_level(id_string: str) -> IDType:
    """Get the hierarchy level of an ID."""
    parsed = IDParser.parse(id_string)
    return parsed.id_type


