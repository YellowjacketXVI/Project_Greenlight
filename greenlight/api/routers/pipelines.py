"""Pipelines router for Project Greenlight API.

Unified pipeline endpoints for writer, director, references, and storyboard.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import LLMFunction
from .pipeline_utils import (
    extract_prompts_from_visual_script,
    setup_llm_manager,
    get_selected_llm_model,
    extract_tags_from_prompt,
    get_scene_from_frame_id,
    get_key_reference_for_tag,
    build_labeled_prompt,
    build_scene_context,
    build_stateless_prompt,
    parse_frames_from_raw_visual_script,
    get_time_negative_prompt,
    load_character_data,
    load_entity_data,
)

logger = get_logger("api.pipelines")

router = APIRouter()

# Rate limiter for expensive pipeline operations
limiter = Limiter(key_func=get_remote_address)

# Store for pipeline status
pipeline_status: dict[str, dict] = {}


class PipelineRequest(BaseModel):
    project_path: str
    llm: Optional[str] = "claude-haiku-4.5"
    image_model: Optional[str] = "seedream"
    max_frames: Optional[int] = None
    # Writer-specific options
    media_type: Optional[str] = "standard"
    visual_style: Optional[str] = "live_action"
    style_notes: Optional[str] = ""
    # Advanced storyboard options
    advanced_mode: Optional[bool] = False  # Enable Gemini analysis + correction loops


class PipelineStageInfo(BaseModel):
    """Individual stage within a pipeline."""
    name: str
    status: str  # pending, running, complete, error
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    message: Optional[str] = None


class PipelineStatus(BaseModel):
    name: str
    status: str  # idle, running, complete, failed
    progress: float
    message: Optional[str] = None
    logs: Optional[list[str]] = None
    current_stage: Optional[str] = None  # Name of currently active stage
    stages: Optional[list[PipelineStageInfo]] = None  # Detailed stage tracking
    total_items: Optional[int] = None  # Total items being processed
    completed_items: Optional[int] = None  # Items completed so far
    current_item: Optional[str] = None  # Description of current item


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


@router.post("/cancel/{pipeline_id:path}")
async def cancel_pipeline(pipeline_id: str):
    """Cancel a running pipeline."""
    if pipeline_id in pipeline_status:
        current_status = pipeline_status[pipeline_id].get("status", "")
        if current_status == "running":
            pipeline_status[pipeline_id]["status"] = "cancelled"
            pipeline_status[pipeline_id]["message"] = "Cancellation requested..."
            _add_log(pipeline_id, "⚠️ Cancellation requested by user")
            return {"success": True, "message": "Cancellation requested"}
        else:
            return {"success": False, "message": f"Pipeline not running (status: {current_status})"}
    return {"success": False, "message": "Pipeline not found"}


@router.post("/writer", response_model=PipelineResponse)
@limiter.limit("2/minute")  # Limit writer pipeline to 2 requests per minute
async def run_writer_pipeline(request: Request, pipeline_request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the Writer pipeline."""
    pipeline_id = f"writer_{pipeline_request.project_path}"
    pipeline_status[pipeline_id] = {
        "name": "writer",
        "status": "running",
        "progress": 0,
        "message": "Starting...",
        "logs": ["Starting Writer pipeline..."]
    }
    background_tasks.add_task(
        execute_writer_pipeline,
        pipeline_id,
        pipeline_request.project_path,
        pipeline_request.llm,
        pipeline_request.media_type,
        pipeline_request.visual_style,
        pipeline_request.style_notes
    )
    return PipelineResponse(success=True, message="Writer pipeline started", pipeline_id=pipeline_id)


@router.post("/director", response_model=PipelineResponse)
@limiter.limit("2/minute")  # Limit director pipeline to 2 requests per minute
async def run_director_pipeline(request: Request, pipeline_request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the Director pipeline."""
    pipeline_id = f"director_{pipeline_request.project_path}"
    pipeline_status[pipeline_id] = {
        "name": "director",
        "status": "running",
        "progress": 0,
        "message": "Starting...",
        "logs": ["Starting Director pipeline..."]
    }
    background_tasks.add_task(
        execute_director_pipeline,
        pipeline_id,
        pipeline_request.project_path,
        pipeline_request.llm,
        pipeline_request.max_frames
    )
    return PipelineResponse(success=True, message="Director pipeline started", pipeline_id=pipeline_id)


@router.post("/references", response_model=PipelineResponse)
@limiter.limit("5/minute")  # Limit reference generation
async def run_references_pipeline(request: Request, pipeline_request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the References pipeline.

    Note: Reference image generation is typically done through the storyboard
    pipeline or manually. This endpoint is a placeholder for future dedicated
    reference generation functionality.
    """
    pipeline_id = f"references_{pipeline_request.project_path}"
    pipeline_status[pipeline_id] = {
        "name": "references",
        "status": "running",
        "progress": 0,
        "message": "Starting...",
        "logs": ["Starting References pipeline..."]
    }
    background_tasks.add_task(
        execute_references_pipeline,
        pipeline_id,
        pipeline_request.project_path,
        pipeline_request.image_model
    )
    return PipelineResponse(success=True, message="References pipeline started", pipeline_id=pipeline_id)


@router.post("/storyboard", response_model=PipelineResponse)
@limiter.limit("1/minute")  # Storyboard is most expensive - limit to 1 per minute
async def run_storyboard_pipeline(request: Request, pipeline_request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the Storyboard pipeline.

    If advanced_mode=True, uses the Advanced Storyboard Pipeline with:
    - Gemini analysis of each frame against script context
    - Correction loops for edit-capable models (P-Image-Edit)
    - Batch coherency checking within scenes
    """
    pipeline_id = f"storyboard_{pipeline_request.project_path}"

    if pipeline_request.advanced_mode:
        # Use standard pipeline WITH parallel healing enabled
        # This generates frames normally but runs continuity analysis in parallel
        pipeline_status[pipeline_id] = {
            "name": "storyboard_advanced",
            "status": "running",
            "progress": 0,
            "message": "Starting Advanced Storyboard with Parallel Healing...",
            "logs": ["Starting Storyboard pipeline with parallel continuity healing..."]
        }
        background_tasks.add_task(
            execute_storyboard_pipeline,
            pipeline_id,
            pipeline_request.project_path,
            pipeline_request.image_model,
            pipeline_request.max_frames,
            enable_healing=True  # Enable parallel healing
        )
        return PipelineResponse(success=True, message="Advanced Storyboard pipeline started with parallel healing", pipeline_id=pipeline_id)
    else:
        # Use standard pipeline without healing
        pipeline_status[pipeline_id] = {
            "name": "storyboard",
            "status": "running",
            "progress": 0,
            "message": "Starting...",
            "logs": ["Starting Storyboard pipeline..."]
        }
        background_tasks.add_task(
            execute_storyboard_pipeline,
            pipeline_id,
            pipeline_request.project_path,
            pipeline_request.image_model,
            pipeline_request.max_frames,
            enable_healing=False
        )
        return PipelineResponse(success=True, message="Storyboard pipeline started", pipeline_id=pipeline_id)


class RefinementRequest(BaseModel):
    """Request for prompt refinement."""
    project_path: str
    llm: Optional[str] = "claude-opus-4.5"
    min_confidence: Optional[float] = 0.6


@router.post("/refine-prompts", response_model=PipelineResponse)
@limiter.limit("2/minute")
async def run_prompt_refinement(request: Request, refinement_request: RefinementRequest, background_tasks: BackgroundTasks):
    """
    Run the Opus prompt refinement agent on visual_script.json.

    This refines prompts to counter common AI image generation issues:
    - Missing characters in multi-person shots
    - Tag leakage (tags rendering as visible text)
    - Costume/period inconsistency
    - Flat/posed/theatrical look
    - Generic expressions and backgrounds

    Output: visual_script_refined.json with improved prompts
    """
    pipeline_id = f"refinement_{refinement_request.project_path}"
    pipeline_status[pipeline_id] = {
        "name": "refinement",
        "status": "running",
        "progress": 0,
        "message": "Starting prompt refinement...",
        "logs": ["Starting Opus prompt refinement agent..."]
    }
    background_tasks.add_task(
        execute_prompt_refinement,
        pipeline_id,
        refinement_request.project_path,
        refinement_request.llm,
        refinement_request.min_confidence
    )
    return PipelineResponse(success=True, message="Prompt refinement started", pipeline_id=pipeline_id)




def _add_log(pipeline_id: str, message: str):
    """Add a log message to the pipeline status."""
    if pipeline_id in pipeline_status:
        if "logs" not in pipeline_status[pipeline_id]:
            pipeline_status[pipeline_id]["logs"] = []
        pipeline_status[pipeline_id]["logs"].append(message)
        pipeline_status[pipeline_id]["message"] = message


def _set_stage(pipeline_id: str, stage_name: str, status: str = "running", message: str = None):
    """Set or update a stage in the pipeline status."""
    from datetime import datetime
    if pipeline_id not in pipeline_status:
        return

    ps = pipeline_status[pipeline_id]
    if "stages" not in ps:
        ps["stages"] = []

    # Find existing stage or create new one
    existing = None
    for stage in ps["stages"]:
        if stage["name"] == stage_name:
            existing = stage
            break

    now = datetime.now().isoformat()

    if existing:
        existing["status"] = status
        if message:
            existing["message"] = message
        if status == "complete" or status == "error":
            existing["completed_at"] = now
    else:
        ps["stages"].append({
            "name": stage_name,
            "status": status,
            "started_at": now,
            "message": message
        })

    # Update current_stage
    if status == "running":
        ps["current_stage"] = stage_name
    elif status in ("complete", "error") and ps.get("current_stage") == stage_name:
        ps["current_stage"] = None


def _set_items_progress(pipeline_id: str, completed: int, total: int, current_item: str = None):
    """Update item-level progress for granular tracking."""
    if pipeline_id not in pipeline_status:
        return

    ps = pipeline_status[pipeline_id]
    ps["total_items"] = total
    ps["completed_items"] = completed
    if current_item:
        ps["current_item"] = current_item

    # Auto-calculate progress from items if we have total
    if total > 0:
        # Reserve 5% for init and 5% for finalization
        item_progress = completed / total
        ps["progress"] = 0.05 + (item_progress * 0.90)


async def execute_writer_pipeline(
    pipeline_id: str,
    project_path: str,
    llm: str,
    media_type: str = "standard",
    visual_style: str = "live_action",
    style_notes: str = ""
):
    """Execute the Writer pipeline.

    Generates script.md from pitch.md using the StoryPipeline.
    """
    from greenlight.pipelines.story_pipeline import StoryPipeline, StoryInput
    from greenlight.tags import TagRegistry

    project_dir = Path(project_path)

    try:
        _add_log(pipeline_id, "📖 Starting Writer Pipeline...")
        _set_stage(pipeline_id, "Loading Pitch", "running")
        pipeline_status[pipeline_id]["progress"] = 0.05

        # Load pitch
        pitch_path = project_dir / "world_bible" / "pitch.md"
        if not pitch_path.exists():
            raise FileNotFoundError("No pitch.md found. Create a pitch first.")

        pitch_content = pitch_path.read_text(encoding="utf-8")
        _add_log(pipeline_id, f"✓ Loaded pitch ({len(pitch_content)} chars)")
        _set_stage(pipeline_id, "Loading Pitch", "complete")
        pipeline_status[pipeline_id]["progress"] = 0.10

        # Load project config for title/genre
        project_config = {}
        config_path = project_dir / "project.json"
        if config_path.exists():
            project_config = json.loads(config_path.read_text(encoding="utf-8"))

        # Initialize LLM manager
        _set_stage(pipeline_id, "Initializing LLM", "running")
        _add_log(pipeline_id, "🔧 Initializing pipeline...")
        llm_manager = setup_llm_manager(llm)
        model_name = get_selected_llm_model(llm)
        _add_log(pipeline_id, f"  ✓ Using LLM: {model_name}")
        _set_stage(pipeline_id, "Initializing LLM", "complete")

        # Initialize pipeline
        tag_registry = TagRegistry()
        story_pipeline = StoryPipeline(
            llm_manager=llm_manager,
            tag_registry=tag_registry,
            project_path=str(project_dir)
        )
        pipeline_status[pipeline_id]["progress"] = 0.15

        # Create input
        story_input = StoryInput(
            raw_text=pitch_content,
            title=project_config.get("name", "Untitled"),
            genre=project_config.get("genre", "Drama"),
            visual_style=visual_style,
            style_notes=style_notes,
            project_size=media_type
        )

        # Run pipeline
        _set_stage(pipeline_id, "Story Generation", "running", "Generating script with LLM...")
        _add_log(pipeline_id, "🚀 Running story generation...")
        pipeline_status[pipeline_id]["progress"] = 0.20

        result = await story_pipeline.run(story_input)

        if result.success and result.output:
            _set_stage(pipeline_id, "Story Generation", "complete", f"{len(result.output.scenes)} scenes generated")
            _set_stage(pipeline_id, "Saving Outputs", "running")
            pipeline_status[pipeline_id]["progress"] = 0.90
            _add_log(pipeline_id, "💾 Saving outputs...")

            # Build script content from scenes
            script_lines = [f"# {result.output.title}\n"]
            if result.output.logline:
                script_lines.append(f"*{result.output.logline}*\n")
            script_lines.append("")

            for scene in result.output.scenes:
                if hasattr(scene, 'scene_number'):
                    scene_num = scene.scene_number
                    location_desc = getattr(scene, 'location_description', '')
                    content = getattr(scene, 'content', '')
                else:
                    scene_num = scene.get('scene_number', 1)
                    location_desc = scene.get('description', scene.get('location_description', ''))
                    content = scene.get('content', '')

                script_lines.append(f"## Scene {scene_num}:")
                if location_desc:
                    script_lines.append(location_desc)
                if content:
                    script_lines.append("")
                    script_lines.append(content)
                script_lines.append("")

            script_content = "\n".join(script_lines)

            # Save script
            scripts_dir = project_dir / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            script_path = scripts_dir / "script.md"
            script_path.write_text(script_content, encoding="utf-8")
            _add_log(pipeline_id, f"  ✓ Saved script.md ({len(result.output.scenes)} scenes)")

            # Save world_config.json
            world_bible_dir = project_dir / "world_bible"
            world_bible_dir.mkdir(parents=True, exist_ok=True)
            world_config_path = world_bible_dir / "world_config.json"

            world_config = {
                "title": result.output.title,
                "genre": result.output.genre,
                "visual_style": result.output.visual_style,
                "style_notes": result.output.style_notes,
                "logline": result.output.logline,
                "synopsis": result.output.synopsis,
                "themes": result.output.themes,
                "world_rules": result.output.world_rules,
                "lighting": result.output.lighting,
                "vibe": result.output.vibe,
                "characters": [
                    {
                        "tag": arc.character_tag,
                        "name": arc.character_name,
                        "role": arc.role,
                        "description": arc.appearance if hasattr(arc, 'appearance') else "",
                    }
                    for arc in result.output.character_arcs
                ] if result.output.character_arcs else [],
                "locations": [
                    {
                        "tag": loc.location_tag,
                        "name": loc.location_name,
                        "description": loc.description,
                    }
                    for loc in result.output.location_descriptions
                ] if result.output.location_descriptions else [],
                "props": [
                    {
                        "tag": prop.prop_tag,
                        "name": prop.prop_name,
                        "description": prop.description,
                    }
                    for prop in result.output.prop_descriptions
                ] if result.output.prop_descriptions else [],
                "all_tags": result.output.all_tags,
            }

            world_config_path.write_text(json.dumps(world_config, indent=2), encoding="utf-8")
            _add_log(pipeline_id, "  ✓ Saved world_config.json")
            _set_stage(pipeline_id, "Saving Outputs", "complete")

            pipeline_status[pipeline_id]["progress"] = 1.0
            pipeline_status[pipeline_id]["status"] = "complete"
            _add_log(pipeline_id, "✅ Writer pipeline complete!")
        else:
            _set_stage(pipeline_id, "Story Generation", "error", result.error)
            pipeline_status[pipeline_id]["status"] = "failed"
            _add_log(pipeline_id, f"❌ Pipeline failed: {result.error}")

    except Exception as e:
        logger.exception(f"Writer pipeline error: {e}")
        pipeline_status[pipeline_id]["status"] = "failed"
        _add_log(pipeline_id, f"❌ Error: {str(e)}")


async def execute_director_pipeline(
    pipeline_id: str,
    project_path: str,
    llm: str,
    max_frames: Optional[int]
):
    """Execute the Director pipeline.

    Transforms script.md into visual_script.json with scene.frame.camera notation.
    """
    from greenlight.pipelines.directing_pipeline import DirectingPipeline, DirectingInput

    project_dir = Path(project_path)

    try:
        _add_log(pipeline_id, "🎬 Starting Director Pipeline...")
        _set_stage(pipeline_id, "Loading Script", "running")
        pipeline_status[pipeline_id]["progress"] = 0.05

        # Load script
        script_path = project_dir / "scripts" / "script.md"
        if not script_path.exists():
            raise FileNotFoundError("No script.md found. Run Writer pipeline first.")

        script_content = script_path.read_text(encoding="utf-8")
        _add_log(pipeline_id, f"✓ Loaded script ({len(script_content)} chars)")
        _set_stage(pipeline_id, "Loading Script", "complete")
        pipeline_status[pipeline_id]["progress"] = 0.10

        # Load world config
        world_config = {}
        world_path = project_dir / "world_bible" / "world_config.json"
        if world_path.exists():
            world_config = json.loads(world_path.read_text(encoding="utf-8"))
            _add_log(pipeline_id, "✓ Loaded world config")

        # Initialize LLM manager
        _set_stage(pipeline_id, "Initializing LLM", "running")
        _add_log(pipeline_id, "🔧 Initializing pipeline...")
        llm_manager = setup_llm_manager(llm)
        model_name = get_selected_llm_model(llm)
        _add_log(pipeline_id, f"  ✓ Using LLM: {model_name}")
        _set_stage(pipeline_id, "Initializing LLM", "complete")
        pipeline_status[pipeline_id]["progress"] = 0.15

        # Create LLM caller function for the pipeline
        async def llm_caller(
            prompt: str,
            system_prompt: str = "",
            function: LLMFunction = LLMFunction.STORY_GENERATION
        ) -> str:
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
        _set_stage(pipeline_id, "Visual Script Generation", "running", "Generating shot-by-shot breakdown...")
        _add_log(pipeline_id, "🚀 Running directing pipeline...")
        pipeline_status[pipeline_id]["progress"] = 0.20

        result = await directing_pipeline.run(directing_input)

        if result.success and result.output:
            _set_stage(pipeline_id, "Visual Script Generation", "complete", f"{result.output.total_frames} frames across {len(result.output.scenes)} scenes")
            _set_stage(pipeline_id, "Saving Outputs", "running")
            pipeline_status[pipeline_id]["progress"] = 0.90
            _add_log(pipeline_id, "💾 Saving outputs...")

            # Create storyboard directory
            storyboard_dir = project_dir / "storyboard"
            storyboard_dir.mkdir(parents=True, exist_ok=True)

            # Save as markdown
            md_path = storyboard_dir / "visual_script.md"
            md_path.write_text(result.output.to_markdown(), encoding="utf-8")
            _add_log(pipeline_id, "  ✓ Saved visual_script.md")

            # Save as JSON with structured scenes array
            json_path = storyboard_dir / "visual_script.json"
            visual_script_dict = result.output.to_dict()
            json_path.write_text(json.dumps(visual_script_dict, indent=2), encoding="utf-8")
            _add_log(pipeline_id, "  ✓ Saved visual_script.json")

            # Save prompts.json for user editing before storyboard generation
            prompts_json = extract_prompts_from_visual_script(visual_script_dict)
            prompts_path = storyboard_dir / "prompts.json"
            prompts_path.write_text(json.dumps(prompts_json, indent=2), encoding="utf-8")
            _add_log(pipeline_id, f"  ✓ Saved prompts.json ({len(prompts_json)} prompts)")

            _set_stage(pipeline_id, "Saving Outputs", "complete")
            pipeline_status[pipeline_id]["progress"] = 1.0
            pipeline_status[pipeline_id]["status"] = "complete"
            _add_log(pipeline_id, f"✅ Director complete! Generated {result.output.total_frames} frames across {len(result.output.scenes)} scenes.")
        else:
            _set_stage(pipeline_id, "Visual Script Generation", "error", result.error)
            pipeline_status[pipeline_id]["status"] = "failed"
            _add_log(pipeline_id, f"❌ Pipeline failed: {result.error}")

    except Exception as e:
        logger.exception(f"Director pipeline error: {e}")
        pipeline_status[pipeline_id]["status"] = "failed"
        _add_log(pipeline_id, f"❌ Error: {str(e)}")


async def execute_references_pipeline(
    pipeline_id: str,
    project_path: str,
    image_model: str
):
    """Execute the References pipeline.

    Generates reference images for characters, locations, and props using
    the UnifiedReferenceScript which provides proper entity-specific handling:
    - Characters: Multi-angle character sheets via template-based prompts
    - Locations: 4 directional views (N/E/S/W) with spatial consistency
    - Props: Multi-angle product reference sheets
    """
    from greenlight.references.unified_reference_script import UnifiedReferenceScript
    from greenlight.core.image_handler import ImageModel

    project_dir = Path(project_path)

    try:
        _add_log(pipeline_id, "🎨 Starting References Pipeline...")
        pipeline_status[pipeline_id]["progress"] = 5

        # Load world config to count entities
        world_path = project_dir / "world_bible" / "world_config.json"
        if not world_path.exists():
            raise FileNotFoundError("No world_config.json found. Run Writer pipeline first.")

        world_config = json.loads(world_path.read_text(encoding="utf-8"))
        _add_log(pipeline_id, "✓ Loaded world config")

        # Count entities by type
        characters = [c for c in world_config.get("characters", []) if c.get("tag")]
        locations = [l for l in world_config.get("locations", []) if l.get("tag")]
        props = [p for p in world_config.get("props", []) if p.get("tag")]

        total_entities = len(characters) + len(locations) + len(props)

        if total_entities == 0:
            _add_log(pipeline_id, "⚠️ No entities found in world_config")
            pipeline_status[pipeline_id]["progress"] = 100
            pipeline_status[pipeline_id]["status"] = "complete"
            return

        _add_log(pipeline_id, f"📊 Found {len(characters)} characters, {len(locations)} locations, {len(props)} props")
        pipeline_status[pipeline_id]["progress"] = 10

        # Map image model
        model_mapping = {
            "seedream": ImageModel.SEEDREAM,
            "seedream_4_5": ImageModel.SEEDREAM,
            "nano_banana": ImageModel.NANO_BANANA,
            "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
            "flux_2_pro": ImageModel.FLUX_2_PRO,
            "p_image_edit": ImageModel.P_IMAGE_EDIT,
            "flux_1_1_pro": ImageModel.FLUX_1_1_PRO,
        }
        selected_model = model_mapping.get(image_model, ImageModel.SEEDREAM)
        _add_log(pipeline_id, f"🤖 Using model: {selected_model.value}")

        # Create progress callback
        def progress_callback(event: str, data: dict):
            tag = data.get("tag", "")
            if event == "generating_prompt":
                _add_log(pipeline_id, f"  📝 Generating prompt for {tag}...")
            elif event == "generating_image":
                _add_log(pipeline_id, f"  🎨 Generating image for {tag}...")

        # Initialize UnifiedReferenceScript
        ref_script = UnifiedReferenceScript(
            project_path=project_dir,
            callback=progress_callback
        )

        # Ensure references directory exists
        refs_dir = project_dir / "references"
        refs_dir.mkdir(parents=True, exist_ok=True)

        # Track results
        successful = 0
        failed = 0
        processed = 0

        # =====================================================================
        # PHASE 1: Generate Character Sheets
        # =====================================================================
        if characters:
            _add_log(pipeline_id, f"\n👤 Phase 1: Generating {len(characters)} character sheets...")

            for char in characters:
                tag = char["tag"]
                name = char.get("name", tag.replace("CHAR_", "").replace("_", " ").title())
                _add_log(pipeline_id, f"🎭 {name} [{tag}]")

                try:
                    result = await ref_script.generate_character_sheet(
                        tag=tag,
                        model=selected_model,
                        overwrite=False
                    )

                    if result.success:
                        successful += 1
                        if result.image_paths:
                            _add_log(pipeline_id, f"  ✓ Character sheet saved")
                        else:
                            _add_log(pipeline_id, f"  ✓ Sheet already exists (skipped)")
                    else:
                        failed += 1
                        _add_log(pipeline_id, f"  ❌ Failed: {result.error}")

                except Exception as e:
                    failed += 1
                    _add_log(pipeline_id, f"  ❌ Error: {str(e)}")
                    logger.exception(f"Character sheet error for {tag}: {e}")

                processed += 1
                progress = 10 + int(processed / total_entities * 85)
                pipeline_status[pipeline_id]["progress"] = progress

        # =====================================================================
        # PHASE 2: Generate Location Directional Views
        # =====================================================================
        if locations:
            _add_log(pipeline_id, f"\n🏛️ Phase 2: Generating {len(locations)} location views...")

            for loc in locations:
                tag = loc["tag"]
                name = loc.get("name", tag.replace("LOC_", "").replace("_", " ").title())
                _add_log(pipeline_id, f"📍 {name} [{tag}]")

                try:
                    result = await ref_script.generate_location_views(
                        tag=tag,
                        model=selected_model,
                        overwrite=False
                    )

                    if result.success:
                        successful += 1
                        view_count = len(result.image_paths)
                        if view_count > 0:
                            _add_log(pipeline_id, f"  ✓ {view_count} directional views saved (N/E/S/W)")
                        else:
                            _add_log(pipeline_id, f"  ✓ Views already exist (skipped)")
                    else:
                        failed += 1
                        _add_log(pipeline_id, f"  ❌ Failed: {result.error}")

                except Exception as e:
                    failed += 1
                    _add_log(pipeline_id, f"  ❌ Error: {str(e)}")
                    logger.exception(f"Location views error for {tag}: {e}")

                processed += 1
                progress = 10 + int(processed / total_entities * 85)
                pipeline_status[pipeline_id]["progress"] = progress

        # =====================================================================
        # PHASE 3: Generate Prop Reference Sheets
        # =====================================================================
        if props:
            _add_log(pipeline_id, f"\n🎁 Phase 3: Generating {len(props)} prop references...")

            for prop in props:
                tag = prop["tag"]
                name = prop.get("name", tag.replace("PROP_", "").replace("_", " ").title())
                _add_log(pipeline_id, f"🔧 {name} [{tag}]")

                try:
                    result = await ref_script.generate_prop_sheet(
                        tag=tag,
                        model=selected_model,
                        overwrite=False
                    )

                    if result.success:
                        successful += 1
                        if result.image_paths:
                            _add_log(pipeline_id, f"  ✓ Prop reference saved")
                        else:
                            _add_log(pipeline_id, f"  ✓ Reference already exists (skipped)")
                    else:
                        failed += 1
                        _add_log(pipeline_id, f"  ❌ Failed: {result.error}")

                except Exception as e:
                    failed += 1
                    _add_log(pipeline_id, f"  ❌ Error: {str(e)}")
                    logger.exception(f"Prop reference error for {tag}: {e}")

                processed += 1
                progress = 10 + int(processed / total_entities * 85)
                pipeline_status[pipeline_id]["progress"] = progress

        # =====================================================================
        # PHASE 4: Auto-label all reference images
        # =====================================================================
        _add_log(pipeline_id, f"\n🏷️ Phase 4: Auto-labeling reference images...")
        try:
            from greenlight.core.reference_labeler import label_all_references
            label_results = label_all_references(project_dir)
            total_labeled = sum(label_results.values())
            if total_labeled > 0:
                _add_log(pipeline_id, f"  ✓ Labeled {total_labeled} images with red tag strips")
            else:
                _add_log(pipeline_id, f"  ✓ All images already labeled")
        except Exception as e:
            logger.warning(f"Auto-labeling error: {e}")
            _add_log(pipeline_id, f"  ⚠️ Labeling warning: {str(e)}")

        # =====================================================================
        # Complete
        # =====================================================================
        pipeline_status[pipeline_id]["progress"] = 100
        pipeline_status[pipeline_id]["status"] = "complete"
        _add_log(pipeline_id, f"\n✅ References complete: {successful}/{total_entities} generated")

        if failed > 0:
            _add_log(pipeline_id, f"⚠️ {failed} references failed")

    except Exception as e:
        logger.exception(f"References pipeline error: {e}")
        pipeline_status[pipeline_id]["status"] = "failed"
        _add_log(pipeline_id, f"❌ Error: {str(e)}")


async def execute_storyboard_pipeline(
    pipeline_id: str,
    project_path: str,
    image_model: str,
    max_frames: Optional[int],
    enable_healing: bool = False
):
    """Execute the Storyboard pipeline.

    1. Reads prompts.json (user-edited) or visual_script.json from {project_path}/storyboard/
    2. For each frame, extracts tags and gets reference images with labels
    3. Uses prior frame as input within each scene (resets at scene boundaries)
    4. Uses ImageHandler to generate images with selected model
    5. Saves to {project_path}/storyboard_output/generated/
    6. Logs full prompts to {project_path}/storyboard_output/prompts_log.json
    """
    from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
    from datetime import datetime

    try:
        project_dir = Path(project_path)
        _add_log(pipeline_id, f"📂 Loading project: {project_dir.name}")

        # 1. Check for prompts.json first (user-edited prompts)
        prompts_json_path = project_dir / "storyboard" / "prompts.json"
        visual_script_path = project_dir / "storyboard" / "visual_script.json"

        frames = []
        using_edited_prompts = False

        if prompts_json_path.exists():
            try:
                prompts_data = json.loads(prompts_json_path.read_text(encoding='utf-8'))
                if prompts_data:
                    _add_log(pipeline_id, f"✓ Loaded prompts.json ({len(prompts_data)} prompts)")
                    using_edited_prompts = True

                    for prompt_entry in prompts_data:
                        frame = {
                            "frame_id": prompt_entry.get("frame_id", ""),
                            "prompt": prompt_entry.get("prompt", ""),
                            "tags": prompt_entry.get("tags", {}),
                            "location_direction": prompt_entry.get("location_direction", "NORTH"),
                            "camera_notation": prompt_entry.get("camera_notation", ""),
                            "position_notation": prompt_entry.get("position_notation", ""),
                            "lighting_notation": prompt_entry.get("lighting_notation", ""),
                            "_scene_num": prompt_entry.get("scene", ""),
                            "_edited": prompt_entry.get("edited", False),
                        }
                        frames.append(frame)

                    edited_count = sum(1 for f in frames if f.get("_edited", False))
                    if edited_count > 0:
                        _add_log(pipeline_id, f"📝 {edited_count} prompt(s) have been edited by user")
            except json.JSONDecodeError:
                _add_log(pipeline_id, "⚠️ Invalid prompts.json, falling back to visual_script.json")

        # Fallback to visual_script.json
        if not frames:
            if not visual_script_path.exists():
                raise FileNotFoundError(f"Visual script not found at {visual_script_path}")

            visual_script = json.loads(visual_script_path.read_text(encoding='utf-8'))
            _add_log(pipeline_id, "✓ Loaded visual script")

            for scene in visual_script.get("scenes", []):
                scene_num = scene.get("scene_number", scene.get("scene_id", ""))
                for frame in scene.get("frames", []):
                    frame["_scene_num"] = scene_num
                    frames.append(frame)

            if not frames and "visual_script" in visual_script:
                _add_log(pipeline_id, "📝 Parsing frames from raw visual script text...")
                raw_text = visual_script.get("visual_script", "")
                frames = parse_frames_from_raw_visual_script(raw_text)
                _add_log(pipeline_id, f"✓ Parsed {len(frames)} frames from text")

        total_frames = len(frames)
        if max_frames and max_frames < total_frames:
            frames = frames[:max_frames]
            total_frames = len(frames)

        _add_log(pipeline_id, f"📊 Found {total_frames} frames to generate")
        pipeline_status[pipeline_id]["progress"] = 0.05
        _set_stage(pipeline_id, "Initialization", "complete", f"Loaded {total_frames} frames")
        _set_stage(pipeline_id, "Image Generation", "running")

        # 3. Create output directory and prompts log
        output_dir = project_dir / "storyboard_output" / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)
        prompts_log_path = project_dir / "storyboard_output" / "prompts_log.json"
        prompts_log: List[Dict[str, Any]] = []
        _add_log(pipeline_id, f"📁 Output: {output_dir}")

        # 4. Initialize ImageHandler
        handler = ImageHandler(project_path=project_dir)

        # 4.5 Load character and entity data for prompt enhancement
        character_data = load_character_data(project_dir)
        entity_data = load_entity_data(project_dir)
        if character_data:
            _add_log(pipeline_id, f"📖 Loaded {len(character_data)} character profiles for consistency")
        if entity_data:
            _add_log(pipeline_id, f"📖 Loaded {len(entity_data)} entity descriptions for context")

        # 4.6 Load world config for lighting/vibe
        world_config = {}
        world_config_path = project_dir / "world_bible" / "world_config.json"
        if world_config_path.exists():
            try:
                world_config = json.loads(world_config_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                pass

        # 4.7 Group frames by scene for context building
        scene_frames_map: Dict[str, List[Dict[str, Any]]] = {}
        for frame in frames:
            scene_num = str(frame.get("_scene_num") or get_scene_from_frame_id(frame.get("frame_id", "")))
            if scene_num not in scene_frames_map:
                scene_frames_map[scene_num] = []
            scene_frames_map[scene_num].append(frame)

        # 5. Map image model string to ImageModel enum
        model_mapping = {
            "seedream": ImageModel.SEEDREAM,
            "seedream_4_5": ImageModel.SEEDREAM,
            "nano_banana": ImageModel.NANO_BANANA,
            "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
            "flux_2_pro": ImageModel.FLUX_2_PRO,
            "p_image_edit": ImageModel.P_IMAGE_EDIT,
            "flux_1_1_pro": ImageModel.FLUX_1_1_PRO,
        }
        selected_model = model_mapping.get(image_model, ImageModel.SEEDREAM)
        _add_log(pipeline_id, f"🤖 Using model: {selected_model.value}")

        # 5.5 Initialize parallel healing pipeline if enabled
        healing_pipeline = None
        healing_task = None
        if enable_healing:
            try:
                from greenlight.pipelines.parallel_healing_pipeline import (
                    ParallelHealingPipeline, create_generated_frame
                )

                # Build story context from synopsis
                story_context = world_config.get("synopsis", "") or world_config.get("logline", "")

                healing_pipeline = ParallelHealingPipeline(
                    project_path=project_dir,
                    image_model=selected_model,
                    log_callback=lambda msg: _add_log(pipeline_id, msg),
                    story_context=story_context,
                    world_config=world_config
                )

                # Start the healing worker in background
                healing_task = asyncio.create_task(healing_pipeline.healing_worker())
                _add_log(pipeline_id, "🔧 Parallel healing enabled - analyzing continuity as frames generate")
            except Exception as e:
                logger.warning(f"Failed to initialize healing pipeline: {e}")
                _add_log(pipeline_id, f"⚠️ Healing disabled: {e}")
                healing_pipeline = None

        # 6. Generate each frame with prior frame walking within scenes
        successful = 0
        failed = 0
        prior_frame_path: Optional[Path] = None
        prior_frame_prompt: Optional[str] = None
        current_scene: Optional[str] = None
        frame_idx_in_scene: int = 0

        for i, frame in enumerate(frames):
            # Check for cancellation at the start of each frame
            if pipeline_status.get(pipeline_id, {}).get("status") == "cancelled":
                _add_log(pipeline_id, f"🛑 Generation cancelled by user after {successful} frames")
                break

            frame_id = frame.get("frame_id", frame.get("id", f"frame_{i+1}"))
            prompt = frame.get("prompt", "")
            frame_scene = str(frame.get("_scene_num") or get_scene_from_frame_id(frame_id))
            location_direction = frame.get("location_direction", "NORTH")

            # Check if we're in a new scene - reset prior frame and counter
            if frame_scene != current_scene:
                prior_frame_path = None
                prior_frame_prompt = None
                current_scene = frame_scene
                frame_idx_in_scene = 0
                _add_log(pipeline_id, f"📍 Scene {frame_scene}")
            else:
                frame_idx_in_scene += 1

            if not prompt:
                _add_log(pipeline_id, f"⚠️ Skipping {frame_id}: no prompt")
                failed += 1
                continue

            # Extract tags from frame data first, fallback to prompt extraction
            frame_tags = frame.get("tags", {})
            if frame_tags and isinstance(frame_tags, dict):
                tags = (
                    frame_tags.get("characters", []) +
                    frame_tags.get("locations", []) +
                    frame_tags.get("props", [])
                )
            else:
                tags = extract_tags_from_prompt(prompt)

            # Build scene context for stateless prompting (do this early to get primary location)
            scene_frames = scene_frames_map.get(frame_scene, [])
            scene_context = build_scene_context(
                scene_frames,
                frame_idx_in_scene,
                entity_data,
                world_config
            )

            # Ensure frame has a location - use scene's primary location if missing
            frame_locations = [t for t in tags if t.startswith("LOC_")]
            if not frame_locations and scene_context.get("primary_location"):
                primary_loc = scene_context["primary_location"]
                tags.append(primary_loc)
                # Also add to tags_dict for logging
                if isinstance(frame_tags, dict):
                    if "locations" not in frame_tags:
                        frame_tags["locations"] = []
                    frame_tags["locations"].append(primary_loc)

            tag_refs: List[tuple] = []
            reference_images: List[Path] = []

            for tag in tags:
                direction = location_direction if tag.startswith("LOC_") else None
                ref_path = get_key_reference_for_tag(project_dir, tag, direction)
                if ref_path:
                    tag_refs.append((tag, ref_path))
                    reference_images.append(ref_path)

            # Add prior frame if we have one (within same scene)
            has_prior_frame = prior_frame_path is not None and prior_frame_path.exists()
            if has_prior_frame:
                reference_images.append(prior_frame_path)

            # Build stateless prompt with full scene context
            # Convert tags list to dict format expected by compress function
            tags_dict = {
                "characters": [t for t in tags if t.startswith("CHAR_")],
                "locations": [t for t in tags if t.startswith("LOC_")],
                "props": [t for t in tags if t.startswith("PROP_")]
            }
            labeled_prompt = build_stateless_prompt(
                base_prompt=prompt,
                scene_context=scene_context,
                tag_refs=tag_refs,
                prior_frame_prompt=prior_frame_prompt,
                has_prior_frame_image=has_prior_frame,
                tags=tags_dict,
                character_data=character_data,
                entity_data=entity_data,
                world_config=world_config
            )

            # Create output path for this frame
            clean_frame_id = frame_id.replace("[", "").replace("]", "")
            output_path = output_dir / f"{clean_frame_id}.png"

            ref_count = len(tag_refs) + (1 if has_prior_frame else 0)
            _add_log(pipeline_id, f"🎨 {frame_id} ({ref_count} refs{', +prior' if has_prior_frame else ''})")
            _set_items_progress(pipeline_id, i, total_frames, f"Generating {frame_id}")

            # Log the prompt
            prompt_log_entry = {
                "frame_id": clean_frame_id,
                "scene": str(frame_scene),
                "original_prompt": prompt,
                "full_prompt": labeled_prompt,
                "tags": tags,
                "location_direction": location_direction,
                "reference_images": [str(p) for p in reference_images],
                "has_prior_frame": has_prior_frame,
                "model": selected_model.value,
                "status": "pending",
                "timestamp": None,
                "output_path": str(output_path),
            }

            try:
                # Get time-of-day negative prompt to prevent moon in morning scenes, etc.
                time_negative = get_time_negative_prompt(prompt)

                request = ImageRequest(
                    prompt=labeled_prompt,
                    model=selected_model,
                    aspect_ratio="16:9",
                    reference_images=reference_images,
                    output_path=output_path,
                    tag=frame_id,
                    prefix_type="generate",
                    add_clean_suffix=True,
                    negative_prompt=time_negative
                )

                prompt_log_entry["timestamp"] = datetime.now().isoformat()

                result = await handler.generate(request)

                if result.success:
                    successful += 1
                    _add_log(pipeline_id, f"✓ {frame_id} saved")
                    prior_frame_path = output_path
                    prior_frame_prompt = prompt  # Save for next frame's context
                    prompt_log_entry["status"] = "success"

                    # Feed to healing pipeline if enabled
                    if healing_pipeline:
                        try:
                            gen_frame = create_generated_frame(frame, output_path, project_dir)
                            await healing_pipeline.add_frame(gen_frame)
                        except Exception as e:
                            logger.warning(f"Failed to add frame to healing queue: {e}")
                else:
                    failed += 1
                    _add_log(pipeline_id, f"❌ {frame_id}: {result.error}")
                    prompt_log_entry["status"] = "failed"
                    prompt_log_entry["error"] = result.error

            except Exception as e:
                failed += 1
                _add_log(pipeline_id, f"❌ {frame_id}: {str(e)}")
                logger.error(f"Error generating frame {frame_id}: {e}")
                prompt_log_entry["status"] = "error"
                prompt_log_entry["error"] = str(e)

            # Add to prompts log and save incrementally
            prompts_log.append(prompt_log_entry)
            prompts_log_path.write_text(json.dumps(prompts_log, indent=2), encoding='utf-8')

            # Update progress - use item-based progress tracking
            _set_items_progress(pipeline_id, i + 1, total_frames, None)

        # Check if was cancelled
        was_cancelled = pipeline_status.get(pipeline_id, {}).get("status") == "cancelled"

        # 6.5 Wait for healing pipeline to complete
        if healing_pipeline and healing_task:
            _set_stage(pipeline_id, "Continuity Healing", "running")
            _add_log(pipeline_id, "🔧 Waiting for healing analysis to complete...")
            try:
                await healing_pipeline.finish()
                await asyncio.wait_for(healing_task, timeout=300)  # 5 min max wait

                stats = healing_pipeline.get_statistics()
                _add_log(pipeline_id, f"✓ Healing complete: {stats['windows_analyzed']} windows analyzed, {stats['frames_healed']} frames healed")
                _set_stage(pipeline_id, "Continuity Healing", "complete",
                          f"{stats['frames_healed']} frames healed")
            except asyncio.TimeoutError:
                _add_log(pipeline_id, "⚠️ Healing timed out")
                _set_stage(pipeline_id, "Continuity Healing", "complete", "Timed out")
            except Exception as e:
                logger.warning(f"Healing completion error: {e}")
                _add_log(pipeline_id, f"⚠️ Healing error: {e}")
                _set_stage(pipeline_id, "Continuity Healing", "error", str(e))

        # 7. Mark generation complete
        _set_stage(pipeline_id, "Image Generation", "complete" if not was_cancelled else "cancelled",
                   f"{successful}/{total_frames} generated")

        # 8. Complete
        pipeline_status[pipeline_id]["progress"] = 1.0
        pipeline_status[pipeline_id]["current_item"] = None

        if was_cancelled:
            pipeline_status[pipeline_id]["status"] = "cancelled"
            _add_log(pipeline_id, f"🛑 Generation cancelled: {successful}/{total_frames} frames completed before cancellation")
        else:
            pipeline_status[pipeline_id]["status"] = "complete"
            _add_log(pipeline_id, f"✅ Storyboard complete: {successful}/{total_frames} frames generated")
            if failed > 0:
                _add_log(pipeline_id, f"⚠️ {failed} frames failed")

    except Exception as e:
        logger.error(f"Storyboard pipeline error: {e}")
        pipeline_status[pipeline_id]["status"] = "failed"
        _add_log(pipeline_id, f"❌ Error: {str(e)}")


async def execute_advanced_storyboard_pipeline(
    pipeline_id: str,
    project_path: str,
    image_model: str,
    max_frames: Optional[int]
):
    """Execute the Advanced Storyboard pipeline with Gemini analysis.

    This pipeline adds AI-powered analysis and correction:
    1. Generate initial frames with selected image model
    2. Gemini analyzes each frame against script context
    3. Correction loop for edit-capable models (P-Image-Edit)
    4. Batch coherency check across frames in each scene
    """
    from greenlight.pipelines.advanced_storyboard_pipeline import AdvancedStoryboardPipeline
    from greenlight.core.image_handler import ImageModel

    try:
        project_dir = Path(project_path)
        _add_log(pipeline_id, f"📂 Loading project: {project_dir.name}")
        _set_stage(pipeline_id, "Initialization", "running")
        pipeline_status[pipeline_id]["progress"] = 0.05

        # Load visual script
        vs_path = project_dir / "storyboard" / "visual_script.json"
        prompts_path = project_dir / "storyboard" / "prompts.json"

        frames = []

        # Try prompts.json first (user-edited)
        if prompts_path.exists():
            try:
                prompts_data = json.loads(prompts_path.read_text(encoding='utf-8'))
                if prompts_data:
                    _add_log(pipeline_id, f"✓ Loaded prompts.json ({len(prompts_data)} prompts)")
                    for prompt_entry in prompts_data:
                        frame = {
                            "frame_id": prompt_entry.get("frame_id", ""),
                            "prompt": prompt_entry.get("prompt", ""),
                            "tags": prompt_entry.get("tags", {}),
                            "location_direction": prompt_entry.get("location_direction", "NORTH"),
                            "camera_notation": prompt_entry.get("camera_notation", ""),
                            "position_notation": prompt_entry.get("position_notation", ""),
                            "lighting_notation": prompt_entry.get("lighting_notation", ""),
                            "visual_description": prompt_entry.get("visual_description", ""),
                            "_scene_num": prompt_entry.get("scene", "1"),
                        }
                        frames.append(frame)
            except json.JSONDecodeError:
                _add_log(pipeline_id, "⚠️ Invalid prompts.json, falling back to visual_script.json")

        # Fallback to visual_script.json
        if not frames:
            if not vs_path.exists():
                raise FileNotFoundError(f"Visual script not found at {vs_path}")

            visual_script = json.loads(vs_path.read_text(encoding='utf-8'))
            _add_log(pipeline_id, "✓ Loaded visual_script.json")

            for scene in visual_script.get("scenes", []):
                scene_num = scene.get("scene_number", "1")
                for frame in scene.get("frames", []):
                    frame["_scene_num"] = scene_num
                    frames.append(frame)

        if max_frames and max_frames < len(frames):
            frames = frames[:max_frames]
            _add_log(pipeline_id, f"⚠️ Limited to {max_frames} frames")

        total_frames = len(frames)
        _add_log(pipeline_id, f"📊 Found {total_frames} frames to process")
        _set_stage(pipeline_id, "Initialization", "complete", f"{total_frames} frames loaded")

        # Load world config
        world_config = {}
        wc_path = project_dir / "world_bible" / "world_config.json"
        if wc_path.exists():
            world_config = json.loads(wc_path.read_text(encoding='utf-8'))
            _add_log(pipeline_id, f"✓ Loaded world config")

        # Map image model
        model_mapping = {
            "seedream": ImageModel.SEEDREAM,
            "seedream_4_5": ImageModel.SEEDREAM,
            "nano_banana": ImageModel.NANO_BANANA,
            "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
            "flux_2_pro": ImageModel.FLUX_2_PRO,
            "p_image_edit": ImageModel.P_IMAGE_EDIT,
            "flux_1_1_pro": ImageModel.FLUX_1_1_PRO,
        }
        selected_model = model_mapping.get(image_model, ImageModel.SEEDREAM)
        _add_log(pipeline_id, f"🤖 Using model: {selected_model.value}")

        # Check if editing is supported
        supports_editing = selected_model in [
            ImageModel.P_IMAGE_EDIT,
            ImageModel.FLUX_2_PRO,
            ImageModel.SEEDREAM
        ]
        if supports_editing:
            _add_log(pipeline_id, "✓ Edit mode enabled (correction loops active)")
        else:
            _add_log(pipeline_id, "ℹ️ Analysis-only mode (no correction loops)")

        # Create callbacks
        def log_cb(msg: str):
            _add_log(pipeline_id, msg)

        def progress_cb(p: float):
            pipeline_status[pipeline_id]["progress"] = p

        def stage_cb(name: str, status: str, message: str = None):
            _set_stage(pipeline_id, name, status, message)

        # Initialize and run pipeline
        _set_stage(pipeline_id, "Image Generation", "running", "Generating and analyzing frames...")
        pipeline = AdvancedStoryboardPipeline(
            project_path=project_dir,
            image_model=selected_model,
            log_callback=log_cb,
            progress_callback=progress_cb,
            stage_callback=stage_cb
        )

        results, metrics = await pipeline.process_frames(frames, world_config)

        # Save report
        report = {
            "timestamp": datetime.now().isoformat(),
            "model": selected_model.value,
            "advanced_mode": True,
            "metrics": metrics,
            "frames": [
                {
                    "frame_id": r.frame_id,
                    "image": str(r.image_path) if r.image_path else None,
                    "score": r.score,
                    "iterations": r.iteration,
                    "passed": r.passed,
                    "corrections": r.corrections_applied,
                    "analysis": r.analysis
                }
                for r in results
            ]
        }
        report_path = project_dir / "storyboard_output" / f"advanced_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        _add_log(pipeline_id, f"📝 Report saved: {report_path.name}")

        # Complete
        pipeline_status[pipeline_id]["progress"] = 1.0
        pipeline_status[pipeline_id]["status"] = "complete"
        _add_log(pipeline_id, f"✅ Advanced Storyboard complete!")
        _add_log(pipeline_id, f"   Passed: {metrics['passed']}/{metrics['total']} ({metrics['pass_rate']:.0f}%)")
        _add_log(pipeline_id, f"   Avg Score: {metrics['avg_score']:.1f}/10")
        _add_log(pipeline_id, f"   Corrections Applied: {metrics['total_corrections']}")

    except Exception as e:
        logger.exception(f"Advanced storyboard pipeline error: {e}")
        pipeline_status[pipeline_id]["status"] = "failed"
        _add_log(pipeline_id, f"❌ Error: {str(e)}")


async def execute_prompt_refinement(
    pipeline_id: str,
    project_path: str,
    llm: str,
    min_confidence: float
):
    """
    Execute the Opus prompt refinement agent.

    Analyzes and fixes visual prompts to counter common AI image generation issues.
    """
    from greenlight.agents.prompt_refinement_agent import refine_visual_script

    try:
        project_dir = Path(project_path)
        _add_log(pipeline_id, f"📂 Loading project: {project_dir.name}")
        _set_stage(pipeline_id, "Loading Visual Script", "running")
        pipeline_status[pipeline_id]["progress"] = 0.05

        # Check for visual script
        vs_path = project_dir / "storyboard" / "visual_script.json"
        if not vs_path.exists():
            raise FileNotFoundError(f"Visual script not found at {vs_path}")

        # Load world config for character data
        world_config = {}
        wc_path = project_dir / "world_bible" / "world_config.json"
        if wc_path.exists():
            world_config = json.loads(wc_path.read_text(encoding='utf-8'))
            _add_log(pipeline_id, f"✓ Loaded world config ({len(world_config.get('characters', []))} characters)")

        _set_stage(pipeline_id, "Loading Visual Script", "complete")

        # Initialize LLM
        _set_stage(pipeline_id, "Initializing LLM", "running")
        llm_manager = setup_llm_manager(llm)
        model_name = get_selected_llm_model(llm)
        _add_log(pipeline_id, f"🤖 Using LLM: {model_name}")
        _set_stage(pipeline_id, "Initializing LLM", "complete")
        pipeline_status[pipeline_id]["progress"] = 0.15

        # Create LLM caller wrapper
        async def llm_caller(prompt: str, system_prompt: str = "", **kwargs):
            return await llm_manager.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                function=LLMFunction.STORY_ANALYSIS
            )

        # Run refinement
        _set_stage(pipeline_id, "Refining Prompts", "running", "Analyzing and fixing prompts...")
        _add_log(pipeline_id, "🔧 Starting prompt refinement (this may take a while)...")
        pipeline_status[pipeline_id]["progress"] = 0.25

        # Get visual style from project config if available
        visual_style = ""
        project_config_path = project_dir / "project.json"
        if project_config_path.exists():
            project_config = json.loads(project_config_path.read_text(encoding='utf-8'))
            visual_style = project_config.get("visual_style", "")

        result = await refine_visual_script(
            project_path=project_dir,
            llm_caller=llm_caller,
            world_config=world_config,
            visual_style=visual_style,
            min_confidence=min_confidence
        )

        if "error" in result:
            raise Exception(result["error"])

        _set_stage(pipeline_id, "Refining Prompts", "complete",
                   f"{result['applied']}/{result['total']} prompts refined")
        _add_log(pipeline_id, f"✅ Refinement complete:")
        _add_log(pipeline_id, f"   Applied: {result['applied']} prompts")
        _add_log(pipeline_id, f"   Skipped: {result['skipped']} prompts (low confidence)")
        _add_log(pipeline_id, f"   Output: {result['output_path']}")

        pipeline_status[pipeline_id]["progress"] = 1.0
        pipeline_status[pipeline_id]["status"] = "complete"
        _add_log(pipeline_id, "📝 Use visual_script_refined.json for storyboard generation")

    except Exception as e:
        logger.error(f"Prompt refinement error: {e}")
        pipeline_status[pipeline_id]["status"] = "failed"
        _add_log(pipeline_id, f"❌ Error: {str(e)}")


