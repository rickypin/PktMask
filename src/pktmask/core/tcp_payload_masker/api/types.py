"""
TCP载荷掩码器API数据类型定义

定义了基于包级指令的掩码处理所需的核心数据结构。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional
from ...trim.models.mask_spec import MaskSpec


@dataclass
class PacketMaskInstruction:
    """
    单个数据包的掩码指令
    
    描述了对特定数据包应用掩码的精确指令，包括包位置、载荷偏移和掩码规范。
    
    Attributes:
        packet_index: 包在PCAP中的索引（从0开始）
        packet_timestamp: 纳秒级时间戳字符串，用于精确包匹配
        payload_offset: TCP载荷在包字节流中的绝对偏移量
        mask_spec: 掩码规范，指定如何对载荷进行掩码操作
        metadata: 可选的元数据信息，用于调试和统计
    """
    packet_index: int
    packet_timestamp: str  
    payload_offset: int
    mask_spec: MaskSpec
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """验证数据的有效性"""
        if self.packet_index < 0:
            raise ValueError(f"packet_index必须为非负数，得到: {self.packet_index}")
        
        if self.payload_offset < 0:
            raise ValueError(f"payload_offset必须为非负数，得到: {self.payload_offset}")
        
        if not isinstance(self.packet_timestamp, str):
            raise ValueError(f"packet_timestamp必须为字符串，得到: {type(self.packet_timestamp)}")


@dataclass 
class MaskingRecipe:
    """
    完整的掩码配方
    
    包含了对整个PCAP文件进行掩码处理的所有指令和元数据。
    
    Attributes:
        instructions: 掩码指令字典，键为(packet_index, timestamp)元组
        total_packets: PCAP文件中的总包数，用于验证完整性
        metadata: 配方元数据，包含生成信息、统计数据等
    """
    instructions: Dict[Tuple[int, str], PacketMaskInstruction]
    total_packets: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """验证配方的有效性"""
        if self.total_packets < 0:
            raise ValueError(f"total_packets必须为非负数，得到: {self.total_packets}")
        
        if not isinstance(self.instructions, dict):
            raise ValueError("instructions必须为字典类型")
        
        # 验证所有指令的索引都在有效范围内
        for (index, timestamp), instruction in self.instructions.items():
            if index >= self.total_packets:
                raise ValueError(
                    f"指令包索引{index}超出总包数{self.total_packets}"
                )
            
            # 验证指令内部的一致性
            if instruction.packet_index != index:
                raise ValueError(
                    f"指令键索引{index}与指令内索引{instruction.packet_index}不一致"
                )
            
            if instruction.packet_timestamp != timestamp:
                raise ValueError(
                    f"指令键时间戳{timestamp}与指令内时间戳{instruction.packet_timestamp}不一致"
                )
    
    def get_instruction_count(self) -> int:
        """获取指令数量"""
        return len(self.instructions)
    
    def get_instruction_for_packet(self, index: int, timestamp: str) -> Optional[PacketMaskInstruction]:
        """获取指定包的掩码指令"""
        return self.instructions.get((index, timestamp))
    
    def has_instruction_for_packet(self, index: int, timestamp: str) -> bool:
        """检查是否有指定包的掩码指令"""
        return (index, timestamp) in self.instructions


@dataclass
class MaskingStatistics:
    """掩码处理统计信息"""
    processed_packets: int = 0
    modified_packets: int = 0
    skipped_packets: int = 0
    error_packets: int = 0
    total_bytes_processed: int = 0
    total_bytes_masked: int = 0
    processing_time_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "processed_packets": self.processed_packets,
            "modified_packets": self.modified_packets,
            "skipped_packets": self.skipped_packets,
            "error_packets": self.error_packets,
            "total_bytes_processed": self.total_bytes_processed,
            "total_bytes_masked": self.total_bytes_masked,
            "processing_time_seconds": self.processing_time_seconds,
            "modification_rate": (
                self.modified_packets / max(self.processed_packets, 1) * 100
            )
        }


@dataclass
class PacketMaskingResult:
    """
    掩码执行结果
    
    包含了掩码处理的完整结果信息，包括成功状态、统计数据和错误信息。
    
    Attributes:
        success: 处理是否成功
        processed_packets: 处理的包总数
        modified_packets: 实际修改的包数
        output_file: 输出文件路径
        errors: 错误信息列表
        statistics: 详细统计信息
        execution_time: 执行时间（秒）
    """
    success: bool
    processed_packets: int
    modified_packets: int
    output_file: str
    errors: List[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    
    def __post_init__(self):
        """验证结果数据的有效性"""
        if self.processed_packets < 0:
            raise ValueError(f"processed_packets必须为非负数，得到: {self.processed_packets}")
        
        if self.modified_packets < 0:
            raise ValueError(f"modified_packets必须为非负数，得到: {self.modified_packets}")
        
        if self.modified_packets > self.processed_packets:
            raise ValueError(
                f"modified_packets({self.modified_packets})不能大于"
                f"processed_packets({self.processed_packets})"
            )
    
    def get_modification_rate(self) -> float:
        """获取修改率（百分比）"""
        if self.processed_packets == 0:
            return 0.0
        return (self.modified_packets / self.processed_packets) * 100
    
    def is_successful(self) -> bool:
        """检查处理是否成功"""
        return self.success and len(self.errors) == 0
    
    def add_error(self, error: str):
        """添加错误信息"""
        self.errors.append(error)
        self.success = False
    
    def get_summary(self) -> str:
        """获取结果摘要"""
        if self.success:
            return (
                f"成功处理{self.processed_packets}个包，"
                f"修改{self.modified_packets}个包 "
                f"({self.get_modification_rate():.1f}%)"
            )
        else:
            return (
                f"处理失败，错误数: {len(self.errors)}，"
                f"已处理: {self.processed_packets}包"
            ) 