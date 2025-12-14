"""
Greenlight Agent Prompts

Centralized prompt templates for all agents in the system.
This is the canonical source for all agent prompts.
"""

from dataclasses import dataclass
from typing import Dict, Optional
from pathlib import Path


@dataclass
class AgentPrompt:
    """A prompt template for an agent."""
    name: str
    template: str
    description: str = ""


class AgentPromptLibrary:
    """
    Library of all agent prompts.
    
    Provides centralized access to prompt templates for:
    - Tag Validation Agents (5 perspectives)
    - Story Building Engine
    - Director Pipeline
    - Quality Check Agents
    - Location Directional Views
    """
    
    # ==========================================================================
    # TAG VALIDATION AGENT PROMPTS
    # ==========================================================================

    # Shared naming rules for all tag extraction agents
    TAG_NAMING_RULES = """
## TAG NAMING RULES (MANDATORY - ALL 5 AGENTS MUST AGREE)

You MUST follow these EXACT naming conventions. Tags that don't follow these rules will be REJECTED.

### Characters (CHAR_ prefix REQUIRED):
- Format: `[CHAR_FIRSTNAME]` or `[CHAR_FIRSTNAME_LASTNAME]`
- Examples: `[CHAR_PROTAGONIST]`, `[CHAR_ALLY]`, `[CHAR_JOHN_SMITH]`
- For titled characters: `[CHAR_THE_CAPTAIN]`, `[CHAR_THE_KING]`
- For unnamed roles: `[CHAR_GUARD_01]`, `[CHAR_SERVANT_01]`
- ALWAYS use CHAR_ prefix - never just the name alone

### Locations (LOC_ prefix REQUIRED):
- Format: `[LOC_SPECIFIC_PLACE_NAME]`
- Examples: `[LOC_MAIN_STREET]`, `[LOC_TOWN_SQUARE]`, `[LOC_ROYAL_PALACE]`
- Be specific: `[LOC_HERO_BEDROOM]` not `[LOC_BEDROOM]`
- Include establishment type: `[LOC_CORNER_CAFE]`, `[LOC_HARBOR_DOCKS]`

### Props (PROP_ prefix REQUIRED):
- Format: `[PROP_DESCRIPTIVE_ITEM_NAME]`
- Examples: `[PROP_ANCIENT_MAP]`, `[PROP_BLUE_CLOAK]`, `[PROP_SILVER_RING]`
- Be specific with colors/materials: `[PROP_BRONZE_DAGGER]`, `[PROP_RED_LANTERN]`

### Concepts (CONCEPT_ prefix REQUIRED):
- Format: `[CONCEPT_THEME_NAME]`
- Examples: `[CONCEPT_FREEDOM]`, `[CONCEPT_HONOR]`, `[CONCEPT_FORBIDDEN_LOVE]`

### Events (EVENT_ prefix REQUIRED):
- Format: `[EVENT_SPECIFIC_OCCURRENCE]`
- Examples: `[EVENT_WEDDING_CEREMONY]`, `[EVENT_ESCAPE_ATTEMPT]`, `[EVENT_FINAL_BATTLE]`

**CRITICAL RULES**:
1. ALL tags MUST have their category prefix (CHAR_, LOC_, PROP_, CONCEPT_, EVENT_)
2. ALL tags MUST be UPPERCASE with underscores for spaces
3. ALL tags MUST be wrapped in square brackets [TAG]
4. Be CONSISTENT - use the EXACT same tag format every time you reference an element
"""

    TAG_STORY_CRITICAL = """Analyze the following text and identify subjects that directly impact the plot or story outcome.

{naming_rules}

Extract ALL story-critical elements as tags:
- Characters: Use CHAR_ prefix (e.g., [CHAR_PROTAGONIST], [CHAR_THE_CAPTAIN])
- Locations: Use LOC_ prefix (e.g., [LOC_PALACE], [LOC_TOWN_SQUARE])
- Props: Use PROP_ prefix (e.g., [PROP_SWORD], [PROP_LETTER])
- Events: Use EVENT_ prefix (e.g., [EVENT_BATTLE], [EVENT_WEDDING])

**Source Text:**
{source_text}

**Output your tags, one per line (MUST include proper prefix):**"""

    TAG_LANDMARK_LOCATIONS = """Analyze the following text and identify locations that are significant settings or landmarks.

{naming_rules}

Focus on extracting LOCATION tags with LOC_ prefix for all places mentioned or implied.
Also extract any characters (CHAR_ prefix) and props (PROP_ prefix) associated with these locations.

**Source Text:**
{source_text}

**Output your tags, one per line (MUST include proper prefix):**"""

    TAG_CHARACTER_DEFINING = """Analyze the following text and identify all characters mentioned or implied.

{naming_rules}

Focus on extracting CHARACTER tags with CHAR_ prefix for all people, named or unnamed:
- Named characters: [CHAR_PROTAGONIST], [CHAR_ALLY], [CHAR_JOHN]
- Titled characters: [CHAR_THE_CAPTAIN], [CHAR_THE_KING]
- Unnamed roles: [CHAR_GUARD_01], [CHAR_SERVANT_01]

Also extract props (PROP_ prefix) and locations (LOC_ prefix) closely associated with each character.

**Source Text:**
{source_text}

**Output your tags, one per line (MUST include proper prefix):**"""

    TAG_WORLD_BUILDING = """Analyze the following text and identify elements that establish the world's rules, culture, or history.

{naming_rules}

Focus on extracting:
- CONCEPT tags (CONCEPT_ prefix) for themes, cultural elements, abstract ideas
- LOC tags (LOC_ prefix) for world-defining locations
- PROP tags (PROP_ prefix) for culturally significant objects
- CHAR tags (CHAR_ prefix) for characters that embody world elements

**Source Text:**
{source_text}

**Output your tags, one per line (MUST include proper prefix):**"""

    TAG_VISUAL_ANCHORS = """Analyze the following text and identify visual elements that will appear repeatedly in storyboards.

{naming_rules}

Focus on extracting:
- PROP tags (PROP_ prefix) for objects, costumes, visual elements
- CHAR tags (CHAR_ prefix) for characters with strong visual presence
- LOC tags (LOC_ prefix) for visually distinctive locations

**Source Text:**
{source_text}

**Output your tags, one per line (MUST include proper prefix):**"""

    TAG_CLASSIFICATION = """Classify the following tag into one of the specified categories: CHARACTER, LOCATION, PROP, CONCEPT, EVENT. Provide only the category name as the output.

**Tag:** `{tag_name}`

**Categories:**
- **CHARACTER:** People or sentient beings (CHAR_ prefix, e.g., CHAR_PROTAGONIST, CHAR_THE_CAPTAIN)
- **LOCATION:** Places (LOC_ prefix, e.g., LOC_PALACE, LOC_TOWN_SQUARE)
- **PROP:** Objects (PROP_ prefix, e.g., PROP_SWORD, PROP_CLOAK)
- **CONCEPT:** Abstract ideas or themes (CONCEPT_ prefix, e.g., CONCEPT_HONOR)
- **EVENT:** Significant occurrences (EVENT_ prefix, e.g., EVENT_WEDDING)"""

    # ==========================================================================
    # STORY BUILDING ENGINE PROMPTS
    # ==========================================================================
    
    PITCH_ANALYSIS = """Analyze the following pitch to extract the core narrative elements. Present the output in JSON format.

**Pitch:**
{pitch}

**JSON Output Structure:**
{{
  "protagonist": "",
  "goal": "",
  "antagonist": "",
  "conflict": "",
  "beats": [],
  "themes": [],
  "setting": ""
}}"""

    PROSE_GENERATION = """Write engaging prose for the following story sequence (500-800 words). Advance the plot, develop characters, and maintain continuity.

**Sequence {num}: {title}**
**Act:** {act}
**Description:** {description}

**Context:**
{previous_sequence_prose}
{character_arc_moments}
{plot_point_info}"""

    # ==========================================================================
    # DIRECTOR PIPELINE PROMPTS
    # ==========================================================================
    
    FRAME_COMPOSER = """Analyze the following scene and break it down into 3-7 key visual frames. For each frame, specify the action, narrative moment, and characters in the frame. Output in JSON format.

**Scene:** {scene_id} - {title}
**Location_Direction:** {location_direction}
**Characters:** {characters}

**Narrative Content:**
{narrative_content}

**JSON Output Structure:**
{{
  "frames": [
    {{
      "action": "Description of what's happening",
      "moment": "Narrative moment (e.g., revelation, conflict, transition)",
      "characters": ["CHAR1", "CHAR2"]
    }}
  ]
}}"""

    CAMERA_EVALUATOR = """Evaluate 3-5 camera shot options for this frame. For each option, specify the shot type, size, movement, composition, and reasoning. Output in JSON format.

**Scene:** {scene_id} - {title}
**Frame:** {frame_id}
**Action:** {action}
**Moment:** {moment}
**Characters:** {characters}

**Camera Shot Library (Use Cases):**
{library_use_cases}

**JSON Output Structure:**
{{
  "options": [
    {{
      "shot_type": "...",
      "shot_size": "...",
      "camera_movement": "...",
      "composition": "...",
      "reasoning": "..."
    }}
  ]
}}"""

    SHOT_DIRECTOR = """Craft detailed cinematic direction for this shot. Provide character blocking, expressions, lighting, atmosphere, tags, and a full storyboard prompt (200-300 words). Be specific and use concrete visual descriptions. Output in JSON format.

**Notation:** {notation}
**Scene:** {scene_id} - {title}
**Frame:** {frame_id} - {action}
**Moment:** {moment}

**Camera Shot:**
- Type: {shot_type}
- Size: {shot_size}
- Movement: {camera_movement}
- Composition: {composition}

**Characters in Frame:** {characters}
**Location:** {location}

**Style Context:**
{style_context}

**JSON Output Structure:**
{{
  "character_blocking": "...",
  "character_expressions": "...",
  "lighting": "...",
  "atmosphere": "...",
  "tags": ["TAG1", "TAG2"],
  "full_prompt": "..."
}}"""

    # ==========================================================================
    # LOCATION DIRECTIONAL VIEW PROMPTS
    # ==========================================================================

    LOCATION_NORTH_VIEW = """You are a world-building expert. Based on the location name and its core description, generate a detailed visual description of the scene when looking **North**. Establish at least 3-5 distinct landmarks or features and their relative positions (e.g., "To the left, a broken statue stands..."; "In the distance, a jagged mountain..."; "Directly ahead, the main gate..."). This description will be the single source of truth for generating all other views.

**Location Name:** {location_name}
**Core Description:** {base_description}

**Output a detailed description for the North view:**"""

    LOCATION_EAST_VIEW = """You are a world-building expert. Your task is to describe the **East** view of a location, maintaining strict spatial consistency with the provided North view. Imagine standing in the same spot and turning 90 degrees to the right.

- Elements that were on the **right** in the North view should now be **in front** of you.
- Elements that were **in front** in the North view should now be on your **left**.
- Describe new elements that are now visible on your **right** (which were previously behind you).

**Location Name:** {location_name}
**Core Description:** {base_description}

**Authoritative North View Description (Reference):**
{north_view_description}

**Based on the North view, output a detailed and consistent description for the East view:**"""

    LOCATION_SOUTH_VIEW = """You are a world-building expert. Your task is to describe the **South** view of a location, maintaining strict spatial consistency with the provided North view. Imagine standing in the same spot and turning 180 degrees.

- The view is the direct opposite of the North view.
- Elements that were in the **background** of the North view may now be in the **foreground** if you walked through the scene, or completely gone if you only turned around. Assume you have only turned around.
- Describe the new scene that was previously behind you in the North view.

**Location Name:** {location_name}
**Core Description:** {base_description}

**Authoritative North View Description (Reference):**
{north_view_description}

**Based on the North view, output a detailed and consistent description for the South view:**"""

    LOCATION_WEST_VIEW = """You are a world-building expert. Your task is to describe the **West** view of a location, maintaining strict spatial consistency with the provided North view. Imagine standing in the same spot and turning 90 degrees to the left.

- Elements that were on the **left** in the North view should now be **in front** of you.
- Elements that were **in front** in the North view should now be on your **right**.
- Describe new elements that are now visible on your **left** (which were previously behind you).

**Location Name:** {location_name}
**Core Description:** {base_description}

**Authoritative North View Description (Reference):**
{north_view_description}

**Based on the North view, output a detailed and consistent description for the West view:**"""

    @classmethod
    def get_tag_validation_prompts(cls) -> Dict[str, str]:
        """Get all tag validation agent prompts (5 perspectives)."""
        return {
            "story_critical": cls.TAG_STORY_CRITICAL,
            "landmark_locations": cls.TAG_LANDMARK_LOCATIONS,
            "character_defining": cls.TAG_CHARACTER_DEFINING,
            "world_building": cls.TAG_WORLD_BUILDING,
            "visual_anchors": cls.TAG_VISUAL_ANCHORS,
            "classification": cls.TAG_CLASSIFICATION,
        }

    @classmethod
    def get_story_prompts(cls) -> Dict[str, str]:
        """Get all story building prompts."""
        return {
            "pitch_analysis": cls.PITCH_ANALYSIS,
            "prose_generation": cls.PROSE_GENERATION,
        }

    @classmethod
    def get_director_prompts(cls) -> Dict[str, str]:
        """Get all director pipeline prompts."""
        return {
            "frame_composer": cls.FRAME_COMPOSER,
            "camera_evaluator": cls.CAMERA_EVALUATOR,
            "shot_director": cls.SHOT_DIRECTOR,
        }

    @classmethod
    def get_location_prompts(cls) -> Dict[str, str]:
        """Get all location directional view prompts."""
        return {
            "north": cls.LOCATION_NORTH_VIEW,
            "east": cls.LOCATION_EAST_VIEW,
            "south": cls.LOCATION_SOUTH_VIEW,
            "west": cls.LOCATION_WEST_VIEW,
        }

    @classmethod
    def render(cls, template: str, **kwargs) -> str:
        """Render a prompt template with variables."""
        return template.format(**kwargs)

