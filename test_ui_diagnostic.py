"""
Comprehensive UI Diagnostic Test for Project Greenlight.

Tests all workspace modes and UI elements, capturing errors for self-healing analysis.
"""

import sys
import time
import json
from pathlib import Path

sys.path.insert(0, '.')

from greenlight.omni_mind.backdoor import BackdoorClient

# Test configuration
PROJECT_PATH = "projects/The Orchid's Gambit"
WORKSPACE_MODES = ["world_bible", "script", "storyboard", "gallery", "references", "editor"]

def test_connection(client: BackdoorClient) -> bool:
    """Test backdoor connection."""
    print("=" * 60)
    print("PHASE 1: CONNECTION TEST")
    print("=" * 60)
    
    if not client.ping():
        print("❌ ERROR: Backdoor server not running")
        return False
    
    print("✅ Backdoor connection successful")
    return True

def test_open_project(client: BackdoorClient) -> dict:
    """Open the test project."""
    print("\n" + "=" * 60)
    print("PHASE 2: OPEN PROJECT")
    print("=" * 60)
    
    result = client.open_project(PROJECT_PATH)
    print(f"Open project result: {result}")
    time.sleep(2)  # Wait for project to load
    return result

def test_workspace_modes(client: BackdoorClient) -> dict:
    """Test each workspace mode."""
    print("\n" + "=" * 60)
    print("PHASE 3: WORKSPACE MODE TESTS")
    print("=" * 60)
    
    results = {}
    
    for mode in WORKSPACE_MODES:
        print(f"\n--- Testing mode: {mode} ---")
        
        # Navigate to mode
        nav_result = client.navigate(mode)
        print(f"  Navigate result: {nav_result}")
        time.sleep(1)
        
        # Get workspace debug info
        debug_result = client.send_command("debug_workspace", {})
        print(f"  Debug workspace: {debug_result}")
        
        # Check for errors
        error_result = client.send_command("get_errors", {})
        print(f"  Errors: {error_result}")
        
        # List UI elements in this mode
        elements = client.list_ui_elements()
        print(f"  UI elements count: {elements.get('count', 0)}")
        
        results[mode] = {
            "navigate": nav_result,
            "debug": debug_result,
            "errors": error_result,
            "elements": elements
        }
        
        time.sleep(0.5)
    
    return results

def test_ui_elements(client: BackdoorClient) -> dict:
    """Test clicking each UI element."""
    print("\n" + "=" * 60)
    print("PHASE 4: UI ELEMENT CLICK TESTS")
    print("=" * 60)
    
    elements = client.list_ui_elements()
    results = {}
    
    if not elements.get("success"):
        print("❌ Failed to list UI elements")
        return results
    
    for element_id in elements.get("elements", {}).keys():
        print(f"\n--- Clicking: {element_id} ---")
        
        click_result = client.click(element_id)
        print(f"  Click result: {click_result}")
        
        # Check for errors after click
        error_result = client.send_command("get_errors", {})
        if error_result.get("errors"):
            print(f"  ⚠️ Errors after click: {error_result}")
        
        results[element_id] = {
            "click": click_result,
            "errors": error_result
        }
        
        time.sleep(0.5)
    
    return results

def generate_report(all_results: dict) -> None:
    """Generate diagnostic report."""
    print("\n" + "=" * 60)
    print("DIAGNOSTIC REPORT")
    print("=" * 60)
    
    # Save to file
    report_path = Path("ui_diagnostic_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n📄 Full report saved to: {report_path}")
    
    # Summary
    errors_found = []
    for category, results in all_results.items():
        if isinstance(results, dict):
            for key, value in results.items():
                if isinstance(value, dict) and value.get("errors"):
                    errors_found.append(f"{category}.{key}: {value['errors']}")
    
    if errors_found:
        print(f"\n⚠️ Errors found: {len(errors_found)}")
        for err in errors_found[:10]:
            print(f"  - {err}")
    else:
        print("\n✅ No errors detected")

def test_self_healing(client: BackdoorClient) -> dict:
    """Test self-healing capabilities."""
    print("\n" + "=" * 60)
    print("PHASE 5: SELF-HEALING TESTS")
    print("=" * 60)

    results = {}

    # Get initial healer stats
    healer_report = client.get_healer_report()
    print(f"Initial healer stats: {healer_report.get('stats', {})}")
    results["initial_stats"] = healer_report.get("stats", {})

    # Test 1: JSON repair capability
    print("\n--- Test 1: JSON Repair ---")
    from greenlight.omni_mind.self_healer import SelfHealer
    import json

    healer = SelfHealer()

    # Test with malformed JSON (trailing comma)
    malformed_json = '{"name": "test", "value": 123,}'
    try:
        json.loads(malformed_json)
    except json.JSONDecodeError as e:
        result, actions = healer.heal(e, {"content": malformed_json, "file_path": "test.json"})
        print(f"  JSON repair result: {result.value}")
        if actions:
            print(f"  Action taken: {actions[0].action_taken}")
        results["json_repair"] = {"result": result.value, "actions": [a.to_dict() for a in actions]}

    # Test 2: Missing config key
    print("\n--- Test 2: Missing Config Key ---")
    try:
        raise KeyError("visual_style")
    except KeyError as e:
        result, actions = healer.heal(e, {"project_path": PROJECT_PATH})
        print(f"  Config key result: {result.value}")
        if actions:
            print(f"  Action taken: {actions[0].action_taken}")
        results["config_key"] = {"result": result.value, "actions": [a.to_dict() for a in actions]}

    # Test 3: UI widget error (cosmetic)
    print("\n--- Test 3: UI Widget Error ---")
    try:
        raise Exception("invalid command name \".!ctkframe.!ctkscrollableframe\"")
    except Exception as e:
        result, actions = healer.heal(e, {})
        print(f"  UI widget result: {result.value}")
        if actions:
            print(f"  Action taken: {actions[0].action_taken}")
        results["ui_widget"] = {"result": result.value, "actions": [a.to_dict() for a in actions]}

    # Get final healer stats
    final_stats = healer.get_stats()
    print(f"\nFinal healer stats: {final_stats}")
    results["final_stats"] = final_stats

    # Generate report
    report = healer.generate_report()
    print(f"\n{report}")
    results["report"] = report

    return results


def main():
    client = BackdoorClient()
    all_results = {}

    # Phase 1: Connection
    if not test_connection(client):
        return 1

    # Phase 2: Open project
    all_results["open_project"] = test_open_project(client)

    # Phase 3: Test workspace modes
    all_results["workspace_modes"] = test_workspace_modes(client)

    # Phase 4: Test UI elements
    all_results["ui_elements"] = test_ui_elements(client)

    # Phase 5: Test self-healing
    all_results["self_healing"] = test_self_healing(client)

    # Generate report
    generate_report(all_results)

    print("\n✅ Diagnostic test complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())

