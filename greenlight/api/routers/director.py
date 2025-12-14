"""Director pipeline router for Project Greenlight API."""

import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()


class DirectorConfig(BaseModel):
    project_path: str
    llm: str = "claude-sonnet-4.5"


class DirectorResponse(BaseModel):
    success: bool
    message: str
    pipeline_id: Optional[str] = None


# Pipeline execution state
_pipeline_status = {}


@router.get("/{project_path:path}/script")
async def get_script_data(project_path: str):
    """Get script data for director pipeline."""
    import json
    import re
    project_dir = Path(project_path)
    script_path = project_dir / "scripts" / "script.md"
    
    if not script_path.exists():
        return {"exists": False, "scenes": [], "total_scenes": 0}
    
    content = script_path.read_text(encoding="utf-8")
    scenes = []
    
    # Parse scenes from script
    scene_pattern = re.compile(r'^## Scene (\d+)(?::\s*(.*))?$', re.MULTILINE)
    matches = list(scene_pattern.finditer(content))
    
    for i, match in enumerate(matches):
        scene_num = int(match.group(1))
        scene_title = match.group(2) or f"Scene {scene_num}"
        
        # Get scene content
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        scene_content = content[start:end].strip()
        
        # Extract metadata from scene content
        location = ""
        time = ""
        characters = []
        
        loc_match = re.search(r'\*\*Location:\*\*\s*(.+)', scene_content)
        if loc_match:
            location = loc_match.group(1).strip()
        
        time_match = re.search(r'\*\*Time:\*\*\s*(.+)', scene_content)
        if time_match:
            time = time_match.group(1).strip()
        
        char_match = re.search(r'\*\*Characters:\*\*\s*(.+)', scene_content)
        if char_match:
            characters = [c.strip() for c in char_match.group(1).split(",")]
        
        scenes.append({
            "scene_number": scene_num,
            "title": scene_title,
            "location": location,
            "time": time,
            "characters": characters,
            "content_preview": scene_content[:200] + "..." if len(scene_content) > 200 else scene_content
        })
    
    return {"exists": True, "scenes": scenes, "total_scenes": len(scenes)}


@router.post("/run")
async def run_director_pipeline(config: DirectorConfig, background_tasks: BackgroundTasks):
    """Start the director pipeline in background."""
    import uuid
    pipeline_id = str(uuid.uuid4())[:8]
    _pipeline_status[pipeline_id] = {"status": "starting", "progress": 0, "logs": []}
    
    background_tasks.add_task(_execute_director_pipeline, pipeline_id, config)
    return DirectorResponse(success=True, message="Pipeline started", pipeline_id=pipeline_id)


@router.get("/status/{pipeline_id}")
async def get_pipeline_status(pipeline_id: str):
    """Get status of a running pipeline."""
    if pipeline_id not in _pipeline_status:
        return {"error": "Pipeline not found"}
    return _pipeline_status[pipeline_id]


async def _execute_director_pipeline(pipeline_id: str, config: DirectorConfig):
    """Execute the director pipeline."""
    import json
    from greenlight.pipelines.directing_pipeline import DirectingPipeline, DirectingInput
    from greenlight.llm import LLMManager
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
        log("🎬 Starting Director Pipeline...")
        update_progress(0.05)
        
        # Load script
        script_path = project_path / "scripts" / "script.md"
        if not script_path.exists():
            raise FileNotFoundError("No script.md found. Run Writer pipeline first.")
        
        script_content = script_path.read_text(encoding="utf-8")
        log(f"✓ Loaded script ({len(script_content)} chars)")
        update_progress(0.1)
        
        # Load world config
        world_config = {}
        world_path = project_path / "world_bible" / "world_config.json"
        if world_path.exists():
            world_config = json.loads(world_path.read_text(encoding="utf-8"))
            log("✓ Loaded world config")
        
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
        directing_pipeline = DirectingPipeline(llm_manager=llm_manager, project_path=str(project_path))
        update_progress(0.15)
        
        # Create input
        directing_input = DirectingInput(
            script=script_content,
            world_config=world_config,
            project_path=str(project_path)
        )
        
        # Run pipeline
        log("🚀 Running directing pipeline...")
        result = await directing_pipeline.run(directing_input)
        
        if result.success and result.output:
            update_progress(0.9)
            log("💾 Saving outputs...")
            
            # Save visual script
            storyboard_dir = project_path / "storyboard"
            storyboard_dir.mkdir(parents=True, exist_ok=True)
            
            # Save as markdown
            md_path = storyboard_dir / "visual_script.md"
            md_path.write_text(result.output.to_markdown(), encoding="utf-8")
            log(f"  ✓ Saved visual_script.md")
            
            # Save as JSON
            json_path = storyboard_dir / "visual_script.json"
            json_path.write_text(json.dumps(result.output.to_dict(), indent=2), encoding="utf-8")
            log(f"  ✓ Saved visual_script.json")
            
            update_progress(1.0)
            log(f"✅ Director complete! Generated {result.output.total_frames} frames.")
            status["status"] = "complete"
            status["result"] = {"total_frames": result.output.total_frames, "total_scenes": len(result.output.scenes)}
        else:
            log(f"❌ Pipeline failed: {result.error}")
            status["status"] = "failed"
            status["error"] = result.error
    except Exception as e:
        log(f"❌ Error: {e}")
        status["status"] = "failed"
        status["error"] = str(e)

