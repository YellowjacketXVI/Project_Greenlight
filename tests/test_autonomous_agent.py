"""
Test Autonomous Agent for OmniMind

Tests the autonomous character modification workflow.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from greenlight.omni_mind.autonomous_agent import (
    AutonomousTaskManager,
    AutonomousTask,
    TaskStatus,
    TaskPriority,
    ImageAnalysisResult,
    CharacterModificationRequest
)


class TestAutonomousTaskManager:
    """Tests for AutonomousTaskManager."""
    
    @pytest.fixture
    def manager(self, tmp_path):
        """Create a task manager with temp project path."""
        return AutonomousTaskManager(project_path=tmp_path)
    
    def test_create_task(self, manager):
        """Test task creation."""
        task = manager.create_task(
            name="Test Task",
            description="A test task",
            priority=TaskPriority.HIGH
        )
        
        assert task.id.startswith("task_")
        assert task.name == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.HIGH
    
    def test_task_dependencies(self, manager):
        """Test task dependency tracking."""
        task1 = manager.create_task("Task 1", "First task")
        task2 = manager.create_task("Task 2", "Second task", dependencies=[task1.id])
        
        # Task 1 can execute (no dependencies)
        assert manager.can_execute_task(task1.id) is True
        
        # Task 2 cannot execute (dependency not complete)
        assert manager.can_execute_task(task2.id) is False
        
        # Complete task 1
        manager.update_task_status(task1.id, TaskStatus.COMPLETE)
        
        # Now task 2 can execute
        assert manager.can_execute_task(task2.id) is True
    
    def test_get_pending_tasks(self, manager):
        """Test getting pending tasks sorted by priority."""
        manager.create_task("Low", "Low priority", priority=TaskPriority.LOW)
        manager.create_task("Critical", "Critical priority", priority=TaskPriority.CRITICAL)
        manager.create_task("Medium", "Medium priority", priority=TaskPriority.MEDIUM)
        
        pending = manager.get_pending_tasks()
        
        assert len(pending) == 3
        assert pending[0].priority == TaskPriority.CRITICAL
        assert pending[1].priority == TaskPriority.MEDIUM
        assert pending[2].priority == TaskPriority.LOW
    
    def test_build_smart_prompt_edit(self, manager):
        """Test smart prompt building with edit prefix."""
        prompt = manager.build_smart_prompt(
            base_instruction="Change hair color to white",
            prefix_type="edit"
        )
        
        assert prompt.startswith("Edit this image: ")
        assert "Change hair color to white" in prompt
    
    def test_build_smart_prompt_with_context(self, manager):
        """Test smart prompt with character and style context."""
        prompt = manager.build_smart_prompt(
            base_instruction="Update character appearance",
            prefix_type="character",
            character_context={
                "name": "Mei",
                "appearance": "Petite Asian woman",
                "costume": "Blue kimono"
            },
            style_context={
                "visual_style": "live_action",
                "style_notes": "Dark cinematic"
            }
        )
        
        assert "Create a new image" in prompt
        assert "Mei" in prompt
        assert "live_action" in prompt
    
    def test_find_frames_with_character(self, manager, tmp_path):
        """Test finding frames by character tag."""
        # Create mock visual_script.json
        storyboard_dir = tmp_path / "storyboard"
        storyboard_dir.mkdir()
        
        visual_script = {
            "scenes": [
                {
                    "scene_id": "1",
                    "frames": [
                        {"frame_id": "1.1", "prompt": "Mei walks", "tags": {"characters": ["CHAR_MEI"]}},
                        {"frame_id": "1.2", "prompt": "Empty room", "tags": {"characters": []}},
                        {"frame_id": "1.3", "prompt": "Mei and Jun", "tags": {"characters": ["CHAR_MEI", "CHAR_JUN"]}}
                    ]
                }
            ]
        }
        
        import json
        with open(storyboard_dir / "visual_script.json", "w") as f:
            json.dump(visual_script, f)
        
        manager.set_project(tmp_path)
        frames = manager.find_frames_with_character("CHAR_MEI")
        
        assert len(frames) == 2
        assert frames[0]["frame_id"] == "1.1"
        assert frames[1]["frame_id"] == "1.3"


class TestImageAnalysisResult:
    """Tests for ImageAnalysisResult dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ImageAnalysisResult(
            success=True,
            description="A woman with white hair",
            characters_detected=["woman"],
            character_details={"woman": {"hair_color": "white"}},
            symbolic_notation="@CHAR_MEI"
        )
        
        d = result.to_dict()
        
        assert d["success"] is True
        assert d["description"] == "A woman with white hair"
        assert "@CHAR_MEI" in d["symbolic_notation"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

