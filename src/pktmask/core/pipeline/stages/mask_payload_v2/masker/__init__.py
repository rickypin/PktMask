"""
Masker模块 - 通用载荷掩码处理器

本模块负责接收 KeepRuleSet 和原始 pcap 文件，应用保留规则进行精确掩码，
处理序列号匹配和回绕，生成掩码后的 pcap 文件。

核心组件：
- PayloadMasker: 载荷掩码处理器主类
- ErrorRecoveryHandler: 错误恢复处理器
- PerformanceMonitor: 性能监控器
- MaskingStats: 掩码统计信息

技术特点：
- 基于 scapy 的通用载荷处理
- 支持 TCP 序列号回绕处理
- 基于 TCP_MARKER_REFERENCE 算法
- 协议无关的掩码应用
"""

from .data_validator import DataValidator
from .error_handler import ErrorCategory, ErrorRecoveryHandler, ErrorSeverity
from .fallback_handler import FallbackHandler, FallbackMode
from .payload_masker import PayloadMasker
from .stats import MaskingStats

__all__ = [
    "PayloadMasker",
    "MaskingStats",
    "ErrorRecoveryHandler",
    "ErrorSeverity",
    "ErrorCategory",
    "DataValidator",
    "FallbackHandler",
    "FallbackMode",
]
