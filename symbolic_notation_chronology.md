# Proposed Story & Context Pipeline v3.0

## Executive Summary

This document proposes a **Symbolic Rubric System** for dissecting, notating, and manipulating scripts at a granular level. The system uses **literal unique symbols** that represent specific narrative positions, character hierarchies, temporal events, and plot mechanics - enabling true RAG-based retrieval and complete control over context delivery.

---

## Table of Contents

1. [Symbolic Rubric System](#1-symbolic-rubric-system)
2. [Symbol Notation Reference](#2-symbol-notation-reference)
3. [Script Dissection Protocol](#3-script-dissection-protocol)
4. [Context Engine Architecture](#4-context-engine-architecture)
5. [Context Control Rubric](#5-context-control-rubric)
6. [Agent Context Delivery](#6-agent-context-delivery)
7. [Story Pipeline Phases](#7-story-pipeline-phases)
8. [Implementation Roadmap](#8-implementation-roadmap)

---

## 1. Symbolic Rubric System

### 1.1 Core Philosophy

The rubric uses **literal symbols** - not descriptive tags - to represent:

| Concept | Symbol Type | Example | Meaning |
|---------|-------------|---------|---------|
| Position in narrative | `[S.B.C]` | `[3.2.A]` | Scene 3, Beat 2, Camera A |
| Character hierarchy | `P#` | `P1` | Protagonist 1 (main) |
| Rise/Fall dynamics | `↑↓` | `P1↑` | Protagonist 1 rising |
| Plot point markers | `◆○` | `◆1` | Plot point 1 opens |
| Temporal anchors | `T:` | `T:0` | Timeline origin |
| State transitions | `→` | `P1:fear→hope` | State change |

### 1.2 Symbol Categories

```
POSITION NOTATION
─────────────────────────────────────────────────────────────
[S.B]       Scene.Beat              [3.2] = Scene 3, Beat 2
[S.B.C]     Scene.Beat.Camera       [3.2.A] = Scene 3, Beat 2, Camera A
[S.B:L]     Scene.Beat:Line         [3.2:14] = Scene 3, Beat 2, Line 14
{S-S}       Scene Range             {3-5} = Scenes 3 through 5
<B-B>       Beat Range              <2-4> = Beats 2 through 4

CHARACTER HIERARCHY
─────────────────────────────────────────────────────────────
P1          Primary Protagonist     Main character
P2          Secondary Protagonist   Second lead
P3-P9       Supporting Protagonists Additional leads
A1          Primary Antagonist      Main opposition
A2-A9       Supporting Antagonists  Additional opposition
N1-N99      Named Characters        Non-protagonist named characters
X           Unnamed/Crowd           Background characters

RISE/FALL DYNAMICS (attach to character)
─────────────────────────────────────────────────────────────
↑           Rising                  P1↑ = Protagonist 1 ascending
↓           Falling                 A1↓ = Antagonist 1 declining
↕           Oscillating             P1↕ = Unstable state
─           Flat/Static             P2─ = No change
⤴           Recovery                P1⤴ = Bouncing back
⤵           Decline                 A1⤵ = Beginning fall
∿           Wavering                P1∿ = Uncertain trajectory

PLOT POINT MARKERS
─────────────────────────────────────────────────────────────
◆1          Plot Point 1 Opens      Inciting incident begins
◇1          Plot Point 1 Closes     Inciting incident resolves
◆2          Plot Point 2 Opens      Second major turn begins
◇2          Plot Point 2 Closes     Second major turn resolves
◆M          Midpoint Opens          Central pivot begins
◇M          Midpoint Closes         Central pivot completes
◆C          Climax Opens            Final confrontation begins
◇C          Climax Closes           Resolution achieved
●           Setup planted           Something introduced
○           Payoff delivered        Setup resolved

TEMPORAL MARKERS
─────────────────────────────────────────────────────────────
T:0         Timeline Origin         Story present (baseline)
T:-1        Past Event 1            First flashback layer
T:-2        Past Event 2            Deeper past
T:+1        Future Event 1          Flash forward
T:+2        Future Event 2          Further future
T:‖         Parallel Time           Simultaneous events
T:∞         Timeless                Outside normal time
T:?         Unknown Time            Temporal ambiguity

SEQUENCE MARKERS
─────────────────────────────────────────────────────────────
»           Flows to                [3.1]»[3.2] = Beat 1 leads to 2
⊣           Interrupts              [3.2]⊣[3.1] = Beat 2 cuts into 1
⊢           Resumes                 [3.3]⊢[3.1] = Resumes from Beat 1
∥           Parallel with           [3.1]∥[4.1] = Simultaneous
⟲           Loops back              [5.1]⟲[2.1] = Returns to earlier
⟳           Advances to             [2.1]⟳[5.1] = Jumps forward

STATE NOTATION
─────────────────────────────────────────────────────────────
:           State indicator         P1:fear = P1 in fear state
→           State transition        P1:fear→hope = Changes from fear to hope
⇒           Forced transition       P1:fear⇒anger = Externally caused
⇔           Oscillating states      P1:love⇔hate = Alternating
∅           Null state              P1:∅ = Absent/unconscious

INTENSITY MARKERS
─────────────────────────────────────────────────────────────
¹           Low intensity           P1:fear¹ = Mild fear
²           Medium intensity        P1:fear² = Moderate fear
³           High intensity          P1:fear³ = Intense fear
⁺           Increasing              P1:fear⁺ = Fear growing
⁻           Decreasing              P1:fear⁻ = Fear fading

RELATIONSHIP MARKERS
─────────────────────────────────────────────────────────────
P1~P2       Bonded                  Characters connected
P1≁P2       Broken                  Connection severed
P1>A1       Dominates               Power over
P1<A1       Submits                 Power under
P1><A1      Conflict                In opposition
P1<>P2      Mutual                  Reciprocal dynamic
P1—N1       Neutral                 No strong dynamic
```

---

## 2. Symbol Notation Reference

### 2.1 Complete Symbol Vocabulary

#### EMOTIONAL STATES (lowercase, attachable)
```
fear        hope        anger       joy
sorrow      desire      love        hate
guilt       shame       pride       envy
relief      dread       peace       rage
trust       doubt       shock       calm
lust        disgust     wonder      bored
```

#### ACTIONS (verb form, timestamped)
```
reveal[T]   conceal[T]  confront[T] flee[T]
fight[T]    surrender[T] choose[T]   refuse[T]
betray[T]   forgive[T]  sacrifice[T] deceive[T]
confess[T]  accuse[T]   defend[T]   attack[T]
promise[T]  break[T]    steal[T]    give[T]
discover[T] create[T]   destroy[T]  heal[T]
```

#### THEMATIC MARKERS (prefix: θ)
```
θFREEDOM    θCAPTIVITY  θPOWER      θIDENTITY
θREDEMPTION θSACRIFICE  θTRUTH      θDECEPTION
θLOVE       θLOSS       θJUSTICE    θCHAOS
θBELONGING  θISOLATION  θMORTALITY  θLEGACY
θINNOCENCE  θCORRUPTION θFATE       θFREEWILL
```

#### STRUCTURAL MARKERS (prefix: σ)
```
σLINEAR     σNONLINEAR  σCIRCULAR   σPARALLEL
σFRAME      σNESTED     σSPIRAL     σMOSAIC
σ3ACT       σ5ACT       σHERO       σSAVECAT
```

### 2.2 Notation Composition

Symbols combine to create precise narrative coordinates:

```
BASIC COMPOSITION
─────────────────────────────────────────────────────────────
[3.2]:P1↑:fear→hope
│  │  │ │ │    │
│  │  │ │ │    └── Exit state
│  │  │ │ └─────── Entry state
│  │  │ └───────── Dynamic (rising)
│  │  └─────────── Character (Protagonist 1)
│  └────────────── Beat number
└───────────────── Scene number

FULL NOTATION EXAMPLE
─────────────────────────────────────────────────────────────
[3.2]:P1↑:fear²→hope³|T:0|◆2|P1>A1|θPOWER
  │    │  │         │   │   │     │
  │    │  │         │   │   │     └── Theme active
  │    │  │         │   │   └──────── Relationship dynamic
  │    │  │         │   └──────────── Plot point 2 opening
  │    │  │         └──────────────── Timeline position
  │    │  └────────────────────────── State transition w/intensity
  │    └───────────────────────────── Character + dynamic
  └────────────────────────────────── Position

COMPACT FORM (for inline use)
─────────────────────────────────────────────────────────────
[3.2]P1↑         Position + character + dynamic
P1:fear→hope    State transition only
◆2[3.2]          Plot point at position
T:-1[2.4]        Temporal marker at position
```

### 2.3 Notation Examples

**Scene opening with character states:**
```
[1.1]:P1─:neutral|P2:curious|A1:confident|T:0|◆1
```
*Scene 1, Beat 1. P1 flat/neutral, P2 curious, A1 confident. Timeline origin. Plot point 1 opens.*

**State change mid-beat:**
```
[3.2]:P1↓:hope³→fear²|A1↑:calm→triumphant
```
*Scene 3, Beat 2. P1 falling from intense hope to moderate fear. A1 rising from calm to triumphant.*

**Flashback reference:**
```
[5.1]:T:-1|[2.3]⟲|P1:sorrow³|●trauma
```
*Scene 5, Beat 1. Flashback (T:-1). Loops back to Scene 2 Beat 3. P1 in intense sorrow. Plants trauma setup.*

**Non-linear jump:**
```
[7.1]:T:+1|[7.1]⟳[9.3]|P1:dead|A1:victorious
```
*Scene 7, Beat 1. Flash forward. Jumps to Scene 9 Beat 3. P1 dead. A1 victorious.*

**Plot point resolution:**
```
[8.4]:◇1|●betrayal→○betrayal|P1↑:rage→resolve|θJUSTICE
```
*Scene 8, Beat 4. Plot point 1 closes. Betrayal setup pays off. P1 rises from rage to resolve. Justice theme.*

---

## 3. Script Dissection Protocol

### 3.1 Dissection Hierarchy

```
SCRIPT
└── ACT
    └── SEQUENCE
        └── SCENE
            └── BEAT
                └── LINE
                    └── MOMENT
```

Each level receives notation:

```
ACT LEVEL
─────────────────────────────────────────────────────────────
{A1}        Act 1 boundary
{A2}        Act 2 boundary
{A3}        Act 3 boundary
{A1-A2}     Act transition

SEQUENCE LEVEL
─────────────────────────────────────────────────────────────
{SEQ:1}     Sequence 1 (e.g., "The Setup")
{SEQ:2}     Sequence 2 (e.g., "Fun and Games")
{SEQ→}      Sequence flows forward
{SEQ⊣}      Sequence interrupted

SCENE LEVEL
─────────────────────────────────────────────────────────────
[S]         Scene number
[S]:INT/EXT Interior/Exterior
[S]:DAY/NIGHT Time of day
[S]:@LOC     Location entity

BEAT LEVEL
─────────────────────────────────────────────────────────────
[S.B]       Scene.Beat
[S.B]:P#    Character focus
[S.B]:●/○   Setup/Payoff

LINE LEVEL
─────────────────────────────────────────────────────────────
[S.B:L]     Scene.Beat:Line number
[S.B:L]:D   Dialogue line
[S.B:L]:A   Action line
[S.B:L]:V   Visual description

MOMENT LEVEL
─────────────────────────────────────────────────────────────
[S.B:L.M]   Scene.Beat:Line.Moment
μ           Micro-moment marker
μ:P1        Character micro-moment
```

### 3.2 Dissection Output Structure

```json
{
  "script_id": "beta_test_v1",
  "notation_version": "3.0",
  "structure": "σ3ACT",

  "timeline": {
    "T:0": "Story present",
    "T:-1": "3 years ago - Mei first sees Lin",
    "T:-2": "5 years ago - Mei sold to teahouse"
  },

  "characters": {
    "P1": {"entity": "@CHAR_MEI", "name": "Mei", "arc": "↓→↑"},
    "P2": {"entity": "@CHAR_LIN", "name": "Lin", "arc": "─→↑"},
    "A1": {"entity": "@CHAR_THE_GENERAL", "name": "General Wei", "arc": "↑→↓"}
  },

  "plot_points": {
    "◆1": {"position": "[1.3]", "description": "General proposes wager"},
    "◆M": {"position": "[4.2]", "description": "Mei gains upper hand"},
    "◆2": {"position": "[6.1]", "description": "General suspects deception"},
    "◆C": {"position": "[8.1]", "description": "Final move"}
  },

  "beats": [
    {
      "id": "[1.1]",
      "position": {"act": 1, "scene": 1, "beat": 1},
      "content": "Mei prepares for evening, gazes at Lin's shop...",
      "notation": "[1.1]:P1─:longing²|T:0|@LOC_TEAHOUSE|θFREEDOM",
      "states": {
        "P1": {"in": "longing²", "out": "longing²", "dynamic": "─"},
        "P2": {"in": null, "out": null, "dynamic": null},
        "A1": {"in": null, "out": null, "dynamic": null}
      },
      "setups": [],
      "payoffs": [],
      "temporal": "T:0"
    },
    {
      "id": "[1.2]",
      "position": {"act": 1, "scene": 1, "beat": 2},
      "content": "General Wei enters, eyes fixed on Mei...",
      "notation": "[1.2]:P1↓:longing→dread|A1↑:calm:predatory|P1<A1",
      "states": {
        "P1": {"in": "longing²", "out": "dread²", "dynamic": "↓"},
        "A1": {"in": "calm", "out": "predatory", "dynamic": "↑"}
      },
      "setups": ["●POWER_DYNAMIC", "●GENERAL_OBSESSION"],
      "payoffs": [],
      "temporal": "T:0"
    }
  ]
}
```

### 3.3 Auto-Dissection Process

```python
class ScriptDissector:
    """
    Dissects prose into symbolically-notated beats.
    """

    def __init__(self, character_map: Dict[str, str], symbol_registry: SymbolRegistry):
        self.char_map = character_map  # {"Mei": "P1", "Lin": "P2", ...}
        self.registry = symbol_registry

    def dissect(self, script: str) -> DissectedScript:
        """
        Full script dissection with symbolic notation.
        """
        # Step 1: Split into scenes
        scenes = self._split_scenes(script)

        # Step 2: Split scenes into beats
        all_beats = []
        for scene_num, scene_content in enumerate(scenes, 1):
            beats = self._split_beats(scene_content, scene_num)
            all_beats.extend(beats)

        # Step 3: Analyze each beat
        notated_beats = []
        for beat in all_beats:
            notated = self._analyze_beat(beat)
            notated_beats.append(notated)

        # Step 4: Track arcs and dynamics
        self._compute_dynamics(notated_beats)

        # Step 5: Identify plot points
        plot_points = self._identify_plot_points(notated_beats)

        # Step 6: Build timeline
        timeline = self._build_timeline(notated_beats)

        return DissectedScript(
            beats=notated_beats,
            plot_points=plot_points,
            timeline=timeline,
            character_arcs=self._compute_arcs(notated_beats)
        )

    def _analyze_beat(self, beat: RawBeat) -> NotatedBeat:
        """
        Analyze a single beat and generate notation.
        """
        content = beat.content

        # Identify characters present
        chars_present = []
        for name, symbol in self.char_map.items():
            if name.lower() in content.lower():
                chars_present.append(symbol)

        # Detect emotional states
        states = {}
        for char in chars_present:
            state = self._detect_state(content, char)
            states[char] = state

        # Detect dynamics (rising/falling)
        dynamics = {}
        for char in chars_present:
            dyn = self._detect_dynamic(content, char)
            dynamics[char] = dyn

        # Detect setups and payoffs
        setups = self._detect_setups(content)
        payoffs = self._detect_payoffs(content)

        # Detect temporal markers
        temporal = self._detect_temporal(content)

        # Detect themes
        themes = self._detect_themes(content)

        # Detect relationships
        relationships = self._detect_relationships(content, chars_present)

        # Build notation string
        notation = self._build_notation(
            position=f"[{beat.scene}.{beat.beat_num}]",
            chars=chars_present,
            states=states,
            dynamics=dynamics,
            temporal=temporal,
            themes=themes,
            setups=setups,
            payoffs=payoffs,
            relationships=relationships
        )

        return NotatedBeat(
            id=f"[{beat.scene}.{beat.beat_num}]",
            content=content,
            notation=notation,
            characters=chars_present,
            states=states,
            dynamics=dynamics,
            setups=setups,
            payoffs=payoffs,
            temporal=temporal,
            themes=themes,
            relationships=relationships
        )

    def _detect_state(self, content: str, char: str) -> str:
        """Detect emotional state for character in content."""
        # State keyword detection
        state_keywords = {
            'fear': ['afraid', 'scared', 'terrified', 'trembled', 'dread'],
            'hope': ['hoped', 'hopeful', 'optimistic', 'brightened'],
            'anger': ['angry', 'furious', 'rage', 'seething'],
            'desire': ['wanted', 'longed', 'craved', 'yearned', 'desired'],
            'love': ['loved', 'adored', 'cherished'],
            'sorrow': ['sad', 'wept', 'mourned', 'grieved'],
            'calm': ['calm', 'peaceful', 'serene', 'composed'],
            'dread': ['dreaded', 'apprehensive', 'anxious'],
            'triumph': ['triumphant', 'victorious', 'exultant'],
            'shame': ['ashamed', 'humiliated', 'embarrassed']
        }

        content_lower = content.lower()
        for state, keywords in state_keywords.items():
            for keyword in keywords:
                if keyword in content_lower:
                    # Detect intensity
                    intensity = self._detect_intensity(content, keyword)
                    return f"{state}{intensity}"

        return "neutral"

    def _detect_intensity(self, content: str, keyword: str) -> str:
        """Detect intensity markers (¹²³)."""
        intensifiers = {
            '³': ['very', 'extremely', 'intensely', 'deeply', 'utterly'],
            '²': ['quite', 'rather', 'somewhat'],
            '¹': ['slightly', 'barely', 'a little']
        }

        content_lower = content.lower()
        # Check for intensifier near keyword
        for level, words in intensifiers.items():
            for word in words:
                if word in content_lower:
                    return level

        return '²'  # Default medium intensity

    def _detect_dynamic(self, content: str, char: str) -> str:
        """Detect arc dynamic (↑↓─↕)."""
        rising_keywords = ['grew', 'strengthened', 'rose', 'brightened', 'gained']
        falling_keywords = ['fell', 'weakened', 'diminished', 'faded', 'lost']
        oscillating_keywords = ['wavered', 'fluctuated', 'alternated']

        content_lower = content.lower()

        if any(k in content_lower for k in rising_keywords):
            return '↑'
        elif any(k in content_lower for k in falling_keywords):
            return '↓'
        elif any(k in content_lower for k in oscillating_keywords):
            return '↕'
        else:
            return '─'

    def _detect_setups(self, content: str) -> List[str]:
        """Detect story setups (●)."""
        setups = []
        setup_patterns = [
            (r'first time', 'FIRST_MEETING'),
            (r'promise', 'PROMISE'),
            (r'secret', 'SECRET'),
            (r'hidden', 'HIDDEN'),
            (r'plans? to', 'PLAN'),
            (r'if only', 'DESIRE'),
            (r'one day', 'FUTURE_HOPE'),
        ]

        for pattern, label in setup_patterns:
            if re.search(pattern, content.lower()):
                setups.append(f"●{label}")

        return setups

    def _detect_payoffs(self, content: str) -> List[str]:
        """Detect story payoffs (○)."""
        payoffs = []
        payoff_patterns = [
            (r'finally', 'RESOLUTION'),
            (r'at last', 'COMPLETION'),
            (r'realized', 'REALIZATION'),
            (r'understood', 'UNDERSTANDING'),
            (r'revealed', 'REVEAL'),
        ]

        for pattern, label in payoff_patterns:
            if re.search(pattern, content.lower()):
                payoffs.append(f"○{label}")

        return payoffs

    def _build_notation(
        self,
        position: str,
        chars: List[str],
        states: Dict[str, str],
        dynamics: Dict[str, str],
        temporal: str,
        themes: List[str],
        setups: List[str],
        payoffs: List[str],
        relationships: List[str]
    ) -> str:
        """Build complete notation string."""
        parts = [position]

        # Character states and dynamics
        for char in chars:
            state = states.get(char, 'neutral')
            dyn = dynamics.get(char, '─')
            parts.append(f"{char}{dyn}:{state}")

        # Temporal
        if temporal:
            parts.append(f"|{temporal}")

        # Setups/Payoffs
        if setups:
            parts.append(f"|{'|'.join(setups)}")
        if payoffs:
            parts.append(f"|{'|'.join(payoffs)}")

        # Themes
        if themes:
            parts.append(f"|{'|'.join(themes)}")

        # Relationships
        if relationships:
            parts.append(f"|{'|'.join(relationships)}")

        return ''.join(parts)
```

---

## 4. Context Engine Architecture

### 4.1 Core Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SYMBOLIC CONTEXT ENGINE v3.0                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        NOTATION INDEX                                 │   │
│  │                                                                       │   │
│  │  Position Index:  [S.B] → Beat data                                  │   │
│  │  Character Index: P# → All beats with character                       │   │
│  │  Dynamic Index:   ↑/↓/─ → All beats with dynamic                      │   │
│  │  State Index:     state → All beats with state                        │   │
│  │  Plot Index:      ◆/◇/●/○ → All plot points                          │   │
│  │  Temporal Index:  T:# → All temporal markers                          │   │
│  │  Theme Index:     θ → All thematic beats                              │   │
│  │  Relation Index:  P#~P# → All relationship beats                      │   │
│  │                                                                       │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                           │
│  ┌───────────────────────────────▼──────────────────────────────────────┐   │
│  │                        QUERY ENGINE                                   │   │
│  │                                                                       │   │
│  │  Query Types:                                                         │   │
│  │  ─────────────────────────────────────────────────────                │   │
│  │  1. Position Query:  [3.2] → exact beat                               │   │
│  │  2. Range Query:     {3-5} → all beats in range                       │   │
│  │  3. Character Query: P1↑ → all P1 rising moments                      │   │
│  │  4. State Query:     P1:fear → all P1 fear states                     │   │
│  │  5. Plot Query:      ◆* → all plot point openings                     │   │
│  │  6. Temporal Query:  T:-1 → all flashbacks                            │   │
│  │  7. Theme Query:     θFREEDOM → all freedom beats                     │   │
│  │  8. Compound Query:  P1↑ & θFREEDOM & {5-8}                           │   │
│  │  9. Arc Query:       P1:fear→hope → all state transitions             │   │
│  │  10. Sequence Query: [3.1]»* → all beats following 3.1                │   │
│  │                                                                       │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                           │
│  ┌───────────────────────────────▼──────────────────────────────────────┐   │
│  │                      CONTEXT COMPILER                                 │   │
│  │                                                                       │   │
│  │  Compile Modes:                                                       │   │
│  │  ─────────────────────────────────────────────────────                │   │
│  │  1. FULL:     Complete beat with all notation                         │   │
│  │  2. SUMMARY:  Compressed beat summary                                 │   │
│  │  3. NOTATION: Just the notation string                                │   │
│  │  4. PROSE:    Just the content                                        │   │
│  │  5. STATE:    Just character states                                   │   │
│  │  6. POSITION: Just position markers                                   │   │
│  │                                                                       │   │
│  │  Token Budgets:                                                       │   │
│  │  ─────────────────────────────────────────────────────                │   │
│  │  MICRO:  50 words   (notation + state only)                           │   │
│  │  SMALL:  100 words  (summary + key info)                              │   │
│  │  MEDIUM: 200 words  (full beat context)                               │   │
│  │  LARGE:  400 words  (beat + surrounding)                              │   │
│  │                                                                       │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                           │
│  ┌───────────────────────────────▼──────────────────────────────────────┐   │
│  │                      CONTEXT PACKET                                   │   │
│  │                                                                       │   │
│  │  Agent receives precisely controlled context:                         │   │
│  │  - Position markers for navigation                                    │   │
│  │  - Character states (in/out)                                          │   │
│  │  - Active setups requiring payoff                                     │   │
│  │  - Recent dynamics (who rising/falling)                               │   │
│  │  - Temporal position                                                  │   │
│  │  - Theme emphasis                                                     │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Notation Index Implementation

```python
class NotationIndex:
    """
    Multi-dimensional index for symbolic notation queries.
    """

    def __init__(self):
        # Primary indices
        self.position_index: Dict[str, NotatedBeat] = {}      # "[3.2]" → Beat
        self.character_index: Dict[str, Set[str]] = {}        # "P1" → {beat_ids}
        self.dynamic_index: Dict[str, Set[str]] = {}          # "↑" → {beat_ids}
        self.state_index: Dict[str, Set[str]] = {}            # "fear" → {beat_ids}
        self.plot_index: Dict[str, Set[str]] = {}             # "◆1" → {beat_ids}
        self.temporal_index: Dict[str, Set[str]] = {}         # "T:-1" → {beat_ids}
        self.theme_index: Dict[str, Set[str]] = {}            # "θFREEDOM" → {beat_ids}
        self.setup_index: Dict[str, str] = {}                 # "●PROMISE" → beat_id
        self.payoff_index: Dict[str, str] = {}                # "○PROMISE" → beat_id

        # Sequence tracking
        self.sequence: List[str] = []  # Ordered list of beat_ids

        # Character state tracking (for transitions)
        self.char_states: Dict[str, List[Tuple[str, str]]] = {}  # P1 → [(beat_id, state)]

    def index_beat(self, beat: NotatedBeat):
        """Index a single beat across all dimensions."""
        beat_id = beat.id

        # Position
        self.position_index[beat_id] = beat
        self.sequence.append(beat_id)

        # Characters
        for char in beat.characters:
            if char not in self.character_index:
                self.character_index[char] = set()
            self.character_index[char].add(beat_id)

            # Track state progression
            if char not in self.char_states:
                self.char_states[char] = []
            state = beat.states.get(char, 'neutral')
            self.char_states[char].append((beat_id, state))

        # Dynamics
        for char, dyn in beat.dynamics.items():
            if dyn not in self.dynamic_index:
                self.dynamic_index[dyn] = set()
            self.dynamic_index[dyn].add(beat_id)

        # States
        for char, state in beat.states.items():
            # Strip intensity for indexing
            base_state = re.sub(r'[¹²³⁺⁻]', '', state)
            if base_state not in self.state_index:
                self.state_index[base_state] = set()
            self.state_index[base_state].add(beat_id)

        # Setups
        for setup in beat.setups:
            self.setup_index[setup] = beat_id
            if setup not in self.plot_index:
                self.plot_index[setup] = set()
            self.plot_index[setup].add(beat_id)

        # Payoffs
        for payoff in beat.payoffs:
            self.payoff_index[payoff] = beat_id
            if payoff not in self.plot_index:
                self.plot_index[payoff] = set()
            self.plot_index[payoff].add(beat_id)

        # Temporal
        if beat.temporal:
            if beat.temporal not in self.temporal_index:
                self.temporal_index[beat.temporal] = set()
            self.temporal_index[beat.temporal].add(beat_id)

        # Themes
        for theme in beat.themes:
            if theme not in self.theme_index:
                self.theme_index[theme] = set()
            self.theme_index[theme].add(beat_id)

    def query(self, query_string: str) -> List[NotatedBeat]:
        """
        Execute a symbolic query.

        Examples:
        - "[3.2]"           → Exact beat
        - "{3-5}"           → Scene range
        - "P1↑"             → P1 rising
        - "P1:fear"         → P1 in fear state
        - "P1:fear→hope"    → P1 fear to hope transitions
        - "◆*"              → All plot openings
        - "●PROMISE"        → Specific setup
        - "T:-1"            → All flashbacks
        - "θFREEDOM"        → All freedom themes
        - "P1↑ & θFREEDOM"  → Compound query
        """
        # Parse query
        if ' & ' in query_string:
            # Compound query - intersection
            parts = query_string.split(' & ')
            results = None
            for part in parts:
                part_results = set(b.id for b in self.query(part.strip()))
                if results is None:
                    results = part_results
                else:
                    results &= part_results
            return [self.position_index[bid] for bid in results if bid in self.position_index]

        if ' | ' in query_string:
            # Union query
            parts = query_string.split(' | ')
            results = set()
            for part in parts:
                part_results = set(b.id for b in self.query(part.strip()))
                results |= part_results
            return [self.position_index[bid] for bid in results if bid in self.position_index]

        # Single query types
        query_string = query_string.strip()

        # Exact position [S.B]
        if re.match(r'\[\d+\.\d+\]', query_string):
            if query_string in self.position_index:
                return [self.position_index[query_string]]
            return []

        # Scene range {S-S}
        if re.match(r'\{(\d+)-(\d+)\}', query_string):
            match = re.match(r'\{(\d+)-(\d+)\}', query_string)
            start, end = int(match.group(1)), int(match.group(2))
            results = []
            for beat_id, beat in self.position_index.items():
                scene = int(beat_id.split('.')[0].strip('[]'))
                if start <= scene <= end:
                    results.append(beat)
            return results

        # Character with dynamic: P1↑
        if re.match(r'[PA]\d+[↑↓─↕⤴⤵∿]', query_string):
            char = query_string[:-1]
            dyn = query_string[-1]
            char_beats = self.character_index.get(char, set())
            dyn_beats = self.dynamic_index.get(dyn, set())
            result_ids = char_beats & dyn_beats
            return [self.position_index[bid] for bid in result_ids]

        # Character with state: P1:fear
        if re.match(r'[PA]\d+:.+', query_string):
            char, state = query_string.split(':', 1)
            char_beats = self.character_index.get(char, set())
            state_beats = self.state_index.get(state, set())
            result_ids = char_beats & state_beats
            return [self.position_index[bid] for bid in result_ids]

        # State transition: P1:fear→hope
        if '→' in query_string and ':' in query_string:
            parts = query_string.split(':')
            char = parts[0]
            states = parts[1].split('→')
            state_from, state_to = states[0], states[1]

            # Find transitions
            if char not in self.char_states:
                return []

            transitions = []
            state_history = self.char_states[char]
            for i in range(len(state_history) - 1):
                curr_state = re.sub(r'[¹²³⁺⁻]', '', state_history[i][1])
                next_state = re.sub(r'[¹²³⁺⁻]', '', state_history[i+1][1])
                if curr_state == state_from and next_state == state_to:
                    transitions.append(state_history[i+1][0])

            return [self.position_index[bid] for bid in transitions]

        # Plot point wildcard: ◆*
        if query_string == '◆*':
            results = []
            for key in self.plot_index:
                if key.startswith('◆'):
                    for bid in self.plot_index[key]:
                        if bid not in [r.id for r in results]:
                            results.append(self.position_index[bid])
            return results

        # Specific plot point: ◆1, ●PROMISE
        if query_string.startswith('◆') or query_string.startswith('◇') or \
           query_string.startswith('●') or query_string.startswith('○'):
            if query_string in self.plot_index:
                return [self.position_index[bid] for bid in self.plot_index[query_string]]
            return []

        # Temporal: T:-1
        if query_string.startswith('T:'):
            if query_string in self.temporal_index:
                return [self.position_index[bid] for bid in self.temporal_index[query_string]]
            return []

        # Theme: θFREEDOM
        if query_string.startswith('θ'):
            if query_string in self.theme_index:
                return [self.position_index[bid] for bid in self.theme_index[query_string]]
            return []

        # Just character: P1
        if re.match(r'^[PA]\d+$', query_string):
            if query_string in self.character_index:
                return [self.position_index[bid] for bid in self.character_index[query_string]]
            return []

        return []

    def get_unresolved_setups(self) -> List[str]:
        """Find all setups without corresponding payoffs."""
        unresolved = []
        for setup in self.setup_index:
            # Convert ●LABEL to ○LABEL
            payoff = '○' + setup[1:]
            if payoff not in self.payoff_index:
                unresolved.append(setup)
        return unresolved

    def get_arc(self, character: str) -> List[Tuple[str, str, str]]:
        """Get character's full arc: [(beat_id, state, dynamic)]."""
        if character not in self.char_states:
            return []

        arc = []
        for beat_id, state in self.char_states[character]:
            beat = self.position_index.get(beat_id)
            if beat:
                dyn = beat.dynamics.get(character, '─')
                arc.append((beat_id, state, dyn))
        return arc

    def get_sequence_around(self, beat_id: str, before: int = 2, after: int = 2) -> List[NotatedBeat]:
        """Get beats surrounding a given beat."""
        if beat_id not in self.sequence:
            return []

        idx = self.sequence.index(beat_id)
        start = max(0, idx - before)
        end = min(len(self.sequence), idx + after + 1)

        return [self.position_index[bid] for bid in self.sequence[start:end]]
```

---

## 5. Context Control Rubric

### 5.1 The Context Control Problem

Agents need **precisely controlled** context to:
1. Write consistent with established story
2. Not get overwhelmed with irrelevant info
3. Receive only what's needed for their specific task
4. Maintain character states across scenes

### 5.2 Context Control Rubric

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONTEXT CONTROL RUBRIC                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  RULE 1: POSITION ANCHORING                                                 │
│  ────────────────────────────────                                           │
│  Every agent call MUST include:                                             │
│  • Current position: [S.B]                                                  │
│  • Previous position: [S.B-1]                                               │
│  • Next position: [S.B+1] (if known)                                        │
│                                                                              │
│  Example:                                                                    │
│  POSITION: Writing [3.2], after [3.1], before [3.3]                         │
│                                                                              │
│  ────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  RULE 2: CHARACTER STATE HANDOFF                                            │
│  ────────────────────────────────                                           │
│  For each character in scene:                                               │
│  • Entry state from previous beat                                           │
│  • Required exit state for next beat                                        │
│  • Current dynamic (↑↓─)                                                    │
│                                                                              │
│  Example:                                                                    │
│  P1: fear² → hope³ (↑)                                                      │
│  A1: confident → uncertain (↓)                                              │
│                                                                              │
│  ────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  RULE 3: ACTIVE SETUPS                                                      │
│  ────────────────────────────────                                           │
│  Include ONLY setups that:                                                  │
│  • Were planted in previous 3 beats, OR                                     │
│  • Are marked for payoff in this beat, OR                                   │
│  • Are thematically relevant                                                │
│                                                                              │
│  Example:                                                                    │
│  ACTIVE SETUPS:                                                             │
│  ●ORCHID_SYMBOL [1.3] - awaiting payoff                                     │
│  ●HIDDEN_BLADE [2.1] - payoff in [8.1]                                      │
│                                                                              │
│  ────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  RULE 4: TEMPORAL CONTEXT                                                   │
│  ────────────────────────────────                                           │
│  If beat is NOT T:0 (present):                                              │
│  • Specify temporal position                                                │
│  • Specify return anchor                                                    │
│  • Specify what present-thread is paused                                    │
│                                                                              │
│  Example:                                                                    │
│  TEMPORAL: T:-1 (flashback)                                                 │
│  RETURN TO: [5.2] (present confrontation paused)                            │
│                                                                              │
│  ────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  RULE 5: PLOT POINT AWARENESS                                               │
│  ────────────────────────────────                                           │
│  If beat is a plot point:                                                   │
│  • Mark which point (◆1, ◆M, ◆2, ◆C)                                        │
│  • Include all related setups                                               │
│  • Specify expected resolution state                                        │
│                                                                              │
│  Example:                                                                    │
│  PLOT POINT: ◆M (Midpoint)                                                  │
│  Must resolve: ●POWER_DYNAMIC → P1>A1                                       │
│                                                                              │
│  ────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  RULE 6: RELATIONSHIP DYNAMICS                                              │
│  ────────────────────────────────                                           │
│  Include current relationship state between present characters:             │
│                                                                              │
│  Example:                                                                    │
│  RELATIONSHIPS:                                                             │
│  P1<A1 (P1 under A1's power)                                                │
│  P1~P2 (P1-P2 bonded but separated)                                         │
│                                                                              │
│  ────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  RULE 7: THEME EMPHASIS                                                     │
│  ────────────────────────────────                                           │
│  If scene has theme focus:                                                  │
│  • Specify active theme                                                     │
│  • Prior appearances of theme                                               │
│                                                                              │
│  Example:                                                                    │
│  THEME: θFREEDOM                                                            │
│  Prior: [1.1] longing, [2.4] first hope, [4.2] setback                      │
│                                                                              │
│  ────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  RULE 8: WORD BUDGET BY TASK                                                │
│  ────────────────────────────────                                           │
│                                                                              │
│  Task Type           Context Budget    Agent Output                         │
│  ──────────────────────────────────────────────────                         │
│  Brainstorm          100-150 words     150-200 words                        │
│  Outline             150-200 words     100-150 per scene                    │
│  Prose Generation    200-250 words     150-250 words                        │
│  Beat Revision       100-150 words     150-250 words                        │
│  Validation          50-100 words      Yes/No + issues                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Context Packet Templates

**TEMPLATE: Prose Generation**
```
═══════════════════════════════════════════════════════════════════════════════
CONTEXT PACKET: PROSE GENERATION
═══════════════════════════════════════════════════════════════════════════════

POSITION: [3.2]
PREVIOUS: [3.1] → P1 entered with fear², A1 entered confident
NEXT: [3.3] → P1 must exit with hope¹, A1 must exit uncertain

CHARACTERS PRESENT:
┌────────────────────────────────────────────────────────────────────────────┐
│ P1 (@CHAR_MEI) "Mei" - Courtesan seeking freedom                          │
│ State: fear² → hope³ | Dynamic: ↑                                         │
│ Want: freedom | Flaw: manipulation                                         │
│                                                                            │
│ A1 (@CHAR_THE_GENERAL) "General Wei" - Military commander                 │
│ State: confident → distracted | Dynamic: ↓                                │
│ Want: possess Mei | Flaw: arrogance                                        │
└────────────────────────────────────────────────────────────────────────────┘

LOCATION: @LOC_MEI_BALCONY
Private balcony, lantern-lit, Go board between them

ACTIVE SETUPS:
● [1.3] ORCHID_SYMBOL - Lin's orchids = tenderness
● [2.1] WRIST_REVEAL - Mei's seduction technique

TEMPORAL: T:0 (present)

RELATIONSHIP: P1<A1 (power under) → shift toward P1><A1 (conflict)

THEME: θFREEDOM (this beat advances)

PREVIOUS ENDED: "The General's eyes narrowed as Mei placed her first stone."

═══════════════════════════════════════════════════════════════════════════════
```
**Word count: ~150 words**

**TEMPLATE: Scene Outline**
```
═══════════════════════════════════════════════════════════════════════════════
CONTEXT PACKET: SCENE OUTLINE
═══════════════════════════════════════════════════════════════════════════════

STORY SEED:
"Beta Test" - A courtesan gambles her freedom in a game of Go against a
powerful general, using wit and seduction to win and pursue the florist
she loves from afar. Feudal China, merchant district. Intimate drama.

CHARACTER CARDS:
┌────────────────────────────────────────────────────────────────────────────┐
│ P1: Mei - courtesan, wants freedom/love, flaw: manipulation               │
│ P2: Lin - florist, wants peace, flaw: passivity                           │
│ A1: General Wei - military, wants Mei, flaw: arrogance                    │
└────────────────────────────────────────────────────────────────────────────┘

WINNING CONCEPT: (from brainstorm phase)
"Mei's journey from manipulator to authentic connection. The Go game is
metaphor for control - she starts playing to win, ends playing to be free."

STEAL LIST:
- From Concept B: "Use orchid petals as visual motif for fragility"
- From Concept D: "Lin witnesses final move but doesn't understand"

STRUCTURE: σ3ACT (8 scenes)
THEMES: θFREEDOM, θIDENTITY, θLOVE

═══════════════════════════════════════════════════════════════════════════════
```
**Word count: ~150 words**

---

## 6. Agent Context Delivery

### 6.1 Delivery Protocol

```python
class ContextDelivery:
    """
    Delivers precisely controlled context to agents.
    """

    def __init__(
        self,
        notation_index: NotationIndex,
        dissected_script: DissectedScript,
        world_config: Dict[str, Any]
    ):
        self.index = notation_index
        self.script = dissected_script
        self.world = world_config

    def compile_prose_context(
        self,
        target_position: str,  # "[3.2]"
        word_budget: int = 200
    ) -> str:
        """
        Compile context packet for prose generation.
        """
        parts = []

        # Position anchoring
        parts.append(f"POSITION: {target_position}")

        # Get surrounding beats
        prev_beat = self._get_previous_beat(target_position)
        next_beat = self._get_next_beat(target_position)

        if prev_beat:
            prev_states = self._format_states(prev_beat)
            parts.append(f"PREVIOUS: {prev_beat.id} → {prev_states}")

        if next_beat:
            next_states = self._format_required_states(next_beat)
            parts.append(f"NEXT: {next_beat.id} → {next_states}")

        # Characters present
        chars_in_scene = self._get_characters_at(target_position)
        parts.append("\nCHARACTERS:")
        for char in chars_in_scene:
            card = self._get_character_card(char)
            state_transition = self._get_state_transition(char, target_position)
            dynamic = self._get_dynamic(char, target_position)
            parts.append(f"{char}: {card}")
            parts.append(f"  {state_transition} | Dynamic: {dynamic}")

        # Location
        location = self._get_location_at(target_position)
        parts.append(f"\nLOCATION: {location}")

        # Active setups (only relevant ones)
        setups = self._get_active_setups(target_position)
        if setups:
            parts.append("\nACTIVE SETUPS:")
            for setup in setups[:3]:  # Max 3
                parts.append(f"● {setup}")

        # Temporal
        temporal = self._get_temporal(target_position)
        parts.append(f"\nTEMPORAL: {temporal}")

        # Relationships
        relationships = self._get_relationships(chars_in_scene)
        if relationships:
            parts.append(f"\nRELATIONSHIPS: {relationships}")

        # Theme
        theme = self._get_active_theme(target_position)
        if theme:
            parts.append(f"\nTHEME: {theme}")

        # Previous ending
        if prev_beat:
            last_line = self._get_last_line(prev_beat)
            parts.append(f'\nPREVIOUS ENDED: "{last_line}"')

        context = '\n'.join(parts)

        # Trim if over budget
        return self._trim_to_budget(context, word_budget)

    def compile_query_context(
        self,
        query: str,
        mode: str = "SUMMARY",
        word_budget: int = 100
    ) -> str:
        """
        Compile context from a symbolic query.

        Modes:
        - FULL: Complete beat data
        - SUMMARY: Compressed summary
        - NOTATION: Just notation strings
        - PROSE: Just content
        - STATE: Just states
        """
        beats = self.index.query(query)

        if not beats:
            return f"No results for query: {query}"

        parts = [f"QUERY: {query}", f"RESULTS: {len(beats)} beats", ""]

        for beat in beats[:5]:  # Max 5 results
            if mode == "FULL":
                parts.append(f"{beat.id}: {beat.notation}")
                parts.append(f"  {beat.content[:100]}...")
            elif mode == "SUMMARY":
                summary = self._summarize_beat(beat)
                parts.append(f"{beat.id}: {summary}")
            elif mode == "NOTATION":
                parts.append(beat.notation)
            elif mode == "PROSE":
                parts.append(beat.content)
            elif mode == "STATE":
                states = self._format_states(beat)
                parts.append(f"{beat.id}: {states}")

        context = '\n'.join(parts)
        return self._trim_to_budget(context, word_budget)

    def compile_arc_context(
        self,
        character: str,  # "P1"
        word_budget: int = 150
    ) -> str:
        """
        Compile character arc context.
        """
        arc = self.index.get_arc(character)

        if not arc:
            return f"No arc data for {character}"

        char_name = self._get_character_name(character)

        parts = [
            f"CHARACTER ARC: {character} ({char_name})",
            ""
        ]

        # Compress arc to key beats
        key_beats = self._get_key_arc_beats(arc)

        for beat_id, state, dynamic in key_beats:
            parts.append(f"{beat_id}: {state} {dynamic}")

        # Overall trajectory
        trajectory = self._compute_trajectory(arc)
        parts.append(f"\nTRAJECTORY: {trajectory}")

        context = '\n'.join(parts)
        return self._trim_to_budget(context, word_budget)

    def compile_thread_context(
        self,
        setup_marker: str,  # "●ORCHID"
        word_budget: int = 100
    ) -> str:
        """
        Compile setup-payoff thread context.
        """
        # Find setup beat
        setup_beats = self.index.query(setup_marker)
        if not setup_beats:
            return f"Setup not found: {setup_marker}"

        setup_beat = setup_beats[0]

        # Find payoff (if exists)
        payoff_marker = '○' + setup_marker[1:]
        payoff_beats = self.index.query(payoff_marker)

        parts = [
            f"THREAD: {setup_marker}",
            f"SETUP: {setup_beat.id}",
            f"  {setup_beat.content[:80]}..."
        ]

        if payoff_beats:
            payoff_beat = payoff_beats[0]
            parts.append(f"PAYOFF: {payoff_beat.id}")
            parts.append(f"  {payoff_beat.content[:80]}...")
            parts.append("STATUS: RESOLVED")
        else:
            parts.append("PAYOFF: PENDING")
            parts.append("STATUS: AWAITING RESOLUTION")

        context = '\n'.join(parts)
        return self._trim_to_budget(context, word_budget)

    # Helper methods

    def _get_previous_beat(self, position: str) -> Optional[NotatedBeat]:
        """Get the beat before given position."""
        if position not in self.index.sequence:
            return None
        idx = self.index.sequence.index(position)
        if idx > 0:
            prev_id = self.index.sequence[idx - 1]
            return self.index.position_index.get(prev_id)
        return None

    def _get_next_beat(self, position: str) -> Optional[NotatedBeat]:
        """Get the beat after given position."""
        if position not in self.index.sequence:
            return None
        idx = self.index.sequence.index(position)
        if idx < len(self.index.sequence) - 1:
            next_id = self.index.sequence[idx + 1]
            return self.index.position_index.get(next_id)
        return None

    def _format_states(self, beat: NotatedBeat) -> str:
        """Format character states from beat."""
        return ', '.join([f"{c}:{s}" for c, s in beat.states.items()])

    def _get_character_card(self, char: str) -> str:
        """Get compressed character card (~30 words)."""
        char_data = self.world.get('characters', {}).get(char, {})
        name = char_data.get('name', 'Unknown')
        role = char_data.get('role', '')
        want = char_data.get('want', '')
        flaw = char_data.get('flaw', '')
        return f"{name} - {role}, wants: {want}, flaw: {flaw}"

    def _get_active_setups(self, position: str) -> List[str]:
        """Get setups active at this position."""
        # Find unresolved setups planted before this position
        active = []
        pos_idx = self.index.sequence.index(position) if position in self.index.sequence else 0

        for setup, beat_id in self.index.setup_index.items():
            setup_idx = self.index.sequence.index(beat_id) if beat_id in self.index.sequence else 0

            # Only include if planted before and not yet paid off
            payoff = '○' + setup[1:]
            if setup_idx < pos_idx and payoff not in self.index.payoff_index:
                active.append(f"{setup} [{beat_id}]")

        return active

    def _trim_to_budget(self, text: str, budget: int) -> str:
        """Trim text to word budget."""
        words = text.split()
        if len(words) <= budget:
            return text
        return ' '.join(words[:budget]) + '...'
```

### 6.2 Agent Prompt Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     AGENT PROMPT STRUCTURE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SECTION 1: ROLE (fixed)                                                    │
│  ═══════════════════════════════════════════════════════════                │
│  You are a prose writer for Project Greenlight.                             │
│  Write narrative prose. Third person, past tense.                           │
│  Show, don't tell. No beat markers or technical notation.                   │
│                                                                              │
│  SECTION 2: NOTATION KEY (if needed, ~50 words)                             │
│  ═══════════════════════════════════════════════════════════                │
│  NOTATION KEY:                                                               │
│  [S.B] = Scene.Beat | P1/A1 = Protagonist/Antagonist                        │
│  ↑↓ = rising/falling | :state = emotional state                             │
│  ●/○ = setup/payoff | → = transition                                        │
│                                                                              │
│  SECTION 3: CONTEXT PACKET (~200 words)                                     │
│  ═══════════════════════════════════════════════════════════                │
│  {compiled context from ContextDelivery}                                    │
│                                                                              │
│  SECTION 4: TASK (~50 words)                                                │
│  ═══════════════════════════════════════════════════════════                │
│  Write [3.2]. 150-250 words.                                                │
│                                                                              │
│  REQUIREMENTS:                                                               │
│  - Move P1 from fear² to hope³                                              │
│  - Move A1 from confident to distracted                                     │
│  - Include Mei's wrist reveal (●WRIST_REVEAL payoff)                        │
│  - End with line leading to [3.3]                                           │
│                                                                              │
│  DO NOT:                                                                     │
│  - Include [S.B] markers in prose                                           │
│  - Use character codes (P1) - use names                                     │
│  - Exceed 250 words                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

TOTAL: ~300-350 tokens (down from 2000+)
```

---

## 7. Story Pipeline Phases

### 7.1 Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STORY PIPELINE v3.0 WITH SYMBOLIC RUBRIC                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT: world_config.json                                                   │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 0: INITIALIZATION                                                    │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  • Load world_config                                                        │
│  • Create character map: name → P#/A#/N#                                    │
│  • Initialize NotationIndex (empty)                                         │
│  • Initialize ContextDelivery                                               │
│                                                                              │
│  OUTPUT: Context engine ready                                               │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 1: CONCEPT BRAINSTORM (5 agents, parallel)                           │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  5 agents with different philosophies generate concepts.                    │
│  Context: Story seed + character cards (~100 words each)                    │
│  Output: 150-200 word concept pitches                                       │
│                                                                              │
│  OUTPUT: 5 story concepts                                                   │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 2: CONCEPT SELECTION + STEAL LIST (3 judges)                         │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  • Rank concepts 1-5                                                        │
│  • Identify elements to STEAL from losers                                   │
│  • Winner = best aggregate                                                  │
│  • Steal list = elements mentioned by 2+ judges                             │
│                                                                              │
│  OUTPUT: Winning concept + steal list                                       │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 3: SCENE OUTLINE                                                     │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  Create scene-level outline with:                                           │
│  • Position: [S] for each scene                                             │
│  • Characters: P#, A# present                                               │
│  • Location: @LOC_*                                                         │
│  • Entry/Exit states: P1:state→state                                        │
│  • Plot points: ◆1, ◆M, ◆2, ◆C assignments                                  │
│  • Temporal: T:# if non-linear                                              │
│  • Theme focus: θ* for scene                                                │
│                                                                              │
│  OUTPUT: scene_outline.json                                                 │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 4: BEAT OUTLINE                                                      │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  For each scene, outline beats:                                             │
│  • Position: [S.B]                                                          │
│  • State transitions                                                        │
│  • Setups to plant: ●LABEL                                                  │
│  • Payoffs to deliver: ○LABEL                                               │
│  • Dynamics: ↑↓─                                                            │
│                                                                              │
│  OUTPUT: beat_outline.json                                                  │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 5: PROSE GENERATION (beat by beat, sequential)                       │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  FOR EACH BEAT:                                                             │
│                                                                              │
│  1. Compile context packet (~200 words):                                    │
│     • Position anchoring                                                    │
│     • Character cards (present only)                                        │
│     • State requirements (in→out)                                           │
│     • Active setups                                                         │
│     • Temporal marker                                                       │
│     • Previous ending                                                       │
│                                                                              │
│  2. Call prose agent (150-250 words output)                                 │
│                                                                              │
│  3. Validate:                                                               │
│     • Word count                                                            │
│     • State transitions achieved                                            │
│     • No forbidden notation in prose                                        │
│                                                                              │
│  4. Dissect output:                                                         │
│     • Auto-detect states from prose                                         │
│     • Auto-detect setups/payoffs                                            │
│     • Generate notation for beat                                            │
│                                                                              │
│  5. Index:                                                                  │
│     • Add to NotationIndex                                                  │
│     • Update character state tracking                                       │
│                                                                              │
│  OUTPUT: script_draft.md + populated NotationIndex                          │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 6: COHERENCE VALIDATION                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  Use symbolic queries to validate:                                          │
│                                                                              │
│  1. Setup/Payoff balance:                                                   │
│     Query: ●* → check all have ○*                                           │
│                                                                              │
│  2. Character arc completion:                                               │
│     Query: P1:* → verify trajectory ↓→↑ or intended                         │
│                                                                              │
│  3. State continuity:                                                       │
│     Verify exit state [S.B] = entry state [S.B+1]                           │
│                                                                              │
│  4. Theme consistency:                                                      │
│     Query: θ* → verify theme appears consistently                           │
│                                                                              │
│  5. Plot point placement:                                                   │
│     Verify ◆1, ◆M, ◆2, ◆C in correct positions                              │
│                                                                              │
│  OUTPUT: validation_report.json (issues list)                               │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 7: REVISION (if issues found)                                        │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  For each issue:                                                            │
│  • Query context for problem beat                                           │
│  • Compile revision context (include issue)                                 │
│  • Regenerate beat                                                          │
│  • Re-validate                                                              │
│                                                                              │
│  OUTPUT: revised script_draft.md                                            │
│                                                                              │
│  ════════════════════════════════════════════════════════════════════════   │
│  PHASE 8: DIRECTING OVERLAY (separate pipeline)                             │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  Takes clean prose, adds:                                                   │
│  • Frame notation: [S.B.C]                                                  │
│  • Camera directions                                                        │
│  • Visual notes                                                             │
│                                                                              │
│  OUTPUT: script.md (final)                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Phase Implementation Code

```python
class StoryPipelineV3:
    """
    Story Pipeline with Symbolic Rubric System.
    """

    def __init__(
        self,
        project_path: Path,
        model_provider: str = "anthropic"
    ):
        self.project_path = project_path
        self.client = get_model_client(model_provider)

        # Initialize components
        self.world_config = self._load_world_config()
        self.char_map = self._build_character_map()
        self.notation_index = NotationIndex()
        self.dissector = ScriptDissector(self.char_map, SymbolRegistry())
        self.delivery = ContextDelivery(
            self.notation_index,
            None,  # Populated after dissection
            self.world_config
        )

    def _build_character_map(self) -> Dict[str, str]:
        """Map character names to P#/A# symbols."""
        char_map = {}
        protagonists = []
        antagonists = []
        others = []

        for char in self.world_config.get('characters', []):
            role = char.get('role', '').lower()
            name = char.get('name', '')

            if 'protagonist' in role or 'hero' in role:
                protagonists.append(name)
            elif 'antagonist' in role or 'villain' in role:
                antagonists.append(name)
            else:
                others.append(name)

        # Assign symbols
        for i, name in enumerate(protagonists, 1):
            char_map[name] = f"P{i}"
        for i, name in enumerate(antagonists, 1):
            char_map[name] = f"A{i}"
        for i, name in enumerate(others, 1):
            char_map[name] = f"N{i}"

        return char_map

    async def run(self) -> StoryOutput:
        """Execute the complete pipeline."""

        # Phase 0: Initialize (already done in __init__)
        logger.info("Phase 0: Initialized")

        # Phase 1: Brainstorm
        concepts = await self._phase_brainstorm()
        logger.info(f"Phase 1: Generated {len(concepts)} concepts")

        # Phase 2: Selection
        winner, steal_list = await self._phase_selection(concepts)
        logger.info(f"Phase 2: Selected winner, {len(steal_list)} steal items")

        # Phase 3: Scene Outline
        scene_outline = await self._phase_scene_outline(winner, steal_list)
        logger.info(f"Phase 3: Created {len(scene_outline)} scene outline")

        # Phase 4: Beat Outline
        beat_outline = await self._phase_beat_outline(scene_outline)
        logger.info(f"Phase 4: Created {len(beat_outline)} beat outline")

        # Phase 5: Prose Generation
        prose = await self._phase_prose_generation(beat_outline)
        logger.info(f"Phase 5: Generated {len(prose)} words of prose")

        # Phase 6: Validation
        issues = await self._phase_validation()
        logger.info(f"Phase 6: Found {len(issues)} issues")

        # Phase 7: Revision (if needed)
        if issues:
            prose = await self._phase_revision(issues)
            logger.info("Phase 7: Revisions complete")

        return StoryOutput(
            script=prose,
            scene_outline=scene_outline,
            beat_outline=beat_outline,
            notation_index=self.notation_index,
            validation_issues=issues
        )

    async def _phase_prose_generation(
        self,
        beat_outline: List[BeatOutline]
    ) -> str:
        """
        Phase 5: Generate prose beat by beat.
        """
        prose_parts = []

        for i, beat in enumerate(beat_outline):
            # Compile context
            context = self.delivery.compile_prose_context(
                target_position=beat.position,
                word_budget=200
            )

            # Build task
            task = self._build_prose_task(beat)

            # Generate
            prompt = self._build_prose_prompt(context, task)
            result = await self.client.generate({"full_prompt": prompt})
            beat_prose = result.text

            # Validate
            valid, issues = self._validate_beat_prose(beat_prose, beat)
            if not valid:
                # Retry with feedback
                retry_prompt = f"{prompt}\n\nISSUES WITH PREVIOUS:\n{issues}\nTry again:"
                result = await self.client.generate({"full_prompt": retry_prompt})
                beat_prose = result.text

            # Dissect and index
            notated_beat = self.dissector._analyze_beat(RawBeat(
                scene=beat.scene,
                beat_num=beat.beat_num,
                content=beat_prose
            ))
            self.notation_index.index_beat(notated_beat)

            prose_parts.append(beat_prose)

            logger.info(f"Generated {beat.position}")

        return '\n\n'.join(prose_parts)

    def _build_prose_task(self, beat: BeatOutline) -> str:
        """Build task instructions for prose generation."""
        lines = [
            f"Write {beat.position}. 150-250 words.",
            "",
            "REQUIREMENTS:"
        ]

        # State transitions
        for char, (state_in, state_out) in beat.state_transitions.items():
            lines.append(f"- Move {char} from {state_in} to {state_out}")

        # Setups to plant
        if beat.setups_to_plant:
            for setup in beat.setups_to_plant:
                lines.append(f"- Plant: {setup}")

        # Payoffs to deliver
        if beat.payoffs_to_deliver:
            for payoff in beat.payoffs_to_deliver:
                lines.append(f"- Resolve: {payoff}")

        lines.extend([
            "",
            "DO NOT:",
            "- Include [S.B] markers in prose",
            "- Use character codes (P1) - use names",
            "- Exceed 250 words"
        ])

        return '\n'.join(lines)

    async def _phase_validation(self) -> List[ValidationIssue]:
        """
        Phase 6: Validate story coherence using symbolic queries.
        """
        issues = []

        # 1. Check unresolved setups
        unresolved = self.notation_index.get_unresolved_setups()
        for setup in unresolved:
            issues.append(ValidationIssue(
                type="UNRESOLVED_SETUP",
                symbol=setup,
                message=f"Setup {setup} has no payoff"
            ))

        # 2. Check character arcs
        for char in self.char_map.values():
            arc = self.notation_index.get_arc(char)
            if arc:
                trajectory = self._analyze_trajectory(arc)
                if trajectory == 'INCOMPLETE':
                    issues.append(ValidationIssue(
                        type="INCOMPLETE_ARC",
                        symbol=char,
                        message=f"{char} arc does not complete"
                    ))

        # 3. Check state continuity
        for i, beat_id in enumerate(self.notation_index.sequence[:-1]):
            curr_beat = self.notation_index.position_index[beat_id]
            next_id = self.notation_index.sequence[i + 1]
            next_beat = self.notation_index.position_index[next_id]

            for char in curr_beat.states:
                if char in next_beat.states:
                    # Check continuity (exit should roughly match entry)
                    # This is simplified - real implementation would be smarter
                    pass

        # 4. Check theme consistency
        for theme in ['θFREEDOM', 'θLOVE', 'θPOWER']:  # From world_config
            theme_beats = self.notation_index.query(theme)
            if len(theme_beats) < 3:
                issues.append(ValidationIssue(
                    type="UNDERDEVELOPED_THEME",
                    symbol=theme,
                    message=f"Theme {theme} appears only {len(theme_beats)} times"
                ))

        # 5. Check plot point placement
        for pp in ['◆1', '◆M', '◆2', '◆C']:
            pp_beats = self.notation_index.query(pp)
            if not pp_beats:
                issues.append(ValidationIssue(
                    type="MISSING_PLOT_POINT",
                    symbol=pp,
                    message=f"Plot point {pp} not found"
                ))

        return issues
```

---

## 8. Implementation Roadmap

### 8.1 Phase 1: Core Notation System

```
TASK                                          STATUS
─────────────────────────────────────────────────────
[ ] Create notation_symbols.py
    - Define all symbol constants
    - Symbol validation functions
    - Symbol parsing utilities

[ ] Create notation_index.py
    - NotationIndex class
    - Multi-dimensional indexing
    - Query engine implementation

[ ] Create script_dissector.py
    - ScriptDissector class
    - State detection
    - Dynamic detection
    - Setup/payoff detection
    - Auto-notation generation

[ ] Create notation_tests.py
    - Unit tests for all notation parsing
    - Query tests
    - Indexing tests
```

### 8.2 Phase 2: Context Control

```
TASK                                          STATUS
─────────────────────────────────────────────────────
[ ] Create context_delivery.py
    - ContextDelivery class
    - Prose context compilation
    - Query context compilation
    - Arc context compilation

[ ] Create context_templates.py
    - Prose generation template
    - Scene outline template
    - Beat outline template
    - Validation template

[ ] Create word_budget.py
    - Budget calculation
    - Trimming utilities
    - Priority ordering
```

### 8.3 Phase 3: Pipeline Integration

```
TASK                                          STATUS
─────────────────────────────────────────────────────
[ ] Create story_pipeline_v3.py
    - StoryPipelineV3 class
    - All 8 phases implemented
    - Integration with existing world_config

[ ] Refactor existing agents
    - Update prompts for notation system
    - Add notation validation
    - Add state tracking

[ ] Create pipeline_tests.py
    - End-to-end pipeline tests
    - Phase-by-phase tests
    - Regression tests
```

### 8.4 Phase 4: Testing & Refinement

```
TASK                                          STATUS
─────────────────────────────────────────────────────
[ ] Test with Beta Test project
    - Full pipeline run
    - Validate output quality
    - Check notation accuracy

[ ] Multi-model testing
    - Test with Claude Haiku
    - Test with GPT-4o
    - Test with Gemini
    - Test with Grok

[ ] Performance optimization
    - Context packet size analysis
    - Query performance
    - Indexing performance
```

---

## Appendix A: Symbol Quick Reference

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         SYMBOLIC NOTATION QUICK REFERENCE                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                                ║
║  POSITION                          CHARACTERS                                  ║
║  ──────────────────────            ───────────────────────                    ║
║  [S.B]     Scene.Beat              P1-P9   Protagonists                       ║
║  [S.B:L]   Scene.Beat:Line         A1-A9   Antagonists                        ║
║  {S-S}     Scene range             N1-N99  Named others                       ║
║  <B-B>     Beat range              X       Unnamed/crowd                      ║
║                                                                                ║
║  DYNAMICS                          STATES                                      ║
║  ──────────────────────            ───────────────────────                    ║
║  ↑  Rising                         :fear :hope :anger :joy                    ║
║  ↓  Falling                        :love :hate :guilt :shame                  ║
║  ─  Static                         :calm :rage :desire :sorrow                ║
║  ↕  Oscillating                    ¹²³ Intensity (low/med/high)               ║
║  ⤴  Recovery                       ⁺⁻  Increasing/Decreasing                  ║
║  ⤵  Decline                                                                    ║
║                                                                                ║
║  PLOT POINTS                       SETUPS/PAYOFFS                             ║
║  ──────────────────────            ───────────────────────                    ║
║  ◆1  Inciting incident opens       ●LABEL  Setup planted                      ║
║  ◇1  Inciting incident closes      ○LABEL  Payoff delivered                   ║
║  ◆M  Midpoint opens                                                            ║
║  ◇M  Midpoint closes               TEMPORAL                                   ║
║  ◆2  Second turn opens             ───────────────────────                    ║
║  ◇2  Second turn closes            T:0   Present                              ║
║  ◆C  Climax opens                  T:-1  Past (flashback)                     ║
║  ◇C  Resolution                    T:+1  Future (flash forward)               ║
║                                    T:‖   Parallel time                        ║
║  RELATIONSHIPS                                                                 ║
║  ──────────────────────            THEMES (prefix θ)                          ║
║  P1~P2   Bonded                    ───────────────────────                    ║
║  P1≁P2   Broken                    θFREEDOM θPOWER θIDENTITY                  ║
║  P1>A1   Dominates                 θLOVE θLOSS θREDEMPTION                    ║
║  P1<A1   Submits                   θTRUTH θDECEPTION θFATE                    ║
║  P1><A1  Conflict                                                              ║
║                                    STRUCTURE (prefix σ)                        ║
║  TRANSITIONS                       ───────────────────────                    ║
║  ──────────────────────            σLINEAR σNONLINEAR σCIRCULAR               ║
║  →   State change                  σPARALLEL σ3ACT σ5ACT                      ║
║  »   Flows to                      σHERO σSAVECAT                             ║
║  ⊣   Interrupts                                                                ║
║  ⟲   Loops back                                                                ║
║  ⟳   Jumps forward                                                             ║
║                                                                                ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## Appendix B: Example Notated Script

```
═══════════════════════════════════════════════════════════════════════════════
BETA TEST - NOTATED SCRIPT EXCERPT
═══════════════════════════════════════════════════════════════════════════════

[1.1]:P1─:longing²|T:0|@LOC_TEAHOUSE|θFREEDOM
──────────────────────────────────────────────────────────────────────────────
Mei stood by the window, her fingers tracing the delicate pattern on the
silk curtain. Below, the merchant district hummed with evening commerce,
but her eyes found only one shop—Lin's Orchids, where careful hands
arranged petals as if each bloom were a whispered secret.

Soon, she told herself. Soon I will know if he sees me as more than a
customer who admires his flowers from across the street.


[1.2]:P1↓:longing→dread²|A1↑:calm→predatory|P1<A1|●POWER_DYNAMIC
──────────────────────────────────────────────────────────────────────────────
The door opened without knock. Mei didn't need to turn to know who it was—
the weight of his presence announced itself like storm clouds over mountains.

"Mei." General Wei's voice was silk wrapped around steel. "I've thought
of nothing but you these past weeks."

She forced her hands to still, her face to compose itself into the mask
she'd worn for years. "General. You honor me with your visit."


[1.3]:P1↓:dread³|A1↑:predatory→triumphant|◆1|●WAGER|●FREEDOM_STAKE
──────────────────────────────────────────────────────────────────────────────
"A wager," he said, moving to the Go board by the window—her window,
looking down at Lin's shop. "You fancy yourself clever at this game.
Beat me, and I release you from your contract. Lose..." His smile
was a blade in moonlight. "And you become mine. Completely."

Mei's heart hammered. This was madness. This was her only chance.

"When do we begin?" she heard herself say.

═══════════════════════════════════════════════════════════════════════════════
```

---

*Document Version: 3.0*
*Created: December 2024*
*For: Project Greenlight Story Pipeline*

---
