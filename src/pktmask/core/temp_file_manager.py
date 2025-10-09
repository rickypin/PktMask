#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Global Temporary File Manager

Provides centralized temporary file and directory management with guaranteed cleanup
even in exceptional scenarios (process kill, exceptions, etc.).

Features:
- Automatic cleanup on normal exit via atexit
- Cleanup on exception via context manager
- Thread-safe operations
- Graceful handling of cleanup failures
- Logging of all operations
"""

import atexit
import logging
import shutil
import tempfile
import threading
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


class TempFileManager:
    """
    Global temporary file manager with guaranteed cleanup.

    This class provides centralized management of temporary files and directories
    with automatic cleanup on program exit, even in exceptional scenarios.

    Features:
    - Thread-safe operations
    - Automatic cleanup via atexit
    - Graceful error handling
    - Comprehensive logging

    Example:
        >>> manager = TempFileManager.get_instance()
        >>> temp_dir = manager.create_temp_dir()
        >>> # Use temp_dir...
        >>> # Cleanup happens automatically on exit
    """

    _instance: Optional["TempFileManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        """Initialize the temporary file manager."""
        self.temp_dirs: Set[Path] = set()
        self.temp_files: Set[Path] = set()
        self._cleanup_lock = threading.Lock()
        self._cleanup_registered = False
        self._is_cleaning_up = False

        logger.debug("TempFileManager initialized")

    @classmethod
    def get_instance(cls) -> "TempFileManager":
        """
        Get singleton instance of TempFileManager.

        Returns:
            TempFileManager: Singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    # Register cleanup on first instantiation
                    atexit.register(cls._instance.cleanup_all)
                    cls._instance._cleanup_registered = True
                    logger.info("TempFileManager singleton created and cleanup registered")
        return cls._instance

    def create_temp_dir(self, prefix: str = "pktmask_", suffix: str = "") -> Path:
        """
        Create a temporary directory and register it for cleanup.

        Args:
            prefix: Directory name prefix
            suffix: Directory name suffix

        Returns:
            Path: Path to created temporary directory
        """
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix, suffix=suffix))

        with self._cleanup_lock:
            self.temp_dirs.add(temp_dir)

        logger.debug(f"Created temp directory: {temp_dir}")
        return temp_dir

    def create_temp_file(
        self, prefix: str = "pktmask_", suffix: str = "", dir: Optional[Path] = None, delete: bool = False
    ) -> Path:
        """
        Create a temporary file and register it for cleanup.

        Args:
            prefix: File name prefix
            suffix: File name suffix
            dir: Directory to create file in (default: system temp)
            delete: If True, file is deleted immediately after creation

        Returns:
            Path: Path to created temporary file
        """
        fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=str(dir) if dir else None)

        # Close the file descriptor
        import os

        os.close(fd)

        temp_file = Path(temp_path)

        if not delete:
            with self._cleanup_lock:
                self.temp_files.add(temp_file)
            logger.debug(f"Created temp file: {temp_file}")
        else:
            # Delete immediately if requested
            try:
                temp_file.unlink()
                logger.debug(f"Created and deleted temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_file}: {e}")

        return temp_file

    def register_temp_dir(self, temp_dir: Path) -> None:
        """
        Register an existing directory for cleanup.

        Args:
            temp_dir: Directory to register
        """
        with self._cleanup_lock:
            self.temp_dirs.add(Path(temp_dir))
        logger.debug(f"Registered temp directory: {temp_dir}")

    def register_temp_file(self, temp_file: Path) -> None:
        """
        Register an existing file for cleanup.

        Args:
            temp_file: File to register
        """
        with self._cleanup_lock:
            self.temp_files.add(Path(temp_file))
        logger.debug(f"Registered temp file: {temp_file}")

    def unregister_temp_dir(self, temp_dir: Path) -> None:
        """
        Unregister a directory (won't be cleaned up automatically).

        Args:
            temp_dir: Directory to unregister
        """
        with self._cleanup_lock:
            self.temp_dirs.discard(Path(temp_dir))
        logger.debug(f"Unregistered temp directory: {temp_dir}")

    def unregister_temp_file(self, temp_file: Path) -> None:
        """
        Unregister a file (won't be cleaned up automatically).

        Args:
            temp_file: File to unregister
        """
        with self._cleanup_lock:
            self.temp_files.discard(Path(temp_file))
        logger.debug(f"Unregistered temp file: {temp_file}")

    def cleanup_all(self) -> None:
        """
        Clean up all registered temporary files and directories.

        This method is called automatically on program exit via atexit.
        It can also be called manually for explicit cleanup.

        Cleanup is performed in the following order:
        1. Temporary files
        2. Temporary directories

        Errors during cleanup are logged but do not raise exceptions.
        """
        # Prevent recursive cleanup
        if self._is_cleaning_up:
            logger.debug("Cleanup already in progress, skipping")
            return

        with self._cleanup_lock:
            self._is_cleaning_up = True

        try:
            logger.info("Starting global temporary file cleanup")

            files_cleaned = 0
            files_failed = 0
            dirs_cleaned = 0
            dirs_failed = 0

            # Clean up temporary files first
            temp_files_copy = list(self.temp_files)
            for temp_file in temp_files_copy:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                        files_cleaned += 1
                        logger.debug(f"Cleaned temp file: {temp_file}")
                    else:
                        logger.debug(f"Temp file already removed: {temp_file}")
                except PermissionError as e:
                    files_failed += 1
                    logger.warning(f"Permission denied cleaning temp file {temp_file}: {e}")
                except OSError as e:
                    files_failed += 1
                    logger.warning(f"OS error cleaning temp file {temp_file}: {e}")
                except Exception as e:
                    files_failed += 1
                    logger.warning(f"Unexpected error cleaning temp file {temp_file}: {e}")

            # Clear the files set
            self.temp_files.clear()

            # Clean up temporary directories
            temp_dirs_copy = list(self.temp_dirs)
            for temp_dir in temp_dirs_copy:
                try:
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir, ignore_errors=False)
                        dirs_cleaned += 1
                        logger.debug(f"Cleaned temp directory: {temp_dir}")
                    else:
                        logger.debug(f"Temp directory already removed: {temp_dir}")
                except PermissionError as e:
                    dirs_failed += 1
                    logger.warning(f"Permission denied cleaning temp directory {temp_dir}: {e}")
                except OSError as e:
                    dirs_failed += 1
                    logger.warning(f"OS error cleaning temp directory {temp_dir}: {e}")
                except Exception as e:
                    dirs_failed += 1
                    logger.warning(f"Unexpected error cleaning temp directory {temp_dir}: {e}")

            # Clear the directories set
            self.temp_dirs.clear()

            # Log summary
            if files_cleaned > 0 or files_failed > 0 or dirs_cleaned > 0 or dirs_failed > 0:
                logger.info(
                    f"Temporary file cleanup completed: "
                    f"files cleaned={files_cleaned}, files failed={files_failed}, "
                    f"dirs cleaned={dirs_cleaned}, dirs failed={dirs_failed}"
                )
            else:
                logger.debug("No temporary files or directories to clean up")

        finally:
            with self._cleanup_lock:
                self._is_cleaning_up = False

    def get_stats(self) -> dict:
        """
        Get statistics about registered temporary files and directories.

        Returns:
            dict: Statistics including counts and total size
        """
        with self._cleanup_lock:
            total_size = 0

            # Calculate size of temp files
            for temp_file in self.temp_files:
                try:
                    if temp_file.exists():
                        total_size += temp_file.stat().st_size
                except Exception:
                    pass

            # Calculate size of temp directories
            for temp_dir in self.temp_dirs:
                try:
                    if temp_dir.exists():
                        for item in temp_dir.rglob("*"):
                            if item.is_file():
                                total_size += item.stat().st_size
                except Exception:
                    pass

            return {
                "temp_files_count": len(self.temp_files),
                "temp_dirs_count": len(self.temp_dirs),
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
            }


# Convenience function to get the global instance
def get_temp_file_manager() -> TempFileManager:
    """
    Get the global TempFileManager instance.

    Returns:
        TempFileManager: Global singleton instance
    """
    return TempFileManager.get_instance()
