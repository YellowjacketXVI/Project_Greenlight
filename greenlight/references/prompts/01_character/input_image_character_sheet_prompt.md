# Input Image Character Sheet Prompt

## Purpose
Generates a character reference sheet from an input image.
This is the "Generate from Image" flow - analyzes an existing image, updates profile, then generates sheet.

## Pipeline
`UnifiedReferenceScript.generate_character_from_image(tag, image_path)`:
1. Image Analysis (Gemini 2.5 Flash) → Extract character details from input image
2. ProfileTemplateAgent → Map analysis to world_config.json profile
3. ImageHandler.generate_character_sheet() → Generate reference sheet using analyzed data

## Image Analysis System Prompt
```
You are analyzing a character image to extract visual details for a reference sheet.
Focus ONLY on observable visual characteristics - do not invent backstory or personality.
```

## Image Analysis Prompt

```
Analyze this character image and extract the following visual details:

CHARACTER TAG: [{tag}]

Extract these observable characteristics:

1. PHYSICAL APPEARANCE:
   - Estimated age range
   - Ethnicity/cultural background (if discernible)
   - Hair color, style, and length
   - Eye color (if visible)
   - Skin tone
   - Body type and build
   - Height estimate (relative to surroundings)
   - Distinguishing features (scars, tattoos, birthmarks)

2. COSTUME/CLOTHING:
   - Primary garments (top, bottom, dress, etc.)
   - Colors and patterns
   - Material/texture (leather, silk, cotton, etc.)
   - Accessories (jewelry, belts, bags, etc.)
   - Footwear
   - Headwear or hair accessories

3. POSE AND EXPRESSION:
   - Current pose/stance
   - Facial expression
   - Body language

Output as structured JSON:
{
  "age_range": "",
  "ethnicity": "",
  "hair": {"color": "", "style": "", "length": ""},
  "eyes": {"color": ""},
  "skin_tone": "",
  "body_type": "",
  "distinguishing_features": [],
  "costume": {
    "top": "",
    "bottom": "",
    "colors": [],
    "materials": [],
    "accessories": [],
    "footwear": ""
  },
  "pose": "",
  "expression": ""
}
```

## Sheet Generation Prompt (After Analysis)

```
Generate a CHARACTER REFERENCE SHEET prompt based on this analyzed character:

TAG: [{tag}]
NAME: {name}

ANALYZED APPEARANCE:
{analyzed_appearance}

ANALYZED COSTUME:
{analyzed_costume}

WORLD STYLE: {world_style}

Create a prompt that:
1. Recreates this EXACT character across 6 views (front, 3/4 left, 3/4 right, profile left, profile right, back)
2. Maintains IDENTICAL appearance and costume in all views
3. Uses neutral standing pose with arms slightly away from body
4. Places character on clean white/light gray background
5. Arranges views in professional reference sheet grid layout

CRITICAL: The generated character must match the analyzed input image exactly.
Do not add or change any visual details.

Output ONLY the final prompt text, ready for image generation.
```

## Variables
- `{tag}`: Character tag (e.g., CHAR_MEI)
- `{name}`: Character name (from world_config or derived from tag)
- `{analyzed_appearance}`: Physical details extracted from image analysis
- `{analyzed_costume}`: Costume details extracted from image analysis
- `{world_style}`: World style from ContextEngine.get_world_style()

## Flow Diagram
```
Input Image
    ↓
[Gemini 2.5 Flash - Image Analysis]
    ↓
Structured JSON (appearance, costume, etc.)
    ↓
[ProfileTemplateAgent]
    ↓
world_config.json updated with analyzed profile
    ↓
[ImageHandler.generate_character_sheet()]
    ↓
Reference Sheet (6 views matching input image)
```

## Key Differences from Regular Sheet Generation
| Aspect | Regular Sheet | Input Image Sheet |
|--------|---------------|-------------------|
| Source | world_config.json text | Analyzed input image |
| Profile | Pre-existing | Generated from analysis |
| Goal | Create from description | Recreate from image |
| Accuracy | Interpretive | Must match input exactly |

## Notes
- Uses Gemini 2.5 Flash for both image analysis and prompt generation
- ProfileTemplateAgent updates world_config.json with analyzed data
- Seedream 4.5 generates final sheet with blank first image at 16:9 2K
- Input image is used as reference during generation (after blank dimensional image)

