# Character Reference Sheet Prompt

## Purpose
Generates a detailed multi-angle character reference sheet prompt from world_config.json data.
This is the "Generate Sheet" flow - no input image, purely from text description.

## Pipeline
`UnifiedReferenceScript.generate_character_sheet(tag)` → `ImageHandler.generate_character_sheet()`

## System Prompt
You are an expert at creating detailed image generation prompts for character reference sheets. Your prompts should be specific, visual, and optimized for AI image generation models like Seedream and FLUX.

## Prompt

```
Generate a detailed multi-angle CHARACTER REFERENCE SHEET prompt for:

TAG: [{tag}]
NAME: {name}
AGE: {age}
ETHNICITY: {ethnicity}

APPEARANCE:
{appearance}

COSTUME:
{costume}

WORLD STYLE: {world_style}

Create a comprehensive image generation prompt that includes:

1. LAYOUT: Professional character reference sheet with 6 views arranged in a grid
   - Top row: Front view (center), 3/4 left view, 3/4 right view
   - Bottom row: Profile left, Profile right, Back view

2. CHARACTER CONSISTENCY:
   - Identical character across all views
   - Same costume, hair, and accessories in every view
   - Neutral standing pose, arms slightly away from body
   - Neutral facial expression

3. VISUAL DETAILS:
   - {appearance}
   - {costume}

4. TECHNICAL REQUIREMENTS:
   - Clean white or light gray background
   - Professional reference sheet layout
   - Each view clearly separated
   - Full body visible in all views

Output ONLY the final prompt text, ready for image generation. No explanations or preamble.
```

## Variables
- `{tag}`: Character tag (e.g., CHAR_MEI)
- `{name}`: Character's full name
- `{age}`: Character's age
- `{ethnicity}`: Cultural/ethnic background
- `{appearance}`: Physical description (75-125 words)
- `{costume}`: Clothing and accessories (50-75 words)
- `{world_style}`: World style from ContextEngine.get_world_style()

## Character Context Fields (Visual Only)
These fields are extracted from world_config.json character profile:
- **name**: Character's full name
- **age**: Character's age
- **ethnicity**: Cultural/ethnic background
- **visual_appearance**: Physical description
- **costume**: Clothing and accessories

## Excluded Fields (Not Used for Visual Reference)
- emotional_tells (for script/roleplay only)
- physicality (for script/roleplay only)
- personality (for script/roleplay only)
- speech_style (for script/roleplay only)
- backstory (for script/roleplay only)

## Notes
- Uses Gemini 2.5 Flash for cost-efficient prompt generation
- Output is used with Seedream 4.5 for image generation
- Seedream requires blank first image at desired dimension (16:9 at 2K)

