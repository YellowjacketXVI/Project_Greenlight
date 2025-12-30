"""Projects router for Project Greenlight API."""

import json
import os
import re
from pathlib import Path
from typing import Optional, Any
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

# Ensure environment variables are loaded
from greenlight.core.env_loader import ensure_env_loaded
ensure_env_loaded()

from greenlight.core.logging_config import get_logger

logger = get_logger("api.projects")

router = APIRouter()

# Unified image generation status tracking
# Used for: reference generation, sheet generation, storyboard generation
_image_generation_status = {}

# Per-project reference watchers for auto-labeling
_project_watchers = {}

PROJECTS_DIR = Path("projects")


def ensure_reference_watcher(project_path: Path) -> None:
    """Ensure reference watcher is running for a project."""
    try:
        from greenlight.references.reference_watcher import ReferenceWatcher

        project_key = str(project_path.absolute())

        # Check if watcher already exists and is running
        if project_key in _project_watchers:
            watcher = _project_watchers[project_key]
            if hasattr(watcher, '_running') and watcher._running:
                return
            # Clean up dead watcher
            del _project_watchers[project_key]

        # Create and start new watcher
        watcher = ReferenceWatcher(project_path)
        watcher.start()
        _project_watchers[project_key] = watcher
        logger.info(f"Started reference watcher for: {project_path.name}")
    except Exception as e:
        # Don't let watcher errors break the API
        logger.warning(f"Could not start reference watcher: {e}")


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
    # Extended metadata from visual_script.json
    camera_notation: Optional[str] = None
    position_notation: Optional[str] = None
    lighting_notation: Optional[str] = None
    location_direction: Optional[str] = None
    # Archived versions (previous iterations that were healed)
    archivedVersions: Optional[list[str]] = None


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
    backstory: Optional[Any] = None  # Can be dict or string
    voice_signature: Optional[Any] = None  # Can be dict or string
    emotional_tells: Optional[Any] = None  # Can be dict or string
    physicality: Optional[Any] = None  # Can be dict or string
    speech_patterns: Optional[Any] = None  # Can be dict or string


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


class StructuredPitchData(BaseModel):
    """Structured pitch data parsed from pitch.md."""
    title: str = ""
    logline: str = ""
    genre: str = ""
    synopsis: str = ""
    characters: str = ""
    locations: str = ""


@router.get("/{project_path:path}/pitch")
async def get_pitch(project_path: str):
    """Get the pitch.md content for a project."""
    project_dir = Path(project_path)
    pitch_path = project_dir / "world_bible" / "pitch.md"

    if not pitch_path.exists():
        return PitchResponse(content="", exists=False)

    content = pitch_path.read_text(encoding="utf-8")
    return PitchResponse(content=content, exists=True)


@router.get("/{project_path:path}/pitch-data")
async def get_pitch_data(project_path: str):
    """Get structured pitch data parsed from pitch.md."""
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


@router.post("/{project_path:path}/pitch-data")
async def save_pitch_data(project_path: str, pitch: StructuredPitchData):
    """Save structured pitch data to pitch.md."""
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

            # Check for archive directory
            archive_dir = project_dir / "storyboard_output" / "archive"

            # Also build frames list with full metadata
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

                    # Find archived versions for this frame
                    archived_versions = []
                    clean_frame_id = frame_id.replace("[", "").replace("]", "")
                    if archive_dir.exists():
                        # Look for archived versions matching this frame ID
                        for archived in archive_dir.glob(f"{clean_frame_id}_v*.png"):
                            archived_versions.append(str(archived))
                        # Sort by timestamp (newest first)
                        archived_versions.sort(reverse=True)

                    prompt = frame_data.get("prompt", "")
                    frames.append(Frame(
                        id=frame_id,
                        scene=scene_num,
                        frame=frame_num,
                        camera=camera,
                        prompt=prompt,
                        imagePath=image_path,
                        tags=_extract_tags_from_prompt(prompt),
                        # Include extended metadata from visual_script.json
                        camera_notation=frame_data.get("camera_notation"),
                        position_notation=frame_data.get("position_notation"),
                        lighting_notation=frame_data.get("lighting_notation"),
                        location_direction=frame_data.get("location_direction"),
                        # Include archived versions
                        archivedVersions=archived_versions if archived_versions else None,
                    ))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse visual script: {e}")
    else:
        logger.warning(f"No visual script found for project: {project_dir}")
        logger.warning(f"Searched paths: {[str(p) for p in possible_paths]}")

    # Fallback: if no frames yet, try loading from prompts.json
    if not frames:
        prompts_path = project_dir / "storyboard" / "prompts.json"
        if prompts_path.exists():
            try:
                prompts_data = json.loads(prompts_path.read_text(encoding="utf-8"))
                # Handle both list format (new) and dict format (legacy)
                if isinstance(prompts_data, list):
                    prompt_list = prompts_data
                elif isinstance(prompts_data, dict):
                    prompt_list = [
                        {"frame_id": fid, "prompt": p, "scene": fid.split(".")[0] if "." in fid else "1"}
                        for fid, p in prompts_data.items()
                    ]
                else:
                    prompt_list = []

                storyboard_dir = project_dir / "storyboard_output" / "generated"
                archive_dir = project_dir / "storyboard_output" / "archive"

                for prompt_entry in prompt_list:
                    frame_id = prompt_entry.get("frame_id", "")
                    parts = frame_id.replace("[", "").replace("]", "").split(".")
                    scene_num = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
                    frame_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                    camera = parts[2] if len(parts) > 2 else "cA"

                    # Find image for this frame
                    image_path = None
                    if storyboard_dir.exists():
                        for img in storyboard_dir.glob(f"*{frame_id}*"):
                            image_path = str(img)
                            break

                    # Find archived versions
                    archived_versions = []
                    clean_frame_id = frame_id.replace("[", "").replace("]", "")
                    if archive_dir.exists():
                        for archived in archive_dir.glob(f"{clean_frame_id}_v*.png"):
                            archived_versions.append(str(archived))
                        archived_versions.sort(reverse=True)

                    prompt = prompt_entry.get("prompt", "")
                    tags = prompt_entry.get("tags", [])
                    if not tags:
                        tags = _extract_tags_from_prompt(prompt)

                    frames.append(Frame(
                        id=frame_id,
                        scene=scene_num,
                        frame=frame_num,
                        camera=camera,
                        prompt=prompt,
                        imagePath=image_path,
                        tags=tags,
                        archivedVersions=archived_versions if archived_versions else None,
                    ))
                logger.info(f"Loaded {len(frames)} frames from prompts.json")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse prompts.json: {e}")

    return StoryboardResponse(frames=frames, visual_script=visual_script_data)


class FramePromptUpdate(BaseModel):
    """Request body for updating a frame's prompt."""
    frame_id: str
    prompt: str


class FrameRegenerateRequest(BaseModel):
    """Request body for regenerating a frame."""
    frame_id: str


class AddCameraRequest(BaseModel):
    """Request body for adding a camera angle to a frame."""
    frame_id: str  # Base frame ID (e.g., "1.2.cA")
    prompt: str  # Prompt for the new camera angle


@router.post("/{project_path:path}/storyboard/frame/update-prompt")
async def update_frame_prompt(project_path: str, request: FramePromptUpdate):
    """Update a frame's prompt in prompts.json.

    This updates the editable prompts file that the storyboard pipeline reads from.
    """
    project_dir = Path(project_path)
    prompts_path = project_dir / "storyboard" / "prompts.json"

    if not prompts_path.exists():
        return {"success": False, "error": "prompts.json not found. Run Director pipeline first."}

    try:
        data = json.loads(prompts_path.read_text(encoding="utf-8"))
        prompts = data.get("prompts", [])

        # Find and update the prompt
        found = False
        for prompt_item in prompts:
            if prompt_item.get("frame_id") == request.frame_id:
                prompt_item["prompt"] = request.prompt
                prompt_item["edited"] = True
                found = True
                break

        if not found:
            return {"success": False, "error": f"Frame {request.frame_id} not found in prompts.json"}

        # Save back
        prompts_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        return {"success": True, "frame_id": request.frame_id, "prompt": request.prompt}
    except Exception as e:
        logger.error(f"Error updating frame prompt: {e}")
        return {"success": False, "error": str(e)}


@router.post("/{project_path:path}/storyboard/frame/regenerate")
async def regenerate_frame(project_path: str, request: FrameRegenerateRequest):
    """Regenerate a single storyboard frame.

    This triggers image generation for just the specified frame.
    """
    project_dir = Path(project_path)

    # Get the prompt for this frame
    prompts_path = project_dir / "storyboard" / "prompts.json"
    if not prompts_path.exists():
        return {"success": False, "error": "prompts.json not found. Run Director pipeline first."}

    try:
        data = json.loads(prompts_path.read_text(encoding="utf-8"))
        prompts = data.get("prompts", [])

        # Find the prompt
        frame_prompt = None
        for prompt_item in prompts:
            if prompt_item.get("frame_id") == request.frame_id:
                frame_prompt = prompt_item
                break

        if not frame_prompt:
            return {"success": False, "error": f"Frame {request.frame_id} not found in prompts.json"}

        # TODO: Trigger actual image generation via ImageHandler
        # For now, return success with the prompt that would be used
        return {
            "success": True,
            "frame_id": request.frame_id,
            "prompt": frame_prompt.get("prompt"),
            "status": "queued",
            "message": "Frame regeneration queued. This feature requires ImageHandler integration."
        }
    except Exception as e:
        logger.error(f"Error regenerating frame: {e}")
        return {"success": False, "error": str(e)}


@router.post("/{project_path:path}/storyboard/frame/add-camera")
async def add_camera_angle(project_path: str, request: AddCameraRequest):
    """Add a new camera angle to an existing frame.

    Creates a new camera variant (e.g., 1.2.cB from 1.2.cA) with the provided prompt.
    """
    project_dir = Path(project_path)

    # Parse the base frame ID to determine the new camera letter
    parts = request.frame_id.replace("[", "").replace("]", "").split(".")
    if len(parts) < 3:
        return {"success": False, "error": f"Invalid frame ID format: {request.frame_id}"}

    scene_num = parts[0]
    frame_num = parts[1]
    current_camera = parts[2]  # e.g., "cA"

    # Determine next camera letter
    current_letter = current_camera[1] if len(current_camera) > 1 else "A"
    next_letter = chr(ord(current_letter) + 1)
    new_frame_id = f"{scene_num}.{frame_num}.c{next_letter}"

    # Update prompts.json
    prompts_path = project_dir / "storyboard" / "prompts.json"
    if not prompts_path.exists():
        return {"success": False, "error": "prompts.json not found. Run Director pipeline first."}

    try:
        data = json.loads(prompts_path.read_text(encoding="utf-8"))
        prompts = data.get("prompts", [])

        # Check if this camera already exists
        for prompt_item in prompts:
            if prompt_item.get("frame_id") == new_frame_id:
                return {"success": False, "error": f"Camera angle {new_frame_id} already exists"}

        # Find the base frame to copy metadata from
        base_frame = None
        insert_index = len(prompts)
        for i, prompt_item in enumerate(prompts):
            if prompt_item.get("frame_id") == request.frame_id:
                base_frame = prompt_item
                insert_index = i + 1
                break

        # Create new camera entry
        new_camera = {
            "frame_id": new_frame_id,
            "scene": base_frame.get("scene") if base_frame else scene_num,
            "prompt": request.prompt,
            "edited": True,
            "camera_notation": f"[{new_frame_id}]",
            "position_notation": base_frame.get("position_notation") if base_frame else None,
            "lighting_notation": base_frame.get("lighting_notation") if base_frame else None,
            "location_direction": base_frame.get("location_direction") if base_frame else None,
            "tags": base_frame.get("tags", {}) if base_frame else {},
        }

        # Insert after the base frame
        prompts.insert(insert_index, new_camera)
        data["prompts"] = prompts

        # Save back
        prompts_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        return {"success": True, "frame_id": new_frame_id, "prompt": request.prompt}
    except Exception as e:
        logger.error(f"Error adding camera angle: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/{project_path:path}/storyboard/frame/{frame_id}")
async def delete_frame(project_path: str, frame_id: str):
    """Delete a frame from the storyboard.

    Removes the frame from prompts.json and optionally deletes the generated image.
    """
    project_dir = Path(project_path)

    # Update prompts.json
    prompts_path = project_dir / "storyboard" / "prompts.json"
    if not prompts_path.exists():
        return {"success": False, "error": "prompts.json not found"}

    try:
        data = json.loads(prompts_path.read_text(encoding="utf-8"))
        prompts = data.get("prompts", [])

        # Find and remove the frame
        original_count = len(prompts)
        prompts = [p for p in prompts if p.get("frame_id") != frame_id]

        if len(prompts) == original_count:
            return {"success": False, "error": f"Frame {frame_id} not found"}

        data["prompts"] = prompts
        prompts_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Also try to delete the generated image
        storyboard_dir = project_dir / "storyboard_output" / "generated"
        deleted_image = False
        if storyboard_dir.exists():
            for img in storyboard_dir.glob(f"*{frame_id}*"):
                img.unlink()
                deleted_image = True
                logger.info(f"Deleted image: {img}")

        return {
            "success": True,
            "frame_id": frame_id,
            "deleted_image": deleted_image
        }
    except Exception as e:
        logger.error(f"Error deleting frame: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# VERSION CONTROL ENDPOINTS
# =============================================================================

class CreateCheckpointRequest(BaseModel):
    """Request body for creating a checkpoint."""
    name: str
    description: str = ""


class RestoreVersionRequest(BaseModel):
    """Request body for restoring a frame version."""
    frame_id: str
    version_id: str


class RestoreCheckpointRequest(BaseModel):
    """Request body for restoring a checkpoint."""
    checkpoint_id: str


@router.get("/{project_path:path}/storyboard/versions")
async def get_frame_versions(project_path: str, frame_id: Optional[str] = None):
    """Get version history for frames.

    If frame_id is provided, returns versions for that specific frame.
    Otherwise, returns versions for all frames.
    """
    from greenlight.pipelines.parallel_healing_pipeline import FrameVersionManager

    project_dir = Path(project_path)
    version_manager = FrameVersionManager(project_dir)

    if frame_id:
        versions = version_manager.get_versions(frame_id)
        return {
            "frame_id": frame_id,
            "versions": [v.to_dict() for v in versions],
            "total_versions": len(versions)
        }
    else:
        all_versions = version_manager.get_all_frame_versions()
        return {
            "frames": all_versions,
            "total_frames": len(all_versions),
            "total_versions": sum(len(v) for v in all_versions.values())
        }


@router.post("/{project_path:path}/storyboard/versions/restore")
async def restore_frame_version(project_path: str, request: RestoreVersionRequest):
    """Restore a specific version of a frame.

    Archives the current version before restoring.
    """
    from greenlight.pipelines.parallel_healing_pipeline import FrameVersionManager

    project_dir = Path(project_path)
    version_manager = FrameVersionManager(project_dir)

    success = version_manager.restore_version(request.frame_id, request.version_id)

    if success:
        return {
            "success": True,
            "frame_id": request.frame_id,
            "restored_version": request.version_id
        }
    else:
        return {
            "success": False,
            "error": f"Failed to restore version {request.version_id}"
        }


@router.get("/{project_path:path}/storyboard/versions/image/{version_id}")
async def get_version_image(project_path: str, version_id: str, thumbnail: bool = False):
    """Get the image for a specific version.

    Returns the path to the image file for serving.
    If thumbnail=True and version is compressed, returns the thumbnail.
    """
    from greenlight.pipelines.parallel_healing_pipeline import FrameVersionManager
    from fastapi.responses import FileResponse

    project_dir = Path(project_path)
    version_manager = FrameVersionManager(project_dir)

    if thumbnail:
        image_path = version_manager.get_thumbnail_path(version_id)
    else:
        image_path = version_manager.get_full_image_path(version_id)

    if image_path and image_path.exists():
        media_type = "image/jpeg" if image_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
        return FileResponse(image_path, media_type=media_type)
    else:
        return {"error": "Image not found", "version_id": version_id}


@router.get("/{project_path:path}/storyboard/checkpoints")
async def get_checkpoints(project_path: str):
    """Get all checkpoints for the project."""
    from greenlight.pipelines.parallel_healing_pipeline import FrameVersionManager

    project_dir = Path(project_path)
    version_manager = FrameVersionManager(project_dir)

    checkpoints = version_manager.get_checkpoints()
    storage_stats = version_manager.get_storage_stats()

    return {
        "checkpoints": checkpoints,
        "total_checkpoints": len(checkpoints),
        "storage": storage_stats
    }


@router.post("/{project_path:path}/storyboard/checkpoints/create")
async def create_checkpoint(project_path: str, request: CreateCheckpointRequest):
    """Create a new checkpoint of the current storyboard state."""
    from greenlight.pipelines.parallel_healing_pipeline import FrameVersionManager

    project_dir = Path(project_path)
    version_manager = FrameVersionManager(project_dir)

    checkpoint = version_manager.create_checkpoint(request.name, request.description)

    return {
        "success": True,
        "checkpoint": checkpoint.to_dict()
    }


@router.post("/{project_path:path}/storyboard/checkpoints/restore")
async def restore_checkpoint(project_path: str, request: RestoreCheckpointRequest):
    """Restore all frames to a checkpoint state."""
    from greenlight.pipelines.parallel_healing_pipeline import FrameVersionManager

    project_dir = Path(project_path)
    version_manager = FrameVersionManager(project_dir)

    success = version_manager.restore_checkpoint(request.checkpoint_id)

    if success:
        return {
            "success": True,
            "checkpoint_id": request.checkpoint_id,
            "message": "All frames restored to checkpoint state"
        }
    else:
        return {
            "success": False,
            "error": f"Failed to restore checkpoint {request.checkpoint_id}"
        }


@router.delete("/{project_path:path}/storyboard/checkpoints/{checkpoint_id}")
async def delete_checkpoint(project_path: str, checkpoint_id: str):
    """Delete a checkpoint (does not delete the actual archived files)."""
    from greenlight.pipelines.parallel_healing_pipeline import FrameVersionManager

    project_dir = Path(project_path)
    version_manager = FrameVersionManager(project_dir)

    success = version_manager.delete_checkpoint(checkpoint_id)

    if success:
        return {"success": True, "deleted_checkpoint": checkpoint_id}
    else:
        return {"success": False, "error": f"Checkpoint {checkpoint_id} not found"}


@router.get("/{project_path:path}/storyboard/storage-stats")
async def get_storage_stats(project_path: str):
    """Get storage statistics for version control."""
    from greenlight.pipelines.parallel_healing_pipeline import FrameVersionManager

    project_dir = Path(project_path)
    version_manager = FrameVersionManager(project_dir)

    return version_manager.get_storage_stats()


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
    Ensures the reference watcher is running for auto-labeling.

    Handles both legacy format (style at root) and new format (style in global).
    Also handles character arc data which may be nested under 'arc' key.
    """
    characters, locations, props = [], [], []
    style = None

    try:
        project_dir = Path(project_path)

        # Ensure reference watcher is running for this project
        ensure_reference_watcher(project_dir)

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
            data = json.loads(world_config_path.read_text(encoding="utf-8"))

            # Handle new format with 'global' section for style data
            global_data = data.get("global", {})

            for char in data.get("characters", []):
                tag = char.get("tag", "")

                # Handle arc data - may be nested under 'arc' key or at root level
                arc_data = char.get("arc", {})
                want = char.get("want") or arc_data.get("want")
                need = char.get("need") or arc_data.get("need")
                flaw = char.get("flaw") or arc_data.get("flaw")

                # Handle physicality - may be a dict or string
                physicality = char.get("physicality")
                if isinstance(physicality, dict):
                    # Convert dict to readable string
                    phys_parts = []
                    if physicality.get("baseline_posture"):
                        phys_parts.append(f"Posture: {physicality['baseline_posture']}")
                    if physicality.get("gait"):
                        phys_parts.append(f"Gait: {physicality['gait']}")
                    physicality = " | ".join(phys_parts) if phys_parts else None

                # Handle voice_signature - may be a dict or string
                voice_sig = char.get("voice_signature")
                if isinstance(voice_sig, dict):
                    voice_sig = voice_sig.get("description") or str(voice_sig)

                # Get description - prefer visual_appearance if description is role-like
                description = char.get("description", "")
                visual_appearance = char.get("visual_appearance", "")
                if visual_appearance and len(visual_appearance) > len(description):
                    description = visual_appearance

                # Get costume for additional description
                costume = char.get("costume", "")
                if costume and len(description) < 500:
                    description = f"{description}\n\nCostume: {costume}"

                characters.append(WorldEntity(
                    tag=tag,
                    name=char.get("name", ""),
                    description=description,
                    imagePath=find_reference_image(project_dir, tag),
                    relationships=char.get("relationships"),
                    scenes=char.get("scenes"),
                    # Extended character fields
                    role=char.get("role"),
                    want=want,
                    need=need,
                    flaw=flaw,
                    backstory=char.get("backstory"),
                    voice_signature=voice_sig,
                    emotional_tells=char.get("emotional_tells"),
                    physicality=physicality,
                    speech_patterns=char.get("speech_patterns"),
                ))

            for loc in data.get("locations", []):
                tag = loc.get("tag", "")

                # Build rich description from multiple fields
                description = loc.get("description", "")
                atmosphere = loc.get("atmosphere", "")
                if atmosphere:
                    description = f"{description}\n\nAtmosphere: {atmosphere}"

                locations.append(WorldEntity(
                    tag=tag,
                    name=loc.get("name", ""),
                    description=description,
                    imagePath=find_reference_image(project_dir, tag),
                    relationships=loc.get("relationships"),
                    scenes=loc.get("scenes")
                ))

            for prop in data.get("props", []):
                tag = prop.get("tag", "")

                # Build rich description from multiple fields
                description = prop.get("description", "")
                appearance = prop.get("appearance", "")
                significance = prop.get("significance", "")

                if appearance:
                    description = appearance
                if significance:
                    description = f"{description}\n\nSignificance: {significance}"

                props.append(WorldEntity(
                    tag=tag,
                    name=prop.get("name", ""),
                    description=description,
                    imagePath=find_reference_image(project_dir, tag),
                    relationships=prop.get("relationships"),
                    scenes=prop.get("scenes")
                ))

            # Extract style data - check both root level (legacy) and global section (new format)
            style = StyleData(
                visual_style=data.get("visual_style") or global_data.get("visual_style"),
                style_notes=data.get("style_notes") or global_data.get("color_palette"),
                lighting=data.get("lighting") or global_data.get("lighting"),
                vibe=data.get("vibe") or global_data.get("vibe")
            )
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse world_config.json: {e}")
    except Exception as e:
        logger.error(f"Error loading world data: {e}")

    return WorldResponse(characters=characters, locations=locations, props=props, style=style)


class StyleUpdateRequest(BaseModel):
    visual_style: Optional[str] = None
    style_notes: Optional[str] = None
    lighting: Optional[str] = None
    vibe: Optional[str] = None


@router.get("/{project_path:path}/style-data")
async def get_style_data(project_path: str):
    """Get style configuration from world_config.json."""
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


class EntityUpdateRequest(BaseModel):
    """Request body for updating entity fields."""
    description: Optional[str] = None
    name: Optional[str] = None


@router.patch("/{project_path:path}/world/entity/{tag}")
async def update_entity(project_path: str, tag: str, update: EntityUpdateRequest):
    """Update an entity's fields in world_config.json."""
    project_dir = Path(project_path)
    world_config_path = project_dir / "world_bible" / "world_config.json"

    if not world_config_path.exists():
        return {"success": False, "error": "world_config.json not found"}

    try:
        config = json.loads(world_config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid world_config.json"}

    # Find the entity in characters, locations, or props
    entity_found = False
    for category in ["characters", "locations", "props"]:
        entities = config.get(category, [])
        for entity in entities:
            if entity.get("tag") == tag:
                # Update fields that were provided
                if update.description is not None:
                    entity["description"] = update.description
                if update.name is not None:
                    entity["name"] = update.name
                entity_found = True
                break
        if entity_found:
            break

    if not entity_found:
        return {"success": False, "error": f"Entity with tag '{tag}' not found"}

    # Save updated config
    world_config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    return {"success": True, "message": f"Entity '{tag}' updated"}


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
    # Additional fields for editing workflow
    camera_notation: Optional[str] = None
    position_notation: Optional[str] = None
    lighting_notation: Optional[str] = None
    location_direction: Optional[str] = None
    edited: bool = False  # Whether user has edited this prompt


class PromptsResponse(BaseModel):
    prompts: list[PromptItem]
    source: str = "none"  # "prompts_json", "prompts_log", "legacy", "none"


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

                # Extract tags - handle both structured dict format and legacy text format
                prompt = frame_data.get("prompt", frame_data.get("visual_prompt", ""))
                position = frame_data.get("position_notation", "")
                camera_notation = frame_data.get("camera_notation", "")
                lighting = frame_data.get("lighting_notation", "")

                # Extract camera letter from cameras array or parse from notation
                cameras = frame_data.get("cameras", [])
                if cameras and isinstance(cameras, list):
                    # Get camera letter from the cameras array (e.g., "1.1.cA" -> "cA")
                    camera = cameras[0].split(".")[-1] if cameras else "cA"
                elif camera_notation:
                    # Try to extract from notation like "[1.1.cA] (Wide, Eye Level)"
                    match = re.search(r'\[[\d.]+\.([a-zA-Z]+)\]', camera_notation)
                    camera = match.group(1) if match else camera_notation
                else:
                    camera = "cA"

                # Check for structured tags format first
                tags_data = frame_data.get("tags", {})
                if isinstance(tags_data, dict):
                    # New structured format: {characters: [], locations: [], props: []}
                    tags = (
                        tags_data.get("characters", []) +
                        tags_data.get("locations", []) +
                        tags_data.get("props", [])
                    )
                elif isinstance(tags_data, list):
                    # Already a flat list
                    tags = tags_data
                else:
                    # Fallback: extract tags from text using regex
                    all_text = f"{prompt} {position} {camera_notation} {lighting}"
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
    """Get storyboard prompts for editing.

    Priority order:
    1. storyboard/prompts.json - Director output for user editing (preferred)
    2. storyboard_output/prompts_log.json - Storyboard generation log
    3. Legacy shot_prompts.json locations
    """
    project_dir = Path(project_path)
    prompts = []

    # Priority 1: storyboard/prompts.json (Director output for editing)
    prompts_json_path = project_dir / "storyboard" / "prompts.json"

    if prompts_json_path.exists():
        try:
            data = json.loads(prompts_json_path.read_text(encoding="utf-8"))

            # Handle both list format (new) and dict format (legacy)
            if isinstance(data, list):
                prompt_list = data
            elif isinstance(data, dict):
                # Convert dict format (frame_id -> prompt) to list format
                prompt_list = [
                    {"frame_id": frame_id, "prompt": prompt, "scene": frame_id.split(".")[0] if "." in frame_id else "1"}
                    for frame_id, prompt in data.items()
                ]
            else:
                prompt_list = []

            for prompt_data in prompt_list:
                # Handle tags - can be dict or list
                tags = prompt_data.get("tags", [])
                if isinstance(tags, dict):
                    tags = (
                        tags.get("characters", []) +
                        tags.get("locations", []) +
                        tags.get("props", [])
                    )

                prompts.append(PromptItem(
                    id=prompt_data.get("frame_id", ""),
                    prompt=prompt_data.get("prompt", ""),
                    original_prompt=prompt_data.get("prompt", ""),
                    tags=tags,
                    scene=str(prompt_data.get("scene", "")),
                    camera_notation=prompt_data.get("camera_notation"),
                    position_notation=prompt_data.get("position_notation"),
                    lighting_notation=prompt_data.get("lighting_notation"),
                    location_direction=prompt_data.get("location_direction"),
                    edited=prompt_data.get("edited", False),
                ))
            return PromptsResponse(prompts=prompts, source="prompts_json")
        except json.JSONDecodeError:
            pass

    # Priority 2: prompts_log.json (Storyboard generation log)
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
            return PromptsResponse(prompts=prompts, source="prompts_log")
        except json.JSONDecodeError:
            pass

    # Priority 3: Legacy shot_prompts.json locations
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
            return PromptsResponse(prompts=prompts, source="legacy")
        except json.JSONDecodeError:
            pass

    return PromptsResponse(prompts=prompts, source="none")


class SavePromptRequest(BaseModel):
    frame_id: str
    prompt: str


class SavePromptsRequest(BaseModel):
    prompts: list[SavePromptRequest]


class SavePromptsResponse(BaseModel):
    success: bool
    message: str
    saved_count: int = 0


@router.post("/{project_path:path}/prompts/save", response_model=SavePromptsResponse)
async def save_prompts(project_path: str, request: SavePromptsRequest):
    """Save edited prompts to storyboard/prompts.json.

    This allows users to edit prompts before running storyboard generation.
    """
    project_dir = Path(project_path)
    prompts_path = project_dir / "storyboard" / "prompts.json"

    if not prompts_path.exists():
        return SavePromptsResponse(
            success=False,
            message="No prompts.json found. Run Director pipeline first."
        )

    try:
        # Load existing prompts
        prompts_data = json.loads(prompts_path.read_text(encoding="utf-8"))

        # Create a map of frame_id -> edited prompt
        edits = {p.frame_id: p.prompt for p in request.prompts}

        # Update prompts with edits
        saved_count = 0
        for prompt_entry in prompts_data:
            frame_id = prompt_entry.get("frame_id", "")
            if frame_id in edits:
                prompt_entry["prompt"] = edits[frame_id]
                prompt_entry["edited"] = True
                saved_count += 1

        # Save back to file
        prompts_path.write_text(json.dumps(prompts_data, indent=2), encoding="utf-8")

        return SavePromptsResponse(
            success=True,
            message=f"Saved {saved_count} prompt(s)",
            saved_count=saved_count
        )

    except json.JSONDecodeError:
        return SavePromptsResponse(success=False, message="Invalid prompts.json file")
    except Exception as e:
        return SavePromptsResponse(success=False, message=f"Error saving prompts: {str(e)}")


@router.post("/{project_path:path}/prompts/{frame_id}/save")
async def save_single_prompt(project_path: str, frame_id: str, request: SavePromptRequest):
    """Save a single edited prompt to storyboard/prompts.json."""
    project_dir = Path(project_path)
    prompts_path = project_dir / "storyboard" / "prompts.json"

    if not prompts_path.exists():
        return {"success": False, "message": "No prompts.json found. Run Director pipeline first."}

    try:
        # Load existing prompts
        prompts_data = json.loads(prompts_path.read_text(encoding="utf-8"))

        # Find and update the prompt
        found = False
        for prompt_entry in prompts_data:
            if prompt_entry.get("frame_id", "") == frame_id:
                prompt_entry["prompt"] = request.prompt
                prompt_entry["edited"] = True
                found = True
                break

        if not found:
            return {"success": False, "message": f"Frame {frame_id} not found"}

        # Save back to file
        prompts_path.write_text(json.dumps(prompts_data, indent=2), encoding="utf-8")

        return {"success": True, "message": f"Saved prompt for {frame_id}"}

    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}


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
    Ensures the reference watcher is running for auto-labeling.
    """
    from greenlight.core.image_handler import get_image_handler

    project_dir = Path(project_path)

    # Ensure reference watcher is running for this project
    ensure_reference_watcher(project_dir)
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

        # Auto-label the uploaded image in-place
        labeled = False
        try:
            from greenlight.core.reference_labeler import label_image
            labeled = label_image(output_path, tag)
        except Exception as label_error:
            logger.warning(f"Auto-labeling failed: {label_error}")

        return {
            "success": True,
            "path": str(output_path),
            "name": safe_filename,
            "labeled": labeled
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/{project_path:path}/references/label-all")
async def label_all_references_endpoint(project_path: str):
    """Label all existing unlabeled reference images in-place.

    Adds a red background strip at top with [TAG_NAME] in black text.
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        return {"success": False, "error": "Project not found"}

    try:
        from greenlight.core.reference_labeler import label_all_references
        results = label_all_references(project_dir)
        labeled_count = sum(results.values())

        return {
            "success": True,
            "labeled_count": labeled_count,
            "by_tag": results,
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
            status["output_path"] = str(result.image_path) if result.image_path else None
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
    """Execute sheet generation in background using UnifiedReferenceScript.

    Uses the unified reference script API for consistent sheet generation.
    See .augment-guidelines for the UnifiedReferenceScript specification.
    """
    from greenlight.core.image_handler import ImageModel
    from greenlight.references.unified_reference_script import UnifiedReferenceScript

    status = _image_generation_status[process_id]
    project_dir = Path(project_path)
    image_path = Path(image_path_str)

    def log(msg: str):
        status["logs"].append(msg)

    def callback(event: str, data: dict):
        """Progress callback from UnifiedReferenceScript."""
        if event == 'analyzing_image':
            log("🔍 Analyzing image with Gemini 2.5...")
            status["progress"] = 0.2
        elif event == 'generating_profile':
            log("📝 Generating character profile from analysis...")
            status["progress"] = 0.4
        elif event == 'generating_prompt':
            log("✍️ Generating optimized prompt...")
            status["progress"] = 0.5
        elif event == 'generating_image':
            log("🖼️ Generating sheet image...")
            status["progress"] = 0.7

    try:
        status["status"] = "running"
        log(f"🖼️ Generating {tag_type} sheet using {model_name}...")

        # Map model string to ImageModel enum
        model_map = {
            "nano_banana": ImageModel.NANO_BANANA,
            "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
            "seedream": ImageModel.SEEDREAM,
            "flux_2_pro": ImageModel.FLUX_2_PRO,
            "p_image_edit": ImageModel.P_IMAGE_EDIT,
            "flux_1_1_pro": ImageModel.FLUX_1_1_PRO,
        }
        model = model_map.get(model_name, ImageModel.NANO_BANANA_PRO)

        # Use UnifiedReferenceScript for consistent sheet generation
        script = UnifiedReferenceScript(project_dir, callback=callback)

        log("📤 Starting sheet generation pipeline...")
        status["progress"] = 0.1

        # Use convert_image_to_sheet which routes to the appropriate method
        result = await script.convert_image_to_sheet(tag, image_path, model=model)

        if result.success:
            status["progress"] = 1.0
            status["status"] = "complete"
            output_path = result.image_paths[0] if result.image_paths else None
            status["output_path"] = str(output_path) if output_path else None
            log(f"✅ Sheet generated successfully")
            log(f"⏱️ Generation time: {result.generation_time_ms}ms")
            if result.profile_updated:
                log("📋 Character profile updated in world_config.json")

            # Auto-label the generated reference image
            if output_path:
                try:
                    from greenlight.core.reference_labeler import label_image
                    if label_image(output_path, tag):
                        log(f"🏷️ Labeled with [{tag}]")
                except Exception as label_err:
                    logger.warning(f"Auto-labeling failed: {label_err}")
        else:
            status["status"] = "failed"
            status["error"] = result.error
            log(f"❌ Generation failed: {result.error}")

    except Exception as e:
        status["status"] = "failed"
        status["error"] = str(e)
        log(f"❌ Error: {str(e)}")

# ============================================================================
# Location Directional Reference Generation
# ============================================================================

class GenerateDirectionsRequest(BaseModel):
    """Request model for generating all directional views for a location."""
    model: str = "nano_banana_pro"


class GenerateDirectionsResponse(BaseModel):
    """Response model for directional reference generation."""
    success: bool
    message: str
    process_id: Optional[str] = None


@router.post("/{project_path:path}/references/{tag}/generate-directions")
async def generate_location_directions(
    project_path: str,
    tag: str,
    request: GenerateDirectionsRequest
):
    """Generate all 4 directional views (N/E/S/W) for a location tag.

    Uses template-based prompt building (no LLM calls).
    North is generated first, then used as reference for E/S/W.
    """
    import uuid
    import asyncio

    if not tag.startswith("LOC_"):
        return GenerateDirectionsResponse(
            success=False,
            message="Directional generation only available for location tags (LOC_)"
        )

    project_dir = Path(project_path)
    world_config_path = project_dir / "world_bible" / "world_config.json"

    if not world_config_path.exists():
        return GenerateDirectionsResponse(success=False, message="world_config.json not found")

    try:
        world_config = json.loads(world_config_path.read_text(encoding='utf-8'))
    except Exception as e:
        return GenerateDirectionsResponse(success=False, message=f"Failed to load world_config.json: {e}")

    # Find the location entity
    entity = None
    for loc in world_config.get("locations", []):
        if loc.get("tag") == tag:
            entity = loc
            break

    if not entity:
        return GenerateDirectionsResponse(success=False, message=f"Location not found for tag: {tag}")

    # Create process ID and initialize status
    process_id = str(uuid.uuid4())[:8]
    _image_generation_status[process_id] = {
        "type": "location_reference",
        "status": "starting",
        "progress": 0,
        "logs": [f"Starting location reference generation for {tag}..."],
        "tag": tag,
        "output_paths": {},
        "error": None
    }

    # Start background task
    asyncio.create_task(
        _execute_location_directions_generation(
            process_id,
            project_path,
            tag,
            entity,
            request.model
        )
    )

    return GenerateDirectionsResponse(
        success=True,
        message="Location reference generation started",
        process_id=process_id
    )


async def _execute_location_directions_generation(
    process_id: str,
    project_path: str,
    tag: str,
    location_data: dict,
    model_name: str
):
    """Execute location reference generation in background (single image)."""
    from greenlight.core.image_handler import get_image_handler, ImageModel

    status = _image_generation_status[process_id]
    project_dir = Path(project_path)

    def log(msg: str):
        status["logs"].append(msg)

    # Map model string to ImageModel enum
    model_map = {
        "nano_banana": ImageModel.NANO_BANANA,
        "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
        "seedream": ImageModel.SEEDREAM,
        "flux_2_pro": ImageModel.FLUX_2_PRO,
        "p_image_edit": ImageModel.P_IMAGE_EDIT,
        "flux_1_1_pro": ImageModel.FLUX_1_1_PRO,
    }
    model = model_map.get(model_name, ImageModel.NANO_BANANA_PRO)

    try:
        status["status"] = "running"
        log(f"📍 Generating location reference for {tag}...")
        log(f"📷 Using model: {model_name}")

        handler = get_image_handler(project_dir)
        name = location_data.get('name', tag.replace('LOC_', '').replace('_', ' ').title())

        result = await handler.generate_location_reference(
            tag=tag,
            name=name,
            location_data=location_data,
            model=model
        )

        status["progress"] = 1.0
        if result.success:
            log(f"✅ Location reference generated successfully!")
            status["status"] = "complete"
            if result.image_path:
                status["output_paths"]["reference"] = str(result.image_path)
        else:
            log(f"❌ Failed to generate location reference: {result.error}")
            status["status"] = "failed"
            status["error"] = result.error

    except Exception as e:
        log(f"❌ Error: {str(e)}")
        status["status"] = "failed"
        status["error"] = str(e)


# ============================================================================
# Bulk Reference Generation
# ============================================================================

class GenerateAllReferencesRequest(BaseModel):
    """Request model for bulk reference generation."""
    tagType: str  # "characters", "locations", or "props"
    model: str = "nano_banana_pro"
    overwrite: bool = False  # Whether to regenerate existing references
    visual_style: str = "live_action"  # Visual style from world config


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
            entities,
            request.visual_style
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
    entities: list,
    visual_style: str = "live_action"
):
    """Execute reference generation in background.

    Uses template-based prompt building (no LLM calls) before image generation.
    For locations, generates all 4 directional views (N/E/S/W).
    """
    import asyncio
    from datetime import datetime
    from greenlight.core.image_handler import get_image_handler, ImageRequest, ImageModel
    from greenlight.references.prompt_builder import ReferencePromptBuilder
    from greenlight.core.constants import TagCategory

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
        "flux_2_pro": ImageModel.FLUX_2_PRO,
        "p_image_edit": ImageModel.P_IMAGE_EDIT,
        "flux_1_1_pro": ImageModel.FLUX_1_1_PRO,
    }
    model = model_map.get(model_name, ImageModel.NANO_BANANA_PRO)

    # Determine entity type and category
    entity_type = tag_type.lower().rstrip('s')  # "characters" -> "character"
    category_map = {
        "character": TagCategory.CHARACTER,
        "location": TagCategory.LOCATION,
        "prop": TagCategory.PROP,
    }
    category = category_map.get(entity_type, TagCategory.CHARACTER)

    try:
        status["status"] = "running"
        log(f"🎨 Starting reference generation for {len(entities)} {tag_type}...")
        log(f"📷 Using model: {model_name}")
        log(f"🎨 Visual style: {visual_style}")
        log(f"📝 Using template-based prompt building")

        handler = get_image_handler(project_dir)
        prompt_builder = ReferencePromptBuilder(context_engine=handler._context_engine)

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
                # Build prompt via template (no LLM call)
                log(f"   📝 Building prompt from template...")
                prompt_result = prompt_builder.build_prompt(tag, category, entity)

                if entity_type == "character":
                    # Use template-built prompt if available
                    if prompt_result.success and prompt_result.reference_sheet_prompt:
                        log(f"   ✓ Built character sheet prompt")
                        result = await handler.generate_character_sheet(
                            tag=tag,
                            name=name,
                            model=model,
                            character_data=entity,
                            custom_prompt=prompt_result.reference_sheet_prompt
                        )
                    else:
                        log(f"   ⚠️ Using fallback template prompt")
                        result = await handler.generate_character_sheet(
                            tag=tag,
                            name=name,
                            model=model,
                            character_data=entity
                        )

                elif entity_type == "prop":
                    # Use template-built prompt if available
                    if prompt_result.success and prompt_result.reference_sheet_prompt:
                        log(f"   ✓ Built prop sheet prompt")
                        result = await handler.generate_prop_reference(
                            tag=tag,
                            name=name,
                            prop_data=entity,
                            model=model,
                            custom_prompt=prompt_result.reference_sheet_prompt
                        )
                    else:
                        log(f"   ⚠️ Using fallback template prompt")
                        result = await handler.generate_prop_reference(
                            tag=tag,
                            name=name,
                            prop_data=entity,
                            model=model
                        )

                elif entity_type == "location":
                    # For locations, generate a single establishing shot
                    log(f"   📍 Generating location reference...")

                    result = await handler.generate_location_reference(
                        tag=tag,
                        name=name,
                        location_data=entity,
                        model=model
                    )
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



