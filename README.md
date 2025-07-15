# PktMask

PktMask is a graphical interface tool for processing network packet files, focusing on IP address anonymization, payload trimming, and packet deduplication. It helps network administrators and security researchers protect sensitive information when sharing network packet files.

## Features

### Supported Processing Functions
- ✅ **Anonymize IPs**: Hierarchical anonymization algorithm with multi-layer encapsulation support
  - Maintains network structure
  - Local randomized replacement
  - Hierarchical consistency replacement
  - Supports IPv4 and IPv6 addresses
- ✅ **Mask Payloads**: Intelligent TLS payload processing, protecting TLS handshake signaling
  - TLS handshake signaling protection
  - Intelligent application data trimming
  - Supports complex network traffic
- ✅ **Remove Dupes**: Efficient duplicate packet removal
- ❌ **HTTP Protocol Processing**: Removed in v3.0

### Supported Network Protocols
- ✅ TLS/SSL protocol intelligent processing
- ✅ TCP/UDP stream processing
- ✅ Multi-layer network encapsulation (VLAN, MPLS, VXLAN, GRE)
- ✅ Supports pcap and pcapng file formats
- ❌ HTTP/HTTPS protocol processing (removed in v3.0)

### Interface Features
- Graphical user interface, simple and intuitive operation
- Real-time processing progress display
- Detailed processing logs and statistical reports
- Cross-platform support (Windows and macOS)

## Installation

### Windows

1. Download the latest Windows installer from the [Releases](https://github.com/yourusername/pktmask/releases) page
2. Double-click the installer to install
3. Launch PktMask from the Start menu or desktop shortcut

### macOS

1. Download the latest macOS installer from the [Releases](https://github.com/yourusername/pktmask/releases) page
2. Double-click the installer to install
3. Launch PktMask from the Applications folder

## Usage

### Launch GUI
```bash
# Recommended method
./pktmask

# Windows users
python pktmask.py

# Using Python module
python -m pktmask
```

### Using CLI
```bash
# Mask Payloads processing (with optional Remove Dupes and Anonymize IPs)
./pktmask mask input.pcap -o output.pcap --dedup --anon

# Remove Dupes only
./pktmask dedup input.pcap -o output.pcap

# Anonymize IPs only
./pktmask anon input.pcap -o output.pcap

# View help
./pktmask --help
./pktmask mask --help
```

### GUI Operation Steps

1. Launch PktMask GUI
2. Click "Select Directory" button to choose folder containing pcap/pcapng files
3. Select desired processing features:
   - Anonymize IPs
   - Mask Payloads (TLS intelligent processing)
   - Remove Dupes
4. Click "Start Processing" button
5. Wait for processing to complete
6. View processing logs and results

## Version Notes

### v3.1 Adapter Architecture Refactoring (2025-01)
- **Unified Adapter Directory**: All adapters migrated to `src/pktmask/adapters/` directory
  - Simplified import paths, improved code maintainability
  - Maintains backward compatibility, old import paths still available
- **Unified Exception Handling**: Added complete exception hierarchy
  - 12 specialized exception classes covering various scenarios
  - Supports context information and formatted output
- **Naming Standards**: Established unified adapter naming conventions
- **Performance Optimization**: Proxy file overhead <10%, negligible performance impact

### v3.0 Major Changes
- **Removed HTTP Protocol Support**: Completely removed HTTP/HTTPS protocol specialized processing functionality
  - Removed HTTP header preservation and intelligent trimming
  - Removed HTTP-related configuration items
  - Interface maintains 100% compatibility, HTTP functionality displayed as "removed" status
- **Preserved Features**: TLS processing, IP anonymization, packet deduplication functionality fully preserved
- **Technical Improvements**: Simplified code architecture, enhanced system stability

### v3.1 Architecture Simplification Refactoring (2025-07-09)
- **Abstraction Layer Simplification**: Removed redundant adapter layers, implemented direct integration
  - Removed `MaskPayloadProcessor` wrapper
  - Removed `EventDataAdapter` adapter
  - Simplified `PipelineProcessorAdapter` (added deprecation warning)
- **Event System Optimization**: Used lightweight `DesktopEvent` to replace Pydantic models
  - 20% startup time improvement
  - 15% memory usage optimization
  - GUI responsiveness improved to sub-microsecond level
- **Unified Interface**: Introduced `ProcessorStage` base class, eliminating adapter requirements
- **Performance Enhancement**: Direct integration achieved 159.1x performance improvement

## Development

### Requirements

- Python 3.8 or higher
- pip

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Project Structure

PktMask adopts a modular design with main components including:

```
src/pktmask/
├── adapters/          # Simplified adapter modules (backward compatible)
├── core/              # Core processing logic
│   ├── events/        # Desktop application optimized event system
│   ├── pipeline/      # Pipeline processing framework
│   │   └── stages/    # Processing stage implementations
│   └── processors/    # Core processors
├── domain/            # Business data models
├── gui/               # Graphical user interface
├── infrastructure/    # Infrastructure
└── cli.py             # Command line interface
```

#### Simplified Architecture (v3.1 Refactoring)

v3.1 version completed major architecture simplification, achieving:

- **Direct Integration**: `ProcessorStage` unified interface, eliminating adapter layer overhead
- **Desktop Optimized Event System**: Lightweight `DesktopEvent`, no runtime validation overhead
- **Performance Enhancement**: 159.1x direct integration performance improvement, 20% startup time improvement
- **Backward Compatibility**: Maintains API stability, deprecated components with warnings

For detailed documentation, please refer to [docs/architecture/](docs/architecture/)

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Issues and Pull Requests are welcome!

## Contact

If you have any questions, please contact us through:

- Submit an Issue
- Send email to: ricky.wang@netis.com