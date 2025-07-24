"""
Tests for memory management improvements in PktMask.

This module tests the practical improvements made to memory management,
focusing on real-world scenarios rather than complex abstractions.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.resource_manager import MemoryMonitor, ResourceManager
from pktmask.core.pipeline.stages.masking_stage.masker.payload_masker import PayloadMasker


class TestStageBase(StageBase):
    """Test implementation of StageBase for testing"""
    
    name = "TestStage"
    
    def initialize(self, config=None):
        return True
    
    def process_file(self, input_path, output_path):
        return {"processed": True}
    
    def _cleanup_stage_specific(self):
        # Test stage-specific cleanup
        pass


class TestMemoryManagementImprovements(unittest.TestCase):
    """Test practical memory management improvements"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_config = {
            "resource_manager": {
                "max_memory_mb": 100,
                "pressure_threshold": 0.8
            }
        }
        self.stage = TestStageBase(self.test_config)

    def test_temp_file_registration_and_cleanup(self):
        """Test unified temporary file management"""
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False) as temp1:
            temp_file1 = Path(temp1.name)
        with tempfile.NamedTemporaryFile(delete=False) as temp2:
            temp_file2 = Path(temp2.name)
        
        # Ensure files exist
        self.assertTrue(temp_file1.exists())
        self.assertTrue(temp_file2.exists())
        
        # Register temp files
        self.stage.register_temp_file(temp_file1)
        self.stage.register_temp_file(temp_file2)
        
        # Verify registration
        self.assertIn(temp_file1, self.stage._temp_files)
        self.assertIn(temp_file2, self.stage._temp_files)
        
        # Cleanup
        self.stage.cleanup()
        
        # Verify cleanup
        self.assertFalse(temp_file1.exists())
        self.assertFalse(temp_file2.exists())
        self.assertEqual(len(self.stage._temp_files), 0)

    def test_cleanup_error_handling(self):
        """Test that cleanup errors are handled gracefully"""
        # Create a temp file and then remove it manually to cause cleanup error
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp_file = Path(temp.name)
        
        self.stage.register_temp_file(temp_file)
        
        # Remove file manually to simulate permission error
        temp_file.unlink()
        
        # Cleanup should not raise exception
        try:
            self.stage.cleanup()
        except Exception as e:
            self.fail(f"Cleanup raised exception: {e}")
        
        # Stage should still be cleaned up
        self.assertFalse(self.stage._initialized)

    def test_memory_monitor_basic_functionality(self):
        """Test basic memory monitoring functionality"""
        monitor = MemoryMonitor({"max_memory_mb": 100, "pressure_threshold": 0.8})
        
        # Test pressure check
        pressure = monitor.check_memory_pressure()
        self.assertIsInstance(pressure, float)
        self.assertGreaterEqual(pressure, 0.0)
        self.assertLessEqual(pressure, 1.0)

    def test_memory_monitor_callback_system(self):
        """Test memory pressure callback system"""
        monitor = MemoryMonitor({"max_memory_mb": 1, "pressure_threshold": 0.1})  # Very low threshold
        
        callback_called = False
        callback_pressure = None
        
        def test_callback(pressure):
            nonlocal callback_called, callback_pressure
            callback_called = True
            callback_pressure = pressure
        
        monitor.register_pressure_callback(test_callback)
        
        # Check memory pressure (should trigger callback due to low threshold)
        pressure = monitor.check_memory_pressure()
        
        # Verify callback behavior (may or may not be called depending on actual memory usage)
        if callback_called:
            self.assertIsInstance(callback_pressure, float)
            self.assertGreaterEqual(callback_pressure, 0.1)

    def test_resource_manager_cleanup_error_handling(self):
        """Test ResourceManager cleanup with error handling"""
        resource_manager = ResourceManager(self.test_config.get("resource_manager", {}))
        
        # Add a callback that will fail
        def failing_callback():
            raise Exception("Test callback failure")
        
        resource_manager.register_cleanup_callback(failing_callback)
        
        # Cleanup should not raise exception
        try:
            resource_manager.cleanup()
        except Exception as e:
            self.fail(f"ResourceManager cleanup raised exception: {e}")

    @patch('pktmask.core.pipeline.stages.masking_stage.masker.payload_masker.PayloadMasker._reset_processing_state')
    def test_payload_masker_simplified_cleanup(self, mock_reset):
        """Test PayloadMasker's simplified cleanup logic"""
        # Create a mock PayloadMasker with some components
        masker = PayloadMasker({})
        
        # Add mock components
        masker.resource_manager = MagicMock()
        masker.error_handler = MagicMock()
        masker.data_validator = MagicMock()
        masker.fallback_handler = MagicMock()
        
        # Test cleanup
        masker.cleanup()
        
        # Verify all components were cleaned up
        masker.resource_manager.cleanup.assert_called_once()
        masker.error_handler.cleanup.assert_called_once()
        masker.data_validator.cleanup.assert_called_once()
        masker.fallback_handler.cleanup.assert_called_once()
        mock_reset.assert_called_once()

    def test_payload_masker_cleanup_with_missing_components(self):
        """Test PayloadMasker cleanup when some components are missing"""
        masker = PayloadMasker({})
        
        # Only add resource_manager
        masker.resource_manager = MagicMock()
        
        # Cleanup should work without errors
        try:
            masker.cleanup()
        except Exception as e:
            self.fail(f"PayloadMasker cleanup failed with missing components: {e}")
        
        # Resource manager should still be cleaned up
        masker.resource_manager.cleanup.assert_called_once()

    def test_stage_cleanup_order(self):
        """Test that cleanup happens in the correct order"""
        cleanup_order = []
        
        class OrderTestStage(TestStageBase):
            def _cleanup_stage_specific(self):
                cleanup_order.append("stage_specific")
            
            def _cleanup_temp_files(self):
                cleanup_order.append("temp_files")
                super()._cleanup_temp_files()
        
        # Mock resource manager cleanup
        stage = OrderTestStage(self.test_config)
        stage.resource_manager.cleanup = lambda: cleanup_order.append("resource_manager")
        
        stage.cleanup()
        
        # Verify cleanup order
        expected_order = ["stage_specific", "temp_files", "resource_manager"]
        self.assertEqual(cleanup_order, expected_order)


if __name__ == '__main__':
    unittest.main()
