"""
Supabase Client for Backend

Async Supabase client for FastAPI.
"""

from supabase import create_client, Client
from functools import lru_cache
from typing import Optional

from .config import settings
from .logging import get_logger

logger = get_logger("supabase")


@lru_cache()
def get_supabase_client() -> Client:
    """Get Supabase client with anon key (for user operations)."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)


@lru_cache()
def get_supabase_admin() -> Optional[Client]:
    """Get Supabase client with service key (for admin operations)."""
    if not settings.supabase_service_key:
        logger.warning("No service key configured - admin operations disabled")
        return None
    return create_client(settings.supabase_url, settings.supabase_service_key)

