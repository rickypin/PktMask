#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ProcessorStageAdapter 单元测试

测试 BaseProcessor 到 StageBase 的适配功能。
"""

import unittest
from unittest.mock import Mock, MagicMock
from pathlib import Path
import tempfile

from pktmask.core.pipeline.stages.processor_stage_adapter import ProcessorStageAdapter
from pktmask.core.pipeline.models import StageStats
from pktmask.core.processors.base_processor import BaseProcessor, ProcessorConfig, ProcessorResult


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


if __name__ == '__main__':
    unittest.main() 