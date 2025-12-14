"""
Greenlight Shot List Extractor

Parses Visual_Script to extract structured shot list with:
- Scenes, frames, cameras
- Reference tags for storyboard generation
- Prompt data for image generation

Output: Structured shot list for storyboard table and image generation.
"""

import re
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from datetime import datetime

from greenlight.core.logging_config import get_logger
from greenlight.config.notation_patterns import REGEX_PATTERNS, get_compiled_patterns

logger = get_logger("pipelines.shot_list_extractor")


@dataclass
class ShotEntry:
    """A single shot/frame entry in the shot list."""
    shot_id: str                          # Unique ID: scene_frame (e.g., "1.3")
    scene_number: int
    frame_number: int
    
    # Visual content
    prompt: str = ""                      # Image generation prompt
    camera: str = ""                      # Camera instruction
    position: str = ""                    # Character positioning
    lighting: str = ""                    # Lighting instruction
    
    # Tags for reference lookup
    character_tags: List[str] = field(default_factory=list)
    location_tags: List[str] = field(default_factory=list)
    prop_tags: List[str] = field(default_factory=list)
    all_tags: List[str] = field(default_factory=list)
    
    # Reference images
    reference_images: Dict[str, str] = field(default_factory=dict)  # tag -> image_path
    
    # Metadata
    duration_estimate: str = "3s"
    aspect_ratio: str = "16:9"
    generated_image_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "scene_number": self.scene_number,
            "frame_number": self.frame_number,
            "prompt": self.prompt,
            "camera": self.camera,
            "position": self.position,
            "lighting": self.lighting,
            "character_tags": self.character_tags,
            "location_tags": self.location_tags,
            "prop_tags": self.prop_tags,
            "all_tags": self.all_tags,
            "reference_images": self.reference_images,
            "duration_estimate": self.duration_estimate,
            "aspect_ratio": self.aspect_ratio,
            "generated_image_path": self.generated_image_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShotEntry':
        return cls(
            shot_id=data["shot_id"],
            scene_number=data["scene_number"],
            frame_number=data["frame_number"],
            prompt=data.get("prompt", ""),
            camera=data.get("camera", ""),
            position=data.get("position", ""),
            lighting=data.get("lighting", ""),
            character_tags=data.get("character_tags", []),
            location_tags=data.get("location_tags", []),
            prop_tags=data.get("prop_tags", []),
            all_tags=data.get("all_tags", []),
            reference_images=data.get("reference_images", {}),
            duration_estimate=data.get("duration_estimate", "3s"),
            aspect_ratio=data.get("aspect_ratio", "16:9"),
            generated_image_path=data.get("generated_image_path")
        )


@dataclass
class SceneGroup:
    """A group of shots belonging to a scene."""
    scene_number: int
    scene_title: str = ""
    location: str = ""
    shots: List[ShotEntry] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_number": self.scene_number,
            "scene_title": self.scene_title,
            "location": self.location,
            "shots": [s.to_dict() for s in self.shots],
            "shot_count": len(self.shots)
        }


@dataclass
class ShotList:
    """Complete shot list extracted from Visual_Script."""
    scenes: List[SceneGroup] = field(default_factory=list)
    total_shots: int = 0
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source_file: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenes": [s.to_dict() for s in self.scenes],
            "total_shots": self.total_shots,
            "extracted_at": self.extracted_at,
            "source_file": self.source_file,
            "scene_count": len(self.scenes)
        }
    
    def get_all_shots(self) -> List[ShotEntry]:
        """Get flat list of all shots."""
        shots = []
        for scene in self.scenes:
            shots.extend(scene.shots)
        return shots
    
    def get_shot_by_id(self, shot_id: str) -> Optional[ShotEntry]:
        """Get a specific shot by ID."""
        for scene in self.scenes:
            for shot in scene.shots:
                if shot.shot_id == shot_id:
                    return shot
        return None


class ShotListExtractor:
    """
    Extracts structured shot list from Visual_Script.
    
    Parses frame notations, camera instructions, and tags
    to create a complete shot list for storyboard generation.
    """
    
    def __init__(self, tag_registry: Dict[str, Any] = None):
        self.patterns = get_compiled_patterns()
        self.tag_registry = tag_registry or {}
    
    def extract(self, visual_script: str, source_file: str = "") -> ShotList:
        """
        Extract shot list from Visual_Script content.
        """
        logger.info("Extracting shot list from Visual_Script")
        
        shot_list = ShotList(source_file=source_file)
        scenes = self._parse_scenes(visual_script)
        
        for scene_num, scene_content in scenes:
            scene_group = self._parse_scene(scene_num, scene_content)
            shot_list.scenes.append(scene_group)
            shot_list.total_shots += len(scene_group.shots)
        
        logger.info(f"Extracted {shot_list.total_shots} shots from {len(scenes)} scenes")
        return shot_list

    def _parse_scenes(self, content: str) -> List[tuple]:
        """Parse content into scene sections."""
        scenes = []

        # Try scene header pattern first
        scene_pattern = re.compile(r'^##\s+Scene\s+(\d+)[^\n]*\n(.*?)(?=^##\s+Scene|\Z)',
                                   re.MULTILINE | re.DOTALL)
        matches = scene_pattern.findall(content)

        if matches:
            for scene_num, scene_content in matches:
                scenes.append((int(scene_num), scene_content.strip()))
        else:
            # Fallback: treat entire content as scene 1
            scenes.append((1, content))

        return scenes

    def _parse_scene(self, scene_num: int, content: str) -> SceneGroup:
        """Parse a single scene into a SceneGroup."""
        scene = SceneGroup(scene_number=scene_num)

        # Extract scene title/location from first line
        first_line = content.split('\n')[0] if content else ""
        scene.scene_title = first_line[:100] if first_line else f"Scene {scene_num}"

        # Find location tag
        loc_match = re.search(REGEX_PATTERNS["location_tag"], content)
        if loc_match:
            scene.location = loc_match.group(0).strip('[]')

        # Extract all frames in this scene
        scene.shots = self._extract_frames(content, scene_num)

        return scene

    def _extract_frames(self, content: str, scene_num: int) -> List[ShotEntry]:
        """Extract all frame entries from scene content.

        Supports both old and new notation formats:
        - Old: {frame_X.Y} followed by notations
        - New: [X.Y.cA] (Shot Type) scene.frame.camera notation
        """
        shots = []

        # Try new scene.frame.camera notation first: [1.2.cA] (Wide)
        new_pattern = re.compile(
            r'\[(\d+)\.(\d+)\.c([A-Z])\]\s*\([^)]+\)(.*?)(?=\[\d+\.\d+\.c[A-Z]\]|\Z)',
            re.DOTALL
        )
        new_matches = new_pattern.findall(content)

        if new_matches:
            for match in new_matches:
                scene_n = int(match[0])
                frame_n = int(match[1])
                camera_letter = match[2]
                block_content = match[3]

                shot = self._parse_frame_block(scene_n, frame_n, block_content)
                # Update shot_id to include camera
                shot.shot_id = f"{scene_n}.{frame_n}.c{camera_letter}"
                shots.append(shot)
            return shots

        # Fallback to old pattern: {frame_X.Y} followed by notations and prompt
        old_pattern = re.compile(
            r'\{frame_(\d+)\.(\d+)\}(.*?)(?=\{frame_|\Z)',
            re.DOTALL
        )
        old_matches = old_pattern.findall(content)

        for match in old_matches:
            scene_n = int(match[0])
            frame_n = int(match[1])
            block_content = match[2]

            shot = self._parse_frame_block(scene_n, frame_n, block_content)
            shots.append(shot)

        # If no frame blocks found, try simpler extraction
        if not shots:
            shots = self._fallback_extraction(content, scene_num)

        return shots

    def _parse_frame_block(self, scene_num: int, frame_num: int, content: str) -> ShotEntry:
        """Parse a single frame block into a ShotEntry."""
        shot = ShotEntry(
            shot_id=f"{scene_num}.{frame_num}",
            scene_number=scene_num,
            frame_number=frame_num
        )

        # Extract camera notation
        cam_match = re.search(REGEX_PATTERNS["camera"], content)
        if cam_match:
            shot.camera = cam_match.group(1).strip()

        # Extract position notation
        pos_match = re.search(REGEX_PATTERNS["position"], content)
        if pos_match:
            shot.position = pos_match.group(1).strip()

        # Extract lighting notation
        light_match = re.search(REGEX_PATTERNS["lighting"], content)
        if light_match:
            shot.lighting = light_match.group(1).strip()

        # Extract prompt notation
        prompt_match = re.search(REGEX_PATTERNS["prompt"], content)
        if prompt_match:
            shot.prompt = prompt_match.group(1).strip()
        else:
            # Use cleaned content as prompt
            shot.prompt = self._clean_for_prompt(content)

        # Extract tags
        shot.character_tags = re.findall(REGEX_PATTERNS["character_tag"], content)
        shot.location_tags = re.findall(REGEX_PATTERNS["location_tag"], content)
        shot.prop_tags = re.findall(REGEX_PATTERNS["prop_tag"], content)
        shot.all_tags = shot.character_tags + shot.location_tags + shot.prop_tags

        # Clean tag brackets
        shot.character_tags = [t.strip('[]') for t in shot.character_tags]
        shot.location_tags = [t.strip('[]') for t in shot.location_tags]
        shot.prop_tags = [t.strip('[]') for t in shot.prop_tags]
        shot.all_tags = [t.strip('[]') for t in shot.all_tags]

        # Look up reference images from registry
        shot.reference_images = self._get_reference_images(shot.all_tags)

        return shot

    def _clean_for_prompt(self, content: str) -> str:
        """Clean content for use as image prompt.

        Removes both old and new notation formats:
        - Old: {frame_X.Y}
        - New: [X.Y.cA] (Shot Type)
        """
        # Remove notation markers
        cleaned = re.sub(r'\[CAM:[^\]]+\]', '', content)
        cleaned = re.sub(r'\[POS:[^\]]+\]', '', cleaned)
        cleaned = re.sub(r'\[LIGHT:[^\]]+\]', '', cleaned)
        cleaned = re.sub(r'\[PROMPT:[^\]]+\]', '', cleaned)
        # Remove old format: {frame_X.Y}
        cleaned = re.sub(r'\{frame_\d+\.\d+\}', '', cleaned)
        # Remove new format: [X.Y.cA] (Shot Type)
        cleaned = re.sub(r'\[\d+\.\d+\.c[A-Z]\]\s*\([^)]+\)', '', cleaned)
        # Remove camera letter prefix: cA. cB. etc.
        cleaned = re.sub(r'\bc[A-Z]\.\s*', '', cleaned)

        # Clean whitespace
        cleaned = ' '.join(cleaned.split())

        # Limit to 250 words
        words = cleaned.split()
        if len(words) > 250:
            cleaned = ' '.join(words[:250])

        return cleaned.strip()

    def _get_reference_images(self, tags: List[str]) -> Dict[str, str]:
        """Look up reference images for tags."""
        references = {}
        for tag in tags:
            if tag in self.tag_registry:
                entry = self.tag_registry[tag]
                if isinstance(entry, dict) and entry.get('image_path'):
                    references[tag] = entry['image_path']
        return references

    def _fallback_extraction(self, content: str, scene_num: int) -> List[ShotEntry]:
        """Fallback extraction when no frame blocks found."""
        shots = []

        # Split by paragraphs and create shots
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        for i, para in enumerate(paragraphs[:10], 1):  # Max 10 shots per scene
            shot = ShotEntry(
                shot_id=f"{scene_num}.{i}",
                scene_number=scene_num,
                frame_number=i,
                prompt=self._clean_for_prompt(para)
            )

            # Extract any tags
            shot.character_tags = [t.strip('[]') for t in re.findall(REGEX_PATTERNS["character_tag"], para)]
            shot.location_tags = [t.strip('[]') for t in re.findall(REGEX_PATTERNS["location_tag"], para)]
            shot.prop_tags = [t.strip('[]') for t in re.findall(REGEX_PATTERNS["prop_tag"], para)]
            shot.all_tags = shot.character_tags + shot.location_tags + shot.prop_tags

            shots.append(shot)

        return shots

    def save(self, shot_list: ShotList, output_path: Path) -> None:
        """Save shot list to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(shot_list.to_dict(), f, indent=2)

        logger.info(f"Saved shot list to {output_path}")

    def load(self, input_path: Path) -> ShotList:
        """Load shot list from JSON file."""
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        shot_list = ShotList(
            total_shots=data.get("total_shots", 0),
            extracted_at=data.get("extracted_at", ""),
            source_file=data.get("source_file", "")
        )

        for scene_data in data.get("scenes", []):
            scene = SceneGroup(
                scene_number=scene_data["scene_number"],
                scene_title=scene_data.get("scene_title", ""),
                location=scene_data.get("location", "")
            )
            for shot_data in scene_data.get("shots", []):
                scene.shots.append(ShotEntry.from_dict(shot_data))
            shot_list.scenes.append(scene)

        return shot_list


class StoryboardPromptGenerator:
    """
    Generates storyboard image prompts from shot list.

    Combines shot data with reference tags to create
    complete prompts for image generation.
    """

    def __init__(
        self,
        style_notes: str = "Cinematic, detailed, professional",
        aspect_ratio: str = "16:9",
        tag_registry: Dict[str, Any] = None
    ):
        self.style_notes = style_notes
        self.aspect_ratio = aspect_ratio
        self.tag_registry = tag_registry or {}

    def generate_prompt(self, shot: ShotEntry) -> str:
        """Generate a complete image generation prompt for a shot."""
        parts = []

        # Base prompt
        if shot.prompt:
            parts.append(shot.prompt)

        # Camera instruction
        if shot.camera:
            parts.append(f"Camera: {shot.camera}")

        # Lighting
        if shot.lighting:
            parts.append(f"Lighting: {shot.lighting}")

        # Character descriptions from registry
        for tag in shot.character_tags:
            if tag in self.tag_registry:
                entry = self.tag_registry[tag]
                if isinstance(entry, dict):
                    desc = entry.get('visual_description') or entry.get('description', '')
                    if desc:
                        parts.append(f"{tag.replace('CHAR_', '')}: {desc[:100]}")

        # Location description
        for tag in shot.location_tags:
            if tag in self.tag_registry:
                entry = self.tag_registry[tag]
                if isinstance(entry, dict):
                    desc = entry.get('description', '')
                    if desc:
                        parts.append(f"Setting: {desc[:100]}")

        # Style notes
        parts.append(f"Style: {self.style_notes}")
        parts.append(f"Aspect ratio: {self.aspect_ratio}")

        return "\n".join(parts)

    def generate_all_prompts(self, shot_list: ShotList) -> List[Dict[str, Any]]:
        """Generate prompts for all shots in the list."""
        prompts = []

        for shot in shot_list.get_all_shots():
            prompt_data = {
                "shot_id": shot.shot_id,
                "scene_number": shot.scene_number,
                "frame_number": shot.frame_number,
                "prompt": self.generate_prompt(shot),
                "reference_tags": shot.all_tags,
                "reference_images": shot.reference_images,
                "camera": shot.camera,
                "lighting": shot.lighting,
                "position": shot.position
            }
            prompts.append(prompt_data)

        return prompts

    def save_prompts(self, prompts: List[Dict], output_path: Path) -> None:
        """Save prompts to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "prompts": prompts,
            "count": len(prompts),
            "generated_at": datetime.now().isoformat(),
            "style_notes": self.style_notes,
            "aspect_ratio": self.aspect_ratio
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(prompts)} storyboard prompts to {output_path}")

