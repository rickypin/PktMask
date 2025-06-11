#!/usr/bin/env python3
"""
PktMask 现代化测试运行器
支持多种测试类型和输出格式
"""
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
                "--cov-report=html:reports/coverage",
                "--cov-report=term-missing"
            ])
            
        # 添加HTML报告
        if html_report:
            cmd.extend([
                "--html=reports/test_report.html",
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


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description="PktMask 现代化测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
测试类型:
  unit        - 单元测试 (快速)
  integration - 集成测试  
  e2e         - 端到端测试
  performance - 性能测试
  real_data   - 真实数据验证测试
  all         - 所有测试

专门测试模式:
  --samples   - 样本数据完整验证 (覆盖所有samples目录)

使用示例:
  python run_tests.py --quick          # 快速单元测试
  python run_tests.py --full           # 完整测试套件
  python run_tests.py --samples        # 样本数据验证
  python run_tests.py --type real_data # 真实数据测试
  python run_tests.py --type performance # 性能测试
  python run_tests.py --no-coverage    # 不生成覆盖率
        """
    )
    
    # 预设模式
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--quick", action="store_true", 
                           help="快速模式 - 仅单元测试")
    mode_group.add_argument("--full", action="store_true",
                           help="完整模式 - 所有测试 + 报告")
    mode_group.add_argument("--samples", action="store_true",
                           help="样本验证 - tests/data/samples/ 完整验证")
    
    # 测试配置
    parser.add_argument("--type", choices=["unit", "integration", "e2e", "performance", "real_data", "all"],
                       default="all", help="测试类型")
    parser.add_argument("--no-coverage", action="store_true",
                       help="禁用覆盖率报告")
    parser.add_argument("--html", action="store_true",
                       help="生成HTML测试报告")
    parser.add_argument("--parallel", action="store_true",
                       help="并行运行测试")
    parser.add_argument("--fail-fast", action="store_true",
                       help="遇到失败立即停止")
    parser.add_argument("--quiet", action="store_true",
                       help="静默模式")
    
    # 自定义pytest参数
    parser.add_argument("pytest_args", nargs="*",
                       help="传递给pytest的额外参数")
    
    args = parser.parse_args()
    
    # 创建测试运行器
    runner = TestRunner()
    
    # 根据模式运行
    if args.quick:
        return runner.quick_test()
    elif args.full:
        return runner.full_test()
    elif args.samples:
        return runner.samples_validation()
    else:
        return runner.run_tests(
            test_type=args.type,
            coverage=not args.no_coverage,
            html_report=args.html,
            verbose=not args.quiet,
            parallel=args.parallel,
            fail_fast=args.fail_fast,
            custom_args=args.pytest_args
        )


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