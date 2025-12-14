"""
World Bible Preserve Dialog

Shows existing world bible elements with checkboxes for user to select which to preserve
when regenerating the world bible.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
import customtkinter as ctk

from greenlight.ui.theme import theme


class WorldBiblePreserveDialog(ctk.CTkToplevel):
    """Dialog to select which world bible elements to preserve during regeneration."""

    def __init__(self, parent, project_path: Path):
        super().__init__(parent)
        self.project_path = project_path
        self.result: Optional[Set[str]] = None  # None = cancelled, Set = selected tags to preserve
        
        self.title("Preserve World Bible Elements")
        self.geometry("550x700")  # Increased height to prevent button cutoff
        self.configure(fg_color=theme.colors.bg_dark)
        self.resizable(False, False)

        # Center on parent
        self.transient(parent)
        self.grab_set()
        x = parent.winfo_x() + (parent.winfo_width() - 550) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 700) // 2
        self.geometry(f"+{x}+{y}")
        
        # Load existing world config
        self.world_config = self._load_world_config()
        self.checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        
        self._build_ui(theme)
        
        self.wait_window()

    def _load_world_config(self) -> Dict[str, Any]:
        """Load existing world_config.json."""
        config_path = self.project_path / "world_bible" / "world_config.json"
        if config_path.exists():
            try:
                return json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _build_ui(self, theme) -> None:
        """Build the dialog UI."""
        # Header
        header = ctk.CTkLabel(
            self, text="🔒 Detected Existing World Bible",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.colors.accent
        )
        header.pack(pady=(20, 5))
        
        subtitle = ctk.CTkLabel(
            self, text="Select elements to preserve. Unselected items will be archived and regenerated.",
            font=ctk.CTkFont(size=12),
            text_color=theme.colors.text_secondary,
            wraplength=500
        )
        subtitle.pack(pady=(0, 15))
        
        # Scrollable frame for checkboxes
        scroll_frame = ctk.CTkScrollableFrame(
            self, width=500, height=400,
            fg_color=theme.colors.bg_medium,
            corner_radius=8
        )
        scroll_frame.pack(padx=20, pady=10, fill="both", expand=True)
        
        # Build sections for characters, locations, props
        self._build_section(scroll_frame, theme, "👤 Characters", self.world_config.get("characters", []))
        self._build_section(scroll_frame, theme, "📍 Locations", self.world_config.get("locations", []))
        self._build_section(scroll_frame, theme, "🎭 Props", self.world_config.get("props", []))
        
        # Select All / Deselect All buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(5, 10))
        
        select_all_btn = ctk.CTkButton(
            btn_row, text="Select All", width=100,
            fg_color=theme.colors.bg_medium,
            command=self._select_all
        )
        select_all_btn.pack(side="left", padx=5)
        
        deselect_all_btn = ctk.CTkButton(
            btn_row, text="Deselect All", width=100,
            fg_color=theme.colors.bg_medium,
            command=self._deselect_all
        )
        deselect_all_btn.pack(side="left", padx=5)
        
        # Action buttons - with extra padding to ensure visibility
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(fill="x", padx=20, pady=(10, 30))
        action_frame.grid_columnconfigure(1, weight=1)
        
        cancel_btn = ctk.CTkButton(
            action_frame, text="Cancel", width=100,
            fg_color="transparent", border_width=1,
            border_color=theme.colors.border,
            command=self._on_cancel
        )
        cancel_btn.grid(row=0, column=0, padx=5)
        
        regenerate_all_btn = ctk.CTkButton(
            action_frame, text="Regenerate All", width=120,
            fg_color=theme.colors.warning if hasattr(theme.colors, 'warning') else "#E67E22",
            command=self._on_regenerate_all
        )
        regenerate_all_btn.grid(row=0, column=1, padx=5, sticky="e")
        
        preserve_btn = ctk.CTkButton(
            action_frame, text="Preserve Selected", width=140,
            fg_color=theme.colors.accent,
            hover_color=theme.colors.accent_hover,
            command=self._on_preserve
        )
        preserve_btn.grid(row=0, column=2, padx=5)

    def _build_section(self, parent, theme, title: str, items: List[Dict]) -> None:
        """Build a section with checkboxes for each item."""
        if not items:
            return
        
        # Section header
        header = ctk.CTkLabel(
            parent, text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.colors.text_primary,
            anchor="w"
        )
        header.pack(fill="x", padx=10, pady=(15, 5))
        
        # Checkboxes for each item
        for item in items:
            tag = item.get("tag", "")
            name = item.get("name", "Unknown")
            
            checkbox = ctk.CTkCheckBox(
                parent, text=f"{tag} - {name}",
                font=ctk.CTkFont(size=12),
                text_color=theme.colors.text_secondary,
                fg_color=theme.colors.accent,
                hover_color=theme.colors.accent_hover
            )
            checkbox.pack(fill="x", padx=20, pady=2, anchor="w")
            checkbox.select()  # Default to selected (preserve)
            self.checkboxes[tag] = checkbox

    def _select_all(self) -> None:
        """Select all checkboxes."""
        for checkbox in self.checkboxes.values():
            checkbox.select()

    def _deselect_all(self) -> None:
        """Deselect all checkboxes."""
        for checkbox in self.checkboxes.values():
            checkbox.deselect()

    def _on_cancel(self) -> None:
        """Cancel and close dialog."""
        self.result = None
        self.grab_release()
        self.destroy()

    def _on_regenerate_all(self) -> None:
        """Regenerate all - preserve nothing."""
        self.result = set()  # Empty set = preserve nothing
        self.grab_release()
        self.destroy()

    def _on_preserve(self) -> None:
        """Preserve selected elements."""
        selected_tags = set()
        for tag, checkbox in self.checkboxes.items():
            if checkbox.get():  # Checkbox is checked
                selected_tags.add(tag)
        self.result = selected_tags
        self.grab_release()
        self.destroy()

    def get_preserved_tags(self) -> Optional[Set[str]]:
        """Get the set of tags to preserve, or None if cancelled."""
        return self.result

