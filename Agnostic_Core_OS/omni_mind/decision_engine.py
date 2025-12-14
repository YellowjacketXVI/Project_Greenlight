"""
Agnostic_Core_OS OmniMind Decision Engine

Autonomous decision making for the OmniMind context library.
Provides rule-based decisions with confidence scoring.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger("agnostic_core_os.omni_mind.decision")


class DecisionType(Enum):
    """Types of decisions."""
    REGENERATION = "regeneration"
    PROPAGATION = "propagation"
    SUGGESTION = "suggestion"
    VALIDATION = "validation"
    OPTIMIZATION = "optimization"
    SELF_HEAL = "self_heal"
    ROUTING = "routing"


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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "decision_type": self.decision_type.value,
            "action": self.action,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "reasoning": self.reasoning,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "executed": self.executed,
            "result": self.result
        }


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
    Makes autonomous decisions for OmniMind.
    
    Features:
    - Rule-based decision making
    - Confidence scoring
    - Decision history
    - Auto-execute for high-confidence decisions
    - Confirmation required for low-confidence decisions
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
        # Self-heal rule
        self.add_rule(DecisionRule(
            name="auto_self_heal",
            condition=lambda ctx: ctx.get("error_count", 0) > 0 and ctx.get("auto_heal", True),
            action="self_heal",
            decision_type=DecisionType.SELF_HEAL,
            base_confidence=0.9,
            priority=10
        ))
        
        # Validation rule
        self.add_rule(DecisionRule(
            name="validate_on_change",
            condition=lambda ctx: ctx.get("content_changed", False),
            action="run_validation",
            decision_type=DecisionType.VALIDATION,
            base_confidence=0.85,
            priority=5
        ))
    
    def add_rule(self, rule: DecisionRule) -> None:
        """Add a decision rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
    
    def evaluate(self, context: Dict[str, Any]) -> List[Decision]:
        """
        Evaluate context and generate decisions.
        
        Args:
            context: Current context
            
        Returns:
            List of decisions
        """
        decisions = []
        
        for rule in self._rules:
            try:
                if rule.condition(context):
                    decision = Decision(
                        id=f"dec_{self._next_id:06d}",
                        decision_type=rule.decision_type,
                        action=rule.action,
                        confidence=rule.base_confidence,
                        reasoning=f"Rule '{rule.name}' matched",
                        context=context
                    )
                    self._next_id += 1
                    decisions.append(decision)
                    self._history.append(decision)
                    logger.debug(f"Decision: {decision.id} - {rule.action}")
            except Exception as e:
                logger.error(f"Rule evaluation failed: {rule.name} - {e}")
        
        return decisions

