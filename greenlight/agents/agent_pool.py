"""
Greenlight Agent Pool

Manages a pool of specialized agents for parallel execution.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type, Any, Callable
import asyncio

from greenlight.core.logging_config import get_logger
from .base_agent import BaseAgent, AgentConfig, AgentResponse

logger = get_logger("agents.pool")


@dataclass
class PooledExecution:
    """Result of a pooled agent execution."""
    agent_name: str
    response: AgentResponse
    execution_order: int


@dataclass
class PoolResult:
    """Result of executing multiple agents."""
    executions: List[PooledExecution]
    total_time: float
    success_count: int
    failure_count: int
    
    @property
    def all_successful(self) -> bool:
        return self.failure_count == 0
    
    def get_response(self, agent_name: str) -> Optional[AgentResponse]:
        """Get response from a specific agent."""
        for execution in self.executions:
            if execution.agent_name == agent_name:
                return execution.response
        return None
    
    def get_all_content(self) -> List[Any]:
        """Get content from all successful executions."""
        return [
            ex.response.content
            for ex in self.executions
            if ex.response.success
        ]


class AgentPool:
    """
    Manages a pool of agents for parallel or sequential execution.
    
    Features:
    - Agent registration and management
    - Parallel execution with asyncio
    - Sequential execution with dependency ordering
    - Result aggregation
    """
    
    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        max_concurrent: int = 5
    ):
        """
        Initialize the agent pool.
        
        Args:
            llm_caller: Shared LLM caller for all agents
            max_concurrent: Maximum concurrent agent executions
        """
        self.llm_caller = llm_caller
        self.max_concurrent = max_concurrent
        self._agents: Dict[str, BaseAgent] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    def register(self, agent: BaseAgent) -> None:
        """
        Register an agent in the pool.
        
        Args:
            agent: Agent instance to register
        """
        if agent.name in self._agents:
            logger.warning(f"Replacing existing agent: {agent.name}")
        
        self._agents[agent.name] = agent
        logger.debug(f"Registered agent: {agent.name}")
    
    def register_many(self, agents: List[BaseAgent]) -> None:
        """Register multiple agents."""
        for agent in agents:
            self.register(agent)
    
    def get(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self._agents.get(name)
    
    def list_agents(self) -> List[str]:
        """List all registered agent names."""
        return list(self._agents.keys())
    
    async def execute_parallel(
        self,
        agent_names: List[str],
        input_data: Dict[str, Any]
    ) -> PoolResult:
        """
        Execute multiple agents in parallel.
        
        Args:
            agent_names: Names of agents to execute
            input_data: Shared input data for all agents
            
        Returns:
            PoolResult with all executions
        """
        import time
        start_time = time.time()
        
        tasks = []
        for i, name in enumerate(agent_names):
            agent = self._agents.get(name)
            if agent:
                task = self._execute_with_semaphore(agent, input_data, i)
                tasks.append(task)
            else:
                logger.warning(f"Agent not found: {name}")
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        executions = []
        success_count = 0
        failure_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                executions.append(PooledExecution(
                    agent_name=agent_names[i],
                    response=AgentResponse.error_response(str(result)),
                    execution_order=i
                ))
                failure_count += 1
            else:
                executions.append(result)
                if result.response.success:
                    success_count += 1
                else:
                    failure_count += 1
        
        total_time = time.time() - start_time
        
        logger.info(
            f"Parallel execution complete: {success_count} success, "
            f"{failure_count} failed in {total_time:.2f}s"
        )
        
        return PoolResult(
            executions=executions,
            total_time=total_time,
            success_count=success_count,
            failure_count=failure_count
        )
    
    async def _execute_with_semaphore(
        self,
        agent: BaseAgent,
        input_data: Dict[str, Any],
        order: int
    ) -> PooledExecution:
        """Execute an agent with semaphore control."""
        async with self._semaphore:
            response = await agent.execute(input_data)
            return PooledExecution(
                agent_name=agent.name,
                response=response,
                execution_order=order
            )
    
    async def execute_sequential(
        self,
        agent_names: List[str],
        input_data: Dict[str, Any],
        pass_results: bool = False
    ) -> PoolResult:
        """
        Execute agents sequentially.
        
        Args:
            agent_names: Names of agents in execution order
            input_data: Initial input data
            pass_results: If True, pass previous results to next agent
            
        Returns:
            PoolResult with all executions
        """
        import time
        start_time = time.time()
        
        executions = []
        success_count = 0
        failure_count = 0
        current_data = input_data.copy()
        
        for i, name in enumerate(agent_names):
            agent = self._agents.get(name)
            if not agent:
                logger.warning(f"Agent not found: {name}")
                continue
            
            try:
                response = await agent.execute(current_data)
                
                executions.append(PooledExecution(
                    agent_name=name,
                    response=response,
                    execution_order=i
                ))
                
                if response.success:
                    success_count += 1
                    if pass_results:
                        current_data['previous_result'] = response.content
                else:
                    failure_count += 1
                    if pass_results:
                        break  # Stop on failure when passing results
                        
            except Exception as e:
                executions.append(PooledExecution(
                    agent_name=name,
                    response=AgentResponse.error_response(str(e)),
                    execution_order=i
                ))
                failure_count += 1
                if pass_results:
                    break
        
        total_time = time.time() - start_time
        
        return PoolResult(
            executions=executions,
            total_time=total_time,
            success_count=success_count,
            failure_count=failure_count
        )

