# PktMask Development Environment Setup - Complete

**Date**: 2025-10-10  
**Status**: ✅ Complete  
**Python Version**: 3.13.5  
**Virtual Environment**: `.venv/`

---

## 📋 Setup Summary

### ✅ Completed Steps

1. **Virtual Environment Created**
   - Location: `.venv/`
   - Python: 3.13.5
   - Pip: 25.2 (latest)

2. **Dependencies Installed**
   - Core dependencies: ✅ Installed
   - Development dependencies: ✅ Installed
   - Build dependencies: ✅ Installed
   - Performance monitoring: ✅ Installed

3. **Package Installation**
   - Installed in editable mode: `pip install -e ".[dev,build,performance]"`
   - All 59 packages installed successfully

4. **Verification Tests**
   - ✅ All core modules import successfully
   - ✅ CLI commands available
   - ✅ GUI modules load correctly
   - ✅ Unit tests pass (19/19 in test_config.py)

---

## 🔧 Installed Packages

### Core Dependencies
```
✅ Scapy           2.6.1      - Packet processing
✅ PyQt6           6.9.1      - GUI framework
✅ Typer           0.19.2     - CLI framework
✅ Pydantic        2.12.0     - Data validation
✅ PyYAML          6.0.3      - YAML support
✅ Jinja2          3.1.6      - Template engine
✅ Markdown        3.9        - Markdown rendering
```

### Development Tools
```
✅ Pytest          8.4.2      - Testing framework
✅ Black           25.9.0     - Code formatter
✅ Mypy            1.18.2     - Type checker
✅ Flake8          7.3.0      - Linter
✅ isort           6.1.0      - Import sorter
✅ pre-commit      4.3.0      - Git hooks
```

### Build Tools
```
✅ PyInstaller     6.16.0     - Binary builder
✅ setuptools      80.9.0     - Build system
✅ hatchling       (via pyproject.toml)
```

### Testing Extensions
```
✅ pytest-cov      7.0.0      - Coverage
✅ pytest-qt       4.5.0      - Qt testing
✅ pytest-mock     3.15.1     - Mocking
✅ pytest-xdist    3.8.0      - Parallel testing
✅ pytest-html     4.1.1      - HTML reports
```

### Performance Monitoring
```
✅ psutil          7.1.0      - System monitoring
✅ memory-profiler 0.61.0     - Memory profiling
```

---

## 🚀 Quick Start

### Activate Virtual Environment

**Option 1: Using convenience script (Recommended)**
```bash
source activate.sh
```

**Option 2: Manual activation**
```bash
source .venv/bin/activate
```

### Verify Installation
```bash
# Check Python version
python --version
# Output: Python 3.13.5

# Check pktmask installation
python -c "import pktmask; print('✅ pktmask installed')"

# Run quick test
pytest tests/unit/test_config.py -v
```

---

## 📚 Common Commands

### Development
```bash
# Launch GUI
pktmask

# CLI help
pktmask --help
pktmask process --help

# Process a file
pktmask process input.pcap -o output.pcap --dedup --anon --mask
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_config.py -v

# Run with coverage
pytest --cov=pktmask --cov-report=html

# Run only unit tests
pytest -m unit

# Run integration tests
pytest -m integration
```

### Code Quality
```bash
# Format code
black src/ tests/

# Check formatting (without changes)
black --check src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
```

### Pre-commit Hooks
```bash
# Install git hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

---

## 🔍 External Dependencies

### TShark (Wireshark)
```
✅ Installed: /usr/local/bin/tshark
✅ Version: 4.4.9
```

**Note**: TShark is required for some advanced features. If not installed:
```bash
# macOS
brew install wireshark

# Ubuntu/Debian
sudo apt-get install tshark

# CentOS/RHEL
sudo yum install wireshark
```

---

## 📁 Project Structure

```
PktMask/
├── .venv/                  # Virtual environment (ignored by git)
├── src/pktmask/           # Source code
│   ├── cli/               # CLI interface
│   ├── gui/               # GUI interface
│   ├── core/              # Core processing logic
│   ├── utils/             # Utilities
│   └── infrastructure/    # Infrastructure (logging, etc.)
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── e2e/               # End-to-end tests
├── docs/                  # Documentation
├── config/                # Configuration templates
├── scripts/               # Utility scripts
├── pyproject.toml         # Project configuration
├── pytest.ini             # Pytest configuration
└── activate.sh            # Convenience activation script
```

---

## 🐛 Troubleshooting

### Virtual Environment Issues

**Problem**: Virtual environment not activating
```bash
# Solution: Recreate virtual environment
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,build,performance]"
```

**Problem**: Import errors
```bash
# Solution: Reinstall in editable mode
pip install -e ".[dev,build,performance]"
```

### PyQt6 Issues

**Problem**: Qt platform plugin errors
```bash
# Solution: Set environment variable
export QT_QPA_PLATFORM=offscreen  # For headless testing
```

### Permission Issues

**Problem**: Permission denied when running scripts
```bash
# Solution: Make scripts executable
chmod +x activate.sh
chmod +x scripts/*.sh
```

---

## 📊 Environment Verification Checklist

- [x] Python 3.13.5 installed
- [x] Virtual environment created (`.venv/`)
- [x] Pip upgraded to latest (25.2)
- [x] All dependencies installed (59 packages)
- [x] pktmask package installed in editable mode
- [x] Core modules import successfully
- [x] CLI commands available
- [x] GUI modules load correctly
- [x] Unit tests pass
- [x] TShark available
- [x] Convenience scripts created

---

## 🎯 Next Steps

1. **Start Development**
   ```bash
   source activate.sh
   pktmask  # Launch GUI to verify
   ```

2. **Run Tests**
   ```bash
   pytest -v
   ```

3. **Set Up Git Hooks** (Optional but recommended)
   ```bash
   pre-commit install
   ```

4. **Review Documentation**
   - User Guide: `docs/user/README.md`
   - Developer Guide: `docs/dev/README.md`
   - Architecture: `docs/ARCHITECTURE_UNIFIED.md`

---

## 📝 Notes

- Virtual environment is in `.venv/` (ignored by git)
- Old `venv/` directory still exists but is also ignored
- All dependencies are pinned in `pyproject.toml`
- Use `activate.sh` for convenient activation with status display

---

## 🆘 Getting Help

If you encounter issues:

1. Check this document's troubleshooting section
2. Review `docs/dev/README.md`
3. Check GitHub issues
4. Contact: ricky.wang@netis.com

---

**Environment Status**: ✅ **READY FOR DEVELOPMENT**

Last Updated: 2025-10-10

