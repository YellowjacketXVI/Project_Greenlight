"""Trigger reference image generation via OmniMind backdoor."""
import sys
sys.path.insert(0, '.')
from greenlight.omni_mind.backdoor import BackdoorClient

client = BackdoorClient()

# Check if app is running
if not client.ping():
    print("ERROR: Greenlight app not running")
    sys.exit(1)

# Generate reference images for all extracted tags
print('Triggering reference image generation...')
print('Tag types: character, location, prop')
print('Model: nano_banana_pro')
print('This may take several minutes...')
print()

result = client.send_command('generate_reference_images', {
    'tag_types': ['character', 'location', 'prop'],
    'model': 'nano_banana_pro',
    'overwrite': False
}, timeout=600)

print(f"Success: {result.get('success')}")
print(f"Result: {result.get('result')}")
if result.get('error'):
    print(f"Error: {result.get('error')}")

