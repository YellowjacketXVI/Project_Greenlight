"""
Dialogue Detection and Generation System

Multi-agent consensus system for:
1. Detecting dialogue in beats (3-agent voting)
2. Generating dialogue for single and multi-character scenes
"""

import asyncio
import re
from typing import List, Dict, Optional, Tuple, Callable, Any
from dataclasses import dataclass

from greenlight.core.logging_config import get_logger

logger = get_logger("agents.dialogue")


@dataclass
class DialogueDetectionResult:
    """Result of dialogue detection consensus."""
    has_dialogue: bool
    confidence: float  # 0.0 to 1.0
    votes: List[bool]  # Individual agent votes
    characters: List[str]  # Characters involved in dialogue
    reasoning: List[str]  # Agent reasoning


@dataclass
class DialogueLine:
    """A single line of dialogue."""
    character: str
    text: str
    emotion: str = ""
    action: str = ""  # Accompanying action/gesture
    # ElevenLabs-optimized text with bracketed vocal cues
    elevenlabs_text: str = ""


@dataclass
class DialogueResult:
    """Result of dialogue generation."""
    lines: List[DialogueLine]
    success: bool
    error: Optional[str] = None


class DialogueConsensus:
    """
    3-agent consensus system for detecting dialogue in beats.

    Uses majority voting (2/3) to determine if a beat contains dialogue.
    """

    def __init__(self, llm_caller):
        """
        Initialize dialogue consensus.

        Args:
            llm_caller: Async function to call LLM (prompt: str) -> str
        """
        self.llm_caller = llm_caller
        self.threshold = 2  # 2 out of 3 agents must agree

    async def detect_dialogue(
        self,
        beat_content: str,
        beat_type: str,
        character_tags: List[str]
    ) -> DialogueDetectionResult:
        """
        Detect if a beat contains dialogue using 3-agent consensus.

        Args:
            beat_content: The beat content to analyze
            beat_type: Type of beat (action, dialogue, reaction, etc.)
            character_tags: Character tags present in the beat

        Returns:
            DialogueDetectionResult with consensus decision
        """
        logger.info(f"Running dialogue detection consensus for beat type: {beat_type}")

        # Create 3 detection prompts with different perspectives
        prompts = [
            self._create_detection_prompt_1(beat_content, beat_type, character_tags),
            self._create_detection_prompt_2(beat_content, beat_type, character_tags),
            self._create_detection_prompt_3(beat_content, beat_type, character_tags)
        ]

        # Run all 3 agents in parallel
        responses = await asyncio.gather(*[
            self.llm_caller(prompt) for prompt in prompts
        ])

        # Parse votes
        votes = []
        reasoning = []
        detected_characters = set()

        for i, response in enumerate(responses):
            vote, chars, reason = self._parse_detection_response(response)
            votes.append(vote)
            reasoning.append(reason)
            detected_characters.update(chars)
            logger.debug(f"Agent {i+1} vote: {vote} | Characters: {chars}")

        # Calculate consensus
        yes_votes = sum(votes)
        has_dialogue = yes_votes >= self.threshold
        confidence = yes_votes / len(votes)

        logger.info(f"Dialogue detection: {has_dialogue} (confidence: {confidence:.2f})")

        return DialogueDetectionResult(
            has_dialogue=has_dialogue,
            confidence=confidence,
            votes=votes,
            characters=list(detected_characters),
            reasoning=reasoning
        )

    def _create_detection_prompt_1(
        self,
        beat_content: str,
        beat_type: str,
        character_tags: List[str]
    ) -> str:
        """Agent 1: Focus on explicit dialogue markers."""
        return f"""Analyze this story beat and determine if it contains DIALOGUE (spoken words between characters).

Beat Type: {beat_type}
Characters Present: {', '.join(character_tags) if character_tags else 'Unknown'}

Beat Content:
{beat_content}

Focus on EXPLICIT dialogue markers:
- Quotation marks
- "Said", "asked", "replied" dialogue tags
- Direct speech patterns

Respond in this format:
DIALOGUE: YES/NO
CHARACTERS: [list character names who speak]
REASONING: [brief explanation]"""

    def _create_detection_prompt_2(
        self,
        beat_content: str,
        beat_type: str,
        character_tags: List[str]
    ) -> str:
        """Agent 2: Focus on conversational context."""
        return f"""Analyze this story beat for CONVERSATIONAL CONTENT (characters talking to each other).

Beat Type: {beat_type}
Characters: {', '.join(character_tags) if character_tags else 'Unknown'}

Content:
{beat_content}

Look for:
- Conversations or exchanges between characters
- Questions and responses
- Verbal communication (even if not in quotes)

Respond:
DIALOGUE: YES/NO
CHARACTERS: [who is speaking]
REASONING: [why you decided this]"""

    def _create_detection_prompt_3(
        self,
        beat_content: str,
        beat_type: str,
        character_tags: List[str]
    ) -> str:
        """Agent 3: Focus on beat type and narrative structure."""
        return f"""Determine if this beat requires DIALOGUE to be fully realized.

Beat Type: {beat_type}
Characters: {', '.join(character_tags) if character_tags else 'Unknown'}

Beat:
{beat_content}

Consider:
- Does the beat type suggest dialogue? (dialogue, reaction beats often have speech)
- Would dialogue enhance this beat?
- Are there implied conversations?

Format:
DIALOGUE: YES/NO
CHARACTERS: [speakers]
REASONING: [your analysis]"""

    def _parse_detection_response(self, response: str) -> Tuple[bool, List[str], str]:
        """
        Parse agent response for dialogue detection.

        Returns:
            (has_dialogue, characters, reasoning)
        """
        lines = response.strip().split('\n')
        has_dialogue = False
        characters = []
        reasoning = ""

        for line in lines:
            line = line.strip()
            if line.startswith("DIALOGUE:"):
                vote_text = line.split(":", 1)[1].strip().upper()
                has_dialogue = "YES" in vote_text
            elif line.startswith("CHARACTERS:"):
                char_text = line.split(":", 1)[1].strip()
                # Parse character list (handle various formats)
                char_text = char_text.strip("[]")
                if char_text and char_text.lower() not in ["none", "unknown", "n/a"]:
                    characters = [c.strip() for c in char_text.split(",")]
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()

        return has_dialogue, characters, reasoning



class MultiCharacterRoleplay:
    """
    Multi-character dialogue generation using I/O roleplay pattern.

    Each character gets their own roleplay agent that converses with
    other character agents to construct authentic dialogue.
    """

    def __init__(self, llm_caller):
        """
        Initialize multi-character roleplay.

        Args:
            llm_caller: Async function that calls LLM with a prompt
        """
        self.llm_caller = llm_caller

    async def generate_dialogue(
        self,
        beat_content: str,
        characters: List[str],
        character_descriptions: Dict[str, str],
        num_exchanges: int = 3
    ) -> DialogueResult:
        """
        Generate dialogue between multiple characters.

        Args:
            beat_content: The beat content describing the scene
            characters: List of character names involved
            character_descriptions: Dict mapping character names to descriptions
            num_exchanges: Number of dialogue exchanges to generate

        Returns:
            DialogueResult with generated dialogue lines
        """
        if not characters:
            return DialogueResult(lines=[], success=False, error="No characters specified")

        if len(characters) == 1:
            # Single character - use simple roleplay
            return await self._generate_single_character_dialogue(
                beat_content, characters[0], character_descriptions.get(characters[0], "")
            )

        # Multi-character - use I/O roleplay
        return await self._generate_multi_character_dialogue(
            beat_content, characters, character_descriptions, num_exchanges
        )

    async def _generate_single_character_dialogue(
        self,
        beat_content: str,
        character: str,
        description: str
    ) -> DialogueResult:
        """Generate dialogue for a single character (monologue/thinking aloud)."""
        logger.info(f"Generating single-character dialogue for {character}")

        prompt = f"""You are {character}. Generate authentic dialogue for this scene.

Scene Context:
{beat_content}

Character: {character}
{description}

Generate 2-3 lines of dialogue this character would speak in this moment.
Consider their personality, emotional state, and the situation.

Format each line as:
CHARACTER: "dialogue text" [emotion/action if applicable]

Example:
ALICE: "I can't believe this is happening." [shocked]
ALICE: "We need to get out of here, now!" [urgent/grabs bag]"""

        try:
            response = await self.llm_caller(prompt)

            # Parse dialogue from response
            lines = self._parse_dialogue_from_text(response, [character])

            return DialogueResult(lines=lines, success=True)

        except Exception as e:
            logger.error(f"Error generating single-character dialogue: {e}")
            return DialogueResult(lines=[], success=False, error=str(e))

    async def _generate_multi_character_dialogue(
        self,
        beat_content: str,
        characters: List[str],
        character_descriptions: Dict[str, str],
        num_exchanges: int
    ) -> DialogueResult:
        """Generate dialogue between multiple characters."""
        logger.info(f"Generating multi-character dialogue: {', '.join(characters)}")

        # Create context for the conversation
        context = f"""Scene Context:
{beat_content}

Characters in this scene:
"""
        for char in characters:
            desc = character_descriptions.get(char, "No description available")
            context += f"\n{char}: {desc}"

        context += f"\n\nGenerate a natural conversation between these characters for this scene."
        context += f"\nCreate {num_exchanges} exchanges (back-and-forth dialogue)."

        try:
            # Generate dialogue
            prompt = f"""{context}

Format each line as:
CHARACTER: "dialogue text" [emotion/action if any]

Example:
ALICE: "I can't believe this is happening." [shocked]
BOB: "We need to stay calm." [reassuring/places hand on shoulder]

Generate natural, character-appropriate dialogue."""

            result = await self.llm_caller(prompt)

            # Parse dialogue lines
            lines = self._parse_dialogue_from_text(result, characters)

            return DialogueResult(lines=lines, success=True)

        except Exception as e:
            logger.error(f"Error generating multi-character dialogue: {e}")
            return DialogueResult(lines=[], success=False, error=str(e))



    def _parse_dialogue_from_text(
        self,
        text: str,
        characters: List[str]
    ) -> List[DialogueLine]:
        """Parse dialogue lines from generated text."""
        lines = []

        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Format: CHARACTER: "text" [emotion/action]
            for char in characters:
                if line.upper().startswith(f"{char.upper()}:"):
                    rest = line.split(":", 1)[1].strip()

                    # Extract dialogue text (in quotes)
                    dialogue_text = ""
                    emotion = ""
                    action = ""

                    if '"' in rest:
                        parts = rest.split('"')
                        if len(parts) >= 2:
                            dialogue_text = parts[1]
                            # Check for emotion/action in brackets
                            if len(parts) > 2 and '[' in parts[2]:
                                bracket_content = parts[2].split('[')[1].split(']')[0]
                                if '/' in bracket_content:
                                    emotion, action = bracket_content.split('/', 1)
                                else:
                                    emotion = bracket_content
                    else:
                        dialogue_text = rest

                    if dialogue_text:
                        lines.append(DialogueLine(
                            character=char,
                            text=dialogue_text.strip(),
                            emotion=emotion.strip(),
                            action=action.strip()
                        ))
                    break

        return lines


class ElevenLabsDialogueFormatter:
    """
    Formats dialogue for ElevenLabs text-to-speech synthesis.

    Uses bracketed annotations to convey emotion, pacing, and vocal intention:
    - [whispered] - Soft, intimate delivery
    - [shouted] - Loud, forceful delivery
    - [sarcastic] - Ironic tone
    - [sad] - Sorrowful, low energy
    - [excited] - High energy, fast pace
    - [angry] - Aggressive, tense
    - [nervous] - Hesitant, shaky
    - [confident] - Assured, steady
    - [pause] - Brief pause in speech
    - [long pause] - Extended pause
    - [slowly] - Deliberate, drawn out
    - [quickly] - Rushed, rapid
    - [breaking] - Voice cracking with emotion
    """

    # Emotion to ElevenLabs bracket mapping
    EMOTION_CUES = {
        # Basic emotions
        "happy": "[cheerfully]",
        "sad": "[sadly]",
        "angry": "[angrily]",
        "afraid": "[fearfully]",
        "surprised": "[with surprise]",
        "disgusted": "[with disgust]",
        # Complex emotions
        "nervous": "[nervously]",
        "confident": "[confidently]",
        "sarcastic": "[sarcastically]",
        "excited": "[excitedly]",
        "worried": "[worriedly]",
        "relieved": "[with relief]",
        "frustrated": "[with frustration]",
        "hopeful": "[hopefully]",
        "desperate": "[desperately]",
        "tender": "[tenderly]",
        "threatening": "[threateningly]",
        "pleading": "[pleadingly]",
        "curious": "[curiously]",
        "amused": "[with amusement]",
        "bitter": "[bitterly]",
        "wistful": "[wistfully]",
        "determined": "[with determination]",
        "resigned": "[with resignation]",
        "shocked": "[in shock]",
        "intimate": "[intimately]",
        "cold": "[coldly]",
        "warm": "[warmly]",
    }

    # Delivery style cues
    DELIVERY_CUES = {
        "whisper": "[whispered]",
        "shout": "[shouted]",
        "mutter": "[muttered]",
        "stammer": "[stammering]",
        "breathless": "[breathlessly]",
        "monotone": "[flatly]",
        "sing-song": "[in a sing-song voice]",
        "gruff": "[gruffly]",
        "soft": "[softly]",
        "loud": "[loudly]",
    }

    # Pacing cues
    PACING_CUES = {
        "slow": "[slowly]",
        "fast": "[quickly]",
        "hesitant": "[hesitantly]",
        "deliberate": "[deliberately]",
        "rushed": "[rushing]",
    }

    def __init__(self, llm_caller=None):
        """
        Initialize the formatter.

        Args:
            llm_caller: Optional async LLM caller for advanced formatting
        """
        self.llm_caller = llm_caller

    def format_line(
        self,
        text: str,
        emotion: str = "",
        action: str = "",
        character_vocal_profile: Dict[str, Any] = None
    ) -> str:
        """
        Format a dialogue line for ElevenLabs synthesis.

        Args:
            text: The raw dialogue text
            emotion: The emotional state (e.g., "angry", "sad")
            action: Accompanying action that might affect delivery
            character_vocal_profile: Character's vocal_description dict

        Returns:
            Text formatted with ElevenLabs-compatible bracketed cues
        """
        cues = []

        # Add emotion cue if present
        if emotion:
            emotion_lower = emotion.lower().strip()
            if emotion_lower in self.EMOTION_CUES:
                cues.append(self.EMOTION_CUES[emotion_lower])
            else:
                # Try partial match
                for key, cue in self.EMOTION_CUES.items():
                    if key in emotion_lower or emotion_lower in key:
                        cues.append(cue)
                        break
                else:
                    # Use raw emotion as cue
                    cues.append(f"[{emotion_lower}]")

        # Infer delivery from action
        if action:
            action_lower = action.lower()
            if "whisper" in action_lower:
                cues.append("[whispered]")
            elif "shout" in action_lower or "yell" in action_lower:
                cues.append("[shouted]")
            elif "mutter" in action_lower or "mumble" in action_lower:
                cues.append("[muttered]")
            elif "stammer" in action_lower or "stutter" in action_lower:
                cues.append("[stammering]")

        # Build the formatted text
        if cues:
            prefix = " ".join(cues) + " "
            return f"{prefix}{text}"

        return text

    def format_dialogue_lines(
        self,
        lines: List[DialogueLine],
        character_profiles: Dict[str, Dict[str, Any]] = None
    ) -> List[DialogueLine]:
        """
        Format multiple dialogue lines for ElevenLabs.

        Args:
            lines: List of DialogueLine objects
            character_profiles: Dict mapping character tags to their profiles

        Returns:
            List of DialogueLine objects with elevenlabs_text populated
        """
        character_profiles = character_profiles or {}

        formatted_lines = []
        for line in lines:
            vocal_profile = None
            if line.character in character_profiles:
                vocal_profile = character_profiles[line.character].get("vocal_description", {})

            elevenlabs_text = self.format_line(
                text=line.text,
                emotion=line.emotion,
                action=line.action,
                character_vocal_profile=vocal_profile
            )

            formatted_lines.append(DialogueLine(
                character=line.character,
                text=line.text,
                emotion=line.emotion,
                action=line.action,
                elevenlabs_text=elevenlabs_text
            ))

        return formatted_lines

    async def generate_elevenlabs_dialogue(
        self,
        beat_content: str,
        characters: List[str],
        character_profiles: Dict[str, Dict[str, Any]],
        num_exchanges: int = 3
    ) -> DialogueResult:
        """
        Generate dialogue optimized for ElevenLabs TTS.

        Uses bracketed annotations for emotion, pacing, and delivery.

        Args:
            beat_content: The scene/beat content
            characters: List of character names/tags
            character_profiles: Dict with character profiles including vocal_description
            num_exchanges: Number of dialogue exchanges

        Returns:
            DialogueResult with ElevenLabs-optimized dialogue
        """
        if not self.llm_caller:
            return DialogueResult(
                lines=[],
                success=False,
                error="LLM caller required for dialogue generation"
            )

        # Build vocal profile context for each character
        vocal_context = ""
        for char in characters:
            profile = character_profiles.get(char, {})
            vocal = profile.get("vocal_description", {})
            speech = profile.get("speech", {})

            if vocal or speech:
                vocal_context += f"\n{char} VOICE:\n"
                if vocal.get("pitch"):
                    vocal_context += f"  - Pitch: {vocal['pitch']}\n"
                if vocal.get("timbre"):
                    vocal_context += f"  - Timbre: {vocal['timbre']}\n"
                if vocal.get("pace"):
                    vocal_context += f"  - Pace: {vocal['pace']}\n"
                if vocal.get("accent"):
                    vocal_context += f"  - Accent: {vocal['accent']}\n"
                if vocal.get("distinctive_features"):
                    features = ", ".join(vocal['distinctive_features']) if isinstance(vocal['distinctive_features'], list) else vocal['distinctive_features']
                    vocal_context += f"  - Distinctive: {features}\n"
                if speech.get("speech_rhythm"):
                    vocal_context += f"  - Speech rhythm: {speech['speech_rhythm']}\n"
                if speech.get("vocabulary_level"):
                    vocal_context += f"  - Vocabulary: {speech['vocabulary_level']}\n"

        prompt = f"""Generate dialogue for this scene, optimized for ElevenLabs text-to-speech synthesis.

SCENE:
{beat_content}

CHARACTERS PRESENT: {', '.join(characters)}

CHARACTER VOICE PROFILES:
{vocal_context if vocal_context else "No specific voice profiles available."}

Generate {num_exchanges} exchanges of natural dialogue. For each line, include:
1. The character name
2. The dialogue text WITH bracketed vocal cues for TTS

BRACKETED CUE GUIDE (use these to convey emotion and delivery):
- Emotions: [sadly], [angrily], [excitedly], [nervously], [confidently], [sarcastically], [tenderly], [desperately], [coldly], [warmly]
- Delivery: [whispered], [shouted], [muttered], [stammering], [breathlessly], [softly], [loudly]
- Pacing: [slowly], [quickly], [hesitantly], [deliberately], [with a pause]
- Breaks: [voice breaking], [trailing off...], [interrupted—]

EXAMPLE OUTPUT:
ALICE: [nervously] "I... I don't know if I can do this." [with a pause] "But I have to try."
BOB: [reassuringly] "You've got this. I believe in you."
ALICE: [voice breaking] "What if I fail?"
BOB: [firmly] "Then we fail together. [softly] But we won't."

FORMAT:
CHARACTER: [cue] "dialogue text" [additional cues as needed]

Generate authentic dialogue that matches each character's voice profile and the emotional context of the scene."""

        try:
            response = await self.llm_caller(prompt)
            lines = self._parse_elevenlabs_dialogue(response, characters)

            return DialogueResult(lines=lines, success=True)

        except Exception as e:
            logger.error(f"Error generating ElevenLabs dialogue: {e}")
            return DialogueResult(lines=[], success=False, error=str(e))

    def _parse_elevenlabs_dialogue(
        self,
        response: str,
        characters: List[str]
    ) -> List[DialogueLine]:
        """Parse ElevenLabs-formatted dialogue from LLM response."""
        lines = []

        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue

            for char in characters:
                if line.upper().startswith(f"{char.upper()}:"):
                    rest = line.split(":", 1)[1].strip()

                    # The rest contains the ElevenLabs-formatted text
                    # Extract the raw dialogue (text in quotes) and the full formatted version
                    dialogue_text = ""
                    emotion = ""

                    # Find text in quotes (re is imported at module level)
                    quote_match = re.search(r'"([^"]+)"', rest)
                    if quote_match:
                        dialogue_text = quote_match.group(1)

                    # Extract leading emotion cue
                    cue_match = re.match(r'\[([^\]]+)\]', rest)
                    if cue_match:
                        emotion = cue_match.group(1)

                    # The full elevenlabs_text is the entire formatted line (without character prefix)
                    elevenlabs_text = rest

                    if dialogue_text or elevenlabs_text:
                        lines.append(DialogueLine(
                            character=char,
                            text=dialogue_text,
                            emotion=emotion,
                            action="",
                            elevenlabs_text=elevenlabs_text
                        ))
                    break

        return lines


@dataclass
class SceneDialogue:
    """Dialogue for an entire scene."""
    scene_number: int
    scene_context: str
    dialogue_lines: List[DialogueLine]
    characters_present: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scene_number": self.scene_number,
            "scene_context": self.scene_context,
            "characters_present": self.characters_present,
            "dialogue_lines": [
                {
                    "character": line.character,
                    "text": line.text,
                    "emotion": line.emotion,
                    "action": line.action,
                    "elevenlabs_text": line.elevenlabs_text
                }
                for line in self.dialogue_lines
            ]
        }



