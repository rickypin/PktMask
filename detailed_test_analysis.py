#!/usr/bin/env python3
"""
详细测试分析脚本
分析每个测试文件的具体问题并生成修复建议
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

def analyze_test_results(results_file: str = 'test_validation_results.json'):
    """分析测试结果并生成详细报告"""
    
    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    print("🔍 DETAILED TEST ANALYSIS REPORT")
    print("=" * 80)
    
    # 按状态分类
    passed_tests = []
    failed_tests = []
    needs_fix_tests = []
    
    for file_path, result in results.items():
        test_name = Path(file_path).name
        status = result['overall_status']
        
        if status == 'PASS':
            passed_tests.append((test_name, result))
        elif status == 'FAIL':
            failed_tests.append((test_name, result))
        elif status == 'NEEDS_FIX':
            needs_fix_tests.append((test_name, result))
    
    # 1. 通过的测试
    print(f"\n✅ PASSED TESTS ({len(passed_tests)})")
    print("-" * 40)
    for test_name, result in passed_tests:
        print(f"  • {test_name}")
        print(f"    Summary: {result['summary']}")
    
    # 2. 完全失败的测试（导入或语法错误）
    print(f"\n❌ FAILED TESTS ({len(failed_tests)})")
    print("-" * 40)
    for test_name, result in failed_tests:
        print(f"  • {test_name}")
        print(f"    Summary: {result['summary']}")
        
        if result['import_check']['missing_modules']:
            print(f"    Missing modules: {', '.join(result['import_check']['missing_modules'])}")
        
        if result['syntax_check']['errors']:
            print(f"    Syntax errors: {result['syntax_check']['errors']}")
        
        print(f"    Recommendations: {'; '.join(result['recommendations'])}")
        print()
    
    # 3. 需要修复的测试（语法和导入OK，但执行失败）
    print(f"\n🔧 NEEDS FIX TESTS ({len(needs_fix_tests)})")
    print("-" * 40)
    for test_name, result in needs_fix_tests:
        print(f"  • {test_name}")
        print(f"    Summary: {result['summary']}")
        
        # 分析执行错误
        if result['execution_test']['errors']:
            print(f"    Execution errors: {result['execution_test']['errors'][:2]}")  # 只显示前2个错误
        
        # 从输出中提取关键错误信息
        output = result['execution_test'].get('output', '')
        if 'ModuleNotFoundError' in output:
            # 提取模块名
            import re
            matches = re.findall(r"ModuleNotFoundError: No module named '([^']+)'", output)
            if matches:
                print(f"    Missing modules in execution: {', '.join(set(matches))}")
        
        if 'ImportError' in output:
            matches = re.findall(r"ImportError: (.+)", output)
            if matches:
                print(f"    Import errors in execution: {matches[0]}")
        
        print(f"    Recommendations: {'; '.join(result['recommendations'])}")
        print()
    
    # 4. 依赖分析
    print(f"\n📦 DEPENDENCY ANALYSIS")
    print("-" * 40)
    
    all_external_deps = set()
    all_missing_deps = set()
    
    for result in results.values():
        all_external_deps.update(result['dependency_analysis'].get('external_deps', []))
        all_missing_deps.update(result['dependency_analysis'].get('missing_deps', []))
    
    print(f"External dependencies used: {', '.join(sorted(all_external_deps))}")
    if all_missing_deps:
        print(f"Missing dependencies: {', '.join(sorted(all_missing_deps))}")
    else:
        print("No missing external dependencies found")
    
    # 5. 常见问题分析
    print(f"\n🔍 COMMON ISSUES ANALYSIS")
    print("-" * 40)
    
    module_not_found_count = 0
    import_error_count = 0
    execution_timeout_count = 0
    
    missing_modules = {}
    
    for result in results.values():
        # 统计导入错误
        if result['import_check']['missing_modules']:
            import_error_count += 1
            for module in result['import_check']['missing_modules']:
                missing_modules[module] = missing_modules.get(module, 0) + 1
        
        # 统计执行错误
        output = result['execution_test'].get('output', '')
        if 'ModuleNotFoundError' in output:
            module_not_found_count += 1
        
        if result['execution_test'].get('status') == 'TIMEOUT':
            execution_timeout_count += 1
    
    print(f"Tests with import errors: {import_error_count}")
    print(f"Tests with module not found in execution: {module_not_found_count}")
    print(f"Tests with execution timeout: {execution_timeout_count}")
    
    if missing_modules:
        print(f"\nMost frequently missing modules:")
        for module, count in sorted(missing_modules.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  • {module}: {count} tests")
    
    # 6. 修复优先级建议
    print(f"\n🎯 REPAIR PRIORITY RECOMMENDATIONS")
    print("-" * 40)
    
    print("HIGH PRIORITY (Critical Issues):")
    for test_name, result in failed_tests:
        if result['import_check']['missing_modules']:
            print(f"  • {test_name}: Fix missing imports")
    
    print("\nMEDIUM PRIORITY (Execution Issues):")
    for test_name, result in needs_fix_tests:
        print(f"  • {test_name}: Debug execution failures")
    
    print("\nLOW PRIORITY (Already Working):")
    for test_name, result in passed_tests:
        print(f"  • {test_name}: No action needed")
    
    # 7. 架构兼容性分析
    print(f"\n🏗️ ARCHITECTURE COMPATIBILITY ANALYSIS")
    print("-" * 40)
    
    v2_tests = [name for name, _ in failed_tests + needs_fix_tests + passed_tests if 'mask_payload_v2' in name]
    legacy_tests = [name for name, _ in failed_tests + needs_fix_tests + passed_tests if 'mask_payload_v2' not in name and 'mask_payload' in name]
    
    print(f"New architecture (v2) tests: {len(v2_tests)}")
    print(f"Legacy architecture tests: {len(legacy_tests)}")
    
    if v2_tests:
        print("V2 tests:")
        for test in v2_tests:
            print(f"  • {test}")
    
    return {
        'passed': len(passed_tests),
        'failed': len(failed_tests),
        'needs_fix': len(needs_fix_tests),
        'total': len(results),
        'success_rate': len(passed_tests) / len(results) * 100
    }

def generate_fix_suggestions():
    """生成具体的修复建议"""
    print(f"\n💡 SPECIFIC FIX SUGGESTIONS")
    print("=" * 80)
    
    print("1. ENVIRONMENT SETUP:")
    print("   • Ensure PYTHONPATH includes src directory")
    print("   • Install all required dependencies from pyproject.toml")
    print("   • Set up proper test environment variables")
    
    print("\n2. IMPORT FIXES:")
    print("   • Check if all imported modules exist in src/pktmask/")
    print("   • Update import paths to match current project structure")
    print("   • Remove imports of deprecated/removed modules")
    
    print("\n3. EXECUTION FIXES:")
    print("   • Add missing test data files")
    print("   • Mock external dependencies (tshark, system tools)")
    print("   • Fix test configuration and setup methods")
    
    print("\n4. ARCHITECTURE UPDATES:")
    print("   • Update tests to use new dual-module maskstage architecture")
    print("   • Replace deprecated processor references")
    print("   • Update test assertions to match new API")

def main():
    """主函数"""
    if not os.path.exists('test_validation_results.json'):
        print("❌ Error: test_validation_results.json not found")
        print("Please run test_validation_script.py first")
        return
    
    stats = analyze_test_results()
    generate_fix_suggestions()
    
    print(f"\n📊 FINAL SUMMARY")
    print("=" * 80)
    print(f"Total tests analyzed: {stats['total']}")
    print(f"Success rate: {stats['success_rate']:.1f}%")
    print(f"Tests needing immediate attention: {stats['failed'] + stats['needs_fix']}")
    
    if stats['success_rate'] < 50:
        print("⚠️  WARNING: Low success rate indicates significant issues")
        print("   Recommend focusing on high-priority fixes first")
    
    return stats

if __name__ == "__main__":
    main()
