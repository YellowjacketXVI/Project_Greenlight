"""Main FastAPI application for Project Greenlight."""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Load environment variables using centralized loader
from greenlight.core.env_loader import ensure_env_loaded
ensure_env_loaded()

from greenlight.api.routers import projects, pipelines, images, settings, sse

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Project Greenlight API",
    description="API for AI-powered cinematic storyboard generation",
    version="3.0.0",
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware for web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(pipelines.router, prefix="/api/pipelines", tags=["pipelines"])
app.include_router(sse.router, prefix="/api/pipelines", tags=["sse"])
app.include_router(images.router, prefix="/api/images", tags=["images"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Project Greenlight API", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Start the FastAPI server."""
    uvicorn.run(
        "greenlight.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="warning",  # Suppress INFO logs for each request
    )


if __name__ == "__main__":
    start_server()

