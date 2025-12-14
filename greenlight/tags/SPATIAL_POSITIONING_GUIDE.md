# Spatial Positioning System - User Guide

## Overview

The Spatial Positioning System maintains **visual continuity** across shots by calculating where elements appear in frame based on:
- **Camera Direction**: Where the camera is facing (N, E, S, W)
- **Element Position**: Where elements are in world space (compass directions)
- **Spatial Relationships**: How elements relate to each other

## Core Formula

```python
# Calculate where an element appears in frame
frame_position = calculate_frame_position(
    element_compass_direction="N",  # Where element is in world
    camera_facing_direction="W",    # Where camera faces
    depth=0.5,                      # 0.0 = foreground, 1.0 = background
    vertical_offset=0.0             # -1.0 = bottom, 1.0 = top
)

# Result:
# frame_position.x = -1.0 (left side of frame)
# frame_position.y = 0.0 (middle height)
# frame_position.z = 0.5 (mid-depth)
# frame_position.screen_side = "left"
```

## Mathematical Formula

```
1. Get element compass angle (0-360°):
   N=0°, NE=45°, E=90°, SE=135°, S=180°, SW=225°, W=270°, NW=315°

2. Get camera facing angle (0-360°)

3. Calculate relative angle:
   relative_angle = (element_angle - camera_angle + 180) % 360

4. Convert to screen coordinates:
   x = sin(relative_angle)  # -1.0 (left) to 1.0 (right)
   
   Where:
   - 0° (ahead) → x = 0.0 (center)
   - 90° (right) → x = 1.0 (right edge)
   - 180° (behind) → x = 0.0 (center, but behind camera)
   - 270° (left) → x = -1.0 (left edge)
```

## Practical Examples

### Example 1: Door Position Changes with Camera

**Scenario**: A door is on the North wall. Where does it appear as camera rotates?

```python
from greenlight.tags import SpatialPositionCalculator

calc = SpatialPositionCalculator()

# Camera facing West - door is to the left
pos = calc.calculate_frame_position("N", "W")
# Result: x = -1.0 (left), screen_side = "left"

# Camera facing East - door is to the right
pos = calc.calculate_frame_position("N", "E")
# Result: x = 1.0 (right), screen_side = "right"

# Camera facing North - door is ahead (center)
pos = calc.calculate_frame_position("N", "N")
# Result: x = 0.0 (center), screen_side = "center"

# Camera facing South - door is behind camera
pos = calc.calculate_frame_position("N", "S")
# Result: x = 0.0 (center, but behind - low visibility)
```

### Example 2: Character Conversation (180° Rule)

**Scenario**: Two characters facing each other. Maintain screen positions across cuts.

```python
from greenlight.tags import ShotSpatialContext

# Shot 1: Camera facing East
shot1 = ShotSpatialContext(
    shot_id="S01F01",
    camera_direction="E",
    location_tag="LOC_ROOM"
)

# Character A at North, Character B at South
shot1.add_element("CHAR_ALICE", "character", "N")  # x = -0.7 (left)
shot1.add_element("CHAR_BOB", "character", "S")    # x = 0.7 (right)

# Shot 2: Camera facing West (WRONG - violates 180° rule)
shot2_wrong = ShotSpatialContext(
    shot_id="S01F02",
    camera_direction="W",
    location_tag="LOC_ROOM"
)
shot2_wrong.add_element("CHAR_ALICE", "character", "N")  # x = 0.7 (RIGHT - FLIPPED!)
shot2_wrong.add_element("CHAR_BOB", "character", "S")    # x = -0.7 (LEFT - FLIPPED!)

# Shot 2: Camera facing North (CORRECT - maintains positions)
shot2_correct = ShotSpatialContext(
    shot_id="S01F02",
    camera_direction="N",
    location_tag="LOC_ROOM"
)
shot2_correct.add_element("CHAR_ALICE", "character", "N")  # x = 0.0 (center)
shot2_correct.add_element("CHAR_BOB", "character", "S")    # x = 0.0 (center)
# Alice still left of Bob in relative terms
```

### Example 3: Validate Continuity

```python
from greenlight.tags import SpatialContinuityValidator

validator = SpatialContinuityValidator()
validator.add_shot_context(shot1)
validator.add_shot_context(shot2_correct)

# Check 180° rule
is_valid, explanation = validator.validate_180_rule(
    shot1, shot2_correct, "CHAR_ALICE", "CHAR_BOB"
)
print(f"Valid: {is_valid}")
print(f"Explanation: {explanation}")

# Get suggested camera directions for next shot
valid_directions = validator.suggest_camera_direction(
    shot1, "CHAR_ALICE", "CHAR_BOB"
)
print(f"Valid camera directions: {valid_directions}")
# Output: ['N', 'S'] (East and West would violate 180° rule)
```

## Integration with Story Pipeline

The spatial positioning system integrates with beat generation:

```python
# In beat content, specify spatial information:
beat_content = """
[CHAR_MEI] enters from [LOC_BROTHEL_COURTYARD_DIR_N].
Camera facing West.
[CHAR_MEI] compass position: N
[CHAR_LIN] compass position: S
[PROP_TEA_SET] compass position: E
"""

# System calculates:
# - MEI appears on left (x = -1.0)
# - LIN appears on right (x = 1.0)
# - TEA_SET appears on right (x = 1.0)
```

## Best Practices

1. **Always specify camera direction** for each shot
2. **Use compass positions** for all elements (N, NE, E, SE, S, SW, W, NW)
3. **Validate 180° rule** when cutting between characters
4. **Track movement direction** for action sequences
5. **Use directional location tags** (`LOC_NAME_DIR_N/E/S/W`) to specify camera view

## Common Patterns

### Pattern 1: Establishing Shot → Close-up
```
Shot 1: Wide shot, camera facing N
- Shows full room layout
- All elements positioned

Shot 2: Close-up, camera facing same direction (N)
- Maintains spatial relationships
- Focuses on specific element
```

### Pattern 2: Over-the-Shoulder Conversation
```
Shot 1: OTS of Alice, camera facing E
- Alice at N (left), Bob at S (right)

Shot 2: OTS of Bob, camera facing W
- WRONG: Flips positions

Shot 2 (correct): OTS of Bob, camera facing N or S
- Maintains left/right relationship
```

### Pattern 3: Chase Sequence
```
All shots maintain same screen direction:
- Pursuer always on left
- Pursued always on right
- Camera tracks movement direction
```

