"""
Greenlight Context Assembler

Assembles context from multiple sources with token budget management.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

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

