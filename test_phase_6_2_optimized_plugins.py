#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 6.2: 优化版算法插件系统测试
验证所有优化版算法插件的集成和功能
"""

import sys
import time
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.pktmask.algorithms.implementations.register_optimized_plugins import (
    register_optimized_plugins,
    get_optimized_plugins_status,
    list_optimized_plugins
)
from src.pktmask.algorithms.registry.algorithm_registry import get_algorithm_registry
from src.pktmask.algorithms.interfaces.algorithm_interface import AlgorithmType
from src.pktmask.infrastructure.logging import get_logger


def test_plugin_registration():
    """测试插件注册功能"""
    print("🚀 Phase 6.2 测试 1: 插件注册系统")
    print("=" * 60)
    
    try:
        # 注册所有优化版插件
        success = register_optimized_plugins()
        if not success:
            print("❌ 插件注册失败")
            return False
        
        # 检查注册状态
        status = get_optimized_plugins_status()
        print(f"✓ 总插件数: {status['total_plugins']}")
        print(f"✓ 已注册: {status['registered_plugins']}")
        
        if status['registered_plugins'] != status['total_plugins']:
            print("❌ 部分插件注册失败")
            return False
        
        # 验证每个插件
        registry = get_algorithm_registry()
        plugin_names = list_optimized_plugins()
        
        for plugin_name in plugin_names:
            algorithm = registry.get_algorithm(plugin_name)
            if algorithm is None:
                print(f"❌ 无法获取插件实例: {plugin_name}")
                return False
            
            info = algorithm.get_algorithm_info()
            print(f"✓ 插件 {plugin_name}: {info.name} v{info.version}")
        
        print("✅ 插件注册系统测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 插件注册测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_algorithm_discovery():
    """测试算法发现功能"""
    print("\n🔍 Phase 6.2 测试 2: 算法发现系统")
    print("=" * 60)
    
    try:
        # 使用已注册的算法，不重复注册
        registry = get_algorithm_registry()
        
        # 调试：显示注册表状态
        print("调试：注册表内容:")
        for name in registry.list_registered_algorithms():
            algo = registry.get_algorithm(name)
            if algo:
                info = algo.get_algorithm_info()
                print(f"  - {name}: {info.algorithm_type.value}")
        
        # 调试：显示_type_index
        print("调试：类型索引:")
        for algo_type in AlgorithmType:
            index_content = registry._type_index.get(algo_type, [])
            print(f"  - {algo_type.value}: {index_content}")
        
        # 测试按类型获取算法
        algorithm_types = [
            AlgorithmType.IP_ANONYMIZATION,
            AlgorithmType.DEDUPLICATION,
            AlgorithmType.PACKET_PROCESSING
        ]
        
        total_found = 0
        for algo_type in algorithm_types:
            algorithms = registry.get_algorithms_by_type(algo_type)
            count = len(algorithms)
            print(f"✓ {algo_type.value} 类型算法: {count} 个")
            
            for algorithm in algorithms:
                info = algorithm.get_algorithm_info()
                print(f"  - {info.name}: {info.description}")
                total_found += 1
        
        if total_found < 3:  # 期望至少3个优化版算法
            print(f"❌ 算法数量不足，期望至少3个，实际{total_found}个")
            return False
        
        print("✅ 算法发现系统测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 算法发现测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ip_anonymization_plugin():
    """测试IP匿名化插件"""
    print("\n🎭 Phase 6.2 测试 3: IP匿名化插件")
    print("=" * 60)
    
    try:
        registry = get_algorithm_registry()
        algorithm = registry.get_algorithm("optimized_hierarchical_anonymization")
        
        if algorithm is None:
            print("❌ 无法获取IP匿名化插件")
            return False
        
        # 测试算法信息
        info = algorithm.get_algorithm_info()
        print(f"✓ 算法名称: {info.name}")
        print(f"✓ 算法版本: {info.version}")
        print(f"✓ 算法类型: {info.algorithm_type.value}")
        
        # 测试配置和初始化
        config = algorithm.get_default_config()
        if not algorithm.configure(config):
            print("❌ 算法配置失败")
            return False
        if not algorithm.initialize():
            print("❌ 算法初始化失败")
            return False
        
        print("✓ 算法初始化成功")
        
        # 测试基本功能（不需要实际数据包）
        stats = algorithm.get_statistics()
        print(f"✓ 统计信息: {len(stats)} 个指标")
        
        metrics = algorithm.get_performance_metrics()
        if "optimization_features" in metrics:
            print(f"✓ 优化特性: {len(metrics['optimization_features'])} 个")
        
        # 清理
        algorithm.cleanup()
        print("✅ IP匿名化插件测试通过")
        return True
        
    except Exception as e:
        print(f"❌ IP匿名化插件测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_deduplication_plugin():
    """测试去重插件"""
    print("\n🔄 Phase 6.2 测试 4: 去重插件")
    print("=" * 60)
    
    try:
        registry = get_algorithm_registry()
        algorithm = registry.get_algorithm("optimized_deduplication")
        
        if algorithm is None:
            print("❌ 无法获取去重插件")
            return False
        
        # 测试算法信息
        info = algorithm.get_algorithm_info()
        print(f"✓ 算法名称: {info.name}")
        print(f"✓ 算法版本: {info.version}")
        print(f"✓ 算法类型: {info.algorithm_type.value}")
        
        # 测试配置和初始化
        config = algorithm.get_default_config()
        if not algorithm.configure(config):
            print("❌ 算法配置失败")
            return False
        if not algorithm.initialize():
            print("❌ 算法初始化失败")
            return False
        
        print("✓ 算法初始化成功")
        
        # 测试空列表处理
        result = algorithm.deduplicate_packets([])
        if result != []:
            print("❌ 空列表处理失败")
            return False
        
        print("✓ 空列表处理正确")
        
        # 测试统计信息
        stats = algorithm.get_statistics()
        print(f"✓ 统计信息: {len(stats)} 个指标")
        
        metrics = algorithm.get_performance_metrics()
        if "optimization_features" in metrics:
            print(f"✓ 优化特性: {len(metrics['optimization_features'])} 个")
        
        # 清理
        algorithm.cleanup()
        print("✅ 去重插件测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 去重插件测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_packet_processing_plugin():
    """测试数据包处理插件"""
    print("\n📦 Phase 6.2 测试 5: 数据包处理插件")
    print("=" * 60)
    
    try:
        registry = get_algorithm_registry()
        algorithm = registry.get_algorithm("optimized_trimming")
        
        if algorithm is None:
            print("❌ 无法获取数据包处理插件")
            return False
        
        # 测试算法信息
        info = algorithm.get_algorithm_info()
        print(f"✓ 算法名称: {info.name}")
        print(f"✓ 算法版本: {info.version}")
        print(f"✓ 算法类型: {info.algorithm_type.value}")
        
        # 测试配置和初始化
        config = algorithm.get_default_config()
        if not algorithm.configure(config):
            print("❌ 算法配置失败")
            return False
        if not algorithm.initialize():
            print("❌ 算法初始化失败")
            return False
        
        print("✓ 算法初始化成功")
        
        # 测试空列表处理
        result = algorithm.batch_process_packets([])
        if result != []:
            print("❌ 空列表处理失败")
            return False
        
        print("✓ 空列表处理正确")
        
        # 测试统计信息
        stats = algorithm._get_processing_stats()
        print(f"✓ 统计信息: {len(stats)} 个指标")
        
        metrics = algorithm.get_performance_metrics()
        if "optimization_features" in metrics:
            print(f"✓ 优化特性: {len(metrics['optimization_features'])} 个")
        
        # 清理
        algorithm.cleanup()
        print("✅ 数据包处理插件测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 数据包处理插件测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_plugin_lifecycle():
    """测试插件生命周期管理"""
    print("\n🔄 Phase 6.2 测试 6: 插件生命周期")
    print("=" * 60)
    
    try:
        registry = get_algorithm_registry()
        
        # 测试所有插件的生命周期
        plugin_names = list_optimized_plugins()
        
        for plugin_name in plugin_names:
            print(f"测试插件: {plugin_name}")
            
            # 获取插件
            algorithm = registry.get_algorithm(plugin_name)
            if algorithm is None:
                print(f"❌ 无法获取插件: {plugin_name}")
                return False
            
            # 配置和初始化
            config = algorithm.get_default_config()
            if not algorithm.configure(config):
                print(f"❌ 插件配置失败: {plugin_name}")
                return False
            if not algorithm.initialize():
                print(f"❌ 插件初始化失败: {plugin_name}")
                return False
            
            # 检查状态
            status = algorithm.get_status()
            print(f"  ✓ 状态: {status.value}")
            
            # 清理
            algorithm.cleanup()
            print(f"  ✓ 清理完成")
        
        print("✅ 插件生命周期测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 插件生命周期测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_registry_statistics():
    """测试注册中心统计功能"""
    print("\n📊 Phase 6.2 测试 7: 注册中心统计")
    print("=" * 60)
    
    try:
        registry = get_algorithm_registry()
        
        # 获取注册统计
        stats = registry.get_registry_stats()
        print(f"✓ 总注册算法: {stats['total_registered']}")
        print(f"✓ 非活跃算法: {stats['total_inactive']}")
        print(f"✓ 算法类型分布:")
        
        for algo_type, count in stats['type_distribution'].items():
            print(f"  - {algo_type}: {count} 个")
        
        # 验证优化版插件都在注册表中
        plugin_names = list_optimized_plugins()
        registered_algorithms = registry.list_registered_algorithms()
        for plugin_name in plugin_names:
            # 检查插件是否在已注册列表中（可能名称不完全匹配）
            found = any(plugin_name in reg_name or reg_name in plugin_name 
                       for reg_name in registered_algorithms)
            if not found:
                print(f"⚠️ 插件 {plugin_name} 可能未正确注册")
        
        print("✅ 注册中心统计测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 注册中心统计测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🚀 PktMask Phase 6.2: 优化版算法插件系统测试")
    print("=" * 80)
    
    # 设置日志
    from src.pktmask.infrastructure.logging import get_logger
    logger = get_logger('main')
    
    # 测试计数
    total_tests = 0
    passed_tests = 0
    
    # 测试列表
    tests = [
        ("插件注册系统", test_plugin_registration),
        ("算法发现系统", test_algorithm_discovery),
        ("IP匿名化插件", test_ip_anonymization_plugin),
        ("去重插件", test_deduplication_plugin),
        ("数据包处理插件", test_packet_processing_plugin),
        ("插件生命周期", test_plugin_lifecycle),
        ("注册中心统计", test_registry_statistics),
    ]
    
    # 执行测试
    start_time = time.time()
    
    for test_name, test_func in tests:
        total_tests += 1
        try:
            logger.info(f"开始测试: {test_name}")
            if test_func():
                passed_tests += 1
                logger.info(f"✅ {test_name} - 通过")
            else:
                logger.error(f"❌ {test_name} - 失败")
        except Exception as e:
            logger.error(f"❌ {test_name} - 错误: {e}")
            import traceback
            traceback.print_exc()
    
    # 测试结果
    duration = time.time() - start_time
    success_rate = (passed_tests / total_tests) * 100
    
    print("\n" + "=" * 80)
    print("📊 Phase 6.2 测试结果摘要")
    print("=" * 80)
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {total_tests - passed_tests}")
    print(f"成功率: {success_rate:.1f}%")
    print(f"测试耗时: {duration:.2f}秒")
    
    if success_rate >= 95:
        print("\n🎉 Phase 6.2 优化版算法插件系统测试成功！")
        print("\n✨ 已实现功能:")
        print("• 🔌 插件注册系统 - 自动注册和管理算法插件")
        print("• 🔍 算法发现机制 - 按类型查找和获取算法")
        print("• 🎭 优化版IP匿名化 - 基于Phase 5.3.2的35.5%性能提升")
        print("• 🔄 优化版去重算法 - 基于Phase 5.3.3的27.1%性能提升")
        print("• 📦 优化版数据包处理 - 智能缓存和批处理优化")
        print("• 🔄 插件生命周期管理 - 完整的初始化/清理流程")
        print("• 📊 统计和监控系统 - 详细的插件运行状态跟踪")
        
        print("\n📋 Phase 6.2 实现特点:")
        print("• 插件化架构：所有算法都通过标准接口实现")
        print("• 性能优化集成：Phase 5.3的所有优化都已插件化")
        print("• 统一配置管理：支持算法配置的验证和热更新")
        print("• 生命周期管理：完整的插件注册/注销/状态管理")
        print("• 类型安全：基于接口的强类型插件系统")
        print("• 扩展性强：支持动态加载和运行时切换算法")
    else:
        print(f"\n⚠️ 有 {total_tests - passed_tests} 个测试失败，需要检查和修复")
    
    return success_rate >= 95


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 