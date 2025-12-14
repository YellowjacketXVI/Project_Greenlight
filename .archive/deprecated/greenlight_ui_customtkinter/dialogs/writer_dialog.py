"""
Greenlight Writer Dialog - Configure and run the story generation pipeline.

Generates:
- Story Document (expanded narrative from pitch)
- World Config (characters, locations, props)
- Beat Sheet (scene breakdown)
- Visual Script (frame notations for directing)

Uses the 4-Layer Story Pipeline:
1. Plot Architecture
2. Character Architecture
3. Continuity Validation
4. Motivational Coherence

Or the new Assembly-based Story Pipeline v2:
- 7 Parallel Proposal Agents
- 5 Judge Agents
- Calculator + Synthesizer
- Continuity Loop (max 3 iterations)

Directing Pipeline (replaces Novelization):
- Parallel scene processing
- Frame count consensus (3 judges)
- Frame notation insertion
- Camera/placement notations
"""

import customtkinter as ctk
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import threading
import asyncio
import json
from datetime import datetime
import logging

from greenlight.ui.theme import theme
from greenlight.llm.llm_registry import list_available_llms, get_llm_by_id
from greenlight.llm import LLMManager
from greenlight.pipelines.story_pipeline import StoryPipeline, StoryInput, StoryOutput
from greenlight.tags import TagRegistry
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.writer_dialog")


class TextboxLogHandler(logging.Handler):
    """Custom logging handler that writes to a CTkTextbox."""

    def __init__(self, textbox, log_callback):
        super().__init__()
        self.textbox = textbox
        self.log_callback = log_callback

    def emit(self, record):
        try:
            msg = self.format(record)
            # Only show INFO and above from pipeline modules
            if record.name.startswith('pipelines') and record.levelno >= logging.INFO:
                # Clean up the message - remove module prefix
                clean_msg = msg.split(' | ')[-1] if ' | ' in msg else msg
                self.log_callback(clean_msg)
        except Exception:
            self.handleError(record)


class WriterDialog(ctk.CTkToplevel):
    """Dialog for running the Writer pipeline."""

    # Project size presets - aligned with Writer_Flow_v2.md spec
    PROJECT_PRESETS = {
        "short": {"name": "Short (100-150 words)", "total_words": 125, "scenes": 1, "shots": 3, "media_type": "short"},
        "brief": {"name": "Brief (250-500 words)", "total_words": 375, "scenes": 3, "shots": 9, "media_type": "brief"},
        "standard": {"name": "Standard (750-1000 words)", "total_words": 875, "scenes": 8, "shots": 24, "media_type": "standard"},
        "extended": {"name": "Extended (1250-1500 words)", "total_words": 1375, "scenes": 15, "shots": 45, "media_type": "extended"},
        "feature": {"name": "Feature (2000-3000 words)", "total_words": 2500, "scenes": 40, "shots": 120, "media_type": "feature"},
    }

    # Story Mode is always Assembly (7 parallel agents + 5 judges consensus)
    # Removed standard/enhanced dropdown - assembly is the only mode
    # Removed directing mode dropdown - scene-based processing is the default

    def __init__(
        self,
        parent,
        project_path: Path,
        on_complete: Callable[[Dict], None] = None,
        external_log: Callable[[str], None] = None,
        external_progress: Callable[[float], None] = None,
        close_on_start: bool = False,
        **kwargs
    ):
        # Extract auto-run parameters BEFORE calling super()
        self.auto_run = kwargs.pop('auto_run', False)
        self.auto_llm = kwargs.pop('auto_llm', 'claude-haiku')
        self.auto_media_type = kwargs.pop('auto_media_type', 'brief')
        self.auto_visual_style = kwargs.pop('auto_visual_style', 'live_action')

        super().__init__(parent, **kwargs)

        self.project_path = project_path
        self.on_complete = on_complete
        self.external_log = external_log
        self.external_progress = external_progress
        self.close_on_start = close_on_start
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.cancelled = threading.Event()
        self.running = False

        # If auto_run, skip UI and run immediately
        if self.auto_run:
            self.withdraw()  # Hide window
            self._run_background_pipeline()
            return

        # Window setup
        self.title("Greenlight Writer")
        self.geometry("600x700")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 600) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 700) // 2
        self.geometry(f"+{x}+{y}")

        self.configure(fg_color=theme.colors.bg_medium)

        self._create_ui()

    def _create_ui(self) -> None:
        """Create the dialog UI - compact and clean layout."""
        # Title
        title = ctk.CTkLabel(
            self, text="Writer Pipeline",
            font=(theme.fonts.family, theme.fonts.size_header, "bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(pady=(15, 5))

        # Description
        self.desc_label = ctk.CTkLabel(
            self,
            text="Generate story content from your pitch.",
            text_color=theme.colors.text_secondary,
            justify="center"
        )
        self.desc_label.pack(pady=(0, 10))

        # === CONFIGURATION SECTION (shown before running) ===
        self.config_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.config_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # Load existing pitch content
        pitch_data = self._load_pitch_structured()

        # Pitch input frame - compact design
        pitch_frame = ctk.CTkFrame(self.config_frame, fg_color=theme.colors.bg_dark, corner_radius=8)
        pitch_frame.pack(fill="x", pady=5)

        # Title field (single line)
        row1 = ctk.CTkFrame(pitch_frame, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(row1, text="Title:", width=70, anchor="w", text_color=theme.colors.text_primary).pack(side="left")
        self.pitch_title_entry = ctk.CTkEntry(row1, placeholder_text="Project title", fg_color=theme.colors.bg_medium)
        self.pitch_title_entry.pack(side="left", fill="x", expand=True)
        if pitch_data.get("title"):
            self.pitch_title_entry.insert(0, pitch_data["title"])

        # Logline field (single line)
        row2 = ctk.CTkFrame(pitch_frame, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row2, text="Logline:", width=70, anchor="w", text_color=theme.colors.text_primary).pack(side="left")
        self.pitch_logline_entry = ctk.CTkEntry(row2, placeholder_text="One sentence summary", fg_color=theme.colors.bg_medium)
        self.pitch_logline_entry.pack(side="left", fill="x", expand=True)
        if pitch_data.get("logline"):
            self.pitch_logline_entry.insert(0, pitch_data["logline"])

        # Genre field (single line)
        row3 = ctk.CTkFrame(pitch_frame, fg_color="transparent")
        row3.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row3, text="Genre:", width=70, anchor="w", text_color=theme.colors.text_primary).pack(side="left")
        self.pitch_genre_entry = ctk.CTkEntry(row3, placeholder_text="e.g., Drama, Action, Thriller", fg_color=theme.colors.bg_medium)
        self.pitch_genre_entry.pack(side="left", fill="x", expand=True)
        if pitch_data.get("genre"):
            self.pitch_genre_entry.insert(0, pitch_data["genre"])

        # Characters field (optional, single line)
        row4 = ctk.CTkFrame(pitch_frame, fg_color="transparent")
        row4.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row4, text="Characters:", width=70, anchor="w", text_color=theme.colors.text_muted).pack(side="left")
        self.pitch_characters_entry = ctk.CTkEntry(row4, placeholder_text="(Optional) e.g., Mei, Lin, The General", fg_color=theme.colors.bg_medium)
        self.pitch_characters_entry.pack(side="left", fill="x", expand=True)
        if pitch_data.get("characters"):
            self.pitch_characters_entry.insert(0, pitch_data["characters"])

        # Locations field (optional, single line)
        row5 = ctk.CTkFrame(pitch_frame, fg_color="transparent")
        row5.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row5, text="Locations:", width=70, anchor="w", text_color=theme.colors.text_muted).pack(side="left")
        self.pitch_locations_entry = ctk.CTkEntry(row5, placeholder_text="(Optional) e.g., Palace, Market, Temple", fg_color=theme.colors.bg_medium)
        self.pitch_locations_entry.pack(side="left", fill="x", expand=True)
        if pitch_data.get("locations"):
            self.pitch_locations_entry.insert(0, pitch_data["locations"])

        # Synopsis field (text area)
        row6 = ctk.CTkFrame(pitch_frame, fg_color="transparent")
        row6.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row6, text="Synopsis:", width=70, anchor="nw", text_color=theme.colors.text_primary).pack(side="left", anchor="n")
        self.pitch_synopsis_entry = ctk.CTkTextbox(row6, height=100, wrap="word", fg_color=theme.colors.bg_medium)
        self.pitch_synopsis_entry.pack(side="left", fill="x", expand=True)
        if pitch_data.get("synopsis"):
            self.pitch_synopsis_entry.insert("1.0", pitch_data["synopsis"])

        # Bind @-mention detection
        self.pitch_synopsis_entry.bind("<KeyRelease>", self._on_synopsis_key)

        # Tag preview (compact)
        self.tag_preview_text = ctk.CTkLabel(
            pitch_frame,
            text="Tip: Use @Name in synopsis to auto-detect character tags",
            text_color=theme.colors.text_muted, anchor="w",
            font=(theme.fonts.family, theme.fonts.size_small)
        )
        self.tag_preview_text.pack(fill="x", padx=15, pady=(0, 10))

        # Store created tags
        self._quick_created_tags = []

        # Options frame - compact 2x2 grid
        options_frame = ctk.CTkFrame(self.config_frame, fg_color=theme.colors.bg_dark, corner_radius=8)
        options_frame.pack(fill="x", pady=5)
        options_frame.grid_columnconfigure(0, weight=1)
        options_frame.grid_columnconfigure(1, weight=1)

        # Project size
        size_label = ctk.CTkLabel(
            options_frame, text="Project Size:",
            text_color=theme.colors.text_primary, anchor="w"
        )
        size_label.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        size_options = [f"{v['name']}" for v in self.PROJECT_PRESETS.values()]
        self.size_dropdown = ctk.CTkOptionMenu(
            options_frame, values=size_options,
            fg_color=theme.colors.bg_medium, width=200
        )
        self.size_dropdown.set(size_options[2])  # Default to standard
        self.size_dropdown.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")

        # LLM selector
        llm_label = ctk.CTkLabel(
            options_frame, text="AI Model:",
            text_color=theme.colors.text_primary, anchor="w"
        )
        llm_label.grid(row=0, column=1, padx=15, pady=(15, 5), sticky="w")

        llm_list = list_available_llms()
        self.llm_options = [llm.name for llm in llm_list] if llm_list else ["No LLMs configured"]
        self.llm_map = {llm.name: llm.id for llm in llm_list} if llm_list else {}

        self.llm_dropdown = ctk.CTkOptionMenu(
            options_frame, values=self.llm_options,
            fg_color=theme.colors.bg_medium, width=200
        )
        self.llm_dropdown.set(self.llm_options[0])
        self.llm_dropdown.grid(row=1, column=1, padx=15, pady=(0, 10), sticky="w")

        # Story Mode is now always Assembly (removed standard/enhanced dropdown)
        # Assembly mode uses 7 parallel proposal agents + 5 judges for consensus

        # Visual Style selector
        style_label = ctk.CTkLabel(
            options_frame, text="Visual Style:",
            text_color=theme.colors.text_primary, anchor="w"
        )
        style_label.grid(row=2, column=0, padx=15, pady=(5, 5), sticky="w")

        self.VISUAL_STYLE_OPTIONS = [
            "Live Action",
            "Anime",
            "2D Animation",
            "3D Animation",
            "Mixed Reality"
        ]
        self.VISUAL_STYLE_MAP = {
            "Live Action": "live_action",
            "Anime": "anime",
            "2D Animation": "animation_2d",
            "3D Animation": "animation_3d",
            "Mixed Reality": "mixed_reality"
        }

        self.style_dropdown = ctk.CTkOptionMenu(
            options_frame, values=self.VISUAL_STYLE_OPTIONS,
            fg_color=theme.colors.bg_medium, width=200
        )

        # Load existing visual style if available, otherwise default to Live Action
        existing_visual_style = self._load_existing_visual_style()
        if existing_visual_style:
            # Map the loaded style back to display name
            reverse_map = {v: k for k, v in self.VISUAL_STYLE_MAP.items()}
            display_name = reverse_map.get(existing_visual_style, self.VISUAL_STYLE_OPTIONS[0])
            self.style_dropdown.set(display_name)
        else:
            self.style_dropdown.set(self.VISUAL_STYLE_OPTIONS[0])  # Default to Live Action

        self.style_dropdown.grid(row=3, column=0, padx=15, pady=(0, 10), sticky="w")

        # Load existing style notes first to determine label text
        existing_style_notes = self._load_existing_style_notes()
        has_existing_notes = bool(existing_style_notes.strip())

        # Style Notes label - indicate if loading existing content
        label_text = "Style Notes (edit existing):" if has_existing_notes else "Style Notes (optional):"
        style_notes_label = ctk.CTkLabel(
            options_frame, text=label_text,
            text_color=theme.colors.accent if has_existing_notes else theme.colors.text_primary,
            anchor="w"
        )
        style_notes_label.grid(row=2, column=1, padx=15, pady=(5, 5), sticky="w")

        # Style Notes text entry
        self.style_notes_entry = ctk.CTkTextbox(
            options_frame, height=50, width=200, wrap="word",
            fg_color=theme.colors.bg_medium,
            text_color=theme.colors.text_primary
        )
        self.style_notes_entry.grid(row=3, column=1, padx=15, pady=(0, 10), sticky="w")

        # Insert existing style notes
        if existing_style_notes:
            self.style_notes_entry.insert("1.0", existing_style_notes)

        # === PROGRESS SECTION (shown after running) ===
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Don't pack yet - will be shown when running

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=400)
        self.progress_bar.pack(pady=(20, 10))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            self.progress_frame, text="Starting...",
            text_color=theme.colors.text_muted
        )
        self.progress_label.pack(pady=5)

        # Log area - larger view when shown
        self.log_text = ctk.CTkTextbox(
            self.progress_frame, height=250, wrap="word",
            fg_color=theme.colors.bg_dark,
            text_color=theme.colors.text_secondary
        )
        self.log_text.pack(fill="both", expand=True, padx=15, pady=10)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(0, 20))
        btn_frame.grid_columnconfigure(1, weight=1)

        self.btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color="transparent", border_width=1,
            border_color=theme.colors.border,
            command=self._on_cancel
        )
        self.btn_cancel.grid(row=0, column=0)

        # Self-Fix button (hidden initially, shown after pipeline completion)
        self.btn_self_fix = ctk.CTkButton(
            btn_frame, text="🔧 Self-Fix", width=100,
            fg_color=theme.colors.warning if hasattr(theme.colors, 'warning') else "#E67E22",
            hover_color=theme.colors.warning_hover if hasattr(theme.colors, 'warning_hover') else "#D35400",
            command=self._on_self_fix
        )
        # Don't grid yet - will be shown after completion
        self._self_fix_visible = False

        self.btn_run = ctk.CTkButton(
            btn_frame, text="Run Writer", width=120,
            fg_color=theme.colors.accent,
            hover_color=theme.colors.accent_hover,
            command=self._on_run
        )
        self.btn_run.grid(row=0, column=2)

    def _load_pitch_content(self) -> str:
        """Load pitch content from project."""
        pitch_path = self.project_path / "world_bible" / "pitch.md"
        if pitch_path.exists():
            try:
                content = pitch_path.read_text(encoding="utf-8").strip()
                # Truncate for preview if too long
                if len(content) > 500:
                    return content[:500] + "..."
                return content
            except Exception:
                return "Error reading pitch file."
        return ""

    def _load_pitch_structured(self) -> Dict[str, str]:
        """Load and parse pitch.md into structured fields."""
        pitch_path = self.project_path / "world_bible" / "pitch.md"
        result = {"title": "", "logline": "", "genre": "", "synopsis": "", "characters": "", "locations": ""}

        if not pitch_path.exists():
            return result

        try:
            content = pitch_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            current_section = None
            section_content = []

            for line in lines:
                stripped = line.strip()
                # Check for title (# Title)
                if stripped.startswith("# ") and not stripped.startswith("## "):
                    result["title"] = stripped[2:].strip()
                # Check for section headers
                elif stripped.startswith("## "):
                    # Save previous section
                    if current_section and section_content:
                        result[current_section] = "\n".join(section_content).strip()
                    # Start new section
                    header = stripped[3:].strip().lower()
                    if header == "logline":
                        current_section = "logline"
                    elif header == "genre":
                        current_section = "genre"
                    elif header == "synopsis":
                        current_section = "synopsis"
                    elif header == "characters":
                        current_section = "characters"
                    elif header == "locations":
                        current_section = "locations"
                    else:
                        current_section = None
                    section_content = []
                elif current_section:
                    section_content.append(line)

            # Save last section
            if current_section and section_content:
                result[current_section] = "\n".join(section_content).strip()

        except Exception:
            pass

        return result

    def _save_pitch_from_fields(self) -> str:
        """Build pitch content from UI fields and save to pitch.md."""
        title = self.pitch_title_entry.get().strip()
        logline = self.pitch_logline_entry.get().strip()
        genre = self.pitch_genre_entry.get().strip()
        characters = self.pitch_characters_entry.get().strip()
        locations = self.pitch_locations_entry.get().strip()
        synopsis = self.pitch_synopsis_entry.get("1.0", "end-1c").strip()

        # Build markdown content
        lines = []
        lines.append(f"# {title}" if title else "# Untitled Project")
        lines.append("")
        lines.append("## Logline")
        lines.append(logline if logline else "(No logline provided)")
        lines.append("")
        lines.append("## Genre")
        lines.append(genre if genre else "(No genre specified)")
        lines.append("")
        if characters:
            lines.append("## Characters")
            lines.append(characters)
            lines.append("")
        if locations:
            lines.append("## Locations")
            lines.append(locations)
            lines.append("")
        lines.append("## Type")
        lines.append("Single Project")
        lines.append("")
        lines.append("## Synopsis")
        lines.append(synopsis if synopsis else "(No synopsis provided)")
        lines.append("")

        content = "\n".join(lines)

        # Save to pitch.md
        pitch_path = self.project_path / "world_bible" / "pitch.md"
        pitch_path.parent.mkdir(parents=True, exist_ok=True)
        pitch_path.write_text(content, encoding="utf-8")

        return content

    def _on_synopsis_key(self, event=None) -> None:
        """Handle key release in synopsis to detect @-mentions."""
        import re
        text = self.pitch_synopsis_entry.get("1.0", "end-1c")

        # Find @-mentions: @Name or @FirstName_LastName
        mentions = re.findall(r'@([A-Za-z][A-Za-z0-9_]*)', text)

        if mentions:
            # Convert to tag format
            tags = [f"[CHAR_{name.upper()}]" for name in set(mentions)]
            self.tag_preview_text.configure(
                text=f"Detected: {', '.join(sorted(tags))}",
                text_color=theme.colors.accent
            )
        else:
            self.tag_preview_text.configure(
                text="Tip: Use @Name in synopsis to auto-detect character tags",
                text_color=theme.colors.text_muted
            )

    def _load_existing_style_notes(self) -> str:
        """Load existing style notes from world_config.json (single source of truth)."""
        world_config_path = self.project_path / "world_bible" / "world_config.json"
        if not world_config_path.exists():
            return ""

        try:
            config = json.loads(world_config_path.read_text(encoding="utf-8"))
            return config.get("style_notes", "")
        except Exception as e:
            logger.warning(f"Could not load existing style notes: {e}")
            return ""

    def _load_existing_visual_style(self) -> Optional[str]:
        """Load existing visual style from world_config.json (single source of truth)."""
        world_config_path = self.project_path / "world_bible" / "world_config.json"
        if not world_config_path.exists():
            return None

        try:
            config = json.loads(world_config_path.read_text(encoding="utf-8"))
            return config.get("visual_style", None)
        except Exception as e:
            logger.warning(f"Could not load existing visual style: {e}")
            return None

    def _load_existing_lighting(self) -> str:
        """Load existing lighting from world_config.json (single source of truth)."""
        world_config_path = self.project_path / "world_bible" / "world_config.json"
        if not world_config_path.exists():
            return ""

        try:
            config = json.loads(world_config_path.read_text(encoding="utf-8"))
            return config.get("lighting", "")
        except Exception as e:
            logger.warning(f"Could not load existing lighting: {e}")
            return ""

    def _load_existing_vibe(self) -> str:
        """Load existing vibe from world_config.json (single source of truth)."""
        world_config_path = self.project_path / "world_bible" / "world_config.json"
        if not world_config_path.exists():
            return ""

        try:
            config = json.loads(world_config_path.read_text(encoding="utf-8"))
            return config.get("vibe", "")
        except Exception as e:
            logger.warning(f"Could not load existing vibe: {e}")
            return ""

    def _check_existing_world_config(self) -> Optional[set]:
        """Check for existing world config and show preserve dialog if found.

        Returns:
            Set of tags to preserve, empty set to regenerate all, or None if cancelled.
        """
        from greenlight.ui.dialogs.world_bible_preserve_dialog import WorldBiblePreserveDialog

        world_config_path = self.project_path / "world_bible" / "world_config.json"

        if not world_config_path.exists():
            # No existing config, proceed with fresh generation
            return set()

        try:
            config = json.loads(world_config_path.read_text(encoding="utf-8"))
            # Check if there are any elements to preserve
            has_characters = bool(config.get("characters", []))
            has_locations = bool(config.get("locations", []))
            has_props = bool(config.get("props", []))

            if not (has_characters or has_locations or has_props):
                # Config exists but has no elements
                return set()

            # Show preserve dialog
            dialog = WorldBiblePreserveDialog(self, self.project_path)
            return dialog.get_preserved_tags()

        except Exception as e:
            logger.warning(f"Could not check existing world config: {e}")
            return set()

    def _run_background_pipeline(self) -> None:
        """Run pipeline immediately in background (no UI, called when auto_run=True)."""
        self.running = True
        self.cancelled.clear()
        self.preserved_tags = set()  # No preservation in auto mode

        # Use auto parameters
        llm_id = self.auto_llm
        llm_id_config = llm_id.replace("-", "_")
        media_type = self.auto_media_type
        visual_style = self.auto_visual_style
        style_notes = ""

        self._log(f"🤖 Auto-running Writer Pipeline...")
        self._log(f"  → LLM: {llm_id}")
        self._log(f"  → Media Type: {media_type}")
        self._log(f"  → Visual Style: {visual_style}")

        def run_pipeline():
            try:
                import json
                from greenlight.pipelines.story_pipeline import StoryPipeline, StoryInput
                from greenlight.llm import LLMManager
                from greenlight.tags import TagRegistry
                from greenlight.core.config import GreenlightConfig, FunctionLLMMapping, get_config
                from greenlight.core.constants import LLMFunction
                from datetime import datetime

                # Enable self-correction for missing characters
                try:
                    from greenlight.core.logging_config import enable_self_correction
                    enable_self_correction(project_path=self.project_path, auto_fix=True)
                    self._log("🔧 Self-correction enabled for missing characters")
                except Exception as e:
                    self._log(f"⚠️ Could not enable self-correction: {e}")

                self._log("📖 Starting Assembly Story Pipeline...")
                self._update_progress(0.05)

                # Load pitch
                pitch_path = self.project_path / "world_bible" / "pitch.md"
                if pitch_path.exists():
                    pitch_content = pitch_path.read_text(encoding="utf-8")
                    self._log(f"✓ Loaded pitch ({len(pitch_content)} chars)")
                else:
                    self._log("⚠ No pitch found")
                    pitch_content = ""

                # Load project config
                config_path = self.project_path / "project.json"
                project_config = {}
                if config_path.exists():
                    project_config = json.loads(config_path.read_text(encoding="utf-8"))

                self._update_progress(0.1)

                # Initialize pipeline with selected LLM
                self._log("🔧 Initializing pipeline...")
                base_config = get_config()
                custom_config = GreenlightConfig()
                custom_config.llm_configs = base_config.llm_configs.copy()
                custom_config.function_mappings = {}

                selected_config = custom_config.llm_configs.get(llm_id_config)
                if not selected_config:
                    self._log(f"⚠️ LLM '{llm_id_config}' not found, using first available")
                    selected_config = next(iter(custom_config.llm_configs.values()))

                for function in LLMFunction:
                    custom_config.function_mappings[function] = FunctionLLMMapping(
                        function=function,
                        primary_config=selected_config,
                        fallback_config=None
                    )

                self._log(f"  ✓ Using LLM: {selected_config.model}")
                llm_manager = LLMManager(custom_config)
                tag_registry = TagRegistry()
                story_pipeline = StoryPipeline(
                    llm_manager=llm_manager,
                    tag_registry=tag_registry,
                    project_path=str(self.project_path)
                )

                self._update_progress(0.15)

                # Create input - StoryInput uses raw_text, not pitch
                story_input = StoryInput(
                    raw_text=pitch_content,
                    title=project_config.get("name", "Untitled"),
                    genre=project_config.get("genre", "Drama"),
                    visual_style=visual_style,
                    style_notes=style_notes,
                    project_size=media_type if media_type in ["micro", "short", "medium", "feature"] else "short"
                )

                # Run pipeline
                self._log("🚀 Running story generation...")
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(story_pipeline.run(story_input))
                finally:
                    loop.close()

                if result.success and result.output:
                    self._update_progress(0.9)
                    self._log("💾 Saving outputs...")
                    # Load project config for saving
                    project_config = {}
                    config_path = self.project_path / "project.json"
                    if config_path.exists():
                        project_config = json.loads(config_path.read_text(encoding="utf-8"))
                    self._save_pipeline_outputs(result.output, project_config, set())
                    self._update_progress(1.0)
                    self._log("✅ Writer pipeline complete!")

                    if self.on_complete:
                        self.on_complete({"success": True})
                else:
                    self._log(f"❌ Pipeline failed: {result.error}")

            except Exception as e:
                logger.exception("Background writer pipeline error")
                self._log(f"❌ Error: {e}")
            finally:
                self.running = False
                try:
                    self.after(100, self.destroy)
                except:
                    pass

        # Run in thread
        self.executor.submit(run_pipeline)

    def _on_run(self) -> None:
        """Start the writer pipeline using the selected pipeline mode."""
        # Save pitch from UI fields before running
        self._save_pitch_from_fields()

        # Check for existing world config and show preserve dialog
        preserved_tags = self._check_existing_world_config()
        if preserved_tags is None:
            # User cancelled
            return

        # Store preserved tags for pipeline use
        self.preserved_tags = preserved_tags

        self.running = True
        self.btn_run.configure(state="disabled")
        self.cancelled.clear()

        # IMPORTANT: Capture ALL UI values BEFORE potentially destroying the dialog
        selected_size = self.size_dropdown.get()
        size_key = "standard"  # default
        media_type = "standard"
        for key, val in self.PROJECT_PRESETS.items():
            if val["name"] == selected_size:
                size_key = key
                media_type = val.get("media_type", "standard")
                break

        # Story mode is always assembly (7 parallel agents + 5 judges)
        use_assembly = True

        # Directing mode is always scene-based (removed dropdown)
        protocol_key = "scene_chunked"

        selected_llm = self.llm_dropdown.get()
        llm_id = self.llm_map.get(selected_llm, "claude-sonnet")
        # Convert hyphenated ID to underscored ID for config compatibility
        llm_id_config = llm_id.replace("-", "_")

        # Get visual style and style notes from UI (capture before destroy)
        selected_style = self.style_dropdown.get()
        visual_style = self.VISUAL_STYLE_MAP.get(selected_style, "live_action")
        style_notes = self.style_notes_entry.get("1.0", "end-1c").strip()

        # If close_on_start, close dialog immediately and run in background
        if self.close_on_start:
            # Destroy the dialog - pipeline will run in background thread
            self.grab_release()
            self.destroy()
        else:
            # Switch from config view to progress view
            self.config_frame.pack_forget()
            self.progress_frame.pack(fill="both", expand=True, padx=30, pady=10)

        def run_pipeline():
            try:
                # Enable self-correction for missing characters
                try:
                    from greenlight.core.logging_config import enable_self_correction
                    enable_self_correction(project_path=self.project_path, auto_fix=True)
                    self._log("🔧 Self-correction enabled for missing characters")
                except Exception as e:
                    self._log(f"⚠️ Could not enable self-correction: {e}")

                self._log("📖 Starting Assembly Story Pipeline...")
                self._log(f"  → Using 7 parallel agents + 5 judges consensus")
                self._log(f"  → Media Type: {media_type}")
                self._update_progress(0.05)

                # Load pitch
                pitch_path = self.project_path / "world_bible" / "pitch.md"
                if pitch_path.exists():
                    pitch_content = pitch_path.read_text(encoding="utf-8")
                    self._log(f"✓ Loaded pitch ({len(pitch_content)} chars)")
                else:
                    self._log("⚠ No pitch found, using empty pitch")
                    pitch_content = ""

                # Load project config for genre/title
                config_path = self.project_path / "project.json"
                project_config = {}
                if config_path.exists():
                    project_config = json.loads(config_path.read_text(encoding="utf-8"))

                self._update_progress(0.1)

                # Initialize pipeline components with selected LLM
                self._log("🔧 Initializing pipeline...")
                self._log(f"  → Selected LLM: {selected_llm}")

                # Create custom config with selected LLM (Option 2)
                from greenlight.core.config import GreenlightConfig, FunctionLLMMapping, get_config
                from greenlight.core.constants import LLMFunction

                base_config = get_config()
                custom_config = GreenlightConfig()
                custom_config.llm_configs = base_config.llm_configs.copy()
                custom_config.function_mappings = {}

                # Get selected LLM config (use underscored ID for config lookup)
                selected_config = custom_config.llm_configs.get(llm_id_config)
                if not selected_config:
                    self._log(f"⚠️ LLM '{llm_id_config}' not found in config, using first available")
                    selected_config = next(iter(custom_config.llm_configs.values()))

                # Override all function mappings to use selected LLM
                for function in LLMFunction:
                    custom_config.function_mappings[function] = FunctionLLMMapping(
                        function=function,
                        primary_config=selected_config,
                        fallback_config=None  # Could add fallback logic here
                    )

                self._log(f"  ✓ Using LLM: {selected_config.model}")
                self._log("  → Creating LLM Manager with custom config...")
                llm_manager = LLMManager(custom_config)

                self._log("  → Loading Tag Registry...")
                tag_registry = TagRegistry()
                self._log("  → Creating Story Pipeline...")
                story_pipeline = StoryPipeline(
                    llm_manager=llm_manager,
                    tag_registry=tag_registry,
                    project_path=str(self.project_path)
                )

                # Set up progress callback for detailed logging
                def progress_callback(progress_data):
                    step_name = progress_data.get('step', '')
                    current = progress_data.get('current', 0)
                    total = progress_data.get('total', 0)
                    percent = progress_data.get('percent', 0)

                    # Map step names to friendly descriptions (updated for 4-layer)
                    step_descriptions = {
                        'parse_input': '📋 Parsing input and configuration',
                        'extract_tags': '🏷️  Extracting tags with multi-agent consensus',
                        'plot_architecture': '🏗️  Layer 1: Building plot architecture',
                        'character_architecture': '👥 Layer 2: Developing character arcs',
                        'continuity_validation': '🔍 Layer 3: Validating continuity',
                        'motivational_coherence': '🎭 Layer 4: Checking motivational coherence',
                        'assemble_output': '📦 Assembling final output',
                    }

                    description = step_descriptions.get(step_name, step_name)
                    self._log(f"[{current}/{total}] {description}")
                    self._update_progress(percent / 100.0)

                story_pipeline.set_progress_callback(progress_callback)

                # Set up logging handler to capture pipeline logs
                pipeline_logger = logging.getLogger('pipelines')
                log_handler = TextboxLogHandler(self.log_text, self._log)
                log_handler.setLevel(logging.INFO)
                pipeline_logger.addHandler(log_handler)

                # Create story input (visual_style and style_notes captured before dialog close)
                story_input = StoryInput(
                    raw_text=pitch_content,
                    title=project_config.get("name", "Untitled"),
                    genre=project_config.get("genre", ""),
                    visual_style=visual_style,
                    style_notes=style_notes,
                    project_size=size_key
                )

                self._update_progress(0.15)

                # Run the async pipeline
                async def run_async_pipeline():
                    try:
                        # Execute pipeline with run() method (returns PipelineResult)
                        pipeline_result = await story_pipeline.run(story_input)
                        return pipeline_result
                    finally:
                        # Remove the log handler when done
                        pipeline_logger.removeHandler(log_handler)

                # Run async in thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    if self.cancelled.is_set():
                        return

                    self._log("🏗️ Running Assembly-based story building...")
                    pipeline_result = loop.run_until_complete(run_async_pipeline())

                    # Check if pipeline succeeded
                    if not pipeline_result.success:
                        self._log(f"❌ Pipeline failed: {pipeline_result.error}")
                        self.after(0, lambda: self.btn_run.configure(state="normal"))
                        return

                    result: StoryOutput = pipeline_result.output
                    self._update_progress(0.8)
                    self._log(f"✓ Story pipeline complete: {len(result.beats)} beats, {len(result.scenes)} scenes")

                    # Save story outline outputs
                    if not self.cancelled.is_set():
                        self._save_pipeline_outputs(result, project_config, preserved_tags)

                    self._update_progress(0.95)

                finally:
                    loop.close()

                self._update_progress(1.0)
                self._log("✅ Writer pipeline complete!")
                self._log("💡 Run the Director pipeline separately to generate storyboard prompts.")

                if self.on_complete and not self.cancelled.is_set():
                    if self._is_widget_valid():
                        self.after(500, lambda: self._complete())
                    else:
                        # Dialog was closed, call on_complete directly
                        self.on_complete({"project_path": str(self.project_path)})

            except Exception as e:
                logger.exception("Pipeline error")
                self._log(f"❌ Error: {e}")
                if self._is_widget_valid():
                    self.after(0, lambda: self.btn_run.configure(state="normal"))

        self.executor.submit(run_pipeline)

    def _save_pipeline_outputs(self, result: StoryOutput, project_config: Dict, preserved_tags: set = None) -> None:
        """Save all pipeline outputs to project files."""
        if preserved_tags is None:
            preserved_tags = set()
        self._log("💾 Saving outputs...")

        # Determine if series or single project
        is_series = project_config.get("type") == "series"

        if is_series:
            # Save to first episode
            base_path = self.project_path / "SEASON_01" / "EPISODE_01"
        else:
            base_path = self.project_path

        # 1. Save story outline (scenes and beats as markdown) - input for Directing Pipeline
        self._log("📝 Saving Script...")
        story_md = self._format_story_document(result)
        script_path = base_path / "scripts" / "script.md"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(story_md, encoding="utf-8")

        # 2. Save world config (characters, locations, props with full descriptions)
        self._log("🌍 Saving world config...")

        import logging
        logger = logging.getLogger(__name__)

        # VALIDATION: Compare consensus-approved character tags against character_arcs
        # This catches any characters that were approved but didn't get arcs generated
        char_arc_tags = {arc.character_tag for arc in result.character_arcs}
        consensus_char_tags = {t for t in result.all_tags if t.startswith('CHAR_')}
        missing_chars = consensus_char_tags - char_arc_tags

        if missing_chars:
            logger.warning(f"⚠️ VALIDATION WARNING: Consensus-approved characters missing from character_arcs:")
            for tag in sorted(missing_chars):
                logger.warning(f"   • [{tag}] - approved by consensus but has no CharacterArc")
            self._log(f"⚠️ Warning: {len(missing_chars)} character(s) approved by consensus but missing arcs: {missing_chars}")
        else:
            logger.info(f"✅ Validation passed: All {len(consensus_char_tags)} consensus-approved characters have arcs")

        # Load existing world_config to preserve user-edited fields
        world_path = self.project_path / "world_bible" / "world_config.json"
        existing_config = {}
        if world_path.exists():
            try:
                existing_config = json.loads(world_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        world_config = {
            # Project overview (from project.json - user setup, or generated by agents)
            "title": project_config.get("name", result.title),
            "logline": result.logline or existing_config.get("logline") or project_config.get("logline", ""),
            "genre": result.genre or existing_config.get("genre") or project_config.get("genre", ""),
            "synopsis": result.synopsis or existing_config.get("synopsis", ""),

            # Lore (generated by agents)
            "themes": result.themes or existing_config.get("themes", ""),
            "world_rules": result.world_rules or existing_config.get("world_rules", ""),

            # Style Core (from user selection in dialog + generated lighting/vibe)
            "visual_style": result.visual_style,
            "style_notes": result.style_notes,
            "lighting": result.lighting or existing_config.get("lighting", ""),
            "vibe": result.vibe or existing_config.get("vibe", ""),

            # Characters, Locations, Props - merge preserved with newly generated
            "characters": self._merge_preserved_characters(
                result.character_arcs, existing_config, preserved_tags
            ),
            "locations": self._merge_preserved_locations(
                result.location_descriptions, result.location_tags, existing_config, preserved_tags
            ),
            "props": self._merge_preserved_props(
                result.prop_descriptions, existing_config, preserved_tags
            ),
            "all_tags": result.all_tags,
            "generated": datetime.now().isoformat()
        }
        world_path = self.project_path / "world_bible" / "world_config.json"
        world_path.write_text(json.dumps(world_config, indent=2), encoding="utf-8")

        # 2b. Save style guide
        self._log("🎨 Saving style guide...")
        style_guide_content = f"""# Style Guide

## Visual Style
**Type:** {result.visual_style}

## Style Notes
{result.style_notes if result.style_notes else "No custom style notes provided."}

## Generated
{datetime.now().isoformat()}
"""
        style_path = self.project_path / "world_bible" / "style_guide.md"
        style_path.write_text(style_guide_content, encoding="utf-8")

        # 3. Save beat sheet
        self._log("🎬 Saving beat sheet...")
        beats_data = {
            "beats": [
                {
                    "beat_id": beat.beat_id,
                    "scene_number": beat.scene_number,
                    "beat_number": beat.beat_number,
                    "content": beat.content,
                    "tags": beat.tags,
                    "beat_type": beat.beat_type,
                    "emotional_arc": beat.emotional_arc,
                    "camera_suggestion": beat.camera_suggestion,
                    "character_tags": beat.character_tags,
                    "location_tag": beat.location_tag,
                    "prop_tags": beat.prop_tags,
                    "direction": beat.direction
                }
                for beat in result.beats
            ],
            "total_beats": len(result.beats),
            "generated": datetime.now().isoformat()
        }
        beats_path = base_path / "beats" / "beat_sheet.json"
        beats_path.parent.mkdir(parents=True, exist_ok=True)
        beats_path.write_text(json.dumps(beats_data, indent=2), encoding="utf-8")

        # 4. Save plot structure
        self._log("📊 Saving plot structure...")
        plot_data = {
            "plot_points": [
                {
                    "point_id": pp.point_id,
                    "act": pp.act,
                    "position": pp.position,
                    "type": pp.point_type,
                    "description": pp.description
                }
                for pp in result.plot_points
            ],
            "act_structure": {str(k): v for k, v in result.act_structure.items()},
            "generated": datetime.now().isoformat()
        }
        plot_path = base_path / "beats" / "plot_structure.json"
        plot_path.write_text(json.dumps(plot_data, indent=2), encoding="utf-8")

        # 5. Save validation reports
        if result.continuity_issues:
            self._log("⚠️ Saving continuity report...")
            continuity_data = {
                "status": result.continuity_status.value,
                "issues": [
                    {"id": i.issue_id, "severity": i.severity, "category": i.category,
                     "description": i.description, "fix": i.suggested_fix}
                    for i in result.continuity_issues
                ]
            }
            report_path = base_path / "beats" / "continuity_report.json"
            report_path.write_text(json.dumps(continuity_data, indent=2), encoding="utf-8")

        self._log(f"✓ All outputs saved to {base_path}")

    def _merge_preserved_characters(
        self, new_arcs: list, existing_config: Dict, preserved_tags: set
    ) -> list:
        """Merge preserved characters with newly generated ones.

        Saves ALL rich character fields from CharacterArc including:
        - Visual: appearance, costume, age, ethnicity
        - Psychological: psychology, speech_patterns, physicality, decision_heuristics
        - Voice: speech_style, literacy_level
        - Emotional: emotional_tells dict
        - Arc: want, need, flaw, arc_type, key_moments, relationships
        """
        import logging
        logger = logging.getLogger(__name__)

        result = []
        preserved_chars = {c.get("tag"): c for c in existing_config.get("characters", [])}
        new_chars_by_tag = {arc.character_tag: arc for arc in new_arcs}

        # DIAGNOSTIC LOGGING: Log character merge operation
        logger.info(f"📝 Character Merge - {len(new_arcs)} new arcs, {len(preserved_tags)} preserved tags")
        logger.info(f"   New arc tags: {[arc.character_tag for arc in new_arcs]}")
        logger.info(f"   Preserved character tags: {[t for t in preserved_tags if t.startswith('CHAR_')]}")

        # Add preserved characters first
        for tag in preserved_tags:
            if tag.startswith("CHAR_") and tag in preserved_chars:
                result.append(preserved_chars[tag])
                logger.info(f"   ✓ Preserved existing character: [{tag}]")

        # Add newly generated characters (non-preserved) with ALL rich fields
        for arc in new_arcs:
            if arc.character_tag not in preserved_tags:
                char_data = {
                    # Core identity
                    "tag": arc.character_tag,
                    "name": arc.character_name,
                    "role": arc.role,

                    # Character arc
                    "want": arc.want,
                    "need": arc.need,
                    "flaw": arc.flaw,
                    "arc_type": arc.arc_type,

                    # Visual description (RICH - multi-paragraph)
                    "age": arc.age,
                    "ethnicity": arc.ethnicity,
                    "appearance": arc.appearance,  # 50-100 words
                    "costume": arc.costume,  # 30-50 words
                    # Also save as visual_appearance for ContextEngine compatibility
                    "visual_appearance": arc.appearance,

                    # Psychological profile (NEW)
                    "psychology": getattr(arc, 'psychology', ''),

                    # Voice and speech (NEW)
                    "speech_patterns": getattr(arc, 'speech_patterns', ''),
                    "speech_style": getattr(arc, 'speech_style', ''),
                    "literacy_level": getattr(arc, 'literacy_level', ''),

                    # Physicality (NEW)
                    "physicality": getattr(arc, 'physicality', ''),

                    # Decision making (NEW)
                    "decision_heuristics": getattr(arc, 'decision_heuristics', ''),

                    # Emotional tells (NEW - dict with emotion -> physical response)
                    "emotional_tells": getattr(arc, 'emotional_tells', {}),

                    # Relationships and key moments
                    "key_moments": getattr(arc, 'key_moments', []),
                    "relationships": getattr(arc, 'relationships', {})
                }
                result.append(char_data)
                logger.info(f"   ✓ Added new character: [{arc.character_tag}] - {arc.character_name}")

        # Final summary
        logger.info(f"✅ Character merge complete: {len(result)} characters will be written to world_config.json")
        for char in result:
            logger.info(f"   • [{char.get('tag')}] - {char.get('name')}")

        return result

    def _merge_preserved_locations(
        self, new_locs: list, location_tags: list, existing_config: Dict, preserved_tags: set
    ) -> list:
        """Merge preserved locations with newly generated ones."""
        result = []
        preserved_locs = {l.get("tag"): l for l in existing_config.get("locations", [])}

        # Add preserved locations first
        for tag in preserved_tags:
            if tag.startswith("LOC_") and tag in preserved_locs:
                result.append(preserved_locs[tag])

        # Add newly generated locations (non-preserved)
        if new_locs:
            for loc in new_locs:
                if loc.location_tag not in preserved_tags:
                    result.append({
                        "tag": loc.location_tag,
                        "name": loc.location_name,
                        "description": loc.description,
                        "time_period": loc.time_period,
                        "atmosphere": loc.atmosphere,
                        "directional_views": {
                            "north": loc.view_north,
                            "east": loc.view_east,
                            "south": loc.view_south,
                            "west": loc.view_west
                        }
                    })
        else:
            # Fallback for tags without descriptions
            for tag in location_tags:
                if tag not in preserved_tags:
                    result.append({"tag": tag})

        return result

    def _merge_preserved_props(
        self, new_props: list, existing_config: Dict, preserved_tags: set
    ) -> list:
        """Merge preserved props with newly generated ones."""
        result = []
        preserved_props = {p.get("tag"): p for p in existing_config.get("props", [])}

        # Add preserved props first
        for tag in preserved_tags:
            if tag.startswith("PROP_") and tag in preserved_props:
                result.append(preserved_props[tag])

        # Add newly generated props (non-preserved)
        if new_props:
            for prop in new_props:
                if prop.prop_tag not in preserved_tags:
                    result.append({
                        "tag": prop.prop_tag,
                        "name": prop.prop_name,
                        "description": prop.description,
                        "appearance": prop.appearance,
                        "significance": prop.significance,
                        "associated_character": prop.associated_character
                    })

        return result

    def _format_story_document(self, result: StoryOutput) -> str:
        """Format the story output as a markdown document."""
        lines = [
            f"# {result.title}",
            f"\n**Genre:** {result.genre}",
            f"\n**Generated:** {datetime.now().isoformat()}",
            f"\n**Summary:** {result.summary}",
            "\n---\n",
        ]

        # Add scenes
        for scene in result.scenes:
            lines.append(f"\n## Scene {scene.scene_number}: {scene.location_description}")
            lines.append(f"\n**Location:** [{scene.location_tag}]")
            lines.append(f"**Time:** {scene.time_of_day}")
            lines.append(f"**Characters:** {', '.join(f'[{c}]' for c in scene.characters_present)}")
            lines.append(f"**Purpose:** {scene.purpose}")
            lines.append(f"**Emotional Beat:** {scene.emotional_beat}")
            lines.append("")

            # Add beats
            for beat in scene.beats:
                lines.append(f"### Beat {beat.beat_number}")
                lines.append(f"\n{beat.content}")
                lines.append("")

                # Add detailed tag breakdown
                lines.append("**Beat Details:**")
                if beat.character_tags:
                    lines.append(f"- Characters: {', '.join(f'[{t}]' for t in beat.character_tags)}")
                if beat.location_tag:
                    lines.append(f"- Location: [{beat.location_tag}]")
                if beat.prop_tags:
                    lines.append(f"- Props: {', '.join(f'[{t}]' for t in beat.prop_tags)}")
                if beat.direction:
                    lines.append(f"- Direction: {beat.direction}")
                if beat.camera_suggestion:
                    lines.append(f"- Camera: {beat.camera_suggestion}")
                if beat.emotional_arc:
                    lines.append(f"- Emotional Arc: {beat.emotional_arc}")
                lines.append("")

        return "\n".join(lines)

    async def _run_directing_pipeline(
        self,
        story_result: StoryOutput,
        project_config: Dict,
        style_notes: str,
        media_type: str,
        protocol_key: str
    ) -> Optional[Dict]:
        """Run the directing pipeline to add frame notations to the script."""
        from greenlight.pipelines.directing_pipeline import DirectingPipeline, DirectingInput
        from greenlight.pipelines.procedural_generation import (
            ProceduralGenerator, GenerationProtocol, ScriptOutline, Scene, Beat, BeatType
        )
        from greenlight.config.word_caps import get_output_budget

        try:
            # Build character registry from story result
            character_registry = {}
            for arc in story_result.character_arcs:
                character_registry[arc.character_tag] = {
                    'name': arc.character_name,
                    'role': arc.role,
                    'appearance': arc.appearance,
                    'costume': arc.costume,
                    'age': arc.age,
                    'ethnicity': arc.ethnicity,
                    'want': arc.want,
                    'need': arc.need,
                    'flaw': arc.flaw
                }

            # Build location registry from story result
            location_registry = {}
            if story_result.location_descriptions:
                for loc in story_result.location_descriptions:
                    location_registry[loc.location_tag] = {
                        'name': loc.location_name,
                        'description': loc.description,
                        'atmosphere': loc.atmosphere,
                        'views': {
                            'north': loc.view_north,
                            'east': loc.view_east,
                            'south': loc.view_south,
                            'west': loc.view_west
                        }
                    }

            # Get output budget for media type
            output_budget = get_output_budget(media_type)
            self._log(f"  → Output budget: {output_budget['total_words']} words, {output_budget['chunk_size']} per chunk")

            # Convert story scenes/beats to script outline for procedural generation
            script_scenes = []
            for scene in story_result.scenes:
                scene_beats = []
                for beat in scene.beats:
                    # Map beat type
                    beat_type = BeatType.ACTION
                    if beat.beat_type:
                        beat_type_map = {
                            'action': BeatType.ACTION,
                            'dialogue': BeatType.DIALOGUE,
                            'reaction': BeatType.REACTION,
                            'transition': BeatType.TRANSITION
                        }
                        beat_type = beat_type_map.get(beat.beat_type.lower(), BeatType.ACTION)

                    scene_beats.append(Beat(
                        beat_id=beat.beat_id,
                        beat_number=beat.beat_number,
                        content=beat.content,
                        beat_type=beat_type,
                        character_tags=beat.character_tags or [],
                        emotional_arc=beat.emotional_arc or ""
                    ))

                script_scenes.append(Scene(
                    scene_number=scene.scene_number,
                    location_tag=scene.location_tag,
                    time_of_day=scene.time_of_day,
                    characters_present=scene.characters_present,
                    purpose=scene.purpose,
                    beats=scene_beats
                ))

            script_outline = ScriptOutline(
                title=story_result.title,
                genre=story_result.genre,
                scenes=script_scenes,
                total_beats=len(story_result.beats)
            )

            # Determine generation protocol
            protocol_map = {
                'scene_chunked': GenerationProtocol.SCENE_CHUNKED,
                'beat_chunked': GenerationProtocol.BEAT_CHUNKED,
                'expansion': GenerationProtocol.EXPANSION
            }
            protocol = protocol_map.get(protocol_key, GenerationProtocol.SCENE_CHUNKED)

            # Set up progress callback
            def directing_progress(progress_data):
                step_name = progress_data.get('step', '')
                percent = progress_data.get('percent', 0)
                # Map progress from 0.65 to 0.95 range
                mapped_progress = 0.65 + (percent / 100.0) * 0.30
                self._update_progress(mapped_progress)
                self._log(f"  → Directing: {step_name}")

            # Run procedural generation
            self._log(f"  → Using {protocol.value} generation protocol...")
            generator = ProceduralGenerator()

            generated_chunks = await generator.generate(
                script_outline=script_outline,
                protocol=protocol,
                output_budget=output_budget,
                character_registry=character_registry,
                location_registry=location_registry,
                style_notes=style_notes,
                progress_callback=directing_progress
            )

            # Assemble visual script from generated chunks
            visual_script_content = self._assemble_visual_script(
                story_result, generated_chunks, style_notes
            )

            return {
                'visual_script': visual_script_content,
                'total_frames': len(generated_chunks),
                'total_words': sum(len(chunk.content.split()) for chunk in generated_chunks),
                'protocol_used': protocol.value,
                'media_type': media_type
            }

        except Exception as e:
            logger.exception("Directing pipeline error")
            self._log(f"⚠️ Directing error: {e}")
            return None

    def _assemble_visual_script(
        self,
        story_result: StoryOutput,
        generated_chunks: list,
        style_notes: str
    ) -> str:
        """Assemble the visual script from generated chunks."""
        lines = [
            f"# {story_result.title}",
            f"\n**Visual Script**",
            f"\n**Genre:** {story_result.genre}",
            f"\n**Generated:** {datetime.now().isoformat()}",
            f"\n**Style Notes:** {style_notes if style_notes else 'Default style'}",
            "\n---\n",
        ]

        current_scene = None
        for chunk in generated_chunks:
            # Add scene header if new scene
            if hasattr(chunk, 'scene_number') and chunk.scene_number != current_scene:
                current_scene = chunk.scene_number
                lines.append(f"\n## Scene {current_scene}")
                lines.append("")

            # Add frame notation and content
            if hasattr(chunk, 'frame_id'):
                lines.append(f"{{frame_{chunk.frame_id}}}")

            lines.append(chunk.content)
            lines.append("")

        return "\n".join(lines)

    def _save_directing_output(self, result: Dict, project_config: Dict) -> None:
        """Save directing output to visual_script.md."""
        self._log("🎬 Saving visual script...")

        # Determine if series or single project
        is_series = project_config.get("type") == "series"

        if is_series:
            base_path = self.project_path / "SEASON_01" / "EPISODE_01"
        else:
            base_path = self.project_path

        # Save the visual script
        script_path = base_path / "scripts" / "visual_script.md"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(result.get('visual_script', ''), encoding="utf-8")

        # Save directing metadata
        metadata = {
            'total_frames': result.get('total_frames', 0),
            'total_words': result.get('total_words', 0),
            'protocol_used': result.get('protocol_used', ''),
            'media_type': result.get('media_type', ''),
            'generated': datetime.now().isoformat()
        }
        metadata_path = base_path / "scripts" / "directing_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        self._log(f"✓ Visual script saved ({result.get('total_frames', 0)} frames, {result.get('total_words', 0)} words)")

    def _is_widget_valid(self) -> bool:
        """Check if the dialog widgets are still valid (not destroyed)."""
        try:
            return self.winfo_exists()
        except Exception:
            return False

    def _log(self, message: str) -> None:
        """Add a log message."""
        # Always send to external log if available
        if self.external_log:
            try:
                self.external_log(message)
            except Exception:
                pass

        # Update local UI if dialog is still open
        def update():
            if not self._is_widget_valid():
                return
            try:
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
                self.progress_label.configure(text=message)
            except Exception:
                pass  # Widget was destroyed
        if self._is_widget_valid():
            self.after(0, update)

    def _update_progress(self, value: float) -> None:
        """Update progress bar."""
        # Always send to external progress if available
        if self.external_progress:
            try:
                self.external_progress(value)
            except Exception:
                pass

        # Update local UI if dialog is still open
        def update():
            if not self._is_widget_valid():
                return
            try:
                self.progress_bar.set(value)
            except Exception:
                pass  # Widget was destroyed
        if self._is_widget_valid():
            self.after(0, update)

    def _complete(self) -> None:
        """Handle completion."""
        self.running = False
        if not self._is_widget_valid():
            return
        try:
            self.btn_run.configure(text="Done", state="normal", command=self.destroy)
            self.btn_cancel.configure(state="disabled")
            # Show Self-Fix button after completion
            if not self._self_fix_visible:
                self.btn_self_fix.grid(row=0, column=1, padx=10)
                self._self_fix_visible = True
        except Exception:
            pass  # Widget was destroyed

        if self.on_complete:
            self.on_complete({"project_path": str(self.project_path)})

    def _on_cancel(self) -> None:
        """Handle cancel."""
        if self.running:
            self.cancelled.set()
            self._log("⚠ Cancelling...")
        else:
            self.destroy()

    def _on_self_fix(self) -> None:
        """Handle Self-Fix button click - detect and fix missing characters."""
        import threading
        from greenlight.omni_mind.tool_executor import ToolExecutor

        self._log("\n🔍 Checking for missing consensus-approved characters...")

        # Disable button during operation
        self.btn_self_fix.configure(state="disabled", text="🔄 Checking...")

        def run_detection():
            try:
                executor = ToolExecutor(project_path=self.project_path)

                # Detect missing characters
                detection_result = executor.execute('detect_missing_characters')

                if not detection_result.success:
                    self.after(0, lambda: self._show_self_fix_result(
                        success=False,
                        message=f"Detection failed: {detection_result.error}"
                    ))
                    return

                missing_tags = detection_result.result.get("missing_tags", [])

                if not missing_tags:
                    self.after(0, lambda: self._show_self_fix_result(
                        success=True,
                        message="✅ All consensus-approved characters have profiles in world_config.json"
                    ))
                    return

                # Show confirmation dialog
                self.after(0, lambda: self._show_self_fix_confirmation(missing_tags))

            except Exception as e:
                self.after(0, lambda: self._show_self_fix_result(
                    success=False,
                    message=f"Error during detection: {str(e)}"
                ))

        threading.Thread(target=run_detection, daemon=True).start()

    def _show_self_fix_confirmation(self, missing_tags: list) -> None:
        """Show confirmation dialog for fixing missing characters."""
        from tkinter import messagebox

        # Estimate time: ~10 seconds per character with Gemini
        estimated_time = len(missing_tags) * 10
        time_str = f"{estimated_time} seconds" if estimated_time < 60 else f"{estimated_time // 60} min {estimated_time % 60} sec"

        tag_list = "\n".join([f"  • [{tag}]" for tag in missing_tags])

        message = (
            f"Found {len(missing_tags)} missing character(s):\n\n"
            f"{tag_list}\n\n"
            f"Estimated time: {time_str}\n"
            f"LLM: Gemini 2.5 Flash (with Claude fallback)\n\n"
            f"Generate profiles for these characters?"
        )

        result = messagebox.askyesno(
            "Self-Fix: Missing Characters",
            message,
            parent=self
        )

        if result:
            self._execute_self_fix(missing_tags)
        else:
            self._log("❌ Self-fix cancelled by user")
            self.btn_self_fix.configure(state="normal", text="🔧 Self-Fix")

    def _execute_self_fix(self, missing_tags: list) -> None:
        """Execute the self-fix process for missing characters."""
        import threading
        from greenlight.omni_mind.tool_executor import ToolExecutor
        from greenlight.omni_mind.process_monitor import get_character_watcher

        self.btn_self_fix.configure(state="disabled", text="🔄 Fixing...")
        self._log(f"\n🔧 Generating profiles for {len(missing_tags)} character(s)...")
        self._log(f"  → Using Gemini 2.5 Flash (with Claude fallback)")

        def run_fix():
            try:
                executor = ToolExecutor(project_path=self.project_path)

                # Execute fix with Gemini as primary LLM
                fix_result = executor.execute(
                    'fix_missing_characters',
                    missing_tags=missing_tags,
                    dry_run=False,
                    llm_provider="gemini",
                    llm_model="gemini-2.5-flash-preview-05-20"
                )

                # Log to self-healing history
                try:
                    watcher = get_character_watcher()
                    watcher._fix_history.append({
                        "timestamp": __import__('datetime').datetime.now().isoformat(),
                        "missing_tags": missing_tags,
                        "result": fix_result.result,
                        "success": fix_result.success,
                        "source": "manual_self_fix_button"
                    })
                except Exception:
                    pass

                if fix_result.success:
                    fixed_count = fix_result.result.get("fixed_count", 0)
                    fixed_tags = fix_result.result.get("fixed_tags", [])
                    errors = fix_result.result.get("errors", [])

                    self.after(0, lambda: self._show_self_fix_result(
                        success=True,
                        message=f"✅ Fixed {fixed_count}/{len(missing_tags)} character(s)",
                        details={
                            "fixed_tags": fixed_tags,
                            "errors": errors
                        }
                    ))
                else:
                    self.after(0, lambda: self._show_self_fix_result(
                        success=False,
                        message=f"Fix failed: {fix_result.error}"
                    ))

            except Exception as e:
                self.after(0, lambda: self._show_self_fix_result(
                    success=False,
                    message=f"Error during fix: {str(e)}"
                ))

        threading.Thread(target=run_fix, daemon=True).start()

    def _show_self_fix_result(self, success: bool, message: str, details: dict = None) -> None:
        """Show the result of the self-fix operation."""
        self._log(f"\n{message}")

        if details:
            if details.get("fixed_tags"):
                self._log("  Fixed characters:")
                for tag in details["fixed_tags"]:
                    self._log(f"    ✅ [{tag}]")
            if details.get("errors"):
                self._log("  Errors:")
                for error in details["errors"]:
                    self._log(f"    ❌ {error}")

        # Re-enable button
        self.btn_self_fix.configure(
            state="normal",
            text="🔧 Self-Fix",
            fg_color="#27AE60" if success else "#E67E22"  # Green if success, orange if not
        )

        # Show toast notification
        if success and details and details.get("fixed_tags"):
            self._log("\n💡 Tip: Run the Writer pipeline again to use the new character profiles")
