#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Integration tests for GUI-CLI consistency

Tests to verify that GUI and CLI produce identical results and that
the feature flag system works correctly for safe rollout.
"""

import os
from unittest.mock import Mock, patch

import pytest

from pktmask.core.consistency import ConsistentProcessor
from pktmask.gui.core.feature_flags import GUIFeatureFlags
from pktmask.gui.core.gui_consistent_processor import (
    GUIConsistentProcessor,
    GUIThreadingHelper,
)


class TestGUICliConsistency:
    """Test GUI-CLI consistency implementation"""

    def setup_method(self):
        """Reset feature flags before each test"""
        # Clear environment variables
        env_vars = [
            "PKTMASK_USE_CONSISTENT_PROCESSOR",
            "PKTMASK_GUI_DEBUG_MODE",
            "PKTMASK_FORCE_LEGACY_MODE",
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    def test_feature_flag_defaults(self):
        """Test default feature flag values"""
        # Default should be normal mode
        assert not GUIFeatureFlags.is_gui_debug_mode()

        # Status should reflect defaults
        status = GUIFeatureFlags.get_status_summary()
        assert "Normal Mode" in status or "normal" in status.lower()

    def test_feature_flag_debug_mode(self):
        """Test enabling debug mode via environment variable"""
        os.environ["PKTMASK_GUI_DEBUG_MODE"] = "true"

        assert GUIFeatureFlags.is_gui_debug_mode()

        status = GUIFeatureFlags.get_status_summary()
        assert "Debug Mode" in status or "debug" in status.lower()

    def test_gui_consistent_processor_compatibility(self):
        """Test that GUI wrapper produces same config as CLI"""
        # Test with dedup only
        gui_executor = GUIConsistentProcessor.create_executor_from_gui(
            remove_dupes_checked=True,
            anonymize_ips_checked=False,
            mask_payloads_checked=False,
        )

        cli_executor = ConsistentProcessor.create_executor(dedup=True, anon=False, mask=False)

        # Both should have same configuration structure
        assert "remove_dupes" in gui_executor._config
        assert "remove_dupes" in cli_executor._config
        assert gui_executor._config["remove_dupes"]["enabled"] == cli_executor._config["remove_dupes"]["enabled"]

        # Test with all options
        gui_executor_all = GUIConsistentProcessor.create_executor_from_gui(
            remove_dupes_checked=True,
            anonymize_ips_checked=True,
            mask_payloads_checked=True,
        )

        cli_executor_all = ConsistentProcessor.create_executor(dedup=True, anon=True, mask=True)

        # Should have same stages enabled
        gui_stages = set(gui_executor_all._config.keys())
        cli_stages = set(cli_executor_all._config.keys())
        assert gui_stages == cli_stages

    def test_gui_validation_consistency(self):
        """Test that GUI validation matches CLI validation"""
        # Test successful validation
        try:
            GUIConsistentProcessor.validate_gui_options(True, False, False)
            ConsistentProcessor.validate_options(True, False, False)
            # Both should succeed
        except Exception as e:
            pytest.fail(f"Validation should succeed: {e}")

        # Test validation failure
        with pytest.raises(ValueError):
            GUIConsistentProcessor.validate_gui_options(False, False, False)

        with pytest.raises(ValueError):
            ConsistentProcessor.validate_options(False, False, False)

    def test_gui_configuration_summary_consistency(self):
        """Test that GUI and CLI produce same configuration summaries"""
        gui_summary = GUIConsistentProcessor.get_gui_configuration_summary(
            remove_dupes_checked=True,
            anonymize_ips_checked=True,
            mask_payloads_checked=False,
        )

        cli_summary = ConsistentProcessor.get_configuration_summary(dedup=True, anon=True, mask=False)

        # Should contain same enabled options
        assert "Remove Dupes" in gui_summary
        assert "Anonymize IPs" in gui_summary
        assert "Remove Dupes" in cli_summary
        assert "Anonymize IPs" in cli_summary

        # Should not contain disabled option
        assert "Mask Payloads" not in gui_summary
        assert "Mask Payloads" not in cli_summary

    def test_gui_threading_helper_creation(self):
        """Test GUI threading helper creates proper thread"""
        thread = GUIThreadingHelper.create_threaded_executor(
            remove_dupes_checked=True,
            anonymize_ips_checked=False,
            mask_payloads_checked=False,
            base_dir="/tmp",
            output_dir="/tmp",
        )

        # Should be proper Qt thread with required attributes
        assert hasattr(thread, "progress_signal")
        assert hasattr(thread, "start")
        assert hasattr(thread, "stop")
        assert hasattr(thread, "is_running")
        assert thread.is_running is True

    def test_gui_threading_helper_validation_failure(self):
        """Test GUI threading helper validation"""
        with pytest.raises(ValueError, match="At least one processing option"):
            GUIThreadingHelper.create_threaded_executor(
                remove_dupes_checked=False,
                anonymize_ips_checked=False,
                mask_payloads_checked=False,
                base_dir="/tmp",
                output_dir="/tmp",
            )

    @pytest.mark.skip(reason="Mock setup needs refinement after refactoring")
    @patch("os.scandir")
    @patch("os.walk")
    def test_gui_thread_signal_emission(self, mock_walk, mock_scandir):
        """Test that GUI thread emits proper signals"""
        # Mock file discovery
        mock_walk.return_value = [("/test", [], ["test.pcap"])]
        mock_scandir.return_value = []  # Empty directory

        # Create thread
        thread = GUIThreadingHelper.create_threaded_executor(
            remove_dupes_checked=True,
            anonymize_ips_checked=False,
            mask_payloads_checked=False,
            base_dir="/test",
            output_dir="/test/output",
        )

        # Mock signal emission
        thread.progress_signal = Mock()

        # Mock executor run method
        mock_result = Mock()
        mock_result.success = True
        mock_result.duration_ms = 100
        mock_result.stage_stats = []
        thread._executor.run = Mock(return_value=mock_result)

        # Test directory processing
        thread._process_directory_with_progress()

        # Verify signals were emitted
        assert thread.progress_signal.emit.called

        # Check for required signal types
        emitted_events = [call[0][0] for call in thread.progress_signal.emit.call_args_list]
        from pktmask.core.events import PipelineEvents

        assert PipelineEvents.PIPELINE_START in emitted_events
        assert PipelineEvents.PIPELINE_END in emitted_events

    def test_gui_thread_stop_functionality(self):
        """Test GUI thread stop functionality"""
        thread = GUIThreadingHelper.create_threaded_executor(
            remove_dupes_checked=True,
            anonymize_ips_checked=False,
            mask_payloads_checked=False,
            base_dir="/tmp",
            output_dir="/tmp",
        )

        # Mock signal
        thread.progress_signal = Mock()

        # Test stop
        thread.stop()

        assert thread.is_running is False
        assert thread.progress_signal.emit.called

        # Verify stop message was emitted
        calls = thread.progress_signal.emit.call_args_list
        stop_messages = []
        for call in calls:
            if len(call[0]) > 1 and isinstance(call[0][1], dict) and "message" in call[0][1]:
                if "Stopped by User" in call[0][1]["message"]:
                    stop_messages.append(call)

        assert len(stop_messages) > 0
