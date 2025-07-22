"""
CLI统一功能集成测试
验证CLI与GUI功能的一致性
"""
import pytest
import tempfile
import shutil
import json
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from pktmask.cli import app
from pktmask.services.config_service import get_config_service
from pktmask.services.pipeline_service import create_pipeline_executor


class TestCLIUnified:
    """CLI统一功能测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.runner = CliRunner()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.input_dir = self.temp_dir / "input"
        self.output_dir = self.temp_dir / "output"
        self.input_dir.mkdir()
        self.output_dir.mkdir()
        
        # 创建测试文件
        self.test_file = self.input_dir / "test.pcap"
        self.test_file.write_bytes(b"fake pcap content")
        
        # 创建多个测试文件用于目录测试
        for i in range(3):
            test_file = self.input_dir / f"test_{i}.pcap"
            test_file.write_bytes(b"fake pcap content")
    
    def teardown_method(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)
    
    def test_config_service_consistency(self):
        """测试配置服务的一致性"""
        config_service = get_config_service()
        
        # 测试CLI参数配置
        cli_options = config_service.create_options_from_cli_args(
            enable_dedup=True,
            enable_anon=True,
            enable_mask=True,
            mask_mode="enhanced"
        )
        cli_config = config_service.build_pipeline_config(cli_options)
        
        # 测试GUI配置
        gui_options = config_service.create_options_from_gui(
            dedup_checked=True,
            anon_checked=True,
            mask_checked=True
        )
        gui_config = config_service.build_pipeline_config(gui_options)
        
        # 验证配置结构一致性
        assert set(cli_config.keys()) == set(gui_config.keys())
        assert cli_config["remove_dupes"]["enabled"] == gui_config["remove_dupes"]["enabled"]
        assert cli_config["anonymize_ips"]["enabled"] == gui_config["anonymize_ips"]["enabled"]
        assert cli_config["mask_payloads"]["enabled"] == gui_config["mask_payloads"]["enabled"]
    
    @patch('pktmask.services.pipeline_service.process_single_file')
    def test_single_file_processing(self, mock_process):
        """测试单文件处理"""
        # 模拟处理结果
        mock_process.return_value = {
            'success': True,
            'input_file': str(self.test_file),
            'output_file': str(self.output_dir / "test_processed.pcap"),
            'duration_ms': 1000.0,
            'stage_stats': [],
            'errors': [],
            'total_files': 1,
            'processed_files': 1
        }
        
        # 执行命令
        result = self.runner.invoke(app, [
            "mask",
            str(self.test_file),
            "-o", str(self.output_dir / "test_processed.pcap"),
            "--dedup",
            "--anon"
        ])
        
        assert result.exit_code == 0
        mock_process.assert_called_once()
    
    @patch('pktmask.services.pipeline_service.process_directory_cli')
    def test_directory_processing(self, mock_process):
        """测试目录处理"""
        # 模拟处理结果
        mock_process.return_value = {
            'success': True,
            'input_dir': str(self.input_dir),
            'output_dir': str(self.output_dir),
            'duration_ms': 3000.0,
            'total_files': 4,
            'processed_files': 4,
            'failed_files': 0,
            'errors': []
        }
        
        # 执行命令
        result = self.runner.invoke(app, [
            "mask",
            str(self.input_dir),
            "-o", str(self.output_dir),
            "--dedup",
            "--anon",
            "--verbose"
        ])
        
        assert result.exit_code == 0
        mock_process.assert_called_once()
    
    @patch('pktmask.services.pipeline_service.process_directory_cli')
    def test_batch_command(self, mock_process):
        """测试批量处理命令"""
        mock_process.return_value = {
            'success': True,
            'input_dir': str(self.input_dir),
            'output_dir': str(self.output_dir),
            'duration_ms': 3000.0,
            'total_files': 4,
            'processed_files': 4,
            'failed_files': 0,
            'errors': []
        }
        
        result = self.runner.invoke(app, [
            "batch",
            str(self.input_dir),
            "-o", str(self.output_dir),
            "--verbose"
        ])
        
        assert result.exit_code == 0
        mock_process.assert_called_once()
    
    def test_info_command_file(self):
        """测试info命令 - 文件模式"""
        result = self.runner.invoke(app, [
            "info",
            str(self.test_file)
        ])
        
        assert result.exit_code == 0
        assert "File:" in result.stdout
        assert str(self.test_file) in result.stdout
    
    def test_info_command_directory(self):
        """测试info命令 - 目录模式"""
        result = self.runner.invoke(app, [
            "info",
            str(self.input_dir),
            "--verbose"
        ])
        
        assert result.exit_code == 0
        assert "Directory:" in result.stdout
        assert "Files: 4" in result.stdout
    
    def test_info_command_json_output(self):
        """测试info命令 - JSON输出"""
        result = self.runner.invoke(app, [
            "info",
            str(self.input_dir),
            "--format", "json"
        ])
        
        assert result.exit_code == 0
        
        # 验证JSON格式
        try:
            data = json.loads(result.stdout)
            assert data['type'] == 'directory'
            assert data['total_files'] == 4
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
    
    @patch('pktmask.services.pipeline_service.process_single_file')
    def test_report_generation(self, mock_process):
        """测试报告生成功能"""
        mock_process.return_value = {
            'success': True,
            'input_file': str(self.test_file),
            'output_file': str(self.output_dir / "test_processed.pcap"),
            'duration_ms': 1000.0,
            'stage_stats': [
                {
                    'stage_name': 'DeduplicationStage',
                    'packets_processed': 100,
                    'packets_modified': 10,
                    'duration_ms': 500.0
                }
            ],
            'errors': [],
            'total_files': 1,
            'processed_files': 1
        }
        
        result = self.runner.invoke(app, [
            "mask",
            str(self.test_file),
            "-o", str(self.output_dir / "test_processed.pcap"),
            "--save-report",
            "--report-detailed"
        ])
        
        assert result.exit_code == 0
        assert "Report saved:" in result.stdout
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试不存在的文件
        result = self.runner.invoke(app, [
            "mask",
            "/nonexistent/file.pcap",
            "-o", str(self.output_dir / "output.pcap")
        ])
        
        assert result.exit_code != 0
    
    def test_parameter_validation(self):
        """测试参数验证"""
        # 测试无效的掩码模式
        result = self.runner.invoke(app, [
            "mask",
            str(self.test_file),
            "-o", str(self.output_dir / "output.pcap"),
            "--mode", "invalid_mode"
        ])
        
        # 应该仍然成功，因为会回退到默认模式
        assert result.exit_code == 0 or "Configuration error" in result.stdout
    
    @patch('pktmask.services.pipeline_service.process_single_file')
    def test_verbose_output(self, mock_process):
        """测试详细输出模式"""
        mock_process.return_value = {
            'success': True,
            'input_file': str(self.test_file),
            'output_file': str(self.output_dir / "test_processed.pcap"),
            'duration_ms': 1000.0,
            'stage_stats': [],
            'errors': [],
            'total_files': 1,
            'processed_files': 1
        }
        
        result = self.runner.invoke(app, [
            "mask",
            str(self.test_file),
            "-o", str(self.output_dir / "test_processed.pcap"),
            "--verbose"
        ])
        
        assert result.exit_code == 0
        # 在verbose模式下应该有更多输出
        assert len(result.stdout.split('\n')) > 3
    
    def test_output_format_options(self):
        """测试输出格式选项"""
        # 测试JSON格式输出
        result = self.runner.invoke(app, [
            "info",
            str(self.test_file),
            "--format", "json"
        ])
        
        assert result.exit_code == 0
        
        # 验证是否为有效JSON
        try:
            json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail("JSON format output is invalid")


class TestCLIBackwardCompatibility:
    """CLI向后兼容性测试"""
    
    def setup_method(self):
        self.runner = CliRunner()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_file = self.temp_dir / "test.pcap"
        self.test_file.write_bytes(b"fake pcap content")
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir)
    
    @patch('pktmask.services.pipeline_service.process_single_file')
    def test_legacy_dedup_command(self, mock_process):
        """测试遗留的dedup命令"""
        mock_process.return_value = {
            'success': True,
            'input_file': str(self.test_file),
            'output_file': str(self.temp_dir / "output.pcap"),
            'duration_ms': 1000.0,
            'stage_stats': [],
            'errors': [],
            'total_files': 1,
            'processed_files': 1
        }
        
        result = self.runner.invoke(app, [
            "dedup",
            str(self.test_file),
            "-o", str(self.temp_dir / "output.pcap")
        ])
        
        assert result.exit_code == 0
        mock_process.assert_called_once()
    
    @patch('pktmask.services.pipeline_service.process_single_file')
    def test_legacy_anon_command(self, mock_process):
        """测试遗留的anon命令"""
        mock_process.return_value = {
            'success': True,
            'input_file': str(self.test_file),
            'output_file': str(self.temp_dir / "output.pcap"),
            'duration_ms': 1000.0,
            'stage_stats': [],
            'errors': [],
            'total_files': 1,
            'processed_files': 1
        }
        
        result = self.runner.invoke(app, [
            "anon",
            str(self.test_file),
            "-o", str(self.temp_dir / "output.pcap")
        ])
        
        assert result.exit_code == 0
        mock_process.assert_called_once()


class TestGUICLIConsistency:
    """GUI与CLI一致性测试"""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_file = self.temp_dir / "test.pcap"
        self.test_file.write_bytes(b"fake pcap content")

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_config_consistency(self):
        """测试GUI和CLI配置的一致性"""
        from pktmask.services.config_service import get_config_service

        service = get_config_service()

        # GUI配置
        gui_options = service.create_options_from_gui(
            dedup_checked=True,
            anon_checked=True,
            mask_checked=True
        )
        gui_config = service.build_pipeline_config(gui_options)

        # CLI配置
        cli_options = service.create_options_from_cli_args(
            enable_dedup=True,
            enable_anon=True,
            enable_mask=True,
            mask_mode="enhanced"
        )
        cli_config = service.build_pipeline_config(cli_options)

        # 验证核心配置一致性
        assert gui_config["remove_dupes"]["enabled"] == cli_config["remove_dupes"]["enabled"]
        assert gui_config["anonymize_ips"]["enabled"] == cli_config["anonymize_ips"]["enabled"]
        assert gui_config["mask_payloads"]["enabled"] == cli_config["mask_payloads"]["enabled"]

        # 验证掩码配置结构一致性
        gui_mask = gui_config["mask_payloads"]
        cli_mask = cli_config["mask_payloads"]

        assert gui_mask["protocol"] == cli_mask["protocol"]
        assert gui_mask["mode"] == cli_mask["mode"]
        assert "marker_config" in gui_mask
        assert "marker_config" in cli_mask
        assert "masker_config" in gui_mask
        assert "masker_config" in cli_mask
