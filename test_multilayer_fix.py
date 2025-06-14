#!/usr/bin/env python3
"""
多层封装Scapy回写器修复验证脚本

验证双层VLAN、VXLAN、GRE等多层封装场景下的载荷提取和掩码应用
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scapy.all import *
from pktmask.core.trim.stages.scapy_rewriter import ScapyRewriter
import tempfile
from pathlib import Path

def create_double_vlan_tls_packet():
    """创建双层VLAN + TLS数据包"""
    # 构造双层VLAN TLS数据包
    eth = Ether(dst="00:11:22:33:44:55", src="aa:bb:cc:dd:ee:ff")
    vlan1 = Dot1Q(vlan=100, prio=1)  # 外层VLAN
    vlan2 = Dot1Q(vlan=200, prio=2)  # 内层VLAN
    ip = IP(src="10.1.1.1", dst="10.2.2.2")
    tcp = TCP(sport=12345, dport=443, seq=1000)
    
    # TLS应用数据 (Content Type 23)
    tls_data = b'\x17\x03\x03\x01\x40' + b'A' * 315  # 5字节TLS头部 + 315字节应用数据
    
    packet = eth / vlan1 / vlan2 / ip / tcp / Raw(load=tls_data)
    return packet

def create_vxlan_packet():
    """创建VXLAN封装数据包"""
    # 外层
    outer_eth = Ether(dst="00:11:22:33:44:55", src="aa:bb:cc:dd:ee:ff")
    outer_ip = IP(src="192.168.1.1", dst="192.168.1.2")
    outer_udp = UDP(sport=12345, dport=4789)  # VXLAN端口
    vxlan = VXLAN(vni=1000)
    
    # 内层
    inner_eth = Ether(dst="00:aa:bb:cc:dd:ee", src="00:ff:ee:dd:cc:bb")
    vlan = Dot1Q(vlan=300)
    inner_ip = IP(src="10.10.1.1", dst="10.10.2.2")
    tcp = TCP(sport=8080, dport=80, seq=2000)
    
    # HTTP数据
    http_data = b'GET /test HTTP/1.1\r\nHost: example.com\r\n\r\n' + b'B' * 200
    
    packet = outer_eth / outer_ip / outer_udp / vxlan / inner_eth / vlan / inner_ip / tcp / Raw(load=http_data)
    return packet

def test_header_calculation():
    """测试头部长度计算"""
    print("🔧 测试多层封装头部长度计算...")
    
    rewriter = ScapyRewriter()
    
    # 测试1: 双层VLAN
    print("\n1. 双层VLAN测试:")
    double_vlan_pkt = create_double_vlan_tls_packet()
    headers_len = rewriter._calculate_all_headers_length(double_vlan_pkt)
    expected_len = 14 + 4 + 4 + 20 + 20  # Eth + VLAN1 + VLAN2 + IP + TCP = 62
    print(f"   计算头部长度: {headers_len}字节")
    print(f"   期望头部长度: {expected_len}字节")
    print(f"   ✅ 正确" if headers_len == expected_len else f"   ❌ 错误 (差异: {headers_len - expected_len})")
    
    # 测试2: VXLAN
    print("\n2. VXLAN测试:")
    vxlan_pkt = create_vxlan_packet()
    headers_len = rewriter._calculate_all_headers_length(vxlan_pkt)
    # 外层: Eth(14) + IP(20) + UDP(8) + VXLAN(8) + 内层: Eth(14) + VLAN(4) + IP(20) + TCP(20) = 108
    expected_len = 14 + 20 + 8 + 8 + 14 + 4 + 20 + 20
    print(f"   计算头部长度: {headers_len}字节")
    print(f"   期望头部长度: {expected_len}字节")
    print(f"   ✅ 正确" if headers_len == expected_len else f"   ❌ 错误 (差异: {headers_len - expected_len})")

def test_payload_extraction():
    """测试载荷提取"""
    print("\n🔍 测试载荷提取...")
    
    rewriter = ScapyRewriter()
    
    # 测试双层VLAN TLS载荷提取
    print("\n1. 双层VLAN TLS载荷提取:")
    double_vlan_pkt = create_double_vlan_tls_packet()
    payload, seq = rewriter._extract_packet_payload(double_vlan_pkt)
    
    expected_payload = b'\x17\x03\x03\x01\x40' + b'A' * 315
    print(f"   提取载荷长度: {len(payload)}字节")
    print(f"   期望载荷长度: {len(expected_payload)}字节")
    print(f"   载荷前5字节: {payload[:5].hex()}")
    print(f"   期望前5字节: {expected_payload[:5].hex()}")
    print(f"   ✅ 正确" if payload == expected_payload else "   ❌ 载荷不匹配")

def test_complete_workflow():
    """测试完整工作流程"""
    print("\n🎯 测试完整处理工作流程...")
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
    
    try:
        # 创建测试数据包
        packets = [
            create_double_vlan_tls_packet(),
            create_vxlan_packet()
        ]
        
        # 写入临时PCAP文件
        wrpcap(str(tmp_path), packets)
        print(f"   创建测试文件: {tmp_path}")
        print(f"   包含{len(packets)}个数据包")
        
        # 使用新的载荷提取方法读取
        rewriter = ScapyRewriter()
        loaded_packets = rewriter._read_pcap_file(tmp_path)
        
        print(f"   成功读取{len(loaded_packets)}个数据包")
        
        # 测试每个数据包的载荷提取
        for i, packet in enumerate(loaded_packets):
            payload, seq = rewriter._extract_packet_payload(packet)
            print(f"   数据包{i+1}: 载荷长度={len(payload)}字节, 序列号={seq}")
            
            if i == 0:  # 双层VLAN TLS
                expected_tls = b'\x17\x03\x03\x01\x40' + b'A' * 315
                if payload[:5] == expected_tls[:5]:
                    print(f"     ✅ TLS头部正确提取: {payload[:5].hex()}")
                else:
                    print(f"     ❌ TLS头部提取错误: {payload[:5].hex()}")
            
            elif i == 1:  # VXLAN HTTP
                if b'GET /test HTTP' in payload[:50]:
                    print(f"     ✅ HTTP载荷正确提取")
                else:
                    print(f"     ❌ HTTP载荷提取错误: {payload[:50]}")
        
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理临时文件
        if tmp_path.exists():
            tmp_path.unlink()

def main():
    """主测试函数"""
    print("🚀 开始多层封装Scapy回写器修复验证")
    print("=" * 60)
    
    try:
        test_header_calculation()
        test_payload_extraction()
        test_complete_workflow()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        
    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 