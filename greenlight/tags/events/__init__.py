"""
Greenlight Tags - Events Module

Event tag extraction and validation.

Structure:
    /prompts/
        /01_extraction/     - Tag extraction prompts
    /scripts/
        event_tagger.py     - Event-specific tagging logic
    event_tag_manager.py - Main event tag manager
"""

from greenlight.tags.events.event_tag_manager import EventTagManager

__all__ = [
    'EventTagManager',
]

