"""
TCP载荷掩码处理器核心数据结构

定义了TCP保留范围掩码处理所需的所有数据模型：
- TcpKeepRangeEntry: TCP保留范围条目
- TcpMaskingResult: TCP掩码处理结果  
- TcpKeepRangeTable: TCP保留范围表
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import logging
from bisect import bisect_left, insort


@dataclass
class TcpKeepRangeEntry:
    """TCP保留范围条目 - 极简设计
    
    定义对特定TCP流的特定序列号范围内需要保留的字节范围。
    默认掩码所有载荷，只保留指定范围。
    """
    stream_id: str                      # TCP流ID: "TCP_src:port_dst:port_direction"
    sequence_start: int                 # 序列号起始位置（包含）
    sequence_end: int                   # 序列号结束位置（不包含）
    keep_ranges: List[Tuple[int, int]]  # 需要保留的字节范围列表 [(start, end), ...]
    
    # 可选的协议提示，用于优化处理
    protocol_hint: Optional[str] = None  # "TLS", "HTTP", "SSH" 等
    
    def __post_init__(self):
        """验证保留范围条目的有效性"""
        if self.sequence_start >= self.sequence_end:
            raise ValueError(f"序列号范围无效: start={self.sequence_start} >= end={self.sequence_end}")
        
        # 验证保留范围格式
        if not isinstance(self.keep_ranges, list):
            raise ValueError("keep_ranges必须是列表类型")
        
        for i, (start, end) in enumerate(self.keep_ranges):
            if not isinstance(start, int) or not isinstance(end, int):
                raise ValueError(f"保留范围[{i}]必须是整数元组: ({start}, {end})")
            if start >= end:
                raise ValueError(f"保留范围[{i}]无效: start={start} >= end={end}")
            if start < 0:
                raise ValueError(f"保留范围[{i}]起始位置不能为负数: {start}")
        
        # 对保留范围排序并验证无重叠
        self.keep_ranges = self._normalize_keep_ranges(self.keep_ranges)
    
    def _normalize_keep_ranges(self, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """标准化保留范围：排序并合并重叠的范围"""
        if not ranges:
            return []
        
        # 按起始位置排序
        sorted_ranges = sorted(ranges)
        merged = [sorted_ranges[0]]
        
        for current_start, current_end in sorted_ranges[1:]:
            last_start, last_end = merged[-1]
            
            # 检查是否重叠或相邻
            if current_start <= last_end:
                # 合并范围
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                # 添加新范围
                merged.append((current_start, current_end))
        
        return merged
    
    def covers_sequence(self, sequence: int) -> bool:
        """检查该条目是否覆盖指定序列号"""
        return self.sequence_start <= sequence < self.sequence_end
    
    def get_keep_ranges_for_offset(self, offset: int) -> List[Tuple[int, int]]:
        """获取相对于指定偏移量的保留范围
        
        Args:
            offset: 相对于sequence_start的偏移量
            
        Returns:
            调整后的保留范围列表
        """
        if not self.covers_sequence(self.sequence_start + offset):
            return []
        
        # 调整范围相对于给定偏移量
        adjusted_ranges = []
        for start, end in self.keep_ranges:
            adjusted_ranges.append((start + offset, end + offset))
        
        return adjusted_ranges
    
    def get_total_keep_bytes(self) -> int:
        """计算总保留字节数"""
        return sum(end - start for start, end in self.keep_ranges)
    
    def validate(self) -> bool:
        """验证条目的有效性
        
        Returns:
            bool: 如果条目有效返回True，否则返回False
        """
        try:
            # 序列号范围验证
            if self.sequence_start >= self.sequence_end:
                return False
            
            # 保留范围验证
            for start, end in self.keep_ranges:
                if start >= end or start < 0:
                    return False
            
            # 流ID格式验证
            if not self.stream_id or not isinstance(self.stream_id, str):
                return False
                
            return True
        except Exception:
            return False
    
    def merge_keep_ranges(self) -> 'TcpKeepRangeEntry':
        """合并重叠的保留范围，返回新的条目
        
        Returns:
            TcpKeepRangeEntry: 合并后的新条目
        """
        merged_ranges = self._normalize_keep_ranges(self.keep_ranges.copy())
        
        return TcpKeepRangeEntry(
            stream_id=self.stream_id,
            sequence_start=self.sequence_start,
            sequence_end=self.sequence_end,
            keep_ranges=merged_ranges,
            protocol_hint=self.protocol_hint
        )
    
    def get_keep_range_summary(self) -> Dict[str, Any]:
        """获取保留范围摘要信息
        
        Returns:
            Dict[str, Any]: 包含保留范围详细信息的字典
        """
        total_bytes = self.get_total_keep_bytes()
        range_count = len(self.keep_ranges)
        
        # 计算范围密度（保留字节数 / 序列号范围长度）
        seq_length = self.sequence_end - self.sequence_start
        density = total_bytes / seq_length if seq_length > 0 else 0
        
        return {
            'stream_id': self.stream_id,
            'sequence_range': (self.sequence_start, self.sequence_end),
            'sequence_length': seq_length,
            'keep_ranges': self.keep_ranges.copy(),
            'range_count': range_count,
            'total_keep_bytes': total_bytes,
            'keep_density': density,
            'protocol_hint': self.protocol_hint,
            'is_valid': self.validate()
        }


@dataclass
class TcpMaskingResult:
    """TCP掩码处理结果
    
    包含TCP载荷掩码处理过程的详细统计信息和结果。
    """
    success: bool                                     # 处理是否成功
    total_packets: int                                # 总数据包数
    modified_packets: int                             # 修改的数据包数
    bytes_masked: int                                 # 掩码的字节数
    bytes_kept: int                                   # 保留的字节数（新增）
    tcp_streams_processed: int                        # 处理的TCP流数量（强调TCP专用）
    processing_time: float                            # 处理时间（秒）
    error_message: Optional[str] = None               # 错误信息（失败时）
    keep_range_statistics: Dict[str, int] = field(default_factory=dict)  # 保留范围统计
    
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
    
    def get_masking_rate(self) -> float:
        """获取掩码字节比例"""
        total_bytes = self.bytes_masked + self.bytes_kept
        if total_bytes == 0:
            return 0.0
        return self.bytes_masked / total_bytes
    
    def get_keep_rate(self) -> float:
        """获取保留字节比例"""
        total_bytes = self.bytes_masked + self.bytes_kept
        if total_bytes == 0:
            return 0.0
        return self.bytes_kept / total_bytes
    
    def add_keep_range_statistic(self, key: str, value: int) -> None:
        """添加保留范围统计信息"""
        self.keep_range_statistics[key] = value
    
    def get_summary(self) -> str:
        """获取结果摘要"""
        if not self.success:
            return f"TCP载荷掩码处理失败: {self.error_message}"
        
        total_bytes = self.bytes_masked + self.bytes_kept
        return (
            f"TCP载荷掩码处理成功: {self.modified_packets}/{self.total_packets} 个数据包被修改, "
            f"掩码字节: {self.bytes_masked}, 保留字节: {self.bytes_kept} "
            f"(总计 {total_bytes} 字节), "
            f"TCP流: {self.tcp_streams_processed}, "
            f"处理时间: {self.processing_time:.2f}秒, "
            f"处理速度: {self.get_processing_speed():.1f} pps"
        )


class TcpKeepRangeTable:
    """TCP保留范围掩码表
    
    高效管理和查询基于TCP序列号的保留范围条目。
    使用有序列表实现O(log n)的查询性能。
    """
    
    def __init__(self):
        self._entries: List[TcpKeepRangeEntry] = []
        self._stream_index: Dict[str, List[TcpKeepRangeEntry]] = {}
        self.logger = logging.getLogger(__name__)
    
    def add_keep_range_entry(self, entry: TcpKeepRangeEntry) -> None:
        """添加TCP保留范围条目
        
        Args:
            entry: 要添加的保留范围条目
            
        Note:
            条目按序列号起始位置排序，支持高效查询
        """
        # 验证条目有效性
        if not isinstance(entry, TcpKeepRangeEntry):
            raise TypeError("entry必须是TcpKeepRangeEntry类型")
        
        # 添加到总列表
        insort(self._entries, entry, key=lambda x: (x.stream_id, x.sequence_start))
        
        # 添加到按流分组的字典
        if entry.stream_id not in self._stream_index:
            self._stream_index[entry.stream_id] = []
        
        # 在流特定列表中也按序列号排序
        stream_entries = self._stream_index[entry.stream_id]
        insort(stream_entries, entry, key=lambda x: x.sequence_start)
        
        self.logger.debug(
            f"添加TCP保留范围条目: {entry.stream_id} "
            f"[{entry.sequence_start}, {entry.sequence_end}) "
            f"保留范围: {entry.keep_ranges}"
        )
    
    def find_keep_ranges_for_sequence(self, stream_id: str, sequence: int) -> List[Tuple[int, int]]:
        """查找指定TCP序列号位置的保留范围
        
        Args:
            stream_id: TCP流ID
            sequence: 序列号
            
        Returns:
            需要保留的字节范围列表，已合并重叠范围
        """
        if stream_id not in self._stream_index:
            return []
        
        stream_entries = self._stream_index[stream_id]
        all_keep_ranges = []
        
        for entry in stream_entries:
            if entry.covers_sequence(sequence):
                # 调整范围相对于当前序列号的偏移
                offset = sequence - entry.sequence_start
                adjusted_ranges = entry.get_keep_ranges_for_offset(offset)
                all_keep_ranges.extend(adjusted_ranges)
            elif entry.sequence_start > sequence:
                # 由于列表已排序，后续条目不可能匹配
                break
        
        return self._merge_overlapping_ranges(all_keep_ranges)
    
    def _merge_overlapping_ranges(self, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """合并重叠的范围"""
        if not ranges:
            return []
        
        # 按起始位置排序
        sorted_ranges = sorted(ranges)
        merged = [sorted_ranges[0]]
        
        for current_start, current_end in sorted_ranges[1:]:
            last_start, last_end = merged[-1]
            
            # 检查是否重叠或相邻
            if current_start <= last_end:
                # 合并范围
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                # 添加新范围
                merged.append((current_start, current_end))
        
        return merged
    
    def find_entries_for_stream(self, stream_id: str) -> List[TcpKeepRangeEntry]:
        """查找指定TCP流的所有保留范围条目"""
        return self._stream_index.get(stream_id, []).copy()
    
    def find_entries_for_sequence_range(self, stream_id: str, start_seq: int, end_seq: int) -> List[TcpKeepRangeEntry]:
        """查找与指定序列号范围有重叠的保留范围条目
        
        Args:
            stream_id: TCP流ID
            start_seq: 起始序列号
            end_seq: 结束序列号
            
        Returns:
            有重叠的保留范围条目列表
        """
        if stream_id not in self._stream_index:
            return []
        
        stream_entries = self._stream_index[stream_id]
        overlaps = []
        
        for entry in stream_entries:
            # 检查序列号范围是否重叠
            if not (entry.sequence_end <= start_seq or entry.sequence_start >= end_seq):
                overlaps.append(entry)
            elif entry.sequence_start >= end_seq:
                # 后续条目不可能重叠
                break
        
        return overlaps
    
    def get_total_entries(self) -> int:
        """获取总条目数"""
        return len(self._entries)
    
    def get_streams_count(self) -> int:
        """获取TCP流的数量"""
        return len(self._stream_index)
    
    def get_all_stream_ids(self) -> List[str]:
        """获取所有TCP流ID"""
        return list(self._stream_index.keys())
    
    def get_all_entries(self) -> List[TcpKeepRangeEntry]:
        """获取所有保留范围条目
        
        Returns:
            所有保留范围条目的副本列表
        """
        return self._entries.copy()
    
    def clear(self) -> None:
        """清空所有保留范围条目"""
        self._entries.clear()
        self._stream_index.clear()
        self.logger.debug("已清空所有TCP保留范围条目")
    
    def remove_stream(self, stream_id: str) -> int:
        """移除指定TCP流的所有保留范围条目
        
        Args:
            stream_id: 要移除的TCP流ID
            
        Returns:
            移除的条目数量
        """
        if stream_id not in self._stream_index:
            return 0
        
        # 从流字典中移除
        removed_entries = self._stream_index.pop(stream_id)
        removed_count = len(removed_entries)
        
        # 从总列表中移除
        self._entries = [entry for entry in self._entries if entry.stream_id != stream_id]
        
        self.logger.debug(f"移除TCP流 {stream_id} 的 {removed_count} 个保留范围条目")
        return removed_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取保留范围表统计信息"""
        stats = {
            "total_entries": self.get_total_entries(),
            "tcp_streams_count": self.get_streams_count(),
            "entries_per_stream": {},
            "keep_ranges_per_stream": {},
            "sequence_range_coverage": {},
            "protocol_hint_distribution": {}
        }
        
        protocol_hints = {}
        
        for stream_id, entries in self._stream_index.items():
            stats["entries_per_stream"][stream_id] = len(entries)
            
            # 统计保留范围数量
            total_keep_ranges = sum(len(entry.keep_ranges) for entry in entries)
            stats["keep_ranges_per_stream"][stream_id] = total_keep_ranges
            
            # 统计序列号覆盖范围
            if entries:
                min_seq = min(entry.sequence_start for entry in entries)
                max_seq = max(entry.sequence_end for entry in entries)
                stats["sequence_range_coverage"][stream_id] = {
                    "min_sequence": min_seq,
                    "max_sequence": max_seq,
                    "total_range": max_seq - min_seq
                }
                
                # 统计协议提示分布
                for entry in entries:
                    if entry.protocol_hint:
                        protocol_hints[entry.protocol_hint] = protocol_hints.get(entry.protocol_hint, 0) + 1
        
        stats["protocol_hint_distribution"] = protocol_hints
        return stats
    
    def validate_consistency(self) -> List[str]:
        """验证保留范围表的一致性
        
        Returns:
            发现的问题列表，空列表表示无问题
        """
        issues = []
        
        # 检查条目重复
        seen_entries = set()
        for entry in self._entries:
            entry_key = (entry.stream_id, entry.sequence_start, entry.sequence_end, tuple(entry.keep_ranges))
            if entry_key in seen_entries:
                issues.append(f"发现重复条目: {entry_key}")
            seen_entries.add(entry_key)
        
        # 检查流字典一致性
        total_from_streams = sum(len(entries) for entries in self._stream_index.values())
        if total_from_streams != len(self._entries):
            issues.append(f"流字典不一致: 总条目{len(self._entries)} vs 流统计{total_from_streams}")
        
        # 检查TCP流ID格式
        for stream_id in self._stream_index.keys():
            if not stream_id.startswith("TCP_"):
                issues.append(f"非TCP流ID格式: {stream_id}")
        
        # 检查序列号范围重叠（仅警告，因为TCP可能有合理的重叠）
        for stream_id, entries in self._stream_index.items():
            for i in range(len(entries) - 1):
                current = entries[i]
                next_entry = entries[i + 1]
                if current.sequence_end > next_entry.sequence_start:
                    issues.append(
                        f"TCP流 {stream_id} 存在序列号重叠: "
                        f"[{current.sequence_start}, {current.sequence_end}) 与 "
                        f"[{next_entry.sequence_start}, {next_entry.sequence_end}) "
                        "(可能是正常的TCP重组)"
                    )
        
        return issues
    
    def export_to_dict(self) -> Dict[str, Any]:
        """导出保留范围表为字典格式
        
        Returns:
            Dict[str, Any]: 包含所有条目的字典
        """
        return {
            'version': '2.0.0',
            'type': 'TcpKeepRangeTable',
            'entries': [
                {
                    'stream_id': entry.stream_id,
                    'sequence_start': entry.sequence_start,
                    'sequence_end': entry.sequence_end,
                    'keep_ranges': entry.keep_ranges,
                    'protocol_hint': entry.protocol_hint
                }
                for entry in self._entries
            ],
            'statistics': self.get_statistics()
        }
    
    def import_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典格式导入保留范围表
        
        Args:
            data: 包含保留范围条目的字典
            
        Raises:
            ValueError: 数据格式无效时
        """
        if data.get('type') != 'TcpKeepRangeTable':
            raise ValueError(f"数据类型不匹配: 期待TcpKeepRangeTable，得到{data.get('type')}")
        
        # 清空现有数据
        self.clear()
        
        # 导入条目
        entries_data = data.get('entries', [])
        for entry_data in entries_data:
            try:
                entry = TcpKeepRangeEntry(
                    stream_id=entry_data['stream_id'],
                    sequence_start=entry_data['sequence_start'],
                    sequence_end=entry_data['sequence_end'],
                    keep_ranges=entry_data['keep_ranges'],
                    protocol_hint=entry_data.get('protocol_hint')
                )
                self.add_keep_range_entry(entry)
            except (KeyError, ValueError) as e:
                raise ValueError(f"无效的条目数据: {entry_data}, 错误: {e}")
        
        self.logger.info(f"成功导入 {len(entries_data)} 个TCP保留范围条目") 