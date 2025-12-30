"""
Pydantic Models for API
"""

from .auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
)
from .project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    OutlineCreate,
    OutlineResponse,
    DraftCreate,
    DraftResponse,
)
from .writer import (
    WriterInput,
    WriterOutput,
    LayerStatus,
    ApprovalRequest,
)

__all__ = [
    "UserCreate",
    "UserLogin", 
    "UserResponse",
    "TokenResponse",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "OutlineCreate",
    "OutlineResponse",
    "DraftCreate",
    "DraftResponse",
    "WriterInput",
    "WriterOutput",
    "LayerStatus",
    "ApprovalRequest",
]

