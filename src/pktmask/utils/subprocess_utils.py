"""
Windows subprocess utilities to prevent cmd window popup
"""

import logging
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


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
    return run_hidden_subprocess(cmd=cmd, timeout=timeout, check=True, capture_output=True, text=True, **kwargs)


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


def calculate_tshark_timeout(pcap_path: Optional[Union[str, Path]] = None, operation: str = "scan") -> float:
    """
    Calculate appropriate timeout for TShark operation based on file size.

    Args:
        pcap_path: Path to PCAP file (optional, used for file-size-based calculation)
        operation: Type of operation:
            - 'version': Version check (10s)
            - 'protocol': Protocol list (30s)
            - 'test': Quick test operation (10s)
            - 'scan': PCAP scanning (60s-600s based on file size)
            - 'analyze': Flow analysis (60s-600s based on file size)

    Returns:
        Timeout in seconds

    Examples:
        >>> calculate_tshark_timeout(operation="version")
        10.0
        >>> calculate_tshark_timeout("small.pcap", "scan")  # <10MB
        60.0
        >>> calculate_tshark_timeout("large.pcap", "scan")  # >100MB
        600.0
    """
    # Quick operations with fixed timeouts
    if operation == "version":
        return 10.0
    elif operation == "protocol":
        return 30.0
    elif operation == "test":
        return 10.0

    # File-based operations - calculate based on file size
    if pcap_path is None:
        logger.warning(f"No PCAP path provided for operation '{operation}', using default timeout")
        return 300.0  # Default 5 minutes

    try:
        file_size_bytes = Path(pcap_path).stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        # Dynamic timeout based on file size
        if file_size_mb < 10:
            timeout = 60.0  # 1 minute for small files
        elif file_size_mb < 100:
            timeout = 300.0  # 5 minutes for medium files
        else:
            timeout = 600.0  # 10 minutes for large files

        logger.debug(
            f"Calculated TShark timeout: file_size={file_size_mb:.2f}MB, " f"operation={operation}, timeout={timeout}s"
        )
        return timeout

    except (OSError, FileNotFoundError) as e:
        logger.warning(f"Cannot determine file size for {pcap_path}: {e}, using default timeout")
        return 300.0  # Default 5 minutes on error


def open_directory_hidden(directory: Union[str, Path]) -> bool:
    """
    Open directory in system file manager without showing cmd window.

    Args:
        directory: Directory path to open

    Returns:
        Whether successfully opened
    """
    from ..common.constants import SystemConstants

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
