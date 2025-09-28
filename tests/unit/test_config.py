"""
配置系统单元测试
测试AppConfig配置加载、验证、默认值等功能
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pktmask.config.settings import (
    AppConfig,
    LoggingSettings,
    ProcessingSettings,
    UISettings,
)


class TestAppConfig:
    """应用配置类测试"""

    def test_default_initialization(self):
        """测试默认初始化"""
        config = AppConfig.default()
        assert config is not None

        # 检查基本属性存在
        assert hasattr(config, "ui")
        assert hasattr(config, "processing")
        assert hasattr(config, "logging")

        # 检查子配置对象类型
        assert isinstance(config.ui, UISettings)
        assert isinstance(config.processing, ProcessingSettings)
        assert isinstance(config.logging, LoggingSettings)

    def test_config_attributes(self):
        """测试配置对象的基本属性"""
        config = AppConfig.default()

        # UI配置属性
        assert hasattr(config.ui, "window_width")
        assert hasattr(config.ui, "window_height")
        assert hasattr(config.ui, "theme")
        assert hasattr(config.ui, "default_remove_dupes")
        assert hasattr(config.ui, "default_anonymize_ips")
        assert hasattr(config.ui, "default_mask_payloads")

        # 处理配置属性
        assert hasattr(config.processing, "chunk_size")
        assert hasattr(config.processing, "max_workers")
        assert hasattr(config.processing, "timeout_seconds")

        # 日志配置属性
        assert hasattr(config.logging, "log_level")
        assert hasattr(config.logging, "log_to_file")

    def test_config_can_be_modified(self):
        """测试配置可以被修改"""
        config = AppConfig.default()

        # 修改UI设置
        config.ui.window_width = 1600
        assert config.ui.window_width == 1600

        config.ui.theme = "dark"
        assert config.ui.theme == "dark"

        # 修改处理设置
        config.processing.chunk_size = 20
        assert config.processing.chunk_size == 20

        # 修改日志设置
        config.logging.log_level = "DEBUG"
        assert config.logging.log_level == "DEBUG"

    def test_config_validation(self):
        """测试配置验证"""
        config = AppConfig.default()

        # 默认配置应该是有效的
        is_valid, messages = config.validate()
        assert is_valid is True

        # 测试无效配置
        config.processing.chunk_size = -1
        is_valid, messages = config.validate()
        assert is_valid is False
        assert len(messages) > 0


class TestUISettings:
    """UI设置测试"""

    def test_ui_defaults(self):
        """测试UI默认设置"""
        ui = UISettings()

        # 检查默认值
        assert ui.window_width == 1200
        assert ui.window_height == 800
        assert ui.theme == "auto"
        assert ui.default_remove_dupes is True
        assert ui.default_anonymize_ips is True
        assert ui.default_mask_payloads is True

    def test_ui_modifications(self):
        """测试UI设置修改"""
        ui = UISettings()

        # 修改窗口设置
        ui.window_width = 1600
        ui.window_height = 900
        ui.window_maximized = True

        assert ui.window_width == 1600
        assert ui.window_height == 900
        assert ui.window_maximized is True


class TestProcessingSettings:
    """处理设置测试"""

    def test_processing_defaults(self):
        """测试处理默认设置"""
        processing = ProcessingSettings()

        # 检查默认值
        assert processing.chunk_size == 10
        assert processing.max_workers == 4
        assert processing.timeout_seconds == 300
        assert processing.preserve_subnet_structure is True
        assert processing.dedup_algorithm == "sha256"

    def test_processing_modifications(self):
        """测试处理设置修改"""
        processing = ProcessingSettings()

        # 修改处理参数
        processing.chunk_size = 20
        processing.max_workers = 8
        processing.dedup_algorithm = "md5"

        assert processing.chunk_size == 20
        assert processing.max_workers == 8
        assert processing.dedup_algorithm == "md5"


class TestLoggingSettings:
    """日志设置测试"""

    def test_logging_defaults(self):
        """测试日志默认设置"""
        logging = LoggingSettings()

        # 检查默认值
        assert logging.log_level == "INFO"
        assert logging.log_to_file is True
        assert logging.log_file_max_size == 10 * 1024 * 1024  # 10MB
        assert logging.log_backup_count == 5

    def test_logging_modifications(self):
        """测试日志设置修改"""
        logging = LoggingSettings()

        # 修改日志参数
        logging.log_level = "DEBUG"
        logging.log_to_file = False
        logging.performance_logging = True

        assert logging.log_level == "DEBUG"
        assert logging.log_to_file is False
        assert logging.performance_logging is True


@pytest.mark.unit
class TestConfigurationIntegration:
    """配置集成测试"""

    def test_config_save_and_load(self, temp_dir):
        """测试配置保存和加载"""
        config_file = temp_dir / "test_config.yaml"

        # 创建配置
        config = AppConfig.default()
        config.ui.window_width = 1600
        config.processing.chunk_size = 20

        # 保存配置
        success = config.save(config_file)
        assert success is True
        assert config_file.exists()

        # 加载配置
        loaded_config = AppConfig.load(config_file)
        assert loaded_config.ui.window_width == 1600
        assert loaded_config.processing.chunk_size == 20

    def test_config_default_path(self):
        """测试默认配置路径"""
        default_path = AppConfig.get_default_config_path()
        assert isinstance(default_path, Path)
        assert default_path.name == "config.yaml"

    def test_config_with_nonexistent_file(self, temp_dir):
        """测试不存在文件的配置加载"""
        nonexistent_file = temp_dir / "nonexistent.yaml"

        # 加载不存在的文件应该返回默认配置
        config = AppConfig.load(nonexistent_file)
        assert config is not None
        assert isinstance(config, AppConfig)

    def test_config_helper_methods(self):
        """测试配置辅助方法"""
        config = AppConfig.default()

        # 获取处理器配置
        processing_config = config.get_processing_config()
        assert isinstance(processing_config, dict)
        assert "chunk_size" in processing_config
        assert "max_workers" in processing_config

        # 获取UI配置
        ui_config = config.get_ui_config()
        assert isinstance(ui_config, dict)
        assert "default_remove_dupes" in ui_config
        assert "default_anonymize_ips" in ui_config
        assert "default_mask_payloads" in ui_config
        assert "theme" in ui_config


class TestConfigurationEdgeCases:
    """配置边界情况测试"""

    def test_invalid_config_data(self, temp_dir):
        """测试无效配置数据处理"""
        config_file = temp_dir / "invalid_config.yaml"

        # 写入无效的YAML
        config_file.write_text("invalid: yaml: content: [")

        # 加载应该返回默认配置
        config = AppConfig.load(config_file)
        assert config is not None
        assert isinstance(config, AppConfig)

    def test_partial_config_data(self, temp_dir):
        """测试部分配置数据"""
        config_file = temp_dir / "partial_config.yaml"

        # 写入部分配置
        partial_data = {"ui": {"window_width": 1600}, "processing": {"chunk_size": 20}}

        import yaml

        with open(config_file, "w") as f:
            yaml.dump(partial_data, f)

        # 加载应该合并默认配置
        config = AppConfig.load(config_file)
        assert config.ui.window_width == 1600
        assert config.processing.chunk_size == 20
        # 其他值应该是默认值
        assert config.ui.window_height == 800  # 默认值
        assert config.processing.max_workers == 4  # 默认值

    def test_config_update_directories(self):
        """测试目录更新功能"""
        config = AppConfig.default()

        # 更新目录
        config.update_last_directories(
            input_dir="/test/input", output_dir="/test/output"
        )

        assert config.ui.last_input_dir == "/test/input"
        assert config.ui.last_output_dir == "/test/output"


@pytest.mark.unit
class TestConfigurationDefaults:
    """配置默认值详细测试"""

    def test_default_values_are_reasonable(self):
        """测试默认值是合理的"""
        config = AppConfig.default()

        # UI默认值检查
        assert config.ui.window_width >= 800
        assert config.ui.window_height >= 600
        assert config.ui.theme in ["auto", "light", "dark"]

        # 处理默认值检查
        assert config.processing.chunk_size > 0
        assert config.processing.max_workers > 0
        assert config.processing.timeout_seconds > 0
        assert config.processing.dedup_algorithm in ["md5", "sha1", "sha256"]

        # 日志默认值检查
        assert config.logging.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]
        assert config.logging.log_file_max_size > 0

    def test_configs_are_consistent(self):
        """测试配置的一致性"""
        config1 = AppConfig.default()
        config2 = AppConfig.default()

        # 两个新创建的配置对象应该有相同的默认值
        assert config1.ui.window_width == config2.ui.window_width
        assert config1.processing.chunk_size == config2.processing.chunk_size
        assert config1.logging.log_level == config2.logging.log_level
