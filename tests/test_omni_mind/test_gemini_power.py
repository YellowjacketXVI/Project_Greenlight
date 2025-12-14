"""
Tests for Gemini Power module.

Tests initialization protocol, vector tasks, commands, and LLM picker integration.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from greenlight.omni_mind.gemini_power import (
    GeminiPower, VectorTask, VectorTaskType, VectorCommand, CommandScope,
    InitStatus, InitPhase, GeminiResponse, create_gemini_power
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_gemini_client():
    """Create a mock Gemini client."""
    client = Mock()
    response = Mock()
    response.text = "OK - Test response"
    response.raw_response = {"test": True}
    client.generate_text = Mock(return_value=response)
    return client


@pytest.fixture
def temp_project_path(tmp_path):
    """Create a temporary project path."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    return project_path


@pytest.fixture
def gemini_power(mock_gemini_client, temp_project_path):
    """Create a GeminiPower instance with mocked client."""
    power = GeminiPower(
        project_path=temp_project_path,
        gemini_client=mock_gemini_client,
        auto_init=False
    )
    return power


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================

class TestGeminiPowerInit:
    """Tests for GeminiPower initialization."""
    
    def test_init_creates_instance(self, gemini_power):
        """Test that GeminiPower can be instantiated."""
        assert gemini_power is not None
        assert gemini_power._init_status.phase == InitPhase.BOOT
    
    def test_init_with_project_path(self, gemini_power, temp_project_path):
        """Test initialization with project path."""
        assert gemini_power.project_path == temp_project_path
        assert gemini_power.gemini_dir == temp_project_path / ".gemini_power"
    
    @pytest.mark.asyncio
    async def test_initialize_protocol(self, gemini_power):
        """Test full initialization protocol."""
        status = await gemini_power.initialize()
        
        assert status.phase == InitPhase.READY
        assert status.progress == 1.0
        assert status.is_ready
        assert not status.has_errors
    
    @pytest.mark.asyncio
    async def test_initialize_registers_commands(self, gemini_power):
        """Test that initialization registers default commands."""
        await gemini_power.initialize()
        
        assert len(gemini_power._commands) > 0
        assert "query" in gemini_power._commands
        assert "analyze" in gemini_power._commands
        assert "status" in gemini_power._commands
        assert "build" in gemini_power._commands
        assert "diagnose" in gemini_power._commands


# =============================================================================
# COMMAND TESTS
# =============================================================================

class TestVectorCommands:
    """Tests for vector command registration and execution."""
    
    @pytest.mark.asyncio
    async def test_register_command(self, gemini_power):
        """Test registering a custom command."""
        await gemini_power.initialize()
        
        custom_cmd = VectorCommand(
            name="custom_test",
            description="A custom test command",
            scope=CommandScope.LOCAL,
            handler=lambda **kwargs: {"result": "custom"}
        )
        gemini_power.register_command(custom_cmd)
        
        assert "custom_test" in gemini_power._commands
        assert gemini_power.get_command("custom_test") == custom_cmd
    
    @pytest.mark.asyncio
    async def test_list_commands_by_scope(self, gemini_power):
        """Test listing commands filtered by scope."""
        await gemini_power.initialize()
        
        local_cmds = gemini_power.list_commands(CommandScope.LOCAL)
        system_cmds = gemini_power.list_commands(CommandScope.SYSTEM)
        
        assert all(c.scope == CommandScope.LOCAL for c in local_cmds)
        assert all(c.scope == CommandScope.SYSTEM for c in system_cmds)
    
    @pytest.mark.asyncio
    async def test_status_command(self, gemini_power):
        """Test the status command."""
        await gemini_power.initialize()
        
        result = gemini_power._cmd_status()
        
        assert "version" in result
        assert "init_status" in result
        assert result["init_status"]["is_ready"] == True
        assert result["gemini_connected"] == True
    
    @pytest.mark.asyncio
    async def test_diagnose_command(self, gemini_power):
        """Test the diagnose command."""
        await gemini_power.initialize()

        result = gemini_power._cmd_diagnose()

        assert "healthy" in result
        assert "issues" in result
        assert "warnings" in result
        assert "recommendations" in result


# =============================================================================
# TASK TESTS
# =============================================================================

class TestVectorTasks:
    """Tests for vector task creation and execution."""

    @pytest.mark.asyncio
    async def test_create_task(self, gemini_power):
        """Test creating a vector task."""
        await gemini_power.initialize()

        task = gemini_power.create_task(
            task_type=VectorTaskType.QUERY,
            command="query",
            parameters={"query": "test query"},
            priority=8
        )

        assert task.id.startswith("vtask_")
        assert task.task_type == VectorTaskType.QUERY
        assert task.command == "query"
        assert task.priority == 8
        assert task.status == "pending"

    @pytest.mark.asyncio
    async def test_task_priority_ordering(self, gemini_power):
        """Test that tasks are ordered by priority."""
        await gemini_power.initialize()

        low = gemini_power.create_task(VectorTaskType.QUERY, "query", priority=3)
        high = gemini_power.create_task(VectorTaskType.QUERY, "query", priority=9)
        mid = gemini_power.create_task(VectorTaskType.QUERY, "query", priority=5)

        queue = gemini_power.queue
        assert queue[0].priority == 9
        assert queue[1].priority == 5
        assert queue[2].priority == 3

    @pytest.mark.asyncio
    async def test_execute_task_with_handler(self, gemini_power):
        """Test executing a task with a handler."""
        await gemini_power.initialize()

        task = gemini_power.create_task(
            task_type=VectorTaskType.EXECUTE,
            command="status",
            parameters={}
        )

        result = await gemini_power.execute_task(task)

        assert result.status == "completed"
        assert result.result is not None
        assert "version" in result.result

    @pytest.mark.asyncio
    async def test_execute_task_with_gemini(self, gemini_power, mock_gemini_client):
        """Test executing a task using Gemini."""
        await gemini_power.initialize()

        task = gemini_power.create_task(
            task_type=VectorTaskType.TRANSFORM,
            command="analyze",
            parameters={"content": "Test content", "focus": ""}
        )

        result = await gemini_power.execute_task(task)

        assert result.status == "completed"
        mock_gemini_client.generate_text.assert_called()

    @pytest.mark.asyncio
    async def test_process_queue(self, gemini_power):
        """Test processing the task queue."""
        await gemini_power.initialize()

        gemini_power.create_task(VectorTaskType.EXECUTE, "status", priority=5)
        gemini_power.create_task(VectorTaskType.EXECUTE, "status", priority=8)

        assert len(gemini_power.queue) == 2

        processed = await gemini_power.process_queue()

        assert len(processed) == 2
        assert len(gemini_power.queue) == 0
        assert all(t.status == "completed" for t in processed)


# =============================================================================
# HIGH-LEVEL API TESTS
# =============================================================================

class TestHighLevelAPI:
    """Tests for high-level API methods."""

    @pytest.mark.asyncio
    async def test_ask(self, gemini_power, mock_gemini_client):
        """Test the ask method."""
        await gemini_power.initialize()

        response = await gemini_power.ask("What is the theme?")

        assert response.success
        assert "OK" in response.content
        mock_gemini_client.generate_text.assert_called()

    @pytest.mark.asyncio
    async def test_ask_with_context(self, gemini_power, mock_gemini_client):
        """Test ask with context."""
        await gemini_power.initialize()

        response = await gemini_power.ask(
            "What is the theme?",
            context="This is a story about courage."
        )

        assert response.success
        call_args = mock_gemini_client.generate_text.call_args
        assert "Context:" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_execute_direct(self, gemini_power):
        """Test direct command execution."""
        await gemini_power.initialize()

        result = await gemini_power.execute("status")

        assert "version" in result
        assert "init_status" in result

    @pytest.mark.asyncio
    async def test_build(self, gemini_power):
        """Test build command."""
        await gemini_power.initialize()

        result = await gemini_power.build("all")

        assert result["target"] == "all"
        assert len(result["actions"]) > 0

    @pytest.mark.asyncio
    async def test_rebuild(self, gemini_power):
        """Test rebuild command."""
        await gemini_power.initialize()

        result = await gemini_power.rebuild()

        assert result["status"] == "rebuilt"
        assert gemini_power.is_ready


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================

class TestFactoryFunction:
    """Tests for the create_gemini_power factory function."""

    @pytest.mark.asyncio
    async def test_create_gemini_power_wait(self, temp_project_path, mock_gemini_client):
        """Test factory function with wait."""
        with patch('greenlight.omni_mind.gemini_power.GeminiClient', return_value=mock_gemini_client):
            power = await create_gemini_power(
                project_path=temp_project_path,
                wait_for_ready=True
            )

            assert power.is_ready


# =============================================================================
# SELF-GUIDANCE TESTS
# =============================================================================

from greenlight.omni_mind.self_guidance import (
    SelfGuidance, LLMPicker, GuidanceConfig, GuidanceMode, DecisionType,
    LLMRole, LLMSelection, Decision
)


@pytest.fixture
def guidance_config():
    """Create a guidance configuration."""
    return GuidanceConfig(
        mode=GuidanceMode.SUPERVISED,
        default_llm="gemini-flash",
        confidence_threshold=0.8
    )


@pytest.fixture
def self_guidance(temp_project_path, guidance_config):
    """Create a SelfGuidance instance."""
    return SelfGuidance(
        project_path=temp_project_path,
        config=guidance_config
    )


class TestLLMPicker:
    """Tests for LLM Picker."""

    def test_picker_initialization(self, guidance_config):
        """Test LLM picker initializes with defaults."""
        picker = LLMPicker(guidance_config)

        assignments = picker.get_assignments()
        assert "guidance" in assignments
        assert "analysis" in assignments
        assert "validation" in assignments

    def test_picker_default_gemini(self, guidance_config):
        """Test that Gemini 2.5 Flash is default for guidance."""
        picker = LLMPicker(guidance_config)

        guidance_llm = picker.get_llm_for_role(LLMRole.GUIDANCE)
        assert guidance_llm is not None
        # LLMConfig has llm_info.id or name attribute
        assert guidance_llm.llm_info.id == "gemini-flash" or guidance_llm.name == "Gemini 2.5 Flash"

    def test_set_llm_for_role(self, guidance_config):
        """Test setting LLM for a role."""
        picker = LLMPicker(guidance_config)

        result = picker.set_llm_for_role(LLMRole.ANALYSIS, "claude-sonnet")

        assert result == True
        analysis_llm = picker.get_llm_for_role(LLMRole.ANALYSIS)
        # LLMConfig has llm_info.id or name attribute
        assert analysis_llm.llm_info.id == "claude-sonnet" or "Sonnet" in analysis_llm.name

    def test_picker_to_dict(self, guidance_config):
        """Test picker serialization."""
        picker = LLMPicker(guidance_config)

        data = picker.to_dict()

        assert "default_llm" in data
        assert "assignments" in data
        assert "available_llms" in data


class TestSelfGuidance:
    """Tests for Self-Guidance System."""

    def test_guidance_initialization(self, self_guidance):
        """Test self-guidance initializes correctly."""
        assert self_guidance is not None
        assert self_guidance.config.mode == GuidanceMode.SUPERVISED
        assert self_guidance.config.default_llm == "gemini-flash"

    def test_get_mode(self, self_guidance):
        """Test getting guidance mode."""
        mode = self_guidance.get_mode()
        assert mode == "supervised"

    def test_set_mode(self, self_guidance):
        """Test setting guidance mode."""
        self_guidance.set_mode("autonomous")
        assert self_guidance.get_mode() == "autonomous"

    def test_get_llm_assignments(self, self_guidance):
        """Test getting LLM assignments."""
        assignments = self_guidance.get_llm_assignments()

        assert isinstance(assignments, dict)
        assert "guidance" in assignments

    def test_list_available_llms(self, self_guidance):
        """Test listing available LLMs."""
        llms = self_guidance.list_available_llms()

        assert isinstance(llms, list)
        assert len(llms) > 0
        assert all("id" in llm for llm in llms)
        assert all("name" in llm for llm in llms)

    def test_set_llm(self, self_guidance):
        """Test setting LLM for a role."""
        result = self_guidance.set_llm("analysis", "claude-haiku")

        assert result == True
        assignments = self_guidance.get_llm_assignments()
        assert assignments["analysis"] == "claude-haiku"

    def test_get_stats(self, self_guidance):
        """Test getting decision statistics."""
        stats = self_guidance.get_stats()

        assert "total_decisions" in stats
        assert "approved" in stats
        assert "rejected" in stats
        assert "pending" in stats
        assert "mode" in stats
        assert "default_llm" in stats

    def test_pending_approvals_empty(self, self_guidance):
        """Test pending approvals starts empty."""
        pending = self_guidance.get_pending_approvals()
        assert len(pending) == 0


class TestGuidanceConfig:
    """Tests for GuidanceConfig."""

    def test_config_defaults(self):
        """Test config default values."""
        config = GuidanceConfig()

        assert config.mode == GuidanceMode.SUPERVISED
        assert config.default_llm == "gemini-flash"
        assert config.confidence_threshold == 0.8
        assert config.learning_enabled == True

    def test_config_to_dict(self):
        """Test config serialization."""
        config = GuidanceConfig(
            mode=GuidanceMode.AUTONOMOUS,
            default_llm="claude-sonnet"
        )

        data = config.to_dict()

        assert data["mode"] == "autonomous"
        assert data["default_llm"] == "claude-sonnet"

    def test_config_from_dict(self):
        """Test config deserialization."""
        data = {
            "mode": "manual",
            "default_llm": "claude-haiku",
            "confidence_threshold": 0.9
        }

        config = GuidanceConfig.from_dict(data)

        assert config.mode == GuidanceMode.MANUAL
        assert config.default_llm == "claude-haiku"
        assert config.confidence_threshold == 0.9

