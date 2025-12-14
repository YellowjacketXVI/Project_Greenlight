"""
Audio Engine - Audio-to-Vector Notation Processing

Features:
- Audio to vector notation translation
- Waveform analysis and feature extraction
- Audio comparison learning
- Reference audio collaboration across engines
- Sample replication support
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json
import hashlib
import struct


class AudioFormat(Enum):
    """Supported audio formats."""
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"
    OGG = "ogg"
    AAC = "aac"


class AudioType(Enum):
    """Audio classification types."""
    REFERENCE = "reference"
    DIALOGUE = "dialogue"
    MUSIC = "music"
    SFX = "sfx"
    AMBIENT = "ambient"
    VOICEOVER = "voiceover"
    SAMPLE = "sample"


@dataclass
class WaveformData:
    """Waveform representation of audio."""
    sample_rate: int
    channels: int
    duration_seconds: float
    bit_depth: int
    peak_amplitude: float
    rms_level: float
    frequency_bands: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "duration_seconds": self.duration_seconds,
            "bit_depth": self.bit_depth,
            "peak_amplitude": self.peak_amplitude,
            "rms_level": self.rms_level,
            "frequency_bands": self.frequency_bands,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WaveformData":
        return cls(
            sample_rate=data["sample_rate"],
            channels=data["channels"],
            duration_seconds=data["duration_seconds"],
            bit_depth=data["bit_depth"],
            peak_amplitude=data["peak_amplitude"],
            rms_level=data["rms_level"],
            frequency_bands=data.get("frequency_bands", []),
        )


@dataclass
class AudioVector:
    """Vector representation of audio."""
    id: str
    source_path: str
    vector_notation: str
    audio_type: AudioType
    audio_format: AudioFormat
    waveform: WaveformData
    embedding: List[float] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    transcript: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    checksum: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_path": self.source_path,
            "vector_notation": self.vector_notation,
            "audio_type": self.audio_type.value,
            "audio_format": self.audio_format.value,
            "waveform": self.waveform.to_dict(),
            "embedding": self.embedding[:100],
            "tags": self.tags,
            "transcript": self.transcript,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "checksum": self.checksum,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioVector":
        return cls(
            id=data["id"],
            source_path=data["source_path"],
            vector_notation=data["vector_notation"],
            audio_type=AudioType(data["audio_type"]),
            audio_format=AudioFormat(data.get("audio_format", "wav")),
            waveform=WaveformData.from_dict(data["waveform"]),
            embedding=data.get("embedding", []),
            tags=data.get("tags", []),
            transcript=data.get("transcript", ""),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            checksum=data.get("checksum", ""),
        )


@dataclass
class AudioComparison:
    """Comparison result between two audio files."""
    id: str
    source_id: str
    target_id: str
    similarity_score: float
    spectral_similarity: float
    temporal_similarity: float
    rhythm_match: float
    delta_vector: List[float] = field(default_factory=list)
    analysis_notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "similarity_score": self.similarity_score,
            "spectral_similarity": self.spectral_similarity,
            "temporal_similarity": self.temporal_similarity,
            "rhythm_match": self.rhythm_match,
            "delta_vector": self.delta_vector[:50],
            "analysis_notes": self.analysis_notes,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioComparison":
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            similarity_score=data["similarity_score"],
            spectral_similarity=data["spectral_similarity"],
            temporal_similarity=data["temporal_similarity"],
            rhythm_match=data["rhythm_match"],
            delta_vector=data.get("delta_vector", []),
            analysis_notes=data.get("analysis_notes", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


class AudioEngine:
    """
    Audio-to-Vector Translation Engine.

    Features:
    - Load audio and convert to vector notation
    - Waveform analysis and feature extraction
    - Audio comparison with learning analysis
    - Sample replication support
    - Reference audio collaboration
    """

    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path
        self._vectors: Dict[str, AudioVector] = {}
        self._comparisons: Dict[str, AudioComparison] = {}
        self._reference_audio: Optional[AudioVector] = None

        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._vectors_file = storage_path / "audio_vectors.json"
            self._load_vectors()
        else:
            self._vectors_file = None

    def _load_vectors(self) -> None:
        """Load vectors from storage."""
        if self._vectors_file and self._vectors_file.exists():
            with open(self._vectors_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for v in data.get("vectors", []):
                    vec = AudioVector.from_dict(v)
                    self._vectors[vec.id] = vec
                for c in data.get("comparisons", []):
                    comp = AudioComparison.from_dict(c)
                    self._comparisons[comp.id] = comp

    def _save_vectors(self) -> None:
        """Save vectors to storage."""
        if self._vectors_file:
            data = {
                "vectors": [v.to_dict() for v in self._vectors.values()],
                "comparisons": [c.to_dict() for c in self._comparisons.values()],
            }
            with open(self._vectors_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def vectorize_audio(
        self,
        audio_path: Path,
        audio_type: AudioType = AudioType.REFERENCE,
        tags: List[str] = None,
        transcript: str = "",
    ) -> AudioVector:
        """Convert audio to vector notation."""
        path_str = str(audio_path)
        vector_id = hashlib.sha256(path_str.encode()).hexdigest()[:12]

        # Detect format
        suffix = audio_path.suffix.lower().lstrip(".")
        try:
            audio_format = AudioFormat(suffix)
        except ValueError:
            audio_format = AudioFormat.WAV

        # Analyze waveform
        waveform = self._analyze_waveform(audio_path)

        # Generate vector notation
        type_prefix = audio_type.value.upper()
        tag_str = "_".join(tags[:3]) if tags else "UNNAMED"
        vector_notation = f"@AUD_{type_prefix}_{tag_str}_{vector_id[:6]}"

        # Generate embedding
        embedding = self._generate_embedding(audio_path, waveform)

        # Compute checksum
        checksum = self._compute_checksum(audio_path)

        vector = AudioVector(
            id=vector_id,
            source_path=path_str,
            vector_notation=vector_notation,
            audio_type=audio_type,
            audio_format=audio_format,
            waveform=waveform,
            embedding=embedding,
            tags=tags or [],
            transcript=transcript,
            checksum=checksum,
        )

        self._vectors[vector_id] = vector
        self._save_vectors()
        return vector

    def _analyze_waveform(self, path: Path) -> WaveformData:
        """Analyze audio waveform (basic implementation)."""
        try:
            with open(path, "rb") as f:
                header = f.read(44)  # WAV header

                if header[:4] == b'RIFF' and header[8:12] == b'WAVE':
                    # Parse WAV header
                    channels = struct.unpack("<H", header[22:24])[0]
                    sample_rate = struct.unpack("<I", header[24:28])[0]
                    bit_depth = struct.unpack("<H", header[34:36])[0]
                    data_size = struct.unpack("<I", header[40:44])[0]

                    bytes_per_sample = bit_depth // 8
                    total_samples = data_size // (bytes_per_sample * channels)
                    duration = total_samples / sample_rate if sample_rate > 0 else 0

                    # Read some samples for analysis
                    samples = f.read(min(data_size, 8192))
                    peak = 0.0
                    rms_sum = 0.0
                    sample_count = 0

                    for i in range(0, len(samples) - bytes_per_sample, bytes_per_sample):
                        if bytes_per_sample == 2:
                            val = struct.unpack("<h", samples[i:i+2])[0] / 32768.0
                        else:
                            val = samples[i] / 128.0 - 1.0
                        peak = max(peak, abs(val))
                        rms_sum += val * val
                        sample_count += 1

                    rms = (rms_sum / sample_count) ** 0.5 if sample_count > 0 else 0.0

                    return WaveformData(
                        sample_rate=sample_rate,
                        channels=channels,
                        duration_seconds=duration,
                        bit_depth=bit_depth,
                        peak_amplitude=peak,
                        rms_level=rms,
                        frequency_bands=[0.0] * 8,  # Placeholder
                    )
        except Exception:
            pass

        # Default for non-WAV or errors
        return WaveformData(
            sample_rate=44100,
            channels=2,
            duration_seconds=0.0,
            bit_depth=16,
            peak_amplitude=0.0,
            rms_level=0.0,
        )

    def _generate_embedding(self, path: Path, waveform: WaveformData) -> List[float]:
        """Generate audio embedding."""
        try:
            with open(path, "rb") as f:
                f.seek(44)  # Skip header
                data = f.read(4096)

                embedding = []
                for i in range(0, min(len(data), 256), 2):
                    if i + 2 <= len(data):
                        val = struct.unpack("<h", data[i:i+2])[0] / 32768.0
                        embedding.append(val)

                # Pad to 128 dimensions
                while len(embedding) < 128:
                    embedding.append(0.0)

                return embedding[:128]
        except Exception:
            return [0.0] * 128

    def _compute_checksum(self, path: Path) -> str:
        """Compute file checksum."""
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except Exception:
            return ""

    def compare_audio(self, source_id: str, target_id: str) -> Optional[AudioComparison]:
        """Compare two audio files."""
        source = self._vectors.get(source_id)
        target = self._vectors.get(target_id)

        if not source or not target:
            return None

        similarity = self._compute_similarity(source.embedding, target.embedding)
        spectral = self._compute_spectral_similarity(source, target)
        temporal = self._compute_temporal_similarity(source, target)
        rhythm = (spectral + temporal) / 2

        delta = [t - s for s, t in zip(source.embedding[:50], target.embedding[:50])]

        comp_id = hashlib.sha256(f"{source_id}{target_id}".encode()).hexdigest()[:12]

        comparison = AudioComparison(
            id=comp_id,
            source_id=source_id,
            target_id=target_id,
            similarity_score=similarity,
            spectral_similarity=spectral,
            temporal_similarity=temporal,
            rhythm_match=rhythm,
            delta_vector=delta,
            analysis_notes=f"Compared {source.vector_notation} to {target.vector_notation}",
        )

        self._comparisons[comp_id] = comparison
        self._save_vectors()
        return comparison

    def _compute_similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Compute cosine similarity."""
        if not emb1 or not emb2:
            return 0.0

        min_len = min(len(emb1), len(emb2))
        dot = sum(a * b for a, b in zip(emb1[:min_len], emb2[:min_len]))
        norm1 = sum(a * a for a in emb1[:min_len]) ** 0.5
        norm2 = sum(b * b for b in emb2[:min_len]) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return max(0.0, min(1.0, dot / (norm1 * norm2)))

    def _compute_spectral_similarity(self, v1: AudioVector, v2: AudioVector) -> float:
        """Compute spectral similarity."""
        bands1 = v1.waveform.frequency_bands or [0.0] * 8
        bands2 = v2.waveform.frequency_bands or [0.0] * 8
        return self._compute_similarity(bands1, bands2)

    def _compute_temporal_similarity(self, v1: AudioVector, v2: AudioVector) -> float:
        """Compute temporal similarity."""
        d1 = v1.waveform.duration_seconds
        d2 = v2.waveform.duration_seconds
        if d1 == 0 or d2 == 0:
            return 0.5
        return min(d1, d2) / max(d1, d2)

    def set_reference_audio(self, vector_id: str) -> bool:
        """Set reference audio for cross-engine collaboration."""
        if vector_id in self._vectors:
            self._reference_audio = self._vectors[vector_id]
            return True
        return False

    def get_reference_audio(self) -> Optional[AudioVector]:
        """Get current reference audio."""
        return self._reference_audio

    def get_vector(self, vector_id: str) -> Optional[AudioVector]:
        """Get vector by ID."""
        return self._vectors.get(vector_id)

    def query_by_notation(self, notation: str) -> List[AudioVector]:
        """Query by notation pattern."""
        return [v for v in self._vectors.values() if notation in v.vector_notation]

    def query_by_type(self, audio_type: AudioType) -> List[AudioVector]:
        """Query by audio type."""
        return [v for v in self._vectors.values() if v.audio_type == audio_type]

    def list_vectors(self) -> List[Dict[str, Any]]:
        """List all vectors."""
        return [
            {"id": v.id, "notation": v.vector_notation, "type": v.audio_type.value, "duration": v.waveform.duration_seconds}
            for v in self._vectors.values()
        ]

    def export_for_training(self, output_path: Path) -> int:
        """Export as training data."""
        entries = []
        for vec in self._vectors.values():
            entries.append({
                "instruction": f"Vectorize {vec.audio_type.value} audio",
                "input": json.dumps({"path": vec.source_path, "tags": vec.tags, "transcript": vec.transcript}),
                "output": vec.vector_notation,
            })

        with open(output_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        return len(entries)


# Singleton accessor
_audio_engine_instance: Optional[AudioEngine] = None


def get_audio_engine(storage_path: Path = None) -> AudioEngine:
    """Get or create AudioEngine singleton."""
    global _audio_engine_instance
    if _audio_engine_instance is None:
        _audio_engine_instance = AudioEngine(storage_path)
    return _audio_engine_instance

