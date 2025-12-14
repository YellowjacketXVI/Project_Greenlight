"""
Vector Notation Library - Core Procedural Catalog

The active, procedurally growing catalog of vectored data language and notation.
This is the central registry for all notation definitions in Agnostic_Core_OS.

Features:
- Notation definition and registration
- Procedural growth (append-only)
- Scope-based organization
- Version tracking
- Export for training
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import hashlib
import json


class NotationType(Enum):
    """Types of notation entries."""
    TAG = "tag"                 # @TAG notation
    SCOPE = "scope"             # #SCOPE notation
    COMMAND = "command"         # >command notation
    QUERY = "query"             # ?query notation
    INCLUDE = "include"         # +include notation
    EXCLUDE = "exclude"         # -exclude notation
    SIMILAR = "similar"         # ~similar notation
    PIPELINE = "pipeline"       # Pipeline notation
    VECTOR = "vector"           # Vector reference
    CUSTOM = "custom"           # User-defined


class NotationScope(Enum):
    """Scopes for notation organization."""
    GLOBAL = "global"           # Available everywhere
    PROJECT = "project"         # Project-specific
    WORLD_BIBLE = "world_bible" # World bible scope
    STORY = "story"             # Story documents
    STORYBOARD = "storyboard"   # Storyboard frames
    UI = "ui"                   # UI components
    SYSTEM = "system"           # System operations
    USER = "user"               # User-defined


@dataclass
class NotationEntry:
    """A single notation definition."""
    id: str
    symbol: str                 # The notation symbol (e.g., "@CHAR_PROTAGONIST")
    notation_type: NotationType
    scope: NotationScope
    definition: str             # Human-readable definition
    pattern: str                # Regex pattern for matching
    examples: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_immutable: bool = False  # Core notations cannot be changed
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "notation_type": self.notation_type.value,
            "scope": self.scope.value,
            "definition": self.definition,
            "pattern": self.pattern,
            "examples": self.examples,
            "related": self.related,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_immutable": self.is_immutable,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotationEntry":
        return cls(
            id=data["id"],
            symbol=data["symbol"],
            notation_type=NotationType(data["notation_type"]),
            scope=NotationScope(data["scope"]),
            definition=data["definition"],
            pattern=data["pattern"],
            examples=data.get("examples", []),
            related=data.get("related", []),
            version=data.get("version", 1),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
            is_immutable=data.get("is_immutable", False),
        )


class NotationLibrary:
    """
    Vector Notation Library - The Core Catalog.
    
    This is the central registry for all notation definitions.
    Supports procedural growth (append-only for core notations).
    """
    
    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path
        self._entries: Dict[str, NotationEntry] = {}
        self._symbol_index: Dict[str, str] = {}  # symbol -> id
        self._type_index: Dict[NotationType, Set[str]] = {t: set() for t in NotationType}
        self._scope_index: Dict[NotationScope, Set[str]] = {s: set() for s in NotationScope}
        
        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._data_file = storage_path / "notation_library.json"
            self._load_data()
        else:
            self._data_file = None
        
        # Initialize core notations
        self._init_core_notations()
    
    def _load_data(self) -> None:
        """Load library from storage."""
        if self._data_file and self._data_file.exists():
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry_data in data.get("entries", []):
                    entry = NotationEntry.from_dict(entry_data)
                    self._entries[entry.id] = entry
                    self._symbol_index[entry.symbol] = entry.id
                    self._type_index[entry.notation_type].add(entry.id)
                    self._scope_index[entry.scope].add(entry.id)
    
    def _save_data(self) -> None:
        """Save library to storage."""
        if self._data_file:
            data = {
                "version": "1.0",
                "entries": [e.to_dict() for e in self._entries.values()],
                "stats": {
                    "total": len(self._entries),
                    "by_type": {t.value: len(ids) for t, ids in self._type_index.items()},
                    "by_scope": {s.value: len(ids) for s, ids in self._scope_index.items()},
                },
                "updated_at": datetime.now().isoformat(),
            }
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
    
    def _init_core_notations(self) -> None:
        """Initialize immutable core notations."""
        core_notations = [
            # Tag notations
            ("@TAG", NotationType.TAG, "Exact tag lookup", "@[A-Z_]+", ["@CHAR_PROTAGONIST", "@LOC_MAIN_STREET"]),
            ("@CHAR_", NotationType.TAG, "Character tag prefix", "@CHAR_[A-Z_]+", ["@CHAR_PROTAGONIST", "@CHAR_ALLY"]),
            ("@LOC_", NotationType.TAG, "Location tag prefix", "@LOC_[A-Z_]+", ["@LOC_MAIN_STREET", "@LOC_PALACE"]),
            ("@PROP_", NotationType.TAG, "Prop tag prefix", "@PROP_[A-Z_]+", ["@PROP_SWORD", "@PROP_BOOK"]),
            ("@IMG_", NotationType.TAG, "Image vector prefix", "@IMG_[A-Z_]+_[a-z0-9]+", ["@IMG_CHARACTER_abc123"]),
            ("@AUD_", NotationType.TAG, "Audio vector prefix", "@AUD_[A-Z_]+_[a-z0-9]+", ["@AUD_DIALOGUE_abc123"]),
            # Scope notations
            ("#SCOPE", NotationType.SCOPE, "Filter by scope", "#[A-Z_]+", ["#WORLD_BIBLE", "#STORY"]),
            ("#PROJECT", NotationType.SCOPE, "Project scope", "#PROJECT", ["#PROJECT"]),
            ("#WORLD_BIBLE", NotationType.SCOPE, "World bible scope", "#WORLD_BIBLE", ["#WORLD_BIBLE"]),
            ("#STORY", NotationType.SCOPE, "Story scope", "#STORY", ["#STORY"]),
            ("#STORYBOARD", NotationType.SCOPE, "Storyboard scope", "#STORYBOARD", ["#STORYBOARD"]),
            # Command notations
            (">command", NotationType.COMMAND, "Run pipeline command", ">[a-z_]+", [">story", ">diagnose"]),
            (">story", NotationType.COMMAND, "Run story pipeline", ">story [a-z]+", [">story standard"]),
            (">direct", NotationType.COMMAND, "Run directing pipeline", ">direct [a-z_]+", [">direct by_scene"]),
            (">diagnose", NotationType.COMMAND, "Run diagnostics", ">diagnose", [">diagnose"]),
            (">heal", NotationType.COMMAND, "Auto-fix issues", ">heal", [">heal"]),
            # Query notations
            ("?query", NotationType.QUERY, "Natural language query", r'\?"[^"]+"', ['?"who is the protagonist"']),
            # Include/Exclude
            ("+include", NotationType.INCLUDE, "Include in results", r"\+[a-z_]+", ["+characters", "+locations"]),
            ("-exclude", NotationType.EXCLUDE, "Exclude from results", r"-[a-z_]+", ["-archived", "-deprecated"]),
            # Similar
            ("~similar", NotationType.SIMILAR, "Semantic similarity", r'~"[^"]+"', ['~"warrior spirit"']),
        ]

        for symbol, ntype, definition, pattern, examples in core_notations:
            if symbol not in self._symbol_index:
                self.register(
                    symbol=symbol,
                    notation_type=ntype,
                    scope=NotationScope.GLOBAL,
                    definition=definition,
                    pattern=pattern,
                    examples=examples,
                    is_immutable=True,
                )

    def register(
        self,
        symbol: str,
        notation_type: NotationType,
        scope: NotationScope,
        definition: str,
        pattern: str,
        examples: List[str] = None,
        related: List[str] = None,
        is_immutable: bool = False,
    ) -> NotationEntry:
        """
        Register a new notation (append-only for immutable).

        Args:
            symbol: The notation symbol
            notation_type: Type of notation
            scope: Scope for organization
            definition: Human-readable definition
            pattern: Regex pattern for matching
            examples: Example usages
            related: Related notation IDs
            is_immutable: If True, cannot be modified

        Returns:
            The created NotationEntry
        """
        # Check if already exists
        if symbol in self._symbol_index:
            existing = self._entries[self._symbol_index[symbol]]
            if existing.is_immutable:
                return existing  # Cannot modify immutable
            # Update existing
            existing.definition = definition
            existing.pattern = pattern
            existing.examples = examples or existing.examples
            existing.related = related or existing.related
            existing.version += 1
            existing.updated_at = datetime.now()
            self._save_data()
            return existing

        # Create new entry
        entry_id = hashlib.sha256(f"{symbol}{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        entry = NotationEntry(
            id=entry_id,
            symbol=symbol,
            notation_type=notation_type,
            scope=scope,
            definition=definition,
            pattern=pattern,
            examples=examples or [],
            related=related or [],
            is_immutable=is_immutable,
        )

        self._entries[entry_id] = entry
        self._symbol_index[symbol] = entry_id
        self._type_index[notation_type].add(entry_id)
        self._scope_index[scope].add(entry_id)

        self._save_data()
        return entry

    def get(self, symbol: str) -> Optional[NotationEntry]:
        """Get notation by symbol."""
        if symbol in self._symbol_index:
            return self._entries[self._symbol_index[symbol]]
        return None

    def get_by_id(self, entry_id: str) -> Optional[NotationEntry]:
        """Get notation by ID."""
        return self._entries.get(entry_id)

    def query_by_type(self, notation_type: NotationType) -> List[NotationEntry]:
        """Get all notations of a type."""
        return [self._entries[eid] for eid in self._type_index[notation_type]]

    def query_by_scope(self, scope: NotationScope) -> List[NotationEntry]:
        """Get all notations in a scope."""
        return [self._entries[eid] for eid in self._scope_index[scope]]

    def search(self, query: str) -> List[NotationEntry]:
        """Search notations by symbol or definition."""
        query_lower = query.lower()
        results = []
        for entry in self._entries.values():
            if query_lower in entry.symbol.lower() or query_lower in entry.definition.lower():
                results.append(entry)
        return results

    def list_all(self) -> List[Dict[str, Any]]:
        """List all notations."""
        return [{"id": e.id, "symbol": e.symbol, "type": e.notation_type.value, "scope": e.scope.value} for e in self._entries.values()]

    def get_stats(self) -> Dict[str, Any]:
        """Get library statistics."""
        return {
            "total": len(self._entries),
            "by_type": {t.value: len(ids) for t, ids in self._type_index.items()},
            "by_scope": {s.value: len(ids) for s, ids in self._scope_index.items()},
            "immutable": sum(1 for e in self._entries.values() if e.is_immutable),
        }

    def export_for_training(self, output_path: Path) -> int:
        """Export as training data."""
        entries = []
        for entry in self._entries.values():
            entries.append({
                "instruction": f"Define the notation {entry.symbol}",
                "input": entry.symbol,
                "output": json.dumps({
                    "definition": entry.definition,
                    "pattern": entry.pattern,
                    "examples": entry.examples,
                }),
            })

        with open(output_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        return len(entries)


# Singleton accessor
_notation_library_instance: Optional[NotationLibrary] = None


def get_notation_library(storage_path: Path = None) -> NotationLibrary:
    """Get or create NotationLibrary singleton."""
    global _notation_library_instance
    if _notation_library_instance is None:
        _notation_library_instance = NotationLibrary(storage_path)
    return _notation_library_instance

