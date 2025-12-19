# Location Directional Reference Prompt

## Purpose
Generates four directional reference prompts (N/E/S/W) for a location.

## System Prompt
You are an expert at creating detailed image generation prompts for location reference images. Your prompts should capture spatial relationships, architectural details, and atmosphere for consistent scene generation.

## Prompt Template

```
Generate FOUR directional reference prompts for this location:

TAG: [{tag}]
{location_context}

WORLD STYLE: {world_style}

Create prompts for each cardinal direction. The NORTH view is the primary/default view.
Subsequent directions should describe how the view changes when rotating from North.

Output as JSON with this exact structure:
{
    "north": "Detailed prompt for North view (primary/default view)...",
    "east": "Turn 90 degrees right from North. Detailed prompt showing...",
    "south": "Turn 180 degrees from North. Detailed prompt showing...",
    "west": "Turn 90 degrees left from North. Detailed prompt showing..."
}

Each prompt should include:
- Spatial layout and architectural elements visible from that direction
- Lighting conditions and atmosphere
- Key landmarks or features visible from that angle
- Depth and perspective cues
- Style consistency notes

Output ONLY the JSON, no explanations.
```

## Variables
- `{tag}`: Location tag (e.g., LOC_PALACE)
- `{location_context}`: Location data including name, description, spatial_layout, architectural_style
- `{world_style}`: World style from ContextEngine.get_world_style()

## Location Context Fields
- **name**: Location name
- **description**: General description
- **spatial_layout**: Layout and dimensions
- **architectural_style**: Architectural style
- **atmosphere**: Mood and ambiance
- **key_features**: Notable features

## Generation Order
1. North view first (primary/default)
2. East view (90 degrees right)
3. West view (90 degrees left)
4. South view (180 degrees)

## Notes
- Uses Gemini 2.5 Flash for cost-efficient prompt generation
- Single agent for directional tag selection (faster than consensus)
- Output is used with Seedream 4.5 for image generation

