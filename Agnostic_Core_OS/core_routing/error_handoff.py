"""
Agnostic_Core_OS Error Handoff

Error handoff system for self-healing and guidance.
Standalone version for Agnostic_Core_OS runtime.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import traceback
import logging

logger = logging.getLogger("agnostic_core_os.core_routing.error_handoff")


class ErrorSeverity(Enum):
    """Error severity levels."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class HandoffStatus(Enum):
    """Status of error handoff."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class ErrorTranscript:
    """Structured error transcript for handoff."""
    id: str
    severity: ErrorSeverity
    source: str
    error_type: str
    message: str
    stack_trace: str
    context: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    status: HandoffStatus = HandoffStatus.PENDING
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "source": self.source,
            "error_type": self.error_type,
            "message": self.message,
            "stack_trace": self.stack_trace,
            "context": self.context,
            "suggested_actions": self.suggested_actions,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
        }
    
    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = [
            f"# Error Transcript: {self.id}",
            "",
            f"**Severity:** {self.severity.value.upper()}",
            f"**Source:** {self.source}",
            f"**Type:** {self.error_type}",
            f"**Time:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Status:** {self.status.value}",
            "",
            "## Message",
            "",
            self.message,
            "",
            "## Stack Trace",
            "",
            "```",
            self.stack_trace,
            "```",
            "",
        ]
        
        if self.suggested_actions:
            lines.extend([
                "## Suggested Actions",
                "",
            ])
            for action in self.suggested_actions:
                lines.append(f"- {action}")
            lines.append("")
        
        if self.context:
            lines.extend([
                "## Context",
                "",
            ])
            for key, value in self.context.items():
                lines.append(f"- **{key}:** {value}")
            lines.append("")
        
        return "\n".join(lines)


@dataclass
class GuidanceTask:
    """A task created for error guidance."""
    id: str
    transcript_id: str
    title: str
    description: str
    priority: str = "normal"
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    assigned_to: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "transcript_id": self.transcript_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "assigned_to": self.assigned_to,
        }


class ErrorHandoff:
    """
    Error handoff system for Agnostic_Core_OS.
    
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
        """Initialize error handoff system."""
        self.vector_cache = vector_cache
        self.health_logger = health_logger
        self._transcripts: Dict[str, ErrorTranscript] = {}
        self._tasks: Dict[str, GuidanceTask] = {}
        self._next_id = 0
        self._handlers: Dict[str, Callable] = {}
    
    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID."""
        self._next_id += 1
        return f"{prefix}_{self._next_id:06d}"

    def flag_error(
        self,
        error: Exception,
        severity: ErrorSeverity,
        source: str,
        context: Optional[Dict[str, Any]] = None,
        suggested_actions: Optional[List[str]] = None
    ) -> ErrorTranscript:
        """Flag an error and create transcript."""
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

        if error_type == "FileNotFoundError":
            suggestions.append("Check if the file path is correct")
            suggestions.append("Ensure the file exists before accessing")
        elif error_type == "KeyError":
            suggestions.append("Verify the key exists in the dictionary")
            suggestions.append("Use .get() with a default value")
        elif error_type == "TypeError":
            suggestions.append("Check argument types match expected types")
            suggestions.append("Verify function signatures")
        elif error_type == "ValueError":
            suggestions.append("Validate input values before processing")
            suggestions.append("Add input validation")
        elif error_type == "ImportError":
            suggestions.append("Check if the module is installed")
            suggestions.append("Verify import path is correct")
        else:
            suggestions.append("Review the stack trace for context")
            suggestions.append("Check related code for issues")

        return suggestions

    def create_task(
        self,
        transcript: ErrorTranscript,
        priority: str = "normal"
    ) -> GuidanceTask:
        """Create a guidance task for an error."""
        task = GuidanceTask(
            id=self._generate_id("task"),
            transcript_id=transcript.id,
            title=f"[{transcript.severity.value.upper()}] {transcript.error_type} in {transcript.source}",
            description=transcript.message,
            priority=priority
        )

        self._tasks[task.id] = task
        logger.info(f"Created guidance task: {task.id}")
        return task

    def handoff_for_guidance(
        self,
        error: Exception,
        severity: ErrorSeverity,
        source: str,
        context: Optional[Dict[str, Any]] = None,
        auto_create_task: bool = True
    ) -> Dict[str, Any]:
        """Complete error handoff flow: flag → cache → task → log."""
        # Step 1: Flag and create transcript
        transcript = self.flag_error(error, severity, source, context)

        result = {
            "transcript": transcript,
            "transcript_id": transcript.id,
            "cached": self.vector_cache is not None,
            "logged": self.health_logger is not None
        }

        # Step 2: Create guidance task if requested
        if auto_create_task:
            priority = "high" if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.ERROR] else "normal"
            task = self.create_task(transcript, priority)
            result["task"] = task
            result["task_id"] = task.id

        return result

    def resolve(self, transcript_id: str, resolution: str = "") -> bool:
        """Mark an error as resolved."""
        transcript = self._transcripts.get(transcript_id)
        if transcript:
            transcript.status = HandoffStatus.RESOLVED

            # Log resolution
            if self.health_logger:
                self.health_logger.log_self_heal(
                    f"Resolved {transcript_id}: {resolution}",
                    success=True
                )

            logger.info(f"Resolved: {transcript_id}")
            return True
        return False

    def get_pending(self) -> List[ErrorTranscript]:
        """Get all pending error transcripts."""
        return [t for t in self._transcripts.values() if t.status == HandoffStatus.PENDING]

    def get_by_severity(self, severity: ErrorSeverity) -> List[ErrorTranscript]:
        """Get transcripts by severity."""
        return [t for t in self._transcripts.values() if t.severity == severity]

    def get_stats(self) -> Dict[str, Any]:
        """Get error handoff statistics."""
        severity_counts = {}
        for sev in ErrorSeverity:
            severity_counts[sev.value] = len(self.get_by_severity(sev))

        status_counts = {}
        for status in HandoffStatus:
            status_counts[status.value] = len([t for t in self._transcripts.values() if t.status == status])

        return {
            "total_transcripts": len(self._transcripts),
            "total_tasks": len(self._tasks),
            "pending": len(self.get_pending()),
            "by_severity": severity_counts,
            "by_status": status_counts,
        }

