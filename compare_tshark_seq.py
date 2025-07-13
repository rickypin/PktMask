#!/usr/bin/env python3
"""
对比 tshark 解码的序列号与当前计算方法
直接使用 tshark 的 TCP 序列号字段来验证序列号计算的准确性
"""

import json
import subprocess
import sys
from pathlib import Path

def get_tshark_detailed_info(pcap_file, frame_number):
    """获取 tshark 解码的详细 TCP 和 TLS 信息"""
    cmd = [
        "tshark", "-r", str(pcap_file), "-T", "json",
        "-e", "frame.number",
        "-e", "tcp.seq",           # 相对序列号
        "-e", "tcp.seq_raw",       # 绝对序列号
        "-e", "tcp.len",           # TCP 载荷长度
        "-e", "tcp.payload",       # TCP 载荷十六进制
        "-e", "tls.record.content_type",
        "-e", "tls.record.length",
        "-Y", f"frame.number == {frame_number}"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        if data:
            return data[0].get("_source", {}).get("layers", {})
        return {}
    except Exception as e:
        print(f"❌ tshark 执行失败: {e}")
        return {}

def get_tshark_tls_positions(pcap_file, frame_number):
    """使用 tshark 获取 TLS 记录在 TCP 流中的精确位置"""
    # 获取更详细的 TLS 字段信息
    cmd = [
        "tshark", "-r", str(pcap_file), "-T", "json",
        "-e", "frame.number",
        "-e", "tcp.seq_raw",
        "-e", "tcp.len", 
        "-e", "tls.record.content_type",
        "-e", "tls.record.length",
        "-e", "tls.record",           # TLS 记录的完整信息
        "-Y", f"frame.number == {frame_number}"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        if data:
            return data[0].get("_source", {}).get("layers", {})
        return {}
    except Exception as e:
        print(f"❌ 获取 TLS 位置信息失败: {e}")
        return {}

def manual_parse_tcp_payload(tcp_payload_hex):
    """手动解析 TCP 载荷中的 TLS 记录"""
    if not tcp_payload_hex:
        return []
    
    # 清理十六进制字符串
    payload_hex = ''.join(tcp_payload_hex.split())
    
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
            'tcp_payload_offset': offset,
            'content_type': content_type,
            'version': (version_major, version_minor),
            'length': length,
            'header_start_offset': offset,
            'header_end_offset': offset + 4,      # 头部最后一个字节的偏移
            'payload_start_offset': offset + 5,   # 载荷第一个字节的偏移
            'payload_end_offset': offset + 5 + length - 1  # 载荷最后一个字节的偏移
        })
        
        # 移动到下一个记录
        offset += 5 + length
        
        # 检查是否超出载荷边界
        if offset > len(payload_bytes):
            break
    
    return tls_records

def compare_sequence_calculations(pcap_file, frame_number):
    """对比不同方法的序列号计算结果"""
    print(f"🔍 对比帧 {frame_number} 的序列号计算方法")
    print("=" * 80)
    
    # 获取 tshark 基础信息
    layers = get_tshark_detailed_info(pcap_file, frame_number)
    if not layers:
        print("❌ 无法获取 tshark 数据")
        return
    
    # 提取基础字段
    tcp_seq = layers.get("tcp.seq", [""])[0]           # 相对序列号
    tcp_seq_raw = layers.get("tcp.seq_raw", [""])[0]   # 绝对序列号
    tcp_len = layers.get("tcp.len", [""])[0]           # TCP 载荷长度
    tcp_payload = layers.get("tcp.payload", [""])[0]   # TCP 载荷
    
    print(f"📊 tshark 解码的基础信息:")
    print(f"   TCP 相对序列号: {tcp_seq}")
    print(f"   TCP 绝对序列号: {tcp_seq_raw}")
    print(f"   TCP 载荷长度: {tcp_len}")
    print()
    
    if not tcp_seq_raw or not tcp_payload:
        print("❌ 缺少必要的 TCP 信息")
        return
    
    # 手动解析 TLS 记录
    tls_records = manual_parse_tcp_payload(tcp_payload)
    if not tls_records:
        print("❌ 未找到 TLS 记录")
        return
    
    print(f"🔍 找到 {len(tls_records)} 个 TLS 记录")
    print()
    
    tcp_seq_raw_int = int(tcp_seq_raw)
    
    for i, record in enumerate(tls_records):
        print(f"📋 TLS 记录 {i+1}: TLS-{record['content_type']} (长度: {record['length']})")
        print(f"   TCP 载荷内偏移: {record['tcp_payload_offset']}")
        print()
        
        # 方法1: 当前 tls_flow_analyzer.py 的计算方法
        print("🔧 方法1: 当前 tls_flow_analyzer.py 的计算")
        base_seq_current = tcp_seq_raw_int
        tls_offset = record['tcp_payload_offset']
        
        # 当前代码的计算逻辑
        tls_header_seq_start_current = base_seq_current + tls_offset
        tls_header_seq_end_current = tls_header_seq_start_current + 5
        tls_payload_seq_start_current = tls_header_seq_end_current
        tls_payload_seq_end_current = tls_payload_seq_start_current + record['length']
        
        print(f"   base_seq = tcp_seq_raw = {base_seq_current}")
        print(f"   TLS 头部序列号: {tls_header_seq_start_current} - {tls_header_seq_end_current} (左闭右开)")
        print(f"   TLS 载荷序列号: {tls_payload_seq_start_current} - {tls_payload_seq_end_current} (左闭右开)")
        print(f"   整个 TLS 消息: {tls_header_seq_start_current} - {tls_payload_seq_end_current} (左闭右开)")
        print()
        
        # 方法2: 使用 tshark 解码的正确方法（左闭右闭）
        print("✅ 方法2: 基于 tshark 解码的正确计算（左闭右闭区间）")
        
        # tshark 的 tcp.seq_raw 指向 TCP 段的第一个字节
        # TCP 载荷从 tcp.seq_raw + TCP头部长度 开始
        # 但我们可以直接使用 tcp.seq_raw 作为 TCP 载荷的起始参考点
        # 因为 tshark 已经为我们处理了这个偏移
        
        tcp_payload_start_seq = tcp_seq_raw_int  # tshark 已经处理了 TCP 头部偏移
        
        # 正确的序列号计算（左闭右闭区间）
        tls_header_seq_start_correct = tcp_payload_start_seq + record['header_start_offset']
        tls_header_seq_end_correct = tcp_payload_start_seq + record['header_end_offset']
        tls_payload_seq_start_correct = tcp_payload_start_seq + record['payload_start_offset']
        tls_payload_seq_end_correct = tcp_payload_start_seq + record['payload_end_offset']
        
        print(f"   TCP 载荷起始序列号 = {tcp_payload_start_seq}")
        print(f"   TLS 头部序列号: {tls_header_seq_start_correct} - {tls_header_seq_end_correct} (左闭右闭)")
        print(f"   TLS 载荷序列号: {tls_payload_seq_start_correct} - {tls_payload_seq_end_correct} (左闭右闭)")
        print(f"   整个 TLS 消息: {tls_header_seq_start_correct} - {tls_payload_seq_end_correct} (左闭右闭)")
        print()
        
        # 对比差异
        print("🔍 差异分析:")
        header_start_diff = tls_header_seq_start_correct - tls_header_seq_start_current
        header_end_diff = tls_header_seq_end_correct - (tls_header_seq_end_current - 1)  # 转换为左闭右闭
        payload_start_diff = tls_payload_seq_start_correct - tls_payload_seq_start_current
        payload_end_diff = tls_payload_seq_end_correct - (tls_payload_seq_end_current - 1)  # 转换为左闭右闭
        
        print(f"   头部起始序列号差异: {header_start_diff}")
        print(f"   头部结束序列号差异: {header_end_diff}")
        print(f"   载荷起始序列号差异: {payload_start_diff}")
        print(f"   载荷结束序列号差异: {payload_end_diff}")
        
        # 验证长度
        current_header_len = (tls_header_seq_end_current - 1) - tls_header_seq_start_current + 1
        correct_header_len = tls_header_seq_end_correct - tls_header_seq_start_correct + 1
        current_payload_len = (tls_payload_seq_end_current - 1) - tls_payload_seq_start_current + 1
        correct_payload_len = tls_payload_seq_end_correct - tls_payload_seq_start_correct + 1
        
        print(f"   当前方法头部长度: {current_header_len}, 正确方法头部长度: {correct_header_len}")
        print(f"   当前方法载荷长度: {current_payload_len}, 正确方法载荷长度: {correct_payload_len}")
        print(f"   声明的载荷长度: {record['length']}")
        
        # 验证连续性
        if tls_header_seq_end_correct + 1 == tls_payload_seq_start_correct:
            print("   ✅ 正确方法：头部和载荷序列号连续")
        else:
            print("   ❌ 正确方法：头部和载荷序列号不连续")
        
        print("-" * 60)

def main():
    if len(sys.argv) != 3:
        print("用法: python compare_tshark_seq.py <pcap_file> <frame_number>")
        sys.exit(1)
    
    pcap_file = Path(sys.argv[1])
    frame_number = int(sys.argv[2])
    
    if not pcap_file.exists():
        print(f"❌ 文件不存在: {pcap_file}")
        sys.exit(1)
    
    compare_sequence_calculations(pcap_file, frame_number)

if __name__ == "__main__":
    main()
