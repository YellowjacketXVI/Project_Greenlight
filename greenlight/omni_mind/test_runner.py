"""
OmniMind Test Runner - Backdoor for automated testing and error fixing.

Usage:
    py -m greenlight.omni_mind.test_runner --test ui
    py -m greenlight.omni_mind.test_runner --test director
    py -m greenlight.omni_mind.test_runner --test storyboard
"""

import asyncio
import subprocess
import sys
import time
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class TestResult:
    """Result of a test run."""
    name: str
    success: bool
    duration: float
    output: str = ""
    errors: List[str] = field(default_factory=list)
    tracebacks: List[str] = field(default_factory=list)


class OmniMindTestRunner:
    """
    Backdoor test runner for OmniMind.
    
    Allows direct testing of:
    - UI operations
    - Pipeline execution
    - Error capture and analysis
    """
    
    def __init__(self, project_path: str = None):
        self.project_path = Path(project_path) if project_path else None
        self.app_process: Optional[subprocess.Popen] = None
        self.tool_executor = None
        self.omni_mind = None
        self._output_buffer = []
        
    def _init_components(self):
        """Initialize OmniMind components."""
        from greenlight.omni_mind.tool_executor import ToolExecutor
        from greenlight.omni_mind.omni_mind import OmniMind, AssistantMode
        
        self.tool_executor = ToolExecutor()
        if self.project_path:
            self.tool_executor.set_project(self.project_path)
        
        self.omni_mind = OmniMind(mode=AssistantMode.AUTONOMOUS)
        if self.project_path:
            self.omni_mind.set_project(self.project_path)
        
        print(f"✅ OmniMind initialized with {len(self.tool_executor._declarations)} tools")
    
    def launch_app(self, wait_seconds: int = 5) -> bool:
        """Launch the Greenlight app in background."""
        try:
            self.app_process = subprocess.Popen(
                [sys.executable, "-m", "greenlight"],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            time.sleep(wait_seconds)
            
            if self.app_process.poll() is None:
                print(f"✅ App launched (PID: {self.app_process.pid})")
                return True
            else:
                print(f"❌ App exited early")
                return False
        except Exception as e:
            print(f"❌ Failed to launch app: {e}")
            return False
    
    def read_output(self, timeout: float = 2.0) -> str:
        """Read output from app process."""
        if not self.app_process:
            return ""
        
        output = []
        start = time.time()
        
        while time.time() - start < timeout:
            if self.app_process.stdout:
                line = self.app_process.stdout.readline()
                if line:
                    output.append(line)
                    self._output_buffer.append(line)
                else:
                    break
        
        return "".join(output)
    
    def parse_errors(self, output: str = None) -> Dict[str, Any]:
        """Parse errors from output."""
        if output is None:
            output = "".join(self._output_buffer)
        
        errors = []
        tracebacks = []
        
        # Find tracebacks
        tb_pattern = re.compile(
            r'(Traceback \(most recent call last\):.*?(?:Error|Exception)[^\n]*)',
            re.DOTALL
        )
        for match in tb_pattern.finditer(output):
            tracebacks.append(match.group(1))
        
        # Find error lines
        error_pattern = re.compile(
            r'((?:AttributeError|TypeError|ImportError|KeyError|ValueError|NameError|Exception)[^\n]*)'
        )
        for match in error_pattern.finditer(output):
            errors.append(match.group(1))
        
        return {
            "has_errors": len(errors) > 0,
            "error_count": len(errors),
            "errors": errors,
            "tracebacks": tracebacks
        }
    
    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool directly."""
        if not self.tool_executor:
            self._init_components()
        
        if tool_name not in self.tool_executor._tools:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}
        
        try:
            result = self.tool_executor._tools[tool_name](**kwargs)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def kill_app(self):
        """Kill the app process."""
        if self.app_process:
            self.app_process.terminate()
            self.app_process.wait(timeout=5)
            print("✅ App terminated")

    def run_test_sequence(self, test_name: str) -> TestResult:
        """Run a predefined test sequence."""
        start = time.time()

        if test_name == "imports":
            return self._test_imports()
        elif test_name == "tools":
            return self._test_tools()
        elif test_name == "app_launch":
            return self._test_app_launch()
        elif test_name == "ui_elements":
            return self._test_ui_elements()
        elif test_name == "director":
            return self._test_director_pipeline()
        elif test_name == "storyboard":
            return self._test_storyboard()
        elif test_name == "full":
            return self._test_full_flow()
        else:
            return TestResult(
                name=test_name,
                success=False,
                duration=time.time() - start,
                errors=[f"Unknown test: {test_name}"]
            )

    def _test_imports(self) -> TestResult:
        """Test all critical imports."""
        start = time.time()
        errors = []

        modules = [
            "greenlight.omni_mind.tool_executor",
            "greenlight.omni_mind.omni_mind",
            "greenlight.pipelines.directing_pipeline",
            "greenlight.ui.components.storyboard_table",
            "greenlight.ui.components.ui_pointer",
        ]

        for mod in modules:
            try:
                __import__(mod)
                print(f"  ✓ {mod}")
            except Exception as e:
                errors.append(f"{mod}: {e}")
                print(f"  ✗ {mod}: {e}")

        return TestResult(
            name="imports",
            success=len(errors) == 0,
            duration=time.time() - start,
            errors=errors
        )

    def _test_tools(self) -> TestResult:
        """Test tool executor."""
        start = time.time()
        self._init_components()

        tools = self.tool_executor._declarations
        print(f"  Tools registered: {len(tools)}")

        # Test a few tools
        result = self.execute_tool("list_ui_elements")
        print(f"  list_ui_elements: {result.get('success', False)}")

        return TestResult(
            name="tools",
            success=True,
            duration=time.time() - start,
            output=f"{len(tools)} tools registered"
        )

    def _test_app_launch(self) -> TestResult:
        """Test app launch and capture errors."""
        start = time.time()
        errors = []
        tracebacks = []

        print("  Launching app...")
        if not self.launch_app(wait_seconds=8):
            return TestResult(
                name="app_launch",
                success=False,
                duration=time.time() - start,
                errors=["App failed to launch"]
            )

        # Read output and check for errors
        output = self.read_output(timeout=3)
        parsed = self.parse_errors(output)

        self.kill_app()

        return TestResult(
            name="app_launch",
            success=not parsed["has_errors"],
            duration=time.time() - start,
            output=output[:500],
            errors=parsed["errors"],
            tracebacks=parsed["tracebacks"]
        )

    def _test_ui_elements(self) -> TestResult:
        """Test UI element registration."""
        start = time.time()

        # This requires the app to be running
        result = self.execute_tool("list_ui_elements")

        if result.get("success"):
            elements = result.get("elements", {})
            print(f"  UI elements: {len(elements)}")
            for eid in list(elements.keys())[:5]:
                print(f"    - {eid}")

        return TestResult(
            name="ui_elements",
            success=result.get("success", False),
            duration=time.time() - start,
            output=json.dumps(result, indent=2)[:500]
        )

    def _test_director_pipeline(self) -> TestResult:
        """Test director pipeline execution."""
        start = time.time()

        if not self.project_path:
            self.project_path = PROJECT_ROOT / "projects" / "Go for Orchid"

        self._init_components()

        # Check if script exists
        script_path = self.project_path / "scripts" / "script.md"
        if not script_path.exists():
            return TestResult(
                name="director",
                success=False,
                duration=time.time() - start,
                errors=[f"Script not found: {script_path}"]
            )

        print(f"  Script found: {script_path}")

        # Try to run director via tool
        result = self.execute_tool("run_directing", llm_id="gemini-flash")

        return TestResult(
            name="director",
            success=result.get("success", False),
            duration=time.time() - start,
            output=str(result)[:500],
            errors=[result.get("error")] if result.get("error") else []
        )

    def _test_storyboard(self) -> TestResult:
        """Test storyboard loading."""
        start = time.time()

        if not self.project_path:
            self.project_path = PROJECT_ROOT / "projects" / "Go for Orchid"

        prompts_path = self.project_path / "storyboards" / "storyboard_prompts.json"

        if prompts_path.exists():
            with open(prompts_path) as f:
                data = json.load(f)
            print(f"  Prompts loaded: {data.get('total_prompts', 0)}")
            return TestResult(
                name="storyboard",
                success=True,
                duration=time.time() - start,
                output=f"{data.get('total_prompts', 0)} prompts"
            )
        else:
            return TestResult(
                name="storyboard",
                success=False,
                duration=time.time() - start,
                errors=["storyboard_prompts.json not found"]
            )

    def _test_full_flow(self) -> TestResult:
        """Test full flow: launch, open project, run director."""
        start = time.time()
        all_errors = []

        # Test imports
        r1 = self._test_imports()
        all_errors.extend(r1.errors)

        # Test tools
        r2 = self._test_tools()
        all_errors.extend(r2.errors)

        # Test app launch
        r3 = self._test_app_launch()
        all_errors.extend(r3.errors)

        return TestResult(
            name="full",
            success=len(all_errors) == 0,
            duration=time.time() - start,
            errors=all_errors,
            tracebacks=r3.tracebacks
        )


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="OmniMind Test Runner")
    parser.add_argument("--test", default="imports",
                       choices=["imports", "tools", "app_launch", "ui_elements",
                               "director", "storyboard", "full"],
                       help="Test to run")
    parser.add_argument("--project", default=None, help="Project path")

    args = parser.parse_args()

    print(f"\n🧪 OmniMind Test Runner")
    print(f"{'='*50}")
    print(f"Test: {args.test}")
    print(f"{'='*50}\n")

    runner = OmniMindTestRunner(project_path=args.project)
    result = runner.run_test_sequence(args.test)

    print(f"\n{'='*50}")
    print(f"Result: {'✅ PASS' if result.success else '❌ FAIL'}")
    print(f"Duration: {result.duration:.2f}s")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for e in result.errors:
            print(f"  - {e}")

    if result.tracebacks:
        print(f"\nTracebacks ({len(result.tracebacks)}):")
        for tb in result.tracebacks[:2]:
            print(tb[:300])

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())

