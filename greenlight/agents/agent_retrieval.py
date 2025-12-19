"""
Agent Retrieval Tool - Entry Points for Agent Context Access

Provides standardized entry points for agents to:
1. Query the context engine for relevant information
2. Access project data (world bible, tags, scripts)
3. Retrieve related content by tag or topic
4. Get pipeline status and results

This serves as the agent's "personal retrieval tool" - a unified interface
for all context and data access needs.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
from pathlib import Path
from enum import Enum

from greenlight.core.logging_config import get_logger

logger = get_logger("agents.retrieval")

# Lazy imports to avoid circular dependencies
_context_module = None
_ContextEngine = None
_ContextQuery = None
_ContextSource = None


def _get_context_classes():
    """Lazy load context classes to avoid circular imports."""
    global _context_module, _ContextEngine, _ContextQuery, _ContextSource
    if _context_module is None:
        from greenlight.context import context_engine as _context_module
        _ContextEngine = _context_module.ContextEngine
        _ContextQuery = _context_module.ContextQuery
        _ContextSource = _context_module.ContextSource
    return _ContextEngine, _ContextQuery, _ContextSource


class RetrievalScope(Enum):
    """Scope of retrieval query."""
    PROJECT = "project"           # Current project only
    WORLD_BIBLE = "world_bible"   # World bible data
    STORY = "story"               # Story documents
    STORYBOARD = "storyboard"     # Storyboard/visual data
    TAGS = "tags"                 # Tag registry
    ALL = "all"                   # All sources


@dataclass
class RetrievalResult:
    """Result from a retrieval query."""
    success: bool
    content: str = ""
    items: List[Dict[str, Any]] = field(default_factory=list)
    tags_found: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    token_count: int = 0
    error: Optional[str] = None


class AgentRetrievalTool:
    """
    Unified retrieval interface for agents.

    Provides entry points for:
    - Context queries (semantic search)
    - Tag lookups
    - Project file access
    - World bible queries
    - Pipeline result access
    """

    def __init__(
        self,
        context_engine: Any = None,
        project_path: Path = None,
        tag_registry: Any = None
    ):
        ContextEngine, _, _ = _get_context_classes()
        self.context_engine = context_engine or ContextEngine()
        self.project_path = Path(project_path) if project_path else None
        self.tag_registry = tag_registry
        self._cache: Dict[str, RetrievalResult] = {}

        # Ensure ContextEngine has project path set if provided
        if self.project_path and hasattr(self.context_engine, 'set_project_path'):
            self.context_engine.set_project_path(self.project_path)

    def set_project(self, project_path: Path) -> None:
        """Set the current project path."""
        self.project_path = Path(project_path) if project_path else None
        self._cache.clear()

        # Update ContextEngine project path
        if self.project_path and hasattr(self.context_engine, 'set_project_path'):
            self.context_engine.set_project_path(self.project_path)

    # =========================================================================
    # CORE RETRIEVAL METHODS
    # =========================================================================

    async def query(
        self,
        query_text: str,
        scope: RetrievalScope = RetrievalScope.ALL,
        max_results: int = 10,
        tags: List[str] = None
    ) -> RetrievalResult:
        """
        Query the context engine for relevant information.

        Args:
            query_text: Natural language query
            scope: Scope to search within
            max_results: Maximum results to return
            tags: Optional tags to filter by

        Returns:
            RetrievalResult with matched content
        """
        try:
            # Map scope to context sources
            sources = self._scope_to_sources(scope)

            _, ContextQuery, _ = _get_context_classes()
            query = ContextQuery(
                query_text=query_text,
                tags=tags or [],
                max_results=max_results,
                sources=sources
            )

            result = self.context_engine.retrieve(query)

            return RetrievalResult(
                success=True,
                content=result.assembled.full_text,
                items=[{
                    "id": item.id,
                    "content": item.content[:500],  # Truncate for summary
                    "source": item.source.value,
                    "relevance": item.relevance_score
                } for item in result.assembled.items],
                tags_found=list(result.tags_found),
                sources_used=[s.value for s in result.assembled.sources_used],
                token_count=result.assembled.total_tokens
            )
        except Exception as e:
            logger.error(f"Retrieval query failed: {e}")
            return RetrievalResult(success=False, error=str(e))

    async def get_by_tag(self, tag: str) -> RetrievalResult:
        """Get all content related to a specific tag."""
        return await self.query(
            query_text=f"Find all information about [{tag}]",
            tags=[tag],
            max_results=20
        )

    async def get_world_bible_entry(self, tag: str) -> RetrievalResult:
        """Get world bible entry for a tag."""
        if not self.project_path:
            return RetrievalResult(success=False, error="No project loaded")

        try:
            wb_path = self.project_path / "world_bible" / "WORLD_BIBLE.json"
            if not wb_path.exists():
                return RetrievalResult(success=False, error="World bible not found")

            import json
            wb_data = json.loads(wb_path.read_text(encoding='utf-8'))

            # Search for tag in characters, locations, props
            for category in ['characters', 'locations', 'props']:
                for entry in wb_data.get(category, []):
                    if entry.get('tag') == tag:
                        return RetrievalResult(
                            success=True,
                            content=json.dumps(entry, indent=2),
                            items=[entry],
                            tags_found=[tag],
                            sources_used=["world_bible"]
                        )

            return RetrievalResult(success=False, error=f"Tag {tag} not found in world bible")
        except Exception as e:
            return RetrievalResult(success=False, error=str(e))

    async def get_script_content(self, script_type: str = "script") -> RetrievalResult:
        """
        Get script content from the project.

        Args:
            script_type: Type of script - "script", "visual_script", "pitch"
        """
        if not self.project_path:
            return RetrievalResult(success=False, error="No project loaded")

        try:
            # Map script type to file path
            script_paths = {
                "script": self.project_path / "scripts" / "script.md",
                "visual_script": self.project_path / "storyboard" / "visual_script.md",
                "pitch": self.project_path / "world_bible" / "pitch.md",
            }

            path = script_paths.get(script_type)
            if not path or not path.exists():
                return RetrievalResult(success=False, error=f"Script {script_type} not found")

            content = path.read_text(encoding='utf-8')
            return RetrievalResult(
                success=True,
                content=content,
                sources_used=[script_type],
                token_count=len(content.split())
            )
        except Exception as e:
            return RetrievalResult(success=False, error=str(e))

    async def get_related_tags(self, tag: str) -> RetrievalResult:
        """Get tags related to a given tag (co-occurrences, relationships)."""
        if not self.tag_registry:
            return RetrievalResult(success=False, error="Tag registry not available")

        try:
            # Get tag info
            tag_info = self.tag_registry.get_tag(tag)
            if not tag_info:
                return RetrievalResult(success=False, error=f"Tag {tag} not found")

            # Find related tags from registry
            related = []
            if hasattr(tag_info, 'relationships'):
                related = list(tag_info.relationships.keys())

            return RetrievalResult(
                success=True,
                content=f"Related tags for [{tag}]: {', '.join(related)}",
                tags_found=related,
                sources_used=["tag_registry"]
            )
        except Exception as e:
            return RetrievalResult(success=False, error=str(e))

    async def get_pipeline_results(self, pipeline_name: str) -> RetrievalResult:
        """Get results from a specific pipeline run."""
        if not self.project_path:
            return RetrievalResult(success=False, error="No project loaded")

        try:
            # Check for pipeline output files
            output_paths = {
                "story": self.project_path / "scripts" / "script.md",
                "directing": self.project_path / "storyboard" / "visual_script.md",
                "world_bible": self.project_path / "world_bible" / "WORLD_BIBLE.json",
                "storyboard": self.project_path / "storyboard" / "shot_list.json",
            }

            path = output_paths.get(pipeline_name)
            if not path or not path.exists():
                return RetrievalResult(success=False, error=f"No output found for {pipeline_name}")

            content = path.read_text(encoding='utf-8')
            return RetrievalResult(
                success=True,
                content=content,
                sources_used=[pipeline_name],
                token_count=len(content.split())
            )
        except Exception as e:
            return RetrievalResult(success=False, error=str(e))

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _scope_to_sources(self, scope: RetrievalScope) -> Optional[List[Any]]:
        """Map retrieval scope to context sources."""
        if scope == RetrievalScope.ALL:
            return None  # All sources

        _, _, ContextSource = _get_context_classes()
        scope_map = {
            RetrievalScope.PROJECT: [ContextSource.VECTOR_SEARCH, ContextSource.KEYWORD_SEARCH],
            RetrievalScope.WORLD_BIBLE: [ContextSource.WORLD_BIBLE],
            RetrievalScope.STORY: [ContextSource.VECTOR_SEARCH],
            RetrievalScope.STORYBOARD: [ContextSource.VECTOR_SEARCH],
            RetrievalScope.TAGS: [ContextSource.WORLD_BIBLE],
        }
        return scope_map.get(scope, None)

    def get_available_methods(self) -> List[Dict[str, str]]:
        """Get list of available retrieval methods for agent reference."""
        return [
            {"name": "query", "description": "Semantic search across project content"},
            {"name": "get_by_tag", "description": "Get all content related to a tag"},
            {"name": "get_world_bible_entry", "description": "Get world bible entry for a tag"},
            {"name": "get_script_content", "description": "Get script content (script, visual_script, pitch)"},
            {"name": "get_related_tags", "description": "Get tags related to a given tag"},
            {"name": "get_pipeline_results", "description": "Get results from a pipeline run"},
        ]

