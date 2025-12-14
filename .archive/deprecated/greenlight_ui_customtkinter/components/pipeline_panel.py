"""
Pipeline Execution Panel

Small panel showing real-time event log and phase progress.
Displays pipeline execution status with scrolling event log.
"""

import customtkinter as ctk
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from greenlight.ui.theme import theme


class EventType(Enum):
    """Types of pipeline events."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    USER_INPUT = "user_input"
    PHASE_START = "phase_start"
    PHASE_END = "phase_end"
    FILE_CREATED = "file_created"
    IMAGE_GENERATING = "image_generating"
    IMAGE_COMPLETE = "image_complete"
    IMAGE_ERROR = "image_error"


@dataclass
class PipelineEvent:
    """A pipeline event."""
    event_type: EventType
    message: str
    timestamp: datetime
    phase: Optional[str] = None
    file_path: Optional[str] = None
    details: Optional[Dict] = None


class PipelineExecutionPanel(ctk.CTkFrame):
    """
    Pipeline execution panel with event log.
    
    Features:
    - Real-time event log
    - Phase progress indicator
    - File creation notifications
    - Collapsible design
    """
    
    def __init__(
        self,
        master,
        on_file_click: Callable[[str], None] = None,
        on_cancel: Callable[[], None] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_file_click = on_file_click
        self.on_cancel = on_cancel
        self._events: List[PipelineEvent] = []
        self._current_phase: Optional[str] = None
        self._is_running = False
        self._expanded = True

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.configure(
            fg_color=theme.colors.bg_dark,
            corner_radius=8,
            width=280
        )

        # Header
        header = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium, height=35)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Status indicator
        self.status_dot = ctk.CTkLabel(
            header,
            text="●",
            text_color=theme.colors.text_muted,
            font=(theme.fonts.family, 10)
        )
        self.status_dot.pack(side="left", padx=(theme.spacing.sm, 2))

        title = ctk.CTkLabel(
            header,
            text="Pipeline",
            font=(theme.fonts.family, theme.fonts.size_normal, "bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(side="left", padx=2)

        # Cancel button (hidden by default, shown when running)
        self.cancel_btn = ctk.CTkButton(
            header,
            text="✕ Cancel",
            width=70,
            height=24,
            font=(theme.fonts.family, 10),
            fg_color=theme.colors.error,
            hover_color="#cc3333",
            command=self._on_cancel_click
        )
        # Don't pack initially - will be shown when pipeline starts

        # Toggle button
        self.toggle_btn = ctk.CTkButton(
            header,
            text="▼" if self._expanded else "▲",
            width=25,
            height=25,
            fg_color="transparent",
            hover_color=theme.colors.bg_hover,
            command=self._toggle_expand
        )
        self.toggle_btn.pack(side="right", padx=theme.spacing.xs)
        
        # Clear button
        clear_btn = ctk.CTkButton(
            header,
            text="🗑️",
            width=25,
            height=25,
            fg_color="transparent",
            hover_color=theme.colors.bg_hover,
            command=self.clear_events
        )
        clear_btn.pack(side="right")
        
        # Phase indicator
        self.phase_frame = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium, height=30)
        self.phase_frame.pack(fill="x", pady=(1, 0))
        self.phase_frame.pack_propagate(False)
        
        self.phase_label = ctk.CTkLabel(
            self.phase_frame,
            text="Idle",
            text_color=theme.colors.text_secondary,
            font=(theme.fonts.family, theme.fonts.size_small)
        )
        self.phase_label.pack(side="left", padx=theme.spacing.sm)
        
        self.progress_bar = ctk.CTkProgressBar(
            self.phase_frame,
            width=100,
            height=6,
            progress_color=theme.colors.primary
        )
        self.progress_bar.pack(side="right", padx=theme.spacing.sm)
        self.progress_bar.set(0)
        
        # Event log (scrollable) - height doubled (200 -> 400)
        self.log_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            height=400
        )
        self.log_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Add initial message
        self._add_event_widget(PipelineEvent(
            event_type=EventType.INFO,
            message="Pipeline ready",
            timestamp=datetime.now()
        ))

    def _toggle_expand(self) -> None:
        """Toggle panel expansion."""
        self._expanded = not self._expanded
        if self._expanded:
            self.log_frame.pack(fill="both", expand=True, padx=2, pady=2)
            self.toggle_btn.configure(text="▼")
        else:
            self.log_frame.pack_forget()
            self.toggle_btn.configure(text="▲")

    def _on_cancel_click(self) -> None:
        """Handle cancel button click."""
        if self.on_cancel:
            self.on_cancel()
        self.log_warning("Cancel requested by user")

    def set_running(self, running: bool) -> None:
        """Set the running state and show/hide cancel button."""
        self._is_running = running
        if running:
            self.status_dot.configure(text_color=theme.colors.processing)
            self.cancel_btn.pack(side="right", padx=theme.spacing.xs)
        else:
            self.status_dot.configure(text_color=theme.colors.text_muted)
            self.cancel_btn.pack_forget()

    def _get_event_color(self, event_type: EventType) -> str:
        """Get color for event type."""
        colors = {
            EventType.INFO: theme.colors.text_muted,
            EventType.SUCCESS: theme.colors.success,
            EventType.WARNING: theme.colors.warning,
            EventType.ERROR: theme.colors.error,
            EventType.USER_INPUT: theme.colors.primary,
            EventType.PHASE_START: theme.colors.info,
            EventType.PHASE_END: theme.colors.success,
            EventType.FILE_CREATED: theme.colors.accent,
            EventType.IMAGE_GENERATING: theme.colors.processing,
            EventType.IMAGE_COMPLETE: theme.colors.success,
            EventType.IMAGE_ERROR: theme.colors.error,
        }
        return colors.get(event_type, theme.colors.text_muted)

    def _get_event_icon(self, event_type: EventType) -> str:
        """Get icon for event type."""
        icons = {
            EventType.INFO: "ℹ️",
            EventType.SUCCESS: "✅",
            EventType.WARNING: "⚠️",
            EventType.ERROR: "❌",
            EventType.USER_INPUT: "👤",
            EventType.PHASE_START: "▶️",
            EventType.PHASE_END: "⏹️",
            EventType.FILE_CREATED: "📄",
            EventType.IMAGE_GENERATING: "🎨",
            EventType.IMAGE_COMPLETE: "🖼️",
            EventType.IMAGE_ERROR: "🚫",
        }
        return icons.get(event_type, "•")

    def _add_event_widget(self, event: PipelineEvent) -> None:
        """Add an event widget to the log."""
        frame = ctk.CTkFrame(self.log_frame, fg_color="transparent")
        frame.pack(fill="x", pady=1)

        # Time
        time_str = event.timestamp.strftime("%H:%M:%S")
        time_label = ctk.CTkLabel(
            frame,
            text=time_str,
            text_color=theme.colors.text_muted,
            font=(theme.fonts.family, 9),
            width=55
        )
        time_label.pack(side="left")

        # Icon
        icon_label = ctk.CTkLabel(
            frame,
            text=self._get_event_icon(event.event_type),
            font=(theme.fonts.family, 10),
            width=20
        )
        icon_label.pack(side="left")

        # Message (clickable if file)
        if event.file_path:
            msg_btn = ctk.CTkButton(
                frame,
                text=event.message,
                fg_color="transparent",
                hover_color=theme.colors.bg_hover,
                text_color=self._get_event_color(event.event_type),
                font=(theme.fonts.family, theme.fonts.size_small),
                anchor="w",
                command=lambda p=event.file_path: self._on_file_click(p)
            )
            msg_btn.pack(side="left", fill="x", expand=True)
        else:
            msg_label = ctk.CTkLabel(
                frame,
                text=event.message,
                text_color=self._get_event_color(event.event_type),
                font=(theme.fonts.family, theme.fonts.size_small),
                anchor="w"
            )
            msg_label.pack(side="left", fill="x", expand=True)

    def add_event(
        self,
        event_type: EventType,
        message: str,
        phase: str = None,
        file_path: str = None,
        details: Dict = None
    ) -> None:
        """Add an event to the log."""
        event = PipelineEvent(
            event_type=event_type,
            message=message,
            timestamp=datetime.now(),
            phase=phase,
            file_path=file_path,
            details=details
        )
        self._events.append(event)
        self._add_event_widget(event)

        # Auto-scroll to bottom
        self.log_frame._parent_canvas.yview_moveto(1.0)

    def log_info(self, message: str) -> None:
        """Log an info event."""
        self.add_event(EventType.INFO, message)

    def log_success(self, message: str) -> None:
        """Log a success event."""
        self.add_event(EventType.SUCCESS, message)

    def log_warning(self, message: str) -> None:
        """Log a warning event."""
        self.add_event(EventType.WARNING, message)

    def log_error(self, message: str) -> None:
        """Log an error event."""
        self.add_event(EventType.ERROR, message)

    def log_file_created(self, file_path: str, message: str = None) -> None:
        """Log a file creation event."""
        from pathlib import Path
        name = Path(file_path).name
        msg = message or f"Created: {name}"
        self.add_event(EventType.FILE_CREATED, msg, file_path=file_path)

    def log_user_input(self, message: str) -> None:
        """Log user input event."""
        self.add_event(EventType.USER_INPUT, f"Input: {message[:50]}...")

    def log_image_generating(self, tag: str, model: str = None, index: int = None, total: int = None) -> None:
        """Log image generation start event."""
        msg = f"Generating: {tag}"
        if index is not None and total is not None:
            msg = f"[{index}/{total}] {msg}"
        if model:
            msg += f" ({model})"
        self.add_event(EventType.IMAGE_GENERATING, msg)
        self.status_dot.configure(text_color=theme.colors.processing)

    def log_image_complete(self, tag: str, file_path: str = None, index: int = None, total: int = None) -> None:
        """Log image generation complete event."""
        msg = f"Generated: {tag}"
        if index is not None and total is not None:
            msg = f"[{index}/{total}] {msg}"
            # Update progress
            self.set_progress(index / total)
        self.add_event(EventType.IMAGE_COMPLETE, msg, file_path=file_path)

    def log_image_error(self, tag: str, error: str, index: int = None, total: int = None) -> None:
        """Log image generation error event."""
        msg = f"Failed: {tag}"
        if index is not None and total is not None:
            msg = f"[{index}/{total}] {msg}"
        msg += f" - {error[:50]}"
        self.add_event(EventType.IMAGE_ERROR, msg)

    def start_phase(self, phase_name: str) -> None:
        """Start a new phase."""
        self._current_phase = phase_name
        self._is_running = True
        self.phase_label.configure(text=phase_name)
        self.status_dot.configure(text_color=theme.colors.processing)
        self.add_event(EventType.PHASE_START, f"Starting: {phase_name}", phase=phase_name)

    def end_phase(self, phase_name: str, success: bool = True) -> None:
        """End a phase."""
        status = "Complete" if success else "Failed"
        color = theme.colors.success if success else theme.colors.error
        self.add_event(
            EventType.PHASE_END if success else EventType.ERROR,
            f"{phase_name}: {status}",
            phase=phase_name
        )
        self.status_dot.configure(text_color=color)

    def set_progress(self, progress: float) -> None:
        """Set progress bar value (0.0 to 1.0)."""
        self.progress_bar.set(progress)

    def set_idle(self) -> None:
        """Set to idle state."""
        self._is_running = False
        self._current_phase = None
        self.phase_label.configure(text="Idle")
        self.status_dot.configure(text_color=theme.colors.text_muted)
        self.progress_bar.set(0)

    def clear_events(self) -> None:
        """Clear all events."""
        for widget in self.log_frame.winfo_children():
            widget.destroy()
        self._events.clear()
        self.log_info("Log cleared")

    def _on_file_click(self, file_path: str) -> None:
        """Handle file click."""
        if self.on_file_click:
            self.on_file_click(file_path)

    def get_events(self) -> List[PipelineEvent]:
        """Get all events."""
        return self._events.copy()

