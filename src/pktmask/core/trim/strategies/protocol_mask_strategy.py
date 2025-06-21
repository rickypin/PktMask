"""
协议掩码策略抽象基类 - Phase 4实现

这个模块定义了基于TCP序列号的协议掩码策略标准接口。
与现有的BaseStrategy相比，ProtocolMaskStrategy专门针对Phase 1-3建立的
序列号掩码机制设计，支持生成MaskEntry条目而不是直接裁切载荷。

Phase 4重构要点：
1. 专门为序列号掩码机制设计的策略接口
2. 支持生成MaskEntry而不是直接修改载荷
3. 协议检测和掩码条目生成分离
4. 支持多协议混合场景

作者: PktMask Team
创建时间: 2025年6月21日
版本: Phase 4.0.0
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
import logging

# Phase 4: 导入Phase 1-3的核心组件
from ..models.sequence_mask_table import MaskEntry
from ..models.mask_spec import MaskSpec, MaskAfter, MaskRange, KeepAll
from ..models.tcp_stream import ConnectionDirection


@dataclass
class PacketAnalysis:
    """数据包分析结果 - Phase 4增强版"""
    packet_number: int                    # 数据包编号
    timestamp: float                      # 时间戳
    stream_id: str                       # TCP流ID (含方向)
    seq_number: int                      # TCP序列号
    payload_length: int                  # 载荷长度
    
    # 协议层信息
    application_layer: Optional[str]     # 应用层协议 (HTTP, TLS, etc.)
    transport_layer: str = "TCP"         # 传输层协议
    
    # Phase 4: 协议特定属性
    protocol_attributes: Dict[str, Any] = None  # 协议特定属性
    
    def __post_init__(self):
        if self.protocol_attributes is None:
            self.protocol_attributes = {}


@dataclass 
class ProtocolDetectionResult:
    """协议检测结果"""
    is_protocol_match: bool              # 是否匹配协议
    protocol_name: str                   # 协议名称
    confidence: float                    # 检测置信度 (0.0-1.0)
    protocol_version: Optional[str]      # 协议版本
    attributes: Dict[str, Any]           # 协议特定属性
    
    
@dataclass
class MaskGenerationContext:
    """掩码生成上下文"""
    stream_id: str                       # TCP流ID
    direction: ConnectionDirection       # 流方向
    packets: List[PacketAnalysis]        # 相关数据包列表
    flow_metadata: Dict[str, Any]        # 流元数据
    

class ProtocolMaskStrategy(ABC):
    """
    协议掩码策略抽象基类 - Phase 4
    
    专门为基于TCP序列号的掩码机制设计的策略接口。
    与传统的载荷裁切不同，这个策略专注于生成MaskEntry条目，
    由Scapy回写器根据序列号进行精确匹配和置零。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化协议掩码策略
        
        Args:
            config: 策略配置参数
        """
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._validate_config()
    
    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """
        返回策略名称
        
        Returns:
            策略的唯一标识名称
        """
        pass
    
    @property
    @abstractmethod
    def supported_protocols(self) -> Set[str]:
        """
        返回此策略支持的协议集合
        
        Returns:
            支持的协议名称集合，如 {'HTTP', 'HTTPS'}
        """
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """
        返回策略优先级
        
        当多个策略都支持同一协议时，优先级高的策略被选中。
        
        Returns:
            策略优先级 (0-100，数值越高优先级越高)
        """
        pass
        
    @abstractmethod
    def detect_protocol(self, packet: PacketAnalysis) -> ProtocolDetectionResult:
        """
        检测数据包是否为该协议
        
        Args:
            packet: 数据包分析结果
            
        Returns:
            协议检测结果
        """
        pass
    
    @abstractmethod
    def generate_mask_entries(self, context: MaskGenerationContext) -> List[MaskEntry]:
        """
        生成掩码条目
        
        这是策略的核心方法，根据协议特性为TCP流生成掩码条目。
        生成的MaskEntry将被添加到SequenceMaskTable中，供Scapy回写器使用。
        
        Args:
            context: 掩码生成上下文
            
        Returns:
            掩码条目列表
        """
        pass
    
    def analyze_stream(self, packets: List[PacketAnalysis]) -> Dict[str, Any]:
        """
        分析TCP流中的协议特征
        
        这个方法提供了流级别的分析能力，子类可以重写来实现
        更复杂的多包协议分析。
        
        Args:
            packets: TCP流中的数据包列表
            
        Returns:
            流分析结果字典
        """
        return {
            'packet_count': len(packets),
            'total_bytes': sum(p.payload_length for p in packets),
            'protocol_packets': [p for p in packets if self.detect_protocol(p).is_protocol_match]
        }
    
    def can_handle_mixed_protocols(self) -> bool:
        """
        返回是否支持混合协议场景
        
        Returns:
            True 如果策略可以处理混合协议，False 否则
        """
        return False
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config.get(key, default)
        
    def _validate_config(self) -> None:
        """
        验证配置参数
        
        子类可以重写此方法来验证特定的配置要求。
        
        Raises:
            ValueError: 配置无效时
        """
        pass
    
    def _create_mask_entry(self, stream_id: str, seq_start: int, seq_end: int, 
                          mask_type: str, mask_spec: MaskSpec,
                          preserve_headers: Optional[List[Tuple[int, int]]] = None) -> MaskEntry:
        """
        创建掩码条目的辅助方法
        
        Args:
            stream_id: TCP流ID
            seq_start: 起始序列号
            seq_end: 结束序列号
            mask_type: 掩码类型
            mask_spec: 掩码规范
            preserve_headers: 需要保留的头部范围
            
        Returns:
            掩码条目
        """
        return MaskEntry(
            tcp_stream_id=stream_id,
            seq_start=seq_start,
            seq_end=seq_end,
            mask_type=mask_type,
            mask_spec=mask_spec,
            preserve_headers=preserve_headers or []
        )


class GenericProtocolMaskStrategy(ProtocolMaskStrategy):
    """
    通用协议掩码策略
    
    为不支持特定协议策略的情况提供回退方案。
    通常会保留载荷或应用非常保守的掩码策略。
    """
    
    @property
    def strategy_name(self) -> str:
        return "generic"
    
    @property
    def supported_protocols(self) -> Set[str]:
        return {"*"}  # 支持所有协议
    
    @property
    def priority(self) -> int:
        return 0  # 最低优先级，作为回退策略
    
    def detect_protocol(self, packet: PacketAnalysis) -> ProtocolDetectionResult:
        """
        通用协议检测，总是返回匹配
        """
        return ProtocolDetectionResult(
            is_protocol_match=True,
            protocol_name="generic",
            confidence=0.5,  # 中等置信度
            protocol_version=None,
            attributes={}
        )
    
    def generate_mask_entries(self, context: MaskGenerationContext) -> List[MaskEntry]:
        """
        生成保守的掩码条目
        
        通用策略默认保留所有载荷，确保数据的完整性。
        """
        entries = []
        
        for packet in context.packets:
            if packet.payload_length > 0:
                # 使用KeepAll策略保留所有载荷
                entry = self._create_mask_entry(
                    stream_id=packet.stream_id,
                    seq_start=packet.seq_number,
                    seq_end=packet.seq_number + packet.payload_length - 1,
                    mask_type="generic_keepall",
                    mask_spec=KeepAll()
                )
                entries.append(entry)
        
        return entries
    
    def can_handle_mixed_protocols(self) -> bool:
        return True  # 通用策略支持混合协议 