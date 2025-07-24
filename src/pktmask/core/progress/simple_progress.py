"""
简化的进度报告系统 - 轻量级重构方案

这是一个最小化的重构方案，解决当前回调链的核心问题：
1. 标准化回调接口
2. 改善异常处理
3. 提升可测试性
4. 保持简单性

总代码量: ~100行，重构时间: 1-2天
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
from enum import Enum

from pktmask.core.events import PipelineEvents
from pktmask.infrastructure.logging import get_logger

logger = get_logger("SimpleProgress")


class ProgressHandler(Protocol):
    """进度处理器协议 - 使用Protocol而非ABC减少复杂度"""
    
    def handle_progress(self, event_type: PipelineEvents, data: Dict[str, Any]) -> None:
        """处理进度事件"""
        ...


class ProgressReporter:
    """简化的进度报告器 - 替代复杂的事件总线"""
    
    def __init__(self):
        self._handlers: List[ProgressHandler] = []
        self._enabled = True
    
    def add_handler(self, handler: ProgressHandler):
        """添加处理器"""
        if handler not in self._handlers:
            self._handlers.append(handler)
    
    def remove_handler(self, handler: ProgressHandler):
        """移除处理器"""
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    def report(self, event_type: PipelineEvents, data: Dict[str, Any]):
        """报告进度事件"""
        if not self._enabled:
            return
        
        for handler in self._handlers:
            try:
                handler.handle_progress(event_type, data)
            except Exception as e:
                # 简单的错误处理 - 记录但不中断其他处理器
                logger.warning(f"Progress handler error: {e}")
    
    def enable(self):
        """启用进度报告"""
        self._enabled = True
    
    def disable(self):
        """禁用进度报告"""
        self._enabled = False


class CLIProgressHandler:
    """CLI进度处理器 - 简化版本"""
    
    def __init__(self, verbose: bool = False, show_stages: bool = False):
        self.verbose = verbose
        self.show_stages = show_stages
        self.current_file = None
        self.total_files = 0
        self.processed_files = 0
    
    def handle_progress(self, event_type: PipelineEvents, data: Dict[str, Any]):
        """处理进度事件"""
        if event_type == PipelineEvents.PIPELINE_START:
            self.total_files = data.get("total_files", 1)
            if self.verbose:
                print(f"🚀 Starting processing {self.total_files} files...")
        
        elif event_type == PipelineEvents.FILE_START:
            self.current_file = data.get("path", "Unknown")
            if self.verbose:
                if self.total_files > 0:
                    progress = ((self.processed_files + 1) / self.total_files) * 100
                    print(f"📄 [{self.processed_files + 1}/{self.total_files}] "
                          f"({progress:.1f}%) {self.current_file}")
                else:
                    print(f"📄 Processing: {self.current_file}")
        
        elif event_type == PipelineEvents.STEP_SUMMARY and self.show_stages:
            stage_name = data.get("step_name", "Unknown")
            packets_processed = data.get("packets_processed", 0)
            duration_ms = data.get("duration_ms", 0.0)
            if self.verbose:
                print(f"  ⚙️  [{stage_name}] {packets_processed:,} packets, {duration_ms:.1f}ms")
        
        elif event_type == PipelineEvents.FILE_END:
            filename = data.get("path", "Unknown")
            success = data.get("success", True)
            self.processed_files += 1
            
            if success:
                print(f"✅ Completed: {filename}")
            else:
                print(f"❌ Failed: {filename}")
        
        elif event_type == PipelineEvents.ERROR:
            error_message = data.get("message", "Unknown error")
            print(f"❌ Error: {error_message}")


class ReportServiceHandler:
    """报告服务处理器 - 简化版本"""
    
    def __init__(self, report_service):
        self.report_service = report_service
    
    def handle_progress(self, event_type: PipelineEvents, data: Dict[str, Any]):
        """处理报告相关事件"""
        if event_type == PipelineEvents.STEP_SUMMARY:
            stage_name = data.get("step_name", "Unknown")
            self.report_service.add_stage_stats(stage_name, data)
        elif event_type == PipelineEvents.ERROR:
            error_message = data.get("message", "Unknown error")
            self.report_service.add_error(error_message)


class GUIProgressHandler:
    """GUI进度处理器 - 简化版本"""
    
    def __init__(self, event_coordinator):
        self.event_coordinator = event_coordinator
    
    def handle_progress(self, event_type: PipelineEvents, data: Dict[str, Any]):
        """处理GUI进度事件"""
        # 直接转发到现有的GUI事件协调器
        self.event_coordinator.emit_pipeline_event(event_type, data)


# 全局进度报告器实例
_global_reporter: Optional[ProgressReporter] = None


def get_progress_reporter() -> ProgressReporter:
    """获取全局进度报告器"""
    global _global_reporter
    if _global_reporter is None:
        _global_reporter = ProgressReporter()
    return _global_reporter


def report_progress(event_type: PipelineEvents, data: Dict[str, Any]):
    """便捷的进度报告函数"""
    get_progress_reporter().report(event_type, data)


# 向后兼容的回调创建函数
def create_simple_progress_callback(
    verbose: bool = False, 
    show_stages: bool = False, 
    report_service=None
):
    """
    创建简化的进度回调函数 - 替代复杂的回调链
    
    这个函数解决了原有回调链的问题，同时保持简单性：
    1. 统一的接口
    2. 清晰的错误处理
    3. 易于测试
    4. 向后兼容
    """
    reporter = get_progress_reporter()
    
    # 清除之前的处理器
    reporter._handlers.clear()
    
    # 添加CLI处理器
    cli_handler = CLIProgressHandler(verbose, show_stages)
    reporter.add_handler(cli_handler)
    
    # 添加报告服务处理器
    if report_service:
        report_handler = ReportServiceHandler(report_service)
        reporter.add_handler(report_handler)
    
    def simple_callback(event_type: PipelineEvents, data: Dict[str, Any]):
        """简化的回调函数"""
        reporter.report(event_type, data)
    
    return simple_callback


def create_gui_progress_callback(event_coordinator):
    """创建GUI专用的进度回调"""
    reporter = ProgressReporter()  # 创建独立实例避免冲突
    
    gui_handler = GUIProgressHandler(event_coordinator)
    reporter.add_handler(gui_handler)
    
    def gui_callback(event_type: PipelineEvents, data: Dict[str, Any]):
        """GUI回调函数"""
        reporter.report(event_type, data)
    
    return gui_callback


# 测试辅助函数
class MockProgressHandler:
    """测试用的模拟处理器"""
    
    def __init__(self):
        self.events = []
    
    def handle_progress(self, event_type: PipelineEvents, data: Dict[str, Any]):
        """记录事件用于测试验证"""
        self.events.append((event_type, data.copy()))
    
    def get_events(self) -> List[tuple]:
        """获取记录的事件"""
        return self.events.copy()
    
    def clear_events(self):
        """清除记录的事件"""
        self.events.clear()


def create_test_progress_callback():
    """创建测试用的进度回调"""
    reporter = ProgressReporter()
    mock_handler = MockProgressHandler()
    reporter.add_handler(mock_handler)
    
    def test_callback(event_type: PipelineEvents, data: Dict[str, Any]):
        reporter.report(event_type, data)
    
    # 返回回调函数和mock处理器，方便测试验证
    return test_callback, mock_handler
