"""
Greenlight Vector Store

FAISS-based vector storage for semantic search.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import numpy as np

from greenlight.core.exceptions import VectorStoreError
from greenlight.core.logging_config import get_logger

logger = get_logger("context.vector_store")


@dataclass
class VectorEntry:
    """An entry in the vector store."""
    id: str
    text: str
    embedding: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Result from a vector search."""
    id: str
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class VectorStore:
    """
    FAISS-based vector store for semantic search.
    
    Features:
    - Efficient similarity search
    - Metadata filtering
    - Persistence to disk
    - Batch operations
    """
    
    def __init__(
        self,
        dimension: int = 384,
        index_type: str = "flat"
    ):
        """
        Initialize the vector store.
        
        Args:
            dimension: Embedding dimension
            index_type: FAISS index type ("flat", "ivf", "hnsw")
        """
        self.dimension = dimension
        self.index_type = index_type
        self._index = None
        self._entries: Dict[int, VectorEntry] = {}
        self._id_to_idx: Dict[str, int] = {}
        self._next_idx = 0
        self._embedder = None
        
        self._initialize_index()
    
    def _initialize_index(self) -> None:
        """Initialize the FAISS index."""
        try:
            import faiss
            
            if self.index_type == "flat":
                self._index = faiss.IndexFlatIP(self.dimension)
            elif self.index_type == "ivf":
                quantizer = faiss.IndexFlatIP(self.dimension)
                self._index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            else:
                self._index = faiss.IndexFlatIP(self.dimension)
            
            logger.debug(f"Initialized FAISS index: {self.index_type}")
            
        except ImportError:
            logger.warning("FAISS not available, using numpy fallback")
            self._index = None
    
    def set_embedder(self, embedder) -> None:
        """Set the embedding function."""
        self._embedder = embedder
    
    def add(
        self,
        id: str,
        text: str,
        embedding: np.ndarray = None,
        **metadata
    ) -> None:
        """
        Add an entry to the store.
        
        Args:
            id: Unique identifier
            text: Text content
            embedding: Pre-computed embedding (optional)
            **metadata: Additional metadata
        """
        if embedding is None:
            if self._embedder is None:
                raise VectorStoreError("No embedder configured")
            embedding = self._embedder(text)
        
        # Normalize embedding
        embedding = embedding.astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        entry = VectorEntry(
            id=id,
            text=text,
            embedding=embedding,
            metadata=metadata
        )
        
        idx = self._next_idx
        self._entries[idx] = entry
        self._id_to_idx[id] = idx
        self._next_idx += 1
        
        # Add to FAISS index
        if self._index is not None:
            self._index.add(embedding.reshape(1, -1))
        
        logger.debug(f"Added entry: {id}")
    
    def add_batch(
        self,
        entries: List[Tuple[str, str, Dict]]
    ) -> None:
        """
        Add multiple entries.
        
        Args:
            entries: List of (id, text, metadata) tuples
        """
        for id, text, metadata in entries:
            self.add(id, text, **metadata)
    
    def search(
        self,
        query: str,
        k: int = 5,
        filter_fn: callable = None
    ) -> List[SearchResult]:
        """
        Search for similar entries.
        
        Args:
            query: Query text
            k: Number of results
            filter_fn: Optional filter function
            
        Returns:
            List of SearchResult objects
        """
        if self._embedder is None:
            raise VectorStoreError("No embedder configured")
        
        query_embedding = self._embedder(query)
        query_embedding = query_embedding.astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        return self.search_by_vector(query_embedding, k, filter_fn)
    
    def search_by_vector(
        self,
        embedding: np.ndarray,
        k: int = 5,
        filter_fn: callable = None
    ) -> List[SearchResult]:
        """Search by embedding vector."""
        if self._index is not None and len(self._entries) > 0:
            # Use FAISS
            scores, indices = self._index.search(
                embedding.reshape(1, -1),
                min(k * 2, len(self._entries))  # Get extra for filtering
            )
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx not in self._entries:
                    continue
                
                entry = self._entries[idx]
                
                if filter_fn and not filter_fn(entry):
                    continue
                
                results.append(SearchResult(
                    id=entry.id,
                    text=entry.text,
                    score=float(score),
                    metadata=entry.metadata
                ))
                
                if len(results) >= k:
                    break
            
            return results
        
        # Numpy fallback
        return self._numpy_search(embedding, k, filter_fn)
    
    def _numpy_search(
        self,
        embedding: np.ndarray,
        k: int,
        filter_fn: callable = None
    ) -> List[SearchResult]:
        """Fallback search using numpy."""
        if not self._entries:
            return []
        
        scores = []
        for idx, entry in self._entries.items():
            if filter_fn and not filter_fn(entry):
                continue
            score = np.dot(embedding, entry.embedding)
            scores.append((score, idx))
        
        scores.sort(reverse=True)
        
        results = []
        for score, idx in scores[:k]:
            entry = self._entries[idx]
            results.append(SearchResult(
                id=entry.id,
                text=entry.text,
                score=float(score),
                metadata=entry.metadata
            ))
        
        return results
    
    def get(self, id: str) -> Optional[VectorEntry]:
        """Get an entry by ID."""
        idx = self._id_to_idx.get(id)
        if idx is not None:
            return self._entries.get(idx)
        return None
    
    def delete(self, id: str) -> bool:
        """Delete an entry by ID."""
        idx = self._id_to_idx.get(id)
        if idx is not None:
            del self._entries[idx]
            del self._id_to_idx[id]
            # Note: FAISS doesn't support deletion, would need rebuild
            return True
        return False
    
    @property
    def size(self) -> int:
        """Get number of entries."""
        return len(self._entries)

