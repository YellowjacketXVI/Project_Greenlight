"""
Agnostic_Core_OS OmniMind

The central context library for Agnostic_Core_OS.
OmniMind provides memory, context retrieval, decision making,
suggestions, and self-healing capabilities.

The RuntimeDaemon operates OmniMind as the context provider
for all connected applications.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
from enum import Enum
from datetime import datetime
import logging

from .memory import Memory, MemoryType, MemoryEntry
from .context_engine import ContextEngine, ContextQuery, ContextResult, ContextSource
from .decision_engine import DecisionEngine, Decision, DecisionType
from .suggestion_engine import SuggestionEngine, Suggestion, SuggestionType, SuggestionPriority
from .self_heal import SelfHealQueue, SelfHealTask, TaskCategory, TaskPriority

logger = logging.getLogger("agnostic_core_os.omni_mind")


class OmniMindMode(Enum):
    """Operating modes for OmniMind."""
    PASSIVE = "passive"      # Only respond when asked
    PROACTIVE = "proactive"  # Offer suggestions
    AUTONOMOUS = "autonomous"  # Auto-execute high-confidence decisions


@dataclass
class OmniMindConfig:
    """Configuration for OmniMind."""
    mode: OmniMindMode = OmniMindMode.PROACTIVE
    project_path: Optional[Path] = None
    auto_heal: bool = True
    max_memory_short_term: int = 50
    max_memory_long_term: int = 1000
    auto_execute_threshold: float = 0.8
    enable_suggestions: bool = True


class OmniMind:
    """
    Central context library for Agnostic_Core_OS.
    
    OmniMind is operated by the RuntimeDaemon and provides:
    - Memory management (short-term, long-term, preferences)
    - Context retrieval and assembly
    - Decision engine for autonomous actions
    - Suggestion engine for proactive assistance
    - Self-healing queue for error recovery
    
    Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                         OMNI_MIND                               │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
    │  │   Memory    │  │  Context    │  │  Decision   │             │
    │  │   System    │  │  Engine     │  │  Engine     │             │
    │  └─────────────┘  └─────────────┘  └─────────────┘             │
    │  ┌─────────────┐  ┌─────────────┐                              │
    │  │  Suggestion │  │  Self-Heal  │                              │
    │  │   Engine    │  │   Queue     │                              │
    │  └─────────────┘  └─────────────┘                              │
    └─────────────────────────────────────────────────────────────────┘
    """
    
    def __init__(self, config: Optional[OmniMindConfig] = None):
        """
        Initialize OmniMind.
        
        Args:
            config: Configuration options
        """
        self.config = config or OmniMindConfig()
        self._initialized = False
        self._started_at: Optional[datetime] = None
        
        # Initialize components
        self.memory = Memory(
            short_term_limit=self.config.max_memory_short_term,
            long_term_limit=self.config.max_memory_long_term
        )
        
        self.context_engine = ContextEngine(
            project_path=self.config.project_path
        )
        
        self.decision_engine = DecisionEngine(
            auto_execute_threshold=self.config.auto_execute_threshold
        )
        
        self.suggestion_engine = SuggestionEngine()
        
        self.self_heal_queue = SelfHealQueue()
        
        self._initialized = True
        self._started_at = datetime.now()
        logger.info(f"OmniMind initialized (mode: {self.config.mode.value})")
    
    @property
    def mode(self) -> OmniMindMode:
        """Current operating mode."""
        return self.config.mode
    
    @mode.setter
    def mode(self, value: OmniMindMode) -> None:
        """Set operating mode."""
        self.config.mode = value
        logger.info(f"OmniMind mode changed to: {value.value}")
    
    # =========================================================================
    # MEMORY OPERATIONS
    # =========================================================================
    
    def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.PROJECT_CONTEXT,
        importance: float = 0.5,
        **metadata
    ) -> MemoryEntry:
        """Add something to memory."""
        return self.memory.add(content, memory_type, importance, **metadata)
    
    def recall(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search memory for relevant entries."""
        return self.memory.search(query, limit)
    
    def get_conversation_context(self, turns: int = 5) -> str:
        """Get recent conversation context."""
        return self.memory.get_conversation_context(turns)
    
    # =========================================================================
    # CONTEXT RETRIEVAL
    # =========================================================================
    
    def retrieve(self, query: ContextQuery) -> ContextResult:
        """Retrieve context for a query."""
        result = self.context_engine.retrieve(query)
        
        # Remember the retrieval
        self.remember(
            content=f"Retrieved {result.total_found} items for: {query.query_text}",
            memory_type=MemoryType.RETRIEVAL_RESULT,
            importance=0.3,
            query=query.query_text,
            results_count=result.total_found
        )
        
        return result
    
    def index(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        scope: Optional[str] = None,
        **metadata
    ) -> str:
        """Index content for retrieval."""
        return self.context_engine.index_document(content, tags=tags, scope=scope, **metadata)

    # =========================================================================
    # DECISION MAKING
    # =========================================================================

    def evaluate(self, context: Dict[str, Any]) -> List[Decision]:
        """Evaluate context and generate decisions."""
        decisions = self.decision_engine.evaluate(context)

        # Auto-execute in autonomous mode
        if self.mode == OmniMindMode.AUTONOMOUS:
            for decision in decisions:
                if decision.confidence >= self.config.auto_execute_threshold:
                    self._execute_decision(decision)

        return decisions

    def _execute_decision(self, decision: Decision) -> None:
        """Execute a decision."""
        # Log the decision
        self.remember(
            content=f"Executed decision: {decision.action}",
            memory_type=MemoryType.DECISION,
            importance=0.7,
            decision_id=decision.id,
            action=decision.action
        )
        decision.executed = True
        logger.info(f"Executed decision: {decision.id} - {decision.action}")

    # =========================================================================
    # SUGGESTIONS
    # =========================================================================

    def suggest(
        self,
        title: str,
        description: str,
        suggestion_type: SuggestionType = SuggestionType.TIP,
        priority: SuggestionPriority = SuggestionPriority.MEDIUM,
        action: Optional[str] = None,
        **context
    ) -> Optional[Suggestion]:
        """Generate a suggestion (if enabled)."""
        if not self.config.enable_suggestions:
            return None

        if self.mode == OmniMindMode.PASSIVE:
            return None

        return self.suggestion_engine.generate(
            suggestion_type=suggestion_type,
            title=title,
            description=description,
            priority=priority,
            action=action,
            **context
        )

    def get_suggestions(self) -> List[Suggestion]:
        """Get active suggestions."""
        return self.suggestion_engine.get_active()

    # =========================================================================
    # SELF-HEALING
    # =========================================================================

    def queue_heal_task(
        self,
        title: str,
        description: str,
        category: TaskCategory = TaskCategory.ERROR_FIX,
        priority: TaskPriority = TaskPriority.MEDIUM,
        source: Optional[str] = None,
        **context
    ) -> SelfHealTask:
        """Queue a self-healing task."""
        return self.self_heal_queue.add_task(
            category=category,
            title=title,
            description=description,
            priority=priority,
            source=source,
            **context
        )

    async def process_heal_queue(self) -> List[SelfHealTask]:
        """Process all pending self-heal tasks."""
        if not self.config.auto_heal:
            return []
        return await self.self_heal_queue.process_all()

    # =========================================================================
    # DIAGNOSTICS
    # =========================================================================

    def diagnose(self) -> Dict[str, Any]:
        """Run diagnostics on OmniMind."""
        return {
            "mode": self.mode.value,
            "initialized": self._initialized,
            "uptime_seconds": (datetime.now() - self._started_at).total_seconds() if self._started_at else 0,
            "memory": self.memory.get_stats(),
            "context_engine": self.context_engine.get_stats(),
            "suggestions": self.suggestion_engine.get_stats(),
            "self_heal_queue": self.self_heal_queue.get_stats()
        }

    def get_health_report(self) -> str:
        """Generate a health report."""
        diag = self.diagnose()
        lines = [
            "# OmniMind Health Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            f"## Status",
            f"- Mode: {diag['mode']}",
            f"- Uptime: {diag['uptime_seconds']:.1f}s",
            "",
            f"## Memory",
            f"- Short-term: {diag['memory']['short_term_count']}/{diag['memory']['short_term_limit']}",
            f"- Long-term: {diag['memory']['long_term_count']}/{diag['memory']['long_term_limit']}",
            "",
            f"## Context Engine",
            f"- Documents: {diag['context_engine']['total_documents']}",
            f"- Tags: {diag['context_engine']['total_tags']}",
            "",
            f"## Self-Heal Queue",
            f"- Pending: {diag['self_heal_queue']['pending']}",
            f"- Completed: {diag['self_heal_queue']['completed']}",
            f"- Failed: {diag['self_heal_queue']['failed']}"
        ]
        return "\n".join(lines)

