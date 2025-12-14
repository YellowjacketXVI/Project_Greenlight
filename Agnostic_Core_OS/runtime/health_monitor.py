"""
Agnostic_Core_OS Health Monitor

Runtime health tracking and self-healing capabilities.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from datetime import datetime
from pathlib import Path
from enum import Enum
import logging

if TYPE_CHECKING:
    from .daemon import RuntimeDaemon

logger = logging.getLogger("agnostic_core_os.runtime.health_monitor")


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthIssue:
    """A detected health issue."""
    issue_id: str
    component: str
    severity: str
    message: str
    auto_fixable: bool = False
    detected_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    fix_action: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "component": self.component,
            "severity": self.severity,
            "message": self.message,
            "auto_fixable": self.auto_fixable,
            "detected_at": self.detected_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "fix_action": self.fix_action,
        }


@dataclass
class RuntimeHealth:
    """Runtime health status."""
    status: HealthStatus
    checked_at: datetime
    issues: List[HealthIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_healthy(self) -> bool:
        return self.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "is_healthy": self.is_healthy,
            "checked_at": self.checked_at.isoformat(),
            "issues": [i.to_dict() for i in self.issues],
            "metrics": self.metrics,
        }


class HealthMonitor:
    """
    Health monitor for the runtime.
    
    Features:
    - Component health checks
    - Issue detection and tracking
    - Auto-healing capabilities
    - Health report generation
    
    Usage:
        monitor = HealthMonitor(daemon)
        
        # Check health
        health = await monitor.check()
        
        # Auto-heal issues
        if not health.is_healthy:
            await monitor.heal()
    """
    
    def __init__(self, daemon: "RuntimeDaemon"):
        self._daemon = daemon
        self._issues: List[HealthIssue] = []
        self._check_history: List[RuntimeHealth] = []
        self._heal_history: List[Dict[str, Any]] = []
        self._next_issue_id = 0
    
    def _generate_issue_id(self) -> str:
        self._next_issue_id += 1
        return f"issue_{self._next_issue_id:06d}"
    
    async def check(self) -> RuntimeHealth:
        """
        Perform a health check on all runtime components.
        
        Returns:
            RuntimeHealth with status and any issues found
        """
        issues = []
        metrics = {}
        
        # Check daemon state
        if not self._daemon.is_running:
            issues.append(HealthIssue(
                issue_id=self._generate_issue_id(),
                component="daemon",
                severity="CRITICAL",
                message="Runtime daemon is not running",
                auto_fixable=True,
                fix_action="restart_daemon",
            ))
        
        # Check app registry
        if self._daemon.app_registry:
            registry = self._daemon.app_registry
            metrics["apps_registered"] = registry.count
            
            # Check for stale connections
            from .app_registry import AppState
            disconnected = registry.find_by_state(AppState.DISCONNECTED)
            if len(disconnected) > 10:
                issues.append(HealthIssue(
                    issue_id=self._generate_issue_id(),
                    component="app_registry",
                    severity="WARNING",
                    message=f"Many disconnected apps: {len(disconnected)}",
                    auto_fixable=True,
                    fix_action="cleanup_disconnected",
                ))
        
        # Check event bus
        if self._daemon.event_bus:
            bus = self._daemon.event_bus
            metrics["events_pending"] = bus.pending_count
            metrics["events_processed"] = bus._events_processed
            
            # Check for queue backup
            if bus.pending_count > bus.queue_size * 0.8:
                issues.append(HealthIssue(
                    issue_id=self._generate_issue_id(),
                    component="event_bus",
                    severity="WARNING",
                    message=f"Event queue near capacity: {bus.pending_count}/{bus.queue_size}",
                    auto_fixable=False,
                ))

        # Determine overall status
        if any(i.severity == "CRITICAL" for i in issues):
            status = HealthStatus.CRITICAL
        elif any(i.severity == "ERROR" for i in issues):
            status = HealthStatus.UNHEALTHY
        elif any(i.severity == "WARNING" for i in issues):
            status = HealthStatus.DEGRADED
        elif issues:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        # Create health result
        health = RuntimeHealth(
            status=status,
            checked_at=datetime.now(),
            issues=issues,
            metrics=metrics,
        )

        # Store issues and history
        self._issues.extend(issues)
        self._check_history.append(health)

        # Keep history bounded
        if len(self._check_history) > 100:
            self._check_history = self._check_history[-100:]

        return health

    async def heal(self) -> Dict[str, Any]:
        """
        Attempt to auto-heal detected issues.

        Returns:
            Dict with healing results
        """
        fixed = []
        failed = []

        for issue in self._issues:
            if not issue.auto_fixable or issue.resolved_at:
                continue

            try:
                result = await self._apply_fix(issue)
                if result:
                    issue.resolved_at = datetime.now()
                    fixed.append(issue.issue_id)
                else:
                    failed.append({"id": issue.issue_id, "reason": "Fix returned False"})
            except Exception as e:
                failed.append({"id": issue.issue_id, "reason": str(e)})

        heal_result = {
            "timestamp": datetime.now().isoformat(),
            "fixed": fixed,
            "failed": failed,
            "remaining": len([i for i in self._issues if not i.resolved_at]),
        }

        self._heal_history.append(heal_result)
        logger.info(f"Healing complete: {len(fixed)} fixed, {len(failed)} failed")

        return heal_result

    async def _apply_fix(self, issue: HealthIssue) -> bool:
        """Apply a fix for an issue."""
        if issue.fix_action == "restart_daemon":
            # Can't restart ourselves, but we can log it
            logger.warning("Daemon restart requested - requires external action")
            return False

        elif issue.fix_action == "cleanup_disconnected":
            if self._daemon.app_registry:
                from .app_registry import AppState
                disconnected = self._daemon.app_registry.find_by_state(AppState.DISCONNECTED)
                for app in disconnected:
                    self._daemon.app_registry.unregister(app.app_id)
                return True

        return False

    def get_issues(self, include_resolved: bool = False) -> List[HealthIssue]:
        """Get current issues."""
        if include_resolved:
            return self._issues
        return [i for i in self._issues if not i.resolved_at]

    def generate_report(self) -> str:
        """Generate a health report."""
        lines = [
            "# Agnostic_Core_OS Runtime Health Report",
            f"",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
        ]

        # Latest health check
        if self._check_history:
            latest = self._check_history[-1]
            lines.extend([
                "## Current Status",
                f"",
                f"**Status:** {latest.status.value.upper()}",
                f"**Last Check:** {latest.checked_at.strftime('%H:%M:%S')}",
                f"",
                "### Metrics",
            ])
            for key, value in latest.metrics.items():
                lines.append(f"- {key}: {value}")
            lines.append("")

        # Active issues
        active_issues = self.get_issues(include_resolved=False)
        if active_issues:
            lines.extend([
                "## Active Issues",
                "",
            ])
            for issue in active_issues:
                lines.append(f"- **[{issue.severity}]** {issue.component}: {issue.message}")
            lines.append("")

        # Healing history
        if self._heal_history:
            lines.extend([
                "## Recent Healing Actions",
                "",
            ])
            for heal in self._heal_history[-5:]:
                lines.append(f"- Fixed: {len(heal['fixed'])}, Failed: {len(heal['failed'])}")
            lines.append("")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get health monitor statistics."""
        return {
            "total_issues": len(self._issues),
            "active_issues": len(self.get_issues()),
            "checks_performed": len(self._check_history),
            "heals_performed": len(self._heal_history),
            "latest_status": self._check_history[-1].status.value if self._check_history else "unknown",
        }

