"""
Greenlight UI Module

CustomTkinter-based user interface with 4-pane Viewport layout and Omni Mind integration.
"""

from .main_window import Viewport, GreenlightApp, run_app
from .theme import theme, GreenlightTheme
from .components import (
    ProjectNavigator,
    MainWorkspace,
    AssistantPanel,
    StatusBar,
    UserJourneyPanel,
    JourneyPhase,
    PipelineExecutionPanel,
    EventType,
    NotificationManager,
    NotificationType,
)

__all__ = [
    # Main window
    'Viewport',
    'GreenlightApp',  # Alias for backward compatibility
    'run_app',
    # Theme
    'theme',
    'GreenlightTheme',
    # Core components
    'ProjectNavigator',
    'MainWorkspace',
    'AssistantPanel',
    'StatusBar',
    # User Journey
    'UserJourneyPanel',
    'JourneyPhase',
    # Pipeline
    'PipelineExecutionPanel',
    'EventType',
    # Notifications
    'NotificationManager',
    'NotificationType',
]

