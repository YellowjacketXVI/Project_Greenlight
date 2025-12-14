"""
Symbolic Registry - Dynamic Symbol Learning & Growth System

Wraps the Agnostic_Core_OS NotationLibrary and adds:
1. Dynamic symbol learning from project context
2. Self-healing symbol registration
3. LLM-driven symbol discovery
4. Project-specific symbol persistence
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Try to import from Agnostic_Core_OS
try:
    from Agnostic_Core_OS.procedural.notation_library import (
        NotationLibrary, NotationEntry, NotationType, NotationScope
    )
    HAS_NOTATION_LIBRARY = True
except ImportError:
    HAS_NOTATION_LIBRARY = False
    logger.warning("NotationLibrary not available - using standalone mode")


class SymbolOrigin(Enum):
    """How a symbol was discovered/created."""
    CORE = "core"           # Built-in core symbols
    PROJECT = "project"     # Discovered from project files
    USER = "user"           # User-defined
    LLM = "llm"             # Discovered by LLM
    HEALED = "healed"       # Created during self-healing
    IMPORTED = "imported"   # Imported from another project


@dataclass
class SymbolDefinition:
    """A symbol definition with learning metadata."""
    symbol: str
    notation_type: str  # tag, scope, command, query, etc.
    scope: str
    definition: str
    pattern: str
    examples: List[str] = field(default_factory=list)
    origin: SymbolOrigin = SymbolOrigin.PROJECT
    confidence: float = 1.0  # How confident we are in this symbol
    usage_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "notation_type": self.notation_type,
            "scope": self.scope,
            "definition": self.definition,
            "pattern": self.pattern,
            "examples": self.examples,
            "origin": self.origin.value,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbolDefinition":
        return cls(
            symbol=data["symbol"],
            notation_type=data["notation_type"],
            scope=data["scope"],
            definition=data["definition"],
            pattern=data["pattern"],
            examples=data.get("examples", []),
            origin=SymbolOrigin(data.get("origin", "project")),
            confidence=data.get("confidence", 1.0),
            usage_count=data.get("usage_count", 0),
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            metadata=data.get("metadata", {})
        )


@dataclass
class LearningEvent:
    """Record of a symbol learning event."""
    symbol: str
    event_type: str  # discovered, healed, updated, deprecated
    source: str
    details: str
    timestamp: datetime = field(default_factory=datetime.now)


class SymbolicRegistry:
    """
    Dynamic Symbolic Registry with learning capabilities.

    Features:
    - Wraps NotationLibrary for core symbol storage
    - Project-specific symbol persistence
    - Dynamic learning from project context
    - Self-healing symbol registration
    - Usage tracking for symbol importance
    - LLM cypher generation
    """

    # Core symbol prefixes and their meanings
    SYMBOL_PREFIXES = {
        "@": ("tag", "Entity reference (character, location, prop, file)"),
        "#": ("scope", "Scope/category filter"),
        ">": ("command", "Execute command/process"),
        "?": ("query", "Natural language query"),
        "+": ("include", "Include in results"),
        "-": ("exclude", "Exclude from results"),
        "~": ("similar", "Semantic similarity search"),
        "!": ("alert", "Alert/warning marker"),
        "*": ("wildcard", "Wildcard/any match"),
    }

    def __init__(self, project_path: Path, storage_dir: Path = None):
        self.project_path = Path(project_path)
        self.storage_dir = storage_dir or (self.project_path / ".symbolic")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Symbol storage
        self._symbols: Dict[str, SymbolDefinition] = {}
        self._learning_log: List[LearningEvent] = []

        # Indexes for fast lookup
        self._prefix_index: Dict[str, Set[str]] = {p: set() for p in self.SYMBOL_PREFIXES}
        self._scope_index: Dict[str, Set[str]] = {}
        self._type_index: Dict[str, Set[str]] = {}

        # Core notation library (if available)
        self._notation_library: Optional[NotationLibrary] = None
        if HAS_NOTATION_LIBRARY:
            self._notation_library = NotationLibrary(self.storage_dir / "notation_lib")

        # Load existing symbols
        self._load_symbols()

        # Initialize core symbols
        self._init_core_symbols()

        logger.info(f"SymbolicRegistry initialized with {len(self._symbols)} symbols")

    def _load_symbols(self) -> None:
        """Load symbols from persistent storage."""
        symbols_file = self.storage_dir / "symbols.json"
        if symbols_file.exists():
            try:
                with open(symbols_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for sym_data in data.get("symbols", []):
                    sym = SymbolDefinition.from_dict(sym_data)
                    self._symbols[sym.symbol] = sym
                    self._index_symbol(sym)

                logger.info(f"Loaded {len(self._symbols)} symbols from storage")
            except Exception as e:
                logger.error(f"Failed to load symbols: {e}")

    def _save_symbols(self) -> None:
        """Save symbols to persistent storage."""
        symbols_file = self.storage_dir / "symbols.json"
        try:
            data = {
                "project": self.project_path.name,
                "updated_at": datetime.now().isoformat(),
                "symbol_count": len(self._symbols),
                "symbols": [s.to_dict() for s in self._symbols.values()]
            }
            with open(symbols_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save symbols: {e}")

    def _index_symbol(self, sym: SymbolDefinition) -> None:
        """Add symbol to indexes."""
        # Prefix index
        if sym.symbol and sym.symbol[0] in self._prefix_index:
            self._prefix_index[sym.symbol[0]].add(sym.symbol)

        # Scope index
        if sym.scope not in self._scope_index:
            self._scope_index[sym.scope] = set()
        self._scope_index[sym.scope].add(sym.symbol)

        # Type index
        if sym.notation_type not in self._type_index:
            self._type_index[sym.notation_type] = set()
        self._type_index[sym.notation_type].add(sym.symbol)

    # Scene.Frame.Camera Notation Patterns (CORE SYSTEM)
    # Canonical format per .augment-guidelines:
    #   Scene: {scene_number} (e.g., 1, 2, 8)
    #   Frame: {scene}.{frame} (e.g., 1.1, 2.3)
    #   Camera: {scene}.{frame}.c{letter} (e.g., 1.1.cA, 2.3.cB)
    SCENE_FRAME_CAMERA_PATTERNS = {
        # Raw ID patterns (without brackets)
        "full_id": r"(\d+)\.(\d+)\.c([A-Z])",           # 1.2.cA (raw camera ID)
        "scene_frame": r"(\d+)\.(\d+)",                  # 1.2 (raw frame ID)
        "scene_id": r"(\d+)",                            # 1 (raw scene ID)
        # Bracketed patterns (for parsing formatted output)
        "full_id_bracketed": r"\[(\d+)\.(\d+)\.c([A-Z])\]",  # [1.2.cA]
        "camera_block": r"\[(\d+\.\d+\.c[A-Z])\]\s*\(([^)]+)\)",  # [1.1.cA] (Wide)
        # Markers
        "scene_marker": r"##\s*Scene\s+(\d+):",          # ## Scene 1:
        "beat_marker": r"##\s*Beat:\s*scene\.(\d+)\.(\d+)",  # ## Beat: scene.1.01
        # Delimiters
        "frame_chunk_start": r"\(/scene_frame_chunk_start/\)",
        "frame_chunk_end": r"\(/scene_frame_chunk_end/\)",
    }

    def _init_core_symbols(self) -> None:
        """Initialize core built-in symbols."""
        core_symbols = [
            # Directory scopes
            ("#WORLD_BIBLE", "scope", "global", "World bible directory scope", "#WORLD_BIBLE"),
            ("#CHARACTERS", "scope", "global", "Characters directory scope", "#CHARACTERS"),
            ("#LOCATIONS", "scope", "global", "Locations directory scope", "#LOCATIONS"),
            ("#SCRIPTS", "scope", "global", "Scripts directory scope", "#SCRIPTS"),
            ("#STORY_DOCS", "scope", "global", "Story documents scope", "#STORY_DOCS"),
            ("#STORYBOARD", "scope", "global", "Storyboard output scope", "#STORYBOARD"),

            # Core files
            ("@PITCH", "tag", "global", "Project pitch document", "@PITCH"),
            ("@WORLD_CONFIG", "tag", "global", "World configuration file", "@WORLD_CONFIG"),
            ("@STYLE_GUIDE", "tag", "global", "Visual style guide", "@STYLE_GUIDE"),

            # Commands
            (">run_writer", "command", "global", "Run the Writer pipeline", ">run_writer"),
            (">run_director", "command", "global", "Run the Director pipeline", ">run_director"),
            (">diagnose", "command", "global", "Run project diagnostics", ">diagnose"),
            (">heal", "command", "global", "Attempt self-healing", ">heal"),
            (">index", "command", "global", "Re-index project", ">index"),
            (">validate_notation", "command", "global", "Validate scene.frame.camera notation", ">validate_notation"),

            # Queries
            ("?help", "query", "global", "Get help information", "?help"),
            ("?status", "query", "global", "Get project status", "?status"),

            # Scene.Frame.Camera Notation (CORE)
            ("@SCENE", "notation", "directing", "Scene reference: {scene_number} e.g., 1, 2, 8", r"\d+"),
            ("@FRAME", "notation", "directing", "Frame reference: {scene}.{frame} e.g., 1.1, 2.3", r"\d+\.\d+"),
            ("@CAMERA", "notation", "directing", "Camera reference: {scene}.{frame}.c{letter} e.g., 1.1.cA", r"\d+\.\d+\.c[A-Z]"),
        ]

        for symbol, ntype, scope, definition, pattern in core_symbols:
            if symbol not in self._symbols:
                self.register(
                    symbol=symbol,
                    notation_type=ntype,
                    scope=scope,
                    definition=definition,
                    pattern=pattern,
                    origin=SymbolOrigin.CORE,
                    confidence=1.0
                )

    def parse_scene_frame_camera(self, notation: str) -> Optional[Dict[str, Any]]:
        """
        Parse a scene.frame.camera notation string.

        Args:
            notation: String like "1.2.cA" or "1.2" or just "1"

        Returns:
            Dict with scene, frame, camera components or None if invalid
        """
        import re

        # Try full notation: 1.2.cA
        full_match = re.match(self.SCENE_FRAME_CAMERA_PATTERNS["full_id"], notation)
        if full_match:
            return {
                "scene": int(full_match.group(1)),
                "frame": int(full_match.group(2)),
                "camera": full_match.group(3),
                "full_id": notation,
                "type": "camera"
            }

        # Try scene.frame: 1.2
        sf_match = re.match(self.SCENE_FRAME_CAMERA_PATTERNS["scene_frame"], notation)
        if sf_match:
            return {
                "scene": int(sf_match.group(1)),
                "frame": int(sf_match.group(2)),
                "camera": None,
                "full_id": notation,
                "type": "frame"
            }

        # Try just scene number
        if notation.isdigit():
            return {
                "scene": int(notation),
                "frame": None,
                "camera": None,
                "full_id": notation,
                "type": "scene"
            }

        return None

    def format_camera_id(self, scene: int, frame: int, camera_letter: str) -> str:
        """Format a camera ID in standard notation: scene.frame.cX"""
        return f"{scene}.{frame}.c{camera_letter.upper()}"

    def format_frame_id(self, scene: int, frame: int) -> str:
        """Format a frame ID in standard notation: scene.frame"""
        return f"{scene}.{frame}"

    def validate_notation(self, text: str) -> Dict[str, Any]:
        """
        Validate scene.frame.camera notation in text.

        Returns validation report with any issues found.
        """
        import re

        issues = []
        valid_notations = []

        # Find all camera blocks
        camera_blocks = re.findall(self.SCENE_FRAME_CAMERA_PATTERNS["camera_block"], text)
        for notation, shot_type in camera_blocks:
            parsed = self.parse_scene_frame_camera(notation)
            if parsed:
                valid_notations.append({
                    "notation": notation,
                    "shot_type": shot_type,
                    **parsed
                })
            else:
                issues.append(f"Invalid camera notation: {notation}")

        # Check for old-style frame markers that should be converted
        old_frame_pattern = r"\{frame_(\d+)\.(\d+)\}"
        old_frames = re.findall(old_frame_pattern, text)
        for scene, frame in old_frames:
            issues.append(f"Old-style frame marker found: {{frame_{scene}.{frame}}} - should use [{scene}.{frame}.cA] format")

        return {
            "valid": len(issues) == 0,
            "notation_count": len(valid_notations),
            "notations": valid_notations,
            "issues": issues,
            "issue_count": len(issues)
        }

    def register(
        self,
        symbol: str,
        notation_type: str,
        scope: str,
        definition: str,
        pattern: str = None,
        examples: List[str] = None,
        origin: SymbolOrigin = SymbolOrigin.PROJECT,
        confidence: float = 1.0,
        metadata: Dict[str, Any] = None
    ) -> SymbolDefinition:
        """
        Register a new symbol in the registry.

        This is the core learning function - symbols registered here
        become part of the project's symbolic language.
        """
        # Check if already exists
        if symbol in self._symbols:
            existing = self._symbols[symbol]
            # Update usage count
            existing.usage_count += 1
            existing.last_used = datetime.now()
            self._save_symbols()
            return existing

        # Create new symbol
        sym = SymbolDefinition(
            symbol=symbol,
            notation_type=notation_type,
            scope=scope,
            definition=definition,
            pattern=pattern or symbol,
            examples=examples or [symbol],
            origin=origin,
            confidence=confidence,
            metadata=metadata or {}
        )

        self._symbols[symbol] = sym
        self._index_symbol(sym)

        # Log learning event
        self._learning_log.append(LearningEvent(
            symbol=symbol,
            event_type="discovered",
            source=origin.value,
            details=f"Registered: {definition}"
        ))

        # Also register in NotationLibrary if available
        if self._notation_library and HAS_NOTATION_LIBRARY:
            try:
                ntype = NotationType(notation_type) if notation_type in [e.value for e in NotationType] else NotationType.CUSTOM
                nscope = NotationScope(scope) if scope in [e.value for e in NotationScope] else NotationScope.PROJECT
                self._notation_library.register(
                    symbol=symbol,
                    notation_type=ntype,
                    scope=nscope,
                    definition=definition,
                    pattern=pattern or symbol,
                    examples=examples or [symbol]
                )
            except Exception as e:
                logger.debug(f"Failed to register in NotationLibrary: {e}")

        self._save_symbols()
        logger.info(f"Registered symbol: {symbol} ({origin.value})")
        return sym

    def get(self, symbol: str) -> Optional[SymbolDefinition]:
        """Get a symbol by its notation."""
        sym = self._symbols.get(symbol)
        if sym:
            sym.usage_count += 1
            sym.last_used = datetime.now()
        return sym

    def exists(self, symbol: str) -> bool:
        """Check if a symbol exists."""
        return symbol in self._symbols

    def get_by_prefix(self, prefix: str) -> List[SymbolDefinition]:
        """Get all symbols with a given prefix."""
        symbols = self._prefix_index.get(prefix, set())
        return [self._symbols[s] for s in symbols if s in self._symbols]

    def get_by_scope(self, scope: str) -> List[SymbolDefinition]:
        """Get all symbols in a given scope."""
        symbols = self._scope_index.get(scope, set())
        return [self._symbols[s] for s in symbols if s in self._symbols]

    def get_by_type(self, notation_type: str) -> List[SymbolDefinition]:
        """Get all symbols of a given type."""
        symbols = self._type_index.get(notation_type, set())
        return [self._symbols[s] for s in symbols if s in self._symbols]

    def learn_from_text(self, text: str, source: str = "text") -> List[SymbolDefinition]:
        """
        Learn new symbols from text content.

        Scans text for potential symbols and registers them.
        """
        import re
        learned = []

        # Pattern to find symbolic notation
        patterns = [
            (r'@([A-Z][A-Z0-9_]+)', 'tag'),
            (r'#([A-Z][A-Z0-9_]+)', 'scope'),
            (r'>([a-z][a-z0-9_]+)', 'command'),
        ]

        for pattern, ntype in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                symbol = f"{'@' if ntype == 'tag' else '#' if ntype == 'scope' else '>'}{match}"
                if not self.exists(symbol):
                    sym = self.register(
                        symbol=symbol,
                        notation_type=ntype,
                        scope="project",
                        definition=f"Auto-discovered {ntype}: {match}",
                        origin=SymbolOrigin.LLM,
                        confidence=0.7
                    )
                    learned.append(sym)

        return learned

    def heal_missing_symbol(self, symbol: str, context: str = "") -> Optional[SymbolDefinition]:
        """
        Self-healing: Register a missing symbol that was referenced.

        Called when a symbol is used but not found in the registry.
        """
        # Determine type from prefix
        prefix = symbol[0] if symbol else ""
        ntype, desc = self.SYMBOL_PREFIXES.get(prefix, ("custom", "Custom symbol"))

        # Extract the name part
        name = symbol[1:] if prefix in self.SYMBOL_PREFIXES else symbol

        sym = self.register(
            symbol=symbol,
            notation_type=ntype,
            scope="project",
            definition=f"Auto-healed {ntype}: {name}",
            origin=SymbolOrigin.HEALED,
            confidence=0.5,
            metadata={"heal_context": context[:200] if context else ""}
        )

        self._learning_log.append(LearningEvent(
            symbol=symbol,
            event_type="healed",
            source="self_heal",
            details=f"Missing symbol auto-registered from context"
        ))

        logger.info(f"Self-healed missing symbol: {symbol}")
        return sym

    def get_cypher_prompt(self) -> str:
        """
        Generate the LLM Cypher - teaching document for symbolic notation.

        This is the key document that teaches LLMs how to use the symbolic language.
        """
        lines = [
            "# SYMBOLIC NOTATION CYPHER",
            "",
            "This document teaches you how to use the symbolic notation system.",
            "",
            "## Symbol Prefixes",
            "",
            "| Prefix | Type | Meaning |",
            "|--------|------|---------|",
        ]

        for prefix, (ntype, meaning) in self.SYMBOL_PREFIXES.items():
            lines.append(f"| `{prefix}` | {ntype} | {meaning} |")

        lines.extend([
            "",
            "## How to Use Symbols",
            "",
            "### Entity References (@)",
            "Use `@` to reference specific entities:",
            "- `@CHAR_MEI` - Reference character Mei",
            "- `@LOC_TEAHOUSE` - Reference location Teahouse",
            "- `@PITCH` - Reference the pitch document",
            "",
            "### Scope Filters (#)",
            "Use `#` to filter by scope/category:",
            "- `#WORLD_BIBLE` - Search in world bible",
            "- `#CHARACTERS` - Search in characters",
            "- `@CHAR_MEI #STORY` - Find Mei in story context",
            "",
            "### Commands (>)",
            "Use `>` to execute processes:",
            "- `>run_writer` - Run the Writer pipeline",
            "- `>diagnose` - Run diagnostics",
            "- `>heal` - Attempt self-healing",
            "",
            "### Queries (?)",
            "Use `?` for natural language queries:",
            "- `?\"who is the protagonist\"` - Ask about protagonist",
            "- `?help` - Get help",
            "",
            "### Modifiers (+, -, ~)",
            "- `+include` - Include in results",
            "- `-exclude` - Exclude from results",
            "- `~\"similar text\"` - Semantic similarity",
            "",
            "## Combining Symbols",
            "",
            "Symbols can be combined for precise queries:",
            "```",
            "@CHAR_MEI #STORY +relationships",
            "```",
            "This finds character Mei in story scope, including relationships.",
            "",
            "## Context Engine Integration",
            "",
            "When you need information, use symbolic queries:",
            "1. Identify what you need (character, location, scene, etc.)",
            "2. Form the symbolic query with appropriate prefix",
            "3. Add scope filter if needed",
            "4. The context engine will retrieve relevant content",
            "",
            "## Self-Healing",
            "",
            "If you reference a symbol that doesn't exist:",
            "1. The system will auto-register it",
            "2. Mark it as 'healed' with lower confidence",
            "3. Log the event for review",
            "",
        ])

        # Add project-specific symbols
        project_symbols = [s for s in self._symbols.values() if s.origin != SymbolOrigin.CORE]
        if project_symbols:
            lines.extend([
                "## Project Symbols",
                "",
                "| Symbol | Type | Definition |",
                "|--------|------|------------|",
            ])
            for sym in sorted(project_symbols, key=lambda x: x.symbol):
                lines.append(f"| `{sym.symbol}` | {sym.notation_type} | {sym.definition[:50]} |")

        return "\n".join(lines)

    def get_symbol_glossary(self) -> str:
        """Generate a compact glossary of all symbols."""
        lines = ["# SYMBOL GLOSSARY", ""]

        # Group by type
        by_type: Dict[str, List[SymbolDefinition]] = {}
        for sym in self._symbols.values():
            if sym.notation_type not in by_type:
                by_type[sym.notation_type] = []
            by_type[sym.notation_type].append(sym)

        for ntype, symbols in sorted(by_type.items()):
            lines.append(f"## {ntype.upper()}")
            for sym in sorted(symbols, key=lambda x: x.symbol):
                lines.append(f"- `{sym.symbol}`: {sym.definition[:60]}")
            lines.append("")

        return "\n".join(lines)

    def get_learning_log(self, limit: int = 50) -> List[LearningEvent]:
        """Get recent learning events."""
        return self._learning_log[-limit:]

    def export_for_training(self) -> Dict[str, Any]:
        """Export symbols in a format suitable for LLM training."""
        return {
            "project": self.project_path.name,
            "exported_at": datetime.now().isoformat(),
            "symbol_count": len(self._symbols),
            "prefixes": self.SYMBOL_PREFIXES,
            "symbols": [s.to_dict() for s in self._symbols.values()],
            "learning_events": [
                {
                    "symbol": e.symbol,
                    "event_type": e.event_type,
                    "source": e.source,
                    "details": e.details,
                    "timestamp": e.timestamp.isoformat()
                }
                for e in self._learning_log
            ]
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        by_origin = {}
        for sym in self._symbols.values():
            origin = sym.origin.value
            by_origin[origin] = by_origin.get(origin, 0) + 1

        return {
            "total_symbols": len(self._symbols),
            "by_origin": by_origin,
            "by_type": {k: len(v) for k, v in self._type_index.items()},
            "learning_events": len(self._learning_log),
            "healed_count": sum(1 for s in self._symbols.values() if s.origin == SymbolOrigin.HEALED)
        }

