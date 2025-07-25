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
            remove_dupes=True, anonymize_ips=True, mask_payloads=True
        )
        cli_config = config_service.build_pipeline_config(cli_options)

        # 测试GUI配置
        gui_options = config_service.create_options_from_gui(
            remove_dupes_checked=True, anonymize_ips_checked=True, mask_payloads_checked=True
        )
        gui_config = config_service.build_pipeline_config(gui_options)

        # 验证配置结构一致性
        assert set(cli_config.keys()) == set(gui_config.keys())
        assert (
            cli_config["remove_dupes"]["enabled"]
            == gui_config["remove_dupes"]["enabled"]
        )
        assert (
            cli_config["anonymize_ips"]["enabled"]
            == gui_config["anonymize_ips"]["enabled"]
        )
        assert (
            cli_config["mask_payloads"]["enabled"]
            == gui_config["mask_payloads"]["enabled"]
        )

    @patch("pktmask.services.pipeline_service.process_single_file")
    def test_single_file_processing(self, mock_process):
        """测试单文件处理"""
        # 模拟处理结果
        mock_process.return_value = {
            "success": True,
            "input_file": str(self.test_file),
            "output_file": str(self.output_dir / "test_processed.pcap"),
            "duration_ms": 1000.0,
            "stage_stats": [],
            "errors": [],
            "total_files": 1,
            "processed_files": 1,
        }

        # 执行命令
        result = self.runner.invoke(
            app,
            [
                "mask",
                str(self.test_file),
                "-o",
                str(self.output_dir / "test_processed.pcap"),
                "--dedup",
                "--anon",
            ],
        )

        assert result.exit_code == 0
        mock_process.assert_called_once()

    @patch("pktmask.services.pipeline_service.process_directory_cli")
    def test_directory_processing(self, mock_process):
        """测试目录处理"""
        # 模拟处理结果
        mock_process.return_value = {
            "success": True,
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "duration_ms": 3000.0,
            "total_files": 4,
            "processed_files": 4,
            "failed_files": 0,
            "errors": [],
        }

        # 执行命令
        result = self.runner.invoke(
            app,
            [
                "mask",
                str(self.input_dir),
                "-o",
                str(self.output_dir),
                "--dedup",
                "--anon",
                "--verbose",
            ],
        )

        assert result.exit_code == 0
        mock_process.assert_called_once()

    def test_intelligent_defaults_directory_processing(self):
        """测试目录处理的智能默认值 - 自动启用所有操作"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建测试目录和PCAP文件
            test_dir = Path(temp_dir) / "pcaps"
            test_dir.mkdir()
            test_pcap = test_dir / "test.pcap"
            test_pcap.write_text("fake pcap content")

            result = self.runner.invoke(
                app, ["process", str(test_dir)]
            )

            # 应该显示自动启用所有操作的消息
            assert "Directory processing detected: auto-enabled all operations" in result.stdout
            assert "--dedup --anon --mask" in result.stdout
            assert "Auto-generated output path:" in result.stdout

    def test_intelligent_defaults_file_processing_requires_flags(self):
        """测试文件处理需要明确指定操作标志"""
        result = self.runner.invoke(
            app, ["process", str(self.test_file)]
        )

        assert result.exit_code == 1
        assert "At least one operation must be specified: --dedup, --anon, or --mask" in (result.stdout + result.stderr)

    def test_explicit_flags_override_intelligent_defaults(self):
        """测试明确指定的标志会覆盖智能默认值"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建测试目录和PCAP文件
            test_dir = Path(temp_dir) / "pcaps"
            test_dir.mkdir()
            test_pcap = test_dir / "test.pcap"
            test_pcap.write_text("fake pcap content")

            result = self.runner.invoke(
                app, ["process", str(test_dir), "--dedup", "--anon"]
            )

            # 不应该显示自动启用消息，因为用户明确指定了操作
            assert "Directory processing detected: auto-enabled all operations" not in result.stdout
            assert "Auto-generated output path:" in result.stdout

    def test_info_command_file(self):
        """测试info命令 - 文件模式"""
        result = self.runner.invoke(app, ["info", str(self.test_file)])

        assert result.exit_code == 0
        assert "File:" in result.stdout
        assert str(self.test_file) in result.stdout

    def test_info_command_directory(self):
        """测试info命令 - 目录模式"""
        result = self.runner.invoke(app, ["info", str(self.input_dir), "--verbose"])

        assert result.exit_code == 0
        assert "Directory:" in result.stdout
        assert "Files: 4" in result.stdout

    def test_info_command_json_output(self):
        """测试info命令 - JSON输出"""
        result = self.runner.invoke(
            app, ["info", str(self.input_dir), "--format", "json"]
        )

        assert result.exit_code == 0

        # 验证JSON格式
        try:
            data = json.loads(result.stdout)
            assert data["type"] == "directory"
            assert data["total_files"] == 4
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    @patch("pktmask.services.pipeline_service.process_single_file")
    def test_report_generation(self, mock_process):
        """测试报告生成功能"""
        mock_process.return_value = {
            "success": True,
            "input_file": str(self.test_file),
            "output_file": str(self.output_dir / "test_processed.pcap"),
            "duration_ms": 1000.0,
            "stage_stats": [
                {
                    "stage_name": "DeduplicationStage",
                    "packets_processed": 100,
                    "packets_modified": 10,
                    "duration_ms": 500.0,
                }
            ],
            "errors": [],
            "total_files": 1,
            "processed_files": 1,
        }

        result = self.runner.invoke(
            app,
            [
                "mask",
                str(self.test_file),
                "-o",
                str(self.output_dir / "test_processed.pcap"),
                "--save-report",
                "--report-detailed",
            ],
        )

        assert result.exit_code == 0
        assert "Report saved:" in result.stdout

    def test_error_handling(self):
        """测试错误处理"""
        # 测试不存在的文件
        result = self.runner.invoke(
            app,
            [
                "mask",
                "/nonexistent/file.pcap",
                "-o",
                str(self.output_dir / "output.pcap"),
            ],
        )

        assert result.exit_code != 0

    def test_parameter_validation(self):
        """测试参数验证"""
        # 测试基本的mask命令
        result = self.runner.invoke(
            app,
            [
                "mask",
                str(self.test_file),
                "-o",
                str(self.output_dir / "output.pcap"),
            ],
        )

        # 应该成功执行
        assert result.exit_code == 0

    @patch("pktmask.services.pipeline_service.process_single_file")
    def test_verbose_output(self, mock_process):
        """测试详细输出模式"""
        mock_process.return_value = {
            "success": True,
            "input_file": str(self.test_file),
            "output_file": str(self.output_dir / "test_processed.pcap"),
            "duration_ms": 1000.0,
            "stage_stats": [],
            "errors": [],
            "total_files": 1,
            "processed_files": 1,
        }

        result = self.runner.invoke(
            app,
            [
                "mask",
                str(self.test_file),
                "-o",
                str(self.output_dir / "test_processed.pcap"),
                "--verbose",
            ],
        )

        assert result.exit_code == 0
        # 在verbose模式下应该有更多输出
        assert len(result.stdout.split("\n")) > 3

    def test_output_format_options(self):
        """测试输出格式选项"""
        # 测试JSON格式输出
        result = self.runner.invoke(
            app, ["info", str(self.test_file), "--format", "json"]
        )

        assert result.exit_code == 0

        # 验证是否为有效JSON
        try:
            json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail("JSON format output is invalid")

    def test_process_command_validation_no_operations(self):
        """测试process命令验证 - 没有指定操作"""
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.test_file),
                "-o",
                str(self.output_dir / "output.pcap"),
            ],
        )

        assert result.exit_code == 1
        assert "At least one operation must be specified" in result.stdout

    def test_process_command_mask_uses_tls_protocol(self):
        """测试process命令掩码功能使用TLS协议"""
        # Test that mask functionality works without protocol parameter
        result = self.runner.invoke(
            app,
            [
                "process",
                "--help"
            ],
        )

        # Should not show protocol parameter in help
        assert result.exit_code == 0
        assert "--protocol" not in result.stdout
        assert "--mask" in result.stdout

    def test_process_command_help(self):
        """测试process命令帮助信息"""
        result = self.runner.invoke(app, ["process", "--help"])

        assert result.exit_code == 0
        assert "--dedup" in result.stdout
        assert "--anon" in result.stdout
        assert "--mask" in result.stdout
        assert "Unified processing" in result.stdout

    def test_process_command_validation_no_operations(self):
        """测试process命令验证 - 没有指定操作"""
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.test_file),
                "-o",
                str(self.output_dir / "output.pcap"),
            ],
        )

        assert result.exit_code == 1
        # Error messages go to stderr in typer
        assert "At least one operation must be specified" in (result.stdout + result.stderr)



    def test_main_help_shows_process_command(self):
        """测试主帮助显示process命令"""
        result = self.runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "process" in result.stdout
        assert "Unified processing" in result.stdout

    def test_unified_config_functionality(self):
        """测试统一CLI配置功能"""
        from pktmask.services.config_service import build_config_from_unified_args

        # 测试所有操作启用的情况
        all_config = build_config_from_unified_args(
            dedup=True,
            anon=True,
            mask=True,
        )

        assert "remove_dupes" in all_config
        assert "anonymize_ips" in all_config
        assert "mask_payloads" in all_config
        assert all_config["remove_dupes"]["enabled"] is True
        assert all_config["anonymize_ips"]["enabled"] is True
        assert all_config["mask_payloads"]["enabled"] is True

        # 测试单个操作的情况
        dedup_config = build_config_from_unified_args(dedup=True)
        assert "remove_dupes" in dedup_config
        assert dedup_config["remove_dupes"]["enabled"] is True

        anon_config = build_config_from_unified_args(anon=True)
        assert "anonymize_ips" in anon_config
        assert anon_config["anonymize_ips"]["enabled"] is True

        mask_config = build_config_from_unified_args(mask=True)
        assert "mask_payloads" in mask_config
        assert mask_config["mask_payloads"]["enabled"] is True

        # 测试新的灵活组合：dedup + anon（不包含mask）
        dedup_anon_config = build_config_from_unified_args(dedup=True, anon=True, mask=False)
        assert "remove_dupes" in dedup_anon_config
        assert "anonymize_ips" in dedup_anon_config
        assert "mask_payloads" not in dedup_anon_config

    def test_smart_output_path_generation(self):
        """测试智能输出路径生成"""
        from pktmask.cli import _generate_smart_output_path
        from pathlib import Path

        # 测试文件输入
        input_file = Path("/tmp/test.pcap")
        output_file = _generate_smart_output_path(input_file, "file")
        assert output_file == Path("/tmp/test_processed.pcap")

        # 测试目录输入
        input_dir = Path("/tmp/pcaps")
        output_dir = _generate_smart_output_path(input_dir, "directory")
        assert output_dir == Path("/tmp/pcaps_processed")

    def test_input_type_detection(self):
        """测试输入类型检测"""
        from pktmask.cli import _detect_input_type
        from pathlib import Path
        import tempfile
        import os

        # 测试不存在的路径
        non_existent = Path("/non/existent/path")
        input_type, error = _detect_input_type(non_existent)
        assert input_type == "invalid"
        assert "does not exist" in error

        # 测试有效的PCAP文件
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as f:
            pcap_file = Path(f.name)

        try:
            input_type, error = _detect_input_type(pcap_file)
            assert input_type == "file"
            assert error is None
        finally:
            os.unlink(pcap_file)

        # 测试无效的文件扩展名
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            txt_file = Path(f.name)

        try:
            input_type, error = _detect_input_type(txt_file)
            assert input_type == "invalid"
            assert "must be a PCAP or PCAPNG file" in error
        finally:
            os.unlink(txt_file)

        # 测试空目录
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir)
            input_type, error = _detect_input_type(empty_dir)
            assert input_type == "invalid"
            assert "contains no PCAP/PCAPNG files" in error

    def test_process_command_without_output_parameter(self):
        """测试process命令不指定输出参数"""
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.test_file),
                "--dedup",
            ],
        )

        # 应该显示自动生成的输出路径
        assert "Auto-generated output path:" in result.stdout


class TestCLIBackwardCompatibility:
    """CLI向后兼容性测试"""

    def setup_method(self):
        self.runner = CliRunner()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_file = self.temp_dir / "test.pcap"
        self.test_file.write_bytes(b"fake pcap content")

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)




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
            remove_dupes_checked=True, anonymize_ips_checked=True, mask_payloads_checked=True
        )
        gui_config = service.build_pipeline_config(gui_options)

        # CLI配置
        cli_options = service.create_options_from_cli_args(
            remove_dupes=True, anonymize_ips=True, mask_payloads=True
        )
        cli_config = service.build_pipeline_config(cli_options)

        # 验证核心配置一致性
        assert (
            gui_config["remove_dupes"]["enabled"]
            == cli_config["remove_dupes"]["enabled"]
        )
        assert (
            gui_config["anonymize_ips"]["enabled"]
            == cli_config["anonymize_ips"]["enabled"]
        )




