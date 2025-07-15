#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask test runner
Supports multiple test modes and report generation
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional


class TestRunner:
    """Test runner class"""

    def __init__(self):
        self.base_cmd = [sys.executable, "-m", "pytest"]
        self.reports_dir = Path("reports")

    def run_tests(self,
                  test_type: str = "all",
                  coverage: bool = True,
                  html_report: bool = False,
                  verbose: bool = True,
                  parallel: bool = False,
                  fail_fast: bool = False,
                  custom_args: Optional[List[str]] = None) -> int:
        """
        Run specified type of tests

        Args:
            test_type: Test type (unit, integration, e2e, performance, real_data, all)
            coverage: Whether to generate coverage report
            html_report: Whether to generate HTML report
            verbose: Verbose output
            parallel: Run tests in parallel
            fail_fast: Stop immediately on failure
            custom_args: Custom pytest arguments

        Returns:
            Test exit code
        """
        cmd = self.base_cmd.copy()
        
        # 添加测试类型过滤
        if test_type != "all":
            cmd.extend(["-m", test_type])
            
        # 添加覆盖率选项
        if coverage:
            cmd.extend([
                "--cov=src/pktmask",
                "--cov-report=html:output/reports/coverage",
                "--cov-report=term-missing"
            ])
            
        # 添加HTML报告
        if html_report:
            cmd.extend([
                "--html=output/reports/test_report.html",
                "--self-contained-html"
            ])
            
        # 并行执行
        if parallel:
            cmd.extend(["-n", "auto"])
            
        # 快速失败
        if fail_fast:
            cmd.append("-x")
            
        # 详细输出
        if verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")
            
        # 添加自定义参数
        if custom_args:
            cmd.extend(custom_args)
            
        print(f"🚀 Running command: {' '.join(cmd)}")
        print(f"📝 Test type: {test_type}")
        print(f"📊 Coverage report: {'Yes' if coverage else 'No'}")
        print(f"📄 HTML report: {'Yes' if html_report else 'No'}")
        print("-" * 50)

        return subprocess.run(cmd).returncode

    def quick_test(self) -> int:
        """Quick test - only run unit tests, no coverage"""
        print("⚡ Quick test mode - unit tests only")
        return self.run_tests(
            test_type="unit",
            coverage=False,
            verbose=False,
            fail_fast=True
        )

    def full_test(self) -> int:
        """Full test - all test types, including reports"""
        print("🔥 Full test mode - all tests + complete reports")
        return self.run_tests(
            test_type="all",
            coverage=True,
            html_report=True,
            parallel=True
        )

    def performance_test(self) -> int:
        """Performance test"""
        print("⏱️ Performance test mode")
        return self.run_tests(
            test_type="performance",
            coverage=False,
            verbose=True
        )

    def real_data_test(self) -> int:
        """Real data validation test"""
        print("🔍 Real data validation test mode")
        return self.run_tests(
            test_type="real_data",
            coverage=False,
            verbose=True,
            html_report=True
        )

    def samples_validation(self) -> int:
        """Sample validation test - specifically for all samples directories"""
        print("📁 Sample data complete validation test")
        print("🎯 Test scope: all directories under tests/data/samples/")

        # Run specific real data validation tests
        return self.run_tests(
            test_type="real_data and integration",
            coverage=False,
            verbose=True,
            html_report=True,
            custom_args=[
                "tests/integration/test_real_data_validation.py",
                "--durations=20",  # Show slowest 20 tests
                "-s"  # Don't capture output, show print statements
            ]
        )


def setup_test_environment():
    """Setup test environment variables"""
    # Set headless test environment
    os.environ['PKTMASK_TEST_MODE'] = 'true'
    os.environ['PKTMASK_HEADLESS'] = 'true'
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'

    # Set Python path
    project_root = Path(__file__).parent
    src_path = project_root / "src"

    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Comment out this line as it prevents pytest plugin loading
    # os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'


def main():
    """Main function"""
    # First setup test environment
    setup_test_environment()

    parser = argparse.ArgumentParser(description="PktMask test runner")
    parser.add_argument("--quick", action="store_true",
                       help="Quick test mode (no coverage)")
    parser.add_argument("--full", action="store_true",
                       help="Full test mode (coverage + HTML report)")
    parser.add_argument("--type",
                       choices=["unit", "integration", "e2e", "real_data", "performance"],
                       help="Run specific type of tests")
    parser.add_argument("--samples", action="store_true",
                       help="Run real data sample validation tests")
    parser.add_argument("--parallel", action="store_true",
                       help="Execute tests in parallel")
    parser.add_argument("--html", action="store_true",
                       help="Generate HTML test report")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()

    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "junit").mkdir(exist_ok=True)
    (reports_dir / "coverage").mkdir(exist_ok=True)

    # Build pytest command
    pytest_args = ["python", "-m", "pytest"]

    # Add JUnit XML report
    pytest_args.extend(["--junit-xml=output/reports/junit/results.xml"])

    if args.quick:
        print("🔥 Quick test mode - run basic tests only")
        pytest_args.extend(["-x", "--tb=short"])
    elif args.full:
        print("🔥 Full test mode - all tests + complete reports")
        pytest_args.extend([
            "--cov=src/pktmask",
            "--cov-report=html:output/reports/coverage",
            "--cov-report=term-missing",
            "--html=output/reports/test_report.html",
            "--self-contained-html"
        ])
        if args.parallel:
            pytest_args.extend(["-n", "auto"])
    else:
        # Default mode: with coverage but no HTML
        pytest_args.extend([
            "--cov=src/pktmask",
            "--cov-report=html:output/reports/coverage",
            "--cov-report=term-missing"
        ])

    # Test type selection
    if args.type:
        print(f"🎯 Running {args.type} tests")
        pytest_args.extend(["-m", args.type])
    elif args.samples:
        print("🧪 Running real data sample validation")
        pytest_args.extend(["-m", "real_data"])

    # Other options
    if args.html and not args.full:
        pytest_args.extend([
            "--html=output/reports/test_report.html",
            "--self-contained-html"
        ])

    if args.verbose:
        pytest_args.append("-v")
    else:
        pytest_args.append("-v")  # Default verbose output

    print(f"🚀 Running command: {' '.join(pytest_args)}")
    print(f"📝 Test type: {args.type if args.type else 'all'}")
    print(f"📊 Coverage report: {'Yes' if not args.quick else 'No'}")
    print(f"📄 HTML report: {'Yes' if args.html or args.full else 'No'}")
    print("-" * 50)

    # Execute tests
    try:
        result = subprocess.run(pytest_args, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        return 1
    except Exception as e:
        print(f"Error executing tests: {e}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test runner error: {e}")
        sys.exit(1)