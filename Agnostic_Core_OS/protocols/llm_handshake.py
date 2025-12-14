"""
LLM Handshake Protocol - Core LLM Communication with Vector Context

Establishes handshake between natural language requests and LLM responses
using vector notation for context storage and retrieval.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable
from enum import Enum
from datetime import datetime
import json
from pathlib import Path


class HandshakePhase(Enum):
    """Phases of the LLM handshake."""
    INIT = "init"                    # Initialize connection
    CONTEXT_LOAD = "context_load"    # Load vector context
    TRANSLATE = "translate"          # Translate request to vectors
    EXECUTE = "execute"              # Execute LLM call
    VALIDATE = "validate"            # Validate response
    STORE = "store"                  # Store result vectors
    COMPLETE = "complete"            # Handshake complete


class HandshakeStatus(Enum):
    """Status of handshake."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class HandshakeConfig:
    """Configuration for LLM handshake."""
    max_retries: int = 3
    timeout_seconds: float = 30.0
    validate_output: bool = True
    store_context: bool = True
    log_tokens: bool = True
    system_prompt_template: str = ""
    context_window_tokens: int = 8192
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "validate_output": self.validate_output,
            "store_context": self.store_context,
            "log_tokens": self.log_tokens,
            "system_prompt_template": self.system_prompt_template,
            "context_window_tokens": self.context_window_tokens
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HandshakeConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class HandshakeResult:
    """Result of an LLM handshake."""
    handshake_id: str
    status: HandshakeStatus
    phase: HandshakePhase
    input_natural: str
    input_vector: str
    output_natural: str
    output_vector: str
    context_used: Dict[str, Any] = field(default_factory=dict)
    tokens_input: int = 0
    tokens_output: int = 0
    iterations: int = 0
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "handshake_id": self.handshake_id,
            "status": self.status.value,
            "phase": self.phase.value,
            "input_natural": self.input_natural,
            "input_vector": self.input_vector,
            "output_natural": self.output_natural,
            "output_vector": self.output_vector,
            "context_used": self.context_used,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "iterations": self.iterations,
            "duration_ms": self.duration_ms,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ContextVector:
    """A stored context vector for handshake."""
    key: str
    value: Any
    notation: str
    weight: float = 1.0
    expires_at: Optional[datetime] = None
    
    def is_active(self) -> bool:
        if self.expires_at is None:
            return True
        return datetime.now() < self.expires_at


class LLMHandshake:
    """
    Core LLM Handshake Protocol.
    
    Manages the complete lifecycle of an LLM interaction:
    1. INIT - Initialize with config
    2. CONTEXT_LOAD - Load relevant vector context
    3. TRANSLATE - Convert natural language to vector notation
    4. EXECUTE - Call LLM with context
    5. VALIDATE - Validate response quality
    6. STORE - Store result vectors for future use
    7. COMPLETE - Finalize handshake
    
    Example:
        handshake = LLMHandshake(config)
        result = await handshake.execute(
            "Find character Mei and describe her motivation",
            context={"project": "Go for Orchid"}
        )
    """
    
    DEFAULT_SYSTEM_PROMPT = '''You are an AI assistant with access to vector notation context.

## Vector Notation Reference
- @TAG - Exact tag lookup (e.g., @CHAR_PROTAGONIST)
- #SCOPE - Filter by scope (e.g., #STORY)
- >COMMAND - Execute command (e.g., >diagnose)
- ~"text" - Semantic similarity search
- ?QUERY - Natural language query

## Context Vectors Loaded
{context_vectors}

## Instructions
Respond using the provided context. Reference tags with @ notation when applicable.
'''

    def __init__(
        self,
        config: Optional[HandshakeConfig] = None,
        translator: Optional[Any] = None,
        log_dir: Optional[Path] = None
    ):
        """Initialize the LLM handshake protocol."""
        self.config = config or HandshakeConfig()
        self.translator = translator
        self.log_dir = log_dir

        self._context_store: Dict[str, ContextVector] = {}
        self._handshake_history: List[HandshakeResult] = []
        self._next_id = 0
        self._llm_client: Optional[Any] = None

    def _generate_id(self) -> str:
        """Generate unique handshake ID."""
        self._next_id += 1
        return f"hs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._next_id:04d}"

    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client for execution."""
        self._llm_client = client

    def load_context(self, key: str, value: Any, notation: str, weight: float = 1.0) -> None:
        """Load a context vector for handshake."""
        self._context_store[key] = ContextVector(
            key=key,
            value=value,
            notation=notation,
            weight=weight
        )

    def get_active_context(self) -> Dict[str, ContextVector]:
        """Get all active context vectors."""
        return {k: v for k, v in self._context_store.items() if v.is_active()}

    def build_system_prompt(self, additional_context: Optional[Dict] = None) -> str:
        """Build system prompt with loaded context."""
        context_lines = []
        for key, cv in self.get_active_context().items():
            context_lines.append(f"- {cv.notation}: {cv.value} (weight: {cv.weight})")

        if additional_context:
            for k, v in additional_context.items():
                context_lines.append(f"- {k}: {v}")

        context_str = "\n".join(context_lines) if context_lines else "No context loaded"

        template = self.config.system_prompt_template or self.DEFAULT_SYSTEM_PROMPT
        return template.format(context_vectors=context_str)

    async def execute(
        self,
        natural_input: str,
        context: Optional[Dict[str, Any]] = None,
        validate_fn: Optional[Callable[[str], bool]] = None
    ) -> HandshakeResult:
        """
        Execute a complete LLM handshake.

        Args:
            natural_input: Natural language request
            context: Additional context for this request
            validate_fn: Optional validation function for output

        Returns:
            HandshakeResult with complete handshake data
        """
        import time
        start_time = time.time()

        handshake_id = self._generate_id()
        errors = []

        # Phase 1: INIT
        phase = HandshakePhase.INIT

        # Phase 2: CONTEXT_LOAD
        phase = HandshakePhase.CONTEXT_LOAD
        if context:
            for k, v in context.items():
                self.load_context(k, v, f"#{k.upper()}")

        # Phase 3: TRANSLATE
        phase = HandshakePhase.TRANSLATE
        input_vector = natural_input
        if self.translator:
            translation = self.translator.natural_to_vector(natural_input)
            input_vector = translation.output_text

        # Phase 4: EXECUTE
        phase = HandshakePhase.EXECUTE
        output_natural = ""
        tokens_in = len(natural_input.split())
        tokens_out = 0

        if self._llm_client:
            try:
                system_prompt = self.build_system_prompt(context)
                response = await self._llm_client.generate(
                    prompt=natural_input,
                    system=system_prompt
                )
                output_natural = response.text if hasattr(response, 'text') else str(response)
                tokens_out = len(output_natural.split())
            except Exception as e:
                errors.append(f"LLM execution error: {str(e)}")
        else:
            output_natural = f"[Mock Response] Processed: {input_vector}"
            tokens_out = len(output_natural.split())

        # Phase 5: VALIDATE
        phase = HandshakePhase.VALIDATE
        if self.config.validate_output and validate_fn:
            if not validate_fn(output_natural):
                errors.append("Output validation failed")

        # Phase 6: STORE
        phase = HandshakePhase.STORE
        output_vector = ""
        if self.translator and self.config.store_context:
            out_translation = self.translator.natural_to_vector(output_natural)
            output_vector = out_translation.output_text

        # Phase 7: COMPLETE
        phase = HandshakePhase.COMPLETE
        duration_ms = (time.time() - start_time) * 1000

        status = HandshakeStatus.SUCCESS if not errors else HandshakeStatus.FAILED

        result = HandshakeResult(
            handshake_id=handshake_id,
            status=status,
            phase=phase,
            input_natural=natural_input,
            input_vector=input_vector,
            output_natural=output_natural,
            output_vector=output_vector,
            context_used=context or {},
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            iterations=1,
            duration_ms=duration_ms,
            errors=errors
        )

        self._handshake_history.append(result)
        return result

    def get_history(self) -> List[Dict[str, Any]]:
        """Get handshake history."""
        return [r.to_dict() for r in self._handshake_history]

    def clear_context(self) -> None:
        """Clear all context vectors."""
        self._context_store.clear()

