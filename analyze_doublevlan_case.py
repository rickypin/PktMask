#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分析doublevlan_tls_2案例中的TCP段处理问题
重点检查Scapy对大量连续TCP Segment的Application Data的重组/识别逻辑
"""

import logging
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

try:
    from scapy.all import rdpcap, TCP, IP, Raw
    from scapy.packet import NoPayload
except ImportError:
    print("Scapy未安装，请运行: pip install scapy")
    sys.exit(1)

def analyze_doublevlan_case():
    """分析doublevlan_tls_2案例"""
    
    case_dir = Path("/Users/ricky/Downloads/TestCases/doublevlan_tls_2")
    pcap_file = case_dir / "pkt_18-27_Tue-Jun-27-2023.pcap"
    
    if not pcap_file.exists():
        print(f"PCAP文件不存在: {pcap_file}")
        return
    
    print(f"分析案例文件: {pcap_file}")
    print(f"文件大小: {pcap_file.stat().st_size / (1024*1024):.2f} MB")
    
    try:
        packets = rdpcap(str(pcap_file))
        print(f"读取到 {len(packets)} 个数据包")
        
        # 统计基本信息
        tcp_count = 0
        payload_count = 0
        total_payload_bytes = 0
        
        # 按流分组
        tcp_flows = {}
        
        for i, pkt in enumerate(packets, 1):
            if pkt.haslayer(TCP) and pkt.haslayer(IP):
                tcp_count += 1
                
                ip_layer = pkt[IP]
                tcp_layer = pkt[TCP]
                
                # 提取载荷
                payload = b''
                if pkt.haslayer(Raw):
                    payload = bytes(pkt[Raw].load)
                elif hasattr(tcp_layer, 'load'):
                    payload = bytes(tcp_layer.load)
                elif hasattr(pkt, 'load'):
                    payload = bytes(pkt.load)
                
                if payload:
                    payload_count += 1
                    total_payload_bytes += len(payload)
                
                # 生成流ID (与Scapy回写器逻辑一致)
                src_ip = ip_layer.src
                dst_ip = ip_layer.dst
                src_port = tcp_layer.sport
                dst_port = tcp_layer.dport
                
                if (src_ip, src_port) <= (dst_ip, dst_port):
                    flow_id = f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}"
                    direction = "forward"
                else:
                    flow_id = f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}"
                    direction = "reverse"
                
                if flow_id not in tcp_flows:
                    tcp_flows[flow_id] = []
                
                tcp_flows[flow_id].append({
                    'packet_num': i,
                    'direction': direction,
                    'seq': tcp_layer.seq,
                    'ack': tcp_layer.ack,
                    'flags': tcp_layer.flags,
                    'payload_length': len(payload),
                    'payload_preview': payload[:16].hex() if payload else '',
                    'has_tls': payload.startswith(b'\x16\x03') if payload else False,  # TLS检测
                    'is_application_data': payload.startswith(b'\x17\x03') if payload else False,  # TLS Application Data
                })
        
        print(f"\n基本统计:")
        print(f"  TCP包数: {tcp_count}")
        print(f"  有载荷的包: {payload_count}")
        print(f"  总载荷字节数: {total_payload_bytes:,}")
        print(f"  TCP流数: {len(tcp_flows)}")
        
        # 分析每个流中的连续TCP段问题
        print(f"\n=== TCP流分析 ===")
        
        for flow_id, flow_pkts in tcp_flows.items():
            analyze_flow_tcp_segments(flow_id, flow_pkts)
            
    except Exception as e:
        print(f"分析失败: {e}")
        import traceback
        traceback.print_exc()

def analyze_flow_tcp_segments(flow_id, flow_pkts):
    """分析单个流中的TCP段问题"""
    
    print(f"\n--- 流: {flow_id} ---")
    
    # 按方向分组
    forward_pkts = [p for p in flow_pkts if p['direction'] == 'forward']
    reverse_pkts = [p for p in flow_pkts if p['direction'] == 'reverse']
    
    print(f"Forward包数: {len(forward_pkts)}, Reverse包数: {len(reverse_pkts)}")
    
    # 分析每个方向
    for direction, pkts in [('forward', forward_pkts), ('reverse', reverse_pkts)]:
        if not pkts or len(pkts) < 5:  # 只分析包数较多的方向
            continue
            
        analyze_direction_segments(flow_id, direction, pkts)

def analyze_direction_segments(flow_id, direction, pkts):
    """分析单个方向的TCP段"""
    
    print(f"\n  {direction.upper()}方向详细分析:")
    
    # 按序列号排序
    sorted_pkts = sorted(pkts, key=lambda p: p['seq'])
    
    # 统计载荷包
    payload_pkts = [p for p in sorted_pkts if p['payload_length'] > 0]
    tls_pkts = [p for p in payload_pkts if p['has_tls']]
    app_data_pkts = [p for p in payload_pkts if p['is_application_data']]
    
    print(f"    总包数: {len(sorted_pkts)}")
    print(f"    有载荷包数: {len(payload_pkts)}")
    print(f"    TLS包数: {len(tls_pkts)}")
    print(f"    TLS Application Data包数: {len(app_data_pkts)}")
    
    if len(payload_pkts) < 5:
        return
    
    # 检查序列号分布
    seqs = [p['seq'] for p in payload_pkts]
    unique_seqs = set(seqs)
    
    print(f"    序列号唯一值数: {len(unique_seqs)}")
    
    # 重点：检查是否有大量包使用相同序列号（这是问题的关键！）
    from collections import Counter
    seq_counts = Counter(seqs)
    
    duplicate_seqs = {seq: count for seq, count in seq_counts.items() if count > 1}
    
    if duplicate_seqs:
        print(f"    ⚠️  发现重复序列号:")
        for seq, count in sorted(duplicate_seqs.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"      序列号 {seq}: {count}个包")
            
            # 显示使用相同序列号的包的详情
            same_seq_pkts = [p for p in payload_pkts if p['seq'] == seq]
            print(f"        包编号: {[p['packet_num'] for p in same_seq_pkts[:10]]}")  # 只显示前10个
            print(f"        载荷长度: {[p['payload_length'] for p in same_seq_pkts[:10]]}")
            print(f"        载荷预览: {[p['payload_preview'][:16] for p in same_seq_pkts[:3]]}")  # 只显示前3个
            
            # 这就是问题的根源！大量包使用相同序列号
            if count > 10:
                print(f"        🚨 严重问题：{count}个包使用相同序列号 {seq}")
                print(f"           这会导致Scapy回写器的掩码查找和应用出现混乱！")
    
    # 检查连续载荷段
    consecutive_segments = find_consecutive_segments(payload_pkts)
    
    print(f"    连续载荷段数: {len(consecutive_segments)}")
    
    for i, segment in enumerate(consecutive_segments):
        if len(segment) >= 5:  # 只分析大的连续段
            print(f"      连续段{i+1}: {len(segment)}个包")
            
            start_seq = segment[0]['seq']
            end_seq = segment[-1]['seq'] + segment[-1]['payload_length']
            total_payload = sum(p['payload_length'] for p in segment)
            
            print(f"        序列号范围: {start_seq} - {end_seq}")
            print(f"        总载荷长度: {total_payload}")
            
            # 检查这个连续段中的序列号重复问题
            segment_seqs = [p['seq'] for p in segment]
            segment_seq_counts = Counter(segment_seqs)
            segment_duplicates = {seq: count for seq, count in segment_seq_counts.items() if count > 1}
            
            if segment_duplicates:
                print(f"        ⚠️  连续段内序列号重复: {segment_duplicates}")
            
            # 检查TLS Application Data的分布
            segment_app_data = [p for p in segment if p['is_application_data']]
            
            if segment_app_data:
                print(f"        TLS Application Data包: {len(segment_app_data)}/{len(segment)}")
                if len(segment_app_data) > len(segment) * 0.8:
                    print(f"        🎯 这个连续段主要是TLS Application Data")
                    print(f"           序列号重复会严重影响载荷裁切的准确性！")

def find_consecutive_segments(payload_pkts):
    """查找连续的载荷段"""
    
    segments = []
    current_segment = []
    
    for pkt in payload_pkts:
        if not current_segment:
            current_segment = [pkt]
        else:
            # 检查是否连续
            last_pkt = current_segment[-1]
            expected_seq = last_pkt['seq'] + last_pkt['payload_length']
            
            if pkt['seq'] == expected_seq:
                # 连续的载荷段
                current_segment.append(pkt)
            else:
                # 非连续，保存当前段
                if len(current_segment) > 1:
                    segments.append(current_segment)
                current_segment = [pkt]
    
    # 处理最后一个段
    if len(current_segment) > 1:
        segments.append(current_segment)
    
    return segments

def main():
    """主函数"""
    print("分析doublevlan_tls_2案例中的TCP段处理问题")
    print("=" * 80)
    
    analyze_doublevlan_case()
    
    print("\n" + "=" * 80)
    print("分析完成")
    
    print("\n分析结论:")
    print("1. 检查是否有大量TCP包使用相同的序列号")
    print("2. 这种情况会导致Scapy回写器的掩码查找逻辑混乱")
    print("3. 特别是TLS Application Data的大量连续段会受影响")
    print("4. 需要修复序列号计算或掩码匹配逻辑")

if __name__ == "__main__":
    main() 