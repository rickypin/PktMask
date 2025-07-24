# PktMask Developer Documentation

Welcome to the PktMask developer documentation! This guide provides comprehensive technical information for developers, contributors, and anyone interested in understanding the internal architecture of PktMask.

## 🎯 Quick Start for Developers

### Prerequisites

- Python 3.8+ with pip
- Git for version control
- Basic understanding of network protocols and packet analysis
- Familiarity with PyQt6 for GUI development (optional)

### Development Environment Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/pktmask.git
cd pktmask

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks for code quality
pre-commit install

# Verify installation
python -m pytest tests/ -v
python -m pktmask --help
```

### Code Quality Standards

PktMask maintains high code quality standards with automated tooling:

```bash
# Format code (run before committing)
black src/
isort src/

# Check code quality
flake8 src/
mypy src/

# Run all tests
pytest tests/ -v --cov=src/pktmask

# Pre-commit checks (runs automatically on commit)
pre-commit run --all-files
```

## 📊 Recent Code Quality Improvements

**Major Quality Enhancement (2025-07-23):**

PktMask has undergone comprehensive code quality improvements, establishing modern Python development standards:

### Quality Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Linting Errors** | 564 | ~330 | **-41%** |
| **Code Formatting** | Inconsistent | Standardized | **100%** |
| **Import Organization** | Mixed | isort Standard | **100%** |
| **Type Safety** | Partial | Enhanced | **Significant** |

### Standards Compliance

- ✅ **Black Code Formatting**: All 98 Python files comply with Black standards
- ✅ **Import Organization**: isort-compliant import statements throughout codebase
- ✅ **Linting Configuration**: Comprehensive flake8 setup with 88-character line limits
- ✅ **Error Reduction**: Fixed critical undefined names, duplicate definitions, and syntax issues
- ✅ **Maintainability**: Improved code readability and consistency

## 🏗️ Project Architecture

### High-Level Overview

PktMask follows a modular, pipeline-based architecture designed for extensibility and maintainability:

```text
src/pktmask/
├── adapters/          # Legacy adapter modules (backward compatible)
├── core/              # Core processing logic
│   ├── events/        # Desktop-optimized event system
│   ├── pipeline/      # Pipeline processing framework
│   │   └── stages/    # Processing stage implementations
│   └── processors/    # Core processors
├── domain/            # Business data models
├── gui/               # PyQt6 graphical interface
│   ├── managers/      # UI component managers
│   └── core/          # UI core components
├── infrastructure/    # Cross-cutting concerns
│   ├── logging/       # Logging infrastructure
│   ├── error_handling/ # Exception handling
│   └── dependency/    # Dependency management
├── tools/             # Standalone analysis tools
└── cli.py             # Command line interface
```

### Key Architectural Patterns

**StageBase Framework**
- Unified processing pipeline architecture
- Consistent interface for all processing stages
- Built-in error handling and recovery mechanisms
- Performance monitoring and metrics collection

**Event-Driven Design**
- Lightweight desktop-optimized event system
- Decoupled communication between components
- Real-time progress reporting and status updates
- Extensible event handling for custom workflows

**Modular Components**
- Clean separation of concerns
- Dependency injection for testability
- Plugin-style architecture for extensions
- Clear interfaces between layers

## 🔬 Core Processing Stages

### Remove Dupes Stage (UnifiedDeduplicationStage)

**Purpose**: Eliminates duplicate packets while preserving flow integrity

**Key Features**:
- Multiple deduplication algorithms (hash-based, content-based)
- Configurable duplicate detection criteria
- Maintains packet timing relationships
- Supports both exact and fuzzy matching

**Implementation Details**:
```python
# Located in: src/pktmask/core/pipeline/stages/deduplication_stage.py
class DeduplicationStage(StageBase):
    def process_packet(self, packet: Packet) -> ProcessingResult:
        # Hash-based duplicate detection
        packet_hash = self._calculate_packet_hash(packet)
        if packet_hash in self.seen_hashes:
            return ProcessingResult.DUPLICATE

        self.seen_hashes.add(packet_hash)
        return ProcessingResult.KEEP
```

### Anonymize IPs Stage (AnonymizationStage)

**Purpose**: Replaces real IP addresses with consistent anonymized versions

**Key Features**:
- Hierarchical anonymization preserving network topology
- Consistent mapping across packet flows
- Support for IPv4 and IPv6 addresses
- Multi-layer encapsulation handling (VLAN, MPLS, etc.)

**Implementation Details**:
```python
# Located in: src/pktmask/core/pipeline/stages/anonymization_stage.py
class AnonymizationStage(StageBase):
    def anonymize_ip(self, ip_addr: str) -> str:
        # Consistent mapping using cryptographic hash
        if ip_addr not in self.ip_mapping:
            self.ip_mapping[ip_addr] = self._generate_anonymous_ip(ip_addr)
        return self.ip_mapping[ip_addr]
```

### Mask Payloads Stage (MaskingStage)

**Purpose**: Removes sensitive payload data while preserving protocol structure

**Key Features**:
- Dual-module architecture (TLS Marker + Payload Masker)
- Protocol-aware masking (TLS/SSL intelligence)
- Selective preservation of handshake data
- Support for complex multi-layered protocols

**Architecture**:
```text
MaskingStage
├── TLS Marker (tshark-based)
│   ├── Identifies TLS message boundaries
│   ├── Marks sequence number ranges for preservation
│   └── Handles TCP reassembly and fragmentation
└── Payload Masker (scapy-based)
    ├── Applies masking rules based on markers
    ├── Preserves marked sequences (handshakes)
    └── Zeros out unmarked sequences (application data)
```

## 🧪 Testing Framework

### Test Structure

```text
tests/
├── unit/              # Unit tests for individual components
│   ├── core/          # Core logic tests
│   ├── gui/           # GUI component tests
│   └── infrastructure/ # Infrastructure tests
├── integration/       # Integration tests
│   ├── pipeline/      # End-to-end pipeline tests
│   └── stages/        # Stage interaction tests
├── fixtures/          # Test data and fixtures
│   ├── pcap/          # Sample packet captures
│   └── configs/       # Test configurations
└── performance/       # Performance and benchmark tests
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v                    # Unit tests only
pytest tests/integration/ -v             # Integration tests only
pytest tests/performance/ -v             # Performance tests only

# Run with coverage
pytest tests/ --cov=src/pktmask --cov-report=html

# Run specific test files
pytest tests/unit/core/test_pipeline.py -v
```

### Test Data Management

PktMask uses a comprehensive set of test packet captures:

```bash
# Test data locations
tests/fixtures/pcap/
├── tls/               # TLS/SSL test captures
│   ├── ssl_3.pcap     # Basic TLS handshake
│   ├── tls13.pcap     # TLS 1.3 samples
│   └── mixed.pcap     # Mixed protocol traffic
├── basic/             # Basic protocol tests
│   ├── tcp.pcap       # TCP traffic samples
│   ├── udp.pcap       # UDP traffic samples
│   └── icmp.pcap      # ICMP traffic samples
└── complex/           # Complex scenarios
    ├── tunneled.pcap  # Tunneled traffic
    ├── fragmented.pcap # Fragmented packets
    └── malformed.pcap # Malformed packet handling
```

## 🔧 Development Tools and Utilities

### Built-in Analysis Tools

PktMask includes several standalone analysis tools for development and debugging:

**TLS Flow Analyzer** (`src/pktmask/tools/tls_flow_analyzer.py`)
- Analyzes TLS message flows in packet captures
- Generates detailed HTML reports with flow visualization
- Supports batch processing of multiple files
- Essential for debugging TLS masking issues

```bash
# Analyze TLS flows
python -m pktmask.tools.tls_flow_analyzer --pcap input.pcap --output-dir results/
```

**Enhanced TLS Marker** (`src/pktmask/tools/enhanced_tls_marker.py`)
- Advanced TLS protocol type detection
- Supports all TLS message types (20-24)
- Provides detailed statistics and analysis
- Used for validating TLS processing accuracy

```bash
# Mark TLS messages
python -m pktmask.tools.enhanced_tls_marker --pcap input.pcap --types 20,21,22,23,24
```

**TLS-23 Validator** (`src/pktmask/tools/tls23_maskstage_e2e_validator.py`)
- End-to-end validation of TLS-23 (ApplicationData) masking
- Compares input and output files for masking effectiveness
- Generates detailed validation reports
- Critical for ensuring masking quality

```bash
# Validate TLS-23 masking
python -m pktmask.tools.tls23_maskstage_e2e_validator input.pcap output.pcap
```

### Development Debugging

**Verbose Logging**
```bash
# Enable detailed logging
python -m pktmask --verbose mask input.pcap -o output.pcap

# GUI debugging with Qt logging
QT_LOGGING_RULES="*.debug=true" python -m pktmask
```

**Performance Profiling**
```bash
# Profile performance
python -m cProfile -o profile.stats -m pktmask mask large_file.pcap -o output.pcap

# Analyze profile results
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(20)"
```

## 🤝 Contributing Guidelines

### Code Contribution Workflow

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/pktmask.git
   cd pktmask
   git remote add upstream https://github.com/originalowner/pktmask.git
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Development Checklist**
   - [ ] Code follows Black formatting standards
   - [ ] Imports organized with isort
   - [ ] All tests pass (`pytest tests/`)
   - [ ] Code passes linting (`flake8 src/`)
   - [ ] Type hints added where appropriate
   - [ ] Documentation updated for public APIs
   - [ ] Test coverage maintained or improved

4. **Commit and Push**
   ```bash
   # Stage changes
   git add .

   # Commit with descriptive message
   git commit -m "feat: add new TLS masking algorithm

   - Implement selective TLS-23 masking
   - Add support for TLS 1.3 extensions
   - Include comprehensive test coverage
   - Update documentation with usage examples"

   # Push to your fork
   git push origin feature/your-feature-name
   ```

5. **Create Pull Request**
   - Provide clear description of changes
   - Reference related issues
   - Include testing instructions
   - Add screenshots for UI changes

### Code Style Guidelines

**Python Code Standards**
```python
# Use type hints for all public functions
def process_packet(self, packet: Packet) -> ProcessingResult:
    """Process a single packet through the stage.

    Args:
        packet: The packet to process

    Returns:
        Processing result indicating action taken

    Raises:
        ProcessingError: If packet processing fails
    """
    pass

# Use descriptive variable names
packet_hash = self._calculate_packet_hash(packet)
anonymized_ip = self.anonymize_ip_address(original_ip)

# Follow Black formatting (88 character line limit)
very_long_function_call_with_many_parameters(
    first_parameter=value1,
    second_parameter=value2,
    third_parameter=value3,
)
```

**Documentation Standards**
- All public functions must have docstrings
- Use Google-style docstring format
- Include type information in docstrings
- Provide usage examples for complex functions
- Update README.md for user-facing changes

### Testing Requirements

**Unit Test Coverage**
- All new functions must have unit tests
- Aim for >90% code coverage
- Test both success and failure cases
- Use meaningful test names that describe the scenario

```python
def test_deduplication_removes_exact_duplicates():
    """Test that exact duplicate packets are properly removed."""
    # Arrange
    stage = UnifiedDeduplicationStage()
    packet1 = create_test_packet(payload="test")
    packet2 = create_test_packet(payload="test")  # Exact duplicate

    # Act
    result1 = stage.process_packet(packet1)
    result2 = stage.process_packet(packet2)

    # Assert
    assert result1 == ProcessingResult.KEEP
    assert result2 == ProcessingResult.DUPLICATE
```

**Integration Tests**
- Test complete workflows end-to-end
- Use realistic test data
- Verify file output correctness
- Test error handling and recovery

### Performance Considerations

**Optimization Guidelines**
- Profile before optimizing
- Focus on algorithmic improvements over micro-optimizations
- Use appropriate data structures (sets for lookups, deques for queues)
- Consider memory usage for large files
- Implement progress reporting for long-running operations

**Memory Management**
```python
# Good: Process packets in chunks
def process_large_file(self, input_file: str) -> None:
    with PcapReader(input_file) as reader:
        for packet_batch in reader.read_chunks(chunk_size=1000):
            self.process_packet_batch(packet_batch)

# Avoid: Loading entire file into memory
def process_large_file_bad(self, input_file: str) -> None:
    all_packets = list(PcapReader(input_file))  # Memory intensive!
    for packet in all_packets:
        self.process_packet(packet)
```

## 📚 Additional Resources

### External Documentation
- **[Scapy Documentation](https://scapy.readthedocs.io/)** - Packet manipulation library
- **[PyQt6 Documentation](https://doc.qt.io/qtforpython/)** - GUI framework
- **[tshark Manual](https://www.wireshark.org/docs/man-pages/tshark.html)** - Command-line packet analyzer
- **[RFC Index](https://www.rfc-editor.org/rfc-index.html)** - Network protocol specifications

### Internal Documentation
- **[Architecture Guide](../architecture/README.md)** - Detailed system design
- **[API Reference](../api/README.md)** - Programming interfaces
- **[User Guide](../user/README.md)** - End-user documentation
- **[Tools Documentation](../tools/README.md)** - Development tools

### Community and Support

**Getting Help**
- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Technical questions and community support
- **Developer Email**: ricky.wang@netis.com for direct technical inquiries

**Contributing to Documentation**
- Documentation source is in `docs/` directory
- Use Markdown format for all documentation
- Include code examples and diagrams where helpful
- Test documentation changes locally before submitting

## 📚 Organized Documentation Categories

### 🏗️ [Architecture Documentation](architecture/README.md)
Complete architectural analysis, design patterns, and system evolution
- Comprehensive architecture analysis
- Memory management implementation
- Legacy system elimination records

### 🧪 [Testing Documentation](testing/README.md)
Test strategy, validation reports, and quality assurance
- Test validation and usability reports
- Test cleanup and maintenance guides
- Test repair progress tracking

### 🧹 [Cleanup Documentation](cleanup/README.md)
Code cleanup, deprecated code removal, and maintenance activities
- Deprecated code cleanup checklists
- Dead code removal summaries
- Cleanup execution reports

### 📊 [Analysis Documentation](analysis/README.md)
Code analysis, performance reviews, and quality assessments
- Comprehensive code reviews
- Performance analysis reports
- Technical debt assessments
- Naming convention audits

---

*Last Updated: 2025-07-25*
*Documentation reorganized and cleaned up for better navigation*
