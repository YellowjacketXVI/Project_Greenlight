"""
Iteration Validator - Max 100 Iterations for Input/Output Validation

Controls and refines self-healing and OmniMind operations through
iterative validation with a maximum of 100 cycles.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable
from enum import Enum
from datetime import datetime
import json
from pathlib import Path


class ValidationStatus(Enum):
    """Status of validation."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    REFINED = "refined"
    MAX_ITERATIONS = "max_iterations"


class RefinementAction(Enum):
    """Actions for refinement."""
    RETRY = "retry"
    MODIFY_INPUT = "modify_input"
    ADJUST_PARAMS = "adjust_params"
    ESCALATE = "escalate"
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass
class ValidationResult:
    """Result of a validation iteration."""
    iteration: int
    status: ValidationStatus
    input_data: Any
    output_data: Any
    score: float = 0.0
    issues: List[str] = field(default_factory=list)
    refinements: List[str] = field(default_factory=list)
    action: RefinementAction = RefinementAction.ACCEPT
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "status": self.status.value,
            "input_data": str(self.input_data)[:500],
            "output_data": str(self.output_data)[:500],
            "score": self.score,
            "issues": self.issues,
            "refinements": self.refinements,
            "action": self.action.value,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class IterationConfig:
    """Configuration for iteration validation."""
    max_iterations: int = 100
    pass_threshold: float = 0.8
    fail_threshold: float = 0.3
    auto_refine: bool = True
    log_all_iterations: bool = True
    stop_on_pass: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "pass_threshold": self.pass_threshold,
            "fail_threshold": self.fail_threshold,
            "auto_refine": self.auto_refine,
            "log_all_iterations": self.log_all_iterations,
            "stop_on_pass": self.stop_on_pass
        }


class IterationValidator:
    """
    Iteration Validator with max 100 cycles.
    
    Controls input/output validation and refinement for:
    - Self-healing operations
    - OmniMind task execution
    - LLM handshake validation
    - Vector translation quality
    
    Example:
        validator = IterationValidator(config)
        
        async def process(input_data):
            return await llm.generate(input_data)
        
        def validate(output):
            return len(output) > 10, 0.9 if len(output) > 100 else 0.5
        
        result = await validator.run(
            initial_input="Generate a story",
            process_fn=process,
            validate_fn=validate
        )
    """
    
    MAX_ALLOWED_ITERATIONS = 100  # Hard limit
    
    def __init__(
        self,
        config: Optional[IterationConfig] = None,
        log_dir: Optional[Path] = None
    ):
        """Initialize the iteration validator."""
        self.config = config or IterationConfig()
        self.log_dir = log_dir
        
        # Enforce max 100 iterations
        if self.config.max_iterations > self.MAX_ALLOWED_ITERATIONS:
            self.config.max_iterations = self.MAX_ALLOWED_ITERATIONS
        
        self._iteration_history: List[ValidationResult] = []
        self._current_iteration = 0
    
    def reset(self) -> None:
        """Reset the validator for a new run."""
        self._iteration_history.clear()
        self._current_iteration = 0
    
    def _create_result(
        self,
        input_data: Any,
        output_data: Any,
        passed: bool,
        score: float,
        issues: List[str] = None
    ) -> ValidationResult:
        """Create a validation result."""
        status = ValidationStatus.PASSED if passed else ValidationStatus.FAILED
        action = RefinementAction.ACCEPT if passed else RefinementAction.RETRY
        
        if self._current_iteration >= self.config.max_iterations:
            status = ValidationStatus.MAX_ITERATIONS
            action = RefinementAction.ESCALATE
        
        return ValidationResult(
            iteration=self._current_iteration,
            status=status,
            input_data=input_data,
            output_data=output_data,
            score=score,
            issues=issues or [],
            action=action
        )

    async def run(
        self,
        initial_input: Any,
        process_fn: Callable[[Any], Awaitable[Any]],
        validate_fn: Callable[[Any], tuple[bool, float]],
        refine_fn: Optional[Callable[[Any, Any, List[str]], Any]] = None
    ) -> ValidationResult:
        """
        Run iterative validation up to max iterations.

        Args:
            initial_input: Starting input data
            process_fn: Async function to process input → output
            validate_fn: Function returning (passed, score)
            refine_fn: Optional function to refine input based on output

        Returns:
            Final ValidationResult
        """
        self.reset()
        current_input = initial_input
        final_result = None

        while self._current_iteration < self.config.max_iterations:
            self._current_iteration += 1

            # Process
            try:
                output = await process_fn(current_input)
            except Exception as e:
                result = self._create_result(
                    current_input, None, False, 0.0,
                    [f"Process error: {str(e)}"]
                )
                self._iteration_history.append(result)
                if not self.config.auto_refine:
                    return result
                continue

            # Validate
            passed, score = validate_fn(output)
            issues = [] if passed else ["Validation threshold not met"]

            result = self._create_result(current_input, output, passed, score, issues)
            self._iteration_history.append(result)
            final_result = result

            # Check if we should stop
            if passed and self.config.stop_on_pass:
                result.status = ValidationStatus.PASSED
                result.action = RefinementAction.ACCEPT
                return result

            # Refine if auto-refine enabled
            if self.config.auto_refine and refine_fn and not passed:
                current_input = refine_fn(current_input, output, issues)
                result.status = ValidationStatus.REFINED
                result.action = RefinementAction.MODIFY_INPUT

        # Max iterations reached
        if final_result:
            final_result.status = ValidationStatus.MAX_ITERATIONS
            final_result.action = RefinementAction.ESCALATE
            return final_result

        return self._create_result(initial_input, None, False, 0.0, ["No iterations completed"])

    def run_sync(
        self,
        initial_input: Any,
        process_fn: Callable[[Any], Any],
        validate_fn: Callable[[Any], tuple[bool, float]],
        refine_fn: Optional[Callable[[Any, Any, List[str]], Any]] = None
    ) -> ValidationResult:
        """
        Run iterative validation synchronously.

        Same as run() but for synchronous process functions.
        """
        self.reset()
        current_input = initial_input
        final_result = None

        while self._current_iteration < self.config.max_iterations:
            self._current_iteration += 1

            try:
                output = process_fn(current_input)
            except Exception as e:
                result = self._create_result(
                    current_input, None, False, 0.0,
                    [f"Process error: {str(e)}"]
                )
                self._iteration_history.append(result)
                if not self.config.auto_refine:
                    return result
                continue

            passed, score = validate_fn(output)
            issues = [] if passed else ["Validation threshold not met"]

            result = self._create_result(current_input, output, passed, score, issues)
            self._iteration_history.append(result)
            final_result = result

            if passed and self.config.stop_on_pass:
                result.status = ValidationStatus.PASSED
                result.action = RefinementAction.ACCEPT
                return result

            if self.config.auto_refine and refine_fn and not passed:
                current_input = refine_fn(current_input, output, issues)
                result.status = ValidationStatus.REFINED
                result.action = RefinementAction.MODIFY_INPUT

        if final_result:
            final_result.status = ValidationStatus.MAX_ITERATIONS
            final_result.action = RefinementAction.ESCALATE
            return final_result

        return self._create_result(initial_input, None, False, 0.0, ["No iterations completed"])

    def get_history(self) -> List[Dict[str, Any]]:
        """Get iteration history."""
        return [r.to_dict() for r in self._iteration_history]

    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        if not self._iteration_history:
            return {"total": 0, "passed": 0, "failed": 0, "avg_score": 0.0}

        passed = sum(1 for r in self._iteration_history if r.status == ValidationStatus.PASSED)
        scores = [r.score for r in self._iteration_history]

        return {
            "total": len(self._iteration_history),
            "passed": passed,
            "failed": len(self._iteration_history) - passed,
            "avg_score": sum(scores) / len(scores),
            "max_score": max(scores),
            "min_score": min(scores),
            "iterations_used": self._current_iteration
        }

