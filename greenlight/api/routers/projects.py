"""Projects router for Project Greenlight API."""

import json
import re
from pathlib import Path
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

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


class StoryboardResponse(BaseModel):
    frames: list[Frame]


class WorldEntity(BaseModel):
    tag: str
    name: str
    description: str
    imagePath: Optional[str] = None


class WorldResponse(BaseModel):
    characters: list[WorldEntity]
    locations: list[WorldEntity]
    props: list[WorldEntity]


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


@router.get("/{project_path:path}/storyboard", response_model=StoryboardResponse)
async def get_storyboard(project_path: str):
    project_dir = Path(project_path)
    visual_script_path = project_dir / "visual_script.json"
    storyboard_dir = project_dir / "storyboard_output"
    frames = []
    if visual_script_path.exists():
        try:
            data = json.loads(visual_script_path.read_text(encoding="utf-8"))
            for frame_data in data.get("frames", []):
                frame_id = frame_data.get("id", "")
                parts = frame_id.replace("[", "").replace("]", "").split(".")
                scene = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
                frame_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                camera = parts[2] if len(parts) > 2 else "cA"
                image_path = None
                if storyboard_dir.exists():
                    for img in storyboard_dir.glob(f"*{frame_id}*"):
                        image_path = str(img)
                        break
                frames.append(Frame(id=frame_id, scene=scene, frame=frame_num, camera=camera,
                                    prompt=frame_data.get("prompt", ""), imagePath=image_path))
        except json.JSONDecodeError:
            pass
    return StoryboardResponse(frames=frames)


def find_reference_image(references_dir: Path, tag: str) -> Optional[str]:
    if not references_dir.exists():
        return None
    tag_dir = references_dir / tag
    if tag_dir.exists():
        for img in tag_dir.glob("*"):
            if img.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
                return str(img)
    return None


@router.get("/{project_path:path}/world", response_model=WorldResponse)
async def get_world(project_path: str):
    project_dir = Path(project_path)
    world_config_path = project_dir / "world_config.json"
    references_dir = project_dir / "references"
    characters, locations, props = [], [], []
    if world_config_path.exists():
        try:
            data = json.loads(world_config_path.read_text(encoding="utf-8"))
            for char in data.get("characters", []):
                tag = char.get("tag", "")
                characters.append(WorldEntity(tag=tag, name=char.get("name", ""),
                    description=char.get("description", ""), imagePath=find_reference_image(references_dir, tag)))
            for loc in data.get("locations", []):
                tag = loc.get("tag", "")
                locations.append(WorldEntity(tag=tag, name=loc.get("name", ""),
                    description=loc.get("description", ""), imagePath=find_reference_image(references_dir, tag)))
            for prop in data.get("props", []):
                tag = prop.get("tag", "")
                props.append(WorldEntity(tag=tag, name=prop.get("name", ""),
                    description=prop.get("description", ""), imagePath=find_reference_image(references_dir, tag)))
        except json.JSONDecodeError:
            pass
    return WorldResponse(characters=characters, locations=locations, props=props)


@router.get("/{project_path:path}/gallery", response_model=GalleryResponse)
async def get_gallery(project_path: str):
    project_dir = Path(project_path)
    storyboard_dir = project_dir / "storyboard_output"
    images = []
    if storyboard_dir.exists():
        for img in storyboard_dir.glob("*"):
            if img.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
                images.append(GalleryImage(path=str(img), name=img.name))
    return GalleryResponse(images=images)


@router.get("/{project_path:path}/references", response_model=ReferencesResponse)
async def get_references(project_path: str):
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
        for tag_dir in references_dir.iterdir():
            if tag_dir.is_dir():
                tag = tag_dir.name
                images = []
                for img in tag_dir.glob("*"):
                    if img.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
                        is_key = "key" in img.name.lower() or img.name.startswith("_")
                        images.append(ReferenceImage(path=str(img), name=img.name, isKey=is_key))
                if images:
                    references.append(ReferenceTag(tag=tag, name=names.get(tag, tag), images=images))
    return ReferencesResponse(references=references)

