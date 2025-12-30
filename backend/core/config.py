"""
Backend Configuration

Pydantic settings for the FastAPI backend.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = Field(default=True)

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # Supabase
    supabase_url: str = Field(
        default="https://lhliiwgmksdygnwhrjft.supabase.co"
    )
    supabase_anon_key: str = Field(
        default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxobGlpd2dta3NkeWdud2hyamZ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY5ODA4MTIsImV4cCI6MjA4MjU1NjgxMn0.aWwtL24pgNsspn4I9-2QTezLGAmA-rllKPxeyqY4B2M"
    )
    supabase_service_key: str = Field(default="")

    # LLM API Keys
    anthropic_api_key: str = Field(default="")
    google_api_key: str = Field(default="")
    xai_api_key: str = Field(default="")

    # JWT
    jwt_secret: str = Field(default="morpheus-writ-secret-key-change-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiry_hours: int = Field(default=24)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

