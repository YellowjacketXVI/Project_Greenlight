"""
OmniMind Usage Metrics Logger

Tracks and stores:
- Failed requests and error patterns
- Feature usage metrics
- Task execution metrics
- Requested but unavailable features
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from threading import Lock

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.usage_metrics")


class MetricType(Enum):
    """Types of metrics tracked."""
    FAILED_REQUEST = "failed_request"
    FEATURE_USAGE = "feature_usage"
    TASK_EXECUTION = "task_execution"
    UNAVAILABLE_FEATURE = "unavailable_feature"
    USER_FEEDBACK = "user_feedback"


@dataclass
class MetricEntry:
    """A single metric entry."""
    id: str
    metric_type: MetricType
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "metric_type": self.metric_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }


class UsageMetricsLogger:
    """
    Logs OmniMind usage metrics for analysis and improvement.
    
    Usage:
        metrics = UsageMetricsLogger(project_path)
        
        # Log a failed request
        metrics.log_failed_request("generate_image", "API timeout", {"model": "flux"})
        
        # Log feature usage
        metrics.log_feature_usage("writer_pipeline", {"scenes": 5})
        
        # Log unavailable feature request
        metrics.log_unavailable_feature("video_generation", "User asked for video export")
        
        # Get stats
        stats = metrics.get_stats()
    """
    
    def __init__(self, project_path: Optional[Path] = None):
        self.project_path = Path(project_path) if project_path else None
        self._entries: List[MetricEntry] = []
        self._lock = Lock()
        self._next_id = 0
        
        # Feature usage counters
        self._feature_counts: Dict[str, int] = {}
        self._failed_counts: Dict[str, int] = {}
        self._unavailable_requests: Dict[str, int] = {}
        
        # Setup storage
        if self.project_path:
            self.metrics_dir = self.project_path / ".omni_metrics"
            self.metrics_dir.mkdir(parents=True, exist_ok=True)
            self.metrics_file = self.metrics_dir / "usage_metrics.json"
            self._load_from_disk()
    
    def _generate_id(self, prefix: str = "metric") -> str:
        """Generate unique metric ID."""
        self._next_id += 1
        return f"{prefix}_{self._next_id:06d}"
    
    def _load_from_disk(self) -> None:
        """Load existing metrics from disk."""
        if self.metrics_file and self.metrics_file.exists():
            try:
                data = json.loads(self.metrics_file.read_text(encoding='utf-8'))
                self._feature_counts = data.get("feature_counts", {})
                self._failed_counts = data.get("failed_counts", {})
                self._unavailable_requests = data.get("unavailable_requests", {})
                self._next_id = data.get("next_id", 0)
                logger.debug(f"Loaded {len(self._feature_counts)} feature metrics")
            except Exception as e:
                logger.warning(f"Failed to load metrics: {e}")
    
    def _save_to_disk(self) -> None:
        """Save metrics to disk."""
        if not self.metrics_file:
            return
        try:
            data = {
                "feature_counts": self._feature_counts,
                "failed_counts": self._failed_counts,
                "unavailable_requests": self._unavailable_requests,
                "next_id": self._next_id,
                "last_updated": datetime.now().isoformat()
            }
            self.metrics_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
        except Exception as e:
            logger.warning(f"Failed to save metrics: {e}")
    
    def log_failed_request(
        self,
        feature: str,
        error_message: str,
        context: Dict[str, Any] = None
    ) -> MetricEntry:
        """Log a failed request."""
        with self._lock:
            self._failed_counts[feature] = self._failed_counts.get(feature, 0) + 1
            
            entry = MetricEntry(
                id=self._generate_id("fail"),
                metric_type=MetricType.FAILED_REQUEST,
                data={
                    "feature": feature,
                    "error": error_message,
                    "context": context or {}
                }
            )
            self._entries.append(entry)
            self._save_to_disk()
            
            # Also save detailed failure log
            self._save_failure_log(entry)
            
            logger.info(f"Logged failed request: {feature} - {error_message}")
            return entry
    
    def log_feature_usage(self, feature: str, details: Dict[str, Any] = None) -> MetricEntry:
        """Log feature usage."""
        with self._lock:
            self._feature_counts[feature] = self._feature_counts.get(feature, 0) + 1

            entry = MetricEntry(
                id=self._generate_id("use"),
                metric_type=MetricType.FEATURE_USAGE,
                data={"feature": feature, "details": details or {}}
            )
            self._entries.append(entry)
            self._save_to_disk()
            return entry

    def log_unavailable_feature(self, feature: str, user_request: str) -> MetricEntry:
        """Log when user requests a feature that doesn't exist."""
        with self._lock:
            self._unavailable_requests[feature] = self._unavailable_requests.get(feature, 0) + 1

            entry = MetricEntry(
                id=self._generate_id("unavail"),
                metric_type=MetricType.UNAVAILABLE_FEATURE,
                data={"feature": feature, "user_request": user_request}
            )
            self._entries.append(entry)
            self._save_to_disk()

            # Save to requested features log
            self._save_requested_feature(entry)

            logger.info(f"Logged unavailable feature request: {feature}")
            return entry

    def log_task_execution(
        self,
        task_name: str,
        success: bool,
        duration_ms: float,
        details: Dict[str, Any] = None
    ) -> MetricEntry:
        """Log task execution metrics."""
        with self._lock:
            entry = MetricEntry(
                id=self._generate_id("task"),
                metric_type=MetricType.TASK_EXECUTION,
                data={
                    "task": task_name,
                    "success": success,
                    "duration_ms": duration_ms,
                    "details": details or {}
                }
            )
            self._entries.append(entry)
            self._save_to_disk()
            return entry

    def _save_failure_log(self, entry: MetricEntry) -> None:
        """Save detailed failure to separate log file."""
        if not self.metrics_dir:
            return
        try:
            failures_file = self.metrics_dir / "failed_requests.jsonl"
            with open(failures_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Failed to save failure log: {e}")

    def _save_requested_feature(self, entry: MetricEntry) -> None:
        """Save requested feature to separate log file."""
        if not self.metrics_dir:
            return
        try:
            requests_file = self.metrics_dir / "requested_features.jsonl"
            with open(requests_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Failed to save requested feature: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        with self._lock:
            total_failures = sum(self._failed_counts.values())
            total_usage = sum(self._feature_counts.values())
            total_unavailable = sum(self._unavailable_requests.values())

            # Top features
            top_features = sorted(
                self._feature_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]

            # Top failures
            top_failures = sorted(
                self._failed_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]

            # Top requested features
            top_requested = sorted(
                self._unavailable_requests.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]

            return {
                "total_feature_usage": total_usage,
                "total_failures": total_failures,
                "total_unavailable_requests": total_unavailable,
                "top_features": dict(top_features),
                "top_failures": dict(top_failures),
                "top_requested_features": dict(top_requested),
                "failure_rate": total_failures / max(total_usage, 1)
            }

    def generate_report(self) -> str:
        """Generate a markdown report of usage metrics."""
        stats = self.get_stats()

        lines = [
            "# OmniMind Usage Metrics Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"- Total Feature Usage: {stats['total_feature_usage']}",
            f"- Total Failures: {stats['total_failures']}",
            f"- Failure Rate: {stats['failure_rate']:.2%}",
            f"- Unavailable Feature Requests: {stats['total_unavailable_requests']}",
            "",
            "## Top Features Used",
        ]

        for feature, count in stats['top_features'].items():
            lines.append(f"- {feature}: {count}")

        lines.extend(["", "## Top Failures"])
        for feature, count in stats['top_failures'].items():
            lines.append(f"- {feature}: {count}")

        lines.extend(["", "## Requested Features (Not Available)"])
        for feature, count in stats['top_requested_features'].items():
            lines.append(f"- {feature}: {count} requests")

        return "\n".join(lines)

