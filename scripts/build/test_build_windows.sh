#!/bin/bash
# Test script for Windows build configuration
# This script validates the build setup before pushing to GitHub Actions

set -e  # Exit on error

echo "=== PktMask Windows Build Test ==="
echo ""

# Check if we're in the project root
if [ ! -f "PktMask-Windows.spec" ]; then
    echo "Error: PktMask-Windows.spec not found. Please run from project root."
    exit 1
fi

echo "✓ Found PktMask-Windows.spec"

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: Virtual environment not activated"
    echo "Attempting to activate .venv..."
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        echo "✓ Activated .venv"
    else
        echo "Error: .venv not found. Please create a virtual environment first."
        exit 1
    fi
fi

echo "✓ Virtual environment active: $VIRTUAL_ENV"

# Check Python version
PYTHON_VERSION=$(python3 --version)
echo "✓ Python version: $PYTHON_VERSION"

# Check if required packages are installed
echo ""
echo "Checking required packages..."

REQUIRED_PACKAGES=("pyinstaller" "pyinstaller-hooks-contrib" "scapy" "PyQt6")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if python3 -c "import $package" 2>/dev/null; then
        echo "✓ $package installed"
    else
        echo "✗ $package NOT installed"
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -ne 0 ]; then
    echo ""
    echo "Missing packages detected. Installing..."
    pip install "${MISSING_PACKAGES[@]}"
fi

# Check if assets exist
echo ""
echo "Checking assets..."
if [ -f "assets/PktMask.ico" ]; then
    echo "✓ Windows icon found"
else
    echo "✗ Windows icon NOT found (assets/PktMask.ico)"
fi

# Check if launcher script exists
if [ -f "scripts/pktmask_launcher.py" ]; then
    echo "✓ Launcher script found"
else
    echo "✗ Launcher script NOT found"
    exit 1
fi

# Check if pyinstaller_common.py exists
if [ -f "scripts/build/pyinstaller_common.py" ]; then
    echo "✓ PyInstaller common config found"
else
    echo "✗ PyInstaller common config NOT found"
    exit 1
fi

# Validate spec file syntax
echo ""
echo "Validating PktMask-Windows.spec syntax..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    with open('PktMask-Windows.spec', 'r') as f:
        spec_content = f.read()
    compile(spec_content, 'PktMask-Windows.spec', 'exec')
    print('✓ Spec file syntax is valid')
except SyntaxError as e:
    print(f'✗ Spec file syntax error: {e}')
    sys.exit(1)
"

echo ""
echo "=== All checks passed! ==="
echo ""
echo "To build the Windows package, run:"
echo "  pyinstaller PktMask-Windows.spec"
echo ""
echo "Note: This script only validates the configuration."
echo "Actual Windows builds should be done on a Windows machine or via GitHub Actions."

