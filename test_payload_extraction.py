#!/usr/bin/env python3
"""
测试Scapy载荷提取修复效果
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scapy.all import rdpcap
from src.pktmask.core.trim.stages.scapy_rewriter import ScapyRewriter
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_payload_extraction(pcap_file):
    """测试载荷提取功能"""
    print(f"=== 测试文件: {pcap_file} ===")
    
    # 创建Scapy回写器
    rewriter = ScapyRewriter()
    
    # 读取PCAP文件
    try:
        packets = rdpcap(pcap_file)
        print(f"成功读取 {len(packets)} 个数据包")
    except Exception as e:
        print(f"读取PCAP文件失败: {e}")
        return
    
    # 测试前几个有载荷的数据包
    for i, packet in enumerate(packets[:10], 1):
        try:
            payload_data, seq_number = rewriter._extract_packet_payload(packet)
            
            # 检查是否有TCP层
            has_tcp = packet.haslayer('TCP')
            has_tls = packet.haslayer('TLS')
            has_raw = packet.haslayer('Raw')
            
            print(f"\n数据包 {i}:")
            print(f"  协议层: TCP={has_tcp}, TLS={has_tls}, Raw={has_raw}")
            print(f"  序列号: {seq_number}")
            print(f"  载荷长度: {len(payload_data)} 字节")
            
            if payload_data:
                hex_data = payload_data[:16].hex()
                print(f"  载荷前16字节: {hex_data}")
                
                # 检查是否是TLS数据
                if len(payload_data) >= 5:
                    record_type = payload_data[0]
                    version = int.from_bytes(payload_data[1:3], 'big')
                    length = int.from_bytes(payload_data[3:5], 'big')
                    
                    if record_type in [20, 21, 22, 23] and version in [0x0301, 0x0302, 0x0303, 0x0304]:
                        tls_types = {20: "ChangeCipherSpec", 21: "Alert", 22: "Handshake", 23: "ApplicationData"}
                        print(f"  TLS记录: {tls_types.get(record_type, 'Unknown')} (类型={record_type}, 版本=0x{version:04x}, 长度={length})")
                        
                        # 对于ApplicationData包，测试MaskAfter(5)掩码
                        if record_type == 23:
                            print(f"  ** 这是TLS ApplicationData包，适合应用MaskAfter(5)掩码 **")
                            print(f"     前5字节(保留): {payload_data[:5].hex()}")
                            if len(payload_data) > 5:
                                print(f"     其余{len(payload_data)-5}字节(应掩码): {payload_data[5:21].hex()}...")
            else:
                print("  无载荷")
                
        except Exception as e:
            print(f"数据包 {i} 处理失败: {e}")

if __name__ == "__main__":
    # 测试TLS样本文件
    test_file = "/Users/ricky/Downloads/TestCases/TLS/tls_sample.pcap"
    
    if os.path.exists(test_file):
        test_payload_extraction(test_file)
    else:
        print(f"测试文件不存在: {test_file}")
        print("请提供有效的PCAP文件路径") 