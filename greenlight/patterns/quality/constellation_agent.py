"""
Constellation Agent - Tag Relationship Mapper

An agent that maps all tag relationships across the script, ensuring:
- Every tag reference is valid (exists in world_config)
- Relationships are consistent with world_config
- No orphan tags (used but not defined)
- No phantom tags (defined but never used)

Visualizes tags as a "constellation" of interconnected elements.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set
import asyncio
import json
import re

from greenlight.core.logging_config import get_logger
from greenlight.agents.prompts import AgentPromptLibrary
from greenlight.config.notation_patterns import REGEX_PATTERNS
from .universal_context import UniversalContext

logger = get_logger("patterns.quality.constellation")


@dataclass
class TagRelationship:
    """A relationship between two tags."""
    source_tag: str
    target_tag: str
    relationship_type: str  # owns, works_at, visits, uses, connects, interacts_with
    scenes_present: List[int] = field(default_factory=list)
    strength: float = 0.0  # 0-1 based on frequency


@dataclass
class TagValidationIssue:
    """An issue with tag usage."""
    issue_type: str  # orphan, phantom, malformed, inconsistent
    tag: str
    description: str
    scenes: List[int] = field(default_factory=list)
    suggested_fix: str = ""


@dataclass
class ConstellationMap:
    """Complete tag relationship map."""
    all_tags: List[str]
    relationships: List[TagRelationship]
    orphan_tags: List[str]  # Used but not defined
    phantom_tags: List[str]  # Defined but not used
    validation_issues: List[TagValidationIssue]
    is_valid: bool


class ConstellationAgent:
    """
    Maps and validates tag relationships across the script.
    
    Process:
    1. Extract all tags from script
    2. Compare against world_config defined tags
    3. Extract relationships between tags
    4. Validate relationships for consistency
    5. Generate constellation map
    """
    
    # Import regex patterns from canonical source (notation_patterns.py)
    # All 6 canonical prefixes: CHAR_, LOC_, PROP_, CONCEPT_, EVENT_, ENV_
    TAG_PATTERNS = {
        'bracketed': REGEX_PATTERNS['any_tag'],  # [PREFIX_NAME]
        'char_prefix': REGEX_PATTERNS['character_tag'],
        'loc_prefix': REGEX_PATTERNS['location_tag'],
        'prop_prefix': REGEX_PATTERNS['prop_tag'],
        'concept_prefix': REGEX_PATTERNS['concept_tag'],
        'event_prefix': REGEX_PATTERNS['event_tag'],
        'env_prefix': REGEX_PATTERNS['environment_tag'],
    }
    
    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller
    
    async def map_constellation(
        self,
        script: str,
        world_config: Dict[str, Any],
        pitch: str
    ) -> ConstellationMap:
        """
        Build complete tag relationship map.
        
        Args:
            script: Full script text
            world_config: World configuration
            pitch: Story pitch
            
        Returns:
            ConstellationMap with all tag relationships and validation
        """
        logger.info("ConstellationAgent: Mapping tag constellation...")
        
        # Extract all tags from script
        script_tags = self._extract_all_tags(script)
        
        # Get defined tags from world_config
        defined_tags = set(world_config.get('all_tags', []))
        
        # Also add tags from individual categories
        for char in world_config.get('characters', []):
            if char.get('tag'):
                defined_tags.add(char['tag'])
        for loc in world_config.get('locations', []):
            if loc.get('tag'):
                defined_tags.add(loc['tag'])
        for prop in world_config.get('props', []):
            if prop.get('tag'):
                defined_tags.add(prop['tag'])
        
        # Validate tag existence
        orphan_tags = list(script_tags - defined_tags)
        phantom_tags = list(defined_tags - script_tags)
        
        # Extract relationships
        relationships = await self._extract_relationships(script, world_config)
        
        # Validate and generate issues
        validation_issues = self._validate_tags(
            script_tags, defined_tags, orphan_tags, script
        )
        
        # Add relationship validation issues
        rel_issues = self._validate_relationships(relationships, world_config)
        validation_issues.extend(rel_issues)
        
        is_valid = len(orphan_tags) == 0 and len(validation_issues) == 0
        
        logger.info(f"ConstellationAgent: Found {len(script_tags)} tags, "
                   f"{len(orphan_tags)} orphans, {len(phantom_tags)} phantoms, "
                   f"{len(relationships)} relationships")
        
        return ConstellationMap(
            all_tags=list(script_tags | defined_tags),
            relationships=relationships,
            orphan_tags=orphan_tags,
            phantom_tags=phantom_tags,
            validation_issues=validation_issues,
            is_valid=is_valid
        )
    
    def _extract_all_tags(self, script: str) -> Set[str]:
        """Extract all tag references from script."""
        tags = set()
        
        # Find all bracketed tags
        matches = re.findall(self.TAG_PATTERNS['bracketed'], script)
        for match in matches:
            # Normalize tag format
            if not match.startswith(('CHAR_', 'LOC_', 'PROP_', 'CONCEPT_', 'EVENT_', 'ENV_')):
                # Try to infer prefix based on context
                pass
            tags.add(match)
        
        return tags
    
    def _validate_tags(
        self,
        script_tags: Set[str],
        defined_tags: Set[str],
        orphan_tags: List[str],
        script: str
    ) -> List[TagValidationIssue]:
        """Validate tag usage and generate issues."""
        issues = []
        
        # Check for orphan tags
        for tag in orphan_tags:
            # Find scenes where this tag appears
            scenes = self._find_tag_scenes(tag, script)
            
            # Suggest fix
            suggested = self._suggest_tag_fix(tag, defined_tags)
            
            issues.append(TagValidationIssue(
                issue_type='orphan',
                tag=tag,
                description=f"Tag [{tag}] used in script but not defined in world_config",
                scenes=scenes,
                suggested_fix=suggested
            ))
        
        # Check for malformed tags
        malformed = re.findall(r'\[([a-z][a-z0-9_]*)\]', script, re.IGNORECASE)
        for tag in malformed:
            if tag != tag.upper():
                issues.append(TagValidationIssue(
                    issue_type='malformed',
                    tag=tag,
                    description=f"Tag [{tag}] should be uppercase: [{tag.upper()}]",
                    suggested_fix=f"Replace [{tag}] with [{tag.upper()}]"
                ))

        return issues

    def _find_tag_scenes(self, tag: str, script: str) -> List[int]:
        """Find which scenes a tag appears in."""
        scenes = []

        # Split by scene markers
        scene_pattern = r'## Scene (\d+):'
        parts = re.split(scene_pattern, script)

        for i in range(1, len(parts), 2):
            scene_num = int(parts[i])
            scene_content = parts[i + 1] if i + 1 < len(parts) else ""
            if f'[{tag}]' in scene_content:
                scenes.append(scene_num)

        return scenes

    def _suggest_tag_fix(self, tag: str, defined_tags: Set[str]) -> str:
        """Suggest a fix for an undefined tag."""
        # Try to find similar tags
        tag_lower = tag.lower()

        for defined in defined_tags:
            defined_lower = defined.lower()
            # Check for partial match
            if tag_lower in defined_lower or defined_lower in tag_lower:
                return f"Did you mean [{defined}]?"
            # Check for similar prefix
            if tag_lower[:4] == defined_lower[:4]:
                return f"Did you mean [{defined}]?"

        # Suggest adding to world_config
        return f"Add [{tag}] to world_config or remove from script"

    async def _extract_relationships(
        self,
        script: str,
        world_config: Dict[str, Any]
    ) -> List[TagRelationship]:
        """Extract tag relationships from script content."""

        # Get all defined tags for context
        char_tags = [c.get('tag') for c in world_config.get('characters', [])]
        loc_tags = [l.get('tag') for l in world_config.get('locations', [])]
        prop_tags = [p.get('tag') for p in world_config.get('props', [])]

        prompt = f"""Analyze this script for tag relationships.

{AgentPromptLibrary.TAG_NAMING_RULES}

SCRIPT:
{script[:8000]}  # Truncate for token limits

DEFINED TAGS:
Characters: {json.dumps(char_tags)}
Locations: {json.dumps(loc_tags)}
Props: {json.dumps(prop_tags)}

For each relationship found between tags, identify:
- source_tag: The source tag (e.g., CHAR_MEI, CHAR_ZHANG)
- target_tag: The target tag (e.g., PROP_SWORD, LOC_PALACE)
- relationship_type: One of (owns, works_at, visits, uses, connects, interacts_with)
- scenes: List of scene numbers where this relationship appears

**CRITICAL**: Use the EXACT tag names from DEFINED TAGS above. Tags are literal identifiers.

Format as JSON array:
[
  {{"source_tag": "CHAR_MEI", "target_tag": "PROP_SWORD", "relationship_type": "owns", "scenes": [1, 3]}},
  ...
]
"""

        response = await self.llm_caller(prompt)
        return self._parse_relationships(response)

    def _parse_relationships(self, response: str) -> List[TagRelationship]:
        """Parse relationships from LLM response."""
        relationships = []

        # Try to extract JSON array
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                for item in data:
                    if isinstance(item, dict):
                        scenes = item.get('scenes', [])
                        strength = len(scenes) / 10.0  # Normalize by frequency

                        relationships.append(TagRelationship(
                            source_tag=item.get('source_tag', ''),
                            target_tag=item.get('target_tag', ''),
                            relationship_type=item.get('relationship_type', 'interacts_with'),
                            scenes_present=scenes,
                            strength=min(1.0, strength)
                        ))
            except json.JSONDecodeError:
                pass

        return relationships

    def _validate_relationships(
        self,
        relationships: List[TagRelationship],
        world_config: Dict[str, Any]
    ) -> List[TagValidationIssue]:
        """Validate relationships against world_config."""
        issues = []

        # Build expected relationships from world_config
        expected_owners = {}
        for prop in world_config.get('props', []):
            if prop.get('associated_character'):
                expected_owners[prop['tag']] = prop['associated_character']

        # Check for inconsistent ownership
        for rel in relationships:
            if rel.relationship_type == 'owns':
                expected = expected_owners.get(rel.target_tag)
                if expected and expected != rel.source_tag:
                    issues.append(TagValidationIssue(
                        issue_type='inconsistent',
                        tag=rel.target_tag,
                        description=(f"Prop [{rel.target_tag}] owned by [{rel.source_tag}] "
                                   f"in script but associated with [{expected}] in world_config"),
                        scenes=rel.scenes_present,
                        suggested_fix=f"Update world_config or script to be consistent"
                    ))

        return issues

    def generate_constellation_report(self, constellation: ConstellationMap) -> str:
        """Generate a human-readable constellation report."""
        lines = [
            "=" * 60,
            "TAG CONSTELLATION REPORT",
            "=" * 60,
            "",
            f"Total Tags: {len(constellation.all_tags)}",
            f"Valid: {'Yes' if constellation.is_valid else 'No'}",
            "",
        ]

        if constellation.orphan_tags:
            lines.append("ORPHAN TAGS (used but not defined):")
            for tag in constellation.orphan_tags:
                lines.append(f"  - [{tag}]")
            lines.append("")

        if constellation.phantom_tags:
            lines.append("PHANTOM TAGS (defined but not used):")
            for tag in constellation.phantom_tags:
                lines.append(f"  - [{tag}]")
            lines.append("")

        if constellation.validation_issues:
            lines.append("VALIDATION ISSUES:")
            for issue in constellation.validation_issues:
                lines.append(f"  [{issue.issue_type.upper()}] {issue.tag}: {issue.description}")
                if issue.suggested_fix:
                    lines.append(f"    Fix: {issue.suggested_fix}")
            lines.append("")

        if constellation.relationships:
            lines.append("TAG RELATIONSHIPS:")
            for rel in constellation.relationships[:20]:  # Limit output
                lines.append(f"  [{rel.source_tag}] --{rel.relationship_type}--> [{rel.target_tag}]")

        return "\n".join(lines)
