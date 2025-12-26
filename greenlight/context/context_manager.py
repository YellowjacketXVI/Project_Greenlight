"""
Greenlight Context Manager

Unified facade that orchestrates all context subsystems:
- ContextEngine (retrieval/search)
- ProjectContext (caching)
- ContextValidator (validation)
- ContextAssembler (token management)
- Cache invalidation events

This is the single entry point for all context operations.
"""

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Set
import json

from greenlight.core.logging_config import get_logger

logger = get_logger("context.manager")


class ContextEvent(Enum):
    """Events that can trigger cache invalidation or updates."""
    WORLD_CONFIG_CHANGED = "world_config_changed"
    SCRIPT_CHANGED = "script_changed"
    VISUAL_SCRIPT_CHANGED = "visual_script_changed"
    PROJECT_CHANGED = "project_changed"
    ENTITY_ADDED = "entity_added"
    ENTITY_UPDATED = "entity_updated"
    ENTITY_DELETED = "entity_deleted"
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    CACHE_INVALIDATED = "cache_invalidated"


@dataclass
class ContextSnapshot:
    """Snapshot of context state for debugging/tracing."""
    snapshot_id: str
    timestamp: datetime
    request_id: str
    context_type: str  # "character", "scene", "full", etc.
    content: str
    token_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextRequest:
    """A context request with tracing information."""
    request_id: str
    timestamp: datetime
    requester: str  # Pipeline or agent name
    context_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    response_tokens: int = 0
    duration_ms: float = 0


class ContextManager:
    """
    Unified context management facade.

    Provides a single interface for:
    - Context retrieval (delegates to ContextEngine)
    - Caching (delegates to ProjectContext)
    - Validation (delegates to ContextValidator)
    - Event-based cache invalidation
    - Context debugging/tracing

    Usage:
        manager = ContextManager.get_instance()
        manager.set_project(project_path)

        # Get context for an agent
        context = manager.get_context_for_agent("story_brainstorm", tags=["CHAR_MEI"])

        # Subscribe to cache invalidation
        manager.on_event(ContextEvent.WORLD_CONFIG_CHANGED, my_handler)

        # Invalidate cache
        manager.invalidate("world_config")
    """

    _instance: Optional["ContextManager"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ContextManager":
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing or full reload)."""
        with cls._lock:
            if cls._instance:
                cls._instance._cleanup()
            cls._instance = None

    def __init__(self):
        """Initialize the context manager."""
        self._project_path: Optional[Path] = None
        self._access_lock = threading.RLock()

        # Lazy-loaded subsystems
        self._context_engine = None
        self._project_context = None
        self._context_validator = None

        # Event system
        self._event_handlers: Dict[ContextEvent, List[Callable]] = {
            event: [] for event in ContextEvent
        }

        # Debugging/tracing
        self._trace_enabled = False
        self._snapshots: List[ContextSnapshot] = []
        self._requests: List[ContextRequest] = []
        self._max_snapshots = 100
        self._max_requests = 500

        # Version tracking for cache invalidation
        self._versions: Dict[str, int] = {
            "world_config": 0,
            "script": 0,
            "visual_script": 0
        }

        logger.info("ContextManager initialized")

    def _cleanup(self) -> None:
        """Clean up resources."""
        self._snapshots.clear()
        self._requests.clear()
        self._event_handlers = {event: [] for event in ContextEvent}

    # =========================================================================
    # PROJECT MANAGEMENT
    # =========================================================================

    def set_project(self, project_path: Path) -> None:
        """
        Set the current project and initialize subsystems.

        Args:
            project_path: Path to project directory
        """
        project_path = Path(project_path)

        with self._access_lock:
            if self._project_path != project_path:
                # Clear caches and notify
                self._invalidate_all()
                self._project_path = project_path

                # Initialize project context
                self._get_project_context().set_project(project_path)

                # Initialize context engine
                self._get_context_engine().set_project_path(project_path)

                # Fire event
                self._fire_event(ContextEvent.PROJECT_CHANGED, {
                    "project_path": str(project_path)
                })

                logger.info(f"Project set to: {project_path.name}")

    def get_project_path(self) -> Optional[Path]:
        """Get current project path."""
        return self._project_path

    # =========================================================================
    # SUBSYSTEM ACCESS (Lazy Loading)
    # =========================================================================

    def _get_context_engine(self):
        """Get or create context engine."""
        if self._context_engine is None:
            from .context_engine import ContextEngine
            self._context_engine = ContextEngine()
        return self._context_engine

    def _get_project_context(self):
        """Get or create project context."""
        if self._project_context is None:
            from greenlight.core.project_context import ProjectContext
            self._project_context = ProjectContext.get_instance()
        return self._project_context

    def _get_validator(self):
        """Get or create context validator."""
        if self._context_validator is None:
            from .context_validator import ContextValidator
            world_config = self.get_world_config()
            self._context_validator = ContextValidator(
                world_config=world_config.raw if world_config else {}
            )
        return self._context_validator

    # =========================================================================
    # WORLD CONFIG (Single Source of Truth)
    # =========================================================================

    def get_world_config(self, force_reload: bool = False):
        """
        Get world configuration (single source of truth).

        All components should use this method instead of loading directly.

        Args:
            force_reload: Force reload from disk

        Returns:
            CachedWorldConfig or None
        """
        return self._get_project_context().get_world_config(force_reload)

    def get_world_config_raw(self) -> Dict[str, Any]:
        """Get raw world config dictionary."""
        config = self.get_world_config()
        return config.raw if config else {}

    def load_world_config(self, data: Dict[str, Any]) -> None:
        """
        Load world config into the system.

        Use this when world_config is generated or modified programmatically.

        Args:
            data: World configuration dictionary
        """
        with self._access_lock:
            # Load into context engine
            self._get_context_engine().load_world_config(data)

            # Increment version
            self._versions["world_config"] += 1

            # Reset validator to pick up new config
            self._context_validator = None

            # Fire event
            self._fire_event(ContextEvent.WORLD_CONFIG_CHANGED, {
                "version": self._versions["world_config"]
            })

            logger.info("World config loaded into context manager")

    # =========================================================================
    # SCRIPT ACCESS
    # =========================================================================

    def get_script(self, force_reload: bool = False) -> Optional[str]:
        """Get script content."""
        return self._get_project_context().get_script(force_reload)

    def load_script(self, content: str) -> None:
        """Load script content into the system."""
        with self._access_lock:
            self._get_context_engine().load_script(content)
            self._versions["script"] += 1

            self._fire_event(ContextEvent.SCRIPT_CHANGED, {
                "version": self._versions["script"],
                "length": len(content)
            })

    def get_visual_script(self, force_reload: bool = False) -> Optional[str]:
        """Get visual script content."""
        return self._get_project_context().get_visual_script(force_reload)

    def load_visual_script(self, content: str) -> None:
        """Load visual script content into the system."""
        with self._access_lock:
            self._get_context_engine().load_visual_script(content)
            self._versions["visual_script"] += 1

            self._fire_event(ContextEvent.VISUAL_SCRIPT_CHANGED, {
                "version": self._versions["visual_script"],
                "length": len(content)
            })

    # =========================================================================
    # ENTITY ACCESS
    # =========================================================================

    def get_character(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get character by tag."""
        return self._get_project_context().get_character(tag)

    def get_location(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get location by tag."""
        return self._get_project_context().get_location(tag)

    def get_prop(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get prop by tag."""
        return self._get_project_context().get_prop(tag)

    def get_all_tags(self) -> Dict[str, List[str]]:
        """Get all tags organized by category."""
        return self._get_project_context().get_all_tags()

    # =========================================================================
    # CONTEXT RETRIEVAL (High-Level API)
    # =========================================================================

    def get_context_for_agent(
        self,
        agent_type: str,
        tags: List[str] = None,
        scene_number: int = None,
        max_tokens: int = None,
        **kwargs
    ) -> str:
        """
        Get context formatted for a specific agent type.

        This is the primary method for agents to request context.

        Args:
            agent_type: Type of agent (e.g., "story_brainstorm", "director", "dialogue")
            tags: Specific tags to include
            scene_number: Current scene number
            max_tokens: Maximum token budget
            **kwargs: Additional agent-specific parameters

        Returns:
            Formatted context string
        """
        request_id = self._generate_request_id()
        start_time = datetime.now()

        try:
            context = self._build_agent_context(
                agent_type=agent_type,
                tags=tags or [],
                scene_number=scene_number,
                max_tokens=max_tokens,
                **kwargs
            )

            # Record request if tracing enabled
            if self._trace_enabled:
                self._record_request(
                    request_id=request_id,
                    requester=agent_type,
                    context_type="agent_context",
                    parameters={
                        "tags": tags,
                        "scene_number": scene_number,
                        "max_tokens": max_tokens,
                        **kwargs
                    },
                    response_tokens=self._estimate_tokens(context),
                    start_time=start_time
                )

            return context

        except Exception as e:
            logger.error(f"Error getting context for agent {agent_type}: {e}")
            raise

    def _build_agent_context(
        self,
        agent_type: str,
        tags: List[str],
        scene_number: int = None,
        max_tokens: int = None,
        **kwargs
    ) -> str:
        """Build context based on agent type."""
        engine = self._get_context_engine()

        # Agent-specific context building
        if agent_type in ["story_brainstorm", "brainstorm"]:
            return self._build_brainstorm_context(tags, max_tokens)

        elif agent_type in ["director", "directing"]:
            return self._build_director_context(scene_number, tags, **kwargs)

        elif agent_type in ["dialogue", "conversation"]:
            speaking_char = kwargs.get("speaking_character")
            listening_chars = kwargs.get("listening_characters", [])
            scene_ctx = kwargs.get("scene_context", {})
            return engine.for_dialogue_agent(speaking_char, listening_chars, scene_ctx)

        elif agent_type in ["movement", "blocking"]:
            char_tag = kwargs.get("character_tag") or (tags[0] if tags else "")
            emotional_state = kwargs.get("emotional_state", "neutral")
            scene_ctx = kwargs.get("scene_context", {})
            return engine.for_movement_agent(char_tag, emotional_state, scene_ctx)

        elif agent_type == "character_embodiment":
            char_tag = tags[0] if tags else kwargs.get("character_tag", "")
            scene_ctx = kwargs.get("scene_context", {})
            rel_states = kwargs.get("relationship_states")
            return engine.for_character_embodiment_agent(char_tag, scene_ctx, rel_states)

        else:
            # Generic context
            return engine.get_world_context_for_tag_generation()

    def _build_brainstorm_context(self, tags: List[str], max_tokens: int = None) -> str:
        """Build context for brainstorm agents."""
        engine = self._get_context_engine()
        parts = []

        # World context
        parts.append(engine.get_world_context_for_tag_generation())

        # Character cards for specified tags
        for tag in tags:
            if tag.startswith("CHAR_"):
                profile = engine.get_character_profile(tag)
                if profile:
                    parts.append(f"\n[{tag}]: {profile.get('name', tag)}")
                    if desc := profile.get("description"):
                        parts.append(f"  {desc[:200]}...")

        return "\n".join(parts)

    def _build_director_context(
        self,
        scene_number: int = None,
        tags: List[str] = None,
        **kwargs
    ) -> str:
        """Build context for director agents."""
        engine = self._get_context_engine()
        parts = []

        # Notation standards
        parts.append(engine.get_notation_standards(include_examples=True))

        # World style
        parts.append(f"\nVISUAL STYLE: {engine.get_world_style()}")

        # Location and character context
        for tag in (tags or []):
            if tag.startswith("LOC_"):
                loc = engine.get_location_profile(tag)
                if loc:
                    parts.append(f"\nLOCATION [{tag}]: {loc.get('description', '')}")
            elif tag.startswith("CHAR_"):
                char = engine.get_character_profile(tag)
                if char:
                    parts.append(f"\nCHARACTER [{tag}]: {char.get('visual_description', '')}")

        return "\n".join(parts)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def validate(self, strict: bool = False):
        """
        Validate current context integrity.

        Args:
            strict: Treat warnings as errors

        Returns:
            ContextValidationResult
        """
        from .context_validator import ContextValidator

        world_config = self.get_world_config_raw()
        script = self.get_script() or ""
        visual_script = self.get_visual_script() or ""

        validator = ContextValidator(
            world_config=world_config,
            script_content=script,
            visual_script_content=visual_script,
            strict_mode=strict
        )

        return validator.validate_all()

    def validate_entity(self, entity_type: str, entity_data: Dict[str, Any]):
        """Validate a single entity before adding."""
        validator = self._get_validator()

        if entity_type == "character":
            issues = validator._validate_character(entity_data, 0)
        elif entity_type == "location":
            issues = validator._validate_location(entity_data, 0)
        elif entity_type == "prop":
            issues = validator._validate_prop(entity_data, 0)
        else:
            issues = []

        return issues

    # =========================================================================
    # CACHE INVALIDATION
    # =========================================================================

    def invalidate(self, what: str = "all") -> None:
        """
        Invalidate cached context.

        Args:
            what: What to invalidate ('world_config', 'script', 'visual_script', 'all')
        """
        with self._access_lock:
            self._get_project_context().invalidate(what)

            if what == "world_config" or what == "all":
                self._context_validator = None
                self._versions["world_config"] += 1

            if what == "script" or what == "all":
                self._versions["script"] += 1

            if what == "visual_script" or what == "all":
                self._versions["visual_script"] += 1

            self._fire_event(ContextEvent.CACHE_INVALIDATED, {"what": what})
            logger.debug(f"Cache invalidated: {what}")

    def _invalidate_all(self) -> None:
        """Invalidate all caches (internal use)."""
        if self._project_context:
            self._project_context.invalidate("all")
        self._context_validator = None
        self._versions = {k: v + 1 for k, v in self._versions.items()}

    # =========================================================================
    # EVENT SYSTEM
    # =========================================================================

    def on_event(self, event: ContextEvent, handler: Callable) -> None:
        """
        Subscribe to a context event.

        Args:
            event: Event type to subscribe to
            handler: Callback function(event_data: Dict)
        """
        self._event_handlers[event].append(handler)

    def off_event(self, event: ContextEvent, handler: Callable) -> None:
        """Unsubscribe from a context event."""
        if handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)

    def _fire_event(self, event: ContextEvent, data: Dict[str, Any] = None) -> None:
        """Fire an event to all subscribers."""
        data = data or {}
        data["event"] = event.value
        data["timestamp"] = datetime.now().isoformat()

        for handler in self._event_handlers[event]:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Event handler error for {event.value}: {e}")

    # =========================================================================
    # DEBUGGING / TRACING
    # =========================================================================

    def enable_tracing(self, enabled: bool = True) -> None:
        """Enable or disable context tracing."""
        self._trace_enabled = enabled
        logger.info(f"Context tracing {'enabled' if enabled else 'disabled'}")

    def take_snapshot(
        self,
        context_type: str,
        content: str,
        request_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> ContextSnapshot:
        """
        Take a snapshot of context state.

        Args:
            context_type: Type of context
            content: Context content
            request_id: Associated request ID
            metadata: Additional metadata

        Returns:
            ContextSnapshot
        """
        snapshot = ContextSnapshot(
            snapshot_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(),
            request_id=request_id or "",
            context_type=context_type,
            content=content,
            token_count=self._estimate_tokens(content),
            metadata=metadata or {}
        )

        self._snapshots.append(snapshot)

        # Trim old snapshots
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]

        return snapshot

    def get_snapshots(
        self,
        context_type: str = None,
        request_id: str = None,
        limit: int = 10
    ) -> List[ContextSnapshot]:
        """Get context snapshots, optionally filtered."""
        snapshots = self._snapshots

        if context_type:
            snapshots = [s for s in snapshots if s.context_type == context_type]

        if request_id:
            snapshots = [s for s in snapshots if s.request_id == request_id]

        return snapshots[-limit:]

    def get_request_log(self, limit: int = 50) -> List[ContextRequest]:
        """Get recent context requests."""
        return self._requests[-limit:]

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return f"ctx_{datetime.now().strftime('%H%M%S')}_{str(uuid.uuid4())[:6]}"

    def _record_request(
        self,
        request_id: str,
        requester: str,
        context_type: str,
        parameters: Dict[str, Any],
        response_tokens: int,
        start_time: datetime
    ) -> None:
        """Record a context request."""
        duration = (datetime.now() - start_time).total_seconds() * 1000

        request = ContextRequest(
            request_id=request_id,
            timestamp=start_time,
            requester=requester,
            context_type=context_type,
            parameters=parameters,
            response_tokens=response_tokens,
            duration_ms=duration
        )

        self._requests.append(request)

        # Trim old requests
        if len(self._requests) > self._max_requests:
            self._requests = self._requests[-self._max_requests:]

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        # Rough estimate: ~4 chars per token
        return len(text) // 4

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get context manager statistics."""
        return {
            "project_path": str(self._project_path) if self._project_path else None,
            "versions": self._versions.copy(),
            "tracing_enabled": self._trace_enabled,
            "snapshots_count": len(self._snapshots),
            "requests_count": len(self._requests),
            "project_context_stats": self._get_project_context().get_stats() if self._project_context else {},
            "context_engine_outputs": self._get_context_engine().get_all_pipeline_outputs() if self._context_engine else {}
        }


# Convenience functions
def get_context_manager() -> ContextManager:
    """Get the global context manager."""
    return ContextManager.get_instance()


def set_project(project_path: Path) -> None:
    """Set the current project."""
    get_context_manager().set_project(project_path)


def get_world_config():
    """Get cached world configuration."""
    return get_context_manager().get_world_config()


def invalidate_context(what: str = "all") -> None:
    """Invalidate context cache."""
    get_context_manager().invalidate(what)


def validate_context(strict: bool = False):
    """Validate current context."""
    return get_context_manager().validate(strict)
