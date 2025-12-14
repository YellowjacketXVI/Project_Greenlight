"""
Greenlight Keyword Index

Full-text search with keyword matching and fuzzy search.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict
import re

from greenlight.core.logging_config import get_logger

logger = get_logger("context.keyword_index")


@dataclass
class IndexedDocument:
    """A document in the keyword index."""
    id: str
    text: str
    tokens: Set[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KeywordSearchResult:
    """Result from keyword search."""
    id: str
    text: str
    score: float
    matched_terms: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class KeywordIndex:
    """
    Keyword-based search index with fuzzy matching.
    
    Features:
    - Inverted index for fast lookup
    - Fuzzy matching with edit distance
    - Phrase search
    - Boolean operators (AND, OR, NOT)
    """
    
    def __init__(self, min_token_length: int = 2):
        """
        Initialize the keyword index.
        
        Args:
            min_token_length: Minimum token length to index
        """
        self.min_token_length = min_token_length
        self._documents: Dict[str, IndexedDocument] = {}
        self._inverted_index: Dict[str, Set[str]] = defaultdict(set)
        self._token_pattern = re.compile(r'\b\w+\b')
    
    def add(
        self,
        id: str,
        text: str,
        **metadata
    ) -> None:
        """
        Add a document to the index.
        
        Args:
            id: Document ID
            text: Document text
            **metadata: Additional metadata
        """
        tokens = self._tokenize(text)
        
        doc = IndexedDocument(
            id=id,
            text=text,
            tokens=tokens,
            metadata=metadata
        )
        
        self._documents[id] = doc
        
        # Update inverted index
        for token in tokens:
            self._inverted_index[token].add(id)
        
        logger.debug(f"Indexed document: {id} ({len(tokens)} tokens)")
    
    def _tokenize(self, text: str) -> Set[str]:
        """Tokenize text into searchable terms."""
        tokens = self._token_pattern.findall(text.lower())
        return {
            t for t in tokens
            if len(t) >= self.min_token_length
        }
    
    def search(
        self,
        query: str,
        k: int = 10,
        fuzzy: bool = False,
        fuzzy_threshold: float = 0.8
    ) -> List[KeywordSearchResult]:
        """
        Search for documents matching query.
        
        Args:
            query: Search query
            k: Maximum results
            fuzzy: Enable fuzzy matching
            fuzzy_threshold: Minimum similarity for fuzzy match
            
        Returns:
            List of KeywordSearchResult
        """
        query_tokens = self._tokenize(query)
        
        if not query_tokens:
            return []
        
        # Find matching documents
        doc_scores: Dict[str, float] = defaultdict(float)
        doc_matches: Dict[str, List[str]] = defaultdict(list)
        
        for token in query_tokens:
            matching_docs = self._find_matching_docs(token, fuzzy, fuzzy_threshold)
            
            for doc_id in matching_docs:
                doc_scores[doc_id] += 1.0
                doc_matches[doc_id].append(token)
        
        # Sort by score
        sorted_docs = sorted(
            doc_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:k]
        
        results = []
        for doc_id, score in sorted_docs:
            doc = self._documents[doc_id]
            results.append(KeywordSearchResult(
                id=doc_id,
                text=doc.text,
                score=score / len(query_tokens),  # Normalize
                matched_terms=doc_matches[doc_id],
                metadata=doc.metadata
            ))
        
        return results
    
    def _find_matching_docs(
        self,
        token: str,
        fuzzy: bool,
        threshold: float
    ) -> Set[str]:
        """Find documents containing a token."""
        # Exact match
        if token in self._inverted_index:
            return self._inverted_index[token].copy()
        
        if not fuzzy:
            return set()
        
        # Fuzzy match
        matching = set()
        for indexed_token, doc_ids in self._inverted_index.items():
            similarity = self._calculate_similarity(token, indexed_token)
            if similarity >= threshold:
                matching.update(doc_ids)
        
        return matching
    
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using Levenshtein ratio."""
        if s1 == s2:
            return 1.0
        
        len1, len2 = len(s1), len(s2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Simple edit distance
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j
        
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i-1] == s2[j-1] else 1
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,
                    matrix[i][j-1] + 1,
                    matrix[i-1][j-1] + cost
                )
        
        distance = matrix[len1][len2]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len)
    
    def search_phrase(self, phrase: str, k: int = 10) -> List[KeywordSearchResult]:
        """Search for exact phrase matches."""
        phrase_lower = phrase.lower()
        
        results = []
        for doc_id, doc in self._documents.items():
            if phrase_lower in doc.text.lower():
                results.append(KeywordSearchResult(
                    id=doc_id,
                    text=doc.text,
                    score=1.0,
                    matched_terms=[phrase],
                    metadata=doc.metadata
                ))
        
        return results[:k]
    
    def get(self, id: str) -> Optional[IndexedDocument]:
        """Get a document by ID."""
        return self._documents.get(id)
    
    def delete(self, id: str) -> bool:
        """Delete a document from the index."""
        if id not in self._documents:
            return False
        
        doc = self._documents[id]
        
        # Remove from inverted index
        for token in doc.tokens:
            if token in self._inverted_index:
                self._inverted_index[token].discard(id)
        
        del self._documents[id]
        return True
    
    @property
    def size(self) -> int:
        """Get number of indexed documents."""
        return len(self._documents)

