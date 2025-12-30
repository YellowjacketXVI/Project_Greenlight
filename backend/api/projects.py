"""
Projects API Routes
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List

from backend.models.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    OutlineCreate, OutlineResponse,
    DraftCreate, DraftResponse,
)
from backend.api.deps import get_current_user_id
from backend.core.supabase import get_supabase_client
from backend.core.logging import get_logger

router = APIRouter()
logger = get_logger("api.projects")


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(user_id: str = Depends(get_current_user_id)):
    """List all projects for current user."""
    try:
        client = get_supabase_client()
        response = client.table("morphwrit_projects") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("updated_at", desc=True) \
            .execute()

        return response.data or []

    except Exception as e:
        logger.error(f"List projects error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list projects")


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    user_id: str = Depends(get_current_user_id)
):
    """Create a new project."""
    try:
        client = get_supabase_client()
        response = client.table("morphwrit_projects").insert({
            "user_id": user_id,
            "title": project.title,
            "prompt": project.prompt,
            "genre": project.genre,
            "status": "draft",
            "world_config": project.world_config or {}
        }).execute()

        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to create project")

        return response.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create project error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create project")


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Get a specific project."""
    try:
        client = get_supabase_client()
        response = client.table("morphwrit_projects") \
            .select("*") \
            .eq("id", project_id) \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Project not found")

        return response.data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get project error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get project")


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    updates: ProjectUpdate,
    user_id: str = Depends(get_current_user_id)
):
    """Update a project."""
    try:
        client = get_supabase_client()

        update_data = updates.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No updates provided")

        response = client.table("morphwrit_projects") \
            .update(update_data) \
            .eq("id", project_id) \
            .eq("user_id", user_id) \
            .execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Project not found")

        return response.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update project error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update project")


# Outlines endpoints
@router.get("/{project_id}/outlines", response_model=List[OutlineResponse])
async def get_outlines(
    project_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Get all outlines for a project."""
    try:
        # Verify project ownership first
        client = get_supabase_client()
        project = client.table("morphwrit_projects") \
            .select("id") \
            .eq("id", project_id) \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")

        response = client.table("morphwrit_outlines") \
            .select("*") \
            .eq("project_id", project_id) \
            .order("layer") \
            .execute()

        return response.data or []

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get outlines error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get outlines")

