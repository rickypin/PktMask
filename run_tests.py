#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask 测试运行器
支持多种测试模式和报告生成
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional


class TestRunner:
    """测试运行器类"""
    
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
        运行指定类型的测试
        
        Args:
            test_type: 测试类型 (unit, integration, e2e, performance, real_data, all)
            coverage: 是否生成覆盖率报告
            html_report: 是否生成HTML报告
            verbose: 详细输出
            parallel: 并行运行测试
            fail_fast: 遇到失败立即停止
            custom_args: 自定义pytest参数
            
        Returns:
            测试退出码
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
            
        print(f"🚀 运行命令: {' '.join(cmd)}")
        print(f"📝 测试类型: {test_type}")
        print(f"📊 覆盖率报告: {'是' if coverage else '否'}")
        print(f"📄 HTML报告: {'是' if html_report else '否'}")
        print("-" * 50)
        
        return subprocess.run(cmd).returncode
    
    def quick_test(self) -> int:
        """快速测试 - 只运行单元测试，无覆盖率"""
        print("⚡ 快速测试模式 - 仅单元测试")
        return self.run_tests(
            test_type="unit",
            coverage=False,
            verbose=False,
            fail_fast=True
        )
    
    def full_test(self) -> int:
        """完整测试 - 所有测试类型，包含报告"""
        print("🔥 完整测试模式 - 所有测试 + 完整报告")
        return self.run_tests(
            test_type="all",
            coverage=True,
            html_report=True,
            parallel=True
        )
    
    def performance_test(self) -> int:
        """性能测试"""
        print("⏱️ 性能测试模式")
        return self.run_tests(
            test_type="performance", 
            coverage=False,
            verbose=True
        )
    
    def real_data_test(self) -> int:
        """真实数据验证测试"""
        print("🔍 真实数据验证测试模式")
        return self.run_tests(
            test_type="real_data",
            coverage=False,
            verbose=True,
            html_report=True
        )
    
    def samples_validation(self) -> int:
        """样本验证测试 - 专门针对所有samples目录"""
        print("📁 样本数据完整验证测试")
        print("🎯 测试范围: tests/data/samples/ 下的所有目录")
        
        # 运行特定的真实数据验证测试
        return self.run_tests(
            test_type="real_data and integration",
            coverage=False,
            verbose=True,
            html_report=True,
            custom_args=[
                "tests/integration/test_real_data_validation.py",
                "--durations=20",  # 显示最慢的20个测试
                "-s"  # 不捕获输出，显示print语句
            ]
        )


def setup_test_environment():
    """设置测试环境变量"""
    # 设置无GUI测试环境
    os.environ['PKTMASK_TEST_MODE'] = 'true'
    os.environ['PKTMASK_HEADLESS'] = 'true'
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    # 设置Python路径
    project_root = Path(__file__).parent
    src_path = project_root / "src"
    
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    # 注释掉这行，因为它会阻止pytest插件加载
    # os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'


def main():
    """主函数"""
    # 首先设置测试环境
    setup_test_environment()
    
    parser = argparse.ArgumentParser(description="PktMask测试运行器")
    parser.add_argument("--quick", action="store_true", 
                       help="快速测试模式 (无覆盖率)")
    parser.add_argument("--full", action="store_true", 
                       help="完整测试模式 (覆盖率 + HTML报告)")
    parser.add_argument("--type", 
                       choices=["unit", "integration", "e2e", "real_data", "performance"],
                       help="运行特定类型的测试")
    parser.add_argument("--samples", action="store_true",
                       help="运行真实数据样本验证测试")
    parser.add_argument("--parallel", action="store_true",
                       help="并行执行测试")
    parser.add_argument("--html", action="store_true",
                       help="生成HTML测试报告")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="详细输出")
    
    args = parser.parse_args()
    
    # 确保reports目录存在
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "junit").mkdir(exist_ok=True)
    (reports_dir / "coverage").mkdir(exist_ok=True)
    
    # 构建pytest命令
    pytest_args = ["python", "-m", "pytest"]
    
    # 添加JUnit XML报告
    pytest_args.extend(["--junit-xml=output/reports/junit/results.xml"])
    
    if args.quick:
        print("🔥 快速测试模式 - 仅运行基础测试")
        pytest_args.extend(["-x", "--tb=short"])
    elif args.full:
        print("🔥 完整测试模式 - 所有测试 + 完整报告")
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
        # 默认模式：带覆盖率但无HTML
        pytest_args.extend([
            "--cov=src/pktmask",
            "--cov-report=html:output/reports/coverage",
            "--cov-report=term-missing"
        ])
    
    # 测试类型选择
    if args.type:
        print(f"🎯 运行 {args.type} 测试")
        pytest_args.extend(["-m", args.type])
    elif args.samples:
        print("🧪 运行真实数据样本验证")
        pytest_args.extend(["-m", "real_data"])
    
    # 其他选项
    if args.html and not args.full:
        pytest_args.extend([
            "--html=output/reports/test_report.html",
            "--self-contained-html"
        ])
    
    if args.verbose:
        pytest_args.append("-v")
    else:
        pytest_args.append("-v")  # 默认详细输出
    
    print(f"🚀 运行命令: {' '.join(pytest_args)}")
    print(f"📝 测试类型: {args.type if args.type else 'all'}")
    print(f"📊 覆盖率报告: {'是' if not args.quick else '否'}")
    print(f"📄 HTML报告: {'是' if args.html or args.full else '否'}")
    print("-" * 50)
    
    # 执行测试
    try:
        result = subprocess.run(pytest_args, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        return 1
    except Exception as e:
        print(f"执行测试时出错: {e}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 测试运行器错误: {e}")
        sys.exit(1) 