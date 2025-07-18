#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Desktop-optimized Event Coordinator

Simplified event coordinator for desktop applications:
- Minimal signal overhead
- Fast event dispatch
- Memory-friendly subscription management
- Exception isolation
"""

from typing import TYPE_CHECKING, Dict, Any, Callable, Set
from PyQt6.QtCore import QObject, pyqtSignal
from collections import defaultdict
import logging

if TYPE_CHECKING:
    from ..main_window import MainWindow

from pktmask.core.events import DesktopEvent, EventType

class DesktopEventCoordinator(QObject):
    """Desktop application optimized event coordinator

    Optimization features:
    - Minimal signal overhead
    - Fast event dispatch
    - Memory-friendly subscription management
    - Exception isolation
    """

    # Optimized signal definitions
    event_emitted = pyqtSignal(object)  # DesktopEvent
    error_occurred = pyqtSignal(str)    # Error event dedicated signal
    progress_updated = pyqtSignal(int)  # Progress update dedicated signal



    # Structured data signals for enhanced processing
    pipeline_event_data = pyqtSignal(object)  # PipelineEventData
    statistics_data_updated = pyqtSignal(dict)  # Statistics data

    def __init__(self, main_window: 'MainWindow'):
        super().__init__()
        self.main_window = main_window
        self._logger = logging.getLogger(__name__)
        self._subscribers: Dict[str, Set[Callable]] = defaultdict(set)

        # Performance optimization: pre-allocate common event types
        for event_type in [EventType.PIPELINE_START, EventType.FILE_START,
                          EventType.STEP_START, EventType.ERROR]:
            self._subscribers[event_type] = set()

        self._logger.debug("DesktopEventCoordinator initialized")
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to events (using set to avoid duplicate subscriptions)"""
        self._subscribers[event_type].add(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe from events"""
        self._subscribers[event_type].discard(callback)

    def emit_event(self, event: DesktopEvent):
        """High-performance event publishing"""
        # Fast path: error events
        if event.is_error():
            self.error_occurred.emit(event.message)

        # Fast path: progress events
        if event.type == EventType.PROGRESS_UPDATE:
            progress = event.data.get('progress', 0)
            self.progress_updated.emit(progress)

        # Call subscribers (with exception isolation)
        for callback in self._subscribers[event.type]:
            try:
                callback(event)
            except Exception as e:
                self._logger.error(f"Event callback error: {e}")

        # Emit general signal
        self.event_emitted.emit(event)




    
    def emit_fast(self, event_type: str, message: str, **data):
        """Fast event emission (reduces object creation)"""
        event = DesktopEvent.create_fast(event_type, message, **data)
        self.emit_event(event)
    
    # Simplified convenience methods for desktop application
    def request_ui_update(self, action: str, **kwargs):
        """Request UI update"""
        self.emit_fast(EventType.GUI_UPDATE, f"UI update: {action}", action=action, ui_update=True, **kwargs)

    def notify_statistics_change(self, **kwargs):
        """Notify statistics data change"""
        self.emit_fast(EventType.PROGRESS_UPDATE, "Statistics updated", **kwargs)

    def request_file_operation(self, operation: str, **kwargs):
        """Request file operation"""
        self.emit_fast(EventType.GUI_UPDATE, f"File operation: {operation}", operation=operation, file_operation=True, **kwargs)

    def request_report_generation(self, report_type: str, **kwargs):
        """Request report generation"""
        self.emit_fast(EventType.GUI_UPDATE, f"Report generation: {report_type}", report_type=report_type, report_request=True, **kwargs)

    def notify_processing_event(self, event_name: str, **kwargs):
        """Notify processing event"""
        self.emit_fast(EventType.LOG, f"Processing: {event_name}", event=event_name, **kwargs)

    def emit_pipeline_event(self, event_type, data: dict):
        """Emit pipeline event with structured data (legacy compatibility method)"""
        try:
            # Try to create structured event data if available
            from pktmask.domain.models.pipeline_event_data import PipelineEventData

            # Create structured event data with proper format
            event_data = PipelineEventData(event_type=event_type, data=data)
            self.pipeline_event_data.emit(event_data)

        except ImportError:
            # Fallback to simple event emission
            self._logger.debug("Structured event models not available, using simple event")
            message = data.get('message', 'Pipeline event')
            # Remove 'message' from data to avoid conflicts
            clean_data = {k: v for k, v in data.items() if k != 'message'}
            self.emit_fast(str(event_type), message, **clean_data)
        except Exception as e:
            # Fallback to simple event emission on any error
            self._logger.debug(f"Failed to create structured event: {e}")
            message = data.get('message', 'Pipeline event')
            # Remove 'message' from data to avoid conflicts
            clean_data = {k: v for k, v in data.items() if k != 'message'}
            self.emit_fast(str(event_type), message, **clean_data)

    def get_statistics_data(self) -> Dict[str, Any]:
        """Get statistics data (legacy method)"""
        if hasattr(self.main_window, 'pipeline_manager') and hasattr(self.main_window.pipeline_manager, 'statistics'):
            return self.main_window.pipeline_manager.statistics.get_dashboard_stats()
        return {}

    def get_processing_summary(self) -> Dict[str, Any]:
        """Get processing summary (legacy method)"""
        if hasattr(self.main_window, 'pipeline_manager') and hasattr(self.main_window.pipeline_manager, 'statistics'):
            return self.main_window.pipeline_manager.statistics.get_processing_summary()
        return {}

    def reset_all_data(self):
        """重置所有数据（用于重置状态）"""
        self.emit_fast(EventType.GUI_UPDATE, "Reset all data", action='reset')
        self._logger.debug("Reset all data requested")

    def clear_subscribers(self):
        """Clear all subscribers (memory management)"""
        self._subscribers.clear()

    def shutdown(self):
        """Shutdown coordinator"""
        self.clear_subscribers()
        self._logger.debug("DesktopEventCoordinator shutdown")


# Backward compatibility alias
EventCoordinator = DesktopEventCoordinator