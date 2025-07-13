#!/usr/bin/env python3
"""
序列号计算验证脚本
用于交叉验证 tls_flow_analyzer.py 中的序列号计算逻辑
"""

import json
import subprocess
import sys
from pathlib import Path

def run_tshark_analysis(pcap_file):
    """使用 tshark 分析 pcap 文件，获取详细的 TCP 和 TLS 信息"""
    cmd = [
        "tshark", "-r", str(pcap_file), "-T", "json",
        "-e", "frame.number",
        "-e", "tcp.stream", 
        "-e", "tcp.seq",
        "-e", "tcp.seq_raw", 
        "-e", "tcp.len",
        "-e", "tls.record.content_type",
        "-e", "tls.record.length",
        "-e", "tls.record.opaque_type",
        "-e", "tcp.payload",
        "-Y", "tls"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"tshark 执行失败: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        return []

def analyze_tls_payload_manually(tcp_payload_hex):
    """手动解析 TCP 载荷中的 TLS 记录"""
    if not tcp_payload_hex:
        return []
    
    # 移除空格和换行符
    payload_hex = ''.join(tcp_payload_hex.split())
    
    # 转换为字节
    try:
        payload_bytes = bytes.fromhex(payload_hex)
    except ValueError:
        return []
    
    tls_records = []
    offset = 0
    
    while offset + 5 <= len(payload_bytes):
        # 解析 TLS 记录头 (5 字节)
        content_type = payload_bytes[offset]
        version_major = payload_bytes[offset + 1]
        version_minor = payload_bytes[offset + 2]
        length = int.from_bytes(payload_bytes[offset + 3:offset + 5], byteorder='big')
        
        # 验证内容类型
        if content_type not in [20, 21, 22, 23, 24]:
            offset += 1
            continue
        
        tls_records.append({
            'offset_in_tcp': offset,
            'content_type': content_type,
            'version': (version_major, version_minor),
            'length': length,
            'header_start': offset,
            'header_end': offset + 5,
            'payload_start': offset + 5,
            'payload_end': offset + 5 + length
        })
        
        # 移动到下一个记录
        offset += 5 + length
        
        # 检查是否超出载荷边界
        if offset > len(payload_bytes):
            break
    
    return tls_records

def compare_seq_calculations(pcap_file):
    """比较不同方法的序列号计算结果"""
    print(f"分析文件: {pcap_file}")
    print("=" * 80)
    
    # 使用 tshark 获取原始数据
    tshark_data = run_tshark_analysis(pcap_file)
    
    if not tshark_data:
        print("❌ 无法获取 tshark 数据")
        return
    
    print(f"📊 tshark 解析到 {len(tshark_data)} 个 TLS 包")
    print()
    
    for i, packet in enumerate(tshark_data[:5]):  # 只分析前5个包
        layers = packet.get("_source", {}).get("layers", {})
        
        frame_number = layers.get("frame.number", [""])[0]
        tcp_stream = layers.get("tcp.stream", [""])[0]
        tcp_seq = layers.get("tcp.seq", [""])[0]
        tcp_seq_raw = layers.get("tcp.seq_raw", [""])[0]
        tcp_len = layers.get("tcp.len", [""])[0]
        tcp_payload = layers.get("tcp.payload", [""])[0]
        
        print(f"📦 包 {frame_number} (流 {tcp_stream})")
        print(f"   TCP序列号(相对): {tcp_seq}")
        print(f"   TCP序列号(绝对): {tcp_seq_raw}")
        print(f"   TCP载荷长度: {tcp_len}")
        
        # 手动解析 TLS 记录
        tls_records = analyze_tls_payload_manually(tcp_payload)
        
        if not tls_records:
            print("   ❌ 未找到 TLS 记录")
            continue
        
        print(f"   🔍 找到 {len(tls_records)} 个 TLS 记录:")
        
        # 计算序列号（模拟 tls_flow_analyzer.py 的逻辑）
        base_seq = int(tcp_seq_raw) if tcp_seq_raw else (int(tcp_seq) if tcp_seq else 0)
        
        for j, record in enumerate(tls_records):
            # 按照 tls_flow_analyzer.py 的计算方式
            tls_offset = record['offset_in_tcp']
            tls_header_seq_start = base_seq + tls_offset
            tls_header_seq_end = tls_header_seq_start + 5
            tls_payload_seq_start = tls_header_seq_end
            tls_payload_seq_end = tls_payload_seq_start + record['length']
            
            print(f"     [{j+1}] TLS-{record['content_type']} (长度: {record['length']})")
            print(f"         TCP载荷偏移: {tls_offset}")
            print(f"         计算的头部序列号: {tls_header_seq_start} - {tls_header_seq_end}")
            print(f"         计算的载荷序列号: {tls_payload_seq_start} - {tls_payload_seq_end}")
            print(f"         整个TLS消息: {tls_header_seq_start} - {tls_payload_seq_end}")
            
            # 验证计算逻辑
            print(f"         🔍 验证:")
            print(f"            base_seq({base_seq}) + offset({tls_offset}) = {tls_header_seq_start}")
            print(f"            头部范围: [{tls_header_seq_start}, {tls_header_seq_end}) (5字节)")
            print(f"            载荷范围: [{tls_payload_seq_start}, {tls_payload_seq_end}) ({record['length']}字节)")
            
            # 检查序列号是否对应字节边界
            tcp_start_seq = base_seq
            tcp_end_seq = base_seq + int(tcp_len) if tcp_len else base_seq
            
            print(f"         📍 TCP段范围: [{tcp_start_seq}, {tcp_end_seq})")
            
            # 验证 TLS 消息是否在 TCP 段范围内
            if tls_header_seq_start >= tcp_start_seq and tls_payload_seq_end <= tcp_end_seq:
                print(f"         ✅ TLS消息完全在TCP段内")
            else:
                print(f"         ⚠️  TLS消息可能跨TCP段")
        
        print()

def verify_with_wireshark(pcap_file, frame_number):
    """使用 Wireshark 验证特定帧的 TLS 记录位置"""
    print(f"\n🔍 Wireshark 验证 - 帧 {frame_number}")
    print("-" * 50)

    # 获取 TCP 载荷的十六进制数据
    cmd = [
        "tshark", "-r", str(pcap_file), "-T", "fields",
        "-e", "tcp.seq_raw", "-e", "tcp.len", "-e", "tcp.payload",
        "-Y", f"frame.number == {frame_number}"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        if not lines or not lines[0]:
            print("❌ 无法获取数据")
            return

        parts = lines[0].split('\t')
        if len(parts) < 3:
            print("❌ 数据格式错误")
            return

        tcp_seq_raw = int(parts[0])
        tcp_len = int(parts[1])
        tcp_payload_hex = parts[2]

        print(f"TCP 序列号(绝对): {tcp_seq_raw}")
        print(f"TCP 载荷长度: {tcp_len}")

        # 手动解析载荷
        payload_hex = ''.join(tcp_payload_hex.split())
        payload_bytes = bytes.fromhex(payload_hex)

        print(f"载荷十六进制 (前32字节): {payload_hex[:64]}")

        # 逐字节分析 TLS 记录
        offset = 0
        record_num = 1

        while offset + 5 <= len(payload_bytes):
            content_type = payload_bytes[offset]
            version_major = payload_bytes[offset + 1]
            version_minor = payload_bytes[offset + 2]
            length = int.from_bytes(payload_bytes[offset + 3:offset + 5], byteorder='big')

            if content_type not in [20, 21, 22, 23, 24]:
                offset += 1
                continue

            print(f"\n  📋 TLS 记录 {record_num}:")
            print(f"     字节偏移: {offset}")
            print(f"     内容类型: {content_type}")
            print(f"     版本: {version_major}.{version_minor}")
            print(f"     长度: {length}")

            # 计算序列号位置
            header_seq_start = tcp_seq_raw + offset
            header_seq_end = header_seq_start + 5
            payload_seq_start = header_seq_end
            payload_seq_end = payload_seq_start + length

            print(f"     🎯 序列号分析:")
            print(f"        TLS 头部: 序列号 {header_seq_start} - {header_seq_end-1} (字节位置)")
            print(f"        TLS 载荷: 序列号 {payload_seq_start} - {payload_seq_end-1} (字节位置)")
            print(f"        整个消息: 序列号 {header_seq_start} - {payload_seq_end-1} (字节位置)")

            # 验证：序列号应该指向实际字节位置
            print(f"     ✅ 验证:")
            print(f"        第一字节位置: TCP序列号{tcp_seq_raw} + 偏移{offset} = {header_seq_start}")
            print(f"        最后字节位置: {payload_seq_end-1}")
            print(f"        消息总长度: {5 + length} 字节")

            offset += 5 + length
            record_num += 1

            if offset > len(payload_bytes):
                break

    except Exception as e:
        print(f"❌ 验证失败: {e}")

def main():
    if len(sys.argv) != 2:
        print("用法: python debug_seq_calculation.py <pcap_file>")
        sys.exit(1)

    pcap_file = Path(sys.argv[1])
    if not pcap_file.exists():
        print(f"❌ 文件不存在: {pcap_file}")
        sys.exit(1)

    compare_seq_calculations(pcap_file)

    # 验证特定帧
    verify_with_wireshark(pcap_file, 9)

if __name__ == "__main__":
    main()
