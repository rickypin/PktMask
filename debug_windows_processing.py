#!/usr/bin/env python3
"""
Windows Platform Processing Diagnostic Script for PktMask

This script diagnoses Windows-specific issues that prevent batch processing
from executing after clicking the Start button.

Usage:
    python debug_windows_processing.py [test_directory]
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import List, Dict, Any

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

def test_basic_imports():
    """Test basic module imports"""
    print("\n=== Testing Basic Imports ===")
    
    modules_to_test = [
        "pktmask.services.pipeline_service",
        "pktmask.core.pipeline.executor",
        "pktmask.utils.file_ops",
        "pktmask.common.constants",
        "pktmask.infrastructure.logging"
    ]
    
    failed_imports = []
    
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✓ {module}")
        except Exception as e:
            print(f"✗ {module}: {e}")
            failed_imports.append((module, str(e)))
    
    return len(failed_imports) == 0, failed_imports

def test_directory_scanning(test_dir: str):
    """Test directory scanning functionality"""
    print(f"\n=== Testing Directory Scanning: {test_dir} ===")
    
    if not os.path.exists(test_dir):
        print(f"✗ Test directory does not exist: {test_dir}")
        return False, []
    
    print(f"✓ Test directory exists: {test_dir}")
    print(f"  - Absolute path: {os.path.abspath(test_dir)}")
    print(f"  - Is directory: {os.path.isdir(test_dir)}")
    
    # Test os.scandir functionality
    try:
        pcap_files = []
        all_files = []
        
        print("\n--- Scanning directory contents ---")
        for entry in os.scandir(test_dir):
            all_files.append(entry.name)
            print(f"  - {entry.name} (is_file: {entry.is_file()})")
            
            if entry.is_file() and entry.name.lower().endswith(('.pcap', '.pcapng')):
                pcap_files.append(entry.path)
                print(f"    → PCAP file found: {entry.path}")
        
        print(f"\n--- Scan Results ---")
        print(f"Total files: {len(all_files)}")
        print(f"PCAP files: {len(pcap_files)}")
        
        return True, pcap_files
        
    except Exception as e:
        print(f"✗ Directory scanning failed: {e}")
        traceback.print_exc()
        return False, []

def test_pipeline_service(test_dir: str, pcap_files: List[str]):
    """Test pipeline service functionality"""
    print(f"\n=== Testing Pipeline Service ===")
    
    if not pcap_files:
        print("✗ No PCAP files to test with")
        return False
    
    try:
        from pktmask.services.pipeline_service import process_directory, create_pipeline_executor, build_pipeline_config
        from pktmask.core.events import PipelineEvents
        
        print("✓ Pipeline service imports successful")
        
        # Create test configuration
        config = build_pipeline_config(
            enable_anon=True,
            enable_dedup=True,
            enable_mask=False  # Disable mask to avoid complex dependencies
        )
        
        if not config:
            print("✗ Failed to build pipeline configuration")
            return False
        
        print(f"✓ Pipeline configuration created with {len(config)} stages")
        
        # Create executor
        try:
            executor = create_pipeline_executor(config)
            print("✓ Pipeline executor created successfully")
        except Exception as e:
            print(f"✗ Failed to create pipeline executor: {e}")
            traceback.print_exc()
            return False
        
        # Create temporary output directory
        with tempfile.TemporaryDirectory(prefix="pktmask_test_") as temp_output:
            print(f"✓ Created temporary output directory: {temp_output}")
            
            # Test progress callback
            events_received = []
            
            def test_progress_callback(event_type: PipelineEvents, data: Dict[str, Any]):
                events_received.append((event_type, data))
                print(f"  → Event: {event_type.name}, Data: {data}")
            
            # Test is_running check
            def test_is_running_check():
                return True
            
            print("\n--- Testing process_directory function ---")
            try:
                process_directory(
                    executor=executor,
                    input_dir=test_dir,
                    output_dir=temp_output,
                    progress_callback=test_progress_callback,
                    is_running_check=test_is_running_check
                )
                
                print(f"✓ process_directory completed successfully")
                print(f"  - Events received: {len(events_received)}")
                
                # Check output files
                output_files = list(Path(temp_output).glob("*"))
                print(f"  - Output files created: {len(output_files)}")
                for f in output_files:
                    print(f"    → {f.name} ({f.stat().st_size} bytes)")
                
                return True
                
            except Exception as e:
                print(f"✗ process_directory failed: {e}")
                traceback.print_exc()
                return False
    
    except ImportError as e:
        print(f"✗ Import error: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        traceback.print_exc()
        return False

def test_file_operations(test_dir: str):
    """Test file operations and path handling"""
    print(f"\n=== Testing File Operations ===")
    
    try:
        from pktmask.utils.file_ops import ensure_directory, safe_join
        
        print("✓ File operations imports successful")
        
        # Test path joining
        test_path = safe_join(test_dir, "test_subdir", "test_file.pcap")
        print(f"✓ safe_join test: {test_path}")
        
        # Test directory creation
        with tempfile.TemporaryDirectory() as temp_dir:
            test_subdir = safe_join(temp_dir, "test_output")
            
            result = ensure_directory(test_subdir, create_if_missing=True)
            print(f"✓ ensure_directory result: {result}")
            print(f"  - Directory exists: {os.path.exists(test_subdir)}")
            print(f"  - Is directory: {os.path.isdir(test_subdir)}")
        
        return True
        
    except Exception as e:
        print(f"✗ File operations test failed: {e}")
        traceback.print_exc()
        return False

def create_test_pcap_file(output_path: str) -> bool:
    """Create a minimal test PCAP file for testing"""
    print(f"\n=== Creating Test PCAP File: {output_path} ===")
    
    # Minimal PCAP file header (24 bytes)
    pcap_header = bytes([
        0xD4, 0xC3, 0xB2, 0xA1,  # Magic number (little endian)
        0x02, 0x00,              # Version major
        0x04, 0x00,              # Version minor
        0x00, 0x00, 0x00, 0x00,  # Timezone offset
        0x00, 0x00, 0x00, 0x00,  # Timestamp accuracy
        0xFF, 0xFF, 0x00, 0x00,  # Max packet length
        0x01, 0x00, 0x00, 0x00   # Data link type (Ethernet)
    ])
    
    try:
        with open(output_path, 'wb') as f:
            f.write(pcap_header)
        
        print(f"✓ Created test PCAP file: {output_path}")
        print(f"  - File size: {os.path.getsize(output_path)} bytes")
        return True
        
    except Exception as e:
        print(f"✗ Failed to create test PCAP file: {e}")
        return False

def main():
    """Main diagnostic function"""
    print("PktMask Windows Processing Diagnostic Tool")
    print("=" * 50)
    
    # Setup environment
    if not setup_test_environment():
        print("✗ Failed to setup test environment")
        return 1
    
    # Test basic imports
    imports_ok, failed_imports = test_basic_imports()
    if not imports_ok:
        print(f"\n✗ Import failures detected: {len(failed_imports)}")
        for module, error in failed_imports:
            print(f"  - {module}: {error}")
        return 1
    
    # Determine test directory
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        # Create temporary test directory with test PCAP file
        test_dir = tempfile.mkdtemp(prefix="pktmask_test_")
        test_pcap = os.path.join(test_dir, "test.pcap")
        
        if not create_test_pcap_file(test_pcap):
            print("✗ Failed to create test environment")
            return 1
        
        print(f"✓ Using temporary test directory: {test_dir}")
    
    # Test directory scanning
    scan_ok, pcap_files = test_directory_scanning(test_dir)
    if not scan_ok:
        print("✗ Directory scanning failed")
        return 1
    
    # Test file operations
    if not test_file_operations(test_dir):
        print("✗ File operations test failed")
        return 1
    
    # Test pipeline service
    if not test_pipeline_service(test_dir, pcap_files):
        print("✗ Pipeline service test failed")
        return 1
    
    print("\n" + "=" * 50)
    print("✓ All tests passed successfully!")
    print("The Windows processing pipeline appears to be working correctly.")
    print("\nIf the GUI still doesn't work, the issue may be in:")
    print("- GUI event handling")
    print("- Thread management")
    print("- Signal/slot connections")
    print("- PyQt6 Windows compatibility")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
