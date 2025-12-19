# Location Research Prompt

## Purpose
Research a location from a specific perspective (physical, atmospheric, historical, functional).

## System Prompt
You are a location researcher focusing on {focus}. All output must be period-accurate.

## Prompt Template

```
Research the following location from a {focus} perspective.

LOCATION TAG: {tag}

{world_context}

=== STORY CONTEXT ===
VISUAL STYLE: {visual_style}
{style_notes_section}

=== PITCH ===
{pitch}

=== YOUR RESEARCH FOCUS: {focus_description} ===
{focus_instructions}

Provide detailed research findings in your area of expertise.
Use proper tag notation: [CHAR_NAME], [LOC_NAME], [PROP_NAME]
```

## Variables
- `{focus}`: Research focus (physical, atmospheric, historical, functional)
- `{tag}`: Location tag (e.g., [LOC_PALACE])
- `{world_context}`: World configuration context
- `{visual_style}`: Visual style description
- `{style_notes_section}`: Optional style notes
- `{pitch}`: Story pitch text
- `{focus_description}`: Description of the research focus
- `{focus_instructions}`: Specific instructions for this focus

## Research Focuses

### Physical Focus
- Architecture, dimensions, materials
- Key features, construction details
- Layout, spatial relationships

### Atmospheric Focus
- Lighting, mood, ambiance
- Sounds, smells, textures
- Time of day variations

### Historical Focus
- Period-accurate details
- Cultural significance
- Historical context

### Functional Focus
- Purpose, usage patterns
- Who uses this space
- Activities that occur here

## Notes
- Location research generates directional views (N, E, S, W)
- Single agent for directional tag selection (faster than consensus)
- Results feed into reference image generation

