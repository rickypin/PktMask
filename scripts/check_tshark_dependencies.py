#!/usr/bin/env python3
"""
PktMask TShark 依赖检查脚本

此脚本用于验证系统中的tshark安装是否满足PktMask的要求。
可以在部署前或故障排除时使用。

使用方法:
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

# PktMask要求的最低tshark版本
MIN_TSHARK_VERSION = (4, 2, 0)

# 默认搜索路径
DEFAULT_TSHARK_PATHS = [
    "/usr/bin/tshark",
    "/usr/local/bin/tshark",
    "/opt/wireshark/bin/tshark",
    "C:\\Program Files\\Wireshark\\tshark.exe",
    "C:\\Program Files (x86)\\Wireshark\\tshark.exe",
    "/Applications/Wireshark.app/Contents/MacOS/tshark",
]

# 必需的协议支持
REQUIRED_PROTOCOLS = ["tcp", "tls", "ssl", "ip", "ipv6"]

# 必需的字段支持
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
            result["error"] = (
                f"tshark -v returned non-zero exit code: {proc.returncode}"
            )
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
            result["error"] = (
                f"tshark -G fields returned non-zero exit code: {proc.returncode}"
            )
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

    # 协议支持检查
    protocol_result = results["protocols"]
    if protocol_result["success"]:
        print(f"✅ 协议支持: 所有必需协议都支持")
        if verbose:
            print(f"   支持的协议: {', '.join(protocol_result['supported_protocols'])}")
    else:
        print(f"❌ 协议支持: 缺少必需协议")
        if protocol_result["missing_protocols"]:
            print(f"   缺少的协议: {', '.join(protocol_result['missing_protocols'])}")

    # 字段支持检查
    field_result = results["fields"]
    if field_result["success"]:
        print(f"✅ 字段支持: 所有必需字段都支持")
        if verbose:
            print(f"   支持的字段数: {len(field_result['supported_fields'])}")
    else:
        print(f"❌ 字段支持: 缺少必需字段")
        if field_result["missing_fields"]:
            print(f"   缺少的字段: {', '.join(field_result['missing_fields'][:5])}")
            if len(field_result["missing_fields"]) > 5:
                print(f"   ... 还有 {len(field_result['missing_fields']) - 5} 个字段")

    # JSON输出检查
    json_result = results["json"]
    if json_result["success"]:
        print("✅ JSON输出: 支持")
    else:
        print(f"❌ JSON输出: {json_result['error']}")

    # 总体结果
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
        print("🎉 所有检查通过！TShark满足PktMask的要求。")
    else:
        print("⚠️  存在问题，请解决上述问题后重新检查。")
        print("\n建议解决方案:")
        print("1. 安装或升级Wireshark到最新版本")
        print("2. 确保tshark在系统PATH中或使用--tshark-path指定路径")
        print("3. 参考PktMask文档中的安装指南")


def main():
    parser = argparse.ArgumentParser(
        description="Check if TShark dependencies meet PktMask requirements",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--tshark-path", help="Custom tshark executable path")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed information"
    )
    parser.add_argument(
        "--json-output", action="store_true", help="Output results in JSON format"
    )

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

    # 执行各项检查
    results["version"] = check_tshark_version(tshark_path)
    results["protocols"] = check_protocol_support(tshark_path)
    results["fields"] = check_field_support(tshark_path)
    results["json"] = check_json_output(tshark_path)

    # 输出结果
    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print_results(results, args.verbose)

    # 设置退出码
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
