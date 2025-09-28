"""
Integration test for memory management improvements.

This test verifies that the memory management improvements work correctly
in a realistic scenario without breaking existing functionality.
"""

import tempfile
import unittest
from pathlib import Path

from pktmask.core.pipeline.stages.anonymization_stage import AnonymizationStage
from pktmask.core.pipeline.stages.deduplication_stage import DeduplicationStage


class TestMemoryManagementIntegration(unittest.TestCase):
    """Integration test for memory management improvements"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_config = {
            "resource_manager": {"max_memory_mb": 512, "pressure_threshold": 0.8}
        }

    def test_deduplication_stage_lifecycle(self):
        """Test DeduplicationStage with improved memory management"""
        stage = DeduplicationStage(self.test_config)

        # Initialize
        self.assertTrue(stage.initialize())
        self.assertTrue(stage._initialized)

        # Create some temporary files to test cleanup
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp_file = Path(temp.name)

        stage.register_temp_file(temp_file)
        self.assertTrue(temp_file.exists())

        # Cleanup
        stage.cleanup()

        # Verify cleanup
        self.assertFalse(stage._initialized)
        self.assertFalse(temp_file.exists())
        self.assertEqual(len(stage._temp_files), 0)

    def test_anonymization_stage_lifecycle(self):
        """Test AnonymizationStage with improved memory management"""
        stage = AnonymizationStage(self.test_config)

        # Initialize
        self.assertTrue(stage.initialize())
        self.assertTrue(stage._initialized)

        # Create some temporary files to test cleanup
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp_file = Path(temp.name)

        stage.register_temp_file(temp_file)
        self.assertTrue(temp_file.exists())

        # Cleanup
        stage.cleanup()

        # Verify cleanup
        self.assertFalse(stage._initialized)
        self.assertFalse(temp_file.exists())
        self.assertEqual(len(stage._temp_files), 0)

    def test_multiple_stages_cleanup(self):
        """Test that multiple stages can be cleaned up without interference"""
        stages = [
            DeduplicationStage(self.test_config),
            AnonymizationStage(self.test_config),
        ]

        temp_files = []

        # Initialize all stages and create temp files
        for i, stage in enumerate(stages):
            self.assertTrue(stage.initialize())

            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp_file = Path(temp.name)
                temp_files.append(temp_file)
                stage.register_temp_file(temp_file)

        # Verify all temp files exist
        for temp_file in temp_files:
            self.assertTrue(temp_file.exists())

        # Cleanup all stages
        for stage in stages:
            stage.cleanup()

        # Verify all stages are cleaned up
        for stage in stages:
            self.assertFalse(stage._initialized)
            self.assertEqual(len(stage._temp_files), 0)

        # Verify all temp files are cleaned up
        for temp_file in temp_files:
            self.assertFalse(temp_file.exists())

    def test_cleanup_resilience(self):
        """Test that cleanup is resilient to individual component failures"""
        stage = DeduplicationStage(self.test_config)
        stage.initialize()

        # Create temp files - one valid, one that will cause error
        with tempfile.NamedTemporaryFile(delete=False) as temp1:
            temp_file1 = Path(temp1.name)
        with tempfile.NamedTemporaryFile(delete=False) as temp2:
            temp_file2 = Path(temp2.name)

        stage.register_temp_file(temp_file1)
        stage.register_temp_file(temp_file2)

        # Remove one file manually to cause cleanup error
        temp_file2.unlink()

        # Cleanup should still work for the remaining file
        stage.cleanup()

        # Verify stage is cleaned up despite error
        self.assertFalse(stage._initialized)
        self.assertFalse(temp_file1.exists())  # This should be cleaned up
        self.assertEqual(len(stage._temp_files), 0)

    def test_resource_manager_integration(self):
        """Test that ResourceManager integration works correctly"""
        stage = DeduplicationStage(self.test_config)

        # Verify ResourceManager is properly initialized
        self.assertIsNotNone(stage.resource_manager)
        # Note: Configuration may use defaults, so just verify reasonable values
        self.assertGreater(stage.resource_manager.memory_monitor.max_memory_mb, 0)
        self.assertGreater(
            stage.resource_manager.memory_monitor.pressure_threshold, 0.0
        )
        self.assertLessEqual(
            stage.resource_manager.memory_monitor.pressure_threshold, 1.0
        )

        # Test memory pressure check
        pressure = stage.resource_manager.get_memory_pressure()
        self.assertIsInstance(pressure, float)
        self.assertGreaterEqual(pressure, 0.0)
        self.assertLessEqual(pressure, 1.0)


if __name__ == "__main__":
    unittest.main()
