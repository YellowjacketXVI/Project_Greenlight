"""
Task Translator Agent - Natural Language to OmniMind Operations

Translates natural language prompts into structured OmniMind tool operations.
This serves as the bridge between user intent and system execution.

Features:
1. Intent Classification - Understand what the user wants to do
2. Parameter Extraction - Extract required parameters from the prompt
3. Tool Mapping - Map intent to appropriate OmniMind tools
4. Task Decomposition - Break complex requests into subtasks
5. Execution Planning - Create ordered execution plan
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger

logger = get_logger("agents.task_translator")


class TaskIntent(Enum):
    """Classified intent types."""
    # Content Generation
    GENERATE_STORY = "generate_story"
    GENERATE_WORLD_BIBLE = "generate_world_bible"
    GENERATE_STORYBOARD = "generate_storyboard"
    GENERATE_DIALOGUE = "generate_dialogue"

    # Content Modification
    EDIT_CONTENT = "edit_content"
    REFINE_CONTENT = "refine_content"
    EXPAND_CONTENT = "expand_content"

    # Analysis & Validation
    ANALYZE_STORY = "analyze_story"
    VALIDATE_CONTINUITY = "validate_continuity"
    CHECK_CONSISTENCY = "check_consistency"

    # Retrieval & Query
    FIND_INFORMATION = "find_information"
    GET_TAG_INFO = "get_tag_info"
    SEARCH_CONTENT = "search_content"

    # Pipeline Execution
    RUN_PIPELINE = "run_pipeline"

    # Unknown
    UNKNOWN = "unknown"


@dataclass
class TranslatedTask:
    """A translated task ready for execution."""
    intent: TaskIntent
    tool_name: str
    parameters: Dict[str, Any]
    description: str
    priority: int = 1
    depends_on: List[str] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    """Plan for executing translated tasks."""
    tasks: List[TranslatedTask]
    original_prompt: str
    estimated_steps: int
    requires_confirmation: bool = False
    warnings: List[str] = field(default_factory=list)


class TaskTranslatorAgent:
    """
    Translates natural language prompts into OmniMind operations.

    This agent:
    1. Classifies user intent from natural language
    2. Extracts parameters and context
    3. Maps to appropriate tools
    4. Creates execution plans
    """

    # Intent patterns for quick classification
    INTENT_PATTERNS = {
        TaskIntent.GENERATE_STORY: [
            r"write.*story", r"create.*story", r"generate.*story",
            r"write.*script", r"create.*script", r"generate.*script",
        ],
        TaskIntent.GENERATE_WORLD_BIBLE: [
            r"create.*world", r"build.*world", r"generate.*world",
            r"research.*character", r"research.*location",
        ],
        TaskIntent.GENERATE_STORYBOARD: [
            r"create.*storyboard", r"generate.*storyboard",
            r"create.*shots", r"generate.*shots",
        ],
        TaskIntent.ANALYZE_STORY: [
            r"analyze.*story", r"review.*story", r"check.*story",
        ],
        TaskIntent.VALIDATE_CONTINUITY: [
            r"check.*continuity", r"validate.*continuity",
            r"find.*inconsistenc", r"check.*consistency",
        ],
        TaskIntent.FIND_INFORMATION: [
            r"find.*about", r"what.*is", r"tell.*about",
            r"show.*info", r"get.*info",
        ],
        TaskIntent.GET_TAG_INFO: [
            r"find.*tag", r"get.*tag", r"show.*tag",
            r"character.*info", r"location.*info",
        ],
        TaskIntent.RUN_PIPELINE: [
            r"run.*pipeline", r"execute.*pipeline",
            r"start.*pipeline", r"run.*writer",
        ],
        TaskIntent.EDIT_CONTENT: [
            r"edit.*", r"change.*", r"modify.*", r"update.*",
        ],
        TaskIntent.REFINE_CONTENT: [
            r"refine.*", r"improve.*", r"polish.*", r"enhance.*",
        ],
    }

    # Tool mapping for each intent
    INTENT_TO_TOOL = {
        TaskIntent.GENERATE_STORY: "run_story_pipeline",
        TaskIntent.GENERATE_WORLD_BIBLE: "run_world_bible_pipeline",
        TaskIntent.GENERATE_STORYBOARD: "run_directing_pipeline",
        TaskIntent.ANALYZE_STORY: "story_analysis_protocol",
        TaskIntent.VALIDATE_CONTINUITY: "run_quality_validation",
        TaskIntent.FIND_INFORMATION: "omni_find_related",
        TaskIntent.GET_TAG_INFO: "omni_search_tags",
        TaskIntent.RUN_PIPELINE: "get_pipeline_status",
        TaskIntent.EDIT_CONTENT: "write_file",
        TaskIntent.REFINE_CONTENT: "run_procedural_generation",
    }

    def __init__(self, llm_caller: Callable = None, tool_executor: Any = None):
        """
        Initialize the task translator.

        Args:
            llm_caller: Async function to call LLM for complex translations
            tool_executor: ToolExecutor instance for tool validation
        """
        self.llm_caller = llm_caller
        self.tool_executor = tool_executor
        self._available_tools: List[str] = []

        if tool_executor:
            self._available_tools = [t['name'] for t in tool_executor.get_declarations()]

    # =========================================================================
    # CORE TRANSLATION METHODS
    # =========================================================================

    async def translate(self, prompt: str, context: Dict[str, Any] = None) -> ExecutionPlan:
        """
        Translate a natural language prompt into an execution plan.

        Args:
            prompt: Natural language prompt from user
            context: Additional context (current project, tags, etc.)

        Returns:
            ExecutionPlan with tasks to execute
        """
        context = context or {}

        # Step 1: Classify intent
        intent = self._classify_intent(prompt)
        logger.info(f"Classified intent: {intent.value}")

        # Step 2: Extract parameters
        params = self._extract_parameters(prompt, intent, context)

        # Step 3: Check if complex translation needed
        if intent == TaskIntent.UNKNOWN or self._is_complex_request(prompt):
            return await self._llm_translate(prompt, context)

        # Step 4: Create simple execution plan
        return self._create_simple_plan(prompt, intent, params, context)

    def _classify_intent(self, prompt: str) -> TaskIntent:
        """Classify the intent from the prompt using pattern matching."""
        prompt_lower = prompt.lower()

        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, prompt_lower):
                    return intent

        return TaskIntent.UNKNOWN

    def _extract_parameters(
        self,
        prompt: str,
        intent: TaskIntent,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters from the prompt based on intent."""
        params = {}

        # Extract tags mentioned in brackets
        tags = re.findall(r'\[([A-Z_]+)\]', prompt)
        if tags:
            params['tags'] = tags

        # Extract quoted strings
        quoted = re.findall(r'"([^"]+)"', prompt)
        if quoted:
            params['quoted_text'] = quoted

        # Extract file paths
        paths = re.findall(r'[\w/\\]+\.\w+', prompt)
        if paths:
            params['file_paths'] = paths

        # Intent-specific extraction
        if intent == TaskIntent.GENERATE_STORY:
            # Look for story type indicators
            if 'short' in prompt.lower():
                params['project_size'] = 'short'
            elif 'feature' in prompt.lower():
                params['project_size'] = 'feature'
            else:
                params['project_size'] = 'standard'

        elif intent == TaskIntent.RUN_PIPELINE:
            # Extract pipeline name
            pipeline_names = ['story', 'world_bible', 'directing', 'storyboard']
            for name in pipeline_names:
                if name in prompt.lower():
                    params['pipeline_name'] = name
                    break

        # Add context
        params['context'] = context

        return params

    def _is_complex_request(self, prompt: str) -> bool:
        """Check if the request is too complex for pattern matching."""
        # Complex if multiple sentences or conditional logic
        sentences = prompt.split('.')
        if len(sentences) > 3:
            return True

        # Complex if contains conditional words
        complex_words = ['if', 'then', 'unless', 'after', 'before', 'when']
        for word in complex_words:
            if f' {word} ' in prompt.lower():
                return True

        return False

    def _create_simple_plan(
        self,
        prompt: str,
        intent: TaskIntent,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ExecutionPlan:
        """Create a simple execution plan for straightforward requests."""
        tool_name = self.INTENT_TO_TOOL.get(intent, "get_project_info")

        # Build tool parameters
        tool_params = {}
        if 'tags' in params:
            tool_params['tag'] = params['tags'][0] if params['tags'] else None
        if 'file_paths' in params:
            tool_params['path'] = params['file_paths'][0]
        if 'project_size' in params:
            tool_params['project_size'] = params['project_size']
        if 'pipeline_name' in params:
            tool_params['pipeline'] = params['pipeline_name']

        task = TranslatedTask(
            intent=intent,
            tool_name=tool_name,
            parameters=tool_params,
            description=f"Execute {intent.value}: {prompt[:50]}..."
        )

        return ExecutionPlan(
            tasks=[task],
            original_prompt=prompt,
            estimated_steps=1,
            requires_confirmation=intent in [
                TaskIntent.EDIT_CONTENT,
                TaskIntent.GENERATE_STORY,
                TaskIntent.GENERATE_WORLD_BIBLE
            ]
        )

    async def _llm_translate(
        self,
        prompt: str,
        context: Dict[str, Any]
    ) -> ExecutionPlan:
        """Use LLM for complex translation."""
        if not self.llm_caller:
            # Fallback to unknown intent
            return ExecutionPlan(
                tasks=[TranslatedTask(
                    intent=TaskIntent.UNKNOWN,
                    tool_name="get_project_info",
                    parameters={},
                    description="Could not translate request - showing project info"
                )],
                original_prompt=prompt,
                estimated_steps=1,
                warnings=["Complex request could not be fully translated"]
            )

        # Build LLM prompt for translation
        tools_list = "\n".join([f"- {t}" for t in self._available_tools[:20]])

        translation_prompt = f"""Translate this user request into tool operations.

USER REQUEST: {prompt}

AVAILABLE TOOLS:
{tools_list}

Respond with JSON:
{{
    "tasks": [
        {{
            "tool_name": "tool_name_here",
            "parameters": {{"param": "value"}},
            "description": "What this step does"
        }}
    ],
    "requires_confirmation": true/false,
    "warnings": ["any warnings"]
}}"""

        try:
            response = await self.llm_caller(
                prompt=translation_prompt,
                system_prompt="You are a task translator. Convert user requests into tool operations.",
                function=LLMFunction.ASSISTANT
            )

            # Parse JSON response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())

                tasks = []
                for t in data.get('tasks', []):
                    tasks.append(TranslatedTask(
                        intent=TaskIntent.UNKNOWN,
                        tool_name=t.get('tool_name', 'get_project_info'),
                        parameters=t.get('parameters', {}),
                        description=t.get('description', '')
                    ))

                return ExecutionPlan(
                    tasks=tasks,
                    original_prompt=prompt,
                    estimated_steps=len(tasks),
                    requires_confirmation=data.get('requires_confirmation', True),
                    warnings=data.get('warnings', [])
                )
        except Exception as e:
            logger.error(f"LLM translation failed: {e}")

        # Fallback
        return ExecutionPlan(
            tasks=[],
            original_prompt=prompt,
            estimated_steps=0,
            warnings=["Translation failed - please rephrase your request"]
        )

    # =========================================================================
    # EXECUTION METHODS
    # =========================================================================

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        confirm_callback: Callable = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a translated plan.

        Args:
            plan: ExecutionPlan to execute
            confirm_callback: Optional callback for confirmation

        Returns:
            List of results from each task
        """
        if not self.tool_executor:
            return [{"error": "No tool executor available"}]

        # Check confirmation
        if plan.requires_confirmation and confirm_callback:
            confirmed = await confirm_callback(plan)
            if not confirmed:
                return [{"cancelled": True, "message": "User cancelled execution"}]

        results = []
        for task in plan.tasks:
            try:
                result = self.tool_executor.execute(task.tool_name, **task.parameters)
                results.append({
                    "task": task.description,
                    "tool": task.tool_name,
                    "success": result.success,
                    "result": result.result if result.success else result.error
                })
            except Exception as e:
                results.append({
                    "task": task.description,
                    "tool": task.tool_name,
                    "success": False,
                    "error": str(e)
                })

        return results

    def get_supported_intents(self) -> List[Dict[str, str]]:
        """Get list of supported intents for reference."""
        return [
            {"intent": intent.value, "tool": self.INTENT_TO_TOOL.get(intent, "unknown")}
            for intent in TaskIntent
            if intent != TaskIntent.UNKNOWN
        ]

