"""
Agnostic_Core_OS App Registry

Manages registration and tracking of connected applications.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger("agnostic_core_os.runtime.app_registry")


class AppState(Enum):
    """Application connection states."""
    REGISTERED = "registered"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    SUSPENDED = "suspended"


@dataclass
class AppInfo:
    """Information about a registered application."""
    app_id: str
    name: str
    version: str
    state: AppState = AppState.REGISTERED
    registered_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    subscriptions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "version": self.version,
            "state": self.state.value,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "metadata": self.metadata,
            "capabilities": self.capabilities,
            "subscriptions": self.subscriptions,
        }


class AppRegistry:
    """
    Registry for connected applications.
    
    Manages:
    - App registration and deregistration
    - Connection state tracking
    - Heartbeat monitoring
    - Capability discovery
    
    Usage:
        registry = AppRegistry()
        
        # Register an app
        app = registry.register("my_app", "1.0.0", capabilities=["llm", "storage"])
        
        # Update heartbeat
        registry.heartbeat(app.app_id)
        
        # Find apps by capability
        llm_apps = registry.find_by_capability("llm")
    """
    
    def __init__(self, max_apps: int = 100):
        self.max_apps = max_apps
        self._apps: Dict[str, AppInfo] = {}
        self._next_id = 0
        self._on_register_callbacks: List[Callable[[AppInfo], None]] = []
        self._on_disconnect_callbacks: List[Callable[[AppInfo], None]] = []
    
    @property
    def count(self) -> int:
        return len(self._apps)
    
    def _generate_app_id(self, name: str) -> str:
        """Generate unique app ID."""
        self._next_id += 1
        return f"app_{name}_{self._next_id:04d}"
    
    def register(
        self,
        name: str,
        version: str,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AppInfo:
        """
        Register a new application.
        
        Args:
            name: Application name
            version: Application version
            capabilities: List of capabilities the app provides
            metadata: Additional metadata
            
        Returns:
            AppInfo for the registered app
            
        Raises:
            ValueError: If max apps reached or name already registered
        """
        if len(self._apps) >= self.max_apps:
            raise ValueError(f"Maximum apps ({self.max_apps}) reached")
        
        # Check for duplicate name
        for app in self._apps.values():
            if app.name == name and app.state != AppState.DISCONNECTED:
                raise ValueError(f"App '{name}' already registered")
        
        app_id = self._generate_app_id(name)
        app = AppInfo(
            app_id=app_id,
            name=name,
            version=version,
            state=AppState.REGISTERED,
            capabilities=capabilities or [],
            metadata=metadata or {},
        )
        
        self._apps[app_id] = app
        logger.info(f"Registered app: {name} ({app_id})")
        
        # Notify callbacks
        for callback in self._on_register_callbacks:
            callback(app)
        
        return app
    
    def unregister(self, app_id: str) -> bool:
        """Unregister an application."""
        if app_id not in self._apps:
            return False
        
        app = self._apps[app_id]
        app.state = AppState.DISCONNECTED
        
        # Notify callbacks
        for callback in self._on_disconnect_callbacks:
            callback(app)
        
        del self._apps[app_id]
        logger.info(f"Unregistered app: {app.name} ({app_id})")
        return True
    
    def get(self, app_id: str) -> Optional[AppInfo]:
        """Get app by ID."""
        return self._apps.get(app_id)
    
    def get_by_name(self, name: str) -> Optional[AppInfo]:
        """Get app by name."""
        for app in self._apps.values():
            if app.name == name:
                return app
        return None

    def list_all(self) -> List[AppInfo]:
        """List all registered apps."""
        return list(self._apps.values())

    def find_by_capability(self, capability: str) -> List[AppInfo]:
        """Find apps that have a specific capability."""
        return [
            app for app in self._apps.values()
            if capability in app.capabilities and app.state == AppState.CONNECTED
        ]

    def find_by_state(self, state: AppState) -> List[AppInfo]:
        """Find apps in a specific state."""
        return [app for app in self._apps.values() if app.state == state]

    def heartbeat(self, app_id: str) -> bool:
        """Update heartbeat for an app."""
        app = self._apps.get(app_id)
        if not app:
            return False

        app.last_heartbeat = datetime.now()
        if app.state == AppState.REGISTERED:
            app.state = AppState.CONNECTED
        return True

    def connect(self, app_id: str) -> bool:
        """Mark app as connected."""
        app = self._apps.get(app_id)
        if not app:
            return False

        app.state = AppState.CONNECTED
        app.last_heartbeat = datetime.now()
        logger.info(f"App connected: {app.name}")
        return True

    def disconnect(self, app_id: str) -> bool:
        """Mark app as disconnected."""
        app = self._apps.get(app_id)
        if not app:
            return False

        app.state = AppState.DISCONNECTED
        logger.info(f"App disconnected: {app.name}")

        for callback in self._on_disconnect_callbacks:
            callback(app)

        return True

    def subscribe(self, app_id: str, topic: str) -> bool:
        """Subscribe an app to an event topic."""
        app = self._apps.get(app_id)
        if not app:
            return False

        if topic not in app.subscriptions:
            app.subscriptions.append(topic)
        return True

    def unsubscribe(self, app_id: str, topic: str) -> bool:
        """Unsubscribe an app from an event topic."""
        app = self._apps.get(app_id)
        if not app:
            return False

        if topic in app.subscriptions:
            app.subscriptions.remove(topic)
        return True

    def get_subscribers(self, topic: str) -> List[AppInfo]:
        """Get all apps subscribed to a topic."""
        return [
            app for app in self._apps.values()
            if topic in app.subscriptions and app.state == AppState.CONNECTED
        ]

    def on_register(self, callback: Callable[[AppInfo], None]) -> None:
        """Register callback for app registration."""
        self._on_register_callbacks.append(callback)

    def on_disconnect(self, callback: Callable[[AppInfo], None]) -> None:
        """Register callback for app disconnection."""
        self._on_disconnect_callbacks.append(callback)

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        states = {}
        for state in AppState:
            states[state.value] = len(self.find_by_state(state))

        return {
            "total_apps": len(self._apps),
            "max_apps": self.max_apps,
            "states": states,
            "apps": [app.to_dict() for app in self._apps.values()],
        }

