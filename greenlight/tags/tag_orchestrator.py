"""
Tag Orchestrator

Main coordinator for all tag operations.
Delegates to type-specific tag managers and provides unified interface.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Callable, Any
import asyncio

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import TAG_CONSENSUS_THRESHOLD

from greenlight.tags.characters.character_tag_manager import CharacterTagManager, CharacterExtractionResult
from greenlight.tags.locations.location_tag_manager import LocationTagManager, LocationExtractionResult
from greenlight.tags.props.prop_tag_manager import PropTagManager, PropExtractionResult
from greenlight.tags.events.event_tag_manager import EventTagManager, EventExtractionResult
from greenlight.tags.plots.plot_tag_manager import PlotTagManager, PlotExtractionResult
from greenlight.tags.relationships.relationship_tag_manager import RelationshipTagManager, RelationshipExtractionResult

logger = get_logger("tags.orchestrator")


@dataclass
class UnifiedExtractionResult:
    """Combined result from all tag extractors."""
    characters: CharacterExtractionResult
    locations: LocationExtractionResult
    props: PropExtractionResult
    events: EventExtractionResult
    concepts: PlotExtractionResult
    relationships: RelationshipExtractionResult
    
    @property
    def all_tags(self) -> Set[str]:
        """Get all extracted tags."""
        tags = set()
        tags.update(self.characters.character_tags)
        tags.update(self.locations.location_tags)
        tags.update(self.locations.directional_tags)
        tags.update(self.props.prop_tags)
        tags.update(self.events.event_tags)
        tags.update(self.concepts.concept_tags)
        return tags
    
    @property
    def tag_count(self) -> int:
        """Get total tag count."""
        return len(self.all_tags)


class TagOrchestrator:
    """
    Orchestrates all tag extraction and management operations.
    
    Provides a unified interface for:
    - Extracting all tag types from text
    - Validating tags against world bible
    - Managing tag relationships
    - Coordinating consensus voting
    
    Usage:
        orchestrator = TagOrchestrator(llm_caller=my_llm_caller)
        result = await orchestrator.extract_all_tags(text)
        print(f"Found {result.tag_count} tags")
    """
    
    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        world_bible: Optional[Dict] = None,
        threshold: float = TAG_CONSENSUS_THRESHOLD
    ):
        """
        Initialize tag orchestrator.
        
        Args:
            llm_caller: Async function to call LLM
            world_bible: World bible data
            threshold: Consensus threshold for extraction
        """
        self.llm_caller = llm_caller
        self.world_bible = world_bible or {}
        self.threshold = threshold
        
        # Initialize type-specific managers
        self.characters = CharacterTagManager(llm_caller, threshold)
        self.locations = LocationTagManager(llm_caller, world_bible, threshold)
        self.props = PropTagManager(llm_caller, threshold)
        self.events = EventTagManager(llm_caller, threshold)
        self.plots = PlotTagManager(llm_caller, threshold)
        self.relationships = RelationshipTagManager(llm_caller, world_bible)
    
    async def extract_all_tags(
        self,
        text: str,
        context: Optional[str] = None
    ) -> UnifiedExtractionResult:
        """
        Extract all tag types from text.
        
        Runs all extractors in parallel for efficiency.
        
        Args:
            text: Text to extract tags from
            context: Optional additional context
            
        Returns:
            UnifiedExtractionResult with all extracted tags
        """
        logger.info("Starting unified tag extraction")
        
        # Run all extractors in parallel
        results = await asyncio.gather(
            self.characters.extract_character_tags(text, context),
            self.locations.extract_location_tags(text, context),
            self.props.extract_prop_tags(text, context),
            self.events.extract_event_tags(text, context),
            self.plots.extract_concept_tags(text, context),
            self.relationships.extract_relationships(text, context),
            return_exceptions=True
        )
        
        # Handle any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Extractor {i} failed: {result}")
        
        # Build unified result
        unified = UnifiedExtractionResult(
            characters=results[0] if not isinstance(results[0], Exception) else self._empty_character_result(),
            locations=results[1] if not isinstance(results[1], Exception) else self._empty_location_result(),
            props=results[2] if not isinstance(results[2], Exception) else self._empty_prop_result(),
            events=results[3] if not isinstance(results[3], Exception) else self._empty_event_result(),
            concepts=results[4] if not isinstance(results[4], Exception) else self._empty_plot_result(),
            relationships=results[5] if not isinstance(results[5], Exception) else self._empty_relationship_result()
        )
        
        logger.info(f"Unified extraction complete: {unified.tag_count} tags found")
        return unified
    
    def update_world_bible(self, world_bible: Dict) -> None:
        """Update world bible for all managers."""
        self.world_bible = world_bible
        self.locations.world_bible = world_bible
        self.relationships.world_bible = world_bible
    
    def _empty_character_result(self) -> CharacterExtractionResult:
        return CharacterExtractionResult(set(), {}, self.threshold, False)
    
    def _empty_location_result(self) -> LocationExtractionResult:
        return LocationExtractionResult(set(), set(), {}, self.threshold, False)
    
    def _empty_prop_result(self) -> PropExtractionResult:
        return PropExtractionResult(set(), {}, self.threshold, False)
    
    def _empty_event_result(self) -> EventExtractionResult:
        return EventExtractionResult(set(), {}, self.threshold, False)
    
    def _empty_plot_result(self) -> PlotExtractionResult:
        return PlotExtractionResult(set(), {}, self.threshold, False)
    
    def _empty_relationship_result(self) -> RelationshipExtractionResult:
        return RelationshipExtractionResult([], set(), False)

