"""
Greenlight Runtime Integration

Connects Greenlight to the Agnostic_Core_OS runtime as the first integrated app.
Provides event-driven pipeline execution and inter-app communication.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
from datetime import datetime
from pathlib import Path
from enum import Enum
import logging

if TYPE_CHECKING:
    from Agnostic_Core_OS.runtime import RuntimeDaemon, AppSDK, Event

logger = logging.getLogger("greenlight.runtime_integration")


class PipelineType(Enum):
    """Types of Greenlight pipelines."""
    WRITER = "writer"
    DIRECTOR = "director"
    WORLD_BIBLE = "world_bible"
    TAG_EXTRACTION = "tag_extraction"


class PipelineStatus(Enum):
    """Pipeline execution status."""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineProgress:
    """Progress information for a running pipeline."""
    pipeline: PipelineType
    status: PipelineStatus
    progress: float = 0.0
    current_phase: str = ""
    current_item: str = ""
    items_completed: int = 0
    items_total: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline": self.pipeline.value,
            "status": self.status.value,
            "progress": self.progress,
            "current_phase": self.current_phase,
            "current_item": self.current_item,
            "items_completed": self.items_completed,
            "items_total": self.items_total,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


class GreenlightRuntimeBridge:
    """
    Bridge between Greenlight and Agnostic_Core_OS runtime.
    
    Features:
    - Connects Greenlight as an app via AppSDK
    - Emits pipeline events for other apps to consume
    - Subscribes to runtime events
    - Provides progress callbacks for UI integration
    
    Usage:
        from greenlight.runtime_integration import GreenlightRuntimeBridge
        
        bridge = GreenlightRuntimeBridge()
        await bridge.connect(daemon)
        
        # Run pipeline with event emission
        await bridge.run_writer_pipeline(project_path, config)
    """
    
    GREENLIGHT_CAPABILITIES = [
        "story_pipeline",
        "directing_pipeline",
        "world_bible",
        "tag_extraction",
        "multi_agent_consensus",
        "procedural_generation",
        "frame_notation",
        "character_roleplay",
    ]
    
    def __init__(self):
        self._sdk: Optional["AppSDK"] = None
        self._connected = False
        self._project_path: Optional[Path] = None
        self._active_pipelines: Dict[PipelineType, PipelineProgress] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._ui_callbacks: Dict[str, Callable] = {}
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self._sdk is not None
    
    @property
    def app_id(self) -> Optional[str]:
        if self._sdk and self._sdk._connection:
            return self._sdk._connection.app_id
        return None
    
    async def connect(self, daemon: "RuntimeDaemon") -> bool:
        """Connect Greenlight to the runtime."""
        try:
            from Agnostic_Core_OS.runtime import AppSDK

            self._sdk = AppSDK(
                name="Project Greenlight",
                version="1.0.0",
                capabilities=self.GREENLIGHT_CAPABILITIES
            )
            connection = await self._sdk.connect(daemon)

            self._connected = True
            self._setup_subscriptions()

            logger.info(f"Greenlight connected to runtime: {connection.app_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to runtime: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the runtime."""
        if self._sdk:
            await self._sdk.disconnect()
            self._connected = False
            logger.info("Greenlight disconnected from runtime")
    
    def _setup_subscriptions(self) -> None:
        """Set up event subscriptions."""
        if not self._sdk:
            return
        
        # Subscribe to runtime events
        @self._sdk.on("runtime.health.degraded")
        async def on_health_degraded(event: "Event"):
            logger.warning(f"Runtime health degraded: {event.data}")
            await self._handle_runtime_event("health_degraded", event)
        
        @self._sdk.on("runtime.app.connected")
        async def on_app_connected(event: "Event"):
            logger.info(f"New app connected: {event.data}")
            await self._handle_runtime_event("app_connected", event)

    async def _handle_runtime_event(self, event_type: str, event: "Event") -> None:
        """Handle runtime events."""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def on_runtime_event(self, event_type: str, handler: Callable) -> None:
        """Register a handler for runtime events."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def set_ui_callback(self, callback_type: str, callback: Callable) -> None:
        """Set a UI callback for pipeline updates."""
        self._ui_callbacks[callback_type] = callback

    async def _emit_pipeline_event(self, topic: str, data: Dict[str, Any]) -> None:
        """Emit a pipeline event to the runtime."""
        if self._sdk:
            await self._sdk.emit(f"greenlight.{topic}", data)

    async def _notify_ui(self, callback_type: str, data: Any) -> None:
        """Notify UI via callback."""
        callback = self._ui_callbacks.get(callback_type)
        if callback:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"UI callback error: {e}")

    # =========================================================================
    # Pipeline Execution with Runtime Integration
    # =========================================================================

    async def run_writer_pipeline(
        self,
        project_path: Path,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[PipelineProgress], None]] = None
    ) -> Dict[str, Any]:
        """
        Run the Writer pipeline with runtime event emission.

        Args:
            project_path: Path to the project
            config: Pipeline configuration
            progress_callback: Optional callback for progress updates

        Returns:
            Pipeline result dictionary
        """
        pipeline_type = PipelineType.WRITER
        progress = PipelineProgress(
            pipeline=pipeline_type,
            status=PipelineStatus.STARTING,
            started_at=datetime.now()
        )
        self._active_pipelines[pipeline_type] = progress

        try:
            # Emit start event
            await self._emit_pipeline_event("pipeline.writer.started", {
                "project": str(project_path),
                "config": config
            })

            progress.status = PipelineStatus.RUNNING
            await self._notify_progress(progress, progress_callback)

            # Import and run the Condensed Visual Pipeline (replaces legacy Writer)
            from greenlight.pipelines.condensed_visual_pipeline import (
                CondensedVisualPipeline, CondensedPipelineInput
            )
            from greenlight.pipelines.base_pipeline import PipelineStatus as PipelineStatusEnum

            pipeline = CondensedVisualPipeline(
                project_path=project_path,
                cache_conversations=True
            )

            # Create input from config
            pipeline_input = CondensedPipelineInput(
                pitch=config.get("prompt", ""),
                title=config.get("title", ""),
                genre=config.get("genre", ""),
                visual_style=config.get("visual_style", "live_action"),
                style_notes=config.get("style_notes", ""),
                project_size=config.get("media_type", "short"),
                project_path=project_path,
                generate_images=False,  # Writer mode doesn't generate images
                image_model="flux_2_pro",
                max_continuity_corrections=2
            )

            # Run with progress tracking
            async def on_phase(phase: str, phase_progress: float):
                progress.current_phase = phase
                progress.progress = phase_progress
                await self._emit_pipeline_event("pipeline.writer.progress", {
                    "phase": phase,
                    "progress": phase_progress
                })
                await self._notify_progress(progress, progress_callback)

            result = await pipeline.run(pipeline_input)

            # Complete
            progress.status = PipelineStatus.COMPLETED
            progress.progress = 1.0
            progress.completed_at = datetime.now()

            output = result.output if result.status == PipelineStatusEnum.COMPLETED else None
            await self._emit_pipeline_event("pipeline.writer.completed", {
                "scenes": len(output.scenes) if output else 0,
                "frames": output.total_frames if output else 0,
                "duration_seconds": (progress.completed_at - progress.started_at).total_seconds()
            })

            await self._notify_progress(progress, progress_callback)

            return {"success": result.status == PipelineStatusEnum.COMPLETED, "result": output}

        except Exception as e:
            progress.status = PipelineStatus.FAILED
            progress.error = str(e)

            await self._emit_pipeline_event("pipeline.writer.failed", {
                "error": str(e)
            })

            await self._notify_progress(progress, progress_callback)

            return {"success": False, "error": str(e)}

    async def run_directing_pipeline(
        self,
        project_path: Path,
        script: str,
        world_config: Dict[str, Any],
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[PipelineProgress], None]] = None
    ) -> Dict[str, Any]:
        """Run the Directing pipeline with runtime event emission (Writer_Flow_v2)."""
        pipeline_type = PipelineType.DIRECTOR
        progress = PipelineProgress(
            pipeline=pipeline_type,
            status=PipelineStatus.STARTING,
            items_total=1,  # Single pipeline run
            started_at=datetime.now()
        )
        self._active_pipelines[pipeline_type] = progress

        try:
            await self._emit_pipeline_event("pipeline.directing.started", {
                "project": str(project_path),
                "script_length": len(script)
            })

            progress.status = PipelineStatus.RUNNING
            await self._notify_progress(progress, progress_callback)

            # Import and run the Condensed Visual Pipeline with image generation
            from greenlight.pipelines.condensed_visual_pipeline import (
                CondensedVisualPipeline, CondensedPipelineInput
            )
            from greenlight.pipelines.base_pipeline import PipelineStatus as PipelineStatusEnum

            pipeline = CondensedVisualPipeline(
                project_path=project_path,
                cache_conversations=True
            )

            # Use script as pitch content for the condensed pipeline
            pipeline_input = CondensedPipelineInput(
                pitch=script,
                title=world_config.get("title", ""),
                genre=world_config.get("genre", ""),
                visual_style=config.get("visual_style", world_config.get("visual_style", "live_action")),
                style_notes=config.get("style_notes", world_config.get("style_notes", "")),
                project_size=config.get("media_type", "short"),
                project_path=project_path,
                generate_images=True,  # Director mode generates images
                image_model="flux_2_pro",
                max_continuity_corrections=2
            )

            progress.current_item = "Running Condensed Visual Pipeline"
            progress.progress = 0.1
            await self._notify_progress(progress, progress_callback)

            # Run the pipeline
            result = await pipeline.run(pipeline_input)

            progress.status = PipelineStatus.COMPLETED
            progress.progress = 1.0
            progress.items_completed = 1
            progress.completed_at = datetime.now()

            output = result.output if result.status == PipelineStatusEnum.COMPLETED else None
            await self._emit_pipeline_event("pipeline.directing.completed", {
                "total_frames": output.total_frames if output else 0,
                "scenes_processed": len(output.scenes) if output else 0,
                "images_generated": output.images_generated if output else 0,
                "duration_seconds": (progress.completed_at - progress.started_at).total_seconds()
            })

            await self._notify_progress(progress, progress_callback)

            return {
                "success": result.status == PipelineStatusEnum.COMPLETED,
                "visual_script": output.visual_script if output else "",
                "total_frames": output.total_frames if output else 0,
                "scenes": len(output.scenes) if output else 0,
                "images_generated": output.images_generated if output else 0
            }

        except Exception as e:
            progress.status = PipelineStatus.FAILED
            progress.error = str(e)

            await self._emit_pipeline_event("pipeline.directing.failed", {"error": str(e)})
            await self._notify_progress(progress, progress_callback)

            return {"success": False, "error": str(e)}

    async def _notify_progress(
        self,
        progress: PipelineProgress,
        callback: Optional[Callable[[PipelineProgress], None]]
    ) -> None:
        """Notify progress to callback and UI."""
        if callback:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(progress)
                else:
                    callback(progress)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

        await self._notify_ui("pipeline_progress", progress)

    def get_active_pipelines(self) -> Dict[PipelineType, PipelineProgress]:
        """Get currently active pipelines."""
        return self._active_pipelines.copy()

    def get_pipeline_status(self, pipeline_type: PipelineType) -> Optional[PipelineProgress]:
        """Get status of a specific pipeline."""
        return self._active_pipelines.get(pipeline_type)


# Global bridge instance
_bridge: Optional[GreenlightRuntimeBridge] = None


def get_runtime_bridge() -> GreenlightRuntimeBridge:
    """Get or create the global runtime bridge."""
    global _bridge
    if _bridge is None:
        _bridge = GreenlightRuntimeBridge()
    return _bridge


async def connect_to_runtime(daemon: "RuntimeDaemon") -> GreenlightRuntimeBridge:
    """Connect Greenlight to the runtime and return the bridge."""
    bridge = get_runtime_bridge()
    await bridge.connect(daemon)
    return bridge

