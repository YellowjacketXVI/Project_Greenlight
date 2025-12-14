# World Config Revamp Design Document

## Overview

This document outlines the comprehensive restructuring of `world_config.json` to enable:
1. **Agent Embodiment** - Characters agents can convincingly inhabit for dialogue, movement, and decisions
2. **Time Period Research** - Deep historical/cultural context that flows into all tag generation
3. **Physiological/Psychological Tells** - Observable behaviors for 30+ emotional states
4. **Removal of Word Caps** - Full context depth for the new context engine

---

## Current Problems

### 1. Characters are External Only
Current schema captures what a character **wants** and who they are **externally**:
```json
{
  "want": "To escape her life as a courtesan",
  "need": "To discover her own self-worth",
  "flaw": "Self-doubt about her value",
  "appearance": "Petite and graceful..."
}
```

**Missing**: How they *think*, *speak*, *move*, and *decide*.

### 2. World Details Don't Flow Into Tag Context
- Time period, world_rules, themes, style exist at top level
- But character/location/prop research agents don't receive full world context
- Results in anachronistic or inconsistent outputs

### 3. Artificial Word Limits
```python
# context_compiler.py
STORY_SEED_WORD_LIMIT = 100
CHARACTER_CARD_WORD_LIMIT = 250
LOCATION_CARD_WORD_LIMIT = 100
PROP_CARD_WORD_LIMIT = 50
```
These compress rich profiles into unusable summaries for agent embodiment.

### 4. Limited Emotional Range
Current: 10 emotions (annoyance, intrigue, excitement, embarrassment, nervousness, confidence, anger, fear, vulnerability, joy)

**Missing**: crush, intimacy, defeat, triumph, focus, jealousy, shame, guilt, etc.

---

## Proposed Schema

### Top-Level World Context (NEW)

```json
{
  "title": "The Orchids Gambit",
  "logline": "...",
  "genre": "Drama",

  "world_details": {
    "time_period": {
      "era": "Ming Dynasty, circa 1500s",
      "specific_year_range": "1500-1550",
      "historical_events": ["Rise of merchant class", "Strict Confucian social codes"],
      "technology_level": "Pre-industrial, woodblock printing, basic metallurgy",
      "medicine_understanding": "Traditional Chinese medicine, herbal remedies",
      "transportation": "Horse, sedan chair, river boats, walking"
    },

    "cultural_context": {
      "social_hierarchy": ["Emperor", "Scholars/Officials", "Farmers", "Artisans", "Merchants", "Entertainers/Courtesans"],
      "gender_roles": "Strict patriarchal structure, women confined to domestic or entertainment spheres",
      "religion_philosophy": ["Confucianism (dominant)", "Buddhism", "Taoism", "Ancestor worship"],
      "taboos": ["Direct eye contact with superiors", "Women initiating conversation with strangers"],
      "customs": ["Formal bowing protocols", "Tea ceremony significance", "Gift-giving etiquette"],
      "language_register": {
        "formal": "Classical Chinese phrases, honorifics required",
        "informal": "Vernacular Mandarin among equals",
        "forbidden_words": ["Direct references to death", "Cursing the Emperor"]
      }
    },

    "economic_context": {
      "currency": "Silver taels, copper coins",
      "cost_of_living": {
        "meal": "2-5 copper coins",
        "courtesan_evening": "1-5 silver taels",
        "freedom_purchase": "50-200 silver taels"
      },
      "trade_goods": ["Silk", "Tea", "Porcelain", "Spices"]
    },

    "aesthetic_context": {
      "architecture": "Curved tile roofs, wooden post-and-beam, paper screens",
      "fashion": "Layered silk robes, bound feet (upper class), jade ornaments",
      "art_forms": ["Calligraphy", "Ink painting", "Poetry", "Go", "Music"],
      "color_symbolism": {
        "red": "Luck, celebration, passion",
        "white": "Death, mourning",
        "blue": "Immortality, hope",
        "yellow": "Royalty (forbidden to commoners)"
      }
    }
  },

  "world_rules": "...",
  "visual_style": "live_action",
  "style_notes": "...",
  "lighting": "Chiaroscuro...",
  "vibe": "Cinematic, moody, emotive, intimate",
  "themes": ["Freedom vs. servitude", "Authentic love vs. transactional"]
}
```

---

### Character Schema (Expanded)

```json
{
  "tag": "CHAR_MEI",
  "name": "Mei",
  "role": "protagonist",

  "identity": {
    "age": "22-24",
    "ethnicity": "Han Chinese",
    "social_class": "Courtesan (lowest rung, but highest within her class)",
    "education": "Trained in poetry, calligraphy, music, Go, and the art of conversation",
    "backstory": "Sold to the brothel at age 12 after her father's debts...",
    "defining_moment": "The day she first saw Lin tending his orchids with such gentleness"
  },

  "visual": {
    "appearance": "Petite (5'3\"), ethereal beauty, long black hair...",
    "costume_default": "Blue silk kimono with orchid embroidery...",
    "costume_formal": "Red silk with gold accents for the Go game...",
    "distinguishing_marks": "Small scar on left wrist (hidden by sleeves)",
    "movement_style": "Trained grace, economical movements, always aware of being watched"
  },

  "internal_voice": {
    "self_talk_tone": "Critical, constantly measuring her worth against others' desires",
    "recurring_thoughts": [
      "Am I enough?",
      "What does he really want from me?",
      "Lin would never look at someone like me",
      "This is my one chance"
    ],
    "coping_mechanisms": [
      "Retreats into 'performance mode' when vulnerable",
      "Watches the orchids as meditation",
      "Counts her breaths to regain composure"
    ],
    "blind_spots": [
      "Cannot see that her strategic mind is valuable beyond seduction",
      "Doesn't recognize Lin's genuine interest"
    ],
    "inner_critic_voice": "You are a flower to be bought, nothing more",
    "inner_hope_voice": "There must be more than this"
  },

  "speech": {
    "vocabulary_level": "Refined, educated in poetry and classical texts",
    "sentence_structure": "Measured, deliberate pauses — she thinks before speaking",
    "verbal_habits": [
      "Deflects direct questions about feelings with questions",
      "Uses metaphor when discussing herself",
      "Quotes poetry when emotions run high"
    ],
    "topics_avoided": [
      "Her childhood before the brothel",
      "What happens after clients leave",
      "Her real feelings about her work"
    ],
    "topics_gravitated": [
      "Beauty, nature, the orchids",
      "Hypotheticals about 'another life'",
      "Art and poetry"
    ],
    "speech_rhythm": "Slow and deliberate, with strategic silences",
    "accent_dialect": "Refined Mandarin with occasional Suzhou inflections",
    "filler_words": ["perhaps", "one might say", "it is said that"],
    "oath_expressions": {
      "surprise": "Ai-ya!",
      "frustration": "*sharp intake of breath*",
      "delight": "How lovely..."
    },
    "example_dialogue": [
      "The orchids bloom whether anyone watches or not. Perhaps that is their wisdom.",
      "You ask what I want, General. A dangerous question to ask a woman who has nothing."
    ]
  },

  "physicality": {
    "baseline_posture": "Elegant, trained — spine straight, movements economical and graceful",
    "gait": "Glides rather than walks, small steps, hips don't sway",
    "nervous_tells": [
      "Touches her jade hairpin",
      "Looks toward the balcony/window",
      "Fingers trace the edge of her sleeve"
    ],
    "confident_tells": [
      "Slows her movements deliberately",
      "Holds eye contact longer than comfortable",
      "Allows strategic pauses before responding"
    ],
    "how_they_enter_a_room": "Glides in, aware of being watched, positions herself advantageously near light source",
    "how_they_sit": "Kneels formally but with practiced ease that makes it look effortless",
    "how_they_stand": "Weight slightly back, hands folded at waist, chin level",
    "touch_patterns": "Strategic — touches others purposefully to create intimacy, rarely accidentally",
    "personal_space": "Allows clients to enter her space; maintains distance with those she doesn't trust",
    "eye_contact_patterns": "Direct with clients (calculated), averted with Lin (genuine emotion)",
    "hand_gestures": "Minimal, graceful, often involving her sleeves",
    "facial_baseline": "Serene mask with hint of melancholy in the eyes"
  },

  "decision_making": {
    "primary_value": "Self-preservation through control",
    "secondary_value": "Dignity — she will not beg",
    "when_threatened": "Deploys charm as a shield, seeks to regain upper hand through wit",
    "when_vulnerable": "Masks with performance, only shows truth in solitude or with orchids",
    "when_cornered": "Goes quiet, calculates, then makes bold move (like proposing the Go game)",
    "risk_tolerance": "Will take calculated gambles if the alternative is continued captivity",
    "trust_threshold": "Very high — assumes ulterior motives until proven otherwise over time",
    "loyalty_hierarchy": ["Herself", "Her dream of freedom", "Madame Lixuan (grudging)", "Other courtesans"],
    "moral_lines": [
      "Will not betray another courtesan",
      "Will not harm innocents",
      "Will not lose her dignity even in defeat"
    ],
    "temptations": [
      "Genuine affection (Lin)",
      "Security without freedom (wealthy patron)",
      "Revenge on those who wronged her"
    ]
  },

  "emotional_baseline": {
    "default_mood": "Melancholic longing masked by composure",
    "stress_response": "Becomes MORE controlled, not less — tightens the mask",
    "joy_expression": "Rare, genuine smiles only when alone watching the orchids or thinking of Lin",
    "anger_expression": "Cold, precise — weaponized politeness",
    "fear_expression": "Stillness, careful breathing, hands hidden in sleeves",
    "sadness_expression": "Stares at distance, becomes quieter, touches her hairpin",
    "emotional_volatility": "Low — years of training to suppress",
    "emotional_recovery": "Slow in private, instant 'reset' when observed",
    "suppression_style": "Retreats into the 'courtesan mask' — perfect, serene, unreadable"
  },

  "emotional_tells": {
    "happiness": "Eyes soften, slight flush to cheeks, movements become less calculated",
    "sadness": "Becomes very still, gaze distant, fingers trace sleeve edges",
    "anger": "Voice drops lower, pauses become longer, perfect posture becomes rigid",
    "fear": "Breath shortens, touches hairpin, seeks exit routes with eyes",
    "surprise": "Slight widening of eyes, hand to chest, quick recovery to composure",
    "disgust": "Micro-expression of nose wrinkle, quickly hidden, creates distance",

    "annoyance": "Single slow blink, slight tightening of lips, redirects conversation",
    "intrigue": "Head tilts slightly, eyes narrow with interest, leans almost imperceptibly forward",
    "excitement": "Breath quickens, color rises, has to consciously slow movements",
    "embarrassment": "Looks down, color floods cheeks, fidgets with sleeve",
    "nervousness": "Touches hairpin repeatedly, glances at exits, speech becomes more formal",
    "confidence": "Chin lifts, movements slow to deliberate, holds eye contact",
    "vulnerability": "Voice softens, eyes become wet, breaks eye contact, hugs herself",
    "joy": "Genuine smile reaches eyes, posture relaxes, laughter like wind chimes",

    "attraction": "Dilated pupils, mirrors the other's posture, finds excuses to be closer",
    "crush": "Can't help looking at them, blushes when they notice, becomes clumsy",
    "intimacy": "Breath synchronizes, touches become lingering, words become whispers",
    "jealousy": "Jaw tightens, watches the rival intently, becomes falsely cheerful",
    "envy": "Studies what she lacks, becomes quiet, retreats into herself",
    "contempt": "Slight nostril flare, looks down and away, dismissive gestures",
    "admiration": "Eyes brighten, leans in, asks questions, remembers details",
    "gratitude": "Deep bow, voice trembles slightly, sustained eye contact",

    "pride": "Stands taller, chin lifts, allows herself a small smile",
    "shame": "Shoulders curl inward, cannot meet eyes, voice becomes small",
    "guilt": "Restless hands, difficulty staying present, apologizes excessively",
    "defeat": "All tension leaves body, head bows, long exhale, stillness",
    "triumph": "Flash of fierce joy in eyes, quickly controlled, gracious magnanimity",

    "focus": "World narrows to one point, breath slows, body becomes utterly still",
    "confusion": "Brow furrows, head tilts, repeats key words as questions",
    "curiosity": "Leans forward, eyes widen, asks 'why' and 'how'",
    "boredom": "Gaze drifts, posture loosens, answers become shorter",
    "frustration": "Controlled exhale, hands clench in sleeves, patience thins",

    "loneliness": "Stares at orchids, hugs herself, hums childhood melody",
    "belonging": "Shoulders relax, genuine smile, participates freely",
    "rejection": "Flinch quickly hidden, mask slams into place, dignified retreat",
    "acceptance": "Tears of relief, tension releases, allows herself to be held"
  },

  "relationships": {
    "CHAR_THE_GENERAL": {
      "type": "adversary/client",
      "history": "He has visited before, always with possessive intent",
      "current_dynamic": "Cat and mouse — she must win without him knowing he's being played",
      "what_she_shows": "Demure interest, subtle flattery, strategic availability",
      "what_she_hides": "Contempt for his arrogance, fear of becoming his possession"
    },
    "CHAR_LIN": {
      "type": "distant beloved/hope",
      "history": "Watched him for months from her balcony, never spoken",
      "current_dynamic": "He represents everything she wants — gentle love, simple beauty",
      "what_she_shows": "Nothing (too afraid to reveal her feelings)",
      "what_she_hides": "Deep romantic longing, belief she's unworthy of him"
    }
  },

  "arc": {
    "want": "To escape her life as a courtesan and find true love",
    "need": "To discover her worth beyond her beauty and take control of her destiny",
    "flaw": "Self-doubt about her value beyond physical beauty; passive acceptance until now",
    "arc_type": "positive",
    "ghost": "Being sold by her father — the moment she learned she was a commodity",
    "lie_believed": "She is only valuable for what men desire from her",
    "truth_to_learn": "Her strategic mind, her courage, her capacity to love are her true worth"
  },

  "world_context": {
    "social_position": "Highest-tier courtesan (yiji) — educated, artistic, expensive",
    "cultural_constraints": "Cannot leave brothel without purchase, must entertain clients, monitored",
    "period_specific_behaviors": [
      "Pours tea with specific graceful gestures",
      "Walks in tiny steps (trained, not foot-binding)",
      "Addresses men with honorifics always",
      "Never initiates physical contact"
    ],
    "historical_parallels": "Similar to Japanese geisha or Greek hetaira — high-class, educated",
    "anachronisms_to_avoid": [
      "Modern concepts of feminism or rights",
      "Casual physical affection in public",
      "Direct confrontation with men",
      "Discussion of romantic love openly"
    ]
  }
}
```

---

### Location Schema (Expanded)

```json
{
  "tag": "LOC_LIXUAN_BROTHEL",
  "name": "The Lixuan Pleasure House",

  "physical": {
    "architecture": "Three-story traditional Chinese building, upturned eaves, carved dragons/phoenixes",
    "dimensions": "30 meters wide, 15 meters deep, each floor 3.5 meters high",
    "materials": "Red-lacquered wood pillars, rice paper screens, bamboo flooring",
    "key_features": ["Mei's top-floor room with red balcony", "Central staircase", "Private chambers"]
  },

  "sensory": {
    "visual": "Red silk drapes, golden embroidery, candlelight on polished surfaces",
    "auditory": "Soft music from pipas, murmured conversation, silk rustling, distant street sounds",
    "olfactory": "Sandalwood incense, jasmine perfume, tea, subtle musk",
    "tactile": "Smooth silk, cool jade, warm wood, soft cushions"
  },

  "atmosphere": {
    "mood": "Luxurious yet confining — a gilded cage",
    "lighting": "Warm amber from oil lamps, dramatic shadows, intimate pools of light",
    "emotional_quality": "Sensual, secretive, melancholic beneath the beauty",
    "danger_level": "Socially dangerous (reputation), physically safe (protected)"
  },

  "time_period_details": {
    "era_specific_elements": [
      "Paper lanterns (no electricity)",
      "Charcoal braziers for heat",
      "Wooden lattice windows",
      "Ceramic chamber pots behind screens"
    ],
    "social_function": "Licensed entertainment house, regulated by local magistrate",
    "who_frequents": ["Wealthy merchants", "Government officials", "Military officers", "Scholars"],
    "economic_role": "Major tax revenue source, networking hub for powerful men"
  },

  "directional_views": {
    "north": "Main staircase, ornate banisters, paper screens dividing chambers",
    "east": "Mei's chamber — canopied bed, Go table, jade ornaments",
    "south": "Corridor to other courtesans' rooms, Madame's quarters",
    "west": "The famous red balcony overlooking the merchant district and Lin's flower shop"
  },

  "narrative_function": {
    "story_role": "Mei's prison, site of her gambit, place of transformation",
    "emotional_resonance": "Beautiful but suffocating, comfort that is also captivity",
    "key_scenes_here": ["Go game with General", "Mei watching Lin from balcony"]
  }
}
```

---

### Prop Schema (Expanded)

```json
{
  "tag": "PROP_GO_BOARD",
  "name": "Antique Go Game Set",

  "physical": {
    "materials": "Dark walnut board, lacquered finish, black slate stones, white clamshell stones",
    "dimensions": "19x19 inches board, 3/4 inch diameter stones",
    "condition": "Well-used, showing generations of play, some stones have hairline cracks",
    "craftsmanship": "Master-carved, likely 100+ years old"
  },

  "sensory": {
    "visual": "Grid catches candlelight, stones create organic patterns, lacquer gleams",
    "auditory": "Click of stone on wood, soft scrape when captured",
    "tactile": "Smooth cool stones, weight satisfying in palm, slight give of wooden legs"
  },

  "significance": {
    "narrative_function": "Instrument of Mei's gamble for freedom — the battlefield of wits",
    "symbolic_meaning": "Strategy over force, patience over aggression, Mei's hidden depths",
    "emotional_weight": "Life-changing object — success means freedom, failure means captivity"
  },

  "time_period_details": {
    "historical_context": "Go (Weiqi) as scholar's game, sign of refined intellect",
    "social_implications": "A woman playing Go is unusual — marks Mei as exceptional",
    "cultural_weight": "Formal wagers over Go are binding contracts in this society"
  },

  "associations": {
    "primary_character": "CHAR_MEI",
    "secondary_characters": ["CHAR_THE_GENERAL"],
    "location": "LOC_LIXUAN_BROTHEL"
  },

  "history": "Owned by the brothel for 80 years, used for entertainment and formal challenges"
}
```

---

## Agent Architecture for Character Embodiment

### Scene Context Flow

```
Scene Context Arrives
        ↓
Character Agent receives:
  - Full character profile (expanded schema above)
  - Current emotional state (modified by previous scenes)
  - Relationship states with other characters present
  - Scene goal from orchestrator
  - WORLD DETAILS (time period, cultural context, rules)
        ↓
Character Agent outputs:
  1. Internal state assessment (what they're feeling/thinking entering)
  2. What they WANT from this interaction
  3. What they're HIDING
  4. Proposed action/dialogue (with speech patterns)
  5. Physical behavior layer (using physicality + emotional_tells)
        ↓
Synthesis Agent weaves outputs into prose
        ↓
State updates fed back to character profiles
```

### Context Packet for Character Agent

```json
{
  "scene": {
    "number": 3,
    "location": "LOC_LIXUAN_BROTHEL",
    "present_characters": ["CHAR_MEI", "CHAR_THE_GENERAL"],
    "goal": "Mei proposes the Go game wager",
    "tension": 8
  },

  "world_context": {
    "time_period": "Ming Dynasty, 1500s",
    "cultural_rules": ["Women don't initiate", "Go wagers are binding"],
    "social_dynamic": "She is commodity, he is customer with power"
  },

  "character_state": {
    "tag": "CHAR_MEI",
    "entering_emotion": "nervousness masked by confidence performance",
    "relationship_to_present": {
      "CHAR_THE_GENERAL": "adversary, fears becoming his possession"
    },
    "active_want": "Propose the game without appearing desperate",
    "active_hide": "Her terror, her love for Lin, her strategic genius"
  },

  "character_profile": { /* Full expanded profile */ }
}
```

### Agent Output Format

```json
{
  "internal_monologue": "This is my one chance. If I tremble, he'll see weakness. Breathe. Be the courtesan they trained you to be — but use it for yourself.",

  "wants_from_scene": "To get him to agree to the wager without realizing she's the better player",

  "hiding": ["Desperation", "Strategic mind", "That she's studied his previous games"],

  "action_sequence": [
    {
      "beat": 1,
      "action": "Pours tea with deliberate grace, allowing silence to build",
      "physical": "Hands steady through sheer will, breath slow and measured",
      "internal": "Don't speak first. Let him fill the silence."
    },
    {
      "beat": 2,
      "dialogue": "General Chen, you honor this humble house. I find myself curious about a man of your... strategic reputation.",
      "delivery": "Voice low, measured, with a deliberate pause before 'strategic'",
      "physical": "Eyes meet his, holds contact one beat longer than comfortable"
    }
  ],

  "emotional_exit_state": "nervousness transforming to focused determination"
}
```

---

## Expanded Emotional Tells (Full List)

### Basic Emotions (6)
- happiness, sadness, anger, fear, surprise, disgust

### Complex Emotions (8)
- annoyance, intrigue, excitement, embarrassment
- nervousness, confidence, vulnerability, joy

### Interpersonal Emotions (8)
- attraction, crush, intimacy, jealousy
- envy, contempt, admiration, gratitude

### Achievement/Status Emotions (5)
- pride, shame, guilt, defeat, triumph

### Cognitive States (5)
- focus, confusion, curiosity, boredom, frustration

### Social Emotions (4)
- loneliness, belonging, rejection, acceptance

**Total: 36 distinct emotional states with physiological tells**

---

## Context Compiler Changes

### Remove Word Limits for World Config Building

Current:
```python
STORY_SEED_WORD_LIMIT = 50
CHARACTER_CARD_WORD_LIMIT = 40
LOCATION_CARD_WORD_LIMIT = 30
PROP_CARD_WORD_LIMIT = 20
```

Proposed:
```python
# Full context mode for character embodiment agents
CHARACTER_FULL_PROFILE = True  # No compression
LOCATION_FULL_PROFILE = True
PROP_FULL_PROFILE = True

# Compressed mode for brainstorm/outline agents (original limits)
COMPRESSED_MODE_LIMITS = {
    "story_seed": 50,
    "character_card": 40,
    "location_card": 30,
    "prop_card": 20
}
```

### New Context Delivery Methods

```python
def for_character_embodiment_agent(
    self,
    character_tag: str,
    scene_context: Dict,
    relationship_states: Dict
) -> str:
    """
    Full character profile for embodiment agents.
    No compression - new context engine handles parsing.
    """
    pass

def for_dialogue_agent(
    self,
    speaking_character: str,
    listening_characters: List[str],
    scene_context: Dict
) -> str:
    """
    Speech patterns + relationships + world context.
    """
    pass

def for_movement_agent(
    self,
    character_tag: str,
    emotional_state: str,
    scene_context: Dict
) -> str:
    """
    Physicality + emotional_tells for specific state.
    """
    pass
```

---

## Research Agent Prompt Updates

### Current Problem
Research agents receive limited context:
```python
prompt = f"""Research the following character from a {self.focus} perspective.

CHARACTER TAG: {tag}
PITCH CONTEXT: {pitch}
TIME PERIOD: {time_period}
GENRE: {genre}
```

### Proposed: Full World Context Injection

```python
prompt = f"""Research the following character from a {self.focus} perspective.

CHARACTER TAG: {tag}

=== WORLD CONTEXT (Use this for ALL decisions) ===
TIME PERIOD: {world_details['time_period']['era']}
HISTORICAL EVENTS: {world_details['time_period']['historical_events']}
SOCIAL HIERARCHY: {world_details['cultural_context']['social_hierarchy']}
GENDER ROLES: {world_details['cultural_context']['gender_roles']}
CULTURAL TABOOS: {world_details['cultural_context']['taboos']}
CUSTOMS: {world_details['cultural_context']['customs']}
LANGUAGE REGISTER: {world_details['cultural_context']['language_register']}

=== AESTHETIC CONTEXT ===
VISUAL STYLE: {visual_style}
STYLE NOTES: {style_notes}
COLOR SYMBOLISM: {world_details['aesthetic_context']['color_symbolism']}

=== STORY CONTEXT ===
GENRE: {genre}
THEMES: {themes}
WORLD RULES: {world_rules}

=== PITCH ===
{pitch}

=== YOUR RESEARCH FOCUS: {focus_description} ===
{focus_specific_instructions}

CRITICAL: All character details MUST be authentic to the time period and cultural context above.
Avoid anachronisms. Reference specific historical parallels where appropriate.
"""
```

---

## Migration Strategy

### Phase 1: Schema Update
1. Update `CharacterProfile`, `LocationProfile`, `PropProfile` dataclasses
2. Add `world_details` to top-level world_config schema
3. Maintain backward compatibility with legacy fields

### Phase 2: Research Agent Updates
1. Inject full world_context into all research agent prompts
2. Add new research focuses: "internal_voice", "decision_making", "emotional_baseline"
3. Expand emotional tells generation to 36 emotions

### Phase 3: Context Delivery Updates
1. Add `for_character_embodiment_agent()` method
2. Add `for_dialogue_agent()` method
3. Add `for_movement_agent()` method
4. Create toggle for compressed vs. full context mode

### Phase 4: Agent Architecture
1. Implement Character Embodiment Agent
2. Implement Dialogue Synthesis Agent
3. Implement Movement/Gesture Agent
4. Create State Update pipeline for emotional continuity

---

## Open Questions for Discussion

1. **Emotional State Persistence**: How long should emotional states carry across scenes? Decay function?

2. **Relationship Evolution**: Should relationships update automatically based on scene events, or require explicit orchestrator commands?

3. **Context Token Budget**: With full profiles, what's the new token budget per agent call? How does the new context engine handle this?

4. **Backward Compatibility**: Keep generating legacy compressed cards for existing pipelines while adding full profiles for new embodiment agents?

5. **Research Depth**: How many parallel research agents per character for the expanded schema? Current is 6 focuses — expand to 10?

6. **Validation**: How do we validate that generated profiles are period-accurate? Human review? Dedicated validation agent?

---

## Example: Full Character Generation Flow

```
Input: CHAR_MEI tag + pitch + world_details

Step 1: Identity Research Agent
  → name, age, ethnicity, social_class, backstory, defining_moment

Step 2: Internal Voice Research Agent
  → self_talk_tone, recurring_thoughts, coping_mechanisms, blind_spots

Step 3: Speech Research Agent
  → vocabulary, sentence_structure, verbal_habits, topics, example_dialogue

Step 4: Physicality Research Agent
  → posture, gait, nervous_tells, confident_tells, touch_patterns

Step 5: Decision Making Research Agent
  → values, threat_response, vulnerability_response, moral_lines

Step 6: Emotional Baseline Research Agent
  → default_mood, stress_response, expressions by emotion type

Step 7: World Context Research Agent
  → social_position, cultural_constraints, period_behaviors, anachronisms

Step 8: Emotional Tells Generation (36 emotions × Haiku)
  → Parallel generation of physiological tells for each emotion

Step 9: Relationship Research Agent
  → For each other character: type, history, dynamic, shows, hides

Step 10: Arc Research Agent
  → want, need, flaw, ghost, lie_believed, truth_to_learn

Synthesis: Merge all into final CharacterProfile
Validation: Check for period accuracy, internal consistency
Output: Full JSON profile ready for agent embodiment
```

---

## Next Steps

1. Review this design document
2. Discuss open questions
3. Prioritize which sections to implement first
4. Determine if any aspects need further elaboration
5. Create implementation tickets for the agent to execute
