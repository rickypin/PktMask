#!/usr/bin/env python3
"""
分析PktMask处理流水线各阶段对TLS ApplicationData的影响

重点分析：
1. 原始文件中的TLS ApplicationData
2. 去重阶段后的变化
3. IP匿名化阶段后的变化
4. 最终掩码阶段的输入状态
"""

import sys
import os
import subprocess
from pathlib import Path

def analyze_file_with_tshark(file_path, description):
    """使用tshark分析文件中的TLS数据"""
    print(f"\n{'='*60}")
    print(f"分析 {description}")
    print(f"文件: {file_path}")
    print(f"{'='*60}")
    
    if not Path(file_path).exists():
        print(f"❌ 文件不存在: {file_path}")
        return None
    
    # 1. 基本统计
    cmd_basic = [
        "tshark", "-r", file_path,
        "-q", "-z", "conv,tcp"
    ]
    
    try:
        result = subprocess.run(cmd_basic, capture_output=True, text=True)
        if result.returncode == 0:
            print("TCP连接统计:")
            print(result.stdout)
        else:
            print(f"基本统计失败: {result.stderr}")
    except Exception as e:
        print(f"基本统计执行失败: {e}")
    
    # 2. TLS ApplicationData分析
    cmd_app_data = [
        "tshark", "-r", file_path,
        "-Y", "tls.record.content_type == 23",
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
    
    try:
        result = subprocess.run(cmd_app_data, capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                print(f"\n🔍 TLS ApplicationData记录 ({len(lines)-1} 个):")
                print(result.stdout)
            else:
                print("\n❌ 未发现TLS ApplicationData记录")
        else:
            print(f"ApplicationData查询失败: {result.stderr}")
    except Exception as e:
        print(f"ApplicationData查询执行失败: {e}")
    
    # 3. 所有TLS记录统计
    cmd_all_tls = [
        "tshark", "-r", file_path,
        "-Y", "tls",
        "-T", "fields",
        "-e", "tls.record.content_type",
        "-E", "occurrence=a"
    ]
    
    try:
        result = subprocess.run(cmd_all_tls, capture_output=True, text=True)
        if result.returncode == 0:
            tls_types = {}
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    types = line.split(',')
                    for tls_type in types:
                        if tls_type.strip():
                            tls_types[tls_type.strip()] = tls_types.get(tls_type.strip(), 0) + 1
            
            print(f"\n📊 TLS记录类型统计:")
            for tls_type, count in sorted(tls_types.items()):
                type_name = {
                    '20': 'ChangeCipherSpec',
                    '21': 'Alert',
                    '22': 'Handshake', 
                    '23': 'ApplicationData',
                    '24': 'Heartbeat'
                }.get(tls_type, f'Unknown-{tls_type}')
                print(f"  TLS-{tls_type} ({type_name}): {count} 记录")
        else:
            print(f"TLS统计失败: {result.stderr}")
    except Exception as e:
        print(f"TLS统计执行失败: {e}")
    
    # 4. 数据包总数
    cmd_count = [
        "tshark", "-r", file_path,
        "-T", "fields",
        "-e", "frame.number"
    ]
    
    try:
        result = subprocess.run(cmd_count, capture_output=True, text=True)
        if result.returncode == 0:
            packet_count = len([line for line in result.stdout.strip().split('\n') if line.strip()])
            print(f"\n📦 总数据包数: {packet_count}")
        else:
            print(f"数据包计数失败: {result.stderr}")
    except Exception as e:
        print(f"数据包计数执行失败: {e}")

def find_processed_files():
    """查找处理过程中的中间文件"""
    print("🔍 查找处理过程中的中间文件...")
    
    # 查找最近的处理输出目录
    samples_dir = Path("/Users/ricky/Downloads/samples/tls-single")
    if not samples_dir.exists():
        samples_dir = Path("tests/samples/tls-single")
    
    print(f"搜索目录: {samples_dir}")
    
    # 查找最新的处理目录
    masked_dirs = list(samples_dir.glob("tls-single-Masked-*"))
    if masked_dirs:
        latest_dir = max(masked_dirs, key=lambda p: p.stat().st_mtime)
        print(f"最新处理目录: {latest_dir}")
        
        # 列出目录中的文件
        files = list(latest_dir.glob("*.pcap"))
        print(f"找到的pcap文件:")
        for file in files:
            print(f"  {file}")
        
        return latest_dir
    else:
        print("未找到处理输出目录")
        return None

def analyze_temp_files():
    """分析临时文件"""
    print("\n🔍 查找临时处理文件...")
    
    # 查找系统临时目录中的pktmask文件
    import tempfile
    temp_dir = Path(tempfile.gettempdir())
    
    pktmask_temps = list(temp_dir.glob("pktmask_pipeline_*"))
    print(f"临时目录: {temp_dir}")
    print(f"找到的pktmask临时目录: {len(pktmask_temps)}")
    
    for temp_path in pktmask_temps[-3:]:  # 只看最近的3个
        print(f"\n临时目录: {temp_path}")
        if temp_path.exists():
            pcap_files = list(temp_path.glob("*.pcap"))
            print(f"  包含的pcap文件: {len(pcap_files)}")
            for pcap_file in pcap_files:
                print(f"    {pcap_file.name}")
                
                # 分析这个文件
                if pcap_file.exists():
                    analyze_file_with_tshark(str(pcap_file), f"临时文件 {pcap_file.name}")

def main():
    """主分析函数"""
    print("PktMask 处理流水线各阶段分析")
    print("="*80)
    
    # 1. 分析原始文件
    original_file = "tests/samples/tls-single/tls_sample.pcap"
    analyze_file_with_tshark(original_file, "原始文件")
    
    # 2. 查找并分析处理后的文件
    output_dir = find_processed_files()
    if output_dir:
        processed_files = list(output_dir.glob("*.pcap"))
        for processed_file in processed_files:
            analyze_file_with_tshark(str(processed_file), f"处理后文件 {processed_file.name}")
    
    # 3. 分析临时文件
    analyze_temp_files()
    
    print("\n" + "="*80)
    print("🎯 分析总结:")
    print("1. 检查原始文件是否包含TLS ApplicationData")
    print("2. 检查去重阶段是否删除了ApplicationData数据包")
    print("3. 检查IP匿名化阶段是否影响了TLS数据")
    print("4. 确认MaskStage输入文件的实际状态")
    print("="*80)

if __name__ == "__main__":
    main()
