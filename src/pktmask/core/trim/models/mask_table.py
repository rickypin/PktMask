"""
流掩码表实现

基于TCP/UDP流和序列号的掩码映射表，用于记录哪些字节区间需要应用什么样的掩码。
"""

from collections import defaultdict
from typing import List, Optional, Dict, Tuple, Any
from dataclasses import dataclass
import bisect
import logging

from .mask_spec import MaskSpec, MaskAfter
from ..exceptions import StreamMaskTableError


@dataclass
class StreamMaskEntry:
    """
    流掩码条目
    
    记录特定流中特定序列号范围的掩码规范。
    """
    
    stream_id: str
    seq_start: int
    seq_end: int
    mask_spec: MaskSpec
    
    def __post_init__(self):
        if self.seq_start < 0 or self.seq_end < 0:
            raise StreamMaskTableError(
                operation="create_entry",
                stream_id=self.stream_id,
                message=f"序列号不能为负数: start={self.seq_start}, end={self.seq_end}"
            )
        if self.seq_start >= self.seq_end:
            raise StreamMaskTableError(
                operation="create_entry", 
                stream_id=self.stream_id,
                message=f"起始序列号必须小于结束序列号: start={self.seq_start}, end={self.seq_end}"
            )
    
    def overlaps_with(self, other: 'StreamMaskEntry') -> bool:
        """检查是否与另一个条目重叠"""
        if self.stream_id != other.stream_id:
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


class StreamMaskTable:
    """
    流掩码表
    
    基于TCP/UDP流和序列号的掩码映射表。支持高效的条目添加、查询和合并操作。
    """
    
    def __init__(self):
        # 使用字典存储每个流的掩码条目列表，按序列号排序
        # Key: stream_id, Value: 按seq_start排序的StreamMaskEntry列表
        self._table: Dict[str, List[StreamMaskEntry]] = defaultdict(list)
        self._is_finalized = False
        self._logger = logging.getLogger(__name__)
    
    def add_entry(self, entry: StreamMaskEntry) -> None:
        """
        添加掩码条目
        
        Args:
            entry: 要添加的掩码条目
        """
        if self._is_finalized:
            raise StreamMaskTableError(
                operation="add_entry",
                stream_id=entry.stream_id,
                message="表已经完成，不能添加新条目"
            )
        
        stream_entries = self._table[entry.stream_id]
        
        # 使用二分查找插入位置保持排序
        insert_pos = bisect.bisect_left(
            stream_entries, 
            entry.seq_start,
            key=lambda x: x.seq_start
        )
        
        stream_entries.insert(insert_pos, entry)
        
        self._logger.debug(f"添加掩码条目: {entry.stream_id} [{entry.seq_start}:{entry.seq_end}) {entry.mask_spec.get_description()}")
    
    def add_mask_range(self, stream_id: str, seq_start: int, seq_end: int, mask_spec: MaskSpec) -> None:
        """
        添加掩码范围的便捷方法
        
        Args:
            stream_id: 流标识符
            seq_start: 起始序列号
            seq_end: 结束序列号
            mask_spec: 掩码规范
        """
        entry = StreamMaskEntry(stream_id, seq_start, seq_end, mask_spec)
        self.add_entry(entry)
    
    def finalize(self) -> None:
        """
        完成表构建，执行合并和优化操作
        
        此方法会合并相邻的相同掩码条目，并优化表结构以提高查询性能。
        """
        if self._is_finalized:
            return
        
        self._logger.info("开始完成流掩码表构建...")
        
        total_entries_before = self.get_total_entry_count()
        
        # 对每个流的条目进行合并
        for stream_id in self._table:
            self._merge_stream_entries(stream_id)
        
        total_entries_after = self.get_total_entry_count()
        
        self._is_finalized = True
        self._logger.info(f"流掩码表构建完成: {total_entries_before} -> {total_entries_after} 条目")
    
    def _merge_stream_entries(self, stream_id: str) -> None:
        """合并指定流的相邻条目"""
        entries = self._table[stream_id]
        if len(entries) <= 1:
            return
        
        merged = []
        current = entries[0]
        
        for next_entry in entries[1:]:
            # 检查是否可以合并：相邻且掩码规范相同
            if (current.seq_end == next_entry.seq_start and 
                type(current.mask_spec) == type(next_entry.mask_spec) and
                self._can_merge_specs(current.mask_spec, next_entry.mask_spec)):
                
                # 合并条目
                current = StreamMaskEntry(
                    stream_id=current.stream_id,
                    seq_start=current.seq_start,
                    seq_end=next_entry.seq_end,
                    mask_spec=current.mask_spec
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
        # 只有相同类型且参数相同的规范才能合并
        if type(spec1) != type(spec2):
            return False
        
        # 对于MaskAfter类型，检查keep_bytes是否相同
        if isinstance(spec1, MaskAfter) and isinstance(spec2, MaskAfter):
            return spec1.keep_bytes == spec2.keep_bytes
        
        # 对于其他类型，目前简单地认为不能合并
        # 未来可以根据需要扩展
        return False
    
    def lookup(self, stream_id: str, seq: int, length: int) -> Optional[MaskSpec]:
        """
        查询指定位置的掩码规范
        
        Args:
            stream_id: 流标识符
            seq: 序列号
            length: 载荷长度
            
        Returns:
            匹配的掩码规范，如果没有匹配则返回None
        """
        if not self._is_finalized:
            self._logger.warning("表未完成，查询结果可能不准确")
        
        entries = self._table.get(stream_id, [])
        if not entries:
            return None
        
        seq_end = seq + length
        
        # 使用二分查找找到可能的匹配条目
        # 找到第一个seq_start <= seq的条目
        search_pos = bisect.bisect_right(entries, seq, key=lambda x: x.seq_start)
        
        # 向前查找可能的匹配
        for i in range(search_pos - 1, -1, -1):
            entry = entries[i]
            if entry.intersects_range(seq, seq_end):
                return entry.mask_spec
            # 如果条目结束位置在查询位置之前，后面的条目不可能匹配
            if entry.seq_end <= seq:
                break
        
        return None
    
    def lookup_multiple(self, stream_id: str, seq: int, length: int) -> List[Tuple[int, int, MaskSpec]]:
        """
        查询指定范围内的所有掩码规范
        
        Args:
            stream_id: 流标识符
            seq: 序列号
            length: 载荷长度
            
        Returns:
            匹配的掩码规范列表，每个元素为(relative_start, relative_end, mask_spec)
        """
        entries = self._table.get(stream_id, [])
        if not entries:
            return []
        
        seq_end = seq + length
        matches = []
        
        for entry in entries:
            intersection = entry.get_intersection(seq, seq_end)
            if intersection:
                # 转换为相对于载荷起始位置的偏移
                relative_start = intersection[0] - seq
                relative_end = intersection[1] - seq
                matches.append((relative_start, relative_end, entry.mask_spec))
        return matches
    
    def get_stream_ids(self) -> List[str]:
        """获取所有流标识符"""
        return list(self._table.keys())
    
    def get_stream_entry_count(self, stream_id: str) -> int:
        """获取指定流的条目数量"""
        return len(self._table.get(stream_id, []))
    
    def get_total_entry_count(self) -> int:
        """获取总条目数量"""
        return sum(len(entries) for entries in self._table.values())
    
    def get_stream_coverage(self, stream_id: str) -> Tuple[int, int]:
        """
        获取指定流的覆盖范围
        
        Args:
            stream_id: 流标识符
            
        Returns:
            (min_seq, max_seq) 覆盖的序列号范围
        """
        entries = self._table.get(stream_id, [])
        if not entries:
            return (0, 0)
        
        min_seq = min(entry.seq_start for entry in entries)
        max_seq = max(entry.seq_end for entry in entries)
        return (min_seq, max_seq)
    
    def clear(self) -> None:
        """清空掩码表"""
        self._table.clear()
        self._is_finalized = False
        self._logger.debug("流掩码表已清空")
    
    def export_to_dict(self) -> Dict[str, Any]:
        """
        导出为字典格式
        
        Returns:
            包含掩码表数据的字典
        """
        result = {
            'is_finalized': self._is_finalized,
            'streams': {}
        }
        
        for stream_id, entries in self._table.items():
            stream_data = []
            for entry in entries:
                stream_data.append({
                    'seq_start': entry.seq_start,
                    'seq_end': entry.seq_end,
                    'mask_type': type(entry.mask_spec).__name__,
                    'mask_spec': self._serialize_mask_spec(entry.mask_spec)
                })
            result['streams'][stream_id] = stream_data
        
        return result
    
    def _serialize_mask_spec(self, mask_spec: MaskSpec) -> Dict[str, Any]:
        """序列化掩码规范"""
        if isinstance(mask_spec, MaskAfter):
            return {'keep_bytes': mask_spec.keep_bytes}
        elif hasattr(mask_spec, 'ranges'):  # MaskRange
            return {'ranges': mask_spec.ranges}
        else:
            return {}
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            包含各种统计数据的字典
        """
        stats = {
            'total_streams': len(self._table),
            'total_entries': self.get_total_entry_count(),
            'is_finalized': self._is_finalized,
            'streams': {}
        }
        
        for stream_id in self._table:
            stream_stats = {
                'entry_count': self.get_stream_entry_count(stream_id),
                'coverage': self.get_stream_coverage(stream_id)
            }
            stats['streams'][stream_id] = stream_stats
        
        return stats 