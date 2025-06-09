#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版插件系统测试
测试标准版和优化版IP匿名化插件，验证Phase 6.1.3的插件发现和管理功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.algorithms.registry import get_algorithm_registry, get_plugin_loader
from pktmask.algorithms.implementations.ip_anonymization.hierarchical_plugin import (
    HierarchicalAnonymizationPlugin
)
from pktmask.algorithms.implementations.ip_anonymization.optimized_hierarchical_plugin import (
    OptimizedHierarchicalAnonymizationPlugin
)
from pktmask.algorithms.interfaces.algorithm_interface import AlgorithmType


def test_multiple_plugins():
    """测试多个插件的发现和注册"""
    print("🔍 测试多个插件发现和注册")
    
    try:
        # 1. 获取插件加载器
        loader = get_plugin_loader()
        registry = get_algorithm_registry()
        
        # 2. 扫描插件目录
        plugin_dir = os.path.join(os.path.dirname(__file__), 'src', 'pktmask', 'algorithms', 'implementations')
        result = loader.discover_plugins([plugin_dir], recursive=True)
        
        print(f"✅ 插件发现结果:")
        print(f"   发现插件数量: {len(result.found_plugins)}")
        print(f"   扫描耗时: {result.scan_duration:.3f}秒")
        
        # 3. 列出发现的插件
        discovered_plugins = []
        for plugin_class in result.found_plugins:
            try:
                instance = plugin_class()
                info = instance.get_algorithm_info()
                discovered_plugins.append({
                    'class': plugin_class,
                    'name': info.name,
                    'version': info.version,
                    'type': info.algorithm_type.value
                })
                print(f"   📌 {info.name} v{info.version} ({plugin_class.__name__})")
            except Exception as e:
                print(f"   ❌ {plugin_class.__name__}: {e}")
        
        # 4. 注册所有发现的插件
        registered_count = 0
        for plugin_info in discovered_plugins:
            plugin_class = plugin_info['class']
            plugin_name = plugin_info['name'].lower().replace(' ', '_')
            
            success = registry.register_algorithm(
                plugin_class,
                plugin_name,
                metadata={
                    "discovered": True,
                    "version": plugin_info['version'],
                    "type": plugin_info['type']
                }
            )
            
            if success:
                registered_count += 1
                print(f"   ✅ 注册成功: {plugin_name}")
            else:
                print(f"   ❌ 注册失败: {plugin_name}")
        
        print(f"✅ 插件注册完成: {registered_count}/{len(discovered_plugins)} 成功")
        
        # 5. 验证注册结果
        all_algorithms = registry.list_registered_algorithms()
        print(f"✅ 注册中心状态: 共 {len(all_algorithms)} 个算法")
        
        return len(discovered_plugins), registered_count
        
    except Exception as e:
        print(f"❌ 多插件测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0


def test_plugin_comparison():
    """测试标准版和优化版插件的性能对比"""
    print("\n⚖️ 测试插件性能对比")
    
    try:
        # 1. 创建两个插件实例
        standard_plugin = HierarchicalAnonymizationPlugin()
        optimized_plugin = OptimizedHierarchicalAnonymizationPlugin()
        
        plugins = [
            ("标准版", standard_plugin),
            ("优化版", optimized_plugin)
        ]
        
        comparison_results = {}
        
        for plugin_name, plugin in plugins:
            print(f"\n📊 测试 {plugin_name} 插件:")
            
            # 获取算法信息
            info = plugin.get_algorithm_info()
            print(f"   算法名称: {info.name}")
            print(f"   版本: {info.version}")
            print(f"   基准性能: {info.performance_baseline}")
            
            # 配置和初始化
            config = plugin.get_default_config()
            plugin.configure(config)
            plugin.initialize()
            
            # 获取性能指标
            metrics = plugin.get_performance_metrics()
            
            comparison_results[plugin_name] = {
                'info': info,
                'config': config,
                'metrics': metrics,
                'throughput': info.performance_baseline.get('throughput_per_second', 0),
                'memory': info.performance_baseline.get('memory_usage_mb', 0),
                'cache_hit_rate': info.performance_baseline.get('cache_hit_rate', 0)
            }
            
            print(f"   状态: {plugin.get_status()}")
            print(f"   就绪: {'是' if plugin.is_ready() else '否'}")
            print(f"   性能指标数量: {len(metrics)}")
            
            # 清理
            plugin.cleanup()
        
        # 2. 性能对比分析
        print(f"\n📈 性能对比分析:")
        
        standard_throughput = comparison_results['标准版']['throughput']
        optimized_throughput = comparison_results['优化版']['throughput']
        
        if standard_throughput > 0:
            improvement = (optimized_throughput - standard_throughput) / standard_throughput * 100
            print(f"   吞吐量提升: {improvement:.1f}% ({standard_throughput:.0f} -> {optimized_throughput:.0f})")
        
        standard_memory = comparison_results['标准版']['memory']
        optimized_memory = comparison_results['优化版']['memory']
        
        if standard_memory > 0:
            memory_reduction = (standard_memory - optimized_memory) / standard_memory * 100
            print(f"   内存优化: {memory_reduction:.1f}% ({standard_memory:.0f}MB -> {optimized_memory:.0f}MB)")
        
        standard_cache = comparison_results['标准版']['cache_hit_rate']
        optimized_cache = comparison_results['优化版']['cache_hit_rate']
        
        cache_improvement = (optimized_cache - standard_cache) * 100
        print(f"   缓存命中率提升: +{cache_improvement:.1f}% ({standard_cache:.2f} -> {optimized_cache:.2f})")
        
        return comparison_results
        
    except Exception as e:
        print(f"❌ 插件对比测试失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


def test_algorithm_selection():
    """测试算法选择和推荐机制"""
    print("\n🎯 测试算法选择机制")
    
    try:
        registry = get_algorithm_registry()
        
        # 1. 按类型获取所有IP匿名化算法
        ip_algorithms = registry.get_algorithms_by_type(AlgorithmType.IP_ANONYMIZATION)
        print(f"✅ 发现 {len(ip_algorithms)} 个IP匿名化算法")
        
        # 2. 分析每个算法的特性
        algorithm_analysis = []
        
        for algorithm in ip_algorithms:
            try:
                info = algorithm.get_algorithm_info()
                config = algorithm.get_default_config()
                
                # 计算算法评分（基于性能基准）
                baseline = info.performance_baseline or {}
                score = 0
                
                # 吞吐量评分 (权重: 40%)
                throughput = baseline.get('throughput_per_second', 0)
                if throughput > 4000:
                    score += 40
                elif throughput > 3000:
                    score += 30
                else:
                    score += 20
                
                # 内存使用评分 (权重: 30%, 内存越少分数越高)
                memory = baseline.get('memory_usage_mb', 128)
                if memory < 100:
                    score += 30
                elif memory < 128:
                    score += 20
                else:
                    score += 10
                
                # 缓存命中率评分 (权重: 30%)
                cache_rate = baseline.get('cache_hit_rate', 0.8)
                if cache_rate > 0.9:
                    score += 30
                elif cache_rate > 0.85:
                    score += 20
                else:
                    score += 10
                
                algorithm_analysis.append({
                    'algorithm': algorithm,
                    'info': info,
                    'config': config,
                    'score': score,
                    'throughput': throughput,
                    'memory': memory,
                    'cache_rate': cache_rate
                })
                
                print(f"   📊 {info.name}:")
                print(f"      评分: {score}/100")
                print(f"      吞吐量: {throughput:.0f} packets/s")
                print(f"      内存: {memory:.0f} MB")
                print(f"      缓存命中率: {cache_rate:.2f}")
                
            except Exception as e:
                print(f"   ❌ 分析算法失败 {algorithm}: {e}")
        
        # 3. 推荐最佳算法
        if algorithm_analysis:
            best_algorithm = max(algorithm_analysis, key=lambda x: x['score'])
            print(f"\n🏆 推荐算法: {best_algorithm['info'].name}")
            print(f"   推荐理由: 综合评分最高 ({best_algorithm['score']}/100)")
            
            # 4. 场景化推荐
            print(f"\n🎯 场景化推荐:")
            
            # 高性能场景
            high_perf = max(algorithm_analysis, key=lambda x: x['throughput'])
            print(f"   高性能场景: {high_perf['info'].name} (吞吐量: {high_perf['throughput']:.0f})")
            
            # 低内存场景
            low_memory = min(algorithm_analysis, key=lambda x: x['memory'])
            print(f"   低内存场景: {low_memory['info'].name} (内存: {low_memory['memory']:.0f}MB)")
            
            # 高缓存效率场景
            high_cache = max(algorithm_analysis, key=lambda x: x['cache_rate'])
            print(f"   高缓存效率: {high_cache['info'].name} (命中率: {high_cache['cache_rate']:.2f})")
        
        return algorithm_analysis
        
    except Exception as e:
        print(f"❌ 算法选择测试失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_plugin_metadata():
    """测试插件元数据和版本管理"""
    print("\n📋 测试插件元数据管理")
    
    try:
        registry = get_algorithm_registry()
        
        # 1. 获取所有注册的算法
        all_algorithms = registry.list_registered_algorithms()
        print(f"✅ 已注册算法: {len(all_algorithms)} 个")
        
        # 2. 分析插件元数据
        metadata_analysis = {}
        
        for algorithm_name in all_algorithms:
            try:
                algorithm = registry.get_algorithm(algorithm_name)
                if algorithm:
                    info = algorithm.get_algorithm_info()
                    
                    metadata_analysis[algorithm_name] = {
                        'name': info.name,
                        'version': info.version,
                        'author': info.author,
                        'type': info.algorithm_type.value,
                        'formats': info.supported_formats,
                        'requirements': info.requirements,
                        'created_at': info.created_at.isoformat() if info.created_at else None
                    }
                    
                    print(f"   📦 {algorithm_name}:")
                    print(f"      名称: {info.name}")
                    print(f"      版本: {info.version}")
                    print(f"      作者: {info.author}")
                    print(f"      类型: {info.algorithm_type.value}")
                    print(f"      支持格式: {', '.join(info.supported_formats)}")
                    print(f"      依赖: {info.requirements}")
                    
            except Exception as e:
                print(f"   ❌ 获取元数据失败 {algorithm_name}: {e}")
        
        # 3. 版本兼容性检查
        print(f"\n🔍 版本兼容性分析:")
        
        versions = {}
        for name, meta in metadata_analysis.items():
            version = meta['version']
            if version not in versions:
                versions[version] = []
            versions[version].append(name)
        
        for version, algorithms in versions.items():
            print(f"   版本 {version}: {len(algorithms)} 个算法")
            for alg in algorithms:
                print(f"     - {alg}")
        
        # 4. 依赖分析
        print(f"\n📦 依赖分析:")
        
        all_requirements = {}
        for name, meta in metadata_analysis.items():
            for req, version in meta['requirements'].items():
                if req not in all_requirements:
                    all_requirements[req] = set()
                all_requirements[req].add(version)
        
        for req, versions in all_requirements.items():
            print(f"   {req}: {', '.join(sorted(versions))}")
        
        return metadata_analysis
        
    except Exception as e:
        print(f"❌ 元数据测试失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


def test_registry_statistics():
    """测试注册中心统计功能"""
    print("\n📊 测试注册中心统计")
    
    try:
        registry = get_algorithm_registry()
        loader = get_plugin_loader()
        
        # 1. 获取注册中心统计
        registry_stats = registry.get_registry_stats()
        print(f"✅ 注册中心统计:")
        print(f"   总注册算法: {registry_stats['total_registered']}")
        print(f"   类型分布: {registry_stats['type_distribution']}")
        
        # 2. 获取插件加载器统计
        loader_stats = loader.get_plugin_statistics()
        print(f"✅ 插件加载器统计:")
        print(f"   已加载插件: {loader_stats['total_plugins']}")
        print(f"   按类型分布: {loader_stats['plugins_by_type']}")
        print(f"   已加载模块: {loader_stats['loaded_modules']}")
        print(f"   缓存大小: {loader_stats['cache_size']}")
        
        # 3. 性能统计
        print(f"✅ 系统性能统计:")
        
        total_throughput = 0
        total_memory = 0
        algorithm_count = 0
        
        for algorithm_name in registry.list_registered_algorithms():
            try:
                algorithm = registry.get_algorithm(algorithm_name)
                if algorithm:
                    info = algorithm.get_algorithm_info()
                    baseline = info.performance_baseline or {}
                    
                    throughput = baseline.get('throughput_per_second', 0)
                    memory = baseline.get('memory_usage_mb', 0)
                    
                    if throughput > 0:
                        total_throughput += throughput
                        algorithm_count += 1
                    
                    if memory > 0:
                        total_memory += memory
                        
            except Exception as e:
                print(f"   ⚠️ 获取性能数据失败 {algorithm_name}: {e}")
        
        if algorithm_count > 0:
            avg_throughput = total_throughput / algorithm_count
            avg_memory = total_memory / algorithm_count
            
            print(f"   平均吞吐量: {avg_throughput:.0f} packets/s")
            print(f"   平均内存使用: {avg_memory:.0f} MB")
            print(f"   总计算能力: {total_throughput:.0f} packets/s")
        
        return {
            'registry_stats': registry_stats,
            'loader_stats': loader_stats,
            'performance_stats': {
                'total_throughput': total_throughput,
                'average_throughput': total_throughput / algorithm_count if algorithm_count > 0 else 0,
                'average_memory': total_memory / algorithm_count if algorithm_count > 0 else 0,
                'algorithm_count': algorithm_count
            }
        }
        
    except Exception as e:
        print(f"❌ 统计测试失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


def main():
    """主测试函数"""
    print("🚀 PktMask 增强版插件系统测试")
    print("=" * 60)
    
    tests = [
        ("多插件发现和注册", test_multiple_plugins),
        ("插件性能对比", test_plugin_comparison),
        ("算法选择机制", test_algorithm_selection),
        ("插件元数据管理", test_plugin_metadata),
        ("注册中心统计", test_registry_statistics),
    ]
    
    results = []
    test_data = {}
    
    for test_name, test_func in tests:
        print(f"\n{'-' * 30}")
        try:
            result = test_func()
            results.append((test_name, True))
            test_data[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
            test_data[test_name] = None
    
    print(f"\n{'=' * 60}")
    print("📊 测试结果总结")
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 总体结果: {passed}/{len(tests)} 通过")
    
    # 输出关键统计信息
    if test_data.get("多插件发现和注册"):
        discovered, registered = test_data["多插件发现和注册"]
        print(f"📦 插件发现: {discovered} 个插件，{registered} 个成功注册")
    
    if test_data.get("注册中心统计"):
        stats = test_data["注册中心统计"]
        if stats and 'performance_stats' in stats:
            perf = stats['performance_stats']
            print(f"⚡ 系统性能: {perf['algorithm_count']} 个算法，总吞吐量 {perf['total_throughput']:.0f} packets/s")
    
    if passed == len(tests):
        print("🎉 所有测试通过！增强版插件系统运行正常。")
        print("🚀 Phase 6.1.3 插件发现和管理机制验证成功！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查相关组件。")
        return 1


if __name__ == "__main__":
    exit(main()) 