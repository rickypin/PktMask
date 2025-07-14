#!/usr/bin/env python3
"""
深度调试规则匹配问题
分析为什么帧150和帧144仍然被错误匹配
"""

import sys
import subprocess
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def analyze_frame_150_detailed():
    """详细分析帧150的规则匹配问题"""
    print("=== 详细分析帧150规则匹配问题 ===")
    
    pcap_file = 'tests/data/tls/tls_1_0_multi_segment_google-https.pcap'
    frame_number = 150
    
    # 1. 获取帧150的详细信息
    cmd = [
        'tshark', '-r', pcap_file,
        '-Y', f'frame.number=={frame_number}',
        '-T', 'fields',
        '-e', 'frame.number',
        '-e', 'tcp.stream',
        '-e', 'tcp.seq_raw',
        '-e', 'tcp.len',
        '-e', 'ip.src',
        '-e', 'ip.dst',
        '-e', 'tcp.srcport',
        '-e', 'tcp.dstport',
        '-e', 'tcp.payload'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        fields = result.stdout.strip().split('\t')
        
        if len(fields) >= 8:
            frame_num, stream_id, seq_raw, tcp_len, src_ip, dst_ip, src_port, dst_port = fields[:8]
            tcp_payload = fields[8] if len(fields) > 8 else ""
            
            print(f"帧150详细信息:")
            print(f"  流ID: {stream_id}")
            print(f"  序列号: {seq_raw}")
            print(f"  载荷长度: {tcp_len}")
            print(f"  源地址: {src_ip}:{src_port}")
            print(f"  目标地址: {dst_ip}:{dst_port}")
            print(f"  载荷前32字节: {tcp_payload[:64] if tcp_payload else 'N/A'}")
            
            # 2. 分析Marker模块生成的规则
            from pktmask.core.pipeline.stages.mask_payload_v2.marker import TLSProtocolMarker
            
            config = {
                'preserve': {
                    'handshake': True,
                    'application_data': False,
                    'alert': True,
                    'change_cipher_spec': True,
                    'heartbeat': True
                },
                'tshark_path': None,
                'decode_as': []
            }
            
            marker = TLSProtocolMarker(config)
            keep_rules = marker.analyze_file(pcap_file, config)
            
            # 3. 查找影响帧150的所有规则
            frame_seq_start = int(seq_raw)
            frame_seq_end = frame_seq_start + int(tcp_len)
            
            print(f"\n帧150序列号范围: [{frame_seq_start}, {frame_seq_end})")
            
            matching_rules = []
            for rule in keep_rules.rules:
                if rule.stream_id == stream_id:
                    # 检查序列号范围重叠
                    if not (rule.seq_end <= frame_seq_start or rule.seq_start >= frame_seq_end):
                        matching_rules.append(rule)
            
            print(f"\n匹配的规则数: {len(matching_rules)}")
            for i, rule in enumerate(matching_rules):
                print(f"  规则{i+1}:")
                print(f"    范围: [{rule.seq_start}, {rule.seq_end})")
                print(f"    类型: {rule.rule_type}")
                print(f"    方向: {rule.direction}")
                print(f"    策略: {rule.metadata.get('preserve_strategy', 'N/A')}")
                print(f"    元数据: {rule.metadata}")
                
                # 计算重叠部分
                overlap_start = max(rule.seq_start, frame_seq_start)
                overlap_end = min(rule.seq_end, frame_seq_end)
                overlap_len = max(0, overlap_end - overlap_start)
                print(f"    重叠长度: {overlap_len} 字节")
                print()
            
            # 4. 检查是否为TLS片段
            from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            # 构造packet_info用于片段检测
            packet_info = {
                "_source": {
                    "layers": {
                        "frame.number": frame_number,
                        "tcp.stream": stream_id,
                        "tcp.seq_raw": seq_raw,
                        "tcp.len": tcp_len,
                        "tcp.payload": tcp_payload,
                        "tcp.segments": "1,2,3",  # 模拟tcp.segments字段
                        "tls.segment.data": tcp_payload[:32] if tcp_payload else ""  # 模拟tls.segment.data
                    }
                }
            }
            
            marker_instance = TLSProtocolMarker(config)
            
            is_fragment = marker_instance._is_tls_fragment(packet_info)
            is_record_start = marker_instance._is_tls_record_start(packet_info, tcp_payload)
            is_app_data_fragment = marker_instance._is_applicationdata_fragment(packet_info)
            
            print(f"TLS片段检测结果:")
            print(f"  是TLS片段: {is_fragment}")
            print(f"  是TLS记录开始: {is_record_start}")
            print(f"  是ApplicationData片段: {is_app_data_fragment}")
            
    except Exception as e:
        print(f"分析失败: {e}")

def analyze_frame_144_detailed():
    """详细分析帧144的规则匹配问题"""
    print("\n=== 详细分析帧144规则匹配问题 ===")
    
    pcap_file = 'tests/data/tls/tls_1_2_double_vlan.pcap'
    frame_number = 144
    
    # 1. 获取帧144的详细信息
    cmd = [
        'tshark', '-r', pcap_file,
        '-Y', f'frame.number=={frame_number}',
        '-T', 'fields',
        '-e', 'frame.number',
        '-e', 'tcp.stream',
        '-e', 'tcp.seq_raw',
        '-e', 'tcp.len',
        '-e', 'ip.src',
        '-e', 'ip.dst',
        '-e', 'tcp.srcport',
        '-e', 'tcp.dstport',
        '-e', 'tcp.payload',
        '-e', 'tls.record.content_type'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        fields = result.stdout.strip().split('\t')
        
        if len(fields) >= 8:
            frame_num, stream_id, seq_raw, tcp_len, src_ip, dst_ip, src_port, dst_port = fields[:8]
            tcp_payload = fields[8] if len(fields) > 8 else ""
            tls_content_type = fields[9] if len(fields) > 9 else ""
            
            print(f"帧144详细信息:")
            print(f"  流ID: {stream_id}")
            print(f"  序列号: {seq_raw}")
            print(f"  载荷长度: {tcp_len}")
            print(f"  源地址: {src_ip}:{src_port}")
            print(f"  目标地址: {dst_ip}:{dst_port}")
            print(f"  TLS内容类型: {tls_content_type}")
            print(f"  载荷前32字节: {tcp_payload[:64] if tcp_payload else 'N/A'}")
            
            # 2. 分析Marker模块生成的规则
            from pktmask.core.pipeline.stages.mask_payload_v2.marker import TLSProtocolMarker
            
            config = {
                'preserve': {
                    'handshake': True,
                    'application_data': False,
                    'alert': True,
                    'change_cipher_spec': True,
                    'heartbeat': True
                },
                'tshark_path': None,
                'decode_as': []
            }
            
            marker = TLSProtocolMarker(config)
            keep_rules = marker.analyze_file(pcap_file, config)
            
            # 3. 查找影响帧144的所有规则
            frame_seq_start = int(seq_raw)
            frame_seq_end = frame_seq_start + int(tcp_len)
            
            print(f"\n帧144序列号范围: [{frame_seq_start}, {frame_seq_end})")
            
            matching_rules = []
            for rule in keep_rules.rules:
                if rule.stream_id == stream_id:
                    # 检查序列号范围重叠
                    if not (rule.seq_end <= frame_seq_start or rule.seq_start >= frame_seq_end):
                        matching_rules.append(rule)
            
            print(f"\n匹配的规则数: {len(matching_rules)}")
            for i, rule in enumerate(matching_rules):
                print(f"  规则{i+1}:")
                print(f"    范围: [{rule.seq_start}, {rule.seq_end})")
                print(f"    类型: {rule.rule_type}")
                print(f"    方向: {rule.direction}")
                print(f"    策略: {rule.metadata.get('preserve_strategy', 'N/A')}")
                
                # 计算重叠部分
                overlap_start = max(rule.seq_start, frame_seq_start)
                overlap_end = min(rule.seq_end, frame_seq_end)
                overlap_len = max(0, overlap_end - overlap_start)
                print(f"    重叠长度: {overlap_len} 字节")
                print()
            
            # 4. 分析为什么会匹配到错误的规则类型
            print(f"问题分析:")
            print(f"  帧144是TLS-23 ApplicationData (内容类型={tls_content_type})")
            print(f"  应该只保留5字节头部，但被匹配到了changecipherspec规则")
            print(f"  这表明规则生成或匹配逻辑存在问题")
            
    except Exception as e:
        print(f"分析失败: {e}")

def main():
    """主分析函数"""
    print("深度调试规则匹配问题")
    print("=" * 50)
    
    # 检查测试文件
    test_files = [
        'tests/data/tls/tls_1_0_multi_segment_google-https.pcap',
        'tests/data/tls/tls_1_2_double_vlan.pcap'
    ]
    
    missing_files = [f for f in test_files if not Path(f).exists()]
    if missing_files:
        print(f"缺少测试文件: {missing_files}")
        return
    
    # 分析帧150
    analyze_frame_150_detailed()
    
    # 分析帧144
    analyze_frame_144_detailed()
    
    print("\n" + "=" * 50)
    print("调试分析完成")

if __name__ == '__main__':
    main()
