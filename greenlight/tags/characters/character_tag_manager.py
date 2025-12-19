"""
Character Tag Manager

Manages character tag extraction, validation, and reference generation.
Uses 5-agent consensus with 80% threshold for character tag extraction.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Callable, Any
from collections import Counter
import asyncio

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import TAG_CONSENSUS_THRESHOLD
from greenlight.agents.prompts import AgentPromptLibrary

# Note: PromptLoader is available for future use when prompts are externalized
# from greenlight.core.prompt_loader import PromptLoader

logger = get_logger("tags.characters")


@dataclass
class CharacterExtractionResult:
    """Result from character tag extraction."""
    character_tags: Set[str]
    agreement_ratios: Dict[str, float]
    threshold: float
    is_consensus: bool


class CharacterTagManager:
    """
    Manages character tag operations.
    
    Responsibilities:
    - Extract character tags using 5-agent consensus (80% threshold)
    - Validate character tags against registry
    - Generate character reference prompts
    
    Uses externalized prompts from:
        tags/characters/prompts/01_extraction/
        tags/characters/prompts/02_validation/
        tags/characters/prompts/03_enrichment/
    """
    
    # Agent perspectives for character extraction
    AGENT_PERSPECTIVES = [
        ("narrative", "story_critical"),
        ("visual", "visual_anchors"),
        ("character", "character_defining"),
        ("technical", "landmark_locations"),
        ("holistic", "world_building"),
    ]
    
    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        threshold: float = TAG_CONSENSUS_THRESHOLD
    ):
        """
        Initialize character tag manager.
        
        Args:
            llm_caller: Async function to call LLM for extraction
            threshold: Consensus threshold (default: 0.8 = 80%)
        """
        self.llm_caller = llm_caller
        self.threshold = threshold
        self.num_agents = len(self.AGENT_PERSPECTIVES)
    
    async def extract_character_tags(
        self,
        text: str,
        context: Optional[str] = None
    ) -> CharacterExtractionResult:
        """
        Extract character tags using multi-agent consensus.
        
        Args:
            text: Text to extract character tags from
            context: Optional additional context
            
        Returns:
            CharacterExtractionResult with consensus tags
        """
        logger.info(f"Starting character tag extraction with {self.num_agents} agents")
        
        if not self.llm_caller:
            # Fallback to simple regex extraction
            return self._fallback_extraction(text)
        
        # Run all agents in parallel
        tasks = [
            self._run_agent(perspective, prompt_key, text, context)
            for perspective, prompt_key in self.AGENT_PERSPECTIVES
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect valid extractions
        extractions = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Agent {self.AGENT_PERSPECTIVES[i][0]} failed: {result}")
            else:
                extractions.append(result)
        
        return self._calculate_consensus(extractions)
    
    async def _run_agent(
        self,
        perspective: str,
        prompt_key: str,
        text: str,
        context: Optional[str]
    ) -> Set[str]:
        """Run a single extraction agent."""
        logger.debug(f"Running character extraction agent: {perspective}")
        
        # Get prompt from AgentPromptLibrary
        prompts = AgentPromptLibrary.get_tag_validation_prompts()
        template = prompts.get(prompt_key, prompts["story_critical"])
        
        # Build source text
        source_text = text
        if context:
            source_text = f"Context: {context}\n\n{text}"
        
        # Render prompt
        prompt = AgentPromptLibrary.render(
            template,
            source_text=source_text,
            naming_rules=AgentPromptLibrary.TAG_NAMING_RULES
        )
        
        response = await self.llm_caller(prompt)
        
        # Extract character tags (CHAR_ prefix)
        return self._parse_character_tags(response)
    
    def _parse_character_tags(self, response: str) -> Set[str]:
        """Parse character tags from LLM response."""
        import re
        
        # Find all tags with CHAR_ prefix
        pattern = r'\[?(CHAR_[A-Z0-9_]+)\]?'
        matches = re.findall(pattern, response.upper())
        
        # Filter out placeholder patterns
        placeholders = {'CHAR_NAME', 'CHAR_TAG_NAME', 'CHAR_FIRSTNAME', 'CHAR_FIRSTNAME_LASTNAME'}
        return {tag for tag in matches if tag not in placeholders}
    
    def _calculate_consensus(self, extractions: List[Set[str]]) -> CharacterExtractionResult:
        """Calculate consensus from multiple extractions."""
        if not extractions:
            return CharacterExtractionResult(
                character_tags=set(),
                agreement_ratios={},
                threshold=self.threshold,
                is_consensus=False
            )
        
        # Count tag occurrences
        tag_counts = Counter()
        for extraction in extractions:
            for tag in extraction:
                tag_counts[tag] += 1
        
        # Calculate agreement ratios
        num_agents = len(extractions)
        agreement_ratios = {tag: count / num_agents for tag, count in tag_counts.items()}
        
        # Get consensus tags
        consensus_tags = {tag for tag, ratio in agreement_ratios.items() if ratio >= self.threshold}
        
        logger.info(f"Character consensus: {len(consensus_tags)} tags accepted")
        
        return CharacterExtractionResult(
            character_tags=consensus_tags,
            agreement_ratios=agreement_ratios,
            threshold=self.threshold,
            is_consensus=len(consensus_tags) > 0
        )
    
    def _fallback_extraction(self, text: str) -> CharacterExtractionResult:
        """Fallback extraction without LLM."""
        tags = self._parse_character_tags(text)
        return CharacterExtractionResult(
            character_tags=tags,
            agreement_ratios={tag: 1.0 for tag in tags},
            threshold=self.threshold,
            is_consensus=True
        )

