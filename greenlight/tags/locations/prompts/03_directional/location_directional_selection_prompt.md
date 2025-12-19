# Location Directional Selection - Single Agent

## Description
Selects the appropriate directional tag for a location based on scene context.
Uses single-agent selection (not consensus) for speed and consistency.

## Variables
- `{beat_content}`: The beat content text
- `{location_tag}`: Base location tag (e.g., LOC_BROTHEL)
- `{direction_text}`: Direction description from scene
- `{directional_views}`: World bible directional views for this location
- `{scene_context}`: Optional scene context
- `{TAG_NAMING_RULES}`: Tag naming rules (injected from AgentPromptLibrary)

## Prompt
```
Select the correct directional location tag.

{TAG_NAMING_RULES}

## DIRECTIONAL TAG RULES
1. Format: [LOC_NAME_DIR_X] where X is N, E, S, or W
2. Direction indicates where camera is FACING
3. Tags are literal identifiers, NOT placeholders
4. Examples: [LOC_BROTHEL_DIR_N], [LOC_PALACE_DIR_W]

## Beat Content
{beat_content}

## Base Location
{location_tag}

## Direction Information
{direction_text}

## World Bible Directional Views
{directional_views}

## Scene Context
{scene_context}

## Output Format
DIRECTIONAL_TAG: [LOC_..._DIR_X]
CONFIDENCE: [0.0-1.0]
REASONING: [brief explanation of why this direction was selected]
```

## Notes
- Single-agent selection is used because consensus failed to produce better output
- Direction indicates camera facing direction, not character facing direction
- Cross-reference with world bible directional views for accuracy

