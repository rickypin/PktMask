#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
说明：
  本程序用于处理 pcap/pcapng 文件，去除其中完全重复的报文，并输出去重后的新文件。
  主要逻辑：
    1. 根据文件扩展名（.pcap 或 .pcapng）采用对应的 scapy 读取器读取报文；
    2. 利用报文的字节内容去重，完全相同的报文只保留一份；
    3. 将去重后的报文写入新的文件（文件名添加“-deduped”后缀）。
    
依赖：
  pip install scapy
"""

import os
import sys
import datetime
import json
from scapy.all import PcapReader, PcapNgReader, wrpcap

def current_time():
    """返回当前时间的字符串，用于日志记录。"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def process_file_dedup(file_path, error_log):
    """
    处理单个 pcap/pcapng 文件，去除完全重复的报文。
    
    参数：
      file_path：待处理的文件路径；
      error_log：用于记录错误信息的列表。
      
    返回：
      去重后的报文列表，以及原文件中报文的总数与去重后报文的数量。
    """
    packets = []
    total_count = 0
    try:
        ext = os.path.splitext(file_path)[1].lower()
        # 根据扩展名选择对应读取器
        if ext == ".pcap":
            reader_cls = PcapReader
        elif ext == ".pcapng":
            reader_cls = PcapNgReader
        else:
            raise ValueError("不支持的文件扩展名")
        
        # 使用集合保存已出现的报文字节数据，用于去重
        seen = set()
        with reader_cls(file_path) as reader:
            for pkt in reader:
                total_count += 1
                # 使用 bytes(pkt) 获取报文字节表示
                raw_bytes = bytes(pkt)
                if raw_bytes in seen:
                    continue
                seen.add(raw_bytes)
                packets.append(pkt)
        return packets, total_count, len(packets)
    except Exception as e:
        error_log.append(f"{current_time()} - 处理文件 {file_path} 出错：{str(e)}")
        return None, total_count, 0

def main():
    if len(sys.argv) < 2:
        print("用法：python3 remove_duplicates.py <pcap/pcapng 文件路径>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.isfile(file_path):
        print(f"错误：文件 {file_path} 不存在！")
        sys.exit(1)
    
    error_log = []
    print(f"[{current_time()}] 开始处理文件：{file_path}")
    packets, total, deduped = process_file_dedup(file_path, error_log)
    if packets is None:
        print(f"[{current_time()}] 处理失败，请检查错误日志。")
        for err in error_log:
            print(err)
        sys.exit(1)
    
    # 构造输出文件路径（在原文件名后添加“-deduped”）
    dir_name, base_name = os.path.split(file_path)
    name, ext = os.path.splitext(base_name)
    output_file = os.path.join(dir_name, f"{name}-deduped{ext}")
    
    try:
        wrpcap(output_file, packets)
        print(f"[{current_time()}] 去重完成：原报文数 {total}，去重后报文数 {deduped}")
        print(f"[{current_time()}] 去重文件已写入：{output_file}")
    except Exception as e:
        error_log.append(f"{current_time()} - 写出文件 {output_file} 出错：{str(e)}")
        print(f"[{current_time()}] 写出文件出错：{str(e)}")
    
    # 如果有错误记录，则写入 error.log 文件
    if error_log:
        error_log_file = os.path.join(dir_name, "error.log")
        try:
            with open(error_log_file, "w", encoding="utf-8") as f_error:
                for entry in error_log:
                    f_error.write(entry + "\n")
            print(f"[{current_time()}] 错误日志已写入：{error_log_file}")
        except Exception as e:
            print(f"[{current_time()}] 写入错误日志出错：{str(e)}")

if __name__ == "__main__":
    main()
