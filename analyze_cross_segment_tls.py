#!/usr/bin/env python3
"""
跨TCP段TLS消息详细分析工具
分析为什么大部分跨段TLS消息处理正常，只有个别异常
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple

def analyze_tcp_segments_in_file(pcap_file: str) -> Dict[str, Any]:
    """分析文件中所有包含tcp.segments的帧"""
    print(f"\n=== 分析 {pcap_file} 中的TCP段重组情况 ===")
    
    # 查找所有包含tcp.segments的帧
    cmd = [
        'tshark', '-r', pcap_file,
        '-Y', 'tcp.segments',
        '-T', 'fields',
        '-e', 'frame.number',
        '-e', 'tcp.stream',
        '-e', 'tcp.seq_raw',
        '-e', 'tcp.len',
        '-e', 'tcp.segments',
        '-e', 'tls.record.content_type'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        
        segments_info = []
        for line in lines:
            if line.strip():
                fields = line.split('\t')
                if len(fields) >= 4:
                    frame_num = fields[0]
                    stream_id = fields[1]
                    seq_raw = fields[2]
                    tcp_len = fields[3]
                    segments = fields[4] if len(fields) > 4 else ""
                    tls_type = fields[5] if len(fields) > 5 else ""
                    
                    segments_info.append({
                        'frame': int(frame_num),
                        'stream': stream_id,
                        'seq_raw': int(seq_raw) if seq_raw else 0,
                        'tcp_len': int(tcp_len) if tcp_len else 0,
                        'segments': segments,
                        'tls_type': tls_type
                    })
        
        print(f"找到 {len(segments_info)} 个包含TCP段重组的帧")
        return {'segments': segments_info, 'total': len(segments_info)}
        
    except Exception as e:
        print(f"分析失败: {e}")
        return {'segments': [], 'total': 0}

def analyze_tls_reassembly_patterns(pcap_file: str) -> Dict[str, Any]:
    """分析TLS重组模式"""
    print(f"\n=== 分析TLS重组模式 ===")
    
    # 获取所有TLS记录的详细信息
    cmd = [
        'tshark', '-r', pcap_file,
        '-Y', 'tls',
        '-T', 'fields',
        '-e', 'frame.number',
        '-e', 'tcp.stream',
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
        
        tls_patterns = {
            'complete_in_single_segment': [],
            'spans_multiple_segments': [],
            'fragment_of_larger_message': [],
            'reassembled_message': []
        }
        
        for line in lines:
            if line.strip():
                fields = line.split('\t')
                if len(fields) >= 6:
                    frame_num = int(fields[0])
                    stream_id = fields[1]
                    seq_raw = int(fields[2]) if fields[2] else 0
                    tcp_len = int(fields[3]) if fields[3] else 0
                    tls_type = fields[4]
                    tls_len = int(fields[5]) if fields[5] else 0
                    has_segments = fields[6] if len(fields) > 6 else ""
                    reassembled_in = fields[7] if len(fields) > 7 else ""
                    
                    record_info = {
                        'frame': frame_num,
                        'stream': stream_id,
                        'seq_raw': seq_raw,
                        'tcp_len': tcp_len,
                        'tls_type': tls_type,
                        'tls_len': tls_len,
                        'has_segments': bool(has_segments),
                        'reassembled_in': reassembled_in
                    }
                    
                    # 分类TLS消息模式
                    if has_segments and not reassembled_in:
                        # 跨多个段的TLS消息的第一个片段
                        tls_patterns['spans_multiple_segments'].append(record_info)
                    elif reassembled_in:
                        # 大消息的片段，在其他帧中重组
                        tls_patterns['fragment_of_larger_message'].append(record_info)
                    elif has_segments and reassembled_in:
                        # 重组后的完整消息
                        tls_patterns['reassembled_message'].append(record_info)
                    else:
                        # 单段内的完整TLS消息
                        tls_patterns['complete_in_single_segment'].append(record_info)
        
        # 打印统计信息
        for pattern, records in tls_patterns.items():
            print(f"{pattern}: {len(records)} 条记录")
            
        return tls_patterns
        
    except Exception as e:
        print(f"TLS模式分析失败: {e}")
        return {}

def analyze_specific_failure_frame(pcap_file: str, frame_number: int):
    """深度分析特定失败帧的特征"""
    print(f"\n=== 深度分析失败帧 {frame_number} ===")
    
    # 获取该帧的完整协议栈信息
    cmd = [
        'tshark', '-r', pcap_file,
        '-Y', f'frame.number=={frame_number}',
        '-T', 'json', '-V'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        frame_data = json.loads(result.stdout)[0]
        layers = frame_data['_source']['layers']
        
        print(f"协议栈: {' -> '.join(layers.keys())}")
        
        # 分析TCP层信息
        if 'tcp' in layers:
            tcp = layers['tcp']
            print(f"TCP信息:")
            print(f"  序列号: {tcp.get('tcp.seq_raw', 'N/A')}")
            print(f"  载荷长度: {tcp.get('tcp.len', 'N/A')}")
            print(f"  段信息: {tcp.get('tcp.segments', 'N/A')}")
            print(f"  重组信息: {tcp.get('tcp.reassembled_in', 'N/A')}")
            
        # 分析TLS层信息
        tls_keys = [k for k in layers.keys() if k.startswith('tls')]
        if tls_keys:
            print(f"TLS层信息:")
            for tls_key in tls_keys:
                tls = layers[tls_key]
                print(f"  {tls_key}:")
                print(f"    内容类型: {tls.get('tls.record.content_type', 'N/A')}")
                print(f"    记录长度: {tls.get('tls.record.length', 'N/A')}")
                print(f"    版本: {tls.get('tls.record.version', 'N/A')}")
                
        # 获取原始载荷数据
        payload_cmd = [
            'tshark', '-r', pcap_file,
            '-Y', f'frame.number=={frame_number}',
            '-T', 'fields', '-e', 'tcp.payload'
        ]
        
        payload_result = subprocess.run(payload_cmd, capture_output=True, text=True, check=True)
        payload_hex = payload_result.stdout.strip()
        
        if payload_hex:
            print(f"TCP载荷分析:")
            print(f"  载荷长度: {len(payload_hex)//2} 字节")
            print(f"  前16字节: {payload_hex[:32]}")
            
            # 尝试手动解析TLS记录头
            if len(payload_hex) >= 10:
                try:
                    content_type = int(payload_hex[0:2], 16)
                    version_major = int(payload_hex[2:4], 16)
                    version_minor = int(payload_hex[4:6], 16)
                    length = int(payload_hex[6:10], 16)
                    
                    print(f"  手动TLS解析:")
                    print(f"    内容类型: {content_type}")
                    print(f"    版本: {version_major}.{version_minor}")
                    print(f"    声明长度: {length}")
                    print(f"    实际载荷: {len(payload_hex)//2} 字节")
                    
                    # 检查长度一致性
                    if length + 5 > len(payload_hex)//2:
                        print(f"    ⚠️  长度不匹配：声明{length+5}字节，实际{len(payload_hex)//2}字节")
                        print(f"    ⚠️  这可能是跨段TLS消息的片段")
                    
                except ValueError as e:
                    print(f"    ❌ TLS头解析失败: {e}")
                    print(f"    ❌ 这可能不是TLS记录的开始")
        
        return frame_data
        
    except Exception as e:
        print(f"失败帧分析错误: {e}")
        return None

def compare_normal_vs_failed_segments(pcap_file: str, failed_frame: int):
    """对比正常处理的跨段消息与失败的跨段消息"""
    print(f"\n=== 对比正常vs失败的跨段消息 ===")
    
    # 获取所有跨段消息
    segments_info = analyze_tcp_segments_in_file(pcap_file)
    
    # 找到失败帧的特征
    failed_info = None
    normal_samples = []
    
    for seg in segments_info['segments']:
        if seg['frame'] == failed_frame:
            failed_info = seg
        else:
            normal_samples.append(seg)
    
    if failed_info:
        print(f"失败帧 {failed_frame} 特征:")
        print(f"  流ID: {failed_info['stream']}")
        print(f"  序列号: {failed_info['seq_raw']}")
        print(f"  载荷长度: {failed_info['tcp_len']}")
        print(f"  TLS类型: {failed_info['tls_type']}")
        
        print(f"\n正常处理的跨段消息样本 (前5个):")
        for i, normal in enumerate(normal_samples[:5]):
            print(f"  帧{normal['frame']}: 流{normal['stream']}, "
                  f"序列号{normal['seq_raw']}, 长度{normal['tcp_len']}, "
                  f"TLS类型{normal['tls_type']}")
    
    return failed_info, normal_samples

def main():
    """主分析函数"""
    print("跨TCP段TLS消息处理异常深度分析")
    print("=" * 60)
    
    # 分析失败案例
    test_cases = [
        {
            'file': 'tests/data/tls/tls_1_0_multi_segment_google-https.pcap',
            'failed_frame': 150,
            'description': '跨TLS层问题'
        }
    ]
    
    for case in test_cases:
        pcap_file = case['file']
        failed_frame = case['failed_frame']
        
        print(f"\n{'='*80}")
        print(f"分析案例: {case['description']}")
        print(f"文件: {pcap_file}")
        print(f"失败帧: {failed_frame}")
        print(f"{'='*80}")
        
        if not Path(pcap_file).exists():
            print(f"文件不存在: {pcap_file}")
            continue
        
        # 1. 分析所有TCP段重组情况
        segments_info = analyze_tcp_segments_in_file(pcap_file)
        
        # 2. 分析TLS重组模式
        tls_patterns = analyze_tls_reassembly_patterns(pcap_file)
        
        # 3. 深度分析失败帧
        failed_frame_data = analyze_specific_failure_frame(pcap_file, failed_frame)
        
        # 4. 对比分析
        failed_info, normal_samples = compare_normal_vs_failed_segments(pcap_file, failed_frame)
        
        print(f"\n{'-'*60}")
        print("分析完成")

if __name__ == '__main__':
    main()
