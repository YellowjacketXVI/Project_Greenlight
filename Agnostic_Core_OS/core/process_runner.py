"""
Process Runner - Cross-Platform Process Execution

Provides platform-agnostic process execution and management
that works consistently across Windows, macOS, and Linux.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Callable
from pathlib import Path
from datetime import datetime
from enum import Enum
import subprocess
import asyncio
import os

from ..translators.systems_translator import get_systems_translator, OSType


class ProcessStatus(Enum):
    """Process execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ProcessResult:
    """Result of a process execution."""
    command: str
    return_code: int
    stdout: str
    stderr: str
    status: ProcessStatus
    duration_ms: float
    started_at: datetime
    ended_at: datetime
    
    @property
    def success(self) -> bool:
        return self.return_code == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "return_code": self.return_code,
            "stdout": self.stdout[:1000] if self.stdout else "",
            "stderr": self.stderr[:1000] if self.stderr else "",
            "status": self.status.value,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat()
        }


class ProcessRunner:
    """
    Cross-platform process execution.
    
    Provides consistent process execution across all platforms.
    
    Example:
        runner = ProcessRunner()
        
        # Run a command
        result = runner.run("echo Hello World")
        
        # Run with timeout
        result = runner.run("long_command", timeout=30)
        
        # Open file with default app
        runner.open_file("document.pdf")
        
        # Open folder in file manager
        runner.open_folder("output/images")
    """
    
    def __init__(self, working_dir: Optional[Path] = None):
        """Initialize process runner."""
        self.working_dir = working_dir or Path.cwd()
        self._translator = get_systems_translator()
        self._system_info = self._translator.get_system_info()
        self._history: List[ProcessResult] = []
    
    def run(
        self,
        command: Union[str, List[str]],
        timeout: Optional[float] = None,
        capture_output: bool = True,
        shell: bool = True,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Path] = None
    ) -> ProcessResult:
        """
        Run a command synchronously.
        
        Args:
            command: Command to run (string or list)
            timeout: Timeout in seconds
            capture_output: Capture stdout/stderr
            shell: Run in shell
            env: Environment variables
            cwd: Working directory
            
        Returns:
            ProcessResult with execution details
        """
        started_at = datetime.now()
        cmd_str = command if isinstance(command, str) else " ".join(command)
        
        # Merge environment
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        
        try:
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                cwd=cwd or self.working_dir,
                env=run_env
            )
            
            ended_at = datetime.now()
            duration = (ended_at - started_at).total_seconds() * 1000
            
            proc_result = ProcessResult(
                command=cmd_str,
                return_code=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                status=ProcessStatus.COMPLETED if result.returncode == 0 else ProcessStatus.FAILED,
                duration_ms=duration,
                started_at=started_at,
                ended_at=ended_at
            )
            
        except subprocess.TimeoutExpired:
            ended_at = datetime.now()
            duration = (ended_at - started_at).total_seconds() * 1000
            proc_result = ProcessResult(
                command=cmd_str,
                return_code=-1,
                stdout="",
                stderr="Process timed out",
                status=ProcessStatus.TIMEOUT,
                duration_ms=duration,
                started_at=started_at,
                ended_at=ended_at
            )
            
        except Exception as e:
            ended_at = datetime.now()
            duration = (ended_at - started_at).total_seconds() * 1000
            proc_result = ProcessResult(
                command=cmd_str,
                return_code=-1,
                stdout="",
                stderr=str(e),
                status=ProcessStatus.FAILED,
                duration_ms=duration,
                started_at=started_at,
                ended_at=ended_at
            )
        
        self._history.append(proc_result)
        return proc_result

    async def run_async(
        self,
        command: Union[str, List[str]],
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Path] = None
    ) -> ProcessResult:
        """
        Run a command asynchronously.

        Args:
            command: Command to run
            timeout: Timeout in seconds
            env: Environment variables
            cwd: Working directory

        Returns:
            ProcessResult with execution details
        """
        started_at = datetime.now()
        cmd_str = command if isinstance(command, str) else " ".join(command)

        # Merge environment
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        try:
            if isinstance(command, str):
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd or self.working_dir,
                    env=run_env
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd or self.working_dir,
                    env=run_env
                )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )

                ended_at = datetime.now()
                duration = (ended_at - started_at).total_seconds() * 1000

                proc_result = ProcessResult(
                    command=cmd_str,
                    return_code=proc.returncode or 0,
                    stdout=stdout.decode() if stdout else "",
                    stderr=stderr.decode() if stderr else "",
                    status=ProcessStatus.COMPLETED if proc.returncode == 0 else ProcessStatus.FAILED,
                    duration_ms=duration,
                    started_at=started_at,
                    ended_at=ended_at
                )

            except asyncio.TimeoutError:
                proc.kill()
                ended_at = datetime.now()
                duration = (ended_at - started_at).total_seconds() * 1000
                proc_result = ProcessResult(
                    command=cmd_str,
                    return_code=-1,
                    stdout="",
                    stderr="Process timed out",
                    status=ProcessStatus.TIMEOUT,
                    duration_ms=duration,
                    started_at=started_at,
                    ended_at=ended_at
                )

        except Exception as e:
            ended_at = datetime.now()
            duration = (ended_at - started_at).total_seconds() * 1000
            proc_result = ProcessResult(
                command=cmd_str,
                return_code=-1,
                stdout="",
                stderr=str(e),
                status=ProcessStatus.FAILED,
                duration_ms=duration,
                started_at=started_at,
                ended_at=ended_at
            )

        self._history.append(proc_result)
        return proc_result

    def open_file(self, path: Union[str, Path]) -> ProcessResult:
        """
        Open a file with the default application.

        Args:
            path: Path to file

        Returns:
            ProcessResult
        """
        path = Path(path)

        if self._system_info.os_type == OSType.WINDOWS:
            cmd = ['start', '', str(path)]
            return self.run(cmd, shell=True)
        elif self._system_info.os_type == OSType.MACOS:
            return self.run(['open', str(path)], shell=False)
        else:
            return self.run(['xdg-open', str(path)], shell=False)

    def open_folder(self, path: Union[str, Path]) -> ProcessResult:
        """
        Open a folder in the file manager.

        Args:
            path: Path to folder

        Returns:
            ProcessResult
        """
        path = Path(path)

        if self._system_info.os_type == OSType.WINDOWS:
            return self.run(['explorer', str(path)], shell=False)
        elif self._system_info.os_type == OSType.MACOS:
            return self.run(['open', str(path)], shell=False)
        else:
            return self.run(['xdg-open', str(path)], shell=False)

    def run_python(
        self,
        script: Union[str, Path],
        args: Optional[List[str]] = None,
        timeout: Optional[float] = None
    ) -> ProcessResult:
        """
        Run a Python script.

        Args:
            script: Path to script or inline code
            args: Script arguments
            timeout: Timeout in seconds

        Returns:
            ProcessResult
        """
        python_cmd = self._translator.get_python_command()

        script_path = Path(script)
        if script_path.exists():
            cmd = [python_cmd, str(script_path)]
        else:
            # Inline code
            cmd = [python_cmd, '-c', str(script)]

        if args:
            cmd.extend(args)

        return self.run(cmd, timeout=timeout, shell=False)

    def get_history(self, limit: int = 100) -> List[ProcessResult]:
        """Get execution history."""
        return self._history[-limit:]

    def clear_history(self) -> None:
        """Clear execution history."""
        self._history.clear()


# Singleton instance
_process_runner: Optional[ProcessRunner] = None


def get_process_runner(working_dir: Optional[Path] = None) -> ProcessRunner:
    """Get the default ProcessRunner instance."""
    global _process_runner
    if _process_runner is None:
        _process_runner = ProcessRunner(working_dir)
    return _process_runner
