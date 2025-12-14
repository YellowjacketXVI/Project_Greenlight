"""Writer pipeline router for Project Greenlight API."""

import asyncio
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()


class PitchData(BaseModel):
    title: str = ""
    logline: str = ""
    genre: str = ""
    synopsis: str = ""
    characters: str = ""
    locations: str = ""


class WriterConfig(BaseModel):
    project_path: str
    llm: str = "claude-sonnet-4.5"
    media_type: str = "standard"
    visual_style: str = "live_action"
    style_notes: str = ""
    pitch: Optional[PitchData] = None


class WriterResponse(BaseModel):
    success: bool
    message: str
    pipeline_id: Optional[str] = None


class ProjectPreset(BaseModel):
    key: str
    name: str
    total_words: int
    scenes: int
    shots: int
    media_type: str


# Project size presets from WriterDialog
PROJECT_PRESETS = {
    "short": {"name": "Short (100-150 words)", "total_words": 125, "scenes": 1, "shots": 3, "media_type": "short"},
    "brief": {"name": "Brief (250-500 words)", "total_words": 375, "scenes": 3, "shots": 9, "media_type": "brief"},
    "standard": {"name": "Standard (750-1000 words)", "total_words": 875, "scenes": 8, "shots": 24, "media_type": "standard"},
    "extended": {"name": "Extended (1250-1500 words)", "total_words": 1375, "scenes": 15, "shots": 45, "media_type": "extended"},
    "feature": {"name": "Feature (2000-3000 words)", "total_words": 2500, "scenes": 40, "shots": 120, "media_type": "feature"},
}

VISUAL_STYLES = [
    {"key": "live_action", "name": "Live Action"},
    {"key": "anime", "name": "Anime"},
    {"key": "animation_2d", "name": "2D Animation"},
    {"key": "animation_3d", "name": "3D Animation"},
    {"key": "mixed_reality", "name": "Mixed Reality"},
]


@router.get("/presets")
async def get_presets():
    """Get available project size presets."""
    return {"presets": [{"key": k, **v} for k, v in PROJECT_PRESETS.items()]}


@router.get("/visual-styles")
async def get_visual_styles():
    """Get available visual styles."""
    return {"styles": VISUAL_STYLES}


@router.get("/{project_path:path}/pitch")
async def get_pitch(project_path: str):
    """Get pitch data from project."""
    project_dir = Path(project_path)
    pitch_path = project_dir / "world_bible" / "pitch.md"
    
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
            if stripped.startswith("# ") and not stripped.startswith("## "):
                result["title"] = stripped[2:].strip()
            elif stripped.startswith("## "):
                if current_section and section_content:
                    result[current_section] = "\n".join(section_content).strip()
                header = stripped[3:].strip().lower()
                current_section = header if header in result else None
                section_content = []
            elif current_section:
                section_content.append(line)
        
        if current_section and section_content:
            result[current_section] = "\n".join(section_content).strip()
    except Exception:
        pass
    
    return result


@router.post("/{project_path:path}/pitch")
async def save_pitch(project_path: str, pitch: PitchData):
    """Save pitch data to project."""
    project_dir = Path(project_path)
    pitch_path = project_dir / "world_bible" / "pitch.md"
    pitch_path.parent.mkdir(parents=True, exist_ok=True)
    
    lines = [
        f"# {pitch.title}" if pitch.title else "# Untitled Project",
        "", "## Logline", pitch.logline or "(No logline provided)",
        "", "## Genre", pitch.genre or "(No genre specified)",
    ]
    if pitch.characters:
        lines.extend(["", "## Characters", pitch.characters])
    if pitch.locations:
        lines.extend(["", "## Locations", pitch.locations])
    lines.extend(["", "## Type", "Single Project", "", "## Synopsis", pitch.synopsis or "(No synopsis provided)", ""])
    
    pitch_path.write_text("\n".join(lines), encoding="utf-8")
    return {"success": True, "message": "Pitch saved"}


@router.get("/{project_path:path}/style")
async def get_style(project_path: str):
    """Get style configuration from world_config.json."""
    import json
    project_dir = Path(project_path)
    config_path = project_dir / "world_bible" / "world_config.json"

    result = {"visual_style": "live_action", "style_notes": "", "lighting": "", "vibe": ""}

    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            result["visual_style"] = config.get("visual_style", "live_action")
            result["style_notes"] = config.get("style_notes", "")
            result["lighting"] = config.get("lighting", "")
            result["vibe"] = config.get("vibe", "")
        except Exception:
            pass

    return result


# Pipeline execution state
_pipeline_status = {}


@router.post("/run")
async def run_writer_pipeline(config: WriterConfig, background_tasks: BackgroundTasks):
    """Start the writer pipeline in background."""
    import uuid
    pipeline_id = str(uuid.uuid4())[:8]
    _pipeline_status[pipeline_id] = {"status": "starting", "progress": 0, "logs": []}

    background_tasks.add_task(_execute_writer_pipeline, pipeline_id, config)
    return WriterResponse(success=True, message="Pipeline started", pipeline_id=pipeline_id)


@router.get("/status/{pipeline_id}")
async def get_pipeline_status(pipeline_id: str):
    """Get status of a running pipeline."""
    if pipeline_id not in _pipeline_status:
        return {"error": "Pipeline not found"}
    return _pipeline_status[pipeline_id]


async def _execute_writer_pipeline(pipeline_id: str, config: WriterConfig):
    """Execute the writer pipeline."""
    import json
    from greenlight.pipelines.story_pipeline import StoryPipeline, StoryInput
    from greenlight.llm import LLMManager
    from greenlight.tags import TagRegistry
    from greenlight.core.config import GreenlightConfig, FunctionLLMMapping, get_config
    from greenlight.core.constants import LLMFunction

    status = _pipeline_status[pipeline_id]
    project_path = Path(config.project_path)

    def log(msg: str):
        status["logs"].append(msg)

    def update_progress(p: float):
        status["progress"] = p

    try:
        status["status"] = "running"
        log("📖 Starting Writer Pipeline...")
        update_progress(0.05)

        # Save pitch if provided
        if config.pitch:
            await save_pitch(config.project_path, config.pitch)
            log("✓ Saved pitch")

        # Load pitch
        pitch_path = project_path / "world_bible" / "pitch.md"
        pitch_content = pitch_path.read_text(encoding="utf-8") if pitch_path.exists() else ""
        log(f"✓ Loaded pitch ({len(pitch_content)} chars)")
        update_progress(0.1)

        # Initialize pipeline
        log("🔧 Initializing pipeline...")
        base_config = get_config()
        custom_config = GreenlightConfig()
        custom_config.llm_configs = base_config.llm_configs.copy()
        custom_config.function_mappings = {}

        llm_id_config = config.llm.replace("-", "_")
        selected_config = custom_config.llm_configs.get(llm_id_config)
        if not selected_config:
            selected_config = next(iter(custom_config.llm_configs.values()))

        for function in LLMFunction:
            custom_config.function_mappings[function] = FunctionLLMMapping(
                function=function, primary_config=selected_config, fallback_config=None
            )

        log(f"  ✓ Using LLM: {selected_config.model}")
        llm_manager = LLMManager(custom_config)
        tag_registry = TagRegistry()
        story_pipeline = StoryPipeline(
            llm_manager=llm_manager, tag_registry=tag_registry, project_path=str(project_path)
        )
        update_progress(0.15)

        # Create input
        project_config = {}
        config_path = project_path / "project.json"
        if config_path.exists():
            project_config = json.loads(config_path.read_text(encoding="utf-8"))

        story_input = StoryInput(
            raw_text=pitch_content,
            title=project_config.get("name", "Untitled"),
            genre=project_config.get("genre", "Drama"),
            visual_style=config.visual_style,
            style_notes=config.style_notes,
            project_size=config.media_type
        )

        # Run pipeline
        log("🚀 Running story generation...")
        result = await story_pipeline.run(story_input)

        if result.success and result.output:
            update_progress(0.9)
            log("💾 Saving outputs...")

            # Save script
            scripts_dir = project_path / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            script_path = scripts_dir / "script.md"
            script_path.write_text(result.output.script, encoding="utf-8")
            log(f"  ✓ Saved script.md")

            update_progress(1.0)
            log("✅ Writer pipeline complete!")
            status["status"] = "complete"
        else:
            log(f"❌ Pipeline failed: {result.error}")
            status["status"] = "failed"
            status["error"] = result.error
    except Exception as e:
        log(f"❌ Error: {e}")
        status["status"] = "failed"
        status["error"] = str(e)

