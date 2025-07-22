"""
Unit tests for unified memory management system

Tests the ResourceManager, BufferManager, MemoryMonitor components
and their integration with StageBase architecture.
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.pktmask.core.pipeline.resource_manager import (
    ResourceManager, 
    MemoryMonitor, 
    BufferManager,
    ResourceStats
)
from src.pktmask.core.pipeline.base_stage import StageBase
from src.pktmask.core.pipeline.models import StageStats


class TestMemoryMonitor:
    """Test MemoryMonitor component"""
    
    def test_memory_monitor_initialization(self):
        """Test MemoryMonitor initialization with config"""
        config = {
            'max_memory_mb': 1024,
            'pressure_threshold': 0.7,
            'monitoring_interval': 50
        }
        
        monitor = MemoryMonitor(config)
        
        assert monitor.max_memory_mb == 1024
        assert monitor.pressure_threshold == 0.7
        assert monitor.monitoring_interval == 50
        assert monitor.operation_count == 0
        assert monitor.gc_count == 0
        assert len(monitor.pressure_callbacks) == 0
    
    @patch('psutil.Process')
    def test_memory_pressure_calculation(self, mock_process):
        """Test memory pressure calculation"""
        # Mock memory info
        mock_memory_info = Mock()
        mock_memory_info.rss = 512 * 1024 * 1024  # 512MB
        mock_process.return_value.memory_info.return_value = mock_memory_info
        
        config = {'max_memory_mb': 1024}  # 1GB limit
        monitor = MemoryMonitor(config)
        
        pressure = monitor.check_memory_pressure()
        
        # 512MB / 1024MB = 0.5
        assert pressure == 0.5
    
    def test_pressure_callback_registration(self):
        """Test pressure callback registration and notification"""
        monitor = MemoryMonitor({})
        callback_called = False
        received_pressure = None
        
        def test_callback(pressure):
            nonlocal callback_called, received_pressure
            callback_called = True
            received_pressure = pressure
        
        monitor.register_pressure_callback(test_callback)
        monitor._notify_pressure_callbacks(0.9)
        
        assert callback_called
        assert received_pressure == 0.9
    
    def test_garbage_collection_trigger(self):
        """Test garbage collection triggering"""
        monitor = MemoryMonitor({})
        initial_gc_count = monitor.gc_count
        
        collected = monitor.trigger_gc()
        
        assert monitor.gc_count == initial_gc_count + 1
        assert isinstance(collected, int)


class TestBufferManager:
    """Test BufferManager component"""
    
    def test_buffer_creation(self):
        """Test buffer creation and tracking"""
        manager = BufferManager({})
        
        buffer = manager.create_buffer("test_buffer", 50)
        
        assert "test_buffer" in manager.active_buffers
        assert "test_buffer" in manager.buffer_stats
        assert buffer == manager.active_buffers["test_buffer"]
        assert len(buffer) == 0
    
    def test_buffer_flush_conditions(self):
        """Test buffer flush condition logic"""
        config = {'default_buffer_size': 10}
        manager = BufferManager(config)
        
        buffer = manager.create_buffer("test_buffer")
        
        # Add items to buffer
        for i in range(5):
            buffer.append(f"item_{i}")
        
        # Should not flush yet (under threshold)
        assert not manager.should_flush_buffer("test_buffer", 0.0)
        
        # Add more items to exceed threshold
        for i in range(10):
            buffer.append(f"item_{i+5}")
        
        # Should flush now (over threshold)
        assert manager.should_flush_buffer("test_buffer", 0.0)
    
    def test_buffer_flush_under_memory_pressure(self):
        """Test buffer flush under high memory pressure"""
        config = {'default_buffer_size': 100, 'auto_resize': True}
        manager = BufferManager(config)
        
        buffer = manager.create_buffer("test_buffer")
        
        # Add few items
        for i in range(5):
            buffer.append(f"item_{i}")
        
        # Under high memory pressure, should flush even with few items
        assert manager.should_flush_buffer("test_buffer", 0.9)
    
    def test_buffer_flush_operation(self):
        """Test buffer flush operation"""
        manager = BufferManager({})
        
        buffer = manager.create_buffer("test_buffer")
        test_items = ["item1", "item2", "item3"]
        
        for item in test_items:
            buffer.append(item)
        
        # Flush buffer
        flushed_items = manager.flush_buffer("test_buffer")
        
        assert flushed_items == test_items
        assert len(buffer) == 0
        assert manager.buffer_stats["test_buffer"]["flush_count"] == 1
    
    def test_buffer_cleanup(self):
        """Test buffer cleanup operations"""
        manager = BufferManager({})
        
        # Create multiple buffers
        manager.create_buffer("buffer1")
        manager.create_buffer("buffer2")
        
        assert len(manager.active_buffers) == 2
        
        # Cleanup specific buffer
        manager.cleanup_buffer("buffer1")
        assert "buffer1" not in manager.active_buffers
        assert len(manager.active_buffers) == 1
        
        # Cleanup all buffers
        manager.cleanup_all_buffers()
        assert len(manager.active_buffers) == 0


class TestResourceManager:
    """Test ResourceManager integration"""
    
    def test_resource_manager_initialization(self):
        """Test ResourceManager initialization"""
        config = {
            'memory_monitor': {'max_memory_mb': 512},
            'buffer_manager': {'default_buffer_size': 50}
        }
        
        manager = ResourceManager(config)
        
        assert manager.memory_monitor.max_memory_mb == 512
        assert manager.buffer_manager.default_buffer_size == 50
        assert len(manager.temp_files) == 0
        assert len(manager.cleanup_callbacks) == 0
    
    def test_unified_buffer_management(self):
        """Test unified buffer management through ResourceManager"""
        manager = ResourceManager({})
        
        # Create buffer
        buffer = manager.create_buffer("test_buffer")
        assert isinstance(buffer, list)
        
        # Add items
        for i in range(5):
            buffer.append(f"item_{i}")
        
        # Check flush condition
        should_flush = manager.should_flush_buffer("test_buffer")
        assert isinstance(should_flush, bool)
        
        # Flush buffer
        flushed_items = manager.flush_buffer("test_buffer")
        assert len(flushed_items) == 5
    
    def test_temp_file_registration(self):
        """Test temporary file registration and cleanup"""
        manager = ResourceManager({})
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_path = Path(tmp.name)
        
        # Register for cleanup
        manager.register_temp_file(temp_path)
        assert temp_path in manager.temp_files
        
        # Cleanup should remove the file
        manager.cleanup()
        assert not temp_path.exists()
    
    def test_cleanup_callbacks(self):
        """Test cleanup callback registration and execution"""
        manager = ResourceManager({})
        callback_executed = False
        
        def test_callback():
            nonlocal callback_executed
            callback_executed = True
        
        manager.register_cleanup_callback(test_callback)
        manager.cleanup()
        
        assert callback_executed
    
    def test_resource_stats(self):
        """Test resource statistics collection"""
        manager = ResourceManager({})
        
        # Create some resources
        manager.create_buffer("buffer1")
        manager.create_buffer("buffer2")
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            manager.register_temp_file(Path(tmp.name))
        
        stats = manager.get_resource_stats()
        
        assert isinstance(stats, ResourceStats)
        assert stats.buffer_count == 2
        assert stats.temp_files == 1
        assert stats.gc_collections >= 0


class MockStage(StageBase):
    """Mock stage for testing StageBase integration"""
    
    name = "MockStage"
    
    def initialize(self, config=None):
        self._initialized = True
        return True
    
    def process_file(self, input_path, output_path):
        return StageStats(
            stage_name=self.name,
            packets_processed=100,
            packets_modified=10,
            duration_ms=1000
        )


class TestStageBaseIntegration:
    """Test StageBase integration with ResourceManager"""
    
    def test_stage_resource_manager_initialization(self):
        """Test that StageBase initializes ResourceManager"""
        config = {
            'resource_manager': {
                'memory_monitor': {'max_memory_mb': 256}
            }
        }
        
        stage = MockStage(config)
        
        assert hasattr(stage, 'resource_manager')
        assert isinstance(stage.resource_manager, ResourceManager)
        assert stage.resource_manager.memory_monitor.max_memory_mb == 256
    
    def test_stage_cleanup_integration(self):
        """Test that StageBase cleanup calls ResourceManager cleanup"""
        stage = MockStage({})
        stage.initialize()
        
        # Mock the resource manager cleanup
        stage.resource_manager.cleanup = Mock()
        
        # Call stage cleanup
        stage.cleanup()
        
        # Verify resource manager cleanup was called
        stage.resource_manager.cleanup.assert_called_once()
        assert not stage._initialized
    
    def test_stage_specific_cleanup_override(self):
        """Test that stage-specific cleanup is called"""
        
        class TestStage(MockStage):
            def __init__(self, config=None):
                super().__init__(config)
                self.custom_cleanup_called = False
            
            def _cleanup_stage_specific(self):
                self.custom_cleanup_called = True
        
        stage = TestStage({})
        stage.initialize()
        stage.cleanup()
        
        assert stage.custom_cleanup_called


if __name__ == "__main__":
    pytest.main([__file__])
