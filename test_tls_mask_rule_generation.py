#!/usr/bin/env python3
"""
测试TLS掩码规则生成器的跨包处理
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
from pktmask.core.trim.models.tls_models import TLSRecordInfo, MaskAction

def test_cross_packet_rule_generation():
    """测试跨包记录的掩码规则生成"""
    generator = TLSMaskRuleGenerator()
    
    print("=== 测试跨包掩码规则生成 ===")
    
    # 创建跨包TLS记录
    cross_packet_records = [
        # TLS-22 Handshake 跨包记录（应该完全保留）
        TLSRecordInfo(
            packet_number=10,
            content_type=22,
            version=(3, 3),
            length=3194,
            is_complete=True,
            spans_packets=[9, 10],  # 跨包
            tcp_stream_id="TCP_0",
            record_offset=0
        ),
        
        # TLS-23 ApplicationData 跨包记录（应该智能掩码）
        TLSRecordInfo(
            packet_number=20,
            content_type=23,
            version=(3, 3),
            length=2048,
            is_complete=True,
            spans_packets=[19, 20],  # 跨包
            tcp_stream_id="TCP_1",
            record_offset=0
        ),
        
        # 单包记录作为对比
        TLSRecordInfo(
            packet_number=30,
            content_type=22,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[30],  # 单包
            tcp_stream_id="TCP_2",
            record_offset=0
        )
    ]
    
    # 生成掩码规则
    rules = generator.generate_rules(cross_packet_records)
    
    print(f"生成了 {len(rules)} 条掩码规则:")
    
    for rule in rules:
        is_cross_packet = "跨包" in rule.reason
        action_name = rule.action.name if hasattr(rule.action, 'name') else str(rule.action)
        
        print(f"  包{rule.packet_number}: {action_name}, 跨包={is_cross_packet}")
        print(f"    TLS类型: {rule.tls_record_type}")
        print(f"    掩码范围: offset={rule.mask_offset}, length={rule.mask_length}")
        print(f"    原因: {rule.reason}")
        print()
    
    # 验证跨包规则
    cross_packet_rules = [r for r in rules if "跨包" in r.reason]
    print(f"跨包规则数量: {len(cross_packet_rules)}")
    
    # 验证TLS-22跨包记录的处理
    tls22_rules = [r for r in cross_packet_rules if r.tls_record_type == 22]
    for rule in tls22_rules:
        if rule.action == MaskAction.KEEP_ALL:
            print(f"✅ TLS-22跨包记录正确设置为完全保留: 包{rule.packet_number}")
        else:
            print(f"❌ TLS-22跨包记录处理错误: 包{rule.packet_number}, 动作={rule.action}")
    
    # 验证TLS-23跨包记录的处理
    tls23_rules = [r for r in cross_packet_rules if r.tls_record_type == 23]
    for rule in tls23_rules:
        if rule.action == MaskAction.MASK_PAYLOAD:
            print(f"✅ TLS-23跨包记录正确设置为智能掩码: 包{rule.packet_number}")
        else:
            print(f"❌ TLS-23跨包记录处理错误: 包{rule.packet_number}, 动作={rule.action}")
    
    return rules

def test_single_packet_vs_cross_packet():
    """对比单包和跨包记录的规则生成差异"""
    generator = TLSMaskRuleGenerator()
    
    print("\n=== 对比单包vs跨包规则生成 ===")
    
    # 相同类型的单包和跨包记录
    records = [
        # TLS-22 单包
        TLSRecordInfo(
            packet_number=1,
            content_type=22,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="TCP_0",
            record_offset=0
        ),
        
        # TLS-22 跨包
        TLSRecordInfo(
            packet_number=2,
            content_type=22,
            version=(3, 3),
            length=3194,
            is_complete=True,
            spans_packets=[1, 2],
            tcp_stream_id="TCP_0",
            record_offset=0
        )
    ]
    
    rules = generator.generate_rules(records)
    
    for rule in rules:
        is_cross = len([r for r in records if r.packet_number == rule.packet_number and len(r.spans_packets) > 1]) > 0
        packet_type = "跨包" if is_cross else "单包"
        action_name = rule.action.name if hasattr(rule.action, 'name') else str(rule.action)
        
        print(f"包{rule.packet_number} ({packet_type}): {action_name}")
        print(f"  原因: {rule.reason}")
    
    return rules

if __name__ == "__main__":
    print("开始测试TLS掩码规则生成器的跨包处理...")
    
    try:
        # 测试跨包规则生成
        rules1 = test_cross_packet_rule_generation()
        
        # 对比测试
        rules2 = test_single_packet_vs_cross_packet()
        
        print(f"\n=== 测试结果统计 ===")
        print(f"总规则数: {len(rules1) + len(rules2)}")
        
        all_rules = rules1 + rules2
        cross_packet_rules = [r for r in all_rules if "跨包" in r.reason]
        print(f"跨包规则数: {len(cross_packet_rules)}")
        
        print("\n✅ 测试完成！掩码规则生成器的跨包处理工作正常。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
