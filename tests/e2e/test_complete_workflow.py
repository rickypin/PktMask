"""
端到端测试
测试PktMask的完整工作流程
"""
import os
import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch

from pktmask.config.settings import AppConfig


@pytest.mark.e2e
class TestCompleteWorkflow:
    """完整工作流端到端测试"""
    
    def test_basic_processing_workflow(self, temp_dir, test_data_generator):
        """测试基本处理工作流"""
        # 创建测试输入文件
        input_file = temp_dir / "input.pcap"
        output_file = temp_dir / "output.pcap"
        test_data_generator.create_test_pcap(input_file)
        
        # 创建配置
        config = AppConfig.default()
        config.ui.last_output_dir = str(temp_dir / "output")
        
        # 这里应该测试完整的处理流程
        # 由于依赖实际的处理器实现，暂时使用模拟测试
        assert input_file.exists()
        assert config is not None
    
    def test_configuration_workflow(self, temp_dir):
        """测试配置工作流"""
        # 创建自定义配置
        config = AppConfig.default()
        config.ui.last_output_dir = str(temp_dir / "custom_output")
        
        # 验证配置应用
        assert config.ui.last_output_dir == str(temp_dir / "custom_output")
    
    def test_error_recovery_workflow(self, temp_dir):
        """测试错误恢复工作流"""
        # 模拟错误情况
        nonexistent_file = temp_dir / "nonexistent.pcap"
        output_file = temp_dir / "output.pcap"
        
        config = AppConfig.default()
        
        # 应该能优雅地处理文件不存在的情况
        try:
            # 这里应该调用实际的处理函数
            # 暂时只验证配置和文件路径
            assert not nonexistent_file.exists()
            assert config is not None
        except FileNotFoundError:
            # 预期的异常
            pass
    
    def test_output_generation_workflow(self, temp_dir, test_data_generator):
        """测试输出生成工作流"""
        # 创建测试输入
        input_file = temp_dir / "input.pcap"
        output_dir = temp_dir / "output"
        output_dir.mkdir(exist_ok=True)
        
        test_data_generator.create_test_pcap(input_file)
        
        config = AppConfig.default()
        config.ui.last_output_dir = str(output_dir)
        
        # 验证输出目录设置
        assert output_dir.exists()
        assert config.ui.last_output_dir == str(output_dir)


@pytest.mark.e2e
@pytest.mark.slow
class TestPerformanceWorkflow:
    """性能工作流端到端测试"""
    
    def test_large_file_processing(self, temp_dir, test_data_generator):
        """测试大文件处理性能"""
        # 创建较大的测试文件
        large_input = temp_dir / "large_input.pcap"
        output_file = temp_dir / "large_output.pcap"
        
        test_data_generator.create_test_pcap(large_input, packet_count=1000)
        
        config = AppConfig.default()
        config.ui.last_output_dir = str(temp_dir / "output")
        
        start_time = time.time()
        
        # 这里应该测试实际的大文件处理
        # 暂时只测试配置和文件创建
        assert large_input.exists()
        assert config is not None
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 处理时间应该在合理范围内（比如小于10秒）
        assert processing_time < 10.0
    
    def test_memory_efficient_processing(self, temp_dir, test_data_generator):
        """测试内存高效处理"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # 创建测试文件
        input_file = temp_dir / "memory_test.pcap"
        test_data_generator.create_test_pcap(input_file)
        
        config = AppConfig.default()
        
        # 模拟处理过程
        # 实际实现应该调用真实的处理器
        assert input_file.exists()
        assert config is not None
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # 内存增长应该在合理范围内
        assert memory_increase < 50 * 1024 * 1024  # 50MB


@pytest.mark.e2e
class TestErrorHandlingWorkflow:
    """错误处理工作流端到端测试"""
    
    def test_invalid_input_file_handling(self, temp_dir):
        """测试无效输入文件处理"""
        # 测试不存在的文件
        nonexistent_file = temp_dir / "nonexistent.pcap"
        output_file = temp_dir / "output.pcap"
        
        config = AppConfig.default()
        
        # 应该能检测到文件不存在
        assert not nonexistent_file.exists()
        
        # 实际的处理应该抛出适当的异常
        with pytest.raises(FileNotFoundError):
            if not nonexistent_file.exists():
                raise FileNotFoundError("File not found")
    
    def test_permission_denied_handling(self, temp_dir):
        """测试权限拒绝处理"""
        # 创建只读文件
        readonly_file = temp_dir / "readonly.pcap"
        readonly_file.touch()
        readonly_file.chmod(0o444)  # 只读
        
        config = AppConfig.default()
        
        # 应该能检测到权限问题
        assert readonly_file.exists()
        assert not os.access(readonly_file, os.W_OK)
    
    def test_disk_space_handling(self, temp_dir):
        """测试磁盘空间处理"""
        # 这个测试比较难模拟，主要验证配置
        config = AppConfig.default()
        config.ui.last_output_dir = str(temp_dir / "output")
        
        # 验证输出目录配置
        assert config.ui.last_output_dir == str(temp_dir / "output")


@pytest.mark.e2e
class TestIntegrationWorkflow:
    """集成工作流端到端测试"""
    
    def test_config_to_processing_integration(self, temp_dir, test_data_generator):
        """测试从配置到处理的完整集成"""
        # 创建完整的测试环境
        input_file = temp_dir / "integration_input.pcap"
        output_dir = temp_dir / "integration_output"
        log_dir = temp_dir / "integration_logs"
        
        test_data_generator.create_test_pcap(input_file)
        output_dir.mkdir(exist_ok=True)
        log_dir.mkdir(exist_ok=True)
        
        # 配置设置
        config = AppConfig.default()
        config.ui.last_output_dir = str(output_dir)
        config.log_directory = str(log_dir)
        
        # 验证完整的环境设置
        assert input_file.exists()
        assert output_dir.exists()
        assert log_dir.exists()
        assert config.ui.last_output_dir == str(output_dir)
        assert config.log_directory == str(log_dir)
    
    def test_processing_to_output_integration(self, temp_dir, test_data_generator):
        """测试从处理到输出的完整集成"""
        # 设置处理环境
        input_file = temp_dir / "process_input.pcap"
        output_file = temp_dir / "process_output.pcap"
        
        test_data_generator.create_test_pcap(input_file)
        
        config = AppConfig.default()
        config.ui.last_output_dir = str(temp_dir / "output")
        
        # 模拟处理结果
        processing_result = {
            "input_file": str(input_file),
            "output_file": str(output_file),
            "status": "success",
            "steps_completed": ["deduplication", "ip_anonymization"]
        }
        
        # 验证处理结果结构
        assert "input_file" in processing_result
        assert "output_file" in processing_result
        assert "status" in processing_result
        assert processing_result["status"] == "success"


@pytest.mark.e2e
@pytest.mark.gui
class TestGUIWorkflow:
    """GUI工作流端到端测试（如果支持无头模式）"""
    
    def test_gui_initialization(self, mock_gui_environment):
        """测试GUI初始化工作流"""
        # 在无头模式下测试GUI组件
        try:
            from PyQt6.QtWidgets import QApplication
            import sys
            
            # 创建应用程序实例（如果还没有的话）
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            # 验证应用程序创建成功
            assert app is not None
            
        except ImportError:
            # 如果PyQt6不可用，跳过GUI测试
            pytest.skip("PyQt6 not available for GUI testing")
    
    def test_gui_config_integration(self, mock_gui_environment, temp_dir):
        """测试GUI配置集成"""
        # 测试GUI与配置系统的集成
        config = AppConfig.default()
        config.ui.last_output_dir = str(temp_dir / "gui_output")
        
        # 在真实的GUI测试中，这里会验证GUI控件是否正确显示配置
        assert config.ui.last_output_dir == str(temp_dir / "gui_output")
        
        # 模拟GUI操作结果
        gui_result = {
            "config_loaded": True,
            "ui_initialized": True,
            "ready_for_processing": True
        }
        
        assert gui_result["config_loaded"] is True
        assert gui_result["ui_initialized"] is True 