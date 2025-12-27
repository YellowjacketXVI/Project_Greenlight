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
        llm_name: The LLM model name (e.g., "claude-haiku-4.5", "claude-opus-4.5")

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
        llm_name: The LLM model name (e.g., "claude-haiku-4.5", "claude-opus-4.5")

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


def load_character_data(project_path: Path) -> Dict[str, Dict[str, str]]:
    """Load character data from world_config.json for prompt enhancement.

    Args:
        project_path: Path to the project directory

    Returns:
        Dictionary mapping character tags to their data (name, description, role)
    """
    import json

    world_config_path = project_path / "world_bible" / "world_config.json"
    if not world_config_path.exists():
        return {}

    try:
        with open(world_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        character_data = {}
        for char in config.get("characters", []):
            tag = char.get("tag", "")
            if tag:
                character_data[tag] = {
                    "name": char.get("name", ""),
                    "description": char.get("description", ""),
                    "role": char.get("role", "")
                }

        return character_data

    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load character data: {e}")
        return {}


def load_entity_data(project_path: Path) -> Dict[str, Dict[str, str]]:
    """Load all entity data (characters, locations, props) from world_config.json.

    Args:
        project_path: Path to the project directory

    Returns:
        Dictionary mapping all tags to their data (name, description)
    """
    import json

    world_config_path = project_path / "world_bible" / "world_config.json"
    if not world_config_path.exists():
        return {}

    try:
        with open(world_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        entity_data = {}

        # Load characters
        for char in config.get("characters", []):
            tag = char.get("tag", "")
            if tag:
                entity_data[tag] = {
                    "name": char.get("name", ""),
                    "description": char.get("description", ""),
                    "type": "character"
                }

        # Load locations
        for loc in config.get("locations", []):
            tag = loc.get("tag", "")
            if tag:
                entity_data[tag] = {
                    "name": loc.get("name", ""),
                    "description": loc.get("description", ""),
                    "type": "location"
                }

        # Load props
        for prop in config.get("props", []):
            tag = prop.get("tag", "")
            if tag:
                entity_data[tag] = {
                    "name": prop.get("name", ""),
                    "description": prop.get("description", ""),
                    "type": "prop"
                }

        return entity_data

    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load entity data: {e}")
        return {}


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
        direction_upper = location_direction.upper()
        direction_lower = location_direction.lower()

        # Look for directional images with various naming patterns
        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
            # Try generated format: [{tag}]_{direction}_gen_*.ext (most common)
            gen_pattern = f"[{tag}]_{direction_lower}_gen_*{ext}"
            gen_matches = list(refs_dir.glob(gen_pattern))
            if gen_matches:
                # Return most recent (sorted by name = by timestamp)
                return sorted(gen_matches)[-1]

            # Try alternate generated format without brackets
            gen_pattern_alt = f"{tag}_{direction_lower}_gen_*{ext}"
            gen_matches_alt = list(refs_dir.glob(gen_pattern_alt))
            if gen_matches_alt:
                return sorted(gen_matches_alt)[-1]

            # Try simple format: {tag}_{DIRECTION}.ext
            directional_path = refs_dir / f"{tag}_{direction_upper}{ext}"
            if directional_path.exists():
                return directional_path

            # Try {DIRECTION}.ext format
            directional_path = refs_dir / f"{direction_upper}{ext}"
            if directional_path.exists():
                return directional_path

            # Try lowercase direction
            directional_path = refs_dir / f"{direction_lower}{ext}"
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


def detect_time_of_day(prompt: str) -> Optional[str]:
    """Detect time of day from prompt text.

    Args:
        prompt: The prompt text

    Returns:
        Time of day string: "morning", "day", "evening", "night", or None
    """
    prompt_lower = prompt.lower()

    if any(word in prompt_lower for word in ['morning', 'dawn', 'sunrise', 'early light']):
        return "morning"
    elif any(word in prompt_lower for word in ['daylight', 'afternoon', 'midday', 'noon', 'daytime']):
        return "day"
    elif any(word in prompt_lower for word in ['evening', 'dusk', 'sunset', 'twilight']):
        return "evening"
    elif any(word in prompt_lower for word in ['night', 'midnight', 'moonlight', 'starlight']):
        return "night"

    return None


def enforce_time_of_day_consistency(prompt: str) -> str:
    """Enforce time-of-day consistency in prompts.

    Detects time-of-day mentions and adds explicit constraints to prevent
    contradictions (e.g., "morning" scene showing a moon).

    Args:
        prompt: The prompt text

    Returns:
        Prompt with time-of-day enforcement if needed
    """
    time_of_day = detect_time_of_day(prompt)

    # Add explicit time constraints
    if time_of_day == "morning":
        return "TIME: Morning/dawn lighting - no moon visible, warm golden sunlight. " + prompt
    elif time_of_day == "day":
        return "TIME: Daytime - bright natural daylight, no moon. " + prompt
    elif time_of_day == "evening":
        return "TIME: Evening/dusk - warm orange/pink sky, setting sun. " + prompt
    elif time_of_day == "night":
        return "TIME: Nighttime - dark sky, moon/stars visible, artificial lighting. " + prompt

    return prompt


def get_time_negative_prompt(prompt: str) -> Optional[str]:
    """Get negative prompt for time-of-day enforcement.

    Args:
        prompt: The prompt text

    Returns:
        Negative prompt string to exclude conflicting time elements, or None
    """
    from greenlight.core.image_handler import (
        NEGATIVE_PROMPT_MORNING,
        NEGATIVE_PROMPT_DAY,
        NEGATIVE_PROMPT_EVENING,
        NEGATIVE_PROMPT_NIGHT
    )

    time_of_day = detect_time_of_day(prompt)

    if time_of_day == "morning":
        return NEGATIVE_PROMPT_MORNING
    elif time_of_day == "day":
        return NEGATIVE_PROMPT_DAY
    elif time_of_day == "evening":
        return NEGATIVE_PROMPT_EVENING
    elif time_of_day == "night":
        return NEGATIVE_PROMPT_NIGHT

    return None


def compress_prompt_for_image_model(prompt: str, tags: Dict[str, List[str]]) -> str:
    """Compress and optimize a cinematic prompt for image generation models.

    Image models don't understand abstract concepts like "emotional beats" or
    "visual subtext". This function:
    1. Strips non-visual metadata (BEAT, CONTINUITY_FROM, visual subtext, etc.)
    2. Extracts and prioritizes concrete visual descriptions
    3. Adds explicit character count constraints to prevent duplication
    4. Enforces time-of-day consistency
    5. Limits to ~120 words for better model comprehension

    Args:
        prompt: The original cinematic prompt
        tags: Dictionary with 'characters', 'locations', 'props' lists

    Returns:
        Optimized prompt for image generation
    """
    # Remove metadata brackets that image models can't interpret
    # [BEAT: ...], [LIGHTING: ...], [DOF: ...], etc.
    cleaned = re.sub(r'\[BEAT:[^\]]*\]', '', prompt)
    cleaned = re.sub(r'\[LIGHTING:[^\]]*\]', '', cleaned)
    cleaned = re.sub(r'\[DOF:[^\]]*\]', '', cleaned)
    cleaned = re.sub(r'\[CONTINUITY_FROM:[^\]]*\]', '', cleaned)

    # Remove "Visual subtext:" sections - abstract concepts
    cleaned = re.sub(r'Visual subtext:[^.]*\.', '', cleaned)

    # Remove director terminology that confuses image models
    cleaned = re.sub(r'FOREGROUND:', 'In front:', cleaned)
    cleaned = re.sub(r'MIDGROUND:', 'Center:', cleaned)
    cleaned = re.sub(r'BACKGROUND:', 'Behind:', cleaned)

    # Clean up multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Enforce time-of-day consistency
    cleaned = enforce_time_of_day_consistency(cleaned)

    # Count characters in the scene to add explicit constraints
    char_tags = tags.get('characters', [])
    if len(char_tags) == 1:
        # Single character - add explicit "one person" constraint
        char_tag = char_tags[0]
        char_name = char_tag.replace("CHAR_", "").replace("_", " ").title()
        constraint = f"IMPORTANT: Show exactly ONE person in this image - {char_name} [{char_tag}]. Do NOT add any other people. "
        cleaned = constraint + cleaned
    elif len(char_tags) == 2:
        # Two characters - be explicit about who is who
        char1_name = char_tags[0].replace("CHAR_", "").replace("_", " ").title()
        char2_name = char_tags[1].replace("CHAR_", "").replace("_", " ").title()
        constraint = f"IMPORTANT: Show exactly TWO people - {char1_name} [{char_tags[0]}] and {char2_name} [{char_tags[1]}]. Match each to their reference. "
        cleaned = constraint + cleaned
    elif len(char_tags) > 2:
        # Multiple characters - list them all
        char_names = [f"{t.replace('CHAR_', '').replace('_', ' ').title()} [{t}]" for t in char_tags]
        char_list = ', '.join(char_names)
        constraint = f"IMPORTANT: Show exactly {len(char_tags)} people: {char_list}. Match each to their reference. "
        cleaned = constraint + cleaned

    # Allow richer prompts - director now generates 80-120 word detailed prompts
    # Only truncate if excessively long
    words = cleaned.split()
    if len(words) > 180:
        cleaned = ' '.join(words[:180])

    return cleaned


def build_labeled_prompt(
    prompt: str,
    tag_refs: List[tuple],
    has_prior_frame: bool,
    tags: Optional[Dict[str, List[str]]] = None,
    character_data: Optional[Dict[str, Dict[str, str]]] = None
) -> str:
    """Build a prompt with labeled reference image mappings and character descriptions.

    Inserts a reference mapping section so the model knows which image corresponds to which tag.
    Also compresses and optimizes the prompt for better image model comprehension.
    Includes physical descriptions for characters to improve consistency.

    Args:
        prompt: The original prompt text
        tag_refs: List of (tag, path) tuples for reference images
        has_prior_frame: Whether a prior frame is included as reference
        tags: Optional dictionary with 'characters', 'locations', 'props' for optimization
        character_data: Optional dict mapping character tags to their data (name, description)

    Returns:
        The optimized prompt with reference labels prepended
    """
    # Compress and optimize prompt for image models
    if tags:
        prompt = compress_prompt_for_image_model(prompt, tags)

    if not tag_refs and not has_prior_frame:
        return prompt

    # Build reference mapping with clearer format for image models
    ref_parts = []
    char_descriptions = []
    img_num = 1

    for tag, _ in tag_refs:
        if tag.startswith("CHAR_"):
            # For characters, include physical description if available
            char_info = character_data.get(tag, {}) if character_data else {}
            char_name = char_info.get("name", tag.replace("CHAR_", "").replace("_", " ").title())

            # Extract key physical features for the reference guide
            description = char_info.get("description", "")
            if description:
                # Extract first 2-3 sentences of physical description
                sentences = description.split(". ")[:3]
                short_desc = ". ".join(sentences)
                if not short_desc.endswith("."):
                    short_desc += "."
                ref_parts.append(f"Image {img_num} shows [{tag}] ({char_name})")
                char_descriptions.append(f"[{tag}] = {char_name}: {short_desc}")
            else:
                ref_parts.append(f"Image {img_num} shows [{tag}] ({char_name})")
        else:
            # Locations and props
            ref_parts.append(f"Image {img_num} shows [{tag}]")
        img_num += 1

    if has_prior_frame:
        ref_parts.append(f"Image {img_num} is the previous frame for continuity")

    # Build the reference section
    ref_section = "REFERENCE GUIDE: " + "; ".join(ref_parts) + ". "

    # Add character descriptions if we have any
    if char_descriptions:
        ref_section += "CHARACTER DETAILS: " + " | ".join(char_descriptions) + " "

    ref_section += "CRITICAL: Match character faces and appearances EXACTLY to their reference images. "

    # Insert reference section at beginning of prompt
    return ref_section + prompt


def build_scene_context(
    scene_frames: List[Dict[str, Any]],
    current_frame_idx: int,
    entity_data: Dict[str, Dict[str, str]],
    world_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build comprehensive scene context from frames for stateless prompting.

    Creates a context object containing:
    - Scene summary (time of day, primary location, characters present)
    - Prior frames context (what happened before this frame)
    - Visual continuity notes

    Args:
        scene_frames: List of all frames in the current scene
        current_frame_idx: Index of the current frame being generated
        entity_data: Dictionary mapping tags to entity data (name, description)
        world_config: Optional world configuration with lighting/vibe info

    Returns:
        Dictionary with scene context for prompt enhancement
    """
    if not scene_frames or current_frame_idx >= len(scene_frames):
        return {}

    current_frame = scene_frames[current_frame_idx]
    prior_frames = scene_frames[:current_frame_idx]

    # Aggregate scene information
    all_characters = set()
    all_locations = set()
    all_props = set()
    time_of_day = None

    for frame in scene_frames:
        tags = frame.get("tags", {})
        if isinstance(tags, dict):
            all_characters.update(tags.get("characters", []))
            all_locations.update(tags.get("locations", []))
            all_props.update(tags.get("props", []))

        # Detect time of day from any frame prompt
        if not time_of_day:
            time_of_day = detect_time_of_day(frame.get("prompt", ""))

    # Build prior frames summary (what happened before)
    prior_summary = []
    for i, pframe in enumerate(prior_frames[-3:]):  # Last 3 frames for context
        beat = pframe.get("beat", "")
        prompt_preview = pframe.get("prompt", "")[:100]
        if beat:
            prior_summary.append(f"Frame {pframe.get('frame_id', i+1)}: {beat}")
        elif prompt_preview:
            prior_summary.append(f"Frame {pframe.get('frame_id', i+1)}: {prompt_preview}...")

    # Get primary location - prefer current frame's location, then nearest neighbor
    primary_location = None
    location_desc = ""

    # First check if current frame has a location
    current_tags = current_frame.get("tags", {})
    if isinstance(current_tags, dict) and current_tags.get("locations"):
        primary_location = current_tags["locations"][0]
    else:
        # Look at nearest frames for location context (prefer prior, then next)
        # This handles intercutting scenes better than just taking first from set
        for pframe in reversed(prior_frames):  # Check prior frames, most recent first
            ptags = pframe.get("tags", {})
            if isinstance(ptags, dict) and ptags.get("locations"):
                primary_location = ptags["locations"][0]
                break

        # If still no location, check frames after current
        if not primary_location:
            remaining_frames = scene_frames[current_frame_idx + 1:]
            for nframe in remaining_frames:
                ntags = nframe.get("tags", {})
                if isinstance(ntags, dict) and ntags.get("locations"):
                    primary_location = ntags["locations"][0]
                    break

        # Last resort: take first from aggregated set
        if not primary_location and all_locations:
            primary_location = list(all_locations)[0]

    if primary_location and primary_location in entity_data:
        location_desc = entity_data[primary_location].get("description", "")

    # Build character list with names
    character_list = []
    for char_tag in all_characters:
        char_info = entity_data.get(char_tag, {})
        char_name = char_info.get("name", char_tag.replace("CHAR_", "").replace("_", " ").title())
        character_list.append(f"{char_name} [{char_tag}]")

    # Get world lighting/vibe if available
    lighting = ""
    vibe = ""
    if world_config:
        lighting = world_config.get("lighting", "")
        vibe = world_config.get("vibe", "")

    return {
        "scene_number": current_frame.get("scene_number", 1),
        "frame_in_scene": current_frame_idx + 1,
        "total_frames_in_scene": len(scene_frames),
        "time_of_day": time_of_day or "day",
        "primary_location": primary_location,
        "location_description": location_desc[:200] if location_desc else "",
        "characters_in_scene": character_list,
        "props_in_scene": list(all_props),
        "prior_frames_summary": prior_summary,
        "lighting_style": lighting[:150] if lighting else "",
        "scene_vibe": vibe[:100] if vibe else "",
    }


def build_stateless_prompt(
    base_prompt: str,
    scene_context: Dict[str, Any],
    tag_refs: List[tuple],
    prior_frame_prompt: Optional[str] = None,
    has_prior_frame_image: bool = False,
    tags: Optional[Dict[str, List[str]]] = None,
    character_data: Optional[Dict[str, Dict[str, str]]] = None,
    entity_data: Optional[Dict[str, Dict[str, str]]] = None,
    world_config: Optional[Dict[str, Any]] = None
) -> str:
    """Build a robust stateless prompt optimized for Flux 2 Pro coherence.

    Structure (order matters for model attention):
    1. SHOT TYPE - Camera framing first (most important for composition)
    2. SUBJECT - Who/what is the focus with physical descriptions
    3. ACTION - What they're doing
    4. SETTING - Where (location with description)
    5. LIGHTING - Time of day, mood, atmosphere
    6. STYLE - Visual style suffix

    Args:
        base_prompt: The original frame prompt
        scene_context: Scene context from build_scene_context()
        tag_refs: List of (tag, path) tuples for reference images
        prior_frame_prompt: The prompt from the previous frame (for continuity)
        has_prior_frame_image: Whether prior frame image is included as reference
        tags: Dictionary with 'characters', 'locations', 'props' lists
        character_data: Dict mapping character tags to their data
        entity_data: Dict mapping all tags to their data (locations, props too)
        world_config: World configuration with style info

    Returns:
        Fully self-contained prompt optimized for image generation
    """
    entity_data = entity_data or {}
    character_data = character_data or {}
    world_config = world_config or {}

    # Extract shot type from base prompt (Wide, Medium, Close up, etc.)
    shot_type = _extract_shot_type(base_prompt)

    # Get time of day
    time_of_day = scene_context.get("time_of_day", "day") if scene_context else "day"

    # Get primary location and its description - allow full description for rich context
    primary_location = scene_context.get("primary_location", "") if scene_context else ""
    location_desc = ""
    if primary_location:
        loc_data = entity_data.get(primary_location, {})
        # Use first 2 sentences for setting context (richer than before)
        full_desc = loc_data.get("description", "") if loc_data else ""
        if full_desc:
            sentences = full_desc.split(". ")[:2]
            location_desc = ". ".join(sentences)
            if location_desc and not location_desc.endswith("."):
                location_desc += "."

    # Build character appearance strings
    char_tags = tags.get("characters", []) if tags else []
    char_appearances = []
    for char_tag in char_tags:
        char_info = character_data.get(char_tag, entity_data.get(char_tag, {}))
        char_name = char_info.get("name", char_tag.replace("CHAR_", "").replace("_", " ").title())
        desc = char_info.get("description", "")
        if desc:
            # Extract key visual features (first 3 sentences for richer detail)
            sentences = desc.split(". ")[:3]
            short_desc = ". ".join(sentences)
            if not short_desc.endswith("."):
                short_desc += "."
            char_appearances.append(f"{char_name}: {short_desc}")
        else:
            char_appearances.append(char_name)

    # Build the structured prompt
    prompt_parts = []

    # === 1. REFERENCE IMAGE MAPPING (Critical for Flux) ===
    # For reference-based generation, include KEY visual traits to anchor the reference
    char_briefs = []  # Brief visual anchors for each character
    if tag_refs:
        ref_items = []
        for i, (tag, _) in enumerate(tag_refs, 1):
            if tag.startswith("CHAR_"):
                char_info = character_data.get(tag, entity_data.get(tag, {}))
                name = char_info.get("name", tag.replace("CHAR_", "").replace("_", " ").title())
                desc = char_info.get("description", "")
                brief = _extract_visual_anchor(name, desc)
                ref_items.append(f"Image {i} = {brief}")
                char_briefs.append(brief)
            elif tag.startswith("LOC_"):
                loc_info = entity_data.get(tag, {})
                name = loc_info.get("name", tag.replace("LOC_", "").replace("_", " ").title())
                ref_items.append(f"Image {i} = {name} (setting)")
            else:
                ref_items.append(f"Image {i} = {tag}")

        if has_prior_frame_image:
            ref_items.append(f"Image {len(tag_refs) + 1} = previous frame")

        prompt_parts.append(f"REFERENCE IMAGES: {'; '.join(ref_items)}. MATCH EXACTLY.")

    # === 2. SHOT TYPE (Composition priority) ===
    if shot_type:
        prompt_parts.append(f"{shot_type}.")

    # === 3. CHARACTER COUNT (With visual anchors from reference) ===
    if char_briefs:
        if len(char_briefs) == 1:
            prompt_parts.append(f"ONE PERSON: {char_briefs[0]}.")
        elif len(char_briefs) == 2:
            prompt_parts.append(f"TWO PEOPLE: {' and '.join(char_briefs)}.")
        else:
            prompt_parts.append(f"{len(char_briefs)} PEOPLE: {', '.join(char_briefs)}.")

    # === 4. MAIN ACTION (Clean prompt without metadata) ===
    cleaned_prompt = _clean_prompt_for_action(base_prompt)

    # Remove shot type variations from beginning since we already added it
    shot_patterns_remove = [
        r'^(extreme\s+)?wide\s+shot\s+(of\s+)?',
        r'^(extreme\s+)?close[\s-]?up\s+(of\s+)?',
        r'^medium\s+(close[\s-]?up\s+)?(shot\s+)?(of\s+)?',
        r'^full\s+shot\s+(of\s+)?',
        r'^over[\s-]?the[\s-]?shoulder\s+(shot\s+)?(of\s+)?',
        r'^(pov|point\s+of\s+view)\s+(shot\s+)?(of\s+)?',
        r'^(high|low)\s+angle\s+(shot\s+)?(of\s+)?',
        r'^establishing\s+shot\s+(of\s+)?',
    ]
    for pattern in shot_patterns_remove:
        cleaned_prompt = re.sub(pattern, '', cleaned_prompt, flags=re.IGNORECASE)

    # Allow full prompt detail - director prompts are now 80-120 words with rich descriptions
    words = cleaned_prompt.split()
    if len(words) > 120:
        cleaned_prompt = ' '.join(words[:120])

    if cleaned_prompt.strip():
        prompt_parts.append(cleaned_prompt.strip())

    # === 5. SETTING (Location with description) ===
    if primary_location and location_desc:
        prompt_parts.append(f"SETTING: {location_desc}")
    elif primary_location:
        loc_name = primary_location.replace("LOC_", "").replace("_", " ").title()
        prompt_parts.append(f"LOCATION: {loc_name}")

    # === 6. LIGHTING & ATMOSPHERE ===
    time_lighting = {
        "morning": "golden morning light, sunrise",
        "day": "bright daylight",
        "evening": "warm sunset, golden hour",
        "night": "moonlight and lanterns, night"
    }
    lighting = time_lighting.get(time_of_day, "natural lighting")
    prompt_parts.append(f"LIGHTING: {lighting}")

    # === 7. VISUAL STYLE SUFFIX ===
    visual_style = world_config.get("visual_style", "")
    vibe = world_config.get("vibe", "")

    style_parts = []
    if visual_style:
        style_map = {
            "live_action": "photorealistic, cinematic",
            "anime": "anime style",
            "animation_3d": "3D rendered",
            "comic": "comic book style",
            "watercolor": "watercolor painting",
            "oil_painting": "oil painting"
        }
        style_parts.append(style_map.get(visual_style, visual_style))

    if vibe:
        # Take just key mood words
        vibe_words = vibe.split(",")[:2]
        style_parts.append(", ".join(w.strip() for w in vibe_words))

    if style_parts:
        prompt_parts.append(f"STYLE: {', '.join(style_parts)}")

    # === 8. CONTINUITY (if prior frame) ===
    if has_prior_frame_image and prior_frame_prompt:
        prior_preview = prior_frame_prompt[:100].strip()
        prompt_parts.append(f"CONTINUITY: Match previous frame exactly for character positions and lighting.")

    return " ".join(prompt_parts)


def _extract_visual_anchor(name: str, description: str) -> str:
    """Extract key visual traits from description to anchor reference image.

    Flux needs explicit age/gender/ethnicity cues even with reference images.
    Returns a brief visual anchor like "young Asian woman Mei" or "older man General".
    """
    if not description:
        return name

    desc_lower = description.lower()

    # Detect age indicators - be more specific to avoid false positives
    age = ""
    # Explicit old age indicators
    if any(w in desc_lower for w in ["elderly", "aged ", "silver hair", "silver-white", "grey hair",
                                      "gray hair", "old ", "white hair", "wrinkled", "age spots"]):
        age = "older"
    elif any(w in desc_lower for w in ["middle-aged", "mature", "in his forties", "in her forties",
                                        "in his fifties", "in her fifties"]):
        age = "middle-aged"
    elif any(w in desc_lower for w in ["young", "youthful", "adolescent", "teenage", "early twenties",
                                        "late teens", "in his twenties", "in her twenties"]):
        age = "young"
    else:
        # Default to young for characters without explicit age markers
        # (most protagonists/love interests are young adults)
        age = "young"

    # Detect gender - check male first since "he" is in many female words like "she", "her"
    gender = ""
    if any(w in desc_lower for w in [" man ", " man,", " man.", "male", " his ", " he ", " boy ", "gentleman"]):
        gender = "man"
    elif any(w in desc_lower for w in ["woman", "female", " her ", " she ", " girl", "lady", "courtesan", "maiden"]):
        gender = "woman"

    # Detect ethnicity from description if explicitly mentioned
    ethnicity = ""
    ethnicity_keywords = {
        "asian": "Asian",
        "chinese": "Asian",
        "japanese": "Asian",
        "korean": "Asian",
        "caucasian": "Caucasian",
        "european": "European",
        "african": "African",
        "black": "Black",
        "latino": "Latino",
        "hispanic": "Hispanic",
        "indian": "Indian",
        "middle eastern": "Middle Eastern",
    }
    for keyword, eth_value in ethnicity_keywords.items():
        if keyword in desc_lower:
            ethnicity = eth_value
            break

    # Build brief visual anchor
    parts = []
    if age:
        parts.append(age)
    if ethnicity:
        parts.append(ethnicity)
    if gender:
        parts.append(gender)
    parts.append(name)

    return " ".join(parts)


def _clean_prompt_for_action(prompt: str) -> str:
    """Clean prompt for action section - remove metadata but not character constraints."""
    # Remove metadata brackets
    cleaned = re.sub(r'\[BEAT:[^\]]*\]', '', prompt)
    cleaned = re.sub(r'\[LIGHTING:[^\]]*\]', '', cleaned)
    cleaned = re.sub(r'\[DOF:[^\]]*\]', '', cleaned)
    cleaned = re.sub(r'\[CONTINUITY_FROM:[^\]]*\]', '', cleaned)

    # Remove visual subtext
    cleaned = re.sub(r'Visual subtext:[^.]*\.', '', cleaned)

    # Simplify director terminology
    cleaned = re.sub(r'FOREGROUND:', 'In front:', cleaned)
    cleaned = re.sub(r'MIDGROUND:', 'Center:', cleaned)
    cleaned = re.sub(r'BACKGROUND:', 'Behind:', cleaned)

    # Remove separator lines
    cleaned = re.sub(r'---+', '', cleaned)

    # Clean up whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


def _extract_shot_type(prompt: str) -> str:
    """Extract camera shot type from prompt."""
    shot_patterns = [
        (r'\b(extreme\s+wide\s+shot)\b', 'Extreme wide shot'),
        (r'\b(wide\s+shot)\b', 'Wide shot'),
        (r'\b(full\s+shot)\b', 'Full shot'),
        (r'\b(medium\s+wide\s+shot)\b', 'Medium wide shot'),
        (r'\b(medium\s+shot)\b', 'Medium shot'),
        (r'\b(medium\s+close[\s-]?up)\b', 'Medium close-up'),
        (r'\b(close[\s-]?up)\b', 'Close-up'),
        (r'\b(extreme\s+close[\s-]?up)\b', 'Extreme close-up'),
        (r'\b(over[\s-]?the[\s-]?shoulder)\b', 'Over-the-shoulder shot'),
        (r'\b(pov|point\s+of\s+view)\b', 'POV shot'),
        (r'\b(high\s+angle)\b', 'High angle shot'),
        (r'\b(low\s+angle)\b', 'Low angle shot'),
        (r'\b(bird\'?s?\s+eye)\b', 'Bird\'s eye view'),
        (r'\b(establishing\s+shot)\b', 'Establishing shot'),
    ]

    prompt_lower = prompt.lower()
    for pattern, shot_name in shot_patterns:
        if re.search(pattern, prompt_lower):
            return shot_name

    return ""


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
