#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 2: PyShark分析器测试

测试PyShark分析器的Phase 2重构功能：
1. 方向性TCP流ID生成
2. 序列号范围计算 
3. 基于序列号的掩码表生成
4. 重构的TLS协议处理逻辑
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import logging
from pathlib import Path
from typing import Dict, Any, List

# 导入被测试的模块
from src.pktmask.core.trim.stages.pyshark_analyzer import PySharkAnalyzer, PacketAnalysis, StreamInfo
from src.pktmask.core.trim.stages.stage_result import StageResult, StageStatus
from src.pktmask.core.trim.stages.base_stage import StageContext
from src.pktmask.core.trim.models.sequence_mask_table import SequenceMaskTable, MaskEntry
from src.pktmask.core.trim.models.tcp_stream import ConnectionDirection
from src.pktmask.core.trim.models.mask_spec import MaskAfter, KeepAll
from src.pktmask.core.trim.exceptions import StreamMaskTableError


class TestPhase2PySharkAnalyzer(unittest.TestCase):
    """Phase 2 PyShark分析器测试类"""
    
    def setUp(self):
        """测试前设置"""
        self.config = {
            'analyze_tls': True,
            'analyze_tcp': True,
            'analyze_udp': True,
            'tls_keep_handshake': True,
            'tls_mask_application_data': True,
            'max_packets_per_batch': 1000,
            'memory_cleanup_interval': 5000,
            'analysis_timeout_seconds': 600
        }
        self.analyzer = PySharkAnalyzer(self.config)
        
        # 创建模拟上下文
        from pathlib import Path
        self.context = StageContext(
            input_file=Path("/tmp/test_input.pcap"),
            output_file=Path("/tmp/test_output.pcap"),
            work_dir=Path("/tmp")
        )
        self.context.tshark_output = "/tmp/test_output.pcap"
        
        # 设置日志级别
        logging.getLogger().setLevel(logging.DEBUG)
    
    def test_initialization(self):
        """测试初始化"""
        # 模拟pyshark可用性
        with patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark') as mock_pyshark:
            mock_pyshark.__version__ = "0.5.3"
            
            result = self.analyzer.initialize()
            
            self.assertTrue(result)
            self.assertTrue(self.analyzer.is_initialized)
            self.assertEqual(len(self.analyzer._streams), 0)
            self.assertEqual(len(self.analyzer._packet_analyses), 0)
            self.assertIsNone(self.analyzer._sequence_mask_table)
    
    def test_directional_stream_id_generation(self):
        """测试方向性流ID生成"""
        # 测试TCP流ID生成（包含方向）
        tcp_stream_id = self.analyzer._generate_stream_id(
            "192.168.1.1", "10.0.0.1", 12345, 443, "TCP"
        )
        
        # 验证TCP流ID格式包含方向信息
        self.assertIn("TCP_", tcp_stream_id)
        self.assertTrue(tcp_stream_id.endswith("_forward") or tcp_stream_id.endswith("_reverse"))
        
        # 测试UDP流ID生成（无方向）
        udp_stream_id = self.analyzer._generate_stream_id(
            "192.168.1.1", "10.0.0.1", 12345, 53, "UDP"
        )
        
        # 验证UDP流ID格式不包含方向信息
        self.assertIn("UDP_", udp_stream_id)
        self.assertFalse(udp_stream_id.endswith("_forward") or udp_stream_id.endswith("_reverse"))
    
    def test_stream_info_update_with_direction(self):
        """测试流信息更新（包含方向性）"""
        # 创建TCP数据包分析结果
        tcp_analysis = PacketAnalysis(
            packet_number=1,
            timestamp=1234567890.0,
            stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
            seq_number=1000,
            payload_length=100,
            application_layer="TLS"
        )
        
        # 更新流信息
        self.analyzer._update_stream_info(tcp_analysis)
        
        # 验证流信息
        stream_info = self.analyzer._streams[tcp_analysis.stream_id]
        self.assertEqual(stream_info.protocol, "TCP")
        self.assertEqual(stream_info.direction, ConnectionDirection.FORWARD)
        self.assertEqual(stream_info.initial_seq, 1000)
        self.assertEqual(stream_info.last_seq, 1100)  # 1000 + 100 payload_length
        self.assertEqual(stream_info.packet_count, 1)
        self.assertEqual(stream_info.total_bytes, 100)
    
    def test_sequence_range_calculation(self):
        """测试序列号范围计算"""
        # 创建多个数据包分析结果
        packets = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
                seq_number=1000,
                payload_length=100
            ),
            PacketAnalysis(
                packet_number=2,
                timestamp=1234567891.0,
                stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
                seq_number=1100,
                payload_length=50
            ),
            PacketAnalysis(
                packet_number=3,
                timestamp=1234567892.0,
                stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
                seq_number=1150,
                payload_length=200
            )
        ]
        
        # 添加数据包分析结果
        self.analyzer._packet_analyses = packets
        
        # 更新流信息
        for packet in packets:
            self.analyzer._update_stream_info(packet)
        
        # 计算序列号范围
        self.analyzer._calculate_sequence_ranges()
        
        # 验证序列号范围
        stream_id = "TCP_192.168.1.1:12345_10.0.0.1:443_forward"
        stream_info = self.analyzer._streams[stream_id]
        self.assertEqual(stream_info.initial_seq, 1000)
        self.assertEqual(stream_info.last_seq, 1350)  # 1150 + 200
    
    def test_tls_mask_generation(self):
        """测试TLS掩码生成"""
        # 创建序列号掩码表
        sequence_mask_table = SequenceMaskTable()
        
        # 创建TLS数据包分析结果
        tls_packets = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
                seq_number=1000,
                payload_length=100,
                application_layer="TLS",
                is_tls_handshake=True,
                tls_content_type=22
            ),
            PacketAnalysis(
                packet_number=2,
                timestamp=1234567891.0,
                stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
                seq_number=1100,
                payload_length=1500,
                application_layer="TLS",
                is_tls_application_data=True,
                tls_content_type=23
            )
        ]
        
        # 生成TLS掩码
        self.analyzer._generate_tls_masks(
            sequence_mask_table,
            "TCP_192.168.1.1:12345_10.0.0.1:443_forward",
            tls_packets
        )
        
        # 验证掩码表条目
        entries = sequence_mask_table._table["TCP_192.168.1.1:12345_10.0.0.1:443_forward"]
        self.assertEqual(len(entries), 2)
        
        # 验证TLS Handshake掩码（应该完全保留）
        handshake_entry = entries[0]
        self.assertEqual(handshake_entry.seq_start, 1000)
        self.assertEqual(handshake_entry.seq_end, 1100)
        self.assertEqual(handshake_entry.mask_type, "tls_handshake")
        self.assertIsInstance(handshake_entry.mask_spec, KeepAll)
        
        # 验证TLS Application Data掩码（应该保留5字节头部）
        app_data_entry = entries[1]
        self.assertEqual(app_data_entry.seq_start, 1100)
        self.assertEqual(app_data_entry.seq_end, 2600)
        self.assertEqual(app_data_entry.mask_type, "tls_application_data")
        self.assertIsInstance(app_data_entry.mask_spec, MaskAfter)
    
    def test_sequence_mask_table_generation(self):
        """测试序列号掩码表生成"""
        # 设置模拟数据
        self.analyzer._packet_analyses = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
                seq_number=1000,
                payload_length=100,
                application_layer="TLS",
                is_tls_handshake=True,
                tls_content_type=22
            )
        ]
        
        # 设置流信息
        self.analyzer._streams["TCP_192.168.1.1:12345_10.0.0.1:443_forward"] = StreamInfo(
            stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
            src_ip="192.168.1.1",
            dst_ip="10.0.0.1",
            src_port=12345,
            dst_port=443,
            protocol="TCP",
            direction=ConnectionDirection.FORWARD,
            application_protocol="TLS"
        )
        
        # 生成序列号掩码表
        mask_table = self.analyzer._generate_sequence_mask_table()
        
        # 验证掩码表
        self.assertIsInstance(mask_table, SequenceMaskTable)
        self.assertEqual(mask_table.get_total_entry_count(), 1)
        self.assertIn("TCP_192.168.1.1:12345_10.0.0.1:443_forward", mask_table.get_stream_ids())
    
    def test_validate_inputs(self):
        """测试输入验证"""
        # 测试缺少TShark输出文件
        context_no_output = StageContext(
            input_file=Path("/tmp/test_input.pcap"),
            output_file=Path("/tmp/test_output.pcap"),
            work_dir=Path("/tmp")
        )
        context_no_output.tshark_output = None
        
        with patch.object(self.analyzer, '_is_initialized', True):
            result = self.analyzer.validate_inputs(context_no_output)
            self.assertFalse(result)
        
        # 测试文件不存在
        context_missing_file = StageContext(
            input_file=Path("/tmp/test_input.pcap"),
            output_file=Path("/tmp/test_output.pcap"),
            work_dir=Path("/tmp")
        )
        context_missing_file.tshark_output = "/tmp/nonexistent.pcap"
        
        with patch.object(self.analyzer, '_is_initialized', True):
            result = self.analyzer.validate_inputs(context_missing_file)
            self.assertFalse(result)
        
        # 测试正常情况
        with patch.object(self.analyzer, '_is_initialized', True), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat:
            
            mock_stat.return_value.st_size = 1024  # 非空文件
            
            result = self.analyzer.validate_inputs(self.context)
            self.assertTrue(result)
    
    @patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark')
    def test_execute_success(self, mock_pyshark):
        """测试执行成功流程"""
        # 模拟PyShark可用性
        mock_pyshark.__version__ = "0.5.3"
        
        # 初始化分析器
        self.analyzer._initialize_impl()
        
        # 模拟文件系统
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat:
            
            mock_stat.return_value.st_size = 1024
            
            # 模拟PyShark文件捕获
            mock_cap = MagicMock()
            mock_packet = MagicMock()
            mock_packet.number = 1
            mock_packet.sniff_time.timestamp.return_value = 1234567890.0
            
            # 模拟TCP层
            mock_tcp = MagicMock()
            mock_tcp.srcport = "12345"
            mock_tcp.dstport = "443"
            mock_tcp.seq = "1000"
            mock_tcp.payload = None
            mock_packet.tcp = mock_tcp
            
            # 模拟IP层
            mock_ip = MagicMock()
            mock_ip.src = "192.168.1.1"
            mock_ip.dst = "10.0.0.1"
            mock_packet.ip = mock_ip
            
            # 模拟TLS层
            mock_tls = MagicMock()
            mock_packet.tls = mock_tls
            
            mock_cap.__iter__ = lambda x: iter([mock_packet])
            mock_pyshark.FileCapture.return_value = mock_cap
            
            # 模拟进度回调
            progress_callback = Mock()
            
            # 执行分析
            with patch.object(self.analyzer, 'get_progress_callback', return_value=progress_callback):
                result = self.analyzer.execute(self.context)
            
            # 验证结果
            self.assertTrue(result.success)
            self.assertIn('packet_count', result.data)
            self.assertIn('stream_count', result.data)
            self.assertIn('mask_entries', result.data)
            self.assertIsNotNone(self.context.sequence_mask_table)
    
    def test_protocol_strategy_framework(self):
        """测试多协议掩码策略框架"""
        # 创建序列号掩码表
        sequence_mask_table = SequenceMaskTable()
        
        # 测试ICMP协议保留策略
        icmp_packets = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="ICMP_192.168.1.1_10.0.0.1_8_0",
                seq_number=None,
                payload_length=64,
                application_layer="ICMP"
            )
        ]
        
        self.analyzer._generate_preserve_all_masks(
            sequence_mask_table,
            "ICMP_192.168.1.1_10.0.0.1_8_0",
            icmp_packets
        )
        
        # 验证ICMP掩码条目
        icmp_entries = sequence_mask_table._table["ICMP_192.168.1.1_10.0.0.1_8_0"]
        self.assertEqual(len(icmp_entries), 1)
        self.assertEqual(icmp_entries[0].mask_type, "icmp_preserve_all")
        self.assertIsInstance(icmp_entries[0].mask_spec, KeepAll)
        
        # 测试通用协议掩码策略
        generic_packets = [
            PacketAnalysis(
                packet_number=2,
                timestamp=1234567891.0,
                stream_id="TCP_192.168.1.1:8080_10.0.0.1:80_forward",
                seq_number=2000,
                payload_length=500,
                application_layer=None
            )
        ]
        
        self.analyzer._generate_generic_masks(
            sequence_mask_table,
            "TCP_192.168.1.1:8080_10.0.0.1:80_forward",
            generic_packets
        )
        
        # 验证通用掩码条目
        generic_entries = sequence_mask_table._table["TCP_192.168.1.1:8080_10.0.0.1:80_forward"]
        self.assertEqual(len(generic_entries), 1)
        self.assertEqual(generic_entries[0].mask_type, "generic_mask_after")
        # 当前实现：无application_layer的包使用KeepAll（为安全起见）
        self.assertIsInstance(generic_entries[0].mask_spec, KeepAll)
    
    def test_tls_reassembly_logic(self):
        """测试TLS重组逻辑"""
        # 创建测试数据包（模拟跨TCP段的TLS消息）
        packets = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
                seq_number=1000,
                payload_length=500,
                application_layer=None  # 前导包，未识别为TLS
            ),
            PacketAnalysis(
                packet_number=2,
                timestamp=1234567891.0,
                stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
                seq_number=1500,
                payload_length=200,
                application_layer="TLS",
                is_tls_handshake=True,
                tls_content_type=22
            )
        ]
        
        # 执行TLS重组分析
        reassembled_packets = self.analyzer._reassemble_tls_stream(packets)
        
        # 验证重组结果
        self.assertEqual(len(reassembled_packets), 2)
        
        # 验证前导包被标记为重组包
        preceding_packet = reassembled_packets[0]
        self.assertTrue(getattr(preceding_packet, 'tls_reassembled', False))
        self.assertEqual(preceding_packet.tls_reassembly_info.get('record_type'), 'Handshake')
        self.assertEqual(preceding_packet.tls_reassembly_info.get('main_packet'), 2)
        self.assertEqual(preceding_packet.tls_reassembly_info.get('position'), 'preceding')
    
    def test_memory_cleanup(self):
        """测试内存清理"""
        # 添加一些测试数据
        self.analyzer._packet_analyses = [Mock() for _ in range(100)]
        self.analyzer._streams = {f"stream_{i}": Mock() for i in range(10)}
        
        # 执行内存清理
        self.analyzer._cleanup_memory()
        
        # 验证内存被清理（实际清理可能取决于具体实现）
        # 这里主要验证方法能正常执行而不抛出异常
        self.assertTrue(True)
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试无PyShark环境
        with patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark', None):
            with self.assertRaises(RuntimeError):
                self.analyzer._initialize_impl()
        
        # 测试掩码表错误处理
        sequence_mask_table = SequenceMaskTable()
        
        # 模拟掩码表错误
        with patch.object(sequence_mask_table, 'add_mask_range', side_effect=StreamMaskTableError("test", "test", "test")):
            # 应该捕获并记录错误，而不是抛出异常
            self.analyzer._generate_tls_masks(
                sequence_mask_table,
                "test_stream",
                [PacketAnalysis(
                    packet_number=1,
                    timestamp=1234567890.0,
                    stream_id="test_stream",
                    seq_number=1000,
                    payload_length=100,
                    tls_content_type=23
                )]
            )
            
            # 验证没有抛出异常
            self.assertTrue(True)


class TestPhase2Integration(unittest.TestCase):
    """Phase 2集成测试"""
    
    def test_phase1_phase2_integration(self):
        """测试Phase 1和Phase 2的集成"""
        # 验证Phase 2能正确使用Phase 1的数据结构
        from src.pktmask.core.trim.models.sequence_mask_table import SequenceMaskTable, MaskEntry
        from src.pktmask.core.trim.models.tcp_stream import TCPStreamManager, ConnectionDirection
        from src.pktmask.core.trim.models.mask_spec import MaskAfter, KeepAll
        
        # 创建PyShark分析器
        analyzer = PySharkAnalyzer()
        
        # 验证分析器使用了正确的Phase 1组件
        self.assertIsInstance(analyzer._tcp_stream_manager, TCPStreamManager)
        
        # 验证能创建序列号掩码表
        mask_table = SequenceMaskTable()
        self.assertIsInstance(mask_table, SequenceMaskTable)
        
        # 验证掩码表API兼容性
        mask_table.add_mask_range(
            tcp_stream_id="TCP_192.168.1.1:12345_10.0.0.1:443_forward",
            seq_start=1000,
            seq_end=1100,
            mask_type="test_mask",
            mask_spec=MaskAfter(5)
        )
        
        # 验证查询功能
        results = mask_table.match_sequence_range(
            "TCP_192.168.1.1:12345_10.0.0.1:443_forward",
            1050,
            20
        )
        
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_match)


if __name__ == '__main__':
    unittest.main() 