"""
Relationship Tag Manager

Manages relationship mapping between entities.
Tracks character-to-character, character-to-location, and other relationships.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Callable, Tuple

from greenlight.core.logging_config import get_logger
from greenlight.agents.prompts import AgentPromptLibrary

logger = get_logger("tags.relationships")


@dataclass
class Relationship:
    """A relationship between two entities."""
    source_tag: str  # e.g., CHAR_PROTAGONIST
    target_tag: str  # e.g., CHAR_ANTAGONIST
    relationship_type: str  # e.g., "rival", "ally", "family"
    description: str
    strength: float = 1.0  # 0.0 to 1.0


@dataclass
class RelationshipExtractionResult:
    """Result from relationship extraction."""
    relationships: List[Relationship]
    entity_pairs: Set[Tuple[str, str]]
    is_complete: bool


class RelationshipTagManager:
    """
    Manages relationship mapping between entities.
    
    Responsibilities:
    - Extract relationships from narrative
    - Map character-to-character relationships
    - Map character-to-location associations
    - Track relationship evolution across story
    
    Uses externalized prompts from:
        tags/relationships/prompts/01_extraction/
    """
    
    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        world_bible: Optional[Dict] = None
    ):
        """
        Initialize relationship tag manager.
        
        Args:
            llm_caller: Async function to call LLM
            world_bible: World bible with entity data
        """
        self.llm_caller = llm_caller
        self.world_bible = world_bible or {}
        self._relationships: Dict[Tuple[str, str], Relationship] = {}
    
    async def extract_relationships(
        self,
        text: str,
        context: Optional[str] = None
    ) -> RelationshipExtractionResult:
        """
        Extract relationships from text.
        
        Args:
            text: Text to extract relationships from
            context: Optional additional context
            
        Returns:
            RelationshipExtractionResult with extracted relationships
        """
        logger.info("Extracting relationships")
        
        # Parse entity tags from text
        entities = self._parse_all_entity_tags(text)
        
        # Find co-occurring entities (potential relationships)
        pairs = self._find_entity_pairs(entities)
        
        return RelationshipExtractionResult(
            relationships=list(self._relationships.values()),
            entity_pairs=pairs,
            is_complete=True
        )
    
    def add_relationship(
        self,
        source_tag: str,
        target_tag: str,
        relationship_type: str,
        description: str,
        strength: float = 1.0
    ) -> Relationship:
        """
        Add or update a relationship.
        
        Args:
            source_tag: Source entity tag
            target_tag: Target entity tag
            relationship_type: Type of relationship
            description: Description of relationship
            strength: Relationship strength (0.0-1.0)
            
        Returns:
            The created/updated Relationship
        """
        key = (source_tag, target_tag)
        relationship = Relationship(
            source_tag=source_tag,
            target_tag=target_tag,
            relationship_type=relationship_type,
            description=description,
            strength=strength
        )
        self._relationships[key] = relationship
        logger.debug(f"Added relationship: {source_tag} -> {target_tag} ({relationship_type})")
        return relationship
    
    def get_relationships_for(self, tag: str) -> List[Relationship]:
        """Get all relationships involving a tag."""
        return [
            r for r in self._relationships.values()
            if r.source_tag == tag or r.target_tag == tag
        ]
    
    def _parse_all_entity_tags(self, text: str) -> Set[str]:
        """Parse all entity tags from text."""
        import re
        pattern = r'\[?((?:CHAR|LOC|PROP|EVENT|CONCEPT)_[A-Z0-9_]+)\]?'
        matches = re.findall(pattern, text.upper())
        return set(matches)
    
    def _find_entity_pairs(self, entities: Set[str]) -> Set[Tuple[str, str]]:
        """Find pairs of entities that might have relationships."""
        pairs = set()
        entity_list = sorted(entities)
        for i, e1 in enumerate(entity_list):
            for e2 in entity_list[i+1:]:
                pairs.add((e1, e2))
        return pairs

