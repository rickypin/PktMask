#!/usr/bin/env python3
"""
PktMask Test Suite
统一测试入口点，兼容GitHub Actions配置
"""
import sys
import argparse
import subprocess
from pathlib import Path
import os


def ensure_output_dir(output_dir: str) -> Path:
    """确保输出目录存在"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 创建子目录
    (output_path / "junit").mkdir(exist_ok=True)
    (output_path / "coverage").mkdir(exist_ok=True)

    return output_path


def run_quick_tests(output_dir: str) -> int:
    """运行快速测试（跳过性能测试）"""
    print("⚡ Quick test mode - basic tests only")

    output_path = ensure_output_dir(output_dir)

    cmd = [
        "python",
        "-m",
        "pytest",
        "-x",  # 快速失败
        "--tb=short",  # 简短回溯
        "-v",  # 详细输出
        f"--junit-xml={output_path}/junit/results.xml",
        "tests/",
    ]

    print(f"🚀 Running command: {' '.join(cmd)}")
    print("-" * 50)

    return subprocess.run(cmd).returncode


def run_performance_tests(output_dir: str) -> int:
    """运行性能测试"""
    print("⏱️ Performance test mode")

    output_path = ensure_output_dir(output_dir)

    cmd = [
        "python",
        "-m",
        "pytest",
        "-m",
        "performance",  # 只运行性能测试
        "-v",
        f"--junit-xml={output_path}/junit/performance_results.xml",
        f"--html={output_path}/performance_report.html",
        "--self-contained-html",
        "tests/",
    ]

    print(f"🚀 Running command: {' '.join(cmd)}")
    print("-" * 50)

    return subprocess.run(cmd).returncode


def run_full_tests(output_dir: str) -> int:
    """运行完整测试套件"""
    print("🔥 Full test mode - all tests + complete reports")

    output_path = ensure_output_dir(output_dir)

    cmd = [
        "python",
        "-m",
        "pytest",
        "--cov=src/pktmask",
        f"--cov-report=html:{output_path}/coverage",
        "--cov-report=term-missing",
        f"--junit-xml={output_path}/junit/results.xml",
        f"--html={output_path}/test_report.html",
        "--self-contained-html",
        "-v",
        "tests/",
    ]

    print(f"🚀 Running command: {' '.join(cmd)}")
    print("-" * 50)

    return subprocess.run(cmd).returncode


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="PktMask Test Suite")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test mode (no coverage, skip performance)",
    )
    parser.add_argument(
        "--performance", action="store_true", help="Performance test mode"
    )
    parser.add_argument(
        "--output", default="test_reports", help="Output directory for test reports"
    )

    args = parser.parse_args()

    try:
        if args.quick:
            exit_code = run_quick_tests(args.output)
        elif args.performance:
            exit_code = run_performance_tests(args.output)
        else:
            exit_code = run_full_tests(args.output)

        if exit_code == 0:
            print("\n✅ Tests completed successfully!")
        else:
            print(f"\n❌ Tests failed with exit code {exit_code}")

        return exit_code

    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Test runner error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
