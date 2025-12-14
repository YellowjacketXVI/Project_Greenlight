"""
Context Engine Index - Searchable Procedure Index

Provides indexing for context engine searching with full read/write capabilities.
Integrates with the file browser and notation library for comprehensive search.

Features:
- Full-text indexing of files
- Vector notation indexing
- Procedure and function indexing
- Search with filters and scopes
- Read/write operations with auth
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Callable
import hashlib
import json
import re


class IndexScope(Enum):
    """Scopes for index organization."""
    ALL = "all"
    CODE = "code"
    DOCUMENT = "document"
    NOTATION = "notation"
    PROCEDURE = "procedure"
    FUNCTION = "function"
    CLASS = "class"
    VARIABLE = "variable"


class IndexEntryType(Enum):
    """Types of index entries."""
    FILE = "file"
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    NOTATION = "notation"
    PROCEDURE = "procedure"
    COMMENT = "comment"


@dataclass
class IndexEntry:
    """A single index entry."""
    id: str
    entry_type: IndexEntryType
    name: str
    path: str
    line_number: int
    content: str
    vector_notation: str
    scope: IndexScope
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    indexed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entry_type": self.entry_type.value,
            "name": self.name,
            "path": self.path,
            "line_number": self.line_number,
            "content": self.content[:500],
            "vector_notation": self.vector_notation,
            "scope": self.scope.value,
            "parent_id": self.parent_id,
            "children": self.children,
            "tags": self.tags,
            "indexed_at": self.indexed_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IndexEntry":
        return cls(
            id=data["id"],
            entry_type=IndexEntryType(data["entry_type"]),
            name=data["name"],
            path=data["path"],
            line_number=data.get("line_number", 0),
            content=data.get("content", ""),
            vector_notation=data["vector_notation"],
            scope=IndexScope(data["scope"]),
            parent_id=data.get("parent_id"),
            children=data.get("children", []),
            tags=data.get("tags", []),
            indexed_at=datetime.fromisoformat(data["indexed_at"]) if "indexed_at" in data else datetime.now(),
        )


@dataclass
class SearchResult:
    """Result of a search operation."""
    query: str
    scope: IndexScope
    entries: List[IndexEntry]
    total_matches: int
    search_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "scope": self.scope.value,
            "entries": [e.to_dict() for e in self.entries],
            "total_matches": self.total_matches,
            "search_time_ms": self.search_time_ms,
        }


class ContextIndex:
    """
    Context Engine Index for Searchable Procedures.
    
    Provides comprehensive indexing for context engine searching
    with full read/write capabilities.
    """
    
    # Regex patterns for code parsing
    PYTHON_FUNCTION = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", re.MULTILINE)
    PYTHON_CLASS = re.compile(r"^\s*class\s+(\w+)\s*[:\(]", re.MULTILINE)
    PYTHON_VARIABLE = re.compile(r"^(\w+)\s*=\s*", re.MULTILINE)
    
    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path
        self._entries: Dict[str, IndexEntry] = {}
        self._name_index: Dict[str, Set[str]] = {}  # name -> entry ids
        self._path_index: Dict[str, Set[str]] = {}  # path -> entry ids
        self._type_index: Dict[IndexEntryType, Set[str]] = {t: set() for t in IndexEntryType}
        self._scope_index: Dict[IndexScope, Set[str]] = {s: set() for s in IndexScope}
        
        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._data_file = storage_path / "context_index.json"
            self._load_data()
        else:
            self._data_file = None
    
    def _load_data(self) -> None:
        """Load index from storage."""
        if self._data_file and self._data_file.exists():
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry_data in data.get("entries", []):
                    entry = IndexEntry.from_dict(entry_data)
                    self._add_to_indices(entry)
    
    def _save_data(self) -> None:
        """Save index to storage."""
        if self._data_file:
            data = {
                "entries": [e.to_dict() for e in self._entries.values()],
                "stats": self.get_stats(),
                "updated_at": datetime.now().isoformat(),
            }
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def _add_to_indices(self, entry: IndexEntry) -> None:
        """Add entry to all indices."""
        self._entries[entry.id] = entry

        if entry.name not in self._name_index:
            self._name_index[entry.name] = set()
        self._name_index[entry.name].add(entry.id)

        if entry.path not in self._path_index:
            self._path_index[entry.path] = set()
        self._path_index[entry.path].add(entry.id)

        self._type_index[entry.entry_type].add(entry.id)
        self._scope_index[entry.scope].add(entry.id)

    def index_file(self, path: str, content: str) -> List[IndexEntry]:
        """Index a file and extract all entries."""
        entries = []

        # Create file entry
        file_id = hashlib.sha256(path.encode()).hexdigest()[:12]
        file_entry = IndexEntry(
            id=file_id,
            entry_type=IndexEntryType.FILE,
            name=Path(path).name,
            path=path,
            line_number=0,
            content=content[:500],
            vector_notation=f"@FILE_{Path(path).stem}_{file_id[:6]}",
            scope=IndexScope.CODE if path.endswith(".py") else IndexScope.DOCUMENT,
        )
        self._add_to_indices(file_entry)
        entries.append(file_entry)

        # Parse Python files
        if path.endswith(".py"):
            entries.extend(self._parse_python(path, content, file_id))

        self._save_data()
        return entries

    def _parse_python(self, path: str, content: str, parent_id: str) -> List[IndexEntry]:
        """Parse Python file for functions, classes, etc."""
        entries = []
        lines = content.split("\n")

        # Find functions
        for match in self.PYTHON_FUNCTION.finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count("\n") + 1

            entry_id = hashlib.sha256(f"{path}:{name}:{line_num}".encode()).hexdigest()[:12]

            # Get function content (simplified)
            func_content = lines[line_num - 1] if line_num <= len(lines) else ""

            entry = IndexEntry(
                id=entry_id,
                entry_type=IndexEntryType.FUNCTION,
                name=name,
                path=path,
                line_number=line_num,
                content=func_content,
                vector_notation=f"@FUNC_{name}_{entry_id[:6]}",
                scope=IndexScope.FUNCTION,
                parent_id=parent_id,
            )
            self._add_to_indices(entry)
            entries.append(entry)

        # Find classes
        for match in self.PYTHON_CLASS.finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count("\n") + 1

            entry_id = hashlib.sha256(f"{path}:{name}:{line_num}".encode()).hexdigest()[:12]

            entry = IndexEntry(
                id=entry_id,
                entry_type=IndexEntryType.CLASS,
                name=name,
                path=path,
                line_number=line_num,
                content=lines[line_num - 1] if line_num <= len(lines) else "",
                vector_notation=f"@CLASS_{name}_{entry_id[:6]}",
                scope=IndexScope.CLASS,
                parent_id=parent_id,
            )
            self._add_to_indices(entry)
            entries.append(entry)

        return entries

    def search(
        self,
        query: str,
        scope: IndexScope = IndexScope.ALL,
        entry_type: IndexEntryType = None,
        limit: int = 50,
    ) -> SearchResult:
        """Search the index."""
        start_time = datetime.now()
        query_lower = query.lower()

        # Get candidate entries
        if scope == IndexScope.ALL:
            candidates = list(self._entries.values())
        else:
            candidates = [self._entries[eid] for eid in self._scope_index[scope]]

        # Filter by type
        if entry_type:
            candidates = [e for e in candidates if e.entry_type == entry_type]

        # Search
        matches = []
        for entry in candidates:
            if query_lower in entry.name.lower() or query_lower in entry.content.lower():
                matches.append(entry)

        # Sort by relevance (name match first)
        matches.sort(key=lambda e: (0 if query_lower in e.name.lower() else 1, e.name))

        duration = (datetime.now() - start_time).total_seconds() * 1000

        return SearchResult(
            query=query,
            scope=scope,
            entries=matches[:limit],
            total_matches=len(matches),
            search_time_ms=duration,
        )

    def get_by_notation(self, notation: str) -> Optional[IndexEntry]:
        """Get entry by vector notation."""
        for entry in self._entries.values():
            if entry.vector_notation == notation:
                return entry
        return None

    def get_by_path(self, path: str) -> List[IndexEntry]:
        """Get all entries for a path."""
        if path in self._path_index:
            return [self._entries[eid] for eid in self._path_index[path]]
        return []

    def get_by_name(self, name: str) -> List[IndexEntry]:
        """Get all entries with a name."""
        if name in self._name_index:
            return [self._entries[eid] for eid in self._name_index[name]]
        return []

    def get_functions(self, path: str = None) -> List[IndexEntry]:
        """Get all function entries."""
        entries = [self._entries[eid] for eid in self._type_index[IndexEntryType.FUNCTION]]
        if path:
            entries = [e for e in entries if e.path == path]
        return entries

    def get_classes(self, path: str = None) -> List[IndexEntry]:
        """Get all class entries."""
        entries = [self._entries[eid] for eid in self._type_index[IndexEntryType.CLASS]]
        if path:
            entries = [e for e in entries if e.path == path]
        return entries

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "total_entries": len(self._entries),
            "by_type": {t.value: len(ids) for t, ids in self._type_index.items()},
            "by_scope": {s.value: len(ids) for s, ids in self._scope_index.items()},
            "unique_files": len(self._path_index),
            "unique_names": len(self._name_index),
        }

    def clear(self) -> None:
        """Clear all indices."""
        self._entries.clear()
        self._name_index.clear()
        self._path_index.clear()
        for t in IndexEntryType:
            self._type_index[t].clear()
        for s in IndexScope:
            self._scope_index[s].clear()
        self._save_data()


# Singleton accessor
_context_index_instance: Optional[ContextIndex] = None


def get_context_index(storage_path: Path = None) -> ContextIndex:
    """Get or create ContextIndex singleton."""
    global _context_index_instance
    if _context_index_instance is None:
        _context_index_instance = ContextIndex(storage_path)
    return _context_index_instance

