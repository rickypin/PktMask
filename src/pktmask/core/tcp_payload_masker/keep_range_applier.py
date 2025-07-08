"""
TCP载荷掩码应用器

基于保留范围的TCP载荷掩码应用逻辑。
"""

import copy
from typing import List, Dict, Tuple, Optional, Any
import logging
from scapy.all import Packet, Raw

from .keep_range_models import TcpKeepRangeEntry, TcpKeepRangeTable, TcpMaskingResult
from .payload_extractor import PayloadExtractor
from .exceptions import TcpPayloadMaskerError, ValidationError


class MaskApplier:
    """掩码应用器
    
    负责将掩码规则精确应用到数据包载荷中。
    支持基于保留范围的TCP载荷掩码。
    """
    
    def __init__(self, mask_byte_value: int = 0x00, logger: Optional[logging.Logger] = None):
        """初始化掩码应用器
        
        Args:
            mask_byte_value: 掩码字节值，默认为0x00
            logger: 可选的日志器实例
        """
        self.mask_byte_value = mask_byte_value
        self.logger = logger or logging.getLogger(__name__)
        
        # 载荷提取器
        self.payload_extractor = PayloadExtractor(logger)
        
        # 统计信息
        self.stats = {
            'packets_processed': 0,
            'packets_modified': 0,
            'bytes_masked': 0,
            'keep_ranges_applied': 0,
            'tcp_streams_processed': 0
        }
    
    def apply_keep_ranges_to_packets(
        self,
        packets: List[Packet],
        keep_range_table: TcpKeepRangeTable
    ) -> Tuple[List[Packet], Dict[str, Any]]:
        """将保留范围掩码应用到数据包列表
        
        Args:
            packets: 要处理的数据包列表
            keep_range_table: TCP保留范围表
            
        Returns:
            Tuple[List[Packet], Dict]: (修改后的数据包列表, 应用统计信息)
        """
        self.logger.info(f"开始应用保留范围掩码到 {len(packets)} 个数据包")
        
        # 重置统计信息
        self._reset_statistics()
        
        modified_packets = []
        
        for packet in packets:
            self.stats['packets_processed'] += 1
            
            try:
                # 提取流信息
                stream_info = self.payload_extractor.extract_stream_info(packet)
                if stream_info is None:
                    # 非TCP包或无载荷，原样保留
                    modified_packets.append(packet)
                    continue
                
                stream_id, sequence, payload = stream_info
                
                # 查找匹配的保留范围
                keep_ranges = keep_range_table.find_keep_ranges_for_sequence(stream_id, sequence)
                
                if not keep_ranges:
                    # 没有匹配的范围，原样保留
                    modified_packets.append(packet)
                    continue
                
                # 应用保留范围掩码
                modified_packet = self._apply_keep_ranges_to_packet(
                    packet, payload, keep_ranges
                )
                
                modified_packets.append(modified_packet)
                
            except Exception as e:
                self.logger.warning(f"保留范围掩码应用失败: {e}")
                # 失败时保留原包
                modified_packets.append(packet)
        
        # 汇总统计信息
        stats = self._generate_statistics()
        
        self.logger.info(
            f"保留范围掩码应用完成: {self.stats['packets_modified']}/{self.stats['packets_processed']} "
            f"个数据包被修改"
        )
        
        return modified_packets, stats
    
    def _apply_keep_ranges_to_packet(
        self,
        packet: Packet,
        payload: bytes,
        keep_ranges: List[Tuple[int, int]]
    ) -> Packet:
        """将保留范围掩码应用到单个数据包
        
        Args:
            packet: 原始数据包
            payload: TCP载荷
            keep_ranges: 需要保留的字节范围列表
            
        Returns:
            Packet: 修改后的数据包
        """
        # 复制数据包以避免修改原始包
        modified_packet = copy.deepcopy(packet)
        
        # 转换载荷为可修改的字节数组
        modified_payload = bytearray(payload)
        
        # 默认掩码所有字节
        for i in range(len(modified_payload)):
            modified_payload[i] = self.mask_byte_value
        
        # 应用保留范围
        bytes_kept = 0
        for keep_start, keep_end in keep_ranges:
            # 确保范围在载荷内
            start = max(0, keep_start)
            end = min(len(payload), keep_end)
            
            if start < end:
                # 恢复保留范围内的原始字节
                modified_payload[start:end] = payload[start:end]
                bytes_kept += (end - start)
        
        # 更新数据包载荷
        self._update_packet_payload(modified_packet, bytes(modified_payload))
        
        # 更新统计
        if bytes_kept > 0:
            self.stats['packets_modified'] += 1
            self.stats['keep_ranges_applied'] += len(keep_ranges)
            self.stats['bytes_masked'] += len(modified_payload) - bytes_kept
        
        return modified_packet
    
    def _update_packet_payload(self, packet: Packet, new_payload: bytes) -> None:
        """更新数据包的载荷部分"""
        if packet.haslayer(Raw):
            packet[Raw].load = new_payload
        elif hasattr(packet, 'payload') and packet.payload:
            # 如果没有Raw层但有payload，创建一个新的Raw层
            packet.payload = Raw(load=new_payload)
    
    def _reset_statistics(self) -> None:
        """重置统计信息"""
        self.stats = {
            'packets_processed': 0,
            'packets_modified': 0,
            'bytes_masked': 0,
            'keep_ranges_applied': 0,
            'tcp_streams_processed': 0
        }
    
    def _generate_statistics(self) -> Dict[str, Any]:
        """生成统计信息报告"""
        return {
            'tcp_packets_modified': self.stats['packets_modified'],
            'bytes_masked': self.stats['bytes_masked'],
            'bytes_kept': 0,  # 计算保留的字节数
            'keep_ranges_applied': self.stats['keep_ranges_applied'],
            'tcp_streams_processed': self.stats['tcp_streams_processed'],
            'protocol_detections': {}
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取当前统计信息"""
        return self.stats.copy()


def create_mask_applier(
    mask_byte_value: int = 0x00,
    logger: Optional[logging.Logger] = None
) -> MaskApplier:
    """创建掩码应用器实例的工厂函数
    
    Args:
        mask_byte_value: 掩码字节值
        logger: 可选的日志器
        
    Returns:
        MaskApplier: 掩码应用器实例
    """
    return MaskApplier(mask_byte_value=mask_byte_value, logger=logger) 