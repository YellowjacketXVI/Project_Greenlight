"""
Greenlight Tags - Relationships Module

Relationship tag extraction and mapping between entities.

Structure:
    /prompts/
        /01_extraction/     - Relationship extraction prompts
    /scripts/
        relationship_mapper.py - Relationship mapping logic
    relationship_tag_manager.py - Main relationship tag manager
"""

from greenlight.tags.relationships.relationship_tag_manager import RelationshipTagManager

__all__ = [
    'RelationshipTagManager',
]

