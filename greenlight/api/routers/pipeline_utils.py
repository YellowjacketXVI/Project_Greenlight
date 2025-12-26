"""Shared pipeline utilities for Project Greenlight API.

Contains common functions used across multiple pipeline routers to avoid duplication.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional

from greenlight.core.logging_config import get_logger
from greenlight.core.config import GreenlightConfig, FunctionLLMMapping, get_config
from greenlight.core.constants import LLMFunction
from greenlight.llm import LLMManager

logger = get_logger("api.pipeline_utils")


def extract_prompts_from_visual_script(visual_script: dict) -> List[dict]:
    """Extract prompts from visual_script.json for user editing.

    Creates a flat list of prompts with frame metadata that can be edited
    before storyboard generation.

    Args:
        visual_script: The visual script dictionary containing scenes and frames

    Returns:
        List of prompt objects with frame_id, scene, prompt, tags, etc.
    """
    prompts = []

    for scene in visual_script.get("scenes", []):
        scene_num = scene.get("scene_number", 0)
        for frame in scene.get("frames", []):
            frame_id = frame.get("frame_id", "")
            prompt_entry = {
                "frame_id": frame_id,
                "scene": scene_num,
                "prompt": frame.get("prompt", ""),
                "camera_notation": frame.get("camera_notation", ""),
                "position_notation": frame.get("position_notation", ""),
                "lighting_notation": frame.get("lighting_notation", ""),
                "tags": frame.get("tags", {"characters": [], "locations": [], "props": []}),
                "location_direction": frame.get("location_direction", "NORTH"),
                "cameras": frame.get("cameras", [frame_id]),
                "edited": False,  # Track if user has edited this prompt
            }
            prompts.append(prompt_entry)

    return prompts


def setup_llm_manager(llm_name: str) -> LLMManager:
    """Set up an LLM manager with the specified model.

    Args:
        llm_name: The LLM model name (e.g., "claude-sonnet-4.5")

    Returns:
        Configured LLMManager instance
    """
    base_config = get_config()
    custom_config = GreenlightConfig()
    custom_config.llm_configs = base_config.llm_configs.copy()
    custom_config.function_mappings = {}

    # Map LLM name to config key
    llm_id_config = llm_name.replace("-", "_")
    selected_config = custom_config.llm_configs.get(llm_id_config)
    if not selected_config:
        # Fallback to first available config
        selected_config = next(iter(custom_config.llm_configs.values()))

    # Set all functions to use the selected LLM
    for function in LLMFunction:
        custom_config.function_mappings[function] = FunctionLLMMapping(
            function=function, primary_config=selected_config, fallback_config=None
        )

    return LLMManager(custom_config)


def get_selected_llm_model(llm_name: str) -> str:
    """Get the actual model name for a given LLM selection.

    Args:
        llm_name: The LLM model name (e.g., "claude-sonnet-4.5")

    Returns:
        The actual model identifier string
    """
    base_config = get_config()
    llm_id_config = llm_name.replace("-", "_")
    selected_config = base_config.llm_configs.get(llm_id_config)
    if not selected_config:
        selected_config = next(iter(base_config.llm_configs.values()))
    return selected_config.model


def extract_tags_from_prompt(prompt: str) -> List[str]:
    """Extract all tags from a frame prompt.

    Tags are in format: [CHAR_NAME], [LOC_NAME], [PROP_NAME], etc.

    Args:
        prompt: The prompt text to extract tags from

    Returns:
        List of tag names without brackets
    """
    pattern = r'\[(CHAR_|LOC_|PROP_|CONCEPT_|EVENT_|ENV_)[A-Z0-9_]+\]'
    full_tags = re.findall(r'\[(?:CHAR_|LOC_|PROP_|CONCEPT_|EVENT_|ENV_)[A-Z0-9_]+\]', prompt)
    # Remove brackets for directory lookup
    return [tag[1:-1] for tag in full_tags]


def get_scene_from_frame_id(frame_id: str) -> Optional[str]:
    """Extract scene number from frame_id (e.g., '1.2.cA' -> '1').

    Args:
        frame_id: The frame identifier string

    Returns:
        The scene number as a string, or None if parsing fails
    """
    parts = frame_id.split(".")
    if parts:
        return parts[0]
    return None


def get_key_reference_for_tag(
    project_path: Path,
    tag: str,
    location_direction: Optional[str] = None
) -> Optional[Path]:
    """Get the key reference image for a tag.

    Looks in {project_path}/references/{tag}/ for the starred/key image.
    For LOC_ tags with location_direction, looks for directional images first.

    Args:
        project_path: Path to the project directory
        tag: The tag to get reference for (e.g., "CHAR_MEI", "LOC_PALACE")
        location_direction: For LOC_ tags, the direction (NORTH, EAST, SOUTH, WEST)

    Returns:
        Path to the reference image, or None if not found
    """
    refs_dir = project_path / "references" / tag
    if not refs_dir.exists():
        return None

    # For LOC_ tags with direction, look for directional image first
    if tag.startswith("LOC_") and location_direction:
        direction = location_direction.upper()
        # Look for directional image: {tag}_{direction}.png or {direction}.png
        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
            # Try {tag}_{DIRECTION}.ext format
            directional_path = refs_dir / f"{tag}_{direction}{ext}"
            if directional_path.exists():
                return directional_path
            # Try {DIRECTION}.ext format
            directional_path = refs_dir / f"{direction}{ext}"
            if directional_path.exists():
                return directional_path
            # Try lowercase direction
            directional_path = refs_dir / f"{direction.lower()}{ext}"
            if directional_path.exists():
                return directional_path

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


def build_labeled_prompt(
    prompt: str,
    tag_refs: List[tuple],
    has_prior_frame: bool
) -> str:
    """Build a prompt with labeled reference image mappings.

    Inserts a reference mapping section so the model knows which image corresponds to which tag.
    Format: "Reference Images: [1] [CHAR_JOHN], [2] [LOC_PALACE], [3] Prior Frame"

    Args:
        prompt: The original prompt text
        tag_refs: List of (tag, path) tuples for reference images
        has_prior_frame: Whether a prior frame is included as reference

    Returns:
        The prompt with reference labels prepended
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


def parse_frames_from_raw_visual_script(raw_text: str) -> List[Dict[str, Any]]:
    """Parse frames from raw visual_script text when structured scenes array is empty.

    Extracts frames from text format like:
    (/scene_frame_chunk_start/)
    [1.2.cA] (Frame)
    [CAM: ...]
    [POS: ...]
    [LIGHT: ...]
    [PROMPT: ...]
    (/scene_frame_chunk_end/)

    Args:
        raw_text: The raw visual script text to parse

    Returns:
        List of frame dictionaries with frame_id, prompt, scene_number, etc.
    """
    frames = []

    # Pattern to match frame blocks with scene.frame.camera notation
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
