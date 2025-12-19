# Character Research Prompt

## Purpose
Research a character from a specific perspective (visual, psychological, historical, narrative).

## System Prompt
You are a character researcher focusing on {focus}. All output must be period-accurate.

## Prompt Template

```
Research the following character from a {focus} perspective.

CHARACTER TAG: {tag}

{world_context}

=== STORY CONTEXT ===
GENRE: {genre}
VISUAL STYLE: {visual_style}
{style_notes_section}
THEMES: {themes}

=== PITCH ===
{pitch}

=== YOUR RESEARCH FOCUS: {focus_description} ===
{focus_instructions}

Provide detailed research findings in your area of expertise.
Use proper tag notation: [CHAR_NAME], [LOC_NAME], [PROP_NAME]
```

## Variables
- `{focus}`: Research focus (visual, psychological, historical, narrative)
- `{tag}`: Character tag (e.g., [CHAR_PROTAGONIST])
- `{world_context}`: World configuration context
- `{genre}`: Story genre
- `{visual_style}`: Visual style description
- `{style_notes_section}`: Optional style notes
- `{themes}`: Story themes
- `{pitch}`: Story pitch text
- `{focus_description}`: Description of the research focus
- `{focus_instructions}`: Specific instructions for this focus

## Research Focuses

### Visual Focus
- Physical appearance, costume, props
- Color palette, textures, materials
- Distinctive visual markers

### Psychological Focus
- Motivations, fears, desires
- Personality traits, quirks
- Internal conflicts

### Historical Focus
- Period-accurate details
- Cultural context
- Social status markers

### Narrative Focus
- Character arc, transformation
- Relationships, conflicts
- Role in story structure

## Notes
- Multiple research agents run in parallel with different focuses
- Results are synthesized by a judge panel
- All output must be period-accurate to the story setting

