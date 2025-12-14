"""
Greenlight Assistant Bridge

Greenlight-specific assistant bridge that integrates with Agnostic_Core_OS
for background LLM processing and context-aware responses.

This bridge:
- Wraps the Agnostic_Core_OS AssistantBridge
- Adds Greenlight-specific context (project, world bible, etc.)
- Integrates with Greenlight's LLM manager and function router
- Provides UI-friendly callbacks for response delivery
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
from pathlib import Path
from datetime import datetime
import asyncio
import logging

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger

# Import process library and monitor
from greenlight.omni_mind.process_library import ProcessLibrary, ProcessCategory
from greenlight.omni_mind.process_monitor import ProcessMonitor, get_process_monitor
from greenlight.omni_mind.conversation_manager import (
    ConversationManager, MessageRole, ContextType
)
from greenlight.omni_mind.project_primer import ProjectPrimer
from greenlight.omni_mind.symbolic_registry import SymbolicRegistry, SymbolOrigin
from greenlight.config.api_dictionary import (
    lookup_model, lookup_by_symbol, get_image_models, get_model_summary,
    MODEL_SYMBOLS, ALL_MODELS
)

# Import from Agnostic_Core_OS
try:
    from Agnostic_Core_OS.protocols import (
        AssistantBridge as CoreBridge,
        BridgeConfig as CoreBridgeConfig,
        BridgeResponse,
        RequestIntent,
        RequestPriority,
    )
    from Agnostic_Core_OS.protocols.llm_handshake import LLMHandshake, HandshakeConfig
    HAS_CORE_BRIDGE = True
except ImportError:
    HAS_CORE_BRIDGE = False
    CoreBridge = None
    CoreBridgeConfig = None

if TYPE_CHECKING:
    from greenlight.llm import LLMManager, FunctionRouter
    from greenlight.context import ContextEngine

logger = get_logger("omni_mind.assistant_bridge")


@dataclass
class GreenlightBridgeConfig:
    """Configuration for Greenlight assistant bridge."""
    max_workers: int = 4
    queue_size: int = 100
    default_timeout: float = 30.0
    enable_caching: bool = True
    log_requests: bool = True
    # Greenlight-specific
    use_context_engine: bool = True
    include_world_bible: bool = True
    include_project_context: bool = True
    llm_function: LLMFunction = LLMFunction.ASSISTANT


class LLMClientAdapter:
    """Adapter to make Greenlight's FunctionRouter work with LLMHandshake."""
    
    def __init__(
        self,
        function_router: "FunctionRouter",
        function: LLMFunction = LLMFunction.ASSISTANT
    ):
        self.function_router = function_router
        self.function = function
    
    async def generate(
        self,
        prompt: str,
        system: str = "",
        **kwargs
    ) -> "TextResponse":
        """Generate response using function router."""
        response_text = await self.function_router.route(
            function=self.function,
            prompt=prompt,
            system_prompt=system,
            **kwargs
        )
        return TextResponse(text=response_text)


@dataclass
class TextResponse:
    """Simple text response wrapper."""
    text: str


class GreenlightAssistantBridge:
    """
    Greenlight-specific assistant bridge.
    
    Wraps Agnostic_Core_OS AssistantBridge with Greenlight integrations:
    - LLM Manager and Function Router
    - Context Engine for retrieval
    - Project-specific context loading
    - World Bible integration
    
    Usage:
        bridge = GreenlightAssistantBridge(config)
        bridge.initialize(llm_manager, context_engine, project_path)
        bridge.set_response_callback(on_response)
        bridge.start()
        
        bridge.submit("What is Mei's motivation?")
    """
    
    def __init__(self, config: Optional[GreenlightBridgeConfig] = None):
        """Initialize the Greenlight assistant bridge."""
        self.config = config or GreenlightBridgeConfig()
        
        self._llm_manager: Optional["LLMManager"] = None
        self._function_router: Optional["FunctionRouter"] = None
        self._context_engine: Optional["ContextEngine"] = None
        self._project_path: Optional[Path] = None

        # Core bridge from Agnostic_Core_OS
        self._core_bridge: Optional[CoreBridge] = None

        # Process library and monitor
        self._process_library: Optional[ProcessLibrary] = None
        self._process_monitor: Optional[ProcessMonitor] = None
        self._tool_executor = None

        # Conversation manager for history and context
        self._conversation_manager: Optional[ConversationManager] = None

        # Project primer and symbolic registry
        self._project_primer: Optional[ProjectPrimer] = None
        self._symbolic_registry: Optional[SymbolicRegistry] = None

        # Callbacks
        self._response_callback: Optional[Callable[[str], None]] = None
        self._error_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[float, str], None]] = None

        self._initialized = False
        logger.info("GreenlightAssistantBridge created")
    
    def initialize(
        self,
        llm_manager: "LLMManager" = None,
        function_router: "FunctionRouter" = None,
        context_engine: "ContextEngine" = None,
        project_path: Path = None
    ) -> bool:
        """
        Initialize the bridge with Greenlight components.
        
        Args:
            llm_manager: Greenlight LLM manager
            function_router: Function router for LLM calls
            context_engine: Context engine for retrieval
            project_path: Current project path
            
        Returns:
            True if initialization successful
        """
        self._llm_manager = llm_manager
        self._function_router = function_router
        self._context_engine = context_engine
        self._project_path = project_path
        
        if not HAS_CORE_BRIDGE:
            logger.warning("Agnostic_Core_OS bridge not available, using fallback")
            self._initialized = True
            return True
        
        # Create core bridge config
        core_config = CoreBridgeConfig(
            max_workers=self.config.max_workers,
            queue_size=self.config.queue_size,
            default_timeout=self.config.default_timeout,
            enable_caching=self.config.enable_caching,
            log_requests=self.config.log_requests
        )
        
        # Create handshake with system prompt
        handshake_config = HandshakeConfig(
            system_prompt_template=self._build_system_prompt()
        )
        handshake = LLMHandshake(config=handshake_config)
        
        # Create LLM client adapter
        if function_router:
            llm_adapter = LLMClientAdapter(
                function_router,
                self.config.llm_function
            )
            handshake.set_llm_client(llm_adapter)
        
        # Create core bridge
        self._core_bridge = CoreBridge(
            config=core_config,
            handshake=handshake
        )
        
        # Set context engine
        if context_engine:
            self._core_bridge.set_context_engine(context_engine)
        
        # Set response callback wrapper
        self._core_bridge.set_response_callback(self._on_core_response)
        self._core_bridge.set_error_callback(self._on_core_error)
        
        # Initialize process library and monitor
        self._process_library = ProcessLibrary()
        self._process_library.set_project(project_path)
        self._process_monitor = get_process_monitor()

        # Initialize conversation manager with project context
        self._conversation_manager = ConversationManager(
            project_path=project_path,
            max_history=100,
            max_memory_vectors=500,
            scrub_after_hours=24
        )

        # Initialize project primer and symbolic registry
        if project_path:
            self._project_primer = ProjectPrimer(project_path)
            self._project_primer.build_index()

            self._symbolic_registry = SymbolicRegistry(project_path)

            # Learn symbols from project files
            self._learn_project_symbols()

            # Log project context loading
            context_summary = self._conversation_manager.get_project_context_summary()
            primer_stats = self._project_primer.get_stats()
            registry_stats = self._symbolic_registry.get_stats()

            logger.info(f"Project context loaded: {len(context_summary)} chars")
            logger.info(f"Project primer: {primer_stats['total_entries']} entries, {primer_stats['valid_paths']} valid")
            logger.info(f"Symbolic registry: {registry_stats['total_symbols']} symbols")

        self._initialized = True
        logger.info("GreenlightAssistantBridge initialized")
        return True

    def _learn_project_symbols(self) -> None:
        """Learn symbols from project content."""
        if not self._symbolic_registry or not self._project_primer:
            return

        # Register symbols from primer index
        for symbol, entry in self._project_primer.index.items():
            if not self._symbolic_registry.exists(symbol):
                self._symbolic_registry.register(
                    symbol=symbol,
                    notation_type=entry.symbol_type.value,
                    scope="project",
                    definition=entry.description,
                    pattern=symbol,
                    origin=SymbolOrigin.PROJECT
                )

        # Learn from pitch content if available
        if self._conversation_manager and self._conversation_manager._project_context:
            pitch = self._conversation_manager._project_context.pitch
            if pitch:
                self._symbolic_registry.learn_from_text(pitch, "pitch")

    def set_tool_executor(self, executor) -> None:
        """Set the tool executor for process execution."""
        self._tool_executor = executor
        if self._process_library:
            self._process_library.set_tool_executor(executor)

    def set_progress_callback(self, callback: Callable[[float, str], None]) -> None:
        """Set callback for progress updates."""
        self._progress_callback = callback

    def _get_cypher_excerpt(self) -> str:
        """Get abbreviated cypher for system prompt (key parts only)."""
        return """### Symbol Prefixes
| `@` | Entity reference (character, location, file) |
| `#` | Scope filter (category) |
| `>` | Execute command/process |
| `?` | Natural language query |
| `+` | Include in results |
| `-` | Exclude from results |
| `~` | Semantic similarity search |

### Quick Examples
- `@CHAR_MEI` - Reference character Mei
- `#WORLD_BIBLE` - Search in world bible
- `>run_writer` - Run Writer pipeline
- `~"honor"` - Find similar concepts

### Self-Healing
If you reference a missing symbol, it will be auto-registered.
Use `>diagnose` to check issues, `>heal` to fix them."""

    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt with Greenlight context."""
        project_name = self._project_path.name if self._project_path else "Unknown Project"

        # Get project context from conversation manager
        project_context = ""
        quick_dirs = ""
        if self._conversation_manager:
            project_context = self._conversation_manager.get_project_context_summary()
            dirs = self._conversation_manager.get_quick_context_directories()
            if dirs:
                quick_dirs = "\n".join([f"- `{k}` - {v}" for k, v in dirs.items()])

        # Get symbolic index and cypher from primer
        symbolic_index = ""
        cypher_excerpt = ""
        if self._project_primer:
            symbolic_index = self._project_primer.get_symbolic_index_prompt()
            # Get abbreviated cypher (just the key parts)
            cypher_excerpt = self._get_cypher_excerpt()

        # Get symbol glossary from registry
        symbol_glossary = ""
        if self._symbolic_registry:
            symbol_glossary = self._symbolic_registry.get_symbol_glossary()

        return f'''You are Omni Mind, the intelligent AI assistant for Project Greenlight - a creative storyboard and narrative development platform.

## Current Project: {project_name}

## SYMBOLIC NOTATION SYSTEM
{cypher_excerpt if cypher_excerpt else "Use @ for entities, # for scopes, > for commands, ? for queries."}

## PROJECT SYMBOLIC INDEX
{symbolic_index if symbolic_index else "No project loaded."}

## SYMBOL GLOSSARY
{symbol_glossary if symbol_glossary else "No symbols registered."}

## Project Directory Structure
{quick_dirs if quick_dirs else "No project loaded."}

## Loaded Project Context
{project_context if project_context else "No project context loaded. Please open a project first."}

## Your Core Capabilities

### 1. PROCESS EXECUTION (Natural Language Commands)
You can execute these processes when the user asks:
- "run writer" / "start writer pipeline" → Runs the Writer pipeline to generate story content
- "run director" / "start director" → Runs the Director pipeline for visual storyboarding
- "run tests" / "test everything" → Runs all project tests
- "diagnose" / "check project" → Runs project diagnostics
- "analyze tags" → Validates and analyzes project tags
- "run full pipeline" → Runs complete Writer → Director pipeline

### 2. CONTENT MODIFICATION (RAG-Powered)
You can find and modify content across the entire project:
- "change [character]'s description to..." → Updates character in world bible AND all scripts
- "update [location] details..." → Modifies location across all documents
- "rename [tag] to..." → Renames tags throughout the project
- "add trait to [character]..." → Adds traits to character definitions

When modifying content, you will:
1. Search all project files using the Context Engine
2. Find every occurrence using vector similarity and keyword search
3. Apply changes consistently across: world_bible/, story_documents/, scripts/
4. Report what was changed and where

### 3. NAVIGATION GUIDANCE (UI Pointer System)
Guide users through the Greenlight workflow by highlighting UI elements:
- Use `point_to_ui` tool to highlight buttons with neon green glow
- Available elements: world_bible_step, writer_step, director_step, review_step, export_step
- Also: writer_toolbar_btn, director_toolbar_btn, generate_toolbar_btn

Workflow steps:
- World Bible → Define characters, locations, props
- Writer Pipeline → Generate story scripts
- Director Pipeline → Create visual storyboards
- Review & Export → Finalize and export content

When guiding users, HIGHLIGHT the relevant button to show them where to click.

### 4. CREATIVE ASSISTANCE
- Answer questions about story, characters, world
- Provide writing suggestions and creative guidance
- Help with character development and plot structure
- Suggest improvements to dialogue and descriptions

### 5. DOCUMENT CHANGE DETECTION (Auto-Save System)
You automatically detect when users modify documents. When changes are detected:
- Use `get_pending_changes` to see what files have been modified
- Prompt the user: "I noticed you made changes to [files]. Would you like to save or revert?"
- Use `save_document_changes` when user confirms save
- Use `revert_document_changes` when user wants to undo changes

When user says "save", "yes save", "save changes" → call save_document_changes
When user says "revert", "undo", "cancel changes" → call revert_document_changes
When user says "keep editing", "not yet", "later" → acknowledge and wait

### 6. ERROR REPORTING & SELF-HEALING (Augment Integration)
You have a self-healing system that can automatically fix common errors and generate reports for Augment:

**Self-Healing Capabilities:**
- Missing directories → Auto-create
- Missing files → Defer to Augment with template
- API rate limits → Exponential backoff retry
- Connection errors → Auto-retry with backoff
- Notation format errors → Convert old {frame_X.Y} to [X.Y.cA] format
- Missing consensus characters → Auto-generate profiles from story context
- JSON parse errors → Repair trailing commas, quote issues
- Missing config keys → Add defaults (visual_style, lighting, vibe, etc.)
- UI widget errors → Log as cosmetic (Tkinter race conditions, non-blocking)

**Error Reporting Tools:**
- `report_error` - Report an error with full context for Augment to fix
- `get_error_reports` - Get recent error reports for review
- `run_self_heal` - Attempt self-healing on pending errors
- `get_healing_stats` - View self-healing success rates
- `export_error_for_augment` - Export error in Augment-optimized format

**Backdoor Self-Healing Commands (via port 19847):**
- `get_errors` - Get cached errors with healer stats
- `clear_errors` - Clear the error cache
- `self_heal` - Trigger self-healing for cached errors
- `get_healer_report` - Get full healing report with history

**When errors occur:**
1. First attempt self-healing automatically
2. If self-healing succeeds, inform user: "✅ Issue auto-fixed: [action taken]"
3. If self-healing fails, generate Augment transcript and inform user:
   "📋 Error reported for Augment. ID: [error_id]. Suggested fixes: [list]"

**Transcript Levels (for credit optimization):**
- `minimal` - Error + location only (saves Augment credits for simple fixes)
- `standard` - + stack trace + suggestions (default)
- `full` - + code context + dependencies (for complex issues)

### 7. IMAGE GENERATION (API Models)
You can generate images using various AI models. Use symbolic notation:

**Image Models:**
- `@IMG_NANO_BANANA` - Gemini 2.5 Flash Image (fast, Google)
- `@IMG_NANO_BANANA_PRO` - Gemini 3 Pro Image (highest quality, Google)
- `@IMG_SEEDREAM` - Seedream 4.5 (ByteDance via Replicate)
- `@IMG_FLUX_KONTEXT` - FLUX Kontext Pro (context-aware editing)
- `@IMG_FLUX_MAX` - FLUX Kontext Max (highest quality FLUX)

**Usage:** When user asks to generate an image, use the appropriate model.
Example: "generate a stoplight icon using nano banana pro"

## Context Vectors Loaded
{{context_vectors}}

## Response Guidelines
1. Be helpful, concise, and action-oriented
2. When user asks to modify content, confirm what will be changed before executing
3. Reference specific characters, locations, or story elements from loaded context
4. Suggest logical next steps in the workflow
5. For commands, acknowledge and execute; for questions, provide detailed answers
6. Use markdown formatting for clarity
7. When you detect document changes, proactively ask about saving

## Command Detection
If the user's message matches a process command, execute it immediately.
If the user asks to modify content, use the content modification system.
If the user responds to a save/revert prompt, handle it appropriately.
Otherwise, provide a helpful conversational response.

Respond naturally and helpfully to the user's request.'''
    
    def start(self) -> None:
        """Start the background processing."""
        if self._core_bridge:
            self._core_bridge.start()
        logger.info("GreenlightAssistantBridge started")
    
    def stop(self) -> None:
        """Stop the background processing."""
        if self._core_bridge:
            self._core_bridge.stop()
        logger.info("GreenlightAssistantBridge stopped")

    def set_project_path(self, project_path: Path) -> None:
        """Update the project path for context-aware responses."""
        self._project_path = project_path

        # Update process library
        if self._process_library:
            self._process_library.set_project(project_path)

        # Update context engine
        if self._context_engine and hasattr(self._context_engine, 'set_project_path'):
            self._context_engine.set_project_path(project_path)

        # Reload conversation manager with new project context
        if self._conversation_manager:
            self._conversation_manager.set_project_path(project_path)
            context_summary = self._conversation_manager.get_project_context_summary()
            logger.info(f"Reloaded project context: {len(context_summary)} chars")
        else:
            # Create new conversation manager if not exists
            self._conversation_manager = ConversationManager(
                project_path=project_path,
                max_history=100,
                max_memory_vectors=500,
                scrub_after_hours=24
            )
            logger.info("Created new ConversationManager for project")

        # Rebuild project primer and symbolic registry
        if project_path:
            self._project_primer = ProjectPrimer(project_path)
            self._project_primer.build_index()

            # Attempt to heal any broken paths
            healed = self._project_primer.heal_broken_paths()
            if healed:
                logger.info(f"Self-healed {len(healed)} broken paths")

            # Save primer for reference
            self._project_primer.save_primer()

            self._symbolic_registry = SymbolicRegistry(project_path)
            self._learn_project_symbols()

            primer_stats = self._project_primer.get_stats()
            registry_stats = self._symbolic_registry.get_stats()
            logger.info(f"Project primer rebuilt: {primer_stats['total_entries']} entries")
            logger.info(f"Symbolic registry: {registry_stats['total_symbols']} symbols")

        logger.info(f"AssistantBridge project path updated to: {project_path}")

    def set_response_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for response delivery (message text only)."""
        self._response_callback = callback
    
    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for error delivery."""
        self._error_callback = callback

    def try_execute_process(self, message: str) -> Optional[str]:
        """
        Try to match and execute a process from natural language.

        Args:
            message: Natural language message

        Returns:
            Response message if process was executed, None otherwise
        """
        if not self._process_library:
            return None

        # Try to match a process
        process = self._process_library.match(message)
        if not process:
            return None

        logger.info(f"Matched process: {process.id} from message: {message}")

        # Check if confirmation is required
        if process.requires_confirmation:
            return f"⚠️ **{process.name}** requires confirmation.\n\nThis will: {process.description}\n\nEstimated duration: {process.estimated_duration}\n\nType 'yes' or 'confirm' to proceed."

        # Execute the process
        return self._execute_process(process)

    def _execute_process(self, process) -> str:
        """Execute a matched process and return response."""
        import uuid

        # Track in monitor
        process_id = str(uuid.uuid4())[:8]
        if self._process_monitor:
            self._process_monitor.track(process_id, process.name)

        try:
            # Progress callback
            def on_progress(progress: float, message: str):
                if self._process_monitor:
                    self._process_monitor.update_progress(process_id, progress, message)
                if self._progress_callback:
                    self._progress_callback(progress, message)

            # Execute via process library
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            execution = loop.run_until_complete(
                self._process_library.execute(process, progress_callback=on_progress)
            )

            # Update monitor
            if self._process_monitor:
                if execution.status.value == "completed":
                    self._process_monitor.complete(process_id, execution.result)
                else:
                    self._process_monitor.fail(process_id, execution.error or "Unknown error")

            # Format response
            if execution.status.value == "completed":
                return f"✅ **{process.name}** completed successfully!\n\n{self._format_result(execution.result)}"
            else:
                return f"❌ **{process.name}** failed.\n\nError: {execution.error}"

        except Exception as e:
            logger.error(f"Process execution error: {e}")
            if self._process_monitor:
                self._process_monitor.fail(process_id, str(e))
            return f"❌ Error executing **{process.name}**: {str(e)}"

    def _format_result(self, result: Any) -> str:
        """Format a process result for display."""
        if result is None:
            return "Process completed."

        if isinstance(result, dict):
            lines = []
            for key, value in result.items():
                if key in ["output", "logs", "result"]:
                    continue  # Skip verbose fields
                lines.append(f"• **{key}**: {value}")
            return "\n".join(lines) if lines else "Process completed."

        return str(result)[:500]

    def get_available_processes(self) -> str:
        """Get a formatted list of available processes."""
        if not self._process_library:
            return "Process library not initialized."
        return self._process_library.format_process_list()

    def submit(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        priority: str = "normal"
    ) -> Optional[str]:
        """
        Submit a message for processing.
        
        Args:
            message: User's message
            context: Additional context
            priority: Priority level (low, normal, high, critical)
            
        Returns:
            Request ID or None if not initialized
        """
        if not self._initialized:
            logger.error("Bridge not initialized")
            if self._error_callback:
                self._error_callback("Assistant not initialized. Please try again.")
            return None

        # Log user message to conversation history
        if self._conversation_manager:
            self._conversation_manager.add_user_message(message)
            logger.debug(f"Logged user message: {message[:50]}...")

        # First, try to match and execute a process
        process_response = self.try_execute_process(message)
        if process_response:
            # Log process response
            if self._conversation_manager:
                self._conversation_manager.add_assistant_message(
                    process_response,
                    context_used={"type": "process_execution"}
                )
            if self._response_callback:
                self._response_callback(process_response)
            return "process_executed"

        # Build context with project info
        full_context = context or {}
        if self._project_path:
            full_context["project_path"] = str(self._project_path)

        # Add conversation history to context
        if self._conversation_manager:
            full_context["conversation_history"] = self._conversation_manager.get_history_for_prompt(10)
            full_context["project_context"] = self._conversation_manager.get_project_context_summary()

        # Load world bible context if enabled
        if self.config.include_world_bible and self._context_engine:
            try:
                world_context = self._get_world_context(message)
                full_context.update(world_context)
            except Exception as e:
                logger.warning(f"Failed to load world context: {e}")
        
        if self._core_bridge:
            # Use core bridge
            priority_map = {
                "low": RequestPriority.LOW,
                "normal": RequestPriority.NORMAL,
                "high": RequestPriority.HIGH,
                "critical": RequestPriority.CRITICAL
            }
            return self._core_bridge.submit(
                message,
                context=full_context,
                priority=priority_map.get(priority, RequestPriority.NORMAL)
            )
        else:
            # Fallback: process directly
            asyncio.get_event_loop().run_in_executor(
                None,
                self._process_fallback,
                message,
                full_context
            )
            return "fallback"
    
    def _get_world_context(self, query: str) -> Dict[str, Any]:
        """Get relevant world context for the query."""
        context = {}
        
        if self._context_engine and hasattr(self._context_engine, 'retrieve'):
            try:
                from greenlight.context import ContextQuery
                result = self._context_engine.retrieve(ContextQuery(
                    query_text=query,
                    max_results=5
                ))
                if result and hasattr(result, 'assembled'):
                    context["world_context"] = result.assembled.full_text[:2000]
            except Exception as e:
                logger.debug(f"Context retrieval failed: {e}")
        
        return context
    
    def _on_core_response(self, response: BridgeResponse) -> None:
        """Handle response from core bridge."""
        # Log assistant response to conversation history
        if self._conversation_manager:
            self._conversation_manager.add_assistant_message(
                response.message,
                context_used=response.data if hasattr(response, 'data') else {},
                tokens_used=response.data.get("tokens_used", 0) if hasattr(response, 'data') and response.data else 0,
                duration_ms=response.duration_ms if hasattr(response, 'duration_ms') else 0.0
            )
            logger.debug(f"Logged assistant response: {response.message[:50]}...")

        if self._response_callback:
            self._response_callback(response.message)

    def _on_core_error(self, request_id: str, error: Exception) -> None:
        """Handle error from core bridge."""
        # Log error to conversation history
        if self._conversation_manager:
            self._conversation_manager.add_message(
                MessageRole.SYSTEM,
                f"Error: {str(error)}",
                context_used={"request_id": request_id, "error_type": type(error).__name__}
            )

        if self._error_callback:
            self._error_callback(f"Error: {str(error)}")

    def _process_fallback(self, message: str, context: Dict) -> None:
        """Fallback processing when core bridge not available."""
        # Simple keyword-based responses
        response = self._generate_fallback_response(message, context)

        # Log fallback response
        if self._conversation_manager:
            self._conversation_manager.add_assistant_message(
                response,
                context_used={"type": "fallback"}
            )

        if self._response_callback:
            self._response_callback(response)
    
    def _generate_fallback_response(self, message: str, context: Dict = None) -> str:
        """Generate a fallback response based on keywords and project context."""
        msg_lower = message.lower()
        context = context or {}

        # Check for project context to provide informed responses
        project_context = context.get("project_context", "")

        if any(w in msg_lower for w in ["help", "what can you do"]):
            return self._get_help_response()
        elif any(w in msg_lower for w in ["pitch", "about the project", "what is this project"]):
            return self._get_pitch_response(project_context)
        elif any(w in msg_lower for w in ["writer", "write", "story"]):
            return self._get_writer_response(project_context)
        elif any(w in msg_lower for w in ["director", "storyboard"]):
            return self._get_director_response()
        elif any(w in msg_lower for w in ["character", "who is"]):
            return self._get_character_response(project_context)
        else:
            return self._get_default_response(project_context)

    def _get_pitch_response(self, project_context: str = "") -> str:
        """Get response about the project pitch."""
        if project_context and "## Project Pitch" in project_context:
            # Extract pitch from context
            pitch_start = project_context.find("## Project Pitch")
            pitch_end = project_context.find("##", pitch_start + 1)
            if pitch_end == -1:
                pitch_end = len(project_context)
            pitch = project_context[pitch_start:pitch_end].strip()
            return f"Here's what I know about this project:\n\n{pitch}"
        return "No pitch loaded. Please open a project to see its details."
    
    def _get_help_response(self) -> str:
        return """I'm Omni Mind, your AI assistant for Project Greenlight!

📝 **Writing & Story** - Ask about characters, plot, or world-building
🎬 **Storyboard** - Help with visual storytelling and prompts
🔍 **Search** - Find information in your project
💡 **Tips** - Get suggestions and guidance

**Commands I understand:**
- "run writer" - Start the Writer pipeline
- "run director" - Start the Director pipeline
- "tell me about the pitch" - Show project pitch
- "who is [character]?" - Character info

What would you like help with?"""

    def _get_writer_response(self, project_context: str = "") -> str:
        """Get writer response with project context."""
        base = """To work with the Writer pipeline:

1. Open or create a project
2. Say **"run writer"** or click 📝 Writer in the toolbar
3. The Writer will generate story content from your pitch

The Writer creates story structure, beats, and scene breakdowns."""

        # If we have pitch context, mention it
        if project_context and "## Project Pitch" in project_context:
            base += "\n\n✅ **I have your pitch loaded** - I can run the writer pipeline now. Just say 'run writer'!"

        return base

    def _get_director_response(self) -> str:
        return """To work with the Director pipeline:

1. Run the Writer pipeline first
2. Say **"run director"** or click 🎬 Director in the toolbar
3. Review the generated storyboard prompts
4. Use **🎨 Generate** to create images

The Director creates detailed visual prompts for each shot."""

    def _get_character_response(self, project_context: str = "") -> str:
        """Get character response with project context."""
        base = """To learn about characters in your project:

1. Check the **World** tab for character cards
2. Look in the World Bible for detailed descriptions
3. Ask me specific questions like "Who is [character name]?"

I can help you explore character motivations, relationships, and arcs."""

        # If we have character info in context, show it
        if project_context and "**Characters:**" in project_context:
            char_start = project_context.find("**Characters:**")
            char_end = project_context.find("\n", char_start)
            if char_end > char_start:
                chars = project_context[char_start:char_end]
                base += f"\n\n📋 **Loaded characters:** {chars.replace('**Characters:**', '').strip()}"

        return base

    def _get_default_response(self, project_context: str = "") -> str:
        """Get default response with project awareness."""
        if project_context:
            return f"""I'm here to help with your creative project!

✅ **Project context loaded** - I know about your pitch, characters, and world.

You can ask me:
• "Tell me about the pitch" - See your project overview
• "Run writer" - Generate story content
• "Run director" - Create storyboards
• Questions about your characters or story

What would you like to do?"""
        else:
            return """I'm here to help with your creative project!

⚠️ **No project loaded** - Please open a project first.

Once you have a project open, I can:
• Answer questions about your story and characters
• Run the Writer and Director pipelines
• Help with world-building and creative decisions

What would you like to know?"""
    
    @property
    def is_initialized(self) -> bool:
        """Check if bridge is initialized."""
        return self._initialized
    
    @property
    def is_running(self) -> bool:
        """Check if bridge is running."""
        if self._core_bridge:
            return self._core_bridge._running
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        stats = {
            "running": self._initialized,
            "mode": "fallback" if not HAS_CORE_BRIDGE else "core",
            "project": str(self._project_path) if self._project_path else None
        }

        if self._core_bridge:
            stats.update(self._core_bridge.get_stats())

        # Add conversation stats
        if self._conversation_manager:
            stats["conversation"] = self._conversation_manager.get_stats()

        return stats

    def get_conversation_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get conversation history as list of dicts."""
        if self._conversation_manager:
            return self._conversation_manager.get_history_dict()[-limit:] if limit else self._conversation_manager.get_history_dict()
        return []

    def scrub_old_data(self, hours: int = 24) -> Dict[str, int]:
        """Scrub old messages and memory vectors."""
        if self._conversation_manager:
            return self._conversation_manager.scrub_all(hours)
        return {"messages_removed": 0, "vectors_removed": 0}

    def export_session(self, output_path: Path = None) -> Optional[Path]:
        """Export current session to JSON file."""
        if self._conversation_manager:
            return self._conversation_manager.export_session(output_path)
        return None

    def get_project_context_summary(self) -> str:
        """Get the loaded project context summary."""
        if self._conversation_manager:
            return self._conversation_manager.get_project_context_summary()
        return "No conversation manager initialized."

    @property
    def conversation_manager(self) -> Optional[ConversationManager]:
        """Get the conversation manager instance."""
        return self._conversation_manager

    @property
    def project_primer(self) -> Optional[ProjectPrimer]:
        """Get the project primer instance."""
        return self._project_primer

    @property
    def symbolic_registry(self) -> Optional[SymbolicRegistry]:
        """Get the symbolic registry instance."""
        return self._symbolic_registry

    def lookup_symbol(self, symbol: str, auto_heal: bool = True) -> Optional[Dict[str, Any]]:
        """
        Look up a symbol in the registry.

        If auto_heal is True and symbol not found, it will be auto-registered.
        """
        if not self._symbolic_registry:
            return None

        sym = self._symbolic_registry.get(symbol)
        if sym:
            return sym.to_dict()

        # Auto-heal if enabled
        if auto_heal:
            healed = self._symbolic_registry.heal_missing_symbol(symbol)
            if healed:
                logger.info(f"Auto-healed missing symbol: {symbol}")
                return healed.to_dict()

        return None

    def get_full_primer(self) -> str:
        """Get the complete project primer document."""
        if self._project_primer:
            return self._project_primer.get_full_primer()
        return "No project primer available."

    def get_cypher_document(self) -> str:
        """Get the LLM cypher teaching document."""
        if self._project_primer:
            return self._project_primer.get_cypher_document()
        return "No cypher document available."

    def get_symbol_glossary(self) -> str:
        """Get the symbol glossary from the registry."""
        if self._symbolic_registry:
            return self._symbolic_registry.get_symbol_glossary()
        return "No symbol glossary available."

