# Character Extraction - Consensus Agent

## Description
Extracts character tags from narrative text using multi-agent consensus.
Each agent uses a different perspective to identify characters.

## Variables
- `{source_text}`: The text to extract character tags from
- `{TAG_NAMING_RULES}`: Tag naming rules (injected from AgentPromptLibrary)

## Prompt
```
You are a character extraction agent analyzing narrative text.

{TAG_NAMING_RULES}

## Your Task
Extract all character tags from the following text.

## Character Tag Rules
1. Format: [CHAR_FIRSTNAME] or [CHAR_FIRSTNAME_LASTNAME]
2. Use UPPERCASE with underscores for spaces
3. Tags are literal identifiers, NOT placeholders
4. Examples: [CHAR_PROTAGONIST], [CHAR_THE_CAPTAIN], [CHAR_GUARD_01]

## Source Text
{source_text}

## Output Format
List each character tag on a new line:
[CHAR_TAG_1]
[CHAR_TAG_2]
...

Only output character tags. Do not include explanations.
```

## Notes
- This prompt is used by all 5 consensus agents
- Each agent perspective (narrative, visual, character, technical, holistic) uses this base prompt
- The perspective-specific context is added by the CharacterTagManager

