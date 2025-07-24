"""
Unified Resource Management System for PktMask Pipeline

This module provides a unified approach to resource management across all pipeline stages,
addressing the memory management inconsistencies identified in the code review.

Key Features:
- Unified memory and buffer management
- Automatic resource cleanup with RAII patterns
- Configurable memory pressure handling
- Integration with StageBase architecture
"""

from __future__ import annotations

import gc
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Union


class ResourceType(Enum):
    """Resource type enumeration"""

    MEMORY = "memory"
    FILE_HANDLE = "file_handle"
    TEMP_FILE = "temp_file"
    BUFFER = "buffer"
    NETWORK = "network"


@dataclass
class ResourceStats:
    """Resource usage statistics"""

    memory_usage_mb: float
    buffer_count: int
    file_handles: int
    temp_files: int
    peak_memory_mb: float
    gc_collections: int
    last_cleanup_time: float


class ResourceCleanupProtocol(Protocol):
    """Protocol for resource cleanup"""

    def cleanup(self) -> None:
        """Clean up resources"""
        ...


class MemoryMonitor:
    """Unified memory monitoring component"""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Configuration
        self.max_memory_mb = config.get("max_memory_mb", 2048)
        self.pressure_threshold = config.get("pressure_threshold", 0.8)
        self.monitoring_interval = config.get("monitoring_interval", 100)

        # State
        self.operation_count = 0
        self.peak_memory = 0
        self.gc_count = 0
        self.last_check_time = time.time()
        self.pressure_callbacks: List[Callable[[float], None]] = []

    def check_memory_pressure(self) -> float:
        """Check current memory pressure (0.0 to 1.0)"""
        try:
            import psutil

            process = psutil.Process()
            current_memory = process.memory_info().rss

            # Update peak memory
            if current_memory > self.peak_memory:
                self.peak_memory = current_memory

            # Calculate pressure
            max_memory_bytes = self.max_memory_mb * 1024 * 1024
            pressure = min(1.0, current_memory / max_memory_bytes)

            # Trigger callbacks if pressure is high
            if pressure >= self.pressure_threshold:
                self._notify_pressure_callbacks(pressure)

            return pressure

        except ImportError:
            # psutil not available - return 0 to not affect normal functionality
            return 0.0
        except Exception as e:
            self.logger.warning(f"Memory check failed: {e}")
            return 0.0

    def register_pressure_callback(self, callback: Callable[[float], None]) -> None:
        """Register callback for memory pressure events"""
        self.pressure_callbacks.append(callback)

    def _notify_pressure_callbacks(self, pressure: float) -> None:
        """Notify all registered callbacks about memory pressure"""
        for callback in self.pressure_callbacks:
            try:
                callback(pressure)
            except Exception as e:
                self.logger.warning(f"Memory pressure callback failed: {e}")

    def trigger_gc(self) -> int:
        """Trigger garbage collection and return collected objects count"""
        collected = gc.collect()
        self.gc_count += 1
        self.logger.debug(
            f"Garbage collection completed: {collected} objects collected"
        )
        return collected


class BufferManager:
    """Unified buffer management component"""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Configuration
        self.default_buffer_size = config.get("default_buffer_size", 100)
        self.max_buffer_size = config.get("max_buffer_size", 1000)
        self.min_buffer_size = config.get("min_buffer_size", 10)
        self.auto_resize = config.get("auto_resize", True)

        # Active buffers tracking
        self.active_buffers: Dict[str, List[Any]] = {}
        self.buffer_stats: Dict[str, Dict[str, Any]] = {}

    def create_buffer(self, name: str, initial_size: Optional[int] = None) -> List[Any]:
        """Create a new managed buffer"""
        size = initial_size or self.default_buffer_size
        buffer = []

        self.active_buffers[name] = buffer
        self.buffer_stats[name] = {
            "created_time": time.time(),
            "max_size_reached": 0,
            "flush_count": 0,
            "current_size": 0,
        }

        self.logger.debug(f"Created buffer '{name}' with initial capacity {size}")
        return buffer

    def should_flush_buffer(self, name: str, memory_pressure: float = 0.0) -> bool:
        """Determine if buffer should be flushed based on size and memory pressure"""
        if name not in self.active_buffers:
            return False

        buffer = self.active_buffers[name]
        current_size = len(buffer)

        # Update stats
        stats = self.buffer_stats[name]
        stats["current_size"] = current_size
        if current_size > stats["max_size_reached"]:
            stats["max_size_reached"] = current_size

        # Determine flush conditions
        size_threshold = self._calculate_size_threshold(memory_pressure)

        return current_size >= size_threshold

    def flush_buffer(self, name: str) -> List[Any]:
        """Flush and return buffer contents with error handling"""
        if name not in self.active_buffers:
            self.logger.warning(f"Attempted to flush non-existent buffer: {name}")
            return []

        try:
            buffer = self.active_buffers[name]
            contents = buffer.copy()
            buffer.clear()

            # Update stats
            if name in self.buffer_stats:
                self.buffer_stats[name]["flush_count"] += 1
                self.buffer_stats[name]["current_size"] = 0

            self.logger.debug(f"Flushed buffer '{name}': {len(contents)} items")
            return contents

        except Exception as e:
            self.logger.error(f"Error flushing buffer '{name}': {e}")
            # Return empty list on error to prevent further issues
            return []

    def cleanup_buffer(self, name: str) -> None:
        """Clean up a specific buffer with error handling"""
        try:
            if name in self.active_buffers:
                del self.active_buffers[name]
                if name in self.buffer_stats:
                    del self.buffer_stats[name]
                self.logger.debug(f"Cleaned up buffer '{name}'")
            else:
                self.logger.debug(
                    f"Buffer '{name}' already cleaned up or never existed"
                )
        except Exception as e:
            self.logger.warning(f"Error cleaning up buffer '{name}': {e}")

    def cleanup_all_buffers(self) -> None:
        """Clean up all managed buffers with error handling"""
        buffer_names = list(self.active_buffers.keys())
        cleaned_count = 0
        failed_count = 0

        for name in buffer_names:
            try:
                self.cleanup_buffer(name)
                cleaned_count += 1
            except Exception as e:
                failed_count += 1
                self.logger.warning(f"Failed to cleanup buffer '{name}': {e}")

        self.logger.debug(
            f"Buffer cleanup completed: {cleaned_count} cleaned, {failed_count} failed"
        )

    def _calculate_size_threshold(self, memory_pressure: float) -> int:
        """Calculate dynamic buffer size threshold based on memory pressure"""
        if not self.auto_resize:
            return self.default_buffer_size

        # Reduce buffer size under memory pressure
        if memory_pressure > 0.8:
            # Under high memory pressure, flush immediately if buffer has any content
            return 1
        elif memory_pressure > 0.6:
            return max(1, int(self.default_buffer_size * 0.5))
        else:
            return self.default_buffer_size


class ResourceManager:
    """Unified resource manager for pipeline stages"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Initialize components
        memory_config = self.config.get("memory_monitor", {})
        buffer_config = self.config.get("buffer_manager", {})

        self.memory_monitor = MemoryMonitor(memory_config)
        self.buffer_manager = BufferManager(buffer_config)

        # Resource tracking
        self.temp_files: List[Path] = []
        self.managed_resources: Dict[str, Any] = {}
        self.cleanup_callbacks: List[Callable[[], None]] = []

        # Register memory pressure callback
        self.memory_monitor.register_pressure_callback(self._handle_memory_pressure)

        self.logger.debug("ResourceManager initialized")

    def get_memory_pressure(self) -> float:
        """Get current memory pressure level"""
        return self.memory_monitor.check_memory_pressure()

    def create_buffer(self, name: str, initial_size: Optional[int] = None) -> List[Any]:
        """Create a managed buffer"""
        return self.buffer_manager.create_buffer(name, initial_size)

    def should_flush_buffer(self, name: str) -> bool:
        """Check if buffer should be flushed"""
        pressure = self.get_memory_pressure()
        return self.buffer_manager.should_flush_buffer(name, pressure)

    def flush_buffer(self, name: str) -> List[Any]:
        """Flush buffer contents"""
        return self.buffer_manager.flush_buffer(name)

    def register_temp_file(self, file_path: Union[str, Path]) -> None:
        """Register temporary file for cleanup"""
        path = Path(file_path)
        self.temp_files.append(path)
        self.logger.debug(f"Registered temp file: {path}")

    def register_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """Register cleanup callback"""
        self.cleanup_callbacks.append(callback)

    def cleanup(self) -> None:
        """Clean up all managed resources with improved error handling"""
        self.logger.debug("Starting resource cleanup")

        cleanup_errors = []

        # Execute cleanup callbacks
        for i, callback in enumerate(self.cleanup_callbacks):
            try:
                callback()
            except Exception as e:
                cleanup_errors.append(f"Callback {i}: {e}")

        # Clean up buffers
        try:
            self.buffer_manager.cleanup_all_buffers()
        except Exception as e:
            cleanup_errors.append(f"Buffer cleanup: {e}")

        # Clean up temp files
        try:
            self._cleanup_temp_files()
        except Exception as e:
            cleanup_errors.append(f"Temp file cleanup: {e}")

        # Trigger final garbage collection
        try:
            self.memory_monitor.trigger_gc()
        except Exception as e:
            cleanup_errors.append(f"Garbage collection: {e}")

        # Log results
        if cleanup_errors:
            self.logger.warning(f"Resource cleanup completed with errors: {'; '.join(cleanup_errors)}")
        else:
            self.logger.debug("Resource cleanup completed successfully")

    def get_resource_stats(self) -> ResourceStats:
        """Get current resource usage statistics"""
        pressure = self.get_memory_pressure()

        return ResourceStats(
            memory_usage_mb=pressure * self.memory_monitor.max_memory_mb,
            buffer_count=len(self.buffer_manager.active_buffers),
            file_handles=0,  # TODO: Implement file handle tracking
            temp_files=len(self.temp_files),
            peak_memory_mb=self.memory_monitor.peak_memory / (1024 * 1024),
            gc_collections=self.memory_monitor.gc_count,
            last_cleanup_time=time.time(),
        )

    @contextmanager
    def managed_resource(self, resource: Any, cleanup_func: Optional[Callable] = None):
        """Context manager for automatic resource cleanup"""
        try:
            if cleanup_func:
                self.register_cleanup_callback(lambda: cleanup_func(resource))
            yield resource
        finally:
            if cleanup_func:
                try:
                    cleanup_func(resource)
                except Exception as e:
                    self.logger.warning(f"Resource cleanup failed: {e}")

    def _handle_memory_pressure(self, pressure: float) -> None:
        """Handle memory pressure events with error handling"""
        self.logger.warning(f"Memory pressure detected: {pressure*100:.1f}%")

        try:
            # Flush all buffers under high pressure
            if pressure > 0.9:
                buffer_names = list(self.buffer_manager.active_buffers.keys())
                for buffer_name in buffer_names:
                    try:
                        self.buffer_manager.flush_buffer(buffer_name)
                        self.logger.debug(
                            f"Flushed buffer '{buffer_name}' due to memory pressure"
                        )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to flush buffer '{buffer_name}' during memory pressure: {e}"
                        )

            # Trigger garbage collection
            try:
                self.memory_monitor.trigger_gc()
            except Exception as e:
                self.logger.warning(
                    f"Failed to trigger garbage collection during memory pressure: {e}"
                )

        except Exception as e:
            self.logger.error(f"Error handling memory pressure: {e}")

    def _cleanup_temp_files(self) -> None:
        """Clean up temporary files with enhanced error handling"""
        if not self.temp_files:
            return

        cleaned_count = 0
        failed_count = 0

        # Create a copy of the list to avoid modification during iteration
        temp_files_to_clean = list(self.temp_files)

        for temp_file in temp_files_to_clean:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    cleaned_count += 1
                    self.logger.debug(f"Cleaned up temp file: {temp_file}")
                else:
                    self.logger.debug(f"Temp file already removed: {temp_file}")
            except PermissionError as e:
                failed_count += 1
                self.logger.warning(
                    f"Permission denied cleaning temp file {temp_file}: {e}"
                )
            except OSError as e:
                failed_count += 1
                self.logger.warning(f"OS error cleaning temp file {temp_file}: {e}")
            except Exception as e:
                failed_count += 1
                self.logger.warning(
                    f"Unexpected error cleaning temp file {temp_file}: {e}"
                )

        # Clear the list regardless of cleanup success
        self.temp_files.clear()

        if cleaned_count > 0 or failed_count > 0:
            self.logger.info(
                f"Temp file cleanup completed: {cleaned_count} cleaned, {failed_count} failed"
            )
