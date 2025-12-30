"""
Project Models
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ProjectStatus(str, Enum):
    """Project status enum."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectCreate(BaseModel):
    """Create project request."""
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1)
    genre: Optional[str] = None
    world_config: Optional[Dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    """Update project request."""
    title: Optional[str] = None
    prompt: Optional[str] = None
    genre: Optional[str] = None
    scale: Optional[str] = None
    status: Optional[ProjectStatus] = None
    world_config: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    """Project response model."""
    id: str
    user_id: str
    title: str
    prompt: str
    genre: Optional[str] = None
    scale: Optional[str] = None
    status: str = "draft"
    world_config: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OutlineCreate(BaseModel):
    """Create outline request."""
    project_id: str
    layer: int = Field(ge=1, le=6)
    content: Dict[str, Any]
    status: str = "draft"


class OutlineResponse(BaseModel):
    """Outline response model."""
    id: str
    project_id: str
    layer: int
    content: Dict[str, Any]
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DraftCreate(BaseModel):
    """Create draft request."""
    project_id: str
    scene_id: str
    content: str
    version: int = 1


class DraftResponse(BaseModel):
    """Draft response model."""
    id: str
    project_id: str
    scene_id: str
    content: str
    version: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

