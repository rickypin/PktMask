"""
独立PCAP掩码处理器掩码应用器

实现基于序列号的精确掩码应用逻辑，支持三种掩码类型。
这是Phase 4的核心组件之一。
"""

import copy
from typing import List, Dict, Tuple, Optional, Any
import logging
from scapy.all import Packet, Raw

from .models import MaskEntry, SequenceMaskTable, MaskingResult
from .payload_extractor import PayloadExtractor
from ..exceptions import IndependentMaskerError, ValidationError


class MaskApplier:
    """掩码应用器
    
    负责将掩码规则精确应用到数据包载荷中。
    支持mask_after、mask_range、keep_all三种掩码类型。
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
            'mask_after_applied': 0,
            'mask_range_applied': 0,
            'keep_all_applied': 0,
            'sequence_matches': 0,
            'sequence_mismatches': 0,
            'application_failures': 0
        }
    
    def apply_masks_to_packets(
        self,
        packets: List[Packet],
        mask_table: SequenceMaskTable
    ) -> Tuple[List[Packet], Dict[str, Any]]:
        """将掩码应用到数据包列表
        
        Args:
            packets: 要处理的数据包列表
            mask_table: 序列号掩码表
            
        Returns:
            Tuple[List[Packet], Dict]: (修改后的数据包列表, 应用统计信息)
        """
        self.logger.info(f"开始应用掩码到 {len(packets)} 个数据包")
        
        # 重置统计信息
        self.reset_statistics()
        
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
                
                # 查找匹配的掩码条目
                matching_entries = mask_table.find_matches(stream_id, sequence)
                
                if not matching_entries:
                    self.stats['sequence_mismatches'] += 1
                    # 没有匹配的掩码条目，原样保留
                    modified_packets.append(packet)
                    continue
                
                self.stats['sequence_matches'] += 1
                
                # 应用掩码
                modified_packet = self._apply_masks_to_packet(
                    packet, payload, matching_entries, sequence
                )
                
                modified_packets.append(modified_packet)
                
            except Exception as e:
                self.stats['application_failures'] += 1
                self.logger.warning(f"掩码应用失败: {e}")
                # 失败时保留原包
                modified_packets.append(packet)
        
        # 汇总统计信息
        application_stats = self._generate_application_stats()
        
        self.logger.info(
            f"掩码应用完成: {self.stats['packets_modified']}/{self.stats['packets_processed']} "
            f"个数据包被修改，{self.stats['bytes_masked']} 字节被掩码"
        )
        
        return modified_packets, application_stats
    
    def _apply_masks_to_packet(
        self,
        packet: Packet,
        payload: bytes,
        mask_entries: List[MaskEntry],
        sequence: int
    ) -> Packet:
        """将掩码应用到单个数据包
        
        Args:
            packet: 原始数据包
            payload: TCP载荷
            mask_entries: 匹配的掩码条目列表
            sequence: 序列号
            
        Returns:
            Packet: 修改后的数据包
        """
        # 复制数据包以避免修改原始包
        modified_packet = copy.deepcopy(packet)
        
        # 转换载荷为可修改的字节数组
        modified_payload = bytearray(payload)
        original_length = len(modified_payload)
        bytes_masked_this_packet = 0
        
        # 按优先级应用掩码（later entries override earlier ones）
        for entry in mask_entries:
            try:
                bytes_masked = self._apply_mask_entry(
                    modified_payload, entry, sequence, original_length
                )
                bytes_masked_this_packet += bytes_masked
                
                # 更新掩码类型统计
                self._update_mask_type_stats(entry.mask_type)
                
            except Exception as e:
                self.logger.warning(f"应用掩码条目失败: {entry}, 错误: {e}")
        
        # 如果有字节被掩码，更新数据包
        if bytes_masked_this_packet > 0:
            self._update_packet_payload(modified_packet, bytes(modified_payload))
            self.stats['packets_modified'] += 1
            self.stats['bytes_masked'] += bytes_masked_this_packet
        
        return modified_packet
    
    def _apply_mask_entry(
        self,
        payload: bytearray,
        mask_entry: MaskEntry,
        sequence: int,
        original_length: int
    ) -> int:
        """应用单个掩码条目
        
        Args:
            payload: 可修改的载荷字节数组
            mask_entry: 掩码条目
            sequence: 当前序列号
            original_length: 原始载荷长度
            
        Returns:
            int: 被掩码的字节数
        """
        if mask_entry.mask_type == "keep_all":
            return self._apply_keep_all(payload, mask_entry)
        elif mask_entry.mask_type == "mask_after":
            return self._apply_mask_after(payload, mask_entry)
        elif mask_entry.mask_type == "mask_range":
            return self._apply_mask_range(payload, mask_entry)
        else:
            raise ValidationError(f"不支持的掩码类型: {mask_entry.mask_type}")
    
    def _apply_mask_after(self, payload: bytearray, mask_entry: MaskEntry) -> int:
        """应用mask_after掩码类型
        
        保留前N个字节，掩码其余部分。
        
        Args:
            payload: 载荷字节数组
            mask_entry: 掩码条目
            
        Returns:
            int: 被掩码的字节数
        """
        keep_bytes = mask_entry.mask_params.get('keep_bytes', 0)
        
        if keep_bytes < 0:
            raise ValidationError(f"keep_bytes不能为负数: {keep_bytes}")
        
        if keep_bytes >= len(payload):
            # 保留字节数超过载荷长度，不进行掩码
            return 0
        
        # 掩码从keep_bytes位置开始到结尾
        masked_bytes = len(payload) - keep_bytes
        for i in range(keep_bytes, len(payload)):
            payload[i] = self.mask_byte_value
        
        self.logger.debug(
            f"mask_after: 保留前 {keep_bytes} 字节，掩码 {masked_bytes} 字节"
        )
        
        return masked_bytes
    
    def _apply_mask_range(self, payload: bytearray, mask_entry: MaskEntry) -> int:
        """应用mask_range掩码类型
        
        掩码指定的字节范围。
        
        Args:
            payload: 载荷字节数组
            mask_entry: 掩码条目
            
        Returns:
            int: 被掩码的字节数
        """
        ranges = mask_entry.mask_params.get('ranges', [])
        
        if not isinstance(ranges, list):
            raise ValidationError(f"ranges必须是列表: {ranges}")
        
        total_masked = 0
        
        for range_tuple in ranges:
            if not isinstance(range_tuple, (list, tuple)) or len(range_tuple) != 2:
                raise ValidationError(f"范围必须是(start, end)格式: {range_tuple}")
            
            start, end = range_tuple
            
            # 验证范围
            if start < 0 or end < 0:
                raise ValidationError(f"范围索引不能为负数: ({start}, {end})")
            
            if start >= end:
                continue  # 跳过无效范围
            
            # 限制在载荷长度内
            start = min(start, len(payload))
            end = min(end, len(payload))
            
            if start >= len(payload):
                continue  # 超出载荷范围
            
            # 应用掩码
            for i in range(start, end):
                payload[i] = self.mask_byte_value
                total_masked += 1
        
        self.logger.debug(f"mask_range: 掩码 {len(ranges)} 个范围，总计 {total_masked} 字节")
        
        return total_masked
    
    def _apply_keep_all(self, payload: bytearray, mask_entry: MaskEntry) -> int:
        """应用keep_all掩码类型
        
        保留所有字节，不进行掩码（用于调试）。
        
        Args:
            payload: 载荷字节数组
            mask_entry: 掩码条目
            
        Returns:
            int: 被掩码的字节数（always 0）
        """
        self.logger.debug("keep_all: 保留所有字节，不进行掩码")
        return 0
    
    def _update_packet_payload(self, packet: Packet, new_payload: bytes) -> None:
        """更新数据包的载荷
        
        Args:
            packet: 要更新的数据包
            new_payload: 新的载荷字节
        """
        # 查找Raw层并更新
        raw_layer = packet.getlayer(Raw)
        if raw_layer is not None:
            raw_layer.load = new_payload
            
            # 重新计算校验和（如果需要）
            # 注意：这里可能需要更复杂的校验和计算逻辑
            # 但为了保持文件一致性，我们暂时不重新计算
        else:
            self.logger.warning("无法找到Raw层来更新载荷")
    
    def _update_mask_type_stats(self, mask_type: str) -> None:
        """更新掩码类型统计"""
        if mask_type == "mask_after":
            self.stats['mask_after_applied'] += 1
        elif mask_type == "mask_range":
            self.stats['mask_range_applied'] += 1
        elif mask_type == "keep_all":
            self.stats['keep_all_applied'] += 1
    
    def _generate_application_stats(self) -> Dict[str, Any]:
        """生成应用统计信息"""
        stats = self.stats.copy()
        
        # 计算率值
        if stats['packets_processed'] > 0:
            stats['modification_rate'] = stats['packets_modified'] / stats['packets_processed']
            stats['sequence_match_rate'] = stats['sequence_matches'] / stats['packets_processed']
        
        if stats['sequence_matches'] > 0:
            stats['application_success_rate'] = (
                stats['sequence_matches'] - stats['application_failures']
            ) / stats['sequence_matches']
        
        # 添加提取器统计
        stats['payload_extraction'] = self.payload_extractor.get_statistics()
        
        return stats
    
    def reset_statistics(self) -> None:
        """重置统计信息"""
        self.stats = {
            'packets_processed': 0,
            'packets_modified': 0,
            'bytes_masked': 0,
            'mask_after_applied': 0,
            'mask_range_applied': 0,
            'keep_all_applied': 0,
            'sequence_matches': 0,
            'sequence_mismatches': 0,
            'application_failures': 0
        }
        
        # 同时重置载荷提取器统计
        self.payload_extractor.reset_statistics()
        
        self.logger.debug("掩码应用器统计信息已重置")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取详细统计信息"""
        return self._generate_application_stats()
    
    def validate_mask_application(
        self,
        original_payload: bytes,
        modified_payload: bytes,
        mask_entries: List[MaskEntry]
    ) -> Dict[str, Any]:
        """验证掩码应用的正确性
        
        Args:
            original_payload: 原始载荷
            modified_payload: 修改后载荷
            mask_entries: 应用的掩码条目
            
        Returns:
            Dict: 验证结果
        """
        if len(original_payload) != len(modified_payload):
            return {
                'valid': False,
                'error': f"载荷长度不匹配: {len(original_payload)} vs {len(modified_payload)}"
            }
        
        expected_modifications = set()
        
        # 计算期望的修改位置
        for entry in mask_entries:
            if entry.mask_type == "mask_after":
                keep_bytes = entry.mask_params.get('keep_bytes', 0)
                for i in range(keep_bytes, len(original_payload)):
                    expected_modifications.add(i)
            elif entry.mask_type == "mask_range":
                ranges = entry.mask_params.get('ranges', [])
                for start, end in ranges:
                    for i in range(max(0, start), min(len(original_payload), end)):
                        expected_modifications.add(i)
            # keep_all 不添加任何修改位置
        
        # 检查实际修改
        actual_modifications = set()
        for i in range(len(original_payload)):
            if original_payload[i] != modified_payload[i]:
                actual_modifications.add(i)
                if modified_payload[i] != self.mask_byte_value:
                    return {
                        'valid': False,
                        'error': f"位置 {i} 的掩码值不正确: 期望 {self.mask_byte_value}, 实际 {modified_payload[i]}"
                    }
        
        # 比较期望和实际修改
        unexpected_modifications = actual_modifications - expected_modifications
        missing_modifications = expected_modifications - actual_modifications
        
        return {
            'valid': len(unexpected_modifications) == 0 and len(missing_modifications) == 0,
            'expected_modifications': len(expected_modifications),
            'actual_modifications': len(actual_modifications),
            'unexpected_modifications': list(unexpected_modifications),
            'missing_modifications': list(missing_modifications)
        }


def create_mask_applier(
    mask_byte_value: int = 0x00,
    logger: Optional[logging.Logger] = None
) -> MaskApplier:
    """创建掩码应用器实例的工厂函数
    
    Args:
        mask_byte_value: 掩码字节值
        logger: 可选的日志器实例
        
    Returns:
        MaskApplier: 配置好的掩码应用器实例
    """
    return MaskApplier(mask_byte_value, logger) 