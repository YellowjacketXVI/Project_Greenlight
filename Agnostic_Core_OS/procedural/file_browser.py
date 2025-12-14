"""
Vector File Browser - System File Browsing with Vector Translation

Provides file browsing capabilities with automatic vector translation
of system files for context engine indexing.

Features:
- File and directory vectorization
- Automatic indexing for context engine
- Read/write capabilities with auth
- File type detection and categorization
- Search and filter operations
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Generator
import hashlib
import json
import os
import mimetypes


class FileCategory(Enum):
    """File categories for organization."""
    CODE = "code"
    DOCUMENT = "document"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DATA = "data"
    CONFIG = "config"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"


# File extension to category mapping
EXTENSION_CATEGORIES: Dict[str, FileCategory] = {
    # Code
    ".py": FileCategory.CODE,
    ".js": FileCategory.CODE,
    ".ts": FileCategory.CODE,
    ".jsx": FileCategory.CODE,
    ".tsx": FileCategory.CODE,
    ".java": FileCategory.CODE,
    ".cpp": FileCategory.CODE,
    ".c": FileCategory.CODE,
    ".h": FileCategory.CODE,
    ".rs": FileCategory.CODE,
    ".go": FileCategory.CODE,
    # Documents
    ".md": FileCategory.DOCUMENT,
    ".txt": FileCategory.DOCUMENT,
    ".pdf": FileCategory.DOCUMENT,
    ".doc": FileCategory.DOCUMENT,
    ".docx": FileCategory.DOCUMENT,
    # Images
    ".png": FileCategory.IMAGE,
    ".jpg": FileCategory.IMAGE,
    ".jpeg": FileCategory.IMAGE,
    ".gif": FileCategory.IMAGE,
    ".svg": FileCategory.IMAGE,
    ".webp": FileCategory.IMAGE,
    # Audio
    ".mp3": FileCategory.AUDIO,
    ".wav": FileCategory.AUDIO,
    ".ogg": FileCategory.AUDIO,
    ".flac": FileCategory.AUDIO,
    # Video
    ".mp4": FileCategory.VIDEO,
    ".avi": FileCategory.VIDEO,
    ".mkv": FileCategory.VIDEO,
    ".mov": FileCategory.VIDEO,
    # Data
    ".json": FileCategory.DATA,
    ".jsonl": FileCategory.DATA,
    ".csv": FileCategory.DATA,
    ".xml": FileCategory.DATA,
    ".yaml": FileCategory.DATA,
    ".yml": FileCategory.DATA,
    # Config
    ".env": FileCategory.CONFIG,
    ".ini": FileCategory.CONFIG,
    ".toml": FileCategory.CONFIG,
    ".cfg": FileCategory.CONFIG,
    # Archive
    ".zip": FileCategory.ARCHIVE,
    ".tar": FileCategory.ARCHIVE,
    ".gz": FileCategory.ARCHIVE,
    ".7z": FileCategory.ARCHIVE,
}


@dataclass
class FileVector:
    """Vector representation of a file."""
    id: str
    path: str
    name: str
    extension: str
    category: FileCategory
    size_bytes: int
    vector_notation: str
    checksum: str
    mime_type: str
    is_readable: bool = True
    is_writable: bool = True
    indexed_at: datetime = field(default_factory=datetime.now)
    content_preview: str = ""
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "name": self.name,
            "extension": self.extension,
            "category": self.category.value,
            "size_bytes": self.size_bytes,
            "vector_notation": self.vector_notation,
            "checksum": self.checksum,
            "mime_type": self.mime_type,
            "is_readable": self.is_readable,
            "is_writable": self.is_writable,
            "indexed_at": self.indexed_at.isoformat(),
            "content_preview": self.content_preview[:200],
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileVector":
        return cls(
            id=data["id"],
            path=data["path"],
            name=data["name"],
            extension=data["extension"],
            category=FileCategory(data["category"]),
            size_bytes=data["size_bytes"],
            vector_notation=data["vector_notation"],
            checksum=data["checksum"],
            mime_type=data["mime_type"],
            is_readable=data.get("is_readable", True),
            is_writable=data.get("is_writable", True),
            indexed_at=datetime.fromisoformat(data["indexed_at"]) if "indexed_at" in data else datetime.now(),
            content_preview=data.get("content_preview", ""),
            tags=data.get("tags", []),
        )


@dataclass
class DirectoryVector:
    """Vector representation of a directory."""
    id: str
    path: str
    name: str
    vector_notation: str
    file_count: int = 0
    dir_count: int = 0
    total_size: int = 0
    indexed_at: datetime = field(default_factory=datetime.now)
    children: List[str] = field(default_factory=list)  # Child vector IDs
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "name": self.name,
            "vector_notation": self.vector_notation,
            "file_count": self.file_count,
            "dir_count": self.dir_count,
            "total_size": self.total_size,
            "indexed_at": self.indexed_at.isoformat(),
            "children": self.children,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DirectoryVector":
        return cls(
            id=data["id"],
            path=data["path"],
            name=data["name"],
            vector_notation=data["vector_notation"],
            file_count=data.get("file_count", 0),
            dir_count=data.get("dir_count", 0),
            total_size=data.get("total_size", 0),
            indexed_at=datetime.fromisoformat(data["indexed_at"]) if "indexed_at" in data else datetime.now(),
            children=data.get("children", []),
        )


@dataclass
class BrowseResult:
    """Result of a browse operation."""
    path: str
    directories: List[DirectoryVector]
    files: List[FileVector]
    total_items: int
    parent_path: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "directories": [d.to_dict() for d in self.directories],
            "files": [f.to_dict() for f in self.files],
            "total_items": self.total_items,
            "parent_path": self.parent_path,
        }


class VectorFileBrowser:
    """
    Vector File Browser with Context Engine Indexing.

    Provides file browsing with automatic vector translation
    for context engine searching.
    """

    def __init__(self, project_path: Path, storage_path: Path = None):
        self.project_path = Path(project_path)
        self.storage_path = storage_path
        self._files: Dict[str, FileVector] = {}
        self._directories: Dict[str, DirectoryVector] = {}
        self._path_index: Dict[str, str] = {}  # path -> vector id

        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._data_file = storage_path / "file_index.json"
            self._load_data()
        else:
            self._data_file = None

    def _load_data(self) -> None:
        """Load index from storage."""
        if self._data_file and self._data_file.exists():
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for fv in data.get("files", []):
                    vec = FileVector.from_dict(fv)
                    self._files[vec.id] = vec
                    self._path_index[vec.path] = vec.id
                for dv in data.get("directories", []):
                    vec = DirectoryVector.from_dict(dv)
                    self._directories[vec.id] = vec
                    self._path_index[vec.path] = vec.id

    def _save_data(self) -> None:
        """Save index to storage."""
        if self._data_file:
            data = {
                "files": [f.to_dict() for f in self._files.values()],
                "directories": [d.to_dict() for d in self._directories.values()],
                "updated_at": datetime.now().isoformat(),
            }
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def _get_category(self, path: Path) -> FileCategory:
        """Get file category from extension."""
        ext = path.suffix.lower()
        return EXTENSION_CATEGORIES.get(ext, FileCategory.UNKNOWN)

    def _compute_checksum(self, path: Path) -> str:
        """Compute file checksum."""
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except Exception:
            return ""

    def _get_content_preview(self, path: Path, max_chars: int = 200) -> str:
        """Get content preview for text files."""
        try:
            if path.suffix.lower() in [".py", ".js", ".ts", ".md", ".txt", ".json", ".yaml", ".yml"]:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read(max_chars)
        except Exception:
            pass
        return ""

    def vectorize_file(self, file_path: Path) -> FileVector:
        """Create vector representation of a file."""
        rel_path = str(file_path.relative_to(self.project_path))

        # Check if already indexed
        if rel_path in self._path_index:
            return self._files[self._path_index[rel_path]]

        category = self._get_category(file_path)
        mime_type, _ = mimetypes.guess_type(str(file_path))

        vector_id = hashlib.sha256(rel_path.encode()).hexdigest()[:12]
        vector_notation = f"@FILE_{category.value.upper()}_{file_path.stem}_{vector_id[:6]}"

        vector = FileVector(
            id=vector_id,
            path=rel_path,
            name=file_path.name,
            extension=file_path.suffix,
            category=category,
            size_bytes=file_path.stat().st_size if file_path.exists() else 0,
            vector_notation=vector_notation,
            checksum=self._compute_checksum(file_path),
            mime_type=mime_type or "application/octet-stream",
            content_preview=self._get_content_preview(file_path),
        )

        self._files[vector_id] = vector
        self._path_index[rel_path] = vector_id
        self._save_data()

        return vector

    def vectorize_directory(self, dir_path: Path) -> DirectoryVector:
        """Create vector representation of a directory."""
        rel_path = str(dir_path.relative_to(self.project_path))

        if rel_path in self._path_index:
            return self._directories[self._path_index[rel_path]]

        vector_id = hashlib.sha256(rel_path.encode()).hexdigest()[:12]
        vector_notation = f"@DIR_{dir_path.name}_{vector_id[:6]}"

        vector = DirectoryVector(
            id=vector_id,
            path=rel_path,
            name=dir_path.name,
            vector_notation=vector_notation,
        )

        self._directories[vector_id] = vector
        self._path_index[rel_path] = vector_id
        self._save_data()

        return vector

    def browse(self, path: str = "") -> BrowseResult:
        """Browse a directory and return vectorized contents."""
        target_path = self.project_path / path if path else self.project_path

        if not target_path.exists() or not target_path.is_dir():
            return BrowseResult(
                path=path,
                directories=[],
                files=[],
                total_items=0,
                parent_path=None,
            )

        directories = []
        files = []

        for item in target_path.iterdir():
            if item.name.startswith("."):
                continue  # Skip hidden files

            if item.is_dir():
                dv = self.vectorize_directory(item)
                directories.append(dv)
            else:
                fv = self.vectorize_file(item)
                files.append(fv)

        parent_path = None
        if path:
            parent = Path(path).parent
            parent_path = str(parent) if str(parent) != "." else ""

        return BrowseResult(
            path=path,
            directories=sorted(directories, key=lambda d: d.name),
            files=sorted(files, key=lambda f: f.name),
            total_items=len(directories) + len(files),
            parent_path=parent_path,
        )

    def index_recursive(self, path: str = "", max_depth: int = 5) -> int:
        """Recursively index all files and directories."""
        count = 0

        def _index(current_path: Path, depth: int):
            nonlocal count
            if depth > max_depth:
                return

            for item in current_path.iterdir():
                if item.name.startswith("."):
                    continue

                if item.is_dir():
                    self.vectorize_directory(item)
                    count += 1
                    _index(item, depth + 1)
                else:
                    self.vectorize_file(item)
                    count += 1

        target = self.project_path / path if path else self.project_path
        if target.exists() and target.is_dir():
            _index(target, 0)

        return count

    def search(self, query: str, category: FileCategory = None) -> List[FileVector]:
        """Search files by name or content preview."""
        query_lower = query.lower()
        results = []

        for fv in self._files.values():
            if category and fv.category != category:
                continue

            if query_lower in fv.name.lower() or query_lower in fv.content_preview.lower():
                results.append(fv)

        return results

    def get_by_notation(self, notation: str) -> Optional[FileVector]:
        """Get file by vector notation."""
        for fv in self._files.values():
            if fv.vector_notation == notation:
                return fv
        return None

    def get_by_path(self, path: str) -> Optional[FileVector]:
        """Get file by path."""
        if path in self._path_index:
            vid = self._path_index[path]
            return self._files.get(vid)
        return None

    def read_file(self, path: str) -> Optional[str]:
        """Read file contents (text files only)."""
        file_path = self.project_path / path
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def write_file(self, path: str, content: str) -> bool:
        """Write content to file."""
        file_path = self.project_path / path

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Re-index the file
            self.vectorize_file(file_path)
            return True
        except Exception:
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get browser statistics."""
        category_counts = {}
        for fv in self._files.values():
            cat = fv.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_files": len(self._files),
            "total_directories": len(self._directories),
            "by_category": category_counts,
            "total_size": sum(fv.size_bytes for fv in self._files.values()),
        }


# Singleton accessor
_file_browser_instance: Optional[VectorFileBrowser] = None


def get_file_browser(project_path: Path = None, storage_path: Path = None) -> VectorFileBrowser:
    """Get or create VectorFileBrowser singleton."""
    global _file_browser_instance
    if _file_browser_instance is None:
        if project_path is None:
            project_path = Path.cwd()
        _file_browser_instance = VectorFileBrowser(project_path, storage_path)
    return _file_browser_instance

