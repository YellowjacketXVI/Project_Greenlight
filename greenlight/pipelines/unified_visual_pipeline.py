"""
Unified Visual Script Pipeline - Single-Pass Story-to-Visual Generation

This pipeline consolidates the Story Pipeline and Directing Pipeline into a single
coherent flow that generates prose WITH inline frame markers, then injects prompts.

## Key Innovation: Inline Frame Markers

Instead of two separate passes (write script → direct frames), the writer
generates scenes with frame boundaries already marked:

```markdown
## Scene 1: Coffee Shop
[FRAME: wide, establishing] Alice enters the coffee shop...
[FRAME: medium, alice] She spots her ex at the counter...
[FRAME: close-up, hands] Her hands tremble as she grips her bag...
```

## Benefits:
1. Writer thinks visually - frame pacing baked into narrative rhythm
2. Lighter prompt injection pass - just adds generation prompts, no structural analysis
3. Better healing granularity - heal prompts without touching narrative structure
4. Single conversation context - Claude Opus maintains full context for coherence

## Conversation Context Storage

Uses a persistent conversation with Claude Opus for:
- Full story context maintained across all operations
- Coherent healing that references earlier context
- Atomic editing of specific frames with surrounding prose as context

## Visual World Config Optimization

The full world bible contains rich narrative data (psychology, speech patterns,
decision heuristics, etc.) that is unnecessary for image generation. This pipeline
extracts and optimizes only the visual-relevant fields:

KEPT for visual prompts:
- visual_appearance (physical description)
- costume (clothing)
- age, ethnicity (demographic markers)
- location descriptions (environment visuals)
- prop appearances

REMOVED (not needed for image gen):
- internal_voice, speech patterns, decision_making
- emotional_tells, relationships, arc
- vocal_description (TTS-only)
- world_context narrative details

This reduces prompt token usage by ~70% while maintaining visual fidelity.

## Architecture

Phase 1: World Config Loading + Visual Optimization
Phase 2: Scene Generation with Inline Frame Markers
Phase 3: Parallel Prompt Injection per Frame
Phase 4: Validation + Surgical Healing
"""

import asyncio
import re
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import LLMFunction
from greenlight.llm.api_clients import AnthropicClient, TextResponse
from greenlight.pipelines.base_pipeline import BasePipeline, PipelineStep, PipelineResult

logger = get_logger("pipelines.unified_visual")


# =============================================================================
# VISUAL WORLD CONFIG - Optimized for Image Generation
# =============================================================================

@dataclass
class VisualCharacter:
    """
    Visual-only character profile optimized for image generation.

    Contains ONLY the fields needed to render a character visually.
    Strips narrative/behavioral data that doesn't affect appearance.
    """
    tag: str
    name: str
    role: str  # protagonist, antagonist, supporting (affects framing priority)

    # Core visual fields (KEPT)
    age: str = ""  # "early 20s", "mid 40s" - affects rendering
    ethnicity: str = ""  # Affects physical features
    appearance: str = ""  # Physical description: height, build, hair, eyes, skin, features
    costume: str = ""  # Default clothing with colors, materials, details

    # Condensed from full profile
    distinguishing_features: str = ""  # Scars, tattoos, unique identifiers
    body_language_hint: str = ""  # One-line posture/movement note (from physicality)

    @classmethod
    def from_full_profile(cls, profile: Dict[str, Any]) -> 'VisualCharacter':
        """
        Extract visual-only data from a full CharacterProfile.

        Discards: internal_voice, speech, vocal_description, decision_making,
                  emotional_baseline, emotional_tells, relationships, arc, world_context
        """
        # Handle both dict and dataclass inputs
        if hasattr(profile, '__dict__'):
            profile = profile.__dict__

        # Extract appearance - might be in different locations
        appearance = (
            profile.get('visual_appearance') or
            profile.get('appearance') or
            profile.get('description', '')
        )

        # Extract body language hint from physicality if available
        physicality = profile.get('physicality', {})
        if isinstance(physicality, dict):
            body_hint = physicality.get('baseline_posture', '') or physicality.get('gait', '')
        else:
            body_hint = ""

        return cls(
            tag=profile.get('tag', ''),
            name=profile.get('name', ''),
            role=profile.get('role', 'supporting'),
            age=profile.get('age', ''),
            ethnicity=profile.get('ethnicity', ''),
            appearance=appearance,
            costume=profile.get('costume', ''),
            distinguishing_features=profile.get('distinguishing_features', ''),
            body_language_hint=body_hint[:100] if body_hint else ""  # Truncate
        )

    def to_prompt_block(self) -> str:
        """Generate a concise prompt block for this character."""
        parts = [f"[{self.tag}] {self.name}"]

        if self.age or self.ethnicity:
            demo = ", ".join(filter(None, [self.age, self.ethnicity]))
            parts.append(demo)

        if self.appearance:
            # Truncate to ~100 words for prompt efficiency
            words = self.appearance.split()[:100]
            parts.append(" ".join(words))

        if self.costume:
            parts.append(f"Wearing: {self.costume[:150]}")

        if self.distinguishing_features:
            parts.append(f"Notable: {self.distinguishing_features[:80]}")

        return ". ".join(parts)


@dataclass
class VisualLocation:
    """
    Visual-only location profile optimized for image generation.

    Contains ONLY the fields needed to render a location visually.
    """
    tag: str
    name: str
    description: str  # Core visual description

    # Visual atmosphere
    lighting: str = ""  # Lighting conditions
    atmosphere: str = ""  # Mood/ambiance
    time_period_style: str = ""  # Architectural era hints

    # Directional views (for consistent multi-angle shots)
    view_north: str = ""
    view_east: str = ""
    view_south: str = ""
    view_west: str = ""

    @classmethod
    def from_full_profile(cls, profile: Dict[str, Any]) -> 'VisualLocation':
        """Extract visual-only data from a full LocationProfile."""
        if hasattr(profile, '__dict__'):
            profile = profile.__dict__

        # Get atmosphere - might be nested
        atmosphere = profile.get('atmosphere', '')
        if isinstance(atmosphere, dict):
            atmosphere = atmosphere.get('mood', '') or atmosphere.get('emotional_quality', '')

        return cls(
            tag=profile.get('tag', ''),
            name=profile.get('name', ''),
            description=profile.get('description', ''),
            lighting=profile.get('lighting', ''),
            atmosphere=atmosphere,
            time_period_style=profile.get('time_period', ''),
            view_north=profile.get('view_north', ''),
            view_east=profile.get('view_east', ''),
            view_south=profile.get('view_south', ''),
            view_west=profile.get('view_west', '')
        )

    def to_prompt_block(self, direction: str = None) -> str:
        """Generate a concise prompt block for this location."""
        parts = [f"[{self.tag}] {self.name}"]

        # Use directional view if specified
        if direction and hasattr(self, f'view_{direction.lower()}'):
            dir_view = getattr(self, f'view_{direction.lower()}', '')
            if dir_view:
                parts.append(dir_view[:200])
            else:
                parts.append(self.description[:200])
        else:
            parts.append(self.description[:200])

        if self.lighting:
            parts.append(f"Lighting: {self.lighting[:80]}")

        if self.atmosphere:
            parts.append(f"Atmosphere: {self.atmosphere[:80]}")

        return ". ".join(parts)


@dataclass
class VisualProp:
    """Visual-only prop profile."""
    tag: str
    name: str
    appearance: str  # Visual description
    significance: str = ""  # Why it matters (for framing priority)

    @classmethod
    def from_full_profile(cls, profile: Dict[str, Any]) -> 'VisualProp':
        if hasattr(profile, '__dict__'):
            profile = profile.__dict__

        return cls(
            tag=profile.get('tag', ''),
            name=profile.get('name', ''),
            appearance=profile.get('appearance') or profile.get('description', ''),
            significance=profile.get('significance', '')
        )

    def to_prompt_block(self) -> str:
        parts = [f"[{self.tag}] {self.name}"]
        if self.appearance:
            parts.append(self.appearance[:100])
        return ". ".join(parts)


@dataclass
class VisualWorldConfig:
    """
    Optimized world configuration containing ONLY visual-relevant data.

    This is a distilled version of the full world bible, stripped of:
    - Narrative/behavioral data (speech, psychology, decisions)
    - Audio data (vocal descriptions for TTS)
    - Relationship dynamics
    - Character arcs

    Token reduction: ~70% smaller than full world config.
    """
    title: str
    visual_style: str  # live_action, anime, etc.
    lighting_style: str  # Global lighting approach
    color_palette: str  # Dominant colors/mood
    era_style: str  # Time period visual markers

    characters: List[VisualCharacter] = field(default_factory=list)
    locations: List[VisualLocation] = field(default_factory=list)
    props: List[VisualProp] = field(default_factory=list)

    # Quick lookup
    _char_index: Dict[str, VisualCharacter] = field(default_factory=dict, repr=False)
    _loc_index: Dict[str, VisualLocation] = field(default_factory=dict, repr=False)
    _prop_index: Dict[str, VisualProp] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        """Build lookup indexes."""
        self._char_index = {c.tag: c for c in self.characters}
        self._loc_index = {l.tag: l for l in self.locations}
        self._prop_index = {p.tag: p for p in self.props}

    def get_character(self, tag: str) -> Optional[VisualCharacter]:
        return self._char_index.get(tag)

    def get_location(self, tag: str) -> Optional[VisualLocation]:
        return self._loc_index.get(tag)

    def get_prop(self, tag: str) -> Optional[VisualProp]:
        return self._prop_index.get(tag)

    @classmethod
    def from_full_config(cls, config: Dict[str, Any]) -> 'VisualWorldConfig':
        """
        Create optimized visual config from full world bible.

        This is the main optimization entry point.
        """
        # Extract characters
        characters = []
        for char_data in config.get('characters', []):
            characters.append(VisualCharacter.from_full_profile(char_data))

        # Extract locations
        locations = []
        for loc_data in config.get('locations', []):
            locations.append(VisualLocation.from_full_profile(loc_data))

        # Extract props
        props = []
        for prop_data in config.get('props', []):
            props.append(VisualProp.from_full_profile(prop_data))

        return cls(
            title=config.get('title', ''),
            visual_style=config.get('visual_style', 'live_action'),
            lighting_style=config.get('lighting', ''),
            color_palette=config.get('vibe', ''),  # vibe often contains color hints
            era_style=config.get('time_period', '') or config.get('world_rules', '')[:100],
            characters=characters,
            locations=locations,
            props=props
        )

    @classmethod
    def from_json_file(cls, path: Path) -> 'VisualWorldConfig':
        """Load and optimize from a world_config.json file."""
        with open(path, 'r', encoding='utf-8') as f:
            full_config = json.load(f)
        return cls.from_full_config(full_config)

    def to_prompt_context(self) -> str:
        """
        Generate a compact prompt context block for all visual elements.

        This is what gets injected into prompts for image generation.
        """
        sections = []

        # Style header
        sections.append(f"## Visual Style: {self.visual_style}")
        if self.lighting_style:
            sections.append(f"Lighting: {self.lighting_style[:100]}")
        if self.color_palette:
            sections.append(f"Mood: {self.color_palette[:100]}")

        # Characters
        if self.characters:
            sections.append("\n## Characters")
            for char in self.characters:
                sections.append(char.to_prompt_block())

        # Locations
        if self.locations:
            sections.append("\n## Locations")
            for loc in self.locations:
                sections.append(loc.to_prompt_block())

        # Props (only if they exist)
        if self.props:
            sections.append("\n## Key Props")
            for prop in self.props:
                sections.append(prop.to_prompt_block())

        return "\n".join(sections)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "visual_style": self.visual_style,
            "lighting_style": self.lighting_style,
            "color_palette": self.color_palette,
            "era_style": self.era_style,
            "characters": [
                {
                    "tag": c.tag,
                    "name": c.name,
                    "role": c.role,
                    "age": c.age,
                    "ethnicity": c.ethnicity,
                    "appearance": c.appearance,
                    "costume": c.costume,
                    "distinguishing_features": c.distinguishing_features,
                    "body_language_hint": c.body_language_hint
                }
                for c in self.characters
            ],
            "locations": [
                {
                    "tag": l.tag,
                    "name": l.name,
                    "description": l.description,
                    "lighting": l.lighting,
                    "atmosphere": l.atmosphere,
                    "time_period_style": l.time_period_style
                }
                for l in self.locations
            ],
            "props": [
                {
                    "tag": p.tag,
                    "name": p.name,
                    "appearance": p.appearance,
                    "significance": p.significance
                }
                for p in self.props
            ]
        }

    def estimate_token_count(self) -> int:
        """Estimate token count for the prompt context."""
        text = self.to_prompt_context()
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4


class WorldConfigOptimizer:
    """
    Analyzes and optimizes world configs for visual output.

    Can further reduce token usage by:
    1. Removing characters not in current scene
    2. Condensing descriptions based on shot type
    3. Caching optimized configs per scene
    """

    def __init__(self, visual_config: VisualWorldConfig):
        self.config = visual_config
        self._scene_cache: Dict[int, str] = {}

    def get_scene_context(
        self,
        scene_number: int,
        character_tags: List[str],
        location_tag: str,
        prop_tags: List[str] = None
    ) -> str:
        """
        Get optimized context for a specific scene.

        Only includes characters/props actually in the scene.
        """
        cache_key = f"{scene_number}:{','.join(sorted(character_tags))}:{location_tag}"

        if cache_key in self._scene_cache:
            return self._scene_cache[cache_key]

        sections = []

        # Style (always include)
        sections.append(f"Style: {self.config.visual_style}")
        if self.config.lighting_style:
            sections.append(f"Lighting: {self.config.lighting_style[:80]}")

        # Location for this scene
        location = self.config.get_location(location_tag)
        if location:
            sections.append(f"\nLocation: {location.to_prompt_block()}")

        # Only characters in this scene
        sections.append("\nCharacters in scene:")
        for tag in character_tags:
            char = self.config.get_character(tag)
            if char:
                sections.append(f"  {char.to_prompt_block()}")

        # Only props in this scene
        if prop_tags:
            sections.append("\nProps:")
            for tag in prop_tags:
                prop = self.config.get_prop(tag)
                if prop:
                    sections.append(f"  {prop.to_prompt_block()}")

        result = "\n".join(sections)
        self._scene_cache[cache_key] = result
        return result

    def get_frame_context(
        self,
        character_tags: List[str],
        location_tag: str,
        shot_type: str,
        focus_subject: str
    ) -> str:
        """
        Get ultra-condensed context for a single frame.

        Adjusts detail level based on shot type:
        - Wide: More location, less character detail
        - Close-up: More character detail, less location
        - Medium: Balanced
        """
        parts = []

        # Style always
        parts.append(f"{self.config.visual_style}")

        # Location - more detail for wide shots
        location = self.config.get_location(location_tag)
        if location:
            if shot_type in ('wide', 'aerial', 'establishing'):
                parts.append(location.description[:150])
            else:
                parts.append(f"{location.name}, {location.atmosphere[:50]}")

        # Characters - more detail for close shots
        for tag in character_tags:
            char = self.config.get_character(tag)
            if char:
                is_focus = tag.lower() in focus_subject.lower() or char.name.lower() in focus_subject.lower()

                if shot_type in ('close-up', 'extreme-close-up') or is_focus:
                    # Full appearance for close-ups or focus character
                    parts.append(f"{char.name}: {char.appearance[:120]}")
                    if char.costume:
                        parts.append(f"wearing {char.costume[:60]}")
                else:
                    # Brief for background characters
                    parts.append(f"{char.name}: {char.appearance[:50]}")

        return ". ".join(parts)

    @staticmethod
    def analyze_reduction(full_config: Dict[str, Any], visual_config: VisualWorldConfig) -> Dict[str, Any]:
        """
        Analyze the token reduction achieved by optimization.

        Returns stats on original vs optimized sizes.
        """
        # Estimate full config size
        full_text = json.dumps(full_config)
        full_tokens = len(full_text) // 4

        # Estimate optimized size
        optimized_tokens = visual_config.estimate_token_count()

        reduction = ((full_tokens - optimized_tokens) / full_tokens) * 100

        return {
            "full_config_tokens": full_tokens,
            "visual_config_tokens": optimized_tokens,
            "reduction_percent": round(reduction, 1),
            "characters_kept": len(visual_config.characters),
            "locations_kept": len(visual_config.locations),
            "props_kept": len(visual_config.props)
        }


# =============================================================================
# CONVERSATION CONTEXT - Persistent Claude Opus Session
# =============================================================================

@dataclass
class ConversationMessage:
    """A message in the conversation history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    phase: str = ""  # Which pipeline phase generated this
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationContext:
    """
    Maintains a persistent conversation with Claude Opus.

    All pipeline operations use this single conversation, allowing:
    - Full context awareness across all operations
    - Coherent healing that can reference earlier generation
    - Atomic edits with surrounding context

    Supports context caching via disk persistence for resumption.
    """

    OPUS_MODEL = "claude-opus-4-5-20251101"

    def __init__(
        self,
        project_id: str,
        cache_path: Optional[Path] = None,
        system_prompt: str = None
    ):
        """
        Initialize conversation context.

        Args:
            project_id: Unique identifier for this project/session
            cache_path: Optional path to cache conversation to disk
            system_prompt: System prompt for Claude Opus
        """
        self.project_id = project_id
        self.cache_path = cache_path
        self.messages: List[ConversationMessage] = []
        self._client = AnthropicClient()

        self.system_prompt = system_prompt or self._default_system_prompt()

        # Stats tracking
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.request_count = 0

        # Load from cache if exists
        if cache_path and cache_path.exists():
            self._load_from_cache()

    def _default_system_prompt(self) -> str:
        """Default system prompt for unified visual script generation."""
        return """You are a master filmmaker and screenwriter working on a visual storytelling project.

Your role is to create richly detailed visual scripts with embedded frame markers that guide cinematography.

## CRITICAL - ERA ACCURACY

**THE MOST IMPORTANT RULE**: ALL visual descriptions MUST be era-appropriate.
- If the story is set in Imperial China → NO modern elements. Traditional clothing, architecture, lighting (candles, lanterns, natural light)
- If the story is set in 1920s → Art Deco, flapper dresses, Model T cars, gas lamps
- If the story is set in Medieval Europe → Stone castles, torches, tunics, no electricity
- If the story is set in the future → Futuristic elements only
- NEVER MIX ERAS. A Tang Dynasty character does NOT have modern furniture.

LIGHTING BY ERA:
- Pre-1880s: Candles, oil lamps, lanterns, natural sunlight/moonlight ONLY
- 1880-1920s: Gas lamps, early electric bulbs, natural light
- Post-1920s: Modern electric lighting acceptable

## Frame Marker Format

When writing scenes, embed frame markers directly in the prose:

[FRAME: shot_type, focus_subject] Narrative prose continues here...

Shot types: wide, medium, close-up, extreme-close-up, over-shoulder, pov, tracking, insert, reaction
Focus subject: character tag, object, or descriptive term

## VISUAL MOMENT COVERAGE

**TRIGGER-REACTION PAIRS**: Every significant action needs TWO frames:
1. THE TRIGGER: [FRAME: close-up, action/object] - What happens
2. THE REACTION: [FRAME: close-up, CHAR reaction] - Character's response

**INTERACTION CLOSE-UPS**: Physical actions need detail shots:
- Hands reaching → [FRAME: insert, hands]
- Concealing → [FRAME: extreme-close-up, hidden object]
- Exchanging → [FRAME: close-up, the exchange]

**B-ROLL FRAMES**: Environmental and transitional shots:
- Location details, weather elements, symbolic objects
- Time transitions, mood setters

**COMPOSITION DIVERSITY**: Vary your shots:
- Alternate between wide/medium/close
- Use different angles for emotional effect
- Include reaction shots after every major beat

## Tag Format

Use consistent tags for characters, locations, and props:
- Characters: CHAR_NAME (e.g., CHAR_ALICE, CHAR_DETECTIVE)
- Locations: LOC_NAME (e.g., LOC_COFFEE_SHOP, LOC_ROOFTOP)
- Props: PROP_NAME (e.g., PROP_LETTER, PROP_DAGGER)

## Visual Thinking

As you write, visualize each frame:
- What does the camera see?
- Where is the emotional focus?
- How does lighting support the mood? (USE ERA-APPROPRIATE SOURCES)
- What movement occurs within the frame?
- Is there a reaction shot needed after this action?

Your prose should be cinematic - every sentence paintable as a frame.
VERIFY all props, costumes, and lighting are appropriate for the story's era."""

    def _to_api_messages(self) -> List[Dict[str, str]]:
        """Convert conversation history to API format."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]

    async def send(
        self,
        content: str,
        phase: str = "",
        max_tokens: int = 16000,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Send a message and get response, maintaining conversation history.

        Args:
            content: User message content
            phase: Pipeline phase identifier (for tracking)
            max_tokens: Maximum response tokens
            metadata: Optional metadata to attach to message

        Returns:
            Assistant response text
        """
        # Add user message to history
        user_msg = ConversationMessage(
            role="user",
            content=content,
            phase=phase,
            metadata=metadata or {}
        )
        self.messages.append(user_msg)

        # Build API messages
        api_messages = self._to_api_messages()

        # Call Claude Opus with full conversation
        response = await asyncio.to_thread(
            self._client.generate_with_conversation,
            messages=api_messages,
            system=self.system_prompt,
            max_tokens=max_tokens,
            model=self.OPUS_MODEL
        )

        # Check for content rejection and fall back to Grok 4 if needed
        from greenlight.llm.api_clients import is_content_rejection, GrokClient
        if is_content_rejection(response.text):
            logger.warning(f"Content rejection from Claude Opus, falling back to Grok 4")
            try:
                grok_client = GrokClient()
                # For Grok, combine system prompt with messages
                grok_prompt = f"{self.system_prompt}\n\n{content}" if self.system_prompt else content
                grok_response = await asyncio.to_thread(
                    grok_client.generate_text,
                    prompt=grok_prompt,
                    max_tokens=max_tokens,
                    temperature=0.7,
                    model="grok-4"
                )
                if grok_response.text and len(grok_response.text) > 50:
                    logger.info("Grok 4 fallback successful")
                    response = grok_response
            except Exception as e:
                logger.error(f"Grok 4 fallback failed: {e}")
                # Continue with original response

        # Track usage
        if response.usage:
            self.total_tokens_in += response.usage.get("input_tokens", 0)
            self.total_tokens_out += response.usage.get("output_tokens", 0)
        self.request_count += 1

        # Add assistant response to history
        assistant_msg = ConversationMessage(
            role="assistant",
            content=response.text,
            phase=phase,
            metadata={"tokens": response.usage}
        )
        self.messages.append(assistant_msg)

        # Auto-save to cache if configured
        if self.cache_path:
            self._save_to_cache()

        logger.debug(
            f"Conversation turn {self.request_count}: "
            f"{len(content)} chars → {len(response.text)} chars"
        )

        return response.text

    async def heal_frame(
        self,
        frame_marker: str,
        surrounding_context: str,
        issue: str,
        phase: str = "healing"
    ) -> str:
        """
        Heal a specific frame with full conversation context.

        This is the key advantage of unified pipeline - healing operations
        have access to the entire story context.

        Args:
            frame_marker: The [FRAME: ...] marker to heal
            surrounding_context: Prose before and after the frame
            issue: Description of the issue to fix
            phase: Phase identifier

        Returns:
            Healed frame content
        """
        prompt = f"""I need to heal a specific frame in our visual script.

## Frame to Heal
{frame_marker}

## Surrounding Context
{surrounding_context}

## Issue to Fix
{issue}

Please provide ONLY the corrected frame marker and its associated prose.
Keep the same narrative intent but fix the identified issue.
Format: [FRAME: shot_type, focus] Corrected prose here..."""

        return await self.send(prompt, phase=phase, max_tokens=1000)

    def get_context_summary(self) -> Dict[str, Any]:
        """Get summary of conversation context."""
        return {
            "project_id": self.project_id,
            "message_count": len(self.messages),
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "request_count": self.request_count,
            "phases": list(set(m.phase for m in self.messages if m.phase))
        }

    def _save_to_cache(self) -> None:
        """Save conversation to disk cache."""
        if not self.cache_path:
            return

        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "project_id": self.project_id,
                "system_prompt": self.system_prompt,
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "timestamp": m.timestamp,
                        "phase": m.phase,
                        "metadata": m.metadata
                    }
                    for m in self.messages
                ],
                "stats": {
                    "total_tokens_in": self.total_tokens_in,
                    "total_tokens_out": self.total_tokens_out,
                    "request_count": self.request_count
                }
            }

            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved conversation cache: {self.cache_path}")

        except Exception as e:
            logger.warning(f"Failed to save conversation cache: {e}")

    def _load_from_cache(self) -> None:
        """Load conversation from disk cache."""
        if not self.cache_path or not self.cache_path.exists():
            return

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.system_prompt = data.get("system_prompt", self.system_prompt)

            for msg_data in data.get("messages", []):
                self.messages.append(ConversationMessage(
                    role=msg_data["role"],
                    content=msg_data["content"],
                    timestamp=msg_data.get("timestamp", 0),
                    phase=msg_data.get("phase", ""),
                    metadata=msg_data.get("metadata", {})
                ))

            stats = data.get("stats", {})
            self.total_tokens_in = stats.get("total_tokens_in", 0)
            self.total_tokens_out = stats.get("total_tokens_out", 0)
            self.request_count = stats.get("request_count", 0)

            logger.info(
                f"Loaded conversation cache: {len(self.messages)} messages, "
                f"{self.request_count} prior requests"
            )

        except Exception as e:
            logger.warning(f"Failed to load conversation cache: {e}")


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class UnifiedPipelineInput:
    """Input for the unified visual script pipeline."""
    pitch: str  # Raw story pitch/concept
    title: str = ""
    genre: str = ""
    visual_style: str = "live_action"
    style_notes: str = ""
    project_size: str = "short"  # micro, short, medium, feature
    project_path: Optional[Path] = None

    # Optional: Use existing world config instead of generating new
    existing_world_config: Optional[Dict[str, Any]] = None
    world_config_path: Optional[Path] = None  # Path to world_config.json

    def load_world_config(self) -> Optional[Dict[str, Any]]:
        """Load world config from path or return existing."""
        if self.existing_world_config:
            return self.existing_world_config

        if self.world_config_path and self.world_config_path.exists():
            with open(self.world_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Try default location in project path
        if self.project_path:
            default_path = self.project_path / "world_bible" / "world_config.json"
            if default_path.exists():
                with open(default_path, 'r', encoding='utf-8') as f:
                    return json.load(f)

        return None


@dataclass
class InlineFrame:
    """A frame extracted from inline markers."""
    frame_id: str  # scene.frame.camera (e.g., "1.2.cA")
    scene_number: int
    frame_number: int
    shot_type: str  # wide, medium, close-up, etc.
    focus_subject: str  # What/who the frame focuses on
    prose: str  # The narrative text for this frame
    prompt: str = ""  # Generated image prompt (added in Phase 3)
    tags: List[str] = field(default_factory=list)

    @property
    def marker(self) -> str:
        """Reconstruct the frame marker."""
        return f"[FRAME: {self.shot_type}, {self.focus_subject}]"


@dataclass
class UnifiedScene:
    """A scene with inline frame markers."""
    scene_number: int
    location_tag: str
    time_of_day: str
    characters: List[str]
    raw_content: str  # Content with [FRAME:] markers
    frames: List[InlineFrame] = field(default_factory=list)


@dataclass
class UnifiedVisualOutput:
    """Output from the unified pipeline."""
    title: str
    visual_script: str  # Complete script with prompts
    scenes: List[UnifiedScene] = field(default_factory=list)
    total_frames: int = 0
    visual_config: Optional[VisualWorldConfig] = None  # Optimized visual config
    full_world_config: Dict[str, Any] = field(default_factory=dict)  # Original full config
    optimization_stats: Dict[str, Any] = field(default_factory=dict)  # Token savings
    conversation_summary: Dict[str, Any] = field(default_factory=dict)

    # Backwards compatibility
    @property
    def world_config(self) -> Dict[str, Any]:
        """Return visual config as dict for backwards compatibility."""
        if self.visual_config:
            return self.visual_config.to_dict()
        return self.full_world_config

    def to_shot_list(self) -> List[Dict[str, Any]]:
        """Convert to shot list format for storyboard generation."""
        shots = []
        for scene in self.scenes:
            for frame in scene.frames:
                shots.append({
                    "frame_id": frame.frame_id,
                    "scene_number": frame.scene_number,
                    "frame_number": frame.frame_number,
                    "shot_type": frame.shot_type,
                    "focus": frame.focus_subject,
                    "prompt": frame.prompt,
                    "prose": frame.prose,
                    "tags": frame.tags,
                    "location_tag": scene.location_tag
                })
        return shots

    def save_visual_config(self, path: Path) -> None:
        """Save the optimized visual config to disk."""
        if self.visual_config:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.visual_config.to_dict(), f, indent=2)
            logger.info(f"Saved visual config to {path}")


# =============================================================================
# UNIFIED VISUAL SCRIPT PIPELINE
# =============================================================================

class UnifiedVisualScriptPipeline(BasePipeline):
    """
    Single-pass pipeline that generates visual scripts with inline frame markers.

    Uses persistent conversation context with Claude Opus for:
    - Coherent story generation across all scenes
    - Context-aware prompt injection
    - Surgical healing with full story awareness

    Phases:
    1. World Building - Extract tags, build world config from pitch
    2. Scene Generation - Write scenes with inline [FRAME:] markers
    3. Prompt Injection - Generate image prompts for each frame (parallel)
    4. Validation & Healing - Validate prompts, heal failures surgically
    """

    # Scene counts by project size
    SIZE_CONFIG = {
        "micro": {"scenes": 3, "frames_per_scene": 3},
        "short": {"scenes": 8, "frames_per_scene": 5},
        "medium": {"scenes": 15, "frames_per_scene": 6},
        "feature": {"scenes": 40, "frames_per_scene": 8},
    }

    # Frame marker regex pattern
    FRAME_PATTERN = re.compile(
        r'\[FRAME:\s*([^,\]]+),\s*([^\]]+)\]\s*(.+?)(?=\[FRAME:|$)',
        re.DOTALL
    )

    def __init__(
        self,
        project_path: Optional[Path] = None,
        cache_conversations: bool = True
    ):
        """
        Initialize the unified pipeline.

        Args:
            project_path: Path to project directory
            cache_conversations: Whether to cache conversation to disk
        """
        self.project_path = Path(project_path) if project_path else None
        self.cache_conversations = cache_conversations
        self.context: Optional[ConversationContext] = None

    async def run(self, input_data: UnifiedPipelineInput) -> PipelineResult:
        """
        Run the unified visual script pipeline.

        Args:
            input_data: Pipeline input with pitch and configuration

        Returns:
            PipelineResult with UnifiedVisualOutput
        """
        start_time = time.time()

        # Initialize conversation context
        cache_path = None
        if self.cache_conversations and self.project_path:
            cache_path = self.project_path / ".cache" / "conversation_context.json"

        project_id = input_data.title or f"project_{int(time.time())}"
        self.context = ConversationContext(
            project_id=project_id,
            cache_path=cache_path
        )

        try:
            # Phase 1: World Config Loading + Visual Optimization
            logger.info("Phase 1: World Config Loading + Visual Optimization")
            full_config, visual_config, optimization_stats = await self._phase_world_building(input_data)

            # Create optimizer for scene-level context
            self.config_optimizer = WorldConfigOptimizer(visual_config)

            # Phase 2: Scene Generation with Inline Frame Markers
            logger.info("Phase 2: Scene Generation with Frame Markers")
            scenes = await self._phase_scene_generation(input_data, visual_config)

            # Phase 3: Parallel Prompt Injection (uses optimized per-frame context)
            logger.info("Phase 3: Prompt Injection")
            scenes = await self._phase_prompt_injection(scenes, visual_config)

            # Phase 4: Validation & Healing
            logger.info("Phase 4: Validation & Healing")
            scenes, validation_results = await self._phase_validation_healing(scenes)

            # Build final output
            visual_script = self._assemble_visual_script(scenes, input_data.title)
            total_frames = sum(len(s.frames) for s in scenes)

            output = UnifiedVisualOutput(
                title=input_data.title,
                visual_script=visual_script,
                scenes=scenes,
                total_frames=total_frames,
                visual_config=visual_config,
                full_world_config=full_config,
                optimization_stats=optimization_stats,
                conversation_summary=self.context.get_context_summary()
            )

            elapsed = time.time() - start_time
            logger.info(
                f"Pipeline complete: {len(scenes)} scenes, {total_frames} frames "
                f"in {elapsed:.1f}s ({self.context.request_count} LLM calls)"
            )
            if optimization_stats:
                logger.info(
                    f"Config optimization: {optimization_stats.get('reduction_percent', 0)}% token reduction "
                    f"({optimization_stats.get('full_config_tokens', 0)} → {optimization_stats.get('visual_config_tokens', 0)} tokens)"
                )

            return PipelineResult(
                success=True,
                output=output,
                execution_time=elapsed,
                metadata={
                    "validation": validation_results,
                    "optimization": optimization_stats,
                    "conversation": self.context.get_context_summary()
                }
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return PipelineResult(
                success=False,
                output=None,
                error=str(e),
                execution_time=time.time() - start_time
            )

    async def _phase_world_building(
        self,
        input_data: UnifiedPipelineInput
    ) -> Tuple[Dict[str, Any], VisualWorldConfig, Dict[str, Any]]:
        """
        Phase 1: Load or generate world config, then optimize for visual output.

        Returns:
            Tuple of (full_config, visual_config, optimization_stats)
        """
        # Check for existing world config
        existing_config = input_data.load_world_config()

        if existing_config:
            logger.info("Using existing world config - optimizing for visual output")
            full_config = existing_config

            # Create optimized visual config
            visual_config = VisualWorldConfig.from_full_config(full_config)

            # Calculate optimization stats
            optimization_stats = WorldConfigOptimizer.analyze_reduction(full_config, visual_config)

            logger.info(
                f"Loaded {len(visual_config.characters)} characters, "
                f"{len(visual_config.locations)} locations, "
                f"{len(visual_config.props)} props "
                f"({optimization_stats['reduction_percent']}% token reduction)"
            )

            # Brief context message to Claude about the world
            await self.context.send(
                f"Using existing world configuration for '{full_config.get('title', input_data.title)}'.\n\n"
                f"Visual context:\n{visual_config.to_prompt_context()}",
                phase="world_building",
                max_tokens=500
            )

            return full_config, visual_config, optimization_stats

        # No existing config - generate from pitch
        logger.info("Generating new world config from pitch")

        prompt = f"""Analyze this story pitch and extract the world configuration.

## Pitch
{input_data.pitch}

## Additional Context
- Title: {input_data.title or 'TBD'}
- Genre: {input_data.genre or 'TBD'}
- Visual Style: {input_data.visual_style}
- Style Notes: {input_data.style_notes or 'None'}

## Required Output (JSON format)

```json
{{
    "title": "Story Title",
    "logline": "One-sentence summary",
    "themes": ["theme1", "theme2"],
    "tone": "overall tone/mood",
    "visual_style": "{input_data.visual_style}",

    "characters": [
        {{
            "tag": "CHAR_NAME",
            "name": "Full Name",
            "role": "protagonist/antagonist/supporting",
            "appearance": "Detailed physical description (50-100 words)",
            "costume": "Default clothing description (30-50 words)",
            "personality": "Key traits and psychology"
        }}
    ],

    "locations": [
        {{
            "tag": "LOC_NAME",
            "name": "Location Name",
            "description": "Detailed visual description",
            "atmosphere": "Mood and lighting"
        }}
    ],

    "props": [
        {{
            "tag": "PROP_NAME",
            "name": "Prop Name",
            "description": "Visual description",
            "significance": "Story importance"
        }}
    ]
}}
```

Extract ALL characters, locations, and significant props mentioned or implied in the pitch.
Create descriptive tags using CHAR_, LOC_, PROP_ prefixes."""

        response = await self.context.send(prompt, phase="world_building", max_tokens=4000)

        # Parse JSON from response
        full_config = self._extract_json(response)

        if not full_config:
            # Fallback: minimal config
            full_config = {
                "title": input_data.title,
                "characters": [],
                "locations": [],
                "props": [],
                "visual_style": input_data.visual_style
            }
            logger.warning("Failed to parse world config, using minimal fallback")

        # Create optimized visual config from generated config
        visual_config = VisualWorldConfig.from_full_config(full_config)

        # Calculate optimization stats
        optimization_stats = WorldConfigOptimizer.analyze_reduction(full_config, visual_config)

        logger.info(
            f"Generated {len(visual_config.characters)} characters, "
            f"{len(visual_config.locations)} locations, "
            f"{len(visual_config.props)} props"
        )

        return full_config, visual_config, optimization_stats

    async def _phase_scene_generation(
        self,
        input_data: UnifiedPipelineInput,
        visual_config: VisualWorldConfig
    ) -> List[UnifiedScene]:
        """
        Phase 2: Generate scenes with inline frame markers.

        Each scene includes [FRAME: shot_type, focus] markers embedded in prose.
        Uses optimized visual config for efficient context.
        """
        size_config = self.SIZE_CONFIG.get(input_data.project_size, self.SIZE_CONFIG["short"])
        target_scenes = size_config["scenes"]
        target_frames = size_config["frames_per_scene"]

        # Build character/location reference from visual config
        char_tags = [c.tag for c in visual_config.characters]
        loc_tags = [l.tag for l in visual_config.locations]

        # Use optimized visual context
        visual_context = visual_config.to_prompt_context()

        prompt = f"""Now write the complete visual script with inline frame markers.

## Visual World Reference
{visual_context}

## Character Tags: {', '.join(char_tags) or 'None defined'}
## Location Tags: {', '.join(loc_tags) or 'None defined'}

## Requirements
- Write approximately {target_scenes} scenes
- Each scene should have {target_frames-2} to {target_frames+2} frames
- Embed [FRAME: shot_type, focus] markers in the prose

## Scene Format

## Scene N: Scene Title
LOC_TAG - TIME_OF_DAY

[FRAME: wide, establishing] Opening description of the location and atmosphere.
[FRAME: medium, CHAR_NAME] Character action and dialogue continues naturally.
[FRAME: close-up, object/detail] Emphasis on important visual details.

## Shot Types (use these)
- wide: Full environment, establishing shots
- medium: Character from waist up, conversations
- close-up: Face details, emotional moments
- extreme-close-up: Specific details (eyes, hands, objects)
- over-shoulder: Dialogue from behind one character
- pov: Point of view shot
- tracking: Following movement
- aerial: Bird's eye view

## Critical Rules
1. EVERY piece of prose must be preceded by a [FRAME:] marker
2. Use character tags (CHAR_NAME) when focusing on specific characters
3. Vary shot types to create visual rhythm
4. Frame markers flow naturally with the narrative

Begin the visual script now. Write the complete story with all scenes and frame markers."""

        response = await self.context.send(prompt, phase="scene_generation", max_tokens=12000)

        # Parse scenes from response
        scenes = self._parse_scenes_with_frames(response, visual_config)

        return scenes

    async def _phase_prompt_injection(
        self,
        scenes: List[UnifiedScene],
        visual_config: VisualWorldConfig
    ) -> List[UnifiedScene]:
        """
        Phase 3: Generate image prompts for each frame (parallel).

        Uses optimized per-frame context from WorldConfigOptimizer to minimize
        token usage while maintaining visual accuracy.
        """
        # Collect all frames
        all_frames = []
        for scene in scenes:
            for frame in scene.frames:
                all_frames.append((scene, frame))

        if not all_frames:
            return scenes

        # Generate prompts in batches (to stay within context limits)
        batch_size = 10
        for i in range(0, len(all_frames), batch_size):
            batch = all_frames[i:i + batch_size]

            # Build optimized context for this batch
            frames_text_parts = []
            for scene, frame in batch:
                # Get per-frame optimized context
                frame_context = self.config_optimizer.get_frame_context(
                    character_tags=frame.tags,
                    location_tag=scene.location_tag,
                    shot_type=frame.shot_type,
                    focus_subject=frame.focus_subject
                )

                frames_text_parts.append(
                    f"Frame {frame.frame_id}:\n"
                    f"  Shot: {frame.shot_type}\n"
                    f"  Focus: {frame.focus_subject}\n"
                    f"  Context: {frame_context[:150]}\n"
                    f"  Prose: {frame.prose[:150]}..."
                )

            frames_text = "\n\n".join(frames_text_parts)

            prompt = f"""Generate concise image prompts for these frames.

## Visual Style: {visual_config.visual_style}
## Lighting: {visual_config.lighting_style[:80] if visual_config.lighting_style else 'Cinematic'}

## Frames to Process
{frames_text}

## Output Format

For each frame, provide a prompt in this exact format:

FRAME_ID: prompt text here (50 words max, what camera literally sees)

Include: shot type, lighting, character appearance details, environment, mood.
Example:
1.2.cA: Wide shot of dimly lit coffee shop interior, morning sunlight streaming through large windows, woman in red coat at corner table, warm amber lighting, photorealistic, cinematic

Generate prompts for all {len(batch)} frames listed above."""

            response = await self.context.send(prompt, phase="prompt_injection", max_tokens=3000)

            # Parse prompts from response
            self._apply_prompts_to_frames(response, batch)

        return scenes

    async def _phase_validation_healing(
        self,
        scenes: List[UnifiedScene]
    ) -> Tuple[List[UnifiedScene], Dict[str, Any]]:
        """
        Phase 4: Validate prompts and heal any issues.

        Uses the conversation context for surgical healing.
        """
        validation_results = {
            "total_frames": 0,
            "valid_frames": 0,
            "healed_frames": 0,
            "issues": []
        }

        for scene in scenes:
            for frame in scene.frames:
                validation_results["total_frames"] += 1

                # Basic validation
                issues = self._validate_frame(frame)

                if not issues:
                    validation_results["valid_frames"] += 1
                else:
                    # Attempt healing
                    for issue in issues:
                        validation_results["issues"].append({
                            "frame_id": frame.frame_id,
                            "issue": issue
                        })

                    # Get surrounding context
                    context = self._get_surrounding_context(scene, frame)

                    healed = await self.context.heal_frame(
                        frame_marker=frame.marker,
                        surrounding_context=context,
                        issue="; ".join(issues),
                        phase="healing"
                    )

                    # Apply healed content
                    if healed and len(healed) > 20:
                        # Re-extract prompt from healed content
                        frame.prose = healed
                        validation_results["healed_frames"] += 1

        return scenes, validation_results

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text, handling markdown code blocks."""
        # Try to find JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try parsing the whole text as JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try finding JSON object
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def _parse_scenes_with_frames(
        self,
        text: str,
        visual_config: VisualWorldConfig
    ) -> List[UnifiedScene]:
        """Parse scenes and extract inline frame markers."""
        scenes = []

        # Split by scene headers
        scene_pattern = re.compile(
            r'##\s*Scene\s+(\d+):\s*([^\n]+)\n([^\n]*)\n([\s\S]*?)(?=##\s*Scene|$)',
            re.IGNORECASE
        )

        for match in scene_pattern.finditer(text):
            scene_num = int(match.group(1))
            scene_title = match.group(2).strip()
            location_line = match.group(3).strip()
            content = match.group(4).strip()

            # Parse location and time
            loc_match = re.match(r'(LOC_\w+)\s*[-–]\s*(.+)', location_line)
            location_tag = loc_match.group(1) if loc_match else "LOC_UNKNOWN"
            time_of_day = loc_match.group(2) if loc_match else "DAY"

            # Extract frames
            frames = []
            frame_num = 0

            for frame_match in self.FRAME_PATTERN.finditer(content):
                frame_num += 1
                shot_type = frame_match.group(1).strip().lower()
                focus = frame_match.group(2).strip()
                prose = frame_match.group(3).strip()

                # Extract tags from focus and prose
                tags = re.findall(r'(CHAR_\w+|LOC_\w+|PROP_\w+)', f"{focus} {prose}")

                frame = InlineFrame(
                    frame_id=f"{scene_num}.{frame_num}.cA",
                    scene_number=scene_num,
                    frame_number=frame_num,
                    shot_type=shot_type,
                    focus_subject=focus,
                    prose=prose,
                    tags=list(set(tags))
                )
                frames.append(frame)

            # Extract characters from content
            char_tags = list(set(re.findall(r'CHAR_\w+', content)))

            scene = UnifiedScene(
                scene_number=scene_num,
                location_tag=location_tag,
                time_of_day=time_of_day,
                characters=char_tags,
                raw_content=content,
                frames=frames
            )
            scenes.append(scene)

        return scenes

    def _apply_prompts_to_frames(
        self,
        response: str,
        frames: List[Tuple[UnifiedScene, InlineFrame]]
    ) -> None:
        """Apply generated prompts to frames."""
        # Parse prompts from response
        prompt_pattern = re.compile(r'(\d+\.\d+\.c\w+):\s*(.+?)(?=\d+\.\d+\.c\w+:|$)', re.DOTALL)

        prompts = {}
        for match in prompt_pattern.finditer(response):
            frame_id = match.group(1)
            prompt = match.group(2).strip()
            prompts[frame_id] = prompt

        # Apply to frames
        for scene, frame in frames:
            if frame.frame_id in prompts:
                frame.prompt = prompts[frame.frame_id]

    def _validate_frame(self, frame: InlineFrame) -> List[str]:
        """Validate a frame and return list of issues."""
        issues = []

        if not frame.prompt:
            issues.append("Missing image prompt")
        elif len(frame.prompt) < 20:
            issues.append("Prompt too short")

        if not frame.prose:
            issues.append("Missing prose content")

        if not frame.shot_type:
            issues.append("Missing shot type")

        return issues

    def _get_surrounding_context(
        self,
        scene: UnifiedScene,
        target_frame: InlineFrame
    ) -> str:
        """Get prose context surrounding a frame for healing."""
        frames = scene.frames
        target_idx = None

        for i, f in enumerate(frames):
            if f.frame_id == target_frame.frame_id:
                target_idx = i
                break

        if target_idx is None:
            return target_frame.prose

        # Get 2 frames before and after
        start = max(0, target_idx - 2)
        end = min(len(frames), target_idx + 3)

        context_parts = []
        for i in range(start, end):
            frame = frames[i]
            marker = ">>> " if i == target_idx else ""
            context_parts.append(f"{marker}{frame.marker} {frame.prose}")

        return "\n\n".join(context_parts)

    def _assemble_visual_script(
        self,
        scenes: List[UnifiedScene],
        title: str
    ) -> str:
        """Assemble the final visual script with prompts."""
        lines = [f"# {title}", "", "---", ""]

        for scene in scenes:
            lines.append(f"## Scene {scene.scene_number}")
            lines.append(f"{scene.location_tag} - {scene.time_of_day}")
            lines.append("")

            for frame in scene.frames:
                # Frame notation
                lines.append(f"[{frame.frame_id}] ({frame.shot_type.upper()})")
                lines.append("")

                # Prose
                lines.append(frame.prose)
                lines.append("")

                # Prompt block
                if frame.prompt:
                    lines.append(f"**PROMPT:** {frame.prompt}")
                    lines.append("")

                lines.append("---")
                lines.append("")

        return "\n".join(lines)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def run_unified_pipeline(
    pitch: str,
    title: str = "",
    project_path: str = None,
    project_size: str = "short",
    visual_style: str = "live_action"
) -> UnifiedVisualOutput:
    """
    Convenience function to run the unified pipeline.

    Args:
        pitch: Story pitch text
        title: Optional title
        project_path: Path to project directory
        project_size: Size preset (micro, short, medium, feature)
        visual_style: Visual style (live_action, anime, etc.)

    Returns:
        UnifiedVisualOutput with complete visual script
    """
    pipeline = UnifiedVisualScriptPipeline(
        project_path=Path(project_path) if project_path else None
    )

    input_data = UnifiedPipelineInput(
        pitch=pitch,
        title=title,
        project_size=project_size,
        visual_style=visual_style,
        project_path=Path(project_path) if project_path else None
    )

    result = await pipeline.run(input_data)

    if result.success:
        return result.output
    else:
        raise RuntimeError(f"Pipeline failed: {result.error}")
