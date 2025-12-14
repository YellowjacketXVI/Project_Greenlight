"""
Workspace Utility Components

Reusable UI components and data parsing utilities for workspace panels.
Provides consistent patterns for:
- Empty state displays
- Error message displays
- Scrollable content containers
- Data parsing for pipeline outputs (script, visual script, world config)
"""

import customtkinter as ctk
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import json
import re

from greenlight.ui.theme import theme
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.workspace_utils")


# =============================================================================
# UI COMPONENT DEFINITIONS
# =============================================================================
#
# MainWorkspace: Central content area that displays different views (Editor,
#                Script, Storyboard, World Bible, Gallery, References)
#
# WorkspaceMode: Enum defining available view modes for the workspace
#
# Panel: A view within the workspace (e.g., Script Panel, World Bible Panel)
#
# Tab: Sub-section within a panel (e.g., Script tab, Visual Script tab within
#      the Script Panel)
#
# Empty State: UI displayed when a panel has no content to show
#
# Error State: UI displayed when a panel encounters an error loading content
#
# Content Container: Scrollable frame that holds panel content
#
# =============================================================================


class EmptyStateWidget(ctk.CTkFrame):
    """
    Reusable empty state display widget.

    Shows an icon, title, message, and optional action button when
    a panel has no content to display.
    """

    def __init__(
        self,
        master,
        icon: str = "📭",
        title: str = "No Content",
        message: str = "No content available.",
        action_text: Optional[str] = None,
        action_callback: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(master, fg_color=theme.colors.bg_light, corner_radius=8, **kwargs)

        # Icon
        ctk.CTkLabel(
            self,
            text=icon,
            font=(theme.fonts.family, 48),
            text_color=theme.colors.text_muted
        ).pack(pady=(theme.spacing.lg, theme.spacing.sm))

        # Title
        ctk.CTkLabel(
            self,
            text=title,
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.text_primary
        ).pack()

        # Message
        ctk.CTkLabel(
            self,
            text=message,
            text_color=theme.colors.text_secondary,
            justify="center",
            wraplength=400
        ).pack(pady=(theme.spacing.sm, theme.spacing.lg))

        # Optional action button
        if action_text and action_callback:
            ctk.CTkButton(
                self,
                text=action_text,
                command=action_callback,
                fg_color=theme.colors.primary,
                hover_color=theme.colors.primary_hover
            ).pack(pady=(0, theme.spacing.lg))


class ErrorStateWidget(ctk.CTkFrame):
    """
    Reusable error state display widget.

    Shows an error icon, title, error message, and optional retry button.
    """

    def __init__(
        self,
        master,
        title: str = "Error",
        error_message: str = "An error occurred.",
        retry_callback: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(master, fg_color=theme.colors.bg_light, corner_radius=8, **kwargs)

        # Error icon
        ctk.CTkLabel(
            self,
            text="⚠️",
            font=(theme.fonts.family, 48),
            text_color=theme.colors.warning
        ).pack(pady=(theme.spacing.lg, theme.spacing.sm))

        # Title
        ctk.CTkLabel(
            self,
            text=title,
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.text_primary
        ).pack()

        # Error message
        ctk.CTkLabel(
            self,
            text=error_message,
            text_color=theme.colors.text_secondary,


class ScrollableContentContainer(ctk.CTkScrollableFrame):
    """
    Reusable scrollable content container.

    Provides consistent styling for scrollable panel content.
    """

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )


class TabBar(ctk.CTkFrame):
    """
    Reusable tab bar for panels with multiple tabs.
    """

    def __init__(
        self,
        master,
        tabs: List[tuple],  # List of (tab_name, tab_id)
        on_tab_change: Callable[[str], None],
        **kwargs
    ):
        super().__init__(master, fg_color=theme.colors.bg_dark, height=45, **kwargs)
        self.pack_propagate(False)

        self._tabs = {}
        self._active_tab = None
        self._on_tab_change = on_tab_change

        for tab_name, tab_id in tabs:
            tab_btn = ctk.CTkButton(
                self,
                text=tab_name,
                width=140,
                height=35,
                corner_radius=0,
                fg_color="transparent",
                hover_color=theme.colors.bg_medium,
                text_color=theme.colors.text_secondary,
                command=lambda tid=tab_id: self._switch_tab(tid)
            )
            tab_btn.pack(side="left", padx=2, pady=5)
            self._tabs[tab_id] = tab_btn

        # Activate first tab
        if tabs:
            self._switch_tab(tabs[0][1])

    def _switch_tab(self, tab_id: str) -> None:
        """Switch to a different tab."""
        for tid, btn in self._tabs.items():
            if tid == tab_id:
                btn.configure(fg_color=theme.colors.primary, text_color=theme.colors.text_primary)
            else:
                btn.configure(fg_color="transparent", text_color=theme.colors.text_secondary)

        self._active_tab = tab_id
        self._on_tab_change(tab_id)

    @property
    def active_tab(self) -> Optional[str]:
        return self._active_tab


# =============================================================================
# DATA PARSING UTILITIES
# =============================================================================


class ScriptParser:
    """
    Parser for script.md files generated by the Writer pipeline.

    Expected format:
    # Project Name
    **Genre:** ...
    ---
    ## Scene X: Description
    **Location:** [LOC_TAG]
    **Time:** ...
    **Characters:** [CHAR_TAG], ...
    **Purpose:** ...
    **Emotional Beat:** ...
    ### Beat X
    Beat content...
    **Beat Details:**
    - Characters: ...
    - Location: ...
    """

    @staticmethod
    def parse(content: str) -> List[Dict[str, Any]]:
        """Parse script content into scene objects."""
        scenes = []

        # Split by ## Scene X: pattern
        scene_pattern = r'## Scene (\d+):\s*(.+?)(?=\n## Scene \d+:|\Z)'
        scene_matches = re.findall(scene_pattern, content, re.DOTALL)

        for scene_num, scene_content in scene_matches:
            scene_content = scene_content.strip()

            # Extract scene title (first line)
            title_match = re.match(r'^([^\n]+)', scene_content)
            scene_title = title_match.group(1).strip() if title_match else f"Scene {scene_num}"

            # Extract metadata
            location = ScriptParser._extract_field(scene_content, 'Location')
            time = ScriptParser._extract_field(scene_content, 'Time')
            purpose = ScriptParser._extract_field(scene_content, 'Purpose')
            emotional_beat = ScriptParser._extract_field(scene_content, 'Emotional Beat')

            # Extract tags
            char_tags = re.findall(r'\[(CHAR_[A-Z0-9_]+)\]', scene_content)
            loc_tags = re.findall(r'\[(LOC_[A-Z0-9_]+(?:_DIR_[NSEW])?)\]', scene_content)
            prop_tags = re.findall(r'\[(PROP_[A-Z0-9_]+)\]', scene_content)
            concept_tags = re.findall(r'\[(CONCEPT_[A-Z0-9_]+)\]', scene_content)
            event_tags = re.findall(r'\[(EVENT_[A-Z0-9_]+)\]', scene_content)
            env_tags = re.findall(r'\[(ENV_[A-Z0-9_]+)\]', scene_content)

            # Extract beats
            beats = ScriptParser._parse_beats(scene_content)

            scenes.append({
                'id': f"scene.{scene_num}",
                'number': int(scene_num),
                'title': scene_title,
                'content': scene_content,
                'location': location,
                'time': time,
                'purpose': purpose,
                'emotional_beat': emotional_beat,
                'beats': beats,
                'char_tags': list(set(char_tags)),
                'loc_tags': list(set(loc_tags)),
                'prop_tags': list(set(prop_tags)),
                'concept_tags': list(set(concept_tags)),
                'event_tags': list(set(event_tags)),
                'env_tags': list(set(env_tags)),
            })

        return scenes

    @staticmethod
    def _extract_field(content: str, field_name: str) -> str:
        """Extract a metadata field from content."""
        pattern = rf'\*\*{field_name}:\*\*\s*(.+?)(?=\n|\Z)'
        match = re.search(pattern, content)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _parse_beats(scene_content: str) -> List[Dict[str, Any]]:
        """Parse beats from scene content."""
        beats = []
        beat_pattern = r'### Beat (\d+)\s*\n(.+?)(?=\n### Beat \d+|\n## Scene \d+:|\Z)'
        beat_matches = re.findall(beat_pattern, scene_content, re.DOTALL)

        for beat_num, beat_content in beat_matches:
            beat_content = beat_content.strip()
            # First paragraph is the beat description
            beat_desc_match = re.match(r'^([^\n]+(?:\n(?!\*\*)[^\n]+)*)', beat_content)
            beat_desc = beat_desc_match.group(1).strip() if beat_desc_match else beat_content[:200]

            beats.append({
                'number': int(beat_num),
                'content': beat_content,
                'description': beat_desc
            })

        return beats


class VisualScriptParser:
    """
    Parser for visual_script.json files generated by the Director pipeline.

    Expected format:
    {
        "scenes": [
            {
                "scene_number": 1,
                "frames": [
                    {
                        "frame_id": "1.1.cA",
                        "prompt": "...",
                        "camera": {...},
                        "tags": [...]
                    }
                ]
            }
        ]
    }

    Or legacy format:
    [
        {"shot_id": "1.1", "prompt": "...", ...}
    ]
    """

    @staticmethod
    def parse(file_path: Path) -> List[Dict[str, Any]]:
        """Parse visual script JSON file into frame objects."""
        if not file_path.exists():
            return []

        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.error(f"Error parsing visual script: {e}")
            return []

        frames = []

        # Handle different JSON structures
        if isinstance(data, list):
            # Legacy format - flat list of frames
            frames = data
        elif "scenes" in data:
            # New Director output format
            for scene in data.get("scenes", []):
                frames.extend(scene.get("frames", []))
        else:
            # Try frames key directly
            frames = data.get("frames", [])

        return frames

    @staticmethod
    def find_visual_script(project_path: Path) -> Optional[Path]:
        """Find the visual script file in a project."""
        possible_paths = [
            project_path / "storyboard" / "visual_script.json",
            project_path / "storyboards" / "storyboard_prompts.json",
            project_path / "storyboard_output" / "visual_script.json",
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return None


class WorldConfigParser:
    """
    Parser for world_config.json files.

    Expected format:
    {
        "characters": [
            {"tag": "CHAR_MEI", "name": "Mei", "description": "...", ...}
        ],
        "locations": [...],
        "props": [...],
        "concepts": [...],
        "events": [...],
        "environments": [...]
    }
    """

    SECTIONS = ['characters', 'locations', 'props', 'concepts', 'events', 'environments']

    @staticmethod
    def parse(file_path: Path) -> Dict[str, Any]:
        """Parse world config JSON file."""
        if not file_path.exists():
            return {}

        try:
            return json.loads(file_path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.error(f"Error parsing world config: {e}")
            return {}

    @staticmethod
    def get_tag_icon(tag: str) -> str:
        """Get the appropriate icon for a tag based on its prefix."""
        if tag.startswith('CHAR_'):
            return "👤"
        elif tag.startswith('LOC_'):
            return "📍"
        elif tag.startswith('PROP_'):
            return "🎭"
        elif tag.startswith('CONCEPT_'):
            return "💡"
        elif tag.startswith('EVENT_'):
            return "⚡"
        elif tag.startswith('ENV_'):
            return "🌿"
        return "🏷️"

    @staticmethod
    def get_section_icon(section: str) -> str:
        """Get the icon for a world bible section."""
        icons = {
            'characters': '👤',
            'locations': '📍',
            'props': '🎭',
            'concepts': '💡',
            'events': '⚡',
            'environments': '🌿',
            'style_guide': '🎨',
        }
        return icons.get(section, '📁')


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_project_path(current_content: Dict[str, Any]) -> Optional[Path]:
    """
    Safely get project path from current content dict.

    Returns None if not set or invalid.
    """
    path = current_content.get('project_path')
    if not path:
        return None

    path = Path(path)
    if not path.exists():
        logger.warning(f"Project path does not exist: {path}")
        return None

    return path


def load_script_content(project_path: Path) -> Optional[str]:
    """Load script.md content from a project."""
    script_file = project_path / "scripts" / "script.md"
    if not script_file.exists():
        return None

    try:
        return script_file.read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"Error loading script: {e}")
        return None


def load_world_config(project_path: Path) -> Dict[str, Any]:
    """Load world_config.json from a project."""
    config_path = project_path / "world_bible" / "world_config.json"
    return WorldConfigParser.parse(config_path)

