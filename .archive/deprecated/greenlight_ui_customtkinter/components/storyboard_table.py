"""
Greenlight Storyboard Table

Timeline view with zoom morphing between:
- Grid view (0-49% zoom): 10 columns at 1%, scaling down to 3 columns at 49%
- Linear row view (50-100% zoom): Horizontal scroll, 10 images at 50%, 1 fitted centered image at 100%

Features:
- Linear scaling ratio for each half
- Bottom navigator bar with full timeline preview
- Click/scroll/tap-to-snap navigation
- Images scale WITH cards (not fixed size)
- Horizontal scrolling in row mode (>50%)
- 100% zoom = single fitted centered frame
"""

import customtkinter as ctk
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from pathlib import Path
import math

from greenlight.ui.theme import theme
from greenlight.core.logging_config import get_logger
from greenlight.core.thumbnail_manager import get_thumbnail_manager, THUMB_SMALL, THUMB_MEDIUM, THUMB_LARGE

logger = get_logger("ui.storyboard_table")


@dataclass
class StoryboardFrame:
    """A single frame in the storyboard."""
    shot_id: str
    scene_number: int
    frame_number: int
    prompt: str = ""
    image_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    camera: str = ""
    lighting: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class ZoomController:
    """
    Controls zoom level and calculates layout parameters.

    Zoom ranges:
    - 0-49%: Grid view (10 cols at 1% → 3 cols at 49%)
    - 50-100%: Row view (10 images at 50% → 1 image at 100%)
    """

    def __init__(self):
        self.zoom_level: float = 50.0  # Start at transition point
        self.min_zoom: float = 0.0
        self.max_zoom: float = 100.0

    def set_zoom(self, level: float) -> None:
        """Set zoom level (0-100)."""
        self.zoom_level = max(self.min_zoom, min(self.max_zoom, level))

    def get_zoom(self) -> float:
        """Get current zoom level."""
        return self.zoom_level

    def is_grid_mode(self) -> bool:
        """Check if in grid mode (< 50%)."""
        return self.zoom_level < 50.0

    def is_row_mode(self) -> bool:
        """Check if in row mode (>= 50%)."""
        return self.zoom_level >= 50.0

    def get_grid_columns(self) -> int:
        """
        Calculate grid columns for grid mode (zoom < 50%).

        Zoom 1% = 10 columns
        Zoom 49% = 3 columns
        Linear interpolation between.
        """
        if self.zoom_level >= 50:
            return 3  # Minimum for grid mode

        # Map 1-49% to 10-3 columns
        # At 1%: 10 cols, at 49%: 3 cols
        zoom_normalized = (self.zoom_level - 1) / 48  # 0.0 to 1.0
        columns = 10 - int(zoom_normalized * 7)  # 10 down to 3
        return max(3, min(10, columns))

    def get_row_visible_count(self) -> int:
        """
        Calculate visible images for row mode (zoom >= 50%).

        Zoom 50% = 10 images visible
        Zoom 100% = 1 image visible
        Linear interpolation between.
        """
        if self.zoom_level < 50:
            return 10  # Maximum for row mode

        # Map 50-100% to 10-1 images
        # At 50%: 10 images, at 100%: 1 image
        zoom_normalized = (self.zoom_level - 50) / 50  # 0.0 to 1.0
        visible = 10 - int(zoom_normalized * 9)  # 10 down to 1
        return max(1, min(10, visible))
    
    def get_center_scale(self) -> float:
        """
        Get scale factor for center image in row mode.
        
        At 55%: center slightly larger (1.2x)
        At 100%: center fills view (1.0x of available space)
        """
        if not self.is_row_mode():
            return 1.0
        
        t = (self.zoom_level - 50.0) / 50.0
        # Center image gets larger as we zoom in
        return 1.0 + (0.5 * t)
    
    def get_side_scale(self) -> float:
        """Get scale factor for side images in row mode."""
        if not self.is_row_mode():
            return 1.0
        
        t = (self.zoom_level - 50.0) / 50.0
        # Side images get smaller as we zoom in
        return max(0.5, 1.0 - (0.3 * t))


class TimelineNavigator(ctk.CTkFrame):
    """
    Bottom navigator bar showing full timeline preview.

    Features:
    - Miniature view of all frames
    - Click to jump to frame
    - Drag to scroll
    - View indicator centered on playhead position
    """

    def __init__(
        self,
        master,
        on_navigate: Callable[[int], None] = None,
        **kwargs
    ):
        super().__init__(master, height=30, **kwargs)  # Half height (was 60)

        self.on_navigate = on_navigate
        self.frames: List[StoryboardFrame] = []
        self.current_index: int = 0
        self.visible_count: int = 1  # How many frames are visible in current view

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the navigator UI."""
        self.configure(fg_color=theme.colors.bg_dark)
        self.pack_propagate(False)

        # Canvas for drawing timeline - half height
        self.canvas = ctk.CTkCanvas(
            self,
            height=24,  # Was 50
            bg=theme.colors.bg_dark,
            highlightthickness=0
        )
        self.canvas.pack(fill="x", padx=5, pady=3)
        
        # Bind events
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<Configure>", self._on_resize)

    def set_frames(self, frames: List[StoryboardFrame]) -> None:
        """Set the frames to display."""
        self.frames = frames
        self._redraw()

    def set_view_range(self, start: int, end: int) -> None:
        """Set the visible count (how many frames visible in current zoom)."""
        # Calculate visible count from range
        self.visible_count = max(1, end - start)
        self._redraw()

    def set_current_index(self, index: int) -> None:
        """Set the current frame index (playhead position)."""
        self.current_index = max(0, min(len(self.frames) - 1, index))
        self._redraw()

    def _redraw(self) -> None:
        """Redraw the timeline with view indicator centered on playhead."""
        self.canvas.delete("all")

        if not self.frames:
            return

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        if width <= 1:
            return

        frame_count = len(self.frames)
        frame_width = max(2, width / frame_count)

        # Draw frame markers (smaller for half-height bar)
        for i, frame in enumerate(self.frames):
            x = i * frame_width

            # Color based on scene
            scene_colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"]
            color = scene_colors[frame.scene_number % len(scene_colors)]

            # Draw frame rectangle (reduced padding for smaller bar)
            self.canvas.create_rectangle(
                x, 2, x + frame_width - 1, height - 2,
                fill=color,
                outline=""
            )

        # Draw view range indicator CENTERED on current playhead position
        if frame_count > 0 and self.visible_count > 0:
            # Calculate view range centered on current index
            half_visible = self.visible_count / 2.0
            view_start = self.current_index - half_visible + 0.5
            view_end = self.current_index + half_visible + 0.5

            # Clamp to valid range
            if view_start < 0:
                view_end -= view_start
                view_start = 0
            if view_end > frame_count:
                view_start -= (view_end - frame_count)
                view_end = frame_count
            view_start = max(0, view_start)

            start_x = view_start * frame_width
            end_x = view_end * frame_width

            self.canvas.create_rectangle(
                start_x, 0, end_x, height,
                fill="",
                outline=theme.colors.accent,
                width=2
            )

        # Draw current position marker (playhead) - white line
        if 0 <= self.current_index < frame_count:
            marker_x = (self.current_index + 0.5) * frame_width
            self.canvas.create_line(
                marker_x, 0, marker_x, height,
                fill="#ffffff",
                width=2
            )

    def _on_click(self, event) -> None:
        """Handle click to navigate."""
        if not self.frames:
            return

        width = self.canvas.winfo_width()
        frame_width = width / len(self.frames)
        index = int(event.x / frame_width)
        index = max(0, min(len(self.frames) - 1, index))

        self.current_index = index
        self._redraw()

        if self.on_navigate:
            self.on_navigate(index)

    def _on_drag(self, event) -> None:
        """Handle drag to scroll."""
        self._on_click(event)

    def _on_resize(self, event) -> None:
        """Handle resize."""
        self._redraw()


class FlippingFrameCard(ctk.CTkFrame):
    """
    Flipping frame card for storyboard display.

    Front side: Generated image (or placeholder)
    Back side: Visual script input with confirmed tags as thumbnails

    Click flip button to toggle between sides.
    """

    def __init__(
        self,
        master,
        frame_data: StoryboardFrame,
        size: tuple = (160, 90),
        on_click: Callable[[StoryboardFrame], None] = None,
        on_selection_change: Callable[[StoryboardFrame, bool], None] = None,
        project_path: Optional[Path] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.frame_data = frame_data
        self.size = size
        self.on_click = on_click
        self.on_selection_change = on_selection_change
        self.project_path = project_path
        self.is_selected = False
        self.is_flipped = False  # False = front (image), True = back (script)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the flipping card UI."""
        self.configure(
            fg_color=theme.colors.bg_medium,
            corner_radius=4
        )

        # Container for both sides
        self.card_container = ctk.CTkFrame(
            self,
            width=self.size[0],
            height=self.size[1] + 30,
            fg_color="transparent"
        )
        self.card_container.pack(padx=2, pady=2)
        self.card_container.pack_propagate(False)

        # Front side (image)
        self.front_frame = ctk.CTkFrame(
            self.card_container,
            width=self.size[0],
            height=self.size[1],
            fg_color=theme.colors.bg_dark,
            corner_radius=2
        )
        self.front_frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self.front_frame.pack_propagate(False)

        # Load image or show placeholder
        self._setup_front_side()

        # Back side (visual script) - hidden initially
        self.back_frame = ctk.CTkFrame(
            self.card_container,
            width=self.size[0],
            height=self.size[1],
            fg_color=theme.colors.bg_light,
            corner_radius=2
        )
        # Back frame is not placed initially

        self._setup_back_side()

        # Bottom bar with shot ID, selection checkbox, and flip button
        self.bottom_bar = ctk.CTkFrame(
            self.card_container,
            height=28,
            fg_color="transparent"
        )
        self.bottom_bar.place(x=0, rely=1.0, relwidth=1.0, anchor="sw")

        # Selection checkbox (for batch operations)
        self._selection_var = ctk.BooleanVar(value=False)
        self.selection_checkbox = ctk.CTkCheckBox(
            self.bottom_bar,
            text="",
            variable=self._selection_var,
            width=18,
            height=18,
            checkbox_width=14,
            checkbox_height=14,
            fg_color=theme.colors.accent,
            hover_color=theme.colors.accent_hover,
            command=self._on_selection_changed
        )
        self.selection_checkbox.pack(side="left", padx=2)

        # Shot ID
        self.id_label = ctk.CTkLabel(
            self.bottom_bar,
            text=self.frame_data.shot_id,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=theme.colors.text_primary
        )
        self.id_label.pack(side="left", padx=2)

        # Flip button
        self.flip_btn = ctk.CTkButton(
            self.bottom_bar,
            text="🔄",
            width=24,
            height=20,
            fg_color=theme.colors.bg_medium,
            hover_color=theme.colors.bg_hover,
            command=self._flip_card
        )
        self.flip_btn.pack(side="right", padx=2)

        # Bind click on front/back
        self.front_frame.bind("<Button-1>", self._handle_click)
        self.back_frame.bind("<Button-1>", self._handle_click)

    def _setup_front_side(self) -> None:
        """Set up the front side with image using thumbnail manager."""
        # Try to load actual image
        if self.frame_data.image_path:
            try:
                img_path = Path(self.frame_data.image_path)
                if not img_path.is_absolute() and self.project_path:
                    img_path = self.project_path / img_path

                if img_path.exists():
                    # Use thumbnail manager for fast loading
                    img_w = self.size[0] - 4
                    img_h = self.size[1] - 4
                    thumb_mgr = get_thumbnail_manager()
                    ctk_img = thumb_mgr.get_ctk_image(img_path, (img_w, img_h), use_thumbnail=True)

                    if ctk_img:
                        self.image_label = ctk.CTkLabel(
                            self.front_frame,
                            image=ctk_img,
                            text=""
                        )
                        self.image_label.pack(expand=True, fill="both", padx=2, pady=2)
                        self.image_label.bind("<Button-1>", self._handle_click)
                        self._current_image = ctk_img  # Keep reference
                        return
            except Exception as e:
                logger.debug(f"Could not load image: {e}")

        # Placeholder
        self.placeholder_label = ctk.CTkLabel(
            self.front_frame,
            text="🎬",
            font=ctk.CTkFont(size=24),
            text_color=theme.colors.text_muted
        )
        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")

    def _setup_back_side(self) -> None:
        """Set up the back side with visual script and tags."""
        # Scrollable content for prompt
        scroll = ctk.CTkScrollableFrame(
            self.back_frame,
            fg_color="transparent"
        )
        scroll.pack(fill="both", expand=True, padx=2, pady=2)

        # Tags row (confirmed tags as small icons)
        if self.frame_data.tags:
            tags_frame = ctk.CTkFrame(scroll, fg_color="transparent", height=20)
            tags_frame.pack(fill="x", pady=(0, 2))

            for tag in self.frame_data.tags[:6]:  # Limit to 6 tags
                # Determine icon based on tag type (all 6 canonical prefixes)
                if tag.startswith("CHAR_"):
                    icon = "👤"
                    display = tag.replace("CHAR_", "")[:6]
                elif tag.startswith("LOC_"):
                    icon = "📍"
                    display = tag.replace("LOC_", "")[:6]
                elif tag.startswith("PROP_"):
                    icon = "🎭"
                    display = tag.replace("PROP_", "")[:6]
                elif tag.startswith("CONCEPT_"):
                    icon = "💡"
                    display = tag.replace("CONCEPT_", "")[:6]
                elif tag.startswith("EVENT_"):
                    icon = "📅"
                    display = tag.replace("EVENT_", "")[:6]
                elif tag.startswith("ENV_"):
                    icon = "🌤️"
                    display = tag.replace("ENV_", "")[:6]
                else:
                    icon = "🏷️"
                    display = tag[:6]

                # Try to show thumbnail if reference image exists
                tag_label = ctk.CTkLabel(
                    tags_frame,
                    text=f"{icon}",
                    font=ctk.CTkFont(size=10),
                    fg_color=theme.colors.bg_dark,
                    corner_radius=2,
                    width=18,
                    height=18
                )
                tag_label.pack(side="left", padx=1)

        # Camera notation
        if self.frame_data.camera:
            cam_label = ctk.CTkLabel(
                scroll,
                text=f"📷 {self.frame_data.camera[:40]}",
                font=ctk.CTkFont(size=8),
                text_color=theme.colors.neon_green,
                anchor="w"
            )
            cam_label.pack(fill="x")

        # Lighting
        if self.frame_data.lighting:
            light_label = ctk.CTkLabel(
                scroll,
                text=f"💡 {self.frame_data.lighting[:40]}",
                font=ctk.CTkFont(size=8),
                text_color=theme.colors.text_secondary,
                anchor="w"
            )
            light_label.pack(fill="x")

        # Prompt text (truncated)
        prompt_text = self.frame_data.prompt[:200] if self.frame_data.prompt else "No prompt"
        prompt_label = ctk.CTkLabel(
            scroll,
            text=prompt_text,
            font=ctk.CTkFont(size=8),
            text_color=theme.colors.text_primary,
            wraplength=self.size[0] - 10,
            justify="left",
            anchor="nw"
        )
        prompt_label.pack(fill="both", expand=True)

    def _flip_card(self) -> None:
        """Flip the card between front and back."""
        self.is_flipped = not self.is_flipped

        if self.is_flipped:
            # Show back, hide front
            self.front_frame.place_forget()
            self.back_frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)
            self.flip_btn.configure(text="🖼️")
        else:
            # Show front, hide back
            self.back_frame.place_forget()
            self.front_frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)
            self.flip_btn.configure(text="🔄")

    def _handle_click(self, event) -> None:
        """Handle click on frame."""
        if self.on_click:
            self.on_click(self.frame_data)

    def _on_selection_changed(self) -> None:
        """Handle selection checkbox change."""
        self.is_selected = self._selection_var.get()
        if self.is_selected:
            self.configure(fg_color=theme.colors.accent)
        else:
            self.configure(fg_color=theme.colors.bg_medium)

        # Notify parent if callback exists
        if hasattr(self, 'on_selection_change') and self.on_selection_change:
            self.on_selection_change(self.frame_data, self.is_selected)

    def set_selected(self, selected: bool) -> None:
        """Set selection state (programmatic)."""
        self.is_selected = selected
        self._selection_var.set(selected)
        if selected:
            self.configure(fg_color=theme.colors.accent)
        else:
            self.configure(fg_color=theme.colors.bg_medium)

    def get_selected(self) -> bool:
        """Get selection state."""
        return self._selection_var.get()

    def update_size(self, size: tuple, use_full_res: bool = False) -> None:
        """
        Update the card size and reload image at new size.

        Args:
            size: (width, height) tuple
            use_full_res: If True, load full resolution image (for 100% zoom)
        """
        if self.size == size:
            return  # No change needed

        self.size = size
        self.card_container.configure(width=size[0], height=size[1] + 30)
        self.front_frame.configure(width=size[0], height=size[1])
        self.back_frame.configure(width=size[0], height=size[1])

        # Reload image at new size (use thumbnail unless full res requested)
        self._reload_image(use_full_res=use_full_res)

        # Update front frame placement
        if not self.is_flipped:
            self.front_frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        else:
            self.back_frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)

    def _reload_image(self, use_full_res: bool = False) -> None:
        """
        Reload the image at current card size using thumbnail manager.

        Args:
            use_full_res: If True, load full resolution (for 100% zoom)
        """
        # Clear existing image/placeholder
        for widget in self.front_frame.winfo_children():
            widget.destroy()

        # Reload with new size using thumbnail manager
        if self.frame_data.image_path:
            try:
                img_path = Path(self.frame_data.image_path)
                if not img_path.is_absolute() and self.project_path:
                    img_path = self.project_path / img_path

                if img_path.exists():
                    # Calculate display size
                    img_w = self.size[0] - 4
                    img_h = self.size[1] - 4

                    # Use thumbnail manager for fast loading
                    thumb_mgr = get_thumbnail_manager()
                    ctk_img = thumb_mgr.get_ctk_image(
                        img_path,
                        (img_w, img_h),
                        use_thumbnail=not use_full_res
                    )

                    if ctk_img:
                        self.image_label = ctk.CTkLabel(
                            self.front_frame,
                            image=ctk_img,
                            text=""
                        )
                        self.image_label.pack(expand=True, fill="both", padx=2, pady=2)
                        self.image_label.bind("<Button-1>", self._handle_click)
                        # Keep reference to prevent garbage collection
                        self._current_image = ctk_img
                        return
            except Exception as e:
                logger.debug(f"Could not reload image: {e}")

        # Placeholder - scale emoji size with card
        emoji_size = max(12, min(48, self.size[0] // 4))
        self.placeholder_label = ctk.CTkLabel(
            self.front_frame,
            text="🎬",
            font=ctk.CTkFont(size=emoji_size),
            text_color=theme.colors.text_muted
        )
        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")


# Alias for backward compatibility
FrameCard = FlippingFrameCard


class StoryboardTable(ctk.CTkFrame):
    """
    Main storyboard table with zoom morphing layout.

    Zoom behavior:
    - 0-49%: Grid view (10 cols at 1%, 3 cols at 49%)
    - 50-100%: Row view (10 images at 50%, 1 image at 100%)

    Features:
    - Smooth zoom transitions
    - Navigator bar integration
    - Frame selection
    - Scroll synchronization
    """

    def __init__(
        self,
        master,
        on_frame_select: Callable[[StoryboardFrame], None] = None,
        on_regenerate_selected: Callable[[List[StoryboardFrame]], None] = None,
        project_path: Optional[Path] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_frame_select = on_frame_select
        self.on_regenerate_selected = on_regenerate_selected
        self.project_path = project_path
        self.frames: List[StoryboardFrame] = []
        self.frame_cards: List[FrameCard] = []
        self.selected_index: int = -1
        self._selected_frames: List[StoryboardFrame] = []  # Track multi-selection

        self.zoom_controller = ZoomController()

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the storyboard table UI."""
        self.configure(fg_color=theme.colors.bg_dark)

        # Zoom controls at TOP of panel
        self.zoom_frame = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium, height=45)
        self.zoom_frame.pack(fill="x", padx=5, pady=(5, 2))
        self.zoom_frame.pack_propagate(False)

        self.zoom_label = ctk.CTkLabel(
            self.zoom_frame,
            text="Zoom: 50%",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.zoom_label.pack(side="left", padx=10, pady=8)

        self.zoom_slider = ctk.CTkSlider(
            self.zoom_frame,
            from_=0,
            to=100,
            number_of_steps=100,
            command=self._on_zoom_change,
            width=200
        )
        self.zoom_slider.set(50)
        self.zoom_slider.pack(side="left", padx=10, pady=8)

        # Selection controls frame (in zoom bar)
        self.selection_frame = ctk.CTkFrame(self.zoom_frame, fg_color="transparent")
        self.selection_frame.pack(side="right", padx=10, pady=5)

        # Selection count label
        self.selection_label = ctk.CTkLabel(
            self.selection_frame,
            text="0 selected",
            font=ctk.CTkFont(size=12),
            text_color=theme.colors.text_secondary
        )
        self.selection_label.pack(side="left", padx=5)

        # Select All button - larger font, matching colors
        self.select_all_btn = ctk.CTkButton(
            self.selection_frame,
            text="Select All",
            width=90,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color=theme.colors.primary,
            hover_color=theme.colors.accent_hover,
            command=self._select_all_frames
        )
        self.select_all_btn.pack(side="left", padx=3)

        # Clear Selection button - larger font, matching colors
        self.clear_selection_btn = ctk.CTkButton(
            self.selection_frame,
            text="Clear",
            width=70,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color=theme.colors.primary,
            hover_color=theme.colors.accent_hover,
            command=self._clear_selection
        )
        self.clear_selection_btn.pack(side="left", padx=3)

        # Regenerate Selected button - larger font, accent color
        self.regenerate_btn = ctk.CTkButton(
            self.selection_frame,
            text="🔄 Regenerate Selected",
            width=160,
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.colors.accent,
            hover_color=theme.colors.accent_hover,
            command=self._on_regenerate_selected_click,
            state="disabled"
        )
        self.regenerate_btn.pack(side="left", padx=5)

        # Container for both view modes
        self.view_container = ctk.CTkFrame(self, fg_color=theme.colors.bg_dark)
        self.view_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Grid mode: vertical scrolling
        self.grid_scroll_frame = ctk.CTkScrollableFrame(
            self.view_container,
            fg_color=theme.colors.bg_dark,
            orientation="vertical"
        )

        # Grid container (for grid mode cards)
        self.grid_container = ctk.CTkFrame(
            self.grid_scroll_frame,
            fg_color="transparent"
        )

        # Row mode: horizontal scrolling frame
        self.row_scroll_frame = ctk.CTkScrollableFrame(
            self.view_container,
            fg_color=theme.colors.bg_dark,
            orientation="horizontal"
        )

        # Row container (for row mode cards)
        self.row_container = ctk.CTkFrame(
            self.row_scroll_frame,
            fg_color="transparent"
        )

        # Content frame reference for card creation (use grid_scroll_frame as default parent)
        self.content_frame = self.grid_scroll_frame

        # Navigator bar
        self.navigator = TimelineNavigator(
            self,
            on_navigate=self._on_navigate
        )
        self.navigator.pack(fill="x", side="bottom")

        # Initial layout
        self._update_layout()

    def set_frames(self, frames: List[StoryboardFrame]) -> None:
        """Set the frames to display."""
        self.frames = frames
        self.navigator.set_frames(frames)
        self._rebuild_cards()
        self._update_layout()

    def refresh_frame(self, frame_id: str) -> None:
        """Refresh a single frame by its ID (e.g., after image generation)."""
        # Find the frame and card by ID
        for i, frame in enumerate(self.frames):
            if frame.shot_id == frame_id:
                # Check for newly generated image
                if self.project_path:
                    generated_dir = self.project_path / "storyboard" / "generated"
                    if generated_dir.exists():
                        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                            img_file = generated_dir / f"{frame_id}{ext}"
                            if img_file.exists():
                                frame.image_path = str(img_file)
                                break

                # Refresh the corresponding card if it exists
                if i < len(self.frame_cards):
                    card = self.frame_cards[i]
                    card.frame_data = frame
                    card._setup_front_side()
                break

    def _rebuild_cards(self) -> None:
        """Rebuild all frame cards."""
        # Clear existing cards
        for card in self.frame_cards:
            card.destroy()
        self.frame_cards.clear()
        self._selected_frames.clear()
        self._update_selection_ui()

        # Create new cards - use view_container as parent for flexibility
        # Cards will be placed in grid_container or row_container via grid()
        for frame in self.frames:
            card = FrameCard(
                self.view_container,
                frame,
                on_click=self._on_frame_click,
                on_selection_change=self._on_card_selection_change,
                project_path=self.project_path
            )
            self.frame_cards.append(card)

    def _scroll_to_selected(self) -> None:
        """Scroll the row view to center on the selected frame."""
        if not self.frame_cards or self.selected_index < 0:
            return

        try:
            # Get the scroll frame's canvas
            # CTkScrollableFrame uses _parent_canvas internally
            if hasattr(self.row_scroll_frame, '_parent_canvas'):
                canvas = self.row_scroll_frame._parent_canvas

                # Calculate scroll position to center selected card
                total_cards = len(self.frame_cards)
                if total_cards > 0:
                    # Scroll to position (0.0 to 1.0)
                    scroll_pos = self.selected_index / max(1, total_cards - 1)
                    # Center it by adjusting for visible portion
                    visible_count = self.zoom_controller.get_row_visible_count()
                    if total_cards > visible_count:
                        scroll_pos = max(0, min(1, scroll_pos))
                        canvas.xview_moveto(scroll_pos)
        except Exception as e:
            logger.debug(f"Could not scroll to selected: {e}")

    def _on_zoom_change(self, value: float) -> None:
        """Handle zoom slider change."""
        self.zoom_controller.set_zoom(value)
        self.zoom_label.configure(text=f"Zoom: {int(value)}%")
        self._update_layout()

    def _update_layout(self) -> None:
        """Update layout based on current zoom level."""
        if self.zoom_controller.is_grid_mode():
            self._layout_grid()
        else:
            self._layout_row()

        # Update navigator view range
        self._update_navigator_range()

    def _layout_grid(self) -> None:
        """Layout frames in grid mode (vertical scrolling)."""
        # Hide row view frame, show grid scroll frame
        self.row_scroll_frame.pack_forget()
        if hasattr(self, 'row_view_frame'):
            self.row_view_frame.pack_forget()
        self.grid_scroll_frame.pack(fill="both", expand=True)
        self.grid_container.pack(fill="both", expand=True)

        columns = self.zoom_controller.get_grid_columns()

        # Calculate card size based on columns
        container_width = self.grid_scroll_frame.winfo_width() or 800
        card_width = max(80, (container_width - 20) // columns - 10)
        card_height = int(card_width * 9 / 16)  # 16:9 aspect ratio

        # Layout cards in grid - first clear any geometry
        for i, card in enumerate(self.frame_cards):
            try:
                card.grid_forget()
            except:
                pass
            try:
                card.pack_forget()
            except:
                pass

            row = i // columns
            col = i % columns

            card.update_size((card_width, card_height))
            card.grid(in_=self.grid_container, row=row, column=col, padx=3, pady=3, sticky="nw")

    def _layout_row(self) -> None:
        """Layout frames in row mode - VIRTUALIZED (only render visible frames), centered."""
        # Hide grid scroll frame, show row scroll frame
        self.grid_scroll_frame.pack_forget()
        self.row_scroll_frame.pack_forget()  # We'll use a simple frame instead

        # Use a centered container instead of scrollable frame for virtualized view
        if not hasattr(self, 'row_view_frame'):
            self.row_view_frame = ctk.CTkFrame(self.view_container, fg_color="transparent")
        self.row_view_frame.pack(fill="both", expand=True)

        visible_count = self.zoom_controller.get_row_visible_count()

        # Get container dimensions
        container_width = self.view_container.winfo_width() or 800
        container_height = self.view_container.winfo_height() or 450

        # Clear all cards from any geometry manager first
        for card in self.frame_cards:
            try:
                card.grid_forget()
            except:
                pass
            try:
                card.pack_forget()
            except:
                pass
            try:
                card.place_forget()
            except:
                pass

        # Calculate card size based on visible count
        if visible_count == 1:
            # 100% zoom: Single fitted centered frame
            max_width = container_width - 60
            max_height = container_height - 100  # Leave room for controls

            # Fit to container maintaining 16:9 aspect ratio
            if max_width * 9 / 16 <= max_height:
                card_width = max_width
                card_height = int(max_width * 9 / 16)
            else:
                card_height = max_height
                card_width = int(max_height * 16 / 9)
        else:
            # Multiple images visible - each takes viewport_width / visible_count
            card_width = max(120, (container_width - 40) // visible_count - 10)
            card_height = int(card_width * 9 / 16)

        # Calculate which frames to render (only visible ones + 1 buffer on each side)
        center_index = max(0, min(len(self.frames) - 1, self.selected_index))
        if center_index < 0:
            center_index = 0

        half_visible = visible_count // 2
        start_index = max(0, center_index - half_visible - 1)  # -1 for buffer
        end_index = min(len(self.frames), center_index + half_visible + 2)  # +2 for buffer

        # Adjust if near edges
        if end_index - start_index < visible_count:
            if start_index == 0:
                end_index = min(len(self.frames), visible_count + 1)
            else:
                start_index = max(0, len(self.frames) - visible_count - 1)

        # Calculate total width needed for visible cards
        visible_cards_count = end_index - start_index
        total_cards_width = visible_cards_count * (card_width + 10)  # +10 for padding

        # Calculate starting X to center the cards
        start_x = max(0, (container_width - total_cards_width) // 2)

        # Determine if we should use full resolution (100% zoom = 1 visible)
        use_full_res = (visible_count == 1)

        # Layout ONLY visible cards using place() for precise positioning
        for idx, i in enumerate(range(start_index, end_index)):
            if i >= len(self.frame_cards):
                break

            card = self.frame_cards[i]
            card.update_size((card_width, card_height), use_full_res=use_full_res)

            # Calculate x position (centered)
            x_pos = start_x + idx * (card_width + 10)
            # Calculate y position (vertically centered)
            y_pos = max(10, (container_height - card_height - 60) // 2)

            card.place(in_=self.row_view_frame, x=x_pos, y=y_pos)

    def _on_frame_click(self, frame: StoryboardFrame) -> None:
        """Handle frame card click."""
        # Find index
        for i, f in enumerate(self.frames):
            if f.shot_id == frame.shot_id:
                self._select_frame(i)
                break

        if self.on_frame_select:
            self.on_frame_select(frame)

    def _select_frame(self, index: int) -> None:
        """Select a frame by index."""
        # Deselect previous
        if 0 <= self.selected_index < len(self.frame_cards):
            self.frame_cards[self.selected_index].set_selected(False)

        # Select new
        self.selected_index = index
        if 0 <= index < len(self.frame_cards):
            self.frame_cards[index].set_selected(True)

        # Update navigator
        self.navigator.set_current_index(index)

        # Re-layout if in row mode
        if self.zoom_controller.is_row_mode():
            self._layout_row()

    def _on_navigate(self, index: int) -> None:
        """Handle navigation from navigator bar."""
        self._select_frame(index)

        # Scroll to frame in grid mode
        if self.zoom_controller.is_grid_mode() and 0 <= index < len(self.frame_cards):
            # Scroll the content frame to show the selected card
            pass  # CTkScrollableFrame handles this automatically

    def _update_navigator_range(self) -> None:
        """Update the navigator's view range indicator."""
        if not self.frames:
            return

        if self.zoom_controller.is_grid_mode():
            # In grid mode, show all visible frames
            columns = self.zoom_controller.get_grid_columns()
            visible_rows = 4  # Approximate
            visible_count = columns * visible_rows

            start = max(0, self.selected_index - visible_count // 2)
            end = min(len(self.frames), start + visible_count)
        else:
            # In row mode, show visible range
            visible_count = self.zoom_controller.get_row_visible_count()
            center = max(0, self.selected_index)
            start = max(0, center - visible_count // 2)
            end = min(len(self.frames), start + visible_count)

        self.navigator.set_view_range(start, end)

    def get_zoom_level(self) -> float:
        """Get current zoom level."""
        return self.zoom_controller.get_zoom()

    def set_zoom_level(self, level: float) -> None:
        """Set zoom level programmatically."""
        self.zoom_slider.set(level)
        self._on_zoom_change(level)

    def navigate_to_frame(self, shot_id: str) -> None:
        """Navigate to a specific frame by shot ID."""
        for i, frame in enumerate(self.frames):
            if frame.shot_id == shot_id:
                self._select_frame(i)
                break

    def get_selected_frame(self) -> Optional[StoryboardFrame]:
        """Get the currently selected frame."""
        if 0 <= self.selected_index < len(self.frames):
            return self.frames[self.selected_index]
        return None

    # =========================================================================
    # MULTI-SELECTION MANAGEMENT
    # =========================================================================

    def _on_card_selection_change(self, frame: StoryboardFrame, selected: bool) -> None:
        """Handle selection change from a frame card."""
        if selected:
            if frame not in self._selected_frames:
                self._selected_frames.append(frame)
        else:
            if frame in self._selected_frames:
                self._selected_frames.remove(frame)

        self._update_selection_ui()

    def _update_selection_ui(self) -> None:
        """Update selection-related UI elements."""
        count = len(self._selected_frames)
        self.selection_label.configure(text=f"{count} selected")

        # Enable/disable regenerate button
        if count > 0:
            self.regenerate_btn.configure(state="normal")
        else:
            self.regenerate_btn.configure(state="disabled")

    def _select_all_frames(self) -> None:
        """Select all frames."""
        self._selected_frames.clear()
        for card in self.frame_cards:
            card.set_selected(True)
            self._selected_frames.append(card.frame_data)
        self._update_selection_ui()

    def _clear_selection(self) -> None:
        """Clear all selections."""
        for card in self.frame_cards:
            card.set_selected(False)
        self._selected_frames.clear()
        self._update_selection_ui()

    def _on_regenerate_selected_click(self) -> None:
        """Handle regenerate selected button click - opens regeneration modal."""
        if not self._selected_frames:
            return

        # Import and open regeneration modal
        from greenlight.ui.dialogs.regeneration_modal import RegenerationModal

        def on_generate(frames, prompt, model_key):
            """Callback when user clicks generate in modal."""
            if self.on_regenerate_selected:
                # Pass the full regeneration info
                self.on_regenerate_selected(frames, prompt, model_key)

        # Open modal
        modal = RegenerationModal(
            self.winfo_toplevel(),
            selected_frames=self._selected_frames.copy(),
            project_path=self.project_path,
            on_generate=on_generate
        )
        modal.focus()

    def get_selected_frames(self) -> List[StoryboardFrame]:
        """Get list of all selected frames."""
        return self._selected_frames.copy()

    def select_frames_by_id(self, frame_ids: List[str], clear_existing: bool = True) -> None:
        """Select frames by their shot IDs (for OmniMind backdoor)."""
        if clear_existing:
            self._clear_selection()

        for card in self.frame_cards:
            if card.frame_data.shot_id in frame_ids:
                card.set_selected(True)
                if card.frame_data not in self._selected_frames:
                    self._selected_frames.append(card.frame_data)

        self._update_selection_ui()

