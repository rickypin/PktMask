"""
算法接口定义
定义所有算法类型的标准接口
"""

from .algorithm_interface import AlgorithmInterface, AlgorithmInfo, AlgorithmConfig, ValidationResult, ProcessingResult
from .performance_interface import PerformanceMetrics, AlgorithmPerformanceTracker
from .ip_anonymization_interface import IPAnonymizationInterface
from .packet_processing_interface import PacketProcessingInterface  
from .deduplication_interface import DeduplicationInterface

__all__ = [
    'AlgorithmInterface',
    'AlgorithmInfo',
    'AlgorithmConfig', 
    'ValidationResult',
    'ProcessingResult',
    'PerformanceMetrics',
    'AlgorithmPerformanceTracker',
    'IPAnonymizationInterface',
    'PacketProcessingInterface',
    'DeduplicationInterface'
] 