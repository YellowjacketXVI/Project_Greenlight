"""
Mirror Agent - Self-Reflection Pattern

An agent that generates content, then "mirrors" itself to critique its own
output, iterating until self-satisfaction or max iterations reached.

Process:
1. GENERATOR MODE: Create content
2. MIRROR MODE: Critique own output against rubric
3. REFINEMENT MODE: Improve based on self-critique
4. Loop until satisfied or max iterations
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
import re

from greenlight.core.logging_config import get_logger
from .universal_context import UniversalContext, SceneContext

logger = get_logger("patterns.quality.mirror")


@dataclass
class MirrorCritique:
    """Self-critique from mirror mode."""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    specific_fixes: List[str] = field(default_factory=list)
    satisfaction_score: float = 0.0  # 0-1


@dataclass
class MirrorIteration:
    """One iteration of the mirror loop."""
    iteration: int
    content: str
    critique: MirrorCritique
    satisfaction_score: float


@dataclass
class MirrorResult:
    """Complete result from Mirror Agent."""
    final_content: str
    iterations: List[MirrorIteration]
    final_score: float
    converged: bool
    total_iterations: int


class MirrorAgent:
    """
    Agent that generates, critiques, and refines its own output.
    
    Uses self-reflection to iteratively improve content quality.
    """
    
    def __init__(
        self,
        llm_caller: Callable,
        rubric: Optional[Dict[str, Any]] = None,
        max_iterations: int = 3,
        satisfaction_threshold: float = 0.85
    ):
        self.llm_caller = llm_caller
        self.rubric = rubric or self._default_rubric()
        self.max_iterations = max_iterations
        self.satisfaction_threshold = satisfaction_threshold
    
    def _default_rubric(self) -> Dict[str, Any]:
        """Default quality rubric for self-critique."""
        return {
            "visual_clarity": {
                "weight": 0.2,
                "criteria": "Each beat can be captured as a clear, frameable image"
            },
            "character_authenticity": {
                "weight": 0.2,
                "criteria": "Characters act and speak according to their established traits"
            },
            "narrative_flow": {
                "weight": 0.2,
                "criteria": "Story flows naturally with clear cause-and-effect"
            },
            "world_integration": {
                "weight": 0.2,
                "criteria": "World details from world_config are actively demonstrated"
            },
            "notation_correctness": {
                "weight": 0.2,
                "criteria": "Tags and notation follow proper format"
            }
        }
    
    async def generate_and_refine(
        self,
        scene_context: SceneContext,
        universal_context: UniversalContext,
        initial_content: Optional[str] = None
    ) -> MirrorResult:
        """
        Generate content with self-reflection loop.
        
        Args:
            scene_context: Scene-specific context
            universal_context: Universal context with world_config + pitch
            initial_content: Optional initial content to refine
            
        Returns:
            MirrorResult with final content and iteration history
        """
        iterations = []
        current_content = initial_content
        
        for i in range(self.max_iterations):
            logger.info(f"MirrorAgent: Iteration {i + 1}/{self.max_iterations}")
            
            if current_content is None:
                # Generator mode - create initial content
                current_content = await self._generate(scene_context, universal_context)
            
            # Mirror mode - critique own output
            critique = await self._mirror_critique(
                current_content, scene_context, universal_context
            )
            
            iterations.append(MirrorIteration(
                iteration=i + 1,
                content=current_content,
                critique=critique,
                satisfaction_score=critique.satisfaction_score
            ))
            
            # Check if satisfied
            if critique.satisfaction_score >= self.satisfaction_threshold:
                logger.info(f"MirrorAgent: Satisfied at iteration {i + 1} "
                           f"(score: {critique.satisfaction_score:.2f})")
                break
            
            # Refinement mode - improve based on critique
            if i < self.max_iterations - 1:  # Don't refine on last iteration
                current_content = await self._refine(
                    current_content, critique, scene_context, universal_context
                )
        
        final_score = iterations[-1].satisfaction_score if iterations else 0.0
        
        return MirrorResult(
            final_content=current_content or "",
            iterations=iterations,
            final_score=final_score,
            converged=final_score >= self.satisfaction_threshold,
            total_iterations=len(iterations)
        )
    
    async def refine_existing(
        self,
        content: str,
        scene_context: SceneContext,
        universal_context: UniversalContext
    ) -> MirrorResult:
        """
        Refine existing content through self-reflection.
        
        Args:
            content: Existing content to refine
            scene_context: Scene-specific context
            universal_context: Universal context
            
        Returns:
            MirrorResult with refined content
        """
        return await self.generate_and_refine(
            scene_context=scene_context,
            universal_context=universal_context,
            initial_content=content
        )

    async def _generate(
        self,
        scene_context: SceneContext,
        universal_context: UniversalContext
    ) -> str:
        """Generate initial content in generator mode."""
        prompt = f"""You are generating content for Scene {scene_context.scene_number}.

{universal_context.for_scene_prompt(scene_context)}

WORLD STYLE:
{universal_context.style_context}

Generate scene content that:
1. Advances the scene's purpose: {scene_context.scene_purpose}
2. Uses proper tag notation: [CHAR_TAG], [LOC_TAG], [PROP_TAG]
3. Creates visually frameable moments
4. Demonstrates world details from world_config
5. Maintains character authenticity

OUTPUT:
Generate the scene prose with proper formatting.
"""
        return await self.llm_caller(prompt)

    async def _mirror_critique(
        self,
        content: str,
        scene_context: SceneContext,
        universal_context: UniversalContext
    ) -> MirrorCritique:
        """Critique own output in mirror mode."""
        rubric_text = self._format_rubric()

        prompt = f"""You just generated the following content for Scene {scene_context.scene_number}.
Now, step back and critically evaluate your own work.

YOUR GENERATED CONTENT:
{content}

SCENE REQUIREMENTS:
Purpose: {scene_context.scene_purpose}
Characters: {[c.get('tag') for c in scene_context.characters]}
Location: {scene_context.location.get('tag') if scene_context.location else 'Unknown'}

WORLD CONTEXT:
{universal_context.style_context}
Themes: {universal_context.world_config.get('themes', '')}

EVALUATION RUBRIC:
{rubric_text}

Be HONEST and CRITICAL. Evaluate your work against each rubric criterion.

Identify:
1. STRENGTHS: What you did well (list 2-4 items)
2. WEAKNESSES: Where you fell short (list 2-4 items)
3. SPECIFIC_FIXES: Exact changes to make (list specific, actionable fixes)
4. SATISFACTION_SCORE: 0.0-1.0 (how satisfied are you with this output?)

Format:
STRENGTHS:
- [strength 1]
- [strength 2]
...
WEAKNESSES:
- [weakness 1]
- [weakness 2]
...
SPECIFIC_FIXES:
- [fix 1]
- [fix 2]
...
SATISFACTION_SCORE: [0.0-1.0]
"""

        response = await self.llm_caller(prompt)
        return self._parse_critique(response)

    async def _refine(
        self,
        content: str,
        critique: MirrorCritique,
        scene_context: SceneContext,
        universal_context: UniversalContext
    ) -> str:
        """Refine content based on self-critique."""
        prompt = f"""You are improving your previous work based on your own critique.

ORIGINAL CONTENT:
{content}

YOUR CRITIQUE:
Weaknesses:
{chr(10).join('- ' + w for w in critique.weaknesses)}

Specific Fixes Needed:
{chr(10).join('- ' + f for f in critique.specific_fixes)}

SCENE REQUIREMENTS:
Purpose: {scene_context.scene_purpose}
Characters: {[c.get('tag') for c in scene_context.characters]}

WORLD CONTEXT:
{universal_context.style_context}

Generate an IMPROVED version that:
1. Addresses ALL the weaknesses you identified
2. Implements ALL the specific fixes
3. Maintains what was working well (your strengths)
4. Keeps proper tag notation

OUTPUT:
Generate the improved scene content.
"""
        return await self.llm_caller(prompt)

    def _format_rubric(self) -> str:
        """Format rubric for prompt."""
        lines = []
        for name, details in self.rubric.items():
            lines.append(f"- {name} (weight: {details['weight']}): {details['criteria']}")
        return "\n".join(lines)

    def _parse_critique(self, response: str) -> MirrorCritique:
        """Parse critique from LLM response."""
        def extract_list(header: str) -> List[str]:
            pattern = rf'{header}:\s*\n((?:[-•]\s*.+\n?)+)'
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                items = re.findall(r'[-•]\s*(.+)', match.group(1))
                return [item.strip() for item in items if item.strip()]
            return []

        # Extract satisfaction score
        score_match = re.search(r'SATISFACTION_SCORE:\s*([\d.]+)', response, re.IGNORECASE)
        score = 0.5
        if score_match:
            try:
                score = min(1.0, max(0.0, float(score_match.group(1))))
            except ValueError:
                pass

        return MirrorCritique(
            strengths=extract_list('STRENGTHS'),
            weaknesses=extract_list('WEAKNESSES'),
            specific_fixes=extract_list('SPECIFIC_FIXES'),
            satisfaction_score=score
        )
