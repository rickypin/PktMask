"""
TCP载荷掩码器API数据类型定义

定义了基于包级指令的掩码处理所需的核心数据结构。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional, Union


# ------------------------------------------------------------------
# 掩码指令类型
# ------------------------------------------------------------------

@dataclass
class KeepAll:
    """指令：完整保留TCP载荷，不做任何修改。"""
    pass


@dataclass
class MaskAll:
    """指令：完整掩码TCP载荷，所有字节置零。"""
    pass


@dataclass
class MaskAfter:
    """指令：保留载荷的前N个字节，掩码剩余部分。"""
    keep_bytes: int


@dataclass
class MaskRange:
    """指令：仅掩码TCP载荷中[start, end)范围的字节。"""
    start: int
    end: int


# `PacketMaskInstruction` 是一个类型别名，代表所有可能的掩码指令
PacketMaskInstruction = Union[KeepAll, MaskAll, MaskAfter, MaskRange]


@dataclass
class MaskingRecipe:
    """
    完整的掩码配方 (v2)

    包含了对整个PCAP文件进行掩码处理的所有指令和元数据。
    该版本支持在单个数据包上应用多条、多种类型的指令。

    Attributes:
        packet_instructions: 掩码指令字典，键为包索引，值为指令列表
        total_packets: PCAP文件中的总包数，用于验证完整性
        skipped_packets: 处理中被跳过的数据包信息列表
        metadata: 配方元数据，包含生成信息、统计数据等
    """
    total_packets: int
    packet_instructions: Dict[int, List[PacketMaskInstruction]] = field(default_factory=dict)
    skipped_packets: List['SkippedPacketInfo'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """验证配方的有效性"""
        if self.total_packets < 0:
            raise ValueError(f"total_packets必须为非负数，得到: {self.total_packets}")

        if not isinstance(self.packet_instructions, dict):
            raise ValueError("instructions必须为字典类型")

        for index in self.packet_instructions.keys():
            if index >= self.total_packets:
                raise ValueError(
                    f"指令包索引{index}超出总包数{self.total_packets}"
                )

    def get_instruction_count(self) -> int:
        """获取指令总数量（所有包的指令之和）"""
        return sum(len(instr) for instr in self.packet_instructions.values())

    def get_instructions_for_packet(self, index: int) -> Optional[List[PacketMaskInstruction]]:
        """获取指定包的掩码指令列表"""
        return self.packet_instructions.get(index)

    def has_instruction_for_packet(self, index: int) -> bool:
        """检查是否有指定包的掩码指令"""
        return index in self.packet_instructions


@dataclass
class SkippedPacketInfo:
    """记录被跳过数据包的信息，用于生成差异报告"""
    packet_index: int
    reason: str
    packet_summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        return {
            "packet_index": self.packet_index,
            "reason": self.reason,
            "packet_summary": self.packet_summary,
        }


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