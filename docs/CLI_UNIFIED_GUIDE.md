# PktMask CLI Unified Feature Guide

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
pktmask <command> <input> -o <output> [options]
```

## Core Commands

### 1. process - Unified Processing (RECOMMENDED)

The new `process` command provides a unified interface for all PktMask operations with flexible combinations.

**Single Operations**:
```bash
# Deduplication only
pktmask process input.pcap -o output.pcap --dedup

# IP anonymization only
pktmask process input.pcap -o output.pcap --anon

# Payload masking only
pktmask process input.pcap -o output.pcap --mask
```

**Operation Combinations**:
```bash
# Dedup + Anon (previously impossible combination)
pktmask process input.pcap -o output.pcap --dedup --anon

# Anon + Mask
pktmask process input.pcap -o output.pcap --anon --mask --protocol tls

# All operations
pktmask process input.pcap -o output.pcap --dedup --anon --mask --verbose
```

**Directory Processing**:
```bash
# Process all files in directory
pktmask process /data/pcaps -o /data/output --dedup --anon --mask

# Custom file pattern and detailed output
pktmask process /data/pcaps -o /data/output --mask --pattern "*.pcap,*.cap" --verbose
```

**Parameter Description**:
- `--dedup`: Enable Remove Dupes processing
- `--anon`: Enable Anonymize IPs processing
- `--mask`: Enable Mask Payloads processing
- `--protocol`: Protocol type (`tls` - http support planned)
- `--verbose`: Detailed output
- `--format`: Output format (`text`|`json`)
- `--no-progress`: Disable progress display
- `--pattern`: File matching pattern
- `--save-report`: Save detailed report
- `--report-format`: Report format (`text`|`json`)
- `--report-detailed`: Include detailed statistics

### 2. batch - Batch Processing

Command optimized for large-scale batch processing:

```bash
# Process directory with default settings
pktmask batch /path/to/pcaps -o /path/to/output

# Custom processing options
pktmask batch /path/to/pcaps -o /path/to/output \
  --no-remove-dupes --verbose --format json

# Generate detailed reports
pktmask batch /path/to/pcaps -o /path/to/output \
  --verbose --save-report --report-detailed
```

**batch Command Features**:
- Default enables all processing options (dedup, anon, mask)
- Optimized batch processing performance
- Automatic output directory creation
- Parallel processing support (experimental)

### 5. info - File Information Analysis

```bash
# Analyze single file
pktmask info input.pcap

# Analyze directory
pktmask info /path/to/pcaps --verbose

# JSON format output
pktmask info /path/to/pcaps --format json
```

## Advanced Features

### Report Generation

CLI now supports the same detailed report generation as GUI:

```bash
# Generate text report
pktmask mask input.pcap -o output.pcap --save-report

# Generate JSON report
pktmask mask input.pcap -o output.pcap --save-report --report-format json

# Include detailed statistics
pktmask mask input.pcap -o output.pcap --save-report --report-detailed
```

Reports include:
- Processing summary and statistics
- Detailed performance data for each stage
- Error and warning information
- File processing status

### Progress Display

Multiple progress display modes:

```bash
# Simple progress display (default)
pktmask mask /path/to/pcaps -o /path/to/output

# Detailed progress display
pktmask mask /path/to/pcaps -o /path/to/output --verbose

# Disable progress display
pktmask mask /path/to/pcaps -o /path/to/output --no-progress
```

### Output Format

Support for multiple output formats:

```bash
# Text format (default)
pktmask mask input.pcap -o output.pcap --format text

# JSON format
pktmask mask input.pcap -o output.pcap --format json
```

## Usage Examples

### Example 1: Basic Single File Processing
```bash
# Single operation
pktmask process sample.pcap -o processed.pcap --dedup

# Multiple operations
pktmask process sample.pcap -o processed.pcap --dedup --anon --mask
```

### Example 2: Flexible Operation Combinations
```bash
# Dedup + Anon without masking
pktmask process input.pcap -o output.pcap --dedup --anon

# Anon + Mask without deduplication
pktmask process input.pcap -o output.pcap --anon --mask

# All operations together
pktmask process input.pcap -o output.pcap --dedup --anon --mask
```

### Example 3: Directory Batch Processing
```bash
# Unified approach with selective operations
pktmask process /data/pcaps -o /data/output --dedup --anon --mask --verbose

# Batch command for full pipeline
pktmask batch /data/pcaps -o /data/processed --verbose --save-report
```

### Example 4: Custom Configuration Processing
```bash
# New approach with protocol specification
pktmask process /data/pcaps -o /data/output --mask --protocol tls \
  --pattern "*.pcapng" --format json --save-report
```

### Example 4: Analysis Only (No Processing)
```bash
pktmask info /data/pcaps --verbose --format json > analysis.json
```

## Consistency with GUI

CLI is now fully consistent with GUI:

| Feature | GUI | CLI | Status |
|---------|-----|-----|--------|
| Single File Processing | ✅ | ✅ | Fully Consistent |
| Directory Batch Processing | ✅ | ✅ | Fully Consistent |
| Configuration Options | ✅ | ✅ | Fully Consistent |
| Progress Display | ✅ | ✅ | Fully Consistent |
| Error Handling | ✅ | ✅ | Fully Consistent |
| Report Generation | ✅ | ✅ | Fully Consistent |
| Statistics Information | ✅ | ✅ | Fully Consistent |

## Performance Optimization

### Batch Processing Optimization
- Use `batch` command for optimal batch processing performance
- Use `--no-progress` when processing large files to reduce output overhead
- JSON format output is suitable for automated script processing

### Memory Management
- CLI uses the same memory optimization strategies as GUI
- Automatic memory management during large-scale batch processing
- Supports processing large PCAP files

## Troubleshooting

### Common Issues

**1. Configuration Error**
```bash
❌ Configuration error: No processing stages enabled
```
Solution: Enable at least one processing option (--remove-dupes, --anonymize-ips, or default mask)

**2. File Permission Issues**
```bash
❌ Error: Permission denied
```
Solution: Check input file read permissions and output directory write permissions

**3. Insufficient Memory**
```bash
❌ Error: Memory allocation failed
```
Solution: Process smaller file batches or increase system memory

### Debug Options

```bash
# Enable verbose output
pktmask mask input.pcap -o output.pcap --verbose

# Generate detailed report for problem analysis
pktmask mask input.pcap -o output.pcap --save-report --report-detailed

# JSON format for programmatic analysis
pktmask mask input.pcap -o output.pcap --format json
```

## CLI and GUI Consistency

The CLI provides the same functionality as the GUI with additional flexibility:

1. **Same Configuration Options**: All GUI options have corresponding CLI parameters
2. **Same Processing Results**: CLI and GUI produce identical processing results
3. **Same Report Format**: CLI can generate the same detailed reports as GUI
4. **Enhanced Flexibility**: CLI supports operation combinations for maximum efficiency

## Summary

PktMask CLI now provides a fully consistent functional experience with the GUI, while maintaining the simplicity and efficiency of command-line tools. Whether for single file processing or large-scale batch operations, CLI provides powerful and flexible solutions.
