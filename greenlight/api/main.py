"""Main FastAPI application for Project Greenlight."""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from greenlight.api.routers import projects, pipelines, images

app = FastAPI(
    title="Project Greenlight API",
    description="API for AI-powered cinematic storyboard generation",
    version="1.0.0",
)

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
app.include_router(images.router, prefix="/api/images", tags=["images"])


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
    )


if __name__ == "__main__":
    start_server()

