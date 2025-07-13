#!/usr/bin/env python3
"""
独立测试脚本：分析Marker模块生成的保留规则问题

用于诊断PktMask maskstage双模块架构中Marker模块的规则生成和合并逻辑问题。
"""

import sys
import os
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
from pktmask.core.pipeline.stages.mask_payload_v2.marker.types import KeepRuleSet


def analyze_marker_rules():
    """分析Marker模块生成的保留规则"""
    
    # 测试文件路径
    pcap_path = "tests/samples/tls-single/tls_sample.pcap"
    
    if not os.path.exists(pcap_path):
        print(f"错误：测试文件不存在 {pcap_path}")
        return
    
    print("=" * 60)
    print("PktMask Marker模块规则生成分析")
    print("=" * 60)
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
        
        print("第一步：生成原始保留规则（未优化）")
        print("-" * 40)
        
        # 分析文件生成规则
        ruleset = marker.analyze_file(pcap_path, config['preserve_config'])
        
        # 保存优化前的规则
        rules_before = [
            {
                'stream_id': rule.stream_id,
                'direction': rule.direction,
                'seq_start': rule.seq_start,
                'seq_end': rule.seq_end,
                'length': rule.length,
                'rule_type': rule.rule_type,
                'metadata': rule.metadata
            }
            for rule in ruleset.rules
        ]
        
        print(f"生成规则数量: {len(rules_before)}")
        print()
        
        # 显示每条规则的详细信息
        for i, rule_data in enumerate(rules_before, 1):
            print(f"规则 #{i}:")
            print(f"  流ID: {rule_data['stream_id']}")
            print(f"  方向: {rule_data['direction']}")
            print(f"  序列号范围: {rule_data['seq_start']} - {rule_data['seq_end']}")
            print(f"  长度: {rule_data['length']} 字节")
            print(f"  类型: {rule_data['rule_type']}")
            
            # 显示关键元数据
            metadata = rule_data['metadata']
            if 'tls_content_type' in metadata:
                print(f"  TLS类型: {metadata['tls_content_type']} ({metadata.get('tls_type_name', 'unknown')})")
            if 'frame_number' in metadata:
                print(f"  帧号: {metadata['frame_number']}")
            if 'preserve_strategy' in metadata:
                print(f"  保留策略: {metadata['preserve_strategy']}")
            print()
        
        print("第二步：验证修复效果")
        print("-" * 40)

        # 分析规则的序列号覆盖范围
        print("分析规则覆盖的序列号范围：")
        for i, rule_data in enumerate(rules_before, 1):
            print(f"规则 #{i}: {rule_data['seq_start']} - {rule_data['seq_end']} "
                  f"({rule_data['length']}字节) [{rule_data['rule_type']}]")

        print()
        print("检查序列号间隙（应该被掩码的区域）：")

        # 按流和方向分组分析
        streams = {}
        for rule_data in rules_before:
            key = (rule_data['stream_id'], rule_data['direction'])
            if key not in streams:
                streams[key] = []
            streams[key].append(rule_data)

        for (stream_id, direction), stream_rules in streams.items():
            print(f"\n流 {stream_id} ({direction}):")
            # 按序列号排序
            sorted_rules = sorted(stream_rules, key=lambda r: r['seq_start'])

            for i in range(len(sorted_rules)):
                current_rule = sorted_rules[i]
                print(f"  保留: {current_rule['seq_start']} - {current_rule['seq_end']} "
                      f"[{current_rule['rule_type']}]")

                # 检查与下一个规则之间的间隙
                if i < len(sorted_rules) - 1:
                    next_rule = sorted_rules[i + 1]
                    if current_rule['seq_end'] < next_rule['seq_start']:
                        gap_start = current_rule['seq_end']
                        gap_end = next_rule['seq_start']
                        gap_size = gap_end - gap_start
                        print(f"  掩码: {gap_start} - {gap_end} ({gap_size}字节) ✓")

        print("\n第三步：问题分析")
        print("-" * 40)

        # 检查是否还有过大的规则
        large_rules = [r for r in rules_before if r['length'] > 100]
        if large_rules:
            print("⚠️  发现过大的保留规则：")
            for rule in large_rules:
                print(f"  {rule['rule_type']}: {rule['length']}字节")
                print(f"    序列号范围: {rule['seq_start']} - {rule['seq_end']}")
                if '+' in rule['rule_type']:
                    print(f"    ⚠️  这是合并规则，可能包含应被掩码的区域")
        else:
            print("✓ 没有发现过大的保留规则")

        # 保存分析结果到文件
        analysis_result = {
            'pcap_path': pcap_path,
            'config': config,
            'rules_generated': rules_before,
            'statistics': {
                'total_rule_count': len(rules_before),
                'large_rules_count': len(large_rules),
                'tls23_header_rules': len([r for r in rules_before if 'applicationdata_header' in r['rule_type']]),
                'merged_rules': len([r for r in rules_before if '+' in r['rule_type']])
            },
            'analysis': {
                'has_large_rules': len(large_rules) > 0,
                'has_merged_rules': any('+' in r['rule_type'] for r in rules_before)
            }
        }
        
        with open('marker_rules_analysis_fixed.json', 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, indent=2, ensure_ascii=False)

        print(f"修复后分析结果已保存到: marker_rules_analysis_fixed.json")
        
    except Exception as e:
        print(f"分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    analyze_marker_rules()
