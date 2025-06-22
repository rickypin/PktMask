"""
独立PCAP掩码处理器 - Phase 1基础架构测试

测试核心数据结构、配置管理和基础API框架。
"""

import pytest
import logging
from pathlib import Path
import tempfile
import json

from src.pktmask.core.independent_pcap_masker import (
    IndependentPcapMasker,
    MaskEntry,
    MaskingResult,
    SequenceMaskTable,
    IndependentMaskerError,
    ValidationError,
    ConfigurationError
)


class TestMaskEntry:
    """测试MaskEntry数据结构"""
    
    def test_mask_entry_creation_valid(self):
        """测试创建有效的掩码条目"""
        entry = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        assert entry.stream_id == "TCP_1.2.3.4:443_5.6.7.8:1234_forward"
        assert entry.sequence_start == 1000
        assert entry.sequence_end == 2000
        assert entry.mask_type == "mask_after"
        assert entry.mask_params == {"keep_bytes": 5}
        assert entry.preserve_headers is None
    
    def test_mask_entry_creation_with_headers(self):
        """测试创建带头部保留的掩码条目"""
        entry = MaskEntry(
            stream_id="TCP_1.2.3.4:80_5.6.7.8:1234_forward",
            sequence_start=500,
            sequence_end=1500,
            mask_type="mask_range",
            mask_params={"ranges": [(100, 500)]},
            preserve_headers=[(0, 20), (40, 60)]
        )
        
        assert entry.preserve_headers == [(0, 20), (40, 60)]
    
    def test_mask_entry_invalid_sequence_range(self):
        """测试无效的序列号范围"""
        with pytest.raises(ValueError, match="序列号范围无效"):
            MaskEntry(
                stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
                sequence_start=2000,
                sequence_end=1000,  # end < start
                mask_type="mask_after",
                mask_params={"keep_bytes": 5}
            )
    
    def test_mask_entry_invalid_mask_type(self):
        """测试无效的掩码类型"""
        with pytest.raises(ValueError, match="不支持的掩码类型"):
            MaskEntry(
                stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
                sequence_start=1000,
                sequence_end=2000,
                mask_type="invalid_type",
                mask_params={}
            )
    
    def test_mask_entry_missing_params(self):
        """测试缺少必要参数"""
        with pytest.raises(ValueError, match="mask_after类型需要keep_bytes参数"):
            MaskEntry(
                stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
                sequence_start=1000,
                sequence_end=2000,
                mask_type="mask_after",
                mask_params={}  # 缺少keep_bytes
            )
    
    def test_covers_sequence(self):
        """测试序列号覆盖检查"""
        entry = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        assert entry.covers_sequence(1000) == True  # 起始位置
        assert entry.covers_sequence(1500) == True  # 中间位置
        assert entry.covers_sequence(1999) == True  # 结束前一位
        assert entry.covers_sequence(2000) == False  # 结束位置（不包含）
        assert entry.covers_sequence(999) == False   # 起始前
        assert entry.covers_sequence(2001) == False  # 结束后
    
    def test_get_overlap_length(self):
        """测试重叠长度计算"""
        entry = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        # 完全包含
        assert entry.get_overlap_length(1200, 1800) == 600
        
        # 部分重叠
        assert entry.get_overlap_length(1500, 2500) == 500
        assert entry.get_overlap_length(500, 1500) == 500
        
        # 无重叠
        assert entry.get_overlap_length(2000, 3000) == 0
        assert entry.get_overlap_length(0, 1000) == 0
        
        # 完全覆盖
        assert entry.get_overlap_length(500, 2500) == 1000


class TestMaskingResult:
    """测试MaskingResult数据结构"""
    
    def test_masking_result_creation(self):
        """测试创建掩码结果"""
        result = MaskingResult(
            success=True,
            total_packets=100,
            modified_packets=80,
            bytes_masked=1024,
            processing_time=2.5,
            streams_processed=5
        )
        
        assert result.success == True
        assert result.total_packets == 100
        assert result.modified_packets == 80
        assert result.bytes_masked == 1024
        assert result.processing_time == 2.5
        assert result.streams_processed == 5
        assert result.error_message is None
        assert result.statistics == {}
    
    def test_modification_rate(self):
        """测试修改率计算"""
        result = MaskingResult(
            success=True,
            total_packets=100,
            modified_packets=80,
            bytes_masked=1024,
            processing_time=2.5,
            streams_processed=5
        )
        
        assert result.get_modification_rate() == 0.8
        
        # 测试零包情况
        result_zero = MaskingResult(
            success=True,
            total_packets=0,
            modified_packets=0,
            bytes_masked=0,
            processing_time=0.0,
            streams_processed=0
        )
        assert result_zero.get_modification_rate() == 0.0
    
    def test_processing_speed(self):
        """测试处理速度计算"""
        result = MaskingResult(
            success=True,
            total_packets=1000,
            modified_packets=800,
            bytes_masked=1024,
            processing_time=2.0,
            streams_processed=5
        )
        
        assert result.get_processing_speed() == 500.0  # 1000/2.0
        
        # 测试零时间情况
        result_zero_time = MaskingResult(
            success=True,
            total_packets=1000,
            modified_packets=800,
            bytes_masked=1024,
            processing_time=0.0,
            streams_processed=5
        )
        assert result_zero_time.get_processing_speed() == 0.0
    
    def test_add_statistic(self):
        """测试添加统计信息"""
        result = MaskingResult(
            success=True,
            total_packets=100,
            modified_packets=80,
            bytes_masked=1024,
            processing_time=2.5,
            streams_processed=5
        )
        
        result.add_statistic("test_key", "test_value")
        assert result.statistics["test_key"] == "test_value"
        
        result.add_statistic("number_key", 42)
        assert result.statistics["number_key"] == 42
    
    def test_get_summary_success(self):
        """测试成功结果摘要"""
        result = MaskingResult(
            success=True,
            total_packets=1000,
            modified_packets=800,
            bytes_masked=2048,
            processing_time=4.0,
            streams_processed=5
        )
        
        summary = result.get_summary()
        assert "处理成功" in summary
        assert "800/1000" in summary
        assert "2048" in summary
        assert "4.00秒" in summary
        assert "250.0 pps" in summary
    
    def test_get_summary_failure(self):
        """测试失败结果摘要"""
        result = MaskingResult(
            success=False,
            total_packets=0,
            modified_packets=0,
            bytes_masked=0,
            processing_time=0.0,
            streams_processed=0,
            error_message="测试错误信息"
        )
        
        summary = result.get_summary()
        assert "处理失败" in summary
        assert "测试错误信息" in summary


class TestSequenceMaskTable:
    """测试SequenceMaskTable数据结构"""
    
    def test_mask_table_creation(self):
        """测试创建掩码表"""
        table = SequenceMaskTable()
        assert table.get_total_entries() == 0
        assert table.get_streams_count() == 0
        assert table.get_all_stream_ids() == []
    
    def test_add_entry(self):
        """测试添加条目"""
        table = SequenceMaskTable()
        
        entry1 = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        table.add_entry(entry1)
        assert table.get_total_entries() == 1
        assert table.get_streams_count() == 1
        assert "TCP_1.2.3.4:443_5.6.7.8:1234_forward" in table.get_all_stream_ids()
    
    def test_add_entry_invalid_type(self):
        """测试添加无效类型条目"""
        table = SequenceMaskTable()
        
        with pytest.raises(TypeError, match="entry必须是MaskEntry类型"):
            table.add_entry("invalid_entry")
    
    def test_find_matches(self):
        """测试查找匹配条目"""
        table = SequenceMaskTable()
        
        # 添加测试条目
        entry1 = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        entry2 = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1500,
            sequence_end=2500,
            mask_type="mask_range",
            mask_params={"ranges": [(0, 100)]}
        )
        
        table.add_entry(entry1)
        table.add_entry(entry2)
        
        # 测试查找
        matches = table.find_matches("TCP_1.2.3.4:443_5.6.7.8:1234_forward", 1800)
        assert len(matches) == 2  # 两个条目都匹配
        
        matches = table.find_matches("TCP_1.2.3.4:443_5.6.7.8:1234_forward", 1200)
        assert len(matches) == 1  # 只有第一个条目匹配
        
        matches = table.find_matches("TCP_1.2.3.4:443_5.6.7.8:1234_forward", 3000)
        assert len(matches) == 0  # 没有条目匹配
        
        matches = table.find_matches("non_existent_stream", 1500)
        assert len(matches) == 0  # 流不存在
    
    def test_find_range_overlaps(self):
        """测试查找范围重叠"""
        table = SequenceMaskTable()
        
        entry = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        table.add_entry(entry)
        
        # 测试重叠查找
        overlaps = table.find_range_overlaps("TCP_1.2.3.4:443_5.6.7.8:1234_forward", 1500, 2500)
        assert len(overlaps) == 1
        
        overlaps = table.find_range_overlaps("TCP_1.2.3.4:443_5.6.7.8:1234_forward", 2000, 3000)
        assert len(overlaps) == 0  # 无重叠
        
        overlaps = table.find_range_overlaps("non_existent_stream", 1500, 2500)
        assert len(overlaps) == 0  # 流不存在
    
    def test_get_stream_entries(self):
        """测试获取流条目"""
        table = SequenceMaskTable()
        
        entry1 = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        entry2 = MaskEntry(
            stream_id="TCP_5.6.7.8:80_1.2.3.4:5678_forward",
            sequence_start=500,
            sequence_end=1500,
            mask_type="mask_range",
            mask_params={"ranges": [(0, 100)]}
        )
        
        table.add_entry(entry1)
        table.add_entry(entry2)
        
        # 测试获取特定流的条目
        stream1_entries = table.get_stream_entries("TCP_1.2.3.4:443_5.6.7.8:1234_forward")
        assert len(stream1_entries) == 1
        assert stream1_entries[0] == entry1
        
        stream2_entries = table.get_stream_entries("TCP_5.6.7.8:80_1.2.3.4:5678_forward")
        assert len(stream2_entries) == 1
        assert stream2_entries[0] == entry2
        
        non_existent_entries = table.get_stream_entries("non_existent_stream")
        assert len(non_existent_entries) == 0
    
    def test_remove_stream(self):
        """测试移除流"""
        table = SequenceMaskTable()
        
        entry1 = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        entry2 = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=2000,
            sequence_end=3000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        table.add_entry(entry1)
        table.add_entry(entry2)
        
        # 验证初始状态
        assert table.get_total_entries() == 2
        assert table.get_streams_count() == 1
        
        # 移除流
        removed_count = table.remove_stream("TCP_1.2.3.4:443_5.6.7.8:1234_forward")
        assert removed_count == 2
        assert table.get_total_entries() == 0
        assert table.get_streams_count() == 0
        
        # 移除不存在的流
        removed_count = table.remove_stream("non_existent_stream")
        assert removed_count == 0
    
    def test_clear(self):
        """测试清空表"""
        table = SequenceMaskTable()
        
        entry = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        table.add_entry(entry)
        assert table.get_total_entries() == 1
        
        table.clear()
        assert table.get_total_entries() == 0
        assert table.get_streams_count() == 0
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        table = SequenceMaskTable()
        
        # 空表统计
        stats = table.get_statistics()
        assert stats["total_entries"] == 0
        assert stats["streams_count"] == 0
        
        # 添加条目后的统计
        entry1 = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=3000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        entry2 = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=3000,
            sequence_end=5000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        table.add_entry(entry1)
        table.add_entry(entry2)
        
        stats = table.get_statistics()
        assert stats["total_entries"] == 2
        assert stats["streams_count"] == 1
        assert stats["entries_per_stream"]["TCP_1.2.3.4:443_5.6.7.8:1234_forward"] == 2
        
        # 检查序列号范围覆盖
        stream_coverage = stats["sequence_range_coverage"]["TCP_1.2.3.4:443_5.6.7.8:1234_forward"]
        assert stream_coverage["min_sequence"] == 1000
        assert stream_coverage["max_sequence"] == 5000
        assert stream_coverage["total_range"] == 4000
    
    def test_validate_consistency(self):
        """测试一致性验证"""
        table = SequenceMaskTable()
        
        # 空表应该无问题
        issues = table.validate_consistency()
        assert len(issues) == 0
        
        # 添加重叠条目
        entry1 = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        entry2 = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1500,  # 与entry1重叠
            sequence_end=2500,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        table.add_entry(entry1)
        table.add_entry(entry2)
        
        issues = table.validate_consistency()
        assert len(issues) > 0
        assert any("序列号重叠" in issue for issue in issues)


class TestIndependentPcapMaskerBasic:
    """测试IndependentPcapMasker基础功能"""
    
    def test_masker_creation_default_config(self):
        """测试使用默认配置创建处理器"""
        masker = IndependentPcapMasker()
        
        # 验证基础属性
        assert masker.config_manager is not None
        assert masker.logger is not None
        assert hasattr(masker, '_binding_lock')
        assert hasattr(masker, 'protocol_controller')
        assert hasattr(masker, '_processing_stats')
        
        # 验证初始状态
        assert masker.protocol_controller.is_protocol_parsing_disabled() == False
        assert masker._processing_stats['total_files_processed'] == 0
    
    def test_masker_creation_custom_config(self):
        """测试使用自定义配置创建处理器"""
        custom_config = {
            'mask_byte_value': 0xFF,
            'batch_size': 500,
            'log_level': 'DEBUG'
        }
        
        masker = IndependentPcapMasker(custom_config)
        
        # 验证配置应用
        assert masker.config_manager.get('mask_byte_value') == 0xFF
        assert masker.config_manager.get('batch_size') == 500
        assert masker.config_manager.get('log_level') == 'DEBUG'
    
    def test_masker_invalid_config(self):
        """测试无效配置"""
        invalid_config = {
            'mask_byte_value': 300,  # 超出0-255范围
            'batch_size': -1         # 负值
        }
        
        with pytest.raises(ConfigurationError):
            IndependentPcapMasker(invalid_config)
    
    def test_get_global_statistics(self):
        """测试获取全局统计信息"""
        masker = IndependentPcapMasker()
        
        stats = masker.get_global_statistics()
        assert 'total_files_processed' in stats
        assert 'total_packets_processed' in stats
        assert 'total_packets_modified' in stats
        assert 'total_bytes_masked' in stats
        assert 'total_processing_time' in stats
        
        # 初始值应该为0
        assert stats['total_files_processed'] == 0
        assert stats['total_packets_processed'] == 0
    
    def test_reset_statistics(self):
        """测试重置统计信息"""
        masker = IndependentPcapMasker()
        
        # 手动设置一些统计值
        masker._processing_stats['total_files_processed'] = 5
        masker._processing_stats['total_packets_processed'] = 1000
        
        # 验证值已设置
        stats = masker.get_global_statistics()
        assert stats['total_files_processed'] == 5
        assert stats['total_packets_processed'] == 1000
        
        # 重置并验证
        masker.reset_statistics()
        stats = masker.get_global_statistics()
        assert stats['total_files_processed'] == 0
        assert stats['total_packets_processed'] == 0
    
    def test_update_config(self):
        """测试更新配置"""
        masker = IndependentPcapMasker()
        
        original_batch_size = masker.config_manager.get('batch_size')
        
        masker.update_config({'batch_size': 2000})
        
        assert masker.config_manager.get('batch_size') == 2000
        assert masker.config_manager.get('batch_size') != original_batch_size
    
    def test_context_manager(self):
        """测试上下文管理器"""
        with IndependentPcapMasker() as masker:
            assert masker is not None
            assert isinstance(masker, IndependentPcapMasker)
    
    def test_repr(self):
        """测试字符串表示"""
        masker = IndependentPcapMasker()
        repr_str = repr(masker)
        
        assert "IndependentPcapMasker" in repr_str
        assert "files_processed" in repr_str
        assert "packets_processed" in repr_str


class TestInputValidation:
    """测试输入验证功能"""
    
    def setup_method(self):
        """设置测试"""
        self.masker = IndependentPcapMasker()
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # 创建一个虚拟的PCAP文件
        self.test_pcap = self.temp_dir / "test.pcap"
        self.test_pcap.write_bytes(b"dummy pcap content")
        
        # 创建掩码表
        self.mask_table = SequenceMaskTable()
        entry = MaskEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        self.mask_table.add_entry(entry)
    
    def teardown_method(self):
        """清理测试"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validate_inputs_success(self):
        """测试成功的输入验证"""
        output_pcap = str(self.temp_dir / "output.pcap")
        
        # 应该不抛出异常
        self.masker._validate_inputs(str(self.test_pcap), self.mask_table, output_pcap)
    
    def test_validate_inputs_missing_file(self):
        """测试文件不存在"""
        non_existent_file = str(self.temp_dir / "non_existent.pcap")
        output_pcap = str(self.temp_dir / "output.pcap")
        
        with pytest.raises(ValidationError, match="输入文件不存在"):
            self.masker._validate_inputs(non_existent_file, self.mask_table, output_pcap)
    
    def test_validate_inputs_unsupported_format(self):
        """测试不支持的文件格式"""
        unsupported_file = self.temp_dir / "test.txt"
        unsupported_file.write_text("dummy content")
        output_pcap = str(self.temp_dir / "output.pcap")
        
        with pytest.raises(ValidationError, match="不支持的文件格式"):
            self.masker._validate_inputs(str(unsupported_file), self.mask_table, output_pcap)
    
    def test_validate_inputs_invalid_mask_table_type(self):
        """测试无效的掩码表类型"""
        output_pcap = str(self.temp_dir / "output.pcap")
        
        with pytest.raises(ValidationError, match="mask_table必须是SequenceMaskTable类型"):
            self.masker._validate_inputs(str(self.test_pcap), "invalid_table", output_pcap)
    
    def test_validate_inputs_empty_mask_table(self):
        """测试空掩码表"""
        empty_table = SequenceMaskTable()
        output_pcap = str(self.temp_dir / "output.pcap")
        
        with pytest.raises(ValidationError, match="掩码表为空"):
            self.masker._validate_inputs(str(self.test_pcap), empty_table, output_pcap)
    
    def test_validate_inputs_output_is_directory(self):
        """测试输出路径是目录"""
        output_dir = self.temp_dir / "output_dir"
        output_dir.mkdir()
        
        with pytest.raises(ValidationError, match="输出路径是目录"):
            self.masker._validate_inputs(str(self.test_pcap), self.mask_table, str(output_dir))


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"]) 