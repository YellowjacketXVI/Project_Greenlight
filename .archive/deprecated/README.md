# Deprecated Files Archive

This directory contains deprecated files that have been replaced by newer implementations.

**DO NOT USE FILES IN THIS DIRECTORY FOR NEW DEVELOPMENT.**

---

## Contents

### `Agent_Prompts`
- **Deprecated:** 2025-12-13
- **Replaced By:** `greenlight/agents/prompts.py`
- **Reason:** Legacy prompts used placeholder formats (`[TAG_NAME]`) instead of concrete examples with proper prefixes (`[CHAR_MEI]`). The new `AgentPromptLibrary` class provides centralized, standardized prompts.

---

## Migration Guide

### From `Agent_Prompts` to `AgentPromptLibrary`

**Old approach (deprecated):**
```python
# Manually reading prompts from Agent_Prompts file
# Using placeholder formats like [TAG_NAME]
```

**New approach:**
```python
from greenlight.agents.prompts import AgentPromptLibrary

# Access tag naming rules (mandatory for all tag-related prompts)
rules = AgentPromptLibrary.TAG_NAMING_RULES

# Access specific prompt templates
tag_prompts = AgentPromptLibrary.get_tag_validation_prompts()
director_prompts = AgentPromptLibrary.get_director_prompts()
```

---

## Why Files Are Archived (Not Deleted)

1. **Historical Reference:** Understand how the system evolved
2. **Migration Support:** Help developers update old code
3. **Rollback Safety:** Emergency recovery if needed
4. **Documentation:** Preserve context for design decisions

---

## Vector Routing

Per `.augment-guidelines`, archived files have:
- **Weight:** -0.5 (deprioritized in search)
- **Route:** Background access only
- **Status:** ARCHIVED_CONCEPT

---

## See Also

- `DEPRECATION_PLAN.md` - Full deprecation timeline and migration instructions
- `greenlight/agents/prompts.py` - Canonical prompt library
- `greenlight/config/notation_patterns.py` - Canonical notation patterns

