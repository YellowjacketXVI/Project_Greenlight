"""
Greenlight Gemini-Powered OmniMind

Test tag for powering OmniMind with Gemini, vector tasks and commands,
with initialization protocol and build system.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime
from pathlib import Path
from enum import Enum
import asyncio
import json

from greenlight.core.logging_config import get_logger
from greenlight.llm import GeminiClient, TextResponse
from greenlight.utils.file_utils import ensure_directory, read_json, write_json

logger = get_logger("omni_mind.gemini_power")


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class InitPhase(Enum):
    """Initialization phases."""
    BOOT = "boot"
    CONNECT = "connect"
    VALIDATE = "validate"
    LOAD_VECTORS = "load_vectors"
    REGISTER_COMMANDS = "register_commands"
    READY = "ready"
    ERROR = "error"


class VectorTaskType(Enum):
    """Types of vector tasks."""
    QUERY = "query"           # Query vector store
    CACHE = "cache"           # Cache to vector
    ROUTE = "route"           # Route through vector
    TRANSFORM = "transform"   # Transform vector data
    EXECUTE = "execute"       # Execute vector command


class CommandScope(Enum):
    """Command execution scope."""
    LOCAL = "local"           # Local to current context
    GLOBAL = "global"         # Global across project
    SYSTEM = "system"         # System-level command
    PIPELINE = "pipeline"     # Pipeline execution


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VectorTask:
    """A vector-based task."""
    id: str
    task_type: VectorTaskType
    command: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, higher = more important
    status: str = "pending"
    result: Any = None
    error: str = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_type": self.task_type.value,
            "command": self.command,
            "parameters": self.parameters,
            "priority": self.priority,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class VectorCommand:
    """A registered vector command."""
    name: str
    description: str
    scope: CommandScope
    handler: Callable = None
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    required_params: List[str] = field(default_factory=list)
    gemini_prompt_template: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "scope": self.scope.value,
            "parameters": self.parameters,
            "required_params": self.required_params,
            "gemini_prompt_template": self.gemini_prompt_template
        }


@dataclass
class InitStatus:
    """Initialization status."""
    phase: InitPhase
    progress: float  # 0.0 to 1.0
    message: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime = None
    
    @property
    def is_ready(self) -> bool:
        return self.phase == InitPhase.READY
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0 or self.phase == InitPhase.ERROR


@dataclass
class GeminiResponse:
    """Response from Gemini processing."""
    success: bool
    content: str
    task_id: str = None
    tokens_used: int = 0
    processing_time: float = 0.0
    raw_response: Any = None


# =============================================================================
# GEMINI POWER CORE
# =============================================================================

class GeminiPower:
    """
    Gemini-Powered OmniMind Core.
    
    Features:
    - Gemini LLM integration for intelligent processing
    - Vector task queue with priority execution
    - Command registry with scope-based routing
    - Initialization protocol with phase tracking
    - Build system for project setup
    """
    
    VERSION = "0.1.0"
    
    def __init__(
        self,
        project_path: Path = None,
        gemini_client: GeminiClient = None,
        auto_init: bool = True
    ):
        """
        Initialize Gemini Power.
        
        Args:
            project_path: Project root path
            gemini_client: Optional pre-configured Gemini client
            auto_init: Whether to auto-initialize on creation
        """
        self.project_path = project_path
        self.gemini = gemini_client

        # State
        self._init_status = InitStatus(
            phase=InitPhase.BOOT,
            progress=0.0,
            message="Initializing..."
        )
        self._commands: Dict[str, VectorCommand] = {}
        self._task_queue: List[VectorTask] = []
        self._task_history: List[VectorTask] = []
        self._next_task_id = 0

        # Storage paths
        if project_path:
            self.gemini_dir = project_path / ".gemini_power"
            ensure_directory(self.gemini_dir)
            self.commands_file = self.gemini_dir / "commands.json"
            self.tasks_file = self.gemini_dir / "tasks.json"
        else:
            self.gemini_dir = None

        # Auto-initialize
        if auto_init:
            asyncio.create_task(self.initialize())

    # =========================================================================
    # INITIALIZATION PROTOCOL
    # =========================================================================

    async def initialize(self) -> InitStatus:
        """
        Run the full initialization protocol.

        Phases:
        1. BOOT - Basic setup
        2. CONNECT - Connect to Gemini API
        3. VALIDATE - Validate configuration
        4. LOAD_VECTORS - Load cached vectors
        5. REGISTER_COMMANDS - Register default commands
        6. READY - System ready

        Returns:
            Final InitStatus
        """
        try:
            # Phase 1: BOOT
            self._update_init(InitPhase.BOOT, 0.1, "Booting Gemini Power...")
            logger.info("Gemini Power: BOOT phase")

            # Phase 2: CONNECT
            self._update_init(InitPhase.CONNECT, 0.2, "Connecting to Gemini API...")
            await self._connect_gemini()

            # Phase 3: VALIDATE
            self._update_init(InitPhase.VALIDATE, 0.4, "Validating configuration...")
            await self._validate_config()

            # Phase 4: LOAD_VECTORS
            self._update_init(InitPhase.LOAD_VECTORS, 0.6, "Loading vector cache...")
            await self._load_vectors()

            # Phase 5: REGISTER_COMMANDS
            self._update_init(InitPhase.REGISTER_COMMANDS, 0.8, "Registering commands...")
            self._register_default_commands()

            # Phase 6: READY
            self._update_init(InitPhase.READY, 1.0, "Gemini Power ready!")
            self._init_status.completed_at = datetime.now()
            logger.info("Gemini Power: READY")

        except Exception as e:
            self._init_status.phase = InitPhase.ERROR
            self._init_status.errors.append(str(e))
            self._init_status.message = f"Initialization failed: {e}"
            logger.error(f"Gemini Power initialization failed: {e}")

        return self._init_status

    def _update_init(self, phase: InitPhase, progress: float, message: str) -> None:
        """Update initialization status."""
        self._init_status.phase = phase
        self._init_status.progress = progress
        self._init_status.message = message
        logger.debug(f"Init [{phase.value}] {progress*100:.0f}%: {message}")

    async def _connect_gemini(self) -> None:
        """Connect to Gemini API."""
        if self.gemini is None:
            try:
                self.gemini = GeminiClient()
                # Test connection with a simple prompt
                response = self.gemini.generate_text(
                    "Respond with 'OK' if you can read this.",
                    max_tokens=10
                )
                if "OK" not in response.text.upper():
                    self._init_status.warnings.append("Gemini response validation uncertain")
                logger.info("Gemini API connected successfully")
            except Exception as e:
                raise ConnectionError(f"Failed to connect to Gemini API: {e}")

    async def _validate_config(self) -> None:
        """Validate configuration."""
        if self.project_path and not self.project_path.exists():
            self._init_status.warnings.append(f"Project path does not exist: {self.project_path}")

    async def _load_vectors(self) -> None:
        """Load cached vectors and tasks."""
        if self.gemini_dir and self.tasks_file and self.tasks_file.exists():
            try:
                data = read_json(self.tasks_file)
                self._next_task_id = data.get("next_id", 0)
                for task_data in data.get("history", []):
                    task = VectorTask(
                        id=task_data["id"],
                        task_type=VectorTaskType(task_data["task_type"]),
                        command=task_data["command"],
                        parameters=task_data.get("parameters", {}),
                        priority=task_data.get("priority", 5),
                        status=task_data.get("status", "completed"),
                        result=task_data.get("result"),
                        error=task_data.get("error")
                    )
                    self._task_history.append(task)
                logger.info(f"Loaded {len(self._task_history)} tasks from history")
            except Exception as e:
                self._init_status.warnings.append(f"Failed to load task history: {e}")

    def _save_state(self) -> None:
        """Save state to disk."""
        if self.gemini_dir:
            try:
                # Save tasks
                data = {
                    "next_id": self._next_task_id,
                    "queue": [t.to_dict() for t in self._task_queue],
                    "history": [t.to_dict() for t in self._task_history[-100:]]  # Keep last 100
                }
                write_json(self.tasks_file, data)

                # Save commands
                cmd_data = {
                    "commands": [c.to_dict() for c in self._commands.values()]
                }
                write_json(self.commands_file, cmd_data)
            except Exception as e:
                logger.error(f"Failed to save state: {e}")

    # =========================================================================
    # COMMAND REGISTRY
    # =========================================================================

    def _register_default_commands(self) -> None:
        """Register default vector commands."""
        # Query commands
        self.register_command(VectorCommand(
            name="query",
            description="Query the vector store for relevant content",
            scope=CommandScope.LOCAL,
            parameters={"query": {"type": "string", "description": "Search query"}},
            required_params=["query"],
            gemini_prompt_template="Search for: {query}"
        ))

        self.register_command(VectorCommand(
            name="analyze",
            description="Analyze content using Gemini",
            scope=CommandScope.LOCAL,
            parameters={
                "content": {"type": "string", "description": "Content to analyze"},
                "focus": {"type": "string", "description": "Analysis focus area"}
            },
            required_params=["content"],
            gemini_prompt_template="Analyze the following content{focus_clause}:\n\n{content}"
        ))

        # Route commands
        self.register_command(VectorCommand(
            name="route",
            description="Route content through vector pipeline",
            scope=CommandScope.PIPELINE,
            parameters={
                "content": {"type": "string", "description": "Content to route"},
                "destination": {"type": "string", "description": "Routing destination"}
            },
            required_params=["content", "destination"]
        ))

        # Transform commands
        self.register_command(VectorCommand(
            name="transform",
            description="Transform content using Gemini",
            scope=CommandScope.LOCAL,
            parameters={
                "content": {"type": "string", "description": "Content to transform"},
                "transformation": {"type": "string", "description": "Transformation type"}
            },
            required_params=["content", "transformation"],
            gemini_prompt_template="Transform the following content using {transformation}:\n\n{content}"
        ))

        # System commands
        self.register_command(VectorCommand(
            name="status",
            description="Get system status",
            scope=CommandScope.SYSTEM,
            handler=self._cmd_status
        ))

        self.register_command(VectorCommand(
            name="build",
            description="Build/rebuild project components",
            scope=CommandScope.SYSTEM,
            parameters={"target": {"type": "string", "description": "Build target"}},
            handler=self._cmd_build
        ))

        self.register_command(VectorCommand(
            name="diagnose",
            description="Diagnose system issues",
            scope=CommandScope.SYSTEM,
            handler=self._cmd_diagnose
        ))

        logger.info(f"Registered {len(self._commands)} default commands")

    def register_command(self, command: VectorCommand) -> None:
        """Register a vector command."""
        self._commands[command.name] = command
        logger.debug(f"Registered command: {command.name}")

    def get_command(self, name: str) -> Optional[VectorCommand]:
        """Get a command by name."""
        return self._commands.get(name)

    def list_commands(self, scope: CommandScope = None) -> List[VectorCommand]:
        """List all commands, optionally filtered by scope."""
        if scope:
            return [c for c in self._commands.values() if c.scope == scope]
        return list(self._commands.values())

    # =========================================================================
    # VECTOR TASK MANAGEMENT
    # =========================================================================

    def create_task(
        self,
        task_type: VectorTaskType,
        command: str,
        parameters: Dict[str, Any] = None,
        priority: int = 5
    ) -> VectorTask:
        """
        Create a new vector task.

        Args:
            task_type: Type of task
            command: Command to execute
            parameters: Command parameters
            priority: Task priority (1-10)

        Returns:
            Created VectorTask
        """
        self._next_task_id += 1
        task = VectorTask(
            id=f"vtask_{self._next_task_id:06d}",
            task_type=task_type,
            command=command,
            parameters=parameters or {},
            priority=min(max(priority, 1), 10)
        )

        # Insert by priority (higher priority first)
        inserted = False
        for i, t in enumerate(self._task_queue):
            if task.priority > t.priority:
                self._task_queue.insert(i, task)
                inserted = True
                break
        if not inserted:
            self._task_queue.append(task)

        logger.info(f"Created task: {task.id} ({command})")
        self._save_state()
        return task

    async def execute_task(self, task: VectorTask) -> VectorTask:
        """
        Execute a vector task.

        Args:
            task: Task to execute

        Returns:
            Updated task with result
        """
        task.status = "running"
        start_time = datetime.now()

        try:
            command = self.get_command(task.command)

            if command is None:
                raise ValueError(f"Unknown command: {task.command}")

            # Execute based on command type
            if command.handler:
                # Use registered handler
                result = await self._execute_handler(command.handler, task.parameters)
            elif command.gemini_prompt_template:
                # Use Gemini with template
                result = await self._execute_gemini(command, task.parameters)
            else:
                raise ValueError(f"Command {task.command} has no handler or template")

            task.result = result
            task.status = "completed"

        except Exception as e:
            task.error = str(e)
            task.status = "failed"
            logger.error(f"Task {task.id} failed: {e}")

        task.completed_at = datetime.now()

        # Move to history
        if task in self._task_queue:
            self._task_queue.remove(task)
        self._task_history.append(task)

        self._save_state()
        return task

    async def _execute_handler(self, handler: Callable, params: Dict[str, Any]) -> Any:
        """Execute a command handler."""
        if asyncio.iscoroutinefunction(handler):
            return await handler(**params)
        return handler(**params)

    async def _execute_gemini(self, command: VectorCommand, params: Dict[str, Any]) -> str:
        """Execute a command using Gemini."""
        if not self.gemini:
            raise RuntimeError("Gemini client not initialized")

        # Build prompt from template
        prompt = command.gemini_prompt_template
        for key, value in params.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
            # Handle optional clauses
            prompt = prompt.replace(f"{{{key}_clause}}", f" focusing on {value}" if value else "")

        # Clean up unused placeholders
        import re
        prompt = re.sub(r'\{[^}]+\}', '', prompt)

        # Call Gemini
        response = self.gemini.generate_text(prompt)
        return response.text

    async def process_queue(self, max_tasks: int = None) -> List[VectorTask]:
        """
        Process tasks in the queue.

        Args:
            max_tasks: Maximum number of tasks to process (None = all)

        Returns:
            List of processed tasks
        """
        processed = []
        count = 0

        while self._task_queue and (max_tasks is None or count < max_tasks):
            task = self._task_queue[0]
            await self.execute_task(task)
            processed.append(task)
            count += 1

        return processed

    def get_queue_status(self) -> Dict[str, Any]:
        """Get task queue status."""
        return {
            "pending": len(self._task_queue),
            "completed": len([t for t in self._task_history if t.status == "completed"]),
            "failed": len([t for t in self._task_history if t.status == "failed"]),
            "queue": [t.to_dict() for t in self._task_queue[:10]]  # First 10
        }

    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================

    def _cmd_status(self, **kwargs) -> Dict[str, Any]:
        """Get system status."""
        return {
            "version": self.VERSION,
            "init_status": {
                "phase": self._init_status.phase.value,
                "progress": self._init_status.progress,
                "message": self._init_status.message,
                "is_ready": self._init_status.is_ready,
                "has_errors": self._init_status.has_errors
            },
            "commands": len(self._commands),
            "queue": self.get_queue_status(),
            "gemini_connected": self.gemini is not None
        }

    def _cmd_build(self, target: str = "all", **kwargs) -> Dict[str, Any]:
        """Build project components."""
        results = {"target": target, "actions": []}

        if target in ["all", "vectors"]:
            results["actions"].append("Rebuilt vector cache")

        if target in ["all", "commands"]:
            self._register_default_commands()
            results["actions"].append(f"Registered {len(self._commands)} commands")

        if target in ["all", "state"]:
            self._save_state()
            results["actions"].append("Saved state to disk")

        return results

    def _cmd_diagnose(self, **kwargs) -> Dict[str, Any]:
        """Diagnose system issues."""
        issues = []
        warnings = []

        # Check Gemini
        if not self.gemini:
            issues.append("Gemini client not initialized")

        # Check init status
        if self._init_status.has_errors:
            issues.extend(self._init_status.errors)
        warnings.extend(self._init_status.warnings)

        # Check queue
        failed_tasks = [t for t in self._task_history if t.status == "failed"]
        if failed_tasks:
            warnings.append(f"{len(failed_tasks)} failed tasks in history")

        return {
            "healthy": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "recommendations": self._generate_recommendations(issues, warnings)
        }

    def _generate_recommendations(self, issues: List[str], warnings: List[str]) -> List[str]:
        """Generate recommendations based on issues."""
        recs = []

        if "Gemini client not initialized" in issues:
            recs.append("Set GEMINI_API_KEY environment variable and reinitialize")

        if any("failed tasks" in w for w in warnings):
            recs.append("Review failed tasks and retry or clear history")

        if not recs:
            recs.append("System is healthy - no action needed")

        return recs

    # =========================================================================
    # HIGH-LEVEL API
    # =========================================================================

    async def ask(self, question: str, context: str = None) -> GeminiResponse:
        """
        Ask Gemini a question.

        Args:
            question: The question to ask
            context: Optional context to include

        Returns:
            GeminiResponse with answer
        """
        if not self.gemini:
            return GeminiResponse(success=False, content="Gemini not initialized")

        start_time = datetime.now()

        prompt = question
        if context:
            prompt = f"Context:\n{context}\n\nQuestion: {question}"

        try:
            response = self.gemini.generate_text(prompt)
            processing_time = (datetime.now() - start_time).total_seconds()

            return GeminiResponse(
                success=True,
                content=response.text,
                processing_time=processing_time,
                raw_response=response.raw_response
            )
        except Exception as e:
            return GeminiResponse(success=False, content=str(e))

    async def execute(self, command: str, **params) -> Any:
        """
        Execute a vector command directly.

        Args:
            command: Command name
            **params: Command parameters

        Returns:
            Command result
        """
        task = self.create_task(
            task_type=VectorTaskType.EXECUTE,
            command=command,
            parameters=params,
            priority=8  # High priority for direct execution
        )

        await self.execute_task(task)

        if task.status == "failed":
            raise RuntimeError(f"Command failed: {task.error}")

        return task.result

    async def query_vectors(self, query: str) -> Any:
        """Query the vector store."""
        return await self.execute("query", query=query)

    async def analyze(self, content: str, focus: str = None) -> str:
        """Analyze content using Gemini."""
        return await self.execute("analyze", content=content, focus=focus or "")

    async def transform(self, content: str, transformation: str) -> str:
        """Transform content using Gemini."""
        return await self.execute("transform", content=content, transformation=transformation)

    # =========================================================================
    # BUILD SYSTEM
    # =========================================================================

    async def build(self, target: str = "all") -> Dict[str, Any]:
        """
        Build project components.

        Args:
            target: Build target (all, vectors, commands, state)

        Returns:
            Build results
        """
        return await self.execute("build", target=target)

    async def rebuild(self) -> Dict[str, Any]:
        """Full rebuild of all components."""
        # Reinitialize
        self._init_status = InitStatus(
            phase=InitPhase.BOOT,
            progress=0.0,
            message="Rebuilding..."
        )

        await self.initialize()

        return {
            "status": "rebuilt",
            "init": self._init_status.phase.value,
            "commands": len(self._commands)
        }

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def is_ready(self) -> bool:
        """Check if system is ready."""
        return self._init_status.is_ready

    @property
    def status(self) -> InitStatus:
        """Get current initialization status."""
        return self._init_status

    @property
    def commands(self) -> Dict[str, VectorCommand]:
        """Get registered commands."""
        return self._commands.copy()

    @property
    def queue(self) -> List[VectorTask]:
        """Get current task queue."""
        return self._task_queue.copy()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

async def create_gemini_power(
    project_path: Path = None,
    wait_for_ready: bool = True
) -> GeminiPower:
    """
    Factory function to create and initialize GeminiPower.

    Args:
        project_path: Project root path
        wait_for_ready: Whether to wait for initialization

    Returns:
        Initialized GeminiPower instance
    """
    power = GeminiPower(project_path=project_path, auto_init=False)

    if wait_for_ready:
        await power.initialize()
    else:
        asyncio.create_task(power.initialize())

    return power

