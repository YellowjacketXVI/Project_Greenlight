"""
Tests for Director Dialog - Scene-Based Pipeline Execution

Tests the DirectorDialog that loads Script and processes scenes
according to the Directing Phase from Writer_Flow_v2.md.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock


class TestDirectorDialogSceneLoading:
    """Tests for Script loading and scene parsing functionality."""

    def test_load_script_from_standard_project(self, tmp_path):
        """Test loading Script from a standard (non-series) project."""
        # Create project structure
        project_path = tmp_path / "test_project"
        project_path.mkdir()

        # Create project.json (standard project)
        project_config = {"name": "Test Project", "type": "standard"}
        (project_path / "project.json").write_text(json.dumps(project_config))

        # Create Script
        scripts_dir = project_path / "scripts"
        scripts_dir.mkdir()
        script_content = """# Test Script

## Scene 1: Test Scene

**Location:** [LOC_ROOM]
**Time:** Morning
**Characters:** [CHAR_HERO]
**Purpose:** Establish setting
**Emotional Beat:** Calm

### Beat 1

** [CHAR_HERO] enters [LOC_ROOM] from the east.

**Beat Details:**
- Characters: [CHAR_HERO]
- Location: [LOC_ROOM]
- Direction: Moving E
- Camera: Wide shot
- Emotional Arc: Determined

### Beat 2

** [CHAR_HERO] looks around the room.

**Beat Details:**
- Characters: [CHAR_HERO]
- Direction: Facing N
- Camera: Medium shot
- Emotional Arc: Curious
"""
        (scripts_dir / "script.md").write_text(script_content)

        # Test the loading logic directly (without UI)
        from greenlight.ui.dialogs.director_dialog import DirectorDialog

        # Mock the parent and prevent UI creation
        with patch.object(DirectorDialog, '__init__', lambda self, *args, **kwargs: None):
            dialog = DirectorDialog.__new__(DirectorDialog)
            dialog.project_path = project_path
            dialog.scenes_data = []
            dialog.script_content = ""
            dialog._load_script()

            assert len(dialog.scenes_data) == 1
            assert dialog.scenes_data[0].scene_number == 1
            assert dialog.scenes_data[0].location == "LOC_ROOM"
            assert len(dialog.scenes_data[0].beats) == 2

    def test_load_script_from_series_project(self, tmp_path):
        """Test loading Script from a series project."""
        # Create project structure
        project_path = tmp_path / "test_series"
        project_path.mkdir()

        # Create project.json (series project)
        project_config = {"name": "Test Series", "type": "series"}
        (project_path / "project.json").write_text(json.dumps(project_config))

        # Create Script in series structure
        scripts_dir = project_path / "SEASON_01" / "EPISODE_01" / "scripts"
        scripts_dir.mkdir(parents=True)
        script_content = """# Series Script

## Scene 1: Opening

**Location:** [LOC_OFFICE]
**Time:** Morning
**Characters:** [CHAR_DETECTIVE]
**Purpose:** Introduce protagonist
**Emotional Beat:** Tension

### Beat 1

** [CHAR_DETECTIVE] reviews case files.

**Beat Details:**
- Characters: [CHAR_DETECTIVE]
- Direction: Facing desk
- Camera: Close-up
- Emotional Arc: Focused
"""
        (scripts_dir / "script.md").write_text(script_content)

        # Test the loading logic directly
        from greenlight.ui.dialogs.director_dialog import DirectorDialog

        with patch.object(DirectorDialog, '__init__', lambda self, *args, **kwargs: None):
            dialog = DirectorDialog.__new__(DirectorDialog)
            dialog.project_path = project_path
            dialog.scenes_data = []
            dialog.script_content = ""
            dialog._load_script()

            assert len(dialog.scenes_data) == 1
            assert dialog.scenes_data[0].location == "LOC_OFFICE"

    def test_load_script_no_file(self, tmp_path):
        """Test loading when no Script exists."""
        project_path = tmp_path / "empty_project"
        project_path.mkdir()

        # Create project.json but no script
        project_config = {"name": "Empty Project", "type": "standard"}
        (project_path / "project.json").write_text(json.dumps(project_config))

        from greenlight.ui.dialogs.director_dialog import DirectorDialog

        with patch.object(DirectorDialog, '__init__', lambda self, *args, **kwargs: None):
            dialog = DirectorDialog.__new__(DirectorDialog)
            dialog.project_path = project_path
            dialog.scenes_data = []
            dialog.script_content = ""
            dialog._load_script()

            assert len(dialog.scenes_data) == 0

    def test_parse_multiple_scenes(self, tmp_path):
        """Test parsing multiple scenes from Script."""
        project_path = tmp_path / "multi_scene_project"
        project_path.mkdir()

        # Create project.json
        project_config = {"name": "Multi Scene Project", "type": "single"}
        (project_path / "project.json").write_text(json.dumps(project_config))

        # Create script with multiple scenes
        scripts_dir = project_path / "scripts"
        scripts_dir.mkdir()
        script_content = """# Multi Scene Script

## Scene 1: Opening

**Location:** [LOC_ROOM]
**Time:** Morning
**Characters:** [CHAR_HERO]
**Purpose:** Establish setting
**Emotional Beat:** Calm

### Beat 1

** [CHAR_HERO] wakes up.

**Beat Details:**
- Direction: In bed
- Camera: Wide shot
- Emotional Arc: Drowsy

## Scene 2: Journey

**Location:** [LOC_FOREST]
**Time:** Afternoon
**Characters:** [CHAR_HERO], [CHAR_GUIDE]
**Purpose:** Travel sequence
**Emotional Beat:** Adventure

### Beat 1

** [CHAR_HERO] and [CHAR_GUIDE] walk through [LOC_FOREST].

**Beat Details:**
- Direction: Moving N
- Camera: Tracking shot
- Emotional Arc: Determined

### Beat 2

** [CHAR_GUIDE] points to something in the distance.

**Beat Details:**
- Direction: Facing E
- Camera: Over-shoulder
- Emotional Arc: Curious
"""
        (scripts_dir / "script.md").write_text(script_content)

        from greenlight.ui.dialogs.director_dialog import DirectorDialog

        with patch.object(DirectorDialog, '__init__', lambda self, *args, **kwargs: None):
            dialog = DirectorDialog.__new__(DirectorDialog)
            dialog.project_path = project_path
            dialog.scenes_data = []
            dialog.script_content = ""
            dialog._load_script()

            # Should have parsed 2 scenes
            assert len(dialog.scenes_data) == 2
            assert dialog.scenes_data[0].scene_number == 1
            assert dialog.scenes_data[0].location == "LOC_ROOM"
            assert len(dialog.scenes_data[0].beats) == 1

            assert dialog.scenes_data[1].scene_number == 2
            assert dialog.scenes_data[1].location == "LOC_FOREST"
            assert len(dialog.scenes_data[1].beats) == 2


class TestDirectorDialogCharacterLoading:
    """Tests for character description loading."""

    def test_load_character_descriptions(self, tmp_path):
        """Test loading character descriptions from world config."""
        project_path = tmp_path / "test_project"
        project_path.mkdir()
        
        # Create world config
        world_dir = project_path / "world_bible"
        world_dir.mkdir()
        world_config = {
            "characters": [
                {"tag": "CHAR_MEI", "name": "Mei", "role": "Protagonist"},
                {"tag": "CHAR_CHEN", "name": "Chen", "role": "Mentor"},
            ]
        }
        (world_dir / "world_config.json").write_text(json.dumps(world_config))
        
        from greenlight.ui.dialogs.director_dialog import DirectorDialog
        
        with patch.object(DirectorDialog, '__init__', lambda self, *args, **kwargs: None):
            dialog = DirectorDialog.__new__(DirectorDialog)
            dialog.project_path = project_path
            
            descriptions = dialog._load_character_descriptions()
            
            assert "CHAR_MEI" in descriptions
            assert "Mei" in descriptions["CHAR_MEI"]
            assert "Protagonist" in descriptions["CHAR_MEI"]


class TestDirectorDialogPromptSaving:
    """Tests for prompt saving functionality."""

    def test_save_prompts_creates_file(self, tmp_path):
        """Test that prompts are saved correctly."""
        project_path = tmp_path / "test_project"
        project_path.mkdir()

        from greenlight.ui.dialogs.director_dialog import DirectorDialog
        from greenlight.pipelines.director_pipeline import StoryboardPrompt, CameraShot

        # Create mock prompts with correct CameraShot structure
        mock_prompts = [
            StoryboardPrompt(
                notation="(S01).(F01).(c1)",
                scene_description="Test scene",
                camera_shot=CameraShot(
                    notation="(S01).(F01).(c1)",
                    shot_type="WIDE",
                    shot_type_code="WS",
                    angle="EYE_LEVEL",
                    angle_code="EL",
                    movement="STATIC",
                    movement_code="ST",
                    framing="center",
                    focus="subject",
                    lighting_style="natural",
                    description="Wide establishing shot"
                ),
                character_details=["CHAR_MEI"],
                environment_details="Interior teahouse",
                lighting="natural",
                mood="calm",
                action="Character enters",
                full_prompt="A wide shot of the scene",
                negative_prompt="blurry",
                technical_notes="Standard framing"
            )
        ]
        
        with patch.object(DirectorDialog, '__init__', lambda self, *args, **kwargs: None):
            dialog = DirectorDialog.__new__(DirectorDialog)
            dialog.project_path = project_path
            dialog.external_log = None

            # Mock _log method
            dialog._log = MagicMock()

            # Create the prompts directory first (simulating standard project)
            prompts_dir = project_path / "prompts"
            prompts_dir.mkdir(parents=True, exist_ok=True)

            dialog._save_prompts(mock_prompts)

            # Check file was created
            prompts_path = project_path / "prompts" / "storyboard_prompts.json"
            assert prompts_path.exists()

            # Verify content
            saved_data = json.loads(prompts_path.read_text())
            assert saved_data["total_prompts"] == 1
            assert saved_data["prompts"][0]["shot_type"] == "WIDE"

