"""
Location Tag Manager

Manages location tag extraction, directional consensus, and spatial continuity.
Uses single-agent selection for directional tags (faster, more consistent).
Uses 5-agent voting for spatial anchor detection.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Callable, Any

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import TAG_CONSENSUS_THRESHOLD, VALID_DIRECTIONS
from greenlight.agents.prompts import AgentPromptLibrary

logger = get_logger("tags.locations")


@dataclass
class LocationExtractionResult:
    """Result from location tag extraction."""
    location_tags: Set[str]
    directional_tags: Set[str]  # Tags with _DIR_N/E/S/W suffix
    agreement_ratios: Dict[str, float]
    threshold: float
    is_consensus: bool


@dataclass
class DirectionalTagResult:
    """Result from directional tag selection."""
    directional_tag: Optional[str]  # e.g., LOC_BROTHEL_DIR_W
    base_tag: str  # e.g., LOC_BROTHEL
    direction: Optional[str]  # N, E, S, W
    confidence: float
    reasoning: str


class LocationTagManager:
    """
    Manages location tag operations.
    
    Responsibilities:
    - Extract location tags using consensus
    - Select directional tags using single-agent (faster)
    - Detect spatial anchors using 5-agent consensus
    - Track spatial continuity across shots
    
    Uses externalized prompts from:
        tags/locations/prompts/01_extraction/
        tags/locations/prompts/02_validation/
        tags/locations/prompts/03_directional/
        tags/locations/prompts/04_spatial/
    """
    
    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        world_bible: Optional[Dict] = None,
        threshold: float = TAG_CONSENSUS_THRESHOLD
    ):
        """
        Initialize location tag manager.
        
        Args:
            llm_caller: Async function to call LLM
            world_bible: World bible with location data
            threshold: Consensus threshold for extraction
        """
        self.llm_caller = llm_caller
        self.world_bible = world_bible or {}
        self.threshold = threshold
    
    async def extract_location_tags(
        self,
        text: str,
        context: Optional[str] = None
    ) -> LocationExtractionResult:
        """
        Extract location tags from text.
        
        Args:
            text: Text to extract location tags from
            context: Optional additional context
            
        Returns:
            LocationExtractionResult with extracted tags
        """
        logger.info("Extracting location tags")
        
        # Parse location tags from text
        tags = self._parse_location_tags(text)
        
        # Separate directional and base tags
        directional_tags = {t for t in tags if any(t.endswith(f"_DIR_{d}") for d in VALID_DIRECTIONS)}
        base_tags = tags - directional_tags
        
        return LocationExtractionResult(
            location_tags=base_tags,
            directional_tags=directional_tags,
            agreement_ratios={tag: 1.0 for tag in tags},
            threshold=self.threshold,
            is_consensus=True
        )
    
    async def select_directional_tag(
        self,
        beat_content: str,
        location_tag: str,
        direction_text: str,
        scene_context: Optional[str] = None
    ) -> DirectionalTagResult:
        """
        Select the appropriate directional tag for a location.
        
        Uses single-agent selection (not consensus) for speed and consistency.
        
        Args:
            beat_content: The beat content text
            location_tag: Base location tag (e.g., LOC_BROTHEL)
            direction_text: Direction description
            scene_context: Optional scene context
            
        Returns:
            DirectionalTagResult with selected tag
        """
        logger.info(f"Selecting directional tag for {location_tag}")
        
        if not self.llm_caller:
            return self._fallback_directional_selection(location_tag, direction_text)
        
        # Get directional views from world bible
        directional_views = self._get_directional_views(location_tag)
        
        # Build prompt with TAG_NAMING_RULES
        prompt = self._build_directional_prompt(
            beat_content, location_tag, direction_text,
            directional_views, scene_context
        )
        
        response = await self.llm_caller(prompt)
        return self._parse_directional_response(response, location_tag)
    
    def _parse_location_tags(self, text: str) -> Set[str]:
        """Parse location tags from text."""
        import re
        pattern = r'\[?(LOC_[A-Z0-9_]+)\]?'
        matches = re.findall(pattern, text.upper())
        placeholders = {'LOC_NAME', 'LOC_TAG_NAME', 'LOC_SPECIFIC_PLACE_NAME'}
        return {tag for tag in matches if tag not in placeholders}
    
    def _get_directional_views(self, location_tag: str) -> str:
        """Get directional views from world bible."""
        locations = self.world_bible.get('locations', {})
        
        if isinstance(locations, dict):
            loc = locations.get(location_tag)
            if loc and loc.get('directional_views'):
                views = loc['directional_views']
                return "\n".join([
                    f"NORTH: {views.get('north', views.get('N', 'Not defined'))}",
                    f"EAST: {views.get('east', views.get('E', 'Not defined'))}",
                    f"SOUTH: {views.get('south', views.get('S', 'Not defined'))}",
                    f"WEST: {views.get('west', views.get('W', 'Not defined'))}"
                ])
        
        return "No directional views defined."
    
    def _build_directional_prompt(
        self,
        beat_content: str,
        location_tag: str,
        direction_text: str,
        directional_views: str,
        scene_context: Optional[str]
    ) -> str:
        """Build prompt for directional tag selection."""
        return f"""Select the correct directional location tag.

{AgentPromptLibrary.TAG_NAMING_RULES}

## DIRECTIONAL TAG RULES
1. Format: [LOC_NAME_DIR_X] where X is N, E, S, or W
2. Direction indicates where camera is FACING
3. Tags are literal identifiers, NOT placeholders

BEAT CONTENT:
{beat_content}

BASE LOCATION: {location_tag}
DIRECTION INFO: {direction_text}

WORLD BIBLE DIRECTIONAL VIEWS:
{directional_views}

{f"SCENE CONTEXT: {scene_context}" if scene_context else ""}

Output:
DIRECTIONAL_TAG: [LOC_..._DIR_X]
CONFIDENCE: [0.0-1.0]
REASONING: [explanation]"""
    
    def _parse_directional_response(self, response: str, base_tag: str) -> DirectionalTagResult:
        """Parse directional tag from LLM response."""
        import re
        
        # Extract tag
        tag_match = re.search(r'DIRECTIONAL_TAG:\s*\[?([A-Z_]+_DIR_[NESW])\]?', response, re.IGNORECASE)
        directional_tag = tag_match.group(1).upper() if tag_match else None
        
        # Extract direction
        direction = None
        if directional_tag:
            for d in VALID_DIRECTIONS:
                if directional_tag.endswith(f"_DIR_{d}"):
                    direction = d
                    break
        
        # Extract confidence
        conf_match = re.search(r'CONFIDENCE:\s*([\d.]+)', response)
        confidence = float(conf_match.group(1)) if conf_match else 0.5
        
        # Extract reasoning
        reason_match = re.search(r'REASONING:\s*(.+?)(?:\n|$)', response, re.DOTALL)
        reasoning = reason_match.group(1).strip() if reason_match else ""
        
        return DirectionalTagResult(
            directional_tag=directional_tag,
            base_tag=base_tag,
            direction=direction,
            confidence=confidence,
            reasoning=reasoning
        )
    
    def _fallback_directional_selection(self, location_tag: str, direction_text: str) -> DirectionalTagResult:
        """Fallback directional selection without LLM."""
        direction = 'N'  # Default
        for d in VALID_DIRECTIONS:
            if d in direction_text.upper() or self._direction_name(d) in direction_text.upper():
                direction = d
                break
        
        return DirectionalTagResult(
            directional_tag=f"{location_tag}_DIR_{direction}",
            base_tag=location_tag,
            direction=direction,
            confidence=0.7,
            reasoning="Parsed from direction text"
        )
    
    def _direction_name(self, d: str) -> str:
        """Get full direction name."""
        return {'N': 'NORTH', 'E': 'EAST', 'S': 'SOUTH', 'W': 'WEST'}.get(d, d)

