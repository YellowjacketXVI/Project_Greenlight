"""
Tests for Beat Extractor - Story Pipeline v3.0

Tests:
- Beat extraction from prose
- Beat type classification
- BeatSheet serialization
"""

import pytest
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from greenlight.agents.beat_extractor import (
    BeatExtractor,
    BeatSheet,
    Beat,
    BeatType,
    SceneBeats,
)
from greenlight.agents.prose_agent import ProseResult


class TestBeatType:
    """Test BeatType enum."""
    
    def test_all_beat_types(self):
        """Test all beat types exist."""
        expected = ["establishing", "dialogue", "action", "reaction", 
                   "revelation", "transition", "climax", "resolution"]
        actual = [b.value for b in BeatType]
        assert actual == expected


class TestBeat:
    """Test Beat dataclass."""
    
    def test_to_dict(self):
        """Test serialization."""
        beat = Beat(
            beat_id="1.1",
            scene_number=1,
            beat_number=1,
            beat_type=BeatType.ESTABLISHING,
            content="The temple rises in the mist.",
            start_word=0,
            end_word=6,
            characters=["CHAR_LIN"]
        )
        
        d = beat.to_dict()
        assert d["beat_id"] == "1.1"
        assert d["type"] == "establishing"
        assert d["characters"] == ["CHAR_LIN"]


class TestSceneBeats:
    """Test SceneBeats dataclass."""
    
    def test_to_dict(self):
        """Test serialization."""
        scene_beats = SceneBeats(
            scene_number=1,
            beats=[
                Beat("1.1", 1, 1, BeatType.ESTABLISHING, "Content", 0, 5),
                Beat("1.2", 1, 2, BeatType.ACTION, "More content", 5, 10),
            ]
        )
        
        d = scene_beats.to_dict()
        assert d["scene"] == 1
        assert d["beat_count"] == 2
        assert len(d["beats"]) == 2


class TestBeatSheet:
    """Test BeatSheet dataclass."""
    
    @pytest.fixture
    def sample_beat_sheet(self):
        """Create sample beat sheet."""
        return BeatSheet(scenes=[
            SceneBeats(scene_number=1, beats=[
                Beat("1.1", 1, 1, BeatType.ESTABLISHING, "Scene 1 beat 1", 0, 5),
            ]),
            SceneBeats(scene_number=2, beats=[
                Beat("2.1", 2, 1, BeatType.ACTION, "Scene 2 beat 1", 0, 5),
                Beat("2.2", 2, 2, BeatType.DIALOGUE, "Scene 2 beat 2", 5, 10),
            ]),
        ])
    
    def test_total_beats(self, sample_beat_sheet):
        """Test total beats calculation."""
        assert sample_beat_sheet.total_beats == 3
    
    def test_to_dict(self, sample_beat_sheet):
        """Test serialization."""
        d = sample_beat_sheet.to_dict()
        assert d["total_scenes"] == 2
        assert d["total_beats"] == 3
    
    def test_save(self, sample_beat_sheet):
        """Test saving to file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "beat_sheet.json"
            sample_beat_sheet.save(path)
            
            assert path.exists()
            import json
            with open(path) as f:
                data = json.load(f)
            assert data["total_beats"] == 3


class TestBeatExtractor:
    """Test BeatExtractor."""
    
    @pytest.fixture
    def mock_llm_caller(self):
        """Create mock LLM caller."""
        async def caller(prompt, system_prompt, max_tokens):
            return """BEAT 1: [ESTABLISHING]
TEXT: "The temple rises in the morning mist"
CHARACTERS: CHAR_LIN

BEAT 2: [ACTION]
TEXT: "Lin steps forward, her hand on the door"
CHARACTERS: CHAR_LIN"""
        return caller
    
    @pytest.fixture
    def extractor(self, mock_llm_caller):
        """Create test extractor."""
        return BeatExtractor(mock_llm_caller)
    
    @pytest.fixture
    def sample_prose_results(self):
        """Create sample prose results."""
        return [
            ProseResult(
                scene_number=1,
                prose="The temple rises in the morning mist. Lin steps forward, her hand on the door.",
                word_count=15,
                exit_states={},
                new_threads=[], resolved_threads=[], new_setups=[]
            ),
        ]
    
    @pytest.mark.asyncio
    async def test_extract_beats(self, extractor, sample_prose_results):
        """Test beat extraction."""
        beat_sheet = await extractor.extract_beats(sample_prose_results)
        
        assert isinstance(beat_sheet, BeatSheet)
        assert len(beat_sheet.scenes) == 1
        assert beat_sheet.total_beats >= 1
    
    def test_parse_beats(self, extractor, sample_prose_results):
        """Test beat parsing."""
        response = """BEAT 1: [ESTABLISHING]
TEXT: "The temple rises"
CHARACTERS: CHAR_LIN

BEAT 2: [ACTION]
TEXT: "Lin steps forward"
CHARACTERS: CHAR_LIN"""
        
        beats = extractor._parse_beats(response, sample_prose_results[0])
        
        assert len(beats) == 2
        assert beats[0].beat_type == BeatType.ESTABLISHING
        assert beats[1].beat_type == BeatType.ACTION

