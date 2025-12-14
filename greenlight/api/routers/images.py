"""Images router for Project Greenlight API."""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/{image_path:path}")
async def get_image(image_path: str):
    """Serve an image file."""
    path = Path(image_path)
    
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    if not path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    # Validate it's an image
    valid_extensions = [".png", ".jpg", ".jpeg", ".webp", ".gif"]
    if path.suffix.lower() not in valid_extensions:
        raise HTTPException(status_code=400, detail="Invalid image format")
    
    # Determine media type
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = media_types.get(path.suffix.lower(), "application/octet-stream")
    
    return FileResponse(path, media_type=media_type)

