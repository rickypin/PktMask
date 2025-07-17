# Enhanced Logging Features for Windows Diagnostics

## Overview

This document describes the comprehensive logging enhancements added to PktMask to help diagnose Windows build file processing issues. The enhanced logging provides detailed visibility into directory scanning, file processing pipeline, and Windows-specific file operations.

## Key Features

### 1. Directory Scanning Logging

**Location**: `src/pktmask/services/pipeline_service.py`

- **Start/Completion Logging**: Logs when directory scanning starts and completes
- **File Discovery**: Logs each discovered pcap/pcapng file with full path and size
- **Total Count**: Reports total number of valid files found
- **Error Tracking**: Captures and reports scanning errors with details

**Example Output**:
```
📂 Directory Scanning Started
 - Input Directory: /path/to/pcap/files
 - Output Directory: /path/to/output
 - Platform: Windows
 - Scanning for pcap/pcapng files...
 - Found: sample1.pcap (2.45 MB)
 - Found: sample2.pcapng (1.23 MB)
📊 Directory Scanning Completed
 - Total files found: 2
```

### 2. File Processing Pipeline Logging

**Location**: `src/pktmask/services/pipeline_service.py`, `src/pktmask/core/pipeline/executor.py`

- **Stage Start/Completion**: Logs each processing stage (Remove Dupes, Anonymize IPs, Mask Payloads)
- **Detailed Statistics**: Reports packets processed, modified, and processing time
- **Error Handling**: Comprehensive error logging with context information
- **Output Verification**: Verifies output file creation and reports size reduction

**Example Output**:
```
🔄 File Processing Pipeline Started
📄 Processing file 1/2: sample1.pcap
 - Input size: 2.45 MB
 - Output path: sample1_processed.pcap
 - Starting processing stages...
   🔧 Remove Dupes started
   ✅ Remove Dupes: processed 1,000 packets, removed 50 duplicates (5.0%) (0.05s)
   🔧 Anonymize IPs started
   ✅ Anonymize IPs: processed 25 unique IPs, anonymized 25 IPs (100.0%) (0.03s)
   🔧 Mask Payloads started
   ✅ Mask Payloads: processed 950 packets, masked 200 packets (21.1%) (0.12s)
 - ✅ Output created: 2.20 MB (reduction: 10.2%)
```

### 3. Windows-Specific File Operation Logging

**Location**: `src/pktmask/utils/file_ops.py`, `src/pktmask/services/pipeline_service.py`

- **Permission Checks**: Verifies file and directory access permissions
- **Path Encoding**: Validates Windows path encoding and character restrictions
- **File Locks**: Detects file locking issues common on Windows
- **Temporary Files**: Enhanced temporary file creation and cleanup logging
- **Retry Logic**: Implements retry mechanisms for Windows file operations

**Example Output**:
```
 - Directory access: ✅ Readable
 - Input file access: ✅ Readable
 - Output directory access: ✅ Writable
 - Windows file copy completed: input.pcap -> output.pcap
 - Windows file copy verification passed: sizes match (2048000 bytes)
```

### 4. Standardized Message Formatting

**Standards Applied**:
- **Professional English**: All Chinese text replaced with professional English
- **Standardized Naming**: Uses "Remove Dupes", "Anonymize IPs", "Mask Payloads"
- **Proper Indentation**: 1 space + 1 dash for stage messages
- **Functional Emojis**: Meaningful emojis for visual categorization
- **Technical Information**: Preserves all technical data and formatting

**Formatting Levels**:
- Level 0: Main messages (no indent)
- Level 1: Sub-items (` - ` format)
- Level 2: Details (`   • ` format)
- Level 3: Sub-details (`     ◦ ` format)

## Implementation Details

### Enhanced Functions

1. **`process_directory()`**: Comprehensive directory processing with detailed logging
2. **`_handle_stage_progress()`**: Enhanced stage progress reporting
3. **`ensure_directory()`**: Windows-specific directory creation with logging
4. **`copy_file_safely()`**: Enhanced file copying with Windows error handling
5. **`delete_file_safely()`**: Improved file deletion with retry logic

### New Utility Functions

1. **`format_log_message()`**: Standardizes log message formatting
2. **`log_stage_message()`**: Convenience function for stage logging

### Error Handling Improvements

- **Detailed Context**: Includes platform, file paths, and operation details
- **Windows Diagnostics**: Specific checks for Windows file system issues
- **Graceful Degradation**: Continues processing when possible, logs issues
- **Exception Chaining**: Preserves original error information

## Testing

**Test Script**: `tests/test_enhanced_logging.py`

The test script validates:
- Log message formatting consistency
- Directory scanning logging completeness
- Error logging functionality
- Windows-specific feature detection

**Run Tests**:
```bash
cd /path/to/PktMask
python tests/test_enhanced_logging.py
```

## Benefits for Windows Diagnostics

1. **Issue Identification**: Quickly identify where processing fails
2. **Permission Problems**: Detect file/directory access issues
3. **Path Issues**: Identify Windows path encoding or length problems
4. **File Locks**: Detect when files are locked by other processes
5. **Performance Monitoring**: Track processing speed and bottlenecks
6. **Verification**: Confirm successful file operations

## Usage

The enhanced logging is automatically active when using PktMask GUI or CLI. No additional configuration required. Logs appear in:

1. **GUI Log Panel**: Real-time display during processing
2. **Console Output**: When running CLI commands with `-v` flag
3. **Log Files**: Persistent logging to `~/.pktmask/pktmask.log`

## Future Enhancements

- **Log Level Configuration**: Allow users to adjust logging verbosity
- **Performance Metrics**: Add throughput and resource usage logging
- **Export Functionality**: Save processing logs to separate files
- **Integration Testing**: Automated testing on Windows environments
