"""
Greenlight UI Theme

Theme configuration for the CustomTkinter-based UI.
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import customtkinter as ctk


@dataclass
class ColorScheme:
    """Color scheme for the UI."""
    # Primary colors
    primary: str = "#1a73e8"
    primary_hover: str = "#1557b0"
    primary_dark: str = "#0d47a1"

    # Accent colors (Greenlight brand)
    accent: str = "#00c853"  # Greenlight green
    accent_hover: str = "#00a844"
    accent_dark: str = "#008c38"

    # Neon green for navigation highlighting
    neon_green: str = "#39ff14"  # Bright neon green
    neon_green_glow: str = "#00ff00"  # Pure green for glow effects
    neon_green_dim: str = "#2ecc71"  # Dimmer neon for subtle highlights

    # Background colors
    bg_dark: str = "#1e1e1e"
    bg_medium: str = "#252526"
    bg_light: str = "#2d2d30"
    bg_hover: str = "#3e3e42"

    # Text colors
    text_primary: str = "#ffffff"
    text_secondary: str = "#cccccc"
    text_muted: str = "#808080"

    # Status colors
    success: str = "#4caf50"
    warning: str = "#ff9800"
    error: str = "#f44336"
    info: str = "#2196f3"
    
    # Status colors
    pending: str = "#ff9800"
    processing: str = "#2196f3"
    complete: str = "#4caf50"
    failed: str = "#f44336"
    
    # Border colors
    border: str = "#3e3e42"
    border_focus: str = "#1a73e8"


@dataclass
class FontConfig:
    """Font configuration."""
    family: str = "Segoe UI"
    size_small: int = 11
    size_normal: int = 13
    size_large: int = 15
    size_title: int = 18
    size_header: int = 24


@dataclass
class SpacingConfig:
    """Spacing configuration."""
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


class GreenlightTheme:
    """
    Theme manager for the Greenlight UI.

    Features:
    - Dark mode by default
    - Consistent color scheme
    - Configurable fonts and spacing
    """

    def __init__(self):
        """Initialize the theme."""
        self.colors = ColorScheme()
        self.fonts = FontConfig()
        self.spacing = SpacingConfig()
        self._font_scale = 1.0  # Font scale factor

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply the theme to CustomTkinter."""
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

    def set_font_size(self, base_size: int) -> None:
        """
        Set the base font size and scale all font sizes accordingly.

        Args:
            base_size: The new base font size (size_normal)
        """
        # Calculate scale factor from default (13)
        self._font_scale = base_size / 13.0

        # Update all font sizes
        self.fonts.size_small = max(8, int(11 * self._font_scale))
        self.fonts.size_normal = base_size
        self.fonts.size_large = max(12, int(15 * self._font_scale))
        self.fonts.size_title = max(14, int(18 * self._font_scale))
        self.fonts.size_header = max(18, int(24 * self._font_scale))

    def get_font_size(self) -> int:
        """Get the current base font size."""
        return self.fonts.size_normal
    
    def get_button_style(self, variant: str = "primary") -> Dict:
        """Get button style configuration."""
        styles = {
            "primary": {
                "fg_color": self.colors.primary,
                "hover_color": self.colors.primary_hover,
                "text_color": self.colors.text_primary,
            },
            "secondary": {
                "fg_color": self.colors.bg_light,
                "hover_color": self.colors.bg_hover,
                "text_color": self.colors.text_primary,
            },
            "success": {
                "fg_color": self.colors.success,
                "hover_color": "#388e3c",
                "text_color": self.colors.text_primary,
            },
            "danger": {
                "fg_color": self.colors.error,
                "hover_color": "#d32f2f",
                "text_color": self.colors.text_primary,
            },
            "nav_active": {
                "fg_color": self.colors.neon_green,
                "hover_color": self.colors.neon_green_glow,
                "text_color": self.colors.bg_dark,
                "border_color": self.colors.neon_green,
            },
            "nav_highlight": {
                "fg_color": "transparent",
                "hover_color": self.colors.neon_green_dim,
                "text_color": self.colors.neon_green,
                "border_color": self.colors.neon_green,
            },
        }
        return styles.get(variant, styles["primary"])
    
    def get_entry_style(self) -> Dict:
        """Get entry/input style configuration."""
        return {
            "fg_color": self.colors.bg_dark,
            "border_color": self.colors.border,
            "text_color": self.colors.text_primary,
        }
    
    def get_frame_style(self, variant: str = "default") -> Dict:
        """Get frame style configuration."""
        styles = {
            "default": {
                "fg_color": self.colors.bg_medium,
                "corner_radius": 8,
            },
            "card": {
                "fg_color": self.colors.bg_light,
                "corner_radius": 12,
            },
            "panel": {
                "fg_color": self.colors.bg_dark,
                "corner_radius": 0,
            },
        }
        return styles.get(variant, styles["default"])
    
    def get_label_style(self, variant: str = "default") -> Dict:
        """Get label style configuration."""
        styles = {
            "default": {
                "text_color": self.colors.text_primary,
                "font": (self.fonts.family, self.fonts.size_normal),
            },
            "title": {
                "text_color": self.colors.text_primary,
                "font": (self.fonts.family, self.fonts.size_title, "bold"),
            },
            "muted": {
                "text_color": self.colors.text_muted,
                "font": (self.fonts.family, self.fonts.size_small),
            },
        }
        return styles.get(variant, styles["default"])
    
    def get_status_color(self, status: str) -> str:
        """Get color for a status."""
        status_colors = {
            "pending": self.colors.pending,
            "processing": self.colors.processing,
            "complete": self.colors.complete,
            "failed": self.colors.failed,
        }
        return status_colors.get(status, self.colors.text_muted)


# Global theme instance
theme = GreenlightTheme()

