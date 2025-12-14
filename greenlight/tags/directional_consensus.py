"""
Greenlight Directional Tag Consensus System

Directional location tag validation and insertion.
Uses single-agent selection for directional tags (faster, more consistent output).
Uses 5-agent voting for spatial anchor detection.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Tuple
from collections import Counter
import asyncio
import re

from greenlight.core.constants import VALID_DIRECTIONS, DIRECTION_SUFFIXES
from greenlight.core.logging_config import get_logger
from greenlight.agents.prompts import AgentPromptLibrary
from greenlight.tags.tag_parser import TagParser

logger = get_logger("tags.directional_consensus")


@dataclass
class DirectionalTagVote:
    """A single agent's vote for a directional tag."""
    agent_name: str
    directional_tag: str  # e.g., "LOC_BROTHEL_DIR_W"
    confidence: float  # 0.0 to 1.0
    reasoning: str


@dataclass
class SpatialAnchor:
    """A spatial anchor detected in directional description."""
    object_name: str  # e.g., "bed", "window", "door"
    facing_direction: str  # N, E, S, W
    confidence: float
    description: str


@dataclass
class AnchorDetectionVote:
    """A single agent's vote for spatial anchors."""
    agent_name: str
    anchors: List[SpatialAnchor]
    reasoning: str


@dataclass
class DirectionalConsensusResult:
    """Result of directional tag consensus voting."""
    consensus_tag: Optional[str]  # The winning directional tag
    votes: List[DirectionalTagVote]
    agreement_ratio: float  # 0.0 to 1.0
    all_voted_tags: Dict[str, int]  # tag -> vote count
    success: bool
    iteration_count: int = 1


@dataclass
class AnchorConsensusResult:
    """Result of spatial anchor consensus voting."""
    consensus_anchors: List[SpatialAnchor]
    votes: List[AnchorDetectionVote]
    agreement_ratios: Dict[str, float]  # anchor_key -> ratio
    success: bool
    iteration_count: int = 1


class DirectionalTagConsensus:
    """
    Single-agent directional location tag selector.

    Process:
    1. Single agent analyzes beat content, direction, and world bible
    2. Cross-references world bible directional_views
    3. Considers scene context, characters, props, relationships
    4. Returns the selected directional tag

    Note: Changed from 3-agent consensus to single-agent for faster, more
    consistent output. The consensus approach was slower and didn't improve
    accuracy significantly.
    """

    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        world_bible: Optional[Dict] = None,
        strict_tagging_rules: Optional[str] = None
    ):
        """
        Initialize directional tag selector.

        Args:
            llm_caller: Async function to call LLM
            world_bible: World bible with location directional_views
            strict_tagging_rules: Tagging style rules document
        """
        self.llm_caller = llm_caller
        self.world_bible = world_bible or {}
        self.strict_tagging_rules = strict_tagging_rules or self._default_tagging_rules()
        self.parser = TagParser()
    
    def _default_tagging_rules(self) -> str:
        """Default strict tagging rules.

        Combines AgentPromptLibrary.TAG_NAMING_RULES with directional-specific rules.
        """
        return f"""
{AgentPromptLibrary.TAG_NAMING_RULES}

## DIRECTIONAL TAG RULES (ADDITIONAL)

1. Format: [LOC_NAME_DIR_X] where X is N, E, S, or W
2. Direction indicates where camera is FACING (not looking at)
3. Direction suffix must be one of: _DIR_N, _DIR_E, _DIR_S, _DIR_W
4. Tag must match a location defined in world bible

**CRITICAL**: Tags are literal identifiers, NOT placeholders.
- ✅ CORRECT: [LOC_BROTHEL_DIR_W], [LOC_MERCHANT_DISTRICT_DIR_N]
- ❌ WRONG: [LOC_NAME_DIR_X], [LOC_TAG_DIR_N]
"""
    
    async def validate_and_insert_directional_tag(
        self,
        beat_content: str,
        location_tag: str,
        direction_text: str,
        scene_context: Optional[str] = None,
        characters: Optional[List[str]] = None,
        props: Optional[List[str]] = None
    ) -> DirectionalConsensusResult:
        """
        Validate and insert directional tag using single-agent selection.

        Args:
            beat_content: The beat content text
            location_tag: Base location tag (e.g., "LOC_BROTHEL")
            direction_text: Direction description (e.g., "Camera facing W, light from E")
            scene_context: Optional scene context
            characters: Optional list of character tags in beat
            props: Optional list of prop tags in beat

        Returns:
            DirectionalConsensusResult with selected tag
        """
        logger.info(f"Starting directional tag selection for {location_tag}")

        # Run single agent for directional tag selection
        vote = await self._run_single_agent(
            beat_content, location_tag, direction_text,
            scene_context, characters, props
        )

        # Return result (single agent = 100% agreement)
        return DirectionalConsensusResult(
            consensus_tag=vote.directional_tag if vote.directional_tag else None,
            votes=[vote],
            agreement_ratio=1.0 if vote.directional_tag else 0.0,
            all_voted_tags={vote.directional_tag: 1} if vote.directional_tag else {},
            success=bool(vote.directional_tag)
        )

    async def _run_single_agent(
        self,
        beat_content: str,
        location_tag: str,
        direction_text: str,
        scene_context: Optional[str],
        characters: Optional[List[str]],
        props: Optional[List[str]]
    ) -> DirectionalTagVote:
        """Run single agent for directional tag selection."""
        if not self.llm_caller:
            # Fallback: parse direction from text
            votes = self._fallback_direction_parsing(location_tag, direction_text)
            return votes[0] if votes else DirectionalTagVote(
                agent_name="FallbackParser",
                directional_tag="",
                confidence=0.0,
                reasoning="No direction could be parsed"
            )

        try:
            # Single comprehensive agent that considers all factors
            vote = await self._agent_comprehensive_analysis(
                beat_content, location_tag, direction_text,
                scene_context, characters, props
            )
            return vote
        except Exception as e:
            logger.warning(f"Single agent failed: {e}")
            # Fallback to parsing
            votes = self._fallback_direction_parsing(location_tag, direction_text)
            return votes[0] if votes else DirectionalTagVote(
                agent_name="FallbackParser",
                directional_tag="",
                confidence=0.0,
                reasoning=f"Agent failed: {e}"
            )

    async def _agent_comprehensive_analysis(
        self,
        beat_content: str,
        location_tag: str,
        direction_text: str,
        scene_context: Optional[str],
        characters: Optional[List[str]],
        props: Optional[List[str]]
    ) -> DirectionalTagVote:
        """Single comprehensive agent that analyzes all factors."""
        # Get directional views from world bible
        directional_views = self._get_directional_views(location_tag)

        context_info = f"""
SCENE CONTEXT: {scene_context or 'Not provided'}
CHARACTERS IN BEAT: {', '.join(characters) if characters else 'None'}
PROPS IN BEAT: {', '.join(props) if props else 'None'}
"""

        prompt = f"""Analyze this story beat and determine the correct directional location tag.

{self.strict_tagging_rules}

BEAT CONTENT:
{beat_content}

BASE LOCATION TAG: {location_tag}
DIRECTION INFO: {direction_text}

WORLD BIBLE DIRECTIONAL VIEWS:
{directional_views}

{context_info}

Consider ALL of the following:
1. What direction is the camera FACING? (not looking at)
2. What visual elements are described in the beat?
3. What lighting direction is mentioned?
4. Which world bible directional view best matches?
5. Character positions and movements
6. Prop placements and spatial relationships
7. Scene continuity and narrative flow

Output format:
DIRECTIONAL_TAG: [LOC_NAME_DIR_X]
CONFIDENCE: [0.0-1.0]
REASONING: [your comprehensive analysis]"""

        response = await self.llm_caller(prompt)
        return self._parse_vote_response(response, "ComprehensiveAnalysis")

    def _parse_vote_response(self, response: str, agent_name: str) -> DirectionalTagVote:
        """Parse agent vote response."""
        # Extract directional tag - tags MUST be in brackets per notation standard
        tag_match = re.search(r'DIRECTIONAL_TAG:\s*\[([A-Z_]+(?:_DIR_[NESW]))\]', response, re.IGNORECASE)
        if not tag_match:
            # Fallback: look for any [LOC_*_DIR_*] pattern with mandatory brackets
            tag_match = re.search(r'\[(LOC_[A-Z_]+_DIR_[NESW])\]', response)

        directional_tag = tag_match.group(1) if tag_match else ""

        # Extract confidence
        conf_match = re.search(r'CONFIDENCE:\s*([\d.]+)', response)
        confidence = float(conf_match.group(1)) if conf_match else 0.5

        # Extract reasoning
        reason_match = re.search(r'REASONING:\s*(.+?)(?:\n\n|$)', response, re.DOTALL)
        reasoning = reason_match.group(1).strip() if reason_match else response[:200]

        return DirectionalTagVote(
            agent_name=agent_name,
            directional_tag=directional_tag,
            confidence=confidence,
            reasoning=reasoning
        )

    def _get_directional_views(self, location_tag: str) -> str:
        """
        Get directional views from world bible for a location.

        Supports both:
        - New schema: locations as dict keyed by tag with directional_views
        - Legacy schema: locations as list with tag field
        """
        locations = self.world_bible.get('locations', {})

        # Handle new schema: locations as dict keyed by tag
        if isinstance(locations, dict):
            loc = locations.get(location_tag)
            if loc:
                views = loc.get('directional_views', {})
                if views:
                    return self._format_directional_views(views)

        # Handle legacy schema: locations as list
        elif isinstance(locations, list):
            for loc in locations:
                if loc.get('tag') == location_tag or loc.get('id') == location_tag:
                    views = loc.get('directional_views', {})
                    if views:
                        return self._format_directional_views(views)

        return "No directional views defined in world bible for this location."

    def _format_directional_views(self, views: Dict[str, str]) -> str:
        """Format directional views dictionary into readable string."""
        return "\n".join([
            f"NORTH: {views.get('north', views.get('N', 'Not defined'))}",
            f"EAST: {views.get('east', views.get('E', 'Not defined'))}",
            f"SOUTH: {views.get('south', views.get('S', 'Not defined'))}",
            f"WEST: {views.get('west', views.get('W', 'Not defined'))}"
        ])

    def _fallback_direction_parsing(
        self,
        location_tag: str,
        direction_text: str
    ) -> List[DirectionalTagVote]:
        """Fallback: parse direction from text without LLM."""
        direction_text_upper = direction_text.upper()

        # Try to extract direction
        direction = None
        for d in VALID_DIRECTIONS:
            if f"FACING {d}" in direction_text_upper or f"DIR_{d}" in direction_text_upper:
                direction = d
                break
            elif f"FACING {self._direction_name(d)}" in direction_text_upper:
                direction = d
                break

        if not direction:
            direction = 'N'  # Default to North

        directional_tag = f"{location_tag}_DIR_{direction}"

        return [DirectionalTagVote(
            agent_name="FallbackParser",
            directional_tag=directional_tag,
            confidence=0.7,
            reasoning=f"Parsed from direction text: {direction_text}"
        )]

    def _direction_name(self, direction: str) -> str:
        """Get full name of direction."""
        names = {'N': 'NORTH', 'E': 'EAST', 'S': 'SOUTH', 'W': 'WEST'}
        return names.get(direction, direction)


class SpatialAnchorDetector:
    """
    5-agent consensus system for spatial anchor detection.

    Process:
    1. 5 agents analyze directional description for spatial anchors
    2. Each agent identifies objects with directional orientation (e.g., "bed foot facing North")
    3. Require 3/5 consensus (60%) for anchor acceptance
    4. Iterate up to 2 times if consensus fails
    """

    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        max_iterations: int = 2
    ):
        """
        Initialize spatial anchor detector.

        Args:
            llm_caller: Async function to call LLM
            max_iterations: Maximum iterations before giving up
        """
        self.llm_caller = llm_caller
        self.max_iterations = max_iterations
        self.num_agents = 5
        self.consensus_threshold = 3 / 5  # 3 out of 5 agents must agree

    async def detect_anchors(
        self,
        directional_description: str,
        location_tag: str
    ) -> AnchorConsensusResult:
        """
        Detect spatial anchors with 5-agent consensus.

        Args:
            directional_description: Description of the directional view
            location_tag: Location tag for context

        Returns:
            AnchorConsensusResult with consensus anchors
        """
        logger.info(f"Starting spatial anchor detection for {location_tag}")

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"Anchor detection iteration {iteration}/{self.max_iterations}")

            # Run 5 agents in parallel
            votes = await self._run_anchor_agents(directional_description, location_tag, iteration)

            # Calculate consensus
            result = self._calculate_anchor_consensus(votes, iteration)

            if result.success:
                logger.info(f"✓ Anchor consensus reached on iteration {iteration}")
                return result
            else:
                logger.warning(f"✗ Anchor consensus failed on iteration {iteration}")

        # Failed to reach consensus
        logger.warning(f"Failed to reach anchor consensus after {self.max_iterations} iterations")
        return AnchorConsensusResult(
            consensus_anchors=[],
            votes=[],
            agreement_ratios={},
            success=False,
            iteration_count=self.max_iterations
        )

    async def _run_anchor_agents(
        self,
        description: str,
        location_tag: str,
        iteration: int
    ) -> List[AnchorDetectionVote]:
        """Run 5 anchor detection agents in parallel."""
        if not self.llm_caller:
            return []

        # Create tasks for 5 agents
        tasks = [
            self._agent_detect_anchors(description, location_tag, f"Agent{i+1}", iteration)
            for i in range(self.num_agents)
        ]

        votes = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_votes = []
        for i, vote in enumerate(votes):
            if isinstance(vote, Exception):
                logger.warning(f"Anchor agent {i+1} failed: {vote}")
            else:
                valid_votes.append(vote)

        return valid_votes

    async def _agent_detect_anchors(
        self,
        description: str,
        location_tag: str,
        agent_name: str,
        iteration: int
    ) -> AnchorDetectionVote:
        """Single agent detects spatial anchors."""
        iteration_note = ""
        if iteration > 1:
            iteration_note = f"\n\nNOTE: This is iteration {iteration}. Previous attempts failed to reach consensus. Be more specific and look for subtle directional cues."

        prompt = f"""Analyze this directional description and identify spatial anchors.

A SPATIAL ANCHOR is an object or feature with a specific directional orientation that helps determine camera direction.

Examples:
- "bed foot facing North" → ANCHOR: bed, FACING: N
- "window on the eastern wall" → ANCHOR: window, FACING: E
- "door opening to the south" → ANCHOR: door, FACING: S

LOCATION: {location_tag}

DIRECTIONAL DESCRIPTION:
{description}
{iteration_note}

Identify ALL spatial anchors in this description.
For each anchor, specify:
1. Object name (e.g., "bed", "window", "door", "table")
2. Direction it faces (N, E, S, or W)
3. Confidence (0.0-1.0)
4. Brief description of why this is an anchor

Output format (one per line):
ANCHOR: [object_name] | FACING: [N/E/S/W] | CONFIDENCE: [0.0-1.0] | DESC: [description]

If no clear anchors found, output:
NO_ANCHORS_FOUND"""

        response = await self.llm_caller(prompt)
        return self._parse_anchor_response(response, agent_name)

    def _parse_anchor_response(self, response: str, agent_name: str) -> AnchorDetectionVote:
        """Parse anchor detection response."""
        if "NO_ANCHORS_FOUND" in response.upper():
            return AnchorDetectionVote(
                agent_name=agent_name,
                anchors=[],
                reasoning="No clear spatial anchors detected"
            )

        anchors = []
        anchor_pattern = r'ANCHOR:\s*([^\|]+)\s*\|\s*FACING:\s*([NESW])\s*\|\s*CONFIDENCE:\s*([\d.]+)\s*\|\s*DESC:\s*(.+?)(?:\n|$)'

        for match in re.finditer(anchor_pattern, response, re.IGNORECASE):
            object_name = match.group(1).strip()
            facing = match.group(2).upper()
            confidence = float(match.group(3))
            description = match.group(4).strip()

            anchors.append(SpatialAnchor(
                object_name=object_name,
                facing_direction=facing,
                confidence=confidence,
                description=description
            ))

        return AnchorDetectionVote(
            agent_name=agent_name,
            anchors=anchors,
            reasoning=f"Detected {len(anchors)} spatial anchors"
        )

    def _calculate_anchor_consensus(
        self,
        votes: List[AnchorDetectionVote],
        iteration: int
    ) -> AnchorConsensusResult:
        """Calculate consensus from anchor votes."""
        if not votes:
            return AnchorConsensusResult(
                consensus_anchors=[],
                votes=[],
                agreement_ratios={},
                success=False,
                iteration_count=iteration
            )

        # Create anchor keys for matching (object_name + facing_direction)
        anchor_counts = Counter()
        anchor_details = {}  # key -> list of SpatialAnchor objects

        for vote in votes:
            for anchor in vote.anchors:
                key = f"{anchor.object_name.lower()}_{anchor.facing_direction}"
                anchor_counts[key] += 1
                if key not in anchor_details:
                    anchor_details[key] = []
                anchor_details[key].append(anchor)

        # Calculate agreement ratios
        agreement_ratios = {
            key: count / len(votes)
            for key, count in anchor_counts.items()
        }

        # Get consensus anchors (>= 60% agreement)
        consensus_anchors = []
        for key, ratio in agreement_ratios.items():
            if ratio >= self.consensus_threshold:
                # Average the confidence scores for this anchor
                anchors_list = anchor_details[key]
                avg_confidence = sum(a.confidence for a in anchors_list) / len(anchors_list)

                # Use the first anchor's details with averaged confidence
                consensus_anchor = SpatialAnchor(
                    object_name=anchors_list[0].object_name,
                    facing_direction=anchors_list[0].facing_direction,
                    confidence=avg_confidence,
                    description=f"Consensus from {len(anchors_list)}/{len(votes)} agents"
                )
                consensus_anchors.append(consensus_anchor)

        success = len(consensus_anchors) > 0

        logger.info(f"Anchor consensus: {len(consensus_anchors)} anchors with {self.consensus_threshold*100:.0f}%+ agreement")
        for anchor in consensus_anchors:
            key = f"{anchor.object_name.lower()}_{anchor.facing_direction}"
            ratio = agreement_ratios[key]
            logger.info(f"  • {anchor.object_name} facing {anchor.facing_direction}: {ratio*100:.0f}% agreement")

        return AnchorConsensusResult(
            consensus_anchors=consensus_anchors,
            votes=votes,
            agreement_ratios=agreement_ratios,
            success=success,
            iteration_count=iteration
        )

