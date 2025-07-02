"""
TLS协议处理模型

定义了TLS协议处理所需的数据结构，支持跨TCP段TLS消息识别和分类处理。
支持TLS协议类型：20(ChangeCipherSpec), 21(Alert), 22(Handshake), 23(ApplicationData), 24(Heartbeat)
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum


class TLSProcessingStrategy(Enum):
    """TLS处理策略枚举"""
    KEEP_ALL = "keep_all"              # 20,21,22,24类型：完全保留
    MASK_PAYLOAD = "mask_payload"      # 23类型：保留头部(5字节)，掩码载荷


class MaskAction(Enum):
    """掩码操作类型"""
    KEEP_ALL = "keep_all"
    MASK_PAYLOAD = "mask_payload"


@dataclass(frozen=True)
class TLSRecordInfo:
    """TLS记录信息
    
    包含单个TLS记录的完整信息，支持跨TCP段检测和协议类型识别。
    """
    packet_number: int                     # 数据包编号
    content_type: int                      # TLS内容类型 (20/21/22/23/24)
    version: Tuple[int, int]               # TLS版本 (major, minor)
    length: int                            # TLS记录长度
    is_complete: bool                      # 是否为完整记录
    spans_packets: List[int]               # 跨包列表（包含的所有包编号）
    tcp_stream_id: str                     # TCP流标识
    record_offset: int                     # 在TCP载荷中的偏移量
    
    def __post_init__(self):
        """验证TLS记录信息的有效性"""
        if self.content_type not in [20, 21, 22, 23, 24]:
            raise ValueError(f"不支持的TLS内容类型: {self.content_type}")
        
        if self.length < 0:
            raise ValueError(f"TLS记录长度不能为负数: {self.length}")
        
        if self.record_offset < 0:
            raise ValueError(f"记录偏移量不能为负数: {self.record_offset}")
        
        if self.packet_number not in self.spans_packets:
            raise ValueError(f"包编号{self.packet_number}必须在跨包列表中")
    
    @property
    def content_type_name(self) -> str:
        """获取内容类型的名称"""
        type_names = {
            20: "ChangeCipherSpec",
            21: "Alert", 
            22: "Handshake",
            23: "ApplicationData",
            24: "Heartbeat"
        }
        return type_names.get(self.content_type, f"Unknown({self.content_type})")
    
    @property
    def processing_strategy(self) -> TLSProcessingStrategy:
        """获取该TLS记录的处理策略"""
        if self.content_type == 23:  # ApplicationData
            return TLSProcessingStrategy.MASK_PAYLOAD
        else:  # 20, 21, 22, 24
            return TLSProcessingStrategy.KEEP_ALL
    
    @property
    def is_cross_packet(self) -> bool:
        """判断是否跨越多个TCP包"""
        return len(self.spans_packets) > 1
    
    def get_version_string(self) -> str:
        """获取TLS版本字符串"""
        major, minor = self.version
        if major == 3:
            if minor == 0:
                return "SSL 3.0"
            elif minor == 1:
                return "TLS 1.0"
            elif minor == 2:
                return "TLS 1.1"
            elif minor == 3:
                return "TLS 1.2"
            elif minor == 4:
                return "TLS 1.3"
        return f"TLS {major}.{minor}"


@dataclass(frozen=True)
class MaskRule:
    """增强的掩码规则
    
    基于TLS记录级别的精确掩码规则，支持字节级边界处理。
    """
    packet_number: int                     # 目标数据包编号
    tcp_stream_id: str                     # 关联的TCP流标识
    tls_record_offset: int                 # TLS记录在TCP载荷中的偏移
    tls_record_length: int                 # TLS记录总长度
    mask_offset: int                       # 掩码起始偏移（相对于TLS记录）
    mask_length: int                       # 掩码长度
    action: MaskAction                     # 掩码操作类型
    reason: str                            # 掩码原因说明
    tls_record_type: Optional[int] = None  # TLS记录类型
    
    def __post_init__(self):
        """验证掩码规则的有效性"""
        if self.tls_record_offset < 0:
            raise ValueError(f"TLS记录偏移量不能为负数: {self.tls_record_offset}")
        
        if self.tls_record_length <= 0:
            raise ValueError(f"TLS记录长度必须为正数: {self.tls_record_length}")
        
        if self.mask_offset < 0:
            raise ValueError(f"掩码偏移量不能为负数: {self.mask_offset}")
        
        if self.mask_length < 0:
            raise ValueError(f"掩码长度不能为负数: {self.mask_length}")
        
        if self.mask_offset + self.mask_length > self.tls_record_length:
            raise ValueError(f"掩码范围超出TLS记录边界: {self.mask_offset + self.mask_length} > {self.tls_record_length}")
        
        if self.tls_record_type is not None and self.tls_record_type not in [20, 21, 22, 23, 24]:
            raise ValueError(f"不支持的TLS记录类型: {self.tls_record_type}")
    
    @property
    def absolute_mask_start(self) -> int:
        """获取掩码在TCP载荷中的绝对起始位置"""
        return self.tls_record_offset + self.mask_offset
    
    @property
    def absolute_mask_end(self) -> int:
        """获取掩码在TCP载荷中的绝对结束位置"""
        return self.absolute_mask_start + self.mask_length
    
    @property
    def is_mask_operation(self) -> bool:
        """判断是否为实际的掩码操作"""
        return self.action == MaskAction.MASK_PAYLOAD and self.mask_length > 0
    
    def get_description(self) -> str:
        """获取规则描述"""
        if self.action == MaskAction.KEEP_ALL:
            return f"TLS-{self.tls_record_type} 完全保留: {self.reason}"
        else:
            return f"TLS-{self.tls_record_type} 掩码[{self.mask_offset}:{self.mask_offset + self.mask_length}]: {self.reason}"


@dataclass
class TLSAnalysisResult:
    """TLS分析结果
    
    包含对单个PCAP文件的TLS分析结果。
    """
    total_packets: int                     # 总包数
    tls_packets: int                       # TLS包数
    tls_records: List[TLSRecordInfo]       # 识别的TLS记录
    cross_packet_records: List[TLSRecordInfo]  # 跨包TLS记录
    analysis_errors: List[str]             # 分析错误列表
    
    @property
    def tls_record_types(self) -> dict:
        """获取TLS记录类型统计"""
        type_counts = {}
        for record in self.tls_records:
            type_name = record.content_type_name
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        return type_counts
    
    @property
    def cross_packet_ratio(self) -> float:
        """获取跨包记录比例"""
        if not self.tls_records:
            return 0.0
        return len(self.cross_packet_records) / len(self.tls_records)
    
    def get_summary(self) -> str:
        """获取分析结果摘要"""
        summary = f"TLS分析结果: 总包数={self.total_packets}, TLS包数={self.tls_packets}, TLS记录数={len(self.tls_records)}"
        if self.cross_packet_records:
            summary += f", 跨包记录数={len(self.cross_packet_records)}"
        return summary


def create_mask_rule_for_tls_record(record: TLSRecordInfo) -> MaskRule:
    """为TLS记录创建掩码规则
    
    Args:
        record: TLS记录信息
        
    Returns:
        对应的掩码规则
    """
    if record.processing_strategy == TLSProcessingStrategy.KEEP_ALL:
        # 完全保留：20, 21, 22, 24类型
        return MaskRule(
            packet_number=record.packet_number,
            tcp_stream_id=record.tcp_stream_id,
            tls_record_offset=record.record_offset,
            tls_record_length=record.length,
            mask_offset=0,
            mask_length=0,
            action=MaskAction.KEEP_ALL,
            reason=f"TLS-{record.content_type} 协议完全保留策略",
            tls_record_type=record.content_type
        )
    
    elif record.processing_strategy == TLSProcessingStrategy.MASK_PAYLOAD:
        # 智能掩码：23(ApplicationData)类型
        if record.is_complete and record.length > 5:
            # 完整记录且长度超过头部：保留5字节头部，掩码载荷
            return MaskRule(
                packet_number=record.packet_number,
                tcp_stream_id=record.tcp_stream_id,
                tls_record_offset=record.record_offset,
                tls_record_length=record.length,
                mask_offset=5,  # 保留5字节TLS头部
                mask_length=record.length - 5,
                action=MaskAction.MASK_PAYLOAD,
                reason="TLS-23 智能掩码：保留头部，掩码载荷",
                tls_record_type=record.content_type
            )
        else:
            # 不完整记录或纯头部记录：完全保留
            return MaskRule(
                packet_number=record.packet_number,
                tcp_stream_id=record.tcp_stream_id,
                tls_record_offset=record.record_offset,
                tls_record_length=record.length,
                mask_offset=0,
                mask_length=0,
                action=MaskAction.KEEP_ALL,
                reason="TLS-23 不完整记录或纯头部：完全保留",
                tls_record_type=record.content_type
            )
    
    else:
        raise ValueError(f"未知的TLS处理策略: {record.processing_strategy}")


def validate_tls_record_boundary(record: TLSRecordInfo, tcp_payload_length: int) -> bool:
    """验证TLS记录边界的安全性
    
    Args:
        record: TLS记录信息
        tcp_payload_length: TCP载荷总长度
        
    Returns:
        是否在安全边界内
    """
    record_end = record.record_offset + record.length
    return record_end <= tcp_payload_length


def get_tls_processing_strategy(content_type: int) -> TLSProcessingStrategy:
    """根据TLS内容类型获取处理策略
    
    Args:
        content_type: TLS内容类型
        
    Returns:
        对应的处理策略
    """
    if content_type == 23:  # ApplicationData
        return TLSProcessingStrategy.MASK_PAYLOAD
    elif content_type in [20, 21, 22, 24]:  # ChangeCipherSpec, Alert, Handshake, Heartbeat
        return TLSProcessingStrategy.KEEP_ALL
    else:
        raise ValueError(f"不支持的TLS内容类型: {content_type}") 