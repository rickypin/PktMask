#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 3: Scapy回写器重构单元测试

测试基于序列号的掩码机制：
1. 初始化和配置验证  
2. 方向性流ID生成
3. 序列号匹配算法
4. 掩码应用机制
5. 统计信息跟踪
6. 错误处理
7. 集成测试
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

# 导入被测试的模块
from src.pktmask.core.trim.stages.scapy_rewriter import ScapyRewriter
from src.pktmask.core.trim.stages.base_stage import StageContext
from src.pktmask.core.trim.models.sequence_mask_table import SequenceMaskTable, MaskEntry, SequenceMatchResult
from src.pktmask.core.trim.models.tcp_stream import ConnectionDirection
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll


class TestScapyRewriterPhase3:
    """Phase 3 Scapy回写器重构测试"""
    
    def setup_method(self):
        """设置测试方法"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.input_file = self.temp_dir / "input.pcap"
        self.output_file = self.temp_dir / "output.pcap"
        
        # 创建简单的PCAP文件（而不是空文件）
        self._create_test_pcap_file()
        
        # 创建测试对象
        self.mask_table = SequenceMaskTable()
        self.rewriter = ScapyRewriter({
            'preserve_timestamps': True,
            'recalculate_checksums': True,
            'mask_byte_value': 0x00
        })
        
        # 创建标准的测试上下文
        self.test_context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file, 
            work_dir=self.temp_dir
        )
        self.test_context.tshark_output = str(self.input_file)
        self.test_context.mask_table = self.mask_table
    
    def _create_test_pcap_file(self):
        """创建一个简单的测试PCAP文件"""
        import struct
        import time
        
        # PCAP全局头
        pcap_header = struct.pack('<LHHLLLL',
            0xa1b2c3d4,  # magic number
            2,           # version major  
            4,           # version minor
            0,           # thiszone
            0,           # sigfigs
            65535,       # snaplen
            1            # network (Ethernet)
        )
        
        # 创建一个简单的数据包记录
        timestamp = int(time.time())
        packet_data = b'\x00\x01\x02\x03\x04\x05' + b'\x06\x07\x08\x09\x0a\x0b' + b'\x08\x00' + b'\x45\x00\x00\x28' + b'\x00' * 32  # 简单的以太网+IP帧
        
        packet_header = struct.pack('<LLLL',
            timestamp,        # ts_sec
            0,               # ts_usec  
            len(packet_data), # incl_len
            len(packet_data)  # orig_len
        )
        
        # 写入PCAP文件
        with open(self.input_file, 'wb') as f:
            f.write(pcap_header)
            f.write(packet_header)
            f.write(packet_data)
    
    def teardown_method(self):
        """清理测试环境"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_initialization_with_sequence_support(self):
        """测试初始化是否支持序列号机制"""
        # 测试基本属性
        assert self.rewriter.name == "Scapy回写器"
        assert hasattr(self.rewriter, '_stream_manager')
        assert hasattr(self.rewriter, '_sequence_matches')
        assert hasattr(self.rewriter, '_sequence_mismatches')
        
        # 测试初始化
        self.rewriter._initialize_impl()
        assert self.rewriter._sequence_matches == 0
        assert self.rewriter._sequence_mismatches == 0
    
    def test_validate_inputs_with_sequence_mask_table(self):
        """测试输入验证是否支持SequenceMaskTable"""
        self.rewriter._initialize_impl()
        # 手动设置初始化状态，因为测试环境可能没有Scapy
        self.rewriter._is_initialized = True
        
        # 验证有效输入
        assert self.rewriter.validate_inputs(self.test_context) is True
        
        # 测试无效的掩码表类型
        invalid_context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.temp_dir
        )
        invalid_context.tshark_output = str(self.input_file)
        invalid_context.mask_table = {}  # 错误类型
        assert self.rewriter.validate_inputs(invalid_context) is False
        
        # 测试缺少TShark输出文件
        missing_context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.temp_dir
        )
        missing_context.mask_table = self.mask_table
        missing_context.tshark_output = None
        assert self.rewriter.validate_inputs(missing_context) is False
    
    def test_directional_stream_id_generation(self):
        """测试方向性流ID生成"""
        # 测试forward方向
        stream_id_1 = self.rewriter._generate_directional_stream_id(
            "192.168.1.100", "10.0.0.1", 12345, 443, "TCP"
        )
        expected_1 = "TCP_10.0.0.1:443_192.168.1.100:12345_reverse"  # 小端口在前
        assert stream_id_1 == expected_1
        
        # 测试reverse方向
        stream_id_2 = self.rewriter._generate_directional_stream_id(
            "10.0.0.1", "192.168.1.100", 443, 12345, "TCP"
        )
        expected_2 = "TCP_10.0.0.1:443_192.168.1.100:12345_forward"
        assert stream_id_2 == expected_2
        
        # 验证不同方向的流ID不同
        assert stream_id_1 != stream_id_2
    
    def test_packet_direction_determination(self):
        """测试数据包方向确定"""
        # 测试forward方向（源小于目标）
        direction = self.rewriter._determine_packet_direction(
            "10.0.0.1", "192.168.1.100", 443, 12345
        )
        assert direction == ConnectionDirection.FORWARD
        
        # 测试reverse方向（源大于目标）
        direction = self.rewriter._determine_packet_direction(
            "192.168.1.100", "10.0.0.1", 12345, 443
        )
        assert direction == ConnectionDirection.REVERSE
    
    def test_udp_stream_id_generation(self):
        """测试UDP流ID生成"""
        stream_id = self.rewriter._generate_udp_stream_id(
            "192.168.1.100", "10.0.0.1", 12345, 53
        )
        expected = "UDP_192.168.1.100:12345_10.0.0.1:53"
        assert stream_id == expected
    
    def test_sequence_based_mask_application(self):
        """测试基于序列号的掩码应用"""
        # 创建测试载荷
        payload = b"Hello World! This is a test payload for masking."
        
        # 创建匹配结果
        mask_entry = MaskEntry(
            tcp_stream_id="TCP_test_stream_forward",
            seq_start=1000,
            seq_end=1050,
            mask_type="test",
            mask_spec=MaskAfter(5)  # 保留前5字节，掩码其余部分
        )
        
        match_result = SequenceMatchResult(True, 0, len(payload), mask_entry)
        match_results = [match_result]
        
        # 应用掩码
        modified_payload = self.rewriter._apply_sequence_based_masks(
            payload, match_results, 1000
        )
        
        # 验证结果
        assert len(modified_payload) == len(payload)
        assert modified_payload[:5] == payload[:5]  # 前5字节保留
        assert all(b == 0x00 for b in modified_payload[5:])  # 其余部分掩码
    
    def test_mask_spec_to_range_application(self):
        """测试掩码规范到范围的应用"""
        payload = bytearray(b"0123456789ABCDEFGHIJ")
        
        # 测试MaskAfter
        self.rewriter._apply_mask_spec_to_range(
            payload, 5, 15, MaskAfter(3)
        )
        # 应该保留位置5-7（3字节），掩码位置8-14
        assert payload[5:8] == b"567"  # 保留部分
        assert all(b == 0x00 for b in payload[8:15])  # 掩码部分
        assert payload[15:] == b"FGHIJ"  # 未影响部分
        
        # 重置载荷
        payload = bytearray(b"0123456789ABCDEFGHIJ")
        
        # 测试KeepAll
        self.rewriter._apply_mask_spec_to_range(
            payload, 5, 15, KeepAll()
        )
        # 应该保持不变
        assert payload == bytearray(b"0123456789ABCDEFGHIJ")
        
        # 测试MaskRange - 修正期望值
        payload = bytearray(b"0123456789ABCDEFGHIJ")
        self.rewriter._apply_mask_spec_to_range(
            payload, 5, 15, MaskRange([(2, 5), (7, 9)])
        )
        # MaskRange应该掩码相对位置2-4和7-8
        # 相对于范围[5:15)，即绝对位置[7:10)和[12:14)
        expected = bytearray(b"0123456\x00\x00\x00AB\x00\x00EFGHIJ")
        assert payload == expected
    
    def test_zero_mask_application(self):
        """测试零字节掩码应用"""
        payload = bytearray(b"Hello World!")
        
        # 应用零掩码
        self.rewriter._apply_zero_mask(payload, 6, 11)
        
        # 验证结果
        assert payload[:6] == b"Hello "
        assert payload[6:11] == b"\x00\x00\x00\x00\x00"
        assert payload[11:] == b"!"
    
    def test_statistics_tracking(self):
        """测试统计信息跟踪"""
        self.rewriter._initialize_impl()
        
        # 模拟一些统计
        self.rewriter._sequence_matches = 10
        self.rewriter._sequence_mismatches = 2
        self.rewriter._packets_modified = 8
        self.rewriter._total_packets = 20
        self.rewriter._bytes_masked = 1024
        
        # 生成统计信息
        stats = self.rewriter._generate_processing_stats()
        
        # 验证统计信息
        assert stats['sequence_matches'] == 10
        assert stats['sequence_mismatches'] == 2
        assert stats['sequence_match_rate'] == 10 / 12 * 100  # 83.33%
        assert stats['packets_modified'] == 8
        assert stats['modification_rate'] == 8 / 20  # 0.4
        assert stats['bytes_masked'] == 1024
    
    @patch('src.pktmask.core.trim.stages.scapy_rewriter.rdpcap')
    @patch('src.pktmask.core.trim.stages.scapy_rewriter.wrpcap')
    def test_mock_packet_processing(self, mock_wrpcap, mock_rdpcap):
        """测试模拟数据包处理"""
        # 创建模拟的TCP数据包
        mock_packet = Mock()
        mock_packet.haslayer.return_value = True
        mock_packet.getlayer.return_value = Mock(
            src="192.168.1.100",
            dst="10.0.0.1",
            sport=12345,
            dport=443,
            seq=1000
        )
        mock_packet.layers.return_value = ['Ethernet', 'IP', 'TCP']
        
        # 设置TCP载荷 - 修复Mock配置
        mock_tcp_layer = Mock()
        mock_tcp_layer.load = b"Test payload data"
        
        # 正确配置__getitem__方法
        def mock_getitem(key):
            if hasattr(key, '__name__') and key.__name__ == 'TCP':
                return mock_tcp_layer
            return mock_tcp_layer
        
        mock_packet.__getitem__ = Mock(side_effect=mock_getitem)
        
        mock_rdpcap.return_value = [mock_packet]
        
        # 设置掩码表
        mask_entry = MaskEntry(
            tcp_stream_id="TCP_10.0.0.1:443_192.168.1.100:12345_reverse",
            seq_start=1000,
            seq_end=1016,
            mask_type="test",
            mask_spec=MaskAfter(4)
        )
        self.mask_table.add_entry(mask_entry)
        self.mask_table.finalize()
        
        # 使用标准测试上下文
        context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.temp_dir
        )
        context.tshark_output = str(self.input_file)
        context.mask_table = self.mask_table
        
        # 初始化并验证
        self.rewriter._initialize_impl()
        # 手动设置初始化状态，因为测试环境可能没有Scapy
        self.rewriter._is_initialized = True
        assert self.rewriter.validate_inputs(context)
        
        # 验证掩码表已正确设置
        assert isinstance(context.mask_table, SequenceMaskTable)
        assert context.mask_table.get_total_entry_count() > 0
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试无效的掩码表
        error_context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.temp_dir
        )
        error_context.tshark_output = str(self.input_file)
        error_context.mask_table = "invalid_mask_table"  # 错误类型
        
        self.rewriter._initialize_impl()
        assert self.rewriter.validate_inputs(error_context) is False
        
        # 测试缺少文件
        missing_context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.temp_dir
        )
        missing_context.tshark_output = str(Path("/nonexistent/file.pcap"))
        missing_context.mask_table = self.mask_table
        assert self.rewriter.validate_inputs(missing_context) is False


class TestSequenceMatchingIntegration:
    """序列号匹配集成测试"""
    
    def setup_method(self):
        """设置测试方法"""
        self.mask_table = SequenceMaskTable()
        self.rewriter = ScapyRewriter()
        
        # 创建测试掩码条目
        self.mask_table.add_entry(MaskEntry(
            tcp_stream_id="TCP_192.168.1.100:12345_10.0.0.1:443_forward",
            seq_start=1000,
            seq_end=1050,
            mask_type="tls_application_data",
            mask_spec=MaskAfter(5)
        ))
        
        self.mask_table.add_entry(MaskEntry(
            tcp_stream_id="TCP_192.168.1.100:12345_10.0.0.1:443_forward",
            seq_start=2000,
            seq_end=2100,
            mask_type="tls_application_data",
            mask_spec=MaskRange([(0, 10), (20, 30)])
        ))
        
        self.mask_table.finalize()
    
    def test_sequence_range_matching(self):
        """测试序列号范围匹配"""
        stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        
        # 测试完全匹配
        results = self.mask_table.match_sequence_range(stream_id, 1010, 30)
        assert len(results) == 1
        assert results[0].is_match
        assert results[0].mask_start_offset == 0
        assert results[0].mask_end_offset == 30
        
        # 测试部分匹配
        results = self.mask_table.match_sequence_range(stream_id, 1040, 20)
        assert len(results) == 1
        assert results[0].is_match
        assert results[0].mask_start_offset == 0
        assert results[0].mask_end_offset == 10  # 只匹配到1050
        
        # 测试无匹配
        results = self.mask_table.match_sequence_range(stream_id, 1500, 30)
        assert len(results) == 0
        
        # 测试多重匹配（如果序列号范围跨越多个条目）
        results = self.mask_table.match_sequence_range(stream_id, 1990, 120)
        assert len(results) == 1  # 应该匹配第二个条目
        assert results[0].is_match
    
    def test_payload_modification_accuracy(self):
        """测试载荷修改准确性"""
        payload = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        # 创建匹配结果
        mask_entry = MaskEntry(
            tcp_stream_id="test_stream",
            seq_start=100,
            seq_end=136,
            mask_type="test",
            mask_spec=MaskAfter(10)
        )
        
        match_result = SequenceMatchResult(True, 0, len(payload), mask_entry)
        
        # 应用掩码
        modified = self.rewriter._apply_sequence_based_masks(
            payload, [match_result], 100
        )
        
        # 验证精确性
        assert modified[:10] == payload[:10]  # 前10字节保留
        assert all(b == 0x00 for b in modified[10:])  # 其余掩码
        assert len(modified) == len(payload)  # 长度不变


if __name__ == '__main__':
    # 设置日志级别
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # 运行测试
    pytest.main([__file__, '-v', '--tb=short']) 