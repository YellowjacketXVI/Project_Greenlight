"""
Storyboard Generation Modal - Configure and start storyboard image generation.

Opens when clicking the Generate button in the toolbar.
Shows:
- Model selection dropdown
- Brief of what will be generated (frame count, scenes)
- Continue button to start generation
"""

import customtkinter as ctk
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
import json

from greenlight.ui.theme import theme
from greenlight.config.api_dictionary import get_image_models, ModelEntry


class StoryboardGenerationModal(ctk.CTkToplevel):
    """Modal dialog for configuring storyboard generation."""

    def __init__(
        self,
        parent,
        project_path: Path,
        visual_script_data: Dict[str, Any],
        on_continue: Callable[[str, Dict], None] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)

        self.project_path = project_path
        self.visual_script_data = visual_script_data
        self.on_continue = on_continue
        self.result = None

        self.title("Generate Storyboard")
        self.geometry("650x550")
        self.configure(fg_color=theme.colors.bg_dark)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 650) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 550) // 2
        self.geometry(f"+{x}+{y}")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the modal UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        title = ctk.CTkLabel(
            header,
            text="🎨 Generate Storyboard Images",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(side="left", padx=20, pady=15)

        # Close button
        close_btn = ctk.CTkButton(
            header,
            text="✕",
            width=30,
            height=30,
            fg_color="transparent",
            hover_color=theme.colors.error,
            command=self._on_cancel
        )
        close_btn.pack(side="right", padx=10)

        # Main content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=15)

        # === GENERATION BRIEF ===
        brief_label = ctk.CTkLabel(
            content,
            text="📋 Generation Brief",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.colors.text_primary,
            anchor="w"
        )
        brief_label.pack(fill="x", pady=(0, 10))

        # Brief card
        brief_card = ctk.CTkFrame(content, fg_color=theme.colors.bg_medium, corner_radius=8)
        brief_card.pack(fill="x", pady=(0, 20))

        # Get data from visual script
        total_frames = self.visual_script_data.get('total_frames', 0)
        total_scenes = self.visual_script_data.get('total_scenes', 0)

        # Extract tags from all frame prompts (all 6 canonical prefixes)
        # Tags MUST be in brackets per notation standard: [PREFIX_NAME]
        all_tags = set()
        for scene in self.visual_script_data.get('scenes', []):
            for frame in scene.get('frames', []):
                prompt = frame.get('prompt', '')
                import re
                # Extract all 6 canonical tag prefixes with mandatory brackets
                tags = re.findall(r'\[(CHAR_[A-Z0-9_]+|LOC_[A-Z0-9_]+|PROP_[A-Z0-9_]+|CONCEPT_[A-Z0-9_]+|EVENT_[A-Z0-9_]+|ENV_[A-Z0-9_]+)\]', prompt)
                all_tags.update(tags)

        char_tags = [t for t in all_tags if t.startswith('CHAR_')]
        loc_tags = [t for t in all_tags if t.startswith('LOC_')]
        prop_tags = [t for t in all_tags if t.startswith('PROP_')]
        concept_tags = [t for t in all_tags if t.startswith('CONCEPT_')]
        event_tags = [t for t in all_tags if t.startswith('EVENT_')]
        env_tags = [t for t in all_tags if t.startswith('ENV_')]

        # Brief content
        brief_content = ctk.CTkFrame(brief_card, fg_color="transparent")
        brief_content.pack(fill="x", padx=15, pady=15)

        # Frame count - large
        frame_row = ctk.CTkFrame(brief_content, fg_color="transparent")
        frame_row.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            frame_row,
            text=str(total_frames),
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color=theme.colors.accent
        ).pack(side="left")

        ctk.CTkLabel(
            frame_row,
            text=f"  frames to generate across {total_scenes} scene(s)",
            font=ctk.CTkFont(size=14),
            text_color=theme.colors.text_secondary
        ).pack(side="left", pady=(10, 0))

        # Tag summary
        tag_summary = ctk.CTkFrame(brief_content, fg_color="transparent")
        tag_summary.pack(fill="x", pady=(5, 0))

        if char_tags:
            ctk.CTkLabel(
                tag_summary,
                text=f"👤 {len(char_tags)} characters",
                font=ctk.CTkFont(size=11),
                text_color=theme.colors.text_muted,
                fg_color=theme.colors.bg_dark,
                corner_radius=4
            ).pack(side="left", padx=(0, 8), pady=2, ipadx=6, ipady=2)

        if loc_tags:
            ctk.CTkLabel(
                tag_summary,
                text=f"📍 {len(loc_tags)} locations",
                font=ctk.CTkFont(size=11),
                text_color=theme.colors.text_muted,
                fg_color=theme.colors.bg_dark,
                corner_radius=4
            ).pack(side="left", padx=(0, 8), pady=2, ipadx=6, ipady=2)

        if prop_tags:
            ctk.CTkLabel(
                tag_summary,
                text=f"🎭 {len(prop_tags)} props",
                font=ctk.CTkFont(size=11),
                text_color=theme.colors.text_muted,
                fg_color=theme.colors.bg_dark,
                corner_radius=4
            ).pack(side="left", padx=(0, 8), pady=2, ipadx=6, ipady=2)

        # === MODEL SELECTION ===
        model_section = ctk.CTkFrame(content, fg_color="transparent")
        model_section.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(
            model_section,
            text="🤖 Image Generation Model",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.colors.text_primary,
            anchor="w"
        ).pack(fill="x", pady=(0, 8))

        # Build model options from API dictionary
        self.model_map = self._build_model_options()
        model_names = list(self.model_map.keys()) if self.model_map else ["No models available"]

        # Model dropdown
        self.model_dropdown = ctk.CTkOptionMenu(
            model_section,
            values=model_names,
            fg_color=theme.colors.bg_medium,
            button_color=theme.colors.bg_hover,
            dropdown_fg_color=theme.colors.bg_medium,
            width=400,
            height=36,
            font=ctk.CTkFont(size=12)
        )
        self.model_dropdown.set(model_names[0])
        self.model_dropdown.pack(anchor="w", pady=(0, 5))

        # Model description
        self.model_desc_label = ctk.CTkLabel(
            model_section,
            text=self._get_model_description(model_names[0]),
            font=ctk.CTkFont(size=10),
            text_color=theme.colors.text_muted,
            wraplength=550,
            justify="left",
            anchor="w"
        )
        self.model_desc_label.pack(fill="x", pady=(0, 15))

        # Update description on model change
        self.model_dropdown.configure(command=self._on_model_change)

        # === ESTIMATED TIME ===
        estimate_frame = ctk.CTkFrame(content, fg_color=theme.colors.bg_light, corner_radius=6)
        estimate_frame.pack(fill="x", pady=(10, 0))

        # Rough estimate: ~15-30 seconds per image
        est_min = (total_frames * 15) // 60
        est_max = (total_frames * 30) // 60

        ctk.CTkLabel(
            estimate_frame,
            text=f"⏱️ Estimated time: {est_min}-{est_max} minutes",
            font=ctk.CTkFont(size=11),
            text_color=theme.colors.text_secondary
        ).pack(padx=15, pady=10)

        # Footer with buttons
        footer = ctk.CTkFrame(self, fg_color="transparent", height=70)
        footer.pack(fill="x", side="bottom", padx=20, pady=15)

        cancel_btn = ctk.CTkButton(
            footer,
            text="Cancel",
            width=100,
            height=36,
            fg_color=theme.colors.bg_medium,
            hover_color=theme.colors.bg_hover,
            command=self._on_cancel
        )
        cancel_btn.pack(side="left")

        continue_btn = ctk.CTkButton(
            footer,
            text="▶️ Continue",
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=theme.colors.success,
            hover_color="#2d8a4e",
            command=self._on_continue
        )
        continue_btn.pack(side="right")

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

    def _get_model_description(self, display_name: str) -> str:
        """Get description for a model by display name."""
        model_key = self.model_map.get(display_name)
        if model_key:
            image_models = get_image_models()
            model = image_models.get(model_key)
            if model:
                return model.description
        return ""

    def _on_model_change(self, display_name: str) -> None:
        """Handle model selection change."""
        desc = self._get_model_description(display_name)
        self.model_desc_label.configure(text=desc)

    def _on_cancel(self) -> None:
        """Handle cancel button."""
        self.result = None
        self.destroy()

    def _on_continue(self) -> None:
        """Handle continue button - start generation."""
        model_display = self.model_dropdown.get()
        model_key = self.model_map.get(model_display, "seedream_4_5")

        self.result = {
            "model_key": model_key,
            "visual_script_data": self.visual_script_data
        }

        if self.on_continue:
            self.on_continue(model_key, self.visual_script_data)

        self.destroy()

    def get_result(self) -> Optional[Dict[str, Any]]:
        """Get the result after dialog closes."""
        return self.result
