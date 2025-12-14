"""
Greenlight Git Community Model Integration

Handles community model branch for permissions pushes and password-protected updates.
Manages data contribution and training data collection with user consent.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from enum import Enum
import json
import hashlib

from greenlight.core.logging_config import get_logger
from greenlight.utils.file_utils import read_json, write_json, ensure_directory

logger = get_logger("omni_mind.community_model")


class ContributionType(Enum):
    """Types of data contributions."""
    USAGE_STATS = "usage_stats"
    ERROR_LOGS = "error_logs"
    ANONYMIZED_DATA = "anonymized_data"
    TRAINING_DATA = "training_data"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"


class ContributionStatus(Enum):
    """Status of a contribution."""
    PENDING = "pending"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    REJECTED = "rejected"


@dataclass
class DataContribution:
    """A data contribution to the community model."""
    id: str
    contribution_type: ContributionType
    status: ContributionStatus
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    
    # Data
    data_hash: str = ""  # Hash of contributed data
    data_size_bytes: int = 0
    anonymized: bool = True
    
    # Consent
    user_consent: bool = False
    consent_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "contribution_type": self.contribution_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "data_hash": self.data_hash,
            "data_size_bytes": self.data_size_bytes,
            "anonymized": self.anonymized,
            "user_consent": self.user_consent,
            "consent_timestamp": self.consent_timestamp.isoformat() if self.consent_timestamp else None
        }


@dataclass
class UpdateInfo:
    """Information about an available update."""
    version: str
    channel: str
    release_date: datetime
    description: str
    is_critical: bool = False
    requires_password: bool = False
    download_url: str = ""
    checksum: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "channel": self.channel,
            "release_date": self.release_date.isoformat(),
            "description": self.description,
            "is_critical": self.is_critical,
            "requires_password": self.requires_password,
            "download_url": self.download_url,
            "checksum": self.checksum
        }


class CommunityModelManager:
    """
    Manages community model integration.
    
    Features:
    - Data contribution with consent
    - Password-protected updates
    - Community branch management
    - Training data collection
    - Backup to developer
    """
    
    COMMUNITY_BRANCH = "community-model"
    
    def __init__(
        self,
        project_path: Path = None,
        permission_manager: Any = None
    ):
        """
        Initialize community model manager.
        
        Args:
            project_path: Project root path
            permission_manager: PermissionManager for consent
        """
        self.project_path = project_path
        self.permission_manager = permission_manager
        
        self._contributions: Dict[str, DataContribution] = {}
        self._pending_updates: List[UpdateInfo] = []
        self._next_id = 0
        self._update_password_hash: str = ""
        
        # Setup storage
        if project_path:
            self.community_dir = project_path / ".community"
            ensure_directory(self.community_dir)
            self.contributions_file = self.community_dir / "contributions.json"
            self.config_file = self.community_dir / "config.json"
            self._load_from_disk()
        else:
            self.community_dir = None
    
    def _generate_id(self) -> str:
        """Generate unique contribution ID."""
        self._next_id += 1
        return f"contrib_{self._next_id:06d}"
    
    def _hash_data(self, data: str) -> str:
        """Hash data for verification."""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _load_from_disk(self) -> None:
        """Load contributions from disk."""
        try:
            if self.contributions_file and self.contributions_file.exists():
                data = read_json(self.contributions_file)
                self._next_id = data.get("next_id", 0)
            if self.config_file and self.config_file.exists():
                config = read_json(self.config_file)
                self._update_password_hash = config.get("update_password_hash", "")
        except Exception as e:
            logger.error(f"Failed to load community data: {e}")

    def _save_to_disk(self) -> None:
        """Save contributions to disk."""
        try:
            if self.contributions_file:
                data = {
                    "next_id": self._next_id,
                    "contributions": [c.to_dict() for c in self._contributions.values()]
                }
                write_json(self.contributions_file, data)
        except Exception as e:
            logger.error(f"Failed to save contributions: {e}")

    def _save_config(self) -> None:
        """Save config to disk."""
        try:
            if self.config_file:
                config = {
                    "update_password_hash": self._update_password_hash
                }
                write_json(self.config_file, config)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def _check_consent(self) -> bool:
        """Check if user has given consent for data contribution."""
        if self.permission_manager:
            from .permissions import PermissionTier
            tier = self.permission_manager.get_tier()
            return tier in [PermissionTier.FULL, PermissionTier.MODERATE]
        return False

    # =========================================================================
    # PASSWORD MANAGEMENT
    # =========================================================================

    def set_update_password(self, password: str) -> bool:
        """Set password for protected updates."""
        self._update_password_hash = self._hash_data(password)
        self._save_config()
        logger.info("Update password set")
        return True

    def verify_update_password(self, password: str) -> bool:
        """Verify update password."""
        if not self._update_password_hash:
            return True  # No password set
        return self._hash_data(password) == self._update_password_hash

    # =========================================================================
    # DATA CONTRIBUTION
    # =========================================================================

    def create_contribution(
        self,
        contribution_type: ContributionType,
        data: str,
        anonymize: bool = True
    ) -> Optional[DataContribution]:
        """
        Create a data contribution.

        Args:
            contribution_type: Type of contribution
            data: Data to contribute
            anonymize: Whether to anonymize data

        Returns:
            DataContribution or None if no consent
        """
        if not self._check_consent():
            logger.warning("Cannot create contribution: no consent")
            return None

        contribution = DataContribution(
            id=self._generate_id(),
            contribution_type=contribution_type,
            status=ContributionStatus.PENDING,
            data_hash=self._hash_data(data),
            data_size_bytes=len(data.encode()),
            anonymized=anonymize,
            user_consent=True,
            consent_timestamp=datetime.now()
        )

        self._contributions[contribution.id] = contribution
        self._save_to_disk()

        logger.info(f"Created contribution: {contribution.id}")
        return contribution

    def approve_contribution(self, contribution_id: str) -> Optional[DataContribution]:
        """Approve a contribution for submission."""
        contribution = self._contributions.get(contribution_id)
        if contribution and contribution.status == ContributionStatus.PENDING:
            contribution.status = ContributionStatus.APPROVED
            self._save_to_disk()
        return contribution

    def submit_contribution(self, contribution_id: str) -> Optional[DataContribution]:
        """Submit an approved contribution."""
        contribution = self._contributions.get(contribution_id)
        if contribution and contribution.status == ContributionStatus.APPROVED:
            contribution.status = ContributionStatus.SUBMITTED
            contribution.submitted_at = datetime.now()
            self._save_to_disk()
            logger.info(f"Submitted contribution: {contribution_id}")
        return contribution

    def get_pending_contributions(self) -> List[DataContribution]:
        """Get all pending contributions."""
        return [c for c in self._contributions.values() if c.status == ContributionStatus.PENDING]

    # =========================================================================
    # UPDATE MANAGEMENT
    # =========================================================================

    def check_for_updates(self, channel: str = "stable") -> List[UpdateInfo]:
        """
        Check for available updates.

        Args:
            channel: Update channel (stable, beta, community, developer)

        Returns:
            List of available updates
        """
        # In a real implementation, this would check a remote server
        # For now, return pending updates
        return [u for u in self._pending_updates if u.channel == channel]

    def apply_update(self, update: UpdateInfo, password: str = None) -> bool:
        """
        Apply an update.

        Args:
            update: Update to apply
            password: Password if required

        Returns:
            True if successful
        """
        if update.requires_password:
            if not password or not self.verify_update_password(password):
                logger.warning("Update requires valid password")
                return False

        # In a real implementation, this would download and apply the update
        logger.info(f"Applied update: {update.version}")
        return True

    # =========================================================================
    # TRAINING DATA
    # =========================================================================

    def contribute_training_data(
        self,
        data_type: str,
        data: Dict[str, Any]
    ) -> Optional[DataContribution]:
        """
        Contribute training data with full consent.

        Args:
            data_type: Type of training data
            data: Training data

        Returns:
            DataContribution or None
        """
        if self.permission_manager:
            from .permissions import PermissionTier
            if self.permission_manager.get_tier() != PermissionTier.FULL:
                logger.warning("Training data contribution requires FULL permissions")
                return None

        return self.create_contribution(
            contribution_type=ContributionType.TRAINING_DATA,
            data=json.dumps({"type": data_type, "data": data}),
            anonymize=False  # Training data may need full context
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get community model statistics."""
        by_type = {}
        by_status = {}

        for c in self._contributions.values():
            ct = c.contribution_type.value
            by_type[ct] = by_type.get(ct, 0) + 1
            st = c.status.value
            by_status[st] = by_status.get(st, 0) + 1

        return {
            "total_contributions": len(self._contributions),
            "pending": len(self.get_pending_contributions()),
            "by_type": by_type,
            "by_status": by_status,
            "has_update_password": bool(self._update_password_hash)
        }

