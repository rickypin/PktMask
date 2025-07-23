#!/usr/bin/env python3
"""
PktMask测试脚本可用性验证工具

对项目中的所有测试脚本进行全面的可用性验证，包括：
1. 导入验证
2. 语法检查
3. 执行测试
4. 依赖分析
5. 架构兼容性验证
"""

import ast
import importlib
import importlib.util
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Any
import json

class TestValidator:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.results = {}
        
    def validate_all_tests(self) -> Dict[str, Any]:
        """验证所有测试脚本"""
        test_files = self._find_test_files()
        
        print(f"Found {len(test_files)} test files to validate")
        print("=" * 60)
        
        for test_file in test_files:
            print(f"\n🔍 Validating: {test_file}")
            result = self._validate_single_test(test_file)
            self.results[str(test_file)] = result
            
            # 打印简要结果
            status = "✅ PASS" if result['overall_status'] == 'PASS' else "❌ FAIL"
            print(f"   {status} - {result['summary']}")
            
        return self.results
    
    def _find_test_files(self) -> List[Path]:
        """查找所有测试文件"""
        test_files = []
        test_dir = self.project_root / "tests" / "unit"
        
        for file_path in test_dir.rglob("*.py"):
            if file_path.name.startswith("test_"):
                test_files.append(file_path)
                
        return sorted(test_files)
    
    def _validate_single_test(self, test_file: Path) -> Dict[str, Any]:
        """验证单个测试脚本"""
        result = {
            'file_path': str(test_file),
            'syntax_check': {'status': 'UNKNOWN', 'errors': []},
            'import_check': {'status': 'UNKNOWN', 'errors': [], 'missing_modules': []},
            'execution_test': {'status': 'UNKNOWN', 'errors': [], 'output': ''},
            'dependency_analysis': {'external_deps': [], 'missing_deps': []},
            'overall_status': 'UNKNOWN',
            'summary': '',
            'recommendations': []
        }
        
        try:
            # 1. 语法检查
            result['syntax_check'] = self._check_syntax(test_file)
            
            # 2. 导入验证
            result['import_check'] = self._check_imports(test_file)
            
            # 3. 依赖分析
            result['dependency_analysis'] = self._analyze_dependencies(test_file)
            
            # 4. 执行测试（仅在语法和导入都通过时）
            if (result['syntax_check']['status'] == 'PASS' and 
                result['import_check']['status'] == 'PASS'):
                result['execution_test'] = self._execute_test(test_file)
            
            # 5. 综合评估
            result['overall_status'] = self._evaluate_overall_status(result)
            result['summary'] = self._generate_summary(result)
            result['recommendations'] = self._generate_recommendations(result)
            
        except Exception as e:
            result['overall_status'] = 'ERROR'
            result['summary'] = f'Validation error: {str(e)}'
            result['recommendations'] = ['Fix validation script error']
            
        return result
    
    def _check_syntax(self, test_file: Path) -> Dict[str, Any]:
        """检查Python语法"""
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                source = f.read()
            
            ast.parse(source)
            return {'status': 'PASS', 'errors': []}
            
        except SyntaxError as e:
            return {
                'status': 'FAIL',
                'errors': [f'Syntax error at line {e.lineno}: {e.msg}']
            }
        except Exception as e:
            return {
                'status': 'ERROR',
                'errors': [f'Unexpected error: {str(e)}']
            }
    
    def _check_imports(self, test_file: Path) -> Dict[str, Any]:
        """检查导入语句"""
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            imports = []
            missing_modules = []
            errors = []
            
            # 提取所有导入语句
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            
            # 验证每个导入
            for module_name in imports:
                try:
                    if module_name.startswith('pktmask'):
                        # 项目内部模块，需要特殊处理
                        self._check_internal_module(module_name)
                    else:
                        # 外部模块
                        importlib.import_module(module_name)
                except ImportError as e:
                    missing_modules.append(module_name)
                    errors.append(f'Cannot import {module_name}: {str(e)}')
                except Exception as e:
                    errors.append(f'Error checking {module_name}: {str(e)}')
            
            status = 'PASS' if not errors else 'FAIL'
            return {
                'status': status,
                'errors': errors,
                'missing_modules': missing_modules
            }
            
        except Exception as e:
            return {
                'status': 'ERROR',
                'errors': [f'Import check error: {str(e)}'],
                'missing_modules': []
            }
    
    def _check_internal_module(self, module_name: str):
        """检查项目内部模块"""
        # 将模块名转换为文件路径
        parts = module_name.split('.')
        if parts[0] == 'pktmask':
            # 构建可能的文件路径
            src_path = self.project_root / 'src' / '/'.join(parts)
            
            # 检查是否存在 __init__.py 或 .py 文件
            if (src_path / '__init__.py').exists():
                return True
            elif (src_path.parent / f'{src_path.name}.py').exists():
                return True
            else:
                raise ImportError(f'No module named {module_name}')
        
        return True
    
    def _analyze_dependencies(self, test_file: Path) -> Dict[str, Any]:
        """分析依赖关系"""
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            external_deps = []
            missing_deps = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not alias.name.startswith('pktmask') and not alias.name in ['sys', 'os', 'unittest', 'pytest']:
                            external_deps.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and not node.module.startswith('pktmask'):
                        external_deps.append(node.module)
            
            # 检查外部依赖是否可用
            for dep in external_deps:
                try:
                    importlib.import_module(dep)
                except ImportError:
                    missing_deps.append(dep)
            
            return {
                'external_deps': list(set(external_deps)),
                'missing_deps': missing_deps
            }
            
        except Exception as e:
            return {
                'external_deps': [],
                'missing_deps': [],
                'error': str(e)
            }
    
    def _execute_test(self, test_file: Path) -> Dict[str, Any]:
        """执行测试脚本"""
        try:
            # 使用pytest运行单个测试文件
            cmd = [sys.executable, '-m', 'pytest', str(test_file), '-v', '--tb=short']
            
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60  # 60秒超时
            )
            
            status = 'PASS' if result.returncode == 0 else 'FAIL'
            
            return {
                'status': status,
                'return_code': result.returncode,
                'output': result.stdout,
                'errors': result.stderr.split('\n') if result.stderr else []
            }
            
        except subprocess.TimeoutExpired:
            return {
                'status': 'TIMEOUT',
                'return_code': -1,
                'output': '',
                'errors': ['Test execution timed out after 60 seconds']
            }
        except Exception as e:
            return {
                'status': 'ERROR',
                'return_code': -1,
                'output': '',
                'errors': [f'Execution error: {str(e)}']
            }
    
    def _evaluate_overall_status(self, result: Dict[str, Any]) -> str:
        """评估总体状态"""
        if result['syntax_check']['status'] != 'PASS':
            return 'FAIL'
        
        if result['import_check']['status'] != 'PASS':
            return 'FAIL'
        
        if result['execution_test']['status'] == 'PASS':
            return 'PASS'
        elif result['execution_test']['status'] in ['FAIL', 'TIMEOUT', 'ERROR']:
            return 'NEEDS_FIX'
        else:
            return 'UNKNOWN'
    
    def _generate_summary(self, result: Dict[str, Any]) -> str:
        """生成结果摘要"""
        if result['overall_status'] == 'PASS':
            return 'All checks passed, test is fully functional'
        elif result['overall_status'] == 'FAIL':
            issues = []
            if result['syntax_check']['status'] != 'PASS':
                issues.append('syntax errors')
            if result['import_check']['status'] != 'PASS':
                issues.append('import errors')
            return f'Critical issues: {", ".join(issues)}'
        elif result['overall_status'] == 'NEEDS_FIX':
            return 'Syntax and imports OK, but test execution failed'
        else:
            return 'Status unknown'
    
    def _generate_recommendations(self, result: Dict[str, Any]) -> List[str]:
        """生成修复建议"""
        recommendations = []
        
        if result['syntax_check']['status'] != 'PASS':
            recommendations.append('Fix syntax errors')
        
        if result['import_check']['missing_modules']:
            recommendations.append(f'Fix missing imports: {", ".join(result["import_check"]["missing_modules"])}')
        
        if result['dependency_analysis']['missing_deps']:
            recommendations.append(f'Install missing dependencies: {", ".join(result["dependency_analysis"]["missing_deps"])}')
        
        if result['execution_test']['status'] == 'FAIL':
            recommendations.append('Debug test execution failures')
        elif result['execution_test']['status'] == 'TIMEOUT':
            recommendations.append('Optimize test performance or increase timeout')
        
        if not recommendations:
            recommendations.append('No issues found')
        
        return recommendations

def main():
    """主函数"""
    project_root = os.getcwd()
    validator = TestValidator(project_root)
    
    print("🚀 Starting PktMask Test Validation")
    print(f"📁 Project root: {project_root}")
    
    results = validator.validate_all_tests()
    
    # 生成详细报告
    print("\n" + "=" * 80)
    print("📊 VALIDATION SUMMARY")
    print("=" * 80)
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r['overall_status'] == 'PASS')
    failed_tests = sum(1 for r in results.values() if r['overall_status'] == 'FAIL')
    needs_fix_tests = sum(1 for r in results.values() if r['overall_status'] == 'NEEDS_FIX')
    
    print(f"📈 Total tests: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")
    print(f"🔧 Needs fix: {needs_fix_tests}")
    print(f"📊 Success rate: {passed_tests/total_tests*100:.1f}%")
    
    # 保存详细结果到JSON文件
    with open('test_validation_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to: test_validation_results.json")
    
    return results

if __name__ == "__main__":
    main()
