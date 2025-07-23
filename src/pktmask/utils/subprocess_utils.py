"""
Windows subprocess utilities to prevent cmd window popup
"""

import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def get_subprocess_creation_flags() -> int:
    """
    Get appropriate creation flags for subprocess on Windows to hide console windows.

    Returns:
        Creation flags for subprocess.run() on Windows, 0 on other platforms
    """
    if platform.system() == "Windows":
        # Combine flags to hide console window
        import subprocess

        return (
            subprocess.CREATE_NO_WINDOW  # Don't create a console window
            | subprocess.DETACHED_PROCESS  # Detach from parent console
        )
    return 0


def run_hidden_subprocess(
    cmd: List[str],
    capture_output: bool = True,
    text: bool = True,
    timeout: Optional[float] = None,
    check: bool = False,
    encoding: str = "utf-8",
    errors: str = "replace",
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[Union[str, Path]] = None,
    **kwargs,
) -> subprocess.CompletedProcess:
    """
    Run subprocess with Windows-specific flags to prevent cmd window popup.

    Args:
        cmd: Command to execute as list of strings
        capture_output: Whether to capture stdout/stderr
        text: Whether to return text instead of bytes
        timeout: Timeout in seconds
        check: Whether to raise exception on non-zero exit code
        encoding: Text encoding for output
        errors: How to handle encoding errors
        env: Environment variables
        cwd: Working directory
        **kwargs: Additional arguments for subprocess.run

    Returns:
        CompletedProcess instance

    Raises:
        subprocess.CalledProcessError: If check=True and process returns non-zero
        subprocess.TimeoutExpired: If timeout is exceeded
    """
    # Set Windows-specific creation flags
    creation_flags = get_subprocess_creation_flags()

    # Prepare subprocess arguments
    subprocess_args = {
        "capture_output": capture_output,
        "text": text,
        "encoding": encoding,
        "errors": errors,
        "timeout": timeout,
        "check": check,
        "env": env,
        "cwd": cwd,
        **kwargs,
    }

    # Add creation flags on Windows
    if creation_flags:
        subprocess_args["creationflags"] = creation_flags

    return subprocess.run(cmd, **subprocess_args)


def run_tshark_command(
    tshark_path: str, args: List[str], timeout: Optional[float] = 300, **kwargs
) -> subprocess.CompletedProcess:
    """
    Run tshark command with proper Windows console hiding.

    Args:
        tshark_path: Path to tshark executable
        args: Arguments for tshark (without the executable name)
        timeout: Timeout in seconds (default 5 minutes)
        **kwargs: Additional arguments for run_hidden_subprocess

    Returns:
        CompletedProcess instance
    """
    cmd = [tshark_path] + args
    return run_hidden_subprocess(
        cmd=cmd, timeout=timeout, check=True, capture_output=True, text=True, **kwargs
    )


def run_editcap_command(
    editcap_path: str, args: List[str], timeout: Optional[float] = 60, **kwargs
) -> subprocess.CompletedProcess:
    """
    Run editcap command with proper Windows console hiding.

    Args:
        editcap_path: Path to editcap executable
        args: Arguments for editcap (without the executable name)
        timeout: Timeout in seconds (default 1 minute)
        **kwargs: Additional arguments for run_hidden_subprocess

    Returns:
        CompletedProcess instance
    """
    cmd = [editcap_path] + args
    return run_hidden_subprocess(cmd=cmd, timeout=timeout, check=True, **kwargs)


def open_directory_hidden(directory: Union[str, Path]) -> bool:
    """
    Open directory in system file manager without showing cmd window.

    Args:
        directory: Directory path to open

    Returns:
        Whether successfully opened
    """
    import logging

    from ..common.constants import SystemConstants

    logger = logging.getLogger(__name__)
    directory = Path(directory)

    if not directory.exists() or not directory.is_dir():
        logger.warning(f"Directory does not exist: {directory}")
        return False

    try:
        system = platform.system()

        if system == SystemConstants.MACOS_SYSTEM_NAME:
            cmd = [SystemConstants.MACOS_OPEN_COMMAND, str(directory)]
        elif system == SystemConstants.WINDOWS_SYSTEM_NAME:
            cmd = [SystemConstants.WINDOWS_OPEN_COMMAND, str(directory)]
        else:  # Linux and others
            cmd = [SystemConstants.LINUX_OPEN_COMMAND, str(directory)]

        # Use hidden subprocess for Windows
        run_hidden_subprocess(cmd, capture_output=False, check=False)

        logger.debug(f"Opened directory in system file manager: {directory}")
        return True

    except Exception as e:
        logger.error(f"Failed to open directory: {directory}, error: {e}")
        return False
