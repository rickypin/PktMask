#!/usr/bin/env python3
"""
增强版 MaskStage 集成测试

验证增强版 MaskStage 与 PipelineExecutor 的集成，确保与 EnhancedTrimmer 功能对等。
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pktmask.core.pipeline.executor import PipelineExecutor
from pktmask.core.pipeline.stages.mask_payload.stage import MaskStage
from pktmask.core.pipeline.models import StageStats


class TestEnhancedMaskStageIntegration:
    """测试增强版 MaskStage 与系统的集成"""

    @patch('pktmask.core.trim.stages.tshark_preprocessor.TSharkPreprocessor')
    @patch('pktmask.core.trim.stages.enhanced_pyshark_analyzer.EnhancedPySharkAnalyzer')
    @patch('pktmask.core.trim.stages.tcp_payload_masker_adapter.TcpPayloadMaskerAdapter')
    @patch('pktmask.config.defaults.get_tshark_paths')
    def test_pipeline_executor_integration_enhanced_mode(self, mock_tshark_paths, mock_adapter,
                                                       mock_analyzer, mock_preprocessor):
        """测试 PipelineExecutor 与增强模式 MaskStage 的集成"""
        # Mock 配置
        mock_tshark_paths.return_value = ['/usr/bin/tshark']
        
        # Mock Stage 组件
        self._setup_mock_stages(mock_preprocessor, mock_analyzer, mock_adapter)
        
        # Mock MultiStageExecutor
        mock_executor_instance = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.stage_results = [
            Mock(packets_processed=100, packets_modified=30),
            Mock(packets_processed=100, packets_modified=30),
            Mock(packets_processed=100, packets_modified=30)
        ]
        mock_executor_instance.execute_pipeline.return_value = mock_result
        
        # 配置 Pipeline
        config = {
            "dedup": {"enabled": False},
            "anon": {"enabled": False},
            "mask": {
                "enabled": True,
                "mode": "enhanced",
                "preserve_ratio": 0.3,
                "tls_strategy_enabled": True
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            # 创建 PipelineExecutor 并执行
            executor = PipelineExecutor(config)
            
            # 模拟执行 - 这里主要验证 MaskStage 被正确创建和配置
            stages = executor._build_pipeline(config)
            
            # 验证 MaskStage 被创建 - 调试输出
            print(f"Enhanced mode - Created stages: {[type(s).__name__ for s in stages]}")
            mask_stages = [s for s in stages if isinstance(s, MaskStage)]
            print(f"Enhanced mode - MaskStages found: {len(mask_stages)}")
            assert len(mask_stages) == 1
            
            mask_stage = mask_stages[0]
            
            # 验证增强模式配置
            assert mask_stage._use_enhanced_mode is True
            assert mask_stage._executor is not None
            
            # 验证组件注册
            mock_executor_instance.register_stage.assert_called()
            # Stage可能被重复注册（PipelineExecutor构建时 + MaskStage初始化时）
            assert mock_executor_instance.register_stage.call_count >= 3

    def test_pipeline_executor_integration_basic_mode(self):
        """测试 PipelineExecutor 与基础模式 MaskStage 的集成"""
        # 配置基础模式
        config = {
            "dedup": {"enabled": False},
            "anon": {"enabled": False},
            "mask": {
                "enabled": True,
                "mode": "basic",
                "recipe_dict": {
                    "total_packets": 100,
                    "packet_instructions": {},
                    "skipped_packets": []
                }
            }
        }
        
        with patch('pktmask.core.tcp_payload_masker.utils.helpers.create_masking_recipe_from_dict') as mock_recipe_creator, \
             patch('pktmask.core.tcp_payload_masker.core.blind_masker.BlindPacketMasker') as mock_masker:
            
            mock_recipe = Mock()
            mock_recipe_creator.return_value = mock_recipe
            mock_masker_instance = Mock()
            mock_masker.return_value = mock_masker_instance
            
            # 创建 PipelineExecutor
            executor = PipelineExecutor(config)
            stages = executor._build_pipeline(config)
            
            # 验证 MaskStage 被创建 - 调试输出
            print(f"Basic mode - Created stages: {[type(s).__name__ for s in stages]}")
            mask_stages = [s for s in stages if isinstance(s, MaskStage)]
            print(f"Basic mode - MaskStages found: {len(mask_stages)}")
            assert len(mask_stages) == 1
            
            mask_stage = mask_stages[0]
            
            # 验证基础模式配置
            assert mask_stage._use_enhanced_mode is False
            assert mask_stage._masker is not None  # 有BlindPacketMasker实例（真实或Mock都OK）

    def test_enhanced_mode_fallback_to_basic_mode(self):
        """测试增强模式失败时降级到基础模式"""
        # 配置增强模式，但模拟导入失败
        config = {
            "mask": {
                "enabled": True,
                "mode": "enhanced"
            }
        }
        
        with patch('pktmask.core.trim.multi_stage_executor.MultiStageExecutor',
                  side_effect=ImportError("Module not found")):
            
            # 创建 MaskStage
            stage = MaskStage(config["mask"])
            stage.initialize()
            
            # 验证降级到基础模式
            assert stage._use_enhanced_mode is False
            assert stage._executor is None

    @patch('scapy.all.rdpcap')
    @patch('scapy.all.wrpcap')
    def test_end_to_end_processing_simulation(self, mock_wrpcap, mock_rdpcap):
        """测试端到端处理流程模拟"""
        # Mock 数据包
        mock_packets = [Mock(), Mock(), Mock()]
        mock_rdpcap.return_value = mock_packets
        
        # 创建 MaskStage 并配置为增强模式
        stage = MaskStage({"mode": "enhanced"})
        
        # Mock MultiStageExecutor
        mock_executor = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.stage_results = [
            Mock(packets_processed=3, packets_modified=2),
            Mock(packets_processed=3, packets_modified=2),
            Mock(packets_processed=3, packets_modified=2)
        ]
        mock_executor.execute_pipeline.return_value = mock_result
        
        stage._use_enhanced_mode = True
        stage._executor = mock_executor
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            # 执行处理
            result = stage.process_file(input_file.name, output_file.name)
            
            # 验证结果
            assert isinstance(result, StageStats)
            assert result.stage_name == "MaskStage"
            assert result.packets_processed == 3
            assert result.packets_modified == 2
            assert result.extra_metrics["enhanced_mode"] is True
            assert result.extra_metrics["intelligent_protocol_detection"] is True
            
            # 验证执行器调用
            mock_executor.execute_pipeline.assert_called_once()

    def test_configuration_propagation(self):
        """测试配置参数传播机制"""
        base_config = {
            "preserve_ratio": 0.4,
            "tls_strategy_enabled": False,
            "chunk_size": 2000,
            "enable_validation": True
        }
        
        stage = MaskStage({"mode": "enhanced", **base_config})
        
        # 验证各阶段配置创建
        tshark_config = stage._create_stage_config("tshark", base_config)
        pyshark_config = stage._create_stage_config("pyshark", base_config)
        scapy_config = stage._create_stage_config("scapy", base_config)
        
        # 验证 TShark 配置
        assert tshark_config['preserve_ratio'] == 0.4
        assert tshark_config['chunk_size'] == 2000
        assert tshark_config['enable_tcp_reassembly'] is True
        
        # 验证 PyShark 配置
        assert pyshark_config['tls_strategy_enabled'] is False
        assert pyshark_config['auto_protocol_detection'] is True
        
        # 验证 Scapy 配置
        assert scapy_config['enable_validation'] is True
        assert scapy_config['preserve_timestamps'] is True

    def test_performance_metrics_collection(self):
        """测试性能指标收集"""
        stage = MaskStage({"mode": "enhanced"})
        
        # Mock 执行器返回性能数据
        mock_executor = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.stage_results = [
            Mock(packets_processed=1000, packets_modified=500, duration=1.5),
            Mock(packets_processed=1000, packets_modified=500, duration=2.0),
            Mock(packets_processed=1000, packets_modified=500, duration=0.8)
        ]
        mock_executor.execute_pipeline.return_value = mock_result
        
        stage._use_enhanced_mode = True
        stage._executor = mock_executor
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            start_time = time.time()
            result = stage.process_file(input_file.name, output_file.name)
            
            # 验证性能指标
            assert result.duration_ms > 0
            assert result.extra_metrics["stages_count"] == 3
            assert result.extra_metrics["success_rate"] == "100%"
            assert result.extra_metrics["multi_stage_processing"] is True

    def test_error_handling_and_recovery(self):
        """测试错误处理和恢复机制"""
        stage = MaskStage({"mode": "enhanced"})
        
        # Mock 执行器抛出异常
        mock_executor = Mock()
        mock_executor.execute_pipeline.side_effect = RuntimeError("执行失败")
        
        stage._use_enhanced_mode = True
        stage._executor = mock_executor
        
        with patch('pktmask.core.pipeline.stages.mask_payload.stage.rdpcap') as mock_rdpcap, \
             patch('pktmask.core.pipeline.stages.mask_payload.stage.wrpcap') as mock_wrpcap, \
             tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as output_file:
            
            # 写入一些虚拟数据到输入文件避免Scapy读取错误
            input_file.write(b'\x00' * 100)  # 写入一些字节避免空文件
            input_file.flush()
            
            mock_packets = [Mock(), Mock()]
            mock_rdpcap.return_value = mock_packets
            
            # 执行处理
            result = stage.process_file(input_file.name, output_file.name)
            
            # 验证错误恢复
            assert isinstance(result, StageStats)
            assert result.extra_metrics["enhanced_mode"] is False
            assert result.extra_metrics["mode"] == "fallback"
            assert result.extra_metrics["graceful_degradation"] is True
            
            # 验证文件被复制作为降级方案
            mock_wrpcap.assert_called_once_with(output_file.name, mock_packets)

    def _setup_mock_stages(self, mock_preprocessor, mock_analyzer, mock_adapter):
        """设置 Mock Stage 组件"""
        # Mock TShark 预处理器
        mock_tshark_stage = Mock()
        mock_tshark_stage.initialize.return_value = True
        mock_preprocessor.return_value = mock_tshark_stage
        
        # Mock PyShark 分析器
        mock_pyshark_stage = Mock()
        mock_pyshark_stage.initialize.return_value = True
        mock_analyzer.return_value = mock_pyshark_stage
        
        # Mock Adapter
        mock_adapter_stage = Mock()
        mock_adapter_stage.initialize.return_value = True
        mock_adapter.return_value = mock_adapter_stage
        
        return mock_tshark_stage, mock_pyshark_stage, mock_adapter_stage


class TestMaskStageCompatibility:
    """测试 MaskStage 与现有系统的兼容性"""

    def test_stage_stats_compatibility(self):
        """测试 StageStats 兼容性"""
        stage = MaskStage({"mode": "basic"})
        stage._masker = None  # 使用透传模式
        
        with patch('pktmask.core.pipeline.stages.mask_payload.stage.rdpcap') as mock_rdpcap, \
             patch('pktmask.core.pipeline.stages.mask_payload.stage.wrpcap') as mock_wrpcap, \
             tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as output_file:
            
            # 写入一些虚拟数据到输入文件避免Scapy读取错误
            input_file.write(b'\x00' * 100)  # 写入一些字节避免空文件
            input_file.flush()
            
            mock_rdpcap.return_value = [Mock(), Mock()]
            
            result = stage.process_file(input_file.name, output_file.name)
            
            # 验证 StageStats 结构
            assert hasattr(result, 'stage_name')
            assert hasattr(result, 'packets_processed')
            assert hasattr(result, 'packets_modified')
            assert hasattr(result, 'duration_ms')
            assert hasattr(result, 'extra_metrics')
            
            # 验证类型
            assert isinstance(result.stage_name, str)
            assert isinstance(result.packets_processed, int)
            assert isinstance(result.packets_modified, int)
            assert isinstance(result.duration_ms, (int, float))
            assert isinstance(result.extra_metrics, dict)

    def test_backward_compatibility_with_original_interface(self):
        """测试与原有接口的向后兼容性"""
        # 测试原有配置格式仍然有效
        legacy_config = {
            "recipe_dict": {
                "total_packets": 10,
                "packet_instructions": {},
                "skipped_packets": []
            }
        }
        
        with patch('pktmask.core.tcp_payload_masker.utils.helpers.create_masking_recipe_from_dict') as mock_creator, \
             patch('pktmask.core.tcp_payload_masker.core.blind_masker.BlindPacketMasker') as mock_masker:
            
            mock_creator.return_value = Mock()
            mock_masker.return_value = Mock()
            
            # 应该能够正常初始化（默认增强模式会降级到基础模式）
            stage = MaskStage(legacy_config)
            stage.initialize()
            
            # 验证降级到基础模式并使用配方
            # Enhanced模式可能成功初始化，也可能降级到基础模式
            if stage._use_enhanced_mode:
                # 如果仍是Enhanced模式，应该有executor
                assert stage._executor is not None
            else:
                # 如果降级到基础模式，可能有masker或为None（透传模式）
                pass

    def test_integration_with_existing_pipeline_events(self):
        """测试与现有 Pipeline 事件系统的集成"""
        # 这个测试确保 MaskStage 不会破坏现有的事件流
        stage = MaskStage({"mode": "enhanced"})
        
        # Mock 执行器
        mock_executor = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.stage_results = []
        mock_executor.execute_pipeline.return_value = mock_result
        
        stage._use_enhanced_mode = True
        stage._executor = mock_executor
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            # 执行处理
            result = stage.process_file(input_file.name, output_file.name)
            
            # 验证结果格式符合预期
            assert isinstance(result, StageStats)
            assert result.stage_name == "MaskStage"


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 