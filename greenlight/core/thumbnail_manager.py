"""
Thumbnail Manager for fast storyboard navigation.

Generates and caches small proxy images for quick loading.
Full-res images only loaded at 100% zoom or on explicit request.
"""

from pathlib import Path
from typing import Optional, Tuple, Dict
import hashlib
import threading

from greenlight.core.logging_config import get_logger

logger = get_logger("core.thumbnail_manager")

# Thumbnail sizes for different zoom levels
THUMB_SMALL = (160, 90)    # Grid mode, many columns
THUMB_MEDIUM = (320, 180)  # Row mode, multiple visible
THUMB_LARGE = (640, 360)   # Row mode, few visible


class ThumbnailManager:
    """
    Manages thumbnail generation and caching for storyboard images.
    
    Thumbnails are stored in .thumbnails/ subfolder next to original images.
    Uses lazy generation - thumbnails created on first access.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern for shared cache."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cache: Dict[str, 'CTkImage'] = {}  # In-memory cache
        self._cache_lock = threading.Lock()
        self._max_cache_size = 200  # Max cached thumbnails
    
    def get_thumbnail_path(self, image_path: Path, size: Tuple[int, int] = THUMB_MEDIUM) -> Path:
        """Get the path where thumbnail should be stored."""
        thumb_dir = image_path.parent / ".thumbnails"
        size_suffix = f"_{size[0]}x{size[1]}"
        thumb_name = f"{image_path.stem}{size_suffix}{image_path.suffix}"
        return thumb_dir / thumb_name
    
    def ensure_thumbnail(self, image_path: Path, size: Tuple[int, int] = THUMB_MEDIUM) -> Optional[Path]:
        """
        Ensure thumbnail exists, creating if necessary.
        Returns thumbnail path or None if failed.
        """
        if not image_path.exists():
            return None
            
        thumb_path = self.get_thumbnail_path(image_path, size)
        
        # Check if thumbnail exists and is newer than source
        if thumb_path.exists():
            if thumb_path.stat().st_mtime >= image_path.stat().st_mtime:
                return thumb_path
        
        # Generate thumbnail
        return self._generate_thumbnail(image_path, thumb_path, size)
    
    def _generate_thumbnail(self, source: Path, dest: Path, size: Tuple[int, int]) -> Optional[Path]:
        """Generate a thumbnail image."""
        try:
            from PIL import Image
            
            # Create thumbnail directory
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Open and resize
            with Image.open(source) as img:
                # Use LANCZOS for quality, but could use BILINEAR for speed
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Save as JPEG for smaller size (unless PNG with transparency)
                if source.suffix.lower() == '.png':
                    img.save(dest, 'PNG', optimize=True)
                else:
                    # Convert to RGB if needed (for JPEG)
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    img.save(dest, 'JPEG', quality=85, optimize=True)
            
            logger.debug(f"Generated thumbnail: {dest}")
            return dest
            
        except Exception as e:
            logger.warning(f"Failed to generate thumbnail for {source}: {e}")
            return None
    
    def get_ctk_image(self, image_path: Path, size: Tuple[int, int], 
                      use_thumbnail: bool = True) -> Optional['ctk.CTkImage']:
        """
        Get a CTkImage for display, using thumbnail if appropriate.
        
        Args:
            image_path: Path to the original image
            size: Display size (width, height)
            use_thumbnail: If True, use thumbnail for sizes <= THUMB_LARGE
        """
        import customtkinter as ctk
        from PIL import Image
        
        # Determine if we should use thumbnail
        if use_thumbnail and size[0] <= THUMB_LARGE[0] and size[1] <= THUMB_LARGE[1]:
            # Pick appropriate thumbnail size
            if size[0] <= THUMB_SMALL[0]:
                thumb_size = THUMB_SMALL
            elif size[0] <= THUMB_MEDIUM[0]:
                thumb_size = THUMB_MEDIUM
            else:
                thumb_size = THUMB_LARGE
            
            thumb_path = self.ensure_thumbnail(image_path, thumb_size)
            load_path = thumb_path if thumb_path else image_path
        else:
            # Load full resolution
            load_path = image_path
        
        # Check cache
        cache_key = f"{load_path}_{size[0]}x{size[1]}"
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        # Load and create CTkImage
        try:
            with Image.open(load_path) as img:
                img = img.resize(size, Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img.copy(), dark_image=img.copy(), size=size)
            
            # Cache it
            with self._cache_lock:
                if len(self._cache) >= self._max_cache_size:
                    # Remove oldest entries (simple FIFO)
                    keys = list(self._cache.keys())[:50]
                    for k in keys:
                        del self._cache[k]
                self._cache[cache_key] = ctk_img
            
            return ctk_img
            
        except Exception as e:
            logger.debug(f"Failed to load image {load_path}: {e}")
            return None
    
    def clear_cache(self):
        """Clear the in-memory image cache."""
        with self._cache_lock:
            self._cache.clear()
        logger.debug("Thumbnail cache cleared")


# Singleton accessor
def get_thumbnail_manager() -> ThumbnailManager:
    """Get the singleton ThumbnailManager instance."""
    return ThumbnailManager()

