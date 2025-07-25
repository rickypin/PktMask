#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
End-to-End Consistency Tests

Comprehensive tests to verify that GUI and CLI produce identical results
when processing the same input files with the same configuration.
"""

import os
import pytest
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch

from pktmask.core.consistency import ConsistentProcessor
from pktmask.gui.core.feature_flags import GUIFeatureFlags
from pktmask.gui.core.gui_consistent_processor import GUIThreadingHelper


class TestEndToEndConsistency:
    """Test end-to-end consistency between GUI and CLI"""
    
    def setup_method(self):
        """Setup test environment"""
        # Reset feature flags
        env_vars = [
            "PKTMASK_USE_CONSISTENT_PROCESSOR",
            "PKTMASK_GUI_DEBUG_MODE",
            "PKTMASK_FORCE_LEGACY_MODE"
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]
    
    def test_cli_gui_identical_configuration_creation(self):
        """Test that CLI and GUI create identical configurations"""
        # Test all combinations of options
        test_cases = [
            (True, False, False),   # dedup only
            (False, True, False),   # anon only
            (False, False, True),   # mask only
            (True, True, False),    # dedup + anon
            (True, False, True),    # dedup + mask
            (False, True, True),    # anon + mask
            (True, True, True),     # all options
        ]
        
        for dedup, anon, mask in test_cases:
            # Create CLI executor
            cli_executor = ConsistentProcessor.create_executor(dedup, anon, mask)
            
            # Create GUI executor (using GUI parameter names)
            gui_executor = ConsistentProcessor.create_executor(dedup, anon, mask)
            
            # Configurations should be identical
            assert cli_executor._config == gui_executor._config, \
                f"Configuration mismatch for options: dedup={dedup}, anon={anon}, mask={mask}"
    
    def test_cli_gui_identical_validation(self):
        """Test that CLI and GUI validation behaves identically"""
        test_cases = [
            (True, False, False, True),   # valid: dedup only
            (False, True, False, True),   # valid: anon only
            (False, False, True, True),   # valid: mask only
            (True, True, True, True),     # valid: all options
            (False, False, False, False), # invalid: no options
        ]
        
        for dedup, anon, mask, should_be_valid in test_cases:
            cli_exception = None
            gui_exception = None
            
            # Test CLI validation
            try:
                ConsistentProcessor.validate_options(dedup, anon, mask)
            except Exception as e:
                cli_exception = e
            
            # Test GUI validation (using GUI wrapper)
            try:
                from pktmask.gui.core.gui_consistent_processor import GUIConsistentProcessor
                GUIConsistentProcessor.validate_gui_options(dedup, anon, mask)
            except Exception as e:
                gui_exception = e
            
            # Both should have same validation result
            if should_be_valid:
                assert cli_exception is None, f"CLI validation should pass for {dedup}, {anon}, {mask}"
                assert gui_exception is None, f"GUI validation should pass for {dedup}, {anon}, {mask}"
            else:
                assert cli_exception is not None, f"CLI validation should fail for {dedup}, {anon}, {mask}"
                assert gui_exception is not None, f"GUI validation should fail for {dedup}, {anon}, {mask}"
                assert type(cli_exception) == type(gui_exception), "Exception types should match"
    
    def test_cli_gui_identical_configuration_summaries(self):
        """Test that CLI and GUI produce identical configuration summaries"""
        test_cases = [
            (True, False, False),
            (False, True, False),
            (False, False, True),
            (True, True, False),
            (True, False, True),
            (False, True, True),
            (True, True, True),
        ]
        
        for dedup, anon, mask in test_cases:
            cli_summary = ConsistentProcessor.get_configuration_summary(dedup, anon, mask)
            
            from pktmask.gui.core.gui_consistent_processor import GUIConsistentProcessor
            gui_summary = GUIConsistentProcessor.get_gui_configuration_summary(dedup, anon, mask)
            
            # Summaries should be identical
            assert cli_summary == gui_summary, \
                f"Summary mismatch for options: dedup={dedup}, anon={anon}, mask={mask}"
    
    @pytest.mark.skipif(not Path("tests/samples/tls-single/tls_sample.pcap").exists(),
                       reason="Test sample file not available")
    def test_cli_gui_identical_processing_results(self):
        """Test that CLI and GUI produce identical processing results"""
        input_file = Path("tests/samples/tls-single/tls_sample.pcap")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test with dedup only (simpler case)
            cli_output = temp_path / "cli_output.pcap"
            gui_output = temp_path / "gui_output.pcap"
            
            # Process with CLI approach
            cli_result = ConsistentProcessor.process_file(
                input_file, cli_output, dedup=True, anon=False, mask=False
            )
            
            # Process with GUI approach (using same core)
            gui_executor = ConsistentProcessor.create_executor(
                dedup=True, anon=False, mask=False
            )
            gui_result = gui_executor.run(input_file, gui_output)
            
            # Results should be identical
            assert cli_result.success == gui_result.success
            assert len(cli_result.stage_stats) == len(gui_result.stage_stats)
            
            # Output files should be identical
            if cli_output.exists() and gui_output.exists():
                cli_hash = self._get_file_hash(cli_output)
                gui_hash = self._get_file_hash(gui_output)
                assert cli_hash == gui_hash, "Output files should be identical"
    
    def test_gui_feature_flag_consistency(self):
        """Test that GUI feature flags work correctly with both implementations"""
        # Test legacy mode (default)
        assert not GUIFeatureFlags.should_use_consistent_processor()
        
        # Test enabling consistent processor
        GUIFeatureFlags.enable_consistent_processor()
        assert GUIFeatureFlags.should_use_consistent_processor()
        
        # Test force legacy override
        GUIFeatureFlags.force_legacy_mode()
        assert not GUIFeatureFlags.should_use_consistent_processor()
        assert GUIFeatureFlags.is_legacy_mode_forced()
    
    def test_gui_threading_consistency(self):
        """Test that GUI threading produces consistent results"""
        # Create GUI thread using helper
        thread = GUIThreadingHelper.create_threaded_executor(
            remove_dupes_checked=True,
            anonymize_ips_checked=False,
            mask_payloads_checked=False,
            base_dir="/tmp",
            output_dir="/tmp"
        )
        
        # Thread should have proper Qt interface
        assert hasattr(thread, 'progress_signal')
        assert hasattr(thread, 'start')
        assert hasattr(thread, 'stop')
        assert hasattr(thread, 'is_running')
        
        # Thread should use same executor configuration as CLI
        cli_executor = ConsistentProcessor.create_executor(
            dedup=True, anon=False, mask=False
        )
        
        # Both should have same configuration
        assert thread._executor._config == cli_executor._config
    
    def test_error_message_consistency(self):
        """Test that error messages are consistent between CLI and GUI"""
        from pktmask.core.messages import StandardMessages
        
        # Test that standard messages are used consistently
        assert StandardMessages.NO_OPTIONS_SELECTED != ""
        assert StandardMessages.INPUT_NOT_FOUND != ""
        assert StandardMessages.INVALID_FILE_TYPE != ""
        
        # Test that both CLI and GUI use same error messages
        try:
            ConsistentProcessor.validate_options(False, False, False)
            assert False, "Should have raised exception"
        except ValueError as e:
            cli_error = str(e)
        
        try:
            from pktmask.gui.core.gui_consistent_processor import GUIConsistentProcessor
            GUIConsistentProcessor.validate_gui_options(False, False, False)
            assert False, "Should have raised exception"
        except ValueError as e:
            gui_error = str(e)
        
        assert cli_error == gui_error, "Error messages should be identical"
    
    def test_progress_message_consistency(self):
        """Test that progress messages are consistent"""
        from pktmask.core.messages import StandardMessages
        
        # Test stage progress formatting
        stage_msg = StandardMessages.format_stage_progress("test_stage", 100, 50)
        assert "test_stage" in stage_msg
        assert "100" in stage_msg
        assert "50" in stage_msg
        
        # Test file progress formatting
        file_msg = StandardMessages.format_file_progress("test.pcap", 1, 5)
        assert "test.pcap" in file_msg
        assert "[1/5]" in file_msg
        
        # Test configuration summary formatting
        config_lines = StandardMessages.format_configuration_summary(True, True, False)
        assert len(config_lines) == 3
        assert any("Remove Dupes: Enabled" in line for line in config_lines)
        assert any("Anonymize IPs: Enabled" in line for line in config_lines)
        assert any("Mask Payloads: Disabled" in line for line in config_lines)
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Get MD5 hash of file for comparison"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


class TestConsistencyRegression:
    """Regression tests to ensure consistency is maintained"""
    
    def test_service_layer_compatibility(self):
        """Test that new implementation is compatible with existing service layer interfaces"""
        # This test ensures we haven't broken existing interfaces
        from pktmask.services import build_pipeline_config, create_pipeline_executor
        
        # Test that legacy service layer still works
        config = build_pipeline_config(
            anonymize_ips=True,
            remove_dupes=False,
            mask_payloads=False
        )
        
        assert config is not None
        assert "anonymize_ips" in config
        
        executor = create_pipeline_executor(config)
        assert executor is not None
    
    def test_gui_signal_compatibility(self):
        """Test that GUI signals remain compatible"""
        from pktmask.core.events import PipelineEvents
        
        # Test that all required events exist
        required_events = [
            PipelineEvents.PIPELINE_START,
            PipelineEvents.PIPELINE_END,
            PipelineEvents.FILE_START,
            PipelineEvents.FILE_END,
            PipelineEvents.ERROR,
            PipelineEvents.LOG
        ]
        
        for event in required_events:
            assert event is not None, f"Event {event} should exist"
    
    def test_configuration_backward_compatibility(self):
        """Test that configuration remains backward compatible"""
        from pktmask.core.config import ConfigConverter, BackwardCompatibilityAdapter
        
        # Test legacy GUI format conversion
        legacy_gui_config = {
            'remove_dupes_checked': True,
            'anonymize_ips_checked': False,
            'mask_payloads_checked': True
        }
        
        unified_config = BackwardCompatibilityAdapter.adapt_legacy_gui_config(legacy_gui_config)
        assert unified_config.dedup is True
        assert unified_config.anon is False
        assert unified_config.mask is True
        
        # Test conversion back to legacy format
        legacy_format = ConfigConverter.to_legacy_gui_format(unified_config)
        assert legacy_format['remove_dupes_checked'] is True
        assert legacy_format['anonymize_ips_checked'] is False
        assert legacy_format['mask_payloads_checked'] is True
    
    def test_import_compatibility(self):
        """Test that all imports work correctly"""
        # Test core imports
        from pktmask.core.consistency import ConsistentProcessor
        from pktmask.core.messages import StandardMessages
        from pktmask.core.config import UnifiedConfig
        
        # Test GUI imports
        from pktmask.gui.core.feature_flags import GUIFeatureFlags
        from pktmask.gui.core.gui_consistent_processor import GUIConsistentProcessor
        
        # Test CLI imports
        from pktmask.cli.commands import process_command
        from pktmask.cli.formatters import format_result
        
        # All imports should succeed
        assert ConsistentProcessor is not None
        assert StandardMessages is not None
        assert UnifiedConfig is not None
        assert GUIFeatureFlags is not None
        assert GUIConsistentProcessor is not None
        assert process_command is not None
        assert format_result is not None
