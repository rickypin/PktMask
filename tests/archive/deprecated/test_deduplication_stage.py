"""
Unit tests for DeduplicationStage - Phase 2 Architecture Migration

This module tests the DeduplicationStage implementation to ensure it provides
full compatibility with the original DeduplicationProcessor while using the
unified StageBase architecture.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from pktmask.core.pipeline.stages.deduplication_stage import DeduplicationStage
from pktmask.core.pipeline.models import StageStats


class TestDeduplicationStage:
    """Test suite for DeduplicationStage"""

    def test_initialization_with_config(self):
        """Test stage initialization with configuration"""
        config = {
            'enabled': True,
            'name': 'test_dedup',
            'priority': 5
        }
        
        stage = DeduplicationStage(config)
        
        assert stage.config == config
        assert stage.enabled == True
        assert stage.stage_name == 'test_dedup'
        assert stage.priority == 5
        assert not stage._initialized
        assert stage._processor is None

    def test_initialization_with_defaults(self):
        """Test stage initialization with default values"""
        stage = DeduplicationStage({})
        
        assert stage.enabled == True
        assert stage.stage_name == 'deduplication'
        assert stage.priority == 0

    def test_stage_initialize(self):
        """Test stage initialization process"""
        config = {'enabled': True, 'name': 'test_init'}
        stage = DeduplicationStage(config)
        
        # Mock the DeduplicationProcessor
        with patch('pktmask.core.pipeline.stages.dedup.DeduplicationProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.initialize.return_value = True
            mock_processor_class.return_value = mock_processor
            
            stage.initialize()
            
            assert stage._initialized
            assert stage._processor is not None
            mock_processor.initialize.assert_called_once()

    def test_stage_initialize_failure(self):
        """Test stage initialization failure handling"""
        config = {'enabled': True, 'name': 'test_fail'}
        stage = DeduplicationStage(config)
        
        # Mock the DeduplicationProcessor to fail initialization
        with patch('pktmask.core.pipeline.stages.dedup.DeduplicationProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.initialize.return_value = False
            mock_processor_class.return_value = mock_processor
            
            with pytest.raises(RuntimeError, match="DeduplicationProcessor initialization failed"):
                stage.initialize()

    def test_process_file_success(self):
        """Test successful file processing"""
        config = {'enabled': True, 'name': 'test_process'}
        stage = DeduplicationStage(config)
        
        # Mock successful processing
        mock_result = ProcessorResult(
            success=True,
            data={'total_packets': 100, 'unique_packets': 80, 'removed_count': 20, 'processing_time': 1.5},
            stats={'total_packets': 100, 'unique_packets': 80, 'removed_count': 20, 'deduplication_rate': 20.0}
        )
        
        with patch('pktmask.core.pipeline.stages.dedup.DeduplicationProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.initialize.return_value = True
            mock_processor.process_file.return_value = mock_result
            mock_processor_class.return_value = mock_processor
            
            # Create temporary files for testing
            with tempfile.TemporaryDirectory() as temp_dir:
                input_file = Path(temp_dir) / "input.pcap"
                output_file = Path(temp_dir) / "output.pcap"
                
                # Create a dummy input file
                input_file.write_bytes(b"dummy pcap data")
                
                result = stage.process_file(input_file, output_file)
                
                assert isinstance(result, StageStats)
                assert result.stage_name == "DeduplicationStage"
                assert result.packets_processed == 100
                assert result.packets_modified == 20
                assert result.extra_metrics['success'] == True
                assert result.extra_metrics['total_packets'] == 100
                assert result.extra_metrics['removed_count'] == 20

    def test_process_file_failure(self):
        """Test file processing failure handling"""
        config = {'enabled': True, 'name': 'test_fail'}
        stage = DeduplicationStage(config)
        
        # Mock failed processing
        mock_result = ProcessorResult(
            success=False,
            error="Processing failed"
        )
        
        with patch('pktmask.core.pipeline.stages.dedup.DeduplicationProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.initialize.return_value = True
            mock_processor.process_file.return_value = mock_result
            mock_processor_class.return_value = mock_processor
            
            # Create temporary files for testing
            with tempfile.TemporaryDirectory() as temp_dir:
                input_file = Path(temp_dir) / "input.pcap"
                output_file = Path(temp_dir) / "output.pcap"
                
                # Create a dummy input file
                input_file.write_bytes(b"dummy pcap data")
                
                result = stage.process_file(input_file, output_file)
                
                assert isinstance(result, StageStats)
                assert result.stage_name == "DeduplicationStage"
                assert result.packets_processed == 0
                assert result.packets_modified == 0
                assert result.extra_metrics['success'] == False
                assert result.extra_metrics['error'] == "Processing failed"

    def test_process_file_nonexistent_input(self):
        """Test processing with non-existent input file"""
        config = {'enabled': True, 'name': 'test_nonexistent'}
        stage = DeduplicationStage(config)
        stage.initialize = Mock()  # Skip actual initialization
        stage._initialized = True
        stage._processor = Mock()
        
        with pytest.raises(FileNotFoundError):
            stage.process_file("/non/existent/file.pcap", "/tmp/output.pcap")

    def test_process_file_directory_input(self):
        """Test processing with directory as input"""
        config = {'enabled': True, 'name': 'test_directory'}
        stage = DeduplicationStage(config)
        stage.initialize = Mock()  # Skip actual initialization
        stage._initialized = True
        stage._processor = Mock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Input path is not a file"):
                stage.process_file(temp_dir, "/tmp/output.pcap")

    def test_get_display_name(self):
        """Test display name method"""
        stage = DeduplicationStage({})
        assert stage.get_display_name() == "Remove Dupes"

    def test_get_description(self):
        """Test description method"""
        stage = DeduplicationStage({})
        description = stage.get_description()
        assert "duplicate packets" in description.lower()
        assert "reduce file size" in description.lower()

    def test_get_required_tools(self):
        """Test required tools method"""
        stage = DeduplicationStage({})
        tools = stage.get_required_tools()
        assert tools == []

    def test_stop_method(self):
        """Test stop method"""
        stage = DeduplicationStage({})
        # Should not raise any exceptions
        stage.stop()

    def test_convert_processor_result_to_stage_stats_success(self):
        """Test conversion of successful ProcessorResult to StageStats"""
        stage = DeduplicationStage({'enabled': True, 'name': 'test_convert'})
        
        result = ProcessorResult(
            success=True,
            data={'processing_time': 2.5},
            stats={
                'total_packets': 150,
                'unique_packets': 120,
                'removed_count': 30,
                'deduplication_rate': 20.0,
                'space_saved': {'saved_bytes': 1024, 'saved_percentage': 15.5}
            }
        )
        
        stage_stats = stage._convert_processor_result_to_stage_stats(result, 2500.0)
        
        assert stage_stats.stage_name == "DeduplicationStage"
        assert stage_stats.packets_processed == 150
        assert stage_stats.packets_modified == 30
        assert stage_stats.duration_ms == 2500.0
        assert stage_stats.extra_metrics['success'] == True
        assert stage_stats.extra_metrics['deduplication_rate'] == 20.0
        assert stage_stats.extra_metrics['processing_time'] == 2.5

    def test_convert_processor_result_to_stage_stats_failure(self):
        """Test conversion of failed ProcessorResult to StageStats"""
        stage = DeduplicationStage({'enabled': True, 'name': 'test_convert_fail'})
        
        result = ProcessorResult(
            success=False,
            error="Test error message"
        )
        
        stage_stats = stage._convert_processor_result_to_stage_stats(result, 1000.0)
        
        assert stage_stats.stage_name == "DeduplicationStage"
        assert stage_stats.packets_processed == 0
        assert stage_stats.packets_modified == 0
        assert stage_stats.duration_ms == 1000.0
        assert stage_stats.extra_metrics['success'] == False
        assert stage_stats.extra_metrics['error'] == "Test error message"


class TestDedupStageCompatibility:
    """Test compatibility alias DedupStage"""

    def test_dedup_stage_deprecation_warning(self):
        """Test that DedupStage raises deprecation warning"""
        from pktmask.core.pipeline.stages.dedup import DedupStage
        
        with pytest.warns(DeprecationWarning, match="DedupStage is deprecated"):
            stage = DedupStage({})
            assert isinstance(stage, DeduplicationStage)
