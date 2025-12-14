"""
Test the Greenlight ID System

Run with: py test_id_system.py

## Scene.Frame.Camera Notation System (CANONICAL)

The unified notation format is: `{scene}.{frame}.c{letter}`

| Component | Position | Format | Examples |
|-----------|----------|--------|----------|
| Scene     | X.x.x    | Integer | 1, 2, 8 |
| Frame     | x.X.x    | Integer | 1.1, 1.2, 2.3 |
| Camera    | x.x.X    | Letter  | 1.1.cA, 1.2.cB, 2.3.cC |
"""

from greenlight.core.id_system import IDParser, IDGenerator, IDType, convert_legacy_to_new

print("=" * 80)
print("GREENLIGHT ID SYSTEM TEST (CANONICAL FORMAT)")
print("=" * 80)

print("\n📍 TEST 1: Parsing Scene IDs (just scene number)")
print("-" * 80)

# Canonical scene IDs are just integers
scene_ids = ["1", "2", "10"]
for sid in scene_ids:
    parsed = IDParser.parse(sid)
    print(f"\nInput: {sid}")
    print(f"  Type: {parsed.id_type.value}")
    print(f"  Scene: {parsed.scene_number}")
    print(f"  Canonical: {str(parsed)}")
    assert parsed.id_type == IDType.SCENE, f"Expected SCENE, got {parsed.id_type}"

print("\n📍 TEST 1b: Parsing Beat Markers (scene.N.XX)")
print("-" * 80)

# Beat markers use scene.N.XX format
beat_ids = ["scene.1.01", "scene.2.15", "scene.10.99"]
for bid in beat_ids:
    parsed = IDParser.parse(bid)
    print(f"\nInput: {bid}")
    print(f"  Type: {parsed.id_type.value}")
    print(f"  Scene: {parsed.scene_number}, Beat: {parsed.beat_number}")
    print(f"  Beat ID: {parsed.beat_id}")
    assert parsed.id_type == IDType.SCENE, f"Expected SCENE, got {parsed.id_type}"

print("\n" + "=" * 80)
print("📍 TEST 2: Parsing Frame IDs (scene.frame)")
print("-" * 80)

# Canonical frame IDs are scene.frame (e.g., 1.1, 2.3)
frame_ids = ["1.1", "2.15", "10.99"]
for fid in frame_ids:
    parsed = IDParser.parse(fid)
    print(f"\nInput: {fid}")
    print(f"  Type: {parsed.id_type.value}")
    print(f"  Scene: {parsed.scene_number}, Frame: {parsed.frame_number}")
    print(f"  Canonical: {str(parsed)}")
    assert parsed.id_type == IDType.FRAME, f"Expected FRAME, got {parsed.id_type}"

print("\n📍 TEST 2b: Parsing Legacy Frame IDs (1.frame.01)")
print("-" * 80)

# Legacy frame IDs still supported for backward compatibility
legacy_frame_ids = ["1.frame.01", "2.frame.15", "10.frame.99"]
for fid in legacy_frame_ids:
    parsed = IDParser.parse(fid)
    print(f"\nInput: {fid} (legacy)")
    print(f"  Type: {parsed.id_type.value}")
    print(f"  Scene: {parsed.scene_number}, Frame: {parsed.frame_number}")
    print(f"  Canonical: {str(parsed)}")
    assert parsed.id_type == IDType.FRAME, f"Expected FRAME, got {parsed.id_type}"

print("\n" + "=" * 80)
print("📍 TEST 3: Parsing Camera IDs (scene.frame.cX)")
print("-" * 80)

camera_ids = ["1.1.cA", "1.1.cB", "1.2.cA", "1.2.cC", "2.3.cA"]
for cid in camera_ids:
    parsed = IDParser.parse(cid)
    print(f"\nInput: {cid}")
    print(f"  Type: {parsed.id_type.value}")
    print(f"  Scene: {parsed.scene_number}, Frame: {parsed.frame_number}, Camera: {parsed.camera_letter}")
    print(f"  Canonical: {str(parsed)}")
    assert parsed.id_type == IDType.CAMERA, f"Expected CAMERA, got {parsed.id_type}"

print("\n" + "=" * 80)
print("📍 TEST 4: Generating IDs (Canonical Format)")
print("-" * 80)

# Scene ID is just the scene number
scene_id = IDGenerator.scene_id(1)
print(f"\nGenerate scene ID for scene 1: {scene_id}")
assert scene_id == "1", f"Expected '1', got '{scene_id}'"

# Beat ID uses scene.N.XX format
beat_id = IDGenerator.beat_id(1, 1)
print(f"Generate beat ID scene.1.01: {beat_id}")
assert beat_id == "scene.1.01", f"Expected 'scene.1.01', got '{beat_id}'"

# Frame ID uses scene.frame format
frame_id = IDGenerator.frame_id(1, 1)
print(f"Generate frame ID 1.1: {frame_id}")
assert frame_id == "1.1", f"Expected '1.1', got '{frame_id}'"

# Camera ID uses scene.frame.cX format
camera_id = IDGenerator.camera_id(1, 1, 'A')
print(f"Generate camera ID 1.1.cA: {camera_id}")
assert camera_id == "1.1.cA", f"Expected '1.1.cA', got '{camera_id}'"

# Camera block notation
camera_block = IDGenerator.camera_block(1, 1, 'A', 'Wide')
print(f"Generate camera block [1.1.cA] (Wide): {camera_block}")
assert camera_block == "[1.1.cA] (Wide)", f"Expected '[1.1.cA] (Wide)', got '{camera_block}'"

print("\n" + "=" * 80)
print("📍 TEST 5: Next Camera Letter")
print("-" * 80)

existing = []
next_letter = IDGenerator.next_camera_letter(existing)
print(f"\nNo existing cameras → Next: {next_letter}")
assert next_letter == 'A'

existing = ["1.1.cA"]
next_letter = IDGenerator.next_camera_letter(existing)
print(f"Existing: {existing} → Next: {next_letter}")
assert next_letter == 'B'

existing = ["1.1.cA", "1.1.cB", "1.1.cC"]
next_letter = IDGenerator.next_camera_letter(existing)
print(f"Existing: {existing} → Next: {next_letter}")
assert next_letter == 'D'

print("\n" + "=" * 80)
print("📍 TEST 6: Legacy Format Conversion")
print("-" * 80)

# Legacy formats are converted to canonical format
legacy_conversions = [
    ("S01B01", "scene.1.01"),  # Legacy beat → beat ID
    ("S02B15", "scene.2.15"),  # Legacy beat → beat ID
    ("1.frame.01", "1.1"),     # Legacy frame → canonical frame
    ("2.frame.03", "2.3"),     # Legacy frame → canonical frame
    ("1.1a", "1.1.cA"),        # Legacy camera → canonical camera
    ("1.2b", "1.2.cB"),        # Legacy camera → canonical camera
]

for legacy, expected in legacy_conversions:
    result = convert_legacy_to_new(legacy)
    print(f"\n{legacy} → {result}")
    assert result == expected, f"Expected {expected}, got {result}"

print("\n" + "=" * 80)
print("📍 TEST 7: Hierarchy Navigation")
print("-" * 80)

camera_parsed = IDParser.parse("1.2.cB")
print(f"\nCamera ID: {camera_parsed.camera_id}")
print(f"  → Frame ID: {camera_parsed.frame_id}")
print(f"  → Scene ID: {camera_parsed.scene_id}")
print(f"  → Beat ID: {camera_parsed.beat_id}")

# Canonical format assertions
assert camera_parsed.camera_id == "1.2.cB", f"Expected '1.2.cB', got '{camera_parsed.camera_id}'"
assert camera_parsed.frame_id == "1.2", f"Expected '1.2', got '{camera_parsed.frame_id}'"
assert camera_parsed.scene_id == "1", f"Expected '1', got '{camera_parsed.scene_id}'"

print("\n" + "=" * 80)
print("📍 TEST 8: Practical Example - Director Pipeline Flow")
print("-" * 80)

print("\nStory Pipeline Output (Beat Markers):")
beat_id = IDGenerator.beat_id(1, 1)
print(f"  ## Beat: {beat_id} - Mei applies makeup")

print("\nDirector Pipeline - Frame Breakdown:")
frames = [
    IDGenerator.frame_id(1, 1),
    IDGenerator.frame_id(1, 2),
    IDGenerator.frame_id(1, 3),
]
for i, fid in enumerate(frames, 1):
    print(f"  {fid} - Frame {i}")

print("\nDirector Pipeline - Camera Planning:")
cameras = [
    IDGenerator.camera_id(1, 1, 'A'),
    IDGenerator.camera_id(1, 1, 'B'),
    IDGenerator.camera_id(1, 2, 'A'),
    IDGenerator.camera_id(1, 3, 'A'),
    IDGenerator.camera_id(1, 3, 'B'),
]
for cid in cameras:
    parsed = IDParser.parse(cid)
    print(f"  {cid} - Scene {parsed.scene_number}, Frame {parsed.frame_number}, Camera {parsed.camera_letter}")

print("\nDirector Pipeline - Camera Block Notation:")
for cid in cameras:
    parsed = IDParser.parse(cid)
    block = IDGenerator.camera_block(parsed.scene_number, parsed.frame_number, parsed.camera_letter, "Wide")
    print(f"  {block}")

print("\n" + "=" * 80)
print("✅ ALL TESTS PASSED")
print("=" * 80)
print("\nThe ID system correctly:")
print("  1. Parses scene, frame, and camera IDs (canonical format)")
print("  2. Generates new IDs in canonical format")
print("  3. Converts legacy formats to canonical")
print("  4. Navigates hierarchy (camera → frame → scene)")
print("  5. Supports director pipeline workflow")
print("  6. Generates camera block notation")
print("=" * 80)

