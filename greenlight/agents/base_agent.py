"""
Greenlight Base Agent

Abstract base class for all agents in the system.
Provides common functionality for LLM interaction, template loading, and response handling.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from pathlib import Path
import json

from greenlight.core.constants import LLMFunction
from greenlight.core.exceptions import LLMError, LLMResponseError
from greenlight.core.logging_config import get_logger

logger = get_logger("agents.base")


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    description: str
    llm_function: LLMFunction
    system_prompt: str = ""
    template_path: Optional[Path] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    retry_count: int = 3
    timeout: int = 60
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'description': self.description,
            'llm_function': self.llm_function.value,
            'system_prompt': self.system_prompt,
            'template_path': str(self.template_path) if self.template_path else None,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'retry_count': self.retry_count,
            'timeout': self.timeout
        }


@dataclass
class AgentResponse:
    """Response from an agent execution."""
    success: bool
    content: Any
    raw_response: str = ""
    tokens_used: int = 0
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    @classmethod
    def success_response(cls, content: Any, **kwargs) -> 'AgentResponse':
        return cls(success=True, content=content, **kwargs)
    
    @classmethod
    def error_response(cls, error: str, **kwargs) -> 'AgentResponse':
        return cls(success=False, content=None, error=error, **kwargs)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Provides:
    - Template loading and rendering
    - LLM interaction abstraction
    - Response parsing
    - Error handling and retries
    - Execution logging
    """
    
    def __init__(
        self,
        config: AgentConfig,
        llm_caller: Optional[Callable] = None
    ):
        """
        Initialize the agent.
        
        Args:
            config: Agent configuration
            llm_caller: Function to call LLM (async)
        """
        self.config = config
        self.llm_caller = llm_caller
        self._template_cache: Dict[str, str] = {}
        self._execution_history: List[Dict] = []
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Execute the agent's main task.
        
        Args:
            input_data: Input data for the task
            
        Returns:
            AgentResponse with results
        """
        pass
    
    @abstractmethod
    def parse_response(self, raw_response: str) -> Any:
        """
        Parse the raw LLM response into structured data.
        
        Args:
            raw_response: Raw text response from LLM
            
        Returns:
            Parsed and structured data
        """
        pass
    
    async def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Call the LLM with the given prompt.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt override
            
        Returns:
            LLM response text
        """
        if not self.llm_caller:
            raise LLMError("No LLM caller configured")
        
        system = system_prompt or self.config.system_prompt
        
        start_time = datetime.now()
        
        for attempt in range(self.config.retry_count):
            try:
                response = await self.llm_caller(
                    prompt=prompt,
                    system_prompt=system,
                    function=self.config.llm_function,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
                
                execution_time = (datetime.now() - start_time).total_seconds()
                self._log_execution(prompt, response, execution_time, attempt + 1)
                
                return response
                
            except Exception as e:
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
                if attempt == self.config.retry_count - 1:
                    raise LLMError(f"All {self.config.retry_count} attempts failed: {e}")
        
        raise LLMError("Unexpected error in LLM call")
    
    def load_template(self, template_name: str) -> str:
        """
        Load a prompt template from file.
        
        Args:
            template_name: Name of template file
            
        Returns:
            Template content
        """
        if template_name in self._template_cache:
            return self._template_cache[template_name]
        
        if not self.config.template_path:
            raise ValueError("No template path configured")
        
        template_file = self.config.template_path / template_name
        
        if not template_file.exists():
            raise FileNotFoundError(f"Template not found: {template_file}")
        
        with open(template_file, 'r', encoding='utf-8') as f:
            template = f.read()
        
        self._template_cache[template_name] = template
        return template
    
    def render_template(self, template: str, **variables) -> str:
        """
        Render a template with variables.
        
        Args:
            template: Template string with {variable} placeholders
            **variables: Variables to substitute
            
        Returns:
            Rendered template
        """
        try:
            return template.format(**variables)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")
    
    def _log_execution(
        self,
        prompt: str,
        response: str,
        execution_time: float,
        attempt: int
    ) -> None:
        """Log execution details."""
        self._execution_history.append({
            'timestamp': datetime.now().isoformat(),
            'prompt_length': len(prompt),
            'response_length': len(response),
            'execution_time': execution_time,
            'attempt': attempt
        })
        
        logger.debug(
            f"{self.name} executed in {execution_time:.2f}s "
            f"(attempt {attempt})"
        )

