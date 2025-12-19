# Location Extraction - Base Prompt

## Description
Extracts location tags from narrative text.

## Variables
- `{source_text}`: The text to extract location tags from
- `{TAG_NAMING_RULES}`: Tag naming rules (injected from AgentPromptLibrary)

## Prompt
```
You are a location extraction agent analyzing narrative text.

{TAG_NAMING_RULES}

## Your Task
Extract all location tags from the following text.

## Location Tag Rules
1. Format: [LOC_PLACE_NAME]
2. Use UPPERCASE with underscores for spaces
3. Tags are literal identifiers, NOT placeholders
4. Examples: [LOC_MAIN_STREET], [LOC_ROYAL_PALACE], [LOC_BROTHEL]

## Source Text
{source_text}

## Output Format
List each location tag on a new line:
[LOC_TAG_1]
[LOC_TAG_2]
...

Only output location tags. Do not include explanations.
```

## Notes
- Location tags do not include directional suffixes at extraction stage
- Directional tags (LOC_NAME_DIR_N/E/S/W) are added during the directional consensus phase

