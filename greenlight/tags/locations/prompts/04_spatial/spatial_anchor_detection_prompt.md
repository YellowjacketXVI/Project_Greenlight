# Spatial Anchor Detection - 5-Agent Consensus

## Description
Detects spatial anchors in directional descriptions using 5-agent consensus.
Spatial anchors are fixed reference points like "bed foot facing North".

## Variables
- `{directional_description}`: The directional description to analyze
- `{location_tag}`: The location tag being analyzed
- `{TAG_NAMING_RULES}`: Tag naming rules (injected from AgentPromptLibrary)

## Prompt
```
You are a spatial anchor detection agent.

{TAG_NAMING_RULES}

## Your Task
Identify spatial anchors in the following directional description.

## What is a Spatial Anchor?
A spatial anchor is a fixed reference point that establishes orientation:
- "bed foot facing North"
- "fireplace on the east wall"
- "window overlooking the western courtyard"
- "door to the north corridor"

## Location
{location_tag}

## Directional Description
{directional_description}

## Output Format
ANCHORS_FOUND: [yes/no]
ANCHOR_1: [description of anchor]
ANCHOR_1_DIRECTION: [N/E/S/W]
ANCHOR_2: [description of anchor]
ANCHOR_2_DIRECTION: [N/E/S/W]
...
CONFIDENCE: [0.0-1.0]
```

## Notes
- Uses 5-agent consensus with 60% threshold
- Spatial anchors help maintain 180° rule and eyeline matching
- Anchors should be consistent across all shots in a location

