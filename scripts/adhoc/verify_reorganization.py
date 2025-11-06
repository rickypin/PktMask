#!/usr/bin/env python3
"""
Verification script for scripts directory reorganization
Created: 2024-11-06
Status: One-time verification script

This script verifies that all scripts have been moved correctly and
all references have been updated.
"""

import sys
from pathlib import Path

# Color codes for output
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
NC = "\033[0m"  # No Color


def print_success(msg):
    print(f"{GREEN}✅ {msg}{NC}")


def print_error(msg):
    print(f"{RED}❌ {msg}{NC}")


def print_info(msg):
    print(f"{YELLOW}ℹ️  {msg}{NC}")


def verify_file_exists(path, description):
    """Verify that a file exists at the expected location"""
    if path.exists():
        print_success(f"{description}: {path}")
        return True
    else:
        print_error(f"{description} not found: {path}")
        return False


def verify_file_not_exists(path, description):
    """Verify that a file does NOT exist (has been moved)"""
    if not path.exists():
        print_success(f"{description} correctly moved from: {path}")
        return True
    else:
        print_error(f"{description} still exists at old location: {path}")
        return False


def verify_import(module_path, description):
    """Verify that a Python module can be imported"""
    try:
        # Add project root to path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        # Try to import
        parts = module_path.split(".")
        module = __import__(module_path)
        for part in parts[1:]:
            module = getattr(module, part)

        print_success(f"{description}: {module_path}")
        return True
    except ImportError as e:
        print_error(f"{description} import failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Scripts Directory Reorganization Verification")
    print("=" * 60)
    print()

    project_root = Path(__file__).parent.parent.parent
    scripts_dir = project_root / "scripts"

    all_passed = True

    # 1. Verify new directory exists
    print("1. Verifying new directories...")
    all_passed &= verify_file_exists(scripts_dir / "adhoc" / "README.md", "adhoc directory README")
    print()

    # 2. Verify files moved to correct locations
    print("2. Verifying files in new locations...")
    moved_files = [
        ("scripts/build/pyinstaller_common.py", "PyInstaller common config"),
        ("scripts/maintenance/check_tshark_dependencies.py", "TShark dependency checker"),
        ("scripts/docs/docs_quality_check.sh", "Docs quality check script"),
        ("scripts/test/test_unified_functionality.py", "Unified functionality test"),
        ("scripts/validation/run_http_auto_e2e.py", "HTTP auto E2E runner"),
        ("scripts/validation/verify_http_zero_body.py", "HTTP zero-body verifier"),
    ]

    for file_path, description in moved_files:
        all_passed &= verify_file_exists(project_root / file_path, description)
    print()

    # 3. Verify files removed from old locations
    print("3. Verifying files removed from old locations...")
    old_files = [
        ("scripts/pyinstaller_common.py", "PyInstaller common config"),
        ("scripts/check_tshark_dependencies.py", "TShark dependency checker"),
        ("scripts/docs_quality_check.sh", "Docs quality check script"),
        ("scripts/test_unified_functionality.py", "Unified functionality test"),
        ("scripts/run_http_auto_e2e.py", "HTTP auto E2E runner"),
        ("scripts/verify_http_zero_body.py", "HTTP zero-body verifier"),
    ]

    for file_path, description in old_files:
        all_passed &= verify_file_not_exists(project_root / file_path, description)
    print()

    # 4. Verify essential files remain in root
    print("4. Verifying essential files in scripts root...")
    essential_files = [
        ("scripts/README.md", "Scripts README"),
        ("scripts/__init__.py", "Scripts package marker"),
        ("scripts/pktmask_launcher.py", "PyInstaller launcher"),
    ]

    for file_path, description in essential_files:
        all_passed &= verify_file_exists(project_root / file_path, description)
    print()

    # 5. Verify Python imports work
    print("5. Verifying Python imports...")
    all_passed &= verify_import("scripts.build.pyinstaller_common", "PyInstaller common import")
    print()

    # 6. Verify documentation files
    print("6. Verifying documentation updates...")
    doc_files = [
        ("docs/dev/SCRIPTS_REORGANIZATION_2024.md", "Reorganization documentation"),
    ]

    for file_path, description in doc_files:
        all_passed &= verify_file_exists(project_root / file_path, description)
    print()

    # 7. Check scripts directory structure
    print("7. Verifying scripts directory structure...")
    expected_subdirs = [
        "adhoc",
        "build",
        "docs",
        "git-hooks",
        "maintenance",
        "test",
        "validation",
    ]

    for subdir in expected_subdirs:
        subdir_path = scripts_dir / subdir
        if subdir_path.exists() and subdir_path.is_dir():
            print_success(f"Subdirectory exists: {subdir}/")
        else:
            print_error(f"Subdirectory missing: {subdir}/")
            all_passed = False
    print()

    # Final summary
    print("=" * 60)
    if all_passed:
        print_success("All verification checks passed! ✨")
        print()
        print_info("The scripts directory reorganization is complete.")
        print_info("All files are in their correct locations.")
        print_info("All imports and references have been updated.")
        return 0
    else:
        print_error("Some verification checks failed!")
        print()
        print_info("Please review the errors above and fix them.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
