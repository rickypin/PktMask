"""
简化进度报告系统的单元测试

测试新的简化进度报告系统的核心功能：
1. ProgressReporter的基本功能
2. 各种处理器的正确行为
3. 错误处理机制
4. 向后兼容性
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from pktmask.core.events import PipelineEvents
from pktmask.core.progress.simple_progress import (
    ProgressReporter,
    CLIProgressHandler,
    ReportServiceHandler,
    GUIProgressHandler,
    MockProgressHandler,
    create_simple_progress_callback,
    create_gui_progress_callback,
    create_test_progress_callback,
    get_progress_reporter,
    report_progress
)


class TestProgressReporter:
    """测试ProgressReporter核心功能"""
    
    def test_reporter_creation(self):
        """测试报告器创建"""
        reporter = ProgressReporter()
        assert reporter._enabled is True
        assert len(reporter._handlers) == 0
    
    def test_add_remove_handlers(self):
        """测试添加和移除处理器"""
        reporter = ProgressReporter()
        handler = MockProgressHandler()
        
        # 添加处理器
        reporter.add_handler(handler)
        assert len(reporter._handlers) == 1
        assert handler in reporter._handlers
        
        # 重复添加不会增加
        reporter.add_handler(handler)
        assert len(reporter._handlers) == 1
        
        # 移除处理器
        reporter.remove_handler(handler)
        assert len(reporter._handlers) == 0
        assert handler not in reporter._handlers
    
    def test_report_event(self):
        """测试事件报告"""
        reporter = ProgressReporter()
        handler = MockProgressHandler()
        reporter.add_handler(handler)
        
        # 报告事件
        test_data = {"test": "data"}
        reporter.report(PipelineEvents.FILE_START, test_data)
        
        # 验证处理器收到事件
        events = handler.get_events()
        assert len(events) == 1
        assert events[0][0] == PipelineEvents.FILE_START
        assert events[0][1] == test_data
    
    def test_enable_disable(self):
        """测试启用/禁用功能"""
        reporter = ProgressReporter()
        handler = MockProgressHandler()
        reporter.add_handler(handler)
        
        # 禁用后不应该报告事件
        reporter.disable()
        reporter.report(PipelineEvents.FILE_START, {"test": "data"})
        assert len(handler.get_events()) == 0
        
        # 启用后应该报告事件
        reporter.enable()
        reporter.report(PipelineEvents.FILE_START, {"test": "data"})
        assert len(handler.get_events()) == 1
    
    def test_error_handling(self):
        """测试错误处理"""
        reporter = ProgressReporter()
        
        # 创建会抛出异常的处理器
        class ErrorHandler:
            def handle_progress(self, event_type, data):
                raise ValueError("Test error")
        
        error_handler = ErrorHandler()
        normal_handler = MockProgressHandler()
        
        reporter.add_handler(error_handler)
        reporter.add_handler(normal_handler)
        
        # 报告事件，错误处理器应该不影响正常处理器
        with patch('pktmask.core.progress.simple_progress.logger') as mock_logger:
            reporter.report(PipelineEvents.FILE_START, {"test": "data"})
            
            # 验证错误被记录
            mock_logger.warning.assert_called_once()
            
            # 验证正常处理器仍然工作
            assert len(normal_handler.get_events()) == 1


class TestCLIProgressHandler:
    """测试CLI进度处理器"""
    
    def test_handler_creation(self):
        """测试处理器创建"""
        handler = CLIProgressHandler(verbose=True, show_stages=True)
        assert handler.verbose is True
        assert handler.show_stages is True
        assert handler.total_files == 0
        assert handler.processed_files == 0
    
    def test_pipeline_start(self):
        """测试管道开始事件"""
        handler = CLIProgressHandler(verbose=True)
        
        with patch('builtins.print') as mock_print:
            handler.handle_progress(
                PipelineEvents.PIPELINE_START, 
                {"total_files": 5}
            )
            
            assert handler.total_files == 5
            mock_print.assert_called_once_with("🚀 Starting processing 5 files...")
    
    def test_file_start(self):
        """测试文件开始事件"""
        handler = CLIProgressHandler(verbose=True)
        handler.total_files = 2  # 设置总文件数
        
        with patch('builtins.print') as mock_print:
            handler.handle_progress(
                PipelineEvents.FILE_START, 
                {"path": "test.pcap"}
            )
            
            assert handler.current_file == "test.pcap"
            mock_print.assert_called_once()
            # 验证输出包含进度信息
            call_args = mock_print.call_args[0][0]
            assert "test.pcap" in call_args
            assert "50.0%" in call_args
    
    def test_file_end_success(self):
        """测试文件结束事件（成功）"""
        handler = CLIProgressHandler()
        
        with patch('builtins.print') as mock_print:
            handler.handle_progress(
                PipelineEvents.FILE_END, 
                {"path": "test.pcap", "success": True}
            )
            
            assert handler.processed_files == 1
            mock_print.assert_called_once_with("✅ Completed: test.pcap")
    
    def test_file_end_failure(self):
        """测试文件结束事件（失败）"""
        handler = CLIProgressHandler()
        
        with patch('builtins.print') as mock_print:
            handler.handle_progress(
                PipelineEvents.FILE_END, 
                {"path": "test.pcap", "success": False}
            )
            
            assert handler.processed_files == 1
            mock_print.assert_called_once_with("❌ Failed: test.pcap")
    
    def test_step_summary_verbose(self):
        """测试步骤摘要事件（详细模式）"""
        handler = CLIProgressHandler(verbose=True, show_stages=True)
        
        with patch('builtins.print') as mock_print:
            handler.handle_progress(
                PipelineEvents.STEP_SUMMARY, 
                {
                    "step_name": "dedup",
                    "packets_processed": 1000,
                    "duration_ms": 150.5
                }
            )
            
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "dedup" in call_args
            assert "1,000" in call_args
            assert "150.5ms" in call_args
    
    def test_error_event(self):
        """测试错误事件"""
        handler = CLIProgressHandler()
        
        with patch('builtins.print') as mock_print:
            handler.handle_progress(
                PipelineEvents.ERROR, 
                {"message": "Test error"}
            )
            
            mock_print.assert_called_once_with("❌ Error: Test error")


class TestReportServiceHandler:
    """测试报告服务处理器"""
    
    def test_step_summary_handling(self):
        """测试步骤摘要处理"""
        mock_service = Mock()
        handler = ReportServiceHandler(mock_service)
        
        test_data = {
            "step_name": "dedup",
            "packets_processed": 100,
            "duration_ms": 50.0
        }
        
        handler.handle_progress(PipelineEvents.STEP_SUMMARY, test_data)
        
        mock_service.add_stage_stats.assert_called_once_with("dedup", test_data)
    
    def test_error_handling(self):
        """测试错误处理"""
        mock_service = Mock()
        handler = ReportServiceHandler(mock_service)
        
        handler.handle_progress(
            PipelineEvents.ERROR, 
            {"message": "Test error"}
        )
        
        mock_service.add_error.assert_called_once_with("Test error")


class TestGUIProgressHandler:
    """测试GUI进度处理器"""
    
    def test_event_forwarding(self):
        """测试事件转发"""
        mock_coordinator = Mock()
        handler = GUIProgressHandler(mock_coordinator)
        
        test_data = {"test": "data"}
        handler.handle_progress(PipelineEvents.FILE_START, test_data)
        
        mock_coordinator.emit_pipeline_event.assert_called_once_with(
            PipelineEvents.FILE_START, test_data
        )


class TestCallbackCreation:
    """测试回调函数创建"""
    
    def test_create_simple_progress_callback(self):
        """测试创建简单进度回调"""
        mock_service = Mock()
        callback = create_simple_progress_callback(
            verbose=True, 
            show_stages=True, 
            report_service=mock_service
        )
        
        # 测试回调函数
        with patch('builtins.print'):
            callback(PipelineEvents.STEP_SUMMARY, {
                "step_name": "test",
                "packets_processed": 100
            })
        
        # 验证报告服务被调用
        mock_service.add_stage_stats.assert_called_once()
    
    def test_create_gui_progress_callback(self):
        """测试创建GUI进度回调"""
        mock_coordinator = Mock()
        callback = create_gui_progress_callback(mock_coordinator)
        
        test_data = {"test": "data"}
        callback(PipelineEvents.FILE_START, test_data)
        
        mock_coordinator.emit_pipeline_event.assert_called_once_with(
            PipelineEvents.FILE_START, test_data
        )
    
    def test_create_test_progress_callback(self):
        """测试创建测试进度回调"""
        callback, mock_handler = create_test_progress_callback()
        
        # 测试回调记录事件
        test_data = {"test": "data"}
        callback(PipelineEvents.FILE_START, test_data)
        
        events = mock_handler.get_events()
        assert len(events) == 1
        assert events[0][0] == PipelineEvents.FILE_START
        assert events[0][1] == test_data


class TestGlobalFunctions:
    """测试全局函数"""
    
    def test_get_progress_reporter(self):
        """测试获取全局进度报告器"""
        reporter1 = get_progress_reporter()
        reporter2 = get_progress_reporter()
        
        # 应该返回同一个实例
        assert reporter1 is reporter2
    
    def test_report_progress(self):
        """测试全局进度报告函数"""
        # 清理全局状态
        import pktmask.core.progress.simple_progress as module
        module._global_reporter = None
        
        handler = MockProgressHandler()
        reporter = get_progress_reporter()
        reporter.add_handler(handler)
        
        test_data = {"test": "data"}
        report_progress(PipelineEvents.FILE_START, test_data)
        
        events = handler.get_events()
        assert len(events) == 1
        assert events[0][0] == PipelineEvents.FILE_START
        assert events[0][1] == test_data


class TestMockProgressHandler:
    """测试模拟进度处理器"""
    
    def test_event_recording(self):
        """测试事件记录"""
        handler = MockProgressHandler()
        
        # 记录多个事件
        handler.handle_progress(PipelineEvents.FILE_START, {"file": "test1.pcap"})
        handler.handle_progress(PipelineEvents.FILE_END, {"file": "test1.pcap"})
        
        events = handler.get_events()
        assert len(events) == 2
        assert events[0][0] == PipelineEvents.FILE_START
        assert events[1][0] == PipelineEvents.FILE_END
    
    def test_clear_events(self):
        """测试清除事件"""
        handler = MockProgressHandler()
        
        handler.handle_progress(PipelineEvents.FILE_START, {"test": "data"})
        assert len(handler.get_events()) == 1
        
        handler.clear_events()
        assert len(handler.get_events()) == 0


if __name__ == "__main__":
    pytest.main([__file__])
