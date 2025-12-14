"""
Vector Key Authentication System

Provides secure access control for Agnostic_Core_OS core directories.
Uses .env-based authorization with vector key authentication.

Features:
- Vector key generation and validation
- .env file management for secure storage
- Directory access protection
- Permission levels for read/write/execute
- Audit logging for access attempts
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import hashlib
import secrets
import json
import os


class AccessLevel(Enum):
    """Access permission levels."""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class AuthResult(Enum):
    """Authentication result codes."""
    SUCCESS = "success"
    INVALID_KEY = "invalid_key"
    EXPIRED_KEY = "expired_key"
    INSUFFICIENT_PERMISSION = "insufficient_permission"
    LOCKED_RESOURCE = "locked_resource"
    NOT_INITIALIZED = "not_initialized"


@dataclass
class VectorKey:
    """Vector authentication key."""
    id: str
    key_hash: str
    access_level: AccessLevel
    protected_paths: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    use_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key_hash": self.key_hash,
            "access_level": self.access_level.value,
            "protected_paths": self.protected_paths,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "use_count": self.use_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorKey":
        return cls(
            id=data["id"],
            key_hash=data["key_hash"],
            access_level=AccessLevel(data["access_level"]),
            protected_paths=data.get("protected_paths", []),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            use_count=data.get("use_count", 0),
        )


@dataclass
class AccessAttempt:
    """Record of an access attempt."""
    timestamp: datetime
    key_id: str
    path: str
    action: str
    result: AuthResult
    ip_address: str = "local"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "key_id": self.key_id,
            "path": self.path,
            "action": self.action,
            "result": self.result.value,
            "ip_address": self.ip_address,
        }


class VectorKeyAuth:
    """
    Vector Key Authentication System.
    
    Manages secure access to protected directories using vector keys
    stored in .env files.
    """
    
    ENV_KEY_PREFIX = "AGNOSTIC_CORE_"
    MASTER_KEY_VAR = "AGNOSTIC_CORE_MASTER_KEY"
    
    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.env_file = self.project_path / ".env"
        self._keys: Dict[str, VectorKey] = {}
        self._locked_paths: Set[str] = set()
        self._access_log: List[AccessAttempt] = []
        self._initialized = False
        self._master_key_hash: Optional[str] = None
        
        # Core protected paths (cannot be edited externally)
        self._core_protected = [
            "Agnostic_Core_OS/core/vector_auth.py",
            "Agnostic_Core_OS/core/core_lock.py",
            "Agnostic_Core_OS/procedural/notation_library.py",
        ]
        
        self._load_env()
    
    def _load_env(self) -> None:
        """Load keys from .env file."""
        if self.env_file.exists():
            with open(self.env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key] = value
                        
                        if key == self.MASTER_KEY_VAR:
                            self._master_key_hash = value
                            self._initialized = True
    
    def _save_env(self) -> None:
        """Save keys to .env file."""
        lines = []
        
        # Add header
        lines.append("# Agnostic_Core_OS Vector Key Authentication")
        lines.append(f"# Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Add master key
        if self._master_key_hash:
            lines.append(f"{self.MASTER_KEY_VAR}={self._master_key_hash}")
            lines.append("")
        
        # Add other keys
        for key_id, vkey in self._keys.items():
            lines.append(f"{self.ENV_KEY_PREFIX}{key_id}={vkey.key_hash}")
        
        with open(self.env_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _hash_key(self, raw_key: str) -> str:
        """Hash a raw key for secure storage."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def _generate_key(self) -> str:
        """Generate a new secure key."""
        return secrets.token_urlsafe(32)

    def initialize(self) -> str:
        """
        Initialize the authentication system with a master key.

        Returns:
            The raw master key (save this securely!)
        """
        if self._initialized:
            raise RuntimeError("Authentication system already initialized")

        master_key = self._generate_key()
        self._master_key_hash = self._hash_key(master_key)
        self._initialized = True
        self._save_env()

        return master_key

    def authenticate(self, raw_key: str) -> AuthResult:
        """Authenticate with a key."""
        if not self._initialized:
            return AuthResult.NOT_INITIALIZED

        key_hash = self._hash_key(raw_key)

        # Check master key
        if key_hash == self._master_key_hash:
            return AuthResult.SUCCESS

        # Check registered keys
        for vkey in self._keys.values():
            if vkey.key_hash == key_hash:
                # Check expiration
                if vkey.expires_at and datetime.now() > vkey.expires_at:
                    return AuthResult.EXPIRED_KEY

                vkey.last_used = datetime.now()
                vkey.use_count += 1
                return AuthResult.SUCCESS

        return AuthResult.INVALID_KEY

    def create_key(
        self,
        master_key: str,
        access_level: AccessLevel = AccessLevel.READ,
        protected_paths: List[str] = None,
        expires_days: int = None,
    ) -> Optional[str]:
        """
        Create a new vector key.

        Args:
            master_key: The master key for authorization
            access_level: Permission level for the new key
            protected_paths: Paths this key can access
            expires_days: Days until key expires (None = never)

        Returns:
            The raw key (save this!) or None if unauthorized
        """
        if self.authenticate(master_key) != AuthResult.SUCCESS:
            return None

        raw_key = self._generate_key()
        key_id = hashlib.sha256(raw_key.encode()).hexdigest()[:12]

        expires_at = None
        if expires_days:
            from datetime import timedelta
            expires_at = datetime.now() + timedelta(days=expires_days)

        vkey = VectorKey(
            id=key_id,
            key_hash=self._hash_key(raw_key),
            access_level=access_level,
            protected_paths=protected_paths or [],
            expires_at=expires_at,
        )

        self._keys[key_id] = vkey
        self._save_env()

        return raw_key

    def revoke_key(self, master_key: str, key_id: str) -> bool:
        """Revoke a vector key."""
        if self.authenticate(master_key) != AuthResult.SUCCESS:
            return False

        if key_id in self._keys:
            del self._keys[key_id]
            self._save_env()
            return True
        return False

    def check_access(
        self,
        raw_key: str,
        path: str,
        action: str = "read",
    ) -> AuthResult:
        """
        Check if a key has access to a path.

        Args:
            raw_key: The authentication key
            path: Path to check access for
            action: Action type (read, write, execute)

        Returns:
            AuthResult indicating access status
        """
        # Log the attempt
        attempt = AccessAttempt(
            timestamp=datetime.now(),
            key_id=self._hash_key(raw_key)[:12],
            path=path,
            action=action,
            result=AuthResult.SUCCESS,  # Will be updated
        )

        # Check if path is core protected
        for protected in self._core_protected:
            if path.startswith(protected) and action == "write":
                attempt.result = AuthResult.LOCKED_RESOURCE
                self._access_log.append(attempt)
                return AuthResult.LOCKED_RESOURCE

        # Check if path is locked
        if path in self._locked_paths and action == "write":
            attempt.result = AuthResult.LOCKED_RESOURCE
            self._access_log.append(attempt)
            return AuthResult.LOCKED_RESOURCE

        # Authenticate
        auth_result = self.authenticate(raw_key)
        if auth_result != AuthResult.SUCCESS:
            attempt.result = auth_result
            self._access_log.append(attempt)
            return auth_result

        # Check master key (full access)
        if self._hash_key(raw_key) == self._master_key_hash:
            self._access_log.append(attempt)
            return AuthResult.SUCCESS

        # Check specific key permissions
        key_hash = self._hash_key(raw_key)
        for vkey in self._keys.values():
            if vkey.key_hash == key_hash:
                # Check access level
                required_level = {
                    "read": [AccessLevel.READ, AccessLevel.WRITE, AccessLevel.EXECUTE, AccessLevel.ADMIN],
                    "write": [AccessLevel.WRITE, AccessLevel.EXECUTE, AccessLevel.ADMIN],
                    "execute": [AccessLevel.EXECUTE, AccessLevel.ADMIN],
                    "admin": [AccessLevel.ADMIN],
                }

                if vkey.access_level not in required_level.get(action, []):
                    attempt.result = AuthResult.INSUFFICIENT_PERMISSION
                    self._access_log.append(attempt)
                    return AuthResult.INSUFFICIENT_PERMISSION

                # Check path restrictions
                if vkey.protected_paths:
                    path_allowed = any(path.startswith(p) for p in vkey.protected_paths)
                    if not path_allowed:
                        attempt.result = AuthResult.INSUFFICIENT_PERMISSION
                        self._access_log.append(attempt)
                        return AuthResult.INSUFFICIENT_PERMISSION

                self._access_log.append(attempt)
                return AuthResult.SUCCESS

        attempt.result = AuthResult.INVALID_KEY
        self._access_log.append(attempt)
        return AuthResult.INVALID_KEY

    def lock_path(self, master_key: str, path: str) -> bool:
        """Lock a path from external write access."""
        if self.authenticate(master_key) != AuthResult.SUCCESS:
            return False
        self._locked_paths.add(path)
        return True

    def unlock_path(self, master_key: str, path: str) -> bool:
        """Unlock a path for write access."""
        if self.authenticate(master_key) != AuthResult.SUCCESS:
            return False
        self._locked_paths.discard(path)
        return True

    def get_access_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent access attempts."""
        return [a.to_dict() for a in self._access_log[-limit:]]

    def is_initialized(self) -> bool:
        """Check if auth system is initialized."""
        return self._initialized

    def list_keys(self, master_key: str) -> Optional[List[Dict[str, Any]]]:
        """List all registered keys (requires master key)."""
        if self.authenticate(master_key) != AuthResult.SUCCESS:
            return None
        return [vkey.to_dict() for vkey in self._keys.values()]


# Singleton accessor
_auth_instance: Optional[VectorKeyAuth] = None


def get_vector_auth(project_path: Path = None) -> VectorKeyAuth:
    """Get or create VectorKeyAuth singleton."""
    global _auth_instance
    if _auth_instance is None:
        if project_path is None:
            project_path = Path.cwd()
        _auth_instance = VectorKeyAuth(project_path)
    return _auth_instance

