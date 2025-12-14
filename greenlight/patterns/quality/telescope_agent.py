"""
Telescope Agent - Dual-Focal Analysis Pattern

An agent that operates at two focal lengths:
- WIDE VIEW: Examines the full script with complete world context
- NARROW VIEW: Zooms into individual scenes with filtered context

This enables holistic assessment while maintaining detailed scene analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
import asyncio
import re

from greenlight.core.logging_config import get_logger
from .universal_context import UniversalContext, SceneContext

logger = get_logger("patterns.quality.telescope")


@dataclass
class WideAssessment:
    """Assessment from wide (full script) view."""
    overall_coherence: float  # 0-1
    narrative_flow: float  # 0-1
    character_consistency: float  # 0-1
    world_integration: float  # 0-1
    visual_clarity: float  # 0-1
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    global_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class NarrowAssessment:
    """Assessment from narrow (scene-specific) view."""
    scene_number: int
    scene_score: float  # 0-1
    visual_frameable: bool  # Can each beat be captured as an image?
    character_positions_valid: bool
    world_details_present: bool
    notation_correct: bool
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ReconciliationResult:
    """Result of reconciling wide and narrow assessments."""
    issues: List[Dict[str, Any]] = field(default_factory=list)
    corrections: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    overall_quality: float = 0.0


@dataclass
class TelescopeAnalysis:
    """Complete analysis from Telescope Agent."""
    wide_assessment: WideAssessment
    scene_analyses: List[NarrowAssessment]
    reconciliation: ReconciliationResult
    issues_found: List[Dict[str, Any]] = field(default_factory=list)
    corrections_needed: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TelescopeContext:
    """
    Dual-focal context for Telescope Agent.
    
    Maintains both wide (full script) and narrow (scene-specific) views.
    """
    universal_context: UniversalContext
    current_scene: Optional[SceneContext] = None
    
    # Derived from analysis
    character_arc_summary: str = ""
    location_relationship_map: Dict[str, List[str]] = field(default_factory=dict)
    
    @property
    def full_script(self) -> str:
        return self.universal_context.full_script
    
    @property
    def world_config(self) -> Dict[str, Any]:
        return self.universal_context.world_config
    
    @property
    def pitch(self) -> str:
        return self.universal_context.pitch
    
    def get_wide_prompt_context(self) -> str:
        """Format wide view for LLM prompt."""
        return self.universal_context.for_prompt(include_script=True)
    
    def get_narrow_prompt_context(self) -> str:
        """Format narrow view for LLM prompt."""
        if not self.current_scene:
            return "No scene focused."
        return self.universal_context.for_scene_prompt(self.current_scene)


class TelescopeAgent:
    """
    Agent that operates at dual focal lengths for holistic + detailed analysis.
    
    Process:
    1. Load WIDE VIEW → Generate holistic assessment
    2. For each scene: ZOOM to NARROW VIEW → Detailed analysis
    3. ZOOM OUT → Compare scene findings against holistic assessment
    4. Generate reconciliation report
    """
    
    def __init__(
        self,
        llm_caller: Callable,
        rubric: Optional[Dict[str, Any]] = None
    ):
        self.llm_caller = llm_caller
        self.rubric = rubric or self._default_rubric()
    
    def _default_rubric(self) -> Dict[str, Any]:
        """Default quality rubric for assessment."""
        return {
            "narrative_coherence": {
                "weight": 0.2,
                "criteria": "Story flows logically with clear cause-and-effect"
            },
            "character_consistency": {
                "weight": 0.2,
                "criteria": "Characters act according to established motivations"
            },
            "visual_clarity": {
                "weight": 0.2,
                "criteria": "Each beat can be captured as a clear image"
            },
            "world_integration": {
                "weight": 0.2,
                "criteria": "World details from world_config are demonstrated"
            },
            "notation_correctness": {
                "weight": 0.2,
                "criteria": "Tags and notation follow scene.frame.camera format"
            }
        }
    
    async def analyze_script(
        self,
        universal_context: UniversalContext,
        scenes: List[Dict[str, Any]]
    ) -> TelescopeAnalysis:
        """
        Perform dual-focal analysis of the script.
        
        Args:
            universal_context: The universal context with pitch + world_config
            scenes: List of scene dictionaries with content
            
        Returns:
            TelescopeAnalysis with wide, narrow, and reconciled assessments
        """
        context = TelescopeContext(universal_context=universal_context)
        
        # Phase 1: Wide view holistic assessment
        logger.info("TelescopeAgent: Performing wide view assessment...")
        wide_assessment = await self._assess_wide_view(context)
        
        # Phase 2: Narrow view per-scene analysis (parallel)
        logger.info(f"TelescopeAgent: Analyzing {len(scenes)} scenes in narrow view...")
        scene_analyses = await self._assess_all_scenes(context, scenes)
        
        # Phase 3: Reconciliation
        logger.info("TelescopeAgent: Reconciling wide and narrow assessments...")
        reconciliation = await self._reconcile_views(
            wide_assessment, scene_analyses, context
        )
        
        return TelescopeAnalysis(
            wide_assessment=wide_assessment,
            scene_analyses=scene_analyses,
            reconciliation=reconciliation,
            issues_found=reconciliation.issues,
            corrections_needed=reconciliation.corrections
        )

    async def _assess_wide_view(self, context: TelescopeContext) -> WideAssessment:
        """Assess the full script from wide view."""
        prompt = f"""You are a story analyst performing a HOLISTIC assessment of a complete script.

{context.get_wide_prompt_context()}

EVALUATION RUBRIC:
{self._format_rubric()}

Analyze the ENTIRE script and provide:
1. OVERALL_COHERENCE (0.0-1.0): Does the story hold together as a whole?
2. NARRATIVE_FLOW (0.0-1.0): Does the story flow naturally from scene to scene?
3. CHARACTER_CONSISTENCY (0.0-1.0): Do characters behave consistently with their motivations?
4. WORLD_INTEGRATION (0.0-1.0): Are world details from world_config actively demonstrated?
5. VISUAL_CLARITY (0.0-1.0): Can each major moment be captured as a clear image?

Also identify:
- STRENGTHS: What works well (list 3-5 items)
- WEAKNESSES: What needs improvement (list 3-5 items)
- GLOBAL_ISSUES: Issues that affect multiple scenes
- RECOMMENDATIONS: Specific improvements

Format your response as:
OVERALL_COHERENCE: [score]
NARRATIVE_FLOW: [score]
CHARACTER_CONSISTENCY: [score]
WORLD_INTEGRATION: [score]
VISUAL_CLARITY: [score]
STRENGTHS:
- [strength 1]
- [strength 2]
...
WEAKNESSES:
- [weakness 1]
- [weakness 2]
...
GLOBAL_ISSUES:
- [issue 1]
...
RECOMMENDATIONS:
- [recommendation 1]
...
"""
        response = await self.llm_caller(prompt)
        return self._parse_wide_assessment(response)

    async def _assess_all_scenes(
        self,
        context: TelescopeContext,
        scenes: List[Dict[str, Any]]
    ) -> List[NarrowAssessment]:
        """Assess all scenes in parallel."""
        tasks = [
            self._assess_narrow_view(context, scene, i + 1)
            for i, scene in enumerate(scenes)
        ]
        return await asyncio.gather(*tasks)

    async def _assess_narrow_view(
        self,
        context: TelescopeContext,
        scene: Dict[str, Any],
        scene_number: int
    ) -> NarrowAssessment:
        """Assess a single scene from narrow view."""
        # Create scene context
        scene_ctx = context.universal_context.get_scene_context(
            scene_number=scene_number,
            scene_content=scene.get('content', str(scene)),
            scene_purpose=scene.get('purpose', ''),
            character_tags=scene.get('characters_present', scene.get('characters', [])),
            location_tag=scene.get('location_tag', ''),
            prop_tags=scene.get('prop_tags', []),
            entry_state=scene.get('entry_state', {}),
            exit_state=scene.get('exit_state', {})
        )

        prompt = f"""You are a scene analyst performing a DETAILED assessment of Scene {scene_number}.

{context.universal_context.for_scene_prompt(scene_ctx)}

WORLD CONTEXT (for reference):
Visual Style: {context.world_config.get('visual_style', 'live_action')}
Vibe: {context.world_config.get('vibe', '')}

Analyze this scene and answer:
1. SCENE_SCORE (0.0-1.0): Overall quality of this scene
2. VISUAL_FRAMEABLE (true/false): Can each moment be captured as a single, clear image?
3. CHARACTER_POSITIONS_VALID (true/false): Are character positions physically possible?
4. WORLD_DETAILS_PRESENT (true/false): Are world details from world_config demonstrated?
5. NOTATION_CORRECT (true/false): Are tags formatted correctly (e.g., [CHAR_MEI], [LOC_PALACE], [1.2.cA])?

Also list:
- ISSUES: Specific problems found
- SUGGESTIONS: Specific improvements

Format:
SCENE_SCORE: [score]
VISUAL_FRAMEABLE: [true/false]
CHARACTER_POSITIONS_VALID: [true/false]
WORLD_DETAILS_PRESENT: [true/false]
NOTATION_CORRECT: [true/false]
ISSUES:
- [issue 1]
...
SUGGESTIONS:
- [suggestion 1]
...
"""
        response = await self.llm_caller(prompt)
        return self._parse_narrow_assessment(response, scene_number)

    async def _reconcile_views(
        self,
        wide: WideAssessment,
        narrows: List[NarrowAssessment],
        context: TelescopeContext
    ) -> ReconciliationResult:
        """Reconcile wide and narrow assessments to find conflicts and corrections."""
        issues = []
        corrections = []
        conflicts = []

        # Collect all scene issues
        for narrow in narrows:
            for issue in narrow.issues:
                issues.append({
                    "scene": narrow.scene_number,
                    "issue": issue,
                    "type": "scene_specific"
                })

        # Add global issues from wide assessment
        for issue in wide.global_issues:
            issues.append({
                "scene": "global",
                "issue": issue,
                "type": "global"
            })

        # Check for conflicts between wide and narrow assessments
        avg_scene_score = sum(n.scene_score for n in narrows) / len(narrows) if narrows else 0
        if abs(wide.overall_coherence - avg_scene_score) > 0.3:
            conflicts.append(
                f"Wide coherence ({wide.overall_coherence:.2f}) differs significantly "
                f"from average scene score ({avg_scene_score:.2f})"
            )

        # Generate corrections from issues
        for issue in issues:
            corrections.append({
                "scene": issue["scene"],
                "issue": issue["issue"],
                "correction_type": "needs_review",
                "priority": "high" if issue["type"] == "global" else "medium"
            })

        # Calculate overall quality
        wide_score = (
            wide.overall_coherence * 0.3 +
            wide.narrative_flow * 0.2 +
            wide.character_consistency * 0.2 +
            wide.world_integration * 0.15 +
            wide.visual_clarity * 0.15
        )
        overall_quality = (wide_score + avg_scene_score) / 2

        return ReconciliationResult(
            issues=issues,
            corrections=corrections,
            conflicts=conflicts,
            overall_quality=overall_quality
        )

    def _format_rubric(self) -> str:
        """Format rubric for prompt."""
        lines = []
        for name, details in self.rubric.items():
            lines.append(f"- {name} (weight: {details['weight']}): {details['criteria']}")
        return "\n".join(lines)

    def _parse_wide_assessment(self, response: str) -> WideAssessment:
        """Parse wide assessment from LLM response."""
        def extract_score(pattern: str, default: float = 0.5) -> float:
            match = re.search(pattern + r':\s*([\d.]+)', response, re.IGNORECASE)
            if match:
                try:
                    return min(1.0, max(0.0, float(match.group(1))))
                except ValueError:
                    return default
            return default

        def extract_list(header: str) -> List[str]:
            pattern = rf'{header}:\s*\n((?:[-•]\s*.+\n?)+)'
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                items = re.findall(r'[-•]\s*(.+)', match.group(1))
                return [item.strip() for item in items if item.strip()]
            return []

        return WideAssessment(
            overall_coherence=extract_score('OVERALL_COHERENCE'),
            narrative_flow=extract_score('NARRATIVE_FLOW'),
            character_consistency=extract_score('CHARACTER_CONSISTENCY'),
            world_integration=extract_score('WORLD_INTEGRATION'),
            visual_clarity=extract_score('VISUAL_CLARITY'),
            strengths=extract_list('STRENGTHS'),
            weaknesses=extract_list('WEAKNESSES'),
            global_issues=extract_list('GLOBAL_ISSUES'),
            recommendations=extract_list('RECOMMENDATIONS')
        )

    def _parse_narrow_assessment(self, response: str, scene_number: int) -> NarrowAssessment:
        """Parse narrow assessment from LLM response."""
        def extract_score(pattern: str, default: float = 0.5) -> float:
            match = re.search(pattern + r':\s*([\d.]+)', response, re.IGNORECASE)
            if match:
                try:
                    return min(1.0, max(0.0, float(match.group(1))))
                except ValueError:
                    return default
            return default

        def extract_bool(pattern: str, default: bool = False) -> bool:
            match = re.search(pattern + r':\s*(true|false|yes|no)', response, re.IGNORECASE)
            if match:
                return match.group(1).lower() in ('true', 'yes')
            return default

        def extract_list(header: str) -> List[str]:
            pattern = rf'{header}:\s*\n((?:[-•]\s*.+\n?)+)'
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                items = re.findall(r'[-•]\s*(.+)', match.group(1))
                return [item.strip() for item in items if item.strip()]
            return []

        return NarrowAssessment(
            scene_number=scene_number,
            scene_score=extract_score('SCENE_SCORE'),
            visual_frameable=extract_bool('VISUAL_FRAMEABLE'),
            character_positions_valid=extract_bool('CHARACTER_POSITIONS_VALID'),
            world_details_present=extract_bool('WORLD_DETAILS_PRESENT'),
            notation_correct=extract_bool('NOTATION_CORRECT'),
            issues=extract_list('ISSUES'),
            suggestions=extract_list('SUGGESTIONS')
        )

