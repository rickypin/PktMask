"""
协议掩码策略工厂 - Phase 4实现

专门为基于TCP序列号的掩码机制设计的策略工厂。
"""

from typing import Dict, List, Type, Optional, Set, Any, Tuple
import logging
from collections import defaultdict
from dataclasses import dataclass

from .protocol_mask_strategy import (
    ProtocolMaskStrategy, PacketAnalysis, ProtocolDetectionResult, 
    MaskGenerationContext, GenericProtocolMaskStrategy
)
from ..models.sequence_mask_table import MaskEntry
from ..models.tcp_stream import ConnectionDirection


class ProtocolMaskFactory:
    """协议掩码策略工厂 - Phase 4"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

