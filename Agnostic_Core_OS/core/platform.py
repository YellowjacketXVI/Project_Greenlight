"""
Agnostic Core Platform - Main Platform Orchestrator

Central orchestrator for the Agnostic_Core_OS platform, integrating:
- Vector Language Translation
- LLM Handshake Protocol
- Iteration Validation
- Token-Efficient Logging
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable
from datetime import datetime
from pathlib import Path
import json

from .context_logger import TokenEfficientLogger, ContextReport, CompressionLevel
from ..translators.vector_language import VectorLanguageTranslator, TranslationResult
from ..protocols.llm_handshake import LLMHandshake, HandshakeConfig, HandshakeResult
from ..validators.iteration_validator import IterationValidator, IterationConfig, ValidationResult


@dataclass
class PlatformConfig:
    """Configuration for the Agnostic Core Platform."""
    max_iterations: int = 100
    max_tokens: int = 8192
    compression_level: CompressionLevel = CompressionLevel.MEDIUM
    auto_log: bool = True
    store_history: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_tokens": self.max_tokens,
            "compression_level": self.compression_level.value,
            "auto_log": self.auto_log,
            "store_history": self.store_history
        }


@dataclass
class PlatformSession:
    """A platform interaction session."""
    session_id: str
    natural_input: str
    vector_input: str
    natural_output: str
    vector_output: str
    iterations: int
    tokens_used: int
    handshake_result: Optional[HandshakeResult] = None
    validation_result: Optional[ValidationResult] = None
    context_report: Optional[ContextReport] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "natural_input": self.natural_input,
            "vector_input": self.vector_input,
            "natural_output": self.natural_output,
            "vector_output": self.vector_output,
            "iterations": self.iterations,
            "tokens_used": self.tokens_used,
            "handshake": self.handshake_result.to_dict() if self.handshake_result else None,
            "validation": self.validation_result.to_dict() if self.validation_result else None,
            "context": self.context_report.to_dict() if self.context_report else None,
            "timestamp": self.timestamp.isoformat()
        }


class AgnosticCorePlatform:
    """
    Agnostic Core Platform - Main Orchestrator.
    
    Provides a unified interface for:
    - Natural ↔ Vector translation
    - LLM handshake with context
    - Iterative validation (max 100)
    - Token-efficient logging
    
    Example:
        platform = AgnosticCorePlatform(project_path)
        
        # Simple translation
        result = platform.translate("Find character Mei")
        
        # Full LLM interaction with validation
        session = await platform.execute(
            "Describe Mei's motivation",
            context={"project": "Go for Orchid"},
            validate=True
        )
        
        # Get developer report
        report = platform.generate_developer_report()
    """
    
    def __init__(
        self,
        project_path: Optional[Path] = None,
        config: Optional[PlatformConfig] = None
    ):
        """Initialize the Agnostic Core Platform."""
        self.project_path = project_path
        self.config = config or PlatformConfig()
        
        # Setup directories
        if project_path:
            self.platform_dir = project_path / "Agnostic_Core_OS"
            self.logs_dir = self.platform_dir / "logs"
            self.logs_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.platform_dir = None
            self.logs_dir = None
        
        # Initialize components
        self.translator = VectorLanguageTranslator(log_dir=self.logs_dir)
        self.handshake = LLMHandshake(
            config=HandshakeConfig(),
            translator=self.translator,
            log_dir=self.logs_dir
        )
        self.validator = IterationValidator(
            config=IterationConfig(max_iterations=self.config.max_iterations),
            log_dir=self.logs_dir
        )
        self.logger = TokenEfficientLogger(
            max_tokens=self.config.max_tokens,
            log_dir=self.logs_dir,
            default_compression=self.config.compression_level
        )
        
        # Session tracking
        self._sessions: List[PlatformSession] = []
        self._next_session_id = 0
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        self._next_session_id += 1
        return f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._next_session_id:04d}"
    
    def translate(self, text: str, to_vector: bool = True) -> TranslationResult:
        """
        Translate between natural language and vector notation.
        
        Args:
            text: Input text
            to_vector: True for natural→vector, False for vector→natural
            
        Returns:
            TranslationResult
        """
        if to_vector:
            return self.translator.natural_to_vector(text)
        else:
            return self.translator.vector_to_natural(text)
    
    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client for handshake execution."""
        self.handshake.set_llm_client(client)

    def load_context(self, key: str, value: Any, notation: str) -> None:
        """Load context for LLM handshake."""
        self.handshake.load_context(key, value, notation)
        self.logger.log(key, value, notation)

    async def execute(
        self,
        natural_input: str,
        context: Optional[Dict[str, Any]] = None,
        validate: bool = True,
        validate_fn: Optional[Callable[[str], tuple[bool, float]]] = None
    ) -> PlatformSession:
        """
        Execute a complete platform interaction.

        Args:
            natural_input: Natural language request
            context: Additional context
            validate: Whether to run validation
            validate_fn: Custom validation function

        Returns:
            PlatformSession with complete interaction data
        """
        session_id = self._generate_session_id()

        # Translate input
        translation = self.translator.natural_to_vector(natural_input)
        vector_input = translation.output_text

        # Execute handshake
        handshake_result = await self.handshake.execute(natural_input, context)

        # Validate if requested
        validation_result = None
        iterations = 1

        if validate and validate_fn:
            async def process_fn(inp):
                return handshake_result.output_natural

            validation_result = await self.validator.run(
                natural_input,
                process_fn,
                validate_fn
            )
            iterations = validation_result.iteration

        # Translate output
        output_translation = self.translator.natural_to_vector(handshake_result.output_natural)
        vector_output = output_translation.output_text

        # Generate context report
        context_report = self.logger.generate_report()

        # Create session
        session = PlatformSession(
            session_id=session_id,
            natural_input=natural_input,
            vector_input=vector_input,
            natural_output=handshake_result.output_natural,
            vector_output=vector_output,
            iterations=iterations,
            tokens_used=handshake_result.tokens_input + handshake_result.tokens_output,
            handshake_result=handshake_result,
            validation_result=validation_result,
            context_report=context_report
        )

        if self.config.store_history:
            self._sessions.append(session)

        return session

    def get_sessions(self) -> List[Dict[str, Any]]:
        """Get all session history."""
        return [s.to_dict() for s in self._sessions]

    def generate_developer_report(self) -> str:
        """Generate a comprehensive developer report."""
        lines = [
            "# Agnostic Core OS - Developer Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Platform Configuration",
            f"- Max Iterations: {self.config.max_iterations}",
            f"- Max Tokens: {self.config.max_tokens}",
            f"- Compression: {self.config.compression_level.name}",
            "",
            "## Session Statistics",
            f"- Total Sessions: {len(self._sessions)}",
        ]

        if self._sessions:
            total_tokens = sum(s.tokens_used for s in self._sessions)
            total_iterations = sum(s.iterations for s in self._sessions)
            lines.extend([
                f"- Total Tokens Used: {total_tokens}",
                f"- Total Iterations: {total_iterations}",
                f"- Avg Tokens/Session: {total_tokens / len(self._sessions):.1f}",
            ])

        lines.extend([
            "",
            "## Translation History",
            f"- Translations: {len(self.translator.get_history())}",
            "",
            "## Handshake History",
            f"- Handshakes: {len(self.handshake.get_history())}",
            "",
            "## Token Usage",
        ])

        usage = self.logger.get_token_usage()
        lines.extend([
            f"- Total Entries: {usage['total_entries']}",
            f"- Raw Tokens: {usage['total_tokens']}",
            f"- Compressed: {usage['compressed_tokens']}",
            f"- Efficiency: {usage['efficiency']:.1%}",
        ])

        # Recent sessions
        if self._sessions:
            lines.extend(["", "## Recent Sessions"])
            for session in self._sessions[-5:]:
                lines.extend([
                    f"### {session.session_id}",
                    f"- Input: {session.natural_input[:50]}...",
                    f"- Vector: {session.vector_input[:50]}...",
                    f"- Output: {session.natural_output[:50]}...",
                    f"- Iterations: {session.iterations}",
                    f"- Tokens: {session.tokens_used}",
                    ""
                ])

        return "\n".join(lines)

    def save_developer_report(self, filename: Optional[str] = None) -> Optional[Path]:
        """Save developer report to disk."""
        if not self.logs_dir:
            return None

        report = self.generate_developer_report()
        fname = filename or f"dev_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = self.logs_dir / fname

        with open(path, 'w') as f:
            f.write(report)

        return path
