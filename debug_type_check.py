#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
调试枚举类型比较问题
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def debug_enum_comparison():
    """调试枚举比较问题"""
    try:
        # 导入相关模块
        from src.pktmask.algorithms.interfaces.algorithm_interface import AlgorithmType
        from src.pktmask.algorithms.implementations.ip_anonymization.optimized_hierarchical_plugin import OptimizedHierarchicalAnonymizationPlugin
        
        print("🔍 调试枚举类型比较问题")
        print("=" * 50)
        
        # 创建算法实例
        algorithm = OptimizedHierarchicalAnonymizationPlugin()
        algorithm_info = algorithm.get_algorithm_info()
        
        print(f"算法类型信息:")
        print(f"  algorithm_info.algorithm_type = {algorithm_info.algorithm_type}")
        print(f"  type(algorithm_info.algorithm_type) = {type(algorithm_info.algorithm_type)}")
        print(f"  str(algorithm_info.algorithm_type) = {str(algorithm_info.algorithm_type)}")
        print(f"  repr(algorithm_info.algorithm_type) = {repr(algorithm_info.algorithm_type)}")
        print(f"  algorithm_info.algorithm_type.value = {algorithm_info.algorithm_type.value}")
        
        print(f"\nAlgorithmType.IP_ANONYMIZATION 信息:")
        print(f"  AlgorithmType.IP_ANONYMIZATION = {AlgorithmType.IP_ANONYMIZATION}")
        print(f"  type(AlgorithmType.IP_ANONYMIZATION) = {type(AlgorithmType.IP_ANONYMIZATION)}")
        print(f"  str(AlgorithmType.IP_ANONYMIZATION) = {str(AlgorithmType.IP_ANONYMIZATION)}")
        print(f"  repr(AlgorithmType.IP_ANONYMIZATION) = {repr(AlgorithmType.IP_ANONYMIZATION)}")
        print(f"  AlgorithmType.IP_ANONYMIZATION.value = {AlgorithmType.IP_ANONYMIZATION.value}")
        
        print(f"\n比较结果:")
        print(f"  algorithm_info.algorithm_type == AlgorithmType.IP_ANONYMIZATION: {algorithm_info.algorithm_type == AlgorithmType.IP_ANONYMIZATION}")
        print(f"  algorithm_info.algorithm_type is AlgorithmType.IP_ANONYMIZATION: {algorithm_info.algorithm_type is AlgorithmType.IP_ANONYMIZATION}")
        print(f"  id(algorithm_info.algorithm_type) = {id(algorithm_info.algorithm_type)}")
        print(f"  id(AlgorithmType.IP_ANONYMIZATION) = {id(AlgorithmType.IP_ANONYMIZATION)}")
        
        # 检查枚举模块位置
        import src.pktmask.algorithms.interfaces.algorithm_interface as ai_module
        print(f"\n模块信息:")
        print(f"  algorithm_interface模块: {ai_module}")
        print(f"  AlgorithmType模块: {AlgorithmType.__module__}")
        print(f"  algorithm_info.algorithm_type模块: {algorithm_info.algorithm_type.__class__.__module__}")
        
        # 检查hash值
        print(f"\nhash值:")
        print(f"  hash(algorithm_info.algorithm_type) = {hash(algorithm_info.algorithm_type)}")
        print(f"  hash(AlgorithmType.IP_ANONYMIZATION) = {hash(AlgorithmType.IP_ANONYMIZATION)}")
        
        # 测试字典key比较
        test_dict = {AlgorithmType.IP_ANONYMIZATION: "test"}
        print(f"\n字典测试:")
        print(f"  test_dict = {test_dict}")
        print(f"  algorithm_info.algorithm_type in test_dict: {algorithm_info.algorithm_type in test_dict}")
        
        # 测试defaultdict
        from collections import defaultdict
        test_defaultdict = defaultdict(list)
        test_defaultdict[AlgorithmType.IP_ANONYMIZATION].append("original")
        print(f"\n  test_defaultdict初始状态: {dict(test_defaultdict)}")
        
        test_defaultdict[algorithm_info.algorithm_type].append("from_algorithm")
        print(f"  添加algorithm_info.algorithm_type后: {dict(test_defaultdict)}")
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_enum_comparison() 