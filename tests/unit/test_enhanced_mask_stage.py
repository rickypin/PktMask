#!/usr/bin/env python3
"""
增强版 MaskStage 单元测试

验证 MaskStage 的增强模式和基础模式功能，确保与 EnhancedTrimmer 功能对等。
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.pktmask.core.pipeline.stages.mask_payload.stage import MaskStage
from src.pktmask.core.pipeline.models import StageStats


class TestEnhancedMaskStage:
    """测试增强版 MaskStage 的功能"""

    def test_initialization_enhanced_mode_default(self):
        """测试默认初始化为增强模式"""
        stage = MaskStage()
        assert stage._use_enhanced_mode is True
        
    def test_initialization_explicit_enhanced_mode(self):
        """测试显式配置增强模式"""
        config = {"mode": "enhanced"}
        stage = MaskStage(config)
        assert stage._use_enhanced_mode is True
        
    def test_initialization_basic_mode(self):
        """测试配置基础模式"""
        config = {"mode": "basic"}
        stage = MaskStage(config)
        assert stage._use_enhanced_mode is False

    @patch('pktmask.core.trim.multi_stage_executor.MultiStageExecutor')
    @patch('pktmask.core.trim.stages.tshark_preprocessor.TSharkPreprocessor')
    @patch('pktmask.core.trim.stages.enhanced_pyshark_analyzer.EnhancedPySharkAnalyzer')
    @patch('pktmask.core.trim.stages.tcp_payload_masker_adapter.TcpPayloadMaskerAdapter')
    @patch('pktmask.config.defaults.get_tshark_paths')
    def test_enhanced_mode_initialization_success(self, mock_tshark_paths, mock_adapter, 
                                                mock_analyzer, mock_preprocessor, mock_executor):
        """测试增强模式成功初始化"""
        # Mock 配置
        mock_tshark_paths.return_value = ['/usr/bin/tshark']
        
        # Mock Stage 实例
        mock_tshark_stage = Mock()
        mock_tshark_stage.initialize.return_value = True
        mock_preprocessor.return_value = mock_tshark_stage
        
        mock_pyshark_stage = Mock()
        mock_pyshark_stage.initialize.return_value = True
        mock_analyzer.return_value = mock_pyshark_stage
        
        mock_adapter_stage = Mock()
        mock_adapter_stage.initialize.return_value = True
        mock_adapter.return_value = mock_adapter_stage
        
        # Mock 执行器
        mock_executor_instance = Mock()
        mock_executor.return_value = mock_executor_instance
        
        # 创建并初始化 Stage
        stage = MaskStage({"mode": "enhanced"})
        stage.initialize()
        
        # 验证初始化
        assert stage._use_enhanced_mode is True
        assert stage._executor is not None
        
        # 验证组件创建和注册
        mock_preprocessor.assert_called_once()
        mock_analyzer.assert_called_once()
        mock_adapter.assert_called_once()
        
        mock_executor_instance.register_stage.assert_any_call(mock_tshark_stage)
        mock_executor_instance.register_stage.assert_any_call(mock_pyshark_stage)
        mock_executor_instance.register_stage.assert_any_call(mock_adapter_stage)

    @patch('pktmask.core.trim.multi_stage_executor.MultiStageExecutor')
    def test_enhanced_mode_initialization_import_failure_fallback(self, mock_executor):
        """测试增强模式导入失败时降级到基础模式"""
        mock_executor.side_effect = ImportError("Module not found")
        
        stage = MaskStage({"mode": "enhanced"})
        stage.initialize()
        
        # 应该降级到基础模式
        assert stage._use_enhanced_mode is False

    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.create_masking_recipe_from_dict')
    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.BlindPacketMasker')
    def test_basic_mode_initialization_with_recipe(self, mock_masker, mock_recipe_creator):
        """测试基础模式使用配方初始化"""
        mock_recipe = Mock()
        mock_recipe_creator.return_value = mock_recipe
        mock_masker_instance = Mock()
        mock_masker.return_value = mock_masker_instance
        
        config = {
            "mode": "basic",
            "recipe_dict": {"some": "recipe"}
        }
        
        stage = MaskStage(config)
        stage.initialize()
        
        # 验证基础模式初始化
        assert stage._use_enhanced_mode is False
        mock_recipe_creator.assert_called_once_with({"some": "recipe"})
        mock_masker.assert_called_once_with(masking_recipe=mock_recipe)
        assert stage._masker is mock_masker_instance

    def test_stage_config_creation_tshark(self):
        """测试 TShark 阶段配置创建"""
        with patch('pktmask.config.defaults.get_tshark_paths', return_value=['/usr/bin/tshark']):
            stage = MaskStage()
            config = stage._create_stage_config("tshark", {"preserve_ratio": 0.5})
            
            # 验证 TShark 特定配置
            assert config['enable_tcp_reassembly'] is True
            assert config['enable_ip_defragmentation'] is True
            assert '/usr/bin/tshark' in config['tshark_executable_paths']
            assert config['preserve_ratio'] == 0.5

    def test_stage_config_creation_pyshark(self):
        """测试 PyShark 阶段配置创建"""
        stage = MaskStage()
        config = stage._create_stage_config("pyshark", {"tls_strategy_enabled": False})
        
        # 验证 PyShark 特定配置
        assert config['tls_strategy_enabled'] is False
        assert config['auto_protocol_detection'] is True

    def test_stage_config_creation_scapy(self):
        """测试 Scapy 阶段配置创建"""
        stage = MaskStage()
        config = stage._create_stage_config("scapy", {"enable_validation": False})
        
        # 验证 Scapy 特定配置
        assert config['preserve_timestamps'] is True
        assert config['recalculate_checksums'] is True
        assert config['enable_validation'] is False

    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.rdpcap')
    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.wrpcap')
    def test_process_file_enhanced_mode_success(self, mock_wrpcap, mock_rdpcap):
        """测试增强模式文件处理成功"""
        # Mock MultiStageExecutor
        mock_executor = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.stage_results = [
            Mock(packets_processed=100, packets_modified=50),
            Mock(packets_processed=100, packets_modified=50),
            Mock(packets_processed=100, packets_modified=50)
        ]
        mock_executor.execute_pipeline.return_value = mock_result
        
        stage = MaskStage({"mode": "enhanced"})
        stage._use_enhanced_mode = True
        stage._executor = mock_executor
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            result = stage.process_file(input_file.name, output_file.name)
            
            # 验证结果
            assert result is not None
            assert result.stage_name == "MaskStage"
            assert result.packets_processed == 100
            assert result.packets_modified == 50
            assert result.extra_metrics["enhanced_mode"] is True
            assert result.extra_metrics["pipeline_success"] is True
            
            # 验证执行器调用
            mock_executor.execute_pipeline.assert_called_once()

    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.rdpcap')
    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.wrpcap')
    def test_process_file_enhanced_mode_failure_fallback(self, mock_wrpcap, mock_rdpcap):
        """测试增强模式失败时降级处理"""
        # Mock 数据包
        mock_packets = [Mock(), Mock(), Mock()]
        mock_rdpcap.return_value = mock_packets
        
        # Mock 失败的执行器
        mock_executor = Mock()
        mock_executor.execute_pipeline.side_effect = Exception("执行失败")
        
        stage = MaskStage({"mode": "enhanced"})
        stage._use_enhanced_mode = True
        stage._executor = mock_executor
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            result = stage.process_file(input_file.name, output_file.name)
            
            # 验证降级结果
            assert result is not None
            assert result.stage_name == "MaskStage"
            assert result.packets_processed == 3
            assert result.packets_modified == 0
            assert result.extra_metrics["enhanced_mode"] is False
            assert result.extra_metrics["mode"] == "fallback"
            assert result.extra_metrics["graceful_degradation"] is True
            
            # 验证文件复制
            mock_wrpcap.assert_called_once_with(output_file.name, mock_packets)

    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.rdpcap')
    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.wrpcap')
    def test_process_file_basic_mode_with_masker(self, mock_wrpcap, mock_rdpcap):
        """测试基础模式有掩码器的文件处理"""
        # Mock 数据包
        mock_packets = [Mock(), Mock()]
        mock_rdpcap.return_value = mock_packets
        
        # Mock 掩码器
        mock_masker = Mock()
        mock_modified_packets = [Mock(), Mock()]
        mock_masker.mask_packets.return_value = mock_modified_packets
        mock_stats = Mock()
        mock_stats.processed_packets = 2
        mock_stats.modified_packets = 1
        mock_stats.to_dict.return_value = {"test": "stats"}
        mock_masker.get_statistics.return_value = mock_stats
        
        stage = MaskStage({"mode": "basic"})
        stage._use_enhanced_mode = False
        stage._masker = mock_masker
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            result = stage.process_file(input_file.name, output_file.name)
            
            # 验证结果
            assert result is not None
            assert result.packets_processed == 2
            assert result.packets_modified == 1
            assert result.extra_metrics["enhanced_mode"] is False
            assert result.extra_metrics["mode"] == "basic_masking"
            assert result.extra_metrics["test"] == "stats"
            
            # 验证掩码器调用
            mock_masker.mask_packets.assert_called_once_with(mock_packets)
            mock_wrpcap.assert_called_once_with(output_file.name, mock_modified_packets)

    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.rdpcap')
    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.wrpcap')
    def test_process_file_basic_mode_no_masker_bypass(self, mock_wrpcap, mock_rdpcap):
        """测试基础模式无掩码器时的透传模式"""
        # Mock 数据包
        mock_packets = [Mock(), Mock(), Mock()]
        mock_rdpcap.return_value = mock_packets
        
        stage = MaskStage({"mode": "basic"})
        stage._use_enhanced_mode = False
        stage._masker = None  # 无掩码器
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            result = stage.process_file(input_file.name, output_file.name)
            
            # 验证透传结果
            assert result is not None
            assert result.packets_processed == 3
            assert result.packets_modified == 0
            assert result.extra_metrics["enhanced_mode"] is False
            assert result.extra_metrics["mode"] == "bypass"
            assert result.extra_metrics["reason"] == "no_valid_masking_recipe"
            
            # 验证文件复制
            mock_wrpcap.assert_called_once_with(output_file.name, mock_packets)

    def test_mode_switching_during_runtime(self):
        """测试运行时模式切换"""
        # 初始为增强模式
        stage = MaskStage({"mode": "enhanced"})
        assert stage._use_enhanced_mode is True
        
        # 运行时切换到基础模式
        stage.initialize({"mode": "basic"})
        assert stage._use_enhanced_mode is False

    def test_configuration_inheritance(self):
        """测试配置继承机制"""
        base_config = {
            "mode": "enhanced",
            "preserve_ratio": 0.4,
            "tls_strategy_enabled": False
        }
        
        runtime_config = {
            "mode": "basic",  # 覆盖基础配置
            "chunk_size": 2000  # 新增配置
        }
        
        stage = MaskStage(base_config)
        stage.initialize(runtime_config)
        
        # 验证配置合并和覆盖
        assert stage._use_enhanced_mode is False  # 运行时配置优先
        
        # 验证阶段配置创建中的继承
        tshark_config = stage._create_stage_config("tshark", {**base_config, **runtime_config})
        assert tshark_config['preserve_ratio'] == 0.4  # 继承基础配置
        assert tshark_config['chunk_size'] == 2000     # 继承运行时配置


class TestMaskStageIntegration:
    """MaskStage 集成测试"""

    def test_compatibility_with_stage_base_interface(self):
        """测试与 StageBase 接口的兼容性"""
        stage = MaskStage()
        
        # 验证必要属性和方法存在
        assert hasattr(stage, 'name')
        assert hasattr(stage, 'initialize')
        assert hasattr(stage, 'process_file')
        assert stage.name == "MaskStage"

    def test_error_handling_in_initialization(self):
        """测试初始化过程中的错误处理"""
        # 测试配方解析错误
        stage = MaskStage({
            "mode": "basic",
            "recipe_dict": "invalid_recipe"  # 无效的配方格式
        })
        
        # 应该不抛出异常，而是优雅处理
        stage.initialize()
        assert stage._masker is None  # 配方解析失败，无掩码器

    @patch('src.pktmask.core.pipeline.stages.mask_payload.stage.Path')
    def test_file_path_handling(self, mock_path):
        """测试文件路径处理"""
        # Mock Path 对象
        mock_input_path = Mock()
        mock_output_path = Mock()
        mock_path.side_effect = [mock_input_path, mock_output_path]
        
        stage = MaskStage({"mode": "basic"})
        stage._masker = None  # 使用透传模式简化测试
        
        with patch('src.pktmask.core.pipeline.stages.mask_payload.stage.rdpcap') as mock_rdpcap, \
             patch('src.pktmask.core.pipeline.stages.mask_payload.stage.wrpcap') as mock_wrpcap:
            
            mock_rdpcap.return_value = []
            
            stage.process_file("input.pcap", "output.pcap")
            
            # 验证路径转换
            assert mock_path.call_count == 2
            mock_path.assert_any_call("input.pcap")
            mock_path.assert_any_call("output.pcap")


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 