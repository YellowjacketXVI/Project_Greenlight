"""
Prompt Refinement Agent (Opus-powered)

A post-director refinement agent that analyzes and fixes visual prompts
to counter common AI image generation issues:

1. Missing characters - ensures all tagged characters are clearly described
2. Tag leakage - prevents tags from rendering as visible text
3. Costume inconsistency - enforces period/style consistency
4. Flat/posed look - adds naturalistic motion and authentic expressions
5. Generic compositions - adds specific visual storytelling elements

This agent reads the visual_script.json and prompts_log.json, analyzes
issues, and writes corrected versions back.

Uses Claude Opus for maximum quality and nuanced understanding.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from greenlight.agents.base_agent import BaseAgent, AgentConfig, AgentResponse

logger = get_logger("agents.prompt_refinement")


# =============================================================================
# ANTI-PATTERN PROMPT - Core rules to counter flat/fake AI outputs
# =============================================================================

ANTI_PATTERN_PROMPT = """
## CRITICAL ANTI-PATTERNS TO AVOID IN IMAGE GENERATION PROMPTS

You are refining prompts for cinematic storyboard generation. The following issues
plague AI image generation and MUST be actively countered in every prompt:

### 1. TAG LEAKAGE (HIGHEST PRIORITY)
- NEVER let tags like [CHAR_MEI] or [LOC_PALACE] render as visible text in the image
- Tags are REFERENCE MARKERS for the AI, not literal text to display
- BAD: "Show [CHAR_MEI] standing by [LOC_PALACE]" → AI may render "CHAR_MEI" as text
- GOOD: "A young Chinese woman (reference: CHAR_MEI) stands before the palace entrance"
- Use format: "(reference: TAG)" or describe the character by their visual traits

### 2. MISSING CHARACTERS IN MULTI-PERSON SHOTS
- When a prompt mentions multiple characters, EACH must be distinctly described
- Include: position (screen-left/right/center), facing direction, key visual identifiers
- BAD: "CHAR_MEI and CHAR_LIN in the courtyard"
- GOOD: "Two figures in the courtyard: screen-left, a young woman in dark silk robes
  with jade hairpin (CHAR_MEI) faces right; screen-right, a middle-aged man in worn
  workman's clothes (CHAR_LIN) faces left toward her"

### 3. COSTUME/PERIOD INCONSISTENCY
- AI models default to modern clothing. ALWAYS specify period-accurate attire.
- Include: fabric type, color, style period, condition, cultural context
- BAD: "A man helps a woman up from the muddy road"
- GOOD: "A man in traditional Han dynasty workman's tunic (褂, grey cotton, patched at
  elbows, dirt-stained from labor) reaches down to help a woman in formal silk hanfu
  (dark purple with gold embroidery, now mud-splattered)"

### 4. FLAT/POSED/THEATRICAL LOOK
- AI images often look like posed photographs or stage plays
- Counter with: mid-action moments, asymmetric composition, imperfect details
- BAD: "She looks at him with longing"
- GOOD: "Caught mid-motion: her head turning, hair still settling from movement,
  one hand arrested mid-gesture near her throat, eyes not quite meeting his -
  that vulnerable moment before composure returns"

### 5. GENERIC EXPRESSIONS AND BODY LANGUAGE
- "Happy", "sad", "angry" produce generic stock expressions
- Use: specific micro-expressions, physical tells, cultural gesture vocabulary
- BAD: "She looks angry at him"
- GOOD: "Her jaw tightens almost imperceptibly, chin lifting in that particular
  way that signals controlled fury. Her hands have stilled completely - too still -
  while her eyes hold his with the flat calm before a storm"

### 6. EMPTY/GENERIC BACKGROUNDS
- AI often produces blurry or generic backgrounds
- Include: specific architectural details, environmental storytelling, depth layers
- BAD: "Standing in an ancient Chinese building"
- GOOD: "In the shadow of carved wooden eaves: latticed windows throw geometric
  shadows across weathered stone floors, a bronze incense burner trails thin smoke
  that catches the afternoon light slanting through dust motes, silk scrolls hang
  on age-darkened walls"

### 7. POOR LIGHTING DESCRIPTIONS
- "Natural lighting" produces flat, even lighting with no mood
- Specify: direction, quality, color temperature, shadow behavior, practical sources
- BAD: "Soft morning light"
- GOOD: "Dawn light from the east window: golden-warm but still gentle, casting
  long shadows that stretch across the floor toward camera, key light on her face
  with deep shadow pooling in her eye sockets, rim light catching loose hairs"

### 8. STATIC CAMERA FEEL
- Even still images should suggest the moment before/after
- Include: implied motion, camera relationship to action, breathing room in frame
- BAD: "Wide shot of the courtyard scene"
- GOOD: "Wide establishing shot, camera low and slightly Dutch-angled as if we've
  just ducked through the courtyard gate - negative space screen-left creates
  tension, anticipating movement from that direction"

### PROMPT STRUCTURE FOR MAXIMUM EFFECTIVENESS

Every refined prompt should follow this structure:
1. SHOT SETUP: Type, angle, lens implication, camera attitude
2. SUBJECT PLACEMENT: Specific positions using rule of thirds, facing directions
3. CHARACTER DETAILS: Period costume, physical state, micro-expressions
4. ACTION/MOMENT: What's happening in THIS instant (not before, not after)
5. ENVIRONMENT: Foreground, midground, background with specific details
6. LIGHTING: Direction, quality, mood, shadows, practical sources
7. ATMOSPHERE: Weather, particles, mood, color palette
8. VISUAL SUBTEXT: What the composition MEANS (framing = emotion)

Remember: You're not describing a photograph, you're DIRECTING a moment in a film.
Every choice should serve the story's emotional truth.
"""


@dataclass
class RefinementResult:
    """Result from prompt refinement."""
    frame_id: str
    original_prompt: str
    refined_prompt: str
    issues_found: List[str]
    changes_made: List[str]
    confidence: float  # 0-1 scale


class PromptRefinementAgent(BaseAgent):
    """
    Opus-powered agent that refines visual prompts to counter AI image generation issues.

    Analyzes prompts for common problems and rewrites them with specific,
    naturalistic, period-accurate, and emotionally resonant descriptions.
    """

    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        world_config: Optional[Dict[str, Any]] = None,
        visual_style: str = ""
    ):
        config = AgentConfig(
            name="PromptRefinementAgent",
            description="Refines visual prompts to counter flat/fake AI outputs",
            llm_function=LLMFunction.STORY_ANALYSIS,  # Use analysis for quality
            system_prompt=self._build_system_prompt(),
            temperature=0.3,  # Lower temp for consistent quality
            max_tokens=2000,
            retry_count=2
        )
        super().__init__(config, llm_caller)

        self.world_config = world_config or {}
        self.visual_style = visual_style
        self._character_cache: Dict[str, Dict] = {}
        self._load_character_data()

    def _build_system_prompt(self) -> str:
        return f"""You are a senior cinematographer and visual director refining storyboard prompts.
Your role is to transform generic AI image prompts into specific, evocative, cinematic descriptions
that will produce authentic, emotionally resonant images.

{ANTI_PATTERN_PROMPT}

You have deep knowledge of:
- Classical cinematography techniques (Kurosawa, Wong Kar-wai, Zhang Yimou)
- Period-accurate costume and set design
- Human body language and micro-expressions
- Visual storytelling and subtext
- Cultural authenticity in historical settings

When refining prompts, you PRESERVE all essential story information while ENHANCING
the visual specificity and emotional depth."""

    def _load_character_data(self) -> None:
        """Load character visual data from world_config for reference."""
        for char in self.world_config.get("characters", []):
            tag = char.get("tag", "")
            if tag:
                self._character_cache[tag] = {
                    "name": char.get("name", ""),
                    "visual": char.get("visual", {}),
                    "description": char.get("description", ""),
                    "costume": char.get("visual", {}).get("costume_default", "")
                }

    def _get_character_visual_desc(self, tag: str) -> str:
        """Get character visual description from cache."""
        if tag in self._character_cache:
            char = self._character_cache[tag]
            parts = []
            if char.get("name"):
                parts.append(char["name"])
            if char.get("costume"):
                parts.append(f"wearing {char['costume']}")
            if char.get("description"):
                parts.append(char["description"][:100])
            return ", ".join(parts) if parts else tag
        return tag

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Refine a batch of prompts.

        Args:
            input_data: {
                "prompts": List of dicts with frame_id, prompt, tags
                "world_config": World config for character data
                "visual_style": Style notes
            }

        Returns:
            AgentResponse with list of RefinementResult
        """
        prompts = input_data.get("prompts", [])
        if not prompts:
            return AgentResponse.error_response("No prompts provided")

        results = []

        for prompt_data in prompts:
            try:
                result = await self._refine_single_prompt(prompt_data)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to refine prompt {prompt_data.get('frame_id')}: {e}")
                results.append(RefinementResult(
                    frame_id=prompt_data.get("frame_id", "unknown"),
                    original_prompt=prompt_data.get("prompt", ""),
                    refined_prompt=prompt_data.get("prompt", ""),  # Keep original on error
                    issues_found=["Error during refinement"],
                    changes_made=[],
                    confidence=0.0
                ))

        return AgentResponse.success_response(
            content=results,
            metadata={"total_refined": len(results)}
        )

    async def _refine_single_prompt(self, prompt_data: Dict[str, Any]) -> RefinementResult:
        """Refine a single prompt."""
        frame_id = prompt_data.get("frame_id", "unknown")
        original_prompt = prompt_data.get("prompt", "")
        tags = prompt_data.get("tags", {})
        scene_context = prompt_data.get("scene_context", "")

        # Build character context
        char_context = []
        for char_tag in tags.get("characters", []):
            desc = self._get_character_visual_desc(char_tag)
            char_context.append(f"  - {char_tag}: {desc}")

        char_context_str = "\n".join(char_context) if char_context else "  (none specified)"

        # Build refinement prompt
        prompt = f"""Analyze and refine this storyboard frame prompt.

FRAME ID: {frame_id}

ORIGINAL PROMPT:
{original_prompt}

CHARACTERS IN SCENE:
{char_context_str}

SCENE CONTEXT:
{scene_context or "Not specified"}

VISUAL STYLE NOTES:
{self.visual_style or "Period-appropriate, cinematic"}

---

TASK:
1. Identify issues with this prompt (tag leakage, missing characters, generic descriptions, etc.)
2. Rewrite the prompt following the anti-pattern guidelines
3. Ensure ALL characters mentioned in tags appear distinctly in the description
4. Add period-accurate costume details if missing
5. Add specific micro-expressions and body language
6. Add environmental and lighting specificity

OUTPUT FORMAT:
ISSUES FOUND:
- [list each issue]

CHANGES MADE:
- [list each change]

REFINED PROMPT:
[Your complete refined prompt here - this will directly replace the original]

CONFIDENCE: [0.0-1.0 how confident you are this refinement improves the prompt]
"""

        response = await self.call_llm(prompt)
        return self._parse_refinement_response(frame_id, original_prompt, response)

    def _parse_refinement_response(
        self,
        frame_id: str,
        original_prompt: str,
        response: str
    ) -> RefinementResult:
        """Parse the LLM response into a RefinementResult."""
        issues = []
        changes = []
        refined_prompt = original_prompt
        confidence = 0.5

        # Extract issues
        issues_match = re.search(r'ISSUES FOUND:\s*\n(.*?)(?=CHANGES MADE:|REFINED PROMPT:|$)',
                                  response, re.DOTALL | re.IGNORECASE)
        if issues_match:
            issues_text = issues_match.group(1)
            issues = [line.strip().lstrip('-').strip()
                     for line in issues_text.split('\n')
                     if line.strip() and line.strip() != '-']

        # Extract changes
        changes_match = re.search(r'CHANGES MADE:\s*\n(.*?)(?=REFINED PROMPT:|$)',
                                   response, re.DOTALL | re.IGNORECASE)
        if changes_match:
            changes_text = changes_match.group(1)
            changes = [line.strip().lstrip('-').strip()
                      for line in changes_text.split('\n')
                      if line.strip() and line.strip() != '-']

        # Extract refined prompt
        prompt_match = re.search(r'REFINED PROMPT:\s*\n(.*?)(?=CONFIDENCE:|$)',
                                  response, re.DOTALL | re.IGNORECASE)
        if prompt_match:
            refined_prompt = prompt_match.group(1).strip()

        # Extract confidence
        conf_match = re.search(r'CONFIDENCE:\s*([0-9.]+)', response, re.IGNORECASE)
        if conf_match:
            try:
                confidence = float(conf_match.group(1))
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                confidence = 0.5

        return RefinementResult(
            frame_id=frame_id,
            original_prompt=original_prompt,
            refined_prompt=refined_prompt,
            issues_found=issues,
            changes_made=changes,
            confidence=confidence
        )

    def parse_response(self, raw_response: str) -> Any:
        """Parse raw response - required by base class."""
        return raw_response


async def refine_visual_script(
    project_path: Path,
    llm_caller: Callable,
    world_config: Optional[Dict[str, Any]] = None,
    visual_style: str = "",
    min_confidence: float = 0.6
) -> Dict[str, Any]:
    """
    Refine all prompts in a project's visual script.

    Reads visual_script.json, refines each prompt, and writes back.

    Args:
        project_path: Path to project root
        llm_caller: Async function for LLM calls
        world_config: World config dict (loaded if not provided)
        visual_style: Visual style notes
        min_confidence: Minimum confidence to apply refinement

    Returns:
        Dict with refinement statistics
    """
    project_path = Path(project_path)

    # Load visual script
    vs_path = project_path / "storyboard" / "visual_script.json"
    if not vs_path.exists():
        logger.error(f"Visual script not found: {vs_path}")
        return {"error": "Visual script not found"}

    with open(vs_path, 'r', encoding='utf-8') as f:
        visual_script = json.load(f)

    # Load world config if not provided
    if not world_config:
        wc_path = project_path / "world_bible" / "world_config.json"
        if wc_path.exists():
            with open(wc_path, 'r', encoding='utf-8') as f:
                world_config = json.load(f)
        else:
            world_config = {}

    # Initialize agent
    agent = PromptRefinementAgent(
        llm_caller=llm_caller,
        world_config=world_config,
        visual_style=visual_style
    )

    # Collect all prompts
    prompts_to_refine = []
    for scene in visual_script.get("scenes", []):
        scene_num = scene.get("scene_number", 0)
        for frame in scene.get("frames", []):
            prompts_to_refine.append({
                "frame_id": frame.get("frame_id", ""),
                "prompt": frame.get("prompt", ""),
                "tags": frame.get("tags", {}),
                "scene_context": f"Scene {scene_num}"
            })

    # Refine in batches
    batch_size = 5
    all_results = []

    for i in range(0, len(prompts_to_refine), batch_size):
        batch = prompts_to_refine[i:i+batch_size]
        response = await agent.execute({"prompts": batch})

        if response.success:
            all_results.extend(response.content)

    # Apply refinements back to visual script
    refinement_map = {r.frame_id: r for r in all_results}

    applied = 0
    skipped = 0

    for scene in visual_script.get("scenes", []):
        for frame in scene.get("frames", []):
            frame_id = frame.get("frame_id", "")
            if frame_id in refinement_map:
                result = refinement_map[frame_id]
                if result.confidence >= min_confidence:
                    frame["prompt"] = result.refined_prompt
                    frame["refinement_applied"] = True
                    frame["refinement_confidence"] = result.confidence
                    applied += 1
                else:
                    skipped += 1

    # Save refined visual script
    output_path = project_path / "storyboard" / "visual_script_refined.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(visual_script, f, indent=2, ensure_ascii=False)

    logger.info(f"Refinement complete: {applied} applied, {skipped} skipped")

    # Save refinement log
    log_path = project_path / "storyboard" / "refinement_log.json"
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "total_prompts": len(prompts_to_refine),
        "applied": applied,
        "skipped": skipped,
        "results": [
            {
                "frame_id": r.frame_id,
                "issues": r.issues_found,
                "changes": r.changes_made,
                "confidence": r.confidence
            }
            for r in all_results
        ]
    }
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    return {
        "total": len(prompts_to_refine),
        "applied": applied,
        "skipped": skipped,
        "output_path": str(output_path),
        "log_path": str(log_path)
    }


# Export anti-pattern prompt for use in other modules
def get_anti_pattern_prompt() -> str:
    """Get the anti-pattern prompt for use in other contexts."""
    return ANTI_PATTERN_PROMPT
