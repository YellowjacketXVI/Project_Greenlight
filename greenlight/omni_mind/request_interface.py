"""
Greenlight OmniMind Request Interface

UI interface for sending requests to OmniMind through vectored search context notation.
Translates user requests using symbolic notation from .augment-guidelines.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum
import re

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.request_interface")


class RequestType(Enum):
    """Types of OmniMind requests."""
    TAG_LOOKUP = "tag_lookup"           # @TAG
    SCOPE_FILTER = "scope_filter"       # #SCOPE
    INCLUDE = "include"                 # +INCLUDE
    EXCLUDE = "exclude"                 # -EXCLUDE
    SIMILARITY = "similarity"           # ~SIMILAR
    PIPELINE = "pipeline"               # >PIPELINE
    QUERY = "query"                     # ?QUERY
    ROUTE = "route"                     # >route
    DIAGNOSE = "diagnose"               # >diagnose
    HEAL = "heal"                       # >heal


class RequestStatus(Enum):
    """Status of a request."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ParsedRequest:
    """A parsed request from symbolic notation."""
    request_type: RequestType
    symbol: str
    value: str
    raw_input: str
    modifiers: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestResult:
    """Result of a request execution."""
    request_id: str
    status: RequestStatus
    result: Any = None
    error: str = ""
    execution_time_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class RequestHistoryEntry:
    """Entry in request history."""
    id: str
    raw_input: str
    parsed: ParsedRequest
    result: RequestResult
    timestamp: datetime = field(default_factory=datetime.now)


class SymbolicNotationParser:
    """
    Parser for symbolic notation from .augment-guidelines.
    
    Supported symbols:
    - @TAG: Exact tag lookup
    - #SCOPE: Filter by scope
    - +INCLUDE: Include in results
    - -EXCLUDE: Exclude from results
    - ~SIMILAR: Semantic similarity
    - >PIPELINE: Run pipeline
    - ?QUERY: Natural language query
    - >route: Core vector routing commands
    - >diagnose: Run diagnostics
    - >heal: Self-healing
    """
    
    # Pattern definitions
    PATTERNS = {
        RequestType.TAG_LOOKUP: r'^@(\w+)$',
        RequestType.SCOPE_FILTER: r'^#(\w+)$',
        RequestType.INCLUDE: r'^\+(\w+)$',
        RequestType.EXCLUDE: r'^-(\w+)$',
        RequestType.SIMILARITY: r'^~"([^"]+)"$',
        RequestType.PIPELINE: r'^>(\w+)(?:\s+(.*))?$',
        RequestType.QUERY: r'^\?"([^"]+)"$',
        RequestType.ROUTE: r'^>route\s+(\w+)(?:\s+(.*))?$',
        RequestType.DIAGNOSE: r'^>diagnose(?:\s+(.*))?$',
        RequestType.HEAL: r'^>heal$',
    }
    
    def parse(self, input_text: str) -> Optional[ParsedRequest]:
        """
        Parse symbolic notation input.
        
        Args:
            input_text: Raw input text
            
        Returns:
            ParsedRequest or None if not recognized
        """
        input_text = input_text.strip()
        
        for req_type, pattern in self.PATTERNS.items():
            match = re.match(pattern, input_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                value = groups[0] if groups else ""
                modifiers = {}
                
                # Handle additional groups as modifiers
                if len(groups) > 1 and groups[1]:
                    modifiers["args"] = groups[1]
                
                return ParsedRequest(
                    request_type=req_type,
                    symbol=input_text[0] if input_text else "",
                    value=value,
                    raw_input=input_text,
                    modifiers=modifiers
                )
        
        # Default to natural language query
        return ParsedRequest(
            request_type=RequestType.QUERY,
            symbol="?",
            value=input_text,
            raw_input=input_text
        )
    
    def get_help(self) -> str:
        """Get help text for symbolic notation."""
        return """
# Symbolic Notation Reference

| Symbol | Meaning | Example |
|--------|---------|---------|
| @TAG | Exact tag lookup | @CHAR_MEI |
| #SCOPE | Filter by scope | #WORLD_BIBLE |
| +INCLUDE | Include in results | +characters |
| -EXCLUDE | Exclude from results | -archived |
| ~"text" | Semantic similarity | ~"warrior spirit" |
| >pipeline | Run pipeline | >story_pipeline |
| ?"text" | Natural language query | ?"who is the protagonist" |
| >route cmd | Vector routing | >route archive entry_id |
| >diagnose | Run diagnostics | >diagnose all |
| >heal | Self-healing | >heal |
"""


class OmniMindRequestInterface:
    """
    Request interface for OmniMind.

    Features:
    - Parse symbolic notation
    - Execute requests through OmniMind
    - Track request history
    - Provide suggestions and autocomplete
    """

    def __init__(
        self,
        omni_mind: Any = None,
        key_chain: Any = None
    ):
        """
        Initialize request interface.

        Args:
            omni_mind: OmniMind instance
            key_chain: KeyChain for tracking
        """
        self.omni_mind = omni_mind
        self.key_chain = key_chain
        self.parser = SymbolicNotationParser()

        self._history: List[RequestHistoryEntry] = []
        self._handlers: Dict[RequestType, Callable] = {}
        self._next_id = 0

        self._register_default_handlers()

    def _generate_id(self) -> str:
        """Generate unique request ID."""
        self._next_id += 1
        return f"req_{self._next_id:08d}"

    def _register_default_handlers(self) -> None:
        """Register default request handlers."""
        self._handlers = {
            RequestType.TAG_LOOKUP: self._handle_tag_lookup,
            RequestType.SCOPE_FILTER: self._handle_scope_filter,
            RequestType.PIPELINE: self._handle_pipeline,
            RequestType.ROUTE: self._handle_route,
            RequestType.DIAGNOSE: self._handle_diagnose,
            RequestType.HEAL: self._handle_heal,
            RequestType.QUERY: self._handle_query,
            RequestType.SIMILARITY: self._handle_similarity,
        }

    async def execute(self, input_text: str) -> RequestResult:
        """
        Execute a request from symbolic notation.

        Args:
            input_text: Raw input text

        Returns:
            RequestResult
        """
        import time
        start_time = time.time()

        request_id = self._generate_id()
        parsed = self.parser.parse(input_text)

        if not parsed:
            return RequestResult(
                request_id=request_id,
                status=RequestStatus.FAILED,
                error="Could not parse input"
            )

        # Track in key chain
        if self.key_chain:
            from .key_chain import KeyType
            self.key_chain.track_retrieval(
                query=input_text,
                scope=parsed.request_type.value,
                results_count=0,
                accessor="user"
            )

        # Execute handler
        handler = self._handlers.get(parsed.request_type)
        if handler:
            try:
                result = await handler(parsed)
                execution_time = (time.time() - start_time) * 1000

                result_obj = RequestResult(
                    request_id=request_id,
                    status=RequestStatus.COMPLETED,
                    result=result,
                    execution_time_ms=execution_time
                )
            except Exception as e:
                result_obj = RequestResult(
                    request_id=request_id,
                    status=RequestStatus.FAILED,
                    error=str(e)
                )
        else:
            result_obj = RequestResult(
                request_id=request_id,
                status=RequestStatus.FAILED,
                error=f"No handler for {parsed.request_type.value}"
            )

        # Add to history
        self._history.append(RequestHistoryEntry(
            id=request_id,
            raw_input=input_text,
            parsed=parsed,
            result=result_obj
        ))

        return result_obj

    # =========================================================================
    # REQUEST HANDLERS
    # =========================================================================

    async def _handle_tag_lookup(self, parsed: ParsedRequest) -> Any:
        """Handle @TAG lookup."""
        if self.omni_mind and hasattr(self.omni_mind, 'tag_registry'):
            tag = self.omni_mind.tag_registry.get_tag(parsed.value)
            if tag:
                return tag.to_dict() if hasattr(tag, 'to_dict') else str(tag)
        return f"Tag not found: {parsed.value}"

    async def _handle_scope_filter(self, parsed: ParsedRequest) -> Any:
        """Handle #SCOPE filter."""
        return f"Scope filter: {parsed.value}"

    async def _handle_pipeline(self, parsed: ParsedRequest) -> Any:
        """Handle >pipeline command."""
        pipeline_name = parsed.value
        args = parsed.modifiers.get("args", "")

        if self.omni_mind:
            # Map pipeline names to handlers
            pipeline_map = {
                "story": "run_story_pipeline_v2",
                "story_pipeline": "run_story_pipeline_v2",
                "directing": "run_directing_pipeline",
                "world_bible": "run_world_bible_pipeline",
            }

            handler_name = pipeline_map.get(pipeline_name.lower())
            if handler_name and hasattr(self.omni_mind, '_action_handlers'):
                handler = self.omni_mind._action_handlers.get(handler_name)
                if handler:
                    return await handler({})

        return f"Pipeline not found: {pipeline_name}"

    async def _handle_route(self, parsed: ParsedRequest) -> Any:
        """Handle >route command."""
        command = parsed.value
        args = parsed.modifiers.get("args", "")

        if self.omni_mind:
            if command == "error":
                return "Use route_error() method with exception"
            elif command == "archive":
                return self.omni_mind.route_archive(args)
            elif command == "deprecate":
                return self.omni_mind.route_deprecate(args)
            elif command == "restore":
                return self.omni_mind.route_restore(args)
            elif command == "flush":
                return self.omni_mind.route_flush()

        return f"Unknown route command: {command}"

    async def _handle_diagnose(self, parsed: ParsedRequest) -> Any:
        """Handle >diagnose command."""
        scope = parsed.modifiers.get("args", "all")
        if self.omni_mind and hasattr(self.omni_mind, 'diagnose'):
            return await self.omni_mind.diagnose(scope)
        return "Diagnose not available"

    async def _handle_heal(self, parsed: ParsedRequest) -> Any:
        """Handle >heal command."""
        if self.omni_mind and hasattr(self.omni_mind, 'self_heal'):
            return await self.omni_mind.self_heal()
        return "Self-heal not available"

    async def _handle_query(self, parsed: ParsedRequest) -> Any:
        """Handle natural language query."""
        if self.omni_mind and hasattr(self.omni_mind, 'process'):
            response = await self.omni_mind.process(parsed.value)
            return response.message if hasattr(response, 'message') else str(response)
        return f"Query: {parsed.value}"

    async def _handle_similarity(self, parsed: ParsedRequest) -> Any:
        """Handle ~"text" similarity search."""
        if self.omni_mind and hasattr(self.omni_mind, 'retrieval_tool'):
            from greenlight.agents.agent_retrieval import RetrievalScope
            result = await self.omni_mind.retrieval_tool.retrieve(
                query=parsed.value,
                scope=RetrievalScope.ALL
            )
            return result.to_dict() if hasattr(result, 'to_dict') else str(result)
        return f"Similarity search: {parsed.value}"

    # =========================================================================
    # HISTORY & SUGGESTIONS
    # =========================================================================

    def get_history(self, limit: int = 50) -> List[RequestHistoryEntry]:
        """Get recent request history."""
        return self._history[-limit:]

    def get_suggestions(self, partial: str) -> List[str]:
        """Get autocomplete suggestions."""
        suggestions = []
        partial_lower = partial.lower()

        # Suggest based on prefix
        if partial.startswith("@"):
            suggestions.extend(["@CHAR_", "@LOC_", "@PROP_", "@EVENT_"])
        elif partial.startswith("#"):
            suggestions.extend(["#WORLD_BIBLE", "#STORY", "#STORYBOARD", "#TAGS"])
        elif partial.startswith(">"):
            suggestions.extend([
                ">story_pipeline", ">directing", ">world_bible",
                ">route archive", ">route deprecate", ">diagnose", ">heal"
            ])
        elif partial.startswith("~"):
            suggestions.append('~"search term"')
        elif partial.startswith("?"):
            suggestions.append('?"your question"')

        # Filter by partial match
        return [s for s in suggestions if partial_lower in s.lower()]

    def get_help(self) -> str:
        """Get help text."""
        return self.parser.get_help()

    def get_stats(self) -> Dict[str, Any]:
        """Get interface statistics."""
        by_type = {}
        by_status = {}

        for entry in self._history:
            rt = entry.parsed.request_type.value
            by_type[rt] = by_type.get(rt, 0) + 1
            st = entry.result.status.value
            by_status[st] = by_status.get(st, 0) + 1

        return {
            "total_requests": len(self._history),
            "by_type": by_type,
            "by_status": by_status
        }

