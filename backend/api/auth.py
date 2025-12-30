"""
Authentication API Routes
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional

from backend.models.auth import UserCreate, UserLogin, UserResponse, TokenResponse
from backend.core.supabase import get_supabase_client
from backend.core.logging import get_logger

router = APIRouter()
logger = get_logger("api.auth")


@router.post("/signup", response_model=TokenResponse)
async def signup(user: UserCreate):
    """Register a new user."""
    try:
        client = get_supabase_client()
        response = client.auth.sign_up({
            "email": user.email,
            "password": user.password,
            "options": {
                "data": {"display_name": user.display_name}
            }
        })

        if not response.user:
            raise HTTPException(status_code=400, detail="Signup failed")

        return TokenResponse(
            access_token=response.session.access_token,
            expires_in=response.session.expires_in,
            refresh_token=response.session.refresh_token,
            user=UserResponse(
                id=response.user.id,
                email=response.user.email,
                display_name=user.display_name,
            )
        )

    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login with email and password."""
    try:
        client = get_supabase_client()
        response = client.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })

        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        return TokenResponse(
            access_token=response.session.access_token,
            expires_in=response.session.expires_in,
            refresh_token=response.session.refresh_token,
            user=UserResponse(
                id=response.user.id,
                email=response.user.email,
                display_name=response.user.user_metadata.get("display_name"),
            )
        )

    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """Logout current user."""
    try:
        client = get_supabase_client()
        client.auth.sign_out()
        return {"message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_current_user(authorization: str = Header(...)):
    """Get current authenticated user."""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid token format")

        token = authorization.replace("Bearer ", "")
        client = get_supabase_client()
        response = client.auth.get_user(token)

        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid token")

        return UserResponse(
            id=response.user.id,
            email=response.user.email,
            display_name=response.user.user_metadata.get("display_name"),
            created_at=response.user.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """Refresh access token."""
    try:
        client = get_supabase_client()
        response = client.auth.refresh_session(refresh_token)

        if not response.session:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        return TokenResponse(
            access_token=response.session.access_token,
            expires_in=response.session.expires_in,
            refresh_token=response.session.refresh_token,
            user=UserResponse(
                id=response.user.id,
                email=response.user.email,
            )
        )

    except Exception as e:
        logger.error(f"Refresh error: {e}")
        raise HTTPException(status_code=401, detail="Token refresh failed")

