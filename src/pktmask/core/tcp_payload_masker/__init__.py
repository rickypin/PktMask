"""
TCP载荷掩码处理器模块

这是一个专用于TCP载荷的保留范围掩码处理器。
采用隐私优先设计理念：默认掩码所有TCP载荷，只保留指定的协议头部范围。

主要特性：
- TCP专用：只处理TCP协议，不支持其他协议
- 保留范围：记录要保留的字节范围，其余全部掩码为0x00
- 隐私优先：默认掩码所有载荷，最大化隐私保护
- 协议保留：支持TLS/HTTP/SSH等协议头部自动保留
"""

from .core.tcp_masker import TcpPayloadMasker
from .core.keep_range_models import TcpKeepRangeEntry, TcpMaskingResult, TcpKeepRangeTable
from .core.keep_range_applier import TcpPayloadKeepRangeMasker, TcpProtocolHintGenerator
from .exceptions import (
    TcpPayloadMaskerError,
    ProtocolBindingError,
    FileConsistencyError,
    TcpKeepRangeApplicationError,
    ValidationError,
    ConfigurationError
)

__version__ = "2.0.0"
__author__ = "PktMask Team"

# 主要API导出
__all__ = [
    'TcpPayloadMasker',
    'TcpKeepRangeEntry', 
    'TcpMaskingResult',
    'TcpKeepRangeTable',
    'TcpPayloadKeepRangeMasker',
    'TcpProtocolHintGenerator',
    'TcpPayloadMaskerError',
    'ProtocolBindingError',
    'FileConsistencyError',
    'TcpKeepRangeApplicationError',
    'ValidationError',
    'ConfigurationError'
] 