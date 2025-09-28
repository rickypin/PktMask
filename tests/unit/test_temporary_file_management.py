#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Temporary File Management Tests

Tests for proper temporary file creation, usage, and cleanup across PktMask components.
Validates that temporary files are correctly managed in both normal and exceptional scenarios.
"""

import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pktmask.core.pipeline.executor import PipelineExecutor
from pktmask.core.pipeline.resource_manager import ResourceManager
from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage


class TestTemporaryFileManagement:
    """Test temporary file management across PktMask components"""

    def test_pipeline_executor_temp_directory_cleanup(self, tmp_path):
        """Test that PipelineExecutor properly cleans up temporary directories"""
        input_file = tmp_path / "test_input.pcap"
        output_file = tmp_path / "test_output.pcap"

        # Create a minimal input file
        input_file.write_bytes(b"fake pcap data")

        # Create executor with empty config (no stages)
        executor = PipelineExecutor({})

        # Track temporary directories created during execution
        original_tempdir = tempfile.TemporaryDirectory
        temp_dirs_created = []

        def track_temp_dir(*args, **kwargs):
            temp_dir = original_tempdir(*args, **kwargs)
            temp_dirs_created.append(temp_dir.name)
            return temp_dir

        with patch("tempfile.TemporaryDirectory", side_effect=track_temp_dir):
            result = executor.run(input_file, output_file)

        # Verify that temporary directories were created and cleaned up
        assert len(temp_dirs_created) > 0, "No temporary directories were created"

        for temp_dir_path in temp_dirs_created:
            assert not Path(
                temp_dir_path
            ).exists(), f"Temporary directory not cleaned up: {temp_dir_path}"

    def test_pipeline_executor_temp_cleanup_on_exception(self, tmp_path):
        """Test that temporary directories are cleaned up even when exceptions occur"""
        input_file = tmp_path / "test_input.pcap"
        output_file = tmp_path / "test_output.pcap"

        # Create a minimal input file
        input_file.write_bytes(b"fake pcap data")

        # Create executor with a mock stage that will raise an exception
        mock_stage = Mock()
        mock_stage.name = "FailingStage"
        mock_stage.process_file.side_effect = Exception("Simulated stage failure")

        executor = PipelineExecutor({})
        executor.stages = [mock_stage]

        # Track temporary directories
        temp_dirs_created = []
        original_tempdir = tempfile.TemporaryDirectory

        def track_temp_dir(*args, **kwargs):
            temp_dir = original_tempdir(*args, **kwargs)
            temp_dirs_created.append(temp_dir.name)
            return temp_dir

        with patch("tempfile.TemporaryDirectory", side_effect=track_temp_dir):
            result = executor.run(input_file, output_file)

        # Verify execution failed but cleanup still occurred
        assert not result.success, "Expected execution to fail"
        assert len(temp_dirs_created) > 0, "No temporary directories were created"

        for temp_dir_path in temp_dirs_created:
            assert not Path(
                temp_dir_path
            ).exists(), (
                f"Temporary directory not cleaned up after exception: {temp_dir_path}"
            )

    def test_mask_stage_hardlink_cleanup(self, tmp_path):
        """Test that MaskStage properly cleans up temporary hardlinks"""
        # Create test input file
        input_file = tmp_path / "test_input.pcap"
        output_file = tmp_path / "test_output.pcap"
        input_file.write_bytes(b"fake pcap data" * 1000)  # Make it reasonably sized

        # Create MaskStage with minimal config
        config = {"enabled": True, "protocol": "tls", "mode": "enhanced"}
        stage = NewMaskPayloadStage(config)

        # Mock the resource manager to track cleanup calls
        mock_resource_manager = Mock(spec=ResourceManager)
        stage.resource_manager = mock_resource_manager

        # Test hardlink creation and cleanup
        file_size_mb = input_file.stat().st_size / (1024 * 1024)

        # Mock os.link to succeed
        with patch("os.link") as mock_link:
            temp_path = stage._create_temp_hardlink(input_file, file_size_mb)

            # Verify that resource manager was called to register temp file
            mock_resource_manager.register_temp_file.assert_called()
            mock_resource_manager.register_cleanup_callback.assert_called()

            # Verify temp path is different from input (hardlink was created)
            if temp_path != input_file:  # Only if hardlink was actually created
                assert temp_path.name.startswith("input_")
                assert "pktmask_stage_" in str(temp_path.parent)

    def test_mask_stage_hardlink_cross_device_fallback(self, tmp_path):
        """Test that MaskStage handles cross-device hardlink errors gracefully"""
        input_file = tmp_path / "test_input.pcap"
        input_file.write_bytes(b"fake pcap data" * 1000)

        config = {"enabled": True, "protocol": "tls", "mode": "enhanced"}
        stage = NewMaskPayloadStage(config)
        stage.resource_manager = Mock(spec=ResourceManager)

        file_size_mb = input_file.stat().st_size / (1024 * 1024)

        # Mock os.link to raise cross-device error
        with patch("os.link", side_effect=OSError("Invalid cross-device link")):
            temp_path = stage._create_temp_hardlink(input_file, file_size_mb)

            # Should fall back to original path
            assert temp_path == input_file

            # Resource manager should not be called for failed hardlink
            stage.resource_manager.register_temp_file.assert_not_called()

    def test_resource_manager_temp_file_registration(self, tmp_path):
        """Test ResourceManager temporary file registration and cleanup"""
        manager = ResourceManager({})

        # Create temporary files
        temp_file1 = tmp_path / "temp1.tmp"
        temp_file2 = tmp_path / "temp2.tmp"
        temp_file1.write_text("temp data 1")
        temp_file2.write_text("temp data 2")

        # Register temp files
        manager.register_temp_file(temp_file1)
        manager.register_temp_file(temp_file2)

        # Verify files are registered
        assert temp_file1 in manager.temp_files
        assert temp_file2 in manager.temp_files

        # Verify files exist before cleanup
        assert temp_file1.exists()
        assert temp_file2.exists()

        # Cleanup should remove files
        manager.cleanup()

        # Verify files are removed
        assert not temp_file1.exists()
        assert not temp_file2.exists()

    def test_resource_manager_cleanup_callbacks(self):
        """Test ResourceManager cleanup callback execution"""
        manager = ResourceManager({})

        callback_executed = []

        def test_callback1():
            callback_executed.append("callback1")

        def test_callback2():
            callback_executed.append("callback2")

        # Register callbacks
        manager.register_cleanup_callback(test_callback1)
        manager.register_cleanup_callback(test_callback2)

        # Execute cleanup
        manager.cleanup()

        # Verify callbacks were executed
        assert "callback1" in callback_executed
        assert "callback2" in callback_executed

    def test_temp_directory_cleanup_helper(self, tmp_path):
        """Test the temporary directory cleanup helper method"""
        config = {"enabled": True, "protocol": "tls", "mode": "enhanced"}
        stage = NewMaskPayloadStage(config)

        # Create a temporary directory with the expected prefix
        temp_dir = tmp_path / "pktmask_stage_test123"
        temp_dir.mkdir()

        # Verify directory exists
        assert temp_dir.exists()

        # Test cleanup
        stage._cleanup_temp_directory(temp_dir)

        # Verify directory is removed
        assert not temp_dir.exists()

    def test_temp_directory_cleanup_non_empty(self, tmp_path):
        """Test that cleanup handles non-empty directories gracefully"""
        config = {"enabled": True, "protocol": "tls", "mode": "enhanced"}
        stage = NewMaskPayloadStage(config)

        # Create a temporary directory with files
        temp_dir = tmp_path / "pktmask_stage_test456"
        temp_dir.mkdir()
        (temp_dir / "leftover_file.txt").write_text("leftover data")

        # Verify directory exists and is not empty
        assert temp_dir.exists()
        assert list(temp_dir.iterdir())  # Directory is not empty

        # Test cleanup - should not raise exception
        stage._cleanup_temp_directory(temp_dir)

        # Directory should still exist (because it's not empty)
        assert temp_dir.exists()

    @pytest.mark.parametrize(
        "prefix", ["pktmask_pipeline_", "pktmask_stage_", "pktmask_test_"]
    )
    def test_temp_directory_prefixes(self, prefix):
        """Test that temporary directories use consistent prefixes"""
        with tempfile.TemporaryDirectory(prefix=prefix) as temp_dir:
            temp_path = Path(temp_dir)
            assert temp_path.name.startswith(prefix.rstrip("_"))

    def test_concurrent_temp_file_access(self, tmp_path):
        """Test that temporary file management works with concurrent access"""
        import threading
        import time

        manager = ResourceManager({})
        temp_files_created = []
        errors = []

        def create_and_register_temp_file(thread_id):
            try:
                temp_file = tmp_path / f"temp_{thread_id}.tmp"
                temp_file.write_text(f"data from thread {thread_id}")
                manager.register_temp_file(temp_file)
                temp_files_created.append(temp_file)
                time.sleep(0.1)  # Simulate some work
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_and_register_temp_file, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert not errors, f"Errors occurred during concurrent access: {errors}"

        # Verify all files were created and registered
        assert len(temp_files_created) == 5
        assert len(manager.temp_files) == 5

        # Cleanup should remove all files
        manager.cleanup()

        for temp_file in temp_files_created:
            assert not temp_file.exists()
