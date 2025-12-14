"""
Test Reference Image Prompt Generation

Validates that the ContextEngine integration is working correctly and that
prompts include the expanded world-building data.

Usage:
    py test_reference_prompts.py
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from greenlight.context.context_engine import ContextEngine
from greenlight.core.image_handler import ImageHandler


def print_separator(title: str):
    """Print a formatted separator."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_section(title: str, content: str):
    """Print a formatted section."""
    print(f"\n--- {title} ---")
    if content:
        # Indent content for readability
        for line in content.split('\n'):
            print(f"  {line}")
    else:
        print("  (empty)")


def test_character_prompt(image_handler: ImageHandler, context_engine: ContextEngine, tag: str):
    """Test character sheet prompt generation."""
    print_separator(f"Testing [{tag}]")
    
    # Get profile from ContextEngine
    profile = context_engine.get_character_profile(tag)
    print_section("Profile Data Retrieved from ContextEngine", 
                  json.dumps(profile, indent=2, ensure_ascii=False) if profile else "None")
    
    # Get world context
    world_context = context_engine.get_world_context_for_tag_generation()
    print_section("World Context Injected", world_context[:1000] + "..." if len(world_context) > 1000 else world_context)
    
    # Generate prompt (without passing character_data - should auto-fetch)
    name = profile.get('name', tag) if profile else tag
    prompt = image_handler.get_character_sheet_prompt(tag=tag, name=name)
    print_section("Generated Prompt", prompt)
    
    # Check reference images
    project_path = context_engine._project_path
    if project_path:
        ref_dir = project_path / "references" / tag
        if ref_dir.exists():
            refs = list(ref_dir.glob("*.png")) + list(ref_dir.glob("*.jpg"))
            print_section("Reference Images Found", "\n".join(str(r) for r in refs[:5]))
        else:
            print_section("Reference Images Found", f"No reference directory at {ref_dir}")


def test_location_prompt(image_handler: ImageHandler, context_engine: ContextEngine, tag: str, direction: str = "north"):
    """Test location view prompt generation."""
    print_separator(f"Testing [{tag}] (Direction: {direction})")
    
    # Get profile from ContextEngine
    profile = context_engine.get_location_profile(tag)
    print_section("Profile Data Retrieved from ContextEngine",
                  json.dumps(profile, indent=2, ensure_ascii=False) if profile else "None")
    
    # Get world context
    world_context = context_engine.get_world_context_for_tag_generation()
    print_section("World Context Injected", world_context[:500] + "..." if len(world_context) > 500 else world_context)
    
    # Generate prompt (without passing location_data - should auto-fetch)
    name = profile.get('name', tag) if profile else tag
    directional_view = ""
    if profile and profile.get('directional_views'):
        directional_view = profile['directional_views'].get(direction, "")
    
    prompt = image_handler.get_location_view_prompt(
        tag=tag, name=name, direction=direction, directional_view=directional_view
    )
    print_section("Generated Prompt", prompt)


def test_directional_tag(image_handler: ImageHandler, context_engine: ContextEngine, base_tag: str, direction: str):
    """Test directional location tag prompt generation."""
    directional_tag = f"{base_tag}_DIR_{direction.upper()[0]}"
    print_separator(f"Testing Directional Tag [{directional_tag}]")
    
    # Get base location profile
    profile = context_engine.get_location_profile(base_tag)
    print_section("Base Location Profile", 
                  json.dumps(profile, indent=2, ensure_ascii=False)[:800] + "..." if profile else "None")
    
    # Get directional view description
    if profile and profile.get('directional_views'):
        dir_view = profile['directional_views'].get(direction.lower(), "")
        print_section(f"Directional View ({direction})", dir_view)


def test_prop_prompt(image_handler: ImageHandler, context_engine: ContextEngine, tag: str):
    """Test prop reference prompt generation."""
    print_separator(f"Testing [{tag}]")
    
    # Get profile from ContextEngine
    profile = context_engine.get_prop_profile(tag)
    print_section("Profile Data Retrieved from ContextEngine",
                  json.dumps(profile, indent=2, ensure_ascii=False) if profile else "None")
    
    # Generate prompt (without passing prop_data - should auto-fetch)
    name = profile.get('name', tag) if profile else tag
    prompt = image_handler.get_prop_reference_prompt(tag=tag, name=name)
    print_section("Generated Prompt", prompt)


def main():
    """Run all prompt generation tests."""
    # Use The Orchids Gambit project
    project_path = Path("projects/The Orchids Gambit")
    
    if not project_path.exists():
        print(f"ERROR: Project not found at {project_path}")
        return 1
    
    print(f"\n{'#' * 80}")
    print(f"#  Reference Image Prompt Generation Test")
    print(f"#  Project: {project_path}")
    print(f"{'#' * 80}")
    
    # Initialize ContextEngine
    print("\nInitializing ContextEngine...")
    context_engine = ContextEngine()
    context_engine.set_project_path(project_path)
    print(f"  Project path set: {context_engine._project_path}")
    print(f"  World config loaded: {len(context_engine._world_config)} keys")
    
    # Initialize ImageHandler with ContextEngine
    print("\nInitializing ImageHandler with ContextEngine...")
    image_handler = ImageHandler(project_path=project_path, context_engine=context_engine)
    print(f"  ImageHandler initialized with context_engine: {image_handler._context_engine is not None}")
    
    # Test Character Prompt
    test_character_prompt(image_handler, context_engine, "CHAR_MEI")
    
    # Test Location Prompt
    test_location_prompt(image_handler, context_engine, "LOC_FLOWER_SHOP", "west")
    
    # Test Directional Tag
    test_directional_tag(image_handler, context_engine, "LOC_LIXUAN_BROTHEL", "west")
    
    # Test Prop Prompt
    test_prop_prompt(image_handler, context_engine, "PROP_GO_BOARD")
    
    print("\n" + "=" * 80)
    print("  TEST COMPLETE")
    print("=" * 80 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

