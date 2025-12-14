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
from .shot_list_validator import (
    ShotListValidatorAgent,
    ValidationResult,
    ValidationIssue,
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
from .brainstorm_agents import (
    BrainstormAgent,
    BrainstormOrchestrator,
    BrainstormPhilosophy,
    BrainstormPhilosophyConfig,
    PHILOSOPHY_CONFIGS,
)
from .steal_list_judge import (
    StealListJudge,
    JudgePanel,
    JudgeVote,
    StealListJudgeConfig,
    JUDGE_CONFIGS,
)
from .scene_outline_agent import (
    SceneOutlineAgent,
    StoryOutline,
)
from .prose_agent import (
    ProseAgent,
    ProseOrchestrator,
    ProseResult,
)
from .beat_extractor import (
    BeatExtractor,
    BeatSheet,
    Beat,
    BeatType,
    SceneBeats,
)
from .reference_prompt_agent import (
    ReferencePromptAgent,
    ReferencePromptResult,
    ReferencePromptType,
)

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
    # Shot list validation
    'ShotListValidatorAgent',
    'ValidationResult',
    'ValidationIssue',
    # Agent retrieval
    'AgentRetrievalTool',
    'RetrievalScope',
    'RetrievalResult',
    # Task translator
    'TaskTranslatorAgent',
    'TaskIntent',
    'TranslatedTask',
    'ExecutionPlan',
    # Brainstorm agents (Story Pipeline v3.0)
    'BrainstormAgent',
    'BrainstormOrchestrator',
    'BrainstormPhilosophy',
    'BrainstormPhilosophyConfig',
    'PHILOSOPHY_CONFIGS',
    # Steal list judges (Story Pipeline v3.0)
    'StealListJudge',
    'JudgePanel',
    'JudgeVote',
    'StealListJudgeConfig',
    'JUDGE_CONFIGS',
    # Scene outline agent (Story Pipeline v3.0)
    'SceneOutlineAgent',
    'StoryOutline',
    # Prose agent (Story Pipeline v3.0)
    'ProseAgent',
    'ProseOrchestrator',
    'ProseResult',
    # Beat extractor (Story Pipeline v3.0)
    'BeatExtractor',
    'BeatSheet',
    'Beat',
    'BeatType',
    'SceneBeats',
    # Reference prompt agent
    'ReferencePromptAgent',
    'ReferencePromptResult',
    'ReferencePromptType',
]

