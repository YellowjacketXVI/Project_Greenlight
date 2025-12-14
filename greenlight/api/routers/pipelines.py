"""Pipelines router for Project Greenlight API."""

import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()

# Store for pipeline status
pipeline_status: dict[str, dict] = {}


class PipelineRequest(BaseModel):
    project_path: str
    llm: Optional[str] = "claude-sonnet-4.5"
    image_model: Optional[str] = "seedream"
    max_frames: Optional[int] = None


class PipelineStatus(BaseModel):
    name: str
    status: str  # idle, running, completed, error
    progress: float
    message: Optional[str] = None


class PipelineResponse(BaseModel):
    success: bool
    message: str
    pipeline_id: Optional[str] = None


@router.get("/status/{pipeline_name}", response_model=PipelineStatus)
async def get_pipeline_status(pipeline_name: str):
    """Get status of a pipeline."""
    if pipeline_name in pipeline_status:
        return PipelineStatus(**pipeline_status[pipeline_name])
    return PipelineStatus(name=pipeline_name, status="idle", progress=0)


@router.post("/writer", response_model=PipelineResponse)
async def run_writer_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the Writer pipeline."""
    pipeline_id = f"writer_{request.project_path}"
    pipeline_status["writer"] = {"name": "writer", "status": "running", "progress": 0, "message": "Starting..."}
    background_tasks.add_task(execute_writer_pipeline, request.project_path, request.llm)
    return PipelineResponse(success=True, message="Writer pipeline started", pipeline_id=pipeline_id)


@router.post("/director", response_model=PipelineResponse)
async def run_director_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the Director pipeline."""
    pipeline_id = f"director_{request.project_path}"
    pipeline_status["director"] = {"name": "director", "status": "running", "progress": 0, "message": "Starting..."}
    background_tasks.add_task(execute_director_pipeline, request.project_path, request.llm, request.max_frames)
    return PipelineResponse(success=True, message="Director pipeline started", pipeline_id=pipeline_id)


@router.post("/references", response_model=PipelineResponse)
async def run_references_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the References pipeline."""
    pipeline_id = f"references_{request.project_path}"
    pipeline_status["references"] = {"name": "references", "status": "running", "progress": 0, "message": "Starting..."}
    background_tasks.add_task(execute_references_pipeline, request.project_path, request.image_model)
    return PipelineResponse(success=True, message="References pipeline started", pipeline_id=pipeline_id)


@router.post("/storyboard", response_model=PipelineResponse)
async def run_storyboard_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the Storyboard pipeline."""
    pipeline_id = f"storyboard_{request.project_path}"
    pipeline_status["storyboard"] = {"name": "storyboard", "status": "running", "progress": 0, "message": "Starting..."}
    background_tasks.add_task(execute_storyboard_pipeline, request.project_path, request.image_model, request.max_frames)
    return PipelineResponse(success=True, message="Storyboard pipeline started", pipeline_id=pipeline_id)


async def execute_writer_pipeline(project_path: str, llm: str):
    """Execute the Writer pipeline."""
    try:
        pipeline_status["writer"]["message"] = "Running Writer pipeline..."
        pipeline_status["writer"]["progress"] = 10
        # TODO: Import and run actual pipeline
        # from greenlight.pipelines.story_pipeline import StoryPipeline
        await asyncio.sleep(2)  # Placeholder
        pipeline_status["writer"]["progress"] = 100
        pipeline_status["writer"]["status"] = "completed"
        pipeline_status["writer"]["message"] = "Writer pipeline completed"
    except Exception as e:
        pipeline_status["writer"]["status"] = "error"
        pipeline_status["writer"]["message"] = str(e)


async def execute_director_pipeline(project_path: str, llm: str, max_frames: Optional[int]):
    """Execute the Director pipeline."""
    try:
        pipeline_status["director"]["message"] = "Running Director pipeline..."
        pipeline_status["director"]["progress"] = 10
        await asyncio.sleep(2)  # Placeholder
        pipeline_status["director"]["progress"] = 100
        pipeline_status["director"]["status"] = "completed"
        pipeline_status["director"]["message"] = "Director pipeline completed"
    except Exception as e:
        pipeline_status["director"]["status"] = "error"
        pipeline_status["director"]["message"] = str(e)


async def execute_references_pipeline(project_path: str, image_model: str):
    """Execute the References pipeline."""
    try:
        pipeline_status["references"]["message"] = "Generating reference images..."
        pipeline_status["references"]["progress"] = 10
        await asyncio.sleep(2)  # Placeholder
        pipeline_status["references"]["progress"] = 100
        pipeline_status["references"]["status"] = "completed"
        pipeline_status["references"]["message"] = "References pipeline completed"
    except Exception as e:
        pipeline_status["references"]["status"] = "error"
        pipeline_status["references"]["message"] = str(e)


async def execute_storyboard_pipeline(project_path: str, image_model: str, max_frames: Optional[int]):
    """Execute the Storyboard pipeline."""
    try:
        pipeline_status["storyboard"]["message"] = "Generating storyboard frames..."
        pipeline_status["storyboard"]["progress"] = 10
        await asyncio.sleep(2)  # Placeholder
        pipeline_status["storyboard"]["progress"] = 100
        pipeline_status["storyboard"]["status"] = "completed"
        pipeline_status["storyboard"]["message"] = "Storyboard pipeline completed"
    except Exception as e:
        pipeline_status["storyboard"]["status"] = "error"
        pipeline_status["storyboard"]["message"] = str(e)

