"""
Greenlight Assistant Memory

Memory systems for the Omni Mind AI assistant.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from collections import deque

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.memory")


class MemoryType(Enum):
    """Types of memory entries."""
    CONVERSATION = "conversation"
    DECISION = "decision"
    USER_PREFERENCE = "user_preference"
    PROJECT_CONTEXT = "project_context"
    ERROR = "error"
    SUGGESTION = "suggestion"


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    memory_type: MemoryType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    importance: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
    accessed_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def access(self) -> None:
        """Record an access to this memory."""
        self.accessed_count += 1
        self.last_accessed = datetime.now()


class AssistantMemory:
    """
    Memory system for the Omni Mind assistant.
    
    Features:
    - Short-term conversation memory
    - Long-term project memory
    - User preference tracking
    - Decision history
    - Importance-based retention
    """
    
    def __init__(
        self,
        short_term_limit: int = 50,
        long_term_limit: int = 1000
    ):
        """
        Initialize the memory system.
        
        Args:
            short_term_limit: Max short-term memories
            long_term_limit: Max long-term memories
        """
        self.short_term_limit = short_term_limit
        self.long_term_limit = long_term_limit
        
        self._short_term: deque = deque(maxlen=short_term_limit)
        self._long_term: Dict[str, MemoryEntry] = {}
        self._preferences: Dict[str, Any] = {}
        self._next_id = 0
    
    def add(
        self,
        content: str,
        memory_type: MemoryType,
        importance: float = 0.5,
        **metadata
    ) -> MemoryEntry:
        """
        Add a memory entry.
        
        Args:
            content: Memory content
            memory_type: Type of memory
            importance: Importance score (0-1)
            **metadata: Additional metadata
            
        Returns:
            Created MemoryEntry
        """
        entry = MemoryEntry(
            id=f"mem_{self._next_id:06d}",
            memory_type=memory_type,
            content=content,
            importance=importance,
            metadata=metadata
        )
        self._next_id += 1
        
        # Add to short-term
        self._short_term.append(entry)
        
        # Promote to long-term if important
        if importance >= 0.7:
            self._promote_to_long_term(entry)
        
        logger.debug(f"Added memory: {entry.id} ({memory_type.value})")
        return entry
    
    def _promote_to_long_term(self, entry: MemoryEntry) -> None:
        """Promote a memory to long-term storage."""
        if len(self._long_term) >= self.long_term_limit:
            # Remove least important
            self._evict_least_important()
        
        self._long_term[entry.id] = entry
    
    def _evict_least_important(self) -> None:
        """Remove the least important long-term memory."""
        if not self._long_term:
            return
        
        # Score by importance and recency
        def score(entry: MemoryEntry) -> float:
            age_days = (datetime.now() - entry.timestamp).days
            recency_factor = 1.0 / (1.0 + age_days * 0.1)
            access_factor = min(1.0, entry.accessed_count * 0.1)
            return entry.importance * 0.5 + recency_factor * 0.3 + access_factor * 0.2
        
        least_important = min(self._long_term.values(), key=score)
        del self._long_term[least_important.id]
    
    def get_recent(self, count: int = 10) -> List[MemoryEntry]:
        """Get recent short-term memories."""
        return list(self._short_term)[-count:]
    
    def get_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 20
    ) -> List[MemoryEntry]:
        """Get memories of a specific type."""
        all_memories = list(self._short_term) + list(self._long_term.values())
        filtered = [m for m in all_memories if m.memory_type == memory_type]
        return sorted(filtered, key=lambda m: m.timestamp, reverse=True)[:limit]
    
    def search(
        self,
        query: str,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Search memories by content."""
        query_lower = query.lower()
        all_memories = list(self._short_term) + list(self._long_term.values())
        
        matches = []
        for memory in all_memories:
            if query_lower in memory.content.lower():
                memory.access()
                matches.append(memory)
        
        return sorted(matches, key=lambda m: m.importance, reverse=True)[:limit]
    
    def set_preference(self, key: str, value: Any) -> None:
        """Set a user preference."""
        self._preferences[key] = value
        self.add(
            content=f"Preference set: {key} = {value}",
            memory_type=MemoryType.USER_PREFERENCE,
            importance=0.8,
            key=key,
            value=value
        )
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        return self._preferences.get(key, default)
    
    def get_conversation_context(self, turns: int = 5) -> str:
        """Get recent conversation context as text."""
        recent = self.get_by_type(MemoryType.CONVERSATION, limit=turns)
        return "\n".join(m.content for m in reversed(recent))
    
    def clear_short_term(self) -> None:
        """Clear short-term memory."""
        self._short_term.clear()
    
    @property
    def short_term_count(self) -> int:
        return len(self._short_term)
    
    @property
    def long_term_count(self) -> int:
        return len(self._long_term)

