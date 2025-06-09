#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基准测试运行脚本
用于建立算法性能基线和验证测试框架
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from test_runner import PerformanceTestRunner
from pktmask.infrastructure.logging import get_logger


def main():
    """主函数"""
    logger = get_logger('baseline_test')
    logger.info("开始运行基线建立测试")
    
    try:
        # 创建测试运行器
        runner = PerformanceTestRunner(output_dir="performance_results")
        
        # 运行基线建立测试
        baseline_report = runner.run_baseline_establishment()
        
        # 生成HTML报告
        html_report = runner.generate_html_report(baseline_report)
        
        logger.info("基线建立测试完成!")
        logger.info(f"基线报告: {baseline_report}")
        logger.info(f"HTML报告: {html_report}")
        
        # 打印结果摘要
        print("\n=== 基线建立测试结果摘要 ===")
        if 'test_summary' in baseline_report:
            summary = baseline_report['test_summary']
            print(f"总算法数: {summary.get('total_algorithms', 0)}")
            print(f"总测试数: {summary.get('total_tests', 0)}")
            print(f"成功测试: {summary.get('successful_tests', 0)}")
            print(f"失败测试: {summary.get('failed_tests', 0)}")
        
        if 'baseline_metrics' in baseline_report:
            print("\n算法性能基线:")
            for algorithm, metrics in baseline_report['baseline_metrics'].items():
                print(f"\n{algorithm}:")
                print(f"  平均吞吐量: {metrics['throughput_mbps']['avg']:.2f} MB/s")
                print(f"  平均处理速度: {metrics['packets_per_second']['avg']:.0f} packets/s")
                print(f"  平均内存使用: {metrics['memory_usage_mb']['avg']:.1f} MB")
                print(f"  成功率: {metrics['success_rate']:.1%}")
        
        return 0
        
    except Exception as e:
        logger.error(f"基线建立测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 