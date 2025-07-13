#!/usr/bin/env python3
"""
最终验证脚本：确认Marker模块修复效果

验证PktMask maskstage双模块架构中Marker模块的简化策略是否成功解决了
TLS消息边界丢失和过度合并的问题。
"""

import sys
import os
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker


def final_verification():
    """最终验证修复效果"""
    
    pcap_path = "tests/samples/tls-single/tls_sample.pcap"
    
    if not os.path.exists(pcap_path):
        print(f"错误：测试文件不存在 {pcap_path}")
        return
    
    print("=" * 70)
    print("PktMask Marker模块修复效果最终验证")
    print("=" * 70)
    print(f"测试文件: {pcap_path}")
    print()
    
    # 配置TLS标记器
    config = {
        'preserve_config': {
            'handshake': True,          # TLS-22
            'change_cipher_spec': True, # TLS-20
            'alert': True,              # TLS-21
            'heartbeat': True,          # TLS-24
            'application_data': False   # TLS-23 只保留头部
        }
    }
    
    try:
        # 创建TLS标记器
        marker = TLSProtocolMarker(config)
        
        # 分析文件生成规则
        ruleset = marker.analyze_file(pcap_path, config['preserve_config'])
        
        print("✅ 修复验证结果")
        print("-" * 50)
        
        # 统计规则类型
        rule_stats = {}
        tls23_rules = []
        large_rules = []
        merged_rules = []
        
        for rule in ruleset.rules:
            rule_type = rule.rule_type
            if rule_type not in rule_stats:
                rule_stats[rule_type] = 0
            rule_stats[rule_type] += 1
            
            # 检查TLS-23规则
            if 'applicationdata' in rule_type:
                tls23_rules.append(rule)
            
            # 检查大规则
            if rule.length > 500:
                large_rules.append(rule)
            
            # 检查合并规则
            if '+' in rule_type:
                merged_rules.append(rule)
        
        print(f"总规则数量: {len(ruleset.rules)}")
        print(f"规则类型分布:")
        for rule_type, count in sorted(rule_stats.items()):
            print(f"  {rule_type}: {count}条")
        
        print()
        print("🔍 关键验证点:")
        
        # 验证点1：是否消除了合并规则
        if merged_rules:
            print(f"❌ 仍存在 {len(merged_rules)} 条合并规则:")
            for rule in merged_rules:
                print(f"   {rule.rule_type} ({rule.length}字节)")
        else:
            print("✅ 已消除所有合并规则")
        
        # 验证点2：TLS-23规则是否正确
        if tls23_rules:
            print(f"✅ TLS-23 ApplicationData规则: {len(tls23_rules)}条")
            all_header_only = True
            for rule in tls23_rules:
                if rule.length != 5:
                    all_header_only = False
                    print(f"   ❌ 规则长度异常: {rule.length}字节 (应为5字节)")
                else:
                    print(f"   ✅ 头部规则: {rule.seq_start}-{rule.seq_end} (5字节)")
            
            if all_header_only:
                print("✅ 所有TLS-23规则都是正确的5字节头部规则")
        else:
            print("❌ 没有找到TLS-23规则")
        
        # 验证点3：大规则是否合理
        if large_rules:
            print(f"📊 大规则分析 ({len(large_rules)}条):")
            for rule in large_rules:
                print(f"   {rule.rule_type}: {rule.length}字节")
                if 'handshake' in rule.rule_type.lower() and not '+' in rule.rule_type:
                    print(f"      ✅ 单个Handshake消息，合理")
                else:
                    print(f"      ⚠️  需要进一步检查")
        
        # 验证点4：序列号覆盖分析
        print()
        print("📍 序列号覆盖分析:")
        
        # 按流和方向分组
        streams = {}
        for rule in ruleset.rules:
            key = (rule.stream_id, rule.direction)
            if key not in streams:
                streams[key] = []
            streams[key].append(rule)
        
        total_preserved = 0
        total_gaps = 0
        
        for (stream_id, direction), stream_rules in streams.items():
            print(f"\n流 {stream_id} ({direction}):")
            sorted_rules = sorted(stream_rules, key=lambda r: r.seq_start)
            
            stream_preserved = 0
            stream_gaps = 0
            
            for i, rule in enumerate(sorted_rules):
                stream_preserved += rule.length
                print(f"  保留: {rule.seq_start}-{rule.seq_end} "
                      f"({rule.length}字节) [{rule.rule_type}]")
                
                # 检查间隙
                if i < len(sorted_rules) - 1:
                    next_rule = sorted_rules[i + 1]
                    if rule.seq_end < next_rule.seq_start:
                        gap_size = next_rule.seq_start - rule.seq_end
                        stream_gaps += gap_size
                        print(f"  掩码: {rule.seq_end}-{next_rule.seq_start} "
                              f"({gap_size}字节) ✓")
            
            total_preserved += stream_preserved
            total_gaps += stream_gaps
            print(f"  小计: 保留{stream_preserved}字节, 掩码{stream_gaps}字节")
        
        print(f"\n总计: 保留{total_preserved}字节, 掩码{total_gaps}字节")
        
        # 最终结论
        print()
        print("🎯 修复效果总结:")
        print("-" * 50)
        
        success_count = 0
        total_checks = 4
        
        if not merged_rules:
            print("✅ 1. 成功消除过度合并规则")
            success_count += 1
        else:
            print("❌ 1. 仍存在合并规则")
        
        if tls23_rules and all(r.length == 5 for r in tls23_rules):
            print("✅ 2. TLS-23头部规则正确")
            success_count += 1
        else:
            print("❌ 2. TLS-23规则有问题")
        
        if large_rules and all('handshake' in r.rule_type.lower() and '+' not in r.rule_type for r in large_rules):
            print("✅ 3. 大规则都是合理的单个Handshake消息")
            success_count += 1
        else:
            print("❌ 3. 存在不合理的大规则")
        
        if total_gaps > 0:
            print("✅ 4. 成功识别出需要掩码的区域")
            success_count += 1
        else:
            print("❌ 4. 没有识别出掩码区域")
        
        print()
        if success_count == total_checks:
            print("🎉 修复完全成功！所有验证点都通过了。")
            print("   单条TLS消息粒度的保留规则策略工作正常。")
        else:
            print(f"⚠️  修复部分成功 ({success_count}/{total_checks})，需要进一步调整。")
        
        # 保存验证结果
        verification_result = {
            'total_rules': len(ruleset.rules),
            'rule_types': rule_stats,
            'merged_rules_count': len(merged_rules),
            'tls23_rules_count': len(tls23_rules),
            'large_rules_count': len(large_rules),
            'total_preserved_bytes': total_preserved,
            'total_masked_bytes': total_gaps,
            'success_rate': f"{success_count}/{total_checks}",
            'verification_passed': success_count == total_checks
        }
        
        with open('final_verification_result.json', 'w', encoding='utf-8') as f:
            json.dump(verification_result, f, indent=2, ensure_ascii=False)
        
        print(f"\n验证结果已保存到: final_verification_result.json")
        
    except Exception as e:
        print(f"验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    final_verification()
