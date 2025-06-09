#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
优化版算法插件注册器
自动注册所有优化版算法插件到注册中心
"""

from typing import List, Tuple, Type
from ..interfaces.algorithm_interface import AlgorithmInterface
from ..registry.algorithm_registry import get_algorithm_registry
from ...infrastructure.logging import get_logger

# 导入优化版插件
from .ip_anonymization.optimized_hierarchical_plugin import OptimizedHierarchicalAnonymizationPlugin
from .deduplication.optimized_deduplication_plugin import OptimizedDeduplicationPlugin  
from .packet_processing.optimized_trimming_plugin import OptimizedTrimmingPlugin


def get_optimized_plugins() -> List[Tuple[str, Type[AlgorithmInterface]]]:
    """
    获取所有优化版插件列表
    
    Returns:
        List[Tuple[str, Type[AlgorithmInterface]]]: (插件名称, 插件类) 的列表
    """
    return [
        ("optimized_hierarchical_anonymization", OptimizedHierarchicalAnonymizationPlugin),
        ("optimized_deduplication", OptimizedDeduplicationPlugin),
        ("optimized_trimming", OptimizedTrimmingPlugin),
    ]


def register_optimized_plugins() -> bool:
    """
    注册所有优化版算法插件
    
    Returns:
        bool: 是否全部注册成功
    """
    logger = get_logger('algorithm.registry.optimized')
    registry = get_algorithm_registry()
    
    plugins = get_optimized_plugins()
    success_count = 0
    total_count = len(plugins)
    
    logger.info(f"开始注册 {total_count} 个优化版算法插件")
    
    for plugin_name, plugin_class in plugins:
        try:
            if registry.register_algorithm(plugin_class, plugin_name):
                logger.info(f"✓ 成功注册插件: {plugin_name}")
                success_count += 1
            else:
                logger.warning(f"✗ 插件注册失败: {plugin_name}")
        except Exception as e:
            logger.error(f"✗ 插件注册异常 {plugin_name}: {e}")
    
    if success_count == total_count:
        logger.info(f"🎉 所有 {total_count} 个优化版插件注册成功！")
        return True
    else:
        logger.warning(f"⚠️ 注册完成: {success_count}/{total_count} 个插件成功")
        return False


def unregister_optimized_plugins() -> bool:
    """
    注销所有优化版算法插件
    
    Returns:
        bool: 是否全部注销成功
    """
    logger = get_logger('algorithm.registry.optimized')
    registry = get_algorithm_registry()
    
    plugins = get_optimized_plugins()
    success_count = 0
    total_count = len(plugins)
    
    logger.info(f"开始注销 {total_count} 个优化版算法插件")
    
    for plugin_name, _ in plugins:
        try:
            if registry.unregister_algorithm(plugin_name):
                logger.info(f"✓ 成功注销插件: {plugin_name}")
                success_count += 1
            else:
                logger.warning(f"✗ 插件注销失败: {plugin_name}")
        except Exception as e:
            logger.error(f"✗ 插件注销异常 {plugin_name}: {e}")
    
    if success_count == total_count:
        logger.info(f"🧹 所有 {total_count} 个优化版插件注销成功！")
        return True
    else:
        logger.warning(f"⚠️ 注销完成: {success_count}/{total_count} 个插件成功")
        return False


def list_optimized_plugins() -> List[str]:
    """
    列出所有优化版插件名称
    
    Returns:
        List[str]: 插件名称列表
    """
    plugins = get_optimized_plugins()
    return [plugin_name for plugin_name, _ in plugins]


def is_optimized_plugin_registered(plugin_name: str) -> bool:
    """
    检查指定的优化版插件是否已注册
    
    Args:
        plugin_name: 插件名称
        
    Returns:
        bool: 是否已注册
    """
    registry = get_algorithm_registry()
    return registry.is_registered(plugin_name)


def get_optimized_plugins_status() -> dict:
    """
    获取所有优化版插件的注册状态
    
    Returns:
        dict: 插件状态信息
    """
    registry = get_algorithm_registry()
    plugins = get_optimized_plugins()
    
    status = {
        "total_plugins": len(plugins),
        "registered_plugins": 0,
        "plugin_status": {}
    }
    
    for plugin_name, plugin_class in plugins:
        is_registered = registry.is_registered(plugin_name)
        if is_registered:
            status["registered_plugins"] += 1
        
        status["plugin_status"][plugin_name] = {
            "registered": is_registered,
            "class": plugin_class.__name__,
            "module": plugin_class.__module__
        }
    
    return status


if __name__ == "__main__":
    # 运行插件注册
    success = register_optimized_plugins()
    
    if success:
        print("🎉 所有优化版算法插件注册成功！")
        
        # 显示状态
        status = get_optimized_plugins_status()
        print(f"\n📊 插件状态:")
        print(f"总插件数: {status['total_plugins']}")
        print(f"已注册: {status['registered_plugins']}")
        
        for name, info in status["plugin_status"].items():
            status_icon = "✓" if info["registered"] else "✗"
            print(f"  {status_icon} {name}: {info['class']}")
    else:
        print("❌ 部分插件注册失败，请检查日志")
        exit(1) 