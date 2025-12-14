"""
Greenlight Vector Cache

Heavy vector caching system for OmniMind with up to 1MB data storage.
Supports error transcripts, notation definitions, and archived concepts.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path
from enum import Enum
import json
import hashlib
import sys

from greenlight.core.logging_config import get_logger
from greenlight.utils.file_utils import ensure_directory, write_json, read_json

logger = get_logger("omni_mind.vector_cache")

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
    Heavy vector cache for OmniMind.
    
    Features:
    - Up to 1MB storage capacity
    - Weighted entries for retrieval priority
    - Negative weights for archived/deprecated content
    - Persistence to disk
    - LRU eviction when full
    """
    
    def __init__(self, cache_dir: Path = None):
        """
        Initialize the vector cache.
        
        Args:
            cache_dir: Directory for cache persistence
        """
        self.cache_dir = cache_dir
        self._entries: Dict[str, CacheEntry] = {}
        self._total_size: int = 0
        self._access_order: List[str] = []  # For LRU eviction
        
        if cache_dir:
            ensure_directory(cache_dir)
            self._load_from_disk()
    
    @property
    def size_bytes(self) -> int:
        """Current cache size in bytes."""
        return self._total_size
    
    @property
    def size_mb(self) -> float:
        """Current cache size in MB."""
        return self._total_size / (1024 * 1024)
    
    @property
    def capacity_used(self) -> float:
        """Percentage of capacity used."""
        return (self._total_size / MAX_CACHE_SIZE_BYTES) * 100
    
    def add(
        self,
        content: str,
        entry_type: CacheEntryType,
        weight: float = 1.0,
        entry_id: str = None,
        **metadata
    ) -> CacheEntry:
        """
        Add an entry to the cache.
        
        Args:
            content: Content to cache
            entry_type: Type of entry
            weight: Vector weight (-1.0 to 1.0)
            entry_id: Optional custom ID
            **metadata: Additional metadata
            
        Returns:
            Created CacheEntry
        """
        # Generate ID if not provided
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
                logger.warning("Cannot add entry: cache full and nothing to evict")
                return None
        
        # Add entry
        self._entries[entry_id] = entry
        self._total_size += entry.size_bytes
        self._access_order.append(entry_id)
        
        logger.debug(f"Cached: {entry_id} ({entry.size_bytes} bytes, weight={weight})")
        return entry

    def get(self, entry_id: str) -> Optional[CacheEntry]:
        """Get an entry by ID."""
        entry = self._entries.get(entry_id)
        if entry:
            # Update access order for LRU
            if entry_id in self._access_order:
                self._access_order.remove(entry_id)
            self._access_order.append(entry_id)
        return entry

    def get_by_type(self, entry_type: CacheEntryType) -> List[CacheEntry]:
        """Get all entries of a specific type."""
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
        """Deprecate an entry (set weight to -1.0, excluded from search)."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.weight = VectorWeight.DEPRECATED.value
            logger.info(f"Deprecated: {entry_id}")
            return True
        return False

    def restore(self, entry_id: str) -> bool:
        """Restore an entry to active (weight = 1.0)."""
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
        """Evict least recently used entry. Returns True if evicted."""
        if not self._access_order:
            return False

        # Find first non-critical entry to evict
        for entry_id in self._access_order:
            entry = self._entries.get(entry_id)
            if entry and entry.entry_type != CacheEntryType.ERROR_TRANSCRIPT:
                self.remove(entry_id)
                return True

        # If only error transcripts, evict oldest
        if self._access_order:
            oldest_id = self._access_order[0]
            self.remove(oldest_id)
            return True

        return False

    def _load_from_disk(self) -> None:
        """Load cache from disk."""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / "vector_cache.json"
        if cache_file.exists():
            try:
                data = read_json(cache_file)
                for entry_data in data.get("entries", []):
                    entry = CacheEntry.from_dict(entry_data)
                    self._entries[entry.id] = entry
                    self._total_size += entry.size_bytes
                    self._access_order.append(entry.id)
                logger.info(f"Loaded {len(self._entries)} entries from disk")
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")

    def save_to_disk(self) -> None:
        """Save cache to disk."""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / "vector_cache.json"
        data = {
            "entries": [e.to_dict() for e in self._entries.values()],
            "total_size": self._total_size,
            "saved_at": datetime.now().isoformat()
        }
        try:
            write_json(cache_file, data)
            logger.info(f"Saved {len(self._entries)} entries to disk")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        type_counts = {}
        for entry in self._entries.values():
            type_name = entry.entry_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        return {
            "total_entries": len(self._entries),
            "total_size_bytes": self._total_size,
            "total_size_mb": self.size_mb,
            "capacity_used_percent": self.capacity_used,
            "max_capacity_mb": MAX_CACHE_SIZE_BYTES / (1024 * 1024),
            "entries_by_type": type_counts,
            "active_count": len(self.get_active()),
            "archived_count": len(self.get_archived())
        }

