# Greenlight Notation Standards

**Version:** 2.0
**Last Updated:** 2025-12-13
**Status:** ✅ Standardization Complete

This document defines the canonical notation formats used throughout Project Greenlight. Strict adherence is **critical** for parsing reliability and pipeline consistency.

---

## 1. Why Strict Notation Matters

### Parsing Dependency Chain
```
Writer Pipeline → script.md → Director Pipeline → visual_script.md → Image Generation
                     ↓                  ↓
              Regex Parsing        Regex Parsing
```

If notation deviates from the standard:
- **Parsing fails** → Frames not extracted → No images generated
- **Tag mismatches** → Reference images not found → Inconsistent characters
- **Scene markers missing** → Scenes not split → Incorrect frame counts

### LLM Behavior
LLMs interpret `[TAG_NAME]` as a placeholder unless explicitly told otherwise. System prompts MUST:
1. State that tags are **literal identifiers**
2. Provide **concrete examples** (not abstract patterns)
3. Include **CRITICAL/MANDATORY** emphasis for format rules

---

## 2. Tag Notation Standard

### Format
```
[PREFIX_NAME]
```

### Prefixes (MANDATORY)

| Prefix | Category | Usage |
|--------|----------|-------|
| `CHAR_` | Characters | All people, named or unnamed |
| `LOC_` | Locations | All places, specific or general |
| `PROP_` | Props | All objects, items, costumes |
| `CONCEPT_` | Concepts | Themes, abstract ideas |
| `EVENT_` | Events | Significant occurrences |

### Naming Rules
- **UPPERCASE** with underscores for spaces
- **Specific names**: `[CHAR_MEI]` not `[CHAR_PROTAGONIST]`
- **Titled characters**: `[CHAR_THE_GENERAL]`, `[CHAR_THE_EMPEROR]`
- **Unnamed roles**: `[CHAR_GUARD_01]`, `[CHAR_SERVANT_01]`
- **Specific locations**: `[LOC_MEI_BEDROOM]` not `[LOC_BEDROOM]`

### Examples
```
✅ CORRECT:
[CHAR_MEI], [CHAR_THE_GENERAL], [CHAR_GUARD_01]
[LOC_FLOWER_SHOP], [LOC_IMPERIAL_PALACE], [LOC_CHEN_TEAHOUSE]
[PROP_JADE_HAIRPIN], [PROP_GO_BOARD], [PROP_BRONZE_DAGGER]

❌ INCORRECT:
Mei, [Mei], CHAR_MEI, [char_mei], [CHARACTER_MEI]
```

---

## 3. Scene.Frame.Camera Notation Standard

### Format
```
{scene}.{frame}.c{letter}
```

| Component | Type | Range | Examples |
|-----------|------|-------|----------|
| Scene | Integer | 1+ | `1`, `2`, `8` |
| Frame | Integer | 1+ | `1`, `2`, `15` |
| Camera | Letter | A-Z | `cA`, `cB`, `cC` |

### Camera Block Format
```
[{scene}.{frame}.c{letter}] ({shot_type})
c{letter}. {SHOT_TYPE_CAPS}. {prompt_content}...
```

### Example
```
[1.2.cA] (Wide)
cA. WIDE ESTABLISHING SHOT. The camera frames the flower shop exterior...

[1.2.cB] (Close-up)
cB. CLOSE-UP on [CHAR_MEI]'s hands arranging orchids...
```

### Scene Markers
```
## Scene 1:
## Scene 2:
```

### Beat Markers
```
## Beat: scene.1.01
## Beat: scene.1.02
```

### Frame Chunk Delimiters
```
(/scene_frame_chunk_start/)
[1.1.cA] (Wide)
[CAM: Wide establishing, eye level, static]
[POS: CHAR_MEI center frame]
[LIGHT: Natural daylight from windows]
[PROMPT: Wide shot of the flower shop interior...]
(/scene_frame_chunk_end/)
```

---

## 4. Technical Notations

### Camera Instruction
```
[CAM: {shot_type}, {angle}, {movement}, {lens}]
```
Example: `[CAM: Medium close-up, slight low angle, static, 85mm]`

### Position Notation
```
[POS: {TAG} {position}, {TAG} {position}, ...]
```
Positions: `center`, `screen left`, `screen right`, `foreground`, `background`

Example: `[POS: CHAR_MEI center, CHAR_LIN screen right background]`

### Lighting Notation
```
[LIGHT: {style}, {key_source}, {atmosphere}]
```
Example: `[LIGHT: Chiaroscuro, key from east window, dramatic shadows]`

### Prompt Notation
```
[PROMPT: {250_word_max_prompt}]
```

---

## 5. Writing System Prompts

### Required Elements
1. **Explicit format specification** with examples
2. **CRITICAL/MANDATORY emphasis** for format rules
3. **Concrete examples** (never abstract placeholders)
4. **Validation instructions** (check format before output)

### Template Pattern
```python
PROMPT = """
## TAG FORMAT (MANDATORY)
All entity references MUST use bracketed tags with prefixes:
- Characters: [CHAR_NAME] e.g., [CHAR_MEI], [CHAR_THE_GENERAL]
- Locations: [LOC_NAME] e.g., [LOC_FLOWER_SHOP], [LOC_PALACE]
- Props: [PROP_NAME] e.g., [PROP_SWORD], [PROP_JADE_HAIRPIN]

**CRITICAL**: Tags are literal identifiers, NOT placeholders.
Use the EXACT tag format every time you reference an element.

## SCENE.FRAME.CAMERA FORMAT (MANDATORY)
Camera blocks MUST follow: [{scene}.{frame}.c{letter}] ({shot_type})
Example: [1.2.cA] (Wide)

{actual_task_instructions}
"""
```

---

## 6. Testing Notation Compliance

### Manual Validation
```python
from greenlight.config.notation_patterns import (
    extract_camera_ids,
    extract_frame_chunks,
    REGEX_PATTERNS
)
import re

# Test tag extraction
text = "The scene shows [CHAR_MEI] at [LOC_FLOWER_SHOP]"
char_tags = re.findall(REGEX_PATTERNS["character_tag"], text)
loc_tags = re.findall(REGEX_PATTERNS["location_tag"], text)

# Test camera notation
text = "[1.2.cA] (Wide) cA. ESTABLISHING SHOT..."
cameras = extract_camera_ids(text)  # Returns [('1', '2', 'A')]
```

### Using AnchorAgent
```python
from greenlight.patterns.quality.anchor_agent import AnchorAgent

anchor = AnchorAgent()
report = await anchor.enforce_notation(script_content, world_config)

if not report.notation_valid:
    for issue in report.issues_found:
        print(f"{issue.issue_type}: {issue.description}")
        print(f"  Current: {issue.current_value}")
        print(f"  Fix: {issue.suggested_fix}")
```

---

## 7. Regex Patterns Reference

Located in `greenlight/config/notation_patterns.py`:

```python
# SCENE-ONLY ARCHITECTURE: No beat_marker pattern
SCENE_FRAME_CAMERA_PATTERNS = {
    "full_id": r"\[(\d+)\.(\d+)\.c([A-Z])\]",           # [1.2.cA]
    "full_id_with_type": r"\[(\d+)\.(\d+)\.c([A-Z])\]\s*\(([^)]+)\)",
    "scene_marker": r"##\s*Scene\s+(\d+):",             # ## Scene 1:
}

REGEX_PATTERNS = {
    "character_tag": r"\[CHAR_[A-Z_]+\]",
    "location_tag": r"\[LOC_[A-Z_]+\]",
    "prop_tag": r"\[PROP_[A-Z_]+\]",
    "frame_chunk_start": r"\(/scene_frame_chunk_start/\)",
    "frame_chunk_end": r"\(/scene_frame_chunk_end/\)",
}
```

---

## 8. Audit Report: Standardization Complete

### Issues Fixed (2025-12-13)

| Location | Issue | Status | Fix Applied |
|----------|-------|--------|-------------|
| `Agent_Prompts` (legacy) | Uses `[TAG_NAME]` placeholder format | ✅ FIXED | Moved to `.archive/deprecated/` |
| `Agent_Prompts` | Missing TAG_NAMING_RULES in prompts | ✅ FIXED | Deprecated, use `prompts.py` |
| `inquisitor_panel.py` | Notation rules use `[CHAR_NAME]` not `[CHAR_TAG]` | ✅ FIXED | Added TAG_NAMING_RULES import |
| `anchor_agent.py` | Duplicate pattern definitions | ✅ FIXED | Now imports from `notation_patterns.py` |
| `constellation_agent.py` | Missing TAG_NAMING_RULES | ✅ FIXED | Added AgentPromptLibrary import |
| `directional_consensus.py` | Missing TAG_NAMING_RULES | ✅ FIXED | Added AgentPromptLibrary import |
| `notation_patterns.py` | Old frame_id_template format | ✅ FIXED | Updated to `[{scene}.{frame}.c{camera}]` |
| `directing_pipeline.py` | No notation validation note | ✅ FIXED | Added docstring explaining QA phase |

### Fixes Applied (2025-12-13)

1. ✅ **Deprecated `Agent_Prompts`** - Moved to `.archive/deprecated/Agent_Prompts`
2. ✅ **Updated `inquisitor_panel.py`** - Added TAG_NAMING_RULES with concrete examples
3. ✅ **Consolidated patterns** - `anchor_agent.py` now imports from `notation_patterns.py`
4. ✅ **Standardized all prompts** - TAG_NAMING_RULES used in all tag-related prompts
5. ✅ **Updated frame format** - `frame_id_template` now uses `[{scene}.{frame}.c{camera}]`
6. ✅ **Added deprecation warnings** - `format_frame_id()` emits DeprecationWarning
7. ✅ **Created documentation** - `DEPRECATION_PLAN.md` and `.archive/deprecated/README.md`

---

## 9. File Ownership

| File | Owner | Purpose |
|------|-------|---------|
| `greenlight/agents/prompts.py` | AgentPromptLibrary | Central prompt templates with TAG_NAMING_RULES |
| `greenlight/config/notation_patterns.py` | Config | **Canonical source** for all regex patterns |
| `greenlight/patterns/quality/anchor_agent.py` | QA | Notation validation (imports from notation_patterns.py) |
| `greenlight/patterns/quality/inquisitor_panel.py` | QA | Technical notation checking (uses TAG_NAMING_RULES) |
| `greenlight/patterns/quality/constellation_agent.py` | QA | Tag relationship extraction (uses TAG_NAMING_RULES) |
| `greenlight/tags/directional_consensus.py` | Tags | Directional tagging (uses TAG_NAMING_RULES) |
| `.augment-guidelines` | Augment | AI assistant instructions |
| `.augment-task-instructions.md` | Augment | Pre-task checklist with maintenance rules |
| `NOTATION_STANDARDS.md` | Developers | This document |
| `DEPRECATION_PLAN.md` | Developers | Deprecation timeline and migration guide |

---

## 10. Maintenance Protocol

### Adding New Notation-Related Code

1. **Import patterns from canonical source:**
   ```python
   from greenlight.config.notation_patterns import (
       SCENE_FRAME_CAMERA_PATTERNS,
       REGEX_PATTERNS,
   )
   ```

2. **Use TAG_NAMING_RULES for prompts:**
   ```python
   from greenlight.agents.prompts import AgentPromptLibrary

   prompt = f"""
   {AgentPromptLibrary.TAG_NAMING_RULES}

   {your_instructions}
   """
   ```

3. **Always use concrete examples:**
   - ❌ `[TAG_NAME]`, `[CHAR_X]`
   - ✅ `[CHAR_MEI]`, `[LOC_PALACE]`, `[PROP_SWORD]`

### Deprecating Notation Code

1. Move file to `.archive/deprecated/` with deprecation notice
2. Add entry to `DEPRECATION_PLAN.md`
3. Add `warnings.warn()` to any remaining functions
4. Update file ownership table above

### Testing Changes

```bash
# Run notation standardization tests
py -m pytest tests/test_notation_standardization.py -v

# Verify no circular dependencies
py -c "from greenlight.patterns.quality.anchor_agent import AnchorAgent; print('OK')"
py -c "from greenlight.patterns.quality.inquisitor_panel import TechnicalInquisitor; print('OK')"
```

