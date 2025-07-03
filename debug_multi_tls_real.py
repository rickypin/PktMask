#!/usr/bin/env python3
"""
调试真实TLS数据中的多TLS记录掩码问题
专门分析同一包中包含多个TLS-23记录时的掩码行为
"""

import sys
import os
sys.path.insert(0, '/Users/ricky/Downloads/PktMask/src')

from pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer
from pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
from pktmask.core.trim.models.tls_models import TLSRecordInfo

def analyze_pcap_tls_records(pcap_file):
    """分析PCAP文件中的TLS记录，重点关注多TLS-23记录的掩码问题"""
    
    if not os.path.exists(pcap_file):
        print(f"❌ PCAP文件不存在: {pcap_file}")
        return
    
    print(f"🔍 分析真实TLS数据: {pcap_file}")
    
    # 初始化分析器
    analyzer = TSharkTLSAnalyzer({'verbose': True})
    
    try:
        # 分析TLS记录
        tls_records = analyzer.analyze_file(pcap_file)
        
        print(f"📊 总共发现 {len(tls_records)} 个TLS记录")
        
        # 按包分组，寻找多记录包
        packet_groups = {}
        for record in tls_records:
            packet_num = record.packet_number
            if packet_num not in packet_groups:
                packet_groups[packet_num] = []
            packet_groups[packet_num].append(record)
        
        # 找出包含多个TLS记录的包
        multi_record_packets = {k: v for k, v in packet_groups.items() if len(v) > 1}
        
        # 特别关注包含多个TLS-23记录的包
        multi_tls23_packets = {}
        for packet_num, records in multi_record_packets.items():
            tls23_records = [r for r in records if r.content_type == 23]
            if len(tls23_records) > 1:
                multi_tls23_packets[packet_num] = records
        
        if multi_tls23_packets:
            print(f"\n🚨 发现 {len(multi_tls23_packets)} 个包含多个TLS-23记录的包:")
            for packet_num, records in multi_tls23_packets.items():
                analyze_multi_tls23_packet(packet_num, records)
        else:
            print(f"\n✅ 未发现包含多个TLS-23记录的包")
            
        if multi_record_packets:
            print(f"\n🔍 发现 {len(multi_record_packets)} 个包含多TLS记录的包:")
            for packet_num, records in multi_record_packets.items():
                print(f"\n包 {packet_num} - {len(records)} 个TLS记录:")
                for i, record in enumerate(records):
                    print(f"  记录{i+1}: TLS-{record.content_type}, 偏移={record.record_offset}, 长度={record.length}")
                    
                # 生成掩码规则并分析
                rule_generator = TLSMaskRuleGenerator({'verbose': True})
                rules = rule_generator.generate_rules(records)
                
                print(f"  生成 {len(rules)} 条掩码规则:")
                for rule in rules:
                    print(f"    TLS-{rule.tls_record_type}: {rule.action.name}")
                    print(f"      记录边界: [{rule.tls_record_offset}:{rule.tls_record_offset + rule.tls_record_length}]")
                    if rule.action.name == 'MASK_PAYLOAD':
                        print(f"      掩码边界: [{rule.absolute_mask_start}:{rule.absolute_mask_end}]")
                        print(f"      头部保护: {rule.mask_offset}字节")
                        
                # 检查重叠
                print("  重叠检查:")
                mask_rules = [r for r in rules if r.action.name == 'MASK_PAYLOAD']
                check_overlap_issues(rules, mask_rules)
                    
        else:
            print(f"\n✅ 该文件中没有包含多TLS记录的包")
            
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

def analyze_multi_tls23_packet(packet_num, records):
    """专门分析包含多个TLS-23记录的包"""
    print(f"\n🚨 包 {packet_num} - 多TLS-23记录分析:")
    
    tls23_records = [r for r in records if r.content_type == 23]
    other_records = [r for r in records if r.content_type != 23]
    
    print(f"  包含 {len(tls23_records)} 个TLS-23 ApplicationData记录")
    print(f"  包含 {len(other_records)} 个其他类型TLS记录")
    
    # 分析每个TLS-23记录
    for i, record in enumerate(tls23_records):
        print(f"\n  TLS-23记录 {i+1}:")
        print(f"    偏移: {record.record_offset}")
        print(f"    长度: {record.length}字节")
        print(f"    期望头部范围: [{record.record_offset}:{record.record_offset + 5}]")
        print(f"    期望载荷范围: [{record.record_offset + 5}:{record.record_offset + 5 + record.length}]")
    
    # 生成掩码规则
    rule_generator = TLSMaskRuleGenerator({'verbose': True})
    rules = rule_generator.generate_rules(records)
    
    tls23_rules = [r for r in rules if r.tls_record_type == 23]
    
    print(f"\n  生成的TLS-23掩码规则数量: {len(tls23_rules)}")
    
    if len(tls23_rules) != len(tls23_records):
        print(f"  🚨 警告: 记录数({len(tls23_records)}) != 规则数({len(tls23_rules)})")
        print(f"  🚨 可能存在规则合并问题！")
    
    # 分析每个TLS-23规则
    for i, rule in enumerate(tls23_rules):
        print(f"\n  TLS-23规则 {i+1}:")
        print(f"    记录偏移: {rule.tls_record_offset}")
        print(f"    记录长度: {rule.tls_record_length}")
        print(f"    掩码偏移: {rule.mask_offset}")
        print(f"    掩码长度: {rule.mask_length}")
        print(f"    绝对掩码范围: [{rule.absolute_mask_start}:{rule.absolute_mask_end}]")
        print(f"    原因: {rule.reason}")
    
    # 检查头部保护问题
    print(f"\n  🔍 TLS-23头部保护检查:")
    check_tls23_header_protection(tls23_records, tls23_rules)

def check_tls23_header_protection(records, rules):
    """检查TLS-23记录的头部保护是否正确"""
    
    for i, record in enumerate(records):
        expected_header_start = record.record_offset
        expected_header_end = record.record_offset + 5
        expected_payload_start = record.record_offset + 5
        expected_payload_end = record.record_offset + 5 + record.length
        
        print(f"    记录{i+1} 期望头部保护: [{expected_header_start}:{expected_header_end}]")
        print(f"    记录{i+1} 期望载荷掩码: [{expected_payload_start}:{expected_payload_end}]")
        
        # 检查是否有对应的规则
        corresponding_rule = None
        for rule in rules:
            if (rule.tls_record_offset <= expected_header_start < 
                rule.tls_record_offset + rule.tls_record_length):
                corresponding_rule = rule
                break
        
        if corresponding_rule:
            actual_header_protection_end = corresponding_rule.tls_record_offset + corresponding_rule.mask_offset
            actual_mask_start = corresponding_rule.absolute_mask_start
            actual_mask_end = corresponding_rule.absolute_mask_end
            
            print(f"    对应规则头部保护: [{corresponding_rule.tls_record_offset}:{actual_header_protection_end}]")
            print(f"    对应规则载荷掩码: [{actual_mask_start}:{actual_mask_end}]")
            
            # 检查头部是否被正确保护
            if actual_header_protection_end != expected_header_end:
                print(f"    🚨 头部保护不正确: 期望{expected_header_end}, 实际{actual_header_protection_end}")
            
            # 检查载荷掩码是否正确
            if actual_mask_start != expected_payload_start:
                print(f"    🚨 载荷掩码起始不正确: 期望{expected_payload_start}, 实际{actual_mask_start}")
            
            # 检查头部是否被意外掩码
            if actual_mask_start < expected_header_end:
                print(f"    🚨 严重问题: TLS-23头部被错误掩码! 掩码起始{actual_mask_start} < 头部结束{expected_header_end}")
        else:
            print(f"    🚨 未找到对应的掩码规则!")

def check_overlap_issues(all_rules, mask_rules):
    """检查掩码规则重叠问题"""
    if len(mask_rules) < 2:
        print("    无重叠风险（掩码规则少于2个）")
        return
    
    # 按绝对偏移排序
    sorted_rules = sorted(mask_rules, key=lambda r: r.absolute_mask_start)
    
    overlaps = []
    for i in range(len(sorted_rules) - 1):
        current = sorted_rules[i]
        next_rule = sorted_rules[i + 1]
        
        if current.absolute_mask_end > next_rule.absolute_mask_start:
            overlaps.append((current, next_rule))
    
    if overlaps:
        print(f"    🚨 发现 {len(overlaps)} 个重叠问题:")
        for current, next_rule in overlaps:
            print(f"      TLS-{current.tls_record_type}[{current.absolute_mask_start}:{current.absolute_mask_end}] 与 ")
            print(f"      TLS-{next_rule.tls_record_type}[{next_rule.absolute_mask_start}:{next_rule.absolute_mask_end}] 重叠")
    else:
        print("    ✅ 无掩码重叠问题")

def main():
    """主函数"""
    # 测试文件列表
    test_files = [
        "/Users/ricky/Downloads/PktMask/tests/data/tls/tls_1_2_double_vlan.pcap",
        "/Users/ricky/Downloads/PktMask/tests/data/tls/tls_1_2_plainip.pcap",
        "/Users/ricky/Downloads/PktMask/tests/data/tls/tls_1_2-2.pcapng"
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\n{'='*60}")
            analyze_pcap_tls_records(test_file)
        else:
            print(f"⏭️  跳过不存在的文件: {test_file}")

if __name__ == "__main__":
    main() 