"""
TCP载荷掩码处理器核心模块

包含所有核心功能的实现：
- keep_range_models: TCP保留范围数据结构
- tcp_masker: 主要API实现  
- config: 配置管理
- protocol_control: 协议解析控制 (Phase 2)
- file_handler: 文件I/O处理器 (Phase 3)
- consistency: 一致性验证器 (Phase 3)
- payload_extractor: 载荷提取器 (Phase 4)
- keep_range_applier: 保留范围掩码应用器 (Phase 4)
"""

# 主要API类
from .tcp_masker import TcpPayloadMasker

# 数据模型
from .keep_range_models import (
    TcpKeepRangeEntry,
    TcpMaskingResult, 
    TcpKeepRangeTable
)

# 配置管理
from .config import (
    ConfigManager,
    create_config_manager
)

# 协议控制 (Phase 2)
from .protocol_control import ProtocolBindingController

# 文件I/O处理 (Phase 3)
from .file_handler import PcapFileHandler

# 一致性验证 (Phase 3)
from .consistency import ConsistencyVerifier

# 核心掩码处理 (Phase 4)
from .payload_extractor import PayloadExtractor, create_payload_extractor
from .keep_range_applier import MaskApplier, create_mask_applier

# 新架构核心组件 (Phase 1.2) - BlindPacketMasker 已移除
# from .blind_masker import BlindPacketMasker  # 已废弃

__all__ = [
    # 主要API
    'TcpPayloadMasker',
    
    # 数据模型
    'TcpKeepRangeEntry',
    'TcpMaskingResult',
    'TcpKeepRangeTable',
    
    # 配置管理
    'ConfigManager',
    'create_config_manager',
    
    # 协议控制
    'ProtocolBindingController',
    
    # 文件I/O处理 (Phase 3)
    'PcapFileHandler',
    
    # 一致性验证 (Phase 3)
    'ConsistencyVerifier',
    
    # 核心掩码处理 (Phase 4)
    'PayloadExtractor',
    'create_payload_extractor',
    'MaskApplier',
    'create_mask_applier',
    
    # 新架构核心组件 (Phase 1.2) - 已废弃
    # 'BlindPacketMasker',  # 已移除
] 
