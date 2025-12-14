"""
Greenlight Shot Pipeline

Pipeline for generating shot lists from story beats.
Integrates with ReferenceManager for per-shot reference image loading.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from greenlight.llm import LLMManager, FunctionRouter
from greenlight.tags import TagParser, TagRegistry
from .base_pipeline import BasePipeline, PipelineStep

logger = get_logger("pipelines.shot")

# Import ReferenceManager with fallback
try:
    from greenlight.references import ReferenceManager
    HAS_REFERENCE_MANAGER = True
except ImportError:
    HAS_REFERENCE_MANAGER = False
    ReferenceManager = None


@dataclass
class ShotInput:
    """Input for the shot pipeline."""
    beat_id: str
    beat_content: str
    scene_number: int
    tags: List[str] = field(default_factory=list)
    previous_shots: List[str] = field(default_factory=list)
    style_guide: str = ""


@dataclass
class Shot:
    """A single shot in the shot list."""
    shot_id: str
    shot_number: int
    description: str
    shot_type: str
    duration_estimate: str
    characters: List[str]
    action: str
    dialogue: str = ""
    notes: str = ""
    # Reference data for image generation
    reference_tags: List[str] = field(default_factory=list)
    reference_images: List[Dict] = field(default_factory=list)


@dataclass
class ShotOutput:
    """Output from the shot pipeline."""
    beat_id: str
    shots: List[Shot]
    total_shots: int
    estimated_duration: str
    tags_used: List[str]


class ShotPipeline(BasePipeline[ShotInput, ShotOutput]):
    """
    Pipeline for generating shot lists from beats.

    Steps:
    1. Analyze beat content
    2. Identify key moments
    3. Generate shot descriptions
    4. Assign shot types
    5. Estimate timing
    6. Load references (if ReferenceManager available)
    """

    def __init__(
        self,
        llm_manager: LLMManager = None,
        tag_registry: TagRegistry = None,
        project_path: Path = None,
        reference_manager: 'ReferenceManager' = None
    ):
        self.llm_manager = llm_manager or LLMManager()
        self.tag_registry = tag_registry or TagRegistry()

        self.function_router = FunctionRouter(self.llm_manager)
        self.tag_parser = TagParser()

        # Initialize reference manager if project path provided
        self.reference_manager = reference_manager
        if self.reference_manager is None and project_path and HAS_REFERENCE_MANAGER:
            self.reference_manager = ReferenceManager(
                project_path=project_path,
                tag_registry=self.tag_registry
            )

        super().__init__("shot_pipeline")
    
    def _define_steps(self) -> None:
        """Define pipeline steps."""
        self._steps = [
            PipelineStep(
                name="analyze_beat",
                description="Analyze beat for shot opportunities"
            ),
            PipelineStep(
                name="identify_moments",
                description="Identify key visual moments"
            ),
            PipelineStep(
                name="generate_shots",
                description="Generate shot descriptions"
            ),
            PipelineStep(
                name="assign_types",
                description="Assign shot types and angles"
            ),
            PipelineStep(
                name="load_references",
                description="Load reference images for each shot"
            ),
            PipelineStep(
                name="estimate_timing",
                description="Estimate shot durations"
            ),
        ]
    
    async def _execute_step(
        self,
        step: PipelineStep,
        input_data: Any,
        context: Dict[str, Any]
    ) -> Any:
        """Execute a pipeline step."""
        if step.name == "analyze_beat":
            return await self._analyze_beat(input_data, context)
        elif step.name == "identify_moments":
            return await self._identify_moments(input_data, context)
        elif step.name == "generate_shots":
            return await self._generate_shots(input_data, context)
        elif step.name == "assign_types":
            return await self._assign_types(input_data, context)
        elif step.name == "load_references":
            return await self._load_references(input_data, context)
        elif step.name == "estimate_timing":
            return await self._estimate_timing(input_data, context)
        return input_data
    
    async def _analyze_beat(
        self,
        input_data: ShotInput,
        context: Dict
    ) -> Dict[str, Any]:
        """Analyze beat content."""
        return {
            'input': input_data,
            'beat_content': input_data.beat_content,
            'tags': input_data.tags,
            'scene_num': input_data.scene_number
        }
    
    async def _identify_moments(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Identify key visual moments."""
        prompt = f"""Identify 2-4 key visual moments in this story beat.
Each moment should be a distinct shot opportunity.

Beat: {data['beat_content']}
Characters: {', '.join(data['tags'])}

List each moment briefly:
MOMENT 1: [description]
MOMENT 2: [description]
"""
        
        response = await self.function_router.route(
            function=LLMFunction.SHOT_PLANNING,
            prompt=prompt,
            system_prompt="You are a cinematographer identifying shot opportunities."
        )
        
        moments = self._parse_moments(response)
        data['moments'] = moments
        return data
    
    async def _generate_shots(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Generate shot descriptions."""
        shots = []
        input_data = data['input']
        
        for i, moment in enumerate(data.get('moments', [{'description': data['beat_content']}])):
            shot = Shot(
                shot_id=f"{input_data.beat_id}_S{i+1:02d}",
                shot_number=i + 1,
                description=moment.get('description', ''),
                shot_type='medium',
                duration_estimate='3s',
                characters=[t for t in data['tags'] if not t.startswith('LOC_')],
                action=moment.get('description', '')
            )
            shots.append(shot)
        
        data['shots'] = shots
        return data
    
    async def _assign_types(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Assign shot types."""
        # Would use LLM for more sophisticated assignment
        shot_types = ['wide', 'medium', 'close-up', 'medium']

        for i, shot in enumerate(data.get('shots', [])):
            shot.shot_type = shot_types[i % len(shot_types)]

        return data

    async def _load_references(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> Dict[str, Any]:
        """Load reference images for each shot based on tags."""
        if not self.reference_manager:
            logger.debug("No reference manager available, skipping reference loading")
            return data

        shots = data.get('shots', [])
        aspect_ratio = context.get('aspect_ratio', '16:9')

        for shot in shots:
            # Build a prompt-like string from shot description and characters
            shot_text = f"{shot.description} "
            for char in shot.characters:
                shot_text += f"[{char}] "

            # Get references for this shot
            ref_tags, ref_images = self.reference_manager.get_references_for_shot(
                prompt=shot_text,
                aspect_ratio=aspect_ratio
            )

            shot.reference_tags = ref_tags
            shot.reference_images = ref_images

            if ref_tags:
                logger.debug(f"Shot {shot.shot_id}: loaded {len(ref_images)} references for tags {ref_tags}")

        return data

    async def _estimate_timing(
        self,
        data: Dict[str, Any],
        context: Dict
    ) -> ShotOutput:
        """Estimate timing and build output."""
        shots = data.get('shots', [])
        input_data = data['input']
        
        # Simple timing estimation
        total_seconds = len(shots) * 3
        
        return ShotOutput(
            beat_id=input_data.beat_id,
            shots=shots,
            total_shots=len(shots),
            estimated_duration=f"{total_seconds}s",
            tags_used=data.get('tags', [])
        )
    
    def _parse_moments(self, response: str) -> List[Dict]:
        """Parse moments from LLM response."""
        import re
        moments = []
        pattern = r'MOMENT\s+(\d+):\s*(.+?)(?=MOMENT|\Z)'
        matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
        
        for num, desc in matches:
            moments.append({
                'number': int(num),
                'description': desc.strip()
            })
        
        return moments if moments else [{'description': 'Main action'}]

