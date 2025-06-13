#!/usr/bin/env python3
"""
简化的Scapy载荷检测调试脚本
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from scapy.all import rdpcap
    from scapy.layers.inet import IP, TCP
    from scapy.packet import Raw
except ImportError as e:
    print(f"❌ 无法导入Scapy: {e}")
    sys.exit(1)

def analyze_original_file():
    """分析原始TLS文件"""
    
    original_file = Path("tests/samples/TLS/tls_sample.pcap")
    
    if not original_file.exists():
        print(f"❌ 原始文件不存在: {original_file}")
        return
    
    print("🔬 分析原始TLS文件中的载荷检测")
    print("=" * 60)
    
    try:
        packets = rdpcap(str(original_file))
        print(f"📄 读取 {len(packets)} 个数据包")
        
        # 分析关键的数据包（重点关注有载荷的包）
        for packet_num in range(1, min(len(packets) + 1, 23)):  # 分析前22个包
            packet = packets[packet_num - 1]  # 0-based index
            
            if not packet.haslayer(TCP):
                continue
                
            tcp = packet[TCP]
            tcp_seq = tcp.seq
            
            # 检查载荷提取方法
            raw_exists = packet.haslayer(Raw)
            raw_payload_len = len(packet[Raw].load) if raw_exists else 0
            
            tcp_load_exists = hasattr(tcp, 'load')
            tcp_load_len = len(tcp.load) if tcp_load_exists else 0
            
            # 只显示有载荷的包
            if raw_payload_len > 0 or tcp_load_len > 0:
                print(f"\n📦 数据包{packet_num}: {packet.summary()}")
                print(f"   TCP序列号: {tcp_seq}")
                print(f"   Raw层存在: {raw_exists}, 载荷长度: {raw_payload_len}")
                print(f"   TCP.load存在: {tcp_load_exists}, 载荷长度: {tcp_load_len}")
                
                if raw_exists and raw_payload_len > 0:
                    payload = packet[Raw].load
                    print(f"   Raw载荷前16字节: {payload[:16].hex()}")
                elif tcp_load_exists and tcp_load_len > 0:
                    payload = tcp.load
                    print(f"   TCP载荷前16字节: {payload[:16].hex()}")
                    
                # 测试PyShark报告的包14和包15
                if packet_num in [14, 15]:
                    print(f"   🎯 关键包{packet_num} - PyShark报告有载荷")
    
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

def test_manual_extraction():
    """测试手动载荷提取"""
    
    original_file = Path("tests/samples/TLS/tls_sample.pcap")
    
    if not original_file.exists():
        print(f"❌ 原始文件不存在: {original_file}")
        return
    
    print("\n🧪 测试手动载荷提取方法")
    print("=" * 60)
    
    try:
        packets = rdpcap(str(original_file))
        
        # 重点测试包14（PyShark显示有205字节载荷）
        packet = packets[13]  # 0-based index for packet 14
        
        print(f"🎯 数据包14详细分析:")
        print(f"   摘要: {packet.summary()}")
        
        # 显示协议栈
        layers = []
        layer = packet
        while layer:
            layers.append(layer.__class__.__name__)
            layer = layer.payload if hasattr(layer, 'payload') and layer.payload else None
        print(f"   协议栈: {' / '.join(layers)}")
        
        # 详细检查各个方法
        print(f"\n   方法1 - Raw层检测:")
        raw_exists = packet.haslayer(Raw)
        print(f"     Raw层存在: {raw_exists}")
        if raw_exists:
            raw_payload = bytes(packet[Raw].load)
            print(f"     Raw载荷长度: {len(raw_payload)}")
            if len(raw_payload) > 0:
                print(f"     Raw载荷前32字节: {raw_payload[:32].hex()}")
        
        print(f"\n   方法2 - TCP load属性:")
        tcp = packet[TCP]
        tcp_load_exists = hasattr(tcp, 'load')
        print(f"     TCP.load存在: {tcp_load_exists}")
        if tcp_load_exists:
            tcp_payload = bytes(tcp.load)
            print(f"     TCP载荷长度: {len(tcp_payload)}")
            if len(tcp_payload) > 0:
                print(f"     TCP载荷前32字节: {tcp_payload[:32].hex()}")
        
        print(f"\n   方法3 - 包级load属性:")
        packet_load_exists = hasattr(packet, 'load')
        print(f"     packet.load存在: {packet_load_exists}")
        if packet_load_exists:
            packet_payload = bytes(packet.load)
            print(f"     packet载荷长度: {len(packet_payload)}")
            if len(packet_payload) > 0:
                print(f"     packet载荷前32字节: {packet_payload[:32].hex()}")
        
        print(f"\n   方法4 - 字节级计算:")
        packet_bytes = bytes(packet)
        print(f"     数据包总长度: {len(packet_bytes)}")
        
        # 计算头部长度
        eth_len = 14
        ip_len = packet[IP].ihl * 4 if packet.haslayer(IP) else 0
        tcp_len = packet[TCP].dataofs * 4 if packet.haslayer(TCP) else 0
        headers_len = eth_len + ip_len + tcp_len
        
        print(f"     头部长度: ETH({eth_len}) + IP({ip_len}) + TCP({tcp_len}) = {headers_len}")
        
        payload_len = len(packet_bytes) - headers_len
        print(f"     计算载荷长度: {payload_len}")
        
        if payload_len > 0:
            calculated_payload = packet_bytes[headers_len:]
            print(f"     计算载荷前32字节: {calculated_payload[:32].hex()}")
            
            # 这应该与PyShark的205字节匹配！
            print(f"   🔍 关键发现: 计算载荷长度 = {payload_len} 字节")
            print(f"   📊 PyShark报告的载荷长度 = 205 字节")
            if payload_len == 205:
                print(f"   ✅ 载荷长度匹配！")
            else:
                print(f"   ❌ 载荷长度不匹配!")
    
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Scapy载荷检测调试")
    print("=" * 70)
    
    # 分析原始文件
    analyze_original_file()
    
    # 测试手动提取
    test_manual_extraction()
    
    print("\n" + "=" * 70)
    print("✅ 调试完成") 