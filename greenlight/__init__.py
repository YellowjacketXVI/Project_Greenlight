"""
Project Greenlight - AI-Powered Cinematic Storyboard Generation Platform

A comprehensive platform for transforming creative ideas into production-ready
visual storytelling assets through AI-powered story development, shot planning,
and cinematic direction.

Now integrated with Agnostic_Core_OS as the first runtime-connected app.

Version: 2.1.0
"""

__version__ = "2.1.0"
__author__ = "Project Greenlight Team"
__project__ = "Project Greenlight"

from pathlib import Path

# Load environment variables early - before any other imports that might need them
from greenlight.core.env_loader import ensure_env_loaded
ensure_env_loaded()

# Package root directory
PACKAGE_ROOT = Path(__file__).parent
PROJECT_ROOT = PACKAGE_ROOT.parent

# Runtime Integration
from .runtime_integration import (
    GreenlightRuntimeBridge,
    PipelineType,
    PipelineStatus,
    PipelineProgress,
    get_runtime_bridge,
    connect_to_runtime,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__project__",
    # Paths
    "PACKAGE_ROOT",
    "PROJECT_ROOT",
    # Runtime Integration
    "GreenlightRuntimeBridge",
    "PipelineType",
    "PipelineStatus",
    "PipelineProgress",
    "get_runtime_bridge",
    "connect_to_runtime",
]

