"""
Agnostic_Core_OS Assistant Bridge

Background process manager for LLM requests that bridges UI ↔ OmniMind ↔ LLM.
Handles request queuing, async execution, and response routing.

Architecture:
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ASSISTANT BRIDGE (Background Manager)               │
├─────────────────────────────────────────────────────────────────────────────┤
│  User Input → Parse Intent → Route to Handler → Execute → Return Response  │
│                                                                             │
│  Handlers:                                                                  │
│    QUERY → OmniMind.process() → LLM call → Response                        │
│    COMMAND → TaskTranslator → ExecutionPlan → ToolExecutor                 │
│    SEARCH → ContextEngine.retrieve() → Results                             │
│    PIPELINE → PipelineManager.run() → Progress updates                     │
│                                                                             │
│  Background Process:                                                        │
│    - Runs in ThreadPoolExecutor                                            │
│    - Queues requests                                                        │
│    - Sends progress updates via callbacks                                   │
│    - Integrates with RuntimeDaemon                                         │
└─────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable, Union
from enum import Enum
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import asyncio
import queue
import threading
import logging
import uuid

from .llm_handshake import LLMHandshake, HandshakeConfig, HandshakeResult, HandshakeStatus

logger = logging.getLogger("agnostic_core_os.protocols.assistant_bridge")


class RequestIntent(Enum):
    """Types of user request intents."""
    QUERY = "query"           # Natural language question
    COMMAND = "command"       # Execute an action
    SEARCH = "search"         # Search for information
    PIPELINE = "pipeline"     # Run a pipeline
    SYSTEM = "system"         # System command (help, status, etc.)
    UNKNOWN = "unknown"


class RequestPriority(Enum):
    """Priority levels for requests."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class RequestStatus(Enum):
    """Status of a request."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BridgeRequest:
    """A request to the assistant bridge."""
    id: str
    input_text: str
    intent: RequestIntent
    priority: RequestPriority = RequestPriority.NORMAL
    context: Dict[str, Any] = field(default_factory=dict)
    status: RequestStatus = RequestStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def __lt__(self, other: "BridgeRequest") -> bool:
        """Compare by priority for queue ordering."""
        return self.priority.value > other.priority.value


@dataclass
class BridgeResponse:
    """Response from the assistant bridge."""
    request_id: str
    success: bool
    message: str
    intent: RequestIntent
    data: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class BridgeConfig:
    """Configuration for the assistant bridge."""
    max_workers: int = 4
    queue_size: int = 100
    default_timeout: float = 30.0
    enable_caching: bool = True
    log_requests: bool = True
    system_prompt: str = ""


class AssistantBridge:
    """
    Background process manager for LLM assistant requests.
    
    Features:
    - Request queuing with priority
    - Async execution in thread pool
    - Intent detection and routing
    - Progress callbacks
    - Integration with LLM handshake protocol
    - Error handling and retry logic
    
    Usage:
        bridge = AssistantBridge(config)
        bridge.set_llm_client(llm_client)
        bridge.set_response_callback(on_response)
        bridge.start()
        
        request_id = bridge.submit("What is the main character's motivation?")
        # Response delivered via callback
    """
    
    # Intent detection keywords
    COMMAND_KEYWORDS = [
        "run", "execute", "start", "stop", "create", "delete", "update",
        "generate", "build", "compile", "save", "load", "export", "import"
    ]
    SEARCH_KEYWORDS = [
        "find", "search", "look for", "where is", "show me", "list", "get"
    ]
    PIPELINE_KEYWORDS = [
        "pipeline", "writer", "director", "storyboard", "novelization"
    ]
    SYSTEM_KEYWORDS = [
        "help", "status", "version", "about", "settings", "config"
    ]
    
    def __init__(
        self,
        config: Optional[BridgeConfig] = None,
        handshake: Optional[LLMHandshake] = None
    ):
        """Initialize the assistant bridge."""
        self.config = config or BridgeConfig()
        self.handshake = handshake or LLMHandshake(HandshakeConfig())
        
        self._executor: Optional[ThreadPoolExecutor] = None
        self._request_queue: queue.PriorityQueue = queue.PriorityQueue(
            maxsize=self.config.queue_size
        )
        self._active_requests: Dict[str, BridgeRequest] = {}
        self._completed_requests: Dict[str, BridgeResponse] = {}
        
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Callbacks
        self._response_callback: Optional[Callable[[BridgeResponse], None]] = None
        self._progress_callback: Optional[Callable[[str, str, float], None]] = None
        self._error_callback: Optional[Callable[[str, Exception], None]] = None
        
        # LLM client
        self._llm_client: Optional[Any] = None
        
        # Context engine reference
        self._context_engine: Optional[Any] = None
        
        logger.info("AssistantBridge initialized")
    
    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client for processing requests."""
        self._llm_client = client
        self.handshake.set_llm_client(client)
        logger.info("LLM client set")
    
    def set_context_engine(self, engine: Any) -> None:
        """Set the context engine for retrieval."""
        self._context_engine = engine
    
    def set_response_callback(
        self,
        callback: Callable[[BridgeResponse], None]
    ) -> None:
        """Set callback for when responses are ready."""
        self._response_callback = callback
    
    def set_progress_callback(
        self,
        callback: Callable[[str, str, float], None]
    ) -> None:
        """Set callback for progress updates (request_id, message, progress)."""
        self._progress_callback = callback
    
    def set_error_callback(
        self,
        callback: Callable[[str, Exception], None]
    ) -> None:
        """Set callback for errors (request_id, exception)."""
        self._error_callback = callback
    
    def start(self) -> None:
        """Start the background processing."""
        if self._running:
            return
        
        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("AssistantBridge started")
    
    def stop(self) -> None:
        """Stop the background processing."""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        logger.info("AssistantBridge stopped")
    
    def submit(
        self,
        input_text: str,
        context: Optional[Dict[str, Any]] = None,
        priority: RequestPriority = RequestPriority.NORMAL
    ) -> str:
        """
        Submit a request for processing.
        
        Args:
            input_text: User's input text
            context: Additional context
            priority: Request priority
            
        Returns:
            Request ID for tracking
        """
        request_id = str(uuid.uuid4())[:8]
        intent = self._detect_intent(input_text)
        
        request = BridgeRequest(
            id=request_id,
            input_text=input_text,
            intent=intent,
            priority=priority,
            context=context or {}
        )
        
        self._request_queue.put(request)
        self._active_requests[request_id] = request
        
        if self.config.log_requests:
            logger.info(f"Request submitted: {request_id} ({intent.value})")
        
        return request_id
    
    def cancel(self, request_id: str) -> bool:
        """Cancel a pending request."""
        if request_id in self._active_requests:
            request = self._active_requests[request_id]
            if request.status == RequestStatus.QUEUED:
                request.status = RequestStatus.CANCELLED
                return True
        return False
    
    def get_status(self, request_id: str) -> Optional[RequestStatus]:
        """Get the status of a request."""
        if request_id in self._active_requests:
            return self._active_requests[request_id].status
        if request_id in self._completed_requests:
            return RequestStatus.COMPLETED
        return None
    
    def _detect_intent(self, text: str) -> RequestIntent:
        """Detect the intent of the input text."""
        text_lower = text.lower()
        
        # Check for system commands first
        if any(kw in text_lower for kw in self.SYSTEM_KEYWORDS):
            return RequestIntent.SYSTEM
        
        # Check for pipeline commands
        if any(kw in text_lower for kw in self.PIPELINE_KEYWORDS):
            return RequestIntent.PIPELINE
        
        # Check for explicit commands
        if any(text_lower.startswith(kw) for kw in self.COMMAND_KEYWORDS):
            return RequestIntent.COMMAND
        
        # Check for search queries
        if any(kw in text_lower for kw in self.SEARCH_KEYWORDS):
            return RequestIntent.SEARCH
        
        # Default to query
        return RequestIntent.QUERY
    
    def _worker_loop(self) -> None:
        """Main worker loop for processing requests."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        while self._running:
            try:
                # Get next request with timeout
                try:
                    request = self._request_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                if request.status == RequestStatus.CANCELLED:
                    continue
                
                # Process the request
                request.status = RequestStatus.PROCESSING
                request.started_at = datetime.now()
                
                try:
                    response = self._loop.run_until_complete(
                        self._process_request(request)
                    )
                    request.status = RequestStatus.COMPLETED
                except Exception as e:
                    logger.error(f"Request {request.id} failed: {e}")
                    response = BridgeResponse(
                        request_id=request.id,
                        success=False,
                        message=f"Error processing request: {str(e)}",
                        intent=request.intent,
                        error=str(e)
                    )
                    request.status = RequestStatus.FAILED
                    
                    if self._error_callback:
                        self._error_callback(request.id, e)
                
                request.completed_at = datetime.now()
                self._completed_requests[request.id] = response
                
                # Deliver response via callback
                if self._response_callback:
                    self._response_callback(response)
                
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
        
        self._loop.close()
    
    async def _process_request(self, request: BridgeRequest) -> BridgeResponse:
        """Process a single request."""
        import time
        start_time = time.time()
        
        # Report progress
        if self._progress_callback:
            self._progress_callback(request.id, "Processing...", 0.1)
        
        # Route based on intent
        if request.intent == RequestIntent.SYSTEM:
            response = await self._handle_system(request)
        elif request.intent == RequestIntent.SEARCH:
            response = await self._handle_search(request)
        elif request.intent == RequestIntent.COMMAND:
            response = await self._handle_command(request)
        elif request.intent == RequestIntent.PIPELINE:
            response = await self._handle_pipeline(request)
        else:
            response = await self._handle_query(request)
        
        response.duration_ms = (time.time() - start_time) * 1000
        
        if self._progress_callback:
            self._progress_callback(request.id, "Complete", 1.0)
        
        return response
    
    async def _handle_query(self, request: BridgeRequest) -> BridgeResponse:
        """Handle a natural language query."""
        # Use LLM handshake for query processing
        result = await self.handshake.execute(
            request.input_text,
            context=request.context
        )
        
        return BridgeResponse(
            request_id=request.id,
            success=result.status == HandshakeStatus.SUCCESS,
            message=result.output_natural,
            intent=request.intent,
            data={
                "handshake_id": result.handshake_id,
                "tokens_used": result.tokens_input + result.tokens_output
            },
            error=result.errors[0] if result.errors else None
        )
    
    async def _handle_search(self, request: BridgeRequest) -> BridgeResponse:
        """Handle a search request."""
        if self._context_engine:
            try:
                # Use context engine for search
                results = self._context_engine.retrieve(request.input_text)
                return BridgeResponse(
                    request_id=request.id,
                    success=True,
                    message=f"Found {len(results) if hasattr(results, '__len__') else 'some'} results",
                    intent=request.intent,
                    data={"results": results}
                )
            except Exception as e:
                return BridgeResponse(
                    request_id=request.id,
                    success=False,
                    message=f"Search failed: {str(e)}",
                    intent=request.intent,
                    error=str(e)
                )
        
        # Fallback to LLM query
        return await self._handle_query(request)
    
    async def _handle_command(self, request: BridgeRequest) -> BridgeResponse:
        """Handle a command request."""
        # For now, route to query handler
        # In full implementation, this would use TaskTranslator
        return await self._handle_query(request)
    
    async def _handle_pipeline(self, request: BridgeRequest) -> BridgeResponse:
        """Handle a pipeline request."""
        # Return guidance on how to run pipelines
        return BridgeResponse(
            request_id=request.id,
            success=True,
            message=(
                "To run pipelines, use the toolbar buttons:\n"
                "• 📝 Writer - Generate story content\n"
                "• 🎬 Director - Create storyboard prompts\n"
                "• 🎨 Generate - Create images from prompts"
            ),
            intent=request.intent,
            suggestions=[
                "Click the Writer button to start",
                "Make sure you have a project open first"
            ]
        )
    
    async def _handle_system(self, request: BridgeRequest) -> BridgeResponse:
        """Handle a system request."""
        text_lower = request.input_text.lower()
        
        if "help" in text_lower:
            message = self._get_help_message()
        elif "status" in text_lower:
            message = self._get_status_message()
        elif "version" in text_lower:
            message = "Agnostic_Core_OS Assistant Bridge v1.0.0"
        else:
            message = "System command not recognized. Try 'help' for available commands."
        
        return BridgeResponse(
            request_id=request.id,
            success=True,
            message=message,
            intent=request.intent
        )
    
    def _get_help_message(self) -> str:
        """Get help message."""
        return """I'm your AI assistant for Project Greenlight! Here's what I can help with:

📝 **Writing & Story**
• Ask questions about your story, characters, or world
• Get suggestions for plot development
• Review and edit content

🎬 **Storyboard Pipeline**
• Run the Writer pipeline to generate story content
• Run the Director pipeline to create storyboard prompts
• Generate storyboard images from prompts

🔍 **Search & Discovery**
• Find characters, locations, or props in your world bible
• Search for specific scenes or beats
• Look up tag references

💡 **Tips**
• Use natural language - I understand context
• Ask follow-up questions for more detail
• Say "help" anytime for this message"""
    
    def _get_status_message(self) -> str:
        """Get status message."""
        queued = self._request_queue.qsize()
        active = len([r for r in self._active_requests.values() 
                     if r.status == RequestStatus.PROCESSING])
        completed = len(self._completed_requests)
        
        return f"""**Assistant Bridge Status**
• Running: {self._running}
• Queued requests: {queued}
• Active requests: {active}
• Completed requests: {completed}
• LLM client: {'Connected' if self._llm_client else 'Not connected'}
• Context engine: {'Connected' if self._context_engine else 'Not connected'}"""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        return {
            "running": self._running,
            "queued": self._request_queue.qsize(),
            "active": len([r for r in self._active_requests.values() 
                          if r.status == RequestStatus.PROCESSING]),
            "completed": len(self._completed_requests),
            "failed": len([r for r in self._completed_requests.values() 
                          if not r.success]),
            "llm_connected": self._llm_client is not None,
            "context_connected": self._context_engine is not None
        }

