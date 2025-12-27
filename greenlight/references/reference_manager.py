"""
Greenlight Reference Manager

Manages reference images for tags (characters, locations, props).
Integrates with TagRegistry for consistent tag handling.
"""

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from PIL import Image
import io

from greenlight.core.constants import TagCategory, VALID_DIRECTIONS, REFERENCES_DIR
from greenlight.core.logging_config import get_logger
from greenlight.tags.tag_registry import TagRegistry, TagEntry
from greenlight.tags.tag_parser import TagParser, ParsedTag

logger = get_logger("references.manager")


@dataclass
class ReferenceImage:
    """A reference image with metadata."""
    tag_name: str
    path: Path
    category: TagCategory
    direction: Optional[str] = None  # N, E, S, W for directional
    priority: int = 0  # Lower = higher priority
    
    def to_inline_data(self, aspect_ratio: str = None) -> Optional[Dict]:
        """Convert to inline_data format for API calls."""
        if not self.path.exists():
            return None
        
        try:
            with Image.open(self.path) as img:
                # Resize if aspect ratio specified
                if aspect_ratio:
                    img = _resize_to_aspect(img, aspect_ratio)
                
                # Convert to base64
                buffer = io.BytesIO()
                img_format = "PNG" if self.path.suffix.lower() == ".png" else "JPEG"
                img.save(buffer, format=img_format)
                b64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                mime_type = f"image/{img_format.lower()}"
                return {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": b64_data
                    }
                }
        except Exception as e:
            logger.error(f"Failed to load reference image {self.path}: {e}")
            return None


class ReferenceManager:
    """
    Manages reference images using the TagRegistry.
    
    Features:
    - Creates reference folders based on registered tags
    - Loads reference images by tag name
    - Supports directional references for locations (N/E/S/W)
    - Priority-based image selection
    - Extracts references needed for a shot based on tags in prompt
    """
    
    # Image file priority (lower = higher priority)
    # Note: Reference images are auto-labeled in-place with red tag strips
    IMAGE_PRIORITY = {
        "reference_sheet": 0,      # Character/prop reference sheet (auto-labeled)
        "sheet": 1,                # Any sheet variant
        "reference": 2,            # Primary reference
        "dir_n": 3,                # Directional north
        "dir_e": 4,
        "dir_s": 5,
        "dir_w": 6,
        "default": 10              # Any other image
    }
    
    SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
    
    def __init__(
        self,
        project_path: Path,
        tag_registry: TagRegistry = None
    ):
        """
        Initialize reference manager.

        Args:
            project_path: Path to project root
            tag_registry: Optional TagRegistry (creates new if not provided)

        Note:
            Reference images are stored in a flat structure: references/{TAG}/
            e.g., references/CHAR_MEI/, references/LOC_TEAHOUSE/
            This is consistent with ImageHandler and the project structure.
        """
        self.project_path = Path(project_path)
        self.tag_registry = tag_registry or TagRegistry()
        self.tag_parser = TagParser()

        # Base references directory (flat structure: references/{TAG}/)
        self.refs_base = self.project_path / REFERENCES_DIR

        # Cache for loaded references
        self._cache: Dict[str, List[ReferenceImage]] = {}
    
    def create_reference_folders(self) -> Dict[str, Path]:
        """
        Create reference folders for all registered tags.

        Uses flat structure: references/{TAG}/
        e.g., references/CHAR_MEI/, references/LOC_TEAHOUSE/

        Returns:
            Dict mapping tag names to created folder paths
        """
        created = {}

        # Ensure base references directory exists
        self.refs_base.mkdir(parents=True, exist_ok=True)

        for category in [TagCategory.CHARACTER, TagCategory.LOCATION, TagCategory.PROP]:
            for tag_entry in self.tag_registry.get_by_category(category):
                # Use tag name directly as folder name (e.g., CHAR_MEI)
                folder_path = self.refs_base / tag_entry.name
                folder_path.mkdir(exist_ok=True)
                created[tag_entry.name] = folder_path
                logger.debug(f"Created folder for [{tag_entry.name}]: {folder_path}")

        logger.info(f"Created {len(created)} reference folders")
        return created

    def get_reference_folder(self, tag_name: str) -> Optional[Path]:
        """Get the reference folder path for a tag.

        Uses flat structure: references/{TAG}/
        """
        # Normalize tag name (remove brackets if present)
        if tag_name.startswith('['):
            tag_name = tag_name[1:-1]

        # Direct path: references/{TAG}/
        folder_path = self.refs_base / tag_name
        return folder_path
    
    def scan_references(self, tag_name: str) -> List[ReferenceImage]:
        """
        Scan and return all reference images for a tag.

        Also scans subdirectories for cardinal views:
            references/{TAG}/{image_stem}/{image_stem}_dir_n.png

        Args:
            tag_name: Tag name (with or without brackets)

        Returns:
            List of ReferenceImage sorted by priority
        """
        # Normalize tag name
        if tag_name.startswith('['):
            tag_name = tag_name[1:-1]

        # Check cache
        if tag_name in self._cache:
            return self._cache[tag_name]

        folder = self.get_reference_folder(tag_name)
        if not folder or not folder.exists():
            return []

        # Get category
        try:
            entry = self.tag_registry.get(tag_name)
            category = entry.category
        except Exception:
            parsed = self.tag_parser.parse_single(tag_name)
            category = parsed.category

        references = []

        # Scan top-level files
        for file_path in folder.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                # Determine priority and direction
                priority, direction = self._get_image_priority(file_path, tag_name)

                ref = ReferenceImage(
                    tag_name=tag_name,
                    path=file_path,
                    category=category,
                    direction=direction,
                    priority=priority
                )
                references.append(ref)

            # Scan subdirectories for cardinal views
            elif file_path.is_dir():
                for subfile in file_path.iterdir():
                    if subfile.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                        priority, direction = self._get_image_priority(subfile, tag_name)
                        ref = ReferenceImage(
                            tag_name=tag_name,
                            path=subfile,
                            category=category,
                            direction=direction,
                            priority=priority
                        )
                        references.append(ref)

        # Sort by priority
        references.sort(key=lambda r: r.priority)

        # Cache results
        self._cache[tag_name] = references

        return references

    def scan_cardinal_views(self, tag_name: str) -> Dict[str, Path]:
        """
        Scan for cardinal view images for a location tag.

        Looks in subdirectories for files matching pattern:
            references/{TAG}/{subdir}/{subdir}_dir_{n|e|s|w}.png

        Args:
            tag_name: Location tag name

        Returns:
            Dict mapping direction ('N', 'E', 'S', 'W') to file path
        """
        # Normalize tag name
        if tag_name.startswith('['):
            tag_name = tag_name[1:-1]

        folder = self.get_reference_folder(tag_name)
        if not folder or not folder.exists():
            return {}

        cardinals = {}

        # Look in subdirectories
        for subdir in folder.iterdir():
            if not subdir.is_dir():
                continue

            for direction in VALID_DIRECTIONS:
                dir_lower = direction.lower()
                # Look for files matching pattern: {subdir_name}_dir_{direction}.png
                for ext in self.SUPPORTED_EXTENSIONS:
                    cardinal_file = subdir / f"{subdir.name}_dir_{dir_lower}{ext}"
                    if cardinal_file.exists():
                        cardinals[direction.upper()] = cardinal_file
                        break

        return cardinals

    def has_cardinal_views(self, tag_name: str) -> bool:
        """Check if a location tag has all 4 cardinal views."""
        cardinals = self.scan_cardinal_views(tag_name)
        return len(cardinals) == 4

    def _get_image_priority(self, file_path: Path, tag_name: str) -> Tuple[int, Optional[str]]:
        """
        Determine image priority and direction from filename.

        Note: All reference images are auto-labeled in-place with red tag strips,
        so we don't need separate priority for labeled vs unlabeled.

        Returns:
            Tuple of (priority, direction or None)
        """
        stem = file_path.stem.lower()

        # Reference sheets have highest priority
        if "reference_sheet" in stem:
            return self.IMAGE_PRIORITY["reference_sheet"], None

        if "sheet" in stem:
            return self.IMAGE_PRIORITY["sheet"], None

        # Check for directional views
        for direction in VALID_DIRECTIONS:
            if f"_dir_{direction.lower()}" in stem or f"_{direction.lower()}" == stem[-2:]:
                return self.IMAGE_PRIORITY[f"dir_{direction.lower()}"], direction

        if "reference" in stem:
            return self.IMAGE_PRIORITY["reference"], None

        return self.IMAGE_PRIORITY["default"], None

    def load_reference(
        self,
        tag_name: str,
        direction: str = None,
        aspect_ratio: str = None
    ) -> Optional[Dict]:
        """
        Load the best reference image for a tag.

        For directional tags (e.g., LOC_FLOWER_SHOP_DIR_E), automatically
        parses the direction and looks in cardinal subdirectories.

        Args:
            tag_name: Tag name (may include directional suffix like _DIR_N)
            direction: Optional direction (N/E/S/W) for locations
            aspect_ratio: Optional aspect ratio to resize to ("16:9", "9:16", "1:1")

        Returns:
            inline_data dict for API, or None if not found
        """
        # Parse tag to check for directional suffix
        parsed = self.tag_parser.parse_single(tag_name)

        # If tag has directional suffix, extract base name and direction
        lookup_name = tag_name
        if parsed.is_directional:
            lookup_name = parsed.base_name or tag_name
            direction = parsed.direction or direction

        references = self.scan_references(lookup_name)
        if not references:
            logger.debug(f"No references found for [{lookup_name}]")
            return None

        # If direction specified, try to find directional reference
        if direction:
            direction_upper = direction.upper()

            # First, try cardinal subdirectory structure
            cardinals = self.scan_cardinal_views(lookup_name)
            if direction_upper in cardinals:
                cardinal_path = cardinals[direction_upper]
                ref = ReferenceImage(
                    tag_name=lookup_name,
                    path=cardinal_path,
                    category=parsed.category,
                    direction=direction_upper,
                    priority=self.IMAGE_PRIORITY[f"dir_{direction.lower()}"]
                )
                result = ref.to_inline_data(aspect_ratio)
                if result:
                    logger.debug(f"Loaded cardinal reference for [{lookup_name}] dir={direction_upper}")
                    return result

            # Fall back to scanning all references for directional match
            for ref in references:
                if ref.direction and ref.direction.upper() == direction_upper:
                    result = ref.to_inline_data(aspect_ratio)
                    if result:
                        logger.debug(f"Loaded directional reference for [{lookup_name}] dir={direction_upper}")
                        return result

        # Return highest priority reference
        for ref in references:
            result = ref.to_inline_data(aspect_ratio)
            if result:
                logger.debug(f"Loaded reference for [{lookup_name}]")
                return result

        return None

    def get_references_for_shot(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        include_style: bool = False
    ) -> Tuple[List[str], List[Dict]]:
        """
        Get all reference images needed for a shot based on tags in prompt.

        This is the primary method for per-shot reference selection.
        Uses TagParser to extract tags, then loads references for each.

        Args:
            prompt: Shot prompt with [TAG] markers
            aspect_ratio: Target aspect ratio for images
            include_style: Whether to include style/mood references

        Returns:
            Tuple of (list of tag names used, list of inline_data dicts)
        """
        # Parse tags from prompt
        parsed_tags = self.tag_parser.parse_text(prompt)

        used_tags = []
        references = []

        for parsed in parsed_tags:
            tag_name = parsed.name
            direction = parsed.direction if parsed.is_directional else None

            # For directional tags, use base name for lookup
            lookup_name = parsed.base_name if parsed.is_directional else tag_name

            ref_data = self.load_reference(
                lookup_name,
                direction=direction,
                aspect_ratio=aspect_ratio
            )

            if ref_data:
                used_tags.append(tag_name)
                references.append(ref_data)
                logger.debug(f"Added reference for [{tag_name}]")

        logger.info(f"Shot references: {len(references)} images for {len(parsed_tags)} tags")
        return used_tags, references

    def clear_cache(self) -> None:
        """Clear the reference cache."""
        self._cache.clear()

    def load_tags_from_world_bible(self, world_bible_path: Path = None) -> int:
        """
        Load tags from WORLD_BIBLE.json into the TagRegistry.

        Args:
            world_bible_path: Path to WORLD_BIBLE.json (defaults to project_path/world_bible/WORLD_BIBLE.json)

        Returns:
            Number of tags loaded
        """
        if world_bible_path is None:
            world_bible_path = self.project_path / "world_bible" / "WORLD_BIBLE.json"

        if not world_bible_path.exists():
            logger.warning(f"World bible not found: {world_bible_path}")
            return 0

        try:
            with open(world_bible_path, 'r', encoding='utf-8') as f:
                world_bible = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load world bible: {e}")
            return 0

        count = 0

        # Load characters
        for char in world_bible.get('characters', []):
            tag_name = char.get('tag') or char.get('name', '').upper().replace(' ', '_')
            if tag_name:
                try:
                    self.tag_registry.register(
                        name=tag_name,
                        category=TagCategory.CHARACTER,
                        description=char.get('description', ''),
                        # Use description as fallback for visual_description since world_config only has 'description'
                        visual_description=char.get('visual_description', char.get('description', ''))
                    )
                    count += 1
                except Exception as e:
                    logger.debug(f"Tag {tag_name} already registered or invalid: {e}")

        # Load locations
        for loc in world_bible.get('locations', []):
            tag_name = loc.get('tag') or f"LOC_{loc.get('name', '').upper().replace(' ', '_')}"
            if tag_name:
                try:
                    self.tag_registry.register(
                        name=tag_name,
                        category=TagCategory.LOCATION,
                        description=loc.get('description', '')
                    )
                    count += 1
                except Exception as e:
                    logger.debug(f"Tag {tag_name} already registered or invalid: {e}")

        # Load props
        for prop in world_bible.get('props', []):
            tag_name = prop.get('tag') or f"PROP_{prop.get('name', '').upper().replace(' ', '_')}"
            if tag_name:
                try:
                    self.tag_registry.register(
                        name=tag_name,
                        category=TagCategory.PROP,
                        description=prop.get('description', '')
                    )
                    count += 1
                except Exception as e:
                    logger.debug(f"Tag {tag_name} already registered or invalid: {e}")

        logger.info(f"Loaded {count} tags from world bible")
        return count

    def get_missing_references(self) -> Dict[str, List[str]]:
        """
        Find registered tags that don't have reference images.

        Returns:
            Dict mapping category name to list of tags without references
        """
        missing = {
            "characters": [],
            "locations": [],
            "props": []
        }

        category_map = {
            TagCategory.CHARACTER: "characters",
            TagCategory.LOCATION: "locations",
            TagCategory.PROP: "props"
        }

        for category, key in category_map.items():
            for entry in self.tag_registry.get_by_category(category):
                refs = self.scan_references(entry.name)
                if not refs:
                    missing[key].append(entry.name)

        return missing


def _resize_to_aspect(img: Image.Image, aspect_ratio: str) -> Image.Image:
    """Resize image to match target aspect ratio."""
    ratios = {
        "16:9": (16, 9),
        "9:16": (9, 16),
        "1:1": (1, 1),
        "4:3": (4, 3),
        "3:4": (3, 4)
    }

    if aspect_ratio not in ratios:
        return img

    target_w, target_h = ratios[aspect_ratio]

    # Calculate new dimensions maintaining aspect ratio
    orig_w, orig_h = img.size
    target_ratio = target_w / target_h
    orig_ratio = orig_w / orig_h

    if orig_ratio > target_ratio:
        # Image is wider - crop width
        new_w = int(orig_h * target_ratio)
        left = (orig_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, orig_h))
    elif orig_ratio < target_ratio:
        # Image is taller - crop height
        new_h = int(orig_w / target_ratio)
        top = (orig_h - new_h) // 2
        img = img.crop((0, top, orig_w, top + new_h))

    return img

