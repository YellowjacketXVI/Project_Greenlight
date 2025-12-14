"""
Greenlight Beat Extractor - Story Pipeline v3.0

Extracts beats from prose AFTER generation (post-hoc).

The beat extractor:
1. Reads completed prose
2. Identifies natural beat boundaries
3. Classifies beat types
4. Outputs beat_sheet.json for Director pipeline

Key principle: Beats are discovered, not prescribed.
The writer writes organically; beats are extracted for technical use.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from enum import Enum

from greenlight.core.logging_config import get_logger
from greenlight.agents.prose_agent import ProseResult

logger = get_logger("agents.beat_extractor")


class BeatType(Enum):
    """Types of story beats."""
    ESTABLISHING = "establishing"      # Scene setup, location intro
    DIALOGUE = "dialogue"              # Character conversation
    ACTION = "action"                  # Physical action, movement
    REACTION = "reaction"              # Emotional response
    REVELATION = "revelation"          # Information revealed
    TRANSITION = "transition"          # Scene change, time skip
    CLIMAX = "climax"                  # Peak tension moment
    RESOLUTION = "resolution"          # Tension release


@dataclass
class Beat:
    """A single story beat extracted from prose."""
    beat_id: str  # scene.beat format (e.g., "1.1", "1.2")
    scene_number: int
    beat_number: int
    beat_type: BeatType
    content: str
    start_word: int  # Word index in scene prose
    end_word: int
    characters: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "scene": self.scene_number,
            "beat": self.beat_number,
            "type": self.beat_type.value,
            "content": self.content,
            "word_range": [self.start_word, self.end_word],
            "characters": self.characters
        }


@dataclass
class SceneBeats:
    """Beats extracted from a single scene."""
    scene_number: int
    beats: List[Beat] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene": self.scene_number,
            "beat_count": len(self.beats),
            "beats": [b.to_dict() for b in self.beats]
        }


@dataclass
class BeatSheet:
    """Complete beat sheet for the story."""
    scenes: List[SceneBeats] = field(default_factory=list)
    
    @property
    def total_beats(self) -> int:
        return sum(len(s.beats) for s in self.scenes)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_scenes": len(self.scenes),
            "total_beats": self.total_beats,
            "scenes": [s.to_dict() for s in self.scenes]
        }
    
    def save(self, path: Path):
        """Save beat sheet to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)


class BeatExtractor:
    """
    Extracts beats from prose after generation.
    
    Uses LLM to identify natural beat boundaries and classify types.
    """
    
    SYSTEM_PROMPT = """You are a story analyst. You identify beats in prose.

A beat is a unit of story action - a moment where something changes.

Beat types:
- ESTABLISHING: Scene setup, location description
- DIALOGUE: Character conversation
- ACTION: Physical movement, activity
- REACTION: Emotional response to events
- REVELATION: New information revealed
- TRANSITION: Scene change, time skip
- CLIMAX: Peak tension moment
- RESOLUTION: Tension release

For each beat, identify:
1. The beat type
2. The exact text (quote from prose)
3. Characters involved

Output format:
BEAT 1: [TYPE]
TEXT: "exact quote from prose"
CHARACTERS: CHAR_TAG1, CHAR_TAG2

BEAT 2: [TYPE]
TEXT: "exact quote from prose"
CHARACTERS: CHAR_TAG1"""

    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller
    
    async def extract_beats(self, prose_results: List[ProseResult]) -> BeatSheet:
        """
        Extract beats from all prose results.
        
        Args:
            prose_results: List of ProseResult from prose generation
            
        Returns:
            BeatSheet with all extracted beats
        """
        scene_beats_list = []
        
        for result in prose_results:
            scene_beats = await self._extract_scene_beats(result)
            scene_beats_list.append(scene_beats)
        
        logger.info(f"Extracted {sum(len(s.beats) for s in scene_beats_list)} beats from {len(prose_results)} scenes")
        return BeatSheet(scenes=scene_beats_list)

    async def _extract_scene_beats(self, prose_result: ProseResult) -> SceneBeats:
        """Extract beats from a single scene."""
        prompt = f"""Analyze this scene and identify the beats:

SCENE {prose_result.scene_number}:
{prose_result.prose}

Identify 2-5 beats in this scene. For each beat, specify:
1. Beat type (ESTABLISHING, DIALOGUE, ACTION, REACTION, REVELATION, TRANSITION, CLIMAX, RESOLUTION)
2. The exact text (quote from the prose)
3. Characters involved (use CHAR_ prefix)

Output format:
BEAT 1: [TYPE]
TEXT: "exact quote"
CHARACTERS: CHAR_NAME1, CHAR_NAME2"""

        try:
            response = await self.llm_caller(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=800
            )

            beats = self._parse_beats(response, prose_result)
            return SceneBeats(scene_number=prose_result.scene_number, beats=beats)

        except Exception as e:
            logger.error(f"Beat extraction failed for scene {prose_result.scene_number}: {e}")
            return SceneBeats(scene_number=prose_result.scene_number, beats=[])

    def _parse_beats(self, response: str, prose_result: ProseResult) -> List[Beat]:
        """Parse LLM response into Beat objects."""
        beats = []

        # Pattern to match beat blocks
        beat_pattern = r'BEAT\s+(\d+):\s*\[?(\w+)\]?\s*\n\s*TEXT:\s*["\']?([^"\']+)["\']?\s*\n\s*CHARACTERS:\s*([^\n]*)'

        matches = re.findall(beat_pattern, response, re.IGNORECASE)

        for i, match in enumerate(matches):
            beat_num = int(match[0])
            beat_type_str = match[1].upper()
            content = match[2].strip()
            characters_str = match[3].strip()

            # Parse beat type
            try:
                beat_type = BeatType(beat_type_str.lower())
            except ValueError:
                beat_type = BeatType.ACTION  # Default

            # Parse characters
            characters = [c.strip() for c in characters_str.split(',') if c.strip()]

            # Find word positions in prose
            prose_lower = prose_result.prose.lower()
            content_lower = content.lower()[:50]  # First 50 chars for matching

            start_pos = prose_lower.find(content_lower)
            if start_pos >= 0:
                start_word = len(prose_result.prose[:start_pos].split())
                end_word = start_word + len(content.split())
            else:
                start_word = 0
                end_word = len(content.split())

            beat = Beat(
                beat_id=f"{prose_result.scene_number}.{beat_num}",
                scene_number=prose_result.scene_number,
                beat_number=beat_num,
                beat_type=beat_type,
                content=content,
                start_word=start_word,
                end_word=end_word,
                characters=characters
            )
            beats.append(beat)

        # If no beats parsed, create a default one
        if not beats:
            beats.append(Beat(
                beat_id=f"{prose_result.scene_number}.1",
                scene_number=prose_result.scene_number,
                beat_number=1,
                beat_type=BeatType.ACTION,
                content=prose_result.prose[:100] + "...",
                start_word=0,
                end_word=prose_result.word_count,
                characters=[]
            ))

        return beats
