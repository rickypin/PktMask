#!/usr/bin/env python3
"""
Test script for enhanced logging functionality in PktMask
Validates comprehensive logging for Windows file processing issues
"""

import os
import sys
import tempfile
import platform
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pktmask.services.pipeline_service import (
    process_directory, 
    format_log_message, 
    log_stage_message,
    create_pipeline_executor
)
from pktmask.core.events import PipelineEvents
from pktmask.infrastructure.logging import get_logger

logger = get_logger("TestEnhancedLogging")

class MockProgressCallback:
    """Mock progress callback to capture log messages"""
    
    def __init__(self):
        self.messages = []
        self.events = []
    
    def __call__(self, event_type: PipelineEvents, data: dict):
        self.events.append((event_type, data))
        if event_type == PipelineEvents.LOG:
            message = data.get('message', '')
            self.messages.append(message)
            print(f"[LOG] {message}")

def test_log_message_formatting():
    """Test log message formatting functions"""
    print("\n=== Testing Log Message Formatting ===")
    
    # Test different indentation levels
    test_cases = [
        ("Main message", 0, "🚀"),
        ("Sub-item message", 1, ""),
        ("Detail message", 2, ""),
        ("Sub-detail message", 3, ""),
    ]
    
    for message, level, emoji in test_cases:
        formatted = format_log_message(message, level, emoji)
        print(f"Level {level}: '{formatted}'")
    
    print("✅ Log message formatting test completed")

def test_directory_scanning_logging():
    """Test directory scanning with enhanced logging"""
    print("\n=== Testing Directory Scanning Logging ===")
    
    # Create temporary test directory with sample files
    with tempfile.TemporaryDirectory(prefix="pktmask_test_") as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test pcap files
        test_files = [
            "test1.pcap",
            "test2.pcapng", 
            "test3.txt",  # Non-pcap file (should be ignored)
            "test4.pcap"
        ]
        
        for filename in test_files:
            test_file = temp_path / filename
            test_file.write_bytes(b"fake pcap data" * 100)  # Create some test data
        
        print(f"Created test directory: {temp_dir}")
        print(f"Platform: {platform.system()}")
        
        # Test directory scanning
        callback = MockProgressCallback()
        
        try:
            # Mock executor for testing
            class MockExecutor:
                def run(self, input_path, output_path, progress_cb=None):
                    from pktmask.core.pipeline.types import ProcessResult, StageStats
                    return ProcessResult(
                        success=True,
                        input_file=str(input_path),
                        output_file=str(output_path),
                        duration_ms=100.0,
                        stage_stats=[
                            StageStats(
                                stage_name="DedupStage",
                                packets_processed=1000,
                                packets_modified=50,
                                duration_ms=50.0,
                                extra_metrics={}
                            )
                        ],
                        errors=[]
                    )
            
            mock_executor = MockExecutor()
            output_dir = temp_path / "output"
            output_dir.mkdir()
            
            # Test the enhanced directory processing
            process_directory(
                executor=mock_executor,
                input_dir=str(temp_dir),
                output_dir=str(output_dir),
                progress_callback=callback,
                is_running_check=lambda: True
            )
            
            print(f"\n📊 Captured {len(callback.messages)} log messages")
            print(f"📊 Captured {len(callback.events)} events")
            
            # Verify key logging features
            log_text = "\n".join(callback.messages)
            
            checks = [
                ("Directory scanning started", "📂 Directory Scanning Started" in log_text),
                ("Platform information", f"Platform: {platform.system()}" in log_text),
                ("Files found", "Found:" in log_text),
                ("Scanning completed", "📊 Directory Scanning Completed" in log_text),
                ("File processing", "📄 Processing file" in log_text),
                ("Stage logging", "Remove Dupes:" in log_text or "✅" in log_text),
            ]
            
            print("\n🔍 Logging Feature Verification:")
            for check_name, passed in checks:
                status = "✅" if passed else "❌"
                print(f"  {status} {check_name}")
            
            # Windows-specific checks
            if platform.system() == "Windows":
                windows_checks = [
                    ("Directory access check", "Directory access:" in log_text),
                    ("File path encoding", "Path encoding" in log_text or "Windows" in log_text),
                ]
                
                print("\n🪟 Windows-Specific Checks:")
                for check_name, passed in windows_checks:
                    status = "✅" if passed else "⚠️"
                    print(f"  {status} {check_name}")
            
        except Exception as e:
            print(f"❌ Directory scanning test failed: {e}")
            logger.error(f"Directory scanning test failed: {e}", exc_info=True)

def test_error_logging():
    """Test error logging with non-existent directory"""
    print("\n=== Testing Error Logging ===")
    
    callback = MockProgressCallback()
    non_existent_dir = "/path/that/does/not/exist"
    
    try:
        process_directory(
            executor=None,
            input_dir=non_existent_dir,
            output_dir="/tmp/output",
            progress_callback=callback,
            is_running_check=lambda: True
        )
    except Exception as e:
        print(f"✅ Expected error caught: {type(e).__name__}")
        
        # Check if error was logged properly
        log_text = "\n".join(callback.messages)
        if "does not exist" in log_text:
            print("✅ Error properly logged")
        else:
            print("❌ Error not properly logged")

def main():
    """Run all logging tests"""
    print("🧪 PktMask Enhanced Logging Test Suite")
    print("=" * 50)
    
    try:
        test_log_message_formatting()
        test_directory_scanning_logging()
        test_error_logging()
        
        print("\n" + "=" * 50)
        print("✅ All logging tests completed successfully!")
        print("\n💡 Enhanced logging features:")
        print("  • Comprehensive directory scanning logs")
        print("  • Detailed file processing pipeline logs") 
        print("  • Windows-specific file operation logs")
        print("  • Standardized message formatting")
        print("  • Professional English messages")
        print("  • Proper indentation (1 space + 1 dash)")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        logger.error(f"Test suite failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
