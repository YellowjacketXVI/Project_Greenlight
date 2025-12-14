"""Scene Editor Dialog for editing individual script scenes."""

import customtkinter as ctk
from pathlib import Path
import re

from greenlight.ui.theme import theme
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.dialogs.scene_editor")


class SceneEditorDialog(ctk.CTkToplevel):
    """Dialog for editing a single scene in the script."""

    def __init__(
        self,
        parent,
        scene_id: str,
        scene_content: str,
        script_file: Path,
        **kwargs
    ):
        super().__init__(parent, **kwargs)

        self.scene_id = scene_id
        self.scene_content = scene_content
        self.script_file = Path(script_file)
        self.result = None

        self.title(f"Edit Scene: {scene_id}")
        self.geometry("800x600")
        self.configure(fg_color=theme.colors.bg_dark)

        # Center on parent
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 800) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=f"🎬 Editing: {self.scene_id}",
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.neon_green
        ).pack(side="left", padx=theme.spacing.md, pady=theme.spacing.sm)

        # Content area
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=theme.spacing.md, pady=theme.spacing.md)

        # Text editor
        self.editor = ctk.CTkTextbox(
            content_frame,
            fg_color=theme.colors.bg_light,
            text_color=theme.colors.text_primary,
            font=(theme.fonts.family, theme.fonts.size_normal),
            wrap="word"
        )
        self.editor.pack(fill="both", expand=True)
        self.editor.insert("1.0", self.scene_content)

        # Button row
        btn_frame = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium, height=50)
        btn_frame.pack(fill="x", side="bottom")
        btn_frame.pack_propagate(False)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            fg_color=theme.colors.bg_light,
            hover_color=theme.colors.bg_hover,
            text_color=theme.colors.text_primary,
            command=self._on_cancel
        ).pack(side="right", padx=theme.spacing.sm, pady=theme.spacing.sm)

        ctk.CTkButton(
            btn_frame,
            text="Save",
            width=100,
            fg_color=theme.colors.neon_green,
            hover_color=theme.colors.neon_green_dim,
            text_color=theme.colors.bg_dark,
            command=self._on_save
        ).pack(side="right", padx=theme.spacing.sm, pady=theme.spacing.sm)

    def _on_cancel(self) -> None:
        """Cancel editing."""
        self.result = None
        self.destroy()

    def _on_save(self) -> None:
        """Save the edited scene back to the script file."""
        new_content = self.editor.get("1.0", "end-1c")

        try:
            # Read the full script
            script_text = self.script_file.read_text(encoding='utf-8')

            # Find and replace this scene's content
            # Pattern: ## Beat: scene.X.XX ... (until next ## Beat or end)
            pattern = rf'(## Beat: {re.escape(self.scene_id)}\s*\n)(.+?)(?=\n## Beat:|\Z)'
            
            def replacer(match):
                return match.group(1) + new_content + "\n"

            new_script = re.sub(pattern, replacer, script_text, flags=re.DOTALL)

            # Write back
            self.script_file.write_text(new_script, encoding='utf-8')
            logger.info(f"Saved scene {self.scene_id} to {self.script_file}")

            self.result = new_content
            self.destroy()

        except Exception as e:
            logger.error(f"Error saving scene: {e}")
            # Show error
            error_label = ctk.CTkLabel(
                self,
                text=f"Error saving: {e}",
                text_color="red"
            )
            error_label.pack(pady=theme.spacing.sm)

