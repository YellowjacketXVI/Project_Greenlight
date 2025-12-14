"""
Greenlight Terminal Logger System

Provides a separate terminal log for agent process output with advanced user access.
Allows users to view, filter, and interact with agent processes in real-time.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path
from enum import Enum
from collections import deque
import json
import threading

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.terminal_logger")


class LogLevel(Enum):
    """Log levels for terminal output."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    AGENT = "AGENT"      # Agent-specific output
    PROCESS = "PROCESS"  # Process execution output
    USER = "USER"        # User interaction


class ProcessStatus(Enum):
    """Status of a tracked process."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TerminalEntry:
    """A single terminal log entry."""
    id: str
    timestamp: datetime
    level: LogLevel
    source: str
    message: str
    process_id: Optional[str] = None
    agent_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "source": self.source,
            "message": self.message,
            "process_id": self.process_id,
            "agent_name": self.agent_name,
            "metadata": self.metadata
        }
    
    def format_line(self, include_timestamp: bool = True) -> str:
        """Format as terminal line."""
        parts = []
        if include_timestamp:
            parts.append(f"[{self.timestamp.strftime('%H:%M:%S')}]")
        parts.append(f"[{self.level.value}]")
        if self.agent_name:
            parts.append(f"[{self.agent_name}]")
        parts.append(self.message)
        return " ".join(parts)


@dataclass
class TrackedProcess:
    """A tracked agent process."""
    id: str
    name: str
    agent_name: str
    status: ProcessStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    output_lines: List[str] = field(default_factory=list)
    error_lines: List[str] = field(default_factory=list)
    result: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TerminalLogger:
    """
    Terminal logging system for OmniMind agent processes.
    
    Features:
    - Real-time process output logging
    - Filterable by level, source, agent
    - Process tracking with status
    - Exportable logs
    - Subscriber pattern for UI updates
    """
    
    MAX_ENTRIES = 10000  # Max entries to keep in memory
    MAX_PROCESS_OUTPUT = 1000  # Max lines per process
    
    def __init__(
        self,
        project_path: Path = None,
        log_to_file: bool = True
    ):
        """
        Initialize terminal logger.
        
        Args:
            project_path: Project root path
            log_to_file: Whether to persist logs to file
        """
        self.project_path = project_path
        self.log_to_file = log_to_file
        
        # Log storage
        self._entries: deque = deque(maxlen=self.MAX_ENTRIES)
        self._processes: Dict[str, TrackedProcess] = {}
        self._next_id = 0
        self._lock = threading.Lock()
        
        # Subscribers for real-time updates
        self._subscribers: List[Callable[[TerminalEntry], None]] = []
        
        # Log directory
        if project_path:
            self.log_dir = project_path / ".logs" / "terminal"
            self.log_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.log_dir = None
    
    def _generate_id(self, prefix: str = "log") -> str:
        """Generate unique ID."""
        self._next_id += 1
        return f"{prefix}_{self._next_id:08d}"
    
    def subscribe(self, callback: Callable[[TerminalEntry], None]) -> None:
        """Subscribe to log updates."""
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[TerminalEntry], None]) -> None:
        """Unsubscribe from log updates."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    def _notify_subscribers(self, entry: TerminalEntry) -> None:
        """Notify all subscribers of new entry."""
        for callback in self._subscribers:
            try:
                callback(entry)
            except Exception as e:
                logger.error(f"Subscriber callback error: {e}")

    def log(
        self,
        level: LogLevel,
        message: str,
        source: str = "system",
        process_id: str = None,
        agent_name: str = None,
        **metadata
    ) -> TerminalEntry:
        """
        Log a terminal entry.

        Args:
            level: Log level
            message: Log message
            source: Source of the log
            process_id: Associated process ID
            agent_name: Associated agent name
            **metadata: Additional metadata

        Returns:
            Created TerminalEntry
        """
        with self._lock:
            entry = TerminalEntry(
                id=self._generate_id("log"),
                timestamp=datetime.now(),
                level=level,
                source=source,
                message=message,
                process_id=process_id,
                agent_name=agent_name,
                metadata=metadata
            )

            self._entries.append(entry)

            # Add to process output if tracking
            if process_id and process_id in self._processes:
                proc = self._processes[process_id]
                if level == LogLevel.ERROR:
                    proc.error_lines.append(message)
                else:
                    proc.output_lines.append(message)

            # Notify subscribers
            self._notify_subscribers(entry)

            # Persist to file if enabled
            if self.log_to_file and self.log_dir:
                self._persist_entry(entry)

            return entry

    def _persist_entry(self, entry: TerminalEntry) -> None:
        """Persist entry to log file."""
        try:
            date_str = entry.timestamp.strftime("%Y-%m-%d")
            log_file = self.log_dir / f"terminal_{date_str}.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry.format_line() + "\n")
        except Exception as e:
            logger.error(f"Failed to persist log entry: {e}")

    def log_info(self, message: str, **kwargs) -> TerminalEntry:
        """Log info level message."""
        return self.log(LogLevel.INFO, message, **kwargs)

    def log_warning(self, message: str, **kwargs) -> TerminalEntry:
        """Log warning level message."""
        return self.log(LogLevel.WARNING, message, **kwargs)

    def log_error(self, message: str, **kwargs) -> TerminalEntry:
        """Log error level message."""
        return self.log(LogLevel.ERROR, message, **kwargs)

    def log_agent(self, agent_name: str, message: str, **kwargs) -> TerminalEntry:
        """Log agent-specific output."""
        return self.log(LogLevel.AGENT, message, agent_name=agent_name, **kwargs)

    def log_process(self, process_id: str, message: str, **kwargs) -> TerminalEntry:
        """Log process output."""
        return self.log(LogLevel.PROCESS, message, process_id=process_id, **kwargs)

    # =========================================================================
    # PROCESS TRACKING
    # =========================================================================

    def start_process(
        self,
        name: str,
        agent_name: str = "system",
        **metadata
    ) -> TrackedProcess:
        """
        Start tracking a new process.

        Args:
            name: Process name
            agent_name: Agent running the process
            **metadata: Additional metadata

        Returns:
            TrackedProcess instance
        """
        process = TrackedProcess(
            id=self._generate_id("proc"),
            name=name,
            agent_name=agent_name,
            status=ProcessStatus.RUNNING,
            started_at=datetime.now(),
            metadata=metadata
        )

        self._processes[process.id] = process

        self.log(
            LogLevel.PROCESS,
            f"Started: {name}",
            source="process_tracker",
            process_id=process.id,
            agent_name=agent_name
        )

        return process

    def complete_process(
        self,
        process_id: str,
        result: Any = None,
        success: bool = True
    ) -> Optional[TrackedProcess]:
        """
        Mark a process as completed.

        Args:
            process_id: Process ID
            result: Process result
            success: Whether process succeeded

        Returns:
            Updated TrackedProcess or None
        """
        if process_id not in self._processes:
            return None

        process = self._processes[process_id]
        process.status = ProcessStatus.COMPLETED if success else ProcessStatus.FAILED
        process.completed_at = datetime.now()
        process.result = result

        status_str = "Completed" if success else "Failed"
        self.log(
            LogLevel.PROCESS,
            f"{status_str}: {process.name}",
            source="process_tracker",
            process_id=process_id,
            agent_name=process.agent_name
        )

        return process

    def cancel_process(self, process_id: str) -> Optional[TrackedProcess]:
        """Cancel a running process."""
        if process_id not in self._processes:
            return None

        process = self._processes[process_id]
        process.status = ProcessStatus.CANCELLED
        process.completed_at = datetime.now()

        self.log(
            LogLevel.PROCESS,
            f"Cancelled: {process.name}",
            source="process_tracker",
            process_id=process_id
        )

        return process

    def get_process(self, process_id: str) -> Optional[TrackedProcess]:
        """Get a tracked process by ID."""
        return self._processes.get(process_id)

    def get_running_processes(self) -> List[TrackedProcess]:
        """Get all running processes."""
        return [p for p in self._processes.values() if p.status == ProcessStatus.RUNNING]

    # =========================================================================
    # FILTERING & RETRIEVAL
    # =========================================================================

    def get_entries(
        self,
        level: LogLevel = None,
        source: str = None,
        agent_name: str = None,
        process_id: str = None,
        since: datetime = None,
        limit: int = 100
    ) -> List[TerminalEntry]:
        """
        Get filtered log entries.

        Args:
            level: Filter by level
            source: Filter by source
            agent_name: Filter by agent
            process_id: Filter by process
            since: Filter by timestamp
            limit: Max entries to return

        Returns:
            List of matching entries
        """
        results = []

        for entry in reversed(self._entries):
            if len(results) >= limit:
                break

            if level and entry.level != level:
                continue
            if source and entry.source != source:
                continue
            if agent_name and entry.agent_name != agent_name:
                continue
            if process_id and entry.process_id != process_id:
                continue
            if since and entry.timestamp < since:
                continue

            results.append(entry)

        return list(reversed(results))

    def get_recent(self, count: int = 50) -> List[TerminalEntry]:
        """Get most recent entries."""
        return list(self._entries)[-count:]

    def search(self, query: str, limit: int = 100) -> List[TerminalEntry]:
        """Search entries by message content."""
        query_lower = query.lower()
        results = []

        for entry in reversed(self._entries):
            if len(results) >= limit:
                break
            if query_lower in entry.message.lower():
                results.append(entry)

        return list(reversed(results))

    def export_log(self, filepath: Path = None) -> str:
        """
        Export all entries to file or return as string.

        Args:
            filepath: Optional file path to save

        Returns:
            Log content as string
        """
        lines = [entry.format_line() for entry in self._entries]
        content = "\n".join(lines)

        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        return content

    def clear(self) -> int:
        """Clear all entries. Returns count cleared."""
        count = len(self._entries)
        self._entries.clear()
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get terminal logger statistics."""
        level_counts = {}
        for entry in self._entries:
            lv = entry.level.value
            level_counts[lv] = level_counts.get(lv, 0) + 1

        return {
            "total_entries": len(self._entries),
            "max_entries": self.MAX_ENTRIES,
            "tracked_processes": len(self._processes),
            "running_processes": len(self.get_running_processes()),
            "subscribers": len(self._subscribers),
            "by_level": level_counts
        }

