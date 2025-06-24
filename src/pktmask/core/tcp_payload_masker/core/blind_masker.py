"""
盲操作数据包掩码器

实现基于包级指令的纯字节操作掩码引擎，完全不依赖协议解析。
"""

import time
import logging
from typing import Optional, Tuple
from scapy.all import raw, Ether, IP, TCP
from scapy.packet import Packet

from ..api.types import (
    MaskingRecipe, 
    PacketMaskInstruction, 
    MaskingStatistics,
    PacketMaskingResult
)
from ...trim.models.mask_spec import MaskSpec, MaskAfter, MaskRange, KeepAll


logger = logging.getLogger(__name__)


class BlindPacketMasker:
    """
    盲操作数据包掩码器
    
    这是一个纯字节操作的掩码引擎，它：
    1. 完全不解析协议结构
    2. 基于精确的字节偏移进行操作
    3. 支持所有MaskSpec类型
    4. 自动处理Scapy校验和更新
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
    
    def process_packet(self, packet_index: int, packet: Packet) -> Tuple[Optional[bytes], bool]:
        """
        处理单个数据包
        
        Args:
            packet_index: 包在PCAP中的索引
            packet: Scapy数据包对象
            
        Returns:
            Tuple[修改后的字节流或None, 是否被修改]
            - 如果包被修改，返回(修改后的bytes, True)
            - 如果包未修改，返回(None, False)
        """
        self.stats.processed_packets += 1
        
        try:
            # 获取包的时间戳（转换为字符串格式）
            timestamp = str(packet.time)
            
            # 查找是否有对应的掩码指令
            instruction = self.recipe.get_instruction_for_packet(packet_index, timestamp)
            
            if instruction is None:
                # 没有指令，包保持不变
                self.stats.skipped_packets += 1
                self.logger.debug(f"包{packet_index}无掩码指令，跳过")
                return None, False
            
            # 应用掩码指令
            original_bytes = raw(packet)
            self.stats.total_bytes_processed += len(original_bytes)
            
            modified_bytes = self._apply_mask_instruction(original_bytes, instruction)
            
            if modified_bytes != original_bytes:
                self.stats.modified_packets += 1
                self.stats.total_bytes_masked += self._count_masked_bytes(
                    original_bytes, modified_bytes
                )
                self.logger.debug(
                    f"包{packet_index}已掩码，原始{len(original_bytes)}字节，"
                    f"载荷偏移{instruction.payload_offset}"
                )
                return modified_bytes, True
            else:
                self.stats.skipped_packets += 1
                self.logger.debug(f"包{packet_index}掩码后无变化")
                return None, False
                
        except Exception as e:
            self.stats.error_packets += 1
            self.logger.error(f"处理包{packet_index}时发生错误: {e}")
            return None, False
    
    def _apply_mask_instruction(
        self, 
        raw_bytes: bytes, 
        instruction: PacketMaskInstruction
    ) -> bytes:
        """
        在字节数组上应用掩码指令
        
        Args:
            raw_bytes: 原始包字节流
            instruction: 掩码指令
            
        Returns:
            应用掩码后的字节流
        """
        # 验证载荷偏移量的有效性
        if instruction.payload_offset >= len(raw_bytes):
            self.logger.warning(
                f"载荷偏移{instruction.payload_offset}超出包长度{len(raw_bytes)}，跳过掩码"
            )
            return raw_bytes
        
        # 提取载荷部分
        payload_start = instruction.payload_offset
        payload_bytes = raw_bytes[payload_start:]
        
        if not payload_bytes:
            self.logger.debug("载荷为空，无需掩码")
            return raw_bytes
        
        # 应用掩码规范
        masked_payload = self._apply_mask_spec(payload_bytes, instruction.mask_spec)
        
        # 如果载荷没有变化，直接返回原始字节流
        if masked_payload == payload_bytes:
            return raw_bytes
        
        # 重新组装数据包：头部 + 掩码后的载荷
        header_bytes = raw_bytes[:payload_start]
        modified_bytes = header_bytes + masked_payload
        
        return modified_bytes
    
    def _apply_mask_spec(self, payload: bytes, mask_spec: MaskSpec) -> bytes:
        """
        应用具体的掩码规范
        
        Args:
            payload: 载荷字节流
            mask_spec: 掩码规范
            
        Returns:
            掩码后的载荷字节流
        """
        if isinstance(mask_spec, MaskAfter):
            return self._apply_mask_after(payload, mask_spec)
        elif isinstance(mask_spec, MaskRange):
            return self._apply_mask_range(payload, mask_spec)
        elif isinstance(mask_spec, KeepAll):
            return payload
        else:
            self.logger.warning(f"未知的掩码类型: {type(mask_spec)}")
            return payload
    
    def _apply_mask_after(self, payload: bytes, mask_spec: MaskAfter) -> bytes:
        """应用MaskAfter掩码"""
        if not payload:
            return payload
        
        keep_bytes = mask_spec.keep_bytes
        
        if keep_bytes <= 0:
            # 全部置零
            return b'\x00' * len(payload)
        elif keep_bytes >= len(payload):
            # 保留全部
            return payload
        else:
            # 保留前N字节，后续置零
            keep_part = payload[:keep_bytes]
            zero_part = b'\x00' * (len(payload) - keep_bytes)
            return keep_part + zero_part
    
    def _apply_mask_range(self, payload: bytes, mask_spec: MaskRange) -> bytes:
        """应用MaskRange掩码"""
        if not payload:
            return payload
        
        # 转换为可变字节数组
        result = bytearray(payload)
        
        # 对每个指定区间进行置零
        for start, end in mask_spec.ranges:
            # 确保不超出载荷边界
            actual_start = min(start, len(result))
            actual_end = min(end, len(result))
            
            # 置零指定区间
            for i in range(actual_start, actual_end):
                result[i] = 0
        
        return bytes(result)
    
    def _count_masked_bytes(self, original: bytes, modified: bytes) -> int:
        """计算被掩码的字节数"""
        if len(original) != len(modified):
            return len(modified)  # 如果长度不同，算作全部被修改
        
        count = 0
        for o, m in zip(original, modified):
            if o != m:
                count += 1
        return count
    
    def get_statistics(self) -> MaskingStatistics:
        """获取处理统计信息"""
        return self.stats
    
    def reset_statistics(self):
        """重置统计信息"""
        self.stats = MaskingStatistics() 