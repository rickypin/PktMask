#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 6 - GUI 调用迁移测试

验证GUI内部成功迁移到新的PipelineExecutor，同时保持外观/交互零变化。
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Mock PyQt6 before importing GUI components
import sys
sys.modules['PyQt6'] = Mock()
sys.modules['PyQt6.QtCore'] = Mock()
sys.modules['PyQt6.QtWidgets'] = Mock()
sys.modules['PyQt6.QtGui'] = Mock()

# Mock QThread and signals
mock_qthread = Mock()
mock_qthread.pyqtSignal = Mock(return_value=Mock())
sys.modules['PyQt6.QtCore'].QThread = mock_qthread
sys.modules['PyQt6.QtCore'].pyqtSignal = mock_qthread.pyqtSignal

class TestPhase6GUIMigration(unittest.TestCase):
    """测试Phase 6 GUI迁移到新的PipelineExecutor"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_base_dir = os.path.join(self.temp_dir, "input")
        self.test_output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.test_base_dir)
        os.makedirs(self.test_output_dir)
        
        # 创建测试PCAP文件
        self.test_pcap = os.path.join(self.test_base_dir, "test.pcap")
        with open(self.test_pcap, 'w') as f:
            f.write("fake pcap content")
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('pktmask.gui.managers.pipeline_manager.PipelineExecutor')
    def test_build_pipeline_config(self, mock_executor_class):
        """测试_build_pipeline_config方法"""
        from pktmask.gui.managers.pipeline_manager import PipelineManager
        
        # Mock主窗口和复选框
        mock_main_window = Mock()
        mock_main_window.mask_ip_cb.isChecked.return_value = True
        mock_main_window.dedup_packet_cb.isChecked.return_value = True
        mock_main_window.trim_packet_cb.isChecked.return_value = False
        
        # 创建PipelineManager
        manager = PipelineManager(mock_main_window)
        
        # 测试配置构建
        config = manager._build_pipeline_config()
        
        # 验证配置正确性
        self.assertIn("anon", config)
        self.assertIn("dedup", config)
        self.assertNotIn("mask", config)
        
        self.assertTrue(config["anon"]["enabled"])
        self.assertTrue(config["dedup"]["enabled"])
    
    @patch('pktmask.gui.managers.pipeline_manager.PipelineExecutor')
    def test_build_pipeline_config_with_mask(self, mock_executor_class):
        """测试包含mask的配置构建"""
        from pktmask.gui.managers.pipeline_manager import PipelineManager
        
        # Mock主窗口和复选框
        mock_main_window = Mock()
        mock_main_window.mask_ip_cb.isChecked.return_value = False
        mock_main_window.dedup_packet_cb.isChecked.return_value = False
        mock_main_window.trim_packet_cb.isChecked.return_value = True
        
        # 创建PipelineManager
        manager = PipelineManager(mock_main_window)
        
        # 测试配置构建
        config = manager._build_pipeline_config()
        
        # 验证配置正确性
        self.assertNotIn("anon", config)
        self.assertNotIn("dedup", config)
        self.assertIn("mask", config)
        
        self.assertTrue(config["mask"]["enabled"])
        self.assertIn("recipe_path", config["mask"])
    
    def test_new_pipeline_thread_creation(self):
        """测试NewPipelineThread的创建和基本功能"""
        from pktmask.gui.main_window import NewPipelineThread
        
        # Mock executor
        mock_executor = Mock()
        mock_executor.run.return_value = Mock(stage_stats=[])
        
        # 创建线程
        thread = NewPipelineThread(mock_executor, self.test_base_dir, self.test_output_dir)
        
        # 验证初始化
        self.assertEqual(thread._base_dir, self.test_base_dir)
        self.assertEqual(thread._output_dir, self.test_output_dir)
        self.assertTrue(thread.is_running)
    
    @patch('os.scandir')
    def test_directory_processing_logic(self, mock_scandir):
        """测试目录处理逻辑"""
        from pktmask.gui.main_window import NewPipelineThread
        
        # Mock scandir返回PCAP文件
        mock_file = Mock()
        mock_file.name = "test.pcap"
        mock_file.path = self.test_pcap
        mock_scandir.return_value = [mock_file]
        
        # Mock executor
        mock_result = Mock()
        mock_result.stage_stats = []
        mock_executor = Mock()
        mock_executor.run.return_value = mock_result
        
        # 创建线程并运行
        thread = NewPipelineThread(mock_executor, self.test_base_dir, self.test_output_dir)
        
        # Mock信号发射
        thread.progress_signal = Mock()
        
        # 运行目录处理
        thread._run_directory_processing()
        
        # 验证executor被调用
        mock_executor.run.assert_called_once()
        
        # 验证发送了正确的事件
        call_args_list = thread.progress_signal.emit.call_args_list
        event_types = [call[0][0] for call in call_args_list]
        
        # 检查基本事件序列
        self.assertIn(thread.progress_signal.emit.call_args_list[0][0][0], 
                     ['PIPELINE_START', 'PipelineEvents.PIPELINE_START'])
    
    def test_backward_compatibility(self):
        """测试向后兼容性 - 原有的PipelineThread仍然存在"""
        from pktmask.gui.main_window import PipelineThread
        
        # 验证原有类仍然存在
        self.assertTrue(hasattr(PipelineThread, '__init__'))
        self.assertTrue(hasattr(PipelineThread, 'run'))
        self.assertTrue(hasattr(PipelineThread, 'stop'))
    
    @patch('pktmask.gui.managers.pipeline_manager.PipelineExecutor')
    def test_no_stages_selected(self, mock_executor_class):
        """测试未选择任何处理步骤的情况"""
        from pktmask.gui.managers.pipeline_manager import PipelineManager
        
        # Mock主窗口 - 所有复选框都未选中
        mock_main_window = Mock()
        mock_main_window.mask_ip_cb.isChecked.return_value = False
        mock_main_window.dedup_packet_cb.isChecked.return_value = False
        mock_main_window.trim_packet_cb.isChecked.return_value = False
        
        # 创建PipelineManager
        manager = PipelineManager(mock_main_window)
        
        # 测试配置构建
        config = manager._build_pipeline_config()
        
        # 验证返回空配置
        self.assertEqual(config, {})
    
    def test_gui_text_preservation(self):
        """测试GUI文本保持不变 - 这是Phase 6的关键要求"""
        # 这个测试主要是文档性的，确保GUI复选框文本仍然是用户友好的
        
        # 根据REFACTOR_PLAN.md：
        # "GUI 文案仍显示"Trim Payloads"以避免用户感知变化，
        #  但内部调用 `mask_payload` Processor"
        
        # 这意味着：
        # - trim_packet_cb 复选框的显示文本仍然是 "Trim Payloads"
        # - 但内部配置使用 "mask" 键
        
        # 由于GUI文本在UI创建时设置，这里主要是确保配置映射正确
        from pktmask.gui.managers.pipeline_manager import PipelineManager
        
        # Mock主窗口
        mock_main_window = Mock()
        mock_main_window.trim_packet_cb.isChecked.return_value = True
        mock_main_window.mask_ip_cb.isChecked.return_value = False
        mock_main_window.dedup_packet_cb.isChecked.return_value = False
        
        manager = PipelineManager(mock_main_window)
        config = manager._build_pipeline_config()
        
        # 验证内部使用正确的新键名
        self.assertIn("mask", config)  # 内部使用新的键名
        self.assertNotIn("trim", config)  # 不使用旧的键名


class TestPhase6Integration(unittest.TestCase):
    """测试Phase 6整体集成"""
    
    @patch('pktmask.gui.managers.pipeline_manager.PipelineExecutor')
    def test_end_to_end_config_flow(self, mock_executor_class):
        """测试端到端的配置流程"""
        from pktmask.gui.managers.pipeline_manager import PipelineManager
        
        # Mock完整的主窗口
        mock_main_window = Mock()
        mock_main_window.base_dir = "/test/input"
        mock_main_window.current_output_dir = "/test/output"
        mock_main_window.mask_ip_cb.isChecked.return_value = True
        mock_main_window.dedup_packet_cb.isChecked.return_value = True
        mock_main_window.trim_packet_cb.isChecked.return_value = True
        
        # Mock其他必要属性
        mock_main_window.files_processed_count = 0
        mock_main_window.packets_processed_count = 0
        mock_main_window.files_processed_label = Mock()
        mock_main_window.packets_processed_label = Mock()
        mock_main_window.log_text = Mock()
        
        # 创建manager
        manager = PipelineManager(mock_main_window)
        
        # 测试配置构建
        config = manager._build_pipeline_config()
        
        # 验证所有stages都被包含
        self.assertIn("anon", config)
        self.assertIn("dedup", config) 
        self.assertIn("mask", config)
        
        # 验证所有stages都启用
        self.assertTrue(config["anon"]["enabled"])
        self.assertTrue(config["dedup"]["enabled"])
        self.assertTrue(config["mask"]["enabled"])
        
        # 验证mask配置包含recipe_path
        self.assertIn("recipe_path", config["mask"])


if __name__ == '__main__':
    unittest.main() 