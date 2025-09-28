#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for core consistency layer

Tests for ConsistentProcessor, StandardMessages, and unified configuration
to ensure proper functionality and consistency across GUI and CLI interfaces.
"""

import tempfile
from pathlib import Path

import pytest

from pktmask.core.config import ConfigConverter, ConfigValidator, UnifiedConfig
from pktmask.core.consistency import (
    ConfigurationError,
    ConsistentProcessor,
    ProcessingError,
)
from pktmask.core.messages import MessageFormatter, StandardMessages


class TestConsistentProcessor:
    """Test ConsistentProcessor functionality"""

    def test_validate_options_success(self):
        """Test successful option validation"""
        # Should not raise for valid combinations
        ConsistentProcessor.validate_options(True, False, False)
        ConsistentProcessor.validate_options(False, True, False)
        ConsistentProcessor.validate_options(False, False, True)
        ConsistentProcessor.validate_options(True, True, True)

    def test_validate_options_failure(self):
        """Test option validation failure"""
        with pytest.raises(ValueError, match="At least one processing option"):
            ConsistentProcessor.validate_options(False, False, False)

    def test_create_executor_dedup_only(self):
        """Test executor creation with dedup only"""
        executor = ConsistentProcessor.create_executor(True, False, False)
        assert executor is not None
        assert "remove_dupes" in executor._config
        assert executor._config["remove_dupes"]["enabled"] is True
        assert "anonymize_ips" not in executor._config
        assert "mask_payloads" not in executor._config

    def test_create_executor_anon_only(self):
        """Test executor creation with anon only"""
        executor = ConsistentProcessor.create_executor(False, True, False)
        assert executor is not None
        assert "anonymize_ips" in executor._config
        assert executor._config["anonymize_ips"]["enabled"] is True
        assert "remove_dupes" not in executor._config
        assert "mask_payloads" not in executor._config

    def test_create_executor_mask_only(self):
        """Test executor creation with mask only"""
        executor = ConsistentProcessor.create_executor(False, False, True)
        assert executor is not None
        assert "mask_payloads" in executor._config
        assert executor._config["mask_payloads"]["enabled"] is True
        assert executor._config["mask_payloads"]["protocol"] == "auto"
        assert "remove_dupes" not in executor._config
        assert "anonymize_ips" not in executor._config

    def test_create_executor_all_options(self):
        """Test executor creation with all options"""
        executor = ConsistentProcessor.create_executor(True, True, True)
        assert executor is not None
        assert "remove_dupes" in executor._config
        assert "anonymize_ips" in executor._config
        assert "mask_payloads" in executor._config
        assert executor._config["remove_dupes"]["enabled"] is True
        assert executor._config["anonymize_ips"]["enabled"] is True
        assert executor._config["mask_payloads"]["enabled"] is True

    def test_create_executor_no_options(self):
        """Test executor creation with no options fails"""
        with pytest.raises(ValueError, match="At least one processing option"):
            ConsistentProcessor.create_executor(False, False, False)

    def test_get_configuration_summary(self):
        """Test configuration summary generation"""
        # Test individual options
        assert "Remove Dupes" in ConsistentProcessor.get_configuration_summary(True, False, False)
        assert "Anonymize IPs" in ConsistentProcessor.get_configuration_summary(False, True, False)
        assert "Mask Payloads" in ConsistentProcessor.get_configuration_summary(False, False, True)

        # Test multiple options
        summary = ConsistentProcessor.get_configuration_summary(True, True, False)
        assert "Remove Dupes" in summary
        assert "Anonymize IPs" in summary
        assert "Mask Payloads" not in summary

        # Test no options
        summary = ConsistentProcessor.get_configuration_summary(False, False, False)
        assert "No processing options enabled" in summary

    def test_validate_input_path_file_exists(self):
        """Test input path validation for existing file"""
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            try:
                # Should not raise for valid PCAP file
                ConsistentProcessor.validate_input_path(tmp_path)
            finally:
                tmp_path.unlink()

    def test_validate_input_path_file_not_exists(self):
        """Test input path validation for non-existent file"""
        non_existent = Path("/non/existent/file.pcap")
        with pytest.raises(FileNotFoundError):
            ConsistentProcessor.validate_input_path(non_existent)

    def test_validate_input_path_invalid_extension(self):
        """Test input path validation for invalid file extension"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            try:
                with pytest.raises(ValueError, match="PCAP or PCAPNG"):
                    ConsistentProcessor.validate_input_path(tmp_path)
            finally:
                tmp_path.unlink()

    def test_generate_output_path_file(self):
        """Test output path generation for file"""
        input_path = Path("/test/input.pcap")
        output_path = ConsistentProcessor.generate_output_path(input_path)
        assert output_path == Path("/test/input_processed.pcap")

        # Test custom suffix
        output_path = ConsistentProcessor.generate_output_path(input_path, "_custom")
        assert output_path == Path("/test/input_custom.pcap")

    def test_generate_output_path_directory(self):
        """Test output path generation for directory"""
        input_path = Path("/test/input_dir")
        output_path = ConsistentProcessor.generate_output_path(input_path)
        assert output_path == Path("/test/input_dir_processed")


class TestStandardMessages:
    """Test StandardMessages functionality"""

    def test_error_messages_defined(self):
        """Test that all error messages are defined"""
        assert hasattr(StandardMessages, "NO_OPTIONS_SELECTED")
        assert hasattr(StandardMessages, "INPUT_NOT_FOUND")
        assert hasattr(StandardMessages, "INVALID_FILE_TYPE")
        assert StandardMessages.NO_OPTIONS_SELECTED != ""
        assert StandardMessages.INPUT_NOT_FOUND != ""
        assert StandardMessages.INVALID_FILE_TYPE != ""

    def test_progress_messages_defined(self):
        """Test that all progress messages are defined"""
        assert hasattr(StandardMessages, "PROCESSING_START")
        assert hasattr(StandardMessages, "PROCESSING_COMPLETE")
        assert hasattr(StandardMessages, "PROCESSING_FAILED")
        assert StandardMessages.PROCESSING_START != ""
        assert StandardMessages.PROCESSING_COMPLETE != ""
        assert StandardMessages.PROCESSING_FAILED != ""

    def test_status_icons_defined(self):
        """Test that all status icons are defined"""
        assert hasattr(StandardMessages, "SUCCESS_ICON")
        assert hasattr(StandardMessages, "ERROR_ICON")
        assert hasattr(StandardMessages, "WARNING_ICON")
        assert StandardMessages.SUCCESS_ICON != ""
        assert StandardMessages.ERROR_ICON != ""
        assert StandardMessages.WARNING_ICON != ""

    def test_format_stage_progress(self):
        """Test stage progress formatting"""
        result = StandardMessages.format_stage_progress("dedup", 1000, 50)
        assert "dedup" in result
        assert "1,000" in result
        assert "50" in result
        assert StandardMessages.PROCESSING_ICON in result

    def test_format_file_progress(self):
        """Test file progress formatting"""
        result = StandardMessages.format_file_progress("test.pcap", 1, 5)
        assert "test.pcap" in result
        assert "[1/5]" in result

    def test_format_configuration_summary(self):
        """Test configuration summary formatting"""
        # Test all enabled
        config_lines = StandardMessages.format_configuration_summary(True, True, True)
        assert len(config_lines) == 3
        assert any("Remove Dupes: Enabled" in line for line in config_lines)
        assert any("Anonymize IPs: Enabled" in line for line in config_lines)
        assert any("Mask Payloads: Enabled" in line for line in config_lines)

        # Test all disabled
        config_lines = StandardMessages.format_configuration_summary(False, False, False)
        assert len(config_lines) == 3
        assert any("Remove Dupes: Disabled" in line for line in config_lines)
        assert any("Anonymize IPs: Disabled" in line for line in config_lines)
        assert any("Mask Payloads: Disabled" in line for line in config_lines)

    def test_format_error_with_context(self):
        """Test error formatting with context"""
        result = StandardMessages.format_error_with_context("Test error", "Test context")
        assert StandardMessages.ERROR_ICON in result
        assert "Test error" in result
        assert "Test context" in result

        # Test without context
        result = StandardMessages.format_error_with_context("Test error")
        assert StandardMessages.ERROR_ICON in result
        assert "Test error" in result
        assert "Context:" not in result


class TestMessageFormatter:
    """Test MessageFormatter functionality"""

    def test_format_duration_milliseconds(self):
        """Test duration formatting for milliseconds"""
        result = MessageFormatter.format_duration(500)
        assert "500ms" in result

    def test_format_duration_seconds(self):
        """Test duration formatting for seconds"""
        result = MessageFormatter.format_duration(2500)
        assert "2.5s" in result

    def test_format_duration_minutes(self):
        """Test duration formatting for minutes"""
        result = MessageFormatter.format_duration(125000)  # 2m 5s
        assert "2m" in result
        assert "5.0s" in result

    def test_format_file_size(self):
        """Test file size formatting"""
        assert "1.0 KB" in MessageFormatter.format_file_size(1024)
        assert "1.0 MB" in MessageFormatter.format_file_size(1024 * 1024)
        assert "1.0 GB" in MessageFormatter.format_file_size(1024 * 1024 * 1024)

    def test_format_percentage(self):
        """Test percentage formatting"""
        assert "50.0%" == MessageFormatter.format_percentage(50, 100)
        assert "0.0%" == MessageFormatter.format_percentage(0, 100)
        assert "0.0%" == MessageFormatter.format_percentage(10, 0)  # Edge case


class TestUnifiedConfig:
    """Test UnifiedConfig functionality"""

    def test_default_config(self):
        """Test default configuration"""
        config = UnifiedConfig()
        assert config.dedup is False
        assert config.anon is False
        assert config.mask is False
        assert config.mask_protocol == "tls"
        assert config.preserve_handshake is True

    def test_has_any_processing_enabled(self):
        """Test processing enabled check"""
        config = UnifiedConfig()
        assert not config.has_any_processing_enabled()

        config.dedup = True
        assert config.has_any_processing_enabled()

    def test_get_enabled_options(self):
        """Test getting enabled options"""
        config = UnifiedConfig(dedup=True, mask=True)
        enabled = config.get_enabled_options()
        assert "dedup" in enabled
        assert "mask" in enabled
        assert "anon" not in enabled

    def test_to_pipeline_config(self):
        """Test conversion to pipeline config"""
        config = UnifiedConfig(dedup=True, anon=True)
        pipeline_config = config.to_pipeline_config()

        assert "remove_dupes" in pipeline_config
        assert "anonymize_ips" in pipeline_config
        assert "mask_payloads" not in pipeline_config
        assert pipeline_config["remove_dupes"]["enabled"] is True
        assert pipeline_config["anonymize_ips"]["enabled"] is True

    def test_get_summary(self):
        """Test configuration summary"""
        config = UnifiedConfig()
        assert "No processing options enabled" in config.get_summary()

        config.dedup = True
        config.anon = True
        summary = config.get_summary()
        assert "dedup" in summary
        assert "anon" in summary


class TestConfigValidator:
    """Test ConfigValidator functionality"""

    def test_validate_config_success(self):
        """Test successful config validation"""
        config = UnifiedConfig(dedup=True)
        errors = ConfigValidator.validate_config(config)
        assert len(errors) == 0

    def test_validate_config_no_options(self):
        """Test config validation with no options"""
        config = UnifiedConfig()
        errors = ConfigValidator.validate_config(config)
        assert len(errors) > 0
        assert any("At least one processing option" in error for error in errors)

    def test_validate_processing_options_success(self):
        """Test successful processing options validation"""
        # Should not raise
        ConfigValidator.validate_processing_options(True, False, False)

    def test_validate_processing_options_failure(self):
        """Test processing options validation failure"""
        with pytest.raises(ValueError, match="At least one processing option"):
            ConfigValidator.validate_processing_options(False, False, False)


class TestConfigConverter:
    """Test ConfigConverter functionality"""

    def test_from_gui_checkboxes(self):
        """Test conversion from GUI checkboxes"""
        config = ConfigConverter.from_gui_checkboxes(True, False, True)
        assert config.dedup is True
        assert config.anon is False
        assert config.mask is True

    def test_from_cli_args(self):
        """Test conversion from CLI args"""
        input_path = Path("/test/input.pcap")
        config = ConfigConverter.from_cli_args(dedup=True, anon=True, mask=False, input_path=input_path, verbose=True)
        assert config.dedup is True
        assert config.anon is True
        assert config.mask is False
        assert config.input_path == input_path
        assert config.verbose is True

    def test_to_legacy_gui_format(self):
        """Test conversion to legacy GUI format"""
        config = UnifiedConfig(dedup=True, anon=False, mask=True)
        legacy = ConfigConverter.to_legacy_gui_format(config)

        assert legacy["remove_dupes_checked"] is True
        assert legacy["anonymize_ips_checked"] is False
        assert legacy["mask_payloads_checked"] is True

    def test_to_legacy_cli_format(self):
        """Test conversion to legacy CLI format"""
        config = UnifiedConfig(dedup=True, anon=True, mask=False, verbose=True)
        legacy = ConfigConverter.to_legacy_cli_format(config)

        assert legacy["remove_dupes"] is True
        assert legacy["anonymize_ips"] is True
        assert legacy["mask_payloads"] is False
        assert legacy["verbose"] is True
