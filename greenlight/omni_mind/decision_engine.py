"""
Greenlight Decision Engine

Autonomous decision making for the Omni Mind assistant.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.decision")


class DecisionType(Enum):
    """Types of decisions."""
    REGENERATION = "regeneration"
    PROPAGATION = "propagation"
    SUGGESTION = "suggestion"
    VALIDATION = "validation"
    OPTIMIZATION = "optimization"


class DecisionConfidence(Enum):
    """Confidence levels for decisions."""
    HIGH = "high"       # > 0.8
    MEDIUM = "medium"   # 0.5 - 0.8
    LOW = "low"         # < 0.5


@dataclass
class Decision:
    """A decision made by the engine."""
    id: str
    decision_type: DecisionType
    action: str
    confidence: float
    reasoning: str
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    executed: bool = False
    result: Optional[str] = None
    
    @property
    def confidence_level(self) -> DecisionConfidence:
        if self.confidence >= 0.8:
            return DecisionConfidence.HIGH
        elif self.confidence >= 0.5:
            return DecisionConfidence.MEDIUM
        return DecisionConfidence.LOW


@dataclass
class DecisionRule:
    """A rule for making decisions."""
    name: str
    condition: Callable[[Dict], bool]
    action: str
    decision_type: DecisionType
    base_confidence: float = 0.7
    priority: int = 0


class DecisionEngine:
    """
    Makes autonomous decisions for the assistant.
    
    Features:
    - Rule-based decision making
    - Confidence scoring
    - Decision history
    - User confirmation for low-confidence decisions
    """
    
    def __init__(
        self,
        auto_execute_threshold: float = 0.8,
        require_confirmation_threshold: float = 0.5
    ):
        """
        Initialize the decision engine.
        
        Args:
            auto_execute_threshold: Confidence for auto-execution
            require_confirmation_threshold: Confidence requiring confirmation
        """
        self.auto_execute_threshold = auto_execute_threshold
        self.require_confirmation_threshold = require_confirmation_threshold
        
        self._rules: List[DecisionRule] = []
        self._history: List[Decision] = []
        self._next_id = 0
        
        self._initialize_default_rules()
    
    def _initialize_default_rules(self) -> None:
        """Initialize default decision rules."""
        # Regeneration rules
        self.add_rule(DecisionRule(
            name="regenerate_on_tag_change",
            condition=lambda ctx: ctx.get('tag_changed', False),
            action="regenerate_dependent_content",
            decision_type=DecisionType.REGENERATION,
            base_confidence=0.9,
            priority=10
        ))
        
        self.add_rule(DecisionRule(
            name="regenerate_on_character_edit",
            condition=lambda ctx: ctx.get('character_edited', False),
            action="regenerate_character_appearances",
            decision_type=DecisionType.REGENERATION,
            base_confidence=0.85,
            priority=9
        ))
        
        # Validation rules
        self.add_rule(DecisionRule(
            name="validate_new_content",
            condition=lambda ctx: ctx.get('new_content', False),
            action="run_quality_validation",
            decision_type=DecisionType.VALIDATION,
            base_confidence=0.95,
            priority=8
        ))
        
        # Suggestion rules
        self.add_rule(DecisionRule(
            name="suggest_missing_tags",
            condition=lambda ctx: len(ctx.get('unregistered_tags', [])) > 0,
            action="suggest_tag_registration",
            decision_type=DecisionType.SUGGESTION,
            base_confidence=0.7,
            priority=5
        ))
    
    def add_rule(self, rule: DecisionRule) -> None:
        """Add a decision rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
    
    def evaluate(self, context: Dict[str, Any]) -> List[Decision]:
        """
        Evaluate context and make decisions.
        
        Args:
            context: Current context information
            
        Returns:
            List of decisions
        """
        decisions = []
        
        for rule in self._rules:
            try:
                if rule.condition(context):
                    decision = self._create_decision(rule, context)
                    decisions.append(decision)
                    self._history.append(decision)
            except Exception as e:
                logger.error(f"Rule evaluation failed: {rule.name} - {e}")
        
        return decisions
    
    def _create_decision(
        self,
        rule: DecisionRule,
        context: Dict[str, Any]
    ) -> Decision:
        """Create a decision from a rule."""
        # Adjust confidence based on context
        confidence = rule.base_confidence
        
        # Reduce confidence if similar decision was recently rejected
        recent_rejections = self._count_recent_rejections(rule.decision_type)
        if recent_rejections > 0:
            confidence *= (0.9 ** recent_rejections)
        
        decision = Decision(
            id=f"dec_{self._next_id:06d}",
            decision_type=rule.decision_type,
            action=rule.action,
            confidence=confidence,
            reasoning=f"Rule '{rule.name}' triggered",
            context=context.copy()
        )
        self._next_id += 1
        
        logger.info(
            f"Decision: {decision.action} "
            f"(confidence: {confidence:.2f})"
        )
        
        return decision
    
    def _count_recent_rejections(
        self,
        decision_type: DecisionType,
        hours: int = 24
    ) -> int:
        """Count recent rejected decisions of a type."""
        cutoff = datetime.now()
        count = 0
        
        for decision in reversed(self._history[-100:]):
            if decision.decision_type == decision_type:
                if decision.result == "rejected":
                    count += 1
        
        return count
    
    def should_auto_execute(self, decision: Decision) -> bool:
        """Check if a decision should be auto-executed."""
        return decision.confidence >= self.auto_execute_threshold
    
    def requires_confirmation(self, decision: Decision) -> bool:
        """Check if a decision requires user confirmation."""
        return (
            decision.confidence < self.auto_execute_threshold and
            decision.confidence >= self.require_confirmation_threshold
        )
    
    def record_result(
        self,
        decision_id: str,
        result: str,
        executed: bool = True
    ) -> None:
        """Record the result of a decision."""
        for decision in self._history:
            if decision.id == decision_id:
                decision.executed = executed
                decision.result = result
                break
    
    def get_pending_decisions(self) -> List[Decision]:
        """Get decisions awaiting confirmation."""
        return [
            d for d in self._history
            if not d.executed and self.requires_confirmation(d)
        ]
    
    def get_history(
        self,
        decision_type: DecisionType = None,
        limit: int = 50
    ) -> List[Decision]:
        """Get decision history."""
        history = self._history
        if decision_type:
            history = [d for d in history if d.decision_type == decision_type]
        return history[-limit:]

