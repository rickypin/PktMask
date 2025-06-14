#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
调试Scapy对大量连续TCP Segment的处理
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

def analyze_tcp_segments_in_pcap(pcap_file):
    """分析PCAP文件中的TCP段"""
    
    print(f"\n=== 分析文件: {pcap_file} ===")
    
    if not Path(pcap_file).exists():
        print(f"文件不存在: {pcap_file}")
        return
    
    try:
        packets = rdpcap(str(pcap_file))
        print(f"读取到 {len(packets)} 个数据包")
        
        # 按流分组
        tcp_flows = {}
        
        for i, pkt in enumerate(packets, 1):
            if pkt.haslayer(TCP) and pkt.haslayer(IP):
                ip_layer = pkt[IP]
                tcp_layer = pkt[TCP]
                
                # 生成流ID
                src_ip = ip_layer.src
                dst_ip = ip_layer.dst
                src_port = tcp_layer.sport
                dst_port = tcp_layer.dport
                
                # 标准化流ID
                if (src_ip, src_port) <= (dst_ip, dst_port):
                    flow_id = f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}"
                    direction = "forward"
                else:
                    flow_id = f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}"
                    direction = "reverse"
                
                if flow_id not in tcp_flows:
                    tcp_flows[flow_id] = []
                
                # 提取载荷信息
                payload = b''
                payload_layers = []
                
                # 方法1: 从Raw层提取
                if pkt.haslayer(Raw):
                    payload = bytes(pkt[Raw].load)
                    payload_layers.append("Raw")
                
                # 方法2: 从TCP层提取
                elif hasattr(tcp_layer, 'load'):
                    payload = bytes(tcp_layer.load)
                    payload_layers.append("TCP.load")
                
                # 方法3: 从数据包层级提取
                elif hasattr(pkt, 'load'):
                    payload = bytes(pkt.load)
                    payload_layers.append("Packet.load")
                
                tcp_flows[flow_id].append({
                    'packet_num': i,
                    'direction': direction,
                    'seq': tcp_layer.seq,
                    'ack': tcp_layer.ack,
                    'flags': tcp_layer.flags,
                    'payload_length': len(payload),
                    'payload_sources': payload_layers,
                    'payload_preview': payload[:16].hex() if payload else '',
                    'has_raw_layer': pkt.haslayer(Raw),
                    'tcp_has_load': hasattr(tcp_layer, 'load'),
                    'pkt_has_load': hasattr(pkt, 'load'),
                    'layer_summary': pkt.summary(),
                    'layers': [layer.name for layer in pkt.layers()]
                })
        
        # 分析每个流
        for flow_id, flow_pkts in tcp_flows.items():
            analyze_tcp_flow(flow_id, flow_pkts)
            
    except Exception as e:
        print(f"分析失败: {e}")
        import traceback
        traceback.print_exc()

def analyze_tcp_flow(flow_id, flow_pkts):
    """分析单个TCP流"""
    
    print(f"\n--- 流分析: {flow_id} ---")
    print(f"总包数: {len(flow_pkts)}")
    
    # 按方向分组
    forward_pkts = [p for p in flow_pkts if p['direction'] == 'forward']
    reverse_pkts = [p for p in flow_pkts if p['direction'] == 'reverse']
    
    print(f"Forward方向: {len(forward_pkts)} 包")
    print(f"Reverse方向: {len(reverse_pkts)} 包")
    
    # 分析每个方向的连续载荷段
    for direction, pkts in [('forward', forward_pkts), ('reverse', reverse_pkts)]:
        if not pkts:
            continue
            
        print(f"\n  {direction.upper()}方向分析:")
        
        # 按序列号排序
        sorted_pkts = sorted(pkts, key=lambda p: p['seq'])
        
        # 检查连续载荷段
        payload_segments = []
        current_segment = []
        
        for pkt in sorted_pkts:
            if pkt['payload_length'] > 0:
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
                            payload_segments.append(current_segment)
                        current_segment = [pkt]
        
        # 处理最后一个段
        if len(current_segment) > 1:
            payload_segments.append(current_segment)
        
        print(f"    连续载荷段数: {len(payload_segments)}")
        
        # 详细分析大的连续段
        for i, segment in enumerate(payload_segments):
            if len(segment) >= 5:  # 只分析大的连续段
                print(f"      大连续段{i+1}: {len(segment)}个包")
                
                start_seq = segment[0]['seq']
                end_seq = segment[-1]['seq'] + segment[-1]['payload_length']
                total_payload = sum(p['payload_length'] for p in segment)
                
                print(f"        序列号范围: {start_seq} - {end_seq}")
                print(f"        总载荷长度: {total_payload}")
                
                # 检查载荷提取方式的一致性
                payload_sources = set()
                for pkt in segment:
                    payload_sources.update(pkt['payload_sources'])
                
                print(f"        载荷来源: {payload_sources}")
                
                # 检查是否有Scapy的层结构异常
                layer_types = set()
                raw_layer_count = 0
                for pkt in segment:
                    layer_types.update(pkt['layers'])
                    if pkt['has_raw_layer']:
                        raw_layer_count += 1
                
                print(f"        协议层类型: {layer_types}")
                print(f"        Raw层比例: {raw_layer_count}/{len(segment)} ({raw_layer_count/len(segment)*100:.1f}%)")
                
                # 检查潜在的重组问题标志
                potential_issues = []
                
                if raw_layer_count < len(segment) * 0.8:
                    potential_issues.append("Raw层缺失率高")
                
                if len(payload_sources) > 1:
                    potential_issues.append("载荷来源不一致")
                
                # 检查序列号间隙
                for j in range(1, len(segment)):
                    prev_pkt = segment[j-1]
                    curr_pkt = segment[j]
                    expected_seq = prev_pkt['seq'] + prev_pkt['payload_length']
                    if curr_pkt['seq'] != expected_seq:
                        potential_issues.append(f"序列号跳跃: {expected_seq} -> {curr_pkt['seq']}")
                
                if potential_issues:
                    print(f"        ⚠️  潜在问题: {potential_issues}")
                else:
                    print(f"        ✅ 连续段正常")
                
                # 显示前几个包的详细信息
                print(f"        前3个包详情:")
                for pkt in segment[:3]:
                    print(f"          包{pkt['packet_num']}: seq={pkt['seq']}, len={pkt['payload_length']}, 来源={pkt['payload_sources']}")

def main():
    """主函数"""
    print("Scapy TCP段处理分析")
    print("=" * 60)
    
    # 测试文件列表
    test_files = [
        "tests/samples/TLS/tls_sample.pcap",
        "tests/samples/TLS70/tls_sample.pcap",
        "tests/samples/singlevlan/vlan_sample.pcap"
    ]
    
    for test_file in test_files:
        analyze_tcp_segments_in_pcap(test_file)
    
    print("\n" + "=" * 60)
    print("分析完成")

if __name__ == "__main__":
    main() 