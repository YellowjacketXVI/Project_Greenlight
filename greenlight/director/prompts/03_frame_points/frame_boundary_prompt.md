# Frame Boundary Determination Prompt

## Purpose
Identifies frame boundaries within a scene using collaborative iteration.

## System Prompt (Iteration 1)
You are a collaborative frame marker identifying frame boundaries.

## System Prompt (Iteration 2)
You are a collaborative frame marker refining frame boundaries.

## Prompt Template

```
Identify {frame_count} frame boundaries in this scene.

SCENE:
{scene_text}

{other_proposals}

For each frame, identify:
1. START: The exact text where the frame begins
2. END: The exact text where the frame ends
3. CAPTURES: What this frame visually captures

Format each frame as:
FRAME 1:
  START: "[exact starting text]"
  END: "[exact ending text]"
  CAPTURES: [what this frame shows]

FRAME 2:
  START: "[exact starting text]"
  END: "[exact ending text]"
  CAPTURES: [what this frame shows]

...

CRITICAL:
- Frames must cover the entire scene without gaps
- Each frame should capture a distinct visual moment
- START and END must be exact quotes from the scene text
```

## Variables
- `{frame_count}`: Number of frames to identify
- `{scene_text}`: The full scene text
- `{other_proposals}`: (Iteration 2 only) Previous agent's proposals

## Iteration Process
1. First agent identifies boundaries independently
2. Second agent refines based on first agent's proposals
3. Final boundaries are parsed from second response

## Notes
- Uses 2-iteration collaboration pattern
- Boundaries must be exact text quotes for parsing
- Each frame should capture a distinct visual moment

