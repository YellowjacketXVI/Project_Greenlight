"""
Event Tag Manager

Manages event tag extraction and validation.
Events represent significant story moments (EVENT_WEDDING, EVENT_BATTLE, etc.)
"""

from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Callable

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import TAG_CONSENSUS_THRESHOLD
from greenlight.agents.prompts import AgentPromptLibrary

logger = get_logger("tags.events")


@dataclass
class EventExtractionResult:
    """Result from event tag extraction."""
    event_tags: Set[str]
    agreement_ratios: Dict[str, float]
    threshold: float
    is_consensus: bool


class EventTagManager:
    """
    Manages event tag operations.
    
    Responsibilities:
    - Extract event tags from narrative
    - Validate event tags against story structure
    - Track event sequences
    
    Uses externalized prompts from:
        tags/events/prompts/01_extraction/
    """
    
    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        threshold: float = TAG_CONSENSUS_THRESHOLD
    ):
        """
        Initialize event tag manager.
        
        Args:
            llm_caller: Async function to call LLM
            threshold: Consensus threshold
        """
        self.llm_caller = llm_caller
        self.threshold = threshold
    
    async def extract_event_tags(
        self,
        text: str,
        context: Optional[str] = None
    ) -> EventExtractionResult:
        """
        Extract event tags from text.
        
        Args:
            text: Text to extract event tags from
            context: Optional additional context
            
        Returns:
            EventExtractionResult with extracted tags
        """
        logger.info("Extracting event tags")
        
        # Parse event tags from text
        tags = self._parse_event_tags(text)
        
        return EventExtractionResult(
            event_tags=tags,
            agreement_ratios={tag: 1.0 for tag in tags},
            threshold=self.threshold,
            is_consensus=True
        )
    
    def _parse_event_tags(self, text: str) -> Set[str]:
        """Parse event tags from text."""
        import re
        pattern = r'\[?(EVENT_[A-Z0-9_]+)\]?'
        matches = re.findall(pattern, text.upper())
        placeholders = {'EVENT_NAME', 'EVENT_TAG_NAME'}
        return {tag for tag in matches if tag not in placeholders}

