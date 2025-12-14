"""
Greenlight Main Window

The main application window with 3-pane layout.
"""

import customtkinter as ctk
from typing import Dict, Optional, Any, List
from pathlib import Path
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from greenlight.ui.theme import theme, GreenlightTheme
from greenlight.ui.components import (
    ProjectNavigator,
    MainWorkspace,
    AssistantPanel,
    StatusBar,
    JourneyPhase,
    PipelineExecutionPanel,
    EventType,
)
from greenlight.core.logging_config import get_logger
from greenlight.llm.llm_registry import LLM_REGISTRY, list_available_llms, LLMInfo

logger = get_logger("ui.main_window")

# Try to import OmniMind for assistant integration
try:
    from greenlight.omni_mind import OmniMind, AssistantMode
    from greenlight.omni_mind import GreenlightAssistantBridge, GreenlightBridgeConfig
    HAS_OMNI_MIND = True
except ImportError:
    HAS_OMNI_MIND = False
    GreenlightAssistantBridge = None
    GreenlightBridgeConfig = None
    logger.warning("OmniMind not available - assistant will use fallback mode")

# Try to import LLM components for bridge
try:
    from greenlight.llm import LLMManager, FunctionRouter
    from greenlight.context import ContextEngine
    HAS_LLM = True
except ImportError:
    HAS_LLM = False
    LLMManager = None
    FunctionRouter = None
    ContextEngine = None
    logger.warning("LLM components not available")

# Try to import Agnostic_Core_OS for Agnostic Learner
try:
    from Agnostic_Core_OS import (
        AgnosticCorePlatform,
        ComparisonLearning,
        get_notation_library,
        VectorLanguageTranslator,
    )
    from Agnostic_Core_OS.engines import get_image_engine, get_live_engine
    HAS_AGNOSTIC_CORE = True
except ImportError:
    HAS_AGNOSTIC_CORE = False
    AgnosticCorePlatform = None
    ComparisonLearning = None
    logger.warning("Agnostic_Core_OS not available - learner will use fallback")


class Viewport(ctk.CTk):
    """
    Main Greenlight Viewport (application window).

    Features:
    - 4-pane layout (navigator, workspace, assistant, pipeline panel)
    - User Journey walkthrough with input hooks
    - Pipeline execution panel with event log
    - Notification system with sounds
    - Omni Mind integration
    - Project management
    - Real-time updates
    """
    
    def __init__(
        self,
        title: str = "Project Greenlight - Viewport",
        width: int = 1600,
        height: int = 950
    ):
        super().__init__()

        self.title(title)
        self.geometry(f"{width}x{height}")
        self.minsize(1200, 800)

        # Apply theme
        self._theme = GreenlightTheme()

        # State
        self._project_path: Optional[str] = None
        self._omni_mind = None
        self._assistant_bridge = None
        self._llm_manager = None
        self._function_router = None
        self._context_engine = None
        self._llm_options: Dict[str, LLMInfo] = {}
        self._selected_llm: Optional[LLMInfo] = None
        self._project_list: List[str] = []
        self._projects_dir = Path.cwd() / "projects"
        self._current_journey_phase: Optional[JourneyPhase] = None
        self._is_pipeline_running = False

        # Agnostic Learner state
        self._agnostic_platform = None
        self._comparison_learning = None
        self._notation_library = None
        self._image_engine = None
        self._live_engine = None

        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._async_loop = None

        self._setup_ui()
        self._setup_bindings()
        self._initialize_agnostic_learner()
        self._initialize_omni_mind()
        self._initialize_assistant_bridge()
        self._initialize_backdoor()
        self._connect_image_handler()

        # Set World Bible as the default view on startup
        self.workspace.set_view("world_bible")
    
    def _setup_ui(self) -> None:
        """Set up the main Viewport layout."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Menu bar
        self._create_menu()

        # Main container with 2 columns: left panel (navigator + pipeline), workspace
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True)
        main_container.grid_columnconfigure(1, weight=1)  # Workspace expands
        main_container.grid_rowconfigure(0, weight=1)

        # Left Panel: Navigator + Pipeline
        left_panel = ctk.CTkFrame(main_container, fg_color=theme.colors.bg_dark, width=260)
        left_panel.grid(row=0, column=0, sticky="nsw", rowspan=2)
        left_panel.grid_propagate(False)
        left_panel.grid_rowconfigure(0, weight=1)  # Navigator expands
        left_panel.grid_columnconfigure(0, weight=1)

        # Project Navigator (top of left panel)
        self.navigator = ProjectNavigator(
            left_panel,
            on_select=self._on_node_select
        )
        self.navigator.pack(fill="both", expand=True)

        # Pipeline Execution Panel (bottom of left panel, with cancel button)
        self.pipeline_panel = PipelineExecutionPanel(
            left_panel,
            on_file_click=self._on_pipeline_file_click,
            on_cancel=self._on_pipeline_cancel
        )
        self.pipeline_panel.pack(fill="x", side="bottom", padx=4, pady=4)

        # Center: Main Workspace + Assistant (expanded to fill removed right panel)
        center_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        center_frame.grid(row=0, column=1, sticky="nsew")
        center_frame.grid_rowconfigure(0, weight=1)
        center_frame.grid_columnconfigure(0, weight=1)

        self.workspace = MainWorkspace(
            center_frame,
            on_content_change=self._on_content_change
        )
        self.workspace.grid(row=0, column=0, sticky="nsew")

        # Bottom: Assistant Panel
        self.assistant = AssistantPanel(
            center_frame,
            on_message=self._on_assistant_message
        )
        self.assistant.grid(row=1, column=0, sticky="sew")

        # Notifications now go to assistant panel instead of floating overlay

        # User Journey Panel removed - functionality moved to assistant

        # Status Bar
        self.status_bar = StatusBar(self)
        self.status_bar.pack(side="bottom", fill="x")
    
    def _create_menu(self) -> None:
        """Create the menu bar and toolbar."""
        # Menu bar - simplified with just logo and settings
        menu_frame = ctk.CTkFrame(self, fg_color=theme.colors.bg_dark, height=30)
        menu_frame.pack(fill="x")
        menu_frame.pack_propagate(False)

        # Logo/Title
        logo = ctk.CTkLabel(
            menu_frame,
            text="🎬 Project Greenlight",
            font=(theme.fonts.family, theme.fonts.size_large, "bold"),
            text_color=theme.colors.text_primary
        )
        logo.pack(side="left", padx=theme.spacing.md)

        # Right side buttons
        settings_btn = ctk.CTkButton(
            menu_frame,
            text="⚙️",
            width=30,
            fg_color="transparent",
            hover_color=theme.colors.bg_hover,
            command=self._show_settings
        )
        settings_btn.pack(side="right", padx=theme.spacing.sm)

        # Toolbar with quick access buttons
        toolbar = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium, height=40)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        # New Project button
        new_btn = ctk.CTkButton(
            toolbar,
            text="📁 New Project",
            width=120,
            height=30,
            fg_color=theme.colors.accent,
            hover_color=theme.colors.accent_hover,
            command=self._new_project
        )
        new_btn.pack(side="left", padx=theme.spacing.sm, pady=5)

        # Project selector dropdown
        project_label = ctk.CTkLabel(
            toolbar,
            text="Project:",
            text_color=theme.colors.text_secondary
        )
        project_label.pack(side="left", padx=(theme.spacing.sm, theme.spacing.xs))

        # Build project list
        self._project_list = self._scan_projects_directory()
        project_values = self._project_list if self._project_list else ["No projects found"]

        self.project_selector = ctk.CTkOptionMenu(
            toolbar,
            values=project_values,
            command=self._on_project_selected,
            width=200,
            height=28,
            fg_color=theme.colors.bg_dark,
            button_color=theme.colors.primary,
            button_hover_color=theme.colors.accent_hover,
        )
        self.project_selector.set("Select a project...")
        self.project_selector.pack(side="left", padx=theme.spacing.xs, pady=5)

        # Refresh projects button
        refresh_btn = ctk.CTkButton(
            toolbar,
            text="🔄",
            width=30,
            height=28,
            fg_color=theme.colors.bg_dark,
            hover_color=theme.colors.bg_hover,
            command=self._refresh_project_list
        )
        refresh_btn.pack(side="left", padx=(0, theme.spacing.sm), pady=5)

        # Separator (Save button removed - OmniMind handles save prompts)
        sep = ctk.CTkFrame(toolbar, width=2, fg_color=theme.colors.border)
        sep.pack(side="left", fill="y", padx=theme.spacing.md, pady=8)

        # Writer button (red)
        writer_btn = ctk.CTkButton(
            toolbar,
            text="📝 Writer",
            width=90,
            height=30,
            fg_color="#C0392B",
            hover_color="#E74C3C",
            command=self._run_writer
        )
        writer_btn.pack(side="left", padx=theme.spacing.xs, pady=5)
        self._register_ui_element("writer_toolbar_btn", writer_btn, "Writer pipeline button", "toolbar")

        # Director button (yellow)
        director_btn = ctk.CTkButton(
            toolbar,
            text="🎬 Director",
            width=100,
            height=30,
            fg_color="#D4AC0D",
            hover_color="#F1C40F",
            text_color="#1a1a2e",
            command=self._run_director
        )
        director_btn.pack(side="left", padx=theme.spacing.xs, pady=5)
        self._register_ui_element("director_toolbar_btn", director_btn, "Director pipeline button", "toolbar")

        # Generate Storyboard button
        gen_btn = ctk.CTkButton(
            toolbar,
            text="🎨 Generate",
            width=100,
            height=30,
            fg_color=theme.colors.success,
            hover_color="#2d8a4e",
            command=self._generate_storyboard
        )
        gen_btn.pack(side="left", padx=theme.spacing.xs, pady=5)
        self._register_ui_element("generate_toolbar_btn", gen_btn, "Generate storyboard images button", "toolbar")

        # Right side - LLM selector with "Omni Model" label on the right
        # Build LLM options from registry
        self._llm_options = self._build_llm_options()
        llm_values = list(self._llm_options.keys())
        default_llm = llm_values[0] if llm_values else "No LLMs Available"

        # "Omni Model" label (to the right of dropdown)
        omni_label = ctk.CTkLabel(
            toolbar,
            text="Omni Model",
            text_color=theme.colors.text_secondary,
            font=(theme.fonts.family, theme.fonts.size_normal)
        )
        omni_label.pack(side="right", padx=(theme.spacing.sm, theme.spacing.md))

        self.llm_selector = ctk.CTkOptionMenu(
            toolbar,
            values=llm_values if llm_values else ["No LLMs Available"],
            command=self._on_llm_selected,
            width=180,
            height=28,
            fg_color=theme.colors.bg_dark,
            button_color=theme.colors.primary,
            button_hover_color=theme.colors.accent_hover,
        )
        self.llm_selector.set(default_llm)
        self.llm_selector.pack(side="right", padx=theme.spacing.sm, pady=5)

        # Set initial selected LLM
        if llm_values:
            self._on_llm_selected(default_llm)
    
    def _setup_bindings(self) -> None:
        """Set up keyboard bindings."""
        self.bind("<Control-n>", lambda e: self._new_project())
        self.bind("<Control-o>", lambda e: self._open_project())
        self.bind("<Control-s>", lambda e: self._save_project())
        self.bind("<Control-q>", lambda e: self.quit())

    def _register_ui_element(self, element_id: str, widget, description: str, category: str = "general") -> None:
        """Register a UI element with the pointer system for OmniMind guidance."""
        try:
            from greenlight.ui.components.ui_pointer import register_element
            register_element(element_id, widget, description, category)
        except ImportError:
            pass  # UI pointer not available

    def _initialize_agnostic_learner(self) -> None:
        """
        Initialize the Agnostic Learner from Agnostic_Core_OS.

        This primes the system with:
        - AgnosticCorePlatform for vector-language translation
        - ComparisonLearning for iterative learning
        - NotationLibrary for symbolic notation registry
        - ImageEngine and LiveEngine for multi-modal processing
        """
        if not HAS_AGNOSTIC_CORE:
            logger.info("Agnostic_Core_OS not available, learner disabled")
            return

        try:
            # Initialize platform (project-agnostic at startup)
            self._agnostic_platform = AgnosticCorePlatform(project_path=None)
            logger.info("AgnosticCorePlatform initialized")

            # Initialize notation library (global symbolic registry)
            self._notation_library = get_notation_library()
            entry_count = len(self._notation_library._entries) if hasattr(self._notation_library, '_entries') else 0
            logger.info(f"NotationLibrary loaded: {entry_count} entries")

            # Initialize comparison learning system
            learning_path = Path.cwd() / ".learning"
            self._comparison_learning = ComparisonLearning(storage_path=learning_path)
            logger.info("ComparisonLearning initialized")

            # Initialize engines
            self._image_engine = get_image_engine()
            self._live_engine = get_live_engine()

            # Connect engines to learning system
            if self._comparison_learning and self._image_engine:
                self._comparison_learning.connect_engines(
                    image_engine=self._image_engine,
                    audio_engine=None  # Audio engine optional
                )
                logger.info("Engines connected to ComparisonLearning")

            logger.info("✅ Agnostic Learner initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Agnostic Learner: {e}")
            self._agnostic_platform = None
            self._comparison_learning = None

    def _initialize_omni_mind(self) -> None:
        """Initialize the OmniMind assistant."""
        if not HAS_OMNI_MIND:
            logger.info("OmniMind not available, using fallback assistant")
            return

        try:
            self._omni_mind = OmniMind(mode=AssistantMode.SUPERVISED)

            # Connect Agnostic Learner to OmniMind if available
            if self._agnostic_platform and hasattr(self._omni_mind, 'set_platform'):
                self._omni_mind.set_platform(self._agnostic_platform)
                logger.info("AgnosticCorePlatform connected to OmniMind")

            logger.info("OmniMind initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OmniMind: {e}")
            self._omni_mind = None

    def _initialize_assistant_bridge(self) -> None:
        """Initialize the AssistantBridge for background LLM processing."""
        if not HAS_OMNI_MIND or GreenlightAssistantBridge is None:
            logger.info("AssistantBridge not available, using fallback")
            return

        try:
            # Initialize LLM components if available
            if HAS_LLM:
                try:
                    self._llm_manager = LLMManager()
                    self._function_router = FunctionRouter(self._llm_manager)
                    self._context_engine = ContextEngine()
                    # Update workspace with context engine for world context injection
                    if hasattr(self, 'workspace') and self.workspace:
                        self.workspace.set_context_engine(self._context_engine)
                    logger.info("LLM components initialized")
                except Exception as e:
                    logger.warning(f"Failed to initialize LLM components: {e}")

            # Create bridge config
            config = GreenlightBridgeConfig(
                max_workers=4,
                queue_size=100,
                enable_caching=True,
                log_requests=True
            )

            # Create and initialize bridge
            self._assistant_bridge = GreenlightAssistantBridge(config)
            self._assistant_bridge.initialize(
                llm_manager=self._llm_manager,
                function_router=self._function_router,
                context_engine=self._context_engine,
                project_path=Path(self._project_path) if self._project_path else None
            )

            # Set callbacks
            self._assistant_bridge.set_response_callback(self._on_bridge_response)
            self._assistant_bridge.set_error_callback(self._on_bridge_error)
            self._assistant_bridge.set_progress_callback(self._on_bridge_progress)

            # Wire up tool executor if OmniMind is available
            if self._omni_mind and hasattr(self._omni_mind, 'tool_executor'):
                self._assistant_bridge.set_tool_executor(self._omni_mind.tool_executor)
                logger.info("Tool executor connected to AssistantBridge")

            # Start the bridge
            self._assistant_bridge.start()
            logger.info("AssistantBridge initialized and started")

            # Initialize document tracker with OmniMind prompt callback
            self._initialize_document_tracker()

        except Exception as e:
            logger.error(f"Failed to initialize AssistantBridge: {e}")
            self._assistant_bridge = None

    def _initialize_backdoor(self) -> None:
        """Initialize the backdoor server for testing and automation."""
        try:
            from greenlight.omni_mind.backdoor import start_backdoor
            self._backdoor = start_backdoor(main_window=self)
            logger.info("Backdoor server initialized on port 19847")
        except Exception as e:
            logger.warning(f"Failed to initialize backdoor: {e}")
            self._backdoor = None

    def _initialize_document_tracker(self) -> None:
        """Initialize document change tracker for OmniMind save/revert prompts."""
        try:
            from greenlight.omni_mind.document_tracker import get_document_tracker

            self._document_tracker = get_document_tracker()

            # Register callback to show prompts in assistant panel
            def on_prompt(message: str):
                self.after(0, lambda: self.assistant.add_response(message))

            self._document_tracker.register_prompt_callback(on_prompt)
            logger.info("Document tracker initialized with OmniMind prompts")
        except ImportError:
            logger.warning("Document tracker not available")
            self._document_tracker = None
        except Exception as e:
            logger.error(f"Failed to initialize document tracker: {e}")
            self._document_tracker = None

    def _on_bridge_response(self, message: str) -> None:
        """Handle response from AssistantBridge."""
        # Hide thinking indicator and update UI on main thread
        self.after(0, lambda: self.assistant.hide_thinking())
        self.after(0, lambda: self._handle_assistant_response(message))

    def _on_bridge_error(self, error_message: str) -> None:
        """Handle error from AssistantBridge."""
        # Hide thinking indicator
        self.after(0, lambda: self.assistant.hide_thinking())
        self.after(0, lambda: self._handle_assistant_response(
            f"⚠️ {error_message}\n\nPlease try again or check the logs for details."
        ))

    def _on_bridge_progress(self, progress: float, message: str) -> None:
        """Handle progress update from AssistantBridge."""
        # Update thinking indicator in assistant panel
        if hasattr(self, 'assistant') and self.assistant:
            thinking_status = self._format_thinking_status(progress, message)
            self.after(0, lambda: self.assistant.update_thinking_status(thinking_status))

        # Update pipeline panel if available
        if hasattr(self, '_workspace') and self._workspace:
            try:
                pipeline_panel = self._workspace.pipeline_panel
                if pipeline_panel:
                    self.after(0, lambda: pipeline_panel.update_progress(progress, message))
            except Exception as e:
                logger.debug(f"Could not update pipeline panel: {e}")

    def _format_thinking_status(self, progress: float, message: str) -> str:
        """Format progress into a thinking status message."""
        # Map progress to thinking phases
        if progress < 0.1:
            phase = "🔍 Analyzing request..."
        elif progress < 0.3:
            phase = "📚 Loading context..."
        elif progress < 0.5:
            phase = "🧠 Reasoning..."
        elif progress < 0.7:
            phase = "✍️ Generating response..."
        elif progress < 0.9:
            phase = "🔧 Finalizing..."
        else:
            phase = "✅ Almost done..."

        # Include custom message if provided
        if message and message != "Processing...":
            return f"{phase} {message}"
        return phase

    def _on_node_select(self, node) -> None:
        """Handle node selection in navigator."""
        logger.debug(f"Selected node: {node.name}")

        # Handle action nodes (special commands from navigator)
        if node.node_type == "action" and node.path.startswith("__action__/"):
            action = node.path.replace("__action__/", "")
            self._handle_navigator_action(action)
            return

        # Load actual file content
        file_path = Path(node.path)
        content_text = ""

        if file_path.is_file():
            try:
                # Read file content based on type
                if node.node_type in ['markdown', 'text', 'json']:
                    content_text = file_path.read_text(encoding='utf-8')
                elif node.node_type == 'image':
                    content_text = f"[Image: {file_path.name}]"
                else:
                    # Try to read as text
                    try:
                        content_text = file_path.read_text(encoding='utf-8')
                    except UnicodeDecodeError:
                        content_text = f"[Binary file: {file_path.name}]"
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                content_text = f"Error reading file: {e}"
        elif file_path.is_dir():
            # Show directory contents summary
            try:
                items = list(file_path.iterdir())
                files = [f.name for f in items if f.is_file()][:10]
                dirs = [d.name for d in items if d.is_dir()][:10]
                content_text = f"# {file_path.name}\n\n"
                if dirs:
                    content_text += f"## Folders ({len([d for d in items if d.is_dir()])})\n"
                    content_text += "\n".join(f"📁 {d}" for d in dirs) + "\n\n"
                if files:
                    content_text += f"## Files ({len([f for f in items if f.is_file()])})\n"
                    content_text += "\n".join(f"📄 {f}" for f in files)
            except Exception as e:
                content_text = f"Error reading directory: {e}"
        else:
            content_text = f"Path not found: {node.path}"

        # Load content into workspace
        self.workspace.load_content({
            'path': node.path,
            'type': node.node_type,
            'text': content_text,
            'project_path': self._project_path
        })

        self.status_bar.set_status(f"Viewing: {node.name}")

    def _handle_navigator_action(self, action: str) -> None:
        """Handle special action commands from navigator."""
        logger.debug(f"Navigator action: {action}")

        # Ensure project path is set for views that need it
        if self._project_path:
            self.workspace.set_project_path(self._project_path)

        if action == "world_bible":
            # Switch to World Bible page view
            self.workspace.set_view("world_bible")
            self.status_bar.set_status("World Bible")
        elif action == "script":
            # Switch to Script panel view
            self.workspace.set_view("script")
            self.status_bar.set_status("Script")
        elif action == "storyboard":
            # Switch to storyboard view
            self.workspace.set_view("storyboard")
            self.status_bar.set_status("Storyboard")
        elif action == "run_writer":
            self._run_writer()
        elif action == "run_director":
            self._run_director()
        else:
            logger.warning(f"Unknown navigator action: {action}")

    def _on_content_change(self, content: str) -> None:
        """Handle content changes in workspace."""
        # Mark as modified
        self.status_bar.set_status("Modified", theme.colors.warning)

        # Track change for OmniMind save/revert prompts
        self._track_document_change(content)

    def _track_document_change(self, current_content: str) -> None:
        """Track document change for OmniMind save/revert prompts."""
        if not hasattr(self, '_document_tracker') or not self._document_tracker:
            return

        # Get current file path from workspace
        current_path = getattr(self, '_current_file_path', None)
        if not current_path:
            # Try to get from workspace current content
            if hasattr(self, 'workspace') and hasattr(self.workspace, '_current_content'):
                current_path = self.workspace._current_content.get('path')

        if not current_path:
            return

        try:
            from greenlight.omni_mind.document_tracker import ChangeType

            # Get original content if we haven't stored it yet
            original_content = getattr(self, '_original_file_content', {}).get(current_path)
            if original_content is None:
                # First change - read original from disk
                file_path = Path(current_path)
                if file_path.exists():
                    original_content = file_path.read_text(encoding='utf-8')
                    if not hasattr(self, '_original_file_content'):
                        self._original_file_content = {}
                    self._original_file_content[current_path] = original_content

            # Track the change
            self._document_tracker.track_change(
                file_path=current_path,
                change_type=ChangeType.MODIFIED,
                original_content=original_content,
                current_content=current_content
            )
        except Exception as e:
            logger.debug(f"Failed to track document change: {e}")

    def _on_assistant_message(self, message: str) -> None:
        """Handle message from assistant panel."""
        logger.info(f"User message: {message}")

        # Handle attachment messages
        if message.startswith("[ATTACHMENT:"):
            self.status_bar.set_status("File attached")
            return

        self.status_bar.show_processing("Processing...")

        # Build context for the assistant
        context = {
            'project_path': self._project_path,
            'selected_llm': self._selected_llm.id if self._selected_llm else None,
        }

        # Use AssistantBridge if available (preferred)
        if self._assistant_bridge and self._assistant_bridge.is_initialized:
            request_id = self._assistant_bridge.submit(message, context)
            if request_id:
                logger.debug(f"Submitted to bridge: {request_id}")
                return

        # Fallback to OmniMind if bridge not available
        if self._omni_mind:
            self._executor.submit(self._process_with_omni_mind, message, context)
        else:
            # Final fallback: provide helpful responses based on message content
            self._executor.submit(self._process_fallback, message, context)

    def _process_with_omni_mind(self, message: str, context: Dict) -> None:
        """Process message with OmniMind in background thread."""
        try:
            # Update thinking status
            self.after(0, lambda: self.assistant.update_thinking_status("🧠 Reasoning with OmniMind..."))

            # Create event loop for async call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            response = loop.run_until_complete(
                self._omni_mind.process(message, context)
            )
            loop.close()

            # Hide thinking indicator and update UI on main thread
            self.after(0, lambda: self.assistant.hide_thinking())
            self.after(0, lambda: self._handle_assistant_response(response.message))

            # Show suggestions if any
            if response.suggestions:
                suggestions_text = "\n\n💡 **Suggestions:**\n" + "\n".join(
                    f"• {s.description}" for s in response.suggestions[:3]
                )
                self.after(100, lambda: self.assistant.add_response(suggestions_text))

        except Exception as e:
            logger.error(f"OmniMind error: {e}")
            self.after(0, lambda: self.assistant.hide_thinking())
            self.after(0, lambda: self._handle_assistant_response(
                f"I encountered an error processing your request: {str(e)}\n\n"
                "Please try again or check the logs for details."
            ))

    def _process_fallback(self, message: str, context: Dict) -> None:
        """Fallback message processing when OmniMind is not available."""
        msg_lower = message.lower()

        # Provide contextual responses based on message content
        if any(word in msg_lower for word in ['help', 'what can you do', 'commands']):
            response = """I'm Omni Mind, your AI assistant for Project Greenlight! Here's what I can help with:

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
• Select files in the navigator to view/edit them
• Use the mode buttons to switch between Editor, Storyboard, and Gallery views"""

        elif any(word in msg_lower for word in ['writer', 'write', 'story', 'script']):
            response = """To work with the Writer pipeline:

1. **Create a project** using the "New Project" button
2. **Enter your pitch** with logline and synopsis
3. **Click "📝 Writer"** in the toolbar to run the Writer pipeline

The Writer will generate:
• Story structure and beats
• Scene breakdowns
• Shot lists for each scene

Would you like me to help you get started with a new project?"""

        elif any(word in msg_lower for word in ['director', 'storyboard', 'prompt']):
            response = """To work with the Director pipeline:

1. **Run Writer first** to generate story content
2. **Click "🎬 Director"** in the toolbar
3. **Review the generated prompts** in the Storyboard view

The Director will create:
• Detailed image prompts for each shot
• Camera angles and compositions
• Visual style descriptions

After Director completes, use "🎨 Generate" to create images!"""

        elif any(word in msg_lower for word in ['generate', 'image', 'picture']):
            response = """To generate storyboard images:

1. **Complete the Director pipeline** first
2. **Click "🎨 Generate"** in the toolbar
3. **View results** in the Gallery or Storyboard view

The system will:
• Load your storyboard prompts
• Generate images using the configured AI model
• Save them to your project's storyboards folder

Make sure you have an image generation API configured in Settings!"""

        elif 'project' in msg_lower and any(word in msg_lower for word in ['new', 'create', 'start']):
            response = """To create a new project:

1. **Click "📁 New Project"** in the toolbar
2. **Enter project details:**
   • Name and type (Single/Series)
   • Genre
   • Logline and pitch
3. **Choose options:**
   • Project size
   • AI model
4. **Click Create** to generate the project structure

Your project will include folders for scripts, beats, shots, storyboards, and more!"""

        else:
            response = f"""I received your message: "{message}"

I'm currently running in fallback mode without full AI capabilities.
To enable full assistant features, please ensure:
• API keys are configured in Settings
• The OmniMind module is properly initialized

In the meantime, I can help with:
• Navigating your project (use the left panel)
• Running pipelines (use toolbar buttons)
• Viewing storyboards (use mode buttons)

Type "help" for a list of available commands!"""

        # Hide thinking indicator and show response
        self.after(0, lambda: self.assistant.hide_thinking())
        self.after(0, lambda: self._handle_assistant_response(response))

    def _handle_assistant_response(self, response: str) -> None:
        """Handle response from Omni Mind."""
        self.assistant.add_response(response)
        self.status_bar.show_success("Ready")
    
    def _export_project(self) -> None:
        """Export project to various formats."""
        if not self._project_path:
            self.status_bar.set_status("No project to export", theme.colors.warning)
            return
        self.status_bar.show_processing("Exporting...")
        self.after(1000, lambda: self.status_bar.show_success("Export complete"))

    def _show_about(self) -> None:
        """Show about dialog."""
        from greenlight.core.constants import VERSION, PROJECT_NAME
        about = ctk.CTkToplevel(self)
        about.title("About")
        about.geometry("300x150")
        about.configure(fg_color=theme.colors.bg_dark)

        ctk.CTkLabel(about, text=PROJECT_NAME, font=(theme.fonts.family, 18, "bold")).pack(pady=10)
        ctk.CTkLabel(about, text=f"Version {VERSION}").pack()
        ctk.CTkLabel(about, text="AI-Powered Cinematic Storyboard Generation").pack(pady=10)
        ctk.CTkButton(about, text="Close", command=about.destroy).pack(pady=10)
    
    def _show_settings(self) -> None:
        """Show settings dialog."""
        from greenlight.ui.dialogs.settings_dialog import SettingsDialog
        SettingsDialog(self)

    def _new_project(self) -> None:
        """Create a new project using the wizard."""
        from greenlight.ui.dialogs.project_wizard import ProjectWizard

        def on_complete(project_data: Dict):
            """Handle project creation."""
            project_path = project_data.get('path')
            if project_path:
                # Load the new project
                self.load_project(project_path)

                # Show pitch in workspace
                pitch_file = Path(project_path) / "world_bible" / "pitch.md"
                if pitch_file.exists():
                    self.workspace.load_content({
                        'path': str(pitch_file),
                        'type': 'markdown',
                        'text': pitch_file.read_text(encoding='utf-8')
                    })

                self.status_bar.show_success(f"Created project: {project_data['name']}")
                logger.info(f"Created new project: {project_data['name']}")

        ProjectWizard(self, on_complete=on_complete)

    def _open_project(self) -> None:
        """Open an existing project."""
        from greenlight.ui.dialogs.project_dialog import OpenProjectDialog

        def on_open(path: str):
            self.load_project(path)

        # Get recent projects from config if available
        recent = []
        OpenProjectDialog(self, recent_projects=recent, on_open=on_open)
    
    def _save_project(self) -> None:
        """Save the current project."""
        if not self._project_path:
            self.status_bar.set_status("No project to save", theme.colors.warning)
            return
        self.status_bar.show_processing("Saving...")
        self.after(500, lambda: self.status_bar.show_success("Saved"))

    def _run_writer(self) -> None:
        """Run the Writer pipeline."""
        if not self._project_path:
            self.status_bar.set_status("Open a project first", theme.colors.warning)
            return

        from greenlight.ui.dialogs.writer_dialog import WriterDialog

        def on_complete(result: Dict):
            self.status_bar.show_success("Writer complete!")
            self.assistant.add_response("✅ Writer pipeline complete! Story, world config, beats, and shots generated.")
            self.pipeline_panel.end_phase("Writer", success=True)
            self.pipeline_panel.set_idle()
            # Refresh navigator
            self.navigator.load_project(self._project_path)
            # Switch to Script view and refresh to show the generated script
            from greenlight.ui.components.main_workspace import WorkspaceMode
            self.workspace.set_project_path(self._project_path)
            self.workspace.set_mode(WorkspaceMode.SCRIPT)

        def external_log(message: str):
            """Route log messages to pipeline panel."""
            self.pipeline_panel.log_info(message)

        def external_progress(value: float):
            """Route progress to pipeline panel."""
            self.pipeline_panel.set_progress(value)

        # Start the phase in pipeline panel
        self.pipeline_panel.start_phase("Writer")
        self.status_bar.show_processing("Running Writer pipeline...")

        WriterDialog(
            self,
            project_path=Path(self._project_path),
            on_complete=on_complete,
            external_log=external_log,
            external_progress=external_progress,
            close_on_start=True
        )

    def _run_director(self) -> None:
        """Run the Director pipeline."""
        if not self._project_path:
            self.status_bar.set_status("Open a project first", theme.colors.warning)
            return

        from greenlight.ui.dialogs.director_dialog import DirectorDialog

        def on_complete(result: Dict):
            self.status_bar.show_success("Director complete!")
            self.assistant.add_response("✅ Director pipeline complete! Storyboard prompts generated and ready for image generation.")
            self.pipeline_panel.end_phase("Director", success=True)
            self.pipeline_panel.set_idle()
            # Refresh navigator
            self.navigator.load_project(self._project_path)

        def external_log(message: str):
            """Route log messages to pipeline panel."""
            self.pipeline_panel.log_info(message)

        def external_progress(value: float):
            """Route progress to pipeline panel."""
            self.pipeline_panel.set_progress(value)

        # Start the phase in pipeline panel
        self.pipeline_panel.start_phase("Director")
        self.status_bar.show_processing("Running Director pipeline...")

        DirectorDialog(
            self,
            project_path=Path(self._project_path),
            on_complete=on_complete,
            external_log=external_log,
            external_progress=external_progress,
            close_on_start=False  # Show modal for LLM selection
        )

    def _validate_storyboard_references(self, prompts_data: Dict) -> List[Dict]:
        """
        Validate all tags in storyboard prompts have reference images.

        Checks:
        - Characters: Must have at least one reference (preferably a sheet)
        - Locations: Must have a reference (North view) and optionally cardinal views
        - Props: Must have at least one reference

        Returns:
            List of missing references:
            [
                {"tag": "CHAR_MEI", "type": "character", "issue": "no_reference"},
                {"tag": "LOC_FLOWER_SHOP", "type": "location", "issue": "no_cardinals"},
                ...
            ]
        """
        from greenlight.tags.tag_parser import TagParser
        from greenlight.references.reference_manager import ReferenceManager
        from greenlight.core.constants import TagCategory

        parser = TagParser()
        ref_manager = ReferenceManager(Path(self._project_path))

        missing = []
        all_tags = set()

        # Extract all unique tags from all prompts
        for prompt_data in prompts_data.get('prompts', []):
            prompt_text = prompt_data.get('prompt', '')
            tags_text = prompt_data.get('tags', '')

            # Parse both prompt and tags field
            combined_text = f"{tags_text} {prompt_text}"
            parsed = parser.parse_text(combined_text)
            for tag in parsed:
                # Use base_name for directional tags
                tag_name = tag.base_name if tag.is_directional else tag.name
                all_tags.add((tag_name, tag.category))

        # Check each tag has references
        for tag_name, category in all_tags:
            refs = ref_manager.scan_references(tag_name)

            if category == TagCategory.CHARACTER:
                if not refs:
                    missing.append({
                        "tag": tag_name,
                        "type": "character",
                        "issue": "no_reference",
                        "message": f"Character [{tag_name}] has no reference images"
                    })

            elif category == TagCategory.LOCATION:
                if not refs:
                    missing.append({
                        "tag": tag_name,
                        "type": "location",
                        "issue": "no_reference",
                        "message": f"Location [{tag_name}] has no reference images"
                    })
                else:
                    # Check for cardinal views
                    if not ref_manager.has_cardinal_views(tag_name):
                        missing.append({
                            "tag": tag_name,
                            "type": "location",
                            "issue": "no_cardinals",
                            "message": f"Location [{tag_name}] missing cardinal views (N/E/S/W)"
                        })

            elif category == TagCategory.PROP:
                if not refs:
                    missing.append({
                        "tag": tag_name,
                        "type": "prop",
                        "issue": "no_reference",
                        "message": f"Prop [{tag_name}] has no reference images"
                    })

        return missing

    def _show_missing_references_warning(self, missing: List[Dict]) -> None:
        """Show a warning notification about missing references with quick-fix action."""
        # Group by type
        chars = [m for m in missing if m['type'] == 'character']
        locs = [m for m in missing if m['type'] == 'location']
        props = [m for m in missing if m['type'] == 'prop']

        # Build message
        msg_parts = []
        if chars:
            msg_parts.append(f"{len(chars)} character(s)")
        if locs:
            msg_parts.append(f"{len(locs)} location(s)")
        if props:
            msg_parts.append(f"{len(props)} prop(s)")

        message = f"Missing references: {', '.join(msg_parts)}"

        # Log details to assistant
        details = "\n".join([f"  • {m['message']}" for m in missing[:10]])
        if len(missing) > 10:
            details += f"\n  ... and {len(missing) - 10} more"

        self.assistant.add_response(
            f"⚠️ **Cannot generate storyboard - Missing References**\n\n{details}\n\n"
            f"Please generate reference images for these tags before running storyboard generation."
        )

        # Show notification with action button
        # Notify via assistant panel
        self.assistant.add_system_message(f"⚠️ Missing References: {message}")

    def _open_reference_modal_for_tag(self, tag: str, tag_type: str) -> None:
        """Open the reference modal for a specific tag."""
        from greenlight.ui.components.reference_modal import ReferenceModal

        # Load world config
        world_config = {}
        if self._project_path:
            config_path = Path(self._project_path) / "world_bible" / "world_config.json"
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    world_config = json.load(f)

        # Find the name for this tag
        name = tag
        if tag_type == "character":
            chars = world_config.get("characters", [])
            char_data = next((c for c in chars if c.get("tag") == tag), {})
            name = char_data.get("name", tag)
        elif tag_type == "location":
            locs = world_config.get("locations", [])
            loc_data = next((l for l in locs if l.get("tag") == tag), {})
            name = loc_data.get("name", tag)
        elif tag_type == "prop":
            props = world_config.get("props", [])
            prop_data = next((p for p in props if p.get("tag") == tag), {})
            name = prop_data.get("name", tag)

        ReferenceModal(
            self,
            tag=tag,
            name=name,
            tag_type=tag_type,
            project_path=Path(self._project_path),
            world_config=world_config,
            on_change=lambda: self.workspace.refresh_current_view(),
            context_engine=self._context_engine
        )

    def _generate_storyboard(self) -> None:
        """Generate storyboard images from visual script."""
        if not self._project_path:
            self.status_bar.set_status("Open a project first", theme.colors.warning)
            return

        # Check for visual script
        project_path = Path(self._project_path)
        visual_script_file = project_path / "storyboard" / "visual_script.json"

        if not visual_script_file.exists():
            self.status_bar.set_status("Run Director first to generate visual script", theme.colors.warning)
            self.assistant.add_response("⚠️ No visual script found. Please run the Director pipeline first.")
            return

        # Load visual script
        try:
            import json
            with open(visual_script_file, 'r', encoding='utf-8') as f:
                visual_script_data = json.load(f)

            total_frames = visual_script_data.get('total_frames', 0)
            if total_frames == 0:
                self.status_bar.set_status("No frames found in visual script", theme.colors.warning)
                return

            self.status_bar.set_status("Ready to generate", theme.colors.success)

            # Open the generation modal
            from greenlight.ui.dialogs.storyboard_generation_modal import StoryboardGenerationModal

            def on_continue(model_key: str, script_data: Dict):
                """Handle continue from modal - start generation."""
                self._start_storyboard_generation(model_key, script_data, project_path)

            StoryboardGenerationModal(
                self,
                project_path=project_path,
                visual_script_data=visual_script_data,
                on_continue=on_continue
            )

        except Exception as e:
            logger.error(f"Failed to load visual script: {e}")
            self.status_bar.set_status(f"Error: {e}", theme.colors.error)
            self.assistant.add_response(f"❌ Error loading visual script: {e}")

    def _start_storyboard_generation(self, model_key: str, visual_script_data: Dict, project_path: Path) -> None:
        """Start storyboard generation after modal confirmation."""
        from greenlight.config.api_dictionary import get_image_models
        from datetime import datetime
        import shutil

        # Get model info
        image_models = get_image_models()
        model = image_models.get(model_key)
        model_name = model.display_name if model else model_key

        # Extract frames from visual script scenes
        frames = []
        for scene in visual_script_data.get('scenes', []):
            for frame in scene.get('frames', []):
                frames.append(frame)

        total = len(frames)

        # Archive existing generated storyboard if it exists
        output_dir = project_path / "storyboard" / "generated"
        if output_dir.exists() and any(output_dir.iterdir()):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_dir = project_path / "storyboard" / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archived_path = archive_dir / f"generated_{timestamp}"
            shutil.move(str(output_dir), str(archived_path))
            logger.info(f"Archived previous storyboard to: {archived_path}")
            self.pipeline_panel.add_event(EventType.INFO, f"Archived previous storyboard: generated_{timestamp}")

        self.status_bar.show_processing(f"Generating {total} images with {model_name}...")
        self.assistant.add_response(f"🎨 Starting storyboard generation...\n\n📊 **{total} frames** using **{model_name}**\n\nProgress will be tracked in the Pipeline panel.")

        # Log to pipeline panel
        self.pipeline_panel.start_phase("Storyboard Generation")
        self.pipeline_panel.add_event(EventType.INFO, f"Starting generation of {total} frames with {model_name}")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Store generation state
        self._generation_model_key = model_key
        self._generation_frames = frames
        self._generation_progress = 0
        self._generation_total = total
        self._generation_output_dir = output_dir

        # Start async generation
        self._run_image_generation_async(frames, output_dir, model_key)

    def _run_image_generation_async(self, frames: List, output_dir: Path, model_key: str) -> None:
        """Run image generation for storyboard frames with pipeline tracking."""
        total = len(frames)

        if total == 0:
            self.status_bar.show_success("No frames to generate")
            self.pipeline_panel.end_phase("Storyboard Generation", success=True)
            return

        # Start real image generation using ImageHandler
        import asyncio
        import threading

        def run_generation():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._generate_frames_async(frames, output_dir, model_key))
            finally:
                loop.close()

        # Run in background thread to not block UI
        thread = threading.Thread(target=run_generation, daemon=True)
        thread.start()

    async def _generate_frames_async(self, frames: List, output_dir: Path, model_key: str) -> None:
        """Generate frames asynchronously using ImageHandler.

        Loads style info from world_config and reference images for each frame's tags.
        """
        from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
        import json
        import re

        # Map model_key to ImageModel enum
        model_map = {
            'seedream': ImageModel.SEEDREAM,
            'nano_banana': ImageModel.NANO_BANANA,
            'nano_banana_pro': ImageModel.NANO_BANANA_PRO,
            'imagen_3': ImageModel.IMAGEN_3,
            'flux_kontext_pro': ImageModel.FLUX_KONTEXT_PRO,
            'flux_kontext_max': ImageModel.FLUX_KONTEXT_MAX,
            'sdxl': ImageModel.SDXL,
            'dalle_3': ImageModel.DALLE_3,
        }
        image_model = model_map.get(model_key, ImageModel.SEEDREAM)

        # Get or create ImageHandler with ContextEngine for world context injection
        handler = getattr(self, '_image_handler', None)
        if not handler:
            handler = ImageHandler(self._project_path, self._context_engine)
            self._image_handler = handler
        elif self._context_engine and not handler._context_engine:
            # Update existing handler with context engine if not already set
            handler.set_context_engine(self._context_engine)

        # Get style suffix from ImageHandler (single source of truth: world_config.json)
        style_suffix = handler.get_style_suffix()
        if style_suffix:
            logger.info(f"Using style suffix: {style_suffix}")

        # Load world_config for tag lookup only
        all_tags = []
        world_config_path = self._project_path / "world_bible" / "world_config.json"
        if world_config_path.exists():
            try:
                world_config = json.loads(world_config_path.read_text(encoding='utf-8'))
                all_tags = world_config.get("all_tags", [])
            except Exception as e:
                logger.warning(f"Could not load world_config: {e}")

        handler.start_batch(len(frames))

        for i, frame_data in enumerate(frames):
            frame_id = frame_data.get('frame_id', f'frame_{i+1}')
            prompt = frame_data.get('prompt', '')

            # Get tags from frame data (if Director extracted them) or extract from prompt
            frame_tags = frame_data.get('tags', {})
            if not frame_tags or not any(frame_tags.values()):
                # Extract tags from prompt text
                frame_tags = self._extract_tags_from_prompt(prompt, all_tags)

            # Collect reference images for all tags in this frame
            reference_images = []
            all_frame_tags = (
                frame_tags.get('characters', []) +
                frame_tags.get('locations', []) +
                frame_tags.get('props', [])
            )

            for tag in all_frame_tags:
                ref_path = handler.get_key_reference(tag)
                if ref_path and ref_path.exists():
                    reference_images.append(ref_path)
                    logger.debug(f"Frame {frame_id}: Added reference for {tag}: {ref_path}")

            if reference_images:
                logger.info(f"Frame {frame_id}: Using {len(reference_images)} reference images for tags: {all_frame_tags}")

            # Update UI from main thread
            self.after(0, lambda idx=i+1, fid=frame_id: self._update_generation_progress(idx, fid, 'generating'))

            # Create image request with style and references
            # Uses PROMPT_TEMPLATE_CREATE for storyboard frame generation
            request = ImageRequest(
                prompt=prompt,
                model=image_model,
                aspect_ratio="16:9",
                output_path=output_dir / f"{frame_id}.png",
                tag=frame_id,
                prefix_type="create",  # Use create template for storyboard frames
                add_clean_suffix=True,
                style_suffix=style_suffix if style_suffix else None,
                reference_images=reference_images,
            )

            # Generate the image
            try:
                result = await handler.generate(request)

                if result.success:
                    # Update UI with success
                    self.after(0, lambda idx=i+1, fid=frame_id, path=result.image_path:
                               self._update_generation_progress(idx, fid, 'complete', str(path)))
                else:
                    # Log error but continue
                    logger.error(f"Failed to generate {frame_id}: {result.error}")
                    self.after(0, lambda idx=i+1, fid=frame_id, err=result.error:
                               self._update_generation_progress(idx, fid, 'error', error=err))
            except Exception as e:
                logger.error(f"Exception generating {frame_id}: {e}")
                self.after(0, lambda idx=i+1, fid=frame_id, err=str(e):
                           self._update_generation_progress(idx, fid, 'error', error=err))

        # Complete generation
        self.after(0, self._generation_complete)

    def _extract_tags_from_prompt(self, prompt: str, all_tags: List[str]) -> Dict[str, List[str]]:
        """Extract tags from prompt text and categorize them.

        Args:
            prompt: The frame prompt text
            all_tags: List of all valid tags from world_config

        Returns:
            Dict with keys 'characters', 'locations', 'props' containing lists of tags
        """
        tags = {"characters": [], "locations": [], "props": []}

        for tag in all_tags:
            # Check for tag in brackets [TAG] or as plain text
            if f"[{tag}]" in prompt or tag in prompt:
                if tag.startswith("CHAR_"):
                    if tag not in tags["characters"]:
                        tags["characters"].append(tag)
                elif tag.startswith("LOC_"):
                    if tag not in tags["locations"]:
                        tags["locations"].append(tag)
                elif tag.startswith("PROP_"):
                    if tag not in tags["props"]:
                        tags["props"].append(tag)

        return tags

    def _update_generation_progress(self, index: int, frame_id: str, status: str,
                                     file_path: str = None, error: str = None) -> None:
        """Update UI with generation progress (called from main thread)."""
        total = self._generation_total

        if status == 'generating':
            self.pipeline_panel.log_image_generating(
                tag=frame_id,
                model=self._generation_model_key,
                index=index,
                total=total
            )
            percent = int((index / total) * 100)
            self.status_bar.set_status(f"Generating: {index}/{total} ({percent}%)")
            self.pipeline_panel.set_progress(percent / 100.0)

        elif status == 'complete':
            self.pipeline_panel.log_image_complete(
                tag=frame_id,
                file_path=file_path or str(self._generation_output_dir / f"{frame_id}.png"),
                index=index,
                total=total
            )
            # Refresh storyboard table to show new image
            if hasattr(self.workspace, 'storyboard_table') and self.workspace.storyboard_table:
                try:
                    self.workspace.storyboard_table.refresh_frame(frame_id)
                except Exception as e:
                    logger.warning(f"Could not refresh frame {frame_id}: {e}")

        elif status == 'error':
            self.pipeline_panel.add_event(EventType.ERROR, f"Failed to generate {frame_id}: {error}")

    def _generation_complete(self) -> None:
        """Handle generation completion."""
        # End batch on image handler
        if hasattr(self, '_image_handler') and self._image_handler:
            self._image_handler.end_batch()

        self.status_bar.show_success("Generation complete!")
        self.pipeline_panel.end_phase("Storyboard Generation", success=True)
        self.pipeline_panel.add_event(EventType.SUCCESS, f"✅ Generated {self._generation_total} storyboard frames")

        self.assistant.add_response(f"✅ Storyboard generation complete!\n\n📁 Output: {self._generation_output_dir}\n\n**{self._generation_total} frames** generated successfully.")

        # Refresh navigator to show new files
        if self._project_path:
            self.navigator.load_project(self._project_path)

        # Refresh storyboard view to show new images
        if hasattr(self.workspace, 'refresh_storyboard'):
            self.workspace.refresh_storyboard()

    def load_project(self, path: str) -> None:
        """Load a project."""
        old_path = self._project_path
        self._project_path = path
        self.navigator.load_project(path)
        self.workspace.set_project_path(path)  # Set project path for storyboard loading
        self.status_bar.set_status(f"Loaded: {Path(path).name}")
        logger.info(f"Loaded project: {path}")

        # Update window title
        self.title(f"Project Greenlight - {Path(path).name}")

        # Update assistant panel with new project path
        if hasattr(self, 'assistant') and self.assistant:
            self.assistant.set_project_path(path)

        # Reinitialize OmniMind and AssistantBridge for new project
        if old_path != path:
            self._reinitialize_for_project(path)

    def _reinitialize_for_project(self, project_path: str) -> None:
        """Reinitialize OmniMind and AssistantBridge for a new project."""
        logger.info(f"Reinitializing for project: {project_path}")
        path = Path(project_path)

        # Update OmniMind project path and integrations
        if self._omni_mind:
            try:
                self._omni_mind.set_project_path(path)
                logger.info("OmniMind project path updated")

                # Initialize integrations for the tool executor
                self._initialize_tool_integrations(path)
            except Exception as e:
                logger.warning(f"Failed to update OmniMind project path: {e}")

        # Update ContextEngine project path
        if self._context_engine:
            try:
                self._context_engine.set_project_path(path)
                logger.info("ContextEngine project path updated")
            except Exception as e:
                logger.warning(f"Failed to update ContextEngine project path: {e}")

        # Update AssistantBridge project path
        if self._assistant_bridge:
            try:
                self._assistant_bridge.set_project_path(path)
                logger.info("AssistantBridge project path updated")
            except Exception as e:
                logger.warning(f"Failed to update AssistantBridge project path: {e}")

        # Update Agnostic Learner for new project
        self._update_agnostic_learner_for_project(path)

    def _initialize_tool_integrations(self, project_path: Path) -> None:
        """Initialize tool executor integrations for pipelines and systems."""
        if not self._omni_mind or not hasattr(self._omni_mind, 'set_integrations'):
            return

        try:
            from greenlight.references.reference_manager import ReferenceManager
            from greenlight.tags.tag_registry import TagRegistry

            # Create reference manager for the project
            reference_manager = ReferenceManager(project_path)

            # Create tag registry
            tag_registry = TagRegistry()

            # Load existing tags from world config if available
            world_config_path = project_path / "world_bible" / "world_config.json"
            if world_config_path.exists():
                try:
                    import json
                    from greenlight.core.constants import TagCategory
                    world_config = json.loads(world_config_path.read_text(encoding='utf-8'))

                    # Register characters
                    for char in world_config.get("characters", []):
                        tag_name = char.get("tag", "")
                        if tag_name:
                            try:
                                tag_registry.register(
                                    name=tag_name,
                                    category=TagCategory.CHARACTER,
                                    description=char.get("name", "")
                                )
                            except Exception:
                                pass  # Skip invalid tags

                    # Register locations
                    for loc in world_config.get("locations", []):
                        tag_name = loc.get("tag", "")
                        if tag_name:
                            try:
                                tag_registry.register(
                                    name=tag_name,
                                    category=TagCategory.LOCATION,
                                    description=loc.get("name", "")
                                )
                            except Exception:
                                pass  # Skip invalid tags

                    # Register props
                    for prop in world_config.get("props", []):
                        tag_name = prop.get("tag", "")
                        if tag_name:
                            try:
                                tag_registry.register(
                                    name=tag_name,
                                    category=TagCategory.PROP,
                                    description=prop.get("name", "")
                                )
                            except Exception:
                                pass  # Skip invalid tags

                    logger.info(f"Loaded {len(tag_registry._tags)} tags from world config")
                except Exception as e:
                    logger.warning(f"Failed to load tags from world config: {e}")

            # Set integrations on OmniMind (which passes to tool executor)
            self._omni_mind.set_integrations(
                reference_manager=reference_manager
            )

            # Also update the tag registry on tool executor directly
            if hasattr(self._omni_mind, 'tool_executor'):
                self._omni_mind.tool_executor.set_integrations(
                    tag_registry=tag_registry,
                    reference_manager=reference_manager
                )

            logger.info("✅ Tool integrations initialized for project")

        except Exception as e:
            logger.warning(f"Failed to initialize tool integrations: {e}")

    def _update_agnostic_learner_for_project(self, project_path: Path) -> None:
        """Update Agnostic Learner with project-specific context."""
        if not HAS_AGNOSTIC_CORE:
            return

        try:
            # Reinitialize platform with project path
            self._agnostic_platform = AgnosticCorePlatform(project_path=project_path)
            logger.info(f"AgnosticCorePlatform updated for project: {project_path.name}")

            # Initialize project-specific learning storage
            learning_path = project_path / ".learning"
            self._comparison_learning = ComparisonLearning(storage_path=learning_path)

            # Reconnect engines
            if self._image_engine:
                self._comparison_learning.connect_engines(
                    image_engine=self._image_engine,
                    audio_engine=None
                )

            # Load project-specific notations into library
            if self._notation_library:
                # Scan project for notation definitions
                notation_files = list(project_path.glob("**/*.notation.json"))
                for nf in notation_files[:10]:  # Limit to 10 files
                    try:
                        self._notation_library.load_from_file(nf)
                    except Exception:
                        pass

            logger.info(f"✅ Agnostic Learner updated for project: {project_path.name}")

        except Exception as e:
            logger.warning(f"Failed to update Agnostic Learner: {e}")

    def set_omni_mind(self, omni_mind) -> None:
        """Set the Omni Mind instance."""
        self._omni_mind = omni_mind

    def _build_llm_options(self) -> Dict[str, LLMInfo]:
        """Build the LLM options dictionary for the dropdown."""
        options = {}

        # Define the order and display names for LLMs
        # IDs must match LLM_REGISTRY keys (use hyphens, not underscores)
        llm_display_order = [
            ("gemini-pro", "🌟 Gemini 3 Pro"),
            ("gemini-flash", "⚡ Gemini 2.5 Flash"),
            ("claude-opus", "🎭 Claude Opus 4.5"),
            ("claude-sonnet", "🎵 Claude Sonnet 4.5"),
            ("claude-haiku", "🌸 Claude Haiku 4.5"),
            ("grok-4", "🧠 Grok 4"),
            ("grok-3-fast", "🚀 Grok 3 Fast"),
        ]

        for llm_id, display_name in llm_display_order:
            if llm_id in LLM_REGISTRY:
                llm_info = LLM_REGISTRY[llm_id]
                # Include all LLMs, mark unavailable ones
                if llm_info.is_available():
                    options[display_name] = llm_info
                else:
                    options[f"{display_name} (no key)"] = llm_info

        return options

    def _on_llm_selected(self, selection: str) -> None:
        """Handle LLM selection change."""
        if selection in self._llm_options:
            self._selected_llm = self._llm_options[selection]
        else:
            # Try to find by partial match (for "(no key)" entries)
            for key, llm_info in self._llm_options.items():
                if selection.startswith(key.split(" (")[0]):
                    self._selected_llm = llm_info
                    break

        # Log the selection
        if self._selected_llm:
            logger.info(f"LLM selected: {self._selected_llm.name} ({self._selected_llm.id})")
            # Only update status bar if it exists (it's created after menu)
            if hasattr(self, 'status_bar'):
                self.status_bar.set_status(f"LLM: {self._selected_llm.name}")

    def get_selected_llm(self) -> Optional[LLMInfo]:
        """Get the currently selected LLM info object."""
        return self._selected_llm

    def get_selected_llm_id(self) -> Optional[str]:
        """Get the currently selected LLM ID."""
        return self._selected_llm.id if self._selected_llm else None

    def _scan_projects_directory(self) -> List[str]:
        """Scan the projects directory and return list of project names."""
        projects = []

        if not self._projects_dir.exists():
            logger.warning(f"Projects directory not found: {self._projects_dir}")
            return projects

        try:
            for item in sorted(self._projects_dir.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    # Check if it has a project.json or looks like a project
                    if (item / "project.json").exists() or \
                       any((item / folder).exists() for folder in ["scripts", "world_bible", "SEASON_01"]):
                        projects.append(item.name)
        except Exception as e:
            logger.error(f"Error scanning projects directory: {e}")

        return projects

    def _on_project_selected(self, project_name: str) -> None:
        """Handle project selection from dropdown."""
        if project_name == "Select a project..." or project_name == "No projects found":
            return

        project_path = self._projects_dir / project_name
        if project_path.exists():
            self.load_project(str(project_path))
        else:
            logger.error(f"Project not found: {project_path}")
            self.status_bar.set_status(f"Project not found: {project_name}", theme.colors.error)

    def _refresh_project_list(self) -> None:
        """Refresh the project list dropdown."""
        self._project_list = self._scan_projects_directory()
        project_values = self._project_list if self._project_list else ["No projects found"]

        self.project_selector.configure(values=project_values)
        self.project_selector.set("Select a project...")

        self.status_bar.set_status(f"Found {len(self._project_list)} project(s)")
        logger.info(f"Refreshed project list: {len(self._project_list)} projects found")

    # ==================== User Journey Handlers ====================

    def _on_journey_input(self, phase: JourneyPhase, user_input: str) -> None:
        """Handle user input from the journey panel."""
        logger.info(f"User input for phase {phase.value}: {user_input[:50]}...")

        # Log to pipeline panel
        self.pipeline_panel.log_user_input(user_input)

        # Notify via assistant
        self.assistant.add_system_message(f"✅ Input Received: Your input for {phase.value} has been recorded")

        # Process input based on phase
        self._process_journey_input(phase, user_input)

    def _on_journey_reiterate(self, phase: JourneyPhase) -> None:
        """Handle reiteration request from journey panel."""
        logger.info(f"Reiterating phase: {phase.value}")

        self.pipeline_panel.log_info(f"Reiterating: {phase.value}")
        self.status_bar.set_status(f"Reiterating {phase.value}...")

        # Re-run the phase
        self._run_journey_phase(phase)

    def _on_journey_skip(self, phase: JourneyPhase) -> None:
        """Handle skip request from journey panel."""
        logger.info(f"Skipping phase: {phase.value}")

        self.pipeline_panel.log_warning(f"Skipped: {phase.value}")

        # Move to next phase
        self._advance_journey()

    def _process_journey_input(self, phase: JourneyPhase, user_input: str) -> None:
        """Process user input for a journey phase."""
        # This would integrate with the actual pipeline
        # For now, just log and advance
        self.pipeline_panel.log_info(f"Processing input for {phase.value}")

        # Simulate processing
        self.after(500, lambda: self._complete_journey_phase(phase))

    def _run_journey_phase(self, phase: JourneyPhase) -> None:
        """Run a specific journey phase."""
        self._current_journey_phase = phase
        self._is_pipeline_running = True

        self.pipeline_panel.set_running(True)
        self.pipeline_panel.start_phase(phase.value)

        # Notify user that input is needed via assistant
        self.assistant.add_system_message(f"✏️ Input Needed: Please provide your input for the {phase.value} phase")

    def _complete_journey_phase(self, phase: JourneyPhase) -> None:
        """Complete a journey phase."""
        self.pipeline_panel.end_phase(phase.value, success=True)

        # Notify via assistant
        self.assistant.add_system_message(f"🎉 Phase Complete: {phase.value}")

        # Advance to next phase
        self._advance_journey()

    def _advance_journey(self) -> None:
        """Advance to the next journey phase."""
        phases = list(JourneyPhase)
        if self._current_journey_phase:
            current_idx = phases.index(self._current_journey_phase)
            if current_idx < len(phases) - 1:
                next_phase = phases[current_idx + 1]
                self._run_journey_phase(next_phase)
            else:
                # Journey complete
                self._is_pipeline_running = False
                self.pipeline_panel.set_running(False)
                self.pipeline_panel.set_idle()
                self.assistant.add_system_message("🎉 Journey Complete: All phases have been completed!")

    def start_user_journey(self) -> None:
        """Start the user journey from the beginning."""
        self.pipeline_panel.log_info("Starting user journey...")
        self._run_journey_phase(JourneyPhase.PITCH)

    # ==================== Pipeline Panel Handlers ====================

    def _on_pipeline_file_click(self, file_path: str) -> None:
        """Handle file click from pipeline panel."""
        logger.info(f"Opening file from pipeline: {file_path}")
        self._open_file_in_workspace(file_path)

    def _on_pipeline_cancel(self) -> None:
        """Handle pipeline cancel request."""
        logger.info("Pipeline cancel requested")
        # Set cancellation flag if pipeline is running
        if hasattr(self, '_pipeline_cancel_flag'):
            self._pipeline_cancel_flag = True
        self.pipeline_panel.log_warning("Pipeline cancellation requested...")
        self.status_bar.set_status("Cancelling pipeline...", theme.colors.warning)

    def _on_notification_file_open(self, file_path: str) -> None:
        """Handle file open from notification."""
        logger.info(f"Opening file from notification: {file_path}")
        self._open_file_in_workspace(file_path)

    def _open_file_in_workspace(self, file_path: str) -> None:
        """Open a file in the main workspace."""
        try:
            from pathlib import Path
            path = Path(file_path)
            if path.exists():
                content = path.read_text(encoding='utf-8')
                self.workspace.set_content(content)
                self.workspace.set_title(path.name)
                self.status_bar.set_status(f"Opened: {path.name}")
        except Exception as e:
            logger.error(f"Failed to open file: {e}")
            self.status_bar.show_error(f"Failed to open file")

    def log_pipeline_event(self, event_type: EventType, message: str, file_path: str = None) -> None:
        """Log an event to the pipeline panel."""
        self.pipeline_panel.add_event(event_type, message, file_path=file_path)

        # If file created, also notify via assistant
        if event_type == EventType.FILE_CREATED and file_path:
            self.assistant.add_system_message(f"📄 File Ready: {message}")

    def _connect_image_handler(self) -> None:
        """Connect ImageHandler to pipeline panel for logging."""
        try:
            from greenlight.core.image_handler import ImageHandler

            handler = ImageHandler.get_instance()

            def on_image_event(event_type: str, data: dict):
                """Handle image generation events."""
                tag = data.get('tag', 'image')
                index = data.get('index')
                total = data.get('total')

                # Use after() to ensure UI updates happen on main thread
                if event_type == 'generating':
                    model = data.get('model', '')
                    self.after(0, lambda: self.pipeline_panel.log_image_generating(
                        tag, model, index, total
                    ))
                elif event_type == 'complete':
                    file_path = data.get('file_path')
                    self.after(0, lambda: self.pipeline_panel.log_image_complete(
                        tag, file_path, index, total
                    ))
                elif event_type == 'error':
                    error = data.get('error', 'Unknown error')
                    self.after(0, lambda: self.pipeline_panel.log_image_error(
                        tag, error, index, total
                    ))
                elif event_type == 'batch_start':
                    self.after(0, lambda: self.pipeline_panel.start_phase(
                        f"Image Generation ({total} images)"
                    ))
                elif event_type == 'batch_end':
                    completed = data.get('completed', 0)
                    self.after(0, lambda: self.pipeline_panel.end_phase(
                        f"Image Generation", success=completed > 0
                    ))

            handler.register_callback(on_image_event)
            logger.info("ImageHandler connected to pipeline panel")

        except Exception as e:
            logger.warning(f"Could not connect ImageHandler to pipeline panel: {e}")

    def destroy(self) -> None:
        """Clean up resources before destroying the window."""
        # Stop backdoor server
        if hasattr(self, '_backdoor') and self._backdoor:
            try:
                from greenlight.omni_mind.backdoor import stop_backdoor
                stop_backdoor()
                logger.info("Backdoor server stopped")
            except Exception as e:
                logger.error(f"Error stopping backdoor: {e}")

        # Stop assistant bridge
        if self._assistant_bridge:
            try:
                self._assistant_bridge.stop()
                logger.info("AssistantBridge stopped")
            except Exception as e:
                logger.error(f"Error stopping AssistantBridge: {e}")

        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=False)

        # Call parent destroy
        super().destroy()


# Alias for backward compatibility
GreenlightApp = Viewport


def run_app():
    """Run the Greenlight Viewport application."""
    app = Viewport()
    app.mainloop()


if __name__ == "__main__":
    run_app()

