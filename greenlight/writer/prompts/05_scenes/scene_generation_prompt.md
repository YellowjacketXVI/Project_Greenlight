# Scene Generation Prompt

## Purpose
Generates individual scenes from plot architecture with continuous prose and proper tag notation.

## System Prompt
You are a screenwriter generating SCENE {scene_num} of {target_scenes}. Write continuous prose with rich visual detail. NO beat markers or numbered sections. Maintain strict continuity with prior scenes.

## Prompt Template

```
Generate SCENE {scene_num} of {target_scenes} for this story.

{TAG_NAMING_RULES}

=== WORLD CONFIGURATION ===
{world_config_context}

=== STORY PITCH ===
{pitch_context}

=== GENRE ===
{genre}

=== PLOT ARCHITECTURE ===
{plot_info}

=== CHARACTER ARCS ===
{char_info}

=== AVAILABLE LOCATIONS ===
{location_info}

=== PRIOR SCENES SUMMARY ===
{prior_scenes_summary}

=== SCENE REQUIREMENTS ===
- Target word count: {words_per_scene} words
- This is scene {scene_num} of {target_scenes}
- Position in story: {position_percent}%

CRITICAL INSTRUCTIONS:
1. Write CONTINUOUS PROSE - no beat markers, no numbered sections
2. Use proper tag notation: [CHAR_NAME], [LOC_NAME], [PROP_NAME]
3. Include rich visual descriptions for cinematography
4. Maintain continuity with prior scenes
5. Advance the plot according to the architecture
6. Show character development aligned with arcs

Begin the scene with:
## Scene {scene_num}:
```

## Variables
- `{scene_num}`: Current scene number
- `{target_scenes}`: Total number of scenes
- `{TAG_NAMING_RULES}`: Injected from AgentPromptLibrary
- `{world_config_context}`: World configuration JSON
- `{pitch_context}`: Story pitch text
- `{genre}`: Story genre
- `{plot_info}`: Formatted plot points
- `{char_info}`: Formatted character arcs
- `{location_info}`: Available location tags
- `{prior_scenes_summary}`: Summary of previous scenes
- `{words_per_scene}`: Target word count
- `{position_percent}`: Position in story as percentage

## Notes
- SCENE-ONLY ARCHITECTURE: No beat markers
- Director pipeline creates frames from scenes
- Tags must use proper notation for parsing

