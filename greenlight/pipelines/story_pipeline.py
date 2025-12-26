"""
Greenlight Story Pipeline - 4-Layer Story Building Engine (Optimized)

Pipeline for processing story content through 4 progressive layers:
1. Plot Architecture - Story structure, acts, key plot points
2. Character Architecture - Character arcs, relationships, motivations
3. Continuity Validation - Cross-reference consistency checks
4. Motivational Coherence - Character action/motivation alignment

OPTIMIZATION: Uses parallel processing where possible:
- Layer 1 & 2 run in parallel (plot + character architecture)
- Layer 3 & 4 run in parallel (continuity + motivation validation)

NOTE: Story Novelling (prose expansion) has been moved to the Directing Pipeline.
The Story Pipeline outputs Script (scripts/script.md - structured story with scenes only).
The Directing Pipeline transforms Script into Visual_Script with frame notations.

SCENE-ONLY ARCHITECTURE:
- Scenes are the atomic narrative unit (## Scene N:)
- No beat markers - scenes contain continuous prose
- Director pipeline creates frames from scenes using scene.frame.camera notation
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from greenlight.core.constants import LLMFunction, StoryLayer, ValidationStatus
from greenlight.core.logging_config import get_logger
from greenlight.core.pitch_analyzer import PitchAnalyzer, PitchMetrics
from greenlight.llm import LLMManager, FunctionRouter, AnthropicClient
from greenlight.tags import TagParser, TagRegistry, ConsensusTagger, DirectionalTagConsensus, SpatialAnchorDetector
from greenlight.context import ContextEngine
from greenlight.patterns.quality import (
    QualityOrchestrator,
    QualityConfig,
    QualityReport,
    UniversalContext,
)
from .base_pipeline import BasePipeline, PipelineStep, PipelineResult

logger = get_logger("pipelines.story")


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class StoryInput:
    """Input for the story pipeline."""
    raw_text: str
    title: str = ""
    genre: str = ""
    visual_style: str = "live_action"  # live_action, anime, animation_2d, animation_3d, mixed_reality
    style_notes: str = ""  # Custom style instructions from user
    existing_tags: List[str] = field(default_factory=list)
    project_size: str = "short"  # micro, short, medium, feature, or "dynamic" for pitch-driven
    dynamic_scenes: bool = True  # If True, analyze pitch to determine optimal scene count


@dataclass
class PlotPoint:
    """A key plot point in the story structure."""
    point_id: str
    act: int
    position: float  # 0.0 to 1.0 position in story
    point_type: str  # inciting_incident, midpoint, climax, etc.
    description: str
    characters_involved: List[str] = field(default_factory=list)
    location: str = ""


@dataclass
class CharacterArc:
    """Character development arc with rich visual and psychological description.

    Designed to produce 125-250 word character profiles for storyboard generation.
    """
    character_tag: str
    character_name: str
    role: str  # protagonist, antagonist, supporting, etc.
    want: str  # External goal
    need: str  # Internal need/growth
    flaw: str  # Character flaw to overcome
    arc_type: str  # positive, negative, flat

    # Visual description fields (RICH - multi-paragraph)
    age: str = ""  # e.g., "early 20s", "mid 40s"
    ethnicity: str = ""  # e.g., "East Asian", "Mediterranean"
    appearance: str = ""  # RICH: Height, build, hair, eyes, skin, distinguishing features (50-100 words)
    costume: str = ""  # RICH: Default/signature clothing with colors, materials, details (30-50 words)

    # Psychological profile (NEW)
    psychology: str = ""  # Core psychological profile, fears, desires, coping mechanisms (50-75 words)

    # Voice and speech (NEW)
    speech_patterns: str = ""  # Dialogue style, vocabulary, verbal habits (30-50 words)
    speech_style: str = ""  # Formal/informal, direct/indirect, metaphorical
    literacy_level: str = ""  # Education level reflected in speech

    # Physicality (NEW)
    physicality: str = ""  # Movement style, gestures, body language, mannerisms (30-50 words)

    # Decision making (NEW)
    decision_heuristics: str = ""  # How they make decisions, moral compass, risk tolerance

    # Relationships and arc
    key_moments: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)

    # Emotional tells (NEW - for prose agents)
    emotional_tells: Dict[str, str] = field(default_factory=dict)  # emotion -> physical manifestation


@dataclass
class LocationDescription:
    """Location with directional views."""
    location_tag: str
    location_name: str
    description: str  # General description
    time_period: str = ""  # Historical/setting context
    atmosphere: str = ""  # Mood, lighting, ambiance
    # Directional views for consistent framing
    view_north: str = ""
    view_east: str = ""
    view_south: str = ""
    view_west: str = ""


@dataclass
class PropDescription:
    """Prop with detailed visual description."""
    prop_tag: str
    prop_name: str
    description: str  # What it is
    appearance: str = ""  # Visual details: color, material, size, condition
    significance: str = ""  # Story/symbolic importance
    associated_character: str = ""  # Which character it belongs to


class TransitionType:
    """Scene transition types for cinematic continuity."""
    FADE_IN = "FADE_IN"            # Fade in from black (opening)
    FADE_OUT = "FADE_OUT"          # Fade out to black (ending)
    CUT_TO = "CUT_TO"              # Standard cut
    DISSOLVE_TO = "DISSOLVE_TO"    # Gradual blend (time passage, dream)
    FADE_TO = "FADE_TO"            # Fade to black/white
    MATCH_CUT = "MATCH_CUT"        # Visual/thematic match between scenes
    SMASH_CUT = "SMASH_CUT"        # Abrupt jarring cut for shock
    CROSS_CUT = "CROSS_CUT"        # Parallel action intercutting
    FLASHBACK = "FLASHBACK"        # Jump to past
    FLASH_FORWARD = "FLASH_FORWARD"  # Jump to future
    JUMP_CUT = "JUMP_CUT"          # Time jump within same scene
    WIPE = "WIPE"                  # Scene wipes across screen


class SceneWeight:
    """Scene importance weights for word budget allocation."""
    MINIMAL = 0.5      # Brief transitional scenes
    STANDARD = 1.0     # Normal scenes
    IMPORTANT = 1.5    # Key plot moments
    CLIMACTIC = 2.0    # Major turning points, climax
    EPIC = 2.5         # Extended climactic sequences


@dataclass
class Scene:
    """A scene in the story.

    Scenes are the atomic narrative unit in the scene-only architecture.
    Director pipeline creates frames from scenes using scene.frame.camera notation.
    """
    scene_id: str
    scene_number: int
    location_tag: str
    location_description: str
    time_of_day: str
    characters_present: List[str]
    purpose: str  # What this scene accomplishes
    conflict: str
    outcome: str
    emotional_arc: str  # The emotional progression of the scene
    content: str = ""  # The full prose content of the scene
    tags: List[str] = field(default_factory=list)  # All tags used in this scene
    prop_tags: List[str] = field(default_factory=list)  # Props used in this scene

    # NEW: Scene weighting for word budget allocation
    weight: float = 1.0  # SceneWeight value - climactic scenes get more words

    # NEW: Transition and temporal fields
    transition_in: str = "CUT_TO"   # How we enter this scene (TransitionType)
    transition_out: str = "CUT_TO"  # How we exit this scene (TransitionType)
    time_jump: str = ""  # Time elapsed since previous scene (e.g., "2 hours later", "next morning")

    # NEW: Subtext and dramatic irony tracking
    subtext_notes: str = ""  # What characters mean vs. what they say
    dramatic_irony: str = ""  # What audience knows that characters don't
    unspoken_tension: str = ""  # Underlying tensions not explicitly addressed

    # NEW: Thematic resonance tracking
    themes_advanced: List[str] = field(default_factory=list)  # Which themes this scene develops
    thematic_resonance: str = ""  # How this scene connects to core themes
    symbolic_elements: List[str] = field(default_factory=list)  # Symbols/motifs used


@dataclass
class ContinuityIssue:
    """A continuity issue found during validation."""
    issue_id: str
    severity: str  # critical, warning, suggestion
    category: str  # character, location, timeline, prop
    description: str
    scene_refs: List[str]
    suggested_fix: str = ""


@dataclass
class MotivationCheck:
    """Result of motivation coherence check."""
    character_tag: str
    action: str
    scene_id: str
    is_coherent: bool
    reasoning: str
    suggested_revision: str = ""


@dataclass
class StoryOutput:
    """Complete output from the story pipeline."""
    title: str
    genre: str
    visual_style: str = ""  # live_action, anime, animation_2d, animation_3d, mixed_reality
    style_notes: str = ""  # Custom style instructions

    # World Overview (generated by agents from pitch)
    logline: str = ""  # One-sentence story summary
    synopsis: str = ""  # Expanded story summary
    themes: str = ""  # Core themes explored
    world_rules: str = ""  # World-specific rules, magic systems, etc.
    lighting: str = ""  # Lighting style for the project
    vibe: str = ""  # Overall mood/atmosphere

    # Layer 1: Plot Architecture
    plot_points: List[PlotPoint] = field(default_factory=list)
    act_structure: Dict[int, List[str]] = field(default_factory=dict)

    # Layer 2: Character Architecture (with visual descriptions)
    character_arcs: List[CharacterArc] = field(default_factory=list)

    # Scene structure (populated by plot/character architecture)
    # Scenes are the atomic narrative unit - no beat subdivision
    scenes: List[Scene] = field(default_factory=list)

    # Layer 3: Continuity
    continuity_issues: List[ContinuityIssue] = field(default_factory=list)
    continuity_status: ValidationStatus = ValidationStatus.PENDING

    # Layer 4: Motivation
    motivation_checks: List[MotivationCheck] = field(default_factory=list)
    motivation_status: ValidationStatus = ValidationStatus.PENDING

    # Tags
    all_tags: List[str] = field(default_factory=list)
    character_tags: List[str] = field(default_factory=list)
    location_tags: List[str] = field(default_factory=list)

    # Detailed descriptions
    location_descriptions: List[LocationDescription] = field(default_factory=list)
    prop_descriptions: List[PropDescription] = field(default_factory=list)

    # Quality Assurance
    quality_score: float = 0.0
    quality_passed: bool = False
    quality_report: Optional[Any] = None  # QualityReport from quality patterns

    summary: str = ""

    # Script content (built from scenes or stored directly)
    _script_content: str = field(default="", repr=False)

    @property
    def script(self) -> str:
        """
        Get the full script content.

        Returns the stored script content if available, otherwise builds it from scenes.
        This property ensures compatibility with code expecting a 'script' attribute.
        """
        if self._script_content:
            return self._script_content

        # Build script from scenes
        lines = [f"# {self.title}\n"]
        if self.logline:
            lines.append(f"*{self.logline}*\n")
        lines.append("")

        for scene in self.scenes:
            # Handle both Scene dataclass and dict formats
            if hasattr(scene, 'scene_number'):
                scene_num = scene.scene_number
                location_desc = getattr(scene, 'location_description', '')
                content = getattr(scene, 'content', '')
            else:
                scene_num = scene.get('scene_number', 1)
                location_desc = scene.get('description', scene.get('location_description', ''))
                content = scene.get('content', '')

            lines.append(f"## Scene {scene_num}:")
            if location_desc:
                lines.append(location_desc)
            if content:
                lines.append("")
                lines.append(content)
            lines.append("")

        return "\n".join(lines)

    @script.setter
    def script(self, value: str) -> None:
        """Set the script content directly."""
        self._script_content = value


# =============================================================================
# STORY PIPELINE
# =============================================================================

class StoryPipeline(BasePipeline[StoryInput, StoryOutput]):
    """
    4-Layer Story Building Pipeline.

    Layers:
    1. Plot Architecture - Structure and key plot points
    2. Character Architecture - Arcs, relationships, motivations
    3. Continuity Validation - Consistency checking
    4. Motivational Coherence - Action/motivation alignment

    NOTE: Prose expansion (Story Novelling) has been moved to the Directing Pipeline.
    This pipeline outputs Script (scripts/script.md - structured story with scenes only).

    SCENE-ONLY ARCHITECTURE:
    - Scenes are the atomic narrative unit (## Scene N:)
    - No beat markers - scenes contain continuous prose
    - Director pipeline creates frames from scenes using scene.frame.camera notation
    """

    # Project size configurations (scene-only, no beats)
    SIZE_CONFIG = {
        "micro": {"target_words": 500, "scenes": 3, "words_per_scene": 150},
        "short": {"target_words": 2000, "scenes": 8, "words_per_scene": 250},
        "medium": {"target_words": 5000, "scenes": 15, "words_per_scene": 333},
        "feature": {"target_words": 15000, "scenes": 40, "words_per_scene": 375},
    }

    def __init__(
        self,
        llm_manager: LLMManager = None,
        tag_registry: TagRegistry = None,
        context_engine: ContextEngine = None,
        project_path: Optional[str] = None
    ):
        """Initialize the story pipeline.

        Args:
            llm_manager: LLM manager for API calls
            tag_registry: Tag registry for tag management
            context_engine: Context engine for retrieval
            project_path: Path to project root (required for file-based QA context)
        """
        from pathlib import Path

        self.llm_manager = llm_manager or LLMManager()
        self.tag_registry = tag_registry or TagRegistry()
        self.context_engine = context_engine
        self.project_path = Path(project_path) if project_path else None

        self.function_router = FunctionRouter(self.llm_manager)
        self.tag_parser = TagParser()

        # Create LLM caller for consensus tagger - HARDCODED TO CLAUDE HAIKU 4.5
        # Using AnthropicClient directly to ensure Haiku is always used for 10-agent consensus
        # (cost efficiency - Haiku is much cheaper for high-volume consensus voting)
        self._anthropic_client = AnthropicClient()

        async def llm_caller(prompt: str) -> str:
            """Async LLM caller for tag extraction - uses Claude Haiku 4.5."""
            import asyncio
            # Use Claude Haiku 4.5 model directly for 10-agent consensus (cost efficiency)
            response = await asyncio.to_thread(
                self._anthropic_client.generate_text,
                prompt,
                system="You are a tag extraction specialist. Extract character, location, and prop tags from story content.",
                max_tokens=2000,
                model="claude-haiku-4-5-20251001"
            )
            return response.text

        self.consensus_tagger = ConsensusTagger(
            registry=self.tag_registry,
            llm_caller=llm_caller
        )

        super().__init__("story_pipeline_v2")

    def _define_steps(self) -> None:
        """Define the optimized pipeline steps with parallel execution."""
        self._steps = [
            # Pre-processing
            PipelineStep(
                name="parse_input",
                description="Parse and clean raw story input"
            ),
            PipelineStep(
                name="extract_tags",
                description="Extract and validate story tags with consensus"
            ),
            # World Overview: Generate logline, synopsis, themes, world_rules, lighting, vibe
            PipelineStep(
                name="world_overview",
                description="Generate world overview (logline, synopsis, themes, rules, style)"
            ),
            # Parallel Layer 1+2: Plot & Character Architecture (run together)
            PipelineStep(
                name="parallel_architecture",
                description="Layers 1+2: Build plot and character architecture in parallel"
            ),
            # Scene Generation: Convert plot points to scenes (continuous prose)
            PipelineStep(
                name="generate_scenes",
                description="Generate scenes from plot architecture (scene-only, no beats)"
            ),
            # Parallel Layer 3+4: Validation (run together)
            PipelineStep(
                name="parallel_validation",
                description="Layers 3+4: Run continuity and motivation validation in parallel"
            ),
            # Quality Assurance: Run quality patterns to fix issues before output
            PipelineStep(
                name="quality_assurance",
                description="Run quality assurance patterns (Telescope, Inquisitor, Continuity, Constellation, Anchor)"
            ),
            # Final assembly
            PipelineStep(
                name="assemble_output",
                description="Assemble final story output (Script)"
            ),
        ]

    def _log_agent_operation(self, operation: str, details: str = "") -> None:
        """Log an agent operation for detailed progress tracking."""
        message = f"    ⚙️  {operation}"
        if details:
            message += f": {details}"
        logger.info(message)

    async def _execute_step(
        self,
        step: PipelineStep,
        input_data: Any,
        context: Dict[str, Any]
    ) -> Any:
        """Execute a pipeline step with parallel optimization."""
        step_handlers = {
            "parse_input": self._parse_input,
            "extract_tags": self._extract_tags,
            "world_overview": self._generate_world_overview,
            "parallel_architecture": self._parallel_architecture,
            "generate_scenes": self._generate_scenes,
            "parallel_validation": self._parallel_validation,
            "quality_assurance": self._quality_assurance,
            "assemble_output": self._assemble_output,
        }

        handler = step_handlers.get(step.name)
        if handler:
            return await handler(input_data, context)
        return input_data

    # =========================================================================
    # PARALLEL EXECUTION METHODS
    # =========================================================================

    async def _parallel_architecture(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """
        Run Layer 1 (Plot) and Layer 2 (Character) in parallel.

        This is faster than sequential execution since both layers
        only depend on the input data, not on each other.
        """
        logger.info("⚡ Running Layers 1+2 in parallel (Plot + Character Architecture)...")
        self._log_agent_operation("Starting parallel architecture phase")

        # Run both layers concurrently
        results = await asyncio.gather(
            self._layer1_plot_architecture(data.copy(), context),
            self._layer2_character_architecture(data.copy(), context),
            return_exceptions=True
        )

        # Merge results
        plot_result, char_result = results

        # Handle exceptions
        if isinstance(plot_result, Exception):
            logger.error(f"Plot architecture failed: {plot_result}")
            plot_result = data
        if isinstance(char_result, Exception):
            logger.error(f"Character architecture failed: {char_result}")
            char_result = data

        # Merge both results into data
        data['plot_points'] = plot_result.get('plot_points', [])
        data['plot_architecture_raw'] = plot_result.get('plot_architecture_raw', '')
        data['character_arcs'] = char_result.get('character_arcs', [])
        data['character_architecture_raw'] = char_result.get('character_architecture_raw', '')

        self._log_agent_operation("Parallel architecture complete",
                                  f"{len(data['plot_points'])} plot points, {len(data['character_arcs'])} character arcs")

        return data

    async def _generate_scenes(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Generate scenes from plot architecture (scene-only, no beats).

        SCENE-ONLY ARCHITECTURE:
        - Scenes are the atomic narrative unit (## Scene N:)
        - Each scene contains continuous prose (no beat markers)
        - Director pipeline creates frames from scenes using scene.frame.camera notation

        Uses FILE-BASED INCREMENTAL approach:
        - Each scene is appended to script_content.md immediately after generation
        - Subsequent scenes receive the FULL prior script as context (not just a summary)
        - This ensures stronger continuity, character consistency, and narrative coherence
        """
        import json

        logger.info("Generating scenes from plot architecture...")
        self._log_agent_operation("Starting scene generation (file-based incremental)")

        plot_points = data.get('plot_points', [])
        character_arcs = data.get('character_arcs', [])
        size_config = data.get('size_config', {'scenes': 8, 'words_per_scene': 250})
        target_scenes = size_config.get('scenes', 8)
        words_per_scene = size_config.get('words_per_scene', 250)

        # Build character info for prompt
        char_info = "\n".join([
            f"- [{arc.character_tag}] {arc.character_name}: {arc.role} - Want: {arc.want}, Need: {arc.need}"
            for arc in character_arcs
        ]) if character_arcs else "No characters defined"

        # Build plot points for prompt
        plot_info = "\n".join([
            f"- {pp.point_type} (Act {pp.act}, Position {pp.position}): {pp.description}"
            for pp in plot_points
        ]) if plot_points else "No plot points defined"

        # Build location info
        location_tags = data.get('location_tags', [])
        location_info = ", ".join(f"[{tag}]" for tag in location_tags) if location_tags else "No locations defined"

        # =====================================================================
        # FILE-BASED INCREMENTAL SCENE GENERATION
        # Each scene is written to file immediately, and full context is loaded
        # for subsequent scenes to ensure narrative coherence
        # =====================================================================
        self._log_agent_operation("Using file-based incremental scene generation", f"{target_scenes} scenes")

        # Load world_config.json and pitch.md for rich context
        world_config_context = ""
        pitch_context = ""

        if self.project_path:
            # Load world_config.json
            world_config_path = self.project_path / "world_bible" / "world_config.json"
            if world_config_path.exists():
                try:
                    world_config_data = json.loads(world_config_path.read_text(encoding="utf-8"))
                    # Build concise world context
                    world_parts = []
                    if world_config_data.get('title'):
                        world_parts.append(f"Title: {world_config_data['title']}")
                    if world_config_data.get('genre'):
                        world_parts.append(f"Genre: {world_config_data['genre']}")
                    if world_config_data.get('themes'):
                        world_parts.append(f"Themes: {world_config_data['themes']}")
                    if world_config_data.get('world_rules'):
                        world_parts.append(f"World Rules: {world_config_data['world_rules']}")
                    if world_config_data.get('style_notes'):
                        world_parts.append(f"Style: {world_config_data['style_notes']}")
                    # Add character details
                    chars = world_config_data.get('characters', [])
                    if chars:
                        char_details = []
                        for c in chars[:10]:  # Limit to 10 characters
                            char_details.append(f"  - [{c.get('tag', '')}] {c.get('name', '')}: {c.get('role', '')}")
                        world_parts.append("Characters:\n" + "\n".join(char_details))
                    # Add location details
                    locs = world_config_data.get('locations', [])
                    if locs:
                        loc_details = []
                        for loc in locs[:10]:  # Limit to 10 locations
                            loc_details.append(f"  - [{loc.get('tag', '')}] {loc.get('name', '')}")
                        world_parts.append("Locations:\n" + "\n".join(loc_details))
                    world_config_context = "\n".join(world_parts)
                    self._log_agent_operation("Loaded world_config.json", f"{len(world_config_context)} chars")
                except Exception as e:
                    logger.warning(f"Failed to load world_config.json: {e}")

            # Load pitch.md
            pitch_path = self.project_path / "world_bible" / "pitch.md"
            if pitch_path.exists():
                pitch_context = pitch_path.read_text(encoding="utf-8")
                self._log_agent_operation("Loaded pitch.md", f"{len(pitch_context)} chars")

            # Initialize/clear script_content.md at start of scene generation
            script_content_path = self.project_path / "scripts" / "script_content.md"
            script_content_path.parent.mkdir(parents=True, exist_ok=True)
            script_content_path.write_text("# Script Content\n\n", encoding="utf-8")
            self._log_agent_operation("Initialized script_content.md")

        all_scenes_text = []

        for scene_num in range(1, target_scenes + 1):
            self._log_agent_operation(f"Generating scene {scene_num}/{target_scenes}")

            # Determine which plot points apply to this scene
            act = 1 if scene_num <= target_scenes * 0.25 else (2 if scene_num <= target_scenes * 0.75 else 3)
            relevant_plot_points = [pp for pp in plot_points if pp.act == act]
            relevant_plot_info = "\n".join([
                f"- {pp.point_type}: {pp.description}"
                for pp in relevant_plot_points
            ]) if relevant_plot_points else "Continue story progression"

            # Load current script_content.md for full prior context
            prior_script_context = ""
            if self.project_path:
                script_content_path = self.project_path / "scripts" / "script_content.md"
                if script_content_path.exists():
                    prior_script_context = script_content_path.read_text(encoding="utf-8")
                    # Only include if there's actual content beyond the header
                    if len(prior_script_context.strip()) <= len("# Script Content"):
                        prior_script_context = ""

            # Get notation standards from context engine (single source of truth)
            notation_standards = ""
            if self.context_engine:
                notation_standards = self.context_engine.get_tag_format_rules()
            else:
                # Fallback if no context engine
                notation_standards = """
## TAG FORMAT (MANDATORY)
- ALL tags MUST use square brackets: [TAG_NAME]
- ALL tags MUST have prefix: CHAR_, LOC_, PROP_, CONCEPT_, EVENT_, ENV_
- ALL tags MUST be UPPERCASE with underscores
- Examples: [CHAR_PROTAGONIST], [LOC_PALACE], [PROP_SWORD], [CONCEPT_HONOR]
"""

            # Calculate scene weight for word budget allocation
            # Act 1: Setup (standard), Act 2 midpoint: important, Act 3 climax: climactic
            scene_weight = 1.0
            if scene_num == 1:
                scene_weight = 1.2  # Strong opening
            elif scene_num == target_scenes:
                scene_weight = 1.5  # Strong ending
            elif act == 2 and scene_num == int(target_scenes * 0.5):
                scene_weight = 1.5  # Midpoint
            elif act == 3 and scene_num >= int(target_scenes * 0.85):
                scene_weight = 2.0  # Climax

            # Adjust words for this scene based on weight
            scene_words = int(words_per_scene * scene_weight)

            # Determine transition type based on scene position and content
            if scene_num == 1:
                transition_in = "FADE_IN"
            elif act != (1 if (scene_num - 1) <= target_scenes * 0.25 else (2 if (scene_num - 1) <= target_scenes * 0.75 else 3)):
                transition_in = "DISSOLVE_TO"  # Act transitions
            else:
                transition_in = "CUT_TO"

            # Get themes for thematic tracking
            story_themes = data.get('themes', '')

            # Build the scene prompt with full context and notation standards
            # SCENE-ONLY ARCHITECTURE: Generate continuous prose, no beat markers
            scene_prompt = f"""Generate SCENE {scene_num} of {target_scenes} for this story.

{notation_standards}

=== WORLD CONFIGURATION ===
{world_config_context if world_config_context else "No world config available"}

=== STORY PITCH ===
{pitch_context[:2000] if pitch_context else data['text'][:1500]}

=== GENRE ===
{data['genre']}

=== CORE THEMES TO WEAVE THROUGHOUT ===
{story_themes if story_themes else "No specific themes defined - infer from pitch"}

=== CHARACTERS (with speech patterns) ===
{char_info}
IMPORTANT: Each character should have a DISTINCT voice. Match their dialogue to their speech patterns, vocabulary level, and personality.

=== RELEVANT PLOT POINTS FOR THIS SCENE (Act {act}) ===
{relevant_plot_info}

=== AVAILABLE LOCATIONS ===
{location_info}

{"=== PRIOR SCENES (FULL SCRIPT SO FAR) ===" + chr(10) + prior_script_context if prior_script_context else "=== THIS IS THE OPENING SCENE ==="}

=== SCENE IMPORTANCE ===
Scene Weight: {scene_weight} ({'Opening scene' if scene_num == 1 else 'Climactic scene' if scene_weight >= 2.0 else 'Key moment' if scene_weight >= 1.5 else 'Standard scene'})
Target Word Count: {scene_words}-{scene_words + 75} words (weighted for scene importance)
Transition In: {transition_in}

Generate EXACTLY this format for SCENE {scene_num}:

## Scene {scene_num}:
Location: [LOC_LOCATION_NAME] - [specific location description]
Time: [time of day]
Characters: [CHAR_NAME1], [CHAR_NAME2]
Purpose: [what this scene accomplishes in the story]
Emotional Arc: [the emotional progression of this scene]
Transition: {transition_in}
Time Jump: [if any time has passed since previous scene, e.g., "Two hours later", "Next morning", or "Continuous" if immediate]
Themes Advanced: [which core themes this scene develops - must reference at least one theme from the list above]
Subtext: [what characters MEAN vs. what they SAY - the unspoken tension beneath the dialogue]

[Write {scene_words}-{scene_words + 75} words of continuous prose describing the scene.
Include character actions, dialogue, environment details, and emotional subtext.
Use proper tags throughout: [CHAR_NAME], [LOC_NAME], [PROP_NAME].
Write as flowing narrative - NO beat markers, NO numbered sections.

CHARACTER VOICE REQUIREMENTS:
- Each character's dialogue must match their established speech patterns
- Use distinct vocabulary levels, verbal habits, and speaking styles
- Show personality through HOW they speak, not just WHAT they say

SUBTEXT REQUIREMENTS:
- Include unspoken tension between characters
- Show what characters want but cannot say directly
- Layer meaning beneath surface dialogue

THEMATIC REQUIREMENTS:
- Each scene must advance at least one core theme
- Use symbolic elements (props, actions, imagery) that reinforce themes
- Connect character choices to thematic exploration

Let the story breathe naturally through the prose.]

CRITICAL TAG RULES:
- Use ACTUAL tags from world config (e.g., [CHAR_PROTAGONIST], [LOC_MAIN_SETTING])
- ALL tags MUST have square brackets
- ALL tags MUST have proper prefix (CHAR_, LOC_, PROP_)
- DO NOT use placeholder tags like [CHAR_TAG1] - use real character names from the story

IMPORTANT: Maintain continuity with prior scenes. Reference established:
- Character positions and emotional states
- Location details already described
- Props that have been introduced
- Story threads and tensions

Generate SCENE {scene_num} now as continuous prose (NO beat markers):"""

            scene_response = await self.function_router.route(
                function=LLMFunction.STORY_ANALYSIS,
                prompt=scene_prompt,
                system_prompt=f"You are a screenwriter generating SCENE {scene_num} of {target_scenes}. Write continuous prose with rich visual detail. NO beat markers or numbered sections. Maintain strict continuity with prior scenes."
            )

            all_scenes_text.append(scene_response)

            # IMMEDIATELY append this scene to script_content.md
            if self.project_path:
                script_content_path = self.project_path / "scripts" / "script_content.md"
                with open(script_content_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n{scene_response}")
                self._log_agent_operation(f"Appended scene {scene_num} to script_content.md",
                                          f"{len(scene_response)} chars")

            self._log_agent_operation(f"Scene {scene_num} generated", f"{len(scene_response)} chars")

        # Combine all scenes
        response = "\n\n".join(all_scenes_text)
        self._log_agent_operation("All scenes generated", f"{len(response)} chars, {target_scenes} scenes")
        self._log_agent_operation("Parsing scenes from response")

        # Parse scenes from response (scene-only, no beats)
        scenes = self._parse_scenes_detailed(response, data)
        data['scenes'] = scenes

        self._log_agent_operation("Scene generation complete", f"{len(scenes)} scenes")

        # script_content.md is already populated incrementally - log final state
        if self.project_path:
            script_content_path = self.project_path / "scripts" / "script_content.md"
            final_content = script_content_path.read_text(encoding="utf-8")
            self._log_agent_operation("Final script_content.md ready",
                                      f"{len(final_content)} chars")
            logger.info(f"📝 Script content ready at {script_content_path}")

        return data

    async def _parallel_validation(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """
        Run Layer 3 (Continuity) and Layer 4 (Motivation) in parallel.

        Both validation layers can run concurrently since they
        analyze the same data independently.
        """
        logger.info("⚡ Running Layers 3+4 in parallel (Continuity + Motivation Validation)...")
        self._log_agent_operation("Starting parallel validation phase")

        # Run both validation layers concurrently
        results = await asyncio.gather(
            self._layer3_continuity_validation(data.copy(), context),
            self._layer4_motivational_coherence(data.copy(), context),
            return_exceptions=True
        )

        # Merge results
        continuity_result, motivation_result = results

        # Handle exceptions
        if isinstance(continuity_result, Exception):
            logger.error(f"Continuity validation failed: {continuity_result}")
            continuity_result = data
        if isinstance(motivation_result, Exception):
            logger.error(f"Motivation validation failed: {motivation_result}")
            motivation_result = data

        # Merge validation results
        data['continuity_issues'] = continuity_result.get('continuity_issues', [])
        data['continuity_status'] = continuity_result.get('continuity_status', ValidationStatus.PASSED)
        data['directional_validation'] = continuity_result.get('directional_validation', {})
        data['spatial_anchors'] = continuity_result.get('spatial_anchors', [])
        data['motivation_checks'] = motivation_result.get('motivation_checks', [])
        data['motivation_status'] = motivation_result.get('motivation_status', ValidationStatus.PASSED)

        # Log summary
        continuity_count = len(data['continuity_issues'])
        motivation_count = sum(1 for c in data['motivation_checks'] if not c.is_coherent)
        self._log_agent_operation("Parallel validation complete",
                                  f"{continuity_count} continuity issues, {motivation_count} motivation issues")

        return data

    # =========================================================================
    # QUALITY ASSURANCE STEP
    # =========================================================================

    async def _quality_assurance(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """
        Run quality assurance patterns on the script before final output.

        Phase 2 of two-phase output process:
        1. Load context files from disk (script_content.md, world_config.json, pitch.md)
        2. Run quality agents (Telescope, Inquisitor, Continuity, Constellation, Anchor)
        3. Save final corrected output as scripts/script.md

        Issues are detected AND corrected before the script goes to Director.
        """
        import json

        logger.info("🔍 Running Quality Assurance Phase...")
        self._log_agent_operation("Starting quality assurance phase")

        # Phase 2: Load context files from disk for complete context
        script_content = ""
        world_config = {}
        pitch = ""

        if self.project_path:
            # Load intermediate script_content.md
            script_content_path = self.project_path / "scripts" / "script_content.md"
            if script_content_path.exists():
                script_content = script_content_path.read_text(encoding="utf-8")
                self._log_agent_operation("Loaded script_content.md",
                                          f"{len(script_content)} chars")
            else:
                # Fallback to building from data
                script_content = self._build_script_content(data)
                self._log_agent_operation("Built script from data (no script_content.md found)")

            # Load world_config.json
            world_config_path = self.project_path / "world_bible" / "world_config.json"
            if world_config_path.exists():
                try:
                    world_config = json.loads(world_config_path.read_text(encoding="utf-8"))
                    self._log_agent_operation("Loaded world_config.json",
                                              f"{len(world_config)} keys")
                except Exception as e:
                    logger.warning(f"Failed to load world_config.json: {e}")
                    world_config = self._build_world_config(data)
            else:
                world_config = self._build_world_config(data)

            # Load pitch.md
            pitch_path = self.project_path / "world_bible" / "pitch.md"
            if pitch_path.exists():
                pitch = pitch_path.read_text(encoding="utf-8")
                self._log_agent_operation("Loaded pitch.md", f"{len(pitch)} chars")
            else:
                pitch = data.get('text', '')
        else:
            # No project_path - use in-memory data
            script_content = self._build_script_content(data)
            world_config = context.get('world_config', {})
            if not world_config:
                world_config = self._build_world_config(data)
            pitch = data.get('text', '')

        # Prepare scenes for quality analysis
        scenes = []
        for scene in data.get('scenes', []):
            # Handle both Scene dataclass and dict formats
            if hasattr(scene, 'scene_number'):
                # Scene dataclass
                scene_dict = {
                    'scene_number': scene.scene_number,
                    'content': scene.location_description if hasattr(scene, 'location_description') else '',
                    'purpose': scene.purpose if hasattr(scene, 'purpose') else '',
                    'location': scene.location_tag if hasattr(scene, 'location_tag') else '',
                    'characters': scene.characters_present if hasattr(scene, 'characters_present') else [],
                }
            else:
                # Dict format
                scene_dict = {
                    'scene_number': scene.get('scene_number', 1),
                    'content': scene.get('description', scene.get('location_description', '')),
                    'purpose': scene.get('purpose', ''),
                    'location': scene.get('location', scene.get('location_tag', '')),
                    'characters': scene.get('characters', scene.get('characters_present', [])),
                }
            scenes.append(scene_dict)

        # Configure quality orchestrator
        config = QualityConfig(
            run_telescope=True,
            run_inquisitor=True,
            run_continuity=True,
            run_constellation=True,
            run_anchor=True,
            run_mirror=False,  # Optional - can be enabled for deeper refinement
            min_telescope_score=0.7,
            min_continuity_score=0.8,
            min_overall_score=0.75,
        )

        # Create LLM caller for quality agents
        async def quality_llm_caller(prompt: str) -> str:
            """LLM caller for quality agents."""
            response = await self.llm_manager.call_llm(
                function=LLMFunction.STORY_VALIDATION,
                prompt=prompt,
                context={"layer": "quality_assurance"}
            )
            return response.content if hasattr(response, 'content') else str(response)

        # Run quality orchestrator
        orchestrator = QualityOrchestrator(
            llm_caller=quality_llm_caller,
            config=config
        )

        try:
            quality_report = await orchestrator.run_quality_assurance(
                script=script_content,
                scenes=scenes,
                world_config=world_config,
                pitch=pitch
            )

            # Store quality report in data
            data['quality_report'] = quality_report
            data['quality_score'] = quality_report.overall_score
            data['quality_passed'] = quality_report.passed

            # Get script after quality agents (may have fixes applied)
            qa_script = quality_report.final_script if quality_report.final_script else script_content

            # If script was modified, log the changes
            if quality_report.final_script and quality_report.final_script != script_content:
                self._log_agent_operation("Quality fixes applied",
                                          f"Score: {quality_report.overall_score:.2f}")

            # Log phase results and collect feedback for Assembly Agent
            quality_feedback_parts = []
            for phase in quality_report.phases:
                status = "✓" if phase.passed else "✗"
                self._log_agent_operation(f"  {status} {phase.phase_name}",
                                          f"Score: {phase.score:.2f}, Issues: {phase.issues_found}")
                if phase.issues_found > 0:
                    quality_feedback_parts.append(
                        f"{phase.phase_name}: {phase.issues_found} issues (Score: {phase.score:.2f})"
                    )

            self._log_agent_operation("Quality assurance complete",
                                      f"Overall: {quality_report.overall_score:.2f}, Passed: {quality_report.passed}")

            # =========================================================
            # FULL CONTEXT ASSEMBLY AGENT (Final Step)
            # =========================================================
            # Run Full Context Assembly Agent to produce final script.md
            # Uses Claude Sonnet 4.5 (hardcoded) with all context
            quality_feedback = "\n".join(quality_feedback_parts) if quality_feedback_parts else None

            final_script = await self._full_context_assembly(
                script_content=qa_script,
                world_config=world_config,
                pitch=pitch,
                quality_feedback=quality_feedback
            )

            # Phase 2 Complete: Save final script.md
            if self.project_path:
                script_path = self.project_path / "scripts" / "script.md"
                script_path.parent.mkdir(parents=True, exist_ok=True)
                script_path.write_text(final_script, encoding="utf-8")
                self._log_agent_operation("Saved final script",
                                          f"scripts/script.md ({len(final_script)} chars)")
                logger.info(f"📝 Saved final script to {script_path}")

            # Store final script in data for downstream use
            data['final_script'] = final_script

        except Exception as e:
            logger.error(f"Quality assurance failed: {e}")
            data['quality_report'] = None
            data['quality_score'] = 0.0
            data['quality_passed'] = False

            # Even on failure, save what we have as script.md
            if self.project_path and script_content:
                script_path = self.project_path / "scripts" / "script.md"
                script_path.parent.mkdir(parents=True, exist_ok=True)
                script_path.write_text(script_content, encoding="utf-8")
                self._log_agent_operation("Saved script (QA failed)",
                                          f"scripts/script.md ({len(script_content)} chars)")
                data['final_script'] = script_content

        return data

    def _build_script_content(self, data: Dict[str, Any]) -> str:
        """Build script content from scenes (scene-only, no beats).

        SCENE-ONLY ARCHITECTURE:
        - Each scene is output with ## Scene N: header
        - Scene content is continuous prose (no beat markers)
        - Director pipeline creates frames from scenes
        """
        lines = []

        for scene in data.get('scenes', []):
            # Handle both Scene dataclass and dict formats
            if hasattr(scene, 'scene_number'):
                # Scene dataclass
                scene_num = scene.scene_number
                location_desc = scene.location_description if hasattr(scene, 'location_description') else ''
                content = scene.content if hasattr(scene, 'content') else ''
            else:
                # Dict format
                scene_num = scene.get('scene_number', 1)
                location_desc = scene.get('description', scene.get('location_description', ''))
                content = scene.get('content', '')

            lines.append(f"## Scene {scene_num}:")
            if location_desc:
                lines.append(location_desc)
            if content:
                lines.append("")
                lines.append(content)
            lines.append("")

        return "\n".join(lines)

    def _build_world_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build world_config from pipeline data."""
        return {
            'title': data.get('title', ''),
            'genre': data.get('genre', ''),
            'themes': data.get('themes', ''),
            'world_rules': data.get('world_rules', ''),
            'style_notes': data.get('style_notes', ''),
            'characters': [
                {'tag': tag, 'name': tag.replace('CHAR_', '').title()}
                for tag in data.get('character_tags', [])
            ],
            'locations': [
                {'tag': tag, 'name': tag.replace('LOC_', '').title()}
                for tag in data.get('location_tags', [])
            ],
            'props': [
                {'tag': tag, 'name': tag.replace('PROP_', '').title()}
                for tag in data.get('all_tags', [])
                if tag.startswith('PROP_')
            ],
            'all_tags': data.get('all_tags', []),
        }

    # =========================================================================
    # FULL CONTEXT ASSEMBLY AGENT
    # =========================================================================

    async def _full_context_assembly(
        self,
        script_content: str,
        world_config: Dict[str, Any],
        pitch: str,
        quality_feedback: Optional[str] = None
    ) -> str:
        """
        Full Context Assembly Agent - Final consolidation step.

        HARDCODED: Uses Claude Opus 4.5 (claude-opus-4-5-20251101) for
        high-quality final assembly.

        Takes ALL context inputs and produces the final script.md:
        - pitch.md: Original story pitch
        - world_config.json: World bible with characters, locations, props
        - script_content: Current script from quality agents
        - quality_feedback: Issues logged by quality agents (for awareness)

        Processes scene-by-scene with chunking to maintain context window.

        Returns:
            Final assembled script content
        """
        import json

        logger.info("🔧 Running Full Context Assembly Agent (Claude Opus 4.5)...")
        self._log_agent_operation("Full Context Assembly Agent", "Consolidating all context")

        # Build comprehensive context
        context_parts = [
            "=== FULL CONTEXT ASSEMBLY ===",
            "",
            "You are the Full Context Assembly Agent. Your task is to produce the FINAL",
            "script.md by consolidating all available context and ensuring quality.",
            "",
            "=== PITCH (Original Story) ===",
            pitch if pitch else "(No pitch available)",
            "",
            "=== WORLD CONFIGURATION ===",
        ]

        # Add world config summary
        if world_config:
            context_parts.append(f"Title: {world_config.get('title', 'Untitled')}")
            context_parts.append(f"Genre: {world_config.get('genre', 'Unknown')}")
            context_parts.append(f"Themes: {world_config.get('themes', '')}")
            context_parts.append(f"World Rules: {world_config.get('world_rules', '')}")
            context_parts.append(f"Style: {world_config.get('style_notes', '')}")

            # Characters
            chars = world_config.get('characters', [])
            if chars:
                context_parts.append("")
                context_parts.append("Characters:")
                for char in chars[:10]:  # Limit to avoid token overflow
                    tag = char.get('tag', '')
                    name = char.get('name', '')
                    context_parts.append(f"  - [{tag}]: {name}")

            # Locations
            locs = world_config.get('locations', [])
            if locs:
                context_parts.append("")
                context_parts.append("Locations:")
                for loc in locs[:10]:
                    tag = loc.get('tag', '')
                    name = loc.get('name', '')
                    context_parts.append(f"  - [{tag}]: {name}")

        context_parts.extend([
            "",
            "=== QUALITY FEEDBACK (for awareness) ===",
            quality_feedback if quality_feedback else "(No issues logged)",
            "",
            "=== CURRENT SCRIPT ===",
            script_content,
            "",
            "=== TASK ===",
            "Review the script and produce the FINAL version.",
            "Ensure:",
            "1. All scenes use ## Scene N: format (scene-only, no beat markers)",
            "2. All character tags use [CHAR_NAME] format",
            "3. All location tags use [LOC_NAME] format",
            "4. All prop tags use [PROP_NAME] format",
            "5. Continuous prose within each scene (no subdivisions)",
            "6. Narrative flows naturally from scene to scene",
            "7. Character actions align with their established arcs",
            "",
            "Output ONLY the final script content. No explanations or meta-commentary.",
            "Start with ## Scene 1: and continue through all scenes.",
        ])

        full_context = "\n".join(context_parts)

        # Use Claude Opus 4.5 directly (hardcoded for high-quality final assembly)
        try:
            response = await asyncio.to_thread(
                self._anthropic_client.generate_text,
                full_context,
                system="You are the Full Context Assembly Agent. Produce the final script.md with proper scene-only structure and tag notation. Output ONLY the script content.",
                max_tokens=8000,
                model="claude-opus-4-5-20251101"
            )

            if response and len(response.strip()) > 100:
                self._log_agent_operation("Assembly complete",
                                          f"{len(response)} chars")
                return response.strip()
            else:
                logger.warning("Assembly Agent returned insufficient content, using original")
                return script_content

        except Exception as e:
            logger.error(f"Full Context Assembly failed: {e}")
            self._log_agent_operation("Assembly failed", str(e))
            return script_content

    # =========================================================================
    # PRE-PROCESSING STEPS
    # =========================================================================

    async def _parse_input(
        self,
        input_data: StoryInput,
        context: Dict
    ) -> Dict[str, Any]:
        """Parse and clean the input."""
        cleaned_text = input_data.raw_text.strip()
        existing_tags = self.tag_parser.extract_unique_tags(cleaned_text)

        # Determine scene count: dynamic (pitch-driven) or static (preset-based)
        if input_data.dynamic_scenes or input_data.project_size == "dynamic":
            # Use PitchAnalyzer to determine optimal scene count
            analyzer = PitchAnalyzer()
            pitch_metrics = analyzer.analyze(
                pitch_text=cleaned_text,
                genre=input_data.genre,
                existing_tags=list(existing_tags)
            )

            size_config = {
                "target_words": pitch_metrics.recommended_scenes * pitch_metrics.words_per_scene,
                "scenes": pitch_metrics.recommended_scenes,
                "words_per_scene": pitch_metrics.words_per_scene,
            }

            self._log_agent_operation(
                "Dynamic scene analysis",
                f"{pitch_metrics.recommended_scenes} scenes (range: {pitch_metrics.min_scenes}-{pitch_metrics.max_scenes})"
            )
            self._log_agent_operation("Analysis reasoning", pitch_metrics.reasoning)
        else:
            # Use static SIZE_CONFIG presets
            size_config = self.SIZE_CONFIG.get(input_data.project_size, self.SIZE_CONFIG["short"])
            pitch_metrics = None

        return {
            'text': cleaned_text,
            'title': input_data.title,
            'genre': input_data.genre,
            'visual_style': input_data.visual_style,
            'style_notes': input_data.style_notes,
            'existing_tags': list(existing_tags),
            'project_size': input_data.project_size,
            'size_config': size_config,
            'pitch_metrics': pitch_metrics,  # Store for later use if needed
        }

    async def _extract_tags(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Extract and validate tags using multi-agent consensus."""
        self._log_agent_operation("Initializing multi-agent consensus tagger")
        self._log_agent_operation("Deploying tag extraction agents", f"Genre: {data['genre']}")

        # Filter out placeholder tags from the text before extraction
        text_to_analyze = data['text']
        # Remove common placeholder patterns
        placeholder_patterns = [
            "(To be developed - add character entries with [CHARACTER_NAME] tags)",
            "(To be developed - add location entries with [LOC_NAME] tags)",
            "(To be developed)",
            "[CHARACTER_NAME]",
            "[LOC_NAME]"
        ]
        for pattern in placeholder_patterns:
            text_to_analyze = text_to_analyze.replace(pattern, "")

        # Use consensus tagger for tag extraction
        result = await self.consensus_tagger.extract_with_consensus(
            text_to_analyze,
            context=f"Genre: {data['genre']}"
        )

        self._log_agent_operation("Agents completed tag extraction", f"{len(result.consensus_tags)} tags found")
        self._log_agent_operation("Calculating consensus scores")

        # Filter out any remaining placeholder tags
        filtered_tags = {
            tag for tag in result.consensus_tags
            if tag not in {'CHARACTER_NAME', 'LOC_NAME', 'PROP_NAME'}
        }

        # Separate by category based on prefix
        character_tags = []
        location_tags = []
        prop_tags = []
        concept_tags = []
        event_tags = []

        for tag in filtered_tags:
            if tag.startswith('CHAR_'):
                character_tags.append(tag)
            elif tag.startswith('LOC_'):
                location_tags.append(tag)
            elif tag.startswith('PROP_'):
                prop_tags.append(tag)
            elif tag.startswith('CONCEPT_'):
                concept_tags.append(tag)
            elif tag.startswith('EVENT_'):
                event_tags.append(tag)
            else:
                # Legacy tags without prefix - try to categorize
                logger.warning(f"Tag without proper prefix: {tag} - skipping")

        data['all_tags'] = list(filtered_tags)
        data['character_tags'] = character_tags
        data['location_tags'] = location_tags
        data['prop_tags'] = prop_tags
        data['concept_tags'] = concept_tags
        data['event_tags'] = event_tags
        data['consensus_score'] = sum(result.agreement_ratios.values()) / max(len(result.agreement_ratios), 1) if result.agreement_ratios else 0.0

        self._log_agent_operation("Tag categorization complete",
                                  f"{len(character_tags)} chars, {len(location_tags)} locs, {len(prop_tags)} props, {len(concept_tags)} concepts, {len(event_tags)} events")
        self._log_agent_operation("Consensus score", f"{data['consensus_score']:.2%}")

        # Generate detailed descriptions for locations and props
        if location_tags:
            data['location_descriptions'] = await self._generate_location_descriptions(data, location_tags)
        if prop_tags:
            data['prop_descriptions'] = await self._generate_prop_descriptions(data, prop_tags)

        return data

    async def _generate_world_overview(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Generate world overview: logline, synopsis, themes, world_rules, lighting, vibe."""
        logger.info("Generating world overview...")
        self._log_agent_operation("Generating world overview from pitch")

        visual_style = data.get('visual_style', 'live_action')
        style_notes = data.get('style_notes', '')
        genre = data.get('genre', '')

        # Map visual style to descriptive text
        style_descriptions = {
            "live_action": "photorealistic live-action cinematography",
            "anime": "Japanese anime style with expressive characters",
            "animation_2d": "traditional 2D animation style",
            "animation_3d": "modern 3D computer animation",
            "mixed_reality": "blend of live action and CGI elements"
        }
        style_desc = style_descriptions.get(visual_style, visual_style)

        prompt = f"""Analyze this story pitch and generate a comprehensive world overview.

PITCH:
{data['text']}

GENRE: {genre}
VISUAL STYLE: {style_desc}
STYLE NOTES: {style_notes if style_notes else "None provided"}

Generate the following sections:

1. LOGLINE: A single compelling sentence that captures the essence of the story (who, what, stakes)

2. SYNOPSIS: A 2-3 paragraph summary expanding on the pitch, covering setup, conflict, and resolution

3. THEMES: The core themes explored in this story (e.g., redemption, freedom, love, power)

4. WORLD RULES: Any special rules, systems, or constraints in this world (magic systems, technology, social structures, historical context)

5. LIGHTING: Recommended lighting style that matches the visual style and mood (e.g., "Chiaroscuro with dramatic shadows", "Soft natural lighting", "Neon-lit cyberpunk aesthetic")

6. VIBE: The overall mood and atmosphere in 3-5 descriptive words (e.g., "Cinematic, moody, intimate", "Epic, sweeping, triumphant")

Format your response exactly as:
LOGLINE: [your logline]

SYNOPSIS:
[your synopsis]

THEMES: [theme1], [theme2], [theme3]

WORLD RULES:
[your world rules]

LIGHTING: [lighting description]

VIBE: [vibe words]"""

        response = await self.function_router.route(
            function=LLMFunction.STORY_ANALYSIS,
            prompt=prompt,
            system_prompt="You are a world-building expert. Create rich, cohesive world overviews that establish tone and rules."
        )

        # Parse the response
        world_overview = self._parse_world_overview(response)

        data['logline'] = world_overview.get('logline', '')
        data['synopsis'] = world_overview.get('synopsis', '')
        data['themes'] = world_overview.get('themes', '')
        data['world_rules'] = world_overview.get('world_rules', '')
        data['lighting'] = world_overview.get('lighting', '')
        data['vibe'] = world_overview.get('vibe', '')

        self._log_agent_operation("World overview complete",
                                  f"Logline: {len(data['logline'])} chars, Synopsis: {len(data['synopsis'])} chars")

        return data

    def _parse_world_overview(self, response: str) -> Dict[str, str]:
        """Parse world overview from LLM response."""
        import re
        result = {}

        # Extract LOGLINE
        logline_match = re.search(r'LOGLINE:\s*(.+?)(?=\n\n|\nSYNOPSIS:|\Z)', response, re.DOTALL)
        if logline_match:
            result['logline'] = logline_match.group(1).strip()

        # Extract SYNOPSIS
        synopsis_match = re.search(r'SYNOPSIS:\s*(.+?)(?=\nTHEMES:|\Z)', response, re.DOTALL)
        if synopsis_match:
            result['synopsis'] = synopsis_match.group(1).strip()

        # Extract THEMES
        themes_match = re.search(r'THEMES:\s*(.+?)(?=\n\n|\nWORLD RULES:|\Z)', response, re.DOTALL)
        if themes_match:
            result['themes'] = themes_match.group(1).strip()

        # Extract WORLD RULES
        rules_match = re.search(r'WORLD RULES:\s*(.+?)(?=\nLIGHTING:|\Z)', response, re.DOTALL)
        if rules_match:
            result['world_rules'] = rules_match.group(1).strip()

        # Extract LIGHTING
        lighting_match = re.search(r'LIGHTING:\s*(.+?)(?=\n\n|\nVIBE:|\Z)', response, re.DOTALL)
        if lighting_match:
            result['lighting'] = lighting_match.group(1).strip()

        # Extract VIBE
        vibe_match = re.search(r'VIBE:\s*(.+?)(?=\n\n|\Z)', response, re.DOTALL)
        if vibe_match:
            result['vibe'] = vibe_match.group(1).strip()

        return result

    async def _generate_location_descriptions(
        self,
        data: Dict[str, Any],
        location_tags: List[str]
    ) -> List[LocationDescription]:
        """Generate detailed descriptions for locations with directional views."""
        self._log_agent_operation("Generating location descriptions", f"{len(location_tags)} locations")

        visual_style = data.get('visual_style', 'live_action')
        style_notes = data.get('style_notes', '')

        prompt = f"""Generate detailed visual descriptions for each location in this story.

STORY:
{data['text']}

VISUAL STYLE: {visual_style}
STYLE NOTES: {style_notes}

LOCATIONS TO DESCRIBE: {', '.join(f'[{tag}]' for tag in location_tags)}

For each location, provide:
1. NAME: Human-readable name
2. DESCRIPTION: General description of the place
3. TIME_PERIOD: Historical/setting context
4. ATMOSPHERE: Mood, lighting, ambiance
5. DIRECTIONAL VIEWS (for consistent camera framing):
   - VIEW_NORTH: What you see looking north
   - VIEW_EAST: What you see looking east
   - VIEW_SOUTH: What you see looking south
   - VIEW_WEST: What you see looking west

Format each location as:
LOCATION: [TAG]
Name: [human readable name]
Description: [general description]
Time Period: [era/setting]
Atmosphere: [mood and lighting]
View North: [description]
View East: [description]
View South: [description]
View West: [description]

Describe all locations:"""

        response = await self.function_router.route(
            function=LLMFunction.STORY_ANALYSIS,
            prompt=prompt,
            system_prompt="You are a production designer. Create vivid, filmable location descriptions."
        )

        return self._parse_location_descriptions(response, location_tags)

    def _parse_location_descriptions(self, response: str, location_tags: List[str]) -> List[LocationDescription]:
        """Parse location descriptions from LLM response."""
        descriptions = []
        blocks = re.split(r'LOCATION:\s*\[?', response, flags=re.IGNORECASE)

        for block in blocks[1:]:
            tag_match = re.match(r'([A-Z_]+)\]?', block)
            if not tag_match:
                continue

            tag = tag_match.group(1)
            name = re.search(r'Name:\s*(.+?)(?:\n|$)', block)
            desc = re.search(r'Description:\s*(.+?)(?:\n|$)', block)
            time_period = re.search(r'Time Period:\s*(.+?)(?:\n|$)', block)
            atmosphere = re.search(r'Atmosphere:\s*(.+?)(?:\n|$)', block)
            view_n = re.search(r'View North:\s*(.+?)(?:\n|$)', block)
            view_e = re.search(r'View East:\s*(.+?)(?:\n|$)', block)
            view_s = re.search(r'View South:\s*(.+?)(?:\n|$)', block)
            view_w = re.search(r'View West:\s*(.+?)(?:\n|$)', block)

            descriptions.append(LocationDescription(
                location_tag=tag,
                location_name=name.group(1).strip() if name else tag.replace('LOC_', '').replace('_', ' ').title(),
                description=desc.group(1).strip() if desc else "",
                time_period=time_period.group(1).strip() if time_period else "",
                atmosphere=atmosphere.group(1).strip() if atmosphere else "",
                view_north=view_n.group(1).strip() if view_n else "",
                view_east=view_e.group(1).strip() if view_e else "",
                view_south=view_s.group(1).strip() if view_s else "",
                view_west=view_w.group(1).strip() if view_w else ""
            ))

        # Create basic descriptions for any missing locations
        parsed_tags = {d.location_tag for d in descriptions}
        for tag in location_tags:
            if tag not in parsed_tags:
                descriptions.append(LocationDescription(
                    location_tag=tag,
                    location_name=tag.replace('LOC_', '').replace('_', ' ').title(),
                    description="", time_period="", atmosphere="",
                    view_north="", view_east="", view_south="", view_west=""
                ))

        self._log_agent_operation("Location descriptions complete", f"{len(descriptions)} locations")
        return descriptions

    async def _generate_prop_descriptions(
        self,
        data: Dict[str, Any],
        prop_tags: List[str]
    ) -> List[PropDescription]:
        """Generate detailed descriptions for props."""
        self._log_agent_operation("Generating prop descriptions", f"{len(prop_tags)} props")

        visual_style = data.get('visual_style', 'live_action')
        style_notes = data.get('style_notes', '')

        prompt = f"""Generate detailed visual descriptions for each prop in this story.

STORY:
{data['text']}

VISUAL STYLE: {visual_style}
STYLE NOTES: {style_notes}

PROPS TO DESCRIBE: {', '.join(f'[{tag}]' for tag in prop_tags)}

For each prop, provide:
1. NAME: Human-readable name
2. DESCRIPTION: What the prop is
3. APPEARANCE: Detailed visual description (color, material, size, condition, style)
4. SIGNIFICANCE: Story or symbolic importance
5. ASSOCIATED_CHARACTER: Which character it belongs to or is associated with (use CHAR_ tag)

Format each prop as:
PROP: [TAG]
Name: [human readable name]
Description: [what it is]
Appearance: [detailed visual description]
Significance: [story importance]
Associated Character: [CHAR_TAG or "none"]

Describe all props:"""

        response = await self.function_router.route(
            function=LLMFunction.STORY_ANALYSIS,
            prompt=prompt,
            system_prompt="You are a prop master. Create detailed, filmable prop descriptions."
        )

        return self._parse_prop_descriptions(response, prop_tags)

    def _parse_prop_descriptions(self, response: str, prop_tags: List[str]) -> List[PropDescription]:
        """Parse prop descriptions from LLM response."""
        descriptions = []
        blocks = re.split(r'PROP:\s*\[?', response, flags=re.IGNORECASE)

        for block in blocks[1:]:
            tag_match = re.match(r'([A-Z_]+)\]?', block)
            if not tag_match:
                continue

            tag = tag_match.group(1)
            name = re.search(r'Name:\s*(.+?)(?:\n|$)', block)
            desc = re.search(r'Description:\s*(.+?)(?:\n|$)', block)
            appearance = re.search(r'Appearance:\s*(.+?)(?:\n|$)', block)
            significance = re.search(r'Significance:\s*(.+?)(?:\n|$)', block)
            assoc_char = re.search(r'Associated Character:\s*(.+?)(?:\n|$)', block)

            descriptions.append(PropDescription(
                prop_tag=tag,
                prop_name=name.group(1).strip() if name else tag.replace('PROP_', '').replace('_', ' ').title(),
                description=desc.group(1).strip() if desc else "",
                appearance=appearance.group(1).strip() if appearance else "",
                significance=significance.group(1).strip() if significance else "",
                associated_character=assoc_char.group(1).strip() if assoc_char else ""
            ))

        # Create basic descriptions for any missing props
        parsed_tags = {d.prop_tag for d in descriptions}
        for tag in prop_tags:
            if tag not in parsed_tags:
                descriptions.append(PropDescription(
                    prop_tag=tag,
                    prop_name=tag.replace('PROP_', '').replace('_', ' ').title(),
                    description="", appearance="", significance="", associated_character=""
                ))

        self._log_agent_operation("Prop descriptions complete", f"{len(descriptions)} props")
        return descriptions

    # =========================================================================
    # LAYER 1: PLOT ARCHITECTURE
    # =========================================================================

    async def _layer1_plot_architecture(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Layer 1: Build plot structure and identify key plot points."""
        logger.info("Layer 1: Building plot architecture...")
        self._log_agent_operation("Analyzing story structure")

        size_config = data['size_config']
        target_scenes = size_config['scenes']

        self._log_agent_operation("Target configuration", f"{target_scenes} scenes, {data['project_size']} format")
        self._log_agent_operation("Deploying plot architecture agent")

        prompt = f"""Analyze this story and create a plot architecture.

STORY:
{data['text']}

GENRE: {data['genre']}
TARGET SCENES: {target_scenes}

Create a structured plot breakdown with:

1. THREE-ACT STRUCTURE:
   - Act 1 (Setup, ~25%): Introduce world, characters, inciting incident
   - Act 2 (Confrontation, ~50%): Rising action, midpoint, complications
   - Act 3 (Resolution, ~25%): Climax, falling action, resolution

2. KEY PLOT POINTS (identify each with position 0.0-1.0):
   - Opening Image (0.0)
   - Inciting Incident (~0.12)
   - First Plot Point (~0.25)
   - Midpoint (~0.50)
   - Second Plot Point (~0.75)
   - Climax (~0.90)
   - Resolution (~1.0)

Format each plot point as:
PLOT_POINT: [type] | Position: [0.0-1.0] | Act: [1/2/3]
Characters: [character tags]
Location: [location tag]
Description: [what happens]

List all plot points:"""

        self._log_agent_operation("Sending request to LLM", "Story Analysis function")
        response = await self.function_router.route(
            function=LLMFunction.STORY_ANALYSIS,
            prompt=prompt,
            system_prompt="You are a story structure analyst. Create clear, actionable plot architectures."
        )

        self._log_agent_operation("Received plot architecture response", f"{len(response)} chars")
        self._log_agent_operation("Parsing plot points from response")

        # Parse plot points from response
        plot_points = self._parse_plot_points(response, data)
        data['plot_points'] = plot_points
        data['plot_architecture_raw'] = response

        self._log_agent_operation("Plot architecture complete", f"{len(plot_points)} plot points identified")

        return data

    def _parse_plot_points(self, response: str, data: Dict) -> List[PlotPoint]:
        """Parse plot points from LLM response."""
        import re
        plot_points = []

        # Pattern to match plot point blocks
        pattern = r'PLOT_POINT:\s*([^|]+)\|\s*Position:\s*([\d.]+)\s*\|\s*Act:\s*(\d)'
        matches = re.findall(pattern, response, re.IGNORECASE)

        for i, (point_type, position, act) in enumerate(matches):
            # Extract description (text after the match until next PLOT_POINT or end)
            plot_points.append(PlotPoint(
                point_id=f"PP{i+1:02d}",
                act=int(act),
                position=float(position),
                point_type=point_type.strip().lower().replace(' ', '_'),
                description=point_type.strip(),
                characters_involved=data.get('character_tags', [])[:3],
                location=data.get('location_tags', [''])[0] if data.get('location_tags') else ""
            ))

        # If no matches, create basic structure
        if not plot_points:
            plot_points = [
                PlotPoint("PP01", 1, 0.0, "opening", "Story opening", [], ""),
                PlotPoint("PP02", 1, 0.12, "inciting_incident", "Inciting incident", [], ""),
                PlotPoint("PP03", 2, 0.50, "midpoint", "Story midpoint", [], ""),
                PlotPoint("PP04", 3, 0.90, "climax", "Story climax", [], ""),
                PlotPoint("PP05", 3, 1.0, "resolution", "Resolution", [], ""),
            ]

        return plot_points

    # =========================================================================
    # LAYER 2: CHARACTER ARCHITECTURE
    # =========================================================================

    async def _layer2_character_architecture(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Layer 2: Define character arcs and relationships."""
        logger.info("Layer 2: Building character architecture...")
        self._log_agent_operation("Analyzing character development")

        character_tags = data.get('character_tags', [])

        if not character_tags:
            self._log_agent_operation("No characters found, skipping layer")
            data['character_arcs'] = []
            return data

        # DIAGNOSTIC LOGGING: Log all consensus-approved character tags being sent to LLM
        logger.info(f"📋 Character Architecture Input - {len(character_tags)} consensus-approved character tags:")
        for tag in character_tags:
            logger.info(f"   • [{tag}]")

        self._log_agent_operation("Characters identified", f"{len(character_tags)} characters")
        self._log_agent_operation("Deploying character architecture agent")

        visual_style = data.get('visual_style', 'live_action')
        style_notes = data.get('style_notes', '')
        world_rules = data.get('world_rules', '')
        genre = data.get('genre', '')

        prompt = f"""Analyze the characters in this story and create RICH CHARACTER PROFILES (125-250 words each).

STORY:
{data['text']}

GENRE: {genre}
VISUAL STYLE: {visual_style}
STYLE NOTES: {style_notes}

=== WORLD CONTEXT (CRITICAL FOR COSTUME/SETTING ACCURACY) ===
{world_rules if world_rules else "Infer time period and setting from the story pitch."}

IMPORTANT: All character costumes MUST be period-accurate and setting-appropriate based on the world context above. If the story is set in historical East Asia, characters should wear traditional clothing (hanfu, changshan, ruqun, etc.). If set in medieval Europe, they wear period-appropriate garments. NEVER use modern clothing unless the world context explicitly indicates a modern setting.

IDENTIFIED CHARACTERS: {', '.join(f'[{tag}]' for tag in character_tags)}

For each character, provide DETAILED multi-paragraph descriptions:

## CHARACTER DEVELOPMENT:
1. ROLE: protagonist, antagonist, mentor, ally, love_interest, etc.
2. WANT: Their external goal - what they're actively pursuing (2-3 sentences)
3. NEED: Their internal need - what they must learn/accept to grow (2-3 sentences)
4. FLAW: Their character flaw that creates conflict and holds them back (2-3 sentences)
5. ARC TYPE: positive (overcomes flaw), negative (succumbs), flat (changes others)

## VISUAL DESCRIPTION (50-100 words each - CRITICAL for storyboard generation):
6. AGE: Specific age range with context (e.g., "mid-20s, youthful but with eyes that suggest wisdom beyond her years")
7. ETHNICITY: Cultural/ethnic background with visual implications
8. APPEARANCE: DETAILED multi-sentence physical description including:
   - Height and build with posture notes
   - Hair color, style, length, texture
   - Eye color, shape, and expressiveness
   - Skin tone and complexion
   - Distinguishing features (scars, marks, unique traits)
   - Overall impression/aura they project
9. COSTUME: DETAILED period-accurate signature clothing (30-50 words) with:
   - Specific garments appropriate to the world's time period and culture
   - Colors, fabrics, and materials authentic to the setting
   - Condition and wear patterns reflecting character's status
   - Accessories and adornments typical of the era
   - MUST match the historical/cultural context from WORLD CONTEXT above

## PSYCHOLOGICAL PROFILE (50-75 words):
10. PSYCHOLOGY: Core psychological makeup including:
    - Dominant personality traits
    - Deepest fears and desires
    - Coping mechanisms under stress
    - Blind spots and vulnerabilities

## VOICE AND SPEECH (30-50 words):
11. SPEECH_PATTERNS: How they speak including:
    - Vocabulary level and sources
    - Sentence structure (complex vs simple)
    - Verbal habits and tics
    - Topics they avoid
12. SPEECH_STYLE: Formal/informal, direct/indirect, metaphorical/literal
13. LITERACY_LEVEL: Education reflected in speech

## PHYSICALITY (30-50 words):
14. PHYSICALITY: How they move and occupy space:
    - Movement style (graceful, deliberate, nervous)
    - Signature gestures
    - Body language patterns
    - Physical tells when emotional

## DECISION MAKING:
15. DECISION_HEURISTICS: How they make choices:
    - Moral compass orientation
    - Risk tolerance
    - Trust threshold
    - What triggers action vs hesitation

## EMOTIONAL TELLS (one sentence each):
16. EMOTIONAL_TELLS: Physical manifestations of emotions:
    - FEAR: [physical response]
    - ANGER: [physical response]
    - JOY: [physical response]
    - SADNESS: [physical response]
    - VULNERABILITY: [physical response]

## RELATIONSHIPS:
17. KEY_MOMENTS: 3-5 pivotal moments in their journey
18. RELATIONSHIPS: How they relate to other characters

Format each character EXACTLY as (use ||| as multi-line delimiter):
===CHARACTER_START===
TAG: [TAG]
NAME: [full name]
ROLE: [role]
WANT: [2-3 sentence external goal]
NEED: [2-3 sentence internal need]
FLAW: [2-3 sentence character flaw]
ARC: [positive/negative/flat]
AGE: [age with context]
ETHNICITY: [cultural background]
APPEARANCE: [50-100 word detailed physical description]
COSTUME: [30-50 word detailed clothing description]
PSYCHOLOGY: [50-75 word psychological profile]
SPEECH_PATTERNS: [30-50 word speech description]
SPEECH_STYLE: [formal/informal, direct/indirect]
LITERACY_LEVEL: [education level]
PHYSICALITY: [30-50 word movement/gesture description]
DECISION_HEURISTICS: [decision-making patterns]
EMOTIONAL_TELLS:
- FEAR: [physical response]
- ANGER: [physical response]
- JOY: [physical response]
- SADNESS: [physical response]
- VULNERABILITY: [physical response]
KEY_MOMENTS: [moment1] ||| [moment2] ||| [moment3]
RELATIONSHIPS: [OTHER_TAG]: [relationship description]
===CHARACTER_END===

Create RICH, DETAILED profiles for all characters:"""

        self._log_agent_operation("Sending request to LLM", "Character Analysis function")
        response = await self.function_router.route(
            function=LLMFunction.STORY_ANALYSIS,
            prompt=prompt,
            system_prompt="You are a character development specialist. Create deep, meaningful character arcs."
        )

        self._log_agent_operation("Received character architecture response", f"{len(response)} chars")
        self._log_agent_operation("Parsing character arcs from response")

        character_arcs = self._parse_character_arcs(response, character_tags)
        data['character_arcs'] = character_arcs
        data['character_architecture_raw'] = response

        self._log_agent_operation("Character architecture complete", f"{len(character_arcs)} character arcs defined")

        return data

    def _parse_character_arcs(self, response: str, character_tags: List[str]) -> List[CharacterArc]:
        """Parse rich character arcs from LLM response.

        Handles both new structured format (===CHARACTER_START===) and legacy format.
        """
        import re
        arcs = []

        # Try new structured format first
        char_blocks = re.findall(
            r'===CHARACTER_START===(.*?)===CHARACTER_END===',
            response,
            re.DOTALL | re.IGNORECASE
        )

        if char_blocks:
            # Parse new structured format
            for block in char_blocks:
                arc = self._parse_structured_character_block(block)
                if arc:
                    arcs.append(arc)
        else:
            # Fallback to legacy parsing
            arcs = self._parse_legacy_character_blocks(response, character_tags)

        # If no arcs parsed, create basic ones from tags
        if not arcs and character_tags:
            logger.warning("No character arcs parsed from LLM response, creating fallback arcs for all characters")
            for i, tag in enumerate(character_tags):
                arcs.append(CharacterArc(
                    character_tag=tag,
                    character_name=tag.replace('_', ' ').replace('CHAR_', '').title(),
                    role="protagonist" if i == 0 else "supporting",
                    want="", need="", flaw="",
                    arc_type="positive",
                    age="", ethnicity="", appearance="", costume="",
                    key_moments=[], relationships={}
                ))

        # VALIDATION: Ensure ALL consensus-approved character tags have corresponding arcs
        # This prevents characters from being dropped if LLM response parsing fails for some
        parsed_tags = {arc.character_tag for arc in arcs}
        missing_tags = set(character_tags) - parsed_tags

        if missing_tags:
            logger.warning(f"⚠️ Characters approved by consensus but missing from LLM response: {missing_tags}")
            self._log_agent_operation(
                "Missing character arcs detected",
                f"Creating fallback arcs for: {', '.join(missing_tags)}"
            )
            for tag in sorted(missing_tags):
                logger.info(f"Creating fallback arc for missing character: [{tag}]")
                arcs.append(CharacterArc(
                    character_tag=tag,
                    character_name=tag.replace('CHAR_', '').replace('_', ' ').title(),
                    role="supporting",
                    want="Character goal to be defined",
                    need="Character need to be defined",
                    flaw="Character flaw to be defined",
                    arc_type="positive",
                    age="",
                    ethnicity="",
                    appearance="Appearance to be defined based on story context",
                    costume="Costume to be defined based on story context",
                    key_moments=[],
                    relationships={}
                ))

        # Log final parsing results
        logger.info(f"✅ Character arc parsing complete: {len(arcs)} arcs for {len(character_tags)} consensus tags")
        if len(arcs) == len(character_tags):
            logger.info(f"   All consensus-approved characters have arcs: {', '.join(sorted(parsed_tags))}")

        return arcs

    def _parse_structured_character_block(self, block: str) -> Optional[CharacterArc]:
        """Parse a single structured character block."""
        import re

        def extract_field(field_name: str, until_next: bool = True) -> str:
            """Extract field value, optionally capturing multi-line content."""
            if until_next:
                # Capture until next field or end of block
                pattern = rf'{field_name}:\s*(.+?)(?=\n[A-Z_]+:|$)'
                match = re.search(pattern, block, re.DOTALL | re.IGNORECASE)
            else:
                # Single line only
                pattern = rf'{field_name}:\s*(.+?)(?:\n|$)'
                match = re.search(pattern, block, re.IGNORECASE)
            return match.group(1).strip() if match else ""

        def extract_emotional_tells() -> Dict[str, str]:
            """Extract emotional tells section."""
            tells = {}
            tells_match = re.search(
                r'EMOTIONAL_TELLS:(.*?)(?=KEY_MOMENTS:|RELATIONSHIPS:|===CHARACTER_END===|$)',
                block,
                re.DOTALL | re.IGNORECASE
            )
            if tells_match:
                tells_text = tells_match.group(1)
                for emotion in ['FEAR', 'ANGER', 'JOY', 'SADNESS', 'VULNERABILITY']:
                    emotion_match = re.search(rf'-?\s*{emotion}:\s*(.+?)(?:\n|$)', tells_text, re.IGNORECASE)
                    if emotion_match:
                        tells[emotion.lower()] = emotion_match.group(1).strip()
            return tells

        def extract_key_moments() -> List[str]:
            """Extract key moments list."""
            moments_match = re.search(r'KEY_MOMENTS:\s*(.+?)(?=RELATIONSHIPS:|===CHARACTER_END===|$)', block, re.DOTALL | re.IGNORECASE)
            if moments_match:
                moments_text = moments_match.group(1).strip()
                # Handle ||| delimiter or comma-separated
                if '|||' in moments_text:
                    return [m.strip() for m in moments_text.split('|||') if m.strip()]
                else:
                    return [m.strip() for m in moments_text.split(',') if m.strip()]
            return []

        def extract_relationships() -> Dict[str, str]:
            """Extract relationships dict."""
            rels = {}
            rels_match = re.search(r'RELATIONSHIPS:\s*(.+?)(?====CHARACTER_END===|$)', block, re.DOTALL | re.IGNORECASE)
            if rels_match:
                rels_text = rels_match.group(1).strip()
                # Parse [TAG]: description or TAG: description
                for line in rels_text.split('\n'):
                    rel_match = re.match(r'\[?([A-Z_]+)\]?:\s*(.+)', line.strip())
                    if rel_match:
                        rels[rel_match.group(1)] = rel_match.group(2).strip()
            return rels

        # Extract tag
        tag_match = re.search(r'TAG:\s*\[?([A-Z_]+)\]?', block, re.IGNORECASE)
        if not tag_match:
            return None
        tag = tag_match.group(1)

        return CharacterArc(
            character_tag=tag,
            character_name=extract_field('NAME', False) or tag.replace('_', ' ').title(),
            role=extract_field('ROLE', False).lower() or "supporting",
            want=extract_field('WANT', True),
            need=extract_field('NEED', True),
            flaw=extract_field('FLAW', True),
            arc_type=extract_field('ARC', False).lower() or "positive",
            age=extract_field('AGE', True),
            ethnicity=extract_field('ETHNICITY', True),
            appearance=extract_field('APPEARANCE', True),
            costume=extract_field('COSTUME', True),
            psychology=extract_field('PSYCHOLOGY', True),
            speech_patterns=extract_field('SPEECH_PATTERNS', True),
            speech_style=extract_field('SPEECH_STYLE', False),
            literacy_level=extract_field('LITERACY_LEVEL', False),
            physicality=extract_field('PHYSICALITY', True),
            decision_heuristics=extract_field('DECISION_HEURISTICS', True),
            emotional_tells=extract_emotional_tells(),
            key_moments=extract_key_moments(),
            relationships=extract_relationships()
        )

    def _parse_legacy_character_blocks(self, response: str, character_tags: List[str]) -> List[CharacterArc]:
        """Parse legacy CHARACTER: format for backward compatibility."""
        import re
        arcs = []

        blocks = re.split(r'CHARACTER:\s*\[?', response, flags=re.IGNORECASE)

        for block in blocks[1:]:
            tag_match = re.match(r'([A-Z_]+)\]?', block)
            if not tag_match:
                continue

            tag = tag_match.group(1)

            # Extract fields - try multi-line first, fall back to single line
            def get_field(name: str) -> str:
                # Try multi-line (until next field)
                multi = re.search(rf'{name}:\s*(.+?)(?=\n[A-Za-z_]+:|$)', block, re.DOTALL | re.IGNORECASE)
                if multi:
                    return multi.group(1).strip()
                # Fall back to single line
                single = re.search(rf'{name}:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
                return single.group(1).strip() if single else ""

            arcs.append(CharacterArc(
                character_tag=tag,
                character_name=get_field('Name') or tag.replace('_', ' ').title(),
                role=get_field('Role').lower() or "supporting",
                want=get_field('Want'),
                need=get_field('Need'),
                flaw=get_field('Flaw'),
                arc_type=get_field('Arc').lower() or "positive",
                age=get_field('Age'),
                ethnicity=get_field('Ethnicity'),
                appearance=get_field('Appearance'),
                costume=get_field('Costume'),
                psychology=get_field('Psychology'),
                speech_patterns=get_field('Speech_Patterns') or get_field('Speech Patterns'),
                speech_style=get_field('Speech_Style') or get_field('Speech Style'),
                literacy_level=get_field('Literacy_Level') or get_field('Literacy Level'),
                physicality=get_field('Physicality'),
                decision_heuristics=get_field('Decision_Heuristics') or get_field('Decision Heuristics'),
                key_moments=[],
                relationships={}
            ))

        return arcs

    # =========================================================================
    # NOTE: STORY NOVELLING (LAYER 3) REMOVED
    # Prose expansion is now handled by the Directing Pipeline.
    # The Story Pipeline outputs Script (scripts/script.md - structured story outline).
    # =========================================================================

    def _format_plot_points(self, plot_points: List[PlotPoint]) -> str:
        """Format plot points for prompt."""
        if not plot_points:
            return "No plot points defined"
        return "\n".join([
            f"- {pp.point_type} (Act {pp.act}, {pp.position:.0%}): {pp.description}"
            for pp in plot_points
        ])

    def _format_character_arcs(self, arcs: List[CharacterArc]) -> str:
        """Format character arcs for prompt."""
        if not arcs:
            return "No character arcs defined"
        return "\n".join([
            f"- [{arc.character_tag}] ({arc.role}): Want={arc.want}, Need={arc.need}"
            for arc in arcs
        ])

    def _parse_scenes_detailed(self, response: str, data: Dict) -> List[Scene]:
        """Parse detailed scenes from LLM response including new fields."""
        import re
        scenes = []
        target_scenes = data.get('size_config', {}).get('scenes', 8)

        # Split by SCENE markers (supports both "SCENE X:" and "## Scene X:")
        scene_blocks = re.split(r'(?:##\s*)?SCENE\s+(\d+):', response, flags=re.IGNORECASE)

        for i in range(1, len(scene_blocks), 2):
            if i + 1 >= len(scene_blocks):
                break

            scene_num = int(scene_blocks[i])
            content = scene_blocks[i + 1]

            # Extract scene metadata (original fields)
            location_match = re.search(r'Location:\s*\[?([A-Z_]+)\]?\s*-?\s*(.+?)(?:\n|$)', content)
            time_match = re.search(r'Time:\s*(.+?)(?:\n|$)', content)
            chars_match = re.search(r'Characters:\s*(.+?)(?:\n|$)', content)
            purpose_match = re.search(r'Purpose:\s*(.+?)(?:\n|$)', content)
            conflict_match = re.search(r'Conflict:\s*(.+?)(?:\n|$)', content)
            outcome_match = re.search(r'Outcome:\s*(.+?)(?:\n|$)', content)
            emotion_match = re.search(r'Emotional (?:Arc|Beat):\s*(.+?)(?:\n|$)', content)

            # Extract NEW fields for enhanced scene tracking
            transition_match = re.search(r'Transition:\s*(.+?)(?:\n|$)', content)
            time_jump_match = re.search(r'Time Jump:\s*(.+?)(?:\n|$)', content)
            themes_match = re.search(r'Themes? Advanced:\s*(.+?)(?:\n|$)', content)
            subtext_match = re.search(r'Subtext:\s*(.+?)(?:\n|$)', content)

            # Extract character tags from characters line
            chars_text = chars_match.group(1) if chars_match else ""
            char_tags = re.findall(r'\[([A-Z_]+)\]', chars_text)
            if not char_tags:
                char_tags = [c.strip() for c in chars_text.split(',') if c.strip()]

            # Extract all tags from content
            all_tags = re.findall(r'\[([A-Z_]+)\]', content)
            prop_tags = [tag for tag in all_tags if tag.startswith('PROP_')]

            # Extract prose content (everything after metadata lines)
            # Remove metadata lines to get pure prose
            prose_content = content
            for pattern in [r'Location:.*?\n', r'Time:.*?\n', r'Characters:.*?\n',
                           r'Purpose:.*?\n', r'Conflict:.*?\n', r'Outcome:.*?\n',
                           r'Emotional (?:Arc|Beat):.*?\n', r'Transition:.*?\n',
                           r'Time Jump:.*?\n', r'Themes? Advanced:.*?\n', r'Subtext:.*?\n']:
                prose_content = re.sub(pattern, '', prose_content, flags=re.IGNORECASE)
            prose_content = prose_content.strip()

            # Calculate scene weight based on position
            act = 1 if scene_num <= target_scenes * 0.25 else (2 if scene_num <= target_scenes * 0.75 else 3)
            scene_weight = 1.0
            if scene_num == 1:
                scene_weight = 1.2
            elif scene_num == target_scenes:
                scene_weight = 1.5
            elif act == 2 and scene_num == int(target_scenes * 0.5):
                scene_weight = 1.5
            elif act == 3 and scene_num >= int(target_scenes * 0.85):
                scene_weight = 2.0

            # Parse transition type
            transition_in = "CUT_TO"
            if transition_match:
                trans_text = transition_match.group(1).strip().upper().replace(" ", "_")
                if trans_text in ["FADE_IN", "DISSOLVE_TO", "FADE_TO", "MATCH_CUT", "SMASH_CUT",
                                  "CROSS_CUT", "FLASHBACK", "FLASH_FORWARD", "JUMP_CUT", "WIPE", "CUT_TO"]:
                    transition_in = trans_text

            # Parse themes advanced
            themes_advanced = []
            if themes_match:
                themes_text = themes_match.group(1).strip()
                # Split by commas or semicolons
                themes_advanced = [t.strip() for t in re.split(r'[,;]', themes_text) if t.strip()]

            scene = Scene(
                scene_id=f"S{scene_num:02d}",
                scene_number=scene_num,
                location_tag=location_match.group(1) if location_match else "",
                location_description=location_match.group(2).strip() if location_match else "",
                time_of_day=time_match.group(1).strip() if time_match else "day",
                characters_present=char_tags,
                purpose=purpose_match.group(1).strip() if purpose_match else "",
                conflict=conflict_match.group(1).strip() if conflict_match else "",
                outcome=outcome_match.group(1).strip() if outcome_match else "",
                emotional_arc=emotion_match.group(1).strip() if emotion_match else "",
                content=prose_content,
                tags=all_tags,
                prop_tags=prop_tags,
                # NEW fields
                weight=scene_weight,
                transition_in=transition_in,
                transition_out="CUT_TO",  # Will be set when next scene is processed
                time_jump=time_jump_match.group(1).strip() if time_jump_match else "",
                subtext_notes=subtext_match.group(1).strip() if subtext_match else "",
                themes_advanced=themes_advanced,
                thematic_resonance=subtext_match.group(1).strip() if subtext_match else "",
            )
            scenes.append(scene)

        # Set transition_out for each scene based on next scene's transition_in
        for i in range(len(scenes) - 1):
            scenes[i].transition_out = scenes[i + 1].transition_in
        if scenes:
            scenes[-1].transition_out = "FADE_OUT"  # Last scene fades out

        # If no scenes parsed, create basic structure
        if not scenes:
            scenes = [Scene(
                scene_id="S01", scene_number=1,
                location_tag="", location_description="",
                time_of_day="day", characters_present=[],
                purpose="", conflict="", outcome="", emotional_arc=""
            )]

        return scenes

    def _extract_scene_summary(self, scene_text: str, scene_num: int) -> str:
        """Extract a brief summary from a generated scene for context handoff.

        SCENE-ONLY ARCHITECTURE: Summarizes scene prose content.
        """
        import re

        # Try to extract key elements
        location_match = re.search(r'Location:\s*\[?([A-Z_]+)\]?\s*-?\s*(.+?)(?:\n|$)', scene_text)
        purpose_match = re.search(r'Purpose:\s*(.+?)(?:\n|$)', scene_text)
        emotional_match = re.search(r'Emotional (?:Arc|Beat):\s*(.+?)(?:\n|$)', scene_text)

        # Extract first 200 chars of prose content as summary
        prose_preview = ""
        lines = scene_text.split('\n')
        for line in lines:
            # Skip metadata lines
            if any(line.strip().startswith(prefix) for prefix in
                   ['Location:', 'Time:', 'Characters:', 'Purpose:', 'Conflict:', 'Outcome:', 'Emotional']):
                continue
            if line.strip() and len(line.strip()) > 20:
                prose_preview = line.strip()[:200]
                break

        summary_parts = [f"Scene {scene_num}:"]
        if location_match:
            summary_parts.append(f"Location: {location_match.group(1)}")
        if purpose_match:
            summary_parts.append(f"Purpose: {purpose_match.group(1).strip()[:100]}")
        if emotional_match:
            summary_parts.append(f"Emotional: {emotional_match.group(1).strip()[:50]}")
        if prose_preview:
            summary_parts.append(f"Preview: {prose_preview}...")

        return " | ".join(summary_parts)

    # =========================================================================
    # LAYER 3: CONTINUITY VALIDATION
    # =========================================================================

    async def _layer3_continuity_validation(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Layer 3: Check for continuity issues across scenes."""
        logger.info("Layer 3: Validating continuity...")
        self._log_agent_operation("Initiating continuity validation")

        scenes = data.get('scenes', [])
        if not scenes:
            self._log_agent_operation("No scenes to validate, skipping layer")
            data['continuity_issues'] = []
            data['continuity_status'] = ValidationStatus.PASSED
            return data

        self._log_agent_operation("Analyzing scene continuity", f"{len(scenes)} scenes")
        self._log_agent_operation("Deploying continuity validation agent")

        # Build scene summary for analysis
        scene_summary = "\n".join([
            f"Scene {s.scene_number}: {s.location_tag} - {', '.join(s.characters_present)} - {s.purpose}"
            for s in scenes
        ])

        prompt = f"""Check this story for continuity issues.

SCENES:
{scene_summary}

CHARACTER ARCS:
{self._format_character_arcs(data.get('character_arcs', []))}

Check for:
1. CHARACTER CONTINUITY: Characters appearing where they shouldn't be
2. LOCATION CONTINUITY: Impossible location transitions
3. TIMELINE CONTINUITY: Time inconsistencies
4. PROP CONTINUITY: Objects appearing/disappearing incorrectly
5. EMOTIONAL CONTINUITY: Jarring emotional shifts

For each issue found, format as:
ISSUE: [category]
Severity: [critical/warning/suggestion]
Scenes: [scene numbers]
Description: [what's wrong]
Fix: [suggested fix]

List all continuity issues (or state "No issues found"):"""

        self._log_agent_operation("Sending request to LLM", "Continuity Validation function")
        response = await self.function_router.route(
            function=LLMFunction.CONTINUITY,
            prompt=prompt,
            system_prompt="You are a script supervisor checking for continuity errors."
        )

        self._log_agent_operation("Received continuity validation response", f"{len(response)} chars")
        self._log_agent_operation("Parsing continuity issues from response")

        issues = self._parse_continuity_issues(response)
        data['continuity_issues'] = issues
        data['continuity_status'] = (
            ValidationStatus.FAILED if any(i.severity == "critical" for i in issues)
            else ValidationStatus.NEEDS_REVISION if issues
            else ValidationStatus.PASSED
        )

        critical_count = sum(1 for i in issues if i.severity == "critical")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        self._log_agent_operation("Continuity validation complete",
                                  f"{len(issues)} issues ({critical_count} critical, {warning_count} warnings)")

        # DIRECTIONAL TAG VALIDATION - 3-agent consensus
        self._log_agent_operation("Starting directional tag validation with 3-agent consensus")
        data = await self._validate_directional_tags(data, context)

        return data

    def _parse_continuity_issues(self, response: str) -> List[ContinuityIssue]:
        """Parse continuity issues from LLM response."""
        import re
        issues = []

        if "no issues found" in response.lower():
            return issues

        # Split by ISSUE markers
        issue_blocks = re.split(r'ISSUE:\s*', response, flags=re.IGNORECASE)

        for i, block in enumerate(issue_blocks[1:], 1):
            category_match = re.match(r'(.+?)(?:\n|$)', block)
            severity_match = re.search(r'Severity:\s*(.+?)(?:\n|$)', block)
            scenes_match = re.search(r'Scenes:\s*(.+?)(?:\n|$)', block)
            desc_match = re.search(r'Description:\s*(.+?)(?:\n|$)', block)
            fix_match = re.search(r'Fix:\s*(.+?)(?:\n|$)', block)

            issues.append(ContinuityIssue(
                issue_id=f"CI{i:02d}",
                severity=severity_match.group(1).strip().lower() if severity_match else "warning",
                category=category_match.group(1).strip().lower() if category_match else "general",
                description=desc_match.group(1).strip() if desc_match else block[:100],
                scene_refs=scenes_match.group(1).split(',') if scenes_match else [],
                suggested_fix=fix_match.group(1).strip() if fix_match else ""
            ))

        return issues

    async def _validate_directional_tags(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Validate and insert directional tags using 3-agent consensus.

        SCENE-ONLY ARCHITECTURE: Processes scenes directly, not beats.
        Directional tags are validated per-scene based on location_tag.
        """
        scenes = data.get('scenes', [])
        if not scenes:
            self._log_agent_operation("No scenes to validate, skipping directional tag validation")
            return data

        self._log_agent_operation("Validating directional tags", f"{len(scenes)} scenes")

        # Load world bible from context if available
        world_bible = context.get('world_bible', {})

        # Create LLM caller for directional consensus
        async def directional_llm_caller(prompt: str) -> str:
            """Async LLM caller for directional tag validation."""
            return await self.function_router.route(
                function=LLMFunction.TAG_VALIDATION,
                prompt=prompt,
                system_prompt="You are a cinematography expert analyzing camera directions and spatial positioning."
            )

        # Initialize directional tag consensus system
        directional_consensus = DirectionalTagConsensus(
            llm_caller=directional_llm_caller,
            world_bible=world_bible
        )

        # Track statistics
        validated_count = 0
        inserted_count = 0
        failed_count = 0

        # Process each scene
        for scene in scenes:
            if not scene.location_tag:
                continue

            # Check if scene already has directional tag in content
            if f"{scene.location_tag}_DIR_" in scene.content:
                validated_count += 1
                continue

            try:
                # Run 3-agent consensus
                result = await directional_consensus.validate_and_insert_directional_tag(
                    beat_content=scene.content,  # Using scene content
                    location_tag=scene.location_tag,
                    direction_text="",  # Scenes don't have explicit direction field
                    scene_context=scene.purpose,
                    characters=scene.characters_present,
                    props=scene.prop_tags if hasattr(scene, 'prop_tags') else []
                )

                if result.success and result.consensus_tag:
                    # Insert directional tag into scene content
                    old_tag = f"[{scene.location_tag}]"
                    new_tag = f"[{result.consensus_tag}]"
                    scene.content = scene.content.replace(old_tag, new_tag, 1)

                    # Update location_tag to include direction
                    scene.location_tag = result.consensus_tag

                    inserted_count += 1
                    self._log_agent_operation(
                        f"✓ Scene {scene.scene_number}",
                        f"{result.consensus_tag} ({result.agreement_ratio*100:.0f}% consensus)"
                    )
                else:
                    failed_count += 1
                    self._log_agent_operation(
                        f"✗ Scene {scene.scene_number}",
                        f"Failed to reach consensus ({result.agreement_ratio*100:.0f}% agreement)"
                    )

            except Exception as e:
                failed_count += 1
                logger.warning(f"Error validating directional tag for scene {scene.scene_number}: {e}")

        self._log_agent_operation(
            "Directional tag validation complete",
            f"{inserted_count} inserted, {validated_count} already valid, {failed_count} failed"
        )

        data['directional_tags_validated'] = validated_count + inserted_count
        data['directional_tags_failed'] = failed_count

        return data

    # =========================================================================
    # LAYER 4: MOTIVATIONAL COHERENCE
    # =========================================================================

    async def _layer4_motivational_coherence(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Layer 4: Validate character motivations align with actions."""
        logger.info("Layer 4: Checking motivational coherence...")
        self._log_agent_operation("Initiating motivational coherence check")

        character_arcs = data.get('character_arcs', [])
        scenes = data.get('scenes', [])

        if not character_arcs or not scenes:
            self._log_agent_operation("No character arcs or scenes, skipping layer")
            data['motivation_checks'] = []
            data['motivation_status'] = ValidationStatus.PASSED
            return data

        self._log_agent_operation("Analyzing character motivations", f"{len(character_arcs)} characters")
        self._log_agent_operation("Deploying motivational coherence agent")

        # Build character action summary from scene content
        # SCENE-ONLY ARCHITECTURE: Extract character actions from scene prose
        char_actions = []
        for scene in scenes:
            # Get tags from scene (either from tags field or extracted from content)
            scene_tags = scene.tags if hasattr(scene, 'tags') and scene.tags else []
            for tag in scene_tags:
                if tag in [arc.character_tag for arc in character_arcs]:
                    # Use scene content preview as action description
                    content_preview = scene.content[:200] if hasattr(scene, 'content') and scene.content else scene.purpose
                    char_actions.append(f"[{tag}] in Scene {scene.scene_number}: {content_preview}")

        prompt = f"""Check if character actions align with their motivations.

CHARACTER ARCS:
{chr(10).join([f"[{arc.character_tag}]: Want={arc.want}, Need={arc.need}, Flaw={arc.flaw}" for arc in character_arcs])}

CHARACTER ACTIONS:
{chr(10).join(char_actions[:20])}  # Limit to first 20 actions

For each action, determine if it's coherent with the character's motivation.
Flag any actions that seem out of character.

Format each check as:
CHECK: [CHARACTER_TAG]
Scene: [scene number]
Action: [what they do]
Coherent: [yes/no]
Reasoning: [why it does/doesn't fit]
Revision: [suggested revision if not coherent]

List all motivation checks:"""

        self._log_agent_operation("Sending request to LLM", "Motivational Analysis function")
        response = await self.function_router.route(
            function=LLMFunction.STORY_ANALYSIS,
            prompt=prompt,
            system_prompt="You are a character consistency analyst ensuring motivational coherence."
        )

        self._log_agent_operation("Received motivational coherence response", f"{len(response)} chars")
        self._log_agent_operation("Parsing motivation checks from response")

        checks = self._parse_motivation_checks(response)
        data['motivation_checks'] = checks

        incoherent_count = sum(1 for c in checks if not c.is_coherent)
        data['motivation_status'] = (
            ValidationStatus.FAILED if incoherent_count > len(checks) * 0.3
            else ValidationStatus.NEEDS_REVISION if incoherent_count > 0
            else ValidationStatus.PASSED
        )

        coherent_count = len(checks) - incoherent_count
        self._log_agent_operation("Motivational coherence complete",
                                  f"{coherent_count}/{len(checks)} actions coherent")

        return data

    def _parse_motivation_checks(self, response: str) -> List[MotivationCheck]:
        """Parse motivation checks from LLM response."""
        import re
        checks = []

        check_blocks = re.split(r'CHECK:\s*\[?', response, flags=re.IGNORECASE)

        for block in check_blocks[1:]:
            tag_match = re.match(r'([A-Z_]+)\]?', block)
            scene_match = re.search(r'Scene:\s*(\d+)', block)
            action_match = re.search(r'Action:\s*(.+?)(?:\n|$)', block)
            coherent_match = re.search(r'Coherent:\s*(yes|no)', block, re.IGNORECASE)
            reasoning_match = re.search(r'Reasoning:\s*(.+?)(?:\n|$)', block)
            revision_match = re.search(r'Revision:\s*(.+?)(?:\n|$)', block)

            if tag_match:
                checks.append(MotivationCheck(
                    character_tag=tag_match.group(1),
                    action=action_match.group(1).strip() if action_match else "",
                    scene_id=f"S{int(scene_match.group(1)):02d}" if scene_match else "",
                    is_coherent=coherent_match.group(1).lower() == "yes" if coherent_match else True,
                    reasoning=reasoning_match.group(1).strip() if reasoning_match else "",
                    suggested_revision=revision_match.group(1).strip() if revision_match else ""
                ))

        return checks

    # =========================================================================
    # FINAL ASSEMBLY
    # =========================================================================

    async def _assemble_output(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> StoryOutput:
        """Assemble the final story output from all layers.

        SCENE-ONLY ARCHITECTURE: Scenes are the atomic narrative unit.
        No beat subdivision - Director pipeline creates frames from scenes.
        """
        logger.info("Assembling final story output...")

        scenes = data.get('scenes', [])

        # Build act structure from plot points
        act_structure = {1: [], 2: [], 3: []}
        for pp in data.get('plot_points', []):
            act_structure[pp.act].append(pp.point_id)

        # Get final script content if available (from quality assurance phase)
        final_script = data.get('final_script', '')

        output = StoryOutput(
            title=data.get('title', 'Untitled'),
            genre=data.get('genre', ''),
            visual_style=data.get('visual_style', 'live_action'),
            style_notes=data.get('style_notes', ''),

            # World Overview (generated by agents)
            logline=data.get('logline', ''),
            synopsis=data.get('synopsis', ''),
            themes=data.get('themes', ''),
            world_rules=data.get('world_rules', ''),
            lighting=data.get('lighting', ''),
            vibe=data.get('vibe', ''),

            # Layer 1
            plot_points=data.get('plot_points', []),
            act_structure=act_structure,

            # Layer 2 (with visual descriptions)
            character_arcs=data.get('character_arcs', []),

            # Scene structure (scene-only, no beats)
            scenes=scenes,

            # Layer 3: Continuity
            continuity_issues=data.get('continuity_issues', []),
            continuity_status=data.get('continuity_status', ValidationStatus.PENDING),

            # Layer 4: Motivation
            motivation_checks=data.get('motivation_checks', []),
            motivation_status=data.get('motivation_status', ValidationStatus.PENDING),

            # Tags
            all_tags=data.get('all_tags', []),
            character_tags=data.get('character_tags', []),
            location_tags=data.get('location_tags', []),

            # Detailed descriptions
            location_descriptions=data.get('location_descriptions', []),
            prop_descriptions=data.get('prop_descriptions', []),

            # Quality Assurance
            quality_score=data.get('quality_score', 0.0),
            quality_passed=data.get('quality_passed', False),
            quality_report=data.get('quality_report'),

            summary=self._build_summary(scenes, data),

            # Store final script content if available
            _script_content=final_script
        )

        return output

    def _build_summary(self, scenes: List, data: Dict[str, Any]) -> str:
        """Build the summary string safely.

        SCENE-ONLY ARCHITECTURE: Summary reports scenes only (no beats).
        """
        continuity_status = data.get('continuity_status', ValidationStatus.PENDING)
        motivation_status = data.get('motivation_status', ValidationStatus.PENDING)

        # Handle both enum and string values
        if hasattr(continuity_status, 'name'):
            continuity_name = continuity_status.name
        else:
            continuity_name = str(continuity_status)

        if hasattr(motivation_status, 'name'):
            motivation_name = motivation_status.name
        else:
            motivation_name = str(motivation_status)

        quality_score = data.get('quality_score', 0.0)
        quality_passed = data.get('quality_passed', False)
        quality_status = f"Quality: {quality_score:.2f} ({'PASSED' if quality_passed else 'NEEDS REVIEW'})"

        return (f"Story with {len(scenes)} scenes. "
                f"Continuity: {continuity_name}. "
                f"Motivation: {motivation_name}. "
                f"{quality_status}.")
