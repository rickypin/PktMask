"""
数据模型模块

包含所有核心数据传输对象和业务模型。
"""

from .file_processing_data import (
    FileInfo,
    FileProcessingData,
    OutputInfo,
    ProcessingContext,
    ProcessingError,
    ProcessingProgress,
)
from .pipeline_event_data import (
    BaseEventData,
    ErrorEventData,
    FileEndData,
    FileStartData,
    LogEventData,
    PacketsScannedData,
    PipelineEndData,
    PipelineEventData,
    PipelineStartData,
    StepEndData,
    StepStartData,
    StepSummaryData,
    SubdirEndData,
    SubdirStartData,
)
from .report_data import (
    ErrorSummary,
    PerformanceMetrics,
    ProcessingSummary,
    ReportData,
    ReportSection,
    StepStatistics,
)
from .statistics_data import (
    FileProcessingResults,
    IPMappingData,
    ProcessingMetrics,
    ProcessingState,
    StatisticsData,
    TimingData,
)
from .step_result_data import (
    BaseStepResult,
    CustomStepResult,
    DeduplicationResult,
    FileStepResults,
    IPAnonymizationResult,
    StepResultData,
    TrimmingResult,
)

__all__ = [
    # 文件处理数据
    "FileProcessingData",
    "FileInfo",
    "ProcessingProgress",
    "ProcessingContext",
    "OutputInfo",
    "ProcessingError",
    # 统计数据
    "StatisticsData",
    "ProcessingMetrics",
    "TimingData",
    "FileProcessingResults",
    "IPMappingData",
    "ProcessingState",
    # 管道事件数据
    "PipelineEventData",
    "BaseEventData",
    "PipelineStartData",
    "PipelineEndData",
    "SubdirStartData",
    "SubdirEndData",
    "FileStartData",
    "FileEndData",
    "StepStartData",
    "StepEndData",
    "StepSummaryData",
    "PacketsScannedData",
    "LogEventData",
    "ErrorEventData",
    # 步骤结果数据
    "StepResultData",
    "BaseStepResult",
    "IPAnonymizationResult",
    "DeduplicationResult",
    "TrimmingResult",
    "CustomStepResult",
    "FileStepResults",
    # 报告数据
    "ReportData",
    "ReportSection",
    "ProcessingSummary",
    "StepStatistics",
    "ErrorSummary",
    "PerformanceMetrics",
]
