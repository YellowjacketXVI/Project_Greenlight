"""
Greenlight Director Dialog - Configure and run the director pipeline.

Directing Phase (from Writer_Flow_v2.md):
- Takes Script as input (scripts/script.md - output from Writer pipeline)
- Step 1: Scene Chunking (split Script into individual scenes)
- Step 2: Per-Scene Processing (frame count, frame points, frame marking, prompts)
- Step 3: Camera/Placement Insertion
- Output: Visual_Script with frame notations
"""

import customtkinter as ctk
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
import threading
import asyncio
import json
import re
from datetime import datetime
from dataclasses import dataclass, field

from greenlight.ui.theme import theme
from greenlight.llm.llm_registry import list_available_llms, get_llm_by_id
from greenlight.llm import LLMManager
from greenlight.pipelines.directing_pipeline import (
    DirectingPipeline, DirectingInput, VisualScriptOutput
)
from greenlight.tags import TagRegistry
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.director_dialog")


@dataclass
class SceneData:
    """Parsed scene data from Script."""
    scene_number: int
    title: str
    location: str
    time: str
    characters: List[str]
    purpose: str
    emotional_beat: str
    props: List[str]
    beats: List[Dict[str, Any]]
    raw_content: str


class DirectorDialog(ctk.CTkToplevel):
    """Dialog for running the Director pipeline on Script scenes."""

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
        # Extract auto parameters before passing to super
        self.auto_llm = kwargs.pop('auto_llm', 'gemini-flash')
        # Note: auto_max_frames removed - pipeline now determines optimal frame count autonomously

        super().__init__(parent, **kwargs)

        self.project_path = project_path
        self.on_complete = on_complete
        self.external_log = external_log
        self.external_progress = external_progress
        self.close_on_start = close_on_start
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.cancelled = threading.Event()
        self.running = False
        self.scenes_data: List[SceneData] = []
        self.script_content = ""

        # Load Script and parse scenes
        self._load_script()

        # If close_on_start, skip UI creation and run immediately in background
        if self.close_on_start:
            # Check if we have scenes
            if not self.scenes_data:
                # Log error and close
                if self.external_log:
                    self.external_log("❌ No Script found. Run Writer pipeline first.")
                self.destroy()
                return

            # Start pipeline immediately in background (no UI)
            self.withdraw()  # Hide window
            self._run_background_pipeline()
            return

        # Window setup (only when showing UI)
        self.title("Greenlight Director")
        self.geometry("650x450")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 650) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 450) // 2
        self.geometry(f"+{x}+{y}")

        self.configure(fg_color=theme.colors.bg_medium)

        self._create_ui()
        self._create_progress_section()
        self._create_buttons()

    def _load_script(self) -> None:
        """Load Script from project and parse into scenes."""
        # Check project type from project.json
        project_config_path = self.project_path / "project.json"
        is_series = False
        if project_config_path.exists():
            try:
                project_config = json.loads(project_config_path.read_text(encoding="utf-8"))
                is_series = project_config.get("type") == "series"
            except Exception:
                pass

        # Determine base path based on project type
        if is_series:
            base_path = self.project_path / "SEASON_01" / "EPISODE_01"
        else:
            base_path = self.project_path

        # Load script - only use script.md
        script_path = base_path / "scripts" / "script.md"
        if not script_path.exists():
            script_path = None

        if script_path:
            try:
                self.script_content = script_path.read_text(encoding="utf-8")
                self.scenes_data = self._parse_scenes_from_script(self.script_content)
                logger.info(f"Loaded script with {len(self.scenes_data)} scenes from {script_path}")
            except Exception as e:
                logger.error(f"Failed to load script: {e}")
                self.scenes_data = []
        else:
            logger.warning(f"No script found in {base_path / 'scripts'}")
            self.scenes_data = []

    def _parse_scenes_from_script(self, script_content: str) -> List[SceneData]:
        """Parse scenes from script markdown format.

        Supports two formats:
        1. Scene-centric: ## Scene N
        2. Beat-centric: ## Beat: scene.X.YY (groups beats by scene number X)
        """
        scenes = []

        # Try scene-centric format first: ## Scene N
        scene_pattern = r'^## Scene (\d+)[^\n]*\n'
        scene_splits = re.split(scene_pattern, script_content, flags=re.MULTILINE)

        if len(scene_splits) > 1:
            # Scene-centric format found
            for i in range(1, len(scene_splits), 2):
                if i + 1 >= len(scene_splits):
                    break
                scene_num = int(scene_splits[i])
                scene_content = scene_splits[i + 1]
                scenes.append(self._create_scene_data(scene_num, scene_content))
            return scenes

        # Try beat-centric format: ## Beat: scene.X.YY
        beat_pattern = r'^## Beat: scene\.(\d+)\.(\d+)\s*\n'
        beat_matches = list(re.finditer(beat_pattern, script_content, flags=re.MULTILINE))

        if beat_matches:
            # Group beats by scene number
            scene_beats: Dict[int, List[Dict[str, Any]]] = {}
            scene_contents: Dict[int, str] = {}

            for idx, match in enumerate(beat_matches):
                scene_num = int(match.group(1))
                beat_num = int(match.group(2))

                # Get beat content (from this match to next match or end)
                start = match.end()
                end = beat_matches[idx + 1].start() if idx + 1 < len(beat_matches) else len(script_content)
                beat_content = script_content[start:end].strip()

                if scene_num not in scene_beats:
                    scene_beats[scene_num] = []
                    scene_contents[scene_num] = ""

                # Accumulate content for scene
                scene_contents[scene_num] += f"\n\n{beat_content}"

                # Create beat data
                scene_beats[scene_num].append({
                    "beat_id": f"scene.{scene_num}.{beat_num:02d}",
                    "beat_number": beat_num,
                    "content": beat_content,
                    "description": self._extract_beat_description(beat_content)
                })

            # Create SceneData for each scene
            for scene_num in sorted(scene_beats.keys()):
                scene_content = scene_contents[scene_num]
                scene_data = self._create_scene_data(scene_num, scene_content)
                scene_data.beats = scene_beats[scene_num]
                scenes.append(scene_data)

            return scenes

        logger.warning("No scenes found in script - unrecognized format")
        return scenes

    def _extract_beat_description(self, beat_content: str) -> str:
        """Extract description from beat content."""
        # Look for **[OPENING IMAGE]** or similar markers
        desc_match = re.search(r'\*\*\[([^\]]+)\]\*\*', beat_content)
        if desc_match:
            return desc_match.group(1)
        # Fall back to first line
        lines = beat_content.strip().split('\n')
        return lines[0][:100] if lines else ""

    def _create_scene_data(self, scene_num: int, scene_content: str) -> SceneData:
        """Create SceneData from scene content."""
        # Parse scene metadata
        location = self._extract_field(scene_content, r'\*\*Location:\*\*\s*\[([^\]]+)\]')
        time = self._extract_field(scene_content, r'\*\*Time:\*\*\s*\*?\*?\s*(.+?)(?:\n|$)')
        characters_str = self._extract_field(scene_content, r'\*\*Characters:\*\*\s*(.+?)(?:\n|$)')
        purpose = self._extract_field(scene_content, r'\*\*Purpose:\*\*\s*\*?\*?\s*(.+?)(?:\n|$)')
        emotional_beat = self._extract_field(scene_content, r'\*\*Emotional Beat:\*\*\s*\*?\*?\s*(.+?)(?:\n|$)')

        # Extract character tags from content
        characters = re.findall(r'\[CHAR_[^\]]+\]', characters_str) if characters_str else []
        if not characters:
            # Try to find characters in the full content
            characters = list(set(re.findall(r'\[CHAR_[^\]]+\]', scene_content)))

        # Extract props
        props_match = re.search(r'Props:\s*(.+?)(?:\n|$)', scene_content)
        props = []
        if props_match:
            props = re.findall(r'\[PROP_[^\]]+\]', props_match.group(1))
        if not props:
            # Try to find props in the full content
            props = list(set(re.findall(r'\[PROP_[^\]]+\]', scene_content)))

        # Extract locations from content if not found in header
        if not location:
            loc_tags = list(set(re.findall(r'\[LOC_[^\]]+\]', scene_content)))
            location = loc_tags[0] if loc_tags else ""

        # Parse beats within this scene (for scene-centric format)
        beats = self._parse_beats_in_scene(scene_content, scene_num)

        return SceneData(
            scene_number=scene_num,
            title=f"Scene {scene_num}",
            location=location or "",
            time=time or "",
            characters=characters,
            purpose=purpose or "",
            emotional_beat=emotional_beat or "",
            props=props,
            beats=beats,
            raw_content=scene_content
        )

    def _extract_field(self, content: str, pattern: str) -> Optional[str]:
        """Extract a field from content using regex pattern."""
        match = re.search(pattern, content, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _parse_beats_in_scene(self, scene_content: str, scene_num: int) -> List[Dict[str, Any]]:
        """Parse beats within a scene."""
        beats = []

        # Split by beat headers
        beat_pattern = r'^### Beat (\d+)\n'
        beat_splits = re.split(beat_pattern, scene_content, flags=re.MULTILINE)

        for i in range(1, len(beat_splits), 2):
            if i + 1 >= len(beat_splits):
                break

            beat_num = int(beat_splits[i])
            beat_content = beat_splits[i + 1]

            # Extract beat description (line starting with **)
            desc_match = re.search(r'^\*\*\s*(.+?)(?:\n|$)', beat_content, re.MULTILINE)
            description = desc_match.group(1).strip() if desc_match else ""

            # Extract beat details
            direction = self._extract_field(beat_content, r'- Direction:\s*(.+?)(?:\n|$)')
            camera = self._extract_field(beat_content, r'- Camera:\s*(.+?)(?:\n|$)')
            emotional_arc = self._extract_field(beat_content, r'- Emotional Arc:\s*(.+?)(?:\n|$)')

            # Extract tags
            char_tags = re.findall(r'\[CHAR_[^\]]+\]', beat_content)
            prop_tags = re.findall(r'\[PROP_[^\]]+\]', beat_content)
            loc_tags = re.findall(r'\[LOC_[^\]]+\]', beat_content)

            beats.append({
                "beat_id": f"scene.{scene_num}.{beat_num:02d}",
                "beat_number": beat_num,
                "description": description,
                "direction": direction or "",
                "camera_suggestion": camera or "",
                "emotional_arc": emotional_arc or "",
                "character_tags": char_tags,
                "prop_tags": prop_tags,
                "location_tags": loc_tags,
                "raw_content": beat_content
            })

        return beats

    def _create_ui(self) -> None:
        """Create the dialog UI."""
        # Title
        title = ctk.CTkLabel(
            self, text="Director Pipeline",
            font=(theme.fonts.family, theme.fonts.size_header, "bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(pady=(20, 10))

        # Description
        desc = ctk.CTkLabel(
            self,
            text="Transform Script into Visual_Script with frame notations.\n"
                 "Scene Chunking → Frame Marking → Camera/Placement Insertion",
            text_color=theme.colors.text_secondary,
            justify="center"
        )
        desc.pack(pady=(0, 20))

        # Count total beats across all scenes
        total_beats = sum(len(scene.beats) for scene in self.scenes_data)

        # Scene count info
        scene_info = ctk.CTkLabel(
            self,
            text=f"Found {len(self.scenes_data)} scenes ({total_beats} beats) to process",
            text_color=theme.colors.accent if self.scenes_data else theme.colors.warning
        )
        scene_info.pack(pady=(0, 10))

        # Options frame
        options_frame = ctk.CTkFrame(self, fg_color=theme.colors.bg_dark)
        options_frame.pack(fill="x", padx=30, pady=10)

        # LLM selector
        llm_label = ctk.CTkLabel(
            options_frame, text="AI Model:",
            text_color=theme.colors.text_primary, anchor="w"
        )
        llm_label.pack(fill="x", padx=15, pady=(15, 5))

        llm_list = list_available_llms()
        self.llm_options = [llm.name for llm in llm_list] if llm_list else ["No LLMs configured"]
        self.llm_map = {llm.name: llm.id for llm in llm_list} if llm_list else {}

        self.llm_dropdown = ctk.CTkOptionMenu(
            options_frame, values=self.llm_options,
            fg_color=theme.colors.bg_medium
        )
        self.llm_dropdown.set(self.llm_options[0])
        self.llm_dropdown.pack(fill="x", padx=15, pady=(0, 15))

        # Note: Max frames per scene control removed - pipeline now determines
        # optimal frame count autonomously based on scene content

    def _create_progress_section(self) -> None:
        """Create progress display section."""
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.pack(fill="x", padx=30, pady=10)

        self.progress_label = ctk.CTkLabel(
            progress_frame, text="Ready to generate",
            text_color=theme.colors.text_muted
        )
        self.progress_label.pack(pady=5)

        # Placeholder for log_text to avoid attribute errors
        self.log_text = None

    def _create_buttons(self) -> None:
        """Create action buttons."""
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

        self.btn_run = ctk.CTkButton(
            btn_frame, text="Run Director", width=120,
            fg_color=theme.colors.accent,
            hover_color=theme.colors.accent_hover,
            command=self._on_run,
            state="normal" if self.scenes_data else "disabled"
        )
        self.btn_run.grid(row=0, column=2)

    def _on_run(self) -> None:
        """Start the director pipeline from UI button."""
        if not self.scenes_data:
            self._log("❌ No Script found. Run Writer pipeline first.")
            return

        self.running = True
        self.cancelled.clear()

        selected_llm = self.llm_dropdown.get()
        llm_id = self.llm_map.get(selected_llm, "gemini-pro")
        llm_id_config = llm_id.replace("-", "_")

        self._execute_pipeline(llm_id_config, selected_llm)

        # Close the dialog - pipeline runs in background with external logging
        self.after(100, self.destroy)

    def _run_background_pipeline(self) -> None:
        """Run pipeline immediately in background (no UI, called when close_on_start=True)."""
        self.running = True
        self.cancelled.clear()

        # Use auto parameters for background execution
        llm_id = self.auto_llm
        llm_id_config = llm_id.replace("-", "_")
        selected_llm = llm_id

        self._log(f"🤖 Auto-running Director Pipeline...")
        self._log(f"  → LLM: {llm_id}")

        self._execute_pipeline(llm_id_config, selected_llm)

        # Destroy the hidden window after starting the pipeline
        self.after(100, self.destroy)

    def _execute_pipeline(self, llm_id_config: str, selected_llm: str) -> None:
        """Execute the directing pipeline in a background thread."""
        # Capture references before dialog is destroyed
        scenes_data = self.scenes_data
        script_content = self.script_content
        project_path = self.project_path
        external_log = self.external_log
        external_progress = self.external_progress
        on_complete = self.on_complete
        cancelled = self.cancelled

        def log_msg(msg: str) -> None:
            """Log to external logger and standard logger."""
            logger.info(msg)
            if external_log:
                try:
                    external_log(msg)
                except Exception:
                    pass

        def update_progress(value: float) -> None:
            """Update external progress."""
            if external_progress:
                try:
                    external_progress(value)
                except Exception:
                    pass

        def run_pipeline():
            try:
                total_beats = sum(len(scene.beats) for scene in scenes_data)
                log_msg("🎬 Starting Directing Pipeline (Writer_Flow_v2)...")
                log_msg(f"  → Processing {len(scenes_data)} scenes ({total_beats} beats)")
                update_progress(0.05)

                # Load world config
                world_path = project_path / "world_bible" / "world_config.json"
                world_config = {}
                if world_path.exists():
                    try:
                        world_config = json.loads(world_path.read_text(encoding="utf-8"))
                    except Exception as e:
                        logger.warning(f"Failed to load world config: {e}")

                # Initialize pipeline with selected LLM
                log_msg("🔧 Initializing pipeline...")
                log_msg(f"  → Selected LLM: {selected_llm}")

                from greenlight.core.config import GreenlightConfig, FunctionLLMMapping, get_config
                from greenlight.core.constants import LLMFunction

                base_config = get_config()
                custom_config = GreenlightConfig()
                custom_config.llm_configs = base_config.llm_configs.copy()
                custom_config.function_mappings = {}

                selected_config = custom_config.llm_configs.get(llm_id_config)
                if not selected_config:
                    log_msg(f"⚠️ LLM '{llm_id_config}' not found, using first available")
                    selected_config = next(iter(custom_config.llm_configs.values()))

                for function in LLMFunction:
                    custom_config.function_mappings[function] = FunctionLLMMapping(
                        function=function,
                        primary_config=selected_config,
                        fallback_config=None
                    )

                log_msg(f"  ✓ Using LLM: {selected_config.model}")
                llm_manager = LLMManager(custom_config)

                # Create LLM caller function for the pipeline
                async def llm_caller(prompt: str, system_prompt: str = "", function: LLMFunction = LLMFunction.STORY_GENERATION) -> str:
                    return await llm_manager.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        function=function
                    )

                # Create DirectingPipeline with LLM caller
                directing_pipeline = DirectingPipeline(llm_caller=llm_caller)

                update_progress(0.1)

                # Create DirectingInput with full script
                directing_input = DirectingInput(
                    script=script_content,
                    world_config=world_config,
                    visual_style=world_config.get("visual_style", ""),
                    style_notes=world_config.get("style_notes", ""),
                    media_type=world_config.get("media_type", "standard")
                )

                log_msg("🎬 Running Directing Pipeline (parallel scene processing)...")
                update_progress(0.2)

                # Run the pipeline
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    pipeline_result = loop.run_until_complete(
                        directing_pipeline.run(directing_input)
                    )

                    if pipeline_result.success and pipeline_result.output:
                        result: VisualScriptOutput = pipeline_result.output
                        log_msg(f"  ✓ Processed {len(result.scenes)} scenes")
                        log_msg(f"  ✓ Generated {result.total_frames} frames")

                        update_progress(0.9)

                        if not cancelled.is_set():
                            # Save visual script output
                            log_msg("💾 Saving Visual_Script...")
                            project_config_path = project_path / "project.json"
                            is_series = False
                            if project_config_path.exists():
                                try:
                                    proj_cfg = json.loads(project_config_path.read_text(encoding="utf-8"))
                                    is_series = proj_cfg.get("type") == "series"
                                except Exception:
                                    pass

                            if is_series:
                                output_dir = project_path / "episodes" / "ep01" / "storyboard"
                            else:
                                output_dir = project_path / "storyboard"
                            output_dir.mkdir(parents=True, exist_ok=True)

                            # Save as markdown
                            md_path = output_dir / "visual_script.md"
                            md_content = result.to_markdown()
                            md_path.write_text(md_content, encoding="utf-8")
                            log_msg(f"  ✓ Saved: {md_path.name}")

                            # Save as JSON
                            json_path = output_dir / "visual_script.json"
                            json_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
                            log_msg(f"  ✓ Saved: {json_path.name}")

                        update_progress(1.0)
                        log_msg(f"✅ Directing complete! Generated {result.total_frames} frames across {len(result.scenes)} scenes.")
                    elif pipeline_result.error:
                        log_msg(f"⚠️ Pipeline failed: {pipeline_result.error}")
                    else:
                        log_msg("⚠️ Pipeline returned no result")

                finally:
                    loop.close()

                # Call completion callback
                if on_complete and not cancelled.is_set():
                    on_complete({"project_path": str(project_path)})

            except Exception as e:
                logger.exception("Directing pipeline error")
                log_msg(f"❌ Error: {e}")

        # Submit to thread pool - use a new executor that won't be destroyed with the dialog
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        executor.submit(run_pipeline)

    def _load_character_descriptions(self) -> Dict[str, str]:
        """Load character descriptions from world config."""
        world_path = self.project_path / "world_bible" / "world_config.json"
        if world_path.exists():
            try:
                data = json.loads(world_path.read_text(encoding="utf-8"))
                return {
                    char.get("tag", ""): f"{char.get('name', '')} - {char.get('role', '')}"
                    for char in data.get("characters", [])
                }
            except Exception:
                pass
        return {}

    def _load_world_config(self) -> Dict[str, Any]:
        """Load full world config for directing pipeline."""
        world_path = self.project_path / "world_bible" / "world_config.json"
        if world_path.exists():
            try:
                return json.loads(world_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to load world config: {e}")
        return {}

    def _save_visual_script_output(self, result: VisualScriptOutput) -> None:
        """Save Visual_Script output from DirectingPipeline."""
        self._log("💾 Saving Visual_Script...")

        # Determine output path based on project type
        project_config_path = self.project_path / "project.json"
        is_series = False
        if project_config_path.exists():
            try:
                project_config = json.loads(project_config_path.read_text(encoding="utf-8"))
                is_series = project_config.get("type") == "series"
            except Exception:
                pass

        if is_series:
            base_path = self.project_path / "SEASON_01" / "EPISODE_01"
        else:
            base_path = self.project_path

        scripts_path = base_path / "scripts" / "visual_script.md"
        scripts_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the visual script
        scripts_path.write_text(result.visual_script, encoding="utf-8")
        self._log(f"✓ Saved Visual_Script to {scripts_path.name}")

        # Save metadata
        metadata_path = base_path / "scripts" / "directing_metadata.json"
        metadata = {
            "total_frames": result.total_frames,
            "scenes_processed": len(result.scenes),
            "generated": datetime.now().isoformat(),
            **result.metadata
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        self._log(f"✓ Saved directing metadata ({result.total_frames} frames)")

    def _save_prompts(self, prompts: List) -> None:
        """Save generated prompts to project."""
        self._log("💾 Saving storyboard prompts...")

        # Determine output path
        prompts_path = self.project_path / "prompts" / "storyboard_prompts.json"
        if not prompts_path.parent.exists():
            prompts_path = self.project_path / "SEASON_01" / "EPISODE_01" / "prompts" / "storyboard_prompts.json"

        prompts_path.parent.mkdir(parents=True, exist_ok=True)

        prompts_data = {
            "prompts": [
                {
                    "notation": p.notation,
                    "scene_description": p.scene_description,
                    "shot_type": p.camera_shot.shot_type,
                    "shot_code": p.camera_shot.shot_type_code,
                    "angle": p.camera_shot.angle,
                    "movement": p.camera_shot.movement,
                    "lighting": p.lighting,
                    "mood": p.mood,
                    "full_prompt": p.full_prompt,
                    "negative_prompt": p.negative_prompt,
                    "technical_notes": p.technical_notes
                }
                for p in prompts
            ],
            "total_prompts": len(prompts),
            "generated": datetime.now().isoformat()
        }

        prompts_path.write_text(json.dumps(prompts_data, indent=2), encoding="utf-8")
        self._log(f"✓ Saved {len(prompts)} prompts to {prompts_path.name}")

    def _save_visual_script(self, prompts: List) -> None:
        """Save Visual_Script with frame notations (output of Directing Phase)."""
        self._log("💾 Generating Visual_Script...")

        # Determine output path
        scripts_path = self.project_path / "scripts" / "visual_script.md"
        if not scripts_path.parent.exists():
            scripts_path = self.project_path / "SEASON_01" / "EPISODE_01" / "scripts" / "visual_script.md"

        scripts_path.parent.mkdir(parents=True, exist_ok=True)

        # Group prompts by scene
        scenes_prompts: Dict[int, List] = {}
        for p in prompts:
            # Extract scene number from notation using scene.frame.camera format (e.g., 1.2.cA)
            # Also support legacy format (S##).(F##).(c#) for backwards compatibility
            scene_match = re.search(r'^(\d+)\.\d+\.c[A-Z]', p.notation)
            if not scene_match:
                # Fallback to legacy format
                scene_match = re.search(r'\(S(\d+)\)', p.notation)
            scene_num = int(scene_match.group(1)) if scene_match else 1
            if scene_num not in scenes_prompts:
                scenes_prompts[scene_num] = []
            scenes_prompts[scene_num].append(p)

        # Build Visual_Script markdown
        lines = [
            "# Visual Script",
            "",
            f"**Generated:** {datetime.now().isoformat()}",
            f"**Total Frames:** {len(prompts)}",
            "",
            "---",
            ""
        ]

        for scene_num in sorted(scenes_prompts.keys()):
            scene_prompts = scenes_prompts[scene_num]
            lines.append(f"## Scene {scene_num}")
            lines.append("")

            for p in scene_prompts:
                # Frame notation block per Writer_Flow_v2.md format
                lines.append("(/scene_frame_chunk_start/)")
                lines.append("")
                lines.append(f"{{frame_{p.notation.replace('(', '').replace(')', '').replace('.', '_')}}}")
                lines.append(f"[CAM: {p.camera_shot.shot_type}, {p.camera_shot.angle}, {p.camera_shot.movement}]")
                lines.append(f"[LIGHT: {p.lighting}]")
                lines.append(f"[PROMPT: {p.full_prompt[:500]}...]" if len(p.full_prompt) > 500 else f"[PROMPT: {p.full_prompt}]")
                lines.append("")
                lines.append("(/scene_frame_chunk_end/)")
                lines.append("")

            lines.append("---")
            lines.append("")

        visual_script_content = "\n".join(lines)
        scripts_path.write_text(visual_script_content, encoding="utf-8")
        self._log(f"✓ Saved Visual_Script to {scripts_path.name}")

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

    def _complete(self) -> None:
        """Handle completion."""
        self.running = False
        if not self._is_widget_valid():
            return
        try:
            self.btn_run.configure(text="Done", state="normal", command=self.destroy)
            self.btn_cancel.configure(state="disabled")
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
