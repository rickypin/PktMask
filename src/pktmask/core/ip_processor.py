#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IP 地址处理核心模块
包含 IP 地址替换的核心逻辑
"""

import os
import random
import ipaddress
from datetime import datetime
from typing import Dict, Set, Tuple, List
import json
from jinja2 import Template
import sys

from scapy.all import PcapReader, PcapNgReader, wrpcap, IP, IPv6, TCP, UDP

# 自动加载HTML模板，兼容PyInstaller打包和开发环境
if hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS
else:
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATE_PATH = os.path.join(base_path, 'resources', 'log_template.html')
with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
    LOG_HTML = f.read()

def current_time() -> str:
    """获取当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ip_sort_key(ip_str: str) -> tuple:
    """根据 IP 字符串生成排序键"""
    try:
        if '.' in ip_str:
            parts = ip_str.split('.')
            return (4,) + tuple(int(x) for x in parts)
        else:
            try:
                ip_obj = ipaddress.IPv6Address(ip_str)
                ip_str = ip_obj.exploded
            except Exception:
                pass
            parts = ip_str.split(':')
            return (6,) + tuple(int(x, 16) for x in parts)
    except Exception:
        return (99,)

def randomize_ipv4_segment(original_seg: str) -> str:
    """随机化 IPv4 地址段"""
    orig_int = int(original_seg)
    n = len(original_seg)
    if n == 1:
        lower, upper, delta = 0, 9, 2
    elif n == 2:
        lower, upper, delta = 10, 99, 3
    elif n == 3:
        lower, upper, delta = 100, 255, 20
    else:
        lower = 10 ** (n - 1)
        upper = min(10 ** n - 1, 255)
        delta = 20
    cand_lower = max(lower, orig_int - delta)
    cand_upper = min(upper, orig_int + delta)
    count = (cand_upper - cand_lower + 1) - 1
    if count <= 0:
        cand_lower, cand_upper = lower, upper
        count = (upper - lower + 1) - 1
    r = random.randint(0, count - 1)
    candidate = cand_lower + r
    if candidate >= orig_int:
        candidate += 1
    return str(candidate)

def randomize_ipv6_segment(original_seg: str) -> str:
    """随机化 IPv6 地址段"""
    n = len(original_seg)
    orig_int = int(original_seg, 16)
    lower = 16 ** (n - 1) if n > 1 else 0
    upper = 16 ** n - 1
    if n == 1:
        delta = 2
    elif n == 2:
        delta = 5
    elif n == 3:
        delta = 20
    elif n == 4:
        delta = 50
    else:
        delta = 50
    cand_lower = max(lower, orig_int - delta)
    cand_upper = min(upper, orig_int + delta)
    count = (cand_upper - cand_lower + 1) - 1
    if count <= 0:
        cand_lower, cand_upper = lower, upper
        count = (upper - lower + 1) - 1
    r = random.randint(0, count - 1)
    candidate = cand_lower + r
    if candidate >= orig_int:
        candidate += 1
    return format(candidate, 'x').zfill(n)

def generate_new_ipv4_address_hierarchical(
    original_ip: str,
    freq1: Dict[str, int],
    freq2: Dict[str, int],
    freq3: Dict[str, int],
    ipv4_first_map: Dict[str, str],
    ipv4_second_map: Dict[str, str],
    ipv4_third_map: Dict[str, str]
) -> str:
    """生成新的 IPv4 地址（分层替换）"""
    parts = original_ip.split('.')
    if len(parts) != 4:
        return original_ip
    A, B, C, D = parts
    
    # 第一块：根据频率决定是否统一替换
    if freq1.get(A, 0) >= 2:
        if A not in ipv4_first_map:
            ipv4_first_map[A] = randomize_ipv4_segment(A)
        newA = ipv4_first_map[A]
    else:
        newA = randomize_ipv4_segment(A)
    
    # 第二块：根据前两块频率决定是否统一替换
    key2 = ".".join(parts[:2])
    if freq2.get(key2, 0) >= 2:
        if key2 not in ipv4_second_map:
            ipv4_second_map[key2] = randomize_ipv4_segment(B)
        newB = ipv4_second_map[key2]
    else:
        newB = randomize_ipv4_segment(B)
    
    # 第三块：根据前三块频率决定是否统一替换
    key3 = ".".join(parts[:3])
    if freq3.get(key3, 0) >= 2:
        if key3 not in ipv4_third_map:
            ipv4_third_map[key3] = randomize_ipv4_segment(C)
        newC = ipv4_third_map[key3]
    else:
        newC = randomize_ipv4_segment(C)
    
    return f"{newA}.{newB}.{newC}.{D}"

def generate_new_ipv6_address_hierarchical(
    original_ip: str,
    freq_ipv6_1: Dict[str, int],
    freq_ipv6_2: Dict[str, int],
    freq_ipv6_3: Dict[str, int],
    freq_ipv6_4: Dict[str, int],
    freq_ipv6_5: Dict[str, int],
    freq_ipv6_6: Dict[str, int],
    freq_ipv6_7: Dict[str, int],
    ipv6_first_map: Dict[str, str],
    ipv6_second_map: Dict[str, str],
    ipv6_third_map: Dict[str, str],
    ipv6_fourth_map: Dict[str, str],
    ipv6_fifth_map: Dict[str, str],
    ipv6_sixth_map: Dict[str, str],
    ipv6_seventh_map: Dict[str, str]
) -> str:
    """生成新的 IPv6 地址（分层替换）"""
    try:
        ip_obj = ipaddress.IPv6Address(original_ip)
        parts = ip_obj.exploded.split(':')
    except Exception:
        return original_ip
    if len(parts) != 8:
        return original_ip
    
    freq_list = [freq_ipv6_1, freq_ipv6_2, freq_ipv6_3, freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7]
    map_list = [ipv6_first_map, ipv6_second_map, ipv6_third_map, ipv6_fourth_map, ipv6_fifth_map, ipv6_sixth_map, ipv6_seventh_map]
    
    new_parts = []
    for i in range(7):
        key = ":".join(parts[:i+1])
        # 根据频率决定是否统一替换
        if freq_list[i].get(key, 0) >= 2:
            if key not in map_list[i]:
                map_list[i][key] = randomize_ipv6_segment(parts[i])
            new_seg = map_list[i][key]
        else:
            new_seg = randomize_ipv6_segment(parts[i])
        new_parts.append(new_seg)
    
    new_parts.append(parts[7])  # 最后一组保持不变
    return ":".join(new_parts)

def prescan_addresses(files_to_process: List[str], subdir_path: str, error_log: List[str]) -> Tuple:
    """预扫描文件中的 IP 地址"""
    freq_ipv4_1, freq_ipv4_2, freq_ipv4_3 = {}, {}, {}
    freq_ipv6_1, freq_ipv6_2, freq_ipv6_3 = {}, {}, {}
    freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7 = {}, {}, {}, {}
    unique_ips = set()
    
    for f in files_to_process:
        # 跳过带有 -Replaced 后缀的文件
        if f.endswith('-Replaced.pcap') or f.endswith('-Replaced.pcapng'):
            continue
            
        file_path = os.path.join(subdir_path, f)
        ext = os.path.splitext(f)[1].lower()
        try:
            reader_class = PcapNgReader if ext == ".pcapng" else PcapReader
            with reader_class(file_path) as reader:
                for packet in reader:
                    if packet.haslayer(IP):
                        ip_str = packet.getlayer(IP).src
                        unique_ips.add(ip_str)
                        unique_ips.add(packet.getlayer(IP).dst)
                        try:
                            ipaddress.IPv4Address(ip_str)
                        except Exception:
                            continue
                        parts = ip_str.split('.')
                        if len(parts) != 4:
                            continue
                        freq_ipv4_1[parts[0]] = freq_ipv4_1.get(parts[0], 0) + 1
                        freq_ipv4_2[".".join(parts[:2])] = freq_ipv4_2.get(".".join(parts[:2]), 0) + 1
                        freq_ipv4_3[".".join(parts[:3])] = freq_ipv4_3.get(".".join(parts[:3]), 0) + 1
                    if packet.haslayer(IPv6):
                        ip_str = packet.getlayer(IPv6).src
                        unique_ips.add(ip_str)
                        unique_ips.add(packet.getlayer(IPv6).dst)
                        try:
                            ip_obj = ipaddress.IPv6Address(ip_str)
                        except Exception:
                            continue
                        parts = ip_obj.exploded.split(':')
                        if len(parts) != 8:
                            continue
                        freq_ipv6_1[parts[0]] = freq_ipv6_1.get(parts[0], 0) + 1
                        freq_ipv6_2[":".join(parts[:2])] = freq_ipv6_2.get(":".join(parts[:2]), 0) + 1
                        freq_ipv6_3[":".join(parts[:3])] = freq_ipv6_3.get(":".join(parts[:3]), 0) + 1
                        freq_ipv6_4[":".join(parts[:4])] = freq_ipv6_4.get(":".join(parts[:4]), 0) + 1
                        freq_ipv6_5[":".join(parts[:5])] = freq_ipv6_5.get(":".join(parts[:5]), 0) + 1
                        freq_ipv6_6[":".join(parts[:6])] = freq_ipv6_6.get(":".join(parts[:6]), 0) + 1
                        freq_ipv6_7[":".join(parts[:7])] = freq_ipv6_7.get(":".join(parts[:7]), 0) + 1
        except Exception as e:
            error_log.append(f"{current_time()} - 预扫描文件 {file_path} 出错：{str(e)}")
    
    return (freq_ipv4_1, freq_ipv4_2, freq_ipv4_3,
            freq_ipv6_1, freq_ipv6_2, freq_ipv6_3, freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7,
            unique_ips)

def process_packet(packet, mapping: Dict[str, str]):
    """处理单个数据包"""
    if packet.haslayer(IP):
        ip_layer = packet.getlayer(IP)
        orig_src = ip_layer.src
        ip_layer.src = mapping.get(orig_src, orig_src)
        orig_dst = ip_layer.dst
        ip_layer.dst = mapping.get(orig_dst, orig_dst)
        if hasattr(ip_layer, "chksum"):
            del ip_layer.chksum
        if packet.haslayer(TCP):
            tcp_layer = packet.getlayer(TCP)
            if hasattr(tcp_layer, "chksum"):
                del tcp_layer.chksum
        elif packet.haslayer(UDP):
            udp_layer = packet.getlayer(UDP)
            if hasattr(udp_layer, "chksum"):
                del udp_layer.chksum
    if packet.haslayer(IPv6):
        ipv6_layer = packet.getlayer(IPv6)
        orig_src = ipv6_layer.src
        ipv6_layer.src = mapping.get(orig_src, orig_src)
        orig_dst = ipv6_layer.dst
        ipv6_layer.dst = mapping.get(orig_dst, orig_dst)
        if hasattr(ipv6_layer, "chksum"):
            del ipv6_layer.chksum
        if packet.haslayer(TCP):
            tcp_layer = packet.getlayer(TCP)
            if hasattr(tcp_layer, "chksum"):
                del tcp_layer.chksum
        elif packet.haslayer(UDP):
            udp_layer = packet.getlayer(UDP)
            if hasattr(udp_layer, "chksum"):
                del udp_layer.chksum
    return packet

def process_file(file_path: str, mapping: Dict[str, str], error_log: List[str]) -> (bool, Dict[str, str]):
    """处理单个文件，返回是否成功及本文件涉及的IP映射"""
    try:
        # 仅处理不带 '-Replaced' 后缀的文件
        if file_path.endswith('-Replaced.pcap') or file_path.endswith('-Replaced.pcapng'):
            return True, {}  # 改为返回 True，表示正常跳过

        # 用于统计本文件中实际使用的IP
        file_used_ips = set()
        
        ext = os.path.splitext(file_path)[1].lower()
        reader_class = PcapNgReader if ext == ".pcapng" else PcapReader
        with reader_class(file_path) as reader:
            packets = []
            for packet in reader:
                # 先保存原始IP
                if packet.haslayer(IP):
                    orig_src = packet.getlayer(IP).src
                    orig_dst = packet.getlayer(IP).dst
                    file_used_ips.add(orig_src)
                    file_used_ips.add(orig_dst)
                if packet.haslayer(IPv6):
                    orig_src = packet.getlayer(IPv6).src
                    orig_dst = packet.getlayer(IPv6).dst
                    file_used_ips.add(orig_src)
                    file_used_ips.add(orig_dst)
                # 再处理数据包
                packets.append(process_packet(packet, mapping))

        # 输出文件名加 -Replaced 后缀，直接覆盖
        base, ext = os.path.splitext(file_path)
        new_file_path = f"{base}-Replaced{ext}"
        wrpcap(new_file_path, packets)

        # 只返回本文件中实际使用的IP的映射
        file_mapping = {ip: mapping[ip] for ip in file_used_ips if ip in mapping}
        return True, file_mapping
    except Exception as e:
        error_log.append(f"{current_time()} - 处理文件 {file_path} 出错：{str(e)}")
        return False, {}

def stream_subdirectory_process(subdir_path, base_path=None):
    """处理子目录，确保跨文件的 IP 替换一致性"""
    if base_path is None:
        base_path = os.path.dirname(subdir_path)
    rel_subdir = os.path.relpath(subdir_path, base_path)
    start_time = datetime.now()
    yield f"[{current_time()}] 开始处理子目录：{rel_subdir}"

    # 检查是否所有文件都已替换
    original_files = []
    all_replaced = True
    for f in os.listdir(subdir_path):
        if f.lower().endswith(('.pcap', '.pcapng')):
            if not f.endswith('-Replaced.pcap') and not f.endswith('-Replaced.pcapng'):
                original_files.append(f)
                all_replaced = False

    if all_replaced:
        yield f"[{current_time()}] 子目录内所有文件均已替换，跳过。"
        yield "[SUBDIR_RESULT] SKIPPED"
    else:
        files_to_process = original_files
        error_log_entries = []
        yield f"[{current_time()}] 【预扫描】开始..."
        
        # 预扫描所有文件，收集所有 IP 地址和频率
        (freq_ipv4_1, freq_ipv4_2, freq_ipv4_3,
         freq_ipv6_1, freq_ipv6_2, freq_ipv6_3, freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7,
         all_ips) = prescan_addresses(files_to_process, subdir_path, error_log_entries)
        
        yield f"[{current_time()}] 【预扫描】完成，唯一 IP 数量：{len(all_ips)}"
        
        # 生成全局 IP 映射
        mapping = {}
        ipv4_first_map, ipv4_second_map, ipv4_third_map = {}, {}, {}
        ipv6_first_map, ipv6_second_map, ipv6_third_map = {}, {}, {}
        ipv6_fourth_map, ipv6_fifth_map, ipv6_sixth_map, ipv6_seventh_map = {}, {}, {}, {}
        
        yield f"[{current_time()}] 【预计算映射】开始..."
        
        # 先对所有IP进行排序，确保生成顺序一致
        sorted_ips = sorted(all_ips, key=ip_sort_key)
        
        # 一次性生成所有IP的映射
        for ip in sorted_ips:
            try:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.version == 4:
                    mapping[ip] = generate_new_ipv4_address_hierarchical(
                        ip, freq_ipv4_1, freq_ipv4_2, freq_ipv4_3,
                        ipv4_first_map, ipv4_second_map, ipv4_third_map
                    )
                else:
                    mapping[ip] = generate_new_ipv6_address_hierarchical(
                        ip, freq_ipv6_1, freq_ipv6_2, freq_ipv6_3,
                        freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7,
                        ipv6_first_map, ipv6_second_map, ipv6_third_map,
                        ipv6_fourth_map, ipv6_fifth_map, ipv6_sixth_map, ipv6_seventh_map
                    )
            except Exception as e:
                error_log_entries.append(f"{current_time()} - 预计算映射出错：{str(e)}")
        
        yield f"[{current_time()}] 【预计算映射】完成."
        
        # 处理每个文件，使用同一个映射表
        file_ip_counts = {}
        processed_file_count = 0
        actual_used_ips = set()  # 用于记录实际使用的IP
        file_mappings = {}  # 用于记录每个文件的映射关系
        
        for f in files_to_process:
            file_path = os.path.join(subdir_path, f)
            rel_file_path = os.path.relpath(file_path, base_path)
            yield f"[{current_time()}] 【文件处理】正在处理文件：{rel_file_path}"
            
            success, file_mapping = process_file(file_path, mapping, error_log_entries)
            if not success:
                yield f"[{current_time()}] 【文件处理】文件处理出错：{rel_file_path}，跳过。"
                continue
            
            processed_file_count += 1
            file_ip_counts[f] = len(file_mapping)
            actual_used_ips.update(file_mapping.keys())  # 更新实际使用的IP集合
            file_mappings[f] = file_mapping  # 保存文件映射关系
            rel_new_file_path = os.path.relpath(f"{os.path.splitext(file_path)[0]}-Replaced{os.path.splitext(f)[1]}", base_path)
            yield f"[{current_time()}] 【文件处理】文件处理成功：{rel_new_file_path} （唯一 IP 数量：{len(file_mapping)}）"
        
        # 只保留实际使用的IP的映射
        final_mapping = {ip: mapping[ip] for ip in actual_used_ips}
        
        # 生成处理报告
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        # 基础统计
        stats = {
            "processed_file_count": processed_file_count,
            "total_unique_ips": len(final_mapping),
            "total_time_seconds": elapsed_time,
            "file_ip_counts": file_ip_counts
        }
        
        # 生成日志数据
        log_data = {
            "stats": stats,
            "file_mappings": {f: dict(sorted(m.items(), key=lambda x: ip_sort_key(x[0]))) 
                            for f, m in file_mappings.items()},
            "total_mapping": dict(sorted(final_mapping.items(), key=lambda x: ip_sort_key(x[0])))
        }
        
        # 保存处理报告
        replace_log_path = os.path.join(subdir_path, "replacement.log")
        try:
            with open(replace_log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            error_log_entries.append(f"{current_time()} - 保存处理报告出错：{str(e)}")
        
        # 生成 HTML 报告
        try:
            html_path = os.path.join(subdir_path, "replacement.html")
            html_content = Template(LOG_HTML).render(
                subdir=rel_subdir,
                now=current_time(),
                stats=stats,
                file_mappings=file_mappings,
                total_mapping=final_mapping
            )
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            error_log_entries.append(f"{current_time()} - 生成 HTML 报告出错：{str(e)}")
        
        # 输出处理结果
        if error_log_entries:
            yield f"[{current_time()}] 【处理完成】处理过程中出现 {len(error_log_entries)} 个错误："
            for error in error_log_entries:
                yield f"[{current_time()}] {error}"
            yield "[SUBDIR_RESULT] ERROR"
        else:
            yield f"[{current_time()}] 【处理完成】成功处理 {processed_file_count} 个文件，总耗时 {elapsed_time:.2f} 秒"
            yield "[SUBDIR_RESULT] SUCCESS" 