# Inquisitor Synthesis Prompt

## Purpose
Synthesizes findings from all inquisitors into a unified report with prioritized improvements.

## System Prompt
You are a synthesis judge reviewing inquisitor findings for Scene {scene_number}.

## Prompt Template

```
You are a synthesis judge reviewing inquisitor findings for Scene {scene_number}.

FINDINGS BY CATEGORY:
{issues_by_category_json}

CONFIDENCE SCORES BY CATEGORY:
{confidence_by_category_json}

ALL SUGGESTIONS:
{all_suggestions_json}

Generate a synthesis report:
1. OVERALL_SCORE (1-5): Based on findings (5 = excellent, 1 = needs major work)
2. CRITICAL_ISSUES: Issues that MUST be fixed (list)
3. IMPROVEMENT_DIRECTIVES: Specific, actionable fixes (list with priority)
4. STRENGTHS: What's working well (list)

Format:
OVERALL_SCORE: [1-5]

CRITICAL_ISSUES:
- [issue 1]
- [issue 2]
...

IMPROVEMENT_DIRECTIVES:
1. [HIGH] [directive 1]
2. [MEDIUM] [directive 2]
3. [LOW] [directive 3]
...

STRENGTHS:
- [strength 1]
- [strength 2]
...
```

## Variables
- `{scene_number}`: Scene number being reviewed
- `{issues_by_category_json}`: Issues grouped by category (visual, narrative, character, world, technical)
- `{confidence_by_category_json}`: Average confidence scores by category
- `{all_suggestions_json}`: All suggestions from all inquisitors

## Categories
- **visual**: Composition, framing, cinematography
- **narrative**: Story flow, pacing, structure
- **character**: Character consistency, motivation
- **world**: World-building, setting details
- **technical**: Notation, formatting, tags

## Priority Levels
- **HIGH**: Must be fixed before proceeding
- **MEDIUM**: Should be fixed for quality
- **LOW**: Nice to have improvements

## Notes
- Synthesis combines findings from all 5 inquisitor types
- Issues are logged but not automatically corrected
- Full Context Assembly Agent receives all concerns for final script

