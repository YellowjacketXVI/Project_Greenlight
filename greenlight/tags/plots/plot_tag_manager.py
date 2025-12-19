"""
Plot Tag Manager

Manages plot/concept tag extraction and validation.
Concepts represent thematic elements (CONCEPT_HONOR, CONCEPT_FREEDOM, etc.)
"""

from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Callable

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import TAG_CONSENSUS_THRESHOLD
from greenlight.agents.prompts import AgentPromptLibrary

logger = get_logger("tags.plots")


@dataclass
class PlotExtractionResult:
    """Result from plot/concept tag extraction."""
    concept_tags: Set[str]
    agreement_ratios: Dict[str, float]
    threshold: float
    is_consensus: bool


class PlotTagManager:
    """
    Manages plot/concept tag operations.
    
    Responsibilities:
    - Extract concept tags from narrative
    - Track thematic elements across story
    - Validate concept consistency
    
    Uses externalized prompts from:
        tags/plots/prompts/01_extraction/
    """
    
    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        threshold: float = TAG_CONSENSUS_THRESHOLD
    ):
        """
        Initialize plot tag manager.
        
        Args:
            llm_caller: Async function to call LLM
            threshold: Consensus threshold
        """
        self.llm_caller = llm_caller
        self.threshold = threshold
    
    async def extract_concept_tags(
        self,
        text: str,
        context: Optional[str] = None
    ) -> PlotExtractionResult:
        """
        Extract concept tags from text.
        
        Args:
            text: Text to extract concept tags from
            context: Optional additional context
            
        Returns:
            PlotExtractionResult with extracted tags
        """
        logger.info("Extracting concept tags")
        
        # Parse concept tags from text
        tags = self._parse_concept_tags(text)
        
        return PlotExtractionResult(
            concept_tags=tags,
            agreement_ratios={tag: 1.0 for tag in tags},
            threshold=self.threshold,
            is_consensus=True
        )
    
    def _parse_concept_tags(self, text: str) -> Set[str]:
        """Parse concept tags from text."""
        import re
        pattern = r'\[?(CONCEPT_[A-Z0-9_]+)\]?'
        matches = re.findall(pattern, text.upper())
        placeholders = {'CONCEPT_NAME', 'CONCEPT_TAG_NAME'}
        return {tag for tag in matches if tag not in placeholders}

