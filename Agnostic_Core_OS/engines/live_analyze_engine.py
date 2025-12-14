"""
Live Analyze Engine - Real-Time Analysis and Flash Features

Features:
- Real-time analysis of image/audio streams
- Flash feature generation from vectors
- Sample replication (vector → media)
- Cross-engine collaboration via reference
- Usage reporting with full permissions
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
import json
import hashlib
import asyncio

if TYPE_CHECKING:
    from .image_engine import ImageEngine, ImageVector
    from .audio_engine import AudioEngine, AudioVector


class AnalysisMode(Enum):
    """Analysis modes."""
    REALTIME = "realtime"
    BATCH = "batch"
    STREAMING = "streaming"
    SNAPSHOT = "snapshot"


class FeatureType(Enum):
    """Flash feature types."""
    COLOR_PALETTE = "color_palette"
    COMPOSITION = "composition"
    MOTION = "motion"
    AUDIO_SPECTRUM = "audio_spectrum"
    RHYTHM = "rhythm"
    STYLE_TRANSFER = "style_transfer"
    SEMANTIC = "semantic"


class ReplicationMode(Enum):
    """Sample replication modes."""
    EXACT = "exact"
    VARIATION = "variation"
    INTERPOLATION = "interpolation"
    EXTRAPOLATION = "extrapolation"


@dataclass
class FlashFeature:
    """A flash feature extracted from analysis."""
    id: str
    feature_type: FeatureType
    source_vector: str
    values: List[float] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "feature_type": self.feature_type.value,
            "source_vector": self.source_vector,
            "values": self.values[:50],
            "labels": self.labels,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlashFeature":
        return cls(
            id=data["id"],
            feature_type=FeatureType(data["feature_type"]),
            source_vector=data["source_vector"],
            values=data.get("values", []),
            labels=data.get("labels", []),
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


@dataclass
class SampleReplication:
    """A sample replication request/result."""
    id: str
    source_vector: str
    mode: ReplicationMode
    target_path: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result_vector: str = ""
    similarity_to_source: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_vector": self.source_vector,
            "mode": self.mode.value,
            "target_path": self.target_path,
            "parameters": self.parameters,
            "status": self.status,
            "result_vector": self.result_vector,
            "similarity_to_source": self.similarity_to_source,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SampleReplication":
        return cls(
            id=data["id"],
            source_vector=data["source_vector"],
            mode=ReplicationMode(data["mode"]),
            target_path=data.get("target_path", ""),
            parameters=data.get("parameters", {}),
            status=data.get("status", "pending"),
            result_vector=data.get("result_vector", ""),
            similarity_to_source=data.get("similarity_to_source", 0.0),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )


@dataclass
class AnalysisReport:
    """Full analysis report with usage tracking."""
    id: str
    session_id: str
    mode: AnalysisMode
    vectors_analyzed: int = 0
    features_extracted: int = 0
    replications_completed: int = 0
    comparisons_made: int = 0
    total_processing_time_ms: float = 0.0
    permission_level: str = "full"
    features: List[FlashFeature] = field(default_factory=list)
    replications: List[SampleReplication] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "mode": self.mode.value,
            "vectors_analyzed": self.vectors_analyzed,
            "features_extracted": self.features_extracted,
            "replications_completed": self.replications_completed,
            "comparisons_made": self.comparisons_made,
            "total_processing_time_ms": self.total_processing_time_ms,
            "permission_level": self.permission_level,
            "features": [f.to_dict() for f in self.features],
            "replications": [r.to_dict() for r in self.replications],
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisReport":
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            mode=AnalysisMode(data["mode"]),
            vectors_analyzed=data.get("vectors_analyzed", 0),
            features_extracted=data.get("features_extracted", 0),
            replications_completed=data.get("replications_completed", 0),
            comparisons_made=data.get("comparisons_made", 0),
            total_processing_time_ms=data.get("total_processing_time_ms", 0.0),
            permission_level=data.get("permission_level", "full"),
            features=[FlashFeature.from_dict(f) for f in data.get("features", [])],
            replications=[SampleReplication.from_dict(r) for r in data.get("replications", [])],
            errors=data.get("errors", []),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


class LiveAnalyzeEngine:
    """
    Real-Time Analysis Engine for Flash Features and Sample Replication.

    Features:
    - Real-time analysis of vectors
    - Flash feature extraction
    - Sample replication (vector → media)
    - Cross-engine collaboration
    - Full permission usage reporting
    """

    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path
        self._features: Dict[str, FlashFeature] = {}
        self._replications: Dict[str, SampleReplication] = {}
        self._reports: Dict[str, AnalysisReport] = {}
        self._current_session: Optional[str] = None
        self._image_engine = None
        self._audio_engine = None

        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._data_file = storage_path / "live_analyze.json"
            self._load_data()
        else:
            self._data_file = None

    def _load_data(self) -> None:
        """Load data from storage."""
        if self._data_file and self._data_file.exists():
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for feat in data.get("features", []):
                    ff = FlashFeature.from_dict(feat)
                    self._features[ff.id] = ff
                for rep in data.get("replications", []):
                    sr = SampleReplication.from_dict(rep)
                    self._replications[sr.id] = sr
                for rep in data.get("reports", []):
                    ar = AnalysisReport.from_dict(rep)
                    self._reports[ar.id] = ar

    def _save_data(self) -> None:
        """Save data to storage."""
        if self._data_file:
            data = {
                "features": [f.to_dict() for f in self._features.values()],
                "replications": [r.to_dict() for r in self._replications.values()],
                "reports": [r.to_dict() for r in self._reports.values()],
            }
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def connect_engines(self, image_engine=None, audio_engine=None) -> None:
        """Connect image and audio engines for collaboration."""
        self._image_engine = image_engine
        self._audio_engine = audio_engine

    def start_session(self, mode: AnalysisMode = AnalysisMode.REALTIME) -> str:
        """Start a new analysis session."""
        session_id = hashlib.sha256(datetime.now().isoformat().encode()).hexdigest()[:12]
        self._current_session = session_id

        report = AnalysisReport(
            id=hashlib.sha256(f"report_{session_id}".encode()).hexdigest()[:12],
            session_id=session_id,
            mode=mode,
        )
        self._reports[report.id] = report
        self._save_data()
        return session_id

    def end_session(self) -> Optional[AnalysisReport]:
        """End current session and return report."""
        if not self._current_session:
            return None

        # Find report for session
        for report in self._reports.values():
            if report.session_id == self._current_session:
                self._current_session = None
                return report

        self._current_session = None
        return None

    def extract_flash_feature(
        self,
        vector_notation: str,
        feature_type: FeatureType,
    ) -> Optional[FlashFeature]:
        """Extract a flash feature from a vector."""
        start_time = datetime.now()

        # Try to find vector in connected engines
        source_data = None
        if self._image_engine:
            results = self._image_engine.query_by_notation(vector_notation)
            if results:
                source_data = results[0]

        if not source_data and self._audio_engine:
            results = self._audio_engine.query_by_notation(vector_notation)
            if results:
                source_data = results[0]

        # Generate feature based on type
        feature_id = hashlib.sha256(f"{vector_notation}{feature_type.value}".encode()).hexdigest()[:12]

        values = []
        labels = []

        if feature_type == FeatureType.COLOR_PALETTE:
            values = [0.2, 0.4, 0.6, 0.8, 1.0]  # Placeholder palette
            labels = ["primary", "secondary", "accent", "background", "text"]
        elif feature_type == FeatureType.COMPOSITION:
            values = [0.33, 0.5, 0.66]  # Rule of thirds
            labels = ["left_third", "center", "right_third"]
        elif feature_type == FeatureType.AUDIO_SPECTRUM:
            values = [0.1, 0.3, 0.5, 0.7, 0.4, 0.2, 0.1, 0.05]  # 8-band spectrum
            labels = ["sub", "bass", "low_mid", "mid", "high_mid", "presence", "brilliance", "air"]
        elif feature_type == FeatureType.RHYTHM:
            values = [120.0, 4.0, 0.8]  # BPM, time signature, swing
            labels = ["bpm", "time_sig", "swing"]
        elif feature_type == FeatureType.SEMANTIC:
            if source_data and hasattr(source_data, 'embedding'):
                values = source_data.embedding[:10]
            else:
                values = [0.0] * 10
            labels = [f"dim_{i}" for i in range(10)]

        feature = FlashFeature(
            id=feature_id,
            feature_type=feature_type,
            source_vector=vector_notation,
            values=values,
            labels=labels,
            confidence=0.85 if source_data else 0.5,
        )

        self._features[feature_id] = feature

        # Update session report
        self._update_session_report(
            features_extracted=1,
            processing_time=(datetime.now() - start_time).total_seconds() * 1000,
            feature=feature,
        )

        self._save_data()
        return feature

    def replicate_sample(
        self,
        source_vector: str,
        mode: ReplicationMode = ReplicationMode.EXACT,
        target_path: str = "",
        parameters: Dict[str, Any] = None,
    ) -> SampleReplication:
        """Replicate a sample from vector back to media."""
        start_time = datetime.now()

        rep_id = hashlib.sha256(f"{source_vector}{mode.value}{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        replication = SampleReplication(
            id=rep_id,
            source_vector=source_vector,
            mode=mode,
            target_path=target_path,
            parameters=parameters or {},
            status="processing",
        )

        # Simulate replication process
        # In real implementation, this would generate actual media
        if mode == ReplicationMode.EXACT:
            replication.similarity_to_source = 1.0
        elif mode == ReplicationMode.VARIATION:
            replication.similarity_to_source = 0.85
        elif mode == ReplicationMode.INTERPOLATION:
            replication.similarity_to_source = 0.7
        else:
            replication.similarity_to_source = 0.5

        replication.status = "completed"
        replication.completed_at = datetime.now()
        replication.result_vector = f"{source_vector}_REP_{rep_id[:4]}"

        self._replications[rep_id] = replication

        # Update session report
        self._update_session_report(
            replications_completed=1,
            processing_time=(datetime.now() - start_time).total_seconds() * 1000,
            replication=replication,
        )

        self._save_data()
        return replication

    async def analyze_stream(
        self,
        vector_stream: List[str],
        feature_types: List[FeatureType],
        callback: Optional[Callable[[FlashFeature], None]] = None,
    ) -> List[FlashFeature]:
        """Analyze a stream of vectors in real-time."""
        features = []

        for vector in vector_stream:
            for ftype in feature_types:
                feature = self.extract_flash_feature(vector, ftype)
                if feature:
                    features.append(feature)
                    if callback:
                        callback(feature)

            # Small delay for streaming simulation
            await asyncio.sleep(0.01)

        return features

    def _update_session_report(
        self,
        vectors_analyzed: int = 0,
        features_extracted: int = 0,
        replications_completed: int = 0,
        comparisons_made: int = 0,
        processing_time: float = 0.0,
        feature: FlashFeature = None,
        replication: SampleReplication = None,
    ) -> None:
        """Update current session report."""
        if not self._current_session:
            return

        for report in self._reports.values():
            if report.session_id == self._current_session:
                report.vectors_analyzed += vectors_analyzed
                report.features_extracted += features_extracted
                report.replications_completed += replications_completed
                report.comparisons_made += comparisons_made
                report.total_processing_time_ms += processing_time

                if feature:
                    report.features.append(feature)
                if replication:
                    report.replications.append(replication)
                break

    def get_session_report(self, session_id: str = None) -> Optional[AnalysisReport]:
        """Get report for a session."""
        target_session = session_id or self._current_session
        if not target_session:
            return None

        for report in self._reports.values():
            if report.session_id == target_session:
                return report
        return None

    def get_feature(self, feature_id: str) -> Optional[FlashFeature]:
        """Get a feature by ID."""
        return self._features.get(feature_id)

    def get_replication(self, rep_id: str) -> Optional[SampleReplication]:
        """Get a replication by ID."""
        return self._replications.get(rep_id)

    def list_features(self, feature_type: FeatureType = None) -> List[Dict[str, Any]]:
        """List all features."""
        features = self._features.values()
        if feature_type:
            features = [f for f in features if f.feature_type == feature_type]
        return [{"id": f.id, "type": f.feature_type.value, "source": f.source_vector} for f in features]

    def list_replications(self, status: str = None) -> List[Dict[str, Any]]:
        """List all replications."""
        reps = self._replications.values()
        if status:
            reps = [r for r in reps if r.status == status]
        return [{"id": r.id, "source": r.source_vector, "mode": r.mode.value, "status": r.status} for r in reps]

    def generate_usage_report(self, permission_level: str = "full") -> Dict[str, Any]:
        """Generate full usage report."""
        total_features = len(self._features)
        total_replications = len(self._replications)
        total_reports = len(self._reports)

        feature_breakdown = {}
        for f in self._features.values():
            ftype = f.feature_type.value
            feature_breakdown[ftype] = feature_breakdown.get(ftype, 0) + 1

        replication_breakdown = {}
        for r in self._replications.values():
            mode = r.mode.value
            replication_breakdown[mode] = replication_breakdown.get(mode, 0) + 1

        return {
            "permission_level": permission_level,
            "total_features": total_features,
            "total_replications": total_replications,
            "total_sessions": total_reports,
            "feature_breakdown": feature_breakdown,
            "replication_breakdown": replication_breakdown,
            "generated_at": datetime.now().isoformat(),
        }

    def export_for_training(self, output_path: Path) -> int:
        """Export as training data."""
        entries = []

        for feature in self._features.values():
            entries.append({
                "instruction": f"Extract {feature.feature_type.value} feature",
                "input": feature.source_vector,
                "output": json.dumps({"values": feature.values, "labels": feature.labels}),
            })

        for rep in self._replications.values():
            entries.append({
                "instruction": f"Replicate sample with {rep.mode.value} mode",
                "input": rep.source_vector,
                "output": rep.result_vector,
            })

        with open(output_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        return len(entries)


# Singleton accessor
_live_engine_instance: Optional[LiveAnalyzeEngine] = None


def get_live_engine(storage_path: Path = None) -> LiveAnalyzeEngine:
    """Get or create LiveAnalyzeEngine singleton."""
    global _live_engine_instance
    if _live_engine_instance is None:
        _live_engine_instance = LiveAnalyzeEngine(storage_path)
    return _live_engine_instance

