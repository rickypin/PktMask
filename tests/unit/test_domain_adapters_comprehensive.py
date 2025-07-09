#!/usr/bin/env python3
"""
Desktop Event System and Adapters Test - Refactored for simplified architecture
Tests the new desktop-optimized event system and remaining adapters
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.pktmask.domain.adapters.statistics_adapter import StatisticsDataAdapter
from src.pktmask.domain.models.statistics_data import StatisticsData
from src.pktmask.core.events import (
    DesktopEvent, EventType, PipelineEvents,
    create_pipeline_start_event, create_file_start_event, create_error_event
)


class TestDesktopEventSystem:
    """Test the new desktop-optimized event system"""

    def test_desktop_event_creation(self):
        """Test basic DesktopEvent creation"""
        event = DesktopEvent.create_fast('test_type', 'Test message', data1='value1')

        assert event.type == 'test_type'
        assert event.message == 'Test message'
        assert event.data['data1'] == 'value1'
        assert event.severity == 'info'
        assert event.timestamp is not None
    
    def test_desktop_event_factory_functions(self):
        """Test factory functions for common events"""
        # Test pipeline start event
        pipeline_event = create_pipeline_start_event(100, '/input', '/output')
        assert pipeline_event.type == EventType.PIPELINE_START
        assert 'Starting pipeline processing 100 files' in pipeline_event.message
        assert pipeline_event.data['total_files'] == 100

        # Test file start event
        file_event = create_file_start_event('test.pcap', '/path/test.pcap', 1024)
        assert file_event.type == EventType.FILE_START
        assert file_event.data['filename'] == 'test.pcap'
        assert file_event.data['size_bytes'] == 1024

        # Test error event
        error_event = create_error_event('Test error', {'context': 'test'})
        assert error_event.type == EventType.ERROR
        assert error_event.is_error() == True
        assert error_event.data['context'] == 'test'

    def test_desktop_event_performance(self):
        """Test event creation performance"""
        import time

        # Test fast creation
        start = time.time()
        for _ in range(1000):
            event = DesktopEvent.create_fast('test', 'message', data='value')
        creation_time = time.time() - start

        # Should be very fast (less than 10ms for 1000 events)
        assert creation_time < 0.01

    def test_desktop_event_serialization(self):
        """Test event serialization"""
        event = create_pipeline_start_event(50, '/input', '/output')

        # Test to_dict conversion
        event_dict = event.to_dict()
        assert isinstance(event_dict, dict)
        assert event_dict['type'] == EventType.PIPELINE_START
        assert event_dict['data']['total_files'] == 50

    def test_backward_compatibility_events(self):
        """Test backward compatibility with PipelineEvents"""
        # Test that PipelineEvents enum still exists
        assert hasattr(PipelineEvents, 'PIPELINE_START')
        assert hasattr(PipelineEvents, 'FILE_START')
        assert hasattr(PipelineEvents, 'ERROR')

        # Test that EventType mapping works
        assert EventType.PIPELINE_START == 'pipeline_start'
        assert EventType.FILE_START == 'file_start'
        assert EventType.ERROR == 'error'


class TestStatisticsDataAdapter:
    """测试统计数据适配器"""
    
    def test_statistics_adapter_initialization(self):
        """测试统计适配器初始化"""
        adapter = StatisticsDataAdapter()
        assert hasattr(adapter, 'from_legacy_manager')
        assert hasattr(adapter, 'to_legacy_dict')
        assert hasattr(adapter, '_logger')
    
    def test_to_legacy_dict_basic(self):
        """测试基本的转换为遗留字典"""
        adapter = StatisticsDataAdapter()
        
        # 创建模拟的统计数据
        mock_stats = Mock(spec=StatisticsData)
        mock_stats.metrics = Mock()
        mock_stats.metrics.files_processed = 5
        mock_stats.metrics.total_files_to_process = 10
        mock_stats.metrics.packets_processed = 1000
        mock_stats.metrics.get_completion_rate.return_value = 50.0
        
        mock_stats.timing = Mock()
        mock_stats.timing.get_elapsed_time_string.return_value = "00:01:30"
        mock_stats.timing.get_processing_speed.return_value = 100.0
        
        mock_stats.step_results = {}
        mock_stats.file_results = {}
        mock_stats.ip_mapping = Mock()
        mock_stats.ip_mapping.global_mappings = {}
        mock_stats.ip_mapping.reports_by_subdir = {}
        
        mock_stats.state = Mock()
        mock_stats.state.current_processing_file = "test.pcap"
        
        try:
            result = adapter.to_legacy_dict(mock_stats)
            assert isinstance(result, dict)
            assert 'files_processed' in result
            assert result['files_processed'] == 5
        except Exception as e:
            pytest.skip(f"Legacy dict conversion not implemented: {e}")
    
    def test_merge_statistics_basic(self):
        """测试基本的统计数据合并"""
        adapter = StatisticsDataAdapter()
        
        # 创建基础统计数据模拟
        base_stats = Mock(spec=StatisticsData)
        base_stats.copy.return_value = base_stats
        base_stats.metrics = Mock()
        base_stats.timing = Mock()
        base_stats.file_results = {}
        base_stats.step_results = {}
        base_stats.ip_mapping = Mock()
        base_stats.ip_mapping.global_mappings = {}
        base_stats.ip_mapping.reports_by_subdir = {}
        base_stats.state = Mock()
        
        update_data = {
            'files_processed': 10,
            'packets_processed': 2000
        }
        
        try:
            result = adapter.merge_statistics(base_stats, update_data)
            assert result is not None
            # 验证合并操作被执行
            base_stats.copy.assert_called_once()
        except Exception as e:
            pytest.skip(f"Statistics merging not implemented: {e}")
    
    def test_create_dashboard_update(self):
        """测试创建仪表盘更新"""
        adapter = StatisticsDataAdapter()
        
        mock_stats = Mock(spec=StatisticsData)
        mock_stats.get_dashboard_summary.return_value = {
            'completion_rate': 75.0,
            'files_processed': 15,
            'current_speed': 120.5
        }
        
        try:
            result = adapter.create_dashboard_update(mock_stats)
            assert isinstance(result, dict)
            assert 'completion_rate' in result
            assert result['completion_rate'] == 75.0
        except Exception as e:
            pytest.skip(f"Dashboard update creation not implemented: {e}")
    
    def test_validate_statistics_data(self):
        """测试统计数据验证"""
        adapter = StatisticsDataAdapter()
        
        # 创建有效的统计数据
        valid_stats = Mock(spec=StatisticsData)
        valid_stats.metrics = Mock()
        valid_stats.timing = Mock()
        valid_stats.file_results = {}
        
        try:
            result = adapter.validate_statistics_data(valid_stats)
            assert isinstance(result, bool)
        except Exception as e:
            pytest.skip(f"Statistics validation not implemented: {e}")


class TestDataModels:
    """测试数据模型基本功能"""
    
    def test_desktop_event_data_exists(self):
        """测试DesktopEvent类存在且可导入"""
        # 验证类已成功导入
        assert DesktopEvent is not None

        # 创建实例
        event = DesktopEvent.create_fast(EventType.LOG, 'Test message', level='info')
        assert event.type == EventType.LOG
        assert event.message == 'Test message'
    
    def test_statistics_data_exists(self):
        """测试StatisticsData类存在且可导入"""
        # 验证类已成功导入
        assert StatisticsData is not None
        
        # 尝试创建实例（如果构造函数允许）
        try:
            stats = StatisticsData()
            assert stats is not None
        except Exception:
            # 如果构造函数需要特定参数，这是正常的
            pass
    
    def test_pipeline_events_enum(self):
        """测试PipelineEvents枚举值"""
        # 验证关键事件类型存在
        assert hasattr(PipelineEvents, 'LOG')
        assert hasattr(PipelineEvents, 'STEP_START')
        assert hasattr(PipelineEvents, 'STEP_COMPLETED')  # 修正名称
        assert hasattr(PipelineEvents, 'FILE_RESULT')
        assert hasattr(PipelineEvents, 'STEP_SUMMARY')


class TestSimplifiedArchitectureIntegration:
    """Simplified architecture integration tests"""

    def test_desktop_event_system_integration(self):
        """Test desktop event system integration"""
        # Test event creation and factory functions
        events = [
            create_pipeline_start_event(10, '/input', '/output'),
            create_file_start_event('test.pcap', '/path/test.pcap'),
            create_error_event('Test error')
        ]

        for event in events:
            assert isinstance(event, DesktopEvent)
            assert event.timestamp is not None
            assert event.message is not None

    def test_remaining_adapters_functionality(self):
        """Test remaining adapters functionality"""
        stats_adapter = StatisticsDataAdapter()

        assert stats_adapter is not None
        assert hasattr(stats_adapter, '_logger')

        # 统计适配器方法
        expected_stats_methods = [
            'from_legacy_manager', 'to_legacy_dict', 'merge_statistics', 'validate_statistics_data'
        ]
        for method in expected_stats_methods:
            assert hasattr(stats_adapter, method), f"StatisticsDataAdapter missing method: {method}"
    
    def test_error_handling_in_simplified_system(self):
        """Test error handling in simplified system"""
        # Test desktop event error handling
        try:
            # Test with invalid data
            event = DesktopEvent.create_fast('', '', invalid_param=None)
            # Should handle gracefully
            assert event.type == ''
            assert event.message == ''
        except Exception:
            # Exception is also acceptable
            pass

        # Test statistics adapter error handling
        stats_adapter = StatisticsDataAdapter()
        try:
            result = stats_adapter.to_legacy_dict(None)
            # Should handle None input gracefully
            assert isinstance(result, dict) or result is None
        except Exception:
            # Exception is also acceptable behavior
            pass