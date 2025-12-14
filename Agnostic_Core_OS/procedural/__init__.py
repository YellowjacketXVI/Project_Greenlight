"""
Agnostic_Core_OS Procedural Module

Core procedural systems for:
- Vector notation library and cataloging
- File browsing with vector translation
- Context engine indexing
- Procedural UI generation
"""

from .notation_library import (
    NotationLibrary,
    NotationEntry,
    NotationType,
    NotationScope,
    get_notation_library,
)
from .file_browser import (
    VectorFileBrowser,
    FileVector,
    DirectoryVector,
    BrowseResult,
    FileCategory,
    get_file_browser,
)
from .context_index import (
    ContextIndex,
    IndexEntry,
    SearchResult,
    IndexScope,
    IndexEntryType,
    get_context_index,
)

__all__ = [
    # Notation Library
    "NotationLibrary",
    "NotationEntry",
    "NotationType",
    "NotationScope",
    "get_notation_library",
    # File Browser
    "VectorFileBrowser",
    "FileVector",
    "DirectoryVector",
    "BrowseResult",
    "FileCategory",
    "get_file_browser",
    # Context Index
    "ContextIndex",
    "IndexEntry",
    "SearchResult",
    "IndexScope",
    "IndexEntryType",
    "get_context_index",
]

