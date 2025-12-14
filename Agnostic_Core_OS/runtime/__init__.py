"""
Agnostic_Core_OS Runtime Module

Vector-Native Runtime Environment providing:
- RuntimeDaemon: Background service managing persistent state
- AppRegistry: Track and manage connected applications
- EventBus: Inter-app communication via pub/sub
- AppSDK: Clean interface for apps to connect
- HealthMonitor: Runtime health tracking and self-healing
"""

from .daemon import RuntimeDaemon, DaemonState, DaemonConfig
from .app_registry import AppRegistry, AppInfo, AppState
from .event_bus import EventBus, Event, EventHandler, EventPriority
from .sdk import AppSDK, AppConnection, get_runtime_daemon, set_runtime_daemon
from .health_monitor import HealthMonitor, RuntimeHealth, HealthStatus, HealthIssue

__all__ = [
    # Daemon
    "RuntimeDaemon",
    "DaemonState",
    "DaemonConfig",
    # App Registry
    "AppRegistry",
    "AppInfo",
    "AppState",
    # Event Bus
    "EventBus",
    "Event",
    "EventHandler",
    "EventPriority",
    # SDK
    "AppSDK",
    "AppConnection",
    "get_runtime_daemon",
    "set_runtime_daemon",
    # Health
    "HealthMonitor",
    "RuntimeHealth",
    "HealthStatus",
    "HealthIssue",
]

