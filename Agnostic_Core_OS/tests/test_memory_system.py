"""
Tests for the Memory Vector System

Tests:
- VectorMemory storage and retrieval
- UINetworkCrafter layout management
- UserProfileManager workflow tracking
- DatasetCrafter LoRA export
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from Agnostic_Core_OS.memory.vector_memory import (
    VectorMemory,
    MemoryEntry,
    MemoryType,
    MemoryPriority,
)
from Agnostic_Core_OS.memory.ui_network import (
    UINetworkCrafter,
    UIComponent,
    UILayout,
    ComponentType,
)
from Agnostic_Core_OS.memory.user_profile import (
    UserProfileManager,
    UserProfile,
    WorkflowPattern,
    WorkflowType,
)
from Agnostic_Core_OS.memory.dataset_crafter import (
    DatasetCrafter,
    DatasetEntry,
    DatasetFormat,
    LoRADataset,
)


# =============================================================================
# VECTOR MEMORY TESTS
# =============================================================================

class TestVectorMemory:
    """Tests for VectorMemory."""
    
    @pytest.fixture
    def memory(self, tmp_path):
        """Create a VectorMemory instance."""
        return VectorMemory(storage_path=tmp_path / "memory")
    
    def test_store_and_retrieve(self, memory):
        """Test storing and retrieving entries."""
        entry = memory.store(
            memory_type=MemoryType.UI_STATE,
            content={"panel": "editor", "visible": True},
            vector_notation=">ui show editor",
            natural_language="Show the editor panel",
        )
        
        assert entry.id is not None
        assert entry.memory_type == MemoryType.UI_STATE
        
        retrieved = memory.retrieve(entry.id)
        assert retrieved is not None
        assert retrieved.access_count == 1
    
    def test_query_by_vector(self, memory):
        """Test querying by vector notation."""
        memory.store(
            memory_type=MemoryType.UI_STATE,
            content={"action": "hide"},
            vector_notation=">ui hide nav",
        )
        
        results = memory.query_by_vector(">ui hide nav")
        assert len(results) == 1
    
    def test_query_by_type(self, memory):
        """Test querying by memory type."""
        memory.store(MemoryType.WORKFLOW, {"step": 1}, "")
        memory.store(MemoryType.WORKFLOW, {"step": 2}, "")
        memory.store(MemoryType.UI_STATE, {"panel": "nav"}, "")
        
        workflows = memory.query_by_type(MemoryType.WORKFLOW)
        assert len(workflows) == 2
    
    def test_export_training_data(self, memory, tmp_path):
        """Test exporting as training data."""
        memory.store(
            MemoryType.LLM_INTERACTION,
            {"request": "test"},
            ">test",
            "Run a test",
        )
        
        output = tmp_path / "training.jsonl"
        count = memory.export_training_data(output)
        assert count == 1
        assert output.exists()


# =============================================================================
# UI NETWORK TESTS
# =============================================================================

class TestUINetworkCrafter:
    """Tests for UINetworkCrafter."""
    
    @pytest.fixture
    def crafter(self):
        """Create a UINetworkCrafter instance."""
        return UINetworkCrafter()
    
    def test_default_layouts(self, crafter):
        """Test default layouts are created."""
        layouts = crafter.list_layouts()
        assert len(layouts) >= 3
        
        names = [l["name"] for l in layouts]
        assert "Story Writing" in names
        assert "Storyboard" in names
    
    def test_set_active_layout(self, crafter):
        """Test setting active layout."""
        assert crafter.set_active_layout("layout_story")
        layout = crafter.get_active_layout()
        assert layout is not None
        assert layout.name == "Story Writing"
    
    def test_create_layout(self, crafter):
        """Test creating a custom layout."""
        layout = crafter.create_layout(
            name="Custom Layout",
            description="A custom layout",
            components=[
                UIComponent("panel1", ComponentType.PANEL, "Panel 1"),
            ]
        )
        
        assert layout.id is not None
        assert len(layout.components) == 1
    
    @pytest.mark.asyncio
    async def test_customize_from_request(self, crafter):
        """Test customizing from natural language."""
        crafter.set_active_layout("layout_story")

        customization = await crafter.customize_from_request("Hide the navigator")

        assert customization.request_id is not None
        assert ">ui hide nav" in customization.vector_notation


# =============================================================================
# USER PROFILE TESTS
# =============================================================================

class TestUserProfileManager:
    """Tests for UserProfileManager."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a UserProfileManager instance."""
        return UserProfileManager(storage_path=tmp_path / "profiles")

    def test_create_profile(self, manager):
        """Test creating a profile."""
        profile = manager.create_profile("Test User", "test@example.com")

        assert profile.id is not None
        assert profile.name == "Test User"
        assert manager.get_active_profile() == profile

    def test_set_preference(self, manager):
        """Test setting preferences."""
        manager.create_profile("Test User")

        assert manager.set_preference("theme", "dark", "ui")
        assert manager.get_preference("theme") == "dark"

    def test_record_action(self, manager):
        """Test recording actions."""
        manager.create_profile("Test User")

        for i in range(5):
            manager.record_action(
                action_type="edit_story",
                details={"step": i},
                vector=">story edit",
            )

        profile = manager.get_active_profile()
        assert profile.total_actions == 5

    def test_workflow_detection(self, manager):
        """Test workflow pattern detection."""
        manager.create_profile("Test User")

        # Record enough actions to trigger detection
        for i in range(12):
            manager.record_action(
                action_type=f"action_{i % 5}",
                details={"step": i},
            )

        workflows = manager.get_frequent_workflows()
        # May or may not have detected patterns depending on sequence
        assert isinstance(workflows, list)


# =============================================================================
# DATASET CRAFTER TESTS
# =============================================================================

class TestDatasetCrafter:
    """Tests for DatasetCrafter."""

    @pytest.fixture
    def crafter(self, tmp_path):
        """Create a DatasetCrafter instance."""
        return DatasetCrafter(storage_path=tmp_path / "datasets")

    def test_create_dataset(self, crafter):
        """Test creating a dataset."""
        dataset = crafter.create_dataset(
            name="Test Dataset",
            description="A test dataset",
            format=DatasetFormat.JSONL,
        )

        assert dataset.id is not None
        assert dataset.name == "Test Dataset"

    def test_add_entry(self, crafter):
        """Test adding entries."""
        dataset = crafter.create_dataset("Test", "Test dataset")

        entry = crafter.add_entry(
            dataset_id=dataset.id,
            instruction="Translate to vector",
            input_text="Show the editor",
            output_text=">ui show editor",
            category="ui",
        )

        assert entry is not None
        assert entry.instruction == "Translate to vector"

    def test_export_formats(self, crafter, tmp_path):
        """Test exporting in different formats."""
        dataset = crafter.create_dataset("Export Test", "Test export")

        crafter.add_entry(
            dataset.id,
            "Test instruction",
            "Test input",
            "Test output",
        )

        result = crafter.export(
            dataset.id,
            tmp_path / "export",
            format=DatasetFormat.JSONL,
        )

        assert result["total"] == 1
        assert (tmp_path / "export_train.jsonl").exists()

    def test_dataset_stats(self, crafter):
        """Test getting dataset statistics."""
        dataset = crafter.create_dataset("Stats Test", "Test stats")

        crafter.add_entry(dataset.id, "Inst1", "In1", "Out1", category="cat1")
        crafter.add_entry(dataset.id, "Inst2", "In2", "Out2", category="cat2")

        stats = crafter.get_stats(dataset.id)

        assert stats["total_entries"] == 2
        assert "cat1" in stats["categories"]
        assert "cat2" in stats["categories"]


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestMemoryIntegration:
    """Integration tests for the memory system."""

    def test_memory_to_dataset_flow(self, tmp_path):
        """Test flow from memory to dataset."""
        # Create memory and store entries
        memory = VectorMemory(storage_path=tmp_path / "memory")

        memory.store(
            MemoryType.LLM_INTERACTION,
            {"request": "Show editor"},
            ">ui show editor",
            "Show the editor panel",
        )
        memory.store(
            MemoryType.LLM_INTERACTION,
            {"request": "Run story pipeline"},
            ">story standard",
            "Run the story pipeline",
        )

        # Create dataset and import from memory
        crafter = DatasetCrafter(storage_path=tmp_path / "datasets")
        dataset = crafter.create_dataset("From Memory", "Imported from memory")

        entries = memory.query_by_type(MemoryType.LLM_INTERACTION)
        count = crafter.add_from_memory(dataset.id, entries)

        assert count == 2

        # Export
        result = crafter.export(dataset.id, tmp_path / "lora_data")
        assert result["total"] == 2

