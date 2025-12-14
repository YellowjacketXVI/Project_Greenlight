"""Core platform infrastructure for Agnostic_Core_OS."""

from .platform import AgnosticCorePlatform
from .context_logger import TokenEfficientLogger, ContextReport
from .file_ops import FileOperations, FileInfo, get_file_ops
from .process_runner import (
    ProcessRunner,
    ProcessResult,
    ProcessStatus,
    get_process_runner,
)
from .vector_auth import (
    VectorKeyAuth,
    VectorKey,
    AccessLevel,
    AuthResult,
    get_vector_auth,
)
from .core_lock import (
    CoreLock,
    CoreFile,
    CoreScope,
    Capability,
    CORE_FILES,
    CORE_GUIDELINES,
    get_core_lock,
)

__all__ = [
    # Platform
    "AgnosticCorePlatform",
    # Logging
    "TokenEfficientLogger",
    "ContextReport",
    # File Operations
    "FileOperations",
    "FileInfo",
    "get_file_ops",
    # Process Runner
    "ProcessRunner",
    "ProcessResult",
    "ProcessStatus",
    "get_process_runner",
    # Vector Auth
    "VectorKeyAuth",
    "VectorKey",
    "AccessLevel",
    "AuthResult",
    "get_vector_auth",
    # Core Lock
    "CoreLock",
    "CoreFile",
    "CoreScope",
    "Capability",
    "CORE_FILES",
    "CORE_GUIDELINES",
    "get_core_lock",
]
