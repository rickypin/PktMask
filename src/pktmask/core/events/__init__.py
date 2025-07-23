"""
Desktop-optimized event system

Lightweight event system for desktop applications.
"""

from .desktop_events import (
    DesktopEvent,
    EventType,
    EventSeverity,
    create_pipeline_start_event,
    create_pipeline_end_event,
    create_file_start_event,
    create_file_end_event,
    create_step_start_event,
    create_step_end_event,
    create_progress_event,
    create_error_event,
    create_log_event,
)

# Backward compatibility - re-export PipelineEvents from the original location
from enum import Enum, auto


class PipelineEvents(Enum):
    """Legacy pipeline events for backward compatibility"""

    # 管道级别事件
    PIPELINE_START = auto()
    PIPELINE_STARTED = auto()  # 别名，为了向后兼容
    PIPELINE_END = auto()
    PIPELINE_COMPLETED = auto()  # 别名，为了向后兼容

    # 目录级别事件
    SUBDIR_START = auto()
    SUBDIR_END = auto()

    # 文件级别事件
    FILE_START = auto()
    FILE_STARTED = auto()  # 别名，为了向后兼容
    FILE_END = auto()
    FILE_COMPLETED = auto()  # 别名，为了向后兼容

    # 步骤级别事件
    STEP_START = auto()
    STEP_STARTED = auto()  # 别名，为了向后兼容
    STEP_END = auto()
    STEP_COMPLETED = auto()  # 别名，为了向后兼容
    STEP_SUMMARY = auto()

    # 其他事件
    PACKETS_SCANNED = auto()
    FILE_RESULT = auto()
    LOG = auto()
    ERROR = auto()


# Event type mapping for backward compatibility
EVENT_TYPE_MAPPING = {
    PipelineEvents.PIPELINE_START: EventType.PIPELINE_START,
    PipelineEvents.PIPELINE_STARTED: EventType.PIPELINE_START,
    PipelineEvents.PIPELINE_END: EventType.PIPELINE_END,
    PipelineEvents.PIPELINE_COMPLETED: EventType.PIPELINE_END,
    PipelineEvents.SUBDIR_START: EventType.SUBDIR_START,
    PipelineEvents.SUBDIR_END: EventType.SUBDIR_END,
    PipelineEvents.FILE_START: EventType.FILE_START,
    PipelineEvents.FILE_STARTED: EventType.FILE_START,
    PipelineEvents.FILE_END: EventType.FILE_END,
    PipelineEvents.FILE_COMPLETED: EventType.FILE_END,
    PipelineEvents.STEP_START: EventType.STEP_START,
    PipelineEvents.STEP_STARTED: EventType.STEP_START,
    PipelineEvents.STEP_END: EventType.STEP_END,
    PipelineEvents.STEP_COMPLETED: EventType.STEP_END,
    PipelineEvents.STEP_SUMMARY: EventType.STEP_SUMMARY,
    PipelineEvents.PACKETS_SCANNED: EventType.PACKETS_SCANNED,
    PipelineEvents.LOG: EventType.LOG,
    PipelineEvents.ERROR: EventType.ERROR,
}

__all__ = [
    "DesktopEvent",
    "EventType",
    "EventSeverity",
    "create_pipeline_start_event",
    "create_pipeline_end_event",
    "create_file_start_event",
    "create_file_end_event",
    "create_step_start_event",
    "create_step_end_event",
    "create_progress_event",
    "create_error_event",
    "create_log_event",
    "PipelineEvents",
    "EVENT_TYPE_MAPPING",
]
