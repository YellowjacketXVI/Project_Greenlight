# UI & Pipeline Improvements Discussion
## Verbatim Analysis and Planning Session

**Date:** 2025-12-12  
**Status:** Planning  

---

# Updated Analysis Based on Your Clarifications

## 1. Seedream Aspect Ratio Fix

**Current Problem** (from `greenlight/llm/api_clients.py` line 498):
```python
"aspect_ratio": "match_input_image" if image_input else aspect_ratio
```

When reference images exist, it uses `match_input_image` which inherits the aspect ratio from the **first** reference image. If that reference is a character portrait (e.g., 1:1 or 4:3), the output will be wrong.

**Current Behavior** (from `greenlight/core/image_handler.py` lines 374-384):
```python
if not request.reference_images:
    empty_img = self._create_empty_image(1920, 1080)  # Only when NO references
    ref_images.append(...)
else:
    for img_path in request.reference_images:  # Just adds references directly
        ...
```

**Required Fix**:
- **ALWAYS** insert a blank 16:9 2K image (2560x1440) as the **first** image in `ref_images`
- This ensures Seedream always outputs 16:9 regardless of reference image dimensions
- The blank image acts as an aspect ratio template that Seedream will match

### Suggested Implementation

**File:** `greenlight/core/image_handler.py`

**Location:** `_generate_seedream()` method (lines 374-384)

```python
async def _generate_seedream(self, request: ImageGenerationRequest) -> ImageGenerationResult:
    """Generate image using Seedream 4.5."""

    ref_images = []

    # ALWAYS insert blank 16:9 2K as FIRST image - this is mandatory
    # Seedream uses "match_input_image" which inherits aspect ratio from first image
    empty_img = self._create_empty_image(2560, 1440)  # 16:9 at 2K resolution
    empty_base64 = self._image_to_base64(empty_img)
    ref_images.append(empty_base64)

    # Then add any reference images AFTER the blank template
    if request.reference_images:
        for img_path in request.reference_images:
            if Path(img_path).exists():
                img_base64 = self._load_image_as_base64(img_path)
                ref_images.append(img_base64)

    # Now ref_images[0] is always the 16:9 template
    # Seedream will match this aspect ratio regardless of other references
    ...
```

**Key Changes:**
1. Remove the `if not request.reference_images:` conditional
2. Always create and prepend the blank 16:9 image first
3. Append reference images after the blank template

---

## 2. Storyboard Zoom Behavior

**Your Specification**:
- Under 50% zoom = Grid View with 3 columns at 49% → 10 columns at 1%
- Over 50% zoom = Row View with 10 images at 55% → 1 image at 100%

**Current Implementation** (from `storyboard_table.py`):
```python
def get_grid_columns(self) -> int:
    # Currently: 10 → 2 columns (wrong minimum)
    
def get_row_visible_count(self) -> int:
    # Currently: 5 → 1 (wrong maximum)
```

**Required Changes**:

| Zoom % | Mode | Columns/Images |
|--------|------|----------------|
| 1% | Grid | 10 columns |
| 25% | Grid | ~6 columns |
| 49% | Grid | 3 columns |
| 50% | Threshold | Switch to Row |
| 55% | Row | 10 images visible |
| 75% | Row | ~5 images visible |
| 100% | Row | 1 image visible |

### Suggested Implementation

**File:** `greenlight/ui/components/storyboard_table.py`

**Location:** `ZoomController` class

```python
class ZoomController:
    """Controls zoom behavior for storyboard display."""

    def get_grid_columns(self) -> int:
        """
        Calculate number of columns for grid view (zoom < 50%).

        Zoom 1% = 10 columns
        Zoom 49% = 3 columns
        Linear interpolation between.
        """
        if self.zoom_level >= 50:
            return 3  # Minimum for grid mode

        # Map 1-49% to 10-3 columns
        # At 1%: 10 cols, at 49%: 3 cols
        zoom_normalized = (self.zoom_level - 1) / 48  # 0.0 to 1.0
        columns = 10 - int(zoom_normalized * 7)  # 10 down to 3
        return max(3, min(10, columns))

    def get_row_visible_count(self) -> int:
        """
        Calculate number of visible images for row view (zoom >= 50%).

        Zoom 50% = 10 images visible
        Zoom 100% = 1 image visible
        Linear interpolation between.
        """
        if self.zoom_level < 50:
            return 10  # Maximum for row mode

        # Map 50-100% to 10-1 images
        # At 50%: 10 images, at 100%: 1 image
        zoom_normalized = (self.zoom_level - 50) / 50  # 0.0 to 1.0
        visible = 10 - int(zoom_normalized * 9)  # 10 down to 1
        return max(1, min(10, visible))

    def is_grid_mode(self) -> bool:
        """Return True if zoom < 50% (grid mode), False for row mode."""
        return self.zoom_level < 50
```

**Key Changes:**
1. Grid mode: 10 → 3 columns (not 10 → 2)
2. Row mode: 10 → 1 images (not 5 → 1)
3. Threshold at exactly 50%

---

## 3. World Attributes

**Your Specification**: A set of description parameters per tag that must be populated - a description of how they fit in with the time period and genre.

**Implementation**: Add `world_attributes` field to each tag entry in world_config.json:

```json
{
  "tag": "CHAR_MEI",
  "name": "Mei",
  "world_attributes": "A high-class courtesan in feudal China, trained in refined arts befitting the era's expectations of entertainment and beauty. Her education and mannerisms reflect the cultural emphasis on poetry, music, and strategic games like Go."
}
```

This field describes how the character/location/prop fits within:
- The time period (feudal China, Victorian England, etc.)
- The genre (drama, action, romance, etc.)
- Cultural context and expectations

### Suggested Implementation

**File:** `greenlight/pipelines/world_bible_pipeline.py`

**Step 1: Add to CharacterProfile dataclass**
```python
@dataclass
class CharacterProfile:
    # ... existing fields ...
    world_attributes: str = ""  # NEW: How this character fits time period/genre
```

**Step 2: Add to LocationProfile and PropProfile dataclasses**
```python
@dataclass
class LocationProfile:
    # ... existing fields ...
    world_attributes: str = ""  # NEW: How this location fits time period/genre

@dataclass
class PropProfile:
    # ... existing fields ...
    world_attributes: str = ""  # NEW: How this prop fits time period/genre
```

**Step 3: Update CharacterResearchAgent prompt to generate world_attributes**

Add to the research prompt in `CharacterResearchAgent`:
```python
RESEARCH_FOCUSES = {
    # ... existing focuses ...
    "world_context": "How this character fits within the time period, genre, and cultural context"
}
```

**Step 4: Update the parsing to extract world_attributes**

In `_parse_character_profile()`:
```python
def _parse_character_profile(self, tag: str, content: str) -> CharacterProfile:
    # ... existing parsing ...

    # Extract world_attributes
    world_attributes = self._extract_section(content, "WORLD CONTEXT") or \
                       self._extract_section(content, "WORLD ATTRIBUTES") or ""

    return CharacterProfile(
        # ... existing fields ...
        world_attributes=world_attributes
    )
```

**Step 5: Include time_period and genre in research context**

Ensure the research prompt includes project-level time_period and genre:
```python
research_context = f"""
PROJECT CONTEXT:
Time Period: {input_data.time_period}
Genre: {input_data.genre}

CHARACTER TO RESEARCH: {tag}
...
"""
```

---

## 4. Character Dialogue Fields

**Your Specification**: Add fields for roleplay and dialogue creation in the writer pipeline.

**New Fields**:

| Field | Purpose | Example |
|-------|---------|---------|
| `personality` | Core personality traits | "Virtuous, intelligent, quietly determined, yearning for freedom" |
| `speech_style` | How they speak | "Refined, poetic, measured - trained in the arts of conversation" |
| `literacy_level` | Education affecting speech patterns | "Highly educated in classical arts, poetry, and strategy" |

**Schema Update**:
```json
{
  "tag": "CHAR_MEI",
  "name": "Mei",
  "personality": "Virtuous, intelligent, quietly determined, yearning for freedom",
  "speech_style": "Refined, poetic, measured - trained in the arts of conversation",
  "literacy_level": "Highly educated in classical arts, poetry, and strategy"
}
```

### Suggested Implementation

**File:** `greenlight/pipelines/world_bible_pipeline.py`

**Step 1: Add to CharacterProfile dataclass**
```python
@dataclass
class CharacterProfile:
    # ... existing fields ...
    personality: str = ""        # NEW: Core personality traits
    speech_style: str = ""       # NEW: How they speak
    literacy_level: str = ""     # NEW: Education affecting speech patterns
```

**Step 2: Update CharacterResearchAgent RESEARCH_FOCUSES**

Modify the existing "speech" focus to be more specific:
```python
RESEARCH_FOCUSES = {
    "identity": "Core identity, name, role, age, ethnicity, backstory",
    "psychology": "Internal voice, fears, desires, coping mechanisms, PERSONALITY TRAITS",
    "speech": "Dialogue patterns, vocabulary, SPEECH STYLE, LITERACY LEVEL, communication style",
    "physicality": "Movement, gestures, physical presence, body language",
    "decisions": "Decision heuristics, relationships, moral compass"
}
```

**Step 3: Update research prompt to explicitly request these fields**

In `CharacterResearchAgent.generate_proposal()`:
```python
prompt = f"""
Research the character {character_tag} for the following focus: {self.focus}

{context}

For PSYCHOLOGY focus, include:
- PERSONALITY: Core personality traits (3-5 key traits)

For SPEECH focus, include:
- SPEECH_STYLE: How they speak (formal/casual, poetic/direct, etc.)
- LITERACY_LEVEL: Education level affecting vocabulary and speech patterns

Output in structured format with clear section headers.
"""
```

**Step 4: Update parsing to extract new fields**

In `_parse_character_profile()`:
```python
def _parse_character_profile(self, tag: str, content: str) -> CharacterProfile:
    # ... existing parsing ...

    # Extract new dialogue fields
    personality = self._extract_section(content, "PERSONALITY") or ""
    speech_style = self._extract_section(content, "SPEECH_STYLE") or \
                   self._extract_section(content, "SPEECH STYLE") or ""
    literacy_level = self._extract_section(content, "LITERACY_LEVEL") or \
                     self._extract_section(content, "LITERACY LEVEL") or ""

    return CharacterProfile(
        # ... existing fields ...
        personality=personality,
        speech_style=speech_style,
        literacy_level=literacy_level
    )
```

**Step 5: Use in dialogue generation**

**File:** `greenlight/agents/dialogue_consensus.py`

```python
def _build_character_context(self, character: str, profile: CharacterProfile) -> str:
    """Build rich character context for roleplay dialogue generation."""
    return f"""
CHARACTER: {character}
PERSONALITY: {profile.personality}
SPEECH STYLE: {profile.speech_style}
LITERACY LEVEL: {profile.literacy_level}

When generating dialogue for this character:
- Match their speech style (formal/casual, poetic/direct)
- Use vocabulary appropriate to their literacy level
- Express their personality through word choice and sentence structure
"""
```

---

## 5. Physiological/Physical Tells (NOT Verbal Ticks)

**Your Clarification**: NOT verbal ticks but physiological ticks - how characters physically express emotions like annoyance, intrigue, mannerism, excitement, embarrassment.

**What This Means**: Observable physical behaviors that express internal emotional states through body language, facial expressions, posture changes, and physical mannerisms.

| Emotion | Physical Expression Example |
|---------|----------------------------|
| **Annoyance** | Jaw tightening, eye roll, crossed arms, tapping fingers |
| **Intrigue** | Leaning forward, raised eyebrow, tilted head, narrowed eyes |
| **Excitement** | Widened eyes, quickened breathing, animated gestures, bouncing |
| **Embarrassment** | Flushed cheeks, averted gaze, touching face/neck, shrinking posture |
| **Nervousness** | Fidgeting, avoiding eye contact, wringing hands, shifting weight |
| **Confidence** | Expanded posture, steady gaze, deliberate movements, space-taking |
| **Anger** | Clenched fists, flared nostrils, rigid posture, intense stare |
| **Fear** | Pale complexion, shallow breathing, frozen stance, wide eyes |
| **Vulnerability** | Hunched shoulders, arms wrapped around self, soft voice |
| **Joy** | Genuine smile reaching eyes, open posture, light movements |

**Schema Update**:
```json
{
  "tag": "CHAR_MEI",
  "emotional_tells": {
    "annoyance": "A subtle tightening at the corners of her eyes, fingers drumming once on any nearby surface before stilling with visible effort.",
    "intrigue": "Head tilts almost imperceptibly, eyes widen slightly, and she leans forward just enough to close distance without seeming aggressive.",
    "excitement": "Quick intake of breath, eyes brightening, hands clasping together or gesturing with unusual animation.",
    "embarrassment": "Color rising to cheeks, gaze dropping to study hands or nearby objects, shoulders drawing inward.",
    "nervousness": "Smoothing fabric of clothing repeatedly, weight shifting from foot to foot, avoiding prolonged eye contact.",
    "confidence": "Shoulders back, chin level, movements deliberate and unhurried, maintaining steady eye contact.",
    "anger": "Stillness that precedes storm—jaw set, nostrils flaring slightly, hands pressed flat against surfaces.",
    "fear": "Pallor replacing natural color, breathing becoming shallow, body poised for flight.",
    "vulnerability": "Arms crossing protectively, voice softening, seeking corners or walls for psychological support.",
    "joy": "Genuine smile reaching eyes, posture opening, movements becoming lighter and more fluid."
  }
}
```

### Suggested Implementation

**File:** `greenlight/pipelines/world_bible_pipeline.py`

**Step 1: Add to CharacterProfile dataclass**
```python
@dataclass
class CharacterProfile:
    # ... existing fields ...
    emotional_tells: Dict[str, str] = field(default_factory=dict)  # NEW
```

**Step 2: Define the emotions list as a constant**
```python
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
```

**Step 3: Use in dialogue generation for action beats**

**File:** `greenlight/agents/dialogue_consensus.py`

```python
def _build_character_context(self, character: str, profile: CharacterProfile) -> str:
    """Build rich character context including emotional tells for action beats."""

    tells_text = ""
    if profile.emotional_tells:
        tells_text = "\n".join([
            f"  - {emotion.upper()}: {description}"
            for emotion, description in profile.emotional_tells.items()
        ])

    return f"""
CHARACTER: {character}
...

PHYSIOLOGICAL TELLS (use these for action beats in dialogue):
{tells_text}

When writing dialogue, include action beats that show these physical expressions
rather than telling the reader what the character feels.
"""
```

**Step 4: Use in visual script for storyboard expressions**

When generating frame descriptions, include the relevant emotional tell based on the scene's emotional context.

---

## 6. Physiological Tells Assembly with Claude Haiku

**Your Suggestion**: Add an assembly agent mode step for creating physiological/physical tells using hardcoded Claude Haiku.

### Why Claude Haiku?

| Aspect | Haiku Advantage |
|--------|-----------------|
| **Speed** | ~3x faster than Sonnet |
| **Cost** | ~10x cheaper than Sonnet |
| **Task Fit** | Simple, focused prompts (2-3 sentence outputs) |
| **Parallel Calls** | 10 agents + 3 judges = 13 calls per character |

### Cost Analysis (per project with 3 characters)

- **With Sonnet**: 39 calls × ~$0.003 = ~$0.12
- **With Haiku**: 39 calls × ~$0.0003 = ~$0.012 (10x cheaper)

### Hardcoded Model ID
```
claude-haiku-4-5-20251001
```

### Assembly Pattern Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHYSIOLOGICAL TELLS ASSEMBLY                             │
│                    (Hardcoded Claude Haiku)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  INPUT: CharacterProfile (from main character research)                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 10 PARALLEL PROPOSAL AGENTS (one per emotion)                       │   │
│  │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │ │Annoyance│ │Intrigue │ │Excite-  │ │Embarrass│ │Nervous- │        │   │
│  │ │  Agent  │ │  Agent  │ │ment Agt │ │  Agent  │ │ness Agt │        │   │
│  │ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │ │Confid-  │ │ Anger   │ │  Fear   │ │Vulnera- │ │   Joy   │        │   │
│  │ │ence Agt │ │  Agent  │ │  Agent  │ │bility   │ │  Agent  │        │   │
│  │ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 3 JUDGES                                                            │   │
│  │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                     │   │
│  │ │ Authenticity│ │Visual Clarity│ │Cultural Fit │                    │   │
│  │ │    Judge    │ │    Judge    │ │    Judge    │                     │   │
│  │ └─────────────┘ └─────────────┘ └─────────────┘                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ CALCULATOR → SYNTHESIZER                                            │   │
│  │ Aggregate rankings → Merge best tells → Output emotional_tells dict │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  OUTPUT: emotional_tells: Dict[str, str]                                   │
│  {                                                                          │
│    "annoyance": "A subtle tightening at the corners of her eyes...",       │
│    "intrigue": "Head tilts almost imperceptibly, eyes widen slightly...",  │
│    ...                                                                      │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Summary

| Component | Model | Count | Purpose |
|-----------|-------|-------|---------|
| Proposal Agents | Claude Haiku | 10 | Generate tells for each emotion |
| Judge Agents | Claude Haiku | 3 | Evaluate authenticity, visual clarity, cultural fit |
| Calculator | No LLM | 1 | Aggregate judge rankings |
| Synthesizer | Claude Haiku | 1 | Merge best tells into final dict |

### Hardcoded Haiku Caller Pattern

```python
class WorldBiblePipeline(BasePipeline):
    def __init__(self, ...):
        # ... existing init ...

        # Create hardcoded Haiku caller for physiological tells
        # This is separate from the main llm_caller to ensure Haiku is always used
        self._haiku_client = AnthropicClient()

    async def _haiku_caller(self, prompt: str) -> str:
        """Hardcoded Claude Haiku caller for physiological tells assembly."""
        import asyncio
        response = await asyncio.to_thread(
            self._haiku_client.generate_text,
            prompt,
            system="You are a character behavior specialist focusing on physical expressions of emotion.",
            max_tokens=500,  # Small output for efficiency
            model="claude-haiku-4-5-20251001"  # HARDCODED HAIKU
        )
        return response.text
```

### Proposal Agent Implementation

```python
class PhysiologicalTellsAgent(ProposalAgent):
    """
    Proposal agent for generating physiological tells for a specific emotion.
    Uses hardcoded Claude Haiku for cost efficiency.
    """

    EMOTIONS = [
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
```

### Assembly Execution

```python
async def _generate_physiological_tells(
    self,
    character_profile: CharacterProfile,
    input_data: WorldBibleInput
) -> Dict[str, str]:
    """
    Generate physiological tells using assembly pattern with hardcoded Haiku.

    10 parallel agents (one per emotion) → 3 judges → Calculator → Synthesizer
    """

    # Create 10 proposal agents (one per emotion)
    emotions = PhysiologicalTellsAgent.EMOTIONS
    proposal_agents = [
        PhysiologicalTellsAgent(
            f"tells_agent_{i}",
            emotion,
            self._haiku_caller  # Hardcoded Haiku
        )
        for i, emotion in enumerate(emotions)
    ]

    # Create 3 judges (also using Haiku for cost efficiency)
    judge_agents = [
        PhysiologicalTellsJudge(f"tells_judge_{i}", criterion, self._haiku_caller)
        for i, criterion in enumerate([
            "authenticity",      # Does this match the character's personality?
            "visual_clarity",    # Is this visually describable for storyboards?
            "cultural_fit"       # Does this fit the time period/genre?
        ])
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
        "character_name": character_profile.name,
        "character_profile": f"""
Name: {character_profile.name}
Role: {character_profile.role}
Personality: {character_profile.psychology}
Physicality: {character_profile.physicality}
Age: {character_profile.age}
Ethnicity: {character_profile.ethnicity}
""",
        "time_period": input_data.time_period,
        "genre": input_data.genre
    }

    # Execute assembly
    result = await assembly.execute(context)

    # Parse result into emotional_tells dict
    return self._parse_emotional_tells(result.content)
```

### Integration Point

```python
async def _research_single_character(self, tag: str, input_data: WorldBibleInput):
    # ... existing assembly pattern for main profile ...
    profile = self._parse_character_profile(tag, result.content)

    # NEW: Generate physiological tells using Haiku assembly
    profile.emotional_tells = await self._generate_physiological_tells(
        profile, input_data
    )

    return profile
```

---

## 7. OmniMind Character Modification Process

**Your Requirement**: OmniMind should have the logic to do character modification processes universally for any topic or character change required by the user.

### Flow for Character Modification

```
User Request: "Change Lin's appearance"
    ↓
[1] OmniMind: Update world_config.json
    - Modify "appearance" field
    - Modify "costume" field
    ↓
[2] OmniMind: Update key reference image
    - New reference image path in world_config.json
    ↓
[3] OmniMind: Archive old storyboard images
    - Move to storyboards/archive/{timestamp}/
    ↓
[4] OmniMind: Regenerate storyboard frames
    - Find all frames where character appears
    - Regenerate with new reference
```

### Archive Structure

```
projects/{project}/storyboards/
├── scene_1/
│   ├── frame_1.1.png (current)
│   └── archive/
│       └── 2025-12-12_143022/
│           └── frame_1.1.png (previous)
```

### Suggested Implementation

**File:** `greenlight/omni_mind/tool_executor.py`

**Step 1: Add character modification tool**
```python
def _register_tools(self):
    # ... existing registrations ...

    self._register_tool("modify_character", self._modify_character,
        "Modify a character's attributes in world_config.json and optionally regenerate storyboards.",
        {"character_tag": {"type": "string", "description": "Character tag (e.g., CHAR_LIN)"},
         "appearance": {"type": "string", "description": "New appearance description (optional)"},
         "costume": {"type": "string", "description": "New costume description (optional)"},
         "reference_image": {"type": "string", "description": "Path to new reference image (optional)"},
         "regenerate_frames": {"type": "boolean", "description": "Whether to regenerate storyboard frames"}},
        ["character_tag"],
        ToolCategory.CONTENT_MODIFICATION)
```

**Step 2: Implement the modification method**
```python
async def _modify_character(
    self,
    character_tag: str,
    appearance: str = None,
    costume: str = None,
    reference_image: str = None,
    regenerate_frames: bool = False
) -> Dict[str, Any]:
    """
    Modify a character's attributes and optionally regenerate storyboards.

    Flow:
    1. Load world_config.json
    2. Find character by tag
    3. Update specified fields
    4. If reference_image provided, update reference path
    5. Save world_config.json
    6. If regenerate_frames:
       a. Archive existing storyboard images
       b. Find frames where character appears
       c. Trigger regeneration
    """
    project_path = self._get_current_project_path()
    world_config_path = project_path / "world_bible" / "world_config.json"

    # Load config
    with open(world_config_path, 'r') as f:
        config = json.load(f)

    # Find character
    character = None
    for char in config.get("characters", []):
        if char.get("tag") == character_tag:
            character = char
            break

    if not character:
        return {"success": False, "error": f"Character {character_tag} not found"}

    # Update fields
    if appearance:
        character["appearance"] = appearance
    if costume:
        character["costume"] = costume
    if reference_image:
        character["reference_image"] = reference_image

    # Save config
    with open(world_config_path, 'w') as f:
        json.dump(config, f, indent=2)

    result = {"success": True, "updated_fields": []}
    if appearance:
        result["updated_fields"].append("appearance")
    if costume:
        result["updated_fields"].append("costume")
    if reference_image:
        result["updated_fields"].append("reference_image")

    # Regenerate if requested
    if regenerate_frames:
        archive_result = await self._archive_character_frames(character_tag)
        regen_result = await self._regenerate_character_frames(character_tag)
        result["archive"] = archive_result
        result["regeneration"] = regen_result

    return result
```

**Step 3: Add archive helper method**
```python
async def _archive_character_frames(self, character_tag: str) -> Dict[str, Any]:
    """Archive storyboard frames containing the specified character."""
    import shutil
    from datetime import datetime

    project_path = self._get_current_project_path()
    storyboards_path = project_path / "storyboards"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    archived_files = []

    # Find all frames with this character
    for scene_dir in storyboards_path.iterdir():
        if not scene_dir.is_dir() or scene_dir.name == "archive":
            continue

        archive_dir = scene_dir / "archive" / timestamp

        for frame_file in scene_dir.glob("*.png"):
            # Check if character appears in this frame (via visual_script.json)
            if self._character_in_frame(character_tag, frame_file.stem):
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_path = archive_dir / frame_file.name
                shutil.copy2(frame_file, archive_path)
                archived_files.append(str(frame_file))

    return {"archived_count": len(archived_files), "archived_files": archived_files}
```

**Step 4: Add regeneration helper method**
```python
async def _regenerate_character_frames(self, character_tag: str) -> Dict[str, Any]:
    """Regenerate storyboard frames containing the specified character."""
    # Find frames with this character
    frames_to_regenerate = self._find_frames_with_character(character_tag)

    # Trigger regeneration via director pipeline or image handler
    regenerated = []
    for frame_id in frames_to_regenerate:
        # Use existing regeneration infrastructure
        result = await self._regenerate_single_frame(frame_id)
        if result.get("success"):
            regenerated.append(frame_id)

    return {"regenerated_count": len(regenerated), "frames": regenerated}
```

---

## 8. Reference Modal Improvements

**Your Requirements**:
- Generate sheet button should only appear on individual loaded images (to convert that image to a sheet)
- Starred/key reference image gets a labeled frame
- Key reference is flattened into a single image before being used as input for generation

### Suggested Implementation

**File:** `greenlight/ui/dialogs/reference_modal.py`

**Step 1: Add generate sheet button to individual images only**
```python
class ReferenceImageCard(QWidget):
    """Card widget for a single reference image."""

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Image display
        self.image_label = QLabel()
        self.image_label.setPixmap(self._load_thumbnail())
        layout.addWidget(self.image_label)

        # Button row
        button_row = QHBoxLayout()

        # Star/key button
        self.star_btn = QPushButton("★")
        self.star_btn.setCheckable(True)
        self.star_btn.clicked.connect(self._toggle_key_reference)
        button_row.addWidget(self.star_btn)

        # Generate sheet button - ONLY on individual loaded images
        self.sheet_btn = QPushButton("Generate Sheet")
        self.sheet_btn.clicked.connect(self._generate_sheet_from_image)
        button_row.addWidget(self.sheet_btn)

        layout.addLayout(button_row)

    def _toggle_key_reference(self):
        """Toggle this image as the key reference."""
        if self.star_btn.isChecked():
            # Add labeled frame to indicate key reference
            self._add_key_frame()
            self.key_reference_changed.emit(self.image_path)
        else:
            self._remove_key_frame()

    def _add_key_frame(self):
        """Add a labeled frame around the key reference image."""
        # Add visual indicator (colored border + "KEY" label)
        self.setStyleSheet("border: 3px solid gold;")
        # Add "KEY REFERENCE" label overlay

    def _generate_sheet_from_image(self):
        """Convert this single image into a character sheet."""
        # Call sheet generation with this image as input
        self.generate_sheet_requested.emit(self.image_path)
```

**Step 2: Flatten key reference before generation**
```python
def get_flattened_key_reference(self) -> Optional[str]:
    """
    Get the key reference image, flattened to a single image.

    If the key reference has a labeled frame, flatten it into
    a single image file before returning the path.
    """
    if not self.key_reference_path:
        return None

    # If key reference has overlay/frame, flatten it
    if self._has_key_frame_overlay():
        flattened_path = self._flatten_with_frame(self.key_reference_path)
        return flattened_path

    return self.key_reference_path

def _flatten_with_frame(self, image_path: str) -> str:
    """Flatten image with its labeled frame into a single image."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(image_path)

    # Add frame
    draw = ImageDraw.Draw(img)
    # Draw gold border
    border_width = 5
    draw.rectangle(
        [0, 0, img.width - 1, img.height - 1],
        outline="gold",
        width=border_width
    )

    # Add "KEY REFERENCE" label
    font = ImageFont.load_default()
    draw.text((10, 10), "KEY REFERENCE", fill="gold", font=font)

    # Save flattened version
    flattened_path = Path(image_path).parent / f"{Path(image_path).stem}_key_flattened.png"
    img.save(flattened_path)

    return str(flattened_path)
```

---

## 9. Storyboard Frame Selection for Regeneration

**Your Requirement**: Add storyboard image selection for regeneration on the panel itself for the user and for OmniMind to backdoor it.

### UI Component
- Add selection checkboxes or click-to-select on storyboard frames
- Add "Regenerate Selected" button

### OmniMind Backdoor
- Add tool for programmatic frame selection
- Add tool for triggering regeneration of selected frames

### Suggested Implementation

**File:** `greenlight/ui/components/storyboard_table.py`

**Step 1: Add selection state to frame cards**
```python
class StoryboardFrameCard(QWidget):
    """Card widget for a single storyboard frame with selection support."""

    selection_changed = Signal(str, bool)  # frame_id, is_selected

    def __init__(self, frame_id: str, image_path: str, parent=None):
        super().__init__(parent)
        self.frame_id = frame_id
        self.image_path = image_path
        self.is_selected = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Selection checkbox
        self.select_checkbox = QCheckBox()
        self.select_checkbox.stateChanged.connect(self._on_selection_changed)

        # Image display
        self.image_label = ClickableLabel()
        self.image_label.clicked.connect(self._toggle_selection)

        # Frame ID label
        self.id_label = QLabel(self.frame_id)

        layout.addWidget(self.select_checkbox)
        layout.addWidget(self.image_label)
        layout.addWidget(self.id_label)

    def _toggle_selection(self):
        """Toggle selection on click."""
        self.select_checkbox.setChecked(not self.select_checkbox.isChecked())

    def _on_selection_changed(self, state):
        """Handle selection state change."""
        self.is_selected = state == Qt.Checked
        self._update_visual_state()
        self.selection_changed.emit(self.frame_id, self.is_selected)

    def _update_visual_state(self):
        """Update visual appearance based on selection."""
        if self.is_selected:
            self.setStyleSheet("border: 2px solid #4CAF50; background: rgba(76, 175, 80, 0.1);")
        else:
            self.setStyleSheet("")

    def set_selected(self, selected: bool):
        """Programmatically set selection state (for OmniMind backdoor)."""
        self.select_checkbox.setChecked(selected)
```

**File:** `greenlight/ui/panels/storyboard_panel.py`

**Step 2: Add regenerate selected button**
```python
class StoryboardPanel(QWidget):
    def _setup_toolbar(self):
        # ... existing toolbar setup ...

        # Add regenerate selected button
        self.regenerate_selected_btn = QPushButton("Regenerate Selected")
        self.regenerate_selected_btn.clicked.connect(self._regenerate_selected_frames)
        self.regenerate_selected_btn.setEnabled(False)  # Disabled until frames selected
        self.toolbar.addWidget(self.regenerate_selected_btn)

        # Add select all / deselect all
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all_frames)
        self.toolbar.addWidget(self.select_all_btn)

    def _on_frame_selection_changed(self, frame_id: str, is_selected: bool):
        """Handle frame selection changes."""
        if is_selected:
            self.selected_frames.add(frame_id)
        else:
            self.selected_frames.discard(frame_id)

        # Enable/disable regenerate button
        self.regenerate_selected_btn.setEnabled(len(self.selected_frames) > 0)
        self.regenerate_selected_btn.setText(f"Regenerate Selected ({len(self.selected_frames)})")

    async def _regenerate_selected_frames(self):
        """Regenerate all selected frames."""
        for frame_id in self.selected_frames:
            await self._regenerate_frame(frame_id)

        # Clear selection after regeneration
        self._deselect_all_frames()
```

**File:** `greenlight/omni_mind/tool_executor.py`

**Step 3: Add OmniMind backdoor tools**
```python
def _register_tools(self):
    # ... existing registrations ...

    self._register_tool("select_storyboard_frames", self._select_storyboard_frames,
        "Select storyboard frames for regeneration.",
        {"frame_ids": {"type": "array", "description": "List of frame IDs to select (e.g., ['frame_1.1', 'frame_1.2'])"},
         "select": {"type": "boolean", "description": "True to select, False to deselect"}},
        ["frame_ids"],
        ToolCategory.FILE_MANAGEMENT)

    self._register_tool("regenerate_selected_frames", self._regenerate_selected_frames,
        "Regenerate currently selected storyboard frames.",
        {},
        [],
        ToolCategory.PIPELINE)

async def _select_storyboard_frames(self, frame_ids: List[str], select: bool = True) -> Dict[str, Any]:
    """Select or deselect storyboard frames via backdoor."""
    # Send command to UI via backdoor socket
    command = {
        "action": "select_frames",
        "frame_ids": frame_ids,
        "select": select
    }
    response = await self._send_backdoor_command(command)
    return response

async def _regenerate_selected_frames(self) -> Dict[str, Any]:
    """Trigger regeneration of selected frames via backdoor."""
    command = {"action": "regenerate_selected"}
    response = await self._send_backdoor_command(command)
    return response
```

---

## Files to Modify Summary

| File | Changes |
|------|---------|
| `greenlight/core/image_handler.py` | Always insert blank 16:9 2K as FIRST image for Seedream |
| `greenlight/ui/components/storyboard_table.py` | Fix zoom thresholds (3-10 cols grid, 10-1 images row) |
| `greenlight/ui/panels/scripts_panel.py` | Add Visual Script tab |
| `greenlight/pipelines/world_bible_pipeline.py` | Add CharacterProfile fields, Haiku caller, physiological tells assembly |
| `greenlight/agents/dialogue_consensus.py` | Include emotional_tells in roleplay prompts |
| `greenlight/omni_mind/tool_executor.py` | Add character modification tools, frame regeneration backdoor |
| `greenlight/ui/dialogs/reference_modal.py` | Generate sheet button, key reference handling |
| `greenlight/ui/panels/storyboard_panel.py` | Frame selection UI, regenerate selected button |
| `projects/*/world_bible/world_config.json` | Schema includes new fields |

---

## CharacterProfile Dataclass Update

```python
@dataclass
class CharacterProfile:
    tag: str
    name: str
    role: str
    age: str = ""
    ethnicity: str = ""
    backstory: str = ""
    visual_appearance: str = ""
    costume: str = ""
    psychology: str = ""
    speech_patterns: str = ""
    physicality: str = ""
    decision_heuristics: str = ""
    relationships: Dict[str, str] = field(default_factory=dict)
    arc: Dict[str, str] = field(default_factory=dict)
    # NEW FIELDS
    personality: str = ""
    speech_style: str = ""
    literacy_level: str = ""
    emotional_tells: Dict[str, str] = field(default_factory=dict)
    world_attributes: str = ""
```

---

## world_config.json Schema Example

```json
{
  "tag": "CHAR_MEI",
  "name": "Mei",
  "role": "Protagonist",
  "age": "Early 20s",
  "ethnicity": "Chinese",
  "appearance": "Delicate features, expressive eyes, graceful bearing",
  "costume": "Elegant silk robes in muted colors, hair ornaments",
  "personality": "Virtuous, intelligent, quietly determined, yearning for freedom",
  "speech_style": "Refined, poetic, measured - trained in the arts of conversation",
  "literacy_level": "Highly educated in classical arts, poetry, and strategy",
  "world_attributes": "A high-class courtesan in feudal China, trained in refined arts befitting the era's expectations of entertainment and beauty. Her education and mannerisms reflect the cultural emphasis on poetry, music, and strategic games like Go.",
  "emotional_tells": {
    "annoyance": "A subtle tightening at the corners of her eyes, fingers drumming once on any nearby surface before stilling with visible effort.",
    "intrigue": "Head tilts almost imperceptibly, eyes widen slightly, and she leans forward just enough to close distance without seeming aggressive.",
    "excitement": "Quick intake of breath, eyes brightening, hands clasping together or gesturing with unusual animation.",
    "embarrassment": "Color rising to cheeks, gaze dropping to study hands or nearby objects, shoulders drawing inward.",
    "nervousness": "Smoothing fabric of clothing repeatedly, weight shifting from foot to foot, avoiding prolonged eye contact.",
    "confidence": "Shoulders back, chin level, movements deliberate and unhurried, maintaining steady eye contact.",
    "anger": "Stillness that precedes storm—jaw set, nostrils flaring slightly, hands pressed flat against surfaces.",
    "fear": "Pallor replacing natural color, breathing becoming shallow, body poised for flight.",
    "vulnerability": "Arms crossing protectively, voice softening, seeking corners or walls for psychological support.",
    "joy": "Genuine smile reaching eyes, posture opening, movements becoming lighter and more fluid."
  }
}
```

---

## Implementation Order

| Priority | Task | Complexity |
|----------|------|------------|
| 1 | Seedream aspect ratio fix | Low |
| 2 | Storyboard zoom behavior | Low |
| 3 | Visual Script tab | Medium |
| 4 | Character dialogue fields (personality, speech_style, literacy_level) | Medium |
| 5 | World attributes field | Medium |
| 6 | Physiological tells assembly with Haiku | High |
| 7 | Storyboard archive functionality | Medium |
| 8 | Frame selection for regeneration | Medium |
| 9 | OmniMind character modification process | High |
| 10 | Reference modal improvements | Medium |

---

## Test Sequence

After implementation:
1. Run Writer Pipeline → Verify new character fields populated
2. Run Director Pipeline → Verify storyboard generation with correct aspect ratio
3. Test zoom behavior at all thresholds
4. Test character modification flow end-to-end
5. Verify archive creation on regeneration

