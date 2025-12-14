"""
Vector Memory System

Provides vectorized memory storage for UI states, preferences, and workflows.
Uses JSONL format for LoRA-compatible dataset generation.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import hashlib


class MemoryType(Enum):
    """Types of memory entries."""
    UI_STATE = "ui_state"           # UI component states
    UI_LAYOUT = "ui_layout"         # Layout configurations
    USER_ACTION = "user_action"     # User interactions
    WORKFLOW = "workflow"           # Workflow patterns
    PREFERENCE = "preference"       # User preferences
    LLM_INTERACTION = "llm_interaction"  # LLM request/response pairs
    VECTOR_TRANSLATION = "vector_translation"  # Natural ↔ Vector translations
    SYSTEM_EVENT = "system_event"   # System events


class MemoryPriority(Enum):
    """Priority levels for memory entries."""
    CRITICAL = 1.0    # Always retain
    HIGH = 0.8        # Retain unless space needed
    NORMAL = 0.5      # Standard retention
    LOW = 0.3         # Can be pruned
    EPHEMERAL = 0.1   # Session-only


@dataclass
class MemoryEntry:
    """A single memory entry in the vector store."""
    id: str
    memory_type: MemoryType
    priority: MemoryPriority
    timestamp: datetime
    content: Dict[str, Any]
    vector_notation: str = ""       # Vector representation
    natural_language: str = ""      # Natural language description
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "memory_type": self.memory_type.value,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "content": self.content,
            "vector_notation": self.vector_notation,
            "natural_language": self.natural_language,
            "tags": self.tags,
            "metadata": self.metadata,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            memory_type=MemoryType(data["memory_type"]),
            priority=MemoryPriority(data["priority"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            content=data["content"],
            vector_notation=data.get("vector_notation", ""),
            natural_language=data.get("natural_language", ""),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
        )
    
    def to_training_pair(self) -> Dict[str, str]:
        """Convert to LLM training pair format."""
        return {
            "instruction": self.natural_language or f"Process {self.memory_type.value}",
            "input": json.dumps(self.content),
            "output": self.vector_notation or json.dumps(self.content),
        }


class VectorMemory:
    """
    Vector Memory Store for procedural UI crafting.
    
    Features:
    - JSONL storage for LoRA-compatible datasets
    - Priority-based retention
    - Vector notation indexing
    - Workflow pattern detection
    """
    
    def __init__(self, storage_path: Path = None, max_entries: int = 10000):
        self.storage_path = storage_path
        self.max_entries = max_entries
        self._entries: Dict[str, MemoryEntry] = {}
        self._vector_index: Dict[str, List[str]] = {}  # vector -> entry_ids
        self._type_index: Dict[MemoryType, List[str]] = {}
        
        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._memory_file = storage_path / "memory.jsonl"
            self._load_from_disk()
        else:
            self._memory_file = None
    
    def _generate_id(self, content: Dict[str, Any]) -> str:
        """Generate unique ID from content hash."""
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
    
    def _load_from_disk(self) -> None:
        """Load memory from JSONL file."""
        if self._memory_file and self._memory_file.exists():
            with open(self._memory_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entry = MemoryEntry.from_dict(json.loads(line))
                        self._entries[entry.id] = entry
                        self._index_entry(entry)
    
    def _save_entry(self, entry: MemoryEntry) -> None:
        """Append entry to JSONL file."""
        if self._memory_file:
            with open(self._memory_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
    
    def _index_entry(self, entry: MemoryEntry) -> None:
        """Index entry for fast retrieval."""
        # Vector index
        if entry.vector_notation:
            if entry.vector_notation not in self._vector_index:
                self._vector_index[entry.vector_notation] = []
            self._vector_index[entry.vector_notation].append(entry.id)

        # Type index
        if entry.memory_type not in self._type_index:
            self._type_index[entry.memory_type] = []
        self._type_index[entry.memory_type].append(entry.id)

    def store(
        self,
        memory_type: MemoryType,
        content: Dict[str, Any],
        vector_notation: str = "",
        natural_language: str = "",
        priority: MemoryPriority = MemoryPriority.NORMAL,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> MemoryEntry:
        """Store a new memory entry."""
        entry = MemoryEntry(
            id=self._generate_id(content),
            memory_type=memory_type,
            priority=priority,
            timestamp=datetime.now(),
            content=content,
            vector_notation=vector_notation,
            natural_language=natural_language,
            tags=tags or [],
            metadata=metadata or {},
        )

        self._entries[entry.id] = entry
        self._index_entry(entry)
        self._save_entry(entry)
        self._prune_if_needed()

        return entry

    def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve entry by ID and update access stats."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.now()
        return entry

    def query_by_vector(self, vector_notation: str) -> List[MemoryEntry]:
        """Query entries by vector notation."""
        entry_ids = self._vector_index.get(vector_notation, [])
        return [self._entries[eid] for eid in entry_ids if eid in self._entries]

    def query_by_type(self, memory_type: MemoryType) -> List[MemoryEntry]:
        """Query entries by type."""
        entry_ids = self._type_index.get(memory_type, [])
        return [self._entries[eid] for eid in entry_ids if eid in self._entries]

    def query_by_tags(self, tags: List[str], match_all: bool = False) -> List[MemoryEntry]:
        """Query entries by tags."""
        results = []
        for entry in self._entries.values():
            if match_all:
                if all(tag in entry.tags for tag in tags):
                    results.append(entry)
            else:
                if any(tag in entry.tags for tag in tags):
                    results.append(entry)
        return results

    def get_recent(self, count: int = 10, memory_type: MemoryType = None) -> List[MemoryEntry]:
        """Get most recent entries."""
        entries = list(self._entries.values())
        if memory_type:
            entries = [e for e in entries if e.memory_type == memory_type]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:count]

    def get_frequent(self, count: int = 10) -> List[MemoryEntry]:
        """Get most frequently accessed entries."""
        entries = list(self._entries.values())
        entries.sort(key=lambda e: e.access_count, reverse=True)
        return entries[:count]

    def _prune_if_needed(self) -> None:
        """Prune low-priority entries if over limit."""
        if len(self._entries) <= self.max_entries:
            return

        # Sort by priority and access count
        entries = list(self._entries.values())
        entries.sort(key=lambda e: (e.priority.value, e.access_count))

        # Remove lowest priority entries
        to_remove = len(entries) - self.max_entries
        for entry in entries[:to_remove]:
            if entry.priority != MemoryPriority.CRITICAL:
                del self._entries[entry.id]

    def export_training_data(self, output_path: Path, memory_types: List[MemoryType] = None) -> int:
        """Export entries as JSONL training data for LoRA."""
        entries = list(self._entries.values())
        if memory_types:
            entries = [e for e in entries if e.memory_type in memory_types]

        with open(output_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry.to_training_pair()) + "\n")

        return len(entries)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        type_counts = {}
        for mtype in MemoryType:
            type_counts[mtype.value] = len(self._type_index.get(mtype, []))

        return {
            "total_entries": len(self._entries),
            "max_entries": self.max_entries,
            "vector_index_size": len(self._vector_index),
            "type_counts": type_counts,
        }


# Singleton instance
_vector_memory: Optional[VectorMemory] = None


def get_vector_memory(storage_path: Path = None) -> VectorMemory:
    """Get or create the singleton VectorMemory instance."""
    global _vector_memory
    if _vector_memory is None:
        _vector_memory = VectorMemory(storage_path)
    return _vector_memory

