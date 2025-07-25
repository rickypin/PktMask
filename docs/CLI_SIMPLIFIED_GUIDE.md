# PktMask CLI Simplified Interface Guide

## Overview

PktMask CLI features a simplified and unified interface that eliminates complexity and improves user experience:

- ✅ **Unified Input Handling**: Automatically detects file vs directory input and processes accordingly
- ✅ **Smart Output Defaults**: Auto-generates output paths when not specified
- ✅ **Simplified Parameters**: Removed low-value parameters, system automatically optimizes settings
- ✅ **Consistent Interface**: Same parameters work identically for files and directories
- ✅ **Enhanced Validation**: Clear error messages with helpful guidance
- ✅ **User-Friendly Design**: Pragmatic solutions that prioritize ease of use

## Installation and Basic Usage

### Installation
```bash
# Install from project root directory
pip install -e .

# Or run directly
python -m pktmask --help
```

### Basic Command Structure
```bash
pktmask <command> <input> [options]
```

**Key Simplifications:**
- Output path is optional (auto-generated if not specified)
- Input can be a file or directory (automatically detected)
- System automatically optimizes settings for best performance

## Core Commands

### 1. process - Unified Processing (RECOMMENDED)

The `process` command automatically detects input type and generates smart output paths.

**Single File Processing (with auto-generated output)**:
```bash
# Deduplication only - creates input_processed.pcap
pktmask process input.pcap --dedup

# Multiple operations - creates input_processed.pcap
pktmask process input.pcap --dedup --anon --mask
```

**Directory Processing (with auto-generated output)**:
```bash
# Process all PCAP files - creates input_dir_processed/
pktmask process /data/pcaps --dedup --anon --mask

# Verbose output with report
pktmask process /data/pcaps --mask --verbose --save-report
```

**Custom Output Paths (when needed)**:
```bash
# Custom file output
pktmask process input.pcap -o custom_output.pcap --dedup

# Custom directory output
pktmask process /data/pcaps -o /custom/output --anon --mask
```

**Simplified Parameters**:
- `--dedup`: Enable Remove Dupes processing
- `--anon`: Enable Anonymize IPs processing
- `--mask`: Enable Mask Payloads processing (uses TLS protocol)
- `--verbose`: Detailed output and progress information
- `--save-report`: Save detailed processing report
- `-o, --output`: Custom output path (optional)

### 2. info - File Information

Display information about PCAP files or directories.

```bash
# Single file information
pktmask info input.pcap

# Directory information
pktmask info /path/to/pcaps --verbose
```

### 3. info - File Information

Display information about PCAP files or directories.

```bash
# Single file information
pktmask info input.pcap

# Directory information
pktmask info /path/to/pcaps --verbose
```

## Smart Features

### Automatic Input Detection

The CLI automatically detects and validates input:

- **File with .pcap/.pcapng extension** → Single file processing
- **Directory containing PCAP files** → Batch directory processing
- **File with other extension** → Clear error message
- **Empty directory** → Helpful message about no PCAP files found

### Smart Output Path Generation

When no output path is specified:

- **Single file**: `input.pcap` → `input_processed.pcap`
- **Directory**: `/data/pcaps` → `/data/pcaps_processed`

### Automatic Optimization

The system automatically optimizes:

- File pattern matching (always includes *.pcap and *.pcapng)
- Progress display (always enabled for better user experience)
- Report format (text format with appropriate detail level)
- Performance settings (no manual tuning required)

## Usage Examples

### Example 1: Basic Single File Processing
```bash
# Simple deduplication (output auto-generated)
pktmask process sample.pcap --dedup

# Multiple operations with verbose output
pktmask process sample.pcap --dedup --anon --mask --verbose
```

### Example 2: Directory Processing with Intelligent Defaults
```bash
# Process all PCAP files in directory (auto-enables all operations)
pktmask process /data/pcaps

# Explicit operation selection for directory
pktmask process /data/pcaps --dedup --anon
```

### Example 3: Custom Output Paths
```bash
# Custom file output
pktmask process input.pcap -o /custom/path/output.pcap --dedup

# Custom directory output
pktmask process /data/pcaps -o /results/processed --mask --save-report
```

### Example 4: Analysis Only
```bash
# Get file information
pktmask info sample.pcap --verbose

# Analyze directory contents
pktmask info /data/pcaps
```

## Error Handling and Validation

The CLI provides clear, helpful error messages:

```bash
# Invalid file type
❌ Input file must be a PCAP or PCAPNG file (got: .txt)

# Empty directory
❌ Directory contains no PCAP/PCAPNG files: /path/to/empty

# No operations specified
❌ At least one operation must be specified: --dedup, --anon, or --mask

# Invalid protocol
❌ Invalid protocol 'invalid'. Currently supported protocols: tls
```

## Migration from Complex Interface

### Before (Complex)
```bash
# Required output parameter, many low-value options
pktmask process input.pcap -o output.pcap --dedup --verbose --format text --no-progress --pattern "*.pcap"

# Separate batch command for directories
pktmask batch /data/pcaps -o /output --remove-dupes --anonymize-ips --mask-payloads
```

### After (Simplified with Intelligent Defaults)
```bash
# Auto-generated output, smart defaults for files
pktmask process input.pcap --dedup --verbose

# Auto-enabled all operations for directories
pktmask process /data/pcaps --verbose
```

### Benefits of Simplification

1. **Intelligent Defaults**: Directory processing auto-enables all operations for convenience
2. **Reduced Cognitive Load**: Fewer parameters to remember, smart behavior based on input type
3. **Faster Workflow**: No need to specify obvious defaults or remember different commands
4. **Better User Experience**: System handles optimization and path generation automatically
5. **Consistent Behavior**: Same interface for files and directories with context-aware defaults
6. **Clear Error Messages**: Helpful guidance when things go wrong

## CLI and GUI Consistency

The simplified CLI maintains full consistency with the GUI:

1. **Same Configuration Options**: All GUI options have corresponding CLI parameters
2. **Same Processing Results**: CLI and GUI produce identical processing results  
3. **Same Report Format**: CLI can generate the same detailed reports as GUI
4. **Enhanced Flexibility**: CLI supports operation combinations for maximum efficiency

## Summary

The simplified PktMask CLI provides a user-friendly, efficient interface that eliminates unnecessary complexity while maintaining full functionality. The smart defaults and automatic optimizations allow users to focus on their processing goals rather than technical configuration details.
