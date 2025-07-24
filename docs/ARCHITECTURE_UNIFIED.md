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
│  AnonymizationStage     │  DeduplicationStage             │
│  MaskingStage           │  Other processing stages        │
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
    def create_options_from_gui(self, remove_dupes: bool, anonymize_ips: bool, mask_payloads: bool) -> ProcessingOptions
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

## Naming Conventions (Standardized)

PktMask follows consistent naming conventions across all components to ensure clarity and maintainability. This standardization was implemented to resolve architectural inconsistencies and improve developer experience.

### 1. Core Processing Features

The three main processing features use standardized naming across all contexts:

#### GUI Display Names
- **"Remove Dupes"** - Packet deduplication processing
- **"Anonymize IPs"** - IP address anonymization processing
- **"Mask Payloads"** - Payload masking processing

#### Code Variables and Parameters
```python
# Method parameters and variables
remove_dupes: bool = False
anonymize_ips: bool = False
mask_payloads: bool = False

# ProcessingOptions dataclass fields
enable_remove_dupes: bool = False
enable_anonymize_ips: bool = False
enable_mask_payloads: bool = False
```

#### CLI Arguments
```bash
# Full argument names (recommended)
--remove-dupes     # Enable deduplication processing
--anonymize-ips    # Enable IP anonymization processing
--mask-payloads    # Enable payload masking processing

# Usage examples
pktmask mask input.pcap -o output.pcap --remove-dupes --anonymize-ips
pktmask batch /data/pcaps -o /data/output --remove-dupes --anonymize-ips --mask-payloads
```

#### Configuration Keys
```yaml
# Pipeline configuration structure
remove_dupes:
  enabled: true
  algorithm: "sha256"

anonymize_ips:
  enabled: true
  preserve_subnet_structure: true

mask_payloads:
  enabled: true
  mode: "enhanced"
  protocol: "tls"
```

### 2. Stage Architecture Naming

#### Stage Class Names
```python
# Standardized stage class names
class DeduplicationStage(StageBase):     # Packet deduplication
class AnonymizationStage(StageBase):     # IP anonymization
class MaskingStage(StageBase):           # Payload masking
```

#### Logger Names
```python
# Consistent logger naming pattern
self.logger = get_logger("dedup_stage")      # DeduplicationStage
self.logger = get_logger("anonymize_stage")  # AnonymizationStage
self.logger = get_logger("mask_stage")       # MaskingStage
```

### 3. Service Layer Naming

#### Method Naming Patterns
```python
# ConfigService methods use full descriptive names
def create_options_from_cli_args(
    self,
    remove_dupes: bool = False,
    anonymize_ips: bool = False,
    mask_payloads: bool = False,
    # ...
) -> ProcessingOptions

def create_options_from_gui(
    self,
    remove_dupes_checked: bool,
    anonymize_ips_checked: bool,
    mask_payloads_checked: bool
) -> ProcessingOptions
```

### 4. Naming Convention Benefits

#### Developer Experience
- **Consistency**: Same terminology across GUI, CLI, and code
- **Clarity**: Descriptive names that clearly indicate functionality
- **Maintainability**: Easier to locate and modify related code

#### User Experience
- **Predictability**: Consistent terminology across all interfaces
- **Documentation**: Clear mapping between GUI options and CLI arguments
- **Learning**: Reduced cognitive load when switching between interfaces

### 5. Migration from Legacy Names

The following legacy naming patterns have been standardized:

| Legacy Pattern | Standardized Pattern | Context |
|----------------|---------------------|---------|
| `enable_dedup`, `enable_anon`, `enable_mask` | `remove_dupes`, `anonymize_ips`, `mask_payloads` | Code variables |
| `UnifiedIPAnonymizationStage` | `AnonymizationStage` | Stage classes |
| `NewMaskPayloadStage` | `MaskingStage` | Stage classes |
| `--dedup`, `--anon` (shortcuts) | `--remove-dupes`, `--anonymize-ips` | CLI documentation |
| Mixed logger patterns | `dedup_stage`, `anonymize_stage`, `mask_stage` | Logger names |

### 3. Configuration Unification Mechanism

#### Configuration Flow
```
GUI State ──┐
            ├──→ ProcessingOptions ──→ PipelineConfig ──→ PipelineExecutor
CLI Args ───┘
```

#### Configuration Mapping
| GUI Option | CLI Parameter | Config Key | Description |
|-----------|---------------|------------|-------------|
| Remove Dupes checkbox | `--remove-dupes` | `remove_dupes.enabled` | Deduplication processing |
| Anonymize IPs checkbox | `--anonymize-ips` | `anonymize_ips.enabled` | IP anonymization |
| Mask Payloads checkbox | `--mask-payloads` | `mask_payloads.enabled` | Payload masking |
| Masking mode selection | `--mode` | `mask_payloads.mode` | enhanced/basic |
| Protocol type | `--protocol` | `mask_payloads.protocol` | tls/http |

### 4. Processing Flow Unification

#### Single File Processing Flow
```
Input File → Config Validation → Executor Creation → Stage Execution → Result Output → Report Generation
```

#### Directory Batch Processing Flow
```
Input Directory → File Scanning → Config Validation → Executor Creation →
Loop Processing → Progress Updates → Result Aggregation → Report Generation
```

### 5. Error Handling Unification

#### Error Hierarchy
1. **Configuration Errors**: Parameter validation failures
2. **File Errors**: File access permission issues
3. **Processing Errors**: Stage execution exceptions
4. **System Errors**: System-level issues like insufficient memory

#### Error Handling Strategies
- **GUI**: Graphical error dialogs + logging
- **CLI**: Command line error output + exit codes + optional reports

### 6. Performance Optimization

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
