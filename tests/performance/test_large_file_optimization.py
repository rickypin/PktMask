#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
大文件数据包处理算法优化测试
专门测试大型pcap文件的性能提升
"""

import sys
import os
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from benchmark_suite import AlgorithmBenchmark


def main():
    """运行大文件数据包处理算法优化测试"""
    print("🚀 启动大文件数据包处理算法优化测试")
    print("=" * 60)
    
    # 大文件路径
    large_file = "../data/big/20180819104500-4248.pcap"
    
    if not os.path.exists(large_file):
        print("❌ 错误: 未找到大文件测试数据")
        print(f"期望路径: {large_file}")
        return 1
    
    file_size_mb = os.path.getsize(large_file) / (1024 * 1024)
    print(f"🎯 使用大文件: {large_file} (大小: {file_size_mb:.1f} MB)")
    
    # 初始化基准测试组件
    benchmark = AlgorithmBenchmark()
    
    # 运行数据包处理算法性能比较
    print("\n" + "=" * 60)
    print("🔧 开始大文件数据包处理算法性能比较测试")
    print("=" * 60)
    
    try:
        # 执行比较测试
        print("⏱️ 测试可能需要几分钟时间，请耐心等待...")
        results = benchmark.compare_packet_processing_algorithms(large_file)
        
        # 显示详细结果
        print("\n📊 大文件测试结果详情:")
        print("-" * 40)
        
        # 裁切算法对比
        print("\n🔪 数据包裁切算法对比:")
        trim_orig = results['trimming_original']
        trim_opt = results['trimming_optimized']
        
        print(f"原始算法: {trim_orig['throughput_mbps']:.2f} MB/s, "
              f"{trim_orig['packets_per_second']:.0f} packets/s, "
              f"{trim_orig['memory_used_mb']:.1f} MB内存, "
              f"耗时: {trim_orig['duration']:.1f}秒")
        print(f"优化算法: {trim_opt['throughput_mbps']:.2f} MB/s, "
              f"{trim_opt['packets_per_second']:.0f} packets/s, "
              f"{trim_opt['memory_used_mb']:.1f} MB内存, "
              f"缓存命中: {trim_opt.get('cache_hits', 0)}, "
              f"耗时: {trim_opt['duration']:.1f}秒")
        
        # 去重算法对比
        print("\n🗂️ 数据包去重算法对比:")
        dedup_orig = results['deduplication_original']
        dedup_opt = results['deduplication_optimized']
        
        print(f"原始算法: {dedup_orig['throughput_mbps']:.2f} MB/s, "
              f"{dedup_orig['packets_per_second']:.0f} packets/s, "
              f"{dedup_orig['memory_used_mb']:.1f} MB内存, "
              f"耗时: {dedup_orig['duration']:.1f}秒")
        print(f"优化算法: {dedup_opt['throughput_mbps']:.2f} MB/s, "
              f"{dedup_opt['packets_per_second']:.0f} packets/s, "
              f"{dedup_opt['memory_used_mb']:.1f} MB内存, "
              f"缓存命中: {dedup_opt.get('cache_hits', 0)}, "
              f"耗时: {dedup_opt['duration']:.1f}秒")
        
        # 性能改进总结
        print("\n📈 大文件性能改进总结:")
        print("-" * 40)
        
        improvements = results['improvements']
        
        # 裁切算法改进
        trim_imp = improvements['trimming']
        print(f"裁切算法优化:")
        print(f"  ✅ 吞吐量改进: {trim_imp['throughput_improvement']:+.1f}%")
        print(f"  ✅ 处理速度改进: {trim_imp['speed_improvement']:+.1f}%")
        print(f"  ✅ 内存优化: {trim_imp['memory_improvement']:+.1f}%")
        print(f"  ⏱️ 时间节省: {(trim_orig['duration'] - trim_opt['duration']):.1f}秒")
        
        avg_trim_improvement = (abs(trim_imp['throughput_improvement']) + 
                               abs(trim_imp['speed_improvement']) + 
                               abs(trim_imp['memory_improvement'])) / 3
        
        # 去重算法改进
        dedup_imp = improvements['deduplication']
        print(f"\n去重算法优化:")
        print(f"  ✅ 吞吐量改进: {dedup_imp['throughput_improvement']:+.1f}%")
        print(f"  ✅ 处理速度改进: {dedup_imp['speed_improvement']:+.1f}%")
        print(f"  ✅ 内存优化: {dedup_imp['memory_improvement']:+.1f}%")
        print(f"  ⏱️ 时间节省: {(dedup_orig['duration'] - dedup_opt['duration']):.1f}秒")
        
        avg_dedup_improvement = (abs(dedup_imp['throughput_improvement']) + 
                                abs(dedup_imp['speed_improvement']) + 
                                abs(dedup_imp['memory_improvement'])) / 3
        
        # 整体评估
        overall_improvement = (avg_trim_improvement + avg_dedup_improvement) / 2
        total_time_saved = ((trim_orig['duration'] - trim_opt['duration']) + 
                           (dedup_orig['duration'] - dedup_opt['duration']))
        
        print(f"\n🎉 大文件整体优化效果:")
        print(f"   文件大小: {file_size_mb:.1f} MB")
        print(f"   裁切算法平均改进: {avg_trim_improvement:.1f}%")
        print(f"   去重算法平均改进: {avg_dedup_improvement:.1f}%")
        print(f"   总体平均改进: {overall_improvement:.1f}%")
        print(f"   总时间节省: {total_time_saved:.1f}秒")
        
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
        results_file = f"large_file_optimization_results_{timestamp}.json"
        
        import json
        # 添加文件信息
        results['file_info'] = {
            'file_path': large_file,
            'file_size_mb': file_size_mb,
            'test_timestamp': timestamp
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 详细结果已保存到: {results_file}")
        
        print("\n" + "=" * 60)
        print("✅ 大文件数据包处理算法优化测试完成!")
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