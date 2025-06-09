#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask 自动化测试套件
用于打包发布前的完整测试验证

功能:
- 运行所有测试类型 (单元、集成、性能)
- 生成统一的测试报告
- 支持CI/CD集成
- 提供测试覆盖率分析

使用方法:
    python test_suite.py              # 运行所有测试
    python test_suite.py --quick      # 快速测试(跳过性能测试)
    python test_suite.py --unit       # 仅单元测试
    python test_suite.py --integration # 仅集成测试
    python test_suite.py --performance # 仅性能测试
"""

import os
import sys
import argparse
import time
import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 设置GUI测试环境变量（必须在Qt应用程序启动之前设置）
os.environ['QT_QPA_PLATFORM'] = 'offscreen'  # 无头模式
os.environ['PYTEST_CURRENT_TEST'] = 'automated_test'  # 标识自动化测试环境

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

class TestSuiteRunner:
    """测试套件运行器"""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.start_time = datetime.now()
        self.test_results = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'skipped': 0,
            'duration': 0,
            'test_suites': {},
            'coverage': {},
            'environment': self._get_environment_info()
        }
        
        self.output_dir = output_dir or Path.cwd() / "test_reports"
        self.output_dir.mkdir(exist_ok=True)
        
        # 测试发现路径
        self.test_paths = {
            'unit': [
                'tests/test_basic_phase_7.py',
                'tests/test_config_system.py',
                'tests/test_algorithm_plugins.py',
                'tests/test_managers.py',
                'tests/test_pktmask.py',
                'tests/test_gui.py',
                'tests/test_core_ip_processor_unit.py'
            ],
            'integration': [
                'tests/test_integration_phase_7.py',
                'test_phase_6_4_basic.py',
                'test_plugin_system.py',
                'test_enhanced_plugin_system.py'
            ],
            'performance': [
                'tests/performance/test_runner.py',
                'tests/performance/benchmark_suite.py',
                'tests/performance/run_optimization_test.py'
            ],
            'phase_specific': [
                'test_phase_6_2_optimized_plugins.py',
                'test_phase_6_2_enhanced_plugins.py', 
                'test_phase_6_3_algorithm_configs.py',
                'test_phase_6_4_dynamic_loading.py'
            ]
        }
    
    def _get_environment_info(self) -> Dict[str, Any]:
        """获取环境信息"""
        import platform
        try:
            import psutil
            memory_info = psutil.virtual_memory()
            cpu_count = psutil.cpu_count()
        except ImportError:
            memory_info = None
            cpu_count = os.cpu_count()
        
        return {
            'python_version': platform.python_version(),
            'platform': platform.platform(),
            'architecture': platform.architecture(),
            'cpu_count': cpu_count,
            'memory_total': memory_info.total if memory_info else None,
            'timestamp': self.start_time.isoformat(),
            'working_directory': str(Path.cwd())
        }
    
    def run_pytest_suite(self, test_paths: List[str], suite_name: str) -> Dict[str, Any]:
        """运行pytest测试套件"""
        print(f"\n{'='*60}")
        print(f"运行 {suite_name} 测试套件")
        print(f"{'='*60}")
        
        existing_paths = [p for p in test_paths if Path(p).exists()]
        if not existing_paths:
            print(f"⚠️  {suite_name}: 没有找到有效的测试文件")
            return {
                'total': 0, 'passed': 0, 'failed': 0, 'errors': 0, 'skipped': 0,
                'duration': 0, 'output': f"No test files found for {suite_name}"
            }
        
        # 创建临时pytest配置
        pytest_args = [
            'python', '-m', 'pytest',
            '-v',
            '--tb=short',
            '--durations=10',
            '--junitxml=' + str(self.output_dir / f'{suite_name}_results.xml')
        ] + existing_paths
        
        try:
            start_time = time.time()
            result = subprocess.run(
                pytest_args,
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            duration = time.time() - start_time
            
            # 解析pytest结果
            results = self._parse_pytest_output(result.stdout, result.stderr, duration)
            results['exit_code'] = result.returncode
            results['command'] = ' '.join(pytest_args)
            
            print(f"✅ {suite_name} 完成: {results['passed']}/{results['total']} 通过")
            return results
            
        except Exception as e:
            print(f"❌ {suite_name} 执行失败: {e}")
            return {
                'total': 0, 'passed': 0, 'failed': 1, 'errors': 1, 'skipped': 0,
                'duration': 0, 'output': str(e), 'exit_code': 1
            }
    
    def run_standalone_tests(self, test_paths: List[str], suite_name: str) -> Dict[str, Any]:
        """运行独立的测试脚本"""
        print(f"\n{'='*60}")
        print(f"运行 {suite_name} 独立测试")
        print(f"{'='*60}")
        
        total_results = {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0, 'skipped': 0, 'duration': 0}
        
        for test_path in test_paths:
            if not Path(test_path).exists():
                continue
                
            print(f"\n🔍 执行: {test_path}")
            try:
                start_time = time.time()
                result = subprocess.run(
                    [sys.executable, test_path],
                    capture_output=True,
                    text=True,
                    cwd=Path.cwd()
                )
                duration = time.time() - start_time
                
                if result.returncode == 0:
                    total_results['passed'] += 1
                    print(f"✅ {test_path} - 通过 ({duration:.2f}s)")
                else:
                    total_results['failed'] += 1
                    print(f"❌ {test_path} - 失败 ({duration:.2f}s)")
                    print(f"错误输出: {result.stderr}")
                
                total_results['total'] += 1
                total_results['duration'] += duration
                
            except Exception as e:
                total_results['errors'] += 1
                total_results['total'] += 1
                print(f"💥 {test_path} - 执行错误: {e}")
        
        return total_results
    
    def _parse_pytest_output(self, stdout: str, stderr: str, duration: float) -> Dict[str, Any]:
        """解析pytest输出"""
        results = {
            'total': 0, 'passed': 0, 'failed': 0, 'errors': 0, 'skipped': 0,
            'duration': duration, 'output': stdout, 'stderr': stderr
        }
        
        # 简单的输出解析
        lines = stdout.split('\n')
        for line in lines:
            if 'passed' in line and ('failed' in line or 'error' in line or 'skipped' in line or 'in' in line):
                # 匹配类似 "5 passed, 2 failed in 10.5s"
                import re
                match = re.search(r'(\d+) passed(?:, (\d+) failed)?(?:, (\d+) error)?(?:, (\d+) skipped)?', line)
                if match:
                    results['passed'] = int(match.group(1) or 0)
                    results['failed'] = int(match.group(2) or 0) 
                    results['errors'] = int(match.group(3) or 0)
                    results['skipped'] = int(match.group(4) or 0)
                    results['total'] = results['passed'] + results['failed'] + results['errors'] + results['skipped']
                break
        
        return results
    
    def generate_coverage_report(self) -> Dict[str, Any]:
        """生成覆盖率报告"""
        print(f"\n{'='*60}")
        print("生成测试覆盖率报告")
        print(f"{'='*60}")
        
        try:
            # 运行覆盖率分析
            coverage_cmd = [
                'python', '-m', 'pytest',
                '--cov=src/pktmask',
                '--cov-report=json:' + str(self.output_dir / 'coverage.json'),
                '--cov-report=html:' + str(self.output_dir / 'htmlcov'),
                '--cov-report=term',
                'tests/'
            ]
            
            result = subprocess.run(coverage_cmd, capture_output=True, text=True)
            
            # 解析覆盖率结果
            coverage_file = self.output_dir / 'coverage.json'
            if coverage_file.exists():
                with open(coverage_file, 'r') as f:
                    coverage_data = json.load(f)
                    
                return {
                    'total_coverage': coverage_data.get('totals', {}).get('percent_covered', 0),
                    'lines_covered': coverage_data.get('totals', {}).get('covered_lines', 0),
                    'lines_total': coverage_data.get('totals', {}).get('num_statements', 0),
                    'files': coverage_data.get('files', {}),
                    'report_path': str(self.output_dir / 'htmlcov' / 'index.html')
                }
        
        except Exception as e:
            print(f"⚠️  覆盖率报告生成失败: {e}")
            
        return {'total_coverage': 0, 'error': str(e) if 'e' in locals() else 'Unknown error'}
    
    def run_all_tests(self, test_types: List[str] = None) -> Dict[str, Any]:
        """运行所有测试"""
        if test_types is None:
            test_types = ['unit', 'integration', 'phase_specific', 'performance']
        
        print(f"\n🚀 开始 PktMask 自动化测试套件")
        print(f"📅 开始时间: {self.start_time}")
        print(f"📁 报告目录: {self.output_dir}")
        
        # 运行各类测试
        for test_type in test_types:
            if test_type in self.test_paths:
                if test_type in ['unit', 'integration']:
                    results = self.run_pytest_suite(self.test_paths[test_type], test_type)
                else:
                    results = self.run_standalone_tests(self.test_paths[test_type], test_type)
                
                self.test_results['test_suites'][test_type] = results
                self.test_results['total_tests'] += results['total']
                self.test_results['passed'] += results['passed']
                self.test_results['failed'] += results['failed']
                self.test_results['errors'] += results['errors']
                self.test_results['skipped'] += results['skipped']
        
        # 生成覆盖率报告
        if 'unit' in test_types or 'integration' in test_types:
            self.test_results['coverage'] = self.generate_coverage_report()
        
        # 计算总耗时
        self.test_results['duration'] = (datetime.now() - self.start_time).total_seconds()
        
        return self.test_results
    
    def generate_summary_report(self) -> str:
        """生成汇总报告"""
        report_file = self.output_dir / f"test_summary_{self.start_time.strftime('%Y%m%d_%H%M%S')}.html"
        
        # 计算通过率
        pass_rate = (self.test_results['passed'] / max(self.test_results['total_tests'], 1)) * 100
        overall_status = '通过' if self.test_results['failed'] == 0 and self.test_results['errors'] == 0 else '失败'
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PktMask 测试报告</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; text-align: center; margin-bottom: 30px; }}
        h2 {{ color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
        .metric h3 {{ margin: 0 0 10px 0; font-size: 1.2em; }}
        .metric .value {{ font-size: 2em; font-weight: bold; }}
        .success {{ background: linear-gradient(135deg, #4ecdc4 0%, #44a08d 100%); }}
        .warning {{ background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); color: #333; }}
        .error {{ background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%); }}
        .suite {{ margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .suite h3 {{ margin-top: 0; color: #2980b9; }}
        .status-pass {{ color: #27ae60; font-weight: bold; }}
        .status-fail {{ color: #e74c3c; font-weight: bold; }}
        .progress-bar {{ width: 100%; height: 10px; background: #ecf0f1; border-radius: 5px; overflow: hidden; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #2ecc71, #27ae60); transition: width 0.3s; }}
        .timestamp {{ text-align: center; color: #7f8c8d; margin-top: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 PktMask 自动化测试报告</h1>
        
        <div class="summary">
            <div class="metric {'success' if overall_status == '通过' else 'error'}">
                <h3>总体状态</h3>
                <div class="value">{'✅ ' + overall_status}</div>
            </div>
            <div class="metric">
                <h3>测试总数</h3>
                <div class="value">{self.test_results['total_tests']}</div>
            </div>
            <div class="metric success">
                <h3>通过</h3>
                <div class="value">{self.test_results['passed']}</div>
            </div>
            <div class="metric {'error' if self.test_results['failed'] > 0 else 'success'}">
                <h3>失败</h3>
                <div class="value">{self.test_results['failed']}</div>
            </div>
            <div class="metric {'warning' if self.test_results['errors'] > 0 else 'success'}">
                <h3>错误</h3>
                <div class="value">{self.test_results['errors']}</div>
            </div>
            <div class="metric">
                <h3>耗时</h3>
                <div class="value">{self.test_results['duration']:.1f}s</div>
            </div>
        </div>
        
        <div class="progress-bar">
            <div class="progress-fill" style="width: {pass_rate:.1f}%"></div>
        </div>
        
        <h2>📊 测试套件详情</h2>"""
        
        for suite_name, results in self.test_results['test_suites'].items():
            status_class = "status-pass" if results['failed'] == 0 and results['errors'] == 0 else "status-fail"
            status_text = '通过' if results['failed'] == 0 and results['errors'] == 0 else '失败'
            html_content += f"""
        <div class="suite">
            <h3>{suite_name.title()} 测试套件</h3>
            <table>
                <tr><td>状态</td><td class="{status_class}">{status_text}</td></tr>
                <tr><td>总计</td><td>{results['total']}</td></tr>
                <tr><td>通过</td><td>{results['passed']}</td></tr>
                <tr><td>失败</td><td>{results['failed']}</td></tr>
                <tr><td>错误</td><td>{results['errors']}</td></tr>
                <tr><td>跳过</td><td>{results['skipped']}</td></tr>
                <tr><td>耗时</td><td>{results['duration']:.2f}s</td></tr>
            </table>
        </div>"""
        
        # 覆盖率信息
        if 'coverage' in self.test_results and self.test_results['coverage'] and 'total_coverage' in self.test_results['coverage']:
            coverage = self.test_results['coverage']
            html_content += f"""
        <h2>📈 代码覆盖率</h2>
        <div class="suite">
            <table>
                <tr><td>总体覆盖率</td><td>{coverage.get('total_coverage', 0):.1f}%</td></tr>
                <tr><td>覆盖行数</td><td>{coverage.get('lines_covered', 0)}</td></tr>
                <tr><td>总行数</td><td>{coverage.get('lines_total', 0)}</td></tr>
                {'<tr><td>详细报告</td><td><a href="' + coverage.get('report_path', '') + '">查看HTML报告</a></td></tr>' if 'report_path' in coverage else ''}
            </table>
        </div>"""
        
        # 环境信息
        env = self.test_results['environment']
        html_content += f"""
        <h2>🔧 环境信息</h2>
        <div class="suite">
            <table>
                <tr><td>Python版本</td><td>{env['python_version']}</td></tr>
                <tr><td>平台</td><td>{env['platform']}</td></tr>
                <tr><td>CPU核心数</td><td>{env['cpu_count']}</td></tr>
                <tr><td>执行时间</td><td>{env['timestamp']}</td></tr>
                <tr><td>工作目录</td><td>{env['working_directory']}</td></tr>
            </table>
        </div>
        
        <div class="timestamp">
            📅 报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>"""
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # 同时生成JSON报告
        json_report_file = self.output_dir / f"test_summary_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_report_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        
        return str(report_file)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PktMask 自动化测试套件')
    parser.add_argument('--quick', action='store_true', help='快速测试(跳过性能测试)')
    parser.add_argument('--unit', action='store_true', help='仅运行单元测试')
    parser.add_argument('--integration', action='store_true', help='仅运行集成测试')
    parser.add_argument('--performance', action='store_true', help='仅运行性能测试')
    parser.add_argument('--output', type=str, help='输出目录', default='test_reports')
    
    args = parser.parse_args()
    
    # 确定要运行的测试类型
    test_types = []
    if args.unit:
        test_types.append('unit')
    elif args.integration:
        test_types.append('integration')
    elif args.performance:
        test_types.append('performance')
    elif args.quick:
        test_types = ['unit', 'integration', 'phase_specific']
    else:
        test_types = ['unit', 'integration', 'phase_specific', 'performance']
    
    # 创建输出目录
    output_dir = Path(args.output)
    
    # 运行测试套件
    runner = TestSuiteRunner(output_dir)
    results = runner.run_all_tests(test_types)
    
    # 生成报告
    report_file = runner.generate_summary_report()
    
    # 打印结果摘要
    print(f"\n{'='*60}")
    print("🎯 测试完成摘要")
    print(f"{'='*60}")
    print(f"📊 总计: {results['total_tests']} 个测试")
    print(f"✅ 通过: {results['passed']}")
    print(f"❌ 失败: {results['failed']}")
    print(f"💥 错误: {results['errors']}")
    print(f"⏭️  跳过: {results['skipped']}")
    print(f"⏱️  耗时: {results['duration']:.1f} 秒")
    
    if 'coverage' in results and results['coverage']:
        print(f"📈 代码覆盖率: {results['coverage'].get('total_coverage', 0):.1f}%")
    
    print(f"\n📋 详细报告: {report_file}")
    print(f"📁 报告目录: {output_dir}")
    
    # 根据测试结果设置退出码
    exit_code = 0 if results['failed'] == 0 and results['errors'] == 0 else 1
    print(f"\n{'🎉 所有测试通过!' if exit_code == 0 else '⚠️  存在测试失败，请检查报告'}")
    
    return exit_code


if __name__ == "__main__":
    exit(main()) 