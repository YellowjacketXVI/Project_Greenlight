# Greenlight Deprecation Plan

**Created:** 2025-12-13
**Status:** Active
**Last Updated:** 2025-12-13

---

## Overview

This document tracks deprecated components in the Greenlight codebase and provides migration instructions for developers.

---

## 1. Deprecated: `Agent_Prompts` File

### Status
- **Deprecated:** 2025-12-13
- **Removal Date:** Immediate (moved to archive)
- **Replacement:** `greenlight/agents/prompts.py`

### What Changed
The legacy `Agent_Prompts` file contained outdated prompt templates that used placeholder formats like `[TAG_NAME]` instead of concrete examples with proper prefixes.

### Migration Instructions

**Before (deprecated):**
```python
# Reading prompts from Agent_Prompts file
# Using [TAG_NAME] placeholder format
```

**After (use this):**
```python
from greenlight.agents.prompts import AgentPromptLibrary

# Get tag naming rules
rules = AgentPromptLibrary.TAG_NAMING_RULES

# Get specific prompts
prompts = AgentPromptLibrary.get_tag_validation_prompts()
```

### Detection
Search for references to `Agent_Prompts`:
```bash
grep -r "Agent_Prompts" --include="*.py" --include="*.md"
```

---

## 2. Deprecated: Old Frame ID Format `{frame_X.Y}`

### Status
- **Deprecated:** 2025-12-13
- **Removal Date:** Immediate
- **Replacement:** Scene.Frame.Camera notation `[X.Y.cZ]`

### What Changed
The old frame ID format `{frame_1.2}` has been replaced with the unified scene.frame.camera notation `[1.2.cA]`.

### Format Comparison

| Old Format (Deprecated) | New Format (Use This) |
|------------------------|----------------------|
| `{frame_1.2}` | `[1.2.cA]` |
| `{frame_2.5}` | `[2.5.cA]` |
| No camera identifier | Camera letter (cA, cB, cC...) |

### Migration Instructions

**Before (deprecated):**
```python
frame_id = "{frame_1.2}"
pattern = r"\{frame_(\d+)\.(\d+)\}"
```

**After (use this):**
```python
frame_id = "[1.2.cA]"
pattern = r"\[(\d+)\.(\d+)\.c([A-Z])\]"
```

### Detection
Search for old format usage:
```bash
grep -rE "\{frame_[0-9]+\.[0-9]+\}" --include="*.py" --include="*.md"
grep -rE "frame_id.*\{frame" --include="*.py"
```

---

## 3. Deprecated: Placeholder Tag Formats in Prompts

### Status
- **Deprecated:** 2025-12-13
- **Removal Date:** Immediate
- **Replacement:** Concrete tag examples with proper prefixes

### What Changed
System prompts must use concrete tag examples, not placeholders.

### Format Comparison

| Deprecated (Placeholder) | Correct (Concrete) |
|-------------------------|-------------------|
| `[TAG_NAME]` | `[CHAR_MEI]` |
| `[CHAR_NAME]` | `[CHAR_THE_GENERAL]` |
| `[LOC_TAG]` | `[LOC_PALACE]` |
| `[N.N.cX]` | `[1.2.cA]` |

### Migration Instructions

All prompts must include:
1. `AgentPromptLibrary.TAG_NAMING_RULES` constant
2. Concrete examples with proper prefixes
3. Explicit instruction: "Tags are literal identifiers, NOT placeholders"

### Detection
Search for placeholder patterns:
```bash
grep -rE "\[TAG_NAME\]|\[CHAR_NAME\]|\[LOC_NAME\]|\[N\.N\.cX\]" --include="*.py"
```

---

## Canonical Sources

| Component | Canonical Location |
|-----------|-------------------|
| Tag Naming Rules | `greenlight/agents/prompts.py::AgentPromptLibrary.TAG_NAMING_RULES` |
| Notation Patterns | `greenlight/config/notation_patterns.py` |
| Tag Prefixes | `greenlight/core/constants.py::TagPrefix` |
| Frame Notation | `greenlight/config/notation_patterns.py::SCENE_FRAME_CAMERA_PATTERNS` |

---

## Validation Commands

Run these commands to verify no deprecated patterns are in use:

```bash
# Check for Agent_Prompts references
grep -r "Agent_Prompts" --include="*.py"

# Check for old frame format
grep -rE "\{frame_[0-9]" --include="*.py"

# Check for placeholder tags in prompts
grep -rE "\[TAG_NAME\]|\[CHAR_NAME\]|\[LOC_NAME\]" --include="*.py"

# Import test for all modified files
python -c "from greenlight.agents.prompts import AgentPromptLibrary; print('OK')"
python -c "from greenlight.config.notation_patterns import SCENE_FRAME_CAMERA_PATTERNS; print('OK')"
python -c "from greenlight.patterns.quality.anchor_agent import AnchorAgent; print('OK')"
```

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-13 | Initial deprecation plan created | Augment Agent |
| 2025-12-13 | Deprecated Agent_Prompts, old frame format, placeholder tags | Augment Agent |

