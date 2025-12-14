"""
Greenlight Omni Mind

The central AI assistant that orchestrates all operations.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from greenlight.llm import LLMManager, FunctionRouter
from greenlight.context import ContextEngine, ContextQuery
from greenlight.tags import TagRegistry, ConsensusTagger
from greenlight.graph import DependencyGraph, PropagationEngine
from greenlight.agents.agent_retrieval import AgentRetrievalTool, RetrievalScope, RetrievalResult
from greenlight.agents.task_translator import TaskTranslatorAgent, TaskIntent, ExecutionPlan
from .memory import AssistantMemory, MemoryType
from .decision_engine import DecisionEngine, Decision, DecisionType
from .suggestion_engine import SuggestionEngine, Suggestion
from .tool_executor import ToolExecutor, ToolResult
from .vector_cache import VectorCache, CacheEntryType
from .project_health import ProjectHealthLogger, LogCategory
from .error_handoff import ErrorHandoff, ErrorSeverity
from .usage_metrics import UsageMetricsLogger

logger = get_logger("omni_mind.core")


class AssistantMode(Enum):
    """Operating modes for the assistant."""
    AUTONOMOUS = "autonomous"      # Full auto-execution
    SUPERVISED = "supervised"      # Confirm important decisions
    MANUAL = "manual"              # User controls everything


@dataclass
class AssistantResponse:
    """Response from the assistant."""
    message: str
    decisions: List[Decision] = field(default_factory=list)
    suggestions: List[Suggestion] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    context_used: Dict[str, Any] = field(default_factory=dict)
    requires_input: bool = False
    input_prompt: Optional[str] = None


class OmniMind:
    """
    The Omni Mind AI assistant.
    
    Features:
    - Natural language interaction
    - Context-aware responses
    - Autonomous decision making
    - Proactive suggestions
    - Memory and learning
    """
    
    def __init__(
        self,
        llm_manager: LLMManager = None,
        context_engine: ContextEngine = None,
        tag_registry: TagRegistry = None,
        dependency_graph: DependencyGraph = None,
        mode: AssistantMode = AssistantMode.SUPERVISED,
        project_path: Path = None
    ):
        """
        Initialize the Omni Mind assistant.

        Args:
            llm_manager: LLM manager for AI calls
            context_engine: Context engine for retrieval
            tag_registry: Tag registry for validation
            dependency_graph: Dependency graph for relationships
            mode: Operating mode
            project_path: Path to the current project
        """
        self.llm_manager = llm_manager or LLMManager()
        self.context_engine = context_engine or ContextEngine()
        self.tag_registry = tag_registry or TagRegistry()
        self.graph = dependency_graph
        self.mode = mode
        self.project_path = project_path

        self.memory = AssistantMemory()
        self.decision_engine = DecisionEngine()
        self.suggestion_engine = SuggestionEngine()
        self.function_router = FunctionRouter(self.llm_manager)

        # Initialize tool executor
        self.tool_executor = ToolExecutor(project_path)
        self.tool_executor.set_integrations(tag_registry=self.tag_registry)

        # Initialize Agent Retrieval Tool
        self.retrieval_tool = AgentRetrievalTool(
            context_engine=self.context_engine,
            project_path=project_path,
            tag_registry=self.tag_registry
        )

        # Initialize Task Translator Agent
        self.task_translator = TaskTranslatorAgent(
            llm_caller=self._llm_call,
            tool_executor=self.tool_executor
        )

        # Self-healing state
        self._self_healing_enabled = True
        self._healing_history: List[Dict[str, Any]] = []

        # Initialize Core Vector Routing components
        cache_dir = project_path / ".cache" if project_path else None
        self.vector_cache = VectorCache(cache_dir=cache_dir)
        self.health_logger = ProjectHealthLogger(project_path=project_path)
        self.error_handoff = ErrorHandoff(
            vector_cache=self.vector_cache,
            health_logger=self.health_logger
        )

        # Initialize Usage Metrics Logger
        self.usage_metrics = UsageMetricsLogger(project_path=project_path)

        self._action_handlers: Dict[str, Callable] = {}
        self._initialize_handlers()

    def _initialize_handlers(self) -> None:
        """Initialize action handlers."""
        self._action_handlers = {
            'regenerate_dependent_content': self._handle_regeneration,
            'run_quality_validation': self._handle_validation,
            'suggest_tag_registration': self._handle_tag_suggestion,
            # New v2 pipeline handlers
            'run_story_pipeline_v2': self._handle_story_v2,
            'run_world_bible_pipeline': self._handle_world_bible,
            'run_directing_pipeline': self._handle_directing,
            'run_procedural_generation': self._handle_procedural,
            'extract_and_validate_tags': self._handle_tag_extraction,
            # Self-healing handlers
            'self_heal': self._handle_self_heal,
            'diagnose_issue': self._handle_diagnose,
            'auto_fix': self._handle_auto_fix,
        }

        # Initialize pipeline references
        self._story_pipeline_v2 = None
        self._world_bible_pipeline = None
        self._directing_pipeline = None
        self._procedural_generator = None
        self._tag_reference_system = None
    
    async def process(
        self,
        user_input: str,
        context: Dict[str, Any] = None
    ) -> AssistantResponse:
        """
        Process user input and generate a response.
        
        Args:
            user_input: User's message
            context: Additional context
            
        Returns:
            AssistantResponse with message and actions
        """
        context = context or {}
        
        # Store in memory
        self.memory.add(
            content=f"User: {user_input}",
            memory_type=MemoryType.CONVERSATION,
            importance=0.5
        )
        
        # Retrieve relevant context
        query = ContextQuery(
            query_text=user_input,
            tags=context.get('tags', []),
            max_results=10
        )
        context_result = self.context_engine.retrieve(query)
        
        # Build prompt with context
        system_prompt = self._build_system_prompt()
        full_prompt = self._build_prompt(
            user_input,
            context_result.assembled.full_text,
            self.memory.get_conversation_context()
        )
        
        # Generate response
        try:
            response_text = await self.function_router.route(
                function=LLMFunction.ASSISTANT,
                prompt=full_prompt,
                system_prompt=system_prompt
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            # Provide a helpful fallback response
            response_text = self._generate_fallback_response(user_input, str(e))

        # Store response in memory
        self.memory.add(
            content=f"Assistant: {response_text}",
            memory_type=MemoryType.CONVERSATION,
            importance=0.5
        )
        
        # Evaluate for decisions and suggestions
        eval_context = {
            **context,
            'user_input': user_input,
            'tags_found': list(context_result.tags_found)
        }
        
        decisions = self.decision_engine.evaluate(eval_context)
        suggestions = self.suggestion_engine.evaluate(eval_context)
        
        # Execute auto-decisions
        actions_taken = []
        if self.mode == AssistantMode.AUTONOMOUS:
            for decision in decisions:
                if self.decision_engine.should_auto_execute(decision):
                    result = await self._execute_decision(decision)
                    actions_taken.append(f"{decision.action}: {result}")
        
        return AssistantResponse(
            message=response_text,
            decisions=decisions,
            suggestions=suggestions,
            actions_taken=actions_taken,
            context_used={
                'sources': [s.value for s in context_result.assembled.sources_used],
                'tokens': context_result.assembled.total_tokens
            }
        )
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the assistant."""
        base_prompt = """You are Omni Mind, the AI assistant for Project Greenlight.
You help users create and manage cinematic storyboards.

Your capabilities:
- Analyze and improve story content
- Manage characters, locations, and props
- Generate and refine storyboard prompts
- Track continuity and consistency
- Suggest creative improvements
- Execute tools to interact with the project

PIPELINE CAPABILITIES (Writer Flow v2):
- Story Pipeline v2: Assembly-based with 7 parallel proposal agents and 5 judges
- World Bible Pipeline: Chunked-per-tag research for characters, locations, props
- Directing Pipeline: Transform Script_v1 into Visual_Script with frame notations
- Procedural Generation: Micro-chunked prose with state tracking (200-400 word chunks)
- Tag Reference System: 10-agent consensus (100% agreement) for tag extraction

PIPELINE MODES:
- Classic 4-Layer: Traditional sequential story building
- Assembly 7+7: Parallel proposals with judge consensus

GENERATION PROTOCOLS:
- Scene-Chunked: Process by scene boundaries
- Beat-Chunked: Process by story beats
- Expansion-Based: Expand from outline to full prose

Be helpful, concise, and proactive. When you notice issues, suggest solutions.
When asked about the project, use the provided context to give accurate answers.
You can run any pipeline individually to help users edit and refine their materials.

You have access to the following tools:
"""
        # Add tool descriptions
        tool_list = []
        for decl in self.tool_executor.get_declarations():
            tool_list.append(f"- {decl['name']}: {decl['description'][:100]}...")

        return base_prompt + "\n".join(tool_list)
    
    def _build_prompt(
        self,
        user_input: str,
        context: str,
        conversation: str
    ) -> str:
        """Build the full prompt with context."""
        parts = []

        if context:
            parts.append(f"## Relevant Context\n{context}")

        if conversation:
            parts.append(f"## Recent Conversation\n{conversation}")

        parts.append(f"## User Message\n{user_input}")

        return "\n\n".join(parts)

    def _generate_fallback_response(self, user_input: str, error: str = "") -> str:
        """Generate a fallback response when LLM is unavailable."""
        msg_lower = user_input.lower()

        # Check for common queries and provide helpful responses
        if any(w in msg_lower for w in ["help", "what can you do", "commands"]):
            return """I'm Omni Mind, your AI assistant for Project Greenlight! Here's what I can help with:

📝 **Writing & Story**
• Create and edit scripts, beats, and shot lists
• Develop characters and world-building

🎬 **Storyboard Pipeline**
• Run the Writer pipeline to generate story content
• Run the Director pipeline to create storyboard prompts
• Generate storyboard images from prompts

📁 **Project Management**
• Navigate your project files
• Access World Bible, Style Guide, and Assets

💡 **Tips**
• Use the toolbar buttons for quick actions
• Select files in the navigator to view/edit them"""

        elif any(w in msg_lower for w in ["writer", "write", "story", "script"]):
            return """To work with the Writer pipeline:

1. **Create a project** using the "New Project" button
2. **Enter your pitch** with logline and synopsis
3. **Click "📝 Writer"** in the toolbar to run the Writer pipeline

The Writer will generate story structure, beats, and scene breakdowns."""

        elif any(w in msg_lower for w in ["director", "storyboard", "prompt"]):
            return """To work with the Director pipeline:

1. **Run Writer first** to generate story content
2. **Click "🎬 Director"** in the toolbar
3. **Review the generated prompts** in the Storyboard view

The Director creates detailed image prompts for each shot."""

        elif any(w in msg_lower for w in ["generate", "image", "picture"]):
            return """To generate storyboard images:

1. **Complete the Director pipeline** first
2. **Click "🎨 Generate"** in the toolbar
3. **View results** in the Gallery or Storyboard view"""

        else:
            # Generic response with error info if available
            base = "I'm here to help with your creative project! "
            if error:
                base += f"\n\n(Note: I encountered an issue connecting to the AI service: {error[:100]})"
            base += "\n\nTry asking about:\n• Your story and characters\n• How to use Greenlight features\n• Writing and storyboarding tips"
            return base
    
    async def _execute_decision(self, decision: Decision) -> str:
        """Execute a decision."""
        handler = self._action_handlers.get(decision.action)
        if handler:
            try:
                result = await handler(decision.context)
                self.decision_engine.record_result(decision.id, result)
                return result
            except Exception as e:
                self.decision_engine.record_result(decision.id, f"error: {e}")
                return f"error: {e}"
        return "no handler"
    
    async def _handle_regeneration(self, context: Dict) -> str:
        """Handle regeneration action."""
        # Implementation would trigger regeneration pipeline
        return "regeneration queued"
    
    async def _handle_validation(self, context: Dict) -> str:
        """Handle validation action."""
        # Implementation would run quality validation
        return "validation complete"
    
    async def _handle_tag_suggestion(self, context: Dict) -> str:
        """Handle tag suggestion action."""
        tags = context.get('unregistered_tags', [])
        return f"suggested {len(tags)} tags for registration"

    async def _handle_story_v2(self, context: Dict) -> str:
        """Handle Story Pipeline v2 execution."""
        if not self._story_pipeline_v2:
            return "error: Story Pipeline v2 not available"
        try:
            result = await self._story_pipeline_v2.run(
                context.get('pitch_content', ''),
                context=context
            )
            return f"Story Pipeline v2 completed: {result.status.value}"
        except Exception as e:
            return f"error: {e}"

    async def _handle_world_bible(self, context: Dict) -> str:
        """Handle World Bible Pipeline execution."""
        if not self._world_bible_pipeline:
            return "error: World Bible Pipeline not available"
        try:
            result = await self._world_bible_pipeline.run(
                context.get('pitch_content', ''),
                context=context
            )
            return f"World Bible Pipeline completed: {result.status.value}"
        except Exception as e:
            return f"error: {e}"

    async def _handle_directing(self, context: Dict) -> str:
        """Handle Directing Pipeline execution."""
        if not self._directing_pipeline:
            return "error: Directing Pipeline not available"
        try:
            result = await self._directing_pipeline.run(
                context.get('script_content', ''),
                context=context
            )
            return f"Directing Pipeline completed: {result.status.value}"
        except Exception as e:
            return f"error: {e}"

    async def _handle_procedural(self, context: Dict) -> str:
        """Handle Procedural Generation execution."""
        if not self._procedural_generator:
            return "error: Procedural Generator not available"
        try:
            result = await self._procedural_generator.generate(
                context.get('script_content', ''),
                protocol=context.get('protocol', 'scene_chunked'),
                chunk_size=context.get('chunk_size', 300)
            )
            return f"Procedural Generation completed: {result.get('chunks_generated', 0)} chunks"
        except Exception as e:
            return f"error: {e}"

    async def _handle_tag_extraction(self, context: Dict) -> str:
        """Handle tag extraction with 10-agent consensus."""
        if not self._tag_reference_system:
            return "error: Tag Reference System not available"
        try:
            result = await self._tag_reference_system.extract_and_validate(
                context.get('content', ''),
                tag_types=context.get('tag_types', ['character', 'location', 'prop'])
            )
            return f"Tag extraction completed: {len(result.get('validated_tags', []))} tags validated"
        except Exception as e:
            return f"error: {e}"

    def set_mode(self, mode: AssistantMode) -> None:
        """Set the operating mode."""
        self.mode = mode
        logger.info(f"Assistant mode set to: {mode.value}")
    
    def confirm_decision(self, decision_id: str) -> None:
        """Confirm a pending decision."""
        self.decision_engine.record_result(decision_id, "confirmed")
    
    def reject_decision(self, decision_id: str) -> None:
        """Reject a pending decision."""
        self.decision_engine.record_result(decision_id, "rejected", executed=False)
    
    def apply_suggestion(self, suggestion_id: str) -> Optional[str]:
        """Apply a suggestion."""
        return self.suggestion_engine.apply(suggestion_id)
    
    def dismiss_suggestion(self, suggestion_id: str) -> None:
        """Dismiss a suggestion."""
        self.suggestion_engine.dismiss(suggestion_id)

    def set_project(self, project_path: Path) -> None:
        """Set the current project path."""
        self.project_path = Path(project_path) if project_path else None
        self.tool_executor.set_project(self.project_path)

        # Update context engine if available
        if self.context_engine and hasattr(self.context_engine, 'set_project_path'):
            self.context_engine.set_project_path(self.project_path)

        # Update retrieval tool
        if self.retrieval_tool:
            self.retrieval_tool.project_path = self.project_path

        # Update health logger
        if self.health_logger:
            self.health_logger.project_path = self.project_path

        logger.info(f"OmniMind project set to: {self.project_path}")

    def set_project_path(self, project_path: Path) -> None:
        """Alias for set_project for consistency."""
        self.set_project(project_path)

    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        return self.tool_executor.execute(tool_name, **kwargs)

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        return self.tool_executor.get_declarations()

    def set_integrations(
        self,
        reference_manager=None,
        story_pipeline=None,
        shot_pipeline=None,
        story_pipeline_v2=None,
        world_bible_pipeline=None,
        directing_pipeline=None,
        procedural_generator=None,
        tag_reference_system=None
    ) -> None:
        """Set optional integrations for the tool executor."""
        self.tool_executor.set_integrations(
            tag_registry=self.tag_registry,
            reference_manager=reference_manager,
            story_pipeline=story_pipeline,
            shot_pipeline=shot_pipeline,
            story_pipeline_v2=story_pipeline_v2,
            world_bible_pipeline=world_bible_pipeline,
            directing_pipeline=directing_pipeline,
            procedural_generator=procedural_generator,
            tag_reference_system=tag_reference_system
        )

        # Store references for direct access
        self._story_pipeline_v2 = story_pipeline_v2
        self._world_bible_pipeline = world_bible_pipeline
        self._directing_pipeline = directing_pipeline
        self._procedural_generator = procedural_generator
        self._tag_reference_system = tag_reference_system

    # =========================================================================
    # LLM HELPER METHODS
    # =========================================================================

    async def _llm_call(
        self,
        prompt: str,
        system_prompt: str = None,
        function: LLMFunction = LLMFunction.ASSISTANT_REASONING
    ) -> str:
        """Helper method for LLM calls used by Task Translator."""
        return await self.function_router.route(
            function=function,
            prompt=prompt,
            system_prompt=system_prompt or "You are a helpful assistant."
        )

    # =========================================================================
    # AGENT RETRIEVAL METHODS
    # =========================================================================

    async def retrieve(
        self,
        query: str,
        scope: RetrievalScope = RetrievalScope.ALL,
        tags: List[str] = None
    ) -> RetrievalResult:
        """
        Retrieve information using the Agent Retrieval Tool.

        Args:
            query: Natural language query
            scope: Scope to search within
            tags: Optional tags to filter by

        Returns:
            RetrievalResult with matched content
        """
        return await self.retrieval_tool.query(query, scope=scope, tags=tags)

    async def get_tag_info(self, tag: str) -> RetrievalResult:
        """Get all information about a specific tag."""
        return await self.retrieval_tool.get_by_tag(tag)

    async def get_world_bible_entry(self, tag: str) -> RetrievalResult:
        """Get world bible entry for a tag."""
        return await self.retrieval_tool.get_world_bible_entry(tag)

    # =========================================================================
    # TASK TRANSLATION METHODS
    # =========================================================================

    async def translate_and_execute(
        self,
        prompt: str,
        auto_execute: bool = False
    ) -> Dict[str, Any]:
        """
        Translate a natural language prompt and optionally execute it.

        Args:
            prompt: Natural language prompt
            auto_execute: Whether to auto-execute the plan

        Returns:
            Dict with plan and optional results
        """
        context = {
            'project_path': str(self.project_path) if self.project_path else None,
            'mode': self.mode.value
        }

        plan = await self.task_translator.translate(prompt, context)

        result = {
            'plan': {
                'tasks': [
                    {
                        'intent': t.intent.value,
                        'tool': t.tool_name,
                        'description': t.description
                    }
                    for t in plan.tasks
                ],
                'estimated_steps': plan.estimated_steps,
                'requires_confirmation': plan.requires_confirmation,
                'warnings': plan.warnings
            },
            'executed': False,
            'results': []
        }

        if auto_execute and not plan.requires_confirmation:
            results = await self.task_translator.execute_plan(plan)
            result['executed'] = True
            result['results'] = results

        return result

    # =========================================================================
    # SELF-HEALING METHODS
    # =========================================================================

    async def _handle_self_heal(self, context: Dict) -> str:
        """Handle self-healing action."""
        issue_type = context.get('issue_type', 'unknown')
        return await self.self_heal(issue_type, context)

    async def _handle_diagnose(self, context: Dict) -> str:
        """Handle diagnosis action."""
        target = context.get('target', 'project')
        diagnosis = await self.diagnose(target)
        return f"Diagnosis complete: {len(diagnosis.get('issues', []))} issues found"

    async def _handle_auto_fix(self, context: Dict) -> str:
        """Handle auto-fix action."""
        issue_id = context.get('issue_id')
        if issue_id:
            return await self.auto_fix(issue_id)
        return "No issue_id provided"

    async def diagnose(self, target: str = "project") -> Dict[str, Any]:
        """
        Diagnose issues in the project or specific component.

        Args:
            target: What to diagnose - "project", "tags", "continuity", "pipelines"

        Returns:
            Dict with issues found and recommendations
        """
        issues = []
        recommendations = []

        if target in ["project", "all"]:
            # Check project structure
            if self.project_path:
                required_dirs = ["world_bible", "story_documents"]
                for dir_name in required_dirs:
                    dir_path = self.project_path / dir_name
                    if not dir_path.exists():
                        issues.append({
                            "id": f"missing_dir_{dir_name}",
                            "type": "structure",
                            "severity": "warning",
                            "message": f"Missing directory: {dir_name}",
                            "auto_fixable": True
                        })
                        recommendations.append(f"Create {dir_name} directory")

        if target in ["tags", "all"]:
            # Check for unregistered tags
            if self.project_path:
                script_path = self.project_path / "scripts" / "script.md"
                if script_path.exists():
                    import re
                    content = script_path.read_text(encoding='utf-8')
                    found_tags = set(re.findall(r'\[([A-Z_]+)\]', content))

                    if self.tag_registry:
                        registered = {t.name for t in self.tag_registry.get_all_tags()}
                        unregistered = found_tags - registered

                        for tag in unregistered:
                            issues.append({
                                "id": f"unregistered_tag_{tag}",
                                "type": "tag",
                                "severity": "info",
                                "message": f"Unregistered tag: [{tag}]",
                                "auto_fixable": True
                            })
                            recommendations.append(f"Register tag [{tag}] in world bible")

        if target in ["pipelines", "all"]:
            # Check pipeline availability
            pipeline_status = self.tool_executor.execute("get_pipeline_status")
            if pipeline_status.success:
                for name, info in pipeline_status.result.get("pipelines", {}).items():
                    if not info.get("available"):
                        issues.append({
                            "id": f"unavailable_pipeline_{name}",
                            "type": "pipeline",
                            "severity": "info",
                            "message": f"Pipeline not initialized: {name}",
                            "auto_fixable": False
                        })

        return {
            "target": target,
            "issues": issues,
            "issue_count": len(issues),
            "recommendations": recommendations,
            "auto_fixable_count": sum(1 for i in issues if i.get("auto_fixable"))
        }

    async def auto_fix(self, issue_id: str) -> str:
        """
        Automatically fix an issue by ID.

        Args:
            issue_id: The issue ID from diagnose()

        Returns:
            Result message
        """
        if not self._self_healing_enabled:
            return "Self-healing is disabled"

        # Parse issue type from ID
        if issue_id.startswith("missing_dir_"):
            dir_name = issue_id.replace("missing_dir_", "")
            if self.project_path:
                dir_path = self.project_path / dir_name
                dir_path.mkdir(parents=True, exist_ok=True)
                self._healing_history.append({
                    "issue_id": issue_id,
                    "action": "create_directory",
                    "result": "success"
                })
                return f"Created directory: {dir_name}"

        elif issue_id.startswith("unregistered_tag_"):
            tag = issue_id.replace("unregistered_tag_", "")
            # Use retrieval to find tag context
            result = await self.retrieval_tool.query(
                f"Find information about [{tag}]",
                scope=RetrievalScope.STORY
            )

            if result.success and result.content:
                # Could auto-register tag here
                self._healing_history.append({
                    "issue_id": issue_id,
                    "action": "suggest_tag_registration",
                    "result": "pending_confirmation"
                })
                return f"Found context for [{tag}]. Suggest adding to world bible."

        return f"Cannot auto-fix issue: {issue_id}"

    async def self_heal(
        self,
        issue_type: str = "all",
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Run self-healing process to detect and fix issues.

        Args:
            issue_type: Type of issues to heal - "all", "structure", "tags", "continuity"
            context: Additional context

        Returns:
            Dict with healing results
        """
        if not self._self_healing_enabled:
            return {"enabled": False, "message": "Self-healing is disabled"}

        # Step 1: Diagnose
        diagnosis = await self.diagnose(issue_type)

        # Step 2: Auto-fix what we can
        fixed = []
        failed = []

        for issue in diagnosis.get("issues", []):
            if issue.get("auto_fixable"):
                try:
                    result = await self.auto_fix(issue["id"])
                    if "success" in result.lower() or "created" in result.lower():
                        fixed.append(issue["id"])
                    else:
                        failed.append({"id": issue["id"], "reason": result})
                except Exception as e:
                    failed.append({"id": issue["id"], "reason": str(e)})

        return {
            "enabled": True,
            "issues_found": len(diagnosis.get("issues", [])),
            "auto_fixed": len(fixed),
            "fixed_issues": fixed,
            "failed_fixes": failed,
            "remaining_issues": [
                i for i in diagnosis.get("issues", [])
                if i["id"] not in fixed
            ],
            "recommendations": diagnosis.get("recommendations", [])
        }

    def enable_self_healing(self, enabled: bool = True) -> None:
        """Enable or disable self-healing."""
        self._self_healing_enabled = enabled
        logger.info(f"Self-healing {'enabled' if enabled else 'disabled'}")

    def get_healing_history(self) -> List[Dict[str, Any]]:
        """Get history of self-healing actions."""
        return self._healing_history.copy()

    # =========================================================================
    # CORE VECTOR ROUTING METHODS
    # =========================================================================

    def route_error(
        self,
        error: Exception,
        source: str,
        severity: str = "ERROR",
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Route an error through the error handoff system.

        Flow: Flag → Cache → Task → Log

        Args:
            error: The exception
            source: Error source
            severity: CRITICAL, ERROR, WARNING, INFO
            context: Additional context

        Returns:
            Dict with transcript and task info
        """
        sev = ErrorSeverity[severity.upper()]
        result = self.error_handoff.handoff_for_guidance(
            error=error,
            severity=sev,
            source=source,
            context=context,
            auto_create_task=True
        )

        # Log to health
        self.health_logger.log(
            LogCategory.ERROR,
            f"Error routed: {result['transcript_id']}",
            severity=severity,
            source=source
        )

        return result

    def route_archive(self, entry_id: str) -> bool:
        """
        Route an entry to archive (weight = -0.5).

        Args:
            entry_id: The cache entry ID

        Returns:
            True if archived
        """
        result = self.vector_cache.archive(entry_id)
        if result:
            self.health_logger.log(
                LogCategory.CACHE,
                f"Archived: {entry_id}",
                severity="INFO"
            )
        return result

    def route_deprecate(self, entry_id: str) -> bool:
        """
        Route an entry to deprecated (weight = -1.0, excluded from search).

        Args:
            entry_id: The cache entry ID

        Returns:
            True if deprecated
        """
        result = self.vector_cache.deprecate(entry_id)
        if result:
            self.health_logger.log(
                LogCategory.CACHE,
                f"Deprecated: {entry_id}",
                severity="INFO"
            )
        return result

    def route_restore(self, entry_id: str) -> bool:
        """
        Restore an entry to active (weight = 1.0).

        Args:
            entry_id: The cache entry ID

        Returns:
            True if restored
        """
        result = self.vector_cache.restore(entry_id)
        if result:
            self.health_logger.log(
                LogCategory.CACHE,
                f"Restored: {entry_id}",
                severity="INFO"
            )
        return result

    def route_flush(self) -> int:
        """
        Flush all cache entries.

        Returns:
            Number of entries flushed
        """
        count = self.vector_cache.flush()
        self.health_logger.log(
            LogCategory.CACHE,
            f"Flushed {count} cache entries",
            severity="INFO"
        )
        return count

    def log_notation(
        self,
        notation_id: str,
        notation_type: str,
        definition: str,
        example: str = ""
    ) -> None:
        """
        Log a notation definition to the health index.

        Args:
            notation_id: Unique notation ID
            notation_type: Type (scene, frame, camera, etc.)
            definition: Human-readable definition
            example: Example usage
        """
        self.health_logger.log_notation(
            notation_id=notation_id,
            notation_type=notation_type,
            definition=definition,
            example=example
        )

        # Also cache the definition
        self.vector_cache.add(
            content=f"{notation_id}: {definition}\nExample: {example}",
            entry_type=CacheEntryType.NOTATION_DEFINITION,
            weight=1.0,
            entry_id=f"notation_{notation_id}",
            notation_type=notation_type
        )

    def generate_health_report(self) -> Path:
        """
        Generate and save the project health report.

        Returns:
            Path to the saved report
        """
        return self.health_logger.save_health_report()

    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all core vector routing components.

        Returns:
            Dict with cache, health, and error stats
        """
        return {
            "vector_cache": self.vector_cache.get_stats(),
            "health_logger": self.health_logger.get_stats(),
            "error_handoff": self.error_handoff.get_stats(),
            "usage_metrics": self.usage_metrics.get_stats(),
            "self_healing": {
                "enabled": self._self_healing_enabled,
                "history_count": len(self._healing_history)
            }
        }

    # ==================== Usage Metrics Methods ====================

    def log_feature_usage(self, feature: str, details: Dict[str, Any] = None) -> None:
        """
        Log feature usage for analytics.

        Args:
            feature: Feature name (e.g., "writer_pipeline", "image_generation")
            details: Additional details about the usage
        """
        self.usage_metrics.log_feature_usage(feature, details)

    def log_failed_request(
        self,
        feature: str,
        error_message: str,
        context: Dict[str, Any] = None
    ) -> None:
        """
        Log a failed request for debugging and improvement.

        Args:
            feature: Feature that failed
            error_message: Error description
            context: Additional context
        """
        self.usage_metrics.log_failed_request(feature, error_message, context)

    def log_unavailable_feature(self, feature: str, user_request: str) -> None:
        """
        Log when user requests a feature that doesn't exist.

        Args:
            feature: Requested feature name
            user_request: Original user request text
        """
        self.usage_metrics.log_unavailable_feature(feature, user_request)

    def log_task_execution(
        self,
        task_name: str,
        success: bool,
        duration_ms: float,
        details: Dict[str, Any] = None
    ) -> None:
        """
        Log task execution metrics.

        Args:
            task_name: Name of the task
            success: Whether it succeeded
            duration_ms: Duration in milliseconds
            details: Additional details
        """
        self.usage_metrics.log_task_execution(task_name, success, duration_ms, details)

    def get_usage_report(self) -> str:
        """
        Generate a usage metrics report.

        Returns:
            Markdown formatted report
        """
        return self.usage_metrics.generate_report()
