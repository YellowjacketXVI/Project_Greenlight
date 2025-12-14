"""
Quality Orchestrator - Script Finalization Quality Assurance

SINGLE-PASS VALIDATION ARCHITECTURE:
Orchestrates all quality patterns in sequence to ANALYZE the script.
Issues are logged for awareness but NOT corrected in-place.
The Full Context Assembly Agent (in story_pipeline.py) handles final consolidation.

Phases:
1. HOLISTIC REVIEW - TelescopeAgent + InquisitorPanel (analyze, log concerns)
2. CONTINUITY ANALYSIS - ContinuityWeaver (detect issues, log concerns)
3. TAG VALIDATION - ConstellationAgent (validate tags, log concerns)
4. NOTATION VALIDATION - AnchorAgent (validate notation, log concerns)

NOTE: MirrorAgent is disabled by default. All corrections are deferred to
the Full Context Assembly Agent which has full context awareness.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
import asyncio
import json

from greenlight.core.logging_config import get_logger
from .universal_context import UniversalContext, SceneContext
from .telescope_agent import TelescopeAgent, TelescopeAnalysis
from .inquisitor_panel import InquisitorPanel, InquisitorReport
from .continuity_weaver import ContinuityWeaver, ContinuityReport
from .constellation_agent import ConstellationAgent, ConstellationMap
from .anchor_agent import AnchorAgent, NotationReport
from .mirror_agent import MirrorAgent, MirrorResult

logger = get_logger("patterns.quality.orchestrator")


@dataclass
class QualityPhaseResult:
    """Result from a single quality phase."""
    phase_name: str
    passed: bool
    score: float
    issues_found: int
    fixes_applied: int
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    """Complete quality assurance report."""
    original_script: str
    final_script: str
    phases: List[QualityPhaseResult]
    overall_score: float
    passed: bool
    telescope_analysis: Optional[TelescopeAnalysis] = None
    inquisitor_synthesis: Optional[InquisitorReport] = None
    continuity_report: Optional[ContinuityReport] = None
    constellation_map: Optional[ConstellationMap] = None
    notation_report: Optional[NotationReport] = None
    mirror_result: Optional[MirrorResult] = None


@dataclass
class QualityConfig:
    """Configuration for quality orchestration."""
    run_telescope: bool = True
    run_inquisitor: bool = True
    run_continuity: bool = True
    run_constellation: bool = True
    run_anchor: bool = True
    run_mirror: bool = False  # Optional final refinement
    
    # Thresholds
    min_telescope_score: float = 0.7
    min_continuity_score: float = 0.8
    min_overall_score: float = 0.75
    
    # Mirror settings
    mirror_max_iterations: int = 3
    mirror_satisfaction_threshold: float = 0.85


class QualityOrchestrator:
    """
    Orchestrates all quality patterns for script finalization.

    SINGLE-PASS VALIDATION:
    - Runs quality phases in sequence, collecting analysis results
    - Logs concerns and issues for awareness
    - Does NOT apply corrections in-place (deferred to Full Context Assembly Agent)
    - Returns analysis report for downstream processing
    """
    
    def __init__(
        self,
        llm_caller: Callable,
        config: Optional[QualityConfig] = None
    ):
        self.llm_caller = llm_caller
        self.config = config or QualityConfig()
        
        # Initialize agents
        self.telescope = TelescopeAgent(llm_caller)
        self.inquisitor = InquisitorPanel(llm_caller)
        self.continuity = ContinuityWeaver(llm_caller)
        self.constellation = ConstellationAgent(llm_caller)
        self.anchor = AnchorAgent(llm_caller)
        self.mirror = MirrorAgent(
            llm_caller,
            max_iterations=self.config.mirror_max_iterations,
            satisfaction_threshold=self.config.mirror_satisfaction_threshold
        )
    
    async def run_quality_assurance(
        self,
        script: str,
        scenes: List[Dict[str, Any]],
        world_config: Dict[str, Any],
        pitch: str
    ) -> QualityReport:
        """
        Run complete quality assurance on the script.

        SINGLE-PASS VALIDATION:
        - Analyzes script through all quality phases
        - Logs concerns and issues for awareness
        - Does NOT apply corrections (deferred to Full Context Assembly Agent)
        - Returns analysis report with all findings

        Args:
            script: The full script text
            scenes: List of scene dictionaries
            world_config: World configuration
            pitch: Story pitch

        Returns:
            QualityReport with all phase results (analysis only, no corrections)
        """
        logger.info("QualityOrchestrator: Starting SINGLE-PASS quality analysis...")

        # Create universal context
        universal_context = UniversalContext(
            pitch=pitch,
            world_config=world_config,
            full_script=script
        )

        phases = []
        # SINGLE-PASS: Script is not modified, only analyzed
        current_script = script

        # Phase 1: Holistic Review (Telescope + Inquisitor) - ANALYSIS ONLY
        telescope_analysis = None
        inquisitor_synthesis = None
        
        if self.config.run_telescope:
            logger.info("Phase 1a: Running TelescopeAgent...")
            telescope_analysis = await self.telescope.analyze_script(
                universal_context, scenes
            )
            phases.append(QualityPhaseResult(
                phase_name="Telescope Analysis",
                passed=telescope_analysis.reconciliation.overall_score >= self.config.min_telescope_score,
                score=telescope_analysis.reconciliation.overall_score,
                issues_found=len(telescope_analysis.reconciliation.discrepancies),
                fixes_applied=0,
                details={"discrepancies": telescope_analysis.reconciliation.discrepancies}
            ))
        
        if self.config.run_inquisitor:
            logger.info("Phase 1b: Running InquisitorPanel...")
            # Run on each scene
            all_syntheses = []
            for scene in scenes:
                scene_num = scene.get('scene_number', 1)
                scene_content = scene.get('content', str(scene))
                location = scene.get('location', {})
                
                synthesis = await self.inquisitor.interrogate_scene(
                    scene_content=scene_content,
                    scene_number=scene_num,
                    world_config=world_config,
                    pitch=pitch,
                    location=location
                )
                all_syntheses.append(synthesis)
            
            # Aggregate inquisitor results
            if all_syntheses:
                avg_score = sum(s.overall_score for s in all_syntheses) / len(all_syntheses)
                total_issues = sum(len(s.critical_issues) for s in all_syntheses)
                inquisitor_synthesis = all_syntheses[0]  # Store first for reference
                
                phases.append(QualityPhaseResult(
                    phase_name="Inquisitor Panel",
                    passed=avg_score >= 0.7,
                    score=avg_score,
                    issues_found=total_issues,
                    fixes_applied=0,
                    details={"scene_scores": [s.overall_score for s in all_syntheses]}
                ))

        # Phase 2: Continuity Analysis (SINGLE-PASS: log only, no patches applied)
        continuity_report = None
        if self.config.run_continuity:
            logger.info("Phase 2: Running ContinuityWeaver (analysis only)...")
            continuity_report = await self.continuity.weave_threads(
                scenes=scenes,
                world_config=world_config,
                pitch=pitch
            )

            # SINGLE-PASS: Log issues but do NOT apply patches
            # Patches are available in continuity_report for Full Context Assembly Agent
            if continuity_report.patches:
                logger.info(f"  Continuity: {len(continuity_report.patches)} patches identified (not applied)")

            phases.append(QualityPhaseResult(
                phase_name="Continuity Weaver",
                passed=continuity_report.continuity_score >= self.config.min_continuity_score,
                score=continuity_report.continuity_score,
                issues_found=len(continuity_report.issues),
                fixes_applied=0,  # SINGLE-PASS: No fixes applied
                details={
                    "thread_count": len(continuity_report.threads),
                    "patches_identified": len(continuity_report.patches) if continuity_report.patches else 0
                }
            ))

        # Phase 3: Tag Validation
        constellation_map = None
        if self.config.run_constellation:
            logger.info("Phase 3: Running ConstellationAgent...")
            constellation_map = await self.constellation.map_constellation(
                script=current_script,
                world_config=world_config,
                pitch=pitch
            )

            phases.append(QualityPhaseResult(
                phase_name="Constellation Agent",
                passed=constellation_map.is_valid,
                score=1.0 if constellation_map.is_valid else 0.5,
                issues_found=len(constellation_map.validation_issues),
                fixes_applied=0,
                details={
                    "orphan_tags": constellation_map.orphan_tags,
                    "phantom_tags": constellation_map.phantom_tags
                }
            ))

        # Phase 4: Notation Validation (SINGLE-PASS: log only, no fixes applied)
        notation_report = None
        if self.config.run_anchor:
            logger.info("Phase 4: Running AnchorAgent (validation only)...")
            notation_report = await self.anchor.enforce_notation(
                script=current_script,
                world_config=world_config
            )

            # SINGLE-PASS: Log issues but do NOT apply fixes
            # Fixes are available in notation_report for Full Context Assembly Agent
            if notation_report.issues_found:
                logger.info(f"  Notation: {len(notation_report.issues_found)} issues identified (not applied)")

            phases.append(QualityPhaseResult(
                phase_name="Anchor Agent",
                passed=notation_report.notation_valid,
                score=1.0 if notation_report.notation_valid else 0.7,
                issues_found=len(notation_report.issues_found),
                fixes_applied=0,  # SINGLE-PASS: No fixes applied
                details={
                    "scene_count": notation_report.scene_count,
                    "camera_count": notation_report.camera_count,
                    "fixes_identified": len(notation_report.fixes_applied) if notation_report.fixes_applied else 0
                }
            ))

        # Phase 5: Final Refinement (DISABLED in SINGLE-PASS architecture)
        # MirrorAgent is disabled - all corrections deferred to Full Context Assembly Agent
        mirror_result = None
        if self.config.run_mirror:
            # SINGLE-PASS: Log that mirror is skipped, do not run
            logger.info("Phase 5: MirrorAgent SKIPPED (single-pass architecture)")
            logger.info("  Corrections deferred to Full Context Assembly Agent")

            # Identify scenes that would need refinement (for logging only)
            scenes_to_refine = self._identify_scenes_needing_refinement(
                phases, scenes, telescope_analysis
            )

            if scenes_to_refine:
                logger.info(f"  {len(scenes_to_refine)} scenes identified for refinement (not applied)")
                phases.append(QualityPhaseResult(
                    phase_name="Mirror Agent (Skipped)",
                    passed=True,  # Skipped phases pass
                    score=1.0,
                    issues_found=len(scenes_to_refine),
                    fixes_applied=0,  # SINGLE-PASS: No fixes applied
                    details={"scenes_needing_refinement": [s.get('scene_number') for s in scenes_to_refine]}
                ))

        # Calculate overall score
        if phases:
            overall_score = sum(p.score for p in phases) / len(phases)
        else:
            overall_score = 1.0

        passed = overall_score >= self.config.min_overall_score

        logger.info(f"QualityOrchestrator: Complete. Score: {overall_score:.2f}, Passed: {passed}")

        return QualityReport(
            original_script=script,
            final_script=current_script,
            phases=phases,
            overall_score=overall_score,
            passed=passed,
            telescope_analysis=telescope_analysis,
            inquisitor_synthesis=inquisitor_synthesis,
            continuity_report=continuity_report,
            constellation_map=constellation_map,
            notation_report=notation_report,
            mirror_result=mirror_result
        )

    def _apply_continuity_patches(
        self,
        script: str,
        patches: List[Any]
    ) -> str:
        """Apply continuity patches to the script."""
        # Sort patches by target scene (descending) to avoid offset issues
        sorted_patches = sorted(patches, key=lambda p: p.target_scene, reverse=True)

        for patch in sorted_patches:
            # Find the target scene in the script
            scene_pattern = f"## Scene {patch.target_scene}:"
            scene_idx = script.find(scene_pattern)

            if scene_idx == -1:
                continue

            # Find insertion point
            if patch.insertion_point == 'beginning':
                # Insert after scene header
                insert_idx = script.find('\n', scene_idx) + 1
            elif patch.insertion_point == 'end':
                # Find next scene or end of script
                next_scene = script.find(f"## Scene {patch.target_scene + 1}:", scene_idx)
                insert_idx = next_scene if next_scene != -1 else len(script)
            else:
                # Default to beginning
                insert_idx = script.find('\n', scene_idx) + 1

            # Insert patch content
            script = script[:insert_idx] + f"\n{patch.patch_content}\n" + script[insert_idx:]

        return script

    def _identify_scenes_needing_refinement(
        self,
        phases: List[QualityPhaseResult],
        scenes: List[Dict[str, Any]],
        telescope_analysis: Optional[TelescopeAnalysis]
    ) -> List[Dict[str, Any]]:
        """Identify scenes that need refinement based on phase results."""
        scenes_to_refine = []

        if telescope_analysis:
            # Find scenes with low narrow scores
            for narrow in telescope_analysis.narrow_assessments:
                if narrow.overall_score < 0.7:
                    # Find matching scene
                    for scene in scenes:
                        if scene.get('scene_number') == narrow.scene_number:
                            scenes_to_refine.append(scene)
                            break

        return scenes_to_refine[:3]  # Limit to 3 scenes for efficiency

    def _replace_scene_content(
        self,
        script: str,
        scene_number: int,
        new_content: str
    ) -> str:
        """Replace a scene's content in the script."""
        import re

        # Find scene boundaries
        scene_start = f"## Scene {scene_number}:"
        next_scene = f"## Scene {scene_number + 1}:"

        start_idx = script.find(scene_start)
        if start_idx == -1:
            return script

        end_idx = script.find(next_scene, start_idx)
        if end_idx == -1:
            end_idx = len(script)

        # Replace content
        return script[:start_idx] + f"{scene_start}\n{new_content}\n\n" + script[end_idx:]

    def generate_quality_report(self, report: QualityReport) -> str:
        """Generate a human-readable quality report."""
        lines = [
            "=" * 70,
            "SCRIPT QUALITY ASSURANCE REPORT",
            "=" * 70,
            "",
            f"Overall Score: {report.overall_score:.2f}",
            f"Passed: {'✓ YES' if report.passed else '✗ NO'}",
            "",
            "PHASE RESULTS:",
            "-" * 40,
        ]

        for phase in report.phases:
            status = "✓" if phase.passed else "✗"
            lines.append(f"  {status} {phase.phase_name}")
            lines.append(f"      Score: {phase.score:.2f}")
            lines.append(f"      Issues: {phase.issues_found}, Fixes: {phase.fixes_applied}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)
