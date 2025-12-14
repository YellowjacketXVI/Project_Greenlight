"""
Greenlight Story Pipeline v3.0

Complete story generation pipeline with:
1. Context Compression - 90%+ token reduction
2. Steal List Mechanism - Preserve best ideas from losing concepts
3. Prose-First Generation - Story discovers beats naturally

Pipeline Phases:
1. BRAINSTORM: 5 philosophy agents generate competing concepts
2. SELECTION: 3 judges rank concepts, build steal list
3. OUTLINE: Scene-level goals/states (NO beat breakdown)
4. PROSE: 150-250 words per scene, pure prose
5. VALIDATION: Coherence check, steal list integration
6. BEAT_EXTRACTION: Post-hoc beat detection (Week 4)

Token Budget: ~37,000 tokens (vs ~256,000 in v2)
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

from greenlight.core.logging_config import get_logger
from greenlight.pipelines.base_pipeline import BasePipeline, PipelineResult, PipelineStatus, PipelineStep

# Context compression
from greenlight.context import ContextCompiler, ThreadTracker, AgentContextDelivery, SceneOutline

# Agents
from greenlight.agents.brainstorm_agents import BrainstormOrchestrator
from greenlight.agents.steal_list_judge import JudgePanel
from greenlight.agents.scene_outline_agent import SceneOutlineAgent, StoryOutline
from greenlight.agents.prose_agent import ProseOrchestrator, ProseResult

# Patterns
from greenlight.patterns.steal_list import StealListAggregator
from greenlight.patterns.assembly import Proposal
from greenlight.patterns.quality.coherence_validator import CoherenceValidator, CoherenceReport

# Beat extraction
from greenlight.agents.beat_extractor import BeatExtractor, BeatSheet

logger = get_logger("pipelines.story_v3")


@dataclass
class StoryPipelineV3Config:
    """Configuration for Story Pipeline v3."""
    num_scenes: int = 8
    num_brainstorm_agents: int = 5
    num_judges: int = 3
    steal_threshold: int = 2
    prose_word_min: int = 150
    prose_word_max: int = 250
    validate_steal_integration: bool = True


@dataclass
class StoryPipelineV3Output:
    """Output from Story Pipeline v3."""
    script: str
    scenes: List[ProseResult]
    winning_concept: Proposal
    steal_list: List[str]
    story_outline: StoryOutline
    token_usage: Dict[str, int]
    validation_results: Dict[str, Any]
    coherence_report: Optional[CoherenceReport] = None
    beat_sheet: Optional[BeatSheet] = None


class StoryPipelineV3(BasePipeline[Path, StoryPipelineV3Output]):
    """
    Story Pipeline v3.0 - Context Compression + Steal List + Prose-First
    
    Generates complete story scripts with 90%+ token reduction.
    """
    
    def __init__(
        self,
        llm_caller: Callable,
        config: StoryPipelineV3Config = None
    ):
        self.llm_caller = llm_caller
        self.config = config or StoryPipelineV3Config()
        
        # Initialize components
        self.brainstorm = BrainstormOrchestrator(llm_caller)
        self.judge_panel = JudgePanel(llm_caller)
        self.steal_aggregator = StealListAggregator(threshold=self.config.steal_threshold)
        self.outline_agent = SceneOutlineAgent(llm_caller, num_scenes=self.config.num_scenes)
        self.prose_orchestrator = ProseOrchestrator(llm_caller)
        self.beat_extractor = BeatExtractor(llm_caller)
        # CoherenceValidator is initialized per-run with steal_list

        super().__init__("StoryPipelineV3")

    def _define_steps(self):
        """Define pipeline steps."""
        self._steps = [
            PipelineStep("context_init", "Initialize context compression", timeout_seconds=30),
            PipelineStep("brainstorm", "Generate 5 competing concepts", timeout_seconds=120),
            PipelineStep("selection", "Judge concepts, build steal list", timeout_seconds=90),
            PipelineStep("outline", "Create scene-level outline", timeout_seconds=60),
            PipelineStep("prose", "Generate prose for all scenes", timeout_seconds=300),
            PipelineStep("coherence", "Validate story coherence", timeout_seconds=60),
            PipelineStep("beat_extraction", "Extract beats from prose", timeout_seconds=120),
        ]
    
    async def execute(self, project_path: Path) -> PipelineResult[StoryPipelineV3Output]:
        """
        Execute the complete story pipeline.
        
        Args:
            project_path: Path to project directory
            
        Returns:
            PipelineResult with StoryPipelineV3Output
        """
        start_time = datetime.now()
        self._status = PipelineStatus.RUNNING
        token_usage = {}
        
        try:
            # Step 1: Initialize context compression
            self._current_step = 0
            self._report_progress("Initializing context compression...")
            
            delivery = AgentContextDelivery.from_project(project_path)
            token_usage["context_init"] = delivery.compiler.estimate_tokens()["total"]
            
            # Step 2: Brainstorm
            self._current_step = 1
            self._report_progress("Generating 5 competing story concepts...")
            
            concepts = await self.brainstorm.generate_concepts(delivery)
            token_usage["brainstorm"] = len(concepts) * 200  # Estimate
            
            # Step 3: Selection
            self._current_step = 2
            self._report_progress("Judges evaluating concepts...")
            
            context_text = delivery.for_judge_agent([c.content for c in concepts])
            judge_result = await self.judge_panel.evaluate_concepts(concepts, context_text)
            
            winning_concept = judge_result["winner"]
            steal_list = judge_result["steal_list"]
            token_usage["selection"] = len(judge_result["votes"]) * 400  # Estimate
            
            logger.info(f"Winner: {winning_concept.agent_id}, Steal list: {len(steal_list)} items")

            # Step 4: Outline
            self._current_step = 3
            self._report_progress("Creating scene-level outline...")

            story_outline = await self.outline_agent.generate_outline(
                delivery=delivery,
                winning_concept=winning_concept.content,
                steal_list=steal_list
            )
            token_usage["outline"] = 500  # Estimate

            logger.info(f"Generated outline with {story_outline.total_scenes} scenes")

            # Step 5: Prose generation
            self._current_step = 4
            self._report_progress("Generating prose for all scenes...")

            prose_results = await self.prose_orchestrator.generate_all_scenes(
                delivery=delivery,
                outlines=story_outline.scenes
            )
            token_usage["prose"] = sum(r.word_count for r in prose_results) * 2  # Estimate

            # Compile script
            script = self.prose_orchestrator.compile_script(prose_results)

            # Step 6: Coherence Validation
            self._current_step = 5
            self._report_progress("Validating story coherence...")

            coherence_validator = CoherenceValidator(steal_list=steal_list)
            coherence_report = coherence_validator.validate(
                prose_results=prose_results,
                outlines=story_outline.scenes,
                tracker=delivery.tracker
            )
            token_usage["coherence"] = 100  # Estimate

            logger.info(f"Coherence score: {coherence_report.score:.2f}, Valid: {coherence_report.is_valid}")

            # Step 7: Beat Extraction
            self._current_step = 6
            self._report_progress("Extracting beats from prose...")

            beat_sheet = await self.beat_extractor.extract_beats(prose_results)
            token_usage["beat_extraction"] = beat_sheet.total_beats * 100  # Estimate

            # Save beat sheet
            beat_sheet_path = project_path / "scripts" / "beat_sheet.json"
            beat_sheet.save(beat_sheet_path)

            logger.info(f"Extracted {beat_sheet.total_beats} beats, saved to {beat_sheet_path}")

            # Legacy validation results for backward compatibility
            validation_results = self._validate_output(
                script=script,
                steal_list=steal_list,
                prose_results=prose_results
            )

            # Calculate total tokens
            token_usage["total"] = sum(token_usage.values())

            # Save script to project
            script_path = project_path / "scripts" / "script.md"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(script, encoding="utf-8")

            logger.info(f"Script saved to {script_path}")

            # Build output
            output = StoryPipelineV3Output(
                script=script,
                scenes=prose_results,
                winning_concept=winning_concept,
                steal_list=steal_list,
                story_outline=story_outline,
                token_usage=token_usage,
                validation_results=validation_results,
                coherence_report=coherence_report,
                beat_sheet=beat_sheet
            )

            duration = (datetime.now() - start_time).total_seconds()
            self._status = PipelineStatus.COMPLETED

            return PipelineResult(
                status=PipelineStatus.COMPLETED,
                output=output,
                duration_seconds=duration,
                metadata={
                    "total_words": sum(r.word_count for r in prose_results),
                    "total_scenes": len(prose_results),
                    "steal_list_size": len(steal_list),
                    "token_usage": token_usage
                }
            )

        except Exception as e:
            logger.error(f"Story Pipeline v3 failed: {e}")
            self._status = PipelineStatus.FAILED
            duration = (datetime.now() - start_time).total_seconds()

            return PipelineResult(
                status=PipelineStatus.FAILED,
                error=str(e),
                duration_seconds=duration
            )

    def _validate_output(
        self,
        script: str,
        steal_list: List[str],
        prose_results: List[ProseResult]
    ) -> Dict[str, Any]:
        """Validate the generated output."""
        results = {
            "word_count_valid": True,
            "steal_integration": {"valid": True, "missing": []},
            "scene_count_valid": len(prose_results) == self.config.num_scenes
        }

        # Check word counts
        for result in prose_results:
            if not (self.config.prose_word_min <= result.word_count <= self.config.prose_word_max):
                results["word_count_valid"] = False
                break

        # Check steal list integration
        if self.config.validate_steal_integration and steal_list:
            validation = self.steal_aggregator.validate_integration(
                self.steal_aggregator.aggregate([]),  # Empty for structure
                script
            )
            # Manual check since we have the steal list directly
            script_lower = script.lower()
            missing = []
            for item in steal_list:
                key_words = [w for w in item.lower().split() if len(w) > 3]
                if not any(w in script_lower for w in key_words):
                    missing.append(item)

            results["steal_integration"] = {
                "valid": len(missing) == 0,
                "missing": missing,
                "integration_score": 1.0 - (len(missing) / len(steal_list)) if steal_list else 1.0
            }

        return results

    def _report_progress(self, message: str):
        """Report progress to callback if set."""
        if self._progress_callback:
            progress = (self._current_step + 1) / len(self._steps)
            self._progress_callback(progress, message)
        logger.info(f"[{self._current_step + 1}/{len(self._steps)}] {message}")
