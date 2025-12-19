# Plot Architecture Prompt

## Purpose
Analyzes a story pitch and creates a structured plot architecture with three-act structure and key plot points.

## System Prompt
You are a story structure analyst. Create clear, actionable plot architectures.

## Prompt Template

```
Analyze this story and create a plot architecture.

STORY:
{story_text}

GENRE: {genre}
TARGET SCENES: {target_scenes}

Create a structured plot breakdown with:

1. THREE-ACT STRUCTURE:
   - Act 1 (Setup, ~25%): Introduce world, characters, inciting incident
   - Act 2 (Confrontation, ~50%): Rising action, midpoint, complications
   - Act 3 (Resolution, ~25%): Climax, resolution, denouement

2. KEY PLOT POINTS (minimum 8):
   For each plot point, specify:
   - POINT_TYPE: [INCITING_INCIDENT|FIRST_PLOT_POINT|MIDPOINT|SECOND_PLOT_POINT|CLIMAX|RESOLUTION|PINCH_POINT|SUBPLOT]
   - ACT: [1|2|3]
   - POSITION: [0.0-1.0] (position within the story)
   - DESCRIPTION: What happens at this point
   - CHARACTERS: Which characters are involved (use [CHAR_NAME] format)
   - LOCATION: Where it happens (use [LOC_NAME] format)

Format each plot point as:
PLOT_POINT:
- TYPE: [type]
- ACT: [act]
- POSITION: [position]
- DESCRIPTION: [description]
- CHARACTERS: [character tags]
- LOCATION: [location tag]
```

## Variables
- `{story_text}`: The raw story pitch text
- `{genre}`: The story genre
- `{target_scenes}`: Number of target scenes based on project size

## Notes
- Plot points should be distributed across all three acts
- Each plot point should advance the story meaningfully
- Character and location tags should use proper notation: [CHAR_NAME], [LOC_NAME]

