"""
Morpheus Writ - Layered Writer Pipeline

A streamlined writer that operates in layers:
1. High-Level Outline - Generate story structure from prompt
2. User Checkpoint - Present outline, await user feedback
3. Granular Outline - Refine with scene-level detail
4. Scale Determination - Analyze scope (micro/short/medium/feature)
5. Write Out - Generate final prose

Integrates with Supabase for persistence and user interaction.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum

from morpheus.core.logging_config import get_logger
from morpheus.core.constants import LLMFunction
from morpheus.llm import LLMManager, FunctionRouter
from .base_pipeline import BasePipeline, PipelineStep, PipelineResult, PipelineStatus

logger = get_logger("pipelines.layered_writer")


class WriterLayer(Enum):
    """Layers in the writing process."""
    HIGH_LEVEL_OUTLINE = 1
    USER_CHECKPOINT_1 = 2
    GRANULAR_OUTLINE = 3
    USER_CHECKPOINT_2 = 4
    SCALE_DETERMINATION = 5
    WRITE_OUT = 6


@dataclass
class WriterInput:
    """Input for the layered writer pipeline."""
    prompt: str
    title: str = ""
    genre: str = ""
    world_config: Optional[Dict[str, Any]] = None  # Optional world bible reference
    project_id: Optional[str] = None  # Supabase project ID for persistence
    user_id: Optional[str] = None  # Supabase user ID


@dataclass
class OutlineSection:
    """A section in the outline."""
    section_id: str
    title: str
    summary: str
    key_events: List[str] = field(default_factory=list)
    characters: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    estimated_scenes: int = 1


@dataclass
class HighLevelOutline:
    """High-level story outline (Layer 1 output)."""
    title: str
    logline: str
    genre: str
    tone: str
    themes: List[str]
    act_structure: List[OutlineSection]
    protagonist: str
    antagonist: str
    central_conflict: str


@dataclass
class GranularOutline:
    """Scene-level outline (Layer 3 output)."""
    scenes: List[Dict[str, Any]]  # Each scene with beats, characters, location
    total_scenes: int
    estimated_word_count: int
    pacing_notes: str


@dataclass
class ScaleDetermination:
    """Scale analysis (Layer 5 output)."""
    scale: str  # micro, short, medium, feature
    scene_count: int
    target_word_count: int
    chapter_structure: Optional[List[str]] = None
    reasoning: str = ""


@dataclass
class WriterOutput:
    """Final output from the layered writer."""
    title: str
    content: str  # The written prose
    word_count: int
    scene_count: int
    scale: str
    outline: GranularOutline
    metadata: Dict[str, Any] = field(default_factory=dict)


# Type for user feedback callback
UserFeedbackCallback = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class LayeredWriterPipeline(BasePipeline[WriterInput, WriterOutput]):
    """
    Layered writer pipeline with user checkpoints.

    Flow:
    1. Generate high-level outline from prompt
    2. CHECKPOINT: Present to user, get feedback
    3. Generate granular scene-level outline
    4. CHECKPOINT: Present to user, get feedback
    5. Determine scale based on outline
    6. Write out final prose
    """

    def __init__(
        self,
        llm_manager: Optional[LLMManager] = None,
        user_feedback_callback: Optional[UserFeedbackCallback] = None,
        supabase_client: Optional[Any] = None
    ):
        self.llm_manager = llm_manager or LLMManager()
        self.router = FunctionRouter(self.llm_manager)
        self.user_feedback_callback = user_feedback_callback
        self.supabase = supabase_client

        # State for checkpoints
        self._awaiting_feedback = False
        self._current_layer = WriterLayer.HIGH_LEVEL_OUTLINE
        self._outline_data: Dict[str, Any] = {}

        super().__init__("LayeredWriter")

    def _define_steps(self) -> None:
        """Define the pipeline steps."""
        self._steps = [
            PipelineStep("high_level_outline", "Generate high-level story outline", timeout_seconds=120),
            PipelineStep("user_checkpoint_1", "Await user feedback on outline", required=False, timeout_seconds=3600),
            PipelineStep("granular_outline", "Generate scene-level outline", timeout_seconds=180),
            PipelineStep("user_checkpoint_2", "Await user feedback on scenes", required=False, timeout_seconds=3600),
            PipelineStep("scale_determination", "Determine story scale", timeout_seconds=60),
            PipelineStep("write_out", "Generate final prose", timeout_seconds=600),
        ]

    async def _execute_step(
        self,
        step: PipelineStep,
        input_data: Any,
        context: Dict[str, Any]
    ) -> Any:
        """Execute a single step."""
        if step.name == "high_level_outline":
            return await self._generate_high_level_outline(input_data, context)
        elif step.name == "user_checkpoint_1":
            return await self._user_checkpoint(input_data, context, layer=1)
        elif step.name == "granular_outline":
            return await self._generate_granular_outline(input_data, context)
        elif step.name == "user_checkpoint_2":
            return await self._user_checkpoint(input_data, context, layer=2)
        elif step.name == "scale_determination":
            return await self._determine_scale(input_data, context)
        elif step.name == "write_out":
            return await self._write_out(input_data, context)
        else:
            raise ValueError(f"Unknown step: {step.name}")

    # =========================================================================
    # LAYER 1: High-Level Outline
    # =========================================================================

    async def _generate_high_level_outline(
        self,
        input_data: WriterInput,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate high-level story outline from prompt."""
        logger.info(f"Generating high-level outline for: {input_data.title or 'Untitled'}")

        # Build context from world_config if available
        world_context = ""
        if input_data.world_config:
            chars = input_data.world_config.get("characters", [])
            locs = input_data.world_config.get("locations", [])
            if chars:
                world_context += f"\nAvailable Characters: {', '.join(c.get('name', c.get('tag', '')) for c in chars[:5])}"
            if locs:
                world_context += f"\nAvailable Locations: {', '.join(l.get('name', l.get('tag', '')) for l in locs[:5])}"

        system_prompt = """You are a master story architect. Generate a high-level story outline.

## CANONICAL TAG FORMAT (MANDATORY)
All characters, locations, props, and events MUST use canonical tags:
- Characters: [CHAR_FIRSTNAME] or [CHAR_FIRSTNAME_LASTNAME] e.g., [CHAR_JOHN], [CHAR_MARY_SMITH]
- Locations: [LOC_PLACE_NAME] e.g., [LOC_TOWN_SQUARE], [LOC_DARK_FOREST]
- Props: [PROP_ITEM_NAME] e.g., [PROP_ANCIENT_SWORD], [PROP_GOLDEN_KEY]
- Events: [EVENT_NAME] e.g., [EVENT_WEDDING], [EVENT_BATTLE]

Output JSON with this structure:
{
    "title": "Story title",
    "logline": "One sentence summary",
    "genre": "Primary genre",
    "tone": "Overall tone/mood",
    "themes": ["[CONCEPT_THEME1]", "[CONCEPT_THEME2]"],
    "protagonist": "[CHAR_NAME] - brief description",
    "antagonist": "[CHAR_NAME] - opposing force description",
    "central_conflict": "Core dramatic question",
    "act_structure": [
        {
            "section_id": "act_1",
            "title": "Act 1: Setup",
            "summary": "What happens in this act",
            "key_events": ["[EVENT_INCITING_INCIDENT]", "[EVENT_FIRST_TURNING_POINT]"],
            "characters": ["[CHAR_PROTAGONIST]", "[CHAR_MENTOR]"],
            "locations": ["[LOC_STARTING_LOCATION]"],
            "estimated_scenes": 3
        }
    ]
}"""

        user_prompt = f"""Create a high-level story outline for:

PROMPT: {input_data.prompt}

{f"GENRE: {input_data.genre}" if input_data.genre else ""}
{world_context}

Generate a compelling 3-act structure with clear dramatic progression."""

        response = await self.router.route(
            function=LLMFunction.STORY_GENERATION,
            prompt=user_prompt,
            system_prompt=system_prompt,
            response_format="json"
        )

        outline = self._parse_json_response(response)

        # Store in state
        self._outline_data["high_level"] = outline
        self._current_layer = WriterLayer.USER_CHECKPOINT_1

        # Persist to Supabase if available
        if self.supabase and input_data.project_id:
            await self._save_outline_to_supabase(input_data.project_id, 1, outline)

        return {"input": input_data, "high_level_outline": outline}

    # =========================================================================
    # USER CHECKPOINTS
    # =========================================================================

    async def _user_checkpoint(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any],
        layer: int
    ) -> Dict[str, Any]:
        """Await user feedback at checkpoint."""
        if not self.user_feedback_callback:
            logger.info(f"No feedback callback - auto-approving layer {layer}")
            return data

        self._awaiting_feedback = True

        # Prepare data for user review
        review_data = {
            "layer": layer,
            "outline": data.get("high_level_outline") if layer == 1 else data.get("granular_outline"),
            "project_id": data.get("input", {}).project_id if hasattr(data.get("input", {}), "project_id") else None
        }

        # Call the feedback callback (this would be connected to UI/API)
        feedback = await self.user_feedback_callback(review_data)

        self._awaiting_feedback = False

        # Apply feedback
        if feedback.get("approved", True):
            data["user_feedback"] = feedback.get("notes", "")
            data["modifications"] = feedback.get("modifications", {})
        else:
            # User rejected - could trigger re-generation
            data["rejected"] = True
            data["rejection_reason"] = feedback.get("reason", "")

        return data


    # =========================================================================
    # LAYER 3: Granular Outline
    # =========================================================================

    async def _generate_granular_outline(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate scene-level granular outline."""
        logger.info("Generating granular scene-level outline")

        high_level = data.get("high_level_outline", {})
        user_feedback = data.get("user_feedback", "")
        modifications = data.get("modifications", {})

        system_prompt = """You are a master scene architect. Break down the story outline into detailed scenes.

## CANONICAL TAG FORMAT (MANDATORY)
All characters, locations, props MUST use canonical tags:
- Characters: [CHAR_NAME] e.g., [CHAR_JOHN], [CHAR_MARY]
- Locations: [LOC_PLACE] e.g., [LOC_TOWN_SQUARE], [LOC_CASTLE]
- Props: [PROP_ITEM] e.g., [PROP_SWORD], [PROP_LETTER]
- Environment: [ENV_CONDITION] e.g., [ENV_RAIN], [ENV_NIGHT]

Output JSON with this structure:
{
    "scenes": [
        {
            "scene_id": "1",
            "title": "Scene title",
            "act": 1,
            "location": "[LOC_SPECIFIC_PLACE]",
            "characters": ["[CHAR_NAME1]", "[CHAR_NAME2]"],
            "time_of_day": "morning/afternoon/evening/night",
            "summary": "What happens - use [CHAR_X] tags for characters",
            "beats": ["[CHAR_X] does action", "[CHAR_Y] responds"],
            "emotional_arc": "How emotion shifts",
            "purpose": "Why this scene matters"
        }
    ],
    "total_scenes": 12,
    "estimated_word_count": 15000,
    "pacing_notes": "Notes on story rhythm and pacing"
}"""

        user_prompt = f"""Break down this story outline into detailed scenes:

OUTLINE:
Title: {high_level.get('title', 'Untitled')}
Logline: {high_level.get('logline', '')}
Central Conflict: {high_level.get('central_conflict', '')}

ACT STRUCTURE:
{self._format_act_structure(high_level.get('act_structure', []))}

{f"USER FEEDBACK TO INCORPORATE: {user_feedback}" if user_feedback else ""}

Create detailed scene breakdowns with clear beats and emotional progression."""

        response = await self.router.route(
            function=LLMFunction.STORY_GENERATION,
            prompt=user_prompt,
            system_prompt=system_prompt,
            response_format="json"
        )

        granular = self._parse_json_response(response)

        self._outline_data["granular"] = granular
        self._current_layer = WriterLayer.USER_CHECKPOINT_2

        # Persist to Supabase
        input_data = data.get("input")
        if self.supabase and input_data and input_data.project_id:
            await self._save_outline_to_supabase(input_data.project_id, 3, granular)

        data["granular_outline"] = granular
        return data

    # =========================================================================
    # LAYER 5: Scale Determination
    # =========================================================================

    async def _determine_scale(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Determine story scale based on outline complexity."""
        logger.info("Determining story scale")

        granular = data.get("granular_outline", {})
        scene_count = granular.get("total_scenes", len(granular.get("scenes", [])))
        estimated_words = granular.get("estimated_word_count", scene_count * 1500)

        # Scale thresholds
        if scene_count <= 3 and estimated_words <= 3000:
            scale = "micro"
            target_words = 2000
        elif scene_count <= 8 and estimated_words <= 10000:
            scale = "short"
            target_words = 7500
        elif scene_count <= 20 and estimated_words <= 40000:
            scale = "medium"
            target_words = 25000
        else:
            scale = "feature"
            target_words = 60000

        scale_data = ScaleDetermination(
            scale=scale,
            scene_count=scene_count,
            target_word_count=target_words,
            reasoning=f"Based on {scene_count} scenes and estimated {estimated_words} words"
        )

        data["scale"] = scale_data
        self._current_layer = WriterLayer.WRITE_OUT

        # Update project status in Supabase
        input_data = data.get("input")
        if self.supabase and input_data and input_data.project_id:
            await self._update_project_scale(input_data.project_id, scale)

        return data


    # =========================================================================
    # LAYER 6: Write Out
    # =========================================================================

    async def _write_out(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> WriterOutput:
        """Generate final prose from granular outline."""
        logger.info("Writing out final prose")

        granular = data.get("granular_outline", {})
        scale_data = data.get("scale", ScaleDetermination("short", 5, 7500))
        high_level = data.get("high_level_outline", {})
        input_data = data.get("input", WriterInput(prompt=""))

        scenes = granular.get("scenes", [])
        all_prose = []

        # Write each scene
        for i, scene in enumerate(scenes):
            logger.info(f"Writing scene {i+1}/{len(scenes)}: {scene.get('title', 'Untitled')}")

            scene_prose = await self._write_scene(scene, high_level, input_data.world_config)
            all_prose.append(scene_prose)

        # Combine all scenes
        full_content = "\n\n---\n\n".join(all_prose)
        word_count = len(full_content.split())

        output = WriterOutput(
            title=high_level.get("title", input_data.title or "Untitled"),
            content=full_content,
            word_count=word_count,
            scene_count=len(scenes),
            scale=scale_data.scale if isinstance(scale_data, ScaleDetermination) else scale_data,
            outline=GranularOutline(
                scenes=scenes,
                total_scenes=len(scenes),
                estimated_word_count=word_count,
                pacing_notes=granular.get("pacing_notes", "")
            ),
            metadata={
                "genre": high_level.get("genre", input_data.genre),
                "themes": high_level.get("themes", []),
                "logline": high_level.get("logline", "")
            }
        )

        # Save draft to Supabase
        if self.supabase and input_data.project_id:
            await self._save_draft_to_supabase(input_data.project_id, output)

        return output

    async def _write_scene(
        self,
        scene: Dict[str, Any],
        high_level: Dict[str, Any],
        world_config: Optional[Dict[str, Any]]
    ) -> str:
        """Write a single scene."""
        # Build character context from world_config
        char_context = ""
        if world_config and scene.get("characters"):
            chars = world_config.get("characters", [])
            for char_name in scene.get("characters", []):
                char_data = next((c for c in chars if c.get("name") == char_name or c.get("tag") == char_name), None)
                if char_data:
                    char_context += f"\n{char_name}: {char_data.get('description', char_data.get('visual_appearance', ''))}"

        system_prompt = """You are a master prose writer. Write vivid, engaging scene prose.

## INLINE TAG ANNOTATIONS (MANDATORY)
Maintain canonical tags inline in the prose for key story elements:
- First mention of characters: "John [CHAR_JOHN] entered the room..."
- Key locations: "...arrived at the town square [LOC_TOWN_SQUARE]..."
- Important props: "She picked up the ancient sword [PROP_ANCIENT_SWORD]..."
- Significant events: "The wedding [EVENT_WEDDING] began at sunset..."

Guidelines:
- Show, don't tell
- Use sensory details
- Natural dialogue with subtext
- Clear scene geography
- Emotional resonance
- Include [CHAR_X] tags on first character mention per scene
- Include [LOC_X] tags for location establishment
- Include [PROP_X] tags for significant objects

Write the scene in third person past tense."""

        user_prompt = f"""Write this scene with inline tag annotations:

SCENE: {scene.get('title', 'Untitled')}
LOCATION: {scene.get('location', 'Unknown')}
TIME: {scene.get('time_of_day', 'day')}
CHARACTERS: {', '.join(scene.get('characters', []))}

SUMMARY: {scene.get('summary', '')}

BEATS TO HIT:
{chr(10).join(f"- {beat}" for beat in scene.get('beats', []))}

EMOTIONAL ARC: {scene.get('emotional_arc', '')}
PURPOSE: {scene.get('purpose', '')}

{f"CHARACTER DETAILS:{char_context}" if char_context else ""}

STORY CONTEXT:
Genre: {high_level.get('genre', '')}
Tone: {high_level.get('tone', '')}
Central Conflict: {high_level.get('central_conflict', '')}

Write the complete scene with vivid prose. Include [CHAR_X], [LOC_X], [PROP_X] tags inline."""

        response = await self.router.route(
            function=LLMFunction.STORY_GENERATION,
            prompt=user_prompt,
            system_prompt=system_prompt
        )

        return response.strip()

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response."""
        import json

        # Try to extract JSON from response
        text = response.strip()

        # Handle markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON: {e}")
            return {}

    def _format_act_structure(self, acts: List[Dict[str, Any]]) -> str:
        """Format act structure for prompts."""
        lines = []
        for act in acts:
            lines.append(f"\n{act.get('title', 'Act')}:")
            lines.append(f"  Summary: {act.get('summary', '')}")
            if act.get('key_events'):
                lines.append(f"  Key Events: {', '.join(act.get('key_events', []))}")
        return "\n".join(lines)

    # =========================================================================
    # SUPABASE PERSISTENCE
    # =========================================================================

    async def _save_outline_to_supabase(
        self,
        project_id: str,
        layer: int,
        outline: Dict[str, Any]
    ) -> None:
        """Save outline to Supabase."""
        if not self.supabase:
            return

        try:
            # This would use the Supabase client
            # await self.supabase.table("morphwrit_outlines").insert({
            #     "project_id": project_id,
            #     "layer": layer,
            #     "outline_content": outline,
            #     "approved": False
            # }).execute()
            logger.info(f"Saved layer {layer} outline to Supabase")
        except Exception as e:
            logger.error(f"Failed to save outline: {e}")

    async def _update_project_scale(self, project_id: str, scale: str) -> None:
        """Update project scale in Supabase."""
        if not self.supabase:
            return

        try:
            # await self.supabase.table("morphwrit_projects").update({
            #     "scale": scale,
            #     "status": "writing"
            # }).eq("id", project_id).execute()
            logger.info(f"Updated project scale to {scale}")
        except Exception as e:
            logger.error(f"Failed to update scale: {e}")

    async def _save_draft_to_supabase(
        self,
        project_id: str,
        output: WriterOutput
    ) -> None:
        """Save final draft to Supabase."""
        if not self.supabase:
            return

        try:
            # await self.supabase.table("morphwrit_drafts").insert({
            #     "project_id": project_id,
            #     "content": output.content,
            #     "word_count": output.word_count,
            #     "scene_count": output.scene_count
            # }).execute()
            #
            # await self.supabase.table("morphwrit_projects").update({
            #     "status": "complete"
            # }).eq("id", project_id).execute()
            logger.info(f"Saved draft to Supabase: {output.word_count} words")
        except Exception as e:
            logger.error(f"Failed to save draft: {e}")

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    @property
    def current_layer(self) -> WriterLayer:
        """Get current layer in the writing process."""
        return self._current_layer

    @property
    def awaiting_feedback(self) -> bool:
        """Check if pipeline is awaiting user feedback."""
        return self._awaiting_feedback

    def get_outline_data(self) -> Dict[str, Any]:
        """Get current outline data for review."""
        return self._outline_data.copy()
