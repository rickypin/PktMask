"""
测试同一包内多个不同TLS类型记录的掩码处理

验证当一个数据包包含多个不同类型的TLS记录时（如TLS-22 + TLS-23），
掩码规则的生成和应用是否正确。
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from pathlib import Path

from src.pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer
from src.pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
from src.pktmask.core.trim.models.tls_models import TLSRecordInfo, MaskRule, MaskAction


class TestMultiTLSRecordMasking(unittest.TestCase):
    """测试同一包内多个不同TLS类型记录的掩码处理"""
    
    def setUp(self):
        """测试初始化"""
        self.analyzer = TSharkTLSAnalyzer({'verbose': True})
        self.rule_generator = TLSMaskRuleGenerator({'verbose': True})
        
    def test_single_packet_multi_tls_records_parsing(self):
        """测试单包多TLS记录的解析"""
        # 模拟包含TLS-22 (Handshake) + TLS-23 (ApplicationData) 的包
        mock_packet_multi_tls = {
            "_source": {
                "layers": {
                    "frame.number": ["100"],
                    "tcp.stream": ["5"],
                    "tcp.seq": ["1000"],
                    "tls.record.content_type": ["22", "23"],  # Handshake + ApplicationData
                    "tls.record.length": ["64", "256"],       # 64字节 + 256字节
                    "tls.record.version": ["0x0303", "0x0303"]  # TLS 1.2
                }
            }
        }
        
        # 测试解析
        records = self.analyzer._parse_packet_tls_records(mock_packet_multi_tls)
        
        # 验证解析结果
        self.assertEqual(len(records), 2, "应该解析出2个TLS记录")
        
        # 验证第一个记录 (TLS-22 Handshake)
        record1 = records[0]
        self.assertEqual(record1.content_type, 22)
        self.assertEqual(record1.length, 64)
        self.assertEqual(record1.record_offset, 0, "第一个记录偏移应该是0")
        
        # 验证第二个记录 (TLS-23 ApplicationData)
        record2 = records[1]
        self.assertEqual(record2.content_type, 23)
        self.assertEqual(record2.length, 256)
        self.assertEqual(record2.record_offset, 69, "第二个记录偏移应该是69 (0+5+64)")
        
    def test_multi_tls_records_mask_rule_generation(self):
        """测试多TLS记录的掩码规则生成"""
        # 创建测试TLS记录
        record1 = TLSRecordInfo(
            packet_number=100,
            content_type=22,  # Handshake - 应该完全保留
            version=(3, 3),
            length=64,
            is_complete=True,
            spans_packets=[100],
            tcp_stream_id="TCP_5",
            record_offset=0
        )
        
        record2 = TLSRecordInfo(
            packet_number=100,
            content_type=23,  # ApplicationData - 应该掩码载荷
            version=(3, 3),
            length=256,
            is_complete=True,
            spans_packets=[100],
            tcp_stream_id="TCP_5",
            record_offset=69  # 0 + 5 (TLS头) + 64 (第一个记录长度)
        )
        
        records = [record1, record2]
        
        # 生成掩码规则
        rules = self.rule_generator.generate_rules(records)
        
        # 验证规则数量
        self.assertEqual(len(rules), 2, "应该生成2条掩码规则")
        
        # 验证TLS-22规则 (完全保留)
        tls22_rules = [r for r in rules if r.tls_record_type == 22]
        self.assertEqual(len(tls22_rules), 1, "应该有1条TLS-22规则")
        rule22 = tls22_rules[0]
        self.assertEqual(rule22.action, MaskAction.KEEP_ALL, "TLS-22应该完全保留")
        self.assertEqual(rule22.tls_record_offset, 0, "TLS-22偏移应该是0")
        self.assertEqual(rule22.mask_length, 0, "TLS-22掩码长度应该是0")
        
        # 验证TLS-23规则 (掩码载荷)
        tls23_rules = [r for r in rules if r.tls_record_type == 23]
        self.assertEqual(len(tls23_rules), 1, "应该有1条TLS-23规则")
        rule23 = tls23_rules[0]
        self.assertEqual(rule23.action, MaskAction.MASK_PAYLOAD, "TLS-23应该掩码载荷")
        self.assertEqual(rule23.tls_record_offset, 69, "TLS-23偏移应该是69")
        self.assertEqual(rule23.mask_offset, 5, "TLS-23掩码偏移应该是5字节(保留头部)")
        self.assertEqual(rule23.mask_length, 256, "TLS-23掩码长度应该是256字节")
        
    def test_mask_rule_absolute_offsets(self):
        """测试掩码规则的绝对偏移计算"""
        # 创建TLS-23记录（在包内偏移69）
        record = TLSRecordInfo(
            packet_number=100,
            content_type=23,
            version=(3, 3),
            length=256,
            is_complete=True,
            spans_packets=[100],
            tcp_stream_id="TCP_5",
            record_offset=69
        )
        
        rules = self.rule_generator.generate_rules([record])
        self.assertEqual(len(rules), 1)
        
        rule = rules[0]
        
        # 验证绝对偏移计算
        # 绝对掩码开始位置 = record_offset + mask_offset = 69 + 5 = 74
        # 绝对掩码结束位置 = 绝对开始位置 + mask_length = 74 + 256 = 330
        self.assertEqual(rule.absolute_mask_start, 74, "绝对掩码开始位置应该是74")
        self.assertEqual(rule.absolute_mask_end, 330, "绝对掩码结束位置应该是330")
        
    def test_overlapping_mask_detection(self):
        """测试重叠掩码检测"""
        # 创建两个可能重叠的记录
        record1 = TLSRecordInfo(
            packet_number=100,
            content_type=22,
            version=(3, 3),
            length=100,  # 较大的Handshake记录
            is_complete=True,
            spans_packets=[100],
            tcp_stream_id="TCP_5",
            record_offset=0
        )
        
        record2 = TLSRecordInfo(
            packet_number=100,
            content_type=23,
            version=(3, 3),
            length=50,
            is_complete=True,
            spans_packets=[100],
            tcp_stream_id="TCP_5",
            record_offset=105  # 0 + 5 + 100 = 105
        )
        
        records = [record1, record2]
        rules = self.rule_generator.generate_rules(records)
        
        # 验证没有重叠
        rule22 = next(r for r in rules if r.tls_record_type == 22)
        rule23 = next(r for r in rules if r.tls_record_type == 23)
        
        # TLS-22: 0-105 (完全保留，所以实际不掩码)
        # TLS-23: 110-160 (105+5 到 105+5+50)
        
        self.assertEqual(rule22.tls_record_offset, 0)
        self.assertEqual(rule22.tls_record_length, 105)  # 5 + 100
        
        self.assertEqual(rule23.tls_record_offset, 105)
        self.assertEqual(rule23.absolute_mask_start, 110)  # 105 + 5
        self.assertEqual(rule23.absolute_mask_end, 160)    # 110 + 50
        
    def test_three_tls_records_in_packet(self):
        """测试一个包内包含三个TLS记录的情况"""
        # 模拟包含3个TLS记录的复杂包
        mock_packet_three_tls = {
            "_source": {
                "layers": {
                    "frame.number": ["200"],
                    "tcp.stream": ["10"],
                    "tcp.seq": ["2000"],
                    "tls.record.content_type": ["22", "23", "22"],  # Handshake + ApplicationData + Handshake
                    "tls.record.length": ["32", "128", "16"],        # 32 + 128 + 16字节
                    "tls.record.version": ["0x0303", "0x0303", "0x0303"]
                }
            }
        }
        
        records = self.analyzer._parse_packet_tls_records(mock_packet_three_tls)
        
        # 验证记录数量和偏移
        self.assertEqual(len(records), 3)
        
        # 第一个记录 (TLS-22): 偏移0
        self.assertEqual(records[0].content_type, 22)
        self.assertEqual(records[0].record_offset, 0)
        
        # 第二个记录 (TLS-23): 偏移37 (0+5+32)
        self.assertEqual(records[1].content_type, 23)
        self.assertEqual(records[1].record_offset, 37)
        
        # 第三个记录 (TLS-22): 偏移170 (37+5+128)
        self.assertEqual(records[2].content_type, 22)
        self.assertEqual(records[2].record_offset, 170)
        
        # 生成掩码规则
        rules = self.rule_generator.generate_rules(records)
        
        # 验证只有TLS-23被掩码
        tls22_rules = [r for r in rules if r.tls_record_type == 22]
        tls23_rules = [r for r in rules if r.tls_record_type == 23]
        
        self.assertEqual(len(tls22_rules), 2, "应该有2条TLS-22规则")
        self.assertEqual(len(tls23_rules), 1, "应该有1条TLS-23规则")
        
        # 验证TLS-23掩码规则
        rule23 = tls23_rules[0]
        self.assertEqual(rule23.absolute_mask_start, 42)  # 37 + 5
        self.assertEqual(rule23.absolute_mask_end, 170)   # 42 + 128
        
    def test_mixed_tls_versions_multi_records(self):
        """测试混合TLS版本的多记录包"""
        # 模拟包含TLS 1.2和TLS 1.3记录的包
        mock_packet_mixed_versions = {
            "_source": {
                "layers": {
                    "frame.number": ["300"],
                    "tcp.stream": ["15"],
                    "tcp.seq": ["3000"],
                    "tls.record.content_type": ["22", ""],      # TLS 1.2 Handshake
                    "tls.record.opaque_type": ["", "23"],       # TLS 1.3 ApplicationData
                    "tls.record.length": ["48", "200"],
                    "tls.record.version": ["0x0303", "0x0304"]  # TLS 1.2 + TLS 1.3
                }
            }
        }
        
        records = self.analyzer._parse_packet_tls_records(mock_packet_mixed_versions)
        
        # 验证混合版本解析
        self.assertEqual(len(records), 2)
        
        # TLS 1.2 Handshake
        self.assertEqual(records[0].content_type, 22)
        self.assertEqual(records[0].version, (3, 3))
        self.assertEqual(records[0].record_offset, 0)
        
        # TLS 1.3 ApplicationData
        self.assertEqual(records[1].content_type, 23)
        self.assertEqual(records[1].version, (3, 4))
        self.assertEqual(records[1].record_offset, 53)  # 0 + 5 + 48
        
        # 生成掩码规则并验证
        rules = self.rule_generator.generate_rules(records)
        
        tls22_rule = next(r for r in rules if r.tls_record_type == 22)
        tls23_rule = next(r for r in rules if r.tls_record_type == 23)
        
        # TLS-22完全保留
        self.assertEqual(tls22_rule.action, MaskAction.KEEP_ALL)
        
        # TLS-23掩码载荷
        self.assertEqual(tls23_rule.action, MaskAction.MASK_PAYLOAD)
        self.assertEqual(tls23_rule.absolute_mask_start, 58)  # 53 + 5
        self.assertEqual(tls23_rule.absolute_mask_end, 258)   # 58 + 200


if __name__ == '__main__':
    unittest.main() 