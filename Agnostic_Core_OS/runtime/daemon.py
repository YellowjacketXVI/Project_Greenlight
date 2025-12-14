"""
Agnostic_Core_OS Runtime Daemon

Background service that manages the runtime environment state.
Provides persistent state management, service lifecycle, and coordination.

The RuntimeDaemon operates OmniMind as its context library, providing
memory, context retrieval, decision making, and self-healing capabilities
to all connected applications.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable, TYPE_CHECKING
from datetime import datetime
from pathlib import Path
from enum import Enum
import asyncio
import json
import logging

if TYPE_CHECKING:
    from .app_registry import AppRegistry
    from .event_bus import EventBus
    from .health_monitor import HealthMonitor
    from ..omni_mind import OmniMind

logger = logging.getLogger("agnostic_core_os.runtime.daemon")


class DaemonState(Enum):
    """Runtime daemon states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class DaemonConfig:
    """Configuration for the runtime daemon."""
    state_dir: Path = field(default_factory=lambda: Path(".agnostic_runtime"))
    auto_heal: bool = True
    health_check_interval: float = 30.0  # seconds
    max_apps: int = 100
    event_queue_size: int = 1000
    persist_state: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_dir": str(self.state_dir),
            "auto_heal": self.auto_heal,
            "health_check_interval": self.health_check_interval,
            "max_apps": self.max_apps,
            "event_queue_size": self.event_queue_size,
            "persist_state": self.persist_state,
        }


@dataclass
class RuntimeState:
    """Persistent runtime state."""
    daemon_id: str
    started_at: datetime
    state: DaemonState
    apps_registered: int = 0
    events_processed: int = 0
    errors_count: int = 0
    last_health_check: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "daemon_id": self.daemon_id,
            "started_at": self.started_at.isoformat(),
            "state": self.state.value,
            "apps_registered": self.apps_registered,
            "events_processed": self.events_processed,
            "errors_count": self.errors_count,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
        }


class RuntimeDaemon:
    """
    Agnostic_Core_OS Runtime Daemon.

    Central background service that:
    - Manages runtime lifecycle
    - Coordinates app registry and event bus
    - Runs health checks and self-healing
    - Persists state across restarts
    - Operates OmniMind as the context library

    Usage:
        daemon = RuntimeDaemon(config=DaemonConfig())
        await daemon.start()

        # Register apps, emit events, etc.
        # Access OmniMind via daemon.omni_mind

        await daemon.stop()
    """

    def __init__(self, config: Optional[DaemonConfig] = None):
        self.config = config or DaemonConfig()
        self._state = DaemonState.STOPPED
        self._runtime_state: Optional[RuntimeState] = None

        # Components (lazy initialized)
        self._app_registry: Optional[AppRegistry] = None
        self._event_bus: Optional[EventBus] = None
        self._health_monitor: Optional[HealthMonitor] = None
        self._omni_mind: Optional[OmniMind] = None

        # Background tasks
        self._health_task: Optional[asyncio.Task] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        # Callbacks
        self._on_start_callbacks: List[Callable[[], Awaitable[None]]] = []
        self._on_stop_callbacks: List[Callable[[], Awaitable[None]]] = []

        # Ensure state directory
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def state(self) -> DaemonState:
        return self._state
    
    @property
    def is_running(self) -> bool:
        return self._state == DaemonState.RUNNING
    
    @property
    def app_registry(self) -> Optional["AppRegistry"]:
        return self._app_registry
    
    @property
    def event_bus(self) -> Optional["EventBus"]:
        return self._event_bus
    
    @property
    def health_monitor(self) -> Optional["HealthMonitor"]:
        return self._health_monitor

    @property
    def omni_mind(self) -> Optional["OmniMind"]:
        """Get the OmniMind context library."""
        return self._omni_mind

    @property
    def daemon_id(self) -> Optional[str]:
        """Get the daemon ID."""
        return self._runtime_state.daemon_id if self._runtime_state else None

    @property
    def runtime_state(self) -> Optional[RuntimeState]:
        """Get the current runtime state."""
        return self._runtime_state

    def _generate_daemon_id(self) -> str:
        """Generate unique daemon ID."""
        return f"daemon_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    async def start(self) -> bool:
        """Start the runtime daemon."""
        if self._state == DaemonState.RUNNING:
            logger.warning("Daemon already running")
            return True
        
        try:
            self._state = DaemonState.STARTING
            logger.info("Starting Agnostic_Core_OS Runtime Daemon...")
            
            # Initialize components
            from .app_registry import AppRegistry
            from .event_bus import EventBus
            from .health_monitor import HealthMonitor
            from ..omni_mind import OmniMind, OmniMindConfig, OmniMindMode

            self._app_registry = AppRegistry(max_apps=self.config.max_apps)
            self._event_bus = EventBus(queue_size=self.config.event_queue_size)
            self._health_monitor = HealthMonitor(daemon=self)

            # Initialize OmniMind as the context library
            omni_config = OmniMindConfig(
                mode=OmniMindMode.PROACTIVE,
                project_path=self.config.state_dir.parent,
                auto_heal=self.config.auto_heal
            )
            self._omni_mind = OmniMind(config=omni_config)
            logger.info("OmniMind context library initialized")

            # Create runtime state
            self._runtime_state = RuntimeState(
                daemon_id=self._generate_daemon_id(),
                started_at=datetime.now(),
                state=DaemonState.RUNNING,
            )

            # Start health check loop
            if self.config.auto_heal:
                self._health_task = asyncio.create_task(self._health_check_loop())

            # Run start callbacks
            for callback in self._on_start_callbacks:
                await callback()

            self._state = DaemonState.RUNNING
            logger.info(f"Runtime Daemon started: {self._runtime_state.daemon_id}")

            # Persist state
            if self.config.persist_state:
                self._save_state()

            return True

        except Exception as e:
            self._state = DaemonState.ERROR
            logger.error(f"Failed to start daemon: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the runtime daemon."""
        if self._state == DaemonState.STOPPED:
            logger.warning("Daemon already stopped")
            return True

        try:
            self._state = DaemonState.STOPPING
            logger.info("Stopping Agnostic_Core_OS Runtime Daemon...")

            # Cancel health check
            if self._health_task:
                self._health_task.cancel()
                try:
                    await self._health_task
                except asyncio.CancelledError:
                    pass

            # Run stop callbacks
            for callback in self._on_stop_callbacks:
                await callback()

            # Persist final state
            if self.config.persist_state and self._runtime_state:
                self._runtime_state.state = DaemonState.STOPPED
                self._save_state()

            self._state = DaemonState.STOPPED
            logger.info("Runtime Daemon stopped")
            return True

        except Exception as e:
            self._state = DaemonState.ERROR
            logger.error(f"Error stopping daemon: {e}")
            return False

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._state == DaemonState.RUNNING:
            try:
                await asyncio.sleep(self.config.health_check_interval)

                if self._health_monitor and self._runtime_state:
                    health = await self._health_monitor.check()
                    self._runtime_state.last_health_check = datetime.now()

                    if not health.is_healthy and self.config.auto_heal:
                        await self._health_monitor.heal()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                if self._runtime_state:
                    self._runtime_state.errors_count += 1

    def _save_state(self) -> None:
        """Persist runtime state to disk."""
        if not self._runtime_state:
            return

        state_file = self.config.state_dir / "runtime_state.json"
        with open(state_file, 'w') as f:
            json.dump(self._runtime_state.to_dict(), f, indent=2)

    def _load_state(self) -> Optional[RuntimeState]:
        """Load runtime state from disk."""
        state_file = self.config.state_dir / "runtime_state.json"
        if not state_file.exists():
            return None

        try:
            with open(state_file, 'r') as f:
                data = json.load(f)
            return RuntimeState(
                daemon_id=data["daemon_id"],
                started_at=datetime.fromisoformat(data["started_at"]),
                state=DaemonState(data["state"]),
                apps_registered=data.get("apps_registered", 0),
                events_processed=data.get("events_processed", 0),
                errors_count=data.get("errors_count", 0),
            )
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return None

    def on_start(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register a callback to run on daemon start."""
        self._on_start_callbacks.append(callback)

    def on_stop(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register a callback to run on daemon stop."""
        self._on_stop_callbacks.append(callback)

    def get_status(self) -> Dict[str, Any]:
        """Get current daemon status."""
        return {
            "state": self._state.value,
            "runtime": self._runtime_state.to_dict() if self._runtime_state else None,
            "config": self.config.to_dict(),
            "apps": self._app_registry.count if self._app_registry else 0,
            "events_pending": self._event_bus.pending_count if self._event_bus else 0,
            "omni_mind": self._omni_mind.diagnose() if self._omni_mind else None,
        }

    # =========================================================================
    # OMNI_MIND CONTEXT OPERATIONS
    # =========================================================================

    def remember(self, content: str, **kwargs) -> Any:
        """Add something to OmniMind memory."""
        if self._omni_mind:
            return self._omni_mind.remember(content, **kwargs)
        return None

    def recall(self, query: str, limit: int = 10) -> List[Any]:
        """Search OmniMind memory."""
        if self._omni_mind:
            return self._omni_mind.recall(query, limit)
        return []

    def retrieve_context(self, query_text: str, **kwargs) -> Any:
        """Retrieve context from OmniMind."""
        if self._omni_mind:
            from ..omni_mind import ContextQuery
            query = ContextQuery(query_text=query_text, **kwargs)
            return self._omni_mind.retrieve(query)
        return None

    def index_content(self, content: str, **kwargs) -> Optional[str]:
        """Index content in OmniMind for retrieval."""
        if self._omni_mind:
            return self._omni_mind.index(content, **kwargs)
        return None

