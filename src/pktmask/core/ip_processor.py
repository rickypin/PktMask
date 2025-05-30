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

from scapy.all import PcapReader, PcapNgReader, wrpcap, IP, IPv6, TCP, UDP

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
    newA = ipv4_first_map.setdefault(A, randomize_ipv4_segment(A))
    key2 = ".".join(parts[:2])
    newB = ipv4_second_map.setdefault(key2, randomize_ipv4_segment(B)) if freq2.get(key2, 0) >= 2 else randomize_ipv4_segment(B)
    key3 = ".".join(parts[:3])
    newC = ipv4_third_map.setdefault(key3, randomize_ipv4_segment(C)) if freq3.get(key3, 0) >= 2 else randomize_ipv4_segment(C)
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
        new_seg = map_list[i].setdefault(key, randomize_ipv6_segment(parts[i])) if freq_list[i].get(key, 0) >= 2 else randomize_ipv6_segment(parts[i])
        new_parts.append(new_seg)
    new_parts.append(parts[7])
    return ":".join(new_parts)

def prescan_addresses(files_to_process: List[str], subdir_path: str, error_log: List[str]) -> Tuple:
    """预扫描文件中的 IP 地址"""
    freq_ipv4_1, freq_ipv4_2, freq_ipv4_3 = {}, {}, {}
    freq_ipv6_1, freq_ipv6_2, freq_ipv6_3 = {}, {}, {}
    freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7 = {}, {}, {}, {}
    unique_ips = set()
    
    for f in files_to_process:
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

def process_file(file_path: str, mapping: Dict[str, str], error_log: List[str]) -> bool:
    """处理单个文件"""
    try:
        ext = os.path.splitext(file_path)[1].lower()
        reader_class = PcapNgReader if ext == ".pcapng" else PcapReader
        with reader_class(file_path) as reader:
            packets = [process_packet(packet, mapping) for packet in reader]
        wrpcap(file_path, packets)
        return True
    except Exception as e:
        error_log.append(f"{current_time()} - 处理文件 {file_path} 出错：{str(e)}")
        return False 