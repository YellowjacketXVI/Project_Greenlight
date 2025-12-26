"""
Greenlight Scene Summarizer

Provides cross-scene context summarization for long scripts.
Generates progressive summaries to maintain global context without token bloat.

Features:
- Scene-by-scene summarization
- Hierarchical summarization (scenes → acts → story)
- "Story so far" context for late scenes
- Character arc tracking across scenes
- Narrative thread continuity
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable, Awaitable
from enum import Enum

from greenlight.core.logging_config import get_logger
from greenlight.utils.unicode_utils import count_tokens_estimate

logger = get_logger("context.summarizer")


class SummaryLevel(Enum):
    """Levels of summarization detail."""
    DETAILED = "detailed"      # 150-200 words per scene
    STANDARD = "standard"      # 50-100 words per scene
    COMPRESSED = "compressed"  # 25-50 words per scene
    MINIMAL = "minimal"        # 10-20 words per scene


@dataclass
class SceneSummary:
    """Summary of a single scene."""
    scene_number: int
    title: str = ""
    summary: str = ""
    characters_featured: List[str] = field(default_factory=list)
    location: str = ""
    key_events: List[str] = field(default_factory=list)
    emotional_beats: List[str] = field(default_factory=list)
    narrative_threads_advanced: List[str] = field(default_factory=list)
    token_count: int = 0

    def to_context_string(self, level: SummaryLevel = SummaryLevel.STANDARD) -> str:
        """Convert to context string at specified detail level."""
        if level == SummaryLevel.MINIMAL:
            return f"Scene {self.scene_number}: {self.title or self.summary[:50]}"

        elif level == SummaryLevel.COMPRESSED:
            chars = ", ".join(self.characters_featured[:3]) if self.characters_featured else "—"
            return f"Scene {self.scene_number} ({chars}): {self.summary[:100]}"

        elif level == SummaryLevel.STANDARD:
            parts = [f"## Scene {self.scene_number}: {self.title}"]
            if self.location:
                parts.append(f"Location: [{self.location}]")
            if self.characters_featured:
                parts.append(f"Characters: {', '.join(self.characters_featured)}")
            parts.append(self.summary)
            return "\n".join(parts)

        else:  # DETAILED
            parts = [f"## Scene {self.scene_number}: {self.title}"]
            if self.location:
                parts.append(f"Location: [{self.location}]")
            if self.characters_featured:
                parts.append(f"Characters: {', '.join(self.characters_featured)}")
            parts.append(f"\n{self.summary}")
            if self.key_events:
                parts.append(f"\nKey Events: {'; '.join(self.key_events)}")
            if self.emotional_beats:
                parts.append(f"Emotional Beats: {'; '.join(self.emotional_beats)}")
            return "\n".join(parts)


@dataclass
class ActSummary:
    """Summary of an act (group of scenes)."""
    act_number: int
    scenes: List[int]  # Scene numbers in this act
    summary: str = ""
    arc_progression: str = ""  # How the act advances the story
    character_developments: Dict[str, str] = field(default_factory=dict)
    themes_explored: List[str] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Convert to context string."""
        parts = [f"### Act {self.act_number} (Scenes {self.scenes[0]}-{self.scenes[-1]})"]
        parts.append(self.summary)
        if self.arc_progression:
            parts.append(f"Arc: {self.arc_progression}")
        return "\n".join(parts)


@dataclass
class CharacterArc:
    """Tracks a character's arc across scenes."""
    tag: str
    name: str
    appearances: List[int] = field(default_factory=list)  # Scene numbers
    arc_points: List[Tuple[int, str]] = field(default_factory=list)  # (scene, description)
    relationships_evolved: Dict[str, List[Tuple[int, str]]] = field(default_factory=dict)
    current_state: str = ""  # Latest state summary

    def to_context_string(self) -> str:
        """Convert to context string."""
        parts = [f"[{self.tag}] Arc:"]
        for scene_num, point in self.arc_points[-3:]:  # Last 3 arc points
            parts.append(f"  Scene {scene_num}: {point}")
        if self.current_state:
            parts.append(f"  Current: {self.current_state}")
        return "\n".join(parts)


@dataclass
class NarrativeThread:
    """Tracks a narrative thread across scenes."""
    thread_id: str
    name: str
    introduced_scene: int
    current_status: str = "active"  # active, resolved, dormant
    progression: List[Tuple[int, str]] = field(default_factory=list)  # (scene, update)

    def to_context_string(self) -> str:
        """Convert to context string."""
        status_icon = {"active": "→", "resolved": "✓", "dormant": "⋯"}.get(self.current_status, "?")
        parts = [f"{status_icon} {self.name} (from Scene {self.introduced_scene}):"]
        for scene_num, update in self.progression[-2:]:
            parts.append(f"  Scene {scene_num}: {update}")
        return "\n".join(parts)


class SceneSummarizer:
    """
    Manages scene summarization and cross-scene context.

    Provides:
    - Individual scene summaries
    - Hierarchical act summaries
    - "Story so far" context
    - Character arc tracking
    - Narrative thread tracking

    Usage:
        summarizer = SceneSummarizer(llm_caller)

        # Summarize scenes as they're generated
        for scene in scenes:
            await summarizer.add_scene(scene_number, scene_content)

        # Get context for a new scene
        context = summarizer.get_story_so_far(current_scene=5)
    """

    def __init__(
        self,
        llm_caller: Optional[Callable[..., Awaitable[str]]] = None,
        scenes_per_act: int = 3,
        max_token_budget: int = 2000
    ):
        """
        Initialize the scene summarizer.

        Args:
            llm_caller: Optional LLM caller for generating summaries
            scenes_per_act: Number of scenes per act for grouping
            max_token_budget: Maximum tokens for "story so far" context
        """
        self.llm_caller = llm_caller
        self.scenes_per_act = scenes_per_act
        self.max_token_budget = max_token_budget

        # Storage
        self.scene_summaries: Dict[int, SceneSummary] = {}
        self.act_summaries: Dict[int, ActSummary] = {}
        self.character_arcs: Dict[str, CharacterArc] = {}
        self.narrative_threads: Dict[str, NarrativeThread] = {}

        # Scene content cache (for re-summarization)
        self._scene_content: Dict[int, str] = {}

    async def add_scene(
        self,
        scene_number: int,
        content: str,
        characters: List[str] = None,
        location: str = "",
        generate_summary: bool = True
    ) -> SceneSummary:
        """
        Add a scene and generate its summary.

        Args:
            scene_number: Scene number
            content: Scene content
            characters: Characters in scene
            location: Location tag
            generate_summary: Whether to generate LLM summary

        Returns:
            SceneSummary for the scene
        """
        self._scene_content[scene_number] = content

        # Create or update summary
        if generate_summary and self.llm_caller:
            summary = await self._generate_scene_summary(
                scene_number, content, characters or [], location
            )
        else:
            summary = self._extract_scene_summary_heuristic(
                scene_number, content, characters or [], location
            )

        self.scene_summaries[scene_number] = summary

        # Update character arcs
        for char_tag in summary.characters_featured:
            self._update_character_arc(char_tag, scene_number, content)

        # Check if we need to generate act summary
        act_number = (scene_number - 1) // self.scenes_per_act + 1
        act_scenes = [
            s for s in range(
                (act_number - 1) * self.scenes_per_act + 1,
                act_number * self.scenes_per_act + 1
            )
            if s in self.scene_summaries
        ]

        if len(act_scenes) == self.scenes_per_act:
            await self._generate_act_summary(act_number, act_scenes)

        return summary

    async def _generate_scene_summary(
        self,
        scene_number: int,
        content: str,
        characters: List[str],
        location: str
    ) -> SceneSummary:
        """Generate scene summary using LLM."""
        prompt = f"""Summarize this scene concisely (50-100 words).

SCENE {scene_number}:
{content[:3000]}

Extract:
1. TITLE: A short evocative title (3-5 words)
2. SUMMARY: What happens in 50-100 words
3. KEY_EVENTS: 2-3 bullet points of major events
4. EMOTIONAL_BEATS: 1-2 emotional turning points

Format your response as:
TITLE: [title]
SUMMARY: [summary]
KEY_EVENTS:
- [event 1]
- [event 2]
EMOTIONAL_BEATS:
- [beat 1]
"""

        try:
            response = await self.llm_caller(
                prompt=prompt,
                system_prompt="You are a precise story summarizer. Be concise and focus on plot-critical information."
            )

            return self._parse_summary_response(scene_number, response, characters, location)

        except Exception as e:
            logger.warning(f"LLM summary failed for scene {scene_number}: {e}")
            return self._extract_scene_summary_heuristic(scene_number, content, characters, location)

    def _parse_summary_response(
        self,
        scene_number: int,
        response: str,
        characters: List[str],
        location: str
    ) -> SceneSummary:
        """Parse LLM summary response."""
        summary = SceneSummary(
            scene_number=scene_number,
            characters_featured=characters,
            location=location
        )

        # Parse title
        if match := re.search(r'TITLE:\s*(.+?)(?:\n|$)', response):
            summary.title = match.group(1).strip()

        # Parse summary
        if match := re.search(r'SUMMARY:\s*(.+?)(?:KEY_EVENTS|EMOTIONAL|$)', response, re.DOTALL):
            summary.summary = match.group(1).strip()

        # Parse key events
        if match := re.search(r'KEY_EVENTS:\s*(.+?)(?:EMOTIONAL|$)', response, re.DOTALL):
            events_text = match.group(1)
            summary.key_events = [
                e.strip().lstrip('- ')
                for e in events_text.split('\n')
                if e.strip() and e.strip() != '-'
            ]

        # Parse emotional beats
        if match := re.search(r'EMOTIONAL_BEATS?:\s*(.+?)$', response, re.DOTALL):
            beats_text = match.group(1)
            summary.emotional_beats = [
                b.strip().lstrip('- ')
                for b in beats_text.split('\n')
                if b.strip() and b.strip() != '-'
            ]

        summary.token_count = count_tokens_estimate(summary.to_context_string())

        return summary

    def _extract_scene_summary_heuristic(
        self,
        scene_number: int,
        content: str,
        characters: List[str],
        location: str
    ) -> SceneSummary:
        """Extract scene summary without LLM using heuristics."""
        # Extract title from scene header if present
        title = ""
        if match := re.search(r'##\s*Scene\s*\d+:\s*(.+?)(?:\n|$)', content, re.IGNORECASE):
            title = match.group(1).strip()

        # Get first paragraph as summary
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        summary_text = paragraphs[0] if paragraphs else content[:200]

        # Truncate to reasonable length
        if len(summary_text) > 300:
            summary_text = summary_text[:297] + "..."

        # Extract character tags from content
        char_tags = re.findall(r'\[CHAR_([A-Z_]+)\]', content)
        all_chars = list(set(characters + [f"CHAR_{t}" for t in char_tags]))

        return SceneSummary(
            scene_number=scene_number,
            title=title or f"Scene {scene_number}",
            summary=summary_text,
            characters_featured=all_chars[:5],
            location=location,
            token_count=count_tokens_estimate(summary_text)
        )

    async def _generate_act_summary(self, act_number: int, scene_numbers: List[int]) -> ActSummary:
        """Generate summary for an act."""
        scene_summaries = [
            self.scene_summaries[s].to_context_string(SummaryLevel.COMPRESSED)
            for s in scene_numbers
            if s in self.scene_summaries
        ]

        if self.llm_caller:
            prompt = f"""Summarize this act (scenes {scene_numbers[0]}-{scene_numbers[-1]}) in 75 words.

SCENES:
{chr(10).join(scene_summaries)}

Focus on:
1. Major plot progression
2. Character development
3. How this act advances the story arc

SUMMARY:"""

            try:
                response = await self.llm_caller(
                    prompt=prompt,
                    system_prompt="You are a story arc analyst. Summarize act progression concisely."
                )
                summary_text = response.strip()
            except Exception as e:
                logger.warning(f"Act summary generation failed: {e}")
                summary_text = " ".join(
                    self.scene_summaries[s].summary[:50]
                    for s in scene_numbers
                    if s in self.scene_summaries
                )
        else:
            summary_text = " ".join(
                self.scene_summaries[s].summary[:50]
                for s in scene_numbers
                if s in self.scene_summaries
            )

        act_summary = ActSummary(
            act_number=act_number,
            scenes=scene_numbers,
            summary=summary_text
        )

        self.act_summaries[act_number] = act_summary
        return act_summary

    def _update_character_arc(self, char_tag: str, scene_number: int, content: str) -> None:
        """Update character arc tracking."""
        if char_tag not in self.character_arcs:
            # Extract name from tag
            name = char_tag.replace("CHAR_", "").replace("_", " ").title()
            self.character_arcs[char_tag] = CharacterArc(
                tag=char_tag,
                name=name
            )

        arc = self.character_arcs[char_tag]
        arc.appearances.append(scene_number)

        # Simple heuristic: look for character + emotional words
        emotional_words = [
            "realizes", "discovers", "decides", "confronts", "accepts",
            "rejects", "struggles", "overcomes", "fails", "succeeds"
        ]

        content_lower = content.lower()
        char_pattern = char_tag.lower().replace("char_", "")

        for word in emotional_words:
            if char_pattern in content_lower and word in content_lower:
                arc.arc_points.append((scene_number, f"{arc.name} {word}"))
                break

    def get_story_so_far(
        self,
        current_scene: int,
        level: SummaryLevel = SummaryLevel.STANDARD,
        include_character_arcs: bool = True,
        include_threads: bool = True
    ) -> str:
        """
        Get "story so far" context for a scene.

        Provides hierarchical summary of all prior scenes.

        Args:
            current_scene: Current scene number
            level: Detail level for summaries
            include_character_arcs: Include character arc summaries
            include_threads: Include narrative thread tracking

        Returns:
            Formatted context string
        """
        parts = ["=== STORY SO FAR ==="]

        # Determine which scenes need summarization
        prior_scenes = [s for s in sorted(self.scene_summaries.keys()) if s < current_scene]

        if not prior_scenes:
            return "=== STORY SO FAR ===\n(Beginning of story)"

        # Use act summaries for older scenes, detailed for recent
        recent_threshold = max(1, current_scene - 3)

        # Add act summaries for older scenes
        for act_num, act_summary in sorted(self.act_summaries.items()):
            if all(s < recent_threshold for s in act_summary.scenes):
                parts.append(act_summary.to_context_string())

        # Add scene summaries for recent scenes
        parts.append("\n### Recent Scenes:")
        for scene_num in prior_scenes:
            if scene_num >= recent_threshold:
                summary = self.scene_summaries[scene_num]
                parts.append(summary.to_context_string(level))

        # Add character arcs
        if include_character_arcs and self.character_arcs:
            parts.append("\n### Character Arcs:")
            for arc in self.character_arcs.values():
                if arc.appearances and max(arc.appearances) >= recent_threshold - 1:
                    parts.append(arc.to_context_string())

        # Add narrative threads
        if include_threads and self.narrative_threads:
            active_threads = [
                t for t in self.narrative_threads.values()
                if t.current_status == "active"
            ]
            if active_threads:
                parts.append("\n### Active Narrative Threads:")
                for thread in active_threads:
                    parts.append(thread.to_context_string())

        result = "\n".join(parts)

        # Check token budget
        tokens = count_tokens_estimate(result)
        if tokens > self.max_token_budget:
            # Compress by using more minimal summaries
            return self.get_story_so_far(
                current_scene,
                level=SummaryLevel.COMPRESSED if level != SummaryLevel.MINIMAL else SummaryLevel.MINIMAL,
                include_character_arcs=False,
                include_threads=include_threads
            )

        return result

    def get_character_context(self, char_tag: str, current_scene: int) -> str:
        """Get context for a specific character up to current scene."""
        if char_tag not in self.character_arcs:
            return f"[{char_tag}]: No prior appearances"

        arc = self.character_arcs[char_tag]
        prior_appearances = [s for s in arc.appearances if s < current_scene]

        if not prior_appearances:
            return f"[{char_tag}] ({arc.name}): First appearance"

        parts = [f"[{char_tag}] ({arc.name}) Arc:"]
        parts.append(f"  Appeared in scenes: {', '.join(map(str, prior_appearances))}")

        # Recent arc points
        recent_points = [(s, p) for s, p in arc.arc_points if s < current_scene][-3:]
        for scene, point in recent_points:
            parts.append(f"  Scene {scene}: {point}")

        if arc.current_state:
            parts.append(f"  Current state: {arc.current_state}")

        return "\n".join(parts)

    def add_narrative_thread(
        self,
        thread_id: str,
        name: str,
        introduced_scene: int,
        initial_description: str = ""
    ) -> NarrativeThread:
        """Add a new narrative thread to track."""
        thread = NarrativeThread(
            thread_id=thread_id,
            name=name,
            introduced_scene=introduced_scene,
            progression=[(introduced_scene, initial_description)] if initial_description else []
        )
        self.narrative_threads[thread_id] = thread
        return thread

    def update_thread(
        self,
        thread_id: str,
        scene_number: int,
        update: str,
        status: str = None
    ) -> None:
        """Update a narrative thread's progression."""
        if thread_id in self.narrative_threads:
            thread = self.narrative_threads[thread_id]
            thread.progression.append((scene_number, update))
            if status:
                thread.current_status = status

    def get_active_threads(self) -> List[NarrativeThread]:
        """Get all active narrative threads."""
        return [t for t in self.narrative_threads.values() if t.current_status == "active"]

    def get_scene_summary(self, scene_number: int) -> Optional[SceneSummary]:
        """Get summary for a specific scene."""
        return self.scene_summaries.get(scene_number)

    def get_all_summaries(self, level: SummaryLevel = SummaryLevel.STANDARD) -> str:
        """Get all scene summaries as a formatted string."""
        parts = []
        for scene_num in sorted(self.scene_summaries.keys()):
            parts.append(self.scene_summaries[scene_num].to_context_string(level))
        return "\n\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get summarizer statistics."""
        return {
            "scenes_summarized": len(self.scene_summaries),
            "acts_summarized": len(self.act_summaries),
            "character_arcs_tracked": len(self.character_arcs),
            "narrative_threads": len(self.narrative_threads),
            "active_threads": len(self.get_active_threads()),
            "total_tokens": sum(s.token_count for s in self.scene_summaries.values())
        }


# Convenience functions
def create_summarizer(
    llm_caller: Optional[Callable] = None,
    scenes_per_act: int = 3
) -> SceneSummarizer:
    """Create a scene summarizer instance."""
    return SceneSummarizer(llm_caller, scenes_per_act)


async def summarize_script(
    scenes: List[Tuple[int, str]],
    llm_caller: Optional[Callable] = None
) -> SceneSummarizer:
    """
    Summarize an entire script.

    Args:
        scenes: List of (scene_number, content) tuples
        llm_caller: Optional LLM caller

    Returns:
        SceneSummarizer with all summaries
    """
    summarizer = SceneSummarizer(llm_caller)

    for scene_num, content in scenes:
        await summarizer.add_scene(scene_num, content)

    return summarizer
