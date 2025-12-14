"""
Image Handler - Centralized Image Generation Handler

Provides unified interface for all image generation requests across Project Greenlight.
Supports all models from API Dictionary:

Google/Gemini:
- Nano Banana (Gemini 2.5 Flash Image) - Basic quality, fast
- Nano Banana Pro (Gemini 3 Pro Image) - Best quality
- Imagen 3 - High-fidelity text-to-image

Replicate:
- Seedream 4.5 (ByteDance) - Cheap, fast, quality
- FLUX Kontext Pro - Context-aware editing
- FLUX Kontext Max - Highest quality FLUX
- FLUX 1.1 Pro - Flagship text-to-image
- SDXL - Stable Diffusion XL

Stability AI:
- SD 3.5 - Latest Stable Diffusion
- SDXL Turbo - Fast generation

OpenAI:
- DALL-E 3 - OpenAI image generation

Features:
- Reference image management with key reference selection
- Character/Prop multiview sheet generation
- Location cardinal view generation
- Labeled frame generation for AI reference
"""

from __future__ import annotations

import base64
import json
import os
import io
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable, TYPE_CHECKING

# Ensure environment variables are loaded before any API clients are instantiated
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from greenlight.core.logging_config import get_logger

if TYPE_CHECKING:
    from greenlight.context.context_engine import ContextEngine

logger = get_logger("core.image_handler")


class ImageModel(Enum):
    """Available image generation models."""
    # Google/Gemini
    NANO_BANANA = "nano_banana"           # Gemini 2.5 Flash Image - Basic
    NANO_BANANA_PRO = "nano_banana_pro"   # Gemini 3 Pro Image - Best quality
    IMAGEN_3 = "imagen_3"                 # Google Imagen 3

    # Replicate
    SEEDREAM = "seedream"                 # ByteDance Seedream 4.5 - Cheap/Fast
    FLUX_KONTEXT_PRO = "flux_kontext_pro" # FLUX Kontext Pro - Context-aware
    FLUX_KONTEXT_MAX = "flux_kontext_max" # FLUX Kontext Max - Highest quality
    FLUX_1_1_PRO = "flux_1_1_pro"         # FLUX 1.1 Pro - Flagship
    SDXL = "sdxl"                         # Stable Diffusion XL on Replicate

    # Stability AI
    SD_3_5 = "sd_3_5"                     # Stable Diffusion 3.5
    SDXL_TURBO = "sdxl_turbo"             # SDXL Turbo - Fast

    # OpenAI
    DALLE_3 = "dalle_3"                   # DALL-E 3


# =============================================================================
# PROMPT TEMPLATE DEFINITIONS
# These are the canonical template prefixes for all image generation.
# All image generation pathways MUST use these templates via prefix_type.
# =============================================================================

# EDIT: For editing existing images while preserving subject identity
PROMPT_TEMPLATE_EDIT = (
    "Edit image maintaining its qualities and subject identity while precisely "
    "making these changes:"
)

# CREATE: For creating new images from reference images (storyboard frames, scenes)
PROMPT_TEMPLATE_CREATE = (
    "Create a new image inspired by the reference images, maintain subject identity "
    "and original structure while dynamically manipulating them to be immersed into "
    "the scene with each subject being imported into the scene by reference of their "
    "unique name or tag as their source of design TRUTH, create this image:"
)

# RE-ANGLE: For recreating images from different camera angles
PROMPT_TEMPLATE_REANGLE = (
    "Recreate this image while preserving the identity and structure of the subjects "
    "position and pose and spatial relation in the scene. You are to use the reference "
    "image sheets to dynamically obtain different angle data of the subject per subject "
    "most matching reference image called and activated by their unique name and tag in "
    "the prompt. Recreate this scene from a new angle following these instructions:"
)

# RECREATE: For regenerating images with modifications (character references, regeneration)
PROMPT_TEMPLATE_RECREATE = (
    "Recreate this image with the alterations described by the prompt's request. "
    "Rules to follow: maintain subject identity and original structure while dynamically "
    "manipulating them to be immersed into the scene with each subject being imported "
    "into the scene by reference of their unique name or tag as their source of design "
    "TRUTH. The prompt is:"
)

# Legacy aliases for backward compatibility (deprecated - use new names)
PROMPT_PREFIX_CHARACTER = PROMPT_TEMPLATE_CREATE
PROMPT_PREFIX_EDIT = PROMPT_TEMPLATE_EDIT
PROMPT_PREFIX_GENERATE = PROMPT_TEMPLATE_CREATE

# Suffix to prevent unwanted elements and inject style
PROMPT_SUFFIX_CLEAN = " --no labels, no tags, no subtitles, no dialogue, no multi-frame, no text overlays, single frame only"


@dataclass
class ImageRequest:
    """Image generation request."""
    prompt: str
    model: ImageModel = ImageModel.NANO_BANANA_PRO
    aspect_ratio: str = "16:9"
    size: str = "2K"
    reference_images: List[Path] = field(default_factory=list)
    output_path: Optional[Path] = None
    tag: Optional[str] = None
    style_suffix: Optional[str] = None  # World bible style to append
    prefix_type: str = "generate"  # "character", "edit", "generate", or "none"
    add_clean_suffix: bool = True  # Add --no labels suffix
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageResult:
    """Image generation result."""
    success: bool
    image_path: Optional[Path] = None
    image_data: Optional[bytes] = None
    model_used: str = ""
    error: Optional[str] = None
    generation_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ImageHandler:
    """
    Centralized handler for all image generation requests.
    
    Usage:
        handler = ImageHandler(project_path)
        result = await handler.generate(ImageRequest(
            prompt="A beautiful landscape",
            model=ImageModel.NANO_BANANA_PRO,
            aspect_ratio="16:9"
        ))
    """
    
    _instance: Optional["ImageHandler"] = None

    def __init__(
        self,
        project_path: Optional[Path] = None,
        context_engine: Optional["ContextEngine"] = None
    ):
        """
        Initialize the ImageHandler.

        Args:
            project_path: Path to the project directory
            context_engine: Optional ContextEngine for retrieving profile data and world context
        """
        self.project_path = Path(project_path) if project_path else None
        self._context_engine = context_engine
        self._clients: Dict[str, Any] = {}
        self._callbacks: List[Callable] = []
        self._generation_count = 0
        self._generation_total = 0
        self._world_context_cache: Optional[str] = None
        logger.info("ImageHandler initialized")

    @classmethod
    def get_instance(
        cls,
        project_path: Optional[Path] = None,
        context_engine: Optional["ContextEngine"] = None
    ) -> "ImageHandler":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(project_path, context_engine)
        else:
            if project_path:
                cls._instance.project_path = Path(project_path)
            if context_engine:
                cls._instance.set_context_engine(context_engine)
        return cls._instance

    def set_project(self, project_path: Path) -> None:
        """Set the current project path."""
        self.project_path = Path(project_path)
        self._world_context_cache = None  # Clear cache when project changes

    def set_context_engine(self, context_engine: "ContextEngine") -> None:
        """Set or update the ContextEngine instance."""
        self._context_engine = context_engine
        self._world_context_cache = None  # Clear cache when engine changes

    def _get_world_context(self) -> str:
        """Get world context from ContextEngine, with caching."""
        if self._context_engine is None:
            return ""
        if self._world_context_cache is None:
            self._world_context_cache = self._context_engine.get_world_context_for_tag_generation()
        return self._world_context_cache

    def register_callback(self, callback: Callable) -> None:
        """Register a callback for generation events.

        Callback signature: callback(event_type: str, data: dict)
        Event types: 'generating', 'complete', 'error', 'batch_start', 'batch_end'
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            logger.debug(f"Registered image generation callback: {callback}")

    def unregister_callback(self, callback: Callable) -> None:
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self, event_type: str, data: dict) -> None:
        """Notify all registered callbacks of an event."""
        for callback in self._callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.warning(f"Callback error: {e}")

    def get_style_suffix(self) -> str:
        """Get the style suffix from the project's Style Core settings.

        Single source of truth: Reads ONLY from world_config.json.
        Builds a comprehensive style suffix for visual consistency across all generated images.

        Style suffix format:
            [visual_style_mapped]. [style_notes]. Lighting: [lighting]. Mood: [vibe]

        Returns:
            Style suffix string to append to image prompts.
        """
        if not self.project_path:
            return ""

        # Single source of truth: world_config.json
        world_config_path = self.project_path / "world_bible" / "world_config.json"
        if not world_config_path.exists():
            return ""

        try:
            world_config = json.loads(world_config_path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.warning(f"Error reading world_config.json: {e}")
            return ""

        style_parts = []

        # 1. Visual style - map to descriptive text
        visual_style = world_config.get('visual_style', '')
        if visual_style:
            style_map = {
                'live_action': 'live action, photorealistic cinematography, 8k quality, dynamic lighting, real life subjects, photographic, practical effects, natural skin texture, realistic materials, film grain, shallow depth of field, RAW photo, DSLR quality',
                'anime': 'anime style, cel-shaded, vibrant colors, expressive characters, bold linework, stylized proportions, clean vector art, high contrast colors, dynamic action lines',
                'animation_2d': 'hand-drawn 2D animation, traditional animation aesthetic, painted backgrounds, fluid motion, artistic linework, watercolor textures, gouache painting, illustrated',
                'animation_3d': '3D CGI rendering, subsurface scattering, global illumination, volumetric lighting, high-poly models, realistic textures, ray tracing, cinematic 3D animation',
                'mixed_reality': 'mixed reality, seamless blend of live action and CGI, photorealistic integration, matched lighting, HDR compositing, practical and digital fusion, photoreal CGI characters'
            }
            mapped_style = style_map.get(visual_style, visual_style)
            style_parts.append(mapped_style)

        # 2. Style notes - custom user description
        style_notes = world_config.get('style_notes', '')
        if style_notes and style_notes.strip():
            style_parts.append(style_notes.strip())

        # 3. Lighting
        lighting = world_config.get('lighting', '')
        if lighting and lighting.strip():
            style_parts.append(f"Lighting: {lighting.strip()}")

        # 4. Vibe/Mood
        vibe = world_config.get('vibe', '')
        if vibe and vibe.strip():
            style_parts.append(f"Mood: {vibe.strip()}")

        if style_parts:
            return ". ".join(style_parts)
        return ""

    def _build_prompt(self, request: ImageRequest) -> str:
        """Build final prompt with template prefix and suffix.

        Prompt Hierarchy (Mandatory Order):
            [TEMPLATE_PREFIX] + [STYLE_SUFFIX] + [DESCRIPTION] + [CLEAN_SUFFIX]

        Template Types:
        - "create": For creating new images from references (storyboard frames, scenes)
        - "edit": For editing existing images while preserving identity
        - "reangle": For recreating images from different camera angles
        - "recreate": For regenerating images with modifications (character references)
        - "character": Legacy alias for "create" (deprecated)
        - "generate": Legacy alias for "create" (deprecated)
        - "none": No prefix, use prompt as-is

        Suffix:
        - style_suffix: World bible style to maintain consistency
        - clean_suffix: Removes labels, tags, multi-frame artifacts
        """
        parts = []

        # Add template prefix based on type
        if request.prefix_type == "create":
            parts.append(PROMPT_TEMPLATE_CREATE)
        elif request.prefix_type == "edit":
            parts.append(PROMPT_TEMPLATE_EDIT)
        elif request.prefix_type == "reangle":
            parts.append(PROMPT_TEMPLATE_REANGLE)
        elif request.prefix_type == "recreate":
            parts.append(PROMPT_TEMPLATE_RECREATE)
        # Legacy aliases (deprecated - for backward compatibility)
        elif request.prefix_type == "character":
            parts.append(PROMPT_TEMPLATE_CREATE)
        elif request.prefix_type == "generate":
            parts.append(PROMPT_TEMPLATE_CREATE)
        # "none" adds no prefix

        # Add style suffix BEFORE the main prompt content (per hierarchy)
        if request.style_suffix:
            parts.append(f" Style: {request.style_suffix}.")

        # Add main prompt/description
        parts.append(f" {request.prompt}")

        # Add clean suffix to prevent artifacts
        if request.add_clean_suffix:
            parts.append(PROMPT_SUFFIX_CLEAN)

        return "".join(parts)

    def _get_references_dir(self) -> Path:
        """Get the references directory for current project.

        Uses REFERENCES_DIR constant from greenlight.core.constants.
        Reference images are organized by tag: references/{TAG}/
        """
        if not self.project_path:
            raise ValueError("No project path set")
        from greenlight.core.constants import REFERENCES_DIR
        refs_dir = self.project_path / REFERENCES_DIR
        refs_dir.mkdir(exist_ok=True)
        return refs_dir
    
    def _get_output_dir(self) -> Path:
        """Get the output directory for generated images."""
        if not self.project_path:
            raise ValueError("No project path set")
        output_dir = self.project_path / "storyboard_output" / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def _create_empty_image(self, width: int = 1920, height: int = 1080) -> bytes:
        """Create an empty image for Seedream input requirement."""
        try:
            from PIL import Image
            img = Image.new('RGB', (width, height), color=(255, 255, 255))
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()
        except ImportError:
            # Minimal PNG without PIL
            return self._create_minimal_png(width, height)
    
    def _create_minimal_png(self, width: int, height: int) -> bytes:
        """Create minimal white PNG without PIL."""
        import struct
        import zlib
        
        def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
            chunk_len = struct.pack('>I', len(data))
            chunk_crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
            return chunk_len + chunk_type + data + chunk_crc
        
        signature = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        ihdr = png_chunk(b'IHDR', ihdr_data)
        
        # White scanlines
        raw_data = b''
        for _ in range(height):
            raw_data += b'\x00' + b'\xff' * (width * 3)
        
        idat = png_chunk(b'IDAT', zlib.compress(raw_data))
        iend = png_chunk(b'IEND', b'')
        
        return signature + ihdr + idat + iend

    def _encode_image(self, image_path: Path) -> Tuple[str, str]:
        """Encode image to base64 with mime type."""
        suffix = image_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp"
        }
        mime_type = mime_types.get(suffix, "image/jpeg")
        data_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return data_b64, mime_type

    async def generate(self, request: ImageRequest) -> ImageResult:
        """Generate an image based on the request.

        Automatically applies the project's Style Core suffix if not provided.
        Notifies registered callbacks of generation events.
        """
        import time
        start_time = time.time()

        # Auto-apply style suffix from project if not provided
        if request.style_suffix is None and self.project_path:
            request.style_suffix = self.get_style_suffix()

        # Notify callbacks of generation start
        tag = request.tag or "image"
        model_name = request.model.value if request.model else "unknown"
        self._generation_count += 1
        self._notify_callbacks('generating', {
            'tag': tag,
            'model': model_name,
            'index': self._generation_count,
            'total': self._generation_total or self._generation_count
        })

        try:
            # Route to appropriate backend based on model
            if request.model == ImageModel.NANO_BANANA:
                result = await self._generate_gemini(request, pro=False)
            elif request.model == ImageModel.NANO_BANANA_PRO:
                result = await self._generate_gemini(request, pro=True)
            elif request.model == ImageModel.IMAGEN_3:
                result = await self._generate_imagen(request)
            elif request.model == ImageModel.SEEDREAM:
                result = await self._generate_seedream(request)
            elif request.model in (ImageModel.FLUX_KONTEXT_PRO, ImageModel.FLUX_KONTEXT_MAX,
                                   ImageModel.FLUX_1_1_PRO, ImageModel.SDXL):
                result = await self._generate_replicate(request)
            elif request.model in (ImageModel.SD_3_5, ImageModel.SDXL_TURBO):
                result = await self._generate_stability(request)
            elif request.model == ImageModel.DALLE_3:
                result = await self._generate_dalle(request)
            else:
                self._notify_callbacks('error', {
                    'tag': tag,
                    'error': f"Unknown model: {request.model}",
                    'index': self._generation_count,
                    'total': self._generation_total or self._generation_count
                })
                return ImageResult(success=False, error=f"Unknown model: {request.model}")

            result.generation_time_ms = int((time.time() - start_time) * 1000)

            # Notify callbacks of completion
            if result.success:
                self._notify_callbacks('complete', {
                    'tag': tag,
                    'file_path': str(result.image_path) if result.image_path else None,
                    'index': self._generation_count,
                    'total': self._generation_total or self._generation_count,
                    'time_ms': result.generation_time_ms
                })
            else:
                self._notify_callbacks('error', {
                    'tag': tag,
                    'error': result.error or "Unknown error",
                    'index': self._generation_count,
                    'total': self._generation_total or self._generation_count
                })

            return result

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            self._notify_callbacks('error', {
                'tag': tag,
                'error': str(e),
                'index': self._generation_count,
                'total': self._generation_total or self._generation_count
            })
            return ImageResult(
                success=False,
                error=str(e),
                generation_time_ms=int((time.time() - start_time) * 1000)
            )

    def start_batch(self, total: int) -> None:
        """Start a batch of image generations."""
        self._generation_count = 0
        self._generation_total = total
        self._notify_callbacks('batch_start', {'total': total})

    def end_batch(self) -> None:
        """End a batch of image generations."""
        self._notify_callbacks('batch_end', {
            'completed': self._generation_count,
            'total': self._generation_total
        })
        self._generation_count = 0
        self._generation_total = 0

    async def _generate_seedream(self, request: ImageRequest) -> ImageResult:
        """Generate image using Seedream 4.5."""
        from greenlight.llm.api_clients import ReplicateClient

        client = ReplicateClient()

        # Build final prompt with prefix/suffix
        final_prompt = self._build_prompt(request)

        # Prepare reference images
        ref_images = []

        # ALWAYS insert blank 16:9 2K as FIRST image - this is mandatory
        # Seedream uses "match_input_image" which inherits aspect ratio from first image
        # Using 2560x1440 (2K 16:9) ensures consistent output aspect ratio
        empty_img = self._create_empty_image(2560, 1440)
        ref_images.append({
            "data": base64.b64encode(empty_img).decode("ascii"),
            "mime_type": "image/png"
        })

        # Then add any reference images AFTER the blank template
        if request.reference_images:
            for img_path in request.reference_images:
                if img_path.exists():
                    data_b64, mime_type = self._encode_image(img_path)
                    ref_images.append({"data": data_b64, "mime_type": mime_type})

        response = client.generate_image(
            prompt=final_prompt,
            ref_images=ref_images,
            aspect_ratio=request.aspect_ratio
        )

        if response.images:
            image_data, _ = response.images[0]
            output_path = self._save_image(image_data, request)
            return ImageResult(
                success=True,
                image_path=output_path,
                image_data=image_data,
                model_used="Seedream 4.5"
            )

        return ImageResult(success=False, error="No images returned", model_used="Seedream 4.5")

    async def _generate_gemini(self, request: ImageRequest, pro: bool = False) -> ImageResult:
        """Generate image using Gemini (Nano Banana)."""
        from greenlight.llm.api_clients import GeminiClient
        import json
        from urllib import request as url_request

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return ImageResult(success=False, error="GOOGLE_API_KEY not set")

        # Correct model names as of Dec 2025 (verified via ListModels API)
        # - gemini-2.5-flash-image-preview: Nano Banana (basic)
        # - gemini-3-pro-image-preview: Nano Banana Pro (best quality)
        model = "gemini-3-pro-image-preview" if pro else "gemini-2.5-flash-image-preview"
        model_name = "Nano Banana Pro" if pro else "Nano Banana"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        # Build final prompt with prefix/suffix
        final_prompt = self._build_prompt(request)

        # Build request body
        parts = [{"text": final_prompt}]

        # Add reference images if provided
        for img_path in request.reference_images:
            if img_path.exists():
                data_b64, mime_type = self._encode_image(img_path)
                parts.append({"inline_data": {"mime_type": mime_type, "data": data_b64}})

        # Build generation config with image settings
        # imageConfig must be nested inside generationConfig
        image_config = {"aspectRatio": request.aspect_ratio}
        if request.size == "2K" and pro:
            image_config["imageSize"] = "2K"
        elif request.size == "4K" and pro:
            image_config["imageSize"] = "4K"

        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "imageConfig": image_config
            }
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        req = url_request.Request(url, data=json.dumps(body).encode(), headers=headers)

        try:
            with url_request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
        except Exception as e:
            return ImageResult(success=False, error=str(e), model_used=model_name)

        # Extract image from response
        candidates = result.get("candidates", [])
        if candidates:
            for part in candidates[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    image_b64 = part["inlineData"]["data"]
                    image_data = base64.b64decode(image_b64)
                    output_path = self._save_image(image_data, request)
                    return ImageResult(
                        success=True,
                        image_path=output_path,
                        image_data=image_data,
                        model_used=model_name
                    )

        return ImageResult(success=False, error="No image in response", model_used=model_name)

    async def _generate_imagen(self, request: ImageRequest) -> ImageResult:
        """Generate image using Google Imagen 3."""
        from urllib import request as url_request

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return ImageResult(success=False, error="GOOGLE_API_KEY not set")

        model = "imagen-3.0-generate-001"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateImages"

        # Build final prompt with prefix/suffix
        final_prompt = self._build_prompt(request)

        body = {
            "prompt": final_prompt,
            "numberOfImages": 1,
            "aspectRatio": request.aspect_ratio.replace(":", "_"),
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        req = url_request.Request(url, data=json.dumps(body).encode(), headers=headers)

        try:
            with url_request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
        except Exception as e:
            return ImageResult(success=False, error=str(e), model_used="Imagen 3")

        # Extract image from response
        images = result.get("generatedImages", [])
        if images:
            image_b64 = images[0].get("image", {}).get("imageBytes", "")
            if image_b64:
                image_data = base64.b64decode(image_b64)
                output_path = self._save_image(image_data, request)
                return ImageResult(success=True, image_path=output_path, image_data=image_data, model_used="Imagen 3")

        return ImageResult(success=False, error="No image in response", model_used="Imagen 3")

    async def _generate_replicate(self, request: ImageRequest) -> ImageResult:
        """Generate image using Replicate models (FLUX, SDXL)."""
        from greenlight.llm.api_clients import ReplicateClient

        client = ReplicateClient()

        # Map model enum to Replicate model ID
        model_map = {
            ImageModel.FLUX_KONTEXT_PRO: ("black-forest-labs/flux-kontext-pro", "FLUX Kontext Pro"),
            ImageModel.FLUX_KONTEXT_MAX: ("black-forest-labs/flux-kontext-max", "FLUX Kontext Max"),
            ImageModel.FLUX_1_1_PRO: ("black-forest-labs/flux-1.1-pro", "FLUX 1.1 Pro"),
            ImageModel.SDXL: ("stability-ai/sdxl", "SDXL"),
        }

        model_id, model_name = model_map.get(request.model, ("stability-ai/sdxl", "SDXL"))

        # Build final prompt with prefix/suffix
        final_prompt = self._build_prompt(request)

        # Build input parameters
        input_params = {
            "prompt": final_prompt,
            "aspect_ratio": request.aspect_ratio,
        }

        # Add reference image for Kontext models
        if request.model in (ImageModel.FLUX_KONTEXT_PRO, ImageModel.FLUX_KONTEXT_MAX):
            if request.reference_images:
                ref_path = request.reference_images[0]
                if ref_path.exists():
                    data_b64, _ = self._encode_image(ref_path)
                    input_params["image"] = f"data:image/png;base64,{data_b64}"

        try:
            result = await client.generate_image(model_id, input_params)

            if result.get("output"):
                output_url = result["output"]
                if isinstance(output_url, list):
                    output_url = output_url[0]

                # Download the image
                import urllib.request
                with urllib.request.urlopen(output_url) as resp:
                    image_data = resp.read()

                output_path = self._save_image(image_data, request)
                return ImageResult(success=True, image_path=output_path, image_data=image_data, model_used=model_name)

            return ImageResult(success=False, error="No output from Replicate", model_used=model_name)

        except Exception as e:
            return ImageResult(success=False, error=str(e), model_used=model_name)

    async def _generate_stability(self, request: ImageRequest) -> ImageResult:
        """Generate image using Stability AI models."""
        from urllib import request as url_request

        api_key = os.getenv("STABILITY_API_KEY")
        if not api_key:
            return ImageResult(success=False, error="STABILITY_API_KEY not set")

        model_map = {
            ImageModel.SD_3_5: ("sd3.5-large", "SD 3.5"),
            ImageModel.SDXL_TURBO: ("sdxl-turbo", "SDXL Turbo"),
        }

        model_id, model_name = model_map.get(request.model, ("sd3.5-large", "SD 3.5"))

        url = "https://api.stability.ai/v2beta/stable-image/generate/core"

        # Parse aspect ratio to dimensions
        ar_map = {
            "16:9": (1920, 1080), "9:16": (1080, 1920),
            "1:1": (1024, 1024), "4:3": (1365, 1024), "3:4": (1024, 1365),
        }
        width, height = ar_map.get(request.aspect_ratio, (1920, 1080))

        # Build final prompt with prefix/suffix
        final_prompt = self._build_prompt(request)

        # Build multipart form data
        import uuid
        boundary = str(uuid.uuid4())

        body_parts = []
        body_parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="prompt"\r\n\r\n{final_prompt}')
        body_parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="output_format"\r\n\r\npng')
        body_parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="aspect_ratio"\r\n\r\n{request.aspect_ratio}')
        body_parts.append(f'--{boundary}--')

        body = '\r\n'.join(body_parts).encode()

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {api_key}",
            "Accept": "image/*"
        }

        req = url_request.Request(url, data=body, headers=headers)

        try:
            with url_request.urlopen(req, timeout=120) as resp:
                image_data = resp.read()

            output_path = self._save_image(image_data, request)
            return ImageResult(success=True, image_path=output_path, image_data=image_data, model_used=model_name)

        except Exception as e:
            return ImageResult(success=False, error=str(e), model_used=model_name)

    async def _generate_dalle(self, request: ImageRequest) -> ImageResult:
        """Generate image using OpenAI DALL-E 3."""
        from urllib import request as url_request

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return ImageResult(success=False, error="OPENAI_API_KEY not set")

        url = "https://api.openai.com/v1/images/generations"

        # Map aspect ratio to DALL-E size
        size_map = {
            "16:9": "1792x1024", "9:16": "1024x1792",
            "1:1": "1024x1024", "4:3": "1792x1024", "3:4": "1024x1792",
        }
        size = size_map.get(request.aspect_ratio, "1792x1024")

        # Build final prompt with prefix/suffix
        final_prompt = self._build_prompt(request)

        body = {
            "model": "dall-e-3",
            "prompt": final_prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json"
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        req = url_request.Request(url, data=json.dumps(body).encode(), headers=headers)

        try:
            with url_request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
        except Exception as e:
            return ImageResult(success=False, error=str(e), model_used="DALL-E 3")

        # Extract image from response
        data = result.get("data", [])
        if data:
            image_b64 = data[0].get("b64_json", "")
            if image_b64:
                image_data = base64.b64decode(image_b64)
                output_path = self._save_image(image_data, request)
                return ImageResult(success=True, image_path=output_path, image_data=image_data, model_used="DALL-E 3")

        return ImageResult(success=False, error="No image in response", model_used="DALL-E 3")

    def _save_image(self, image_data: bytes, request: ImageRequest) -> Path:
        """Save generated image to disk."""
        if request.output_path:
            output_path = request.output_path
        else:
            output_dir = self._get_output_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            tag_part = f"_{request.tag}" if request.tag else ""
            output_path = output_dir / f"gen{tag_part}_{timestamp}.png"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_data)
        logger.info(f"Saved generated image: {output_path}")
        return output_path

    # =========================================================================
    # Reference Image Management
    # =========================================================================

    def get_references_for_tag(self, tag: str) -> List[Path]:
        """Get all reference images for a tag from its subdirectory."""
        # Each tag has its own subdirectory: references/{TAG}/
        tag_dir = self._get_references_dir() / tag
        references = []

        if not tag_dir.exists():
            return references

        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
            # Get all images in the tag's directory
            for f in tag_dir.glob(f"*{ext}"):
                # Skip hidden files and marker files
                if not f.name.startswith('.') and f not in references:
                    references.append(f)

        return sorted(references)

    def get_key_reference(self, tag: str) -> Optional[Path]:
        """Get the key (starred) reference image for a tag."""
        # Key file stored in tag's subdirectory
        tag_dir = self._get_references_dir() / tag
        tag_dir.mkdir(parents=True, exist_ok=True)
        key_file = tag_dir / ".key"

        if key_file.exists():
            key_path = Path(key_file.read_text().strip())
            if key_path.exists():
                return key_path

        # Fall back to first reference
        refs = self.get_references_for_tag(tag)
        return refs[0] if refs else None

    def set_key_reference(self, tag: str, image_path: Path) -> None:
        """Set the key reference image for a tag."""
        # Key file stored in tag's subdirectory
        tag_dir = self._get_references_dir() / tag
        tag_dir.mkdir(parents=True, exist_ok=True)
        key_file = tag_dir / ".key"
        key_file.write_text(str(image_path))
        logger.info(f"Set key reference for {tag}: {image_path}")

    def get_references_for_tags(self, tags: List[str]) -> List[Path]:
        """Get key reference images for multiple tags.

        This is the primary method for collecting references for image generation.
        Returns the key reference for each tag that has one.

        Args:
            tags: List of tag names (e.g., ["CHAR_MEI", "LOC_TEAHOUSE"])

        Returns:
            List of Path objects to key reference images
        """
        references = []
        for tag in tags:
            key_ref = self.get_key_reference(tag)
            if key_ref and key_ref.exists():
                references.append(key_ref)
        return references

    def prepare_generation_context(
        self,
        tags: List[str],
        include_style: bool = True
    ) -> Tuple[List[Path], str]:
        """Prepare reference images and style suffix for image generation.

        This is the single-path method for preparing all context needed
        for image generation:

        Flow: Tags → Key References → Style Suffix

        Args:
            tags: List of tag names to get references for
            include_style: Whether to include style suffix from world bible

        Returns:
            Tuple of (reference_images, style_suffix)
        """
        # Get key references for all tags
        references = self.get_references_for_tags(tags)

        # Get style suffix if requested
        style_suffix = self.get_style_suffix() if include_style else ""

        return references, style_suffix

    # =========================================================================
    # Reference Image Preprocessing (adapted from Prometheus Director)
    # =========================================================================

    def create_labeled_image(
        self,
        image_path: Path,
        label: str,
        output_path: Path,
        display_name: Optional[str] = None
    ) -> bool:
        """Create a labeled version of the image with tag and name overlay.

        Creates a single-line label bar at the top of the image with:
        - Left-aligned: Tag in bracket notation (e.g., [CHAR_MEI])
        - Right-aligned: Display name (e.g., Mei)
        - Red background box with black text

        Args:
            image_path: Path to the source image
            label: Tag label text (e.g., "[CHAR_MEI]")
            output_path: Path to save the labeled image
            display_name: Optional display name for right-aligned text (e.g., "Mei")

        Returns:
            True if successful, False otherwise
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.warning("Pillow not installed, cannot create labeled image")
            return False

        try:
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)

            # Minimum 50px font size, scale up for larger images
            font_size = max(50, img.width // 20)
            font = None

            # Try to use a bold font, fall back to default
            for font_name in ["arialbd.ttf", "Arial Bold.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"]:
                try:
                    font = ImageFont.truetype(font_name, font_size)
                    break
                except Exception:
                    continue

            if font is None:
                font = ImageFont.load_default()

            # Calculate text sizes for both label and display name
            label_bbox = draw.textbbox((0, 0), label, font=font)
            label_width = label_bbox[2] - label_bbox[0]
            label_height = label_bbox[3] - label_bbox[1]

            # Calculate display name size if provided
            name_width = 0
            if display_name:
                name_bbox = draw.textbbox((0, 0), display_name, font=font)
                name_width = name_bbox[2] - name_bbox[0]

            # Padding and margin
            padding_h = max(20, font_size // 3)
            padding_v = max(15, font_size // 4)
            margin = max(10, img.width // 50)
            spacing = max(40, font_size)  # Space between tag and name

            # Calculate total box width for single-line layout
            if display_name:
                total_text_width = label_width + spacing + name_width
            else:
                total_text_width = label_width

            box_width = total_text_width + padding_h * 2
            box_height = label_height + padding_v * 2

            # Position: top of image, spanning needed width, centered or left-aligned
            box_x = margin
            box_y = margin

            # Draw red background rectangle
            draw.rectangle(
                [box_x, box_y, box_x + box_width, box_y + box_height],
                fill=(255, 0, 0)  # Red background
            )

            # Draw tag label (left-aligned)
            text_y = box_y + padding_v
            draw.text((box_x + padding_h, text_y), label, fill=(0, 0, 0), font=font)

            # Draw display name (right-aligned within box) if provided
            if display_name:
                name_x = box_x + box_width - padding_h - name_width
                draw.text((name_x, text_y), display_name, fill=(0, 0, 0), font=font)

            # Save
            img.save(output_path, quality=95)
            logger.debug(f"Created labeled image: {output_path}")
            return True

        except Exception as e:
            logger.warning(f"Failed to create labeled image: {e}")
            return False

    def create_mosaic(
        self,
        images: List[Path],
        output_path: Path,
        target_ratio: float = 16/9
    ) -> bool:
        """Create a mosaic from multiple images at the target aspect ratio.

        Arranges images in a grid optimized for 16:9 output. This allows
        multiple reference images to be sent as a single consolidated input.

        Args:
            images: List of image paths to combine
            output_path: Path to save the mosaic
            target_ratio: Target aspect ratio (default 16:9)

        Returns:
            True if successful, False otherwise
        """
        try:
            from PIL import Image
        except ImportError:
            logger.warning("Pillow not installed, cannot create mosaic")
            return False

        if not images:
            return False

        try:
            # Open all images
            imgs = [Image.open(p) for p in images]
            n = len(imgs)

            # Determine grid layout based on count and target ratio
            if n == 1:
                cols, rows = 1, 1
            elif n == 2:
                cols, rows = 2, 1
            elif n == 3:
                cols, rows = 3, 1
            elif n == 4:
                cols, rows = 2, 2
            elif n <= 6:
                cols, rows = 3, 2
            else:
                cols, rows = 4, 2

            # Calculate cell size - aim for 2K output (2730x1536 for 16:9)
            output_width = 2730
            output_height = int(output_width / target_ratio)
            cell_width = output_width // cols
            cell_height = output_height // rows

            # Create output canvas (white background)
            mosaic = Image.new('RGB', (output_width, output_height), (255, 255, 255))

            # Place each image
            for idx, img in enumerate(imgs):
                if idx >= cols * rows:
                    break

                row = idx // cols
                col = idx % cols

                # Resize image to fit cell while maintaining aspect ratio
                img_ratio = img.width / img.height
                cell_ratio = cell_width / cell_height

                if img_ratio > cell_ratio:
                    new_width = cell_width
                    new_height = int(cell_width / img_ratio)
                else:
                    new_height = cell_height
                    new_width = int(cell_height * img_ratio)

                img_resized = img.resize((new_width, new_height), Image.LANCZOS)

                # Center in cell
                x = col * cell_width + (cell_width - new_width) // 2
                y = row * cell_height + (cell_height - new_height) // 2

                mosaic.paste(img_resized, (x, y))

            # Save mosaic
            mosaic.save(output_path, quality=95)
            logger.debug(f"Created mosaic from {n} images: {output_path}")
            return True

        except Exception as e:
            logger.warning(f"Failed to create mosaic: {e}")
            return False

    def prepare_labeled_inputs(
        self,
        tag: str,
        input_images: List[Path],
        display_name: Optional[str] = None,
        max_inputs: int = 4
    ) -> Tuple[Optional[Path], List[Path]]:
        """Prepare labeled input images and create mosaic for character sheet generation.

        This preprocessing step:
        1. Labels each input image with the character tag and display name
        2. Creates a mosaic from the labeled images
        3. Returns the mosaic as the primary input

        Args:
            tag: Character tag (e.g., "CHAR_MEI")
            input_images: List of input reference images
            display_name: Optional display name for right-aligned label (e.g., "Mei")
            max_inputs: Maximum number of input images to use (default 4)

        Returns:
            Tuple of (mosaic_path, labeled_images) or (None, []) if failed
        """
        if not input_images:
            return None, []

        # Limit inputs
        input_images = input_images[:max_inputs]
        char_tag = f"[{tag}]"

        # Create labeled_inputs directory
        refs_dir = self._get_references_dir() / tag
        labeled_dir = refs_dir / "labeled_inputs"
        labeled_dir.mkdir(parents=True, exist_ok=True)

        # Check for existing labeled reference
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            labeled_ref = refs_dir / f"reference_labeled{ext}"
            if labeled_ref.exists():
                logger.info(f"Using existing labeled reference: {labeled_ref.name}")
                return labeled_ref, [labeled_ref]

        # Label each input image
        labeled_images = []
        for img_path in input_images:
            labeled_path = labeled_dir / f"{img_path.stem}_labeled{img_path.suffix}"

            if labeled_path.exists():
                logger.debug(f"Using cached labeled: {labeled_path.name}")
                labeled_images.append(labeled_path)
            else:
                logger.info(f"Labeling: {img_path.name}")
                if self.create_labeled_image(img_path, char_tag, labeled_path, display_name):
                    labeled_images.append(labeled_path)
                else:
                    # Fall back to original if labeling fails
                    labeled_images.append(img_path)

        if not labeled_images:
            return None, []

        # Create mosaic from labeled images
        mosaic_path = labeled_dir / f"{tag}_input_mosaic.png"

        # Check if mosaic is up-to-date
        if mosaic_path.exists():
            mosaic_mtime = mosaic_path.stat().st_mtime
            if not any(img.stat().st_mtime > mosaic_mtime for img in labeled_images):
                logger.debug(f"Using cached mosaic: {mosaic_path.name}")
                return mosaic_path, labeled_images

        logger.info(f"Creating mosaic from {len(labeled_images)} images...")
        if self.create_mosaic(labeled_images, mosaic_path):
            return mosaic_path, labeled_images

        # Fall back to first labeled image if mosaic fails
        return labeled_images[0] if labeled_images else None, labeled_images

    # =========================================================================
    # Character/Prop Sheet Generation
    # =========================================================================

    def get_character_sheet_prompt(
        self,
        tag: str,
        name: str,
        template_instruction: str = "",
        character_data: Optional[Dict[str, Any]] = None,
        num_reference_images: int = 1
    ) -> str:
        """Get the prompt for generating a character/prop multiview sheet.

        Adapted from Prometheus Director's proven prompt structure with:
        - Figure references for input images
        - Detailed layout specifications
        - Fidelity requirements

        Args:
            tag: Character tag (e.g., CHAR_MEI)
            name: Character display name
            template_instruction: Additional template instructions
            character_data: Optional dict with expanded character profile fields
            num_reference_images: Number of reference images being provided (for figure refs)
        """
        # Try to get character data from ContextEngine if not provided
        if character_data is None and self._context_engine is not None:
            character_data = self._context_engine.get_character_profile(tag)

        # Get world context for period-accurate generation
        world_context = self._get_world_context()

        # Build figure references for input images (Prometheus Director style)
        if num_reference_images > 1:
            figure_refs = ", ".join([f"image {i+1}" for i in range(num_reference_images)])
        else:
            figure_refs = "the reference image"

        # Build style context section from world context
        style_context = ""
        if world_context:
            style_context = f"""
WORLD STYLE CONTEXT:
{world_context}
Ensure the reference sheet reflects this visual style and aesthetic."""

        # Build character description section if data provided
        char_description = ""
        if character_data:
            desc_parts = []

            # Try new expanded schema first (identity section)
            identity = character_data.get("identity", {})
            if identity:
                if identity.get("age"):
                    desc_parts.append(f"Age: {identity['age']}")
                if identity.get("ethnicity"):
                    desc_parts.append(f"Ethnicity: {identity['ethnicity']}")
                if identity.get("social_class"):
                    desc_parts.append(f"Social Class: {identity['social_class']}")

            # Try new expanded schema (visual section)
            visual = character_data.get("visual", {})
            if visual:
                if visual.get("appearance"):
                    desc_parts.append(f"Appearance: {visual['appearance']}")
                if visual.get("costume_default"):
                    desc_parts.append(f"Default Costume: {visual['costume_default']}")
                if visual.get("distinguishing_marks"):
                    desc_parts.append(f"Distinguishing Marks: {visual['distinguishing_marks']}")
                if visual.get("movement_style"):
                    desc_parts.append(f"Movement Style: {visual['movement_style']}")

            # Fallback to legacy fields if new schema not present
            if not identity and not visual:
                if character_data.get("age"):
                    desc_parts.append(f"Age: {character_data['age']}")
                if character_data.get("ethnicity"):
                    desc_parts.append(f"Ethnicity: {character_data['ethnicity']}")
                if character_data.get("appearance") or character_data.get("visual_appearance"):
                    appearance = character_data.get("appearance") or character_data.get("visual_appearance", "")
                    desc_parts.append(f"Appearance: {appearance}")
                if not desc_parts and character_data.get("description"):
                    desc_parts.append(f"Appearance: {character_data['description']}")
                if character_data.get("costume"):
                    desc_parts.append(f"Costume: {character_data['costume']}")
                if character_data.get("physicality"):
                    desc_parts.append(f"Physicality/Movement: {character_data['physicality']}")
                if character_data.get("emotional_tells"):
                    tells = character_data.get("emotional_tells", {})
                    if isinstance(tells, dict) and tells:
                        tells_str = ", ".join([f"{k}: {v}" for k, v in tells.items()])
                        desc_parts.append(f"Emotional Tells: {tells_str}")

            if desc_parts:
                char_description = "\n" + "\n".join(f"- {p}" for p in desc_parts)

        # Prometheus Director style prompt with figure references
        return f"""Create a detailed professional REFERENCE SHEET for the subject "{name}".
{style_context}
REFERENCE SUBJECT:
Study the subject shown in {figure_refs} carefully. This is [{tag}].{char_description}

You must maintain EXACT fidelity to this subject's:
- Face structure, facial features, and expressions
- Body proportions, build, and posture
- Hair style, color, and texture
- Skin tone and complexion
- Clothing design, colors, and details
- Any accessories, props, or distinguishing features
- Overall art style and rendering quality

LAYOUT: Two rows in a 16:9 sheet

TOP ROW - HEAD/FACE ROTATION (6 frames, 1:1 square ratio each):
Arrange 6 close-up head shots in a horizontal row showing full head rotation:
1. FRONT - Face looking directly at camera
2. 3/4 LEFT - Face turned 45 degrees to the left
3. PROFILE LEFT - Face in full left profile (90 degrees)
4. BACK - Back of head view
5. PROFILE RIGHT - Face in full right profile (90 degrees)
6. 3/4 RIGHT - Face turned 45 degrees to the right

BOTTOM ROW - FULL BODY ROTATION (5 frames, 2:5 tall ratio each):
Arrange 5 full body shots (head to feet) in a horizontal row showing full body rotation:
1. FRONT - Full body facing camera, neutral standing pose
2. 3/4 LEFT - Full body at 45 degree angle to the left
3. BACK - Full body from behind
4. 3/4 RIGHT - Full body at 45 degree angle to the right
5. PROFILE - Full body side view (left or right profile)

LABELING REQUIREMENTS:
- Add a clear label "[{tag}]" prominently at the top of the sheet
- Include the subject name "{name}" as a title
- Label each frame with its view angle (FRONT, 3/4 LEFT, PROFILE, BACK, etc.)
{template_instruction}
STYLE REQUIREMENTS:
- Clean white or light neutral background
- Maximum detail
- Subject must be IDENTICAL across all views - same identity, same outfit, same structure, same style
- Stay TRUE to the reference subject's identity - do not alter or reimagine
- All frames should have consistent scale and positioning"""

    async def generate_character_sheet(
        self,
        tag: str,
        name: str,
        model: ImageModel = ImageModel.NANO_BANANA_PRO,
        template_instruction: str = "",
        character_data: Optional[Dict[str, Any]] = None,
        use_preprocessing: bool = True
    ) -> ImageResult:
        """Generate a multiview character/prop sheet.

        Adapted from Prometheus Director's proven workflow:
        1. Collect all reference images for the tag (up to 4)
        2. Label each image with the character tag
        3. Create a mosaic from labeled images
        4. Generate the character sheet using the mosaic + prompt

        Args:
            tag: Character tag (e.g., CHAR_MEI)
            name: Character display name
            model: Image generation model to use
            template_instruction: Additional template instructions
            character_data: Optional dict with age, ethnicity, appearance, costume fields
            use_preprocessing: Whether to use labeled input preprocessing (default True)
        """
        refs_dir = self._get_references_dir() / tag
        refs_dir.mkdir(parents=True, exist_ok=True)

        # Collect all reference images for this tag
        all_refs = self.get_references_for_tag(tag)
        reference_images: List[Path] = []
        num_reference_images = 0

        if use_preprocessing and all_refs:
            # Use Prometheus Director style preprocessing with display name
            mosaic_path, labeled_images = self.prepare_labeled_inputs(tag, all_refs, display_name=name)
            if mosaic_path:
                reference_images = [mosaic_path]
                num_reference_images = len(labeled_images)
                logger.info(f"Using preprocessed mosaic with {num_reference_images} labeled images")
            else:
                # Fall back to key reference
                key_ref = self.get_key_reference(tag)
                if key_ref:
                    reference_images = [key_ref]
                    num_reference_images = 1
        else:
            # Use single key reference (legacy behavior)
            key_ref = self.get_key_reference(tag)
            if key_ref:
                reference_images = [key_ref]
                num_reference_images = 1

        # Build prompt with figure references
        prompt = self.get_character_sheet_prompt(
            tag, name, template_instruction, character_data,
            num_reference_images=num_reference_images
        )

        # Get style suffix from Context Engine (single source of truth)
        style_suffix = ""
        if self._context_engine:
            style_suffix = self._context_engine.get_world_style()
        if not style_suffix:
            style_suffix = self.get_style_suffix()

        # Create output path in references directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = refs_dir / f"{tag}_sheet_{timestamp}.png"

        # For reference sheets, don't use prefix (Prometheus Director uses add_prefix=False)
        request = ImageRequest(
            prompt=prompt,
            model=model,
            aspect_ratio="16:9",
            reference_images=reference_images,
            tag=f"{tag}_sheet",
            output_path=output_path,
            prefix_type=None,  # No prefix for reference sheets (Prometheus Director style)
            style_suffix=style_suffix if style_suffix else None,
            add_clean_suffix=True
        )

        return await self.generate(request)

    # =========================================================================
    # Prop Reference Image Generation
    # =========================================================================

    def get_prop_reference_prompt(
        self,
        tag: str,
        name: str,
        prop_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Get prompt for generating a prop reference image.

        Args:
            tag: Prop tag (e.g., PROP_GO_BOARD)
            name: Prop display name
            prop_data: Optional dict with expanded prop profile fields:
                - physical: {materials, dimensions, condition, craftsmanship}
                - sensory: {visual, auditory, tactile}
                - significance: {narrative_function, symbolic_meaning, emotional_weight}
                - time_period_details: {historical_context, social_implications, cultural_weight}
                - associations: {primary_character, secondary_characters, location}
                - Legacy fields: appearance, significance, history
        """
        # Try to get prop data from ContextEngine if not provided
        if prop_data is None and self._context_engine is not None:
            prop_data = self._context_engine.get_prop_profile(tag)

        # Get world context for period-accurate generation
        world_context = self._get_world_context()

        prompt_parts = [f"[{tag}] - {name}", "Prop reference image."]

        # Inject world context for period-accurate generation
        if world_context:
            prompt_parts.append(f"\n{world_context}\n")

        if prop_data:
            # Physical details from expanded schema
            physical = prop_data.get("physical", {})
            if physical:
                if physical.get("materials"):
                    prompt_parts.append(f"Materials: {physical['materials']}")
                if physical.get("dimensions"):
                    prompt_parts.append(f"Dimensions: {physical['dimensions']}")
                if physical.get("condition"):
                    prompt_parts.append(f"Condition: {physical['condition']}")
                if physical.get("craftsmanship"):
                    prompt_parts.append(f"Craftsmanship: {physical['craftsmanship']}")

            # Sensory details (visual is most important)
            sensory = prop_data.get("sensory", {})
            if sensory and sensory.get("visual"):
                prompt_parts.append(f"Visual Details: {sensory['visual']}")

            # Time period context
            tp_details = prop_data.get("time_period_details", {})
            if tp_details:
                if tp_details.get("historical_context"):
                    prompt_parts.append(f"Historical Context: {tp_details['historical_context']}")

            # Associations for context
            associations = prop_data.get("associations", {})
            if associations:
                if associations.get("primary_character"):
                    prompt_parts.append(f"Associated with: [{associations['primary_character']}]")
                if associations.get("location"):
                    prompt_parts.append(f"Found at: [{associations['location']}]")

            # Fallback to legacy fields
            if not physical and not sensory:
                if prop_data.get("appearance"):
                    prompt_parts.append(f"Appearance: {prop_data['appearance']}")
                if prop_data.get("history"):
                    prompt_parts.append(f"History: {prop_data['history']}")

        prompt_parts.append("""
REQUIREMENTS:
- Clear product-shot style composition
- Neutral background to highlight the prop
- High detail on materials and textures
- Accurate to time period and cultural context
- 16:9 aspect ratio, 2K resolution""")

        return "\n".join(prompt_parts)

    async def generate_prop_reference(
        self,
        tag: str,
        name: str,
        prop_data: Optional[Dict[str, Any]] = None,
        model: ImageModel = ImageModel.NANO_BANANA_PRO
    ) -> ImageResult:
        """Generate a reference image for a prop.

        Uses PROMPT_TEMPLATE_RECREATE for prop reference generation.
        Style suffix is obtained from Context Engine's get_world_style() or
        falls back to get_style_suffix().

        Args:
            tag: Prop tag (e.g., PROP_GO_BOARD)
            name: Prop display name
            prop_data: Optional dict with expanded prop profile fields
            model: Image generation model to use
        """
        prompt = self.get_prop_reference_prompt(tag, name, prop_data)

        # Get style suffix from Context Engine (single source of truth)
        # Falls back to get_style_suffix() if Context Engine not available
        style_suffix = ""
        if self._context_engine:
            style_suffix = self._context_engine.get_world_style()
        if not style_suffix:
            style_suffix = self.get_style_suffix()

        # Create output path in references directory (not storyboard_output)
        refs_dir = self._get_references_dir() / tag
        refs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = refs_dir / f"{tag}_reference_{timestamp}.png"

        request = ImageRequest(
            prompt=prompt,
            model=model,
            aspect_ratio="16:9",
            tag=f"{tag}_reference",
            output_path=output_path,  # Save to references/{TAG}/ directory
            prefix_type="recreate",  # Use recreate template for prop references
            style_suffix=style_suffix if style_suffix else None,
            add_clean_suffix=True
        )

        return await self.generate(request)

    # =========================================================================
    # Location Cardinal View Generation
    # =========================================================================

    CARDINAL_DIRECTIONS = [
        {"name": "north", "angle": 0},
        {"name": "east", "angle": 90},
        {"name": "south", "angle": 180},
        {"name": "west", "angle": 270},
    ]

    def get_location_view_prompt(
        self,
        tag: str,
        name: str,
        direction: str,
        description: str = "",
        time_period: str = "",
        atmosphere: str = "",
        directional_view: str = "",
        location_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Get prompt for a location cardinal view.

        Args:
            tag: Location tag (e.g., LOC_FLOWER_SHOP)
            name: Location display name
            direction: Cardinal direction (north, east, south, west)
            description: Location description
            time_period: Historical time period
            atmosphere: Mood/atmosphere description
            directional_view: Direction-specific view description from world_config
            location_data: Optional dict with expanded location profile fields:
                - physical: {architecture, dimensions, materials, key_features}
                - sensory: {visual, auditory, olfactory, tactile}
                - atmosphere: {mood, lighting, emotional_quality, danger_level}
                - time_period_details: {era_specific_elements, social_function, ...}
        """
        # Try to get location data from ContextEngine if not provided
        if location_data is None and self._context_engine is not None:
            location_data = self._context_engine.get_location_profile(tag)

        # Get world context for period-accurate generation
        world_context = self._get_world_context()

        dir_info = next((d for d in self.CARDINAL_DIRECTIONS if d["name"] == direction.lower()), None)

        # Build prompt parts
        prompt_parts = [f"[{tag}] - {name}", f"Location view facing {direction.upper()}."]

        # Inject world context for period-accurate generation
        if world_context:
            prompt_parts.append(f"\n{world_context}\n")

        # Extract from expanded schema if available
        if location_data:
            # Physical details
            physical = location_data.get("physical", {})
            if physical:
                if physical.get("architecture"):
                    prompt_parts.append(f"Architecture: {physical['architecture']}")
                if physical.get("materials"):
                    prompt_parts.append(f"Materials: {physical['materials']}")
                if physical.get("key_features"):
                    features = physical['key_features']
                    if isinstance(features, list):
                        prompt_parts.append(f"Key Features: {', '.join(features)}")
                    else:
                        prompt_parts.append(f"Key Features: {features}")

            # Sensory details (visual is most important for image gen)
            sensory = location_data.get("sensory", {})
            if sensory and sensory.get("visual"):
                prompt_parts.append(f"Visual Details: {sensory['visual']}")

            # Atmosphere from expanded schema or legacy string
            atmos = location_data.get("atmosphere", {})
            if atmos:
                if isinstance(atmos, dict):
                    # New expanded schema format
                    if atmos.get("mood"):
                        prompt_parts.append(f"Mood: {atmos['mood']}")
                    if atmos.get("lighting"):
                        prompt_parts.append(f"Lighting: {atmos['lighting']}")
                    if atmos.get("emotional_quality"):
                        prompt_parts.append(f"Emotional Quality: {atmos['emotional_quality']}")
                elif isinstance(atmos, str):
                    # Legacy string format
                    prompt_parts.append(f"Atmosphere: {atmos}")

            # Time period details
            tp_details = location_data.get("time_period_details", {})
            if tp_details and tp_details.get("era_specific_elements"):
                elements = tp_details['era_specific_elements']
                if isinstance(elements, list):
                    prompt_parts.append(f"Era-Specific Elements: {', '.join(elements)}")
                else:
                    prompt_parts.append(f"Era-Specific Elements: {elements}")

        # Fallback to legacy fields
        if time_period:
            prompt_parts.append(f"Time Period: {time_period}")
        if description:
            prompt_parts.append(f"Description: {description}")
        if atmosphere and not location_data:  # Only use if no expanded schema
            prompt_parts.append(f"Atmosphere: {atmosphere}")
        if directional_view:
            prompt_parts.append(f"{direction.upper()} View: {directional_view}")

        prompt_parts.append("""
REQUIREMENTS:
- Same location, different camera direction
- Maintain consistent architecture, lighting, and atmosphere
- Camera now facing """ + direction.upper() + """
- Preserve all architectural details and environmental elements
- Consistent time of day and weather conditions
- 16:9 aspect ratio, 2K resolution""")

        return "\n".join(prompt_parts)

    async def generate_location_views(
        self,
        tag: str,
        name: str,
        description: str = "",
        time_period: str = "",
        atmosphere: str = "",
        directional_views: Optional[Dict[str, str]] = None,
        model: ImageModel = ImageModel.NANO_BANANA_PRO,
        location_data: Optional[Dict[str, Any]] = None
    ) -> List[ImageResult]:
        """Generate all cardinal views for a location, starting with North.

        Args:
            tag: Location tag (e.g., LOC_FLOWER_SHOP)
            name: Location display name
            description: Location description
            time_period: Historical time period
            atmosphere: Mood/atmosphere description
            directional_views: Dict with north/east/south/west view descriptions
            model: Image generation model to use
            location_data: Optional expanded location profile data

        Uses PROMPT_TEMPLATE_RECREATE for location view generation.
        Style suffix is obtained from Context Engine's get_world_style() or
        falls back to get_style_suffix().
        """
        results = []
        previous_image: Optional[Path] = None
        directional_views = directional_views or {}

        # Get style suffix from Context Engine (single source of truth)
        # Falls back to get_style_suffix() if Context Engine not available
        style_suffix = ""
        if self._context_engine:
            style_suffix = self._context_engine.get_world_style()
        if not style_suffix:
            style_suffix = self.get_style_suffix()

        for dir_info in self.CARDINAL_DIRECTIONS:
            direction = dir_info["name"]
            directional_view = directional_views.get(direction, "")
            prompt = self.get_location_view_prompt(
                tag, name, direction, description, time_period, atmosphere, directional_view,
                location_data=location_data
            )

            # Use previous image as reference for consistency
            ref_images = [previous_image] if previous_image else []

            request = ImageRequest(
                prompt=prompt,
                model=model,
                aspect_ratio="16:9",
                reference_images=ref_images,
                tag=f"{tag}_{direction}",
                prefix_type="recreate",  # Use recreate template for location views
                style_suffix=style_suffix if style_suffix else None,
                add_clean_suffix=True
            )

            result = await self.generate(request)
            results.append(result)

            if result.success and result.image_path:
                previous_image = result.image_path

            logger.info(f"Generated {direction} view for {tag}: {'success' if result.success else result.error}")

        return results

    # =========================================================================
    # Labeled Frame Generation
    # =========================================================================

    def create_labeled_reference(self, tag: str, name: str, image_path: Path) -> Optional[Path]:
        """Create a labeled reference image with tag and name overlay.

        OVERWRITES the original image with the labeled version.
        Label bar: 140px height, 60px bold font, centered text.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.warning("PIL not available for labeled reference creation")
            return None

        try:
            img = Image.open(image_path)

            # Convert to RGBA if needed for transparency
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Try to use a bold font at 60px, fall back to regular then default
            font = None
            font_size = 60
            for font_name in ["arialbd.ttf", "Arial Bold.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"]:
                try:
                    font = ImageFont.truetype(font_name, font_size)
                    break
                except:
                    continue
            if font is None:
                font = ImageFont.load_default()

            # Add label bar at top - sized for 60px font
            bar_height = 140
            label_bar = Image.new('RGBA', (img.width, bar_height), (0, 0, 0, 200))
            img.paste(label_bar, (0, 0), label_bar)

            # Draw tag and name centered in the bar
            draw = ImageDraw.Draw(img)
            label_text = f"[{tag}] {name}"

            # Get text dimensions for centering
            try:
                text_bbox = draw.textbbox((0, 0), label_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
            except:
                # Fallback for older PIL versions
                text_width = len(label_text) * 36  # Approximate for 60px font
                text_height = 60

            # Center text horizontally and vertically in the bar
            text_x = (img.width - text_width) // 2
            text_y = (bar_height - text_height) // 2

            # Draw centered text (gold/amber color for tag, white for name)
            # For simplicity, draw entire label in gold/amber
            draw.text((text_x, text_y), label_text, fill=(255, 200, 100), font=font)

            # Overwrite the original image with labeled version
            img.convert('RGB').save(image_path)

            logger.info(f"Labeled reference (overwritten): {image_path}")
            return image_path

        except Exception as e:
            logger.error(f"Failed to create labeled reference: {e}")
            return None

    def auto_label_references(self, tag: str, name: str) -> List[Path]:
        """Automatically label all unlabeled images in a tag's reference directory.

        Any image entering the directory gets labeled instantly (overwrites original).
        Uses a marker file to track which images have been labeled.
        Also labels cardinal direction subdirectories with directional tags.
        Returns list of newly labeled images.
        """
        refs_dir = self._get_references_dir() / tag
        if not refs_dir.exists():
            return []

        # Marker file tracks which images have been labeled
        marker_file = refs_dir / ".labeled"
        labeled_set = set()
        if marker_file.exists():
            labeled_set = set(marker_file.read_text().strip().split('\n'))

        created = []
        image_extensions = {'.png', '.jpg', '.jpeg', '.webp'}

        # Direction code to label mapping
        dir_labels = {
            '_dir_n': ('_DIR_N', 'North View'),
            '_dir_e': ('_DIR_E', 'East View'),
            '_dir_s': ('_DIR_S', 'South View'),
            '_dir_w': ('_DIR_W', 'West View'),
        }

        def label_image(img_file: Path, img_tag: str, img_name: str, relative_key: str):
            """Label a single image and track it."""
            if relative_key in labeled_set:
                return
            result = self.create_labeled_reference(img_tag, img_name, img_file)
            if result:
                created.append(result)
                labeled_set.add(relative_key)

        # Label top-level images
        for img_file in refs_dir.iterdir():
            if not img_file.is_file():
                continue
            if img_file.suffix.lower() not in image_extensions:
                continue
            if img_file.name.startswith('.'):
                continue

            label_image(img_file, tag, name, img_file.name)

        # Label cardinal direction subdirectories
        for subdir in refs_dir.iterdir():
            if not subdir.is_dir():
                continue
            if subdir.name.startswith('.'):
                continue

            for img_file in subdir.iterdir():
                if not img_file.is_file():
                    continue
                if img_file.suffix.lower() not in image_extensions:
                    continue
                if img_file.name.startswith('.'):
                    continue

                # Determine directional tag from filename
                fname_lower = img_file.stem.lower()
                dir_tag = tag
                dir_name = name

                for code, (suffix, view_name) in dir_labels.items():
                    if code in fname_lower:
                        dir_tag = f"{tag}{suffix}"
                        dir_name = f"{name} - {view_name}"
                        break

                # Use relative path as key to avoid collisions
                relative_key = f"{subdir.name}/{img_file.name}"
                label_image(img_file, dir_tag, dir_name, relative_key)

        # Update marker file
        if created:
            marker_file.write_text('\n'.join(sorted(labeled_set)))

        return created

    def get_labeled_reference(self, tag: str, name: str) -> Optional[Path]:
        """Get the key reference for a tag, auto-labeling if needed.

        This is the main method to get a reference image ready for AI use.
        All images are labeled in-place, so just returns the key reference.
        """
        # First, auto-label any new images
        self.auto_label_references(tag, name)

        # Get the key reference (already labeled)
        return self.get_key_reference(tag)


# Convenience function
def get_image_handler(
    project_path: Optional[Path] = None,
    context_engine: Optional["ContextEngine"] = None
) -> ImageHandler:
    """Get the ImageHandler singleton instance.

    Args:
        project_path: Path to the project directory
        context_engine: Optional ContextEngine for retrieving profile data and world context
    """
    return ImageHandler.get_instance(project_path, context_engine)

