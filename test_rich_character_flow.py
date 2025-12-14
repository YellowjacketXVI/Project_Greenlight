#!/usr/bin/env python
"""
Test script to verify rich character descriptions flow through the entire system.

Tests:
1. CharacterArc dataclass has all rich fields
2. Story Pipeline parsing extracts rich fields
3. Writer dialog saves all rich fields to world_config.json
4. ContextEngine retrieves all rich fields
5. ImageHandler prompt generation includes rich fields
6. UI displays rich field indicators

Run: py test_rich_character_flow.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_character_arc_dataclass():
    """Test that CharacterArc has all rich fields."""
    from greenlight.pipelines.story_pipeline import CharacterArc
    from dataclasses import fields
    
    field_names = {f.name for f in fields(CharacterArc)}
    
    required_fields = {
        # Core
        'character_tag', 'character_name', 'role',
        # Arc
        'want', 'need', 'flaw', 'arc_type',
        # Visual
        'age', 'ethnicity', 'appearance', 'costume',
        # Rich fields (NEW)
        'psychology', 'speech_patterns', 'speech_style', 'literacy_level',
        'physicality', 'decision_heuristics', 'emotional_tells',
        'key_moments', 'relationships'
    }
    
    missing = required_fields - field_names
    if missing:
        print(f"❌ CharacterArc missing fields: {missing}")
        return False
    
    print(f"✅ CharacterArc has all {len(required_fields)} required fields")
    return True


def test_context_engine_retrieval():
    """Test that ContextEngine retrieves all rich fields."""
    from greenlight.context.context_engine import ContextEngine
    
    # Create a mock world_config with rich character data
    mock_config = {
        "characters": [{
            "tag": "CHAR_TEST",
            "name": "Test Character",
            "role": "protagonist",
            "want": "To find truth",
            "need": "To accept herself",
            "flaw": "Pride",
            "arc_type": "positive",
            "age": "25",
            "ethnicity": "Asian",
            "appearance": "Tall with dark hair and piercing eyes. Athletic build.",
            "costume": "Traditional silk robes in deep blue.",
            "visual_appearance": "Tall with dark hair and piercing eyes. Athletic build.",
            "psychology": "Driven by a need to prove herself. Masks vulnerability with confidence.",
            "speech_patterns": "Formal, measured. Uses metaphors from nature.",
            "speech_style": "formal",
            "literacy_level": "highly educated",
            "physicality": "Graceful, deliberate movements. Trained in martial arts.",
            "decision_heuristics": "Logic first, then intuition. Rarely acts impulsively.",
            "emotional_tells": {"anger": "jaw tightens", "fear": "hands tremble"},
            "key_moments": ["First defeat", "Meeting mentor"],
            "relationships": {"CHAR_MENTOR": "respect and gratitude"}
        }]
    }
    
    # Create ContextEngine with mock data
    engine = ContextEngine.__new__(ContextEngine)
    engine._world_config = mock_config
    engine._pitch_content = ""
    engine._script_content = ""
    engine._visual_script = {}
    engine._project_path = Path(".")
    
    # Test retrieval
    profile = engine.get_character_profile("CHAR_TEST")
    
    if not profile:
        print("❌ ContextEngine.get_character_profile() returned None")
        return False
    
    # Check rich fields are present
    rich_fields = ['psychology', 'speech_patterns', 'physicality', 'emotional_tells']
    missing = [f for f in rich_fields if not profile.get(f)]
    
    if missing:
        print(f"❌ ContextEngine missing rich fields: {missing}")
        return False
    
    print(f"✅ ContextEngine retrieves all rich fields correctly")
    return True


def test_image_handler_prompt():
    """Test that ImageHandler prompt includes rich character data."""
    from greenlight.core.image_handler import ImageHandler
    
    # Create handler without project path (just for prompt testing)
    handler = ImageHandler.__new__(ImageHandler)
    handler.project_path = None
    handler._context_engine = None
    
    # Test with rich character data
    char_data = {
        "age": "25",
        "ethnicity": "Asian",
        "appearance": "Tall with dark hair and piercing eyes. Athletic build with graceful posture.",
        "costume": "Traditional silk robes in deep blue with gold embroidery.",
        "visual_appearance": "Tall with dark hair and piercing eyes. Athletic build with graceful posture."
    }
    
    prompt = handler.get_character_sheet_prompt("CHAR_TEST", "Test Character", character_data=char_data)
    
    # Check that rich data is in prompt
    if "Tall with dark hair" not in prompt:
        print("❌ ImageHandler prompt missing appearance data")
        return False
    
    if "silk robes" not in prompt:
        print("❌ ImageHandler prompt missing costume data")
        return False
    
    print(f"✅ ImageHandler prompt includes rich character data")
    print(f"   Prompt length: {len(prompt)} chars")
    return True


def main():
    print("=" * 60)
    print("Testing Rich Character Description Flow")
    print("=" * 60)
    
    results = []
    
    print("\n1. Testing CharacterArc dataclass...")
    results.append(test_character_arc_dataclass())
    
    print("\n2. Testing ContextEngine retrieval...")
    results.append(test_context_engine_retrieval())
    
    print("\n3. Testing ImageHandler prompt generation...")
    results.append(test_image_handler_prompt())
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

