"""
Token-Efficient Context Logger - Safe Efficient Token Context Log Reports

Generates system prompts and context reports optimized for token efficiency.
Tracks token usage and provides compressed context for LLM interactions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime
import json
from pathlib import Path


class LogLevel(Enum):
    """Log levels for context entries."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CompressionLevel(Enum):
    """Compression levels for token efficiency."""
    NONE = 0        # Full context
    LOW = 1         # Remove whitespace
    MEDIUM = 2      # Abbreviate common terms
    HIGH = 3        # Summarize to key points
    EXTREME = 4     # Minimal notation only


@dataclass
class ContextEntry:
    """A single context log entry."""
    key: str
    value: Any
    notation: str
    level: LogLevel = LogLevel.INFO
    tokens: int = 0
    compressed: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": str(self.value)[:200],
            "notation": self.notation,
            "level": self.level.value,
            "tokens": self.tokens,
            "compressed": self.compressed,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ContextReport:
    """A compiled context report."""
    report_id: str
    entries: List[ContextEntry]
    total_tokens: int
    compressed_tokens: int
    compression_level: CompressionLevel
    system_prompt: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "entries": [e.to_dict() for e in self.entries],
            "total_tokens": self.total_tokens,
            "compressed_tokens": self.compressed_tokens,
            "compression_level": self.compression_level.value,
            "system_prompt": self.system_prompt[:500],
            "timestamp": self.timestamp.isoformat()
        }
    
    def get_efficiency(self) -> float:
        """Get compression efficiency ratio."""
        if self.total_tokens == 0:
            return 1.0
        return 1.0 - (self.compressed_tokens / self.total_tokens)


class TokenEfficientLogger:
    """
    Token-Efficient Context Logger.
    
    Manages context logging with token optimization:
    - Tracks token usage per entry
    - Compresses context based on level
    - Generates optimized system prompts
    - Produces developer-readable reports
    
    Example:
        logger = TokenEfficientLogger(max_tokens=4096)
        logger.log("character", char_data, "@CHAR_PROTAGONIST")
        logger.log("location", loc_data, "@LOC_MAIN_STREET")
        
        report = logger.generate_report(CompressionLevel.MEDIUM)
        system_prompt = report.system_prompt
    """
    
    # Abbreviation mappings for compression
    ABBREVIATIONS = {
        "character": "char",
        "location": "loc",
        "description": "desc",
        "motivation": "motiv",
        "background": "bg",
        "relationship": "rel",
        "appearance": "appear",
        "personality": "pers",
        "objective": "obj",
        "conflict": "conf",
        "resolution": "res",
        "dialogue": "dial",
        "action": "act",
        "scene": "sc",
        "frame": "fr",
        "camera": "cam",
        "position": "pos",
        "lighting": "light",
    }
    
    def __init__(
        self,
        max_tokens: int = 8192,
        log_dir: Optional[Path] = None,
        default_compression: CompressionLevel = CompressionLevel.MEDIUM
    ):
        """Initialize the token-efficient logger."""
        self.max_tokens = max_tokens
        self.log_dir = log_dir
        self.default_compression = default_compression
        
        self._entries: List[ContextEntry] = []
        self._next_report_id = 0
        
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: ~4 chars per token)."""
        return len(str(text)) // 4 + 1
    
    def _compress(self, text: str, level: CompressionLevel) -> str:
        """Compress text based on compression level."""
        if level == CompressionLevel.NONE:
            return text
        
        result = str(text)
        
        if level.value >= CompressionLevel.LOW.value:
            # Remove extra whitespace
            result = " ".join(result.split())
        
        if level.value >= CompressionLevel.MEDIUM.value:
            # Apply abbreviations
            for full, abbr in self.ABBREVIATIONS.items():
                result = result.replace(full, abbr)
                result = result.replace(full.title(), abbr.title())
        
        if level.value >= CompressionLevel.HIGH.value:
            # Truncate to first 100 chars
            if len(result) > 100:
                result = result[:97] + "..."
        
        if level.value >= CompressionLevel.EXTREME.value:
            # Keep only first 50 chars
            if len(result) > 50:
                result = result[:47] + "..."

        return result

    def log(
        self,
        key: str,
        value: Any,
        notation: str,
        level: LogLevel = LogLevel.INFO
    ) -> ContextEntry:
        """
        Log a context entry.

        Args:
            key: Entry key/name
            value: Entry value (any type)
            notation: Vector notation (e.g., @CHAR_PROTAGONIST)
            level: Log level

        Returns:
            Created ContextEntry
        """
        text = str(value)
        tokens = self._estimate_tokens(text)
        compressed = self._compress(text, self.default_compression)

        entry = ContextEntry(
            key=key,
            value=value,
            notation=notation,
            level=level,
            tokens=tokens,
            compressed=compressed
        )
        self._entries.append(entry)
        return entry

    def generate_report(
        self,
        compression: Optional[CompressionLevel] = None,
        max_entries: Optional[int] = None,
        levels: Optional[List[LogLevel]] = None
    ) -> ContextReport:
        """
        Generate a context report.

        Args:
            compression: Override compression level
            max_entries: Limit number of entries
            levels: Filter by log levels

        Returns:
            ContextReport with system prompt
        """
        comp_level = compression or self.default_compression

        # Filter entries
        entries = self._entries
        if levels:
            entries = [e for e in entries if e.level in levels]
        if max_entries:
            entries = entries[-max_entries:]

        # Calculate tokens
        total_tokens = sum(e.tokens for e in entries)

        # Compress entries
        compressed_entries = []
        compressed_tokens = 0
        for entry in entries:
            compressed = self._compress(str(entry.value), comp_level)
            entry.compressed = compressed
            compressed_tokens += self._estimate_tokens(compressed)
            compressed_entries.append(entry)

        # Generate system prompt
        system_prompt = self._build_system_prompt(compressed_entries, comp_level)

        self._next_report_id += 1
        report = ContextReport(
            report_id=f"ctx_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._next_report_id:04d}",
            entries=compressed_entries,
            total_tokens=total_tokens,
            compressed_tokens=compressed_tokens,
            compression_level=comp_level,
            system_prompt=system_prompt
        )

        return report

    def _build_system_prompt(
        self,
        entries: List[ContextEntry],
        compression: CompressionLevel
    ) -> str:
        """Build an optimized system prompt from entries."""
        lines = ["## Context (Token-Optimized)"]

        for entry in entries:
            if compression.value >= CompressionLevel.HIGH.value:
                lines.append(f"- {entry.notation}: {entry.compressed}")
            else:
                lines.append(f"- {entry.notation} ({entry.key}): {entry.compressed}")

        return "\n".join(lines)

    def get_token_usage(self) -> Dict[str, Any]:
        """Get current token usage statistics."""
        total = sum(e.tokens for e in self._entries)
        compressed = sum(self._estimate_tokens(e.compressed) for e in self._entries)

        return {
            "total_entries": len(self._entries),
            "total_tokens": total,
            "compressed_tokens": compressed,
            "efficiency": 1.0 - (compressed / total) if total > 0 else 1.0,
            "remaining_budget": self.max_tokens - compressed,
            "over_budget": compressed > self.max_tokens
        }

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()

    def save_report(self, report: ContextReport, filename: Optional[str] = None) -> Optional[Path]:
        """Save report to disk."""
        if not self.log_dir:
            return None

        fname = filename or f"{report.report_id}.json"
        path = self.log_dir / fname

        with open(path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)

        return path

    def generate_developer_report(self) -> str:
        """Generate a human-readable developer report."""
        usage = self.get_token_usage()

        lines = [
            "# Token-Efficient Context Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Token Usage",
            f"- Total Entries: {usage['total_entries']}",
            f"- Raw Tokens: {usage['total_tokens']}",
            f"- Compressed Tokens: {usage['compressed_tokens']}",
            f"- Efficiency: {usage['efficiency']:.1%}",
            f"- Budget Remaining: {usage['remaining_budget']}",
            "",
            "## Entries",
        ]

        for entry in self._entries:
            lines.append(f"### {entry.notation}")
            lines.append(f"- Key: {entry.key}")
            lines.append(f"- Level: {entry.level.value}")
            lines.append(f"- Tokens: {entry.tokens}")
            lines.append(f"- Value: {str(entry.value)[:100]}...")
            lines.append("")

        return "\n".join(lines)
