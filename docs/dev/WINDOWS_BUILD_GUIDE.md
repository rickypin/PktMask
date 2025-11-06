# Windows Build Guide for PktMask

This guide explains how to build Windows executable packages for PktMask.

## Overview

PktMask uses PyInstaller to create standalone Windows executables. There are two ways to build:

1. **GitHub Actions (Recommended)** - Automated builds on push tags
2. **Local Build** - Manual builds on Windows machines

## Method 1: GitHub Actions (Recommended)

### Prerequisites

- Push access to the repository
- Git installed locally

### Steps

1. **Ensure all changes are committed:**
   ```bash
   git add .
   git commit -m "chore: prepare for release"
   git push
   ```

2. **Create and push a version tag:**
   ```bash
   # Create a new version tag (e.g., v0.2.1)
   git tag v0.2.1
   
   # Push the tag to trigger the build
   git push origin v0.2.1
   ```

3. **Monitor the build:**
   - Go to GitHub Actions tab in your repository
   - Watch the "Build and Release" workflow
   - Wait for both Windows and macOS builds to complete

4. **Download the artifacts:**
   - Once the build succeeds, go to the Releases page
   - Download `PktMask-Windows.zip`
   - Extract and test the executable

### Build Configuration

The GitHub Actions workflow (`.github/workflows/build.yml`) performs these steps:

1. Sets up Python 3.11
2. Installs dependencies from `pyproject.toml`
3. Runs PyInstaller with `PktMask-Windows.spec`
4. Uploads the built package as an artifact
5. Creates a GitHub Release with the Windows zip file

### Troubleshooting GitHub Actions

If the build fails:

1. **Check the build logs:**
   - Click on the failed workflow run
   - Expand the "Build Windows Installer" step
   - Look for error messages

2. **Common issues:**
   - **Missing dependencies:** Ensure all packages are in `pyproject.toml`
   - **Import errors:** Add missing modules to `hiddenimports` in `PktMask-Windows.spec`
   - **File not found:** Check that all data files are listed in `common_datas`

3. **Test locally first:**
   ```bash
   # Run the validation script
   bash scripts/build/test_build_windows.sh
   ```

## Method 2: Local Build on Windows

### Prerequisites

- Windows 10 or later
- Python 3.10+ installed
- Git for Windows (optional, for cloning)

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/pktmask.git
   cd pktmask
   ```

2. **Create and activate virtual environment:**
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```cmd
   pip install -e ".[build]"
   ```

4. **Run PyInstaller:**
   ```cmd
   pyinstaller PktMask-Windows.spec
   ```

5. **Test the executable:**
   ```cmd
   cd dist\PktMask
   PktMask.exe
   ```

6. **Create distribution package:**
   ```cmd
   # Compress the dist\PktMask folder
   # Use 7-Zip, WinRAR, or Windows built-in compression
   ```

### Build Output

After a successful build, you'll find:

```
dist/
└── PktMask/
    ├── PktMask.exe          # Main executable
    ├── _internal/           # Dependencies and libraries
    │   ├── *.dll            # Required DLLs
    │   ├── PyQt6/           # Qt libraries
    │   ├── scapy/           # Scapy modules
    │   └── ...
    └── resources/           # Application resources
        ├── log_template.html
        ├── summary.md
        └── ...
```

## Build Configuration Files

### PktMask-Windows.spec

This is the PyInstaller specification file for Windows builds. Key sections:

```python
# Hidden imports - modules that PyInstaller might miss
windows_hidden_imports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'pktmask',
    'scapy.all',
    # ... more imports
]

# Data files to include
common_datas = [
    ("config/templates/log_template.html", "resources"),
    ("config/templates/summary.md", "resources"),
    # ... more data files
]

# Executable settings
exe = EXE(
    name='PktMask',
    icon='assets/PktMask.ico',
    console=False,  # No console window
    upx=False,      # Disable UPX compression
)
```

### scripts/build/pyinstaller_common.py

Shared configuration between Windows and macOS builds:

- `common_datas`: Data files to bundle
- `common_hiddenimports`: Common hidden imports

## Testing the Build

### Automated Testing

Run the validation script before building:

```bash
bash scripts/build/test_build_windows.sh
```

This checks:
- Spec file syntax
- Required packages
- Asset files
- Launcher script

### Manual Testing

After building, test these features:

1. **Launch the application:**
   - Double-click `PktMask.exe`
   - Verify the GUI opens without errors

2. **Load a pcap file:**
   - Use File → Open
   - Select a test pcap file
   - Verify packets are displayed

3. **Mask IP addresses:**
   - Click "Start Masking"
   - Verify the process completes
   - Check the output file

4. **Generate reports:**
   - Enable report generation
   - Verify HTML report is created

## Distribution

### Creating a Release Package

1. **Compress the build:**
   ```cmd
   cd dist
   # Right-click PktMask folder → Send to → Compressed (zipped) folder
   # Or use 7-Zip: 7z a PktMask-Windows.zip PktMask\
   ```

2. **Test the package:**
   - Extract on a clean Windows machine
   - Run `PktMask.exe`
   - Verify all features work

3. **Upload to GitHub Releases:**
   - Go to Releases page
   - Click "Create a new release"
   - Upload `PktMask-Windows.zip`
   - Add release notes

### System Requirements

Document these requirements for users:

- **OS:** Windows 10 or later (64-bit)
- **RAM:** 4GB minimum, 8GB recommended
- **Disk:** 200MB for application + space for pcap files
- **Permissions:** Administrator rights for packet capture (if using live capture)

## Troubleshooting

### Common Build Errors

1. **"Module not found" errors:**
   - Add the module to `hiddenimports` in `PktMask-Windows.spec`

2. **"File not found" errors:**
   - Check that data files exist in the specified paths
   - Update paths in `common_datas` if needed

3. **PyQt6 import errors:**
   - Ensure PyQt6 is installed: `pip install PyQt6`
   - Check that `PyQt6.sip` is in hidden imports

4. **Scapy errors:**
   - Install Npcap on Windows (for packet capture)
   - Add scapy submodules to hidden imports

### Runtime Errors

1. **Application won't start:**
   - Check Windows Event Viewer for error details
   - Run from command line to see error messages:
     ```cmd
     cd dist\PktMask
     PktMask.exe
     ```

2. **Missing DLL errors:**
   - Install Visual C++ Redistributable
   - Rebuild with `--collect-all` for problematic packages

3. **Qt platform plugin errors:**
   - Ensure Qt plugins are included in the build
   - Check `_internal/PyQt6/Qt6/plugins/platforms/`

## Advanced Configuration

### Reducing Build Size

1. **Exclude unnecessary modules:**
   ```python
   excludes=['tkinter', 'matplotlib', 'numpy']
   ```

2. **Use UPX compression (optional):**
   ```python
   upx=True,
   upx_exclude=['vcruntime140.dll', 'python*.dll']
   ```

### Adding Custom Icons

1. Create/obtain a `.ico` file (256x256 recommended)
2. Place in `assets/PktMask.ico`
3. Reference in spec file:
   ```python
   icon='assets/PktMask.ico'
   ```

### Debug Builds

For debugging, enable console output:

```python
exe = EXE(
    console=True,  # Show console window
    debug=True,    # Enable debug output
)
```

## References

- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [Scapy Documentation](https://scapy.readthedocs.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## Support

If you encounter issues:

1. Check the [GitHub Issues](https://github.com/yourusername/pktmask/issues)
2. Review build logs in GitHub Actions
3. Run the validation script: `bash scripts/build/test_build_windows.sh`
4. Create a new issue with:
   - Error messages
   - Build logs
   - System information

