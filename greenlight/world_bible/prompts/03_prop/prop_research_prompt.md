# Prop Research Prompt

## Purpose
Research a prop from a specific perspective (physical, historical, symbolic, functional).

## System Prompt
You are a prop researcher focusing on {focus}. All output must be period-accurate.

## Prompt Template

```
Research the following prop from a {focus} perspective.

PROP TAG: {tag}

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
- `{focus}`: Research focus (physical, historical, symbolic, functional)
- `{tag}`: Prop tag (e.g., [PROP_SWORD])
- `{world_context}`: World configuration context
- `{visual_style}`: Visual style description
- `{style_notes_section}`: Optional style notes
- `{pitch}`: Story pitch text
- `{focus_description}`: Description of the research focus
- `{focus_instructions}`: Specific instructions for this focus

## Research Focuses

### Physical Focus
- Materials, dimensions, condition
- Craftsmanship, visual details
- Weight, texture, color

### Historical Focus
- Period-accurate details
- Origin, provenance
- Cultural context

### Symbolic Focus
- Meaning, significance
- Narrative importance
- Character associations

### Functional Focus
- How it's used
- Who uses it
- When it appears in story

## Notes
- Props are important objects, weapons, tools, vehicles
- Symbolic items get extra attention
- Results feed into reference image generation

