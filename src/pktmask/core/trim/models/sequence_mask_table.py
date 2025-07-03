"""
基于TCP序列号的掩码表实现

实现基于TCP序列号绝对值范围的通用掩码机制，支持方向性TCP流处理。
这是重构方案中的核心数据结构。
"""

from collections import defaultdict
from typing import List, Optional, Dict, Tuple, Any, Union
from dataclasses import dataclass
import bisect
import logging

from .mask_spec import MaskSpec
from .tcp_stream import ConnectionDirection, TCPStreamManager
from ..exceptions import StreamMaskTableError


@dataclass
class MaskEntry:
    """
    掩码条目
    
    记录特定TCP流中特定序列号范围的掩码规范，这是重构方案的核心数据模型。
    """
    
    tcp_stream_id: str          # TCP流标识（含方向）
    seq_start: int              # 绝对序列号起始位置
    seq_end: int                # 绝对序列号结束位置
    mask_type: str              # 掩码类型（如"tls_application_data"）
    mask_spec: MaskSpec         # 掩码规范
    preserve_headers: List[Tuple[int, int]] = None  # 需要保留的头部范围 [(start, end), ...]
    
    def __post_init__(self):
        if self.preserve_headers is None:
            self.preserve_headers = []
            
        if self.seq_start < 0 or self.seq_end < 0:
            raise StreamMaskTableError(
                operation="create_mask_entry",
                stream_id=self.tcp_stream_id,
                message=f"序列号不能为负数: start={self.seq_start}, end={self.seq_end}"
            )
        if self.seq_start >= self.seq_end:
            raise StreamMaskTableError(
                operation="create_mask_entry", 
                stream_id=self.tcp_stream_id,
                message=f"起始序列号必须小于结束序列号: start={self.seq_start}, end={self.seq_end}"
            )
    
    def overlaps_with(self, other: 'MaskEntry') -> bool:
        """检查是否与另一个条目重叠"""
        if self.tcp_stream_id != other.tcp_stream_id:
            return False
        return not (self.seq_end <= other.seq_start or other.seq_end <= self.seq_start)
    
    def contains_range(self, seq_start: int, seq_end: int) -> bool:
        """检查是否包含指定的序列号范围"""
        return self.seq_start <= seq_start and seq_end <= self.seq_end
    
    def intersects_range(self, seq_start: int, seq_end: int) -> bool:
        """检查是否与指定的序列号范围相交"""
        return not (self.seq_end <= seq_start or seq_end <= self.seq_start)
    
    def get_intersection(self, seq_start: int, seq_end: int) -> Optional[Tuple[int, int]]:
        """获取与指定范围的交集"""
        if not self.intersects_range(seq_start, seq_end):
            return None
        
        intersect_start = max(self.seq_start, seq_start)
        intersect_end = min(self.seq_end, seq_end)
        return (intersect_start, intersect_end)
    
    def get_description(self) -> str:
        """获取条目描述"""
        header_info = ""
        if self.preserve_headers:
            header_ranges = [f"[{start}:{end})" for start, end in self.preserve_headers]
            header_info = f", 保留头部: {', '.join(header_ranges)}"
        
        return f"{self.mask_type} [{self.seq_start}:{self.seq_end}){header_info}"


class SequenceMatchResult:
    """
    序列号匹配结果
    
    封装序列号范围匹配的结果信息，包括匹配状态和偏移量计算。
    """
    
    def __init__(self, is_match: bool, mask_start_offset: int = 0, mask_end_offset: int = 0, 
                 entry: Optional[MaskEntry] = None):
        self.is_match = is_match
        self.mask_start_offset = mask_start_offset
        self.mask_end_offset = mask_end_offset
        self.entry = entry
    
    @property
    def mask_length(self) -> int:
        """获取掩码长度"""
        if not self.is_match:
            return 0
        return self.mask_end_offset - self.mask_start_offset
    
    def apply_preserve_headers(self, payload: bytearray) -> bytearray:
        """
        应用头部保留规则
        
        Args:
            payload: 载荷数据
            
        Returns:
            应用头部保留后的载荷
        """
        if not self.entry or not self.entry.preserve_headers:
            return payload
        
        # 对于每个需要保留的头部范围，恢复原始数据
        for header_start, header_end in self.entry.preserve_headers:
            # 计算在当前payload中的相对位置
            payload_header_start = max(0, header_start - self.mask_start_offset)
            payload_header_end = min(len(payload), header_end - self.mask_start_offset)
            
            if payload_header_start < payload_header_end:
                # 这里应该从原始数据恢复，暂时先跳过置零
                pass
        
        return payload


class SequenceMaskTable:
    """
    基于序列号的掩码表
    
    实现重构方案中要求的基于TCP序列号绝对值范围的通用掩码机制。
    支持方向性TCP流处理和高效的序列号匹配算法。
    """
    
    def __init__(self):
        # 使用字典存储每个流的掩码条目列表，按序列号排序
        # Key: tcp_stream_id, Value: 按seq_start排序的MaskEntry列表
        self._table: Dict[str, List[MaskEntry]] = defaultdict(list)
        self._stream_manager = TCPStreamManager()
        self._is_finalized = False
        self._logger = logging.getLogger(__name__)
        
        # 统计信息
        self._stats = {
            'entries_added': 0,
            'entries_merged': 0,
            'lookups_performed': 0,
            'matches_found': 0
        }
    
    def add_entry(self, entry: MaskEntry) -> None:
        """
        添加掩码条目
        
        Args:
            entry: 要添加的掩码条目
        """
        if self._is_finalized:
            raise StreamMaskTableError(
                operation="add_entry",
                stream_id=entry.tcp_stream_id,
                message="表已经完成，不能添加新条目"
            )
        
        stream_entries = self._table[entry.tcp_stream_id]
        
        # 使用二分查找插入位置保持排序 (Python 3.9兼容版本)
        seq_starts = [x.seq_start for x in stream_entries]
        insert_pos = bisect.bisect_left(seq_starts, entry.seq_start)
        
        stream_entries.insert(insert_pos, entry)
        self._stats['entries_added'] += 1
        
        self._logger.debug(f"添加掩码条目: {entry.get_description()}")
    
    def add_mask_range(
        self, 
        tcp_stream_id: str, 
        seq_start: int, 
        seq_end: int, 
        mask_type: str,
        mask_spec: MaskSpec,
        preserve_headers: List[Tuple[int, int]] = None
    ) -> None:
        """
        添加掩码范围的便捷方法
        
        Args:
            tcp_stream_id: TCP流标识符（含方向）
            seq_start: 起始序列号
            seq_end: 结束序列号
            mask_type: 掩码类型
            mask_spec: 掩码规范
            preserve_headers: 需要保留的头部范围列表
        """
        entry = MaskEntry(
            tcp_stream_id=tcp_stream_id,
            seq_start=seq_start,
            seq_end=seq_end,
            mask_type=mask_type,
            mask_spec=mask_spec,
            preserve_headers=preserve_headers or []
        )
        self.add_entry(entry)
    
    def match_sequence_range(
        self, 
        tcp_stream_id: str,
        packet_seq: int, 
        payload_len: int
    ) -> List[SequenceMatchResult]:
        """
        匹配数据包序列号范围与掩码条目
        
        这是重构方案的核心算法，实现精确的序列号范围匹配。
        
        Args:
            tcp_stream_id: TCP流标识符
            packet_seq: 数据包序列号
            payload_len: 载荷长度
            
        Returns:
            匹配结果列表
        """
        self._stats['lookups_performed'] += 1
        
        if tcp_stream_id not in self._table:
            return []
        
        packet_start = packet_seq
        packet_end = packet_seq + payload_len
        
        stream_entries = self._table[tcp_stream_id]
        results = []
        
        # 使用二分查找找到可能相交的条目范围 (Python 3.9兼容版本)
        seq_starts = [x.seq_start for x in stream_entries]
        start_idx = bisect.bisect_left(seq_starts, packet_end)
        
        # 向前查找所有可能相交的条目
        for i in range(start_idx):
            entry = stream_entries[i]
            if entry.seq_end <= packet_start:
                continue
                
            # 计算重叠范围
            overlap_start = max(packet_start, entry.seq_start)
            overlap_end = min(packet_end, entry.seq_end)
            
            if overlap_start < overlap_end:
                # 转换为数据包内偏移量
                mask_start_offset = overlap_start - packet_start
                mask_end_offset = overlap_end - packet_start
                
                result = SequenceMatchResult(
                    is_match=True,
                    mask_start_offset=mask_start_offset,
                    mask_end_offset=mask_end_offset,
                    entry=entry
                )
                results.append(result)
                self._stats['matches_found'] += 1
        
        return results
    
    def lookup_masks(self, tcp_stream_id: str, packet_seq: int, payload_len: int) -> List[MaskSpec]:
        """
        查询指定位置的掩码规范
        
        Args:
            tcp_stream_id: TCP流标识符
            packet_seq: 数据包序列号
            payload_len: 载荷长度
            
        Returns:
            匹配的掩码规范列表
        """
        match_results = self.match_sequence_range(tcp_stream_id, packet_seq, payload_len)
        return [result.entry.mask_spec for result in match_results if result.is_match]
    
    def finalize(self) -> None:
        """
        完成表构建，执行合并和优化操作
        
        此方法会合并相邻的相同掩码条目，并优化表结构以提高查询性能。
        """
        if self._is_finalized:
            return
        
        self._logger.info("开始完成序列号掩码表构建...")
        
        total_entries_before = self.get_total_entry_count()
        
        # 对每个流的条目进行合并
        for stream_id in self._table:
            self._merge_stream_entries(stream_id)
        
        total_entries_after = self.get_total_entry_count()
        self._stats['entries_merged'] = total_entries_before - total_entries_after
        
        self._is_finalized = True
        self._logger.info(f"序列号掩码表构建完成: {total_entries_before} -> {total_entries_after} 条目")
    
    def _merge_stream_entries(self, stream_id: str) -> None:
        """合并指定流的相邻条目"""
        entries = self._table[stream_id]
        if len(entries) <= 1:
            return
        
        merged = []
        current = entries[0]
        
        for next_entry in entries[1:]:
            # 检查是否可以合并：相邻、同类型且掩码规范相同
            if (current.seq_end == next_entry.seq_start and 
                current.mask_type == next_entry.mask_type and
                type(current.mask_spec) == type(next_entry.mask_spec) and
                self._can_merge_specs(current.mask_spec, next_entry.mask_spec) and
                current.preserve_headers == next_entry.preserve_headers):
                
                # 合并条目
                current = MaskEntry(
                    tcp_stream_id=current.tcp_stream_id,
                    seq_start=current.seq_start,
                    seq_end=next_entry.seq_end,
                    mask_type=current.mask_type,
                    mask_spec=current.mask_spec,
                    preserve_headers=current.preserve_headers
                )
            else:
                # 不能合并，保存当前条目
                merged.append(current)
                current = next_entry
        
        # 添加最后一个条目
        merged.append(current)
        
        self._table[stream_id] = merged
        
        if len(merged) < len(entries):
            self._logger.debug(f"流 {stream_id}: {len(entries)} -> {len(merged)} 条目")
    
    def _can_merge_specs(self, spec1: MaskSpec, spec2: MaskSpec) -> bool:
        """检查两个掩码规范是否可以合并"""
        # 导入掩码规范类型
        from .mask_spec import MaskAfter, KeepAll
        
        if type(spec1) != type(spec2):
            return False
        
        # 对于MaskAfter类型，检查keep_bytes是否相同
        if isinstance(spec1, MaskAfter) and isinstance(spec2, MaskAfter):
            return spec1.keep_bytes == spec2.keep_bytes
        
        # KeepAll类型总是可以合并
        if isinstance(spec1, KeepAll) and isinstance(spec2, KeepAll):
            return True
        
        # 对于其他类型，目前简单地认为不能合并
        return False
    
    def get_stream_ids(self) -> List[str]:
        """获取所有流ID列表"""
        return list(self._table.keys())
    
    def get_stream_entry_count(self, stream_id: str) -> int:
        """获取指定流的条目数量"""
        return len(self._table.get(stream_id, []))
    
    def get_total_entry_count(self) -> int:
        """获取总条目数量"""
        return sum(len(entries) for entries in self._table.values())
    
    def get_stream_coverage(self, stream_id: str) -> Tuple[int, int]:
        """
        获取指定流的序列号覆盖范围
        
        Args:
            stream_id: 流标识符
            
        Returns:
            (最小序列号, 最大序列号) 元组，如果流不存在则返回 (0, 0)
        """
        entries = self._table.get(stream_id, [])
        if not entries:
            return (0, 0)
        
        min_seq = min(entry.seq_start for entry in entries)
        max_seq = max(entry.seq_end for entry in entries)
        return (min_seq, max_seq)
    
    def clear(self) -> None:
        """清除所有数据"""
        self._table.clear()
        self._is_finalized = False
        self._stats = {
            'entries_added': 0,
            'entries_merged': 0,
            'lookups_performed': 0,
            'matches_found': 0
        }
        self._logger.debug("已清除序列号掩码表")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_entries = self.get_total_entry_count()
        stream_count = len(self._table)
        
        return {
            'total_entries': total_entries,
            'stream_count': stream_count,
            'avg_entries_per_stream': total_entries / max(stream_count, 1),
            'is_finalized': self._is_finalized,
            **self._stats
        }
    
    def export_to_dict(self) -> Dict[str, Any]:
        """导出为字典格式"""
        result = {
            'metadata': {
                'type': 'SequenceMaskTable',
                'is_finalized': self._is_finalized,
                'statistics': self.get_statistics()
            },
            'streams': {}
        }
        
        for stream_id, entries in self._table.items():
            result['streams'][stream_id] = [
                {
                    'seq_start': entry.seq_start,
                    'seq_end': entry.seq_end,
                    'mask_type': entry.mask_type,
                    'mask_spec_type': type(entry.mask_spec).__name__,
                    'mask_spec_desc': entry.mask_spec.get_description(),
                    'preserve_headers': entry.preserve_headers
                }
                for entry in entries
            ]
        
        return result 