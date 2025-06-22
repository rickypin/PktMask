"""
独立PCAP掩码处理器核心数据结构

定义了掩码处理所需的所有数据模型：
- MaskEntry: 掩码条目定义
- MaskingResult: 处理结果
- SequenceMaskTable: 序列号掩码表
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import logging
from bisect import bisect_left, insort


@dataclass
class MaskEntry:
    """掩码条目定义
    
    定义了对特定TCP流的特定序列号范围应用的掩码规则。
    """
    stream_id: str                                    # TCP流ID (如: "TCP_1.2.3.4:443_5.6.7.8:1234_forward")
    sequence_start: int                               # 序列号起始位置（包含）
    sequence_end: int                                 # 序列号结束位置（不包含）
    mask_type: str                                    # 掩码类型: "mask_after", "mask_range", "keep_all"
    mask_params: Dict[str, Any]                       # 掩码参数
    preserve_headers: Optional[List[Tuple[int, int]]] = None  # 头部保留范围
    
    def __post_init__(self):
        """验证掩码条目的有效性"""
        if self.sequence_start >= self.sequence_end:
            raise ValueError(f"序列号范围无效: start={self.sequence_start} >= end={self.sequence_end}")
        
        if self.mask_type not in ["mask_after", "mask_range", "keep_all"]:
            raise ValueError(f"不支持的掩码类型: {self.mask_type}")
        
        # 验证mask_params的格式
        if self.mask_type == "mask_after" and "keep_bytes" not in self.mask_params:
            raise ValueError("mask_after类型需要keep_bytes参数")
        elif self.mask_type == "mask_range" and "ranges" not in self.mask_params:
            raise ValueError("mask_range类型需要ranges参数")
    
    def covers_sequence(self, sequence: int) -> bool:
        """检查该掩码条目是否覆盖指定序列号"""
        return self.sequence_start <= sequence < self.sequence_end
    
    def get_overlap_length(self, other_start: int, other_end: int) -> int:
        """计算与另一个序列号范围的重叠长度"""
        overlap_start = max(self.sequence_start, other_start)
        overlap_end = min(self.sequence_end, other_end)
        return max(0, overlap_end - overlap_start)


@dataclass
class MaskingResult:
    """掩码处理结果
    
    包含处理过程的详细统计信息和结果。
    """
    success: bool                                     # 处理是否成功
    total_packets: int                                # 总数据包数
    modified_packets: int                             # 修改的数据包数
    bytes_masked: int                                 # 掩码的字节数
    processing_time: float                            # 处理时间（秒）
    streams_processed: int                            # 处理的TCP流数量
    error_message: Optional[str] = None               # 错误信息（失败时）
    statistics: Optional[Dict[str, Any]] = field(default_factory=dict)  # 详细统计信息
    
    def get_modification_rate(self) -> float:
        """获取数据包修改率"""
        if self.total_packets == 0:
            return 0.0
        return self.modified_packets / self.total_packets
    
    def get_processing_speed(self) -> float:
        """获取处理速度（包/秒）"""
        if self.processing_time == 0:
            return 0.0
        return self.total_packets / self.processing_time
    
    def add_statistic(self, key: str, value: Any) -> None:
        """添加统计信息"""
        if self.statistics is None:
            self.statistics = {}
        self.statistics[key] = value
    
    def get_summary(self) -> str:
        """获取结果摘要"""
        if not self.success:
            return f"处理失败: {self.error_message}"
        
        return (
            f"处理成功: {self.modified_packets}/{self.total_packets} 个数据包被修改, "
            f"掩码字节数: {self.bytes_masked}, "
            f"处理时间: {self.processing_time:.2f}秒, "
            f"处理速度: {self.get_processing_speed():.1f} pps"
        )


class SequenceMaskTable:
    """序列号掩码表
    
    高效管理和查询基于序列号的掩码条目。
    使用有序列表实现O(log n)的查询性能。
    """
    
    def __init__(self):
        self.entries: List[MaskEntry] = []
        self._entries_by_stream: Dict[str, List[MaskEntry]] = {}
        self.logger = logging.getLogger(__name__)
    
    def add_entry(self, entry: MaskEntry) -> None:
        """添加掩码条目
        
        Args:
            entry: 要添加的掩码条目
            
        Note:
            条目按序列号起始位置排序，支持高效查询
        """
        # 验证条目有效性
        if not isinstance(entry, MaskEntry):
            raise TypeError("entry必须是MaskEntry类型")
        
        # 添加到总列表
        insort(self.entries, entry, key=lambda x: (x.stream_id, x.sequence_start))
        
        # 添加到按流分组的字典
        if entry.stream_id not in self._entries_by_stream:
            self._entries_by_stream[entry.stream_id] = []
        
        # 在流特定列表中也按序列号排序
        stream_entries = self._entries_by_stream[entry.stream_id]
        insort(stream_entries, entry, key=lambda x: x.sequence_start)
        
        self.logger.debug(f"添加掩码条目: {entry.stream_id} [{entry.sequence_start}, {entry.sequence_end})")
    
    def find_matches(self, stream_id: str, sequence: int) -> List[MaskEntry]:
        """查找匹配指定流ID和序列号的掩码条目
        
        Args:
            stream_id: TCP流ID
            sequence: 序列号
            
        Returns:
            匹配的掩码条目列表（按序列号起始位置排序）
        """
        if stream_id not in self._entries_by_stream:
            return []
        
        stream_entries = self._entries_by_stream[stream_id]
        matches = []
        
        for entry in stream_entries:
            if entry.covers_sequence(sequence):
                matches.append(entry)
            elif entry.sequence_start > sequence:
                # 由于列表已排序，后续条目不可能匹配
                break
        
        return matches
    
    def find_range_overlaps(self, stream_id: str, start_seq: int, end_seq: int) -> List[MaskEntry]:
        """查找与指定序列号范围有重叠的掩码条目
        
        Args:
            stream_id: TCP流ID
            start_seq: 起始序列号
            end_seq: 结束序列号
            
        Returns:
            有重叠的掩码条目列表
        """
        if stream_id not in self._entries_by_stream:
            return []
        
        stream_entries = self._entries_by_stream[stream_id]
        overlaps = []
        
        for entry in stream_entries:
            if entry.get_overlap_length(start_seq, end_seq) > 0:
                overlaps.append(entry)
            elif entry.sequence_start >= end_seq:
                # 后续条目不可能重叠
                break
        
        return overlaps
    
    def get_total_entries(self) -> int:
        """获取总条目数"""
        return len(self.entries)
    
    def get_streams_count(self) -> int:
        """获取流的数量"""
        return len(self._entries_by_stream)
    
    def get_stream_entries(self, stream_id: str) -> List[MaskEntry]:
        """获取指定流的所有掩码条目"""
        return self._entries_by_stream.get(stream_id, []).copy()
    
    def get_all_stream_ids(self) -> List[str]:
        """获取所有流ID"""
        return list(self._entries_by_stream.keys())
    
    def clear(self) -> None:
        """清空所有掩码条目"""
        self.entries.clear()
        self._entries_by_stream.clear()
        self.logger.debug("已清空所有掩码条目")
    
    def remove_stream(self, stream_id: str) -> int:
        """移除指定流的所有掩码条目
        
        Args:
            stream_id: 要移除的流ID
            
        Returns:
            移除的条目数量
        """
        if stream_id not in self._entries_by_stream:
            return 0
        
        # 从流字典中移除
        removed_entries = self._entries_by_stream.pop(stream_id)
        removed_count = len(removed_entries)
        
        # 从总列表中移除
        self.entries = [entry for entry in self.entries if entry.stream_id != stream_id]
        
        self.logger.debug(f"移除流 {stream_id} 的 {removed_count} 个掩码条目")
        return removed_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取掩码表统计信息"""
        stats = {
            "total_entries": self.get_total_entries(),
            "streams_count": self.get_streams_count(),
            "entries_per_stream": {},
            "sequence_range_coverage": {}
        }
        
        for stream_id, entries in self._entries_by_stream.items():
            stats["entries_per_stream"][stream_id] = len(entries)
            
            if entries:
                min_seq = min(entry.sequence_start for entry in entries)
                max_seq = max(entry.sequence_end for entry in entries)
                stats["sequence_range_coverage"][stream_id] = {
                    "min_sequence": min_seq,
                    "max_sequence": max_seq,
                    "total_range": max_seq - min_seq
                }
        
        return stats
    
    def validate_consistency(self) -> List[str]:
        """验证掩码表的一致性
        
        Returns:
            发现的问题列表，空列表表示无问题
        """
        issues = []
        
        # 检查条目重复
        seen_entries = set()
        for entry in self.entries:
            entry_key = (entry.stream_id, entry.sequence_start, entry.sequence_end)
            if entry_key in seen_entries:
                issues.append(f"发现重复条目: {entry_key}")
            seen_entries.add(entry_key)
        
        # 检查流字典一致性
        total_from_streams = sum(len(entries) for entries in self._entries_by_stream.values())
        if total_from_streams != len(self.entries):
            issues.append(f"流字典不一致: 总条目{len(self.entries)} vs 流统计{total_from_streams}")
        
        # 检查序列号范围重叠（警告）
        for stream_id, entries in self._entries_by_stream.items():
            for i in range(len(entries) - 1):
                current = entries[i]
                next_entry = entries[i + 1]
                if current.sequence_end > next_entry.sequence_start:
                    issues.append(
                        f"流 {stream_id} 存在序列号重叠: "
                        f"[{current.sequence_start}, {current.sequence_end}) 与 "
                        f"[{next_entry.sequence_start}, {next_entry.sequence_end})"
                    )
        
        return issues 