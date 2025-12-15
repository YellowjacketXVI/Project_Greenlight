"""
Reference Modal - Modal for managing reference images for tags.

Features:
- Display all reference images for a tag
- Star/select key reference image
- Generate new references using AI models
- Generate character/prop sheets
- Generate location cardinal views

DEPRECATION NOTICE:
    The generation methods in this file are DEPRECATED and should not be used.
    Use UnifiedReferenceScript instead for all reference generation.

    Deprecated methods:
    - _generate_reference() - Use UnifiedReferenceScript.generate_character_sheet()
    - _generate_character_sheet() - Use UnifiedReferenceScript.generate_character_sheet()
    - _generate_sheet() - Use UnifiedReferenceScript.generate_character_sheet()
    - _generate_sheet_from_selected() - Use UnifiedReferenceScript.convert_reference_to_sheet()
    - _generate_sheet_from_image() - Use UnifiedReferenceScript.convert_image_to_sheet()
    - _generate_cardinal_views() - Use UnifiedReferenceScript.generate_location_views()
    - _build_reference_prompt() - Use ReferencePromptAgent

    See .augment-guidelines for the UnifiedReferenceScript API specification.
    See .archive/deprecated/reference_modal_legacy/README.md for migration guide.
"""

from __future__ import annotations

import asyncio
import threading
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import customtkinter as ctk

from greenlight.ui.theme import theme
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.reference_modal")

if TYPE_CHECKING:
    from greenlight.core.image_handler import ImageHandler, ImageModel
    from greenlight.context.context_engine import ContextEngine


def _deprecated_method(method_name: str, replacement: str):
    """Emit deprecation warning for legacy methods."""
    msg = (
        f"{method_name} is deprecated and will be removed in a future version. "
        f"Use {replacement} instead. "
        f"See .archive/deprecated/reference_modal_legacy/README.md for migration guide."
    )
    warnings.warn(msg, DeprecationWarning, stacklevel=3)
    logger.warning(msg)


class ReferenceModal(ctk.CTkToplevel):
    """Modal window for managing reference images."""

    def __init__(
        self,
        parent,
        tag: str,
        name: str,
        tag_type: str,  # "character", "location", "prop"
        project_path: Path,
        world_config: Dict[str, Any] = None,
        on_change: Optional[Callable] = None,
        context_engine: Optional["ContextEngine"] = None
    ):
        super().__init__(parent)

        self.tag = tag
        self.name = name
        self.tag_type = tag_type
        self.project_path = Path(project_path)
        self.world_config = world_config or {}
        self.on_change = on_change
        self._context_engine = context_engine

        self._image_handler = None
        self._key_reference: Optional[Path] = None
        self._references: List[Path] = []
        self._image_cache: Dict[str, Any] = {}
        self._selected_image: Optional[Path] = None  # Currently selected image
        self._card_widgets: Dict[Path, ctk.CTkFrame] = {}  # Track cards for selection

        self._setup_window()
        self._create_ui()
        self._load_references()
    
    def _setup_window(self):
        """Configure the modal window."""
        self.title(f"References: [{self.tag}] {self.name}")
        self.geometry("800x600")
        self.configure(fg_color=theme.colors.bg_dark)

        # Center on parent
        self.transient(self.master)
        self.grab_set()

        # Track if modal is still open
        self._is_open = True

        # Make modal
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _safe_status_update(self, text: str):
        """Safely update status label, checking if widget still exists."""
        if self._is_open and hasattr(self, 'status_label'):
            try:
                self.status_label.configure(text=text)
            except Exception:
                pass  # Widget was destroyed
    
    def _get_image_handler(self):
        """Get or create ImageHandler instance with ContextEngine."""
        if self._image_handler is None:
            from greenlight.core.image_handler import get_image_handler
            self._image_handler = get_image_handler(self.project_path, self._context_engine)
        return self._image_handler
    
    def _create_ui(self):
        """Create the modal UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        # Tag badge
        tag_colors = {
            'character': theme.colors.primary,
            'location': '#3498DB',
            'prop': '#F39C12'
        }
        tag_color = tag_colors.get(self.tag_type, theme.colors.text_secondary)
        
        ctk.CTkLabel(
            header,
            text=f"[{self.tag}]",
            font=(theme.fonts.family, 14, "bold"),
            text_color=tag_color
        ).pack(side="left", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        ctk.CTkLabel(
            header,
            text=self.name,
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.text_primary
        ).pack(side="left", padx=theme.spacing.sm)
        
        # Close button
        ctk.CTkButton(
            header,
            text="✕",
            width=30,
            height=30,
            fg_color="transparent",
            hover_color=theme.colors.error,
            command=self._on_close
        ).pack(side="right", padx=theme.spacing.sm)
        
        # Main content area
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=theme.spacing.md, pady=theme.spacing.md)

        # Right side - Actions panel (pack first so it stays on right)
        right_panel = ctk.CTkFrame(content, fg_color=theme.colors.bg_light, width=220, corner_radius=8)
        right_panel.pack(side="right", fill="y", padx=(theme.spacing.md, 0))
        right_panel.pack_propagate(False)
        self._create_actions_panel(right_panel)

        # Left side - Two horizontal panels stacked vertically
        left_panel = ctk.CTkFrame(content, fg_color="transparent")
        left_panel.pack(side="left", fill="both", expand=True)

        # === TOP HALF: Reference images (horizontal scroll) ===
        refs_section = ctk.CTkFrame(left_panel, fg_color="transparent")
        refs_section.pack(fill="both", expand=True)

        ctk.CTkLabel(
            refs_section,
            text="📁 Reference Images",
            font=(theme.fonts.family, 13, "bold"),
            text_color=theme.colors.text_primary
        ).pack(anchor="w", pady=(0, theme.spacing.sm))

        # Horizontal scrollable container for references
        self.refs_scroll = ctk.CTkScrollableFrame(
            refs_section,
            fg_color=theme.colors.bg_light,
            corner_radius=8,
            orientation="horizontal"
        )
        self.refs_scroll.pack(fill="both", expand=True)

        self.refs_grid = ctk.CTkFrame(self.refs_scroll, fg_color="transparent")
        self.refs_grid.pack(fill="both", expand=True)

        # === BOTTOM HALF: Cardinal views preview (for locations only) ===
        if self.tag_type == "location":
            self._create_cardinal_preview_panel(left_panel)

    def _create_actions_panel(self, parent):
        """Create the actions panel with generation options."""
        # =====================================================================
        # SELECTION-DEPENDENT ACTIONS (greyed out until media selected)
        # =====================================================================
        ctk.CTkLabel(
            parent,
            text="📌 Selected Image",
            font=(theme.fonts.family, 13, "bold"),
            text_color=theme.colors.text_primary
        ).pack(anchor="w", padx=theme.spacing.sm, pady=(theme.spacing.md, theme.spacing.sm))

        # Delete button (disabled until selection)
        self.delete_btn = ctk.CTkButton(
            parent,
            text="🗑️ Delete",
            command=self._delete_selected,
            fg_color=theme.colors.bg_light,
            hover_color=theme.colors.error,
            text_color=theme.colors.text_muted,
            height=32,
            state="disabled"
        )
        self.delete_btn.pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.xs)

        # Generate sheet from selected (for characters/props only)
        if self.tag_type in ("character", "prop"):
            self.sheet_btn = ctk.CTkButton(
                parent,
                text="📋 Generate Sheet from Selected",
                command=self._generate_sheet_from_selected,
                fg_color=theme.colors.bg_light,
                hover_color=theme.colors.accent,
                text_color=theme.colors.text_muted,
                height=32,
                state="disabled"
            )
            self.sheet_btn.pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.xs)

        # Generate cardinal views from selected (for locations only - requires selection)
        if self.tag_type == "location":
            self.cardinal_btn = ctk.CTkButton(
                parent,
                text="🧭 Generate Cardinal Views",
                command=self._generate_cardinal_views,
                fg_color=theme.colors.bg_light,
                hover_color=theme.colors.accent,
                text_color=theme.colors.text_muted,
                height=32,
                state="disabled"
            )
            self.cardinal_btn.pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.xs)

        # Separator
        ctk.CTkFrame(parent, height=1, fg_color=theme.colors.bg_dark).pack(
            fill="x", padx=theme.spacing.sm, pady=theme.spacing.md
        )

        # =====================================================================
        # GENERATION OPTIONS
        # =====================================================================
        ctk.CTkLabel(
            parent,
            text="🎨 Generate New",
            font=(theme.fonts.family, 13, "bold"),
            text_color=theme.colors.text_primary
        ).pack(anchor="w", padx=theme.spacing.sm, pady=(theme.spacing.sm, theme.spacing.sm))

        # Model selection
        ctk.CTkLabel(
            parent,
            text="Model:",
            font=(theme.fonts.family, 10),
            text_color=theme.colors.text_secondary
        ).pack(anchor="w", padx=theme.spacing.sm)

        self.model_var = ctk.StringVar(value="nano_banana_pro")
        models = [
            ("Nano Banana (Basic)", "nano_banana"),
            ("Nano Banana Pro (Best)", "nano_banana_pro"),
            ("Seedream 4.5 (Fast)", "seedream"),
        ]

        for label, value in models:
            ctk.CTkRadioButton(
                parent,
                text=label,
                variable=self.model_var,
                value=value,
                font=(theme.fonts.family, 10),
                text_color=theme.colors.text_primary
            ).pack(anchor="w", padx=theme.spacing.md, pady=2)

        # Separator
        ctk.CTkFrame(parent, height=1, fg_color=theme.colors.bg_dark).pack(
            fill="x", padx=theme.spacing.sm, pady=theme.spacing.md
        )

        # =====================================================================
        # TAG-TYPE SPECIFIC GENERATION BUTTONS
        # =====================================================================

        if self.tag_type == "character":
            # Characters: Generate Character Sheet (from description, no input image needed)
            ctk.CTkButton(
                parent,
                text="🎭 Generate Character Sheet",
                command=self._generate_character_sheet,
                fg_color=theme.colors.primary,
                hover_color=theme.colors.primary_hover,
                height=32
            ).pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.xs)

        elif self.tag_type == "prop":
            # Props: Generate Reference (from appearance field)
            ctk.CTkButton(
                parent,
                text="🖼️ Generate Reference",
                command=self._generate_reference,
                fg_color=theme.colors.primary,
                hover_color=theme.colors.primary_hover,
                height=32
            ).pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.xs)

        elif self.tag_type == "location":
            # Locations: Generate Reference (North view only)
            ctk.CTkButton(
                parent,
                text="🖼️ Generate Reference (North)",
                command=self._generate_reference,
                fg_color=theme.colors.primary,
                hover_color=theme.colors.primary_hover,
                height=32
            ).pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.xs)

        # Separator
        ctk.CTkFrame(parent, height=1, fg_color=theme.colors.bg_dark).pack(
            fill="x", padx=theme.spacing.sm, pady=theme.spacing.md
        )

        # Add from file
        ctk.CTkButton(
            parent,
            text="📂 Add from File",
            command=self._add_from_file,
            fg_color="transparent",
            border_width=1,
            border_color=theme.colors.text_muted,
            text_color=theme.colors.text_primary,
            hover_color=theme.colors.bg_medium,
            height=32
        ).pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.xs)

        # Status label
        self.status_label = ctk.CTkLabel(
            parent,
            text="Click an image to select it",
            font=(theme.fonts.family, 9),
            text_color=theme.colors.text_muted,
            wraplength=200
        )
        self.status_label.pack(anchor="w", padx=theme.spacing.sm, pady=theme.spacing.md)

    def _create_cardinal_preview_panel(self, parent):
        """Create the cardinal views preview panel for locations (bottom half)."""
        # Container for cardinal preview - takes up bottom half
        cardinal_section = ctk.CTkFrame(parent, fg_color="transparent")
        cardinal_section.pack(fill="both", expand=True, pady=(theme.spacing.sm, 0))

        # Header
        header = ctk.CTkFrame(cardinal_section, fg_color=theme.colors.bg_dark, height=28, corner_radius=4)
        header.pack(fill="x")
        header.pack_propagate(False)

        self.cardinal_header_label = ctk.CTkLabel(
            header,
            text="🧭 Cardinal Views (select an image)",
            font=(theme.fonts.family, 11, "bold"),
            text_color=theme.colors.text_muted
        )
        self.cardinal_header_label.pack(side="left", padx=theme.spacing.sm, pady=4)

        # Scrollable horizontal container for thumbnails
        self.cardinal_scroll = ctk.CTkScrollableFrame(
            cardinal_section,
            fg_color=theme.colors.bg_light,
            corner_radius=8,
            orientation="horizontal"
        )
        self.cardinal_scroll.pack(fill="both", expand=True, pady=(4, 0))

        # Placeholder text
        self.cardinal_placeholder = ctk.CTkLabel(
            self.cardinal_scroll,
            text="Select a reference image to see its cardinal direction views",
            font=(theme.fonts.family, 10),
            text_color=theme.colors.text_muted
        )
        self.cardinal_placeholder.pack(expand=True, pady=theme.spacing.md)

    def _update_cardinal_preview(self, image_path: Path):
        """Update the cardinal preview panel for the selected image."""
        if not hasattr(self, 'cardinal_scroll'):
            return

        # Clear existing thumbnails
        for widget in self.cardinal_scroll.winfo_children():
            widget.destroy()

        # Find cardinal views for this image
        # Cardinal views are stored in a subdirectory named after the image stem
        refs_dir = self.project_path / "references" / self.tag
        image_stem = image_path.stem

        # Look for subdirectory matching the image name
        cardinal_dir = refs_dir / image_stem
        cardinal_images = []

        if cardinal_dir.exists() and cardinal_dir.is_dir():
            cardinal_images = sorted(
                list(cardinal_dir.glob("*.png")) + list(cardinal_dir.glob("*.jpg"))
            )

        if not cardinal_images:
            # No cardinal views found
            self.cardinal_header_label.configure(
                text=f"🧭 No cardinal views for {image_stem}",
                text_color=theme.colors.text_muted
            )
            ctk.CTkLabel(
                self.cardinal_scroll,
                text="Click '🧭 Generate Cardinal Views' to create them",
                font=(theme.fonts.family, 10),
                text_color=theme.colors.text_muted
            ).pack(expand=True, pady=theme.spacing.md)
            return

        # Update header
        self.cardinal_header_label.configure(
            text=f"🧭 Cardinal Views ({len(cardinal_images)} views)",
            text_color=theme.colors.info
        )

        # Direction icons mapping
        dir_icons = {'n': '⬆️ North', 's': '⬇️ South', 'e': '➡️ East', 'w': '⬅️ West'}

        # Create larger thumbnail cards for the bottom half panel
        for img_path in cardinal_images:
            card = ctk.CTkFrame(
                self.cardinal_scroll,
                fg_color=theme.colors.bg_medium,
                corner_radius=8,
                width=180,
                height=140
            )
            card.pack(side="left", padx=6, pady=4)
            card.pack_propagate(False)

            # Determine direction from filename
            fname = img_path.stem.lower()
            direction_label = "View"
            for code, label in dir_icons.items():
                if f'_dir_{code}' in fname:
                    direction_label = label
                    break

            # Direction label at top
            ctk.CTkLabel(
                card,
                text=direction_label,
                font=(theme.fonts.family, 11, "bold"),
                text_color=theme.colors.info
            ).pack(pady=(4, 2))

            # Larger thumbnail
            try:
                from PIL import Image
                img = Image.open(img_path)
                img.thumbnail((160, 100))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(160, 100))
                img_label = ctk.CTkLabel(card, image=ctk_img, text="")
                img_label.pack(expand=True, padx=4)
                img_label._image = ctk_img
                # Click to open full image
                img_label.bind("<Button-1>", lambda e, p=img_path: self._open_cardinal_image(p))
                card.bind("<Button-1>", lambda e, p=img_path: self._open_cardinal_image(p))
            except Exception:
                ctk.CTkLabel(
                    card,
                    text="🖼️",
                    font=(theme.fonts.family, 32),
                    text_color=theme.colors.text_muted
                ).pack(expand=True)

    def _load_references(self):
        """Load reference images for the tag, auto-labeling any new images.

        Checks if modal is still open before rendering to prevent TclError.
        """
        if not self._is_open:
            return

        handler = self._get_image_handler()

        # Auto-label any new images in the directory
        handler.auto_label_references(self.tag, self.name)

        self._references = handler.get_references_for_tag(self.tag)
        self._key_reference = handler.get_key_reference(self.tag)

        if self._is_open:
            self._render_references()

    def _render_references(self):
        """Render the reference image grid.

        Checks if modal is still open before rendering to prevent TclError.
        """
        if not self._is_open:
            return

        # Clear existing
        try:
            for widget in self.refs_grid.winfo_children():
                widget.destroy()
        except Exception:
            return  # Widget was destroyed

        if not self._references:
            ctk.CTkLabel(
                self.refs_grid,
                text="No references yet.\nGenerate or add images.",
                text_color=theme.colors.text_muted,
                justify="center"
            ).pack(expand=True, pady=theme.spacing.lg)
            return

        # Horizontal layout - pack side by side
        for ref_path in self._references:
            card = self._create_reference_card(ref_path)
            card.pack(side="left", padx=6, pady=4)

    def _open_cardinal_image(self, image_path: Path):
        """Open a cardinal view image in the default viewer."""
        import subprocess
        import sys

        if sys.platform == 'win32':
            subprocess.run(['start', '', str(image_path)], shell=True)
        elif sys.platform == 'darwin':
            subprocess.run(['open', str(image_path)])
        else:
            subprocess.run(['xdg-open', str(image_path)])

    def _create_reference_card(self, image_path: Path) -> ctk.CTkFrame:
        """Create a reference image card with star button, sheet button, and click selection."""
        is_key = self._key_reference and image_path == self._key_reference
        is_selected = self._selected_image and image_path == self._selected_image

        # Card height: taller for characters/props to fit sheet button
        card_height = 195 if self.tag_type in ("character", "prop") else 170

        # Card with gold border for key reference, neon green for selected
        border_color = theme.colors.warning if is_key else (
            theme.colors.neon_green if is_selected else theme.colors.bg_medium
        )
        border_width = 3 if (is_key or is_selected) else 0

        card = ctk.CTkFrame(
            self.refs_grid,
            fg_color=theme.colors.bg_dark if is_key else theme.colors.bg_medium,
            corner_radius=6,
            width=150,
            height=card_height,
            border_width=border_width,
            border_color=border_color
        )
        card.pack_propagate(False)

        # Store card reference for selection updates
        self._card_widgets[image_path] = card

        # Image thumbnail container (with KEY REFERENCE label overlay for starred)
        img_frame = ctk.CTkFrame(card, fg_color=theme.colors.bg_light, height=100, corner_radius=4)
        img_frame.pack(fill="x", padx=4, pady=4)
        img_frame.pack_propagate(False)

        try:
            from PIL import Image
            img = Image.open(image_path)
            img.thumbnail((140, 90))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(140, 90))
            img_label = ctk.CTkLabel(img_frame, image=ctk_img, text="")
            img_label.pack(expand=True)
            img_label._image = ctk_img
            img_label.bind("<Button-1>", lambda e, p=image_path: self._select_image(p))
        except Exception:
            placeholder = ctk.CTkLabel(img_frame, text="🖼️", font=(theme.fonts.family, 24))
            placeholder.pack(expand=True)
            placeholder.bind("<Button-1>", lambda e, p=image_path: self._select_image(p))

        # KEY REFERENCE label overlay for starred images
        if is_key:
            key_label = ctk.CTkLabel(
                img_frame,
                text="⭐ KEY REFERENCE",
                font=(theme.fonts.family, 8, "bold"),
                text_color=theme.colors.warning,
                fg_color=theme.colors.bg_dark,
                corner_radius=3
            )
            key_label.place(x=2, y=2)

        # Bind click on card and img_frame
        card.bind("<Button-1>", lambda e, p=image_path: self._select_image(p))
        img_frame.bind("<Button-1>", lambda e, p=image_path: self._select_image(p))

        # Bottom row with star and filename
        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.pack(fill="x", padx=4)

        # Star button
        star_text = "⭐" if is_key else "☆"
        star_btn = ctk.CTkButton(
            bottom,
            text=star_text,
            width=24,
            height=24,
            fg_color="transparent" if not is_key else theme.colors.warning,
            hover_color=theme.colors.warning,
            command=lambda p=image_path: self._set_key_reference(p)
        )
        star_btn.pack(side="left")

        # Filename (truncated)
        fname = image_path.name
        if len(fname) > 12:
            fname = fname[:9] + "..."
        fname_label = ctk.CTkLabel(
            bottom,
            text=fname,
            font=(theme.fonts.family, 8),
            text_color=theme.colors.text_muted
        )
        fname_label.pack(side="left", padx=2)
        fname_label.bind("<Button-1>", lambda e, p=image_path: self._select_image(p))

        # Generate Sheet button - ONLY on individual loaded images for characters/props
        if self.tag_type in ("character", "prop"):
            sheet_btn = ctk.CTkButton(
                card,
                text="📋 Sheet",
                width=60,
                height=20,
                font=(theme.fonts.family, 9),
                fg_color=theme.colors.accent,
                hover_color=theme.colors.accent_hover,
                command=lambda p=image_path: self._generate_sheet_from_image(p)
            )
            sheet_btn.pack(pady=(2, 4))

        return card

    def _select_image(self, image_path: Path):
        """Select an image (neon green outline) and enable action buttons."""
        self._selected_image = image_path

        # Update all card borders (with safety check for destroyed widgets)
        for path, card in list(self._card_widgets.items()):
            try:
                if card.winfo_exists():
                    if path == image_path:
                        card.configure(border_width=3, border_color=theme.colors.neon_green)
                    else:
                        card.configure(border_width=0, border_color=theme.colors.bg_dark)
            except Exception:
                # Widget was destroyed, remove from tracking
                pass

        # Enable action buttons
        self.delete_btn.configure(
            state="normal",
            fg_color=theme.colors.error,
            text_color=theme.colors.text_primary
        )
        if hasattr(self, 'sheet_btn'):
            self.sheet_btn.configure(
                state="normal",
                fg_color=theme.colors.accent,
                text_color=theme.colors.text_primary
            )
        # Enable cardinal views button for locations
        if hasattr(self, 'cardinal_btn'):
            self.cardinal_btn.configure(
                state="normal",
                fg_color=theme.colors.accent,
                text_color=theme.colors.text_primary
            )

        # Update cardinal preview for locations
        if self.tag_type == "location":
            self._update_cardinal_preview(image_path)

        # Update status
        self.status_label.configure(text=f"Selected: {image_path.name}")

    def _delete_selected(self):
        """Delete the currently selected image."""
        if not self._selected_image:
            return

        image_path = self._selected_image

        # Confirm deletion
        try:
            import os
            os.remove(image_path)

            # If this was the key reference, clear it
            if self._key_reference == image_path:
                self._key_reference = None

            # Clear selection
            self._selected_image = None

            # Reload references
            self._load_references()
            self.status_label.configure(text=f"✓ Deleted {image_path.name}")

            if self.on_change:
                self.on_change()
        except Exception as e:
            self.status_label.configure(text=f"❌ Error: {e}")

    def _generate_sheet_from_selected(self):
        """Generate a reference sheet using the selected image as input.

        EXCEPTION CASE: When generating from an input image, use PROMPT_TEMPLATE_EDIT
        with style suffix ONLY - do NOT include character description.
        The input image IS the character definition.

        DEPRECATED: Use UnifiedReferenceScript.convert_reference_to_sheet() instead.
        """
        _deprecated_method("_generate_sheet_from_selected", "UnifiedReferenceScript.convert_reference_to_sheet()")
        if not self._selected_image:
            return

        self.status_label.configure(text="🔄 Generating sheet from selected...")

        def run_generation():
            import asyncio
            from datetime import datetime
            from greenlight.core.image_handler import ImageRequest

            handler = self._get_image_handler()
            model = self._get_selected_model()

            # Get style suffix from Context Engine (single source of truth)
            style_suffix = ""
            if self._context_engine:
                style_suffix = self._context_engine.get_world_style()

            # EXCEPTION CASE: Sheet from input image uses minimal prompt
            # Only layout instructions - NO character description (image IS the definition)
            if self.tag_type == "character":
                prompt = "Create a character reference sheet with multiple views (front, side, back, 3/4 view). Maintain consistent appearance across all views. Clean white background, professional character turnaround sheet layout."
            else:  # prop
                prompt = "Create a prop reference sheet showing this object from multiple angles (front, side, top, 3/4 view). Maintain consistent appearance. Clean white background, professional product sheet layout."

            # Create output path
            refs_dir = self.project_path / "references" / self.tag
            refs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = refs_dir / f"{self.tag}_sheet_{timestamp}.png"

            request = ImageRequest(
                prompt=prompt,
                model=model,
                aspect_ratio="16:9",
                tag=self.tag,
                output_path=output_path,
                reference_images=[self._selected_image],  # Use selected as input
                prefix_type="edit",  # EXCEPTION: Use edit template for sheet from input
                style_suffix=style_suffix if style_suffix else None,
                add_clean_suffix=True
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(handler.generate(request))
                if result.success:
                    self.after(0, lambda r=result: self._on_generation_complete(r))
                else:
                    error_msg = result.error
                    self.after(0, lambda msg=error_msg: self._safe_status_update(f"❌ {msg}"))
            except Exception as e:
                error_str = str(e)
                self.after(0, lambda msg=error_str: self._safe_status_update(f"❌ Error: {msg}"))
            finally:
                loop.close()

        import threading
        threading.Thread(target=run_generation, daemon=True).start()

    def _set_key_reference(self, image_path: Path):
        """Set an image as the key reference."""
        handler = self._get_image_handler()
        handler.set_key_reference(self.tag, image_path)
        self._key_reference = image_path
        self._render_references()
        self.status_label.configure(text=f"✓ Set as key reference")

        if self.on_change:
            self.on_change()

    def _generate_sheet_from_image(self, image_path: Path):
        """Generate a character/prop sheet from a specific image (button on card).

        EXCEPTION CASE: When generating from an input image, use PROMPT_TEMPLATE_EDIT
        with style suffix ONLY - do NOT include character description.
        The input image IS the character definition.

        DEPRECATED: Use UnifiedReferenceScript.convert_image_to_sheet() instead.
        """
        _deprecated_method("_generate_sheet_from_image", "UnifiedReferenceScript.convert_image_to_sheet()")
        self.status_label.configure(text=f"🔄 Generating sheet from {image_path.name}...")

        def run_generation():
            import asyncio
            from datetime import datetime
            from greenlight.core.image_handler import ImageRequest

            handler = self._get_image_handler()
            model = self._get_selected_model()

            # Get style suffix from Context Engine (single source of truth)
            style_suffix = ""
            if self._context_engine:
                style_suffix = self._context_engine.get_world_style()

            # EXCEPTION CASE: Sheet from input image uses minimal prompt
            # Only layout instructions - NO character description (image IS the definition)
            if self.tag_type == "character":
                prompt = "Create a character reference sheet with multiple views (front, side, back, 3/4 view). Maintain consistent appearance across all views. Clean white background, professional character turnaround sheet layout."
            else:  # prop
                prompt = "Create a prop reference sheet showing this object from multiple angles (front, side, top, 3/4 view). Maintain consistent appearance. Clean white background, professional product sheet layout."

            # Create output path
            refs_dir = self.project_path / "references" / self.tag
            refs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = refs_dir / f"{self.tag}_sheet_{timestamp}.png"

            request = ImageRequest(
                prompt=prompt,
                model=model,
                aspect_ratio="16:9",
                tag=self.tag,
                output_path=output_path,
                reference_images=[image_path],  # Use the specific image as input
                prefix_type="edit",  # EXCEPTION: Use edit template for sheet from input
                style_suffix=style_suffix if style_suffix else None,
                add_clean_suffix=True
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(handler.generate(request))
                if result.success:
                    self.after(0, lambda r=result: self._on_generation_complete(r))
                else:
                    error_msg = result.error
                    self.after(0, lambda msg=error_msg: self._safe_status_update(f"❌ {msg}"))
            except Exception as e:
                error_str = str(e)
                self.after(0, lambda msg=error_str: self._safe_status_update(f"❌ Error: {msg}"))
            finally:
                loop.close()

        import threading
        threading.Thread(target=run_generation, daemon=True).start()

    def get_flattened_key_reference(self) -> Optional[Path]:
        """
        Get the key reference image, flattened with its labeled frame.

        If the key reference exists, creates a flattened version with
        a gold border and "KEY REFERENCE" label baked into the image.
        This is used when passing the key reference to generation pipelines.
        """
        if not self._key_reference or not self._key_reference.exists():
            return None

        return self._flatten_with_frame(self._key_reference)

    def _flatten_with_frame(self, image_path: Path) -> Path:
        """Flatten image with its labeled frame into a single image."""
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(image_path)

        # Add gold border
        draw = ImageDraw.Draw(img)
        border_width = 5
        draw.rectangle(
            [0, 0, img.width - 1, img.height - 1],
            outline="#FFD700",  # Gold color
            width=border_width
        )

        # Add "KEY REFERENCE" label
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()

        # Draw label background
        label_text = "KEY REFERENCE"
        bbox = draw.textbbox((0, 0), label_text, font=font)
        label_width = bbox[2] - bbox[0] + 10
        label_height = bbox[3] - bbox[1] + 6
        draw.rectangle([5, 5, 5 + label_width, 5 + label_height], fill="#FFD700")
        draw.text((10, 7), label_text, fill="black", font=font)

        # Save flattened version
        flattened_path = image_path.parent / f"{image_path.stem}_key_flattened.png"
        img.save(flattened_path)

        return flattened_path

    def _get_selected_model(self):
        """Get the selected ImageModel."""
        from greenlight.core.image_handler import ImageModel
        model_map = {
            "nano_banana": ImageModel.NANO_BANANA,
            "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
            "seedream": ImageModel.SEEDREAM,
        }
        return model_map.get(self.model_var.get(), ImageModel.NANO_BANANA_PRO)

    def _generate_reference(self):
        """Generate a new reference image.

        Uses PROMPT_TEMPLATE_RECREATE for character/prop/location references.
        Style suffix is obtained from Context Engine's get_world_style().

        DEPRECATED: Use UnifiedReferenceScript.generate_character_sheet() instead.
        """
        _deprecated_method("_generate_reference", "UnifiedReferenceScript.generate_character_sheet()")
        self.status_label.configure(text="🔄 Generating reference...")

        def run_generation():
            import asyncio
            from datetime import datetime
            from greenlight.core.image_handler import ImageRequest

            handler = self._get_image_handler()
            model = self._get_selected_model()

            # Build prompt based on tag type and world config
            prompt = self._build_reference_prompt()

            # Get style suffix from Context Engine (single source of truth)
            style_suffix = ""
            if self._context_engine:
                style_suffix = self._context_engine.get_world_style()

            # Create output path in the tag's reference directory
            refs_dir = self.project_path / "references" / self.tag
            refs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = refs_dir / f"{self.tag}_{timestamp}.png"

            request = ImageRequest(
                prompt=prompt,
                model=model,
                aspect_ratio="16:9",
                tag=self.tag,
                output_path=output_path,
                prefix_type="recreate",  # Use recreate template for reference generation
                style_suffix=style_suffix if style_suffix else None,
                add_clean_suffix=True
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(handler.generate(request))
                self.after(0, lambda: self._on_generation_complete(result))
            finally:
                loop.close()

        thread = threading.Thread(target=run_generation, daemon=True)
        thread.start()

    def _build_reference_prompt(self) -> str:
        """Build a prompt for reference generation based on world config.

        Uses correct fields per tag type:
        - Characters: appearance + costume (for character sheet)
        - Props: appearance
        - Locations: description + atmosphere + directional_views.north (North view)

        DEPRECATED: Use ReferencePromptAgent.generate_prompt() instead.
        """
        _deprecated_method("_build_reference_prompt", "ReferencePromptAgent.generate_prompt()")
        if self.tag_type == "character":
            # Characters should use _generate_character_sheet() instead
            # This is a fallback that uses all visual attributes
            chars = self.world_config.get("characters", [])
            char_data = next((c for c in chars if c.get("tag") == self.tag), {})
            appearance = char_data.get('appearance', char_data.get('visual_appearance', char_data.get('description', '')))
            costume = char_data.get('costume', '')
            age = char_data.get('age', '')
            ethnicity = char_data.get('ethnicity', '')

            # Build prompt with all visual attributes
            prompt_parts = [f"Character reference for [{self.tag}] {self.name}."]
            if age:
                prompt_parts.append(f"Age: {age}")
            if ethnicity:
                prompt_parts.append(f"Ethnicity: {ethnicity}")
            if appearance:
                prompt_parts.append(f"Appearance: {appearance}")
            if costume:
                prompt_parts.append(f"Costume: {costume}")
            prompt_parts.append("\nFull body portrait, detailed character design, high quality, 16:9 aspect ratio.")

            return "\n".join(prompt_parts)

        elif self.tag_type == "location":
            # Locations: Generate North view using all location attributes
            locs = self.world_config.get("locations", [])
            loc_data = next((l for l in locs if l.get("tag") == self.tag), {})
            description = loc_data.get('description', '')
            atmosphere = loc_data.get('atmosphere', '')
            time_period = loc_data.get('time_period', '')
            directional_views = loc_data.get('directional_views', {})
            north_view = directional_views.get('north', '')

            prompt_parts = [f"Location reference (NORTH VIEW) for [{self.tag}] {self.name}."]
            if time_period:
                prompt_parts.append(f"Time Period: {time_period}")
            if description:
                prompt_parts.append(f"Description: {description}")
            if atmosphere:
                prompt_parts.append(f"Atmosphere: {atmosphere}")
            if north_view:
                prompt_parts.append(f"North View Details: {north_view}")
            prompt_parts.append("\nEstablishing shot facing NORTH, detailed environment, atmospheric lighting, 16:9 aspect ratio.")

            return "\n".join(prompt_parts)

        elif self.tag_type == "prop":
            # Props: Use appearance, significance, and associated_character fields
            props = self.world_config.get("props", [])
            prop_data = next((p for p in props if p.get("tag") == self.tag), {})
            appearance = prop_data.get('appearance', prop_data.get('description', ''))
            significance = prop_data.get('significance', '')
            associated_char = prop_data.get('associated_character', '')

            # Build prompt with all prop attributes
            prompt_parts = [f"Prop reference for [{self.tag}] {self.name}."]
            if appearance:
                prompt_parts.append(f"Appearance: {appearance}")
            if significance:
                prompt_parts.append(f"Significance: {significance}")
            if associated_char:
                prompt_parts.append(f"Associated with: {associated_char}")
            prompt_parts.append("\nDetailed object study, clean background, high quality, 16:9 aspect ratio.")

            return "\n".join(prompt_parts)

        return f"Reference image for [{self.tag}] {self.name}. High quality, detailed, 16:9 aspect ratio."

    def _on_generation_complete(self, result):
        """Handle generation completion.

        Uses _safe_status_update to prevent TclError if modal was closed
        before the async callback executes.
        """
        if result.success:
            self._safe_status_update(f"✓ Generated in {result.generation_time_ms}ms")
            if self._is_open:
                self._load_references()
            if self.on_change:
                self.on_change()
        else:
            self._safe_status_update(f"✗ Error: {result.error}")

    def _generate_character_sheet(self):
        """Generate a character sheet using ImageHandler's unified prompt generation.

        Uses the Character Reference Template as a layout guide.
        Generates a multi-view character turnaround sheet.
        Uses PROMPT_TEMPLATE_RECREATE for character sheet generation.
        Style suffix is obtained from Context Engine's get_world_style().

        DEPRECATED: Use UnifiedReferenceScript.generate_character_sheet() instead.
        """
        _deprecated_method("_generate_character_sheet", "UnifiedReferenceScript.generate_character_sheet()")
        self.status_label.configure(text="🔄 Generating character sheet...")

        def run_generation():
            import asyncio
            from datetime import datetime
            from greenlight.core.image_handler import ImageRequest

            handler = self._get_image_handler()
            model = self._get_selected_model()

            # Get character data from world config
            chars = self.world_config.get("characters", [])
            char_data = next((c for c in chars if c.get("tag") == self.tag), {})

            # Use ImageHandler's unified prompt generation (includes ContextEngine data)
            prompt = handler.get_character_sheet_prompt(
                self.tag, self.name, character_data=char_data
            )

            # Get style suffix from Context Engine (single source of truth)
            style_suffix = ""
            if self._context_engine:
                style_suffix = self._context_engine.get_world_style()

            # Reference images for initial character sheet generation:
            # ONLY include Character_Reference_Template.png as a LAYOUT GUIDE
            # NO existing character references - this is a fresh generation from description
            reference_images = []

            # Add template as layout guide (shows the multi-view grid format)
            template_path = Path(__file__).parent.parent.parent / "assets" / "Character_Reference_Template.png"
            if template_path.exists():
                reference_images.append(template_path)

            # Create output path
            # Filename format: [{TAG}]_sheet_{timestamp}.png
            refs_dir = self.project_path / "references" / self.tag
            refs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = refs_dir / f"[{self.tag}]_sheet_{timestamp}.png"

            request = ImageRequest(
                prompt=prompt,
                model=model,
                aspect_ratio="16:9",
                tag=self.tag,
                output_path=output_path,
                reference_images=reference_images if reference_images else None,
                prefix_type="recreate",  # Use recreate template for character sheets
                style_suffix=style_suffix if style_suffix else None,
                add_clean_suffix=True
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(handler.generate(request))
                if result.success:
                    self.after(0, lambda r=result: self._on_generation_complete(r))
                else:
                    error_msg = result.error
                    self.after(0, lambda msg=error_msg: self._safe_status_update(f"❌ {msg}"))
            except Exception as e:
                error_str = str(e)
                self.after(0, lambda msg=error_str: self._safe_status_update(f"❌ Error: {msg}"))
            finally:
                loop.close()

        import threading
        threading.Thread(target=run_generation, daemon=True).start()

    def _generate_sheet(self):
        """Generate a multiview character/prop sheet.

        DEPRECATED: Use UnifiedReferenceScript.generate_character_sheet() or
        generate_prop_sheet() instead.
        """
        _deprecated_method("_generate_sheet", "UnifiedReferenceScript.generate_character_sheet()")
        self.status_label.configure(text="🔄 Generating sheet...")

        # Get character data for the prompt if this is a character
        char_data = None
        if self.tag_type == "character":
            chars = self.world_config.get("characters", [])
            char_data = next((c for c in chars if c.get("tag") == self.tag), None)

        def run_generation():
            import asyncio
            handler = self._get_image_handler()
            model = self._get_selected_model()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    handler.generate_character_sheet(
                        self.tag, self.name, model,
                        character_data=char_data
                    )
                )
                self.after(0, lambda: self._on_generation_complete(result))
            finally:
                loop.close()

        thread = threading.Thread(target=run_generation, daemon=True)
        thread.start()

    def _generate_cardinal_views(self):
        """Generate cardinal direction views for a location.

        Uses the reference project approach:
        1. Generate NORTH first using the selected image as reference
        2. Generate E/S/W using the NORTH image as reference with rotation prompts
        3. Include direction-specific descriptions from world bible directional_views

        Structure:
            references/{LOC_TAG}/{selected_image_stem}/
                {selected_image_stem}_dir_n.png
                {selected_image_stem}_dir_e.png
                {selected_image_stem}_dir_s.png
                {selected_image_stem}_dir_w.png

        DEPRECATED: Use UnifiedReferenceScript.generate_location_views() instead.
        """
        _deprecated_method("_generate_cardinal_views", "UnifiedReferenceScript.generate_location_views()")
        if not self._selected_image:
            self.status_label.configure(text="⚠️ Select an image first")
            return

        self.status_label.configure(text="🔄 Generating NORTH view (1/4)...")
        selected_image = self._selected_image

        def run_generation():
            import asyncio
            from greenlight.core.image_handler import ImageRequest, ImageResult

            handler = self._get_image_handler()
            model = self._get_selected_model()

            # Get location data from world bible
            locs = self.world_config.get("locations", [])
            loc_data = next((l for l in locs if l.get("tag") == self.tag), {})

            description = loc_data.get('description', '')
            atmosphere = loc_data.get('atmosphere', '')
            time_period = loc_data.get('time_period', '')
            directional_views = loc_data.get('directional_views', {})
            visual_keywords = loc_data.get('visual_keywords', [])
            period_details = loc_data.get('period_details', {})

            # Build visual context
            visual_desc = ", ".join(visual_keywords) if visual_keywords else ""
            arch_style = period_details.get("architecture", "") if period_details else ""
            lighting = period_details.get("lighting", "") if period_details else ""

            # Create subdirectory named after selected image stem
            image_stem = selected_image.stem
            cardinal_dir = self.project_path / "references" / self.tag / image_stem
            cardinal_dir.mkdir(parents=True, exist_ok=True)

            results = []
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # === STEP 1: Generate NORTH view first ===
                north_view_desc = directional_views.get('north', '')
                north_path = cardinal_dir / f"{image_stem}_dir_n.png"

                north_prompt = f"""Create a cinematic establishing shot of "{self.name}" facing NORTH.

{f"TIME PERIOD: {time_period}" if time_period else ""}
LOCATION: {description}
ATMOSPHERE: {atmosphere}
{f"NORTH VIEW: {north_view_desc}" if north_view_desc else ""}
{f"ARCHITECTURE: {arch_style}" if arch_style else ""}
{f"LIGHTING: {lighting}" if lighting else ""}
{f"VISUAL DETAILS: {visual_desc}" if visual_desc else ""}

REQUIREMENTS:
- Wide establishing shot showing the full environment
- Camera facing NORTH direction
- High quality cinematic composition
- 16:9 aspect ratio
- Consistent with the location's period and atmosphere
- Match the style and visual quality of the reference image"""

                north_request = ImageRequest(
                    prompt=north_prompt,
                    model=model,
                    aspect_ratio="16:9",
                    tag=f"{self.tag}_DIR_N",
                    output_path=north_path,
                    reference_images=[selected_image]
                )

                try:
                    north_result = loop.run_until_complete(handler.generate(north_request))
                    results.append(north_result)
                    self.after(0, lambda: self._safe_status_update("🔄 NORTH complete. Generating EAST (2/4)..."))
                except Exception as e:
                    results.append(ImageResult(success=False, error=str(e)))
                    # Can't continue without NORTH
                    self.after(0, lambda: self._on_cardinal_complete(0, 4))
                    return

                if not north_result.success or not north_path.exists():
                    self.after(0, lambda: self._on_cardinal_complete(0, 4))
                    return

                # === STEP 2: Generate E/S/W using NORTH as reference ===
                # Direction info with rotation prompts
                other_directions = [
                    ('e', 'east', 'EAST', "Turn 90 degrees RIGHT from the north view"),
                    ('s', 'south', 'SOUTH', "Turn 180 degrees from the north view (opposite direction)"),
                    ('w', 'west', 'WEST', "Turn 90 degrees LEFT from the north view"),
                ]

                for i, (dir_code, dir_key, dir_label, rotation_desc) in enumerate(other_directions, 2):
                    dir_view_desc = directional_views.get(dir_key, '')
                    dir_path = cardinal_dir / f"{image_stem}_dir_{dir_code}.png"

                    dir_prompt = f"""Get a new angle of this scene facing {dir_label}.

REFERENCE: The first image shows this location facing NORTH.
TASK: {rotation_desc} to show the {dir_label} view of the same location.

{f"TIME PERIOD: {time_period}" if time_period else ""}
{f"{dir_label} VIEW: {dir_view_desc}" if dir_view_desc else ""}
LOCATION: {description}
ATMOSPHERE: {atmosphere}

REQUIREMENTS:
- Same location, different camera direction
- Maintain consistent architecture, lighting, and atmosphere
- Camera now facing {dir_label}
- High quality cinematic composition
- 16:9 aspect ratio"""

                    dir_request = ImageRequest(
                        prompt=dir_prompt,
                        model=model,
                        aspect_ratio="16:9",
                        tag=f"{self.tag}_DIR_{dir_code.upper()}",
                        output_path=dir_path,
                        reference_images=[north_path]  # Use NORTH as reference
                    )

                    try:
                        result = loop.run_until_complete(handler.generate(dir_request))
                        results.append(result)
                        next_dir = ["SOUTH", "WEST", "complete"][i - 2] if i < 4 else "complete"
                        self.after(0, lambda d=dir_label, n=next_dir, c=i: self._safe_status_update(
                            f"🔄 {d} complete. {'Generating ' + n if n != 'complete' else 'Finishing up'} ({c}/4)..."
                        ))
                    except Exception as e:
                        results.append(ImageResult(success=False, error=str(e)))

                success_count = sum(1 for r in results if r.success)
                self.after(0, lambda: self._on_cardinal_complete(success_count, len(results)))
            finally:
                loop.close()

        import threading
        threading.Thread(target=run_generation, daemon=True).start()

    def _on_cardinal_complete(self, success: int, total: int):
        """Handle cardinal view generation completion."""
        self._safe_status_update(f"✓ Generated {success}/{total} cardinal views")
        if self._is_open:
            self._load_references()
        if self.on_change:
            self.on_change()

    def _add_from_file(self):
        """Add a reference image from file."""
        from tkinter import filedialog
        import shutil

        file_path = filedialog.askopenfilename(
            title=f"Select reference image for [{self.tag}]",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.gif"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            src = Path(file_path)
            # Save to tag's subdirectory (references/{TAG}/)
            refs_dir = self.project_path / "references" / self.tag
            refs_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename
            counter = len(list(refs_dir.glob(f"{self.tag}*")))
            suffix = f"_{counter}" if counter > 0 else ""
            dest = refs_dir / f"{self.tag}{suffix}{src.suffix}"

            try:
                # Copy the file (not move) so original is preserved
                shutil.copy2(src, dest)
                self.status_label.configure(text=f"✓ Copied {dest.name}")
                # _load_references will auto-label the new image
                self._load_references()
                if self.on_change:
                    self.on_change()
            except Exception as e:
                self.status_label.configure(text=f"✗ Error: {e}")

    def _on_close(self):
        """Handle modal close."""
        self._is_open = False
        self.grab_release()
        self.destroy()
