"""
Conversation Manager for OmniMind

Manages conversation history, memory vectors, and context loading.
Provides scrubbing for old processes and automatic context retrieval.

Features:
- Chat history logging with timestamps
- Memory vector tracking
- Automatic project context loading (pitch, world bible, etc.)
- Old process scrubbing
- Context assembly for LLM prompts
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.conversation")


class MessageRole(Enum):
    """Role of message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    CONTEXT = "context"


class ContextType(Enum):
    """Types of project context."""
    PITCH = "pitch"
    WORLD_BIBLE = "world_bible"
    SCRIPT = "script"
    STYLE_GUIDE = "style_guide"
    CHARACTER = "character"
    LOCATION = "location"
    STORYBOARD = "storyboard"


@dataclass
class ConversationMessage:
    """A single message in the conversation."""
    id: str
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    context_used: Dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "context_used": self.context_used,
            "tokens_used": self.tokens_used,
            "duration_ms": self.duration_ms
        }


@dataclass
class MemoryVector:
    """A memory vector entry."""
    id: str
    content: str
    vector_type: str
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "vector_type": self.vector_type,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "access_count": self.access_count
        }


@dataclass
class ProjectContext:
    """Cached project context."""
    pitch: Optional[str] = None
    world_bible: Optional[Dict[str, Any]] = None
    style_guide: Optional[str] = None
    characters: Dict[str, Any] = field(default_factory=dict)
    locations: Dict[str, Any] = field(default_factory=dict)
    current_script: Optional[str] = None
    loaded_at: Optional[datetime] = None

    def is_stale(self, max_age_minutes: int = 5) -> bool:
        """Check if context is stale and needs refresh."""
        if not self.loaded_at:
            return True
        age = datetime.now() - self.loaded_at
        return age > timedelta(minutes=max_age_minutes)


class ConversationManager:
    """
    Manages conversation history and project context for OmniMind.

    Features:
    - Automatic project context loading
    - Conversation history with scrubbing
    - Memory vector tracking
    - Context assembly for LLM prompts
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        max_history: int = 100,
        max_memory_vectors: int = 500,
        scrub_after_hours: int = 24
    ):
        self.project_path = project_path
        self.max_history = max_history
        self.max_memory_vectors = max_memory_vectors
        self.scrub_after_hours = scrub_after_hours

        # Conversation history (deque for efficient scrubbing)
        self._history: deque[ConversationMessage] = deque(maxlen=max_history)

        # Memory vectors
        self._memory_vectors: Dict[str, MemoryVector] = {}

        # Project context cache
        self._project_context = ProjectContext()

        # Message counter for IDs
        self._next_id = 0

        # Stats
        self._stats = {
            "total_messages": 0,
            "total_tokens": 0,
            "context_loads": 0,
            "scrubs_performed": 0
        }

        # Load project context if path provided
        if project_path:
            self.load_project_context(project_path)

        logger.info("ConversationManager initialized")

    def _generate_id(self) -> str:
        """Generate unique message ID."""
        self._next_id += 1
        return f"msg_{datetime.now().strftime('%H%M%S')}_{self._next_id:04d}"

    # ==================== PROJECT CONTEXT LOADING ====================

    def set_project_path(self, project_path: Path) -> None:
        """Set project path and reload context."""
        self.project_path = Path(project_path) if project_path else None
        if self.project_path:
            self.load_project_context(self.project_path)

    def load_project_context(self, project_path: Path) -> Dict[str, Any]:
        """
        Load all relevant project context for OmniMind priming.

        Loads:
        - project.json (project config)
        - pitch.md (story pitch)
        - world_config.json (world bible)
        - style_guide.md (visual style)
        - Characters and locations
        - Current script if exists
        """
        project_path = Path(project_path)
        loaded = {}

        try:
            # 1. Load project.json
            project_json = project_path / "project.json"
            if project_json.exists():
                import json
                config = json.loads(project_json.read_text(encoding='utf-8'))
                loaded["project_config"] = config
                logger.info(f"Loaded project config: {config.get('name', 'Unknown')}")

            # 2. Load pitch.md
            pitch_file = project_path / "world_bible" / "pitch.md"
            if pitch_file.exists():
                self._project_context.pitch = pitch_file.read_text(encoding='utf-8')
                loaded["pitch"] = len(self._project_context.pitch)
                logger.info(f"Loaded pitch: {len(self._project_context.pitch)} chars")

            # 3. Load world_config.json (world bible)
            world_config = project_path / "world_bible" / "world_config.json"
            if world_config.exists():
                import json
                self._project_context.world_bible = json.loads(
                    world_config.read_text(encoding='utf-8')
                )
                loaded["world_bible"] = True
                logger.info("Loaded world bible config")

            # 4. Load style_guide.md
            style_guide = project_path / "world_bible" / "style_guide.md"
            if style_guide.exists():
                self._project_context.style_guide = style_guide.read_text(encoding='utf-8')
                loaded["style_guide"] = len(self._project_context.style_guide)
                logger.info(f"Loaded style guide: {len(self._project_context.style_guide)} chars")

            # 5. Load characters
            chars_dir = project_path / "characters"
            if chars_dir.exists():
                for char_file in chars_dir.glob("*.json"):
                    try:
                        import json
                        char_data = json.loads(char_file.read_text(encoding='utf-8'))
                        self._project_context.characters[char_file.stem] = char_data
                    except Exception:
                        pass
                loaded["characters"] = len(self._project_context.characters)

            # 6. Load locations
            locs_dir = project_path / "locations"
            if locs_dir.exists():
                for loc_file in locs_dir.glob("*.json"):
                    try:
                        import json
                        loc_data = json.loads(loc_file.read_text(encoding='utf-8'))
                        self._project_context.locations[loc_file.stem] = loc_data
                    except Exception:
                        pass
                loaded["locations"] = len(self._project_context.locations)

            # 7. Load current script (script.md only)
            script_path = project_path / "scripts" / "script.md"
            if script_path.exists():
                self._project_context.current_script = script_path.read_text(encoding='utf-8')
                loaded["script"] = script_path.name
                logger.info(f"Loaded script: {script_path.name}")

            self._project_context.loaded_at = datetime.now()
            self._stats["context_loads"] += 1

            logger.info(f"Project context loaded: {loaded}")

        except Exception as e:
            logger.error(f"Error loading project context: {e}")

        return loaded

    def get_project_context_summary(self) -> str:
        """Get a summary of loaded project context for system prompt."""
        parts = []

        if self._project_context.pitch:
            # Include full pitch (it's the core context)
            parts.append(f"## Project Pitch\n{self._project_context.pitch}")

        if self._project_context.world_bible:
            wb = self._project_context.world_bible
            parts.append(f"## World Bible Summary")
            if "characters" in wb:
                char_names = [c.get("name", c.get("tag", "Unknown")) for c in wb.get("characters", [])]
                parts.append(f"**Characters:** {', '.join(char_names[:10])}")
            if "locations" in wb:
                loc_names = [l.get("name", l.get("tag", "Unknown")) for l in wb.get("locations", [])]
                parts.append(f"**Locations:** {', '.join(loc_names[:10])}")

        if self._project_context.style_guide:
            # Include first 500 chars of style guide
            parts.append(f"## Style Guide\n{self._project_context.style_guide[:500]}...")

        if self._project_context.current_script:
            # Include script outline (first 1000 chars)
            parts.append(f"## Current Script (excerpt)\n{self._project_context.current_script[:1000]}...")

        return "\n\n".join(parts) if parts else "No project context loaded."

    def get_quick_context_directories(self) -> Dict[str, str]:
        """Get quick reference to project directories and their purposes."""
        if not self.project_path:
            return {}

        return {
            "world_bible/": "Core story definitions - pitch.md, world_config.json, style_guide.md",
            "characters/": "Character JSON files with descriptions, traits, relationships",
            "locations/": "Location JSON files with descriptions, atmosphere, props",
            "scripts/": "Story scripts - script.md is the main script",
            "story_documents/": "Generated story content from Writer pipeline",
            "storyboard_output/": "Generated storyboard frames from Director pipeline",
            "beats/": "Story beats and plot structure",
            "assets/": "Reference images and assets",
            "references/": "Reference materials and inspiration"
        }


    # ==================== CONVERSATION HISTORY ====================

    def add_message(
        self,
        role: MessageRole,
        content: str,
        context_used: Dict[str, Any] = None,
        tokens_used: int = 0,
        duration_ms: float = 0.0
    ) -> ConversationMessage:
        """Add a message to conversation history."""
        msg = ConversationMessage(
            id=self._generate_id(),
            role=role,
            content=content,
            context_used=context_used or {},
            tokens_used=tokens_used,
            duration_ms=duration_ms
        )

        self._history.append(msg)
        self._stats["total_messages"] += 1
        self._stats["total_tokens"] += tokens_used

        logger.debug(f"Added {role.value} message: {content[:50]}...")
        return msg

    def add_user_message(self, content: str) -> ConversationMessage:
        """Add a user message."""
        return self.add_message(MessageRole.USER, content)

    def add_assistant_message(
        self,
        content: str,
        context_used: Dict[str, Any] = None,
        tokens_used: int = 0,
        duration_ms: float = 0.0
    ) -> ConversationMessage:
        """Add an assistant message with metadata."""
        return self.add_message(
            MessageRole.ASSISTANT,
            content,
            context_used=context_used,
            tokens_used=tokens_used,
            duration_ms=duration_ms
        )

    def get_history(self, limit: int = None) -> List[ConversationMessage]:
        """Get conversation history."""
        history = list(self._history)
        if limit:
            return history[-limit:]
        return history

    def get_history_for_prompt(self, max_messages: int = 10) -> str:
        """Get formatted history for LLM prompt."""
        recent = self.get_history(max_messages)
        lines = []
        for msg in recent:
            role = msg.role.value.upper()
            lines.append(f"[{role}]: {msg.content}")
        return "\n".join(lines)

    def get_history_dict(self) -> List[Dict[str, Any]]:
        """Get history as list of dicts for logging/export."""
        return [msg.to_dict() for msg in self._history]

    # ==================== MEMORY VECTORS ====================

    def add_memory_vector(
        self,
        content: str,
        vector_type: str,
        importance: float = 0.5
    ) -> MemoryVector:
        """Add a memory vector."""
        vector_id = f"vec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self._memory_vectors):04d}"

        vector = MemoryVector(
            id=vector_id,
            content=content,
            vector_type=vector_type,
            importance=importance
        )

        self._memory_vectors[vector_id] = vector
        logger.debug(f"Added memory vector: {vector_type} - {content[:50]}...")
        return vector

    def get_memory_vectors(self, vector_type: str = None) -> List[MemoryVector]:
        """Get memory vectors, optionally filtered by type."""
        vectors = list(self._memory_vectors.values())
        if vector_type:
            vectors = [v for v in vectors if v.vector_type == vector_type]
        return sorted(vectors, key=lambda v: v.importance, reverse=True)

    def access_memory_vector(self, vector_id: str) -> Optional[MemoryVector]:
        """Access a memory vector (updates access count)."""
        if vector_id in self._memory_vectors:
            vector = self._memory_vectors[vector_id]
            vector.last_accessed = datetime.now()
            vector.access_count += 1
            return vector
        return None

    # ==================== SCRUBBING ====================

    def scrub_old_messages(self, hours: int = None) -> int:
        """Remove messages older than specified hours."""
        hours = hours or self.scrub_after_hours
        cutoff = datetime.now() - timedelta(hours=hours)

        old_count = len(self._history)
        self._history = deque(
            [msg for msg in self._history if msg.timestamp > cutoff],
            maxlen=self.max_history
        )

        removed = old_count - len(self._history)
        if removed > 0:
            self._stats["scrubs_performed"] += 1
            logger.info(f"Scrubbed {removed} old messages (older than {hours}h)")

        return removed

    def scrub_old_vectors(self, hours: int = None) -> int:
        """Remove memory vectors older than specified hours."""
        hours = hours or self.scrub_after_hours
        cutoff = datetime.now() - timedelta(hours=hours)

        old_ids = [
            vid for vid, v in self._memory_vectors.items()
            if v.last_accessed < cutoff and v.importance < 0.8
        ]

        for vid in old_ids:
            del self._memory_vectors[vid]

        if old_ids:
            logger.info(f"Scrubbed {len(old_ids)} old memory vectors")

        return len(old_ids)

    def scrub_all(self, hours: int = None) -> Dict[str, int]:
        """Scrub both messages and vectors."""
        return {
            "messages_removed": self.scrub_old_messages(hours),
            "vectors_removed": self.scrub_old_vectors(hours)
        }

    # ==================== STATS & EXPORT ====================

    def get_stats(self) -> Dict[str, Any]:
        """Get conversation statistics."""
        return {
            **self._stats,
            "current_history_size": len(self._history),
            "current_vector_count": len(self._memory_vectors),
            "project_context_loaded": self._project_context.loaded_at is not None,
            "context_stale": self._project_context.is_stale()
        }

    def export_session(self, output_path: Path = None) -> Path:
        """Export current session to JSON file."""
        if not output_path:
            output_path = Path(".health") / "sessions"

        output_path.mkdir(parents=True, exist_ok=True)

        session_file = output_path / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        import json
        session_data = {
            "exported_at": datetime.now().isoformat(),
            "stats": self.get_stats(),
            "history": self.get_history_dict(),
            "memory_vectors": [v.to_dict() for v in self._memory_vectors.values()]
        }

        session_file.write_text(json.dumps(session_data, indent=2))
        logger.info(f"Session exported to: {session_file}")
        return session_file

    def clear_session(self) -> None:
        """Clear current session (history and vectors)."""
        self._history.clear()
        self._memory_vectors.clear()
        self._next_id = 0
        logger.info("Session cleared")

