# PktMask Code Architecture and Data Processing Mechanisms

## Project Overview

PktMask is a modern PCAP packet processing and anonymization tool focused on network packet deduplication, IP anonymization, and payload trimming. The project has evolved through multiple phases to form a complete architectural system.

**Project Status**: According to memory, 6 major development phases have been completed, including simplified refactoring, multi-layer encapsulation support, test system construction, etc. Currently in production-ready state.

---

## 1. Project Architecture Overview

### 1.1 Overall Architecture Design

```
PktMask/
├── src/pktmask/          # Main application code
├── tests/                # Test code
├── configs/              # Configuration files
├── docs/                 # Documentation
├── reports/              # Report output
├── assets/               # Resource files
└── hooks/                # Git hooks
```

### 1.2 Core Module Layering

1. **Presentation Layer**: GUI interface management
2. **Business Layer**: Data processing pipeline and processors
3. **Core Layer**: Data processing algorithms and strategies
4. **Infrastructure Layer**: Logging, configuration, error handling
5. **Data Layer**: File I/O and data models

---

## 2. Detailed Code Structure

### 2.1 GUI Interface System (`src/pktmask/gui/`)

#### Main Window Architecture
- **MainWindow** (`main_window.py`): Main window controller
  - Uses modern manager pattern, distributing responsibilities to specialized managers
  - Supports event-driven update mechanisms
  - Integrates configuration management and theme system

#### Manager Pattern (`managers/`)
```python
# Manager responsibility distribution
UIManager        # Interface initialization and style management
FileManager      # File selection and path management
PipelineManager  # Processing flow control
ReportManager    # Report generation and display
DialogManager    # Dialog management
StatisticsManager # Statistical data management
EventCoordinator # Event coordination and communication
```

#### Key Features
- **Responsive Theme System**: Automatic detection of system light/dark mode
- **Internationalization Support**: Configurable multi-language support
- **Event-Driven Updates**: Using observer pattern for UI updates
- **Progress Visualization**: Animated progress bars and real-time statistics

### 2.2 Processor System (`src/pktmask/core/processors/`)

#### Simplified Architecture Design
Project simplified from complex plugin system to intuitive processor pattern:

```python
# Processor base architecture
BaseProcessor       # Abstract base class, defines processor interface
ProcessorConfig     # Processor configuration data class
ProcessorResult     # Processing result encapsulation
ProcessorRegistry   # Processor registry
```

#### Specific Processor Implementations
```python
# Three core processors
IPAnonymizer    # IP anonymization processor
Deduplicator    # Deduplication processor  
Trimmer         # Payload trimming processor
```

#### Pipeline Adapter
```python
ProcessorAdapter           # Adapts processors to Pipeline system
adapt_processors_to_pipeline  # Adapter factory function
```

### 2.3 Data Processing Pipeline (`src/pktmask/core/`)

#### Pipeline System
- **Pipeline** (`pipeline.py`): Core processing pipeline
  - Supports multi-step serial processing
  - Progress callbacks and event reporting
  - Temporary file management
  - Error handling and recovery

#### Processing Strategies
- **AnonymizationStrategy**: Anonymization strategy interface
- **HierarchicalAnonymizationStrategy**: Hierarchical anonymization implementation
  - Maintains subnet structure consistency
  - Supports multi-layer network encapsulation
  - Intelligent IP mapping cache

#### Event System
```python
# Event type enumeration
PipelineEvents.PIPELINE_START
PipelineEvents.FILE_START  
PipelineEvents.STEP_SUMMARY
PipelineEvents.PACKETS_SCANNED
PipelineEvents.ERROR
```

### 2.4 Processing Step Implementation (`src/pktmask/steps/`)

#### Deduplication Processing (`deduplication.py`)
```python
def process_file_dedup(file_path, error_log):
    # Hash-based deduplication using packet raw bytes
    # Supports pcap and pcapng formats
    # Memory-optimized deduplication algorithm
```

#### IP Anonymization (`ip_anonymization.py`)
```python
class IpAnonymizationStep:
    # Directory-level IP mapping pre-construction
    def prepare_for_directory(subdir_path, all_pcap_files)
    
    # Single file IP replacement processing
    def process_file(input_path, output_path)
    
    # Final report generation
    def finalize_directory_processing()
```

#### Intelligent Trimming (`trimming.py`)
```python
# Key algorithms
find_tls_signaling_ranges()  # TLS signaling detection
trim_packet_payload()        # Intelligent payload trimming
get_tcp_session_key()        # TCP session identification
```

### 2.5 Configuration Management System (`src/pktmask/config/`)

#### Simplified Configuration Architecture
```python
@dataclass
class UISettings:
    window_width: int = 1200
    theme: str = "auto"
    default_dedup: bool = True
    # ... more UI settings

@dataclass  
class ProcessingSettings:
    chunk_size: int = 10
    max_workers: int = 4
    preserve_subnet_structure: bool = True
    # ... more processing settings

@dataclass
class AppConfig:
    ui: UISettings
    processing: ProcessingSettings  
    logging: LoggingSettings
```

#### Configuration Features
- Automatic loading/saving (YAML/JSON)
- Legacy configuration migration
- Configuration validation and defaults
- Runtime configuration updates

---

## 3. Data Processing Mechanisms

### 3.1 Data Processing Flow

#### Overall Processing Flow
```
File Selection → Directory Scanning → Pipeline Construction → Parallel Processing → Result Aggregation
```

#### Detailed Processing Steps
1. **Input Validation**: File format checking and path validation
2. **Directory Scanning**: Recursive PCAP file discovery
3. **Pipeline Construction**: Build processor chain based on user selection
4. **Preprocessing**: IP mapping pre-scanning (for anonymization)
5. **Serial Processing**: Sequential processing by each processor
6. **Temporary File Management**: Intermediate result temporary storage
7. **Result Output**: Final file writing and report generation

### 3.2 Processor Execution Mechanism

#### Processor Lifecycle
```python
# 1. Initialization phase
processor.initialize()

# 2. Directory preparation (optional)
processor.prepare_for_directory(dir_path, file_list)

# 3. File processing
result = processor.process_file(input_path, output_path)

# 4. Directory completion (optional)
final_report = processor.finalize_directory_processing()
```

#### Data Flow Transformation
```
Original PCAP → Processor1 → Temp File → Processor2 → Temp File → Processor3 → Final File
```

### 3.3 Multi-Layer Encapsulation Processing

#### Encapsulation Detection Engine (`src/pktmask/core/encapsulation/`)
```python
# Supported encapsulation types
- Plain IP (no encapsulation)
- VLAN (802.1Q)
- Double VLAN
- MPLS
- VXLAN  
- GRE
- Composite encapsulation
```

#### Protocol Stack Parsing
```python
# Automatic detection and parsing of multi-layer protocol stacks
EncapsulationDetector.detect_encapsulation()
ProtocolStackParser.parse_layers()
ProcessingAdapter.extract_inner_payload()
```

### 3.4 Performance Optimization Mechanisms

#### Memory Management
- Streaming processing: Avoid loading entire file into memory
- Chunked processing: Configurable processing chunk size
- Temporary file cleanup: Automatic cleanup of intermediate files

#### Concurrent Processing
- Asynchronous file I/O
- Multi-threaded progress updates
- Non-blocking UI response

#### Caching Mechanisms
- IP mapping cache (directory level)
- Protocol parsing result cache
- Configuration object cache

---

## 4. Event and Communication Mechanisms

### 4.1 Event-Driven Architecture

#### Event Types
```python
# Pipeline events
PIPELINE_START, PIPELINE_END
SUBDIR_START, SUBDIR_END  
FILE_START, FILE_END
STEP_SUMMARY
PACKETS_SCANNED
ERROR, LOG

# UI events
STATISTICS_CHANGED
UI_STATE_CHANGED
CONFIGURATION_CHANGED
```

#### Event Coordinator
```python
class EventCoordinator:
    # Event publish/subscribe
    def subscribe(event_type, handler)
    def emit_event(event_type, data)
    
    # Structured event data
    def emit_pipeline_event(event_type, data)
    def emit_statistics_data(stats_data)
```

### 4.2 Data Model System

#### Structured Event Data (`src/pktmask/domain/models/`)
```python
# Pipeline event data models
PipelineEventData
FileStartData, FileEndData
StepSummaryData
ErrorData

# Statistical data models  
StatisticsData
ProcessingMetrics
TimingMetrics

# Step result data models
IPAnonymizationResult
DeduplicationResult
TrimmingResult
```

### 4.3 Reporting System

#### Multi-Level Reporting
1. **Real-time Progress Reports**: Immediate feedback during processing
2. **File-level Reports**: Detailed statistics after single file completion
3. **Directory-level Reports**: Summary after entire directory processing
4. **Global Reports**: Overall statistics after all processing completion

#### Report Formats
- **Console Logs**: Real-time text output
- **GUI Summary**: Formatted user-friendly display
- **JSON Reports**: Structured machine-readable reports
- **Markdown Documentation**: Detailed processing documentation

---

## 5. Extensibility Design

### 5.1 Processor Extension

#### Steps to Add New Processor
1. Inherit from `BaseProcessor`
2. Implement `process_file()` method
3. Register in `ProcessorRegistry`
4. Add GUI option (optional)

#### Extension Example
```python
class CustomProcessor(BaseProcessor):
    def process_file(self, input_path, output_path):
        # Custom processing logic
        return ProcessorResult(success=True, stats={...})

# Register
ProcessorRegistry.register_processor("custom", CustomProcessor)
```

### 5.2 Configuration Extension

#### Adding New Configuration Items
```python
@dataclass
class ProcessingSettings:
    # Existing configuration...
    new_feature_enabled: bool = False
    new_algorithm_params: dict = field(default_factory=dict)
```

### 5.3 Protocol Extension

#### Supporting New Network Protocols
1. Add detector in `encapsulation/` module
2. Update protocol stack parser
3. Extend processing adapter

---

## 6. Test Architecture

### 6.1 Test Layering

```python
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests  
├── e2e/            # End-to-end tests
├── performance/    # Performance tests
└── samples/        # Test data samples
```

### 6.2 Test Coverage

#### Current Test Status
- **Unit Tests**: 85%+ coverage
- **Integration Tests**: Complete real data validation
- **Performance Tests**: Benchmark testing and regression detection
- **GUI Tests**: Automated testing support

#### Test Tools
- pytest: Main testing framework
- coverage: Coverage analysis
- mock: Dependency isolation
- Dedicated test runner: `run_tests.py`

---

## 7. Deployment and Packaging

### 7.1 Modern Packaging

#### pyproject.toml Configuration
- Follows PEP 518/621 standards
- Production/development/documentation dependency separation
- Supports `pip install pcap-batch-decoder`

#### Automated Deployment
```python
deploy.py  # One-click deployment script
├── Code checking and test validation
├── Package building and virtual environment testing
├── Test PyPI and official PyPI deployment
└── Deployment report generation
```

### 7.2 Cross-Platform Support

#### Operating Systems
- Windows (PyQt6 + Npcap)
- macOS (PyQt6 + libpcap)  
- Linux (PyQt6 + libpcap)

#### Python Versions
- Python 3.8+
- Dependency management through requirements.txt

---

## 8. Future Improvement Suggestions

### 8.1 Performance Optimization

1. **Enhanced Parallel Processing**
   - File-level parallel processing
   - GPU-accelerated packet processing
   - Memory-mapped file I/O

2. **Algorithm Optimization**
   - More efficient deduplication algorithms
   - Incremental IP mapping updates
   - Intelligent caching strategies

### 8.2 Feature Extensions

1. **Web Traffic Specialized Processing**
   - HTTP/HTTPS traffic filtering
   - Web security analysis enhancement
   - Application layer protocol deep parsing

2. **Advanced Anonymization**
   - Differential privacy algorithms
   - Timestamp obfuscation
   - Traffic pattern protection

3. **Visualization Enhancement**
   - Interactive data flow diagrams
   - Real-time performance monitoring
   - Processing result visualization

### 8.3 Architecture Evolution

1. **Microservices**
   - Independent processing engine services
   - Standardized API interfaces
   - Distributed processing support

2. **Cloud-Native Support**
   - Docker containerization
   - Kubernetes deployment
   - Elastic scaling

3. **Enterprise-Grade Enhancement**
   - Audit logging system
   - User permission management
   - Batch job scheduling

---

## Summary

PktMask project has the following advantages:

1. **Clear Architecture**: Modern layered architecture with clear separation of responsibilities
2. **Strong Extensibility**: Modular design, easy to add new features
3. **Excellent Performance**: Memory optimization and concurrent processing
4. **User-Friendly**: Intuitive GUI and detailed feedback
5. **Comprehensive Testing**: High-coverage automated testing
6. **Production-Ready**: Complete deployment and monitoring support

This document can serve as an important reference for subsequent feature improvements, code maintenance, and architectural evolution. 