"""
Scapy独立掩码处理器模块

这是一个完全独立的PCAP掩码处理器，可以脱离PktMask主程序运行。
提供基于TCP序列号的字节级掩码处理功能。

主要特性：
- 零架构依赖：不依赖BaseStage、StageContext等
- API驱动：提供标准化的函数调用接口  
- 功能单一：纯粹的序列号匹配和字节级掩码
- 完全测试：可独立进行单元测试和集成测试
"""

from .core.masker import IndependentPcapMasker
from .core.models import MaskEntry, MaskingResult, SequenceMaskTable
from .exceptions import (
    IndependentMaskerError,
    ProtocolBindingError,
    FileConsistencyError,
    MaskApplicationError,
    ValidationError,
    ConfigurationError
)

__version__ = "1.0.0"
__author__ = "PktMask Team"

# 主要API导出
__all__ = [
    'IndependentPcapMasker',
    'MaskEntry', 
    'MaskingResult',
    'SequenceMaskTable',
    'IndependentMaskerError',
    'ProtocolBindingError',
    'FileConsistencyError',
    'MaskApplicationError',
    'ValidationError',
    'ConfigurationError'
] 