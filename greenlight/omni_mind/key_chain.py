"""
Greenlight Key Chain Tracking System

Tracks and logs vectored key retrievals with permission-based access.
Provides audit trail for all retrieval requests and data access.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from pathlib import Path
from enum import Enum
import json

from greenlight.core.logging_config import get_logger
from greenlight.utils.file_utils import read_json, write_json, ensure_directory

logger = get_logger("omni_mind.key_chain")


class KeyType(Enum):
    """Types of tracked keys."""
    RETRIEVAL = "retrieval"      # Context retrieval key
    NOTATION = "notation"        # Notation definition key
    TAG = "tag"                  # Tag reference key
    CACHE = "cache"              # Cache entry key
    PERMISSION = "permission"    # Permission access key
    VECTOR = "vector"            # Vector search key
    TASK = "task"                # Task execution key


class AccessLevel(Enum):
    """Access levels for keys."""
    PUBLIC = "public"            # Anyone can access
    USER = "user"                # User-level access
    ELEVATED = "elevated"        # Elevated permissions required
    RESTRICTED = "restricted"    # Restricted access
    SYSTEM = "system"            # System-only access


@dataclass
class TrackedKey:
    """A tracked key in the key chain."""
    id: str
    key_type: KeyType
    key_value: str
    access_level: AccessLevel
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    source: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key_type": self.key_type.value,
            "key_value": self.key_value,
            "access_level": self.access_level.value,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "source": self.source,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackedKey":
        return cls(
            id=data["id"],
            key_type=KeyType(data["key_type"]),
            key_value=data["key_value"],
            access_level=AccessLevel(data.get("access_level", "user")),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            last_accessed=datetime.fromisoformat(data.get("last_accessed", datetime.now().isoformat())),
            access_count=data.get("access_count", 0),
            source=data.get("source", "system"),
            metadata=data.get("metadata", {})
        )


@dataclass
class KeyAccessLog:
    """Log entry for key access."""
    id: str
    key_id: str
    timestamp: datetime
    action: str  # access, create, update, delete
    accessor: str
    granted: bool
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key_id": self.key_id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "accessor": self.accessor,
            "granted": self.granted,
            "reason": self.reason
        }


class KeyChain:
    """
    Key chain tracking system for OmniMind.
    
    Features:
    - Track all vectored key retrievals
    - Permission-based access control
    - Audit trail for all access
    - Key lifecycle management
    - Statistics and reporting
    """
    
    def __init__(
        self,
        project_path: Path = None,
        permission_manager: Any = None
    ):
        """
        Initialize key chain.
        
        Args:
            project_path: Project root path
            permission_manager: PermissionManager for access control
        """
        self.project_path = project_path
        self.permission_manager = permission_manager
        
        self._keys: Dict[str, TrackedKey] = {}
        self._access_log: List[KeyAccessLog] = []
        self._next_id = 0
        
        # Setup storage
        if project_path:
            self.chain_dir = project_path / ".keychain"
            ensure_directory(self.chain_dir)
            self.keys_file = self.chain_dir / "keys.json"
            self.log_file = self.chain_dir / "access_log.json"
            self._load_from_disk()
        else:
            self.chain_dir = None
    
    def _generate_id(self, prefix: str = "key") -> str:
        """Generate unique ID."""
        self._next_id += 1
        return f"{prefix}_{self._next_id:08d}"
    
    def _load_from_disk(self) -> None:
        """Load keys from disk."""
        try:
            if self.keys_file and self.keys_file.exists():
                data = read_json(self.keys_file)
                for key_data in data.get("keys", []):
                    key = TrackedKey.from_dict(key_data)
                    self._keys[key.id] = key
                self._next_id = data.get("next_id", len(self._keys))
                logger.info(f"Loaded {len(self._keys)} keys from disk")
        except Exception as e:
            logger.error(f"Failed to load keys: {e}")

    def _save_to_disk(self) -> None:
        """Save keys to disk."""
        try:
            if self.keys_file:
                data = {
                    "next_id": self._next_id,
                    "keys": [k.to_dict() for k in self._keys.values()]
                }
                write_json(self.keys_file, data)
        except Exception as e:
            logger.error(f"Failed to save keys: {e}")

    def _log_access(
        self,
        key_id: str,
        action: str,
        accessor: str,
        granted: bool,
        reason: str = ""
    ) -> KeyAccessLog:
        """Log a key access."""
        log_entry = KeyAccessLog(
            id=self._generate_id("log"),
            key_id=key_id,
            timestamp=datetime.now(),
            action=action,
            accessor=accessor,
            granted=granted,
            reason=reason
        )
        self._access_log.append(log_entry)
        return log_entry

    def _check_access(self, key: TrackedKey, accessor: str) -> bool:
        """Check if accessor has permission to access key."""
        # System always has access
        if accessor == "system":
            return True

        # Check based on access level
        if key.access_level == AccessLevel.PUBLIC:
            return True
        elif key.access_level == AccessLevel.USER:
            return True  # All users can access
        elif key.access_level == AccessLevel.ELEVATED:
            # Check permission manager if available
            if self.permission_manager:
                from .permissions import PermissionTier
                return self.permission_manager.get_tier() in [
                    PermissionTier.FULL, PermissionTier.MODERATE
                ]
            return False
        elif key.access_level == AccessLevel.RESTRICTED:
            if self.permission_manager:
                from .permissions import PermissionTier
                return self.permission_manager.get_tier() == PermissionTier.FULL
            return False
        elif key.access_level == AccessLevel.SYSTEM:
            return accessor == "system"

        return False

    # =========================================================================
    # KEY MANAGEMENT
    # =========================================================================

    def register_key(
        self,
        key_value: str,
        key_type: KeyType,
        access_level: AccessLevel = AccessLevel.USER,
        source: str = "system",
        **metadata
    ) -> TrackedKey:
        """
        Register a new key in the chain.

        Args:
            key_value: The key value
            key_type: Type of key
            access_level: Access level required
            source: Source of the key
            **metadata: Additional metadata

        Returns:
            Created TrackedKey
        """
        key = TrackedKey(
            id=self._generate_id("key"),
            key_type=key_type,
            key_value=key_value,
            access_level=access_level,
            source=source,
            metadata=metadata
        )

        self._keys[key.id] = key
        self._log_access(key.id, "create", source, True)
        self._save_to_disk()

        logger.debug(f"Registered key: {key.id} ({key_type.value})")
        return key

    def access_key(
        self,
        key_id: str,
        accessor: str = "user"
    ) -> Optional[TrackedKey]:
        """
        Access a key (with permission check).

        Args:
            key_id: Key ID
            accessor: Who is accessing

        Returns:
            TrackedKey if access granted, None otherwise
        """
        key = self._keys.get(key_id)
        if not key:
            self._log_access(key_id, "access", accessor, False, "Key not found")
            return None

        if not self._check_access(key, accessor):
            self._log_access(key_id, "access", accessor, False, "Permission denied")
            logger.warning(f"Access denied to key {key_id} for {accessor}")
            return None

        # Update access stats
        key.last_accessed = datetime.now()
        key.access_count += 1
        self._log_access(key_id, "access", accessor, True)
        self._save_to_disk()

        return key

    def find_key_by_value(
        self,
        key_value: str,
        accessor: str = "user"
    ) -> Optional[TrackedKey]:
        """Find a key by its value."""
        for key in self._keys.values():
            if key.key_value == key_value:
                return self.access_key(key.id, accessor)
        return None

    def get_keys_by_type(self, key_type: KeyType) -> List[TrackedKey]:
        """Get all keys of a specific type."""
        return [k for k in self._keys.values() if k.key_type == key_type]

    def revoke_key(self, key_id: str, revoker: str = "system") -> bool:
        """Revoke (delete) a key."""
        if key_id in self._keys:
            self._log_access(key_id, "delete", revoker, True)
            del self._keys[key_id]
            self._save_to_disk()
            logger.info(f"Key revoked: {key_id}")
            return True
        return False

    # =========================================================================
    # RETRIEVAL TRACKING
    # =========================================================================

    def track_retrieval(
        self,
        query: str,
        scope: str,
        results_count: int,
        accessor: str = "user"
    ) -> TrackedKey:
        """
        Track a retrieval request.

        Args:
            query: The retrieval query
            scope: Retrieval scope
            results_count: Number of results
            accessor: Who made the request

        Returns:
            Created TrackedKey for the retrieval
        """
        return self.register_key(
            key_value=query,
            key_type=KeyType.RETRIEVAL,
            access_level=AccessLevel.USER,
            source=accessor,
            scope=scope,
            results_count=results_count
        )

    def track_vector_search(
        self,
        vector_query: str,
        weight: float,
        accessor: str = "user"
    ) -> TrackedKey:
        """Track a vector search."""
        return self.register_key(
            key_value=vector_query,
            key_type=KeyType.VECTOR,
            access_level=AccessLevel.USER,
            source=accessor,
            weight=weight
        )

    # =========================================================================
    # AUDIT & REPORTING
    # =========================================================================

    def get_access_log(
        self,
        key_id: str = None,
        action: str = None,
        limit: int = 100
    ) -> List[KeyAccessLog]:
        """Get filtered access log."""
        results = []
        for entry in reversed(self._access_log):
            if len(results) >= limit:
                break
            if key_id and entry.key_id != key_id:
                continue
            if action and entry.action != action:
                continue
            results.append(entry)
        return list(reversed(results))

    def get_denied_accesses(self, limit: int = 50) -> List[KeyAccessLog]:
        """Get recent denied access attempts."""
        return [e for e in self._access_log if not e.granted][-limit:]

    def get_most_accessed_keys(self, limit: int = 10) -> List[TrackedKey]:
        """Get most frequently accessed keys."""
        sorted_keys = sorted(
            self._keys.values(),
            key=lambda k: k.access_count,
            reverse=True
        )
        return sorted_keys[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get key chain statistics."""
        by_type = {}
        by_level = {}

        for key in self._keys.values():
            kt = key.key_type.value
            by_type[kt] = by_type.get(kt, 0) + 1
            al = key.access_level.value
            by_level[al] = by_level.get(al, 0) + 1

        denied = len([e for e in self._access_log if not e.granted])

        return {
            "total_keys": len(self._keys),
            "total_accesses": len(self._access_log),
            "denied_accesses": denied,
            "by_type": by_type,
            "by_access_level": by_level
        }

    def export_audit_report(self) -> str:
        """Export audit report as markdown."""
        lines = [
            "# Key Chain Audit Report",
            f"",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            "## Summary",
            f"- Total Keys: {len(self._keys)}",
            f"- Total Accesses: {len(self._access_log)}",
            f"- Denied Accesses: {len(self.get_denied_accesses())}",
            f"",
            "## Most Accessed Keys",
            "",
            "| Key ID | Type | Value | Access Count |",
            "|--------|------|-------|--------------|",
        ]

        for key in self.get_most_accessed_keys(10):
            lines.append(
                f"| {key.id} | {key.key_type.value} | {key.key_value[:30]} | {key.access_count} |"
            )

        lines.extend([
            "",
            "## Recent Denied Accesses",
            "",
        ])

        for entry in self.get_denied_accesses(10):
            lines.append(f"- [{entry.timestamp.strftime('%H:%M:%S')}] {entry.key_id}: {entry.reason}")

        return "\n".join(lines)

