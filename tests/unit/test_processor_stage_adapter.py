#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ProcessorStageAdapter 单元测试

测试 BaseProcessor 到 StageBase 的适配功能。
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile
import pytest
import logging

from pktmask.core.pipeline.stages.processor_stage_adapter import ProcessorStageAdapter
from pktmask.core.pipeline.models import StageStats
from pktmask.core.processors.base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from pktmask.core.pipeline.stages.mask_payload.stage import MaskStage
from pktmask.core.tcp_payload_masker.api.types import MaskingRecipe, MaskAfter


class MockProcessor(BaseProcessor):
    """用于测试的模拟处理器"""
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self.process_file_calls = []
        self.mock_result = ProcessorResult(success=True, stats={'packets_processed': 100, 'packets_modified': 50})
    
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        self.process_file_calls.append((input_path, output_path))
        return self.mock_result
    
    def get_display_name(self) -> str:
        return "Mock Processor"


class TestProcessorStageAdapter(unittest.TestCase):
    """ProcessorStageAdapter 测试类"""
    
    def setUp(self):
        """测试准备"""
        self.processor_config = ProcessorConfig(enabled=True, name="test_processor")
        self.mock_processor = MockProcessor(self.processor_config)
        self.adapter_config = {"test_param": "test_value"}
        
        # 创建临时文件
        self.temp_dir = Path(tempfile.mkdtemp())
        self.input_file = self.temp_dir / "input.pcap"
        self.output_file = self.temp_dir / "output.pcap"
        self.input_file.touch()  # 创建空文件
        
    def test_adapter_initialization(self):
        """测试适配器初始化"""
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        
        # 验证基本属性
        self.assertEqual(adapter.name, "Adapter_MockProcessor")
        self.assertEqual(adapter._processor, self.mock_processor)
        self.assertEqual(adapter._config, self.adapter_config)
        
    def test_adapter_initialize_method(self):
        """测试适配器初始化方法"""
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        
        # 初始化应该成功
        adapter.initialize()
        
        # 验证底层处理器和适配器都已初始化
        self.assertTrue(self.mock_processor.is_initialized)
        self.assertTrue(adapter._initialized)
        
    def test_adapter_initialize_with_runtime_config(self):
        """测试带运行时配置的初始化"""
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        runtime_config = {"runtime_param": "runtime_value"}
        
        adapter.initialize(runtime_config)
        
        # 验证配置合并
        expected_config = {**self.adapter_config, **runtime_config}
        self.assertEqual(adapter._config, expected_config)
        
    def test_successful_file_processing(self):
        """测试成功的文件处理"""
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        adapter.initialize()
        
        # 处理文件
        result = adapter.process_file(self.input_file, self.output_file)
        
        # 验证结果
        self.assertIsInstance(result, StageStats)
        self.assertEqual(result.stage_name, "Adapter_MockProcessor")
        self.assertEqual(result.packets_processed, 100)
        self.assertEqual(result.packets_modified, 50)
        self.assertEqual(result.duration_ms, 0.0)  # Mock 返回默认值
        
        # 验证底层处理器被调用
        self.assertEqual(len(self.mock_processor.process_file_calls), 1)
        call_args = self.mock_processor.process_file_calls[0]
        self.assertEqual(call_args[0], str(self.input_file))
        self.assertEqual(call_args[1], str(self.output_file))
        
    def test_failed_file_processing(self):
        """测试文件处理失败的情况"""
        # 设置处理器返回失败结果
        self.mock_processor.mock_result = ProcessorResult(
            success=False, 
            error="Test error message"
        )
        
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        adapter.initialize()
        
        # 处理文件应该抛出异常
        with self.assertRaises(RuntimeError) as context:
            adapter.process_file(self.input_file, self.output_file)
        
        # 验证异常信息
        self.assertIn("Test error message", str(context.exception))
        
    def test_processor_exception_handling(self):
        """测试处理器抛出异常的情况"""
        # 设置处理器抛出异常
        self.mock_processor.process_file = Mock(side_effect=Exception("Test exception"))
        
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        adapter.initialize()
        
        # 处理文件应该抛出异常
        with self.assertRaises(Exception) as context:
            adapter.process_file(self.input_file, self.output_file)
        
        # 验证异常信息
        self.assertIn("Test exception", str(context.exception))
        
    def test_get_required_tools_with_method(self):
        """测试获取必需工具（底层处理器有此方法）"""
        # 给底层处理器添加 get_required_tools 方法
        self.mock_processor.get_required_tools = Mock(return_value=['tshark', 'tcpdump'])
        
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        
        tools = adapter.get_required_tools()
        self.assertEqual(tools, ['tshark', 'tcpdump'])
        self.mock_processor.get_required_tools.assert_called_once()
        
    def test_get_required_tools_without_method(self):
        """测试获取必需工具（底层处理器无此方法）"""
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        
        tools = adapter.get_required_tools()
        self.assertEqual(tools, [])
        
    def test_stop_with_method(self):
        """测试停止功能（底层处理器有此方法）"""
        # 给底层处理器添加 stop 方法
        self.mock_processor.stop = Mock()
        
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        adapter.stop()
        
        self.mock_processor.stop.assert_called_once()
        
    def test_stop_without_method(self):
        """测试停止功能（底层处理器无此方法）"""
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        
        # 应该不抛出异常
        adapter.stop()
        
    def test_processor_initialization_failure(self):
        """测试底层处理器初始化失败"""
        # 设置处理器初始化失败
        self.mock_processor.initialize = Mock(return_value=False)
        
        adapter = ProcessorStageAdapter(self.mock_processor, self.adapter_config)
        
        # 初始化应该抛出异常
        with self.assertRaises(RuntimeError) as context:
            adapter.initialize()
        
        self.assertIn("初始化失败", str(context.exception))
        
    def tearDown(self):
        """清理测试文件"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestMaskStageProcessorAdapterIntegration(unittest.TestCase):
    """MaskStage 与 ProcessorStageAdapter 集成测试"""
    
    def setUp(self):
        """测试准备"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.input_file = self.temp_dir / "input.pcap"
        self.output_file = self.temp_dir / "output.pcap"
        self.input_file.touch()  # 创建空文件
        
    def tearDown(self):
        """清理测试文件"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_no_recipe_processor_adapter_success(self):
        """测试用例1: 不提供 recipe → processor_adapter 成功 → 正常处理（mock）"""
        # 配置：不提供 recipe，使用默认 processor_adapter 模式
        config = {"mode": "processor_adapter"}
        
        with patch('pktmask.core.processors.tshark_enhanced_mask_processor.TSharkEnhancedMaskProcessor') as mock_processor_class:
            with patch('pktmask.core.pipeline.stages.processor_stage_adapter.ProcessorStageAdapter') as mock_adapter_class:
                # 设置 mock 返回值
                mock_processor = Mock()
                mock_processor.initialize.return_value = True
                mock_processor.is_initialized = True
                mock_processor_class.return_value = mock_processor
                
                mock_adapter = Mock()
                mock_adapter.process_file.return_value = StageStats(
                    stage_name="MaskStage",
                    packets_processed=100,
                    packets_modified=50,
                    duration_ms=1200.5,
                    extra_metrics={"processor_adapter_mode": True}
                )
                mock_adapter_class.return_value = mock_adapter
                
                # 创建 MaskStage
                stage = MaskStage(config)
                stage.initialize()
                
                # 验证初始化使用了 processor_adapter 模式
                self.assertTrue(stage._use_processor_adapter_mode)
                self.assertIsNotNone(stage._processor_adapter)
                
                # 执行处理
                result = stage.process_file(self.input_file, self.output_file)
                
                # 验证结果
                self.assertIsInstance(result, StageStats)
                self.assertEqual(result.stage_name, "MaskStage")
                self.assertEqual(result.packets_processed, 100)
                self.assertEqual(result.packets_modified, 50)
                self.assertTrue(result.extra_metrics.get("processor_adapter_mode"))
                
                # 验证调用链
                mock_processor_class.assert_called_once()
                mock_adapter_class.assert_called_once()
                mock_adapter.process_file.assert_called_once_with(self.input_file, self.output_file)
    
    def test_processor_adapter_exception_fallback(self):
        """测试用例2: processor_adapter 抛异常 → 降级，验证透传且 log 捕获"""
        config = {"mode": "processor_adapter"}
        
        with patch('pktmask.core.processors.tshark_enhanced_mask_processor.TSharkEnhancedMaskProcessor') as mock_processor_class:
            with patch('pktmask.core.pipeline.stages.processor_stage_adapter.ProcessorStageAdapter') as mock_adapter_class:
                with patch('pktmask.core.pipeline.stages.mask_payload.stage.rdpcap') as mock_rdpcap:
                    with patch('pktmask.core.pipeline.stages.mask_payload.stage.wrpcap') as mock_wrpcap:
                        # 设置 processor_adapter 抛异常
                        mock_processor = Mock()
                        mock_processor.initialize.return_value = True
                        mock_processor.is_initialized = True
                        mock_processor_class.return_value = mock_processor
                        
                        mock_adapter = Mock()
                        mock_adapter.process_file.side_effect = RuntimeError("TShark processor failed")
                        mock_adapter_class.return_value = mock_adapter
                        
                        # 设置透传处理的 mock
                        mock_packets = [Mock(), Mock(), Mock()]
                        mock_rdpcap.return_value = mock_packets
                        
                        # 创建 MaskStage 并处理
                        stage = MaskStage(config)
                        stage.initialize()
                        
                        # 直接测试 process_file 方法的降级处理
                        # MaskStage 已经内置了降级机制，不会抛出异常
                        result = stage.process_file(self.input_file, self.output_file)
                        
                        # 验证降级结果
                        self.assertIsInstance(result, StageStats)
                        self.assertEqual(result.stage_name, "MaskStage")
                        self.assertEqual(result.packets_processed, len(mock_packets))
                        self.assertEqual(result.packets_modified, 0)  # 透传模式不修改包
                        
                        # 验证降级指标
                        extra_metrics = result.extra_metrics
                        self.assertFalse(extra_metrics.get("processor_adapter_mode"))
                        self.assertEqual(extra_metrics.get("mode"), "fallback")
                        self.assertEqual(extra_metrics.get("original_mode"), "processor_adapter")
                        self.assertIn("TShark processor failed", extra_metrics.get("fallback_reason", ""))
                        self.assertTrue(extra_metrics.get("graceful_degradation"))
                        
                        # 验证透传调用
                        mock_rdpcap.assert_called_once_with(str(self.input_file))
                        mock_wrpcap.assert_called_once()
    
    def test_basic_mode_fallback_passthrough(self):
        """测试用例3: basic 模式现已简化为透传模式（BlindPacketMasker 已移除）"""
        # 创建 MaskingRecipe 实例（会被忽略，因为 basic 模式现为透传）
        recipe = MaskingRecipe(
            total_packets=10,
            packet_instructions={0: [MaskAfter(keep_bytes=5)]},
            metadata={"test": "basic_mode"}
        )
        
        config = {
            "mode": "basic",
            "recipe": recipe
        }
        
        # basic 模式现在是透传模式，使用 shutil.copyfile 进行文件复制
        with patch('pktmask.core.pipeline.stages.mask_payload.stage.rdpcap') as mock_rdpcap:
            with patch('pktmask.core.pipeline.stages.mask_payload.stage.shutil.copyfile') as mock_copyfile:
                # 设置 rdpcap mock - 用于统计包数
                mock_packets = [Mock() for _ in range(10)]
                mock_rdpcap.return_value = mock_packets
                
                # 创建 MaskStage
                stage = MaskStage(config)
                stage.initialize()
                
                # 验证初始化使用了 basic 模式（透传）
                self.assertFalse(stage._use_processor_adapter_mode)
                self.assertIsNone(stage._masker)  # basic 模式不再使用 masker
                
                # 执行处理
                result = stage.process_file(self.input_file, self.output_file)
                
                # 验证结果 - 透传模式的特征
                self.assertIsInstance(result, StageStats)
                self.assertEqual(result.stage_name, "MaskStage")
                self.assertEqual(result.packets_processed, 10)  # 读取的包数
                self.assertEqual(result.packets_modified, 0)   # 透传模式不修改包
                
                # 验证透传模式的指标
                extra_metrics = result.extra_metrics
                self.assertFalse(extra_metrics.get("processor_adapter_mode"))
                self.assertEqual(extra_metrics.get("mode"), "basic_passthrough")
                self.assertEqual(extra_metrics.get("reason"), "blind_packet_masker_removed")
                
                # 验证透传调用链
                mock_copyfile.assert_called_once_with(str(self.input_file), str(self.output_file))
                mock_rdpcap.assert_called_once_with(str(self.input_file))  # 用于统计包数
    
    def test_processor_adapter_initialization_exception_fallback_with_caplog(self):
        """测试用例2补充: 使用 caplog 检查降级日志"""
        config = {"mode": "processor_adapter"}
        
        with patch('pktmask.core.processors.tshark_enhanced_mask_processor.TSharkEnhancedMaskProcessor', side_effect=ImportError("TShark不可用")):
            # 直接使用 caplog fixture (需要在 pytest 环境中)
            import logging
            
            # 创建日志捕获器
            log_capture_handler = logging.Handler()
            captured_logs = []
            
            class LogCapture(logging.Handler):
                def emit(self, record):
                    captured_logs.append(record)
            
            log_handler = LogCapture()
            # 使用 MaskStage 的日志记录器名称
            logger = logging.getLogger('MaskStage')
            logger.addHandler(log_handler)
            logger.setLevel(logging.ERROR)
            
            try:
                stage = MaskStage(config)
                stage.initialize()
                
                # 验证降级到 basic 模式
                self.assertFalse(stage._use_processor_adapter_mode)
                
                # 验证日志中包含降级信息
                log_messages = [record.getMessage() for record in captured_logs]
                degradation_logged = any("降级为Basic Mode" in msg for msg in log_messages)
                self.assertTrue(degradation_logged, f"未找到降级日志，实际日志: {log_messages}")
            finally:
                logger.removeHandler(log_handler)


if __name__ == '__main__':
    unittest.main()
