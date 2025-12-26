"""
Pitch Analyzer - Dynamic Scene Count Calculator

Analyzes story pitches to determine optimal scene count based on:
- Number of characters and their complexity
- Number of locations
- Plot complexity (narrative beats, conflicts, resolutions)
- Genre conventions
- Word count and density of the pitch

This replaces the static scene counts from SIZE_CONFIG with intelligent,
pitch-driven calculations.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from greenlight.core.logging_config import get_logger

logger = get_logger("core.pitch_analyzer")


@dataclass
class PitchMetrics:
    """Metrics extracted from pitch analysis."""
    character_count: int
    location_count: int
    plot_beat_count: int
    conflict_count: int
    relationship_count: int
    time_span_indicator: str  # "moment", "day", "week", "month", "year", "lifetime"
    genre: str
    pitch_word_count: int
    complexity_score: float  # 0.0 to 1.0

    # Calculated scene recommendation
    recommended_scenes: int
    min_scenes: int
    max_scenes: int
    words_per_scene: int
    reasoning: str


# Genre-specific scene density multipliers
GENRE_MULTIPLIERS = {
    "action": 1.2,      # More scenes, faster pacing
    "thriller": 1.15,
    "horror": 1.1,
    "comedy": 1.0,
    "drama": 0.95,      # Fewer, deeper scenes
    "romance": 0.9,
    "epic": 1.3,        # Many scenes for scope
    "mystery": 1.1,
    "sci-fi": 1.05,
    "fantasy": 1.1,
    "slice-of-life": 0.85,
    "default": 1.0
}

# Time span to scene count base
TIME_SPAN_BASE_SCENES = {
    "moment": 3,        # A single moment/event
    "hour": 4,
    "day": 6,
    "week": 10,
    "month": 15,
    "year": 20,
    "lifetime": 30,
    "default": 8
}

# Scene count boundaries
MIN_SCENES = 3
MAX_SCENES = 50
DEFAULT_WORDS_PER_SCENE = 250


class PitchAnalyzer:
    """Analyzes pitches to determine optimal story structure."""

    def __init__(self, llm_manager=None):
        """
        Initialize the pitch analyzer.

        Args:
            llm_manager: Optional LLM manager for advanced analysis.
                        If None, uses heuristic analysis only.
        """
        self.llm_manager = llm_manager

    def analyze(self, pitch_text: str, genre: str = "", existing_tags: List[str] = None) -> PitchMetrics:
        """
        Analyze a pitch and return scene recommendations.

        Args:
            pitch_text: The story pitch text
            genre: Genre of the story
            existing_tags: Pre-extracted tags if available

        Returns:
            PitchMetrics with scene recommendations
        """
        existing_tags = existing_tags or []
        genre = genre.lower().strip() if genre else "default"

        # Extract metrics from pitch
        character_count = self._count_characters(pitch_text, existing_tags)
        location_count = self._count_locations(pitch_text, existing_tags)
        plot_beat_count = self._count_plot_beats(pitch_text)
        conflict_count = self._count_conflicts(pitch_text)
        relationship_count = self._count_relationships(pitch_text, character_count)
        time_span = self._detect_time_span(pitch_text)
        pitch_word_count = len(pitch_text.split())

        # Calculate complexity score
        complexity_score = self._calculate_complexity(
            character_count, location_count, plot_beat_count,
            conflict_count, relationship_count, pitch_word_count
        )

        # Calculate recommended scene count
        recommended, min_scenes, max_scenes, reasoning = self._calculate_scene_count(
            character_count=character_count,
            location_count=location_count,
            plot_beat_count=plot_beat_count,
            conflict_count=conflict_count,
            time_span=time_span,
            complexity_score=complexity_score,
            genre=genre,
            pitch_word_count=pitch_word_count
        )

        # Calculate words per scene based on total target
        words_per_scene = self._calculate_words_per_scene(recommended, complexity_score)

        logger.info(f"Pitch analysis: {character_count} chars, {location_count} locs, "
                   f"{plot_beat_count} beats -> {recommended} scenes recommended")

        return PitchMetrics(
            character_count=character_count,
            location_count=location_count,
            plot_beat_count=plot_beat_count,
            conflict_count=conflict_count,
            relationship_count=relationship_count,
            time_span_indicator=time_span,
            genre=genre,
            pitch_word_count=pitch_word_count,
            complexity_score=complexity_score,
            recommended_scenes=recommended,
            min_scenes=min_scenes,
            max_scenes=max_scenes,
            words_per_scene=words_per_scene,
            reasoning=reasoning
        )

    def _count_characters(self, text: str, tags: List[str]) -> int:
        """Count characters from tags and text analysis."""
        # Count from CHAR_ tags
        char_tags = [t for t in tags if t.startswith("CHAR_")]
        tag_count = len(char_tags)

        # Heuristic: look for character indicators in text
        # Names (capitalized words that appear multiple times)
        words = re.findall(r'\b[A-Z][a-z]+\b', text)
        name_candidates = {}
        for word in words:
            if word not in {"The", "A", "An", "In", "On", "At", "To", "For", "And", "But", "Or", "If", "When", "Where", "Who", "What", "How", "Why"}:
                name_candidates[word] = name_candidates.get(word, 0) + 1

        # Characters mentioned 2+ times are likely actual characters
        text_char_count = sum(1 for count in name_candidates.values() if count >= 2)

        # Character role keywords
        role_keywords = ["protagonist", "antagonist", "hero", "villain", "main character",
                        "supporting", "mentor", "love interest", "sidekick"]
        role_count = sum(1 for kw in role_keywords if kw in text.lower())

        # Use max of tag count or heuristic estimate
        return max(tag_count, text_char_count, role_count, 1)

    def _count_locations(self, text: str, tags: List[str]) -> int:
        """Count locations from tags and text analysis."""
        # Count from LOC_ tags
        loc_tags = [t for t in tags if t.startswith("LOC_")]
        tag_count = len(loc_tags)

        # Heuristic: location indicators
        location_keywords = ["in the", "at the", "inside", "outside", "enters", "arrives at",
                           "walks into", "returns to", "leaves", "room", "house", "street",
                           "building", "palace", "castle", "forest", "city", "village",
                           "office", "apartment", "home", "shop", "store", "market"]

        keyword_count = sum(1 for kw in location_keywords if kw in text.lower())
        estimated_locations = max(1, keyword_count // 3)  # Rough estimate

        return max(tag_count, estimated_locations, 1)

    def _count_plot_beats(self, text: str) -> int:
        """Count plot beats/events in the pitch."""
        # Look for narrative progression indicators
        beat_indicators = [
            # Inciting incidents
            "discovers", "finds out", "learns that", "realizes",
            # Rising action
            "must", "has to", "decides to", "attempts", "tries to",
            "confronts", "challenges", "fights", "battles",
            # Complications
            "but", "however", "unfortunately", "until", "when suddenly",
            "only to find", "complications", "obstacle",
            # Climax indicators
            "finally", "ultimate", "showdown", "confrontation", "climax",
            # Resolution indicators
            "resolves", "overcomes", "succeeds", "fails", "ends",
            # Transition words that indicate new beats
            "meanwhile", "later", "then", "after", "before", "during"
        ]

        text_lower = text.lower()
        beat_count = sum(1 for indicator in beat_indicators if indicator in text_lower)

        # Minimum of 3 beats (beginning, middle, end)
        return max(3, beat_count)

    def _count_conflicts(self, text: str) -> int:
        """Count conflict indicators."""
        conflict_keywords = [
            "conflict", "struggle", "fight", "battle", "war", "versus", "vs",
            "against", "enemy", "rival", "opponent", "obstacle", "challenge",
            "tension", "clash", "dispute", "disagreement", "competition",
            "threat", "danger", "risk", "stakes", "must overcome"
        ]

        text_lower = text.lower()
        return sum(1 for kw in conflict_keywords if kw in text_lower)

    def _count_relationships(self, text: str, character_count: int) -> int:
        """Estimate number of significant relationships."""
        relationship_keywords = [
            "love", "friend", "enemy", "rival", "partner", "sibling",
            "parent", "child", "mentor", "student", "boss", "colleague",
            "husband", "wife", "boyfriend", "girlfriend", "family",
            "betrayal", "trust", "loyalty", "bond"
        ]

        text_lower = text.lower()
        keyword_count = sum(1 for kw in relationship_keywords if kw in text_lower)

        # Also estimate from character count (n characters = up to n*(n-1)/2 relationships)
        max_possible = (character_count * (character_count - 1)) // 2

        return min(keyword_count, max_possible) if max_possible > 0 else keyword_count

    def _detect_time_span(self, text: str) -> str:
        """Detect the time span the story covers."""
        text_lower = text.lower()

        # Check for explicit time indicators
        if any(word in text_lower for word in ["lifetime", "years later", "decades", "generations"]):
            return "lifetime"
        if any(word in text_lower for word in ["year", "months later", "seasons"]):
            return "year"
        if any(word in text_lower for word in ["month", "weeks later"]):
            return "month"
        if any(word in text_lower for word in ["week", "days later", "several days"]):
            return "week"
        if any(word in text_lower for word in ["day", "morning", "evening", "night", "sunset", "sunrise"]):
            return "day"
        if any(word in text_lower for word in ["hour", "minutes"]):
            return "hour"
        if any(word in text_lower for word in ["moment", "instant", "single night", "one evening"]):
            return "moment"

        return "default"

    def _calculate_complexity(
        self,
        characters: int,
        locations: int,
        plot_beats: int,
        conflicts: int,
        relationships: int,
        word_count: int
    ) -> float:
        """Calculate overall complexity score (0.0 to 1.0)."""
        # Normalize each factor
        char_score = min(characters / 10, 1.0)  # 10+ chars = max
        loc_score = min(locations / 8, 1.0)     # 8+ locations = max
        beat_score = min(plot_beats / 15, 1.0)  # 15+ beats = max
        conflict_score = min(conflicts / 5, 1.0) # 5+ conflicts = max
        rel_score = min(relationships / 10, 1.0) # 10+ relationships = max
        density_score = min(word_count / 500, 1.0)  # 500+ words = dense pitch

        # Weighted average
        weights = {
            "characters": 0.2,
            "locations": 0.15,
            "plot_beats": 0.25,
            "conflicts": 0.15,
            "relationships": 0.1,
            "density": 0.15
        }

        complexity = (
            char_score * weights["characters"] +
            loc_score * weights["locations"] +
            beat_score * weights["plot_beats"] +
            conflict_score * weights["conflicts"] +
            rel_score * weights["relationships"] +
            density_score * weights["density"]
        )

        return round(complexity, 2)

    def _calculate_scene_count(
        self,
        character_count: int,
        location_count: int,
        plot_beat_count: int,
        conflict_count: int,
        time_span: str,
        complexity_score: float,
        genre: str,
        pitch_word_count: int
    ) -> Tuple[int, int, int, str]:
        """
        Calculate recommended scene count.

        Returns:
            Tuple of (recommended, min, max, reasoning)
        """
        reasoning_parts = []

        # Base from time span
        base_scenes = TIME_SPAN_BASE_SCENES.get(time_span, TIME_SPAN_BASE_SCENES["default"])
        reasoning_parts.append(f"Time span '{time_span}' suggests base of {base_scenes} scenes")

        # Adjust for character count (each major character needs introduction + development)
        char_adjustment = max(0, (character_count - 2) * 1.5)  # +1.5 scenes per character beyond 2
        if char_adjustment > 0:
            reasoning_parts.append(f"+{char_adjustment:.0f} for {character_count} characters")

        # Adjust for locations (new locations need establishing)
        loc_adjustment = max(0, (location_count - 2) * 0.75)  # +0.75 scenes per location beyond 2
        if loc_adjustment > 0:
            reasoning_parts.append(f"+{loc_adjustment:.0f} for {location_count} locations")

        # Adjust for plot beats (each major beat needs screen time)
        beat_adjustment = max(0, (plot_beat_count - 5) * 0.5)  # +0.5 scenes per beat beyond 5
        if beat_adjustment > 0:
            reasoning_parts.append(f"+{beat_adjustment:.0f} for {plot_beat_count} plot beats")

        # Adjust for conflicts (conflicts need setup + resolution)
        conflict_adjustment = conflict_count * 0.75
        if conflict_adjustment > 0:
            reasoning_parts.append(f"+{conflict_adjustment:.0f} for {conflict_count} conflicts")

        # Calculate raw total
        raw_total = base_scenes + char_adjustment + loc_adjustment + beat_adjustment + conflict_adjustment

        # Apply genre multiplier
        genre_key = genre if genre in GENRE_MULTIPLIERS else "default"
        genre_mult = GENRE_MULTIPLIERS[genre_key]
        after_genre = raw_total * genre_mult
        if genre_mult != 1.0:
            reasoning_parts.append(f"x{genre_mult} for {genre} genre")

        # Apply complexity modifier (high complexity = slightly more scenes)
        complexity_mult = 0.9 + (complexity_score * 0.3)  # Range: 0.9 to 1.2
        final_raw = after_genre * complexity_mult
        reasoning_parts.append(f"Complexity score: {complexity_score:.0%}")

        # Round and clamp
        recommended = int(round(final_raw))
        recommended = max(MIN_SCENES, min(MAX_SCENES, recommended))

        # Calculate min/max range (±25%)
        min_scenes = max(MIN_SCENES, int(recommended * 0.75))
        max_scenes = min(MAX_SCENES, int(recommended * 1.25))

        reasoning = " -> ".join(reasoning_parts) + f" -> {recommended} scenes"

        return recommended, min_scenes, max_scenes, reasoning

    def _calculate_words_per_scene(self, scene_count: int, complexity: float) -> int:
        """Calculate optimal words per scene."""
        # More scenes = slightly fewer words per scene
        # Higher complexity = slightly more words per scene

        if scene_count <= 5:
            base_words = 300  # Short stories: denser scenes
        elif scene_count <= 10:
            base_words = 275
        elif scene_count <= 20:
            base_words = 250
        elif scene_count <= 30:
            base_words = 225
        else:
            base_words = 200  # Many scenes: keep each tighter

        # Adjust for complexity (+/- 20%)
        complexity_adjustment = 1.0 + ((complexity - 0.5) * 0.4)  # 0.8 to 1.2

        return int(base_words * complexity_adjustment)


def analyze_pitch(pitch_text: str, genre: str = "", tags: List[str] = None) -> PitchMetrics:
    """
    Convenience function for quick pitch analysis.

    Args:
        pitch_text: The story pitch
        genre: Optional genre
        tags: Optional pre-extracted tags

    Returns:
        PitchMetrics with recommendations
    """
    analyzer = PitchAnalyzer()
    return analyzer.analyze(pitch_text, genre, tags)
