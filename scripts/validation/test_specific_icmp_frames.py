#!/usr/bin/env python3
"""
测试特定ICMP封装帧的Masker支持

直接测试帧807, 857, 859的处理能力
"""

import sys
from pathlib import Path
from scapy.all import *

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_specific_frames():
    """测试特定的ICMP封装帧"""
    pcap_path = "tests/data/tls/tls_1_2_single_vlan.pcap"
    target_frames = [807, 857, 859]
    
    print(f"测试特定ICMP封装帧: {target_frames}")
    print("="*60)
    
    # 读取pcap文件
    packets = rdpcap(pcap_path)
    
    for frame_num in target_frames:
        if frame_num <= len(packets):
            pkt = packets[frame_num - 1]  # 帧号从1开始，数组从0开始
            print(f"\n帧 {frame_num} 分析:")
            print("-" * 30)
            
            # 分析协议栈
            analyze_protocol_stack(pkt)
            
            # 测试TCP查找
            test_tcp_finding(pkt)
            
            # 测试Masker兼容性
            test_masker_compatibility(pkt)
        else:
            print(f"帧 {frame_num} 不存在（总共 {len(packets)} 帧）")

def analyze_protocol_stack(packet):
    """分析协议栈"""
    print("协议栈分析:")
    layers = []
    current = packet
    depth = 0
    
    while current and depth < 10:  # 防止无限循环
        layer_name = current.__class__.__name__
        layer_info = f"  {depth}: {layer_name}"
        
        # 添加关键信息
        if layer_name == "IP":
            layer_info += f" (src={current.src}, dst={current.dst}, proto={current.proto})"
        elif layer_name == "ICMP":
            layer_info += f" (type={current.type}, code={current.code})"
        elif layer_name == "TCP":
            layer_info += f" (sport={current.sport}, dport={current.dport}, seq={current.seq})"
        
        layers.append(layer_info)
        print(layer_info)
        
        if hasattr(current, 'payload') and current.payload:
            current = current.payload
            depth += 1
        else:
            break
    
    return layers

def test_tcp_finding(packet):
    """测试TCP查找"""
    print("\nTCP查找测试:")
    
    # 方法1: 递归查找所有TCP层
    tcp_layers = find_all_tcp_layers(packet)
    print(f"  发现TCP层数量: {len(tcp_layers)}")
    
    for i, (tcp, ip) in enumerate(tcp_layers):
        # 处理不同类型的IP和TCP层
        if hasattr(ip, 'src') and hasattr(tcp, 'sport'):
            print(f"    TCP层 {i+1}: {ip.src}:{tcp.sport} -> {ip.dst}:{tcp.dport} (seq={tcp.seq})")
        else:
            print(f"    TCP层 {i+1}: {tcp.__class__.__name__} in {ip.__class__.__name__}")
    
    # 方法2: 查找最内层TCP
    innermost_tcp, innermost_ip = find_innermost_tcp(packet)
    if innermost_tcp and innermost_ip:
        if hasattr(innermost_ip, 'src') and hasattr(innermost_tcp, 'sport'):
            print(f"  最内层TCP: {innermost_ip.src}:{innermost_tcp.sport} -> {innermost_ip.dst}:{innermost_tcp.dport}")
        else:
            print(f"  最内层TCP: {innermost_tcp.__class__.__name__} in {innermost_ip.__class__.__name__}")
    else:
        print("  未找到最内层TCP")

def find_all_tcp_layers(packet):
    """查找所有TCP层（包括ICMP错误消息中的TCPerror）"""
    tcp_layers = []
    current = packet

    while current:
        tcp_layer = None
        ip_layer = None

        # 检查标准TCP层
        if hasattr(current, 'haslayer') and current.haslayer(TCP):
            tcp_layer = current[TCP]
            # 查找对应的IP层
            temp = current
            while temp:
                if hasattr(temp, 'haslayer') and temp.haslayer(IP):
                    ip_layer = temp[IP]
                    break
                if hasattr(temp, 'payload') and temp.payload:
                    temp = temp.payload
                else:
                    break

        # 检查ICMP错误消息中的TCPerror层
        elif hasattr(current, '__class__') and current.__class__.__name__ == 'TCPerror':
            tcp_layer = current
            # 查找对应的IPerror层
            temp = packet
            while temp:
                if hasattr(temp, '__class__') and temp.__class__.__name__ == 'IPerror':
                    ip_layer = temp
                    break
                if hasattr(temp, 'payload') and temp.payload:
                    temp = temp.payload
                else:
                    break

        if tcp_layer and ip_layer:
            tcp_layers.append((tcp_layer, ip_layer))

        if hasattr(current, 'payload') and current.payload:
            current = current.payload
        else:
            break

    return tcp_layers

def find_innermost_tcp(packet):
    """查找最内层TCP（模拟Masker逻辑，包括TCPerror）"""
    tcp_layer = None
    ip_layer = None
    current = packet

    # 递归查找最深层的TCP
    while current:
        # 检查标准TCP层
        if hasattr(current, 'haslayer') and current.haslayer(TCP):
            tcp_layer = current[TCP]
            # 查找对应的IP层
            temp = current
            while temp:
                if temp.haslayer(IP):
                    ip_layer = temp[IP]
                    break
                if hasattr(temp, 'payload') and temp.payload:
                    temp = temp.payload
                else:
                    break

        # 检查TCPerror层（ICMP错误消息中的TCP）
        elif hasattr(current, '__class__') and current.__class__.__name__ == 'TCPerror':
            tcp_layer = current
            # 查找对应的IPerror层
            temp = packet
            while temp:
                if hasattr(temp, '__class__') and temp.__class__.__name__ == 'IPerror':
                    ip_layer = temp
                    break
                if hasattr(temp, 'payload') and temp.payload:
                    temp = temp.payload
                else:
                    break

        if hasattr(current, 'payload') and current.payload:
            current = current.payload
        else:
            break

    return tcp_layer, ip_layer

def test_masker_compatibility(packet):
    """测试Masker兼容性"""
    print("\nMasker兼容性测试:")
    
    # 测试流ID构建
    tcp_layer, ip_layer = find_innermost_tcp(packet)
    
    if tcp_layer and ip_layer:
        # 检查是否为标准层还是错误层
        if hasattr(ip_layer, 'src') and hasattr(tcp_layer, 'sport'):
            # 构建流ID（简化版本）
            src_ip = str(ip_layer.src)
            dst_ip = str(ip_layer.dst)
            src_port = str(tcp_layer.sport)
            dst_port = str(tcp_layer.dport)
        
            # 按字典序排序
            if (src_ip, src_port) < (dst_ip, dst_port):
                stream_id = f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}"
                direction = "forward"
            else:
                stream_id = f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}"
                direction = "reverse"

            print(f"  流ID: {stream_id}")
            print(f"  方向: {direction}")
            print(f"  TCP序列号: {tcp_layer.seq}")

            # 检查载荷
            if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
                payload_len = len(bytes(tcp_layer.payload))
                print(f"  TCP载荷长度: {payload_len} 字节")

                # 检查是否为TLS
                payload_bytes = bytes(tcp_layer.payload)
                if len(payload_bytes) >= 5:
                    tls_type = payload_bytes[0]
                    tls_version = (payload_bytes[1] << 8) | payload_bytes[2]
                    tls_length = (payload_bytes[3] << 8) | payload_bytes[4]

                    print(f"  可能的TLS记录: type={tls_type}, version=0x{tls_version:04x}, length={tls_length}")

                    if tls_type == 23:  # ApplicationData
                        print("  ✅ 检测到TLS ApplicationData，需要掩码处理")
                    else:
                        print(f"  ℹ️  TLS类型 {tls_type}，根据策略决定处理方式")
            else:
                print("  无TCP载荷")

            print("  ✅ Masker模块应该能够处理此数据包")
        else:
            print(f"  ⚠️  发现 {tcp_layer.__class__.__name__} 和 {ip_layer.__class__.__name__}")
            print("  ❌ 当前Masker模块可能无法处理ICMP错误消息中的TCP层")
    else:
        print("  ❌ 无法找到TCP层，Masker模块无法处理")

def main():
    test_specific_frames()

if __name__ == "__main__":
    main()
