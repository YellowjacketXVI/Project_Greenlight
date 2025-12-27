"""
Unified Reference Script - Single entry point for all reference image generation.

This module provides a unified API for generating reference images that:
1. Maps 1:1 to UI button operations
2. Enforces consistent naming conventions
3. Routes through proper pipelines (ReferencePromptBuilder, ImageHandler)
4. Enforces Seedream blank-first requirement at ImageHandler level

NOTE: Uses template-based prompt building (no LLM calls for prompts).

NAMING CONVENTION:
    {action}_{scope?}_{entity_type}_{output_type}
    
    - action: generate, convert, get, list
    - scope: all (optional, omit for single-tag)
    - entity_type: character, location, prop, reference
    - output_type: sheet, views, from_image, status

See .augment-guidelines for full specification.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from greenlight.core.logging_config import get_logger

if TYPE_CHECKING:
    from greenlight.core.image_handler import ImageHandler, ImageModel, ImageResult
    from greenlight.context.context_engine import ContextEngine
    from greenlight.references.prompt_builder import ReferencePromptBuilder
    from greenlight.omni_mind.autonomous_agent import ImageAnalysisResult

logger = get_logger("references.unified")


class ReferenceType(Enum):
    """Types of reference generation."""
    CHARACTER_SHEET = "character_sheet"
    CHARACTER_FROM_IMAGE = "character_from_image"
    LOCATION_VIEWS = "location_views"
    PROP_SHEET = "prop_sheet"


@dataclass
class ReferenceResult:
    """Result from single-tag reference generation."""
    success: bool
    reference_type: ReferenceType
    tag: str
    image_paths: List[Path] = field(default_factory=list)
    profile_updated: bool = False
    error: Optional[str] = None
    generation_time_ms: int = 0


@dataclass
class BatchResult:
    """Result from batch reference generation."""
    success: bool
    total: int
    completed: int
    failed: int
    skipped: int = 0
    results: List[ReferenceResult] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)


@dataclass
class ReferenceStatus:
    """Status of references for a single tag."""
    tag: str
    entity_type: str  # "character", "location", "prop"
    has_sheet: bool = False
    has_views: bool = False
    has_key_reference: bool = False
    image_count: int = 0
    last_updated: Optional[datetime] = None


class UnifiedReferenceScript:
    """
    Single entry point for all reference image generation.

    Consolidates:
    1. Character portfolio look sheet generation (from world_config)
    2. Character reference from input image (analyze → profile → prompt → generate)
    3. Location directional views (N → E → S → W pipeline)
    4. Prop portfolio look sheets

    All pipelines enforce:
    - Seedream blank-first requirement (at ImageHandler level)
    - Style suffix from ContextEngine.get_world_style()
    - Output to references/{TAG}/ directory

    Usage:
        script = UnifiedReferenceScript(project_path)
        result = await script.generate_character_sheet("CHAR_MEI")
        batch = await script.generate_all_references()
    """
    
    def __init__(
        self,
        project_path: Path,
        context_engine: Optional["ContextEngine"] = None,
        callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ):
        """
        Initialize the unified reference script.
        
        Args:
            project_path: Path to project root
            context_engine: Optional ContextEngine (creates new if not provided)
            callback: Optional progress callback(event, data)
        """
        self.project_path = Path(project_path)
        self._callback = callback
        
        # Lazy-loaded components
        self._context_engine = context_engine
        self._image_handler = None
        self._prompt_builder = None
        self._profile_template_agent = None
        
        # Reference directory
        self._refs_dir = self.project_path / "references"
    
    # =========================================================================
    # LAZY INITIALIZATION
    # =========================================================================
    
    def _get_context_engine(self) -> "ContextEngine":
        """Get or create ContextEngine."""
        if self._context_engine is None:
            from greenlight.context.context_engine import ContextEngine
            self._context_engine = ContextEngine(self.project_path)
        return self._context_engine
    
    def _get_image_handler(self) -> "ImageHandler":
        """Get or create ImageHandler singleton."""
        if self._image_handler is None:
            from greenlight.core.image_handler import get_image_handler
            self._image_handler = get_image_handler(
                self.project_path, 
                self._get_context_engine()
            )
        return self._image_handler
    
    def _get_prompt_builder(self) -> "ReferencePromptBuilder":
        """Get or create ReferencePromptBuilder (template-based, no LLM)."""
        if self._prompt_builder is None:
            from greenlight.references.prompt_builder import ReferencePromptBuilder
            self._prompt_builder = ReferencePromptBuilder(
                context_engine=self._get_context_engine()
            )
        return self._prompt_builder
    
    def _emit(self, event: str, data: Dict[str, Any]) -> None:
        """Emit progress callback."""
        if self._callback:
            try:
                self._callback(event, data)
            except Exception as e:
                logger.warning(f"Callback error: {e}")

    # =========================================================================
    # SINGLE-TAG GENERATION METHODS
    # =========================================================================

    async def generate_character_sheet(
        self,
        tag: str,
        model: Optional["ImageModel"] = None,
        overwrite: bool = False
    ) -> ReferenceResult:
        """
        Generate character portfolio look sheet from world_config.json data.

        UI Button: "Generate Sheet" on character card
        Pipeline: world_config → ReferencePromptBuilder → ImageHandler
        Output: references/{TAG}/{TAG}_sheet.png

        Args:
            tag: Character tag (e.g., "CHAR_MEI")
            model: Image model to use (default: SEEDREAM)
            overwrite: Whether to overwrite existing sheet

        Returns:
            ReferenceResult with success status and image path
        """
        from greenlight.core.image_handler import ImageModel

        if model is None:
            model = ImageModel.SEEDREAM

        start_time = datetime.now()
        self._emit('start', {'pipeline': 'character_sheet', 'tag': tag})

        # Normalize tag
        tag = self._normalize_tag(tag)

        # Check for existing sheet
        output_path = self._get_output_path(tag, "sheet")
        if output_path.exists() and not overwrite:
            logger.info(f"Sheet already exists for {tag}, skipping (overwrite=False)")
            return ReferenceResult(
                success=True,
                reference_type=ReferenceType.CHARACTER_SHEET,
                tag=tag,
                image_paths=[output_path],
                error="Sheet already exists (skipped)"
            )

        # Get character data from ContextEngine
        context_engine = self._get_context_engine()
        char_data = context_engine.get_character_profile(tag)

        if not char_data:
            return ReferenceResult(
                success=False,
                reference_type=ReferenceType.CHARACTER_SHEET,
                tag=tag,
                error=f"Character {tag} not found in world_config.json"
            )

        # Build prompt via template (no LLM call)
        self._emit('generating_prompt', {'tag': tag})
        prompt_builder = self._get_prompt_builder()

        from greenlight.core.constants import TagCategory
        prompt_result = prompt_builder.build_character_prompt(tag, char_data)

        if not prompt_result.success:
            return ReferenceResult(
                success=False,
                reference_type=ReferenceType.CHARACTER_SHEET,
                tag=tag,
                error=f"Prompt generation failed: {prompt_result.error}"
            )

        # Generate character sheet via ImageHandler
        self._emit('generating_image', {'tag': tag})
        handler = self._get_image_handler()
        name = char_data.get('name', tag.replace('CHAR_', '').replace('_', ' ').title())

        result = await handler.generate_character_sheet(
            tag=tag,
            name=name,
            model=model,
            custom_prompt=prompt_result.reference_sheet_prompt,
            character_data=char_data
        )

        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        self._emit('complete', {'tag': tag, 'success': result.success})

        return ReferenceResult(
            success=result.success,
            reference_type=ReferenceType.CHARACTER_SHEET,
            tag=tag,
            image_paths=[result.image_path] if result.image_path else [],
            generation_time_ms=elapsed_ms,
            error=result.error
        )

    async def generate_character_from_image(
        self,
        tag: str,
        image_path: Path,
        model: Optional["ImageModel"] = None,
        update_profile: bool = True
    ) -> ReferenceResult:
        """
        Generate character reference from an input image.

        UI Button: "Generate from Image" on character card
        Pipeline: Image Analysis → ProfileTemplateAgent → ReferencePromptBuilder → ImageHandler
        Output: references/{TAG}/{TAG}_sheet.png + world_config.json update

        Args:
            tag: Character tag (e.g., "CHAR_MEI")
            image_path: Path to input image
            model: Image model to use (default: SEEDREAM)
            update_profile: Whether to update world_config.json with analyzed profile

        Returns:
            ReferenceResult with success status, image path, and profile_updated flag
        """
        from greenlight.core.image_handler import ImageModel

        if model is None:
            model = ImageModel.SEEDREAM

        start_time = datetime.now()
        image_path = Path(image_path)

        self._emit('start', {'pipeline': 'character_from_image', 'tag': tag, 'image': str(image_path)})

        # Normalize tag
        tag = self._normalize_tag(tag)

        if not image_path.exists():
            return ReferenceResult(
                success=False,
                reference_type=ReferenceType.CHARACTER_FROM_IMAGE,
                tag=tag,
                error=f"Input image not found: {image_path}"
            )

        # Stage 1: Image Analysis with Gemini 2.5
        self._emit('analyzing_image', {'tag': tag, 'image': str(image_path)})

        try:
            from greenlight.omni_mind.autonomous_agent import AutonomousTaskManager
            manager = AutonomousTaskManager(project_path=self.project_path)
            analysis = await manager.analyze_image(image_path, analysis_type="character")

            if not analysis.success:
                return ReferenceResult(
                    success=False,
                    reference_type=ReferenceType.CHARACTER_FROM_IMAGE,
                    tag=tag,
                    error=f"Image analysis failed: {analysis.error}"
                )
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return ReferenceResult(
                success=False,
                reference_type=ReferenceType.CHARACTER_FROM_IMAGE,
                tag=tag,
                error=f"Image analysis error: {e}"
            )

        # Stage 2: Profile Template Generation → world_config.json
        profile_updated = False
        if update_profile:
            self._emit('generating_profile', {'tag': tag})
            try:
                from greenlight.agents.profile_template_agent import ProfileTemplateAgent
                profile_agent = ProfileTemplateAgent(context_engine=self._get_context_engine())
                profile = await profile_agent.generate_character_profile(tag, analysis)
                profile_updated = await profile_agent.update_world_config(
                    tag=tag,
                    profile=profile,
                    project_path=self.project_path
                )
            except ImportError:
                logger.warning("ProfileTemplateAgent not available, skipping profile update")
            except Exception as e:
                logger.warning(f"Profile update failed: {e}")

        # Stage 3: Generate Prompt from Analysis
        self._emit('generating_prompt', {'tag': tag})
        context_engine = self._get_context_engine()
        # NOTE: Do NOT use world_style for portfolio look sheets - they use neutral studio lighting

        # Get updated character data (may have been updated by profile agent)
        char_data = context_engine.get_character_profile(tag) or {}

        # Use template-based prompt builder (no LLM call)
        prompt_builder = self._get_prompt_builder()
        prompt_result = prompt_builder.build_character_prompt(tag, char_data)

        if not prompt_result.success:
            # Fallback to basic neutral prompt (no mood/story elements)
            prompt = f"Multi-angle portfolio look sheet for {tag}. Multiple views showing front, side, back, and 3/4 angles. Consistent appearance across all views. Clean white background. Professional studio lighting with soft, even illumination. Neutral expression."
        else:
            prompt = prompt_result.reference_sheet_prompt

        # Stage 4: Generate Portfolio Look Sheet with Input Image
        self._emit('generating_image', {'tag': tag})
        handler = self._get_image_handler()
        name = char_data.get('name', tag.replace('CHAR_', '').replace('_', ' ').title())

        result = await handler.generate_character_sheet(
            tag=tag,
            name=name,
            model=model,
            custom_prompt=prompt,
            character_data=char_data,
            source_image=image_path  # Use the clicked image as reference
        )

        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        self._emit('complete', {'tag': tag, 'success': result.success, 'profile_updated': profile_updated})

        return ReferenceResult(
            success=result.success,
            reference_type=ReferenceType.CHARACTER_FROM_IMAGE,
            tag=tag,
            image_paths=[result.image_path] if result.image_path else [],
            profile_updated=profile_updated,
            generation_time_ms=elapsed_ms,
            error=result.error
        )

    async def generate_location_views(
        self,
        tag: str,
        model: Optional["ImageModel"] = None,
        overwrite: bool = False
    ) -> ReferenceResult:
        """
        Generate all cardinal direction views for a location.

        UI Button: "Generate Views" on location card
        Pipeline: ReferencePromptBuilder (N/E/S/W) → ImageHandler (chained)
        Output: references/{TAG}/{TAG}_north.png, _east.png, _south.png, _west.png

        Args:
            tag: Location tag (e.g., "LOC_PALACE")
            model: Image model to use (default: SEEDREAM)
            overwrite: Whether to overwrite existing views

        Returns:
            ReferenceResult with success status and list of image paths
        """
        from greenlight.core.image_handler import ImageModel

        if model is None:
            model = ImageModel.SEEDREAM

        start_time = datetime.now()
        self._emit('start', {'pipeline': 'location_views', 'tag': tag})

        # Normalize tag
        tag = self._normalize_tag(tag)

        # Get location data from ContextEngine
        context_engine = self._get_context_engine()
        loc_data = context_engine.get_location_profile(tag)

        if not loc_data:
            loc_data = {'name': tag.replace('LOC_', '').replace('_', ' ').title()}

        name = loc_data.get('name', tag.replace('LOC_', '').replace('_', ' ').title())

        # Build directional prompts via template (no LLM call)
        self._emit('generating_prompts', {'tag': tag})
        prompt_builder = self._get_prompt_builder()
        prompt_result = prompt_builder.build_location_prompts(tag, loc_data)

        if not prompt_result.success:
            return ReferenceResult(
                success=False,
                reference_type=ReferenceType.LOCATION_VIEWS,
                tag=tag,
                error=f"Prompt generation failed: {prompt_result.error}"
            )

        # Generate views via ImageHandler (handles N→E→S→W chaining internally)
        self._emit('generating_images', {'tag': tag, 'count': 4})
        handler = self._get_image_handler()

        results = await handler.generate_location_views(
            tag=tag,
            name=name,
            directional_views=prompt_result.reference_prompts,
            model=model,
            location_data=loc_data
        )

        image_paths = [r.image_path for r in results if r.success and r.image_path]
        success = len(image_paths) == 4

        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        self._emit('complete', {'tag': tag, 'success': success, 'views': len(image_paths)})

        return ReferenceResult(
            success=success,
            reference_type=ReferenceType.LOCATION_VIEWS,
            tag=tag,
            image_paths=image_paths,
            generation_time_ms=elapsed_ms,
            error=None if success else f"Only {len(image_paths)}/4 views generated"
        )

    async def generate_prop_sheet(
        self,
        tag: str,
        model: Optional["ImageModel"] = None,
        overwrite: bool = False
    ) -> ReferenceResult:
        """
        Generate prop portfolio look sheet from world_config.json data.

        UI Button: "Generate Sheet" on prop card
        Pipeline: world_config → ReferencePromptBuilder → ImageHandler
        Output: references/{TAG}/{TAG}_sheet.png

        Args:
            tag: Prop tag (e.g., "PROP_SWORD")
            model: Image model to use (default: SEEDREAM)
            overwrite: Whether to overwrite existing sheet

        Returns:
            ReferenceResult with success status and image path
        """
        from greenlight.core.image_handler import ImageModel

        if model is None:
            model = ImageModel.SEEDREAM

        start_time = datetime.now()
        self._emit('start', {'pipeline': 'prop_sheet', 'tag': tag})

        # Normalize tag
        tag = self._normalize_tag(tag)

        # Check for existing sheet
        output_path = self._get_output_path(tag, "sheet")
        if output_path.exists() and not overwrite:
            logger.info(f"Sheet already exists for {tag}, skipping (overwrite=False)")
            return ReferenceResult(
                success=True,
                reference_type=ReferenceType.PROP_SHEET,
                tag=tag,
                image_paths=[output_path],
                error="Sheet already exists (skipped)"
            )

        # Get prop data from ContextEngine
        context_engine = self._get_context_engine()
        prop_data = context_engine.get_prop_profile(tag)

        if not prop_data:
            prop_data = {'name': tag.replace('PROP_', '').replace('_', ' ').title()}

        # Build prompt via template (no LLM call)
        self._emit('generating_prompt', {'tag': tag})
        prompt_builder = self._get_prompt_builder()
        prompt_result = prompt_builder.build_prop_prompt(tag, prop_data)

        if not prompt_result.success:
            return ReferenceResult(
                success=False,
                reference_type=ReferenceType.PROP_SHEET,
                tag=tag,
                error=f"Prompt generation failed: {prompt_result.error}"
            )

        # Generate prop sheet via ImageHandler
        self._emit('generating_image', {'tag': tag})
        handler = self._get_image_handler()
        name = prop_data.get('name', tag.replace('PROP_', '').replace('_', ' ').title())

        result = await handler.generate_prop_reference(
            tag=tag,
            name=name,
            prop_data=prop_data,
            model=model,
            custom_prompt=prompt_result.reference_sheet_prompt
        )

        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        self._emit('complete', {'tag': tag, 'success': result.success})

        return ReferenceResult(
            success=result.success,
            reference_type=ReferenceType.PROP_SHEET,
            tag=tag,
            image_paths=[result.image_path] if result.image_path else [],
            generation_time_ms=elapsed_ms,
            error=result.error
        )

    # =========================================================================
    # BATCH GENERATION METHODS
    # =========================================================================

    async def generate_all_character_sheets(
        self,
        model: Optional["ImageModel"] = None,
        overwrite: bool = False
    ) -> BatchResult:
        """
        Generate character sheets for all characters in world_config.json.

        UI Button: "Generate All Characters"

        Args:
            model: Image model to use (default: SEEDREAM)
            overwrite: Whether to overwrite existing sheets

        Returns:
            BatchResult with success counts and individual results
        """
        context_engine = self._get_context_engine()
        characters = context_engine.get_all_characters()

        if not characters:
            return BatchResult(success=True, total=0, completed=0, failed=0)

        results = []
        completed = 0
        failed = 0
        skipped = 0
        errors = {}

        self._emit('batch_start', {'type': 'character_sheets', 'total': len(characters)})

        for tag in characters.keys():
            result = await self.generate_character_sheet(tag, model=model, overwrite=overwrite)
            results.append(result)

            if result.success:
                if result.error and "skipped" in result.error.lower():
                    skipped += 1
                else:
                    completed += 1
            else:
                failed += 1
                errors[tag] = result.error or "Unknown error"

            self._emit('batch_progress', {'completed': completed + skipped, 'failed': failed, 'total': len(characters)})

        self._emit('batch_complete', {'completed': completed, 'failed': failed, 'skipped': skipped})

        return BatchResult(
            success=failed == 0,
            total=len(characters),
            completed=completed,
            failed=failed,
            skipped=skipped,
            results=results,
            errors=errors
        )

    async def generate_all_location_views(
        self,
        model: Optional["ImageModel"] = None,
        overwrite: bool = False
    ) -> BatchResult:
        """
        Generate directional views for all locations in world_config.json.

        UI Button: "Generate All Locations"

        Args:
            model: Image model to use (default: SEEDREAM)
            overwrite: Whether to overwrite existing views

        Returns:
            BatchResult with success counts and individual results
        """
        context_engine = self._get_context_engine()
        locations = context_engine.get_all_locations()

        if not locations:
            return BatchResult(success=True, total=0, completed=0, failed=0)

        results = []
        completed = 0
        failed = 0
        errors = {}

        self._emit('batch_start', {'type': 'location_views', 'total': len(locations)})

        for tag in locations.keys():
            result = await self.generate_location_views(tag, model=model, overwrite=overwrite)
            results.append(result)

            if result.success:
                completed += 1
            else:
                failed += 1
                errors[tag] = result.error or "Unknown error"

            self._emit('batch_progress', {'completed': completed, 'failed': failed, 'total': len(locations)})

        self._emit('batch_complete', {'completed': completed, 'failed': failed})

        return BatchResult(
            success=failed == 0,
            total=len(locations),
            completed=completed,
            failed=failed,
            results=results,
            errors=errors
        )

    async def generate_all_prop_sheets(
        self,
        model: Optional["ImageModel"] = None,
        overwrite: bool = False
    ) -> BatchResult:
        """
        Generate prop sheets for all props in world_config.json.

        UI Button: "Generate All Props"

        Args:
            model: Image model to use (default: SEEDREAM)
            overwrite: Whether to overwrite existing sheets

        Returns:
            BatchResult with success counts and individual results
        """
        context_engine = self._get_context_engine()
        props = context_engine.get_all_props()

        if not props:
            return BatchResult(success=True, total=0, completed=0, failed=0)

        results = []
        completed = 0
        failed = 0
        skipped = 0
        errors = {}

        self._emit('batch_start', {'type': 'prop_sheets', 'total': len(props)})

        for tag in props.keys():
            result = await self.generate_prop_sheet(tag, model=model, overwrite=overwrite)
            results.append(result)

            if result.success:
                if result.error and "skipped" in result.error.lower():
                    skipped += 1
                else:
                    completed += 1
            else:
                failed += 1
                errors[tag] = result.error or "Unknown error"

            self._emit('batch_progress', {'completed': completed + skipped, 'failed': failed, 'total': len(props)})

        self._emit('batch_complete', {'completed': completed, 'failed': failed, 'skipped': skipped})

        return BatchResult(
            success=failed == 0,
            total=len(props),
            completed=completed,
            failed=failed,
            skipped=skipped,
            results=results,
            errors=errors
        )

    async def generate_all_references(
        self,
        model: Optional["ImageModel"] = None,
        overwrite: bool = False
    ) -> BatchResult:
        """
        Generate all reference images (characters + locations + props).

        UI Button: "Generate All" (main button)

        Args:
            model: Image model to use (default: SEEDREAM)
            overwrite: Whether to overwrite existing references

        Returns:
            BatchResult with combined success counts
        """
        self._emit('batch_start', {'type': 'all_references'})

        # Run all batch operations
        char_result = await self.generate_all_character_sheets(model=model, overwrite=overwrite)
        loc_result = await self.generate_all_location_views(model=model, overwrite=overwrite)
        prop_result = await self.generate_all_prop_sheets(model=model, overwrite=overwrite)

        # Combine results
        total = char_result.total + loc_result.total + prop_result.total
        completed = char_result.completed + loc_result.completed + prop_result.completed
        failed = char_result.failed + loc_result.failed + prop_result.failed
        skipped = char_result.skipped + loc_result.skipped + prop_result.skipped

        all_results = char_result.results + loc_result.results + prop_result.results
        all_errors = {**char_result.errors, **loc_result.errors, **prop_result.errors}

        self._emit('batch_complete', {'completed': completed, 'failed': failed, 'skipped': skipped, 'total': total})

        return BatchResult(
            success=failed == 0,
            total=total,
            completed=completed,
            failed=failed,
            skipped=skipped,
            results=all_results,
            errors=all_errors
        )

    # =========================================================================
    # CONVERSION METHODS
    # =========================================================================

    async def convert_image_to_sheet(
        self,
        tag: str,
        image_path: Path,
        model: Optional["ImageModel"] = None
    ) -> ReferenceResult:
        """
        Convert any image to a reference sheet.

        UI Button: "Convert to Sheet" on uploaded image
        Pipeline: Same as generate_character_from_image but for any entity type

        Args:
            tag: Entity tag (CHAR_*, LOC_*, PROP_*)
            image_path: Path to input image
            model: Image model to use (default: SEEDREAM)

        Returns:
            ReferenceResult with success status and image path
        """
        # Determine entity type from tag prefix
        if tag.startswith("CHAR_"):
            return await self.generate_character_from_image(tag, image_path, model=model)
        elif tag.startswith("LOC_"):
            # For locations, we generate views from the analyzed image
            return await self.generate_location_views(tag, model=model, overwrite=True)
        elif tag.startswith("PROP_"):
            return await self.generate_prop_sheet(tag, model=model, overwrite=True)
        else:
            return ReferenceResult(
                success=False,
                reference_type=ReferenceType.CHARACTER_SHEET,
                tag=tag,
                error=f"Unknown tag prefix: {tag}"
            )

    async def convert_reference_to_sheet(
        self,
        tag: str,
        model: Optional["ImageModel"] = None
    ) -> ReferenceResult:
        """
        Convert existing key reference to a reference sheet.

        UI Button: "Generate Sheet" on key reference
        Pipeline: Find key reference → analyze → generate sheet

        Args:
            tag: Entity tag (CHAR_*, LOC_*, PROP_*)
            model: Image model to use (default: SEEDREAM)

        Returns:
            ReferenceResult with success status and image path
        """
        # Find key reference image
        tag = self._normalize_tag(tag)
        ref_dir = self._refs_dir / tag

        if not ref_dir.exists():
            return ReferenceResult(
                success=False,
                reference_type=ReferenceType.CHARACTER_SHEET,
                tag=tag,
                error=f"No reference directory found for {tag}"
            )

        # Look for key reference (starred image)
        key_ref = None
        for img_file in ref_dir.glob("*.png"):
            if "_key" in img_file.stem or "key_" in img_file.stem:
                key_ref = img_file
                break

        # Fallback to first image if no key reference
        if key_ref is None:
            images = list(ref_dir.glob("*.png"))
            if images:
                key_ref = images[0]

        if key_ref is None:
            return ReferenceResult(
                success=False,
                reference_type=ReferenceType.CHARACTER_SHEET,
                tag=tag,
                error=f"No reference images found for {tag}"
            )

        # Use convert_image_to_sheet with the key reference
        return await self.convert_image_to_sheet(tag, key_ref, model=model)

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def get_reference_status(self, tag: str) -> ReferenceStatus:
        """
        Get reference status for a single tag.

        UI Usage: Card status indicator

        Args:
            tag: Entity tag (CHAR_*, LOC_*, PROP_*)

        Returns:
            ReferenceStatus with has_sheet, has_views, has_key_reference, image_count
        """
        tag = self._normalize_tag(tag)
        ref_dir = self._refs_dir / tag

        # Determine entity type
        if tag.startswith("CHAR_"):
            entity_type = "character"
        elif tag.startswith("LOC_"):
            entity_type = "location"
        elif tag.startswith("PROP_"):
            entity_type = "prop"
        else:
            entity_type = "unknown"

        if not ref_dir.exists():
            return ReferenceStatus(tag=tag, entity_type=entity_type)

        images = list(ref_dir.glob("*.png"))

        # Check for sheet
        has_sheet = any("_sheet" in img.stem for img in images)

        # Check for directional views (locations only)
        has_views = all(
            any(f"_{direction}" in img.stem for img in images)
            for direction in ["north", "east", "south", "west"]
        )

        # Check for key reference
        has_key_reference = any("_key" in img.stem or "key_" in img.stem for img in images)

        # Get last updated time
        last_updated = None
        if images:
            last_updated = max(datetime.fromtimestamp(img.stat().st_mtime) for img in images)

        return ReferenceStatus(
            tag=tag,
            entity_type=entity_type,
            has_sheet=has_sheet,
            has_views=has_views,
            has_key_reference=has_key_reference,
            image_count=len(images),
            last_updated=last_updated
        )

    def get_all_reference_status(self) -> Dict[str, ReferenceStatus]:
        """
        Get reference status for all tags.

        UI Usage: Panel header stats

        Returns:
            Dict mapping tag to ReferenceStatus
        """
        context_engine = self._get_context_engine()

        all_tags = []
        all_tags.extend(context_engine.get_all_characters().keys())
        all_tags.extend(context_engine.get_all_locations().keys())
        all_tags.extend(context_engine.get_all_props().keys())

        return {tag: self.get_reference_status(tag) for tag in all_tags}

    def list_missing_references(self) -> Dict[str, List[str]]:
        """
        List tags that are missing references.

        UI Usage: "Missing" filter

        Returns:
            Dict with keys 'characters', 'locations', 'props' containing lists of tags
        """
        all_status = self.get_all_reference_status()

        missing = {
            'characters': [],
            'locations': [],
            'props': []
        }

        for tag, status in all_status.items():
            if status.entity_type == "character" and not status.has_sheet:
                missing['characters'].append(tag)
            elif status.entity_type == "location" and not status.has_views:
                missing['locations'].append(tag)
            elif status.entity_type == "prop" and not status.has_sheet:
                missing['props'].append(tag)

        return missing

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _normalize_tag(self, tag: str) -> str:
        """Normalize tag format (uppercase, no brackets)."""
        tag = tag.strip().upper()
        if tag.startswith("[") and tag.endswith("]"):
            tag = tag[1:-1]
        return tag

    def _get_output_path(self, tag: str, suffix: str) -> Path:
        """Get output path for a reference image."""
        ref_dir = self._refs_dir / tag
        ref_dir.mkdir(parents=True, exist_ok=True)
        return ref_dir / f"{tag}_{suffix}.png"
