"""
Greenlight Process Monitor

Monitors running processes, tracks their status, and handles errors.
Provides real-time feedback and auto-recovery capabilities.

Usage:
    monitor = ProcessMonitor()
    monitor.start()
    
    # Track a process
    process_id = monitor.track(process_execution)
    
    # Get status
    status = monitor.get_status(process_id)
    
    # Handle errors
    monitor.on_error(process_id, error_handler)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set
from enum import Enum
from pathlib import Path
from datetime import datetime
import threading
import queue
import time
import traceback

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.process_monitor")


class MonitorEventType(Enum):
    """Types of monitor events."""
    PROCESS_STARTED = "process_started"
    PROCESS_PROGRESS = "process_progress"
    PROCESS_COMPLETED = "process_completed"
    PROCESS_FAILED = "process_failed"
    PROCESS_CANCELLED = "process_cancelled"
    ERROR_DETECTED = "error_detected"
    ERROR_RECOVERED = "error_recovered"
    HEALTH_CHECK = "health_check"


@dataclass
class MonitorEvent:
    """An event from the process monitor."""
    event_type: MonitorEventType
    process_id: str
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class TrackedProcess:
    """A process being tracked by the monitor."""
    id: str
    name: str
    started_at: datetime
    status: str = "running"
    progress: float = 0.0
    logs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    result: Any = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3


class ProcessMonitor:
    """
    Monitors running processes and handles errors.
    
    Features:
    - Real-time process tracking
    - Error detection and recovery
    - Progress callbacks
    - Health checks
    - Event history
    """
    
    def __init__(self, auto_recover: bool = True):
        """Initialize the process monitor."""
        self._processes: Dict[str, TrackedProcess] = {}
        self._event_queue: queue.Queue = queue.Queue()
        self._event_history: List[MonitorEvent] = []
        self._callbacks: Dict[MonitorEventType, List[Callable]] = {}
        self._error_handlers: Dict[str, Callable] = {}
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._auto_recover = auto_recover
        self._lock = threading.Lock()
        
        logger.info("ProcessMonitor initialized")
    
    def start(self) -> None:
        """Start the monitor background thread."""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ProcessMonitor"
        )
        self._monitor_thread.start()
        logger.info("ProcessMonitor started")
    
    def stop(self) -> None:
        """Stop the monitor."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("ProcessMonitor stopped")
    
    def track(
        self,
        process_id: str,
        name: str,
        max_recovery: int = 3
    ) -> str:
        """
        Start tracking a process.
        
        Args:
            process_id: Unique process identifier
            name: Human-readable process name
            max_recovery: Maximum auto-recovery attempts
            
        Returns:
            The process ID
        """
        with self._lock:
            process = TrackedProcess(
                id=process_id,
                name=name,
                started_at=datetime.now(),
                max_recovery_attempts=max_recovery
            )
            self._processes[process_id] = process
        
        self._emit_event(MonitorEvent(
            event_type=MonitorEventType.PROCESS_STARTED,
            process_id=process_id,
            timestamp=datetime.now(),
            data={"name": name}
        ))
        
        logger.info(f"Tracking process: {process_id} ({name})")
        return process_id
    
    def update_progress(
        self,
        process_id: str,
        progress: float,
        message: str = None
    ) -> None:
        """Update process progress."""
        with self._lock:
            if process_id not in self._processes:
                return
            
            process = self._processes[process_id]
            process.progress = progress
            if message:
                process.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
        self._emit_event(MonitorEvent(
            event_type=MonitorEventType.PROCESS_PROGRESS,
            process_id=process_id,
            timestamp=datetime.now(),
            data={"progress": progress, "message": message}
        ))
    
    def complete(
        self,
        process_id: str,
        result: Any = None
    ) -> None:
        """Mark a process as completed."""
        with self._lock:
            if process_id not in self._processes:
                return
            
            process = self._processes[process_id]
            process.status = "completed"
            process.progress = 1.0
            process.completed_at = datetime.now()
            process.result = result
        
        self._emit_event(MonitorEvent(
            event_type=MonitorEventType.PROCESS_COMPLETED,
            process_id=process_id,
            timestamp=datetime.now(),
            data={"result": result}
        ))
        
        logger.info(f"Process completed: {process_id}")
    
    def fail(
        self,
        process_id: str,
        error: str,
        recoverable: bool = True
    ) -> None:
        """Mark a process as failed."""
        with self._lock:
            if process_id not in self._processes:
                return
            
            process = self._processes[process_id]
            process.errors.append(error)
            
            # Check if we should attempt recovery
            if recoverable and self._auto_recover:
                if process.recovery_attempts < process.max_recovery_attempts:
                    process.recovery_attempts += 1
                    self._attempt_recovery(process_id, error)
                    return
            
            process.status = "failed"
            process.completed_at = datetime.now()
        
        self._emit_event(MonitorEvent(
            event_type=MonitorEventType.PROCESS_FAILED,
            process_id=process_id,
            timestamp=datetime.now(),
            error=error
        ))
        
        logger.error(f"Process failed: {process_id} - {error}")
    
    def cancel(self, process_id: str) -> None:
        """Cancel a running process."""
        with self._lock:
            if process_id not in self._processes:
                return
            
            process = self._processes[process_id]
            process.status = "cancelled"
            process.completed_at = datetime.now()
        
        self._emit_event(MonitorEvent(
            event_type=MonitorEventType.PROCESS_CANCELLED,
            process_id=process_id,
            timestamp=datetime.now()
        ))
        
        logger.info(f"Process cancelled: {process_id}")
    
    def get_status(self, process_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a tracked process."""
        with self._lock:
            if process_id not in self._processes:
                return None
            
            process = self._processes[process_id]
            return {
                "id": process.id,
                "name": process.name,
                "status": process.status,
                "progress": process.progress,
                "started_at": process.started_at.isoformat(),
                "completed_at": process.completed_at.isoformat() if process.completed_at else None,
                "logs": process.logs[-10:],  # Last 10 logs
                "errors": process.errors,
                "recovery_attempts": process.recovery_attempts
            }
    
    def get_all_active(self) -> List[Dict[str, Any]]:
        """Get all active (running) processes."""
        with self._lock:
            return [
                self.get_status(pid)
                for pid, p in self._processes.items()
                if p.status == "running"
            ]
    
    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent events."""
        return [
            {
                "type": e.event_type.value,
                "process_id": e.process_id,
                "timestamp": e.timestamp.isoformat(),
                "data": e.data,
                "error": e.error
            }
            for e in self._event_history[-limit:]
        ]
    
    def on_event(
        self,
        event_type: MonitorEventType,
        callback: Callable[[MonitorEvent], None]
    ) -> None:
        """Register a callback for an event type."""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)
    
    def set_error_handler(
        self,
        process_id: str,
        handler: Callable[[str, str], bool]
    ) -> None:
        """Set a custom error handler for a process."""
        self._error_handlers[process_id] = handler
    
    def _emit_event(self, event: MonitorEvent) -> None:
        """Emit an event to the queue."""
        self._event_queue.put(event)
        self._event_history.append(event)
        
        # Keep history bounded
        if len(self._event_history) > 1000:
            self._event_history = self._event_history[-500:]
    
    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                # Process events
                try:
                    event = self._event_queue.get(timeout=0.1)
                    self._handle_event(event)
                except queue.Empty:
                    pass
                
                # Periodic health check
                self._health_check()
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(1)
    
    def _handle_event(self, event: MonitorEvent) -> None:
        """Handle an event by calling registered callbacks."""
        callbacks = self._callbacks.get(event.event_type, [])
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _health_check(self) -> None:
        """Perform periodic health checks on running processes."""
        # Check for stalled processes (no progress in 5 minutes)
        with self._lock:
            now = datetime.now()
            for process in self._processes.values():
                if process.status != "running":
                    continue
                
                # Check if process has been running too long without progress
                elapsed = (now - process.started_at).total_seconds()
                if elapsed > 300 and process.progress < 0.1:  # 5 min, <10%
                    logger.warning(f"Process may be stalled: {process.id}")
    
    def _attempt_recovery(self, process_id: str, error: str) -> None:
        """Attempt to recover from an error."""
        logger.info(f"Attempting recovery for {process_id} (attempt {self._processes[process_id].recovery_attempts})")
        
        # Check for custom error handler
        if process_id in self._error_handlers:
            try:
                recovered = self._error_handlers[process_id](process_id, error)
                if recovered:
                    self._emit_event(MonitorEvent(
                        event_type=MonitorEventType.ERROR_RECOVERED,
                        process_id=process_id,
                        timestamp=datetime.now(),
                        data={"error": error, "recovered": True}
                    ))
                    return
            except Exception as e:
                logger.error(f"Error handler failed: {e}")
        
        # Default recovery: log and continue
        self._emit_event(MonitorEvent(
            event_type=MonitorEventType.ERROR_DETECTED,
            process_id=process_id,
            timestamp=datetime.now(),
            error=error,
            data={"recovery_attempted": True}
        ))


# Global monitor instance
_monitor: Optional[ProcessMonitor] = None


def get_process_monitor() -> ProcessMonitor:
    """Get or create the global process monitor."""
    global _monitor
    if _monitor is None:
        _monitor = ProcessMonitor()
        _monitor.start()
    return _monitor


class MissingCharacterWatcher:
    """
    Watches for missing character warnings and triggers self-correction.

    Monitors log output for patterns indicating consensus-approved characters
    are missing from world_config.json and automatically fixes them.
    """

    # Warning patterns to watch for
    WARNING_PATTERNS = [
        "characters approved by consensus but missing from llm response",
        "consensus-approved characters missing from character_arcs",
        "validation warning: consensus-approved characters missing",
    ]

    def __init__(self, project_path: Path = None, auto_fix: bool = True):
        """
        Initialize the watcher.

        Args:
            project_path: Path to the current project
            auto_fix: Whether to automatically fix detected issues
        """
        self.project_path = project_path
        self.auto_fix = auto_fix
        self._detected_issues: List[Dict[str, Any]] = []
        self._fix_history: List[Dict[str, Any]] = []
        self._enabled = True

        logger.info("MissingCharacterWatcher initialized")

    def set_project(self, project_path: Path) -> None:
        """Set the current project path."""
        self.project_path = project_path

    def check_log_message(self, message: str) -> bool:
        """
        Check if a log message indicates missing characters.

        Args:
            message: The log message to check

        Returns:
            True if the message indicates missing characters
        """
        if not self._enabled:
            return False

        message_lower = message.lower()

        for pattern in self.WARNING_PATTERNS:
            if pattern in message_lower:
                logger.info(f"🔍 Detected missing character warning: {message[:100]}...")
                self._detected_issues.append({
                    "timestamp": datetime.now().isoformat(),
                    "message": message,
                    "pattern_matched": pattern
                })

                if self.auto_fix:
                    self._trigger_auto_fix()

                return True

        return False

    def _trigger_auto_fix(self) -> None:
        """Trigger automatic fix for missing characters."""
        if not self.project_path:
            logger.warning("Cannot auto-fix: no project path set")
            return

        logger.info("🔧 Triggering automatic character fix...")

        try:
            from greenlight.omni_mind.tool_executor import ToolExecutor

            executor = ToolExecutor(project_path=self.project_path)

            # Detect missing characters
            detection_result = executor.execute("detect_missing_characters")

            if not detection_result.success:
                logger.error(f"Detection failed: {detection_result.error}")
                return

            missing_tags = detection_result.result.get("missing_tags", [])

            if not missing_tags:
                logger.info("No missing characters detected after re-check")
                return

            logger.info(f"Found {len(missing_tags)} missing character(s): {missing_tags}")

            # Fix missing characters
            fix_result = executor.execute(
                "fix_missing_characters",
                missing_tags=missing_tags,
                dry_run=False
            )

            self._fix_history.append({
                "timestamp": datetime.now().isoformat(),
                "missing_tags": missing_tags,
                "result": fix_result.result,
                "success": fix_result.success
            })

            if fix_result.success:
                fixed_count = fix_result.result.get("fixed_count", 0)
                logger.info(f"✅ Auto-fixed {fixed_count} missing character(s)")
            else:
                logger.error(f"Auto-fix failed: {fix_result.error}")

        except Exception as e:
            logger.error(f"Error during auto-fix: {e}")
            traceback.print_exc()

    def get_status(self) -> Dict[str, Any]:
        """Get watcher status."""
        return {
            "enabled": self._enabled,
            "auto_fix": self.auto_fix,
            "project_path": str(self.project_path) if self.project_path else None,
            "detected_issues_count": len(self._detected_issues),
            "fix_history_count": len(self._fix_history),
            "recent_issues": self._detected_issues[-5:],
            "recent_fixes": self._fix_history[-5:]
        }

    def enable(self) -> None:
        """Enable the watcher."""
        self._enabled = True
        logger.info("MissingCharacterWatcher enabled")

    def disable(self) -> None:
        """Disable the watcher."""
        self._enabled = False
        logger.info("MissingCharacterWatcher disabled")


# Global watcher instance
_character_watcher: Optional[MissingCharacterWatcher] = None


def get_character_watcher() -> MissingCharacterWatcher:
    """Get or create the global character watcher."""
    global _character_watcher
    if _character_watcher is None:
        _character_watcher = MissingCharacterWatcher()
    return _character_watcher


def setup_character_watcher(project_path: Path = None, auto_fix: bool = True) -> MissingCharacterWatcher:
    """Setup and return the character watcher with project path."""
    watcher = get_character_watcher()
    if project_path:
        watcher.set_project(project_path)
    watcher.auto_fix = auto_fix
    return watcher

