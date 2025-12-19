# Global Context Research Prompt

## Purpose
Research the global context for a story including historical, cultural, and atmospheric elements.

## System Prompt
You are a world-building researcher.

## Prompt Template

```
Research the global context for this story.

PITCH: {pitch_text}
TIME PERIOD: {time_period}
SETTING: {setting}
GENRE: {genre}

Provide:
1. Historical/cultural context
2. World rules (physics, magic, technology)
3. Atmosphere palette (colors, moods, textures)
4. Social dynamics

Format as JSON.
```

## Variables
- `{pitch_text}`: The story pitch text
- `{time_period}`: Time period of the story
- `{setting}`: Story setting/location
- `{genre}`: Story genre

## Expected Output Format

```json
{
  "historical_context": {
    "era": "...",
    "key_events": ["..."],
    "cultural_norms": ["..."]
  },
  "world_rules": {
    "physics": "...",
    "magic_system": "...",
    "technology_level": "..."
  },
  "atmosphere_palette": {
    "primary_colors": ["..."],
    "moods": ["..."],
    "textures": ["..."]
  },
  "social_dynamics": {
    "class_structure": "...",
    "power_dynamics": "...",
    "key_conflicts": ["..."]
  }
}
```

## Notes
- Global context informs all other research
- Provides consistency across characters, locations, props
- Atmosphere palette feeds into visual style

