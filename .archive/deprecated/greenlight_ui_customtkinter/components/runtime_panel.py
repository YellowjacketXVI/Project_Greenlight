"""
Runtime Status Panel

Displays Agnostic_Core_OS runtime connection status and controls.
"""

import customtkinter as ctk
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import asyncio
import threading

from greenlight.ui.theme import theme


class RuntimeStatusPanel(ctk.CTkFrame):
    """
    Panel showing Agnostic_Core_OS runtime status.
    
    Features:
    - Connection status indicator
    - Runtime health display
    - Connected apps list
    - Event activity monitor
    """
    
    def __init__(
        self,
        master,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color=theme.colors.bg_dark, **kwargs)
        
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self._connected = False
        self._runtime_info: Dict[str, Any] = {}
        self._event_count = 0
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))
        
        title = ctk.CTkLabel(
            header,
            text="⚡ Runtime",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(side="left")
        
        # Status indicator
        self.status_indicator = ctk.CTkLabel(
            header,
            text="●",
            font=ctk.CTkFont(size=12),
            text_color=theme.colors.text_muted
        )
        self.status_indicator.pack(side="right")
        
        # Connection status
        self.status_label = ctk.CTkLabel(
            self,
            text="Disconnected",
            font=ctk.CTkFont(size=11),
            text_color=theme.colors.text_muted
        )
        self.status_label.pack(fill="x", padx=8, pady=2)
        
        # Connect/Disconnect button
        self.connect_btn = ctk.CTkButton(
            self,
            text="Connect to Runtime",
            command=self._on_connect_click,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color=theme.colors.accent,
            hover_color=theme.colors.accent_hover
        )
        self.connect_btn.pack(fill="x", padx=8, pady=4)
        
        # Runtime info frame (hidden when disconnected)
        self.info_frame = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium)
        
        # Health status
        health_row = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        health_row.pack(fill="x", padx=8, pady=4)
        
        ctk.CTkLabel(
            health_row,
            text="Health:",
            font=ctk.CTkFont(size=10),
            text_color=theme.colors.text_muted
        ).pack(side="left")
        
        self.health_label = ctk.CTkLabel(
            health_row,
            text="--",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=theme.colors.success
        )
        self.health_label.pack(side="right")
        
        # Apps connected
        apps_row = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        apps_row.pack(fill="x", padx=8, pady=2)
        
        ctk.CTkLabel(
            apps_row,
            text="Apps:",
            font=ctk.CTkFont(size=10),
            text_color=theme.colors.text_muted
        ).pack(side="left")
        
        self.apps_label = ctk.CTkLabel(
            apps_row,
            text="0",
            font=ctk.CTkFont(size=10),
            text_color=theme.colors.text_primary
        )
        self.apps_label.pack(side="right")
        
        # Events processed
        events_row = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        events_row.pack(fill="x", padx=8, pady=2)
        
        ctk.CTkLabel(
            events_row,
            text="Events:",
            font=ctk.CTkFont(size=10),
            text_color=theme.colors.text_muted
        ).pack(side="left")
        
        self.events_label = ctk.CTkLabel(
            events_row,
            text="0",
            font=ctk.CTkFont(size=10),
            text_color=theme.colors.text_primary
        )
        self.events_label.pack(side="right")
        
        # Daemon ID
        daemon_row = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        daemon_row.pack(fill="x", padx=8, pady=(2, 8))
        
        ctk.CTkLabel(
            daemon_row,
            text="Daemon:",
            font=ctk.CTkFont(size=10),
            text_color=theme.colors.text_muted
        ).pack(side="left")
        
        self.daemon_label = ctk.CTkLabel(
            daemon_row,
            text="--",
            font=ctk.CTkFont(size=9),
            text_color=theme.colors.text_muted
        )
        self.daemon_label.pack(side="right")

    def _on_connect_click(self) -> None:
        """Handle connect/disconnect button click."""
        if self._connected:
            if self.on_disconnect:
                self.on_disconnect()
        else:
            if self.on_connect:
                self.on_connect()

    def set_connected(self, connected: bool, info: Dict[str, Any] = None) -> None:
        """Update connection status."""
        self._connected = connected
        self._runtime_info = info or {}

        if connected:
            self.status_indicator.configure(text_color=theme.colors.success)
            self.status_label.configure(
                text="Connected to Agnostic_Core_OS",
                text_color=theme.colors.success
            )
            self.connect_btn.configure(
                text="Disconnect",
                fg_color=theme.colors.error,
                hover_color="#c0392b"
            )
            self.info_frame.pack(fill="x", padx=4, pady=4)

            # Update info
            self.health_label.configure(text=info.get("health", "HEALTHY"))
            self.apps_label.configure(text=str(info.get("apps", 1)))
            self.daemon_label.configure(text=info.get("daemon_id", "--")[:12] + "...")
        else:
            self.status_indicator.configure(text_color=theme.colors.text_muted)
            self.status_label.configure(
                text="Disconnected",
                text_color=theme.colors.text_muted
            )
            self.connect_btn.configure(
                text="Connect to Runtime",
                fg_color=theme.colors.accent,
                hover_color=theme.colors.accent_hover
            )
            self.info_frame.pack_forget()

    def update_stats(self, apps: int = None, events: int = None, health: str = None) -> None:
        """Update runtime statistics."""
        if apps is not None:
            self.apps_label.configure(text=str(apps))
        if events is not None:
            self._event_count = events
            self.events_label.configure(text=str(events))
        if health is not None:
            color = theme.colors.success if health == "HEALTHY" else theme.colors.warning
            self.health_label.configure(text=health, text_color=color)

    def increment_events(self) -> None:
        """Increment event counter."""
        self._event_count += 1
        self.events_label.configure(text=str(self._event_count))


class RuntimeEventLog(ctk.CTkFrame):
    """
    Scrollable log of runtime events.

    Shows real-time events from the Agnostic_Core_OS event bus.
    """

    def __init__(self, master, max_events: int = 50, **kwargs):
        super().__init__(master, fg_color=theme.colors.bg_medium, **kwargs)

        self._max_events = max_events
        self._events = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the event log UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(
            header,
            text="📡 Event Log",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.colors.text_primary
        ).pack(side="left")

        # Clear button
        ctk.CTkButton(
            header,
            text="Clear",
            command=self.clear,
            width=50,
            height=20,
            font=ctk.CTkFont(size=10),
            fg_color=theme.colors.bg_dark
        ).pack(side="right")

        # Scrollable event list
        self.event_list = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            height=150
        )
        self.event_list.pack(fill="both", expand=True, padx=4, pady=4)

    def add_event(self, topic: str, source: str = None, data: Any = None) -> None:
        """Add an event to the log."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Create event row
        event_frame = ctk.CTkFrame(self.event_list, fg_color=theme.colors.bg_dark, height=24)
        event_frame.pack(fill="x", pady=1)
        event_frame.pack_propagate(False)

        # Timestamp
        ctk.CTkLabel(
            event_frame,
            text=timestamp,
            font=ctk.CTkFont(size=9),
            text_color=theme.colors.text_muted,
            width=50
        ).pack(side="left", padx=4)

        # Topic with color coding
        topic_color = self._get_topic_color(topic)
        ctk.CTkLabel(
            event_frame,
            text=topic,
            font=ctk.CTkFont(size=9),
            text_color=topic_color
        ).pack(side="left", padx=4)

        self._events.append(event_frame)

        # Limit events
        while len(self._events) > self._max_events:
            old_event = self._events.pop(0)
            old_event.destroy()

    def _get_topic_color(self, topic: str) -> str:
        """Get color for topic based on type."""
        if "error" in topic.lower() or "failed" in topic.lower():
            return theme.colors.error
        elif "completed" in topic.lower() or "success" in topic.lower():
            return theme.colors.success
        elif "progress" in topic.lower():
            return theme.colors.accent
        elif "started" in topic.lower():
            return theme.colors.warning
        return theme.colors.text_primary

    def clear(self) -> None:
        """Clear all events."""
        for event in self._events:
            event.destroy()
        self._events.clear()

