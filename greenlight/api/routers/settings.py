"""Settings router for Project Greenlight API."""

import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class LLMSettings(BaseModel):
    anthropic_key: str = ""
    openai_key: str = ""
    google_key: str = ""


class UISettings(BaseModel):
    theme: str = "dark"
    font_size: int = 13


class ProjectSettings(BaseModel):
    default_llm: str = "anthropic"
    auto_save: bool = True
    auto_regen: bool = False


class AppSettings(BaseModel):
    llm: LLMSettings = LLMSettings()
    ui: UISettings = UISettings()
    project: ProjectSettings = ProjectSettings()


def _get_settings_path() -> Path:
    """Get path to settings file."""
    return Path(__file__).parent.parent.parent.parent / "config" / "settings.json"


@router.get("")
async def get_settings():
    """Get application settings."""
    settings_path = _get_settings_path()
    
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            return data
        except Exception:
            pass
    
    # Return defaults
    return AppSettings().model_dump()


@router.post("")
async def save_settings(settings: AppSettings):
    """Save application settings."""
    settings_path = _get_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    
    settings_path.write_text(json.dumps(settings.model_dump(), indent=2), encoding="utf-8")
    return {"success": True, "message": "Settings saved"}


@router.get("/llm-providers")
async def get_llm_providers():
    """Get available LLM providers and models."""
    try:
        from greenlight.config.api_dictionary import get_llm_models
        models = get_llm_models()
        
        providers = {}
        for key, model in models.items():
            provider = model.provider.value
            if provider not in providers:
                providers[provider] = []
            providers[provider].append({
                "key": key,
                "display_name": model.display_name,
                "model_id": model.model_id,
                "symbol": model.symbol
            })
        
        return {"providers": providers}
    except Exception as e:
        return {"providers": {}, "error": str(e)}


@router.get("/image-models")
async def get_image_models():
    """Get available image generation models."""
    try:
        from greenlight.config.api_dictionary import get_image_models
        models = get_image_models()
        
        result = []
        for key, model in models.items():
            result.append({
                "key": key,
                "display_name": model.display_name,
                "model_id": model.model_id,
                "provider": model.provider.value,
                "description": model.description
            })
        
        return {"models": result}
    except Exception as e:
        return {"models": [], "error": str(e)}

