"""
OmniMind Backdoor - Socket-based IPC for testing and automation.

The app starts a backdoor server that listens for commands.
External scripts can connect and send commands to control the UI.
"""

import socket
import threading
import json
from typing import Dict, Any, Callable, Optional, List
from pathlib import Path

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.backdoor")

DEFAULT_PORT = 19847
BUFFER_SIZE = 65536


class BackdoorServer:
    """
    Socket server for receiving commands from external scripts.
    Runs in the app process and can access UI elements.
    """

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._handlers: Dict[str, Callable] = {}
        self._main_window = None
        self._error_cache: List[Dict[str, Any]] = []  # Cache of recent errors
        self._max_error_cache = 50  # Max errors to cache
        self._self_healer = None  # SelfHealer instance

    def set_main_window(self, window):
        """Set reference to main window for UI access."""
        self._main_window = window
        # Initialize self-healer
        self._init_self_healer()

    def _init_self_healer(self):
        """Initialize the self-healer with project context."""
        try:
            from greenlight.omni_mind.self_healer import SelfHealer
            project_path = None
            if self._main_window and hasattr(self._main_window, 'project_path'):
                project_path = self._main_window.project_path
            self._self_healer = SelfHealer(project_path=project_path)
            logger.info("SelfHealer initialized for backdoor")
        except Exception as e:
            logger.warning(f"Failed to initialize SelfHealer: {e}")

    def cache_error(self, error: Exception, source: str, context: Dict = None):
        """Cache an error for later retrieval and potential self-healing."""
        from datetime import datetime
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": type(error).__name__,
            "message": str(error),
            "source": source,
            "context": context or {}
        }
        self._error_cache.append(error_entry)
        # Keep cache bounded
        if len(self._error_cache) > self._max_error_cache:
            self._error_cache = self._error_cache[-self._max_error_cache:]

        # Attempt self-healing
        if self._self_healer:
            try:
                result, actions = self._self_healer.heal(error, context or {})
                error_entry["heal_result"] = result.value
                error_entry["heal_actions"] = [a.to_dict() for a in actions]
            except Exception as heal_error:
                logger.debug(f"Self-healing failed: {heal_error}")
        
    def register_handler(self, command: str, handler: Callable):
        """Register a command handler."""
        self._handlers[command] = handler
        
    def start(self):
        """Start the backdoor server."""
        if self.running:
            return
            
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.socket.bind(('127.0.0.1', self.port))
            self.socket.listen(1)
            self.socket.settimeout(1.0)  # Allow checking running flag
            self.running = True
            
            self.thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.thread.start()
            
            logger.info(f"Backdoor server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start backdoor server: {e}")
            
    def stop(self):
        """Stop the backdoor server."""
        self.running = False
        if self.socket:
            self.socket.close()
        logger.info("Backdoor server stopped")
        
    def _listen_loop(self):
        """Main listening loop."""
        while self.running:
            try:
                conn, addr = self.socket.accept()
                self._handle_connection(conn)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Backdoor error: {e}")
                    
    def _handle_connection(self, conn: socket.socket):
        """Handle an incoming connection."""
        try:
            data = conn.recv(BUFFER_SIZE).decode('utf-8')
            if not data:
                return
                
            request = json.loads(data)
            command = request.get('command', '')
            params = request.get('params', {})
            
            response = self._execute_command(command, params)
            conn.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            error_response = {"success": False, "error": str(e)}
            conn.send(json.dumps(error_response).encode('utf-8'))
        finally:
            conn.close()
            
    def _execute_command(self, command: str, params: Dict) -> Dict[str, Any]:
        """Execute a command."""
        logger.info(f"Backdoor command: {command}")
        
        # Built-in commands
        if command == "ping":
            return {"success": True, "message": "pong"}
            
        elif command == "list_ui_elements":
            return self._cmd_list_ui_elements()
            
        elif command == "click":
            return self._cmd_click(params.get("element_id", ""))
            
        elif command == "open_project":
            return self._cmd_open_project(params.get("path", ""))
            
        elif command == "navigate":
            return self._cmd_navigate(params.get("view", ""))
            
        elif command == "run_writer":
            return self._cmd_run_writer(params)

        elif command == "run_director":
            return self._cmd_run_director(params)

        elif command == "run_storyboard":
            return self._cmd_run_storyboard(params)

        elif command == "get_errors":
            return self._cmd_get_errors()

        elif command == "clear_errors":
            return self._cmd_clear_errors()

        elif command == "self_heal":
            return self._cmd_self_heal(params)

        elif command == "get_healer_report":
            return self._cmd_get_healer_report()

        elif command == "set_zoom":
            return self._cmd_set_zoom(params)

        elif command == "select_frames":
            return self._cmd_select_frames(params)

        elif command == "get_selected_frames":
            return self._cmd_get_selected_frames()

        elif command == "regenerate_selected":
            return self._cmd_regenerate_selected()

        elif command == "clear_selection":
            return self._cmd_clear_selection()

        elif command == "debug_workspace":
            return self._cmd_debug_workspace()

        elif command == "execute_tool":
            return self._cmd_execute_tool(params)

        elif command == "autonomous_modify_character":
            return self._cmd_autonomous_modify_character(params)

        elif command == "execute_autonomous":
            return self._cmd_execute_autonomous(params)

        elif command == "continuity_check":
            return self._cmd_continuity_check(params)

        elif command == "run_e2e_pipeline":
            return self._cmd_run_e2e_pipeline(params)

        elif command == "generate_reference_images":
            return self._cmd_generate_reference_images(params)

        elif command == "get_e2e_status":
            return self._cmd_get_e2e_status()

        elif command == "wait_for_pipeline":
            return self._cmd_wait_for_pipeline(params)

        # Self-correction commands
        elif command == "detect_missing_characters":
            return self._cmd_detect_missing_characters()

        elif command == "fix_missing_characters":
            return self._cmd_fix_missing_characters(params)

        elif command == "validate_world_config":
            return self._cmd_validate_world_config()

        # Custom handlers
        elif command in self._handlers:
            try:
                result = self._handlers[command](params)
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}
                
        else:
            return {"success": False, "error": f"Unknown command: {command}"}
            
    def _cmd_list_ui_elements(self) -> Dict[str, Any]:
        """List UI elements."""
        try:
            from greenlight.ui.components.ui_pointer import get_ui_registry
            registry = get_ui_registry()
            elements = registry.get_element_info()
            return {"success": True, "elements": elements, "count": len(elements)}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _cmd_click(self, element_id: str) -> Dict[str, Any]:
        """Click a UI element."""
        try:
            from greenlight.ui.components.ui_pointer import click_element
            success = click_element(element_id)
            return {"success": success, "element_id": element_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_open_project(self, path: str) -> Dict[str, Any]:
        """Open a project."""
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            # Schedule on main thread
            self._main_window.after(0, lambda: self._main_window.load_project(Path(path)))
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_navigate(self, view: str) -> Dict[str, Any]:
        """Navigate to a view."""
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            self._main_window.after(0, lambda: self._main_window.workspace.set_view(view))
            return {"success": True, "view": view}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_run_writer(self, params: Dict) -> Dict[str, Any]:
        """Run the writer pipeline with optional auto-run parameters.

        Params:
            auto_run: bool - If True, run immediately without UI (default: True)
            llm: str - LLM to use (default: 'claude-haiku')
            media_type: str - Media type: 'brief', 'short', 'standard', 'extended', 'feature' (default: 'brief')
            visual_style: str - Visual style (default: 'live_action')
        """
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            auto_run = params.get("auto_run", True)
            llm = params.get("llm", "claude-haiku")
            media_type = params.get("media_type", "brief")
            visual_style = params.get("visual_style", "live_action")

            def run_writer():
                from greenlight.ui.dialogs.writer_dialog import WriterDialog
                project_path = Path(self._main_window._project_path) if self._main_window._project_path else None
                if not project_path:
                    logger.error("No project loaded")
                    return

                def on_complete(result):
                    self._main_window.status_bar.show_success("Writer complete!")
                    self._main_window.pipeline_panel.end_phase("Writer", success=True)
                    self._main_window.pipeline_panel.set_idle()
                    self._main_window.navigator.load_project(self._main_window._project_path)

                def external_log(msg):
                    self._main_window.pipeline_panel.log_info(msg)

                def external_progress(val):
                    self._main_window.pipeline_panel.set_progress(val)

                self._main_window.pipeline_panel.start_phase("Writer")
                self._main_window.status_bar.show_processing("Running Writer pipeline...")

                WriterDialog(
                    self._main_window,
                    project_path=project_path,
                    on_complete=on_complete,
                    external_log=external_log,
                    external_progress=external_progress,
                    close_on_start=True,
                    auto_run=auto_run,
                    auto_llm=llm,
                    auto_media_type=media_type,
                    auto_visual_style=visual_style
                )

            self._main_window.after(0, run_writer)
            return {"success": True, "message": f"Writer pipeline started (auto_run={auto_run}, llm={llm}, media_type={media_type})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_run_director(self, params: Dict) -> Dict[str, Any]:
        """Run the director pipeline with optional auto-run parameters.

        Params:
            auto_run: bool - If True, run immediately without UI (default: True)
            llm: str - LLM to use (default: 'gemini-flash')

        Note: Frame count is now determined autonomously by the pipeline.
        """
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            auto_run = params.get("auto_run", True)
            llm = params.get("llm", "gemini-flash")

            def run_director():
                from greenlight.ui.dialogs.director_dialog import DirectorDialog
                project_path = Path(self._main_window._project_path) if self._main_window._project_path else None
                if not project_path:
                    logger.error("No project loaded")
                    return

                def on_complete(result):
                    self._main_window.status_bar.show_success("Director complete!")
                    self._main_window.pipeline_panel.end_phase("Director", success=True)
                    self._main_window.pipeline_panel.set_idle()
                    self._main_window.navigator.load_project(self._main_window._project_path)

                def external_log(msg):
                    self._main_window.pipeline_panel.log_info(msg)

                def external_progress(val):
                    self._main_window.pipeline_panel.set_progress(val)

                self._main_window.pipeline_panel.start_phase("Director")
                self._main_window.status_bar.show_processing("Running Director pipeline...")

                DirectorDialog(
                    self._main_window,
                    project_path=project_path,
                    on_complete=on_complete,
                    external_log=external_log,
                    external_progress=external_progress,
                    close_on_start=auto_run,
                    auto_llm=llm
                )

            self._main_window.after(0, run_director)
            return {"success": True, "message": f"Director pipeline started (auto_run={auto_run}, llm={llm})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_run_storyboard(self, params: Dict) -> Dict[str, Any]:
        """Run the storyboard generation pipeline directly (bypasses modal).

        Params:
            model: str - Image model to use (default: 'seedream')
            start_shot: str - Starting shot ID (optional)
            end_shot: str - Ending shot ID (optional)
        """
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            import json
            from pathlib import Path

            model = params.get("model", "seedream")

            # Get project path
            project_path = getattr(self._main_window, '_project_path', None)
            if not project_path:
                return {"success": False, "error": "No project loaded"}

            project_path = Path(project_path)
            visual_script_file = project_path / "storyboard" / "visual_script.json"

            if not visual_script_file.exists():
                return {"success": False, "error": "No visual script found. Run Director first."}

            # Load visual script
            with open(visual_script_file, 'r', encoding='utf-8') as f:
                visual_script_data = json.load(f)

            total_frames = visual_script_data.get('total_frames', 0)
            if total_frames == 0:
                return {"success": False, "error": "No frames found in visual script"}

            def run_storyboard():
                # Directly start generation without modal
                self._main_window._start_storyboard_generation(model, visual_script_data, project_path)

            self._main_window.after(0, run_storyboard)
            return {"success": True, "message": f"Storyboard generation started (model={model}, frames={total_frames})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_get_errors(self) -> Dict[str, Any]:
        """Get recent errors from the error cache."""
        try:
            errors = self._error_cache.copy()
            healer_stats = {}
            if self._self_healer:
                healer_stats = self._self_healer.get_stats()

            return {
                "success": True,
                "errors": errors,
                "count": len(errors),
                "healer_stats": healer_stats,
                "message": f"{len(errors)} error(s) cached"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_clear_errors(self) -> Dict[str, Any]:
        """Clear the error cache."""
        try:
            count = len(self._error_cache)
            self._error_cache.clear()
            return {"success": True, "cleared": count, "message": f"Cleared {count} error(s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_self_heal(self, params: Dict) -> Dict[str, Any]:
        """Trigger self-healing for a specific error or all cached errors."""
        try:
            if not self._self_healer:
                self._init_self_healer()
                if not self._self_healer:
                    return {"success": False, "error": "SelfHealer not available"}

            # Get project path for context
            project_path = None
            if self._main_window and hasattr(self._main_window, 'project_path'):
                project_path = self._main_window.project_path

            error_index = params.get("error_index")
            results = []

            if error_index is not None:
                # Heal specific error
                if 0 <= error_index < len(self._error_cache):
                    error_entry = self._error_cache[error_index]
                    # Create exception from cached error
                    error = Exception(error_entry["message"])
                    context = error_entry.get("context", {})
                    context["project_path"] = project_path
                    result, actions = self._self_healer.heal(error, context)
                    results.append({
                        "index": error_index,
                        "result": result.value,
                        "actions": [a.to_dict() for a in actions]
                    })
            else:
                # Heal all cached errors
                for i, error_entry in enumerate(self._error_cache):
                    error = Exception(error_entry["message"])
                    context = error_entry.get("context", {})
                    context["project_path"] = project_path
                    result, actions = self._self_healer.heal(error, context)
                    results.append({
                        "index": i,
                        "result": result.value,
                        "actions": [a.to_dict() for a in actions]
                    })

            return {
                "success": True,
                "results": results,
                "stats": self._self_healer.get_stats()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_get_healer_report(self) -> Dict[str, Any]:
        """Get the self-healer report."""
        try:
            if not self._self_healer:
                return {"success": False, "error": "SelfHealer not initialized"}

            return {
                "success": True,
                "report": self._self_healer.generate_report(),
                "stats": self._self_healer.get_stats(),
                "history": [a.to_dict() for a in self._self_healer.get_history()]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_set_zoom(self, params: Dict) -> Dict[str, Any]:
        """Set the storyboard zoom level."""
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            zoom = params.get("zoom", 50)
            def set_zoom():
                if hasattr(self._main_window, 'workspace') and hasattr(self._main_window.workspace, 'storyboard_view'):
                    storyboard = self._main_window.workspace.storyboard_view
                    if hasattr(storyboard, 'storyboard_table') and storyboard.storyboard_table:
                        storyboard.storyboard_table.zoom_slider.set(zoom)
                        storyboard.storyboard_table._on_zoom_change(zoom)
            self._main_window.after(0, set_zoom)
            return {"success": True, "zoom": zoom}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_storyboard_table(self):
        """Get the storyboard table from main window."""
        if not self._main_window:
            return None
        if hasattr(self._main_window, 'workspace'):
            workspace = self._main_window.workspace
            # Check for direct storyboard_table attribute
            if hasattr(workspace, 'storyboard_table') and workspace.storyboard_table:
                try:
                    # Check if widget still exists
                    workspace.storyboard_table.winfo_exists()
                    return workspace.storyboard_table
                except:
                    pass
            # Fallback: check for storyboard_view.storyboard_table
            if hasattr(workspace, 'storyboard_view') and workspace.storyboard_view:
                if hasattr(workspace.storyboard_view, 'storyboard_table'):
                    try:
                        workspace.storyboard_view.storyboard_table.winfo_exists()
                        return workspace.storyboard_view.storyboard_table
                    except:
                        pass
        return None

    def _cmd_select_frames(self, params: Dict) -> Dict[str, Any]:
        """Select frames by their shot IDs."""
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            frame_ids = params.get("frame_ids", [])
            clear_existing = params.get("clear_existing", True)

            result_holder = {"selected": []}

            def do_select():
                table = self._get_storyboard_table()
                if table:
                    table.select_frames_by_id(frame_ids, clear_existing)
                    result_holder["selected"] = [f.shot_id for f in table.get_selected_frames()]

            self._main_window.after(0, do_select)
            return {"success": True, "frame_ids": frame_ids, "message": f"Selected {len(frame_ids)} frames"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_get_selected_frames(self) -> Dict[str, Any]:
        """Get currently selected frames."""
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            table = self._get_storyboard_table()
            if table:
                selected = table.get_selected_frames()
                return {
                    "success": True,
                    "count": len(selected),
                    "frames": [{"shot_id": f.shot_id, "scene": f.scene_id} for f in selected]
                }
            return {"success": False, "error": "Storyboard table not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_regenerate_selected(self) -> Dict[str, Any]:
        """Trigger regeneration of selected frames."""
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            def do_regenerate():
                table = self._get_storyboard_table()
                if table:
                    table._on_regenerate_selected_click()

            self._main_window.after(0, do_regenerate)
            return {"success": True, "message": "Regeneration triggered for selected frames"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_clear_selection(self) -> Dict[str, Any]:
        """Clear all frame selections."""
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            def do_clear():
                table = self._get_storyboard_table()
                if table:
                    table._clear_selection()

            self._main_window.after(0, do_clear)
            return {"success": True, "message": "Selection cleared"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_debug_workspace(self) -> Dict[str, Any]:
        """Debug workspace state."""
        if not self._main_window:
            return {"success": False, "error": "Main window not set"}
        try:
            workspace = self._main_window.workspace if hasattr(self._main_window, 'workspace') else None
            if not workspace:
                return {"success": False, "error": "No workspace"}

            info = {
                "has_workspace": True,
                "mode": str(workspace._mode) if hasattr(workspace, '_mode') else "unknown",
                "has_storyboard_table": hasattr(workspace, 'storyboard_table'),
                "storyboard_table_value": str(workspace.storyboard_table) if hasattr(workspace, 'storyboard_table') else None,
                "current_content_keys": list(workspace._current_content.keys()) if hasattr(workspace, '_current_content') else [],
                "project_path": str(workspace._current_content.get('project_path', 'None')) if hasattr(workspace, '_current_content') else None,
            }
            return {"success": True, "info": info}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_execute_tool(self, params: Dict) -> Dict[str, Any]:
        """Execute a tool from the ToolExecutor."""
        try:
            from greenlight.omni_mind.tool_executor import ToolExecutor

            tool_name = params.get("tool", "")
            tool_params = params.get("params", {})

            if not tool_name:
                return {"success": False, "error": "No tool specified"}

            # Get project path from main window
            project_path = None
            if self._main_window and hasattr(self._main_window, 'project_path'):
                project_path = self._main_window.project_path

            executor = ToolExecutor(project_path=project_path)
            result = executor.execute(tool_name, **tool_params)

            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_autonomous_modify_character(self, params: Dict) -> Dict[str, Any]:
        """Execute autonomous character modification workflow."""
        try:
            from greenlight.omni_mind.autonomous_agent import AutonomousTaskManager

            character_tag = params.get("character_tag", "")
            modification = params.get("modification", "")
            auto_execute = params.get("auto_execute", True)

            if not character_tag or not modification:
                return {"success": False, "error": "character_tag and modification required"}

            # Get project path (check both _project_path and project_path)
            project_path = None
            if self._main_window:
                if hasattr(self._main_window, '_project_path'):
                    project_path = self._main_window._project_path
                elif hasattr(self._main_window, 'project_path'):
                    project_path = self._main_window.project_path

            if not project_path:
                return {"success": False, "error": "No project loaded"}

            # Create task manager
            manager = AutonomousTaskManager(project_path=project_path)

            # Execute the modification
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    manager.execute_character_modification(
                        character_tag=character_tag,
                        modification_description=modification,
                        auto_execute=auto_execute
                    )
                )
            finally:
                loop.close()

            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_execute_autonomous(self, params: Dict) -> Dict[str, Any]:
        """Execute an autonomous task using natural language."""
        try:
            from greenlight.omni_mind.autonomous_agent import AutonomousTaskManager

            task_description = params.get("task", "")
            if not task_description:
                return {"success": False, "error": "No task description provided"}

            # Get project path
            project_path = None
            if self._main_window and hasattr(self._main_window, 'project_path'):
                project_path = self._main_window.project_path

            if not project_path:
                return {"success": False, "error": "No project loaded"}

            # Create task manager
            manager = AutonomousTaskManager(project_path=project_path)

            # Plan and execute tasks
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Plan tasks from natural language
                tasks = loop.run_until_complete(
                    manager.plan_character_modification("", task_description)
                )

                # Execute all pending tasks
                results = loop.run_until_complete(manager.execute_all_pending())
            finally:
                loop.close()

            return {
                "success": True,
                "tasks_planned": len(tasks),
                "results": results
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_continuity_check(self, params: Dict) -> Dict[str, Any]:
        """Execute continuity check on storyboard frames."""
        try:
            from greenlight.omni_mind.autonomous_agent import AutonomousTaskManager

            user_request = params.get("request", params.get("user_request", ""))
            auto_fix = params.get("auto_fix", True)

            if not user_request:
                return {"success": False, "error": "No request provided"}

            # Get project path
            project_path = None
            if self._main_window:
                if hasattr(self._main_window, '_project_path'):
                    project_path = self._main_window._project_path
                elif hasattr(self._main_window, 'project_path'):
                    project_path = self._main_window.project_path

            if not project_path:
                return {"success": False, "error": "No project loaded"}

            # Create task manager
            manager = AutonomousTaskManager(project_path=project_path)

            # Execute continuity check
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    manager.execute_continuity_check(user_request, auto_fix=auto_fix)
                )
            finally:
                loop.close()

            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_run_e2e_pipeline(self, params: Dict) -> Dict[str, Any]:
        """Run complete end-to-end pipeline: Writer → Director → References → Storyboard.

        Params:
            llm: str - LLM to use (default: 'claude-sonnet-4.5')
            image_model: str - Image model (default: 'seedream')
            generate_references: bool - Generate reference images (default: True)
            dry_run: bool - Preview without executing (default: False)

        Note: Frame count is now determined autonomously by the Director pipeline.
        """
        try:
            from greenlight.omni_mind.tool_executor import ToolExecutor

            # Get project path
            project_path = None
            if self._main_window:
                if hasattr(self._main_window, '_project_path'):
                    project_path = self._main_window._project_path
                elif hasattr(self._main_window, 'project_path'):
                    project_path = self._main_window.project_path

            if not project_path:
                return {"success": False, "error": "No project loaded"}

            executor = ToolExecutor(project_path=Path(project_path))

            result = executor.execute(
                "run_e2e_pipeline",
                llm=params.get("llm", "claude-sonnet-4.5"),
                image_model=params.get("image_model", "seedream"),
                generate_references=params.get("generate_references", True),
                dry_run=params.get("dry_run", False)
            )

            return {"success": result.success, "result": result.result, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_generate_reference_images(self, params: Dict) -> Dict[str, Any]:
        """Generate reference images for all extracted tags.

        Params:
            tag_types: list - Tag types to process (default: all)
            model: str - Image model (default: 'nano_banana_pro')
            overwrite: bool - Overwrite existing references (default: False)
        """
        try:
            from greenlight.omni_mind.tool_executor import ToolExecutor

            project_path = None
            if self._main_window:
                if hasattr(self._main_window, '_project_path'):
                    project_path = self._main_window._project_path
                elif hasattr(self._main_window, 'project_path'):
                    project_path = self._main_window.project_path

            if not project_path:
                return {"success": False, "error": "No project loaded"}

            executor = ToolExecutor(project_path=Path(project_path))

            result = executor.execute(
                "generate_all_reference_images",
                tag_types=params.get("tag_types", ["character", "location", "prop"]),
                model=params.get("model", "nano_banana_pro"),
                overwrite=params.get("overwrite", False)
            )

            return {"success": result.success, "result": result.result, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_get_e2e_status(self) -> Dict[str, Any]:
        """Get status of the end-to-end pipeline execution."""
        try:
            from greenlight.omni_mind.tool_executor import ToolExecutor

            project_path = None
            if self._main_window:
                if hasattr(self._main_window, '_project_path'):
                    project_path = self._main_window._project_path
                elif hasattr(self._main_window, 'project_path'):
                    project_path = self._main_window.project_path

            if not project_path:
                return {"success": False, "error": "No project loaded"}

            executor = ToolExecutor(project_path=Path(project_path))
            result = executor.execute("get_e2e_pipeline_status")

            return {"success": result.success, "result": result.result, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_wait_for_pipeline(self, params: Dict) -> Dict[str, Any]:
        """Wait for a running pipeline to complete.

        Params:
            pipeline_name: str - Pipeline to wait for (default: 'any')
            timeout_seconds: int - Max wait time (default: 300)
        """
        try:
            from greenlight.omni_mind.tool_executor import ToolExecutor

            project_path = None
            if self._main_window:
                if hasattr(self._main_window, '_project_path'):
                    project_path = self._main_window._project_path
                elif hasattr(self._main_window, 'project_path'):
                    project_path = self._main_window.project_path

            if not project_path:
                return {"success": False, "error": "No project loaded"}

            executor = ToolExecutor(project_path=Path(project_path))

            result = executor.execute(
                "wait_for_pipeline",
                pipeline_name=params.get("pipeline_name", "any"),
                timeout_seconds=params.get("timeout_seconds", 300)
            )

            return {"success": result.success, "result": result.result, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # SELF-CORRECTION COMMANDS
    # =========================================================================

    def _cmd_detect_missing_characters(self) -> Dict[str, Any]:
        """Detect consensus-approved character tags missing from world_config.json."""
        try:
            from greenlight.omni_mind.tool_executor import ToolExecutor

            project_path = None
            if self._main_window:
                if hasattr(self._main_window, '_project_path'):
                    project_path = self._main_window._project_path
                elif hasattr(self._main_window, 'project_path'):
                    project_path = self._main_window.project_path

            if not project_path:
                return {"success": False, "error": "No project loaded"}

            executor = ToolExecutor(project_path=Path(project_path))
            result = executor.execute("detect_missing_characters")

            return {"success": result.success, "result": result.result, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_fix_missing_characters(self, params: Dict) -> Dict[str, Any]:
        """Automatically generate and insert missing character profiles.

        Params:
            missing_tags: list - Specific tags to fix (optional, auto-detects if empty)
            dry_run: bool - Preview without making changes (default: False)
        """
        try:
            from greenlight.omni_mind.tool_executor import ToolExecutor

            project_path = None
            if self._main_window:
                if hasattr(self._main_window, '_project_path'):
                    project_path = self._main_window._project_path
                elif hasattr(self._main_window, 'project_path'):
                    project_path = self._main_window.project_path

            if not project_path:
                return {"success": False, "error": "No project loaded"}

            executor = ToolExecutor(project_path=Path(project_path))

            result = executor.execute(
                "fix_missing_characters",
                missing_tags=params.get("missing_tags", []),
                dry_run=params.get("dry_run", False)
            )

            return {"success": result.success, "result": result.result, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_validate_world_config(self) -> Dict[str, Any]:
        """Validate that all consensus-approved tags have entries in world_config.json."""
        try:
            from greenlight.omni_mind.tool_executor import ToolExecutor

            project_path = None
            if self._main_window:
                if hasattr(self._main_window, '_project_path'):
                    project_path = self._main_window._project_path
                elif hasattr(self._main_window, 'project_path'):
                    project_path = self._main_window.project_path

            if not project_path:
                return {"success": False, "error": "No project loaded"}

            executor = ToolExecutor(project_path=Path(project_path))
            result = executor.execute("validate_world_config")

            return {"success": result.success, "result": result.result, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}


class BackdoorClient:
    """Client for sending commands to the backdoor server."""

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port

    def send_command(self, command: str, params: Dict = None, timeout: float = 10.0) -> Dict[str, Any]:
        """Send a command to the backdoor server.

        Args:
            command: Command name
            params: Command parameters
            timeout: Socket timeout in seconds (default 10, use higher for long operations)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(('127.0.0.1', self.port))

            request = {"command": command, "params": params or {}}
            sock.send(json.dumps(request).encode('utf-8'))

            response = sock.recv(BUFFER_SIZE).decode('utf-8')
            sock.close()

            return json.loads(response)
        except ConnectionRefusedError:
            return {"success": False, "error": "Backdoor server not running"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def ping(self) -> bool:
        """Check if server is running."""
        result = self.send_command("ping")
        return result.get("success", False)

    def list_ui_elements(self) -> Dict[str, Any]:
        """List UI elements."""
        return self.send_command("list_ui_elements")

    def click(self, element_id: str) -> Dict[str, Any]:
        """Click a UI element."""
        return self.send_command("click", {"element_id": element_id})

    def open_project(self, path: str) -> Dict[str, Any]:
        """Open a project."""
        return self.send_command("open_project", {"path": path})

    def navigate(self, view: str) -> Dict[str, Any]:
        """Navigate to a view."""
        return self.send_command("navigate", {"view": view})

    def run_director(self, llm_id: str = None) -> Dict[str, Any]:
        """Run director pipeline."""
        return self.send_command("run_director", {"llm_id": llm_id})

    def execute_tool(self, tool_name: str, **params) -> Dict[str, Any]:
        """Execute a tool from the ToolExecutor."""
        return self.send_command("execute_tool", {"tool": tool_name, "params": params})

    def autonomous_modify_character(
        self,
        character_tag: str,
        modification: str,
        auto_execute: bool = True
    ) -> Dict[str, Any]:
        """Execute autonomous character modification."""
        return self.send_command("autonomous_modify_character", {
            "character_tag": character_tag,
            "modification": modification,
            "auto_execute": auto_execute
        }, timeout=120.0)  # Long timeout for autonomous operations

    def execute_autonomous(self, task: str) -> Dict[str, Any]:
        """Execute an autonomous task using natural language."""
        return self.send_command("execute_autonomous", {"task": task}, timeout=120.0)

    def continuity_check(
        self,
        request: str,
        auto_fix: bool = True
    ) -> Dict[str, Any]:
        """
        Execute continuity check on storyboard frames.

        Args:
            request: Natural language request (e.g., "frame 1.3 seems weird")
            auto_fix: Whether to automatically fix issues and regenerate

        Returns:
            Continuity analysis and fix results
        """
        return self.send_command("continuity_check", {
            "request": request,
            "auto_fix": auto_fix
        }, timeout=300.0)  # 5 min timeout for analysis + regeneration

    def run_e2e_pipeline(
        self,
        llm: str = "claude-sonnet-4.5",
        image_model: str = "seedream",
        generate_references: bool = True,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Run complete end-to-end pipeline: Writer → Director → References → Storyboard.

        Args:
            llm: LLM to use ('claude-sonnet-4.5', 'claude-haiku', 'gemini-flash')
            image_model: Image model ('seedream', 'nano_banana_pro')
            generate_references: Whether to generate reference images
            dry_run: Preview without executing

        Returns:
            Pipeline execution result

        Note: Frame count is now determined autonomously by the Director pipeline.
        """
        return self.send_command("run_e2e_pipeline", {
            "llm": llm,
            "image_model": image_model,
            "generate_references": generate_references,
            "dry_run": dry_run
        }, timeout=600.0)  # 10 min timeout for full pipeline

    def generate_reference_images(
        self,
        tag_types: List[str] = None,
        model: str = "nano_banana_pro",
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Generate reference images for all extracted tags.

        Args:
            tag_types: Tag types to process (default: all)
            model: Image model to use
            overwrite: Whether to overwrite existing references

        Returns:
            Generation result with counts
        """
        return self.send_command("generate_reference_images", {
            "tag_types": tag_types or ["character", "location", "prop"],
            "model": model,
            "overwrite": overwrite
        }, timeout=300.0)

    def get_e2e_status(self) -> Dict[str, Any]:
        """Get status of the end-to-end pipeline execution."""
        return self.send_command("get_e2e_status")

    def wait_for_pipeline(
        self,
        pipeline_name: str = "any",
        timeout_seconds: int = 300
    ) -> Dict[str, Any]:
        """
        Wait for a running pipeline to complete.

        Args:
            pipeline_name: Pipeline to wait for ('writer', 'director', 'storyboard', 'any')
            timeout_seconds: Max wait time

        Returns:
            Final pipeline status
        """
        return self.send_command("wait_for_pipeline", {
            "pipeline_name": pipeline_name,
            "timeout_seconds": timeout_seconds
        }, timeout=float(timeout_seconds + 30))

    # =========================================================================
    # SELF-CORRECTION CLIENT METHODS
    # =========================================================================

    def detect_missing_characters(self) -> Dict[str, Any]:
        """
        Detect consensus-approved character tags missing from world_config.json.

        Returns:
            Detection result with missing_tags list
        """
        return self.send_command("detect_missing_characters")

    def fix_missing_characters(
        self,
        missing_tags: List[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Automatically generate and insert missing character profiles.

        Args:
            missing_tags: Specific tags to fix (auto-detects if empty)
            dry_run: Preview without making changes

        Returns:
            Fix result with fixed_count and fixed_tags
        """
        return self.send_command("fix_missing_characters", {
            "missing_tags": missing_tags or [],
            "dry_run": dry_run
        }, timeout=120.0)  # 2 min timeout for LLM generation

    def validate_world_config(self) -> Dict[str, Any]:
        """
        Validate that all consensus-approved tags have entries in world_config.json.

        Returns:
            Validation result with missing items by category
        """
        return self.send_command("validate_world_config")

    # =========================================================================
    # SELF-HEALING CLIENT METHODS
    # =========================================================================

    def get_errors(self) -> Dict[str, Any]:
        """
        Get cached errors and self-healer stats.

        Returns:
            Dict with errors list, count, and healer_stats
        """
        return self.send_command("get_errors")

    def clear_errors(self) -> Dict[str, Any]:
        """
        Clear the error cache.

        Returns:
            Dict with cleared count
        """
        return self.send_command("clear_errors")

    def self_heal(self, error_index: int = None) -> Dict[str, Any]:
        """
        Trigger self-healing for cached errors.

        Args:
            error_index: Specific error index to heal (heals all if None)

        Returns:
            Dict with healing results and stats
        """
        params = {}
        if error_index is not None:
            params["error_index"] = error_index
        return self.send_command("self_heal", params, timeout=60.0)

    def get_healer_report(self) -> Dict[str, Any]:
        """
        Get the self-healer report with stats and history.

        Returns:
            Dict with report, stats, and history
        """
        return self.send_command("get_healer_report")


# Global server instance
_server: Optional[BackdoorServer] = None


def get_backdoor_server() -> BackdoorServer:
    """Get or create the backdoor server."""
    global _server
    if _server is None:
        _server = BackdoorServer()
    return _server


def start_backdoor(main_window=None):
    """Start the backdoor server."""
    server = get_backdoor_server()
    if main_window:
        server.set_main_window(main_window)
    server.start()
    return server


def stop_backdoor():
    """Stop the backdoor server."""
    global _server
    if _server:
        _server.stop()
        _server = None

