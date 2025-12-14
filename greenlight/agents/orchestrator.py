"""
Greenlight Orchestrator Agent

Master coordinator for multi-agent task execution.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import asyncio

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from .base_agent import BaseAgent, AgentConfig, AgentResponse
from .agent_pool import AgentPool, PoolResult

logger = get_logger("agents.orchestrator")


class ExecutionMode(Enum):
    """Modes for orchestrated execution."""
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    PIPELINE = "pipeline"
    CONSENSUS = "consensus"
    SOCRATIC_COLLABORATION = "socratic_collaboration"
    ROLEPLAY_COLLABORATION = "roleplay_collaboration"


@dataclass
class WorkflowStep:
    """A step in an orchestrated workflow."""
    name: str
    agents: List[str]
    mode: ExecutionMode
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_key: str = ""
    required: bool = True
    condition: Optional[Callable[[Dict], bool]] = None
    collaboration_config: Optional[Any] = None  # CollaborationConfig for collaboration modes


@dataclass
class WorkflowResult:
    """Result of a complete workflow execution."""
    success: bool
    steps_completed: int
    total_steps: int
    outputs: Dict[str, Any]
    step_results: Dict[str, PoolResult]
    errors: List[str] = field(default_factory=list)


class OrchestratorAgent(BaseAgent):
    """
    Orchestrates complex multi-agent workflows.
    
    Features:
    - Workflow definition and execution
    - Multiple execution modes (parallel, sequential, pipeline, consensus)
    - Conditional step execution
    - Result aggregation and transformation
    """
    
    def __init__(
        self,
        pool: AgentPool,
        llm_caller: Optional[Callable] = None
    ):
        """
        Initialize the orchestrator.
        
        Args:
            pool: AgentPool with registered agents
            llm_caller: LLM caller for orchestrator decisions
        """
        config = AgentConfig(
            name="Orchestrator",
            description="Master coordinator for multi-agent workflows",
            llm_function=LLMFunction.ASSISTANT_REASONING
        )
        super().__init__(config, llm_caller)
        self.pool = pool
        self._workflows: Dict[str, List[WorkflowStep]] = {}
    
    def define_workflow(
        self,
        name: str,
        steps: List[WorkflowStep]
    ) -> None:
        """
        Define a reusable workflow.
        
        Args:
            name: Workflow name
            steps: List of workflow steps
        """
        self._workflows[name] = steps
        logger.info(f"Defined workflow: {name} with {len(steps)} steps")
    
    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Execute the orchestrator's default task."""
        workflow_name = input_data.get('workflow')
        if workflow_name and workflow_name in self._workflows:
            result = await self.run_workflow(workflow_name, input_data)
            return AgentResponse.success_response(result)
        
        return AgentResponse.error_response("No workflow specified")
    
    def parse_response(self, raw_response: str) -> Any:
        """Parse orchestrator response."""
        return raw_response
    
    async def run_workflow(
        self,
        workflow_name: str,
        input_data: Dict[str, Any]
    ) -> WorkflowResult:
        """
        Execute a defined workflow.
        
        Args:
            workflow_name: Name of workflow to run
            input_data: Initial input data
            
        Returns:
            WorkflowResult with all outputs
        """
        if workflow_name not in self._workflows:
            return WorkflowResult(
                success=False,
                steps_completed=0,
                total_steps=0,
                outputs={},
                step_results={},
                errors=[f"Workflow not found: {workflow_name}"]
            )
        
        steps = self._workflows[workflow_name]
        outputs = input_data.copy()
        step_results = {}
        errors = []
        steps_completed = 0
        
        logger.info(f"Starting workflow: {workflow_name}")
        
        for step in steps:
            # Check condition
            if step.condition and not step.condition(outputs):
                logger.debug(f"Skipping step {step.name}: condition not met")
                continue
            
            # Prepare step input
            step_input = self._prepare_step_input(step, outputs)
            
            # Execute step
            try:
                result = await self._execute_step(step, step_input)
                step_results[step.name] = result
                
                if result.all_successful:
                    steps_completed += 1
                    # Store output
                    if step.output_key:
                        outputs[step.output_key] = result.get_all_content()
                else:
                    if step.required:
                        errors.append(f"Step {step.name} failed")
                        break
                        
            except Exception as e:
                errors.append(f"Step {step.name} error: {e}")
                if step.required:
                    break
        
        success = len(errors) == 0
        
        logger.info(
            f"Workflow {workflow_name} complete: "
            f"{steps_completed}/{len(steps)} steps, success={success}"
        )
        
        return WorkflowResult(
            success=success,
            steps_completed=steps_completed,
            total_steps=len(steps),
            outputs=outputs,
            step_results=step_results,
            errors=errors
        )
    
    def _prepare_step_input(
        self,
        step: WorkflowStep,
        outputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare input data for a step."""
        step_input = {}
        
        for target_key, source_key in step.input_mapping.items():
            if source_key in outputs:
                step_input[target_key] = outputs[source_key]
        
        # Include any unmapped outputs
        for key, value in outputs.items():
            if key not in step_input:
                step_input[key] = value
        
        return step_input
    
    async def _execute_step(
        self,
        step: WorkflowStep,
        input_data: Dict[str, Any]
    ) -> PoolResult:
        """Execute a single workflow step."""
        logger.debug(f"Executing step: {step.name} ({step.mode.value})")

        if step.mode == ExecutionMode.PARALLEL:
            return await self.pool.execute_parallel(step.agents, input_data)

        elif step.mode == ExecutionMode.SEQUENTIAL:
            return await self.pool.execute_sequential(step.agents, input_data)

        elif step.mode == ExecutionMode.PIPELINE:
            return await self.pool.execute_sequential(
                step.agents, input_data, pass_results=True
            )

        elif step.mode == ExecutionMode.CONSENSUS:
            result = await self.pool.execute_parallel(step.agents, input_data)
            # For consensus, we need majority agreement
            # This is handled by the consensus tagger for tag extraction
            return result

        elif step.mode == ExecutionMode.SOCRATIC_COLLABORATION:
            return await self._execute_socratic_step(step, input_data)

        elif step.mode == ExecutionMode.ROLEPLAY_COLLABORATION:
            return await self._execute_roleplay_step(step, input_data)

        else:
            raise ValueError(f"Unknown execution mode: {step.mode}")

    async def _execute_socratic_step(
        self,
        step: WorkflowStep,
        input_data: Dict[str, Any]
    ) -> PoolResult:
        """
        Execute Socratic collaboration step.

        Requires:
        - step.agents: [agent_a_name, agent_b_name]
        - step.collaboration_config: CollaborationConfig
        - input_data: Contains 'goal' key
        """
        from .collaboration import CollaborationAgent

        if not step.collaboration_config:
            raise ValueError("Socratic collaboration requires collaboration_config")

        if len(step.agents) < 2:
            raise ValueError("Socratic collaboration requires 2 agents")

        agent_a = self.pool.get(step.agents[0])
        agent_b = self.pool.get(step.agents[1])
        goal = input_data.get('goal', '')

        collab = CollaborationAgent(self.llm_caller)
        result = await collab.execute_socratic(agent_a, agent_b, goal, step.collaboration_config)

        # Convert CollaborationResult to PoolResult format
        from .agent_pool import ExecutionResult

        execution = ExecutionResult(
            agent_name="Socratic Collaboration",
            response=AgentResponse.success_response(result),
            execution_time=result.total_time,
            tokens_used=result.total_tokens
        )

        pool_result = PoolResult(
            executions=[execution],
            total_time=result.total_time,
            success_count=1 if result.success else 0,
            failure_count=0 if result.success else 1
        )

        logger.info(f"Socratic collaboration completed: {result.convergence_achieved}")
        return pool_result

    async def _execute_roleplay_step(
        self,
        step: WorkflowStep,
        input_data: Dict[str, Any]
    ) -> PoolResult:
        """
        Execute Roleplay collaboration step.

        Requires:
        - step.agents: [agent_a_name, agent_b_name]
        - step.collaboration_config: CollaborationConfig
        - input_data: Contains 'character' and 'context' keys
        """
        from .collaboration import CollaborationAgent

        if not step.collaboration_config:
            raise ValueError("Roleplay collaboration requires collaboration_config")

        if len(step.agents) < 2:
            raise ValueError("Roleplay collaboration requires 2 agents")

        agent_a = self.pool.get(step.agents[0])
        agent_b = self.pool.get(step.agents[1])
        context = input_data.get('context', '')
        character = input_data.get('character', '')

        collab = CollaborationAgent(self.llm_caller)
        result = await collab.execute_roleplay(agent_a, agent_b, context, character, step.collaboration_config)

        # Convert CollaborationResult to PoolResult format
        from .agent_pool import ExecutionResult

        execution = ExecutionResult(
            agent_name="Roleplay Collaboration",
            response=AgentResponse.success_response(result),
            execution_time=result.total_time,
            tokens_used=result.total_tokens
        )

        pool_result = PoolResult(
            executions=[execution],
            total_time=result.total_time,
            success_count=1 if result.success else 0,
            failure_count=0 if result.success else 1
        )

        logger.info(f"Roleplay collaboration completed: {character}")
        return pool_result

