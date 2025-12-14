"""
User Profile Manager

Manages user profiles with:
- Routine workflow tracking
- Vectored preference libraries
- Personalized UI configurations
- LoRA-compatible dataset generation
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import hashlib


class WorkflowType(Enum):
    """Types of workflows."""
    STORY_WRITING = "story_writing"
    STORYBOARD_EDITING = "storyboard_editing"
    WORLD_BUILDING = "world_building"
    CHARACTER_DESIGN = "character_design"
    PROMPT_CRAFTING = "prompt_crafting"
    REVIEW_APPROVAL = "review_approval"
    EXPORT_DELIVERY = "export_delivery"
    CUSTOM = "custom"


@dataclass
class WorkflowPattern:
    """A detected workflow pattern."""
    id: str
    workflow_type: WorkflowType
    name: str
    description: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    frequency: int = 0
    avg_duration_minutes: float = 0.0
    preferred_layout: str = ""
    vector_sequence: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflow_type": self.workflow_type.value,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "frequency": self.frequency,
            "avg_duration_minutes": self.avg_duration_minutes,
            "preferred_layout": self.preferred_layout,
            "vector_sequence": self.vector_sequence,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowPattern":
        return cls(
            id=data["id"],
            workflow_type=WorkflowType(data["workflow_type"]),
            name=data["name"],
            description=data["description"],
            steps=data.get("steps", []),
            frequency=data.get("frequency", 0),
            avg_duration_minutes=data.get("avg_duration_minutes", 0.0),
            preferred_layout=data.get("preferred_layout", ""),
            vector_sequence=data.get("vector_sequence", []),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
        )


@dataclass
class ProfilePreference:
    """A user preference setting."""
    key: str
    value: Any
    category: str = "general"
    vector_notation: str = ""
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "vector_notation": self.vector_notation,
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfilePreference":
        return cls(
            key=data["key"],
            value=data["value"],
            category=data.get("category", "general"),
            vector_notation=data.get("vector_notation", ""),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


@dataclass
class UserProfile:
    """A complete user profile."""
    id: str
    name: str
    email: str = ""
    preferences: Dict[str, ProfilePreference] = field(default_factory=dict)
    workflows: Dict[str, WorkflowPattern] = field(default_factory=dict)
    active_layout: str = "layout_story"
    llm_preferences: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    session_count: int = 0
    total_actions: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "preferences": {k: v.to_dict() for k, v in self.preferences.items()},
            "workflows": {k: v.to_dict() for k, v in self.workflows.items()},
            "active_layout": self.active_layout,
            "llm_preferences": self.llm_preferences,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "session_count": self.session_count,
            "total_actions": self.total_actions,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        prefs = {k: ProfilePreference.from_dict(v) for k, v in data.get("preferences", {}).items()}
        workflows = {k: WorkflowPattern.from_dict(v) for k, v in data.get("workflows", {}).items()}
        return cls(
            id=data["id"],
            name=data["name"],
            email=data.get("email", ""),
            preferences=prefs,
            workflows=workflows,
            active_layout=data.get("active_layout", "layout_story"),
            llm_preferences=data.get("llm_preferences", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            last_active=datetime.fromisoformat(data["last_active"]) if "last_active" in data else datetime.now(),
            session_count=data.get("session_count", 0),
            total_actions=data.get("total_actions", 0),
            metadata=data.get("metadata", {}),
        )


class UserProfileManager:
    """
    Manages user profiles with workflow tracking and vectored libraries.

    Features:
    - Profile creation and persistence
    - Workflow pattern detection
    - Preference vectorization
    - LoRA dataset export
    """

    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path
        self._profiles: Dict[str, UserProfile] = {}
        self._active_profile: Optional[str] = None
        self._action_buffer: List[Dict[str, Any]] = []

        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._profiles_file = storage_path / "profiles.json"
            self._load_profiles()
        else:
            self._profiles_file = None

    def _load_profiles(self) -> None:
        """Load profiles from disk."""
        if self._profiles_file and self._profiles_file.exists():
            with open(self._profiles_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for profile_data in data.get("profiles", []):
                    profile = UserProfile.from_dict(profile_data)
                    self._profiles[profile.id] = profile
                self._active_profile = data.get("active_profile")

    def _save_profiles(self) -> None:
        """Save profiles to disk."""
        if self._profiles_file:
            data = {
                "profiles": [p.to_dict() for p in self._profiles.values()],
                "active_profile": self._active_profile,
            }
            with open(self._profiles_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def create_profile(self, name: str, email: str = "") -> UserProfile:
        """Create a new user profile."""
        profile_id = hashlib.sha256(f"{name}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        profile = UserProfile(id=profile_id, name=name, email=email)
        self._profiles[profile_id] = profile

        if not self._active_profile:
            self._active_profile = profile_id

        self._save_profiles()
        return profile

    def get_profile(self, profile_id: str) -> Optional[UserProfile]:
        """Get a profile by ID."""
        return self._profiles.get(profile_id)

    def get_active_profile(self) -> Optional[UserProfile]:
        """Get the active profile."""
        if self._active_profile:
            return self._profiles.get(self._active_profile)
        return None

    def set_active_profile(self, profile_id: str) -> bool:
        """Set the active profile."""
        if profile_id in self._profiles:
            self._active_profile = profile_id
            profile = self._profiles[profile_id]
            profile.session_count += 1
            profile.last_active = datetime.now()
            self._save_profiles()
            return True
        return False

    def list_profiles(self) -> List[Dict[str, Any]]:
        """List all profiles."""
        return [
            {"id": p.id, "name": p.name, "last_active": p.last_active.isoformat()}
            for p in self._profiles.values()
        ]

    def set_preference(self, key: str, value: Any, category: str = "general", vector: str = "") -> bool:
        """Set a preference for the active profile."""
        profile = self.get_active_profile()
        if not profile:
            return False

        pref = ProfilePreference(key=key, value=value, category=category, vector_notation=vector)
        profile.preferences[key] = pref
        self._save_profiles()
        return True

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a preference value."""
        profile = self.get_active_profile()
        if profile and key in profile.preferences:
            return profile.preferences[key].value
        return default

    def record_action(self, action_type: str, details: Dict[str, Any], vector: str = "") -> None:
        """Record a user action for workflow detection."""
        profile = self.get_active_profile()
        if profile:
            profile.total_actions += 1

        self._action_buffer.append({
            "timestamp": datetime.now().isoformat(),
            "action_type": action_type,
            "details": details,
            "vector": vector,
        })

        # Detect patterns every 10 actions
        if len(self._action_buffer) >= 10:
            self._detect_patterns()

    def _detect_patterns(self) -> None:
        """Detect workflow patterns from action buffer."""
        profile = self.get_active_profile()
        if not profile or len(self._action_buffer) < 5:
            return

        # Group actions by type sequence
        action_types = [a["action_type"] for a in self._action_buffer[-10:]]
        sequence_key = "->".join(action_types[:5])

        # Check if pattern exists
        pattern_id = hashlib.sha256(sequence_key.encode()).hexdigest()[:8]

        if pattern_id in profile.workflows:
            pattern = profile.workflows[pattern_id]
            pattern.frequency += 1
            pattern.last_used = datetime.now()
        else:
            # Create new pattern
            workflow_type = self._classify_workflow(action_types)
            pattern = WorkflowPattern(
                id=pattern_id,
                workflow_type=workflow_type,
                name=f"Pattern {len(profile.workflows) + 1}",
                description=f"Detected pattern: {sequence_key}",
                steps=[{"action": a, "order": i} for i, a in enumerate(action_types[:5])],
                frequency=1,
                vector_sequence=[a.get("vector", "") for a in self._action_buffer[-5:]],
            )
            profile.workflows[pattern_id] = pattern

        self._save_profiles()
        self._action_buffer = self._action_buffer[-5:]  # Keep last 5 for overlap

    def _classify_workflow(self, actions: List[str]) -> WorkflowType:
        """Classify workflow type from actions."""
        action_str = " ".join(actions).lower()

        if "story" in action_str or "write" in action_str or "edit" in action_str:
            return WorkflowType.STORY_WRITING
        elif "storyboard" in action_str or "frame" in action_str:
            return WorkflowType.STORYBOARD_EDITING
        elif "world" in action_str or "bible" in action_str:
            return WorkflowType.WORLD_BUILDING
        elif "character" in action_str:
            return WorkflowType.CHARACTER_DESIGN
        elif "prompt" in action_str:
            return WorkflowType.PROMPT_CRAFTING
        elif "review" in action_str or "approve" in action_str:
            return WorkflowType.REVIEW_APPROVAL
        elif "export" in action_str:
            return WorkflowType.EXPORT_DELIVERY

        return WorkflowType.CUSTOM

    def get_frequent_workflows(self, count: int = 5) -> List[WorkflowPattern]:
        """Get most frequent workflows for active profile."""
        profile = self.get_active_profile()
        if not profile:
            return []

        workflows = list(profile.workflows.values())
        workflows.sort(key=lambda w: w.frequency, reverse=True)
        return workflows[:count]

    def export_profile_dataset(self, output_path: Path) -> int:
        """Export profile data as JSONL for LoRA training."""
        profile = self.get_active_profile()
        if not profile:
            return 0

        entries = []

        # Export preferences
        for pref in profile.preferences.values():
            entries.append({
                "instruction": f"Set user preference for {pref.category}",
                "input": pref.key,
                "output": json.dumps(pref.value),
            })

        # Export workflows
        for workflow in profile.workflows.values():
            entries.append({
                "instruction": f"Execute {workflow.workflow_type.value} workflow",
                "input": workflow.description,
                "output": " ".join(workflow.vector_sequence),
            })

        with open(output_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        return len(entries)

