#!/usr/bin/env python3
"""
PktMask 重构验证器

验证重构后的代码质量、性能和功能完整性。
"""

import os
import sys
import subprocess
import time
import psutil
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

@dataclass
class ValidationResult:
    """验证结果"""
    test_name: str
    success: bool
    duration_seconds: float
    details: Dict[str, any]
    error_message: Optional[str] = None

class RefactorValidator:
    """重构验证器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results: List[ValidationResult] = []
        
    def run_all_validations(self) -> bool:
        """运行所有验证测试"""
        print("🔍 开始重构验证...")
        print("=" * 50)
        
        validations = [
            ("功能完整性测试", self._validate_functionality),
            ("性能基准测试", self._validate_performance),
            ("代码质量检查", self._validate_code_quality),
            ("依赖关系验证", self._validate_dependencies),
            ("接口兼容性测试", self._validate_interfaces),
            ("内存使用测试", self._validate_memory_usage),
            ("错误处理测试", self._validate_error_handling),
            ("文档一致性检查", self._validate_documentation)
        ]
        
        all_passed = True
        
        for test_name, test_func in validations:
            print(f"\n📋 执行: {test_name}")
            result = test_func()
            self.results.append(result)
            
            if result.success:
                print(f"✅ {test_name} 通过")
            else:
                print(f"❌ {test_name} 失败: {result.error_message}")
                all_passed = False
        
        return all_passed
    
    def _validate_functionality(self) -> ValidationResult:
        """验证功能完整性"""
        start_time = time.time()
        
        try:
            # 运行完整的测试套件
            test_commands = [
                "python -m pytest tests/unit/ -v --tb=short",
                "python -m pytest tests/integration/ -v --tb=short",
                "python -m pytest tests/e2e/ -v --tb=short -k 'not performance'"
            ]
            
            test_results = {}
            all_passed = True
            
            for cmd in test_commands:
                test_type = cmd.split()[3].split('/')[1]  # 提取测试类型
                print(f"   运行 {test_type} 测试...")
                
                result = subprocess.run(
                    cmd.split(),
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10分钟超时
                )
                
                test_results[test_type] = {
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
                
                if result.returncode != 0:
                    all_passed = False
            
            duration = time.time() - start_time
            
            return ValidationResult(
                test_name="functionality",
                success=all_passed,
                duration_seconds=duration,
                details=test_results,
                error_message=None if all_passed else "部分测试失败"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return ValidationResult(
                test_name="functionality",
                success=False,
                duration_seconds=duration,
                details={},
                error_message=str(e)
            )
    
    def _validate_performance(self) -> ValidationResult:
        """验证性能基准"""
        start_time = time.time()
        
        try:
            # 运行性能基准测试
            benchmark_script = self.project_root / "scripts" / "performance" / "benchmark_simplification.py"
            
            if not benchmark_script.exists():
                # 创建简单的性能测试
                performance_data = self._run_simple_performance_test()
            else:
                result = subprocess.run(
                    [sys.executable, str(benchmark_script)],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    performance_data = json.loads(result.stdout)
                else:
                    raise Exception(f"性能测试失败: {result.stderr}")
            
            # 检查性能指标
            performance_ok = self._check_performance_metrics(performance_data)
            
            duration = time.time() - start_time
            
            return ValidationResult(
                test_name="performance",
                success=performance_ok,
                duration_seconds=duration,
                details=performance_data,
                error_message=None if performance_ok else "性能指标不达标"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return ValidationResult(
                test_name="performance",
                success=False,
                duration_seconds=duration,
                details={},
                error_message=str(e)
            )
    
    def _run_simple_performance_test(self) -> Dict[str, any]:
        """运行简单的性能测试"""
        print("   运行简单性能测试...")
        
        # 测试导入时间
        import_start = time.time()
        try:
            import pktmask
            import_time = time.time() - import_start
            import_success = True
        except Exception as e:
            import_time = time.time() - import_start
            import_success = False
        
        # 测试内存使用
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            "import_time_seconds": import_time,
            "import_success": import_success,
            "memory_rss_mb": memory_info.rss / 1024 / 1024,
            "memory_vms_mb": memory_info.vms / 1024 / 1024
        }
    
    def _check_performance_metrics(self, data: Dict[str, any]) -> bool:
        """检查性能指标是否达标"""
        # 定义性能阈值
        thresholds = {
            "import_time_seconds": 2.0,  # 导入时间不超过2秒
            "memory_rss_mb": 100.0,      # 内存使用不超过100MB
        }
        
        for metric, threshold in thresholds.items():
            if metric in data and data[metric] > threshold:
                print(f"   ⚠️  性能指标 {metric} 超过阈值: {data[metric]} > {threshold}")
                return False
        
        return True
    
    def _validate_code_quality(self) -> ValidationResult:
        """验证代码质量"""
        start_time = time.time()
        
        try:
            quality_checks = {}
            
            # 检查代码复杂度
            print("   检查代码复杂度...")
            complexity_result = self._check_code_complexity()
            quality_checks["complexity"] = complexity_result
            
            # 检查代码重复
            print("   检查代码重复...")
            duplication_result = self._check_code_duplication()
            quality_checks["duplication"] = duplication_result
            
            # 检查导入依赖
            print("   检查导入依赖...")
            import_result = self._check_import_structure()
            quality_checks["imports"] = import_result
            
            # 检查文件大小
            print("   检查文件大小...")
            file_size_result = self._check_file_sizes()
            quality_checks["file_sizes"] = file_size_result
            
            all_passed = all(check["passed"] for check in quality_checks.values())
            
            duration = time.time() - start_time
            
            return ValidationResult(
                test_name="code_quality",
                success=all_passed,
                duration_seconds=duration,
                details=quality_checks,
                error_message=None if all_passed else "代码质量检查未通过"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return ValidationResult(
                test_name="code_quality",
                success=False,
                duration_seconds=duration,
                details={},
                error_message=str(e)
            )
    
    def _check_code_complexity(self) -> Dict[str, any]:
        """检查代码复杂度"""
        # 简单的复杂度检查：统计文件行数和函数数量
        src_dir = self.project_root / "src"
        total_lines = 0
        total_files = 0
        large_files = []
        
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            with open(py_file, 'r', encoding='utf-8') as f:
                lines = len(f.readlines())
                total_lines += lines
                total_files += 1
                
                if lines > 500:  # 超过500行的文件
                    large_files.append({"file": str(py_file.relative_to(src_dir)), "lines": lines})
        
        avg_lines_per_file = total_lines / total_files if total_files > 0 else 0
        
        return {
            "passed": len(large_files) < 5,  # 大文件不超过5个
            "total_lines": total_lines,
            "total_files": total_files,
            "avg_lines_per_file": avg_lines_per_file,
            "large_files": large_files
        }
    
    def _check_code_duplication(self) -> Dict[str, any]:
        """检查代码重复"""
        # 简单的重复检查：查找相似的类名和函数名
        src_dir = self.project_root / "src"
        class_names = []
        function_names = []
        
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # 简单的正则匹配类名和函数名
                    import re
                    classes = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
                    functions = re.findall(r'^def\s+(\w+)', content, re.MULTILINE)
                    
                    class_names.extend(classes)
                    function_names.extend(functions)
            except Exception:
                continue
        
        # 检查重复
        duplicate_classes = [name for name in set(class_names) if class_names.count(name) > 1]
        duplicate_functions = [name for name in set(function_names) if function_names.count(name) > 3]  # 函数重复阈值更高
        
        return {
            "passed": len(duplicate_classes) < 3 and len(duplicate_functions) < 10,
            "duplicate_classes": duplicate_classes,
            "duplicate_functions": duplicate_functions
        }
    
    def _check_import_structure(self) -> Dict[str, any]:
        """检查导入结构"""
        # 检查是否有循环导入和过深的导入层次
        src_dir = self.project_root / "src"
        import_issues = []
        
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # 检查相对导入层次
                    import re
                    relative_imports = re.findall(r'from\s+(\.{2,})', content)
                    if any(len(imp) > 3 for imp in relative_imports):  # 超过3层的相对导入
                        import_issues.append(f"深层相对导入: {py_file.relative_to(src_dir)}")
                        
            except Exception:
                continue
        
        return {
            "passed": len(import_issues) == 0,
            "issues": import_issues
        }
    
    def _check_file_sizes(self) -> Dict[str, any]:
        """检查文件大小"""
        src_dir = self.project_root / "src"
        large_files = []
        total_size = 0
        
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            size = py_file.stat().st_size
            total_size += size
            
            if size > 50000:  # 超过50KB的文件
                large_files.append({
                    "file": str(py_file.relative_to(src_dir)),
                    "size_kb": size / 1024
                })
        
        return {
            "passed": len(large_files) < 3,  # 大文件不超过3个
            "total_size_mb": total_size / 1024 / 1024,
            "large_files": large_files
        }
    
    def _validate_dependencies(self) -> ValidationResult:
        """验证依赖关系"""
        start_time = time.time()
        
        try:
            # 检查是否能正常导入主要模块
            import_tests = [
                "pktmask",
                "pktmask.core",
                "pktmask.gui",
                "pktmask.cli"
            ]
            
            import_results = {}
            all_passed = True
            
            for module in import_tests:
                try:
                    __import__(module)
                    import_results[module] = {"success": True, "error": None}
                except Exception as e:
                    import_results[module] = {"success": False, "error": str(e)}
                    all_passed = False
            
            duration = time.time() - start_time
            
            return ValidationResult(
                test_name="dependencies",
                success=all_passed,
                duration_seconds=duration,
                details=import_results,
                error_message=None if all_passed else "模块导入失败"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return ValidationResult(
                test_name="dependencies",
                success=False,
                duration_seconds=duration,
                details={},
                error_message=str(e)
            )
    
    def _validate_interfaces(self) -> ValidationResult:
        """验证接口兼容性"""
        start_time = time.time()
        
        try:
            # 检查关键接口是否存在
            interface_checks = {}
            
            # 检查CLI接口
            cli_result = subprocess.run(
                [sys.executable, "-m", "pktmask", "--help"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            interface_checks["cli"] = {"success": cli_result.returncode == 0}
            
            # 检查GUI接口（在测试模式下）
            env = os.environ.copy()
            env["PKTMASK_TEST_MODE"] = "true"
            env["PKTMASK_HEADLESS"] = "true"
            
            gui_result = subprocess.run(
                [sys.executable, "-c", "from pktmask.gui.main_window import main; main()"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            interface_checks["gui"] = {"success": gui_result.returncode == 0}
            
            all_passed = all(check["success"] for check in interface_checks.values())
            
            duration = time.time() - start_time
            
            return ValidationResult(
                test_name="interfaces",
                success=all_passed,
                duration_seconds=duration,
                details=interface_checks,
                error_message=None if all_passed else "接口验证失败"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return ValidationResult(
                test_name="interfaces",
                success=False,
                duration_seconds=duration,
                details={},
                error_message=str(e)
            )
    
    def _validate_memory_usage(self) -> ValidationResult:
        """验证内存使用"""
        start_time = time.time()
        
        try:
            # 测试内存使用情况
            process = psutil.Process()
            initial_memory = process.memory_info().rss
            
            # 导入主要模块
            import pktmask
            
            after_import_memory = process.memory_info().rss
            memory_increase = (after_import_memory - initial_memory) / 1024 / 1024  # MB
            
            # 检查内存增长是否合理
            memory_ok = memory_increase < 50  # 导入不应该增加超过50MB内存
            
            duration = time.time() - start_time
            
            return ValidationResult(
                test_name="memory_usage",
                success=memory_ok,
                duration_seconds=duration,
                details={
                    "initial_memory_mb": initial_memory / 1024 / 1024,
                    "after_import_memory_mb": after_import_memory / 1024 / 1024,
                    "memory_increase_mb": memory_increase
                },
                error_message=None if memory_ok else f"内存增长过多: {memory_increase:.1f}MB"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return ValidationResult(
                test_name="memory_usage",
                success=False,
                duration_seconds=duration,
                details={},
                error_message=str(e)
            )
    
    def _validate_error_handling(self) -> ValidationResult:
        """验证错误处理"""
        start_time = time.time()
        
        try:
            # 测试错误处理机制
            error_tests = {}
            
            # 测试无效输入处理
            cli_error_result = subprocess.run(
                [sys.executable, "-m", "pktmask", "mask", "nonexistent.pcap", "-o", "output.pcap"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # 应该返回非零退出码，但不应该崩溃
            error_tests["invalid_input"] = {
                "handled_gracefully": cli_error_result.returncode != 0 and "Traceback" not in cli_error_result.stderr
            }
            
            all_passed = all(test["handled_gracefully"] for test in error_tests.values())
            
            duration = time.time() - start_time
            
            return ValidationResult(
                test_name="error_handling",
                success=all_passed,
                duration_seconds=duration,
                details=error_tests,
                error_message=None if all_passed else "错误处理验证失败"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return ValidationResult(
                test_name="error_handling",
                success=False,
                duration_seconds=duration,
                details={},
                error_message=str(e)
            )
    
    def _validate_documentation(self) -> ValidationResult:
        """验证文档一致性"""
        start_time = time.time()
        
        try:
            docs_dir = self.project_root / "docs"
            doc_checks = {}
            
            # 检查关键文档是否存在
            required_docs = [
                "README.md",
                "docs/architecture/ABSTRACTION_LAYER_SIMPLIFICATION_PLAN.md"
            ]
            
            missing_docs = []
            for doc in required_docs:
                doc_path = self.project_root / doc
                if not doc_path.exists():
                    missing_docs.append(doc)
            
            doc_checks["required_docs"] = {
                "all_present": len(missing_docs) == 0,
                "missing": missing_docs
            }
            
            all_passed = doc_checks["required_docs"]["all_present"]
            
            duration = time.time() - start_time
            
            return ValidationResult(
                test_name="documentation",
                success=all_passed,
                duration_seconds=duration,
                details=doc_checks,
                error_message=None if all_passed else f"缺少文档: {missing_docs}"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return ValidationResult(
                test_name="documentation",
                success=False,
                duration_seconds=duration,
                details={},
                error_message=str(e)
            )
    
    def generate_report(self) -> str:
        """生成验证报告"""
        report_path = self.project_root / "reports" / f"refactor_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(exist_ok=True)
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "passed_tests": sum(1 for r in self.results if r.success),
            "failed_tests": sum(1 for r in self.results if not r.success),
            "total_duration": sum(r.duration_seconds for r in self.results),
            "overall_success": all(r.success for r in self.results),
            "tests": [
                {
                    "name": r.test_name,
                    "success": r.success,
                    "duration": r.duration_seconds,
                    "details": r.details,
                    "error": r.error_message
                }
                for r in self.results
            ]
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        return str(report_path)

def main():
    """主函数"""
    validator = RefactorValidator(project_root)
    
    print("🔍 PktMask 重构验证器")
    print("=" * 50)
    
    success = validator.run_all_validations()
    
    # 生成报告
    report_path = validator.generate_report()
    
    print(f"\n📊 验证报告已生成: {report_path}")
    
    if success:
        print("\n🎉 所有验证测试通过！重构成功！")
        sys.exit(0)
    else:
        print("\n❌ 部分验证测试失败，请检查报告详情")
        sys.exit(1)

if __name__ == "__main__":
    main()
