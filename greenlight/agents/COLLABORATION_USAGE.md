# Collaborative Execution - Usage Guide

## Overview

The collaboration framework enables two agents to engage in structured dialogue for iterative refinement and deep exploration.

## Two Collaboration Modes

### 1. SOCRATIC_COLLABORATION

Iterative refinement through dialectical questioning.

```python
from greenlight.agents import (
    CollaborationAgent,
    CollaborationConfig,
    CollaborationMode,
    ExecutionMode,
    WorkflowStep,
)

# Create collaboration config
config = CollaborationConfig(
    mode=CollaborationMode.SOCRATIC,
    agent_a_name="ideator",
    agent_b_name="pragmatist",
    max_iterations=4,
    convergence_threshold=0.80
)

# Create collaboration agent
collab = CollaborationAgent(llm_caller=your_llm_function)

# Execute
result = await collab.execute_socratic(
    agent_a=ideator_agent,
    agent_b=pragmatist_agent,
    goal="Create a compelling magic system",
    config=config
)

# Access results
print(f"Converged: {result.convergence_achieved}")
print(f"Iterations: {result.iterations_completed}")
print(f"Final output: {result.final_output}")
print(f"Insights: {result.insights}")
print(f"Transcript:\n{result.dialogue_transcript}")
```

### 2. ROLEPLAY_COLLABORATION

Embodied perspective-taking for authenticity validation.

```python
# Create collaboration config
config = CollaborationConfig(
    mode=CollaborationMode.ROLEPLAY,
    agent_a_name="roleplay_agent",
    agent_b_name="instructor_agent",
    max_iterations=5
)

# Execute
result = await collab.execute_roleplay(
    agent_a=roleplay_agent,
    agent_b=instructor_agent,
    context="Medieval tavern, late evening",
    character="Grizzled mercenary with a hidden past",
    config=config
)

# Access results
print(f"Character responses: {result.insights['character_responses']}")
print(f"Exploration depth: {result.insights['exploration_depth']}")
print(f"Transcript:\n{result.dialogue_transcript}")
```

## Using in Workflows

### Socratic Step

```python
from greenlight.agents import OrchestratorAgent, WorkflowStep, ExecutionMode

orchestrator = OrchestratorAgent(pool=agent_pool)

# Define workflow with Socratic collaboration
orchestrator.define_workflow("story_refinement", [
    WorkflowStep(
        name="Socratic Refinement",
        agents=['ideator', 'pragmatist'],
        mode=ExecutionMode.SOCRATIC_COLLABORATION,
        collaboration_config=CollaborationConfig(
            mode=CollaborationMode.SOCRATIC,
            agent_a_name='ideator',
            agent_b_name='pragmatist',
            max_iterations=4,
            convergence_threshold=0.80
        ),
        input_mapping={'goal': 'initial_concept'},
        output_key="refined_concept"
    )
])

# Run workflow
result = await orchestrator.run_workflow("story_refinement", {
    'initial_concept': 'A story about time travel'
})

print(result.outputs['refined_concept'])
```

### Roleplay Step

```python
orchestrator.define_workflow("character_development", [
    WorkflowStep(
        name="Character Exploration",
        agents=['roleplay_agent', 'instructor_agent'],
        mode=ExecutionMode.ROLEPLAY_COLLABORATION,
        collaboration_config=CollaborationConfig(
            mode=CollaborationMode.ROLEPLAY,
            agent_a_name='roleplay_agent',
            agent_b_name='instructor_agent',
            max_iterations=5
        ),
        input_mapping={
            'character': 'character_description',
            'context': 'story_context'
        },
        output_key="character_insights"
    )
])

# Run workflow
result = await orchestrator.run_workflow("character_development", {
    'character_description': 'Detective Sarah Chen - haunted by unsolved case',
    'story_context': 'Interrogation room, late night'
})

print(result.outputs['character_insights'])
```

## Convergence Strategies

### Conservative (High Confidence)
```python
config = CollaborationConfig(
    mode=CollaborationMode.SOCRATIC,
    agent_a_name="ideator",
    agent_b_name="pragmatist",
    max_iterations=5,
    convergence_threshold=0.90  # Strict agreement
)
```

### Balanced (Recommended)
```python
config = CollaborationConfig(
    mode=CollaborationMode.SOCRATIC,
    agent_a_name="ideator",
    agent_b_name="pragmatist",
    max_iterations=4,
    convergence_threshold=0.80  # Reasonable agreement
)
```

### Exploratory (Deep Dive)
```python
config = CollaborationConfig(
    mode=CollaborationMode.SOCRATIC,
    agent_a_name="ideator",
    agent_b_name="pragmatist",
    max_iterations=7,
    convergence_threshold=0.70  # Allow exploration
)
```

## Monitoring Collaboration

```python
# Check convergence
if result.convergence_achieved:
    print(f"✅ Converged in {result.iterations_completed} iterations")
else:
    print(f"⚠️ No convergence after {result.iterations_completed} iterations")

# Analyze turns
for turn in result.turns:
    print(f"Turn {turn.turn_number}: {turn.agent_name}")
    print(f"  Response: {turn.response[:100]}...")
    print(f"  Tokens: {turn.tokens_used}")
    print(f"  Time: {turn.execution_time:.2f}s")

# Extract insights
for key, value in result.insights.items():
    print(f"{key}: {value}")

# View full transcript
print(result.dialogue_transcript)
```

## Error Handling

```python
try:
    result = await collab.execute_socratic(...)
    
    if not result.success:
        print(f"Failed: {result.errors}")
    
    if not result.convergence_achieved:
        print("Warning: No convergence")
        # Use partial result
        print(result.final_output)
        
except Exception as e:
    print(f"Error: {e}")
    # Fallback to single agent
```

## Data Structures

### CollaborationConfig
```python
@dataclass
class CollaborationConfig:
    mode: CollaborationMode
    agent_a_name: str
    agent_b_name: str
    max_iterations: int = 5
    convergence_threshold: float = 0.85
    temperature_a: Optional[float] = None
    temperature_b: Optional[float] = None
    system_prompt_a: str = ""
    system_prompt_b: str = ""
    metadata: Dict[str, Any] = {}
```

### CollaborationResult
```python
@dataclass
class CollaborationResult:
    success: bool
    mode: CollaborationMode
    turns: List[CollaborationTurn]
    final_output: str
    convergence_achieved: bool
    iterations_completed: int
    total_time: float
    total_tokens: int
    dialogue_transcript: str
    insights: Dict[str, Any]
    errors: List[str] = []
```

## Best Practices

1. **Choose the right mode**
   - Socratic: Logic/structure problems
   - Roleplay: Character/perspective problems

2. **Set appropriate convergence threshold**
   - 0.90: Critical decisions
   - 0.80: Most use cases (recommended)
   - 0.70: Complex exploration

3. **Monitor token usage**
   - Collaboration uses 2x tokens (two agents)
   - Track total_tokens in result

4. **Use in pipelines**
   - Socratic before Roleplay for comprehensive refinement
   - Parallel execution for independent collaborations

5. **Extract insights**
   - CollaborationResult.insights contains structured data
   - Use dialogue_transcript for detailed analysis

## Integration Points

- **Story Pipeline**: Refine story structure and character authenticity
- **Director Pipeline**: Validate shot logic and character perspective
- **Quality Pipeline**: Check logic consistency and dialogue authenticity
- **Beat Sheet**: Enhance with collaborative refinement
- **Script Output**: Validate dialogue and character consistency

## Next Steps

1. Register agents in AgentPool
2. Create CollaborationConfig
3. Define workflow with collaboration steps
4. Run workflow and monitor results
5. Extract insights and refine as needed

