"""
Unit tests for IPAnonymizationStage

Tests the new StageBase-compatible IP anonymization implementation,
ensuring full functional compatibility with the original IPAnonymizer.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pktmask.core.pipeline.stages.anonymization_stage import AnonymizationStage as IPAnonymizationStage
from pktmask.core.pipeline.models import StageStats


class TestIPAnonymizationStage:
    """Test suite for IPAnonymizationStage"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_config = {
            'method': 'prefix_preserving',
            'ipv4_prefix': 24,
            'ipv6_prefix': 64,
            'enabled': True,
            'name': 'test_ip_anonymization'
        }
        
    def test_stage_creation(self):
        """Test stage creation with valid configuration"""
        stage = IPAnonymizationStage(self.test_config)
        
        assert stage.name == "IPAnonymizationStage"
        assert stage.method == 'prefix_preserving'
        assert stage.ipv4_prefix == 24
        assert stage.ipv6_prefix == 64
        assert stage.enabled is True
        assert stage.stage_name == 'test_ip_anonymization'
        assert not stage._initialized
        
    def test_stage_creation_with_defaults(self):
        """Test stage creation with minimal configuration"""
        minimal_config = {}
        stage = IPAnonymizationStage(minimal_config)
        
        assert stage.method == 'prefix_preserving'  # default
        assert stage.ipv4_prefix == 24  # default
        assert stage.ipv6_prefix == 64  # default
        assert stage.enabled is True  # default
        assert stage.stage_name == 'ip_anonymization'  # default
        
    def test_initialization_success(self):
        """Test successful stage initialization"""
        stage = IPAnonymizationStage(self.test_config)
        
        with patch('pktmask.core.pipeline.stages.ip_anonymization.IPAnonymizer') as mock_anonymizer_class:
            mock_anonymizer = Mock()
            mock_anonymizer.initialize.return_value = True
            mock_anonymizer_class.return_value = mock_anonymizer
            
            stage.initialize()
            
            assert stage._initialized
            assert stage._anonymizer is not None
            mock_anonymizer.initialize.assert_called_once()
            
    def test_initialization_failure(self):
        """Test stage initialization failure"""
        stage = IPAnonymizationStage(self.test_config)
        
        with patch('pktmask.core.pipeline.stages.ip_anonymization.IPAnonymizer') as mock_anonymizer_class:
            mock_anonymizer = Mock()
            mock_anonymizer.initialize.return_value = False
            mock_anonymizer_class.return_value = mock_anonymizer
            
            with pytest.raises(RuntimeError, match="IPAnonymizer initialization failed"):
                stage.initialize()
                
    def test_initialization_idempotent(self):
        """Test that initialization is idempotent"""
        stage = IPAnonymizationStage(self.test_config)
        
        with patch('pktmask.core.pipeline.stages.ip_anonymization.IPAnonymizer') as mock_anonymizer_class:
            mock_anonymizer = Mock()
            mock_anonymizer.initialize.return_value = True
            mock_anonymizer_class.return_value = mock_anonymizer
            
            # First initialization
            stage.initialize()
            first_anonymizer = stage._anonymizer
            
            # Second initialization should not create new anonymizer
            stage.initialize()
            assert stage._anonymizer is first_anonymizer
            
            # Should only be called once
            mock_anonymizer.initialize.assert_called_once()
            
    def test_prepare_for_directory(self):
        """Test directory preparation functionality"""
        stage = IPAnonymizationStage(self.test_config)
        
        with patch('pktmask.core.pipeline.stages.ip_anonymization.IPAnonymizer') as mock_anonymizer_class:
            mock_anonymizer = Mock()
            mock_anonymizer.initialize.return_value = True
            mock_anonymizer.get_ip_mappings.return_value = {'192.168.1.1': '10.0.0.1', '192.168.1.2': '10.0.0.2'}
            mock_anonymizer_class.return_value = mock_anonymizer
            
            test_directory = "/test/directory"
            test_files = ["file1.pcap", "file2.pcap"]
            
            stage.prepare_for_directory(test_directory, test_files)
            
            # Should initialize if not already done
            assert stage._initialized
            
            # Should call prepare_for_directory on anonymizer
            mock_anonymizer.prepare_for_directory.assert_called_once_with(test_directory, test_files)
            
    def test_process_file_success(self):
        """Test successful file processing"""
        stage = IPAnonymizationStage(self.test_config)
        
        # Mock successful processor result
        mock_result = ProcessorResult(
            success=True,
            data={'processing_time': 1.5},
            stats={
                'total_packets': 100,
                'anonymized_packets': 80,
                'original_ips': 10,
                'anonymized_ips': 10,
                'anonymization_rate': 100.0,
                'ip_mappings': {'192.168.1.1': '10.0.0.1'}
            }
        )
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            with patch('pktmask.core.pipeline.stages.ip_anonymization.IPAnonymizer') as mock_anonymizer_class:
                mock_anonymizer = Mock()
                mock_anonymizer.initialize.return_value = True
                mock_anonymizer.process_file.return_value = mock_result
                mock_anonymizer_class.return_value = mock_anonymizer
                
                result = stage.process_file(input_file.name, output_file.name)
                
                # Verify result type and content
                assert isinstance(result, StageStats)
                assert result.stage_name == "IPAnonymizationStage"
                assert result.packets_processed == 100
                assert result.packets_modified == 80
                assert result.duration_ms > 0
                
                # Verify extra metrics
                assert result.extra_metrics['success'] is True
                assert result.extra_metrics['original_ips'] == 10
                assert result.extra_metrics['anonymized_ips'] == 10
                assert result.extra_metrics['anonymization_rate'] == 100.0
                assert result.extra_metrics['method'] == 'prefix_preserving'
                assert result.extra_metrics['ipv4_prefix'] == 24
                assert result.extra_metrics['ipv6_prefix'] == 64
                
                # Verify anonymizer was called correctly
                mock_anonymizer.process_file.assert_called_once_with(input_file.name, output_file.name)
                
    def test_process_file_failure(self):
        """Test file processing failure"""
        stage = IPAnonymizationStage(self.test_config)
        
        # Mock failed processor result
        mock_result = ProcessorResult(
            success=False,
            error="Processing failed"
        )
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            with patch('pktmask.core.pipeline.stages.ip_anonymization.IPAnonymizer') as mock_anonymizer_class:
                mock_anonymizer = Mock()
                mock_anonymizer.initialize.return_value = True
                mock_anonymizer.process_file.return_value = mock_result
                mock_anonymizer_class.return_value = mock_anonymizer
                
                result = stage.process_file(input_file.name, output_file.name)
                
                # Verify failure result
                assert isinstance(result, StageStats)
                assert result.stage_name == "IPAnonymizationStage"
                assert result.packets_processed == 0
                assert result.packets_modified == 0
                assert result.extra_metrics['success'] is False
                assert result.extra_metrics['error'] == "Processing failed"
                
    def test_process_file_nonexistent_input(self):
        """Test processing with non-existent input file"""
        stage = IPAnonymizationStage(self.test_config)
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            nonexistent_input = "/nonexistent/file.pcap"
            
            with pytest.raises(FileNotFoundError, match="Input file does not exist"):
                stage.process_file(nonexistent_input, output_file.name)
                
    def test_process_file_auto_initialization(self):
        """Test that process_file automatically initializes if needed"""
        stage = IPAnonymizationStage(self.test_config)
        
        mock_result = ProcessorResult(success=True, stats={})
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
            
            with patch('pktmask.core.pipeline.stages.ip_anonymization.IPAnonymizer') as mock_anonymizer_class:
                mock_anonymizer = Mock()
                mock_anonymizer.initialize.return_value = True
                mock_anonymizer.process_file.return_value = mock_result
                mock_anonymizer_class.return_value = mock_anonymizer
                
                # Should not be initialized initially
                assert not stage._initialized
                
                stage.process_file(input_file.name, output_file.name)
                
                # Should be initialized after processing
                assert stage._initialized
                
    def test_finalize_directory_processing(self):
        """Test directory processing finalization"""
        stage = IPAnonymizationStage(self.test_config)
        
        with patch('pktmask.core.pipeline.stages.ip_anonymization.IPAnonymizer') as mock_anonymizer_class:
            mock_anonymizer = Mock()
            mock_anonymizer.initialize.return_value = True
            mock_anonymizer.get_ip_mappings.return_value = {
                '192.168.1.1': '10.0.0.1',
                '192.168.1.2': '10.0.0.2'
            }
            mock_anonymizer_class.return_value = mock_anonymizer
            
            stage.initialize()
            
            summary = stage.finalize_directory_processing()
            
            assert summary is not None
            assert summary['total_unique_ips'] == 2
            assert summary['anonymization_method'] == 'prefix_preserving'
            assert summary['ipv4_prefix'] == 24
            assert summary['ipv6_prefix'] == 64
            assert len(summary['ip_mappings']) == 2
            
    def test_finalize_directory_processing_no_anonymizer(self):
        """Test finalization when anonymizer is not initialized"""
        stage = IPAnonymizationStage(self.test_config)
        
        summary = stage.finalize_directory_processing()
        assert summary is None
        
    def test_get_required_tools(self):
        """Test required tools method"""
        stage = IPAnonymizationStage(self.test_config)
        tools = stage.get_required_tools()
        assert tools == []
        
    def test_stop(self):
        """Test stop method"""
        stage = IPAnonymizationStage(self.test_config)
        # Should not raise any exceptions
        stage.stop()
        
    def test_get_display_name(self):
        """Test display name method"""
        stage = IPAnonymizationStage(self.test_config)
        assert stage.get_display_name() == "Anonymize IPs"
        
    def test_get_description(self):
        """Test description method"""
        stage = IPAnonymizationStage(self.test_config)
        description = stage.get_description()
        assert "Anonymize IP addresses" in description
        assert "prefix_preserving" in description
        assert "24" in description  # IPv4 prefix
        assert "64" in description  # IPv6 prefix
        
    def test_configuration_update_during_initialization(self):
        """Test configuration update during initialization"""
        stage = IPAnonymizationStage(self.test_config)
        
        update_config = {
            'method': 'random',
            'ipv4_prefix': 16,
            'ipv6_prefix': 48
        }
        
        with patch('pktmask.core.pipeline.stages.ip_anonymization.IPAnonymizer') as mock_anonymizer_class:
            mock_anonymizer = Mock()
            mock_anonymizer.initialize.return_value = True
            mock_anonymizer_class.return_value = mock_anonymizer
            
            stage.initialize(update_config)
            
            # Configuration should be updated
            assert stage.method == 'random'
            assert stage.ipv4_prefix == 16
            assert stage.ipv6_prefix == 48


class TestIPAnonymizationStageIntegration:
    """Integration tests for IPAnonymizationStage with ProcessorRegistry"""

    def test_processor_registry_integration(self):
        """Test integration with ProcessorRegistry"""
        from pktmask.core.processors.registry import ProcessorRegistry
        from pktmask.core.processors.base_processor import ProcessorConfig

        # Test getting processor through registry
        config = ProcessorConfig(enabled=True, name='anonymize_ips')
        processor = ProcessorRegistry.get_processor('anonymize_ips', config)

        assert isinstance(processor, IPAnonymizationStage)
        assert processor.method == 'prefix_preserving'
        assert processor.ipv4_prefix == 24
        assert processor.ipv6_prefix == 64

    def test_processor_registry_legacy_alias(self):
        """Test legacy alias support through ProcessorRegistry"""
        from pktmask.core.processors.registry import ProcessorRegistry
        from pktmask.core.processors.base_processor import ProcessorConfig

        # Test legacy alias
        config = ProcessorConfig(enabled=True, name='anon_ip')
        processor = ProcessorRegistry.get_processor('anon_ip', config)

        assert isinstance(processor, IPAnonymizationStage)

    def test_processor_info_compatibility(self):
        """Test processor info retrieval compatibility"""
        from pktmask.core.processors.registry import ProcessorRegistry

        info = ProcessorRegistry.get_processor_info('anonymize_ips')

        assert info['name'] == 'anonymize_ips'
        assert info['display_name'] == 'Anonymize IPs'
        assert 'Anonymize IP addresses' in info['description']
        assert info['class'] == 'IPAnonymizationStage'

    def test_pipeline_executor_integration(self):
        """Test integration with PipelineExecutor"""
        from pktmask.core.pipeline.executor import PipelineExecutor

        config = {
            'anonymize_ips': {'enabled': True}
        }

        executor = PipelineExecutor(config)

        # Should have one stage
        assert len(executor.stages) == 1
        assert isinstance(executor.stages[0], IPAnonymizationStage)
        assert executor.stages[0]._initialized  # Should be initialized during build
