"""
Greenlight Project Navigator

Left panel for navigating project hierarchy.
"""

import customtkinter as ctk
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
import json

from greenlight.ui.theme import theme
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.project_navigator")


class TreeNode:
    """A node in the project tree."""
    
    def __init__(
        self,
        name: str,
        node_type: str,
        path: str = "",
        children: List['TreeNode'] = None,
        icon: str = "📄"
    ):
        self.name = name
        self.node_type = node_type
        self.path = path
        self.children = children or []
        self.icon = icon
        self.expanded = False


class ProjectNavigator(ctk.CTkFrame):
    """
    Project navigation panel.

    Features:
    - Panel-based navigation (World Bible, Script, Storyboard, Editor)
    - Neon green navigation highlighting
    - Workflow progress tracking
    """

    # Navigation panels - each leads to a dedicated view
    NAV_PANELS = [
        ("world_bible", "🌍 World Bible", "Characters, locations, props"),
        ("script", "📜 Script", "View and edit story scenes"),
        ("storyboard", "🎬 Storyboard", "Visual storyboard frames"),
        ("editor", "✏️ Editor", "Coming soon"),
    ]

    def __init__(
        self,
        master,
        on_select: Callable[[TreeNode], None] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_select = on_select
        self._nodes: Dict[str, TreeNode] = {}
        self._selected_node: Optional[TreeNode] = None
        self._workflow_buttons: Dict[str, ctk.CTkButton] = {}
        self._current_workflow_step: str = "world_bible"
        self._completed_steps: set = set()

        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        # Configure frame - width increased by 50% (220 -> 330)
        self.configure(
            fg_color=theme.colors.bg_dark,
            corner_radius=0,
            width=330
        )

        # Header with project name
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.md)

        title = ctk.CTkLabel(
            header,
            text="Navigation",
            **theme.get_label_style("title")
        )
        title.pack(side="left")

        # Project name label (updated when project loads)
        self.project_label = ctk.CTkLabel(
            self,
            text="No project loaded",
            **theme.get_label_style("muted")
        )
        self.project_label.pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.md))

        # Navigation panels section
        nav_label = ctk.CTkLabel(
            self,
            text="📍 Panels",
            **theme.get_label_style("title")
        )
        nav_label.pack(fill="x", padx=theme.spacing.md, pady=(theme.spacing.md, theme.spacing.sm))

        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.md))

        for panel_id, panel_text, panel_desc in self.NAV_PANELS:
            # Editor is "coming soon" - disable it
            is_disabled = panel_id == "editor"

            btn = ctk.CTkButton(
                nav_frame,
                text=panel_text,
                command=lambda p=panel_id: self._on_panel_select(p),
                state="disabled" if is_disabled else "normal",
                **theme.get_button_style("secondary")
            )
            btn.pack(fill="x", pady=2)
            self._workflow_buttons[panel_id] = btn

            # Register with UI pointer system for OmniMind guidance
            self._register_workflow_button(panel_id, btn, panel_desc)

        # Highlight the first panel by default
        self._update_workflow_highlighting()

        # Spacer to push content up
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

    def _register_workflow_button(self, step_id: str, btn: ctk.CTkButton, description: str) -> None:
        """Register a workflow button with the UI pointer system."""
        try:
            from greenlight.ui.components.ui_pointer import register_element
            register_element(
                f"{step_id}_step",
                btn,
                description,
                category="workflow"
            )
        except ImportError:
            pass  # UI pointer not available
    
    def load_project(self, project_path: str) -> None:
        """Load a project into the navigator."""
        self._nodes.clear()
        project_path_obj = Path(project_path)

        # Update project label
        self.project_label.configure(text=f"📁 {project_path_obj.name}")

        # Store project path for panel navigation
        self._project_path = project_path_obj

        # Detect project type and store
        self._project_type = self._detect_project_type(project_path_obj)

        # Create root node for compatibility
        root = TreeNode(
            name=project_path_obj.name,
            node_type=self._project_type,
            path=project_path,
            icon="🎬" if self._project_type == "single" else "📺"
        )
        self._nodes[project_path] = root

    def _on_panel_select(self, panel_id: str) -> None:
        """Handle panel button click."""
        self._current_workflow_step = panel_id
        self._update_workflow_highlighting()

        # Create action node for the selected panel
        if self.on_select:
            if panel_id == "world_bible":
                node = TreeNode(
                    name="World Bible",
                    node_type="action",
                    path="__action__/world_bible",
                    icon="🌍"
                )
                self.on_select(node)
            elif panel_id == "script":
                node = TreeNode(
                    name="Script",
                    node_type="action",
                    path="__action__/script",
                    icon="📜"
                )
                self.on_select(node)
            elif panel_id == "storyboard":
                node = TreeNode(
                    name="Storyboard",
                    node_type="action",
                    path="__action__/storyboard",
                    icon="🎬"
                )
                self.on_select(node)
            elif panel_id == "editor":
                # Coming soon - do nothing
                pass
    def _detect_project_type(self, project_path: Path) -> str:
        """Detect if project is single or series."""
        # Check for project.json
        config_path = project_path / "project.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get("type", "single")
            except Exception as e:
                logger.warning(f"Could not read project.json: {e}")

        # Check for series structure (SEASON_XX folders)
        for item in project_path.iterdir():
            if item.is_dir() and item.name.startswith("SEASON_"):
                return "series"

        return "single"

    def _scan_project_structure(self, root: TreeNode, project_path: Path, project_type: str) -> None:
        """Scan project directory and build tree structure."""
        if project_type == "series":
            self._scan_series_structure(root, project_path)
        else:
            self._scan_single_structure(root, project_path)

    def _scan_single_structure(self, root: TreeNode, project_path: Path) -> None:
        """Scan single project structure."""
        # Define folder order and icons
        folder_config = [
            ("world_bible", "🌍", "World Bible"),
            ("story_documents", "📖", "Story Documents"),
            ("scripts", "📝", "Scripts"),
            ("beats", "🎵", "Beats"),
            ("shots", "🎬", "Shots"),
            ("prompts", "💬", "Prompts"),
            ("storyboard_output", "🎬", "Storyboard Output"),
            ("storyboards", "🖼️", "Storyboards"),
            ("characters", "👤", "Characters"),
            ("locations", "📍", "Locations"),
            ("assets", "🎨", "Assets"),
            ("references", "📚", "References"),
        ]

        for folder_name, icon, display_name in folder_config:
            folder_path = project_path / folder_name
            if folder_path.exists() and folder_path.is_dir():
                node = TreeNode(
                    name=display_name,
                    node_type="folder",
                    path=str(folder_path),
                    icon=icon
                )
                # Scan for files in this folder
                self._scan_folder_contents(node, folder_path)
                root.children.append(node)
                self._nodes[str(folder_path)] = node

    def _scan_series_structure(self, root: TreeNode, project_path: Path) -> None:
        """Scan series project structure."""
        # Add shared resources
        shared_path = project_path / "SHARED_RESOURCES"
        if shared_path.exists():
            shared_node = TreeNode(
                name="Shared Resources",
                node_type="folder",
                path=str(shared_path),
                icon="📦"
            )
            self._scan_folder_contents(shared_node, shared_path)
            root.children.append(shared_node)
            self._nodes[str(shared_path)] = shared_node

        # Add seasons
        seasons = sorted([d for d in project_path.iterdir()
                         if d.is_dir() and d.name.startswith("SEASON_")])

        for season_dir in seasons:
            season_node = TreeNode(
                name=season_dir.name.replace("_", " ").title(),
                node_type="season",
                path=str(season_dir),
                icon="📺"
            )

            # Add episodes
            episodes = sorted([d for d in season_dir.iterdir()
                             if d.is_dir() and d.name.startswith("EPISODE_")])

            for episode_dir in episodes:
                episode_node = TreeNode(
                    name=episode_dir.name.replace("_", " ").title(),
                    node_type="episode",
                    path=str(episode_dir),
                    icon="🎬"
                )
                self._scan_folder_contents(episode_node, episode_dir)
                season_node.children.append(episode_node)
                self._nodes[str(episode_dir)] = episode_node

            root.children.append(season_node)
            self._nodes[str(season_dir)] = season_node

    def _scan_folder_contents(self, parent_node: TreeNode, folder_path: Path, max_depth: int = 2) -> None:
        """Scan folder contents and add file nodes."""
        try:
            items = sorted(folder_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))

            for item in items:
                # Skip hidden files
                if item.name.startswith('.'):
                    continue

                # Determine icon based on file type
                if item.is_dir():
                    icon = "📁"
                    node_type = "folder"
                elif item.suffix == '.json':
                    icon = "📋"
                    node_type = "json"
                elif item.suffix == '.md':
                    icon = "📄"
                    node_type = "markdown"
                elif item.suffix in ['.txt', '.text']:
                    icon = "📝"
                    node_type = "text"
                elif item.suffix in ['.png', '.jpg', '.jpeg', '.webp']:
                    icon = "🖼️"
                    node_type = "image"
                else:
                    icon = "📄"
                    node_type = "file"

                node = TreeNode(
                    name=item.name,
                    node_type=node_type,
                    path=str(item),
                    icon=icon
                )

                parent_node.children.append(node)
                self._nodes[str(item)] = node

        except PermissionError:
            logger.warning(f"Permission denied accessing {folder_path}")
        except Exception as e:
            logger.error(f"Error scanning {folder_path}: {e}")

    # =========================================================================
    # OMNIMIND TOOLING METHODS (kept for programmatic access)
    # =========================================================================

    def _select_node(self, node: TreeNode) -> None:
        """Select a node programmatically."""
        self._selected_node = node
        if self.on_select:
            self.on_select(node)

    def search_nodes(self, query: str) -> List[TreeNode]:
        """Search nodes by name (for OmniMind tooling)."""
        query = query.lower().strip()
        matching_nodes = []
        for path, node in self._nodes.items():
            if query in node.name.lower():
                matching_nodes.append(node)
        return matching_nodes

    def get_node_by_path(self, path: str) -> Optional[TreeNode]:
        """Get a node by its path (for OmniMind tooling)."""
        return self._nodes.get(path)
    
    def add_node(
        self,
        parent_path: str,
        name: str,
        node_type: str,
        icon: str = "📄"
    ) -> TreeNode:
        """Add a node to the tree."""
        parent = self._nodes.get(parent_path)
        if parent:
            node = TreeNode(
                name=name,
                node_type=node_type,
                path=f"{parent_path}/{name}",
                icon=icon
            )
            parent.children.append(node)
            self._nodes[node.path] = node
            return node
        return None

    # =========================================================================
    # PANEL NAVIGATION WITH NEON GREEN HIGHLIGHTING
    # =========================================================================

    def _update_workflow_highlighting(self) -> None:
        """Update panel button highlighting - current gets green highlight."""
        for panel_id, btn in self._workflow_buttons.items():
            # Skip disabled buttons (editor)
            if panel_id == "editor":
                continue

            if panel_id == self._current_workflow_step:
                # Current selection - secondary style with neon green border
                btn.configure(
                    fg_color=theme.colors.bg_light,
                    hover_color=theme.colors.bg_hover,
                    text_color=theme.colors.neon_green,
                    border_width=2,
                    border_color=theme.colors.neon_green
                )
            elif panel_id in self._completed_steps:
                # Completed panel - secondary style with subtle indicator
                btn.configure(
                    fg_color=theme.colors.bg_light,
                    hover_color=theme.colors.bg_hover,
                    text_color=theme.colors.text_primary,
                    border_width=1,
                    border_color=theme.colors.neon_green_dim
                )
            else:
                # Inactive panel - default secondary style
                btn.configure(
                    fg_color=theme.colors.bg_light,
                    hover_color=theme.colors.bg_hover,
                    text_color=theme.colors.text_primary,
                    border_width=0
                )

    def set_panel(self, panel_id: str) -> None:
        """Set the current panel (called externally)."""
        if panel_id in [p[0] for p in self.NAV_PANELS]:
            self._current_workflow_step = panel_id
            self._update_workflow_highlighting()

    def complete_panel(self, panel_id: str) -> None:
        """Mark a panel as having content (completed)."""
        self._completed_steps.add(panel_id)
        self._update_workflow_highlighting()

    def get_navigation_state(self) -> Dict[str, Any]:
        """Get current navigation state."""
        panel_ids = [p[0] for p in self.NAV_PANELS]
        return {
            "current_panel": self._current_workflow_step,
            "completed_panels": list(self._completed_steps),
            "total_panels": len(panel_ids)
        }
