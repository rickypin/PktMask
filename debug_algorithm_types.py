#!/usr/bin/env python3

import sys
sys.path.insert(0, 'src')

from pktmask.algorithms.implementations.register_optimized_plugins import register_optimized_plugins
from pktmask.algorithms.registry.algorithm_registry import get_algorithm_registry
from pktmask.algorithms.interfaces.algorithm_interface import AlgorithmType

def main():
    print("=== 注册优化版插件 ===")
    register_optimized_plugins()
    
    print("\n=== 获取注册中心 ===")
    registry = get_algorithm_registry()
    
    print("\n=== 所有注册的算法 ===")
    registered_names = registry.list_registered_algorithms()
    print(f"总数: {len(registered_names)}")
    
    for name in registered_names:
        algorithm = registry.get_algorithm(name)
        if algorithm:
            info = algorithm.get_algorithm_info()
            print(f"- {name}: {info.name} ({info.algorithm_type.value})")
        else:
            print(f"- {name}: 获取失败")
    
    print("\n=== 检查_type_index内容 ===")
    for algo_type in AlgorithmType:
        print(f"{algo_type.value}: {registry._type_index.get(algo_type, [])}")
    
    print("\n=== 按类型分组 ===")
    for algo_type in AlgorithmType:
        algorithms = registry.get_algorithms_by_type(algo_type)
        print(f"{algo_type.value}: {len(algorithms)} 个")
        for algorithm in algorithms:
            info = algorithm.get_algorithm_info()
            print(f"  - {info.name}")
    
    print("\n=== 检查特定算法 ===")
    ip_algo = registry.get_algorithm('optimized_hierarchical_anonymization')
    if ip_algo:
        info = ip_algo.get_algorithm_info()
        print(f"IP算法: {info.name}, 类型: {info.algorithm_type}, 值: {info.algorithm_type.value}")
        
        # 直接检查_type_index
        ip_type = AlgorithmType.IP_ANONYMIZATION
        names_in_index = registry._type_index.get(ip_type, [])
        print(f"IP_ANONYMIZATION索引中的名称: {names_in_index}")
        
        # 检查名称是否匹配
        if 'optimized_hierarchical_anonymization' in names_in_index:
            print("✅ 算法名称在索引中")
        else:
            print("❌ 算法名称不在索引中")

if __name__ == "__main__":
    main() 