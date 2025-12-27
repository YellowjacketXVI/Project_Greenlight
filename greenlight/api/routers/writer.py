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
    llm: str = "claude-haiku-4.5"
    media_type: str = "dynamic"  # Changed default to dynamic
    visual_style: str = "live_action"
    style_notes: str = ""
    pitch: Optional[PitchData] = None
    dynamic_scenes: bool = True  # Enable pitch-driven scene count by default


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
    "dynamic": {"name": "Dynamic (Pitch-Driven)", "total_words": 0, "scenes": 0, "shots": 0, "media_type": "dynamic"},
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


@router.post("/{project_path:path}/analyze-pitch")
async def analyze_pitch(project_path: str):
    """Analyze pitch and return recommended scene count."""
    from greenlight.core.pitch_analyzer import PitchAnalyzer

    project_dir = Path(project_path)
    pitch_path = project_dir / "world_bible" / "pitch.md"

    if not pitch_path.exists():
        return {"error": "No pitch found", "recommended_scenes": 8}

    pitch_content = pitch_path.read_text(encoding="utf-8")

    # Extract genre from pitch if available
    genre = ""
    for line in pitch_content.split("\n"):
        if line.strip().lower().startswith("## genre"):
            # Next non-empty line is the genre
            idx = pitch_content.find(line) + len(line)
            remaining = pitch_content[idx:].strip().split("\n")
            for g in remaining:
                if g.strip() and not g.startswith("#"):
                    genre = g.strip()
                    break
            break

    analyzer = PitchAnalyzer()
    metrics = analyzer.analyze(pitch_content, genre)

    return {
        "recommended_scenes": metrics.recommended_scenes,
        "min_scenes": metrics.min_scenes,
        "max_scenes": metrics.max_scenes,
        "words_per_scene": metrics.words_per_scene,
        "total_words": metrics.recommended_scenes * metrics.words_per_scene,
        "complexity_score": metrics.complexity_score,
        "reasoning": metrics.reasoning,
        "metrics": {
            "characters": metrics.character_count,
            "locations": metrics.location_count,
            "plot_beats": metrics.plot_beat_count,
            "conflicts": metrics.conflict_count,
            "time_span": metrics.time_span_indicator,
        }
    }


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
    _pipeline_status[pipeline_id] = {
        "status": "starting",
        "progress": 0,
        "logs": [],
        "stages": [],
        "current_stage": None
    }

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

    from datetime import datetime
    status = _pipeline_status[pipeline_id]
    project_path = Path(config.project_path)

    def log(msg: str):
        status["logs"].append(msg)

    def update_progress(p: float):
        status["progress"] = p

    def set_stage(name: str, stage_status: str = "running", message: str = None):
        """Set or update a stage in the pipeline status."""
        # Find existing stage or create new one
        existing = None
        for stage in status.get("stages", []):
            if stage["name"] == name:
                existing = stage
                break

        now = datetime.now().isoformat()

        if existing:
            existing["status"] = stage_status
            if message:
                existing["message"] = message
            if stage_status in ("complete", "error"):
                existing["completed_at"] = now
        else:
            if "stages" not in status:
                status["stages"] = []
            status["stages"].append({
                "name": name,
                "status": stage_status,
                "started_at": now,
                "message": message
            })

        # Update current_stage
        if stage_status == "running":
            status["current_stage"] = name
        elif stage_status in ("complete", "error") and status.get("current_stage") == name:
            status["current_stage"] = None

    try:
        status["status"] = "running"
        set_stage("Loading Pitch", "running")
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
        set_stage("Loading Pitch", "complete")
        update_progress(0.1)

        # Initialize pipeline
        set_stage("Initializing LLM", "running")
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
        set_stage("Initializing LLM", "complete")
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
            project_size=config.media_type,
            dynamic_scenes=config.dynamic_scenes
        )

        # Run pipeline
        set_stage("Story Generation", "running", "Generating script with LLM...")
        log("🚀 Running story generation...")
        result = await story_pipeline.run(story_input)

        if result.success and result.output:
            set_stage("Story Generation", "complete", f"{len(result.output.scenes)} scenes generated")
            set_stage("Saving Outputs", "running")
            update_progress(0.9)
            log("💾 Saving outputs...")

            # Build script content from scenes
            script_lines = [f"# {result.output.title}\n"]
            if result.output.logline:
                script_lines.append(f"*{result.output.logline}*\n")
            script_lines.append("")

            for scene in result.output.scenes:
                # Handle both Scene dataclass and dict formats
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
            scripts_dir = project_path / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            script_path = scripts_dir / "script.md"
            script_path.write_text(script_content, encoding="utf-8")
            log(f"  ✓ Saved script.md ({len(result.output.scenes)} scenes)")

            # Save world_config.json
            world_bible_dir = project_path / "world_bible"
            world_bible_dir.mkdir(parents=True, exist_ok=True)
            world_config_path = world_bible_dir / "world_config.json"

            # Build world config from output
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

            import json
            world_config_path.write_text(json.dumps(world_config, indent=2), encoding="utf-8")
            log(f"  ✓ Saved world_config.json")
            set_stage("Saving Outputs", "complete")

            update_progress(1.0)
            log("✅ Writer pipeline complete!")
            status["status"] = "complete"
            status["current_stage"] = None
        else:
            set_stage("Story Generation", "error", result.error)
            log(f"❌ Pipeline failed: {result.error}")
            status["status"] = "failed"
            status["error"] = result.error
    except Exception as e:
        log(f"❌ Error: {e}")
        status["status"] = "failed"
        status["error"] = str(e)

