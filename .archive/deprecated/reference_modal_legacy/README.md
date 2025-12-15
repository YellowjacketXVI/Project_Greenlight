# DEPRECATED: Reference Modal Legacy Generation Methods

**Deprecated Date**: 2025-12-15
**Replaced By**: `greenlight/references/unified_reference_script.py`

## What Was Deprecated

The following methods in `greenlight/ui/components/reference_modal.py` are **DEPRECATED**:

### Generation Methods (DO NOT USE)
- `_generate_reference()` - Direct ImageRequest creation bypasses UnifiedReferenceScript
- `_generate_character_sheet()` - Uses `get_character_sheet_prompt()` directly, bypasses unified flow
- `_generate_sheet()` - Duplicate of character sheet generation
- `_generate_sheet_from_selected()` - Direct ImageRequest with hardcoded prefix_type
- `_generate_sheet_from_image()` - Direct ImageRequest with hardcoded prefix_type
- `_generate_cardinal_views()` - Direct ImageRequest creation for location views
- `_build_reference_prompt()` - Manual prompt building (should use ReferencePromptAgent)

### Why Deprecated

1. **Bypasses UnifiedReferenceScript**: These methods create `ImageRequest` objects directly instead of using the unified API
2. **Inconsistent prefix_type**: Different methods use different `prefix_type` values (edit, recreate, none)
3. **Duplicate logic**: Style suffix and prompt building logic is duplicated across methods
4. **No image analysis pipeline**: Character from image doesn't use Gemini analysis → profile template flow
5. **Legacy UI only**: These methods only work in the CustomTkinter UI, not the Web UI

## Migration Guide

### Before (DEPRECATED)
```python
# In reference_modal.py
def _generate_character_sheet(self):
    handler = self._get_image_handler()
    prompt = handler.get_character_sheet_prompt(self.tag, self.name, character_data=char_data)
    request = ImageRequest(
        prompt=prompt,
        model=model,
        prefix_type="recreate",  # Hardcoded!
        ...
    )
    result = await handler.generate(request)
```

### After (USE THIS)
```python
from greenlight.references.unified_reference_script import UnifiedReferenceScript

script = UnifiedReferenceScript(project_path)
result = await script.generate_character_sheet(tag)
```

## Files Affected

| Old Location | Status | Replacement |
|--------------|--------|-------------|
| `greenlight/ui/components/reference_modal.py` | DEPRECATED (methods only) | `UnifiedReferenceScript` |
| Direct `ImageRequest` creation | DEPRECATED | `UnifiedReferenceScript` methods |
| `ImageHandler.get_character_sheet_prompt()` | DEPRECATED | `ReferencePromptAgent.generate_character_prompt()` |

## Related Documentation

- `.augment-guidelines` - Updated with UNIFIED REFERENCE SCRIPT API section
- `greenlight/references/unified_reference_script.py` - New canonical entry point
- `greenlight/agents/reference_prompt_agent.py` - LLM-based prompt generation
- `greenlight/agents/profile_template_agent.py` - Image analysis → profile mapping

