"""
Greenlight Base Pipeline

Abstract base class for all processing pipelines.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Generic, TypeVar
from datetime import datetime
from enum import Enum

from greenlight.core.logging_config import get_logger
from greenlight.core.exceptions import PipelineError

logger = get_logger("pipelines.base")

InputT = TypeVar('InputT')
OutputT = TypeVar('OutputT')


class PipelineStatus(Enum):
    """Status of a pipeline execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineResult(Generic[OutputT]):
    """Result from a pipeline execution."""
    status: PipelineStatus
    output: Optional[OutputT] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        return self.status == PipelineStatus.COMPLETED


@dataclass
class PipelineStep:
    """A step in a pipeline."""
    name: str
    description: str
    required: bool = True
    timeout_seconds: int = 300


class BasePipeline(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for processing pipelines.
    
    Features:
    - Step-based execution
    - Progress tracking
    - Error handling
    - Cancellation support
    """
    
    def __init__(self, name: str):
        """
        Initialize the pipeline.
        
        Args:
            name: Pipeline name
        """
        self.name = name
        self._steps: List[PipelineStep] = []
        self._current_step: int = 0
        self._status = PipelineStatus.PENDING
        self._cancelled = False
        self._progress_callback = None
        
        self._define_steps()
    
    @abstractmethod
    def _define_steps(self) -> None:
        """Define the pipeline steps. Override in subclasses."""
        pass
    
    @abstractmethod
    async def _execute_step(
        self,
        step: PipelineStep,
        input_data: Any,
        context: Dict[str, Any]
    ) -> Any:
        """Execute a single step. Override in subclasses."""
        pass
    
    async def run(
        self,
        input_data: InputT,
        context: Dict[str, Any] = None
    ) -> PipelineResult[OutputT]:
        """
        Run the pipeline.
        
        Args:
            input_data: Input data
            context: Additional context
            
        Returns:
            PipelineResult with output
        """
        context = context or {}
        start_time = datetime.now()
        
        self._status = PipelineStatus.RUNNING
        self._current_step = 0
        self._cancelled = False
        
        logger.info(f"Starting pipeline: {self.name}")
        
        try:
            current_data = input_data
            
            for i, step in enumerate(self._steps):
                if self._cancelled:
                    return PipelineResult(
                        status=PipelineStatus.CANCELLED,
                        duration_seconds=self._get_duration(start_time)
                    )
                
                self._current_step = i
                self._report_progress(step, i, len(self._steps))
                
                logger.debug(f"Executing step: {step.name}")
                
                try:
                    current_data = await self._execute_step(
                        step, current_data, context
                    )
                except Exception as e:
                    if step.required:
                        raise
                    logger.warning(f"Optional step failed: {step.name} - {e}")
            
            self._status = PipelineStatus.COMPLETED
            
            return PipelineResult(
                status=PipelineStatus.COMPLETED,
                output=current_data,
                duration_seconds=self._get_duration(start_time),
                metadata={'steps_completed': len(self._steps)}
            )
            
        except Exception as e:
            self._status = PipelineStatus.FAILED
            logger.error(f"Pipeline failed: {self.name} - {e}")
            
            return PipelineResult(
                status=PipelineStatus.FAILED,
                error=str(e),
                duration_seconds=self._get_duration(start_time),
                metadata={'failed_step': self._current_step}
            )
    
    def cancel(self) -> None:
        """Cancel the pipeline execution."""
        self._cancelled = True
        logger.info(f"Pipeline cancelled: {self.name}")
    
    def set_progress_callback(self, callback) -> None:
        """Set a callback for progress updates."""
        self._progress_callback = callback
    
    def _report_progress(
        self,
        step: PipelineStep,
        current: int,
        total: int
    ) -> None:
        """Report progress to callback."""
        if self._progress_callback:
            self._progress_callback({
                'pipeline': self.name,
                'step': step.name,
                'current': current + 1,
                'total': total,
                'percent': (current + 1) / total * 100
            })
    
    def _get_duration(self, start_time: datetime) -> float:
        """Get duration since start time."""
        return (datetime.now() - start_time).total_seconds()
    
    @property
    def status(self) -> PipelineStatus:
        return self._status
    
    @property
    def progress(self) -> float:
        """Get current progress (0-1)."""
        if not self._steps:
            return 0.0
        return self._current_step / len(self._steps)
    
    @property
    def steps(self) -> List[PipelineStep]:
        return self._steps.copy()

