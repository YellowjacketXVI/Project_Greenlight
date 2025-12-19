# Prop Reference Sheet Prompt

## Purpose
Generates a detailed multi-angle prop reference sheet prompt for AI image generation.

## System Prompt
You are an expert at creating detailed image generation prompts for prop/object reference sheets. Your prompts should capture materials, scale, and functional details for consistent prop generation.

## Prompt Template

```
Generate a detailed multi-angle PROP REFERENCE SHEET prompt for:

TAG: [{tag}]
{prop_context}

WORLD STYLE: {world_style}

Create a comprehensive prompt that specifies:

1. VIEWS TO INCLUDE:
   - Front view (primary angle)
   - Side view left
   - Side view right
   - Top view (bird's eye)
   - Back view
   - Detail shots (close-ups of key features)

2. DETAILS TO CAPTURE:
   - Material properties (metal, wood, fabric, etc.)
   - Surface textures and finishes
   - Color palette and variations
   - Scale reference (show relative size)
   - Functional elements and mechanisms
   - Wear, damage, or patina if applicable

3. STYLE REQUIREMENTS:
   - Consistent object identity across all views
   - Clean, professional reference sheet layout
   - Neutral background (white or light gray)
   - Include scale reference where appropriate

Output ONLY the final prompt text, ready for image generation. No explanations.
```

## Variables
- `{tag}`: Prop tag (e.g., PROP_SWORD)
- `{prop_context}`: Prop data including name, description, materials, dimensions
- `{world_style}`: World style from ContextEngine.get_world_style()

## Prop Context Fields
- **name**: Prop name
- **description**: General description
- **materials**: Materials used (metal, wood, fabric, etc.)
- **dimensions**: Size and scale
- **condition**: Wear, damage, patina
- **significance**: Narrative importance

## Notes
- Uses Gemini 2.5 Flash for cost-efficient prompt generation
- Output is used with Seedream 4.5 for image generation
- Seedream requires blank first image at desired dimension

