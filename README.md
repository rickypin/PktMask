# PktMask

[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#system-requirements)
[![Version](https://img.shields.io/badge/Version-v3.1+-blue.svg)](#installation)

**Secure Network Data Processing Made Simple**

PktMask is a user-friendly desktop application that helps network professionals safely share and analyze network packet captures. Whether you're a network administrator, security analyst, or researcher, PktMask removes sensitive information from your packet files while preserving their analytical value.

## 🔒 Why PktMask?

### The Problem
Network packet captures contain sensitive information that can't be shared safely:
- **Private IP addresses** that reveal internal network structure
- **Sensitive payload data** including passwords, personal information, and proprietary data
- **Duplicate packets** that bloat file sizes and complicate analysis
- **Compliance requirements** that mandate data sanitization before sharing

### The Solution
PktMask automatically sanitizes your network captures while maintaining their usefulness for:
- **Security incident analysis** - Share evidence without exposing sensitive data
- **Network troubleshooting** - Collaborate with vendors while protecting privacy
- **Research and education** - Use real network data in academic or training environments
- **Compliance reporting** - Meet regulatory requirements for data protection

## ⚡ What PktMask Does

PktMask provides three essential functions to make your network data safe to share:

### 🔄 Remove Dupes
**Eliminates duplicate packets to reduce file size and improve analysis**
- Automatically detects and removes identical packets
- Reduces file sizes by up to 50% in typical network captures
- Speeds up analysis tools by eliminating redundant data
- Preserves the first occurrence of each unique packet

### 🎭 Anonymize IPs
**Replaces real IP addresses with consistent fake ones**
- Protects internal network topology from exposure
- Maintains relationships between communicating hosts
- Supports both IPv4 and IPv6 addresses
- Works with complex network setups (VLANs, tunnels, etc.)

### 🛡️ Mask Payloads
**Removes sensitive data while keeping protocol structure**
- Intelligently handles encrypted traffic (TLS/SSL)
- Preserves connection handshakes needed for analysis
- Removes application data that might contain sensitive information
- Maintains packet timing and flow characteristics

## 💼 Common Use Cases

**Security Incident Response**
- Share attack evidence with external security teams
- Collaborate with law enforcement while protecting victim privacy
- Provide sanitized data to security vendors for analysis

**Network Troubleshooting**
- Send network captures to equipment vendors for support
- Share problematic traffic patterns with consultants
- Collaborate across teams without exposing sensitive systems

**Training and Research**
- Create realistic datasets for security training
- Provide anonymized data for academic research
- Build test cases without using production data

**Compliance and Auditing**
- Meet regulatory requirements for data sharing
- Prepare evidence for compliance audits
- Document network behavior without exposing sensitive details

## � System Requirements

**Operating Systems:**
- Windows 10 or later
- macOS 10.14 (Mojave) or later
- Linux (Ubuntu 18.04+, CentOS 7+, or equivalent)

**Hardware:**
- 4 GB RAM minimum (8 GB recommended for large files)
- 1 GB available disk space
- Network interface for packet capture (if capturing live traffic)

**Dependencies:**
- Python 3.8 or later (automatically installed with binary releases)
- Wireshark/tshark (recommended for advanced features)

## 📦 Installation

### Option 1: Download Ready-to-Use Application (Recommended)

**Windows Users:**
1. Download the latest `.exe` installer from [Releases](https://github.com/yourusername/pktmask/releases)
2. Run the installer and follow the setup wizard
3. Launch PktMask from the Start menu or desktop shortcut

**macOS Users:**
1. Download the latest `.dmg` package from [Releases](https://github.com/yourusername/pktmask/releases)
2. Open the `.dmg` file and drag PktMask to Applications
3. Launch PktMask from Applications folder

### Option 2: Install from Source (Advanced Users)

```bash
# Download and setup
git clone https://github.com/yourusername/pktmask.git
cd pktmask

# Install (creates virtual environment automatically)
pip install -e .

# Run the application
python -m pktmask
```

### Verify Installation

After installation, test that PktMask works correctly:

1. Launch PktMask
2. Click "Select Directory" and choose a folder with sample pcap files
3. Enable "Remove Dupes" and click "Start Processing"
4. Check that processed files appear in the output directory

## Quick Verification

After installation, you can quickly verify that all functions are working correctly:

```bash
# Activate virtual environment (if using source installation)
source .venv/bin/activate

# Test basic mask functionality
python -m pktmask mask tests/data/tls/ssl_3.pcap -o /tmp/test_basic.pcap --mode basic

# Test enhanced mask with IP anonymization
python -m pktmask mask tests/data/tls/ssl_3.pcap -o /tmp/test_enhanced.pcap --anonymize-ips --mode enhanced --verbose

# Test full pipeline (dedup + anon + mask)
python -m pktmask mask tests/data/tls/ssl_3.pcap -o /tmp/test_full.pcap --remove-dupes --anonymize-ips --mode enhanced --verbose
```

Expected results:
- ✅ All commands should complete successfully
- ✅ Output files should be generated in `/tmp/`
- ✅ Enhanced mode should process ~101 packets and modify ~59 packets
- ✅ IP anonymization should modify all 101 packets

## 🚀 Quick Start Guide

### Using the Graphical Interface (Recommended)

1. **Launch PktMask**
   - Windows: Click the PktMask icon on your desktop or Start menu
   - macOS: Open PktMask from Applications folder
   - Linux: Run `python -m pktmask` in terminal

2. **Select Your Files**
   - Click "Select Directory" button
   - Choose the folder containing your .pcap or .pcapng files
   - PktMask will automatically find all packet capture files

3. **Choose What to Do**
   - ✅ **Remove Dupes**: Check this to eliminate duplicate packets
   - ✅ **Anonymize IPs**: Check this to replace real IP addresses with fake ones
   - ✅ **Mask Payloads**: Check this to remove sensitive data from packets

4. **Start Processing**
   - Click "Start Processing" button
   - Watch the progress bar and log messages
   - Processed files will appear in a new "output" folder

5. **Review Results**
   - Check the output folder for your sanitized files
   - Review the processing log for details about what was changed
   - Original files are never modified - they remain safe

### Example Workflows

**Scenario 1: Sharing with External Support**
```
Goal: Send network capture to vendor for troubleshooting
Steps: Enable "Anonymize IPs" + "Mask Payloads"
Result: Vendor can analyze network behavior without seeing your real IPs or sensitive data
```

**Scenario 2: Reducing File Size for Analysis**
```
Goal: Clean up large capture files before detailed analysis
Steps: Enable "Remove Dupes" only
Result: Smaller files that load faster in analysis tools like Wireshark
```

**Scenario 3: Complete Sanitization**
```
Goal: Maximum privacy protection for sharing or archiving
Steps: Enable all three options (Remove Dupes + Anonymize IPs + Mask Payloads)
Result: Fully sanitized files safe for any sharing scenario
```

## ❓ Frequently Asked Questions

**Q: Will PktMask modify my original files?**
A: No, PktMask never changes your original files. It creates new processed files in an output directory.

**Q: How much does file size typically reduce with "Remove Dupes"?**
A: Most network captures see 30-50% size reduction, though this varies based on network conditions.

**Q: Can I undo the anonymization to get back real IP addresses?**
A: No, anonymization is one-way for security. PktMask doesn't store the mapping between real and fake IPs.

**Q: What file formats does PktMask support?**
A: PktMask works with standard .pcap and .pcapng files created by Wireshark, tcpdump, and similar tools.

**Q: Is PktMask safe to use on sensitive networks?**
A: Yes, PktMask runs locally on your computer and doesn't send data anywhere. All processing happens offline.

## 🆘 Getting Help

**For Users:**
- Check the [User Guide](docs/user/README.md) for detailed instructions
- Report issues on [GitHub Issues](https://github.com/yourusername/pktmask/issues)
- Email support: ricky.wang@netis.com

**For Developers:**
- See [Developer Documentation](docs/dev/README.md) for technical details
- Review [API Documentation](docs/api/README.md) for integration
- Check [Architecture Guide](docs/architecture/README.md) for system design

## 📄 License and Legal

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Important Notes:**
- PktMask is provided "as-is" without warranty
- Users are responsible for compliance with local privacy and data protection laws
- Always verify that processed files meet your security requirements before sharing

---

**PktMask** - Making network data safe to share, one packet at a time.