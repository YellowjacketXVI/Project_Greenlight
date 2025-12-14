"""
Agnostic_Core_OS Health Logger

Health monitoring and markdown report generation.
Standalone version for Agnostic_Core_OS runtime.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from enum import Enum
import logging

logger = logging.getLogger("agnostic_core_os.core_routing.health_logger")


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class LogCategory(Enum):
    """Categories for health logs."""
    TAG_VALIDATION = "tag_validation"
    PIPELINE = "pipeline"
    ERROR = "error"
    SELF_HEAL = "self_heal"
    NOTATION = "notation"
    VECTOR_CACHE = "vector_cache"
    RUNTIME = "runtime"


@dataclass
class HealthLogEntry:
    """A single health log entry."""
    id: str
    category: LogCategory
    message: str
    severity: str = "INFO"
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class NotationDefinition:
    """A notation definition with translation."""
    notation: str
    translation: str
    scope: str
    examples: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "notation": self.notation,
            "translation": self.translation,
            "scope": self.scope,
            "examples": self.examples,
            "timestamp": self.timestamp.isoformat(),
        }


class HealthLogger:
    """
    Health logging and reporting system for Agnostic_Core_OS.
    
    Features:
    - Log notation definitions with translations
    - Track errors and their resolution
    - Monitor pipeline executions
    - Generate markdown health reports
    - Maintain notation definition index
    """
    
    def __init__(self, project_path: Optional[Path] = None):
        """Initialize the health logger."""
        self.project_path = project_path
        self._logs: List[HealthLogEntry] = []
        self._notations: Dict[str, NotationDefinition] = {}
        self._pipeline_history: List[Dict[str, Any]] = []
        self._next_id = 0
        
        if project_path:
            self.health_dir = project_path / ".health"
            self.health_dir.mkdir(parents=True, exist_ok=True)
    
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
        """Add a log entry."""
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
        context: Optional[Dict[str, Any]] = None
    ) -> HealthLogEntry:
        """Log an error."""
        return self.log(
            LogCategory.ERROR,
            f"{type(error).__name__}: {str(error)}",
            severity="ERROR",
            source=source,
            error_type=type(error).__name__,
            context=context or {}
        )
    
    def log_self_heal(
        self,
        action: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> HealthLogEntry:
        """Log a self-healing action."""
        severity = "INFO" if success else "WARNING"
        status = "SUCCESS" if success else "FAILED"
        return self.log(
            LogCategory.SELF_HEAL,
            f"Self-heal {status}: {action}",
            severity=severity,
            **(details or {})
        )
    
    def log_notation(
        self,
        notation: str,
        translation: str,
        scope: str,
        examples: Optional[List[str]] = None
    ) -> NotationDefinition:
        """Log a notation definition."""
        definition = NotationDefinition(
            notation=notation,
            translation=translation,
            scope=scope,
            examples=examples or []
        )
        self._notations[notation] = definition
        self.log(LogCategory.NOTATION, f"Defined: {notation} → {translation}")
        return definition

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

    def get_by_category(self, category: LogCategory) -> List[HealthLogEntry]:
        """Get logs by category."""
        return [e for e in self._logs if e.category == category]

    def get_by_severity(self, severity: str) -> List[HealthLogEntry]:
        """Get logs by severity."""
        return [e for e in self._logs if e.severity == severity]

    def get_errors(self) -> List[HealthLogEntry]:
        """Get all error logs."""
        return self.get_by_category(LogCategory.ERROR)

    def get_notation(self, notation: str) -> Optional[NotationDefinition]:
        """Get a notation definition."""
        return self._notations.get(notation)

    def get_all_notations(self) -> List[NotationDefinition]:
        """Get all notation definitions."""
        return list(self._notations.values())

    def get_status(self) -> HealthStatus:
        """Determine overall health status."""
        errors = self.get_errors()
        recent_errors = [e for e in errors if (datetime.now() - e.timestamp).seconds < 300]

        if len(recent_errors) >= 5:
            return HealthStatus.CRITICAL
        elif len(recent_errors) >= 3:
            return HealthStatus.UNHEALTHY
        elif len(recent_errors) >= 1:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def generate_health_report(self) -> str:
        """Generate a markdown health report."""
        lines = [
            "# Agnostic_Core_OS Health Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Status:** {self.get_status().value.upper()}",
            "",
            "## Summary",
            "",
            f"- Total Logs: {len(self._logs)}",
            f"- Errors: {len(self.get_errors())}",
            f"- Notations Defined: {len(self._notations)}",
            f"- Pipelines Run: {len(self._pipeline_history)}",
            "",
        ]

        # Recent errors
        errors = self.get_errors()
        if errors:
            lines.extend([
                "## Recent Errors",
                "",
            ])
            for entry in errors[-10:]:
                lines.append(f"- [{entry.severity}] {entry.message}")
            lines.append("")

        # Self-healing history
        heals = self.get_by_category(LogCategory.SELF_HEAL)
        if heals:
            lines.extend([
                "## Self-Healing History",
                "",
            ])
            for entry in heals[-10:]:
                lines.append(f"- {entry.message}")
            lines.append("")

        # Notation index
        if self._notations:
            lines.extend([
                "## Notation Index",
                "",
                "| Notation | Translation | Scope |",
                "|----------|-------------|-------|",
            ])
            for notation in list(self._notations.values())[:20]:
                lines.append(f"| `{notation.notation}` | {notation.translation} | {notation.scope} |")
            lines.append("")

        lines.extend([
            "---",
            "*Report generated by Agnostic_Core_OS Health Logger*"
        ])

        return "\n".join(lines)

    def save_health_report(self) -> Optional[Path]:
        """Generate and save health report."""
        if not self.project_path:
            logger.warning("No project path set, cannot save health report")
            return None

        report = self.generate_health_report()
        report_path = self.health_dir / "health_report.md"
        with open(report_path, 'w') as f:
            f.write(report)
        logger.info(f"Health report saved to: {report_path}")
        return report_path

    def get_stats(self) -> Dict[str, Any]:
        """Get health logger statistics."""
        category_counts = {}
        for cat in LogCategory:
            category_counts[cat.value] = len(self.get_by_category(cat))

        return {
            "total_logs": len(self._logs),
            "status": self.get_status().value,
            "notations_defined": len(self._notations),
            "pipelines_run": len(self._pipeline_history),
            "by_category": category_counts,
        }

