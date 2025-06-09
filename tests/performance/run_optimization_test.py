#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IP匿名化算法优化版本性能比较测试
用于验证优化效果
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
    logger = get_logger('optimization_test')
    logger.info("开始运行IP匿名化算法优化测试")
    
    try:
        # 创建测试运行器
        runner = PerformanceTestRunner(output_dir="performance_results")
        
        # 运行包含优化版本的基准测试
        logger.info("运行包含优化版本的完整基准测试...")
        baseline_report = runner.run_baseline_establishment()
        
        # 查找之前的基线报告进行比较
        baseline_files = []
        for file in os.listdir("performance_results"):
            if file.startswith("baseline_report_") and file.endswith(".json"):
                baseline_files.append(os.path.join("performance_results", file))
        
        if len(baseline_files) >= 2:
            # 使用倒数第二个基线报告作为对比基准
            baseline_files.sort()
            old_baseline = baseline_files[-2]
            
            logger.info(f"使用基线文件进行比较: {old_baseline}")
            
            # 进行性能比较
            from benchmark_suite import AlgorithmBenchmark
            benchmark = AlgorithmBenchmark()
            
            # 只运行优化版本测试获取当前结果
            current_results = {
                'ip_anonymization_optimized': benchmark.benchmark_ip_anonymization_optimized()
            }
            
            comparison_report = runner.compare_with_baseline(old_baseline, current_results)
            
            # 生成包含比较的HTML报告
            html_report = runner.generate_html_report(baseline_report, comparison_report)
            
            logger.info(f"比较报告已生成: {html_report}")
        else:
            logger.info("没有足够的基线数据进行比较，仅生成当前基线报告")
            html_report = runner.generate_html_report(baseline_report)
        
        # 打印优化效果总结
        print("\n=== IP匿名化算法优化测试结果 ===")
        
        if 'ip_anonymization_original' in baseline_report.get('baseline_metrics', {}):
            original_metrics = baseline_report['baseline_metrics']['ip_anonymization_original']
            print(f"\n原版本算法:")
            print(f"  平均吞吐量: {original_metrics['throughput_mbps']['avg']:.2f} MB/s")
            print(f"  平均处理速度: {original_metrics['packets_per_second']['avg']:.0f} packets/s")
            print(f"  平均内存使用: {original_metrics['memory_usage_mb']['avg']:.1f} MB")
            
        if 'ip_anonymization_optimized' in baseline_report.get('baseline_metrics', {}):
            optimized_metrics = baseline_report['baseline_metrics']['ip_anonymization_optimized']
            print(f"\n优化版本算法:")
            print(f"  平均吞吐量: {optimized_metrics['throughput_mbps']['avg']:.2f} MB/s")
            print(f"  平均处理速度: {optimized_metrics['packets_per_second']['avg']:.0f} packets/s")
            print(f"  平均内存使用: {optimized_metrics['memory_usage_mb']['avg']:.1f} MB")
            
            # 计算改进百分比
            if 'ip_anonymization_original' in baseline_report.get('baseline_metrics', {}):
                original = baseline_report['baseline_metrics']['ip_anonymization_original']
                optimized = baseline_report['baseline_metrics']['ip_anonymization_optimized']
                
                throughput_improvement = ((optimized['throughput_mbps']['avg'] - original['throughput_mbps']['avg']) / original['throughput_mbps']['avg']) * 100
                speed_improvement = ((optimized['packets_per_second']['avg'] - original['packets_per_second']['avg']) / original['packets_per_second']['avg']) * 100
                memory_improvement = ((original['memory_usage_mb']['avg'] - optimized['memory_usage_mb']['avg']) / original['memory_usage_mb']['avg']) * 100
                
                print(f"\n性能改进:")
                print(f"  吞吐量提升: {throughput_improvement:+.1f}%")
                print(f"  处理速度提升: {speed_improvement:+.1f}%")
                print(f"  内存使用优化: {memory_improvement:+.1f}%")
                
                # 判断优化效果
                avg_improvement = (throughput_improvement + speed_improvement + memory_improvement) / 3
                if avg_improvement > 10:
                    print(f"✅ 优化效果显著! 平均改进: {avg_improvement:.1f}%")
                elif avg_improvement > 5:
                    print(f"✅ 优化效果良好! 平均改进: {avg_improvement:.1f}%")
                elif avg_improvement > 0:
                    print(f"✅ 有轻微改进! 平均改进: {avg_improvement:.1f}%")
                else:
                    print(f"⚠️ 需要进一步优化! 平均改进: {avg_improvement:.1f}%")
        
        print(f"\n详细测试报告: {html_report}")
        
        return 0
        
    except Exception as e:
        logger.error(f"优化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 