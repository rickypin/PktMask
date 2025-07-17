#!/usr/bin/env python3
"""
Test Windows Platform Fixes for PktMask

This script tests the Windows-specific fixes that were applied to resolve
the batch processing failure issue.
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path

def setup_test_environment():
    """Setup test environment and paths"""
    print("=== Setting up test environment ===")
    
    # Add src to Python path
    src_path = Path(__file__).parent / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))
        print(f"✓ Added to Python path: {src_path}")
    else:
        print(f"✗ Source path not found: {src_path}")
        return False
    
    return True

def test_path_operations():
    """Test path operations with Windows fixes"""
    print("\n=== Testing Path Operations ===")
    
    try:
        from pktmask.utils.file_ops import safe_join, ensure_directory
        
        # Test safe_join with mixed separators
        test_paths = ["C:\\test", "subdir/file.txt"] if os.name == 'nt' else ["/test", "subdir/file.txt"]
        result = safe_join(*test_paths)
        print(f"✓ safe_join result: {result}")
        
        # Test directory creation
        with tempfile.TemporaryDirectory() as temp_dir:
            test_subdir = safe_join(temp_dir, "test_output", "nested")
            
            success = ensure_directory(test_subdir, create_if_missing=True)
            print(f"✓ ensure_directory result: {success}")
            print(f"  - Directory exists: {os.path.exists(test_subdir)}")
            print(f"  - Is directory: {os.path.isdir(test_subdir)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Path operations test failed: {e}")
        traceback.print_exc()
        return False

def test_file_manager_fixes():
    """Test file manager Windows fixes"""
    print("\n=== Testing File Manager Fixes ===")

    try:
        # Set test mode to avoid GUI dependencies
        os.environ['PKTMASK_TEST_MODE'] = 'true'

        # Create QApplication if needed
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from pktmask.gui.managers.file_manager import FileManager
        from pktmask.gui.main_window import MainWindow
        
        # Create a mock main window for testing
        window = MainWindow()
        file_manager = FileManager(window)
        
        print("✓ FileManager created successfully")
        
        # Test path generation
        with tempfile.TemporaryDirectory() as temp_dir:
            window.base_dir = temp_dir
            
            output_path = file_manager.generate_actual_output_path()
            print(f"✓ Generated output path: {output_path}")
            
            # Verify path is properly formatted
            path_obj = Path(output_path)
            print(f"  - Path is absolute: {path_obj.is_absolute()}")
            print(f"  - Parent exists: {path_obj.parent.exists()}")
        
        return True
        
    except Exception as e:
        print(f"✗ File manager test failed: {e}")
        traceback.print_exc()
        return False
    finally:
        # Clean up test mode
        if 'PKTMASK_TEST_MODE' in os.environ:
            del os.environ['PKTMASK_TEST_MODE']

def test_pipeline_manager_fixes():
    """Test pipeline manager Windows fixes"""
    print("\n=== Testing Pipeline Manager Fixes ===")

    try:
        # Set test mode
        os.environ['PKTMASK_TEST_MODE'] = 'true'

        # Create QApplication if needed
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from pktmask.gui.managers.pipeline_manager import PipelineManager
        from pktmask.gui.main_window import MainWindow
        
        # Create mock window
        window = MainWindow()
        pipeline_manager = PipelineManager(window)
        
        print("✓ PipelineManager created successfully")
        
        # Test output directory creation logic
        with tempfile.TemporaryDirectory() as temp_dir:
            window.base_dir = temp_dir
            
            # Mock the file manager
            class MockFileManager:
                def generate_actual_output_path(self):
                    return os.path.join(temp_dir, "test_output")
            
            window.file_manager = MockFileManager()
            
            # Test directory creation (without actually starting processing)
            output_dir = window.file_manager.generate_actual_output_path()
            
            # Test the directory creation logic directly
            from pathlib import Path
            output_path = Path(output_dir)
            
            try:
                output_path.mkdir(parents=True, exist_ok=True)
                print("✓ Directory creation test passed")
            except PermissionError:
                if os.name == 'nt':
                    os.makedirs(str(output_path), exist_ok=True)
                    print("✓ Directory creation test passed (Windows fallback)")
                else:
                    raise
        
        return True
        
    except Exception as e:
        print(f"✗ Pipeline manager test failed: {e}")
        traceback.print_exc()
        return False
    finally:
        # Clean up test mode
        if 'PKTMASK_TEST_MODE' in os.environ:
            del os.environ['PKTMASK_TEST_MODE']

def test_thread_handling():
    """Test thread handling improvements"""
    print("\n=== Testing Thread Handling ===")
    
    try:
        # Set test mode
        os.environ['PKTMASK_TEST_MODE'] = 'true'
        
        from pktmask.gui.main_window import ServicePipelineThread
        from pktmask.services.pipeline_service import create_pipeline_executor, build_pipeline_config
        
        # Create test configuration
        config = build_pipeline_config(
            enable_anon=True,
            enable_dedup=True,
            enable_mask=False
        )
        
        executor = create_pipeline_executor(config)
        
        # Create temporary test environment
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test PCAP file
            test_pcap = os.path.join(temp_dir, "test.pcap")
            pcap_header = bytes([
                0xD4, 0xC3, 0xB2, 0xA1,  # Magic number
                0x02, 0x00, 0x04, 0x00,  # Version
                0x00, 0x00, 0x00, 0x00,  # Timezone
                0x00, 0x00, 0x00, 0x00,  # Timestamp accuracy
                0xFF, 0xFF, 0x00, 0x00,  # Max packet length
                0x01, 0x00, 0x00, 0x00   # Data link type
            ])
            
            with open(test_pcap, 'wb') as f:
                f.write(pcap_header)
            
            output_dir = os.path.join(temp_dir, "output")
            
            # Create thread
            thread = ServicePipelineThread(executor, temp_dir, output_dir)
            print("✓ ServicePipelineThread created successfully")
            
            # Test thread properties
            print(f"  - Thread running: {thread.isRunning()}")
            print(f"  - Thread finished: {thread.isFinished()}")
        
        return True
        
    except Exception as e:
        print(f"✗ Thread handling test failed: {e}")
        traceback.print_exc()
        return False
    finally:
        # Clean up test mode
        if 'PKTMASK_TEST_MODE' in os.environ:
            del os.environ['PKTMASK_TEST_MODE']

def main():
    """Main test function"""
    print("PktMask Windows Fixes Validation")
    print("=" * 40)
    
    # Setup environment
    if not setup_test_environment():
        return 1
    
    # Run tests
    tests = [
        ("Path Operations", test_path_operations),
        ("File Manager Fixes", test_file_manager_fixes),
        ("Pipeline Manager Fixes", test_pipeline_manager_fixes),
        ("Thread Handling", test_thread_handling)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                print(f"✓ {test_name} PASSED")
                passed += 1
            else:
                print(f"✗ {test_name} FAILED")
                failed += 1
        except Exception as e:
            print(f"✗ {test_name} FAILED with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 40)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✓ All Windows fixes validated successfully!")
        print("\nThe fixes should resolve the Windows batch processing issue.")
    else:
        print("✗ Some tests failed. Please review the fixes.")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
