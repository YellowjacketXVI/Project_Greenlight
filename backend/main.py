"""
Morpheus Writ FastAPI Backend

Main application entry point with ASGI server.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from backend.core.config import settings
from backend.core.logging import setup_logging, get_logger
from backend.api import auth, projects, writer, health

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Morpheus Writ API...")
    yield
    logger.info("Shutting down Morpheus Writ API...")


app = FastAPI(
    title="Morpheus Writ API",
    description="AI-Powered Story Writing Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(writer.router, prefix="/api/writer", tags=["Writer"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Morpheus Writ API",
        "version": "1.0.0",
        "status": "running"
    }


def run():
    """Run the server."""
    setup_logging()
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )


if __name__ == "__main__":
    run()

