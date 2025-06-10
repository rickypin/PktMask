"""
算法注册机制
提供算法插件的注册、发现和管理功能
"""

from .algorithm_registry import AlgorithmRegistry, get_algorithm_registry
from .plugin_loader import PluginLoader, get_plugin_loader

__all__ = [
    'AlgorithmRegistry',
    'get_algorithm_registry',
    'PluginLoader',
    'get_plugin_loader'
] 