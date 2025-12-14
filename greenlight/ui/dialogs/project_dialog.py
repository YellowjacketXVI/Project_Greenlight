"""
Greenlight Project Dialogs

Dialogs for project creation and management.
"""

import customtkinter as ctk
from typing import Dict, Optional, Callable, Any
from pathlib import Path
from tkinter import filedialog

from greenlight.ui.theme import theme


class NewProjectDialog(ctk.CTkToplevel):
    """
    New project creation dialog.

    Features:
    - Project name and location
    - Template selection
    - Pitch/logline entry
    - Initial configuration
    """

    def __init__(
        self,
        master,
        on_create: Callable[[Dict], None] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_create = on_create

        # Get default projects folder (root/projects/)
        self.default_location = Path(__file__).parent.parent.parent.parent / "projects"
        self.default_location.mkdir(exist_ok=True)

        self.title("New Project")
        self.geometry("600x550")
        self.resizable(False, False)

        self.transient(master)
        self.grab_set()

        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.configure(fg_color=theme.colors.bg_medium)

        # Title
        title = ctk.CTkLabel(
            self, text="Create New Project",
            **theme.get_label_style("title")
        )
        title.pack(pady=theme.spacing.lg)

        # Scrollable form for more fields
        form = ctk.CTkScrollableFrame(self, fg_color="transparent", height=420)
        form.pack(fill="both", expand=True, padx=theme.spacing.xl)

        # Project name
        ctk.CTkLabel(form, text="Project Name *", **theme.get_label_style()).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(
            form, placeholder_text="My Storyboard Project",
            **theme.get_entry_style()
        )
        self.name_entry.pack(fill="x", pady=(theme.spacing.xs, theme.spacing.md))

        # Location - default to projects folder
        ctk.CTkLabel(form, text="Location", **theme.get_label_style()).pack(anchor="w")

        loc_frame = ctk.CTkFrame(form, fg_color="transparent")
        loc_frame.pack(fill="x", pady=(theme.spacing.xs, theme.spacing.md))

        self.location_var = ctk.StringVar(value=str(self.default_location))
        self.location_entry = ctk.CTkEntry(
            loc_frame, textvariable=self.location_var,
            **theme.get_entry_style()
        )
        self.location_entry.pack(side="left", fill="x", expand=True)

        browse_btn = ctk.CTkButton(
            loc_frame, text="Browse", width=80,
            command=self._browse_location,
            **theme.get_button_style("secondary")
        )
        browse_btn.pack(side="right", padx=(theme.spacing.sm, 0))

        # Template
        ctk.CTkLabel(form, text="Template", **theme.get_label_style()).pack(anchor="w")
        self.template_var = ctk.StringVar(value="feature_film")
        template_menu = ctk.CTkOptionMenu(
            form, values=["blank", "feature_film", "series", "short_film", "music_video", "commercial"],
            variable=self.template_var
        )
        template_menu.pack(fill="x", pady=(theme.spacing.xs, theme.spacing.md))

        # === PITCH / STORY SECTION ===
        pitch_header = ctk.CTkLabel(
            form, text="📝 Story & Pitch",
            font=(theme.fonts.family, theme.fonts.size_large, "bold"),
            text_color=theme.colors.accent
        )
        pitch_header.pack(anchor="w", pady=(theme.spacing.md, theme.spacing.xs))

        # Logline
        ctk.CTkLabel(form, text="Logline (1-2 sentences)", **theme.get_label_style()).pack(anchor="w")
        self.logline_entry = ctk.CTkEntry(
            form, placeholder_text="A [protagonist] must [goal] before [stakes]...",
            **theme.get_entry_style()
        )
        self.logline_entry.pack(fill="x", pady=(theme.spacing.xs, theme.spacing.md))

        # Genre
        ctk.CTkLabel(form, text="Genre", **theme.get_label_style()).pack(anchor="w")
        self.genre_var = ctk.StringVar(value="Drama")
        genre_menu = ctk.CTkOptionMenu(
            form, values=["Drama", "Comedy", "Action", "Thriller", "Horror", "Sci-Fi", "Fantasy", "Romance", "Documentary", "Animation"],
            variable=self.genre_var
        )
        genre_menu.pack(fill="x", pady=(theme.spacing.xs, theme.spacing.md))

        # Synopsis / Pitch
        ctk.CTkLabel(form, text="Synopsis / Pitch", **theme.get_label_style()).pack(anchor="w")
        self.pitch_entry = ctk.CTkTextbox(
            form, height=100,
            fg_color=theme.colors.bg_dark
        )
        self.pitch_entry.pack(fill="x", pady=(theme.spacing.xs, theme.spacing.md))
        self.pitch_entry.insert("1.0", "Describe your story idea here. Include main characters, setting, and the central conflict...")
        self.pitch_entry.bind("<FocusIn>", self._clear_pitch_placeholder)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=theme.spacing.xl, pady=theme.spacing.lg)

        cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            command=self.destroy,
            **theme.get_button_style("secondary")
        )
        cancel_btn.pack(side="right", padx=theme.spacing.sm)

        create_btn = ctk.CTkButton(
            btn_frame, text="Create Project", width=120,
            command=self._create_project,
            **theme.get_button_style("primary")
        )
        create_btn.pack(side="right")

    def _clear_pitch_placeholder(self, event=None):
        """Clear placeholder text on focus."""
        current = self.pitch_entry.get("1.0", "end-1c")
        if current.startswith("Describe your story idea"):
            self.pitch_entry.delete("1.0", "end")
    
    def _browse_location(self) -> None:
        """Browse for project location."""
        path = filedialog.askdirectory(title="Select Project Location")
        if path:
            self.location_var.set(path)
    
    def _create_project(self) -> None:
        """Create the project."""
        name = self.name_entry.get().strip()
        location = self.location_var.get().strip()

        if not name:
            # Show error - name is required
            return

        # Use default location if not specified
        if not location:
            location = str(self.default_location)

        # Get pitch content, excluding placeholder
        pitch_content = self.pitch_entry.get("1.0", "end-1c")
        if pitch_content.startswith("Describe your story idea"):
            pitch_content = ""

        project_data = {
            'name': name,
            'location': location,
            'template': self.template_var.get(),
            'logline': self.logline_entry.get().strip(),
            'genre': self.genre_var.get(),
            'pitch': pitch_content,
        }

        if self.on_create:
            self.on_create(project_data)

        self.destroy()


class OpenProjectDialog(ctk.CTkToplevel):
    """
    Open existing project dialog.
    
    Features:
    - Recent projects list
    - Browse for project
    """
    
    def __init__(
        self,
        master,
        recent_projects: list = None,
        on_open: Callable[[str], None] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        
        self.recent_projects = recent_projects or []
        self.on_open = on_open
        
        self.title("Open Project")
        self.geometry("450x350")
        self.resizable(False, False)
        
        self.transient(master)
        self.grab_set()
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.configure(fg_color=theme.colors.bg_medium)
        
        # Title
        title = ctk.CTkLabel(
            self, text="Open Project",
            **theme.get_label_style("title")
        )
        title.pack(pady=theme.spacing.lg)
        
        # Recent projects
        ctk.CTkLabel(
            self, text="Recent Projects",
            **theme.get_label_style()
        ).pack(anchor="w", padx=theme.spacing.xl)
        
        recent_frame = ctk.CTkScrollableFrame(
            self, fg_color=theme.colors.bg_dark, height=150
        )
        recent_frame.pack(fill="x", padx=theme.spacing.xl, pady=theme.spacing.sm)
        
        if self.recent_projects:
            for project in self.recent_projects:
                btn = ctk.CTkButton(
                    recent_frame, text=project,
                    anchor="w", fg_color="transparent",
                    hover_color=theme.colors.bg_hover,
                    command=lambda p=project: self._open_project(p)
                )
                btn.pack(fill="x", pady=1)
        else:
            ctk.CTkLabel(
                recent_frame, text="No recent projects",
                **theme.get_label_style("muted")
            ).pack(pady=theme.spacing.md)
        
        # Browse button
        browse_btn = ctk.CTkButton(
            self, text="Browse for Project...", width=200,
            command=self._browse_project,
            **theme.get_button_style("secondary")
        )
        browse_btn.pack(pady=theme.spacing.lg)
        
        # Cancel
        cancel_btn = ctk.CTkButton(
            self, text="Cancel", width=100,
            command=self.destroy,
            **theme.get_button_style("secondary")
        )
        cancel_btn.pack(pady=theme.spacing.sm)
    
    def _browse_project(self) -> None:
        """Browse for a project folder."""
        path = filedialog.askdirectory(title="Select Project Folder")
        if path:
            self._open_project(path)
    
    def _open_project(self, path: str) -> None:
        """Open the selected project."""
        if self.on_open:
            self.on_open(path)
        self.destroy()

