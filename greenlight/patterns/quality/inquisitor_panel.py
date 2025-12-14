"""
Inquisitor Panel - Self-Questioning Assembly Pattern

A panel of specialized questioner agents that interrogate the script from
different perspectives, then a synthesizer agent consolidates findings.

Inquisitors:
- VisualInquisitor: Interrogates visual/cinematic aspects
- NarrativeInquisitor: Interrogates narrative flow and story logic
- CharacterInquisitor: Interrogates character authenticity and consistency
- WorldInquisitor: Interrogates world-building and historical accuracy
- TechnicalInquisitor: Interrogates technical formatting and notation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
import asyncio
import json
import re

from greenlight.core.logging_config import get_logger
from greenlight.agents.prompts import AgentPromptLibrary
from .universal_context import UniversalContext, SceneContext

logger = get_logger("patterns.quality.inquisitor")


@dataclass
class InquisitorQuestion:
    """A question posed by an inquisitor."""
    question_id: str
    category: str  # visual, narrative, character, world, technical
    question: str
    answer: str
    confidence: float  # 0-1
    issues_found: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class SynthesisResult:
    """Result of synthesizing all inquisitor findings."""
    score: float  # 0-5
    critical_issues: List[str] = field(default_factory=list)
    directives: List[Dict[str, Any]] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    confidence_by_category: Dict[str, float] = field(default_factory=dict)


@dataclass
class InquisitorReport:
    """Complete report from the Inquisitor Panel."""
    scene_number: int
    questions: List[InquisitorQuestion]
    synthesis: SynthesisResult
    overall_score: float
    critical_issues: List[str]
    improvement_directives: List[Dict[str, Any]]


class BaseInquisitor:
    """Base class for all inquisitors."""
    
    CATEGORY: str = "base"
    QUESTIONS: List[str] = []
    
    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller
    
    async def interrogate(
        self,
        scene_content: str,
        scene_number: int,
        world_config: Dict[str, Any],
        pitch: str,
        location: Optional[Dict] = None
    ) -> List[InquisitorQuestion]:
        """Ask questions about the scene."""
        results = []
        
        for i, question in enumerate(self.QUESTIONS):
            prompt = self._build_prompt(
                question, scene_content, scene_number,
                world_config, pitch, location
            )
            response = await self.llm_caller(prompt)
            parsed = self._parse_qa_response(response)
            
            results.append(InquisitorQuestion(
                question_id=f"{self.CATEGORY.upper()}_{i+1:02d}",
                category=self.CATEGORY,
                question=question,
                answer=parsed.get('answer', ''),
                confidence=parsed.get('confidence', 0.5),
                issues_found=parsed.get('issues', []),
                suggestions=parsed.get('suggestions', [])
            ))
        
        return results
    
    def _build_prompt(
        self,
        question: str,
        scene_content: str,
        scene_number: int,
        world_config: Dict[str, Any],
        pitch: str,
        location: Optional[Dict]
    ) -> str:
        """Build the prompt for a question. Override in subclasses."""
        return f"""You are a {self.CATEGORY} analyst reviewing Scene {scene_number}.

WORLD CONTEXT:
Visual Style: {world_config.get('visual_style', 'live_action')}
Vibe: {world_config.get('vibe', '')}
Themes: {world_config.get('themes', '')}

LOCATION:
{json.dumps(location, indent=2) if location else 'Not specified'}

SCENE CONTENT:
{scene_content}

QUESTION: {question}

Answer honestly. If there are issues, identify them specifically.
Format your response as:
ANSWER: [your detailed answer]
CONFIDENCE: [0.0-1.0]
ISSUES: [list any issues found, one per line starting with -, or "None"]
SUGGESTIONS: [list improvements, one per line starting with -, or "None"]
"""
    
    def _parse_qa_response(self, response: str) -> Dict[str, Any]:
        """Parse Q&A response from LLM."""
        result = {
            'answer': '',
            'confidence': 0.5,
            'issues': [],
            'suggestions': []
        }
        
        # Extract answer
        answer_match = re.search(r'ANSWER:\s*(.+?)(?=CONFIDENCE:|$)', response, re.DOTALL | re.IGNORECASE)
        if answer_match:
            result['answer'] = answer_match.group(1).strip()
        
        # Extract confidence
        conf_match = re.search(r'CONFIDENCE:\s*([\d.]+)', response, re.IGNORECASE)
        if conf_match:
            try:
                result['confidence'] = min(1.0, max(0.0, float(conf_match.group(1))))
            except ValueError:
                pass
        
        # Extract issues
        issues_match = re.search(r'ISSUES:\s*(.+?)(?=SUGGESTIONS:|$)', response, re.DOTALL | re.IGNORECASE)
        if issues_match:
            issues_text = issues_match.group(1).strip()
            if issues_text.lower() != 'none':
                result['issues'] = [
                    item.strip() for item in re.findall(r'[-•]\s*(.+)', issues_text)
                    if item.strip()
                ]
        
        # Extract suggestions
        sugg_match = re.search(r'SUGGESTIONS:\s*(.+?)$', response, re.DOTALL | re.IGNORECASE)
        if sugg_match:
            sugg_text = sugg_match.group(1).strip()
            if sugg_text.lower() != 'none':
                result['suggestions'] = [
                    item.strip() for item in re.findall(r'[-•]\s*(.+)', sugg_text)
                    if item.strip()
                ]

        return result


class VisualInquisitor(BaseInquisitor):
    """Interrogates visual/cinematic aspects of the scene."""

    CATEGORY = "visual"
    QUESTIONS = [
        "Can each beat be captured as a single, clear image?",
        "Are character positions physically possible and dramatically meaningful?",
        "Does the lighting described match the emotional tone?",
        "Are there clear visual anchors for the camera to focus on?",
        "Would a viewer understand the story from images alone?",
        "Are props visible and positioned logically?",
        "Does the scene have visual variety (wide, medium, close)?",
    ]


class NarrativeInquisitor(BaseInquisitor):
    """Interrogates narrative flow and story logic."""

    CATEGORY = "narrative"
    QUESTIONS = [
        "Does this scene advance the plot meaningfully?",
        "Is the cause-and-effect chain clear?",
        "Does the scene have a clear beginning, middle, and end?",
        "Are there any logical gaps or unexplained jumps?",
        "Does the pacing match the emotional content?",
        "Is the scene's purpose clear from the content?",
    ]


class CharacterInquisitor(BaseInquisitor):
    """Interrogates character authenticity and consistency."""

    CATEGORY = "character"
    QUESTIONS = [
        "Do character actions align with their established motivations?",
        "Are character voices distinct and authentic?",
        "Do emotional reactions feel earned and proportional?",
        "Are character positions/movements physically consistent?",
        "Does dialogue reveal character or just convey information?",
        "Are character relationships demonstrated through action?",
    ]

    def _build_prompt(
        self,
        question: str,
        scene_content: str,
        scene_number: int,
        world_config: Dict[str, Any],
        pitch: str,
        location: Optional[Dict]
    ) -> str:
        """Build prompt with character context."""
        chars = world_config.get('characters', [])
        char_context = "\n".join([
            f"[{c.get('tag')}] {c.get('name')}: {c.get('role')} - Want: {c.get('want')} - Flaw: {c.get('flaw')}"
            for c in chars
        ])

        return f"""You are a character analyst reviewing Scene {scene_number}.

CHARACTERS IN WORLD:
{char_context}

SCENE CONTENT:
{scene_content}

QUESTION: {question}

Answer honestly. If there are issues, identify them specifically.
Format your response as:
ANSWER: [your detailed answer]
CONFIDENCE: [0.0-1.0]
ISSUES: [list any issues found, one per line starting with -, or "None"]
SUGGESTIONS: [list improvements, one per line starting with -, or "None"]
"""


class WorldInquisitor(BaseInquisitor):
    """Interrogates world-building and historical accuracy."""

    CATEGORY = "world"
    QUESTIONS = [
        "Are historical/cultural details actively demonstrated?",
        "Do world rules established in world_config appear in the scene?",
        "Is the setting integral to the action or just backdrop?",
        "Are props period-appropriate and meaningful?",
        "Does the atmosphere match the world's established vibe?",
        "Are social dynamics from world_rules reflected in interactions?",
    ]

    def _build_prompt(
        self,
        question: str,
        scene_content: str,
        scene_number: int,
        world_config: Dict[str, Any],
        pitch: str,
        location: Optional[Dict]
    ) -> str:
        """Build prompt with world context."""
        return f"""You are a world-building analyst reviewing Scene {scene_number}.

WORLD CONFIGURATION:
Title: {world_config.get('title', '')}
Themes: {world_config.get('themes', '')}
World Rules: {world_config.get('world_rules', '')}
Vibe: {world_config.get('vibe', '')}
Lighting: {world_config.get('lighting', '')}

LOCATION DETAILS:
{json.dumps(location, indent=2) if location else 'Not specified'}

PROPS IN WORLD:
{json.dumps(world_config.get('props', []), indent=2)}

SCENE CONTENT:
{scene_content}

QUESTION: {question}

Answer honestly. If there are issues, identify them specifically.
Format your response as:
ANSWER: [your detailed answer]
CONFIDENCE: [0.0-1.0]
ISSUES: [list any issues found, one per line starting with -, or "None"]
SUGGESTIONS: [list improvements, one per line starting with -, or "None"]
"""


class TechnicalInquisitor(BaseInquisitor):
    """Interrogates technical formatting and notation.

    Uses TAG_NAMING_RULES from AgentPromptLibrary for consistent notation enforcement.
    """

    CATEGORY = "technical"
    QUESTIONS = [
        "Are all character references using [CHAR_TAG] format with proper prefix?",
        "Are all location references using [LOC_TAG] format with proper prefix?",
        "Are all prop references using [PROP_TAG] format with proper prefix?",
        "Is scene.frame.camera notation correctly formatted (e.g., [1.2.cA])?",
        "Are beat markers properly structured (## Beat: scene.N.XX)?",
        "Is the word count within budget?",
    ]

    def _build_prompt(
        self,
        question: str,
        scene_content: str,
        scene_number: int,
        world_config: Dict[str, Any],
        pitch: str,
        location: Optional[Dict]
    ) -> str:
        """Build prompt with technical context and TAG_NAMING_RULES."""
        all_tags = world_config.get('all_tags', [])

        return f"""You are a technical notation analyst reviewing Scene {scene_number}.

VALID TAGS IN WORLD:
{json.dumps(all_tags, indent=2)}

{AgentPromptLibrary.TAG_NAMING_RULES}

## SCENE.FRAME.CAMERA NOTATION (MANDATORY)

Camera blocks MUST follow this exact format:
- Full ID: `[{{scene}}.{{frame}}.c{{letter}}] ({{shot_type}})`
- Examples: `[1.1.cA] (Wide)`, `[1.2.cB] (Close-up)`, `[2.3.cC] (Medium)`

Scene markers: `## Scene N:` (e.g., `## Scene 1:`, `## Scene 2:`)
Beat markers: `## Beat: scene.N.XX` (e.g., `## Beat: scene.1.01`)
Frame chunks: `(/scene_frame_chunk_start/)` ... `(/scene_frame_chunk_end/)`

**CRITICAL**: Tags are literal identifiers, NOT placeholders.
- ✅ CORRECT: [CHAR_MEI], [LOC_PALACE], [PROP_SWORD], [1.2.cA]
- ❌ WRONG: [CHAR_NAME], [LOC_TAG], [PROP_TAG], [N.N.cX]

SCENE CONTENT:
{scene_content}

QUESTION: {question}

Answer honestly. If there are issues, identify them specifically.
Format your response as:
ANSWER: [your detailed answer]
CONFIDENCE: [0.0-1.0]
ISSUES: [list any issues found, one per line starting with -, or "None"]
SUGGESTIONS: [list improvements, one per line starting with -, or "None"]
"""


class InquisitorPanel:
    """
    Orchestrates the panel of inquisitors for scene analysis.

    Runs all 5 inquisitors in parallel, then synthesizes findings.
    """

    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller
        self.visual = VisualInquisitor(llm_caller)
        self.narrative = NarrativeInquisitor(llm_caller)
        self.character = CharacterInquisitor(llm_caller)
        self.world = WorldInquisitor(llm_caller)
        self.technical = TechnicalInquisitor(llm_caller)

    async def interrogate_scene(
        self,
        scene_content: str,
        scene_number: int,
        world_config: Dict[str, Any],
        pitch: str,
        location: Optional[Dict] = None
    ) -> InquisitorReport:
        """
        Run all inquisitors in parallel on a scene.

        Args:
            scene_content: The scene text content
            scene_number: Scene number
            world_config: World configuration
            pitch: Story pitch
            location: Optional location details

        Returns:
            InquisitorReport with all findings
        """
        logger.info(f"InquisitorPanel: Interrogating Scene {scene_number}...")

        # Parallel interrogation
        results = await asyncio.gather(
            self.visual.interrogate(scene_content, scene_number, world_config, pitch, location),
            self.narrative.interrogate(scene_content, scene_number, world_config, pitch, location),
            self.character.interrogate(scene_content, scene_number, world_config, pitch, location),
            self.world.interrogate(scene_content, scene_number, world_config, pitch, location),
            self.technical.interrogate(scene_content, scene_number, world_config, pitch, location),
        )

        all_questions = []
        for result in results:
            all_questions.extend(result)

        # Synthesis judge consolidates findings
        synthesis = await self._synthesize_findings(all_questions, scene_number, world_config)

        return InquisitorReport(
            scene_number=scene_number,
            questions=all_questions,
            synthesis=synthesis,
            overall_score=synthesis.score,
            critical_issues=synthesis.critical_issues,
            improvement_directives=synthesis.directives
        )

    async def interrogate_all_scenes(
        self,
        scenes: List[Dict[str, Any]],
        world_config: Dict[str, Any],
        pitch: str
    ) -> List[InquisitorReport]:
        """
        Interrogate all scenes.

        Args:
            scenes: List of scene dictionaries
            world_config: World configuration
            pitch: Story pitch

        Returns:
            List of InquisitorReports
        """
        reports = []
        for i, scene in enumerate(scenes):
            scene_content = scene.get('content', str(scene))
            scene_number = scene.get('scene_number', i + 1)
            location_tag = scene.get('location_tag', '')

            # Get location from world_config
            location = None
            for loc in world_config.get('locations', []):
                if loc.get('tag') == location_tag:
                    location = loc
                    break

            report = await self.interrogate_scene(
                scene_content=scene_content,
                scene_number=scene_number,
                world_config=world_config,
                pitch=pitch,
                location=location
            )
            reports.append(report)

        return reports

    async def _synthesize_findings(
        self,
        questions: List[InquisitorQuestion],
        scene_number: int,
        world_config: Dict[str, Any]
    ) -> SynthesisResult:
        """Synthesize all inquisitor findings into actionable report."""

        # Group issues by category
        issues_by_category = {}
        for q in questions:
            if q.issues_found:
                if q.category not in issues_by_category:
                    issues_by_category[q.category] = []
                issues_by_category[q.category].extend(q.issues_found)

        # Calculate average confidence per category
        confidence_by_category = {}
        for category in ['visual', 'narrative', 'character', 'world', 'technical']:
            cat_questions = [q for q in questions if q.category == category]
            if cat_questions:
                confidence_by_category[category] = sum(q.confidence for q in cat_questions) / len(cat_questions)

        # Collect all suggestions
        all_suggestions = []
        for q in questions:
            all_suggestions.extend(q.suggestions)

        # Generate synthesis via LLM
        prompt = f"""You are a synthesis judge reviewing inquisitor findings for Scene {scene_number}.

FINDINGS BY CATEGORY:
{json.dumps(issues_by_category, indent=2)}

CONFIDENCE SCORES BY CATEGORY:
{json.dumps(confidence_by_category, indent=2)}

ALL SUGGESTIONS:
{json.dumps(all_suggestions, indent=2)}

Generate a synthesis report:
1. OVERALL_SCORE (1-5): Based on findings (5 = excellent, 1 = needs major work)
2. CRITICAL_ISSUES: Issues that MUST be fixed (list)
3. IMPROVEMENT_DIRECTIVES: Specific, actionable fixes (list with priority)
4. STRENGTHS: What's working well (list)

Format:
OVERALL_SCORE: [1-5]
CRITICAL_ISSUES:
- [issue 1]
...
IMPROVEMENT_DIRECTIVES:
- [directive 1] (priority: high/medium/low)
...
STRENGTHS:
- [strength 1]
...
"""

        response = await self.llm_caller(prompt)
        return self._parse_synthesis(response, confidence_by_category)

    def _parse_synthesis(
        self,
        response: str,
        confidence_by_category: Dict[str, float]
    ) -> SynthesisResult:
        """Parse synthesis response from LLM."""
        # Extract score
        score_match = re.search(r'OVERALL_SCORE:\s*(\d+)', response, re.IGNORECASE)
        score = float(score_match.group(1)) if score_match else 3.0
        score = min(5.0, max(1.0, score))

        # Extract critical issues
        critical_issues = []
        issues_match = re.search(r'CRITICAL_ISSUES:\s*\n((?:[-•]\s*.+\n?)+)', response, re.IGNORECASE)
        if issues_match:
            critical_issues = [
                item.strip() for item in re.findall(r'[-•]\s*(.+)', issues_match.group(1))
                if item.strip()
            ]

        # Extract directives
        directives = []
        dir_match = re.search(r'IMPROVEMENT_DIRECTIVES:\s*\n((?:[-•]\s*.+\n?)+)', response, re.IGNORECASE)
        if dir_match:
            for item in re.findall(r'[-•]\s*(.+)', dir_match.group(1)):
                priority = 'medium'
                if 'high' in item.lower():
                    priority = 'high'
                elif 'low' in item.lower():
                    priority = 'low'
                directives.append({
                    'directive': item.strip(),
                    'priority': priority
                })

        # Extract strengths
        strengths = []
        str_match = re.search(r'STRENGTHS:\s*\n((?:[-•]\s*.+\n?)+)', response, re.IGNORECASE)
        if str_match:
            strengths = [
                item.strip() for item in re.findall(r'[-•]\s*(.+)', str_match.group(1))
                if item.strip()
            ]

        return SynthesisResult(
            score=score,
            critical_issues=critical_issues,
            directives=directives,
            strengths=strengths,
            confidence_by_category=confidence_by_category
        )

