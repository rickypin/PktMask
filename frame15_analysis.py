#!/usr/bin/env python3
"""
Frame 15问题深度分析

专门分析Frame 15为什么没有被正确掩码处理
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
from pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import PayloadMasker


def analyze_frame15_problem():
    """深度分析Frame 15的问题"""
    print("=" * 80)
    print("Frame 15问题深度分析")
    print("=" * 80)
    
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    config = {
        'preserve': {
            'handshake': True,
            'application_data': False,  # 只保留头部
            'alert': True,
            'change_cipher_spec': True,
            'heartbeat': True
        }
    }
    
    # 1. 使用tshark详细分析Frame 15
    print("\n1. tshark详细分析Frame 15")
    print("-" * 50)
    
    cmd = [
        "tshark", "-r", test_file,
        "-Y", "frame.number == 15",
        "-T", "json",
        "-e", "frame.number",
        "-e", "tcp.stream",
        "-e", "tcp.seq_raw",
        "-e", "tcp.len",
        "-e", "tcp.payload",
        "-e", "ip.src",
        "-e", "ip.dst",
        "-e", "tcp.srcport",
        "-e", "tcp.dstport",
        "-e", "tls.record.content_type",
        "-e", "tls.record.length"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        frame15_data = json.loads(result.stdout)[0]
        layers = frame15_data["_source"]["layers"]
        
        frame15_info = {
            "frame_number": layers.get("frame.number", [""])[0],
            "tcp_stream": layers.get("tcp.stream", [""])[0],
            "tcp_seq_raw": layers.get("tcp.seq_raw", [""])[0],
            "tcp_len": layers.get("tcp.len", [""])[0],
            "tcp_payload": layers.get("tcp.payload", [""])[0],
            "ip_src": layers.get("ip.src", [""])[0],
            "ip_dst": layers.get("ip.dst", [""])[0],
            "tcp_srcport": layers.get("tcp.srcport", [""])[0],
            "tcp_dstport": layers.get("tcp.dstport", [""])[0],
            "tls_content_types": layers.get("tls.record.content_type", []),
            "tls_record_lengths": layers.get("tls.record.length", [])
        }
        
        print(f"Frame 15详细信息:")
        print(f"  TCP流: {frame15_info['tcp_stream']}")
        print(f"  TCP序列号: {frame15_info['tcp_seq_raw']}")
        print(f"  TCP载荷长度: {frame15_info['tcp_len']}")
        print(f"  源地址: {frame15_info['ip_src']}:{frame15_info['tcp_srcport']}")
        print(f"  目标地址: {frame15_info['ip_dst']}:{frame15_info['tcp_dstport']}")
        print(f"  TLS内容类型: {frame15_info['tls_content_types']}")
        print(f"  TLS记录长度: {frame15_info['tls_record_lengths']}")
        
        # 分析TCP载荷
        if frame15_info['tcp_payload']:
            payload_bytes = bytes.fromhex(frame15_info['tcp_payload'].replace(":", ""))
            print(f"  TCP载荷前32字节: {payload_bytes[:32].hex()}")
            
            # 检查是否全为零
            all_zero = all(b == 0 for b in payload_bytes)
            print(f"  载荷是否全为零: {all_zero}")
            
            if not all_zero:
                # 找到非零字节的位置
                non_zero_positions = [i for i, b in enumerate(payload_bytes) if b != 0]
                print(f"  非零字节位置: {non_zero_positions[:10]}...")  # 只显示前10个
        
    except Exception as e:
        print(f"❌ tshark分析失败: {e}")
        return None
    
    # 2. 检查Marker生成的规则
    print("\n2. 检查Marker生成的Frame 15相关规则")
    print("-" * 50)
    
    marker = TLSProtocolMarker(config)
    ruleset = marker.analyze_file(test_file, config)
    
    frame15_rules = []
    for rule in ruleset.rules:
        if rule.metadata.get("frame_number") == "15":
            frame15_rules.append(rule)
    
    print(f"Frame 15相关规则数量: {len(frame15_rules)}")
    
    for i, rule in enumerate(frame15_rules):
        print(f"\n规则#{i+1}:")
        print(f"  类型: {rule.rule_type}")
        print(f"  序列号范围: {rule.seq_start} - {rule.seq_end}")
        print(f"  长度: {rule.seq_end - rule.seq_start}字节")
        print(f"  流ID: {rule.stream_id}")
        print(f"  方向: {rule.direction}")
        print(f"  保留策略: {rule.metadata.get('preserve_strategy', 'unknown')}")
    
    # 3. 构建流标识和方向，检查匹配
    print("\n3. 流标识和方向匹配检查")
    print("-" * 50)
    
    # 根据Frame 15的信息构建流标识
    ip_src = frame15_info['ip_src']
    ip_dst = frame15_info['ip_dst']
    tcp_srcport = int(frame15_info['tcp_srcport'])
    tcp_dstport = int(frame15_info['tcp_dstport'])
    
    # 构建流标识（按照Masker的逻辑）
    if ip_src < ip_dst or (ip_src == ip_dst and tcp_srcport < tcp_dstport):
        stream_id = f"{ip_src}:{tcp_srcport}-{ip_dst}:{tcp_dstport}"
        direction = "forward"
    else:
        stream_id = f"{ip_dst}:{tcp_dstport}-{ip_src}:{tcp_srcport}"
        direction = "reverse"
    
    print(f"Frame 15流标识: {stream_id}")
    print(f"Frame 15方向: {direction}")
    
    # 检查是否有匹配的规则
    matching_rules = []
    for rule in ruleset.rules:
        if rule.stream_id == frame15_info['tcp_stream'] and rule.direction == direction:
            matching_rules.append(rule)
    
    print(f"匹配的规则数量: {len(matching_rules)}")
    
    for rule in matching_rules:
        tcp_seq = int(frame15_info['tcp_seq_raw'])
        tcp_len = int(frame15_info['tcp_len'])
        tcp_end = tcp_seq + tcp_len
        
        # 检查序列号范围是否重叠
        overlap = not (rule.seq_end <= tcp_seq or rule.seq_start >= tcp_end)
        print(f"  规则 {rule.seq_start}-{rule.seq_end} vs TCP {tcp_seq}-{tcp_end}: {'重叠' if overlap else '不重叠'}")
    
    # 4. 模拟Masker处理过程
    print("\n4. 模拟Masker处理过程")
    print("-" * 50)
    
    try:
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp_file:
            output_file = tmp_file.name
        
        masker = PayloadMasker({})
        
        # 启用调试日志
        import logging
        logging.basicConfig(level=logging.DEBUG)
        
        masking_stats = masker.apply_masking(test_file, output_file, ruleset)
        
        print(f"Masker处理结果:")
        print(f"  成功: {masking_stats.success}")
        print(f"  处理包数: {masking_stats.processed_packets}")
        print(f"  修改包数: {masking_stats.modified_packets}")
        print(f"  掩码字节数: {masking_stats.masked_bytes}")
        print(f"  保留字节数: {masking_stats.preserved_bytes}")
        
        # 检查输出文件中的Frame 15
        print("\n5. 检查输出文件中的Frame 15")
        print("-" * 50)
        
        cmd_output = [
            "tshark", "-r", output_file,
            "-Y", "frame.number == 15",
            "-T", "json",
            "-e", "tcp.payload"
        ]
        
        result_output = subprocess.run(cmd_output, capture_output=True, text=True, check=True)
        output_data = json.loads(result_output.stdout)
        
        if output_data:
            output_layers = output_data[0]["_source"]["layers"]
            output_payload = output_layers.get("tcp.payload", [""])[0]
            
            if output_payload:
                output_bytes = bytes.fromhex(output_payload.replace(":", ""))
                print(f"输出文件Frame 15载荷前32字节: {output_bytes[:32].hex()}")
                
                # 比较原始和输出载荷
                original_bytes = bytes.fromhex(frame15_info['tcp_payload'].replace(":", ""))
                
                if original_bytes == output_bytes:
                    print("❌ Frame 15载荷没有被修改")
                else:
                    print("✅ Frame 15载荷已被修改")
                    
                    # 检查哪些字节被修改
                    modified_positions = []
                    for i, (orig, new) in enumerate(zip(original_bytes, output_bytes)):
                        if orig != new:
                            modified_positions.append(i)
                    
                    print(f"修改的字节位置: {modified_positions[:10]}...")
        
        return {
            "frame15_info": frame15_info,
            "frame15_rules": [
                {
                    "rule_type": rule.rule_type,
                    "seq_start": rule.seq_start,
                    "seq_end": rule.seq_end,
                    "stream_id": rule.stream_id,
                    "direction": rule.direction,
                    "metadata": rule.metadata
                } for rule in frame15_rules
            ],
            "stream_id": stream_id,
            "direction": direction,
            "matching_rules": len(matching_rules),
            "masking_stats": {
                "success": masking_stats.success,
                "processed_packets": masking_stats.processed_packets,
                "modified_packets": masking_stats.modified_packets,
                "masked_bytes": masking_stats.masked_bytes,
                "preserved_bytes": masking_stats.preserved_bytes
            }
        }
        
    except Exception as e:
        print(f"❌ Masker模拟失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    try:
        results = analyze_frame15_problem()
        
        if results:
            # 保存分析结果
            with open("frame15_analysis_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"\n详细分析结果已保存到: frame15_analysis_results.json")
        
    except Exception as e:
        print(f"❌ Frame 15分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
