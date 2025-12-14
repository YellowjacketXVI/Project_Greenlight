"""
Greenlight Context Compiler

Compiles minimal context packets for each agent task in Story Pipeline v3.0.
Reduces token usage by 85-90% through intelligent compression and caching.

Key features:
- story_seed: 50-word compressed pitch
- character_cards: 30-50 words per character
- location_cards: 20-30 words per location
- Cached on initialization for reuse across agents
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

from greenlight.core.logging_config import get_logger
from greenlight.utils.unicode_utils import count_tokens_estimate

logger = get_logger("context.compiler")


# Word limits for compressed context
STORY_SEED_WORD_LIMIT = 50
CHARACTER_CARD_WORD_LIMIT = 40
LOCATION_CARD_WORD_LIMIT = 30
PROP_CARD_WORD_LIMIT = 20


def _truncate_to_words(text: str, max_words: int) -> str:
    """Truncate text to maximum word count."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return ' '.join(words[:max_words]) + "..."


def _extract_core_trait(text: str, max_words: int = 10) -> str:
    """Extract the core trait from a longer description."""
    # Take first sentence or truncate
    sentences = text.split('.')
    if sentences:
        first = sentences[0].strip()
        return _truncate_to_words(first, max_words)
    return _truncate_to_words(text, max_words)


@dataclass
class ContextCompiler:
    """
    Compiles minimal context packets for each agent task.
    
    Caches compressed versions on initialization for efficient reuse.
    Target: ~250 words per agent call (down from 1500+).
    """
    
    # Source data
    world_config: Dict[str, Any] = field(default_factory=dict)
    pitch: str = ""
    
    # Pre-compiled (cached on init)
    story_seed: str = field(default="", init=False)
    character_cards: Dict[str, str] = field(default_factory=dict, init=False)
    location_cards: Dict[str, str] = field(default_factory=dict, init=False)
    prop_cards: Dict[str, str] = field(default_factory=dict, init=False)
    
    # Metadata
    title: str = field(default="", init=False)
    logline: str = field(default="", init=False)
    themes: str = field(default="", init=False)
    
    def __post_init__(self):
        """Compile all context on initialization."""
        if self.world_config or self.pitch:
            self._compile_all()
    
    def _compile_all(self):
        """Compile all context components."""
        self._compile_story_seed()
        self._compile_character_cards()
        self._compile_location_cards()
        self._compile_prop_cards()
        self._extract_metadata()
        
        logger.info(
            f"ContextCompiler initialized: "
            f"seed={len(self.story_seed.split())} words, "
            f"chars={len(self.character_cards)}, "
            f"locs={len(self.location_cards)}, "
            f"props={len(self.prop_cards)}"
        )
    
    def _extract_metadata(self):
        """Extract title, logline, themes from world_config."""
        self.title = self.world_config.get('title', '')
        self.logline = self.world_config.get('logline', '')
        self.themes = self.world_config.get('themes', '')
    
    def _compile_story_seed(self):
        """
        Compile story seed from pitch + world_config.
        Target: 50 words max.
        """
        # Build seed from key elements
        title = self.world_config.get('title', '')
        logline = self.world_config.get('logline', '')
        themes = self.world_config.get('themes', '')
        
        # If we have structured data, use it
        if logline:
            seed_parts = []
            if title:
                seed_parts.append(f"'{title}':")
            seed_parts.append(logline)
            if themes:
                seed_parts.append(f"Themes: {themes}")
            raw_seed = ' '.join(seed_parts)
        else:
            # Fall back to pitch
            raw_seed = self.pitch
        
        self.story_seed = _truncate_to_words(raw_seed, STORY_SEED_WORD_LIMIT)
    
    def _compile_character_cards(self):
        """
        Compile character cards from world_config.
        Target: 30-50 words per character.
        """
        characters = self.world_config.get('characters', [])
        
        for char in characters:
            tag = char.get('tag', '')
            if not tag:
                continue
            
            # Build compressed card
            name = char.get('name', tag.replace('CHAR_', ''))
            role = char.get('role', '')
            
            # Core elements only
            card_parts = [f"[{tag}] {name}"]
            if role:
                card_parts.append(f"- {role}")
            
            # Add key trait if available
            backstory = char.get('backstory', '')
            if backstory:
                core_trait = _extract_core_trait(backstory, 15)
                card_parts.append(f"- {core_trait}")
            
            # Add want/need if available
            want = char.get('want', '')
            need = char.get('need', '')
            if want:
                card_parts.append(f"Wants: {_truncate_to_words(want, 8)}")
            if need:
                card_parts.append(f"Needs: {_truncate_to_words(need, 8)}")
            
            card = ' '.join(card_parts)
            self.character_cards[tag] = _truncate_to_words(card, CHARACTER_CARD_WORD_LIMIT)

    def _compile_location_cards(self):
        """
        Compile location cards from world_config.
        Target: 20-30 words per location.
        """
        locations = self.world_config.get('locations', [])

        for loc in locations:
            tag = loc.get('tag', '')
            if not tag:
                continue

            name = loc.get('name', tag.replace('LOC_', ''))
            description = loc.get('description', '')
            atmosphere = loc.get('atmosphere', '')

            card_parts = [f"[{tag}] {name}"]
            if description:
                card_parts.append(f"- {_extract_core_trait(description, 12)}")
            if atmosphere:
                card_parts.append(f"Atmosphere: {_truncate_to_words(atmosphere, 6)}")

            card = ' '.join(card_parts)
            self.location_cards[tag] = _truncate_to_words(card, LOCATION_CARD_WORD_LIMIT)

    def _compile_prop_cards(self):
        """
        Compile prop cards from world_config.
        Target: 15-20 words per prop.
        """
        props = self.world_config.get('props', [])

        for prop in props:
            tag = prop.get('tag', '')
            if not tag:
                continue

            name = prop.get('name', tag.replace('PROP_', ''))
            significance = prop.get('significance', '')

            card_parts = [f"[{tag}] {name}"]
            if significance:
                card_parts.append(f"- {_extract_core_trait(significance, 10)}")

            card = ' '.join(card_parts)
            self.prop_cards[tag] = _truncate_to_words(card, PROP_CARD_WORD_LIMIT)

    # =========================================================================
    # Context Packet Builders
    # =========================================================================

    def get_story_seed(self) -> str:
        """Get the compiled story seed (~50 words)."""
        return self.story_seed

    def get_character_card(self, tag: str) -> str:
        """Get a single character card by tag."""
        return self.character_cards.get(tag, "")

    def get_location_card(self, tag: str) -> str:
        """Get a single location card by tag."""
        return self.location_cards.get(tag, "")

    def get_all_character_cards(self) -> str:
        """Get all character cards concatenated."""
        return '\n'.join(self.character_cards.values())

    def get_all_location_cards(self) -> str:
        """Get all location cards concatenated."""
        return '\n'.join(self.location_cards.values())

    def get_relevant_cards(
        self,
        character_tags: List[str] = None,
        location_tag: str = None,
        prop_tags: List[str] = None
    ) -> str:
        """
        Get only the cards relevant to a specific scene.

        Args:
            character_tags: Tags of characters in the scene
            location_tag: Tag of the scene location
            prop_tags: Tags of props in the scene

        Returns:
            Concatenated relevant cards
        """
        parts = []

        if character_tags:
            char_cards = [self.character_cards.get(t, "") for t in character_tags]
            char_cards = [c for c in char_cards if c]
            if char_cards:
                parts.append("CHARACTERS:\n" + '\n'.join(char_cards))

        if location_tag:
            loc_card = self.location_cards.get(location_tag, "")
            if loc_card:
                parts.append(f"LOCATION:\n{loc_card}")

        if prop_tags:
            prop_cards = [self.prop_cards.get(t, "") for t in prop_tags]
            prop_cards = [c for c in prop_cards if c]
            if prop_cards:
                parts.append("PROPS:\n" + '\n'.join(prop_cards))

        return '\n\n'.join(parts)

    def estimate_tokens(self) -> Dict[str, int]:
        """Estimate token counts for all compiled context."""
        return {
            "story_seed": count_tokens_estimate(self.story_seed),
            "character_cards": count_tokens_estimate(self.get_all_character_cards()),
            "location_cards": count_tokens_estimate(self.get_all_location_cards()),
            "total": count_tokens_estimate(
                self.story_seed +
                self.get_all_character_cards() +
                self.get_all_location_cards()
            )
        }

    @classmethod
    def from_project(cls, project_path: Path) -> "ContextCompiler":
        """
        Create a ContextCompiler from a project directory.

        Args:
            project_path: Path to the project root

        Returns:
            Initialized ContextCompiler
        """
        world_config = {}
        pitch = ""

        # Load world_config.json
        config_path = project_path / "world_bible" / "world_config.json"
        if config_path.exists():
            try:
                world_config = json.loads(config_path.read_text(encoding='utf-8'))
            except Exception as e:
                logger.warning(f"Failed to load world_config: {e}")

        # Load pitch.md
        pitch_path = project_path / "world_bible" / "pitch.md"
        if pitch_path.exists():
            try:
                pitch = pitch_path.read_text(encoding='utf-8')
            except Exception as e:
                logger.warning(f"Failed to load pitch: {e}")

        return cls(world_config=world_config, pitch=pitch)

