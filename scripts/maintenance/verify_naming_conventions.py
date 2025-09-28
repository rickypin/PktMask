#!/usr/bin/env python3
"""
Naming Convention Verification Script

Verifies that all naming conventions have been properly standardized across the PktMask codebase.
Checks for deprecated terms and ensures consistent terminology usage.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Deprecated terms that should not appear in the codebase
DEPRECATED_TERMS = {
    # GUI Display Text (should be standardized)
    "IP Anonymization": "Anonymize IPs",
    "Packet Deduplication": "Remove Dupes",
    "Payload Masking": "Mask Payloads",
    "Remove Duplicates": "Remove Dupes",
    "Mask IP": "Anonymize IPs",
    "Trim Packets": "Mask Payloads",
    # Code identifiers (internal)
    "unified_deduplication": "dedup_stage",
    "unified_ip_anonymization": "anonymize_stage",
}

# Chinese characters pattern
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")

# Files to check (exclude certain directories)
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "venv",
    ".venv",
    "build",
    "dist",
    "*.egg-info",
    "backup_refactor_*",
    "output",
    "tests/data",
}

INCLUDE_EXTENSIONS = {".py", ".md", ".yaml", ".yml", ".txt", ".sh"}


def find_files_to_check() -> List[Path]:
    """Find all files that should be checked for naming conventions."""
    files_to_check = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Remove excluded directories
        dirs[:] = [d for d in dirs if not any(d.startswith(excl.rstrip("*")) for excl in EXCLUDE_DIRS)]

        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in INCLUDE_EXTENSIONS:
                files_to_check.append(file_path)

    return files_to_check


def check_deprecated_terms(file_path: Path) -> List[Tuple[int, str, str]]:
    """Check for deprecated terms in a file."""
    issues = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                for deprecated, standard in DEPRECATED_TERMS.items():
                    if deprecated in line:
                        issues.append((line_num, deprecated, standard))
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")

    return issues


def check_chinese_text(file_path: Path) -> List[Tuple[int, str]]:
    """Check for Chinese characters in a file."""
    issues = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                if CHINESE_PATTERN.search(line):
                    # Extract the Chinese text
                    chinese_matches = CHINESE_PATTERN.findall(line)
                    chinese_text = ", ".join(chinese_matches)
                    issues.append((line_num, chinese_text))
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")

    return issues


def check_gui_text_consistency(file_path: Path) -> List[Tuple[int, str]]:
    """Check for GUI text consistency in specific files."""
    issues = []

    # Only check GUI-related files
    if "gui" not in str(file_path) and "enums.py" not in str(file_path):
        return issues

    # Patterns that should use standardized terms
    gui_patterns = [
        (r'"[^"]*IP Anonymization[^"]*"', 'Should use "Anonymize IPs"'),
        (r'"[^"]*Packet Deduplication[^"]*"', 'Should use "Remove Dupes"'),
        (r'"[^"]*Payload Masking[^"]*"', 'Should use "Mask Payloads"'),
        (r'"[^"]*Remove Duplicates[^"]*"', 'Should use "Remove Dupes"'),
        (r'"[^"]*Mask IP[^"]*"', 'Should use "Anonymize IPs"'),
        (r'"[^"]*Trim Packets[^"]*"', 'Should use "Mask Payloads"'),
    ]

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                for pattern, message in gui_patterns:
                    if re.search(pattern, line):
                        issues.append((line_num, message))
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")

    return issues


def generate_report(files_to_check: List[Path]) -> Dict:
    """Generate a comprehensive naming convention report."""
    report = {
        "total_files_checked": len(files_to_check),
        "deprecated_terms": {},
        "chinese_text": {},
        "gui_inconsistencies": {},
        "summary": {
            "files_with_deprecated_terms": 0,
            "files_with_chinese_text": 0,
            "files_with_gui_issues": 0,
            "total_deprecated_instances": 0,
            "total_chinese_instances": 0,
            "total_gui_issues": 0,
        },
    }

    for file_path in files_to_check:
        rel_path = file_path.relative_to(PROJECT_ROOT)

        # Check deprecated terms
        deprecated_issues = check_deprecated_terms(file_path)
        if deprecated_issues:
            report["deprecated_terms"][str(rel_path)] = deprecated_issues
            report["summary"]["files_with_deprecated_terms"] += 1
            report["summary"]["total_deprecated_instances"] += len(deprecated_issues)

        # Check Chinese text
        chinese_issues = check_chinese_text(file_path)
        if chinese_issues:
            report["chinese_text"][str(rel_path)] = chinese_issues
            report["summary"]["files_with_chinese_text"] += 1
            report["summary"]["total_chinese_instances"] += len(chinese_issues)

        # Check GUI consistency
        gui_issues = check_gui_text_consistency(file_path)
        if gui_issues:
            report["gui_inconsistencies"][str(rel_path)] = gui_issues
            report["summary"]["files_with_gui_issues"] += 1
            report["summary"]["total_gui_issues"] += len(gui_issues)

    return report


def print_report(report: Dict):
    """Print the naming convention verification report."""
    print("=" * 80)
    print("🔍 PktMask Naming Convention Verification Report")
    print("=" * 80)

    summary = report["summary"]
    print("\n📊 Summary:")
    print(f"   Total files checked: {report['total_files_checked']}")
    print(f"   Files with deprecated terms: {summary['files_with_deprecated_terms']}")
    print(f"   Files with Chinese text: {summary['files_with_chinese_text']}")
    print(f"   Files with GUI inconsistencies: {summary['files_with_gui_issues']}")
    print(f"   Total deprecated instances: {summary['total_deprecated_instances']}")
    print(f"   Total Chinese text instances: {summary['total_chinese_instances']}")
    print(f"   Total GUI issues: {summary['total_gui_issues']}")

    # Detailed reports
    if report["deprecated_terms"]:
        print("\n🚫 Deprecated Terms Found:")
        for file_path, issues in report["deprecated_terms"].items():
            print(f"\n   📄 {file_path}:")
            for line_num, deprecated, standard in issues:
                print(f"      Line {line_num}: '{deprecated}' → should be '{standard}'")

    if report["chinese_text"]:
        print("\n🈶 Chinese Text Found:")
        for file_path, issues in report["chinese_text"].items():
            print(f"\n   📄 {file_path}:")
            for line_num, chinese_text in issues:
                print(f"      Line {line_num}: Contains Chinese text: {chinese_text}")

    if report["gui_inconsistencies"]:
        print("\n🖥️ GUI Text Inconsistencies:")
        for file_path, issues in report["gui_inconsistencies"].items():
            print(f"\n   📄 {file_path}:")
            for line_num, message in issues:
                print(f"      Line {line_num}: {message}")

    # Overall status
    total_issues = (
        summary["total_deprecated_instances"] + summary["total_chinese_instances"] + summary["total_gui_issues"]
    )

    print(f"\n{'='*80}")
    if total_issues == 0:
        print("✅ SUCCESS: All naming conventions are properly standardized!")
        print("   No deprecated terms, Chinese text, or GUI inconsistencies found.")
    else:
        print(f"❌ ISSUES FOUND: {total_issues} naming convention issues detected.")
        print("   Please review and fix the issues listed above.")
    print("=" * 80)

    return total_issues == 0


def main():
    """Main function to run the naming convention verification."""
    print("🔍 Starting PktMask naming convention verification...")

    # Find files to check
    files_to_check = find_files_to_check()
    print(f"📁 Found {len(files_to_check)} files to check")

    # Generate report
    report = generate_report(files_to_check)

    # Print report
    success = print_report(report)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
