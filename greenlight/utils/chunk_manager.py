"""
Greenlight Chunk Manager

Text chunking utilities for processing large documents with overlap.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import re


@dataclass
class Chunk:
    """Represents a chunk of text with metadata."""
    id: str
    content: str
    start_index: int
    end_index: int
    metadata: dict = field(default_factory=dict)
    
    @property
    def length(self) -> int:
        """Get the length of the chunk content."""
        return len(self.content)
    
    def contains_position(self, position: int) -> bool:
        """Check if a position falls within this chunk."""
        return self.start_index <= position < self.end_index


class ChunkManager:
    """
    Manages text chunking with configurable size and overlap.
    
    Supports:
    - Fixed-size chunking with overlap
    - Sentence-aware chunking
    - Paragraph-aware chunking
    """
    
    def __init__(
        self,
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
        respect_sentences: bool = True
    ):
        """
        Initialize the chunk manager.
        
        Args:
            chunk_size: Target size for each chunk
            chunk_overlap: Overlap between consecutive chunks
            respect_sentences: If True, try to break at sentence boundaries
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.respect_sentences = respect_sentences
    
    def chunk_text(
        self,
        text: str,
        id_prefix: str = "chunk"
    ) -> List[Chunk]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to chunk
            id_prefix: Prefix for chunk IDs
            
        Returns:
            List of Chunk objects
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        chunk_num = 0
        
        while start < len(text):
            # Calculate end position
            end = min(start + self.chunk_size, len(text))
            
            # Adjust to sentence boundary if enabled
            if self.respect_sentences and end < len(text):
                end = self._find_sentence_boundary(text, start, end)
            
            # Extract chunk content
            content = text[start:end]
            
            # Create chunk
            chunk = Chunk(
                id=f"{id_prefix}_{chunk_num:04d}",
                content=content,
                start_index=start,
                end_index=end
            )
            chunks.append(chunk)
            
            # Move to next position with overlap
            start = end - self.chunk_overlap
            if start >= len(text) - self.chunk_overlap:
                break
            chunk_num += 1
        
        return chunks
    
    def _find_sentence_boundary(
        self,
        text: str,
        start: int,
        target_end: int
    ) -> int:
        """
        Find the nearest sentence boundary before target_end.
        
        Args:
            text: Full text
            start: Start of current chunk
            target_end: Target end position
            
        Returns:
            Adjusted end position at sentence boundary
        """
        # Look for sentence endings in the last portion of the chunk
        search_start = max(start, target_end - 200)
        search_text = text[search_start:target_end]
        
        # Find last sentence ending
        matches = list(re.finditer(r'[.!?]\s+', search_text))
        
        if matches:
            # Use the last sentence boundary found
            last_match = matches[-1]
            return search_start + last_match.end()
        
        # No sentence boundary found, use target_end
        return target_end
    
    def chunk_by_paragraphs(
        self,
        text: str,
        id_prefix: str = "para"
    ) -> List[Chunk]:
        """
        Split text into chunks by paragraphs.
        
        Args:
            text: Text to chunk
            id_prefix: Prefix for chunk IDs
            
        Returns:
            List of Chunk objects
        """
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        current_pos = 0
        
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue
            
            # Find actual position in original text
            start = text.find(para, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(para)
            
            chunk = Chunk(
                id=f"{id_prefix}_{i:04d}",
                content=para,
                start_index=start,
                end_index=end
            )
            chunks.append(chunk)
            current_pos = end
        
        return chunks
    
    def merge_chunks(
        self,
        chunks: List[Chunk],
        max_size: int = None
    ) -> List[Chunk]:
        """
        Merge small consecutive chunks up to max_size.
        
        Args:
            chunks: List of chunks to merge
            max_size: Maximum size for merged chunks
            
        Returns:
            List of merged chunks
        """
        if not chunks:
            return []
        
        max_size = max_size or self.chunk_size
        merged = []
        current = chunks[0]
        
        for chunk in chunks[1:]:
            combined_length = current.length + chunk.length
            
            if combined_length <= max_size:
                # Merge chunks
                current = Chunk(
                    id=current.id,
                    content=current.content + "\n\n" + chunk.content,
                    start_index=current.start_index,
                    end_index=chunk.end_index
                )
            else:
                merged.append(current)
                current = chunk
        
        merged.append(current)
        return merged
    
    def get_chunk_at_position(
        self,
        chunks: List[Chunk],
        position: int
    ) -> Optional[Chunk]:
        """
        Find the chunk containing a specific position.
        
        Args:
            chunks: List of chunks
            position: Position to find
            
        Returns:
            Chunk containing the position, or None
        """
        for chunk in chunks:
            if chunk.contains_position(position):
                return chunk
        return None

