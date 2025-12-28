"""
Greenlight Agents Module

Agnostic agent framework with template-based configuration for multi-agent
task execution and orchestration.
"""

from .base_agent import BaseAgent, AgentConfig, AgentResponse
from .agent_pool import AgentPool
from .orchestrator import OrchestratorAgent, ExecutionMode, WorkflowStep
from .prompts import AgentPromptLibrary
from .collaboration import (
    CollaborationAgent,
    CollaborationConfig,
    CollaborationMode,
    CollaborationTurn,
    CollaborationResult,
)
from .specialized_agents import (
    TagValidationAgent,
    StoryBuildingAgent,
    DirectorAgent,
    LocationViewAgent,
    TagClassificationAgent,
)
from .agent_retrieval import (
    AgentRetrievalTool,
    RetrievalScope,
    RetrievalResult,
)
from .task_translator import (
    TaskTranslatorAgent,
    TaskIntent,
    TranslatedTask,
    ExecutionPlan,
)
from .prompt_refinement_agent import PromptRefinementAgent
from .batch_coherency_agent import BatchCoherencyAgent

__all__ = [
    'BaseAgent',
    'AgentConfig',
    'AgentResponse',
    'AgentPool',
    'OrchestratorAgent',
    'ExecutionMode',
    'WorkflowStep',
    'AgentPromptLibrary',
    # Collaboration
    'CollaborationAgent',
    'CollaborationConfig',
    'CollaborationMode',
    'CollaborationTurn',
    'CollaborationResult',
    # Specialized agents
    'TagValidationAgent',
    'StoryBuildingAgent',
    'DirectorAgent',
    'LocationViewAgent',
    'TagClassificationAgent',
    # Agent retrieval
    'AgentRetrievalTool',
    'RetrievalScope',
    'RetrievalResult',
    # Task translator
    'TaskTranslatorAgent',
    'TaskIntent',
    'TranslatedTask',
    'ExecutionPlan',
    # Prompt refinement
    'PromptRefinementAgent',
    'BatchCoherencyAgent',
]
