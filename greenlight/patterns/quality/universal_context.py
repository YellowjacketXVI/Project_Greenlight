"""
Universal Context - Ensures world_config + pitch flow to ALL agents.

This module provides the UniversalContext class that MUST be passed to every
agent in the Writer pipeline, ensuring consistent access to world configuration
and pitch information.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import json

from greenlight.core.logging_config import get_logger

logger = get_logger("patterns.quality.universal_context")


@dataclass
class SceneContext:
    """Context for a specific scene, derived from UniversalContext."""
    scene_number: int
    scene_content: str
    scene_purpose: str
    characters: List[Dict[str, Any]]
    location: Optional[Dict[str, Any]]
    props: List[Dict[str, Any]]
    entry_state: Dict[str, str] = field(default_factory=dict)
    exit_state: Dict[str, str] = field(default_factory=dict)


@dataclass
class UniversalContext:
    """
    Universal context that MUST be passed to every agent in the Writer pipeline.
    
    Contains:
    - pitch: The original story pitch text
    - world_config: Complete world configuration (characters, locations, props, etc.)
    
    Provides derived summaries for efficient prompt construction.
    """
    # Required inputs
    pitch: str
    world_config: Dict[str, Any]
    
    # Optional: Full script for holistic analysis
    full_script: str = ""
    
    # Derived context (computed on initialization)
    character_summary: str = field(default="", init=False)
    location_summary: str = field(default="", init=False)
    prop_summary: str = field(default="", init=False)
    theme_summary: str = field(default="", init=False)
    style_context: str = field(default="", init=False)
    
    def __post_init__(self):
        """Compute derived context on initialization."""
        self.character_summary = self._build_character_summary()
        self.location_summary = self._build_location_summary()
        self.prop_summary = self._build_prop_summary()
        self.theme_summary = self._build_theme_summary()
        self.style_context = self._build_style_context()
        logger.debug(f"UniversalContext initialized with {len(self.get_all_tags())} tags")
    
    def _build_character_summary(self) -> str:
        """Build summary of all characters."""
        chars = self.world_config.get('characters', [])
        if not chars:
            return "No characters defined."
        
        lines = []
        for c in chars:
            tag = c.get('tag', 'UNKNOWN')
            name = c.get('name', '')
            role = c.get('role', '')
            want = c.get('want', '')
            flaw = c.get('flaw', '')
            appearance = c.get('visual_appearance', c.get('appearance', ''))
            
            line = f"[{tag}] {name}: {role}"
            if want:
                line += f" - Wants: {want}"
            if flaw:
                line += f" - Flaw: {flaw}"
            if appearance:
                line += f"\n    Appearance: {appearance[:100]}..."
            lines.append(line)
        
        return "\n".join(lines)
    
    def _build_location_summary(self) -> str:
        """Build summary of all locations."""
        locs = self.world_config.get('locations', [])
        if not locs:
            return "No locations defined."
        
        lines = []
        for loc in locs:
            tag = loc.get('tag', 'UNKNOWN')
            name = loc.get('name', '')
            desc = loc.get('description', '')[:80]
            lines.append(f"[{tag}] {name}: {desc}...")
        
        return "\n".join(lines)
    
    def _build_prop_summary(self) -> str:
        """Build summary of all props."""
        props = self.world_config.get('props', [])
        if not props:
            return "No props defined."
        
        lines = []
        for p in props:
            tag = p.get('tag', 'UNKNOWN')
            name = p.get('name', '')
            significance = p.get('significance', '')[:60]
            lines.append(f"[{tag}] {name}: {significance}...")
        
        return "\n".join(lines)
    
    def _build_theme_summary(self) -> str:
        """Build summary of themes and world rules."""
        themes = self.world_config.get('themes', '')
        rules = self.world_config.get('world_rules', '')
        return f"Themes: {themes}\nWorld Rules: {rules}"
    
    def _build_style_context(self) -> str:
        """Build visual style context."""
        return f"""Visual Style: {self.world_config.get('visual_style', 'live_action')}
Style Notes: {self.world_config.get('style_notes', '')}
Lighting: {self.world_config.get('lighting', '')}
Vibe: {self.world_config.get('vibe', '')}"""
    
    def get_all_tags(self) -> List[str]:
        """Get all defined tags from world_config."""
        return self.world_config.get('all_tags', [])
    
    def get_character_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get character data by tag."""
        for c in self.world_config.get('characters', []):
            if c.get('tag') == tag:
                return c
        return None
    
    def get_location_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get location data by tag."""
        for loc in self.world_config.get('locations', []):
            if loc.get('tag') == tag:
                return loc
        return None
    
    def get_prop_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get prop data by tag."""
        for p in self.world_config.get('props', []):
            if p.get('tag') == tag:
                return p
        return None

    def get_scene_context(
        self,
        scene_number: int,
        scene_content: str,
        scene_purpose: str,
        character_tags: List[str],
        location_tag: str,
        prop_tags: List[str],
        entry_state: Dict[str, str] = None,
        exit_state: Dict[str, str] = None
    ) -> SceneContext:
        """
        Create a scene-specific context with relevant world_config data.

        Args:
            scene_number: Scene number
            scene_content: The scene text content
            scene_purpose: What the scene accomplishes
            character_tags: Tags of characters in the scene
            location_tag: Tag of the scene location
            prop_tags: Tags of props used in the scene
            entry_state: Character states entering the scene
            exit_state: Character states exiting the scene

        Returns:
            SceneContext with filtered world_config data
        """
        # Filter characters to those in scene
        scene_chars = [
            c for c in self.world_config.get('characters', [])
            if c.get('tag') in character_tags
        ]

        # Get location
        scene_loc = self.get_location_by_tag(location_tag)

        # Filter props to those in scene
        scene_props = [
            p for p in self.world_config.get('props', [])
            if p.get('tag') in prop_tags
        ]

        return SceneContext(
            scene_number=scene_number,
            scene_content=scene_content,
            scene_purpose=scene_purpose,
            characters=scene_chars,
            location=scene_loc,
            props=scene_props,
            entry_state=entry_state or {},
            exit_state=exit_state or {}
        )

    def for_prompt(self, include_full_config: bool = False, include_script: bool = False) -> str:
        """
        Format universal context for inclusion in LLM prompts.

        Args:
            include_full_config: Include full JSON world_config
            include_script: Include full script text

        Returns:
            Formatted context string for prompts
        """
        base = f"""=== UNIVERSAL CONTEXT ===

PITCH:
{self.pitch}

TITLE: {self.world_config.get('title', '')}
LOGLINE: {self.world_config.get('logline', '')}
THEMES: {self.world_config.get('themes', '')}
WORLD RULES: {self.world_config.get('world_rules', '')}

{self.style_context}

CHARACTERS:
{self.character_summary}

LOCATIONS:
{self.location_summary}

PROPS:
{self.prop_summary}
"""
        if include_script and self.full_script:
            base += f"\n\n=== FULL SCRIPT ===\n{self.full_script}\n"

        if include_full_config:
            base += f"\n\n=== FULL WORLD CONFIG ===\n{json.dumps(self.world_config, indent=2)}\n"

        return base

    def for_scene_prompt(self, scene_context: SceneContext) -> str:
        """
        Format context for a specific scene prompt.

        Args:
            scene_context: The scene-specific context

        Returns:
            Formatted context string for scene-level prompts
        """
        return f"""=== SCENE {scene_context.scene_number} CONTEXT ===

SCENE PURPOSE: {scene_context.scene_purpose}

SCENE CONTENT:
{scene_context.scene_content}

CHARACTERS IN SCENE:
{json.dumps(scene_context.characters, indent=2)}

LOCATION:
{json.dumps(scene_context.location, indent=2) if scene_context.location else 'Unknown'}

PROPS IN SCENE:
{json.dumps(scene_context.props, indent=2)}

ENTRY STATE: {json.dumps(scene_context.entry_state)}
EXIT STATE: {json.dumps(scene_context.exit_state)}

=== WORLD CONTEXT ===
{self.style_context}
Themes: {self.world_config.get('themes', '')}
"""

