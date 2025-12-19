# World Overview Prompt

## Purpose
Analyzes a story pitch and generates a comprehensive world overview including logline, synopsis, themes, world rules, lighting, and vibe.

## System Prompt
You are a world-building expert. Create rich, cohesive world overviews that establish tone and rules.

## Prompt Template

```
Analyze this story pitch and generate a comprehensive world overview.

PITCH:
{story_text}

GENRE: {genre}
VISUAL STYLE: {visual_style}
STYLE NOTES: {style_notes}

Generate the following sections:

1. LOGLINE (1 sentence):
   A compelling one-sentence summary of the story.

2. SYNOPSIS (2-3 paragraphs):
   An expanded summary covering the main plot, characters, and stakes.

3. THEMES (3-5 themes):
   Core themes explored in the story, each with a brief explanation.

4. WORLD_RULES (if applicable):
   Any special rules, magic systems, technology, or world-specific mechanics.

5. LIGHTING:
   Describe the overall lighting style for the project.
   Examples: "Chiaroscuro with low-key, volumetric lighting", "Bright, high-key naturalistic lighting"

6. VIBE (3-5 words):
   Overall mood/atmosphere of the project.
   Examples: "Intimate, Poetic, Subversive, Elegant, Atmospheric"

Format your response as:
LOGLINE: [logline]

SYNOPSIS:
[synopsis]

THEMES:
- [theme 1]: [explanation]
- [theme 2]: [explanation]
...

WORLD_RULES:
[rules or "N/A"]

LIGHTING: [lighting description]

VIBE: [3-5 mood words]
```

## Variables
- `{story_text}`: The raw story pitch text
- `{genre}`: The story genre
- `{visual_style}`: Visual style (live_action, anime, animation_2d, animation_3d, mixed_reality)
- `{style_notes}`: Custom style instructions from user

## Notes
- Lighting and vibe are saved to world_config.json for style suffix generation
- Visual style is mapped to descriptive text (e.g., "live_action" → "photorealistic live-action cinematography")
- Do NOT reference specific studios (Pixar, Disney, etc.) - use technical descriptors only

