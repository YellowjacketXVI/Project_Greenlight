"""
Greenlight File Utilities

Common file operations with error handling and encoding support.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

from greenlight.core.exceptions import GreenlightError


def read_json(path: Union[str, Path], encoding: str = 'utf-8') -> Dict[str, Any]:
    """
    Read and parse a JSON file.
    
    Args:
        path: Path to JSON file
        encoding: File encoding (default: utf-8)
        
    Returns:
        Parsed JSON data as dictionary
        
    Raises:
        GreenlightError: If file cannot be read or parsed
    """
    path = Path(path)
    if not path.exists():
        raise GreenlightError(f"File not found: {path}")
    
    try:
        with open(path, 'r', encoding=encoding) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise GreenlightError(f"Invalid JSON in {path}: {e}")
    except Exception as e:
        raise GreenlightError(f"Failed to read {path}: {e}")


def write_json(
    path: Union[str, Path],
    data: Dict[str, Any],
    encoding: str = 'utf-8',
    indent: int = 2,
    ensure_ascii: bool = False
) -> None:
    """
    Write data to a JSON file.
    
    Args:
        path: Path to JSON file
        data: Data to write
        encoding: File encoding (default: utf-8)
        indent: JSON indentation (default: 2)
        ensure_ascii: If False, allow non-ASCII characters
    """
    path = Path(path)
    ensure_directory(path.parent)
    
    try:
        with open(path, 'w', encoding=encoding) as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
    except Exception as e:
        raise GreenlightError(f"Failed to write {path}: {e}")


def read_text(path: Union[str, Path], encoding: str = 'utf-8') -> str:
    """
    Read a text file.
    
    Args:
        path: Path to text file
        encoding: File encoding (default: utf-8)
        
    Returns:
        File contents as string
    """
    path = Path(path)
    if not path.exists():
        raise GreenlightError(f"File not found: {path}")
    
    try:
        with open(path, 'r', encoding=encoding) as f:
            return f.read()
    except Exception as e:
        raise GreenlightError(f"Failed to read {path}: {e}")


def write_text(
    path: Union[str, Path],
    content: str,
    encoding: str = 'utf-8'
) -> None:
    """
    Write text to a file.
    
    Args:
        path: Path to text file
        content: Content to write
        encoding: File encoding (default: utf-8)
    """
    path = Path(path)
    ensure_directory(path.parent)
    
    try:
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
    except Exception as e:
        raise GreenlightError(f"Failed to write {path}: {e}")


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path
        
    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str, max_length: int = 100) -> str:
    """
    Convert a string to a safe filename.
    
    Args:
        name: Original name
        max_length: Maximum filename length
        
    Returns:
        Safe filename string
    """
    # Remove or replace invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Replace multiple spaces/underscores with single underscore
    safe = re.sub(r'[\s_]+', '_', safe)
    # Remove leading/trailing underscores
    safe = safe.strip('_')
    # Truncate if too long
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip('_')
    return safe or "unnamed"


def get_file_hash(path: Union[str, Path]) -> str:
    """
    Get MD5 hash of a file for change detection.
    
    Args:
        path: Path to file
        
    Returns:
        MD5 hash string
    """
    import hashlib
    
    path = Path(path)
    if not path.exists():
        raise GreenlightError(f"File not found: {path}")
    
    hasher = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def list_files(
    directory: Union[str, Path],
    pattern: str = "*",
    recursive: bool = False
) -> list:
    """
    List files in a directory matching a pattern.
    
    Args:
        directory: Directory to search
        pattern: Glob pattern (default: "*")
        recursive: If True, search recursively
        
    Returns:
        List of matching file paths
    """
    directory = Path(directory)
    if not directory.exists():
        return []
    
    if recursive:
        return list(directory.rglob(pattern))
    return list(directory.glob(pattern))

