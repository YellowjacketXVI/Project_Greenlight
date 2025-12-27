"""
Reference Image Watcher - Auto-labels reference images when added to tag folders.

Monitors the references/{TAG}/ directories and automatically labels any new images
in-place with a red strip containing the [TAG] at the top of the image.

Uses greenlight.core.reference_labeler for consistent labeling with:
- Red background strip at top
- Black text with [TAG_NAME]
- Original image is overwritten (in-place labeling)

Usage:
    from greenlight.references.reference_watcher import ReferenceWatcher

    watcher = ReferenceWatcher(project_path)
    watcher.start()  # Starts background monitoring
    # ... later ...
    watcher.stop()
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional, Set, Callable

from greenlight.core.logging_config import get_logger

logger = get_logger("references.watcher")

# Image extensions to watch
WATCHED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Reserved filenames to skip - only skip actual processing artifacts
# All reference images including sheets, uploads, and generated should be labeled
RESERVED_PATTERNS = []  # No exclusions - label everything


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
        self._lock = threading.Lock()

    def _load_tag_names(self) -> None:
        """Placeholder for compatibility - labeling uses reference_labeler."""
        pass
    
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

    def _label_image(self, image_path: Path) -> bool:
        """Label an image in-place using reference_labeler.

        Returns:
            True if labeled, False if skipped or failed
        """
        try:
            from greenlight.core.reference_labeler import label_image, is_already_labeled
        except ImportError:
            logger.warning("reference_labeler not available")
            return False

        # Get tag from parent directory name
        tag = image_path.parent.name

        # Skip if already labeled
        if is_already_labeled(image_path):
            logger.debug(f"Already labeled: {image_path.name}")
            return False

        # Label in-place
        success = label_image(image_path, tag)
        if success:
            logger.info(f"Labeled: {image_path.name} with [{tag}]")
        return success

    def _watch_loop(self) -> None:
        """Background loop that watches for new files."""
        logger.info(f"Reference watcher started for: {self.references_dir}")

        # Initial scan - label any existing unlabeled images first
        self._load_tag_names()
        self._known_files = self._scan_references()

        # Label existing unlabeled images on startup
        for img_path in self._known_files:
            self._label_image(img_path)

        while self._running:
            try:
                time.sleep(self.poll_interval)

                # Rescan for new files
                current_files = self._scan_references()
                new_files = current_files - self._known_files

                if new_files:
                    for new_file in new_files:
                        logger.info(f"New reference image detected: {new_file.name}")
                        success = self._label_image(new_file)

                        if success and self.on_label_complete:
                            try:
                                self.on_label_complete(new_file, new_file)  # Same path since in-place
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
        """Label all existing unlabeled reference images in-place.

        Returns:
            Number of images labeled
        """
        self._load_tag_names()
        files = self._scan_references()
        labeled_count = 0

        for img_path in files:
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

