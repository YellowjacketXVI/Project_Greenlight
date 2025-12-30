"""
API Dependencies

Common dependencies for route handlers.
"""

from fastapi import Header, HTTPException, Depends
from typing import Optional

from backend.core.supabase import get_supabase_client
from backend.core.logging import get_logger

logger = get_logger("api.deps")


async def get_current_user_id(authorization: str = Header(...)) -> str:
    """Extract and validate user ID from authorization header."""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid token format")

        token = authorization.replace("Bearer ", "")
        client = get_supabase_client()
        response = client.auth.get_user(token)

        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid token")

        return response.user.id

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


async def get_optional_user_id(
    authorization: Optional[str] = Header(None)
) -> Optional[str]:
    """Get user ID if authenticated, None otherwise."""
    if not authorization:
        return None

    try:
        return await get_current_user_id(authorization)
    except HTTPException:
        return None

