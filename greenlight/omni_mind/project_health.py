"""
Greenlight Project Health Logger

Logs notation vectors with definitions and generates markdown health reports.
Outputs to .health/health_report.md for easy project health monitoring.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from enum import Enum
import json

from greenlight.core.logging_config import get_logger
from greenlight.utils.file_utils import ensure_directory, write_text, read_text

logger = get_logger("omni_mind.project_health")


class HealthStatus(Enum):
    """Overall health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class LogCategory(Enum):
    """Categories for health log entries."""
    NOTATION = "notation"
    ERROR = "error"
    PIPELINE = "pipeline"
    TAG = "tag"
    CACHE = "cache"
    SELF_HEAL = "self_heal"


@dataclass
class HealthLogEntry:
    """A single health log entry."""
    id: str
    category: LogCategory
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    severity: str = "INFO"
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "details": self.details,
            "resolved": self.resolved
        }


@dataclass
class NotationDefinition:
    """A notation definition for the index."""
    notation_id: str
    notation_type: str  # scene, frame, camera, position, lighting
    definition: str
    example: str
    registered_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "notation_id": self.notation_id,
            "notation_type": self.notation_type,
            "definition": self.definition,
            "example": self.example,
            "registered_at": self.registered_at.isoformat()
        }


class ProjectHealthLogger:
    """
    Project health logging and reporting system.
    
    Features:
    - Log notation definitions with translations
    - Track errors and their resolution
    - Monitor pipeline executions
    - Generate markdown health reports
    - Maintain notation definition index
    """
    
    def __init__(self, project_path: Path = None):
        """
        Initialize the health logger.
        
        Args:
            project_path: Path to the project root
        """
        self.project_path = project_path
        self._logs: List[HealthLogEntry] = []
        self._notations: Dict[str, NotationDefinition] = {}
        self._pipeline_history: List[Dict[str, Any]] = []
        self._next_id = 0
        
        if project_path:
            self.health_dir = project_path / ".health"
            ensure_directory(self.health_dir)
    
    def _generate_id(self, prefix: str = "log") -> str:
        """Generate a unique log ID."""
        self._next_id += 1
        return f"{prefix}_{self._next_id:06d}"
    
    def log(
        self,
        category: LogCategory,
        message: str,
        severity: str = "INFO",
        **details
    ) -> HealthLogEntry:
        """
        Add a log entry.
        
        Args:
            category: Log category
            message: Log message
            severity: CRITICAL, ERROR, WARNING, INFO
            **details: Additional details
            
        Returns:
            Created HealthLogEntry
        """
        entry = HealthLogEntry(
            id=self._generate_id("log"),
            category=category,
            message=message,
            severity=severity,
            details=details
        )
        self._logs.append(entry)
        logger.debug(f"Health log: [{severity}] {category.value}: {message}")
        return entry
    
    def log_error(
        self,
        error: Exception,
        source: str,
        context: Dict[str, Any] = None
    ) -> HealthLogEntry:
        """Log an error with context."""
        return self.log(
            LogCategory.ERROR,
            str(error),
            severity="ERROR",
            source=source,
            error_type=type(error).__name__,
            context=context or {}
        )
    
    def log_notation(
        self,
        notation_id: str,
        notation_type: str,
        definition: str,
        example: str = ""
    ) -> NotationDefinition:
        """
        Register a notation definition.
        
        Args:
            notation_id: Unique notation identifier
            notation_type: Type (scene, frame, camera, etc.)
            definition: Human-readable definition
            example: Example usage
            
        Returns:
            Created NotationDefinition
        """
        notation = NotationDefinition(
            notation_id=notation_id,
            notation_type=notation_type,
            definition=definition,
            example=example
        )
        self._notations[notation_id] = notation

        # Also log the registration
        self.log(
            LogCategory.NOTATION,
            f"Registered notation: {notation_id}",
            severity="INFO",
            notation_type=notation_type
        )
        return notation

    def log_pipeline(
        self,
        pipeline_name: str,
        status: str,
        duration_seconds: float = 0,
        **details
    ) -> None:
        """Log a pipeline execution."""
        entry = {
            "pipeline": pipeline_name,
            "status": status,
            "duration_seconds": duration_seconds,
            "timestamp": datetime.now().isoformat(),
            **details
        }
        self._pipeline_history.append(entry)

        severity = "INFO" if status == "success" else "WARNING"
        self.log(
            LogCategory.PIPELINE,
            f"Pipeline {pipeline_name}: {status}",
            severity=severity,
            duration=duration_seconds
        )

    def log_self_heal(
        self,
        action: str,
        issue_id: str,
        result: str
    ) -> HealthLogEntry:
        """Log a self-healing action."""
        return self.log(
            LogCategory.SELF_HEAL,
            f"Self-heal {action}: {issue_id} -> {result}",
            severity="INFO",
            action=action,
            issue_id=issue_id,
            result=result
        )

    def resolve_entry(self, entry_id: str) -> bool:
        """Mark a log entry as resolved."""
        for entry in self._logs:
            if entry.id == entry_id:
                entry.resolved = True
                return True
        return False

    def get_unresolved(self) -> List[HealthLogEntry]:
        """Get all unresolved log entries."""
        return [e for e in self._logs if not e.resolved]

    def get_by_category(self, category: LogCategory) -> List[HealthLogEntry]:
        """Get logs by category."""
        return [e for e in self._logs if e.category == category]

    def get_status(self) -> HealthStatus:
        """Determine overall health status."""
        unresolved = self.get_unresolved()

        critical_count = sum(1 for e in unresolved if e.severity == "CRITICAL")
        error_count = sum(1 for e in unresolved if e.severity == "ERROR")

        if critical_count > 0:
            return HealthStatus.CRITICAL
        elif error_count > 0:
            return HealthStatus.WARNING
        elif len(self._logs) == 0:
            return HealthStatus.UNKNOWN
        else:
            return HealthStatus.HEALTHY

    def generate_health_report(self) -> str:
        """Generate a markdown health report."""
        status = self.get_status()
        now = datetime.now()

        lines = [
            "# Project Health Report",
            f"",
            f"**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Status:** {status.value.upper()}",
            f"",
            "---",
            "",
            "## Summary",
            "",
            f"- Total Log Entries: {len(self._logs)}",
            f"- Unresolved Issues: {len(self.get_unresolved())}",
            f"- Registered Notations: {len(self._notations)}",
            f"- Pipeline Executions: {len(self._pipeline_history)}",
            "",
        ]

        # Unresolved Issues Section
        unresolved = self.get_unresolved()
        if unresolved:
            lines.extend([
                "## ⚠️ Unresolved Issues",
                "",
                "| ID | Severity | Category | Message |",
                "|-----|----------|----------|---------|",
            ])
            for entry in unresolved[:20]:  # Limit to 20
                lines.append(
                    f"| {entry.id} | {entry.severity} | {entry.category.value} | {entry.message[:50]} |"
                )
            lines.append("")

        # Notation Index Section
        if self._notations:
            lines.extend([
                "## 📝 Notation Definition Index",
                "",
                "| ID | Type | Definition |",
                "|----|------|------------|",
            ])
            for notation in list(self._notations.values())[:30]:
                lines.append(
                    f"| `{notation.notation_id}` | {notation.notation_type} | {notation.definition[:40]} |"
                )
            lines.append("")

        # Recent Pipeline History
        if self._pipeline_history:
            lines.extend([
                "## 🔄 Recent Pipeline Executions",
                "",
                "| Pipeline | Status | Duration |",
                "|----------|--------|----------|",
            ])
            for entry in self._pipeline_history[-10:]:
                lines.append(
                    f"| {entry['pipeline']} | {entry['status']} | {entry.get('duration_seconds', 0):.2f}s |"
                )
            lines.append("")

        # Error Summary
        errors = self.get_by_category(LogCategory.ERROR)
        if errors:
            lines.extend([
                "## ❌ Error Log",
                "",
            ])
            for entry in errors[-10:]:
                lines.append(f"- **[{entry.severity}]** {entry.message}")
                if entry.details.get("source"):
                    lines.append(f"  - Source: {entry.details['source']}")
            lines.append("")

        # Self-Healing History
        heals = self.get_by_category(LogCategory.SELF_HEAL)
        if heals:
            lines.extend([
                "## 🔧 Self-Healing History",
                "",
            ])
            for entry in heals[-10:]:
                lines.append(f"- {entry.message}")
            lines.append("")

        lines.extend([
            "---",
            f"*Report generated by OmniMind Project Health Logger*"
        ])

        return "\n".join(lines)

    def save_health_report(self) -> Path:
        """Generate and save health report to .health/health_report.md"""
        if not self.project_path:
            logger.warning("No project path set, cannot save health report")
            return None

        report = self.generate_health_report()
        report_path = self.health_dir / "health_report.md"
        write_text(report_path, report)
        logger.info(f"Health report saved to: {report_path}")
        return report_path

    def get_stats(self) -> Dict[str, Any]:
        """Get health logger statistics."""
        return {
            "total_logs": len(self._logs),
            "unresolved_count": len(self.get_unresolved()),
            "notation_count": len(self._notations),
            "pipeline_executions": len(self._pipeline_history),
            "status": self.get_status().value,
            "logs_by_category": {
                cat.value: len(self.get_by_category(cat))
                for cat in LogCategory
            }
        }

