"""
Writer Configuration Dialog - Collects settings and returns them.

This is a simple config dialog that closes after the user clicks "Start".
The actual pipeline execution happens in the main window with progress
displayed in the pipeline panel.
"""

import customtkinter as ctk
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from greenlight.ui.theme import theme
from greenlight.llm.llm_registry import list_available_llms
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.writer_config_dialog")


class WriterConfigDialog(ctk.CTkToplevel):
    """Dialog for configuring the Writer pipeline."""

    PROJECT_PRESETS = {
        "short": {"name": "Short (100-150 words)", "total_words": 125, "scenes": 2, "shots": 5, "media_type": "short"},
        "brief": {"name": "Brief (250-500 words)", "total_words": 375, "scenes": 4, "shots": 12, "media_type": "brief"},
        "standard": {"name": "Standard (750-1000 words)", "total_words": 875, "scenes": 6, "shots": 20, "media_type": "standard"},
        "extended": {"name": "Extended (1250-1500 words)", "total_words": 1375, "scenes": 10, "shots": 35, "media_type": "extended"},
        "feature": {"name": "Feature (2000-3000 words)", "total_words": 2500, "scenes": 15, "shots": 60, "media_type": "feature"},
    }

    # Story Mode is always Assembly (7 parallel agents + 5 judges consensus)
    # Removed standard/enhanced dropdown - assembly is the only mode

    DIRECTING_MODES = {"scene": "By Scene", "beat": "By Beat", "outline": "Outline First"}
    DIRECTING_MODE_MAP = {"By Scene": "scene_chunked", "By Beat": "beat_chunked", "Outline First": "expansion"}

    VISUAL_STYLE_OPTIONS = ["Live Action", "Anime", "2D Animation", "3D Animation", "Mixed Reality"]
    VISUAL_STYLE_MAP = {
        "Live Action": "live_action", "Anime": "anime", "2D Animation": "animation_2d",
        "3D Animation": "animation_3d", "Mixed Reality": "mixed_reality"
    }

    def __init__(self, parent, project_path: Path, on_start: Callable[[Dict[str, Any]], None] = None, **kwargs):
        super().__init__(parent, **kwargs)

        self.project_path = project_path
        self.on_start = on_start
        self.result: Optional[Dict[str, Any]] = None

        self.title("Writer Pipeline Configuration")
        self.geometry("550x580")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 550) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 580) // 2
        self.geometry(f"+{x}+{y}")

        self.configure(fg_color=theme.colors.bg_medium)
        self._create_ui()

    def _create_ui(self) -> None:
        """Create the dialog UI."""
        # Title
        title = ctk.CTkLabel(
            self, text="Writer Pipeline",
            font=(theme.fonts.family, theme.fonts.size_header, "bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(pady=(20, 5))

        desc = ctk.CTkLabel(
            self, text="Configure and start the story generation pipeline.",
            text_color=theme.colors.text_secondary
        )
        desc.pack(pady=(0, 15))

        # Pitch preview
        pitch_frame = ctk.CTkFrame(self, fg_color=theme.colors.bg_dark)
        pitch_frame.pack(fill="x", padx=30, pady=5)

        pitch_label = ctk.CTkLabel(pitch_frame, text="📝 Pitch:", text_color=theme.colors.text_primary, anchor="w")
        pitch_label.pack(fill="x", padx=15, pady=(10, 5))

        pitch_content = self._load_pitch_content()
        self.pitch_preview = ctk.CTkTextbox(pitch_frame, height=100, wrap="word", fg_color=theme.colors.bg_medium)
        self.pitch_preview.pack(fill="x", padx=15, pady=(0, 10))
        self.pitch_preview.insert("1.0", pitch_content or "No pitch found.")
        self.pitch_preview.configure(state="disabled")

        # Options grid
        options_frame = ctk.CTkFrame(self, fg_color=theme.colors.bg_dark)
        options_frame.pack(fill="x", padx=30, pady=10)
        options_frame.grid_columnconfigure(0, weight=1)
        options_frame.grid_columnconfigure(1, weight=1)

        # Row 0: Project Size & LLM
        ctk.CTkLabel(options_frame, text="Project Size:", text_color=theme.colors.text_primary).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        size_options = [v['name'] for v in self.PROJECT_PRESETS.values()]
        self.size_dropdown = ctk.CTkOptionMenu(options_frame, values=size_options, fg_color=theme.colors.bg_medium, width=180)
        self.size_dropdown.set(size_options[2])
        self.size_dropdown.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")

        ctk.CTkLabel(options_frame, text="AI Model:", text_color=theme.colors.text_primary).grid(row=0, column=1, padx=15, pady=(15, 5), sticky="w")
        llm_list = list_available_llms()
        self.llm_options = [llm.name for llm in llm_list] if llm_list else ["No LLMs"]
        self.llm_map = {llm.name: llm.id for llm in llm_list} if llm_list else {}
        self.llm_dropdown = ctk.CTkOptionMenu(options_frame, values=self.llm_options, fg_color=theme.colors.bg_medium, width=180)
        self.llm_dropdown.set(self.llm_options[0])
        self.llm_dropdown.grid(row=1, column=1, padx=15, pady=(0, 10), sticky="w")

        # Row 2: Directing Mode (Story Mode is always Assembly)
        ctk.CTkLabel(options_frame, text="Directing Mode:", text_color=theme.colors.text_primary).grid(row=2, column=0, padx=15, pady=(5, 5), sticky="w")
        dir_opts = list(self.DIRECTING_MODES.values())
        self.directing_mode_dropdown = ctk.CTkOptionMenu(options_frame, values=dir_opts, fg_color=theme.colors.bg_medium, width=180)
        self.directing_mode_dropdown.set(dir_opts[0])
        self.directing_mode_dropdown.grid(row=3, column=0, padx=15, pady=(0, 10), sticky="w")

        # Row 4: Visual Style & Style Notes
        ctk.CTkLabel(options_frame, text="Visual Style:", text_color=theme.colors.text_primary).grid(row=4, column=0, padx=15, pady=(5, 5), sticky="w")
        self.style_dropdown = ctk.CTkOptionMenu(options_frame, values=self.VISUAL_STYLE_OPTIONS, fg_color=theme.colors.bg_medium, width=180)
        existing_style = self._load_existing_visual_style()
        if existing_style:
            reverse_map = {v: k for k, v in self.VISUAL_STYLE_MAP.items()}
            self.style_dropdown.set(reverse_map.get(existing_style, self.VISUAL_STYLE_OPTIONS[0]))
        else:
            self.style_dropdown.set(self.VISUAL_STYLE_OPTIONS[0])
        self.style_dropdown.grid(row=5, column=0, padx=15, pady=(0, 10), sticky="w")

        existing_notes = self._load_existing_style_notes()
        label_text = "Style Notes (edit):" if existing_notes else "Style Notes:"
        ctk.CTkLabel(options_frame, text=label_text, text_color=theme.colors.text_primary).grid(row=4, column=1, padx=15, pady=(5, 5), sticky="w")
        self.style_notes_entry = ctk.CTkTextbox(options_frame, height=50, width=180, wrap="word", fg_color=theme.colors.bg_medium)
        self.style_notes_entry.grid(row=5, column=1, padx=15, pady=(0, 10), sticky="w")
        if existing_notes:
            self.style_notes_entry.insert("1.0", existing_notes)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(15, 20))
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="transparent", border_width=1, border_color=theme.colors.border, command=self.destroy).grid(row=0, column=0)
        ctk.CTkButton(btn_frame, text="Start Writer", width=120, fg_color=theme.colors.accent, hover_color=theme.colors.accent_hover, command=self._on_start).grid(row=0, column=2)

    def _on_start(self) -> None:
        """Collect config and close dialog."""
        # Find preset key from display name
        size_display = self.size_dropdown.get()
        preset_key = "standard"
        for key, val in self.PROJECT_PRESETS.items():
            if val['name'] == size_display:
                preset_key = key
                break

        self.result = {
            "project_path": self.project_path,
            "preset_key": preset_key,
            "preset": self.PROJECT_PRESETS[preset_key],
            "llm_id": self.llm_map.get(self.llm_dropdown.get(), "gemini-pro"),
            "story_mode": "assembly",  # Always use assembly mode (7 agents + 5 judges)
            "directing_mode": self.DIRECTING_MODE_MAP.get(self.directing_mode_dropdown.get(), "scene_chunked"),
            "visual_style": self.VISUAL_STYLE_MAP.get(self.style_dropdown.get(), "live_action"),
            "style_notes": self.style_notes_entry.get("1.0", "end-1c").strip(),
        }

        if self.on_start:
            self.on_start(self.result)

        self.destroy()

    def _load_pitch_content(self) -> str:
        """Load pitch content from project."""
        pitch_paths = [
            self.project_path / "world_bible" / "pitch.md",
            self.project_path / "pitch.md",
            self.project_path / "SEASON_01" / "EPISODE_01" / "world_bible" / "pitch.md",
        ]
        for path in pitch_paths:
            if path.exists():
                try:
                    return path.read_text(encoding="utf-8")[:500]
                except Exception:
                    pass
        return ""

    def _load_existing_visual_style(self) -> str:
        """Load existing visual style from world config."""
        config_paths = [
            self.project_path / "world_bible" / "world_config.json",
            self.project_path / "SEASON_01" / "EPISODE_01" / "world_bible" / "world_config.json",
        ]
        for path in config_paths:
            if path.exists():
                try:
                    import json
                    data = json.loads(path.read_text(encoding="utf-8"))
                    return data.get("visual_style", "")
                except Exception:
                    pass
        return ""

    def _load_existing_style_notes(self) -> str:
        """Load existing style notes from world config."""
        config_paths = [
            self.project_path / "world_bible" / "world_config.json",
            self.project_path / "SEASON_01" / "EPISODE_01" / "world_bible" / "world_config.json",
        ]
        for path in config_paths:
            if path.exists():
                try:
                    import json
                    data = json.loads(path.read_text(encoding="utf-8"))
                    return data.get("style_notes", "")
                except Exception:
                    pass
        return ""

