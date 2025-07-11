#!/usr/bin/env python3
"""验证 x509sat 协议层问题和解决方案的脚本"""

import subprocess
import json
import sys
from pathlib import Path

def run_tshark_command(pcap_file: str, frame_number: int) -> dict:
    """运行 tshark 命令获取指定帧的协议信息"""
    cmd = [
        "tshark",
        "-r", pcap_file,
        "-T", "json",
        "-e", "frame.number",
        "-e", "frame.protocols",
        "-Y", f"frame.number == {frame_number}"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        if data:
            return data[0]["_source"]["layers"]
        return {}
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        print(f"错误：无法获取帧信息 - {e}")
        return {}

def clean_protocol_layers(protocol_layers: list) -> list:
    """清理协议层级列表（模拟 TLS 流量分析器的清理逻辑）"""
    if not protocol_layers:
        return []
    
    cleaned = []
    seen_protocols = set()
    
    # 定义需要去重的协议
    dedup_protocols = {
        'x509sat', 'x509af', 'x509ce', 'x509if',
        'pkcs1', 'pkix1explicit', 'pkix1implicit',
        'cms', 'pkcs7'
    }
    
    for protocol in protocol_layers:
        protocol_lower = protocol.lower()
        
        # 对于需要去重的协议，只保留第一次出现
        if protocol_lower in dedup_protocols:
            if protocol_lower not in seen_protocols:
                cleaned.append(protocol)
                seen_protocols.add(protocol_lower)
        else:
            # 其他协议直接保留
            cleaned.append(protocol)
    
    return cleaned

def main():
    """主函数"""
    if len(sys.argv) != 3:
        print("用法: python verify_x509sat_issue.py <pcap_file> <frame_number>")
        print("示例: python verify_x509sat_issue.py tests/data/tls/tls_1_2_plainip.pcap 7")
        sys.exit(1)
    
    pcap_file = sys.argv[1]
    frame_number = int(sys.argv[2])
    
    # 检查文件是否存在
    if not Path(pcap_file).exists():
        print(f"错误：文件不存在 - {pcap_file}")
        sys.exit(1)
    
    print(f"分析文件: {pcap_file}")
    print(f"数据帧: {frame_number}")
    print("=" * 60)
    
    # 获取原始协议层级
    layers_data = run_tshark_command(pcap_file, frame_number)
    if not layers_data:
        print("错误：无法获取协议层级信息")
        sys.exit(1)
    
    protocols_raw = layers_data.get("frame.protocols", [""])[0]
    if not protocols_raw:
        print("错误：该帧没有协议信息")
        sys.exit(1)
    
    protocols_list = protocols_raw.split(":")
    
    print("🔍 原始协议层级:")
    print(f"   {protocols_raw}")
    print(f"   总层数: {len(protocols_list)}")
    
    # 统计 x509sat 出现次数
    x509sat_count = protocols_list.count("x509sat")
    print(f"   x509sat 出现次数: {x509sat_count}")
    
    print("\n🧹 清理后的协议层级:")
    cleaned_protocols = clean_protocol_layers(protocols_list)
    cleaned_protocols_str = ":".join(cleaned_protocols)
    print(f"   {cleaned_protocols_str}")
    print(f"   总层数: {len(cleaned_protocols)}")
    
    # 统计清理后的 x509sat 出现次数
    cleaned_x509sat_count = cleaned_protocols.count("x509sat")
    print(f"   x509sat 出现次数: {cleaned_x509sat_count}")
    
    print("\n📊 清理效果:")
    print(f"   层级数量减少: {len(protocols_list)} → {len(cleaned_protocols)} (-{len(protocols_list) - len(cleaned_protocols)})")
    print(f"   x509sat 去重: {x509sat_count} → {cleaned_x509sat_count} (-{x509sat_count - cleaned_x509sat_count})")
    
    # 显示去重的协议类型
    removed_protocols = []
    protocol_counts = {}
    for protocol in protocols_list:
        protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1
    
    for protocol, count in protocol_counts.items():
        if count > 1 and protocol.lower() in ['x509sat', 'x509af', 'x509ce', 'x509if', 'pkcs1', 'pkix1explicit', 'pkix1implicit', 'cms', 'pkcs7']:
            removed_protocols.append(f"{protocol}({count}→1)")
    
    if removed_protocols:
        print(f"   去重的协议: {', '.join(removed_protocols)}")
    
    print("\n✅ 验证完成")

if __name__ == "__main__":
    main()
