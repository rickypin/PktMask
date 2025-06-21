"""
序列号掩码表单元测试

验证Phase 1重构中序列号范围计算和掩码表CRUD操作的正确性。
"""

import pytest
import logging

from src.pktmask.core.trim.models.sequence_mask_table import (
    MaskEntry,
    SequenceMatchResult,
    SequenceMaskTable
)
from src.pktmask.core.trim.models.mask_spec import MaskAfter, KeepAll, MaskRange
from src.pktmask.core.trim.models.tcp_stream import ConnectionDirection
from src.pktmask.core.trim.exceptions import StreamMaskTableError


class TestMaskEntry:
    """测试掩码条目"""
    
    def test_create_valid_entry(self):
        """测试创建有效的掩码条目"""
        mask_spec = MaskAfter(5)
        entry = MaskEntry(
            tcp_stream_id="TCP_192.168.1.100:12345_10.0.0.1:443_forward",
            seq_start=1000,
            seq_end=1500,
            mask_type="tls_application_data",
            mask_spec=mask_spec
        )
        
        assert entry.tcp_stream_id == "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        assert entry.seq_start == 1000
        assert entry.seq_end == 1500
        assert entry.mask_type == "tls_application_data"
        assert entry.mask_spec == mask_spec
        assert entry.preserve_headers == []
    
    def test_invalid_sequence_numbers(self):
        """测试无效序列号抛出异常"""
        mask_spec = MaskAfter(5)
        
        # 负数序列号
        with pytest.raises(StreamMaskTableError) as exc_info:
            MaskEntry(
                tcp_stream_id="test_stream",
                seq_start=-1,
                seq_end=1000,
                mask_type="test",
                mask_spec=mask_spec
            )
        assert "序列号不能为负数" in str(exc_info.value)
        
        # 起始大于等于结束
        with pytest.raises(StreamMaskTableError) as exc_info:
            MaskEntry(
                tcp_stream_id="test_stream",
                seq_start=1000,
                seq_end=1000,
                mask_type="test",
                mask_spec=mask_spec
            )
        assert "起始序列号必须小于结束序列号" in str(exc_info.value)
    
    def test_overlaps_with(self):
        """测试重叠检测"""
        mask_spec = MaskAfter(5)
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        entry1 = MaskEntry(stream_id, 1000, 1500, "test", mask_spec)
        entry2 = MaskEntry(stream_id, 1200, 1800, "test", mask_spec)  # 重叠
        entry3 = MaskEntry(stream_id, 1500, 2000, "test", mask_spec)  # 不重叠（相邻）
        entry4 = MaskEntry("different_stream", 1200, 1800, "test", mask_spec)  # 不同流
        
        assert entry1.overlaps_with(entry2) is True
        assert entry1.overlaps_with(entry3) is False
        assert entry1.overlaps_with(entry4) is False
    
    def test_contains_range(self):
        """测试范围包含检测"""
        mask_spec = MaskAfter(5)
        entry = MaskEntry("test_stream", 1000, 1500, "test", mask_spec)
        
        assert entry.contains_range(1100, 1400) is True  # 完全包含
        assert entry.contains_range(1000, 1500) is True  # 完全相等
        assert entry.contains_range(900, 1200) is False  # 部分重叠
        assert entry.contains_range(1600, 1800) is False  # 完全不包含
    
    def test_intersects_range(self):
        """测试范围相交检测"""
        mask_spec = MaskAfter(5)
        entry = MaskEntry("test_stream", 1000, 1500, "test", mask_spec)
        
        assert entry.intersects_range(1100, 1400) is True  # 完全包含
        assert entry.intersects_range(900, 1200) is True   # 部分重叠
        assert entry.intersects_range(1400, 1600) is True  # 部分重叠
        assert entry.intersects_range(800, 900) is False   # 完全不相交
        assert entry.intersects_range(1600, 1800) is False # 完全不相交
    
    def test_get_intersection(self):
        """测试获取交集"""
        mask_spec = MaskAfter(5)
        entry = MaskEntry("test_stream", 1000, 1500, "test", mask_spec)
        
        # 完全包含
        assert entry.get_intersection(1100, 1400) == (1100, 1400)
        
        # 部分重叠
        assert entry.get_intersection(900, 1200) == (1000, 1200)
        assert entry.get_intersection(1400, 1600) == (1400, 1500)
        
        # 完全不相交
        assert entry.get_intersection(800, 900) is None
        assert entry.get_intersection(1600, 1800) is None
    
    def test_get_description(self):
        """测试获取描述信息"""
        mask_spec = MaskAfter(5)
        
        # 不带头部保留的条目
        entry1 = MaskEntry("test_stream", 1000, 1500, "tls_data", mask_spec)
        desc1 = entry1.get_description()
        assert "tls_data [1000:1500)" in desc1
        assert "保留头部" not in desc1
        
        # 带头部保留的条目
        entry2 = MaskEntry(
            "test_stream", 1000, 1500, "tls_data", mask_spec,
            preserve_headers=[(0, 5), (20, 25)]
        )
        desc2 = entry2.get_description()
        assert "tls_data [1000:1500)" in desc2
        assert "保留头部: [0:5), [20:25)" in desc2


class TestSequenceMatchResult:
    """测试序列号匹配结果"""
    
    def test_create_match_result(self):
        """测试创建匹配结果"""
        mask_spec = MaskAfter(5)
        entry = MaskEntry("test_stream", 1000, 1500, "test", mask_spec)
        
        result = SequenceMatchResult(
            is_match=True,
            mask_start_offset=10,
            mask_end_offset=50,
            entry=entry
        )
        
        assert result.is_match is True
        assert result.mask_start_offset == 10
        assert result.mask_end_offset == 50
        assert result.entry == entry
        assert result.mask_length == 40
    
    def test_no_match_result(self):
        """测试无匹配结果"""
        result = SequenceMatchResult(is_match=False)
        
        assert result.is_match is False
        assert result.mask_length == 0
        assert result.entry is None


class TestSequenceMaskTable:
    """测试序列号掩码表"""
    
    def test_create_table(self):
        """测试创建掩码表"""
        table = SequenceMaskTable()
        
        assert table.get_total_entry_count() == 0
        assert table.get_stream_ids() == []
        assert table._is_finalized is False
    
    def test_add_entry(self):
        """测试添加条目"""
        table = SequenceMaskTable()
        mask_spec = MaskAfter(5)
        
        entry = MaskEntry(
            "TCP_192.168.1.100:12345_10.0.0.1:443_forward",
            1000, 1500, "tls_data", mask_spec
        )
        
        table.add_entry(entry)
        
        assert table.get_total_entry_count() == 1
        assert table.get_stream_entry_count("TCP_192.168.1.100:12345_10.0.0.1:443_forward") == 1
        assert "TCP_192.168.1.100:12345_10.0.0.1:443_forward" in table.get_stream_ids()
    
    def test_add_mask_range(self):
        """测试添加掩码范围"""
        table = SequenceMaskTable()
        mask_spec = MaskAfter(5)
        
        table.add_mask_range(
            tcp_stream_id="TCP_192.168.1.100:12345_10.0.0.1:443_forward",
            seq_start=1000,
            seq_end=1500,
            mask_type="tls_data",
            mask_spec=mask_spec,
            preserve_headers=[(0, 5)]
        )
        
        assert table.get_total_entry_count() == 1
    
    def test_add_entry_after_finalize(self):
        """测试完成后添加条目应该抛出异常"""
        table = SequenceMaskTable()
        table.finalize()
        
        mask_spec = MaskAfter(5)
        entry = MaskEntry("test_stream", 1000, 1500, "test", mask_spec)
        
        with pytest.raises(StreamMaskTableError) as exc_info:
            table.add_entry(entry)
        assert "表已经完成，不能添加新条目" in str(exc_info.value)
    
    def test_match_sequence_range_no_stream(self):
        """测试匹配不存在的流"""
        table = SequenceMaskTable()
        
        results = table.match_sequence_range("nonexistent_stream", 1000, 100)
        assert results == []
    
    def test_match_sequence_range_basic(self):
        """测试基本的序列号范围匹配"""
        table = SequenceMaskTable()
        mask_spec = MaskAfter(5)
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        # 添加掩码条目
        table.add_mask_range(stream_id, 1000, 1500, "tls_data", mask_spec)
        
        # 测试完全包含的情况
        results = table.match_sequence_range(stream_id, 1100, 200)
        assert len(results) == 1
        assert results[0].is_match is True
        assert results[0].mask_start_offset == 0
        assert results[0].mask_end_offset == 200
        
        # 测试部分重叠的情况
        results = table.match_sequence_range(stream_id, 900, 200)  # 900-1100，与1000-1500重叠100字节
        assert len(results) == 1
        assert results[0].is_match is True
        assert results[0].mask_start_offset == 100  # 1000 - 900
        assert results[0].mask_end_offset == 200
        
        # 测试无重叠的情况
        results = table.match_sequence_range(stream_id, 2000, 100)
        assert len(results) == 0
    
    def test_match_sequence_range_multiple_entries(self):
        """测试匹配多个条目"""
        table = SequenceMaskTable()
        mask_spec1 = MaskAfter(5)
        mask_spec2 = MaskAfter(10)
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        # 添加多个掩码条目
        table.add_mask_range(stream_id, 1000, 1200, "tls_header", mask_spec1)
        table.add_mask_range(stream_id, 1500, 1800, "tls_data", mask_spec2)
        
        # 测试跨多个条目的数据包
        results = table.match_sequence_range(stream_id, 1100, 600)  # 1100-1700，跨两个条目
        assert len(results) == 2
        
        # 第一个匹配：1100-1200 (100字节)
        assert results[0].mask_start_offset == 0
        assert results[0].mask_end_offset == 100
        
        # 第二个匹配：1500-1700 (200字节)
        assert results[1].mask_start_offset == 400  # 1500 - 1100
        assert results[1].mask_end_offset == 600
    
    def test_lookup_masks(self):
        """测试查询掩码规范"""
        table = SequenceMaskTable()
        mask_spec1 = MaskAfter(5)
        mask_spec2 = KeepAll()
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        table.add_mask_range(stream_id, 1000, 1200, "tls_header", mask_spec1)
        table.add_mask_range(stream_id, 1500, 1800, "tls_data", mask_spec2)
        
        # 查询跨多个条目的掩码
        masks = table.lookup_masks(stream_id, 1100, 600)
        assert len(masks) == 2
        assert mask_spec1 in masks
        assert mask_spec2 in masks
    
    def test_finalize_and_merge(self):
        """测试完成和合并操作"""
        table = SequenceMaskTable()
        mask_spec = MaskAfter(5)
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        # 添加相邻的相同类型条目
        table.add_mask_range(stream_id, 1000, 1200, "tls_data", mask_spec)
        table.add_mask_range(stream_id, 1200, 1400, "tls_data", mask_spec)
        table.add_mask_range(stream_id, 1400, 1600, "tls_data", mask_spec)
        
        assert table.get_total_entry_count() == 3
        
        # 完成操作应该合并相邻条目
        table.finalize()
        
        assert table.get_total_entry_count() == 1
        assert table._is_finalized is True
        
        # 验证合并后的范围正确
        coverage = table.get_stream_coverage(stream_id)
        assert coverage == (1000, 1600)
    
    def test_merge_different_types_not_merged(self):
        """测试不同类型的条目不会被合并"""
        table = SequenceMaskTable()
        mask_spec1 = MaskAfter(5)
        mask_spec2 = MaskAfter(10)  # 不同参数
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        table.add_mask_range(stream_id, 1000, 1200, "tls_data", mask_spec1)
        table.add_mask_range(stream_id, 1200, 1400, "tls_data", mask_spec2)
        
        table.finalize()
        
        # 应该保持两个条目，因为掩码规范不同
        assert table.get_total_entry_count() == 2
    
    def test_get_stream_coverage(self):
        """测试获取流覆盖范围"""
        table = SequenceMaskTable()
        mask_spec = MaskAfter(5)
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        # 空流应该返回(0, 0)
        assert table.get_stream_coverage("nonexistent") == (0, 0)
        
        # 添加条目
        table.add_mask_range(stream_id, 1000, 1200, "test1", mask_spec)
        table.add_mask_range(stream_id, 1500, 1800, "test2", mask_spec)
        
        coverage = table.get_stream_coverage(stream_id)
        assert coverage == (1000, 1800)
    
    def test_clear(self):
        """测试清除操作"""
        table = SequenceMaskTable()
        mask_spec = MaskAfter(5)
        
        table.add_mask_range("stream1", 1000, 1200, "test", mask_spec)
        table.add_mask_range("stream2", 2000, 2200, "test", mask_spec)
        table.finalize()
        
        assert table.get_total_entry_count() == 2
        assert table._is_finalized is True
        
        table.clear()
        
        assert table.get_total_entry_count() == 0
        assert table._is_finalized is False
        assert table.get_stream_ids() == []
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        table = SequenceMaskTable()
        mask_spec = MaskAfter(5)
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        # 添加条目并进行查询
        table.add_mask_range(stream_id, 1000, 1200, "test", mask_spec)
        table.match_sequence_range(stream_id, 1100, 50)
        table.finalize()
        
        stats = table.get_statistics()
        
        assert stats['total_entries'] == 1
        assert stats['stream_count'] == 1
        assert stats['entries_added'] == 1
        assert stats['lookups_performed'] == 1
        assert stats['matches_found'] == 1
        assert stats['is_finalized'] is True
    
    def test_export_to_dict(self):
        """测试导出为字典"""
        table = SequenceMaskTable()
        mask_spec = MaskAfter(5)
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        table.add_mask_range(
            stream_id, 1000, 1200, "tls_data", mask_spec, 
            preserve_headers=[(0, 5)]
        )
        table.finalize()
        
        exported = table.export_to_dict()
        
        assert exported['metadata']['type'] == 'SequenceMaskTable'
        assert exported['metadata']['is_finalized'] is True
        assert stream_id in exported['streams']
        
        entry_data = exported['streams'][stream_id][0]
        assert entry_data['seq_start'] == 1000
        assert entry_data['seq_end'] == 1200
        assert entry_data['mask_type'] == "tls_data"
        assert entry_data['preserve_headers'] == [(0, 5)]


class TestComplexScenarios:
    """复杂场景测试"""
    
    def test_tcp_sequence_wraparound_scenario(self):
        """测试TCP序列号回绕场景"""
        table = SequenceMaskTable()
        mask_spec = MaskAfter(5)
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        # 添加接近最大序列号的条目
        max_seq = 4294967295  # 2^32 - 1
        table.add_mask_range(stream_id, max_seq - 100, max_seq, "test", mask_spec)
        
        # 添加回绕后的条目
        table.add_mask_range(stream_id, 0, 100, "test", mask_spec)
        
        # 测试匹配回绕前的数据包
        results = table.match_sequence_range(stream_id, max_seq - 50, 20)
        assert len(results) == 1
        
        # 测试匹配回绕后的数据包
        results = table.match_sequence_range(stream_id, 50, 20)
        assert len(results) == 1
    
    def test_tls_application_data_scenario(self):
        """测试TLS Application Data处理场景"""
        table = SequenceMaskTable()
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        # TLS记录：保留5字节头部，掩码其余载荷
        tls_mask = MaskAfter(5)
        table.add_mask_range(
            stream_id, 1000, 1500, "tls_application_data", tls_mask,
            preserve_headers=[(0, 5)]  # 保留TLS记录头
        )
        
        # 匹配TLS记录
        results = table.match_sequence_range(stream_id, 1000, 500)
        assert len(results) == 1
        assert results[0].entry.mask_type == "tls_application_data"
        assert results[0].entry.preserve_headers == [(0, 5)]
    
    def test_multiple_streams_scenario(self):
        """测试多个流的场景"""
        table = SequenceMaskTable()
        mask_spec = MaskAfter(5)
        
        # 两个不同的TCP流
        stream1 = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        stream2 = "TCP_192.168.1.100:12345_10.0.0.1:443_reverse"
        
        # 每个流添加条目
        table.add_mask_range(stream1, 1000, 1500, "client_data", mask_spec)
        table.add_mask_range(stream2, 2000, 2500, "server_data", mask_spec)
        
        # 验证流隔离
        results1 = table.match_sequence_range(stream1, 1200, 100)
        results2 = table.match_sequence_range(stream2, 2200, 100)
        
        assert len(results1) == 1
        assert len(results2) == 1
        assert results1[0].entry.mask_type == "client_data"
        assert results2[0].entry.mask_type == "server_data"
        
        # 跨流查询应该无匹配
        results_cross = table.match_sequence_range(stream1, 2200, 100)
        assert len(results_cross) == 0


if __name__ == "__main__":
    # 配置日志以便调试
    logging.basicConfig(level=logging.DEBUG)
    
    # 运行测试
    pytest.main([__file__, "-v"]) 