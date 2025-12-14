"""
Agnostic_Core_OS OmniMind Self-Heal Queue

Auto-implementation task queue for self-healing capabilities.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger("agnostic_core_os.omni_mind.self_heal")


class TaskPriority(Enum):
    """Priority levels for self-heal tasks."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(Enum):
    """Status of a self-heal task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskCategory(Enum):
    """Categories of self-heal tasks."""
    ERROR_FIX = "error_fix"
    OPTIMIZATION = "optimization"
    VALIDATION = "validation"
    REGENERATION = "regeneration"
    CLEANUP = "cleanup"


@dataclass
class SelfHealTask:
    """A self-healing task."""
    id: str
    category: TaskCategory
    title: str
    description: str
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    source: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "source": self.source,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count
        }


class SelfHealQueue:
    """
    Queue for self-healing tasks.
    
    Features:
    - Priority-based task ordering
    - Automatic retry on failure
    - Task history tracking
    - Handler registration
    """
    
    def __init__(self, max_retries: int = 3):
        """
        Initialize the self-heal queue.
        
        Args:
            max_retries: Maximum retry attempts per task
        """
        self.max_retries = max_retries
        self._tasks: Dict[str, SelfHealTask] = {}
        self._handlers: Dict[TaskCategory, Callable] = {}
        self._next_id = 0
    
    def add_task(
        self,
        category: TaskCategory,
        title: str,
        description: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        source: Optional[str] = None,
        **context
    ) -> SelfHealTask:
        """
        Add a self-heal task to the queue.
        
        Args:
            category: Task category
            title: Short title
            description: Detailed description
            priority: Priority level
            source: Source of the task
            **context: Additional context
            
        Returns:
            Created SelfHealTask
        """
        task = SelfHealTask(
            id=f"heal_{self._next_id:06d}",
            category=category,
            title=title,
            description=description,
            priority=priority,
            source=source,
            context=context,
            max_retries=self.max_retries
        )
        self._next_id += 1
        
        self._tasks[task.id] = task
        logger.info(f"Added self-heal task: {task.id} - {title}")
        return task
    
    def register_handler(self, category: TaskCategory, handler: Callable) -> None:
        """Register a handler for a task category."""
        self._handlers[category] = handler
        logger.debug(f"Registered handler for {category.value}")
    
    def get_pending(self) -> List[SelfHealTask]:
        """Get all pending tasks, ordered by priority."""
        pending = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 3
        }
        return sorted(pending, key=lambda t: (priority_order[t.priority], t.created_at))
    
    async def process_next(self) -> Optional[SelfHealTask]:
        """Process the next pending task."""
        pending = self.get_pending()
        if not pending:
            return None

        task = pending[0]
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()

        handler = self._handlers.get(task.category)
        if not handler:
            task.status = TaskStatus.FAILED
            task.error = f"No handler for category: {task.category.value}"
            logger.error(task.error)
            return task

        try:
            result = await handler(task)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = str(result) if result else "Success"
            logger.info(f"Task completed: {task.id}")
        except Exception as e:
            task.retry_count += 1
            if task.retry_count >= task.max_retries:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                logger.error(f"Task failed after {task.retry_count} retries: {task.id} - {e}")
            else:
                task.status = TaskStatus.PENDING
                logger.warning(f"Task retry {task.retry_count}/{task.max_retries}: {task.id}")

        return task

    async def process_all(self) -> List[SelfHealTask]:
        """Process all pending tasks."""
        processed = []
        while True:
            task = await self.process_next()
            if not task:
                break
            processed.append(task)
        return processed

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        all_tasks = list(self._tasks.values())
        return {
            "total": len(all_tasks),
            "pending": len([t for t in all_tasks if t.status == TaskStatus.PENDING]),
            "in_progress": len([t for t in all_tasks if t.status == TaskStatus.IN_PROGRESS]),
            "completed": len([t for t in all_tasks if t.status == TaskStatus.COMPLETED]),
            "failed": len([t for t in all_tasks if t.status == TaskStatus.FAILED]),
            "cancelled": len([t for t in all_tasks if t.status == TaskStatus.CANCELLED])
        }

