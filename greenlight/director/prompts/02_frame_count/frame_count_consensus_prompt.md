# Frame Count Consensus Prompt

## Purpose
Determines the optimal frame count for a scene using 3-judge consensus.

## System Prompt
You are a director determining frame counts. Respond with only a number.

## Prompt Template

```
Determine the optimal frame count for this scene.

SCENE:
{scene_text}

SCENE NUMBER: {scene_num}
MEDIA TYPE: {media_type}

Consider:
- Key narrative moments that need visual capture
- Character moments requiring close-ups
- Establishing shots needed
- Transitions and movements
- Emotional turning points
- Scene complexity and pacing needs

Respond with ONLY a single number representing the optimal frame count.
No explanation needed.
```

## Variables
- `{scene_text}`: The full scene text
- `{scene_num}`: Scene number
- `{media_type}`: Media type (standard, short, feature)

## Consensus Configuration
- 3 judges vote independently
- Best of 3 (median) is selected
- No artificial limits - LLM determines optimal count
- Minimum 1 frame per scene

## Notes
- Frame count is determined autonomously by LLM consensus
- No hardcoded limits or UI controls
- Each judge responds with only a number

