"""
Memory Vector System - Procedural UI Crafting Network

Provides vectorized memory storage for:
- UI states and customizations
- User preferences and profiles
- Workflow patterns and routines
- LoRA-compatible dataset generation

File Format: JSONL (JSON Lines) for LoRA-like storage
- Each line is a self-contained JSON object
- Compatible with ML training frameworks
- Easy streaming, appending, and processing
"""

from .vector_memory import (
    VectorMemory,
    MemoryEntry,
    MemoryType,
    MemoryPriority,
    get_vector_memory,
)
from .ui_network import (
    UINetworkCrafter,
    UIComponent,
    UILayout,
    UICustomization,
    ComponentType,
)
from .user_profile import (
    UserProfileManager,
    UserProfile,
    WorkflowPattern,
    ProfilePreference,
)
from .dataset_crafter import (
    DatasetCrafter,
    DatasetEntry,
    DatasetFormat,
    LoRADataset,
)

__all__ = [
    # Vector Memory
    "VectorMemory",
    "MemoryEntry",
    "MemoryType",
    "MemoryPriority",
    "get_vector_memory",
    # UI Network
    "UINetworkCrafter",
    "UIComponent",
    "UILayout",
    "UICustomization",
    "ComponentType",
    # User Profile
    "UserProfileManager",
    "UserProfile",
    "WorkflowPattern",
    "ProfilePreference",
    # Dataset Crafter
    "DatasetCrafter",
    "DatasetEntry",
    "DatasetFormat",
    "LoRADataset",
]

