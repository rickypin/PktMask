#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
事件协调器 - 管理器间通信的中心化协调器
减少管理器间的直接依赖关系
"""

from typing import TYPE_CHECKING, Dict, Any, Callable, Set
from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from ..main_window import MainWindow

from ...infrastructure.logging import get_logger

class EventCoordinator(QObject):
    """事件协调器 - 中心化管理器间通信"""
    
    # 统计数据更新信号
    statistics_updated = pyqtSignal(dict)  # 统计数据变更
    ui_update_requested = pyqtSignal(str, dict)  # UI更新请求
    file_operation_requested = pyqtSignal(str, dict)  # 文件操作请求
    report_generation_requested = pyqtSignal(str, dict)  # 报告生成请求
    
    def __init__(self, main_window: 'MainWindow'):
        super().__init__()
        self.main_window = main_window
        self._logger = get_logger(__name__)
        
        # 订阅者注册表
        self._subscribers: Dict[str, Set[Callable]] = {
            'statistics_changed': set(),
            'ui_state_changed': set(),
            'processing_event': set(),
            'file_operation': set(),
            'report_request': set()
        }
        
        self._logger.debug("EventCoordinator initialized")
    
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
    
    def emit_event(self, event_type: str, data: Dict[str, Any]):
        """发布事件"""
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
        """获取统计数据（通过StatisticsManager）"""
        if hasattr(self.main_window, 'pipeline_manager') and hasattr(self.main_window.pipeline_manager, 'statistics'):
            return self.main_window.pipeline_manager.statistics.get_dashboard_stats()
        return {}
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """获取处理摘要（通过StatisticsManager）"""
        if hasattr(self.main_window, 'pipeline_manager') and hasattr(self.main_window.pipeline_manager, 'statistics'):
            return self.main_window.pipeline_manager.statistics.get_processing_summary()
        return {}
    
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