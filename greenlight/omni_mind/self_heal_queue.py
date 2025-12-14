"""
Greenlight Self-Heal Task Queue

OmniMind waiting task list for missing functions and auto-implementation.
Initializes on startup to detect and queue self-healing tasks.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path
from enum import Enum
import json

from greenlight.core.logging_config import get_logger
from greenlight.utils.file_utils import read_json, write_json, ensure_directory

logger = get_logger("omni_mind.self_heal_queue")


class TaskPriority(Enum):
    """Priority levels for self-heal tasks."""
    CRITICAL = 1    # Must fix immediately
    HIGH = 2        # Fix soon
    MEDIUM = 3      # Fix when possible
    LOW = 4         # Nice to have
    DEFERRED = 5    # Postponed


class TaskStatus(Enum):
    """Status of a self-heal task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class TaskCategory(Enum):
    """Categories of self-heal tasks."""
    MISSING_FUNCTION = "missing_function"
    MISSING_FILE = "missing_file"
    MISSING_DIRECTORY = "missing_directory"
    BROKEN_IMPORT = "broken_import"
    CONFIG_ERROR = "config_error"
    DEPENDENCY_ISSUE = "dependency_issue"
    FEATURE_REQUEST = "feature_request"
    OPTIMIZATION = "optimization"


@dataclass
class SelfHealTask:
    """A self-healing task in the queue."""
    id: str
    title: str
    description: str
    category: TaskCategory
    priority: TaskPriority
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Implementation details
    target_file: str = ""
    target_function: str = ""
    implementation_plan: str = ""
    auto_fixable: bool = False
    
    # Execution tracking
    attempts: int = 0
    max_attempts: int = 3
    last_error: str = ""
    result: str = ""
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "target_file": self.target_file,
            "target_function": self.target_function,
            "implementation_plan": self.implementation_plan,
            "auto_fixable": self.auto_fixable,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "last_error": self.last_error,
            "result": self.result,
            "depends_on": self.depends_on,
            "blocks": self.blocks
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelfHealTask":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            category=TaskCategory(data["category"]),
            priority=TaskPriority(data["priority"]),
            status=TaskStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            target_file=data.get("target_file", ""),
            target_function=data.get("target_function", ""),
            implementation_plan=data.get("implementation_plan", ""),
            auto_fixable=data.get("auto_fixable", False),
            attempts=data.get("attempts", 0),
            max_attempts=data.get("max_attempts", 3),
            last_error=data.get("last_error", ""),
            result=data.get("result", ""),
            depends_on=data.get("depends_on", []),
            blocks=data.get("blocks", [])
        )


class SelfHealQueue:
    """
    Self-healing task queue for OmniMind.
    
    Features:
    - Queue tasks for missing functions/features
    - Priority-based execution
    - Dependency tracking
    - Auto-implementation on initialization
    - Persistent storage
    """
    
    def __init__(
        self,
        project_path: Path = None,
        auto_initialize: bool = True
    ):
        """
        Initialize self-heal queue.
        
        Args:
            project_path: Project root path
            auto_initialize: Whether to run initialization checks
        """
        self.project_path = project_path
        self._tasks: Dict[str, SelfHealTask] = {}
        self._next_id = 0
        self._handlers: Dict[TaskCategory, Callable] = {}
        
        # Setup storage
        if project_path:
            self.queue_dir = project_path / ".self_heal"
            ensure_directory(self.queue_dir)
            self.queue_file = self.queue_dir / "task_queue.json"
            self._load_from_disk()
        else:
            self.queue_dir = None

    def _generate_id(self) -> str:
        """Generate unique task ID."""
        self._next_id += 1
        return f"heal_{self._next_id:06d}"

    def _load_from_disk(self) -> None:
        """Load queue from disk."""
        try:
            if self.queue_file and self.queue_file.exists():
                data = read_json(self.queue_file)
                for task_data in data.get("tasks", []):
                    task = SelfHealTask.from_dict(task_data)
                    self._tasks[task.id] = task
                self._next_id = data.get("next_id", len(self._tasks))
                logger.info(f"Loaded {len(self._tasks)} self-heal tasks")
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")

    def _save_to_disk(self) -> None:
        """Save queue to disk."""
        try:
            if self.queue_file:
                data = {
                    "next_id": self._next_id,
                    "tasks": [t.to_dict() for t in self._tasks.values()]
                }
                write_json(self.queue_file, data)
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")

    # =========================================================================
    # TASK MANAGEMENT
    # =========================================================================

    def add_task(
        self,
        title: str,
        description: str,
        category: TaskCategory,
        priority: TaskPriority = TaskPriority.MEDIUM,
        target_file: str = "",
        target_function: str = "",
        auto_fixable: bool = False,
        implementation_plan: str = "",
        depends_on: List[str] = None
    ) -> SelfHealTask:
        """
        Add a new self-heal task.

        Args:
            title: Task title
            description: Task description
            category: Task category
            priority: Task priority
            target_file: Target file to fix
            target_function: Target function to implement
            auto_fixable: Whether task can be auto-fixed
            implementation_plan: Plan for implementation
            depends_on: List of task IDs this depends on

        Returns:
            Created SelfHealTask
        """
        task = SelfHealTask(
            id=self._generate_id(),
            title=title,
            description=description,
            category=category,
            priority=priority,
            target_file=target_file,
            target_function=target_function,
            auto_fixable=auto_fixable,
            implementation_plan=implementation_plan,
            depends_on=depends_on or []
        )

        self._tasks[task.id] = task
        self._save_to_disk()

        logger.info(f"Added self-heal task: {task.id} - {title}")
        return task

    def get_task(self, task_id: str) -> Optional[SelfHealTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_pending_tasks(self) -> List[SelfHealTask]:
        """Get all pending tasks sorted by priority."""
        pending = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
        return sorted(pending, key=lambda t: t.priority.value)

    def get_auto_fixable_tasks(self) -> List[SelfHealTask]:
        """Get all auto-fixable pending tasks."""
        return [
            t for t in self.get_pending_tasks()
            if t.auto_fixable and t.attempts < t.max_attempts
        ]

    def get_by_category(self, category: TaskCategory) -> List[SelfHealTask]:
        """Get tasks by category."""
        return [t for t in self._tasks.values() if t.category == category]

    def start_task(self, task_id: str) -> Optional[SelfHealTask]:
        """Mark a task as in progress."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now()
            task.updated_at = datetime.now()
            task.attempts += 1
            self._save_to_disk()
        return task

    def complete_task(self, task_id: str, result: str = "") -> Optional[SelfHealTask]:
        """Mark a task as completed."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.updated_at = datetime.now()
            task.result = result
            self._save_to_disk()
            logger.info(f"Completed self-heal task: {task_id}")
        return task

    def fail_task(self, task_id: str, error: str) -> Optional[SelfHealTask]:
        """Mark a task as failed."""
        task = self._tasks.get(task_id)
        if task:
            task.last_error = error
            task.updated_at = datetime.now()

            if task.attempts >= task.max_attempts:
                task.status = TaskStatus.FAILED
                logger.error(f"Self-heal task failed after {task.attempts} attempts: {task_id}")
            else:
                task.status = TaskStatus.PENDING  # Retry later
                logger.warning(f"Self-heal task attempt {task.attempts} failed: {task_id}")

            self._save_to_disk()
        return task

    def defer_task(self, task_id: str) -> Optional[SelfHealTask]:
        """Defer a task for later."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.DEFERRED
            task.updated_at = datetime.now()
            self._save_to_disk()
        return task

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.now()
            self._save_to_disk()
            return True
        return False

    # =========================================================================
    # INITIALIZATION CHECKS
    # =========================================================================

    def run_initialization_checks(self) -> List[SelfHealTask]:
        """
        Run initialization checks and queue tasks for missing features.

        Returns:
            List of newly created tasks
        """
        new_tasks = []

        # Check for required directories
        required_dirs = [
            ("world_bible", "World Bible directory"),
            ("story_documents", "Story documents directory"),
            ("storyboard_output", "Storyboard output directory"),
        ]

        if self.project_path:
            for dir_name, description in required_dirs:
                dir_path = self.project_path / dir_name
                if not dir_path.exists():
                    task = self.add_task(
                        title=f"Create {dir_name} directory",
                        description=f"Missing required directory: {description}",
                        category=TaskCategory.MISSING_DIRECTORY,
                        priority=TaskPriority.HIGH,
                        target_file=str(dir_path),
                        auto_fixable=True,
                        implementation_plan=f"Create directory: {dir_path}"
                    )
                    new_tasks.append(task)

        logger.info(f"Initialization check found {len(new_tasks)} issues")
        return new_tasks

    def register_handler(
        self,
        category: TaskCategory,
        handler: Callable[[SelfHealTask], bool]
    ) -> None:
        """Register a handler for a task category."""
        self._handlers[category] = handler

    async def process_auto_fixable(self) -> Dict[str, Any]:
        """
        Process all auto-fixable tasks.

        Returns:
            Dict with results
        """
        tasks = self.get_auto_fixable_tasks()
        fixed = []
        failed = []

        for task in tasks:
            self.start_task(task.id)

            try:
                handler = self._handlers.get(task.category)
                if handler:
                    success = handler(task)
                    if success:
                        self.complete_task(task.id, "Auto-fixed by handler")
                        fixed.append(task.id)
                    else:
                        self.fail_task(task.id, "Handler returned False")
                        failed.append(task.id)
                else:
                    # Default handling for missing directories
                    if task.category == TaskCategory.MISSING_DIRECTORY:
                        Path(task.target_file).mkdir(parents=True, exist_ok=True)
                        self.complete_task(task.id, "Directory created")
                        fixed.append(task.id)
                    else:
                        self.fail_task(task.id, "No handler registered")
                        failed.append(task.id)
            except Exception as e:
                self.fail_task(task.id, str(e))
                failed.append(task.id)

        return {
            "processed": len(tasks),
            "fixed": fixed,
            "failed": failed
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        by_status = {}
        by_category = {}
        by_priority = {}

        for task in self._tasks.values():
            st = task.status.value
            by_status[st] = by_status.get(st, 0) + 1
            cat = task.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            pri = task.priority.name
            by_priority[pri] = by_priority.get(pri, 0) + 1

        return {
            "total_tasks": len(self._tasks),
            "pending": len(self.get_pending_tasks()),
            "auto_fixable": len(self.get_auto_fixable_tasks()),
            "by_status": by_status,
            "by_category": by_category,
            "by_priority": by_priority
        }

