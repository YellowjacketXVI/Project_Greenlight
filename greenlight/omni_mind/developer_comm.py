"""
Greenlight Developer Communication System

Handles flagged request analysis, user notes to developer, and permissions logging.
Provides secure communication channel between users and core developers.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from enum import Enum
import json

from greenlight.core.logging_config import get_logger
from greenlight.utils.file_utils import read_json, write_json, ensure_directory

logger = get_logger("omni_mind.developer_comm")


class NoteType(Enum):
    """Types of developer notes."""
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    FEEDBACK = "feedback"
    QUESTION = "question"
    SECURITY = "security"
    PERFORMANCE = "performance"


class NoteStatus(Enum):
    """Status of a developer note."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class NotePriority(Enum):
    """Priority of developer notes."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class DeveloperNote:
    """A note/message to the developer."""
    id: str
    note_type: NoteType
    priority: NotePriority
    subject: str
    content: str
    status: NoteStatus = NoteStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    
    # User info (anonymized if moderate permissions)
    user_id: str = "anonymous"
    include_logs: bool = False
    include_context: bool = False
    
    # Attachments
    attached_logs: List[str] = field(default_factory=list)
    attached_files: List[str] = field(default_factory=list)
    
    # Response
    developer_response: str = ""
    response_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "note_type": self.note_type.value,
            "priority": self.priority.value,
            "subject": self.subject,
            "content": self.content,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "user_id": self.user_id,
            "include_logs": self.include_logs,
            "include_context": self.include_context,
            "attached_logs": self.attached_logs,
            "attached_files": self.attached_files,
            "developer_response": self.developer_response,
            "response_at": self.response_at.isoformat() if self.response_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeveloperNote":
        return cls(
            id=data["id"],
            note_type=NoteType(data["note_type"]),
            priority=NotePriority(data["priority"]),
            subject=data["subject"],
            content=data["content"],
            status=NoteStatus(data.get("status", "draft")),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
            submitted_at=datetime.fromisoformat(data["submitted_at"]) if data.get("submitted_at") else None,
            user_id=data.get("user_id", "anonymous"),
            include_logs=data.get("include_logs", False),
            include_context=data.get("include_context", False),
            attached_logs=data.get("attached_logs", []),
            attached_files=data.get("attached_files", []),
            developer_response=data.get("developer_response", ""),
            response_at=datetime.fromisoformat(data["response_at"]) if data.get("response_at") else None
        )


@dataclass
class FlagAnalysis:
    """Analysis of a flagged request."""
    id: str
    flag_id: str
    timestamp: datetime
    analysis_type: str
    findings: str
    severity_assessment: str
    recommended_action: str
    auto_resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "flag_id": self.flag_id,
            "timestamp": self.timestamp.isoformat(),
            "analysis_type": self.analysis_type,
            "findings": self.findings,
            "severity_assessment": self.severity_assessment,
            "recommended_action": self.recommended_action,
            "auto_resolved": self.auto_resolved
        }


class DeveloperCommunication:
    """
    Developer communication system for OmniMind.
    
    Features:
    - Create and submit notes to developer
    - Analyze flagged requests
    - Permission-aware log sharing
    - Secure communication channel
    """
    
    def __init__(
        self,
        project_path: Path = None,
        permission_manager: Any = None
    ):
        """
        Initialize developer communication.
        
        Args:
            project_path: Project root path
            permission_manager: PermissionManager for access control
        """
        self.project_path = project_path
        self.permission_manager = permission_manager
        
        self._notes: Dict[str, DeveloperNote] = {}
        self._analyses: Dict[str, FlagAnalysis] = {}
        self._next_id = 0

        # Setup storage
        if project_path:
            self.comm_dir = project_path / ".developer"
            ensure_directory(self.comm_dir)
            self.notes_file = self.comm_dir / "notes.json"
            self.analyses_file = self.comm_dir / "analyses.json"
            self._load_from_disk()
        else:
            self.comm_dir = None

    def _generate_id(self, prefix: str = "note") -> str:
        """Generate unique ID."""
        self._next_id += 1
        return f"{prefix}_{self._next_id:06d}"

    def _load_from_disk(self) -> None:
        """Load notes from disk."""
        try:
            if self.notes_file and self.notes_file.exists():
                data = read_json(self.notes_file)
                for note_data in data.get("notes", []):
                    note = DeveloperNote.from_dict(note_data)
                    self._notes[note.id] = note
                self._next_id = data.get("next_id", len(self._notes))
        except Exception as e:
            logger.error(f"Failed to load notes: {e}")

    def _save_to_disk(self) -> None:
        """Save notes to disk."""
        try:
            if self.notes_file:
                data = {
                    "next_id": self._next_id,
                    "notes": [n.to_dict() for n in self._notes.values()]
                }
                write_json(self.notes_file, data)
        except Exception as e:
            logger.error(f"Failed to save notes: {e}")

    def _can_include_logs(self) -> bool:
        """Check if logs can be included based on permissions."""
        if self.permission_manager:
            from .permissions import PermissionTier
            tier = self.permission_manager.get_tier()
            return tier in [PermissionTier.FULL, PermissionTier.MODERATE]
        return False

    # =========================================================================
    # NOTE MANAGEMENT
    # =========================================================================

    def create_note(
        self,
        note_type: NoteType,
        subject: str,
        content: str,
        priority: NotePriority = NotePriority.MEDIUM,
        include_logs: bool = False,
        include_context: bool = False
    ) -> DeveloperNote:
        """
        Create a new developer note.

        Args:
            note_type: Type of note
            subject: Note subject
            content: Note content
            priority: Priority level
            include_logs: Whether to include logs
            include_context: Whether to include context

        Returns:
            Created DeveloperNote
        """
        # Check permissions for log inclusion
        if include_logs and not self._can_include_logs():
            include_logs = False
            logger.warning("Log inclusion disabled due to permission settings")

        note = DeveloperNote(
            id=self._generate_id("note"),
            note_type=note_type,
            priority=priority,
            subject=subject,
            content=content,
            include_logs=include_logs,
            include_context=include_context
        )

        self._notes[note.id] = note
        self._save_to_disk()

        logger.info(f"Created developer note: {note.id}")
        return note

    def submit_note(self, note_id: str) -> Optional[DeveloperNote]:
        """Submit a note to developer."""
        note = self._notes.get(note_id)
        if note and note.status == NoteStatus.DRAFT:
            note.status = NoteStatus.SUBMITTED
            note.submitted_at = datetime.now()
            note.updated_at = datetime.now()
            self._save_to_disk()
            logger.info(f"Submitted note: {note_id}")
        return note

    def get_note(self, note_id: str) -> Optional[DeveloperNote]:
        """Get a note by ID."""
        return self._notes.get(note_id)

    def get_submitted_notes(self) -> List[DeveloperNote]:
        """Get all submitted notes."""
        return [n for n in self._notes.values() if n.status == NoteStatus.SUBMITTED]

    def get_notes_by_type(self, note_type: NoteType) -> List[DeveloperNote]:
        """Get notes by type."""
        return [n for n in self._notes.values() if n.note_type == note_type]

    def update_note(self, note_id: str, **updates) -> Optional[DeveloperNote]:
        """Update a note's fields."""
        note = self._notes.get(note_id)
        if note and note.status == NoteStatus.DRAFT:
            for key, value in updates.items():
                if hasattr(note, key):
                    setattr(note, key, value)
            note.updated_at = datetime.now()
            self._save_to_disk()
        return note

    def delete_note(self, note_id: str) -> bool:
        """Delete a draft note."""
        note = self._notes.get(note_id)
        if note and note.status == NoteStatus.DRAFT:
            del self._notes[note_id]
            self._save_to_disk()
            return True
        return False

    # =========================================================================
    # FLAG ANALYSIS
    # =========================================================================

    def analyze_flag(
        self,
        flag_id: str,
        content: str,
        severity: str
    ) -> FlagAnalysis:
        """
        Analyze a flagged request.

        Args:
            flag_id: ID of the flagged request
            content: Content to analyze
            severity: Reported severity

        Returns:
            FlagAnalysis result
        """
        # Simple analysis logic (can be enhanced with AI)
        findings = []
        recommended_action = "review"
        auto_resolved = False

        content_lower = content.lower()

        # Check for common patterns
        if "error" in content_lower or "exception" in content_lower:
            findings.append("Contains error/exception keywords")
            recommended_action = "investigate"

        if "security" in content_lower or "password" in content_lower:
            findings.append("Contains security-related keywords")
            recommended_action = "security_review"

        if "performance" in content_lower or "slow" in content_lower:
            findings.append("Contains performance-related keywords")
            recommended_action = "performance_review"

        if not findings:
            findings.append("No concerning patterns detected")
            auto_resolved = True

        analysis = FlagAnalysis(
            id=self._generate_id("analysis"),
            flag_id=flag_id,
            timestamp=datetime.now(),
            analysis_type="automated",
            findings="; ".join(findings),
            severity_assessment=severity,
            recommended_action=recommended_action,
            auto_resolved=auto_resolved
        )

        self._analyses[analysis.id] = analysis
        logger.info(f"Analyzed flag {flag_id}: {recommended_action}")

        return analysis

    def get_analysis(self, flag_id: str) -> Optional[FlagAnalysis]:
        """Get analysis for a flag."""
        for analysis in self._analyses.values():
            if analysis.flag_id == flag_id:
                return analysis
        return None

    # =========================================================================
    # QUICK ACTIONS
    # =========================================================================

    def report_bug(self, subject: str, description: str) -> DeveloperNote:
        """Quick action to report a bug."""
        return self.create_note(
            note_type=NoteType.BUG_REPORT,
            subject=subject,
            content=description,
            priority=NotePriority.HIGH,
            include_logs=self._can_include_logs()
        )

    def request_feature(self, subject: str, description: str) -> DeveloperNote:
        """Quick action to request a feature."""
        return self.create_note(
            note_type=NoteType.FEATURE_REQUEST,
            subject=subject,
            content=description,
            priority=NotePriority.MEDIUM
        )

    def send_feedback(self, subject: str, content: str) -> DeveloperNote:
        """Quick action to send feedback."""
        return self.create_note(
            note_type=NoteType.FEEDBACK,
            subject=subject,
            content=content,
            priority=NotePriority.LOW
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get communication statistics."""
        by_type = {}
        by_status = {}

        for note in self._notes.values():
            nt = note.note_type.value
            by_type[nt] = by_type.get(nt, 0) + 1
            st = note.status.value
            by_status[st] = by_status.get(st, 0) + 1

        return {
            "total_notes": len(self._notes),
            "submitted": len(self.get_submitted_notes()),
            "analyses": len(self._analyses),
            "by_type": by_type,
            "by_status": by_status
        }

