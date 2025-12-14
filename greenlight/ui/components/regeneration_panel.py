"""
Greenlight Regeneration Queue Panel

UI for managing the regeneration queue.
"""

import customtkinter as ctk
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from enum import Enum

from greenlight.ui.theme import theme


class QueueItemStatus(Enum):
    """Status of a queue item."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueueItem(ctk.CTkFrame):
    """A single item in the regeneration queue."""
    
    def __init__(
        self,
        master,
        item_id: str,
        title: str,
        status: QueueItemStatus = QueueItemStatus.PENDING,
        priority: int = 0,
        on_cancel: Callable[[str], None] = None,
        on_retry: Callable[[str], None] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        
        self.item_id = item_id
        self.status = status
        self.on_cancel = on_cancel
        self.on_retry = on_retry
        
        self.configure(
            fg_color=theme.colors.bg_light,
            corner_radius=6
        )
        
        # Status indicator
        status_colors = {
            QueueItemStatus.PENDING: theme.colors.pending,
            QueueItemStatus.PROCESSING: theme.colors.processing,
            QueueItemStatus.COMPLETE: theme.colors.complete,
            QueueItemStatus.FAILED: theme.colors.failed,
            QueueItemStatus.CANCELLED: theme.colors.text_muted,
        }
        
        indicator = ctk.CTkLabel(
            self, text="●",
            text_color=status_colors.get(status, theme.colors.text_muted),
            font=(theme.fonts.family, 10)
        )
        indicator.pack(side="left", padx=theme.spacing.sm)
        
        # Title
        title_label = ctk.CTkLabel(
            self, text=title,
            **theme.get_label_style()
        )
        title_label.pack(side="left", fill="x", expand=True)
        
        # Priority badge
        if priority > 0:
            priority_label = ctk.CTkLabel(
                self, text=f"P{priority}",
                text_color=theme.colors.warning,
                font=(theme.fonts.family, 10)
            )
            priority_label.pack(side="left", padx=theme.spacing.sm)
        
        # Action buttons
        if status == QueueItemStatus.PENDING:
            cancel_btn = ctk.CTkButton(
                self, text="✕", width=25, height=25,
                fg_color="transparent",
                hover_color=theme.colors.error,
                command=lambda: on_cancel(item_id) if on_cancel else None
            )
            cancel_btn.pack(side="right", padx=2)
        
        if status == QueueItemStatus.FAILED:
            retry_btn = ctk.CTkButton(
                self, text="↻", width=25, height=25,
                fg_color="transparent",
                hover_color=theme.colors.primary,
                command=lambda: on_retry(item_id) if on_retry else None
            )
            retry_btn.pack(side="right", padx=2)


class RegenerationPanel(ctk.CTkFrame):
    """
    Regeneration queue management panel.
    
    Features:
    - Queue item display
    - Priority management
    - Cancel/retry actions
    - Progress tracking
    """
    
    def __init__(
        self,
        master,
        on_process: Callable[[], None] = None,
        on_clear: Callable[[], None] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        
        self.on_process = on_process
        self.on_clear = on_clear
        self._items: Dict[str, Dict] = {}
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.configure(
            fg_color=theme.colors.bg_medium,
            corner_radius=8
        )
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=40)
        header.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        title = ctk.CTkLabel(
            header, text="🔄 Regeneration Queue",
            **theme.get_label_style("title")
        )
        title.pack(side="left")
        
        self.count_label = ctk.CTkLabel(
            header, text="0 items",
            **theme.get_label_style("muted")
        )
        self.count_label.pack(side="left", padx=theme.spacing.md)
        
        # Action buttons
        clear_btn = ctk.CTkButton(
            header, text="Clear All", width=80,
            command=self._clear_all,
            **theme.get_button_style("secondary")
        )
        clear_btn.pack(side="right", padx=2)
        
        process_btn = ctk.CTkButton(
            header, text="Process All", width=100,
            command=self._process_all,
            **theme.get_button_style("primary")
        )
        process_btn.pack(side="right", padx=2)
        
        # Queue list
        self.queue_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent"
        )
        self.queue_frame.pack(fill="both", expand=True, padx=theme.spacing.md, pady=theme.spacing.sm)
        
        # Empty state
        self.empty_label = ctk.CTkLabel(
            self.queue_frame,
            text="No items in queue",
            **theme.get_label_style("muted")
        )
        self.empty_label.pack(pady=theme.spacing.xl)
    
    def add_item(
        self,
        item_id: str,
        title: str,
        priority: int = 0,
        status: QueueItemStatus = QueueItemStatus.PENDING
    ) -> None:
        """Add an item to the queue."""
        self._items[item_id] = {
            'title': title,
            'priority': priority,
            'status': status,
            'added': datetime.now()
        }
        self._render_queue()
    
    def remove_item(self, item_id: str) -> None:
        """Remove an item from the queue."""
        if item_id in self._items:
            del self._items[item_id]
            self._render_queue()
    
    def update_status(self, item_id: str, status: QueueItemStatus) -> None:
        """Update item status."""
        if item_id in self._items:
            self._items[item_id]['status'] = status
            self._render_queue()
    
    def _render_queue(self) -> None:
        """Render the queue items."""
        # Clear existing
        for widget in self.queue_frame.winfo_children():
            widget.destroy()
        
        if not self._items:
            self.empty_label = ctk.CTkLabel(
                self.queue_frame,
                text="No items in queue",
                **theme.get_label_style("muted")
            )
            self.empty_label.pack(pady=theme.spacing.xl)
            self.count_label.configure(text="0 items")
            return
        
        # Sort by priority
        sorted_items = sorted(
            self._items.items(),
            key=lambda x: (-x[1]['priority'], x[1]['added'])
        )
        
        for item_id, data in sorted_items:
            item = QueueItem(
                self.queue_frame,
                item_id=item_id,
                title=data['title'],
                status=data['status'],
                priority=data['priority'],
                on_cancel=self._cancel_item,
                on_retry=self._retry_item
            )
            item.pack(fill="x", pady=2)
        
        self.count_label.configure(text=f"{len(self._items)} items")
    
    def _cancel_item(self, item_id: str) -> None:
        """Cancel a queue item."""
        self.update_status(item_id, QueueItemStatus.CANCELLED)
    
    def _retry_item(self, item_id: str) -> None:
        """Retry a failed item."""
        self.update_status(item_id, QueueItemStatus.PENDING)
    
    def _process_all(self) -> None:
        """Process all pending items."""
        if self.on_process:
            self.on_process()
    
    def _clear_all(self) -> None:
        """Clear all items."""
        self._items.clear()
        self._render_queue()
        if self.on_clear:
            self.on_clear()

