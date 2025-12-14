"""
Greenlight Regeneration Queue

Priority-based queue for managing content regeneration.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any
from enum import Enum
from datetime import datetime
import heapq
from threading import Lock

from greenlight.core.logging_config import get_logger
from .dependency_graph import DependencyGraph, NodeType

logger = get_logger("graph.regeneration")


class RegenerationPriority(Enum):
    """Priority levels for regeneration tasks."""
    CRITICAL = 1    # Must regenerate immediately
    HIGH = 2        # Regenerate soon
    NORMAL = 3      # Standard priority
    LOW = 4         # Can wait
    BACKGROUND = 5  # Regenerate when idle


class RegenerationStatus(Enum):
    """Status of a regeneration task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(order=True)
class RegenerationTask:
    """A task in the regeneration queue."""
    priority: int
    created_at: datetime = field(compare=False)
    node_id: str = field(compare=False)
    reason: str = field(compare=False, default="")
    status: RegenerationStatus = field(compare=False, default=RegenerationStatus.PENDING)
    attempts: int = field(compare=False, default=0)
    max_attempts: int = field(compare=False, default=3)
    metadata: Dict[str, Any] = field(compare=False, default_factory=dict)
    
    @property
    def can_retry(self) -> bool:
        return self.attempts < self.max_attempts


class RegenerationQueue:
    """
    Priority-based queue for managing content regeneration.
    
    Features:
    - Priority-based ordering
    - Dependency-aware scheduling
    - Retry logic with backoff
    - Batch processing support
    - Progress tracking
    """
    
    def __init__(
        self,
        graph: DependencyGraph,
        max_concurrent: int = 3
    ):
        """
        Initialize regeneration queue.
        
        Args:
            graph: DependencyGraph for dependency checking
            max_concurrent: Maximum concurrent regenerations
        """
        self.graph = graph
        self.max_concurrent = max_concurrent
        
        self._queue: List[RegenerationTask] = []
        self._in_progress: Dict[str, RegenerationTask] = {}
        self._completed: Dict[str, RegenerationTask] = {}
        self._lock = Lock()
        
        self._regenerator: Optional[Callable] = None
    
    def set_regenerator(
        self,
        regenerator: Callable[[str, Dict], bool]
    ) -> None:
        """
        Set the regeneration function.
        
        Args:
            regenerator: Function that regenerates a node
        """
        self._regenerator = regenerator
    
    def add(
        self,
        node_id: str,
        priority: RegenerationPriority = RegenerationPriority.NORMAL,
        reason: str = "",
        **metadata
    ) -> RegenerationTask:
        """
        Add a node to the regeneration queue.
        
        Args:
            node_id: ID of node to regenerate
            priority: Task priority
            reason: Reason for regeneration
            **metadata: Additional task metadata
            
        Returns:
            Created RegenerationTask
        """
        with self._lock:
            # Check if already queued
            for task in self._queue:
                if task.node_id == node_id:
                    # Update priority if higher
                    if priority.value < task.priority:
                        task.priority = priority.value
                    return task
            
            task = RegenerationTask(
                priority=priority.value,
                created_at=datetime.now(),
                node_id=node_id,
                reason=reason,
                metadata=metadata
            )
            
            heapq.heappush(self._queue, task)
            logger.info(f"Added to queue: {node_id} (priority: {priority.name})")
            
            return task
    
    def add_batch(
        self,
        node_ids: List[str],
        priority: RegenerationPriority = RegenerationPriority.NORMAL,
        reason: str = ""
    ) -> List[RegenerationTask]:
        """Add multiple nodes to the queue."""
        return [
            self.add(node_id, priority, reason)
            for node_id in node_ids
        ]
    
    def get_next(self) -> Optional[RegenerationTask]:
        """
        Get the next task to process.
        
        Returns:
            Next task, or None if queue is empty or at capacity
        """
        with self._lock:
            if len(self._in_progress) >= self.max_concurrent:
                return None
            
            while self._queue:
                task = heapq.heappop(self._queue)
                
                # Check if dependencies are satisfied
                if self._dependencies_satisfied(task.node_id):
                    task.status = RegenerationStatus.IN_PROGRESS
                    task.attempts += 1
                    self._in_progress[task.node_id] = task
                    return task
                else:
                    # Re-queue with lower priority
                    task.priority = min(task.priority + 1, RegenerationPriority.BACKGROUND.value)
                    heapq.heappush(self._queue, task)
            
            return None
    
    def _dependencies_satisfied(self, node_id: str) -> bool:
        """Check if all dependencies have been regenerated."""
        try:
            dependencies = self.graph.get_dependencies(node_id)
            for dep_id in dependencies:
                # Check if dependency is pending or in progress
                if dep_id in self._in_progress:
                    return False
                for task in self._queue:
                    if task.node_id == dep_id:
                        return False
            return True
        except Exception:
            return True
    
    def complete(self, node_id: str, success: bool = True) -> None:
        """
        Mark a task as completed.
        
        Args:
            node_id: ID of completed node
            success: Whether regeneration succeeded
        """
        with self._lock:
            if node_id not in self._in_progress:
                return
            
            task = self._in_progress.pop(node_id)
            
            if success:
                task.status = RegenerationStatus.COMPLETED
                self._completed[node_id] = task
                logger.info(f"Completed: {node_id}")
            else:
                task.status = RegenerationStatus.FAILED
                if task.can_retry:
                    # Re-queue for retry
                    task.status = RegenerationStatus.PENDING
                    task.priority = min(task.priority + 1, RegenerationPriority.LOW.value)
                    heapq.heappush(self._queue, task)
                    logger.warning(f"Retry queued: {node_id} (attempt {task.attempts})")
                else:
                    self._completed[node_id] = task
                    logger.error(f"Failed permanently: {node_id}")
    
    def cancel(self, node_id: str) -> bool:
        """Cancel a pending task."""
        with self._lock:
            for i, task in enumerate(self._queue):
                if task.node_id == node_id:
                    task.status = RegenerationStatus.CANCELLED
                    self._queue.pop(i)
                    heapq.heapify(self._queue)
                    return True
            return False
    
    @property
    def pending_count(self) -> int:
        return len(self._queue)
    
    @property
    def in_progress_count(self) -> int:
        return len(self._in_progress)
    
    def get_status(self) -> Dict[str, Any]:
        """Get queue status summary."""
        return {
            'pending': self.pending_count,
            'in_progress': self.in_progress_count,
            'completed': len(self._completed),
            'in_progress_nodes': list(self._in_progress.keys())
        }

