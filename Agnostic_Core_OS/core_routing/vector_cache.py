"""
Agnostic_Core_OS Vector Cache

Heavy vector caching system with up to 1MB storage capacity.
Standalone version for Agnostic_Core_OS runtime.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from enum import Enum
import json
import hashlib
import sys
import logging

logger = logging.getLogger("agnostic_core_os.core_routing.vector_cache")

# Maximum cache size: 1MB
MAX_CACHE_SIZE_BYTES = 1024 * 1024


class CacheEntryType(Enum):
    """Types of cached entries."""
    ERROR_TRANSCRIPT = "error_transcript"
    NOTATION_DEFINITION = "notation_definition"
    ARCHIVED_CONCEPT = "archived_concept"
    TASK_CONTEXT = "task_context"
    RETRIEVAL_RESULT = "retrieval_result"


class VectorWeight(Enum):
    """Vector weights for retrieval priority."""
    ACTIVE = 1.0           # Normal active content
    ARCHIVED = -0.5        # Old versions, deprioritized
    DEPRECATED = -1.0      # Deprecated tags, excluded from search


@dataclass
class CacheEntry:
    """A single cache entry with vector weight."""
    id: str
    entry_type: CacheEntryType
    content: str
    weight: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    size_bytes: int = 0
    
    def __post_init__(self):
        """Calculate size after initialization."""
        self.size_bytes = sys.getsizeof(self.content) + sys.getsizeof(json.dumps(self.metadata))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "entry_type": self.entry_type.value,
            "content": self.content,
            "weight": self.weight,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "size_bytes": self.size_bytes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            entry_type=CacheEntryType(data["entry_type"]),
            content=data["content"],
            weight=data.get("weight", 1.0),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
            size_bytes=data.get("size_bytes", 0)
        )


class VectorCache:
    """
    Heavy vector cache for Agnostic_Core_OS.
    
    Features:
    - Up to 1MB storage capacity
    - Weighted entries for retrieval priority
    - Negative weights for archived/deprecated content
    - Persistence to disk
    - LRU eviction when full
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the vector cache."""
        self.cache_dir = cache_dir
        self._entries: Dict[str, CacheEntry] = {}
        self._total_size: int = 0
        self._access_order: List[str] = []  # For LRU eviction
        
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()
    
    @property
    def size_bytes(self) -> int:
        return self._total_size
    
    @property
    def count(self) -> int:
        return len(self._entries)
    
    def add(
        self,
        content: str,
        entry_type: CacheEntryType,
        weight: float = 1.0,
        entry_id: Optional[str] = None,
        **metadata
    ) -> Optional[CacheEntry]:
        """Add an entry to the cache."""
        if entry_id is None:
            entry_id = self._generate_id(content)
        
        entry = CacheEntry(
            id=entry_id,
            entry_type=entry_type,
            content=content,
            weight=weight,
            metadata=metadata
        )
        
        # Evict if necessary
        while self._total_size + entry.size_bytes > MAX_CACHE_SIZE_BYTES:
            if not self._evict_lru():
                logger.warning("Cannot add entry: cache full")
                return None
        
        self._entries[entry_id] = entry
        self._total_size += entry.size_bytes
        self._access_order.append(entry_id)
        
        if self.cache_dir:
            self._save_to_disk()
        
        logger.debug(f"Added: {entry_id} ({entry.size_bytes} bytes)")
        return entry
    
    def get(self, entry_id: str) -> Optional[CacheEntry]:
        """Get an entry by ID."""
        entry = self._entries.get(entry_id)
        if entry and entry_id in self._access_order:
            self._access_order.remove(entry_id)
            self._access_order.append(entry_id)
        return entry
    
    def get_by_type(self, entry_type: CacheEntryType) -> List[CacheEntry]:
        """Get entries by type."""
        return [e for e in self._entries.values() if e.entry_type == entry_type]

    def get_by_weight(self, min_weight: float = 0.0) -> List[CacheEntry]:
        """Get entries with weight >= min_weight."""
        return [e for e in self._entries.values() if e.weight >= min_weight]

    def get_active(self) -> List[CacheEntry]:
        """Get all active (positive weight) entries."""
        return self.get_by_weight(0.0)

    def get_archived(self) -> List[CacheEntry]:
        """Get all archived (negative weight) entries."""
        return [e for e in self._entries.values() if e.weight < 0]

    def archive(self, entry_id: str) -> bool:
        """Archive an entry (set weight to -0.5)."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.weight = VectorWeight.ARCHIVED.value
            logger.info(f"Archived: {entry_id}")
            return True
        return False

    def deprecate(self, entry_id: str) -> bool:
        """Deprecate an entry (set weight to -1.0)."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.weight = VectorWeight.DEPRECATED.value
            logger.info(f"Deprecated: {entry_id}")
            return True
        return False

    def restore(self, entry_id: str) -> bool:
        """Restore an entry to active (set weight to 1.0)."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.weight = VectorWeight.ACTIVE.value
            logger.info(f"Restored: {entry_id}")
            return True
        return False

    def remove(self, entry_id: str) -> bool:
        """Remove an entry from cache."""
        if entry_id in self._entries:
            entry = self._entries.pop(entry_id)
            self._total_size -= entry.size_bytes
            if entry_id in self._access_order:
                self._access_order.remove(entry_id)
            logger.debug(f"Removed: {entry_id}")
            return True
        return False

    def flush(self) -> int:
        """Clear all entries. Returns count of entries removed."""
        count = len(self._entries)
        self._entries.clear()
        self._access_order.clear()
        self._total_size = 0
        logger.info(f"Flushed {count} entries")
        return count

    def _generate_id(self, content: str) -> str:
        """Generate a unique ID from content hash."""
        hash_obj = hashlib.md5(content.encode())
        return f"vec_{hash_obj.hexdigest()[:12]}"

    def _evict_lru(self) -> bool:
        """Evict least recently used entry."""
        if not self._access_order:
            return False

        # Prefer evicting archived/deprecated first
        for entry_id in self._access_order:
            entry = self._entries.get(entry_id)
            if entry and entry.weight < 0:
                self.remove(entry_id)
                return True

        # Otherwise evict oldest
        oldest_id = self._access_order[0]
        self.remove(oldest_id)
        return True

    def _save_to_disk(self) -> None:
        """Persist cache to disk."""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / "vector_cache.json"
        data = {
            "entries": [e.to_dict() for e in self._entries.values()],
            "access_order": self._access_order,
        }
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_from_disk(self) -> None:
        """Load cache from disk."""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / "vector_cache.json"
        if not cache_file.exists():
            return

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            for entry_data in data.get("entries", []):
                entry = CacheEntry.from_dict(entry_data)
                self._entries[entry.id] = entry
                self._total_size += entry.size_bytes

            self._access_order = data.get("access_order", [])
            logger.info(f"Loaded {len(self._entries)} entries from disk")
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        type_counts = {}
        for entry_type in CacheEntryType:
            type_counts[entry_type.value] = len(self.get_by_type(entry_type))

        return {
            "total_entries": len(self._entries),
            "total_size_bytes": self._total_size,
            "max_size_bytes": MAX_CACHE_SIZE_BYTES,
            "utilization": self._total_size / MAX_CACHE_SIZE_BYTES if MAX_CACHE_SIZE_BYTES > 0 else 0,
            "active_count": len(self.get_active()),
            "archived_count": len(self.get_archived()),
            "by_type": type_counts,
        }

