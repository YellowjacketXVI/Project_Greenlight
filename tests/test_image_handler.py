"""
Test Image Handler with Mei character from Go for Orchid project.

Tests all three image generators:
- Nano Banana (Gemini 2.5 Flash)
- Nano Banana Pro (Gemini 3 Pro)
- Seedream 4.5 (ByteDance via Replicate)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
env_path = project_root / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()
    print(f"✅ Loaded .env file")
    print(f"   GEMINI_API_KEY: {'set' if os.getenv('GEMINI_API_KEY') else 'not set'}")
    print(f"   REPLICATE_API_TOKEN: {'set' if os.getenv('REPLICATE_API_TOKEN') else 'not set'}")
    print()

from greenlight.core.image_handler import ImageHandler, ImageModel, ImageRequest


async def test_mei_generation():
    """Test generating Mei character with all models."""
    
    # Load world config
    project_path = Path(__file__).parent.parent / "projects" / "Go for Orchid"
    world_config_path = project_path / "world_bible" / "world_config.json"
    
    if not world_config_path.exists():
        print(f"❌ World config not found: {world_config_path}")
        return
    
    world_config = json.loads(world_config_path.read_text(encoding='utf-8'))
    
    # Get Mei's data
    mei_data = next((c for c in world_config.get("characters", []) if c.get("tag") == "CHAR_MEI"), None)
    
    if not mei_data:
        print("❌ CHAR_MEI not found in world config")
        return
    
    print("=" * 60)
    print("🎭 MEI CHARACTER DATA")
    print("=" * 60)
    print(f"Tag: {mei_data.get('tag')}")
    print(f"Name: {mei_data.get('name')}")
    print(f"Role: {mei_data.get('role')}")
    print(f"Age: {mei_data.get('age')}")
    print(f"Ethnicity: {mei_data.get('ethnicity')}")
    print(f"Appearance: {mei_data.get('appearance', '')[:200]}...")
    print(f"Costume: {mei_data.get('costume', '')[:200]}...")
    print()
    
    # Build prompt from world bible data
    prompt = f"""Character reference for [CHAR_MEI] Mei.

APPEARANCE:
{mei_data.get('appearance', '')}

COSTUME:
{mei_data.get('costume', '')}

Role: {mei_data.get('role', '')}
Age: {mei_data.get('age', '')}
Ethnicity: {mei_data.get('ethnicity', '')}

Full body portrait, detailed character design, high quality, 16:9 aspect ratio.
Feudal China setting, cinematic lighting, photorealistic style."""

    print("=" * 60)
    print("📝 GENERATION PROMPT")
    print("=" * 60)
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    print()
    
    # Initialize handler
    handler = ImageHandler(project_path)
    
    # Test each model - all available image models
    models = [
        # Google/Gemini
        (ImageModel.NANO_BANANA, "Nano Banana (Gemini 2.5 Flash)"),
        (ImageModel.NANO_BANANA_PRO, "Nano Banana Pro (Gemini 3 Pro)"),
        # (ImageModel.IMAGEN_3, "Imagen 3"),  # Requires Vertex AI

        # Replicate
        (ImageModel.SEEDREAM, "Seedream 4.5 (ByteDance)"),
        # (ImageModel.FLUX_KONTEXT_PRO, "FLUX Kontext Pro"),  # Expensive
        # (ImageModel.FLUX_1_1_PRO, "FLUX 1.1 Pro"),  # Expensive
        # (ImageModel.SDXL, "SDXL"),

        # Stability AI - requires STABILITY_API_KEY
        # (ImageModel.SD_3_5, "SD 3.5"),

        # OpenAI - requires OPENAI_API_KEY
        # (ImageModel.DALLE_3, "DALL-E 3"),
    ]
    
    results = []
    
    for model, model_name in models:
        print("=" * 60)
        print(f"🎨 TESTING: {model_name}")
        print("=" * 60)
        
        request = ImageRequest(
            prompt=prompt,
            model=model,
            aspect_ratio="16:9",
            tag=f"CHAR_MEI_test_{model.value}"
        )
        
        try:
            result = await handler.generate(request)
            
            if result.success:
                print(f"✅ SUCCESS!")
                print(f"   Model: {result.model_used}")
                print(f"   Time: {result.generation_time_ms}ms")
                print(f"   Path: {result.image_path}")
                results.append((model_name, True, result.generation_time_ms, result.image_path))
            else:
                print(f"❌ FAILED: {result.error}")
                results.append((model_name, False, 0, result.error))
                
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            results.append((model_name, False, 0, str(e)))
        
        print()
    
    # Summary
    print("=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    for model_name, success, time_ms, info in results:
        status = "✅" if success else "❌"
        if success:
            print(f"{status} {model_name}: {time_ms}ms - {info}")
        else:
            print(f"{status} {model_name}: {info}")


if __name__ == "__main__":
    print("🚀 Starting Image Handler Test for CHAR_MEI")
    print()
    asyncio.run(test_mei_generation())

