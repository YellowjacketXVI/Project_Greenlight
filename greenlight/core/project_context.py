"""
Greenlight Project Context Singleton

Global project context that caches world config, scripts, and other
project-level data to avoid repeated file loading.
"""

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from greenlight.core.logging_config import get_logger

logger = get_logger("core.project_context")


@dataclass
class ProjectMetadata:
    """Metadata about the current project."""
    project_name: str
    project_path: Path
    created_at: datetime
    last_accessed: datetime
    world_config_loaded: bool = False
    script_loaded: bool = False
    visual_script_loaded: bool = False


@dataclass
class CachedWorldConfig:
    """Cached world configuration with parsed entities."""
    raw: Dict[str, Any]
    characters: List[Dict[str, Any]]
    locations: List[Dict[str, Any]]
    props: List[Dict[str, Any]]
    visual_style: str
    style_notes: str
    lighting: str
    vibe: str
    themes: List[str]
    world_details: Dict[str, Any]

    # Pre-formatted context strings
    _style_suffix: Optional[str] = None
    _world_context: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CachedWorldConfig':
        """Create from raw world_config dict."""
        themes = data.get('themes', [])
        if isinstance(themes, str):
            themes = [themes]

        return cls(
            raw=data,
            characters=data.get('characters', []),
            locations=data.get('locations', []),
            props=data.get('props', []),
            visual_style=data.get('visual_style', ''),
            style_notes=data.get('style_notes', ''),
            lighting=data.get('lighting', ''),
            vibe=data.get('vibe', ''),
            themes=themes,
            world_details=data.get('world_details', {})
        )

    def get_style_suffix(self) -> str:
        """Get formatted style suffix for image prompts."""
        if self._style_suffix is None:
            parts = []
            if self.visual_style:
                parts.append(self.visual_style)
            if self.style_notes:
                parts.append(self.style_notes)
            if self.lighting:
                parts.append(f"Lighting: {self.lighting}")
            if self.vibe:
                parts.append(f"Mood: {self.vibe}")
            self._style_suffix = ". ".join(parts)
        return self._style_suffix

    def get_character_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get character by tag."""
        for char in self.characters:
            if char.get('tag') == tag:
                return char
        return None

    def get_location_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get location by tag."""
        for loc in self.locations:
            if loc.get('tag') == tag:
                return loc
        return None

    def get_prop_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get prop by tag."""
        for prop in self.props:
            if prop.get('tag') == tag:
                return prop
        return None


class ProjectContext:
    """
    Singleton project context manager.

    Caches project data to avoid repeated file loading:
    - world_config.json
    - Script content
    - Visual script content
    - Tag registries

    Thread-safe with automatic cache invalidation.
    """

    _instance: Optional['ProjectContext'] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'ProjectContext':
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing or project switch)."""
        with cls._lock:
            cls._instance = None

    def __init__(self):
        """Initialize empty project context."""
        self._project_path: Optional[Path] = None
        self._metadata: Optional[ProjectMetadata] = None
        self._world_config: Optional[CachedWorldConfig] = None
        self._script: Optional[str] = None
        self._visual_script: Optional[str] = None
        self._tag_registry: Dict[str, Any] = {}
        self._file_mtimes: Dict[str, float] = {}
        self._access_lock = threading.RLock()

    def set_project(self, project_path: Path) -> None:
        """
        Set the current project.

        Clears cached data if project path changes.

        Args:
            project_path: Path to project directory
        """
        project_path = Path(project_path)

        with self._access_lock:
            if self._project_path != project_path:
                # Clear caches on project change
                self._clear_caches()
                self._project_path = project_path
                self._metadata = ProjectMetadata(
                    project_name=project_path.name,
                    project_path=project_path,
                    created_at=datetime.now(),
                    last_accessed=datetime.now()
                )
                logger.info(f"Project context set to: {project_path.name}")

    def _clear_caches(self) -> None:
        """Clear all cached data."""
        self._world_config = None
        self._script = None
        self._visual_script = None
        self._tag_registry = {}
        self._file_mtimes = {}

    def get_project_path(self) -> Optional[Path]:
        """Get current project path."""
        return self._project_path

    def get_world_config(self, force_reload: bool = False) -> Optional[CachedWorldConfig]:
        """
        Get cached world configuration.

        Automatically reloads if file has changed on disk.

        Args:
            force_reload: Force reload from disk

        Returns:
            Cached world config or None
        """
        if self._project_path is None:
            return None

        with self._access_lock:
            config_path = self._project_path / "world_bible" / "world_config.json"

            if not config_path.exists():
                return None

            # Check if reload needed
            current_mtime = config_path.stat().st_mtime
            cached_mtime = self._file_mtimes.get(str(config_path), 0)

            if force_reload or self._world_config is None or current_mtime > cached_mtime:
                self._load_world_config(config_path)

            if self._metadata:
                self._metadata.last_accessed = datetime.now()

            return self._world_config

    def _load_world_config(self, config_path: Path) -> None:
        """Load world config from disk."""
        try:
            data = json.loads(config_path.read_text(encoding='utf-8'))
            self._world_config = CachedWorldConfig.from_dict(data)
            self._file_mtimes[str(config_path)] = config_path.stat().st_mtime

            if self._metadata:
                self._metadata.world_config_loaded = True

            logger.info(
                f"Loaded world_config: {len(self._world_config.characters)} chars, "
                f"{len(self._world_config.locations)} locs, "
                f"{len(self._world_config.props)} props"
            )

        except Exception as e:
            logger.error(f"Failed to load world_config: {e}")
            self._world_config = None

    def get_script(self, force_reload: bool = False) -> Optional[str]:
        """
        Get cached script content.

        Args:
            force_reload: Force reload from disk

        Returns:
            Script content or None
        """
        if self._project_path is None:
            return None

        with self._access_lock:
            script_path = self._project_path / "scripts" / "script.md"

            if not script_path.exists():
                return None

            current_mtime = script_path.stat().st_mtime
            cached_mtime = self._file_mtimes.get(str(script_path), 0)

            if force_reload or self._script is None or current_mtime > cached_mtime:
                self._script = script_path.read_text(encoding='utf-8')
                self._file_mtimes[str(script_path)] = current_mtime

                if self._metadata:
                    self._metadata.script_loaded = True

                logger.debug(f"Loaded script: {len(self._script)} chars")

            return self._script

    def get_visual_script(self, force_reload: bool = False) -> Optional[str]:
        """
        Get cached visual script content.

        Args:
            force_reload: Force reload from disk

        Returns:
            Visual script content or None
        """
        if self._project_path is None:
            return None

        with self._access_lock:
            vs_path = self._project_path / "scripts" / "visual_script.md"

            if not vs_path.exists():
                return None

            current_mtime = vs_path.stat().st_mtime
            cached_mtime = self._file_mtimes.get(str(vs_path), 0)

            if force_reload or self._visual_script is None or current_mtime > cached_mtime:
                self._visual_script = vs_path.read_text(encoding='utf-8')
                self._file_mtimes[str(vs_path)] = current_mtime

                if self._metadata:
                    self._metadata.visual_script_loaded = True

                logger.debug(f"Loaded visual_script: {len(self._visual_script)} chars")

            return self._visual_script

    def get_character(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get character by tag from cached world config."""
        config = self.get_world_config()
        if config:
            return config.get_character_by_tag(tag)
        return None

    def get_location(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get location by tag from cached world config."""
        config = self.get_world_config()
        if config:
            return config.get_location_by_tag(tag)
        return None

    def get_prop(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get prop by tag from cached world config."""
        config = self.get_world_config()
        if config:
            return config.get_prop_by_tag(tag)
        return None

    def get_style_suffix(self) -> str:
        """Get formatted style suffix for image prompts."""
        config = self.get_world_config()
        if config:
            return config.get_style_suffix()
        return ""

    def get_all_tags(self) -> Dict[str, List[str]]:
        """Get all tags organized by category."""
        config = self.get_world_config()
        if not config:
            return {"characters": [], "locations": [], "props": []}

        return {
            "characters": [c.get('tag', '') for c in config.characters if c.get('tag')],
            "locations": [l.get('tag', '') for l in config.locations if l.get('tag')],
            "props": [p.get('tag', '') for p in config.props if p.get('tag')]
        }

    def invalidate(self, what: str = "all") -> None:
        """
        Invalidate cached data.

        Args:
            what: What to invalidate ('world_config', 'script', 'visual_script', 'all')
        """
        with self._access_lock:
            if what in ("world_config", "all"):
                self._world_config = None
                if self._metadata:
                    self._metadata.world_config_loaded = False
            if what in ("script", "all"):
                self._script = None
                if self._metadata:
                    self._metadata.script_loaded = False
            if what in ("visual_script", "all"):
                self._visual_script = None
                if self._metadata:
                    self._metadata.visual_script_loaded = False

            logger.debug(f"Invalidated cache: {what}")

    def get_stats(self) -> Dict[str, Any]:
        """Get context statistics."""
        with self._access_lock:
            config = self._world_config
            return {
                "project_path": str(self._project_path) if self._project_path else None,
                "world_config_loaded": config is not None,
                "script_loaded": self._script is not None,
                "visual_script_loaded": self._visual_script is not None,
                "characters_count": len(config.characters) if config else 0,
                "locations_count": len(config.locations) if config else 0,
                "props_count": len(config.props) if config else 0,
                "cached_files": len(self._file_mtimes)
            }


# Convenience functions
def get_project_context() -> ProjectContext:
    """Get the global project context."""
    return ProjectContext.get_instance()


def set_project(project_path: Path) -> None:
    """Set the current project."""
    get_project_context().set_project(project_path)


def get_world_config(force_reload: bool = False) -> Optional[CachedWorldConfig]:
    """Get cached world configuration."""
    return get_project_context().get_world_config(force_reload)


def get_script(force_reload: bool = False) -> Optional[str]:
    """Get cached script content."""
    return get_project_context().get_script(force_reload)


def get_visual_script(force_reload: bool = False) -> Optional[str]:
    """Get cached visual script content."""
    return get_project_context().get_visual_script(force_reload)


def get_character(tag: str) -> Optional[Dict[str, Any]]:
    """Get character by tag."""
    return get_project_context().get_character(tag)


def get_location(tag: str) -> Optional[Dict[str, Any]]:
    """Get location by tag."""
    return get_project_context().get_location(tag)


def get_prop(tag: str) -> Optional[Dict[str, Any]]:
    """Get prop by tag."""
    return get_project_context().get_prop(tag)
