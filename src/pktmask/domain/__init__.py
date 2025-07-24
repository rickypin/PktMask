"""
Domain模块

包含业务数据模型和适配器。
"""

from .models import (
    BaseEventData,
    BaseStepResult,
    FileInfo,
    FileProcessingData,
    FileProcessingResults,
    IPMappingData,
    PipelineEventData,
    ProcessingMetrics,
    ProcessingState,
    ReportData,
    ReportSection,
    StatisticsData,
    StepResultData,
    TimingData,
)

# Note: Legacy adapter layer has been eliminated
# Direct scapy operations are now used instead of adapter abstraction

__all__ = [
    # 数据模型
    "StatisticsData",
    "ProcessingMetrics",
    "TimingData",
    "FileProcessingResults",
    "IPMappingData",
    "ProcessingState",
    "PipelineEventData",
    "BaseEventData",
    "StepResultData",
    "BaseStepResult",
    "FileProcessingData",
    "FileInfo",
    "ReportData",
    "ReportSection",
]
