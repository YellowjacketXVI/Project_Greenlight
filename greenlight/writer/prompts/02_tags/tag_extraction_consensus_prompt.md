# Tag Extraction Consensus Prompt

## Purpose
Extracts character, location, and prop tags from story content using multi-agent consensus.

## System Prompt
You are a tag extraction specialist. Extract character, location, and prop tags from story content.

## Prompt Template

```
{TAG_NAMING_RULES}

Extract all tags from the following story content.

STORY CONTENT:
{story_text}

Identify and extract:

1. CHARACTER TAGS [CHAR_*]:
   - Main characters (protagonists, antagonists)
   - Supporting characters
   - Minor characters with names
   - Groups or organizations (if named)

2. LOCATION TAGS [LOC_*]:
   - Named locations
   - Distinct settings
   - Recurring places

3. PROP TAGS [PROP_*]:
   - Important objects
   - Weapons, tools, vehicles
   - Symbolic items

Format your response as:
CHARACTERS:
- [CHAR_NAME_1]
- [CHAR_NAME_2]
...

LOCATIONS:
- [LOC_NAME_1]
- [LOC_NAME_2]
...

PROPS:
- [PROP_NAME_1]
- [PROP_NAME_2]
...

CRITICAL RULES:
- Use UPPERCASE with underscores for multi-word names
- Always include the category prefix (CHAR_, LOC_, PROP_)
- Always wrap in square brackets
- Tags are literal identifiers, NOT placeholders
```

## Variables
- `{TAG_NAMING_RULES}`: Injected from AgentPromptLibrary
- `{story_text}`: The story content to extract tags from

## Consensus Configuration
- 5 agents with different perspectives (narrative, visual, character, technical, holistic)
- 80% threshold for character tags
- Single agent for location directional tags (faster, more consistent)

## Notes
- This prompt is used by ConsensusTagger with 5 agents
- Each agent has a different perspective defined in consensus_tagger.py
- Tags must match the canonical format: [PREFIX_NAME]

