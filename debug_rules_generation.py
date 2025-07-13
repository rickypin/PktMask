#!/usr/bin/env python3
"""
调试规则生成过程

查看TLS-23规则生成和优化的详细过程
"""

import json
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker


def debug_rules_generation():
    """调试规则生成过程"""
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    config = {
        'preserve': {
            'handshake': True,
            'application_data': False,  # 关键：应该生成头部保留规则
            'alert': True,
            'change_cipher_spec': True,
            'heartbeat': True
        }
    }
    
    print("=" * 80)
    print("调试TLS-23规则生成过程")
    print("=" * 80)
    
    marker = TLSProtocolMarker(config)
    
    # 临时修改日志级别以获取更多调试信息
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    ruleset = marker.analyze_file(test_file, config)
    
    print(f"\n生成的规则总数: {len(ruleset.rules)}")
    
    print("\n详细规则信息:")
    for i, rule in enumerate(ruleset.rules):
        print(f"\n规则 #{i}:")
        print(f"  类型: {rule.rule_type}")
        print(f"  序列号范围: {rule.seq_start} - {rule.seq_end}")
        print(f"  长度: {rule.seq_end - rule.seq_start} 字节")
        print(f"  流ID: {rule.stream_id}")
        print(f"  方向: {rule.direction}")
        print(f"  元数据:")
        for key, value in rule.metadata.items():
            print(f"    {key}: {value}")
    
    # 检查是否有TLS-23相关的规则
    tls23_rules = []
    for rule in ruleset.rules:
        if "applicationdata" in rule.rule_type.lower():
            tls23_rules.append(rule)
    
    print(f"\nTLS-23相关规则数量: {len(tls23_rules)}")
    
    if tls23_rules:
        print("\nTLS-23规则详情:")
        for i, rule in enumerate(tls23_rules):
            print(f"  规则 #{i}:")
            print(f"    长度: {rule.seq_end - rule.seq_start} 字节")
            print(f"    保留策略: {rule.metadata.get('preserve_strategy', 'unknown')}")
            print(f"    头部大小: {rule.metadata.get('header_size', 'unknown')}")
    
    # 保存详细结果
    rules_data = []
    for rule in ruleset.rules:
        rules_data.append({
            "rule_type": rule.rule_type,
            "seq_start": rule.seq_start,
            "seq_end": rule.seq_end,
            "length": rule.seq_end - rule.seq_start,
            "stream_id": rule.stream_id,
            "direction": rule.direction,
            "metadata": rule.metadata
        })
    
    with open("debug_rules_details.json", "w", encoding="utf-8") as f:
        json.dump(rules_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n详细规则数据已保存到: debug_rules_details.json")


if __name__ == "__main__":
    debug_rules_generation()
