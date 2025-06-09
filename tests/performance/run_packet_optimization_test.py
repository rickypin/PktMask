#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据包处理算法优化测试脚本
测试裁切和去重算法的优化版本性能
"""

import sys
import os
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from benchmark_suite import AlgorithmBenchmark
from test_runner import PerformanceTestRunner


def main():
    """运行数据包处理算法优化测试"""
    print("🚀 启动 Phase 5.3.3: 数据包处理算法优化测试")
    print("=" * 60)
    
    # 初始化基准测试组件
    benchmark = AlgorithmBenchmark()
    runner = PerformanceTestRunner()
    
    # 获取测试文件
    file_categories = benchmark._get_test_files_by_size()
    all_files = []
    for category, files in file_categories.items():
        all_files.extend(files)
    
    if not all_files:
        print("❌ 错误: 未找到测试pcap文件")
        print("请确保 tests/data/ 目录下存在pcap文件")
        return 1
    
    print(f"📁 找到 {len(all_files)} 个测试文件")
    for category, files in file_categories.items():
        if files:
            print(f"   {category}: {len(files)} 个文件")
    
    # 选择合适大小的文件进行测试 - 优先选择小文件
    selected_file = None
    if file_categories['small']:
        selected_file = file_categories['small'][0]
    elif file_categories['medium']:
        selected_file = file_categories['medium'][0]
    elif file_categories['large']:
        selected_file = file_categories['large'][0]
    else:
        selected_file = all_files[0]
    
    file_size_mb = os.path.getsize(selected_file) / (1024 * 1024)
    print(f"\n🎯 使用测试文件: {selected_file} (大小: {file_size_mb:.2f} MB)")
    
    # 运行数据包处理算法性能比较
    print("\n" + "=" * 60)
    print("🔧 开始数据包处理算法性能比较测试")
    print("=" * 60)
    
    try:
        # 执行比较测试
        results = benchmark.compare_packet_processing_algorithms(selected_file)
        
        # 显示详细结果
        print("\n📊 测试结果详情:")
        print("-" * 40)
        
        # 裁切算法对比
        print("\n🔪 数据包裁切算法对比:")
        trim_orig = results['trimming_original']
        trim_opt = results['trimming_optimized']
        
        print(f"原始算法: {trim_orig['throughput_mbps']:.2f} MB/s, "
              f"{trim_orig['packets_per_second']:.0f} packets/s, "
              f"{trim_orig['memory_used_mb']:.1f} MB内存")
        print(f"优化算法: {trim_opt['throughput_mbps']:.2f} MB/s, "
              f"{trim_opt['packets_per_second']:.0f} packets/s, "
              f"{trim_opt['memory_used_mb']:.1f} MB内存, "
              f"{trim_opt.get('cache_hits', 0)} 缓存命中")
        
        # 去重算法对比
        print("\n🗂️ 数据包去重算法对比:")
        dedup_orig = results['deduplication_original']
        dedup_opt = results['deduplication_optimized']
        
        print(f"原始算法: {dedup_orig['throughput_mbps']:.2f} MB/s, "
              f"{dedup_orig['packets_per_second']:.0f} packets/s, "
              f"{dedup_orig['memory_used_mb']:.1f} MB内存")
        print(f"优化算法: {dedup_opt['throughput_mbps']:.2f} MB/s, "
              f"{dedup_opt['packets_per_second']:.0f} packets/s, "
              f"{dedup_opt['memory_used_mb']:.1f} MB内存, "
              f"{dedup_opt.get('cache_hits', 0)} 缓存命中")
        
        # 性能改进总结
        print("\n📈 性能改进总结:")
        print("-" * 40)
        
        improvements = results['improvements']
        
        # 裁切算法改进
        trim_imp = improvements['trimming']
        print(f"裁切算法优化:")
        print(f"  ✅ 吞吐量改进: {trim_imp['throughput_improvement']:+.1f}%")
        print(f"  ✅ 处理速度改进: {trim_imp['speed_improvement']:+.1f}%")
        print(f"  ✅ 内存优化: {trim_imp['memory_improvement']:+.1f}%")
        
        avg_trim_improvement = (abs(trim_imp['throughput_improvement']) + 
                               abs(trim_imp['speed_improvement']) + 
                               abs(trim_imp['memory_improvement'])) / 3
        
        # 去重算法改进
        dedup_imp = improvements['deduplication']
        print(f"\n去重算法优化:")
        print(f"  ✅ 吞吐量改进: {dedup_imp['throughput_improvement']:+.1f}%")
        print(f"  ✅ 处理速度改进: {dedup_imp['speed_improvement']:+.1f}%")
        print(f"  ✅ 内存优化: {dedup_imp['memory_improvement']:+.1f}%")
        
        avg_dedup_improvement = (abs(dedup_imp['throughput_improvement']) + 
                                abs(dedup_imp['speed_improvement']) + 
                                abs(dedup_imp['memory_improvement'])) / 3
        
        # 整体评估
        overall_improvement = (avg_trim_improvement + avg_dedup_improvement) / 2
        
        print(f"\n🎉 整体优化效果:")
        print(f"   裁切算法平均改进: {avg_trim_improvement:.1f}%")
        print(f"   去重算法平均改进: {avg_dedup_improvement:.1f}%")
        print(f"   总体平均改进: {overall_improvement:.1f}%")
        
        # 优化效果评级
        if overall_improvement >= 30:
            grade = "🏆 显著优化"
        elif overall_improvement >= 15:
            grade = "🥈 良好优化"
        elif overall_improvement >= 5:
            grade = "🥉 轻微优化"
        else:
            grade = "⚠️ 效果有限"
        
        print(f"   优化等级: {grade}")
        
        # 保存详细结果
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        results_file = f"packet_optimization_results_{timestamp}.json"
        
        import json
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 详细结果已保存到: {results_file}")
        
        print("\n" + "=" * 60)
        print("✅ Phase 5.3.3: 数据包处理算法优化测试完成!")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"❌ 测试执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 