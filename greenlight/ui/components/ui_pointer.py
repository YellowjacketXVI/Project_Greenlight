"""
OmniMind UI Pointer System

Allows OmniMind to highlight UI elements with neon green to guide users.
"""

import customtkinter as ctk
from typing import Dict, Optional, Callable, Any, List
from dataclasses import dataclass, field
from enum import Enum
import threading
import time

from greenlight.ui.theme import theme
from greenlight.core.logging_config import get_logger

logger = get_logger("ui.pointer")


class HighlightStyle(Enum):
    """Highlight animation styles."""
    SOLID = "solid"          # Solid neon green border
    PULSE = "pulse"          # Pulsing glow effect
    BLINK = "blink"          # Blinking highlight
    ARROW = "arrow"          # Arrow pointing to element


@dataclass
class UIElement:
    """A registered UI element that can be highlighted."""
    element_id: str
    widget: ctk.CTkBaseClass
    description: str
    category: str = "general"
    original_border_color: Optional[str] = None
    original_border_width: int = 0
    original_fg_color: Optional[str] = None
    is_highlighted: bool = False


class UIElementRegistry:
    """
    Registry of UI elements that OmniMind can highlight.
    
    Usage:
        registry = UIElementRegistry()
        
        # Register elements
        registry.register("world_bible_btn", button, "World Bible button")
        
        # Highlight from OmniMind
        registry.highlight("world_bible_btn")
        registry.pulse("world_bible_btn", duration=3.0)
        registry.unhighlight("world_bible_btn")
    """
    
    _instance: Optional['UIElementRegistry'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._elements: Dict[str, UIElement] = {}
        self._highlight_threads: Dict[str, threading.Thread] = {}
        self._stop_flags: Dict[str, bool] = {}
        self._callbacks: List[Callable[[str, str], None]] = []
        self._initialized = True
        
        logger.info("UIElementRegistry initialized")
    
    def register(
        self,
        element_id: str,
        widget: ctk.CTkBaseClass,
        description: str,
        category: str = "general"
    ) -> None:
        """Register a UI element for highlighting."""
        # Store original styling
        original_border_color = None
        original_border_width = 0
        original_fg_color = None
        
        try:
            if hasattr(widget, 'cget'):
                try:
                    original_border_color = widget.cget('border_color')
                except Exception:
                    pass
                try:
                    original_border_width = widget.cget('border_width')
                except Exception:
                    pass
                try:
                    original_fg_color = widget.cget('fg_color')
                except Exception:
                    pass
        except Exception:
            pass
        
        element = UIElement(
            element_id=element_id,
            widget=widget,
            description=description,
            category=category,
            original_border_color=original_border_color,
            original_border_width=original_border_width,
            original_fg_color=original_fg_color
        )
        
        self._elements[element_id] = element
        logger.debug(f"Registered UI element: {element_id}")
    
    def unregister(self, element_id: str) -> None:
        """Unregister a UI element."""
        if element_id in self._elements:
            self.unhighlight(element_id)
            del self._elements[element_id]
            logger.debug(f"Unregistered UI element: {element_id}")
    
    def highlight(
        self,
        element_id: str,
        style: HighlightStyle = HighlightStyle.SOLID,
        message: Optional[str] = None
    ) -> bool:
        """Highlight a UI element with neon green."""
        if element_id not in self._elements:
            logger.warning(f"Element not found: {element_id}")
            return False
        
        element = self._elements[element_id]
        
        try:
            widget = element.widget
            widget.configure(
                border_color=theme.colors.neon_green,
                border_width=3
            )
            element.is_highlighted = True
            
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(element_id, message or f"Look at: {element.description}")
                except Exception:
                    pass
            
            logger.info(f"Highlighted: {element_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to highlight {element_id}: {e}")
            return False

    def unhighlight(self, element_id: str) -> bool:
        """Remove highlight from a UI element."""
        if element_id not in self._elements:
            return False

        element = self._elements[element_id]

        # Stop any running animation
        self._stop_flags[element_id] = True

        try:
            widget = element.widget
            widget.configure(
                border_color=element.original_border_color or theme.colors.border,
                border_width=element.original_border_width
            )
            element.is_highlighted = False
            logger.debug(f"Unhighlighted: {element_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to unhighlight {element_id}: {e}")
            return False

    def unhighlight_all(self) -> None:
        """Remove all highlights."""
        for element_id in list(self._elements.keys()):
            self.unhighlight(element_id)

    def pulse(
        self,
        element_id: str,
        duration: float = 3.0,
        interval: float = 0.5
    ) -> bool:
        """Pulse highlight on an element for a duration."""
        if element_id not in self._elements:
            return False

        self._stop_flags[element_id] = False

        def pulse_thread():
            element = self._elements.get(element_id)
            if not element:
                return

            end_time = time.time() + duration
            is_on = True

            while time.time() < end_time and not self._stop_flags.get(element_id, True):
                try:
                    if is_on:
                        element.widget.configure(
                            border_color=theme.colors.neon_green,
                            border_width=3
                        )
                    else:
                        element.widget.configure(
                            border_color=theme.colors.neon_green_dim,
                            border_width=2
                        )
                    is_on = not is_on
                except Exception:
                    break
                time.sleep(interval)

            # Restore original
            self.unhighlight(element_id)

        thread = threading.Thread(target=pulse_thread, daemon=True)
        self._highlight_threads[element_id] = thread
        thread.start()
        return True

    def point_to(
        self,
        element_id: str,
        message: str,
        duration: float = 5.0
    ) -> bool:
        """
        Point to an element with highlight and message.
        Called by OmniMind to guide users.
        """
        success = self.pulse(element_id, duration=duration)

        if success:
            # Notify callbacks with the guidance message
            for callback in self._callbacks:
                try:
                    callback(element_id, message)
                except Exception:
                    pass

        return success

    def add_callback(self, callback: Callable[[str, str], None]) -> None:
        """Add a callback for highlight events."""
        self._callbacks.append(callback)

    def get_element(self, element_id: str) -> Optional[UIElement]:
        """Get a registered element."""
        return self._elements.get(element_id)

    def list_elements(self, category: Optional[str] = None) -> List[str]:
        """List all registered element IDs."""
        if category:
            return [eid for eid, e in self._elements.items() if e.category == category]
        return list(self._elements.keys())

    def get_element_info(self) -> Dict[str, Dict[str, Any]]:
        """Get info about all registered elements for OmniMind."""
        return {
            eid: {
                "description": e.description,
                "category": e.category,
                "is_highlighted": e.is_highlighted
            }
            for eid, e in self._elements.items()
        }

    def click_element(self, element_id: str) -> bool:
        """
        Programmatically click a UI element.
        Used by OmniMind for UI automation.
        """
        if element_id not in self._elements:
            logger.warning(f"Element not found for click: {element_id}")
            return False

        element = self._elements[element_id]
        widget = element.widget

        try:
            # Try to invoke the button's command
            if hasattr(widget, 'invoke'):
                widget.invoke()
                logger.info(f"Clicked element: {element_id}")
                return True
            elif hasattr(widget, '_command') and widget._command:
                widget._command()
                logger.info(f"Invoked command on element: {element_id}")
                return True
            else:
                logger.warning(f"Element {element_id} has no clickable action")
                return False
        except Exception as e:
            logger.error(f"Error clicking element {element_id}: {e}")
            return False

    def invoke_action(self, element_id: str, action: str, **kwargs) -> Any:
        """
        Invoke a specific action on a UI element.

        Actions:
        - 'click': Click the element
        - 'set_value': Set a value (for entries, sliders)
        - 'select': Select an option (for dropdowns)
        - 'focus': Focus the element
        """
        if element_id not in self._elements:
            logger.warning(f"Element not found: {element_id}")
            return None

        element = self._elements[element_id]
        widget = element.widget

        try:
            if action == 'click':
                return self.click_element(element_id)

            elif action == 'set_value':
                value = kwargs.get('value', '')
                if hasattr(widget, 'delete') and hasattr(widget, 'insert'):
                    widget.delete(0, 'end')
                    widget.insert(0, str(value))
                    return True
                elif hasattr(widget, 'set'):
                    widget.set(value)
                    return True

            elif action == 'select':
                value = kwargs.get('value', '')
                if hasattr(widget, 'set'):
                    widget.set(value)
                    return True

            elif action == 'focus':
                if hasattr(widget, 'focus_set'):
                    widget.focus_set()
                    return True

            logger.warning(f"Unknown action '{action}' for element {element_id}")
            return False

        except Exception as e:
            logger.error(f"Error invoking {action} on {element_id}: {e}")
            return False

    def get_element_state(self, element_id: str) -> Dict[str, Any]:
        """Get the current state of a UI element."""
        if element_id not in self._elements:
            return {"error": f"Element not found: {element_id}"}

        element = self._elements[element_id]
        widget = element.widget

        state = {
            "element_id": element_id,
            "description": element.description,
            "category": element.category,
            "is_highlighted": element.is_highlighted,
            "widget_type": type(widget).__name__
        }

        try:
            # Get common widget properties
            if hasattr(widget, 'cget'):
                try:
                    state["text"] = widget.cget('text')
                except:
                    pass
                try:
                    state["state"] = widget.cget('state')
                except:
                    pass

            if hasattr(widget, 'get'):
                try:
                    state["value"] = widget.get()
                except:
                    pass

            # Check visibility
            if hasattr(widget, 'winfo_viewable'):
                state["visible"] = widget.winfo_viewable()

        except Exception as e:
            state["error"] = str(e)

        return state


# Global singleton instance
_registry: Optional[UIElementRegistry] = None


def get_ui_registry() -> UIElementRegistry:
    """Get the global UI element registry."""
    global _registry
    if _registry is None:
        _registry = UIElementRegistry()
    return _registry


def register_element(
    element_id: str,
    widget: ctk.CTkBaseClass,
    description: str,
    category: str = "general"
) -> None:
    """Convenience function to register an element."""
    get_ui_registry().register(element_id, widget, description, category)


def highlight_element(element_id: str, message: Optional[str] = None) -> bool:
    """Convenience function to highlight an element."""
    return get_ui_registry().highlight(element_id, message=message)


def point_to_element(element_id: str, message: str, duration: float = 5.0) -> bool:
    """Convenience function for OmniMind to point to an element."""
    return get_ui_registry().point_to(element_id, message, duration)


def click_element(element_id: str) -> bool:
    """Convenience function for OmniMind to click an element."""
    return get_ui_registry().click_element(element_id)


def invoke_action(element_id: str, action: str, **kwargs) -> Any:
    """Convenience function for OmniMind to invoke an action on an element."""
    return get_ui_registry().invoke_action(element_id, action, **kwargs)


def get_element_state(element_id: str) -> Dict[str, Any]:
    """Convenience function to get element state."""
    return get_ui_registry().get_element_state(element_id)

