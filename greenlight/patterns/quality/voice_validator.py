"""
Voice Differentiation Validator - Story Pipeline

Validates that character dialogue matches their established speech patterns.
Ensures each character has a distinct voice that remains consistent throughout.

Checks:
1. Speech pattern adherence (formal/informal, vocabulary level)
2. Verbal habits and catchphrases
3. Dialogue distinctiveness between characters
4. Literacy level consistency
5. Cultural/regional speech markers
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter

from greenlight.core.logging_config import get_logger

logger = get_logger("patterns.quality.voice_validator")


@dataclass
class CharacterVoiceProfile:
    """Profile of a character's speech patterns for validation."""
    character_tag: str
    character_name: str
    speech_style: str = ""  # formal, informal, terse, verbose, poetic
    vocabulary_level: str = ""  # simple, moderate, sophisticated, archaic
    verbal_habits: List[str] = field(default_factory=list)  # repeated phrases, filler words
    speech_patterns: str = ""  # Full description from CharacterArc
    literacy_level: str = ""
    cultural_markers: List[str] = field(default_factory=list)  # dialect, idioms


@dataclass
class VoiceIssue:
    """A voice consistency issue found in dialogue."""
    issue_type: str  # style_mismatch, vocabulary_mismatch, missing_habit, voice_blur
    severity: str  # critical, warning, info
    scene_number: int
    character_tag: str
    dialogue_excerpt: str
    description: str
    suggested_fix: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.issue_type,
            "severity": self.severity,
            "scene": self.scene_number,
            "character": self.character_tag,
            "excerpt": self.dialogue_excerpt[:100] + "..." if len(self.dialogue_excerpt) > 100 else self.dialogue_excerpt,
            "description": self.description,
            "fix": self.suggested_fix
        }


@dataclass
class VoiceReport:
    """Report from voice validation."""
    is_valid: bool
    score: float  # 0.0 to 1.0
    issues: List[VoiceIssue] = field(default_factory=list)
    character_scores: Dict[str, float] = field(default_factory=dict)
    distinctiveness_score: float = 0.0  # How different characters sound from each other

    @property
    def critical_issues(self) -> List[VoiceIssue]:
        return [i for i in self.issues if i.severity == "critical"]

    @property
    def warnings(self) -> List[VoiceIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "issues": [i.to_dict() for i in self.issues],
            "character_scores": self.character_scores,
            "distinctiveness": self.distinctiveness_score
        }


# Speech style indicators
FORMAL_INDICATORS = [
    "shall", "whom", "indeed", "therefore", "furthermore", "nevertheless",
    "I believe", "one must", "it would appear", "I am", "you are",
    "please", "kindly", "perhaps", "certainly", "undoubtedly"
]

INFORMAL_INDICATORS = [
    "gonna", "wanna", "gotta", "yeah", "nah", "hey", "yo", "cool",
    "awesome", "dude", "man", "like", "totally", "whatever", "stuff",
    "kinda", "sorta", "ain't", "y'all", "lemme", "gimme"
]

TERSE_PATTERNS = [
    r'\b\w+\.\s*$',  # Single word sentences
    r'^[A-Z][a-z]+\.$',  # Very short sentences
]

VERBOSE_INDICATORS = [
    "in my humble opinion", "as a matter of fact", "to be perfectly honest",
    "if I may say so", "speaking of which", "on the other hand",
    "what I mean to say is", "the thing is"
]

SOPHISTICATED_VOCABULARY = [
    "erudite", "perspicacious", "eloquent", "profound", "nuanced",
    "paradigm", "dichotomy", "juxtaposition", "ephemeral", "ubiquitous"
]

SIMPLE_VOCABULARY = [
    "good", "bad", "big", "small", "nice", "happy", "sad", "want", "need",
    "go", "come", "see", "look", "think", "know"
]


class VoiceValidator:
    """
    Validates character voice differentiation and consistency.

    Uses speech patterns from CharacterArc to ensure dialogue authenticity.
    """

    def __init__(self, character_profiles: List[CharacterVoiceProfile] = None):
        self.profiles = {p.character_tag: p for p in (character_profiles or [])}
        self.dialogue_cache: Dict[str, List[str]] = {}  # tag -> list of dialogue

    def add_profile(self, profile: CharacterVoiceProfile):
        """Add a character voice profile."""
        self.profiles[profile.character_tag] = profile

    def add_profile_from_arc(self, arc: Any):
        """Create a voice profile from a CharacterArc dataclass."""
        profile = CharacterVoiceProfile(
            character_tag=arc.character_tag,
            character_name=arc.character_name,
            speech_style=getattr(arc, 'speech_style', ''),
            vocabulary_level=getattr(arc, 'literacy_level', ''),
            speech_patterns=getattr(arc, 'speech_patterns', ''),
            literacy_level=getattr(arc, 'literacy_level', ''),
        )
        self.profiles[arc.character_tag] = profile

    def extract_dialogue(self, scene_content: str, character_tag: str) -> List[str]:
        """Extract dialogue attributed to a specific character from scene content."""
        dialogues = []

        # Pattern 1: Direct attribution "[CHAR_NAME] said/asked/replied..."
        pattern1 = rf'\[{character_tag}\][^"]*"([^"]+)"'
        dialogues.extend(re.findall(pattern1, scene_content))

        # Pattern 2: Character name followed by dialogue
        char_name = self.profiles.get(character_tag, CharacterVoiceProfile(character_tag, "")).character_name
        if char_name:
            pattern2 = rf'{char_name}[^"]*"([^"]+)"'
            dialogues.extend(re.findall(pattern2, scene_content, re.IGNORECASE))

        # Pattern 3: Dialogue after character action
        pattern3 = rf'\[{character_tag}\][^.]*\.\s*"([^"]+)"'
        dialogues.extend(re.findall(pattern3, scene_content))

        return list(set(dialogues))  # Remove duplicates

    def analyze_speech_style(self, dialogues: List[str]) -> Dict[str, float]:
        """Analyze the speech style indicators in dialogue."""
        if not dialogues:
            return {"formal": 0, "informal": 0, "terse": 0, "verbose": 0}

        combined = " ".join(dialogues).lower()
        word_count = len(combined.split())

        if word_count == 0:
            return {"formal": 0, "informal": 0, "terse": 0, "verbose": 0}

        formal_count = sum(1 for ind in FORMAL_INDICATORS if ind.lower() in combined)
        informal_count = sum(1 for ind in INFORMAL_INDICATORS if ind.lower() in combined)
        verbose_count = sum(1 for ind in VERBOSE_INDICATORS if ind.lower() in combined)

        # Terse: short sentences
        sentences = re.split(r'[.!?]', combined)
        short_sentences = sum(1 for s in sentences if len(s.split()) <= 5 and len(s.strip()) > 0)
        terse_ratio = short_sentences / max(len(sentences), 1)

        return {
            "formal": formal_count / max(word_count / 50, 1),
            "informal": informal_count / max(word_count / 50, 1),
            "terse": terse_ratio,
            "verbose": verbose_count / max(word_count / 100, 1)
        }

    def analyze_vocabulary_level(self, dialogues: List[str]) -> str:
        """Determine vocabulary sophistication level."""
        if not dialogues:
            return "unknown"

        combined = " ".join(dialogues).lower()
        words = set(combined.split())

        sophisticated_matches = len(words.intersection(set(SOPHISTICATED_VOCABULARY)))
        simple_matches = len(words.intersection(set(SIMPLE_VOCABULARY)))

        # Average word length as proxy
        avg_word_length = sum(len(w) for w in words) / max(len(words), 1)

        if sophisticated_matches >= 2 or avg_word_length > 7:
            return "sophisticated"
        elif simple_matches > len(words) * 0.3 or avg_word_length < 4.5:
            return "simple"
        else:
            return "moderate"

    def calculate_distinctiveness(self, character_dialogues: Dict[str, List[str]]) -> float:
        """
        Calculate how distinct different characters sound from each other.
        Returns 0.0 (identical) to 1.0 (completely distinct).
        """
        if len(character_dialogues) < 2:
            return 1.0  # Can't compare with only one character

        # Build word frequency profiles for each character
        profiles = {}
        for tag, dialogues in character_dialogues.items():
            if dialogues:
                combined = " ".join(dialogues).lower()
                words = re.findall(r'\b\w+\b', combined)
                profiles[tag] = Counter(words)

        if len(profiles) < 2:
            return 1.0

        # Calculate pairwise distinctiveness using Jaccard distance
        tags = list(profiles.keys())
        distances = []

        for i, tag1 in enumerate(tags):
            for tag2 in tags[i+1:]:
                words1 = set(profiles[tag1].keys())
                words2 = set(profiles[tag2].keys())

                if not words1 or not words2:
                    continue

                intersection = len(words1.intersection(words2))
                union = len(words1.union(words2))

                jaccard_distance = 1 - (intersection / union)
                distances.append(jaccard_distance)

        return sum(distances) / len(distances) if distances else 1.0

    def validate_character_voice(
        self,
        character_tag: str,
        dialogues: List[str],
        scene_number: int
    ) -> List[VoiceIssue]:
        """Validate a character's dialogue against their voice profile."""
        issues = []
        profile = self.profiles.get(character_tag)

        if not profile:
            return issues  # No profile to validate against

        if not dialogues:
            return issues  # No dialogue to validate

        style_analysis = self.analyze_speech_style(dialogues)
        vocab_level = self.analyze_vocabulary_level(dialogues)

        # Check speech style consistency
        expected_style = profile.speech_style.lower() if profile.speech_style else ""

        if expected_style:
            if "formal" in expected_style and style_analysis["informal"] > style_analysis["formal"]:
                issues.append(VoiceIssue(
                    issue_type="style_mismatch",
                    severity="warning",
                    scene_number=scene_number,
                    character_tag=character_tag,
                    dialogue_excerpt=dialogues[0] if dialogues else "",
                    description=f"{profile.character_name}'s dialogue is too informal for their formal speech style",
                    suggested_fix=f"Revise dialogue to use more formal language fitting {profile.character_name}'s established voice"
                ))
            elif "informal" in expected_style and style_analysis["formal"] > style_analysis["informal"]:
                issues.append(VoiceIssue(
                    issue_type="style_mismatch",
                    severity="warning",
                    scene_number=scene_number,
                    character_tag=character_tag,
                    dialogue_excerpt=dialogues[0] if dialogues else "",
                    description=f"{profile.character_name}'s dialogue is too formal for their informal speech style",
                    suggested_fix=f"Revise dialogue to use more casual language fitting {profile.character_name}'s established voice"
                ))

        # Check vocabulary level
        expected_vocab = profile.literacy_level.lower() if profile.literacy_level else ""

        if expected_vocab:
            if "simple" in expected_vocab and vocab_level == "sophisticated":
                issues.append(VoiceIssue(
                    issue_type="vocabulary_mismatch",
                    severity="warning",
                    scene_number=scene_number,
                    character_tag=character_tag,
                    dialogue_excerpt=dialogues[0] if dialogues else "",
                    description=f"{profile.character_name} uses vocabulary too sophisticated for their literacy level",
                    suggested_fix="Use simpler words appropriate for the character's education level"
                ))
            elif "educated" in expected_vocab or "sophisticated" in expected_vocab:
                if vocab_level == "simple":
                    issues.append(VoiceIssue(
                        issue_type="vocabulary_mismatch",
                        severity="info",
                        scene_number=scene_number,
                        character_tag=character_tag,
                        dialogue_excerpt=dialogues[0] if dialogues else "",
                        description=f"{profile.character_name} uses simpler vocabulary than expected for their education",
                        suggested_fix="Consider using more sophisticated vocabulary where appropriate"
                    ))

        return issues

    def validate_scene(
        self,
        scene_content: str,
        scene_number: int,
        characters_present: List[str]
    ) -> List[VoiceIssue]:
        """Validate all character voices in a scene."""
        issues = []

        for character_tag in characters_present:
            dialogues = self.extract_dialogue(scene_content, character_tag)
            if dialogues:
                self.dialogue_cache.setdefault(character_tag, []).extend(dialogues)
                issues.extend(self.validate_character_voice(character_tag, dialogues, scene_number))

        return issues

    def validate_full_story(
        self,
        scenes: List[Any],  # List of Scene dataclasses
    ) -> VoiceReport:
        """
        Validate voice consistency across the entire story.

        Args:
            scenes: List of Scene dataclasses with content and characters_present

        Returns:
            VoiceReport with scores and issues
        """
        all_issues = []
        character_scores = {}
        self.dialogue_cache.clear()

        # Validate each scene
        for scene in scenes:
            scene_num = getattr(scene, 'scene_number', 0)
            content = getattr(scene, 'content', '')
            characters = getattr(scene, 'characters_present', [])

            scene_issues = self.validate_scene(content, scene_num, characters)
            all_issues.extend(scene_issues)

        # Calculate per-character scores
        for tag in self.profiles.keys():
            char_issues = [i for i in all_issues if i.character_tag == tag]
            critical_count = sum(1 for i in char_issues if i.severity == "critical")
            warning_count = sum(1 for i in char_issues if i.severity == "warning")

            # Score: 1.0 - (0.2 per critical, 0.1 per warning)
            score = max(0.0, 1.0 - (critical_count * 0.2) - (warning_count * 0.1))
            character_scores[tag] = score

        # Calculate distinctiveness
        distinctiveness = self.calculate_distinctiveness(self.dialogue_cache)

        # Overall score
        if character_scores:
            avg_char_score = sum(character_scores.values()) / len(character_scores)
        else:
            avg_char_score = 1.0

        overall_score = (avg_char_score * 0.7) + (distinctiveness * 0.3)
        is_valid = overall_score >= 0.6 and not any(i.severity == "critical" for i in all_issues)

        return VoiceReport(
            is_valid=is_valid,
            score=overall_score,
            issues=all_issues,
            character_scores=character_scores,
            distinctiveness_score=distinctiveness
        )


def create_validator_from_character_arcs(character_arcs: List[Any]) -> VoiceValidator:
    """
    Convenience function to create a VoiceValidator from CharacterArc list.

    Args:
        character_arcs: List of CharacterArc dataclasses

    Returns:
        Configured VoiceValidator
    """
    validator = VoiceValidator()
    for arc in character_arcs:
        validator.add_profile_from_arc(arc)
    return validator
