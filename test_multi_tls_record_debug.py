"""
深度调试测试：多TLS记录掩码边界计算和重叠检测

用于验证当同一数据包包含多个不同TLS类型记录时的具体行为：
1. 是否存在多打（重复掩码）
2. 是否存在偏移错误
3. 是否错误掩码了TLS-23消息头
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# 添加源码路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer
from src.pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
from src.pktmask.core.processors.scapy_mask_applier import ScapyMaskApplier
from src.pktmask.core.trim.models.tls_models import TLSRecordInfo, MaskRule, MaskAction


class TestMultiTLSRecordDebug(unittest.TestCase):
    """深度调试多TLS记录掩码处理"""
    
    def setUp(self):
        """初始化测试组件"""
        self.analyzer = TSharkTLSAnalyzer({'verbose': True})
        self.rule_generator = TLSMaskRuleGenerator({'verbose': True})
        self.mask_applier = ScapyMaskApplier({'verbose': True})
        
    def test_tls22_tls23_boundary_calculation(self):
        """测试TLS-22 + TLS-23记录的边界计算"""
        print("\n=== 测试TLS-22 + TLS-23边界计算 ===")
        
        # 模拟实际的TLS-22 Handshake + TLS-23 ApplicationData包
        record_tls22 = TLSRecordInfo(
            packet_number=100,
            content_type=22,  # Handshake
            version=(3, 3),   # TLS 1.2
            length=64,        # 消息体64字节
            is_complete=True,
            spans_packets=[100],
            tcp_stream_id="TCP_192.168.1.1:443_192.168.1.100:12345",
            record_offset=0   # 第一个记录，偏移0
        )
        
        record_tls23 = TLSRecordInfo(
            packet_number=100,
            content_type=23,  # ApplicationData  
            version=(3, 3),
            length=256,       # 消息体256字节
            is_complete=True,
            spans_packets=[100],
            tcp_stream_id="TCP_192.168.1.1:443_192.168.1.100:12345",
            record_offset=69  # 0 + 5(头部) + 64(TLS-22长度) = 69
        )
        
        # 生成掩码规则
        rules = self.rule_generator.generate_rules([record_tls22, record_tls23])
        
        print(f"生成规则数量: {len(rules)}")
        
        for i, rule in enumerate(rules):
            print(f"\n规则 {i+1}:")
            print(f"  类型: TLS-{rule.tls_record_type}")
            print(f"  动作: {rule.action.name}")
            print(f"  记录偏移: {rule.tls_record_offset}")
            print(f"  记录长度: {rule.tls_record_length}")
            print(f"  掩码偏移: {rule.mask_offset}")
            print(f"  掩码长度: {rule.mask_length}")
            print(f"  绝对起始: {rule.absolute_mask_start}")
            print(f"  绝对结束: {rule.absolute_mask_end}")
            print(f"  原因: {rule.reason}")
            
        # 验证边界计算
        tls22_rule = next(r for r in rules if r.tls_record_type == 22)
        tls23_rule = next(r for r in rules if r.tls_record_type == 23)
        
        # TLS-22验证
        print(f"\n=== TLS-22边界验证 ===")
        print(f"TLS-22记录范围: {tls22_rule.tls_record_offset} - {tls22_rule.tls_record_offset + tls22_rule.tls_record_length}")
        self.assertEqual(tls22_rule.tls_record_offset, 0, "TLS-22偏移应该是0")
        self.assertEqual(tls22_rule.tls_record_length, 69, "TLS-22记录长度应该是69 (64+5)")
        self.assertEqual(tls22_rule.action, MaskAction.KEEP_ALL, "TLS-22应该完全保留")
        
        # TLS-23验证
        print(f"\n=== TLS-23边界验证 ===")
        print(f"TLS-23记录范围: {tls23_rule.tls_record_offset} - {tls23_rule.tls_record_offset + tls23_rule.tls_record_length}")
        print(f"TLS-23掩码范围: {tls23_rule.absolute_mask_start} - {tls23_rule.absolute_mask_end}")
        self.assertEqual(tls23_rule.tls_record_offset, 69, "TLS-23偏移应该是69")
        self.assertEqual(tls23_rule.tls_record_length, 261, "TLS-23记录长度应该是261 (256+5)")
        self.assertEqual(tls23_rule.mask_offset, 5, "TLS-23掩码偏移应该是5（保留头部）")
        self.assertEqual(tls23_rule.mask_length, 256, "TLS-23掩码长度应该是256")
        self.assertEqual(tls23_rule.absolute_mask_start, 74, "绝对掩码起始应该是74 (69+5)")
        self.assertEqual(tls23_rule.absolute_mask_end, 330, "绝对掩码结束应该是330 (74+256)")
        
        # 验证无重叠
        print(f"\n=== 重叠检查 ===")
        tls22_end = tls22_rule.tls_record_offset + tls22_rule.tls_record_length
        tls23_start = tls23_rule.tls_record_offset
        print(f"TLS-22结束位置: {tls22_end}")
        print(f"TLS-23开始位置: {tls23_start}")
        self.assertEqual(tls22_end, tls23_start, "TLS-22结束位置应该等于TLS-23开始位置")
        
        # 验证TLS-23头部保护
        print(f"\n=== TLS-23头部保护验证 ===")
        tls23_header_start = tls23_rule.tls_record_offset
        tls23_header_end = tls23_header_start + 5
        tls23_payload_start = tls23_rule.absolute_mask_start
        print(f"TLS-23头部范围: {tls23_header_start} - {tls23_header_end}")
        print(f"TLS-23载荷掩码起始: {tls23_payload_start}")
        self.assertEqual(tls23_header_end, tls23_payload_start, "头部结束位置应该等于载荷掩码起始位置")
        
        print("\n✅ TLS-22 + TLS-23边界计算测试通过！")
        
    def test_overlapping_mask_detection(self):
        """测试掩码重叠检测"""
        print("\n=== 测试掩码重叠检测 ===")
        
        # 创建三个TLS记录，测试复杂的重叠场景
        records = [
            TLSRecordInfo(
                packet_number=200,
                content_type=22,  # Handshake
                version=(3, 3),
                length=32,
                is_complete=True,
                spans_packets=[200],
                tcp_stream_id="TCP_test",
                record_offset=0
            ),
            TLSRecordInfo(
                packet_number=200,
                content_type=23,  # ApplicationData
                version=(3, 3),
                length=128,
                is_complete=True,
                spans_packets=[200],
                tcp_stream_id="TCP_test",
                record_offset=37  # 0 + 5 + 32 = 37
            ),
            TLSRecordInfo(
                packet_number=200,
                content_type=22,  # Handshake
                version=(3, 3),
                length=16,
                is_complete=True,
                spans_packets=[200],
                tcp_stream_id="TCP_test",
                record_offset=170  # 37 + 5 + 128 = 170
            )
        ]
        
        rules = self.rule_generator.generate_rules(records)
        
        print(f"生成规则数量: {len(rules)}")
        
        # 按TLS类型分组
        tls22_rules = [r for r in rules if r.tls_record_type == 22]
        tls23_rules = [r for r in rules if r.tls_record_type == 23]
        
        print(f"TLS-22规则数: {len(tls22_rules)}")
        print(f"TLS-23规则数: {len(tls23_rules)}")
        
        # 验证所有规则的边界
        print(f"\n=== 所有规则边界 ===")
        for i, rule in enumerate(sorted(rules, key=lambda r: r.tls_record_offset)):
            print(f"规则{i+1} TLS-{rule.tls_record_type}: 记录[{rule.tls_record_offset}:{rule.tls_record_offset + rule.tls_record_length}]", end="")
            if rule.action == MaskAction.MASK_PAYLOAD:
                print(f" 掩码[{rule.absolute_mask_start}:{rule.absolute_mask_end}]")
            else:
                print(f" 完全保留")
        
        # 检查重叠
        mask_ranges = []
        for rule in rules:
            if rule.action == MaskAction.MASK_PAYLOAD:
                mask_ranges.append((rule.absolute_mask_start, rule.absolute_mask_end, f"TLS-{rule.tls_record_type}"))
        
        print(f"\n=== 掩码范围重叠检查 ===")
        for i, (start1, end1, type1) in enumerate(mask_ranges):
            for j, (start2, end2, type2) in enumerate(mask_ranges):
                if i < j:  # 避免重复检查
                    overlap = not (end1 <= start2 or end2 <= start1)
                    print(f"{type1}[{start1}:{end1}] vs {type2}[{start2}:{end2}] - {'❌重叠' if overlap else '✅无重叠'}")
                    self.assertFalse(overlap, f"检测到重叠: {type1} vs {type2}")
                    
        print("\n✅ 重叠检测测试通过！")
        
    def test_tls23_header_protection(self):
        """测试TLS-23头部保护"""
        print("\n=== 测试TLS-23头部保护 ===")
        
        # 创建多个TLS-23记录
        records = [
            TLSRecordInfo(
                packet_number=300,
                content_type=23,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[300],
                tcp_stream_id="TCP_test",
                record_offset=0
            ),
            TLSRecordInfo(
                packet_number=300,
                content_type=23,
                version=(3, 3),
                length=200,
                is_complete=True,
                spans_packets=[300],
                tcp_stream_id="TCP_test",
                record_offset=105  # 0 + 5 + 100 = 105
            )
        ]
        
        rules = self.rule_generator.generate_rules(records)
        
        print(f"TLS-23记录数: {len(records)}")
        print(f"生成规则数: {len(rules)}")
        
        for i, rule in enumerate(rules):
            print(f"\nTLS-23记录{i+1}:")
            print(f"  记录偏移: {rule.tls_record_offset}")
            print(f"  记录长度: {rule.tls_record_length}")
            print(f"  头部范围: {rule.tls_record_offset} - {rule.tls_record_offset + 5}")
            print(f"  载荷范围: {rule.tls_record_offset + 5} - {rule.tls_record_offset + rule.tls_record_length}")
            print(f"  掩码偏移: {rule.mask_offset}")
            print(f"  掩码长度: {rule.mask_length}")
            print(f"  绝对掩码: {rule.absolute_mask_start} - {rule.absolute_mask_end}")
            
            # 验证头部保护
            expected_header_start = rule.tls_record_offset
            expected_header_end = rule.tls_record_offset + 5
            actual_mask_start = rule.absolute_mask_start
            
            print(f"  头部保护验证: 头部[{expected_header_start}:{expected_header_end}] vs 掩码起始[{actual_mask_start}]")
            self.assertEqual(expected_header_end, actual_mask_start, 
                           f"TLS-23记录{i+1}头部未正确保护：头部结束{expected_header_end} != 掩码起始{actual_mask_start}")
            
        print("\n✅ TLS-23头部保护测试通过！")
        
    def test_length_calculation_consistency(self):
        """测试长度计算一致性"""
        print("\n=== 测试长度计算一致性 ===")
        
        # 创建不同类型的TLS记录
        test_cases = [
            (22, 50, "KEEP_ALL"),    # TLS-22 Handshake
            (23, 100, "MASK_PAYLOAD"), # TLS-23 ApplicationData
            (21, 30, "KEEP_ALL"),    # TLS-21 Alert
            (20, 1, "KEEP_ALL"),     # TLS-20 ChangeCipherSpec
        ]
        
        for content_type, message_length, expected_strategy in test_cases:
            record = TLSRecordInfo(
                packet_number=400,
                content_type=content_type,
                version=(3, 3),
                length=message_length,
                is_complete=True,
                spans_packets=[400],
                tcp_stream_id="TCP_test",
                record_offset=0
            )
            
            rules = self.rule_generator.generate_rules([record])
            self.assertEqual(len(rules), 1)
            
            rule = rules[0]
            expected_total_length = message_length + 5  # 消息体 + 5字节头部
            
            print(f"\nTLS-{content_type} ({expected_strategy}):")
            print(f"  消息体长度: {message_length}")
            print(f"  期望总长度: {expected_total_length}")
            print(f"  实际记录长度: {rule.tls_record_length}")
            print(f"  验证: {'✅通过' if rule.tls_record_length == expected_total_length else '❌失败'}")
            
            self.assertEqual(rule.tls_record_length, expected_total_length,
                           f"TLS-{content_type}长度计算不一致：期望{expected_total_length}，实际{rule.tls_record_length}")
                           
        print("\n✅ 长度计算一致性测试通过！")
        
    def test_real_world_scenario(self):
        """测试真实世界复杂场景"""
        print("\n=== 测试真实世界复杂场景 ===")
        
        # 模拟一个复杂的包：TLS-22 + TLS-23 + TLS-21
        # 这种组合在HTTPS握手+数据传输+连接关闭时可能出现
        records = [
            TLSRecordInfo(
                packet_number=500,
                content_type=22,  # Handshake (ServerHello)
                version=(3, 3),
                length=78,
                is_complete=True,
                spans_packets=[500],
                tcp_stream_id="TCP_complex",
                record_offset=0
            ),
            TLSRecordInfo(
                packet_number=500,
                content_type=23,  # ApplicationData (HTTP Response)
                version=(3, 3),
                length=512,
                is_complete=True,
                spans_packets=[500],
                tcp_stream_id="TCP_complex",
                record_offset=83  # 0 + 5 + 78 = 83
            ),
            TLSRecordInfo(
                packet_number=500,
                content_type=21,  # Alert (CloseNotify)
                version=(3, 3),
                length=2,
                is_complete=True,
                spans_packets=[500],
                tcp_stream_id="TCP_complex",
                record_offset=600  # 83 + 5 + 512 = 600
            )
        ]
        
        rules = self.rule_generator.generate_rules(records)
        
        print(f"复杂场景记录数: {len(records)}")
        print(f"生成规则数: {len(rules)}")
        
        # 计算总TCP载荷长度
        total_tcp_payload = records[-1].record_offset + records[-1].length + 5
        print(f"预期TCP载荷总长度: {total_tcp_payload}")
        
        # 验证每个规则
        for i, rule in enumerate(sorted(rules, key=lambda r: r.tls_record_offset)):
            print(f"\n规则{i+1} - TLS-{rule.tls_record_type}:")
            print(f"  动作: {rule.action.name}")
            print(f"  记录边界: [{rule.tls_record_offset}:{rule.tls_record_offset + rule.tls_record_length}]")
            
            if rule.action == MaskAction.MASK_PAYLOAD:
                print(f"  掩码边界: [{rule.absolute_mask_start}:{rule.absolute_mask_end}]")
                print(f"  头部保护: {rule.tls_record_offset} - {rule.tls_record_offset + rule.mask_offset}")
                
                # 验证头部保护
                self.assertEqual(rule.mask_offset, 5, f"TLS-{rule.tls_record_type}应该保护5字节头部")
                self.assertEqual(rule.absolute_mask_start, rule.tls_record_offset + 5,
                               f"TLS-{rule.tls_record_type}掩码应该从头部后开始")
            else:
                print(f"  完全保留（无掩码）")
        
        # 验证策略正确性
        tls22_rule = next(r for r in rules if r.tls_record_type == 22)
        tls23_rule = next(r for r in rules if r.tls_record_type == 23)
        tls21_rule = next(r for r in rules if r.tls_record_type == 21)
        
        self.assertEqual(tls22_rule.action, MaskAction.KEEP_ALL, "TLS-22应该完全保留")
        self.assertEqual(tls23_rule.action, MaskAction.MASK_PAYLOAD, "TLS-23应该掩码载荷")
        self.assertEqual(tls21_rule.action, MaskAction.KEEP_ALL, "TLS-21应该完全保留")
        
        print("\n✅ 真实世界复杂场景测试通过！")


if __name__ == '__main__':
    # 设置详细输出
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # 运行测试
    unittest.main(verbosity=2) 