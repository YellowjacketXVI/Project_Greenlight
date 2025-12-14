"""
Comparison Learning System - Iterative Learning with Vectored Reports

Features:
- Image-to-image comparison learning analysis
- Audio-to-audio comparison learning
- Cross-modal comparison (image ↔ audio)
- Iterative learning with delta vectors
- Full permission usage reports
- Training data generation
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING
import json
import hashlib

if TYPE_CHECKING:
    from .image_engine import ImageEngine, ImageVector, ImageComparison
    from .audio_engine import AudioEngine, AudioVector, AudioComparison


class ComparisonType(Enum):
    """Types of comparisons."""
    IMAGE_TO_IMAGE = "image_to_image"
    AUDIO_TO_AUDIO = "audio_to_audio"
    IMAGE_TO_AUDIO = "image_to_audio"
    VECTOR_TO_VECTOR = "vector_to_vector"


class LearningPhase(Enum):
    """Learning iteration phases."""
    INITIAL = "initial"
    ANALYZING = "analyzing"
    COMPARING = "comparing"
    LEARNING = "learning"
    VALIDATING = "validating"
    COMPLETE = "complete"


@dataclass
class VectorDelta:
    """Delta between two vectors for learning."""
    id: str
    source_vector: str
    target_vector: str
    delta_values: List[float] = field(default_factory=list)
    magnitude: float = 0.0
    direction: str = ""
    semantic_shift: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_vector": self.source_vector,
            "target_vector": self.target_vector,
            "delta_values": self.delta_values[:50],
            "magnitude": self.magnitude,
            "direction": self.direction,
            "semantic_shift": self.semantic_shift,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorDelta":
        return cls(
            id=data["id"],
            source_vector=data["source_vector"],
            target_vector=data["target_vector"],
            delta_values=data.get("delta_values", []),
            magnitude=data.get("magnitude", 0.0),
            direction=data.get("direction", ""),
            semantic_shift=data.get("semantic_shift", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


@dataclass
class IterationResult:
    """Result of a learning iteration."""
    iteration: int
    phase: LearningPhase
    deltas_computed: int
    avg_magnitude: float
    convergence_score: float
    improvements: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "phase": self.phase.value,
            "deltas_computed": self.deltas_computed,
            "avg_magnitude": self.avg_magnitude,
            "convergence_score": self.convergence_score,
            "improvements": self.improvements,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IterationResult":
        return cls(
            iteration=data["iteration"],
            phase=LearningPhase(data["phase"]),
            deltas_computed=data.get("deltas_computed", 0),
            avg_magnitude=data.get("avg_magnitude", 0.0),
            convergence_score=data.get("convergence_score", 0.0),
            improvements=data.get("improvements", []),
            errors=data.get("errors", []),
            duration_ms=data.get("duration_ms", 0.0),
        )


@dataclass
class LearningReport:
    """Full learning report with usage tracking."""
    id: str
    comparison_type: ComparisonType
    source_count: int
    target_count: int
    total_iterations: int
    max_iterations: int
    final_convergence: float
    deltas: List[VectorDelta] = field(default_factory=list)
    iterations: List[IterationResult] = field(default_factory=list)
    permission_level: str = "full"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "comparison_type": self.comparison_type.value,
            "source_count": self.source_count,
            "target_count": self.target_count,
            "total_iterations": self.total_iterations,
            "max_iterations": self.max_iterations,
            "final_convergence": self.final_convergence,
            "deltas": [d.to_dict() for d in self.deltas],
            "iterations": [i.to_dict() for i in self.iterations],
            "permission_level": self.permission_level,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningReport":
        return cls(
            id=data["id"],
            comparison_type=ComparisonType(data["comparison_type"]),
            source_count=data.get("source_count", 0),
            target_count=data.get("target_count", 0),
            total_iterations=data.get("total_iterations", 0),
            max_iterations=data.get("max_iterations", 100),
            final_convergence=data.get("final_convergence", 0.0),
            deltas=[VectorDelta.from_dict(d) for d in data.get("deltas", [])],
            iterations=[IterationResult.from_dict(i) for i in data.get("iterations", [])],
            permission_level=data.get("permission_level", "full"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )


class ComparisonLearning:
    """
    Comparison Learning System for Iterative Vector Analysis.

    Features:
    - Image-to-image comparison learning
    - Audio-to-audio comparison learning
    - Cross-modal comparison
    - Iterative refinement (max 100 iterations)
    - Delta vector computation
    - Full permission usage reports
    """

    MAX_ITERATIONS = 100
    CONVERGENCE_THRESHOLD = 0.95

    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path
        self._deltas: Dict[str, VectorDelta] = {}
        self._reports: Dict[str, LearningReport] = {}
        self._image_engine = None
        self._audio_engine = None

        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._data_file = storage_path / "comparison_learning.json"
            self._load_data()
        else:
            self._data_file = None

    def _load_data(self) -> None:
        """Load data from storage."""
        if self._data_file and self._data_file.exists():
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for d in data.get("deltas", []):
                    delta = VectorDelta.from_dict(d)
                    self._deltas[delta.id] = delta
                for r in data.get("reports", []):
                    report = LearningReport.from_dict(r)
                    self._reports[report.id] = report

    def _save_data(self) -> None:
        """Save data to storage."""
        if self._data_file:
            data = {
                "deltas": [d.to_dict() for d in self._deltas.values()],
                "reports": [r.to_dict() for r in self._reports.values()],
            }
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def connect_engines(self, image_engine=None, audio_engine=None) -> None:
        """Connect image and audio engines."""
        self._image_engine = image_engine
        self._audio_engine = audio_engine

    def compute_delta(
        self,
        source_embedding: List[float],
        target_embedding: List[float],
        source_notation: str,
        target_notation: str,
    ) -> VectorDelta:
        """Compute delta between two embeddings."""
        min_len = min(len(source_embedding), len(target_embedding))

        delta_values = [
            target_embedding[i] - source_embedding[i]
            for i in range(min_len)
        ]

        # Compute magnitude
        magnitude = sum(d * d for d in delta_values) ** 0.5

        # Determine direction
        if magnitude < 0.1:
            direction = "stable"
        elif sum(delta_values) > 0:
            direction = "positive"
        else:
            direction = "negative"

        # Semantic shift description
        if magnitude < 0.1:
            semantic_shift = "minimal_change"
        elif magnitude < 0.5:
            semantic_shift = "subtle_shift"
        elif magnitude < 1.0:
            semantic_shift = "moderate_shift"
        else:
            semantic_shift = "significant_shift"

        delta_id = hashlib.sha256(f"{source_notation}{target_notation}".encode()).hexdigest()[:12]

        delta = VectorDelta(
            id=delta_id,
            source_vector=source_notation,
            target_vector=target_notation,
            delta_values=delta_values[:50],
            magnitude=magnitude,
            direction=direction,
            semantic_shift=semantic_shift,
        )

        self._deltas[delta_id] = delta
        self._save_data()
        return delta

    def learn_from_comparisons(
        self,
        source_vectors: List[Tuple[str, List[float]]],
        target_vectors: List[Tuple[str, List[float]]],
        comparison_type: ComparisonType = ComparisonType.VECTOR_TO_VECTOR,
        max_iterations: int = None,
    ) -> LearningReport:
        """
        Learn from comparing source and target vectors.

        Args:
            source_vectors: List of (notation, embedding) tuples
            target_vectors: List of (notation, embedding) tuples
            comparison_type: Type of comparison
            max_iterations: Max iterations (default: 100)

        Returns:
            LearningReport with all iterations and deltas
        """
        max_iter = min(max_iterations or self.MAX_ITERATIONS, self.MAX_ITERATIONS)

        report_id = hashlib.sha256(datetime.now().isoformat().encode()).hexdigest()[:12]

        report = LearningReport(
            id=report_id,
            comparison_type=comparison_type,
            source_count=len(source_vectors),
            target_count=len(target_vectors),
            total_iterations=0,
            max_iterations=max_iter,
            final_convergence=0.0,
        )

        convergence = 0.0
        iteration = 0

        while iteration < max_iter and convergence < self.CONVERGENCE_THRESHOLD:
            start_time = datetime.now()
            iteration += 1

            # Compute deltas for this iteration
            iteration_deltas = []
            total_magnitude = 0.0

            for src_notation, src_emb in source_vectors:
                for tgt_notation, tgt_emb in target_vectors:
                    delta = self.compute_delta(src_emb, tgt_emb, src_notation, tgt_notation)
                    iteration_deltas.append(delta)
                    total_magnitude += delta.magnitude

            avg_magnitude = total_magnitude / len(iteration_deltas) if iteration_deltas else 0.0

            # Update convergence based on magnitude reduction
            if iteration == 1:
                convergence = 0.1
            else:
                # Convergence increases as magnitude decreases
                convergence = min(1.0, convergence + (1.0 - avg_magnitude) * 0.1)

            # Determine phase
            if iteration == 1:
                phase = LearningPhase.INITIAL
            elif convergence < 0.3:
                phase = LearningPhase.ANALYZING
            elif convergence < 0.6:
                phase = LearningPhase.COMPARING
            elif convergence < 0.9:
                phase = LearningPhase.LEARNING
            elif convergence < self.CONVERGENCE_THRESHOLD:
                phase = LearningPhase.VALIDATING
            else:
                phase = LearningPhase.COMPLETE

            duration = (datetime.now() - start_time).total_seconds() * 1000

            iter_result = IterationResult(
                iteration=iteration,
                phase=phase,
                deltas_computed=len(iteration_deltas),
                avg_magnitude=avg_magnitude,
                convergence_score=convergence,
                improvements=[f"Processed {len(iteration_deltas)} comparisons"],
                duration_ms=duration,
            )

            report.iterations.append(iter_result)
            report.deltas.extend(iteration_deltas)

        report.total_iterations = iteration
        report.final_convergence = convergence
        report.completed_at = datetime.now()

        self._reports[report_id] = report
        self._save_data()
        return report

    def learn_images(
        self,
        source_ids: List[str],
        target_ids: List[str],
    ) -> Optional[LearningReport]:
        """Learn from image comparisons using connected image engine."""
        if not self._image_engine:
            return None

        source_vectors = []
        target_vectors = []

        for sid in source_ids:
            vec = self._image_engine.get_vector(sid)
            if vec:
                source_vectors.append((vec.vector_notation, vec.embedding))

        for tid in target_ids:
            vec = self._image_engine.get_vector(tid)
            if vec:
                target_vectors.append((vec.vector_notation, vec.embedding))

        if not source_vectors or not target_vectors:
            return None

        return self.learn_from_comparisons(
            source_vectors,
            target_vectors,
            ComparisonType.IMAGE_TO_IMAGE,
        )

    def learn_audio(
        self,
        source_ids: List[str],
        target_ids: List[str],
    ) -> Optional[LearningReport]:
        """Learn from audio comparisons using connected audio engine."""
        if not self._audio_engine:
            return None

        source_vectors = []
        target_vectors = []

        for sid in source_ids:
            vec = self._audio_engine.get_vector(sid)
            if vec:
                source_vectors.append((vec.vector_notation, vec.embedding))

        for tid in target_ids:
            vec = self._audio_engine.get_vector(tid)
            if vec:
                target_vectors.append((vec.vector_notation, vec.embedding))

        if not source_vectors or not target_vectors:
            return None

        return self.learn_from_comparisons(
            source_vectors,
            target_vectors,
            ComparisonType.AUDIO_TO_AUDIO,
        )

    def learn_cross_modal(
        self,
        image_ids: List[str],
        audio_ids: List[str],
    ) -> Optional[LearningReport]:
        """Learn from cross-modal (image ↔ audio) comparisons."""
        if not self._image_engine or not self._audio_engine:
            return None

        image_vectors = []
        audio_vectors = []

        for iid in image_ids:
            vec = self._image_engine.get_vector(iid)
            if vec:
                image_vectors.append((vec.vector_notation, vec.embedding))

        for aid in audio_ids:
            vec = self._audio_engine.get_vector(aid)
            if vec:
                audio_vectors.append((vec.vector_notation, vec.embedding))

        if not image_vectors or not audio_vectors:
            return None

        return self.learn_from_comparisons(
            image_vectors,
            audio_vectors,
            ComparisonType.IMAGE_TO_AUDIO,
        )

    def get_report(self, report_id: str) -> Optional[LearningReport]:
        """Get a learning report by ID."""
        return self._reports.get(report_id)

    def get_delta(self, delta_id: str) -> Optional[VectorDelta]:
        """Get a delta by ID."""
        return self._deltas.get(delta_id)

    def list_reports(self) -> List[Dict[str, Any]]:
        """List all reports."""
        return [
            {
                "id": r.id,
                "type": r.comparison_type.value,
                "iterations": r.total_iterations,
                "convergence": r.final_convergence,
            }
            for r in self._reports.values()
        ]

    def generate_usage_report(self, permission_level: str = "full") -> Dict[str, Any]:
        """Generate full usage report."""
        total_deltas = len(self._deltas)
        total_reports = len(self._reports)

        type_breakdown = {}
        for r in self._reports.values():
            ctype = r.comparison_type.value
            type_breakdown[ctype] = type_breakdown.get(ctype, 0) + 1

        avg_convergence = 0.0
        if self._reports:
            avg_convergence = sum(r.final_convergence for r in self._reports.values()) / len(self._reports)

        return {
            "permission_level": permission_level,
            "total_deltas": total_deltas,
            "total_reports": total_reports,
            "type_breakdown": type_breakdown,
            "avg_convergence": avg_convergence,
            "generated_at": datetime.now().isoformat(),
        }

    def export_for_training(self, output_path: Path) -> int:
        """Export as training data."""
        entries = []

        for delta in self._deltas.values():
            entries.append({
                "instruction": f"Compute delta from {delta.source_vector} to {delta.target_vector}",
                "input": json.dumps({"source": delta.source_vector, "target": delta.target_vector}),
                "output": json.dumps({
                    "magnitude": delta.magnitude,
                    "direction": delta.direction,
                    "semantic_shift": delta.semantic_shift,
                }),
            })

        for report in self._reports.values():
            entries.append({
                "instruction": f"Learn from {report.comparison_type.value} comparison",
                "input": json.dumps({"sources": report.source_count, "targets": report.target_count}),
                "output": json.dumps({
                    "iterations": report.total_iterations,
                    "convergence": report.final_convergence,
                }),
            })

        with open(output_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        return len(entries)

