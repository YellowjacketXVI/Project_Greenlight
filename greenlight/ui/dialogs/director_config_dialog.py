"""
Director Configuration Dialog - Collects settings and returns them.

This is a simple config dialog that closes after the user clicks "Start".
The actual pipeline execution happens in the main window with progress
displayed in the pipeline panel.
"""

import customtkinter as ctk
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import json

from greenlight.ui.theme import theme
from greenlight.llm.llm_registry import list_available_llms
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.director_config_dialog")


class DirectorConfigDialog(ctk.CTkToplevel):
    """Dialog for configuring the Director pipeline."""

    def __init__(self, parent, project_path: Path, on_start: Callable[[Dict[str, Any]], None] = None, **kwargs):
        super().__init__(parent, **kwargs)

        self.project_path = project_path
        self.on_start = on_start
        self.result: Optional[Dict[str, Any]] = None
        self.beats_data = []

        self.title("Director Pipeline Configuration")
        self.geometry("450x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 350) // 2
        self.geometry(f"+{x}+{y}")

        self.configure(fg_color=theme.colors.bg_medium)
        self._load_beats()
        self._create_ui()

    def _load_beats(self) -> None:
        """Load beats from project."""
        beats_paths = [
            self.project_path / "beats" / "beat_sheet.json",
            self.project_path / "SEASON_01" / "EPISODE_01" / "beats" / "beat_sheet.json",
        ]
        for path in beats_paths:
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    self.beats_data = data.get("beats", [])
                    return
                except Exception as e:
                    logger.error(f"Failed to load beats: {e}")

    def _create_ui(self) -> None:
        """Create the dialog UI."""
        # Title
        title = ctk.CTkLabel(
            self, text="Director Pipeline",
            font=(theme.fonts.family, theme.fonts.size_header, "bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(pady=(20, 5))

        desc = ctk.CTkLabel(
            self, text="Generate storyboard prompts from beats.",
            text_color=theme.colors.text_secondary
        )
        desc.pack(pady=(0, 15))

        # Beat count info
        beat_color = theme.colors.accent if self.beats_data else theme.colors.warning
        beat_text = f"Found {len(self.beats_data)} beats to process" if self.beats_data else "No beats found. Run Writer first."
        beat_info = ctk.CTkLabel(self, text=beat_text, text_color=beat_color)
        beat_info.pack(pady=(0, 15))

        # Options
        options_frame = ctk.CTkFrame(self, fg_color=theme.colors.bg_dark)
        options_frame.pack(fill="x", padx=30, pady=10)

        # LLM selector
        ctk.CTkLabel(options_frame, text="AI Model:", text_color=theme.colors.text_primary, anchor="w").pack(fill="x", padx=15, pady=(15, 5))
        llm_list = list_available_llms()
        self.llm_options = [llm.name for llm in llm_list] if llm_list else ["No LLMs"]
        self.llm_map = {llm.name: llm.id for llm in llm_list} if llm_list else {}
        self.llm_dropdown = ctk.CTkOptionMenu(options_frame, values=self.llm_options, fg_color=theme.colors.bg_medium)
        self.llm_dropdown.set(self.llm_options[0])
        self.llm_dropdown.pack(fill="x", padx=15, pady=(0, 10))

        # Shots per beat
        ctk.CTkLabel(options_frame, text="Max shots per beat:", text_color=theme.colors.text_primary, anchor="w").pack(fill="x", padx=15, pady=(5, 5))
        self.shots_var = ctk.StringVar(value="3")
        shots_dropdown = ctk.CTkOptionMenu(options_frame, values=["1", "2", "3", "4", "5"], variable=self.shots_var, fg_color=theme.colors.bg_medium)
        shots_dropdown.pack(fill="x", padx=15, pady=(0, 15))

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(15, 20))
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="transparent", border_width=1, border_color=theme.colors.border, command=self.destroy).grid(row=0, column=0)

        start_btn = ctk.CTkButton(
            btn_frame, text="Start Director", width=120,
            fg_color=theme.colors.accent, hover_color=theme.colors.accent_hover,
            command=self._on_start,
            state="normal" if self.beats_data else "disabled"
        )
        start_btn.grid(row=0, column=2)

    def _on_start(self) -> None:
        """Collect config and close dialog."""
        if not self.beats_data:
            return

        selected_llm = self.llm_dropdown.get()
        llm_id = self.llm_map.get(selected_llm, "gemini-pro")
        # Convert hyphenated ID to underscored for config compatibility
        llm_id = llm_id.replace("-", "_")

        self.result = {
            "project_path": self.project_path,
            "llm_id": llm_id,
            "max_shots_per_beat": int(self.shots_var.get()),
            "beats_data": self.beats_data,
            "beats_count": len(self.beats_data),
        }

        if self.on_start:
            self.on_start(self.result)

        self.destroy()

