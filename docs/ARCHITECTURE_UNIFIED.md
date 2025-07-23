# PktMask Unified Architecture Documentation

## Overview

This document describes the complete architectural design of the PktMask project after implementing unified GUI and CLI functionality. Through a unified service layer and configuration system, both interfaces now share the same core processing logic, ensuring functional consistency and code reuse.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                     │
├─────────────────────────┬───────────────────────────────────┤
│         GUI             │            CLI                    │
│   (main_window.py)      │        (cli.py)                   │
│   - Graphical interaction│   - Command line interaction     │
│   - Real-time progress  │   - Batch processing              │
│   - Visual reports      │   - Scripted operations          │
└─────────────────────────┴───────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────────┐
│                    Unified Service Layer                    │
├─────────────────────────────────────────────────────────────┤
│  ConfigService     │  OutputService    │  ProgressService   │
│  - Configuration   │  - Output         │  - Progress        │
│    building        │    formatting     │    management      │
│  - Parameter       │  - Multi-format   │  - Callback        │
│    validation      │    support        │    coordination    │
│  - GUI/CLI         │  - Statistics     │  - Status          │
│    adaptation      │    display        │    tracking        │
├─────────────────────────────────────────────────────────────┤
│  PipelineService   │  ReportService    │                    │
│  - Executor        │  - Report         │                    │
│    management      │    generation     │                    │
│  - File/directory  │  - Multi-format   │                    │
│    processing      │    export         │                    │
│  - Error handling  │  - Detailed       │                    │
│                    │    statistics     │                    │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────────┐
│                    Core Processing Layer                    │
├─────────────────────────────────────────────────────────────┤
│                 PipelineExecutor                            │
│                 - Unified execution engine                 │
│                 - Stage scheduling                         │
│                 - Result aggregation                       │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────────┐
│                   StageBase Architecture                    │
├─────────────────────────────────────────────────────────────┤
│  UnifiedIPAnonymizationStage  │  UnifiedDeduplicationStage  │
│  NewMaskPayloadStage          │  Other processing stages    │
└─────────────────────────────────────────────────────────────┘
```

## Core Component Details

### 1. Unified Service Layer

#### ConfigService - Configuration Service
**Responsibilities**:
- Unified configuration building and validation
- Standardized conversion of GUI and CLI parameters
- Configuration integrity checking

**Key Interfaces**:
```python
class ConfigService:
    def build_pipeline_config(self, options: ProcessingOptions) -> Dict[str, Any]
    def create_options_from_cli_args(self, **kwargs) -> ProcessingOptions
    def create_options_from_gui(self, dedup: bool, anon: bool, mask: bool) -> ProcessingOptions
    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]
```

#### PipelineService - Pipeline Service
**Responsibilities**:
- Executor creation and management
- Unified interface for single file and directory processing
- Progress callback coordination

**Key Interfaces**:
```python
def process_single_file(executor, input_file, output_file, progress_callback, verbose) -> Dict
def process_directory_cli(executor, input_dir, output_dir, progress_callback, verbose) -> Dict
```

#### OutputService - Output Service
**Responsibilities**:
- Unified output formatting
- Multi-level verbosity control
- Text and JSON format support

**Output Levels**:
- `MINIMAL`: Minimal output
- `NORMAL`: Standard output
- `VERBOSE`: Detailed output
- `DEBUG`: Debug output

#### ProgressService - Progress Service
**Responsibilities**:
- Unified progress display management
- Multi-style progress presentation
- Callback event coordination

**Progress Styles**:
- `NONE`: No progress display
- `SIMPLE`: Simple progress
- `DETAILED`: Detailed progress
- `RICH`: Rich progress display

#### ReportService - Report Service
**Responsibilities**:
- Detailed processing report generation
- Multi-format report export
- Statistical data aggregation

**Report Formats**:
- Text format: Human-readable detailed reports
- JSON format: Machine-readable structured data

### 2. Configuration Unification Mechanism

#### Configuration Flow
```
GUI State ──┐
            ├──→ ProcessingOptions ──→ PipelineConfig ──→ PipelineExecutor
CLI Args ───┘
```

#### Configuration Mapping
| GUI Option | CLI Parameter | Config Key | Description |
|-----------|---------------|------------|-------------|
| Remove Dupes checkbox | `--dedup` | `remove_dupes.enabled` | Deduplication processing |
| Anonymize IPs checkbox | `--anon` | `anonymize_ips.enabled` | IP anonymization |
| Mask Payloads checkbox | `--mask` | `mask_payloads.enabled` | Payload masking |
| Masking mode selection | `--mode` | `mask_payloads.mode` | enhanced/basic |
| Protocol type | `--protocol` | `mask_payloads.protocol` | tls/http |

### 3. Processing Flow Unification

#### Single File Processing Flow
```
Input File → Config Validation → Executor Creation → Stage Execution → Result Output → Report Generation
```

#### Directory Batch Processing Flow
```
Input Directory → File Scanning → Config Validation → Executor Creation →
Loop Processing → Progress Updates → Result Aggregation → Report Generation
```

### 4. Error Handling Unification

#### Error Hierarchy
1. **Configuration Errors**: Parameter validation failures
2. **File Errors**: File access permission issues
3. **Processing Errors**: Stage execution exceptions
4. **System Errors**: System-level issues like insufficient memory

#### Error Handling Strategies
- **GUI**: Graphical error dialogs + logging
- **CLI**: Command line error output + exit codes + optional reports

### 5. Performance Optimization

#### Memory Management
- Unified memory pool management
- Large file streaming processing
- Timely resource release

#### Concurrent Processing
- Stage internal concurrency optimization
- File-level concurrency during batch processing (experimental)
- Asynchronous progress callback processing

## Extensibility Design

### 1. New Interface Support
The architecture supports easy addition of new user interfaces:
```python
# New interfaces only need to implement unified service layer interfaces
new_interface = NewInterface()
config = build_config_from_new_interface(new_interface.get_options())
executor = create_pipeline_executor(config)
result = process_with_unified_service(executor, input_path, output_path)
```

### 2. New Processing Stages
Adding new processing stages:
```python
class NewProcessingStage(StageBase):
    def process_packet(self, packet):
        # Implement new processing logic
        pass

# Register in configuration service
config_service.register_stage("new_processing", NewProcessingStage)
```

### 3. New Output Formats
Adding new output formats:
```python
class NewOutputFormatter:
    def format_result(self, result):
        # Implement new formatting logic
        pass

output_service.register_formatter("new_format", NewOutputFormatter)
```

## Testing Strategy

### 1. Unit Testing
- Independent testing of each service component
- Configuration conversion logic testing
- Error handling path testing

### 2. Integration Testing
- GUI and CLI functional consistency testing
- End-to-end processing flow testing
- Performance benchmark testing

### 3. Compatibility Testing
- Backward compatibility verification
- Cross-platform compatibility testing
- Large-scale data processing testing

## Deployment Considerations

### 1. Dependency Management
- Unified dependency declarations
- Conditional loading of optional dependencies
- Version compatibility management

### 2. Configuration Management
- Reasonableness of default configurations
- User configuration persistence
- Configuration migration strategies

### 3. Monitoring and Logging
- Unified logging format
- Performance metrics collection
- Error tracking and reporting

## Future Development

### 1. Short-term Goals
- Improve concurrent support for batch processing
- Enhance visualization capabilities of the reporting system
- Optimize large file processing performance

### 2. Long-term Goals
- Support for more protocol types
- Implement plugin-based architecture
- Provide Web interface support

## Summary

Through the unified service layer architecture, PktMask achieves complete functional consistency between GUI and CLI while maintaining good code reusability and extensibility. This design not only solves current functional difference issues but also establishes a solid foundation for future feature extensions and new interface support.
