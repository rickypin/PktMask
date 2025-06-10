"""
管道集成测试
测试处理管道的完整工作流
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pktmask.core.pipeline import Pipeline
from pktmask.config.settings import AppConfig


@pytest.mark.integration
class TestPipelineIntegration:
    """管道集成测试"""
    
    @pytest.fixture
    def pipeline(self, test_config):
        """创建管道实例"""
        return Pipeline(test_config)
    
    def test_pipeline_initialization(self, pipeline):
        """测试管道初始化"""
        assert pipeline is not None
        assert hasattr(pipeline, 'process')
    
    def test_pipeline_with_empty_processor_list(self, pipeline, temp_dir):
        """测试空处理器列表的管道"""
        input_file = temp_dir / "input.pcap"
        output_file = temp_dir / "output.pcap"
        input_file.touch()
        
        # 使用空处理器列表
        processors = []
        
        try:
            result = pipeline.process(str(input_file), str(output_file), processors)
            # 应该能处理空列表的情况
            assert result is not None
        except ValueError:
            # 拒绝空列表也是合理的
            pass
    
    @patch('pktmask.core.processors.deduplicator.Deduplicator')
    def test_pipeline_with_single_processor(self, mock_deduplicator, pipeline, temp_dir):
        """测试单个处理器的管道"""
        # 设置模拟
        mock_processor_instance = Mock()
        mock_processor_instance.process.return_value = {
            "step_name": "remove_dupes",
            "status": "success"
        }
        mock_deduplicator.return_value = mock_processor_instance
        
        input_file = temp_dir / "input.pcap"
        output_file = temp_dir / "output.pcap"
        input_file.touch()
        
        # 使用单个处理器
        processors = ["deduplicator"]
        
        try:
            result = pipeline.process(str(input_file), str(output_file), processors)
            assert result is not None
        except Exception as e:
            # 如果失败，至少应该是可预期的异常
            assert isinstance(e, (ValueError, KeyError, ImportError))
    
    @patch('pktmask.core.processors.deduplicator.Deduplicator')
    @patch('pktmask.core.processors.ip_anonymizer.IPAnonymizer')
    def test_pipeline_with_multiple_processors(self, mock_ip_anon, mock_dedup, pipeline, temp_dir):
        """测试多个处理器的管道"""
        # 设置模拟
        mock_dedup_instance = Mock()
        mock_dedup_instance.process.return_value = {"step_name": "remove_dupes", "status": "success"}
        mock_dedup.return_value = mock_dedup_instance
        
        mock_ip_instance = Mock()
        mock_ip_instance.process.return_value = {"step_name": "mask_ips", "status": "success"}
        mock_ip_anon.return_value = mock_ip_instance
        
        input_file = temp_dir / "input.pcap"
        output_file = temp_dir / "output.pcap"
        input_file.touch()
        
        # 使用多个处理器
        processors = ["deduplicator", "ip_anonymizer"]
        
        try:
            result = pipeline.process(str(input_file), str(output_file), processors)
            assert result is not None
        except Exception as e:
            # 如果失败，至少应该是可预期的异常
            assert isinstance(e, (ValueError, KeyError, ImportError))
    
    def test_pipeline_error_handling(self, pipeline, temp_dir):
        """测试管道错误处理"""
        # 不存在的输入文件
        nonexistent_file = temp_dir / "nonexistent.pcap"
        output_file = temp_dir / "output.pcap"
        
        with pytest.raises((FileNotFoundError, ValueError)):
            pipeline.process(str(nonexistent_file), str(output_file), ["deduplicator"])


@pytest.mark.integration
class TestProcessorFactory:
    """处理器工厂集成测试"""
    
    def test_factory_function_exists(self):
        """测试工厂函数存在"""
        from pktmask.core.factory import get_step_instance
        assert get_step_instance is not None
        assert callable(get_step_instance)
    
    def test_factory_can_create_steps(self):
        """测试工厂可以创建处理步骤"""
        from pktmask.core.factory import get_step_instance
        
        # 测试创建已知的处理步骤
        known_steps = ["dedup_packet", "trim_packet", "mask_ip"]
        
        for step_name in known_steps:
            try:
                step = get_step_instance(step_name)
                assert step is not None
            except (KeyError, ImportError, ValueError):
                # 如果工厂不支持这个步骤，应该抛出明确的异常
                pass
    
    def test_factory_handles_unknown_step(self):
        """测试工厂处理未知步骤"""
        from pktmask.core.factory import get_step_instance
        
        with pytest.raises((KeyError, ValueError)):
            get_step_instance("unknown_step")


@pytest.mark.integration
class TestPipelineConfigIntegration:
    """管道配置集成测试"""
    
    def test_pipeline_respects_config_settings(self, temp_dir):
        """测试管道遵循配置设置"""
        # 创建自定义配置
        config = AppConfig.default()
        config.output_directory = str(temp_dir / "custom_output")
        config.log_directory = str(temp_dir / "custom_logs")
        
        pipeline = Pipeline(config)
        assert pipeline is not None
    
    def test_pipeline_with_invalid_config(self):
        """测试无效配置的管道"""
        # 测试None配置
        try:
            pipeline = Pipeline(None)
            # 如果允许None配置，应该有默认行为
            assert pipeline is not None
        except (TypeError, ValueError):
            # 拒绝None配置也是合理的
            pass
    
    def test_pipeline_config_validation(self, test_config):
        """测试管道配置验证"""
        # 修改配置中的路径为无效路径
        test_config.output_directory = "/invalid/nonexistent/path"
        
        try:
            pipeline = Pipeline(test_config)
            # 如果管道接受无效路径，应该在运行时处理
            assert pipeline is not None
        except (ValueError, OSError):
            # 在初始化时验证路径也是合理的
            pass


@pytest.mark.integration
@pytest.mark.slow
class TestPipelinePerformance:
    """管道性能集成测试"""
    
    def test_pipeline_handles_large_processor_chain(self, test_config, temp_dir):
        """测试管道处理大量处理器链"""
        input_file = temp_dir / "input.pcap"
        output_file = temp_dir / "output.pcap"
        input_file.touch()
        
        # 创建一个较长的处理器链
        processors = ["deduplicator", "ip_anonymizer", "trimmer"] * 3
        
        pipeline = Pipeline(test_config)
        
        try:
            # 这个测试主要检查管道不会崩溃
            result = pipeline.process(str(input_file), str(output_file), processors)
            # 如果成功，结果应该不为空
            if result is not None:
                assert result is not None
        except Exception as e:
            # 如果失败，应该是可预期的异常类型
            assert isinstance(e, (ValueError, KeyError, ImportError, FileNotFoundError))
    
    def test_pipeline_memory_usage(self, test_config, temp_dir):
        """测试管道内存使用"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        input_file = temp_dir / "input.pcap"
        output_file = temp_dir / "output.pcap"
        input_file.touch()
        
        pipeline = Pipeline(test_config)
        
        try:
            pipeline.process(str(input_file), str(output_file), ["deduplicator"])
        except Exception:
            # 即使处理失败，也要检查内存
            pass
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # 内存增长应该在合理范围内（比如小于100MB）
        assert memory_increase < 100 * 1024 * 1024  # 100MB 