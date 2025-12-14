"""
Greenlight Status Bar

Bottom status bar showing system status and regeneration queue.
"""

import customtkinter as ctk
from typing import Dict, List, Optional, Any
from datetime import datetime

from greenlight.ui.theme import theme


class StatusBar(ctk.CTkFrame):
    """
    Status bar component.
    
    Features:
    - System status display
    - Regeneration queue indicator
    - Progress tracking
    - Quick actions
    """
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self._queue_count = 0
        self._current_task = ""
        self._progress = 0.0
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.configure(
            fg_color=theme.colors.bg_dark,
            corner_radius=0,
            height=30
        )
        self.pack_propagate(False)
        
        # Left section: Status
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=theme.spacing.md)
        
        self.status_indicator = ctk.CTkLabel(
            left,
            text="●",
            text_color=theme.colors.success,
            font=(theme.fonts.family, 10)
        )
        self.status_indicator.pack(side="left")
        
        self.status_label = ctk.CTkLabel(
            left,
            text="Ready",
            **theme.get_label_style("muted")
        )
        self.status_label.pack(side="left", padx=theme.spacing.sm)
        
        # Center section: Current task
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(side="left", fill="x", expand=True)
        
        self.task_label = ctk.CTkLabel(
            center,
            text="",
            **theme.get_label_style("muted")
        )
        self.task_label.pack(side="left", padx=theme.spacing.md)
        
        self.progress_bar = ctk.CTkProgressBar(
            center,
            width=150,
            height=8,
            progress_color=theme.colors.primary
        )
        self.progress_bar.pack(side="left")
        self.progress_bar.set(0)
        
        # Right section: Queue and actions
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=theme.spacing.md)
        
        # Regeneration queue
        self.queue_btn = ctk.CTkButton(
            right,
            text="🔄 Queue: 0",
            width=100,
            height=24,
            fg_color="transparent",
            hover_color=theme.colors.bg_hover,
            text_color=theme.colors.text_muted,
            command=self._show_queue
        )
        self.queue_btn.pack(side="left", padx=theme.spacing.sm)
        
        # LLM indicator
        self.llm_label = ctk.CTkLabel(
            right,
            text="LLM: Claude",
            **theme.get_label_style("muted")
        )
        self.llm_label.pack(side="left", padx=theme.spacing.sm)
        
        # Time
        self.time_label = ctk.CTkLabel(
            right,
            text="",
            **theme.get_label_style("muted")
        )
        self.time_label.pack(side="left")
        self._update_time()
    
    def set_status(self, status: str, color: str = None) -> None:
        """Set the status message."""
        self.status_label.configure(text=status)
        if color:
            self.status_indicator.configure(text_color=color)
    
    def set_task(self, task: str, progress: float = 0.0) -> None:
        """Set the current task."""
        self._current_task = task
        self._progress = progress
        
        self.task_label.configure(text=task)
        self.progress_bar.set(progress)
        
        if progress > 0:
            self.progress_bar.pack(side="left")
        else:
            self.progress_bar.pack_forget()
    
    def set_queue_count(self, count: int) -> None:
        """Set the regeneration queue count."""
        self._queue_count = count
        self.queue_btn.configure(text=f"🔄 Queue: {count}")
        
        if count > 0:
            self.queue_btn.configure(text_color=theme.colors.warning)
        else:
            self.queue_btn.configure(text_color=theme.colors.text_muted)
    
    def set_llm(self, llm_name: str) -> None:
        """Set the current LLM indicator."""
        self.llm_label.configure(text=f"LLM: {llm_name}")
    
    def _show_queue(self) -> None:
        """Show the regeneration queue dialog."""
        # Would open queue management dialog
        pass
    
    def _update_time(self) -> None:
        """Update the time display."""
        now = datetime.now().strftime("%H:%M")
        self.time_label.configure(text=now)
        self.after(60000, self._update_time)  # Update every minute
    
    def show_processing(self, message: str = "Processing...") -> None:
        """Show processing state."""
        self.set_status(message, theme.colors.processing)
        self.status_indicator.configure(text_color=theme.colors.processing)
    
    def show_success(self, message: str = "Complete") -> None:
        """Show success state."""
        self.set_status(message, theme.colors.success)
        self.status_indicator.configure(text_color=theme.colors.success)
    
    def show_error(self, message: str = "Error") -> None:
        """Show error state."""
        self.set_status(message, theme.colors.error)
        self.status_indicator.configure(text_color=theme.colors.error)

