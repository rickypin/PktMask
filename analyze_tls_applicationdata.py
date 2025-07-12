#!/usr/bin/env python3
"""
专门分析TLS ApplicationData的脚本

目标：
1. 确认测试样本中是否真的有TLS ApplicationData
2. 分析为什么tls_flow_analyzer显示有ApplicationData但详细帧分析中找不到
3. 检查规则优化过程是否错误地将ApplicationData包含在保留规则中
"""

import sys
import os
import json
import subprocess
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def analyze_with_tshark_directly():
    """直接使用tshark分析TLS ApplicationData"""
    print("=" * 80)
    print("直接使用tshark分析TLS ApplicationData")
    print("=" * 80)
    
    input_file = "tests/samples/tls-single/tls_sample.pcap"
    
    # 使用tshark直接查询TLS ApplicationData
    cmd = [
        "tshark",
        "-r", input_file,
        "-Y", "tls.record.content_type == 23",  # ApplicationData
        "-T", "fields",
        "-e", "frame.number",
        "-e", "tcp.stream",
        "-e", "tcp.seq",
        "-e", "tcp.len",
        "-e", "tls.record.content_type",
        "-e", "tls.record.length",
        "-E", "header=y",
        "-E", "separator=,"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("tshark输出:")
            print(result.stdout)
            
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # 除了header
                print(f"发现 {len(lines) - 1} 个TLS ApplicationData记录")
            else:
                print("未发现TLS ApplicationData记录")
        else:
            print(f"tshark执行失败: {result.stderr}")
    except Exception as e:
        print(f"执行tshark失败: {e}")

def analyze_all_tls_records():
    """分析所有TLS记录"""
    print("\n" + "=" * 80)
    print("分析所有TLS记录")
    print("=" * 80)
    
    input_file = "tests/samples/tls-single/tls_sample.pcap"
    
    # 查询所有TLS记录
    cmd = [
        "tshark",
        "-r", input_file,
        "-Y", "tls",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "tcp.stream",
        "-e", "tcp.seq",
        "-e", "tcp.len",
        "-e", "tls.record.content_type",
        "-e", "tls.record.length",
        "-E", "header=y",
        "-E", "separator=,",
        "-E", "occurrence=a"  # 显示所有出现
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("所有TLS记录:")
            lines = result.stdout.strip().split('\n')
            
            if len(lines) > 1:
                header = lines[0]
                print(header)
                print("-" * len(header))
                
                tls_type_counts = {}
                for line in lines[1:]:
                    if line.strip():
                        fields = line.split(',')
                        if len(fields) >= 5:
                            frame_num = fields[0]
                            tcp_stream = fields[1]
                            tcp_seq = fields[2]
                            tcp_len = fields[3]
                            tls_types = fields[4].split(',') if fields[4] else []
                            tls_lengths = fields[5].split(',') if len(fields) > 5 and fields[5] else []
                            
                            print(f"{line}")
                            
                            # 统计TLS类型
                            for tls_type in tls_types:
                                if tls_type.strip():
                                    tls_type_counts[tls_type.strip()] = tls_type_counts.get(tls_type.strip(), 0) + 1
                
                print(f"\nTLS类型统计:")
                for tls_type, count in sorted(tls_type_counts.items()):
                    type_name = {
                        '20': 'ChangeCipherSpec',
                        '21': 'Alert', 
                        '22': 'Handshake',
                        '23': 'ApplicationData',
                        '24': 'Heartbeat'
                    }.get(tls_type, f'Unknown-{tls_type}')
                    print(f"  TLS-{tls_type} ({type_name}): {count} 记录")
            else:
                print("未发现TLS记录")
        else:
            print(f"tshark执行失败: {result.stderr}")
    except Exception as e:
        print(f"执行tshark失败: {e}")

def analyze_tcp_payload_ranges():
    """分析TCP载荷范围"""
    print("\n" + "=" * 80)
    print("分析TCP载荷范围")
    print("=" * 80)
    
    input_file = "tests/samples/tls-single/tls_sample.pcap"
    
    # 查询所有有TCP载荷的包
    cmd = [
        "tshark",
        "-r", input_file,
        "-Y", "tcp.len > 0",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "tcp.stream",
        "-e", "tcp.seq",
        "-e", "tcp.len",
        "-e", "tcp.payload",
        "-E", "header=y",
        "-E", "separator=,"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("TCP载荷数据包:")
            lines = result.stdout.strip().split('\n')
            
            if len(lines) > 1:
                header = lines[0]
                print(header)
                print("-" * len(header))
                
                for line in lines[1:]:
                    if line.strip():
                        fields = line.split(',')
                        if len(fields) >= 4:
                            frame_num = fields[0]
                            tcp_stream = fields[1]
                            tcp_seq = int(fields[2]) if fields[2] else 0
                            tcp_len = int(fields[3]) if fields[3] else 0
                            tcp_payload = fields[4] if len(fields) > 4 else ""
                            
                            tcp_end = tcp_seq + tcp_len
                            print(f"帧 {frame_num}: 流{tcp_stream}, 序列号 {tcp_seq}-{tcp_end} (长度 {tcp_len})")
                            
                            # 分析载荷前几个字节来判断TLS类型
                            if tcp_payload and len(tcp_payload) >= 2:
                                first_byte = tcp_payload[:2]
                                try:
                                    tls_type = int(first_byte, 16)
                                    if tls_type in [20, 21, 22, 23, 24]:
                                        type_name = {
                                            20: 'ChangeCipherSpec',
                                            21: 'Alert',
                                            22: 'Handshake', 
                                            23: 'ApplicationData',
                                            24: 'Heartbeat'
                                        }[tls_type]
                                        print(f"    可能的TLS类型: {tls_type} ({type_name})")
                                except:
                                    pass
            else:
                print("未发现TCP载荷数据包")
        else:
            print(f"tshark执行失败: {result.stderr}")
    except Exception as e:
        print(f"执行tshark失败: {e}")

def compare_with_original_analysis():
    """与原始分析结果对比"""
    print("\n" + "=" * 80)
    print("与原始分析结果对比")
    print("=" * 80)
    
    analysis_file = "output/tls_sample_tls_flow_analysis.json"
    if Path(analysis_file).exists():
        with open(analysis_file, 'r') as f:
            analysis_data = json.load(f)
        
        print("原始分析器统计:")
        if 'protocol_type_statistics' in analysis_data:
            for tls_type, stats in analysis_data['protocol_type_statistics'].items():
                type_name = analysis_data['metadata']['tls_content_types'].get(tls_type, f'Unknown-{tls_type}')
                strategy = analysis_data['metadata']['processing_strategies'].get(tls_type, 'unknown')
                print(f"  TLS-{tls_type} ({type_name}, {strategy}): {stats['frames']} 帧, {stats['records']} 记录")
        
        # 查找ApplicationData的详细信息
        print("\n查找ApplicationData详细信息:")
        if 'detailed_frames' in analysis_data:
            app_data_found = False
            for frame in analysis_data['detailed_frames']:
                if 'tls_messages' in frame:
                    for msg in frame['tls_messages']:
                        if msg.get('tls_type') == 23:
                            app_data_found = True
                            print(f"  帧 {frame['frame']}:")
                            print(f"    TLS类型: {msg.get('tls_type')} (ApplicationData)")
                            print(f"    TCP序列号: {msg.get('tcp_seq_start')}")
                            print(f"    TCP长度: {msg.get('tcp_len')}")
                            print(f"    TLS长度: {msg.get('tls_length')}")
                            if 'tcp_seq_range' in msg:
                                print(f"    TCP序列号范围: {msg['tcp_seq_range']}")
            
            if not app_data_found:
                print("  在详细帧信息中未找到ApplicationData")
                
                # 检查是否有TLS-23的统计但没有详细信息
                if '23' in analysis_data.get('protocol_type_statistics', {}):
                    print("  ⚠️  统计中显示有TLS-23记录，但详细帧中找不到")
                    print("  这可能是tls_flow_analyzer的一个bug或数据处理问题")
    else:
        print("原始分析文件不存在")

def main():
    """主函数"""
    print("TLS ApplicationData 专项分析")
    print("=" * 80)
    
    # 1. 直接用tshark查询ApplicationData
    analyze_with_tshark_directly()
    
    # 2. 分析所有TLS记录
    analyze_all_tls_records()
    
    # 3. 分析TCP载荷范围
    analyze_tcp_payload_ranges()
    
    # 4. 与原始分析对比
    compare_with_original_analysis()
    
    print("\n" + "=" * 80)
    print("分析总结:")
    print("如果tshark直接查询没有找到TLS-23记录，")
    print("那么测试样本中可能确实没有ApplicationData，")
    print("这解释了为什么没有数据包被掩码。")
    print("=" * 80)

if __name__ == "__main__":
    main()
