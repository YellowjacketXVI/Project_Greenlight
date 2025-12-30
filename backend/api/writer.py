"""
Writer Pipeline API Routes
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import json

from backend.models.writer import (
    StartWriterInput, WriterInput, WriterOutput, LayerStatus, WriterLayer,
    ApprovalRequest, GenerateRequest, StreamChunk,
)
from backend.api.deps import get_current_user_id
from backend.core.supabase import get_supabase_client
from backend.core.logging import get_logger

router = APIRouter()
logger = get_logger("api.writer")


@router.post("/start", response_model=WriterOutput)
async def start_writing(
    input_data: StartWriterInput,
    user_id: str = Depends(get_current_user_id)
):
    """Start the writing pipeline for a project."""
    try:
        # Verify project ownership
        client = get_supabase_client()
        project = client.table("morphwrit_projects") \
            .select("*") \
            .eq("id", input_data.project_id) \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")

        # Initialize pipeline state
        layers = [
            LayerStatus(layer=WriterLayer.HIGH_LEVEL_OUTLINE, status="active"),
            LayerStatus(layer=WriterLayer.USER_CHECKPOINT_1, status="pending"),
            LayerStatus(layer=WriterLayer.GRANULAR_OUTLINE, status="pending"),
            LayerStatus(layer=WriterLayer.USER_CHECKPOINT_2, status="pending"),
            LayerStatus(layer=WriterLayer.SCALE_DETERMINATION, status="pending"),
            LayerStatus(layer=WriterLayer.WRITE_OUT, status="pending"),
        ]

        # Update project status
        client.table("morphwrit_projects") \
            .update({"status": "in_progress"}) \
            .eq("id", input_data.project_id) \
            .execute()

        return WriterOutput(
            project_id=input_data.project_id,
            current_layer=WriterLayer.HIGH_LEVEL_OUTLINE,
            layers=layers,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Start writing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to start writing")


@router.post("/generate")
async def generate_layer(
    request: GenerateRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Generate content for the current or specified layer."""
    try:
        # Import pipeline here to avoid circular imports
        from morpheus.pipelines import LayeredWriterPipeline, WriterInput as PipelineInput

        # Get project
        client = get_supabase_client()
        project = client.table("morphwrit_projects") \
            .select("*") \
            .eq("id", request.project_id) \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")

        # Create pipeline input
        pipeline_input = PipelineInput(
            prompt=project.data["prompt"],
            title=project.data["title"],
            genre=project.data.get("genre"),
            world_config=project.data.get("world_config"),
            project_id=request.project_id,
            user_id=user_id,
        )

        # Run pipeline - generate high-level outline
        pipeline = LayeredWriterPipeline(supabase_client=client)

        logger.info(f"Starting outline generation for project {request.project_id}")

        # Run the first step (high-level outline)
        result = await pipeline.run(pipeline_input)

        # Get the outline data from the result
        outline_content = {}
        if hasattr(result, 'outline') and result.outline:
            outline_content = {
                "title": result.title if hasattr(result, 'title') else project.data["title"],
                "acts": getattr(result.outline, 'acts', []),
                "themes": getattr(result.outline, 'themes', []),
            }
        elif isinstance(result, dict):
            outline_content = result.get("high_level_outline", result)

        # Save outline to database
        outline_data = {
            "project_id": request.project_id,
            "layer": 1,
            "content": outline_content,
            "status": "awaiting_approval"
        }

        # Check if outline already exists
        existing = client.table("morphwrit_outlines") \
            .select("id") \
            .eq("project_id", request.project_id) \
            .eq("layer", 1) \
            .execute()

        if existing.data:
            client.table("morphwrit_outlines") \
                .update({"content": outline_content, "status": "awaiting_approval"}) \
                .eq("project_id", request.project_id) \
                .eq("layer", 1) \
                .execute()
        else:
            client.table("morphwrit_outlines").insert(outline_data).execute()

        logger.info(f"Outline generated and saved for project {request.project_id}")

        return {
            "status": "completed",
            "message": "High-level outline generated",
            "layer": "high_level_outline",
            "content": outline_content
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate: {str(e)}")


@router.post("/approve")
async def approve_layer(
    request: ApprovalRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Approve or reject a layer's content."""
    try:
        client = get_supabase_client()

        # Verify project ownership
        project = client.table("morphwrit_projects") \
            .select("id") \
            .eq("id", request.project_id) \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")

        # Update outline status
        status = "approved" if request.approved else "rejected"
        layer_num = list(WriterLayer).index(request.layer) + 1

        client.table("morphwrit_outlines") \
            .update({
                "status": status,
                "feedback": request.feedback,
            }) \
            .eq("project_id", request.project_id) \
            .eq("layer", layer_num) \
            .execute()

        return {
            "status": status,
            "layer": request.layer,
            "next_layer": _get_next_layer(request.layer) if request.approved else request.layer
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approve error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process approval")


def _get_next_layer(current: WriterLayer) -> WriterLayer:
    """Get the next layer in the pipeline."""
    layers = list(WriterLayer)
    idx = layers.index(current)
    if idx < len(layers) - 1:
        return layers[idx + 1]
    return current

