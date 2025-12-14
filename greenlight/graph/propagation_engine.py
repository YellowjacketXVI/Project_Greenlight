"""
Greenlight Propagation Engine

Manages cascading edits through the dependency graph.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Callable, Any
from enum import Enum
from datetime import datetime

from greenlight.core.logging_config import get_logger
from .dependency_graph import DependencyGraph, NodeType, EdgeType

logger = get_logger("graph.propagation")


class PropagationStrategy(Enum):
    """Strategies for propagating changes."""
    IMMEDIATE = "immediate"      # Propagate immediately
    QUEUED = "queued"           # Add to regeneration queue
    MANUAL = "manual"           # Require manual confirmation
    SELECTIVE = "selective"     # User selects which to propagate


class ChangeType(Enum):
    """Types of changes that can be propagated."""
    CONTENT_EDIT = "content_edit"
    TAG_CHANGE = "tag_change"
    STRUCTURE_CHANGE = "structure_change"
    DELETION = "deletion"
    ADDITION = "addition"


@dataclass
class PropagationEvent:
    """Represents a change that needs to be propagated."""
    source_node_id: str
    change_type: ChangeType
    old_value: Any = None
    new_value: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PropagationResult:
    """Result of a propagation operation."""
    source_node_id: str
    affected_nodes: List[str]
    propagated_nodes: List[str]
    failed_nodes: List[str]
    skipped_nodes: List[str]
    errors: Dict[str, str] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        return len(self.failed_nodes) == 0


class PropagationEngine:
    """
    Manages cascading edits through the dependency graph.
    
    Features:
    - Automatic detection of affected nodes
    - Configurable propagation strategies
    - Selective propagation support
    - Rollback capability
    """
    
    def __init__(
        self,
        graph: DependencyGraph,
        default_strategy: PropagationStrategy = PropagationStrategy.QUEUED
    ):
        """
        Initialize propagation engine.
        
        Args:
            graph: DependencyGraph instance
            default_strategy: Default propagation strategy
        """
        self.graph = graph
        self.default_strategy = default_strategy
        self._handlers: Dict[ChangeType, Callable] = {}
        self._history: List[PropagationEvent] = []
    
    def register_handler(
        self,
        change_type: ChangeType,
        handler: Callable[[str, PropagationEvent], bool]
    ) -> None:
        """
        Register a handler for a specific change type.
        
        Args:
            change_type: Type of change to handle
            handler: Function that processes the change
        """
        self._handlers[change_type] = handler
        logger.debug(f"Registered handler for {change_type.value}")
    
    def calculate_affected(
        self,
        node_id: str,
        change_type: ChangeType
    ) -> List[str]:
        """
        Calculate all nodes affected by a change.
        
        Args:
            node_id: ID of changed node
            change_type: Type of change
            
        Returns:
            List of affected node IDs in propagation order
        """
        affected = self.graph.get_all_affected(node_id)
        
        # Sort by dependency order (topological sort)
        ordered = self._topological_sort(affected, node_id)
        
        logger.info(f"Change to {node_id} affects {len(ordered)} nodes")
        return ordered
    
    def _topological_sort(
        self,
        nodes: Set[str],
        source: str
    ) -> List[str]:
        """Sort nodes in dependency order."""
        # Simple BFS-based ordering
        ordered = []
        visited = set()
        queue = [source]
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            
            if current in nodes:
                ordered.append(current)
            
            for dependent in self.graph.get_dependents(current):
                if dependent not in visited:
                    queue.append(dependent)
        
        return ordered
    
    def propagate(
        self,
        event: PropagationEvent,
        strategy: PropagationStrategy = None,
        selected_nodes: Set[str] = None
    ) -> PropagationResult:
        """
        Propagate a change through the graph.
        
        Args:
            event: The propagation event
            strategy: Override default strategy
            selected_nodes: For SELECTIVE strategy, nodes to propagate to
            
        Returns:
            PropagationResult with details
        """
        strategy = strategy or self.default_strategy
        
        # Record in history
        self._history.append(event)
        
        # Calculate affected nodes
        affected = self.calculate_affected(event.source_node_id, event.change_type)
        
        propagated = []
        failed = []
        skipped = []
        errors = {}
        
        for node_id in affected:
            # Check if should propagate
            if strategy == PropagationStrategy.SELECTIVE:
                if selected_nodes and node_id not in selected_nodes:
                    skipped.append(node_id)
                    continue
            elif strategy == PropagationStrategy.MANUAL:
                skipped.append(node_id)
                continue
            
            # Execute propagation
            try:
                success = self._propagate_to_node(node_id, event)
                if success:
                    propagated.append(node_id)
                else:
                    failed.append(node_id)
            except Exception as e:
                failed.append(node_id)
                errors[node_id] = str(e)
                logger.error(f"Propagation to {node_id} failed: {e}")
        
        result = PropagationResult(
            source_node_id=event.source_node_id,
            affected_nodes=affected,
            propagated_nodes=propagated,
            failed_nodes=failed,
            skipped_nodes=skipped,
            errors=errors
        )
        
        logger.info(
            f"Propagation complete: {len(propagated)} propagated, "
            f"{len(failed)} failed, {len(skipped)} skipped"
        )
        
        return result
    
    def _propagate_to_node(
        self,
        node_id: str,
        event: PropagationEvent
    ) -> bool:
        """Propagate change to a single node."""
        handler = self._handlers.get(event.change_type)
        
        if handler:
            return handler(node_id, event)
        
        # Default: mark node as needing regeneration
        node = self.graph.get_node(node_id)
        node.data['needs_regeneration'] = True
        node.data['regeneration_reason'] = f"Upstream change: {event.source_node_id}"
        node.updated_at = datetime.now()
        
        return True
    
    def get_pending_regenerations(self) -> List[str]:
        """Get all nodes marked for regeneration."""
        pending = []
        for node_id, node in self.graph._nodes.items():
            if node.data.get('needs_regeneration', False):
                pending.append(node_id)
        return pending
    
    def clear_regeneration_flag(self, node_id: str) -> None:
        """Clear the regeneration flag for a node."""
        node = self.graph.get_node(node_id)
        node.data['needs_regeneration'] = False
        node.data.pop('regeneration_reason', None)

