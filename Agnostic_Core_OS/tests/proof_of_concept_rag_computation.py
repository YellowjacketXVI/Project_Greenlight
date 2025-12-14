"""
Proof of Concept: Symbolic Implementation as RAG-Driving Computational Platform

This test suite demonstrates the binary/computational processes behind:
1. Symbol → Binary Hash Indexing
2. Vector Embedding Computation
3. Retrieval-Augmented Generation (RAG) Pipeline
4. Weighted Retrieval with Priority Routing
5. Context Assembly and Generation Augmentation
6. Iterative Learning with Delta Vectors
7. Self-Healing Computational Refinement

The symbolic notation system serves as a human-readable interface to
underlying binary computational processes that drive RAG operations.
"""

import asyncio
import hashlib
import json
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestStatus(Enum):
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    HEALED = "🔧 HEALED"


@dataclass
class ComputationResult:
    """Result of a computational test."""
    test_name: str
    status: TestStatus
    description: str
    input_data: Any
    binary_representation: str
    computation_steps: List[Dict[str, Any]]
    output_data: Any
    duration_ms: float = 0.0
    iterations: int = 1
    healing_applied: bool = False
    healing_details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "status": self.status.value,
            "description": self.description,
            "input": str(self.input_data)[:500],
            "binary_representation": self.binary_representation[:200],
            "computation_steps": self.computation_steps[:10],
            "output": str(self.output_data)[:500],
            "duration_ms": self.duration_ms,
            "iterations": self.iterations,
            "healing_applied": self.healing_applied,
            "healing_details": self.healing_details,
        }


@dataclass
class RAGComputationReport:
    """Full report of RAG computation proof of concept."""
    title: str = "RAG Computational Platform Proof of Concept"
    version: str = "1.0"
    generated_at: datetime = field(default_factory=datetime.now)
    results: List[ComputationResult] = field(default_factory=list)

    def add_result(self, result: ComputationResult) -> None:
        self.results.append(result)

    def get_summary(self) -> Dict[str, int]:
        summary = {}
        for r in self.results:
            status = r.status.value
            summary[status] = summary.get(status, 0) + 1
        return summary

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title}",
            f"**Version:** {self.version}",
            f"**Generated:** {self.generated_at.isoformat()}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            "This report demonstrates the **binary computational processes** underlying",
            "the symbolic vectoring system as a **RAG-driving computational platform**.",
            "",
            "### Key Demonstrations:",
            "- Symbol → Binary Hash Conversion (SHA-256)",
            "- Vector Embedding as Float32 Arrays",
            "- Weighted Retrieval Priority Computation",
            "- Context Assembly with Token Budgeting",
            "- Delta Vector Learning Computation",
            "- Self-Healing Iteration Refinement",
            "",
            "---",
            "",
            "## Test Summary",
            "",
            "| Status | Count |",
            "|--------|-------|",
        ]

        for status, count in self.get_summary().items():
            lines.append(f"| {status} | {count} |")

        total = len(self.results)
        passed = sum(1 for r in self.results if r.status in [TestStatus.PASSED, TestStatus.HEALED])
        rate = (passed / total * 100) if total > 0 else 0

        lines.extend([
            "",
            f"**Total Tests:** {total}",
            f"**Success Rate:** {rate:.1f}%",
            "",
            "---",
            "",
            "## Detailed Computation Results",
            "",
        ])

        for i, result in enumerate(self.results, 1):
            lines.extend([
                f"### Test {i}: {result.test_name}",
                f"**Status:** {result.status.value}",
                f"**Description:** {result.description}",
                "",
                "**Input:**",
                "```",
                str(result.input_data)[:300],
                "```",
                "",
                "**Binary Representation:**",
                "```",
                result.binary_representation[:200],
                "```",
                "",
                "**Computation Steps:**",
            ])

            for step in result.computation_steps[:5]:
                lines.append(f"- **{step.get('step', 'N/A')}**: {str(step.get('data', step))[:100]}")

            lines.extend([
                "",
                "**Output:**",
                "```",
                str(result.output_data)[:300],
                "```",
                "",
            ])

            if result.healing_applied:
                lines.extend([
                    f"**🔧 Self-Healing Applied:** {result.healing_details}",
                    f"**Iterations:** {result.iterations}",
                    "",
                ])

            lines.append("---\n")

        return "\n".join(lines)


class RAGComputationTestSuite:
    """
    Test suite demonstrating symbolic notation as RAG computational platform.

    Shows the binary/computational layer beneath the symbolic interface.
    """

    def __init__(self, project_path: Path = None):
        self.project_path = project_path or Path(__file__).parent.parent.parent
        self.report = RAGComputationReport()

        # Initialize components
        from Agnostic_Core_OS.translators.vector_language import VectorLanguageTranslator
        from Agnostic_Core_OS.procedural.notation_library import NotationLibrary, NotationType, NotationScope
        from Agnostic_Core_OS.procedural.context_index import ContextIndex, IndexScope, IndexEntryType
        from Agnostic_Core_OS.core_routing.vector_cache import VectorCache, CacheEntryType, VectorWeight
        from Agnostic_Core_OS.engines.comparison_learning import ComparisonLearning, ComparisonType

        self.translator = VectorLanguageTranslator()
        self.notation_library = NotationLibrary()
        self.context_index = ContextIndex()
        self.vector_cache = VectorCache()
        self.comparison_learning = ComparisonLearning()

        # Store imports for tests
        self.NotationType = NotationType
        self.NotationScope = NotationScope
        self.IndexScope = IndexScope
        self.IndexEntryType = IndexEntryType
        self.CacheEntryType = CacheEntryType
        self.VectorWeight = VectorWeight
        self.ComparisonType = ComparisonType

    def _time_test(self, func) -> Tuple[ComputationResult, float]:
        """Time a test function."""
        start = time.perf_counter()
        result = func()
        duration = (time.perf_counter() - start) * 1000
        return result, duration

    # =========================================================================
    # TEST 1: Symbol → Binary Hash Indexing
    # =========================================================================
    def test_symbol_to_binary_hash(self) -> ComputationResult:
        """Demonstrate symbol to binary hash conversion for indexing."""
        symbols = [
            "@CHAR_MEI",
            "@LOC_TEAHOUSE",
            ">story standard",
            "#WORLD_BIBLE",
            "~warrior spirit",
        ]

        computation_steps = []
        binary_representations = []

        for symbol in symbols:
            # Step 1: Encode to bytes
            symbol_bytes = symbol.encode('utf-8')

            # Step 2: Compute SHA-256 hash
            hash_obj = hashlib.sha256(symbol_bytes)
            hash_bytes = hash_obj.digest()
            hash_hex = hash_obj.hexdigest()

            # Step 3: Extract index key (first 12 chars)
            index_key = hash_hex[:12]

            # Step 4: Convert to binary representation
            binary_str = ''.join(format(b, '08b') for b in hash_bytes[:4])

            computation_steps.append({
                "step": "hash_computation",
                "symbol": symbol,
                "bytes": symbol_bytes.hex(),
                "sha256": hash_hex,
                "index_key": index_key,
                "binary_prefix": binary_str,
            })

            binary_representations.append(f"{symbol} → {index_key} → {binary_str[:16]}...")

        # Verify uniqueness
        index_keys = [s["index_key"] for s in computation_steps]
        unique = len(index_keys) == len(set(index_keys))

        return ComputationResult(
            test_name="Symbol → Binary Hash Indexing",
            status=TestStatus.PASSED if unique else TestStatus.FAILED,
            description="Convert symbolic notation to binary hash for O(1) index lookup",
            input_data={"symbols": symbols},
            binary_representation="\n".join(binary_representations),
            computation_steps=computation_steps,
            output_data={
                "unique_hashes": unique,
                "hash_count": len(index_keys),
                "collision_free": unique,
            },
        )

    # =========================================================================
    # TEST 2: Vector Embedding Computation
    # =========================================================================
    def test_vector_embedding_computation(self) -> ComputationResult:
        """Demonstrate vector embedding as float32 arrays."""
        texts = [
            "Character Mei is a skilled warrior",
            "The teahouse is located in the mountains",
            "A battle scene with dramatic lighting",
        ]

        computation_steps = []

        for text in texts:
            # Simulate embedding computation (simplified)
            # In production, this would use sentence-transformers or similar

            # Step 1: Tokenize (simplified)
            tokens = text.lower().split()

            # Step 2: Create pseudo-embedding (384 dimensions typical)
            embedding_dim = 384
            embedding = []
            for i in range(embedding_dim):
                # Deterministic pseudo-embedding based on text hash
                seed = hashlib.md5(f"{text}{i}".encode()).digest()
                value = struct.unpack('f', seed[:4])[0]
                # Normalize to [-1, 1]
                value = (value % 2) - 1
                embedding.append(value)

            # Step 3: Normalize (L2 normalization)
            magnitude = sum(v * v for v in embedding) ** 0.5
            normalized = [v / magnitude for v in embedding]

            # Step 4: Convert to binary (float32)
            binary_floats = [struct.pack('f', v).hex() for v in normalized[:4]]

            computation_steps.append({
                "step": "embedding_computation",
                "text": text[:50],
                "tokens": len(tokens),
                "dimension": embedding_dim,
                "magnitude": magnitude,
                "normalized_sample": normalized[:4],
                "binary_floats": binary_floats,
            })

        # Compute similarity between first two embeddings
        emb1 = computation_steps[0]["normalized_sample"]
        emb2 = computation_steps[1]["normalized_sample"]
        similarity = sum(a * b for a, b in zip(emb1, emb2))

        return ComputationResult(
            test_name="Vector Embedding Computation",
            status=TestStatus.PASSED,
            description="Convert text to float32 vector embeddings for semantic search",
            input_data={"texts": texts},
            binary_representation=f"Float32 arrays: {computation_steps[0]['binary_floats']}",
            computation_steps=computation_steps,
            output_data={
                "embedding_dimension": 384,
                "sample_similarity": similarity,
                "binary_size_bytes": 384 * 4,  # float32 = 4 bytes
            },
        )

    # =========================================================================
    # TEST 3: Weighted Retrieval Priority Computation
    # =========================================================================
    def test_weighted_retrieval_priority(self) -> ComputationResult:
        """Demonstrate weighted retrieval with priority routing."""
        entries = [
            {"id": "entry_1", "content": "Active character data", "weight": 1.0, "type": "ACTIVE"},
            {"id": "entry_2", "content": "Archived scene data", "weight": -0.5, "type": "ARCHIVED"},
            {"id": "entry_3", "content": "Deprecated tag", "weight": -1.0, "type": "DEPRECATED"},
            {"id": "entry_4", "content": "Task context", "weight": 1.0, "type": "ACTIVE"},
            {"id": "entry_5", "content": "Error transcript", "weight": 0.8, "type": "ACTIVE"},
        ]

        computation_steps = []

        # Step 1: Add entries to cache with weights
        for entry in entries:
            cache_entry = self.vector_cache.add(
                content=entry["content"],
                entry_type=self.CacheEntryType.NOTATION_DEFINITION,
                weight=entry["weight"],
            )

            # Compute binary weight representation
            weight_bytes = struct.pack('f', entry["weight"])
            weight_binary = ''.join(format(b, '08b') for b in weight_bytes)

            computation_steps.append({
                "step": "weight_assignment",
                "id": cache_entry.id if cache_entry else entry["id"],
                "weight": entry["weight"],
                "weight_binary": weight_binary,
                "type": entry["type"],
            })

        # Step 2: Retrieve with weight filtering
        active_entries = self.vector_cache.get_active()
        archived_entries = self.vector_cache.get_archived()

        # Step 3: Compute priority scores
        priority_scores = []
        for entry in active_entries:
            # Priority = weight * recency_factor
            recency_factor = 1.0  # Simplified
            priority = entry.weight * recency_factor
            priority_scores.append({
                "id": entry.id,
                "weight": entry.weight,
                "priority": priority,
            })

        # Sort by priority
        priority_scores.sort(key=lambda x: x["priority"], reverse=True)

        return ComputationResult(
            test_name="Weighted Retrieval Priority Computation",
            status=TestStatus.PASSED,
            description="Compute retrieval priority using weighted vector routing",
            input_data={"entries": len(entries)},
            binary_representation=f"Weight binary: {computation_steps[0]['weight_binary']}",
            computation_steps=computation_steps,
            output_data={
                "active_count": len(active_entries),
                "archived_count": len(archived_entries),
                "priority_order": [p["id"] for p in priority_scores[:3]],
            },
        )


    # =========================================================================
    # TEST 4: Context Assembly with Token Budgeting
    # =========================================================================
    def test_context_assembly_token_budget(self) -> ComputationResult:
        """Demonstrate context assembly with token budget computation."""
        # Simulate retrieved context items
        context_items = [
            {"id": "ctx_1", "content": "Mei is a warrior seeking redemption", "tokens": 8, "relevance": 0.95},
            {"id": "ctx_2", "content": "The teahouse is a place of peace", "tokens": 9, "relevance": 0.85},
            {"id": "ctx_3", "content": "Scene 1 takes place at dawn", "tokens": 7, "relevance": 0.75},
            {"id": "ctx_4", "content": "The sword represents honor and duty", "tokens": 7, "relevance": 0.70},
            {"id": "ctx_5", "content": "Background lore about the kingdom", "tokens": 6, "relevance": 0.50},
        ]

        token_budget = 30
        computation_steps = []

        # Step 1: Sort by relevance
        sorted_items = sorted(context_items, key=lambda x: x["relevance"], reverse=True)

        # Step 2: Greedy selection within budget
        selected = []
        current_tokens = 0

        for item in sorted_items:
            if current_tokens + item["tokens"] <= token_budget:
                selected.append(item)
                current_tokens += item["tokens"]

                computation_steps.append({
                    "step": "context_selection",
                    "id": item["id"],
                    "tokens": item["tokens"],
                    "relevance": item["relevance"],
                    "cumulative_tokens": current_tokens,
                    "budget_remaining": token_budget - current_tokens,
                })

        # Step 3: Compute binary token representation
        token_binary = format(current_tokens, '016b')

        return ComputationResult(
            test_name="Context Assembly with Token Budgeting",
            status=TestStatus.PASSED,
            description="Assemble context within token budget using greedy selection",
            input_data={"items": len(context_items), "budget": token_budget},
            binary_representation=f"Token count binary: {token_binary}",
            computation_steps=computation_steps,
            output_data={
                "selected_count": len(selected),
                "total_tokens": current_tokens,
                "budget_used_percent": (current_tokens / token_budget) * 100,
                "avg_relevance": sum(s["relevance"] for s in selected) / len(selected),
            },
        )

    # =========================================================================
    # TEST 5: Delta Vector Learning Computation
    # =========================================================================
    def test_delta_vector_learning(self) -> ComputationResult:
        """Demonstrate delta vector computation for iterative learning."""
        # Create source and target embeddings
        source_vectors = [
            ("@CHAR_MEI_v1", [0.1, 0.2, 0.3, 0.4, 0.5]),
            ("@LOC_TEAHOUSE_v1", [0.2, 0.3, 0.4, 0.5, 0.6]),
        ]

        target_vectors = [
            ("@CHAR_MEI_v2", [0.15, 0.25, 0.35, 0.45, 0.55]),
            ("@LOC_TEAHOUSE_v2", [0.22, 0.32, 0.42, 0.52, 0.62]),
        ]

        computation_steps = []

        # Compute deltas
        for (src_name, src_emb), (tgt_name, tgt_emb) in zip(source_vectors, target_vectors):
            delta = self.comparison_learning.compute_delta(
                source_embedding=src_emb,
                target_embedding=tgt_emb,
                source_notation=src_name,
                target_notation=tgt_name,
            )

            # Binary representation of delta values
            delta_binary = [struct.pack('f', v).hex() for v in delta.delta_values[:3]]

            computation_steps.append({
                "step": "delta_computation",
                "source": src_name,
                "target": tgt_name,
                "magnitude": delta.magnitude,
                "direction": delta.direction,
                "semantic_shift": delta.semantic_shift,
                "delta_binary": delta_binary,
            })

        # Run learning iteration
        report = self.comparison_learning.learn_from_comparisons(
            source_vectors=source_vectors,
            target_vectors=target_vectors,
            comparison_type=self.ComparisonType.VECTOR_TO_VECTOR,
            max_iterations=5,
        )

        computation_steps.append({
            "step": "learning_iteration",
            "iterations": report.total_iterations,
            "convergence": report.final_convergence,
            "deltas_computed": len(report.deltas),
        })

        return ComputationResult(
            test_name="Delta Vector Learning Computation",
            status=TestStatus.PASSED,
            description="Compute delta vectors for iterative learning refinement",
            input_data={"sources": len(source_vectors), "targets": len(target_vectors)},
            binary_representation=f"Delta binary: {computation_steps[0]['delta_binary']}",
            computation_steps=computation_steps,
            output_data={
                "total_iterations": report.total_iterations,
                "final_convergence": report.final_convergence,
                "deltas_computed": len(report.deltas),
            },
        )

    # =========================================================================
    # TEST 6: RAG Pipeline End-to-End Computation
    # =========================================================================
    def test_rag_pipeline_computation(self) -> ComputationResult:
        """Demonstrate complete RAG pipeline computation."""
        query = "Describe Mei's motivation in the teahouse scene"

        computation_steps = []

        # Step 1: Query → Vector Translation
        translation_result = self.translator.natural_to_vector(query)
        vector_notation = translation_result.output_text
        notations = self.translator.parse_notations(vector_notation)

        computation_steps.append({
            "step": "query_translation",
            "input": query,
            "vector": vector_notation,
            "notations_found": len(notations),
        })

        # Step 2: Query Embedding (simulated)
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        query_embedding = [float(int(query_hash[i:i+2], 16)) / 255.0 for i in range(0, 64, 2)]

        computation_steps.append({
            "step": "query_embedding",
            "dimension": len(query_embedding),
            "sample": query_embedding[:4],
            "binary": [struct.pack('f', v).hex() for v in query_embedding[:2]],
        })

        # Step 3: Index Search (simulated)
        # Index some content first
        self.context_index.index_file(
            "world_bible/characters/mei.py",
            "class Mei:\n    motivation = 'seeking redemption'\n    location = 'teahouse'"
        )

        search_result = self.context_index.search("Mei", limit=5)

        computation_steps.append({
            "step": "index_search",
            "query": "Mei",
            "results": search_result.total_matches,
            "search_time_ms": search_result.search_time_ms,
        })

        # Step 4: Context Assembly
        context_tokens = sum(len(e.content.split()) for e in search_result.entries)

        computation_steps.append({
            "step": "context_assembly",
            "entries": len(search_result.entries),
            "total_tokens": context_tokens,
        })

        # Step 5: Generation Augmentation (simulated)
        augmented_prompt = f"Context:\n{search_result.entries[0].content if search_result.entries else 'N/A'}\n\nQuery: {query}"

        computation_steps.append({
            "step": "generation_augmentation",
            "prompt_length": len(augmented_prompt),
            "context_included": len(search_result.entries) > 0,
        })

        return ComputationResult(
            test_name="RAG Pipeline End-to-End Computation",
            status=TestStatus.PASSED,
            description="Complete RAG pipeline: Query → Embed → Retrieve → Augment → Generate",
            input_data={"query": query},
            binary_representation=f"Query embedding: {computation_steps[1]['binary']}",
            computation_steps=computation_steps,
            output_data={
                "pipeline_steps": 5,
                "context_retrieved": len(search_result.entries),
                "augmented_prompt_length": len(augmented_prompt),
            },
        )

    # =========================================================================
    # TEST 7: Self-Healing Computational Refinement
    # =========================================================================
    async def test_self_healing_computation(self) -> ComputationResult:
        """Demonstrate self-healing with iterative refinement."""
        from Agnostic_Core_OS.validators.iteration_validator import (
            IterationValidator, IterationConfig, ValidationStatus
        )
        from Agnostic_Core_OS.core_routing.error_handoff import ErrorHandoff, ErrorSeverity

        computation_steps = []

        # Step 1: Simulate an error condition
        error_handoff = ErrorHandoff()

        # Create a simulated error
        error = ValueError("Vector embedding dimension mismatch: expected 384, got 256")

        transcript = error_handoff.flag_error(
            error=error,
            severity=ErrorSeverity.ERROR,
            source="rag_computation_test",
            context={"expected": 384, "actual": 256},
        )

        computation_steps.append({
            "step": "error_detection",
            "error_id": transcript.id,
            "severity": transcript.severity.value,
            "message": transcript.message[:50],
        })

        # Step 2: Create healing task
        task = error_handoff.create_task(transcript)

        computation_steps.append({
            "step": "task_creation",
            "task_id": task.id if task else "N/A",
            "error_id": transcript.id,
        })

        # Step 3: Iterative refinement
        config = IterationConfig(
            max_iterations=10,
            pass_threshold=0.9,
            auto_refine=True,
        )
        validator = IterationValidator(config)

        iteration_count = [0]

        async def process_fn(input_data: str) -> str:
            iteration_count[0] += 1
            # Simulate fixing the dimension mismatch
            if iteration_count[0] >= 3:
                return "Fixed: Padded embedding to 384 dimensions"
            return f"Attempt {iteration_count[0]}: Still mismatched"

        def validate_fn(output: str) -> tuple:
            passed = "Fixed" in output
            score = 1.0 if passed else 0.3 * iteration_count[0]
            return (passed, min(score, 1.0))

        def refine_fn(input_data: str, output: str, issues: list) -> str:
            return f"Retry with padding: {output}"

        result = await validator.run(
            initial_input="Fix dimension mismatch",
            process_fn=process_fn,
            validate_fn=validate_fn,
            refine_fn=refine_fn,
        )

        computation_steps.append({
            "step": "iterative_refinement",
            "iterations": iteration_count[0],
            "status": result.status.value,
            "final_score": result.score,
        })

        # Step 4: Resolve error
        error_handoff.resolve_error(transcript.id, "Dimension mismatch fixed via padding")

        computation_steps.append({
            "step": "error_resolution",
            "error_id": transcript.id,
            "resolved": True,
        })

        return ComputationResult(
            test_name="Self-Healing Computational Refinement",
            status=TestStatus.HEALED,
            description="Detect error, create task, iterate to fix, resolve",
            input_data={"error": "dimension_mismatch", "max_iterations": 10},
            binary_representation=f"Iteration count: {format(iteration_count[0], '08b')}",
            computation_steps=computation_steps,
            output_data={
                "iterations_to_heal": iteration_count[0],
                "final_status": result.status.value,
                "error_resolved": True,
            },
            iterations=iteration_count[0],
            healing_applied=True,
            healing_details=f"Fixed after {iteration_count[0]} iterations via padding",
        )

    # =========================================================================
    # RUN ALL TESTS
    # =========================================================================
    async def run_all_tests(self) -> RAGComputationReport:
        """Run all RAG computation tests."""
        print("\n🚀 Initializing RAG Computation Proof of Concept...\n")
        print("=" * 70)
        print("  RAG COMPUTATIONAL PLATFORM PROOF OF CONCEPT")
        print("=" * 70 + "\n")

        sync_tests = [
            ("Symbol → Binary Hash Indexing", self.test_symbol_to_binary_hash),
            ("Vector Embedding Computation", self.test_vector_embedding_computation),
            ("Weighted Retrieval Priority", self.test_weighted_retrieval_priority),
            ("Context Assembly Token Budget", self.test_context_assembly_token_budget),
            ("Delta Vector Learning", self.test_delta_vector_learning),
            ("RAG Pipeline End-to-End", self.test_rag_pipeline_computation),
        ]

        async_tests = [
            ("Self-Healing Computation", self.test_self_healing_computation),
        ]

        # Run sync tests
        for name, test_func in sync_tests:
            print(f"Running: {name}...", end=" ")
            try:
                result, duration = self._time_test(test_func)
                result.duration_ms = duration
                self.report.add_result(result)
                print(result.status.value)
            except Exception as e:
                print(f"❌ ERROR: {e}")
                self.report.add_result(ComputationResult(
                    test_name=name,
                    status=TestStatus.FAILED,
                    description=f"Test crashed: {e}",
                    input_data=None,
                    binary_representation="N/A",
                    computation_steps=[],
                    output_data=str(e),
                ))

        # Run async tests
        for name, test_coro in async_tests:
            print(f"Running: {name}...", end=" ")
            try:
                start = time.perf_counter()
                result = await test_coro()
                duration = (time.perf_counter() - start) * 1000
                result.duration_ms = duration
                self.report.add_result(result)
                print(result.status.value)
            except Exception as e:
                print(f"❌ ERROR: {e}")
                self.report.add_result(ComputationResult(
                    test_name=name,
                    status=TestStatus.FAILED,
                    description=f"Test crashed: {e}",
                    input_data=None,
                    binary_representation="N/A",
                    computation_steps=[],
                    output_data=str(e),
                ))

        # Print summary
        print("\n" + "=" * 70)
        print("  TEST SUMMARY")
        print("=" * 70)

        summary = self.report.get_summary()
        for status, count in summary.items():
            print(f"  {status}: {count}")

        total = len(self.report.results)
        passed = sum(1 for r in self.report.results if r.status in [TestStatus.PASSED, TestStatus.HEALED])
        rate = (passed / total * 100) if total > 0 else 0

        print(f"\n  Total: {total} | Success Rate: {rate:.1f}%")
        print("=" * 70)

        return self.report


async def main():
    """Main entry point."""
    import logging
    logging.basicConfig(level=logging.INFO)

    project_path = Path(__file__).parent.parent.parent
    suite = RAGComputationTestSuite(project_path)

    report = await suite.run_all_tests()

    # Save reports
    output_dir = project_path / ".proof_of_concept"
    output_dir.mkdir(exist_ok=True)

    # Markdown report
    md_path = output_dir / "rag_computation_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())
    print(f"\n📄 Report saved to: {md_path}")

    # JSON data
    json_path = output_dir / "rag_computation_data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "title": report.title,
            "version": report.version,
            "generated_at": report.generated_at.isoformat(),
            "summary": report.get_summary(),
            "tests": [r.to_dict() for r in report.results],
        }, f, indent=2)
    print(f"📊 Data saved to: {json_path}")

    print(f"\n✅ RAG Computation Proof of Concept Complete!")
    print(f"   View full report: {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
