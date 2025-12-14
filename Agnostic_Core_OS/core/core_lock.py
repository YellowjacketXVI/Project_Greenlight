"""
Core Lock System - Protected Critical System Code

This module defines the immutable core of Agnostic_Core_OS.
Files and directories listed here CANNOT be edited externally.

Features:
- Immutable core file registry
- Scope and capability definitions
- Guidelines enforcement
- Checksum validation for integrity
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, FrozenSet
import hashlib
import json


class CoreScope(Enum):
    """Scope levels for core capabilities."""
    SYSTEM = "system"           # Core OS operations
    AUTHENTICATION = "auth"     # Security and access control
    NOTATION = "notation"       # Vector notation library
    TRANSLATION = "translation" # Language translation
    INDEXING = "indexing"       # File and context indexing
    PROCEDURAL = "procedural"   # Procedural generation


class Capability(Enum):
    """Core system capabilities."""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_INDEX = "file_index"
    VECTOR_TRANSLATE = "vector_translate"
    CONTEXT_SEARCH = "context_search"
    AUTH_VALIDATE = "auth_validate"
    NOTATION_DEFINE = "notation_define"
    NOTATION_CATALOG = "notation_catalog"
    PROCEDURAL_GROW = "procedural_grow"
    SYSTEM_LOCK = "system_lock"


@dataclass(frozen=True)
class CoreFile:
    """Immutable core file definition."""
    path: str
    scope: CoreScope
    capabilities: FrozenSet[Capability]
    description: str
    checksum: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "scope": self.scope.value,
            "capabilities": [c.value for c in self.capabilities],
            "description": self.description,
            "checksum": self.checksum,
        }


# =============================================================================
# IMMUTABLE CORE REGISTRY - DO NOT MODIFY
# =============================================================================

CORE_FILES: FrozenSet[CoreFile] = frozenset([
    CoreFile(
        path="Agnostic_Core_OS/core/vector_auth.py",
        scope=CoreScope.AUTHENTICATION,
        capabilities=frozenset([Capability.AUTH_VALIDATE, Capability.SYSTEM_LOCK]),
        description="Vector key authentication and access control",
    ),
    CoreFile(
        path="Agnostic_Core_OS/core/core_lock.py",
        scope=CoreScope.SYSTEM,
        capabilities=frozenset([Capability.SYSTEM_LOCK]),
        description="Core lock system - this file",
    ),
    CoreFile(
        path="Agnostic_Core_OS/procedural/notation_library.py",
        scope=CoreScope.NOTATION,
        capabilities=frozenset([Capability.NOTATION_DEFINE, Capability.NOTATION_CATALOG, Capability.PROCEDURAL_GROW]),
        description="Vector notation library and catalog",
    ),
    CoreFile(
        path="Agnostic_Core_OS/procedural/file_browser.py",
        scope=CoreScope.INDEXING,
        capabilities=frozenset([Capability.FILE_READ, Capability.FILE_INDEX, Capability.CONTEXT_SEARCH]),
        description="Vector file browser with indexing",
    ),
    CoreFile(
        path="Agnostic_Core_OS/procedural/context_index.py",
        scope=CoreScope.INDEXING,
        capabilities=frozenset([Capability.FILE_READ, Capability.FILE_WRITE, Capability.CONTEXT_SEARCH]),
        description="Context engine indexing system",
    ),
])

# Immutable capability scope mappings
SCOPE_CAPABILITIES: Dict[CoreScope, FrozenSet[Capability]] = {
    CoreScope.SYSTEM: frozenset([Capability.SYSTEM_LOCK]),
    CoreScope.AUTHENTICATION: frozenset([Capability.AUTH_VALIDATE, Capability.SYSTEM_LOCK]),
    CoreScope.NOTATION: frozenset([Capability.NOTATION_DEFINE, Capability.NOTATION_CATALOG, Capability.PROCEDURAL_GROW]),
    CoreScope.TRANSLATION: frozenset([Capability.VECTOR_TRANSLATE]),
    CoreScope.INDEXING: frozenset([Capability.FILE_READ, Capability.FILE_WRITE, Capability.FILE_INDEX, Capability.CONTEXT_SEARCH]),
    CoreScope.PROCEDURAL: frozenset([Capability.PROCEDURAL_GROW, Capability.NOTATION_CATALOG]),
}

# =============================================================================
# GUIDELINES - IMMUTABLE OPERATIONAL RULES
# =============================================================================

CORE_GUIDELINES: Dict[str, str] = {
    "NO_EXTERNAL_EDIT": "Core files cannot be modified by external processes",
    "AUTH_REQUIRED": "All write operations require vector key authentication",
    "CHECKSUM_VALIDATE": "File integrity must be validated before operations",
    "NOTATION_IMMUTABLE": "Core notation definitions cannot be changed once cataloged",
    "SCOPE_ENFORCE": "Operations must stay within their defined scope",
    "AUDIT_ALL": "All access attempts must be logged",
    "PROCEDURAL_APPEND": "Procedural growth is append-only, no deletions",
}


class CoreLock:
    """
    Core Lock System for protecting critical system code.
    
    This class enforces immutability of core files and validates
    operations against defined scopes and capabilities.
    """
    
    def __init__(self, project_path: Path = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self._checksums: Dict[str, str] = {}
        self._compute_checksums()
    
    def _compute_checksums(self) -> None:
        """Compute checksums for all core files."""
        for core_file in CORE_FILES:
            file_path = self.project_path / core_file.path
            if file_path.exists():
                with open(file_path, "rb") as f:
                    self._checksums[core_file.path] = hashlib.sha256(f.read()).hexdigest()
    
    def is_core_file(self, path: str) -> bool:
        """Check if a path is a core file."""
        return any(cf.path == path for cf in CORE_FILES)
    
    def get_core_file(self, path: str) -> Optional[CoreFile]:
        """Get core file definition."""
        for cf in CORE_FILES:
            if cf.path == path:
                return cf
        return None

    def validate_integrity(self, path: str) -> bool:
        """Validate file integrity against stored checksum."""
        if path not in self._checksums:
            return True  # Not a tracked file

        file_path = self.project_path / path
        if not file_path.exists():
            return False

        with open(file_path, "rb") as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()

        return current_hash == self._checksums[path]

    def can_modify(self, path: str) -> bool:
        """Check if a path can be modified."""
        return not self.is_core_file(path)

    def get_scope(self, path: str) -> Optional[CoreScope]:
        """Get the scope of a core file."""
        cf = self.get_core_file(path)
        return cf.scope if cf else None

    def get_capabilities(self, path: str) -> FrozenSet[Capability]:
        """Get capabilities of a core file."""
        cf = self.get_core_file(path)
        return cf.capabilities if cf else frozenset()

    def has_capability(self, path: str, capability: Capability) -> bool:
        """Check if a file has a specific capability."""
        return capability in self.get_capabilities(path)

    def list_core_files(self) -> List[Dict[str, Any]]:
        """List all core files."""
        return [cf.to_dict() for cf in CORE_FILES]

    def list_guidelines(self) -> Dict[str, str]:
        """Get all core guidelines."""
        return CORE_GUIDELINES.copy()

    def get_scope_capabilities(self, scope: CoreScope) -> FrozenSet[Capability]:
        """Get all capabilities for a scope."""
        return SCOPE_CAPABILITIES.get(scope, frozenset())

    def validate_operation(
        self,
        path: str,
        operation: str,
        required_capability: Capability,
    ) -> tuple[bool, str]:
        """
        Validate if an operation is allowed.

        Returns:
            (allowed, reason)
        """
        # Check if core file
        if self.is_core_file(path):
            if operation == "write" or operation == "delete":
                return False, CORE_GUIDELINES["NO_EXTERNAL_EDIT"]

        # Check integrity
        if not self.validate_integrity(path):
            return False, "File integrity check failed"

        # Check capability
        cf = self.get_core_file(path)
        if cf and required_capability not in cf.capabilities:
            return False, f"File does not have capability: {required_capability.value}"

        return True, "Operation allowed"

    def get_protected_paths(self) -> List[str]:
        """Get all protected paths."""
        return [cf.path for cf in CORE_FILES]

    def generate_report(self) -> Dict[str, Any]:
        """Generate a core lock status report."""
        integrity_status = {}
        for cf in CORE_FILES:
            integrity_status[cf.path] = self.validate_integrity(cf.path)

        return {
            "core_files": len(CORE_FILES),
            "guidelines": len(CORE_GUIDELINES),
            "scopes": [s.value for s in CoreScope],
            "capabilities": [c.value for c in Capability],
            "integrity_status": integrity_status,
            "all_valid": all(integrity_status.values()),
            "generated_at": datetime.now().isoformat(),
        }


# Singleton accessor
_core_lock_instance: Optional[CoreLock] = None


def get_core_lock(project_path: Path = None) -> CoreLock:
    """Get or create CoreLock singleton."""
    global _core_lock_instance
    if _core_lock_instance is None:
        _core_lock_instance = CoreLock(project_path)
    return _core_lock_instance

