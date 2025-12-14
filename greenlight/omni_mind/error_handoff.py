"""
Greenlight Error Handoff System

Handles error flagging, code handoff for tasking, and guidance from error transcripts.
Integrates with VectorCache for storage and ProjectHealthLogger for reporting.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path
from enum import Enum
import traceback
import json

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.error_handoff")


class ErrorSeverity(Enum):
    """Error severity levels."""
    CRITICAL = "CRITICAL"  # Blocks execution, requires immediate attention
    ERROR = "ERROR"        # Needs attention, may affect output quality
    WARNING = "WARNING"    # Potential issue, should be reviewed
    INFO = "INFO"          # Informational, for logging purposes


class HandoffStatus(Enum):
    """Status of error handoff."""
    PENDING = "pending"        # Awaiting handoff
    HANDED_OFF = "handed_off"  # Handed to user/agent
    IN_PROGRESS = "in_progress"  # Being addressed
    RESOLVED = "resolved"      # Fixed
    DISMISSED = "dismissed"    # Acknowledged but not fixed


@dataclass
class ErrorTranscript:
    """Structured error transcript for handoff."""
    id: str
    severity: ErrorSeverity
    source: str
    error_type: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    stack_trace: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: List[str] = field(default_factory=list)
    status: HandoffStatus = HandoffStatus.PENDING
    task_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "source": self.source,
            "error_type": self.error_type,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "stack_trace": self.stack_trace,
            "context": self.context,
            "suggested_actions": self.suggested_actions,
            "status": self.status.value,
            "task_id": self.task_id
        }
    
    def to_markdown(self) -> str:
        """Generate markdown representation for display."""
        lines = [
            f"## Error: {self.id}",
            f"",
            f"**Severity:** {self.severity.value}",
            f"**Source:** {self.source}",
            f"**Type:** {self.error_type}",
            f"**Status:** {self.status.value}",
            f"**Time:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"### Message",
            f"```",
            self.message,
            f"```",
            f"",
        ]
        
        if self.context:
            lines.extend([
                "### Context",
                "```json",
                json.dumps(self.context, indent=2, default=str),
                "```",
                "",
            ])
        
        if self.suggested_actions:
            lines.extend([
                "### Suggested Actions",
                "",
            ])
            for i, action in enumerate(self.suggested_actions, 1):
                lines.append(f"{i}. {action}")
            lines.append("")
        
        if self.stack_trace:
            lines.extend([
                "### Stack Trace",
                "```",
                self.stack_trace[:2000],  # Limit stack trace
                "```",
            ])
        
        return "\n".join(lines)


@dataclass
class GuidanceTask:
    """A task created from error handoff for user/agent guidance."""
    id: str
    error_id: str
    title: str
    description: str
    priority: int  # 1=highest, 5=lowest
    created_at: datetime = field(default_factory=datetime.now)
    assigned_to: Optional[str] = None
    status: str = "open"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "error_id": self.error_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "assigned_to": self.assigned_to,
            "status": self.status
        }


class ErrorHandoff:
    """
    Error handoff system for OmniMind.
    
    Flow:
    1. Error Detected → Flag with severity
    2. Generate Error Transcript (structured context)
    3. Cache in Heavy Vector (up to 1MB)
    4. Create Task for Guidance (handoff to user/agent)
    5. Log to Health Report
    """
    
    def __init__(
        self,
        vector_cache: Any = None,
        health_logger: Any = None
    ):
        """
        Initialize error handoff system.
        
        Args:
            vector_cache: VectorCache instance for storing transcripts
            health_logger: ProjectHealthLogger for health reporting
        """
        self.vector_cache = vector_cache
        self.health_logger = health_logger
        self._transcripts: Dict[str, ErrorTranscript] = {}
        self._tasks: Dict[str, GuidanceTask] = {}
        self._next_id = 0
        self._handlers: Dict[str, Callable] = {}

    def _generate_id(self, prefix: str = "err") -> str:
        """Generate unique ID."""
        self._next_id += 1
        return f"{prefix}_{self._next_id:06d}"

    def flag_error(
        self,
        error: Exception,
        severity: ErrorSeverity,
        source: str,
        context: Dict[str, Any] = None,
        suggested_actions: List[str] = None
    ) -> ErrorTranscript:
        """
        Flag an error and create transcript.

        Args:
            error: The exception that occurred
            severity: Error severity level
            source: Where the error originated
            context: Additional context information
            suggested_actions: Suggested fixes

        Returns:
            Created ErrorTranscript
        """
        transcript = ErrorTranscript(
            id=self._generate_id("err"),
            severity=severity,
            source=source,
            error_type=type(error).__name__,
            message=str(error),
            stack_trace=traceback.format_exc(),
            context=context or {},
            suggested_actions=suggested_actions or self._suggest_actions(error, source)
        )

        self._transcripts[transcript.id] = transcript

        # Cache in vector cache if available
        if self.vector_cache:
            from .vector_cache import CacheEntryType
            self.vector_cache.add(
                content=transcript.to_markdown(),
                entry_type=CacheEntryType.ERROR_TRANSCRIPT,
                weight=1.0,
                entry_id=transcript.id,
                severity=severity.value,
                source=source
            )

        # Log to health logger if available
        if self.health_logger:
            self.health_logger.log_error(error, source, context)

        logger.warning(f"Error flagged: {transcript.id} [{severity.value}] {source}: {error}")
        return transcript

    def _suggest_actions(self, error: Exception, source: str) -> List[str]:
        """Generate suggested actions based on error type."""
        suggestions = []
        error_type = type(error).__name__

        if "FileNotFound" in error_type:
            suggestions.append("Check if the file path is correct")
            suggestions.append("Ensure the file exists in the project directory")
        elif "Permission" in error_type:
            suggestions.append("Check file permissions")
            suggestions.append("Run with appropriate privileges")
        elif "JSON" in error_type or "Decode" in error_type:
            suggestions.append("Validate JSON syntax")
            suggestions.append("Check for encoding issues")
        elif "Connection" in error_type or "Timeout" in error_type:
            suggestions.append("Check network connectivity")
            suggestions.append("Verify API endpoint is accessible")
        elif "API" in error_type or "Rate" in error_type:
            suggestions.append("Check API key configuration")
            suggestions.append("Wait and retry if rate limited")
        else:
            suggestions.append("Review the error message and stack trace")
            suggestions.append("Check the source code at the error location")

        suggestions.append(f"Run diagnostics: >diagnose {source}")
        return suggestions

    def create_task(self, transcript: ErrorTranscript) -> GuidanceTask:
        """
        Create a guidance task from an error transcript.

        Args:
            transcript: The error transcript

        Returns:
            Created GuidanceTask
        """
        # Determine priority from severity
        priority_map = {
            ErrorSeverity.CRITICAL: 1,
            ErrorSeverity.ERROR: 2,
            ErrorSeverity.WARNING: 3,
            ErrorSeverity.INFO: 4
        }

        task = GuidanceTask(
            id=self._generate_id("task"),
            error_id=transcript.id,
            title=f"[{transcript.severity.value}] {transcript.error_type} in {transcript.source}",
            description=self._generate_task_description(transcript),
            priority=priority_map.get(transcript.severity, 3)
        )

        self._tasks[task.id] = task
        transcript.task_id = task.id
        transcript.status = HandoffStatus.HANDED_OFF

        logger.info(f"Created guidance task: {task.id} for error {transcript.id}")
        return task

    def _generate_task_description(self, transcript: ErrorTranscript) -> str:
        """Generate task description from transcript."""
        lines = [
            f"Error occurred in {transcript.source}:",
            f"",
            f"**Message:** {transcript.message}",
            f"",
            "**Suggested Actions:**",
        ]
        for action in transcript.suggested_actions:
            lines.append(f"- {action}")

        if transcript.context:
            lines.extend([
                "",
                "**Context:**",
                f"```json",
                json.dumps(transcript.context, indent=2, default=str)[:500],
                "```"
            ])

        return "\n".join(lines)

    def handoff_for_guidance(
        self,
        error: Exception,
        severity: ErrorSeverity,
        source: str,
        context: Dict[str, Any] = None,
        auto_create_task: bool = True
    ) -> Dict[str, Any]:
        """
        Complete error handoff flow: flag → cache → task → log.

        Args:
            error: The exception
            severity: Severity level
            source: Error source
            context: Additional context
            auto_create_task: Whether to auto-create guidance task

        Returns:
            Dict with transcript and optional task
        """
        # Step 1: Flag and create transcript
        transcript = self.flag_error(error, severity, source, context)

        result = {
            "transcript": transcript,
            "transcript_id": transcript.id,
            "cached": self.vector_cache is not None,
            "logged": self.health_logger is not None
        }

        # Step 2: Create task if requested
        if auto_create_task:
            task = self.create_task(transcript)
            result["task"] = task
            result["task_id"] = task.id

        return result

    def get_transcript(self, transcript_id: str) -> Optional[ErrorTranscript]:
        """Get a transcript by ID."""
        return self._transcripts.get(transcript_id)

    def get_task(self, task_id: str) -> Optional[GuidanceTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_pending_transcripts(self) -> List[ErrorTranscript]:
        """Get all pending (unhandled) transcripts."""
        return [t for t in self._transcripts.values() if t.status == HandoffStatus.PENDING]

    def get_open_tasks(self) -> List[GuidanceTask]:
        """Get all open tasks."""
        return [t for t in self._tasks.values() if t.status == "open"]

    def resolve_error(self, transcript_id: str, resolution: str = "") -> bool:
        """Mark an error as resolved."""
        transcript = self._transcripts.get(transcript_id)
        if transcript:
            transcript.status = HandoffStatus.RESOLVED
            if transcript.task_id:
                task = self._tasks.get(transcript.task_id)
                if task:
                    task.status = "resolved"

            # Log resolution
            if self.health_logger:
                self.health_logger.log_self_heal("resolve", transcript_id, resolution or "resolved")

            logger.info(f"Resolved error: {transcript_id}")
            return True
        return False

    def dismiss_error(self, transcript_id: str, reason: str = "") -> bool:
        """Dismiss an error without fixing."""
        transcript = self._transcripts.get(transcript_id)
        if transcript:
            transcript.status = HandoffStatus.DISMISSED
            if transcript.task_id:
                task = self._tasks.get(transcript.task_id)
                if task:
                    task.status = "dismissed"
            logger.info(f"Dismissed error: {transcript_id} - {reason}")
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get error handoff statistics."""
        severity_counts = {}
        status_counts = {}

        for t in self._transcripts.values():
            sev = t.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            stat = t.status.value
            status_counts[stat] = status_counts.get(stat, 0) + 1

        return {
            "total_transcripts": len(self._transcripts),
            "total_tasks": len(self._tasks),
            "pending_count": len(self.get_pending_transcripts()),
            "open_tasks": len(self.get_open_tasks()),
            "by_severity": severity_counts,
            "by_status": status_counts
        }

