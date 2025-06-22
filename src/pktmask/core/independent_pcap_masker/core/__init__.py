"""
独立PCAP掩码处理器核心模块

包含所有核心功能的实现：
- models: 数据结构定义
- masker: 主要API实现  
- config: 配置管理
- protocol_control: 协议解析控制 (Phase 2)
- file_handler: 文件I/O处理器 (Phase 3)
- consistency: 一致性验证器 (Phase 3)
- payload_extractor: 载荷提取器 (Phase 4)
- mask_applier: 掩码应用器 (Phase 4)
"""

# 主要API类
from .masker import IndependentPcapMasker

# 数据模型
from .models import (
    MaskEntry,
    MaskingResult, 
    SequenceMaskTable
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
from .mask_applier import MaskApplier, create_mask_applier

__all__ = [
    # 主要API
    'IndependentPcapMasker',
    
    # 数据模型
    'MaskEntry',
    'MaskingResult',
    'SequenceMaskTable',
    
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
    'create_mask_applier'
] 