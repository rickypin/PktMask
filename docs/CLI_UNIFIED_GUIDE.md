# PktMask CLI Unified Feature Guide

## Overview

PktMask CLI now achieves complete functional unification with the GUI, supporting all core processing capabilities, including:

- ✅ **Single File Processing**: Process individual PCAP/PCAPNG files
- ✅ **Directory Batch Processing**: Batch process multiple files in directories
- ✅ **Unified Configuration System**: Uses the same configuration logic as GUI
- ✅ **Rich Output Options**: Detailed progress display, statistics, and report generation
- ✅ **Complete Error Handling**: Unified error handling and recovery mechanisms

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

### 1. mask - Payload Masking Processing

**Single File Processing**:
```bash
# Basic masking processing
pktmask mask input.pcap -o output.pcap

# Enable all processing options
pktmask mask input.pcap -o output.pcap --dedup --anon --verbose

# Custom masking mode
pktmask mask input.pcap -o output.pcap --mode basic --protocol tls
```

**Directory Batch Processing**:
```bash
# Process all files in directory
pktmask mask /path/to/pcaps -o /path/to/output --dedup --anon

# Custom file matching pattern
pktmask mask /path/to/pcaps -o /path/to/output --pattern "*.pcap,*.cap"

# Detailed output and report generation
pktmask mask /path/to/pcaps -o /path/to/output --verbose --save-report --report-detailed
```

**Parameter Description**:
- `--dedup`: Enable Remove Dupes processing
- `--anon`: Enable Anonymize IPs processing
- `--mode`: Masking mode (`enhanced`|`basic`)
- `--protocol`: Protocol type (`tls`|`http`)
- `--verbose`: Detailed output
- `--format`: Output format (`text`|`json`)
- `--no-progress`: Disable progress display
- `--pattern`: File matching pattern
- `--save-report`: Save detailed report
- `--report-format`: Report format (`text`|`json`)
- `--report-detailed`: Include detailed statistics

### 2. dedup - Remove Dupes Processing

```bash
# Single file deduplication
pktmask dedup input.pcap -o output.pcap

# Directory batch deduplication
pktmask dedup /path/to/pcaps -o /path/to/output --verbose
```

### 3. anon - Anonymize IPs

```bash
# Single file anonymization
pktmask anon input.pcap -o output.pcap

# Directory batch anonymization
pktmask anon /path/to/pcaps -o /path/to/output --verbose
```

### 4. batch - Batch Processing (Recommended)

Command optimized for large-scale batch processing:

```bash
# Process directory with default settings
pktmask batch /path/to/pcaps -o /path/to/output

# Custom processing options
pktmask batch /path/to/pcaps -o /path/to/output \
  --no-dedup --mode basic --verbose --format json

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
pktmask mask sample.pcap -o processed.pcap --dedup --anon
```

### Example 2: Directory Batch Processing
```bash
pktmask batch /data/pcaps -o /data/processed \
  --verbose --save-report --report-detailed
```

### Example 3: Custom Configuration Processing
```bash
pktmask mask /data/pcaps -o /data/output \
  --mode basic --protocol http \
  --pattern "*.pcapng" --format json
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
Solution: Enable at least one processing option (--dedup, --anon, or default mask)

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

## Migration Guide

### Migrating from Legacy CLI

Legacy commands are still compatible, but new unified commands are recommended:

```bash
# Legacy (still supported)
pktmask mask input.pcap -o output.pcap --dedup --anon --mode enhanced

# New (recommended)
pktmask mask input.pcap -o output.pcap --dedup --anon --verbose --save-report
```

### Migrating from GUI

GUI users can easily switch to CLI:

1. **Same Configuration Options**: All GUI options have corresponding CLI parameters
2. **Same Processing Results**: CLI and GUI produce identical processing results
3. **Same Report Format**: CLI can generate the same detailed reports as GUI

## Summary

PktMask CLI now provides a fully consistent functional experience with the GUI, while maintaining the simplicity and efficiency of command-line tools. Whether for single file processing or large-scale batch operations, CLI provides powerful and flexible solutions.
