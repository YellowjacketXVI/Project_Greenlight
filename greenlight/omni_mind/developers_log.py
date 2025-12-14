"""
Greenlight Developers Log Pipeline

Comprehensive logging pipeline for development reports, updates, and capability tracking.
Generates structured reports for developers with version history, capability registry,
and update logs.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path
from enum import Enum
import json

from greenlight.core.logging_config import get_logger
from greenlight.utils.file_utils import read_json, write_json, ensure_directory

logger = get_logger("omni_mind.developers_log")


class UpdateType(Enum):
    """Types of development updates."""
    FEATURE = "feature"
    BUGFIX = "bugfix"
    ENHANCEMENT = "enhancement"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    PERFORMANCE = "performance"
    SECURITY = "security"
    BREAKING = "breaking"


class CapabilityStatus(Enum):
    """Status of a capability."""
    PLANNED = "planned"
    IN_DEVELOPMENT = "in_development"
    TESTING = "testing"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


class ReportType(Enum):
    """Types of developer reports."""
    CHANGELOG = "changelog"
    CAPABILITY_MATRIX = "capability_matrix"
    SYSTEM_STATUS = "system_status"
    FULL_REPORT = "full_report"
    RELEASE_NOTES = "release_notes"


@dataclass
class UpdateEntry:
    """A development update entry."""
    id: str
    update_type: UpdateType
    title: str
    description: str
    version: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Affected components
    affected_files: List[str] = field(default_factory=list)
    affected_modules: List[str] = field(default_factory=list)
    
    # Metadata
    author: str = "system"
    breaking_changes: bool = False
    migration_notes: str = ""
    related_issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "update_type": self.update_type.value,
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "affected_files": self.affected_files,
            "affected_modules": self.affected_modules,
            "author": self.author,
            "breaking_changes": self.breaking_changes,
            "migration_notes": self.migration_notes,
            "related_issues": self.related_issues
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UpdateEntry":
        return cls(
            id=data["id"],
            update_type=UpdateType(data["update_type"]),
            title=data["title"],
            description=data["description"],
            version=data.get("version", ""),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            affected_files=data.get("affected_files", []),
            affected_modules=data.get("affected_modules", []),
            author=data.get("author", "system"),
            breaking_changes=data.get("breaking_changes", False),
            migration_notes=data.get("migration_notes", ""),
            related_issues=data.get("related_issues", [])
        )


@dataclass
class Capability:
    """A system capability definition."""
    id: str
    name: str
    description: str
    status: CapabilityStatus
    module: str
    version_added: str = ""
    version_deprecated: str = ""
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    required_by: List[str] = field(default_factory=list)
    
    # Documentation
    usage_example: str = ""
    api_reference: str = ""
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "module": self.module,
            "version_added": self.version_added,
            "version_deprecated": self.version_deprecated,
            "depends_on": self.depends_on,
            "required_by": self.required_by,
            "usage_example": self.usage_example,
            "api_reference": self.api_reference,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Capability":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            status=CapabilityStatus(data["status"]),
            module=data["module"],
            version_added=data.get("version_added", ""),
            version_deprecated=data.get("version_deprecated", ""),
            depends_on=data.get("depends_on", []),
            required_by=data.get("required_by", []),
            usage_example=data.get("usage_example", ""),
            api_reference=data.get("api_reference", ""),
            notes=data.get("notes", "")
        )


@dataclass
class VersionInfo:
    """Version information."""
    version: str
    release_date: datetime
    codename: str = ""
    is_stable: bool = True
    changelog_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "release_date": self.release_date.isoformat(),
            "codename": self.codename,
            "is_stable": self.is_stable,
            "changelog_summary": self.changelog_summary
        }


class DevelopersLogPipeline:
    """
    Developers Log Pipeline for comprehensive development tracking.

    Features:
    - Track development updates (features, bugfixes, enhancements)
    - Register and monitor system capabilities
    - Generate structured reports (changelog, capability matrix, etc.)
    - Version history management
    - Integration with health logger and terminal logger
    """

    CURRENT_VERSION = "0.1.0"

    def __init__(
        self,
        project_path: Path = None,
        health_logger: Any = None,
        terminal_logger: Any = None
    ):
        """
        Initialize developers log pipeline.

        Args:
            project_path: Project root path
            health_logger: ProjectHealthLogger instance
            terminal_logger: TerminalLogger instance
        """
        self.project_path = project_path
        self.health_logger = health_logger
        self.terminal_logger = terminal_logger

        self._updates: Dict[str, UpdateEntry] = {}
        self._capabilities: Dict[str, Capability] = {}
        self._versions: List[VersionInfo] = []
        self._next_id = 0

        # Setup storage
        if project_path:
            self.dev_log_dir = project_path / ".dev_log"
            ensure_directory(self.dev_log_dir)
            self.updates_file = self.dev_log_dir / "updates.json"
            self.capabilities_file = self.dev_log_dir / "capabilities.json"
            self.versions_file = self.dev_log_dir / "versions.json"
            self._load_from_disk()
        else:
            self.dev_log_dir = None

    def _generate_id(self, prefix: str = "upd") -> str:
        """Generate unique ID."""
        self._next_id += 1
        return f"{prefix}_{self._next_id:06d}"

    def _load_from_disk(self) -> None:
        """Load data from disk."""
        try:
            if self.updates_file and self.updates_file.exists():
                data = read_json(self.updates_file)
                for entry_data in data.get("updates", []):
                    entry = UpdateEntry.from_dict(entry_data)
                    self._updates[entry.id] = entry
                self._next_id = data.get("next_id", len(self._updates))

            if self.capabilities_file and self.capabilities_file.exists():
                data = read_json(self.capabilities_file)
                for cap_data in data.get("capabilities", []):
                    cap = Capability.from_dict(cap_data)
                    self._capabilities[cap.id] = cap

            if self.versions_file and self.versions_file.exists():
                data = read_json(self.versions_file)
                for ver_data in data.get("versions", []):
                    self._versions.append(VersionInfo(
                        version=ver_data["version"],
                        release_date=datetime.fromisoformat(ver_data["release_date"]),
                        codename=ver_data.get("codename", ""),
                        is_stable=ver_data.get("is_stable", True),
                        changelog_summary=ver_data.get("changelog_summary", "")
                    ))

            logger.info(f"Loaded {len(self._updates)} updates, {len(self._capabilities)} capabilities")
        except Exception as e:
            logger.error(f"Failed to load developers log: {e}")

    def _save_to_disk(self) -> None:
        """Save data to disk."""
        try:
            if self.updates_file:
                data = {
                    "next_id": self._next_id,
                    "updates": [u.to_dict() for u in self._updates.values()]
                }
                write_json(self.updates_file, data)

            if self.capabilities_file:
                data = {
                    "capabilities": [c.to_dict() for c in self._capabilities.values()]
                }
                write_json(self.capabilities_file, data)

            if self.versions_file:
                data = {
                    "versions": [v.to_dict() for v in self._versions]
                }
                write_json(self.versions_file, data)
        except Exception as e:
            logger.error(f"Failed to save developers log: {e}")

    # =========================================================================
    # UPDATE MANAGEMENT
    # =========================================================================

    def log_update(
        self,
        update_type: UpdateType,
        title: str,
        description: str,
        version: str = None,
        affected_files: List[str] = None,
        affected_modules: List[str] = None,
        breaking_changes: bool = False,
        migration_notes: str = "",
        author: str = "system"
    ) -> UpdateEntry:
        """
        Log a development update.

        Args:
            update_type: Type of update
            title: Update title
            description: Update description
            version: Version number
            affected_files: List of affected files
            affected_modules: List of affected modules
            breaking_changes: Whether this is a breaking change
            migration_notes: Migration notes if breaking
            author: Author of the update

        Returns:
            Created UpdateEntry
        """
        entry = UpdateEntry(
            id=self._generate_id("upd"),
            update_type=update_type,
            title=title,
            description=description,
            version=version or self.CURRENT_VERSION,
            affected_files=affected_files or [],
            affected_modules=affected_modules or [],
            breaking_changes=breaking_changes,
            migration_notes=migration_notes,
            author=author
        )

        self._updates[entry.id] = entry
        self._save_to_disk()

        # Log to terminal if available
        if self.terminal_logger:
            self.terminal_logger.log_info(
                f"[DEV] {update_type.value.upper()}: {title}",
                source="developers_log"
            )

        logger.info(f"Logged update: {entry.id} - {title}")
        return entry

    def log_feature(self, title: str, description: str, **kwargs) -> UpdateEntry:
        """Quick method to log a feature."""
        return self.log_update(UpdateType.FEATURE, title, description, **kwargs)

    def log_bugfix(self, title: str, description: str, **kwargs) -> UpdateEntry:
        """Quick method to log a bugfix."""
        return self.log_update(UpdateType.BUGFIX, title, description, **kwargs)

    def log_enhancement(self, title: str, description: str, **kwargs) -> UpdateEntry:
        """Quick method to log an enhancement."""
        return self.log_update(UpdateType.ENHANCEMENT, title, description, **kwargs)

    def get_updates_by_type(self, update_type: UpdateType) -> List[UpdateEntry]:
        """Get updates by type."""
        return [u for u in self._updates.values() if u.update_type == update_type]

    def get_updates_by_version(self, version: str) -> List[UpdateEntry]:
        """Get updates for a specific version."""
        return [u for u in self._updates.values() if u.version == version]

    def get_breaking_changes(self) -> List[UpdateEntry]:
        """Get all breaking changes."""
        return [u for u in self._updates.values() if u.breaking_changes]

    # =========================================================================
    # CAPABILITY MANAGEMENT
    # =========================================================================

    def register_capability(
        self,
        name: str,
        description: str,
        module: str,
        status: CapabilityStatus = CapabilityStatus.STABLE,
        version_added: str = None,
        depends_on: List[str] = None,
        usage_example: str = "",
        api_reference: str = ""
    ) -> Capability:
        """
        Register a system capability.

        Args:
            name: Capability name
            description: Capability description
            module: Module containing the capability
            status: Current status
            version_added: Version when added
            depends_on: List of dependency capability IDs
            usage_example: Usage example code
            api_reference: API reference link

        Returns:
            Created Capability
        """
        cap = Capability(
            id=self._generate_id("cap"),
            name=name,
            description=description,
            status=status,
            module=module,
            version_added=version_added or self.CURRENT_VERSION,
            depends_on=depends_on or [],
            usage_example=usage_example,
            api_reference=api_reference
        )

        self._capabilities[cap.id] = cap
        self._save_to_disk()

        logger.info(f"Registered capability: {cap.id} - {name}")
        return cap

    def update_capability_status(
        self,
        capability_id: str,
        status: CapabilityStatus,
        version_deprecated: str = None
    ) -> Optional[Capability]:
        """Update a capability's status."""
        cap = self._capabilities.get(capability_id)
        if cap:
            cap.status = status
            if status == CapabilityStatus.DEPRECATED and version_deprecated:
                cap.version_deprecated = version_deprecated
            self._save_to_disk()
        return cap

    def get_capabilities_by_status(self, status: CapabilityStatus) -> List[Capability]:
        """Get capabilities by status."""
        return [c for c in self._capabilities.values() if c.status == status]

    def get_capabilities_by_module(self, module: str) -> List[Capability]:
        """Get capabilities by module."""
        return [c for c in self._capabilities.values() if c.module == module]

    # =========================================================================
    # VERSION MANAGEMENT
    # =========================================================================

    def register_version(
        self,
        version: str,
        codename: str = "",
        is_stable: bool = True,
        changelog_summary: str = ""
    ) -> VersionInfo:
        """Register a new version."""
        ver = VersionInfo(
            version=version,
            release_date=datetime.now(),
            codename=codename,
            is_stable=is_stable,
            changelog_summary=changelog_summary
        )
        self._versions.append(ver)
        self._save_to_disk()

        logger.info(f"Registered version: {version}")
        return ver

    def get_current_version(self) -> str:
        """Get current version."""
        if self._versions:
            return self._versions[-1].version
        return self.CURRENT_VERSION

    # =========================================================================
    # REPORT GENERATION
    # =========================================================================

    def generate_changelog(self, version: str = None) -> str:
        """
        Generate changelog report.

        Args:
            version: Specific version or None for all

        Returns:
            Markdown changelog
        """
        lines = [
            "# Changelog",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        updates = self.get_updates_by_version(version) if version else list(self._updates.values())
        updates = sorted(updates, key=lambda u: u.timestamp, reverse=True)

        if not updates:
            lines.append("*No updates recorded.*")
            return "\n".join(lines)

        # Group by version
        by_version: Dict[str, List[UpdateEntry]] = {}
        for u in updates:
            ver = u.version or "Unreleased"
            if ver not in by_version:
                by_version[ver] = []
            by_version[ver].append(u)

        for ver, ver_updates in by_version.items():
            lines.extend([
                f"## [{ver}]",
                "",
            ])

            # Group by type
            by_type: Dict[str, List[UpdateEntry]] = {}
            for u in ver_updates:
                t = u.update_type.value.capitalize()
                if t not in by_type:
                    by_type[t] = []
                by_type[t].append(u)

            for update_type, type_updates in by_type.items():
                lines.append(f"### {update_type}s")
                for u in type_updates:
                    lines.append(f"- **{u.title}**: {u.description}")
                    if u.breaking_changes:
                        lines.append(f"  - ⚠️ BREAKING CHANGE")
                        if u.migration_notes:
                            lines.append(f"  - Migration: {u.migration_notes}")
                lines.append("")

        return "\n".join(lines)

    def generate_capability_matrix(self) -> str:
        """Generate capability matrix report."""
        lines = [
            "# Capability Matrix",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Total Capabilities:** {len(self._capabilities)}",
            "",
            "## Status Overview",
            "",
            "| Status | Count |",
            "|--------|-------|",
        ]

        # Count by status
        status_counts = {}
        for cap in self._capabilities.values():
            s = cap.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        for status, count in status_counts.items():
            lines.append(f"| {status.replace('_', ' ').title()} | {count} |")

        lines.extend([
            "",
            "## Capabilities by Module",
            "",
        ])

        # Group by module
        by_module: Dict[str, List[Capability]] = {}
        for cap in self._capabilities.values():
            if cap.module not in by_module:
                by_module[cap.module] = []
            by_module[cap.module].append(cap)

        for module, caps in sorted(by_module.items()):
            lines.extend([
                f"### {module}",
                "",
                "| Capability | Status | Version Added |",
                "|------------|--------|---------------|",
            ])
            for cap in caps:
                status_emoji = {
                    CapabilityStatus.STABLE: "✅",
                    CapabilityStatus.TESTING: "🧪",
                    CapabilityStatus.IN_DEVELOPMENT: "🔧",
                    CapabilityStatus.PLANNED: "📋",
                    CapabilityStatus.DEPRECATED: "⚠️",
                    CapabilityStatus.REMOVED: "❌"
                }.get(cap.status, "")
                lines.append(f"| {cap.name} | {status_emoji} {cap.status.value} | {cap.version_added} |")
            lines.append("")

        return "\n".join(lines)

    def generate_system_status(self) -> str:
        """Generate system status report."""
        lines = [
            "# System Status Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Current Version:** {self.get_current_version()}",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"- Total Updates: {len(self._updates)}",
            f"- Total Capabilities: {len(self._capabilities)}",
            f"- Stable Capabilities: {len(self.get_capabilities_by_status(CapabilityStatus.STABLE))}",
            f"- In Development: {len(self.get_capabilities_by_status(CapabilityStatus.IN_DEVELOPMENT))}",
            f"- Breaking Changes: {len(self.get_breaking_changes())}",
            "",
        ]

        # Recent updates
        recent = sorted(self._updates.values(), key=lambda u: u.timestamp, reverse=True)[:10]
        if recent:
            lines.extend([
                "## Recent Updates",
                "",
                "| Date | Type | Title |",
                "|------|------|-------|",
            ])
            for u in recent:
                date_str = u.timestamp.strftime("%Y-%m-%d")
                lines.append(f"| {date_str} | {u.update_type.value} | {u.title} |")
            lines.append("")

        # Health integration
        if self.health_logger:
            stats = self.health_logger.get_stats()
            lines.extend([
                "## Health Status",
                "",
                f"- Log Entries: {stats.get('total_entries', 0)}",
                f"- Unresolved Issues: {stats.get('unresolved', 0)}",
                f"- Pipeline Executions: {stats.get('pipeline_count', 0)}",
                "",
            ])

        return "\n".join(lines)

    def generate_full_report(self) -> str:
        """Generate comprehensive full report."""
        sections = [
            self.generate_system_status(),
            "",
            "---",
            "",
            self.generate_capability_matrix(),
            "",
            "---",
            "",
            self.generate_changelog(),
        ]
        return "\n".join(sections)

    def generate_release_notes(self, version: str) -> str:
        """Generate release notes for a specific version."""
        updates = self.get_updates_by_version(version)

        lines = [
            f"# Release Notes - v{version}",
            "",
            f"**Release Date:** {datetime.now().strftime('%Y-%m-%d')}",
            "",
        ]

        # Find version info
        ver_info = next((v for v in self._versions if v.version == version), None)
        if ver_info and ver_info.codename:
            lines.append(f"**Codename:** {ver_info.codename}")
            lines.append("")

        if not updates:
            lines.append("*No updates for this version.*")
            return "\n".join(lines)

        # Highlights
        features = [u for u in updates if u.update_type == UpdateType.FEATURE]
        if features:
            lines.extend([
                "## ✨ New Features",
                "",
            ])
            for f in features:
                lines.append(f"- **{f.title}**: {f.description}")
            lines.append("")

        # Bug fixes
        bugfixes = [u for u in updates if u.update_type == UpdateType.BUGFIX]
        if bugfixes:
            lines.extend([
                "## 🐛 Bug Fixes",
                "",
            ])
            for b in bugfixes:
                lines.append(f"- {b.title}")
            lines.append("")

        # Breaking changes
        breaking = [u for u in updates if u.breaking_changes]
        if breaking:
            lines.extend([
                "## ⚠️ Breaking Changes",
                "",
            ])
            for b in breaking:
                lines.append(f"- **{b.title}**: {b.description}")
                if b.migration_notes:
                    lines.append(f"  - Migration: {b.migration_notes}")
            lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # REPORT SAVING
    # =========================================================================

    def save_report(self, report_type: ReportType, version: str = None) -> Optional[Path]:
        """
        Generate and save a report.

        Args:
            report_type: Type of report to generate
            version: Version for version-specific reports

        Returns:
            Path to saved report
        """
        if not self.dev_log_dir:
            logger.warning("No project path set, cannot save report")
            return None

        reports_dir = self.dev_log_dir / "reports"
        ensure_directory(reports_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if report_type == ReportType.CHANGELOG:
            content = self.generate_changelog(version)
            filename = f"changelog_{timestamp}.md"
        elif report_type == ReportType.CAPABILITY_MATRIX:
            content = self.generate_capability_matrix()
            filename = f"capability_matrix_{timestamp}.md"
        elif report_type == ReportType.SYSTEM_STATUS:
            content = self.generate_system_status()
            filename = f"system_status_{timestamp}.md"
        elif report_type == ReportType.FULL_REPORT:
            content = self.generate_full_report()
            filename = f"full_report_{timestamp}.md"
        elif report_type == ReportType.RELEASE_NOTES:
            if not version:
                version = self.get_current_version()
            content = self.generate_release_notes(version)
            filename = f"release_notes_v{version}_{timestamp}.md"
        else:
            logger.error(f"Unknown report type: {report_type}")
            return None

        report_path = reports_dir / filename
        report_path.write_text(content, encoding="utf-8")

        logger.info(f"Saved report: {report_path}")
        return report_path

    def get_stats(self) -> Dict[str, Any]:
        """Get developers log statistics."""
        by_type = {}
        for u in self._updates.values():
            t = u.update_type.value
            by_type[t] = by_type.get(t, 0) + 1

        by_status = {}
        for c in self._capabilities.values():
            s = c.status.value
            by_status[s] = by_status.get(s, 0) + 1

        return {
            "total_updates": len(self._updates),
            "total_capabilities": len(self._capabilities),
            "total_versions": len(self._versions),
            "current_version": self.get_current_version(),
            "updates_by_type": by_type,
            "capabilities_by_status": by_status,
            "breaking_changes": len(self.get_breaking_changes())
        }

