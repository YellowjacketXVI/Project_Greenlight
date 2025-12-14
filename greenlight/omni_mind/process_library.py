"""
Greenlight Process Library

Maps natural language commands to executable processes and protocols.
Enables OmniMind to trigger pipelines, tests, and system operations
through natural language understanding.

Usage:
    library = ProcessLibrary()
    process = library.match("run the writer pipeline")
    result = await library.execute(process)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable, Union
from enum import Enum
from pathlib import Path
import re
import asyncio
from datetime import datetime

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.process_library")


class ProcessCategory(Enum):
    """Categories of processes."""
    PIPELINE = "pipeline"
    TEST = "test"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    VALIDATION = "validation"
    SYSTEM = "system"
    DIAGNOSTIC = "diagnostic"


class ProcessStatus(Enum):
    """Status of a process execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProcessDefinition:
    """Definition of an executable process."""
    id: str
    name: str
    description: str
    category: ProcessCategory
    triggers: List[str]  # Natural language patterns that trigger this process
    handler: str  # Tool name or handler function name
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_project: bool = True
    requires_confirmation: bool = False
    estimated_duration: str = "unknown"
    tags: List[str] = field(default_factory=list)


@dataclass
class ProcessExecution:
    """Tracks a process execution."""
    id: str
    process_id: str
    status: ProcessStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    progress: float = 0.0
    logs: List[str] = field(default_factory=list)


class ProcessLibrary:
    """
    Library of executable processes triggered by natural language.
    
    Maps user intents to specific tools and pipelines, enabling
    OmniMind to execute complex operations through conversation.
    """
    
    def __init__(self):
        """Initialize the process library."""
        self._processes: Dict[str, ProcessDefinition] = {}
        self._executions: Dict[str, ProcessExecution] = {}
        self._tool_executor = None
        self._project_path: Optional[Path] = None
        
        self._register_default_processes()
        logger.info("ProcessLibrary initialized with default processes")
    
    def set_tool_executor(self, executor) -> None:
        """Set the tool executor for process execution."""
        self._tool_executor = executor
    
    def set_project(self, project_path: Path) -> None:
        """Set the current project path."""
        self._project_path = project_path
    
    def _register_default_processes(self) -> None:
        """Register all default processes."""
        # Pipeline processes
        self._register_pipeline_processes()
        # Test processes
        self._register_test_processes()
        # Analysis processes
        self._register_analysis_processes()
        # Diagnostic processes
        self._register_diagnostic_processes()
        # System processes
        self._register_system_processes()
    
    def _register_pipeline_processes(self) -> None:
        """Register pipeline-related processes."""
        self.register(ProcessDefinition(
            id="run_writer",
            name="Writer Pipeline",
            description="Run the Writer pipeline to generate story content from pitch",
            category=ProcessCategory.PIPELINE,
            triggers=[
                "run writer", "run the writer", "start writer pipeline",
                "generate story", "create story", "write the story",
                "run story pipeline", "execute writer"
            ],
            handler="run_writer",
            estimated_duration="2-5 minutes",
            tags=["story", "generation", "writer"]
        ))
        
        self.register(ProcessDefinition(
            id="run_director",
            name="Director Pipeline",
            description="Run the Director pipeline to create storyboard prompts",
            category=ProcessCategory.PIPELINE,
            triggers=[
                "run director", "run the director", "start director pipeline",
                "create storyboard", "generate prompts", "storyboard the story",
                "run shot pipeline", "execute director"
            ],
            handler="run_director",
            estimated_duration="3-8 minutes",
            tags=["storyboard", "prompts", "director"]
        ))
        
        self.register(ProcessDefinition(
            id="run_story_v2",
            name="Story Pipeline v2 (Assembly)",
            description="Run the Assembly-based Story Pipeline with 7-agent proposals",
            category=ProcessCategory.PIPELINE,
            triggers=[
                "run story v2", "run assembly pipeline", "7 agent story",
                "parallel story generation", "run story pipeline v2"
            ],
            handler="run_story_v2",
            parameters={"pipeline_mode": "assembly"},
            estimated_duration="5-10 minutes",
            tags=["story", "assembly", "parallel"]
        ))
        
        self.register(ProcessDefinition(
            id="run_world_bible",
            name="World Bible Pipeline",
            description="Generate world bible with character, location, and prop research",
            category=ProcessCategory.PIPELINE,
            triggers=[
                "run world bible", "generate world bible", "create world config",
                "research characters", "build world", "world bible pipeline"
            ],
            handler="run_world_bible",
            estimated_duration="3-6 minutes",
            tags=["world", "characters", "locations", "props"]
        ))
        
        self.register(ProcessDefinition(
            id="run_full_pipeline",
            name="Full Pipeline (Writer + Director)",
            description="Run complete pipeline: Writer then Director",
            category=ProcessCategory.PIPELINE,
            triggers=[
                "run full pipeline", "run everything", "complete pipeline",
                "writer and director", "full generation", "run all pipelines"
            ],
            handler="run_full_pipeline",
            requires_confirmation=True,
            estimated_duration="10-20 minutes",
            tags=["full", "complete", "all"]
        ))
    
    def _register_test_processes(self) -> None:
        """Register test-related processes."""
        self.register(ProcessDefinition(
            id="run_all_tests",
            name="Run All Tests",
            description="Run all pytest tests in the project",
            category=ProcessCategory.TEST,
            triggers=[
                "run tests", "run all tests", "execute tests",
                "test everything", "pytest", "run pytest"
            ],
            handler="run_tests",
            requires_project=False,
            estimated_duration="1-5 minutes",
            tags=["test", "pytest", "validation"]
        ))
        
        self.register(ProcessDefinition(
            id="run_pipeline_tests",
            name="Run Pipeline Tests",
            description="Run tests for pipeline modules",
            category=ProcessCategory.TEST,
            triggers=[
                "test pipelines", "run pipeline tests", "test story pipeline",
                "test director pipeline"
            ],
            handler="run_tests",
            parameters={"test_path": "tests/test_pipelines"},
            requires_project=False,
            estimated_duration="30-60 seconds",
            tags=["test", "pipeline"]
        ))
        
        self.register(ProcessDefinition(
            id="run_omni_mind_tests",
            name="Run OmniMind Tests",
            description="Run tests for OmniMind module",
            category=ProcessCategory.TEST,
            triggers=[
                "test omni mind", "run omni mind tests", "test assistant",
                "test omni"
            ],
            handler="run_tests",
            parameters={"test_path": "tests/test_omni_mind"},
            requires_project=False,
            estimated_duration="30-60 seconds",
            tags=["test", "omni_mind"]
        ))
        
        self.register(ProcessDefinition(
            id="run_core_tests",
            name="Run Core Tests",
            description="Run tests for core modules",
            category=ProcessCategory.TEST,
            triggers=[
                "test core", "run core tests", "test basics"
            ],
            handler="run_tests",
            parameters={"test_path": "tests/test_core"},
            requires_project=False,
            estimated_duration="20-40 seconds",
            tags=["test", "core"]
        ))
    
    def _register_analysis_processes(self) -> None:
        """Register analysis-related processes."""
        self.register(ProcessDefinition(
            id="analyze_project",
            name="Analyze Project",
            description="Analyze project structure, tags, and content",
            category=ProcessCategory.ANALYSIS,
            triggers=[
                "analyze project", "project analysis", "check project",
                "review project", "project status"
            ],
            handler="get_project_summary",
            estimated_duration="5-10 seconds",
            tags=["analysis", "project"]
        ))
        
        self.register(ProcessDefinition(
            id="analyze_tags",
            name="Analyze Tags",
            description="Analyze and validate all tags in the project",
            category=ProcessCategory.ANALYSIS,
            triggers=[
                "analyze tags", "check tags", "validate tags",
                "tag analysis", "review tags"
            ],
            handler="extract_tags",
            estimated_duration="30-60 seconds",
            tags=["analysis", "tags"]
        ))
        
        self.register(ProcessDefinition(
            id="find_missing_references",
            name="Find Missing References",
            description="Find tags without reference images",
            category=ProcessCategory.ANALYSIS,
            triggers=[
                "find missing references", "missing images", "check references",
                "what references are missing"
            ],
            handler="get_missing_references",
            estimated_duration="5-10 seconds",
            tags=["analysis", "references"]
        ))
    
    def _register_diagnostic_processes(self) -> None:
        """Register diagnostic processes."""
        self.register(ProcessDefinition(
            id="diagnose_all",
            name="Full Diagnostics",
            description="Run full project diagnostics",
            category=ProcessCategory.DIAGNOSTIC,
            triggers=[
                "diagnose", "run diagnostics", "check for issues",
                "find problems", "health check", "diagnose project"
            ],
            handler="diagnose_project",
            parameters={"target": "all"},
            estimated_duration="10-30 seconds",
            tags=["diagnostic", "health"]
        ))
        
        self.register(ProcessDefinition(
            id="self_heal",
            name="Self-Healing",
            description="Automatically detect and fix issues",
            category=ProcessCategory.DIAGNOSTIC,
            triggers=[
                "self heal", "auto fix", "fix issues", "heal project",
                "run self healing", "fix problems automatically"
            ],
            handler="run_self_healing",
            requires_confirmation=True,
            estimated_duration="30-120 seconds",
            tags=["diagnostic", "healing", "auto-fix"]
        ))
        
        self.register(ProcessDefinition(
            id="check_pipeline_status",
            name="Pipeline Status",
            description="Check status and availability of all pipelines",
            category=ProcessCategory.DIAGNOSTIC,
            triggers=[
                "pipeline status", "check pipelines", "what pipelines are available",
                "list pipelines", "show pipeline status"
            ],
            handler="get_pipeline_status",
            requires_project=False,
            estimated_duration="1-2 seconds",
            tags=["diagnostic", "pipeline"]
        ))

        # Notation validation processes
        self.register(ProcessDefinition(
            id="validate_notation",
            name="Validate Scene.Frame.Camera Notation",
            description="Validate scene.frame.camera notation in visual scripts (e.g., 1.2.cA)",
            category=ProcessCategory.VALIDATION,
            triggers=[
                "validate notation", "check notation", "validate frames",
                "check frame notation", "validate scene frame camera",
                "notation check", "verify notation"
            ],
            handler="validate_notation",
            estimated_duration="2-5 seconds",
            tags=["validation", "notation", "directing"]
        ))

        self.register(ProcessDefinition(
            id="fix_notation",
            name="Fix Old Notation Format",
            description="Convert old {frame_X.Y} notation to new [X.Y.cA] format",
            category=ProcessCategory.DIAGNOSTIC,
            triggers=[
                "fix notation", "convert notation", "update frame format",
                "fix frame notation", "convert old notation"
            ],
            handler="validate_notation",
            parameters={"auto_fix": True},
            requires_confirmation=True,
            estimated_duration="5-10 seconds",
            tags=["diagnostic", "notation", "auto-fix"]
        ))

        self.register(ProcessDefinition(
            id="parse_notation",
            name="Parse Notation",
            description="Parse a scene.frame.camera notation string (e.g., 1.2.cA → scene=1, frame=2, camera=A)",
            category=ProcessCategory.ANALYSIS,
            triggers=[
                "parse notation", "decode notation", "explain notation",
                "what does notation mean", "parse frame id"
            ],
            handler="parse_notation",
            estimated_duration="instant",
            tags=["analysis", "notation"]
        ))

    def _register_system_processes(self) -> None:
        """Register system processes."""
        self.register(ProcessDefinition(
            id="list_processes",
            name="List Available Processes",
            description="List all available processes and commands",
            category=ProcessCategory.SYSTEM,
            triggers=[
                "list processes", "what can you do", "show commands",
                "available processes", "help", "list commands"
            ],
            handler="list_processes",
            requires_project=False,
            estimated_duration="instant",
            tags=["system", "help"]
        ))
        
        self.register(ProcessDefinition(
            id="show_project_info",
            name="Show Project Info",
            description="Display current project information",
            category=ProcessCategory.SYSTEM,
            triggers=[
                "project info", "show project", "current project",
                "what project", "project details"
            ],
            handler="get_project_info",
            estimated_duration="instant",
            tags=["system", "project"]
        ))
    
    def register(self, process: ProcessDefinition) -> None:
        """Register a process definition."""
        self._processes[process.id] = process
        logger.debug(f"Registered process: {process.id}")
    
    def get(self, process_id: str) -> Optional[ProcessDefinition]:
        """Get a process by ID."""
        return self._processes.get(process_id)
    
    def list_all(self) -> List[ProcessDefinition]:
        """List all registered processes."""
        return list(self._processes.values())
    
    def list_by_category(self, category: ProcessCategory) -> List[ProcessDefinition]:
        """List processes by category."""
        return [p for p in self._processes.values() if p.category == category]
    
    def match(self, text: str) -> Optional[ProcessDefinition]:
        """
        Match natural language text to a process.
        
        Args:
            text: Natural language input
            
        Returns:
            Matched ProcessDefinition or None
        """
        text_lower = text.lower().strip()
        
        best_match = None
        best_score = 0
        
        for process in self._processes.values():
            for trigger in process.triggers:
                # Exact match
                if trigger in text_lower:
                    score = len(trigger)
                    if score > best_score:
                        best_score = score
                        best_match = process
                
                # Fuzzy match - check if all words in trigger are in text
                trigger_words = set(trigger.split())
                text_words = set(text_lower.split())
                if trigger_words.issubset(text_words):
                    score = len(trigger_words) * 2
                    if score > best_score:
                        best_score = score
                        best_match = process
        
        if best_match:
            logger.info(f"Matched '{text}' to process: {best_match.id}")
        
        return best_match
    
    async def execute(
        self,
        process: ProcessDefinition,
        parameters: Dict[str, Any] = None,
        progress_callback: Callable[[float, str], None] = None
    ) -> ProcessExecution:
        """
        Execute a process.
        
        Args:
            process: Process to execute
            parameters: Override parameters
            progress_callback: Callback for progress updates
            
        Returns:
            ProcessExecution with results
        """
        import uuid
        
        execution_id = str(uuid.uuid4())[:8]
        execution = ProcessExecution(
            id=execution_id,
            process_id=process.id,
            status=ProcessStatus.RUNNING,
            started_at=datetime.now()
        )
        self._executions[execution_id] = execution
        
        # Check requirements
        if process.requires_project and not self._project_path:
            execution.status = ProcessStatus.FAILED
            execution.error = "No project loaded"
            execution.completed_at = datetime.now()
            return execution
        
        # Merge parameters
        params = {**process.parameters, **(parameters or {})}
        
        try:
            if progress_callback:
                progress_callback(0.1, f"Starting {process.name}...")
            
            execution.logs.append(f"Starting {process.name}")
            
            # Execute via tool executor
            if self._tool_executor:
                result = self._tool_executor.execute(process.handler, **params)
                
                if result.success:
                    execution.status = ProcessStatus.COMPLETED
                    execution.result = result.result
                    execution.logs.append(f"Completed successfully")
                else:
                    execution.status = ProcessStatus.FAILED
                    execution.error = result.error
                    execution.logs.append(f"Failed: {result.error}")
            else:
                execution.status = ProcessStatus.FAILED
                execution.error = "Tool executor not available"
            
            if progress_callback:
                progress_callback(1.0, f"Completed {process.name}")
                
        except Exception as e:
            execution.status = ProcessStatus.FAILED
            execution.error = str(e)
            execution.logs.append(f"Error: {e}")
            logger.error(f"Process execution failed: {e}")
        
        execution.completed_at = datetime.now()
        execution.progress = 1.0
        
        return execution
    
    def get_execution(self, execution_id: str) -> Optional[ProcessExecution]:
        """Get an execution by ID."""
        return self._executions.get(execution_id)
    
    def get_recent_executions(self, limit: int = 10) -> List[ProcessExecution]:
        """Get recent executions."""
        executions = sorted(
            self._executions.values(),
            key=lambda e: e.started_at,
            reverse=True
        )
        return executions[:limit]
    
    def format_process_list(self) -> str:
        """Format a human-readable list of processes."""
        lines = ["## Available Processes\n"]
        
        by_category: Dict[ProcessCategory, List[ProcessDefinition]] = {}
        for process in self._processes.values():
            if process.category not in by_category:
                by_category[process.category] = []
            by_category[process.category].append(process)
        
        for category in ProcessCategory:
            if category in by_category:
                lines.append(f"\n### {category.value.title()}\n")
                for process in by_category[category]:
                    triggers = ", ".join(f'"{t}"' for t in process.triggers[:3])
                    lines.append(f"- **{process.name}**: {process.description}")
                    lines.append(f"  - Triggers: {triggers}")
                    lines.append(f"  - Duration: {process.estimated_duration}")
        
        return "\n".join(lines)

