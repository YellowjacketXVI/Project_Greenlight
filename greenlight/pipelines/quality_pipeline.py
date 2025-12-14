"""
Greenlight Quality Pipeline

Pipeline for validating and improving content quality.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from greenlight.llm import LLMManager, FunctionRouter
from greenlight.tags import TagParser, TagRegistry
from .base_pipeline import BasePipeline, PipelineStep

logger = get_logger("pipelines.quality")


class QualityLevel(Enum):
    """Quality assessment levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    NEEDS_IMPROVEMENT = "needs_improvement"
    POOR = "poor"


@dataclass
class QualityIssue:
    """A quality issue found during validation."""
    issue_type: str
    severity: str  # critical, major, minor
    description: str
    location: str
    suggestion: str


@dataclass
class QualityInput:
    """Input for quality validation."""
    content: str
    content_type: str  # beat, prompt, scene
    tags: List[str] = field(default_factory=list)
    context: str = ""


@dataclass
class QualityOutput:
    """Output from quality validation."""
    level: QualityLevel
    score: float  # 0-100
    issues: List[QualityIssue]
    suggestions: List[str]
    improved_content: Optional[str] = None
    passed: bool = True


class QualityPipeline(BasePipeline[QualityInput, QualityOutput]):
    """
    Pipeline for content quality validation.
    
    Steps:
    1. Check tag consistency
    2. Validate language quality
    3. Check continuity
    4. Assess visual clarity
    5. Generate improvements
    """
    
    def __init__(
        self,
        llm_manager: LLMManager = None,
        tag_registry: TagRegistry = None,
        min_quality_score: float = 70.0
    ):
        self.llm_manager = llm_manager or LLMManager()
        self.tag_registry = tag_registry or TagRegistry()
        self.min_quality_score = min_quality_score
        
        self.function_router = FunctionRouter(self.llm_manager)
        self.tag_parser = TagParser()
        
        super().__init__("quality_pipeline")
    
    def _define_steps(self) -> None:
        """Define pipeline steps."""
        self._steps = [
            PipelineStep(
                name="tag_check",
                description="Check tag consistency and validity"
            ),
            PipelineStep(
                name="language_check",
                description="Validate language quality"
            ),
            PipelineStep(
                name="continuity_check",
                description="Check for continuity issues"
            ),
            PipelineStep(
                name="clarity_check",
                description="Assess visual clarity for prompts"
            ),
            PipelineStep(
                name="generate_improvements",
                description="Generate improvement suggestions",
                required=False
            ),
        ]
    
    async def _execute_step(
        self,
        step: PipelineStep,
        input_data: Any,
        context: Dict[str, Any]
    ) -> Any:
        """Execute a pipeline step."""
        if step.name == "tag_check":
            return await self._tag_check(input_data, context)
        elif step.name == "language_check":
            return await self._language_check(input_data, context)
        elif step.name == "continuity_check":
            return await self._continuity_check(input_data, context)
        elif step.name == "clarity_check":
            return await self._clarity_check(input_data, context)
        elif step.name == "generate_improvements":
            return await self._generate_improvements(input_data, context)
        return input_data
    
    async def _tag_check(
        self,
        input_data: QualityInput,
        context: Dict
    ) -> Dict[str, Any]:
        """Check tag consistency."""
        issues = []
        
        # Extract tags from content
        found_tags = self.tag_parser.extract_unique_tags(input_data.content)
        
        # Check for unregistered tags
        for tag in found_tags:
            if not self.tag_registry.exists(tag):
                issues.append(QualityIssue(
                    issue_type="unregistered_tag",
                    severity="minor",
                    description=f"Tag [{tag}] is not registered",
                    location="content",
                    suggestion=f"Register [{tag}] in the tag registry"
                ))
        
        # Check for missing expected tags
        for tag in input_data.tags:
            if tag not in found_tags:
                issues.append(QualityIssue(
                    issue_type="missing_tag",
                    severity="major",
                    description=f"Expected tag [{tag}] not found in content",
                    location="content",
                    suggestion=f"Add [{tag}] to the content"
                ))
        
        return {
            'input': input_data,
            'issues': issues,
            'found_tags': list(found_tags),
            'scores': {'tag_consistency': 100 - len(issues) * 10}
        }
    
    async def _language_check(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Check language quality."""
        input_data = data['input']
        
        # Check for vague words
        vague_words = ['something', 'somehow', 'thing', 'stuff', 'very', 'really']
        content_lower = input_data.content.lower()
        
        vague_count = sum(1 for word in vague_words if word in content_lower)
        
        if vague_count > 2:
            data['issues'].append(QualityIssue(
                issue_type="vague_language",
                severity="minor",
                description=f"Found {vague_count} vague words",
                location="content",
                suggestion="Use more specific, descriptive language"
            ))
        
        # Check content length
        word_count = len(input_data.content.split())
        if word_count < 10:
            data['issues'].append(QualityIssue(
                issue_type="too_short",
                severity="major",
                description="Content is too brief",
                location="content",
                suggestion="Add more detail and description"
            ))
        
        data['scores']['language_quality'] = max(0, 100 - vague_count * 5 - (10 if word_count < 10 else 0))
        return data
    
    async def _continuity_check(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Check for continuity issues."""
        # Would check against project context in full implementation
        data['scores']['continuity'] = 100
        return data
    
    async def _clarity_check(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Check visual clarity for prompts."""
        input_data = data['input']
        
        if input_data.content_type == 'prompt':
            # Check for visual descriptors
            visual_keywords = ['camera', 'shot', 'angle', 'lighting', 'color', 'composition']
            has_visual = any(kw in input_data.content.lower() for kw in visual_keywords)
            
            if not has_visual:
                data['issues'].append(QualityIssue(
                    issue_type="missing_visual_details",
                    severity="major",
                    description="Prompt lacks visual/camera details",
                    location="content",
                    suggestion="Add camera angle, shot type, and lighting details"
                ))
        
        data['scores']['clarity'] = 100 if 'missing_visual_details' not in [i.issue_type for i in data['issues']] else 70
        return data
    
    async def _generate_improvements(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> QualityOutput:
        """Generate improvement suggestions and final output."""
        issues = data.get('issues', [])
        scores = data.get('scores', {})
        
        # Calculate overall score
        if scores:
            overall_score = sum(scores.values()) / len(scores)
        else:
            overall_score = 100
        
        # Determine quality level
        if overall_score >= 90:
            level = QualityLevel.EXCELLENT
        elif overall_score >= 80:
            level = QualityLevel.GOOD
        elif overall_score >= 70:
            level = QualityLevel.ACCEPTABLE
        elif overall_score >= 50:
            level = QualityLevel.NEEDS_IMPROVEMENT
        else:
            level = QualityLevel.POOR
        
        # Generate suggestions
        suggestions = [issue.suggestion for issue in issues]
        
        # Generate improved content if needed
        improved_content = None
        if overall_score < self.min_quality_score and issues:
            improved_content = await self._improve_content(data['input'], issues)
        
        return QualityOutput(
            level=level,
            score=overall_score,
            issues=issues,
            suggestions=suggestions,
            improved_content=improved_content,
            passed=overall_score >= self.min_quality_score
        )
    
    async def _improve_content(
        self,
        input_data: QualityInput,
        issues: List[QualityIssue]
    ) -> str:
        """Generate improved content."""
        issues_text = "\n".join(f"- {i.description}: {i.suggestion}" for i in issues)
        
        prompt = f"""Improve this content based on the issues found.

Original content:
{input_data.content}

Issues to fix:
{issues_text}

Provide an improved version that addresses all issues.
"""
        
        response = await self.function_router.route(
            function=LLMFunction.QUALITY_CHECK,
            prompt=prompt,
            system_prompt="You are a content editor improving story and prompt quality."
        )
        
        return response.strip()

