"""
Greenlight Context Assembler

Assembles context from multiple sources with token budget management.

Enhanced Features:
- Configurable token budgets per pipeline/agent type
- Attention-weighted context priority for focal entities
- Relationship context surfacing
- Dynamic budget rebalancing
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
from copy import deepcopy

from greenlight.core.constants import CONTEXT_WINDOW_LIMIT
from greenlight.core.logging_config import get_logger
from greenlight.utils.unicode_utils import count_tokens_estimate

logger = get_logger("context.assembler")


class ContextSource(Enum):
    """Sources of context information."""
    VECTOR_SEARCH = "vector_search"
    KEYWORD_SEARCH = "keyword_search"
    GRAPH_TRAVERSAL = "graph_traversal"
    WORLD_BIBLE = "world_bible"
    RECENT_EDITS = "recent_edits"
    USER_SELECTION = "user_selection"
    RELATIONSHIP = "relationship"  # New: relationship context
    FOCAL_ENTITY = "focal_entity"  # New: focal entity priority context


@dataclass
class ContextItem:
    """A single item of context."""
    id: str
    content: str
    source: ContextSource
    relevance_score: float
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.token_count == 0:
            self.token_count = count_tokens_estimate(self.content)


@dataclass
class AssembledContext:
    """Result of context assembly."""
    items: List[ContextItem]
    total_tokens: int
    budget_used: float
    sources_used: List[ContextSource]
    truncated: bool = False
    
    @property
    def full_text(self) -> str:
        """Get concatenated context text."""
        return "\n\n---\n\n".join(item.content for item in self.items)
    
    def get_by_source(self, source: ContextSource) -> List[ContextItem]:
        """Get items from a specific source."""
        return [item for item in self.items if item.source == source]


class ContextAssembler:
    """
    Assembles context from multiple sources within token budget.
    
    Features:
    - Token budget management
    - Source prioritization
    - Deduplication
    - Relevance-based selection
    """
    
    # Default budget allocation by source
    DEFAULT_BUDGET_ALLOCATION = {
        ContextSource.USER_SELECTION: 0.30,
        ContextSource.VECTOR_SEARCH: 0.25,
        ContextSource.WORLD_BIBLE: 0.20,
        ContextSource.GRAPH_TRAVERSAL: 0.15,
        ContextSource.KEYWORD_SEARCH: 0.05,
        ContextSource.RECENT_EDITS: 0.05,
    }
    
    def __init__(
        self,
        max_tokens: int = CONTEXT_WINDOW_LIMIT,
        budget_allocation: Dict[ContextSource, float] = None
    ):
        """
        Initialize the context assembler.
        
        Args:
            max_tokens: Maximum tokens for context
            budget_allocation: Token budget per source
        """
        self.max_tokens = max_tokens
        self.budget_allocation = budget_allocation or self.DEFAULT_BUDGET_ALLOCATION
        self._seen_ids: set = set()
    
    def assemble(
        self,
        items_by_source: Dict[ContextSource, List[ContextItem]],
        required_items: List[ContextItem] = None
    ) -> AssembledContext:
        """
        Assemble context from multiple sources.
        
        Args:
            items_by_source: Items grouped by source
            required_items: Items that must be included
            
        Returns:
            AssembledContext with selected items
        """
        self._seen_ids.clear()
        selected_items = []
        total_tokens = 0
        truncated = False
        
        # First, add required items
        if required_items:
            for item in required_items:
                if self._can_add(item, total_tokens):
                    selected_items.append(item)
                    total_tokens += item.token_count
                    self._seen_ids.add(item.id)
        
        # Then, add items by source priority
        for source in self._get_source_priority():
            if source not in items_by_source:
                continue
            
            source_budget = int(self.max_tokens * self.budget_allocation.get(source, 0.1))
            source_tokens = 0
            
            # Sort by relevance
            source_items = sorted(
                items_by_source[source],
                key=lambda x: x.relevance_score,
                reverse=True
            )
            
            for item in source_items:
                if item.id in self._seen_ids:
                    continue
                
                if source_tokens + item.token_count > source_budget:
                    continue
                
                if not self._can_add(item, total_tokens):
                    truncated = True
                    continue
                
                selected_items.append(item)
                total_tokens += item.token_count
                source_tokens += item.token_count
                self._seen_ids.add(item.id)
        
        sources_used = list(set(item.source for item in selected_items))
        
        logger.info(
            f"Assembled context: {len(selected_items)} items, "
            f"{total_tokens} tokens, {len(sources_used)} sources"
        )
        
        return AssembledContext(
            items=selected_items,
            total_tokens=total_tokens,
            budget_used=total_tokens / self.max_tokens,
            sources_used=sources_used,
            truncated=truncated
        )
    
    def _can_add(self, item: ContextItem, current_tokens: int) -> bool:
        """Check if an item can be added within budget."""
        return current_tokens + item.token_count <= self.max_tokens
    
    def _get_source_priority(self) -> List[ContextSource]:
        """Get sources in priority order."""
        return sorted(
            self.budget_allocation.keys(),
            key=lambda s: self.budget_allocation[s],
            reverse=True
        )
    
    def create_item(
        self,
        id: str,
        content: str,
        source: ContextSource,
        relevance_score: float = 1.0,
        **metadata
    ) -> ContextItem:
        """Create a context item."""
        return ContextItem(
            id=id,
            content=content,
            source=source,
            relevance_score=relevance_score,
            metadata=metadata
        )
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return count_tokens_estimate(text)
    
    def get_remaining_budget(self, current_tokens: int) -> int:
        """Get remaining token budget."""
        return max(0, self.max_tokens - current_tokens)

    def set_budget_allocation(self, allocation: Dict[ContextSource, float]) -> None:
        """Update budget allocation."""
        self.budget_allocation = allocation

    def get_budget_allocation(self) -> Dict[ContextSource, float]:
        """Get current budget allocation."""
        return self.budget_allocation.copy()


# =========================================================================
# PIPELINE/AGENT-SPECIFIC BUDGET CONFIGURATIONS
# =========================================================================

class BudgetProfile:
    """Pre-configured budget profiles for different pipeline/agent types."""

    # Story Pipeline profiles
    STORY_BRAINSTORM = {
        ContextSource.USER_SELECTION: 0.35,
        ContextSource.WORLD_BIBLE: 0.30,
        ContextSource.VECTOR_SEARCH: 0.15,
        ContextSource.RELATIONSHIP: 0.10,
        ContextSource.KEYWORD_SEARCH: 0.05,
        ContextSource.RECENT_EDITS: 0.05,
    }

    STORY_OUTLINE = {
        ContextSource.USER_SELECTION: 0.25,
        ContextSource.WORLD_BIBLE: 0.25,
        ContextSource.VECTOR_SEARCH: 0.20,
        ContextSource.FOCAL_ENTITY: 0.15,
        ContextSource.RELATIONSHIP: 0.10,
        ContextSource.KEYWORD_SEARCH: 0.05,
    }

    STORY_PROSE = {
        ContextSource.FOCAL_ENTITY: 0.30,
        ContextSource.USER_SELECTION: 0.20,
        ContextSource.RELATIONSHIP: 0.20,
        ContextSource.WORLD_BIBLE: 0.15,
        ContextSource.VECTOR_SEARCH: 0.10,
        ContextSource.RECENT_EDITS: 0.05,
    }

    # Director Pipeline profiles
    DIRECTOR_SCENE = {
        ContextSource.FOCAL_ENTITY: 0.35,
        ContextSource.WORLD_BIBLE: 0.25,
        ContextSource.USER_SELECTION: 0.20,
        ContextSource.VECTOR_SEARCH: 0.10,
        ContextSource.RELATIONSHIP: 0.10,
    }

    DIRECTOR_FRAME = {
        ContextSource.FOCAL_ENTITY: 0.40,
        ContextSource.WORLD_BIBLE: 0.25,
        ContextSource.USER_SELECTION: 0.15,
        ContextSource.RECENT_EDITS: 0.15,
        ContextSource.VECTOR_SEARCH: 0.05,
    }

    # Dialogue profiles
    DIALOGUE = {
        ContextSource.FOCAL_ENTITY: 0.30,
        ContextSource.RELATIONSHIP: 0.30,
        ContextSource.WORLD_BIBLE: 0.20,
        ContextSource.USER_SELECTION: 0.10,
        ContextSource.VECTOR_SEARCH: 0.10,
    }

    # Character embodiment
    CHARACTER_EMBODIMENT = {
        ContextSource.FOCAL_ENTITY: 0.40,
        ContextSource.RELATIONSHIP: 0.25,
        ContextSource.WORLD_BIBLE: 0.20,
        ContextSource.USER_SELECTION: 0.10,
        ContextSource.VECTOR_SEARCH: 0.05,
    }

    # Default fallback
    DEFAULT = ContextAssembler.DEFAULT_BUDGET_ALLOCATION

    @classmethod
    def get_profile(cls, profile_name: str) -> Dict[ContextSource, float]:
        """Get a budget profile by name."""
        profiles = {
            "story_brainstorm": cls.STORY_BRAINSTORM,
            "story_outline": cls.STORY_OUTLINE,
            "story_prose": cls.STORY_PROSE,
            "director_scene": cls.DIRECTOR_SCENE,
            "director_frame": cls.DIRECTOR_FRAME,
            "dialogue": cls.DIALOGUE,
            "character_embodiment": cls.CHARACTER_EMBODIMENT,
            "default": cls.DEFAULT,
        }
        return profiles.get(profile_name.lower(), cls.DEFAULT)

    @classmethod
    def list_profiles(cls) -> List[str]:
        """List available profile names."""
        return [
            "story_brainstorm", "story_outline", "story_prose",
            "director_scene", "director_frame", "dialogue",
            "character_embodiment", "default"
        ]


# =========================================================================
# RELATIONSHIP CONTEXT BUILDER
# =========================================================================

@dataclass
class RelationshipContext:
    """Relationship context between entities."""
    source_tag: str
    target_tag: str
    relationship_type: str  # e.g., "rival", "mentor", "lover"
    description: str
    dynamics: str = ""  # Power dynamics, tension, etc.
    history: str = ""  # Shared history
    current_state: str = ""  # Current relationship state

    def to_context_string(self) -> str:
        """Convert to context string."""
        parts = [f"[{self.source_tag}] → [{self.target_tag}]: {self.relationship_type}"]
        if self.description:
            parts.append(f"  {self.description}")
        if self.dynamics:
            parts.append(f"  Dynamics: {self.dynamics}")
        if self.current_state:
            parts.append(f"  Current: {self.current_state}")
        return "\n".join(parts)


class RelationshipContextBuilder:
    """
    Builds relationship context from world_config.

    Surfaces relevant relationships when characters appear together in scenes.
    """

    def __init__(self, world_config: Dict[str, Any] = None):
        """Initialize with world config."""
        self.world_config = world_config or {}
        self._relationship_cache: Dict[Tuple[str, str], RelationshipContext] = {}
        self._build_cache()

    def _build_cache(self) -> None:
        """Build relationship cache from world_config."""
        for char in self.world_config.get("characters", []):
            char_tag = char.get("tag", "")
            if not char_tag:
                continue

            relationships = char.get("relationships", {})
            if isinstance(relationships, dict):
                for target_tag, rel_data in relationships.items():
                    if isinstance(rel_data, str):
                        rel_type = rel_data
                        description = ""
                    elif isinstance(rel_data, dict):
                        rel_type = rel_data.get("type", "related")
                        description = rel_data.get("description", "")
                    else:
                        continue

                    self._relationship_cache[(char_tag, target_tag)] = RelationshipContext(
                        source_tag=char_tag,
                        target_tag=target_tag,
                        relationship_type=rel_type,
                        description=description,
                        dynamics=rel_data.get("dynamics", "") if isinstance(rel_data, dict) else "",
                        history=rel_data.get("history", "") if isinstance(rel_data, dict) else "",
                        current_state=rel_data.get("current_state", "") if isinstance(rel_data, dict) else ""
                    )

    def get_relationship(self, char1: str, char2: str) -> Optional[RelationshipContext]:
        """Get relationship between two characters."""
        # Check both directions
        if (char1, char2) in self._relationship_cache:
            return self._relationship_cache[(char1, char2)]
        if (char2, char1) in self._relationship_cache:
            return self._relationship_cache[(char2, char1)]
        return None

    def get_relationships_for_character(self, char_tag: str) -> List[RelationshipContext]:
        """Get all relationships for a character."""
        return [
            rel for (source, _), rel in self._relationship_cache.items()
            if source == char_tag
        ]

    def get_relationships_for_scene(self, character_tags: List[str]) -> List[RelationshipContext]:
        """Get all relevant relationships for characters in a scene."""
        relationships = []
        seen_pairs = set()

        for i, char1 in enumerate(character_tags):
            for char2 in character_tags[i+1:]:
                pair = tuple(sorted([char1, char2]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                rel = self.get_relationship(char1, char2)
                if rel:
                    relationships.append(rel)

        return relationships

    def build_relationship_context(
        self,
        character_tags: List[str],
        focal_character: str = None
    ) -> str:
        """
        Build relationship context string for characters.

        Args:
            character_tags: Characters in scene
            focal_character: Primary character (gets more detail)

        Returns:
            Formatted relationship context string
        """
        relationships = self.get_relationships_for_scene(character_tags)

        if not relationships:
            return ""

        parts = ["=== CHARACTER RELATIONSHIPS ==="]

        # Prioritize focal character relationships
        if focal_character:
            focal_rels = [r for r in relationships if r.source_tag == focal_character or r.target_tag == focal_character]
            other_rels = [r for r in relationships if r not in focal_rels]

            if focal_rels:
                parts.append(f"\n[{focal_character}] Relationships:")
                for rel in focal_rels:
                    parts.append(rel.to_context_string())

            if other_rels:
                parts.append("\nOther Relationships:")
                for rel in other_rels:
                    parts.append(f"  {rel.source_tag} ↔ {rel.target_tag}: {rel.relationship_type}")
        else:
            for rel in relationships:
                parts.append(rel.to_context_string())

        return "\n".join(parts)

    def to_context_items(
        self,
        character_tags: List[str],
        focal_character: str = None
    ) -> List[ContextItem]:
        """Convert relationships to ContextItems for assembly."""
        relationships = self.get_relationships_for_scene(character_tags)
        items = []

        for rel in relationships:
            # Higher relevance for focal character relationships
            relevance = 1.0
            if focal_character:
                if rel.source_tag == focal_character or rel.target_tag == focal_character:
                    relevance = 1.5

            items.append(ContextItem(
                id=f"rel_{rel.source_tag}_{rel.target_tag}",
                content=rel.to_context_string(),
                source=ContextSource.RELATIONSHIP,
                relevance_score=relevance,
                metadata={
                    "source_tag": rel.source_tag,
                    "target_tag": rel.target_tag,
                    "relationship_type": rel.relationship_type
                }
            ))

        return items


# =========================================================================
# ATTENTION-WEIGHTED CONTEXT PRIORITY
# =========================================================================

class AttentionWeightedAssembler(ContextAssembler):
    """
    Extended assembler with attention-weighted priority for focal entities.

    Boosts context relevance for entities that are the "focus" of the current
    scene/frame, ensuring they get more token budget.
    """

    def __init__(
        self,
        max_tokens: int = CONTEXT_WINDOW_LIMIT,
        budget_allocation: Dict[ContextSource, float] = None,
        focal_boost: float = 1.5,
        background_penalty: float = 0.5
    ):
        """
        Initialize with attention weighting parameters.

        Args:
            max_tokens: Maximum tokens
            budget_allocation: Budget per source
            focal_boost: Relevance multiplier for focal entities
            background_penalty: Relevance multiplier for background entities
        """
        super().__init__(max_tokens, budget_allocation)
        self.focal_boost = focal_boost
        self.background_penalty = background_penalty
        self._focal_entities: Set[str] = set()
        self._background_entities: Set[str] = set()

    def set_focal_entities(self, entities: List[str]) -> None:
        """Set the focal entities for current context."""
        self._focal_entities = set(entities)

    def set_background_entities(self, entities: List[str]) -> None:
        """Set background entities (lower priority)."""
        self._background_entities = set(entities)

    def clear_attention(self) -> None:
        """Clear attention weights."""
        self._focal_entities.clear()
        self._background_entities.clear()

    def assemble_with_attention(
        self,
        items_by_source: Dict[ContextSource, List[ContextItem]],
        focal_entities: List[str] = None,
        required_items: List[ContextItem] = None
    ) -> AssembledContext:
        """
        Assemble context with attention weighting.

        Args:
            items_by_source: Items grouped by source
            focal_entities: Entities to boost
            required_items: Items that must be included

        Returns:
            AssembledContext with attention-weighted selection
        """
        if focal_entities:
            self.set_focal_entities(focal_entities)

        # Apply attention weights
        weighted_items = {}
        for source, items in items_by_source.items():
            weighted_items[source] = [
                self._apply_attention_weight(item)
                for item in items
            ]

        return self.assemble(weighted_items, required_items)

    def _apply_attention_weight(self, item: ContextItem) -> ContextItem:
        """Apply attention weight to an item."""
        # Check if item relates to focal or background entities
        item_entities = set()

        # Extract entities from item
        if "tag" in item.metadata:
            item_entities.add(item.metadata["tag"])
        if "tags" in item.metadata:
            item_entities.update(item.metadata["tags"])

        # Also check content for entity tags
        import re
        tags_in_content = re.findall(r'\[(CHAR|LOC|PROP)_([A-Z_]+)\]', item.content)
        for prefix, name in tags_in_content:
            item_entities.add(f"{prefix}_{name}")

        # Apply weights
        if item_entities & self._focal_entities:
            # Boost focal entities
            weighted_item = ContextItem(
                id=item.id,
                content=item.content,
                source=item.source,
                relevance_score=item.relevance_score * self.focal_boost,
                token_count=item.token_count,
                metadata=item.metadata
            )
            return weighted_item

        elif item_entities & self._background_entities:
            # Penalize background entities
            weighted_item = ContextItem(
                id=item.id,
                content=item.content,
                source=item.source,
                relevance_score=item.relevance_score * self.background_penalty,
                token_count=item.token_count,
                metadata=item.metadata
            )
            return weighted_item

        return item


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

def create_assembler_for_pipeline(
    pipeline_type: str,
    max_tokens: int = None
) -> ContextAssembler:
    """
    Create an assembler configured for a specific pipeline.

    Args:
        pipeline_type: Pipeline/agent type name
        max_tokens: Optional max tokens override

    Returns:
        Configured ContextAssembler
    """
    profile = BudgetProfile.get_profile(pipeline_type)
    return ContextAssembler(
        max_tokens=max_tokens or CONTEXT_WINDOW_LIMIT,
        budget_allocation=profile
    )


def create_attention_assembler(
    pipeline_type: str = "default",
    max_tokens: int = None,
    focal_boost: float = 1.5
) -> AttentionWeightedAssembler:
    """
    Create an attention-weighted assembler.

    Args:
        pipeline_type: Pipeline/agent type for budget profile
        max_tokens: Optional max tokens
        focal_boost: Boost multiplier for focal entities

    Returns:
        AttentionWeightedAssembler
    """
    profile = BudgetProfile.get_profile(pipeline_type)
    return AttentionWeightedAssembler(
        max_tokens=max_tokens or CONTEXT_WINDOW_LIMIT,
        budget_allocation=profile,
        focal_boost=focal_boost
    )


def build_relationship_context(
    world_config: Dict[str, Any],
    characters: List[str],
    focal_character: str = None
) -> str:
    """
    Build relationship context for characters.

    Args:
        world_config: World configuration
        characters: Character tags in scene
        focal_character: Primary character

    Returns:
        Formatted relationship context string
    """
    builder = RelationshipContextBuilder(world_config)
    return builder.build_relationship_context(characters, focal_character)

