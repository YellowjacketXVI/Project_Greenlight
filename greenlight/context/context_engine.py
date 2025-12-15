"""
Greenlight Context Engine

Enhanced context engine with RAG capabilities and story-aware retrieval.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from pathlib import Path

from greenlight.core.constants import TagCategory
from greenlight.core.logging_config import get_logger
from greenlight.tags import TagParser, TagRegistry
from greenlight.graph import DependencyGraph
from .vector_store import VectorStore, SearchResult
from .keyword_index import KeywordIndex, KeywordSearchResult
from .context_assembler import ContextAssembler, ContextItem, ContextSource, AssembledContext

logger = get_logger("context.engine")


@dataclass
class ContextQuery:
    """A query for context retrieval."""
    query_text: str
    tags: List[str] = field(default_factory=list)
    node_ids: List[str] = field(default_factory=list)
    sources: List[ContextSource] = field(default_factory=list)
    max_results: int = 10
    include_related: bool = True


@dataclass
class ContextResult:
    """Result from context retrieval."""
    assembled: AssembledContext
    vector_results: List[SearchResult]
    keyword_results: List[KeywordSearchResult]
    graph_context: Dict[str, Any]
    tags_found: Set[str]


class ContextEngine:
    """
    Enhanced context engine with RAG capabilities.

    Features:
    - Semantic search via vector store
    - Keyword search with fuzzy matching
    - Graph-based context traversal
    - Tag-aware retrieval
    - Story element tracking
    - Pipeline output tracking (Script, Visual_Script, world_config)
    - Tag reference registry integration
    """

    def __init__(
        self,
        vector_store: VectorStore = None,
        keyword_index: KeywordIndex = None,
        tag_registry: TagRegistry = None,
        dependency_graph: DependencyGraph = None,
        max_context_tokens: int = 50000
    ):
        """
        Initialize the context engine.

        Args:
            vector_store: Vector store for semantic search
            keyword_index: Keyword index for text search
            tag_registry: Tag registry for validation
            dependency_graph: Dependency graph for relationships
            max_context_tokens: Maximum context tokens
        """
        self.vector_store = vector_store or VectorStore()
        self.keyword_index = keyword_index or KeywordIndex()
        self.tag_registry = tag_registry or TagRegistry()
        self.graph = dependency_graph

        self.assembler = ContextAssembler(max_tokens=max_context_tokens)
        self.tag_parser = TagParser()

        self._world_bible: Dict[str, Any] = {}
        self._project_path: Optional[Path] = None

        # Pipeline output storage
        self._script: Optional[str] = None
        self._visual_script: Optional[str] = None
        self._world_config: Dict[str, Any] = {}
        self._tag_reference_registry: Dict[str, Any] = {}

    def set_project_path(self, project_path: Path) -> None:
        """Set the project path and reload project-specific data."""
        from pathlib import Path
        self._project_path = Path(project_path) if project_path else None

        if self._project_path:
            # Reload world bible if exists
            world_config_path = self._project_path / "world_bible" / "world_config.json"
            if world_config_path.exists():
                try:
                    import json
                    self._world_config = json.loads(world_config_path.read_text(encoding='utf-8'))
                except Exception:
                    pass

    def index_document(
        self,
        doc_id: str,
        content: str,
        doc_type: str = "general",
        **metadata
    ) -> None:
        """
        Index a document for retrieval.
        
        Args:
            doc_id: Document ID
            content: Document content
            doc_type: Type of document
            **metadata: Additional metadata
        """
        # Extract tags
        tags = self.tag_parser.extract_unique_tags(content)
        
        # Add to vector store
        self.vector_store.add(
            id=doc_id,
            text=content,
            doc_type=doc_type,
            tags=list(tags),
            **metadata
        )
        
        # Add to keyword index
        self.keyword_index.add(
            id=doc_id,
            text=content,
            doc_type=doc_type,
            tags=list(tags),
            **metadata
        )
        
        logger.debug(f"Indexed document: {doc_id} ({len(tags)} tags)")
    
    def load_world_bible(self, data: Dict[str, Any]) -> None:
        """
        Load world bible data.
        
        Args:
            data: World bible dictionary
        """
        self._world_bible = data
        
        # Register tags from world bible
        if 'characters' in data:
            for char in data['characters']:
                self.tag_registry.register(
                    name=char.get('tag', char.get('name', '').upper()),
                    category=TagCategory.CHARACTER,
                    description=char.get('description', ''),
                    visual_description=char.get('visual_description')
                )
        
        if 'locations' in data:
            for loc in data['locations']:
                self.tag_registry.register(
                    name=loc.get('tag', f"LOC_{loc.get('name', '').upper()}"),
                    category=TagCategory.LOCATION,
                    description=loc.get('description', '')
                )
        
        logger.info(f"Loaded world bible: {len(self.tag_registry.get_all_names())} tags")
    
    def retrieve(self, query: ContextQuery) -> ContextResult:
        """
        Retrieve context for a query.
        
        Args:
            query: Context query
            
        Returns:
            ContextResult with assembled context
        """
        items_by_source: Dict[ContextSource, List[ContextItem]] = {}
        
        # Vector search
        if not query.sources or ContextSource.VECTOR_SEARCH in query.sources:
            vector_results = self.vector_store.search(
                query.query_text,
                k=query.max_results
            )
            items_by_source[ContextSource.VECTOR_SEARCH] = [
                self.assembler.create_item(
                    id=r.id,
                    content=r.text,
                    source=ContextSource.VECTOR_SEARCH,
                    relevance_score=r.score,
                    **r.metadata
                )
                for r in vector_results
            ]
        else:
            vector_results = []
        
        # Keyword search
        if not query.sources or ContextSource.KEYWORD_SEARCH in query.sources:
            keyword_results = self.keyword_index.search(
                query.query_text,
                k=query.max_results,
                fuzzy=True
            )
            items_by_source[ContextSource.KEYWORD_SEARCH] = [
                self.assembler.create_item(
                    id=r.id,
                    content=r.text,
                    source=ContextSource.KEYWORD_SEARCH,
                    relevance_score=r.score,
                    matched_terms=r.matched_terms,
                    **r.metadata
                )
                for r in keyword_results
            ]
        else:
            keyword_results = []
        
        # World bible context
        if not query.sources or ContextSource.WORLD_BIBLE in query.sources:
            world_bible_items = self._get_world_bible_context(query.tags)
            items_by_source[ContextSource.WORLD_BIBLE] = world_bible_items
        
        # Graph context
        graph_context = {}
        if self.graph and query.node_ids:
            graph_context = self._get_graph_context(query.node_ids)
            if graph_context.get('items'):
                items_by_source[ContextSource.GRAPH_TRAVERSAL] = graph_context['items']
        
        # Assemble context
        assembled = self.assembler.assemble(items_by_source)
        
        # Collect all tags found
        tags_found = set()
        for item in assembled.items:
            tags_found.update(self.tag_parser.extract_unique_tags(item.content))
        
        return ContextResult(
            assembled=assembled,
            vector_results=vector_results,
            keyword_results=keyword_results,
            graph_context=graph_context,
            tags_found=tags_found
        )
    
    def _get_world_bible_context(self, tags: List[str]) -> List[ContextItem]:
        """Get context from world bible for specific tags."""
        items = []
        
        for tag in tags:
            if self.tag_registry.exists(tag):
                entry = self.tag_registry.get(tag)
                content = f"[{tag}]: {entry.description}"
                if entry.visual_description:
                    content += f"\nVisual: {entry.visual_description}"
                
                items.append(self.assembler.create_item(
                    id=f"wb_{tag}",
                    content=content,
                    source=ContextSource.WORLD_BIBLE,
                    relevance_score=1.0,
                    tag=tag,
                    category=entry.category.value
                ))
        
        return items
    
    def _get_graph_context(self, node_ids: List[str]) -> Dict[str, Any]:
        """Get context from dependency graph."""
        if not self.graph:
            return {}
        
        items = []
        related_nodes = set()
        
        for node_id in node_ids:
            try:
                node = self.graph.get_node(node_id)
                related_nodes.update(self.graph.get_dependencies(node_id))
                related_nodes.update(self.graph.get_dependents(node_id))
            except Exception:
                continue
        
        return {
            'items': items,
            'related_nodes': list(related_nodes)
        }

    # =========================================================================
    #  PIPELINE OUTPUT MANAGEMENT
    # =========================================================================

    def load_script(self, content: str) -> None:
        """
        Load Script output from Writer Pipeline.

        Args:
            content: The Script markdown content (scripts/script.md)
        """
        self._script = content

        # Index the script for retrieval
        self.index_document(
            doc_id="script",
            content=content,
            doc_type="script"
        )

        logger.info("Loaded Script into context engine")

    def load_visual_script(self, content: str) -> None:
        """
        Load Visual_Script output from Directing Pipeline.

        Args:
            content: The Visual_Script markdown content with frame notations
        """
        self._visual_script = content

        # Index the visual script for retrieval
        self.index_document(
            doc_id="visual_script",
            content=content,
            doc_type="visual_script"
        )

        logger.info("Loaded Visual_Script into context engine")

    def load_world_config(self, data: Dict[str, Any]) -> None:
        """
        Load world_config.json from World Bible Pipeline.

        Args:
            data: The world configuration dictionary
        """
        self._world_config = data

        # Register tags from world config
        if 'characters' in data:
            for char_tag, char_data in data.get('characters', {}).items():
                self.tag_registry.register(
                    name=char_tag,
                    category=TagCategory.CHARACTER,
                    description=char_data.get('description', ''),
                    visual_description=char_data.get('visual_description')
                )

        if 'locations' in data:
            for loc_tag, loc_data in data.get('locations', {}).items():
                self.tag_registry.register(
                    name=loc_tag,
                    category=TagCategory.LOCATION,
                    description=loc_data.get('description', '')
                )

        if 'props' in data:
            for prop_tag, prop_data in data.get('props', {}).items():
                self.tag_registry.register(
                    name=prop_tag,
                    category=TagCategory.PROP,
                    description=prop_data.get('description', '')
                )

        logger.info(f"Loaded world_config with {len(self.tag_registry.get_all_names())} tags")

    def load_tag_reference_registry(self, data: Dict[str, Any]) -> None:
        """
        Load tag reference registry from Tag Reference System.

        Args:
            data: The tag reference registry with validated tags and prompts
        """
        self._tag_reference_registry = data
        logger.info(f"Loaded tag reference registry with {len(data)} entries")

    def get_script(self) -> Optional[str]:
        """Get the current Script content."""
        return self._script

    def get_visual_script(self) -> Optional[str]:
        """Get the current Visual_Script content."""
        return self._visual_script

    def get_world_config(self) -> Dict[str, Any]:
        """Get the current world configuration."""
        return self._world_config

    def get_world_style(self) -> str:
        """
        Get the formatted world style suffix for image generation.

        Single source of truth for style information across all image generation pathways.
        Reads from world_config.json and formats into a consistent style suffix.

        Style suffix format:
            [visual_style_mapped]. [style_notes]. Lighting: [lighting]. Mood: [vibe]

        Returns:
            Formatted style suffix string for image prompts.
        """
        style_parts = []

        # 1. Visual style - map to descriptive text
        visual_style = self._world_config.get('visual_style', '')
        if visual_style:
            style_map = {
                'live_action': 'live action, photorealistic cinematography, 8k quality, dynamic lighting, real life subjects, photographic, practical effects, natural skin texture, realistic materials, film grain, shallow depth of field, RAW photo, DSLR quality',
                'anime': 'anime style, cel-shaded, vibrant colors, expressive characters, bold linework, stylized proportions, clean vector art, high contrast colors, dynamic action lines',
                'animation_2d': 'hand-drawn 2D animation, traditional animation aesthetic, painted backgrounds, fluid motion, artistic linework, watercolor textures, gouache painting, illustrated',
                'animation_3d': '3D CGI rendering, subsurface scattering, global illumination, volumetric lighting, high-poly models, realistic textures, ray tracing, cinematic 3D animation',
                'mixed_reality': 'mixed reality, seamless blend of live action and CGI, photorealistic integration, matched lighting, HDR compositing, practical and digital fusion, photoreal CGI characters'
            }
            mapped_style = style_map.get(visual_style, visual_style)
            style_parts.append(mapped_style)

        # 2. Style notes - custom user description
        style_notes = self._world_config.get('style_notes', '')
        if style_notes and style_notes.strip():
            style_parts.append(style_notes.strip())

        # 3. Lighting
        lighting = self._world_config.get('lighting', '')
        if lighting and lighting.strip():
            style_parts.append(f"Lighting: {lighting.strip()}")

        # 4. Vibe/Mood
        vibe = self._world_config.get('vibe', '')
        if vibe and vibe.strip():
            style_parts.append(f"Mood: {vibe.strip()}")

        if style_parts:
            return ". ".join(style_parts)
        return ""

    def get_tag_reference_registry(self) -> Dict[str, Any]:
        """Get the tag reference registry."""
        return self._tag_reference_registry

    def get_pipeline_context(self, pipeline_type: str) -> Optional[str]:
        """
        Get context for a specific pipeline type.

        Args:
            pipeline_type: One of 'script', 'visual_script', 'world_config'

        Returns:
            The content or None if not loaded
        """
        if pipeline_type == 'script':
            return self._script
        elif pipeline_type == 'visual_script':
            return self._visual_script
        elif pipeline_type == 'world_config':
            import json
            return json.dumps(self._world_config, indent=2) if self._world_config else None
        return None

    def get_all_pipeline_outputs(self) -> Dict[str, Any]:
        """Get summary of all loaded pipeline outputs."""
        return {
            'script': {
                'loaded': self._script is not None,
                'length': len(self._script) if self._script else 0
            },
            'visual_script': {
                'loaded': self._visual_script is not None,
                'length': len(self._visual_script) if self._visual_script else 0
            },
            'world_config': {
                'loaded': bool(self._world_config),
                'characters': len(self._world_config.get('characters', {})),
                'locations': len(self._world_config.get('locations', {})),
                'props': len(self._world_config.get('props', {}))
            },
            'tag_reference_registry': {
                'loaded': bool(self._tag_reference_registry),
                'entries': len(self._tag_reference_registry)
            }
        }

    # =========================================================================
    # NOTATION STANDARDS PROVIDER
    # =========================================================================

    def get_notation_standards(self, include_examples: bool = True) -> str:
        """
        Get the canonical notation standards for injection into LLM prompts.

        This is the SINGLE SOURCE OF TRUTH for notation formats.
        All pipelines should use this method to ensure consistent notation.

        Args:
            include_examples: Whether to include concrete examples

        Returns:
            Notation standards string for prompt injection
        """
        standards = """
=== NOTATION STANDARDS (MANDATORY) ===

## TAG FORMAT
ALL tags MUST be wrapped in square brackets with uppercase prefix and name.

| Prefix | Category | Format |
|--------|----------|--------|
| CHAR_ | Characters | [CHAR_FIRSTNAME] or [CHAR_THE_TITLE] |
| LOC_ | Locations | [LOC_PLACE_NAME] |
| PROP_ | Props | [PROP_ITEM_NAME] |
| CONCEPT_ | Concepts | [CONCEPT_THEME] |
| EVENT_ | Events | [EVENT_OCCURRENCE] |
| ENV_ | Environment | [ENV_CONDITION] |

**CRITICAL RULES:**
1. ALL tags MUST have square brackets: [TAG_NAME]
2. ALL tags MUST have category prefix: CHAR_, LOC_, PROP_, etc.
3. ALL tags MUST be UPPERCASE with underscores for spaces
4. Tags are LITERAL identifiers, NOT placeholders
"""

        if include_examples:
            standards += """
**CORRECT Examples:**
- [CHAR_MEI] - Character named Mei
- [CHAR_THE_GENERAL] - Titled character
- [LOC_LIXUAN_BROTHEL] - Specific location
- [LOC_FLOWER_SHOP] - Location type
- [PROP_GO_BOARD] - Prop item
- [PROP_BLUE_SILK_KIMONO] - Descriptive prop
- [CONCEPT_FREEDOM] - Abstract concept
- [EVENT_GO_GAME] - Story event

**INCORRECT (DO NOT USE):**
- ❌ CHAR_MEI (missing brackets)
- ❌ [Mei] (missing prefix)
- ❌ [char_mei] (lowercase)
- ❌ [CHARACTER_MEI] (wrong prefix)
- ❌ Mei (no formatting at all)

## SCENE.FRAME.CAMERA NOTATION
Format: {scene}.{frame}.c{letter}

- Scene: Integer (1, 2, 3...)
- Frame: Integer (1, 2, 3...)
- Camera: Letter with 'c' prefix (cA, cB, cC...)

**Examples:**
- 1.1.cA = Scene 1, Frame 1, Camera A
- 2.3.cB = Scene 2, Frame 3, Camera B
- 8.5.cD = Scene 8, Frame 5, Camera D

**Camera Block Format:**
[1.2.cA] (Wide)
Description of the shot...
"""

        return standards

    def get_tag_format_rules(self) -> str:
        """
        Get just the tag format rules (shorter version for token efficiency).

        Returns:
            Compact tag format rules string
        """
        return """
## TAG FORMAT (MANDATORY)
- ALL tags MUST use square brackets: [TAG_NAME]
- ALL tags MUST have prefix: CHAR_, LOC_, PROP_, CONCEPT_, EVENT_, ENV_
- ALL tags MUST be UPPERCASE with underscores
- Examples: [CHAR_MEI], [LOC_PALACE], [PROP_SWORD], [CONCEPT_HONOR]
"""

    def inject_notation_standards(self, prompt: str, position: str = "start") -> str:
        """
        Inject notation standards into a prompt.

        Args:
            prompt: The original prompt
            position: Where to inject - "start", "end", or "both"

        Returns:
            Prompt with notation standards injected
        """
        standards = self.get_tag_format_rules()

        if position == "start":
            return f"{standards}\n\n{prompt}"
        elif position == "end":
            return f"{prompt}\n\n{standards}"
        elif position == "both":
            return f"{standards}\n\n{prompt}\n\n{standards}"
        else:
            return f"{standards}\n\n{prompt}"

    # =========================================================================
    # @-MENTION TO [TAG] CONVERSION
    # =========================================================================

    def convert_mentions_to_tags(self, text: str, default_prefix: str = "CHAR") -> str:
        """
        Convert @-mentions to canonical [TAG] format.

        Converts social media-style @mentions (e.g., @Mei, @Palace) to
        canonical tag notation (e.g., [CHAR_MEI], [LOC_PALACE]).

        Args:
            text: Text containing @-mentions
            default_prefix: Default tag prefix if not specified (CHAR, LOC, PROP, etc.)

        Returns:
            Text with @-mentions converted to [TAG] format
        """
        import re

        def replace_mention(match):
            mention = match.group(1)
            # Check if mention has a prefix hint (e.g., @loc:Palace, @prop:Sword)
            if ':' in mention:
                prefix_hint, name = mention.split(':', 1)
                prefix = prefix_hint.upper()
                # Validate prefix
                valid_prefixes = ['CHAR', 'LOC', 'PROP', 'CONCEPT', 'EVENT', 'ENV']
                if prefix not in valid_prefixes:
                    prefix = default_prefix
            else:
                name = mention
                prefix = default_prefix

            # Convert name to tag format (uppercase, underscores for spaces)
            tag_name = re.sub(r'[^A-Za-z0-9]', '_', name).upper()
            tag_name = re.sub(r'_+', '_', tag_name).strip('_')

            return f"[{prefix}_{tag_name}]"

        # Pattern: @Name or @prefix:Name (case-insensitive prefix)
        # Matches: @Mei, @The_General, @loc:Palace, @prop:Sword
        pattern = r'@([A-Za-z][A-Za-z0-9_:]*)'

        return re.sub(pattern, replace_mention, text)

    def extract_mentions(self, text: str) -> List[Dict[str, str]]:
        """
        Extract @-mentions from text and return as structured data.

        Args:
            text: Text containing @-mentions

        Returns:
            List of dicts with 'mention', 'prefix', 'name', 'tag' keys
        """
        import re

        mentions = []
        pattern = r'@([A-Za-z][A-Za-z0-9_:]*)'

        for match in re.finditer(pattern, text):
            mention = match.group(1)

            if ':' in mention:
                prefix_hint, name = mention.split(':', 1)
                prefix = prefix_hint.upper()
                valid_prefixes = ['CHAR', 'LOC', 'PROP', 'CONCEPT', 'EVENT', 'ENV']
                if prefix not in valid_prefixes:
                    prefix = 'CHAR'
            else:
                name = mention
                prefix = 'CHAR'

            tag_name = re.sub(r'[^A-Za-z0-9]', '_', name).upper()
            tag_name = re.sub(r'_+', '_', tag_name).strip('_')

            mentions.append({
                'mention': f"@{mention}",
                'prefix': prefix,
                'name': name,
                'tag': f"[{prefix}_{tag_name}]"
            })

        return mentions

    def validate_and_convert_tags(self, text: str) -> str:
        """
        Validate existing tags and convert @-mentions in one pass.

        This is the primary method for processing user input that may contain
        both @-mentions and existing [TAG] notation.

        Args:
            text: Text with mixed @-mentions and [TAG] notation

        Returns:
            Text with all @-mentions converted to [TAG] format
        """
        # First convert @-mentions
        converted = self.convert_mentions_to_tags(text)

        # Log any tags found for debugging
        tags = self.tag_parser.extract_unique_tags(converted)
        if tags:
            logger.debug(f"Tags found after conversion: {tags}")

        return converted

    # =========================================================================
    # WORLD DETAILS CONTEXT PROVIDER
    # =========================================================================

    def get_world_details(self) -> Dict[str, Any]:
        """
        Get the world_details section from world_config.

        Returns:
            world_details dictionary or empty dict if not available
        """
        return self._world_config.get('world_details', {})

    def get_world_context_for_tag_generation(self) -> str:
        """
        Get full world context formatted for TAG generation prompts.

        This context should be injected into all [CHAR_*], [LOC_*], [PROP_*]
        generation prompts to ensure period-accurate, culturally-consistent output.

        Returns:
            Formatted world context string for prompt injection
        """
        world_details = self.get_world_details()
        if not world_details:
            # Fallback to basic world config fields
            return self._get_basic_world_context()

        time_period = world_details.get('time_period', {})
        cultural = world_details.get('cultural_context', {})
        economic = world_details.get('economic_context', {})
        aesthetic = world_details.get('aesthetic_context', {})

        context_parts = ["=== WORLD CONTEXT (Use this for ALL decisions) ==="]

        # Time Period
        if time_period:
            context_parts.append(f"\n## TIME PERIOD")
            context_parts.append(f"Era: {time_period.get('era', 'Not specified')}")
            if time_period.get('historical_events'):
                context_parts.append(f"Historical Events: {', '.join(time_period['historical_events'])}")
            if time_period.get('technology_level'):
                context_parts.append(f"Technology: {time_period['technology_level']}")
            if time_period.get('medicine_understanding'):
                context_parts.append(f"Medicine: {time_period['medicine_understanding']}")
            if time_period.get('transportation'):
                context_parts.append(f"Transportation: {time_period['transportation']}")

        # Cultural Context
        if cultural:
            context_parts.append(f"\n## CULTURAL CONTEXT")
            if cultural.get('social_hierarchy'):
                hierarchy = cultural['social_hierarchy']
                if isinstance(hierarchy, list):
                    context_parts.append(f"Social Hierarchy: {' > '.join(hierarchy)}")
                else:
                    context_parts.append(f"Social Hierarchy: {hierarchy}")
            if cultural.get('gender_roles'):
                context_parts.append(f"Gender Roles: {cultural['gender_roles']}")
            if cultural.get('religion_philosophy'):
                context_parts.append(f"Religion/Philosophy: {', '.join(cultural['religion_philosophy'])}")
            if cultural.get('taboos'):
                context_parts.append(f"Taboos: {', '.join(cultural['taboos'])}")
            if cultural.get('customs'):
                context_parts.append(f"Customs: {', '.join(cultural['customs'])}")
            if cultural.get('language_register'):
                lang = cultural['language_register']
                if isinstance(lang, dict):
                    context_parts.append(f"Language - Formal: {lang.get('formal', '')}")
                    context_parts.append(f"Language - Informal: {lang.get('informal', '')}")

        # Economic Context
        if economic:
            context_parts.append(f"\n## ECONOMIC CONTEXT")
            if economic.get('currency'):
                context_parts.append(f"Currency: {economic['currency']}")
            if economic.get('trade_goods'):
                context_parts.append(f"Trade Goods: {', '.join(economic['trade_goods'])}")

        # Aesthetic Context
        if aesthetic:
            context_parts.append(f"\n## AESTHETIC CONTEXT")
            if aesthetic.get('architecture'):
                context_parts.append(f"Architecture: {aesthetic['architecture']}")
            if aesthetic.get('fashion'):
                context_parts.append(f"Fashion: {aesthetic['fashion']}")
            if aesthetic.get('art_forms'):
                context_parts.append(f"Art Forms: {', '.join(aesthetic['art_forms'])}")
            if aesthetic.get('color_symbolism'):
                colors = aesthetic['color_symbolism']
                if isinstance(colors, dict):
                    color_str = "; ".join([f"{k}: {v}" for k, v in colors.items()])
                    context_parts.append(f"Color Symbolism: {color_str}")

        # Add top-level style info
        context_parts.append(f"\n## VISUAL STYLE")
        context_parts.append(f"Style: {self._world_config.get('visual_style', 'Not specified')}")
        context_parts.append(f"Style Notes: {self._world_config.get('style_notes', '')}")
        context_parts.append(f"Lighting: {self._world_config.get('lighting', '')}")
        context_parts.append(f"Vibe: {self._world_config.get('vibe', '')}")

        # Themes and world rules
        if self._world_config.get('themes'):
            themes = self._world_config['themes']
            if isinstance(themes, list):
                context_parts.append(f"\n## THEMES: {', '.join(themes)}")
            else:
                context_parts.append(f"\n## THEMES: {themes}")

        if self._world_config.get('world_rules'):
            context_parts.append(f"\n## WORLD RULES: {self._world_config['world_rules']}")

        context_parts.append("\n\nCRITICAL: All generated content MUST be authentic to the time period and cultural context above. Avoid anachronisms.")

        return "\n".join(context_parts)

    def _get_basic_world_context(self) -> str:
        """Fallback world context from basic world_config fields."""
        parts = ["=== WORLD CONTEXT ==="]

        if self._world_config.get('time_period'):
            parts.append(f"Time Period: {self._world_config['time_period']}")
        if self._world_config.get('genre'):
            parts.append(f"Genre: {self._world_config['genre']}")
        if self._world_config.get('visual_style'):
            parts.append(f"Visual Style: {self._world_config['visual_style']}")
        if self._world_config.get('style_notes'):
            parts.append(f"Style Notes: {self._world_config['style_notes']}")
        if self._world_config.get('themes'):
            themes = self._world_config['themes']
            if isinstance(themes, list):
                parts.append(f"Themes: {', '.join(themes)}")
            else:
                parts.append(f"Themes: {themes}")

        return "\n".join(parts)

    # =========================================================================
    # CHARACTER EMBODIMENT CONTEXT METHODS
    # =========================================================================

    def get_character_profile(self, character_tag: str) -> Optional[Dict[str, Any]]:
        """
        Get full character profile from world_config.

        Args:
            character_tag: The character tag (e.g., "CHAR_MEI")

        Returns:
            Full character profile dictionary or None
        """
        characters = self._world_config.get('characters', [])
        # Handle both list format (with 'tag' field) and dict format (keyed by tag)
        if isinstance(characters, list):
            for char in characters:
                if char.get('tag') == character_tag:
                    return char
            return None
        else:
            # Legacy dict format
            return characters.get(character_tag)

    def get_location_profile(self, location_tag: str) -> Optional[Dict[str, Any]]:
        """
        Get full location profile from world_config.

        Args:
            location_tag: The location tag (e.g., "LOC_BROTHEL")

        Returns:
            Full location profile dictionary or None
        """
        locations = self._world_config.get('locations', [])
        # Handle both list format (with 'tag' field) and dict format (keyed by tag)
        if isinstance(locations, list):
            for loc in locations:
                if loc.get('tag') == location_tag:
                    return loc
            return None
        else:
            # Legacy dict format
            return locations.get(location_tag)

    def get_prop_profile(self, prop_tag: str) -> Optional[Dict[str, Any]]:
        """
        Get full prop profile from world_config.

        Args:
            prop_tag: The prop tag (e.g., "PROP_GO_BOARD")

        Returns:
            Full prop profile dictionary or None
        """
        props = self._world_config.get('props', [])
        # Handle both list format (with 'tag' field) and dict format (keyed by tag)
        if isinstance(props, list):
            for prop in props:
                if prop.get('tag') == prop_tag:
                    return prop
            return None
        else:
            # Legacy dict format
            return props.get(prop_tag)

    # =========================================================================
    # REFERENCE PROMPT STORAGE AND RETRIEVAL
    # =========================================================================

    def get_reference_sheet_prompt(self, tag: str) -> Optional[str]:
        """
        Get stored reference sheet prompt for a character or prop tag.

        Args:
            tag: The tag (e.g., "CHAR_MEI", "PROP_SWORD")

        Returns:
            Stored reference sheet prompt or None
        """
        try:
            entry = self.tag_registry.get(tag)
            return entry.reference_sheet_prompt
        except Exception:
            return None

    def get_reference_prompts(self, tag: str) -> Optional[Dict[str, str]]:
        """
        Get stored directional reference prompts for a location tag.

        Args:
            tag: The location tag (e.g., "LOC_PALACE")

        Returns:
            Dict with keys "north", "east", "south", "west" or None
        """
        try:
            entry = self.tag_registry.get(tag)
            return entry.reference_prompts if entry.reference_prompts else None
        except Exception:
            return None

    def store_reference_sheet_prompt(self, tag: str, prompt: str) -> bool:
        """
        Store a reference sheet prompt for a character or prop tag.

        Args:
            tag: The tag (e.g., "CHAR_MEI", "PROP_SWORD")
            prompt: The LLM-generated reference sheet prompt

        Returns:
            True if stored successfully
        """
        try:
            self.tag_registry.update(tag, reference_sheet_prompt=prompt)
            logger.info(f"Stored reference sheet prompt for {tag}")
            return True
        except Exception as e:
            logger.error(f"Failed to store reference sheet prompt for {tag}: {e}")
            return False

    def store_reference_prompts(self, tag: str, prompts: Dict[str, str]) -> bool:
        """
        Store directional reference prompts for a location tag.

        Args:
            tag: The location tag (e.g., "LOC_PALACE")
            prompts: Dict with keys "north", "east", "south", "west"

        Returns:
            True if stored successfully
        """
        try:
            self.tag_registry.update(tag, reference_prompts=prompts)
            logger.info(f"Stored directional reference prompts for {tag}")
            return True
        except Exception as e:
            logger.error(f"Failed to store reference prompts for {tag}: {e}")
            return False

    def get_entity_data_for_reference(
        self,
        tag: str,
        category: "TagCategory"
    ) -> Optional[Dict[str, Any]]:
        """
        Get entity data suitable for reference prompt generation.

        Args:
            tag: The tag identifier
            category: Tag category (CHARACTER, LOCATION, PROP)

        Returns:
            Entity data dict or None
        """
        from greenlight.core.constants import TagCategory as TC

        if category == TC.CHARACTER:
            return self.get_character_profile(tag)
        elif category == TC.LOCATION:
            return self.get_location_profile(tag)
        elif category == TC.PROP:
            return self.get_prop_profile(tag)
        return None

    def for_character_embodiment_agent(
        self,
        character_tag: str,
        scene_context: Dict[str, Any],
        relationship_states: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get full character profile for embodiment agents.

        No compression - provides complete character data for agents that need
        to convincingly inhabit a character for dialogue, movement, and decisions.

        Args:
            character_tag: The character tag (e.g., "CHAR_MEI")
            scene_context: Current scene information (location, present characters, goal)
            relationship_states: Optional current relationship states

        Returns:
            Full context string for character embodiment
        """
        import json

        profile = self.get_character_profile(character_tag)
        if not profile:
            return f"Character profile not found for {character_tag}"

        world_context = self.get_world_context_for_tag_generation()

        parts = [
            "=== CHARACTER EMBODIMENT CONTEXT ===",
            f"\nCHARACTER: [{character_tag}]",
            f"\n{world_context}",
            f"\n=== FULL CHARACTER PROFILE ===",
            json.dumps(profile, indent=2, ensure_ascii=False),
        ]

        # Add scene context
        if scene_context:
            parts.append(f"\n=== CURRENT SCENE ===")
            parts.append(json.dumps(scene_context, indent=2, ensure_ascii=False))

        # Add relationship states
        if relationship_states:
            parts.append(f"\n=== RELATIONSHIP STATES ===")
            parts.append(json.dumps(relationship_states, indent=2, ensure_ascii=False))

        return "\n".join(parts)

    def for_dialogue_agent(
        self,
        speaking_character: str,
        listening_characters: List[str],
        scene_context: Dict[str, Any]
    ) -> str:
        """
        Get context for dialogue generation agents.

        Focuses on speech patterns, relationships, and world context
        to generate authentic character dialogue.

        Args:
            speaking_character: Tag of the speaking character
            listening_characters: Tags of characters being spoken to
            scene_context: Current scene information

        Returns:
            Context string optimized for dialogue generation
        """
        import json

        speaker_profile = self.get_character_profile(speaking_character)
        if not speaker_profile:
            return f"Speaker profile not found for {speaking_character}"

        parts = [
            "=== DIALOGUE GENERATION CONTEXT ===",
            f"\nSPEAKER: [{speaking_character}]",
            f"LISTENERS: {', '.join([f'[{c}]' for c in listening_characters])}",
        ]

        # Add world context (language register is critical for dialogue)
        world_details = self.get_world_details()
        if world_details.get('cultural_context', {}).get('language_register'):
            lang = world_details['cultural_context']['language_register']
            parts.append(f"\n=== LANGUAGE REGISTER ===")
            if isinstance(lang, dict):
                parts.append(f"Formal: {lang.get('formal', '')}")
                parts.append(f"Informal: {lang.get('informal', '')}")
                if lang.get('forbidden_words'):
                    parts.append(f"Forbidden: {', '.join(lang['forbidden_words'])}")

        # Add speaker's speech patterns
        if speaker_profile.get('speech'):
            parts.append(f"\n=== SPEAKER'S SPEECH PATTERNS ===")
            parts.append(json.dumps(speaker_profile['speech'], indent=2, ensure_ascii=False))

        # Add speaker's relationships to listeners
        if speaker_profile.get('relationships'):
            relevant_rels = {}
            for listener in listening_characters:
                if listener in speaker_profile['relationships']:
                    relevant_rels[listener] = speaker_profile['relationships'][listener]
            if relevant_rels:
                parts.append(f"\n=== RELATIONSHIPS TO LISTENERS ===")
                parts.append(json.dumps(relevant_rels, indent=2, ensure_ascii=False))

        # Add scene context
        if scene_context:
            parts.append(f"\n=== SCENE CONTEXT ===")
            parts.append(json.dumps(scene_context, indent=2, ensure_ascii=False))

        return "\n".join(parts)

    def for_movement_agent(
        self,
        character_tag: str,
        emotional_state: str,
        scene_context: Dict[str, Any]
    ) -> str:
        """
        Get context for movement/gesture generation agents.

        Focuses on physicality and emotional tells for the specific
        emotional state to generate authentic physical behavior.

        Args:
            character_tag: The character tag
            emotional_state: Current emotional state (e.g., "nervousness", "confidence")
            scene_context: Current scene information

        Returns:
            Context string optimized for movement generation
        """
        import json

        profile = self.get_character_profile(character_tag)
        if not profile:
            return f"Character profile not found for {character_tag}"

        parts = [
            "=== MOVEMENT GENERATION CONTEXT ===",
            f"\nCHARACTER: [{character_tag}]",
            f"EMOTIONAL STATE: {emotional_state}",
        ]

        # Add physicality section
        if profile.get('physicality'):
            parts.append(f"\n=== PHYSICALITY ===")
            parts.append(json.dumps(profile['physicality'], indent=2, ensure_ascii=False))

        # Add specific emotional tell for current state
        if profile.get('emotional_tells'):
            tells = profile['emotional_tells']
            if emotional_state in tells:
                parts.append(f"\n=== EMOTIONAL TELL FOR '{emotional_state.upper()}' ===")
                parts.append(tells[emotional_state])
            # Also include related tells
            related_states = self._get_related_emotional_states(emotional_state)
            for state in related_states:
                if state in tells and state != emotional_state:
                    parts.append(f"\n=== RELATED TELL: '{state}' ===")
                    parts.append(tells[state])

        # Add emotional baseline
        if profile.get('emotional_baseline'):
            parts.append(f"\n=== EMOTIONAL BASELINE ===")
            parts.append(json.dumps(profile['emotional_baseline'], indent=2, ensure_ascii=False))

        # Add scene context
        if scene_context:
            parts.append(f"\n=== SCENE CONTEXT ===")
            parts.append(json.dumps(scene_context, indent=2, ensure_ascii=False))

        return "\n".join(parts)

    def _get_related_emotional_states(self, state: str) -> List[str]:
        """Get related emotional states for context."""
        # Emotional state clusters
        clusters = {
            'nervousness': ['fear', 'anxiety', 'embarrassment'],
            'confidence': ['pride', 'triumph', 'focus'],
            'anger': ['frustration', 'contempt', 'annoyance'],
            'sadness': ['loneliness', 'defeat', 'rejection'],
            'happiness': ['joy', 'excitement', 'belonging'],
            'fear': ['nervousness', 'anxiety', 'vulnerability'],
            'attraction': ['crush', 'intimacy', 'admiration'],
            'shame': ['guilt', 'embarrassment', 'defeat'],
        }
        return clusters.get(state, [])

