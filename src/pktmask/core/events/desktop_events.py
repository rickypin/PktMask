"""
Desktop-optimized event system for PktMask

Lightweight event system designed for desktop applications:
- No runtime validation overhead
- Minimal memory footprint
- Fast creation and access
- Simple serialization
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """Event types for desktop application"""

    # Pipeline events
    PIPELINE_START = "pipeline_start"
    PIPELINE_END = "pipeline_end"

    # Directory events
    SUBDIR_START = "subdir_start"
    SUBDIR_END = "subdir_end"

    # File events
    FILE_START = "file_start"
    FILE_END = "file_end"

    # Step events
    STEP_START = "step_start"
    STEP_END = "step_end"
    STEP_SUMMARY = "step_summary"

    # Other events
    PACKETS_SCANNED = "packets_scanned"
    LOG = "log"
    ERROR = "error"
    PROGRESS_UPDATE = "progress_update"
    GUI_UPDATE = "gui_update"


class EventSeverity(str, Enum):
    """Event severity levels"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DesktopEvent:
    """Desktop application optimized event data structure

    Design principles:
    - Minimal memory footprint
    - Fast creation and access
    - No runtime validation overhead
    - Simple serialization
    """

    type: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    severity: str = "info"

    def to_dict(self) -> dict:
        """Fast conversion to dictionary for GUI display"""
        return asdict(self)

    @classmethod
    def create_fast(cls, event_type: str, message: str, **data) -> "DesktopEvent":
        """Fast event creation optimized for desktop application performance"""
        return cls(type=event_type, message=message, data=data)

    def is_error(self) -> bool:
        """Fast error check"""
        return self.severity in ("error", "critical")

    def get_display_text(self) -> str:
        """Get user-friendly display text"""
        timestamp_str = self.timestamp.strftime("%H:%M:%S")
        return f"[{timestamp_str}] {self.message}"

    def get_progress(self) -> Optional[int]:
        """Get progress value if this is a progress event"""
        if self.type == EventType.PROGRESS_UPDATE:
            return self.data.get("progress", 0)
        return None

    def get_file_info(self) -> Optional[Dict[str, str]]:
        """Get file information if this is a file event"""
        if self.type in (EventType.FILE_START, EventType.FILE_END):
            return {
                "filename": self.data.get("filename", ""),
                "path": self.data.get("path", ""),
                "size": str(self.data.get("size_bytes", 0)),
            }
        return None


# Factory functions for common events
def create_pipeline_start_event(
    total_files: int, root_path: str, output_dir: str
) -> DesktopEvent:
    """Create pipeline start event"""
    return DesktopEvent.create_fast(
        EventType.PIPELINE_START,
        f"Starting pipeline processing {total_files} files",
        total_files=total_files,
        root_path=root_path,
        output_dir=output_dir,
    )


def create_pipeline_end_event(
    success: bool, files_processed: int, duration_ms: int
) -> DesktopEvent:
    """Create pipeline end event"""
    status = "completed" if success else "failed"
    return DesktopEvent.create_fast(
        EventType.PIPELINE_END,
        f"Pipeline {status}: {files_processed} files processed in {duration_ms}ms",
        success=success,
        files_processed=files_processed,
        duration_ms=duration_ms,
    )


def create_file_start_event(
    filename: str, path: str, size_bytes: Optional[int] = None
) -> DesktopEvent:
    """Create file start event"""
    return DesktopEvent.create_fast(
        EventType.FILE_START,
        f"Processing file: {filename}",
        filename=filename,
        path=path,
        size_bytes=size_bytes or 0,
    )


def create_file_end_event(
    filename: str, success: bool, duration_ms: int
) -> DesktopEvent:
    """Create file end event"""
    status = "completed" if success else "failed"
    return DesktopEvent.create_fast(
        EventType.FILE_END,
        f"File {status}: {filename} ({duration_ms}ms)",
        filename=filename,
        success=success,
        duration_ms=duration_ms,
    )


def create_step_start_event(step_name: str, filename: str) -> DesktopEvent:
    """Create step start event"""
    return DesktopEvent.create_fast(
        EventType.STEP_START,
        f"Starting {step_name} on {filename}",
        step_name=step_name,
        filename=filename,
    )


def create_step_end_event(
    step_name: str, filename: str, success: bool, duration_ms: int
) -> DesktopEvent:
    """Create step end event"""
    status = "completed" if success else "failed"
    return DesktopEvent.create_fast(
        EventType.STEP_END,
        f"Step {status}: {step_name} on {filename} ({duration_ms}ms)",
        step_name=step_name,
        filename=filename,
        success=success,
        duration_ms=duration_ms,
    )


def create_progress_event(progress: int, message: str = "") -> DesktopEvent:
    """Create progress update event"""
    return DesktopEvent.create_fast(
        EventType.PROGRESS_UPDATE,
        message or f"Progress: {progress}%",
        progress=progress,
    )


def create_error_event(
    error_message: str, context: Optional[Dict[str, Any]] = None
) -> DesktopEvent:
    """Create error event"""
    event = DesktopEvent.create_fast(
        EventType.ERROR, f"Error: {error_message}", error_message=error_message
    )
    event.severity = EventSeverity.ERROR
    if context:
        event.data.update(context)
    return event


def create_log_event(message: str, level: str = "info") -> DesktopEvent:
    """Create log event"""
    event = DesktopEvent.create_fast(EventType.LOG, message, level=level)
    event.severity = level
    return event
