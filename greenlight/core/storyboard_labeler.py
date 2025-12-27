"""
Storyboard Auto-Labeler

Renames unlabeled media files in storyboard_output/generated/ to match
the scene.frame.camera notation from visual_script.json.

Note: Storyboard images do NOT get visual labels - only reference images do.

Usage:
    from greenlight.core.storyboard_labeler import label_storyboard_media
    label_storyboard_media(project_path)

Or run directly:
    py -m greenlight.core.storyboard_labeler "C:/path/to/project"
"""

import json
import re
from pathlib import Path
from typing import List, Tuple

from greenlight.core.logging_config import get_logger

logger = get_logger("core.storyboard_labeler")

# Supported media extensions
MEDIA_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.mov', '.avi'}


def get_frame_ids_from_visual_script(project_path: Path) -> List[str]:
    """Extract ordered frame IDs from visual_script.json."""
    visual_script_path = project_path / "storyboard" / "visual_script.json"
    
    if not visual_script_path.exists():
        logger.warning(f"Visual script not found: {visual_script_path}")
        return []
    
    try:
        data = json.loads(visual_script_path.read_text(encoding='utf-8'))
        frame_ids = []
        
        for scene in data.get("scenes", []):
            for frame in scene.get("frames", []):
                frame_id = frame.get("frame_id", frame.get("id", ""))
                if frame_id:
                    # Clean the frame_id
                    clean_id = frame_id.replace("[", "").replace("]", "")
                    frame_ids.append(clean_id)
        
        return frame_ids
    except Exception as e:
        logger.error(f"Error reading visual script: {e}")
        return []


def is_already_labeled(filename: str) -> bool:
    """Check if a filename matches the scene.frame.camera pattern."""
    # Pattern: 1.1.cA.png, 2.3.cB.jpg, etc.
    pattern = r'^\d+\.\d+\.c[A-Z]\.[a-z]+$'
    return bool(re.match(pattern, filename, re.IGNORECASE))


def get_unlabeled_media(folder: Path) -> List[Path]:
    """Get all unlabeled media files in the folder."""
    unlabeled = []
    
    if not folder.exists():
        return unlabeled
    
    for file in folder.iterdir():
        if file.is_file() and file.suffix.lower() in MEDIA_EXTENSIONS:
            if not is_already_labeled(file.name):
                unlabeled.append(file)
    
    # Sort by modification time (oldest first) to maintain order
    unlabeled.sort(key=lambda f: f.stat().st_mtime)
    return unlabeled


def label_storyboard_media(project_path: Path, dry_run: bool = False) -> List[Tuple[str, str]]:
    """
    Rename unlabeled media files in storyboard_output/generated/ to match frame IDs.

    Note: This only renames files - storyboard images do NOT get visual labels
    (only reference images get visual labels).

    Args:
        project_path: Path to the project directory
        dry_run: If True, only report what would be renamed without actually renaming

    Returns:
        List of (old_name, new_name) tuples for renamed files
    """
    project_path = Path(project_path)
    generated_dir = project_path / "storyboard_output" / "generated"

    if not generated_dir.exists():
        logger.info(f"Generated folder does not exist: {generated_dir}")
        return []

    # Get frame IDs from visual script
    frame_ids = get_frame_ids_from_visual_script(project_path)
    if not frame_ids:
        logger.warning("No frame IDs found in visual script")
        return []

    # Get unlabeled media files
    unlabeled = get_unlabeled_media(generated_dir)
    if not unlabeled:
        logger.info("No unlabeled media files found")
        return []

    # Find which frame IDs don't have corresponding files yet
    existing_labeled = set()
    for file in generated_dir.iterdir():
        if is_already_labeled(file.name):
            existing_labeled.add(file.stem)

    available_ids = [fid for fid in frame_ids if fid not in existing_labeled]

    # Rename unlabeled files
    renamed = []
    for i, file in enumerate(unlabeled):
        if i >= len(available_ids):
            logger.warning(f"More unlabeled files than available frame IDs. Skipping: {file.name}")
            break

        new_name = f"{available_ids[i]}{file.suffix.lower()}"
        new_path = generated_dir / new_name

        if dry_run:
            logger.info(f"[DRY RUN] Would rename: {file.name} -> {new_name}")
        else:
            try:
                file.rename(new_path)
                logger.info(f"Renamed: {file.name} -> {new_name}")
            except Exception as e:
                logger.error(f"Failed to rename {file.name}: {e}")
                continue

        renamed.append((file.name, new_name))

    return renamed


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: py -m greenlight.core.storyboard_labeler <project_path> [--dry-run]")
        sys.exit(1)
    
    project = Path(sys.argv[1])
    dry = "--dry-run" in sys.argv
    
    print(f"Labeling storyboard media in: {project}")
    results = label_storyboard_media(project, dry_run=dry)
    
    if results:
        print(f"\n{'Would rename' if dry else 'Renamed'} {len(results)} files:")
        for old, new in results:
            print(f"  {old} -> {new}")
    else:
        print("No files to rename.")

