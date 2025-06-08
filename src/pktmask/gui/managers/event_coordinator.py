#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
事件协调器 - 管理器间通信的中心化协调器
减少管理器间的直接依赖关系，支持新的数据模型传递
"""

from typing import TYPE_CHECKING, Dict, Any, Callable, Set, Union
from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from ..main_window import MainWindow

from pktmask.infrastructure.logging import get_logger
from pktmask.domain.adapters import EventDataAdapter, StatisticsDataAdapter
from pktmask.domain.models.pipeline_event_data import PipelineEventData
from pktmask.domain.models.statistics_data import StatisticsData
from pktmask.core.events import PipelineEvents

class EventCoordinator(QObject):
    """事件协调器 - 中心化管理器间通信，支持新数据模型"""
    
    # 统计数据更新信号
    statistics_updated = pyqtSignal(dict)  # 统计数据变更
    ui_update_requested = pyqtSignal(str, dict)  # UI更新请求
    file_operation_requested = pyqtSignal(str, dict)  # 文件操作请求
    report_generation_requested = pyqtSignal(str, dict)  # 报告生成请求
    
    # 新增：结构化数据信号
    pipeline_event_data = pyqtSignal(PipelineEventData)  # 管道事件数据
    statistics_data_updated = pyqtSignal(StatisticsData)  # 统计数据模型更新
    
    def __init__(self, main_window: 'MainWindow'):
        super().__init__()
        self.main_window = main_window
        self._logger = get_logger(__name__)
        
        # 初始化适配器
        self.event_adapter = EventDataAdapter()
        self.stats_adapter = StatisticsDataAdapter()
        
        # 订阅者注册表
        self._subscribers: Dict[str, Set[Callable]] = {
            'statistics_changed': set(),
            'ui_state_changed': set(),
            'processing_event': set(),
            'file_operation': set(),
            'report_request': set(),
            'pipeline_event': set(),  # 新增：管道事件
            'statistics_data': set()   # 新增：统计数据模型
        }
        
        self._logger.debug("EventCoordinator initialized with data adapters")
    
    def subscribe(self, event_type: str, callback: Callable):
        """订阅事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()
        self._subscribers[event_type].add(callback)
        self._logger.debug(f"Subscribed to {event_type}: {callback.__name__}")
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """取消订阅事件"""
        if event_type in self._subscribers:
            self._subscribers[event_type].discard(callback)
            self._logger.debug(f"Unsubscribed from {event_type}: {callback.__name__}")
    
    def emit_event(self, event_type: str, data: Union[Dict[str, Any], PipelineEventData, StatisticsData]):
        """发布事件，支持多种数据格式"""
        # 处理结构化数据
        if isinstance(data, PipelineEventData):
            self._emit_pipeline_event(data)
            return
        elif isinstance(data, StatisticsData):
            self._emit_statistics_data(data)
            return
        
        # 处理传统字典数据
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    self._logger.error(f"Error in event callback {callback.__name__}: {e}")
        
        # 发出Qt信号
        if event_type == 'statistics_changed':
            self.statistics_updated.emit(data)
        elif event_type == 'ui_state_changed':
            self.ui_update_requested.emit(data.get('action', ''), data)
        elif event_type == 'file_operation':
            self.file_operation_requested.emit(data.get('operation', ''), data)
        elif event_type == 'report_request':
            self.report_generation_requested.emit(data.get('report_type', ''), data)
    
    def _emit_pipeline_event(self, event_data: PipelineEventData):
        """发布管道事件数据"""
        # 调用订阅者
        for callback in self._subscribers.get('pipeline_event', []):
            try:
                callback(event_data)
            except Exception as e:
                self._logger.error(f"Error in pipeline event callback {callback.__name__}: {e}")
        
        # 发出Qt信号
        self.pipeline_event_data.emit(event_data)
        
        # 为向后兼容，也发出传统格式
        legacy_data = self.event_adapter.to_legacy_dict(event_data)
        self.emit_event('processing_event', legacy_data)
        
        self._logger.debug(f"Pipeline event emitted: {event_data.event_type}")
    
    def _emit_statistics_data(self, stats_data: StatisticsData):
        """发布统计数据"""
        # 调用订阅者
        for callback in self._subscribers.get('statistics_data', []):
            try:
                callback(stats_data)
            except Exception as e:
                self._logger.error(f"Error in statistics data callback {callback.__name__}: {e}")
        
        # 发出Qt信号
        self.statistics_data_updated.emit(stats_data)
        
        # 为向后兼容，也发出传统格式
        legacy_data = self.stats_adapter.to_legacy_dict(stats_data)
        self.emit_event('statistics_changed', legacy_data)
        
        self._logger.debug(f"Statistics data emitted: {stats_data.metrics.files_processed} files")
    
    def request_ui_update(self, action: str, **kwargs):
        """请求UI更新"""
        data = {'action': action, **kwargs}
        self.emit_event('ui_state_changed', data)
    
    def notify_statistics_change(self, **kwargs):
        """通知统计数据变化"""
        self.emit_event('statistics_changed', kwargs)
    
    def request_file_operation(self, operation: str, **kwargs):
        """请求文件操作"""
        data = {'operation': operation, **kwargs}
        self.emit_event('file_operation', data)
    
    def request_report_generation(self, report_type: str, **kwargs):
        """请求报告生成"""
        data = {'report_type': report_type, **kwargs}
        self.emit_event('report_request', data)
    
    def notify_processing_event(self, event_name: str, **kwargs):
        """通知处理事件"""
        data = {'event': event_name, **kwargs}
        self.emit_event('processing_event', data)
    
    def get_statistics_data(self) -> Dict[str, Any]:
        """获取统计数据（通过StatisticsManager）- 遗留方法"""
        if hasattr(self.main_window, 'pipeline_manager') and hasattr(self.main_window.pipeline_manager, 'statistics'):
            return self.main_window.pipeline_manager.statistics.get_dashboard_stats()
        return {}
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """获取处理摘要（通过StatisticsManager）- 遗留方法"""
        if hasattr(self.main_window, 'pipeline_manager') and hasattr(self.main_window.pipeline_manager, 'statistics'):
            return self.main_window.pipeline_manager.statistics.get_processing_summary()
        return {}
    
    def get_structured_statistics(self) -> StatisticsData:
        """获取结构化统计数据"""
        if hasattr(self.main_window, 'pipeline_manager') and hasattr(self.main_window.pipeline_manager, 'statistics'):
            return self.stats_adapter.from_legacy_manager(self.main_window.pipeline_manager.statistics)
        return StatisticsData()
    
    def emit_pipeline_event(self, event_type: PipelineEvents, data: Dict[str, Any]):
        """发布管道事件（转换为结构化数据）"""
        event_data = self.event_adapter.from_legacy_dict(event_type, data)
        self.emit_event('pipeline_event', event_data)
    
    def emit_statistics_update(self, stats_manager):
        """发布统计数据更新（转换为结构化数据）"""
        stats_data = self.stats_adapter.from_legacy_manager(stats_manager)
        self.emit_event('statistics_data', stats_data)
    
    def reset_all_data(self):
        """重置所有数据"""
        self.notify_statistics_change(action='reset')
        self.request_ui_update('reset')
        self._logger.debug("All data reset requested")
    
    def shutdown(self):
        """关闭协调器"""
        for event_type in self._subscribers:
            self._subscribers[event_type].clear()
        self._logger.debug("EventCoordinator shutdown") 