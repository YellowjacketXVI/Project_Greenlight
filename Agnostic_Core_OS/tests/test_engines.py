"""
Tests for Agnostic_Core_OS Engines

Tests:
- ImageEngine: vectorization, comparison, SafeTensor
- AudioEngine: vectorization, waveform analysis, comparison
- LiveAnalyzeEngine: flash features, sample replication
- ComparisonLearning: iterative learning, delta computation
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from Agnostic_Core_OS.engines.image_engine import (
    ImageEngine,
    ImageVector,
    ImageComparison,
    ImageType,
    SafeTensorFormat,
)
from Agnostic_Core_OS.engines.audio_engine import (
    AudioEngine,
    AudioVector,
    AudioComparison,
    AudioType,
    WaveformData,
)
from Agnostic_Core_OS.engines.live_analyze_engine import (
    LiveAnalyzeEngine,
    FlashFeature,
    SampleReplication,
    AnalysisMode,
    FeatureType,
    ReplicationMode,
)
from Agnostic_Core_OS.engines.comparison_learning import (
    ComparisonLearning,
    LearningReport,
    VectorDelta,
    ComparisonType,
)


# =============================================================================
# IMAGE ENGINE TESTS
# =============================================================================

class TestImageEngine:
    """Tests for ImageEngine."""
    
    @pytest.fixture
    def engine(self, tmp_path):
        """Create an ImageEngine instance."""
        return ImageEngine(storage_path=tmp_path / "images")
    
    @pytest.fixture
    def sample_image(self, tmp_path):
        """Create a sample PNG image."""
        img_path = tmp_path / "test.png"
        # Minimal PNG header
        png_header = b'\x89PNG\r\n\x1a\n'
        ihdr = b'\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x02\x00\x00\x00\x90\x91h6'
        with open(img_path, "wb") as f:
            f.write(png_header + ihdr + b'\x00' * 100)
        return img_path
    
    def test_vectorize_image(self, engine, sample_image):
        """Test image vectorization."""
        vector = engine.vectorize_image(
            image_path=sample_image,
            image_type=ImageType.CHARACTER,
            tags=["test", "character"],
        )
        
        assert vector.id is not None
        assert "@IMG_CHARACTER" in vector.vector_notation
        assert vector.image_type == ImageType.CHARACTER
        assert len(vector.embedding) > 0
    
    def test_compare_images(self, engine, sample_image):
        """Test image comparison."""
        v1 = engine.vectorize_image(sample_image, ImageType.REFERENCE, ["a"])
        v2 = engine.vectorize_image(sample_image, ImageType.REFERENCE, ["b"])
        
        comparison = engine.compare_images(v1.id, v2.id)
        
        assert comparison is not None
        assert comparison.similarity_score >= 0.0
        assert comparison.similarity_score <= 1.0
    
    def test_reference_image(self, engine, sample_image):
        """Test reference image setting."""
        vector = engine.vectorize_image(sample_image, ImageType.REFERENCE)
        
        assert engine.set_reference_image(vector.id)
        assert engine.get_reference_image() == vector
    
    def test_query_by_notation(self, engine, sample_image):
        """Test querying by notation."""
        engine.vectorize_image(sample_image, ImageType.CHARACTER, ["mei"])
        
        results = engine.query_by_notation("CHARACTER")
        assert len(results) == 1


# =============================================================================
# AUDIO ENGINE TESTS
# =============================================================================

class TestAudioEngine:
    """Tests for AudioEngine."""
    
    @pytest.fixture
    def engine(self, tmp_path):
        """Create an AudioEngine instance."""
        return AudioEngine(storage_path=tmp_path / "audio")
    
    @pytest.fixture
    def sample_audio(self, tmp_path):
        """Create a sample WAV file."""
        wav_path = tmp_path / "test.wav"
        # Minimal WAV header
        import struct
        with open(wav_path, "wb") as f:
            f.write(b'RIFF')
            f.write(struct.pack("<I", 36 + 1000))  # File size
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write(struct.pack("<I", 16))  # Chunk size
            f.write(struct.pack("<H", 1))   # Audio format (PCM)
            f.write(struct.pack("<H", 2))   # Channels
            f.write(struct.pack("<I", 44100))  # Sample rate
            f.write(struct.pack("<I", 176400))  # Byte rate
            f.write(struct.pack("<H", 4))   # Block align
            f.write(struct.pack("<H", 16))  # Bits per sample
            f.write(b'data')
            f.write(struct.pack("<I", 1000))  # Data size
            f.write(b'\x00' * 1000)  # Audio data
        return wav_path
    
    def test_vectorize_audio(self, engine, sample_audio):
        """Test audio vectorization."""
        vector = engine.vectorize_audio(
            audio_path=sample_audio,
            audio_type=AudioType.DIALOGUE,
            tags=["test"],
            transcript="Hello world",
        )
        
        assert vector.id is not None
        assert "@AUD_DIALOGUE" in vector.vector_notation
        assert vector.waveform.sample_rate == 44100
        assert vector.transcript == "Hello world"
    
    def test_compare_audio(self, engine, sample_audio):
        """Test audio comparison."""
        v1 = engine.vectorize_audio(sample_audio, AudioType.REFERENCE, ["a"])
        v2 = engine.vectorize_audio(sample_audio, AudioType.REFERENCE, ["b"])
        
        comparison = engine.compare_audio(v1.id, v2.id)

        assert comparison is not None
        assert comparison.similarity_score >= 0.0


# =============================================================================
# LIVE ANALYZE ENGINE TESTS
# =============================================================================

class TestLiveAnalyzeEngine:
    """Tests for LiveAnalyzeEngine."""

    @pytest.fixture
    def engine(self, tmp_path):
        """Create a LiveAnalyzeEngine instance."""
        return LiveAnalyzeEngine(storage_path=tmp_path / "analysis")

    def test_start_session(self, engine):
        """Test session management."""
        session_id = engine.start_session(AnalysisMode.REALTIME)

        assert session_id is not None
        assert len(session_id) == 12

    def test_extract_flash_feature(self, engine):
        """Test flash feature extraction."""
        engine.start_session()

        feature = engine.extract_flash_feature(
            vector_notation="@IMG_TEST_abc123",
            feature_type=FeatureType.COLOR_PALETTE,
        )

        assert feature is not None
        assert feature.feature_type == FeatureType.COLOR_PALETTE
        assert len(feature.values) > 0
        assert len(feature.labels) > 0

    def test_replicate_sample(self, engine):
        """Test sample replication."""
        engine.start_session()

        replication = engine.replicate_sample(
            source_vector="@IMG_TEST_abc123",
            mode=ReplicationMode.VARIATION,
        )

        assert replication is not None
        assert replication.status == "completed"
        assert replication.similarity_to_source == 0.85

    def test_session_report(self, engine):
        """Test session report generation."""
        session_id = engine.start_session()
        engine.extract_flash_feature("@IMG_TEST", FeatureType.COMPOSITION)
        engine.replicate_sample("@IMG_TEST", ReplicationMode.EXACT)

        report = engine.end_session()

        assert report is not None
        assert report.features_extracted == 1
        assert report.replications_completed == 1

    def test_usage_report(self, engine):
        """Test usage report generation."""
        engine.start_session()
        engine.extract_flash_feature("@IMG_A", FeatureType.SEMANTIC)

        usage = engine.generate_usage_report(permission_level="full")

        assert usage["permission_level"] == "full"
        assert usage["total_features"] >= 1


# =============================================================================
# COMPARISON LEARNING TESTS
# =============================================================================

class TestComparisonLearning:
    """Tests for ComparisonLearning."""

    @pytest.fixture
    def learning(self, tmp_path):
        """Create a ComparisonLearning instance."""
        return ComparisonLearning(storage_path=tmp_path / "learning")

    def test_compute_delta(self, learning):
        """Test delta computation."""
        delta = learning.compute_delta(
            source_embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            target_embedding=[0.2, 0.3, 0.4, 0.5, 0.6],
            source_notation="@IMG_A",
            target_notation="@IMG_B",
        )

        assert delta is not None
        assert delta.magnitude > 0
        assert delta.direction in ["positive", "negative", "stable"]

    def test_learn_from_comparisons(self, learning):
        """Test iterative learning."""
        source_vectors = [
            ("@IMG_A", [0.1, 0.2, 0.3]),
            ("@IMG_B", [0.2, 0.3, 0.4]),
        ]
        target_vectors = [
            ("@IMG_C", [0.3, 0.4, 0.5]),
            ("@IMG_D", [0.4, 0.5, 0.6]),
        ]

        report = learning.learn_from_comparisons(
            source_vectors=source_vectors,
            target_vectors=target_vectors,
            comparison_type=ComparisonType.IMAGE_TO_IMAGE,
            max_iterations=10,
        )

        assert report is not None
        assert report.total_iterations > 0
        assert report.total_iterations <= 10
        assert len(report.deltas) > 0

    def test_usage_report(self, learning):
        """Test usage report generation."""
        learning.compute_delta([0.1], [0.2], "@A", "@B")

        usage = learning.generate_usage_report()

        assert usage["total_deltas"] >= 1

    def test_export_for_training(self, learning, tmp_path):
        """Test training data export."""
        learning.compute_delta([0.1, 0.2], [0.3, 0.4], "@A", "@B")

        output_path = tmp_path / "training.jsonl"
        count = learning.export_for_training(output_path)

        assert count >= 1
        assert output_path.exists()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestEngineIntegration:
    """Integration tests for all engines."""

    def test_cross_engine_collaboration(self, tmp_path):
        """Test engines working together."""
        img_engine = ImageEngine(storage_path=tmp_path / "img")
        aud_engine = AudioEngine(storage_path=tmp_path / "aud")
        live_engine = LiveAnalyzeEngine(storage_path=tmp_path / "live")
        learning = ComparisonLearning(storage_path=tmp_path / "learn")

        # Connect engines
        live_engine.connect_engines(image_engine=img_engine, audio_engine=aud_engine)
        learning.connect_engines(image_engine=img_engine, audio_engine=aud_engine)

        # Start analysis session
        session_id = live_engine.start_session()
        assert session_id is not None

        # Extract features
        feature = live_engine.extract_flash_feature("@TEST", FeatureType.SEMANTIC)
        assert feature is not None

        # Compute learning delta
        delta = learning.compute_delta([0.1, 0.2], [0.3, 0.4], "@A", "@B")
        assert delta is not None

        # End session
        report = live_engine.end_session()
        assert report.features_extracted >= 1

