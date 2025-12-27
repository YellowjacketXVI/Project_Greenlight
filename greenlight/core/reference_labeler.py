"""
Reference Image Auto-Labeler

Automatically labels reference images with a red strip containing the tag name.
Overwrites originals - designed to run automatically when images are added to
reference folders.

Label format: Red background strip at top with black text "[TAG_NAME]"

Usage:
    from greenlight.core.reference_labeler import label_image, label_folder, label_all_references

    # Label single image (overwrites original)
    label_image(image_path, "CHAR_MEI")

    # Label all images in a tag folder
    label_folder(folder_path, "CHAR_MEI")

    # Label all references in project
    label_all_references(project_path)
"""

from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from greenlight.core.logging_config import get_logger

logger = get_logger("core.reference_labeler")

# Label styling
LABEL_HEIGHT_RATIO = 0.06  # 6% of image height
MIN_LABEL_HEIGHT = 40
MAX_LABEL_HEIGHT = 80
LABEL_BG_COLOR = (200, 30, 30)  # Red background
LABEL_TEXT_COLOR = (0, 0, 0)  # Black text
SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

# Marker to detect already-labeled images (embedded in metadata or filename check)
LABEL_MARKER = "_GL_LABELED_"


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """Get a bold system font."""
    font_paths = [
        "C:/Windows/Fonts/arialbd.ttf",  # Arial Bold
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def is_already_labeled(image_path: Path) -> bool:
    """Check if image has already been labeled by checking for red strip at top."""
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')

            width, height = img.size
            # Sample pixels from the top strip area
            sample_y = min(20, height // 20)

            # Check multiple points across the top
            red_count = 0
            sample_points = 5
            for i in range(sample_points):
                x = int((i + 0.5) * width / sample_points)
                pixel = img.getpixel((x, sample_y))
                # Check if pixel is reddish (high red, low green/blue)
                if pixel[0] > 150 and pixel[1] < 100 and pixel[2] < 100:
                    red_count += 1

            # If majority of samples are red, it's labeled
            return red_count >= 3
    except Exception:
        return False


def label_image(image_path: Path, tag_name: str, force: bool = False) -> bool:
    """
    Label an image with a red strip at the top containing the tag name.
    Overwrites the original image.

    Args:
        image_path: Path to image file
        tag_name: Tag name to display (e.g., "CHAR_MEI")
        force: If True, relabel even if already labeled

    Returns:
        True if labeled, False if skipped or failed
    """
    image_path = Path(image_path)

    if not image_path.exists():
        logger.warning(f"Image not found: {image_path}")
        return False

    if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False

    # Check if already labeled
    if not force and is_already_labeled(image_path):
        logger.debug(f"Already labeled: {image_path.name}")
        return False

    try:
        with Image.open(image_path) as img:
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            width, height = img.size

            # Calculate label strip height
            label_height = max(MIN_LABEL_HEIGHT, min(MAX_LABEL_HEIGHT, int(height * LABEL_HEIGHT_RATIO)))

            # Create new image with space for label
            new_height = height + label_height
            labeled_img = Image.new('RGB', (width, new_height), LABEL_BG_COLOR)

            # Paste original image below the label strip
            labeled_img.paste(img, (0, label_height))

            # Draw label text
            draw = ImageDraw.Draw(labeled_img)

            # Format tag text
            display_text = f"[{tag_name}]"

            # Find font size that fits
            font_size = label_height - 10
            font = get_font(font_size)

            # Get text bounding box
            bbox = draw.textbbox((0, 0), display_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Reduce font if text too wide
            while text_width > width - 20 and font_size > 12:
                font_size -= 2
                font = get_font(font_size)
                bbox = draw.textbbox((0, 0), display_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

            # Center text in label strip
            x = (width - text_width) // 2
            y = (label_height - text_height) // 2

            # Draw text
            draw.text((x, y), display_text, font=font, fill=LABEL_TEXT_COLOR)

            # Save back to original path
            # Determine format
            save_format = 'JPEG' if image_path.suffix.lower() in ['.jpg', '.jpeg'] else 'PNG'

            if save_format == 'JPEG':
                labeled_img.save(image_path, format=save_format, quality=95)
            else:
                labeled_img.save(image_path, format=save_format)

            logger.info(f"Labeled: {image_path.name} with [{tag_name}]")
            return True

    except Exception as e:
        logger.error(f"Failed to label {image_path}: {e}")
        return False


def label_folder(folder_path: Path, tag_name: Optional[str] = None, force: bool = False) -> int:
    """
    Label all images in a folder with the tag name.

    Args:
        folder_path: Path to folder containing images
        tag_name: Tag name (defaults to folder name if not provided)
        force: If True, relabel already-labeled images

    Returns:
        Number of images labeled
    """
    folder_path = Path(folder_path)

    if not folder_path.exists() or not folder_path.is_dir():
        logger.warning(f"Folder not found: {folder_path}")
        return 0

    # Use folder name as tag if not provided
    if tag_name is None:
        tag_name = folder_path.name

    count = 0
    for img_file in folder_path.iterdir():
        if img_file.is_file() and img_file.suffix.lower() in SUPPORTED_EXTENSIONS:
            if label_image(img_file, tag_name, force=force):
                count += 1

    return count


def label_all_references(project_path: Path, force: bool = False) -> dict:
    """
    Label all reference images in a project's references folder.

    Scans references/{TAG}/ folders and labels all images with their tag.

    Args:
        project_path: Path to project root
        force: If True, relabel already-labeled images

    Returns:
        Dict mapping tag names to count of images labeled
    """
    project_path = Path(project_path)
    refs_dir = project_path / "references"

    if not refs_dir.exists():
        logger.warning(f"References directory not found: {refs_dir}")
        return {}

    results = {}

    for tag_folder in refs_dir.iterdir():
        if not tag_folder.is_dir():
            continue

        tag_name = tag_folder.name

        # Only process valid tag folders
        if not (tag_name.startswith("CHAR_") or
                tag_name.startswith("LOC_") or
                tag_name.startswith("PROP_")):
            continue

        count = label_folder(tag_folder, tag_name, force=force)

        if count > 0:
            results[tag_name] = count
            logger.info(f"[{tag_name}]: {count} images labeled")

    total = sum(results.values())
    if total > 0:
        logger.info(f"Total: {total} images labeled across {len(results)} tags")

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: py -m greenlight.core.reference_labeler <project_path> [--force]")
        sys.exit(1)

    project = Path(sys.argv[1])
    force = "--force" in sys.argv

    print(f"Labeling references in: {project}")
    results = label_all_references(project, force=force)

    if results:
        print(f"\nLabeled images:")
        for tag, count in results.items():
            print(f"  [{tag}]: {count}")
    else:
        print("No images needed labeling.")
