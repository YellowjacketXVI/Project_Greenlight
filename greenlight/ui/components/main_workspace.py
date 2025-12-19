"""
Greenlight Main Workspace

Central workspace for content editing and viewing.
"""

import customtkinter as ctk
from typing import Dict, List, Optional, Callable, Any, TYPE_CHECKING
from enum import Enum

from greenlight.ui.theme import theme
from greenlight.ui.components.tooltip import Tooltip, TAB_TOOLTIPS
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.main_workspace")

if TYPE_CHECKING:
    from greenlight.context.context_engine import ContextEngine

# Use Agnostic_Core_OS for cross-platform operations
try:
    from Agnostic_Core_OS import get_process_runner
    _process_runner = get_process_runner()
except ImportError:
    _process_runner = None


class WorkspaceMode(Enum):
    """Workspace display modes."""
    EDITOR = "editor"
    WRITER = "writer"  # Story writing mode
    STORYBOARD = "storyboard"
    GALLERY = "gallery"
    REFERENCES = "references"  # Reference images by tag
    SPLIT = "split"
    WORLD_BIBLE = "world_bible"  # World Bible management page
    SCRIPT = "script"  # Script viewer with scene panels


class MainWorkspace(ctk.CTkFrame):
    """
    Main workspace panel.

    Features:
    - Multiple view modes
    - Content editing
    - Storyboard display
    - Image gallery
    """

    def __init__(
        self,
        master,
        on_content_change: Callable[[str], None] = None,
        context_engine: Optional["ContextEngine"] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_content_change = on_content_change
        self._mode = WorkspaceMode.EDITOR
        self._current_content: Dict[str, Any] = {}
        self._context_engine = context_engine

        self._setup_ui()

    def set_context_engine(self, context_engine: "ContextEngine") -> None:
        """Set the context engine for world context injection."""
        self._context_engine = context_engine
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.configure(
            fg_color=theme.colors.bg_medium,
            corner_radius=0
        )
        
        # Toolbar (minimal - modes controlled via navigator)
        toolbar = ctk.CTkFrame(self, fg_color=theme.colors.bg_dark, height=40)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        # Content area - expanded to use full space
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=theme.spacing.sm, pady=theme.spacing.sm)
        
        # Initialize with editor view
        self._show_editor()
    
    def _safe_destroy_widgets(self, parent) -> None:
        """
        Safely destroy all child widgets, handling pending callbacks.

        This prevents TclError when widgets have pending after() callbacks
        or Configure events that fire after the widget is destroyed.

        The key is to:
        1. Cancel all pending after() callbacks
        2. Process pending events
        3. Unbind all events
        4. Destroy from leaves to root
        """
        try:
            # Process any pending events before destroying widgets
            # This helps prevent TclError from pending Configure events
            try:
                parent.update_idletasks()
            except Exception:
                pass

            # Get list of children first (avoid modifying during iteration)
            children = list(parent.winfo_children())

            for widget in children:
                try:
                    # Check if widget still exists
                    if not widget.winfo_exists():
                        continue

                    # Recursively destroy children first (leaves before parents)
                    self._safe_destroy_widgets(widget)

                    # Cancel any pending after() callbacks on this widget
                    try:
                        # Get all after callbacks and cancel them
                        # This is the key to preventing race conditions
                        for after_id in widget.tk.call('after', 'info'):
                            try:
                                widget.after_cancel(after_id)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # Unbind all events to prevent callbacks
                    try:
                        widget.unbind_all('<Configure>')
                        widget.unbind('<Configure>')
                    except Exception:
                        pass

                    # For CTk widgets, try to cancel internal callbacks
                    if hasattr(widget, '_draw'):
                        try:
                            # Prevent any pending draw operations
                            widget.configure(width=0, height=0)
                        except Exception:
                            pass

                    # Check again before destroying
                    if widget.winfo_exists():
                        widget.destroy()
                except Exception as e:
                    # Widget may already be destroyed, ignore
                    logger.debug(f"Widget destruction warning: {e}")

            # Final update to clear any remaining events
            try:
                parent.update_idletasks()
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Safe destroy warning: {e}")

    def set_mode(self, mode: WorkspaceMode) -> None:
        """Set the workspace mode."""
        self._mode = mode

        # Clear content frame safely
        self._safe_destroy_widgets(self.content_frame)

        # Allow pending events to clear before creating new widgets
        # This prevents race conditions with CTk widget draw callbacks
        try:
            self.content_frame.update()
        except Exception:
            pass

        if mode == WorkspaceMode.EDITOR:
            self._show_editor()
        elif mode == WorkspaceMode.STORYBOARD:
            self._show_storyboard()
        elif mode == WorkspaceMode.GALLERY:
            self._show_gallery()
        elif mode == WorkspaceMode.REFERENCES:
            self._show_references()
        elif mode == WorkspaceMode.SPLIT:
            self._show_split()
        elif mode == WorkspaceMode.WORLD_BIBLE:
            self._show_world_bible()
        elif mode == WorkspaceMode.SCRIPT:
            self._show_script()
    
    def _show_editor(self) -> None:
        """Show the text editor view."""
        self.editor = ctk.CTkTextbox(
            self.content_frame,
            fg_color=theme.colors.bg_dark,
            text_color=theme.colors.text_primary,
            font=(theme.fonts.family, theme.fonts.size_normal)
        )
        self.editor.pack(fill="both", expand=True)
        
        # Bind change event
        self.editor.bind("<KeyRelease>", self._on_text_change)
    
    def _show_storyboard(self) -> None:
        """Show the storyboard view with zoom morphing table."""
        from greenlight.ui.components.storyboard_table import StoryboardTable, StoryboardFrame
        from pathlib import Path

        # Try to load storyboard prompts from project
        storyboard_data = self._load_storyboard_data()

        # Get project path for image loading
        project_path = self._current_content.get('project_path')
        if project_path:
            project_path = Path(project_path)

        if storyboard_data:
            # Use new StoryboardTable with zoom morphing
            self.storyboard_table = StoryboardTable(
                self.content_frame,
                on_frame_select=self._on_storyboard_frame_select,
                project_path=project_path
            )
            self.storyboard_table.pack(fill="both", expand=True)

            # Convert data to StoryboardFrame objects
            frames = []
            for prompt_data in storyboard_data:
                shot_id = prompt_data.get('shot_id', f"{prompt_data.get('scene_number', 1)}.{prompt_data.get('frame_number', 1)}")
                frame = StoryboardFrame(
                    shot_id=shot_id,
                    scene_number=prompt_data.get('scene_number', 1),
                    frame_number=prompt_data.get('frame_number', 1),
                    prompt=prompt_data.get('prompt', ''),
                    image_path=prompt_data.get('image_path'),
                    camera=prompt_data.get('camera', ''),
                    lighting=prompt_data.get('lighting', ''),
                    tags=prompt_data.get('reference_tags', [])
                )
                frames.append(frame)

            self.storyboard_table.set_frames(frames)
        else:
            # Show empty state with instructions
            empty_frame = ctk.CTkFrame(self.content_frame, fg_color=theme.colors.bg_light, corner_radius=8)
            empty_frame.pack(fill="x", pady=theme.spacing.md, padx=theme.spacing.md)

            ctk.CTkLabel(
                empty_frame,
                text="📽️ No Storyboard Data",
                font=(theme.fonts.family, 16, "bold"),
                text_color=theme.colors.text_primary
            ).pack(pady=(theme.spacing.lg, theme.spacing.sm))

            ctk.CTkLabel(
                empty_frame,
                text="Run the Writer and Director pipelines to generate storyboard frames.",
                text_color=theme.colors.text_secondary
            ).pack(pady=(0, theme.spacing.lg))

    def _on_storyboard_frame_select(self, frame) -> None:
        """Handle storyboard frame selection."""
        # Store selected frame info
        self._current_content['selected_frame'] = {
            'shot_id': frame.shot_id,
            'prompt': frame.prompt,
            'camera': frame.camera,
            'tags': frame.tags
        }
        # Could trigger a detail panel or callback here

    def refresh_storyboard(self) -> None:
        """Refresh the storyboard view to show newly generated images."""
        if hasattr(self, 'storyboard_table') and self.storyboard_table:
            # Reload storyboard data and update frames
            storyboard_data = self._load_storyboard_data()
            if storyboard_data:
                from greenlight.ui.components.storyboard_table import StoryboardFrame
                frames = []
                for prompt_data in storyboard_data:
                    shot_id = prompt_data.get('shot_id', f"{prompt_data.get('scene_number', 1)}.{prompt_data.get('frame_number', 1)}")
                    frame = StoryboardFrame(
                        shot_id=shot_id,
                        scene_number=prompt_data.get('scene_number', 1),
                        frame_number=prompt_data.get('frame_number', 1),
                        prompt=prompt_data.get('prompt', ''),
                        image_path=prompt_data.get('image_path'),
                        camera=prompt_data.get('camera', ''),
                        lighting=prompt_data.get('lighting', ''),
                        tags=prompt_data.get('reference_tags', [])
                    )
                    frames.append(frame)
                self.storyboard_table.set_frames(frames)

    def _load_storyboard_data(self) -> List[Dict]:
        """Load storyboard data from the visual script."""
        import json
        from pathlib import Path

        # Get project path from current content
        project_path = self._current_content.get('project_path')
        if not project_path:
            return []

        visual_script_file = Path(project_path) / "storyboard" / "visual_script.json"
        if not visual_script_file.exists():
            return []

        try:
            with open(visual_script_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Flatten frames from scenes into a list
            frames = []
            generated_dir = Path(project_path) / "storyboard" / "generated"

            for scene in data.get('scenes', []):
                for frame in scene.get('frames', []):
                    frame_id = frame.get('frame_id', '')
                    # Check for generated image
                    image_path = None
                    if generated_dir.exists():
                        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                            img_file = generated_dir / f"{frame_id}{ext}"
                            if img_file.exists():
                                image_path = str(img_file)
                                break

                    frames.append({
                        'shot_id': frame_id,
                        'scene_number': frame.get('scene_number', 1),
                        'frame_number': frame.get('frame_number', 1),
                        'prompt': frame.get('prompt', ''),
                        'image_path': image_path,
                        'camera': frame.get('camera_notation', ''),
                        'lighting': frame.get('lighting_notation', ''),
                        'reference_tags': []  # Could extract from prompt if needed
                    })

            return frames
        except Exception:
            return []

    def _create_storyboard_frame(self, parent, index: int, prompt_data: Dict) -> None:
        """Create a single storyboard frame display."""
        frame = ctk.CTkFrame(
            parent,
            fg_color=theme.colors.bg_light,
            corner_radius=8
        )
        frame.pack(fill="x", pady=theme.spacing.sm, padx=theme.spacing.sm)

        # Header with notation
        header = ctk.CTkFrame(frame, fg_color=theme.colors.bg_medium, corner_radius=4)
        header.pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.sm)

        notation = prompt_data.get('notation', f'1.{index+1}.cA')
        ctk.CTkLabel(
            header,
            text=f"🎬 {notation}",
            font=(theme.fonts.family, 12, "bold"),
            text_color=theme.colors.primary
        ).pack(side="left", padx=theme.spacing.sm, pady=theme.spacing.xs)

        # Camera info
        shot_type = prompt_data.get('shot_type', 'MS')
        angle = prompt_data.get('angle', 'EYE')
        movement = prompt_data.get('movement', 'STATIC')
        ctk.CTkLabel(
            header,
            text=f"📷 {shot_type} | {angle} | {movement}",
            text_color=theme.colors.text_secondary
        ).pack(side="right", padx=theme.spacing.sm)

        # Content area
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.sm)

        # Image placeholder (left)
        img_frame = ctk.CTkFrame(content, fg_color=theme.colors.bg_dark, width=200, height=120, corner_radius=4)
        img_frame.pack(side="left", padx=(0, theme.spacing.sm))
        img_frame.pack_propagate(False)

        # Check for generated image
        img_path = prompt_data.get('image_path')
        if img_path:
            ctk.CTkLabel(img_frame, text="🖼️", font=(theme.fonts.family, 24)).pack(expand=True)
        else:
            ctk.CTkLabel(img_frame, text="⏳ Pending", text_color=theme.colors.text_secondary).pack(expand=True)

        # Prompt text (right)
        prompt_text = prompt_data.get('full_prompt', prompt_data.get('description', 'No prompt available'))
        text_frame = ctk.CTkFrame(content, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True)

        # Truncate long prompts
        display_text = prompt_text[:200] + "..." if len(prompt_text) > 200 else prompt_text
        ctk.CTkLabel(
            text_frame,
            text=display_text,
            wraplength=400,
            justify="left",
            text_color=theme.colors.text_primary
        ).pack(anchor="w")
    
    def _show_gallery(self) -> None:
        """Show the image gallery view with actual project images."""
        from pathlib import Path

        scroll = ctk.CTkScrollableFrame(
            self.content_frame,
            fg_color="transparent"
        )
        scroll.pack(fill="both", expand=True)

        # Try to load images from project
        images = self._load_gallery_images()

        if images:
            # Grid of actual images
            grid = ctk.CTkFrame(scroll, fg_color="transparent")
            grid.pack(fill="both", expand=True)

            for i, img_info in enumerate(images):
                row, col = divmod(i, 4)

                img_frame = ctk.CTkFrame(
                    grid,
                    fg_color=theme.colors.bg_light,
                    corner_radius=8
                )
                img_frame.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

                # Image name
                name_label = ctk.CTkLabel(
                    img_frame,
                    text=img_info['name'][:20] + "..." if len(img_info['name']) > 20 else img_info['name'],
                    text_color=theme.colors.text_secondary,
                    font=(theme.fonts.family, 10)
                )
                name_label.pack(pady=(theme.spacing.sm, 0))

                # Image placeholder with icon
                img_placeholder = ctk.CTkFrame(
                    img_frame,
                    fg_color=theme.colors.bg_dark,
                    width=150,
                    height=100,
                    corner_radius=4
                )
                img_placeholder.pack(padx=theme.spacing.sm, pady=theme.spacing.sm)
                img_placeholder.pack_propagate(False)

                ctk.CTkLabel(
                    img_placeholder,
                    text="🖼️",
                    font=(theme.fonts.family, 24)
                ).pack(expand=True)

                # Make clickable
                img_placeholder.bind("<Button-1>", lambda e, p=img_info['path']: self._open_image(p))

            # Configure grid columns
            for col in range(4):
                grid.grid_columnconfigure(col, weight=1)
        else:
            # Show empty state
            empty_frame = ctk.CTkFrame(scroll, fg_color=theme.colors.bg_light, corner_radius=8)
            empty_frame.pack(fill="x", pady=theme.spacing.md, padx=theme.spacing.md)

            ctk.CTkLabel(
                empty_frame,
                text="🖼️ No Images Found",
                font=(theme.fonts.family, 16, "bold"),
                text_color=theme.colors.text_primary
            ).pack(pady=(theme.spacing.lg, theme.spacing.sm))

            ctk.CTkLabel(
                empty_frame,
                text="Generate storyboard images or add images to your project's assets folder.",
                text_color=theme.colors.text_secondary
            ).pack(pady=(0, theme.spacing.lg))

    def _load_gallery_images(self) -> List[Dict]:
        """Load images from the current project."""
        from pathlib import Path

        images = []
        project_path = self._current_content.get('project_path')

        if not project_path:
            return images

        project_path = Path(project_path)

        # Search for images in common locations
        image_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
        search_paths = [
            project_path / "storyboards" / "generated",
            project_path / "storyboards",
            project_path / "assets",
            project_path / "references",
        ]

        for search_path in search_paths:
            if search_path.exists():
                for img_file in search_path.rglob("*"):
                    if img_file.suffix.lower() in image_extensions:
                        images.append({
                            'name': img_file.name,
                            'path': str(img_file),
                            'folder': img_file.parent.name
                        })

        return images[:24]  # Limit to 24 images

    def _open_image(self, path: str) -> None:
        """Open an image file."""
        if _process_runner:
            result = _process_runner.open_file(path)
            if not result.success:
                print(f"Error opening image: {result.stderr}")
        else:
            # Fallback if Agnostic_Core_OS not available
            import subprocess
            import sys
            try:
                if sys.platform == 'win32':
                    subprocess.run(['start', '', path], shell=True)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', path])
                else:
                    subprocess.run(['xdg-open', path])
            except Exception as e:
                print(f"Error opening image: {e}")

    def _show_references(self) -> None:
        """Show the references view organized by tag category."""
        from pathlib import Path

        scroll = ctk.CTkScrollableFrame(
            self.content_frame,
            fg_color="transparent"
        )
        scroll.pack(fill="both", expand=True)

        project_path = self._current_content.get('project_path')
        if not project_path:
            self._show_references_empty(scroll, "No project loaded")
            return

        project_path = Path(project_path)
        refs_path = project_path / "references"

        if not refs_path.exists():
            self._show_references_empty(scroll, "No references folder found")
            return

        # Load references by category
        categories = [
            ("👤 Characters", refs_path / "characters"),
            ("🏠 Locations", refs_path / "locations"),
            ("🔧 Props", refs_path / "props"),
        ]

        has_any = False
        for cat_name, cat_path in categories:
            if cat_path.exists():
                refs = self._load_category_references(cat_path)
                if refs:
                    has_any = True
                    self._create_reference_category(scroll, cat_name, refs)

        if not has_any:
            self._show_references_empty(scroll, "No reference images found.\nAdd images to references/characters, references/locations, or references/props folders.")

    def _show_references_empty(self, parent, message: str) -> None:
        """Show empty state for references."""
        empty_frame = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8)
        empty_frame.pack(fill="x", pady=theme.spacing.md, padx=theme.spacing.md)

        ctk.CTkLabel(
            empty_frame,
            text="🏷️ References",
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.text_primary
        ).pack(pady=(theme.spacing.lg, theme.spacing.sm))

        ctk.CTkLabel(
            empty_frame,
            text=message,
            text_color=theme.colors.text_secondary,
            justify="center"
        ).pack(pady=(0, theme.spacing.lg))

    def _load_category_references(self, category_path: Path) -> Dict[str, Dict]:
        """Load references from a category folder, organized by tag.

        Returns dict with structure:
        {
            "TAG_NAME": {
                "images": [Path, ...],  # Direct images in tag folder
                "subdirs": {
                    "subdir_name": [Path, ...],  # Images in subdirectory
                    ...
                }
            }
        }
        """
        from pathlib import Path

        refs = {}
        image_extensions = {'.png', '.jpg', '.jpeg', '.webp'}

        for tag_folder in category_path.iterdir():
            if tag_folder.is_dir():
                tag_data = {"images": [], "subdirs": {}}

                for item in tag_folder.iterdir():
                    if item.is_file() and item.suffix.lower() in image_extensions:
                        # Direct image in tag folder
                        tag_data["images"].append(item)
                    elif item.is_dir():
                        # Subdirectory (e.g., cardinal directions)
                        subdir_images = []
                        for img_file in item.iterdir():
                            if img_file.is_file() and img_file.suffix.lower() in image_extensions:
                                subdir_images.append(img_file)
                        if subdir_images:
                            tag_data["subdirs"][item.name] = subdir_images

                # Only add if has any content
                if tag_data["images"] or tag_data["subdirs"]:
                    refs[tag_folder.name.upper()] = tag_data

        return refs

    def _create_reference_category(self, parent, category_name: str, refs: Dict[str, Dict]) -> None:
        """Create a category section with reference images."""
        # Category header
        header = ctk.CTkFrame(parent, fg_color=theme.colors.bg_dark, corner_radius=4)
        header.pack(fill="x", pady=(theme.spacing.md, theme.spacing.sm), padx=theme.spacing.sm)

        ctk.CTkLabel(
            header,
            text=category_name,
            font=(theme.fonts.family, 14, "bold"),
            text_color=theme.colors.primary
        ).pack(side="left", padx=theme.spacing.md, pady=theme.spacing.sm)

        ctk.CTkLabel(
            header,
            text=f"{len(refs)} tags",
            text_color=theme.colors.text_secondary
        ).pack(side="right", padx=theme.spacing.md)

        # Tags grid
        for tag_name, tag_data in refs.items():
            self._create_tag_reference_row(parent, tag_name, tag_data)

    def _create_tag_reference_row(self, parent, tag_name: str, tag_data: Dict) -> None:
        """Create a row for a single tag's references with expandable subdirectories."""
        images = tag_data.get("images", [])
        subdirs = tag_data.get("subdirs", {})
        has_subdirs = len(subdirs) > 0
        total_images = len(images) + sum(len(imgs) for imgs in subdirs.values())

        # Main container for tag (allows expansion)
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", pady=2, padx=theme.spacing.sm)

        # Main row
        row = ctk.CTkFrame(container, fg_color=theme.colors.bg_light, corner_radius=4)
        row.pack(fill="x")

        # Expand button if has subdirs
        if has_subdirs:
            expand_btn = ctk.CTkButton(
                row,
                text="▶",
                width=20,
                height=20,
                fg_color="transparent",
                hover_color=theme.colors.bg_hover,
                text_color=theme.colors.text_secondary,
                font=(theme.fonts.family, 10)
            )
            expand_btn.pack(side="left", padx=(theme.spacing.xs, 0))

            # Subdirs container (hidden by default)
            subdirs_container = ctk.CTkFrame(container, fg_color="transparent")
            subdirs_container._visible = False

            def toggle_subdirs(btn=expand_btn, cont=subdirs_container):
                if cont._visible:
                    cont.pack_forget()
                    cont._visible = False
                    btn.configure(text="▶")
                else:
                    cont.pack(fill="x", padx=(theme.spacing.lg, 0))
                    cont._visible = True
                    btn.configure(text="▼")
                    # Render subdirs if not already done
                    if not cont.winfo_children():
                        self._render_subdirs(cont, subdirs)

            expand_btn.configure(command=toggle_subdirs)

        # Tag name
        ctk.CTkLabel(
            row,
            text=f"[{tag_name}]",
            font=(theme.fonts.family, 11, "bold"),
            text_color=theme.colors.accent,
            width=150,
            anchor="w"
        ).pack(side="left", padx=theme.spacing.sm, pady=theme.spacing.xs)

        # Image count with subdir indicator
        count_text = f"{total_images} image(s)"
        if has_subdirs:
            count_text += f" • {len(subdirs)} 📁"
        ctk.CTkLabel(
            row,
            text=count_text,
            text_color=theme.colors.text_secondary
        ).pack(side="left", padx=theme.spacing.sm)

        # Image thumbnails (show first 3 from direct images)
        if images:
            thumb_frame = ctk.CTkFrame(row, fg_color="transparent")
            thumb_frame.pack(side="left", padx=theme.spacing.sm)

            for i, img_path in enumerate(images[:3]):
                thumb = ctk.CTkFrame(
                    thumb_frame,
                    fg_color=theme.colors.bg_dark,
                    width=40,
                    height=40,
                    corner_radius=4
                )
                thumb.pack(side="left", padx=2)
                thumb.pack_propagate(False)

                ctk.CTkLabel(thumb, text="🖼️", font=(theme.fonts.family, 12)).pack(expand=True)
                thumb.bind("<Button-1>", lambda e, p=str(img_path): self._open_image(p))

            if len(images) > 3:
                ctk.CTkLabel(
                    thumb_frame,
                    text=f"+{len(images) - 3}",
                    text_color=theme.colors.text_secondary
                ).pack(side="left", padx=theme.spacing.xs)

        # Open folder button
        folder_path = images[0].parent if images else (list(subdirs.values())[0][0].parent.parent if subdirs else None)
        if folder_path:
            open_btn = ctk.CTkButton(
                row,
                text="📂",
                width=30,
                command=lambda p=folder_path: self._open_folder(p),
                **theme.get_button_style("secondary")
            )
            open_btn.pack(side="right", padx=theme.spacing.sm, pady=theme.spacing.xs)

    def _render_subdirs(self, parent, subdirs: Dict[str, list]) -> None:
        """Render subdirectory rows (e.g., cardinal direction views)."""
        for subdir_name, images in subdirs.items():
            subrow = ctk.CTkFrame(parent, fg_color=theme.colors.bg_medium, corner_radius=4)
            subrow.pack(fill="x", pady=1, padx=theme.spacing.sm)

            # Check if this is a cardinal direction folder
            is_cardinal = any(d in subdir_name.lower() for d in ['_dir_', 'north', 'south', 'east', 'west'])
            icon = "🧭" if is_cardinal else "📁"

            # Subdir name
            ctk.CTkLabel(
                subrow,
                text=f"  {icon} {subdir_name}",
                font=(theme.fonts.family, 10),
                text_color=theme.colors.text_secondary,
                width=180,
                anchor="w"
            ).pack(side="left", padx=theme.spacing.sm, pady=theme.spacing.xs)

            # Image count
            ctk.CTkLabel(
                subrow,
                text=f"{len(images)} image(s)",
                text_color=theme.colors.text_muted,
                font=(theme.fonts.family, 10)
            ).pack(side="left", padx=theme.spacing.sm)

            # Thumbnails for subdir
            thumb_frame = ctk.CTkFrame(subrow, fg_color="transparent")
            thumb_frame.pack(side="left", padx=theme.spacing.sm)

            for img_path in images[:4]:
                thumb = ctk.CTkFrame(
                    thumb_frame,
                    fg_color=theme.colors.bg_dark,
                    width=32,
                    height=32,
                    corner_radius=3
                )
                thumb.pack(side="left", padx=1)
                thumb.pack_propagate(False)

                # Show direction indicator if cardinal
                label_text = "🖼️"
                if is_cardinal:
                    fname = img_path.stem.lower()
                    if '_dir_n' in fname or 'north' in fname:
                        label_text = "⬆️"
                    elif '_dir_s' in fname or 'south' in fname:
                        label_text = "⬇️"
                    elif '_dir_e' in fname or 'east' in fname:
                        label_text = "➡️"
                    elif '_dir_w' in fname or 'west' in fname:
                        label_text = "⬅️"

                ctk.CTkLabel(thumb, text=label_text, font=(theme.fonts.family, 10)).pack(expand=True)
                thumb.bind("<Button-1>", lambda e, p=str(img_path): self._open_image(p))

            # Open subdir button
            open_btn = ctk.CTkButton(
                subrow,
                text="📂",
                width=25,
                height=20,
                command=lambda p=images[0].parent: self._open_folder(p),
                **theme.get_button_style("secondary")
            )
            open_btn.pack(side="right", padx=theme.spacing.sm, pady=2)

    def _open_folder(self, path) -> None:
        """Open a folder in the file explorer."""
        if _process_runner:
            result = _process_runner.open_folder(path)
            if not result.success:
                print(f"Error opening folder: {result.stderr}")
        else:
            # Fallback if Agnostic_Core_OS not available
            import subprocess
            import sys
            try:
                if sys.platform == 'win32':
                    subprocess.run(['explorer', str(path)])
                elif sys.platform == 'darwin':
                    subprocess.run(['open', str(path)])
                else:
                    subprocess.run(['xdg-open', str(path)])
            except Exception as e:
                print(f"Error opening folder: {e}")

    def _show_split(self) -> None:
        """Show split view (editor + preview)."""
        # Left: Editor
        left = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)
        
        self.editor = ctk.CTkTextbox(
            left,
            fg_color=theme.colors.bg_dark,
            text_color=theme.colors.text_primary
        )
        self.editor.pack(fill="both", expand=True, padx=(0, theme.spacing.sm))
        
        # Right: Preview
        right = ctk.CTkFrame(
            self.content_frame,
            fg_color=theme.colors.bg_light
        )
        right.pack(side="right", fill="both", expand=True)
        
        preview_label = ctk.CTkLabel(right, text="Preview", **theme.get_label_style())
        preview_label.pack(pady=theme.spacing.lg)

    def _show_script(self) -> None:
        """Show the Script panel with tabbed interface like World Bible."""
        from pathlib import Path
        import json

        # Get project path
        project_path = self._current_content.get('project_path')
        if not project_path:
            self._show_script_empty("No project loaded. Select a project to view its script.")
            return

        project_path = Path(project_path)

        # Store for tab switching
        self._script_project_path = project_path
        self._script_tabs = {}
        self._script_active_tab = None

        # Load world_config for tag icons
        self._script_world_config = {}
        world_config_path = project_path / "world_bible" / "world_config.json"
        if world_config_path.exists():
            try:
                self._script_world_config = json.loads(world_config_path.read_text(encoding='utf-8'))
            except Exception:
                pass

        # Tab bar at top
        tab_bar = ctk.CTkFrame(self.content_frame, fg_color=theme.colors.bg_dark, height=45)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        # Define tabs - Script, Visual Script, Prompts
        tabs = [
            ("📜 Script", "script"),
            ("🎬 Visual Script", "visual"),
            ("🖼️ Prompts", "prompts"),
        ]

        # Create tab buttons
        for tab_name, tab_id in tabs:
            tab_btn = ctk.CTkButton(
                tab_bar,
                text=tab_name,
                width=140,
                height=35,
                corner_radius=0,
                fg_color="transparent",
                hover_color=theme.colors.bg_medium,
                text_color=theme.colors.text_secondary,
                command=lambda tid=tab_id: self._switch_script_tab(tid)
            )
            tab_btn.pack(side="left", padx=2, pady=5)
            self._script_tabs[tab_id] = tab_btn

        # Content area for tabs
        self._script_tab_content = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self._script_tab_content.pack(fill="both", expand=True)

        # Show first tab
        self._switch_script_tab('script')

    def _switch_script_tab(self, tab_id: str) -> None:
        """Switch to a different Script tab."""
        # Update tab button styles
        for tid, btn in self._script_tabs.items():
            if tid == tab_id:
                btn.configure(fg_color=theme.colors.primary, text_color=theme.colors.text_primary)
            else:
                btn.configure(fg_color="transparent", text_color=theme.colors.text_secondary)

        self._script_active_tab = tab_id

        # Clear content area safely
        self._safe_destroy_widgets(self._script_tab_content)

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(self._script_tab_content, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Render appropriate content
        if tab_id == "script":
            self._render_script_tab(scroll)
        elif tab_id == "visual":
            self._render_visual_script_tab(scroll)
        elif tab_id == "prompts":
            self._render_prompts_tab(scroll)

    def _render_script_tab(self, parent) -> None:
        """Render the Script tab with scene cards."""
        import re

        scripts_path = self._script_project_path / "scripts"

        # Load script.md (the only script file used by UI)
        script_file = scripts_path / "script.md"
        if not script_file.exists():
            self._show_empty_script_tab(parent, "📜", "No script found",
                "Run the Writer pipeline to generate a script.")
            return

        # Load and parse script
        try:
            script_content = script_file.read_text(encoding='utf-8')
        except Exception as e:
            self._show_empty_script_tab(parent, "📜", "Error loading script", str(e))
            return

        # Parse scenes from script
        scenes = self._parse_script_scenes(script_content)

        if not scenes:
            self._show_empty_script_tab(parent, "📜", "No scenes found",
                "The script may be empty or in an unexpected format.")
            return

        # Header
        header_frame = ctk.CTkFrame(parent, fg_color=theme.colors.bg_dark, corner_radius=8)
        header_frame.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.md)

        ctk.CTkLabel(
            header_frame,
            text=f"📜 Script: {script_file.name}",
            font=(theme.fonts.family, 18, "bold"),
            text_color=theme.colors.text_primary
        ).pack(side="left", padx=theme.spacing.md, pady=theme.spacing.md)

        ctk.CTkLabel(
            header_frame,
            text=f"{len(scenes)} scenes",
            text_color=theme.colors.text_muted
        ).pack(side="right", padx=theme.spacing.md, pady=theme.spacing.md)

        # Render each scene
        for scene in scenes:
            self._render_script_scene(parent, scene, self._script_world_config, script_file)

    def _render_visual_script_tab(self, parent) -> None:
        """Render the Visual Script tab with frame cards.

        Loads visual script from storyboard/visual_script.json (Director output).
        Supports scene.frame.camera notation format.
        """
        import json

        # Try multiple possible paths for visual script
        possible_paths = [
            self._script_project_path / "storyboard" / "visual_script.json",  # Director output
            self._script_project_path / "storyboards" / "storyboard_prompts.json",  # Legacy
            self._script_project_path / "storyboard_output" / "visual_script.json",  # Alt location
        ]

        visual_path = None
        for path in possible_paths:
            if path.exists():
                visual_path = path
                break

        if not visual_path:
            self._show_empty_script_tab(parent, "🎬", "No visual script found",
                "Run the Director pipeline to generate a visual script.")
            return

        try:
            data = json.loads(visual_path.read_text(encoding='utf-8'))

            # Handle different JSON structures
            if isinstance(data, list):
                frames = data
            elif "scenes" in data:
                # New Director output format - extract frames from scenes
                frames = []
                for scene in data.get("scenes", []):
                    frames.extend(scene.get("frames", []))
            else:
                frames = data.get("frames", [])

        except Exception as e:
            self._show_empty_script_tab(parent, "🎬", "Error loading visual script", str(e))
            return

        if not frames:
            self._show_empty_script_tab(parent, "🎬", "No frames found",
                "The visual script is empty.")
            return

        # Get scene count from data
        total_scenes = data.get("total_scenes", len(data.get("scenes", []))) if isinstance(data, dict) else 0
        total_frames = data.get("total_frames", len(frames)) if isinstance(data, dict) else len(frames)

        # Header
        header_frame = ctk.CTkFrame(parent, fg_color=theme.colors.bg_dark, corner_radius=8)
        header_frame.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.md)

        ctk.CTkLabel(
            header_frame,
            text="🎬 Visual Script",
            font=(theme.fonts.family, 18, "bold"),
            text_color=theme.colors.text_primary
        ).pack(side="left", padx=theme.spacing.md, pady=theme.spacing.md)

        # Show scene and frame counts
        stats_text = f"{total_scenes} scenes • {total_frames} frames" if total_scenes else f"{len(frames)} frames"
        ctk.CTkLabel(
            header_frame,
            text=stats_text,
            text_color=theme.colors.text_muted
        ).pack(side="right", padx=theme.spacing.md, pady=theme.spacing.md)

        # Group frames by scene for better organization
        current_scene = None
        for i, frame in enumerate(frames):
            scene_num = frame.get("scene_number", 0)

            # Add scene header if scene changed
            if scene_num != current_scene and scene_num > 0:
                current_scene = scene_num
                scene_header = ctk.CTkFrame(parent, fg_color=theme.colors.bg_medium, corner_radius=6)
                scene_header.pack(fill="x", padx=theme.spacing.md, pady=(theme.spacing.md, theme.spacing.sm))
                ctk.CTkLabel(
                    scene_header,
                    text=f"📍 Scene {scene_num}",
                    font=(theme.fonts.family, 14, "bold"),
                    text_color=theme.colors.info  # Use info color (blue) for scene headers
                ).pack(side="left", padx=theme.spacing.md, pady=theme.spacing.sm)

            self._render_visual_frame_card(parent, frame, i)

    def _render_visual_frame_card(self, parent, frame: dict, index: int) -> None:
        """Render a visual script frame card.

        Supports scene.frame.camera notation from Director pipeline output:
        - frame_id: "1.1", "1.2", "2.1" (scene.frame format)
        - camera_notation: "[CAM: Wide Establishing Shot, ...]"
        - position_notation: "[POS: CHAR_MEI center, ...]"
        - lighting_notation: "[LIGHT: Key from East, ...]"
        - prompt: Full visual prompt text
        """
        import re

        card = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8)
        card.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        # Header row
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        # Parse frame ID - format is "scene.frame" like "1.1", "1.2", "2.1"
        frame_id = frame.get("frame_id", f"{index + 1}")
        scene_num = frame.get("scene_number", 0)
        frame_num = frame.get("frame_number", 0)

        # Build display ID in scene.frame.camera notation
        if scene_num and frame_num:
            display_id = f"[{scene_num}.{frame_num}.cA]"
        elif "." in str(frame_id):
            # Parse from frame_id like "1.2"
            parts = str(frame_id).split(".")
            display_id = f"[{parts[0]}.{parts[1]}.cA]"
        else:
            display_id = f"[Frame {index + 1}]"

        ctk.CTkLabel(
            header,
            text=f"🎬 {display_id}",
            font=(theme.fonts.family, 14, "bold"),
            text_color=theme.colors.neon_green
        ).pack(side="left")

        # Camera notation - extract shot type from "[CAM: Wide Establishing Shot, ...]"
        camera_notation = frame.get("camera_notation", "")
        if camera_notation:
            # Extract just the shot type (first part after CAM:)
            cam_match = re.search(r'\[CAM:\s*([^,\]]+)', camera_notation)
            shot_type = cam_match.group(1).strip() if cam_match else camera_notation
            ctk.CTkLabel(
                header,
                text=f"📷 {shot_type}",
                font=(theme.fonts.family, 11),
                text_color=theme.colors.text_muted
            ).pack(side="right", padx=(theme.spacing.sm, 0))

        # Technical info row (position + lighting)
        position = frame.get("position_notation", "")
        lighting = frame.get("lighting_notation", "")
        if position or lighting:
            tech_row = ctk.CTkFrame(card, fg_color="transparent")
            tech_row.pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.sm))

            if position:
                # Extract position info from "[POS: CHAR_MEI center, ...]"
                pos_match = re.search(r'\[POS:\s*([^\]]+)', position)
                pos_text = pos_match.group(1).strip() if pos_match else position
                ctk.CTkLabel(
                    tech_row,
                    text=f"📍 {pos_text[:50]}{'...' if len(pos_text) > 50 else ''}",
                    font=(theme.fonts.family, 10),
                    text_color=theme.colors.text_muted,
                    fg_color=theme.colors.bg_dark,
                    corner_radius=4
                ).pack(side="left", padx=(0, theme.spacing.sm))

            if lighting:
                # Extract lighting info from "[LIGHT: Key from East, ...]"
                light_match = re.search(r'\[LIGHT:\s*([^\]]+)', lighting)
                light_text = light_match.group(1).strip() if light_match else lighting
                ctk.CTkLabel(
                    tech_row,
                    text=f"💡 {light_text[:40]}{'...' if len(light_text) > 40 else ''}",
                    font=(theme.fonts.family, 10),
                    text_color=theme.colors.text_muted,
                    fg_color=theme.colors.bg_dark,
                    corner_radius=4
                ).pack(side="left")

        # Extract and display actual tags from frame data
        prompt = frame.get("prompt", frame.get("visual_prompt", ""))
        all_text = f"{prompt} {position} {camera_notation} {lighting}"

        # Extract tags using regex patterns for all 6 canonical prefixes
        # Tags MUST be in brackets per notation standard: [PREFIX_NAME]
        char_tags = set(re.findall(r'\[(CHAR_[A-Z0-9_]+)\]', all_text))
        loc_tags = set(re.findall(r'\[(LOC_[A-Z0-9_]+)\]', all_text))
        prop_tags = set(re.findall(r'\[(PROP_[A-Z0-9_]+)\]', all_text))
        concept_tags = set(re.findall(r'\[(CONCEPT_[A-Z0-9_]+)\]', all_text))
        event_tags = set(re.findall(r'\[(EVENT_[A-Z0-9_]+)\]', all_text))
        env_tags = set(re.findall(r'\[(ENV_[A-Z0-9_]+)\]', all_text))

        # Also check frame-level tag fields if present
        if frame.get("characters"):
            for c in frame.get("characters", []):
                if isinstance(c, str):
                    char_tags.add(c if c.startswith("CHAR_") else f"CHAR_{c.upper()}")
                elif isinstance(c, dict):
                    char_tags.add(c.get("tag", ""))
        if frame.get("location"):
            loc = frame.get("location")
            if isinstance(loc, str):
                loc_tags.add(loc if loc.startswith("LOC_") else f"LOC_{loc.upper()}")
            elif isinstance(loc, dict):
                loc_tags.add(loc.get("tag", ""))
        if frame.get("props"):
            for p in frame.get("props", []):
                if isinstance(p, str):
                    prop_tags.add(p if p.startswith("PROP_") else f"PROP_{p.upper()}")
                elif isinstance(p, dict):
                    prop_tags.add(p.get("tag", ""))

        # Display tags row if any tags found (all 6 canonical prefixes)
        all_tags = list(char_tags) + list(loc_tags) + list(prop_tags) + list(concept_tags) + list(event_tags) + list(env_tags)
        all_tags = [t for t in all_tags if t]  # Filter empty

        if all_tags:
            tags_row = ctk.CTkFrame(card, fg_color="transparent")
            tags_row.pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.sm))

            for tag in all_tags[:8]:  # Limit to 8 tags to avoid overflow
                # Color code by tag type (6 canonical prefixes)
                if tag.startswith("CHAR_"):
                    tag_color = theme.colors.info  # Blue for characters
                    tag_icon = "👤"
                elif tag.startswith("LOC_"):
                    tag_color = theme.colors.success  # Green for locations
                    tag_icon = "📍"
                elif tag.startswith("PROP_"):
                    tag_color = theme.colors.warning  # Orange for props
                    tag_icon = "🎭"
                elif tag.startswith("CONCEPT_"):
                    tag_color = theme.colors.primary  # Primary for concepts
                    tag_icon = "💡"
                elif tag.startswith("EVENT_"):
                    tag_color = theme.colors.error  # Red for events
                    tag_icon = "📅"
                elif tag.startswith("ENV_"):
                    tag_color = theme.colors.text_secondary  # Secondary for environment
                    tag_icon = "🌤️"
                else:
                    tag_color = theme.colors.text_muted
                    tag_icon = "🏷️"

                tag_label = ctk.CTkLabel(
                    tags_row,
                    text=f"{tag_icon} [{tag}]",
                    font=(theme.fonts.family, 10),
                    text_color=tag_color,
                    fg_color=theme.colors.bg_dark,
                    corner_radius=4
                )
                tag_label.pack(side="left", padx=(0, theme.spacing.xs))

            if len(all_tags) > 8:
                ctk.CTkLabel(
                    tags_row,
                    text=f"+{len(all_tags) - 8} more",
                    font=(theme.fonts.family, 9),
                    text_color=theme.colors.text_muted
                ).pack(side="left", padx=theme.spacing.xs)

        # Prompt text
        if prompt:
            ctk.CTkLabel(
                card,
                text=prompt[:500] + "..." if len(prompt) > 500 else prompt,
                font=(theme.fonts.family, 12),
                text_color=theme.colors.text_secondary,
                wraplength=700,
                justify="left",
                anchor="w"
            ).pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.md))

    def _render_prompts_tab(self, parent) -> None:
        """Render the Prompts tab with storyboard prompt cards."""
        import json

        # Try multiple possible locations for prompts
        prompts_paths = [
            self._script_project_path / "storyboard_output" / "prompts" / "shot_prompts.json",
            self._script_project_path / "prompts" / "shot_prompts.json",
            self._script_project_path / "storyboard_output" / "shot_prompts.json",
        ]

        prompts_path = None
        for p in prompts_paths:
            if p.exists():
                prompts_path = p
                break

        if not prompts_path:
            self._show_empty_script_tab(parent, "🖼️", "No prompts found",
                "Run the Storyboard pipeline to generate prompts.")
            return

        try:
            data = json.loads(prompts_path.read_text(encoding='utf-8'))
            prompts = data if isinstance(data, list) else data.get("prompts", data.get("shots", []))
        except Exception as e:
            self._show_empty_script_tab(parent, "🖼️", "Error loading prompts", str(e))
            return

        if not prompts:
            self._show_empty_script_tab(parent, "🖼️", "No prompts found",
                "The prompts file is empty.")
            return

        # Header
        header_frame = ctk.CTkFrame(parent, fg_color=theme.colors.bg_dark, corner_radius=8)
        header_frame.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.md)

        ctk.CTkLabel(
            header_frame,
            text="🖼️ Storyboard Prompts",
            font=(theme.fonts.family, 18, "bold"),
            text_color=theme.colors.text_primary
        ).pack(side="left", padx=theme.spacing.md, pady=theme.spacing.md)

        ctk.CTkLabel(
            header_frame,
            text=f"{len(prompts)} prompts",
            text_color=theme.colors.text_muted
        ).pack(side="right", padx=theme.spacing.md, pady=theme.spacing.md)

        # Render each prompt
        for i, prompt_data in enumerate(prompts):
            self._render_prompt_card(parent, prompt_data, i)

    def _render_prompt_card(self, parent, prompt_data: dict, index: int) -> None:
        """Render a storyboard prompt card."""
        card = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8)
        card.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        # Header row
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        shot_id = prompt_data.get("shot_id", prompt_data.get("id", f"Shot {index + 1}"))
        ctk.CTkLabel(
            header,
            text=f"🖼️ {shot_id}",
            font=(theme.fonts.family, 14, "bold"),
            text_color=theme.colors.neon_green
        ).pack(side="left")

        # Model used
        model = prompt_data.get("model", "")
        if model:
            ctk.CTkLabel(
                header,
                text=model,
                font=(theme.fonts.family, 10),
                text_color=theme.colors.text_muted
            ).pack(side="right")

        # Prompt text
        prompt = prompt_data.get("prompt", prompt_data.get("text", ""))
        if prompt:
            ctk.CTkLabel(
                card,
                text=prompt[:500] + "..." if len(prompt) > 500 else prompt,
                font=(theme.fonts.family, 12),
                text_color=theme.colors.text_secondary,
                wraplength=700,
                justify="left",
                anchor="w"
            ).pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.sm))

    def _show_empty_script_tab(self, parent, icon: str, title: str, message: str) -> None:
        """Show empty state for a script tab."""
        empty_frame = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8)
        empty_frame.pack(fill="x", pady=theme.spacing.md, padx=theme.spacing.md)

        ctk.CTkLabel(
            empty_frame,
            text=icon,
            font=(theme.fonts.family, 48),
            text_color=theme.colors.text_muted
        ).pack(pady=(theme.spacing.lg, theme.spacing.sm))

        ctk.CTkLabel(
            empty_frame,
            text=title,
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.text_primary
        ).pack()

        ctk.CTkLabel(
            empty_frame,
            text=message,
            text_color=theme.colors.text_secondary,
            justify="center"
        ).pack(pady=(theme.spacing.sm, theme.spacing.lg))

    def _parse_script_scenes(self, content: str) -> list:
        """Parse script content into scene objects.

        Supports the standard script format:
        ## Scene X: Description
        **Location:** [LOC_TAG]
        **Time:** ...
        **Characters:** [CHAR_TAG], ...
        ### Beat X
        Beat content...
        """
        import re

        scenes = []

        # Split by ## Scene X: pattern (the actual format used by Writer pipeline)
        scene_pattern = r'## Scene (\d+):\s*(.+?)(?=\n## Scene \d+:|\Z)'
        scene_matches = re.findall(scene_pattern, content, re.DOTALL)

        for scene_num, scene_content in scene_matches:
            scene_content = scene_content.strip()

            # Extract scene title (first line after ## Scene X:)
            title_match = re.match(r'^([^\n]+)', scene_content)
            scene_title = title_match.group(1).strip() if title_match else f"Scene {scene_num}"

            # Extract metadata
            location_match = re.search(r'\*\*Location:\*\*\s*(.+?)(?=\n|\Z)', scene_content)
            time_match = re.search(r'\*\*Time:\*\*\s*(.+?)(?=\n|\Z)', scene_content)
            purpose_match = re.search(r'\*\*Purpose:\*\*\s*(.+?)(?=\n|\Z)', scene_content)
            emotional_match = re.search(r'\*\*Emotional Beat:\*\*\s*(.+?)(?=\n|\Z)', scene_content)

            # Extract tags from content (all 6 canonical prefixes)
            char_tags = re.findall(r'\[(CHAR_[A-Z0-9_]+)\]', scene_content)
            loc_tags = re.findall(r'\[(LOC_[A-Z0-9_]+(?:_DIR_[NSEW])?)\]', scene_content)
            prop_tags = re.findall(r'\[(PROP_[A-Z0-9_]+)\]', scene_content)
            concept_tags = re.findall(r'\[(CONCEPT_[A-Z0-9_]+)\]', scene_content)
            event_tags = re.findall(r'\[(EVENT_[A-Z0-9_]+)\]', scene_content)
            env_tags = re.findall(r'\[(ENV_[A-Z0-9_]+)\]', scene_content)

            # Extract beats
            beats = []
            beat_pattern = r'### Beat (\d+)\s*\n(.+?)(?=\n### Beat \d+|\n## Scene \d+:|\Z)'
            beat_matches = re.findall(beat_pattern, scene_content, re.DOTALL)

            for beat_num, beat_content in beat_matches:
                beat_content = beat_content.strip()
                # First paragraph is the beat description
                beat_desc_match = re.match(r'^([^\n]+(?:\n(?!\*\*)[^\n]+)*)', beat_content)
                beat_desc = beat_desc_match.group(1).strip() if beat_desc_match else beat_content[:200]

                beats.append({
                    'number': int(beat_num),
                    'content': beat_content,
                    'description': beat_desc
                })

            scenes.append({
                'id': f"scene.{scene_num}",
                'number': int(scene_num),
                'title': scene_title,
                'content': scene_content,
                'location': location_match.group(1).strip() if location_match else "",
                'time': time_match.group(1).strip() if time_match else "",
                'purpose': purpose_match.group(1).strip() if purpose_match else "",
                'emotional_beat': emotional_match.group(1).strip() if emotional_match else "",
                'beats': beats,
                'char_tags': list(set(char_tags)),
                'loc_tags': list(set(loc_tags)),
                'prop_tags': list(set(prop_tags)),
                'concept_tags': list(set(concept_tags)),
                'event_tags': list(set(event_tags)),
                'env_tags': list(set(env_tags)),
            })

        return scenes

    def _render_script_scene(self, parent, scene: dict, world_config: dict, script_file) -> None:
        """Render a single scene card with beats."""
        # Scene card
        card = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8)
        card.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        # Header row with scene number and title
        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        scene_num = scene.get('number', 0)
        scene_title = scene.get('title', f"Scene {scene_num}")

        ctk.CTkLabel(
            header_row,
            text=f"🎬 Scene {scene_num}",
            font=(theme.fonts.family, 14, "bold"),
            text_color=theme.colors.neon_green
        ).pack(side="left")

        # Edit button
        edit_btn = ctk.CTkButton(
            header_row,
            text="✏️ Edit",
            width=60,
            height=24,
            fg_color=theme.colors.bg_medium,
            hover_color=theme.colors.bg_hover,
            text_color=theme.colors.text_primary,
            command=lambda s=scene, f=script_file: self._edit_scene(s, f)
        )
        edit_btn.pack(side="right")

        # Scene title/description
        if scene_title:
            ctk.CTkLabel(
                card,
                text=scene_title[:150] + ("..." if len(scene_title) > 150 else ""),
                font=(theme.fonts.family, 12),
                text_color=theme.colors.text_primary,
                wraplength=700,
                justify="left",
                anchor="w"
            ).pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.xs))

        # Metadata row (location, time)
        meta_row = ctk.CTkFrame(card, fg_color="transparent")
        meta_row.pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.xs))

        if scene.get('location'):
            ctk.CTkLabel(
                meta_row,
                text=f"📍 {scene['location']}",
                font=(theme.fonts.family, 10),
                text_color=theme.colors.text_muted
            ).pack(side="left", padx=(0, theme.spacing.md))

        if scene.get('time'):
            ctk.CTkLabel(
                meta_row,
                text=f"🕐 {scene['time']}",
                font=(theme.fonts.family, 10),
                text_color=theme.colors.text_muted
            ).pack(side="left", padx=(0, theme.spacing.md))

        # Tags row
        tags_row = ctk.CTkFrame(card, fg_color="transparent")
        tags_row.pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.sm))

        # Character tags
        for tag in scene.get('char_tags', [])[:5]:
            tag_label = ctk.CTkLabel(
                tags_row,
                text=f"👤 {tag.replace('CHAR_', '')}",
                font=(theme.fonts.family, 10),
                text_color=theme.colors.text_secondary,
                fg_color=theme.colors.bg_dark,
                corner_radius=4
            )
            tag_label.pack(side="left", padx=2)

        # Location tags (show simplified)
        for tag in scene.get('loc_tags', [])[:2]:
            # Remove directional suffix for display
            display_tag = tag.replace('LOC_', '').split('_DIR_')[0]
            tag_label = ctk.CTkLabel(
                tags_row,
                text=f"🏠 {display_tag}",
                font=(theme.fonts.family, 10),
                text_color=theme.colors.text_secondary,
                fg_color=theme.colors.bg_dark,
                corner_radius=4
            )
            tag_label.pack(side="left", padx=2)

        # Purpose/emotional beat
        if scene.get('purpose'):
            ctk.CTkLabel(
                card,
                text=f"📌 {scene['purpose']}",
                font=(theme.fonts.family, 11),
                text_color=theme.colors.text_secondary,
                wraplength=700,
                justify="left",
                anchor="w"
            ).pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.xs))

        # Beats summary
        beats = scene.get('beats', [])
        if beats:
            beats_frame = ctk.CTkFrame(card, fg_color=theme.colors.bg_dark, corner_radius=4)
            beats_frame.pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.md))

            ctk.CTkLabel(
                beats_frame,
                text=f"📝 {len(beats)} beats",
                font=(theme.fonts.family, 10, "bold"),
                text_color=theme.colors.text_muted
            ).pack(anchor="w", padx=theme.spacing.sm, pady=(theme.spacing.xs, 0))

            # Show first 2 beats as preview
            for beat in beats[:2]:
                beat_desc = beat.get('description', '')[:150]
                if len(beat.get('description', '')) > 150:
                    beat_desc += "..."
                ctk.CTkLabel(
                    beats_frame,
                    text=f"  • Beat {beat['number']}: {beat_desc}",
                    font=(theme.fonts.family, 10),
                    text_color=theme.colors.text_secondary,
                    wraplength=680,
                    justify="left",
                    anchor="w"
                ).pack(fill="x", padx=theme.spacing.sm, pady=1)

            if len(beats) > 2:
                ctk.CTkLabel(
                    beats_frame,
                    text=f"  ... and {len(beats) - 2} more beats",
                    font=(theme.fonts.family, 10),
                    text_color=theme.colors.text_muted
                ).pack(anchor="w", padx=theme.spacing.sm, pady=(0, theme.spacing.xs))

    def _edit_scene(self, scene: dict, script_file) -> None:
        """Open scene editor dialog."""
        from greenlight.ui.dialogs.scene_editor_dialog import SceneEditorDialog

        dialog = SceneEditorDialog(
            self,
            scene_id=scene['id'],
            scene_content=scene['content'],
            script_file=script_file
        )
        dialog.grab_set()

    def _show_script_empty(self, message: str) -> None:
        """Show empty state for Script panel (no project loaded)."""
        self._show_empty_script_tab(self.content_frame, "📜", "Script", message)

    def _show_world_bible(self) -> None:
        """Show the World Bible management page with tabbed interface."""
        from pathlib import Path
        import json

        # Get project path
        project_path = self._current_content.get('project_path')
        if not project_path:
            scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
            scroll.pack(fill="both", expand=True)
            self._show_world_bible_empty(scroll, "No project loaded. Select a project to manage its World Bible.")
            return

        project_path = Path(project_path)
        world_bible_path = project_path / "world_bible"
        world_config_path = world_bible_path / "world_config.json"

        # Load world_config.json if it exists
        world_config = {}
        if world_config_path.exists():
            try:
                world_config = json.loads(world_config_path.read_text(encoding='utf-8'))
            except Exception as e:
                print(f"Error loading world_config.json: {e}")

        if not world_bible_path.exists():
            world_bible_path.mkdir(parents=True, exist_ok=True)

        # Main container
        main_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        main_container.pack(fill="both", expand=True)

        # Tab bar at the top
        tab_bar = ctk.CTkFrame(main_container, fg_color=theme.colors.bg_dark, height=45)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        # Tab content area
        tab_content = ctk.CTkFrame(main_container, fg_color="transparent")
        tab_content.pack(fill="both", expand=True)

        # Store references for tab switching
        self._wb_tab_content = tab_content
        self._wb_world_config = world_config
        self._wb_world_bible_path = world_bible_path
        self._wb_tabs = {}
        self._wb_active_tab = None

        # Define tabs - Characters, Locations, Props, World, Lore, Style Core
        tabs = [
            ("👤 Characters", "characters", len(world_config.get('characters', []))),
            ("📍 Locations", "locations", len(world_config.get('locations', []))),
            ("🔧 Props", "props", len(world_config.get('props', []))),
            ("🌍 World", "world", 1),  # World overview
            ("📜 Lore", "lore", 1),    # Themes, rules, lore
            ("🎨 Style Core", "style", 1),  # Visual style settings
        ]

        # Create tab buttons with tooltips
        for tab_name, tab_id, count in tabs:
            tab_btn = ctk.CTkButton(
                tab_bar,
                text=f"{tab_name} ({count})",
                width=140,
                height=35,
                corner_radius=0,
                fg_color="transparent",
                hover_color=theme.colors.bg_medium,
                text_color=theme.colors.text_secondary,
                command=lambda tid=tab_id: self._switch_world_bible_tab(tid)
            )
            tab_btn.pack(side="left", padx=2, pady=5)
            self._wb_tabs[tab_id] = tab_btn

            # Add tooltip for this tab
            if tab_id in TAB_TOOLTIPS:
                Tooltip(tab_btn, TAB_TOOLTIPS[tab_id])

        # Show first tab with content
        if world_config.get('characters'):
            self._switch_world_bible_tab('characters')
        elif world_config.get('locations'):
            self._switch_world_bible_tab('locations')
        elif world_config.get('props'):
            self._switch_world_bible_tab('props')
        else:
            self._switch_world_bible_tab('characters')

    def _switch_world_bible_tab(self, tab_id: str) -> None:
        """Switch to a different World Bible tab."""
        # Update tab button styles
        for tid, btn in self._wb_tabs.items():
            if tid == tab_id:
                btn.configure(fg_color=theme.colors.primary, text_color=theme.colors.text_primary)
            else:
                btn.configure(fg_color="transparent", text_color=theme.colors.text_secondary)

        self._wb_active_tab = tab_id

        # Clear content area safely
        self._safe_destroy_widgets(self._wb_tab_content)

        # Allow pending events to clear before creating new widgets
        # This prevents race conditions with CTkScrollableFrame's internal canvas
        try:
            self._wb_tab_content.update()
        except Exception:
            pass

        # Add "Generate All References" button for characters, locations, props tabs
        if tab_id in ("characters", "locations", "props"):
            action_bar = ctk.CTkFrame(self._wb_tab_content, fg_color="transparent", height=40)
            action_bar.pack(fill="x", padx=theme.spacing.sm, pady=(theme.spacing.sm, 0))
            action_bar.pack_propagate(False)

            gen_all_btn = ctk.CTkButton(
                action_bar,
                text=f"🎨 Generate All {tab_id.title()} References",
                fg_color=theme.colors.accent,
                hover_color=theme.colors.accent_hover,
                height=32,
                command=lambda t=tab_id: self._generate_all_references(t)
            )
            gen_all_btn.pack(side="left", padx=theme.spacing.xs)

        # Create scrollable grid area
        scroll = ctk.CTkScrollableFrame(self._wb_tab_content, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=theme.spacing.sm, pady=theme.spacing.sm)

        # Grid container for cards
        grid_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True)

        # Render appropriate content
        if tab_id == "characters":
            self._render_character_grid(grid_frame, self._wb_world_config.get('characters', []))
        elif tab_id == "locations":
            self._render_location_grid(grid_frame, self._wb_world_config.get('locations', []))
        elif tab_id == "props":
            self._render_prop_grid(grid_frame, self._wb_world_config.get('props', []))
        elif tab_id == "world":
            self._render_world_tab(grid_frame)
        elif tab_id == "lore":
            self._render_lore_tab(grid_frame)
        elif tab_id == "style":
            self._render_style_tab(grid_frame)

    def _render_character_grid(self, parent, characters: List[Dict]) -> None:
        """Render character cards in a grid layout."""
        if not characters:
            self._show_empty_tab(parent, "👤", "No characters defined",
                "Run the Writer pipeline to extract characters from your pitch.")
            return

        # Grid layout - 3 columns
        row = 0
        col = 0
        max_cols = 3

        for char in characters:
            card = self._create_tag_card(parent, char, "character")
            card.grid(row=row, column=col, padx=theme.spacing.sm, pady=theme.spacing.sm, sticky="nsew")

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Configure grid weights for responsive layout
        for c in range(max_cols):
            parent.grid_columnconfigure(c, weight=1)

    def _render_location_grid(self, parent, locations: List[Dict]) -> None:
        """Render location cards in a grid layout."""
        if not locations:
            self._show_empty_tab(parent, "📍", "No locations defined",
                "Run the Writer pipeline to extract locations from your pitch.")
            return

        row = 0
        col = 0
        max_cols = 3

        for loc in locations:
            card = self._create_tag_card(parent, loc, "location")
            card.grid(row=row, column=col, padx=theme.spacing.sm, pady=theme.spacing.sm, sticky="nsew")

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        for c in range(max_cols):
            parent.grid_columnconfigure(c, weight=1)

    def _render_prop_grid(self, parent, props: List[Dict]) -> None:
        """Render prop cards in a grid layout."""
        if not props:
            self._show_empty_tab(parent, "🔧", "No props defined",
                "Run the Writer pipeline to extract props from your pitch.")
            return

        row = 0
        col = 0
        max_cols = 3

        for prop in props:
            card = self._create_tag_card(parent, prop, "prop")
            card.grid(row=row, column=col, padx=theme.spacing.sm, pady=theme.spacing.sm, sticky="nsew")

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        for c in range(max_cols):
            parent.grid_columnconfigure(c, weight=1)

    def _render_world_tab(self, parent) -> None:
        """Render the World tab with overview information."""
        from pathlib import Path

        # Read from world_config.json first, fallback to pitch.md
        pitch_path = self._wb_world_bible_path / "pitch.md"
        pitch_data = self._parse_pitch_sections(pitch_path)

        # World overview sections - prefer world_config.json, fallback to pitch.md
        world_sections = [
            ("📖 Logline", self._wb_world_config.get("logline") or pitch_data.get("logline", ""), "logline"),
            ("🎭 Genre", self._wb_world_config.get("genre") or pitch_data.get("genre", ""), "genre"),
            ("📝 Synopsis", self._wb_world_config.get("synopsis") or pitch_data.get("synopsis", ""), "synopsis"),
        ]

        # Also show generated timestamp and all_tags from world_config
        if self._wb_world_config.get("generated"):
            world_sections.append(("🕐 Generated", self._wb_world_config.get("generated", ""), "generated"))

        if self._wb_world_config.get("all_tags"):
            tags_str = ", ".join(self._wb_world_config.get("all_tags", []))
            world_sections.append(("🏷️ All Tags", tags_str, "all_tags"))

        for title, content, section_id in world_sections:
            if content:
                self._create_info_card(parent, title, content, section_id, editable=(section_id in ["logline", "synopsis"]))

        if not any(content for _, content, _ in world_sections):
            self._show_empty_tab(parent, "🌍", "No world overview found",
                "Run the Writer pipeline to generate world data.")

    def _render_lore_tab(self, parent) -> None:
        """Render the Lore tab with themes, world rules, etc."""
        from pathlib import Path

        # Read from world_config.json first, fallback to pitch.md
        pitch_path = self._wb_world_bible_path / "pitch.md"
        pitch_data = self._parse_pitch_sections(pitch_path)

        # Lore sections - prefer world_config.json, fallback to pitch.md
        lore_sections = [
            ("🎯 Themes", self._wb_world_config.get("themes") or pitch_data.get("themes", ""), "themes"),
            ("⚙️ World Rules", self._wb_world_config.get("world_rules") or pitch_data.get("world_rules", ""), "world_rules"),
        ]

        for title, content, section_id in lore_sections:
            self._create_info_card(parent, title, content, section_id, editable=True,
                                   placeholder="Click Edit to add content..." if not content else None)

        if not any(content for _, content, _ in lore_sections):
            self._show_empty_tab(parent, "📜", "No lore defined yet",
                "Use the Edit button to add themes and world rules.")

    def _render_style_tab(self, parent) -> None:
        """Render the Style Core tab with visual style dropdown and settings.

        Single source of truth: world_config.json
        All style data (visual_style, style_notes, lighting, vibe) is read from
        and written to world_config.json only.
        """
        # Single source of truth: world_config.json
        # No fallback to style_guide.md or pitch.md
        current_style = self._wb_world_config.get("visual_style", "live_action")
        self._create_style_dropdown_card(parent, current_style)

        # Style sections - read only from world_config.json
        style_sections = [
            ("✏️ Style Notes", self._wb_world_config.get("style_notes", ""), "style_notes"),
            ("💡 Lighting", self._wb_world_config.get("lighting", ""), "lighting"),
            ("🎭 Vibe", self._wb_world_config.get("vibe", ""), "vibe"),
        ]

        for title, content, section_id in style_sections:
            self._create_info_card(parent, title, content, section_id, editable=True,
                                   placeholder="Click Edit to add..." if not content else None)

    def _create_style_dropdown_card(self, parent, current_style: str) -> ctk.CTkFrame:
        """Create a card with visual style dropdown selector."""
        # Visual style options
        VISUAL_STYLE_OPTIONS = ["Live Action", "Anime", "2D Animation", "3D Animation", "Mixed Reality"]
        VISUAL_STYLE_MAP = {
            "Live Action": "live_action", "Anime": "anime", "2D Animation": "animation_2d",
            "3D Animation": "animation_3d", "Mixed Reality": "mixed_reality"
        }
        REVERSE_MAP = {v: k for k, v in VISUAL_STYLE_MAP.items()}

        card = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8)
        card.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        # Header row
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        ctk.CTkLabel(
            header,
            text="🎬 Visual Style",
            font=(theme.fonts.family, 14, "bold"),
            text_color=theme.colors.text_primary
        ).pack(side="left")

        # Dropdown selector
        dropdown_frame = ctk.CTkFrame(card, fg_color="transparent")
        dropdown_frame.pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.md))

        ctk.CTkLabel(
            dropdown_frame,
            text="Select your project's visual style:",
            font=(theme.fonts.family, 11),
            text_color=theme.colors.text_secondary
        ).pack(anchor="w", pady=(0, theme.spacing.xs))

        # Get display name for current style
        display_style = REVERSE_MAP.get(current_style, "Live Action")

        style_dropdown = ctk.CTkOptionMenu(
            dropdown_frame,
            values=VISUAL_STYLE_OPTIONS,
            fg_color=theme.colors.bg_dark,
            button_color=theme.colors.primary,
            button_hover_color=theme.colors.neon_green,
            dropdown_fg_color=theme.colors.bg_medium,
            dropdown_hover_color=theme.colors.primary,
            text_color=theme.colors.text_primary,
            font=(theme.fonts.family, 12),
            width=200,
            command=lambda val: self._save_visual_style(VISUAL_STYLE_MAP.get(val, "live_action"))
        )
        style_dropdown.set(display_style)
        style_dropdown.pack(anchor="w")

        # Description of current style
        style_descriptions = {
            "Live Action": "Photorealistic cinematography with real-world lighting and textures",
            "Anime": "Japanese animation style with expressive characters and dynamic action",
            "2D Animation": "Traditional hand-drawn or digital 2D animation style",
            "3D Animation": "Computer-generated 3D graphics with depth and dimension",
            "Mixed Reality": "Blend of live action and CGI/animated elements"
        }

        desc_label = ctk.CTkLabel(
            dropdown_frame,
            text=style_descriptions.get(display_style, ""),
            font=(theme.fonts.family, 10),
            text_color=theme.colors.text_muted,
            wraplength=400
        )
        desc_label.pack(anchor="w", pady=(theme.spacing.xs, 0))

        return card

    def _save_visual_style(self, style_value: str) -> None:
        """Save the selected visual style to world_config.json (single source of truth)."""
        import json

        # Single source of truth: world_config.json only
        self._wb_world_config["visual_style"] = style_value
        config_path = self._wb_world_bible_path / "world_config.json"
        try:
            config_path.write_text(json.dumps(self._wb_world_config, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"Error saving world_config.json: {e}")

        # Refresh the tab to show updated description
        self._switch_world_bible_tab("style")

    def _parse_pitch_sections(self, pitch_path) -> Dict[str, str]:
        """Parse pitch.md into sections."""
        from pathlib import Path

        result = {}
        if not pitch_path.exists():
            return result

        try:
            content = pitch_path.read_text(encoding='utf-8')
        except Exception:
            return result

        # Parse markdown sections
        current_section = None
        current_content = []

        for line in content.split('\n'):
            if line.startswith('## '):
                # Save previous section
                if current_section:
                    result[current_section] = '\n'.join(current_content).strip()
                # Start new section
                section_name = line[3:].strip().lower().replace(' ', '_')
                current_section = section_name
                current_content = []
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section:
            result[current_section] = '\n'.join(current_content).strip()

        # Also extract inline style info (Camera:, Lighting:, Vibe:)
        for line in content.split('\n'):
            if line.startswith('Camera:'):
                result['camera'] = line.replace('Camera:', '').strip()
            elif line.startswith('Lighting:'):
                result['lighting'] = line.replace('Lighting:', '').strip()
            elif line.startswith('Vibe:'):
                result['vibe'] = line.replace('Vibe:', '').strip()

        return result

    # NOTE: _parse_style_guide removed - style data now comes from world_config.json only

    def _create_info_card(self, parent, title: str, content: str, section_id: str,
                          editable: bool = False, placeholder: str = None) -> ctk.CTkFrame:
        """Create an info card with optional edit capability."""
        card = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8)
        card.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        # Header row with title and edit button
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        ctk.CTkLabel(
            header,
            text=title,
            font=(theme.fonts.family, 14, "bold"),
            text_color=theme.colors.text_primary
        ).pack(side="left")

        if editable:
            edit_btn = ctk.CTkButton(
                header,
                text="✏️ Edit",
                width=60,
                height=24,
                corner_radius=4,
                fg_color=theme.colors.bg_dark,
                hover_color=theme.colors.primary,
                text_color=theme.colors.text_secondary,
                font=(theme.fonts.family, 10),
                command=lambda: self._open_edit_dialog(title, content, section_id)
            )
            edit_btn.pack(side="right")

        # Content area
        display_text = content if content else (placeholder or "No content")
        text_color = theme.colors.text_secondary if content else theme.colors.text_muted

        content_label = ctk.CTkLabel(
            card,
            text=display_text,
            font=(theme.fonts.family, 12),
            text_color=text_color,
            wraplength=600,
            justify="left"
        )
        content_label.pack(anchor="w", padx=theme.spacing.md, pady=(0, theme.spacing.md))

        return card

    def _open_edit_dialog(self, title: str, content: str, section_id: str) -> None:
        """Open a dialog to edit content."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit {title}")
        dialog.geometry("600x400")
        dialog.transient(self)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 600) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")

        dialog.configure(fg_color=theme.colors.bg_dark)

        # Title
        ctk.CTkLabel(
            dialog,
            text=f"Edit {title}",
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.text_primary
        ).pack(pady=theme.spacing.md)

        # Text editor
        text_box = ctk.CTkTextbox(
            dialog,
            fg_color=theme.colors.bg_medium,
            text_color=theme.colors.text_primary,
            font=(theme.fonts.family, 12),
            wrap="word"
        )
        text_box.pack(fill="both", expand=True, padx=theme.spacing.md, pady=theme.spacing.sm)
        text_box.insert("1.0", content or "")

        # Button row
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.md)

        def save_and_close():
            new_content = text_box.get("1.0", "end-1c")
            self._save_section_content(section_id, new_content)
            dialog.destroy()
            # Refresh current tab
            self._switch_world_bible_tab(self._wb_active_tab)

        ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=100,
            fg_color=theme.colors.bg_light,
            hover_color=theme.colors.bg_medium,
            text_color=theme.colors.text_secondary,
            command=dialog.destroy
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="💾 Save",
            width=100,
            fg_color=theme.colors.primary,
            hover_color=theme.colors.neon_green,
            text_color=theme.colors.bg_dark,
            command=save_and_close
        ).pack(side="right")

    def _save_section_content(self, section_id: str, content: str) -> None:
        """Save edited content back to world_config.json (single source of truth)."""
        import json
        from pathlib import Path

        # All editable sections are saved to world_config.json only
        world_config_sections = [
            "logline", "synopsis", "genre", "themes", "world_rules",
            "visual_style", "style_notes", "lighting", "vibe"
        ]

        if section_id in world_config_sections:
            # Single source of truth: world_config.json only
            self._wb_world_config[section_id] = content
            config_path = self._wb_world_bible_path / "world_config.json"
            try:
                config_path.write_text(json.dumps(self._wb_world_config, indent=2), encoding='utf-8')
            except Exception as e:
                print(f"Error saving world_config.json: {e}")

    # NOTE: _update_style_guide and _update_pitch_section removed
    # All style data is now saved to world_config.json only (single source of truth)

    def _create_tag_card(self, parent, data: Dict, tag_type: str) -> ctk.CTkFrame:
        """Create a tag card with reference image, details, and edit button."""
        from pathlib import Path

        # Larger card with more space for text and edit button
        card = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8, width=300, height=420)
        card.pack_propagate(False)

        tag = data.get('tag', 'UNKNOWN')
        name = data.get('name', tag)

        # Color coding by type
        tag_colors = {
            'character': theme.colors.primary,
            'location': '#3498DB',
            'prop': '#F39C12'
        }
        tag_color = tag_colors.get(tag_type, theme.colors.text_secondary)

        # Reference image area (clickable to change) - larger
        img_frame = ctk.CTkFrame(card, fg_color=theme.colors.bg_dark, corner_radius=6, height=160)
        img_frame.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)
        img_frame.pack_propagate(False)

        # Check for existing reference image
        ref_image_path = self._find_reference_image(tag)

        if ref_image_path:
            # Load and display the image, respecting aspect ratio
            try:
                from PIL import Image
                img = Image.open(ref_image_path)

                # Calculate size that fits within bounds while preserving aspect ratio
                max_width, max_height = 280, 150
                orig_width, orig_height = img.size

                # Calculate scale to fit within bounds
                scale = min(max_width / orig_width, max_height / orig_height)
                new_width = int(orig_width * scale)
                new_height = int(orig_height * scale)

                # Use thumbnail to resize (preserves aspect ratio)
                img.thumbnail((new_width, new_height), Image.Resampling.LANCZOS)

                # Create CTkImage with actual resized dimensions (no stretching)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(new_width, new_height))
                img_label = ctk.CTkLabel(img_frame, image=ctk_img, text="")
                img_label.pack(expand=True)
                img_label.bind("<Button-1>", lambda e, t=tag: self._change_reference_image(t))
            except Exception:
                self._show_image_placeholder(img_frame, tag)
        else:
            self._show_image_placeholder(img_frame, tag)

        # Tag badge row with Edit button
        tag_row = ctk.CTkFrame(card, fg_color="transparent")
        tag_row.pack(fill="x", padx=theme.spacing.md, pady=(theme.spacing.xs, 0))

        ctk.CTkLabel(
            tag_row,
            text=f"[{tag}]",
            font=(theme.fonts.family, 12, "bold"),
            text_color=tag_color
        ).pack(side="left")

        # Edit button
        edit_btn = ctk.CTkButton(
            tag_row,
            text="✏️ Edit",
            width=55,
            height=22,
            corner_radius=4,
            fg_color=theme.colors.bg_dark,
            hover_color=theme.colors.primary,
            text_color=theme.colors.text_secondary,
            font=(theme.fonts.family, 10),
            command=lambda d=data, t=tag_type: self._open_tag_edit_dialog(d, t)
        )
        edit_btn.pack(side="right")

        # Name - larger font with more spacing
        ctk.CTkLabel(
            card,
            text=name,
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.text_primary
        ).pack(anchor="w", padx=theme.spacing.md, pady=(theme.spacing.xs, theme.spacing.xs))

        # Type-specific details with larger fonts
        if tag_type == "character":
            role = data.get('role', '')
            age = data.get('age', '')
            if role or age:
                details = f"{role.title()}" if role else ""
                if age:
                    details += f" • {age}" if details else age
                ctk.CTkLabel(
                    card,
                    text=details,
                    font=(theme.fonts.family, 12),
                    text_color=theme.colors.text_muted
                ).pack(anchor="w", padx=theme.spacing.md)

            # Show rich field indicators (icons for populated fields)
            rich_fields = []
            if data.get('appearance') or data.get('visual_appearance'):
                rich_fields.append("👁️")  # Visual
            if data.get('psychology'):
                rich_fields.append("🧠")  # Psychology
            if data.get('speech_patterns') or data.get('speech_style'):
                rich_fields.append("💬")  # Voice
            if data.get('physicality'):
                rich_fields.append("🏃")  # Physicality
            if data.get('emotional_tells'):
                rich_fields.append("❤️")  # Emotional tells

            if rich_fields:
                ctk.CTkLabel(
                    card,
                    text=" ".join(rich_fields),
                    font=(theme.fonts.family, 10),
                    text_color=theme.colors.text_muted
                ).pack(anchor="w", padx=theme.spacing.md)

            # Want (truncated)
            if data.get('want'):
                want = data['want'][:80] + "..." if len(data.get('want', '')) > 80 else data.get('want', '')
                ctk.CTkLabel(
                    card,
                    text=f"💭 {want}",
                    font=(theme.fonts.family, 11),
                    text_color=theme.colors.text_secondary,
                    wraplength=270,
                    justify="left"
                ).pack(anchor="w", padx=theme.spacing.md, pady=(theme.spacing.xs, 0))

        elif tag_type == "location":
            if data.get('time_period'):
                ctk.CTkLabel(
                    card,
                    text=data['time_period'],
                    font=(theme.fonts.family, 12),
                    text_color=theme.colors.text_muted
                ).pack(anchor="w", padx=theme.spacing.md)

            if data.get('description'):
                desc = data['description'][:100] + "..." if len(data['description']) > 100 else data['description']
                ctk.CTkLabel(
                    card,
                    text=desc,
                    font=(theme.fonts.family, 11),
                    text_color=theme.colors.text_secondary,
                    wraplength=270,
                    justify="left"
                ).pack(anchor="w", padx=theme.spacing.md, pady=(theme.spacing.xs, 0))

        elif tag_type == "prop":
            if data.get('associated_character'):
                ctk.CTkLabel(
                    card,
                    text=f"→ {data['associated_character']}",
                    font=(theme.fonts.family, 12),
                    text_color=theme.colors.text_muted
                ).pack(anchor="w", padx=theme.spacing.md)

            if data.get('description'):
                desc = data['description'][:100] + "..." if len(data['description']) > 100 else data['description']
                ctk.CTkLabel(
                    card,
                    text=desc,
                    font=(theme.fonts.family, 11),
                    text_color=theme.colors.text_secondary,
                    wraplength=270,
                    justify="left"
                ).pack(anchor="w", padx=theme.spacing.md, pady=(theme.spacing.xs, 0))

        return card

    def _open_tag_edit_dialog(self, data: Dict, tag_type: str) -> None:
        """Open a dialog to edit a tag's data (character, location, or prop)."""
        import json

        tag = data.get('tag', 'UNKNOWN')
        name = data.get('name', tag)

        # Larger dialog for characters with rich fields
        dialog_height = 750 if tag_type == "character" else 550
        dialog_width = 700 if tag_type == "character" else 650

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit {name}")
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        dialog.transient(self)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dialog_width) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dialog_height) // 2
        dialog.geometry(f"+{x}+{y}")

        dialog.configure(fg_color=theme.colors.bg_dark)

        # Title
        ctk.CTkLabel(
            dialog,
            text=f"Edit [{tag}] - {name}",
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.text_primary
        ).pack(pady=theme.spacing.md)

        # Scrollable content area
        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=theme.spacing.md, pady=theme.spacing.sm)

        # Store entry widgets for saving
        entries = {}

        # Define fields based on tag type
        if tag_type == "character":
            # Get appearance from either field (visual_appearance or appearance)
            appearance_val = data.get("visual_appearance") or data.get("appearance", "")
            fields = [
                # Core identity
                ("name", "Name", data.get("name", ""), False),
                ("role", "Role", data.get("role", ""), False),
                ("age", "Age", data.get("age", ""), False),
                ("ethnicity", "Ethnicity", data.get("ethnicity", ""), False),
                # Character arc
                ("want", "Want (external goal)", data.get("want", ""), True),
                ("need", "Need (internal growth)", data.get("need", ""), True),
                ("flaw", "Flaw", data.get("flaw", ""), True),
                ("arc_type", "Arc Type", data.get("arc_type", ""), False),
                # Visual description (RICH)
                ("appearance", "Appearance (50-100 words)", appearance_val, True),
                ("costume", "Costume (30-50 words)", data.get("costume", ""), True),
                # Psychological profile
                ("psychology", "Psychology (50-75 words)", data.get("psychology", ""), True),
                # Voice and speech
                ("speech_patterns", "Speech Patterns", data.get("speech_patterns", ""), True),
                ("speech_style", "Speech Style", data.get("speech_style", ""), False),
                ("literacy_level", "Literacy Level", data.get("literacy_level", ""), False),
                # Physicality
                ("physicality", "Physicality (30-50 words)", data.get("physicality", ""), True),
                # Decision making
                ("decision_heuristics", "Decision Heuristics", data.get("decision_heuristics", ""), True),
            ]
        elif tag_type == "location":
            fields = [
                ("name", "Name", data.get("name", ""), False),
                ("time_period", "Time Period", data.get("time_period", ""), False),
                ("description", "Description", data.get("description", ""), True),
                ("atmosphere", "Atmosphere", data.get("atmosphere", ""), True),
            ]
        else:  # prop
            fields = [
                ("name", "Name", data.get("name", ""), False),
                ("associated_character", "Associated Character", data.get("associated_character", ""), False),
                ("description", "Description", data.get("description", ""), True),
                ("appearance", "Appearance", data.get("appearance", ""), True),
                ("significance", "Significance", data.get("significance", ""), True),
            ]

        for field_id, label, value, is_multiline in fields:
            field_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            field_frame.pack(fill="x", pady=theme.spacing.xs)

            ctk.CTkLabel(
                field_frame,
                text=label,
                font=(theme.fonts.family, 12, "bold"),
                text_color=theme.colors.text_secondary,
                width=120,
                anchor="w"
            ).pack(side="left", padx=(0, theme.spacing.sm))

            if is_multiline:
                text_box = ctk.CTkTextbox(
                    field_frame,
                    fg_color=theme.colors.bg_medium,
                    text_color=theme.colors.text_primary,
                    font=(theme.fonts.family, 11),
                    height=60,
                    wrap="word"
                )
                text_box.pack(side="left", fill="x", expand=True)
                text_box.insert("1.0", value or "")
                entries[field_id] = ("text", text_box)
            else:
                entry = ctk.CTkEntry(
                    field_frame,
                    fg_color=theme.colors.bg_medium,
                    text_color=theme.colors.text_primary,
                    font=(theme.fonts.family, 11)
                )
                entry.pack(side="left", fill="x", expand=True)
                entry.insert(0, value or "")
                entries[field_id] = ("entry", entry)

        # Button row
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.md)

        def save_and_close():
            # Collect values from entries
            new_data = dict(data)  # Copy original data
            for field_id, (widget_type, widget) in entries.items():
                if widget_type == "text":
                    new_data[field_id] = widget.get("1.0", "end-1c")
                else:
                    new_data[field_id] = widget.get()

            # For characters, sync appearance and visual_appearance fields
            if tag_type == "character" and "appearance" in new_data:
                new_data["visual_appearance"] = new_data["appearance"]

            # Save to world_config.json
            self._save_tag_data(tag, tag_type, new_data)
            dialog.destroy()
            # Refresh current tab
            self._switch_world_bible_tab(self._wb_active_tab)

        ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=100,
            fg_color=theme.colors.bg_light,
            hover_color=theme.colors.bg_medium,
            text_color=theme.colors.text_secondary,
            command=dialog.destroy
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="💾 Save",
            width=100,
            fg_color=theme.colors.primary,
            hover_color=theme.colors.neon_green,
            text_color=theme.colors.bg_dark,
            command=save_and_close
        ).pack(side="right")

    def _save_tag_data(self, tag: str, tag_type: str, new_data: Dict) -> None:
        """Save updated tag data to world_config.json."""
        import json

        config_path = self._wb_world_bible_path / "world_config.json"

        # Determine which list to update
        list_key = f"{tag_type}s"  # characters, locations, props

        # Find and update the item
        items = self._wb_world_config.get(list_key, [])
        for i, item in enumerate(items):
            if item.get('tag') == tag:
                items[i] = new_data
                break

        self._wb_world_config[list_key] = items

        # Save to file
        try:
            config_path.write_text(json.dumps(self._wb_world_config, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"Error saving world_config.json: {e}")

    def _show_image_placeholder(self, parent, tag: str) -> None:
        """Show a placeholder for missing reference image."""
        placeholder = ctk.CTkLabel(
            parent,
            text="🖼️ Click to add\nreference image",
            font=(theme.fonts.family, 11),
            text_color=theme.colors.text_muted,
            justify="center"
        )
        placeholder.pack(expand=True)
        placeholder.bind("<Button-1>", lambda e, t=tag: self._change_reference_image(t))

    def _find_reference_image(self, tag: str) -> Optional[str]:
        """Find the key reference image for a tag using ImageHandler.

        Also triggers auto-labeling for any new images in the tag's directory.
        """
        from pathlib import Path

        if not hasattr(self, '_wb_world_bible_path'):
            return None

        # Get name from world config for auto-labeling
        name = self._get_name_for_tag(tag)

        try:
            from greenlight.core.image_handler import get_image_handler
            handler = get_image_handler(self._wb_world_bible_path.parent)

            # Auto-label any new images and get the labeled key reference
            if name:
                key_ref = handler.get_labeled_reference(tag, name)
            else:
                key_ref = handler.get_key_reference(tag)

            if key_ref:
                return str(key_ref)
        except Exception:
            pass

        # Fallback: Check references folder directly
        refs_path = self._wb_world_bible_path.parent / "references"
        if refs_path.exists():
            for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                img_path = refs_path / f"{tag}{ext}"
                if img_path.exists():
                    return str(img_path)
                img_path = refs_path / f"{tag.lower()}{ext}"
                if img_path.exists():
                    return str(img_path)

        return None

    def _get_name_for_tag(self, tag: str) -> Optional[str]:
        """Get the display name for a tag from world config."""
        if not hasattr(self, '_wb_world_config') or not self._wb_world_config:
            return None

        # Search in characters, locations, props
        for category in ['characters', 'locations', 'props']:
            items = self._wb_world_config.get(category, [])
            for item in items:
                if item.get('tag') == tag:
                    return item.get('name', tag)

        return None

    def _change_reference_image(self, tag: str) -> None:
        """Open the Reference Modal for managing reference images."""
        from greenlight.ui.components.reference_modal import ReferenceModal

        # Determine tag type and get name from world config
        tag_type = "character"
        name = tag

        if tag.startswith("CHAR_"):
            tag_type = "character"
            chars = self._wb_world_config.get("characters", [])
            char_data = next((c for c in chars if c.get("tag") == tag), {})
            name = char_data.get("name", tag.replace("CHAR_", ""))
        elif tag.startswith("LOC_"):
            tag_type = "location"
            locs = self._wb_world_config.get("locations", [])
            loc_data = next((l for l in locs if l.get("tag") == tag), {})
            name = loc_data.get("name", tag.replace("LOC_", ""))
        elif tag.startswith("PROP_"):
            tag_type = "prop"
            props = self._wb_world_config.get("props", [])
            prop_data = next((p for p in props if p.get("tag") == tag), {})
            name = prop_data.get("name", tag.replace("PROP_", ""))

        project_path = self._wb_world_bible_path.parent

        def on_change():
            # Refresh the current tab when modal makes changes
            if hasattr(self, '_wb_active_tab'):
                self._switch_world_bible_tab(self._wb_active_tab)

        # Open the modal
        modal = ReferenceModal(
            self,
            tag=tag,
            name=name,
            tag_type=tag_type,
            project_path=project_path,
            world_config=self._wb_world_config,
            on_change=on_change,
            context_engine=self._context_engine
        )

    def _show_empty_tab(self, parent, icon: str, title: str, message: str) -> None:
        """Show empty state for a tab."""
        frame = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8)
        frame.pack(fill="x", padx=theme.spacing.lg, pady=theme.spacing.lg)

        ctk.CTkLabel(
            frame,
            text=icon,
            font=(theme.fonts.family, 48)
        ).pack(pady=(theme.spacing.lg, theme.spacing.sm))

        ctk.CTkLabel(
            frame,
            text=title,
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.text_primary
        ).pack()

        ctk.CTkLabel(
            frame,
            text=message,
            text_color=theme.colors.text_secondary,
            justify="center"
        ).pack(pady=(theme.spacing.sm, theme.spacing.lg))

    def _generate_all_references(self, tab_id: str) -> None:
        """Generate references for all items in a tab that have empty reference directories."""
        import threading
        from pathlib import Path

        logger.info(f"_generate_all_references called for tab: {tab_id}")

        if not hasattr(self, '_wb_world_config') or not hasattr(self, '_wb_world_bible_path'):
            logger.warning("_generate_all_references: Missing _wb_world_config or _wb_world_bible_path")
            return

        project_path = self._wb_world_bible_path.parent
        refs_dir = project_path / "references"
        logger.info(f"Project path: {project_path}, refs_dir: {refs_dir}")

        # Get items based on tab
        if tab_id == "characters":
            items = self._wb_world_config.get('characters', [])
            tag_type = "character"
        elif tab_id == "locations":
            items = self._wb_world_config.get('locations', [])
            tag_type = "location"
        elif tab_id == "props":
            items = self._wb_world_config.get('props', [])
            tag_type = "prop"
        else:
            logger.warning(f"_generate_all_references: Unknown tab_id: {tab_id}")
            return

        logger.info(f"Found {len(items)} {tab_id} items in world_config")

        # Filter to items with empty or missing reference directories
        items_to_generate = []
        for item in items:
            tag = item.get('tag', '')
            name = item.get('name', tag)
            tag_refs_dir = refs_dir / tag

            # Check if directory is empty or doesn't exist
            if not tag_refs_dir.exists():
                items_to_generate.append((tag, name, item))
            else:
                # Check if directory has any image files
                image_files = list(tag_refs_dir.glob("*.png")) + list(tag_refs_dir.glob("*.jpg"))
                if not image_files:
                    items_to_generate.append((tag, name, item))

        logger.info(f"Items to generate: {len(items_to_generate)}")

        if not items_to_generate:
            # Show notification that all items already have references
            logger.info("All items already have references, nothing to generate")
            if hasattr(self, 'winfo_toplevel'):
                toplevel = self.winfo_toplevel()
                if hasattr(toplevel, 'notification_manager'):
                    toplevel.notification_manager.show_info(
                        "All References Exist",
                        f"All {tab_id} already have reference images."
                    )
            return

        # Show progress notification
        if hasattr(self, 'winfo_toplevel'):
            toplevel = self.winfo_toplevel()
            if hasattr(toplevel, 'notification_manager'):
                toplevel.notification_manager.show_info(
                    "Generating References",
                    f"Generating references for {len(items_to_generate)} {tab_id}..."
                )

        def run_batch_generation():
            import asyncio
            from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
            from greenlight.context.context_engine import ContextEngine
            from datetime import datetime

            logger.info("run_batch_generation thread started")

            try:
                # Initialize handler with ContextEngine for rich prompt generation
                context_engine = ContextEngine()
                context_engine.set_project_path(project_path)
                handler = ImageHandler(project_path, context_engine=context_engine)
                logger.info(f"ImageHandler initialized with project_path: {project_path}")

                # Get selected model from main window
                model = ImageModel.NANO_BANANA  # Default
                if hasattr(self, 'winfo_toplevel'):
                    toplevel = self.winfo_toplevel()
                    if hasattr(toplevel, '_selected_llm') and toplevel._selected_llm:
                        # Try to map LLM to image model
                        pass  # Use default for now

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Get style suffix from Context Engine (single source of truth)
                style_suffix = context_engine.get_world_style()
                logger.info(f"Style suffix from Context Engine: {style_suffix[:100] if style_suffix else 'None'}...")

                # Load Character_Reference_Template.png as layout guide for character sheets
                template_path = Path(__file__).parent.parent.parent / "assets" / "Character_Reference_Template.png"
                character_template_refs = [template_path] if template_path.exists() else []

                generated_count = 0
                for tag, name, item_data in items_to_generate:
                    logger.info(f"Generating reference for {tag} ({name})")
                    # Create refs directory
                    tag_refs_dir = refs_dir / tag
                    tag_refs_dir.mkdir(parents=True, exist_ok=True)

                    # Use ImageHandler's prompt generation methods for rich prompts
                    # These methods use ContextEngine to get full profile data
                    reference_images = None
                    if tag_type == "character":
                        prompt = handler.get_character_sheet_prompt(
                            tag, name, character_data=item_data
                        )
                        # Include Character_Reference_Template.png as layout guide
                        # NO existing character refs - this is fresh generation from description
                        reference_images = character_template_refs if character_template_refs else None
                        output_suffix = "sheet"
                    elif tag_type == "location":
                        # Use location view prompt for a general reference
                        prompt = handler.get_location_view_prompt(
                            tag, name, direction="north",
                            description=item_data.get('description', ''),
                            time_period=item_data.get('time_period', ''),
                            atmosphere=item_data.get('atmosphere', ''),
                            location_data=item_data
                        )
                        output_suffix = "ref"
                    else:
                        prompt = handler.get_prop_reference_prompt(tag, name, item_data)
                        output_suffix = "ref"

                    # Filename format: [{TAG}]_{suffix}_{timestamp}.png
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = tag_refs_dir / f"[{tag}]_{output_suffix}_{timestamp}.png"

                    request = ImageRequest(
                        prompt=prompt,
                        model=model,
                        aspect_ratio="16:9",
                        tag=tag,
                        output_path=output_path,
                        reference_images=reference_images,  # Template for characters, None for others
                        prefix_type="recreate",  # Use recreate template for reference generation
                        style_suffix=style_suffix if style_suffix else None,
                        add_clean_suffix=True
                    )

                    try:
                        result = loop.run_until_complete(handler.generate(request))
                        if result.success:
                            generated_count += 1
                            logger.info(f"Successfully generated reference for {tag}: {output_path}")
                        else:
                            logger.error(f"Failed to generate reference for {tag}: {result.error}")
                    except Exception as e:
                        logger.error(f"Exception generating reference for {tag}: {e}", exc_info=True)

                logger.info(f"Batch generation complete: {generated_count}/{len(items_to_generate)} successful")

                # Refresh tab after completion
                self.after(0, lambda: self._switch_world_bible_tab(tab_id))

                # Show completion notification
                if hasattr(self, 'winfo_toplevel'):
                    toplevel = self.winfo_toplevel()
                    if hasattr(toplevel, 'notification_manager'):
                        self.after(0, lambda: toplevel.notification_manager.show_success(
                            "Generation Complete",
                            f"Generated references for {generated_count}/{len(items_to_generate)} {tab_id}."
                        ))

                loop.close()

            except Exception as e:
                logger.error(f"Exception in run_batch_generation: {e}", exc_info=True)

        logger.info("Starting batch generation thread")
        threading.Thread(target=run_batch_generation, daemon=True).start()

    def _show_world_bible_empty(self, parent, message: str) -> None:
        """Show empty state for World Bible."""
        empty_frame = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8)
        empty_frame.pack(fill="x", pady=theme.spacing.md, padx=theme.spacing.md)

        ctk.CTkLabel(
            empty_frame,
            text="📚 World Bible",
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.text_primary
        ).pack(pady=(theme.spacing.lg, theme.spacing.sm))

        ctk.CTkLabel(
            empty_frame,
            text=message,
            text_color=theme.colors.text_secondary,
            justify="center"
        ).pack(pady=(0, theme.spacing.lg))

    def _create_world_bible_section(self, parent, section_name: str, section_id: str,
                                     description: str, world_bible_path, fields: List[str]) -> None:
        """Create a World Bible section card."""
        from pathlib import Path

        section_path = world_bible_path / section_id

        # Section card
        card = ctk.CTkFrame(parent, fg_color=theme.colors.bg_light, corner_radius=8)
        card.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        # Header row
        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        ctk.CTkLabel(
            header_row,
            text=section_name,
            font=(theme.fonts.family, 14, "bold"),
            text_color=theme.colors.text_primary
        ).pack(side="left")

        # Count items
        item_count = 0
        if section_path.exists() and section_path.is_dir():
            item_count = len([f for f in section_path.iterdir() if f.suffix in ['.json', '.md']])
        elif section_id == "style_guide":
            style_file = world_bible_path / "style_guide.md"
            if style_file.exists():
                item_count = 1

        count_label = ctk.CTkLabel(
            header_row,
            text=f"{item_count} items" if item_count != 1 else "1 item",
            text_color=theme.colors.text_muted,
            font=(theme.fonts.family, 11)
        )
        count_label.pack(side="right")

        # Description
        ctk.CTkLabel(
            card,
            text=description,
            text_color=theme.colors.text_secondary,
            font=(theme.fonts.family, 11)
        ).pack(anchor="w", padx=theme.spacing.md)

        # Action buttons
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        # View/Edit button
        view_btn = ctk.CTkButton(
            btn_row,
            text="📂 Open",
            width=80,
            command=lambda: self._open_world_bible_section(section_id, world_bible_path),
            **theme.get_button_style("secondary")
        )
        view_btn.pack(side="left", padx=(0, theme.spacing.sm))

        # Add new button
        add_btn = ctk.CTkButton(
            btn_row,
            text="➕ Add",
            width=80,
            command=lambda: self._add_world_bible_item(section_id, world_bible_path, fields),
            **theme.get_button_style("primary")
        )
        add_btn.pack(side="left")

        # Show existing items preview
        if item_count > 0:
            self._show_section_items_preview(card, section_id, world_bible_path)

    def _show_section_items_preview(self, parent, section_id: str, world_bible_path) -> None:
        """Show a preview of items in a section."""
        from pathlib import Path
        import json

        section_path = world_bible_path / section_id
        items_frame = ctk.CTkFrame(parent, fg_color=theme.colors.bg_dark, corner_radius=4)
        items_frame.pack(fill="x", padx=theme.spacing.md, pady=(0, theme.spacing.sm))

        items = []
        if section_path.exists() and section_path.is_dir():
            for f in section_path.iterdir():
                if f.suffix == '.json':
                    try:
                        data = json.loads(f.read_text(encoding='utf-8'))
                        items.append(data.get('name', f.stem))
                    except Exception:
                        items.append(f.stem)
                elif f.suffix == '.md':
                    items.append(f.stem)
        elif section_id == "style_guide":
            style_file = world_bible_path / "style_guide.md"
            if style_file.exists():
                items.append("Style Guide")

        # Show up to 5 items
        for item_name in items[:5]:
            item_label = ctk.CTkLabel(
                items_frame,
                text=f"  • {item_name}",
                text_color=theme.colors.text_secondary,
                font=(theme.fonts.family, 11),
                anchor="w"
            )
            item_label.pack(anchor="w", padx=theme.spacing.sm, pady=2)

        if len(items) > 5:
            ctk.CTkLabel(
                items_frame,
                text=f"  ... and {len(items) - 5} more",
                text_color=theme.colors.text_muted,
                font=(theme.fonts.family, 10)
            ).pack(anchor="w", padx=theme.spacing.sm, pady=2)

    def _open_world_bible_section(self, section_id: str, world_bible_path) -> None:
        """Open a World Bible section folder or file."""
        from pathlib import Path

        if section_id == "style_guide":
            target = world_bible_path / "style_guide.md"
            if not target.exists():
                target.write_text("# Style Guide\n\n## Visual Style\n\n## Color Palette\n\n## Mood\n\n")
        else:
            target = world_bible_path / section_id
            if not target.exists():
                target.mkdir(parents=True, exist_ok=True)

        if _process_runner:
            if target.is_dir():
                _process_runner.open_folder(target)
            else:
                _process_runner.open_file(target)
        else:
            import subprocess
            import sys
            try:
                if sys.platform == 'win32':
                    subprocess.run(['explorer' if target.is_dir() else 'start', '', str(target)], shell=True)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', str(target)])
                else:
                    subprocess.run(['xdg-open', str(target)])
            except Exception as e:
                print(f"Error opening: {e}")

    def _add_world_bible_item(self, section_id: str, world_bible_path, fields: List[str]) -> None:
        """Add a new item to a World Bible section."""
        from pathlib import Path
        import json

        section_path = world_bible_path / section_id

        if section_id == "style_guide":
            # Open style guide for editing
            self._open_world_bible_section(section_id, world_bible_path)
            return

        # Create section folder if needed
        if not section_path.exists():
            section_path.mkdir(parents=True, exist_ok=True)

        # Create a new item with template
        item_num = len(list(section_path.glob("*.json"))) + 1
        new_item = {field: "" for field in fields}
        new_item["name"] = f"New {section_id.rstrip('s').title()} {item_num}"

        new_file = section_path / f"{new_item['name'].lower().replace(' ', '_')}.json"
        new_file.write_text(json.dumps(new_item, indent=2), encoding='utf-8')

        # Open the new file
        if _process_runner:
            _process_runner.open_file(new_file)
        else:
            import subprocess
            import sys
            try:
                if sys.platform == 'win32':
                    subprocess.run(['start', '', str(new_file)], shell=True)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', str(new_file)])
                else:
                    subprocess.run(['xdg-open', str(new_file)])
            except Exception as e:
                print(f"Error opening: {e}")

        # Refresh the view
        self.set_mode(WorkspaceMode.WORLD_BIBLE)

    def load_content(self, content: Dict[str, Any]) -> None:
        """Load content into the workspace."""
        self._current_content = content
        
        if hasattr(self, 'editor') and 'text' in content:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", content['text'])
        
        if 'path' in content:
            self.breadcrumb.configure(text=content['path'])
    
    def _on_text_change(self, event) -> None:
        """Handle text change."""
        if self.on_content_change and hasattr(self, 'editor'):
            content = self.editor.get("1.0", "end-1c")
            self.on_content_change(content)
    
    def _save_content(self) -> None:
        """Save current content."""
        if hasattr(self, 'editor'):
            content = self.editor.get("1.0", "end-1c")
            self._current_content['text'] = content
            # Trigger save callback

    def set_project_path(self, path: str) -> None:
        """Set the current project path for loading storyboard data."""
        self._current_content['project_path'] = path

    def set_view(self, view_name: str) -> None:
        """Set the workspace view by name (for menu compatibility).

        Args:
            view_name: One of 'editor', 'storyboard', 'gallery', 'references', 'split', 'world_bible', 'script'
        """
        view_map = {
            'editor': WorkspaceMode.EDITOR,
            'storyboard': WorkspaceMode.STORYBOARD,
            'gallery': WorkspaceMode.GALLERY,
            'references': WorkspaceMode.REFERENCES,
            'split': WorkspaceMode.SPLIT,
            'world_bible': WorkspaceMode.WORLD_BIBLE,
            'script': WorkspaceMode.SCRIPT,
        }
        mode = view_map.get(view_name.lower(), WorkspaceMode.EDITOR)
        self.set_mode(mode)

    def refresh_references(self) -> None:
        """Refresh the references view."""
        if self._mode == WorkspaceMode.REFERENCES:
            self.set_mode(WorkspaceMode.REFERENCES)

    # Note: refresh_storyboard is defined earlier in the class (line ~188)
    # It reloads storyboard data and updates frames without recreating the view

    def refresh_gallery(self) -> None:
        """Refresh the gallery view with latest images."""
        if self._mode == WorkspaceMode.GALLERY:
            self.set_mode(WorkspaceMode.GALLERY)

    def refresh_script(self) -> None:
        """Refresh the script view with latest script content."""
        if self._mode == WorkspaceMode.SCRIPT:
            self.set_mode(WorkspaceMode.SCRIPT)

