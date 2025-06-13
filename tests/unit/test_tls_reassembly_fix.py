"""
测试TLS跨TCP段重组功能的修复

验证PyShark分析器能够正确识别和处理跨TCP段的TLS消息，
确保所有相关的TCP段都被标记为需要保留的TLS内容。
"""

import unittest
from unittest.mock import Mock, patch
import logging
from pathlib import Path
from typing import List

from pktmask.core.trim.stages.pyshark_analyzer import PySharkAnalyzer, PacketAnalysis
from pktmask.core.trim.stages.base_stage import StageContext
from pktmask.core.trim.models.mask_table import StreamMaskTable


class TestTLSReassemblyFix(unittest.TestCase):
    """测试TLS跨TCP段重组功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.analyzer = PySharkAnalyzer()
        # 设置日志级别为DEBUG以便观察详细信息
        logging.basicConfig(level=logging.DEBUG)
        
    def test_tls_handshake_across_tcp_segments(self):
        """测试跨TCP段的TLS Handshake识别"""
        
        # 模拟包6和包7的场景
        packets = [
            PacketAnalysis(
                packet_number=6,
                timestamp=1234567890.0,
                stream_id="TCP_8.178.236.80:33492_8.49.51.161:443_reverse",
                seq_number=1,  # 序列号1，载荷长度1342
                payload_length=1342,
                application_layer=None,  # 未被PyShark识别为TLS
                is_tls_handshake=False,
                is_tls_application_data=False,
                is_tls_change_cipher_spec=False,
                is_tls_alert=False,
                is_tls_heartbeat=False,
                tls_content_type=None
            ),
            PacketAnalysis(
                packet_number=7,
                timestamp=1234567890.1,
                stream_id="TCP_8.178.236.80:33492_8.49.51.161:443_reverse",
                seq_number=1343,  # 序列号1343，载荷长度471
                payload_length=471,
                application_layer='TLS',
                is_tls_handshake=True,  # 被PyShark识别为TLS Handshake
                is_tls_application_data=False,
                is_tls_change_cipher_spec=False,
                is_tls_alert=False,
                is_tls_heartbeat=False,
                tls_content_type=22  # Handshake
            )
        ]
        
        # 调用TLS流重组方法
        enhanced_packets = self.analyzer._reassemble_tls_stream(packets)
        
        # 验证结果
        self.assertEqual(len(enhanced_packets), 2, "应该有2个增强的数据包")
        
        # 找到包6和包7
        packet_6 = next(p for p in enhanced_packets if p.packet_number == 6)
        packet_7 = next(p for p in enhanced_packets if p.packet_number == 7)
        
        # 验证包6被标记为TLS重组包
        self.assertTrue(hasattr(packet_6, 'tls_reassembled'), "包6应该有tls_reassembled属性")
        self.assertTrue(packet_6.tls_reassembled, "包6应该被标记为TLS重组包")
        
        # 验证重组信息
        self.assertTrue(hasattr(packet_6, 'tls_reassembly_info'), "包6应该有重组信息")
        self.assertEqual(packet_6.tls_reassembly_info['record_type'], 'Handshake', "应该标记为Handshake类型")
        self.assertEqual(packet_6.tls_reassembly_info['main_packet'], 7, "应该指向主包7")
        self.assertEqual(packet_6.tls_reassembly_info['position'], 'preceding', "应该标记为前导包")
        
        # 验证包7保持原样
        self.assertTrue(packet_7.is_tls_handshake, "包7应该保持为TLS Handshake")
        self.assertFalse(hasattr(packet_7, 'tls_reassembled') and packet_7.tls_reassembled, "包7不应该被标记为重组包")
        
    def test_generate_masks_with_reassembly(self):
        """测试生成掩码时包含重组包"""
        
        # 创建掩码表
        mask_table = StreamMaskTable()
        stream_id = "TCP_8.178.236.80:33492_8.49.51.161:443_reverse"
        
        # 模拟包6和包7的场景
        packets = [
            PacketAnalysis(
                packet_number=6,
                timestamp=1234567890.0,
                stream_id=stream_id,
                seq_number=1,
                payload_length=1342,
                application_layer=None,
                is_tls_handshake=False,
                is_tls_application_data=False,
                is_tls_change_cipher_spec=False,
                is_tls_alert=False,
                is_tls_heartbeat=False,
                tls_content_type=None
            ),
            PacketAnalysis(
                packet_number=7,
                timestamp=1234567890.1,
                stream_id=stream_id,
                seq_number=1343,
                payload_length=471,
                application_layer='TLS',
                is_tls_handshake=True,
                is_tls_application_data=False,
                is_tls_change_cipher_spec=False,
                is_tls_alert=False,
                is_tls_heartbeat=False,
                tls_content_type=22
            )
        ]
        
        # 调用生成掩码方法
        self.analyzer._generate_tls_masks(mask_table, stream_id, packets)
        
        # 验证掩码表统计信息
        stats = mask_table.get_statistics()
        
        # 应该有1个流，2个条目
        self.assertEqual(stats['total_streams'], 1, "应该有1个流")
        self.assertEqual(stats['total_entries'], 2, "应该有2个掩码条目")
        
        # 验证流的条目数量
        self.assertEqual(mask_table.get_stream_entry_count(stream_id), 2, "该流应该有2个掩码条目")
        
        # 验证序列号覆盖范围
        coverage = mask_table.get_stream_coverage(stream_id)
        self.assertEqual(coverage, (1, 1814), "应该覆盖序列号范围[1:1814)")
        
        # 验证具体的掩码查找功能
        # 检查包6的掩码
        mask_spec_6 = mask_table.lookup(stream_id, 1, 1342)
        self.assertIsNotNone(mask_spec_6, "包6应该有掩码")
        self.assertEqual(mask_spec_6.__class__.__name__, 'KeepAll', "包6应该完全保留")
        
        # 检查包7的掩码
        mask_spec_7 = mask_table.lookup(stream_id, 1343, 471)
        self.assertIsNotNone(mask_spec_7, "包7应该有掩码")
        self.assertEqual(mask_spec_7.__class__.__name__, 'KeepAll', "包7应该完全保留")
            
    def test_non_contiguous_packets_not_reassembled(self):
        """测试非连续的数据包不会被错误重组"""
        
        # 模拟序列号不连续的包
        packets = [
            PacketAnalysis(
                packet_number=5,
                timestamp=1234567889.9,
                stream_id="TCP_8.178.236.80:33492_8.49.51.161:443_reverse",
                seq_number=1,
                payload_length=100,
                application_layer=None,
                is_tls_handshake=False,
                is_tls_application_data=False,
                is_tls_change_cipher_spec=False,
                is_tls_alert=False,
                is_tls_heartbeat=False,
                tls_content_type=None
            ),
            PacketAnalysis(
                packet_number=7,
                timestamp=1234567890.1,
                stream_id="TCP_8.178.236.80:33492_8.49.51.161:443_reverse",
                seq_number=200,  # 序列号不连续
                payload_length=471,
                application_layer='TLS',
                is_tls_handshake=True,
                is_tls_application_data=False,
                is_tls_change_cipher_spec=False,
                is_tls_alert=False,
                is_tls_heartbeat=False,
                tls_content_type=22
            )
        ]
        
        # 调用TLS流重组方法
        enhanced_packets = self.analyzer._reassemble_tls_stream(packets)
        
        # 验证包5不被标记为重组包
        packet_5 = next(p for p in enhanced_packets if p.packet_number == 5)
        self.assertFalse(hasattr(packet_5, 'tls_reassembled') and packet_5.tls_reassembled, 
                        "序列号不连续的包5不应该被标记为重组包")
        
    def test_multiple_preceding_packets(self):
        """测试多个前导包的情况"""
        
        # 模拟一个大TLS消息分成3个TCP段的情况
        packets = [
            PacketAnalysis(
                packet_number=5,
                timestamp=1234567889.8,
                stream_id="TCP_8.178.236.80:33492_8.49.51.161:443_reverse",
                seq_number=1,
                payload_length=1000,
                application_layer=None,
                is_tls_handshake=False,
                is_tls_application_data=False,
                is_tls_change_cipher_spec=False,
                is_tls_alert=False,
                is_tls_heartbeat=False,
                tls_content_type=None
            ),
            PacketAnalysis(
                packet_number=6,
                timestamp=1234567889.9,
                stream_id="TCP_8.178.236.80:33492_8.49.51.161:443_reverse",
                seq_number=1001,
                payload_length=1000,
                application_layer=None,
                is_tls_handshake=False,
                is_tls_application_data=False,
                is_tls_change_cipher_spec=False,
                is_tls_alert=False,
                is_tls_heartbeat=False,
                tls_content_type=None
            ),
            PacketAnalysis(
                packet_number=7,
                timestamp=1234567890.0,
                stream_id="TCP_8.178.236.80:33492_8.49.51.161:443_reverse",
                seq_number=2001,
                payload_length=500,
                application_layer='TLS',
                is_tls_handshake=True,
                is_tls_application_data=False,
                is_tls_change_cipher_spec=False,
                is_tls_alert=False,
                is_tls_heartbeat=False,
                tls_content_type=22
            )
        ]
        
        # 调用TLS流重组方法
        enhanced_packets = self.analyzer._reassemble_tls_stream(packets)
        
        # 验证所有前导包都被标记
        packet_5 = next(p for p in enhanced_packets if p.packet_number == 5)
        packet_6 = next(p for p in enhanced_packets if p.packet_number == 6)
        packet_7 = next(p for p in enhanced_packets if p.packet_number == 7)
        
        self.assertTrue(packet_5.tls_reassembled, "包5应该被标记为重组包")
        self.assertTrue(packet_6.tls_reassembled, "包6应该被标记为重组包")
        self.assertTrue(packet_7.is_tls_handshake, "包7应该保持为TLS Handshake")
        
        # 验证重组信息
        self.assertEqual(packet_5.tls_reassembly_info['record_type'], 'Handshake')
        self.assertEqual(packet_6.tls_reassembly_info['record_type'], 'Handshake')


if __name__ == '__main__':
    unittest.main() 