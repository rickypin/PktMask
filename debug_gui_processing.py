#!/usr/bin/env python3
"""
Debug script to test GUI processing flow
"""

import sys
import os
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_pipeline_config():
    """Test pipeline configuration building"""
    print("=== Testing Pipeline Configuration ===")
    
    try:
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
        
        # Test different configurations
        configs = [
            (True, True, True, "All features"),
            (True, False, False, "Anonymize only"),
            (False, True, False, "Dedup only"),
            (False, False, True, "Mask only"),
            (False, False, False, "No features"),
        ]
        
        for anon, dedup, mask, desc in configs:
            print(f"\nTesting: {desc}")
            config = build_pipeline_config(anon, dedup, mask)
            print(f"  Config: {config}")
            
            if config:
                try:
                    executor = create_pipeline_executor(config)
                    print(f"  ✅ Executor created successfully")
                except Exception as e:
                    print(f"  ❌ Executor creation failed: {e}")
            else:
                print(f"  ⚠️ Empty configuration")
                
    except Exception as e:
        print(f"❌ Pipeline config test failed: {e}")
        import traceback
        traceback.print_exc()

def test_directory_processing():
    """Test directory processing with mock data"""
    print("\n=== Testing Directory Processing ===")
    
    try:
        from pktmask.services.pipeline_service import process_directory, build_pipeline_config, create_pipeline_executor
        from pktmask.core.events import PipelineEvents
        
        # Create test directory with sample files
        with tempfile.TemporaryDirectory(prefix="pktmask_debug_") as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test pcap files
            test_files = ["test1.pcap", "test2.pcapng"]
            for filename in test_files:
                test_file = temp_path / filename
                test_file.write_bytes(b"fake pcap data" * 100)
            
            print(f"Created test directory: {temp_dir}")
            print(f"Test files: {test_files}")
            
            # Create output directory
            output_dir = temp_path / "output"
            output_dir.mkdir()
            
            # Mock progress callback
            class MockCallback:
                def __init__(self):
                    self.events = []
                    
                def __call__(self, event_type, data):
                    self.events.append((event_type, data))
                    if event_type == PipelineEvents.LOG:
                        print(f"[LOG] {data.get('message', '')}")
                    elif event_type == PipelineEvents.ERROR:
                        print(f"[ERROR] {data.get('message', '')}")
                    else:
                        print(f"[{event_type.name}] {data}")
            
            callback = MockCallback()
            
            # Create minimal configuration
            config = build_pipeline_config(False, True, False)  # Only dedup
            if not config:
                print("❌ Failed to create configuration")
                return
                
            print(f"Configuration: {config}")
            
            try:
                executor = create_pipeline_executor(config)
                print("✅ Executor created")
            except Exception as e:
                print(f"❌ Executor creation failed: {e}")
                return
            
            # Test directory processing
            try:
                print("\nStarting directory processing...")
                process_directory(
                    executor=executor,
                    input_dir=str(temp_dir),
                    output_dir=str(output_dir),
                    progress_callback=callback,
                    is_running_check=lambda: True
                )
                print("✅ Directory processing completed")
                print(f"Total events captured: {len(callback.events)}")
                
            except Exception as e:
                print(f"❌ Directory processing failed: {e}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"❌ Directory processing test failed: {e}")
        import traceback
        traceback.print_exc()

def test_logging_system():
    """Test logging system"""
    print("\n=== Testing Logging System ===")
    
    try:
        from pktmask.infrastructure.logging import get_logger
        
        logger = get_logger("DebugTest")
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")
        
        print("✅ Logging system working")
        
    except Exception as e:
        print(f"❌ Logging system test failed: {e}")

def test_imports():
    """Test all required imports"""
    print("\n=== Testing Imports ===")
    
    imports_to_test = [
        ("pktmask.services.pipeline_service", ["build_pipeline_config", "create_pipeline_executor", "process_directory"]),
        ("pktmask.core.events", ["PipelineEvents"]),
        ("pktmask.infrastructure.logging", ["get_logger"]),
        ("pktmask.gui.main_window", ["ServicePipelineThread"]),
    ]
    
    for module_name, items in imports_to_test:
        try:
            module = __import__(module_name, fromlist=items)
            for item in items:
                if hasattr(module, item):
                    print(f"✅ {module_name}.{item}")
                else:
                    print(f"❌ {module_name}.{item} - not found")
        except Exception as e:
            print(f"❌ {module_name} - import failed: {e}")

def main():
    """Run all debug tests"""
    print("🔍 PktMask GUI Processing Debug Script")
    print("=" * 50)
    
    test_imports()
    test_logging_system()
    test_pipeline_config()
    test_directory_processing()
    
    print("\n" + "=" * 50)
    print("🔍 Debug tests completed")
    print("\n💡 If GUI is not processing files:")
    print("  1. Check if any errors appear in the console")
    print("  2. Verify input directory contains .pcap/.pcapng files")
    print("  3. Check file permissions (especially on Windows)")
    print("  4. Ensure at least one processing feature is enabled")
    print("  5. Look for error messages in the log panel")

if __name__ == "__main__":
    main()
