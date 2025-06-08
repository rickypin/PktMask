"""
Domain模块

包含业务数据模型和适配器。
"""

from .models import (
    StatisticsData, ProcessingMetrics, TimingData, FileProcessingResults,
    IPMappingData, ProcessingState, PipelineEventData, BaseEventData,
    StepResultData, BaseStepResult, FileProcessingData, FileInfo,
    ReportData, ReportSection
)

from .adapters import (
    EventDataAdapter, StatisticsDataAdapter
)

__all__ = [
    # 数据模型
    'StatisticsData', 'ProcessingMetrics', 'TimingData', 'FileProcessingResults',
    'IPMappingData', 'ProcessingState', 'PipelineEventData', 'BaseEventData',
    'StepResultData', 'BaseStepResult', 'FileProcessingData', 'FileInfo',
    'ReportData', 'ReportSection',
    
    # 适配器
    'EventDataAdapter', 'StatisticsDataAdapter'
] 