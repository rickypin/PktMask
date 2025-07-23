"""
Unit tests for UnifiedIPAnonymizationStage - Updated for StageBase Architecture

Tests the new StageBase-compatible IP anonymization implementation,
ensuring full functional compatibility with the original IPAnonymizer.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pktmask.core.pipeline.stages.ip_anonymization_unified import UnifiedIPAnonymizationStage as IPAnonymizationStage
from pktmask.core.pipeline.models import StageStats


class TestUnifiedIPAnonymizationStage:
    """Test suite for UnifiedIPAnonymizationStage"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_config = {
            'method': 'prefix_preserving',
            'ipv4_prefix': 24,
            'ipv6_prefix': 64,
            'enabled': True,
            'name': 'test_ip_anonymization'
        }

    def test_initialization_with_config(self):
        """Test stage initialization with configuration"""
        stage = IPAnonymizationStage(self.test_config)
        
        # Verify configuration
        assert stage.method == 'prefix_preserving'
        assert stage.ipv4_prefix == 24
        assert stage.ipv6_prefix == 64
        assert stage.enabled == True
        assert stage.stage_name == 'test_ip_anonymization'

    def test_initialization_with_defaults(self):
        """Test stage initialization with default values"""
        config = {}
        stage = IPAnonymizationStage(config)
        
        # Verify defaults
        assert stage.method == 'prefix_preserving'
        assert stage.ipv4_prefix == 24
        assert stage.ipv6_prefix == 64
        assert stage.enabled == True

    def test_initialize_success(self):
        """Test successful stage initialization"""
        stage = IPAnonymizationStage(self.test_config)
        
        # Test initialization
        result = stage.initialize()
        assert result == True
        assert stage._initialized == True

    def test_initialize_disabled_stage(self):
        """Test initialization of disabled stage"""
        config = self.test_config.copy()
        config['enabled'] = False
        stage = IPAnonymizationStage(config)
        
        # Test initialization
        result = stage.initialize()
        assert result == True  # Should still initialize successfully

    def test_process_file_basic(self):
        """Test basic file processing functionality"""
        stage = IPAnonymizationStage(self.test_config)
        
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
            
            # Verify result
            assert isinstance(result, StageStats)
            assert result.stage_name == 'UnifiedIPAnonymizationStage'  # Uses class name
            assert result.packets_processed >= 0
            assert result.packets_modified >= 0
            assert result.duration_ms >= 0

    def test_process_file_nonexistent_input(self):
        """Test processing with non-existent input file"""
        stage = IPAnonymizationStage(self.test_config)
        
        # Initialize stage
        assert stage.initialize() == True
        
        # Create paths
        input_file = Path("/nonexistent/input.pcap")
        output_file = Path("/tmp/output.pcap")
        
        # Test processing - should raise FileError
        from pktmask.common.exceptions import FileError
        with pytest.raises(FileError):
            stage.process_file(input_file, output_file)

    def test_process_file_uninitalized_stage(self):
        """Test processing with uninitialized stage"""
        stage = IPAnonymizationStage(self.test_config)
        
        # Don't initialize stage
        
        # Use real test PCAP file
        input_file = Path("/mnt/persist/workspace/tests/data/simple_test.pcap")

        # Skip test if test data doesn't exist
        if not input_file.exists():
            pytest.skip(f"Test data file not found: {input_file}")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "output.pcap"

            # Test processing - stage auto-initializes, so this should work
            result = stage.process_file(input_file, output_file)
            assert isinstance(result, StageStats)

    def test_get_display_name(self):
        """Test display name retrieval"""
        stage = IPAnonymizationStage(self.test_config)
        
        display_name = stage.get_display_name()
        assert isinstance(display_name, str)
        assert len(display_name) > 0

    def test_get_description(self):
        """Test description retrieval"""
        stage = IPAnonymizationStage(self.test_config)
        
        description = stage.get_description()
        assert isinstance(description, str)
        assert len(description) > 0

    def test_cleanup(self):
        """Test stage cleanup"""
        stage = IPAnonymizationStage(self.test_config)
        
        # Initialize first
        stage.initialize()
        assert stage._initialized == True
        
        # Test cleanup
        stage.cleanup()
        assert stage._initialized == False

    def test_method_configuration(self):
        """Test different anonymization method configurations"""
        # Test prefix preserving
        config_prefix = {'method': 'prefix_preserving'}
        stage_prefix = IPAnonymizationStage(config_prefix)
        assert stage_prefix.method == 'prefix_preserving'
        
        # Test other methods if supported
        config_random = {'method': 'random'}
        stage_random = IPAnonymizationStage(config_random)
        assert stage_random.method == 'random'

    def test_prefix_configuration(self):
        """Test IPv4 and IPv6 prefix configurations"""
        config = {
            'ipv4_prefix': 16,
            'ipv6_prefix': 48
        }
        stage = IPAnonymizationStage(config)
        
        assert stage.ipv4_prefix == 16
        assert stage.ipv6_prefix == 48

    def test_stage_stats_format(self):
        """Test that returned StageStats has correct format"""
        stage = IPAnonymizationStage(self.test_config)
        
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
        stage = IPAnonymizationStage(self.test_config)
        
        # Test prepare_for_directory
        test_dir = Path("/tmp/test")
        test_files = ["file1.pcap", "file2.pcap"]
        
        # Should not raise any exceptions
        stage.prepare_for_directory(test_dir, test_files)
        
        # Test finalize_directory_processing
        result = stage.finalize_directory_processing()
        # Should return None or dict
        assert result is None or isinstance(result, dict)


class TestUnifiedIPAnonymizationStageIntegration:
    """Integration tests for UnifiedIPAnonymizationStage with ProcessorRegistry"""

    def test_processor_registry_integration(self):
        """Test integration with ProcessorRegistry"""
        from pktmask.core.processors.registry import ProcessorRegistry

        # Test getting processor through registry
        config = {'enabled': True, 'name': 'anonymize_ips'}
        processor = ProcessorRegistry.get_processor('anonymize_ips', config)

        assert isinstance(processor, IPAnonymizationStage)
        assert processor.method == 'prefix_preserving'
        assert processor.ipv4_prefix == 24
        assert processor.ipv6_prefix == 64

    def test_processor_registry_legacy_alias(self):
        """Test legacy alias support through ProcessorRegistry"""
        from pktmask.core.processors.registry import ProcessorRegistry

        # Test legacy alias
        config = {'enabled': True, 'name': 'anon_ip'}
        processor = ProcessorRegistry.get_processor('anon_ip', config)

        assert isinstance(processor, IPAnonymizationStage)

    def test_processor_info_compatibility(self):
        """Test processor info retrieval"""
        from pktmask.core.processors.registry import ProcessorRegistry

        # Test getting processor info
        info = ProcessorRegistry.get_processor_info('anonymize_ips')
        
        assert isinstance(info, dict)
        assert 'name' in info
        assert 'display_name' in info
        assert 'description' in info
        assert 'class' in info

    def test_processor_availability(self):
        """Test processor availability check"""
        from pktmask.core.processors.registry import ProcessorRegistry

        # Test availability
        assert ProcessorRegistry.is_processor_available('anonymize_ips') == True
        assert ProcessorRegistry.is_processor_available('anon_ip') == True
        assert ProcessorRegistry.is_processor_available('nonexistent') == False
