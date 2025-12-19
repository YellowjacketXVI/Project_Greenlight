# Continuity Validation Prompt

## Purpose
Checks story scenes for continuity issues including character, location, prop, and timeline consistency.

## System Prompt
You are a script supervisor checking for continuity errors.

## Prompt Template

```
Check this story for continuity issues.

SCENES:
{scene_summary}

CHARACTER ARCS:
{character_arcs}

Check for:
1. CHARACTER CONTINUITY: Characters appearing where they shouldn't be
2. LOCATION CONTINUITY: Impossible location transitions
3. PROP CONTINUITY: Objects appearing/disappearing incorrectly
4. TIMELINE CONTINUITY: Time inconsistencies

For each issue found, report:
ISSUE:
- TYPE: [CHARACTER|LOCATION|PROP|TIMELINE]
- SEVERITY: [critical|major|minor]
- SCENE: [scene number]
- DESCRIPTION: [what's wrong]
- SUGGESTION: [how to fix]

If no issues found, respond with:
NO_ISSUES_FOUND
```

## Variables
- `{scene_summary}`: Summary of all scenes with key details
- `{character_arcs}`: Formatted character arcs with tags

## Severity Levels
- **critical**: Breaks story logic, must be fixed
- **major**: Noticeable issue, should be fixed
- **minor**: Small inconsistency, optional fix

## Notes
- Part of the parallel validation phase (Layer 3+4)
- Issues are logged but not automatically corrected
- Full Context Assembly Agent receives all concerns for final script

