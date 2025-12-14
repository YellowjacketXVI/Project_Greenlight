"""
Coherence Validator - Story Pipeline v3.0

Validates story coherence after prose generation:
1. Character state consistency (entry/exit states match)
2. Thread resolution (all threads resolved or intentionally open)
3. Steal list integration (all required elements appear)
4. Emotional arc progression (tension builds appropriately)
5. Scene connectivity (transitions make sense)

Works with ThreadTracker for lightweight validation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
import re

from greenlight.core.logging_config import get_logger
from greenlight.context.thread_tracker import ThreadTracker
from greenlight.agents.prose_agent import ProseResult
from greenlight.context.agent_context_delivery import SceneOutline

logger = get_logger("patterns.quality.coherence_validator")


@dataclass
class CoherenceIssue:
    """A coherence issue found in the story."""
    issue_type: str  # state_mismatch, unresolved_thread, missing_steal, arc_break, transition_gap
    severity: str  # critical, warning, info
    scene_number: int
    description: str
    suggested_fix: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.issue_type,
            "severity": self.severity,
            "scene": self.scene_number,
            "description": self.description,
            "fix": self.suggested_fix
        }


@dataclass
class CoherenceReport:
    """Report from coherence validation."""
    is_valid: bool
    score: float  # 0.0 to 1.0
    issues: List[CoherenceIssue] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def critical_issues(self) -> List[CoherenceIssue]:
        return [i for i in self.issues if i.severity == "critical"]
    
    @property
    def warnings(self) -> List[CoherenceIssue]:
        return [i for i in self.issues if i.severity == "warning"]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "issues": [i.to_dict() for i in self.issues],
            "stats": self.stats
        }


class CoherenceValidator:
    """
    Validates story coherence for Story Pipeline v3.0.
    
    Lightweight validation using ThreadTracker and prose results.
    """
    
    def __init__(self, steal_list: List[str] = None):
        self.steal_list = steal_list or []
    
    def validate(
        self,
        prose_results: List[ProseResult],
        outlines: List[SceneOutline],
        tracker: ThreadTracker
    ) -> CoherenceReport:
        """
        Validate story coherence.
        
        Args:
            prose_results: List of ProseResult from prose generation
            outlines: List of SceneOutline used for generation
            tracker: ThreadTracker with continuity state
            
        Returns:
            CoherenceReport with issues and score
        """
        issues = []
        
        # 1. Validate state consistency
        state_issues = self._validate_states(prose_results, outlines)
        issues.extend(state_issues)
        
        # 2. Validate thread resolution
        thread_issues = self._validate_threads(tracker)
        issues.extend(thread_issues)
        
        # 3. Validate steal list integration
        steal_issues = self._validate_steal_integration(prose_results)
        issues.extend(steal_issues)
        
        # 4. Validate emotional arc
        arc_issues = self._validate_arc(outlines)
        issues.extend(arc_issues)
        
        # 5. Validate transitions
        transition_issues = self._validate_transitions(prose_results)
        issues.extend(transition_issues)
        
        # Calculate score
        critical_count = len([i for i in issues if i.severity == "critical"])
        warning_count = len([i for i in issues if i.severity == "warning"])
        
        # Score: start at 1.0, subtract for issues
        score = 1.0 - (critical_count * 0.15) - (warning_count * 0.05)
        score = max(0.0, min(1.0, score))
        
        is_valid = critical_count == 0 and score >= 0.7
        
        return CoherenceReport(
            is_valid=is_valid,
            score=score,
            issues=issues,
            stats={
                "total_scenes": len(prose_results),
                "total_words": sum(r.word_count for r in prose_results),
                "unresolved_threads": tracker.get_unresolved_count(),
                "steal_list_size": len(self.steal_list),
                "critical_issues": critical_count,
                "warnings": warning_count
            }
        )
    
    def _validate_states(
        self,
        prose_results: List[ProseResult],
        outlines: List[SceneOutline]
    ) -> List[CoherenceIssue]:
        """Validate character state consistency between scenes."""
        issues = []
        
        for i in range(1, len(outlines)):
            prev_outline = outlines[i - 1]
            curr_outline = outlines[i]
            
            # Check if exit states of previous match entry states of current
            for char, exit_state in prev_outline.exit_states.items():
                if char in curr_outline.entry_states:
                    entry_state = curr_outline.entry_states[char]
                    if exit_state.lower() != entry_state.lower():
                        issues.append(CoherenceIssue(
                            issue_type="state_mismatch",
                            severity="warning",
                            scene_number=curr_outline.scene_number,
                            description=f"{char} exits scene {i} as '{exit_state}' but enters scene {i+1} as '{entry_state}'",
                            suggested_fix=f"Add transition showing {char} changing from {exit_state} to {entry_state}"
                        ))
        
        return issues

    def _validate_threads(self, tracker: ThreadTracker) -> List[CoherenceIssue]:
        """Validate thread resolution."""
        issues = []

        # Check for unresolved threads
        for thread in tracker.active_threads:
            issues.append(CoherenceIssue(
                issue_type="unresolved_thread",
                severity="warning",
                scene_number=0,  # Story-level issue
                description=f"Thread '{thread}' was never resolved",
                suggested_fix=f"Add resolution for '{thread}' or mark as intentionally open"
            ))

        # Check for setups without payoffs
        for setup in tracker.setups_awaiting_payoff:
            issues.append(CoherenceIssue(
                issue_type="unresolved_thread",
                severity="info",
                scene_number=0,
                description=f"Setup '{setup}' has no payoff",
                suggested_fix=f"Add payoff for '{setup}' or remove the setup"
            ))

        return issues

    def _validate_steal_integration(
        self,
        prose_results: List[ProseResult]
    ) -> List[CoherenceIssue]:
        """Validate steal list elements appear in prose."""
        issues = []

        if not self.steal_list:
            return issues

        # Combine all prose
        full_prose = " ".join(r.prose.lower() for r in prose_results)

        for steal_item in self.steal_list:
            # Check if key words from steal item appear
            key_words = [w for w in steal_item.lower().split() if len(w) > 3]
            found = any(w in full_prose for w in key_words)

            if not found:
                issues.append(CoherenceIssue(
                    issue_type="missing_steal",
                    severity="warning",
                    scene_number=0,
                    description=f"Steal list item '{steal_item}' not found in prose",
                    suggested_fix=f"Incorporate '{steal_item}' into an appropriate scene"
                ))

        return issues

    def _validate_arc(self, outlines: List[SceneOutline]) -> List[CoherenceIssue]:
        """Validate emotional arc progression."""
        issues = []

        if len(outlines) < 3:
            return issues

        tensions = [o.tension for o in outlines]

        # Check for flat arc (no tension variation)
        if len(set(tensions)) == 1:
            issues.append(CoherenceIssue(
                issue_type="arc_break",
                severity="warning",
                scene_number=0,
                description="Tension is flat across all scenes - no arc progression",
                suggested_fix="Vary tension levels to create rising/falling action"
            ))

        # Check for climax (should have high tension near end)
        max_tension = max(tensions)
        max_index = tensions.index(max_tension)

        # Climax should be in last third of story
        if max_index < len(tensions) * 0.5:
            issues.append(CoherenceIssue(
                issue_type="arc_break",
                severity="info",
                scene_number=max_index + 1,
                description=f"Peak tension at scene {max_index + 1} is too early",
                suggested_fix="Move climax closer to the end of the story"
            ))

        return issues

    def _validate_transitions(
        self,
        prose_results: List[ProseResult]
    ) -> List[CoherenceIssue]:
        """Validate scene transitions."""
        issues = []

        for i in range(1, len(prose_results)):
            prev = prose_results[i - 1]
            curr = prose_results[i]

            # Check for abrupt transitions (very short scenes)
            if prev.word_count < 100:
                issues.append(CoherenceIssue(
                    issue_type="transition_gap",
                    severity="info",
                    scene_number=prev.scene_number,
                    description=f"Scene {prev.scene_number} is very short ({prev.word_count} words)",
                    suggested_fix="Expand scene or merge with adjacent scene"
                ))

        return issues
