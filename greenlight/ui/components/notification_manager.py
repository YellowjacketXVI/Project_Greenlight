"""
Notification Manager

Sound notifications and visual flags for user input requests and new file development.
Provides clickable navigation notifications directing to files.
"""

import customtkinter as ctk
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import threading
import os

from greenlight.ui.theme import theme


class NotificationType(Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    FILE_READY = "file_ready"
    INPUT_NEEDED = "input_needed"
    PHASE_COMPLETE = "phase_complete"


@dataclass
class Notification:
    """A notification."""
    notification_type: NotificationType
    title: str
    message: str
    timestamp: datetime
    file_path: Optional[str] = None
    action_callback: Optional[Callable] = None
    dismissed: bool = False


class NotificationToast(ctk.CTkFrame):
    """A single notification toast widget."""
    
    def __init__(
        self,
        master,
        notification: Notification,
        on_click: Callable[[Notification], None] = None,
        on_dismiss: Callable[[Notification], None] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        
        self.notification = notification
        self.on_click = on_click
        self.on_dismiss = on_dismiss
        
        self._setup_ui()
    
    def _get_colors(self) -> tuple:
        """Get colors based on notification type."""
        colors = {
            NotificationType.INFO: (theme.colors.info, "ℹ️"),
            NotificationType.SUCCESS: (theme.colors.success, "✅"),
            NotificationType.WARNING: (theme.colors.warning, "⚠️"),
            NotificationType.ERROR: (theme.colors.error, "❌"),
            NotificationType.FILE_READY: (theme.colors.accent, "📄"),
            NotificationType.INPUT_NEEDED: (theme.colors.primary, "✏️"),
            NotificationType.PHASE_COMPLETE: (theme.colors.success, "🎉"),
        }
        return colors.get(self.notification.notification_type, (theme.colors.info, "•"))
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        color, icon = self._get_colors()
        
        self.configure(
            fg_color=theme.colors.bg_light,
            corner_radius=8,
            border_width=2,
            border_color=color
        )
        
        # Make clickable
        self.bind("<Button-1>", self._on_click)
        
        # Content frame
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=theme.spacing.sm, pady=theme.spacing.sm)
        content.bind("<Button-1>", self._on_click)
        
        # Header row
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")
        header.bind("<Button-1>", self._on_click)
        
        # Icon and title
        icon_label = ctk.CTkLabel(header, text=icon, font=(theme.fonts.family, 14))
        icon_label.pack(side="left")
        icon_label.bind("<Button-1>", self._on_click)
        
        title_label = ctk.CTkLabel(
            header,
            text=self.notification.title,
            font=(theme.fonts.family, theme.fonts.size_normal, "bold"),
            text_color=theme.colors.text_primary
        )
        title_label.pack(side="left", padx=theme.spacing.xs)
        title_label.bind("<Button-1>", self._on_click)
        
        # Dismiss button
        dismiss_btn = ctk.CTkButton(
            header,
            text="✕",
            width=20,
            height=20,
            fg_color="transparent",
            hover_color=theme.colors.bg_hover,
            command=self._dismiss
        )
        dismiss_btn.pack(side="right")
        
        # Message
        msg_label = ctk.CTkLabel(
            content,
            text=self.notification.message,
            text_color=theme.colors.text_secondary,
            wraplength=220,
            anchor="w",
            justify="left"
        )
        msg_label.pack(fill="x", pady=(theme.spacing.xs, 0))
        msg_label.bind("<Button-1>", self._on_click)
        
        # File path hint
        if self.notification.file_path:
            from pathlib import Path
            file_name = Path(self.notification.file_path).name
            file_label = ctk.CTkLabel(
                content,
                text=f"📁 {file_name}",
                text_color=color,
                font=(theme.fonts.family, theme.fonts.size_small)
            )
            file_label.pack(anchor="w", pady=(theme.spacing.xs, 0))
            file_label.bind("<Button-1>", self._on_click)
        
        # Time
        time_str = self.notification.timestamp.strftime("%H:%M:%S")
        time_label = ctk.CTkLabel(
            content,
            text=time_str,
            text_color=theme.colors.text_muted,
            font=(theme.fonts.family, 9)
        )
        time_label.pack(anchor="e")
    
    def _on_click(self, event=None) -> None:
        """Handle click."""
        if self.on_click:
            self.on_click(self.notification)

    def _dismiss(self) -> None:
        """Dismiss notification."""
        self.notification.dismissed = True
        if self.on_dismiss:
            self.on_dismiss(self.notification)


class NotificationManager(ctk.CTkFrame):
    """
    Notification manager with toast notifications.

    Features:
    - Toast notifications with auto-dismiss
    - Sound notifications (system beep)
    - Clickable file navigation
    - Stacked notification display
    """

    def __init__(
        self,
        master,
        on_file_open: Callable[[str], None] = None,
        max_visible: int = 5,
        auto_dismiss_ms: int = 8000,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_file_open = on_file_open
        self.max_visible = max_visible
        self.auto_dismiss_ms = auto_dismiss_ms

        self._notifications: List[Notification] = []
        self._toast_widgets: Dict[Notification, NotificationToast] = {}
        self._sound_enabled = True

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.configure(
            fg_color="transparent",
            width=280,
            height=0  # Start with no height - only expand when notifications exist
        )

        # Track if we're currently visible
        self._is_placed = False

        # Notifications stack from bottom
        self.pack_propagate(False)

    def _update_visibility(self) -> None:
        """Show or hide the notification manager based on active notifications."""
        active_count = len([n for n in self._notifications if not n.dismissed])

        if active_count > 0 and not self._is_placed:
            # Show the notification manager
            self.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
            self._is_placed = True
        elif active_count == 0 and self._is_placed:
            # Hide the notification manager
            self.place_forget()
            self._is_placed = False

    def _play_sound(self, notification_type: NotificationType) -> None:
        """Play notification sound."""
        if not self._sound_enabled:
            return

        def beep():
            try:
                # Windows beep
                import winsound
                if notification_type == NotificationType.ERROR:
                    winsound.MessageBeep(winsound.MB_ICONHAND)
                elif notification_type == NotificationType.WARNING:
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                elif notification_type == NotificationType.INPUT_NEEDED:
                    winsound.MessageBeep(winsound.MB_ICONQUESTION)
                else:
                    winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                # Fallback: print bell character
                print("\a", end="", flush=True)

        # Play in background thread
        threading.Thread(target=beep, daemon=True).start()

    def notify(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        file_path: str = None,
        action_callback: Callable = None,
        play_sound: bool = True
    ) -> Notification:
        """Show a notification."""
        notification = Notification(
            notification_type=notification_type,
            title=title,
            message=message,
            timestamp=datetime.now(),
            file_path=file_path,
            action_callback=action_callback
        )

        self._notifications.append(notification)

        # Play sound
        if play_sound:
            self._play_sound(notification_type)

        # Create toast widget
        self._show_toast(notification)

        # Auto-dismiss after timeout
        if self.auto_dismiss_ms > 0:
            self.after(self.auto_dismiss_ms, lambda: self._auto_dismiss(notification))

        return notification

    def _show_toast(self, notification: Notification) -> None:
        """Show a toast notification."""
        # Remove oldest if at max
        visible = [n for n in self._notifications if not n.dismissed]
        if len(visible) > self.max_visible:
            oldest = visible[0]
            self._dismiss_notification(oldest)

        # Create toast
        toast = NotificationToast(
            self,
            notification,
            on_click=self._on_notification_click,
            on_dismiss=self._dismiss_notification
        )
        toast.pack(fill="x", pady=theme.spacing.xs)

        self._toast_widgets[notification] = toast

        # Show the notification manager if hidden
        self._update_visibility()

    def _dismiss_notification(self, notification: Notification) -> None:
        """Dismiss a notification."""
        notification.dismissed = True
        if notification in self._toast_widgets:
            self._toast_widgets[notification].destroy()
            del self._toast_widgets[notification]

        # Hide the notification manager if no more notifications
        self._update_visibility()

    def _auto_dismiss(self, notification: Notification) -> None:
        """Auto-dismiss a notification if not already dismissed."""
        if not notification.dismissed:
            self._dismiss_notification(notification)

    def _on_notification_click(self, notification: Notification) -> None:
        """Handle notification click."""
        # Open file if available
        if notification.file_path and self.on_file_open:
            self.on_file_open(notification.file_path)

        # Call action callback if available
        if notification.action_callback:
            notification.action_callback()

        # Dismiss
        self._dismiss_notification(notification)

    # Convenience methods
    def notify_info(self, title: str, message: str) -> Notification:
        """Show info notification."""
        return self.notify(NotificationType.INFO, title, message)

    def notify_success(self, title: str, message: str) -> Notification:
        """Show success notification."""
        return self.notify(NotificationType.SUCCESS, title, message)

    def notify_warning(self, title: str, message: str) -> Notification:
        """Show warning notification."""
        return self.notify(NotificationType.WARNING, title, message)

    def notify_error(self, title: str, message: str) -> Notification:
        """Show error notification."""
        return self.notify(NotificationType.ERROR, title, message)

    def notify_file_ready(self, file_path: str, message: str = None) -> Notification:
        """Show file ready notification."""
        from pathlib import Path
        name = Path(file_path).name
        return self.notify(
            NotificationType.FILE_READY,
            "File Ready",
            message or f"New file created: {name}",
            file_path=file_path
        )

    def notify_input_needed(self, phase: str, message: str = None) -> Notification:
        """Show input needed notification."""
        return self.notify(
            NotificationType.INPUT_NEEDED,
            f"Input Needed: {phase}",
            message or "Your input is required to continue"
        )

    def notify_phase_complete(self, phase: str) -> Notification:
        """Show phase complete notification."""
        return self.notify(
            NotificationType.PHASE_COMPLETE,
            "Phase Complete",
            f"{phase} has finished successfully"
        )

    def set_sound_enabled(self, enabled: bool) -> None:
        """Enable or disable notification sounds."""
        self._sound_enabled = enabled

    def clear_all(self) -> None:
        """Clear all notifications."""
        for notification in list(self._toast_widgets.keys()):
            self._dismiss_notification(notification)

    def get_notifications(self) -> List[Notification]:
        """Get all notifications."""
        return self._notifications.copy()

