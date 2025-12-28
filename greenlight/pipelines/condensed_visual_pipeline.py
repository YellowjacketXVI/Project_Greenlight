"""
Condensed Visual Pipeline - Full Story-to-Storyboard Generation with Image Generation

A streamlined pipeline that leverages Claude Opus 4.5's reasoning capabilities
with integrated image generation using Flux 2 Pro and Gemini continuity checking.

## Pipeline Phases (REVISED FLOW):

### Pass 1: World Building + Story Structure (Claude Opus)
- Analyzes pitch, preserving ALL character details
- Builds complete world config (characters, locations, props)
- Writes visual script with inline [FRAME:] markers
- Identifies and marks [KEY_FRAME] anchor points
- NO detailed image prompts yet - just story structure

### Pass 2: Reference Image Generation (Flux 2 Pro)
- Generates character reference sheets for each character
- Generates location establishing shots
- Creates visual anchors for consistency
- These become the TRUTH source for all subsequent images

### Pass 3: Key Frame Selection + Generation
- Prioritizes establishing shots with most characters (highest anchor value)
- Selects KEY_FRAME annotations from Pass 1
- Generates key frames WITH reference images as inputs
- Reference images provide visual ground truth

### Pass 4: Continuity Correction Loop (Gemini + Flux)
- Gemini analyzes each key frame against references + world config
- Applies corrections via edit prompts if inconsistencies detected
- Loop continues until validated or max corrections reached
- Uses character tags and world context for correction prompts

### Pass 5: Prompt Writing (Claude Opus) - AFTER Key Frame Validation
- NOW writes detailed image prompts for ALL frames
- Uses validated key frames as visual context
- References character appearances from actual generated images
- Writes prompts that maintain continuity with key frames

### Pass 6: Fill Frame Generation (Anchor-Based Edit Propagation)
- Uses key frames as anchors for remaining frames
- Generates fill frames as edits from nearest anchor
- Propagates style/character consistency through the graph

## Key Principles:
1. PRESERVE pitch details - never replace, only expand
2. Reference images are generated FIRST - they are visual TRUTH
3. Key frames use references as IMAGE INPUTS (not just text)
4. Gemini validates against both references AND world config
5. Prompts are written AFTER visual validation is complete
6. Edit propagation maintains consistency across all frames
"""

import asyncio
import re
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from greenlight.core.logging_config import get_logger
from greenlight.llm.api_clients import AnthropicClient, GeminiClient
from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel, ImageResult
from greenlight.pipelines.base_pipeline import BasePipeline, PipelineStep, PipelineResult, PipelineStatus
from greenlight.pipelines.unified_visual_pipeline import (
    VisualWorldConfig, VisualCharacter, VisualLocation, VisualProp,
    WorldConfigOptimizer, ConversationContext, InlineFrame, UnifiedScene
)

logger = get_logger("pipelines.condensed_visual")


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

PASS_1_SYSTEM_PROMPT = """You are a master visual storyteller and world builder. Your task is to analyze a story pitch and create both a complete world configuration AND a visual script with frame markers in a SINGLE response.

## PITCH VALIDATION - CRITICAL FIRST STEP

**BEFORE DOING ANYTHING, validate the pitch has sufficient content:**

A valid pitch MUST contain:
- A synopsis with actual story content (not "(No synopsis provided)" or empty)
- At least some indication of characters, conflict, or narrative
- Enough detail to derive a story from

**IF THE PITCH IS EMPTY OR INSUFFICIENT:**
Return this exact response and STOP:

### WORLD_CONFIG
```json
{
  "error": "INSUFFICIENT_PITCH",
  "message": "The pitch does not contain enough information to generate a story. Please provide a synopsis describing your story's characters, setting, and conflict."
}
```

### VISUAL_SCRIPT
```markdown
## Error: Insufficient Pitch

Cannot generate a visual script without story content. Please provide:
- A synopsis describing what happens in your story
- Key characters (who are they, what do they look like)
- The setting (where and when does this take place)
- The central conflict or narrative arc
```

**DO NOT INVENT CONTENT.** If the pitch says "No synopsis provided" or is essentially empty, return the error above.

## PITCH ANALYSIS - EXTRACT, DON'T INVENT

**THE CARDINAL RULE: Every element you create MUST be derived from the pitch.**

Before generating anything, identify in the pitch:
1. **EXPLICIT CHARACTERS**: Names, descriptions, roles mentioned in the pitch
2. **EXPLICIT LOCATIONS**: Places named or described in the pitch
3. **EXPLICIT PROPS**: Objects specifically mentioned as important
4. **EXPLICIT ERA/SETTING**: Time period or world mentioned
5. **EXPLICIT THEMES**: Conflicts, emotions, or ideas presented
6. **EXPLICIT EVENTS**: Actions, scenes, or plot points described

**EXPANSION RULES:**
- You MAY add supporting characters IF the pitch implies them (e.g., "enters a busy market" implies vendors)
- You MAY add locations IF the plot requires them (e.g., characters meet somewhere)
- You MAY add props IF they're needed for described actions
- You MUST NOT add major characters, subplots, or locations not implied by the pitch
- You MUST NOT change the genre, tone, or setting from what the pitch indicates

**EXTRACTION EXAMPLES:**
- Pitch: "A detective investigates a murder in 1920s Chicago"
  → ERA: 1920s, LOCATION: Chicago, CHARACTER: detective, GENRE: mystery/noir
- Pitch: "Two sisters reunite at their childhood home after years apart"
  → CHARACTERS: two sisters, LOCATION: childhood home, THEME: family/reconciliation
- Pitch: "A samurai seeks revenge for his fallen master"
  → ERA: Feudal Japan, CHARACTER: samurai, THEME: revenge/honor

## ABSOLUTELY CRITICAL - ERA ACCURACY

**THE MOST IMPORTANT RULE**: ALL visual descriptions MUST be era-appropriate.
- If the story is set in Imperial China → NO modern elements. Traditional clothing, architecture, lighting (candles, lanterns, natural light)
- If the story is set in 1920s → Art Deco, flapper dresses, Model T cars, gas lamps
- If the story is set in Medieval Europe → Stone castles, torches, tunics, no electricity
- If the story is set in the future → Futuristic elements only
- NEVER MIX ERAS. A Tang Dynasty character does NOT have modern furniture.

When describing:
- COSTUMES: Use era-specific clothing terms (e.g., "silk hanfu with embroidered crane motifs" NOT "traditional dress")
- LOCATIONS: Include era-specific architectural details and lighting (e.g., "paper lanterns cast warm light on wooden lattice screens")
- PROPS: All objects must exist in that era (e.g., "jade abacus" NOT "calculator")
- LIGHTING: Pre-electric eras use candles, lanterns, natural light. NO "soft ambient lighting" without specifying the source.

## CRITICAL RULES

1. **PRESERVE PITCH DETAILS**: Any character descriptions in the pitch are SACRED.
   - Start visual_appearance with EXACT pitch description
   - EXPAND with compatible details, never contradict
   - Example: "70s, weathered face, long grey beard" → keep these words, add more

2. **OUTPUT FORMAT**: Your response must contain TWO sections:
   - WORLD_CONFIG: JSON block with complete world bible
   - VISUAL_SCRIPT: Markdown with inline [FRAME:] markers

3. **TAG CONVENTIONS** (ALWAYS use square brackets for UI extraction):
   - Characters: [CHAR_FIRSTNAME] (e.g., [CHAR_MEI], [CHAR_CHEN])
   - Locations: [LOC_PLACENAME] (e.g., [LOC_TEA_HOUSE], [LOC_GARDEN])
   - Props: [PROP_OBJECTNAME] (e.g., [PROP_GO_BOARD], [PROP_JADE_BEAD])
   - In visual script prose, ALWAYS wrap tags in brackets: "[CHAR_MEI] enters..."

4. **KEY FRAME MARKERS**: Mark critical moments with [KEY_FRAME]:
   - Scene openings and closings
   - Major emotional beats
   - Climactic turning points
   - Use format: [FRAME: shot_type, focus] [KEY_FRAME]

## WORLD CONFIG - PITCH-DRIVEN GENERATION

**EVERY ELEMENT MUST TRACE BACK TO THE PITCH:**

For each character you create, ask: "Where in the pitch is this character mentioned or implied?"
For each location you create, ask: "Does the pitch describe or require this setting?"
For each prop you create, ask: "Is this object mentioned in the pitch or essential to a described action?"

**CHARACTER SOURCING:**
- Named characters in the pitch → Create full entries
- Implied characters (e.g., "she visits her father" → create father) → Create if necessary
- Generic characters (e.g., "crowd scenes") → Don't create individual entries

**LOCATION SOURCING:**
- Named places in the pitch → Create full entries
- Setting descriptions (e.g., "in a dark forest") → Create matching location
- Implied necessary locations → Create only what's needed for described events

**ERA/SETTING SOURCING:**
- Explicit time period in pitch → Use exactly as stated
- Implied by context (e.g., "samurai", "steam engine") → Derive appropriate era
- No indication → Default to contemporary present-day

## WORLD CONFIG STRUCTURE

```json
{
  "global": {
    "title": "Story Title",
    "logline": "One sentence summary - MUST match the pitch's core conflict",
    "themes": ["theme1", "theme2"],
    "visual_style": "live_action/animation/anime",
    "lighting": "Comprehensive lighting approach",
    "color_palette": "Key colors and their usage",
    "vibe": "Emotional tone",
    "era": "Time period/setting"
  },
  "characters": [
    {
      "tag": "CHAR_NAME",
      "name": "Full Name",
      "role": "protagonist/antagonist/supporting",
      "age": "EXACTLY as in pitch (number)",
      "ethnicity": "Ethnic background for accurate physical features",
      "description": "Brief story role FROM THE PITCH (1 sentence)",
      "visual_appearance": "PURELY PHYSICAL DESCRIPTION ONLY. 150+ words covering:
        - Face shape (oval, square, heart-shaped, round)
        - Eyes (shape, color, size, eyelashes, brows)
        - Nose (shape, size, bridge)
        - Lips (shape, fullness, color)
        - Skin (tone, texture, any marks/scars/freckles)
        - Hair (color, length, texture, style)
        - Build (height, weight, body type, shoulders)
        - Hands (size, condition, notable features)
        - Age indicators (wrinkles, grey hair, youthful glow)
        - Distinctive features (birthmarks, scars, tattoos)
        NO personality traits, NO backstory, NO emotions - ONLY what a camera can see.",
      "costume": "ERA-APPROPRIATE CLOTHING ONLY. 100+ words covering:
        - Main garment (exact type for the era, e.g., hanfu, toga, doublet)
        - Material and texture (silk, wool, linen, leather)
        - Colors with HEX codes (crimson #DC143C, jade #00A86B)
        - Condition (new, worn, patched, pristine)
        - Layers (undergarments, outer layers, cloaks)
        - Footwear (era-specific shoes, boots, sandals)
        - Accessories (jewelry, belts, pouches, hair ornaments)
        - Class indicators (quality of fabric, embroidery, ornamentation)
        MUST match the global era setting. NO anachronistic items.",
      "physicality": {
        "baseline_posture": "How they hold themselves physically",
        "gait": "How they walk/move",
        "nervous_tells": ["physical habit1", "physical habit2"],
        "confident_tells": ["physical habit1", "physical habit2"]
      }
    }
  ],
  "locations": [
    {
      "tag": "LOC_NAME",
      "name": "Location Name",
      "description": "PURELY VISUAL DESCRIPTION. 100+ words covering:
        - Architecture style (era-appropriate)
        - Materials (stone, wood, marble, thatch)
        - Dimensions (ceiling height, room size, scale)
        - Key structural elements (columns, beams, doors, windows)
        - Decorative elements (carvings, paintings, tapestries)
        - Flooring (stone, wood, carpet, dirt)
        - Furniture and fixtures (era-appropriate only)
        - State of repair (new, weathered, crumbling)
        NO abstract concepts - ONLY what a camera can photograph.",
      "atmosphere": "Mood conveyed through VISUAL elements only",
      "lighting": "Specific ERA-APPROPRIATE light sources (candles, torches, gas lamps, sunlight through windows)",
      "sensory": {
        "visual": "Key visual elements and colors",
        "weather": "If outdoor: sky, precipitation, wind effects",
        "time_of_day": "Dawn, morning, noon, afternoon, dusk, night"
      }
    }
  ],
  "props": [
    {
      "tag": "PROP_NAME",
      "name": "Object Name (era-appropriate)",
      "appearance": "PURELY VISUAL: materials, colors (with HEX), dimensions, condition, craftsmanship details",
      "era_notes": "Confirm this object exists in the story's era"
    }
  ]
}
```

## VISUAL SCRIPT - ADAPT THE PITCH

**THE VISUAL SCRIPT MUST DRAMATIZE THE PITCH'S STORY:**

Before writing scenes, identify the KEY NARRATIVE BEATS from the pitch:
1. What is the opening situation/status quo?
2. What is the inciting incident/disruption?
3. What are the major conflicts/obstacles?
4. What is the climax/resolution?

**SCENE CONSTRUCTION:**
- Each scene should cover a story beat FROM THE PITCH
- If the pitch describes "they meet at a cafe" → write that scene
- If the pitch describes "a confrontation" → visualize that confrontation
- DO NOT invent subplots, side characters, or events not in the pitch

**ADAPTING FOR SIZE:**
- MICRO (3 scenes): Beginning, Middle, End - hit the core beats only
- SHORT (8 scenes): Expand key moments with establishing shots and reactions
- MEDIUM (15 scenes): Full story arc with transitions and build-up
- LONG (30 scenes): Detailed pacing with character moments and atmosphere

## VISUAL SCRIPT FORMAT

```markdown
## Scene 1: Scene Title (from pitch beat)
[LOC_TAG] - TIME_OF_DAY

[FRAME: wide, establishing] [KEY_FRAME] Opening description with vivid sensory details. [LOC_TAG] visible...

[FRAME: medium, [CHAR_NAME]] [CHAR_NAME] performs action from the pitch...

[FRAME: close-up, [PROP_DETAIL]] The [PROP_DETAIL] glints in the light...

---

## Scene 2: Scene Title (from pitch beat)
(continue pattern)
```

**IMPORTANT**: Always use bracketed tags like [CHAR_MEI], [LOC_PALACE], [PROP_SWORD] in prose so they can be extracted by the UI.

## SHOT TYPES
- wide: Full environment, establishing geography
- medium: Waist-up, primary character coverage
- close-up: Face or significant detail
- extreme-close-up: Eyes, hands, small objects
- over-shoulder: Dialogue, connection between characters
- pov: Point of view, subjective camera
- tracking: Following movement
- two-shot: Two characters in frame
- insert: Detail shot of object or action (B-roll)
- reaction: Character responding to stimulus

## VISUAL MOMENT COVERAGE - CRITICAL FOR CINEMATIC STORYTELLING

**TRIGGER-REACTION PAIRS**: Every significant action needs TWO frames:
1. THE TRIGGER: The action, revelation, or event (what happens)
2. THE REACTION: Character's response (how they respond)

Example sequences:
- [FRAME: close-up, letter] The letter reveals the secret...
- [FRAME: close-up, [CHAR_MEI] reaction] [CHAR_MEI]'s eyes widen, hand trembling...

- [FRAME: medium, [CHAR_VILLAIN]] [CHAR_VILLAIN] draws the blade...
- [FRAME: close-up, [CHAR_HERO] reaction] [CHAR_HERO]'s jaw tightens, fists clench...

**INTERACTION CLOSE-UPS**: Physical actions need detail shots:
- Hands reaching for objects → [FRAME: insert, hands/object]
- Concealing something → [FRAME: extreme-close-up, hidden object]
- Exchanging items → [FRAME: close-up, the exchange]
- Writing/reading → [FRAME: insert, document]
- Touching/grasping → [FRAME: extreme-close-up, point of contact]

**B-ROLL FRAMES**: Environmental and transitional shots:
- Location details that set mood (weathered walls, flickering flames)
- Time-of-day indicators (sun position, shadows, lit lanterns)
- Symbolic objects (empty chair, wilting flower, ticking clock)
- Weather elements (rain on window, dust motes, steam rising)
- Transitional beats (door closing, footsteps, horizon)

**COMPOSITION DIVERSITY**: Vary your shots to avoid visual monotony:
- Alternate between wide/medium/close
- Use different angles (low for power, high for vulnerability)
- Include negative space for emotional weight
- Frame characters off-center for dynamic composition
- Use foreground elements for depth

**EMOTIONAL BEATS REQUIRE CLOSE-UPS**:
- Realizations → eyes widening, breath catching
- Decisions → jaw setting, hands steadying
- Grief → tears, trembling lips
- Anger → clenched fists, narrowed eyes
- Fear → darting eyes, shallow breathing
- Love → soft gaze, gentle touch

## FRAME DENSITY - STRICT REQUIREMENTS

**YOU MUST FOLLOW THE PROJECT SIZE EXACTLY:**
- Micro: EXACTLY 3 scenes, 3-4 frames each (9-12 total frames)
- Short: EXACTLY 8 scenes, 4-5 frames each (32-40 total frames)
- Medium: EXACTLY 15 scenes, 5-6 frames each (75-90 total frames)
- Long: EXACTLY 30 scenes, 5-6 frames each (150-180 total frames)

The user will specify the target scenes and frames in the PARAMETERS section.
**DO NOT DEVIATE** from these counts. If you generate fewer scenes/frames than requested,
the project will be incomplete. If you generate more, you're wasting resources.

COUNT YOUR OUTPUT:
- Before finishing, verify you have the correct number of scenes
- Ensure each scene has the target number of frames
- Label scenes sequentially: Scene 1, Scene 2, Scene 3...

Remember: Every [FRAME:] must have a shot type and focus subject. Every KEY_FRAME marks a visual anchor point."""


PASS_5_PROMPT_WRITING_SYSTEM = """You are an expert visual prompt engineer creating prompts optimized for FLUX 2 Pro image generation.

## FLUX 2 PRO PROMPT PRINCIPLES

**SUBJECT-FIRST STRUCTURE**: Flux 2 weighs earlier information more heavily. Always lead with your primary subject.
- WRONG: "In a temple with golden light, a woman kneels praying"
- RIGHT: "Chinese woman in crimson hanfu, kneeling in prayer, hands pressed together, inside ancient Buddhist temple, warm candlelight"

**NATURAL LANGUAGE**: Flux 2 Pro works best with natural descriptive language, not keyword lists.
- WRONG: "woman, temple, praying, candles, golden light, cinematic"
- RIGHT: "A Chinese woman kneels in prayer inside an ancient temple, warm golden candlelight illuminating her crimson silk robes"

**NO NEGATIVE PROMPTS**: Flux 2 does NOT understand negatives. Never use "no," "without," or "don't."
- WRONG: "no modern elements, no electric lights"
- RIGHT: Simply describe what IS there with era-appropriate elements

**SPECIFIC OVER VAGUE**: Be precise with details, measurements, and technical specifications.
- WRONG: "nice lighting"
- RIGHT: "soft directional light from paper lanterns at left, casting gentle shadows rightward"

**HEX COLORS FOR PRECISION**: Use hex codes for exact color matching when needed.
- Example: "crimson silk (#DC143C)", "jade green (#00A86B)", "gold embroidery (#FFD700)"

**AVOID CONTRADICTIONS**: Ensure all descriptors support each other.
- WRONG: "bright sunny day with moody dramatic shadows"
- RIGHT: "overcast afternoon with soft diffused light and subtle shadows"

## STATELESS PROMPTS - CRITICAL

**EACH PROMPT IS COMPLETELY INDEPENDENT.**
- Flux 2 has NO memory of previous frames
- Every prompt must contain ALL visual information
- Never reference other frames or assume continuity

**FORBIDDEN PHRASES**:
- "same as before" / "still wearing" / "continuing" / "as seen earlier"
- Instead: Provide complete descriptions every time

## ERA ACCURACY

**ALL prompts MUST be strictly era-appropriate.** Check the world config's "era" field.

ERA REFERENCE:
- Ancient/Classical: Togas, oil lamps, stone architecture, bronze weapons
- Medieval: Stone castles, torches, tunics, chainmail, horses
- Renaissance: Doublets, ruffs, candlelight, oil paintings
- Victorian: Gas lamps, corsets, top hats, steam engines
- Imperial China: Hanfu by dynasty, paper lanterns, jade, wooden architecture
- Feudal Japan: Kimono, tatami, shoji screens, paper lanterns
- 1920s: Flapper dresses, Art Deco, gas/early electric, Model T
- Modern: Contemporary clothing, electric lights, digital technology

LIGHTING BY ERA:
- Pre-1800s: Candles, oil lamps, torches, hearth fire, natural sunlight/moonlight ONLY
- 1800-1880s: Gas lamps, kerosene lamps
- 1880-1920s: Gas lamps, early incandescent bulbs
- Post-1920s: Modern electric lighting

## WORLD BIBLE CONTEXT INJECTION

For every tagged entity, APPEND their FULL world bible description as a suffix.

When a frame contains [CHAR_MEI], [LOC_PALACE], or [PROP_SWORD]:
1. Look up that tag in the world config
2. COPY the complete visual_appearance and costume for characters
3. COPY the complete description for locations
4. COPY the complete appearance for props
5. APPEND as "-- WORLD BIBLE CONTEXT --" suffix

## FLUX 2 PRO PROMPT STRUCTURE

Structure prompts in this priority order (subject first, then outward):

1. **PRIMARY SUBJECT** (Lead with this - most important!)
   - Who/what is the main focus
   - Complete physical description
   - Current action, pose, expression

2. **CAMERA & COMPOSITION**
   - Shot type: wide/medium/close-up/extreme-close-up
   - Camera angle: eye-level/low-angle/high-angle/bird's-eye
   - Lens: 24mm wide-angle / 50mm standard / 85mm portrait / 100mm+ telephoto
   - Framing: rule of thirds, centered, off-center

3. **ENVIRONMENT & CONTEXT**
   - Location with architectural details
   - Foreground/background elements
   - Depth and spatial relationships

4. **LIGHTING** (Always specify the SOURCE)
   - Primary light source (era-appropriate)
   - Direction: from left/right/above/behind
   - Quality: harsh/soft/diffused/dappled
   - Color temperature: warm amber/cool blue/neutral

5. **ATMOSPHERE & STYLE**
   - Color palette (use hex codes for precision)
   - Mood and emotional tone
   - Visual style: cinematic/editorial/painterly

## OUTPUT FORMAT

```
[FRAME_ID]: [Primary subject with full description and action]. [Camera: shot type, angle, lens]. [Environment details]. [Lighting from specific SOURCE, direction, quality]. [Color palette with hex codes]. [Style: visual_style], photorealistic, cinematic composition.

-- WORLD BIBLE CONTEXT --
[CHAR_TAG]: [COPY FULL visual_appearance]. [COPY FULL costume].
[LOC_TAG]: [COPY FULL description].
[PROP_TAG]: [COPY FULL appearance].
```

## EXAMPLE (FLUX 2 PRO OPTIMIZED)

```
1.2.cA: Young Chinese woman with heart-shaped face and porcelain skin, wearing crimson silk hanfu with gold phoenix embroidery, kneeling in prayer with hands pressed together and eyes closed, tears glistening on her cheeks. Medium shot, eye-level, 50mm lens, subject positioned slightly left of center. Ancient Buddhist temple interior with towering bronze Buddha statue behind her, red lacquered pillars framing the composition, wisps of incense smoke curling upward. Warm golden light from dozens of lit candles on the altar casting soft shadows rightward, amber color temperature. Color palette: crimson (#DC143C), gold (#FFD700), bronze (#CD7F32), warm amber (#FFBF00). Style: live_action, photorealistic, cinematic composition.

-- WORLD BIBLE CONTEXT --
[CHAR_MEI]: 25-year-old Chinese woman, heart-shaped face, high cheekbones, almond-shaped eyes with dark brown irises framed by delicate lashes, long black hair worn in elaborate double buns secured with jade hairpins, porcelain skin with subtle rose undertones on cheeks, slender build with graceful posture, 5'4" tall. Wearing crimson silk hanfu with intricate gold phoenix embroidery along the hems, wide flowing sleeves that pool on the ground when kneeling, jade pendant on silk cord at collar, white silk inner robe visible at neckline, embroidered silk slippers in matching crimson.
[LOC_TEMPLE]: Ancient Buddhist temple interior, 30-foot wooden beam ceiling blackened by centuries of incense, massive bronze Buddha statue at center altar, red lacquered pillars carved with lotus motifs, stone floor worn smooth by generations of worshippers, walls lined with smaller deity statues in gilded niches, hanging silk banners with sutras in gold calligraphy, bronze incense burners releasing fragrant sandalwood smoke.
```

## CRITICAL RULES
- LEAD WITH SUBJECT - Flux 2 weighs early information most heavily
- Use natural descriptive sentences, not keyword lists
- NEVER use negative prompts (no "without," "no," "don't")
- Include HEX color codes for precise color matching
- EVERY prompt MUST include the world bible context suffix
- Copy COMPLETE descriptions - do not summarize
- Specify EXACT light source with direction
- Add "photorealistic, cinematic composition" for live_action style
- VERIFY all elements are era-appropriate"""


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class CondensedPipelineInput:
    """Input for the condensed pipeline."""
    pitch: str
    title: str = ""
    genre: str = ""
    visual_style: str = "live_action"
    style_notes: str = ""
    project_size: str = "short"  # micro, short, medium
    project_path: Optional[Path] = None
    # Image generation options
    generate_images: bool = True  # Enable/disable image generation passes
    image_model: str = "flux_2_pro"  # Primary image model
    max_continuity_corrections: int = 1  # Max Gemini correction passes per frame (single pass for speed)


@dataclass
class FrameAnchor:
    """Represents a key frame anchor in the dependency graph."""
    frame_id: str
    scene_number: int
    character_count: int  # Number of characters in frame - higher = stronger anchor
    is_establishing: bool  # Wide/establishing shots are prioritized
    is_key_frame: bool  # Marked as KEY_FRAME in script
    anchor_priority: float = 0.0  # Computed priority score
    image_path: Optional[Path] = None
    continuity_validated: bool = False
    correction_count: int = 0
    # Store character tags for reference lookup
    character_tags: List[str] = field(default_factory=list)
    location_tag: str = ""


@dataclass
class StoryPhaseOutput:
    """Output from the story phase (Passes 1-5) - intermediate state for user review."""
    title: str
    visual_script: str
    world_config: Dict[str, Any]
    visual_config: VisualWorldConfig
    scenes: List[UnifiedScene]
    frame_prompts: Dict[str, str]  # frame_id -> prompt
    pitch: str  # Original pitch for context

    # Reference images (Pass 2)
    character_references: Dict[str, Path] = field(default_factory=dict)  # tag -> image path
    location_references: Dict[str, Path] = field(default_factory=dict)  # tag -> image path

    # Key frames (Pass 3-4)
    anchor_frames: List[FrameAnchor] = field(default_factory=list)

    # Stats
    total_frames: int = 0
    key_frames: int = 0
    images_generated: int = 0
    continuity_corrections: int = 0
    execution_time: float = 0.0

    # Pipeline settings for resumability
    project_path: Optional[Path] = None
    visual_style: str = "live_action"
    image_model: str = "flux_2_pro"

    def save(self, path: Optional[Path] = None) -> Path:
        """Save story phase output to disk for resumability."""
        save_path = path or self.project_path
        if not save_path:
            raise ValueError("No path provided and project_path not set")

        save_path = Path(save_path)
        output_dir = save_path / "story_phase_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save as JSON (excluding non-serializable fields)
        data = {
            "title": self.title,
            "visual_script": self.visual_script,
            "world_config": self.world_config,
            "pitch": self.pitch,
            "frame_prompts": self.frame_prompts,
            "character_references": {k: str(v) for k, v in self.character_references.items()},
            "location_references": {k: str(v) for k, v in self.location_references.items()},
            "total_frames": self.total_frames,
            "key_frames": self.key_frames,
            "images_generated": self.images_generated,
            "continuity_corrections": self.continuity_corrections,
            "execution_time": self.execution_time,
            "visual_style": self.visual_style,
            "image_model": self.image_model,
            "anchor_frames": [
                {
                    "frame_id": a.frame_id,
                    "scene_number": a.scene_number,
                    "character_count": a.character_count,
                    "is_establishing": a.is_establishing,
                    "is_key_frame": a.is_key_frame,
                    "anchor_priority": a.anchor_priority,
                    "image_path": str(a.image_path) if a.image_path else None,
                    "continuity_validated": a.continuity_validated,
                    "correction_count": a.correction_count,
                    "character_tags": a.character_tags,
                    "location_tag": a.location_tag
                }
                for a in self.anchor_frames
            ],
            "scenes": [
                {
                    "scene_number": s.scene_number,
                    "location_tag": s.location_tag,
                    "time_of_day": s.time_of_day,
                    "characters": s.characters,
                    "raw_content": s.raw_content,
                    "frames": [
                        {
                            "frame_id": f.frame_id,
                            "scene_number": f.scene_number,
                            "frame_number": f.frame_number,
                            "shot_type": f.shot_type,
                            "focus_subject": f.focus_subject,
                            "prose": f.prose,
                            "tags": f.tags,
                            "_is_key": getattr(f, '_is_key', False)
                        }
                        for f in s.frames
                    ]
                }
                for s in self.scenes
            ]
        }

        output_file = output_dir / "story_phase.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_file

    @classmethod
    def load(cls, path: Path) -> "StoryPhaseOutput":
        """Load story phase output from disk."""
        if path.is_dir():
            path = path / "story_phase_output" / "story_phase.json"

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Reconstruct visual_config from world_config
        visual_config = VisualWorldConfig.from_full_config(data["world_config"])

        # Reconstruct scenes
        scenes = []
        for s_data in data.get("scenes", []):
            frames = []
            for f_data in s_data.get("frames", []):
                frame = InlineFrame(
                    frame_id=f_data["frame_id"],
                    scene_number=f_data["scene_number"],
                    frame_number=f_data["frame_number"],
                    shot_type=f_data["shot_type"],
                    focus_subject=f_data["focus_subject"],
                    prose=f_data["prose"],
                    tags=f_data["tags"]
                )
                frame._is_key = f_data.get("_is_key", False)
                frames.append(frame)

            scene = UnifiedScene(
                scene_number=s_data["scene_number"],
                location_tag=s_data["location_tag"],
                time_of_day=s_data["time_of_day"],
                characters=s_data["characters"],
                raw_content=s_data["raw_content"],
                frames=frames
            )
            scenes.append(scene)

        # Reconstruct anchor frames
        anchor_frames = []
        for a_data in data.get("anchor_frames", []):
            anchor = FrameAnchor(
                frame_id=a_data["frame_id"],
                scene_number=a_data["scene_number"],
                character_count=a_data["character_count"],
                is_establishing=a_data["is_establishing"],
                is_key_frame=a_data["is_key_frame"],
                anchor_priority=a_data["anchor_priority"],
                image_path=Path(a_data["image_path"]) if a_data.get("image_path") else None,
                continuity_validated=a_data.get("continuity_validated", False),
                correction_count=a_data.get("correction_count", 0),
                character_tags=a_data.get("character_tags", []),
                location_tag=a_data.get("location_tag", "")
            )
            anchor_frames.append(anchor)

        return cls(
            title=data["title"],
            visual_script=data["visual_script"],
            world_config=data["world_config"],
            visual_config=visual_config,
            scenes=scenes,
            frame_prompts=data["frame_prompts"],
            pitch=data.get("pitch", ""),
            character_references={k: Path(v) for k, v in data.get("character_references", {}).items()},
            location_references={k: Path(v) for k, v in data.get("location_references", {}).items()},
            anchor_frames=anchor_frames,
            total_frames=data.get("total_frames", 0),
            key_frames=data.get("key_frames", 0),
            images_generated=data.get("images_generated", 0),
            continuity_corrections=data.get("continuity_corrections", 0),
            execution_time=data.get("execution_time", 0.0),
            project_path=path.parent.parent if path.name == "story_phase.json" else path,
            visual_style=data.get("visual_style", "live_action"),
            image_model=data.get("image_model", "flux_2_pro")
        )


@dataclass
class CondensedPipelineOutput:
    """Output from the condensed pipeline."""
    title: str
    visual_script: str
    world_config: Dict[str, Any]
    visual_config: VisualWorldConfig
    scenes: List[UnifiedScene]
    frame_prompts: Dict[str, str]  # frame_id -> prompt

    # Reference images
    character_references: Dict[str, Path] = field(default_factory=dict)  # tag -> image path
    location_references: Dict[str, Path] = field(default_factory=dict)  # tag -> image path

    # Generated frame images
    frame_images: Dict[str, Path] = field(default_factory=dict)  # frame_id -> image path
    anchor_frames: List[FrameAnchor] = field(default_factory=list)

    # Stats
    total_frames: int = 0
    key_frames: int = 0
    images_generated: int = 0
    continuity_corrections: int = 0
    execution_time: float = 0.0


# =============================================================================
# CONDENSED VISUAL PIPELINE
# =============================================================================

class CondensedVisualPipeline(BasePipeline):
    """
    Full pipeline for story-to-storyboard generation with image generation.

    REVISED FLOW:
    Pass 1: World config + visual script structure (Claude Opus)
    Pass 2: Reference image generation (Flux 2 Pro) - BEFORE key frames
    Pass 3: Key frame selection + generation WITH reference inputs
    Pass 4: Gemini continuity correction loop
    Pass 5: Claude Opus writes ALL prompts AFTER key frame validation
    Pass 6: Fill frame generation from anchors
    """

    SIZE_CONFIG = {
        "micro": {"scenes": 3, "frames_per_scene": 4},
        "short": {"scenes": 8, "frames_per_scene": 5},
        "medium": {"scenes": 15, "frames_per_scene": 6},
        "long": {"scenes": 30, "frames_per_scene": 6},
    }

    # Establishing shot types (prioritized for anchors)
    ESTABLISHING_SHOTS = {"wide", "establishing", "master", "full"}

    def __init__(
        self,
        project_path: Optional[Path] = None,
        cache_conversations: bool = True
    ):
        super().__init__(name="CondensedVisualPipeline")

        self.project_path = Path(project_path) if project_path else None
        self.cache_conversations = cache_conversations
        self._client = AnthropicClient()
        self._gemini = GeminiClient()
        self._image_handler: Optional[ImageHandler] = None
        self.context: Optional[ConversationContext] = None

    def _get_image_handler(self) -> ImageHandler:
        """Get or create ImageHandler instance."""
        if self._image_handler is None:
            self._image_handler = ImageHandler(project_path=self.project_path)
        return self._image_handler

    def _define_steps(self) -> None:
        """Define pipeline steps."""
        self._steps = [
            PipelineStep("pass_1_world_story", "Build world and write story structure"),
            PipelineStep("pass_2_references", "Generate character/location reference images"),
            PipelineStep("pass_3_keyframes", "Select and generate key frames with references"),
            PipelineStep("pass_4_continuity", "Gemini continuity correction loop"),
            PipelineStep("pass_5_prompts", "Claude Opus writes all frame prompts"),
            PipelineStep("pass_6_propagation", "Generate fill frames from anchors"),
        ]

    async def _execute_step(self, step: PipelineStep, input_data: Any, context: Dict) -> Any:
        """Execute a pipeline step."""
        return input_data

    async def run(self, input_data: CondensedPipelineInput) -> PipelineResult:
        """Run the full pipeline with REVISED flow."""
        start_time = time.time()

        # Initialize context
        cache_path = None
        if self.cache_conversations and self.project_path:
            cache_path = self.project_path / ".cache" / "condensed_conversation.json"

        project_id = input_data.title or f"project_{int(time.time())}"
        self.context = ConversationContext(project_id=project_id, cache_path=cache_path)

        # Track stats
        images_generated = 0
        continuity_corrections = 0

        try:
            # =================================================================
            # PASS 1: WORLD CONFIG + VISUAL SCRIPT STRUCTURE
            # =================================================================
            logger.info("=" * 60)
            logger.info("PASS 1: World Building + Story Structure")
            logger.info("=" * 60)

            world_config, visual_script, scenes = await self._pass_1_world_and_story(input_data)

            # Optimize config for visual use
            visual_config = VisualWorldConfig.from_full_config(world_config)

            logger.info(f"Pass 1 complete: {len(visual_config.characters)} chars, "
                       f"{len(visual_config.locations)} locs, {len(scenes)} scenes")

            # Initialize output containers
            character_references: Dict[str, Path] = {}
            location_references: Dict[str, Path] = {}
            frame_images: Dict[str, Path] = {}
            anchor_frames: List[FrameAnchor] = []
            frame_prompts: Dict[str, str] = {}

            # =================================================================
            # PASSES 2-6: IMAGE GENERATION (if enabled)
            # =================================================================
            if input_data.generate_images:
                # =============================================================
                # PASS 2: REFERENCE IMAGE GENERATION (FIRST!)
                # =============================================================
                logger.info("=" * 60)
                logger.info("PASS 2: Reference Image Generation (Flux 2 Pro)")
                logger.info("=" * 60)

                character_references, location_references = await self._pass_2_references(
                    visual_config, input_data
                )
                images_generated += len(character_references) + len(location_references)

                logger.info(f"Pass 2 complete: {len(character_references)} character refs, "
                           f"{len(location_references)} location refs")

                # =============================================================
                # PASS 3: KEY FRAME SELECTION + GENERATION WITH REFERENCES
                # =============================================================
                logger.info("=" * 60)
                logger.info("PASS 3: Key Frame Selection + Generation (with reference inputs)")
                logger.info("=" * 60)

                anchor_frames = self._select_key_frame_anchors(scenes, visual_config)
                logger.info(f"  Selected {len(anchor_frames)} anchor frames")

                # Generate key frames WITH reference images as inputs
                anchor_frames = await self._pass_3_keyframes_with_refs(
                    anchor_frames, scenes, character_references,
                    location_references, visual_config, input_data
                )
                images_generated += len([a for a in anchor_frames if a.image_path])

                logger.info(f"Pass 3 complete: {len([a for a in anchor_frames if a.image_path])} key frames generated")

                # =============================================================
                # PASS 4: GEMINI CONTINUITY CORRECTION LOOP
                # =============================================================
                logger.info("=" * 60)
                logger.info("PASS 4: Gemini Continuity Correction Loop")
                logger.info("=" * 60)

                anchor_frames, corrections = await self._pass_4_continuity_loop(
                    anchor_frames, character_references, location_references,
                    visual_config, world_config, input_data
                )
                continuity_corrections = corrections

                logger.info(f"Pass 4 complete: {corrections} total corrections applied")

                # =============================================================
                # PASS 5: PROMPT WRITING (AFTER KEY FRAME VALIDATION)
                # =============================================================
                logger.info("=" * 60)
                logger.info("PASS 5: Claude Opus Writes All Frame Prompts")
                logger.info("=" * 60)

                frame_prompts = await self._pass_5_write_prompts(
                    scenes, visual_config, anchor_frames, input_data
                )

                logger.info(f"Pass 5 complete: {len(frame_prompts)} prompts written")

                # =============================================================
                # PASS 6: FILL FRAME GENERATION FROM ANCHORS
                # =============================================================
                logger.info("=" * 60)
                logger.info("PASS 6: Fill Frame Generation (Anchor-Based Propagation)")
                logger.info("=" * 60)

                frame_images = await self._pass_6_propagation(
                    scenes, anchor_frames, frame_prompts, character_references,
                    location_references, visual_config, input_data
                )
                fill_count = len(frame_images) - len([a for a in anchor_frames if a.image_path])
                images_generated += max(0, fill_count)

                logger.info(f"Pass 6 complete: {len(frame_images)} total frames")

            else:
                # No image generation - just write prompts
                logger.info("=" * 60)
                logger.info("PASS 2: Frame Prompt Generation (no images)")
                logger.info("=" * 60)

                frame_prompts = await self._pass_2_prompts_only(scenes, visual_config, input_data)
                logger.info(f"Pass 2 complete: {len(frame_prompts)} prompts generated")

            # =================================================================
            # ASSEMBLE OUTPUT
            # =================================================================
            elapsed = time.time() - start_time

            total_frames = sum(len(s.frames) for s in scenes)
            key_frame_count = sum(1 for s in scenes for f in s.frames if getattr(f, '_is_key', False))

            output = CondensedPipelineOutput(
                title=input_data.title or world_config.get("global", {}).get("title", "Untitled"),
                visual_script=visual_script,
                world_config=world_config,
                visual_config=visual_config,
                scenes=scenes,
                frame_prompts=frame_prompts,
                character_references=character_references,
                location_references=location_references,
                frame_images=frame_images,
                anchor_frames=anchor_frames,
                total_frames=total_frames,
                key_frames=key_frame_count,
                images_generated=images_generated,
                continuity_corrections=continuity_corrections,
                execution_time=elapsed
            )

            # Save outputs
            if self.project_path:
                await self._save_outputs(output)

            logger.info(f"Pipeline complete in {elapsed:.1f}s - {images_generated} images generated")

            return PipelineResult(
                status=PipelineStatus.COMPLETED,
                output=output,
                duration_seconds=elapsed
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return PipelineResult(
                status=PipelineStatus.FAILED,
                error=str(e),
                duration_seconds=time.time() - start_time
            )

    # =========================================================================
    # TWO-BUTTON ARCHITECTURE: STORY PHASE (Passes 1-5)
    # =========================================================================

    async def run_story_phase(
        self,
        input_data: CondensedPipelineInput,
        progress_callback: Optional[callable] = None
    ) -> StoryPhaseOutput:
        """
        Run the Story Phase (Passes 1-5) for the "Generate Story" button.

        This method runs:
        - Pass 1: World building + story structure
        - Pass 2: Reference image generation
        - Pass 3: Key frame selection + generation
        - Pass 4: Gemini continuity correction
        - Pass 5: Claude Opus writes all prompts

        After this completes, the user can review the output before
        triggering the storyboard phase (Pass 6).

        Args:
            input_data: Pipeline input configuration
            progress_callback: Optional callback for real-time progress updates
                Signature: async def callback(event_type: str, data: dict)

        Returns:
            StoryPhaseOutput with all story phase artifacts for user review
        """
        start_time = time.time()

        # Initialize context
        cache_path = None
        if self.cache_conversations and self.project_path:
            cache_path = self.project_path / ".cache" / "condensed_conversation.json"

        project_id = input_data.title or f"project_{int(time.time())}"
        self.context = ConversationContext(project_id=project_id, cache_path=cache_path)

        # Track stats
        images_generated = 0
        continuity_corrections = 0

        async def emit(event_type: str, data: dict):
            """Emit progress event if callback provided."""
            if progress_callback:
                try:
                    await progress_callback(event_type, data)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

        try:
            # =================================================================
            # PASS 1: WORLD CONFIG + VISUAL SCRIPT STRUCTURE
            # =================================================================
            await emit("pass_start", {"pass": 1, "name": "World Building + Story Structure"})
            logger.info("=" * 60)
            logger.info("PASS 1: World Building + Story Structure")
            logger.info("=" * 60)

            world_config, visual_script, scenes = await self._pass_1_world_and_story(input_data)
            visual_config = VisualWorldConfig.from_full_config(world_config)

            logger.info(f"Pass 1 complete: {len(visual_config.characters)} chars, "
                       f"{len(visual_config.locations)} locs, {len(scenes)} scenes")

            await emit("pass_complete", {
                "pass": 1,
                "characters": len(visual_config.characters),
                "locations": len(visual_config.locations),
                "scenes": len(scenes)
            })

            # Initialize output containers
            character_references: Dict[str, Path] = {}
            location_references: Dict[str, Path] = {}
            anchor_frames: List[FrameAnchor] = []
            frame_prompts: Dict[str, str] = {}

            if input_data.generate_images:
                # =============================================================
                # PASS 2: REFERENCE IMAGE GENERATION
                # =============================================================
                await emit("pass_start", {"pass": 2, "name": "Reference Image Generation"})
                logger.info("=" * 60)
                logger.info("PASS 2: Reference Image Generation (Flux 2 Pro)")
                logger.info("=" * 60)

                character_references, location_references = await self._pass_2_references_with_callback(
                    visual_config, input_data, emit
                )
                images_generated += len(character_references) + len(location_references)

                logger.info(f"Pass 2 complete: {len(character_references)} character refs, "
                           f"{len(location_references)} location refs")

                await emit("pass_complete", {
                    "pass": 2,
                    "character_refs": len(character_references),
                    "location_refs": len(location_references)
                })

                # =============================================================
                # PASS 3: KEY FRAME SELECTION + GENERATION
                # =============================================================
                await emit("pass_start", {"pass": 3, "name": "Key Frame Generation"})
                logger.info("=" * 60)
                logger.info("PASS 3: Key Frame Selection + Generation")
                logger.info("=" * 60)

                anchor_frames = self._select_key_frame_anchors(scenes, visual_config)
                logger.info(f"  Selected {len(anchor_frames)} anchor frames")

                anchor_frames = await self._pass_3_keyframes_with_refs(
                    anchor_frames, scenes, character_references,
                    location_references, visual_config, input_data
                )

                for anchor in anchor_frames:
                    if anchor.image_path:
                        images_generated += 1
                        await emit("keyframe_generated", {
                            "frame_id": anchor.frame_id,
                            "image_path": str(anchor.image_path),
                            "character_tags": anchor.character_tags
                        })

                await emit("pass_complete", {
                    "pass": 3,
                    "keyframes": len([a for a in anchor_frames if a.image_path])
                })

                # =============================================================
                # PASS 4: GEMINI CONTINUITY CORRECTION
                # =============================================================
                await emit("pass_start", {"pass": 4, "name": "Continuity Correction"})
                logger.info("=" * 60)
                logger.info("PASS 4: Gemini Continuity Correction Loop")
                logger.info("=" * 60)

                anchor_frames, corrections = await self._pass_4_continuity_loop(
                    anchor_frames, character_references, location_references,
                    visual_config, world_config, input_data
                )
                continuity_corrections = corrections

                await emit("pass_complete", {
                    "pass": 4,
                    "corrections": corrections
                })

                # =============================================================
                # PASS 5: PROMPT WRITING
                # =============================================================
                await emit("pass_start", {"pass": 5, "name": "Prompt Writing"})
                logger.info("=" * 60)
                logger.info("PASS 5: Claude Opus Writes All Frame Prompts")
                logger.info("=" * 60)

                frame_prompts = await self._pass_5_write_prompts(
                    scenes, visual_config, anchor_frames, input_data
                )

                for frame_id, prompt in frame_prompts.items():
                    await emit("prompt_written", {
                        "frame_id": frame_id,
                        "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt
                    })

                await emit("pass_complete", {
                    "pass": 5,
                    "prompts": len(frame_prompts)
                })

            else:
                # No image generation - just write prompts
                await emit("pass_start", {"pass": 2, "name": "Prompt Writing (no images)"})
                frame_prompts = await self._pass_2_prompts_only(scenes, visual_config, input_data)
                await emit("pass_complete", {"pass": 2, "prompts": len(frame_prompts)})

            # =================================================================
            # ASSEMBLE STORY PHASE OUTPUT
            # =================================================================
            elapsed = time.time() - start_time

            total_frames = sum(len(s.frames) for s in scenes)
            key_frame_count = sum(1 for s in scenes for f in s.frames if getattr(f, '_is_key', False))

            output = StoryPhaseOutput(
                title=input_data.title or world_config.get("global", {}).get("title", "Untitled"),
                visual_script=visual_script,
                world_config=world_config,
                visual_config=visual_config,
                scenes=scenes,
                frame_prompts=frame_prompts,
                pitch=input_data.pitch,
                character_references=character_references,
                location_references=location_references,
                anchor_frames=anchor_frames,
                total_frames=total_frames,
                key_frames=key_frame_count,
                images_generated=images_generated,
                continuity_corrections=continuity_corrections,
                execution_time=elapsed,
                project_path=self.project_path,
                visual_style=input_data.visual_style,
                image_model=input_data.image_model
            )

            # Save story phase output for resumability
            if self.project_path:
                output.save()

            logger.info(f"Story phase complete in {elapsed:.1f}s - {images_generated} images generated")
            await emit("story_phase_complete", {
                "execution_time": elapsed,
                "images_generated": images_generated,
                "total_frames": total_frames
            })

            return output

        except Exception as e:
            logger.error(f"Story phase failed: {e}")
            import traceback
            traceback.print_exc()
            await emit("error", {"message": str(e)})
            raise

    async def run_storyboard_phase(
        self,
        story_output: StoryPhaseOutput,
        progress_callback: Optional[callable] = None
    ) -> CondensedPipelineOutput:
        """
        Run the Storyboard Phase (Pass 6) for the "Generate Storyboard" button.

        This method runs Pass 6: Fill frame generation using the story phase
        output as context. Call this after the user has reviewed and approved
        the story phase output.

        Args:
            story_output: Output from run_story_phase()
            progress_callback: Optional callback for real-time progress updates

        Returns:
            CondensedPipelineOutput with all generated frames
        """
        start_time = time.time()

        async def emit(event_type: str, data: dict):
            """Emit progress event if callback provided."""
            if progress_callback:
                try:
                    await progress_callback(event_type, data)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

        try:
            await emit("pass_start", {"pass": 6, "name": "Fill Frame Generation"})
            logger.info("=" * 60)
            logger.info("PASS 6: Fill Frame Generation (Storyboard Phase)")
            logger.info("=" * 60)

            # Set project path from story output
            if story_output.project_path:
                self.project_path = story_output.project_path

            # Generate fill frames
            frame_images = await self._pass_6_propagation_with_callback(
                story_output.scenes,
                story_output.anchor_frames,
                story_output.frame_prompts,
                story_output.character_references,
                story_output.location_references,
                story_output.visual_config,
                CondensedPipelineInput(
                    pitch=story_output.pitch,
                    title=story_output.title,
                    visual_style=story_output.visual_style,
                    image_model=story_output.image_model,
                    generate_images=True
                ),
                emit
            )

            fill_count = len(frame_images) - len([a for a in story_output.anchor_frames if a.image_path])
            logger.info(f"Pass 6 complete: {len(frame_images)} total frames ({fill_count} new)")

            await emit("pass_complete", {
                "pass": 6,
                "total_frames": len(frame_images),
                "new_frames": fill_count
            })

            # Assemble final output
            elapsed = time.time() - start_time
            total_elapsed = story_output.execution_time + elapsed

            output = CondensedPipelineOutput(
                title=story_output.title,
                visual_script=story_output.visual_script,
                world_config=story_output.world_config,
                visual_config=story_output.visual_config,
                scenes=story_output.scenes,
                frame_prompts=story_output.frame_prompts,
                character_references=story_output.character_references,
                location_references=story_output.location_references,
                frame_images=frame_images,
                anchor_frames=story_output.anchor_frames,
                total_frames=story_output.total_frames,
                key_frames=story_output.key_frames,
                images_generated=story_output.images_generated + fill_count,
                continuity_corrections=story_output.continuity_corrections,
                execution_time=total_elapsed
            )

            # Save full outputs
            if self.project_path:
                await self._save_outputs(output)

            logger.info(f"Storyboard phase complete in {elapsed:.1f}s")
            await emit("storyboard_complete", {
                "execution_time": elapsed,
                "total_frames": len(frame_images)
            })

            return output

        except Exception as e:
            logger.error(f"Storyboard phase failed: {e}")
            import traceback
            traceback.print_exc()
            await emit("error", {"message": str(e)})
            raise

    # =========================================================================
    # MODULAR ENTRY POINT: REFERENCE GENERATION
    # =========================================================================

    async def generate_references(
        self,
        world_config: VisualWorldConfig,
        project_path: Optional[Path] = None,
        image_model: str = "flux_2_pro",
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Path]:
        """
        Standalone entry point for reference generation.

        This method can be called independently or as part of the story phase.
        It generates character reference sheets and location establishing shots
        using the provided world configuration.

        Args:
            world_config: Visual world configuration with characters and locations
            project_path: Optional path to save reference images
            image_model: Image model to use (default: "flux_2_pro")
            progress_callback: Optional callback for progress updates

        Returns:
            Dict mapping tag -> reference_image_path for all generated references
        """
        if project_path:
            self.project_path = Path(project_path)

        async def emit(event_type: str, data: dict):
            if progress_callback:
                try:
                    await progress_callback(event_type, data)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

        input_data = CondensedPipelineInput(
            pitch="",
            image_model=image_model,
            generate_images=True
        )

        await emit("reference_generation_start", {
            "characters": len(world_config.characters),
            "locations": len(world_config.locations)
        })

        character_refs, location_refs = await self._pass_2_references_with_callback(
            world_config, input_data, emit
        )

        # Combine into single dict
        all_refs = {}
        all_refs.update(character_refs)
        all_refs.update(location_refs)

        await emit("reference_generation_complete", {
            "total": len(all_refs)
        })

        return all_refs

    async def _pass_2_references_with_callback(
        self,
        visual_config: VisualWorldConfig,
        input_data: CondensedPipelineInput,
        emit: callable
    ) -> Tuple[Dict[str, Path], Dict[str, Path]]:
        """
        Generate reference images with progress callbacks.
        Wraps _pass_2_references with event emission.
        """
        handler = self._get_image_handler()
        character_refs: Dict[str, Path] = {}
        location_refs: Dict[str, Path] = {}

        ref_dir = self.project_path / "references" if self.project_path else Path("references")
        ref_dir.mkdir(parents=True, exist_ok=True)

        # Generate character references
        for char in visual_config.characters:
            logger.info(f"  Generating reference for {char.tag}...")

            char_prompt = self._build_character_reference_prompt(char, visual_config)

            request = ImageRequest(
                prompt=char_prompt,
                model=ImageModel.FLUX_2_PRO,
                aspect_ratio="1:1",
                output_path=ref_dir / f"{char.tag}_reference.png",
                tag=char.tag,
                prefix_type="create",
                add_clean_suffix=True
            )

            result = await handler.generate(request)
            if result.success and result.image_path:
                character_refs[char.tag] = result.image_path
                logger.info(f"    [OK] {char.tag} reference saved")
                await emit("reference_generated", {
                    "type": "character",
                    "tag": char.tag,
                    "name": char.name,
                    "image_path": str(result.image_path)
                })
            else:
                logger.warning(f"    [!] Failed to generate {char.tag}: {result.error}")

        # Generate location references
        for loc in visual_config.locations:
            logger.info(f"  Generating reference for {loc.tag}...")

            loc_prompt = self._build_location_reference_prompt(loc, visual_config)

            request = ImageRequest(
                prompt=loc_prompt,
                model=ImageModel.FLUX_2_PRO,
                aspect_ratio="16:9",
                output_path=ref_dir / f"{loc.tag}_reference.png",
                tag=loc.tag,
                prefix_type="create",
                add_clean_suffix=True
            )

            result = await handler.generate(request)
            if result.success and result.image_path:
                location_refs[loc.tag] = result.image_path
                logger.info(f"    [OK] {loc.tag} reference saved")
                await emit("reference_generated", {
                    "type": "location",
                    "tag": loc.tag,
                    "name": loc.name,
                    "image_path": str(result.image_path)
                })
            else:
                logger.warning(f"    [!] Failed to generate {loc.tag}: {result.error}")

        return character_refs, location_refs

    async def _pass_6_propagation_with_callback(
        self,
        scenes: List[UnifiedScene],
        anchor_frames: List[FrameAnchor],
        frame_prompts: Dict[str, str],
        character_refs: Dict[str, Path],
        location_refs: Dict[str, Path],
        visual_config: VisualWorldConfig,
        input_data: CondensedPipelineInput,
        emit: callable
    ) -> Dict[str, Path]:
        """
        Generate fill frames with progress callbacks.
        Wraps _pass_6_propagation with event emission.
        """
        handler = self._get_image_handler()
        frame_images: Dict[str, Path] = {}

        # Add anchor images to result
        anchor_ids = set()
        for anchor in anchor_frames:
            if anchor.image_path:
                frame_images[anchor.frame_id] = anchor.image_path
                anchor_ids.add(anchor.frame_id)

        frames_dir = self.project_path / "frames" if self.project_path else Path("frames")
        frames_dir.mkdir(parents=True, exist_ok=True)

        # Build scene-based anchor lookup
        scene_anchors: Dict[int, List[FrameAnchor]] = {}
        for anchor in anchor_frames:
            if anchor.image_path:
                scene_anchors.setdefault(anchor.scene_number, []).append(anchor)

        # Process each scene
        for scene in scenes:
            scene_anchor_list = scene_anchors.get(scene.scene_number, [])
            if not scene_anchor_list:
                continue

            scene_anchor_list.sort(key=lambda a: int(a.frame_id.split('.')[1]))

            for frame in scene.frames:
                if frame.frame_id in anchor_ids:
                    continue

                prompt = frame_prompts.get(frame.frame_id, "")
                if not prompt:
                    continue

                nearest_anchor = self._find_nearest_anchor(frame, scene_anchor_list)

                if nearest_anchor and nearest_anchor.image_path:
                    ref_images = [nearest_anchor.image_path]
                    for tag in frame.tags:
                        if tag.startswith("CHAR_") and tag in character_refs:
                            if character_refs[tag].exists():
                                ref_images.append(character_refs[tag])
                else:
                    ref_images = self._collect_references_for_frame(
                        frame.frame_id, prompt, character_refs, location_refs
                    )

                logger.info(f"    Generating {frame.frame_id}...")

                if nearest_anchor:
                    edit_prompt = self._build_edit_propagation_prompt(prompt, frame, visual_config)
                    prefix_type = "edit"
                else:
                    edit_prompt = prompt
                    prefix_type = "create"

                request = ImageRequest(
                    prompt=edit_prompt,
                    model=ImageModel.FLUX_2_PRO,
                    aspect_ratio="16:9",
                    output_path=frames_dir / f"{frame.frame_id.replace('.', '_')}.png",
                    tag=frame.frame_id,
                    reference_images=ref_images[:8],
                    prefix_type=prefix_type,
                    add_clean_suffix=True
                )

                result = await handler.generate(request)
                if result.success and result.image_path:
                    frame_images[frame.frame_id] = result.image_path
                    await emit("frame_generated", {
                        "frame_id": frame.frame_id,
                        "scene_number": scene.scene_number,
                        "image_path": str(result.image_path)
                    })
                else:
                    logger.warning(f"      [!] Failed: {result.error}")

        return frame_images

    # =========================================================================
    # PASS 1: WORLD + STORY STRUCTURE
    # =========================================================================

    async def _pass_1_world_and_story(
        self,
        input_data: CondensedPipelineInput
    ) -> Tuple[Dict[str, Any], str, List[UnifiedScene]]:
        """
        Single Opus call to generate world config AND visual script structure.
        NO detailed prompts yet - just the story structure with frame markers.
        """
        size_config = self.SIZE_CONFIG.get(input_data.project_size, self.SIZE_CONFIG["short"])

        prompt = f"""{PASS_1_SYSTEM_PROMPT}

---

## YOUR TASK

Create a complete world configuration AND visual script for this pitch.

## PITCH
{input_data.pitch}

## PARAMETERS
- Title: {input_data.title or 'TBD'}
- Genre: {input_data.genre or 'drama'}
- Visual Style: {input_data.visual_style}
- Style Notes: {input_data.style_notes or 'None'}
- **PROJECT SIZE: {input_data.project_size.upper()}**
- **REQUIRED SCENES: EXACTLY {size_config['scenes']} scenes**
- **REQUIRED FRAMES PER SCENE: {size_config['frames_per_scene']} frames each**
- **TOTAL FRAMES EXPECTED: {size_config['scenes'] * size_config['frames_per_scene']} frames**

## STRICT OUTPUT REQUIREMENTS

1. Your VISUAL_SCRIPT MUST contain EXACTLY {size_config['scenes']} scenes
2. Each scene MUST contain approximately {size_config['frames_per_scene']} [FRAME:] markers
3. Count your scenes and frames before submitting - DO NOT submit fewer than required

## OUTPUT

Provide your response in TWO clearly marked sections:

### WORLD_CONFIG
```json
(complete world config following the schema above - include "era" field in global section)
```

### VISUAL_SCRIPT
```markdown
(complete visual script with [FRAME:] markers and [KEY_FRAME] annotations)
(MUST have {size_config['scenes']} scenes with ~{size_config['frames_per_scene']} frames each)
```

Begin now. Remember to PRESERVE all pitch character details exactly and ensure ERA ACCURACY."""

        response = await self.context.send(prompt, phase="pass_1", max_tokens=12000)

        # Parse world config
        world_config = self._extract_world_config(response)

        # Extract visual script
        visual_script = self._extract_visual_script(response)

        # Parse scenes
        scenes = self._parse_scenes(visual_script)

        return world_config, visual_script, scenes

    def _extract_world_config(self, response: str) -> Dict[str, Any]:
        """Extract JSON world config from response."""
        # Look for WORLD_CONFIG section
        config_match = re.search(
            r'###?\s*WORLD_CONFIG.*?```json\s*([\s\S]*?)```',
            response,
            re.IGNORECASE
        )

        if config_match:
            try:
                config = json.loads(config_match.group(1).strip())
                # Check for insufficient pitch error
                if config.get("error") == "INSUFFICIENT_PITCH":
                    raise ValueError(f"Insufficient pitch: {config.get('message', 'The pitch does not contain enough information to generate a story.')}")
                return config
            except json.JSONDecodeError:
                pass

        # Fallback: find any JSON block
        json_match = re.search(r'```json\s*([\s\S]*?)```', response)
        if json_match:
            try:
                config = json.loads(json_match.group(1).strip())
                # Check for insufficient pitch error
                if config.get("error") == "INSUFFICIENT_PITCH":
                    raise ValueError(f"Insufficient pitch: {config.get('message', 'The pitch does not contain enough information to generate a story.')}")
                return config
            except json.JSONDecodeError:
                pass

        # Last resort: try to find raw JSON
        json_match = re.search(r'\{[\s\S]*"global"[\s\S]*\}', response)
        if json_match:
            try:
                config = json.loads(json_match.group(0))
                # Check for insufficient pitch error
                if config.get("error") == "INSUFFICIENT_PITCH":
                    raise ValueError(f"Insufficient pitch: {config.get('message', 'The pitch does not contain enough information to generate a story.')}")
                return config
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to extract world config from response")
        return {"global": {}, "characters": [], "locations": [], "props": []}

    def _extract_visual_script(self, response: str) -> str:
        """Extract markdown visual script from response."""
        # Look for VISUAL_SCRIPT section
        script_match = re.search(
            r'###?\s*VISUAL_SCRIPT.*?```markdown\s*([\s\S]*?)```',
            response,
            re.IGNORECASE
        )

        if script_match:
            return script_match.group(1).strip()

        # Fallback: find content after VISUAL_SCRIPT header
        script_match = re.search(
            r'###?\s*VISUAL_SCRIPT\s*([\s\S]*?)(?=###|$)',
            response,
            re.IGNORECASE
        )

        if script_match:
            # Remove markdown code block markers if present
            text = script_match.group(1).strip()
            text = re.sub(r'```markdown\s*', '', text)
            text = re.sub(r'```\s*$', '', text)
            return text

        # Last resort: find ## Scene markers
        scenes_match = re.search(r'(##\s*Scene\s+1[\s\S]*)', response)
        if scenes_match:
            return scenes_match.group(1)

        logger.warning("Failed to extract visual script from response")
        return ""

    def _parse_scenes(self, script: str) -> List[UnifiedScene]:
        """Parse scenes from visual script."""
        scenes = []

        scene_pattern = re.compile(
            r'##\s*Scene\s+(\d+):\s*([^\n]+)\n([^\n]*)\n([\s\S]*?)(?=##\s*Scene|$)',
            re.IGNORECASE
        )

        frame_pattern = re.compile(
            r'\[FRAME:\s*([^,\]]+),\s*([^\]]+)\]\s*(\[KEY_FRAME\])?\s*(.+?)(?=\[FRAME:|$)',
            re.DOTALL
        )

        for match in scene_pattern.finditer(script):
            scene_num = int(match.group(1))
            title = match.group(2).strip()
            location_line = match.group(3).strip()
            content = match.group(4).strip()

            # Parse location (handle both [LOC_TAG] and LOC_TAG formats)
            loc_match = re.match(r'\[?(LOC_\w+)\]?\s*[-–]\s*(.+)', location_line)
            location_tag = loc_match.group(1) if loc_match else "LOC_UNKNOWN"
            time_of_day = loc_match.group(2) if loc_match else "DAY"

            frames = []
            frame_num = 0

            for frame_match in frame_pattern.finditer(content):
                frame_num += 1
                shot_type = frame_match.group(1).strip().lower()
                focus = frame_match.group(2).strip()
                is_key = frame_match.group(3) is not None
                prose = frame_match.group(4).strip()

                # Extract tags from prose (handle both [TAG] and TAG formats)
                tags = re.findall(r'\[?(CHAR_\w+|LOC_\w+|PROP_\w+)\]?', f"{focus} {prose}")

                frame = InlineFrame(
                    frame_id=f"{scene_num}.{frame_num}.cA",
                    scene_number=scene_num,
                    frame_number=frame_num,
                    shot_type=shot_type,
                    focus_subject=focus,
                    prose=prose,
                    tags=list(set(tags))
                )
                frame._is_key = is_key
                frames.append(frame)

            char_tags = list(set(re.findall(r'\[?(CHAR_\w+)\]?', content)))

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

    # =========================================================================
    # PASS 2: REFERENCE IMAGE GENERATION
    # =========================================================================

    async def _pass_2_references(
        self,
        visual_config: VisualWorldConfig,
        input_data: CondensedPipelineInput
    ) -> Tuple[Dict[str, Path], Dict[str, Path]]:
        """
        Generate reference images for characters and locations using Flux 2 Pro.
        These are generated FIRST and become the visual TRUTH for all subsequent images.

        Returns:
            Tuple of (character_references, location_references) dicts mapping tag -> image path
        """
        handler = self._get_image_handler()
        character_refs: Dict[str, Path] = {}
        location_refs: Dict[str, Path] = {}

        # Create references directory
        ref_dir = self.project_path / "references" if self.project_path else Path("references")
        ref_dir.mkdir(parents=True, exist_ok=True)

        # Generate character reference sheets
        for char in visual_config.characters:
            logger.info(f"  Generating reference for {char.tag}...")

            # Build character reference prompt
            char_prompt = self._build_character_reference_prompt(char, visual_config)

            request = ImageRequest(
                prompt=char_prompt,
                model=ImageModel.FLUX_2_PRO,
                aspect_ratio="1:1",  # Square for character sheets
                output_path=ref_dir / f"{char.tag}_reference.png",
                tag=char.tag,
                prefix_type="create",
                add_clean_suffix=True
            )

            result = await handler.generate(request)
            if result.success and result.image_path:
                character_refs[char.tag] = result.image_path
                logger.info(f"    [OK] {char.tag} reference saved")
            else:
                logger.warning(f"    [!] Failed to generate {char.tag}: {result.error}")

        # Generate location establishing shots
        for loc in visual_config.locations:
            logger.info(f"  Generating reference for {loc.tag}...")

            loc_prompt = self._build_location_reference_prompt(loc, visual_config)

            request = ImageRequest(
                prompt=loc_prompt,
                model=ImageModel.FLUX_2_PRO,
                aspect_ratio="16:9",  # Cinematic for locations
                output_path=ref_dir / f"{loc.tag}_reference.png",
                tag=loc.tag,
                prefix_type="create",
                add_clean_suffix=True
            )

            result = await handler.generate(request)
            if result.success and result.image_path:
                location_refs[loc.tag] = result.image_path
                logger.info(f"    [OK] {loc.tag} reference saved")
            else:
                logger.warning(f"    [!] Failed to generate {loc.tag}: {result.error}")

        return character_refs, location_refs

    def _build_character_reference_prompt(
        self,
        char: VisualCharacter,
        config: VisualWorldConfig
    ) -> str:
        """Build a Flux 2 Pro optimized prompt for character reference generation."""
        style = config.visual_style or "live_action"
        era = config.era_style or "contemporary"

        # Flux 2 Pro: Subject first, natural language, no negatives
        prompt = f"""{char.name}, {char.appearance}

Wearing {era}-era clothing: {char.costume}

Full body front view, standing in neutral pose with arms relaxed at sides, facing camera directly. Professional studio lighting from above-left casting soft shadows, neutral grey backdrop. 85mm portrait lens, f/4 aperture for sharp full-body focus. Character reference sheet composition, photorealistic, high detail on facial features and costume textures.

Style: {style}, character design reference, professional portrait photography."""

        return prompt

    def _build_location_reference_prompt(
        self,
        loc: VisualLocation,
        config: VisualWorldConfig
    ) -> str:
        """Build a Flux 2 Pro optimized prompt for location reference generation."""
        style = config.visual_style or "live_action"
        era = config.era_style or "contemporary"
        palette = config.color_palette or ""

        # Extract lighting info safely
        lighting = loc.lighting if hasattr(loc, 'lighting') and loc.lighting else f"{era}-era natural lighting"
        atmosphere = loc.atmosphere if hasattr(loc, 'atmosphere') and loc.atmosphere else ""

        # Flux 2 Pro: Subject first, natural language, specific details
        prompt = f"""{loc.name}, {era}-era architecture. {loc.description}

{atmosphere} {lighting}

Wide cinematic establishing shot, 24mm wide-angle lens, eye-level camera angle, deep focus showing full architectural details. Empty scene with no people visible. {palette} color palette. Photorealistic, architectural photography, golden hour natural lighting from the side.

Style: {style}, cinematic establishing shot, location reference."""

        return prompt

    # =========================================================================
    # PASS 3: KEY FRAME SELECTION + GENERATION WITH REFERENCES
    # =========================================================================

    def _select_key_frame_anchors(
        self,
        scenes: List[UnifiedScene],
        visual_config: VisualWorldConfig
    ) -> List[FrameAnchor]:
        """
        Select key frame anchors prioritizing:
        1. Establishing shots with most characters (highest priority)
        2. KEY_FRAME marked frames
        3. Scene opening/closing frames

        Returns sorted list of FrameAnchor objects by priority (highest first).
        """
        anchors: List[FrameAnchor] = []

        for scene in scenes:
            for frame in scene.frames:
                # Extract character tags from this frame
                char_tags = [t for t in frame.tags if t.startswith("CHAR_")]
                char_count = len(char_tags)

                # Check if establishing shot
                is_establishing = frame.shot_type.lower() in self.ESTABLISHING_SHOTS

                # Check if marked as key frame
                is_key = getattr(frame, '_is_key', False)

                # Check if first or last frame in scene
                is_boundary = (frame.frame_number == 1 or
                              frame.frame_number == len(scene.frames))

                # Calculate anchor priority score
                priority = char_count * 10  # Base: more characters = higher priority
                if is_establishing:
                    priority += 25  # Big bonus for establishing shots
                if is_key:
                    priority += 15  # Bonus for marked key frames
                if is_boundary:
                    priority += 5   # Small bonus for scene boundaries

                # Only include frames with sufficient priority
                if priority >= 10 or is_key or is_boundary:
                    anchor = FrameAnchor(
                        frame_id=frame.frame_id,
                        scene_number=scene.scene_number,
                        character_count=char_count,
                        is_establishing=is_establishing,
                        is_key_frame=is_key,
                        anchor_priority=priority,
                        character_tags=char_tags,
                        location_tag=scene.location_tag
                    )
                    anchors.append(anchor)

        # Sort by priority (highest first)
        anchors.sort(key=lambda a: a.anchor_priority, reverse=True)

        # Log anchor selection
        logger.info(f"  Selected {len(anchors)} anchor frames:")
        for a in anchors[:5]:  # Show top 5
            logger.info(f"    {a.frame_id}: priority={a.anchor_priority:.0f}, "
                       f"chars={a.character_count}, establishing={a.is_establishing}")

        return anchors

    async def _pass_3_keyframes_with_refs(
        self,
        anchor_frames: List[FrameAnchor],
        scenes: List[UnifiedScene],
        character_refs: Dict[str, Path],
        location_refs: Dict[str, Path],
        visual_config: VisualWorldConfig,
        input_data: CondensedPipelineInput
    ) -> List[FrameAnchor]:
        """
        Generate key frame images using reference images as INPUTS.
        This ensures visual consistency from the start.
        """
        handler = self._get_image_handler()

        # Create keyframes directory
        keyframe_dir = self.project_path / "keyframes" if self.project_path else Path("keyframes")
        keyframe_dir.mkdir(parents=True, exist_ok=True)

        # Build scene lookup for frame prose
        scene_lookup = {s.scene_number: s for s in scenes}
        frame_lookup = {}
        for scene in scenes:
            for frame in scene.frames:
                frame_lookup[frame.frame_id] = (scene, frame)

        for anchor in anchor_frames:
            if anchor.frame_id not in frame_lookup:
                logger.warning(f"  Frame {anchor.frame_id} not found in scenes, skipping")
                continue

            scene, frame = frame_lookup[anchor.frame_id]

            logger.info(f"  Generating key frame {anchor.frame_id} (priority={anchor.anchor_priority:.0f})...")

            # Build prompt from frame prose + world config
            key_prompt = self._build_keyframe_prompt(frame, scene, visual_config)

            # Collect reference images for this frame - THIS IS THE KEY PART
            ref_images = []

            # Add character references for characters in this frame
            for tag in anchor.character_tags:
                if tag in character_refs and character_refs[tag].exists():
                    ref_images.append(character_refs[tag])
                    logger.info(f"    + Using reference: {tag}")

            # Add location reference
            if anchor.location_tag in location_refs and location_refs[anchor.location_tag].exists():
                ref_images.append(location_refs[anchor.location_tag])
                logger.info(f"    + Using reference: {anchor.location_tag}")

            # Generate the key frame with references as inputs
            request = ImageRequest(
                prompt=key_prompt,
                model=ImageModel.FLUX_2_PRO,
                aspect_ratio="16:9",
                output_path=keyframe_dir / f"{anchor.frame_id.replace('.', '_')}.png",
                tag=anchor.frame_id,
                reference_images=ref_images[:8],  # Flux 2 Pro max 8 refs
                prefix_type="create",
                add_clean_suffix=True
            )

            result = await handler.generate(request)

            if result.success and result.image_path:
                anchor.image_path = result.image_path
                logger.info(f"    [OK] {anchor.frame_id} generated with {len(ref_images)} references")
            else:
                logger.warning(f"    [!] Failed to generate {anchor.frame_id}: {result.error}")

        return anchor_frames

    def _build_keyframe_prompt(
        self,
        frame: InlineFrame,
        scene: UnifiedScene,
        visual_config: VisualWorldConfig
    ) -> str:
        """Build a prompt for key frame generation using world config details."""
        parts = []

        # Shot type
        parts.append(f"{frame.shot_type} shot")

        # Location context
        loc = visual_config.get_location(scene.location_tag)
        if loc:
            parts.append(f"in {loc.name}")
            parts.append(f"Lighting: {loc.lighting}")

        # Characters in frame with their appearance details
        for tag in frame.tags:
            if tag.startswith("CHAR_"):
                char = visual_config.get_character(tag)
                if char:
                    parts.append(f"{char.name} [{tag}]: {char.appearance[:150]}")
                    if char.costume:
                        parts.append(f"wearing {char.costume[:100]}")

        # Frame action/prose
        parts.append(f"Action: {frame.prose[:200]}")

        # Style
        parts.append(f"Style: {visual_config.visual_style}")

        return ". ".join(parts)

    # =========================================================================
    # PASS 4: GEMINI CONTINUITY CORRECTION LOOP (SELF-HEALING)
    # =========================================================================

    async def _pass_4_continuity_loop(
        self,
        anchor_frames: List[FrameAnchor],
        character_refs: Dict[str, Path],
        location_refs: Dict[str, Path],
        visual_config: VisualWorldConfig,
        world_config: Dict[str, Any],
        input_data: CondensedPipelineInput
    ) -> Tuple[List[FrameAnchor], int]:
        """
        Use Gemini to validate each key frame against references and world config.
        Performs MULTI-IMAGE ANALYSIS comparing generated frame to reference images.
        Applies corrections via edit prompts if inconsistencies detected.

        Self-Healing Loop:
        1. Gemini analyzes generated frame + reference images side-by-side
        2. Identifies character design, continuity, and composition issues
        3. Generates specific correction prompts based on analysis
        4. FLUX 2 Pro regenerates with corrections
        5. Loop continues until validated or max corrections reached
        """
        handler = self._get_image_handler()
        total_corrections = 0

        # Metrics tracking
        issue_counts = {"character_mismatch": 0, "missing_character": 0, "location_mismatch": 0,
                        "lighting_issue": 0, "composition_issue": 0, "extra_character": 0}
        frames_validated = 0
        frames_corrected = 0

        keyframe_dir = self.project_path / "keyframes" if self.project_path else Path("keyframes")

        logger.info(f"  Starting self-healing loop for {len(anchor_frames)} anchor frames")
        logger.info(f"  Max corrections per frame: {input_data.max_continuity_corrections}")

        for anchor in anchor_frames:
            if not anchor.image_path or not anchor.image_path.exists():
                logger.warning(f"  Skipping {anchor.frame_id} - no image generated")
                continue

            logger.info(f"  Validating {anchor.frame_id}...")

            # Collect reference images for comparison with labels
            ref_images = []
            ref_labels = []

            for tag in anchor.character_tags:
                if tag in character_refs and character_refs[tag].exists():
                    ref_images.append(character_refs[tag])
                    char = visual_config.get_character(tag)
                    label = f"Reference: {char.name if char else tag}"
                    ref_labels.append(label)

            if anchor.location_tag in location_refs and location_refs[anchor.location_tag].exists():
                ref_images.append(location_refs[anchor.location_tag])
                loc = visual_config.get_location(anchor.location_tag)
                ref_labels.append(f"Reference: {loc.name if loc else anchor.location_tag}")

            # Run correction loop
            current_image = anchor.image_path
            corrections = 0
            frame_issues = []

            for correction_pass in range(input_data.max_continuity_corrections):
                try:
                    # Build multi-image analysis with reference comparison
                    all_images = [current_image] + ref_images
                    all_labels = ["Generated Frame (to analyze)"] + ref_labels

                    # Build comprehensive analysis prompt
                    analysis_prompt = self._build_multiimage_analysis_prompt(
                        anchor, visual_config, world_config, ref_labels
                    )

                    # Use multi-image analysis for side-by-side comparison
                    logger.info(f"    Pass {correction_pass + 1}: Gemini analyzing {len(all_images)} images...")
                    analysis = self._gemini.analyze_images(
                        all_images, analysis_prompt, return_json=True, image_labels=all_labels
                    )

                    if analysis.parsed_json:
                        issues = analysis.parsed_json.get("issues", [])
                        needs_correction = analysis.parsed_json.get("needs_correction", False)
                        quality = analysis.parsed_json.get("overall_quality", "unknown")
                        confidence = analysis.parsed_json.get("confidence_score", 0)

                        # Track issue types
                        for issue in issues:
                            issue_type = issue.get("type", "unknown")
                            if issue_type in issue_counts:
                                issue_counts[issue_type] += 1
                            frame_issues.append(issue)

                        # Filter to only critical issue types
                        critical_issues = [i for i in issues if i.get("type") in
                                          ("wrong_era", "wrong_costume", "missing_character", "wrong_ethnicity")]

                        # Accept if quality is good/acceptable OR no critical issues
                        if not needs_correction or not critical_issues or quality in ("excellent", "good", "acceptable"):
                            logger.info(f"    [OK] Validated (quality={quality}, confidence={confidence}%)")
                            anchor.continuity_validated = True
                            frames_validated += 1
                            break

                        # Only proceed with correction if there are critical issues
                        logger.info(f"    [!] {len(critical_issues)} critical issues found")
                        for issue in critical_issues[:3]:
                            logger.info(f"        - {issue.get('type')}: {issue.get('description', '')[:60]}...")

                        # Build correction prompt with specific fixes (only critical issues)
                        correction_prompt = self._build_enhanced_correction_prompt(
                            anchor, critical_issues, visual_config, world_config, analysis.parsed_json
                        )

                        # Collect TAG-SPECIFIC reference images for the characters that need fixing
                        correction_refs = [current_image]  # Start with current frame
                        for issue in critical_issues:
                            tag = issue.get("tag", "")
                            if tag and tag.startswith("CHAR_") and tag in character_refs:
                                if character_refs[tag].exists():
                                    correction_refs.append(character_refs[tag])
                                    logger.info(f"        + Using {tag} reference for correction")

                        # Add location ref if location issue
                        if any(i.get("type") == "wrong_era" for i in critical_issues):
                            if anchor.location_tag in location_refs and location_refs[anchor.location_tag].exists():
                                correction_refs.append(location_refs[anchor.location_tag])

                        # Generate corrected image using NANO_BANANA_PRO for edits
                        request = ImageRequest(
                            prompt=correction_prompt,
                            model=ImageModel.NANO_BANANA_PRO,  # Use Nano Banana Pro for corrections
                            aspect_ratio="16:9",
                            output_path=keyframe_dir / f"{anchor.frame_id.replace('.', '_')}_v{correction_pass + 2}.png",
                            tag=anchor.frame_id,
                            reference_images=correction_refs[:4],  # Nano Banana Pro supports fewer refs
                            prefix_type="edit",
                            add_clean_suffix=True
                        )

                        result = await handler.generate(request)
                        if result.success and result.image_path:
                            current_image = result.image_path
                            anchor.image_path = current_image
                            corrections += 1
                            total_corrections += 1
                            logger.info(f"    [CORRECTED] v{correction_pass + 2} generated")
                        else:
                            logger.warning(f"    Correction failed: {result.error}")
                            break
                    else:
                        # Could not parse JSON - try to extract issues from text
                        logger.info(f"    [OK] Could not parse analysis JSON, assuming valid")
                        anchor.continuity_validated = True
                        frames_validated += 1
                        break

                except Exception as e:
                    logger.warning(f"    Gemini analysis error: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    break

            anchor.correction_count = corrections
            if corrections > 0:
                frames_corrected += 1
            if corrections == 0 and not anchor.continuity_validated:
                anchor.continuity_validated = True  # Mark as validated if no corrections needed

        # Log summary metrics
        logger.info(f"  Self-healing loop complete:")
        logger.info(f"    Frames validated: {frames_validated}/{len(anchor_frames)}")
        logger.info(f"    Frames corrected: {frames_corrected}")
        logger.info(f"    Total corrections: {total_corrections}")
        logger.info(f"    Issue breakdown: {issue_counts}")

        return anchor_frames, total_corrections

    def _build_multiimage_analysis_prompt(
        self,
        anchor: FrameAnchor,
        visual_config: VisualWorldConfig,
        world_config: Dict[str, Any],
        ref_labels: List[str]
    ) -> str:
        """Build comprehensive prompt for multi-image Gemini analysis."""
        # Build character reference descriptions from world config
        char_descs = []
        for tag in anchor.character_tags:
            char = visual_config.get_character(tag)
            if char:
                desc = f"- [{tag}] {char.name}:\n"
                desc += f"    Appearance: {char.appearance[:250]}\n"
                if char.costume:
                    desc += f"    Costume: {char.costume[:150]}\n"
                if hasattr(char, 'age') and char.age:
                    desc += f"    Age: {char.age}\n"
                if hasattr(char, 'ethnicity') and char.ethnicity:
                    desc += f"    Ethnicity: {char.ethnicity}\n"
                char_descs.append(desc)

        # Location description
        loc_desc = ""
        loc = visual_config.get_location(anchor.location_tag)
        if loc:
            loc_desc = f"Location [{anchor.location_tag}]: {loc.name}\n"
            loc_desc += f"  Description: {loc.description[:200]}\n"
            if loc.lighting:
                loc_desc += f"  Lighting: {loc.lighting}\n"
            if loc.atmosphere:
                loc_desc += f"  Atmosphere: {loc.atmosphere}\n"

        # Get era/style from world config
        era = world_config.get("global", {}).get("era", "Historical period")
        visual_style = world_config.get("global", {}).get("visual_style", "live_action")

        return f"""You are a visual continuity supervisor for a storyboard production.

## CRITICAL CONTEXT - DO NOT IGNORE
Era/Setting: {era}
Visual Style: {visual_style}
This is a PERIOD PIECE. Any modern elements are WRONG.

## YOUR TASK
Compare the GENERATED FRAME against the REFERENCE IMAGES.
ONLY flag issues that would genuinely break visual continuity for a viewer.

## IMAGES PROVIDED
1. Generated Frame (to analyze)
{chr(10).join([f"{i+2}. {label}" for i, label in enumerate(ref_labels)])}

## EXPECTED CHARACTERS:
{chr(10).join(char_descs) if char_descs else "No specific characters expected"}

## EXPECTED LOCATION:
{loc_desc if loc_desc else "No specific location defined"}

## VALIDATION CRITERIA (BE LENIENT - only flag MAJOR issues):

### CRITICAL ISSUES (must fix):
- Character wearing completely wrong outfit (modern clothes instead of period costume)
- Wrong era/setting (modern environment instead of {era})
- Character completely missing from frame
- Wrong ethnicity (should be Han Chinese)

### ACCEPTABLE VARIATIONS (do NOT flag):
- Slight differences in hair styling or arrangement
- Minor color shade variations (dark blue vs navy)
- Facial expression differences
- Slight pose or angle differences
- Lighting mood variations
- Background detail differences

## RETURN JSON:
{{
  "needs_correction": true/false,
  "confidence_score": 0-100,
  "overall_quality": "excellent/good/acceptable/poor",
  "issues": [
    {{
      "type": "wrong_era|wrong_costume|missing_character|wrong_ethnicity",
      "tag": "CHAR_NAME if applicable",
      "description": "What's critically wrong",
      "severity": "high",
      "fix_instruction": "Specific fix"
    }}
  ],
  "correct_elements": ["Elements to preserve"]
}}

IMPORTANT: Set needs_correction=true ONLY for critical issues.
If the frame generally matches the references and era, mark it as acceptable.
Be LENIENT - minor imperfections are fine for storyboards."""

    def _build_enhanced_correction_prompt(
        self,
        anchor: FrameAnchor,
        issues: List[Dict],
        visual_config: VisualWorldConfig,
        world_config: Dict[str, Any],
        full_analysis: Dict[str, Any]
    ) -> str:
        """Build detailed edit prompt with specific corrections from Gemini analysis."""
        # Get era/style context - CRITICAL for preventing modern drift
        era = world_config.get("global", {}).get("era", "Imperial China")
        visual_style = world_config.get("global", {}).get("visual_style", "live_action")
        color_palette = world_config.get("global", {}).get("color_palette", "")

        corrections = []
        preserve_elements = full_analysis.get("correct_elements", [])

        # Sort issues by severity (high first)
        sorted_issues = sorted(issues, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", "low"), 2))

        for issue in sorted_issues:
            issue_type = issue.get("type", "")
            tag = issue.get("tag", "")
            fix_instruction = issue.get("fix_instruction", "")
            expected = issue.get("expected", "")
            description = issue.get("description", "")

            if issue_type in ("wrong_era", "wrong_costume", "missing_character", "wrong_ethnicity"):
                if fix_instruction:
                    corrections.append(f"- {fix_instruction}")
                elif tag and tag.startswith("CHAR_"):
                    char = visual_config.get_character(tag)
                    if char:
                        corrections.append(f"- {char.name}: {char.costume[:150]}")
                elif description:
                    corrections.append(f"- {description}")

        correction_text = "\n".join(corrections) if corrections else "- Ensure period-accurate costume and setting"

        # Build character costume reminders
        char_costumes = []
        for tag in anchor.character_tags:
            char = visual_config.get_character(tag)
            if char and char.costume:
                char_costumes.append(f"- {char.name}: {char.costume[:120]}")

        costume_text = "\n".join(char_costumes) if char_costumes else ""

        return f"""CRITICAL: This is {era}. NO modern elements allowed.

## CORRECTIONS:
{correction_text}

## MANDATORY COSTUME REFERENCE:
{costume_text}

## STYLE REQUIREMENTS:
- Era: {era}
- Style: {visual_style}
- Colors: {color_palette[:100] if color_palette else 'Period appropriate'}

## PRESERVE:
- Overall composition and camera angle
- Character positions and poses
- Lighting mood

Transform any modern elements to period-accurate {era} equivalents.
Characters must wear traditional Chinese clothing as specified above."""

    def _build_continuity_analysis_prompt(
        self,
        anchor: FrameAnchor,
        visual_config: VisualWorldConfig,
        world_config: Dict[str, Any]
    ) -> str:
        """Build prompt for single-image Gemini continuity analysis (fallback)."""
        # Build character reference descriptions from world config
        char_descs = []
        for tag in anchor.character_tags:
            char = visual_config.get_character(tag)
            if char:
                char_descs.append(f"- [{tag}] {char.name}: {char.appearance[:200]}")
                if char.costume:
                    char_descs.append(f"  Costume: {char.costume[:100]}")

        # Location description
        loc_desc = ""
        loc = visual_config.get_location(anchor.location_tag)
        if loc:
            loc_desc = f"Location [{anchor.location_tag}]: {loc.description[:200]}"

        return f"""Analyze this storyboard frame for visual continuity issues.

## Expected Characters (from world config):
{chr(10).join(char_descs) if char_descs else "No specific characters expected"}

## Expected Location:
{loc_desc}

## Check for these issues:
1. Character appearance mismatches (wrong features, age, ethnicity, clothing)
2. Missing characters that should be present based on tags
3. Wrong or extra characters present
4. Location/environment inconsistencies
5. Lighting/atmosphere issues
6. Composition problems

## Return JSON:
{{
  "needs_correction": true/false,
  "confidence_score": 0-100,
  "issues": [
    {{"type": "character_mismatch", "tag": "CHAR_NAME", "description": "specific issue", "severity": "high/medium/low", "fix_instruction": "how to fix"}},
    ...
  ],
  "overall_quality": "good/acceptable/poor"
}}"""

    def _build_correction_prompt_with_context(
        self,
        anchor: FrameAnchor,
        issues: List[Dict],
        visual_config: VisualWorldConfig,
        world_config: Dict[str, Any]
    ) -> str:
        """Build an edit prompt to correct identified issues using world config (fallback)."""
        corrections = []
        for issue in issues:
            desc = issue.get("description", "")
            tag = issue.get("tag", "")
            fix_instruction = issue.get("fix_instruction", "")

            if fix_instruction:
                corrections.append(f"- {fix_instruction}")
            elif tag and tag.startswith("CHAR_"):
                char = visual_config.get_character(tag)
                if char:
                    corrections.append(f"- Fix {tag}: Should be {char.appearance[:150]}")
                    continue
            elif desc:
                corrections.append(f"- Fix: {desc}")

        correction_text = "\n".join(corrections)

        return f"""Correct these specific issues while preserving the overall composition:

{correction_text}

Maintain all correct elements. Only fix the identified issues.
Preserve the scene's lighting, camera angle, and mood."""

    # =========================================================================
    # PASS 5: PROMPT WRITING (AFTER KEY FRAME VALIDATION)
    # =========================================================================

    async def _pass_5_write_prompts(
        self,
        scenes: List[UnifiedScene],
        visual_config: VisualWorldConfig,
        anchor_frames: List[FrameAnchor],
        input_data: CondensedPipelineInput
    ) -> Dict[str, str]:
        """
        Claude Opus writes ALL detailed frame prompts AFTER key frames are validated.
        This ensures prompts reference the actual validated visual content.
        """
        # Build context about validated key frames
        validated_anchors = [a for a in anchor_frames if a.continuity_validated or a.image_path]
        anchor_context = []
        for a in validated_anchors:
            anchor_context.append(f"  - {a.frame_id}: chars={a.character_tags}, loc={a.location_tag}")

        # Build frame list
        frame_list = []
        for scene in scenes:
            for frame in scene.frames:
                is_key = "KEY" if getattr(frame, '_is_key', False) else "fill"
                frame_list.append({
                    "id": frame.frame_id,
                    "type": is_key,
                    "shot": frame.shot_type,
                    "focus": frame.focus_subject,
                    "prose": frame.prose[:200],
                    "tags": frame.tags,
                    "location": scene.location_tag
                })

        frames_text = "\n".join([
            f"[{f['id']}] ({f['type']}) {f['shot']} - {f['focus']}\n  Tags: {f['tags']}\n  Location: {f['location']}\n  Prose: {f['prose']}..."
            for f in frame_list
        ])

        prompt = f"""{PASS_5_PROMPT_WRITING_SYSTEM}

---

## WORLD CONFIG REFERENCE

### Characters
{self._format_characters(visual_config)}

### Locations
{self._format_locations(visual_config)}

---

## VALIDATED KEY FRAMES (visual continuity established)
{chr(10).join(anchor_context) if anchor_context else "No key frames validated yet"}

---

## ALL FRAMES TO PROCESS

{frames_text}

---

## OUTPUT

Generate a detailed prompt (80-120 words) for EACH frame above.

Format:
[FRAME_ID]: prompt text here...

Remember:
- Use character tags like [CHAR_MEI] in prompts for identification
- Reference the exact character descriptions from world config
- Maintain visual continuity with validated key frames
- Include shot type, lighting, mood, composition

Begin now."""

        response = await self.context.send(prompt, phase="pass_5", max_tokens=10000)

        # Parse prompts
        prompts = {}
        prompt_pattern = re.compile(r'\[(\d+\.\d+\.c\w+)\]:\s*(.+?)(?=\[\d+\.\d+\.c\w+\]:|$)', re.DOTALL)

        for match in prompt_pattern.finditer(response):
            frame_id = match.group(1)
            prompt_text = match.group(2).strip()
            prompts[frame_id] = prompt_text

        return prompts

    def _format_characters(self, config: VisualWorldConfig) -> str:
        """Format characters for prompt context."""
        lines = []
        for char in config.characters:
            lines.append(f"**[{char.tag}]** {char.name}")
            lines.append(f"  Age: {char.age}, Ethnicity: {char.ethnicity}")
            lines.append(f"  Appearance: {char.appearance[:200]}...")
            lines.append(f"  Costume: {char.costume[:150]}...")
            lines.append("")
        return "\n".join(lines)

    def _format_locations(self, config: VisualWorldConfig) -> str:
        """Format locations for prompt context."""
        lines = []
        for loc in config.locations:
            lines.append(f"**[{loc.tag}]** {loc.name}")
            lines.append(f"  {loc.description[:150]}...")
            lines.append(f"  Lighting: {loc.lighting}")
            lines.append("")
        return "\n".join(lines)

    # =========================================================================
    # PASS 2 (NO IMAGES): PROMPTS ONLY
    # =========================================================================

    async def _pass_2_prompts_only(
        self,
        scenes: List[UnifiedScene],
        visual_config: VisualWorldConfig,
        input_data: CondensedPipelineInput
    ) -> Dict[str, str]:
        """
        Generate prompts without image generation (for --no-images mode).
        """
        # Build frame list
        frame_list = []
        for scene in scenes:
            for frame in scene.frames:
                is_key = "KEY" if getattr(frame, '_is_key', False) else "fill"
                frame_list.append({
                    "id": frame.frame_id,
                    "type": is_key,
                    "shot": frame.shot_type,
                    "focus": frame.focus_subject,
                    "prose": frame.prose[:200]
                })

        frames_text = "\n".join([
            f"[{f['id']}] ({f['type']}) {f['shot']} - {f['focus']}: {f['prose']}..."
            for f in frame_list
        ])

        prompt = f"""{PASS_5_PROMPT_WRITING_SYSTEM}

---

## WORLD CONFIG REFERENCE

### Characters
{self._format_characters(visual_config)}

### Locations
{self._format_locations(visual_config)}

---

## FRAMES TO PROCESS

{frames_text}

---

## OUTPUT

Generate a detailed prompt (60-100 words) for EACH frame above.

Format:
[FRAME_ID]: prompt text here...

Begin now."""

        response = await self.context.send(prompt, phase="pass_2", max_tokens=8000)

        # Parse prompts
        prompts = {}
        prompt_pattern = re.compile(r'\[(\d+\.\d+\.c\w+)\]:\s*(.+?)(?=\[\d+\.\d+\.c\w+\]:|$)', re.DOTALL)

        for match in prompt_pattern.finditer(response):
            frame_id = match.group(1)
            prompt_text = match.group(2).strip()
            prompts[frame_id] = prompt_text

        return prompts

    # =========================================================================
    # PASS 6: ANCHOR-BASED EDIT PROPAGATION
    # =========================================================================

    async def _pass_6_propagation(
        self,
        scenes: List[UnifiedScene],
        anchor_frames: List[FrameAnchor],
        frame_prompts: Dict[str, str],
        character_refs: Dict[str, Path],
        location_refs: Dict[str, Path],
        visual_config: VisualWorldConfig,
        input_data: CondensedPipelineInput
    ) -> Dict[str, Path]:
        """
        Generate fill frames by propagating from anchor frames using edit prompts.
        """
        handler = self._get_image_handler()
        frame_images: Dict[str, Path] = {}

        # Add anchor images to result
        anchor_ids = set()
        for anchor in anchor_frames:
            if anchor.image_path:
                frame_images[anchor.frame_id] = anchor.image_path
                anchor_ids.add(anchor.frame_id)

        # Create frames directory
        frames_dir = self.project_path / "frames" if self.project_path else Path("frames")
        frames_dir.mkdir(parents=True, exist_ok=True)

        # Build scene-based anchor lookup
        scene_anchors: Dict[int, List[FrameAnchor]] = {}
        for anchor in anchor_frames:
            if anchor.image_path:
                scene_anchors.setdefault(anchor.scene_number, []).append(anchor)

        # Process each scene
        for scene in scenes:
            scene_anchor_list = scene_anchors.get(scene.scene_number, [])
            if not scene_anchor_list:
                logger.warning(f"  Scene {scene.scene_number}: No anchors, skipping fill frames")
                continue

            # Sort anchors in scene by frame number
            scene_anchor_list.sort(key=lambda a: int(a.frame_id.split('.')[1]))

            for frame in scene.frames:
                if frame.frame_id in anchor_ids:
                    continue  # Already generated as anchor

                prompt = frame_prompts.get(frame.frame_id, "")
                if not prompt:
                    continue

                # Find nearest anchor for this frame
                nearest_anchor = self._find_nearest_anchor(frame, scene_anchor_list)

                # Collect references
                if nearest_anchor and nearest_anchor.image_path:
                    ref_images = [nearest_anchor.image_path]
                    # Add character refs for this frame
                    for tag in frame.tags:
                        if tag.startswith("CHAR_") and tag in character_refs:
                            if character_refs[tag].exists():
                                ref_images.append(character_refs[tag])
                else:
                    ref_images = self._collect_references_for_frame(
                        frame.frame_id, prompt, character_refs, location_refs
                    )

                logger.info(f"    Generating {frame.frame_id} from anchor {nearest_anchor.frame_id if nearest_anchor else 'none'}...")

                # Build edit prompt
                if nearest_anchor:
                    edit_prompt = self._build_edit_propagation_prompt(
                        prompt, frame, visual_config
                    )
                    prefix_type = "edit"
                else:
                    edit_prompt = prompt
                    prefix_type = "create"

                request = ImageRequest(
                    prompt=edit_prompt,
                    model=ImageModel.FLUX_2_PRO,
                    aspect_ratio="16:9",
                    output_path=frames_dir / f"{frame.frame_id.replace('.', '_')}.png",
                    tag=frame.frame_id,
                    reference_images=ref_images[:8],
                    prefix_type=prefix_type,
                    add_clean_suffix=True
                )

                result = await handler.generate(request)
                if result.success and result.image_path:
                    frame_images[frame.frame_id] = result.image_path
                else:
                    logger.warning(f"      [!] Failed: {result.error}")

        return frame_images

    def _find_nearest_anchor(
        self,
        frame: InlineFrame,
        scene_anchors: List[FrameAnchor]
    ) -> Optional[FrameAnchor]:
        """Find the nearest anchor frame (by frame number) within the same scene."""
        if not scene_anchors:
            return None

        frame_num = frame.frame_number
        nearest = None
        min_distance = float('inf')

        for anchor in scene_anchors:
            anchor_frame_num = int(anchor.frame_id.split('.')[1])
            distance = abs(anchor_frame_num - frame_num)
            if distance < min_distance:
                min_distance = distance
                nearest = anchor

        return nearest

    def _collect_references_for_frame(
        self,
        frame_id: str,
        prompt: str,
        character_refs: Dict[str, Path],
        location_refs: Dict[str, Path]
    ) -> List[Path]:
        """Collect relevant reference images for a frame based on prompt content."""
        refs = []

        # Find character tags in prompt
        char_tags = re.findall(r'\[?(CHAR_\w+)\]?', prompt)
        for tag in char_tags:
            if tag in character_refs and character_refs[tag].exists():
                refs.append(character_refs[tag])

        # Find location tags in prompt
        loc_tags = re.findall(r'\[?(LOC_\w+)\]?', prompt)
        for tag in loc_tags:
            if tag in location_refs and location_refs[tag].exists():
                refs.append(location_refs[tag])

        return refs[:8]

    def _build_edit_propagation_prompt(
        self,
        target_prompt: str,
        frame: InlineFrame,
        visual_config: VisualWorldConfig
    ) -> str:
        """Build an edit prompt that transitions from anchor frame to target frame."""
        return f"""Transform the anchor image to show:

{target_prompt}

Preserve the visual style, lighting, and character appearances from the anchor.
Smoothly transition pose, position, and framing to match the new scene requirements."""

    # =========================================================================
    # OUTPUT
    # =========================================================================

    async def _save_outputs(self, output: CondensedPipelineOutput) -> None:
        """Save pipeline outputs to disk."""
        if not self.project_path:
            return

        output_dir = self.project_path / "pipeline_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save world config
        with open(output_dir / "world_config.json", 'w', encoding='utf-8') as f:
            json.dump(output.world_config, f, indent=2, ensure_ascii=False)

        # Save visual script
        with open(output_dir / "visual_script.md", 'w', encoding='utf-8') as f:
            f.write(output.visual_script)

        # Save prompts
        with open(output_dir / "frame_prompts.json", 'w', encoding='utf-8') as f:
            json.dump(output.frame_prompts, f, indent=2, ensure_ascii=False)

        # Save reference image manifest
        if output.character_references or output.location_references:
            refs_manifest = {
                "characters": {tag: str(path) for tag, path in output.character_references.items()},
                "locations": {tag: str(path) for tag, path in output.location_references.items()}
            }
            with open(output_dir / "references_manifest.json", 'w', encoding='utf-8') as f:
                json.dump(refs_manifest, f, indent=2, ensure_ascii=False)

        # Save frame images manifest
        if output.frame_images:
            frames_manifest = {fid: str(path) for fid, path in output.frame_images.items()}
            with open(output_dir / "frames_manifest.json", 'w', encoding='utf-8') as f:
                json.dump(frames_manifest, f, indent=2, ensure_ascii=False)

        # Save anchor frames info
        if output.anchor_frames:
            anchors_info = [
                {
                    "frame_id": a.frame_id,
                    "scene_number": a.scene_number,
                    "character_count": a.character_count,
                    "character_tags": a.character_tags,
                    "location_tag": a.location_tag,
                    "is_establishing": a.is_establishing,
                    "is_key_frame": a.is_key_frame,
                    "anchor_priority": a.anchor_priority,
                    "image_path": str(a.image_path) if a.image_path else None,
                    "continuity_validated": a.continuity_validated,
                    "correction_count": a.correction_count
                }
                for a in output.anchor_frames
            ]
            with open(output_dir / "anchor_frames.json", 'w', encoding='utf-8') as f:
                json.dump(anchors_info, f, indent=2, ensure_ascii=False)

        # Save pipeline stats
        stats = {
            "title": output.title,
            "total_frames": output.total_frames,
            "key_frames": output.key_frames,
            "images_generated": output.images_generated,
            "continuity_corrections": output.continuity_corrections,
            "execution_time_seconds": output.execution_time,
            "character_refs_count": len(output.character_references),
            "location_refs_count": len(output.location_references),
            "anchor_frames_count": len(output.anchor_frames)
        }
        with open(output_dir / "pipeline_stats.json", 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        logger.info(f"Outputs saved to {output_dir}")


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

async def run_condensed_pipeline(
    pitch: str,
    title: str = "",
    project_path: str = None,
    project_size: str = "short",
    visual_style: str = "live_action",
    generate_images: bool = True,
    image_model: str = "flux_2_pro",
    max_continuity_corrections: int = 1
) -> CondensedPipelineOutput:
    """
    Run the full condensed pipeline with image generation.

    Args:
        pitch: The story pitch text
        title: Optional title for the project
        project_path: Path to save outputs (creates directories if needed)
        project_size: Size of project - "micro" (3 scenes), "short" (8), "medium" (15)
        visual_style: Visual style - "live_action", "anime", "animation_2d", etc.
        generate_images: Whether to run image generation passes (default True)
        image_model: Image model to use (default "flux_2_pro")
        max_continuity_corrections: Max Gemini correction passes per key frame (default 1)

    Returns:
        CondensedPipelineOutput with all generated content and images

    Raises:
        RuntimeError: If pipeline fails
    """
    pipeline = CondensedVisualPipeline(
        project_path=Path(project_path) if project_path else None
    )

    input_data = CondensedPipelineInput(
        pitch=pitch,
        title=title,
        project_size=project_size,
        visual_style=visual_style,
        project_path=Path(project_path) if project_path else None,
        generate_images=generate_images,
        image_model=image_model,
        max_continuity_corrections=max_continuity_corrections
    )

    result = await pipeline.run(input_data)

    if result.status == PipelineStatus.COMPLETED:
        return result.output
    else:
        raise RuntimeError(f"Pipeline failed: {result.error}")
