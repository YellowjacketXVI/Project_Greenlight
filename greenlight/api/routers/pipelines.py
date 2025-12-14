"""Pipelines router for Project Greenlight API."""

import asyncio
import json
import re
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from greenlight.core.logging_config import get_logger

logger = get_logger("api.pipelines")

router = APIRouter()

# Store for pipeline status
pipeline_status: dict[str, dict] = {}


class PipelineRequest(BaseModel):
    project_path: str
    llm: Optional[str] = "claude-sonnet-4.5"
    image_model: Optional[str] = "seedream"
    max_frames: Optional[int] = None


class PipelineStatus(BaseModel):
    name: str
    status: str  # idle, running, complete, failed
    progress: float
    message: Optional[str] = None
    logs: Optional[list[str]] = None


class PipelineResponse(BaseModel):
    success: bool
    message: str
    pipeline_id: Optional[str] = None


@router.get("/status/{pipeline_id:path}", response_model=PipelineStatus)
async def get_pipeline_status(pipeline_id: str):
    """Get status of a pipeline by its ID."""
    if pipeline_id in pipeline_status:
        return PipelineStatus(**pipeline_status[pipeline_id])
    return PipelineStatus(name=pipeline_id, status="idle", progress=0)


@router.post("/writer", response_model=PipelineResponse)
async def run_writer_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the Writer pipeline."""
    pipeline_id = f"writer_{request.project_path}"
    pipeline_status[pipeline_id] = {"name": "writer", "status": "running", "progress": 0, "message": "Starting...", "logs": ["Starting Writer pipeline..."]}
    background_tasks.add_task(execute_writer_pipeline, pipeline_id, request.project_path, request.llm)
    return PipelineResponse(success=True, message="Writer pipeline started", pipeline_id=pipeline_id)


@router.post("/director", response_model=PipelineResponse)
async def run_director_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the Director pipeline."""
    pipeline_id = f"director_{request.project_path}"
    pipeline_status[pipeline_id] = {"name": "director", "status": "running", "progress": 0, "message": "Starting...", "logs": ["Starting Director pipeline..."]}
    background_tasks.add_task(execute_director_pipeline, pipeline_id, request.project_path, request.llm, request.max_frames)
    return PipelineResponse(success=True, message="Director pipeline started", pipeline_id=pipeline_id)


@router.post("/references", response_model=PipelineResponse)
async def run_references_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the References pipeline."""
    pipeline_id = f"references_{request.project_path}"
    pipeline_status[pipeline_id] = {"name": "references", "status": "running", "progress": 0, "message": "Starting...", "logs": ["Starting References pipeline..."]}
    background_tasks.add_task(execute_references_pipeline, pipeline_id, request.project_path, request.image_model)
    return PipelineResponse(success=True, message="References pipeline started", pipeline_id=pipeline_id)


@router.post("/storyboard", response_model=PipelineResponse)
async def run_storyboard_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the Storyboard pipeline."""
    pipeline_id = f"storyboard_{request.project_path}"
    pipeline_status[pipeline_id] = {"name": "storyboard", "status": "running", "progress": 0, "message": "Starting...", "logs": ["Starting Storyboard pipeline..."]}
    background_tasks.add_task(execute_storyboard_pipeline, pipeline_id, request.project_path, request.image_model, request.max_frames)
    return PipelineResponse(success=True, message="Storyboard pipeline started", pipeline_id=pipeline_id)


def _add_log(pipeline_id: str, message: str):
    """Add a log message to the pipeline status."""
    if pipeline_id in pipeline_status:
        if "logs" not in pipeline_status[pipeline_id]:
            pipeline_status[pipeline_id]["logs"] = []
        pipeline_status[pipeline_id]["logs"].append(message)
        pipeline_status[pipeline_id]["message"] = message


async def execute_writer_pipeline(pipeline_id: str, project_path: str, llm: str):
    """Execute the Writer pipeline."""
    try:
        _add_log(pipeline_id, "Running Writer pipeline...")
        pipeline_status[pipeline_id]["progress"] = 10
        # TODO: Import and run actual pipeline
        # from greenlight.pipelines.story_pipeline import StoryPipeline
        await asyncio.sleep(2)  # Placeholder
        pipeline_status[pipeline_id]["progress"] = 100
        pipeline_status[pipeline_id]["status"] = "complete"
        _add_log(pipeline_id, "✓ Writer pipeline completed")
    except Exception as e:
        pipeline_status[pipeline_id]["status"] = "failed"
        _add_log(pipeline_id, f"❌ Error: {str(e)}")


async def execute_director_pipeline(pipeline_id: str, project_path: str, llm: str, max_frames: Optional[int]):
    """Execute the Director pipeline.

    Transforms script.md into visual_script.json with scene.frame.camera notation.
    """
    from greenlight.pipelines.directing_pipeline import DirectingPipeline, DirectingInput
    from greenlight.llm import LLMManager
    from greenlight.core.config import GreenlightConfig, FunctionLLMMapping, get_config
    from greenlight.core.constants import LLMFunction

    project_dir = Path(project_path)

    try:
        _add_log(pipeline_id, "🎬 Starting Director Pipeline...")
        pipeline_status[pipeline_id]["progress"] = 5

        # Load script
        script_path = project_dir / "scripts" / "script.md"
        if not script_path.exists():
            raise FileNotFoundError("No script.md found. Run Writer pipeline first.")

        script_content = script_path.read_text(encoding="utf-8")
        _add_log(pipeline_id, f"✓ Loaded script ({len(script_content)} chars)")
        pipeline_status[pipeline_id]["progress"] = 10

        # Load world config
        world_config = {}
        world_path = project_dir / "world_bible" / "world_config.json"
        if world_path.exists():
            world_config = json.loads(world_path.read_text(encoding="utf-8"))
            _add_log(pipeline_id, "✓ Loaded world config")

        # Initialize LLM manager with selected model
        _add_log(pipeline_id, "🔧 Initializing pipeline...")
        base_config = get_config()
        custom_config = GreenlightConfig()
        custom_config.llm_configs = base_config.llm_configs.copy()
        custom_config.function_mappings = {}

        # Map LLM name to config key
        llm_id_config = llm.replace("-", "_")
        selected_config = custom_config.llm_configs.get(llm_id_config)
        if not selected_config:
            # Fallback to first available config
            selected_config = next(iter(custom_config.llm_configs.values()))

        # Set all functions to use the selected LLM
        for function in LLMFunction:
            custom_config.function_mappings[function] = FunctionLLMMapping(
                function=function, primary_config=selected_config, fallback_config=None
            )

        _add_log(pipeline_id, f"  ✓ Using LLM: {selected_config.model}")
        llm_manager = LLMManager(custom_config)
        pipeline_status[pipeline_id]["progress"] = 15

        # Create LLM caller function for the pipeline
        async def llm_caller(prompt: str, system_prompt: str = "", function: LLMFunction = LLMFunction.STORY_GENERATION) -> str:
            return await llm_manager.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                function=function
            )

        # Initialize directing pipeline
        directing_pipeline = DirectingPipeline(llm_caller=llm_caller)

        # Create input
        directing_input = DirectingInput(
            script=script_content,
            world_config=world_config,
            visual_style=world_config.get("visual_style", ""),
            style_notes=world_config.get("style_notes", ""),
            media_type=world_config.get("media_type", "standard")
        )

        # Run pipeline
        _add_log(pipeline_id, "🚀 Running directing pipeline...")
        pipeline_status[pipeline_id]["progress"] = 20

        result = await directing_pipeline.run(directing_input)

        if result.success and result.output:
            pipeline_status[pipeline_id]["progress"] = 90
            _add_log(pipeline_id, "💾 Saving outputs...")

            # Create storyboard directory
            storyboard_dir = project_dir / "storyboard"
            storyboard_dir.mkdir(parents=True, exist_ok=True)

            # Save as markdown
            md_path = storyboard_dir / "visual_script.md"
            md_path.write_text(result.output.to_markdown(), encoding="utf-8")
            _add_log(pipeline_id, f"  ✓ Saved visual_script.md")

            # Save as JSON with structured scenes array
            json_path = storyboard_dir / "visual_script.json"
            json_path.write_text(json.dumps(result.output.to_dict(), indent=2), encoding="utf-8")
            _add_log(pipeline_id, f"  ✓ Saved visual_script.json")

            pipeline_status[pipeline_id]["progress"] = 100
            pipeline_status[pipeline_id]["status"] = "complete"
            _add_log(pipeline_id, f"✅ Director complete! Generated {result.output.total_frames} frames across {len(result.output.scenes)} scenes.")
        else:
            pipeline_status[pipeline_id]["status"] = "failed"
            _add_log(pipeline_id, f"❌ Pipeline failed: {result.error}")
    except Exception as e:
        logger.exception(f"Director pipeline error: {e}")
        pipeline_status[pipeline_id]["status"] = "failed"
        _add_log(pipeline_id, f"❌ Error: {str(e)}")


async def execute_references_pipeline(pipeline_id: str, project_path: str, image_model: str):
    """Execute the References pipeline."""
    try:
        _add_log(pipeline_id, "Generating reference images...")
        pipeline_status[pipeline_id]["progress"] = 10
        await asyncio.sleep(2)  # Placeholder
        pipeline_status[pipeline_id]["progress"] = 100
        pipeline_status[pipeline_id]["status"] = "complete"
        _add_log(pipeline_id, "✓ References pipeline completed")
    except Exception as e:
        pipeline_status[pipeline_id]["status"] = "failed"
        _add_log(pipeline_id, f"❌ Error: {str(e)}")


def _extract_tags_from_prompt(prompt: str) -> List[str]:
    """Extract all tags from a frame prompt.

    Tags are in format: [CHAR_NAME], [LOC_NAME], [PROP_NAME], etc.
    """
    pattern = r'\[(CHAR_|LOC_|PROP_|CONCEPT_|EVENT_|ENV_)[A-Z0-9_]+\]'
    matches = re.findall(pattern, prompt)
    # Return full tags including brackets
    full_tags = re.findall(r'\[(?:CHAR_|LOC_|PROP_|CONCEPT_|EVENT_|ENV_)[A-Z0-9_]+\]', prompt)
    # Remove brackets for directory lookup
    return [tag[1:-1] for tag in full_tags]


def _parse_frames_from_raw_visual_script(raw_text: str) -> List[Dict[str, Any]]:
    """Parse frames from raw visual_script text when structured scenes array is empty.

    Extracts frames from text format like:
    (/scene_frame_chunk_start/)
    [1.2.cA] (Frame)
    [CAM: ...]
    [POS: ...]
    [LIGHT: ...]
    [PROMPT: ...]
    (/scene_frame_chunk_end/)
    """
    frames = []

    # Pattern to match frame blocks with scene.frame.camera notation
    # Matches: [1.2.cA] (Frame) followed by content until chunk_end
    frame_pattern = re.compile(
        r'\[(\d+)\.(\d+)\.c([A-Z])\]\s*\([^)]*\)'  # [1.2.cA] (Frame)
        r'.*?'  # Any content
        r'\[PROMPT:\s*([^\]]+(?:\][^\]]*)*)\]',  # [PROMPT: ...] - handles nested brackets
        re.DOTALL
    )

    # Also try simpler pattern for **PROMPT:** format
    alt_pattern = re.compile(
        r'\[(\d+)\.(\d+)\.c([A-Z])\]\s*\([^)]*\)'  # [1.2.cA] (Frame)
        r'.*?'  # Any content
        r'\*\*PROMPT:\*\*\s*(.+?)(?=\(/scene_frame_chunk_end/\)|$)',  # **PROMPT:** ...
        re.DOTALL
    )

    # Try primary pattern first
    matches = frame_pattern.findall(raw_text)

    if not matches:
        # Try alternative pattern
        matches = alt_pattern.findall(raw_text)

    for match in matches:
        scene_num = int(match[0])
        frame_num = int(match[1])
        camera = match[2]
        prompt = match[3].strip()

        # Clean up prompt - remove **PROMPT:** prefix if present
        prompt = re.sub(r'^\*\*PROMPT:\*\*\s*', '', prompt)

        # Truncate very long prompts
        words = prompt.split()
        if len(words) > 300:
            prompt = " ".join(words[:300])

        frame_id = f"{scene_num}.{frame_num}.c{camera}"

        frames.append({
            "frame_id": frame_id,
            "id": frame_id,
            "prompt": prompt,
            "scene_number": scene_num,
            "frame_number": frame_num,
            "camera": f"c{camera}",
            "_scene_num": str(scene_num),
        })

    # Sort by scene, then frame, then camera
    frames.sort(key=lambda f: (f["scene_number"], f["frame_number"], f.get("camera", "cA")))

    return frames


def _get_key_reference_for_tag(project_path: Path, tag: str) -> Optional[Path]:
    """Get the key reference image for a tag.

    Looks in {project_path}/references/{tag}/ for the starred/key image.
    """
    refs_dir = project_path / "references" / tag
    if not refs_dir.exists():
        return None

    # Check for .key file that stores the key reference filename
    key_file = refs_dir / ".key"
    if key_file.exists():
        key_filename = key_file.read_text(encoding='utf-8').strip()
        key_path = refs_dir / key_filename
        if key_path.exists():
            return key_path

    # Fallback: find first image in directory
    for ext in ['.png', '.jpg', '.jpeg', '.webp']:
        for img in refs_dir.glob(f'*{ext}'):
            if not img.name.startswith('.'):
                return img

    return None


def _build_labeled_prompt(prompt: str, tag_refs: List[tuple], has_prior_frame: bool) -> str:
    """Build a prompt with labeled reference image mappings.

    Inserts a reference mapping section so the model knows which image corresponds to which tag.
    Format: "Reference Images: [1] [CHAR_JOHN], [2] [LOC_PALACE], [3] Prior Frame"
    """
    if not tag_refs and not has_prior_frame:
        return prompt

    # Build reference mapping
    ref_parts = []
    img_num = 1

    for tag, _ in tag_refs:
        ref_parts.append(f"[{img_num}] [{tag}]")
        img_num += 1

    if has_prior_frame:
        ref_parts.append(f"[{img_num}] Prior Frame (maintain scene continuity)")

    ref_section = "Reference Images: " + ", ".join(ref_parts) + ". "

    # Insert reference section at beginning of prompt
    return ref_section + prompt


def _get_scene_from_frame_id(frame_id: str) -> Optional[str]:
    """Extract scene number from frame_id (e.g., '1.2.cA' -> '1')."""
    parts = frame_id.split(".")
    if parts:
        return parts[0]
    return None


async def execute_storyboard_pipeline(pipeline_id: str, project_path: str, image_model: str, max_frames: Optional[int]):
    """Execute the Storyboard pipeline.

    1. Reads visual_script.json from {project_path}/storyboard/
    2. For each frame, extracts tags and gets reference images with labels
    3. Uses prior frame as input within each scene (resets at scene boundaries)
    4. Uses ImageHandler to generate images with Seedream 4.5
    5. Saves to {project_path}/storyboard_output/generated/
    6. Logs full prompts to {project_path}/storyboard_output/prompts_log.json
    """
    from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel

    try:
        project_dir = Path(project_path)
        _add_log(pipeline_id, f"📂 Loading project: {project_dir.name}")

        # 1. Load visual_script.json
        visual_script_path = project_dir / "storyboard" / "visual_script.json"
        if not visual_script_path.exists():
            raise FileNotFoundError(f"Visual script not found at {visual_script_path}")

        visual_script = json.loads(visual_script_path.read_text(encoding='utf-8'))
        _add_log(pipeline_id, f"✓ Loaded visual script")

        # 2. Extract all frames from scenes (keeping scene structure for prior frame logic)
        frames = []

        # Try structured scenes array first
        for scene in visual_script.get("scenes", []):
            scene_num = scene.get("scene_number", scene.get("scene_id", ""))
            for frame in scene.get("frames", []):
                frame["_scene_num"] = scene_num  # Track scene for continuity
                frames.append(frame)

        # If no structured frames, parse from raw visual_script text
        if not frames and "visual_script" in visual_script:
            _add_log(pipeline_id, "📝 Parsing frames from raw visual script text...")
            raw_text = visual_script.get("visual_script", "")
            frames = _parse_frames_from_raw_visual_script(raw_text)
            _add_log(pipeline_id, f"✓ Parsed {len(frames)} frames from text")

        total_frames = len(frames)
        if max_frames and max_frames < total_frames:
            frames = frames[:max_frames]
            total_frames = len(frames)

        _add_log(pipeline_id, f"📊 Found {total_frames} frames to generate")
        pipeline_status[pipeline_id]["progress"] = 5

        # 3. Create output directory and prompts log
        output_dir = project_dir / "storyboard_output" / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)
        prompts_log_path = project_dir / "storyboard_output" / "prompts_log.json"
        prompts_log: List[Dict[str, Any]] = []
        _add_log(pipeline_id, f"📁 Output: {output_dir}")

        # 4. Initialize ImageHandler
        handler = ImageHandler(project_path=project_dir)

        # 5. Map image model string to ImageModel enum
        model_mapping = {
            "seedream": ImageModel.SEEDREAM,
            "seedream_4_5": ImageModel.SEEDREAM,
            "nano_banana": ImageModel.NANO_BANANA,
            "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
            "flux_kontext_pro": ImageModel.FLUX_KONTEXT_PRO,
            "flux_kontext_max": ImageModel.FLUX_KONTEXT_MAX,
        }
        selected_model = model_mapping.get(image_model, ImageModel.SEEDREAM)
        _add_log(pipeline_id, f"🤖 Using model: {selected_model.value}")

        # 6. Generate each frame with prior frame walking within scenes
        successful = 0
        failed = 0
        prior_frame_path: Optional[Path] = None
        current_scene: Optional[str] = None

        for i, frame in enumerate(frames):
            frame_id = frame.get("frame_id", frame.get("id", f"frame_{i+1}"))
            prompt = frame.get("prompt", "")
            frame_scene = frame.get("_scene_num") or _get_scene_from_frame_id(frame_id)

            # Check if we're in a new scene - reset prior frame
            if frame_scene != current_scene:
                prior_frame_path = None
                current_scene = frame_scene
                _add_log(pipeline_id, f"📍 Scene {frame_scene}")

            if not prompt:
                _add_log(pipeline_id, f"⚠️ Skipping {frame_id}: no prompt")
                failed += 1
                continue

            # Extract tags and get reference images WITH labels
            tags = _extract_tags_from_prompt(prompt)
            tag_refs: List[tuple] = []  # List of (tag, path) tuples
            reference_images: List[Path] = []

            for tag in tags:
                ref_path = _get_key_reference_for_tag(project_dir, tag)
                if ref_path:
                    tag_refs.append((tag, ref_path))
                    reference_images.append(ref_path)

            # Add prior frame if we have one (within same scene)
            has_prior_frame = prior_frame_path is not None and prior_frame_path.exists()
            if has_prior_frame:
                reference_images.append(prior_frame_path)

            # Build labeled prompt
            labeled_prompt = _build_labeled_prompt(prompt, tag_refs, has_prior_frame)

            # Create output path for this frame
            clean_frame_id = frame_id.replace("[", "").replace("]", "")
            output_path = output_dir / f"{clean_frame_id}.png"

            ref_count = len(tag_refs) + (1 if has_prior_frame else 0)
            _add_log(pipeline_id, f"🎨 {frame_id} ({ref_count} refs{', +prior' if has_prior_frame else ''})")

            # Log the prompt BEFORE sending (so it's recorded even if generation fails)
            prompt_log_entry = {
                "frame_id": clean_frame_id,
                "scene": str(frame_scene),
                "original_prompt": prompt,
                "full_prompt": labeled_prompt,
                "tags": tags,
                "reference_images": [str(p) for p in reference_images],
                "has_prior_frame": has_prior_frame,
                "model": selected_model.value,
                "status": "pending",
                "timestamp": None,
                "output_path": str(output_path),
            }

            try:
                # Create image request with labeled prompt
                request = ImageRequest(
                    prompt=labeled_prompt,
                    model=selected_model,
                    aspect_ratio="16:9",
                    reference_images=reference_images,
                    output_path=output_path,
                    tag=frame_id,
                    prefix_type="generate",  # Uses PROMPT_TEMPLATE_CREATE
                    add_clean_suffix=True
                )

                # Update timestamp when request is sent
                from datetime import datetime
                prompt_log_entry["timestamp"] = datetime.now().isoformat()

                # Generate image
                result = await handler.generate(request)

                if result.success:
                    successful += 1
                    _add_log(pipeline_id, f"✓ {frame_id} saved")
                    # Update prior frame for next iteration (within scene)
                    prior_frame_path = output_path
                    prompt_log_entry["status"] = "success"
                else:
                    failed += 1
                    _add_log(pipeline_id, f"❌ {frame_id}: {result.error}")
                    prompt_log_entry["status"] = "failed"
                    prompt_log_entry["error"] = result.error
                    # Don't update prior_frame_path on failure

            except Exception as e:
                failed += 1
                _add_log(pipeline_id, f"❌ {frame_id}: {str(e)}")
                logger.error(f"Error generating frame {frame_id}: {e}")
                prompt_log_entry["status"] = "error"
                prompt_log_entry["error"] = str(e)

            # Add to prompts log and save incrementally
            prompts_log.append(prompt_log_entry)
            prompts_log_path.write_text(json.dumps(prompts_log, indent=2), encoding='utf-8')

            # Update progress
            progress = 5 + int((i + 1) / total_frames * 90)
            pipeline_status[pipeline_id]["progress"] = progress

        # 7. Run auto-labeler to ensure all media in folder is properly labeled
        _add_log(pipeline_id, "🏷️ Running auto-labeler...")
        try:
            from greenlight.core.storyboard_labeler import label_storyboard_media
            renamed = label_storyboard_media(project_dir)
            if renamed:
                _add_log(pipeline_id, f"✓ Labeled {len(renamed)} files")
        except Exception as e:
            logger.warning(f"Auto-labeler error: {e}")
            _add_log(pipeline_id, f"⚠️ Labeler warning: {str(e)}")

        # 8. Complete
        pipeline_status[pipeline_id]["progress"] = 100
        pipeline_status[pipeline_id]["status"] = "complete"
        _add_log(pipeline_id, f"✓ Storyboard complete: {successful}/{total_frames} frames generated")

        if failed > 0:
            _add_log(pipeline_id, f"⚠️ {failed} frames failed")

    except Exception as e:
        logger.error(f"Storyboard pipeline error: {e}")
        pipeline_status[pipeline_id]["status"] = "failed"
        _add_log(pipeline_id, f"❌ Error: {str(e)}")

