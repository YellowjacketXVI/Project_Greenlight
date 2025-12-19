# Frame Prompt Generation Prompt

## Purpose
Writes visual prompts for storyboard image generation with explicit tag notation.

## System Prompt
You are a visual prompt writer for cinematic storyboarding. Always use explicit [TAG] notation for all characters, locations, and props.

## Prompt Template

```
Write frame prompts for this marked scene with EXPLICIT TAG NOTATION.

MARKED SCENE:
{marked_text}

VISUAL STYLE:
{visual_style}

AVAILABLE TAGS (USE THESE EXACTLY IN YOUR PROMPTS):

CHARACTERS:
{character_tags}

LOCATIONS:
{location_tags}

PROPS:
{prop_tags}

For each frame marked with (/scene_frame_chunk_start/) and (/scene_frame_chunk_end/):

1. Write a visual prompt (max 250 words) that:
   - Describes the visual composition
   - Uses EXACT tag notation: [CHAR_NAME], [LOC_NAME], [PROP_NAME]
   - Includes camera angle and framing
   - Describes lighting and mood
   - Captures the emotional beat

2. Format each frame as:
   [{scene}.{frame}.cA] (Shot Type)
   PROMPT: [your visual prompt here]
   TAGS: [list of tags used]
   LOCATION_DIRECTION: [N|E|S|W if applicable]

CRITICAL RULES:
- Use EXACT tags from the available lists above
- Every character mentioned must use [CHAR_*] notation
- Every location must use [LOC_*] notation
- Every prop must use [PROP_*] notation
- Maximum 250 words per prompt
- Include shot type in the frame header
```

## Variables
- `{marked_text}`: Scene text with frame markers inserted
- `{visual_style}`: Visual style description
- `{character_tags}`: List of available character tags
- `{location_tags}`: List of available location tags
- `{prop_tags}`: List of available prop tags

## Output Format
Each frame should include:
- Frame ID: `[{scene}.{frame}.cA]`
- Shot type: `(Wide)`, `(Medium)`, `(Close-up)`, etc.
- PROMPT: Visual description (max 250 words)
- TAGS: List of tags used in the prompt
- LOCATION_DIRECTION: Directional view if applicable

## Notes
- Prompts are saved to storyboard/prompts.json for user editing
- Style suffix is appended during image generation
- Tags must match exactly for reference image injection

