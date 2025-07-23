"""
Pipeline event data models

Defines data structures for various events during pipeline processing.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, field_validator

from ...core.events import PipelineEvents


class EventSeverity(str, Enum):
    """Event severity levels"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class BaseEventData(BaseModel):
    """Base event data"""

    event_type: PipelineEvents = Field(..., description="Event type")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    severity: EventSeverity = Field(
        default=EventSeverity.INFO, description="Event severity level"
    )
    message: Optional[str] = Field(default=None, description="Event message")

    model_config = {"use_enum_values": True}


class PipelineStartData(BaseEventData):
    """Pipeline start event data"""

    total_subdirs: int = Field(default=0, ge=0, description="Total number of subdirectories")
    total_files: int = Field(default=0, ge=0, description="Total number of files")
    root_path: str = Field(..., description="Root path")
    output_dir: str = Field(..., description="Output directory")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.PIPELINE_START, **data)


class PipelineEndData(BaseEventData):
    """Pipeline end event data"""

    success: bool = Field(default=True, description="Whether completed successfully")
    files_processed: int = Field(default=0, ge=0, description="Number of files processed")
    errors_count: int = Field(default=0, ge=0, description="Number of errors")
    duration_ms: int = Field(default=0, ge=0, description="Processing duration (milliseconds)")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.PIPELINE_END, **data)


class SubdirStartData(BaseEventData):
    """Subdirectory start event data"""

    name: str = Field(..., description="Subdirectory name")
    path: str = Field(..., description="Subdirectory path")
    file_count: int = Field(default=0, ge=0, description="Number of files")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.SUBDIR_START, **data)


class SubdirEndData(BaseEventData):
    """Subdirectory end event data"""

    name: str = Field(..., description="Subdirectory name")
    files_processed: int = Field(default=0, ge=0, description="Number of files processed")
    success: bool = Field(default=True, description="Whether completed successfully")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.SUBDIR_END, **data)


class FileStartData(BaseEventData):
    """File start event data"""

    path: str = Field(..., description="File path")
    filename: str = Field(..., description="Filename")
    size_bytes: Optional[int] = Field(default=None, ge=0, description="File size (bytes)")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.FILE_START, **data)
        if "filename" not in data and "path" in data:
            self.filename = data["path"].split("/")[-1]


class FileEndData(BaseEventData):
    """File end event data"""

    path: str = Field(..., description="File path")
    filename: str = Field(..., description="Filename")
    success: bool = Field(default=True, description="Whether processed successfully")
    output_filename: Optional[str] = Field(default=None, description="Output filename")
    packets_processed: int = Field(default=0, ge=0, description="Number of packets processed")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.FILE_END, **data)
        if "filename" not in data and "path" in data:
            self.filename = data["path"].split("/")[-1]


class StepStartData(BaseEventData):
    """Step start event data"""

    step_name: str = Field(..., description="Step name")
    step_type: str = Field(..., description="Step type")
    filename: str = Field(..., description="Filename being processed")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.STEP_START, **data)


class StepEndData(BaseEventData):
    """Step end event data"""

    step_name: str = Field(..., description="Step name")
    step_type: str = Field(..., description="Step type")
    filename: str = Field(..., description="Processed filename")
    success: bool = Field(default=True, description="Whether completed successfully")
    duration_ms: int = Field(default=0, ge=0, description="Step duration (milliseconds)")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.STEP_END, **data)


class StepSummaryData(BaseEventData):
    """Step summary event data"""

    step_name: str = Field(..., description="Step name")
    step_type: str = Field(..., description="Step type")
    filename: str = Field(..., description="Filename")
    result: Dict[str, Any] = Field(default_factory=dict, description="Step result data")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.STEP_SUMMARY, **data)


class PacketsScannedData(BaseEventData):
    """Packets scanned event data"""

    count: int = Field(..., ge=0, description="Number of packets scanned")
    filename: Optional[str] = Field(default=None, description="Filename")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.PACKETS_SCANNED, **data)


class LogEventData(BaseEventData):
    """Log event data"""

    log_message: str = Field(..., description="Log message")
    log_level: str = Field(default="INFO", description="Log level")
    source: Optional[str] = Field(default=None, description="Log source")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.LOG, **data)
        if "message" not in data and "log_message" in data:
            self.message = data["log_message"]


class ErrorEventData(BaseEventData):
    """Error event data"""

    error_message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(default=None, description="Error code")
    traceback: Optional[str] = Field(default=None, description="Error traceback")
    context: Dict[str, Any] = Field(default_factory=dict, description="Error context")

    def __init__(self, **data):
        super().__init__(
            event_type=PipelineEvents.ERROR, severity=EventSeverity.ERROR, **data
        )
        if "message" not in data and "error_message" in data:
            self.message = data["error_message"]


# Event data type mapping
EVENT_DATA_MAPPING = {
    PipelineEvents.PIPELINE_START: PipelineStartData,
    PipelineEvents.PIPELINE_STARTED: PipelineStartData,
    PipelineEvents.PIPELINE_END: PipelineEndData,
    PipelineEvents.PIPELINE_COMPLETED: PipelineEndData,
    PipelineEvents.SUBDIR_START: SubdirStartData,
    PipelineEvents.SUBDIR_END: SubdirEndData,
    PipelineEvents.FILE_START: FileStartData,
    PipelineEvents.FILE_STARTED: FileStartData,
    PipelineEvents.FILE_END: FileEndData,
    PipelineEvents.FILE_COMPLETED: FileEndData,
    PipelineEvents.STEP_START: StepStartData,
    PipelineEvents.STEP_STARTED: StepStartData,
    PipelineEvents.STEP_END: StepEndData,
    PipelineEvents.STEP_COMPLETED: StepEndData,
    PipelineEvents.STEP_SUMMARY: StepSummaryData,
    PipelineEvents.PACKETS_SCANNED: PacketsScannedData,
    PipelineEvents.LOG: LogEventData,
    PipelineEvents.ERROR: ErrorEventData,
}


class PipelineEventData(BaseModel):
    """Universal wrapper for pipeline event data"""

    event_type: PipelineEvents = Field(..., description="Event type")
    data: Union[
        PipelineStartData,
        PipelineEndData,
        SubdirStartData,
        SubdirEndData,
        FileStartData,
        FileEndData,
        StepStartData,
        StepEndData,
        StepSummaryData,
        PacketsScannedData,
        LogEventData,
        ErrorEventData,
        BaseEventData,
    ] = Field(..., description="Event data")

    @field_validator("data", mode="before")
    @classmethod
    def validate_event_data(cls, v, info):
        """Validate event data type"""
        event_type = info.data.get("event_type") if info.data else None

        if isinstance(v, dict):
            # If it's a dictionary, try to convert to appropriate data type
            data_class = EVENT_DATA_MAPPING.get(event_type, BaseEventData)
            return data_class(**v)

        return v

    model_config = {"use_enum_values": True}

    def to_legacy_dict(self) -> dict:
        """Convert to legacy dictionary format for backward compatibility"""
        result = self.data.model_dump()
        result["type"] = (
            self.event_type.name
            if hasattr(self.event_type, "name")
            else str(self.event_type)
        )
        return result

    @classmethod
    def from_legacy_dict(
        cls, event_type: PipelineEvents, data: dict
    ) -> "PipelineEventData":
        """Create event data from legacy dictionary format"""
        data_class = EVENT_DATA_MAPPING.get(event_type, BaseEventData)
        event_data = data_class(event_type=event_type, **data)
        return cls(event_type=event_type, data=event_data)
