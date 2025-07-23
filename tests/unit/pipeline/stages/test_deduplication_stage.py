"""
Unit tests for UnifiedDeduplicationStage - Updated for StageBase Architecture

This module tests the UnifiedDeduplicationStage implementation using the
unified StageBase architecture without BaseProcessor dependencies.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from pktmask.core.pipeline.stages.deduplication_unified import UnifiedDeduplicationStage
from pktmask.core.pipeline.models import StageStats


class TestUnifiedDeduplicationStage:
    """Test suite for UnifiedDeduplicationStage"""

    def test_initialization_with_config(self):
        """Test stage initialization with configuration"""
        config = {
            'enabled': True,
            'name': 'test_dedup',
            'priority': 5,
            'algorithm': 'md5'
        }
        
        stage = UnifiedDeduplicationStage(config)
        
        # Verify configuration
        assert stage.enabled == True
        assert stage.stage_name == 'test_dedup'
        assert stage.priority == 5
        assert stage.algorithm == 'md5'

    def test_initialization_with_defaults(self):
        """Test stage initialization with default values"""
        config = {}
        stage = UnifiedDeduplicationStage(config)
        
        # Verify defaults
        assert stage.enabled == True
        assert stage.stage_name == 'deduplication'
        assert stage.priority == 0
        assert stage.algorithm == 'md5'

    def test_initialize_success(self):
        """Test successful stage initialization"""
        config = {'enabled': True, 'name': 'test_init'}
        stage = UnifiedDeduplicationStage(config)
        
        # Test initialization
        result = stage.initialize()
        assert result == True
        assert stage._initialized == True

    def test_initialize_disabled_stage(self):
        """Test initialization of disabled stage"""
        config = {'enabled': False, 'name': 'test_disabled'}
        stage = UnifiedDeduplicationStage(config)
        
        # Test initialization
        result = stage.initialize()
        assert result == True  # Should still initialize successfully

    def test_process_file_basic(self):
        """Test basic file processing functionality"""
        config = {'enabled': True, 'name': 'test_process', 'algorithm': 'md5'}
        stage = UnifiedDeduplicationStage(config)

        # Initialize stage
        assert stage.initialize() == True

        # Use real test PCAP file
        input_file = Path("/mnt/persist/workspace/tests/data/duplicate_test.pcap")

        # Skip test if test data doesn't exist
        if not input_file.exists():
            pytest.skip(f"Test data file not found: {input_file}")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "output.pcap"

            # Test processing
            result = stage.process_file(input_file, output_file)

            # Verify result
            assert isinstance(result, StageStats)
            assert result.stage_name == 'UnifiedDeduplicationStage'  # Uses class name, not config name
            assert result.packets_processed >= 0
            assert result.packets_modified >= 0
            assert result.duration_ms >= 0

            # Verify output file was created
            assert output_file.exists()
            assert output_file.stat().st_size > 0

    def test_process_file_nonexistent_input(self):
        """Test processing with non-existent input file"""
        config = {'enabled': True, 'name': 'test_nonexistent'}
        stage = UnifiedDeduplicationStage(config)
        
        # Initialize stage
        assert stage.initialize() == True
        
        # Create paths
        input_file = Path("/nonexistent/input.pcap")
        output_file = Path("/tmp/output.pcap")
        
        # Test processing - should raise FileError (not FileNotFoundError)
        from pktmask.common.exceptions import FileError
        with pytest.raises(FileError):
            stage.process_file(input_file, output_file)

    def test_process_file_uninitalized_stage(self):
        """Test processing with uninitialized stage"""
        config = {'enabled': True, 'name': 'test_uninit'}
        stage = UnifiedDeduplicationStage(config)

        # Don't initialize stage - but the stage auto-initializes in process_file
        # So we test with a valid PCAP file
        input_file = Path("/mnt/persist/workspace/tests/data/simple_test.pcap")

        # Skip test if test data doesn't exist
        if not input_file.exists():
            pytest.skip(f"Test data file not found: {input_file}")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "output.pcap"

            # Test processing - should work because stage auto-initializes
            result = stage.process_file(input_file, output_file)
            assert isinstance(result, StageStats)

    def test_get_display_name(self):
        """Test display name retrieval"""
        config = {'name': 'test_display'}
        stage = UnifiedDeduplicationStage(config)
        
        display_name = stage.get_display_name()
        assert isinstance(display_name, str)
        assert len(display_name) > 0

    def test_get_description(self):
        """Test description retrieval"""
        config = {'name': 'test_desc'}
        stage = UnifiedDeduplicationStage(config)
        
        description = stage.get_description()
        assert isinstance(description, str)
        assert len(description) > 0

    def test_cleanup(self):
        """Test stage cleanup"""
        config = {'enabled': True, 'name': 'test_cleanup'}
        stage = UnifiedDeduplicationStage(config)
        
        # Initialize first
        stage.initialize()
        assert stage._initialized == True
        
        # Test cleanup
        stage.cleanup()
        assert stage._initialized == False

    def test_algorithm_configuration(self):
        """Test different algorithm configurations"""
        # Test MD5
        config_md5 = {'algorithm': 'md5'}
        stage_md5 = UnifiedDeduplicationStage(config_md5)
        assert stage_md5.algorithm == 'md5'
        
        # Test SHA256
        config_sha256 = {'algorithm': 'sha256'}
        stage_sha256 = UnifiedDeduplicationStage(config_sha256)
        assert stage_sha256.algorithm == 'sha256'

    def test_stage_stats_format(self):
        """Test that returned StageStats has correct format"""
        config = {'enabled': True, 'name': 'test_stats', 'algorithm': 'md5'}
        stage = UnifiedDeduplicationStage(config)

        # Initialize stage
        assert stage.initialize() == True

        # Use real test PCAP file
        input_file = Path("/mnt/persist/workspace/tests/data/simple_test.pcap")

        # Skip test if test data doesn't exist
        if not input_file.exists():
            pytest.skip(f"Test data file not found: {input_file}")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "output.pcap"

            # Test processing
            result = stage.process_file(input_file, output_file)

            # Verify StageStats format
            assert hasattr(result, 'stage_name')
            assert hasattr(result, 'packets_processed')
            assert hasattr(result, 'packets_modified')
            assert hasattr(result, 'duration_ms')
            assert hasattr(result, 'extra_metrics')

            # Verify types
            assert isinstance(result.stage_name, str)
            assert isinstance(result.packets_processed, int)
            assert isinstance(result.packets_modified, int)
            assert isinstance(result.duration_ms, float)
            assert isinstance(result.extra_metrics, dict)

    def test_directory_lifecycle_methods(self):
        """Test directory-level lifecycle methods"""
        config = {'enabled': True, 'name': 'test_lifecycle'}
        stage = UnifiedDeduplicationStage(config)
        
        # Test prepare_for_directory
        test_dir = Path("/tmp/test")
        test_files = ["file1.pcap", "file2.pcap"]
        
        # Should not raise any exceptions
        stage.prepare_for_directory(test_dir, test_files)
        
        # Test finalize_directory_processing
        result = stage.finalize_directory_processing()
        # Should return None or dict
        assert result is None or isinstance(result, dict)
