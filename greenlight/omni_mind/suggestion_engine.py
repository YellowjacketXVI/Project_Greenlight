"""
Greenlight Suggestion Engine

Proactive suggestions for improving story content.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.suggestion")


class SuggestionCategory(Enum):
    """Categories of suggestions."""
    CONTINUITY = "continuity"
    QUALITY = "quality"
    OPTIMIZATION = "optimization"
    CREATIVE = "creative"
    TECHNICAL = "technical"


class SuggestionPriority(Enum):
    """Priority levels for suggestions."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class Suggestion:
    """A proactive suggestion."""
    id: str
    category: SuggestionCategory
    priority: SuggestionPriority
    title: str
    description: str
    action: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    dismissed: bool = False
    applied: bool = False
    
    def dismiss(self) -> None:
        self.dismissed = True
    
    def apply(self) -> None:
        self.applied = True


@dataclass
class SuggestionTrigger:
    """A trigger for generating suggestions."""
    name: str
    category: SuggestionCategory
    priority: SuggestionPriority
    condition: Callable[[Dict], bool]
    generate: Callable[[Dict], Suggestion]


class SuggestionEngine:
    """
    Generates proactive suggestions for content improvement.
    
    Features:
    - Continuity issue detection
    - Quality improvement suggestions
    - Optimization recommendations
    - Creative enhancements
    """
    
    def __init__(self):
        """Initialize the suggestion engine."""
        self._triggers: List[SuggestionTrigger] = []
        self._suggestions: List[Suggestion] = []
        self._dismissed_patterns: List[str] = []
        self._next_id = 0
        
        self._initialize_default_triggers()
    
    def _initialize_default_triggers(self) -> None:
        """Initialize default suggestion triggers."""
        # Continuity suggestions
        self.add_trigger(SuggestionTrigger(
            name="missing_character_description",
            category=SuggestionCategory.CONTINUITY,
            priority=SuggestionPriority.HIGH,
            condition=lambda ctx: any(
                not c.get('visual_description')
                for c in ctx.get('characters', [])
            ),
            generate=lambda ctx: self._create_suggestion(
                category=SuggestionCategory.CONTINUITY,
                priority=SuggestionPriority.HIGH,
                title="Missing Character Descriptions",
                description="Some characters lack visual descriptions for consistent storyboard generation.",
                action="add_character_descriptions",
                context=ctx
            )
        ))
        
        # Quality suggestions
        self.add_trigger(SuggestionTrigger(
            name="vague_prompt_language",
            category=SuggestionCategory.QUALITY,
            priority=SuggestionPriority.MEDIUM,
            condition=lambda ctx: ctx.get('vague_word_count', 0) > 3,
            generate=lambda ctx: self._create_suggestion(
                category=SuggestionCategory.QUALITY,
                priority=SuggestionPriority.MEDIUM,
                title="Vague Language Detected",
                description=f"Found {ctx.get('vague_word_count')} vague words that could be more specific.",
                action="refine_vague_language",
                context=ctx
            )
        ))
        
        # Optimization suggestions
        self.add_trigger(SuggestionTrigger(
            name="large_regeneration_queue",
            category=SuggestionCategory.OPTIMIZATION,
            priority=SuggestionPriority.LOW,
            condition=lambda ctx: ctx.get('queue_size', 0) > 10,
            generate=lambda ctx: self._create_suggestion(
                category=SuggestionCategory.OPTIMIZATION,
                priority=SuggestionPriority.LOW,
                title="Large Regeneration Queue",
                description=f"{ctx.get('queue_size')} items pending regeneration. Consider batch processing.",
                action="batch_regenerate",
                context=ctx
            )
        ))
    
    def add_trigger(self, trigger: SuggestionTrigger) -> None:
        """Add a suggestion trigger."""
        self._triggers.append(trigger)
    
    def evaluate(self, context: Dict[str, Any]) -> List[Suggestion]:
        """
        Evaluate context and generate suggestions.
        
        Args:
            context: Current context information
            
        Returns:
            List of new suggestions
        """
        new_suggestions = []
        
        for trigger in self._triggers:
            try:
                if trigger.condition(context):
                    # Check if similar suggestion was dismissed
                    if self._is_dismissed(trigger.name):
                        continue
                    
                    suggestion = trigger.generate(context)
                    new_suggestions.append(suggestion)
                    self._suggestions.append(suggestion)
                    
                    logger.info(f"Generated suggestion: {suggestion.title}")
                    
            except Exception as e:
                logger.error(f"Trigger evaluation failed: {trigger.name} - {e}")
        
        return new_suggestions
    
    def _create_suggestion(
        self,
        category: SuggestionCategory,
        priority: SuggestionPriority,
        title: str,
        description: str,
        action: str = None,
        context: Dict = None
    ) -> Suggestion:
        """Create a suggestion."""
        suggestion = Suggestion(
            id=f"sug_{self._next_id:06d}",
            category=category,
            priority=priority,
            title=title,
            description=description,
            action=action,
            context=context or {}
        )
        self._next_id += 1
        return suggestion
    
    def _is_dismissed(self, pattern: str) -> bool:
        """Check if a suggestion pattern was dismissed."""
        return pattern in self._dismissed_patterns
    
    def dismiss(self, suggestion_id: str, remember: bool = True) -> None:
        """
        Dismiss a suggestion.
        
        Args:
            suggestion_id: Suggestion to dismiss
            remember: If True, don't show similar suggestions
        """
        for suggestion in self._suggestions:
            if suggestion.id == suggestion_id:
                suggestion.dismiss()
                if remember:
                    # Find the trigger that generated this
                    for trigger in self._triggers:
                        if trigger.category == suggestion.category:
                            self._dismissed_patterns.append(trigger.name)
                            break
                break
    
    def apply(self, suggestion_id: str) -> Optional[str]:
        """
        Mark a suggestion as applied.
        
        Args:
            suggestion_id: Suggestion to apply
            
        Returns:
            Action to execute, if any
        """
        for suggestion in self._suggestions:
            if suggestion.id == suggestion_id:
                suggestion.apply()
                return suggestion.action
        return None
    
    def get_active(
        self,
        category: SuggestionCategory = None,
        limit: int = 10
    ) -> List[Suggestion]:
        """Get active (not dismissed/applied) suggestions."""
        active = [
            s for s in self._suggestions
            if not s.dismissed and not s.applied
        ]
        
        if category:
            active = [s for s in active if s.category == category]
        
        # Sort by priority
        active.sort(key=lambda s: s.priority.value)
        
        return active[:limit]
    
    def get_by_priority(
        self,
        priority: SuggestionPriority
    ) -> List[Suggestion]:
        """Get suggestions of a specific priority."""
        return [
            s for s in self._suggestions
            if s.priority == priority and not s.dismissed and not s.applied
        ]

