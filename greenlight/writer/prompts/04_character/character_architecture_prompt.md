# Character Architecture Prompt

## Purpose
Analyzes characters in a story and creates rich character profiles with arcs, motivations, and visual descriptions.

## System Prompt
You are a character development specialist. Create deep, meaningful character arcs.

## Prompt Template

```
Analyze the characters in this story and create RICH CHARACTER PROFILES (125-250 words each).

STORY:
{story_text}

VISUAL STYLE: {visual_style}
STYLE NOTES: {style_notes}

IDENTIFIED CHARACTERS: {character_tags}

For each character, provide DETAILED multi-paragraph descriptions:

1. CHARACTER TAG: [CHAR_NAME] format
2. CHARACTER NAME: Full name
3. ROLE: [protagonist|antagonist|supporting|minor]
4. AGE: Specific age or range
5. ETHNICITY: Cultural/ethnic background

6. APPEARANCE (75-125 words):
   - Physical build, height, distinctive features
   - Hair color, style, texture
   - Eye color, facial features
   - Skin tone, complexion
   - Any scars, tattoos, or unique marks

7. COSTUME (50-75 words):
   - Primary outfit/wardrobe
   - Accessories, jewelry
   - Style aesthetic
   - Color palette

8. PHYSICALITY (25-50 words):
   - How they move, posture
   - Gestures, mannerisms
   - Physical presence

9. WANT: What they consciously desire
10. NEED: What they actually need (often different from want)
11. FLAW: Their primary character flaw
12. ARC: How they change through the story

Format each character as:
CHARACTER: [CHAR_TAG]
NAME: [full name]
ROLE: [role]
...
```

## Variables
- `{story_text}`: The raw story pitch text
- `{visual_style}`: Visual style (live_action, anime, etc.)
- `{style_notes}`: Custom style instructions
- `{character_tags}`: List of identified character tags

## Notes
- Visual fields (age, ethnicity, appearance, costume) are used for reference image generation
- Emotional_tells and physicality are for script/roleplay, not visual reference
- Character tags must use [CHAR_NAME] notation

