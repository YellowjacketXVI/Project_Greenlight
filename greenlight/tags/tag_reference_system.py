"""
Greenlight Tag Reference System

Extracts validated tags using 10-agent consensus (100% agreement),
generates reference image prompts for each tag, and maintains a
tag-to-image registry for storyboard generation.

Flow:
1. 10-Agent Consensus Tag Extraction (100% agreement required)
2. Reference Image Prompt Generation (per tag type)
3. Tag Reference Registry (for storyboard calls)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Callable, Any, TYPE_CHECKING
from pathlib import Path
from datetime import datetime
from enum import Enum
import asyncio
import json

from greenlight.core.logging_config import get_logger
from greenlight.tags.tag_parser import TagParser, TagCategory
from greenlight.tags.tag_registry import TagRegistry

if TYPE_CHECKING:
    from greenlight.context.context_engine import ContextEngine

logger = get_logger("tags.reference_system")


class ReferenceImageStatus(Enum):
    """Status of a reference image."""
    PENDING = "pending"
    GENERATING = "generating"
    GENERATED = "generated"
    FAILED = "failed"


@dataclass
class TagReferenceEntry:
    """A tag with its reference image prompt and metadata."""
    tag: str
    category: TagCategory
    display_name: str
    description: str
    reference_prompt: str  # The image generation prompt
    image_path: Optional[str] = None  # Path to generated image
    status: ReferenceImageStatus = ReferenceImageStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "tag": self.tag,
            "category": self.category.value,
            "display_name": self.display_name,
            "description": self.description,
            "reference_prompt": self.reference_prompt,
            "image_path": self.image_path,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TagReferenceEntry':
        return cls(
            tag=data["tag"],
            category=TagCategory(data["category"]),
            display_name=data["display_name"],
            description=data["description"],
            reference_prompt=data["reference_prompt"],
            image_path=data.get("image_path"),
            status=ReferenceImageStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            metadata=data.get("metadata", {})
        )


@dataclass
class ValidatedTagSet:
    """Result of 10-agent consensus tag extraction."""
    character_tags: List[str]
    location_tags: List[str]
    prop_tags: List[str]
    concept_tags: List[str]
    event_tags: List[str]
    all_tags: List[str]
    consensus_achieved: bool
    agent_agreement: str  # e.g., "10/10"
    extraction_details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "character_tags": self.character_tags,
            "location_tags": self.location_tags,
            "prop_tags": self.prop_tags,
            "concept_tags": self.concept_tags,
            "event_tags": self.event_tags,
            "all_tags": self.all_tags,
            "consensus_achieved": self.consensus_achieved,
            "agent_agreement": self.agent_agreement,
            "extraction_details": self.extraction_details
        }


class TenAgentConsensusTagger:
    """
    10-Agent Consensus Tag Extraction with 100% agreement requirement.
    
    Uses Claude Haiku for cost efficiency as specified in Writer_Flow_v2.
    All 10 agents must agree on a tag for it to be validated.
    """
    
    # 10 specialized perspectives as defined in Writer_Flow_v2
    AGENT_PERSPECTIVES = [
        ("narrative", "Story elements, plot points, narrative structure"),
        ("visual", "Visual descriptions, imagery, cinematography"),
        ("character", "Character mentions, relationships, motivations"),
        ("technical", "Props, locations, technical elements"),
        ("holistic", "Overall context, themes, world-building"),
        ("continuity", "Timeline consistency, spatial continuity"),
        ("emotional", "Emotional concepts, emotionally-charged elements"),
        ("spatial", "Physical layout, positioning, movement space"),
        ("temporal", "Time markers, duration, sequence"),
        ("thematic", "Core themes, symbolic elements"),
    ]
    
    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        threshold: float = 1.0  # 100% agreement required
    ):
        self.llm_caller = llm_caller
        self.threshold = threshold
        self.parser = TagParser()
        self.num_agents = len(self.AGENT_PERSPECTIVES)
    
    async def extract_with_consensus(
        self,
        pitch_text: str,
        context: Optional[Dict] = None
    ) -> ValidatedTagSet:
        """
        Extract tags using 10-agent consensus with 100% agreement.
        
        Args:
            pitch_text: The pitch/story text to extract tags from
            context: Optional context (time_period, setting, etc.)
            
        Returns:
            ValidatedTagSet with categorized validated tags
        """
        logger.info(f"Starting 10-agent consensus extraction (threshold: {self.threshold*100}%)")
        
        # Run all 10 agents in parallel
        extractions = await self._run_all_agents(pitch_text, context)
        
        # Calculate consensus (intersection of all agent tag sets)
        consensus_tags = self._calculate_strict_consensus(extractions)
        
        # Categorize tags
        return self._categorize_tags(consensus_tags, extractions)

    async def _run_all_agents(
        self,
        pitch_text: str,
        context: Optional[Dict] = None
    ) -> List[Dict[str, Set[str]]]:
        """Run all 10 agents in parallel to extract tags."""
        tasks = []
        for perspective_name, perspective_desc in self.AGENT_PERSPECTIVES:
            tasks.append(self._run_single_agent(
                pitch_text, perspective_name, perspective_desc, context
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log them
        extractions = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Agent {self.AGENT_PERSPECTIVES[i][0]} failed: {result}")
                extractions.append({"tags": set()})
            else:
                extractions.append(result)

        return extractions

    async def _run_single_agent(
        self,
        pitch_text: str,
        perspective_name: str,
        perspective_desc: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Set[str]]:
        """Run a single agent to extract tags from its perspective."""
        prompt = f"""You are a tag extraction agent with a {perspective_name} perspective.
Your focus: {perspective_desc}

Extract all relevant tags from the following text. Tags should be:
- Character names (format: CHAR_NAME or just NAME in caps)
- Location names (format: LOC_NAME)
- Prop names (format: PROP_NAME)
- Concept tags (format: CONCEPT_NAME)
- Event tags (format: EVENT_NAME)

TEXT:
{pitch_text}

{f"CONTEXT: {json.dumps(context)}" if context else ""}

Return ONLY a JSON object with these keys:
- characters: list of character tags
- locations: list of location tags
- props: list of prop tags
- concepts: list of concept tags
- events: list of event tags

Be thorough but precise. Only include tags that are clearly present in the text."""

        if self.llm_caller:
            try:
                response = await self.llm_caller(
                    prompt=prompt,
                    model="haiku"  # Use Haiku for cost efficiency
                )
                return self._parse_agent_response(response)
            except Exception as e:
                logger.error(f"Agent {perspective_name} LLM call failed: {e}")
                return {"tags": set()}
        else:
            # Fallback: use regex-based extraction
            return self._fallback_extraction(pitch_text)

    def _parse_agent_response(self, response: str) -> Dict[str, Set[str]]:
        """Parse the agent's JSON response into tag sets."""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "characters": set(data.get("characters", [])),
                    "locations": set(data.get("locations", [])),
                    "props": set(data.get("props", [])),
                    "concepts": set(data.get("concepts", [])),
                    "events": set(data.get("events", [])),
                    "tags": set(
                        data.get("characters", []) +
                        data.get("locations", []) +
                        data.get("props", []) +
                        data.get("concepts", []) +
                        data.get("events", [])
                    )
                }
        except json.JSONDecodeError:
            pass

        # Fallback: extract tags using regex
        tags = self.parser.extract_unique_tags(response)
        return {"tags": tags}

    def _fallback_extraction(self, text: str) -> Dict[str, Set[str]]:
        """Fallback regex-based tag extraction."""
        tags = self.parser.extract_unique_tags(text)

        # Categorize by prefix
        characters = {t for t in tags if t.startswith("CHAR_") or not any(t.startswith(p) for p in ["LOC_", "PROP_", "CONCEPT_", "EVENT_"])}
        locations = {t for t in tags if t.startswith("LOC_")}
        props = {t for t in tags if t.startswith("PROP_")}
        concepts = {t for t in tags if t.startswith("CONCEPT_")}
        events = {t for t in tags if t.startswith("EVENT_")}

        return {
            "characters": characters,
            "locations": locations,
            "props": props,
            "concepts": concepts,
            "events": events,
            "tags": tags
        }

    def _calculate_strict_consensus(
        self,
        extractions: List[Dict[str, Set[str]]]
    ) -> Set[str]:
        """Calculate strict consensus (100% agreement) across all agents."""
        if not extractions:
            return set()

        # Start with all tags from first agent
        all_tag_sets = [e.get("tags", set()) for e in extractions if e.get("tags")]

        if not all_tag_sets:
            return set()

        # Intersection of all tag sets = 100% consensus
        consensus = all_tag_sets[0].copy()
        for tag_set in all_tag_sets[1:]:
            consensus &= tag_set

        logger.info(f"Consensus achieved: {len(consensus)} tags agreed by all {len(extractions)} agents")
        return consensus

    def _categorize_tags(
        self,
        consensus_tags: Set[str],
        extractions: List[Dict[str, Set[str]]]
    ) -> ValidatedTagSet:
        """Categorize consensus tags by type."""
        # Categorize by prefix
        character_tags = sorted([t for t in consensus_tags if t.startswith("CHAR_") or
                                 (not any(t.startswith(p) for p in ["LOC_", "PROP_", "CONCEPT_", "EVENT_"]) and t.isupper())])
        location_tags = sorted([t for t in consensus_tags if t.startswith("LOC_")])
        prop_tags = sorted([t for t in consensus_tags if t.startswith("PROP_")])
        concept_tags = sorted([t for t in consensus_tags if t.startswith("CONCEPT_")])
        event_tags = sorted([t for t in consensus_tags if t.startswith("EVENT_")])

        # Calculate agreement stats
        total_agents = len(extractions)
        agents_with_tags = sum(1 for e in extractions if e.get("tags"))

        return ValidatedTagSet(
            character_tags=character_tags,
            location_tags=location_tags,
            prop_tags=prop_tags,
            concept_tags=concept_tags,
            event_tags=event_tags,
            all_tags=sorted(list(consensus_tags)),
            consensus_achieved=len(consensus_tags) > 0,
            agent_agreement=f"{agents_with_tags}/{total_agents}",
            extraction_details={
                "total_agents": total_agents,
                "agents_responded": agents_with_tags,
                "consensus_count": len(consensus_tags)
            }
        )


class ReferencePromptGenerator:
    """
    Generates reference image prompts for validated tags.

    Creates detailed prompts suitable for image generation that capture
    the visual essence of each tag (character, location, prop).

    Supports both legacy simple descriptions and expanded profile schemas.
    Can optionally use ContextEngine to retrieve profile data and world context.
    """

    # Prompt templates by category (legacy format)
    PROMPT_TEMPLATES = {
        TagCategory.CHARACTER: """Reference portrait of {display_name}:
{description}

Style: {style_notes}
Composition: Character reference sheet, neutral pose, clear lighting
Quality: High detail, consistent proportions, reference-quality""",

        TagCategory.LOCATION: """Reference image of {display_name}:
{description}

Style: {style_notes}
Composition: Establishing shot, clear spatial layout, atmospheric lighting
Quality: High detail, architectural accuracy, reference-quality""",

        TagCategory.PROP: """Reference image of {display_name}:
{description}

Style: {style_notes}
Composition: Product shot, clear details, neutral background
Quality: High detail, accurate proportions, reference-quality""",
    }

    def __init__(
        self,
        style_notes: str = "Cinematic, detailed, professional",
        context_engine: Optional["ContextEngine"] = None
    ):
        """
        Initialize the ReferencePromptGenerator.

        Args:
            style_notes: Default style notes for prompts
            context_engine: Optional ContextEngine for retrieving profile data and world context
        """
        self.style_notes = style_notes
        self._context_engine = context_engine
        self._world_context_cache: Optional[str] = None

    def set_context_engine(self, context_engine: "ContextEngine") -> None:
        """Set or update the ContextEngine instance."""
        self._context_engine = context_engine
        self._world_context_cache = None  # Clear cache when engine changes

    def _get_world_context(self) -> str:
        """Get world context from ContextEngine, with caching."""
        if self._context_engine is None:
            return ""
        if self._world_context_cache is None:
            self._world_context_cache = self._context_engine.get_world_context_for_tag_generation()
        return self._world_context_cache

    def _get_profile_from_context_engine(self, tag: str, category: TagCategory) -> Optional[Dict[str, Any]]:
        """Retrieve profile data from ContextEngine based on tag category."""
        if self._context_engine is None:
            return None

        if category == TagCategory.CHARACTER:
            return self._context_engine.get_character_profile(tag)
        elif category == TagCategory.LOCATION:
            return self._context_engine.get_location_profile(tag)
        elif category == TagCategory.PROP:
            return self._context_engine.get_prop_profile(tag)
        return None

    def generate_prompt(
        self,
        tag: str,
        category: TagCategory,
        description: str,
        display_name: str = None,
        profile_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a reference image prompt for a tag.

        Args:
            tag: The tag identifier
            category: Tag category (CHARACTER, LOCATION, PROP)
            description: Basic description (legacy)
            display_name: Display name for the tag
            profile_data: Optional expanded profile data from world_config
        """
        display_name = display_name or tag.replace("_", " ").title()

        # Try to get profile from ContextEngine if not provided
        if profile_data is None and self._context_engine is not None:
            profile_data = self._get_profile_from_context_engine(tag, category)

        # Use expanded profile data if available
        if profile_data:
            return self._generate_from_profile(tag, category, display_name, profile_data)

        # Fallback to legacy template
        template = self.PROMPT_TEMPLATES.get(
            category,
            self.PROMPT_TEMPLATES[TagCategory.PROP]  # Default to prop template
        )

        return template.format(
            display_name=display_name,
            description=description,
            style_notes=self.style_notes
        )

    def _generate_from_profile(
        self,
        tag: str,
        category: TagCategory,
        display_name: str,
        profile: Dict[str, Any]
    ) -> str:
        """Generate prompt from expanded profile data."""
        if category == TagCategory.CHARACTER:
            return self._generate_character_prompt(tag, display_name, profile)
        elif category == TagCategory.LOCATION:
            return self._generate_location_prompt(tag, display_name, profile)
        elif category == TagCategory.PROP:
            return self._generate_prop_prompt(tag, display_name, profile)
        else:
            return f"Reference image of [{tag}] {display_name}. Style: {self.style_notes}"

    def _generate_character_prompt(self, tag: str, display_name: str, profile: Dict[str, Any]) -> str:
        """Generate character reference prompt from expanded profile with world context."""
        parts = [f"[{tag}] - {display_name}", "Character reference portrait."]

        # Inject world context for period-accurate generation
        world_context = self._get_world_context()
        if world_context:
            parts.append(f"\n{world_context}\n")

        # Identity section
        identity = profile.get("identity", {})
        if identity:
            if identity.get("age"):
                parts.append(f"Age: {identity['age']}")
            if identity.get("ethnicity"):
                parts.append(f"Ethnicity: {identity['ethnicity']}")
            if identity.get("social_class"):
                parts.append(f"Social Class: {identity['social_class']}")

        # Visual section (most important for image gen)
        # Simplified: age, ethnicity, appearance, costume only
        # Excludes non-visual fields (emotional_tells, physicality, movement_style)
        visual = profile.get("visual", {})
        if visual:
            if visual.get("appearance"):
                parts.append(f"Appearance: {visual['appearance']}")
            if visual.get("costume_default"):
                parts.append(f"Costume: {visual['costume_default']}")

        # Fallback to legacy fields
        if not identity and not visual:
            if profile.get("age"):
                parts.append(f"Age: {profile['age']}")
            if profile.get("ethnicity"):
                parts.append(f"Ethnicity: {profile['ethnicity']}")
            if profile.get("appearance") or profile.get("visual_appearance"):
                appearance = profile.get("appearance") or profile.get("visual_appearance", "")
                parts.append(f"Appearance: {appearance}")
            if profile.get("costume"):
                parts.append(f"Costume: {profile['costume']}")

        parts.append(f"\nStyle: {self.style_notes}")
        parts.append("Composition: Character reference sheet, neutral pose, clear lighting")
        parts.append("Quality: High detail, consistent proportions, reference-quality")

        return "\n".join(parts)

    def _generate_location_prompt(self, tag: str, display_name: str, profile: Dict[str, Any]) -> str:
        """Generate location reference prompt from expanded profile with world context."""
        parts = [f"[{tag}] - {display_name}", "Location reference image."]

        # Inject world context for period-accurate generation
        world_context = self._get_world_context()
        if world_context:
            parts.append(f"\n{world_context}\n")

        # Physical section
        physical = profile.get("physical", {})
        if physical:
            if physical.get("architecture"):
                parts.append(f"Architecture: {physical['architecture']}")
            if physical.get("materials"):
                parts.append(f"Materials: {physical['materials']}")
            if physical.get("key_features"):
                features = physical['key_features']
                if isinstance(features, list):
                    parts.append(f"Key Features: {', '.join(features)}")
                else:
                    parts.append(f"Key Features: {features}")

        # Sensory section
        sensory = profile.get("sensory", {})
        if sensory and sensory.get("visual"):
            parts.append(f"Visual Details: {sensory['visual']}")

        # Atmosphere section
        atmosphere = profile.get("atmosphere", {})
        if atmosphere:
            if atmosphere.get("mood"):
                parts.append(f"Mood: {atmosphere['mood']}")
            if atmosphere.get("lighting"):
                parts.append(f"Lighting: {atmosphere['lighting']}")

        # Time period details
        time_period_details = profile.get("time_period_details", {})
        if time_period_details:
            if time_period_details.get("historical_context"):
                parts.append(f"Historical Context: {time_period_details['historical_context']}")

        # Fallback to legacy fields
        if not physical and not sensory:
            if profile.get("description"):
                parts.append(f"Description: {profile['description']}")
            if profile.get("architecture"):
                parts.append(f"Architecture: {profile['architecture']}")
            if profile.get("atmosphere"):
                parts.append(f"Atmosphere: {profile['atmosphere']}")

        parts.append(f"\nStyle: {self.style_notes}")
        parts.append("Composition: Establishing shot, clear spatial layout, atmospheric lighting")
        parts.append("Quality: High detail, architectural accuracy, reference-quality")

        return "\n".join(parts)

    def _generate_prop_prompt(self, tag: str, display_name: str, profile: Dict[str, Any]) -> str:
        """Generate prop reference prompt from expanded profile with world context."""
        parts = [f"[{tag}] - {display_name}", "Prop reference image."]

        # Inject world context for period-accurate generation
        world_context = self._get_world_context()
        if world_context:
            parts.append(f"\n{world_context}\n")

        # Physical section
        physical = profile.get("physical", {})
        if physical:
            if physical.get("materials"):
                parts.append(f"Materials: {physical['materials']}")
            if physical.get("dimensions"):
                parts.append(f"Dimensions: {physical['dimensions']}")
            if physical.get("condition"):
                parts.append(f"Condition: {physical['condition']}")
            if physical.get("craftsmanship"):
                parts.append(f"Craftsmanship: {physical['craftsmanship']}")

        # Sensory section
        sensory = profile.get("sensory", {})
        if sensory and sensory.get("visual"):
            parts.append(f"Visual Details: {sensory['visual']}")

        # Significance section
        significance = profile.get("significance", {})
        if significance and significance.get("symbolic_meaning"):
            parts.append(f"Symbolic Meaning: {significance['symbolic_meaning']}")

        # Time period details
        time_period_details = profile.get("time_period_details", {})
        if time_period_details:
            if time_period_details.get("historical_context"):
                parts.append(f"Historical Context: {time_period_details['historical_context']}")

        # Associations
        associations = profile.get("associations", {})
        if associations:
            if associations.get("primary_character"):
                parts.append(f"Associated Character: {associations['primary_character']}")

        # Fallback to legacy fields
        if not physical and not sensory:
            if profile.get("appearance"):
                parts.append(f"Appearance: {profile['appearance']}")
            if profile.get("description"):
                parts.append(f"Description: {profile['description']}")
            if profile.get("significance"):
                parts.append(f"Significance: {profile['significance']}")

        parts.append(f"\nStyle: {self.style_notes}")
        parts.append("Composition: Product shot, clear details, neutral background")
        parts.append("Quality: High detail, accurate proportions, reference-quality")

        return "\n".join(parts)

    def generate_prompts_batch(
        self,
        validated_tags: ValidatedTagSet,
        tag_descriptions: Dict[str, str],
        tag_profiles: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[TagReferenceEntry]:
        """
        Generate reference prompts for all validated tags.

        Args:
            validated_tags: Set of validated tags by category
            tag_descriptions: Simple descriptions keyed by tag (legacy)
            tag_profiles: Optional expanded profile data keyed by tag
        """
        entries = []
        tag_profiles = tag_profiles or {}

        # Process character tags
        for tag in validated_tags.character_tags:
            desc = tag_descriptions.get(tag, f"Character: {tag}")
            profile = tag_profiles.get(tag)
            prompt = self.generate_prompt(tag, TagCategory.CHARACTER, desc, profile_data=profile)
            entries.append(TagReferenceEntry(
                tag=tag,
                category=TagCategory.CHARACTER,
                display_name=tag.replace("CHAR_", "").replace("_", " ").title(),
                description=desc,
                reference_prompt=prompt
            ))

        # Process location tags
        for tag in validated_tags.location_tags:
            desc = tag_descriptions.get(tag, f"Location: {tag}")
            profile = tag_profiles.get(tag)
            prompt = self.generate_prompt(tag, TagCategory.LOCATION, desc, profile_data=profile)
            entries.append(TagReferenceEntry(
                tag=tag,
                category=TagCategory.LOCATION,
                display_name=tag.replace("LOC_", "").replace("_", " ").title(),
                description=desc,
                reference_prompt=prompt
            ))

        # Process prop tags
        for tag in validated_tags.prop_tags:
            desc = tag_descriptions.get(tag, f"Prop: {tag}")
            profile = tag_profiles.get(tag)
            prompt = self.generate_prompt(tag, TagCategory.PROP, desc, profile_data=profile)
            entries.append(TagReferenceEntry(
                tag=tag,
                category=TagCategory.PROP,
                display_name=tag.replace("PROP_", "").replace("_", " ").title(),
                description=desc,
                reference_prompt=prompt
            ))

        return entries


class TagReferenceRegistry:
    """
    Registry for tag reference images.

    Maintains the mapping between validated tags and their reference images
    for use in storyboard generation.
    """

    def __init__(self, project_path: Path = None):
        self.project_path = project_path
        self._entries: Dict[str, TagReferenceEntry] = {}
        self._registry_file = "tag_references.json"

    def add_entry(self, entry: TagReferenceEntry) -> None:
        """Add a tag reference entry."""
        self._entries[entry.tag] = entry
        logger.debug(f"Added tag reference: {entry.tag}")

    def get_entry(self, tag: str) -> Optional[TagReferenceEntry]:
        """Get a tag reference entry."""
        return self._entries.get(tag)

    def get_all_entries(self) -> List[TagReferenceEntry]:
        """Get all tag reference entries."""
        return list(self._entries.values())

    def get_entries_by_category(self, category: TagCategory) -> List[TagReferenceEntry]:
        """Get entries by category."""
        return [e for e in self._entries.values() if e.category == category]

    def get_pending_entries(self) -> List[TagReferenceEntry]:
        """Get entries that need reference images generated."""
        return [e for e in self._entries.values() if e.status == ReferenceImageStatus.PENDING]

    def update_image_path(self, tag: str, image_path: str) -> None:
        """Update the image path for a tag."""
        if tag in self._entries:
            self._entries[tag].image_path = image_path
            self._entries[tag].status = ReferenceImageStatus.GENERATED

    def save(self, path: Path = None) -> None:
        """Save the registry to a JSON file."""
        save_path = path or (self.project_path / "references" / self._registry_file if self.project_path else None)
        if not save_path:
            logger.warning("No save path specified for tag registry")
            return

        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "entries": {tag: entry.to_dict() for tag, entry in self._entries.items()},
            "saved_at": datetime.now().isoformat()
        }

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved tag registry with {len(self._entries)} entries to {save_path}")

    def load(self, path: Path = None) -> None:
        """Load the registry from a JSON file."""
        load_path = path or (self.project_path / "references" / self._registry_file if self.project_path else None)
        if not load_path or not load_path.exists():
            logger.debug("No existing tag registry to load")
            return

        with open(load_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for tag, entry_data in data.get("entries", {}).items():
            self._entries[tag] = TagReferenceEntry.from_dict(entry_data)

        logger.info(f"Loaded tag registry with {len(self._entries)} entries from {load_path}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert registry to dictionary."""
        return {
            "entries": {tag: entry.to_dict() for tag, entry in self._entries.items()},
            "count": len(self._entries),
            "by_category": {
                "characters": len(self.get_entries_by_category(TagCategory.CHARACTER)),
                "locations": len(self.get_entries_by_category(TagCategory.LOCATION)),
                "props": len(self.get_entries_by_category(TagCategory.PROP))
            }
        }


class TagReferenceSystem:
    """
    Complete Tag Reference System.

    Orchestrates:
    1. 10-Agent Consensus Tag Extraction
    2. Reference Image Prompt Generation
    3. Tag Reference Registry Management
    """

    def __init__(
        self,
        project_path: Path = None,
        llm_caller: Optional[Callable] = None,
        style_notes: str = "Cinematic, detailed, professional"
    ):
        self.project_path = project_path
        self.consensus_tagger = TenAgentConsensusTagger(llm_caller=llm_caller)
        self.prompt_generator = ReferencePromptGenerator(style_notes=style_notes)
        self.registry = TagReferenceRegistry(project_path=project_path)

        # Load existing registry if available
        if project_path:
            self.registry.load()

    async def extract_and_validate(
        self,
        content: str,
        tag_types: List[str] = None,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Extract and validate tags from content using 10-agent consensus.

        Args:
            content: The content to extract tags from
            tag_types: Optional filter for tag types
            context: Optional context for extraction

        Returns:
            Dictionary with validated tags and consensus info
        """
        validated = await self.consensus_tagger.extract_with_consensus(content, context)

        result = validated.to_dict()

        # Filter by tag types if specified
        if tag_types:
            if "character" not in tag_types:
                result["character_tags"] = []
            if "location" not in tag_types:
                result["location_tags"] = []
            if "prop" not in tag_types:
                result["prop_tags"] = []

        return result

    async def generate_reference_prompts(
        self,
        tags: List[str] = None,
        style_notes: str = None,
        tag_descriptions: Dict[str, str] = None,
        tag_profiles: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate reference image prompts for tags.

        Args:
            tags: Optional list of specific tags (uses all validated if None)
            style_notes: Optional style notes override
            tag_descriptions: Optional descriptions for tags
            tag_profiles: Optional expanded profile data keyed by tag

        Returns:
            Dictionary with generated prompts
        """
        if style_notes:
            self.prompt_generator.style_notes = style_notes

        tag_descriptions = tag_descriptions or {}
        tag_profiles = tag_profiles or {}

        # If specific tags provided, create a minimal ValidatedTagSet
        if tags:
            validated = ValidatedTagSet(
                character_tags=[t for t in tags if t.startswith("CHAR_") or not any(t.startswith(p) for p in ["LOC_", "PROP_"])],
                location_tags=[t for t in tags if t.startswith("LOC_")],
                prop_tags=[t for t in tags if t.startswith("PROP_")],
                concept_tags=[],
                event_tags=[],
                all_tags=tags,
                consensus_achieved=True,
                agent_agreement="manual"
            )
        else:
            # Use existing registry entries
            entries = self.registry.get_all_entries()
            return {
                "prompts": [e.to_dict() for e in entries],
                "count": len(entries)
            }

        # Generate prompts with expanded profile data
        entries = self.prompt_generator.generate_prompts_batch(validated, tag_descriptions, tag_profiles)

        # Add to registry
        for entry in entries:
            self.registry.add_entry(entry)

        # Save registry
        if self.project_path:
            self.registry.save()

        return {
            "prompts": [e.to_dict() for e in entries],
            "count": len(entries)
        }

    def get_reference_for_tag(self, tag: str) -> Optional[TagReferenceEntry]:
        """Get the reference entry for a specific tag."""
        return self.registry.get_entry(tag)

    def get_all_references(self) -> Dict[str, Any]:
        """Get all reference entries."""
        return self.registry.to_dict()

    def get_pending_references(self) -> List[TagReferenceEntry]:
        """Get references that need images generated."""
        return self.registry.get_pending_entries()

