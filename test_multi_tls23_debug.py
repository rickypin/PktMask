#!/usr/bin/env python3
"""
多TLS-23记录掩码问题调试

专门测试用户描述的问题：
1. 同一数据包包含多个TLS-23 ApplicationData记录
2. 检查是否存在"消息头被错误掩码"的问题
3. 验证每个TLS-23记录的头部是否被正确保护
"""

import sys
import os
sys.path.insert(0, '/Users/ricky/Downloads/PktMask/src')

from pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
from pktmask.core.trim.models.tls_models import TLSRecordInfo, MaskAction

def test_single_tls23_in_packet():
    """测试单个TLS-23记录的正常情况"""
    print("=== 测试单个TLS-23记录 ===")
    
    record = TLSRecordInfo(
        packet_number=10,
        content_type=23,  # ApplicationData
        version=(3, 3),
        length=200,  # 消息体200字节
        is_complete=True,
        spans_packets=[10],
        tcp_stream_id="TCP_test",
        record_offset=0
    )
    
    rule_generator = TLSMaskRuleGenerator({'verbose': True})
    rules = rule_generator.generate_rules([record])
    
    print(f"生成规则数: {len(rules)}")
    for rule in rules:
        print(f"  TLS-{rule.tls_record_type}: {rule.action.name}")
        print(f"    记录偏移: {rule.tls_record_offset}")
        print(f"    记录长度: {rule.tls_record_length}")
        print(f"    掩码偏移: {rule.mask_offset}")
        print(f"    掩码长度: {rule.mask_length}")
        print(f"    绝对掩码范围: [{rule.absolute_mask_start}:{rule.absolute_mask_end}]")
        print(f"    头部保护范围: [{rule.tls_record_offset}:{rule.tls_record_offset + rule.mask_offset}]")
        
        # 验证头部保护
        expected_header_end = record.record_offset + 5
        actual_header_end = rule.tls_record_offset + rule.mask_offset
        if actual_header_end == expected_header_end:
            print(f"    ✅ 头部保护正确: [0:5]")
        else:
            print(f"    ❌ 头部保护错误: 期望[0:5], 实际[0:{rule.mask_offset}]")

def test_two_tls23_in_packet():
    """测试同一包中包含两个TLS-23记录的情况"""
    print("\n=== 测试同一包中的两个TLS-23记录 ===")
    
    # 第一个TLS-23记录：偏移0，长度169字节
    record1 = TLSRecordInfo(
        packet_number=14,
        content_type=23,  # ApplicationData
        version=(3, 3),
        length=169,
        is_complete=True,
        spans_packets=[14],
        tcp_stream_id="TCP_test",
        record_offset=0
    )
    
    # 第二个TLS-23记录：偏移174，长度26字节  
    record2 = TLSRecordInfo(
        packet_number=14,
        content_type=23,  # ApplicationData
        version=(3, 3),
        length=26,
        is_complete=True,
        spans_packets=[14],
        tcp_stream_id="TCP_test",
        record_offset=174  # 0 + 5 + 169 = 174
    )
    
    records = [record1, record2]
    
    print(f"输入记录：")
    for i, record in enumerate(records):
        print(f"  记录{i+1}: TLS-{record.content_type}, 偏移={record.record_offset}, 长度={record.length}")
        print(f"    期望头部保护: [{record.record_offset}:{record.record_offset + 5}]")
        print(f"    期望载荷掩码: [{record.record_offset + 5}:{record.record_offset + 5 + record.length}]")
    
    rule_generator = TLSMaskRuleGenerator({'verbose': True})
    rules = rule_generator.generate_rules(records)
    
    print(f"\n生成规则数: {len(rules)}")
    tls23_rules = [r for r in rules if r.tls_record_type == 23]
    print(f"TLS-23规则数: {len(tls23_rules)}")
    
    if len(tls23_rules) != len(records):
        print(f"🚨 警告: 记录数({len(records)}) != 规则数({len(tls23_rules)})")
        print(f"🚨 可能存在规则合并问题！")
        
        # 如果规则被合并，检查具体影响
        if len(tls23_rules) == 1:
            merged_rule = tls23_rules[0]
            print(f"\n🚨 规则被合并成一条:")
            print(f"  合并规则掩码范围: [{merged_rule.absolute_mask_start}:{merged_rule.absolute_mask_end}]")
            
            # 检查第二个记录的头部是否被错误掩码
            record2_header_start = record2.record_offset
            record2_header_end = record2.record_offset + 5
            
            if (merged_rule.absolute_mask_start <= record2_header_start < merged_rule.absolute_mask_end):
                print(f"🚨 严重问题: 第二个TLS-23记录的头部被错误掩码!")
                print(f"    第二记录头部: [{record2_header_start}:{record2_header_end}]")
                print(f"    合并规则掩码: [{merged_rule.absolute_mask_start}:{merged_rule.absolute_mask_end}]")
                print(f"    重叠范围: [{max(merged_rule.absolute_mask_start, record2_header_start)}:{min(merged_rule.absolute_mask_end, record2_header_end)}]")
    
    for i, rule in enumerate(tls23_rules):
        print(f"\n  规则{i+1}:")
        print(f"    记录偏移: {rule.tls_record_offset}")
        print(f"    记录长度: {rule.tls_record_length}")
        print(f"    掩码偏移: {rule.mask_offset}")
        print(f"    掩码长度: {rule.mask_length}")
        print(f"    绝对掩码范围: [{rule.absolute_mask_start}:{rule.absolute_mask_end}]")
        print(f"    头部保护范围: [{rule.tls_record_offset}:{rule.tls_record_offset + rule.mask_offset}]")
        print(f"    原因: {rule.reason}")

def test_three_tls23_in_packet():
    """测试同一包中包含三个TLS-23记录的极端情况"""
    print("\n=== 测试同一包中的三个TLS-23记录 ===")
    
    records = [
        TLSRecordInfo(
            packet_number=20,
            content_type=23,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[20],
            tcp_stream_id="TCP_test",
            record_offset=0
        ),
        TLSRecordInfo(
            packet_number=20,
            content_type=23,
            version=(3, 3),
            length=50,
            is_complete=True,
            spans_packets=[20],
            tcp_stream_id="TCP_test",
            record_offset=105  # 0 + 5 + 100
        ),
        TLSRecordInfo(
            packet_number=20,
            content_type=23,
            version=(3, 3),
            length=30,
            is_complete=True,
            spans_packets=[20],
            tcp_stream_id="TCP_test",
            record_offset=160  # 105 + 5 + 50
        )
    ]
    
    print(f"输入三个TLS-23记录：")
    total_expected_rules = 0
    for i, record in enumerate(records):
        print(f"  记录{i+1}: 偏移={record.record_offset}, 长度={record.length}")
        print(f"    期望头部保护: [{record.record_offset}:{record.record_offset + 5}]")
        total_expected_rules += 1
    
    rule_generator = TLSMaskRuleGenerator({'verbose': True})
    rules = rule_generator.generate_rules(records)
    
    tls23_rules = [r for r in rules if r.tls_record_type == 23]
    print(f"\n期望规则数: {total_expected_rules}")
    print(f"实际规则数: {len(tls23_rules)}")
    
    if len(tls23_rules) != total_expected_rules:
        print(f"🚨 规则数量不匹配！可能发生了规则合并")
        
    # 检查每个记录的头部保护
    print(f"\n头部保护检查：")
    for i, record in enumerate(records):
        record_header_start = record.record_offset
        record_header_end = record.record_offset + 5
        
        header_protected = True
        for rule in tls23_rules:
            if (rule.absolute_mask_start <= record_header_start < rule.absolute_mask_end):
                header_protected = False
                print(f"  记录{i+1}头部[{record_header_start}:{record_header_end}]: ❌ 被规则[{rule.absolute_mask_start}:{rule.absolute_mask_end}]错误掩码")
                break
        
        if header_protected:
            print(f"  记录{i+1}头部[{record_header_start}:{record_header_end}]: ✅ 正确保护")

def test_mixed_tls_types_with_multiple_tls23():
    """测试混合TLS类型包含多个TLS-23的情况"""
    print("\n=== 测试混合TLS类型 + 多TLS-23记录 ===")
    
    records = [
        # TLS-22 Handshake
        TLSRecordInfo(
            packet_number=30,
            content_type=22,
            version=(3, 3),
            length=64,
            is_complete=True,
            spans_packets=[30],
            tcp_stream_id="TCP_test",
            record_offset=0
        ),
        # 第一个TLS-23 ApplicationData
        TLSRecordInfo(
            packet_number=30,
            content_type=23,
            version=(3, 3),
            length=128,
            is_complete=True,
            spans_packets=[30],
            tcp_stream_id="TCP_test",
            record_offset=69  # 0 + 5 + 64
        ),
        # 第二个TLS-23 ApplicationData
        TLSRecordInfo(
            packet_number=30,
            content_type=23,
            version=(3, 3),
            length=32,
            is_complete=True,
            spans_packets=[30],
            tcp_stream_id="TCP_test",
            record_offset=202  # 69 + 5 + 128
        ),
        # TLS-21 Alert
        TLSRecordInfo(
            packet_number=30,
            content_type=21,
            version=(3, 3),
            length=2,
            is_complete=True,
            spans_packets=[30],
            tcp_stream_id="TCP_test",
            record_offset=239  # 202 + 5 + 32
        )
    ]
    
    rule_generator = TLSMaskRuleGenerator({'verbose': True})
    rules = rule_generator.generate_rules(records)
    
    tls22_rules = [r for r in rules if r.tls_record_type == 22]
    tls23_rules = [r for r in rules if r.tls_record_type == 23]
    tls21_rules = [r for r in rules if r.tls_record_type == 21]
    
    print(f"规则分布:")
    print(f"  TLS-22规则: {len(tls22_rules)} (期望1)")
    print(f"  TLS-23规则: {len(tls23_rules)} (期望2)")
    print(f"  TLS-21规则: {len(tls21_rules)} (期望1)")
    
    # 检查TLS-23规则是否正确
    tls23_records = [r for r in records if r.content_type == 23]
    if len(tls23_rules) != len(tls23_records):
        print(f"🚨 TLS-23规则数量错误: 期望{len(tls23_records)}, 实际{len(tls23_rules)}")
    
    # 详细检查每个TLS-23记录的头部保护
    print(f"\nTLS-23头部保护详细检查:")
    for i, record in enumerate(tls23_records):
        record_header_start = record.record_offset
        record_header_end = record.record_offset + 5
        
        print(f"  TLS-23记录{i+1}: 偏移{record.record_offset}, 头部[{record_header_start}:{record_header_end}]")
        
        # 检查所有规则，看是否有误掩码这个头部
        for rule in rules:
            if rule.action == MaskAction.MASK_PAYLOAD:
                if (rule.absolute_mask_start <= record_header_start < rule.absolute_mask_end):
                    print(f"    🚨 头部被TLS-{rule.tls_record_type}规则[{rule.absolute_mask_start}:{rule.absolute_mask_end}]错误掩码!")

def main():
    """主测试函数"""
    print("🔍 多TLS-23记录掩码问题深度调试")
    print("=" * 60)
    
    # 测试序列
    test_single_tls23_in_packet()
    test_two_tls23_in_packet()
    test_three_tls23_in_packet()
    test_mixed_tls_types_with_multiple_tls23()
    
    print(f"\n" + "=" * 60)
    print("🔍 测试完成")

if __name__ == "__main__":
    main() 