#!/usr/bin/env python3
"""
测试重构后的 Pipeline Service 功能
"""
import unittest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

from pktmask.services.pipeline_service import (
    PipelineServiceError,
    ConfigurationError,
    create_pipeline_executor,
    process_directory,
    stop_pipeline,
    build_pipeline_config,
    validate_config
)
from pktmask.core.events import PipelineEvents


class TestPipelineService(unittest.TestCase):
    """测试 Pipeline Service 的核心功能"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.test_config = {
            "anon": {"enabled": True},
            "dedup": {"enabled": True}
        }
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """测试后的清理工作"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)
    
    def test_build_pipeline_config(self):
        """测试配置构建功能"""
        # 测试所有功能启用
        config = build_pipeline_config(
            enable_anon=True,
            enable_dedup=True,
            enable_mask=True
        )
        
        expected = {
            "anon": {"enabled": True},
            "dedup": {"enabled": True},
            "mask": {
                "enabled": True,
                "protocol": "tls",
                "mode": "enhanced",
                "marker_config": {
                    "preserve": {
                        "application_data": False,
                        "handshake": True,
                        "alert": True,
                        "change_cipher_spec": True,
                        "heartbeat": True
                    }
                },
                "masker_config": {
                    "preserve_ratio": 0.3
                }
            }
        }
        
        self.assertEqual(config, expected)
        
        # 测试空配置
        config = build_pipeline_config(
            enable_anon=False,
            enable_dedup=False,
            enable_mask=False
        )
        
        self.assertEqual(config, {})
    
    def test_validate_config(self):
        """测试配置验证功能"""
        # 测试有效配置
        valid, msg = validate_config(self.test_config)
        self.assertTrue(valid)
        self.assertIsNone(msg)
        
        # 测试无效配置
        valid, msg = validate_config({})
        self.assertFalse(valid)
        self.assertEqual(msg, "配置为空")
    
    @patch('pktmask.core.pipeline.executor.PipelineExecutor')
    def test_create_pipeline_executor(self, mock_executor_class):
        """测试执行器创建功能"""
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor
        
        executor = create_pipeline_executor(self.test_config)
        
        self.assertEqual(executor, mock_executor)
        mock_executor_class.assert_called_once_with(self.test_config)
    
    @patch('pktmask.core.pipeline.executor.PipelineExecutor')
    def test_create_pipeline_executor_error(self, mock_executor_class):
        """测试执行器创建失败"""
        mock_executor_class.side_effect = Exception("创建失败")
        
        with self.assertRaises(PipelineServiceError):
            create_pipeline_executor(self.test_config)
    
    def test_process_directory_no_files(self):
        """测试处理空目录"""
        mock_executor = Mock()
        mock_callback = Mock()
        
        # 空目录测试
        process_directory(
            executor=mock_executor,
            input_dir=self.temp_dir,
            output_dir=self.output_dir,
            progress_callback=mock_callback,
            is_running_check=lambda: True
        )
        
        # 验证发送了正确的事件
        calls = mock_callback.call_args_list
        self.assertTrue(any(call[0][0] == PipelineEvents.PIPELINE_START for call in calls))
        self.assertTrue(any(call[0][0] == PipelineEvents.LOG for call in calls))
        self.assertTrue(any(call[0][0] == PipelineEvents.PIPELINE_END for call in calls))
    
    def test_process_directory_with_pcap_files(self):
        """测试处理包含PCAP文件的目录"""
        # 创建测试用的PCAP文件
        test_pcap = os.path.join(self.temp_dir, "test.pcap")
        with open(test_pcap, 'w') as f:
            f.write("dummy pcap content")
        
        mock_executor = Mock()
        mock_result = Mock()
        mock_result.stage_stats = []
        mock_executor.run.return_value = mock_result
        
        mock_callback = Mock()
        
        process_directory(
            executor=mock_executor,
            input_dir=self.temp_dir,
            output_dir=self.output_dir,
            progress_callback=mock_callback,
            is_running_check=lambda: True
        )
        
        # 验证执行器被调用
        self.assertTrue(mock_executor.run.called)
        
        # 验证发送了文件处理事件
        calls = mock_callback.call_args_list
        self.assertTrue(any(call[0][0] == PipelineEvents.FILE_START for call in calls))
        self.assertTrue(any(call[0][0] == PipelineEvents.FILE_END for call in calls))
    
    def test_stop_pipeline(self):
        """测试停止管道功能"""
        mock_executor = Mock()
        mock_executor.stop = Mock()
        
        # 测试有stop方法的执行器
        stop_pipeline(mock_executor)
        mock_executor.stop.assert_called_once()
        
        # 测试没有stop方法的执行器
        mock_executor_no_stop = Mock()
        del mock_executor_no_stop.stop
        
        # 应该不会抛出异常
        stop_pipeline(mock_executor_no_stop)


class TestServicePipelineThread(unittest.TestCase):
    """测试 ServicePipelineThread 的功能"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """测试后的清理工作"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)
    
    def test_service_integration(self):
        """测试服务层集成"""
        # 测试服务层函数能正常导入和调用
        from pktmask.services.pipeline_service import (
            create_pipeline_executor,
            process_directory,
            stop_pipeline
        )
        
        # 这些函数应该可以正常导入
        self.assertTrue(callable(create_pipeline_executor))
        self.assertTrue(callable(process_directory))
        self.assertTrue(callable(stop_pipeline))
    
    def test_services_module_import(self):
        """测试服务模块导入"""
        # 测试能正常从 services 模块导入
        from pktmask.services import (
            PipelineServiceError,
            ConfigurationError,
            create_pipeline_executor,
            build_pipeline_config
        )
        
        # 验证异常类的继承关系
        self.assertTrue(issubclass(PipelineServiceError, Exception))
        self.assertTrue(issubclass(ConfigurationError, PipelineServiceError))
        
        # 验证函数可调用
        self.assertTrue(callable(create_pipeline_executor))
        self.assertTrue(callable(build_pipeline_config))


if __name__ == '__main__':
    unittest.main()
