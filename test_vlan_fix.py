#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scapy.all import *
from pktmask.core.trim.stages.scapy_rewriter import ScapyRewriter

# 创建双层VLAN数据包
eth = Ether()
vlan1 = Dot1Q(vlan=100)
vlan2 = Dot1Q(vlan=200) 
ip = IP(src='10.1.1.1', dst='10.2.2.2')
tcp = TCP(sport=12345, dport=443, seq=1000)
tls_data = b'\x17\x03\x03\x01\x40' + b'A' * 315
packet = eth / vlan1 / vlan2 / ip / tcp / Raw(load=tls_data)

print('原始数据包结构:')
packet.show()
print(f'数据包总长度: {len(packet)} 字节')

# 测试新的头部计算方法
rewriter = ScapyRewriter()
headers_len = rewriter._calculate_all_headers_length(packet)
print(f'计算的头部长度: {headers_len} 字节')

# 测试载荷提取
payload, seq = rewriter._extract_packet_payload(packet)
print(f'提取的载荷长度: {len(payload)} 字节')
print(f'载荷前10字节: {payload[:10].hex()}')
print(f'期望TLS头部: 1703030140')

# 验证结果
expected_headers = 14 + 4 + 4 + 20 + 20  # Eth + VLAN1 + VLAN2 + IP + TCP
expected_payload = tls_data

print(f'\n验证结果:')
print(f'头部长度: {"✅ 正确" if headers_len == expected_headers else "❌ 错误"}')
print(f'载荷提取: {"✅ 正确" if payload == expected_payload else "❌ 错误"}') 