"""
TCP载荷掩码器模块

基于保留范围的TCP载荷掩码处理系统，提供专业的TCP载荷掩码接口。

核心功能:
- TCP载荷保留范围掩码处理
- 字节级精确掩码操作
- 协议绑定控制和验证
- 文件一致性检查

主要组件:
- TcpPayloadMasker: 主要API类
- TcpKeepRangeTable: 保留范围管理
- ConsistencyVerifier: 文件一致性验证
"""

# Phase 1.1: 核心数据结构 (已完成)
from .api.types import (
    PacketMaskInstruction,
    MaskingRecipe,
    PacketMaskingResult,
    MaskingStatistics
)

# 一致性验证函数
from .consistency import verify_file_consistency

# 向后兼容的旧API (保留以避免破坏现有代码，Phase 2中适配)
from .tcp_masker import TcpMaskPayloadApplier as TcpPayloadMasker
from .keep_range_models import TcpKeepRangeEntry, TcpMaskingResult, TcpKeepRangeTable
from .keep_range_applier import TcpMaskRangeApplier, create_mask_applier
from .exceptions import (
    TcpPayloadMaskerError,
    ProtocolBindingError,
    FileConsistencyError,
    TcpKeepRangeApplicationError,
    ValidationError,
    ConfigurationError
)

# 验证功能
from .api.validator import (
    validate_packet_instruction,
    check_file_accessibility,
    estimate_memory_usage
)

# 核心引擎
from .consistency import ConsistencyVerifier

# 统计工具
from .utils.stats import MaskingStatistics

__version__ = "2.0.0"
__author__ = "PktMask Team"

# 完整导出
__all__ = [
    # 核心数据结构
    "PacketMaskInstruction",
    "MaskingRecipe",
    "PacketMaskingResult",
    "MaskingStatistics",

    # API函数
    "verify_file_consistency",

    # TCP载荷掩码API
    'TcpPayloadMasker',
    'TcpKeepRangeEntry',
    'TcpMaskingResult',
    'TcpKeepRangeTable',
    'TcpMaskRangeApplier',
    'create_mask_applier',
    'TcpPayloadMaskerError',
    'ProtocolBindingError',
    'FileConsistencyError',
    'TcpKeepRangeApplicationError',
    'ValidationError',
    'ConfigurationError',

    # 验证功能
    "validate_packet_instruction",
    "check_file_accessibility",
    "estimate_memory_usage",

    # 核心引擎
    "ConsistencyVerifier"
]
