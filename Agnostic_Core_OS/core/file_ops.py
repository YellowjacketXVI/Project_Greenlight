"""
File Operations - Cross-Platform File System Utilities

Provides platform-agnostic file operations that work consistently
across Windows, macOS, and Linux.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from datetime import datetime
import json
import shutil
import tempfile

from ..translators.systems_translator import get_systems_translator, OSType


@dataclass
class FileInfo:
    """Information about a file."""
    path: Path
    name: str
    extension: str
    size: int
    is_file: bool
    is_dir: bool
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "name": self.name,
            "extension": self.extension,
            "size": self.size,
            "is_file": self.is_file,
            "is_dir": self.is_dir,
            "created": self.created.isoformat() if self.created else None,
            "modified": self.modified.isoformat() if self.modified else None
        }


class FileOperations:
    """
    Cross-platform file operations.
    
    Provides consistent file system operations across all platforms.
    
    Example:
        file_ops = FileOperations()
        
        # Read/write files
        content = file_ops.read_text("config.json")
        file_ops.write_text("output.txt", "Hello World")
        
        # Directory operations
        file_ops.ensure_directory("output/images")
        files = file_ops.list_files("data", pattern="*.json")
        
        # File info
        info = file_ops.get_file_info("document.pdf")
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """Initialize file operations."""
        self.base_path = base_path or Path.cwd()
        self._translator = get_systems_translator()
        self._system_info = self._translator.get_system_info()
    
    def _resolve_path(self, path: Union[str, Path]) -> Path:
        """Resolve a path relative to base path."""
        path = Path(path)
        if not path.is_absolute():
            path = self.base_path / path
        return path
    
    def read_text(
        self,
        path: Union[str, Path],
        encoding: Optional[str] = None
    ) -> str:
        """
        Read a text file.
        
        Args:
            path: Path to file
            encoding: File encoding (auto-detected if None)
            
        Returns:
            File contents as string
        """
        resolved = self._resolve_path(path)
        enc = encoding or self._translator.get_build_parameters().file_encoding
        
        with open(resolved, 'r', encoding=enc) as f:
            return f.read()
    
    def write_text(
        self,
        path: Union[str, Path],
        content: str,
        encoding: Optional[str] = None
    ) -> Path:
        """
        Write text to a file.
        
        Args:
            path: Path to file
            content: Content to write
            encoding: File encoding
            
        Returns:
            Path to written file
        """
        resolved = self._resolve_path(path)
        enc = encoding or self._translator.get_build_parameters().file_encoding
        
        # Ensure parent directory exists
        self.ensure_directory(resolved.parent)
        
        with open(resolved, 'w', encoding=enc) as f:
            f.write(content)
        
        return resolved
    
    def read_json(self, path: Union[str, Path]) -> Any:
        """Read a JSON file."""
        content = self.read_text(path)
        return json.loads(content)
    
    def write_json(
        self,
        path: Union[str, Path],
        data: Any,
        indent: int = 2
    ) -> Path:
        """Write data to a JSON file."""
        content = json.dumps(data, indent=indent, ensure_ascii=False)
        return self.write_text(path, content)
    
    def read_bytes(self, path: Union[str, Path]) -> bytes:
        """Read a binary file."""
        resolved = self._resolve_path(path)
        with open(resolved, 'rb') as f:
            return f.read()
    
    def write_bytes(self, path: Union[str, Path], data: bytes) -> Path:
        """Write binary data to a file."""
        resolved = self._resolve_path(path)
        self.ensure_directory(resolved.parent)
        with open(resolved, 'wb') as f:
            f.write(data)
        return resolved
    
    def ensure_directory(self, path: Union[str, Path]) -> Path:
        """Ensure a directory exists, creating if necessary."""
        resolved = self._resolve_path(path)
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def exists(self, path: Union[str, Path]) -> bool:
        """Check if a path exists."""
        return self._resolve_path(path).exists()

    def is_file(self, path: Union[str, Path]) -> bool:
        """Check if path is a file."""
        return self._resolve_path(path).is_file()

    def is_directory(self, path: Union[str, Path]) -> bool:
        """Check if path is a directory."""
        return self._resolve_path(path).is_dir()

    def list_files(
        self,
        directory: Union[str, Path],
        pattern: str = "*",
        recursive: bool = False
    ) -> List[Path]:
        """
        List files in a directory.

        Args:
            directory: Directory to search
            pattern: Glob pattern
            recursive: Search recursively

        Returns:
            List of matching file paths
        """
        resolved = self._resolve_path(directory)
        if not resolved.exists():
            return []

        if recursive:
            return list(resolved.rglob(pattern))
        return list(resolved.glob(pattern))

    def list_directories(
        self,
        directory: Union[str, Path],
        recursive: bool = False
    ) -> List[Path]:
        """List subdirectories in a directory."""
        resolved = self._resolve_path(directory)
        if not resolved.exists():
            return []

        if recursive:
            return [p for p in resolved.rglob("*") if p.is_dir()]
        return [p for p in resolved.iterdir() if p.is_dir()]

    def get_file_info(self, path: Union[str, Path]) -> FileInfo:
        """Get information about a file."""
        resolved = self._resolve_path(path)
        stat = resolved.stat()

        return FileInfo(
            path=resolved,
            name=resolved.name,
            extension=resolved.suffix,
            size=stat.st_size,
            is_file=resolved.is_file(),
            is_dir=resolved.is_dir(),
            created=datetime.fromtimestamp(stat.st_ctime),
            modified=datetime.fromtimestamp(stat.st_mtime)
        )

    def copy_file(
        self,
        source: Union[str, Path],
        destination: Union[str, Path]
    ) -> Path:
        """Copy a file."""
        src = self._resolve_path(source)
        dst = self._resolve_path(destination)
        self.ensure_directory(dst.parent)
        shutil.copy2(src, dst)
        return dst

    def copy_directory(
        self,
        source: Union[str, Path],
        destination: Union[str, Path]
    ) -> Path:
        """Copy a directory recursively."""
        src = self._resolve_path(source)
        dst = self._resolve_path(destination)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return dst

    def move(
        self,
        source: Union[str, Path],
        destination: Union[str, Path]
    ) -> Path:
        """Move a file or directory."""
        src = self._resolve_path(source)
        dst = self._resolve_path(destination)
        self.ensure_directory(dst.parent)
        shutil.move(str(src), str(dst))
        return dst

    def delete_file(self, path: Union[str, Path]) -> bool:
        """Delete a file."""
        resolved = self._resolve_path(path)
        if resolved.is_file():
            resolved.unlink()
            return True
        return False

    def delete_directory(
        self,
        path: Union[str, Path],
        recursive: bool = False
    ) -> bool:
        """Delete a directory."""
        resolved = self._resolve_path(path)
        if resolved.is_dir():
            if recursive:
                shutil.rmtree(resolved)
            else:
                resolved.rmdir()
            return True
        return False

    def get_temp_file(self, suffix: str = "", prefix: str = "tmp") -> Path:
        """Get a temporary file path."""
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        import os
        os.close(fd)
        return Path(path)

    def get_temp_directory(self, prefix: str = "tmp") -> Path:
        """Get a temporary directory path."""
        return Path(tempfile.mkdtemp(prefix=prefix))

    def safe_filename(self, name: str) -> str:
        """Convert a string to a safe filename."""
        # Remove or replace unsafe characters
        unsafe = '<>:"/\\|?*'
        result = name
        for char in unsafe:
            result = result.replace(char, '_')
        return result.strip()


# Singleton instance
_file_ops: Optional[FileOperations] = None


def get_file_ops(base_path: Optional[Path] = None) -> FileOperations:
    """Get the default FileOperations instance."""
    global _file_ops
    if _file_ops is None:
        _file_ops = FileOperations(base_path)
    return _file_ops
