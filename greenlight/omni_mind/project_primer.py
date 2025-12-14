"""
Project Primer - Symbolic Index & LLM Cypher System

Provides:
1. Symbolic notation index for quick project navigation
2. Cypher document teaching LLMs how to use context engine
3. Self-healing path detection and updates
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SymbolType(Enum):
    """Types of symbolic entries in the index."""
    DIRECTORY = "dir"
    FILE = "file"
    CHARACTER = "char"
    LOCATION = "loc"
    PROP = "prop"
    CONCEPT = "concept"
    SCENE = "scene"
    BEAT = "beat"
    PROCESS = "process"
    TAG = "tag"


class PathStatus(Enum):
    """Status of indexed paths."""
    VALID = "valid"
    MISSING = "missing"
    STALE = "stale"
    NEW = "new"


@dataclass
class SymbolicEntry:
    """A single entry in the symbolic index."""
    symbol: str  # e.g., @CHAR_MEI, #WORLD_BIBLE, >run_writer
    path: str  # Relative path from project root
    symbol_type: SymbolType
    description: str
    status: PathStatus = PathStatus.VALID
    last_verified: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "path": self.path,
            "type": self.symbol_type.value,
            "description": self.description,
            "status": self.status.value,
            "last_verified": self.last_verified.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbolicEntry":
        return cls(
            symbol=data["symbol"],
            path=data["path"],
            symbol_type=SymbolType(data["type"]),
            description=data["description"],
            status=PathStatus(data.get("status", "valid")),
            last_verified=datetime.fromisoformat(data.get("last_verified", datetime.now().isoformat())),
            metadata=data.get("metadata", {})
        )


@dataclass
class BrokenPath:
    """Record of a broken path for self-healing."""
    symbol: str
    expected_path: str
    error: str
    detected_at: datetime = field(default_factory=datetime.now)
    healed: bool = False
    healed_path: Optional[str] = None


class ProjectPrimer:
    """
    Project Primer System - Symbolic Index & LLM Cypher

    Creates a symbolic notation index for quick project navigation
    and teaches LLMs how to use the context engine and OmniMind.
    """

    # Standard project directories with symbolic prefixes
    STANDARD_DIRECTORIES = {
        "#WORLD_BIBLE": ("world_bible", "World configuration, characters, locations, props"),
        "#CHARACTERS": ("characters", "Character definition files"),
        "#LOCATIONS": ("locations", "Location definition files"),
        "#SCRIPTS": ("scripts", "Story scripts and drafts"),
        "#STORY_DOCS": ("story_documents", "Generated story content"),
        "#STORYBOARD": ("storyboard_output", "Storyboard frames and prompts"),
        "#BEATS": ("beats", "Story beat breakdowns"),
        "#ASSETS": ("assets", "Visual assets and references"),
        "#REFERENCES": ("references", "Reference materials"),
        "#HEALTH": (".health", "Project health reports"),
    }

    # Standard files with symbolic prefixes
    STANDARD_FILES = {
        "@PITCH": ("world_bible/pitch.md", "Core story pitch and concept"),
        "@WORLD_CONFIG": ("world_bible/world_config.json", "World bible configuration"),
        "@STYLE_GUIDE": ("world_bible/style_guide.md", "Visual style guidelines"),
        "@PROJECT_CONFIG": ("project.json", "Project configuration"),
    }

    # Process symbols
    PROCESS_SYMBOLS = {
        ">run_writer": ("Run the Writer pipeline to generate story content", "writer"),
        ">run_director": ("Run the Director pipeline to create storyboards", "director"),
        ">diagnose": ("Run project diagnostics and health check", "diagnose"),
        ">heal": ("Attempt self-healing on detected issues", "heal"),
        ">validate_tags": ("Validate all tags in the project", "validate"),
        ">index_project": ("Re-index the project for context engine", "index"),
    }

    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.index: Dict[str, SymbolicEntry] = {}
        self.broken_paths: List[BrokenPath] = []
        self._cypher_cache: Optional[str] = None
        self._index_cache: Optional[str] = None

        logger.info(f"ProjectPrimer initialized for: {self.project_path}")

    def build_index(self) -> Dict[str, SymbolicEntry]:
        """Build the complete symbolic index for the project."""
        self.index.clear()

        # Index standard directories
        self._index_directories()

        # Index standard files
        self._index_files()

        # Index characters
        self._index_characters()

        # Index locations
        self._index_locations()

        # Index processes
        self._index_processes()

        # Index scenes/beats if available
        self._index_story_elements()

        # Verify all paths
        self._verify_paths()

        # Clear caches
        self._index_cache = None

        logger.info(f"Built symbolic index with {len(self.index)} entries")
        return self.index

    def _index_directories(self) -> None:
        """Index standard project directories."""
        for symbol, (rel_path, desc) in self.STANDARD_DIRECTORIES.items():
            full_path = self.project_path / rel_path
            status = PathStatus.VALID if full_path.exists() else PathStatus.MISSING

            self.index[symbol] = SymbolicEntry(
                symbol=symbol,
                path=rel_path,
                symbol_type=SymbolType.DIRECTORY,
                description=desc,
                status=status
            )

    def _index_files(self) -> None:
        """Index standard project files."""
        for symbol, (rel_path, desc) in self.STANDARD_FILES.items():
            full_path = self.project_path / rel_path
            status = PathStatus.VALID if full_path.exists() else PathStatus.MISSING

            self.index[symbol] = SymbolicEntry(
                symbol=symbol,
                path=rel_path,
                symbol_type=SymbolType.FILE,
                description=desc,
                status=status
            )

    def _index_characters(self) -> None:
        """Index character files with @CHAR_ prefix."""
        char_dirs = [
            self.project_path / "characters",
            self.project_path / "world_bible" / "characters"
        ]

        for char_dir in char_dirs:
            if not char_dir.exists():
                continue

            for char_file in char_dir.glob("*.json"):
                try:
                    with open(char_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    name = data.get("name", char_file.stem)
                    symbol = f"@CHAR_{name.upper().replace(' ', '_')}"

                    self.index[symbol] = SymbolicEntry(
                        symbol=symbol,
                        path=str(char_file.relative_to(self.project_path)),
                        symbol_type=SymbolType.CHARACTER,
                        description=data.get("description", f"Character: {name}")[:100],
                        metadata={"name": name, "role": data.get("role", "unknown")}
                    )
                except Exception as e:
                    logger.debug(f"Failed to index character {char_file}: {e}")

    def _index_locations(self) -> None:
        """Index location files with @LOC_ prefix."""
        loc_dirs = [
            self.project_path / "locations",
            self.project_path / "world_bible" / "locations"
        ]

        for loc_dir in loc_dirs:
            if not loc_dir.exists():
                continue

            for loc_file in loc_dir.glob("*.json"):
                try:
                    with open(loc_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    name = data.get("name", loc_file.stem)
                    symbol = f"@LOC_{name.upper().replace(' ', '_')}"

                    self.index[symbol] = SymbolicEntry(
                        symbol=symbol,
                        path=str(loc_file.relative_to(self.project_path)),
                        symbol_type=SymbolType.LOCATION,
                        description=data.get("description", f"Location: {name}")[:100],
                        metadata={"name": name, "type": data.get("type", "unknown")}
                    )
                except Exception as e:
                    logger.debug(f"Failed to index location {loc_file}: {e}")

    def _index_processes(self) -> None:
        """Index available processes with > prefix."""
        for symbol, (desc, process_id) in self.PROCESS_SYMBOLS.items():
            self.index[symbol] = SymbolicEntry(
                symbol=symbol,
                path=f"process:{process_id}",
                symbol_type=SymbolType.PROCESS,
                description=desc,
                metadata={"process_id": process_id}
            )

    def _index_story_elements(self) -> None:
        """Index scenes and beats from story documents."""
        story_dir = self.project_path / "story_documents"
        if not story_dir.exists():
            return

        # Look for scene files
        for scene_file in story_dir.glob("scene_*.md"):
            try:
                scene_num = scene_file.stem.split("_")[1]
                symbol = f"@SCENE_{scene_num}"

                self.index[symbol] = SymbolicEntry(
                    symbol=symbol,
                    path=str(scene_file.relative_to(self.project_path)),
                    symbol_type=SymbolType.SCENE,
                    description=f"Scene {scene_num}",
                    metadata={"scene_number": scene_num}
                )
            except Exception as e:
                logger.debug(f"Failed to index scene {scene_file}: {e}")

        # Look for beat files
        beats_dir = self.project_path / "beats"
        if beats_dir.exists():
            for beat_file in beats_dir.glob("*.json"):
                try:
                    symbol = f"@BEAT_{beat_file.stem.upper()}"
                    self.index[symbol] = SymbolicEntry(
                        symbol=symbol,
                        path=str(beat_file.relative_to(self.project_path)),
                        symbol_type=SymbolType.BEAT,
                        description=f"Beat: {beat_file.stem}",
                    )
                except Exception as e:
                    logger.debug(f"Failed to index beat {beat_file}: {e}")

    def _verify_paths(self) -> None:
        """Verify all indexed paths exist and update status."""
        for symbol, entry in self.index.items():
            if entry.symbol_type == SymbolType.PROCESS:
                continue  # Processes don't have file paths

            full_path = self.project_path / entry.path
            if full_path.exists():
                entry.status = PathStatus.VALID
                entry.last_verified = datetime.now()
            else:
                entry.status = PathStatus.MISSING
                self.broken_paths.append(BrokenPath(
                    symbol=symbol,
                    expected_path=entry.path,
                    error="Path does not exist"
                ))

    def heal_broken_paths(self) -> List[BrokenPath]:
        """Attempt to heal broken paths by searching for alternatives."""
        healed = []

        for broken in self.broken_paths:
            if broken.healed:
                continue

            entry = self.index.get(broken.symbol)
            if not entry:
                continue

            # Try to find the file elsewhere
            filename = Path(broken.expected_path).name
            found_paths = list(self.project_path.rglob(filename))

            if found_paths:
                # Use the first match
                new_path = str(found_paths[0].relative_to(self.project_path))
                entry.path = new_path
                entry.status = PathStatus.VALID
                entry.last_verified = datetime.now()

                broken.healed = True
                broken.healed_path = new_path
                healed.append(broken)

                logger.info(f"Healed path for {broken.symbol}: {broken.expected_path} -> {new_path}")

        # Clear cache after healing
        self._index_cache = None

        return healed

    def get_symbolic_index_prompt(self) -> str:
        """Generate the symbolic index as a prompt for LLMs."""
        if self._index_cache:
            return self._index_cache

        lines = [
            "# PROJECT SYMBOLIC INDEX",
            f"**Project:** {self.project_path.name}",
            "",
            "## Quick Navigation Symbols",
            "",
            "### Directories (#)",
        ]

        # Group by type
        dirs = [e for e in self.index.values() if e.symbol_type == SymbolType.DIRECTORY]
        files = [e for e in self.index.values() if e.symbol_type == SymbolType.FILE]
        chars = [e for e in self.index.values() if e.symbol_type == SymbolType.CHARACTER]
        locs = [e for e in self.index.values() if e.symbol_type == SymbolType.LOCATION]
        procs = [e for e in self.index.values() if e.symbol_type == SymbolType.PROCESS]
        scenes = [e for e in self.index.values() if e.symbol_type == SymbolType.SCENE]

        for entry in dirs:
            status = "✓" if entry.status == PathStatus.VALID else "✗"
            lines.append(f"| `{entry.symbol}` | {entry.path}/ | {entry.description} | {status} |")

        lines.extend(["", "### Key Files (@)"])
        for entry in files:
            status = "✓" if entry.status == PathStatus.VALID else "✗"
            lines.append(f"| `{entry.symbol}` | {entry.path} | {entry.description} | {status} |")

        if chars:
            lines.extend(["", "### Characters (@CHAR_)"])
            for entry in chars:
                lines.append(f"| `{entry.symbol}` | {entry.metadata.get('role', 'character')} | {entry.description[:50]} |")

        if locs:
            lines.extend(["", "### Locations (@LOC_)"])
            for entry in locs:
                lines.append(f"| `{entry.symbol}` | {entry.metadata.get('type', 'location')} | {entry.description[:50]} |")

        if scenes:
            lines.extend(["", "### Scenes (@SCENE_)"])
            for entry in scenes:
                lines.append(f"| `{entry.symbol}` | {entry.path} |")

        lines.extend(["", "### Processes (>)"])
        for entry in procs:
            lines.append(f"| `{entry.symbol}` | {entry.description} |")

        # Add broken paths warning
        broken = [b for b in self.broken_paths if not b.healed]
        if broken:
            lines.extend(["", "### ⚠️ Broken Paths (Need Healing)"])
            for b in broken:
                lines.append(f"| `{b.symbol}` | {b.expected_path} | {b.error} |")

        self._index_cache = "\n".join(lines)
        return self._index_cache



    def get_cypher_document(self) -> str:
        """
        Generate the LLM Cypher document.

        This teaches LLMs how to use the context engine, OmniMind,
        and symbolic notation for this project.
        """
        if self._cypher_cache:
            return self._cypher_cache

        lines = [
            "# PROJECT CYPHER - LLM INSTRUCTION DOCUMENT",
            f"**Project:** {self.project_path.name}",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            "",
            "## 1. SYMBOLIC NOTATION SYSTEM",
            "",
            "Use these prefixes to navigate and query the project:",
            "",
            "| Prefix | Type | Usage | Example |",
            "|--------|------|-------|---------|",
            "| `@` | Entity | Reference specific items | `@CHAR_PROTAGONIST`, `@PITCH` |",
            "| `#` | Scope | Filter by category | `#WORLD_BIBLE`, `#CHARACTERS` |",
            "| `>` | Command | Execute process | `>run_writer`, `>diagnose` |",
            "| `?` | Query | Natural language | `?\"who is protagonist\"` |",
            "| `+` | Include | Add to results | `+relationships` |",
            "| `-` | Exclude | Remove from results | `-archived` |",
            "| `~` | Similar | Semantic search | `~\"warrior spirit\"` |",
            "",
            "## 2. CONTEXT ENGINE QUERIES",
            "",
            "To retrieve information, form symbolic queries:",
            "",
            "```",
            "# Find a character in story context",
            "@CHAR_PROTAGONIST #STORY",
            "",
            "# Search for similar concepts",
            "~\"themes and motifs\" #WORLD_BIBLE",
            "",
            "# Find all locations",
            "#LOCATIONS +all",
            "```",
            "",
            "## 3. AVAILABLE PROCESSES",
            "",
            "| Command | Description |",
            "|---------|-------------|",
            "| `>run_writer` | Generate story content from pitch |",
            "| `>run_director` | Create storyboard from story |",
            "| `>diagnose` | Check project health |",
            "| `>heal` | Auto-fix detected issues |",
            "| `>index` | Re-index project for search |",
            "| `>validate_tags` | Validate all tags |",
            "",
            "## 4. PROJECT STRUCTURE",
            "",
        ]

        # Add directory structure
        for symbol, entry in self.index.items():
            if entry.symbol_type == SymbolType.DIRECTORY:
                status = "✓" if entry.status == PathStatus.VALID else "✗"
                lines.append(f"- `{symbol}` → `{entry.path}/` {status}")

        lines.extend([
            "",
            "## 5. KEY FILES",
            "",
        ])

        for symbol, entry in self.index.items():
            if entry.symbol_type == SymbolType.FILE:
                status = "✓" if entry.status == PathStatus.VALID else "✗"
                lines.append(f"- `{symbol}` → `{entry.path}` - {entry.description} {status}")

        # Add characters if available
        chars = [e for e in self.index.values() if e.symbol_type == SymbolType.CHARACTER]
        if chars:
            lines.extend(["", "## 6. CHARACTERS", ""])
            for entry in chars:
                lines.append(f"- `{entry.symbol}` - {entry.description}")

        # Add locations if available
        locs = [e for e in self.index.values() if e.symbol_type == SymbolType.LOCATION]
        if locs:
            lines.extend(["", "## 7. LOCATIONS", ""])
            for entry in locs:
                lines.append(f"- `{entry.symbol}` - {entry.description}")

        lines.extend([
            "",
            "## 8. SELF-HEALING PROTOCOL",
            "",
            "When you encounter a missing symbol or broken path:",
            "",
            "1. **Log the issue** with `>diagnose`",
            "2. **Attempt healing** with `>heal`",
            "3. **Register new symbol** if discovered",
            "4. **Update the index** with `>index`",
            "",
            "Missing symbols are auto-registered with low confidence.",
            "Broken paths trigger a search for alternatives.",
            "",
            "## 9. QUERY EXAMPLES",
            "",
            "```",
            "# Get pitch content",
            "@PITCH",
            "",
            "# Find character relationships",
            "@CHAR_PROTAGONIST +relationships #STORY",
            "",
            "# Run the writer pipeline",
            ">run_writer",
            "",
            "# Search for themes",
            "~\"themes\" #WORLD_BIBLE",
            "```",
            "",
            "---",
            "",
            "**Remember:** Use symbolic notation for precise queries.",
            "The context engine understands these symbols and will retrieve relevant content.",
        ])

        self._cypher_cache = "\n".join(lines)
        return self._cypher_cache

    def get_full_primer(self) -> str:
        """
        Get the complete project primer for LLM initialization.

        Combines:
        1. Symbolic index (quick navigation)
        2. Cypher document (how to use the system)
        """
        return f"{self.get_symbolic_index_prompt()}\n\n---\n\n{self.get_cypher_document()}"

    def save_primer(self) -> Path:
        """Save the primer to the project's .health directory."""
        health_dir = self.project_path / ".health"
        health_dir.mkdir(parents=True, exist_ok=True)

        primer_file = health_dir / "project_primer.md"
        with open(primer_file, 'w', encoding='utf-8') as f:
            f.write(self.get_full_primer())

        logger.info(f"Saved project primer to {primer_file}")
        return primer_file

    def save_index(self) -> Path:
        """Save the symbolic index to JSON."""
        index_file = self.storage_dir / "symbolic_index.json" if hasattr(self, 'storage_dir') else self.project_path / ".symbolic" / "index.json"
        index_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "project": self.project_path.name,
            "generated_at": datetime.now().isoformat(),
            "entry_count": len(self.index),
            "broken_paths": len([b for b in self.broken_paths if not b.healed]),
            "entries": {k: v.to_dict() for k, v in self.index.items()}
        }

        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        return index_file

    def get_stats(self) -> Dict[str, Any]:
        """Get primer statistics."""
        by_type = {}
        for entry in self.index.values():
            t = entry.symbol_type.value
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_entries": len(self.index),
            "by_type": by_type,
            "valid_paths": sum(1 for e in self.index.values() if e.status == PathStatus.VALID),
            "missing_paths": sum(1 for e in self.index.values() if e.status == PathStatus.MISSING),
            "broken_paths": len(self.broken_paths),
            "healed_paths": sum(1 for b in self.broken_paths if b.healed)
        }