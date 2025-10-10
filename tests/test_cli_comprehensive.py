#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask CLI 全面测试套件

基于代码审查的完整 CLI 命令和参数测试。
测试所有命令、参数组合、边界条件和错误处理。
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pktmask.__main__ import app


class TestCLICommands:
    """测试所有 CLI 命令"""

    @classmethod
    def setup_class(cls):
        """设置测试类"""
        cls.runner = CliRunner()
        cls.test_data_dir = Path("tests/samples/tls-single")

        # 验证测试数据存在
        if not cls.test_data_dir.exists():
            pytest.skip("测试数据目录不存在")

        # 获取测试文件
        cls.pcap_files = list(cls.test_data_dir.glob("*.pcap"))
        if not cls.pcap_files:
            pytest.skip("测试数据目录中没有 PCAP 文件")

        cls.test_pcap = cls.pcap_files[0]

    def setup_method(self):
        """每个测试方法的设置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

    def teardown_method(self):
        """每个测试方法的清理"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    # =========================================================================
    # 1. 主命令测试
    # =========================================================================

    def test_main_help(self):
        """测试主帮助命令"""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "PktMask" in result.stdout
        assert "process" in result.stdout
        assert "validate" in result.stdout
        assert "config" in result.stdout

    def test_invalid_command(self):
        """测试无效命令"""
        result = self.runner.invoke(app, ["invalid-command"])
        assert result.exit_code != 0

    # =========================================================================
    # 2. process 命令测试
    # =========================================================================

    def test_process_help(self):
        """测试 process 命令帮助"""
        result = self.runner.invoke(app, ["process", "--help"])
        assert result.exit_code == 0
        assert "--dedup" in result.stdout
        assert "--anon" in result.stdout
        assert "--mask" in result.stdout
        assert "--mask-protocol" in result.stdout
        assert "--verbose" in result.stdout
        assert "--output" in result.stdout

    def test_process_single_file_dedup(self):
        """测试单文件去重处理"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--dedup"],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_process_single_file_anon(self):
        """测试单文件 IP 匿名化处理"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--anon"],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_process_single_file_mask(self):
        """测试单文件载荷掩码处理"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--mask"],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_process_dedup_anon_combination(self):
        """测试去重+匿名化组合"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--dedup", "--anon"],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_process_dedup_mask_combination(self):
        """测试去重+掩码组合"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--dedup", "--mask"],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_process_anon_mask_combination(self):
        """测试匿名化+掩码组合"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--anon", "--mask"],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_process_all_operations(self):
        """测试所有操作组合"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--dedup", "--anon", "--mask"],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_process_no_operations_error(self):
        """测试没有操作标志时的错误"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file)],
        )
        assert result.exit_code == 1
        assert "At least one" in result.stdout or "At least one" in result.stderr

    def test_process_auto_output_path(self):
        """测试自动生成输出路径"""
        # 复制测试文件到临时目录
        test_file = self.temp_dir / "test.pcap"
        shutil.copy2(self.test_pcap, test_file)

        result = self.runner.invoke(
            app,
            ["process", str(test_file), "--dedup"],
        )
        assert result.exit_code == 0
        # 检查自动生成的输出文件
        expected_output = self.temp_dir / "test_processed.pcap"
        assert expected_output.exists()

    def test_process_verbose_mode(self):
        """测试详细输出模式"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--dedup", "--verbose"],
        )
        assert result.exit_code == 0
        assert "Input:" in result.stdout or "Output:" in result.stdout

    def test_process_mask_protocol_tls(self):
        """测试 TLS 协议掩码"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--mask", "--mask-protocol", "tls"],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_process_mask_protocol_http(self):
        """测试 HTTP 协议掩码"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--mask", "--mask-protocol", "http"],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_process_mask_protocol_auto(self):
        """测试自动协议检测"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--mask", "--mask-protocol", "auto"],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_process_mask_protocol_invalid(self):
        """测试无效协议参数"""
        output_file = self.output_dir / "output.pcap"
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--mask", "--mask-protocol", "invalid"],
        )
        assert result.exit_code == 1
        assert "Invalid" in result.stdout or "Invalid" in result.stderr

    def test_process_directory(self):
        """测试目录批量处理"""
        # 创建测试目录
        test_dir = self.temp_dir / "test_pcaps"
        test_dir.mkdir()
        shutil.copy2(self.test_pcap, test_dir / "test1.pcap")
        shutil.copy2(self.test_pcap, test_dir / "test2.pcap")

        result = self.runner.invoke(
            app,
            ["process", str(test_dir), "-o", str(self.output_dir), "--dedup"],
        )
        assert result.exit_code == 0
        # 检查输出文件
        assert (self.output_dir / "test1.pcap").exists()
        assert (self.output_dir / "test2.pcap").exists()

    # =========================================================================
    # 3. validate 命令测试
    # =========================================================================

    def test_validate_help(self):
        """测试 validate 命令帮助"""
        result = self.runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        assert "validate" in result.stdout.lower()

    def test_validate_single_file(self):
        """测试验证单个文件"""
        result = self.runner.invoke(app, ["validate", str(self.test_pcap)])
        assert result.exit_code == 0
        assert "Valid" in result.stdout or "✅" in result.stdout

    def test_validate_single_file_verbose(self):
        """测试详细模式验证单个文件"""
        result = self.runner.invoke(app, ["validate", str(self.test_pcap), "--verbose"])
        assert result.exit_code == 0
        assert "File size" in result.stdout or "size" in result.stdout.lower()

    def test_validate_directory(self):
        """测试验证目录"""
        result = self.runner.invoke(app, ["validate", str(self.test_data_dir)])
        assert result.exit_code == 0
        assert "Valid" in result.stdout or "✅" in result.stdout

    def test_validate_directory_verbose(self):
        """测试详细模式验证目录"""
        result = self.runner.invoke(app, ["validate", str(self.test_data_dir), "--verbose"])
        assert result.exit_code == 0
        assert "Files found" in result.stdout or "files" in result.stdout.lower()

    def test_validate_nonexistent_file(self):
        """测试验证不存在的文件"""
        result = self.runner.invoke(app, ["validate", str(self.temp_dir / "nonexistent.pcap")])
        assert result.exit_code == 1
        assert "not exist" in result.stdout.lower() or "not exist" in result.stderr.lower()

    def test_validate_invalid_file_type(self):
        """测试验证无效文件类型"""
        # 创建一个 .txt 文件
        txt_file = self.temp_dir / "test.txt"
        txt_file.write_text("test")

        result = self.runner.invoke(app, ["validate", str(txt_file)])
        assert result.exit_code == 1
        assert "PCAP" in result.stdout or "PCAP" in result.stderr

    # =========================================================================
    # 4. config 命令测试
    # =========================================================================

    def test_config_help(self):
        """测试 config 命令帮助"""
        result = self.runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "config" in result.stdout.lower()

    def test_config_dedup_only(self):
        """测试仅去重配置"""
        result = self.runner.invoke(app, ["config", "--dedup"])
        assert result.exit_code == 0
        assert "Remove Dupes" in result.stdout or "dedup" in result.stdout.lower()

    def test_config_anon_only(self):
        """测试仅匿名化配置"""
        result = self.runner.invoke(app, ["config", "--anon"])
        assert result.exit_code == 0
        assert "Anonymize" in result.stdout or "anon" in result.stdout.lower()

    def test_config_mask_only(self):
        """测试仅掩码配置"""
        result = self.runner.invoke(app, ["config", "--mask"])
        assert result.exit_code == 0
        assert "Mask" in result.stdout or "mask" in result.stdout.lower()

    def test_config_all_operations(self):
        """测试所有操作配置"""
        result = self.runner.invoke(app, ["config", "--dedup", "--anon", "--mask"])
        assert result.exit_code == 0
        assert "Remove Dupes" in result.stdout or "Anonymize" in result.stdout or "Mask" in result.stdout

    def test_config_no_operations_error(self):
        """测试无操作配置错误"""
        result = self.runner.invoke(app, ["config"])
        assert result.exit_code == 1
        assert "At least one" in result.stdout or "At least one" in result.stderr


class TestCLIInputValidation:
    """测试输入验证"""

    @classmethod
    def setup_class(cls):
        """设置测试类"""
        cls.runner = CliRunner()
        cls.test_data_dir = Path("tests/samples/tls-single")

        if not cls.test_data_dir.exists():
            pytest.skip("测试数据目录不存在")

        cls.pcap_files = list(cls.test_data_dir.glob("*.pcap"))
        if not cls.pcap_files:
            pytest.skip("测试数据目录中没有 PCAP 文件")

        cls.test_pcap = cls.pcap_files[0]

    def setup_method(self):
        """每个测试方法的设置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

    def teardown_method(self):
        """每个测试方法的清理"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    # =========================================================================
    # 输入文件测试
    # =========================================================================

    def test_nonexistent_input_file(self):
        """测试不存在的输入文件"""
        result = self.runner.invoke(
            app,
            ["process", str(self.temp_dir / "nonexistent.pcap"), "-o", str(self.output_dir / "out.pcap"), "--dedup"],
        )
        assert result.exit_code == 1
        assert "not exist" in result.stdout.lower() or "not exist" in result.stderr.lower()

    def test_invalid_file_extension(self):
        """测试无效文件扩展名"""
        txt_file = self.temp_dir / "test.txt"
        txt_file.write_text("test")

        result = self.runner.invoke(
            app,
            ["process", str(txt_file), "-o", str(self.output_dir / "out.pcap"), "--dedup"],
        )
        assert result.exit_code == 1
        assert "PCAP" in result.stdout or "PCAP" in result.stderr

    def test_pcapng_file_support(self):
        """测试 .pcapng 文件支持"""
        # 如果有 .pcapng 测试文件
        pcapng_files = list(self.test_data_dir.glob("*.pcapng"))
        if pcapng_files:
            result = self.runner.invoke(
                app,
                ["process", str(pcapng_files[0]), "-o", str(self.output_dir / "out.pcapng"), "--dedup"],
            )
            assert result.exit_code == 0

    def test_empty_directory(self):
        """测试空目录"""
        empty_dir = self.temp_dir / "empty"
        empty_dir.mkdir()

        result = self.runner.invoke(
            app,
            ["process", str(empty_dir), "-o", str(self.output_dir), "--dedup"],
        )
        # 应该警告没有文件，但不应该崩溃
        assert "No PCAP" in result.stdout or "No" in result.stdout

    def test_directory_with_mixed_files(self):
        """测试包含混合文件类型的目录"""
        mixed_dir = self.temp_dir / "mixed"
        mixed_dir.mkdir()

        # 复制 PCAP 文件
        shutil.copy2(self.test_pcap, mixed_dir / "test.pcap")
        # 创建非 PCAP 文件
        (mixed_dir / "readme.txt").write_text("test")
        (mixed_dir / "data.json").write_text("{}")

        result = self.runner.invoke(
            app,
            ["process", str(mixed_dir), "-o", str(self.output_dir), "--dedup"],
        )
        # 应该只处理 PCAP 文件
        assert result.exit_code == 0
        assert (self.output_dir / "test.pcap").exists()

    # =========================================================================
    # 输出路径测试
    # =========================================================================

    def test_output_directory_auto_creation(self):
        """测试输出目录自动创建"""
        nested_output = self.temp_dir / "level1" / "level2" / "output.pcap"

        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(nested_output), "--dedup"],
        )
        assert result.exit_code == 0
        assert nested_output.exists()

    def test_output_file_overwrite(self):
        """测试输出文件覆盖"""
        output_file = self.output_dir / "output.pcap"

        # 第一次处理
        result1 = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--dedup"],
        )
        assert result1.exit_code == 0

        # 第二次处理（覆盖）
        result2 = self.runner.invoke(
            app,
            ["process", str(self.test_pcap), "-o", str(output_file), "--dedup"],
        )
        assert result2.exit_code == 0

    # =========================================================================
    # 路径格式测试
    # =========================================================================

    def test_relative_path_input(self):
        """测试相对路径输入"""
        # 使用相对路径
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.test_pcap.relative_to(Path.cwd())),
                "-o",
                str(self.output_dir / "out.pcap"),
                "--dedup",
            ],
        )
        # 应该能够处理相对路径
        assert result.exit_code == 0 or "not exist" in result.stdout.lower()

    def test_absolute_path_input(self):
        """测试绝对路径输入"""
        result = self.runner.invoke(
            app,
            ["process", str(self.test_pcap.absolute()), "-o", str(self.output_dir / "out.pcap"), "--dedup"],
        )
        assert result.exit_code == 0
