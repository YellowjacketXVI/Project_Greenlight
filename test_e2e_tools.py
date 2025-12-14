"""
End-to-End Pipeline Test Script for Project Greenlight

This script tests the complete pipeline sequence:
1. Writer Pipeline - Generate script from pitch.md and world_config.json
2. Director Pipeline - Process script.md to create visual scripts
3. Reference Image Generation - Extract tags and generate reference images
4. Storyboard Creation - Generate final storyboard images

Usage:
    1. Start the Greenlight app: py -m greenlight
    2. Open a project (e.g., "Go for Orchid")
    3. Run this script: py test_e2e_tools.py --test e2e

Requirements:
    - Greenlight app must be running with backdoor enabled
    - A project must be loaded
"""
import sys
import time
import argparse
sys.path.insert(0, '.')

from greenlight.omni_mind.backdoor import BackdoorClient


def test_tools_registration():
    """Verify E2E pipeline tools are properly registered."""
    from greenlight.omni_mind.tool_executor import ToolExecutor

    print("=" * 60)
    print("Testing Tool Registration")
    print("=" * 60)

    t = ToolExecutor()
    print(f'Total tool declarations: {len(t._declarations)}')

    # Find E2E and reference tools
    e2e_tools = [d.name for d in t._declarations if 'e2e' in d.name.lower() or 'reference' in d.name.lower()]
    print(f'\nE2E and Reference tools: {e2e_tools}')

    # Check if methods exist
    methods = ['_run_e2e_pipeline', '_generate_all_reference_images', '_wait_for_pipeline', '_get_e2e_pipeline_status']
    all_exist = True
    for method in methods:
        exists = hasattr(t, method)
        print(f'  {method}: {"✓" if exists else "✗"}')
        if not exists:
            all_exist = False

    return all_exist


def test_e2e_pipeline_dry_run(client):
    """Test E2E pipeline in dry-run mode (no actual execution)."""
    print("\n" + "=" * 60)
    print("Testing E2E Pipeline (Dry Run)")
    print("=" * 60)

    result = client.run_e2e_pipeline(
        llm="claude-sonnet-4.5",
        image_model="seedream",
        generate_references=True,
        dry_run=True
    )

    print(f"Success: {result.get('success')}")
    print(f"Result: {result.get('result')}")

    if result.get('result', {}).get('dry_run'):
        print(f"  Pipeline: {result['result'].get('pipeline')}")
        print(f"  Config: {result['result'].get('config')}")
        print(f"  Message: {result['result'].get('message')}")
        return True

    return False


def test_e2e_pipeline_full(client):
    """Execute full E2E pipeline."""
    print("\n" + "=" * 60)
    print("Executing Full E2E Pipeline")
    print("=" * 60)
    print("Pipeline: Writer → Director → References → Storyboard")
    print("LLM: Claude Sonnet 4.5")
    print("Image Model: Seedream 4.5")
    print("-" * 60)

    # Start the pipeline (frame count determined autonomously)
    print("\n[1/4] Starting pipeline...")
    result = client.run_e2e_pipeline(
        llm="claude-sonnet-4.5",
        image_model="seedream",
        generate_references=True,
        dry_run=False
    )

    if not result.get('success'):
        print(f"ERROR: Pipeline failed to start: {result.get('error')}")
        return False

    print(f"Pipeline started successfully")

    # Monitor progress
    print("\n[2/4] Monitoring pipeline progress...")
    max_wait = 600  # 10 minutes
    poll_interval = 10
    start_time = time.time()

    while (time.time() - start_time) < max_wait:
        status = client.get_e2e_status()

        if not status.get('success'):
            print(f"  Warning: Could not get status: {status.get('error')}")
            time.sleep(poll_interval)
            continue

        pipeline_status = status.get('result', {})
        overall = pipeline_status.get('status', 'unknown')
        stages = pipeline_status.get('stages', {})

        # Print stage status
        stage_line = []
        for stage_name in ['writer', 'director', 'references', 'storyboard']:
            stage = stages.get(stage_name, {})
            s = stage.get('status', 'pending')
            if s == 'complete':
                stage_line.append(f"{stage_name}:✓")
            elif s == 'running':
                stage_line.append(f"{stage_name}:⟳")
            elif s == 'failed':
                stage_line.append(f"{stage_name}:✗")
            elif s == 'skipped':
                stage_line.append(f"{stage_name}:⊘")
            else:
                stage_line.append(f"{stage_name}:○")

        elapsed = int(time.time() - start_time)
        print(f"  [{elapsed}s] {' | '.join(stage_line)} | Overall: {overall}")

        if overall in ['complete', 'failed']:
            break

        time.sleep(poll_interval)

    # Final status
    print("\n[3/4] Final Status:")
    final_status = client.get_e2e_status()
    if final_status.get('success'):
        result = final_status.get('result', {})
        print(f"  Status: {result.get('status')}")
        print(f"  Started: {result.get('started_at')}")

        if result.get('errors'):
            print(f"  Errors: {result.get('errors')}")

        stages = result.get('stages', {})
        for stage_name, stage_data in stages.items():
            print(f"  {stage_name}: {stage_data.get('status')}")

    # Validate outputs
    print("\n[4/4] Validating outputs...")
    return validate_pipeline_outputs(client)


def validate_pipeline_outputs(client):
    """Validate that all expected outputs were generated."""
    print("\nValidation Results:")

    # Use tool executor to check files
    result = client.execute_tool('list_project_files')

    if not result.get('success'):
        print(f"  Could not list project files: {result.get('error')}")
        return False

    files = result.get('result', {}).get('files', [])

    # Check for expected outputs
    checks = {
        'script.md': False,
        'visual_script.json': False,
        'references/': False,
        'storyboard_output/': False
    }

    for f in files:
        if 'script.md' in f:
            checks['script.md'] = True
        if 'visual_script.json' in f:
            checks['visual_script.json'] = True
        if 'references/' in f:
            checks['references/'] = True
        if 'storyboard_output/' in f:
            checks['storyboard_output/'] = True

    all_passed = True
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    return all_passed


def main():
    parser = argparse.ArgumentParser(description='E2E Pipeline Test for Project Greenlight')
    parser.add_argument('--test', default='tools',
                       choices=['tools', 'dry_run', 'e2e', 'all'],
                       help='Test to run')
    args = parser.parse_args()

    # Test tool registration (doesn't require running app)
    if args.test in ['tools', 'all']:
        if not test_tools_registration():
            print("\n✗ Tool registration test failed")
            return 1
        print("\n✓ Tool registration test passed")

    # Tests that require running app
    if args.test in ['dry_run', 'e2e', 'all']:
        client = BackdoorClient()

        if not client.ping():
            print('\nERROR: Backdoor server not running.')
            print('Start the app first: py -m greenlight')
            return 1

        print("\n✓ Connected to Greenlight app")

        if args.test in ['dry_run', 'all']:
            if not test_e2e_pipeline_dry_run(client):
                print("\n✗ Dry run test failed")
                return 1
            print("\n✓ Dry run test passed")

        if args.test == 'e2e':
            if not test_e2e_pipeline_full(client):
                print("\n✗ E2E pipeline test failed")
                return 1
            print("\n✓ E2E pipeline test passed")

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())

