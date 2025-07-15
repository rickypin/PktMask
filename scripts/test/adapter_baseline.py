#!/usr/bin/env python3
"""
适配器重构测试基线记录脚本

用于记录重构前的测试结果，以便后续对比验证。
"""

import subprocess
import json
import datetime
import os
from pathlib import Path

def run_tests():
    """Run all adapter-related tests and record results"""

    # Test results storage path
    output_dir = Path("output/reports/adapter_refactoring")
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_file = output_dir / f"baseline_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    results = {
        "timestamp": datetime.datetime.now().isoformat(),
        "tests": {},
        "performance": {},
        "coverage": {}
    }

    # Find all adapter-related test files
    test_patterns = [
        "test_*adapter*.py",
        "test_*compat*.py"
    ]

    print("Searching for adapter-related test files...")
    test_files = []
    for pattern in test_patterns:
        cmd = f"find tests -name '{pattern}' -type f"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            test_files.extend(result.stdout.strip().split('\n'))

    test_files = [f for f in test_files if f]  # Filter empty strings
    
    if not test_files:
        print("警告：未找到适配器相关的测试文件")
        # 运行所有测试
        print("运行所有测试作为基线...")
        cmd = "python -m pytest tests/ -v --tb=short"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        results["tests"]["all"] = {
            "command": cmd,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    else:
        # 运行找到的测试文件
        for test_file in test_files:
            print(f"运行测试：{test_file}")
            cmd = f"python -m pytest {test_file} -v --tb=short"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            results["tests"][test_file] = {
                "command": cmd,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
    
    # 记录当前代码覆盖率（如果有 coverage 工具）
    print("\n检查代码覆盖率...")
    coverage_cmd = "python -m coverage run -m pytest tests/ && python -m coverage report"
    coverage_result = subprocess.run(coverage_cmd, shell=True, capture_output=True, text=True)
    
    if coverage_result.returncode == 0:
        results["coverage"]["report"] = coverage_result.stdout
    else:
        print("覆盖率测试失败或未安装 coverage 工具")
    
    # 保存基线结果
    with open(baseline_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n测试基线已保存到：{baseline_file}")
    
    # 生成摘要
    print("\n=== 测试基线摘要 ===")
    total_tests = len(results["tests"])
    passed_tests = sum(1 for r in results["tests"].values() if r["returncode"] == 0)
    failed_tests = total_tests - passed_tests
    
    print(f"总测试数：{total_tests}")
    print(f"通过：{passed_tests}")
    print(f"失败：{failed_tests}")
    
    return baseline_file

if __name__ == "__main__":
    run_tests()
