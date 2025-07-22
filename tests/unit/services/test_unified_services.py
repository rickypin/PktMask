"""
统一服务层单元测试
验证各服务组件的功能正确性
"""
import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from pktmask.services.config_service import (
    ConfigService, ProcessingOptions, MaskMode,
    get_config_service, build_config_from_cli_args, build_config_from_gui
)
from pktmask.services.output_service import OutputService, OutputFormat, OutputLevel
from pktmask.services.progress_service import ProgressService, ProgressStyle
from pktmask.services.report_service import ReportService, ProcessingReport


class TestConfigService:
    """配置服务测试"""
    
    def test_processing_options_creation(self):
        """测试处理选项创建"""
        options = ProcessingOptions(
            enable_dedup=True,
            enable_anon=True,
            enable_mask=True,
            mask_mode=MaskMode.ENHANCED
        )
        
        assert options.enable_dedup is True
        assert options.enable_anon is True
        assert options.enable_mask is True
        assert options.mask_mode == MaskMode.ENHANCED
    
    def test_config_service_initialization(self):
        """测试配置服务初始化"""
        service = ConfigService()
        assert service is not None
    
    def test_build_pipeline_config(self):
        """测试管道配置构建"""
        service = ConfigService()
        options = ProcessingOptions(
            enable_dedup=True,
            enable_anon=True,
            enable_mask=True
        )
        
        config = service.build_pipeline_config(options)
        
        assert "remove_dupes" in config
        assert "anonymize_ips" in config
        assert "mask_payloads" in config
        assert config["remove_dupes"]["enabled"] is True
        assert config["anonymize_ips"]["enabled"] is True
        assert config["mask_payloads"]["enabled"] is True
    
    def test_config_validation(self):
        """测试配置验证"""
        service = ConfigService()
        
        # 有效配置
        valid_config = {
            "remove_dupes": {"enabled": True},
            "anonymize_ips": {"enabled": True}
        }
        is_valid, error = service.validate_config(valid_config)
        assert is_valid is True
        assert error is None
        
        # 无效配置 - 空配置
        invalid_config = {}
        is_valid, error = service.validate_config(invalid_config)
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_cli_args_to_options(self):
        """测试CLI参数转换为选项"""
        service = ConfigService()
        options = service.create_options_from_cli_args(
            enable_dedup=True,
            enable_anon=False,
            enable_mask=True,
            mask_mode="basic"
        )
        
        assert options.enable_dedup is True
        assert options.enable_anon is False
        assert options.enable_mask is True
        assert options.mask_mode == MaskMode.BASIC
    
    def test_gui_state_to_options(self):
        """测试GUI状态转换为选项"""
        service = ConfigService()
        options = service.create_options_from_gui(
            dedup_checked=True,
            anon_checked=True,
            mask_checked=False
        )
        
        assert options.enable_dedup is True
        assert options.enable_anon is True
        assert options.enable_mask is False
    
    def test_convenience_functions(self):
        """测试便捷函数"""
        # 测试CLI配置构建
        cli_config = build_config_from_cli_args(
            enable_dedup=True,
            enable_anon=True
        )
        assert "remove_dupes" in cli_config
        assert "anonymize_ips" in cli_config
        
        # 测试GUI配置构建
        gui_config = build_config_from_gui(
            dedup=True,
            anon=True,
            mask=False
        )
        assert "remove_dupes" in gui_config
        assert "anonymize_ips" in gui_config
        assert "mask_payloads" not in gui_config


class TestOutputService:
    """输出服务测试"""
    
    def test_output_service_initialization(self):
        """测试输出服务初始化"""
        service = OutputService(
            output_format=OutputFormat.TEXT,
            output_level=OutputLevel.VERBOSE
        )
        
        assert service.format == OutputFormat.TEXT
        assert service.level == OutputLevel.VERBOSE
    
    def test_processing_summary_text(self):
        """测试文本格式处理摘要"""
        service = OutputService(OutputFormat.TEXT, OutputLevel.NORMAL)
        
        result = {
            'success': True,
            'duration_ms': 1500.0,
            'total_files': 3,
            'processed_files': 3,
            'output_dir': '/test/output'
        }
        
        # 这里我们主要测试不会抛出异常
        try:
            service.print_processing_summary(result)
        except Exception as e:
            pytest.fail(f"print_processing_summary raised {e}")
    
    def test_processing_summary_json(self):
        """测试JSON格式处理摘要"""
        import io
        import sys
        
        # 捕获输出
        captured_output = io.StringIO()
        service = OutputService(
            OutputFormat.JSON, 
            OutputLevel.NORMAL,
            captured_output
        )
        
        result = {
            'success': True,
            'duration_ms': 1500.0,
            'total_files': 3,
            'processed_files': 3
        }
        
        service.print_processing_summary(result)
        output = captured_output.getvalue()
        
        # 验证输出是有效的JSON
        try:
            json.loads(output)
        except json.JSONDecodeError:
            pytest.fail("JSON output is invalid")


class TestProgressService:
    """进度服务测试"""
    
    def test_progress_service_initialization(self):
        """测试进度服务初始化"""
        service = ProgressService(
            style=ProgressStyle.DETAILED,
            update_interval=0.1
        )
        
        assert service.style == ProgressStyle.DETAILED
        assert service.update_interval == 0.1
    
    def test_progress_callbacks(self):
        """测试进度回调"""
        service = ProgressService(ProgressStyle.NONE)
        
        callback_called = False
        def test_callback(event_type, data):
            nonlocal callback_called
            callback_called = True
        
        service.add_callback(test_callback)
        service.start_processing(1)
        
        assert callback_called is True
    
    def test_progress_state_tracking(self):
        """测试进度状态跟踪"""
        service = ProgressService(ProgressStyle.NONE)
        
        service.start_processing(3)
        assert service.state.total_files == 3
        assert service.state.processed_files == 0
        
        service.start_file("test1.pcap")
        assert service.state.current_file == "test1.pcap"
        
        service.complete_file("test1.pcap", True)
        assert service.state.processed_files == 1


class TestReportService:
    """报告服务测试"""
    
    def test_report_service_initialization(self):
        """测试报告服务初始化"""
        service = ReportService()
        assert service is not None
    
    def test_report_lifecycle(self):
        """测试报告生命周期"""
        service = ReportService()
        
        # 开始报告
        service.start_report("/input/test.pcap", "/output/test.pcap")
        
        # 添加阶段统计
        service.add_stage_stats("TestStage", {
            'packets_processed': 100,
            'packets_modified': 50,
            'duration_ms': 1000.0
        })
        
        # 添加错误和警告
        service.add_error("Test error")
        service.add_warning("Test warning")
        
        # 完成报告
        report = service.finalize_report(
            success=True,
            total_files=1,
            processed_files=1,
            total_packets=100,
            modified_packets=50
        )
        
        assert isinstance(report, ProcessingReport)
        assert report.success is True
        assert report.total_files == 1
        assert report.processed_files == 1
        assert len(report.errors) == 1
        assert len(report.warnings) == 1
        assert len(report.stage_reports) == 1
    
    def test_text_report_generation(self):
        """测试文本报告生成"""
        service = ReportService()
        
        # 创建测试报告
        report = ProcessingReport(
            success=True,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_seconds=1.5,
            input_path="/test/input.pcap",
            output_path="/test/output.pcap",
            total_files=1,
            processed_files=1,
            failed_files=0,
            total_packets=100,
            modified_packets=50,
            stage_reports=[],
            errors=[],
            warnings=[]
        )
        
        text_report = service.generate_text_report(report)
        
        assert "PktMask Processing Report" in text_report
        assert "/test/input.pcap" in text_report
        assert "/test/output.pcap" in text_report
        assert "✅ Success" in text_report
    
    def test_json_report_generation(self):
        """测试JSON报告生成"""
        service = ReportService()
        
        report = ProcessingReport(
            success=True,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_seconds=1.5,
            input_path="/test/input.pcap",
            output_path="/test/output.pcap",
            total_files=1,
            processed_files=1,
            failed_files=0,
            total_packets=100,
            modified_packets=50,
            stage_reports=[],
            errors=[],
            warnings=[]
        )
        
        json_report = service.generate_json_report(report)
        
        # 验证JSON格式
        try:
            data = json.loads(json_report)
            assert data['basic_info']['success'] is True
            assert data['file_statistics']['total_files'] == 1
        except json.JSONDecodeError:
            pytest.fail("Generated JSON report is invalid")
    
    def test_report_file_saving(self):
        """测试报告文件保存"""
        service = ReportService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            report = ProcessingReport(
                success=True,
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_seconds=1.5,
                input_path="/test/input.pcap",
                output_path="/test/output.pcap",
                total_files=1,
                processed_files=1,
                failed_files=0,
                total_packets=100,
                modified_packets=50,
                stage_reports=[],
                errors=[],
                warnings=[]
            )
            
            # 保存文本报告
            file_path = service.save_report_to_file(
                report=report,
                output_path=temp_dir,
                format_type="text"
            )
            
            assert Path(file_path).exists()
            assert file_path.endswith(".txt")
            
            # 保存JSON报告
            json_file_path = service.save_report_to_file(
                report=report,
                output_path=temp_dir,
                format_type="json"
            )
            
            assert Path(json_file_path).exists()
            assert json_file_path.endswith(".json")
