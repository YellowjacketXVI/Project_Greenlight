"""
Agnostic_Core_OS App SDK

Clean interface for applications to connect to the runtime.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable, TYPE_CHECKING
from datetime import datetime
from pathlib import Path
import asyncio
import logging

if TYPE_CHECKING:
    from .daemon import RuntimeDaemon
    from .app_registry import AppInfo
    from .event_bus import Event, EventHandler

logger = logging.getLogger("agnostic_core_os.runtime.sdk")


@dataclass
class AppConnection:
    """Represents a connection to the runtime."""
    app_id: str
    name: str
    version: str
    connected: bool = False
    connected_at: Optional[datetime] = None
    subscriptions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "version": self.version,
            "connected": self.connected,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "subscriptions": self.subscriptions,
        }


class AppSDK:
    """
    SDK for applications to connect to Agnostic_Core_OS runtime.
    
    Provides a clean, simple interface for:
    - Connecting to the runtime
    - Subscribing to events
    - Emitting events
    - Accessing platform services
    
    Usage:
        # In your application
        from Agnostic_Core_OS.runtime import AppSDK
        
        sdk = AppSDK(
            name="MyApp",
            version="1.0.0",
            capabilities=["storage", "llm"]
        )
        
        # Connect to runtime
        await sdk.connect()
        
        # Subscribe to events
        @sdk.on("config.changed")
        async def handle_config(event):
            print(f"Config changed: {event.data}")
        
        # Emit events
        await sdk.emit("myapp.ready", {"status": "initialized"})
        
        # Access services
        result = await sdk.call_service("llm", "generate", prompt="Hello")
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.version = version
        self.capabilities = capabilities or []
        self.metadata = metadata or {}
        
        self._connection: Optional[AppConnection] = None
        self._daemon: Optional["RuntimeDaemon"] = None
        self._handlers: Dict[str, List["EventHandler"]] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_interval = 10.0  # seconds
    
    @property
    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.connected
    
    @property
    def app_id(self) -> Optional[str]:
        return self._connection.app_id if self._connection else None
    
    async def connect(self, daemon: Optional["RuntimeDaemon"] = None) -> AppConnection:
        """
        Connect to the runtime.
        
        Args:
            daemon: Optional daemon instance (uses global if not provided)
            
        Returns:
            AppConnection with connection details
        """
        if self.is_connected:
            logger.warning(f"App {self.name} already connected")
            return self._connection
        
        # Get or create daemon
        if daemon:
            self._daemon = daemon
        else:
            # Try to get global daemon
            from . import get_runtime_daemon
            self._daemon = get_runtime_daemon()
        
        if not self._daemon or not self._daemon.is_running:
            raise RuntimeError("Runtime daemon not available")
        
        # Register with app registry
        app_info = self._daemon.app_registry.register(
            name=self.name,
            version=self.version,
            capabilities=self.capabilities,
            metadata=self.metadata,
        )
        
        # Connect
        self._daemon.app_registry.connect(app_info.app_id)
        
        # Create connection
        self._connection = AppConnection(
            app_id=app_info.app_id,
            name=self.name,
            version=self.version,
            connected=True,
            connected_at=datetime.now(),
        )
        
        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # Register stored handlers
        for topic, handlers in self._handlers.items():
            for handler in handlers:
                self._daemon.event_bus.subscribe(
                    topic=topic,
                    handler=handler,
                    app_id=app_info.app_id,
                )
                self._connection.subscriptions.append(topic)
        
        logger.info(f"App connected: {self.name} ({app_info.app_id})")
        return self._connection
    
    async def disconnect(self) -> bool:
        """Disconnect from the runtime."""
        if not self.is_connected:
            return True
        
        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe from events
        if self._daemon and self._daemon.event_bus:
            self._daemon.event_bus.unsubscribe_app(self._connection.app_id)

        # Disconnect from registry
        if self._daemon and self._daemon.app_registry:
            self._daemon.app_registry.disconnect(self._connection.app_id)

        self._connection.connected = False
        logger.info(f"App disconnected: {self.name}")
        return True

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while self.is_connected:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                if self._daemon and self._daemon.app_registry:
                    self._daemon.app_registry.heartbeat(self._connection.app_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def on(self, topic: str) -> Callable:
        """
        Decorator to subscribe to an event topic.

        Usage:
            @sdk.on("config.changed")
            async def handle_config(event):
                print(event.data)
        """
        def decorator(handler: "EventHandler") -> "EventHandler":
            if topic not in self._handlers:
                self._handlers[topic] = []
            self._handlers[topic].append(handler)

            # If already connected, subscribe immediately
            if self.is_connected and self._daemon:
                self._daemon.event_bus.subscribe(
                    topic=topic,
                    handler=handler,
                    app_id=self._connection.app_id,
                )
                self._connection.subscriptions.append(topic)

            return handler
        return decorator

    async def subscribe(self, topic: str, handler: "EventHandler") -> str:
        """Subscribe to an event topic."""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

        if self.is_connected and self._daemon:
            sub_id = self._daemon.event_bus.subscribe(
                topic=topic,
                handler=handler,
                app_id=self._connection.app_id,
            )
            self._connection.subscriptions.append(topic)
            return sub_id

        return f"pending_{topic}"

    async def emit(
        self,
        topic: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Emit an event to a topic."""
        if not self.is_connected:
            raise RuntimeError("Not connected to runtime")

        return await self._daemon.event_bus.emit(
            topic=topic,
            data=data,
            source_app=self._connection.app_id,
            metadata=metadata,
        )

    async def request(
        self,
        topic: str,
        data: Any,
        timeout: float = 30.0,
    ) -> Any:
        """Send a request and wait for response."""
        if not self.is_connected:
            raise RuntimeError("Not connected to runtime")

        response_topic = f"{topic}.response.{self._connection.app_id}"
        response_future: asyncio.Future = asyncio.Future()

        async def response_handler(event: "Event") -> None:
            if not response_future.done():
                response_future.set_result(event.data)

        # Subscribe to response
        sub_id = self._daemon.event_bus.subscribe(
            topic=response_topic,
            handler=response_handler,
            app_id=self._connection.app_id,
        )

        try:
            # Emit request
            await self._daemon.event_bus.emit(
                topic=topic,
                data={"request": data, "response_topic": response_topic},
                source_app=self._connection.app_id,
            )

            # Wait for response
            return await asyncio.wait_for(response_future, timeout=timeout)

        finally:
            self._daemon.event_bus.unsubscribe(sub_id)

    def get_status(self) -> Dict[str, Any]:
        """Get SDK connection status."""
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities,
            "connection": self._connection.to_dict() if self._connection else None,
            "handlers": list(self._handlers.keys()),
        }


# Global daemon instance
_global_daemon: Optional["RuntimeDaemon"] = None


def get_runtime_daemon() -> Optional["RuntimeDaemon"]:
    """Get the global runtime daemon instance."""
    return _global_daemon


def set_runtime_daemon(daemon: "RuntimeDaemon") -> None:
    """Set the global runtime daemon instance."""
    global _global_daemon
    _global_daemon = daemon

