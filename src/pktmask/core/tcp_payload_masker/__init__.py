"""
TCP载荷掩码器模块 - Phase 1 API重设计

基于包级指令的TCP载荷掩码处理系统，提供独立的掩码执行接口。

Phase 1 设计目标:
- 完全独立的、基于包级指令的掩码执行引擎
- 职责单一：纯粹的字节级掩码操作
- 协议无关：完全不解析协议，只进行字节操作
- API优先：提供标准化的函数调用接口

Phase 1 实施进度:
- Phase 1.1: ✅ 核心数据结构设计 (PacketMaskInstruction, MaskingRecipe, PacketMaskingResult)
- Phase 1.2: ✅ 盲操作引擎实现 (BlindPacketMasker)
- Phase 1.3: ✅ API封装和文件处理 (mask_pcap_with_instructions)
- Phase 1.4: ⏳ 真实样本验证

使用示例 (Phase 1.3完成后):
    from pktmask.core.tcp_payload_masker import mask_pcap_with_instructions
    
    result = mask_pcap_with_instructions(
        input_file="input.pcap",
        output_file="output.pcap",
        masking_recipe=recipe
    )
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
from .tcp_masker import TcpPayloadMasker
from .keep_range_models import TcpKeepRangeEntry, TcpMaskingResult, TcpKeepRangeTable
from .keep_range_applier import MaskApplier, create_mask_applier
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

# 核心引擎 - BlindPacketMasker 已移除
# from .core.blind_masker import BlindPacketMasker  # 已废弃
from .consistency import ConsistencyVerifier

# 统计工具
from .utils.stats import MaskingStatistics

__version__ = "2.0.0-phase1.3"
__author__ = "PktMask Team"

# Phase 1.3 完整导出
__all__ = [
    # 新Phase 1 API - 核心数据结构
    "PacketMaskInstruction",
    "MaskingRecipe", 
    "PacketMaskingResult",
    "MaskingStatistics",
    
    # Phase 1.3: API函数 (已完成)
    "verify_file_consistency",
    
    # 向后兼容的旧API
    'TcpPayloadMasker',
    'TcpKeepRangeEntry', 
    'TcpMaskingResult',
    'TcpKeepRangeTable',
    'MaskApplier',
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
    # "BlindPacketMasker",  # 已移除
    "ConsistencyVerifier"
] 
