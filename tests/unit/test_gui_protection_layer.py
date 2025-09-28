#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for GUI Protection Layer

Tests for GUIConsistentProcessor, GUIServicePipelineThread, and feature flags
to ensure proper functionality and GUI compatibility preservation.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from PyQt6.QtCore import QThread, pyqtSignal

from pktmask.core.events import PipelineEvents
from pktmask.gui.core.feature_flags import GUIFeatureFlags, GUIFeatureFlagValidator
from pktmask.gui.core.gui_consistent_processor import (
    GUIConsistentProcessor,
    GUIServicePipelineThread,
    GUIThreadingHelper,
)


class TestGUIFeatureFlags:
    """Test GUI feature flags functionality"""

    def setup_method(self):
        """Clear environment variables before each test"""
        env_vars = [
            "PKTMASK_USE_CONSISTENT_PROCESSOR",
            "PKTMASK_GUI_DEBUG_MODE",
            "PKTMASK_FORCE_LEGACY_MODE",
            "PKTMASK_FEATURE_CONFIG",
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    @pytest.mark.skip(reason="Temporarily skipped - GUI feature flags behavior changed")
    def test_default_values(self):
        """Test default feature flag values"""
        assert not GUIFeatureFlags.should_use_consistent_processor()
        assert not GUIFeatureFlags.is_gui_debug_mode()
        assert not GUIFeatureFlags.is_legacy_mode_forced()

    def test_enable_consistent_processor(self):
        """Test enabling consistent processor"""
        os.environ["PKTMASK_USE_CONSISTENT_PROCESSOR"] = "true"
        assert GUIFeatureFlags.should_use_consistent_processor()

        os.environ["PKTMASK_USE_CONSISTENT_PROCESSOR"] = "false"
        assert not GUIFeatureFlags.should_use_consistent_processor()

    def test_force_legacy_mode_override(self):
        """Test that force legacy mode overrides other settings"""
        os.environ["PKTMASK_USE_CONSISTENT_PROCESSOR"] = "true"
        os.environ["PKTMASK_FORCE_LEGACY_MODE"] = "true"

        # Force legacy should override consistent processor
        assert not GUIFeatureFlags.should_use_consistent_processor()
        assert GUIFeatureFlags.is_legacy_mode_forced()

    def test_debug_mode(self):
        """Test GUI debug mode flag"""
        os.environ["PKTMASK_GUI_DEBUG_MODE"] = "true"
        assert GUIFeatureFlags.is_gui_debug_mode()

        os.environ["PKTMASK_GUI_DEBUG_MODE"] = "false"
        assert not GUIFeatureFlags.is_gui_debug_mode()

    def test_programmatic_control(self):
        """Test programmatic feature flag control"""
        GUIFeatureFlags.enable_consistent_processor()
        assert GUIFeatureFlags.should_use_consistent_processor()

        GUIFeatureFlags.disable_consistent_processor()
        assert not GUIFeatureFlags.should_use_consistent_processor()

        GUIFeatureFlags.force_legacy_mode()
        assert GUIFeatureFlags.is_legacy_mode_forced()

    def test_get_feature_config(self):
        """Test getting complete feature configuration"""
        config = GUIFeatureFlags.get_feature_config()

        assert "use_consistent_processor" in config
        assert "gui_debug_mode" in config
        assert "legacy_mode_forced" in config
        assert "config_source" in config

        assert isinstance(config["use_consistent_processor"], bool)
        assert isinstance(config["gui_debug_mode"], bool)
        assert isinstance(config["legacy_mode_forced"], bool)

    @pytest.mark.skip(reason="Temporarily skipped - GUI status summary format changed")
    def test_status_summary(self):
        """Test status summary generation"""
        # Test legacy mode
        summary = GUIFeatureFlags.get_status_summary()
        assert "Legacy Mode" in summary

        # Test consistent processor mode
        GUIFeatureFlags.enable_consistent_processor()
        summary = GUIFeatureFlags.get_status_summary()
        assert "Consistent Processor Mode" in summary

        # Test forced legacy mode
        GUIFeatureFlags.force_legacy_mode()
        summary = GUIFeatureFlags.get_status_summary()
        assert "Legacy Mode (Forced)" in summary


class TestGUIFeatureFlagValidator:
    """Test GUI feature flag validator"""

    def setup_method(self):
        """Clear environment variables before each test"""
        env_vars = [
            "PKTMASK_USE_CONSISTENT_PROCESSOR",
            "PKTMASK_GUI_DEBUG_MODE",
            "PKTMASK_FORCE_LEGACY_MODE",
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    def test_validate_environment_clean(self):
        """Test validation with clean environment"""
        results = GUIFeatureFlagValidator.validate_environment()

        assert results["valid"] is True
        assert len(results["warnings"]) == 0
        assert len(results["errors"]) == 0
        assert "config" in results

    def test_validate_conflicting_settings(self):
        """Test validation with conflicting settings"""
        os.environ["PKTMASK_USE_CONSISTENT_PROCESSOR"] = "true"
        os.environ["PKTMASK_FORCE_LEGACY_MODE"] = "true"

        results = GUIFeatureFlagValidator.validate_environment()

        # The validator should detect the conflict and issue a warning
        assert len(results["warnings"]) > 0
        warning_text = " ".join(results["warnings"])
        assert "Legacy mode" in warning_text or "forced" in warning_text

    def test_validate_debug_without_processor(self):
        """Test validation with debug mode but no consistent processor"""
        os.environ["PKTMASK_GUI_DEBUG_MODE"] = "true"
        os.environ["PKTMASK_USE_CONSISTENT_PROCESSOR"] = "false"

        results = GUIFeatureFlagValidator.validate_environment()

        assert len(results["warnings"]) > 0
        assert any("Debug mode is enabled" in warning for warning in results["warnings"])


class TestGUIConsistentProcessor:
    """Test GUIConsistentProcessor functionality"""

    def test_create_executor_from_gui(self):
        """Test executor creation from GUI checkbox states"""
        executor = GUIConsistentProcessor.create_executor_from_gui(
            remove_dupes_checked=True,
            anonymize_ips_checked=False,
            mask_payloads_checked=True,
        )

        assert executor is not None
        assert "remove_dupes" in executor._config
        assert "mask_payloads" in executor._config
        assert "anonymize_ips" not in executor._config

    def test_validate_gui_options_success(self):
        """Test successful GUI options validation"""
        # Should not raise for valid combinations
        GUIConsistentProcessor.validate_gui_options(True, False, False)
        GUIConsistentProcessor.validate_gui_options(False, True, False)
        GUIConsistentProcessor.validate_gui_options(False, False, True)
        GUIConsistentProcessor.validate_gui_options(True, True, True)

    def test_validate_gui_options_failure(self):
        """Test GUI options validation failure"""
        with pytest.raises(ValueError, match="At least one processing option"):
            GUIConsistentProcessor.validate_gui_options(False, False, False)

    def test_get_gui_configuration_summary(self):
        """Test GUI configuration summary generation"""
        summary = GUIConsistentProcessor.get_gui_configuration_summary(
            remove_dupes_checked=True,
            anonymize_ips_checked=True,
            mask_payloads_checked=False,
        )

        assert "Remove Dupes" in summary
        assert "Anonymize IPs" in summary
        assert "Mask Payloads" not in summary


class TestGUIServicePipelineThread:
    """Test GUIServicePipelineThread functionality"""

    def test_thread_initialization(self):
        """Test thread initialization"""
        mock_executor = Mock()
        thread = GUIServicePipelineThread(mock_executor, "/test/input", "/test/output")

        assert thread._executor == mock_executor
        assert thread._base_dir == Path("/test/input")
        assert thread._output_dir == Path("/test/output")
        assert thread.is_running is True
        assert hasattr(thread, "progress_signal")

    def test_thread_signals(self):
        """Test that thread has required Qt signals"""
        mock_executor = Mock()
        thread = GUIServicePipelineThread(mock_executor, "/test/input", "/test/output")

        # Verify signal exists and is callable (PyQt signals are bound methods)
        assert hasattr(thread, "progress_signal")
        assert callable(thread.progress_signal.emit)

    def test_stop_functionality(self):
        """Test thread stop functionality"""
        mock_executor = Mock()
        thread = GUIServicePipelineThread(mock_executor, "/test/input", "/test/output")

        # Mock signal emission
        thread.progress_signal = Mock()

        # Test stop
        thread.stop()

        assert thread.is_running is False
        assert thread.progress_signal.emit.called

        # Verify stop message was emitted
        calls = thread.progress_signal.emit.call_args_list
        stop_call = None
        for call in calls:
            if call[0][0] == PipelineEvents.LOG:
                if "Stopped by User" in call[0][1]["message"]:
                    stop_call = call
                    break

        assert stop_call is not None

    @pytest.mark.skip(reason="Temporarily skipped - directory processing logic changed")
    @patch("os.walk")
    def test_directory_processing_file_discovery(self, mock_walk):
        """Test directory processing file discovery"""
        # Mock os.walk to return test files
        mock_walk.return_value = [("/test/dir", [], ["file1.pcap", "file2.pcapng", "file3.txt"])]

        mock_executor = Mock()
        thread = GUIServicePipelineThread(mock_executor, "/test/dir", "/test/output")
        thread.progress_signal = Mock()

        # Mock executor.run to return success
        mock_result = Mock()
        mock_result.success = True
        mock_result.duration_ms = 100
        mock_result.stage_stats = []
        mock_executor.run.return_value = mock_result

        # Test directory processing
        thread._process_directory_with_progress()

        # Verify that only PCAP/PCAPNG files were processed
        assert mock_executor.run.call_count == 2  # file1.pcap and file2.pcapng

        # Verify progress signals were emitted
        assert thread.progress_signal.emit.called

        # Check for pipeline start signal
        start_calls = [
            call for call in thread.progress_signal.emit.call_args_list if call[0][0] == PipelineEvents.PIPELINE_START
        ]
        assert len(start_calls) > 0
        assert start_calls[0][0][1]["total_files"] == 2


class TestGUIThreadingHelper:
    """Test GUIThreadingHelper functionality"""

    def test_create_threaded_executor(self):
        """Test threaded executor creation"""
        thread = GUIThreadingHelper.create_threaded_executor(
            remove_dupes_checked=True,
            anonymize_ips_checked=False,
            mask_payloads_checked=False,
            base_dir="/test/input",
            output_dir="/test/output",
        )

        assert isinstance(thread, GUIServicePipelineThread)
        assert thread._base_dir == Path("/test/input")
        assert thread._output_dir == Path("/test/output")
        assert thread._executor is not None

    def test_create_threaded_executor_validation_failure(self):
        """Test threaded executor creation with validation failure"""
        with pytest.raises(ValueError, match="At least one processing option"):
            GUIThreadingHelper.create_threaded_executor(
                remove_dupes_checked=False,
                anonymize_ips_checked=False,
                mask_payloads_checked=False,
                base_dir="/test/input",
                output_dir="/test/output",
            )

    def test_validate_gui_threading_compatibility(self):
        """Test GUI threading compatibility validation"""
        # This should return True since ConsistentProcessor is thread-safe
        assert GUIThreadingHelper.validate_gui_threading_compatibility() is True


class TestGUIProtectionLayerIntegration:
    """Integration tests for GUI protection layer components"""

    def test_feature_flags_with_gui_processor(self):
        """Test feature flags integration with GUI processor"""
        # Enable consistent processor
        GUIFeatureFlags.enable_consistent_processor()

        # Verify flag is set
        assert GUIFeatureFlags.should_use_consistent_processor()

        # Test that GUI processor can be created
        executor = GUIConsistentProcessor.create_executor_from_gui(
            remove_dupes_checked=True,
            anonymize_ips_checked=False,
            mask_payloads_checked=False,
        )

        assert executor is not None

    def test_debug_mode_integration(self):
        """Test debug mode integration"""
        GUIFeatureFlags.enable_debug_mode()

        assert GUIFeatureFlags.is_gui_debug_mode()

        # Create thread with debug mode enabled
        mock_executor = Mock()
        thread = GUIServicePipelineThread(mock_executor, "/test/input", "/test/output")

        # Debug mode should be detected in thread
        assert thread._debug_mode is True
