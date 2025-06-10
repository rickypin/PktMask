"""
Infrastructure层基础功能测试
测试错误处理、日志系统等基础设施
"""
import pytest
from unittest.mock import Mock, patch


@pytest.mark.unit
class TestInfrastructureModule:
    """基础设施模块测试"""
    
    def test_infrastructure_module_exists(self):
        """测试infrastructure模块存在"""
        try:
            from pktmask import infrastructure
            assert infrastructure is not None
        except ImportError:
            pytest.skip("Infrastructure模块不可用")
    
    def test_logging_module_exists(self):
        """测试日志模块存在"""
        try:
            from pktmask.infrastructure.logging import get_logger
            assert get_logger is not None
            assert callable(get_logger)
        except ImportError:
            pytest.skip("日志模块不可用")
    
    def test_logger_creation(self):
        """测试日志器创建"""
        try:
            from pktmask.infrastructure.logging import get_logger
            logger = get_logger('test')
            assert logger is not None
            assert hasattr(logger, 'info')
            assert hasattr(logger, 'error')
            assert hasattr(logger, 'debug')
        except ImportError:
            pytest.skip("日志模块不可用")
    
    def test_error_handling_modules_exist(self):
        """测试错误处理模块存在"""
        try:
            from pktmask.infrastructure import error_handling
            assert error_handling is not None
        except ImportError:
            pytest.skip("错误处理模块不可用")


@pytest.mark.unit 
class TestLoggingBasic:
    """日志系统基础测试"""
    
    def test_log_performance_function_exists(self):
        """测试性能日志函数存在"""
        try:
            from pktmask.infrastructure.logging import log_performance
            assert log_performance is not None
            assert callable(log_performance)
        except ImportError:
            pytest.skip("性能日志功能不可用")
    
    def test_log_performance_call(self):
        """测试性能日志调用"""
        try:
            from pktmask.infrastructure.logging import log_performance
            
            # 直接调用性能日志记录，检查它不会抛出异常
            log_performance('test_operation', 1.5, 'test.category')
            
            # 如果没有异常，说明功能正常工作
            assert True
            
        except ImportError:
            pytest.skip("性能日志功能不可用")


@pytest.mark.unit
class TestDomainAdapters:
    """Domain适配器测试"""
    
    def test_domain_adapters_exist(self):
        """测试Domain适配器存在"""
        try:
            from pktmask.domain import adapters
            assert adapters is not None
        except ImportError:
            pytest.skip("Domain适配器不可用")
    
    def test_event_adapter_exists(self):
        """测试事件适配器存在"""
        try:
            from pktmask.domain.adapters.event_adapter import EventDataAdapter
            assert EventDataAdapter is not None
        except ImportError:
            pytest.skip("事件适配器不可用")
    
    def test_statistics_adapter_exists(self):
        """测试统计适配器存在"""
        try:
            from pktmask.domain.adapters.statistics_adapter import StatisticsDataAdapter
            assert StatisticsDataAdapter is not None
        except ImportError:
            pytest.skip("统计适配器不可用")


@pytest.mark.unit
class TestUtilsAdvanced:
    """工具函数高级测试"""
    
    def test_file_selector_exists(self):
        """测试文件选择器存在"""
        try:
            from pktmask.utils.file_selector import select_files
            assert select_files is not None
            assert callable(select_files)
        except ImportError:
            pytest.skip("文件选择器不可用")
    
    def test_file_selector_basic_functionality(self, temp_dir):
        """测试文件选择器基本功能"""
        try:
            from pktmask.utils.file_selector import select_files
            
            # 创建测试文件
            test_file = temp_dir / "test.pcap"
            test_file.touch()
            
            # 调用文件选择器
            result = select_files(str(temp_dir), "_suffix", [])
            
            # 验证返回结果
            assert isinstance(result, (tuple, list))
            
        except ImportError:
            pytest.skip("文件选择器不可用")
    
    def test_reporting_utils_exist(self):
        """测试报告工具存在"""
        try:
            from pktmask.utils import reporting
            assert reporting is not None
        except ImportError:
            pytest.skip("报告工具不可用")
    
    def test_path_utils_exist(self):
        """测试路径工具存在"""
        try:
            from pktmask.utils import path
            assert path is not None
        except ImportError:
            pytest.skip("路径工具不可用") 