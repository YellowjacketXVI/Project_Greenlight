"""
Greenlight UI Module

CustomTkinter-based desktop UI for Project Greenlight.

Features:
- 4-pane layout (navigator, workspace, assistant, pipeline panel)
- User Journey walkthrough with input hooks
- Pipeline execution panel with event log
- Notification system with sounds
- Omni Mind integration
- Project management
- Real-time updates
"""

from greenlight.ui.main_window import Viewport
from greenlight.ui.theme import theme, GreenlightTheme


def run_app():
    """
    Launch the Greenlight desktop UI.

    Creates and runs the main Viewport window.
    """
    app = Viewport()
    app.mainloop()


__all__ = [
    'run_app',
    'Viewport',
    'theme',
    'GreenlightTheme',
]

