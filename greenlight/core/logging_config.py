"""
Greenlight Logging Configuration

Structured logging setup with verbose options for debugging and monitoring.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


# Custom log format
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
VERBOSE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(funcName)s | %(message)s"
SIMPLE_FORMAT = "%(levelname)s: %(message)s"

# Logger registry
_loggers: dict = {}
_initialized: bool = False
_log_file: Optional[Path] = None


def setup_logging(
    level: LogLevel = LogLevel.INFO,
    log_file: Optional[Path] = None,
    verbose: bool = True,
    console_output: bool = True
) -> None:
    """
    Set up logging configuration for the entire application.
    
    Args:
        level: Minimum log level to capture
        log_file: Optional path to log file
        verbose: If True, use verbose format with line numbers
        console_output: If True, output to console
    """
    global _initialized, _log_file
    
    # Get root logger for greenlight
    root_logger = logging.getLogger("greenlight")
    root_logger.setLevel(level.value)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Choose format
    log_format = VERBOSE_FORMAT if verbose else DEFAULT_FORMAT
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level.value)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        _log_file = Path(log_file)
        _log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(_log_file, encoding='utf-8')
        file_handler.setLevel(level.value)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    _initialized = True
    root_logger.info(f"Logging initialized - Level: {level.name}, Verbose: {verbose}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Name of the module/component
        
    Returns:
        Configured logger instance
    """
    global _loggers
    
    # Ensure logging is initialized
    if not _initialized:
        setup_logging()
    
    # Create namespaced logger
    full_name = f"greenlight.{name}" if not name.startswith("greenlight") else name
    
    if full_name not in _loggers:
        _loggers[full_name] = logging.getLogger(full_name)
    
    return _loggers[full_name]


class LogContext:
    """Context manager for temporary log level changes."""
    
    def __init__(self, logger: logging.Logger, level: LogLevel):
        self.logger = logger
        self.new_level = level.value
        self.old_level = logger.level
    
    def __enter__(self):
        self.logger.setLevel(self.new_level)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.old_level)
        return False


def log_function_call(logger: logging.Logger):
    """Decorator to log function entry and exit."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Entering {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Exiting {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise
        return wrapper
    return decorator


def create_session_log(base_dir: Path, prefix: str = "session") -> Path:
    """
    Create a new session log file with timestamp.

    Args:
        base_dir: Directory to create log file in
        prefix: Prefix for log file name

    Returns:
        Path to created log file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = base_dir / f"{prefix}_{timestamp}.log"
    setup_logging(log_file=log_file)
    return log_file


class SelfCorrectionHandler(logging.Handler):
    """
    Custom logging handler that intercepts warning messages and triggers
    self-correction for known issues like missing characters.
    """

    def __init__(self, level=logging.WARNING):
        super().__init__(level)
        self._watcher = None

    def emit(self, record: logging.LogRecord) -> None:
        """Process a log record and check for self-correction triggers."""
        try:
            # Only process warnings and errors
            if record.levelno < logging.WARNING:
                return

            message = self.format(record)

            # Lazy import to avoid circular imports
            if self._watcher is None:
                try:
                    from greenlight.omni_mind.process_monitor import get_character_watcher
                    self._watcher = get_character_watcher()
                except ImportError:
                    return

            # Check if this message triggers self-correction
            if self._watcher:
                self._watcher.check_log_message(message)

        except Exception:
            # Don't let handler errors break logging
            pass


def enable_self_correction(project_path: Path = None, auto_fix: bool = True) -> None:
    """
    Enable self-correction by adding the SelfCorrectionHandler to the logger.

    Args:
        project_path: Path to the current project
        auto_fix: Whether to automatically fix detected issues
    """
    root_logger = logging.getLogger("greenlight")

    # Check if handler already exists
    for handler in root_logger.handlers:
        if isinstance(handler, SelfCorrectionHandler):
            return

    # Add the self-correction handler
    handler = SelfCorrectionHandler(level=logging.WARNING)
    handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
    root_logger.addHandler(handler)

    # Setup the character watcher
    try:
        from greenlight.omni_mind.process_monitor import setup_character_watcher
        setup_character_watcher(project_path=project_path, auto_fix=auto_fix)
    except ImportError:
        pass

    root_logger.info("Self-correction handler enabled")

