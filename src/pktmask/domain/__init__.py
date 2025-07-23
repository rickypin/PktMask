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

# 注意：适配器已经迁移到 pktmask.adapters 模块
# 为了避免循环导入，不再从这里导出适配器
# 请直接使用：
#   from pktmask.adapters import EventDataAdapter, StatisticsDataAdapter

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
