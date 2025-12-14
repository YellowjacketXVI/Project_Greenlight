"""
Greenlight Consensus Tagger

Multi-agent tag extraction with consensus validation.
Runs 5 parallel extraction passes and requires 80% agreement.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Callable, Any
from collections import Counter
import asyncio

from greenlight.core.constants import TAG_CONSENSUS_THRESHOLD
from greenlight.core.exceptions import TagConsensusError
from greenlight.core.logging_config import get_logger
from greenlight.agents.prompts import AgentPromptLibrary
from .tag_parser import TagParser, ParsedTag
from .tag_registry import TagRegistry

logger = get_logger("tags.consensus")


@dataclass
class AgentExtraction:
    """Result from a single agent's tag extraction."""
    agent_id: str
    tags: Set[str]
    confidence: float = 1.0
    reasoning: Optional[str] = None


@dataclass
class ConsensusResult:
    """Result of consensus tag extraction."""
    consensus_tags: Set[str]          # Tags that reached consensus
    rejected_tags: Set[str]           # Tags that didn't reach consensus
    all_extractions: List[AgentExtraction]
    agreement_ratios: Dict[str, float]  # tag -> agreement ratio
    threshold: float
    
    @property
    def is_unanimous(self) -> bool:
        """Check if all agents agreed on all tags."""
        return len(self.rejected_tags) == 0
    
    def get_tag_agreement(self, tag: str) -> float:
        """Get agreement ratio for a specific tag."""
        return self.agreement_ratios.get(tag, 0.0)


class ConsensusTagger:
    """
    Multi-agent tag extraction with consensus validation.
    
    Process:
    1. Run 5 parallel extraction agents with different perspectives
    2. Collect all extracted tags
    3. Calculate agreement ratio for each tag
    4. Accept tags with >= 80% agreement (4/5 agents)
    
    Agent Perspectives:
    - Narrative Focus: Story elements and plot points
    - Visual Focus: Visual descriptions and imagery
    - Character Focus: Character mentions and relationships
    - Technical Focus: Props, locations, technical elements
    - Holistic Focus: Overall context and themes
    """
    
    AGENT_PERSPECTIVES = [
        "narrative",
        "visual", 
        "character",
        "technical",
        "holistic"
    ]
    
    def __init__(
        self,
        registry: TagRegistry,
        threshold: float = TAG_CONSENSUS_THRESHOLD,
        llm_caller: Optional[Callable] = None
    ):
        """
        Initialize consensus tagger.
        
        Args:
            registry: Tag registry for validation
            threshold: Consensus threshold (default: 0.8 = 80%)
            llm_caller: Optional async function to call LLM for extraction
        """
        self.registry = registry
        self.threshold = threshold
        self.llm_caller = llm_caller
        self.parser = TagParser()
        self.num_agents = len(self.AGENT_PERSPECTIVES)
    
    async def extract_with_consensus(
        self,
        text: str,
        context: Optional[str] = None
    ) -> ConsensusResult:
        """
        Extract tags using multi-agent consensus.
        
        Args:
            text: Text to extract tags from
            context: Optional additional context
            
        Returns:
            ConsensusResult with consensus and rejected tags
        """
        logger.info(f"Starting consensus extraction with {self.num_agents} agents")
        
        # Run all agents in parallel
        if self.llm_caller:
            extractions = await self._run_llm_agents(text, context)
        else:
            # Fallback to simple parsing (no LLM)
            extractions = self._run_simple_extraction(text)
        
        # Calculate consensus
        return self._calculate_consensus(extractions)
    
    async def _run_llm_agents(
        self,
        text: str,
        context: Optional[str]
    ) -> List[AgentExtraction]:
        """Run LLM-based extraction agents in parallel."""
        tasks = []
        
        for perspective in self.AGENT_PERSPECTIVES:
            task = self._run_single_agent(perspective, text, context)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        extractions = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Agent {self.AGENT_PERSPECTIVES[i]} failed: {result}")
                continue
            extractions.append(result)
        
        return extractions
    
    def _normalize_tag(self, tag: str) -> str:
        """Normalize a tag to ensure consistent format for consensus matching."""
        # Convert to uppercase
        normalized = tag.upper()
        # Replace spaces and hyphens with underscores
        normalized = normalized.replace(' ', '_').replace('-', '_')
        # Remove any double underscores
        while '__' in normalized:
            normalized = normalized.replace('__', '_')
        # Strip leading/trailing underscores
        normalized = normalized.strip('_')
        return normalized

    async def _run_single_agent(
        self,
        perspective: str,
        text: str,
        context: Optional[str]
    ) -> AgentExtraction:
        """Run a single extraction agent."""
        logger.info(f"🤖 Agent [{perspective}] starting extraction...")
        prompt = self._build_extraction_prompt(perspective, text, context)

        # Call LLM
        response = await self.llm_caller(prompt)
        logger.debug(f"Agent [{perspective}] raw response:\n{response[:300]}...")

        # Parse response for tags and normalize them
        raw_tags = self.parser.extract_unique_tags(response)
        normalized_tags = {self._normalize_tag(tag) for tag in raw_tags}

        # Filter out empty tags and placeholder patterns
        placeholder_patterns = {
            'CHARACTER_NAME', 'LOC_NAME', 'PROP_NAME', 'TAG_NAME',
            'CHAR_TAG_NAME', 'LOC_TAG_NAME', 'PROP_TAG_NAME',
            'CONCEPT_TAG_NAME', 'EVENT_TAG_NAME',
            'CHAR_NAME', 'CHAR_FIRSTNAME', 'CHAR_FIRSTNAME_LASTNAME',
            'LOC_SPECIFIC_PLACE_NAME', 'PROP_DESCRIPTIVE_ITEM_NAME',
            'CONCEPT_THEME_NAME', 'EVENT_SPECIFIC_OCCURRENCE'
        }
        filtered_tags = {
            tag for tag in normalized_tags
            if tag and tag not in placeholder_patterns
        }

        logger.info(f"✓ Agent [{perspective}] extracted {len(filtered_tags)} tags: {', '.join(sorted(filtered_tags)[:10])}")

        return AgentExtraction(
            agent_id=perspective,
            tags=filtered_tags,
            reasoning=response[:500]  # Store first 500 chars of reasoning
        )
    
    def _run_simple_extraction(self, text: str) -> List[AgentExtraction]:
        """Simple extraction without LLM (for testing/fallback)."""
        tags = self.parser.extract_unique_tags(text)
        
        # Simulate 5 agents all finding the same tags
        return [
            AgentExtraction(
                agent_id=perspective,
                tags=tags.copy()
            )
            for perspective in self.AGENT_PERSPECTIVES
        ]
    
    def _calculate_consensus(
        self,
        extractions: List[AgentExtraction]
    ) -> ConsensusResult:
        """Calculate consensus from multiple extractions."""
        if not extractions:
            return ConsensusResult(
                consensus_tags=set(),
                rejected_tags=set(),
                all_extractions=[],
                agreement_ratios={},
                threshold=self.threshold
            )
        
        # Count tag occurrences
        tag_counts = Counter()
        for extraction in extractions:
            for tag in extraction.tags:
                tag_counts[tag] += 1
        
        # Calculate agreement ratios
        num_agents = len(extractions)
        agreement_ratios = {
            tag: count / num_agents
            for tag, count in tag_counts.items()
        }
        
        # Separate consensus and rejected tags
        consensus_tags = {
            tag for tag, ratio in agreement_ratios.items()
            if ratio >= self.threshold
        }
        rejected_tags = {
            tag for tag, ratio in agreement_ratios.items()
            if ratio < self.threshold
        }

        logger.info(
            f"📊 Consensus Results: {len(consensus_tags)} accepted, "
            f"{len(rejected_tags)} rejected (threshold: {self.threshold*100}%)"
        )

        # Log detailed breakdown
        if consensus_tags:
            logger.info(f"✅ Accepted tags ({len(consensus_tags)}):")
            for tag in sorted(consensus_tags):
                ratio = agreement_ratios[tag]
                logger.info(f"   • {tag}: {ratio*100:.0f}% ({int(ratio*num_agents)}/{num_agents} agents)")

        if rejected_tags:
            logger.info(f"❌ Rejected tags ({len(rejected_tags)}):")
            for tag in sorted(rejected_tags)[:20]:  # Show first 20
                ratio = agreement_ratios[tag]
                logger.info(f"   • {tag}: {ratio*100:.0f}% ({int(ratio*num_agents)}/{num_agents} agents)")
            if len(rejected_tags) > 20:
                logger.info(f"   ... and {len(rejected_tags) - 20} more")
        
        return ConsensusResult(
            consensus_tags=consensus_tags,
            rejected_tags=rejected_tags,
            all_extractions=extractions,
            agreement_ratios=agreement_ratios,
            threshold=self.threshold
        )
    
    def _build_extraction_prompt(
        self,
        perspective: str,
        text: str,
        context: Optional[str]
    ) -> str:
        """Build extraction prompt for a specific perspective using AgentPromptLibrary."""
        # Map perspectives to prompt templates from AgentPromptLibrary
        prompts = AgentPromptLibrary.get_tag_validation_prompts()

        perspective_to_prompt = {
            "narrative": prompts["story_critical"],
            "visual": prompts["visual_anchors"],
            "character": prompts["character_defining"],
            "technical": prompts["landmark_locations"],
            "holistic": prompts["world_building"],
        }

        template = perspective_to_prompt.get(perspective, prompts["story_critical"])

        # Add context if provided
        source_text = text
        if context:
            source_text = f"Context: {context}\n\n{text}"

        # Include naming rules in the prompt
        naming_rules = AgentPromptLibrary.TAG_NAMING_RULES

        return AgentPromptLibrary.render(
            template,
            source_text=source_text,
            naming_rules=naming_rules
        )

