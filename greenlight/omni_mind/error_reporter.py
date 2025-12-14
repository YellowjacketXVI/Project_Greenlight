"""
Error Reporter for Augment Integration

Generates structured error transcripts optimized for Augment to quickly
understand and fix errors. Includes self-healing patterns and credit-saving
minimal context mode.

Architecture:
    Error Detected → Classify → Self-Heal Attempt → Generate Transcript → Route

Transcript Levels:
    MINIMAL: Error type + message + file:line (saves credits)
    STANDARD: + stack trace + suggested fix
    FULL: + related code + dependencies + test context
"""

from __future__ import annotations

import sys
import traceback
import inspect
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.error_reporter")


class ErrorCategory(Enum):
    """Categories of errors for routing and self-healing."""
    IMPORT_ERROR = "import_error"
    ATTRIBUTE_ERROR = "attribute_error"
    TYPE_ERROR = "type_error"
    VALUE_ERROR = "value_error"
    KEY_ERROR = "key_error"
    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_ERROR = "permission_error"
    CONNECTION_ERROR = "connection_error"
    API_ERROR = "api_error"
    PIPELINE_ERROR = "pipeline_error"
    UI_ERROR = "ui_error"
    CONFIG_ERROR = "config_error"
    UNKNOWN = "unknown"


class TranscriptLevel(Enum):
    """Level of detail in error transcript."""
    MINIMAL = "minimal"      # Error + location only (saves credits)
    STANDARD = "standard"    # + stack trace + suggestions
    FULL = "full"           # + related code + dependencies


class SelfHealStatus(Enum):
    """Status of self-healing attempt."""
    NOT_ATTEMPTED = "not_attempted"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    DEFERRED = "deferred"


@dataclass
class ErrorContext:
    """Context captured at error time."""
    file_path: str
    function_name: str
    line_number: int
    code_snippet: List[str] = field(default_factory=list)
    local_vars: Dict[str, str] = field(default_factory=dict)
    class_name: Optional[str] = None
    module_name: Optional[str] = None


@dataclass
class SelfHealAttempt:
    """Record of a self-healing attempt."""
    pattern_id: str
    pattern_name: str
    status: SelfHealStatus
    action_taken: Optional[str] = None
    result: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class AugmentTranscript:
    """
    Structured error transcript optimized for Augment.
    
    Designed to provide exactly the context Augment needs to fix errors
    efficiently, with minimal token usage for simple fixes.
    """
    id: str
    timestamp: datetime
    category: ErrorCategory
    level: TranscriptLevel
    
    # Core error info
    error_type: str
    error_message: str
    
    # Location
    primary_file: str
    primary_line: int
    primary_function: str
    
    # Stack trace (for STANDARD+)
    stack_trace: List[str] = field(default_factory=list)
    
    # Context (for FULL)
    contexts: List[ErrorContext] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)
    
    # Self-healing
    self_heal_attempts: List[SelfHealAttempt] = field(default_factory=list)
    suggested_fixes: List[str] = field(default_factory=list)
    
    # Metadata
    project_path: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    severity: str = "ERROR"
    
    def to_minimal(self) -> str:
        """Generate minimal transcript (saves Augment credits)."""
        return f"""## Error: {self.error_type}
**File:** `{self.primary_file}:{self.primary_line}` in `{self.primary_function}()`
**Message:** {self.error_message}
**Category:** {self.category.value}
"""

    def to_standard(self) -> str:
        """Generate standard transcript with stack trace."""
        lines = [self.to_minimal()]
        
        if self.stack_trace:
            lines.append("### Stack Trace")
            lines.append("```")
            lines.extend(self.stack_trace[-10:])  # Last 10 frames
            lines.append("```")
        
        if self.suggested_fixes:
            lines.append("### Suggested Fixes")
            for fix in self.suggested_fixes:
                lines.append(f"- {fix}")
        
        if self.self_heal_attempts:
            lines.append("### Self-Heal Attempts")
            for attempt in self.self_heal_attempts:
                status_icon = "✅" if attempt.status == SelfHealStatus.SUCCESS else "❌"
                lines.append(f"- {status_icon} {attempt.pattern_name}: {attempt.status.value}")

        return "\n".join(lines)

    def to_full(self) -> str:
        """Generate full transcript with code context."""
        lines = [self.to_standard()]

        if self.contexts:
            lines.append("\n### Code Context")
            for ctx in self.contexts[:3]:  # Limit to 3 contexts
                lines.append(f"\n**{ctx.file_path}:{ctx.line_number}** in `{ctx.function_name}()`")
                if ctx.code_snippet:
                    lines.append("```python")
                    lines.extend(ctx.code_snippet)
                    lines.append("```")

        if self.related_files:
            lines.append("\n### Related Files")
            for f in self.related_files[:5]:
                lines.append(f"- `{f}`")

        return "\n".join(lines)

    def to_markdown(self, level: TranscriptLevel = None) -> str:
        """Generate markdown transcript at specified level."""
        level = level or self.level
        if level == TranscriptLevel.MINIMAL:
            return self.to_minimal()
        elif level == TranscriptLevel.STANDARD:
            return self.to_standard()
        else:
            return self.to_full()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "level": self.level.value,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "primary_file": self.primary_file,
            "primary_line": self.primary_line,
            "primary_function": self.primary_function,
            "stack_trace": self.stack_trace,
            "suggested_fixes": self.suggested_fixes,
            "self_heal_attempts": [
                {"pattern": a.pattern_name, "status": a.status.value}
                for a in self.self_heal_attempts
            ],
            "severity": self.severity,
            "tags": self.tags
        }


class ErrorReporter:
    """
    Main error reporting system for Augment integration.

    Features:
    - Automatic error classification
    - Self-healing pattern matching
    - Credit-optimized transcript generation
    - Health report integration
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        health_logger: Any = None,
        self_healer: Any = None
    ):
        self.project_path = project_path
        self.health_logger = health_logger
        self.self_healer = self_healer
        self._transcripts: Dict[str, AugmentTranscript] = {}
        self._next_id = 0
        self._error_patterns: Dict[str, Callable] = {}

        # Register default patterns
        self._register_default_patterns()

        logger.info("ErrorReporter initialized")

    def _generate_id(self) -> str:
        """Generate unique transcript ID."""
        self._next_id += 1
        return f"ERR_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._next_id:04d}"

    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error into category for routing."""
        error_type = type(error).__name__

        category_map = {
            "ImportError": ErrorCategory.IMPORT_ERROR,
            "ModuleNotFoundError": ErrorCategory.IMPORT_ERROR,
            "AttributeError": ErrorCategory.ATTRIBUTE_ERROR,
            "TypeError": ErrorCategory.TYPE_ERROR,
            "ValueError": ErrorCategory.VALUE_ERROR,
            "KeyError": ErrorCategory.KEY_ERROR,
            "FileNotFoundError": ErrorCategory.FILE_NOT_FOUND,
            "PermissionError": ErrorCategory.PERMISSION_ERROR,
            "ConnectionError": ErrorCategory.CONNECTION_ERROR,
            "TimeoutError": ErrorCategory.CONNECTION_ERROR,
        }

        # Check for API errors
        if "api" in str(error).lower() or "rate" in str(error).lower():
            return ErrorCategory.API_ERROR

        # Check for pipeline errors
        if "pipeline" in str(error).lower():
            return ErrorCategory.PIPELINE_ERROR

        return category_map.get(error_type, ErrorCategory.UNKNOWN)

    def _extract_context(self, tb) -> List[ErrorContext]:
        """Extract code context from traceback."""
        contexts = []

        for frame_info in traceback.extract_tb(tb):
            # Get code snippet around the error line
            snippet = []
            try:
                with open(frame_info.filename, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    start = max(0, frame_info.lineno - 3)
                    end = min(len(lines), frame_info.lineno + 2)
                    for i in range(start, end):
                        prefix = ">>> " if i == frame_info.lineno - 1 else "    "
                        snippet.append(f"{prefix}{i+1}: {lines[i].rstrip()}")
            except Exception:
                pass

            contexts.append(ErrorContext(
                file_path=frame_info.filename,
                function_name=frame_info.name,
                line_number=frame_info.lineno,
                code_snippet=snippet
            ))

        return contexts

    def _suggest_fixes(self, error: Exception, category: ErrorCategory) -> List[str]:
        """Generate suggested fixes based on error type."""
        suggestions = []
        error_msg = str(error).lower()

        if category == ErrorCategory.IMPORT_ERROR:
            module = str(error).split("'")[1] if "'" in str(error) else "module"
            suggestions.append(f"Install missing module: `pip install {module}`")
            suggestions.append(f"Check if module is in requirements.txt")
            suggestions.append(f"Verify import path is correct")

        elif category == ErrorCategory.ATTRIBUTE_ERROR:
            suggestions.append("Check if object is properly initialized")
            suggestions.append("Verify attribute name spelling")
            suggestions.append("Check if method exists on the class")

        elif category == ErrorCategory.KEY_ERROR:
            suggestions.append("Check if key exists before accessing")
            suggestions.append("Use .get() with default value")
            suggestions.append("Verify dictionary structure")

        elif category == ErrorCategory.FILE_NOT_FOUND:
            suggestions.append("Check if file path is correct")
            suggestions.append("Ensure directory exists")
            suggestions.append("Verify file permissions")

        elif category == ErrorCategory.API_ERROR:
            if "rate" in error_msg:
                suggestions.append("Implement rate limiting/backoff")
                suggestions.append("Check API quota")
            suggestions.append("Verify API key is valid")
            suggestions.append("Check API endpoint URL")

        elif category == ErrorCategory.TYPE_ERROR:
            suggestions.append("Check argument types match expected")
            suggestions.append("Verify function signature")
            suggestions.append("Add type conversion if needed")

        return suggestions

    def _register_default_patterns(self) -> None:
        """Register default self-healing patterns."""
        # Pattern: Missing directory
        self._error_patterns["missing_dir"] = self._heal_missing_directory
        # Pattern: Missing config key
        self._error_patterns["missing_config"] = self._heal_missing_config
        # Pattern: Import path issue
        self._error_patterns["import_path"] = self._heal_import_path

    def _heal_missing_directory(self, error: Exception, context: Dict) -> SelfHealAttempt:
        """Self-heal missing directory errors."""
        attempt = SelfHealAttempt(
            pattern_id="missing_dir",
            pattern_name="Create Missing Directory",
            status=SelfHealStatus.NOT_ATTEMPTED
        )

        if isinstance(error, FileNotFoundError):
            try:
                # Extract path from error
                path_str = str(error).split("'")[1] if "'" in str(error) else None
                if path_str:
                    path = Path(path_str)
                    if not path.suffix:  # Looks like a directory
                        path.mkdir(parents=True, exist_ok=True)
                        attempt.status = SelfHealStatus.SUCCESS
                        attempt.action_taken = f"Created directory: {path}"
                        logger.info(f"Self-healed: Created directory {path}")
            except Exception as e:
                attempt.status = SelfHealStatus.FAILED
                attempt.result = str(e)

        return attempt

    def _heal_missing_config(self, error: Exception, context: Dict) -> SelfHealAttempt:
        """Self-heal missing config key errors."""
        return SelfHealAttempt(
            pattern_id="missing_config",
            pattern_name="Add Missing Config Key",
            status=SelfHealStatus.DEFERRED,
            result="Config changes require manual review"
        )

    def _heal_import_path(self, error: Exception, context: Dict) -> SelfHealAttempt:
        """Self-heal import path issues."""
        return SelfHealAttempt(
            pattern_id="import_path",
            pattern_name="Fix Import Path",
            status=SelfHealStatus.DEFERRED,
            result="Import fixes require code changes"
        )

    def _try_self_heal(
        self,
        error: Exception,
        category: ErrorCategory,
        context: Dict
    ) -> List[SelfHealAttempt]:
        """Attempt self-healing for known patterns."""
        attempts = []

        # Try relevant patterns based on category
        if category == ErrorCategory.FILE_NOT_FOUND:
            attempts.append(self._heal_missing_directory(error, context))
        elif category == ErrorCategory.KEY_ERROR:
            attempts.append(self._heal_missing_config(error, context))
        elif category == ErrorCategory.IMPORT_ERROR:
            attempts.append(self._heal_import_path(error, context))

        return attempts

    def report(
        self,
        error: Exception,
        source: str = "unknown",
        level: TranscriptLevel = TranscriptLevel.STANDARD,
        context: Dict[str, Any] = None,
        try_self_heal: bool = True
    ) -> AugmentTranscript:
        """
        Generate an error report transcript.

        Args:
            error: The exception to report
            source: Source identifier (e.g., "pipeline.writer")
            level: Detail level for transcript
            context: Additional context
            try_self_heal: Whether to attempt self-healing

        Returns:
            AugmentTranscript ready for Augment consumption
        """
        context = context or {}

        # Get exception info
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_tb is None:
            # Error passed directly, not from except block
            exc_tb = error.__traceback__

        # Classify error
        category = self._classify_error(error)

        # Extract stack trace
        stack_trace = traceback.format_exception(type(error), error, exc_tb)

        # Get primary location
        tb_list = traceback.extract_tb(exc_tb) if exc_tb else []
        if tb_list:
            primary = tb_list[-1]
            primary_file = primary.filename
            primary_line = primary.lineno
            primary_function = primary.name
        else:
            primary_file = "unknown"
            primary_line = 0
            primary_function = "unknown"

        # Try self-healing
        heal_attempts = []
        if try_self_heal:
            heal_attempts = self._try_self_heal(error, category, context)

        # Generate suggestions
        suggestions = self._suggest_fixes(error, category)

        # Extract code contexts for FULL level
        contexts = []
        if level == TranscriptLevel.FULL and exc_tb:
            contexts = self._extract_context(exc_tb)

        # Create transcript
        transcript = AugmentTranscript(
            id=self._generate_id(),
            timestamp=datetime.now(),
            category=category,
            level=level,
            error_type=type(error).__name__,
            error_message=str(error),
            primary_file=primary_file,
            primary_line=primary_line,
            primary_function=primary_function,
            stack_trace=[line.strip() for line in stack_trace],
            contexts=contexts,
            self_heal_attempts=heal_attempts,
            suggested_fixes=suggestions,
            project_path=str(self.project_path) if self.project_path else None,
            tags=[source, category.value],
            severity="CRITICAL" if category in [ErrorCategory.PIPELINE_ERROR] else "ERROR"
        )

        # Store transcript
        self._transcripts[transcript.id] = transcript

        # Log to health logger if available
        if self.health_logger:
            self.health_logger.log_error(error, source, context)

        logger.warning(f"Error reported: {transcript.id} [{category.value}] {error}")

        return transcript

    def get_transcript(self, transcript_id: str) -> Optional[AugmentTranscript]:
        """Get a transcript by ID."""
        return self._transcripts.get(transcript_id)

    def get_recent(self, limit: int = 10) -> List[AugmentTranscript]:
        """Get recent transcripts."""
        sorted_transcripts = sorted(
            self._transcripts.values(),
            key=lambda t: t.timestamp,
            reverse=True
        )
        return sorted_transcripts[:limit]

    def export_for_augment(
        self,
        transcript_id: str,
        level: TranscriptLevel = None
    ) -> str:
        """
        Export transcript in Augment-optimized format.

        This generates a markdown document that Augment can quickly
        parse to understand and fix the error.
        """
        transcript = self._transcripts.get(transcript_id)
        if not transcript:
            return f"Transcript {transcript_id} not found"

        level = level or transcript.level

        header = f"""# Augment Error Report
**ID:** {transcript.id}
**Time:** {transcript.timestamp.isoformat()}
**Severity:** {transcript.severity}
**Self-Heal Status:** {"✅ Resolved" if any(a.status == SelfHealStatus.SUCCESS for a in transcript.self_heal_attempts) else "❌ Needs Fix"}

---

"""
        return header + transcript.to_markdown(level)

    def save_report(self, transcript_id: str, output_path: Path = None) -> Path:
        """Save transcript to file for Augment access."""
        transcript = self._transcripts.get(transcript_id)
        if not transcript:
            raise ValueError(f"Transcript {transcript_id} not found")

        if output_path is None:
            if self.project_path:
                output_dir = self.project_path / ".health" / "error_reports"
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"{transcript_id}.md"
            else:
                output_path = Path(f"{transcript_id}.md")

        content = self.export_for_augment(transcript_id)
        output_path.write_text(content, encoding='utf-8')

        logger.info(f"Error report saved: {output_path}")
        return output_path

