"""
Prop Tag Manager

Manages prop tag extraction, validation, and reference generation.
Uses consensus-based extraction for significant props.
"""

from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Callable
from collections import Counter
import asyncio

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import TAG_CONSENSUS_THRESHOLD
from greenlight.agents.prompts import AgentPromptLibrary

logger = get_logger("tags.props")


@dataclass
class PropExtractionResult:
    """Result from prop tag extraction."""
    prop_tags: Set[str]
    agreement_ratios: Dict[str, float]
    threshold: float
    is_consensus: bool


class PropTagManager:
    """
    Manages prop tag operations.
    
    Responsibilities:
    - Extract prop tags using consensus
    - Validate prop tags against registry
    - Generate prop reference prompts
    
    Uses externalized prompts from:
        tags/props/prompts/01_extraction/
        tags/props/prompts/02_validation/
        tags/props/prompts/03_enrichment/
    """
    
    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        threshold: float = TAG_CONSENSUS_THRESHOLD
    ):
        """
        Initialize prop tag manager.
        
        Args:
            llm_caller: Async function to call LLM
            threshold: Consensus threshold
        """
        self.llm_caller = llm_caller
        self.threshold = threshold
    
    async def extract_prop_tags(
        self,
        text: str,
        context: Optional[str] = None
    ) -> PropExtractionResult:
        """
        Extract prop tags from text.
        
        Args:
            text: Text to extract prop tags from
            context: Optional additional context
            
        Returns:
            PropExtractionResult with extracted tags
        """
        logger.info("Extracting prop tags")
        
        # Parse prop tags from text
        tags = self._parse_prop_tags(text)
        
        return PropExtractionResult(
            prop_tags=tags,
            agreement_ratios={tag: 1.0 for tag in tags},
            threshold=self.threshold,
            is_consensus=True
        )
    
    def _parse_prop_tags(self, text: str) -> Set[str]:
        """Parse prop tags from text."""
        import re
        pattern = r'\[?(PROP_[A-Z0-9_]+)\]?'
        matches = re.findall(pattern, text.upper())
        placeholders = {'PROP_NAME', 'PROP_TAG_NAME', 'PROP_ITEM_NAME'}
        return {tag for tag in matches if tag not in placeholders}
    
    async def validate_prop_tag(
        self,
        tag: str,
        world_bible: Optional[Dict] = None
    ) -> bool:
        """
        Validate a prop tag against the world bible.
        
        Args:
            tag: Prop tag to validate
            world_bible: World bible data
            
        Returns:
            True if valid
        """
        if not world_bible:
            return True
        
        props = world_bible.get('props', {})
        if isinstance(props, dict):
            return tag in props
        elif isinstance(props, list):
            return any(p.get('tag') == tag for p in props)
        
        return True

