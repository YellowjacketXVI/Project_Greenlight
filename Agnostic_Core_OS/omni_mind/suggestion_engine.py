"""
Agnostic_Core_OS OmniMind Suggestion Engine

Proactive suggestion generation for the OmniMind context library.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger("agnostic_core_os.omni_mind.suggestion")


class SuggestionType(Enum):
    """Types of suggestions."""
    IMPROVEMENT = "improvement"
    OPTIMIZATION = "optimization"
    WARNING = "warning"
    TIP = "tip"
    ACTION = "action"
    CREATIVE = "creative"


class SuggestionPriority(Enum):
    """Priority levels for suggestions."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Suggestion:
    """A proactive suggestion."""
    id: str
    suggestion_type: SuggestionType
    title: str
    description: str
    priority: SuggestionPriority = SuggestionPriority.MEDIUM
    action: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    dismissed: bool = False
    accepted: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "suggestion_type": self.suggestion_type.value,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "action": self.action,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "dismissed": self.dismissed,
            "accepted": self.accepted
        }


class SuggestionEngine:
    """
    Generates proactive suggestions for OmniMind.
    
    Features:
    - Context-aware suggestions
    - Priority-based ordering
    - Suggestion history
    - Accept/dismiss tracking
    """
    
    def __init__(self, max_active_suggestions: int = 10):
        """
        Initialize the suggestion engine.
        
        Args:
            max_active_suggestions: Maximum active suggestions to keep
        """
        self.max_active_suggestions = max_active_suggestions
        self._suggestions: Dict[str, Suggestion] = {}
        self._next_id = 0
    
    def generate(
        self,
        suggestion_type: SuggestionType,
        title: str,
        description: str,
        priority: SuggestionPriority = SuggestionPriority.MEDIUM,
        action: Optional[str] = None,
        **context
    ) -> Suggestion:
        """
        Generate a new suggestion.
        
        Args:
            suggestion_type: Type of suggestion
            title: Short title
            description: Detailed description
            priority: Priority level
            action: Optional action to take
            **context: Additional context
            
        Returns:
            Created Suggestion
        """
        suggestion = Suggestion(
            id=f"sug_{self._next_id:06d}",
            suggestion_type=suggestion_type,
            title=title,
            description=description,
            priority=priority,
            action=action,
            context=context
        )
        self._next_id += 1
        
        self._suggestions[suggestion.id] = suggestion
        self._cleanup_old_suggestions()
        
        logger.debug(f"Generated suggestion: {suggestion.id} - {title}")
        return suggestion
    
    def _cleanup_old_suggestions(self) -> None:
        """Remove old dismissed/accepted suggestions."""
        active = [s for s in self._suggestions.values() if not s.dismissed and not s.accepted]
        if len(active) > self.max_active_suggestions:
            # Remove oldest low-priority suggestions
            active.sort(key=lambda s: (s.priority.value, s.timestamp))
            to_remove = active[:-self.max_active_suggestions]
            for s in to_remove:
                s.dismissed = True
    
    def get_active(self) -> List[Suggestion]:
        """Get all active (not dismissed/accepted) suggestions."""
        active = [s for s in self._suggestions.values() if not s.dismissed and not s.accepted]
        return sorted(active, key=lambda s: (s.priority.value, s.timestamp), reverse=True)
    
    def accept(self, suggestion_id: str) -> bool:
        """Accept a suggestion."""
        if suggestion_id in self._suggestions:
            self._suggestions[suggestion_id].accepted = True
            return True
        return False
    
    def dismiss(self, suggestion_id: str) -> bool:
        """Dismiss a suggestion."""
        if suggestion_id in self._suggestions:
            self._suggestions[suggestion_id].dismissed = True
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get suggestion statistics."""
        all_suggestions = list(self._suggestions.values())
        return {
            "total": len(all_suggestions),
            "active": len([s for s in all_suggestions if not s.dismissed and not s.accepted]),
            "accepted": len([s for s in all_suggestions if s.accepted]),
            "dismissed": len([s for s in all_suggestions if s.dismissed])
        }

