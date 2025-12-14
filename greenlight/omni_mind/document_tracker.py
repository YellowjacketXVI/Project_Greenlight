"""
Document Change Tracker for OmniMind

Tracks document modifications and notifies OmniMind to prompt users
about saving or reverting changes.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Type of document change."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class DocumentChange:
    """Represents a change to a document."""
    file_path: str
    change_type: ChangeType
    timestamp: datetime = field(default_factory=datetime.now)
    original_content: Optional[str] = None
    current_content: Optional[str] = None
    
    @property
    def file_name(self) -> str:
        return Path(self.file_path).name
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "change_type": self.change_type.value,
            "timestamp": self.timestamp.isoformat(),
            "has_original": self.original_content is not None,
            "has_current": self.current_content is not None,
        }


class DocumentTracker:
    """
    Tracks document changes and notifies OmniMind.
    
    Singleton pattern - use get_document_tracker() to get instance.
    """
    
    _instance: Optional['DocumentTracker'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._changes: Dict[str, DocumentChange] = {}
        self._callbacks: List[Callable[[List[DocumentChange]], None]] = []
        self._prompt_callback: Optional[Callable[[str], None]] = None
        self._prompt_pending = False
        self._prompt_timer: Optional[threading.Timer] = None
        self._prompt_delay = 3.0  # Seconds to wait before prompting
        self._initialized = True
        logger.info("DocumentTracker initialized")
    
    def register_prompt_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback for OmniMind prompts."""
        self._prompt_callback = callback
        logger.debug("Prompt callback registered")
    
    def register_change_callback(self, callback: Callable[[List[DocumentChange]], None]) -> None:
        """Register callback for change notifications."""
        self._callbacks.append(callback)
    
    def track_change(
        self,
        file_path: str,
        change_type: ChangeType,
        original_content: Optional[str] = None,
        current_content: Optional[str] = None
    ) -> None:
        """Track a document change."""
        change = DocumentChange(
            file_path=file_path,
            change_type=change_type,
            original_content=original_content,
            current_content=current_content
        )
        self._changes[file_path] = change
        logger.info(f"Tracked change: {change_type.value} - {file_path}")
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback([change])
            except Exception as e:
                logger.error(f"Change callback error: {e}")
        
        # Schedule OmniMind prompt
        self._schedule_prompt()
    
    def _schedule_prompt(self) -> None:
        """Schedule a prompt to OmniMind after delay."""
        if self._prompt_timer:
            self._prompt_timer.cancel()
        
        self._prompt_timer = threading.Timer(self._prompt_delay, self._trigger_prompt)
        self._prompt_timer.start()
    
    def _trigger_prompt(self) -> None:
        """Trigger OmniMind prompt about changes."""
        if not self._changes or not self._prompt_callback:
            return
        
        changes = list(self._changes.values())
        file_list = ", ".join(c.file_name for c in changes[:5])
        if len(changes) > 5:
            file_list += f" and {len(changes) - 5} more"
        
        prompt = (
            f"📝 I noticed you made changes to: **{file_list}**\n\n"
            f"Would you like me to:\n"
            f"1. **Save** these changes\n"
            f"2. **Revert** to the original\n"
            f"3. **Keep editing** (I'll ask again later)"
        )
        
        try:
            self._prompt_callback(prompt)
            logger.info(f"Prompted user about {len(changes)} changed documents")
        except Exception as e:
            logger.error(f"Failed to prompt user: {e}")
    
    def get_pending_changes(self) -> List[DocumentChange]:
        """Get all pending changes."""
        return list(self._changes.values())
    
    def get_changes_summary(self) -> Dict[str, Any]:
        """Get summary of pending changes for tools."""
        changes = self.get_pending_changes()
        return {
            "total_changes": len(changes),
            "files": [c.to_dict() for c in changes],
            "file_names": [c.file_name for c in changes],
        }

    def save_changes(self, file_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Save specified changes (or all if none specified)."""
        to_save = file_paths or list(self._changes.keys())
        saved = []
        errors = []

        for file_path in to_save:
            if file_path not in self._changes:
                continue

            change = self._changes[file_path]
            if change.current_content is not None:
                try:
                    Path(file_path).write_text(change.current_content, encoding='utf-8')
                    saved.append(file_path)
                    del self._changes[file_path]
                    logger.info(f"Saved: {file_path}")
                except Exception as e:
                    errors.append({"file": file_path, "error": str(e)})
                    logger.error(f"Failed to save {file_path}: {e}")

        return {
            "saved": saved,
            "saved_count": len(saved),
            "errors": errors,
            "remaining_changes": len(self._changes)
        }

    def revert_changes(self, file_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Revert specified changes (or all if none specified)."""
        to_revert = file_paths or list(self._changes.keys())
        reverted = []
        errors = []

        for file_path in to_revert:
            if file_path not in self._changes:
                continue

            change = self._changes[file_path]
            if change.original_content is not None:
                try:
                    Path(file_path).write_text(change.original_content, encoding='utf-8')
                    reverted.append(file_path)
                    del self._changes[file_path]
                    logger.info(f"Reverted: {file_path}")
                except Exception as e:
                    errors.append({"file": file_path, "error": str(e)})
                    logger.error(f"Failed to revert {file_path}: {e}")
            else:
                # No original content, just clear the change
                del self._changes[file_path]
                reverted.append(file_path)

        return {
            "reverted": reverted,
            "reverted_count": len(reverted),
            "errors": errors,
            "remaining_changes": len(self._changes)
        }

    def clear_changes(self) -> None:
        """Clear all tracked changes without saving or reverting."""
        self._changes.clear()
        if self._prompt_timer:
            self._prompt_timer.cancel()
        logger.info("All tracked changes cleared")


def get_document_tracker() -> DocumentTracker:
    """Get the singleton DocumentTracker instance."""
    return DocumentTracker()

