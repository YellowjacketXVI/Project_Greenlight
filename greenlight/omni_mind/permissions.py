"""
Greenlight Permission Tiers System

Three-tier permissions system for data sharing and developer communication.
Controls log sharing, data contribution, and update access.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from enum import Enum
import json
import hashlib
import secrets

from greenlight.core.logging_config import get_logger
from greenlight.utils.file_utils import read_json, write_json, ensure_directory

logger = get_logger("omni_mind.permissions")


class PermissionTier(Enum):
    """
    Permission tiers for data sharing.
    
    FULL: Full permissions - all data shared for training
    MODERATE: Moderate permissions - anonymized data, flagged requests only
    MINIMAL: Minimal - only critical updates, no data sharing
    """
    FULL = "full"
    MODERATE = "moderate"
    MINIMAL = "minimal"


class LogShareLevel(Enum):
    """Levels of log sharing with developer."""
    NONE = "none"              # No logs shared
    CRITICAL_ONLY = "critical" # Only critical errors
    ERRORS = "errors"          # All errors
    WARNINGS = "warnings"      # Warnings and above
    ALL = "all"                # All logs


class UpdateChannel(Enum):
    """Update channels for receiving updates."""
    STABLE = "stable"          # Stable releases only
    BETA = "beta"              # Beta releases
    COMMUNITY = "community"    # Community model branch
    DEVELOPER = "developer"    # Developer builds


@dataclass
class PermissionSettings:
    """User permission settings."""
    tier: PermissionTier = PermissionTier.MODERATE
    log_share_level: LogShareLevel = LogShareLevel.CRITICAL_ONLY
    update_channel: UpdateChannel = UpdateChannel.STABLE
    
    # Data sharing options
    share_usage_stats: bool = False
    share_error_logs: bool = True
    share_anonymized_data: bool = False
    contribute_to_training: bool = False
    
    # Update options
    auto_update: bool = False
    require_password_for_updates: bool = True
    community_branch_password: str = ""  # Hashed
    
    # Developer communication
    allow_developer_notes: bool = True
    send_flagged_requests: bool = True
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "log_share_level": self.log_share_level.value,
            "update_channel": self.update_channel.value,
            "share_usage_stats": self.share_usage_stats,
            "share_error_logs": self.share_error_logs,
            "share_anonymized_data": self.share_anonymized_data,
            "contribute_to_training": self.contribute_to_training,
            "auto_update": self.auto_update,
            "require_password_for_updates": self.require_password_for_updates,
            "community_branch_password": self.community_branch_password,
            "allow_developer_notes": self.allow_developer_notes,
            "send_flagged_requests": self.send_flagged_requests,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PermissionSettings":
        return cls(
            tier=PermissionTier(data.get("tier", "moderate")),
            log_share_level=LogShareLevel(data.get("log_share_level", "critical")),
            update_channel=UpdateChannel(data.get("update_channel", "stable")),
            share_usage_stats=data.get("share_usage_stats", False),
            share_error_logs=data.get("share_error_logs", True),
            share_anonymized_data=data.get("share_anonymized_data", False),
            contribute_to_training=data.get("contribute_to_training", False),
            auto_update=data.get("auto_update", False),
            require_password_for_updates=data.get("require_password_for_updates", True),
            community_branch_password=data.get("community_branch_password", ""),
            allow_developer_notes=data.get("allow_developer_notes", True),
            send_flagged_requests=data.get("send_flagged_requests", True),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat()))
        )


@dataclass
class FlaggedRequest:
    """A flagged request for developer review."""
    id: str
    timestamp: datetime
    request_type: str
    content: str
    reason: str
    severity: str
    user_note: str = ""
    developer_response: str = ""
    status: str = "pending"  # pending, reviewed, resolved
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "request_type": self.request_type,
            "content": self.content,
            "reason": self.reason,
            "severity": self.severity,
            "user_note": self.user_note,
            "developer_response": self.developer_response,
            "status": self.status
        }


@dataclass
class PermissionLogEntry:
    """Log entry for permission-related actions."""
    id: str
    timestamp: datetime
    action: str
    details: str
    tier_at_time: PermissionTier
    shared: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "details": self.details,
            "tier_at_time": self.tier_at_time.value,
            "shared": self.shared
        }


class PermissionManager:
    """
    Manages user permissions, flagged requests, and developer communication.

    Features:
    - Three-tier permission system
    - Log sharing controls
    - Flagged request handling
    - Password-protected updates
    - Permission audit log
    """

    def __init__(self, project_path: Path = None):
        """
        Initialize permission manager.

        Args:
            project_path: Project root path
        """
        self.project_path = project_path
        self.settings = PermissionSettings()
        self._flagged_requests: Dict[str, FlaggedRequest] = {}
        self._permission_log: List[PermissionLogEntry] = []
        self._next_id = 0

        # Setup storage
        if project_path:
            self.perm_dir = project_path / ".permissions"
            ensure_directory(self.perm_dir)
            self.settings_file = self.perm_dir / "settings.json"
            self.flags_file = self.perm_dir / "flagged_requests.json"
            self.log_file = self.perm_dir / "permission_log.json"
            self._load_from_disk()
        else:
            self.perm_dir = None

    def _generate_id(self, prefix: str = "perm") -> str:
        """Generate unique ID."""
        self._next_id += 1
        return f"{prefix}_{self._next_id:06d}"

    def _hash_password(self, password: str) -> str:
        """Hash a password."""
        return hashlib.sha256(password.encode()).hexdigest()

    def _load_from_disk(self) -> None:
        """Load settings from disk."""
        try:
            if self.settings_file and self.settings_file.exists():
                data = read_json(self.settings_file)
                self.settings = PermissionSettings.from_dict(data)

            if self.flags_file and self.flags_file.exists():
                data = read_json(self.flags_file)
                for flag_data in data.get("requests", []):
                    flag = FlaggedRequest(
                        id=flag_data["id"],
                        timestamp=datetime.fromisoformat(flag_data["timestamp"]),
                        request_type=flag_data["request_type"],
                        content=flag_data["content"],
                        reason=flag_data["reason"],
                        severity=flag_data["severity"],
                        user_note=flag_data.get("user_note", ""),
                        developer_response=flag_data.get("developer_response", ""),
                        status=flag_data.get("status", "pending")
                    )
                    self._flagged_requests[flag.id] = flag
                self._next_id = data.get("next_id", len(self._flagged_requests))

            logger.info("Loaded permission settings from disk")
        except Exception as e:
            logger.error(f"Failed to load permissions: {e}")

    def _save_to_disk(self) -> None:
        """Save settings to disk."""
        try:
            if self.settings_file:
                write_json(self.settings_file, self.settings.to_dict())

            if self.flags_file:
                data = {
                    "next_id": self._next_id,
                    "requests": [f.to_dict() for f in self._flagged_requests.values()]
                }
                write_json(self.flags_file, data)
        except Exception as e:
            logger.error(f"Failed to save permissions: {e}")

    def _log_action(self, action: str, details: str) -> None:
        """Log a permission action."""
        entry = PermissionLogEntry(
            id=self._generate_id("log"),
            timestamp=datetime.now(),
            action=action,
            details=details,
            tier_at_time=self.settings.tier
        )
        self._permission_log.append(entry)

    # =========================================================================
    # TIER MANAGEMENT
    # =========================================================================

    def set_tier(self, tier: PermissionTier) -> None:
        """Set the permission tier."""
        old_tier = self.settings.tier
        self.settings.tier = tier
        self.settings.updated_at = datetime.now()

        # Apply tier defaults
        if tier == PermissionTier.FULL:
            self.settings.share_usage_stats = True
            self.settings.share_error_logs = True
            self.settings.share_anonymized_data = True
            self.settings.contribute_to_training = True
            self.settings.log_share_level = LogShareLevel.ALL
        elif tier == PermissionTier.MODERATE:
            self.settings.share_usage_stats = False
            self.settings.share_error_logs = True
            self.settings.share_anonymized_data = True
            self.settings.contribute_to_training = False
            self.settings.log_share_level = LogShareLevel.ERRORS
        else:  # MINIMAL
            self.settings.share_usage_stats = False
            self.settings.share_error_logs = False
            self.settings.share_anonymized_data = False
            self.settings.contribute_to_training = False
            self.settings.log_share_level = LogShareLevel.CRITICAL_ONLY

        self._log_action("tier_change", f"{old_tier.value} -> {tier.value}")
        self._save_to_disk()
        logger.info(f"Permission tier changed to: {tier.value}")

    def get_tier(self) -> PermissionTier:
        """Get current permission tier."""
        return self.settings.tier

    # =========================================================================
    # UPDATE CHANNEL & PASSWORD
    # =========================================================================

    def set_update_channel(self, channel: UpdateChannel, password: str = None) -> bool:
        """
        Set update channel.

        Args:
            channel: Update channel
            password: Required for community/developer channels

        Returns:
            True if successful
        """
        if channel in [UpdateChannel.COMMUNITY, UpdateChannel.DEVELOPER]:
            if not password:
                logger.warning("Password required for community/developer channel")
                return False
            # Verify password (in real implementation, check against stored hash)
            self.settings.community_branch_password = self._hash_password(password)

        self.settings.update_channel = channel
        self.settings.updated_at = datetime.now()
        self._log_action("channel_change", f"Changed to {channel.value}")
        self._save_to_disk()
        return True

    def verify_update_password(self, password: str) -> bool:
        """Verify update password."""
        return self._hash_password(password) == self.settings.community_branch_password

    # =========================================================================
    # FLAGGED REQUESTS
    # =========================================================================

    def flag_request(
        self,
        request_type: str,
        content: str,
        reason: str,
        severity: str = "INFO",
        user_note: str = ""
    ) -> FlaggedRequest:
        """
        Flag a request for developer review.

        Args:
            request_type: Type of request
            content: Request content
            reason: Reason for flagging
            severity: Severity level
            user_note: Optional user note

        Returns:
            Created FlaggedRequest
        """
        if not self.settings.send_flagged_requests:
            logger.info("Flagged requests disabled, not sending")
            return None

        flag = FlaggedRequest(
            id=self._generate_id("flag"),
            timestamp=datetime.now(),
            request_type=request_type,
            content=content[:1000],  # Limit content size
            reason=reason,
            severity=severity,
            user_note=user_note
        )

        self._flagged_requests[flag.id] = flag
        self._log_action("flag_request", f"Flagged: {request_type} - {reason}")
        self._save_to_disk()

        logger.info(f"Request flagged: {flag.id}")
        return flag

    def get_pending_flags(self) -> List[FlaggedRequest]:
        """Get all pending flagged requests."""
        return [f for f in self._flagged_requests.values() if f.status == "pending"]

    def resolve_flag(self, flag_id: str, response: str = "") -> bool:
        """Resolve a flagged request."""
        if flag_id in self._flagged_requests:
            flag = self._flagged_requests[flag_id]
            flag.status = "resolved"
            flag.developer_response = response
            self._save_to_disk()
            return True
        return False

    # =========================================================================
    # DATA SHARING CHECKS
    # =========================================================================

    def can_share_log(self, level: str) -> bool:
        """Check if a log at given level can be shared."""
        level_order = ["none", "critical", "errors", "warnings", "all"]
        current_idx = level_order.index(self.settings.log_share_level.value)

        level_map = {
            "CRITICAL": 1,
            "ERROR": 2,
            "WARNING": 3,
            "INFO": 4,
            "DEBUG": 4
        }

        required_idx = level_map.get(level.upper(), 4)
        return current_idx >= required_idx

    def can_contribute_data(self) -> bool:
        """Check if user has opted to contribute data."""
        return self.settings.contribute_to_training

    def get_shareable_data_summary(self) -> Dict[str, bool]:
        """Get summary of what data can be shared."""
        return {
            "usage_stats": self.settings.share_usage_stats,
            "error_logs": self.settings.share_error_logs,
            "anonymized_data": self.settings.share_anonymized_data,
            "training_contribution": self.settings.contribute_to_training
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get permission manager statistics."""
        return {
            "tier": self.settings.tier.value,
            "log_share_level": self.settings.log_share_level.value,
            "update_channel": self.settings.update_channel.value,
            "pending_flags": len(self.get_pending_flags()),
            "total_flags": len(self._flagged_requests),
            "log_entries": len(self._permission_log),
            "shareable_data": self.get_shareable_data_summary()
        }

