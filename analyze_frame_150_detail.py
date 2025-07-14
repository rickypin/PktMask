#!/usr/bin/env python3
"""
深度分析帧150的特殊情况
为什么这个跨段TLS消息与其他正常处理的跨段消息不同
"""

import subprocess
import json
from pathlib import Path

def analyze_frame_sequence_around_150():
    """分析帧150前后的序列，理解TCP重组上下文"""
    pcap_file = 'tests/data/tls/tls_1_0_multi_segment_google-https.pcap'
    
    print("=== 分析帧150前后的TCP序列 ===")
    
    # 获取帧145-155的详细信息
    cmd = [
        'tshark', '-r', pcap_file,
        '-Y', 'frame.number >= 145 and frame.number <= 155 and tcp.stream == 0',
        '-T', 'fields',
        '-e', 'frame.number',
        '-e', 'tcp.seq_raw',
        '-e', 'tcp.len',
        '-e', 'tcp.segments',
        '-e', 'tcp.reassembled_in',
        '-e', 'tls.record.content_type',
        '-e', 'tls.record.length'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        
        print("帧号\t序列号\t\t载荷长度\t段信息\t\t重组到\tTLS类型\tTLS长度")
        print("-" * 80)
        
        for line in lines:
            if line.strip():
                fields = line.split('\t')
                frame = fields[0] if len(fields) > 0 else ""
                seq = fields[1] if len(fields) > 1 else ""
                tcp_len = fields[2] if len(fields) > 2 else ""
                segments = fields[3] if len(fields) > 3 else ""
                reassembled = fields[4] if len(fields) > 4 else ""
                tls_type = fields[5] if len(fields) > 5 else ""
                tls_len = fields[6] if len(fields) > 6 else ""
                
                print(f"{frame}\t{seq}\t{tcp_len}\t\t{segments[:20]}...\t{reassembled}\t{tls_type}\t{tls_len}")
                
    except Exception as e:
        print(f"分析失败: {e}")

def analyze_tcp_payload_hex_comparison():
    """对比帧150与正常跨段帧的载荷十六进制数据"""
    pcap_file = 'tests/data/tls/tls_1_0_multi_segment_google-https.pcap'
    
    print("\n=== 对比载荷十六进制数据 ===")
    
    # 分析帧150（失败）
    frames_to_analyze = [150, 16, 18]  # 150失败，16和18正常
    
    for frame_num in frames_to_analyze:
        print(f"\n--- 帧 {frame_num} ---")
        
        # 获取载荷
        cmd = [
            'tshark', '-r', pcap_file,
            '-Y', f'frame.number=={frame_num}',
            '-T', 'fields', '-e', 'tcp.payload'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            payload_hex = result.stdout.strip()
            
            if payload_hex:
                print(f"载荷长度: {len(payload_hex)//2} 字节")
                print(f"前32字节: {payload_hex[:64]}")
                
                # 尝试解析TLS头
                if len(payload_hex) >= 10:
                    try:
                        content_type = int(payload_hex[0:2], 16)
                        version = payload_hex[2:6]
                        length = int(payload_hex[6:10], 16)
                        
                        print(f"TLS解析: 类型={content_type}, 版本=0x{version}, 长度={length}")
                        
                        # 检查是否为标准TLS类型
                        tls_types = {20: "ChangeCipherSpec", 21: "Alert", 22: "Handshake", 23: "ApplicationData", 24: "Heartbeat"}
                        if content_type in tls_types:
                            print(f"  -> 标准TLS类型: {tls_types[content_type]}")
                        else:
                            print(f"  -> ⚠️ 非标准TLS类型: {content_type}")
                            
                        # 检查长度合理性
                        if length > 16384:  # TLS记录最大长度
                            print(f"  -> ⚠️ 异常长度: {length} (超过TLS最大记录长度)")
                            
                    except ValueError as e:
                        print(f"TLS解析失败: {e}")
                        
        except Exception as e:
            print(f"帧{frame_num}分析失败: {e}")

def analyze_tls_reassembly_context():
    """分析TLS重组上下文，理解为什么帧150被特殊处理"""
    pcap_file = 'tests/data/tls/tls_1_0_multi_segment_google-https.pcap'
    
    print("\n=== 分析TLS重组上下文 ===")
    
    # 查找流0中所有的TLS记录
    cmd = [
        'tshark', '-r', pcap_file,
        '-Y', 'tcp.stream == 0 and tls',
        '-T', 'fields',
        '-e', 'frame.number',
        '-e', 'tcp.seq_raw',
        '-e', 'tcp.len',
        '-e', 'tls.record.content_type',
        '-e', 'tls.record.length',
        '-e', 'tcp.segments',
        '-e', 'tcp.reassembled_in'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        
        print("流0中的TLS记录:")
        print("帧号\t序列号\t\t载荷长度\tTLS类型\tTLS长度\t段信息\t重组到")
        print("-" * 90)
        
        for line in lines:
            if line.strip():
                fields = line.split('\t')
                if len(fields) >= 5:
                    frame = fields[0]
                    seq = fields[1]
                    tcp_len = fields[2]
                    tls_type = fields[3]
                    tls_len = fields[4]
                    segments = fields[5] if len(fields) > 5 else ""
                    reassembled = fields[6] if len(fields) > 6 else ""
                    
                    marker = "⚠️" if frame == "150" else "  "
                    print(f"{marker}{frame}\t{seq}\t{tcp_len}\t\t{tls_type}\t{tls_len}\t{segments[:15]}...\t{reassembled}")
                    
    except Exception as e:
        print(f"TLS重组分析失败: {e}")

def check_wireshark_tls_dissector_behavior():
    """检查Wireshark TLS解析器对帧150的具体行为"""
    pcap_file = 'tests/data/tls/tls_1_0_multi_segment_google-https.pcap'
    
    print("\n=== 检查Wireshark TLS解析器行为 ===")
    
    # 获取帧150的完整TLS解析信息
    cmd = [
        'tshark', '-r', pcap_file,
        '-Y', 'frame.number==150',
        '-T', 'json', '-V'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        frame_data = json.loads(result.stdout)[0]
        layers = frame_data['_source']['layers']
        
        if 'tls' in layers:
            tls_layer = layers['tls']
            print("TLS层详细信息:")
            
            # 检查所有TLS相关字段
            for key, value in tls_layer.items():
                if key.startswith('tls.'):
                    print(f"  {key}: {value}")
                    
            # 特别关注记录信息
            if 'tls.record' in str(tls_layer):
                print("\nTLS记录信息:")
                for key, value in tls_layer.items():
                    if 'record' in key:
                        print(f"  {key}: {value}")
        else:
            print("帧150没有TLS层信息")
            
        # 检查TCP层的段信息
        if 'tcp' in layers:
            tcp_layer = layers['tcp']
            print("\nTCP段信息:")
            for key, value in tcp_layer.items():
                if 'segment' in key or 'reassembl' in key:
                    print(f"  {key}: {value}")
                    
    except Exception as e:
        print(f"Wireshark解析器分析失败: {e}")

def main():
    """主分析函数"""
    print("帧150特殊情况深度分析")
    print("=" * 50)
    
    if not Path('tests/data/tls/tls_1_0_multi_segment_google-https.pcap').exists():
        print("测试文件不存在")
        return
    
    # 1. 分析帧150前后的序列
    analyze_frame_sequence_around_150()
    
    # 2. 对比载荷十六进制数据
    analyze_tcp_payload_hex_comparison()
    
    # 3. 分析TLS重组上下文
    analyze_tls_reassembly_context()
    
    # 4. 检查Wireshark解析器行为
    check_wireshark_tls_dissector_behavior()
    
    print("\n" + "=" * 50)
    print("分析完成")

if __name__ == '__main__':
    main()
