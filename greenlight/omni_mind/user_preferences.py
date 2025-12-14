"""
Greenlight User Preferences & LoRA Library System

Allows users to add scripted LoRAs (style preferences) as quality of life upgrades.
Safely integrated and non-obstructing to core functionality.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path
from enum import Enum
import json

from greenlight.core.logging_config import get_logger
from greenlight.utils.file_utils import read_json, write_json, ensure_directory

logger = get_logger("omni_mind.user_preferences")


class LoRACategory(Enum):
    """Categories for LoRA preferences."""
    STYLE = "style"              # Visual/writing style
    WORKFLOW = "workflow"        # Pipeline preferences
    NOTATION = "notation"        # Custom notation patterns
    AGENT = "agent"              # Agent behavior preferences
    UI = "ui"                    # UI customizations
    OUTPUT = "output"            # Output format preferences


class LoRAStatus(Enum):
    """Status of a LoRA preference."""
    ACTIVE = "active"
    DISABLED = "disabled"
    PENDING_REVIEW = "pending_review"
    FLAGGED = "flagged"


@dataclass
class ScriptedLoRA:
    """
    A user-defined preference/style that can be layered onto the system.
    
    LoRAs are safely integrated and can be enabled/disabled without
    affecting core functionality.
    """
    id: str
    name: str
    category: LoRACategory
    description: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: LoRAStatus = LoRAStatus.ACTIVE
    author: str = "user"
    version: str = "1.0"
    
    # The actual preference data
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Style-specific fields
    style_prompt: str = ""           # Prompt modifier for style
    style_negative: str = ""         # Negative prompt additions
    style_weight: float = 1.0        # Weight/strength of style
    
    # Workflow-specific fields
    pipeline_overrides: Dict[str, Any] = field(default_factory=dict)
    agent_instructions: str = ""
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "author": self.author,
            "version": self.version,
            "config": self.config,
            "style_prompt": self.style_prompt,
            "style_negative": self.style_negative,
            "style_weight": self.style_weight,
            "pipeline_overrides": self.pipeline_overrides,
            "agent_instructions": self.agent_instructions,
            "tags": self.tags,
            "dependencies": self.dependencies
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScriptedLoRA":
        return cls(
            id=data["id"],
            name=data["name"],
            category=LoRACategory(data["category"]),
            description=data["description"],
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
            status=LoRAStatus(data.get("status", "active")),
            author=data.get("author", "user"),
            version=data.get("version", "1.0"),
            config=data.get("config", {}),
            style_prompt=data.get("style_prompt", ""),
            style_negative=data.get("style_negative", ""),
            style_weight=data.get("style_weight", 1.0),
            pipeline_overrides=data.get("pipeline_overrides", {}),
            agent_instructions=data.get("agent_instructions", ""),
            tags=data.get("tags", []),
            dependencies=data.get("dependencies", [])
        )


class UserPreferencesLibrary:
    """
    Library for managing user preferences and scripted LoRAs.
    
    Features:
    - Add/remove/update LoRAs
    - Category-based organization
    - Safe integration (non-obstructing)
    - Persistence to disk
    - Flagging system for review
    """
    
    def __init__(self, project_path: Path = None):
        """
        Initialize preferences library.
        
        Args:
            project_path: Project root path
        """
        self.project_path = project_path
        self._loras: Dict[str, ScriptedLoRA] = {}
        self._next_id = 0
        
        # Setup storage
        if project_path:
            self.prefs_dir = project_path / ".preferences"
            ensure_directory(self.prefs_dir)
            self.lora_file = self.prefs_dir / "loras.json"
            self._load_from_disk()
        else:
            self.prefs_dir = None
            self.lora_file = None
    
    def _generate_id(self) -> str:
        """Generate unique LoRA ID."""
        self._next_id += 1
        return f"lora_{self._next_id:06d}"
    
    def _load_from_disk(self) -> None:
        """Load LoRAs from disk."""
        if self.lora_file and self.lora_file.exists():
            try:
                data = read_json(self.lora_file)
                for lora_data in data.get("loras", []):
                    lora = ScriptedLoRA.from_dict(lora_data)
                    self._loras[lora.id] = lora
                self._next_id = data.get("next_id", len(self._loras))
                logger.info(f"Loaded {len(self._loras)} LoRAs from disk")
            except Exception as e:
                logger.error(f"Failed to load LoRAs: {e}")

    def _save_to_disk(self) -> None:
        """Save LoRAs to disk."""
        if self.lora_file:
            try:
                data = {
                    "next_id": self._next_id,
                    "loras": [lora.to_dict() for lora in self._loras.values()]
                }
                write_json(self.lora_file, data)
            except Exception as e:
                logger.error(f"Failed to save LoRAs: {e}")

    def add_lora(
        self,
        name: str,
        category: LoRACategory,
        description: str,
        config: Dict[str, Any] = None,
        style_prompt: str = "",
        style_weight: float = 1.0,
        **kwargs
    ) -> ScriptedLoRA:
        """
        Add a new LoRA preference.

        Args:
            name: LoRA name
            category: Category
            description: Description
            config: Configuration dict
            style_prompt: Style prompt modifier
            style_weight: Style weight
            **kwargs: Additional fields

        Returns:
            Created ScriptedLoRA
        """
        lora = ScriptedLoRA(
            id=self._generate_id(),
            name=name,
            category=category,
            description=description,
            config=config or {},
            style_prompt=style_prompt,
            style_weight=style_weight,
            **kwargs
        )

        self._loras[lora.id] = lora
        self._save_to_disk()

        logger.info(f"Added LoRA: {lora.id} - {name}")
        return lora

    def get_lora(self, lora_id: str) -> Optional[ScriptedLoRA]:
        """Get a LoRA by ID."""
        return self._loras.get(lora_id)

    def get_by_category(self, category: LoRACategory) -> List[ScriptedLoRA]:
        """Get all LoRAs in a category."""
        return [l for l in self._loras.values() if l.category == category]

    def get_active(self) -> List[ScriptedLoRA]:
        """Get all active LoRAs."""
        return [l for l in self._loras.values() if l.status == LoRAStatus.ACTIVE]

    def get_active_by_category(self, category: LoRACategory) -> List[ScriptedLoRA]:
        """Get active LoRAs in a category."""
        return [
            l for l in self._loras.values()
            if l.category == category and l.status == LoRAStatus.ACTIVE
        ]

    def update_lora(self, lora_id: str, **updates) -> Optional[ScriptedLoRA]:
        """Update a LoRA's fields."""
        lora = self._loras.get(lora_id)
        if not lora:
            return None

        for key, value in updates.items():
            if hasattr(lora, key):
                setattr(lora, key, value)

        lora.updated_at = datetime.now()
        self._save_to_disk()
        return lora

    def enable_lora(self, lora_id: str) -> bool:
        """Enable a LoRA."""
        lora = self._loras.get(lora_id)
        if lora:
            lora.status = LoRAStatus.ACTIVE
            self._save_to_disk()
            return True
        return False

    def disable_lora(self, lora_id: str) -> bool:
        """Disable a LoRA."""
        lora = self._loras.get(lora_id)
        if lora:
            lora.status = LoRAStatus.DISABLED
            self._save_to_disk()
            return True
        return False

    def flag_lora(self, lora_id: str, reason: str = "") -> bool:
        """Flag a LoRA for review."""
        lora = self._loras.get(lora_id)
        if lora:
            lora.status = LoRAStatus.FLAGGED
            lora.config["flag_reason"] = reason
            self._save_to_disk()
            logger.warning(f"LoRA flagged: {lora_id} - {reason}")
            return True
        return False

    def remove_lora(self, lora_id: str) -> bool:
        """Remove a LoRA."""
        if lora_id in self._loras:
            del self._loras[lora_id]
            self._save_to_disk()
            return True
        return False

    def get_combined_style_prompt(self) -> str:
        """Get combined style prompt from all active style LoRAs."""
        prompts = []
        for lora in self.get_active_by_category(LoRACategory.STYLE):
            if lora.style_prompt:
                prompts.append(lora.style_prompt)
        return ", ".join(prompts)

    def get_pipeline_overrides(self) -> Dict[str, Any]:
        """Get combined pipeline overrides from active workflow LoRAs."""
        overrides = {}
        for lora in self.get_active_by_category(LoRACategory.WORKFLOW):
            overrides.update(lora.pipeline_overrides)
        return overrides

    def get_stats(self) -> Dict[str, Any]:
        """Get library statistics."""
        by_category = {}
        by_status = {}

        for lora in self._loras.values():
            cat = lora.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            stat = lora.status.value
            by_status[stat] = by_status.get(stat, 0) + 1

        return {
            "total_loras": len(self._loras),
            "active_count": len(self.get_active()),
            "by_category": by_category,
            "by_status": by_status
        }

