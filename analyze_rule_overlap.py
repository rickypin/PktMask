#!/usr/bin/env python3
"""
分析规则重叠问题

专门分析为什么大的handshake规则会覆盖TLS-23消息范围
"""

import json
import subprocess
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker


def analyze_rule_overlap_problem():
    """分析规则重叠问题"""
    print("=" * 80)
    print("规则重叠问题分析")
    print("=" * 80)
    
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    config = {
        'preserve': {
            'handshake': True,
            'application_data': False,
            'alert': True,
            'change_cipher_spec': True,
            'heartbeat': True
        }
    }
    
    # 1. 分析Frame 7和Frame 15的详细信息
    print("\n1. 分析Frame 7和Frame 15的详细信息")
    print("-" * 50)
    
    for frame_num in [7, 15]:
        cmd = [
            "tshark", "-r", test_file,
            "-Y", f"frame.number == {frame_num}",
            "-T", "json",
            "-e", "frame.number",
            "-e", "tcp.seq_raw",
            "-e", "tcp.len",
            "-e", "tls.record.content_type",
            "-e", "tls.record.length"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            frame_data = json.loads(result.stdout)[0]
            layers = frame_data["_source"]["layers"]
            
            tcp_seq = int(layers.get("tcp.seq_raw", ["0"])[0])
            tcp_len = int(layers.get("tcp.len", ["0"])[0])
            content_types = layers.get("tls.record.content_type", [])
            record_lengths = layers.get("tls.record.length", [])
            
            print(f"\nFrame {frame_num}:")
            print(f"  TCP序列号: {tcp_seq}")
            print(f"  TCP载荷长度: {tcp_len}")
            print(f"  TCP范围: {tcp_seq} - {tcp_seq + tcp_len}")
            print(f"  TLS内容类型: {content_types}")
            print(f"  TLS记录长度: {record_lengths}")
            
            # 分析TLS消息在TCP载荷中的位置
            if content_types and record_lengths:
                current_offset = 0
                for i, (ct, length) in enumerate(zip(content_types, record_lengths)):
                    if ct and length:
                        tls_start = tcp_seq + current_offset
                        tls_end = tls_start + 5 + int(length)  # 5字节头部 + 载荷
                        print(f"    TLS消息#{i+1} (类型{ct}): {tls_start} - {tls_end}")
                        current_offset += 5 + int(length)
            
        except Exception as e:
            print(f"❌ Frame {frame_num}分析失败: {e}")
    
    # 2. 生成规则并分析重叠
    print("\n2. 生成规则并分析重叠")
    print("-" * 50)
    
    marker = TLSProtocolMarker(config)
    ruleset = marker.analyze_file(test_file, config)
    
    print(f"生成的规则总数: {len(ruleset.rules)}")
    
    # 找到问题规则
    problem_rule = None
    tls23_rule = None
    
    for rule in ruleset.rules:
        if (rule.stream_id == "0" and rule.direction == "reverse" and 
            rule.seq_start <= 3913404815 and rule.seq_end >= 3913404820):
            if "applicationdata" in rule.rule_type.lower():
                tls23_rule = rule
            else:
                problem_rule = rule
    
    if problem_rule and tls23_rule:
        print(f"\n发现重叠规则:")
        print(f"问题规则 (大范围): {problem_rule.seq_start} - {problem_rule.seq_end}")
        print(f"  类型: {problem_rule.rule_type}")
        print(f"  长度: {problem_rule.seq_end - problem_rule.seq_start} 字节")
        
        print(f"TLS-23规则 (小范围): {tls23_rule.seq_start} - {tls23_rule.seq_end}")
        print(f"  类型: {tls23_rule.rule_type}")
        print(f"  长度: {tls23_rule.seq_end - tls23_rule.seq_start} 字节")
        
        # 检查重叠
        overlap_start = max(problem_rule.seq_start, tls23_rule.seq_start)
        overlap_end = min(problem_rule.seq_end, tls23_rule.seq_end)
        
        if overlap_start < overlap_end:
            print(f"\n❌ 规则重叠确认:")
            print(f"  重叠范围: {overlap_start} - {overlap_end}")
            print(f"  重叠长度: {overlap_end - overlap_start} 字节")
            
            # 分析Frame 15在重叠中的位置
            frame15_start = 3913404815
            frame15_end = 3913404926
            
            print(f"\nFrame 15分析:")
            print(f"  Frame 15范围: {frame15_start} - {frame15_end}")
            print(f"  在问题规则中: {'✅' if problem_rule.seq_start <= frame15_start and problem_rule.seq_end >= frame15_end else '❌'}")
            print(f"  在TLS-23规则中: {'✅' if tls23_rule.seq_start <= frame15_start and tls23_rule.seq_end >= frame15_start + 5 else '❌'}")
    
    # 3. 分析解决方案
    print("\n3. 解决方案分析")
    print("-" * 50)
    
    print("问题根源:")
    print("1. Frame 7生成的handshake规则范围过大，覆盖了后续的TLS-23消息")
    print("2. 规则优化过程中，多个handshake规则被合并成一个大规则")
    print("3. 大规则与TLS-23头部规则重叠，导致Masker处理时冲突")
    
    print("\n可能的解决方案:")
    print("1. 修改规则生成逻辑，避免生成过大的规则")
    print("2. 修改规则优化逻辑，避免合并跨越不同消息类型的规则")
    print("3. 修改Masker处理逻辑，优先处理小范围的精确规则")
    
    # 4. 检查Frame 7的TLS消息是否真的需要这么大的范围
    print("\n4. Frame 7 TLS消息范围验证")
    print("-" * 50)
    
    # 使用tshark检查Frame 7到Frame 15之间的所有TLS消息
    cmd_range = [
        "tshark", "-r", test_file,
        "-Y", "frame.number >= 7 and frame.number <= 15 and tls",
        "-T", "json",
        "-e", "frame.number",
        "-e", "tcp.seq_raw",
        "-e", "tcp.len",
        "-e", "tls.record.content_type"
    ]
    
    try:
        result = subprocess.run(cmd_range, capture_output=True, text=True, check=True)
        range_data = json.loads(result.stdout)
        
        print("Frame 7-15之间的TLS消息:")
        for packet in range_data:
            layers = packet["_source"]["layers"]
            frame_num = layers.get("frame.number", [""])[0]
            tcp_seq = layers.get("tcp.seq_raw", [""])[0]
            tcp_len = layers.get("tcp.len", [""])[0]
            content_types = layers.get("tls.record.content_type", [])
            
            if tcp_seq and tcp_len:
                tcp_start = int(tcp_seq)
                tcp_end = tcp_start + int(tcp_len)
                print(f"  Frame {frame_num}: {tcp_start} - {tcp_end}, TLS类型: {content_types}")
        
    except Exception as e:
        print(f"❌ 范围分析失败: {e}")
    
    return {
        "problem_rule": {
            "seq_start": problem_rule.seq_start if problem_rule else None,
            "seq_end": problem_rule.seq_end if problem_rule else None,
            "rule_type": problem_rule.rule_type if problem_rule else None
        } if problem_rule else None,
        "tls23_rule": {
            "seq_start": tls23_rule.seq_start if tls23_rule else None,
            "seq_end": tls23_rule.seq_end if tls23_rule else None,
            "rule_type": tls23_rule.rule_type if tls23_rule else None
        } if tls23_rule else None
    }


def main():
    """主函数"""
    try:
        results = analyze_rule_overlap_problem()
        
        # 保存分析结果
        with open("rule_overlap_analysis_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n详细分析结果已保存到: rule_overlap_analysis_results.json")
        
    except Exception as e:
        print(f"❌ 规则重叠分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
