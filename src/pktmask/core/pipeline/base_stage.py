from __future__ import annotations

import abc
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ...common.exceptions import FileError, ProcessingError
from .models import StageStats
from .resource_manager import ResourceManager


class StageBase(metaclass=abc.ABCMeta):
    """Unified base class for all pipeline processing stages.

    Design principles:
    - Strong type safety with explicit type annotations
    - Consistent interface across all implementations
    - Unified error handling and lifecycle management
    - English-only logging and comments for consistency

    All implementations must maintain backward compatibility and follow
    the unified interface contract defined here.
    """

    #: Stage name for GUI/CLI display - must be overridden by implementations
    name: str = "UnnamedStage"

    #: Internal initialization state
    _initialized: bool = False

    def __init__(self, config: Optional[Dict] = None) -> None:
        """Initialize stage with optional configuration.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._initialized = False
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        # Initialize unified resource manager
        resource_config = self.config.get("resource_manager", {})
        self.resource_manager = ResourceManager(resource_config)

        # Temporary file tracking for unified cleanup
        self._temp_files: List[Path] = []

        # Exception handling configuration
        self.enable_error_recovery = self.config.get("enable_error_recovery", True)
        self.max_retry_attempts = self.config.get("max_retry_attempts", 3)
        self.retry_delay_seconds = self.config.get("retry_delay_seconds", 1.0)

        self.logger.debug(f"Initialized {self.__class__.__name__} with unified resource management and error handling")

    @abc.abstractmethod
    def initialize(self, config: Optional[Dict] = None) -> bool:
        """Initialize the stage with configuration.

        Args:
            config: Optional configuration parameters

        Returns:
            bool: True if initialization successful, False otherwise
        """

    # ---------------------------------------------------------------------
    # Directory-level lifecycle methods
    # ---------------------------------------------------------------------
    def prepare_for_directory(self, directory: Path, all_files: List[str]) -> None:
        """Called before processing files in a directory.

        Used for pre-scanning or resource initialization.
        Default implementation does nothing.

        Args:
            directory: Directory being processed
            all_files: List of all files to be processed
        """

    def finalize_directory_processing(self) -> Optional[Dict]:
        """Called after all files in directory are processed.

        Used for generating summary information or cleanup.

        Returns:
            Optional[Dict]: Summary information or cleanup results
        """
        return None

    # ---------------------------------------------------------------------
    # Temporary file management
    # ---------------------------------------------------------------------
    def register_temp_file(self, file_path: Path) -> None:
        """Register temporary file for cleanup.

        Args:
            file_path: Path to temporary file
        """
        if file_path not in self._temp_files:
            self._temp_files.append(file_path)
            self.logger.debug(f"Registered temp file for cleanup: {file_path}")

    def _cleanup_temp_files(self) -> None:
        """Clean up all registered temporary files."""
        cleanup_errors = []

        for temp_file in self._temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    self.logger.debug(f"Cleaned temp file: {temp_file}")
                else:
                    self.logger.debug(f"Temp file already removed: {temp_file}")
            except PermissionError as e:
                cleanup_errors.append(f"Permission denied for {temp_file}: {e}")
            except OSError as e:
                cleanup_errors.append(f"OS error for {temp_file}: {e}")
            except Exception as e:
                cleanup_errors.append(f"Unexpected error for {temp_file}: {e}")

        # Clear the list after cleanup attempt
        self._temp_files.clear()

        if cleanup_errors:
            self.logger.warning(f"Temp file cleanup completed with errors: {'; '.join(cleanup_errors)}")
        else:
            self.logger.debug("All temporary files cleaned successfully")

    # ---------------------------------------------------------------------
    # Core processing method
    # ---------------------------------------------------------------------
    @abc.abstractmethod
    def process_file(self, input_path: Path, output_path: Path) -> StageStats:
        """Process a single file.

        Args:
            input_path: Input file path
            output_path: Output file path

        Returns:
            StageStats: Processing statistics and results

        Raises:
            FileNotFoundError: If input file does not exist
            ValueError: If input path is not a file
            RuntimeError: If stage is not initialized
        """

    # ---------------------------------------------------------------------
    # Optional lifecycle hooks
    # ---------------------------------------------------------------------
    def stop(self) -> None:
        """Stop processing gracefully.

        Called when pipeline is stopped or user cancels processing.
        Used for terminating external processes or cleanup.
        """

    def cleanup(self) -> None:
        """Clean up stage resources.

        This method provides unified resource cleanup for all stages.
        Subclasses should override _cleanup_stage_specific() for custom cleanup logic.
        """
        self.logger.debug(f"Starting cleanup for {self.__class__.__name__}")

        cleanup_errors = []

        try:
            # Stage-specific cleanup
            self._cleanup_stage_specific()
        except Exception as e:
            cleanup_errors.append(f"Stage-specific cleanup failed: {e}")

        try:
            # Clean up temporary files
            self._cleanup_temp_files()
        except Exception as e:
            cleanup_errors.append(f"Temp file cleanup failed: {e}")

        try:
            # Unified resource cleanup
            self.resource_manager.cleanup()
        except Exception as e:
            cleanup_errors.append(f"Resource manager cleanup failed: {e}")

        # Reset initialization state
        self._initialized = False

        if cleanup_errors:
            error_msg = f"Cleanup completed with errors: {'; '.join(cleanup_errors)}"
            self.logger.warning(error_msg)
            # Don't raise exception for cleanup errors, just log them
        else:
            self.logger.debug(f"Cleanup completed successfully for {self.__class__.__name__}")

    def _cleanup_stage_specific(self) -> None:
        """Stage-specific cleanup logic.

        Subclasses should override this method to implement custom cleanup logic.
        This method is called before the unified resource cleanup.
        """

    # ---------------------------------------------------------------------
    # Exception handling utilities
    # ---------------------------------------------------------------------
    @contextmanager
    def safe_operation(self, operation_name: str, cleanup_func: Optional[Callable] = None):
        """Context manager for safe operations with automatic cleanup.

        Args:
            operation_name: Name of the operation for logging
            cleanup_func: Optional cleanup function to call on exception
        """
        self.logger.debug(f"Starting safe operation: {operation_name}")
        try:
            yield
            self.logger.debug(f"Safe operation completed: {operation_name}")
        except Exception as e:
            self.logger.error(f"Safe operation failed: {operation_name}, error: {e}")
            if cleanup_func:
                try:
                    cleanup_func()
                    self.logger.debug(f"Cleanup completed for failed operation: {operation_name}")
                except Exception as cleanup_error:
                    self.logger.warning(f"Cleanup failed for operation {operation_name}: {cleanup_error}")
            raise

    def retry_operation(
        self,
        operation: Callable,
        operation_name: str = "operation",
        max_attempts: Optional[int] = None,
    ) -> Any:
        """Retry an operation with exponential backoff.

        Args:
            operation: Function to retry
            operation_name: Name for logging
            max_attempts: Maximum retry attempts (uses config default if None)

        Returns:
            Result of the operation

        Raises:
            Exception: Last exception if all retries fail
        """
        attempts = max_attempts or self.max_retry_attempts
        last_exception = None

        for attempt in range(1, attempts + 1):
            try:
                result = operation()
                if attempt > 1:
                    self.logger.info(f"Operation '{operation_name}' succeeded on attempt {attempt}")
                return result
            except Exception as e:
                last_exception = e
                if attempt < attempts:
                    delay = self.retry_delay_seconds * (2 ** (attempt - 1))  # Exponential backoff
                    self.logger.warning(
                        f"Operation '{operation_name}' failed on attempt {attempt}/{attempts}: {e}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(f"Operation '{operation_name}' failed after {attempts} attempts: {e}")

        raise last_exception

    def handle_file_operation_error(self, error: Exception, file_path: Path, operation: str) -> None:
        """Handle file operation errors with context.

        Args:
            error: The original exception
            file_path: Path of the file being operated on
            operation: Description of the operation
        """
        if isinstance(error, FileNotFoundError):
            raise FileError(
                f"File not found during {operation}: {file_path}",
                file_path=str(file_path),
            ) from error
        elif isinstance(error, PermissionError):
            raise FileError(
                f"Permission denied during {operation}: {file_path}",
                file_path=str(file_path),
            ) from error
        elif isinstance(error, OSError):
            raise FileError(
                f"OS error during {operation}: {file_path} - {error}",
                file_path=str(file_path),
            ) from error
        else:
            raise ProcessingError(f"Unexpected error during {operation}: {file_path} - {error}") from error

    def validate_file_access(self, file_path: Path, operation: str = "access") -> None:
        """Validate file access with proper error handling.

        Args:
            file_path: Path to validate
            operation: Operation description for error messages

        Raises:
            FileError: If file access validation fails
        """
        try:
            if not file_path.exists():
                raise FileError(
                    f"File does not exist for {operation}: {file_path}",
                    file_path=str(file_path),
                )
            if not file_path.is_file():
                raise FileError(
                    f"Path is not a file for {operation}: {file_path}",
                    file_path=str(file_path),
                )
            if not file_path.stat().st_size > 0:
                self.logger.warning(f"File is empty for {operation}: {file_path}")
        except OSError as e:
            raise FileError(
                f"Cannot access file for {operation}: {file_path} - {e}",
                file_path=str(file_path),
            ) from e

    # ---------------------------------------------------------------------
    # Tool dependency detection
    # ---------------------------------------------------------------------
    def get_required_tools(self) -> List[str]:
        """Get list of required external tools.

        Returns:
            List[str]: List of required tool names (e.g., 'tshark')
        """
        return []
