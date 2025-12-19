# Physiological Tells Prompt

## Purpose
Define observable physical behaviors that express internal emotional states for a character.

## System Prompt
You are a character behavior specialist defining physiological tells.

## Prompt Template

```
Define the PHYSIOLOGICAL TELLS for {character_name} when experiencing {emotion}.

CHARACTER PROFILE:
{character_profile}

TIME PERIOD: {time_period}
GENRE: {genre}

Physiological tells are OBSERVABLE PHYSICAL BEHAVIORS that express internal emotional states.
These are NOT verbal - they are body language, facial expressions, posture changes, and physical mannerisms.

For {emotion}, describe:
1. FACIAL EXPRESSION - What happens to their face? (eyes, mouth, brow, jaw)
2. BODY POSTURE - How does their posture change?
3. HAND/ARM BEHAVIOR - What do their hands do?
4. BREATHING/VOICE - How does their breathing or voice quality change?
5. UNIQUE TELL - A distinctive behavior specific to this character

Keep descriptions:
- Observable (can be seen/heard)
- Period-accurate
- Character-specific (not generic)
- Concise (1-2 sentences each)
```

## Variables
- `{character_name}`: Character's name
- `{emotion}`: Emotion to describe (anger, fear, joy, sadness, surprise, disgust, love, anxiety)
- `{character_profile}`: Full character profile
- `{time_period}`: Story time period
- `{genre}`: Story genre

## Emotions Covered
- anger
- fear
- joy
- sadness
- surprise
- disgust
- love
- anxiety

## Notes
- Uses Claude Haiku for cost efficiency (hardcoded)
- Physiological tells are for script/roleplay, NOT visual reference generation
- Each emotion gets its own tell definition
- Assembly agent mode with parallel processing

