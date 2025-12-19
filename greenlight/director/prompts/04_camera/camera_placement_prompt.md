# Camera Placement Prompt

## Purpose
Adds camera, position, and lighting notations to frames using scene.frame.camera format.

## System Prompt
You are a cinematographer adding technical notations using scene.frame.camera format.

## Prompt Template

```
Add camera and placement notations to this frame.

FRAME NOTATION: [{camera_id}]
SCENE: {scene_number}
FRAME: {frame_number}

EXISTING PROMPT:
{frame_prompt}

WORLD CONFIG LOCATIONS:
{location_info}

Add the following notations using scene.frame.camera format [{camera_id}]:

1. [CAM: ...] - Camera instruction
   Include: Shot type, angle, movement, lens suggestion
   Examples:
   - [CAM: Wide establishing shot, high angle, static, 24mm]
   - [CAM: Medium close-up, eye level, slow push in, 50mm]
   - [CAM: Over-the-shoulder, slight low angle, handheld, 35mm]

2. [POS: ...] - Character/element positions
   Include: Who is where in frame
   Examples:
   - [POS: CHAR_PROTAGONIST center, CHAR_ALLY screen right]
   - [POS: CHAR_VILLAIN foreground left, PROP_SWORD on table]

3. [LIGHT: ...] - Lighting setup
   Include: Key light, mood, practical sources
   Examples:
   - [LIGHT: Chiaroscuro, key from window, fill from candles]
   - [LIGHT: High-key naturalistic, soft diffused daylight]

Respond with the three notations:
[CAM: ...]
[POS: ...]
[LIGHT: ...]
```

## Variables
- `{camera_id}`: Full camera ID (e.g., "1.2.cA")
- `{scene_number}`: Scene number
- `{frame_number}`: Frame number
- `{frame_prompt}`: Existing frame prompt
- `{location_info}`: Location information from world_config

## Notation Format
- Camera: `[CAM: {instruction}]`
- Position: `[POS: {positions}]`
- Lighting: `[LIGHT: {lighting}]`

## Notes
- Uses scene.frame.camera notation throughout
- Character tags must use [CHAR_NAME] format
- Location tags must use [LOC_NAME] format

