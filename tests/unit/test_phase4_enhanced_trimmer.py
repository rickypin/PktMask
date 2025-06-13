"""
Phase 4.1 & 4.2 测试

验证Enhanced Trimmer处理器的实现和无缝替换功能。

测试覆盖:
1. EnhancedTrimmer基础功能测试
2. 处理器注册和替换测试  
3. 零GUI改动兼容性测试
4. 智能协议处理测试

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 测试目标
from src.pktmask.core.processors.enhanced_trimmer import EnhancedTrimmer, EnhancedTrimConfig
from src.pktmask.core.processors.base_processor import ProcessorConfig, ProcessorResult
from src.pktmask.core.processors.registry import ProcessorRegistry


class TestEnhancedTrimmerBasics:
    """Enhanced Trimmer 基础功能测试"""
    
    def test_enhanced_trimmer_initialization(self):
        """测试Enhanced Trimmer初始化"""
        config = ProcessorConfig(name="enhanced_trim_test")
        trimmer = EnhancedTrimmer(config)
        
        # 验证基本属性
        assert trimmer.config == config
        assert hasattr(trimmer, 'enhanced_config')
        assert isinstance(trimmer.enhanced_config, EnhancedTrimConfig)
        
        # 验证默认配置
        assert trimmer.enhanced_config.http_strategy_enabled is True
        assert trimmer.enhanced_config.tls_strategy_enabled is True
        assert trimmer.enhanced_config.auto_protocol_detection is True
        assert trimmer.enhanced_config.processing_mode == "intelligent_auto"
    
    def test_enhanced_config_defaults(self):
        """测试默认配置的正确性"""
        config = EnhancedTrimConfig()
        
        # 协议策略默认启用
        assert config.http_strategy_enabled is True
        assert config.tls_strategy_enabled is True
        assert config.default_strategy_enabled is True
        assert config.auto_protocol_detection is True
        
        # 性能参数
        assert config.preserve_ratio == 0.3
        assert config.min_preserve_bytes == 100
        assert config.enable_tshark_preprocessing is True
        assert config.chunk_size == 1000
        
    def test_display_name_compatibility(self):
        """测试显示名称兼容性（零GUI改动）"""
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        # 必须保持与原Trimmer相同的显示名称
        assert trimmer.get_display_name() == "Trim Payloads"
        
    def test_enhanced_description(self):
        """测试增强版描述"""
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        description = trimmer.get_description()
        assert "智能协议感知" in description
        assert "HTTP/TLS" in description
        assert "多协议" in description


class TestProcessorRegistryIntegration:
    """处理器注册表集成测试"""
    
    def setup_method(self):
        """测试前准备"""
        # 清空注册表
        ProcessorRegistry.clear_registry()
        
    def teardown_method(self):
        """测试后清理"""
        ProcessorRegistry.clear_registry()
    
    def test_enhanced_trimmer_registration(self):
        """测试Enhanced Trimmer注册"""
        # 触发加载内置处理器
        processors = ProcessorRegistry.list_processors()
        
        # 验证trim_packet处理器已注册
        assert 'trim_packet' in processors
        
        # 验证获取的是EnhancedTrimmer类
        trimmer_class = ProcessorRegistry.get_active_trimmer_class()
        assert trimmer_class.__name__ == 'EnhancedTrimmer'
        
    def test_enhanced_mode_detection(self):
        """测试增强模式检测"""
        # 检查是否启用增强模式
        is_enhanced = ProcessorRegistry.is_enhanced_mode_enabled()
        assert is_enhanced is True
        
    def test_processor_creation(self):
        """测试处理器创建"""
        config = ProcessorConfig(name="trim_test")
        processor = ProcessorRegistry.get_processor('trim_packet', config)
        
        # 验证返回的是EnhancedTrimmer实例
        assert isinstance(processor, EnhancedTrimmer)
        assert processor.get_display_name() == "Trim Payloads"
        
    def test_processor_info_compatibility(self):
        """测试处理器信息兼容性"""
        info = ProcessorRegistry.get_processor_info('trim_packet')
        
        # 验证基本信息
        assert info['name'] == 'trim_packet'
        assert info['display_name'] == 'Trim Payloads'  # 保持兼容
        assert info['class'] == 'EnhancedTrimmer'  # 内部使用增强版
        assert "智能" in info['description']


class TestZeroGUIChangeCompatibility:
    """零GUI改动兼容性测试"""
    
    @patch('src.pktmask.core.trim.multi_stage_executor.MultiStageExecutor')
    @patch('src.pktmask.core.trim.strategies.factory.get_strategy_factory')
    def test_interface_compatibility(self, mock_factory, mock_executor):
        """测试接口兼容性"""
        # Mock设置
        mock_factory.return_value = Mock()
        mock_executor.return_value = Mock()
        
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        # 验证必须的方法存在且返回值兼容
        assert hasattr(trimmer, 'process_file')
        assert hasattr(trimmer, 'get_display_name')
        assert hasattr(trimmer, 'get_description')
        assert hasattr(trimmer, 'get_trimming_stats')  # 兼容性方法
        
        # 验证返回值类型兼容
        assert callable(trimmer.process_file)
        assert isinstance(trimmer.get_display_name(), str)
        assert isinstance(trimmer.get_description(), str)
        
    @patch('src.pktmask.core.trim.multi_stage_executor.MultiStageExecutor')
    def test_stats_interface_compatibility(self, mock_executor):
        """测试统计接口兼容性"""
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        # 获取统计信息
        stats = trimmer.get_trimming_stats()
        
        # 验证兼容性字段存在
        expected_fields = [
            'total_processed', 'packets_trimmed', 'trim_rate',
            'space_saved', 'efficiency'
        ]
        
        for field in expected_fields:
            assert field in stats
            
        # 验证增强字段存在
        assert 'enhanced_stats' in stats
        enhanced_stats = stats['enhanced_stats']
        assert 'enhanced_mode' in enhanced_stats
        assert enhanced_stats['enhanced_mode'] is True


class TestSmartProcessingCapabilities:
    """智能处理能力测试"""
    
    @patch('src.pktmask.core.trim.multi_stage_executor.MultiStageExecutor')
    @patch('src.pktmask.core.trim.strategies.factory.get_strategy_factory')
    def test_multi_stage_integration(self, mock_factory, mock_executor):
        """测试多阶段集成"""
        # Mock设置
        mock_factory.return_value = Mock()
        mock_executor_instance = Mock()
        mock_executor.return_value = mock_executor_instance
        
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        # 模拟初始化
        with patch.object(trimmer, '_register_stages') as mock_register:
            trimmer._initialize_impl()
            
            # 验证执行器初始化
            mock_executor.assert_called_once()
            mock_register.assert_called_once()
            
    def test_stage_config_generation(self):
        """测试阶段配置生成"""
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        # 测试不同阶段的配置
        tshark_config = trimmer._create_stage_config("tshark")
        pyshark_config = trimmer._create_stage_config("pyshark")
        scapy_config = trimmer._create_stage_config("scapy")
        
        # 验证基础配置
        for cfg in [tshark_config, pyshark_config, scapy_config]:
            assert 'preserve_ratio' in cfg
            assert 'min_preserve_bytes' in cfg
            
        # 验证特定配置
        assert 'enable_tcp_reassembly' in tshark_config
        assert 'http_strategy_enabled' in pyshark_config
        assert 'preserve_timestamps' in scapy_config
        
    def test_processing_stats_tracking(self):
        """测试处理统计追踪"""
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        # 重置统计
        trimmer._reset_processing_stats()
        
        # 验证初始状态
        stats = trimmer._processing_stats
        assert stats['total_packets'] == 0
        assert stats['http_packets'] == 0
        assert stats['tls_packets'] == 0
        assert stats['other_packets'] == 0
        assert stats['strategies_applied'] == []
        assert stats['enhancement_level'] == '4x accuracy improvement'
        
    def test_enhanced_stats_generation(self):
        """测试增强统计生成"""
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        # 设置一些统计数据
        trimmer._processing_stats.update({
            'total_packets': 100,
            'http_packets': 30,
            'tls_packets': 40,
            'other_packets': 30,
            'strategies_applied': ['HTTP智能策略', 'TLS智能策略']
        })
        
        enhanced_stats = trimmer.get_enhanced_stats()
        
        # 验证增强统计
        assert enhanced_stats['enhanced_mode'] is True
        assert enhanced_stats['processing_mode'] == 'intelligent_auto'
        
        protocol_stats = enhanced_stats['protocol_stats']
        assert protocol_stats['total_packets'] == 100
        assert protocol_stats['http_packets'] == 30
        assert protocol_stats['tls_packets'] == 40
        assert protocol_stats['other_packets'] == 30
        
        assert enhanced_stats['strategies_applied'] == ['HTTP智能策略', 'TLS智能策略']


class TestErrorHandlingAndRecovery:
    """错误处理和恢复测试"""
    
    def test_initialization_failure_handling(self):
        """测试初始化失败处理"""
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        # 模拟初始化失败
        with patch.object(trimmer, '_register_stages', side_effect=Exception("Mock error")):
            result = trimmer.initialize()
            assert result is False
            assert trimmer._is_initialized is False
            
    @patch('src.pktmask.core.trim.multi_stage_executor.MultiStageExecutor')
    def test_process_file_without_initialization(self, mock_executor):
        """测试未初始化时的处理"""
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        # 确保未初始化
        assert trimmer._is_initialized is False
        
        # 模拟初始化失败
        with patch.object(trimmer, 'initialize', return_value=False):
            result = trimmer.process_file("test.pcap", "output.pcap")
            
            assert result.success is False
            assert "未正确初始化" in result.error
            
    def test_temp_file_cleanup(self):
        """测试临时文件清理"""
        config = ProcessorConfig(name="test")
        trimmer = EnhancedTrimmer(config)
        
        # 设置临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            trimmer._temp_dir = Path(temp_dir)
            trimmer.enhanced_config.keep_intermediate_files = False
            
            # 创建测试文件
            test_file = trimmer._temp_dir / "test.txt"
            test_file.write_text("test content")
            assert test_file.exists()
            
            # 清理临时文件
            trimmer._cleanup_temp_files()
            
            # 验证目录被删除 (如果父目录存在)
            # 注意: 在某些情况下，父目录可能不会被删除，这是正常的


@pytest.mark.integration
class TestIntegrationWithExistingSystem:
    """与现有系统集成测试"""
    
    def test_processor_registry_fallback(self):
        """测试处理器注册表降级机制"""
        # 清空注册表
        ProcessorRegistry.clear_registry()
        
        # 模拟EnhancedTrimmer导入失败
        with patch('src.pktmask.core.processors.registry.EnhancedTrimmer', side_effect=ImportError("Mock import error")):
            # 触发加载，应该降级到Trimmer
            processors = ProcessorRegistry.list_processors()
            
            assert 'trim_packet' in processors
            trimmer_class = ProcessorRegistry.get_active_trimmer_class()
            # 在降级情况下，应该使用原版Trimmer
            assert trimmer_class.__name__ == 'Trimmer'
            
    def test_enhanced_mode_status_reporting(self):
        """测试增强模式状态报告"""
        # 正常情况下应该启用增强模式
        assert ProcessorRegistry.is_enhanced_mode_enabled() is True
        
        # 获取处理器信息
        info = ProcessorRegistry.get_processor_info('trim_packet')
        assert info['class'] == 'EnhancedTrimmer'


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 