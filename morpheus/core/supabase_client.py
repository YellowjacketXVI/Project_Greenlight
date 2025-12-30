"""
Supabase Client for Morpheus Writ

Handles authentication and database operations.
"""

import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from .logging_config import get_logger
from .env_loader import load_env_file

logger = get_logger("core.supabase")

# Load env on import
load_env_file()

# Supabase configuration
SUPABASE_URL = "https://lhliiwgmksdygnwhrjft.supabase.co"
SUPABASE_ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxobGlpd2dta3NkeWdud2hyamZ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY5ODA4MTIsImV4cCI6MjA4MjU1NjgxMn0.aWwtL24pgNsspn4I9-2QTezLGAmA-rllKPxeyqY4B2M"
)


@dataclass
class User:
    """Authenticated user."""
    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class SupabaseClient:
    """Client for Supabase authentication and database operations."""

    def __init__(self):
        self._client = None
        self._user: Optional[User] = None
        self._session = None
        self._init_client()

    def _init_client(self):
        """Initialize the Supabase client."""
        try:
            from supabase import create_client, Client
            self._client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            logger.info("Supabase client initialized")
        except ImportError:
            logger.error("supabase-py not installed. Run: pip install supabase")
            self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize Supabase: {e}")
            self._client = None

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self._user is not None

    @property
    def user(self) -> Optional[User]:
        """Get current user."""
        return self._user

    async def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        """Sign up a new user."""
        if not self._client:
            return {"error": "Supabase client not initialized"}

        try:
            response = self._client.auth.sign_up({
                "email": email,
                "password": password
            })

            if response.user:
                self._user = User(
                    id=response.user.id,
                    email=response.user.email,
                    display_name=response.user.user_metadata.get("display_name")
                )
                self._session = response.session
                logger.info(f"User signed up: {email}")
                return {"success": True, "user": self._user}
            else:
                return {"error": "Sign up failed"}

        except Exception as e:
            logger.error(f"Sign up error: {e}")
            return {"error": str(e)}

    async def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in an existing user."""
        if not self._client:
            return {"error": "Supabase client not initialized"}

        try:
            response = self._client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if response.user:
                self._user = User(
                    id=response.user.id,
                    email=response.user.email,
                    display_name=response.user.user_metadata.get("display_name")
                )
                self._session = response.session
                logger.info(f"User signed in: {email}")
                return {"success": True, "user": self._user}
            else:
                return {"error": "Sign in failed"}

        except Exception as e:
            logger.error(f"Sign in error: {e}")
            return {"error": str(e)}



    # =========================================================================
    # PROJECT OPERATIONS
    # =========================================================================

    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects for the current user."""
        if not self._client or not self._user:
            return []

        try:
            response = self._client.table("morphwrit_projects") \
                .select("*") \
                .eq("user_id", self._user.id) \
                .order("updated_at", desc=True) \
                .execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get projects: {e}")
            return []

    async def create_project(
        self,
        title: str,
        prompt: str,
        genre: Optional[str] = None,
        world_config: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new project."""
        if not self._client or not self._user:
            return None

        try:
            response = self._client.table("morphwrit_projects").insert({
                "user_id": self._user.id,
                "title": title,
                "prompt": prompt,
                "genre": genre,
                "status": "draft",
                "world_config": world_config or {}
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return None

    async def update_project(
        self,
        project_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a project."""
        if not self._client or not self._user:
            return None

        try:
            response = self._client.table("morphwrit_projects") \
                .update(updates) \
                .eq("id", project_id) \
                .eq("user_id", self._user.id) \
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to update project: {e}")
            return None

    async def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific project."""
        if not self._client or not self._user:
            return None

        try:
            response = self._client.table("morphwrit_projects") \
                .select("*") \
                .eq("id", project_id) \
                .eq("user_id", self._user.id) \
                .single() \
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to get project: {e}")
            return None

    # =========================================================================
    # OUTLINE OPERATIONS
    # =========================================================================

    async def save_outline(
        self,
        project_id: str,
        layer: int,
        content: Dict[str, Any],
        status: str = "draft"
    ) -> Optional[Dict[str, Any]]:
        """Save an outline for a project."""
        if not self._client or not self._user:
            return None

        try:
            response = self._client.table("morphwrit_outlines").upsert({
                "project_id": project_id,
                "layer": layer,
                "content": content,
                "status": status
            }, on_conflict="project_id,layer").execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to save outline: {e}")
            return None

    async def get_outlines(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all outlines for a project."""
        if not self._client or not self._user:
            return []

        try:
            response = self._client.table("morphwrit_outlines") \
                .select("*") \
                .eq("project_id", project_id) \
                .order("layer") \
                .execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get outlines: {e}")
            return []

    # =========================================================================
    # DRAFT OPERATIONS
    # =========================================================================

    async def save_draft(
        self,
        project_id: str,
        scene_id: str,
        content: str,
        version: int = 1
    ) -> Optional[Dict[str, Any]]:
        """Save a draft scene."""
        if not self._client or not self._user:
            return None

        try:
            response = self._client.table("morphwrit_drafts").upsert({
                "project_id": project_id,
                "scene_id": scene_id,
                "content": content,
                "version": version
            }, on_conflict="project_id,scene_id").execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to save draft: {e}")
            return None

    async def get_drafts(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all drafts for a project."""
        if not self._client or not self._user:
            return []

        try:
            response = self._client.table("morphwrit_drafts") \
                .select("*") \
                .eq("project_id", project_id) \
                .order("scene_id") \
                .execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get drafts: {e}")
            return []


# Global client instance
_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """Get the global Supabase client instance."""
    global _client
    if _client is None:
        _client = SupabaseClient()
    return _client

