"""
Writer Pipeline Models
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum


class WriterLayer(str, Enum):
    """Writer pipeline layers."""
    HIGH_LEVEL_OUTLINE = "high_level_outline"
    USER_CHECKPOINT_1 = "user_checkpoint_1"
    GRANULAR_OUTLINE = "granular_outline"
    USER_CHECKPOINT_2 = "user_checkpoint_2"
    SCALE_DETERMINATION = "scale_determination"
    WRITE_OUT = "write_out"


class LayerStatus(BaseModel):
    """Status of a pipeline layer."""
    layer: WriterLayer
    status: str  # pending, active, awaiting_approval, approved, completed
    content: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class StartWriterInput(BaseModel):
    """Input for starting the writer pipeline."""
    project_id: str


class WriterInput(BaseModel):
    """Input for writer pipeline."""
    project_id: str
    prompt: str
    title: Optional[str] = None
    genre: Optional[str] = None
    world_config: Optional[Dict[str, Any]] = None
    resume_from_layer: Optional[WriterLayer] = None


class WriterOutput(BaseModel):
    """Output from writer pipeline."""
    project_id: str
    current_layer: WriterLayer
    layers: List[LayerStatus]
    final_content: Optional[str] = None
    word_count: int = 0
    extracted_tags: Optional[Dict[str, List[str]]] = None


class ApprovalRequest(BaseModel):
    """User approval/rejection for a layer."""
    project_id: str
    layer: WriterLayer
    approved: bool
    feedback: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None


class GenerateRequest(BaseModel):
    """Request to generate next layer."""
    project_id: str
    layer: Optional[WriterLayer] = None  # If None, continue from current


class StreamChunk(BaseModel):
    """Streaming response chunk."""
    type: str  # "progress", "content", "layer_complete", "error"
    layer: Optional[WriterLayer] = None
    content: Optional[str] = None
    progress: Optional[float] = None
    message: Optional[str] = None

