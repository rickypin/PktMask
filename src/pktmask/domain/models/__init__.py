"""
Data model module

Contains all core data transfer objects and business models。
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
    # File processing data
    "FileProcessingData",
    "FileInfo",
    "ProcessingProgress",
    "ProcessingContext",
    "OutputInfo",
    "ProcessingError",
    # Statistics data
    "StatisticsData",
    "ProcessingMetrics",
    "TimingData",
    "FileProcessingResults",
    "IPMappingData",
    "ProcessingState",
    # Pipeline event data
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
    # Step result data
    "StepResultData",
    "BaseStepResult",
    "IPAnonymizationResult",
    "DeduplicationResult",
    "TrimmingResult",
    "CustomStepResult",
    "FileStepResults",
    # Report data
    "ReportData",
    "ReportSection",
    "ProcessingSummary",
    "StepStatistics",
    "ErrorSummary",
    "PerformanceMetrics",
]
