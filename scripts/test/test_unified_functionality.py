#!/usr/bin/env python3
"""
PktMask 统一功能测试脚本
验证 GUI 与 CLI 功能的一致性
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.services.config_service import (
    build_config_from_cli_args,
    build_config_from_gui,
    get_config_service,
)
from pktmask.services.pipeline_service import create_pipeline_executor


class UnifiedFunctionalityTester:
    """统一功能测试器"""

    def __init__(self):
        self.temp_dir = None
        self.test_results = []
        self.config_service = get_config_service()

    def setup(self):
        """设置测试环境"""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="pktmask_test_"))
        print(f"📁 Test directory: {self.temp_dir}")

        # 创建测试文件
        self.create_test_files()

    def teardown(self):
        """清理测试环境"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print("🧹 Cleaned up test directory")

    def create_test_files(self):
        """创建测试用的 PCAP 文件"""
        test_data_dir = self.temp_dir / "test_data"
        test_data_dir.mkdir()

        # 创建模拟的 PCAP 文件
        for i in range(3):
            test_file = test_data_dir / f"test_{i}.pcap"
            test_file.write_bytes(b"fake pcap content for testing")

        print(f"📄 Created {len(list(test_data_dir.glob('*.pcap')))} test files")

    def test_config_consistency(self) -> bool:
        """测试配置一致性"""
        print("\n🔧 Testing configuration consistency...")

        try:
            # GUI 配置
            gui_options = self.config_service.create_options_from_gui(
                remove_dupes_checked=True,
                anonymize_ips_checked=True,
                mask_payloads_checked=True,
            )
            gui_config = self.config_service.build_pipeline_config(gui_options)

            # CLI 配置
            cli_options = self.config_service.create_options_from_cli_args(
                remove_dupes=True,
                anonymize_ips=True,
                mask_payloads=True,
            )
            cli_config = self.config_service.build_pipeline_config(cli_options)

            # 验证一致性
            consistency_checks = [
                gui_config["remove_dupes"]["enabled"] == cli_config["remove_dupes"]["enabled"],
                gui_config["anonymize_ips"]["enabled"] == cli_config["anonymize_ips"]["enabled"],
                gui_config["mask_payloads"]["enabled"] == cli_config["mask_payloads"]["enabled"],
                gui_config["mask_payloads"]["mode"] == cli_config["mask_payloads"]["mode"],
                gui_config["mask_payloads"]["protocol"] == cli_config["mask_payloads"]["protocol"],
            ]

            all_consistent = all(consistency_checks)

            if all_consistent:
                print("✅ Configuration consistency: PASSED")
                self.test_results.append(("Config Consistency", True, "All configurations match"))
            else:
                print("❌ Configuration consistency: FAILED")
                self.test_results.append(("Config Consistency", False, "Configuration mismatch"))

            return all_consistent

        except Exception as e:
            print(f"❌ Configuration consistency: ERROR - {e}")
            self.test_results.append(("Config Consistency", False, str(e)))
            return False

    def test_cli_commands(self) -> bool:
        """测试 CLI 命令"""
        print("\n💻 Testing CLI commands...")

        test_file = self.temp_dir / "test_data" / "test_0.pcap"
        output_file = self.temp_dir / "output.pcap"

        commands_to_test = [
            ["python", "-m", "pktmask", "info", str(test_file)],
            [
                "python",
                "-m",
                "pktmask",
                "info",
                str(self.temp_dir / "test_data"),
                "--format",
                "json",
            ],
        ]

        all_passed = True

        for cmd in commands_to_test:
            try:
                result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    print(f"✅ Command '{' '.join(cmd[-2:])}': PASSED")
                    self.test_results.append((f"CLI {cmd[-2]}", True, "Command executed successfully"))
                else:
                    print(f"❌ Command '{' '.join(cmd[-2:])}': FAILED")
                    print(f"   Error: {result.stderr}")
                    self.test_results.append((f"CLI {cmd[-2]}", False, result.stderr))
                    all_passed = False

            except subprocess.TimeoutExpired:
                print(f"⏰ Command '{' '.join(cmd[-2:])}': TIMEOUT")
                self.test_results.append((f"CLI {cmd[-2]}", False, "Command timeout"))
                all_passed = False
            except Exception as e:
                print(f"❌ Command '{' '.join(cmd[-2:])}': ERROR - {e}")
                self.test_results.append((f"CLI {cmd[-2]}", False, str(e)))
                all_passed = False

        return all_passed

    def test_service_layer(self) -> bool:
        """测试服务层"""
        print("\n🔧 Testing service layer...")

        try:
            # 测试配置服务
            config = build_config_from_cli_args(remove_dupes=True, anonymize_ips=True)
            is_valid, error = self.config_service.validate_config(config)

            if not is_valid:
                print(f"❌ Config validation failed: {error}")
                self.test_results.append(("Service Layer", False, f"Config validation: {error}"))
                return False

            # 测试执行器创建
            executor = create_pipeline_executor(config)
            if executor is None:
                print("❌ Executor creation failed")
                self.test_results.append(("Service Layer", False, "Executor creation failed"))
                return False

            print("✅ Service layer: PASSED")
            self.test_results.append(("Service Layer", True, "All service components working"))
            return True

        except Exception as e:
            print(f"❌ Service layer: ERROR - {e}")
            self.test_results.append(("Service Layer", False, str(e)))
            return False

    def test_output_formats(self) -> bool:
        """测试输出格式"""
        print("\n📄 Testing output formats...")

        try:
            import io

            from pktmask.services.output_service import create_output_service
            from pktmask.services.report_service import get_report_service

            # 测试文本输出
            text_output = io.StringIO()
            text_service = create_output_service("text", "normal", text_output)

            test_result = {
                "success": True,
                "duration_ms": 1000.0,
                "total_files": 1,
                "processed_files": 1,
            }

            text_service.print_processing_summary(test_result)
            text_content = text_output.getvalue()

            if not text_content:
                print("❌ Text output: FAILED - No output generated")
                self.test_results.append(("Text Output", False, "No output generated"))
                return False

            # 测试 JSON 输出
            json_output = io.StringIO()
            json_service = create_output_service("json", "normal", json_output)
            json_service.print_processing_summary(test_result)
            json_content = json_output.getvalue()

            try:
                json.loads(json_content)
            except json.JSONDecodeError:
                print("❌ JSON output: FAILED - Invalid JSON")
                self.test_results.append(("JSON Output", False, "Invalid JSON format"))
                return False

            # 测试报告服务
            report_service = get_report_service()
            report_service.start_report("/test/input", "/test/output")
            report = report_service.finalize_report(True, 1, 1)

            text_report = report_service.generate_text_report(report)
            json_report = report_service.generate_json_report(report)

            if not text_report or not json_report:
                print("❌ Report generation: FAILED")
                self.test_results.append(("Report Generation", False, "Report generation failed"))
                return False

            print("✅ Output formats: PASSED")
            self.test_results.append(("Output Formats", True, "All formats working"))
            return True

        except Exception as e:
            print(f"❌ Output formats: ERROR - {e}")
            self.test_results.append(("Output Formats", False, str(e)))
            return False

    def test_error_handling(self) -> bool:
        """测试错误处理"""
        print("\n🚨 Testing error handling...")

        try:
            # 测试无效配置
            invalid_config = {}
            is_valid, error = self.config_service.validate_config(invalid_config)

            if is_valid:
                print("❌ Error handling: FAILED - Invalid config accepted")
                self.test_results.append(("Error Handling", False, "Invalid config accepted"))
                return False

            # 测试不存在的文件
            cmd = ["python", "-m", "pktmask", "info", "/nonexistent/file.pcap"]
            result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                print("❌ Error handling: FAILED - Nonexistent file not handled")
                self.test_results.append(("Error Handling", False, "Nonexistent file not handled"))
                return False

            print("✅ Error handling: PASSED")
            self.test_results.append(("Error Handling", True, "Errors properly handled"))
            return True

        except Exception as e:
            print(f"❌ Error handling: ERROR - {e}")
            self.test_results.append(("Error Handling", False, str(e)))
            return False

    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("📊 TEST REPORT")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, passed, _ in self.test_results if passed)
        failed_tests = total_tests - passed_tests

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        print("\nDetailed Results:")
        print("-" * 40)

        for test_name, passed, message in self.test_results:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} {test_name}: {message}")

        # 保存报告到文件
        report_file = self.temp_dir / "test_report.json"
        report_data = {
            "timestamp": str(Path(__file__).stat().st_mtime),
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests / total_tests) * 100,
            "results": [
                {"test_name": name, "passed": passed, "message": message} for name, passed, message in self.test_results
            ],
        }

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n📄 Detailed report saved to: {report_file}")

        return failed_tests == 0

    def run_all_tests(self) -> bool:
        """运行所有测试"""
        print("🚀 Starting PktMask Unified Functionality Tests")
        print("=" * 60)

        self.setup()

        try:
            tests = [
                self.test_config_consistency,
                self.test_service_layer,
                self.test_output_formats,
                self.test_cli_commands,
                self.test_error_handling,
            ]

            all_passed = True
            for test in tests:
                if not test():
                    all_passed = False

            success = self.generate_report()
            return success

        finally:
            self.teardown()


def main():
    """主函数"""
    tester = UnifiedFunctionalityTester()
    success = tester.run_all_tests()

    if success:
        print("\n🎉 All tests passed! PktMask unified functionality is working correctly.")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed. Please check the detailed report above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
