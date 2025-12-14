"""
Procedural Generation Module - Micro-Chunked Prose Generation

Handles LLM output limitations through micro-chunked generation with:
- Optimal chunk sizes (200-400 words)
- State tracking between chunks
- Micro-synthesis for smooth transitions
- Validation checkpoints

Protocols:
1. Scene-Chunked Generation - Chunk by scene
2. Beat-Chunked Generation - Chunk by story beat
3. Expansion-Based Generation - Start compressed, expand in passes
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from greenlight.config.word_caps import (
    OUTPUT_BUDGETS, PROCEDURAL_CONFIG,
    get_output_budget, calculate_scene_budget
)

logger = get_logger("pipelines.procedural")


# =============================================================================
# ENUMS
# =============================================================================

class BeatType(Enum):
    """Types of story beats."""
    ACTION = "action"
    DIALOGUE = "dialogue"
    REACTION = "reaction"
    TRANSITION = "transition"


class GenerationProtocol(Enum):
    """Available generation protocols."""
    SCENE_CHUNKED = "scene_chunked"
    BEAT_CHUNKED = "beat_chunked"
    EXPANSION = "expansion"


# =============================================================================
# STATE TRACKING DATA CLASSES
# =============================================================================

@dataclass
class CharacterState:
    """Per-character state tracking."""
    tag: str
    position: str = ""  # Where in location
    physical_state: str = ""  # Standing, sitting, moving
    emotional_state: str = ""  # Current emotion
    last_dialogue: str = ""  # What they last said
    last_action: str = ""  # What they last did
    holding: List[str] = field(default_factory=list)  # Props in hand


@dataclass
class ChunkState:
    """State passed between chunks for continuity."""
    character_states: Dict[str, CharacterState] = field(default_factory=dict)
    location_tag: str = ""
    time_of_day: str = ""
    active_props: List[str] = field(default_factory=list)
    unresolved_tensions: List[str] = field(default_factory=list)
    last_speaker: str = ""
    last_action: str = ""
    emotional_tone: str = ""
    
    def to_prompt_context(self) -> str:
        """Format state for inclusion in prompts."""
        lines = []
        
        if self.character_states:
            lines.append("CHARACTER STATES:")
            for tag, state in self.character_states.items():
                lines.append(f"  [{tag}]: {state.emotional_state}, {state.physical_state}")
                if state.last_action:
                    lines.append(f"    Last action: {state.last_action}")
        
        if self.location_tag:
            lines.append(f"LOCATION: [{self.location_tag}]")
        
        if self.time_of_day:
            lines.append(f"TIME: {self.time_of_day}")
        
        if self.emotional_tone:
            lines.append(f"EMOTIONAL TONE: {self.emotional_tone}")
        
        if self.last_action:
            lines.append(f"LAST ACTION: {self.last_action}")
        
        return "\n".join(lines) if lines else "No prior state"


@dataclass
class Beat:
    """A single story beat."""
    beat_id: str
    beat_type: BeatType
    description: str
    word_budget: int = 100


@dataclass
class Scene:
    """A scene with beats."""
    scene_id: str
    scene_number: int
    title: str
    location_tag: str
    characters: List[str]
    purpose: str
    word_budget: int
    beats: List[Beat] = field(default_factory=list)
    entry_state: Dict[str, str] = field(default_factory=dict)
    exit_state: Dict[str, str] = field(default_factory=dict)


@dataclass
class ScriptOutline:
    """Script_v1 structured outline."""
    title: str
    media_type: str
    word_budget: int
    scenes: List[Scene] = field(default_factory=list)


@dataclass
class GeneratedChunk:
    """A generated prose chunk."""
    chunk_id: str
    scene_id: str
    beat_ids: List[str]
    prose: str
    word_count: int
    ending_state: str
    character_states_exit: Dict[str, str] = field(default_factory=dict)


@dataclass
class ValidationCheck:
    """Result of a single validation check."""
    name: str
    passed: bool
    message: str = ""


@dataclass
class ValidationResult:
    """Result of chunk validation."""
    passed: bool
    failed_checks: List[ValidationCheck] = field(default_factory=list)
    regenerate: bool = False


@dataclass
class SynthesisEdit:
    """Edit from micro-synthesis."""
    operation: str  # BRIDGE, SMOOTH, TRIM, NONE
    chunk_a_ending_edit: str = ""
    bridge_content: str = ""
    chunk_b_beginning_edit: str = ""
    continuity_flag: str = ""


# =============================================================================
# PROCEDURAL GENERATOR
# =============================================================================

class ProceduralGenerator:
    """
    Generates prose from script outline using micro-chunked generation.

    Stays within LLM quality zone (200-400 words per chunk) and
    maintains continuity through state tracking and micro-synthesis.
    """

    def __init__(self, llm_caller: Callable = None):
        self.llm_caller = llm_caller
        self.config = PROCEDURAL_CONFIG

    async def generate_prose(
        self,
        script_outline: ScriptOutline,
        protocol: GenerationProtocol = GenerationProtocol.SCENE_CHUNKED
    ) -> str:
        """
        Generate full prose from outline using specified protocol.

        Args:
            script_outline: Structured script outline (Script_v1)
            protocol: Which generation protocol to use

        Returns:
            Full prose within word budget
        """
        logger.info(f"Starting procedural generation with {protocol.value} protocol")
        logger.info(f"Word budget: {script_outline.word_budget}")

        if protocol == GenerationProtocol.SCENE_CHUNKED:
            return await self._scene_chunked_generation(script_outline)
        elif protocol == GenerationProtocol.BEAT_CHUNKED:
            return await self._beat_chunked_generation(script_outline)
        elif protocol == GenerationProtocol.EXPANSION:
            return await self._expansion_generation(script_outline)
        else:
            return await self._scene_chunked_generation(script_outline)

    # =========================================================================
    # PROTOCOL 1: SCENE-CHUNKED GENERATION
    # =========================================================================

    async def _scene_chunked_generation(self, script: ScriptOutline) -> str:
        """Generate prose by chunking at scene level."""
        logger.info("Using Scene-Chunked Generation Protocol")

        # Step 1: Allocate budgets per scene
        scene_budgets = self._allocate_scene_budgets(script)

        # Step 2: Generate scenes sequentially (with state tracking)
        chunks: List[GeneratedChunk] = []
        current_state = ChunkState()

        for scene in script.scenes:
            budget = scene_budgets.get(scene.scene_id, scene.word_budget)

            # Initialize character states from scene entry
            for char_tag, state_desc in scene.entry_state.items():
                if char_tag not in current_state.character_states:
                    current_state.character_states[char_tag] = CharacterState(
                        tag=char_tag,
                        emotional_state=state_desc
                    )

            # Generate scene chunk
            chunk = await self._generate_scene_chunk(
                scene=scene,
                budget=budget,
                entry_state=current_state,
                prev_chunk=chunks[-1] if chunks else None
            )

            # Validate chunk
            validation = self._validate_chunk(chunk, current_state)

            if not validation.passed and validation.regenerate:
                # Retry with guidance
                chunk = await self._regenerate_chunk(
                    scene, budget, current_state, validation
                )

            chunks.append(chunk)

            # Update state for next scene
            current_state = self._extract_exit_state(chunk, scene)

        # Step 3: Micro-synthesis (parallel where possible)
        transitions = await self._parallel_micro_synthesis(chunks)

        # Step 4: Assemble
        prose = self._assemble_with_transitions(chunks, transitions)

        logger.info(f"Generated {len(prose.split())} words across {len(chunks)} chunks")

        return prose

    def _allocate_scene_budgets(self, script: ScriptOutline) -> Dict[str, int]:
        """Allocate word budget across scenes."""
        budgets = {}
        total_budget = script.word_budget
        num_scenes = len(script.scenes)

        if num_scenes == 0:
            return budgets

        # Calculate base budget per scene
        synthesis_overhead = int(total_budget * 0.1)  # 10% for transitions
        available = total_budget - synthesis_overhead
        base_per_scene = available // num_scenes

        for scene in script.scenes:
            # Use scene's own budget if specified, otherwise use calculated
            budgets[scene.scene_id] = scene.word_budget or base_per_scene

        return budgets

    async def _generate_scene_chunk(
        self,
        scene: Scene,
        budget: int,
        entry_state: ChunkState,
        prev_chunk: Optional[GeneratedChunk]
    ) -> GeneratedChunk:
        """Generate prose for a single scene."""
        # Build previous scene ending context
        prev_ending = ""
        if prev_chunk:
            # Get last 2 paragraphs
            paragraphs = prev_chunk.prose.split("\n\n")
            prev_ending = "\n\n".join(paragraphs[-2:]) if len(paragraphs) >= 2 else prev_chunk.prose

        prompt = f"""Generate Scene {scene.scene_number} of the story.

SCENE OUTLINE:
Title: {scene.title}
Purpose: {scene.purpose}
Location: [{scene.location_tag}]
Characters: {', '.join(scene.characters)}

BEATS TO COVER:
{self._format_beats(scene.beats)}

PREVIOUS SCENE ENDING STATE:
{prev_ending if prev_ending else "This is the first scene."}

CHARACTER STATES ENTERING:
{entry_state.to_prompt_context()}

WORD BUDGET: {budget} words (DO NOT EXCEED)

REQUIREMENTS:
1. Generate prose for this scene only
2. Stay within word budget (±10%)
3. Start by connecting to previous scene ending (if applicable)
4. End at a clean boundary (completed action, dialogue exchange, or moment)
5. Use [CHAR_TAG], [LOC_TAG], [PROP_TAG] format for all references
6. Write in present tense, third person

OUTPUT FORMAT:
---
[SCENE_PROSE]
{{your scene prose here}}
[/SCENE_PROSE]

[ENDING_STATE]
Brief summary of where scene ends (1-2 sentences)
[/ENDING_STATE]

[CHARACTER_STATES_EXIT]
{{character_tag}}: {{emotional/physical state exiting scene}}
[/CHARACTER_STATES_EXIT]
---"""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a prose writer generating a single scene. Stay within your word budget and end at a clean boundary.",
            function=LLMFunction.STORY_GENERATION
        )

        return self._parse_scene_response(response, scene)

    def _format_beats(self, beats: List[Beat]) -> str:
        """Format beats for prompt."""
        if not beats:
            return "No specific beats defined"

        lines = []
        for i, beat in enumerate(beats, 1):
            lines.append(f"{i}. [{beat.beat_type.value.upper()}] {beat.description}")
        return "\n".join(lines)

    def _parse_scene_response(
        self,
        response: str,
        scene: Scene
    ) -> GeneratedChunk:
        """Parse scene generation response."""
        # Extract prose
        prose_match = re.search(
            r'\[SCENE_PROSE\]\s*(.*?)\s*\[/SCENE_PROSE\]',
            response, re.DOTALL
        )
        prose = prose_match.group(1).strip() if prose_match else response

        # Extract ending state
        ending_match = re.search(
            r'\[ENDING_STATE\]\s*(.*?)\s*\[/ENDING_STATE\]',
            response, re.DOTALL
        )
        ending_state = ending_match.group(1).strip() if ending_match else ""

        # Extract character states
        char_states = {}
        char_match = re.search(
            r'\[CHARACTER_STATES_EXIT\]\s*(.*?)\s*\[/CHARACTER_STATES_EXIT\]',
            response, re.DOTALL
        )
        if char_match:
            for line in char_match.group(1).strip().split("\n"):
                if ":" in line:
                    tag, state = line.split(":", 1)
                    char_states[tag.strip()] = state.strip()

        return GeneratedChunk(
            chunk_id=f"chunk_{scene.scene_id}",
            scene_id=scene.scene_id,
            beat_ids=[b.beat_id for b in scene.beats],
            prose=prose,
            word_count=len(prose.split()),
            ending_state=ending_state,
            character_states_exit=char_states
        )

    def _validate_chunk(
        self,
        chunk: GeneratedChunk,
        prev_state: ChunkState
    ) -> ValidationResult:
        """Validate a generated chunk."""
        checks = []

        # Word count check (±10% tolerance)
        tolerance = self.config.get("word_budget_tolerance", 0.1)
        # We don't have exact budget here, so just check reasonable range
        if chunk.word_count > self.config.get("chunk_max_words", 400) * 2:
            checks.append(ValidationCheck(
                name="word_count",
                passed=False,
                message=f"Chunk too long: {chunk.word_count} words"
            ))
        else:
            checks.append(ValidationCheck(name="word_count", passed=True))

        # Check for clean boundary (ends with period, not mid-sentence)
        if chunk.prose and not chunk.prose.rstrip().endswith(('.', '!', '?', '"')):
            checks.append(ValidationCheck(
                name="clean_boundary",
                passed=False,
                message="Chunk does not end at clean boundary"
            ))
        else:
            checks.append(ValidationCheck(name="clean_boundary", passed=True))

        # Check tag format
        tag_pattern = r'\[(?:CHAR|LOC|PROP)_[A-Z_]+\]'
        if re.search(tag_pattern, chunk.prose):
            checks.append(ValidationCheck(name="tag_format", passed=True))
        else:
            # Not a failure, just a note
            checks.append(ValidationCheck(name="tag_format", passed=True))

        failed = [c for c in checks if not c.passed]

        return ValidationResult(
            passed=len(failed) == 0,
            failed_checks=failed,
            regenerate=len(failed) > 0
        )

    async def _regenerate_chunk(
        self,
        scene: Scene,
        budget: int,
        state: ChunkState,
        validation: ValidationResult
    ) -> GeneratedChunk:
        """Regenerate a chunk with guidance from validation failures."""
        # Build retry guidance
        guidance = []
        for check in validation.failed_checks:
            if check.name == "word_count":
                guidance.append(f"Previous attempt exceeded word budget. Stay under {budget} words.")
            elif check.name == "clean_boundary":
                guidance.append("Previous attempt ended mid-action. Complete the current action before ending.")

        retry_prompt = f"""RETRY: Generate Scene {scene.scene_number}.

PREVIOUS ATTEMPT ISSUES:
{chr(10).join(guidance)}

SCENE OUTLINE:
Title: {scene.title}
Purpose: {scene.purpose}

WORD BUDGET: {budget} words (STRICT - DO NOT EXCEED)

Generate the scene prose, ending at a clean boundary.

OUTPUT FORMAT:
[SCENE_PROSE]
{{prose}}
[/SCENE_PROSE]

[ENDING_STATE]
{{ending summary}}
[/ENDING_STATE]"""

        response = await self.llm_caller(
            prompt=retry_prompt,
            system_prompt="You are retrying scene generation. Follow the guidance strictly.",
            function=LLMFunction.STORY_GENERATION
        )

        return self._parse_scene_response(response, scene)

    def _extract_exit_state(
        self,
        chunk: GeneratedChunk,
        scene: Scene
    ) -> ChunkState:
        """Extract exit state from chunk for next scene."""
        state = ChunkState()

        # Update character states
        for tag, desc in chunk.character_states_exit.items():
            state.character_states[tag] = CharacterState(
                tag=tag,
                emotional_state=desc
            )

        state.location_tag = scene.location_tag
        state.last_action = chunk.ending_state

        return state

    # =========================================================================
    # MICRO-SYNTHESIS
    # =========================================================================

    async def _parallel_micro_synthesis(
        self,
        chunks: List[GeneratedChunk]
    ) -> List[SynthesisEdit]:
        """Run micro-synthesis on chunk transitions in parallel where possible."""
        if len(chunks) < 2:
            return []

        # Pass 1: Synthesize odd transitions (1→2, 3→4, 5→6)
        pass1_tasks = []
        pass1_indices = []
        for i in range(0, len(chunks) - 1, 2):
            pass1_tasks.append(self._synthesize_transition(chunks[i], chunks[i + 1]))
            pass1_indices.append(i)

        pass1_results = await asyncio.gather(*pass1_tasks, return_exceptions=True)

        # Pass 2: Synthesize even transitions (2→3, 4→5)
        pass2_tasks = []
        pass2_indices = []
        for i in range(1, len(chunks) - 1, 2):
            pass2_tasks.append(self._synthesize_transition(chunks[i], chunks[i + 1]))
            pass2_indices.append(i)

        pass2_results = await asyncio.gather(*pass2_tasks, return_exceptions=True)

        # Combine results in order
        transitions = [None] * (len(chunks) - 1)

        for i, idx in enumerate(pass1_indices):
            result = pass1_results[i]
            if not isinstance(result, Exception):
                transitions[idx] = result

        for i, idx in enumerate(pass2_indices):
            result = pass2_results[i]
            if not isinstance(result, Exception):
                transitions[idx] = result

        # Fill any None with default
        for i in range(len(transitions)):
            if transitions[i] is None:
                transitions[i] = SynthesisEdit(operation="NONE")

        return transitions

    async def _synthesize_transition(
        self,
        chunk_a: GeneratedChunk,
        chunk_b: GeneratedChunk
    ) -> SynthesisEdit:
        """Synthesize transition between two chunks."""
        # Get last 2 paragraphs of chunk A
        paras_a = chunk_a.prose.split("\n\n")
        ending_a = "\n\n".join(paras_a[-2:]) if len(paras_a) >= 2 else chunk_a.prose

        # Get first 2 paragraphs of chunk B
        paras_b = chunk_b.prose.split("\n\n")
        beginning_b = "\n\n".join(paras_b[:2]) if len(paras_b) >= 2 else chunk_b.prose

        prompt = f"""Synthesize the transition between these two chunks.

CHUNK A (ending):
---
{ending_a}
---

CHUNK B (beginning):
---
{beginning_b}
---

CHUNK A ENDING STATE:
{chunk_a.ending_state}

ALLOWED OPERATIONS:
1. BRIDGE: Add 1-2 sentences between chunks (max 30 words)
2. SMOOTH: Adjust final sentence of A or first sentence of B (minimal edits)
3. TRIM: Remove redundant content at boundary
4. NONE: Transition is already smooth

DO NOT:
- Rewrite paragraph content
- Change meaning or events
- Add significant new content

OUTPUT FORMAT:
---
[OPERATION]: {{BRIDGE|SMOOTH|TRIM|NONE}}

[EDIT_CHUNK_A_ENDING]:
{{edited last paragraph of chunk A, or "NO CHANGE"}}

[BRIDGE_CONTENT]:
{{bridge sentences to insert, or "NONE"}}

[EDIT_CHUNK_B_BEGINNING]:
{{edited first paragraph of chunk B, or "NO CHANGE"}}

[CONTINUITY_FLAG]:
{{any continuity issues noticed, or "NONE"}}
---"""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a micro-synthesis agent. Make minimal, surgical edits only.",
            function=LLMFunction.STORY_ANALYSIS
        )

        return self._parse_synthesis_response(response)

    def _parse_synthesis_response(self, response: str) -> SynthesisEdit:
        """Parse micro-synthesis response."""
        # Extract operation
        op_match = re.search(r'\[OPERATION\]:\s*(\w+)', response)
        operation = op_match.group(1) if op_match else "NONE"

        # Extract edits
        edit_a_match = re.search(
            r'\[EDIT_CHUNK_A_ENDING\]:\s*(.*?)(?=\[BRIDGE_CONTENT\]|\[EDIT_CHUNK_B|\Z)',
            response, re.DOTALL
        )
        edit_a = edit_a_match.group(1).strip() if edit_a_match else ""
        if edit_a.upper() == "NO CHANGE":
            edit_a = ""

        bridge_match = re.search(
            r'\[BRIDGE_CONTENT\]:\s*(.*?)(?=\[EDIT_CHUNK_B|\[CONTINUITY|\Z)',
            response, re.DOTALL
        )
        bridge = bridge_match.group(1).strip() if bridge_match else ""
        if bridge.upper() == "NONE":
            bridge = ""

        edit_b_match = re.search(
            r'\[EDIT_CHUNK_B_BEGINNING\]:\s*(.*?)(?=\[CONTINUITY|\Z)',
            response, re.DOTALL
        )
        edit_b = edit_b_match.group(1).strip() if edit_b_match else ""
        if edit_b.upper() == "NO CHANGE":
            edit_b = ""

        flag_match = re.search(r'\[CONTINUITY_FLAG\]:\s*(.*?)(?:\Z|---)', response, re.DOTALL)
        flag = flag_match.group(1).strip() if flag_match else ""
        if flag.upper() == "NONE":
            flag = ""

        return SynthesisEdit(
            operation=operation,
            chunk_a_ending_edit=edit_a,
            bridge_content=bridge,
            chunk_b_beginning_edit=edit_b,
            continuity_flag=flag
        )

    def _assemble_with_transitions(
        self,
        chunks: List[GeneratedChunk],
        transitions: List[SynthesisEdit]
    ) -> str:
        """Assemble chunks with transition edits applied."""
        if not chunks:
            return ""

        parts = []

        for i, chunk in enumerate(chunks):
            prose = chunk.prose

            # Apply ending edit from previous transition
            if i > 0 and i - 1 < len(transitions):
                trans = transitions[i - 1]
                if trans.chunk_b_beginning_edit:
                    # Replace first paragraph
                    paras = prose.split("\n\n")
                    if paras:
                        paras[0] = trans.chunk_b_beginning_edit
                        prose = "\n\n".join(paras)

            # Apply ending edit for this chunk's transition
            if i < len(transitions):
                trans = transitions[i]
                if trans.chunk_a_ending_edit:
                    # Replace last paragraph
                    paras = prose.split("\n\n")
                    if paras:
                        paras[-1] = trans.chunk_a_ending_edit
                        prose = "\n\n".join(paras)

            parts.append(prose)

            # Add bridge content
            if i < len(transitions) and transitions[i].bridge_content:
                parts.append(transitions[i].bridge_content)

        return "\n\n".join(parts)

    # =========================================================================
    # PROTOCOL 2: BEAT-CHUNKED GENERATION
    # =========================================================================

    async def _beat_chunked_generation(self, script: ScriptOutline) -> str:
        """Generate prose by chunking at beat level (more granular)."""
        logger.info("Using Beat-Chunked Generation Protocol")

        # Calculate total beats and allocate budgets
        all_beats = []
        for scene in script.scenes:
            for beat in scene.beats:
                all_beats.append((scene, beat))

        if not all_beats:
            # Fall back to scene-chunked if no beats defined
            return await self._scene_chunked_generation(script)

        # Allocate budget per beat
        total_beats = len(all_beats)
        base_per_beat = script.word_budget // total_beats

        # Generate beats sequentially within scenes
        chunks: List[GeneratedChunk] = []
        current_state = ChunkState()

        current_scene = None
        scene_position = "beginning"

        for scene, beat in all_beats:
            # Track position in scene
            if current_scene != scene.scene_id:
                current_scene = scene.scene_id
                scene_position = "beginning"
                # Update location
                current_state.location_tag = scene.location_tag
            elif beat == scene.beats[-1]:
                scene_position = "end"
            else:
                scene_position = "middle"

            # Generate beat
            chunk = await self._generate_beat_chunk(
                scene=scene,
                beat=beat,
                budget=base_per_beat,
                state=current_state,
                scene_position=scene_position,
                prev_chunk=chunks[-1] if chunks else None
            )

            chunks.append(chunk)

            # Update state
            current_state.last_action = chunk.ending_state

        # Micro-synthesis
        transitions = await self._parallel_micro_synthesis(chunks)

        # Assemble
        prose = self._assemble_with_transitions(chunks, transitions)

        logger.info(f"Generated {len(prose.split())} words across {len(chunks)} beat chunks")

        return prose

    async def _generate_beat_chunk(
        self,
        scene: Scene,
        beat: Beat,
        budget: int,
        state: ChunkState,
        scene_position: str,
        prev_chunk: Optional[GeneratedChunk]
    ) -> GeneratedChunk:
        """Generate prose for a single beat."""
        prev_ending = ""
        if prev_chunk:
            # Get last paragraph
            paragraphs = prev_chunk.prose.split("\n\n")
            prev_ending = paragraphs[-1] if paragraphs else ""

        prompt = f"""Generate Beat {beat.beat_id} of Scene {scene.scene_number}.

BEAT DESCRIPTION:
{beat.description}

BEAT TYPE: {beat.beat_type.value}

PREVIOUS BEAT ENDING:
{prev_ending if prev_ending else "This is the first beat."}

SCENE CONTEXT:
- Scene purpose: {scene.purpose}
- Position in scene: {scene_position}
- Location: [{scene.location_tag}]

CHARACTER STATES:
{state.to_prompt_context()}

WORD BUDGET: {budget} words

REQUIREMENTS:
1. Generate prose for this beat only
2. Stay within word budget
3. Connect smoothly to previous beat
4. Match beat type:
   - Action: Focus on physical movement and consequence
   - Dialogue: Focus on exchange and subtext
   - Reaction: Focus on internal response and decision
   - Transition: Focus on movement between moments
5. End ready for next beat

OUTPUT FORMAT:
---
[BEAT_PROSE]
{{your beat prose here}}
[/BEAT_PROSE]

[ENDING_STATE]
{{one sentence: where this beat ends}}
[/ENDING_STATE]
---"""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are a prose writer generating a single story beat. Be concise and vivid.",
            function=LLMFunction.STORY_GENERATION
        )

        # Parse response
        prose_match = re.search(
            r'\[BEAT_PROSE\]\s*(.*?)\s*\[/BEAT_PROSE\]',
            response, re.DOTALL
        )
        prose = prose_match.group(1).strip() if prose_match else response

        ending_match = re.search(
            r'\[ENDING_STATE\]\s*(.*?)\s*(?:\[/ENDING_STATE\]|---|\Z)',
            response, re.DOTALL
        )
        ending = ending_match.group(1).strip() if ending_match else ""

        return GeneratedChunk(
            chunk_id=f"chunk_{beat.beat_id}",
            scene_id=scene.scene_id,
            beat_ids=[beat.beat_id],
            prose=prose,
            word_count=len(prose.split()),
            ending_state=ending
        )

    # =========================================================================
    # PROTOCOL 3: EXPANSION-BASED GENERATION
    # =========================================================================

    async def _expansion_generation(self, script: ScriptOutline) -> str:
        """Generate prose through progressive expansion passes."""
        logger.info("Using Expansion-Based Generation Protocol")

        # Pass 1: Generate skeleton (20% of budget)
        skeleton_budget = int(script.word_budget * 0.2)
        skeleton = await self._generate_skeleton(script, skeleton_budget)

        # Pass 2: Expand each scene paragraph (parallel)
        scene_budgets = self._allocate_scene_budgets(script)
        expansion_tasks = []

        skeleton_parts = skeleton.split("\n\n")
        for i, scene in enumerate(script.scenes):
            scene_skeleton = skeleton_parts[i] if i < len(skeleton_parts) else ""
            budget = scene_budgets.get(scene.scene_id, 200)
            expansion_tasks.append(
                self._expand_scene(scene, scene_skeleton, budget)
            )

        expanded_scenes = await asyncio.gather(*expansion_tasks, return_exceptions=True)

        # Handle failures
        valid_scenes = []
        for i, result in enumerate(expanded_scenes):
            if isinstance(result, Exception):
                logger.error(f"Scene expansion failed: {result}")
                valid_scenes.append(skeleton_parts[i] if i < len(skeleton_parts) else "")
            else:
                valid_scenes.append(result)

        # Pass 3: Detail enhancement (parallel)
        enhancement_tasks = [
            self._enhance_scene(scene_prose)
            for scene_prose in valid_scenes
        ]

        enhanced_scenes = await asyncio.gather(*enhancement_tasks, return_exceptions=True)

        final_scenes = []
        for i, result in enumerate(enhanced_scenes):
            if isinstance(result, Exception):
                final_scenes.append(valid_scenes[i])
            else:
                final_scenes.append(result)

        # Pass 4: Final synthesis
        prose = "\n\n".join(final_scenes)

        logger.info(f"Generated {len(prose.split())} words through expansion")

        return prose

    async def _generate_skeleton(self, script: ScriptOutline, budget: int) -> str:
        """Generate compressed skeleton of entire story."""
        scenes_desc = "\n".join([
            f"Scene {s.scene_number}: {s.title} - {s.purpose}"
            for s in script.scenes
        ])

        prompt = f"""Generate a compressed skeleton of this story.

STORY OUTLINE:
{scenes_desc}

WORD BUDGET: {budget} words total

Write ONE paragraph per scene capturing:
- Key action
- Essential dialogue (if any)
- Emotional beat

This skeleton will be expanded later. Focus on narrative flow.

OUTPUT: One paragraph per scene, separated by blank lines."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are generating a story skeleton. Be concise but capture essence.",
            function=LLMFunction.STORY_GENERATION
        )

        return response

    async def _expand_scene(
        self,
        scene: Scene,
        skeleton: str,
        budget: int
    ) -> str:
        """Expand a skeleton paragraph into full scene prose."""
        prompt = f"""Expand this scene skeleton into full prose.

SKELETON:
{skeleton}

SCENE DETAILS:
Title: {scene.title}
Purpose: {scene.purpose}
Location: [{scene.location_tag}]
Characters: {', '.join(scene.characters)}

WORD BUDGET: {budget} words

Add:
- Sensory detail
- Expanded dialogue
- Character interiority
- Environmental detail

Maintain the skeleton's narrative beats while enriching the prose."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are expanding a scene skeleton into rich prose.",
            function=LLMFunction.STORY_GENERATION
        )

        return response

    async def _enhance_scene(self, scene_prose: str) -> str:
        """Enhance scene with additional detail passes."""
        prompt = f"""Enhance this scene prose with additional detail.

CURRENT PROSE:
{scene_prose}

Add subtle enhancements:
1. Physicality: Character movements, gestures
2. Sensory: Sights, sounds, textures
3. Subtext: What's unsaid, underlying tension

DO NOT significantly increase word count.
DO NOT change events or dialogue.
Make surgical enhancements only."""

        response = await self.llm_caller(
            prompt=prompt,
            system_prompt="You are enhancing prose with subtle detail. Minimal changes only.",
            function=LLMFunction.STORY_ANALYSIS
        )

        return response
