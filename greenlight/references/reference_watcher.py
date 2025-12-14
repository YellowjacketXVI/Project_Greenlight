"""
Reference Image Watcher - Auto-labels reference images when added to tag folders.

Monitors the references/{TAG}/ directories and automatically creates labeled
versions of any new images with:
- Left-aligned: Tag in bracket notation (e.g., [CHAR_MEI])
- Right-aligned: Display name from world_config.json (e.g., Mei)
- Red background box with black text
- Minimum 50px font size

Usage:
    from greenlight.references.reference_watcher import ReferenceWatcher
    
    watcher = ReferenceWatcher(project_path)
    watcher.start()  # Starts background monitoring
    # ... later ...
    watcher.stop()
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Set, Callable
from datetime import datetime

from greenlight.core.logging_config import get_logger

logger = get_logger("references.watcher")

# Image extensions to watch
WATCHED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Reserved filenames to skip (already labeled or generated)
RESERVED_PATTERNS = ["_labeled", "_sheet", "_mosaic", "reference_labeled"]


class ReferenceWatcher:
    """Watches reference folders and auto-labels new images."""
    
    def __init__(
        self,
        project_path: Path,
        poll_interval: float = 2.0,
        on_label_complete: Optional[Callable[[Path, Path], None]] = None
    ):
        """
        Initialize the reference watcher.
        
        Args:
            project_path: Path to the project root
            poll_interval: Seconds between folder scans (default 2.0)
            on_label_complete: Optional callback(original_path, labeled_path) when labeling completes
        """
        self.project_path = Path(project_path)
        self.references_dir = self.project_path / "references"
        self.poll_interval = poll_interval
        self.on_label_complete = on_label_complete
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._known_files: Set[Path] = set()
        self._tag_names: Dict[str, str] = {}  # tag -> display name mapping
        self._lock = threading.Lock()
        
    def _load_tag_names(self) -> None:
        """Load tag to display name mapping from world_config.json."""
        world_config_path = self.project_path / "world_bible" / "world_config.json"
        
        if not world_config_path.exists():
            logger.debug("world_config.json not found, using tag names as display names")
            return
            
        try:
            data = json.loads(world_config_path.read_text(encoding="utf-8"))
            
            # Load characters
            for char in data.get("characters", []):
                tag = char.get("tag", "")
                name = char.get("name", "")
                if tag and name:
                    self._tag_names[tag] = name
                    
            # Load locations
            for loc in data.get("locations", []):
                tag = loc.get("tag", "")
                name = loc.get("name", "")
                if tag and name:
                    self._tag_names[tag] = name
                    
            # Load props
            for prop in data.get("props", []):
                tag = prop.get("tag", "")
                name = prop.get("name", "")
                if tag and name:
                    self._tag_names[tag] = name
                    
            logger.info(f"Loaded {len(self._tag_names)} tag names from world_config.json")
            
        except Exception as e:
            logger.warning(f"Failed to load world_config.json: {e}")
    
    def _get_display_name(self, tag: str) -> str:
        """Get display name for a tag, falling back to formatted tag name."""
        if tag in self._tag_names:
            return self._tag_names[tag]
        
        # Format tag as display name: CHAR_MEI -> Mei
        parts = tag.split("_")
        if len(parts) > 1 and parts[0] in ("CHAR", "LOC", "PROP", "CONCEPT", "EVENT", "ENV"):
            return " ".join(p.capitalize() for p in parts[1:])
        return tag.replace("_", " ").title()
    
    def _is_reserved_filename(self, filename: str) -> bool:
        """Check if filename is reserved (already processed)."""
        stem = Path(filename).stem.lower()
        return any(pattern in stem for pattern in RESERVED_PATTERNS)
    
    def _scan_references(self) -> Set[Path]:
        """Scan references directory for all image files."""
        files = set()

        if not self.references_dir.exists():
            return files

        for tag_dir in self.references_dir.iterdir():
            if not tag_dir.is_dir():
                continue

            for ext in WATCHED_EXTENSIONS:
                for img_path in tag_dir.glob(f"*{ext}"):
                    if not self._is_reserved_filename(img_path.name):
                        files.add(img_path)

        return files

    def _label_image(self, image_path: Path) -> Optional[Path]:
        """Create labeled version of an image."""
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.warning("Pillow not installed, cannot label images")
            return None

        # Get tag from parent directory name
        tag = image_path.parent.name
        display_name = self._get_display_name(tag)
        label = f"[{tag}]"

        # Output path
        labeled_path = image_path.parent / f"{image_path.stem}_labeled{image_path.suffix}"

        if labeled_path.exists():
            logger.debug(f"Labeled version already exists: {labeled_path.name}")
            return labeled_path

        try:
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)

            # Minimum 50px font, scale up for larger images
            font_size = max(50, img.width // 20)
            font = None

            for font_name in ["arialbd.ttf", "Arial Bold.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"]:
                try:
                    font = ImageFont.truetype(font_name, font_size)
                    break
                except Exception:
                    continue

            if font is None:
                font = ImageFont.load_default()

            # Calculate text sizes
            label_bbox = draw.textbbox((0, 0), label, font=font)
            label_width = label_bbox[2] - label_bbox[0]
            label_height = label_bbox[3] - label_bbox[1]

            name_bbox = draw.textbbox((0, 0), display_name, font=font)
            name_width = name_bbox[2] - name_bbox[0]

            # Padding and spacing
            padding_h = max(20, font_size // 3)
            padding_v = max(15, font_size // 4)
            margin = max(10, img.width // 50)
            spacing = max(40, font_size)

            # Box dimensions
            total_text_width = label_width + spacing + name_width
            box_width = total_text_width + padding_h * 2
            box_height = label_height + padding_v * 2

            # Position at top-left
            box_x = margin
            box_y = margin

            # Draw red background
            draw.rectangle(
                [box_x, box_y, box_x + box_width, box_y + box_height],
                fill=(255, 0, 0)
            )

            # Draw tag (left-aligned)
            text_y = box_y + padding_v
            draw.text((box_x + padding_h, text_y), label, fill=(0, 0, 0), font=font)

            # Draw display name (right-aligned)
            name_x = box_x + box_width - padding_h - name_width
            draw.text((name_x, text_y), display_name, fill=(0, 0, 0), font=font)

            # Save
            img.save(labeled_path, quality=95)
            logger.info(f"Created labeled image: {labeled_path.name}")

            return labeled_path

        except Exception as e:
            logger.error(f"Failed to label image {image_path.name}: {e}")
            return None

    def _watch_loop(self) -> None:
        """Background loop that watches for new files."""
        logger.info(f"Reference watcher started for: {self.references_dir}")

        # Initial scan
        self._load_tag_names()
        self._known_files = self._scan_references()

        while self._running:
            try:
                time.sleep(self.poll_interval)

                # Rescan for new files
                current_files = self._scan_references()
                new_files = current_files - self._known_files

                if new_files:
                    # Reload tag names in case world_config changed
                    self._load_tag_names()

                    for new_file in new_files:
                        logger.info(f"New reference image detected: {new_file.name}")
                        labeled_path = self._label_image(new_file)

                        if labeled_path and self.on_label_complete:
                            try:
                                self.on_label_complete(new_file, labeled_path)
                            except Exception as e:
                                logger.error(f"Callback error: {e}")

                self._known_files = current_files

            except Exception as e:
                logger.error(f"Watch loop error: {e}")
                time.sleep(5)  # Back off on error

    def start(self) -> None:
        """Start the background watcher thread."""
        if self._running:
            logger.warning("Watcher already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("Reference watcher started")

    def stop(self) -> None:
        """Stop the background watcher thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("Reference watcher stopped")

    def label_all_existing(self) -> int:
        """Label all existing unlabeled reference images.

        Returns:
            Number of images labeled
        """
        self._load_tag_names()
        files = self._scan_references()
        labeled_count = 0

        for img_path in files:
            labeled_path = img_path.parent / f"{img_path.stem}_labeled{img_path.suffix}"
            if not labeled_path.exists():
                if self._label_image(img_path):
                    labeled_count += 1

        logger.info(f"Labeled {labeled_count} existing images")
        return labeled_count


# Global watcher instance
_reference_watcher: Optional[ReferenceWatcher] = None


def get_reference_watcher() -> Optional[ReferenceWatcher]:
    """Get the global reference watcher instance."""
    return _reference_watcher


def setup_reference_watcher(
    project_path: Path,
    auto_start: bool = True
) -> ReferenceWatcher:
    """Setup and optionally start the global reference watcher.

    Args:
        project_path: Path to the project root
        auto_start: Whether to start watching immediately

    Returns:
        The ReferenceWatcher instance
    """
    global _reference_watcher

    # Stop existing watcher if any
    if _reference_watcher:
        _reference_watcher.stop()

    _reference_watcher = ReferenceWatcher(project_path)

    if auto_start:
        _reference_watcher.start()

    return _reference_watcher

