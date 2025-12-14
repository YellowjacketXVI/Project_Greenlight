"""
API Dictionary - Comprehensive Index of AI Models and APIs

This module provides a centralized dictionary of all AI models, APIs,
and their nicknames/aliases used across Project Greenlight and Agnostic_Core_OS.

Key Terms:
- Nano Banana = Gemini 2.5 Flash Image (Google)
- Nano Banana Pro = Gemini 3 Pro Image (Google)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class APIProvider(Enum):
    """API Provider/Platform."""
    GOOGLE = "google"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    REPLICATE = "replicate"
    STABILITY = "stability"
    BLACK_FOREST = "black_forest_labs"
    XAI = "xai"
    MIDJOURNEY = "midjourney"


class ModelCapability(Enum):
    """Model capabilities."""
    TEXT_GENERATION = "text_generation"
    IMAGE_GENERATION = "image_generation"
    IMAGE_EDITING = "image_editing"
    IMAGE_UNDERSTANDING = "image_understanding"
    VIDEO_GENERATION = "video_generation"
    CODE_GENERATION = "code_generation"
    MULTIMODAL = "multimodal"
    EMBEDDING = "embedding"


@dataclass
class ModelEntry:
    """A model entry in the API dictionary."""
    model_id: str                          # Official API model ID
    display_name: str                      # Human-readable name
    nicknames: List[str]                   # Alternative names/aliases
    provider: APIProvider                  # API provider
    capabilities: List[ModelCapability]    # What it can do
    api_endpoint: str                      # API endpoint or base URL
    env_key: str                           # Environment variable for API key
    description: str                       # Brief description
    pricing_tier: str = "paid"             # free, paid, enterprise
    max_output_tokens: Optional[int] = None
    supports_streaming: bool = False
    supports_vision: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, query: str) -> bool:
        """Check if query matches this model."""
        query_lower = query.lower().replace(" ", "").replace("-", "").replace("_", "")
        checks = [
            self.model_id.lower().replace("-", "").replace("_", ""),
            self.display_name.lower().replace(" ", ""),
            *[n.lower().replace(" ", "").replace("-", "").replace("_", "") for n in self.nicknames]
        ]
        return any(query_lower in c or c in query_lower for c in checks)


# =============================================================================
# GOOGLE / GEMINI MODELS
# =============================================================================

GOOGLE_MODELS = {
    # Image Generation Models
    "nano_banana": ModelEntry(
        model_id="gemini-2.5-flash-image",
        display_name="Gemini 2.5 Flash Image",
        nicknames=["Nano Banana", "nano-banana", "gemini-flash-image"],
        provider=APIProvider.GOOGLE,
        capabilities=[ModelCapability.IMAGE_GENERATION, ModelCapability.IMAGE_EDITING, ModelCapability.MULTIMODAL],
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models",
        env_key="GOOGLE_API_KEY",
        description="Fast image generation model. Combines Gemini's understanding with generation. Nicknamed 'Nano Banana'.",
        pricing_tier="free_tier_available",
        supports_vision=True,
        metadata={"release_date": "2025", "speed": "fast"}
    ),
    "nano_banana_pro": ModelEntry(
        model_id="gemini-3-pro-image-preview",
        display_name="Gemini 3 Pro Image",
        nicknames=["Nano Banana Pro", "nano-banana-pro", "gemini-pro-image", "Google Image Pro"],
        provider=APIProvider.GOOGLE,
        capabilities=[ModelCapability.IMAGE_GENERATION, ModelCapability.IMAGE_EDITING, ModelCapability.MULTIMODAL],
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models",
        env_key="GOOGLE_API_KEY",
        description="Advanced image generation model. Most capable Google image model. Nicknamed 'Nano Banana Pro'.",
        pricing_tier="paid",
        supports_vision=True,
        metadata={"release_date": "2025", "quality": "highest"}
    ),
    "imagen_3": ModelEntry(
        model_id="imagen-3.0-generate-001",
        display_name="Imagen 3",
        nicknames=["imagen3", "google-imagen"],
        provider=APIProvider.GOOGLE,
        capabilities=[ModelCapability.IMAGE_GENERATION],
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models",
        env_key="GOOGLE_API_KEY",
        description="Google's high-fidelity text-to-image model.",
        pricing_tier="paid",
        metadata={"vertex_ai": True}
    ),
    "gemini_2_flash": ModelEntry(
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        nicknames=["gemini-flash", "flash"],
        provider=APIProvider.GOOGLE,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.MULTIMODAL, ModelCapability.CODE_GENERATION],
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models",
        env_key="GOOGLE_API_KEY",
        description="Fast, efficient Gemini model for text and multimodal tasks.",
        pricing_tier="free_tier_available",
        max_output_tokens=8192,
        supports_streaming=True,
        supports_vision=True
    ),
    "gemini_2_5_flash": ModelEntry(
        model_id="gemini-2.5-flash-preview-05-20",
        display_name="Gemini 2.5 Flash",
        nicknames=["gemini-2.5-flash", "flash-2.5"],
        provider=APIProvider.GOOGLE,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.MULTIMODAL, ModelCapability.CODE_GENERATION],
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models",
        env_key="GOOGLE_API_KEY",
        description="Latest Gemini Flash with improved reasoning.",
        pricing_tier="free_tier_available",
        max_output_tokens=65536,
        supports_streaming=True,
        supports_vision=True
    ),
    "gemini_3_pro": ModelEntry(
        model_id="gemini-3-pro-preview",
        display_name="Gemini 3 Pro",
        nicknames=["gemini-pro", "gemini3"],
        provider=APIProvider.GOOGLE,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.MULTIMODAL, ModelCapability.CODE_GENERATION],
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models",
        env_key="GOOGLE_API_KEY",
        description="Most capable Gemini model for complex tasks.",
        pricing_tier="paid",
        max_output_tokens=65536,
        supports_streaming=True,
        supports_vision=True
    ),
    "veo_3": ModelEntry(
        model_id="veo-3.0-generate-preview",
        display_name="Veo 3",
        nicknames=["veo", "google-video"],
        provider=APIProvider.GOOGLE,
        capabilities=[ModelCapability.VIDEO_GENERATION],
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models",
        env_key="GOOGLE_API_KEY",
        description="Google's video generation model.",
        pricing_tier="paid"
    ),
}

# =============================================================================
# ANTHROPIC / CLAUDE MODELS
# =============================================================================

ANTHROPIC_MODELS = {
    "claude_opus_4_5": ModelEntry(
        model_id="claude-sonnet-4-5-20250514",
        display_name="Claude Sonnet 4.5",
        nicknames=["claude-4.5", "sonnet-4.5", "claude-sonnet"],
        provider=APIProvider.ANTHROPIC,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.CODE_GENERATION, ModelCapability.MULTIMODAL],
        api_endpoint="https://api.anthropic.com/v1/messages",
        env_key="ANTHROPIC_API_KEY",
        description="Anthropic's most capable model. Best for agents, coding, and complex reasoning.",
        pricing_tier="paid",
        max_output_tokens=64000,
        supports_streaming=True,
        supports_vision=True
    ),
    "claude_haiku": ModelEntry(
        model_id="claude-3-5-haiku-20241022",
        display_name="Claude 3.5 Haiku",
        nicknames=["haiku", "claude-haiku", "haiku-3.5"],
        provider=APIProvider.ANTHROPIC,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.CODE_GENERATION],
        api_endpoint="https://api.anthropic.com/v1/messages",
        env_key="ANTHROPIC_API_KEY",
        description="Fast, cost-effective Claude model. Great for consensus voting.",
        pricing_tier="paid",
        max_output_tokens=8192,
        supports_streaming=True,
        supports_vision=True,
        metadata={"use_case": "consensus_voting", "cost": "low"}
    ),
}

# =============================================================================
# REPLICATE MODELS
# =============================================================================

REPLICATE_MODELS = {
    "seedream_4_5": ModelEntry(
        model_id="bytedance/seedream-4.5",
        display_name="Seedream 4.5",
        nicknames=["seedream", "bytedance-seedream"],
        provider=APIProvider.REPLICATE,
        capabilities=[ModelCapability.IMAGE_GENERATION],
        api_endpoint="https://api.replicate.com/v1/models",
        env_key="REPLICATE_API_TOKEN",
        description="ByteDance's image generation model. Good quality, fast.",
        pricing_tier="paid",
        metadata={"aspect_ratios": ["16:9", "1:1", "9:16", "4:3", "3:4"]}
    ),
    "flux_kontext_pro": ModelEntry(
        model_id="black-forest-labs/flux-kontext-pro",
        display_name="FLUX Kontext Pro",
        nicknames=["flux-kontext", "kontext-pro", "flux-pro"],
        provider=APIProvider.REPLICATE,
        capabilities=[ModelCapability.IMAGE_GENERATION, ModelCapability.IMAGE_EDITING],
        api_endpoint="https://api.replicate.com/v1/models",
        env_key="REPLICATE_API_TOKEN",
        description="Black Forest Labs' context-aware image editing. Fast iterative editing.",
        pricing_tier="paid",
        metadata={"in_context": True}
    ),
    "flux_kontext_max": ModelEntry(
        model_id="black-forest-labs/flux-kontext-max",
        display_name="FLUX Kontext Max",
        nicknames=["kontext-max", "flux-max"],
        provider=APIProvider.REPLICATE,
        capabilities=[ModelCapability.IMAGE_GENERATION, ModelCapability.IMAGE_EDITING],
        api_endpoint="https://api.replicate.com/v1/models",
        env_key="REPLICATE_API_TOKEN",
        description="Highest quality FLUX model for image editing.",
        pricing_tier="paid",
        metadata={"in_context": True, "quality": "highest"}
    ),
    "flux_1_1_pro": ModelEntry(
        model_id="black-forest-labs/flux-1.1-pro",
        display_name="FLUX 1.1 Pro",
        nicknames=["flux", "flux-pro", "flux-1.1"],
        provider=APIProvider.REPLICATE,
        capabilities=[ModelCapability.IMAGE_GENERATION],
        api_endpoint="https://api.replicate.com/v1/models",
        env_key="REPLICATE_API_TOKEN",
        description="Black Forest Labs' flagship text-to-image model.",
        pricing_tier="paid"
    ),
    "sdxl": ModelEntry(
        model_id="stability-ai/sdxl",
        display_name="Stable Diffusion XL",
        nicknames=["sdxl", "stable-diffusion-xl", "sd-xl"],
        provider=APIProvider.REPLICATE,
        capabilities=[ModelCapability.IMAGE_GENERATION],
        api_endpoint="https://api.replicate.com/v1/models",
        env_key="REPLICATE_API_TOKEN",
        description="Stability AI's SDXL on Replicate.",
        pricing_tier="paid"
    ),
}

# =============================================================================
# STABILITY AI MODELS
# =============================================================================

STABILITY_MODELS = {
    "sd3_5": ModelEntry(
        model_id="sd3.5-large",
        display_name="Stable Diffusion 3.5",
        nicknames=["sd3.5", "stable-diffusion-3.5", "sd-3.5"],
        provider=APIProvider.STABILITY,
        capabilities=[ModelCapability.IMAGE_GENERATION],
        api_endpoint="https://api.stability.ai/v2beta/stable-image/generate",
        env_key="STABILITY_API_KEY",
        description="Latest Stable Diffusion model from Stability AI.",
        pricing_tier="paid"
    ),
    "sdxl_turbo": ModelEntry(
        model_id="sdxl-turbo",
        display_name="SDXL Turbo",
        nicknames=["sdxl-turbo", "turbo"],
        provider=APIProvider.STABILITY,
        capabilities=[ModelCapability.IMAGE_GENERATION],
        api_endpoint="https://api.stability.ai/v2beta/stable-image/generate",
        env_key="STABILITY_API_KEY",
        description="Fast SDXL variant for quick generation.",
        pricing_tier="paid",
        metadata={"speed": "fast"}
    ),
}

# =============================================================================
# OPENAI MODELS
# =============================================================================

OPENAI_MODELS = {
    "gpt_4o": ModelEntry(
        model_id="gpt-4o",
        display_name="GPT-4o",
        nicknames=["gpt4o", "4o", "omni"],
        provider=APIProvider.OPENAI,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.MULTIMODAL, ModelCapability.CODE_GENERATION],
        api_endpoint="https://api.openai.com/v1/chat/completions",
        env_key="OPENAI_API_KEY",
        description="OpenAI's flagship multimodal model.",
        pricing_tier="paid",
        max_output_tokens=16384,
        supports_streaming=True,
        supports_vision=True
    ),
    "dall_e_3": ModelEntry(
        model_id="dall-e-3",
        display_name="DALL-E 3",
        nicknames=["dalle3", "dall-e", "dalle"],
        provider=APIProvider.OPENAI,
        capabilities=[ModelCapability.IMAGE_GENERATION],
        api_endpoint="https://api.openai.com/v1/images/generations",
        env_key="OPENAI_API_KEY",
        description="OpenAI's image generation model. Note: Deprecated in favor of newer models.",
        pricing_tier="paid",
        metadata={"status": "deprecated"}
    ),
}

# =============================================================================
# XAI / GROK MODELS
# =============================================================================

XAI_MODELS = {
    "grok_4": ModelEntry(
        model_id="grok-4",
        display_name="Grok 4",
        nicknames=["grok", "grok4", "xai-grok"],
        provider=APIProvider.XAI,
        capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.CODE_GENERATION],
        api_endpoint="https://api.x.ai/v1/chat/completions",
        env_key="XAI_API_KEY",
        description="xAI's most capable model.",
        pricing_tier="paid",
        supports_streaming=True
    ),
    "grok_3_fast": ModelEntry(
        model_id="grok-3-fast",
        display_name="Grok 3 Fast",
        nicknames=["grok-fast", "grok3-fast"],
        provider=APIProvider.XAI,
        capabilities=[ModelCapability.TEXT_GENERATION],
        api_endpoint="https://api.x.ai/v1/chat/completions",
        env_key="XAI_API_KEY",
        description="Fast Grok model for quick responses.",
        pricing_tier="paid",
        supports_streaming=True,
        metadata={"speed": "fast"}
    ),
}


# =============================================================================
# UNIFIED API DICTIONARY
# =============================================================================

ALL_MODELS: Dict[str, ModelEntry] = {
    **GOOGLE_MODELS,
    **ANTHROPIC_MODELS,
    **REPLICATE_MODELS,
    **STABILITY_MODELS,
    **OPENAI_MODELS,
    **XAI_MODELS,
}

# Quick lookup by nickname
NICKNAME_INDEX: Dict[str, str] = {}
for key, model in ALL_MODELS.items():
    NICKNAME_INDEX[model.model_id.lower()] = key
    NICKNAME_INDEX[model.display_name.lower()] = key
    for nick in model.nicknames:
        NICKNAME_INDEX[nick.lower().replace(" ", "").replace("-", "_")] = key


def lookup_model(query: str) -> Optional[ModelEntry]:
    """
    Look up a model by name, nickname, or model ID.

    Examples:
        lookup_model("nano banana") -> Gemini 2.5 Flash Image
        lookup_model("nano banana pro") -> Gemini 3 Pro Image
        lookup_model("seedream") -> Seedream 4.5
        lookup_model("flux kontext") -> FLUX Kontext Pro
    """
    query_normalized = query.lower().replace(" ", "").replace("-", "_")

    # Direct lookup
    if query_normalized in NICKNAME_INDEX:
        return ALL_MODELS[NICKNAME_INDEX[query_normalized]]

    # Fuzzy match
    for key, model in ALL_MODELS.items():
        if model.matches(query):
            return model

    return None


def get_image_models() -> Dict[str, ModelEntry]:
    """Get all models capable of image generation."""
    return {k: v for k, v in ALL_MODELS.items()
            if ModelCapability.IMAGE_GENERATION in v.capabilities}


# Recommended models for storyboard generation (subset of all image models)
STORYBOARD_MODELS = ["seedream_4_5", "nano_banana_pro", "flux_kontext_pro"]


def get_storyboard_models() -> Dict[str, ModelEntry]:
    """Get recommended models for storyboard generation.

    Returns a curated subset of image models that work well for storyboard generation:
    - Seedream 4.5: Fast, good quality, cost-effective (recommended)
    - Nano Banana Pro: High quality Gemini model
    - FLUX Kontext Pro: Context-aware, good for reference-based generation
    """
    all_image = get_image_models()
    return {k: v for k, v in all_image.items() if k in STORYBOARD_MODELS}


def get_text_models() -> Dict[str, ModelEntry]:
    """Get all models capable of text generation."""
    return {k: v for k, v in ALL_MODELS.items()
            if ModelCapability.TEXT_GENERATION in v.capabilities}


def get_models_by_provider(provider: APIProvider) -> Dict[str, ModelEntry]:
    """Get all models from a specific provider."""
    return {k: v for k, v in ALL_MODELS.items() if v.provider == provider}


def get_model_summary() -> str:
    """Generate a summary of all available models."""
    lines = [
        "# API MODEL DICTIONARY",
        "",
        "## Quick Reference (Nicknames)",
        "",
        "| Nickname | Official Name | Provider | Capabilities |",
        "|----------|---------------|----------|--------------|",
    ]

    for key, model in ALL_MODELS.items():
        nicks = ", ".join(model.nicknames[:2])
        caps = ", ".join([c.value.replace("_", " ") for c in model.capabilities[:2]])
        lines.append(f"| {nicks} | {model.display_name} | {model.provider.value} | {caps} |")

    lines.extend([
        "",
        "## Image Generation Models",
        "",
    ])

    for key, model in get_image_models().items():
        lines.append(f"- **{model.display_name}** (`{model.model_id}`)")
        lines.append(f"  - Nicknames: {', '.join(model.nicknames)}")
        lines.append(f"  - {model.description}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# SYMBOLIC NOTATION FOR MODELS
# =============================================================================

MODEL_SYMBOLS = {
    # Image Generation
    "@IMG_NANO_BANANA": "nano_banana",
    "@IMG_NANO_BANANA_PRO": "nano_banana_pro",
    "@IMG_IMAGEN": "imagen_3",
    "@IMG_SEEDREAM": "seedream_4_5",
    "@IMG_FLUX_KONTEXT": "flux_kontext_pro",
    "@IMG_FLUX_MAX": "flux_kontext_max",
    "@IMG_SDXL": "sdxl",
    "@IMG_DALLE": "dall_e_3",

    # Text Generation
    "@LLM_CLAUDE": "claude_opus_4_5",
    "@LLM_HAIKU": "claude_haiku",
    "@LLM_GEMINI": "gemini_2_5_flash",
    "@LLM_GEMINI_PRO": "gemini_3_pro",
    "@LLM_GPT4O": "gpt_4o",
    "@LLM_GROK": "grok_4",
}


def lookup_by_symbol(symbol: str) -> Optional[ModelEntry]:
    """Look up model by symbolic notation."""
    if symbol.upper() in MODEL_SYMBOLS:
        key = MODEL_SYMBOLS[symbol.upper()]
        return ALL_MODELS.get(key)
    return None


def get_symbol_for_model(model_key: str) -> Optional[str]:
    """Get symbolic notation for a model key."""
    for symbol, key in MODEL_SYMBOLS.items():
        if key == model_key:
            return symbol
    return None


