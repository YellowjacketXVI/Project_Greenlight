"""
World Bible Research Pipeline for Writer Flow v2

Implements chunked-per-tag architecture where each extracted tag gets its own
dedicated research pipeline running in parallel.

Architecture:
- Character tags: 5 research agents → 3 judges → synthesize
- Location tags: 3 research agents → 3 judges → synthesize
- Prop tags: 2 research agents → 2 judges → synthesize
- Global context: 3 research agents → 3 judges → synthesize
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set

from greenlight.core.constants import LLMFunction, TagPrefix
from greenlight.core.logging_config import get_logger
from greenlight.pipelines.base_pipeline import BasePipeline, PipelineStep, PipelineResult
from greenlight.patterns.assembly import (
    AssemblyPattern, AssemblyConfig, Proposal, JudgeRanking,
    CalculatorResult, SynthesisResult, ProposalAgent, JudgeAgent
)
from greenlight.agents.assembly_agents import (
    AssemblyJudgeAgent, AssemblyCalculatorAgent, AssemblySynthesizerAgent
)

logger = get_logger("pipelines.world_bible")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TagResearchInput:
    """Input for tag research."""
    tag: str
    tag_type: str  # character, location, prop
    pitch_text: str
    time_period: str = ""
    setting: str = ""
    genre: str = ""
    media_type: str = "standard"


@dataclass
class CharacterProfile:
    """
    Complete character profile from research.

    Designed for agent embodiment - enables convincing dialogue, movement, and decisions.
    """
    tag: str
    name: str
    role: str
    age: str = ""
    ethnicity: str = ""
    backstory: str = ""
    visual_appearance: str = ""
    costume: str = ""

    # =========================================================================
    # INTERNAL VOICE / THOUGHT PATTERNS
    # How does this character's mind work? What do they tell themselves?
    # =========================================================================
    internal_voice: Dict[str, Any] = field(default_factory=lambda: {
        "self_talk_tone": "",  # e.g., "Critical, constantly measuring her worth"
        "recurring_thoughts": [],  # e.g., ["Am I enough?", "What does he really want?"]
        "coping_mechanisms": [],  # e.g., ["Retreats into performance mode when vulnerable"]
        "blind_spots": []  # e.g., ["Cannot see her strategic mind is valuable"]
    })

    # =========================================================================
    # SPEECH PATTERNS
    # Not just what they say but how - for dialogue generation
    # =========================================================================
    speech: Dict[str, Any] = field(default_factory=lambda: {
        "vocabulary_level": "",  # e.g., "Refined, educated in poetry and arts"
        "sentence_structure": "",  # e.g., "Measured, deliberate pauses"
        "verbal_habits": [],  # e.g., ["Deflects direct questions about feelings"]
        "topics_avoided": [],  # e.g., ["Her childhood", "What happens after clients leave"]
        "topics_gravitated": [],  # e.g., ["Beauty, nature", "Hypotheticals about 'another life'"]
        "speech_rhythm": "",  # e.g., "Slow and deliberate, or rapid and nervous"
        "accent_dialect": "",  # Any regional or class-based speech patterns
        "filler_words": [],  # e.g., ["perhaps", "one might say"]
        "oath_expressions": []  # What they say when surprised, angry, etc.
    })

    # =========================================================================
    # PHYSICAL LANGUAGE
    # For movement and gesture generation in storyboards/animation
    # =========================================================================
    physicality: Dict[str, Any] = field(default_factory=lambda: {
        "baseline_posture": "",  # e.g., "Elegant, trained - spine straight, movements economical"
        "gait": "",  # How they walk
        "nervous_tells": [],  # e.g., ["Touches her hairpin", "Looks toward the window"]
        "confident_tells": [],  # e.g., ["Slows movements deliberately", "Holds eye contact"]
        "how_they_enter_a_room": "",  # e.g., "Glides, aware of being watched"
        "how_they_sit": "",  # e.g., "Kneels formally but with practiced ease"
        "how_they_stand": "",  # Neutral standing posture
        "touch_patterns": "",  # e.g., "Strategic - touches others purposefully"
        "personal_space": "",  # How close they let others get
        "eye_contact_patterns": "",  # e.g., "Avoids direct eye contact when lying"
        "hand_gestures": "",  # Characteristic hand movements
        "facial_baseline": ""  # Default facial expression
    })

    # =========================================================================
    # DECISION HEURISTICS
    # When the agent faces a choice - for behavior generation
    # =========================================================================
    decision_making: Dict[str, Any] = field(default_factory=lambda: {
        "primary_value": "",  # e.g., "Self-preservation through control"
        "secondary_value": "",  # e.g., "Dignity"
        "when_threatened": "",  # e.g., "Deploys charm as a shield"
        "when_vulnerable": "",  # e.g., "Masks with performance, only shows truth in solitude"
        "when_cornered": "",  # How they react when all options seem bad
        "risk_tolerance": "",  # e.g., "Will take calculated gambles if..."
        "trust_threshold": "",  # e.g., "Very high - assumes ulterior motives"
        "loyalty_hierarchy": [],  # Who/what do they prioritize? In order
        "moral_lines": [],  # What they WILL NOT do, even under pressure
        "temptations": []  # What could make them compromise their values
    })

    # =========================================================================
    # EMOTIONAL STATE TRACKING
    # For dynamic roleplay across scenes - baseline emotional profile
    # =========================================================================
    emotional_baseline: Dict[str, Any] = field(default_factory=lambda: {
        "default_mood": "",  # e.g., "Melancholic longing masked by composure"
        "stress_response": "",  # e.g., "Becomes more controlled, not less"
        "joy_expression": "",  # e.g., "Rare, genuine smiles only when..."
        "anger_expression": "",  # e.g., "Cold, precise - weaponized politeness"
        "fear_expression": "",  # How fear manifests
        "sadness_expression": "",  # How sadness manifests
        "emotional_volatility": "",  # How quickly emotions change
        "emotional_recovery": "",  # How long to return to baseline
        "suppression_style": ""  # How they hide emotions when they need to
    })

    # =========================================================================
    # PHYSIOLOGICAL/PSYCHOLOGICAL TELLS
    # Observable physical behaviors for each emotional state
    # Expanded to 25+ emotions for nuanced agent embodiment
    # =========================================================================
    emotional_tells: Dict[str, str] = field(default_factory=lambda: {
        # Basic emotions
        "happiness": "",
        "sadness": "",
        "anger": "",
        "fear": "",
        "surprise": "",
        "disgust": "",
        # Complex emotions
        "annoyance": "",
        "intrigue": "",
        "excitement": "",
        "embarrassment": "",
        "nervousness": "",
        "confidence": "",
        "vulnerability": "",
        "joy": "",
        # Interpersonal emotions
        "attraction": "",  # Initial attraction/interest
        "crush": "",  # Deeper romantic feelings developing
        "intimacy": "",  # Emotional/physical closeness
        "jealousy": "",
        "envy": "",
        "contempt": "",
        "admiration": "",
        "gratitude": "",
        # Achievement/Status emotions
        "pride": "",
        "shame": "",
        "guilt": "",
        "defeat": "",  # Losing, giving up
        "triumph": "",  # Victory, winning
        # Cognitive states
        "focus": "",  # Deep concentration
        "confusion": "",
        "curiosity": "",
        "boredom": "",
        "frustration": "",
        # Social emotions
        "loneliness": "",
        "belonging": "",
        "rejection": "",
        "acceptance": ""
    })

    # =========================================================================
    # RELATIONSHIPS
    # Dynamic relationship states with other characters
    # =========================================================================
    relationships: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        # Format: "CHAR_TAG": {"type": "", "history": "", "current_state": "", "hidden_feelings": ""}
    })

    # =========================================================================
    # CHARACTER ARC
    # Story-level transformation tracking
    # =========================================================================
    arc: Dict[str, Any] = field(default_factory=lambda: {
        "want": "",  # External goal
        "need": "",  # Internal growth required
        "flaw": "",  # What holds them back
        "arc_type": "",  # positive, negative, flat
        "ghost": "",  # Past trauma/event that shaped them
        "lie_believed": "",  # False belief they hold
        "truth_to_learn": ""  # What they need to understand
    })

    # =========================================================================
    # WORLD INTEGRATION
    # How this character fits within the time period, genre, and cultural context
    # =========================================================================
    world_context: Dict[str, Any] = field(default_factory=lambda: {
        "social_class": "",  # Their position in society
        "occupation_details": "",  # Specifics of their role
        "cultural_background": "",  # Traditions, customs they follow
        "education_level": "",  # Formal/informal education
        "time_period_authenticity": "",  # How their behavior fits the era
        "genre_role": "",  # How they function in the story's genre
        "historical_influences": [],  # Real historical parallels
        "anachronism_notes": ""  # Things to avoid for period accuracy
    })

    # Legacy fields (deprecated - kept for backward compatibility)
    psychology: str = ""
    speech_patterns: str = ""
    personality: str = ""
    speech_style: str = ""
    literacy_level: str = ""
    world_attributes: str = ""


@dataclass
class LocationPhysical:
    """Physical attributes of a location."""
    architecture: str = ""
    dimensions: str = ""
    materials: str = ""
    key_features: List[str] = field(default_factory=list)


@dataclass
class LocationSensory:
    """Sensory details of a location."""
    visual: str = ""
    auditory: str = ""
    olfactory: str = ""
    tactile: str = ""


@dataclass
class LocationAtmosphere:
    """Atmospheric qualities of a location."""
    mood: str = ""
    lighting: str = ""
    emotional_quality: str = ""
    danger_level: str = ""


@dataclass
class LocationTimePeriodDetails:
    """Time period specific details for a location."""
    era_specific_elements: List[str] = field(default_factory=list)
    social_function: str = ""
    who_frequents: List[str] = field(default_factory=list)
    economic_role: str = ""


@dataclass
class LocationNarrativeFunction:
    """Narrative function of a location in the story."""
    story_role: str = ""
    emotional_resonance: str = ""
    key_scenes_here: List[str] = field(default_factory=list)


@dataclass
class LocationProfile:
    """Complete location profile from research (expanded schema)."""
    tag: str
    name: str
    description: str = ""

    # Expanded schema fields
    physical: Optional[LocationPhysical] = None
    sensory: Optional[LocationSensory] = None
    atmosphere: Optional[LocationAtmosphere] = None
    time_period_details: Optional[LocationTimePeriodDetails] = None
    narrative_function: Optional[LocationNarrativeFunction] = None

    # Cardinal direction views for directional tags [LOC_*_DIR_N/E/S/W]
    directional_views: Dict[str, str] = field(default_factory=dict)  # north, east, south, west

    # Props present at this location
    props_present: List[str] = field(default_factory=list)

    # Legacy fields (for backward compatibility)
    architecture: str = ""  # Deprecated: use physical.architecture
    lighting: str = ""  # Deprecated: use atmosphere.lighting
    sounds: str = ""  # Deprecated: use sensory.auditory
    world_attributes: str = ""  # Deprecated: use time_period_details


@dataclass
class PropPhysical:
    """Physical attributes of a prop."""
    materials: str = ""
    dimensions: str = ""
    condition: str = ""
    craftsmanship: str = ""


@dataclass
class PropSensory:
    """Sensory details of a prop."""
    visual: str = ""
    auditory: str = ""
    tactile: str = ""


@dataclass
class PropSignificance:
    """Narrative significance of a prop."""
    narrative_function: str = ""
    symbolic_meaning: str = ""
    emotional_weight: str = ""


@dataclass
class PropTimePeriodDetails:
    """Time period specific details for a prop."""
    historical_context: str = ""
    social_implications: str = ""
    cultural_weight: str = ""


@dataclass
class PropAssociations:
    """Character and location associations for a prop."""
    primary_character: str = ""
    secondary_characters: List[str] = field(default_factory=list)
    location: str = ""


@dataclass
class PropProfile:
    """Complete prop profile from research (expanded schema)."""
    tag: str
    name: str
    appearance: str = ""  # Legacy field

    # Expanded schema fields
    physical: Optional[PropPhysical] = None
    sensory: Optional[PropSensory] = None
    significance: Optional[PropSignificance] = None
    time_period_details: Optional[PropTimePeriodDetails] = None
    associations: Optional[PropAssociations] = None
    history: str = ""

    # Legacy fields (for backward compatibility)
    significance_legacy: str = ""  # Deprecated: use significance object
    associations_legacy: List[str] = field(default_factory=list)  # Deprecated: use associations object
    world_attributes: str = ""  # Deprecated: use time_period_details


@dataclass
class WorldBibleOutput:
    """Complete world bible output."""
    characters: List[CharacterProfile] = field(default_factory=list)
    locations: List[LocationProfile] = field(default_factory=list)
    props: List[PropProfile] = field(default_factory=list)
    global_context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# RESEARCH AGENTS
# =============================================================================

class CharacterResearchAgent(ProposalAgent):
    """Research agent for character tags."""

    RESEARCH_FOCUSES = {
        "identity": "Core identity, name, role, age, ethnicity, backstory, defining_moment",
        "psychology": "Internal voice, fears, desires, coping mechanisms, blind_spots, PERSONALITY TRAITS",
        "speech": "Dialogue patterns, vocabulary, SPEECH STYLE, LITERACY LEVEL, verbal_habits, topics_avoided",
        "physicality": "Movement, gestures, physical presence, body language, nervous_tells, confident_tells",
        "decisions": "Decision heuristics, relationships, moral compass, risk_tolerance, trust_threshold",
        "world_context": "How this character fits within the time period, genre, and cultural context"
    }

    def __init__(self, agent_id: str, focus: str, llm_caller: Callable):
        super().__init__(agent_id)
        self.focus = focus
        self.llm_caller = llm_caller
        self.focus_description = self.RESEARCH_FOCUSES.get(focus, "")

    def _build_world_context(self, context: Dict[str, Any]) -> str:
        """Build full world context section for prompt injection."""
        world_details = context.get('world_details', {})
        if not world_details:
            # Fallback to basic fields
            return f"""TIME PERIOD: {context.get('time_period', 'contemporary')}
GENRE: {context.get('genre', '')}
SETTING: {context.get('setting', '')}"""

        parts = ["=== WORLD CONTEXT (Use this for ALL decisions) ==="]

        # Time Period
        time_period = world_details.get('time_period', {})
        if time_period:
            parts.append(f"\n## TIME PERIOD")
            parts.append(f"Era: {time_period.get('era', context.get('time_period', 'Not specified'))}")
            if time_period.get('historical_events'):
                parts.append(f"Historical Events: {', '.join(time_period['historical_events'])}")
            if time_period.get('technology_level'):
                parts.append(f"Technology: {time_period['technology_level']}")

        # Cultural Context
        cultural = world_details.get('cultural_context', {})
        if cultural:
            parts.append(f"\n## CULTURAL CONTEXT")
            if cultural.get('social_hierarchy'):
                hierarchy = cultural['social_hierarchy']
                if isinstance(hierarchy, list):
                    parts.append(f"Social Hierarchy: {' > '.join(hierarchy)}")
            if cultural.get('gender_roles'):
                parts.append(f"Gender Roles: {cultural['gender_roles']}")
            if cultural.get('taboos'):
                parts.append(f"Taboos: {', '.join(cultural['taboos'])}")
            if cultural.get('customs'):
                parts.append(f"Customs: {', '.join(cultural['customs'])}")
            if cultural.get('language_register'):
                lang = cultural['language_register']
                if isinstance(lang, dict):
                    parts.append(f"Language - Formal: {lang.get('formal', '')}")
                    parts.append(f"Language - Informal: {lang.get('informal', '')}")

        # Aesthetic Context
        aesthetic = world_details.get('aesthetic_context', {})
        if aesthetic:
            parts.append(f"\n## AESTHETIC CONTEXT")
            if aesthetic.get('fashion'):
                parts.append(f"Fashion: {aesthetic['fashion']}")
            if aesthetic.get('color_symbolism'):
                colors = aesthetic['color_symbolism']
                if isinstance(colors, dict):
                    color_str = "; ".join([f"{k}: {v}" for k, v in colors.items()])
                    parts.append(f"Color Symbolism: {color_str}")

        return "\n".join(parts)

    async def generate_proposal(
        self,
        context: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Proposal:
        """Generate character research proposal with full world context."""
        tag = context.get("tag", "")
        pitch = context.get("pitch_text", "")
        genre = context.get('genre', '')

        visual_style = context.get('visual_style', 'live_action')
        style_notes = context.get('style_notes', '')

        # Build full world context
        world_context = self._build_world_context(context)

        # Build focus-specific instructions
        focus_instructions = ""
        if self.focus == "identity":
            focus_instructions = """
For IDENTITY focus, include:
- age, ethnicity, social_class, education
- backstory, defining_moment
- All details MUST be authentic to the time period and cultural context above
"""
        elif self.focus == "psychology":
            focus_instructions = """
For PSYCHOLOGY focus, include:
- internal_voice: self_talk_tone, recurring_thoughts, coping_mechanisms, blind_spots
- PERSONALITY: Core personality traits (3-5 key traits)
- inner_critic_voice, inner_hope_voice
"""
        elif self.focus == "speech":
            focus_instructions = """
For SPEECH focus, include:
- vocabulary_level, sentence_structure, speech_rhythm
- verbal_habits, topics_avoided, topics_gravitated
- accent_dialect, filler_words, oath_expressions
- example_dialogue (2-3 lines showing their voice)
- SPEECH_STYLE: How they speak (formal/casual, poetic/direct, etc.)
- LITERACY_LEVEL: Education level affecting vocabulary
"""
        elif self.focus == "physicality":
            focus_instructions = """
For PHYSICALITY focus, include:
- baseline_posture, gait, movement_style
- nervous_tells (3-5 specific behaviors)
- confident_tells (3-5 specific behaviors)
- how_they_enter_a_room, how_they_sit, how_they_stand
- touch_patterns, personal_space, eye_contact_patterns
- hand_gestures, facial_baseline
"""
        elif self.focus == "decisions":
            focus_instructions = """
For DECISIONS focus, include:
- primary_value, secondary_value
- when_threatened, when_vulnerable, when_cornered
- risk_tolerance, trust_threshold
- loyalty_hierarchy, moral_lines, temptations
"""
        elif self.focus == "world_context":
            focus_instructions = """
For WORLD CONTEXT focus, include:
- social_position within the world's hierarchy
- cultural_constraints they must navigate
- period_specific_behaviors (4-6 specific behaviors)
- historical_parallels (similar roles in history)
- anachronisms_to_avoid (4-6 things to NOT include)
"""

        prompt = f"""Research the following character from a {self.focus} perspective.

CHARACTER TAG: {tag}

{world_context}

=== STORY CONTEXT ===
GENRE: {genre}
VISUAL STYLE: {visual_style}
{f'STYLE NOTES: {style_notes}' if style_notes else ''}
THEMES: {context.get('themes', '')}

=== PITCH ===
{pitch}

=== YOUR RESEARCH FOCUS: {self.focus_description} ===
{focus_instructions}

CRITICAL: All character details MUST be authentic to the time period and cultural context above.
Avoid anachronisms. Reference specific historical parallels where appropriate.

Provide detailed research on this character's {self.focus}.
Format as structured JSON with clear sections."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt=f"You are a character researcher focusing on {self.focus}. All output must be period-accurate.",
            function=LLMFunction.RESEARCH
        )

        return Proposal(
            agent_id=self.agent_id,
            content=response,
            metadata={"focus": self.focus, "tag": tag}
        )


class LocationResearchAgent(ProposalAgent):
    """Research agent for location tags."""

    RESEARCH_FOCUSES = {
        "physical": "Architecture, dimensions, materials, key_features, construction",
        "sensory": "Visual, auditory, olfactory, tactile sensory details",
        "atmosphere": "Mood, lighting, emotional_quality, danger_level",
        "directional": "Views from N/E/S/W with spatial anchors and landmarks"
    }

    def __init__(self, agent_id: str, focus: str, llm_caller: Callable):
        super().__init__(agent_id)
        self.focus = focus
        self.llm_caller = llm_caller
        self.focus_description = self.RESEARCH_FOCUSES.get(focus, "")

    def _build_world_context(self, context: Dict[str, Any]) -> str:
        """Build full world context section for prompt injection."""
        world_details = context.get('world_details', {})
        if not world_details:
            return f"TIME PERIOD: {context.get('time_period', 'contemporary')}"

        parts = ["=== WORLD CONTEXT ==="]

        # Time Period
        time_period = world_details.get('time_period', {})
        if time_period:
            parts.append(f"Era: {time_period.get('era', 'Not specified')}")
            if time_period.get('technology_level'):
                parts.append(f"Technology: {time_period['technology_level']}")

        # Economic Context (important for locations)
        economic = world_details.get('economic_context', {})
        if economic:
            if economic.get('currency'):
                parts.append(f"Currency: {economic['currency']}")
            if economic.get('trade_goods'):
                parts.append(f"Trade Goods: {', '.join(economic['trade_goods'])}")
            if economic.get('class_markers'):
                markers = economic['class_markers']
                if isinstance(markers, dict):
                    parts.append(f"Class Markers - Wealthy: {markers.get('wealthy', '')}")
                    parts.append(f"Class Markers - Poor: {markers.get('poor', '')}")

        # Aesthetic Context
        aesthetic = world_details.get('aesthetic_context', {})
        if aesthetic:
            if aesthetic.get('architecture'):
                parts.append(f"Architecture Style: {aesthetic['architecture']}")
            if aesthetic.get('materials'):
                parts.append(f"Common Materials: {aesthetic['materials']}")

        return "\n".join(parts)

    async def generate_proposal(
        self,
        context: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Proposal:
        """Generate location research proposal with full world context."""
        tag = context.get("tag", "")
        pitch = context.get("pitch_text", "")

        visual_style = context.get('visual_style', 'live_action')
        style_notes = context.get('style_notes', '')

        # Build full world context
        world_context = self._build_world_context(context)

        # Build focus-specific instructions
        focus_instructions = ""
        if self.focus == "physical":
            focus_instructions = """
For PHYSICAL focus, include:
- architecture: Architectural style and construction
- dimensions: Size and scale
- materials: Building materials authentic to the time period
- key_features: 4-6 distinctive features (list)
- All details MUST be authentic to the time period above
"""
        elif self.focus == "sensory":
            focus_instructions = """
For SENSORY focus, include:
- visual: What you see (colors, textures, light)
- auditory: What you hear (ambient sounds, voices)
- olfactory: What you smell
- tactile: What you feel (temperature, textures)
"""
        elif self.focus == "atmosphere":
            focus_instructions = """
For ATMOSPHERE focus, include:
- mood: Overall emotional tone
- lighting: Natural and artificial light sources
- emotional_quality: How the space makes people feel
- danger_level: Safety perception (safe/neutral/tense/dangerous)
"""
        elif self.focus == "directional":
            focus_instructions = """
For DIRECTIONAL focus, include views from each cardinal direction:
- north: What is visible looking North (include spatial anchors)
- east: What is visible looking East
- south: What is visible looking South
- west: What is visible looking West

Each view should include:
- Primary focal point
- Spatial anchors (furniture, architectural features)
- Lighting from that direction
- Distance markers (near/mid/far elements)
"""

        prompt = f"""Research the following location from a {self.focus} perspective.

LOCATION TAG: {tag}

{world_context}

=== STORY CONTEXT ===
VISUAL STYLE: {visual_style}
{f'STYLE NOTES: {style_notes}' if style_notes else ''}

=== PITCH ===
{pitch}

=== YOUR RESEARCH FOCUS: {self.focus_description} ===
{focus_instructions}

CRITICAL: All location details MUST be authentic to the time period and cultural context.
Avoid anachronisms. Use period-appropriate materials, construction, and furnishings.

Provide detailed research on this location's {self.focus}.
Format as structured JSON."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt=f"You are a location researcher focusing on {self.focus}. All output must be period-accurate.",
            function=LLMFunction.RESEARCH
        )

        return Proposal(
            agent_id=self.agent_id,
            content=response,
            metadata={"focus": self.focus, "tag": tag}
        )


class PropResearchAgent(ProposalAgent):
    """Research agent for prop tags."""

    RESEARCH_FOCUSES = {
        "physical": "Materials, dimensions, condition, craftsmanship, visual details",
        "sensory": "Visual, auditory, tactile sensory details",
        "significance": "Narrative function, symbolic meaning, emotional weight",
        "associations": "Character associations, location, history"
    }

    def __init__(self, agent_id: str, focus: str, llm_caller: Callable):
        super().__init__(agent_id)
        self.focus = focus
        self.llm_caller = llm_caller
        self.focus_description = self.RESEARCH_FOCUSES.get(focus, "")

    def _build_world_context(self, context: Dict[str, Any]) -> str:
        """Build full world context section for prompt injection."""
        world_details = context.get('world_details', {})
        if not world_details:
            return f"TIME PERIOD: {context.get('time_period', 'contemporary')}"

        parts = ["=== WORLD CONTEXT ==="]

        # Time Period
        time_period = world_details.get('time_period', {})
        if time_period:
            parts.append(f"Era: {time_period.get('era', 'Not specified')}")
            if time_period.get('technology_level'):
                parts.append(f"Technology: {time_period['technology_level']}")

        # Economic Context (important for props)
        economic = world_details.get('economic_context', {})
        if economic:
            if economic.get('trade_goods'):
                parts.append(f"Trade Goods: {', '.join(economic['trade_goods'])}")
            if economic.get('class_markers'):
                markers = economic['class_markers']
                if isinstance(markers, dict):
                    parts.append(f"Wealth Markers: {markers.get('wealthy', '')}")

        # Aesthetic Context
        aesthetic = world_details.get('aesthetic_context', {})
        if aesthetic:
            if aesthetic.get('materials'):
                parts.append(f"Common Materials: {aesthetic['materials']}")
            if aesthetic.get('color_symbolism'):
                colors = aesthetic['color_symbolism']
                if isinstance(colors, dict):
                    color_str = "; ".join([f"{k}: {v}" for k, v in colors.items()])
                    parts.append(f"Color Symbolism: {color_str}")

        return "\n".join(parts)

    async def generate_proposal(
        self,
        context: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Proposal:
        """Generate prop research proposal with full world context."""
        tag = context.get("tag", "")
        pitch = context.get("pitch_text", "")

        visual_style = context.get('visual_style', 'live_action')
        style_notes = context.get('style_notes', '')

        # Build full world context
        world_context = self._build_world_context(context)

        # Build focus-specific instructions
        focus_instructions = ""
        if self.focus == "physical":
            focus_instructions = """
For PHYSICAL focus, include:
- materials: What the prop is made of (period-authentic)
- dimensions: Size and scale
- condition: New/worn/damaged/antique
- craftsmanship: Quality of construction
- visual: Detailed visual description
"""
        elif self.focus == "sensory":
            focus_instructions = """
For SENSORY focus, include:
- visual: Colors, textures, reflections
- auditory: Sounds it makes when used/moved
- tactile: How it feels to touch (weight, texture, temperature)
"""
        elif self.focus == "significance":
            focus_instructions = """
For SIGNIFICANCE focus, include:
- narrative_function: Role in the story
- symbolic_meaning: What it represents thematically
- emotional_weight: Emotional associations
"""
        elif self.focus == "associations":
            focus_instructions = """
For ASSOCIATIONS focus, include:
- primary_character: Main character associated with this prop (as TAG)
- secondary_characters: Other characters who interact with it (as TAGs)
- location: Where this prop is typically found (as TAG)
- history: Origin and journey of this prop
"""

        prompt = f"""Research the following prop from a {self.focus} perspective.

PROP TAG: {tag}

{world_context}

=== STORY CONTEXT ===
VISUAL STYLE: {visual_style}
{f'STYLE NOTES: {style_notes}' if style_notes else ''}

=== PITCH ===
{pitch}

=== YOUR RESEARCH FOCUS: {self.focus_description} ===
{focus_instructions}

CRITICAL: All prop details MUST be authentic to the time period and cultural context.
Avoid anachronisms. Use period-appropriate materials and craftsmanship.

Provide detailed research on this prop's {self.focus}.
Format as structured JSON."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt=f"You are a prop researcher focusing on {self.focus}. All output must be period-accurate.",
            function=LLMFunction.RESEARCH
        )

        return Proposal(
            agent_id=self.agent_id,
            content=response,
            metadata={"focus": self.focus, "tag": tag}
        )


# =============================================================================
# RESEARCH JUDGES
# =============================================================================

class CharacterResearchJudge(JudgeAgent):
    """Judge for character research proposals."""

    CRITERIA = {
        "authenticity": "Psychological authenticity and believability",
        "consistency": "Internal consistency across all aspects",
        "completeness": "Story service and profile completeness"
    }

    def __init__(self, judge_id: str, criterion: str, llm_caller: Callable):
        super().__init__(judge_id, criterion)
        self.llm_caller = llm_caller
        self.criterion_description = self.CRITERIA.get(criterion, "")

    async def rank_proposals(
        self,
        proposals: List[Proposal],
        context: Dict[str, Any]
    ) -> JudgeRanking:
        """Rank character research proposals."""
        proposals_text = "\n\n".join([
            f"=== PROPOSAL {p.agent_id} ({p.metadata.get('focus', '')}) ===\n{p.content}"
            for p in proposals
        ])

        prompt = f"""Judge these character research proposals on: {self.criterion}

{self.criterion_description}

PROPOSALS:
{proposals_text}

Rank from best to worst and score 1-10.
Respond in JSON: {{"rankings": [...], "scores": {{...}}, "reasoning": "..."}}"""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt=f"You are a {self.criterion} judge for character research.",
            function=LLMFunction.STORY_ANALYSIS
        )

        try:
            result = json.loads(response)
            return JudgeRanking(
                judge_id=self.judge_id,
                criterion=self.criterion,
                rankings=result.get("rankings", []),
                scores=result.get("scores", {}),
                reasoning=result.get("reasoning", "")
            )
        except json.JSONDecodeError:
            return JudgeRanking(
                judge_id=self.judge_id,
                criterion=self.criterion,
                rankings=[p.agent_id for p in proposals],
                scores={p.agent_id: 5.0 for p in proposals}
            )


# =============================================================================
# PHYSIOLOGICAL TELLS ASSEMBLY (Claude Haiku)
# =============================================================================

# Emotions for physiological tells
EMOTIONAL_TELLS_EMOTIONS = [
    "annoyance",
    "intrigue",
    "excitement",
    "embarrassment",
    "nervousness",
    "confidence",
    "anger",
    "fear",
    "vulnerability",
    "joy"
]


class PhysiologicalTellsAgent(ProposalAgent):
    """
    Proposal agent for generating physiological tells for a specific emotion.
    Uses hardcoded Claude Haiku for cost efficiency.
    """

    def __init__(self, agent_id: str, emotion: str, haiku_caller: Callable):
        super().__init__(agent_id)
        self.emotion = emotion
        self.haiku_caller = haiku_caller  # Hardcoded to Haiku

    async def generate_proposal(
        self,
        context: Dict[str, Any],
        constraints: Dict[str, Any] = None
    ) -> Proposal:
        """Generate physiological tell proposal for this emotion."""
        character_name = context.get("character_name", "")
        character_profile = context.get("character_profile", "")
        time_period = context.get("time_period", "")
        genre = context.get("genre", "")

        prompt = f"""Define the PHYSIOLOGICAL TELLS for {character_name} when experiencing {self.emotion.upper()}.

CHARACTER PROFILE:
{character_profile}

TIME PERIOD: {time_period}
GENRE: {genre}

Physiological tells are OBSERVABLE PHYSICAL BEHAVIORS that express internal emotional states.
These are NOT verbal - they are body language, facial expressions, posture changes, and physical mannerisms.

For {self.emotion.upper()}, describe:
1. FACIAL EXPRESSION - What happens to their face? (eyes, mouth, brow, jaw)
2. BODY POSTURE - How does their posture change?
3. HAND/ARM BEHAVIOR - What do their hands do?
4. BREATHING/VOICE - How does their breathing or voice quality change?
5. UNIQUE TELL - What is ONE distinctive physical behavior unique to this character?

Consider:
- Their cultural background and time period (what expressions are appropriate?)
- Their personality (do they suppress or express openly?)
- Their role (protagonist, antagonist, etc.)

Output a 2-3 sentence description of how {character_name} physically expresses {self.emotion}.
Be specific and visual - these descriptions will be used for storyboard generation."""

        response = await self.haiku_caller(prompt)

        return Proposal(
            agent_id=self.agent_id,
            content=response,
            metadata={"emotion": self.emotion, "character": character_name}
        )


class PhysiologicalTellsJudge(JudgeAgent):
    """Judge for physiological tells proposals. Uses Claude Haiku."""

    CRITERIA = {
        "authenticity": "Does this match the character's personality and background?",
        "visual_clarity": "Is this visually describable for storyboards?",
        "cultural_fit": "Does this fit the time period and genre?"
    }

    def __init__(self, judge_id: str, criterion: str, haiku_caller: Callable):
        super().__init__(judge_id, criterion)
        self.haiku_caller = haiku_caller
        self.criterion_description = self.CRITERIA.get(criterion, "")

    async def rank_proposals(
        self,
        proposals: List[Proposal],
        context: Dict[str, Any]
    ) -> JudgeRanking:
        """Rank physiological tells proposals."""
        proposals_text = "\n\n".join([
            f"=== {p.metadata.get('emotion', '').upper()} ===\n{p.content}"
            for p in proposals
        ])

        prompt = f"""Judge these physiological tells on: {self.criterion}

{self.criterion_description}

CHARACTER: {context.get('character_name', '')}
TIME PERIOD: {context.get('time_period', '')}

PROPOSALS:
{proposals_text}

Score each emotion's tell from 1-10 based on {self.criterion}.
Respond in JSON: {{"scores": {{"emotion": score, ...}}, "reasoning": "brief explanation"}}"""

        response = await self.haiku_caller(prompt)

        try:
            result = json.loads(response)
            scores = result.get("scores", {})
            # Convert to agent_id based scores
            agent_scores = {}
            for p in proposals:
                emotion = p.metadata.get("emotion", "")
                agent_scores[p.agent_id] = scores.get(emotion, 5.0)

            # Rank by score
            ranked = sorted(agent_scores.items(), key=lambda x: x[1], reverse=True)

            return JudgeRanking(
                judge_id=self.judge_id,
                criterion=self.criterion,
                rankings=[r[0] for r in ranked],
                scores=agent_scores,
                reasoning=result.get("reasoning", "")
            )
        except json.JSONDecodeError:
            return JudgeRanking(
                judge_id=self.judge_id,
                criterion=self.criterion,
                rankings=[p.agent_id for p in proposals],
                scores={p.agent_id: 5.0 for p in proposals}
            )


class PhysiologicalTellsSynthesizer:
    """Synthesizer for physiological tells. Uses Claude Haiku."""

    def __init__(self, haiku_caller: Callable):
        self.haiku_caller = haiku_caller

    async def synthesize(
        self,
        proposals: List[Proposal],
        calculator_result: Any,
        context: Dict[str, Any]
    ) -> SynthesisResult:
        """Synthesize best tells into final dict."""
        # Build tells dict from proposals
        tells = {}
        for p in proposals:
            emotion = p.metadata.get("emotion", "")
            if emotion:
                tells[emotion] = p.content.strip()

        # Return as JSON
        return SynthesisResult(
            content=json.dumps(tells),
            metadata={"character": context.get("character_name", "")}
        )


# =============================================================================
# WORLD BIBLE PIPELINE
# =============================================================================

@dataclass
class WorldBibleInput:
    """Input for World Bible Pipeline."""
    validated_tags: Dict[str, List[str]]  # character_tags, location_tags, prop_tags
    pitch_text: str
    time_period: str = ""
    setting: str = ""
    genre: str = ""
    media_type: str = "standard"
    visual_style: str = "live_action"  # live_action, anime, animation_2d, animation_3d, mixed_reality
    style_notes: str = ""  # Custom style instructions from user
    preserved_tags: Set[str] = field(default_factory=set)  # Tags to preserve from existing config
    existing_config: Dict[str, Any] = field(default_factory=dict)  # Existing world_config.json data
    world_details: Dict[str, Any] = field(default_factory=dict)  # Top-level world context (time_period, cultural_context, etc.)
    themes: str = ""  # Story themes for context


class WorldBiblePipeline(BasePipeline):
    """
    World Bible Research Pipeline.

    Implements chunked-per-tag architecture where each tag gets its own
    dedicated research pipeline running in parallel.
    """

    def __init__(self, llm_caller: Callable):
        super().__init__("World Bible Research")
        self.llm_caller = llm_caller

        # Create hardcoded Haiku caller for physiological tells (cost efficiency)
        self._haiku_client = None  # Lazy initialization

    async def _haiku_caller(self, prompt: str) -> str:
        """Hardcoded Claude Haiku caller for physiological tells assembly."""
        if self._haiku_client is None:
            from greenlight.llm.api_clients import AnthropicClient
            self._haiku_client = AnthropicClient()

        response = await asyncio.to_thread(
            self._haiku_client.generate_text,
            prompt,
            system="You are a character behavior specialist focusing on physical expressions of emotion.",
            max_tokens=500,  # Small output for efficiency
            model="claude-haiku-4-5-20251001"  # HARDCODED HAIKU
        )
        return response.text

    def _define_steps(self) -> None:
        """Define pipeline steps."""
        self._steps = [
            PipelineStep("character_research", "Research all character tags in parallel"),
            PipelineStep("location_research", "Research all location tags in parallel"),
            PipelineStep("prop_research", "Research all prop tags in parallel"),
            PipelineStep("global_context", "Research global context"),
            PipelineStep("global_assembly", "Merge all profiles into world bible"),
            PipelineStep("continuity_check", "Validate cross-tag relationships"),
        ]

    async def _execute_step(
        self,
        step: PipelineStep,
        input_data: Any,
        context: Dict[str, Any]
    ) -> Any:
        """Execute a single step."""
        if step.name == "character_research":
            return await self._research_characters(input_data, context)
        elif step.name == "location_research":
            return await self._research_locations(input_data, context)
        elif step.name == "prop_research":
            return await self._research_props(input_data, context)
        elif step.name == "global_context":
            return await self._research_global_context(input_data, context)
        elif step.name == "global_assembly":
            return await self._assemble_world_bible(input_data, context)
        elif step.name == "continuity_check":
            return await self._validate_continuity(input_data, context)
        return input_data

    async def _research_characters(
        self,
        input_data: WorldBibleInput,
        context: Dict[str, Any]
    ) -> WorldBibleInput:
        """Research all character tags in parallel."""
        character_tags = input_data.validated_tags.get("character_tags", [])

        if not character_tags:
            context["character_profiles"] = []
            return input_data

        preserved_profiles = []
        tags_to_research = []

        # Separate preserved tags from tags needing research
        for tag in character_tags:
            if tag in input_data.preserved_tags:
                # Load from existing config
                existing_char = self._get_preserved_character(tag, input_data.existing_config)
                if existing_char:
                    preserved_profiles.append(existing_char)
                    logger.info(f"Preserved character: {tag}")
                else:
                    tags_to_research.append(tag)
            else:
                tags_to_research.append(tag)

        # Run research for non-preserved characters in parallel
        if tags_to_research:
            tasks = [
                self._research_single_character(tag, input_data)
                for tag in tags_to_research
            ]
            profiles = await asyncio.gather(*tasks, return_exceptions=True)
            # Filter out exceptions
            valid_profiles = [p for p in profiles if not isinstance(p, Exception)]
        else:
            valid_profiles = []

        # Combine preserved and newly researched profiles
        all_profiles = preserved_profiles + valid_profiles
        context["character_profiles"] = all_profiles

        logger.info(f"Characters: {len(preserved_profiles)} preserved, {len(valid_profiles)} researched")
        return input_data

    def _get_preserved_character(self, tag: str, existing_config: Dict) -> Optional[CharacterProfile]:
        """Get a preserved character from existing config."""
        for char in existing_config.get("characters", []):
            if char.get("tag") == tag:
                return CharacterProfile(
                    tag=char.get("tag", ""),
                    name=char.get("name", ""),
                    role=char.get("role", ""),
                    age=char.get("age", ""),
                    ethnicity=char.get("ethnicity", ""),
                    backstory=char.get("backstory", ""),
                    visual_appearance=char.get("appearance", ""),
                    costume=char.get("costume", ""),
                    psychology=char.get("psychology", ""),
                    speech_patterns=char.get("speech_patterns", ""),
                    physicality=char.get("physicality", ""),
                    decision_heuristics=char.get("decision_heuristics", ""),
                    relationships=char.get("relationships", {}),
                    arc={"want": char.get("want", ""), "need": char.get("need", ""),
                         "flaw": char.get("flaw", ""), "arc_type": char.get("arc_type", "")}
                )
        return None

    async def _research_single_character(
        self,
        tag: str,
        input_data: WorldBibleInput
    ) -> CharacterProfile:
        """Research a single character using assembly pattern."""
        # Create research agents - now includes world_context focus
        focuses = ["identity", "psychology", "speech", "physicality", "decisions", "world_context"]
        proposal_agents = [
            CharacterResearchAgent(f"char_research_{i}", focus, self.llm_caller)
            for i, focus in enumerate(focuses)
        ]

        # Create judges
        judge_agents = [
            CharacterResearchJudge(f"char_judge_{i}", criterion, self.llm_caller)
            for i, criterion in enumerate(["authenticity", "consistency", "completeness"])
        ]

        # Create calculator and synthesizer
        calculator = AssemblyCalculatorAgent()
        synthesizer = AssemblySynthesizerAgent(self.llm_caller)

        # Create assembly pattern
        assembly = AssemblyPattern(
            proposal_agents=proposal_agents,
            judge_agents=judge_agents,
            calculator=calculator,
            synthesizer=synthesizer,
            config=AssemblyConfig(max_continuity_iterations=2)
        )

        # Execute assembly with full world context
        research_context = {
            "tag": tag,
            "pitch_text": input_data.pitch_text,
            "time_period": input_data.time_period,
            "setting": input_data.setting,
            "genre": input_data.genre,
            "visual_style": input_data.visual_style,
            "style_notes": input_data.style_notes,
            "world_details": input_data.world_details,  # Full world context for research agents
            "themes": input_data.themes
        }

        result = await assembly.execute(research_context)

        # Parse result into CharacterProfile
        profile = self._parse_character_profile(tag, result.content)

        # Generate physiological tells using Haiku assembly (cost efficient)
        logger.info(f"Generating physiological tells for {tag} using Claude Haiku...")
        profile.emotional_tells = await self._generate_physiological_tells(profile, input_data)

        return profile

    async def _generate_physiological_tells(
        self,
        profile: CharacterProfile,
        input_data: WorldBibleInput
    ) -> Dict[str, str]:
        """
        Generate physiological tells using assembly pattern with hardcoded Haiku.

        10 parallel agents (one per emotion) → 3 judges → Synthesizer
        """
        # Create 10 proposal agents (one per emotion)
        proposal_agents = [
            PhysiologicalTellsAgent(
                f"tells_agent_{i}",
                emotion,
                self._haiku_caller
            )
            for i, emotion in enumerate(EMOTIONAL_TELLS_EMOTIONS)
        ]

        # Create 3 judges (also using Haiku for cost efficiency)
        judge_agents = [
            PhysiologicalTellsJudge(f"tells_judge_{i}", criterion, self._haiku_caller)
            for i, criterion in enumerate(["authenticity", "visual_clarity", "cultural_fit"])
        ]

        # Calculator and Synthesizer
        calculator = AssemblyCalculatorAgent()
        synthesizer = PhysiologicalTellsSynthesizer(self._haiku_caller)

        # Create assembly
        assembly = AssemblyPattern(
            proposal_agents=proposal_agents,
            judge_agents=judge_agents,
            calculator=calculator,
            synthesizer=synthesizer,
            config=AssemblyConfig(max_continuity_iterations=1)  # Single pass
        )

        # Build context
        context = {
            "character_name": profile.name,
            "character_profile": f"""
Name: {profile.name}
Role: {profile.role}
Personality: {profile.psychology}
Physicality: {profile.physicality}
Age: {profile.age}
Ethnicity: {profile.ethnicity}
""",
            "time_period": input_data.time_period,
            "genre": input_data.genre
        }

        # Execute assembly
        result = await assembly.execute(context)

        # Parse result into emotional_tells dict
        try:
            return json.loads(result.content)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse emotional tells for {profile.name}")
            return {}

    def _parse_character_profile(self, tag: str, content: str) -> CharacterProfile:
        """Parse synthesis result into CharacterProfile."""
        try:
            data = json.loads(content)
            return CharacterProfile(
                tag=tag,
                name=data.get("name", tag.replace("CHAR_", "")),
                role=data.get("role", ""),
                age=data.get("age", ""),
                ethnicity=data.get("ethnicity", ""),
                backstory=data.get("backstory", ""),
                visual_appearance=data.get("visual_appearance", ""),
                costume=data.get("costume", ""),
                psychology=data.get("psychology", ""),
                speech_patterns=data.get("speech_patterns", ""),
                physicality=data.get("physicality", ""),
                decision_heuristics=data.get("decision_heuristics", ""),
                relationships=data.get("relationships", {}),
                arc=data.get("arc", {}),
                # NEW FIELDS for dialogue and roleplay
                personality=data.get("personality", ""),
                speech_style=data.get("speech_style", ""),
                literacy_level=data.get("literacy_level", ""),
                emotional_tells=data.get("emotional_tells", {}),
                world_attributes=data.get("world_attributes", "")
            )
        except json.JSONDecodeError:
            # Return basic profile with raw content
            return CharacterProfile(
                tag=tag,
                name=tag.replace("CHAR_", ""),
                role="",
                backstory=content
            )

    async def _research_locations(
        self,
        input_data: WorldBibleInput,
        context: Dict[str, Any]
    ) -> WorldBibleInput:
        """Research all location tags in parallel."""
        location_tags = input_data.validated_tags.get("location_tags", [])

        if not location_tags:
            context["location_profiles"] = []
            return input_data

        preserved_profiles = []
        tags_to_research = []

        # Separate preserved tags from tags needing research
        for tag in location_tags:
            if tag in input_data.preserved_tags:
                existing_loc = self._get_preserved_location(tag, input_data.existing_config)
                if existing_loc:
                    preserved_profiles.append(existing_loc)
                    logger.info(f"Preserved location: {tag}")
                else:
                    tags_to_research.append(tag)
            else:
                tags_to_research.append(tag)

        if tags_to_research:
            tasks = [
                self._research_single_location(tag, input_data)
                for tag in tags_to_research
            ]
            profiles = await asyncio.gather(*tasks, return_exceptions=True)
            valid_profiles = [p for p in profiles if not isinstance(p, Exception)]
        else:
            valid_profiles = []

        all_profiles = preserved_profiles + valid_profiles
        context["location_profiles"] = all_profiles

        logger.info(f"Locations: {len(preserved_profiles)} preserved, {len(valid_profiles)} researched")
        return input_data

    def _get_preserved_location(self, tag: str, existing_config: Dict) -> Optional[LocationProfile]:
        """Get a preserved location from existing config."""
        for loc in existing_config.get("locations", []):
            if loc.get("tag") == tag:
                return LocationProfile(
                    tag=loc.get("tag", ""),
                    name=loc.get("name", ""),
                    description=loc.get("description", ""),
                    architecture=loc.get("architecture", ""),
                    atmosphere=loc.get("atmosphere", ""),
                    directional_views=loc.get("directional_views", {}),
                    lighting=loc.get("lighting", ""),
                    sounds=loc.get("sounds", ""),
                    props_present=loc.get("props_present", [])
                )
        return None

    async def _research_single_location(
        self,
        tag: str,
        input_data: WorldBibleInput
    ) -> LocationProfile:
        """Research a single location using assembly pattern."""
        # Updated focuses to match new expanded schema
        focuses = ["physical", "sensory", "atmosphere", "directional"]
        proposal_agents = [
            LocationResearchAgent(f"loc_research_{i}", focus, self.llm_caller)
            for i, focus in enumerate(focuses)
        ]

        judge_agents = [
            CharacterResearchJudge(f"loc_judge_{i}", criterion, self.llm_caller)
            for i, criterion in enumerate(["authenticity", "consistency", "completeness"])
        ]

        calculator = AssemblyCalculatorAgent()
        synthesizer = AssemblySynthesizerAgent(self.llm_caller)

        assembly = AssemblyPattern(
            proposal_agents=proposal_agents,
            judge_agents=judge_agents,
            calculator=calculator,
            synthesizer=synthesizer
        )

        # Include full world context for location research
        research_context = {
            "tag": tag,
            "pitch_text": input_data.pitch_text,
            "time_period": input_data.time_period,
            "visual_style": input_data.visual_style,
            "style_notes": input_data.style_notes,
            "world_details": input_data.world_details  # Full world context for research agents
        }

        result = await assembly.execute(research_context)
        return self._parse_location_profile(tag, result.content)

    def _parse_location_profile(self, tag: str, content: str) -> LocationProfile:
        """Parse synthesis result into LocationProfile."""
        try:
            data = json.loads(content)
            return LocationProfile(
                tag=tag,
                name=data.get("name", tag.replace("LOC_", "")),
                description=data.get("description", ""),
                architecture=data.get("architecture", ""),
                atmosphere=data.get("atmosphere", ""),
                directional_views=data.get("directional_views", {}),
                lighting=data.get("lighting", ""),
                sounds=data.get("sounds", ""),
                props_present=data.get("props_present", []),
                world_attributes=data.get("world_attributes", "")
            )
        except json.JSONDecodeError:
            return LocationProfile(
                tag=tag,
                name=tag.replace("LOC_", ""),
                description=content
            )

    async def _research_props(
        self,
        input_data: WorldBibleInput,
        context: Dict[str, Any]
    ) -> WorldBibleInput:
        """Research all prop tags in parallel."""
        prop_tags = input_data.validated_tags.get("prop_tags", [])

        if not prop_tags:
            context["prop_profiles"] = []
            return input_data

        preserved_profiles = []
        tags_to_research = []

        # Separate preserved tags from tags needing research
        for tag in prop_tags:
            if tag in input_data.preserved_tags:
                existing_prop = self._get_preserved_prop(tag, input_data.existing_config)
                if existing_prop:
                    preserved_profiles.append(existing_prop)
                    logger.info(f"Preserved prop: {tag}")
                else:
                    tags_to_research.append(tag)
            else:
                tags_to_research.append(tag)

        if tags_to_research:
            tasks = [
                self._research_single_prop(tag, input_data)
                for tag in tags_to_research
            ]
            profiles = await asyncio.gather(*tasks, return_exceptions=True)
            valid_profiles = [p for p in profiles if not isinstance(p, Exception)]
        else:
            valid_profiles = []

        all_profiles = preserved_profiles + valid_profiles
        context["prop_profiles"] = all_profiles

        logger.info(f"Props: {len(preserved_profiles)} preserved, {len(valid_profiles)} researched")
        return input_data

    def _get_preserved_prop(self, tag: str, existing_config: Dict) -> Optional[PropProfile]:
        """Get a preserved prop from existing config."""
        for prop in existing_config.get("props", []):
            if prop.get("tag") == tag:
                return PropProfile(
                    tag=prop.get("tag", ""),
                    name=prop.get("name", ""),
                    description=prop.get("description", ""),
                    appearance=prop.get("appearance", ""),
                    significance=prop.get("significance", ""),
                    associated_characters=prop.get("associated_character", "").split(", ") if prop.get("associated_character") else []
                )
        return None

    async def _research_single_prop(
        self,
        tag: str,
        input_data: WorldBibleInput
    ) -> PropProfile:
        """Research a single prop using assembly pattern."""
        # Updated focuses to match new expanded schema
        focuses = ["physical", "sensory", "significance", "associations"]
        proposal_agents = [
            PropResearchAgent(f"prop_research_{i}", focus, self.llm_caller)
            for i, focus in enumerate(focuses)
        ]

        # Simpler judging for props (2 judges)
        judge_agents = [
            CharacterResearchJudge(f"prop_judge_{i}", criterion, self.llm_caller)
            for i, criterion in enumerate(["authenticity", "completeness"])
        ]

        calculator = AssemblyCalculatorAgent()
        synthesizer = AssemblySynthesizerAgent(self.llm_caller)

        assembly = AssemblyPattern(
            proposal_agents=proposal_agents,
            judge_agents=judge_agents,
            calculator=calculator,
            synthesizer=synthesizer
        )

        # Include full world context for prop research
        research_context = {
            "tag": tag,
            "pitch_text": input_data.pitch_text,
            "time_period": input_data.time_period,
            "visual_style": input_data.visual_style,
            "style_notes": input_data.style_notes,
            "world_details": input_data.world_details  # Full world context for research agents
        }

        result = await assembly.execute(research_context)
        return self._parse_prop_profile(tag, result.content)

    def _parse_prop_profile(self, tag: str, content: str) -> PropProfile:
        """Parse synthesis result into PropProfile."""
        try:
            data = json.loads(content)
            return PropProfile(
                tag=tag,
                name=data.get("name", tag.replace("PROP_", "")),
                appearance=data.get("appearance", ""),
                significance=data.get("significance", ""),
                associations=data.get("associations", []),
                history=data.get("history", ""),
                world_attributes=data.get("world_attributes", "")
            )
        except json.JSONDecodeError:
            return PropProfile(
                tag=tag,
                name=tag.replace("PROP_", ""),
                appearance=content
            )

    async def _research_global_context(
        self,
        input_data: WorldBibleInput,
        context: Dict[str, Any]
    ) -> WorldBibleInput:
        """Research global context (historical, cultural, atmosphere)."""
        prompt = f"""Research the global context for this story.

PITCH: {input_data.pitch_text}
TIME PERIOD: {input_data.time_period}
SETTING: {input_data.setting}
GENRE: {input_data.genre}

Provide:
1. Historical/cultural context
2. World rules (physics, magic, technology)
3. Atmosphere palette (colors, moods, textures)
4. Social dynamics

Format as JSON."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a world-building researcher.",
            function=LLMFunction.RESEARCH
        )

        try:
            context["global_context"] = json.loads(response)
        except json.JSONDecodeError:
            context["global_context"] = {"raw": response}

        return input_data

    async def _assemble_world_bible(
        self,
        input_data: WorldBibleInput,
        context: Dict[str, Any]
    ) -> WorldBibleOutput:
        """Assemble all profiles into world bible."""
        return WorldBibleOutput(
            characters=context.get("character_profiles", []),
            locations=context.get("location_profiles", []),
            props=context.get("prop_profiles", []),
            global_context=context.get("global_context", {}),
            metadata={
                "media_type": input_data.media_type,
                "genre": input_data.genre,
                "time_period": input_data.time_period
            }
        )

    async def _validate_continuity(
        self,
        world_bible: WorldBibleOutput,
        context: Dict[str, Any]
    ) -> WorldBibleOutput:
        """Validate cross-tag relationships."""
        # Check that all referenced tags exist
        all_char_tags = {c.tag for c in world_bible.characters}
        all_loc_tags = {l.tag for l in world_bible.locations}
        all_prop_tags = {p.tag for p in world_bible.props}

        issues = []

        # Check character relationships reference valid characters
        for char in world_bible.characters:
            for rel_tag in char.relationships.keys():
                if rel_tag.startswith("CHAR_") and rel_tag not in all_char_tags:
                    issues.append(f"Character {char.tag} references unknown character {rel_tag}")

        # Check location props reference valid props
        for loc in world_bible.locations:
            for prop_tag in loc.props_present:
                if prop_tag not in all_prop_tags:
                    issues.append(f"Location {loc.tag} references unknown prop {prop_tag}")

        if issues:
            logger.warning(f"Continuity issues found: {issues}")
            world_bible.metadata["continuity_issues"] = issues
        else:
            world_bible.metadata["continuity_passed"] = True

        return world_bible
