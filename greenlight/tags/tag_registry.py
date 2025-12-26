"""
Greenlight Tag Registry

Central registry for all project tags with metadata and validation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime
import json
from pathlib import Path

from greenlight.core.constants import TagCategory, VALID_DIRECTIONS
from greenlight.core.exceptions import UnregisteredTagError, InvalidTagFormatError
from .tag_parser import TagParser, ParsedTag


@dataclass
class TagEntry:
    """Registry entry for a tag with full metadata."""
    name: str
    category: TagCategory
    description: str = ""
    aliases: List[str] = field(default_factory=list)
    attributes: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0

    # For characters
    visual_description: Optional[str] = None

    # For locations
    directional_views: Dict[str, str] = field(default_factory=dict)  # N/E/S/W -> description

    # Reference prompts (from ReferencePromptBuilder)
    # For characters/props: single multi-view prompt
    reference_sheet_prompt: Optional[str] = None
    # For locations: directional prompts {"north": ..., "east": ..., "south": ..., "west": ...}
    reference_prompts: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'category': self.category.value,
            'description': self.description,
            'aliases': self.aliases,
            'attributes': self.attributes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'usage_count': self.usage_count,
            'visual_description': self.visual_description,
            'directional_views': self.directional_views,
            'reference_sheet_prompt': self.reference_sheet_prompt,
            'reference_prompts': self.reference_prompts
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TagEntry':
        """Create from dictionary."""
        return cls(
            name=data['name'],
            category=TagCategory(data['category']),
            description=data.get('description', ''),
            aliases=data.get('aliases', []),
            attributes=data.get('attributes', {}),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now(),
            updated_at=datetime.fromisoformat(data['updated_at']) if 'updated_at' in data else datetime.now(),
            usage_count=data.get('usage_count', 0),
            visual_description=data.get('visual_description'),
            directional_views=data.get('directional_views', {}),
            reference_sheet_prompt=data.get('reference_sheet_prompt'),
            reference_prompts=data.get('reference_prompts', {})
        )


class TagRegistry:
    """
    Central registry for all project tags.
    
    Provides:
    - Tag registration and lookup
    - Alias resolution
    - Category filtering
    - Persistence to/from JSON
    """
    
    def __init__(self):
        self._tags: Dict[str, TagEntry] = {}
        self._aliases: Dict[str, str] = {}  # alias -> canonical name
        self._parser = TagParser()
    
    def register(
        self,
        name: str,
        category: TagCategory,
        description: str = "",
        aliases: List[str] = None,
        **attributes
    ) -> TagEntry:
        """
        Register a new tag in the registry.
        
        Args:
            name: Tag name (without brackets)
            category: Tag category
            description: Tag description
            aliases: Alternative names for the tag
            **attributes: Additional attributes
            
        Returns:
            Created TagEntry
        """
        # Validate format
        if not self._parser.validate_format(name):
            raise InvalidTagFormatError(name)
        
        # Create entry
        entry = TagEntry(
            name=name,
            category=category,
            description=description,
            aliases=aliases or [],
            attributes=attributes
        )
        
        self._tags[name] = entry
        
        # Register aliases
        for alias in entry.aliases:
            self._aliases[alias.upper()] = name
        
        return entry
    
    def get(self, name: str) -> TagEntry:
        """
        Get a tag entry by name or alias.
        
        Args:
            name: Tag name or alias
            
        Returns:
            TagEntry
            
        Raises:
            UnregisteredTagError: If tag not found
        """
        # Try direct lookup
        if name in self._tags:
            return self._tags[name]
        
        # Try alias lookup
        canonical = self._aliases.get(name.upper())
        if canonical and canonical in self._tags:
            return self._tags[canonical]
        
        raise UnregisteredTagError(name)
    
    def exists(self, name: str) -> bool:
        """Check if a tag exists in the registry."""
        try:
            self.get(name)
            return True
        except UnregisteredTagError:
            return False
    
    def get_by_category(self, category: TagCategory) -> List[TagEntry]:
        """Get all tags of a specific category."""
        return [
            entry for entry in self._tags.values()
            if entry.category == category
        ]
    
    def get_all_names(self) -> Set[str]:
        """Get all registered tag names."""
        return set(self._tags.keys())
    
    def update(self, name: str, **updates) -> TagEntry:
        """
        Update a tag entry.
        
        Args:
            name: Tag name
            **updates: Fields to update
            
        Returns:
            Updated TagEntry
        """
        entry = self.get(name)
        
        for key, value in updates.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        
        entry.updated_at = datetime.now()
        return entry
    
    def increment_usage(self, name: str) -> None:
        """Increment usage count for a tag."""
        if self.exists(name):
            self._tags[name].usage_count += 1
    
    def validate_tags(self, tags: List[str]) -> tuple:
        """
        Validate a list of tags against the registry.
        
        Args:
            tags: List of tag names to validate
            
        Returns:
            Tuple of (valid_tags, invalid_tags)
        """
        valid = []
        invalid = []
        
        for tag in tags:
            if self.exists(tag):
                valid.append(tag)
            else:
                invalid.append(tag)
        
        return valid, invalid
    
    def save(self, path: Path) -> None:
        """Save registry to JSON file."""
        data = {
            'tags': {name: entry.to_dict() for name, entry in self._tags.items()},
            'aliases': self._aliases
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def load(self, path: Path) -> None:
        """Load registry from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self._tags = {
            name: TagEntry.from_dict(entry_data)
            for name, entry_data in data.get('tags', {}).items()
        }
        self._aliases = data.get('aliases', {})

