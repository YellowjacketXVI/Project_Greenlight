"""
Greenlight Project Wizard - Multi-step project creation dialog.

Steps:
1. Project name + type (single/series)
2. Pitch input (logline, synopsis)
3. Options (project size, LLM selector)
4. Create with progress
"""

import customtkinter as ctk
from typing import Dict, Callable, Optional, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
import json
from datetime import datetime

from greenlight.ui.theme import theme
from greenlight.llm.llm_registry import list_available_llms, get_llm_by_id


class ProjectWizard(ctk.CTkToplevel):
    """Multi-step wizard for creating new projects."""

    # Project size presets
    PROJECT_PRESETS = {
        "micro": {"name": "Micro (30s-1min)", "total_words": 500, "scenes": 3},
        "short": {"name": "Short (2-4min)", "total_words": 2000, "scenes": 8},
        "medium": {"name": "Medium (5-10min)", "total_words": 5000, "scenes": 15},
        "feature": {"name": "Feature (20-30min)", "total_words": 15000, "scenes": 40},
    }

    def __init__(
        self,
        parent,
        on_complete: Callable[[Dict], None] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)

        self.on_complete = on_complete
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.cancelled = threading.Event()
        self.running = False

        # Default projects folder
        self.default_location = Path(__file__).parent.parent.parent.parent / "projects"
        self.default_location.mkdir(exist_ok=True)

        # Wizard state
        self.current_step = 0
        self.project_data = {
            "name": "",
            "type": "single",
            "logline": "",
            "pitch": "",
            "genre": "Drama",
            "project_size": "short",
            "llm_id": "claude-sonnet",
            "run_writer": True,
            "location": str(self.default_location),
        }

        # Window setup
        self.title("New Project Wizard")
        self.geometry("700x600")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")

        self.configure(fg_color=theme.colors.bg_medium)

        # Configure grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._create_header()
        self._create_content_area()
        self._create_navigation()

        # Show first step
        self._show_step(0)

    def _create_header(self) -> None:
        """Create the wizard header with step indicators."""
        header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color=theme.colors.bg_dark)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.step_labels = []
        steps = ["1. Name & Type", "2. Pitch", "3. Options", "4. Create"]

        for i, step in enumerate(steps):
            label = ctk.CTkLabel(
                header, text=step,
                font=(theme.fonts.family, theme.fonts.size_normal, "bold" if i == 0 else "normal"),
                text_color=theme.colors.accent if i == 0 else theme.colors.text_muted
            )
            label.grid(row=0, column=i, padx=10, pady=15)
            self.step_labels.append(label)

    def _create_content_area(self) -> None:
        """Create the main content area for step content."""
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Create frames for each step
        self.step_frames = []
        for i in range(4):
            frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
            self.step_frames.append(frame)

        self._create_step1()
        self._create_step2()
        self._create_step3()
        self._create_step4()

    def _create_navigation(self) -> None:
        """Create the navigation buttons."""
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=15)
        nav_frame.grid_columnconfigure(1, weight=1)

        self.btn_back = ctk.CTkButton(
            nav_frame, text="← Back", width=100,
            fg_color="transparent", border_width=1,
            border_color=theme.colors.border,
            command=self._on_back
        )
        self.btn_back.grid(row=0, column=0)

        self.btn_cancel = ctk.CTkButton(
            nav_frame, text="Cancel", width=100,
            fg_color="transparent", border_width=1,
            border_color=theme.colors.border,
            command=self._on_cancel
        )
        self.btn_cancel.grid(row=0, column=1, padx=10)

        self.btn_next = ctk.CTkButton(
            nav_frame, text="Next →", width=100,
            fg_color=theme.colors.accent,
            hover_color=theme.colors.accent_hover,
            command=self._on_next
        )
        self.btn_next.grid(row=0, column=2)

    def _create_step1(self) -> None:
        """Step 1: Project name and type."""
        frame = self.step_frames[0]

        # Title
        title = ctk.CTkLabel(
            frame, text="Create New Project",
            font=(theme.fonts.family, theme.fonts.size_header, "bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(pady=(20, 20))

        # Project name
        name_label = ctk.CTkLabel(frame, text="Project Name:", anchor="w",
                                   text_color=theme.colors.text_primary)
        name_label.pack(fill="x", padx=20)

        self.name_entry = ctk.CTkEntry(
            frame, placeholder_text="My Awesome Project",
            fg_color=theme.colors.bg_dark
        )
        self.name_entry.pack(fill="x", padx=20, pady=(5, 15))

        # Project type with better descriptions
        type_label = ctk.CTkLabel(frame, text="Project Type:", anchor="w",
                                   text_color=theme.colors.text_primary)
        type_label.pack(fill="x", padx=20)

        self.type_var = ctk.StringVar(value="single")
        self.type_var.trace_add("write", self._on_type_change)

        # Type selection frame
        type_frame = ctk.CTkFrame(frame, fg_color=theme.colors.bg_dark, corner_radius=8)
        type_frame.pack(fill="x", padx=20, pady=(5, 10))

        # Single project option
        single_frame = ctk.CTkFrame(type_frame, fg_color="transparent")
        single_frame.pack(fill="x", padx=10, pady=8)

        single_radio = ctk.CTkRadioButton(
            single_frame, text="🎬 Single Project (Film/Short)",
            variable=self.type_var, value="single",
            text_color=theme.colors.text_primary,
            font=(theme.fonts.family, theme.fonts.size_normal, "bold")
        )
        single_radio.pack(anchor="w")

        single_desc = ctk.CTkLabel(
            single_frame,
            text="    Standalone story with one script, one storyboard output",
            text_color=theme.colors.text_muted,
            font=(theme.fonts.family, theme.fonts.size_small)
        )
        single_desc.pack(anchor="w")

        # Series option
        series_frame = ctk.CTkFrame(type_frame, fg_color="transparent")
        series_frame.pack(fill="x", padx=10, pady=(0, 8))

        series_radio = ctk.CTkRadioButton(
            series_frame, text="📺 Series (Multiple Episodes)",
            variable=self.type_var, value="series",
            text_color=theme.colors.text_primary,
            font=(theme.fonts.family, theme.fonts.size_normal, "bold")
        )
        series_radio.pack(anchor="w")

        series_desc = ctk.CTkLabel(
            series_frame,
            text="    Season/Episode hierarchy with shared world bible & characters",
            text_color=theme.colors.text_muted,
            font=(theme.fonts.family, theme.fonts.size_small)
        )
        series_desc.pack(anchor="w")

        # Series configuration (hidden by default)
        self.series_config_frame = ctk.CTkFrame(frame, fg_color=theme.colors.bg_dark, corner_radius=8)

        series_config_label = ctk.CTkLabel(
            self.series_config_frame, text="Series Configuration:",
            text_color=theme.colors.text_primary, anchor="w"
        )
        series_config_label.pack(fill="x", padx=10, pady=(10, 5))

        config_row = ctk.CTkFrame(self.series_config_frame, fg_color="transparent")
        config_row.pack(fill="x", padx=10, pady=(0, 10))

        # Number of seasons
        ctk.CTkLabel(config_row, text="Seasons:", text_color=theme.colors.text_secondary).pack(side="left")
        self.seasons_var = ctk.StringVar(value="1")
        self.seasons_spin = ctk.CTkOptionMenu(
            config_row, values=["1", "2", "3", "4", "5"],
            variable=self.seasons_var, width=60, fg_color=theme.colors.bg_medium
        )
        self.seasons_spin.pack(side="left", padx=(5, 20))

        # Episodes per season
        ctk.CTkLabel(config_row, text="Episodes/Season:", text_color=theme.colors.text_secondary).pack(side="left")
        self.episodes_var = ctk.StringVar(value="6")
        self.episodes_spin = ctk.CTkOptionMenu(
            config_row, values=["3", "4", "5", "6", "8", "10", "12", "13", "22"],
            variable=self.episodes_var, width=60, fg_color=theme.colors.bg_medium
        )
        self.episodes_spin.pack(side="left", padx=5)

        # Genre
        genre_label = ctk.CTkLabel(frame, text="Genre:", anchor="w",
                                    text_color=theme.colors.text_primary)
        genre_label.pack(fill="x", padx=20, pady=(10, 0))

        self.genre_var = ctk.StringVar(value="Drama")
        genre_menu = ctk.CTkOptionMenu(
            frame,
            values=["Drama", "Comedy", "Action", "Thriller", "Horror",
                    "Sci-Fi", "Fantasy", "Romance", "Documentary", "Animation",
                    "Mystery", "Adventure", "Crime", "Western", "Musical"],
            variable=self.genre_var,
            fg_color=theme.colors.bg_dark
        )
        genre_menu.pack(fill="x", padx=20, pady=(5, 10))

        # Info text (dynamic based on type)
        self.type_info = ctk.CTkLabel(
            frame,
            text="💡 Single projects create one complete storyboard pipeline.",
            text_color=theme.colors.text_muted,
            justify="left"
        )
        self.type_info.pack(fill="x", padx=20, pady=(10, 0))

    def _on_type_change(self, *args) -> None:
        """Handle project type change."""
        if self.type_var.get() == "series":
            self.series_config_frame.pack(fill="x", padx=20, pady=(5, 0), after=self.step_frames[0].winfo_children()[4])
            self.type_info.configure(
                text="💡 Series projects share a world bible across all episodes.\n"
                     "   Characters, locations, and lore persist throughout."
            )
        else:
            self.series_config_frame.pack_forget()
            self.type_info.configure(
                text="💡 Single projects create one complete storyboard pipeline."
            )

    def _create_step2(self) -> None:
        """Step 2: Pitch input."""
        frame = self.step_frames[1]

        # Title
        title = ctk.CTkLabel(
            frame, text="Enter Your Pitch",
            font=(theme.fonts.family, theme.fonts.size_header, "bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(pady=(20, 10))

        # Logline
        logline_label = ctk.CTkLabel(
            frame, text="Logline (1-2 sentences):",
            text_color=theme.colors.text_primary, anchor="w"
        )
        logline_label.pack(fill="x", padx=20)

        self.logline_entry = ctk.CTkEntry(
            frame, placeholder_text="A [protagonist] must [goal] before [stakes]...",
            fg_color=theme.colors.bg_dark
        )
        self.logline_entry.pack(fill="x", padx=20, pady=(5, 15))

        # Instructions
        instructions = ctk.CTkLabel(
            frame,
            text="Describe your story concept. Include characters, setting, and plot.",
            text_color=theme.colors.text_muted,
            justify="center"
        )
        instructions.pack(pady=(0, 10))

        # Pitch text area
        self.pitch_text = ctk.CTkTextbox(
            frame, height=200, wrap="word",
            fg_color=theme.colors.bg_dark,
            text_color=theme.colors.text_primary
        )
        self.pitch_text.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Example button
        example_btn = ctk.CTkButton(
            frame, text="📝 Load Example Pitch",
            fg_color="transparent", border_width=1,
            border_color=theme.colors.border,
            command=self._load_example_pitch
        )
        example_btn.pack(pady=(0, 10))

    def _load_example_pitch(self) -> None:
        """Load an example pitch into the text area."""
        example = """A young lighthouse keeper named Elena discovers that the light she tends
doesn't just guide ships—it keeps ancient sea creatures at bay. When the light
begins to flicker and fail, she must venture into the depths to find a new power
source before the creatures reclaim the coast.

Characters:
- Elena: 28, determined, carries her father's legacy
- The Keeper: A mysterious figure who appears in her dreams
- Captain Marsh: An old sailor who knows the truth

Setting: A remote lighthouse on a rocky coast, 1920s aesthetic with
supernatural undertones. Stormy seas, fog-shrouded cliffs, and an
underwater realm of bioluminescent creatures."""

        self.pitch_text.delete("1.0", "end")
        self.pitch_text.insert("1.0", example)
        self.logline_entry.delete(0, "end")
        self.logline_entry.insert(0, "A lighthouse keeper must descend into the depths to save her coast from ancient sea creatures.")

    def _create_step3(self) -> None:
        """Step 3: Options (project size, LLM)."""
        frame = self.step_frames[2]

        # Title
        title = ctk.CTkLabel(
            frame, text="Project Options",
            font=(theme.fonts.family, theme.fonts.size_header, "bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(pady=(20, 30))

        # Project size
        size_label = ctk.CTkLabel(frame, text="Project Size:", anchor="w",
                                   text_color=theme.colors.text_primary)
        size_label.pack(fill="x", padx=20)

        size_options = [f"{v['name']}" for v in self.PROJECT_PRESETS.values()]
        self.size_dropdown = ctk.CTkOptionMenu(
            frame, values=size_options, width=400,
            fg_color=theme.colors.bg_dark
        )
        self.size_dropdown.set(size_options[1])  # Default to short
        self.size_dropdown.pack(fill="x", padx=20, pady=(5, 20))

        # LLM selector
        llm_label = ctk.CTkLabel(frame, text="AI Model:", anchor="w",
                                  text_color=theme.colors.text_primary)
        llm_label.pack(fill="x", padx=20)

        # Build LLM options
        llm_list = list_available_llms()
        self.llm_options = []
        self.llm_map = {}
        for llm in llm_list:
            display = f"{llm.name}"
            self.llm_options.append(display)
            self.llm_map[display] = llm.id

        if not self.llm_options:
            self.llm_options = ["No LLMs configured"]

        self.llm_dropdown = ctk.CTkOptionMenu(
            frame, values=self.llm_options, width=400,
            fg_color=theme.colors.bg_dark
        )
        self.llm_dropdown.set(self.llm_options[0])
        self.llm_dropdown.pack(fill="x", padx=20, pady=(5, 20))

        # Run writer checkbox
        self.run_writer_var = ctk.BooleanVar(value=True)
        writer_check = ctk.CTkCheckBox(
            frame,
            text="Run Writer after creation\n(generates story, beats, shot list)",
            variable=self.run_writer_var,
            text_color=theme.colors.text_primary
        )
        writer_check.pack(fill="x", padx=20, pady=(10, 0))

    def _create_step4(self) -> None:
        """Step 4: Creation progress."""
        frame = self.step_frames[3]

        # Title
        title = ctk.CTkLabel(
            frame, text="Creating Project...",
            font=(theme.fonts.family, theme.fonts.size_header, "bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(pady=(20, 30))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(frame, width=400)
        self.progress_bar.pack(pady=20)
        self.progress_bar.set(0)

        # Status label
        self.progress_label = ctk.CTkLabel(
            frame, text="Preparing...",
            text_color=theme.colors.text_muted
        )
        self.progress_label.pack(pady=10)

        # Log area
        self.log_text = ctk.CTkTextbox(
            frame, height=200, wrap="word",
            fg_color=theme.colors.bg_dark,
            text_color=theme.colors.text_secondary
        )
        self.log_text.pack(fill="both", expand=True, padx=20, pady=10)

    def _show_step(self, step: int) -> None:
        """Show the specified step."""
        # Hide all frames
        for f in self.step_frames:
            f.grid_remove()

        # Show current frame
        self.step_frames[step].grid(row=0, column=0, sticky="nsew")

        # Update header
        for i, label in enumerate(self.step_labels):
            if i == step:
                label.configure(
                    font=(theme.fonts.family, theme.fonts.size_normal, "bold"),
                    text_color=theme.colors.accent
                )
            elif i < step:
                label.configure(
                    font=(theme.fonts.family, theme.fonts.size_normal, "normal"),
                    text_color=theme.colors.success
                )
            else:
                label.configure(
                    font=(theme.fonts.family, theme.fonts.size_normal, "normal"),
                    text_color=theme.colors.text_muted
                )

        # Update navigation buttons
        self.btn_back.configure(state="normal" if step > 0 else "disabled")

        if step == 3:
            self.btn_next.configure(text="Create", state="disabled")
            self._start_creation()
        elif step == 2:
            self.btn_next.configure(text="Create →", state="normal")
        else:
            self.btn_next.configure(text="Next →", state="normal")

        self.current_step = step

    def _on_next(self) -> None:
        """Handle next button click."""
        # Validate current step
        if self.current_step == 0:
            name = self.name_entry.get().strip()
            if not name:
                return
            self.project_data["name"] = name
            self.project_data["type"] = self.type_var.get()
            self.project_data["genre"] = self.genre_var.get()

            # Series configuration
            if self.type_var.get() == "series":
                self.project_data["seasons"] = int(self.seasons_var.get())
                self.project_data["episodes_per_season"] = int(self.episodes_var.get())
            else:
                self.project_data["seasons"] = 0
                self.project_data["episodes_per_season"] = 0

        elif self.current_step == 1:
            self.project_data["logline"] = self.logline_entry.get().strip()
            self.project_data["pitch"] = self.pitch_text.get("1.0", "end-1c")

        elif self.current_step == 2:
            # Get selected LLM
            selected = self.llm_dropdown.get()
            self.project_data["llm_id"] = self.llm_map.get(selected, "claude-sonnet")
            self.project_data["run_writer"] = self.run_writer_var.get()

        # Move to next step
        if self.current_step < 3:
            self._show_step(self.current_step + 1)

    def _on_back(self) -> None:
        """Handle back button click."""
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _on_cancel(self) -> None:
        """Handle cancel button click."""
        self.cancelled.set()
        self.destroy()

    def _start_creation(self) -> None:
        """Start the project creation process."""
        self.running = True
        self.btn_cancel.configure(text="Cancel", command=self._on_cancel)

        def create_project():
            try:
                from greenlight.core.constants import (
                    PROJECT_BASE_DIRS, PROJECT_SINGLE_DIRS, PROJECT_EPISODE_DIRS,
                    PROJECT_SYSTEM_DIRS, SEASONS_DIR_PREFIX, EPISODES_DIR_PREFIX
                )

                is_series = self.project_data["type"] == "series"
                self._log(f"📁 Creating {'series' if is_series else 'project'} structure...")
                self._update_progress(0.1)

                # Create project folder
                project_path = Path(self.project_data["location"]) / self.project_data["name"]
                project_path.mkdir(parents=True, exist_ok=True)

                # Base folders (shared across all episodes for series)
                for folder in PROJECT_BASE_DIRS:
                    (project_path / folder).mkdir(exist_ok=True)

                # System directories
                for folder in PROJECT_SYSTEM_DIRS:
                    (project_path / folder).mkdir(exist_ok=True)

                if is_series:
                    # Create series structure: SEASON_XX/EPISODE_XX
                    seasons = self.project_data.get("seasons", 1)
                    episodes = self.project_data.get("episodes_per_season", 6)

                    for s in range(1, seasons + 1):
                        season_path = project_path / f"{SEASONS_DIR_PREFIX}{s:02d}"
                        season_path.mkdir(exist_ok=True)

                        # Season-level files
                        (season_path / "season_arc.md").write_text(f"# Season {s} Arc\n\n## Overview\n\n## Episode Breakdown\n\n")

                        for e in range(1, episodes + 1):
                            ep_path = season_path / f"{EPISODES_DIR_PREFIX}{e:02d}"
                            ep_path.mkdir(exist_ok=True)

                            # Episode subfolders
                            for subfolder in PROJECT_EPISODE_DIRS:
                                (ep_path / subfolder).mkdir(exist_ok=True)

                            # Episode config
                            ep_config = {
                                "episode_number": e,
                                "season_number": s,
                                "title": f"Episode {e}",
                                "status": "not_started"
                            }
                            (ep_path / "episode.json").write_text(json.dumps(ep_config, indent=2))

                    self._log(f"✓ Created {seasons} season(s) with {episodes} episodes each")
                else:
                    # Single project folders
                    for folder in PROJECT_SINGLE_DIRS:
                        (project_path / folder).mkdir(exist_ok=True)
                    self._log("✓ Folder structure created")

                self._update_progress(0.3)

                # Create project.json
                self._log("📝 Creating project configuration...")
                config = {
                    "name": self.project_data["name"],
                    "type": self.project_data["type"],
                    "genre": self.project_data["genre"],
                    "logline": self.project_data["logline"],
                    "llm_id": self.project_data["llm_id"],
                    "created": datetime.now().isoformat(),
                    "path": str(project_path),
                    "version": "2.0.0",
                }
                if is_series:
                    config["seasons"] = self.project_data.get("seasons", 1)
                    config["episodes_per_season"] = self.project_data.get("episodes_per_season", 6)

                config_file = project_path / "project.json"
                config_file.write_text(json.dumps(config, indent=2))
                self._update_progress(0.5)

                # Create pitch.md in world_bible
                self._log("📖 Creating pitch document...")
                pitch_content = f"""# {self.project_data["name"]}

## Logline
{self.project_data["logline"]}

## Genre
{self.project_data["genre"]}

## Type
{"Series" if is_series else "Single Project"}

## Synopsis
{self.project_data["pitch"]}

## Characters
(To be developed - add character entries with [CHARACTER_NAME] tags)

## Locations
(To be developed - add location entries with [LOC_NAME] tags)

## Themes
(To be developed)

## World Rules
(Define any special rules, magic systems, technology, etc.)
"""
                pitch_file = project_path / "world_bible" / "pitch.md"
                pitch_file.write_text(pitch_content)
                self._update_progress(0.7)

                # Create script template
                self._log("📜 Creating script template...")
                if is_series:
                    # Create pilot episode script
                    script_path = project_path / "SEASON_01" / "EPISODE_01" / "scripts" / "script.md"
                    script_content = f"# {self.project_data['name']} - S01E01\n\n## TEASER\n\n### Scene 1\n\n## ACT 1\n\n### Scene 2\n\n"
                else:
                    script_path = project_path / "scripts" / "script.md"
                    script_content = f"# {self.project_data['name']} - Script\n\n## ACT 1\n\n### Scene 1\n\n## ACT 2\n\n### Scene 2\n\n## ACT 3\n\n### Scene 3\n\n"

                script_path.write_text(script_content)
                self._update_progress(0.9)

                self._log("✅ Project created successfully!")
                self._update_progress(1.0)

                # Call completion callback
                if self.on_complete and not self.cancelled.is_set():
                    self.after(500, lambda: self._complete(str(project_path)))

            except Exception as e:
                self._log(f"❌ Error: {e}")

        # Run in background thread
        self.executor.submit(create_project)

    def _log(self, message: str) -> None:
        """Add a log message."""
        def update():
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.progress_label.configure(text=message)
        self.after(0, update)

    def _update_progress(self, value: float) -> None:
        """Update progress bar."""
        def update():
            self.progress_bar.set(value)
        self.after(0, update)

    def _complete(self, project_path: str) -> None:
        """Handle completion."""
        self.running = False
        self.btn_next.configure(text="Done", state="normal", command=self.destroy)
        self.btn_cancel.configure(state="disabled")

        if self.on_complete:
            self.on_complete({"path": project_path, **self.project_data})
