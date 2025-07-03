"""
多TLS记录掩码边界问题调试测试

用于重现和修复同一数据包中包含不同TLS类型消息时的掩码问题：
1. 多打掩码
2. 偏移错误  
3. TLS-23类型的消息头被掩码

期望行为：
- TLS-23类型：保留5字节头部，消息体置零
- 其他类型：全部保留
"""

import pytest
import logging
from typing import List, Dict, Any

from src.pktmask.core.trim.models.tls_models import (
    TLSRecordInfo, 
    MaskRule, 
    MaskAction,
    create_mask_rule_for_tls_record
)
from src.pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
from src.pktmask.core.processors.scapy_mask_applier import ScapyMaskApplier

class TestMultiTLSRecordMaskingDebug:
    """多TLS记录掩码边界问题调试测试类"""
    
    def setup_method(self):
        """测试初始化"""
        self.logger = logging.getLogger(__name__)
        self.rule_generator = TLSMaskRuleGenerator()
        self.mask_applier = ScapyMaskApplier()
        
    def test_multi_tls_record_boundary_calculation(self):
        """测试多TLS记录的边界计算问题"""
        print("\n=== 测试多TLS记录边界计算 ===")
        
        # 模拟同一包中的TLS-22和TLS-23记录
        # 基于实际PCAP文件的数据包结构
        tls_records = [
            # TLS-22 Handshake记录：偏移0，长度64字节
            TLSRecordInfo(
                packet_number=100,
                content_type=22,  # Handshake
                version=(3, 3),   # TLS 1.2
                length=64,        # 消息体64字节（不包含5字节头部）
                is_complete=True,
                spans_packets=[100],
                tcp_stream_id="TCP_192.168.1.1:443_192.168.1.2:45678_forward",
                record_offset=0   # 第一个记录，偏移0
            ),
            # TLS-23 ApplicationData记录：偏移69，长度256字节  
            TLSRecordInfo(
                packet_number=100,
                content_type=23,  # ApplicationData
                version=(3, 3),   # TLS 1.2
                length=256,       # 消息体256字节（不包含5字节头部）
                is_complete=True,
                spans_packets=[100],
                tcp_stream_id="TCP_192.168.1.1:443_192.168.1.2:45678_forward",
                record_offset=69  # 第二个记录，偏移69（64+5）
            )
        ]
        
        print(f"输入TLS记录：")
        for i, record in enumerate(tls_records):
            print(f"  记录{i}: TLS-{record.content_type}, 偏移={record.record_offset}, 长度={record.length}")
        
        # 生成掩码规则
        rules = self.rule_generator._generate_rules_for_packet(100, tls_records)
        
        print(f"\n生成的掩码规则：")
        for i, rule in enumerate(rules):
            print(f"  规则{i}: TLS-{rule.tls_record_type}")
            print(f"    偏移: {rule.tls_record_offset}, 总长度: {rule.tls_record_length}")
            print(f"    掩码偏移: {rule.mask_offset}, 掩码长度: {rule.mask_length}")
            print(f"    动作: {rule.action}, 原因: {rule.reason}")
            print(f"    绝对掩码范围: {rule.absolute_mask_start}-{rule.absolute_mask_end}")
            
        # 验证TLS-22记录（完全保留）
        tls22_rule = rules[0]
        assert tls22_rule.tls_record_type == 22
        assert tls22_rule.action == MaskAction.KEEP_ALL
        assert tls22_rule.mask_length == 0  # 不掩码
        
        # 验证TLS-23记录（智能掩码）
        tls23_rule = rules[1]
        assert tls23_rule.tls_record_type == 23
        assert tls23_rule.action == MaskAction.MASK_PAYLOAD
        assert tls23_rule.mask_offset == 5  # 保留5字节头部
        assert tls23_rule.mask_length == 256  # 掩码256字节消息体
        
        # 检查边界计算
        print(f"\n边界检查：")
        print(f"  TLS-22边界: {tls22_rule.tls_record_offset}-{tls22_rule.tls_record_offset + tls22_rule.tls_record_length}")
        print(f"  TLS-23边界: {tls23_rule.tls_record_offset}-{tls23_rule.tls_record_offset + tls23_rule.tls_record_length}")
        print(f"  TLS-23掩码范围: {tls23_rule.absolute_mask_start}-{tls23_rule.absolute_mask_end}")
        
        # 验证无重叠：TLS-22结束于69，TLS-23开始于69
        tls22_end = tls22_rule.tls_record_offset + tls22_rule.tls_record_length
        tls23_start = tls23_rule.tls_record_offset
        print(f"  边界检查: TLS-22结束于{tls22_end}, TLS-23开始于{tls23_start}")
        assert tls22_end <= tls23_start, f"TLS记录重叠: {tls22_end} > {tls23_start}"
        
        # 验证TLS-23头部保护：掩码应该从74开始（69+5）
        expected_mask_start = 69 + 5  # 记录偏移 + 头部长度
        assert tls23_rule.absolute_mask_start == expected_mask_start, \
            f"TLS-23掩码起始位置错误: {tls23_rule.absolute_mask_start} != {expected_mask_start}"
        
        print("✓ 边界计算测试通过")
        
    def test_mask_overlap_detection(self):
        """测试掩码重叠检测"""
        print("\n=== 测试掩码重叠检测 ===")
        
        # 模拟三个TLS记录的复杂情况
        tls_records = [
            # TLS-22: 偏移0，长度100字节
            TLSRecordInfo(
                packet_number=200,
                content_type=22, length=100, version=(3, 3),
                is_complete=True, spans_packets=[200],
                tcp_stream_id="TCP_test", record_offset=0
            ),
            # TLS-23: 偏移105，长度200字节
            TLSRecordInfo(
                packet_number=200,
                content_type=23, length=200, version=(3, 3),
                is_complete=True, spans_packets=[200],
                tcp_stream_id="TCP_test", record_offset=105
            ),
            # TLS-22: 偏移310，长度50字节
            TLSRecordInfo(
                packet_number=200,
                content_type=22, length=50, version=(3, 3),
                is_complete=True, spans_packets=[200],
                tcp_stream_id="TCP_test", record_offset=310
            )
        ]
        
        rules = self.rule_generator._generate_rules_for_packet(200, tls_records)
        
        print(f"生成了{len(rules)}个掩码规则")
        
        # 检查所有规则的边界
        boundaries = []
        for i, rule in enumerate(rules):
            start = rule.tls_record_offset
            end = rule.tls_record_offset + rule.tls_record_length
            boundaries.append((start, end, f"TLS-{rule.tls_record_type}"))
            print(f"  规则{i}: TLS-{rule.tls_record_type}, 边界{start}-{end}")
            
            if rule.action == MaskAction.MASK_PAYLOAD:
                mask_start = rule.absolute_mask_start
                mask_end = rule.absolute_mask_end
                print(f"    掩码范围: {mask_start}-{mask_end}")
        
        # 检查边界重叠
        for i in range(len(boundaries) - 1):
            current_end = boundaries[i][1]
            next_start = boundaries[i + 1][0]
            print(f"  边界检查: {boundaries[i][2]}结束于{current_end}, {boundaries[i+1][2]}开始于{next_start}")
            assert current_end <= next_start, f"记录重叠: {boundaries[i][2]} 与 {boundaries[i+1][2]}"
        
        print("✓ 重叠检测测试通过")
        
    def test_tls23_header_protection(self):
        """测试TLS-23头部保护机制"""
        print("\n=== 测试TLS-23头部保护 ===")
        
        # 模拟多个TLS-23记录，验证每个头部都被正确保护
        tls_records = [
            # 第一个TLS-23记录
            TLSRecordInfo(
                packet_number=300,
                content_type=23, length=100, version=(3, 3),
                is_complete=True, spans_packets=[300],
                tcp_stream_id="TCP_test", record_offset=0
            ),
            # 第二个TLS-23记录  
            TLSRecordInfo(
                packet_number=300,
                content_type=23, length=150, version=(3, 3),
                is_complete=True, spans_packets=[300],
                tcp_stream_id="TCP_test", record_offset=105  # 100 + 5
            )
        ]
        
        rules = self.rule_generator._generate_rules_for_packet(300, tls_records)
        
        for i, rule in enumerate(rules):
            print(f"  TLS-23记录{i}:")
            print(f"    记录偏移: {rule.tls_record_offset}")
            print(f"    掩码偏移: {rule.mask_offset}  (应该为5)")
            print(f"    掩码长度: {rule.mask_length}")
            print(f"    头部保护范围: {rule.tls_record_offset}-{rule.tls_record_offset + rule.mask_offset}")
            print(f"    掩码范围: {rule.absolute_mask_start}-{rule.absolute_mask_end}")
            
            # 验证头部保护
            assert rule.mask_offset == 5, f"TLS-23头部保护失效: mask_offset={rule.mask_offset}"
            assert rule.action == MaskAction.MASK_PAYLOAD, f"TLS-23掩码动作错误: {rule.action}"
            
            # 验证掩码范围不包含头部
            expected_mask_start = rule.tls_record_offset + 5
            assert rule.absolute_mask_start == expected_mask_start, \
                f"掩码起始位置包含头部: {rule.absolute_mask_start} != {expected_mask_start}"
        
        print("✓ TLS-23头部保护测试通过")
        
    def test_length_calculation_consistency(self):
        """测试长度计算一致性"""
        print("\n=== 测试长度计算一致性 ===")
        
        # 测试create_mask_rule_for_tls_record函数的长度计算
        tls22_record = TLSRecordInfo(
            packet_number=400, content_type=22, length=64, version=(3, 3),
            is_complete=True, spans_packets=[400],
            tcp_stream_id="TCP_test", record_offset=0
        )
        
        tls23_record = TLSRecordInfo(
            packet_number=400, content_type=23, length=256, version=(3, 3),
            is_complete=True, spans_packets=[400],
            tcp_stream_id="TCP_test", record_offset=69  # 64 + 5
        )
        
        # 生成规则
        tls22_rule = create_mask_rule_for_tls_record(tls22_record)
        tls23_rule = create_mask_rule_for_tls_record(tls23_record)
        
        print(f"TLS-22规则:")
        print(f"  记录长度: {tls22_record.length} -> 规则长度: {tls22_rule.tls_record_length}")
        print(f"  应该包含5字节头部: {tls22_record.length + 5}")
        
        print(f"TLS-23规则:")
        print(f"  记录长度: {tls23_record.length} -> 规则长度: {tls23_rule.tls_record_length}")
        print(f"  应该包含5字节头部: {tls23_record.length + 5}")
        
        # 验证长度计算一致性：都应该包含5字节头部
        expected_tls22_length = tls22_record.length + 5
        expected_tls23_length = tls23_record.length + 5
        
        assert tls22_rule.tls_record_length == expected_tls22_length, \
            f"TLS-22长度计算不一致: {tls22_rule.tls_record_length} != {expected_tls22_length}"
            
        assert tls23_rule.tls_record_length == expected_tls23_length, \
            f"TLS-23长度计算不一致: {tls23_rule.tls_record_length} != {expected_tls23_length}"
        
        print("✓ 长度计算一致性测试通过")
        
    def test_real_world_scenario(self):
        """测试真实世界场景：复杂的多记录包"""
        print("\n=== 测试真实世界场景 ===")
        
        # 模拟实际PCAP文件中的复杂包：
        # TLS Client Hello(22) + TLS Application Data(23) + TLS Alert(21)
        tls_records = [
            # TLS-22 Client Hello
            TLSRecordInfo(
                packet_number=500, content_type=22, length=183, version=(3, 3),
                is_complete=True, spans_packets=[500],
                tcp_stream_id="TCP_real", record_offset=0
            ),
            # TLS-23 Application Data  
            TLSRecordInfo(
                packet_number=500, content_type=23, length=1024, version=(3, 3),
                is_complete=True, spans_packets=[500], 
                tcp_stream_id="TCP_real", record_offset=188  # 183 + 5
            ),
            # TLS-21 Alert
            TLSRecordInfo(
                packet_number=500, content_type=21, length=2, version=(3, 3),
                is_complete=True, spans_packets=[500],
                tcp_stream_id="TCP_real", record_offset=1217  # 188 + 1024 + 5
            )
        ]
        
        rules = self.rule_generator._generate_rules_for_packet(500, tls_records)
        
        print(f"真实场景：包含{len(tls_records)}个TLS记录，生成{len(rules)}个掩码规则")
        
        # 验证处理策略
        strategies = {}
        for rule in rules:
            tls_type = rule.tls_record_type
            action = rule.action
            strategies[tls_type] = action
            
            print(f"  TLS-{tls_type}: {action}")
            if action == MaskAction.MASK_PAYLOAD:
                print(f"    掩码范围: {rule.absolute_mask_start}-{rule.absolute_mask_end}")
                print(f"    头部保护: {rule.tls_record_offset}-{rule.tls_record_offset + rule.mask_offset}")
        
        # 验证策略正确性
        assert strategies[22] == MaskAction.KEEP_ALL, "TLS-22应该完全保留"
        assert strategies[23] == MaskAction.MASK_PAYLOAD, "TLS-23应该智能掩码"
        assert strategies[21] == MaskAction.KEEP_ALL, "TLS-21应该完全保留"
        
        # 验证只有TLS-23被掩码
        mask_rules = [r for r in rules if r.action == MaskAction.MASK_PAYLOAD]
        assert len(mask_rules) == 1, f"应该只有1个掩码规则，实际{len(mask_rules)}个"
        assert mask_rules[0].tls_record_type == 23, "掩码规则应该针对TLS-23"
        
        print("✓ 真实世界场景测试通过")

if __name__ == "__main__":
    # 设置详细日志
    logging.basicConfig(level=logging.INFO)
    
    # 运行测试
    test = TestMultiTLSRecordMaskingDebug()
    test.setup_method()
    
    try:
        test.test_multi_tls_record_boundary_calculation()
        test.test_mask_overlap_detection()
        test.test_tls23_header_protection()
        test.test_length_calculation_consistency()
        test.test_real_world_scenario()
        print("\n🎉 所有测试通过！多TLS记录掩码处理正常。")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        raise 