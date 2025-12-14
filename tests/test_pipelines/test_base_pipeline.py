"""
Tests for Base Pipeline Module

Tests for greenlight/pipelines/base_pipeline.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from greenlight.pipelines.base_pipeline import (
    BasePipeline,
    PipelineStep,
    PipelineResult,
    PipelineStatus
)


class MockPipeline(BasePipeline):
    """Mock pipeline for testing."""
    
    def __init__(self):
        super().__init__("mock_pipeline")
        self._steps = [
            PipelineStep("step1", self._step1),
            PipelineStep("step2", self._step2),
            PipelineStep("step3", self._step3),
        ]
    
    async def _step1(self, data):
        return {"step1_result": data.get("input", "") + "_step1"}
    
    async def _step2(self, data):
        return {"step2_result": data.get("step1_result", "") + "_step2"}
    
    async def _step3(self, data):
        return {"step3_result": data.get("step2_result", "") + "_step3"}
    
    def get_steps(self):
        return self._steps


class TestPipelineStep:
    """Tests for PipelineStep class."""
    
    def test_step_creation(self):
        """Test creating a pipeline step."""
        async def dummy_func(data):
            return data
        
        step = PipelineStep("test_step", dummy_func)
        
        assert step.name == "test_step"
        assert step.func == dummy_func
    
    def test_step_with_description(self):
        """Test step with description."""
        async def dummy_func(data):
            return data
        
        step = PipelineStep(
            "test_step",
            dummy_func,
            description="A test step"
        )
        
        assert step.description == "A test step"


class TestPipelineResult:
    """Tests for PipelineResult class."""
    
    def test_success_result(self):
        """Test successful result."""
        result = PipelineResult(
            status=PipelineStatus.SUCCESS,
            data={"output": "test"},
            steps_completed=3
        )
        
        assert result.status == PipelineStatus.SUCCESS
        assert result.data["output"] == "test"
        assert result.steps_completed == 3
    
    def test_failure_result(self):
        """Test failure result."""
        result = PipelineResult(
            status=PipelineStatus.FAILED,
            error="Something went wrong",
            steps_completed=1
        )
        
        assert result.status == PipelineStatus.FAILED
        assert result.error == "Something went wrong"
        assert result.steps_completed == 1
    
    def test_result_is_success(self):
        """Test is_success property."""
        success = PipelineResult(status=PipelineStatus.SUCCESS)
        failure = PipelineResult(status=PipelineStatus.FAILED)
        
        assert success.is_success is True
        assert failure.is_success is False


class TestBasePipeline:
    """Tests for BasePipeline class."""
    
    @pytest.mark.asyncio
    async def test_run_pipeline(self):
        """Test running a pipeline."""
        pipeline = MockPipeline()
        
        result = await pipeline.run({"input": "test"})
        
        assert result.status == PipelineStatus.SUCCESS
        assert result.steps_completed == 3
    
    @pytest.mark.asyncio
    async def test_pipeline_data_flow(self):
        """Test data flows through pipeline steps."""
        pipeline = MockPipeline()
        
        result = await pipeline.run({"input": "data"})
        
        assert "step3_result" in result.data
        assert result.data["step3_result"] == "data_step1_step2_step3"
    
    def test_pipeline_name(self):
        """Test pipeline name."""
        pipeline = MockPipeline()
        
        assert pipeline.name == "mock_pipeline"
    
    def test_get_steps(self):
        """Test getting pipeline steps."""
        pipeline = MockPipeline()
        
        steps = pipeline.get_steps()
        
        assert len(steps) == 3
        assert steps[0].name == "step1"
        assert steps[1].name == "step2"
        assert steps[2].name == "step3"


class TestPipelineStatus:
    """Tests for PipelineStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert PipelineStatus.PENDING.value == "pending"
        assert PipelineStatus.RUNNING.value == "running"
        assert PipelineStatus.SUCCESS.value == "success"
        assert PipelineStatus.FAILED.value == "failed"
        assert PipelineStatus.CANCELLED.value == "cancelled"

