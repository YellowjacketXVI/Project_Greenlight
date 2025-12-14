"""
Regeneration Modal - Edit/Recreate/Re-Angle frames with AI.

Allows users to:
- Select a template (Edit, Recreate, Re-Angle)
- Enter custom modification prompt
- Select image generation model
- Generate new version of selected frames
"""

import customtkinter as ctk
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

from greenlight.ui.theme import theme
from greenlight.config.api_dictionary import get_image_models, ModelEntry


# Template definitions with prefixes
REGENERATION_TEMPLATES = {
    "Edit": "Edit this image maintaining subject identity and qualities of the original image. Change:",
    "Recreate": "Recreate this image re-envisioning it with these modifications:",
    "Re-Angle": "Analyze this reference image and provide a new angle maintaining subject identity and qualities. The angle of the frame is to show:",
}


class RegenerationModal(ctk.CTkToplevel):
    """Modal dialog for regenerating selected frames."""

    def __init__(
        self,
        parent,
        selected_frames: List[Any],
        project_path: Optional[Path] = None,
        on_generate: Callable[[List[Any], str, str], None] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)

        self.selected_frames = selected_frames
        self.project_path = project_path
        self.on_generate = on_generate
        self.result = None

        self.title("Regenerate Frames")
        self.geometry("600x500")
        self.configure(fg_color=theme.colors.bg_dark)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 600) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 500) // 2
        self.geometry(f"+{x}+{y}")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the modal UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium, height=60)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        title = ctk.CTkLabel(
            header,
            text=f"🔄 Regenerate {len(self.selected_frames)} Frame(s)",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(side="left", padx=20, pady=15)

        # Main content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=15)

        # Template selection
        template_label = ctk.CTkLabel(
            content,
            text="Template:",
            font=ctk.CTkFont(size=12),
            text_color=theme.colors.text_primary,
            anchor="w"
        )
        template_label.pack(fill="x", pady=(0, 5))

        self.template_var = ctk.StringVar(value="Edit")
        self.template_dropdown = ctk.CTkOptionMenu(
            content,
            values=list(REGENERATION_TEMPLATES.keys()),
            variable=self.template_var,
            command=self._on_template_change,
            fg_color=theme.colors.bg_medium,
            button_color=theme.colors.bg_hover,
            width=200
        )
        self.template_dropdown.pack(anchor="w", pady=(0, 15))

        # Template preview (shows prefix)
        self.prefix_label = ctk.CTkLabel(
            content,
            text=REGENERATION_TEMPLATES["Edit"],
            font=ctk.CTkFont(size=10),
            text_color=theme.colors.text_muted,
            wraplength=550,
            justify="left",
            anchor="w"
        )
        self.prefix_label.pack(fill="x", pady=(0, 10))

        # Prompt input
        prompt_label = ctk.CTkLabel(
            content,
            text="Your modifications:",
            font=ctk.CTkFont(size=12),
            text_color=theme.colors.text_primary,
            anchor="w"
        )
        prompt_label.pack(fill="x", pady=(0, 5))

        self.prompt_text = ctk.CTkTextbox(
            content,
            height=150,
            font=ctk.CTkFont(size=12),
            fg_color=theme.colors.bg_medium,
            text_color=theme.colors.text_primary,
            wrap="word"
        )
        self.prompt_text.pack(fill="x", pady=(0, 15))
        self.prompt_text.insert("1.0", "")

        # Model selection
        model_label = ctk.CTkLabel(
            content,
            text="Image Generation Model:",
            font=ctk.CTkFont(size=12),
            text_color=theme.colors.text_primary,
            anchor="w"
        )
        model_label.pack(fill="x", pady=(0, 5))

        # Build model options from API dictionary
        self.model_map = self._build_model_options()
        model_names = list(self.model_map.keys()) if self.model_map else ["No models available"]

        self.model_dropdown = ctk.CTkOptionMenu(
            content,
            values=model_names,
            fg_color=theme.colors.bg_medium,
            button_color=theme.colors.bg_hover,
            width=300
        )
        self.model_dropdown.set(model_names[0])
        self.model_dropdown.pack(anchor="w", pady=(0, 20))

        # Footer with buttons
        footer = ctk.CTkFrame(self, fg_color="transparent", height=60)
        footer.pack(fill="x", side="bottom", padx=20, pady=15)

        cancel_btn = ctk.CTkButton(
            footer,
            text="Cancel",
            width=100,
            fg_color=theme.colors.bg_medium,
            hover_color=theme.colors.bg_hover,
            command=self._on_cancel
        )
        cancel_btn.pack(side="left")

        generate_btn = ctk.CTkButton(
            footer,
            text="🎨 Generate",
            width=150,
            fg_color=theme.colors.accent,
            hover_color=theme.colors.accent_hover,
            command=self._on_generate
        )
        generate_btn.pack(side="right")

    def _build_model_options(self) -> Dict[str, str]:
        """Build model options from API dictionary."""
        model_map = {}
        image_models = get_image_models()

        # Prioritized display order
        priority_keys = ["seedream_4_5", "nano_banana_pro", "nano_banana", "flux_kontext_pro", "flux_kontext_max"]

        for key in priority_keys:
            if key in image_models:
                model = image_models[key]
                display = f"{model.display_name} ({model.provider.value})"
                model_map[display] = key

        # Add remaining models
        for key, model in image_models.items():
            if key not in priority_keys:
                display = f"{model.display_name} ({model.provider.value})"
                model_map[display] = key

        return model_map

    def _on_template_change(self, template_name: str) -> None:
        """Handle template selection change."""
        prefix = REGENERATION_TEMPLATES.get(template_name, "")
        self.prefix_label.configure(text=prefix)

    def _on_cancel(self) -> None:
        """Handle cancel button."""
        self.result = None
        self.destroy()

    def _on_generate(self) -> None:
        """Handle generate button."""
        template = self.template_var.get()
        prefix = REGENERATION_TEMPLATES.get(template, "")
        user_prompt = self.prompt_text.get("1.0", "end-1c").strip()

        # Combine prefix and user prompt
        full_prompt = f"{prefix} {user_prompt}" if user_prompt else prefix

        # Get selected model
        model_display = self.model_dropdown.get()
        model_key = self.model_map.get(model_display, "seedream_4_5")

        self.result = {
            "template": template,
            "prompt": full_prompt,
            "user_prompt": user_prompt,
            "model_key": model_key,
            "frames": self.selected_frames
        }

        if self.on_generate:
            self.on_generate(self.selected_frames, full_prompt, model_key)

        self.destroy()

    def get_result(self) -> Optional[Dict[str, Any]]:
        """Get the result after dialog closes."""
        return self.result

