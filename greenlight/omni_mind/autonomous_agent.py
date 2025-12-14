"""
OmniMind Autonomous Agent

Self-tasking agent that can plan, execute, and validate complex multi-step operations.
Uses Gemini 2.5 as the default processing LLM for task planning and execution.

Key Capabilities:
- Self-tasking: Creates and manages sub-tasks autonomously
- Image Analysis: Submits images to Gemini for structured analysis
- Image Editing: Uses Nano Banana Pro with template prefixes
- Character Updates: Propagates changes across all project documents
- Storyboard Management: Finds and regenerates frames by character
- Validation: Verifies changes using image analysis
"""

from __future__ import annotations

import json
import asyncio
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.autonomous")


class TaskStatus(Enum):
    """Status of an autonomous task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"  # Waiting for dependency
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Priority levels for tasks."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class AutonomousTask:
    """A task that OmniMind can execute autonomously."""
    id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    parent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    subtasks: List[str] = field(default_factory=list)
    tool_name: Optional[str] = None
    tool_params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "parent_id": self.parent_id,
            "dependencies": self.dependencies,
            "subtasks": self.subtasks,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
        }


@dataclass
class ImageAnalysisResult:
    """Result from image analysis."""
    success: bool
    description: str = ""
    characters_detected: List[str] = field(default_factory=list)
    character_details: Dict[str, Dict[str, str]] = field(default_factory=dict)
    locations_detected: List[str] = field(default_factory=list)
    props_detected: List[str] = field(default_factory=list)
    style_analysis: Dict[str, str] = field(default_factory=dict)
    symbolic_notation: str = ""
    raw_response: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "description": self.description,
            "characters_detected": self.characters_detected,
            "character_details": self.character_details,
            "locations_detected": self.locations_detected,
            "props_detected": self.props_detected,
            "style_analysis": self.style_analysis,
            "symbolic_notation": self.symbolic_notation,
            "error": self.error,
        }


@dataclass
class CharacterModificationRequest:
    """Request to modify a character across the project."""
    character_tag: str
    modifications: Dict[str, str]  # field -> new_value
    update_references: bool = True
    regenerate_storyboard: bool = True
    validate_changes: bool = True


class AutonomousTaskManager:
    """
    Manages autonomous task execution for OmniMind.
    
    Uses Gemini 2.5 as the default LLM for:
    - Task planning and decomposition
    - Image analysis with structured output
    - Validation of completed tasks
    """
    
    def __init__(
        self,
        project_path: Optional[Path] = None,
        tool_executor: Optional[Any] = None,
        llm_model: str = "gemini-2.5-flash"
    ):
        self.project_path = Path(project_path) if project_path else None
        self.tool_executor = tool_executor
        self.llm_model = llm_model
        
        self._tasks: Dict[str, AutonomousTask] = {}
        self._task_counter = 0
        self._execution_history: List[Dict[str, Any]] = []
        self._pending_generations: Dict[str, str] = {}  # frame_id -> status
        
        # Callbacks
        self._on_task_update: Optional[Callable[[AutonomousTask], None]] = None
        self._on_task_complete: Optional[Callable[[AutonomousTask], None]] = None
        
        logger.info(f"AutonomousTaskManager initialized with LLM: {llm_model}")

    def set_project(self, project_path: Path) -> None:
        """Set the current project path."""
        self.project_path = Path(project_path) if project_path else None

    def set_tool_executor(self, executor: Any) -> None:
        """Set the tool executor for task execution."""
        self.tool_executor = executor

    def set_callbacks(
        self,
        on_update: Optional[Callable[[AutonomousTask], None]] = None,
        on_complete: Optional[Callable[[AutonomousTask], None]] = None
    ) -> None:
        """Set callbacks for task events."""
        self._on_task_update = on_update
        self._on_task_complete = on_complete

    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        self._task_counter += 1
        return f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._task_counter:04d}"

    # =========================================================================
    # TASK MANAGEMENT
    # =========================================================================

    def create_task(
        self,
        name: str,
        description: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        parent_id: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        tool_name: Optional[str] = None,
        tool_params: Optional[Dict[str, Any]] = None
    ) -> AutonomousTask:
        """Create a new autonomous task."""
        task = AutonomousTask(
            id=self._generate_task_id(),
            name=name,
            description=description,
            priority=priority,
            parent_id=parent_id,
            dependencies=dependencies or [],
            tool_name=tool_name,
            tool_params=tool_params or {}
        )
        self._tasks[task.id] = task

        # Add to parent's subtasks if applicable
        if parent_id and parent_id in self._tasks:
            self._tasks[parent_id].subtasks.append(task.id)

        logger.info(f"Created task: {task.id} - {name}")
        return task

    def get_task(self, task_id: str) -> Optional[AutonomousTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[AutonomousTask]:
        """Get all tasks."""
        return list(self._tasks.values())

    def get_pending_tasks(self) -> List[AutonomousTask]:
        """Get all pending tasks sorted by priority."""
        pending = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
        return sorted(pending, key=lambda t: t.priority.value)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Any] = None,
        error: Optional[str] = None
    ) -> bool:
        """Update a task's status."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = status
        if status == TaskStatus.IN_PROGRESS:
            task.started_at = datetime.now()
        elif status in (TaskStatus.COMPLETE, TaskStatus.FAILED):
            task.completed_at = datetime.now()
            task.result = result
            task.error = error

        if self._on_task_update:
            self._on_task_update(task)

        if status == TaskStatus.COMPLETE and self._on_task_complete:
            self._on_task_complete(task)

        return True

    def can_execute_task(self, task_id: str) -> bool:
        """Check if a task can be executed (all dependencies complete)."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status != TaskStatus.PENDING:
            return False

        # Check all dependencies are complete
        for dep in task.dependencies:
            # Try to find dependency by ID first
            dep_task = self._tasks.get(dep)

            # If not found by ID, try to find by name
            if not dep_task:
                for t in self._tasks.values():
                    if t.name == dep or t.name.lower() == dep.lower():
                        dep_task = t
                        break

            if not dep_task or dep_task.status != TaskStatus.COMPLETE:
                return False

        return True

    async def execute_task(self, task_id: str) -> bool:
        """Execute a single task."""
        task = self._tasks.get(task_id)
        if not task:
            logger.error(f"Task not found: {task_id}")
            return False

        if not self.can_execute_task(task_id):
            logger.warning(f"Task cannot be executed yet: {task_id}")
            return False

        self.update_task_status(task_id, TaskStatus.IN_PROGRESS)
        logger.info(f"Executing task: {task.name}")

        try:
            if task.tool_name and self.tool_executor:
                # Execute via tool executor
                result = self.tool_executor.execute(task.tool_name, **task.tool_params)
                if result.success:
                    self.update_task_status(task_id, TaskStatus.COMPLETE, result=result.result)
                    return True
                else:
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        task.status = TaskStatus.PENDING
                        logger.warning(f"Task failed, retrying ({task.retry_count}/{task.max_retries})")
                        return False
                    self.update_task_status(task_id, TaskStatus.FAILED, error=result.error)
                    return False
            else:
                # No tool specified - mark as complete (manual task)
                self.update_task_status(task_id, TaskStatus.COMPLETE)
                return True

        except Exception as e:
            logger.error(f"Task execution error: {e}")
            self.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
            return False

    async def execute_all_pending(self) -> Dict[str, Any]:
        """Execute all pending tasks in dependency order."""
        executed = []
        failed = []

        while True:
            # Find tasks that can be executed
            executable = [t for t in self.get_pending_tasks() if self.can_execute_task(t.id)]
            if not executable:
                break

            # Execute in parallel where possible
            for task in executable:
                success = await self.execute_task(task.id)
                if success:
                    executed.append(task.id)
                else:
                    failed.append(task.id)

        return {
            "executed": executed,
            "failed": failed,
            "pending": [t.id for t in self.get_pending_tasks()]
        }

    # =========================================================================
    # IMAGE ANALYSIS (Gemini 2.5)
    # =========================================================================

    async def analyze_image(
        self,
        image_path: Path,
        analysis_type: str = "full",
        context: Optional[Dict[str, Any]] = None
    ) -> ImageAnalysisResult:
        """
        Analyze an image using Gemini 2.5 for structured output.

        Args:
            image_path: Path to the image file
            analysis_type: Type of analysis - 'full', 'character', 'scene', 'validation'
            context: Additional context (e.g., expected character, modifications to validate)

        Returns:
            ImageAnalysisResult with structured analysis
        """
        import os
        from urllib import request as url_request

        if not image_path.exists():
            return ImageAnalysisResult(success=False, error=f"Image not found: {image_path}")

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return ImageAnalysisResult(success=False, error="GOOGLE_API_KEY not set")

        # Build analysis prompt based on type
        prompt = self._build_analysis_prompt(analysis_type, context)

        # Encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("ascii")

        suffix = image_path.suffix.lower()
        mime_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix.lstrip("."), "image/jpeg")

        # Call Gemini 2.5
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.llm_model}:generateContent"

        body = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_data}}
                ]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096
            }
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        try:
            req = url_request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
            with url_request.urlopen(req, timeout=60) as resp:
                response_data = json.loads(resp.read().decode())

            # Parse response
            if "candidates" in response_data and response_data["candidates"]:
                text = response_data["candidates"][0]["content"]["parts"][0]["text"]
                return self._parse_analysis_response(text, analysis_type)
            else:
                return ImageAnalysisResult(success=False, error="No response from Gemini")

        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return ImageAnalysisResult(success=False, error=str(e))

    def _build_analysis_prompt(self, analysis_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build the analysis prompt based on type."""
        base_prompt = """Analyze this image and provide a structured response in JSON format.

"""

        if analysis_type == "character":
            prompt = base_prompt + """Focus on character analysis:
{
  "characters_detected": ["list of character descriptions"],
  "character_details": {
    "character_1": {
      "ethnicity": "detected ethnicity",
      "hair_color": "hair color",
      "hair_style": "hair style",
      "age_range": "estimated age",
      "gender": "gender",
      "clothing": "clothing description",
      "pose": "body pose/position",
      "expression": "facial expression"
    }
  },
  "symbolic_notation": "@CHAR_TAG format if identifiable"
}"""

        elif analysis_type == "validation":
            expected = context.get("expected", {}) if context else {}
            prompt = base_prompt + f"""Validate if the image matches these expected characteristics:
Expected: {json.dumps(expected, indent=2)}

Respond with:
{{
  "matches": true/false,
  "match_score": 0.0-1.0,
  "matched_attributes": ["list of matching attributes"],
  "mismatched_attributes": ["list of mismatches with details"],
  "description": "overall assessment"
}}"""

        else:  # full analysis
            prompt = base_prompt + """{
  "description": "detailed scene description",
  "characters_detected": ["list of characters with descriptions"],
  "character_details": {},
  "locations_detected": ["location descriptions"],
  "props_detected": ["notable props/objects"],
  "style_analysis": {
    "lighting": "lighting description",
    "color_palette": "dominant colors",
    "mood": "emotional tone",
    "composition": "framing/composition notes"
  },
  "symbolic_notation": "tags in @TAG format"
}"""

        return prompt

    def _parse_analysis_response(self, text: str, analysis_type: str) -> ImageAnalysisResult:
        """Parse the Gemini response into structured result."""
        try:
            # Try to extract JSON from response
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                data = json.loads(json_str)

                return ImageAnalysisResult(
                    success=True,
                    description=data.get("description", ""),
                    characters_detected=data.get("characters_detected", []),
                    character_details=data.get("character_details", {}),
                    locations_detected=data.get("locations_detected", []),
                    props_detected=data.get("props_detected", []),
                    style_analysis=data.get("style_analysis", {}),
                    symbolic_notation=data.get("symbolic_notation", ""),
                    raw_response=text
                )
            else:
                # No JSON found, return raw text
                return ImageAnalysisResult(
                    success=True,
                    description=text,
                    raw_response=text
                )
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            return ImageAnalysisResult(
                success=True,
                description=text,
                raw_response=text,
                error=f"JSON parse error: {e}"
            )

    # =========================================================================
    # CHARACTER MODIFICATION
    # =========================================================================

    async def plan_character_modification(
        self,
        character_tag: str,
        modification_description: str
    ) -> List[AutonomousTask]:
        """
        Plan a character modification using Gemini 2.5 to decompose the request.

        Args:
            character_tag: The character tag (e.g., 'CHAR_MEI')
            modification_description: Natural language description of changes

        Returns:
            List of planned tasks
        """
        import os
        from urllib import request as url_request

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.error("GOOGLE_API_KEY not set")
            return []

        # Load current character data
        character_data = self._load_character_data(character_tag)

        prompt = f"""You are a task planning agent. Given a character modification request,
decompose it into specific executable tasks.

Current Character Data:
{json.dumps(character_data, indent=2)}

Modification Request: "{modification_description}"

Create a task plan in JSON format:
{{
  "tasks": [
    {{
      "name": "task name",
      "description": "what this task does",
      "tool_name": "tool to use",
      "tool_params": {{}},
      "dependencies": []
    }}
  ]
}}

Available tools:
- modify_content: Update character/location/prop data (entity_type, entity_name, field, new_value)
  - For characters: field can be 'ethnicity', 'visual_appearance', 'costume', 'name', 'age', 'backstory'
- generate_character_reference: Generate a new reference image for a character (character_tag)
  - This automatically uses the updated character profile to generate the image
  - It saves to references/CHAR_TAG/ and marks as key reference
- find_frames_by_character: Find all storyboard frames with a character (character_tag)
- regenerate_frames_by_character: Regenerate all frames containing a character (character_tag)
  - This uses the new key reference image automatically

For character appearance changes, use this EXACT sequence:
1. modify_content to update ethnicity field
2. modify_content to update visual_appearance field
3. generate_character_reference to create new reference image (uses updated profile)
4. regenerate_frames_by_character to update all storyboard frames

IMPORTANT: Use task IDs (not names) for dependencies. First task has no dependencies.

Respond with ONLY the JSON task plan."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.llm_model}:generateContent"

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096}
        }

        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

        try:
            req = url_request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
            with url_request.urlopen(req, timeout=60) as resp:
                response_data = json.loads(resp.read().decode())

            if "candidates" in response_data and response_data["candidates"]:
                text = response_data["candidates"][0]["content"]["parts"][0]["text"]
                return self._parse_task_plan(text, character_tag)

        except Exception as e:
            logger.error(f"Task planning error: {e}")

        return []

    def _parse_task_plan(self, text: str, parent_context: str) -> List[AutonomousTask]:
        """Parse the task plan from Gemini response."""
        tasks = []
        try:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(text[json_start:json_end])

                # First pass: create all tasks with raw dependencies
                raw_deps_map = {}  # task_index -> raw dependencies
                for i, task_data in enumerate(data.get("tasks", [])):
                    raw_deps = task_data.get("dependencies", [])
                    raw_deps_map[i] = raw_deps

                    task = self.create_task(
                        name=task_data.get("name", f"Task {i+1}"),
                        description=task_data.get("description", ""),
                        tool_name=task_data.get("tool_name"),
                        tool_params=task_data.get("tool_params", {}),
                        dependencies=[]  # Will be resolved in second pass
                    )
                    tasks.append(task)

                # Second pass: resolve dependencies
                for i, task in enumerate(tasks):
                    raw_deps = raw_deps_map.get(i, [])
                    resolved_deps = []

                    for dep in raw_deps:
                        if isinstance(dep, int):
                            # Dependency is an index - convert to task ID
                            if 0 <= dep < len(tasks):
                                resolved_deps.append(tasks[dep].id)
                        elif isinstance(dep, str):
                            # Dependency is a name or ID - keep as is
                            resolved_deps.append(dep)

                    # If no dependencies but not first task, depend on previous
                    if not resolved_deps and i > 0:
                        resolved_deps = [tasks[i-1].id]

                    task.dependencies = resolved_deps

        except Exception as e:
            logger.error(f"Failed to parse task plan: {e}")

        return tasks

    def _load_character_data(self, character_tag: str) -> Dict[str, Any]:
        """Load character data from world_config.json."""
        if not self.project_path:
            return {}

        config_path = self.project_path / "world_bible" / "world_config.json"
        if not config_path.exists():
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # Normalize tag
            tag = character_tag.upper()
            if not tag.startswith("CHAR_"):
                tag = f"CHAR_{tag}"

            for char in config.get("characters", []):
                if char.get("tag") == tag:
                    return char
        except Exception as e:
            logger.error(f"Failed to load character data: {e}")

        return {}

    # =========================================================================
    # STORYBOARD FRAME MANAGEMENT
    # =========================================================================

    def find_frames_with_character(self, character_tag: str) -> List[Dict[str, Any]]:
        """Find all storyboard frames containing a specific character."""
        if not self.project_path:
            return []

        # Normalize tag
        tag = character_tag.upper()
        if not tag.startswith("CHAR_"):
            tag = f"CHAR_{tag}"

        frames = []
        visual_script_path = self.project_path / "storyboard" / "visual_script.json"

        if not visual_script_path.exists():
            logger.warning(f"Visual script not found: {visual_script_path}")
            return []

        try:
            with open(visual_script_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for scene in data.get("scenes", []):
                for frame in scene.get("frames", []):
                    # Check tags field
                    frame_tags = frame.get("tags", {})
                    characters = frame_tags.get("characters", [])

                    if tag in characters:
                        frames.append({
                            "frame_id": frame.get("frame_id"),
                            "scene_id": scene.get("scene_id"),
                            "prompt": frame.get("prompt", ""),
                            "tags": frame_tags,
                            "image_path": self.project_path / "storyboard" / "generated" / f"{frame.get('frame_id')}.png"
                        })
                        continue

                    # Also check prompt text for character mentions
                    prompt = frame.get("prompt", "").upper()
                    if tag in prompt or tag.replace("CHAR_", "") in prompt:
                        frames.append({
                            "frame_id": frame.get("frame_id"),
                            "scene_id": scene.get("scene_id"),
                            "prompt": frame.get("prompt", ""),
                            "tags": frame_tags,
                            "image_path": self.project_path / "storyboard" / "generated" / f"{frame.get('frame_id')}.png"
                        })

        except Exception as e:
            logger.error(f"Failed to find frames: {e}")

        logger.info(f"Found {len(frames)} frames with character {tag}")
        return frames

    def get_pending_generations(self) -> Dict[str, str]:
        """Get status of pending image generations."""
        return self._pending_generations.copy()

    def set_generation_pending(self, frame_id: str) -> None:
        """Mark a frame as pending generation."""
        self._pending_generations[frame_id] = "pending"

    def set_generation_complete(self, frame_id: str) -> None:
        """Mark a frame generation as complete."""
        self._pending_generations[frame_id] = "complete"

    def is_generation_pending(self, frame_id: str) -> bool:
        """Check if a frame generation is pending."""
        return self._pending_generations.get(frame_id) == "pending"

    # =========================================================================
    # MAIN EXECUTION ENTRY POINT
    # =========================================================================

    async def execute_character_modification(
        self,
        character_tag: str,
        modification_description: str,
        auto_execute: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a complete character modification workflow.

        This is the main entry point for autonomous character changes.

        Args:
            character_tag: Character to modify (e.g., 'CHAR_MEI' or 'MEI')
            modification_description: Natural language description of changes
            auto_execute: Whether to automatically execute the planned tasks

        Returns:
            Execution result with task status
        """
        logger.info(f"Starting character modification: {character_tag}")
        logger.info(f"Modification: {modification_description}")

        # Step 1: Plan the modification
        tasks = await self.plan_character_modification(character_tag, modification_description)

        if not tasks:
            return {
                "success": False,
                "error": "Failed to plan modification tasks",
                "tasks": []
            }

        logger.info(f"Planned {len(tasks)} tasks for modification")

        result = {
            "success": True,
            "character_tag": character_tag,
            "modification": modification_description,
            "tasks": [],
            "executed": [],
            "failed": []
        }

        if auto_execute:
            # Step 2: Execute all tasks
            exec_result = await self.execute_all_pending()
            result["executed"] = exec_result["executed"]
            result["failed"] = exec_result["failed"]
            result["success"] = len(exec_result["failed"]) == 0
            # Get updated task status after execution
            result["tasks"] = [self._tasks[t.id].to_dict() for t in tasks if t.id in self._tasks]
        else:
            result["tasks"] = [t.to_dict() for t in tasks]

        return result

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of all task executions."""
        total = len(self._tasks)
        complete = len([t for t in self._tasks.values() if t.status == TaskStatus.COMPLETE])
        failed = len([t for t in self._tasks.values() if t.status == TaskStatus.FAILED])
        pending = len([t for t in self._tasks.values() if t.status == TaskStatus.PENDING])
        in_progress = len([t for t in self._tasks.values() if t.status == TaskStatus.IN_PROGRESS])

        return {
            "total_tasks": total,
            "complete": complete,
            "failed": failed,
            "pending": pending,
            "in_progress": in_progress,
            "success_rate": complete / total if total > 0 else 0,
            "tasks": [t.to_dict() for t in self._tasks.values()]
        }

    # =========================================================================
    # SMART PROMPTING WITH LLM HANDSHAKE
    # =========================================================================

    def build_smart_prompt(
        self,
        base_instruction: str,
        prefix_type: str = "edit",
        character_context: Optional[Dict[str, Any]] = None,
        style_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build a smart prompt using template prefixes and context.

        Template Types (canonical definitions from image_handler.py):
        - edit: For editing existing images while preserving identity
        - reangle: For recreating images from different camera angles
        - recreate: For regenerating images with modifications (character references)
        - create: For creating new images from references (storyboard frames, scenes)
        - character: Legacy alias for "create" (deprecated)
        - generate: Legacy alias for "create" (deprecated)

        Args:
            base_instruction: The core instruction
            prefix_type: Type of prefix to use
            character_context: Character data for context injection
            style_context: Style data (visual_style, style_notes)

        Returns:
            Fully constructed prompt with context
        """
        # Import canonical template definitions from image_handler
        from greenlight.core.image_handler import (
            PROMPT_TEMPLATE_EDIT,
            PROMPT_TEMPLATE_CREATE,
            PROMPT_TEMPLATE_REANGLE,
            PROMPT_TEMPLATE_RECREATE
        )

        # Template prefixes - use canonical definitions
        prefixes = {
            "edit": PROMPT_TEMPLATE_EDIT + " ",
            "reangle": PROMPT_TEMPLATE_REANGLE + " ",
            "recreate": PROMPT_TEMPLATE_RECREATE + " ",
            "create": PROMPT_TEMPLATE_CREATE + " ",
            # Legacy aliases (deprecated)
            "character": PROMPT_TEMPLATE_CREATE + " ",
            "generate": PROMPT_TEMPLATE_CREATE + " ",
            "none": ""
        }

        prefix = prefixes.get(prefix_type, "")

        # Build context section
        context_parts = []

        # Add style context
        if style_context:
            visual_style = style_context.get("visual_style", "")
            style_notes = style_context.get("style_notes", "")
            if visual_style:
                context_parts.append(f"Style: {visual_style}")
            if style_notes:
                context_parts.append(f"Style Notes: {style_notes}")

        # Add character context
        if character_context:
            char_name = character_context.get("name", "")
            char_appearance = character_context.get("appearance", "")
            char_costume = character_context.get("costume", "")

            if char_name:
                context_parts.append(f"Character: {char_name}")
            if char_appearance:
                context_parts.append(f"Appearance: {char_appearance[:200]}")
            if char_costume:
                context_parts.append(f"Costume: {char_costume[:200]}")

        # Construct final prompt
        context_str = " | ".join(context_parts) if context_parts else ""

        if context_str:
            return f"{prefix}{base_instruction}\n\n[Context: {context_str}]"
        else:
            return f"{prefix}{base_instruction}"

    async def execute_with_handshake(
        self,
        natural_request: str,
        context: Optional[Dict[str, Any]] = None,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a request using the LLM handshake protocol.

        This provides:
        - Context loading from project
        - Vector notation translation
        - Response validation
        - Result storage

        Args:
            natural_request: Natural language request
            context: Additional context to load
            validate: Whether to validate the response

        Returns:
            Handshake result with response
        """
        import os
        from urllib import request as url_request

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return {"success": False, "error": "GOOGLE_API_KEY not set"}

        # Phase 1: INIT - Build system prompt with context
        system_prompt = self._build_handshake_system_prompt(context)

        # Phase 2: CONTEXT_LOAD - Load project context
        project_context = self._load_project_context()

        # Phase 3: TRANSLATE - Convert to vector notation (for logging)
        vector_notation = self._translate_to_notation(natural_request)

        # Phase 4: EXECUTE - Call LLM
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.llm_model}:generateContent"

        body = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{natural_request}"}]}
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096
            }
        }

        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

        try:
            req = url_request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
            with url_request.urlopen(req, timeout=60) as resp:
                response_data = json.loads(resp.read().decode())

            if "candidates" in response_data and response_data["candidates"]:
                response_text = response_data["candidates"][0]["content"]["parts"][0]["text"]

                # Phase 5: VALIDATE
                validation_result = None
                if validate:
                    validation_result = self._validate_response(response_text, natural_request)

                # Phase 6: STORE - Log the handshake
                self._execution_history.append({
                    "request": natural_request,
                    "vector_notation": vector_notation,
                    "response": response_text[:500],
                    "validated": validation_result,
                    "timestamp": datetime.now().isoformat()
                })

                return {
                    "success": True,
                    "response": response_text,
                    "vector_notation": vector_notation,
                    "validation": validation_result,
                    "context_loaded": list(project_context.keys()) if project_context else []
                }
            else:
                return {"success": False, "error": "No response from LLM"}

        except Exception as e:
            logger.error(f"Handshake execution error: {e}")
            return {"success": False, "error": str(e)}

    def _build_handshake_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Build system prompt for handshake."""
        base = """You are an autonomous agent for Project Greenlight, a storyboard generation system.

## Vector Notation Reference
- @TAG - Exact tag lookup (e.g., @CHAR_MEI, @LOC_TEAHOUSE)
- #SCOPE - Filter by scope (e.g., #STORY, #WORLD_BIBLE)
- >COMMAND - Execute command (e.g., >diagnose, >heal)

## Available Actions
- Modify character descriptions
- Analyze images for content
- Edit images with instructions
- Find storyboard frames by character
- Regenerate frames with new references
- Validate changes

## Response Format
Respond with clear, actionable steps. Use @TAG notation when referencing entities.
"""

        if context:
            base += f"\n## Additional Context\n{json.dumps(context, indent=2)}"

        return base

    def _load_project_context(self) -> Dict[str, Any]:
        """Load relevant project context."""
        if not self.project_path:
            return {}

        context = {}

        # Load world_config.json
        config_path = self.project_path / "world_bible" / "world_config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                context["visual_style"] = config.get("visual_style", "")
                context["style_notes"] = config.get("style_notes", "")
                context["character_count"] = len(config.get("characters", []))
                context["location_count"] = len(config.get("locations", []))
            except:
                pass

        return context

    def _translate_to_notation(self, natural_request: str) -> str:
        """Translate natural language to vector notation."""
        # Simple translation for logging
        notation_parts = []

        # Detect character references
        if "mei" in natural_request.lower():
            notation_parts.append("@CHAR_MEI")
        if "character" in natural_request.lower():
            notation_parts.append("#CHARACTER")
        if "storyboard" in natural_request.lower():
            notation_parts.append("#STORYBOARD")
        if "edit" in natural_request.lower():
            notation_parts.append(">edit")
        if "regenerate" in natural_request.lower():
            notation_parts.append(">regenerate")

        return " ".join(notation_parts) if notation_parts else "?QUERY"

    def _validate_response(self, response: str, request: str) -> Dict[str, Any]:
        """Validate LLM response quality."""
        # Basic validation
        validation = {
            "has_content": len(response) > 10,
            "not_error": "error" not in response.lower()[:100],
            "relevant": any(word in response.lower() for word in request.lower().split()[:5])
        }
        validation["passed"] = all(validation.values())
        return validation

    # =========================================================================
    # CONTINUITY CHECK & AUTO-FIX
    # =========================================================================

    async def analyze_continuity(
        self,
        frame_ids: List[str],
        focus_frame: Optional[str] = None,
        user_concern: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze continuity across multiple frames using Gemini 2.5 multi-image input.

        Args:
            frame_ids: List of frame IDs to analyze (e.g., ["1.1", "1.2", "1.3"])
            focus_frame: Specific frame to focus on (e.g., "1.3")
            user_concern: User's description of the issue

        Returns:
            Continuity report with issues and recommendations
        """
        import os
        from urllib import request as url_request

        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return {"success": False, "error": "GOOGLE_API_KEY not set"}

        # Load visual script for context
        visual_script = self._load_visual_script()
        if not visual_script:
            return {"success": False, "error": "Could not load visual script"}

        # Collect frame images and prompts
        frames_data = []
        image_parts = []

        frames_dir = self.project_path / "storyboard" / "frames"

        for frame_id in frame_ids:
            # Find frame in visual script
            frame_info = self._get_frame_info(visual_script, frame_id)

            # Find image file
            scene_num, frame_num = frame_id.split(".")
            image_path = frames_dir / f"frame_{scene_num}_{frame_num}.png"

            if image_path.exists():
                with open(image_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("ascii")

                image_parts.append({
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_data
                    }
                })

                frames_data.append({
                    "frame_id": frame_id,
                    "prompt": frame_info.get("prompt", "") if frame_info else "",
                    "camera": frame_info.get("camera_notation", "") if frame_info else "",
                    "lighting": frame_info.get("lighting_notation", "") if frame_info else "",
                    "has_image": True
                })
            else:
                frames_data.append({
                    "frame_id": frame_id,
                    "prompt": frame_info.get("prompt", "") if frame_info else "",
                    "has_image": False,
                    "error": f"Image not found: {image_path}"
                })

        if not image_parts:
            return {"success": False, "error": "No frame images found"}

        # Build continuity analysis prompt
        prompt = self._build_continuity_prompt(frames_data, focus_frame, user_concern)

        # Build request with multiple images
        parts = [{"text": prompt}] + image_parts

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.llm_model}:generateContent"

        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 8192
            }
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        try:
            req = url_request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
            with url_request.urlopen(req, timeout=120) as resp:
                response_data = json.loads(resp.read().decode())

            if "candidates" in response_data and response_data["candidates"]:
                text = response_data["candidates"][0]["content"]["parts"][0]["text"]
                return self._parse_continuity_report(text, frames_data, focus_frame)
            else:
                return {"success": False, "error": "No response from Gemini"}

        except Exception as e:
            logger.error(f"Continuity analysis error: {e}")
            return {"success": False, "error": str(e)}

    def _build_continuity_prompt(
        self,
        frames_data: List[Dict[str, Any]],
        focus_frame: Optional[str],
        user_concern: Optional[str]
    ) -> str:
        """Build the continuity analysis prompt."""
        prompt = """You are a professional storyboard continuity supervisor. Analyze the provided sequence of storyboard frames for continuity issues.

## Frame Sequence Information
"""
        for i, frame in enumerate(frames_data):
            prompt += f"""
### Frame {frame['frame_id']} (Image {i+1})
- Camera: {frame.get('camera', 'N/A')}
- Lighting: {frame.get('lighting', 'N/A')}
- Prompt: {frame.get('prompt', 'N/A')[:500]}...
"""

        if focus_frame:
            prompt += f"\n## FOCUS: The user is specifically concerned about frame {focus_frame}\n"

        if user_concern:
            prompt += f"\n## User Concern: {user_concern}\n"

        prompt += """
## Analysis Required
Analyze the images for:
1. **Visual Continuity**: Character appearance, clothing, positioning consistency
2. **Lighting Continuity**: Light direction, color temperature, shadows
3. **Scene Flow**: Does the sequence make visual sense? Does each frame logically follow the previous?
4. **Prompt Alignment**: Does each generated image match its intended prompt?
5. **Specific Issues**: Any frame that looks "weird" or doesn't fit

## Response Format (JSON)
{
  "overall_assessment": "Brief summary of continuity quality",
  "continuity_score": 0.0-1.0,
  "issues": [
    {
      "frame_id": "X.X",
      "severity": "critical|major|minor",
      "issue_type": "visual|lighting|flow|prompt_mismatch|other",
      "description": "Detailed description of the issue",
      "recommendation": "How to fix this issue",
      "prompt_fix": "Suggested prompt modification (if applicable)"
    }
  ],
  "frame_assessments": [
    {
      "frame_id": "X.X",
      "fits_sequence": true/false,
      "quality_score": 0.0-1.0,
      "notes": "Assessment notes"
    }
  ],
  "recommended_actions": [
    {
      "action": "regenerate|edit_prompt|adjust_lighting|etc",
      "frame_id": "X.X",
      "details": "Specific action details"
    }
  ]
}

Respond with ONLY the JSON analysis."""

        return prompt

    def _parse_continuity_report(
        self,
        text: str,
        frames_data: List[Dict[str, Any]],
        focus_frame: Optional[str]
    ) -> Dict[str, Any]:
        """Parse the continuity report from Gemini response."""
        try:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(text[json_start:json_end])

                return {
                    "success": True,
                    "frames_analyzed": [f["frame_id"] for f in frames_data],
                    "focus_frame": focus_frame,
                    "overall_assessment": data.get("overall_assessment", ""),
                    "continuity_score": data.get("continuity_score", 0.0),
                    "issues": data.get("issues", []),
                    "frame_assessments": data.get("frame_assessments", []),
                    "recommended_actions": data.get("recommended_actions", []),
                    "raw_response": text
                }
            else:
                return {
                    "success": True,
                    "frames_analyzed": [f["frame_id"] for f in frames_data],
                    "overall_assessment": text,
                    "issues": [],
                    "raw_response": text
                }
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse continuity report JSON: {e}")
            return {
                "success": True,
                "frames_analyzed": [f["frame_id"] for f in frames_data],
                "overall_assessment": text,
                "issues": [],
                "parse_error": str(e),
                "raw_response": text
            }

    def _load_visual_script(self) -> Optional[Dict[str, Any]]:
        """Load the visual script JSON."""
        if not self.project_path:
            return None

        script_path = self.project_path / "storyboard" / "visual_script.json"
        if script_path.exists():
            try:
                with open(script_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load visual script: {e}")
        return None

    def _get_frame_info(self, visual_script: Dict[str, Any], frame_id: str) -> Optional[Dict[str, Any]]:
        """Get frame info from visual script by frame_id."""
        for scene in visual_script.get("scenes", []):
            for frame in scene.get("frames", []):
                if frame.get("frame_id") == frame_id:
                    return frame
        return None

    async def fix_continuity_issues(
        self,
        continuity_report: Dict[str, Any],
        auto_regenerate: bool = True
    ) -> Dict[str, Any]:
        """
        Fix continuity issues based on the analysis report.

        Args:
            continuity_report: The report from analyze_continuity
            auto_regenerate: Whether to automatically regenerate fixed frames

        Returns:
            Result of the fix operation
        """
        if not continuity_report.get("success"):
            return {"success": False, "error": "Invalid continuity report"}

        issues = continuity_report.get("issues", [])
        actions = continuity_report.get("recommended_actions", [])

        if not issues and not actions:
            return {"success": True, "message": "No issues to fix", "fixes_applied": []}

        fixes_applied = []
        frames_to_regenerate = []

        # Load visual script
        visual_script = self._load_visual_script()
        if not visual_script:
            return {"success": False, "error": "Could not load visual script"}

        script_modified = False

        # Process issues with prompt fixes
        for issue in issues:
            frame_id = issue.get("frame_id")
            prompt_fix = issue.get("prompt_fix")

            if prompt_fix and frame_id:
                # Update the prompt in visual script
                updated = self._update_frame_prompt(visual_script, frame_id, prompt_fix, issue.get("description", ""))
                if updated:
                    script_modified = True
                    fixes_applied.append({
                        "type": "prompt_update",
                        "frame_id": frame_id,
                        "issue": issue.get("description"),
                        "new_prompt": prompt_fix[:200] + "..."
                    })
                    frames_to_regenerate.append(frame_id)

        # Process recommended actions
        for action in actions:
            action_type = action.get("action")
            frame_id = action.get("frame_id")

            if action_type == "regenerate" and frame_id:
                if frame_id not in frames_to_regenerate:
                    frames_to_regenerate.append(frame_id)
                    fixes_applied.append({
                        "type": "regenerate",
                        "frame_id": frame_id,
                        "reason": action.get("details", "Recommended by continuity analysis")
                    })

        # Save updated visual script
        if script_modified:
            script_path = self.project_path / "storyboard" / "visual_script.json"
            try:
                with open(script_path, "w", encoding="utf-8") as f:
                    json.dump(visual_script, f, indent=2, ensure_ascii=False)
                logger.info(f"Updated visual script with {len(fixes_applied)} prompt fixes")
            except Exception as e:
                logger.error(f"Failed to save visual script: {e}")
                return {"success": False, "error": f"Failed to save visual script: {e}"}

        # Regenerate frames if requested
        regenerated = []
        if auto_regenerate and frames_to_regenerate and self.tool_executor:
            for frame_id in frames_to_regenerate:
                try:
                    result = self.tool_executor.execute(
                        "regenerate_single_frame",
                        frame_id=frame_id
                    )
                    if result.success:
                        regenerated.append(frame_id)
                    else:
                        logger.warning(f"Failed to regenerate frame {frame_id}: {result.error}")
                except Exception as e:
                    logger.error(f"Error regenerating frame {frame_id}: {e}")

        return {
            "success": True,
            "fixes_applied": fixes_applied,
            "frames_to_regenerate": frames_to_regenerate,
            "frames_regenerated": regenerated,
            "script_modified": script_modified
        }

    def _update_frame_prompt(
        self,
        visual_script: Dict[str, Any],
        frame_id: str,
        new_prompt: str,
        issue_description: str
    ) -> bool:
        """Update a frame's prompt in the visual script."""
        for scene in visual_script.get("scenes", []):
            for frame in scene.get("frames", []):
                if frame.get("frame_id") == frame_id:
                    old_prompt = frame.get("prompt", "")
                    # Append fix note and update prompt
                    frame["prompt"] = new_prompt
                    frame["continuity_fix"] = {
                        "timestamp": datetime.now().isoformat(),
                        "issue": issue_description,
                        "old_prompt_preview": old_prompt[:200] + "..." if len(old_prompt) > 200 else old_prompt
                    }
                    logger.info(f"Updated prompt for frame {frame_id}")
                    return True
        return False

    async def execute_continuity_check(
        self,
        user_request: str,
        auto_fix: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a full continuity check workflow from natural language request.

        Args:
            user_request: Natural language request (e.g., "frame 1.3 seems weird")
            auto_fix: Whether to automatically fix issues

        Returns:
            Complete result with analysis and fixes
        """
        logger.info(f"Continuity check request: {user_request}")

        # Parse the request to identify frames
        focus_frame = self._extract_frame_reference(user_request)

        if not focus_frame:
            return {"success": False, "error": "Could not identify frame reference in request"}

        # Get surrounding frames for context
        frame_ids = self._get_surrounding_frames(focus_frame)

        logger.info(f"Analyzing frames: {frame_ids} with focus on {focus_frame}")

        # Step 1: Analyze continuity
        report = await self.analyze_continuity(
            frame_ids=frame_ids,
            focus_frame=focus_frame,
            user_concern=user_request
        )

        if not report.get("success"):
            return report

        result = {
            "success": True,
            "focus_frame": focus_frame,
            "frames_analyzed": frame_ids,
            "analysis": report
        }

        # Step 2: Fix issues if requested
        if auto_fix and (report.get("issues") or report.get("recommended_actions")):
            fix_result = await self.fix_continuity_issues(report, auto_regenerate=True)
            result["fix_result"] = fix_result

        return result

    def _extract_frame_reference(self, text: str) -> Optional[str]:
        """Extract frame reference from natural language text."""
        import re

        # Pattern: frame X.Y, frame X.Y, 1.3, etc.
        patterns = [
            r"frame\s*(\d+)\.(\d+)",
            r"frame\s*(\d+)\s*\.\s*(\d+)",
            r"(\d+)\.(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return f"{match.group(1)}.{match.group(2)}"

        return None

    def _get_surrounding_frames(self, frame_id: str, context_size: int = 2) -> List[str]:
        """Get surrounding frames for context."""
        visual_script = self._load_visual_script()
        if not visual_script:
            return [frame_id]

        # Collect all frame IDs in order
        all_frames = []
        for scene in visual_script.get("scenes", []):
            for frame in scene.get("frames", []):
                all_frames.append(frame.get("frame_id"))

        if frame_id not in all_frames:
            return [frame_id]

        idx = all_frames.index(frame_id)
        start = max(0, idx - context_size)
        end = min(len(all_frames), idx + context_size + 1)

        return all_frames[start:end]

