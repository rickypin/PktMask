#!/usr/bin/env python3
"""
分析单个TCP数据包中包含多条TLS消息的情况

专门分析Frame 14中的两条TLS-23消息，以及当前实现的问题
"""

import json
import subprocess
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))


def analyze_frame_14_tls_messages():
    """分析Frame 14中的多条TLS消息"""
    print("=" * 80)
    print("分析Frame 14中的多条TLS消息")
    print("=" * 80)
    
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    
    # 1. 使用tshark获取详细的TLS消息信息
    print("\n1. tshark详细分析Frame 14:")
    cmd = [
        "tshark", "-r", test_file,
        "-Y", "frame.number == 14",
        "-T", "json",
        "-e", "frame.number",
        "-e", "tcp.seq_raw",
        "-e", "tcp.len", 
        "-e", "tls.record.content_type",
        "-e", "tls.record.length",
        "-e", "tls.record.opaque_type"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        frame_data = json.loads(result.stdout)[0]
        layers = frame_data["_source"]["layers"]
        
        tcp_seq = int(layers["tcp.seq_raw"][0])
        tcp_len = int(layers["tcp.len"][0])
        content_types = layers["tls.record.content_type"]
        record_lengths = layers["tls.record.length"]
        
        print(f"TCP序列号: {tcp_seq}")
        print(f"TCP载荷长度: {tcp_len}")
        print(f"TLS消息数量: {len(content_types)}")
        
        print("\nTLS消息详情:")
        for i, (content_type, length) in enumerate(zip(content_types, record_lengths)):
            print(f"  消息#{i+1}: 类型={content_type}, 长度={length}字节")
        
        # 2. 计算每个TLS消息在TCP载荷中的位置
        print("\n2. 计算TLS消息在TCP载荷中的位置:")
        current_offset = 0
        tls_message_positions = []
        
        for i, (content_type, length) in enumerate(zip(content_types, record_lengths)):
            tls_record_length = int(length)
            tls_header_size = 5  # TLS记录头部固定5字节
            total_message_size = tls_header_size + tls_record_length
            
            message_start = tcp_seq + current_offset
            message_end = message_start + total_message_size
            header_end = message_start + tls_header_size
            
            tls_message_positions.append({
                "message_index": i + 1,
                "content_type": int(content_type),
                "record_length": tls_record_length,
                "tcp_offset": current_offset,
                "message_start_seq": message_start,
                "message_end_seq": message_end,
                "header_end_seq": header_end,
                "total_size": total_message_size
            })
            
            print(f"  消息#{i+1} (TLS-{content_type}):")
            print(f"    TCP偏移: {current_offset}")
            print(f"    序列号范围: {message_start} - {message_end} (总共{total_message_size}字节)")
            print(f"    头部范围: {message_start} - {header_end} (5字节)")
            print(f"    载荷范围: {header_end} - {message_end} ({tls_record_length}字节)")
            
            current_offset += total_message_size
        
        # 3. 验证计算是否正确
        print(f"\n3. 验证计算:")
        print(f"计算的总偏移: {current_offset}")
        print(f"实际TCP载荷长度: {tcp_len}")
        if current_offset == tcp_len:
            print("✅ 计算正确")
        else:
            print(f"❌ 计算错误，差异: {tcp_len - current_offset}字节")
        
        return tls_message_positions
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        return []


def analyze_current_implementation():
    """分析当前实现的问题"""
    print("\n" + "=" * 80)
    print("分析当前实现的问题")
    print("=" * 80)
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        config = {
            'preserve': {
                'handshake': True,
                'application_data': False,  # 应该生成头部保留规则
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        }
        
        marker = TLSProtocolMarker(config)
        ruleset = marker.analyze_file("tests/samples/tls-single/tls_sample.pcap", config)
        
        # 查找Frame 14相关的规则
        frame_14_rules = []
        for rule in ruleset.rules:
            if rule.metadata.get("frame_number") == "14":
                frame_14_rules.append(rule)
        
        print(f"当前实现为Frame 14生成的规则数量: {len(frame_14_rules)}")
        
        for i, rule in enumerate(frame_14_rules):
            print(f"\n规则#{i+1}:")
            print(f"  类型: {rule.rule_type}")
            print(f"  序列号范围: {rule.seq_start} - {rule.seq_end}")
            print(f"  长度: {rule.seq_end - rule.seq_start}字节")
            print(f"  保留策略: {rule.metadata.get('preserve_strategy', 'unknown')}")
        
        return frame_14_rules
        
    except Exception as e:
        print(f"❌ 当前实现分析失败: {e}")
        return []


def identify_problems_and_solutions(tls_positions, current_rules):
    """识别问题并提出解决方案"""
    print("\n" + "=" * 80)
    print("问题识别和解决方案")
    print("=" * 80)
    
    # 统计应该生成的规则
    expected_tls23_rules = [pos for pos in tls_positions if pos["content_type"] == 23]
    actual_tls23_rules = [rule for rule in current_rules 
                         if "applicationdata" in rule.rule_type.lower()]
    
    print(f"预期TLS-23规则数量: {len(expected_tls23_rules)}")
    print(f"实际TLS-23规则数量: {len(actual_tls23_rules)}")
    
    if len(expected_tls23_rules) > len(actual_tls23_rules):
        print(f"❌ 问题确认: 缺少 {len(expected_tls23_rules) - len(actual_tls23_rules)} 条TLS-23规则")
        
        print("\n预期应该生成的TLS-23头部保留规则:")
        for i, pos in enumerate(expected_tls23_rules):
            print(f"  规则#{i+1}: 序列号 {pos['message_start_seq']} - {pos['header_end_seq']} (5字节头部)")
        
        print("\n根本原因分析:")
        print("1. 当前实现只为整个TCP数据包生成一条规则")
        print("2. 没有解析TCP载荷中的多个TLS消息")
        print("3. 需要修改逻辑以支持单个数据包中的多条TLS消息")
        
        print("\n解决方案:")
        print("1. 修改TLS消息解析逻辑，支持单个TCP数据包中的多条TLS消息")
        print("2. 为每个TLS-23消息分别生成5字节头部保留规则")
        print("3. 确保规则序列号范围精确对应每个TLS消息的头部")
        
        return True
    else:
        print("✅ 当前实现正确")
        return False


def main():
    """主函数"""
    print("分析单个TCP数据包中包含多条TLS消息的问题")
    
    # 分析Frame 14的TLS消息结构
    tls_positions = analyze_frame_14_tls_messages()
    
    # 分析当前实现
    current_rules = analyze_current_implementation()
    
    # 识别问题和解决方案
    has_problems = identify_problems_and_solutions(tls_positions, current_rules)
    
    # 保存分析结果
    analysis_data = {
        "frame_14_tls_messages": tls_positions,
        "current_rules": [
            {
                "rule_type": rule.rule_type,
                "seq_start": rule.seq_start,
                "seq_end": rule.seq_end,
                "length": rule.seq_end - rule.seq_start,
                "metadata": rule.metadata
            } for rule in current_rules
        ],
        "has_problems": has_problems
    }
    
    with open("multiple_tls_messages_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n详细分析结果已保存到: multiple_tls_messages_analysis.json")


if __name__ == "__main__":
    main()
