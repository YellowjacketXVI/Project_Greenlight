# World Building Expansion Plan

## Overview

This document outlines planned improvements to the world building and character processing pipeline to address flat characters and enhance narrative depth. The changes focus on preserving rich research data through the compression layer and providing prose agents with actionable character guidance.

---

## Part 1: Character Depth Improvements

### 1.1 Expand Character Context Limits

**Problem:** Character cards compressed to ~40 words, losing psychology, voice, and physicality.

**Changes:**

| File | Change |
|------|--------|
| `context_compiler.py` | Increase `CHARACTER_CARD_WORD_LIMIT` from 40 to 180 |
| `context_compiler.py` | Restructure `_compile_character_cards()` to include voice and physicality |

**New Character Card Structure:**
```
[TAG] Name - Role, Age
CORE: One-sentence psychological profile
VOICE: Speech style, literacy level, verbal patterns
PHYSICALITY: Movement style, distinctive mannerisms
WANT: External goal (15 words)
NEED: Internal need (15 words)
FLAW: Character limitation (10 words)
```

---

### 1.2 Pass Emotional Tells to Prose Agents

**Problem:** Physiological tells are generated for 10 emotions but never transmitted to prose agents.

**Changes:**

| File | Change |
|------|--------|
| `agent_context_delivery.py` | Add `get_emotional_tells_for_scene()` method |
| `agent_context_delivery.py` | Include relevant tells in `for_prose_agent()` output |
| `context_compiler.py` | Store full `emotional_tells` dict, not just card |

**Implementation:**
```python
def get_emotional_tells_for_scene(self, char_tag: str, scene_emotions: List[str]) -> Dict[str, str]:
    """Extract relevant emotional tells for the scene's emotional context."""
    profile = self.characters.get(char_tag)
    if not profile or not profile.emotional_tells:
        return {}

    return {
        emotion: profile.emotional_tells[emotion]
        for emotion in scene_emotions
        if emotion in profile.emotional_tells
    }
```

**Prose Agent Context Addition:**
```
=== EMOTIONAL TELLS: CHAR_MEI ===
FEAR: Eyes widen briefly, then narrow with calculated focus. Hands still completely.
VULNERABILITY: Eyes soften, shoulders drop slightly, voice becomes whisper-soft.
```

---

### 1.3 Add Voice Signature System

**Problem:** All characters sound similar because speech patterns aren't transmitted.

**New Dataclass:**
```python
@dataclass
class VoiceSignature:
    sentence_structure: str      # "Complex nested clauses" vs "Short, clipped"
    vocabulary_tier: str         # "Classical literary" vs "Street vernacular"
    verbal_tics: List[str]       # Recurring phrases, speech habits
    forbidden_words: List[str]   # Words this character would NEVER use
    sample_lines: List[str]      # 2-3 example lines showing voice
```

**Changes:**

| File | Change |
|------|--------|
| `world_bible_pipeline.py` | Add `VoiceSignature` dataclass |
| `world_bible_pipeline.py` | Generate voice signatures during character research |
| `CharacterProfile` | Add `voice_signature: VoiceSignature` field |
| `context_compiler.py` | Include voice signature in character context |

**Research Prompt Addition:**
```
Generate a voice signature for this character including:
- Sentence structure patterns (complex vs simple, direct vs indirect)
- Vocabulary tier and sources (classical, technical, colloquial)
- 2-3 verbal tics or recurring phrases
- Words this character would NEVER say
- 2-3 sample dialogue lines demonstrating their unique voice
```

---

### 1.4 Implement Character Lens Agent

**Problem:** Gap between rich research data and prose generation.

**New Agent:** `CharacterLensAgent`

**Purpose:** Generate scene-specific character guidance before prose generation.

**Input:**
- Scene outline (location, characters, goal, tension)
- Full character profiles for scene participants
- Current arc progress per character

**Output:**
```python
@dataclass
class CharacterLens:
    character_tag: str
    scene_goal: str              # What they want THIS scene
    hidden_agenda: str           # What they're not saying
    flaw_challenge: str          # How this scene tests their flaw
    expected_tells: List[str]    # Which emotional tells should appear
    voice_shift: str             # How emotional state affects speech
    physical_focus: str          # Key physical behaviors this scene
```

**Integration Point:**
```
SceneOutline → CharacterLensAgent → CharacterLens[] → ProseAgent
```

---

### 1.5 Add Behavioral Consistency Validator

**Problem:** No validation that prose matches established character profiles.

**New Agent:** `BehaviorValidatorAgent`

**Runs:** After prose generation, before quality assurance.

**Checks:**
| Check | Description |
|-------|-------------|
| Dialogue Match | Does speech match `voice_signature`? |
| Show Don't Tell | Are emotions shown via `emotional_tells` or just stated? |
| Decision Consistency | Do choices align with `decision_heuristics`? |
| Physical Distinction | Is physicality unique per character? |
| Forbidden Words | Any `forbidden_words` used in dialogue? |

**Output:**
```python
@dataclass
class BehaviorViolation:
    character_tag: str
    violation_type: str
    location: str                # Line or paragraph reference
    expected: str                # What profile says
    actual: str                  # What prose contains
    suggested_fix: str           # Rewrite suggestion
```

---

## Part 2: Relationship & Arc Tracking

### 2.1 Relationship Dynamics Layer

**Problem:** Relationships stored as tags only, not dynamics.

**New Dataclass:**
```python
@dataclass
class RelationshipDynamic:
    characters: Tuple[str, str]           # (CHAR_A, CHAR_B)
    power_balance: str                    # Who holds what type of power
    tension_source: str                   # Core conflict or attraction
    communication_style: str              # How they interact verbally
    physical_proximity_rules: str         # Touch, distance, charged moments
    subtext_pattern: str                  # What's unsaid between them
    evolution_arc: str                    # How relationship changes over story
    current_stage: str                    # Where they are now in that arc
```

**Changes:**

| File | Change |
|------|--------|
| `world_bible_pipeline.py` | Add relationship research phase after character research |
| `WorldBibleOutput` | Add `relationships: List[RelationshipDynamic]` |
| `context_compiler.py` | Add `get_relationship_context()` for scene pairs |

**Research Process:**
- After all characters researched, identify all character pairs
- For pairs with meaningful interaction potential, generate `RelationshipDynamic`
- Store in world config for scene-level retrieval

---

### 2.2 Character Arc Progress Tracker

**Problem:** Only current emotional state tracked, not arc progression.

**New Class:** `CharacterArcTracker`

```python
@dataclass
class ArcMilestone:
    scene_number: int
    description: str
    arc_progress: float          # 0.0 to 1.0

@dataclass
class CharacterArcTracker:
    character_tag: str
    arc_type: str                # positive, negative, flat
    starting_belief: str         # The lie they believe
    target_truth: str            # What they must accept
    flaw: str                    # What holds them back

    milestones: List[ArcMilestone]
    current_progress: float
    last_milestone_hit: Optional[int]

    def update_progress(self, scene_number: int, milestone_hit: bool) -> None:
        ...

    def get_expected_state(self, story_position: float) -> str:
        ...
```

**Integration:**
- Initialize from `CharacterProfile.arc` during story pipeline setup
- Update after each scene based on content analysis
- Provide expected arc state to `CharacterLensAgent`

---

## Part 3: Pre-World Bible Enhancements

### 3.1 Pitch Enrichment Agent

**Problem:** Raw pitches may be ambiguous; downstream agents make inconsistent assumptions.

**New Agent:** `PitchEnrichmentAgent`

**Runs:** Before WorldBiblePipeline

**Input:** Raw pitch text

**Output:**
```python
@dataclass
class EnrichedPitch:
    original_pitch: str
    identified_characters: List[str]      # Names/roles found
    implied_characters: List[str]         # Roles needed but not named
    setting_details: Dict[str, str]       # Time, place, culture
    genre_markers: List[str]              # Detected genre elements
    ambiguities: List[str]                # Questions needing resolution
    expanded_pitch: str                   # Enriched version
```

**Pipeline Change:**
```
Pitch → PitchEnrichmentAgent → EnrichedPitch → WorldBiblePipeline
```

---

### 3.2 Genre Calibration Agent

**Problem:** Research agents don't calibrate to genre expectations.

**New Agent:** `GenreCalibrationAgent`

**Runs:** After pitch enrichment, before character research

**Output:**
```python
@dataclass
class GenreProfile:
    primary_genre: str
    subgenres: List[str]
    tone_markers: List[str]              # "restrained emotion", "dark humor"
    visual_palette: List[str]            # Color/lighting expectations
    pacing_expectations: str             # "slow burn", "rapid escalation"
    dialogue_conventions: str            # Period-appropriate speech notes
    character_archetypes: List[str]      # Common roles in this genre
    taboos: List[str]                    # What to avoid for genre
```

**Usage:** GenreProfile passed to all research agents as context calibration.

---

### 3.3 Cross-Tag Relationship Graph Validation

**Problem:** Continuity validation happens late; orphaned tags slip through.

**New Agent:** `RelationshipGraphValidator`

**Runs:** After WorldBiblePipeline assembly, before StoryPipeline

**Builds:**
```python
RelationshipGraph:
    nodes: All tags (characters, locations, props)
    edges:
        - CHAR → knows → CHAR
        - CHAR → owns → PROP
        - CHAR → frequents → LOC
        - LOC → contains → PROP
        - LOC → adjacent_to → LOC
```

**Validates:**
- No orphaned tags (characters no one knows, locations no one visits)
- Bidirectional relationships are consistent
- Location accessibility makes sense
- Props are placed in reachable locations

---

## Part 4: Context Management

### 4.1 Hierarchical Context Injection

**Problem:** Loading full prior script will hit context limits at scale.

**New System:** Tiered context based on recency.

```python
@dataclass
class HierarchicalContext:
    immediate: str       # Last 2 scenes - full text
    recent: str          # Scenes 3-6 - summaries (50 words each)
    distant: str         # Earlier scenes - key beats only (20 words each)
    persistent: str      # World config extracts (always included)

    def compile(self, current_scene: int) -> str:
        ...
```

**Changes:**

| File | Change |
|------|--------|
| `story_pipeline.py` | Replace full script loading with `HierarchicalContext` |
| New file | `hierarchical_context.py` - context management system |

**Scene Summary Agent:**
After each scene, generate a 50-word summary for the "recent" tier.

---

### 4.2 Research Depth Triage

**Problem:** All tags get same research depth regardless of importance.

**New Agent:** `ImportanceScoringAgent`

**Runs:** After tag extraction, before research

**Output:**
```python
TagImportance:
    primary: List[str]      # Full research (5 agents + 3 judges)
    secondary: List[str]    # Medium research (3 agents + 2 judges)
    background: List[str]   # Quick pass (1 agent)
```

**Scoring Criteria:**
- Scene count appearances
- Relationship to protagonist
- Plot point involvement
- Named vs unnamed

---

## Part 5: Quality Assurance Enhancements

### 5.1 Visual Consistency Validator

**Problem:** Visual descriptions may conflict (costume vs period, palette clashes).

**New Agent:** `VisualConsistencyValidator`

**Runs:** After all visual descriptions generated

**Checks:**
- Costume materials appropriate to time period
- Color palette consistency across locations
- Prop materials match location aesthetics
- Character costumes appropriate to their status/role

---

### 5.2 QA Feedback Loop to World Bible

**Problem:** QA catches issues but fixes only happen at script level.

**New System:** Bidirectional feedback

```
QA Findings → WorldBibleUpdateAgent → Updated world_config.json
```

**When QA finds:**
- Character motivation inconsistency → Update CharacterProfile
- Location description conflict → Update LocationProfile
- Relationship contradiction → Update RelationshipDynamic

This prevents future scenes from repeating the same errors.

---

## Implementation Priority

### Phase 1: Quick Wins (High Impact, Low Effort)
1. Increase character card limit to 180 words
2. Pass emotional tells to prose agents
3. Add voice signatures to character research

### Phase 2: Character Depth (High Impact, Medium Effort)
4. Implement CharacterLensAgent
5. Add BehaviorValidatorAgent
6. Create RelationshipDynamic layer

### Phase 3: Pipeline Enhancements (Medium Impact, Medium Effort)
7. Add PitchEnrichmentAgent
8. Add GenreCalibrationAgent
9. Implement RelationshipGraphValidator

### Phase 4: Scale & Optimization (High Impact, High Effort)
10. Implement HierarchicalContext system
11. Add Research Depth Triage
12. Build QA Feedback Loop

---

## File Changes Summary

| File | Changes |
|------|---------|
| `context_compiler.py` | Increase limits, restructure cards, add voice/tells |
| `agent_context_delivery.py` | Add emotional tells, relationship context methods |
| `world_bible_pipeline.py` | Add VoiceSignature, RelationshipDynamic, new research phases |
| `story_pipeline.py` | Integrate CharacterLens, HierarchicalContext |
| `thread_tracker.py` | Enhance with CharacterArcTracker |
| **New:** `character_lens_agent.py` | Scene-specific character guidance |
| **New:** `behavior_validator_agent.py` | Post-prose character consistency |
| **New:** `pitch_enrichment_agent.py` | Pre-pipeline pitch expansion |
| **New:** `genre_calibration_agent.py` | Genre profile generation |
| **New:** `relationship_graph_validator.py` | Cross-tag validation |
| **New:** `hierarchical_context.py` | Tiered context management |
| **New:** `visual_consistency_validator.py` | Visual description validation |

---

## Success Metrics

After implementation, characters should:
- Have distinct, recognizable voices in dialogue
- Express emotions through physical tells, not statements
- Make decisions consistent with established heuristics
- Move and gesture in character-specific ways
- Progress through meaningful arcs with visible milestones
- Have dynamic, evolving relationships with other characters

---

## Appendix: Example Before/After

### Before (Current System)

**Prose Agent Receives:**
```
[CHAR_MEI] Mei - prized courtesan seeking freedom.
Wants: freedom. Needs: self-worth.
```

**Generated Prose:**
```
Mei felt afraid. "I don't know if I can do this," she said nervously.
```

### After (Expanded System)

**Prose Agent Receives:**
```
[CHAR_MEI] Mei Ling - Courtesan, 26
CORE: Strategic thinker masking vulnerability beneath composed exterior
VOICE: Poetic, indirect, uses metaphor and game references. Never direct statements.
PHYSICALITY: Graceful, deliberate movements. Perfect posture. Hands always purposeful.
WANT: Freedom from the pleasure house and autonomy over her fate
NEED: Recognize her inherent worth beyond beauty and usefulness
FLAW: Cannot accept help; must control every outcome

EMOTIONAL TELLS (this scene):
FEAR: Eyes widen briefly, then narrow with calculated focus. Hands still completely.
VULNERABILITY: Eyes soften, shoulders drop slightly, voice becomes whisper-soft.

VOICE SAMPLES:
- "The stone placed here speaks of patience. Do you hear it?"
- "One does not capture the wind. One becomes the space it fills."

RELATIONSHIP WITH CHAR_GENERAL:
Power: He holds institutional power; she holds psychological power
Tension: Mutual attraction neither can acknowledge
Style: Formal words, loaded subtext
Physical: Never touch directly; charged near-misses
```

**Generated Prose:**
```
Mei's eyes widened for just a moment before narrowing, her gaze
sharpening like a blade finding its edge. Her hands, which had been
arranging the go stones in an idle pattern, went perfectly still.

"The board reveals much about its players," she said, her voice
carrying the measured calm of a temple bell. "One wonders what
moves remain... when the corner has already been lost."
```

---

*Document Version: 1.0*
*Created: 2024*
*Status: Planning*
