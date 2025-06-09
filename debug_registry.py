#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
调试算法注册和类型索引问题
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def debug_registry():
    """调试注册表问题"""
    try:
        from src.pktmask.algorithms.registry.algorithm_registry import get_algorithm_registry
        from src.pktmask.algorithms.interfaces.algorithm_interface import AlgorithmType
        from src.pktmask.algorithms.implementations.ip_anonymization.optimized_hierarchical_plugin import OptimizedHierarchicalAnonymizationPlugin
        
        print("🔍 深度调试算法注册问题")
        print("=" * 50)
        
        # 获取注册表
        registry = get_algorithm_registry()
        
        # 创建临时实例
        temp_instance = OptimizedHierarchicalAnonymizationPlugin()
        algorithm_info = temp_instance.get_algorithm_info()
        
        print(f"算法信息:")
        print(f"  名称: {algorithm_info.name}")
        print(f"  类型: {algorithm_info.algorithm_type}")
        print(f"  类型值: {algorithm_info.algorithm_type.value}")
        print(f"  类型是否等于IP_ANONYMIZATION: {algorithm_info.algorithm_type == AlgorithmType.IP_ANONYMIZATION}")
        
        # 检查类型索引初始化
        print(f"\n初始类型索引状态:")
        for algo_type in AlgorithmType:
            index_content = registry._type_index.get(algo_type, "NOT_FOUND")
            print(f"  {algo_type.value}: {index_content}")
        
        # 手动执行注册逻辑，每步都调试
        print(f"\n开始手动注册过程:")
        
        # Step 1: 检查是否已注册
        name = "debug_test"
        if name in registry._registrations:
            print("  算法已存在")
        else:
            print("  算法不存在，继续注册")
        
        # Step 2: 创建注册信息
        from src.pktmask.algorithms.registry.algorithm_registry import AlgorithmRegistration
        registration = AlgorithmRegistration(
            algorithm_class=OptimizedHierarchicalAnonymizationPlugin,
            algorithm_info=algorithm_info,
            metadata={}
        )
        print(f"  注册信息创建成功: {registration}")
        
        # Step 3: 添加到注册表
        registry._registrations[name] = registration
        print(f"  添加到注册表成功")
        
        # Step 4: 添加到类型索引（这里是关键）
        print(f"  准备添加到类型索引...")
        print(f"  algorithm_info.algorithm_type = {algorithm_info.algorithm_type}")
        print(f"  type(algorithm_info.algorithm_type) = {type(algorithm_info.algorithm_type)}")
        print(f"  name = {name}")
        
        # 检查_type_index中是否有对应的key
        if algorithm_info.algorithm_type in registry._type_index:
            print(f"  类型索引中已存在 {algorithm_info.algorithm_type}")
        else:
            print(f"  类型索引中不存在 {algorithm_info.algorithm_type}")
            print(f"  registry._type_index.keys() = {list(registry._type_index.keys())}")
        
        # 执行添加操作
        print(f"  执行: registry._type_index[{algorithm_info.algorithm_type}].append('{name}')")
        registry._type_index[algorithm_info.algorithm_type].append(name)
        print(f"  添加到类型索引完成")
        
        # Step 5: 检查结果
        print(f"\n注册后类型索引状态:")
        for algo_type in AlgorithmType:
            index_content = registry._type_index.get(algo_type, [])
            print(f"  {algo_type.value}: {index_content}")
        
        # 验证特定类型
        ip_type_list = registry._type_index[AlgorithmType.IP_ANONYMIZATION]
        print(f"\nIP匿名化类型列表: {ip_type_list}")
        print(f"name在列表中: {name in ip_type_list}")
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_registry() 