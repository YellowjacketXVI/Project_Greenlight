"""
Agnostic_Core_OS OmniMind Context Engine

The core retrieval system for OmniMind - provides semantic search,
keyword search, and context assembly for connected applications.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger("agnostic_core_os.omni_mind.context")


class ContextSource(Enum):
    """Sources of context."""
    VECTOR_SEARCH = "vector_search"
    KEYWORD_SEARCH = "keyword_search"
    MEMORY = "memory"
    GRAPH = "graph"
    TAG_REGISTRY = "tag_registry"
    PIPELINE_OUTPUT = "pipeline_output"
    EXTERNAL = "external"


@dataclass
class ContextQuery:
    """A query for context retrieval."""
    query_text: str
    sources: Optional[List[ContextSource]] = None
    tags: Optional[List[str]] = None
    max_results: int = 10
    min_relevance: float = 0.0
    include_metadata: bool = True
    scope: Optional[str] = None  # e.g., "project", "world_bible", "story"


@dataclass
class ContextItem:
    """A single context item."""
    id: str
    content: str
    source: ContextSource
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ContextResult:
    """Result of a context retrieval."""
    query: ContextQuery
    items: List[ContextItem] = field(default_factory=list)
    total_found: int = 0
    sources_searched: List[ContextSource] = field(default_factory=list)
    search_time_ms: float = 0.0
    
    @property
    def assembled_context(self) -> str:
        """Get assembled context as text."""
        return "\n\n".join(item.content for item in self.items)
    
    @property
    def top_item(self) -> Optional[ContextItem]:
        """Get the most relevant item."""
        return self.items[0] if self.items else None


class ContextEngine:
    """
    Context retrieval engine for OmniMind.
    
    Features:
    - Semantic search via vector embeddings
    - Keyword search with fuzzy matching
    - Memory-based retrieval
    - Tag-aware retrieval
    - Scope-based filtering
    - Result assembly and ranking
    
    This is the core retrieval system that the RuntimeDaemon operates
    to provide context to all connected applications.
    """
    
    def __init__(
        self,
        project_path: Optional[Path] = None,
        enable_vector_search: bool = True,
        enable_keyword_search: bool = True
    ):
        """
        Initialize the context engine.
        
        Args:
            project_path: Path to the project root
            enable_vector_search: Enable semantic vector search
            enable_keyword_search: Enable keyword-based search
        """
        self.project_path = project_path
        self.enable_vector_search = enable_vector_search
        self.enable_keyword_search = enable_keyword_search
        
        # Internal stores
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._tags: Dict[str, Set[str]] = {}  # tag -> document IDs
        self._scopes: Dict[str, Set[str]] = {}  # scope -> document IDs
        self._next_id = 0
        
        logger.info(f"ContextEngine initialized (project: {project_path})")
    
    def index_document(
        self,
        content: str,
        doc_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        scope: Optional[str] = None,
        **metadata
    ) -> str:
        """
        Index a document for retrieval.
        
        Args:
            content: Document content
            doc_id: Optional document ID
            tags: Tags for the document
            scope: Scope (e.g., "world_bible", "story")
            **metadata: Additional metadata
            
        Returns:
            Document ID
        """
        if doc_id is None:
            doc_id = f"doc_{self._next_id:06d}"
            self._next_id += 1
        
        self._documents[doc_id] = {
            "id": doc_id,
            "content": content,
            "tags": tags or [],
            "scope": scope,
            "metadata": metadata,
            "indexed_at": datetime.now()
        }
        
        # Index by tags
        for tag in (tags or []):
            if tag not in self._tags:
                self._tags[tag] = set()
            self._tags[tag].add(doc_id)
        
        # Index by scope
        if scope:
            if scope not in self._scopes:
                self._scopes[scope] = set()
            self._scopes[scope].add(doc_id)
        
        logger.debug(f"Indexed document: {doc_id}")
        return doc_id
    
    def retrieve(self, query: ContextQuery) -> ContextResult:
        """
        Retrieve context for a query.

        Args:
            query: Context query

        Returns:
            ContextResult with assembled context
        """
        start_time = datetime.now()
        items: List[ContextItem] = []
        sources_searched: List[ContextSource] = []

        # Determine which sources to search
        sources = query.sources or [ContextSource.KEYWORD_SEARCH, ContextSource.MEMORY]

        # Filter by scope if specified
        candidate_ids = set(self._documents.keys())
        if query.scope and query.scope in self._scopes:
            candidate_ids = candidate_ids & self._scopes[query.scope]

        # Filter by tags if specified
        if query.tags:
            tag_ids = set()
            for tag in query.tags:
                if tag in self._tags:
                    tag_ids |= self._tags[tag]
            candidate_ids = candidate_ids & tag_ids

        # Keyword search
        if ContextSource.KEYWORD_SEARCH in sources and self.enable_keyword_search:
            sources_searched.append(ContextSource.KEYWORD_SEARCH)
            query_lower = query.query_text.lower()

            for doc_id in candidate_ids:
                doc = self._documents[doc_id]
                content_lower = doc["content"].lower()

                if query_lower in content_lower:
                    # Simple relevance: count occurrences
                    count = content_lower.count(query_lower)
                    relevance = min(1.0, count * 0.2)

                    if relevance >= query.min_relevance:
                        items.append(ContextItem(
                            id=doc_id,
                            content=doc["content"],
                            source=ContextSource.KEYWORD_SEARCH,
                            relevance_score=relevance,
                            metadata=doc.get("metadata", {})
                        ))

        # Sort by relevance
        items.sort(key=lambda x: x.relevance_score, reverse=True)
        items = items[:query.max_results]

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

        return ContextResult(
            query=query,
            items=items,
            total_found=len(items),
            sources_searched=sources_searched,
            search_time_ms=elapsed_ms
        )

    def get_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Get all documents with a specific tag."""
        doc_ids = self._tags.get(tag, set())
        return [self._documents[doc_id] for doc_id in doc_ids if doc_id in self._documents]

    def get_by_scope(self, scope: str) -> List[Dict[str, Any]]:
        """Get all documents in a specific scope."""
        doc_ids = self._scopes.get(scope, set())
        return [self._documents[doc_id] for doc_id in doc_ids if doc_id in self._documents]

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "total_documents": len(self._documents),
            "total_tags": len(self._tags),
            "total_scopes": len(self._scopes),
            "vector_search_enabled": self.enable_vector_search,
            "keyword_search_enabled": self.enable_keyword_search
        }

    def clear(self) -> None:
        """Clear all indexed documents."""
        self._documents.clear()
        self._tags.clear()
        self._scopes.clear()
        self._next_id = 0
        logger.info("Context engine cleared")

