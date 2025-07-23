#!/usr/bin/env python3
"""
Documentation synchronization check script

Checks if components referenced in documentation exist in the code, helping identify outdated documentation.
"""

import os
import re
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Component name patterns to check
COMPONENT_PATTERNS = [
    r"\b(\w+Processor)\b",
    r"\b(\w+Adapter)\b",
    r"\b(\w+Stage)\b",
    r"\b(\w+Analyzer)\b",
    r"\b(\w+Masker)\b",
    r"\b(\w+Manager)\b",
]

# Common words to ignore
IGNORE_WORDS = {
    "BaseProcessor",
    "StageBase",
    "ProcessorResult",
    "StageStats",
    "ProcessorConfig",
    "MaskingRecipe",
}


def find_components_in_docs(doc_path: Path) -> Set[str]:
    """Find component names in documentation"""
    components = set()

    try:
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        for pattern in COMPONENT_PATTERNS:
            matches = re.findall(pattern, content)
            components.update(matches)

    except Exception as e:
        print(f"Error reading {doc_path}: {e}")

    return components - IGNORE_WORDS


def find_components_in_code(src_path: Path) -> Set[str]:
    """Find defined classes in code"""
    components = set()

    for py_file in src_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Find class definitions
            class_matches = re.findall(r"class\s+(\w+)\s*\(", content)
            components.update(class_matches)

        except Exception as e:
            print(f"Error reading {py_file}: {e}")

    return components


def check_doc_sync(
    doc_path: Path, code_components: Set[str]
) -> Tuple[List[str], List[str]]:
    """Check synchronization status of a single document"""
    doc_components = find_components_in_docs(doc_path)

    # Find components mentioned in documentation but not existing in code
    missing_in_code = []
    found_in_code = []

    for component in doc_components:
        if component not in code_components:
            missing_in_code.append(component)
        else:
            found_in_code.append(component)

    return missing_in_code, found_in_code


def main():
    """Main function"""
    print("🔍 Documentation Synchronization Check\n")

    # Collect all components in code
    src_path = PROJECT_ROOT / "src"
    code_components = find_components_in_code(src_path)
    print(f"✅ Found {len(code_components)} components in code\n")

    # Check all documents
    docs_path = PROJECT_ROOT / "docs"
    problems = []

    for doc_file in docs_path.rglob("*.md"):
        # Skip README and other non-technical documents
        if doc_file.name in ["README.md", "DOCUMENT_STATUS.md"]:
            continue

        missing, found = check_doc_sync(doc_file, code_components)

        if missing:
            rel_path = doc_file.relative_to(PROJECT_ROOT)
            problems.append({"path": rel_path, "missing": missing, "found": found})

    # Output results
    if problems:
        print("⚠️  Found the following documents that may be outdated:\n")

        for problem in sorted(problems, key=lambda x: len(x["missing"]), reverse=True):
            print(f"📄 {problem['path']}")
            print(f"   ❌ Non-existent components: {', '.join(problem['missing'])}")
            if problem["found"]:
                print(
                    f"   ✅ Existing components: {', '.join(problem['found'][:3])}..."
                )
            print()

        # Category statistics
        current_problems = [p for p in problems if "current/" in str(p["path"])]
        archive_problems = [p for p in problems if "archive/" in str(p["path"])]

        print("\n📊 Statistics:")
        print(
            f"   - current/ directory: {len(current_problems)} documents need updating"
        )
        print(f"   - archive/ directory: {len(archive_problems)} documents archived")
        print(
            f"   - Other directories: {len(problems) - len(current_problems) - len(archive_problems)} documents"
        )

        if current_problems:
            print(
                "\n❗ Recommend prioritizing updates to documents in current/ directory"
            )

    else:
        print("✅ All documents are synchronized with code!")

    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
