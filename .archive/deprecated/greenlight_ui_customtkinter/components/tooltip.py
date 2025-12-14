"""
Tooltip System for Greenlight UI

Provides hover tooltips and contextual help for UI elements.
"""

import customtkinter as ctk
from typing import Optional, Dict, Callable
from greenlight.ui.theme import theme
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.tooltip")


class Tooltip:
    """
    Hover tooltip for CTk widgets.
    
    Usage:
        btn = ctk.CTkButton(parent, text="Click me")
        Tooltip(btn, "This button does something amazing!")
    """
    
    def __init__(
        self,
        widget: ctk.CTkBaseClass,
        text: str,
        delay_ms: int = 500,
        wrap_length: int = 250
    ):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.wrap_length = wrap_length
        
        self._tooltip_window: Optional[ctk.CTkToplevel] = None
        self._after_id: Optional[str] = None
        
        # Bind events
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.bind("<Button-1>", self._on_leave)
    
    def _on_enter(self, event=None) -> None:
        """Schedule tooltip display."""
        self._cancel_scheduled()
        self._after_id = self.widget.after(self.delay_ms, self._show_tooltip)
    
    def _on_leave(self, event=None) -> None:
        """Hide tooltip and cancel scheduled display."""
        self._cancel_scheduled()
        self._hide_tooltip()
    
    def _cancel_scheduled(self) -> None:
        """Cancel any scheduled tooltip display."""
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
    
    def _show_tooltip(self) -> None:
        """Display the tooltip."""
        if self._tooltip_window:
            return
        
        # Get widget position
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        # Create tooltip window
        self._tooltip_window = ctk.CTkToplevel(self.widget)
        self._tooltip_window.wm_overrideredirect(True)
        self._tooltip_window.wm_geometry(f"+{x}+{y}")
        self._tooltip_window.configure(fg_color=theme.colors.bg_medium)
        
        # Tooltip content
        frame = ctk.CTkFrame(
            self._tooltip_window,
            fg_color=theme.colors.bg_medium,
            corner_radius=6,
            border_width=1,
            border_color=theme.colors.accent
        )
        frame.pack(fill="both", expand=True)
        
        label = ctk.CTkLabel(
            frame,
            text=self.text,
            wraplength=self.wrap_length,
            justify="left",
            font=(theme.fonts.family, 11),
            text_color=theme.colors.text_primary,
            padx=8,
            pady=6
        )
        label.pack()
        
        # Ensure tooltip is on top
        self._tooltip_window.lift()
        self._tooltip_window.attributes("-topmost", True)
    
    def _hide_tooltip(self) -> None:
        """Hide the tooltip."""
        if self._tooltip_window:
            self._tooltip_window.destroy()
            self._tooltip_window = None
    
    def update_text(self, new_text: str) -> None:
        """Update tooltip text."""
        self.text = new_text


# Tooltip registry for tab-specific help
TAB_TOOLTIPS: Dict[str, str] = {
    "characters": (
        "📚 Characters Tab\n\n"
        "Define your story's characters here.\n\n"
        "• Click 'Add Character' to create new characters\n"
        "• Each character gets a unique tag like [CHAR_NAME]\n"
        "• Add reference images for visual consistency\n"
        "• Use 'Generate All References' to batch create sheets"
    ),
    "locations": (
        "🗺️ Locations Tab\n\n"
        "Define your story's locations and settings.\n\n"
        "• Add locations with [LOC_NAME] tags\n"
        "• Include directional variants (N/E/S/W)\n"
        "• Reference images help maintain visual consistency"
    ),
    "props": (
        "🎭 Props Tab\n\n"
        "Define important objects in your story.\n\n"
        "• Props use [PROP_NAME] tags\n"
        "• Include items that appear in multiple scenes\n"
        "• Reference images ensure consistent rendering"
    ),
    "world": (
        "🌍 World Tab\n\n"
        "Overview of your story world.\n\n"
        "• Logline - one sentence summary\n"
        "• Synopsis - full story overview\n"
        "• Setting - time and place details"
    ),
    "lore": (
        "📜 Lore Tab\n\n"
        "Themes, rules, and world-building details.\n\n"
        "• Themes - core story themes\n"
        "• World Rules - how your world works\n"
        "• Backstory - historical context"
    ),
    "style": (
        "🎨 Style Core Tab\n\n"
        "Visual style settings for your project.\n\n"
        "• Visual Style - animation/live action type\n"
        "• Style Notes - specific visual guidelines\n"
        "• These settings affect image generation"
    ),
    "storyboard": (
        "🎬 Storyboard View\n\n"
        "View and manage your visual storyboard.\n\n"
        "• Use zoom slider to adjust card size\n"
        "• Click cards to flip and see details\n"
        "• Select multiple cards for batch regeneration\n"
        "• Navigate scenes with the timeline bar"
    ),
    "editor": (
        "✏️ Editor View\n\n"
        "Edit scripts, beats, and story content.\n\n"
        "• Syntax highlighting for scene notation\n"
        "• Use @tags for autocomplete\n"
        "• Save with Ctrl+S"
    ),
}


def add_tooltip(widget: ctk.CTkBaseClass, text: str, delay_ms: int = 500) -> Tooltip:
    """Convenience function to add a tooltip to a widget."""
    return Tooltip(widget, text, delay_ms)

