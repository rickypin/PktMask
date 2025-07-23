"""
管道事件数据模型

定义管道处理过程中各种事件的数据结构。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, field_validator

from ...core.events import PipelineEvents


class EventSeverity(str, Enum):
    """事件严重程度"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class BaseEventData(BaseModel):
    """基础事件数据"""

    event_type: PipelineEvents = Field(..., description="事件类型")
    timestamp: datetime = Field(default_factory=datetime.now, description="事件时间戳")
    severity: EventSeverity = Field(
        default=EventSeverity.INFO, description="事件严重程度"
    )
    message: Optional[str] = Field(default=None, description="事件消息")

    model_config = {"use_enum_values": True}


class PipelineStartData(BaseEventData):
    """管道开始事件数据"""

    total_subdirs: int = Field(default=0, ge=0, description="总子目录数")
    total_files: int = Field(default=0, ge=0, description="总文件数")
    root_path: str = Field(..., description="根路径")
    output_dir: str = Field(..., description="输出目录")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.PIPELINE_START, **data)


class PipelineEndData(BaseEventData):
    """管道结束事件数据"""

    success: bool = Field(default=True, description="是否成功完成")
    files_processed: int = Field(default=0, ge=0, description="已处理文件数")
    errors_count: int = Field(default=0, ge=0, description="错误数量")
    duration_ms: int = Field(default=0, ge=0, description="处理耗时(毫秒)")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.PIPELINE_END, **data)


class SubdirStartData(BaseEventData):
    """子目录开始事件数据"""

    name: str = Field(..., description="子目录名称")
    path: str = Field(..., description="子目录路径")
    file_count: int = Field(default=0, ge=0, description="文件数量")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.SUBDIR_START, **data)


class SubdirEndData(BaseEventData):
    """子目录结束事件数据"""

    name: str = Field(..., description="子目录名称")
    files_processed: int = Field(default=0, ge=0, description="已处理文件数")
    success: bool = Field(default=True, description="是否成功完成")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.SUBDIR_END, **data)


class FileStartData(BaseEventData):
    """文件开始事件数据"""

    path: str = Field(..., description="文件路径")
    filename: str = Field(..., description="文件名")
    size_bytes: Optional[int] = Field(default=None, ge=0, description="文件大小(字节)")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.FILE_START, **data)
        if "filename" not in data and "path" in data:
            self.filename = data["path"].split("/")[-1]


class FileEndData(BaseEventData):
    """文件结束事件数据"""

    path: str = Field(..., description="文件路径")
    filename: str = Field(..., description="文件名")
    success: bool = Field(default=True, description="是否成功处理")
    output_filename: Optional[str] = Field(default=None, description="输出文件名")
    packets_processed: int = Field(default=0, ge=0, description="处理的包数")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.FILE_END, **data)
        if "filename" not in data and "path" in data:
            self.filename = data["path"].split("/")[-1]


class StepStartData(BaseEventData):
    """步骤开始事件数据"""

    step_name: str = Field(..., description="步骤名称")
    step_type: str = Field(..., description="步骤类型")
    filename: str = Field(..., description="正在处理的文件名")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.STEP_START, **data)


class StepEndData(BaseEventData):
    """步骤结束事件数据"""

    step_name: str = Field(..., description="步骤名称")
    step_type: str = Field(..., description="步骤类型")
    filename: str = Field(..., description="已处理的文件名")
    success: bool = Field(default=True, description="是否成功完成")
    duration_ms: int = Field(default=0, ge=0, description="步骤耗时(毫秒)")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.STEP_END, **data)


class StepSummaryData(BaseEventData):
    """步骤摘要事件数据"""

    step_name: str = Field(..., description="步骤名称")
    step_type: str = Field(..., description="步骤类型")
    filename: str = Field(..., description="文件名")
    result: Dict[str, Any] = Field(default_factory=dict, description="步骤结果数据")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.STEP_SUMMARY, **data)


class PacketsScannedData(BaseEventData):
    """包扫描事件数据"""

    count: int = Field(..., ge=0, description="扫描的包数量")
    filename: Optional[str] = Field(default=None, description="文件名")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.PACKETS_SCANNED, **data)


class LogEventData(BaseEventData):
    """日志事件数据"""

    log_message: str = Field(..., description="日志消息")
    log_level: str = Field(default="INFO", description="日志级别")
    source: Optional[str] = Field(default=None, description="日志来源")

    def __init__(self, **data):
        super().__init__(event_type=PipelineEvents.LOG, **data)
        if "message" not in data and "log_message" in data:
            self.message = data["log_message"]


class ErrorEventData(BaseEventData):
    """错误事件数据"""

    error_message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    traceback: Optional[str] = Field(default=None, description="错误堆栈")
    context: Dict[str, Any] = Field(default_factory=dict, description="错误上下文")

    def __init__(self, **data):
        super().__init__(
            event_type=PipelineEvents.ERROR, severity=EventSeverity.ERROR, **data
        )
        if "message" not in data and "error_message" in data:
            self.message = data["error_message"]


# 事件数据类型映射
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
    """管道事件数据的通用包装器"""

    event_type: PipelineEvents = Field(..., description="事件类型")
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
    ] = Field(..., description="事件数据")

    @field_validator("data", mode="before")
    @classmethod
    def validate_event_data(cls, v, info):
        """验证事件数据类型"""
        event_type = info.data.get("event_type") if info.data else None

        if isinstance(v, dict):
            # 如果是字典，尝试转换为相应的数据类型
            data_class = EVENT_DATA_MAPPING.get(event_type, BaseEventData)
            return data_class(**v)

        return v

    model_config = {"use_enum_values": True}

    def to_legacy_dict(self) -> dict:
        """转换为遗留的字典格式，用于向后兼容"""
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
        """从遗留的字典格式创建事件数据"""
        data_class = EVENT_DATA_MAPPING.get(event_type, BaseEventData)
        event_data = data_class(event_type=event_type, **data)
        return cls(event_type=event_type, data=event_data)
