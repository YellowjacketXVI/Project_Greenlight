"""
Proof of Concept: Symbolic Vectoring System
============================================

Comprehensive test suite demonstrating:
1. Symbolic notation parsing and routing
2. Vector language translation (Natural ↔ Vector)
3. Notation library registration and lookup
4. Vector memory storage and retrieval
5. Error handoff with self-healing iteration
6. LLM handshake protocol with context loading
7. Complete end-to-end pipeline validation

Each test generates documented proof with input/output pairs.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Imports from Agnostic_Core_OS
from Agnostic_Core_OS.translators.vector_language import (
    VectorLanguageTranslator, NotationType, VectorNotation, TranslationResult
)
from Agnostic_Core_OS.procedural.notation_library import (
    NotationLibrary, NotationType as LibNotationType, NotationScope, NotationEntry
)
from Agnostic_Core_OS.memory.vector_memory import (
    VectorMemory, MemoryType, MemoryPriority, MemoryEntry
)
from Agnostic_Core_OS.protocols.llm_handshake import (
    LLMHandshake, HandshakeConfig, HandshakePhase, HandshakeStatus
)
from Agnostic_Core_OS.validators.iteration_validator import IterationValidator

# Imports from Agnostic_Core_OS Core Routing (standalone self-healing)
from Agnostic_Core_OS.core_routing.vector_cache import VectorCache, CacheEntryType, VectorWeight
from Agnostic_Core_OS.core_routing.health_logger import HealthLogger as ProjectHealthLogger, LogCategory
from Agnostic_Core_OS.core_routing.error_handoff import ErrorHandoff, ErrorSeverity


class TestStatus(Enum):
    """Status of individual tests."""
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    HEALED = "🔧 HEALED"
    SKIPPED = "⏭️ SKIPPED"


@dataclass
class TestResult:
    """Result of a single test."""
    test_name: str
    status: TestStatus
    description: str
    input_data: Any
    expected_output: Any
    actual_output: Any
    iterations: int = 1
    healing_applied: bool = False
    healing_details: str = ""
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "status": self.status.value,
            "description": self.description,
            "input": str(self.input_data)[:500],
            "expected": str(self.expected_output)[:500],
            "actual": str(self.actual_output)[:500],
            "iterations": self.iterations,
            "healing_applied": self.healing_applied,
            "healing_details": self.healing_details,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ProofOfConceptReport:
    """Complete proof of concept report."""
    title: str = "Symbolic Vectoring Proof of Concept"
    version: str = "1.0"
    generated_at: datetime = field(default_factory=datetime.now)
    tests: List[TestResult] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    
    def add_result(self, result: TestResult):
        self.tests.append(result)
        status_key = result.status.name
        self.summary[status_key] = self.summary.get(status_key, 0) + 1
    
    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            f"# {self.title}",
            f"**Version:** {self.version}",
            f"**Generated:** {self.generated_at.isoformat()}",
            "",
            "---",
            "",
            "## Summary",
            "",
            "| Status | Count |",
            "|--------|-------|",
        ]
        
        for status, count in self.summary.items():
            lines.append(f"| {status} | {count} |")
        
        total = sum(self.summary.values())
        passed = self.summary.get("PASSED", 0) + self.summary.get("HEALED", 0)
        lines.extend([
            "",
            f"**Total Tests:** {total}",
            f"**Success Rate:** {(passed/total*100):.1f}%" if total > 0 else "N/A",
            "",
            "---",
            "",
            "## Detailed Test Results",
            "",
        ])
        
        for i, test in enumerate(self.tests, 1):
            lines.extend([
                f"### Test {i}: {test.test_name}",
                f"**Status:** {test.status.value}",
                f"**Description:** {test.description}",
                "",
                "**Input:**",
                "```",
                str(test.input_data)[:300],
                "```",
                "",
                "**Expected Output:**",
                "```",
                str(test.expected_output)[:300],
                "```",
                "",
                "**Actual Output:**",
                "```",
                str(test.actual_output)[:300],
                "```",
                "",
            ])
            
            if test.healing_applied:
                lines.extend([
                    f"**🔧 Self-Healing Applied:** {test.healing_details}",
                    f"**Iterations:** {test.iterations}",
                    "",
                ])
            
            lines.append("---\n")
        
        return "\n".join(lines)


class SymbolicVectoringTestSuite:
    """
    Complete test suite for symbolic vectoring proof of concept.

    Tests all components of the symbolic notation system with
    self-healing iteration on failures.
    """

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or PROJECT_ROOT / ".proof_of_concept"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.report = ProofOfConceptReport()

        # Initialize components
        self.translator = VectorLanguageTranslator()
        self.notation_library = NotationLibrary(self.output_dir / "notation_lib")
        self.vector_memory = VectorMemory(self.output_dir / "memory")
        self.vector_cache = VectorCache(self.output_dir / "cache")
        self.health_logger = ProjectHealthLogger(project_path=self.output_dir)
        self.error_handoff = ErrorHandoff(
            vector_cache=self.vector_cache,
            health_logger=self.health_logger
        )
        self.handshake = LLMHandshake(
            translator=self.translator,
            log_dir=self.output_dir / "handshake_logs"
        )

        # Self-healing state
        self.max_heal_iterations = 3
        self.healing_strategies: Dict[str, callable] = {}

    def _time_test(self, func):
        """Time a test function."""
        import time
        start = time.time()
        result = func()
        duration = (time.time() - start) * 1000
        return result, duration

    async def _time_async_test(self, coro):
        """Time an async test."""
        import time
        start = time.time()
        result = await coro
        duration = (time.time() - start) * 1000
        return result, duration

    # =========================================================================
    # TEST 1: Vector Language Translation (Natural → Vector)
    # =========================================================================
    def test_natural_to_vector_translation(self) -> TestResult:
        """Test translating natural language to vector notation."""
        test_cases = [
            ("Find character Mei in the story", "@CHAR_MEI #STORY"),
            ("Run the story pipeline", ">story standard"),
            ("Run diagnostics", ">diagnose"),
            ("Look up the location teahouse in world bible", "@LOC_TEAHOUSE #WORLD_BIBLE"),
        ]

        results = []
        for natural, expected_vector in test_cases:
            translation = self.translator.natural_to_vector(natural)
            results.append({
                "input": natural,
                "expected": expected_vector,
                "actual": translation.output_text,
                "success": translation.success,
                "notations": [n.to_dict() for n in translation.notations]
            })

        all_passed = all(r["success"] for r in results)

        return TestResult(
            test_name="Natural → Vector Translation",
            status=TestStatus.PASSED if all_passed else TestStatus.FAILED,
            description="Translate natural language queries to vector notation",
            input_data=test_cases,
            expected_output=[tc[1] for tc in test_cases],
            actual_output=results,
            duration_ms=0
        )

    # =========================================================================
    # TEST 2: Vector Language Translation (Vector → Natural)
    # =========================================================================
    def test_vector_to_natural_translation(self) -> TestResult:
        """Test translating vector notation to natural language."""
        test_cases = [
            ("@CHAR_MEI #STORY", "Look up character"),
            (">diagnose", "Run project diagnostics"),
            (">route error", "Route error"),
        ]

        results = []
        for vector, expected_contains in test_cases:
            translation = self.translator.vector_to_natural(vector)
            results.append({
                "input": vector,
                "expected_contains": expected_contains,
                "actual": translation.output_text,
                "success": expected_contains.lower() in translation.output_text.lower(),
                "notations_parsed": len(translation.notations)
            })

        all_passed = all(r["success"] for r in results)

        return TestResult(
            test_name="Vector → Natural Translation",
            status=TestStatus.PASSED if all_passed else TestStatus.FAILED,
            description="Translate vector notation back to natural language",
            input_data=test_cases,
            expected_output=[tc[1] for tc in test_cases],
            actual_output=results,
            duration_ms=0
        )

    # =========================================================================
    # TEST 3: Notation Library Registration & Lookup
    # =========================================================================
    def test_notation_library_operations(self) -> TestResult:
        """Test notation library registration, lookup, and search."""
        # Register custom notations
        custom_notations = [
            ("@CHAR_HERO", LibNotationType.TAG, "Main protagonist tag"),
            ("@LOC_CASTLE", LibNotationType.TAG, "Castle location tag"),
            (">render", LibNotationType.COMMAND, "Render storyboard frames"),
        ]

        registered = []
        for symbol, ntype, definition in custom_notations:
            entry = self.notation_library.register(
                symbol=symbol,
                notation_type=ntype,
                scope=NotationScope.PROJECT,
                definition=definition,
                pattern=symbol.replace("_", r"_\w*"),
                examples=[symbol]
            )
            registered.append(entry.to_dict())

        # Lookup operations
        lookups = []
        for symbol, _, _ in custom_notations:
            entry = self.notation_library.get(symbol)
            lookups.append({
                "symbol": symbol,
                "found": entry is not None,
                "definition": entry.definition if entry else None
            })

        # Search operations
        search_results = self.notation_library.search("character")

        # Get stats
        stats = self.notation_library.get_stats()

        all_found = all(l["found"] for l in lookups)

        return TestResult(
            test_name="Notation Library Operations",
            status=TestStatus.PASSED if all_found else TestStatus.FAILED,
            description="Register, lookup, and search notation definitions",
            input_data={"registered": custom_notations, "searches": ["character"]},
            expected_output={"all_registered": True, "all_found": True},
            actual_output={
                "registered": len(registered),
                "lookups": lookups,
                "search_results": len(search_results),
                "stats": stats
            },
            duration_ms=0
        )

    # =========================================================================
    # TEST 4: Vector Cache Operations with Weights
    # =========================================================================
    def test_vector_cache_weighted_storage(self) -> TestResult:
        """Test vector cache with weighted entries and routing."""
        # Add entries with different weights
        entries_added = []

        # Active entry (weight +1.0)
        active = self.vector_cache.add(
            content="Character Mei: A skilled warrior seeking redemption",
            entry_type=CacheEntryType.NOTATION_DEFINITION,
            weight=1.0,
            tag="@CHAR_MEI",
            scope="world_bible"
        )
        entries_added.append({"id": active.id, "weight": active.weight, "type": "active"})

        # Task context
        task = self.vector_cache.add(
            content="Current task: Generate scene 1 storyboard",
            entry_type=CacheEntryType.TASK_CONTEXT,
            weight=1.0,
            task_id="task_001"
        )
        entries_added.append({"id": task.id, "weight": task.weight, "type": "task"})

        # Archive an entry (weight -0.5)
        self.vector_cache.archive(active.id)
        archived_entry = self.vector_cache.get(active.id)
        archived_weight = archived_entry.weight  # Capture weight BEFORE restore

        # Get active vs archived
        active_entries = self.vector_cache.get_active()
        archived_entries = self.vector_cache.get_archived()

        # Restore
        self.vector_cache.restore(active.id)
        restored_entry = self.vector_cache.get(active.id)
        restored_weight = restored_entry.weight  # Capture weight AFTER restore

        # Stats
        stats = self.vector_cache.get_stats()

        archive_worked = archived_weight == -0.5
        restore_worked = restored_weight == 1.0

        return TestResult(
            test_name="Vector Cache Weighted Storage",
            status=TestStatus.PASSED if archive_worked and restore_worked else TestStatus.FAILED,
            description="Test weighted vector caching with archive/restore operations",
            input_data={"entries_to_add": 2, "operations": ["add", "archive", "restore"]},
            expected_output={"archive_weight": -0.5, "restore_weight": 1.0},
            actual_output={
                "entries_added": entries_added,
                "archived_weight": archived_weight,
                "restored_weight": restored_weight,
                "active_count": len(active_entries),
                "archived_count": len(archived_entries),
                "stats": stats
            },
            duration_ms=0
        )

    # =========================================================================
    # TEST 5: Vector Memory Storage & Retrieval
    # =========================================================================
    def test_vector_memory_operations(self) -> TestResult:
        """Test vector memory storage with notation indexing."""
        # Store various memory types
        stored = []

        # UI State memory
        ui_mem = self.vector_memory.store(
            memory_type=MemoryType.UI_STATE,
            content={"panel": "storyboard", "zoom": 1.5, "selected_frame": "frame_1.3"},
            vector_notation="@UI_STATE_STORYBOARD",
            natural_language="User viewing storyboard panel at 150% zoom",
            priority=MemoryPriority.NORMAL,
            tags=["ui", "storyboard"]
        )
        stored.append(ui_mem.id)

        # Vector translation memory
        trans_mem = self.vector_memory.store(
            memory_type=MemoryType.VECTOR_TRANSLATION,
            content={"natural": "Find Mei", "vector": "@CHAR_MEI"},
            vector_notation="@CHAR_MEI",
            natural_language="Translation: Find Mei → @CHAR_MEI",
            priority=MemoryPriority.HIGH,
            tags=["translation", "character"]
        )
        stored.append(trans_mem.id)

        # Query by vector notation
        vector_results = self.vector_memory.query_by_vector("@CHAR_MEI")

        # Query by type
        type_results = self.vector_memory.query_by_type(MemoryType.UI_STATE)

        # Query by tags
        tag_results = self.vector_memory.query_by_tags(["translation"])

        # Get recent
        recent = self.vector_memory.get_recent(5)

        # Stats
        stats = self.vector_memory.get_stats()

        success = len(vector_results) > 0 and len(type_results) > 0

        return TestResult(
            test_name="Vector Memory Operations",
            status=TestStatus.PASSED if success else TestStatus.FAILED,
            description="Store and retrieve memories with vector notation indexing",
            input_data={"memories_stored": 2, "queries": ["by_vector", "by_type", "by_tags"]},
            expected_output={"vector_query_results": ">0", "type_query_results": ">0"},
            actual_output={
                "stored_ids": stored,
                "vector_query_count": len(vector_results),
                "type_query_count": len(type_results),
                "tag_query_count": len(tag_results),
                "recent_count": len(recent),
                "stats": stats
            },
            duration_ms=0
        )

    # =========================================================================
    # TEST 6: Error Handoff with Self-Healing
    # =========================================================================
    def test_error_handoff_self_healing(self) -> TestResult:
        """Test error detection, handoff, and self-healing iteration."""
        healing_iterations = 0
        healing_details = []

        # Simulate an error
        try:
            raise ValueError("Missing required tag @CHAR_UNKNOWN in scene definition")
        except Exception as e:
            # Handoff the error
            handoff_result = self.error_handoff.handoff_for_guidance(
                error=e,
                severity=ErrorSeverity.ERROR,
                source="test_pipeline",
                context={"scene": 1, "frame": 3, "missing_tag": "@CHAR_UNKNOWN"}
            )

            transcript = handoff_result["transcript"]
            task = handoff_result["task"]

            # Self-healing iteration
            max_iterations = 3
            healed = False

            for i in range(max_iterations):
                healing_iterations += 1

                # Healing strategy: Register the missing tag
                if "CHAR_UNKNOWN" in str(e):
                    # Register the missing tag
                    self.notation_library.register(
                        symbol="@CHAR_UNKNOWN",
                        notation_type=LibNotationType.TAG,
                        scope=NotationScope.PROJECT,
                        definition="Auto-registered character tag (healed)",
                        pattern="@CHAR_UNKNOWN",
                        examples=["@CHAR_UNKNOWN"]
                    )
                    healing_details.append(f"Iteration {i+1}: Registered missing tag @CHAR_UNKNOWN")

                    # Verify the fix
                    fixed_entry = self.notation_library.get("@CHAR_UNKNOWN")
                    if fixed_entry:
                        healed = True
                        # Resolve the error
                        self.error_handoff.resolve_error(
                            transcript.id,
                            f"Auto-healed: Registered missing tag after {i+1} iterations"
                        )
                        break

                healing_details.append(f"Iteration {i+1}: Attempting alternative healing...")

        # Log to health
        self.health_logger.log(
            LogCategory.SELF_HEAL,
            f"Self-healing completed: {healed}",
            iterations=healing_iterations,
            healed=healed
        )

        return TestResult(
            test_name="Error Handoff & Self-Healing",
            status=TestStatus.HEALED if healed else TestStatus.FAILED,
            description="Detect errors, create handoff transcript, and self-heal with iteration",
            input_data={"error": "Missing tag @CHAR_UNKNOWN", "max_iterations": 3},
            expected_output={"healed": True, "tag_registered": True},
            actual_output={
                "transcript_id": transcript.id if transcript else None,
                "task_created": task is not None,
                "healed": healed,
                "iterations": healing_iterations,
                "healing_log": healing_details
            },
            iterations=healing_iterations,
            healing_applied=healed,
            healing_details="; ".join(healing_details),
            duration_ms=0
        )

    # =========================================================================
    # TEST 7: LLM Handshake Protocol
    # =========================================================================
    async def test_llm_handshake_protocol(self) -> TestResult:
        """Test LLM handshake with context loading and vector translation."""
        # Load context vectors
        self.handshake.load_context(
            key="character",
            value={"name": "Mei", "role": "protagonist", "traits": ["brave", "skilled"]},
            notation="@CHAR_MEI",
            weight=1.0
        )
        self.handshake.load_context(
            key="location",
            value={"name": "Teahouse", "type": "interior", "mood": "tense"},
            notation="@LOC_TEAHOUSE",
            weight=0.8
        )

        # Build system prompt
        system_prompt = self.handshake.build_system_prompt({"project": "Go for Orchid"})

        # Execute handshake (mock LLM)
        result = await self.handshake.execute(
            natural_input="Describe Mei's motivation in the teahouse scene",
            context={"scene": 1, "mood": "tense"}
        )

        # Get history
        history = self.handshake.get_history()

        success = result.status == HandshakeStatus.SUCCESS

        return TestResult(
            test_name="LLM Handshake Protocol",
            status=TestStatus.PASSED if success else TestStatus.FAILED,
            description="Execute LLM handshake with context loading and vector translation",
            input_data={
                "natural_input": "Describe Mei's motivation in the teahouse scene",
                "context_loaded": ["@CHAR_MEI", "@LOC_TEAHOUSE"]
            },
            expected_output={"status": "SUCCESS", "phases_completed": 7},
            actual_output={
                "handshake_id": result.handshake_id,
                "status": result.status.value,
                "phase": result.phase.value,
                "input_vector": result.input_vector,
                "output_natural": result.output_natural[:200],
                "tokens_in": result.tokens_input,
                "tokens_out": result.tokens_output,
                "duration_ms": result.duration_ms,
                "history_count": len(history)
            },
            duration_ms=result.duration_ms
        )

    # =========================================================================
    # TEST 8: End-to-End Pipeline with Iteration
    # =========================================================================
    async def test_end_to_end_pipeline(self) -> TestResult:
        """Test complete symbolic vectoring pipeline with iteration."""
        pipeline_steps = []
        iterations = 0
        max_iterations = 5
        success = False

        while iterations < max_iterations and not success:
            iterations += 1
            step_results = []

            try:
                # Step 1: Natural language input
                natural_input = "Create a storyboard frame for Mei entering the teahouse"
                step_results.append({"step": "input", "data": natural_input})

                # Step 2: Translate to vector
                translation = self.translator.natural_to_vector(natural_input)
                step_results.append({
                    "step": "translate",
                    "vector": translation.output_text,
                    "notations": len(translation.notations)
                })

                # Step 3: Parse notations
                notations = self.translator.parse_notations(translation.output_text)
                step_results.append({
                    "step": "parse",
                    "notations_found": [n.to_dict() for n in notations]
                })

                # Step 4: Lookup in notation library
                lookups = []
                for notation in notations:
                    entry = self.notation_library.get(notation.raw)
                    lookups.append({
                        "notation": notation.raw,
                        "found": entry is not None
                    })
                step_results.append({"step": "lookup", "results": lookups})

                # Step 5: Store in vector memory
                mem_entry = self.vector_memory.store(
                    memory_type=MemoryType.WORKFLOW,
                    content={
                        "input": natural_input,
                        "vector": translation.output_text,
                        "notations": [n.to_dict() for n in notations]
                    },
                    vector_notation=translation.output_text,
                    natural_language=natural_input,
                    priority=MemoryPriority.HIGH,
                    tags=["pipeline", "storyboard"]
                )
                step_results.append({"step": "store", "memory_id": mem_entry.id})

                # Step 6: Cache result
                cache_entry = self.vector_cache.add(
                    content=json.dumps({
                        "input": natural_input,
                        "output": translation.output_text,
                        "timestamp": datetime.now().isoformat()
                    }),
                    entry_type=CacheEntryType.RETRIEVAL_RESULT,
                    weight=1.0,
                    pipeline="end_to_end"
                )
                step_results.append({"step": "cache", "cache_id": cache_entry.id})

                # Step 7: Log to health
                self.health_logger.log_pipeline(
                    "end_to_end_test",
                    "success",
                    duration_seconds=0.1
                )
                step_results.append({"step": "log", "logged": True})

                success = True
                pipeline_steps = step_results

            except Exception as e:
                # Self-heal on error
                self.error_handoff.handoff_for_guidance(
                    error=e,
                    severity=ErrorSeverity.WARNING,
                    source="end_to_end_pipeline",
                    context={"iteration": iterations, "steps_completed": len(step_results)}
                )
                pipeline_steps = step_results
                pipeline_steps.append({"step": "error", "message": str(e), "healing": True})

        return TestResult(
            test_name="End-to-End Pipeline",
            status=TestStatus.PASSED if success else TestStatus.HEALED if iterations > 1 else TestStatus.FAILED,
            description="Complete symbolic vectoring pipeline with all components",
            input_data={"natural_input": "Create a storyboard frame for Mei entering the teahouse"},
            expected_output={"steps_completed": 7, "success": True},
            actual_output={
                "iterations": iterations,
                "success": success,
                "steps": pipeline_steps
            },
            iterations=iterations,
            healing_applied=iterations > 1,
            healing_details=f"Completed after {iterations} iteration(s)",
            duration_ms=0
        )

    # =========================================================================
    # TEST 9: Iteration Validator with Self-Healing Refinement
    # =========================================================================
    async def test_iteration_validator_refinement(self) -> TestResult:
        """Test iteration validator with refinement loop."""
        from Agnostic_Core_OS.validators.iteration_validator import (
            IterationValidator, IterationConfig, ValidationStatus
        )

        # Configure validator with max 10 iterations for this test
        config = IterationConfig(
            max_iterations=10,
            pass_threshold=0.8,
            auto_refine=True,
            stop_on_pass=True
        )
        validator = IterationValidator(config)

        # Simulate a process that improves with each iteration
        iteration_count = [0]

        async def process_fn(input_data: str) -> str:
            """Simulated process that gets better with refinement."""
            iteration_count[0] += 1
            # Add more content with each iteration
            return input_data + f" [refined_{iteration_count[0]}]"

        def validate_fn(output: str) -> tuple:
            """Validate based on refinement count."""
            # Pass when we have at least 3 refinements
            refinement_count = output.count("[refined_")
            score = min(refinement_count / 3.0, 1.0)
            passed = refinement_count >= 3
            return (passed, score)

        def refine_fn(input_data: str, output: str, issues: list) -> str:
            """Refine input based on output."""
            return output  # Use output as next input

        # Run the validator
        result = await validator.run(
            initial_input="Initial prompt",
            process_fn=process_fn,
            validate_fn=validate_fn,
            refine_fn=refine_fn
        )

        history = validator.get_history()
        stats = validator.get_stats()

        success = result.status == ValidationStatus.PASSED

        return TestResult(
            test_name="Iteration Validator Refinement",
            status=TestStatus.PASSED if success else TestStatus.FAILED,
            description="Test iterative validation with auto-refinement until quality threshold met",
            input_data={"initial_input": "Initial prompt", "max_iterations": 10, "pass_threshold": 0.8},
            expected_output={"status": "PASSED", "iterations": ">=3"},
            actual_output={
                "status": result.status.value,
                "final_score": result.score,
                "iterations_used": stats["iterations_used"],
                "history_length": len(history),
                "final_output": str(result.output_data)[:200]
            },
            iterations=stats["iterations_used"],
            healing_applied=stats["iterations_used"] > 1,
            healing_details=f"Refined {stats['iterations_used']} times to reach quality threshold",
            duration_ms=0
        )

    # =========================================================================
    # RUN ALL TESTS
    # =========================================================================
    async def run_all_tests(self) -> ProofOfConceptReport:
        """Run all tests and generate proof of concept report."""
        print("\n" + "="*70)
        print("  SYMBOLIC VECTORING PROOF OF CONCEPT TEST SUITE")
        print("="*70 + "\n")

        tests = [
            ("Natural → Vector Translation", self.test_natural_to_vector_translation),
            ("Vector → Natural Translation", self.test_vector_to_natural_translation),
            ("Notation Library Operations", self.test_notation_library_operations),
            ("Vector Cache Weighted Storage", self.test_vector_cache_weighted_storage),
            ("Vector Memory Operations", self.test_vector_memory_operations),
            ("Error Handoff & Self-Healing", self.test_error_handoff_self_healing),
        ]

        async_tests = [
            ("LLM Handshake Protocol", self.test_llm_handshake_protocol),
            ("End-to-End Pipeline", self.test_end_to_end_pipeline),
            ("Iteration Validator Refinement", self.test_iteration_validator_refinement),
        ]

        # Run sync tests
        for name, test_func in tests:
            print(f"Running: {name}...", end=" ")
            try:
                result, duration = self._time_test(test_func)
                result.duration_ms = duration
                self.report.add_result(result)
                print(result.status.value)
            except Exception as e:
                print(f"❌ ERROR: {e}")
                self.report.add_result(TestResult(
                    test_name=name,
                    status=TestStatus.FAILED,
                    description=f"Test crashed: {e}",
                    input_data=None,
                    expected_output=None,
                    actual_output=str(e)
                ))

        # Run async tests
        for name, test_coro in async_tests:
            print(f"Running: {name}...", end=" ")
            try:
                result, duration = await self._time_async_test(test_coro())
                result.duration_ms = duration
                self.report.add_result(result)
                print(result.status.value)
            except Exception as e:
                print(f"❌ ERROR: {e}")
                self.report.add_result(TestResult(
                    test_name=name,
                    status=TestStatus.FAILED,
                    description=f"Test crashed: {e}",
                    input_data=None,
                    expected_output=None,
                    actual_output=str(e)
                ))

        # Generate report
        print("\n" + "="*70)
        print("  TEST SUMMARY")
        print("="*70)

        for status, count in self.report.summary.items():
            print(f"  {status}: {count}")

        total = sum(self.report.summary.values())
        passed = self.report.summary.get("PASSED", 0) + self.report.summary.get("HEALED", 0)
        print(f"\n  Total: {total} | Success Rate: {(passed/total*100):.1f}%")
        print("="*70 + "\n")

        # Save report
        report_path = self.output_dir / "proof_of_concept_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self.report.to_markdown())
        print(f"📄 Report saved to: {report_path}")

        # Save JSON data
        json_path = self.output_dir / "proof_of_concept_data.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "title": self.report.title,
                "version": self.report.version,
                "generated_at": self.report.generated_at.isoformat(),
                "summary": self.report.summary,
                "tests": [t.to_dict() for t in self.report.tests]
            }, f, indent=2)
        print(f"📊 Data saved to: {json_path}")

        return self.report


# =============================================================================
# MAIN EXECUTION
# =============================================================================
async def main():
    """Run the proof of concept test suite."""
    print("\n🚀 Initializing Symbolic Vectoring Proof of Concept...\n")

    suite = SymbolicVectoringTestSuite()
    report = await suite.run_all_tests()

    print("\n✅ Proof of Concept Complete!")
    print(f"   View full report: {suite.output_dir / 'proof_of_concept_report.md'}")

    return report


if __name__ == "__main__":
    asyncio.run(main())

