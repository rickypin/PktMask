#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
阶段1集成测试：PipelineExecutor + ProcessorStageAdapter + EnhancedTrimmer

验证通过适配器实现的调用路径统一功能。
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock

from pktmask.core.pipeline.executor import PipelineExecutor
from pktmask.core.pipeline.models import ProcessResult
from pktmask.core.processors.enhanced_trimmer import EnhancedTrimmer
from pktmask.core.processors.base_processor import ProcessorConfig


class TestStage1Integration(unittest.TestCase):
    """阶段1集成测试类"""
    
    def setUp(self):
        """测试准备"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.input_file = self.temp_dir / "test_input.pcap"
        self.output_file = self.temp_dir / "test_output.pcap"
        
        # 创建一个简单的测试文件
        with open(self.input_file, 'wb') as f:
            f.write(b'\x00' * 100)  # 简单的测试数据
            
    def tearDown(self):
        """清理测试文件"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_pipeline_executor_basic_construction(self):
        """测试 PipelineExecutor 基本构造（无mask阶段）"""
        config = {
            "dedup": {"enabled": False},
            "anon": {"enabled": False},
            "mask": {"enabled": False}
        }
        
        executor = PipelineExecutor(config)
        
        # 验证管道构造成功
        self.assertIsInstance(executor, PipelineExecutor)
        self.assertEqual(len(executor.stages), 0)  # 没有启用的阶段
    
    def test_pipeline_executor_with_mask_config(self):
        """测试 PipelineExecutor 包含 mask 阶段的构造"""
        config = {
            "dedup": {"enabled": False},
            "anon": {"enabled": False},
            "mask": {
                "enabled": True,
                "recipe_path": "config/samples/simple_mask_recipe.json"
            }
        }
        
        # 由于 EnhancedTrimmer 需要完整的依赖，我们 mock 它
        with patch('pktmask.core.processors.enhanced_trimmer.EnhancedTrimmer') as mock_trimmer_class:
            mock_trimmer = Mock()
            mock_trimmer.is_initialized = False
            mock_trimmer.initialize.return_value = True
            mock_trimmer.__class__.__name__ = 'EnhancedTrimmer'
            mock_trimmer_class.return_value = mock_trimmer
            
            executor = PipelineExecutor(config)
            
            # 验证管道构造成功并包含 mask 阶段
            self.assertIsInstance(executor, PipelineExecutor)
            self.assertEqual(len(executor.stages), 1)
            
            # 验证阶段是适配器类型
            stage = executor.stages[0]
            self.assertTrue(stage.name.startswith("Adapter_EnhancedTrimmer"))
            
            # 验证 EnhancedTrimmer 被正确创建和初始化
            mock_trimmer_class.assert_called_once()
            mock_trimmer.initialize.assert_called_once()
    
    def test_adapter_in_pipeline_context(self):
        """测试适配器在管道上下文中的表现"""
        config = {
            "mask": {
                "enabled": True,
                "recipe_path": "config/samples/simple_mask_recipe.json"
            }
        }
        
        # Mock EnhancedTrimmer 及其 process_file 方法
        with patch('pktmask.core.processors.enhanced_trimmer.EnhancedTrimmer') as mock_trimmer_class:
            mock_trimmer = Mock()
            mock_trimmer.is_initialized = False
            mock_trimmer.initialize.return_value = True
            mock_trimmer.__class__.__name__ = 'EnhancedTrimmer'
            
            # Mock process_file 返回成功结果
            from pktmask.core.processors.base_processor import ProcessorResult
            mock_result = ProcessorResult(
                success=True,
                stats={
                    'packets_processed': 50,
                    'packets_modified': 25,
                    'duration_ms': 1500.0
                }
            )
            mock_trimmer.process_file.return_value = mock_result
            mock_trimmer_class.return_value = mock_trimmer
            
            executor = PipelineExecutor(config)
            
            # 执行管道
            result = executor.run(self.input_file, self.output_file)
            
            # 验证执行结果
            self.assertIsInstance(result, ProcessResult)
            self.assertTrue(result.success)
            self.assertEqual(len(result.stage_stats), 1)
            
            # 验证阶段统计信息
            stage_stats = result.stage_stats[0]
            self.assertEqual(stage_stats.packets_processed, 50)
            self.assertEqual(stage_stats.packets_modified, 25)
            self.assertEqual(stage_stats.duration_ms, 1500.0)
            
            # 验证底层处理器被调用
            mock_trimmer.process_file.assert_called_once_with(
                str(self.input_file), 
                str(self.output_file)
            )
    
    def test_adapter_error_handling(self):
        """测试适配器的错误处理"""
        config = {
            "mask": {
                "enabled": True,
                "recipe_path": "config/samples/simple_mask_recipe.json"
            }
        }
        
        with patch('pktmask.core.processors.enhanced_trimmer.EnhancedTrimmer') as mock_trimmer_class:
            mock_trimmer = Mock()
            mock_trimmer.is_initialized = False
            mock_trimmer.initialize.return_value = True
            mock_trimmer.__class__.__name__ = 'EnhancedTrimmer'
            
            # Mock process_file 返回失败结果
            from pktmask.core.processors.base_processor import ProcessorResult
            mock_result = ProcessorResult(
                success=False,
                error="Test processing error"
            )
            mock_trimmer.process_file.return_value = mock_result
            mock_trimmer_class.return_value = mock_trimmer
            
            executor = PipelineExecutor(config)
            
            # 执行管道
            result = executor.run(self.input_file, self.output_file)
            
            # 验证执行失败
            self.assertIsInstance(result, ProcessResult)
            self.assertFalse(result.success)
            self.assertEqual(len(result.errors), 1)
            self.assertIn("失败", result.errors[0])
    
    def test_multiple_stages_with_adapter(self):
        """测试包含多个阶段且其中包含适配器的管道"""
        config = {
            "dedup": {"enabled": True},
            "anon": {"enabled": True}, 
            "mask": {
                "enabled": True,
                "recipe_path": "config/samples/simple_mask_recipe.json"
            }
        }
        
        # Mock 所有处理器
        with patch('pktmask.core.processors.enhanced_trimmer.EnhancedTrimmer') as mock_trimmer_class, \
             patch('pktmask.core.pipeline.stages.dedup.DedupStage') as mock_dedup_class, \
             patch('pktmask.core.pipeline.stages.anon_ip.AnonStage') as mock_anon_class:
            
            # Mock EnhancedTrimmer
            mock_trimmer = Mock()
            mock_trimmer.is_initialized = False
            mock_trimmer.initialize.return_value = True
            mock_trimmer.__class__.__name__ = 'EnhancedTrimmer'
            mock_trimmer_class.return_value = mock_trimmer
            
            # Mock 其他阶段
            mock_dedup = Mock()
            mock_dedup.initialize = Mock()
            mock_dedup.name = "DedupStage"
            mock_dedup_class.return_value = mock_dedup
            
            mock_anon = Mock()
            mock_anon.initialize = Mock()
            mock_anon.name = "AnonStage" 
            mock_anon_class.return_value = mock_anon
            
            executor = PipelineExecutor(config)
            
            # 验证管道构造成功并包含3个阶段
            self.assertIsInstance(executor, PipelineExecutor)
            self.assertEqual(len(executor.stages), 3)
            
            # 验证阶段顺序
            stage_names = [stage.name for stage in executor.stages]
            self.assertEqual(stage_names[0], "DedupStage")
            self.assertEqual(stage_names[1], "AnonStage")
            self.assertTrue(stage_names[2].startswith("Adapter_EnhancedTrimmer"))
    
    def test_config_parameter_passing(self):
        """测试配置参数传递到适配器"""
        config = {
            "mask": {
                "enabled": True,
                "recipe_path": "config/samples/simple_mask_recipe.json",
                "custom_param": "custom_value",
                "preserve_ratio": 0.5
            }
        }
        
        with patch('pktmask.core.processors.enhanced_trimmer.EnhancedTrimmer') as mock_trimmer_class:
            mock_trimmer = Mock()
            mock_trimmer.is_initialized = False
            mock_trimmer.initialize.return_value = True
            mock_trimmer.__class__.__name__ = 'EnhancedTrimmer'
            mock_trimmer_class.return_value = mock_trimmer
            
            executor = PipelineExecutor(config)
            
            # 验证管道构造成功
            self.assertEqual(len(executor.stages), 1)
            
            # 验证适配器获得了正确的配置
            adapter = executor.stages[0]
            self.assertIn("custom_param", adapter._config)
            self.assertEqual(adapter._config["custom_param"], "custom_value")
            self.assertEqual(adapter._config["preserve_ratio"], 0.5)


if __name__ == '__main__':
    unittest.main() 