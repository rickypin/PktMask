#!/usr/bin/env python3
"""
PktMask TShark Dependency Check Script

This script is used to verify that the tshark installation in the system meets PktMask requirements.
Can be used before deployment or during troubleshooting.

Usage:
    python scripts/check_tshark_dependencies.py
    python scripts/check_tshark_dependencies.py --tshark-path /custom/path/to/tshark
    python scripts/check_tshark_dependencies.py --verbose
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Minimum tshark version required by PktMask
MIN_TSHARK_VERSION = (4, 2, 0)

# Default search paths
DEFAULT_TSHARK_PATHS = [
    "/usr/bin/tshark",
    "/usr/local/bin/tshark",
    "/opt/wireshark/bin/tshark",
    "C:\\Program Files\\Wireshark\\tshark.exe",
    "C:\\Program Files (x86)\\Wireshark\\tshark.exe",
    "/Applications/Wireshark.app/Contents/MacOS/tshark",
]

# Required protocol support
REQUIRED_PROTOCOLS = ["tcp", "tls", "ssl", "ip", "ipv6"]

# Required field support
REQUIRED_FIELDS = [
    "frame.number",
    "frame.protocols",
    "tcp.stream",
    "tcp.seq",
    "tcp.seq_raw",
    "tcp.payload",
    "tls.record.content_type",
    "tls.app_data",
]


def parse_tshark_version(output: str) -> Optional[Tuple[int, int, int]]:
    """解析tshark版本号"""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
    if match:
        return tuple(map(int, match.groups()))
    return None


def find_tshark_executable(custom_path: Optional[str] = None) -> Optional[str]:
    """Find tshark executable"""
    # 1. Check custom path
    if custom_path:
        if Path(custom_path).exists():
            return custom_path
        else:
            print(f"❌ Custom path does not exist: {custom_path}")
            return None

    # 2. Check default paths
    for path in DEFAULT_TSHARK_PATHS:
        if Path(path).exists():
            return path

    # 3. Search in system PATH
    return shutil.which("tshark")


def check_tshark_version(tshark_path: str) -> Dict[str, any]:
    """Check tshark version"""
    result = {
        "success": False,
        "version": None,
        "version_string": "",
        "meets_requirement": False,
        "error": None,
    }

    try:
        proc = subprocess.run(
            [tshark_path, "-v"], capture_output=True, text=True, timeout=10
        )

        if proc.returncode != 0:
            result["error"] = f"tshark -v returned non-zero exit code: {proc.returncode}"
            return result

        output = proc.stdout + proc.stderr
        result["version_string"] = output.strip()

        version = parse_tshark_version(output)
        if version:
            result["version"] = version
            result["meets_requirement"] = version >= MIN_TSHARK_VERSION
            result["success"] = True
        else:
            result["error"] = "Unable to parse version number"

    except subprocess.TimeoutExpired:
        result["error"] = "tshark -v 执行超时"
    except Exception as e:
        result["error"] = f"执行tshark -v 失败: {e}"

    return result


def check_protocol_support(tshark_path: str) -> Dict[str, any]:
    """检查协议支持"""
    result = {
        "success": False,
        "supported_protocols": [],
        "missing_protocols": [],
        "error": None,
    }

    try:
        proc = subprocess.run(
            [tshark_path, "-G", "protocols"], capture_output=True, text=True, timeout=30
        )

        if proc.returncode != 0:
            result["error"] = f"tshark -G protocols 返回非零退出码: {proc.returncode}"
            return result

        protocols = proc.stdout.lower()

        for protocol in REQUIRED_PROTOCOLS:
            if protocol in protocols:
                result["supported_protocols"].append(protocol)
            else:
                result["missing_protocols"].append(protocol)

        result["success"] = len(result["missing_protocols"]) == 0

    except subprocess.TimeoutExpired:
        result["error"] = "tshark -G protocols 执行超时"
    except Exception as e:
        result["error"] = f"检查协议支持失败: {e}"

    return result


def check_field_support(tshark_path: str) -> Dict[str, any]:
    """Check field support"""
    result = {
        "success": False,
        "supported_fields": [],
        "missing_fields": [],
        "error": None,
    }

    try:
        proc = subprocess.run(
            [tshark_path, "-G", "fields"], capture_output=True, text=True, timeout=30
        )

        if proc.returncode != 0:
            result["error"] = f"tshark -G fields returned non-zero exit code: {proc.returncode}"
            return result

        fields = proc.stdout

        for field in REQUIRED_FIELDS:
            if field in fields:
                result["supported_fields"].append(field)
            else:
                result["missing_fields"].append(field)

        result["success"] = len(result["missing_fields"]) == 0

    except subprocess.TimeoutExpired:
        result["error"] = "tshark -G fields execution timeout"
    except Exception as e:
        result["error"] = f"Field support check failed: {e}"

    return result


def check_json_output(tshark_path: str) -> Dict[str, any]:
    """Check JSON output functionality"""
    result = {"success": False, "error": None}

    try:
        # Create a minimal test command
        proc = subprocess.run(
            [tshark_path, "-T", "json", "-c", "0"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Even without input file, tshark should recognize JSON format option
        # Return code may not be 0, but there should be no format errors
        if "json" in proc.stderr.lower() and "invalid" in proc.stderr.lower():
            result["error"] = "JSON output format not supported"
        else:
            result["success"] = True

    except subprocess.TimeoutExpired:
        result["error"] = "JSON output test timeout"
    except Exception as e:
        result["error"] = f"JSON output test failed: {e}"

    return result


def print_results(results: Dict[str, any], verbose: bool = False):
    """Print check results"""
    print("=" * 60)
    print("PktMask TShark Dependency Check Results")
    print("=" * 60)

    # Executable check
    if results["executable"]["found"]:
        print(f"✅ TShark executable: {results['executable']['path']}")
    else:
        print("❌ TShark executable: Not found")
        print("   Please install Wireshark or configure correct path")
        return

    # Version check
    version_result = results["version"]
    if version_result["success"]:
        version_str = ".".join(map(str, version_result["version"]))
        min_version_str = ".".join(map(str, MIN_TSHARK_VERSION))

        if version_result["meets_requirement"]:
            print(f"✅ TShark version: {version_str} (>= {min_version_str})")
        else:
            print(f"❌ TShark version: {version_str} (requires >= {min_version_str})")
    else:
        print(f"❌ Version check failed: {version_result['error']}")

    # Protocol support check
    protocol_result = results["protocols"]
    if protocol_result["success"]:
        print(f"✅ Protocol support: All required protocols supported")
        if verbose:
            print(f"   Supported protocols: {', '.join(protocol_result['supported_protocols'])}")
    else:
        print(f"❌ Protocol support: Missing required protocols")
        if protocol_result["missing_protocols"]:
            print(f"   Missing protocols: {', '.join(protocol_result['missing_protocols'])}")

    # Field support check
    field_result = results["fields"]
    if field_result["success"]:
        print(f"✅ Field support: All required fields supported")
        if verbose:
            print(f"   Number of supported fields: {len(field_result['supported_fields'])}")
    else:
        print(f"❌ Field support: Missing required fields")
        if field_result["missing_fields"]:
            print(f"   Missing fields: {', '.join(field_result['missing_fields'][:5])}")
            if len(field_result["missing_fields"]) > 5:
                print(f"   ... and {len(field_result['missing_fields']) - 5} more fields")

    # JSON output check
    json_result = results["json"]
    if json_result["success"]:
        print("✅ JSON output: Supported")
    else:
        print(f"❌ JSON output: {json_result['error']}")

    # Overall results
    print("-" * 60)
    all_passed = all(
        [
            results["executable"]["found"],
            version_result["success"] and version_result["meets_requirement"],
            protocol_result["success"],
            field_result["success"],
            json_result["success"],
        ]
    )

    if all_passed:
        print("🎉 All checks passed! TShark meets PktMask requirements.")
    else:
        print("⚠️  Issues found, please resolve the above problems and check again.")
        print("\nSuggested solutions:")
        print("1. Install or upgrade Wireshark to the latest version")
        print("2. Ensure tshark is in system PATH or use --tshark-path to specify path")
        print("3. Refer to installation guide in PktMask documentation")


def main():
    parser = argparse.ArgumentParser(
        description="Check if TShark dependencies meet PktMask requirements",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--tshark-path", help="Custom tshark executable path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed information")
    parser.add_argument("--json-output", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    # Find tshark executable
    tshark_path = find_tshark_executable(args.tshark_path)

    results = {"executable": {"found": tshark_path is not None, "path": tshark_path}}

    if not tshark_path:
        if args.json_output:
            print(json.dumps(results, indent=2))
        else:
            print_results(results, args.verbose)
        sys.exit(1)

    # Execute various checks
    results["version"] = check_tshark_version(tshark_path)
    results["protocols"] = check_protocol_support(tshark_path)
    results["fields"] = check_field_support(tshark_path)
    results["json"] = check_json_output(tshark_path)

    # Output results
    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print_results(results, args.verbose)

    # Set exit code
    all_passed = all(
        [
            results["executable"]["found"],
            results["version"]["success"] and results["version"]["meets_requirement"],
            results["protocols"]["success"],
            results["fields"]["success"],
            results["json"]["success"],
        ]
    )

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
