"""
Greenlight Core Module

Contains core systems including configuration, constants, exceptions, and logging.

OPTIMIZATIONS (v2.1):
- ProjectContext singleton for cached world config and scripts
"""

from .config import GreenlightConfig, load_config
from .constants import *
from .exceptions import *
from .logging_config import setup_logging, get_logger

# Project context singleton
from .project_context import (
    ProjectContext,
    CachedWorldConfig,
    get_project_context,
    set_project,
    get_world_config,
    get_script,
    get_visual_script,
    get_character,
    get_location,
    get_prop,
)

__all__ = [
    'GreenlightConfig',
    'load_config',
    'setup_logging',
    'get_logger',
    # Project Context
    'ProjectContext',
    'CachedWorldConfig',
    'get_project_context',
    'set_project',
    'get_world_config',
    'get_script',
    'get_visual_script',
    'get_character',
    'get_location',
    'get_prop',
]

