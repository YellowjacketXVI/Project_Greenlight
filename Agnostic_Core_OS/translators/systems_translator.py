"""
Systems Translator Index - OS Recognition & Self-Building Parameters

Provides operating system recognition, architecture detection, and
self-building parameter configuration based on the detected environment.

Features:
- OS detection (Windows, macOS, Linux, BSD, etc.)
- Architecture detection (x86, x64, ARM, ARM64)
- Python environment detection
- Self-building parameter generation
- Platform-specific command translation
- Resource limit detection
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from datetime import datetime
from pathlib import Path
import sys
import os
import platform
import json


class OSType(Enum):
    """Operating system types."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    BSD = "bsd"
    UNKNOWN = "unknown"


class Architecture(Enum):
    """CPU architecture types."""
    X86 = "x86"
    X64 = "x64"
    ARM = "arm"
    ARM64 = "arm64"
    UNKNOWN = "unknown"


class ShellType(Enum):
    """Shell types for command execution."""
    POWERSHELL = "powershell"
    CMD = "cmd"
    BASH = "bash"
    ZSH = "zsh"
    SH = "sh"
    UNKNOWN = "unknown"


@dataclass
class SystemInfo:
    """Detected system information."""
    os_type: OSType
    os_name: str
    os_version: str
    architecture: Architecture
    machine: str
    python_version: str
    python_implementation: str
    shell_type: ShellType
    home_dir: Path
    temp_dir: Path
    cpu_count: int
    memory_available: Optional[int] = None
    is_virtual: bool = False
    is_container: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "os_type": self.os_type.value,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "architecture": self.architecture.value,
            "machine": self.machine,
            "python_version": self.python_version,
            "python_implementation": self.python_implementation,
            "shell_type": self.shell_type.value,
            "home_dir": str(self.home_dir),
            "temp_dir": str(self.temp_dir),
            "cpu_count": self.cpu_count,
            "memory_available": self.memory_available,
            "is_virtual": self.is_virtual,
            "is_container": self.is_container,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class BuildParameters:
    """Self-building parameters based on system architecture."""
    parallel_workers: int
    max_memory_mb: int
    chunk_size: int
    temp_dir: Path
    cache_dir: Path
    log_dir: Path
    shell_command_prefix: List[str]
    path_separator: str
    line_ending: str
    file_encoding: str
    async_io_enabled: bool
    multiprocessing_enabled: bool
    gpu_available: bool
    recommended_batch_size: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "parallel_workers": self.parallel_workers,
            "max_memory_mb": self.max_memory_mb,
            "chunk_size": self.chunk_size,
            "temp_dir": str(self.temp_dir),
            "cache_dir": str(self.cache_dir),
            "log_dir": str(self.log_dir),
            "shell_command_prefix": self.shell_command_prefix,
            "path_separator": self.path_separator,
            "line_ending": repr(self.line_ending),
            "file_encoding": self.file_encoding,
            "async_io_enabled": self.async_io_enabled,
            "multiprocessing_enabled": self.multiprocessing_enabled,
            "gpu_available": self.gpu_available,
            "recommended_batch_size": self.recommended_batch_size
        }


@dataclass
class CommandTranslation:
    """Platform-specific command translation."""
    generic_command: str
    windows_command: str
    unix_command: str
    description: str

    def get_for_os(self, os_type: OSType) -> str:
        """Get command for specific OS."""
        if os_type == OSType.WINDOWS:
            return self.windows_command
        return self.unix_command


class SystemsTranslatorIndex:
    """
    Systems Translator Index - OS Recognition & Self-Building Parameters.

    Detects the operating system, architecture, and environment to
    automatically configure platform-specific parameters.

    Example:
        translator = SystemsTranslatorIndex()

        # Get system info
        info = translator.get_system_info()
        print(f"OS: {info.os_type.value}, Arch: {info.architecture.value}")

        # Get build parameters
        params = translator.get_build_parameters()
        print(f"Workers: {params.parallel_workers}")

        # Translate commands
        cmd = translator.translate_command("list_files")
        print(f"Command: {cmd}")
    """

    # Command translation index
    COMMAND_INDEX: Dict[str, CommandTranslation] = {
        "list_files": CommandTranslation(
            "list_files", "dir", "ls -la", "List files in directory"
        ),
        "make_dir": CommandTranslation(
            "make_dir", "mkdir", "mkdir -p", "Create directory"
        ),
        "remove_dir": CommandTranslation(
            "remove_dir", "rmdir /s /q", "rm -rf", "Remove directory"
        ),
        "copy_file": CommandTranslation(
            "copy_file", "copy", "cp", "Copy file"
        ),
        "move_file": CommandTranslation(
            "move_file", "move", "mv", "Move file"
        ),
        "delete_file": CommandTranslation(
            "delete_file", "del", "rm", "Delete file"
        ),
        "find_files": CommandTranslation(
            "find_files", "dir /s /b", "find . -name", "Find files"
        ),
        "grep_text": CommandTranslation(
            "grep_text", "findstr", "grep", "Search text in files"
        ),
        "cat_file": CommandTranslation(
            "cat_file", "type", "cat", "Display file contents"
        ),
        "clear_screen": CommandTranslation(
            "clear_screen", "cls", "clear", "Clear terminal"
        ),
        "env_var": CommandTranslation(
            "env_var", "echo %VAR%", "echo $VAR", "Print environment variable"
        ),
        "set_env": CommandTranslation(
            "set_env", "set VAR=value", "export VAR=value", "Set environment variable"
        ),
        "python_run": CommandTranslation(
            "python_run", "py", "python3", "Run Python"
        ),
        "pip_install": CommandTranslation(
            "pip_install", "py -m pip install", "pip3 install", "Install pip package"
        ),
        "open_file": CommandTranslation(
            "open_file", "start", "xdg-open", "Open file with default app"
        ),
        "open_folder": CommandTranslation(
            "open_folder", "explorer", "xdg-open", "Open folder in file manager"
        ),
    }

    def __init__(self, project_path: Optional[Path] = None):
        """Initialize the Systems Translator Index."""
        self.project_path = project_path
        self._system_info: Optional[SystemInfo] = None
        self._build_params: Optional[BuildParameters] = None
        self._custom_commands: Dict[str, CommandTranslation] = {}

    def detect_os_type(self) -> OSType:
        """Detect the operating system type."""
        system = platform.system().lower()

        if system == "windows":
            return OSType.WINDOWS
        elif system == "darwin":
            return OSType.MACOS
        elif system == "linux":
            return OSType.LINUX
        elif "bsd" in system:
            return OSType.BSD
        else:
            return OSType.UNKNOWN

    def detect_architecture(self) -> Architecture:
        """Detect the CPU architecture."""
        machine = platform.machine().lower()

        if machine in ("x86_64", "amd64"):
            return Architecture.X64
        elif machine in ("i386", "i686", "x86"):
            return Architecture.X86
        elif machine in ("aarch64", "arm64"):
            return Architecture.ARM64
        elif machine.startswith("arm"):
            return Architecture.ARM
        else:
            return Architecture.UNKNOWN

    def detect_shell_type(self) -> ShellType:
        """Detect the shell type."""
        os_type = self.detect_os_type()

        if os_type == OSType.WINDOWS:
            # Check for PowerShell
            if os.environ.get("PSModulePath"):
                return ShellType.POWERSHELL
            return ShellType.CMD
        else:
            shell = os.environ.get("SHELL", "")
            if "zsh" in shell:
                return ShellType.ZSH
            elif "bash" in shell:
                return ShellType.BASH
            elif shell:
                return ShellType.SH
            return ShellType.UNKNOWN

    def detect_container(self) -> bool:
        """Detect if running in a container."""
        # Check for Docker
        if Path("/.dockerenv").exists():
            return True
        # Check cgroup for container
        try:
            with open("/proc/1/cgroup", "r") as f:
                return "docker" in f.read() or "kubepods" in f.read()
        except:
            pass
        return False

    def detect_virtual(self) -> bool:
        """Detect if running in a virtual machine."""
        try:
            # Check for common VM indicators
            if platform.system() == "Linux":
                with open("/sys/class/dmi/id/product_name", "r") as f:
                    product = f.read().lower()
                    return any(vm in product for vm in ["virtualbox", "vmware", "qemu", "kvm"])
        except:
            pass
        return False

    def get_memory_available(self) -> Optional[int]:
        """Get available memory in MB."""
        try:
            import psutil
            return psutil.virtual_memory().available // (1024 * 1024)
        except ImportError:
            pass

        # Fallback for Linux
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if "MemAvailable" in line:
                        return int(line.split()[1]) // 1024
        except:
            pass

        return None

    def check_gpu_available(self) -> bool:
        """Check if GPU is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            pass

        try:
            import tensorflow as tf
            return len(tf.config.list_physical_devices('GPU')) > 0
        except ImportError:
            pass

        return False

    def get_system_info(self, refresh: bool = False) -> SystemInfo:
        """
        Get comprehensive system information.

        Args:
            refresh: Force refresh of cached info

        Returns:
            SystemInfo with all detected parameters
        """
        if self._system_info and not refresh:
            return self._system_info

        os_type = self.detect_os_type()

        # Get temp directory
        import tempfile
        temp_dir = Path(tempfile.gettempdir())

        self._system_info = SystemInfo(
            os_type=os_type,
            os_name=platform.system(),
            os_version=platform.version(),
            architecture=self.detect_architecture(),
            machine=platform.machine(),
            python_version=platform.python_version(),
            python_implementation=platform.python_implementation(),
            shell_type=self.detect_shell_type(),
            home_dir=Path.home(),
            temp_dir=temp_dir,
            cpu_count=os.cpu_count() or 1,
            memory_available=self.get_memory_available(),
            is_virtual=self.detect_virtual(),
            is_container=self.detect_container()
        )

        return self._system_info

    def get_build_parameters(self, refresh: bool = False) -> BuildParameters:
        """
        Generate self-building parameters based on system architecture.

        Args:
            refresh: Force refresh of cached parameters

        Returns:
            BuildParameters optimized for the current system
        """
        if self._build_params and not refresh:
            return self._build_params

        info = self.get_system_info(refresh)

        # Calculate optimal workers
        cpu_count = info.cpu_count
        parallel_workers = max(1, cpu_count - 1)  # Leave one core free

        # Calculate memory limits
        memory_mb = info.memory_available or 4096
        max_memory_mb = min(memory_mb // 2, 8192)  # Use half, max 8GB

        # Calculate chunk size based on memory
        chunk_size = min(max_memory_mb // 4, 2048) * 1024  # In bytes

        # Set directories
        base_dir = self.project_path or Path.cwd()

        # Shell command prefix
        if info.os_type == OSType.WINDOWS:
            if info.shell_type == ShellType.POWERSHELL:
                shell_prefix = ["powershell", "-Command"]
            else:
                shell_prefix = ["cmd", "/c"]
            path_sep = "\\"
            line_ending = "\r\n"
        else:
            shell_prefix = ["/bin/sh", "-c"]
            path_sep = "/"
            line_ending = "\n"

        # Batch size based on resources
        if info.memory_available and info.memory_available > 16000:
            batch_size = 32
        elif info.memory_available and info.memory_available > 8000:
            batch_size = 16
        else:
            batch_size = 8

        self._build_params = BuildParameters(
            parallel_workers=parallel_workers,
            max_memory_mb=max_memory_mb,
            chunk_size=chunk_size,
            temp_dir=info.temp_dir / "agnostic_core_os",
            cache_dir=base_dir / ".cache",
            log_dir=base_dir / "logs",
            shell_command_prefix=shell_prefix,
            path_separator=path_sep,
            line_ending=line_ending,
            file_encoding="utf-8",
            async_io_enabled=True,
            multiprocessing_enabled=cpu_count > 1,
            gpu_available=self.check_gpu_available(),
            recommended_batch_size=batch_size
        )

        return self._build_params

    def translate_command(self, generic_command: str, *args: str) -> str:
        """
        Translate a generic command to platform-specific command.

        Args:
            generic_command: Generic command name from index
            *args: Additional arguments to append

        Returns:
            Platform-specific command string
        """
        info = self.get_system_info()

        # Check custom commands first
        if generic_command in self._custom_commands:
            cmd = self._custom_commands[generic_command].get_for_os(info.os_type)
        elif generic_command in self.COMMAND_INDEX:
            cmd = self.COMMAND_INDEX[generic_command].get_for_os(info.os_type)
        else:
            # Return as-is if not found
            cmd = generic_command

        if args:
            cmd = f"{cmd} {' '.join(args)}"

        return cmd

    def register_command(self, translation: CommandTranslation) -> None:
        """Register a custom command translation."""
        self._custom_commands[translation.generic_command] = translation

    def get_path(self, *parts: str) -> Path:
        """Get a path with correct separators for the OS."""
        return Path(*parts)

    def normalize_path(self, path: str) -> str:
        """Normalize a path string for the current OS."""
        info = self.get_system_info()
        if info.os_type == OSType.WINDOWS:
            return path.replace("/", "\\")
        else:
            return path.replace("\\", "/")

    def get_python_command(self) -> str:
        """Get the correct Python command for this system."""
        info = self.get_system_info()
        if info.os_type == OSType.WINDOWS:
            return "py"
        return "python3"

    def get_pip_command(self) -> str:
        """Get the correct pip command for this system."""
        info = self.get_system_info()
        if info.os_type == OSType.WINDOWS:
            return "py -m pip"
        return "pip3"

    def generate_system_report(self) -> str:
        """Generate a human-readable system report."""
        info = self.get_system_info()
        params = self.get_build_parameters()

        lines = [
            "# Systems Translator Index Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## System Information",
            f"- OS Type: {info.os_type.value}",
            f"- OS Name: {info.os_name}",
            f"- OS Version: {info.os_version}",
            f"- Architecture: {info.architecture.value}",
            f"- Machine: {info.machine}",
            f"- Python: {info.python_version} ({info.python_implementation})",
            f"- Shell: {info.shell_type.value}",
            f"- CPU Cores: {info.cpu_count}",
            f"- Memory Available: {info.memory_available or 'Unknown'} MB",
            f"- Virtual Machine: {info.is_virtual}",
            f"- Container: {info.is_container}",
            "",
            "## Build Parameters",
            f"- Parallel Workers: {params.parallel_workers}",
            f"- Max Memory: {params.max_memory_mb} MB",
            f"- Chunk Size: {params.chunk_size} bytes",
            f"- Batch Size: {params.recommended_batch_size}",
            f"- GPU Available: {params.gpu_available}",
            f"- Async IO: {params.async_io_enabled}",
            f"- Multiprocessing: {params.multiprocessing_enabled}",
            "",
            "## Paths",
            f"- Home: {info.home_dir}",
            f"- Temp: {params.temp_dir}",
            f"- Cache: {params.cache_dir}",
            f"- Logs: {params.log_dir}",
            "",
            "## Command Translations",
        ]

        for name, cmd in self.COMMAND_INDEX.items():
            translated = self.translate_command(name)
            lines.append(f"- {name}: `{translated}`")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Export all system data as dictionary."""
        return {
            "system_info": self.get_system_info().to_dict(),
            "build_parameters": self.get_build_parameters().to_dict(),
            "command_index": {
                name: {
                    "windows": cmd.windows_command,
                    "unix": cmd.unix_command,
                    "description": cmd.description
                }
                for name, cmd in self.COMMAND_INDEX.items()
            }
        }

    def save_config(self, path: Optional[Path] = None) -> Path:
        """Save system configuration to JSON file."""
        if path is None:
            base = self.project_path or Path.cwd()
            path = base / "Agnostic_Core_OS" / "config" / "system_config.json"

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)

        return path


# Singleton instance for easy access
_default_translator: Optional[SystemsTranslatorIndex] = None


def get_systems_translator(project_path: Optional[Path] = None) -> SystemsTranslatorIndex:
    """Get the default systems translator instance."""
    global _default_translator
    if _default_translator is None:
        _default_translator = SystemsTranslatorIndex(project_path)
    return _default_translator
