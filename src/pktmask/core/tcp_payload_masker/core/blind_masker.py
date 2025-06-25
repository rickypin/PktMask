"""
盲操作数据包掩码器

实现基于包级指令的纯字节操作掩码引擎，完全不依赖协议解析。
"""

import time
import logging
from typing import Optional, Tuple, List
from scapy.all import raw, Ether, IP, TCP, Raw, rdpcap, wrpcap
from scapy.packet import Packet

from ..api.types import (
    MaskingRecipe, 
    PacketMaskInstruction, 
    MaskingStatistics,
    PacketMaskingResult,
    MaskRange,
    MaskAfter,
    KeepAll,
    MaskAll,
)
from ...trim.models.mask_spec import MaskSpec


logger = logging.getLogger(__name__)


class BlindPacketMasker:
    """
    盲操作数据包掩码器 (v2)

    这是一个纯字节操作的掩码引擎，它：
    1. 完全不解析协议结构
    2. 基于相对于TCP载荷的偏移进行操作
    3. 支持单个包应用多条指令
    """
    
    def __init__(self, masking_recipe: MaskingRecipe):
        """
        初始化盲操作掩码器
        
        Args:
            masking_recipe: 包含所有掩码指令的配方
        """
        self.recipe = masking_recipe
        self.stats = MaskingStatistics()
        self.logger = logger.getChild("BlindPacketMasker")
        
        self.logger.info(
            f"初始化BlindPacketMasker，配方包含{self.recipe.get_instruction_count()}条指令，"
            f"总包数{self.recipe.total_packets}"
        )
    
    def mask_packets(self, packets: List[Packet]) -> List[Packet]:
        """对整个PCAP文件的数据包列表进行掩码处理"""
        start_time = time.time()
        modified_packets = []

        for i, pkt in enumerate(packets):
            try:
                modified_pkt = self._process_packet(i, pkt)
                modified_packets.append(modified_pkt)
            except Exception as e:
                self.stats.error_packets += 1
                self.logger.error(f"处理包{i}时发生严重错误: {e}", exc_info=True)
                modified_packets.append(pkt)  # 保留原始包

        self.stats.processing_time_seconds = time.time() - start_time
        return modified_packets

    def _process_packet(self, packet_index: int, packet: Packet) -> Packet:
        """处理单个数据包"""
        self.stats.processed_packets += 1

        instructions = self.recipe.get_instructions_for_packet(packet_index)

        if not instructions:
            self.stats.skipped_packets += 1
            return packet

        # 仅当有TCP载荷时才处理
        if not packet.haslayer(TCP) or not packet[TCP].payload:
            self.stats.skipped_packets += 1
            return packet

        original_payload_bytes = raw(packet[TCP].payload)
        payload_bytearray = bytearray(original_payload_bytes)

        # 在可变字节数组上应用所有指令
        for instruction in instructions:
            self._apply_mask_instruction(payload_bytearray, instruction)

        modified_payload_bytes = bytes(payload_bytearray)

        # 检查载荷是否真的被修改
        if original_payload_bytes != modified_payload_bytes:
            self.stats.modified_packets += 1
            self.stats.total_bytes_processed += len(original_payload_bytes)
            self.stats.total_bytes_masked += self._count_masked_bytes(
                original_payload_bytes, modified_payload_bytes
            )

            # 用 Raw 层包裹字节串，保证后续 wrpcap 识别正确
            packet[TCP].remove_payload()
            packet[TCP].add_payload(Raw(load=modified_payload_bytes))
            # Scapy 会在写文件时自动更新校验和
            return packet
        else:
            self.stats.skipped_packets += 1
            return packet

    def _apply_mask_instruction(
        self, payload: bytearray, instruction: PacketMaskInstruction
    ):
        """在字节数组上应用单条掩码指令"""
        if isinstance(instruction, MaskRange):
            start = min(instruction.start, len(payload))
            end = min(instruction.end, len(payload))
            for i in range(start, end):
                payload[i] = 0
        elif isinstance(instruction, MaskAfter):
            keep_bytes = instruction.keep_bytes
            if keep_bytes < len(payload):
                for i in range(keep_bytes, len(payload)):
                    payload[i] = 0
        elif isinstance(instruction, MaskAll):
            for i in range(len(payload)):
                payload[i] = 0
        elif isinstance(instruction, KeepAll):
            pass  # 不做任何操作
        else:
            self.logger.warning(f"未知的掩码指令类型: {type(instruction)}")

    def _count_masked_bytes(self, original: bytes, modified: bytes) -> int:
        """计算被掩码的字节数"""
        # A simple estimate
        return abs(len(original) - len(modified)) + sum(
            1 for o, m in zip(original, modified) if o != m
        )

    def get_statistics(self) -> MaskingStatistics:
        """获取处理统计信息"""
        return self.stats
    
    def reset_statistics(self):
        """重置统计信息"""
        self.stats = MaskingStatistics() 