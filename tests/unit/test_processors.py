"""
处理器模块单元测试
测试去重、IP匿名化、载荷修剪等核心功能
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pktmask.core.processors.deduplicator import Deduplicator
from pktmask.core.processors.ip_anonymizer import IPAnonymizer
from pktmask.core.processors.trimmer import Trimmer
from pktmask.core.processors.registry import ProcessorRegistry
from pktmask.core.processors.base_processor import BaseProcessor
from pktmask.config.settings import AppConfig


class TestDeduplicator:
    """去重处理器测试"""
    
    @pytest.fixture
    def deduplicator(self, processor_config):
        """创建去重处理器实例"""
        processor = Deduplicator(processor_config)
        # 不在这里初始化，让测试方法控制
        return processor
    
    def test_initialization(self, deduplicator):
        """测试去重处理器初始化"""
        assert deduplicator is not None
        assert hasattr(deduplicator, 'process_file')
        assert hasattr(deduplicator, 'is_initialized')
    
    def test_is_initialized_property(self, deduplicator):
        """测试初始化状态属性"""
        # 初始状态应该是未初始化的
        assert deduplicator.is_initialized is False
        # 初始化后应该是True
        assert deduplicator.initialize() is True
        assert deduplicator.is_initialized is True
    
    def test_process_success(self, deduplicator, temp_dir):
        """测试成功处理"""
        # 创建测试文件
        input_file = temp_dir / "test_input.pcap"
        output_file = temp_dir / "test_output.pcap"
        input_file.touch()
        
        # 初始化处理器
        deduplicator.initialize()
        
        # 直接mock处理器的step属性
        mock_step = Mock()
        mock_step.process_file.return_value = {
            'total_packets': 100,
            'unique_packets': 80,
            'removed_count': 20
        }
        deduplicator._step = mock_step
        
        # 执行处理
        result = deduplicator.process_file(str(input_file), str(output_file))
        
        # 验证结果  
        assert result is not None
        assert result.success is True
        assert hasattr(result, 'data')
        assert hasattr(result, 'stats')
        
    def test_process_invalid_input(self, deduplicator):
        """测试无效输入文件处理"""
        result = deduplicator.process_file("nonexistent.pcap", "output.pcap")
        assert result.success is False
        assert result.error is not None


class TestIPAnonymizer:
    """IP匿名化处理器测试"""
    
    @pytest.fixture
    def ip_anonymizer(self, processor_config):
        """创建IP匿名化处理器实例"""
        processor = IPAnonymizer(processor_config)
        # 不在这里初始化，让测试方法控制
        return processor
    
    def test_initialization(self, ip_anonymizer):
        """测试IP匿名化处理器初始化"""
        assert ip_anonymizer is not None
        assert hasattr(ip_anonymizer, 'process_file')
        assert hasattr(ip_anonymizer, 'is_initialized')
    
    def test_is_initialized_property(self, ip_anonymizer):
        """测试初始化状态属性"""
        # 初始状态应该是未初始化的
        assert ip_anonymizer.is_initialized is False
        # 初始化后应该是True
        assert ip_anonymizer.initialize() is True
        assert ip_anonymizer.is_initialized is True
    
    def test_process_success(self, ip_anonymizer, temp_dir):
        """测试成功处理"""
        # 创建测试文件
        input_file = temp_dir / "test_input.pcap"
        output_file = temp_dir / "test_output.pcap"
        input_file.touch()
        
        # 初始化处理器
        ip_anonymizer.initialize()
        
        # 直接mock处理器的step属性
        mock_step = Mock()
        mock_step.process_file.return_value = {
            'original_ips': 50,
            'anonymized_ips': 50,
            'total_packets': 100,
            'anonymized_packets': 80,
            'file_ip_mappings': {'192.168.1.1': '10.0.0.1'}
        }
        ip_anonymizer._step = mock_step
        
        # 执行处理
        result = ip_anonymizer.process_file(str(input_file), str(output_file))
        
        # 验证结果
        assert result is not None
        assert result.success is True
        assert hasattr(result, 'data')
        assert hasattr(result, 'stats')


class TestTrimmer:
    """载荷修剪处理器测试"""
    
    @pytest.fixture
    def trimmer(self, processor_config):
        """创建载荷修剪处理器实例"""
        processor = Trimmer(processor_config)
        # 不在这里初始化，让测试方法控制
        return processor
    
    def test_initialization(self, trimmer):
        """测试载荷修剪处理器初始化"""
        assert trimmer is not None
        assert hasattr(trimmer, 'process_file')
        assert hasattr(trimmer, 'is_initialized')
    
    def test_is_initialized_property(self, trimmer):
        """测试初始化状态属性"""
        # 初始状态应该是未初始化的
        assert trimmer.is_initialized is False
        # 初始化后应该是True
        assert trimmer.initialize() is True
        assert trimmer.is_initialized is True
    
    def test_process_success(self, trimmer, temp_dir):
        """测试成功处理"""
        # 创建测试文件
        input_file = temp_dir / "test_input.pcap"
        output_file = temp_dir / "test_output.pcap"
        input_file.touch()
        
        # 初始化处理器
        trimmer.initialize()
        
        # 直接mock处理器的step属性
        mock_step = Mock()
        mock_step.process_file.return_value = {
            'total_packets': 100,
            'trimmed_packets': 30,
            'trim_rate': 30.0
        }
        trimmer._step = mock_step
        
        # 执行处理
        result = trimmer.process_file(str(input_file), str(output_file))
        
        # 验证结果
        assert result is not None
        assert result.success is True
        assert hasattr(result, 'data')
        assert hasattr(result, 'stats')


class TestProcessorRegistry:
    """处理器注册表测试"""
    
    def test_list_built_in_processors(self):
        """测试列出内置处理器"""
        processors = ProcessorRegistry.list_processors()
        assert isinstance(processors, list)
        assert len(processors) > 0
        assert "mask_ip" in processors
        assert "dedup_packet" in processors
        assert "trim_packet" in processors
    
    def test_get_processor(self):
        """测试获取处理器"""
        config = Mock()
        config.name = "mask_ip"
        
        # 获取处理器实例
        processor = ProcessorRegistry.get_processor("mask_ip", config)
        assert processor is not None
        assert hasattr(processor, 'process_file')
        
    def test_register_processor(self):
        """测试注册自定义处理器"""
        # 创建模拟处理器类
        class MockProcessor(BaseProcessor):
            def __init__(self, config):
                super().__init__(config)
                
            def initialize(self):
                return True
                
            def process_file(self, input_file, output_file):
                return Mock()
        
        # 注册处理器
        ProcessorRegistry.register_processor("test_processor", MockProcessor)
        
        # 验证注册成功
        processors = ProcessorRegistry.list_processors()
        assert "test_processor" in processors
        
        # 清理测试数据
        ProcessorRegistry.unregister_processor("test_processor")
    
    def test_get_nonexistent_processor(self):
        """测试获取不存在的处理器"""
        config = Mock()
        with pytest.raises(ValueError):
            ProcessorRegistry.get_processor("nonexistent", config)
    
    def test_processor_availability_check(self):
        """测试处理器可用性检查"""
        assert ProcessorRegistry.is_processor_available("mask_ip") is True
        assert ProcessorRegistry.is_processor_available("nonexistent") is False


@pytest.mark.unit
class TestProcessorIntegration:
    """处理器集成测试"""
    
    def test_all_processors_can_be_instantiated(self, processor_config):
        """测试所有处理器都可以正常实例化"""
        processor_classes = [Deduplicator, IPAnonymizer, Trimmer]
        
        for ProcessorClass in processor_classes:
            processor = ProcessorClass(processor_config)
            assert processor is not None
            assert processor.initialize() is True
            assert processor.is_initialized is True
    
    def test_processors_have_consistent_interface(self, processor_config):
        """测试所有处理器都有一致的接口"""
        processor_classes = [Deduplicator, IPAnonymizer, Trimmer]
        
        for ProcessorClass in processor_classes:
            processor = ProcessorClass(processor_config) 
            processor.initialize()
            
            # 检查必需的方法
            assert hasattr(processor, 'process_file')
            assert hasattr(processor, 'is_initialized')
            assert callable(processor.process_file) 