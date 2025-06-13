"""
测试TCP双向流序列号冲突修复
验证PyShark分析器和Scapy回写器正确处理TCP双向流的独立序列号空间
"""

import unittest
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from src.pktmask.core.trim.stages.pyshark_analyzer import PySharkAnalyzer, PacketAnalysis, StreamInfo
from src.pktmask.core.trim.stages.scapy_rewriter import ScapyRewriter
from src.pktmask.core.trim.models.mask_table import StreamMaskTable
from src.pktmask.core.trim.models.mask_spec import KeepAll, MaskAfter


class TestTCPBidirectionalFix(unittest.TestCase):
    """测试TCP双向流序列号冲突修复"""
    
    def setUp(self):
        """设置测试环境"""
        self.analyzer = PySharkAnalyzer()
        self.rewriter = ScapyRewriter()
    
    def test_pyshark_analyzer_directional_stream_id_generation(self):
        """测试PyShark分析器生成方向性流ID"""
        
        # 测试TCP协议 - 应该生成方向性流ID
        stream_id_forward = self.analyzer._generate_stream_id(
            "192.168.1.1", "192.168.1.2", 80, 8080, "TCP"
        )
        stream_id_reverse = self.analyzer._generate_stream_id(
            "192.168.1.2", "192.168.1.1", 8080, 80, "TCP"
        )
        
        # 验证TCP流ID包含方向
        self.assertEqual(stream_id_forward, "TCP_192.168.1.1:80_192.168.1.2:8080_forward")
        self.assertEqual(stream_id_reverse, "TCP_192.168.1.1:80_192.168.1.2:8080_reverse")
        self.assertNotEqual(stream_id_forward, stream_id_reverse)
        
        # 测试UDP协议 - 应该生成无方向流ID
        stream_id_udp1 = self.analyzer._generate_stream_id(
            "192.168.1.1", "192.168.1.2", 53, 5353, "UDP"
        )
        stream_id_udp2 = self.analyzer._generate_stream_id(
            "192.168.1.2", "192.168.1.1", 5353, 53, "UDP"
        )
        
        # 验证UDP流ID相同（无方向）
        self.assertEqual(stream_id_udp1, "UDP_192.168.1.1:53_192.168.1.2:5353")
        self.assertEqual(stream_id_udp2, "UDP_192.168.1.1:53_192.168.1.2:5353")
        self.assertEqual(stream_id_udp1, stream_id_udp2)
    
    def test_mask_table_separate_sequence_spaces(self):
        """测试掩码表正确处理分离的序列号空间"""
        
        # 创建模拟的TCP双向流数据包分析结果
        forward_stream_id = "TCP_192.168.1.1:80_192.168.1.2:8080_forward"
        reverse_stream_id = "TCP_192.168.1.1:80_192.168.1.2:8080_reverse"
        
        # 设置流信息
        self.analyzer._streams = {
            forward_stream_id: StreamInfo(
                stream_id=forward_stream_id,
                src_ip="192.168.1.1", dst_ip="192.168.1.2",
                src_port=80, dst_port=8080,
                protocol="TCP", application_protocol="HTTP"
            ),
            reverse_stream_id: StreamInfo(
                stream_id=reverse_stream_id,
                src_ip="192.168.1.2", dst_ip="192.168.1.1",
                src_port=8080, dst_port=80,
                protocol="TCP", application_protocol="HTTP"
            )
        }
        
        # 设置数据包分析结果 - 两个方向都有重叠的序列号
        self.analyzer._packet_analyses = [
            # Forward方向 - 使用序列号范围 1-300
            PacketAnalysis(
                packet_number=1, timestamp=1234567890.0,
                stream_id=forward_stream_id, seq_number=1, payload_length=100,
                application_layer='HTTP', is_http_request=True, http_header_length=50
            ),
            PacketAnalysis(
                packet_number=3, timestamp=1234567892.0,
                stream_id=forward_stream_id, seq_number=101, payload_length=200,
                application_layer='HTTP', is_http_request=True, http_header_length=80
            ),
            # Reverse方向 - 使用序列号范围 1000-1500，与forward方向完全不重叠
            PacketAnalysis(
                packet_number=2, timestamp=1234567891.0,
                stream_id=reverse_stream_id, seq_number=1000, payload_length=150,
                application_layer='HTTP', is_http_response=True, http_header_length=60
            ),
            PacketAnalysis(
                packet_number=4, timestamp=1234567893.0,
                stream_id=reverse_stream_id, seq_number=1150, payload_length=100,
                application_layer='HTTP', is_http_response=True, http_header_length=40
            )
        ]
        
        # 生成掩码表
        mask_table = self.analyzer._generate_mask_table()
        
        # 验证掩码表中有两个独立的流
        self.assertEqual(len(mask_table.get_stream_ids()), 2)
        self.assertIn(forward_stream_id, mask_table.get_stream_ids())
        self.assertIn(reverse_stream_id, mask_table.get_stream_ids())
        
        # 验证每个流的掩码条目数
        self.assertEqual(mask_table.get_stream_entry_count(forward_stream_id), 2)
        self.assertEqual(mask_table.get_stream_entry_count(reverse_stream_id), 2)
        
        # 验证forward方向的掩码查找
        forward_mask_1 = mask_table.lookup(forward_stream_id, 1, 100)
        self.assertIsNotNone(forward_mask_1)
        self.assertIsInstance(forward_mask_1, MaskAfter)
        self.assertEqual(forward_mask_1.keep_bytes, 50)
        
        forward_mask_2 = mask_table.lookup(forward_stream_id, 101, 200)
        self.assertIsNotNone(forward_mask_2)
        self.assertIsInstance(forward_mask_2, MaskAfter)
        self.assertEqual(forward_mask_2.keep_bytes, 80)
        
        # 验证reverse方向的掩码查找
        reverse_mask_1 = mask_table.lookup(reverse_stream_id, 1000, 150)
        self.assertIsNotNone(reverse_mask_1)
        self.assertIsInstance(reverse_mask_1, MaskAfter)
        self.assertEqual(reverse_mask_1.keep_bytes, 60)
        
        reverse_mask_2 = mask_table.lookup(reverse_stream_id, 1150, 100)
        self.assertIsNotNone(reverse_mask_2)
        self.assertIsInstance(reverse_mask_2, MaskAfter)
        self.assertEqual(reverse_mask_2.keep_bytes, 40)
        
        # 验证跨方向查找不会匹配
        cross_mask = mask_table.lookup(forward_stream_id, 1150, 100)  # 查找reverse的序列号
        self.assertIsNone(cross_mask)  # 应该没有匹配
    
    def test_scapy_rewriter_directional_lookup(self):
        """测试Scapy回写器使用方向性流ID进行掩码查找"""
        
        # 创建掩码表
        mask_table = StreamMaskTable()
        
        # 添加方向性流的掩码条目
        forward_stream_id = "TCP_192.168.1.1:80_192.168.1.2:8080_forward"
        reverse_stream_id = "TCP_192.168.1.1:80_192.168.1.2:8080_reverse"
        
        mask_table.add_mask_range(forward_stream_id, 1, 100, MaskAfter(20))
        mask_table.add_mask_range(reverse_stream_id, 1, 100, MaskAfter(30))
        mask_table.finalize()
        
        # 设置回写器的掩码表
        self.rewriter._mask_table = mask_table
        
        # 测试查找forward方向的掩码
        forward_mask = mask_table.lookup(forward_stream_id, 50, 10)
        self.assertIsNotNone(forward_mask)
        self.assertIsInstance(forward_mask, MaskAfter)
        self.assertEqual(forward_mask.keep_bytes, 20)
        
        # 测试查找reverse方向的掩码
        reverse_mask = mask_table.lookup(reverse_stream_id, 50, 10)
        self.assertIsNotNone(reverse_mask)
        self.assertIsInstance(reverse_mask, MaskAfter)
        self.assertEqual(reverse_mask.keep_bytes, 30)
        
        # 验证方向不同的掩码确实不同
        self.assertNotEqual(forward_mask.keep_bytes, reverse_mask.keep_bytes)
    
    def test_end_to_end_bidirectional_processing(self):
        """测试端到端的双向流处理"""
        
        # 模拟完整的处理流程
        analyzer = PySharkAnalyzer()
        
        # 设置测试数据 - 同一TCP连接的双向数据包
        forward_stream_id = "TCP_10.0.0.1:443_10.0.0.2:12345_forward"
        reverse_stream_id = "TCP_10.0.0.1:443_10.0.0.2:12345_reverse"
        
        analyzer._streams = {
            forward_stream_id: StreamInfo(
                stream_id=forward_stream_id,
                src_ip="10.0.0.1", dst_ip="10.0.0.2",
                src_port=443, dst_port=12345,
                protocol="TCP", application_protocol="TLS"
            ),
            reverse_stream_id: StreamInfo(
                stream_id=reverse_stream_id,
                src_ip="10.0.0.2", dst_ip="10.0.0.1",
                src_port=12345, dst_port=443,
                protocol="TCP", application_protocol="TLS"
            )
        }
        
        analyzer._packet_analyses = [
            # Server -> Client (TLS ApplicationData)
            PacketAnalysis(
                packet_number=1, timestamp=1234567890.0,
                stream_id=forward_stream_id, seq_number=100, payload_length=1024,
                application_layer='TLS', is_tls_application_data=True,
                tls_content_type=23, tls_record_length=1024
            ),
            # Client -> Server (TLS ApplicationData)  
            PacketAnalysis(
                packet_number=2, timestamp=1234567891.0,
                stream_id=reverse_stream_id, seq_number=100, payload_length=512,
                application_layer='TLS', is_tls_application_data=True,
                tls_content_type=23, tls_record_length=512
            )
        ]
        
        # 生成掩码表
        mask_table = analyzer._generate_mask_table()
        
        # 验证结果
        self.assertEqual(len(mask_table.get_stream_ids()), 2)
        
        # 验证每个方向都有独立的掩码条目
        forward_mask = mask_table.lookup(forward_stream_id, 100, 1024)
        reverse_mask = mask_table.lookup(reverse_stream_id, 100, 512)
        
        self.assertIsNotNone(forward_mask)
        self.assertIsNotNone(reverse_mask)
        
        # 验证掩码规范正确（TLS ApplicationData应该保留5字节头）
        self.assertIsInstance(forward_mask, MaskAfter)
        self.assertIsInstance(reverse_mask, MaskAfter)
        self.assertEqual(forward_mask.keep_bytes, 5)
        self.assertEqual(reverse_mask.keep_bytes, 5)


if __name__ == '__main__':
    unittest.main() 