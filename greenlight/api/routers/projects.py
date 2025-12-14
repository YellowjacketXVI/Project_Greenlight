"""Projects router for Project Greenlight API."""

import json
import os
import re
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

# Ensure environment variables are loaded
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

from greenlight.core.logging_config import get_logger

logger = get_logger("api.projects")

router = APIRouter()

# Unified image generation status tracking
# Used for: reference generation, sheet generation, storyboard generation
_image_generation_status = {}

PROJECTS_DIR = Path("projects")


class Project(BaseModel):
    name: str
    path: str
    lastModified: Optional[str] = None


class Scene(BaseModel):
    number: int
    title: str
    content: str
    tags: list[str]


class ScriptResponse(BaseModel):
    content: str
    scenes: list[Scene]


class Frame(BaseModel):
    id: str
    scene: int
    frame: int
    camera: str
    prompt: str
    imagePath: Optional[str] = None
    tags: list[str] = []  # Extracted tags from prompt (CHAR_, LOC_, PROP_, etc.)


class VisualScriptData(BaseModel):
    """Visual script data structure expected by frontend."""
    total_frames: int = 0
    total_scenes: int = 0
    scenes: list[dict] = []


class StoryboardResponse(BaseModel):
    frames: list[Frame] = []
    visual_script: Optional[VisualScriptData] = None


class WorldEntity(BaseModel):
    tag: str
    name: str
    description: str
    imagePath: Optional[str] = None
    relationships: Optional[list[str]] = None
    scenes: Optional[list[int]] = None
    # Extended character fields
    role: Optional[str] = None
    want: Optional[str] = None
    need: Optional[str] = None
    flaw: Optional[str] = None
    backstory: Optional[str] = None
    voice_signature: Optional[str] = None
    emotional_tells: Optional[dict] = None
    physicality: Optional[str] = None
    speech_patterns: Optional[str] = None


class StyleData(BaseModel):
    visual_style: Optional[str] = None
    style_notes: Optional[str] = None
    lighting: Optional[str] = None
    vibe: Optional[str] = None


class WorldResponse(BaseModel):
    characters: list[WorldEntity]
    locations: list[WorldEntity]
    props: list[WorldEntity]
    style: Optional[StyleData] = None


class GalleryImage(BaseModel):
    path: str
    name: str


class GalleryResponse(BaseModel):
    images: list[GalleryImage]


class ReferenceImage(BaseModel):
    path: str
    name: str
    isKey: bool


class ReferenceTag(BaseModel):
    tag: str
    name: str
    images: list[ReferenceImage]


class ReferencesResponse(BaseModel):
    references: list[ReferenceTag]


class CreateProjectRequest(BaseModel):
    name: str
    location: str = "projects"
    template: str = "feature_film"
    logline: str = ""
    genre: str = "Drama"
    pitch: str = ""


@router.get("/", response_model=list[Project])
async def list_projects():
    projects = []
    if PROJECTS_DIR.exists():
        for project_dir in PROJECTS_DIR.iterdir():
            if project_dir.is_dir():
                projects.append(Project(name=project_dir.name, path=str(project_dir.absolute())))
    return projects


@router.get("/recent")
async def get_recent_projects():
    """Get list of recent projects."""
    # For now, just return all projects as recent
    projects = []
    if PROJECTS_DIR.exists():
        for project_dir in PROJECTS_DIR.iterdir():
            if project_dir.is_dir():
                projects.append(str(project_dir.absolute()))
    return {"projects": projects[:10]}


@router.post("/create")
async def create_project(request: CreateProjectRequest):
    """Create a new project."""
    # Determine project path
    location = Path(request.location) if request.location else PROJECTS_DIR
    if not location.is_absolute():
        location = Path(__file__).parent.parent.parent.parent / location

    project_path = location / request.name.replace(" ", "_")
    project_path.mkdir(parents=True, exist_ok=True)

    # Create project structure
    (project_path / "scripts").mkdir(exist_ok=True)
    (project_path / "world_bible").mkdir(exist_ok=True)
    (project_path / "storyboard").mkdir(exist_ok=True)
    (project_path / "references").mkdir(exist_ok=True)
    (project_path / "storyboard_output").mkdir(exist_ok=True)

    # Create project.json
    project_config = {
        "name": request.name,
        "template": request.template,
        "genre": request.genre,
        "type": "series" if request.template == "series" else "single"
    }
    (project_path / "project.json").write_text(json.dumps(project_config, indent=2), encoding="utf-8")

    # Create pitch.md
    pitch_content = f"""# {request.name}

## Logline
{request.logline or "(No logline provided)"}

## Genre
{request.genre}

## Type
Single Project

## Synopsis
{request.pitch or "(No synopsis provided)"}
"""
    (project_path / "world_bible" / "pitch.md").write_text(pitch_content, encoding="utf-8")

    # Create empty world_config.json
    world_config = {
        "visual_style": "live_action",
        "style_notes": "",
        "lighting": "",
        "vibe": "",
        "characters": [],
        "locations": [],
        "props": []
    }
    (project_path / "world_bible" / "world_config.json").write_text(json.dumps(world_config, indent=2), encoding="utf-8")

    return {"success": True, "project_path": str(project_path.absolute())}


# ============================================================================
# Project-specific endpoints (must come AFTER /create, /recent, etc.)
# These use path parameters that would otherwise catch static routes
# ============================================================================


@router.get("/{project_path:path}/script", response_model=ScriptResponse)
async def get_script(project_path: str):
    project_dir = Path(project_path)
    script_path = project_dir / "scripts" / "script.md"
    if not script_path.exists():
        return ScriptResponse(content="", scenes=[])
    content = script_path.read_text(encoding="utf-8")
    scenes = parse_script_scenes(content)
    return ScriptResponse(content=content, scenes=scenes)


class SaveSceneRequest(BaseModel):
    sceneNumber: int
    title: str
    content: str


@router.post("/{project_path:path}/script/scene")
async def save_script_scene(project_path: str, request: SaveSceneRequest):
    """Save a single scene in the script.md file."""
    project_dir = Path(project_path)
    script_path = project_dir / "scripts" / "script.md"

    if not script_path.exists():
        return {"success": False, "error": "Script file not found"}

    content = script_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    new_lines = []
    in_target_scene = False
    scene_replaced = False

    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this is the target scene header
        if line.startswith(f"## Scene {request.sceneNumber}:") or line.startswith(f"## Scene {request.sceneNumber} "):
            in_target_scene = True
            scene_replaced = True
            # Write new scene header and content
            new_lines.append(f"## Scene {request.sceneNumber}: {request.title}")
            new_lines.append("")
            new_lines.append(request.content)
            new_lines.append("")
            # Skip old scene content until next scene or end
            i += 1
            while i < len(lines) and not lines[i].startswith("## Scene "):
                i += 1
            continue
        elif line.startswith("## Scene "):
            in_target_scene = False

        if not in_target_scene or not scene_replaced:
            new_lines.append(line)
        i += 1

    # Write back
    script_path.write_text("\n".join(new_lines), encoding="utf-8")
    return {"success": True, "message": f"Scene {request.sceneNumber} saved"}


class PitchResponse(BaseModel):
    content: str
    exists: bool


class SavePitchRequest(BaseModel):
    content: str


@router.get("/{project_path:path}/pitch")
async def get_pitch(project_path: str):
    """Get the pitch.md content for a project."""
    project_dir = Path(project_path)
    pitch_path = project_dir / "world_bible" / "pitch.md"

    if not pitch_path.exists():
        return PitchResponse(content="", exists=False)

    content = pitch_path.read_text(encoding="utf-8")
    return PitchResponse(content=content, exists=True)


@router.post("/{project_path:path}/pitch")
async def save_pitch(project_path: str, request: SavePitchRequest):
    """Save the pitch.md content for a project."""
    project_dir = Path(project_path)
    pitch_path = project_dir / "world_bible" / "pitch.md"

    # Ensure directory exists
    pitch_path.parent.mkdir(parents=True, exist_ok=True)

    # Save the content
    pitch_path.write_text(request.content, encoding="utf-8")

    return {"success": True, "message": "Pitch saved successfully"}


def parse_script_scenes(content: str) -> list[Scene]:
    scenes = []
    current_scene = None
    current_content = []
    for line in content.split("\n"):
        if line.startswith("## Scene "):
            if current_scene:
                current_scene["content"] = "\n".join(current_content).strip()
                current_scene["tags"] = list(set(current_scene["tags"]))
                scenes.append(Scene(**current_scene))
            parts = line.replace("## Scene ", "").split(":", 1)
            scene_num = int(parts[0].strip()) if parts[0].strip().isdigit() else len(scenes) + 1
            title = parts[1].strip() if len(parts) > 1 else ""
            current_scene = {"number": scene_num, "title": title, "content": "", "tags": []}
            current_content = []
        elif current_scene:
            current_content.append(line)
            tags = re.findall(r'\[([A-Z]+_[A-Z0-9_]+)\]', line)
            current_scene["tags"].extend(tags)
    if current_scene:
        current_scene["content"] = "\n".join(current_content).strip()
        current_scene["tags"] = list(set(current_scene["tags"]))
        scenes.append(Scene(**current_scene))
    return scenes


def _extract_tags_from_prompt(prompt: str) -> list[str]:
    """Extract all tags (CHAR_, LOC_, PROP_, CONCEPT_, EVENT_, ENV_) from a prompt."""
    pattern = r'\[(CHAR_[A-Z0-9_]+|LOC_[A-Z0-9_]+|PROP_[A-Z0-9_]+|CONCEPT_[A-Z0-9_]+|EVENT_[A-Z0-9_]+|ENV_[A-Z0-9_]+)\]'
    matches = re.findall(pattern, prompt, re.IGNORECASE)
    # Normalize to uppercase and deduplicate while preserving order
    seen = set()
    result = []
    for tag in matches:
        tag_upper = tag.upper()
        if tag_upper not in seen:
            seen.add(tag_upper)
            result.append(tag_upper)
    return result


@router.get("/{project_path:path}/storyboard", response_model=StoryboardResponse)
async def get_storyboard(project_path: str):
    """Get storyboard data including visual script for generation modal."""
    project_dir = Path(project_path)

    # Look for visual_script.json in the correct location (storyboard/ directory)
    possible_paths = [
        project_dir / "storyboard" / "visual_script.json",
        project_dir / "visual_script.json",  # Fallback for legacy
    ]

    visual_script_path = None
    for p in possible_paths:
        if p.exists():
            visual_script_path = p
            logger.info(f"Found visual script at: {p}")
            break

    storyboard_dir = project_dir / "storyboard_output" / "generated"
    frames = []
    visual_script_data = None

    if visual_script_path and visual_script_path.exists():
        try:
            data = json.loads(visual_script_path.read_text(encoding="utf-8"))

            # Build visual_script data for frontend modal
            scenes_data = data.get("scenes", [])
            total_frames = data.get("total_frames", 0)
            total_scenes = len(scenes_data)

            # If total_frames not in data, count from scenes
            if total_frames == 0:
                for scene in scenes_data:
                    total_frames += len(scene.get("frames", []))

            visual_script_data = VisualScriptData(
                total_frames=total_frames,
                total_scenes=total_scenes,
                scenes=scenes_data
            )

            # Also build frames list for backward compatibility
            for scene in scenes_data:
                for frame_data in scene.get("frames", []):
                    frame_id = frame_data.get("frame_id", frame_data.get("id", ""))
                    parts = frame_id.replace("[", "").replace("]", "").split(".")
                    scene_num = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
                    frame_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                    camera = parts[2] if len(parts) > 2 else "cA"
                    image_path = None
                    if storyboard_dir.exists():
                        for img in storyboard_dir.glob(f"*{frame_id}*"):
                            image_path = str(img)
                            break
                    prompt = frame_data.get("prompt", "")
                    frames.append(Frame(
                        id=frame_id,
                        scene=scene_num,
                        frame=frame_num,
                        camera=camera,
                        prompt=prompt,
                        imagePath=image_path,
                        tags=_extract_tags_from_prompt(prompt)
                    ))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse visual script: {e}")
    else:
        logger.warning(f"No visual script found for project: {project_dir}")
        logger.warning(f"Searched paths: {[str(p) for p in possible_paths]}")

    return StoryboardResponse(frames=frames, visual_script=visual_script_data)


@router.post("/{project_path:path}/storyboard/label")
async def label_storyboard_media(project_path: str, dry_run: bool = False):
    """Label and rename unlabeled media files in storyboard_output/generated/.

    Automatically renames any unlabeled media files to match the scene.frame.camera
    notation from visual_script.json.

    Args:
        project_path: Path to the project directory
        dry_run: If True, only report what would be renamed without actually renaming
    """
    from greenlight.core.storyboard_labeler import label_storyboard_media as do_label

    project_dir = Path(project_path)

    if not project_dir.exists():
        return {"success": False, "error": f"Project not found: {project_path}"}

    try:
        renamed = do_label(project_dir, dry_run=dry_run)
        return {
            "success": True,
            "dry_run": dry_run,
            "renamed_count": len(renamed),
            "renamed": [{"old": old, "new": new} for old, new in renamed]
        }
    except Exception as e:
        logger.error(f"Labeler error: {e}")
        return {"success": False, "error": str(e)}


def find_reference_image(project_dir: Path, tag: str) -> Optional[str]:
    """Find the key reference image for a tag.

    Uses ImageHandler.get_key_reference() to get the starred/key reference image.
    This ensures the World Bible view displays the same image that will be used
    for character sheet generation.
    """
    from greenlight.core.image_handler import get_image_handler

    try:
        handler = get_image_handler(project_dir)
        key_ref = handler.get_key_reference(tag)
        if key_ref and key_ref.exists():
            return str(key_ref)
    except Exception:
        pass

    return None


@router.get("/{project_path:path}/world", response_model=WorldResponse)
async def get_world(project_path: str):
    """Get world data including characters, locations, props, and style.

    Uses ImageHandler.get_key_reference() to get the key (starred) reference
    image for each entity, which is displayed as the card thumbnail.
    """
    project_dir = Path(project_path)
    characters, locations, props = [], [], []
    style = None

    # Try multiple possible locations for world_config.json
    possible_paths = [
        project_dir / "world_bible" / "world_config.json",
        project_dir / "world_config.json",
    ]

    world_config_path = None
    for p in possible_paths:
        if p.exists():
            world_config_path = p
            break

    if world_config_path:
        try:
            data = json.loads(world_config_path.read_text(encoding="utf-8"))
            for char in data.get("characters", []):
                tag = char.get("tag", "")
                characters.append(WorldEntity(
                    tag=tag,
                    name=char.get("name", ""),
                    description=char.get("description", ""),
                    imagePath=find_reference_image(project_dir, tag),
                    relationships=char.get("relationships"),
                    scenes=char.get("scenes"),
                    # Extended character fields
                    role=char.get("role"),
                    want=char.get("want"),
                    need=char.get("need"),
                    flaw=char.get("flaw"),
                    backstory=char.get("backstory"),
                    voice_signature=char.get("voice_signature"),
                    emotional_tells=char.get("emotional_tells"),
                    physicality=char.get("physicality"),
                    speech_patterns=char.get("speech_patterns"),
                ))
            for loc in data.get("locations", []):
                tag = loc.get("tag", "")
                locations.append(WorldEntity(
                    tag=tag,
                    name=loc.get("name", ""),
                    description=loc.get("description", ""),
                    imagePath=find_reference_image(project_dir, tag),
                    relationships=loc.get("relationships"),
                    scenes=loc.get("scenes")
                ))
            for prop in data.get("props", []):
                tag = prop.get("tag", "")
                props.append(WorldEntity(
                    tag=tag,
                    name=prop.get("name", ""),
                    description=prop.get("description", ""),
                    imagePath=find_reference_image(project_dir, tag),
                    relationships=prop.get("relationships"),
                    scenes=prop.get("scenes")
                ))

            # Extract style data
            style = StyleData(
                visual_style=data.get("visual_style"),
                style_notes=data.get("style_notes"),
                lighting=data.get("lighting"),
                vibe=data.get("vibe")
            )
        except json.JSONDecodeError:
            pass
    return WorldResponse(characters=characters, locations=locations, props=props, style=style)


class StyleUpdateRequest(BaseModel):
    visual_style: Optional[str] = None
    style_notes: Optional[str] = None
    lighting: Optional[str] = None
    vibe: Optional[str] = None


@router.post("/{project_path:path}/style")
async def save_style(project_path: str, style: StyleUpdateRequest):
    """Save style data to world_config.json."""
    project_dir = Path(project_path)
    world_config_path = project_dir / "world_bible" / "world_config.json"

    # Ensure world_bible directory exists
    world_config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config or create new one
    if world_config_path.exists():
        try:
            config = json.loads(world_config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}
    else:
        config = {
            "characters": [],
            "locations": [],
            "props": []
        }

    # Update style fields
    if style.visual_style is not None:
        config["visual_style"] = style.visual_style
    if style.style_notes is not None:
        config["style_notes"] = style.style_notes
    if style.lighting is not None:
        config["lighting"] = style.lighting
    if style.vibe is not None:
        config["vibe"] = style.vibe

    # Save updated config
    world_config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    return {"success": True, "message": "Style saved"}


class VisualFrame(BaseModel):
    id: str
    scene: int
    frame: int
    camera: str
    position: str
    lighting: str
    prompt: str
    tags: list[str]


class VisualScriptResponse(BaseModel):
    frames: list[VisualFrame]


class PromptItem(BaseModel):
    id: str
    prompt: str
    full_prompt: Optional[str] = None  # Full prompt with labels sent to model
    original_prompt: Optional[str] = None  # Original prompt from visual script
    model: Optional[str] = None
    tags: list[str] = []  # Extracted tags (CHAR_, LOC_, PROP_, etc.)
    reference_images: list[str] = []  # Paths to reference images used
    has_prior_frame: bool = False  # Whether prior frame was used
    status: Optional[str] = None  # pending, success, failed, error
    timestamp: Optional[str] = None  # When the request was sent
    output_path: Optional[str] = None  # Path to generated image
    scene: Optional[str] = None  # Scene number


class PromptsResponse(BaseModel):
    prompts: list[PromptItem]


@router.get("/{project_path:path}/visual-script", response_model=VisualScriptResponse)
async def get_visual_script(project_path: str):
    """Get visual script frames from Director output."""
    project_dir = Path(project_path)
    frames = []

    # Try multiple possible locations
    possible_paths = [
        project_dir / "storyboard" / "visual_script.json",
        project_dir / "visual_script.json",
        project_dir / "storyboard_output" / "visual_script.json",
    ]

    visual_path = None
    for p in possible_paths:
        if p.exists():
            visual_path = p
            break

    if visual_path:
        try:
            data = json.loads(visual_path.read_text(encoding="utf-8"))

            # Handle different JSON structures
            if isinstance(data, list):
                frame_list = data
            elif "scenes" in data:
                frame_list = []
                for scene in data.get("scenes", []):
                    frame_list.extend(scene.get("frames", []))
            else:
                frame_list = data.get("frames", [])

            for frame_data in frame_list:
                frame_id = frame_data.get("frame_id", frame_data.get("id", ""))
                scene_num = frame_data.get("scene_number", 0)
                frame_num = frame_data.get("frame_number", 0)

                # Parse frame_id if scene/frame not provided
                if not scene_num and "." in str(frame_id):
                    parts = str(frame_id).replace("[", "").replace("]", "").split(".")
                    scene_num = int(parts[0]) if parts[0].isdigit() else 0
                    frame_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

                # Extract tags from prompt and notations
                prompt = frame_data.get("prompt", frame_data.get("visual_prompt", ""))
                position = frame_data.get("position_notation", "")
                camera = frame_data.get("camera_notation", "")
                lighting = frame_data.get("lighting_notation", "")

                all_text = f"{prompt} {position} {camera} {lighting}"
                tags = list(set(re.findall(r'\[([A-Z]+_[A-Z0-9_]+)\]', all_text)))

                frames.append(VisualFrame(
                    id=frame_id,
                    scene=scene_num,
                    frame=frame_num,
                    camera=camera,
                    position=position,
                    lighting=lighting,
                    prompt=prompt,
                    tags=tags
                ))
        except json.JSONDecodeError:
            pass

    return VisualScriptResponse(frames=frames)


@router.get("/{project_path:path}/prompts", response_model=PromptsResponse)
async def get_prompts(project_path: str):
    """Get storyboard prompts from prompts_log.json (full prompt data with tags).

    Falls back to legacy shot_prompts.json if prompts_log.json doesn't exist.
    """
    project_dir = Path(project_path)
    prompts = []

    # Primary: prompts_log.json (new format with full data)
    prompts_log_path = project_dir / "storyboard_output" / "prompts_log.json"

    if prompts_log_path.exists():
        try:
            data = json.loads(prompts_log_path.read_text(encoding="utf-8"))
            prompt_list = data if isinstance(data, list) else []

            for prompt_data in prompt_list:
                prompts.append(PromptItem(
                    id=prompt_data.get("frame_id", ""),
                    prompt=prompt_data.get("original_prompt", ""),
                    full_prompt=prompt_data.get("full_prompt"),
                    original_prompt=prompt_data.get("original_prompt"),
                    model=prompt_data.get("model"),
                    tags=prompt_data.get("tags", []),
                    reference_images=prompt_data.get("reference_images", []),
                    has_prior_frame=prompt_data.get("has_prior_frame", False),
                    status=prompt_data.get("status"),
                    timestamp=prompt_data.get("timestamp"),
                    output_path=prompt_data.get("output_path"),
                    scene=prompt_data.get("scene"),
                ))
            return PromptsResponse(prompts=prompts)
        except json.JSONDecodeError:
            pass

    # Fallback: legacy shot_prompts.json locations
    possible_paths = [
        project_dir / "storyboard_output" / "prompts" / "shot_prompts.json",
        project_dir / "prompts" / "shot_prompts.json",
        project_dir / "storyboard_output" / "shot_prompts.json",
    ]

    prompts_path = None
    for p in possible_paths:
        if p.exists():
            prompts_path = p
            break

    if prompts_path:
        try:
            data = json.loads(prompts_path.read_text(encoding="utf-8"))
            prompt_list = data if isinstance(data, list) else data.get("prompts", data.get("shots", []))

            for i, prompt_data in enumerate(prompt_list):
                prompts.append(PromptItem(
                    id=prompt_data.get("shot_id", prompt_data.get("id", f"Shot {i + 1}")),
                    prompt=prompt_data.get("prompt", prompt_data.get("text", "")),
                    model=prompt_data.get("model")
                ))
        except json.JSONDecodeError:
            pass

    return PromptsResponse(prompts=prompts)


class RegeneratePromptRequest(BaseModel):
    frame_id: str
    prompt: str  # The edited prompt to use
    model: Optional[str] = None  # Optional model override


class RegeneratePromptResponse(BaseModel):
    success: bool
    message: str
    output_path: Optional[str] = None


@router.post("/{project_path:path}/prompts/regenerate", response_model=RegeneratePromptResponse)
async def regenerate_prompt(project_path: str, request: RegeneratePromptRequest):
    """Regenerate a single frame with an edited prompt.

    Uses the same reference images and prior frame logic as the original generation.
    Updates the prompts_log.json with the new prompt and result.
    """
    from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
    from datetime import datetime

    project_dir = Path(project_path)

    # Load prompts log to find the original entry
    prompts_log_path = project_dir / "storyboard_output" / "prompts_log.json"
    if not prompts_log_path.exists():
        return RegeneratePromptResponse(success=False, message="No prompts log found")

    try:
        prompts_log = json.loads(prompts_log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return RegeneratePromptResponse(success=False, message="Invalid prompts log file")

    # Find the frame entry
    frame_entry = None
    frame_index = -1
    for i, entry in enumerate(prompts_log):
        if entry.get("frame_id") == request.frame_id:
            frame_entry = entry
            frame_index = i
            break

    if frame_entry is None:
        return RegeneratePromptResponse(success=False, message=f"Frame {request.frame_id} not found in prompts log")

    # Get reference images from the original entry
    reference_images = [Path(p) for p in frame_entry.get("reference_images", []) if Path(p).exists()]

    # Determine model
    model_str = request.model or frame_entry.get("model", "seedream")
    model_mapping = {
        "seedream": ImageModel.SEEDREAM,
        "seedream_4_5": ImageModel.SEEDREAM,
        "nano_banana": ImageModel.NANO_BANANA,
        "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
        "flux_kontext_pro": ImageModel.FLUX_KONTEXT_PRO,
        "flux_kontext_max": ImageModel.FLUX_KONTEXT_MAX,
    }
    selected_model = model_mapping.get(model_str, ImageModel.SEEDREAM)

    # Build labeled prompt with the new prompt text
    tags = frame_entry.get("tags", [])
    tag_refs = []
    for tag in tags:
        for ref_path in reference_images:
            if tag.lower() in str(ref_path).lower():
                tag_refs.append((tag, ref_path))
                break

    has_prior_frame = frame_entry.get("has_prior_frame", False)

    # Build labeled prompt
    label_parts = []
    for idx, (tag, _) in enumerate(tag_refs, 1):
        label_parts.append(f"[{idx}] [{tag}]")
    if has_prior_frame and reference_images:
        label_parts.append(f"[{len(tag_refs) + 1}] Prior Frame (maintain scene continuity)")

    if label_parts:
        labeled_prompt = f"Reference Images: {', '.join(label_parts)}. {request.prompt}"
    else:
        labeled_prompt = request.prompt

    # Output path
    output_dir = project_dir / "storyboard_output" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{request.frame_id}.png"

    try:
        handler = ImageHandler(project_path=project_dir)

        img_request = ImageRequest(
            prompt=labeled_prompt,
            model=selected_model,
            aspect_ratio="16:9",
            reference_images=reference_images,
            output_path=output_path,
            tag=request.frame_id,
            prefix_type="generate",
            add_clean_suffix=True
        )

        result = await handler.generate(img_request)

        # Update the prompts log entry
        prompts_log[frame_index]["original_prompt"] = request.prompt
        prompts_log[frame_index]["full_prompt"] = labeled_prompt
        prompts_log[frame_index]["timestamp"] = datetime.now().isoformat()
        prompts_log[frame_index]["status"] = "success" if result.success else "failed"
        prompts_log[frame_index]["model"] = selected_model.value
        if not result.success:
            prompts_log[frame_index]["error"] = result.error

        # Save updated log
        prompts_log_path.write_text(json.dumps(prompts_log, indent=2), encoding="utf-8")

        if result.success:
            return RegeneratePromptResponse(
                success=True,
                message=f"Frame {request.frame_id} regenerated successfully",
                output_path=str(output_path)
            )
        else:
            return RegeneratePromptResponse(
                success=False,
                message=f"Generation failed: {result.error}"
            )

    except Exception as e:
        return RegeneratePromptResponse(success=False, message=f"Error: {str(e)}")


@router.get("/{project_path:path}/gallery", response_model=GalleryResponse)
async def get_gallery(project_path: str):
    """Get all images from the project."""
    project_dir = Path(project_path)
    images = []
    image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

    # Search multiple directories
    search_paths = [
        project_dir / "storyboard_output",
        project_dir / "storyboard" / "generated",
        project_dir / "references",
        project_dir / "assets",
    ]

    for search_path in search_paths:
        if search_path.exists():
            for img in search_path.rglob("*"):
                if img.suffix.lower() in image_extensions:
                    images.append(GalleryImage(path=str(img), name=img.name))

    return GalleryResponse(images=images)


@router.get("/{project_path:path}/references", response_model=ReferencesResponse)
async def get_references(project_path: str):
    """Get all reference images organized by tag.

    Uses ImageHandler.get_key_reference() to determine the key (starred) reference for each tag.
    """
    from greenlight.core.image_handler import get_image_handler

    project_dir = Path(project_path)
    references_dir = project_dir / "references"
    world_config_path = project_dir / "world_config.json"
    references = []
    names = {}

    if world_config_path.exists():
        try:
            data = json.loads(world_config_path.read_text(encoding="utf-8"))
            for char in data.get("characters", []):
                names[char.get("tag", "")] = char.get("name", "")
            for loc in data.get("locations", []):
                names[loc.get("tag", "")] = loc.get("name", "")
            for prop in data.get("props", []):
                names[prop.get("tag", "")] = prop.get("name", "")
        except json.JSONDecodeError:
            pass

    if references_dir.exists():
        handler = get_image_handler(project_dir)

        for tag_dir in references_dir.iterdir():
            if tag_dir.is_dir():
                tag = tag_dir.name
                # Get key reference from ImageHandler (single source of truth)
                key_ref = handler.get_key_reference(tag)

                images = []
                for img in tag_dir.glob("*"):
                    if img.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
                        # Mark as key if it matches the key reference path
                        is_key = key_ref is not None and img.resolve() == key_ref.resolve()
                        images.append(ReferenceImage(path=str(img), name=img.name, isKey=is_key))
                if images:
                    references.append(ReferenceTag(tag=tag, name=names.get(tag, tag), images=images))

    return ReferencesResponse(references=references)


class TagReferencesResponse(BaseModel):
    tag: str
    name: str
    tagType: str
    images: list[ReferenceImage]
    keyReference: Optional[str] = None


@router.get("/{project_path:path}/references/{tag}")
async def get_tag_references(project_path: str, tag: str):
    """Get all reference images for a specific tag.

    Uses ImageHandler.get_key_reference() to determine the key (starred) reference.
    """
    from greenlight.core.image_handler import get_image_handler

    project_dir = Path(project_path)
    references_dir = project_dir / "references" / tag

    # Determine tag type from prefix
    tag_type = "character"
    if tag.startswith("LOC_"):
        tag_type = "location"
    elif tag.startswith("PROP_"):
        tag_type = "prop"

    # Get name from world_config
    name = tag
    world_config_path = project_dir / "world_bible" / "world_config.json"
    if not world_config_path.exists():
        world_config_path = project_dir / "world_config.json"

    if world_config_path.exists():
        try:
            data = json.loads(world_config_path.read_text(encoding="utf-8"))
            category = "characters" if tag_type == "character" else "locations" if tag_type == "location" else "props"
            for item in data.get(category, []):
                if item.get("tag") == tag:
                    name = item.get("name", tag)
                    break
        except json.JSONDecodeError:
            pass

    # Get key reference from ImageHandler (single source of truth)
    handler = get_image_handler(project_dir)
    key_ref = handler.get_key_reference(tag)
    key_reference = str(key_ref) if key_ref else None

    images = []
    if references_dir.exists():
        for img in references_dir.glob("*"):
            if img.is_file() and img.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
                # Mark as key if it matches the key reference path
                is_key = key_ref is not None and img.resolve() == key_ref.resolve()
                images.append(ReferenceImage(path=str(img), name=img.name, isKey=is_key))

    return TagReferencesResponse(
        tag=tag,
        name=name,
        tagType=tag_type,
        images=images,
        keyReference=key_reference
    )


class SetKeyReferenceRequest(BaseModel):
    imagePath: str


@router.post("/{project_path:path}/references/{tag}/set-key")
async def set_key_reference(project_path: str, tag: str, request: SetKeyReferenceRequest):
    """Set an image as the key reference for a tag.

    Uses ImageHandler.set_key_reference() which stores the key reference path
    in a .key file within the tag's reference directory. This is the single
    source of truth for which image is the "starred" primary reference.
    """
    from greenlight.core.image_handler import get_image_handler

    project_dir = Path(project_path)
    image_path = Path(request.imagePath)

    if not image_path.exists():
        return {"success": False, "error": "Image not found"}

    try:
        # Use ImageHandler's set_key_reference method (writes .key file)
        handler = get_image_handler(project_dir)
        handler.set_key_reference(tag, image_path)

        return {"success": True, "keyPath": str(image_path)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/{project_path:path}/references/{tag}/upload")
async def upload_reference(project_path: str, tag: str, file: UploadFile = File(...)):
    """Upload a reference image for a tag.

    Accepts image files (PNG, JPG, JPEG, WebP) and saves them to the tag's reference directory.
    Automatically creates a labeled version with tag and display name.
    """
    from datetime import datetime

    # Validate file type
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    file_ext = Path(file.filename).suffix.lower() if file.filename else ''

    if file_ext not in allowed_extensions:
        return {"success": False, "error": f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"}

    project_dir = Path(project_path)
    references_dir = project_dir / "references" / tag
    references_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{tag}_upload_{timestamp}{file_ext}"
    output_path = references_dir / safe_filename

    try:
        # Read and save the file
        content = await file.read()
        output_path.write_bytes(content)

        # Auto-label the uploaded image
        labeled_path = None
        try:
            from greenlight.references.reference_watcher import ReferenceWatcher
            watcher = ReferenceWatcher(project_dir)
            watcher._load_tag_names()
            labeled_path = watcher._label_image(output_path)
        except Exception as label_error:
            logger.warning(f"Auto-labeling failed: {label_error}")

        return {
            "success": True,
            "path": str(output_path),
            "name": safe_filename,
            "labeled_path": str(labeled_path) if labeled_path else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/{project_path:path}/references/label-all")
async def label_all_references(project_path: str):
    """Label all existing unlabeled reference images.

    Creates labeled versions of all reference images with:
    - Left-aligned: Tag in bracket notation (e.g., [CHAR_MEI])
    - Right-aligned: Display name from world_config.json (e.g., Mei)
    - Red background box with black text
    - Minimum 50px font size
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        return {"success": False, "error": "Project not found"}

    try:
        from greenlight.references.reference_watcher import ReferenceWatcher
        watcher = ReferenceWatcher(project_dir)
        labeled_count = watcher.label_all_existing()

        return {
            "success": True,
            "labeled_count": labeled_count,
            "message": f"Labeled {labeled_count} images"
        }
    except Exception as e:
        logger.error(f"Failed to label references: {e}")
        return {"success": False, "error": str(e)}


class GenerateReferenceRequest(BaseModel):
    model: str = "nano_banana_pro"


class GenerateReferenceResponse(BaseModel):
    success: bool
    message: str
    process_id: Optional[str] = None


@router.post("/{project_path:path}/references/{tag}/generate")
async def generate_single_reference(
    project_path: str,
    tag: str,
    request: GenerateReferenceRequest
):
    """Generate a single reference image for a tag (background task).

    Returns immediately with a process_id for status polling.
    """
    import uuid
    import asyncio

    project_dir = Path(project_path)
    world_config_path = project_dir / "world_bible" / "world_config.json"

    if not world_config_path.exists():
        return GenerateReferenceResponse(success=False, message="world_config.json not found")

    try:
        world_config = json.loads(world_config_path.read_text(encoding='utf-8'))
    except Exception as e:
        return GenerateReferenceResponse(success=False, message=f"Failed to load world_config.json: {e}")

    # Find the entity by tag
    entity = None
    entity_type = None
    if tag.startswith("CHAR_"):
        for char in world_config.get("characters", []):
            if char.get("tag") == tag:
                entity = char
                entity_type = "character"
                break
    elif tag.startswith("LOC_"):
        for loc in world_config.get("locations", []):
            if loc.get("tag") == tag:
                entity = loc
                entity_type = "location"
                break
    elif tag.startswith("PROP_"):
        for prop in world_config.get("props", []):
            if prop.get("tag") == tag:
                entity = prop
                entity_type = "prop"
                break

    if not entity:
        return GenerateReferenceResponse(success=False, message=f"Entity not found for tag: {tag}")

    # Create process ID and initialize status
    process_id = str(uuid.uuid4())[:8]
    _image_generation_status[process_id] = {
        "type": "single_reference",
        "status": "starting",
        "progress": 0,
        "logs": [f"Starting {entity_type} reference generation for {tag}..."],
        "tag": tag,
        "entity_type": entity_type,
        "output_path": None,
        "error": None
    }

    # Start background task
    asyncio.create_task(
        _execute_single_reference_generation(
            process_id,
            project_path,
            tag,
            entity_type,
            entity,
            request.model
        )
    )

    return GenerateReferenceResponse(
        success=True,
        message="Reference generation started",
        process_id=process_id
    )


async def _execute_single_reference_generation(
    process_id: str,
    project_path: str,
    tag: str,
    entity_type: str,
    entity: dict,
    model_name: str
):
    """Execute single reference generation in background."""
    from datetime import datetime
    from greenlight.core.image_handler import get_image_handler, ImageModel

    status = _image_generation_status[process_id]
    project_dir = Path(project_path)

    def log(msg: str):
        status["logs"].append(msg)

    try:
        status["status"] = "running"
        log(f"🖼️ Generating {entity_type} reference using {model_name}...")

        # Map model string to ImageModel enum
        model_map = {
            "nano_banana": ImageModel.NANO_BANANA,
            "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
            "seedream": ImageModel.SEEDREAM,
        }
        model = model_map.get(model_name, ImageModel.NANO_BANANA_PRO)

        handler = get_image_handler(project_dir)
        name = entity.get("name", "")

        status["progress"] = 0.3
        log("📤 Sending request to image generation API...")

        if entity_type == "character":
            result = await handler.generate_character_sheet(
                tag=tag,
                name=name,
                model=model,
                character_data=entity
            )
        elif entity_type == "prop":
            result = await handler.generate_prop_reference(
                tag=tag,
                name=name,
                prop_data=entity,
                model=model
            )
        elif entity_type == "location":
            result = await handler.generate_location_reference(
                tag=tag,
                name=name,
                location_data=entity,
                model=model
            )
        else:
            status["status"] = "failed"
            status["error"] = f"Unknown entity type: {entity_type}"
            log(f"❌ Unknown entity type: {entity_type}")
            return

        if result and result.success:
            status["progress"] = 1.0
            status["status"] = "complete"
            status["output_path"] = str(result.output_path) if result.output_path else None
            log(f"✅ Reference generated successfully")
            log(f"⏱️ Generation time: {result.generation_time_ms}ms")
        else:
            status["status"] = "failed"
            status["error"] = result.error if result else "Generation failed"
            log(f"❌ Generation failed: {result.error if result else 'Unknown error'}")

    except Exception as e:
        status["status"] = "failed"
        status["error"] = str(e)
        log(f"❌ Error: {str(e)}")


class GenerateSheetRequest(BaseModel):
    imagePath: str
    model: str = "nano_banana_pro"


class GenerateSheetResponse(BaseModel):
    success: bool
    message: str
    process_id: Optional[str] = None


@router.post("/{project_path:path}/references/{tag}/generate-sheet")
async def generate_sheet(
    project_path: str,
    tag: str,
    request: GenerateSheetRequest
):
    """Generate a character/prop sheet from a reference image (background task).

    Returns immediately with a process_id for status polling.
    """
    import uuid
    import asyncio

    project_dir = Path(project_path)
    image_path = Path(request.imagePath)

    if not image_path.exists():
        return GenerateSheetResponse(success=False, message="Image not found")

    # Determine tag type
    tag_type = "character"
    if tag.startswith("LOC_"):
        tag_type = "location"
    elif tag.startswith("PROP_"):
        tag_type = "prop"

    # Create process ID and initialize status
    process_id = str(uuid.uuid4())[:8]
    _image_generation_status[process_id] = {
        "type": "sheet",
        "status": "starting",
        "progress": 0,
        "logs": [f"Starting {tag_type} sheet generation for {tag}..."],
        "tag": tag,
        "tag_type": tag_type,
        "output_path": None,
        "error": None
    }

    # Start background task using asyncio.create_task for true async execution
    asyncio.create_task(
        _execute_sheet_generation(
            process_id,
            project_path,
            tag,
            tag_type,
            str(image_path),
            request.model
        )
    )

    return GenerateSheetResponse(
        success=True,
        message="Sheet generation started",
        process_id=process_id
    )


async def _execute_sheet_generation(
    process_id: str,
    project_path: str,
    tag: str,
    tag_type: str,
    image_path_str: str,
    model_name: str
):
    """Execute sheet generation in background."""
    from datetime import datetime
    from greenlight.core.image_handler import get_image_handler, ImageRequest, ImageModel

    status = _image_generation_status[process_id]
    project_dir = Path(project_path)
    image_path = Path(image_path_str)

    def log(msg: str):
        status["logs"].append(msg)

    try:
        status["status"] = "running"
        log(f"🖼️ Generating {tag_type} sheet using {model_name}...")

        handler = get_image_handler(project_dir)

        # Map model string to ImageModel enum
        model_map = {
            "nano_banana": ImageModel.NANO_BANANA,
            "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
            "seedream": ImageModel.SEEDREAM,
        }
        model = model_map.get(model_name, ImageModel.NANO_BANANA_PRO)

        # Create output path
        refs_dir = project_dir / "references" / tag
        refs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = refs_dir / f"{tag}_sheet_{timestamp}.png"

        # Build prompt based on tag type
        if tag_type == "character":
            prompt = "Create a character reference sheet with multiple views (front, side, back, 3/4 view). Maintain consistent appearance across all views. Clean white background, professional character turnaround sheet layout."
        elif tag_type == "prop":
            prompt = "Create a prop reference sheet showing this object from multiple angles (front, side, top, 3/4 view). Maintain consistent appearance. Clean white background, professional product sheet layout."
        else:
            prompt = "Create a location reference sheet showing this environment from multiple angles. Maintain consistent appearance. Professional layout."

        # Get style suffix
        style_suffix = handler.get_style_suffix()

        img_request = ImageRequest(
            prompt=prompt,
            model=model,
            aspect_ratio="16:9",
            tag=tag,
            output_path=output_path,
            reference_images=[image_path],
            prefix_type="edit",
            style_suffix=style_suffix if style_suffix else None,
            add_clean_suffix=True
        )

        log("📤 Sending request to image generation API...")
        status["progress"] = 0.3

        result = await handler.generate(img_request)

        if result.success:
            status["progress"] = 1.0
            status["status"] = "complete"
            status["output_path"] = str(output_path)
            log(f"✅ Sheet generated successfully: {output_path.name}")
            log(f"⏱️ Generation time: {result.generation_time_ms}ms")
        else:
            status["status"] = "failed"
            status["error"] = result.error
            log(f"❌ Generation failed: {result.error}")

    except Exception as e:
        status["status"] = "failed"
        status["error"] = str(e)
        log(f"❌ Error: {str(e)}")


# ============================================================================
# Bulk Reference Generation
# ============================================================================

class GenerateAllReferencesRequest(BaseModel):
    """Request model for bulk reference generation."""
    tagType: str  # "characters", "locations", or "props"
    model: str = "nano_banana_pro"
    overwrite: bool = False  # Whether to regenerate existing references


class GenerateAllReferencesResponse(BaseModel):
    """Response model for bulk reference generation."""
    success: bool
    message: str
    process_id: Optional[str] = None


@router.post("/{project_path:path}/references/generate-all")
async def generate_all_references(
    project_path: str,
    request: GenerateAllReferencesRequest
):
    """Start bulk reference generation in background.

    Returns immediately with a process_id that can be used to poll for status.
    The actual generation runs in the background without blocking the UI.

    - Characters: Generates character sheet from description
    - Locations: Generates North view from description
    - Props: Generates prop reference from description
    """
    import uuid
    import asyncio

    project_dir = Path(project_path)
    world_config_path = project_dir / "world_bible" / "world_config.json"

    if not world_config_path.exists():
        return GenerateAllReferencesResponse(
            success=False,
            message="world_config.json not found"
        )

    try:
        world_config = json.loads(world_config_path.read_text(encoding='utf-8'))
    except Exception as e:
        return GenerateAllReferencesResponse(
            success=False,
            message=f"Failed to load world_config.json: {e}"
        )

    # Get entities based on tag type
    tag_type = request.tagType.lower()
    if tag_type == "characters":
        entities = world_config.get("characters", [])
    elif tag_type == "locations":
        entities = world_config.get("locations", [])
    elif tag_type == "props":
        entities = world_config.get("props", [])
    else:
        return GenerateAllReferencesResponse(
            success=False,
            message=f"Invalid tagType: {request.tagType}"
        )

    if not entities:
        return GenerateAllReferencesResponse(
            success=True,
            message=f"No {tag_type} found in world_config.json"
        )

    # Create process ID and initialize status
    process_id = str(uuid.uuid4())[:8]
    _image_generation_status[process_id] = {
        "type": "bulk_references",
        "status": "starting",
        "progress": 0,
        "logs": [],
        "generated": 0,
        "skipped": 0,
        "total": len(entities),
        "errors": []
    }

    # Start background task using asyncio.create_task for true async execution
    # This prevents blocking the response while the task runs
    import asyncio
    asyncio.create_task(
        _execute_reference_generation(
            process_id,
            project_path,
            request.tagType,
            request.model,
            request.overwrite,
            entities
        )
    )

    return GenerateAllReferencesResponse(
        success=True,
        message="Reference generation started",
        process_id=process_id
    )


# ============================================================================
# Unified Image Generation Status Endpoints
# ============================================================================

@router.get("/{project_path:path}/image-generation/status/{process_id}")
async def get_image_generation_status(project_path: str, process_id: str):
    """Get status of any image generation process (sheet, bulk references, storyboard)."""
    if process_id not in _image_generation_status:
        return {"error": "Process not found", "status": "not_found"}
    return _image_generation_status[process_id]


@router.post("/{project_path:path}/image-generation/cancel/{process_id}")
async def cancel_image_generation(project_path: str, process_id: str):
    """Cancel any running image generation process."""
    if process_id not in _image_generation_status:
        return {"success": False, "error": "Process not found"}

    status = _image_generation_status[process_id]
    if status["status"] not in ["running", "starting"]:
        return {"success": False, "error": f"Process is not running (status: {status['status']})"}

    # Set cancelled flag - the background task will check this
    status["cancelled"] = True
    status["status"] = "cancelled"
    status["logs"].append("⚠️ Cancellation requested by user")

    return {"success": True, "message": "Cancellation requested"}


# Legacy endpoints for backward compatibility
@router.get("/{project_path:path}/references/status/{process_id}")
async def get_reference_generation_status(project_path: str, process_id: str):
    """Get status of a running reference generation process (legacy endpoint)."""
    return await get_image_generation_status(project_path, process_id)


@router.post("/{project_path:path}/references/cancel/{process_id}")
async def cancel_reference_generation(project_path: str, process_id: str):
    """Cancel a running reference generation process (legacy endpoint)."""
    return await cancel_image_generation(project_path, process_id)


async def _execute_reference_generation(
    process_id: str,
    project_path: str,
    tag_type: str,
    model_name: str,
    overwrite: bool,
    entities: list
):
    """Execute reference generation in background."""
    import asyncio
    from datetime import datetime
    from greenlight.core.image_handler import get_image_handler, ImageRequest, ImageModel

    status = _image_generation_status[process_id]
    project_dir = Path(project_path)

    def log(msg: str):
        status["logs"].append(msg)

    def update_progress(current: int, total: int):
        status["progress"] = current / total if total > 0 else 0

    # Map model string to ImageModel enum
    model_map = {
        "nano_banana": ImageModel.NANO_BANANA,
        "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
        "seedream": ImageModel.SEEDREAM,
    }
    model = model_map.get(model_name, ImageModel.NANO_BANANA_PRO)

    # Determine entity type
    entity_type = tag_type.lower().rstrip('s')  # "characters" -> "character"
    if entity_type == "location":
        entity_type = "location"  # Keep as-is

    try:
        status["status"] = "running"
        log(f"🎨 Starting reference generation for {len(entities)} {tag_type}...")
        log(f"📷 Using model: {model_name}")

        handler = get_image_handler(project_dir)

        for idx, entity in enumerate(entities):
            # Check for cancellation before each entity
            if status.get("cancelled"):
                log("🛑 Generation cancelled by user")
                status["status"] = "cancelled"
                return

            tag = entity.get("tag", "")
            name = entity.get("name", "")

            if not tag:
                continue

            # Check if references already exist
            refs_dir = project_dir / "references" / tag
            existing_refs = list(refs_dir.glob("*.png")) + list(refs_dir.glob("*.jpg")) if refs_dir.exists() else []

            if existing_refs and not overwrite:
                log(f"⏭️ Skipping {tag} (already has references)")
                status["skipped"] += 1
                update_progress(idx + 1, len(entities))
                continue

            # Create output directory
            refs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            log(f"🖼️ Generating reference for {tag}...")

            try:
                if entity_type == "character":
                    result = await handler.generate_character_sheet(
                        tag=tag,
                        name=name,
                        model=model,
                        character_data=entity
                    )
                elif entity_type == "prop":
                    result = await handler.generate_prop_reference(
                        tag=tag,
                        name=name,
                        prop_data=entity,
                        model=model
                    )
                elif entity_type == "location":
                    prompt = _build_location_reference_prompt(entity)
                    style_suffix = handler.get_style_suffix()
                    output_path = refs_dir / f"{tag}_north_{timestamp}.png"

                    img_request = ImageRequest(
                        prompt=prompt,
                        model=model,
                        aspect_ratio="16:9",
                        tag=tag,
                        output_path=output_path,
                        prefix_type="recreate",
                        style_suffix=style_suffix if style_suffix else None,
                        add_clean_suffix=True
                    )
                    result = await handler.generate(img_request)
                else:
                    continue

                if result.success:
                    log(f"✓ Generated reference for {tag}")
                    status["generated"] += 1
                else:
                    log(f"❌ Failed {tag}: {result.error}")
                    status["errors"].append(f"{tag}: {result.error}")

            except Exception as e:
                log(f"❌ Error generating {tag}: {str(e)}")
                status["errors"].append(f"{tag}: {str(e)}")

            update_progress(idx + 1, len(entities))

            # Small delay to prevent overwhelming the API
            await asyncio.sleep(0.1)

        # Complete
        status["progress"] = 1.0
        log(f"✅ Reference generation complete! Generated: {status['generated']}, Skipped: {status['skipped']}")
        status["status"] = "complete"

    except Exception as e:
        log(f"❌ Error: {str(e)}")
        status["status"] = "failed"
        status["error"] = str(e)


def _build_location_reference_prompt(entity: dict) -> str:
    """Build a prompt for location reference generation (North view)."""
    tag = entity.get("tag", "")
    name = entity.get("name", "")
    description = entity.get("description", "")
    atmosphere = entity.get("atmosphere", "")
    time_period = entity.get("time_period", "")
    directional_views = entity.get("directional_views", {})
    north_view = directional_views.get("north", "")

    prompt_parts = [f"Location reference (NORTH VIEW) for [{tag}] {name}."]
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

