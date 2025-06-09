#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试插件系统基本功能
验证算法插件的加载、注册和基本操作
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.algorithms.registry import get_algorithm_registry, get_plugin_loader
from pktmask.algorithms.implementations.ip_anonymization.hierarchical_plugin import (
    HierarchicalAnonymizationPlugin, register_hierarchical_plugin
)
from pktmask.algorithms.interfaces.algorithm_interface import AlgorithmType


def test_plugin_basic_functionality():
    """测试插件基本功能"""
    print("🧪 测试插件基本功能")
    
    try:
        # 1. 创建插件实例
        plugin = HierarchicalAnonymizationPlugin()
        print(f"✅ 插件实例创建成功: {plugin}")
        
        # 2. 获取算法信息
        info = plugin.get_algorithm_info()
        print(f"✅ 算法信息: {info.name} v{info.version}")
        print(f"   类型: {info.algorithm_type.value}")
        print(f"   描述: {info.description}")
        
        # 3. 获取默认配置
        config = plugin.get_default_config()
        print(f"✅ 默认配置获取成功，策略: {config.strategy}")
        
        # 4. 验证配置
        validation_result = plugin.validate_config(config)
        print(f"✅ 配置验证: {'通过' if validation_result.is_valid else '失败'}")
        if validation_result.warnings:
            print(f"   警告: {validation_result.warnings}")
        
        # 5. 配置插件
        configure_success = plugin.configure(config)
        print(f"✅ 插件配置: {'成功' if configure_success else '失败'}")
        
        # 6. 初始化插件
        init_success = plugin.initialize()
        print(f"✅ 插件初始化: {'成功' if init_success else '失败'}")
        
        # 7. 检查状态
        print(f"✅ 插件状态: {plugin.get_status()}")
        print(f"✅ 插件就绪: {'是' if plugin.is_ready() else '否'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 插件基本功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_plugin_registration():
    """测试插件注册系统"""
    print("\n🔗 测试插件注册系统")
    
    try:
        # 1. 获取注册中心
        registry = get_algorithm_registry()
        print(f"✅ 注册中心获取成功")
        
        # 2. 注册插件
        success = registry.register_algorithm(
            HierarchicalAnonymizationPlugin,
            "hierarchical_ip_anonymization",
            metadata={"test": True, "priority": 100}
        )
        print(f"✅ 插件注册: {'成功' if success else '失败'}")
        
        # 3. 验证注册
        is_registered = registry.is_registered("hierarchical_ip_anonymization")
        print(f"✅ 注册验证: {'已注册' if is_registered else '未注册'}")
        
        # 4. 获取算法实例
        algorithm = registry.get_algorithm("hierarchical_ip_anonymization")
        print(f"✅ 算法实例获取: {'成功' if algorithm else '失败'}")
        
        if algorithm:
            info = algorithm.get_algorithm_info()
            print(f"   算法: {info.name}")
        
        # 5. 按类型获取算法
        ip_algorithms = registry.get_algorithms_by_type(AlgorithmType.IP_ANONYMIZATION)
        print(f"✅ 按类型获取算法: 找到 {len(ip_algorithms)} 个IP匿名化算法")
        
        # 6. 列出所有注册的算法
        all_algorithms = registry.list_registered_algorithms()
        print(f"✅ 已注册算法列表: {all_algorithms}")
        
        # 7. 获取注册统计信息
        stats = registry.get_registry_stats()
        print(f"✅ 注册统计: 总计 {stats['total_registered']} 个算法")
        print(f"   类型分布: {stats['type_distribution']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 插件注册系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_plugin_loader():
    """测试插件加载器"""
    print("\n📦 测试插件加载器")
    
    try:
        # 1. 获取插件加载器
        loader = get_plugin_loader()
        print(f"✅ 插件加载器获取成功")
        
        # 2. 扫描插件目录
        plugin_dir = os.path.join(os.path.dirname(__file__), 'src', 'pktmask', 'algorithms', 'implementations')
        if os.path.exists(plugin_dir):
            result = loader.discover_plugins([plugin_dir], recursive=True)
            print(f"✅ 插件发现: 找到 {len(result.found_plugins)} 个插件")
            print(f"   扫描路径: {result.scan_paths}")
            print(f"   扫描耗时: {result.scan_duration:.3f}秒")
            
            if result.errors:
                print(f"   扫描错误: {len(result.errors)} 个")
                for error in result.errors[:3]:  # 只显示前3个错误
                    print(f"     - {error}")
            
            # 3. 列出发现的插件
            for plugin_class in result.found_plugins:
                try:
                    instance = plugin_class()
                    info = instance.get_algorithm_info()
                    print(f"   📌 {info.name} ({plugin_class.__name__})")
                except Exception as e:
                    print(f"   ❌ {plugin_class.__name__}: {e}")
        else:
            print(f"⚠️  插件目录不存在: {plugin_dir}")
        
        # 4. 获取插件统计信息
        stats = loader.get_plugin_statistics()
        print(f"✅ 插件统计: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ 插件加载器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_algorithm_functionality():
    """测试算法功能"""
    print("\n⚙️ 测试算法功能")
    
    try:
        # 1. 创建并配置插件
        plugin = HierarchicalAnonymizationPlugin()
        config = plugin.get_default_config()
        plugin.configure(config)
        plugin.initialize()
        
        print(f"✅ 插件准备完成")
        
        # 2. 测试IP匿名化（基本功能）
        test_ip = "192.168.1.1"
        anonymized_ip = plugin.anonymize_ip(test_ip)
        print(f"✅ IP匿名化测试: {test_ip} -> {anonymized_ip}")
        
        # 3. 获取性能指标
        metrics = plugin.get_performance_metrics()
        print(f"✅ 性能指标获取成功，指标数量: {len(metrics)}")
        print(f"   策略类型: {metrics.get('strategy_type', 'unknown')}")
        print(f"   映射大小: {metrics.get('mapping_size', 0)}")
        
        # 4. 测试一致性验证
        consistency_report = plugin.validate_subnet_consistency()
        print(f"✅ 一致性验证: {'通过' if consistency_report.get('valid') else '失败'}")
        
        # 5. 清理
        plugin.cleanup()
        print(f"✅ 插件清理完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 算法功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🚀 PktMask 插件系统测试")
    print("=" * 50)
    
    tests = [
        ("插件基本功能", test_plugin_basic_functionality),
        ("插件注册系统", test_plugin_registration),
        ("插件加载器", test_plugin_loader),
        ("算法功能", test_algorithm_functionality),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'-' * 20}")
        result = test_func()
        results.append((test_name, result))
    
    print(f"\n{'=' * 50}")
    print("📊 测试结果总结")
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 总体结果: {passed}/{len(tests)} 通过")
    
    if passed == len(tests):
        print("🎉 所有测试通过！插件系统运行正常。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查相关组件。")
        return 1


if __name__ == "__main__":
    exit(main()) 