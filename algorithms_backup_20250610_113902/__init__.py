"""
算法插件系统
提供统一的算法接口和插件化支持
"""

from .interfaces.algorithm_interface import AlgorithmInterface
from .interfaces.performance_interface import PerformanceMetrics, AlgorithmPerformanceTracker
from .registry.algorithm_registry import AlgorithmRegistry, get_algorithm_registry

__all__ = [
    'AlgorithmInterface',
    'PerformanceMetrics', 
    'AlgorithmPerformanceTracker',
    'AlgorithmRegistry',
    'get_algorithm_registry'
]

__version__ = '1.0.0' 