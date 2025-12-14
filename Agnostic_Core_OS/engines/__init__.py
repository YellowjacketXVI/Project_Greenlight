"""
Agnostic_Core_OS Engines

Multi-modal processing engines for:
- Image Engine: Image-to-vector translation with SafeTensor support
- Audio Engine: Audio-to-vector notation processing
- Live Analyze Engine: Real-time analysis and flash features
- Comparison Learning: Iterative learning with vectored reports
"""

from .image_engine import (
    ImageEngine,
    ImageVector,
    ImageComparison,
    SafeTensorFormat,
    get_image_engine,
)
from .audio_engine import (
    AudioEngine,
    AudioVector,
    AudioComparison,
    WaveformData,
    get_audio_engine,
)
from .live_analyze_engine import (
    LiveAnalyzeEngine,
    FlashFeature,
    SampleReplication,
    AnalysisReport,
    get_live_engine,
)
from .comparison_learning import (
    ComparisonLearning,
    LearningReport,
    VectorDelta,
    IterationResult,
)

__all__ = [
    # Image Engine
    "ImageEngine",
    "ImageVector",
    "ImageComparison",
    "SafeTensorFormat",
    "get_image_engine",
    # Audio Engine
    "AudioEngine",
    "AudioVector",
    "AudioComparison",
    "WaveformData",
    "get_audio_engine",
    # Live Analyze Engine
    "LiveAnalyzeEngine",
    "FlashFeature",
    "SampleReplication",
    "AnalysisReport",
    "get_live_engine",
    # Comparison Learning
    "ComparisonLearning",
    "LearningReport",
    "VectorDelta",
    "IterationResult",
]

