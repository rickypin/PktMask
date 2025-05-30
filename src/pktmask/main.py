#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
说明：
  PktMask - 一个用于处理 pcap/pcapng 文件中 IP 替换的 Web 服务，具有以下特点：
    1. 总目录路径由网页浏览选择 —— 主页显示脚本所在目录下的所有子目录，用户选择待处理的目录作为"总目录"。
    2. 替换处理开始后，采用 SSE 技术动态显示每一步执行情况，而非一次性显示所有日志。
    3. 针对子目录处理：
         - 如果子目录内所有原始文件均已有对应替换文件，则跳过该子目录；
         - 否则，对该子目录内所有原始文件进行处理（覆盖原有替换文件）。
    4. 输出中增加明显的分隔线、阶段标签和时间戳，以及最终的整体统计汇总信息。
    5. 页面顶部标题动态切换：在处理过程中显示"处理进行中..."，处理完成后自动修改为"处理完成"（包括浏览器 Tab 标题）。
    6. 每个子目录处理完成后，提供一个链接，点击后将在新标签页中以友好格式显示该子目录的 IP 替换详情日志（replacement.log）。
    7. IP 替换详情页面中，表格按原始 IP 排序，并在页面标题中显示当前子目录，便于用户区分。
    8. 【新增需求】在首页显示 IP 地址替换逻辑，该逻辑内容存放于程序同目录下的 IP_Replacement_Summary.md 文件（Markdown 格式），在页面中按照 Markdown 格式展示。
       
依赖：
  pip install scapy flask markdown
"""

import os
import json
import ipaddress
import datetime
import random
import urllib.parse
import markdown  # 用于将 Markdown 格式转换为 HTML

from flask import Flask, request, render_template_string, Response, stream_with_context
from scapy.all import PcapReader, PcapNgReader, wrpcap, IP, IPv6, TCP, UDP

app = Flask(__name__)

# 获取脚本所在的目录作为"根目录"
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# --- 辅助函数：根据 IP 字符串生成排序键 ---
def ip_sort_key(ip_str):
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

# ------------------ 随机替换（单段）函数 ------------------

def randomize_ipv4_segment(original_seg: str) -> str:
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

# ------------------ IPv4 分层替换函数 ------------------

def generate_new_ipv4_address_hierarchical(original_ip: str,
                                           freq1: dict, freq2: dict, freq3: dict,
                                           ipv4_first_map: dict, ipv4_second_map: dict, ipv4_third_map: dict) -> str:
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

# ------------------ IPv6 分层替换函数 ------------------

def generate_new_ipv6_address_hierarchical(original_ip: str,
                                           freq_ipv6_1: dict, freq_ipv6_2: dict, freq_ipv6_3: dict,
                                           freq_ipv6_4: dict, freq_ipv6_5: dict, freq_ipv6_6: dict, freq_ipv6_7: dict,
                                           ipv6_first_map: dict, ipv6_second_map: dict, ipv6_third_map: dict,
                                           ipv6_fourth_map: dict, ipv6_fifth_map: dict, ipv6_sixth_map: dict, ipv6_seventh_map: dict) -> str:
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

# ------------------ 预扫描函数 ------------------

def prescan_addresses(files_to_process, subdir_path, error_log):
    freq_ipv4_1, freq_ipv4_2, freq_ipv4_3 = {}, {}, {}
    freq_ipv6_1, freq_ipv6_2, freq_ipv6_3 = {}, {}, {}
    freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7 = {}, {}, {}, {}
    unique_ips = set()
    for f in files_to_process:
        file_path = os.path.join(subdir_path, f)
        ext = os.path.splitext(f)[1].lower()
        try:
            if ext == ".pcap":
                with PcapReader(file_path) as reader:
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
            elif ext == ".pcapng":
                with PcapNgReader(file_path) as reader:
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

# ------------------ 数据包处理 ------------------

def process_packet(packet, mapping):
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
    elif packet.haslayer(IPv6):
        ipv6_layer = packet.getlayer(IPv6)
        orig_src = ipv6_layer.src
        ipv6_layer.src = mapping.get(orig_src, orig_src)
        orig_dst = ipv6_layer.dst
        ipv6_layer.dst = mapping.get(orig_dst, orig_dst)
        if packet.haslayer(TCP):
            tcp_layer = packet.getlayer(TCP)
            if hasattr(tcp_layer, "chksum"):
                del tcp_layer.chksum
        elif packet.haslayer(UDP):
            udp_layer = packet.getlayer(UDP)
            if hasattr(udp_layer, "chksum"):
                del udp_layer.chksum

# ------------------ 文件处理 ------------------

def process_file(file_path, mapping, error_log):
    new_packets = []
    unique_ips_in_file = set()
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pcap":
            with PcapReader(file_path) as reader:
                for packet in reader:
                    if packet.haslayer(IP):
                        ip_layer = packet.getlayer(IP)
                        unique_ips_in_file.add(ip_layer.src)
                        unique_ips_in_file.add(ip_layer.dst)
                    elif packet.haslayer(IPv6):
                        ipv6_layer = packet.getlayer(IPv6)
                        unique_ips_in_file.add(ipv6_layer.src)
                        unique_ips_in_file.add(ipv6_layer.dst)
                    process_packet(packet, mapping)
                    new_packets.append(packet)
        elif ext == ".pcapng":
            with PcapNgReader(file_path) as reader:
                for packet in reader:
                    if packet.haslayer(IP):
                        ip_layer = packet.getlayer(IP)
                        unique_ips_in_file.add(ip_layer.src)
                        unique_ips_in_file.add(ip_layer.dst)
                    elif packet.haslayer(IPv6):
                        ipv6_layer = packet.getlayer(IPv6)
                        unique_ips_in_file.add(ipv6_layer.src)
                        unique_ips_in_file.add(ipv6_layer.dst)
                    process_packet(packet, mapping)
                    new_packets.append(packet)
        else:
            raise ValueError("不支持的文件扩展名")
        return new_packets, len(unique_ips_in_file)
    except Exception as e:
        error_log.append(f"{current_time()} - 处理文件 {file_path} 出错：{str(e)}")
        return None, len(unique_ips_in_file)

# ------------------ 子目录处理（流式生成日志） ------------------

def stream_subdirectory_process(subdir_path):
    # 将子目录路径转换为相对于 BASE_PATH 的相对路径
    rel_subdir = os.path.relpath(subdir_path, BASE_PATH)
    yield f"[{current_time()}] 开始处理子目录：{rel_subdir}"
    start_time = datetime.datetime.now()
    try:
        files = os.listdir(subdir_path)
    except Exception as e:
        yield f"[{current_time()}] 读取子目录出错：{str(e)}"
        return
    original_files = []
    for f in files:
        full_path = os.path.join(subdir_path, f)
        if os.path.isfile(full_path):
            name, ext = os.path.splitext(f)
            if ext.lower() in [".pcap", ".pcapng"] and "-Replaced" not in name:
                original_files.append(f)
    if not original_files:
        yield f"[{current_time()}] 子目录内未找到原始 pcap/pcapng 文件，跳过。"
        return
    all_replaced = True
    for f in original_files:
        name, ext = os.path.splitext(f)
        replaced_path = os.path.join(subdir_path, f"{name}-Replaced{ext}")
        if not os.path.exists(replaced_path):
            all_replaced = False
            break
    if all_replaced:
        yield f"[{current_time()}] 子目录内所有文件均已替换，跳过。"
        yield "[SUBDIR_RESULT] SKIPPED"
    else:
        files_to_process = original_files
        error_log_entries = []
        yield f"[{current_time()}] 【预扫描】开始..."
        (freq_ipv4_1, freq_ipv4_2, freq_ipv4_3,
         freq_ipv6_1, freq_ipv6_2, freq_ipv6_3, freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7,
         unique_ips) = prescan_addresses(files_to_process, subdir_path, error_log_entries)
        yield f"[{current_time()}] 【预扫描】完成，唯一 IP 数量：{len(unique_ips)}"
        mapping = {}
        ipv4_first_map, ipv4_second_map, ipv4_third_map = {}, {}, {}
        ipv6_first_map, ipv6_second_map, ipv6_third_map = {}, {}, {}
        ipv6_fourth_map, ipv6_fifth_map, ipv6_sixth_map, ipv6_seventh_map = {}, {}, {}, {}
        yield f"[{current_time()}] 【预计算映射】开始..."
        for ip in unique_ips:
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
        file_ip_counts = {}
        processed_file_count = 0
        for f in files_to_process:
            file_path = os.path.join(subdir_path, f)
            rel_file_path = os.path.relpath(file_path, BASE_PATH)
            yield f"[{current_time()}] 【文件处理】正在处理文件：{rel_file_path}"
            packets, unique_ip_count = process_file(file_path, mapping, error_log_entries)
            if packets is None:
                rel_file_path = os.path.relpath(file_path, BASE_PATH)
                yield f"[{current_time()}] 【文件处理】文件处理出错：{rel_file_path}，跳过。"
                continue
            name, ext = os.path.splitext(f)
            new_file_path = os.path.join(subdir_path, f"{name}-Replaced{ext}")
            try:
                wrpcap(new_file_path, packets)
                processed_file_count += 1
                file_ip_counts[f] = unique_ip_count
                rel_new_file_path = os.path.relpath(new_file_path, BASE_PATH)
                yield f"[{current_time()}] 【文件处理】文件处理成功：{rel_new_file_path} （唯一 IP 数量：{unique_ip_count}）"
            except Exception as e:
                error_log_entries.append(f"{current_time()} - 写出文件出错：{new_file_path}，{str(e)}")
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        log_data = {
            "processed_file_count": processed_file_count,
            "file_ip_counts": file_ip_counts,
            "total_unique_ips": len(mapping),
            "ip_mapping": mapping,
            "total_time_seconds": elapsed_time
        }
        replace_log_path = os.path.join(subdir_path, "replacement.log")
        try:
            with open(replace_log_path, "w", encoding="utf-8") as f_log:
                json.dump(log_data, f_log, indent=4, ensure_ascii=False)
            rel_replace_log_path = os.path.relpath(replace_log_path, BASE_PATH)
            yield f"[{current_time()}] 替换日志已写入：{rel_replace_log_path}"
        except Exception as e:
            yield f"[{current_time()}] 写入替换日志出错：{str(e)}"
        if error_log_entries:
            error_log_path = os.path.join(subdir_path, "error.log")
            try:
                with open(error_log_path, "w", encoding="utf-8") as f_error:
                    for entry in error_log_entries:
                        f_error.write(entry + "\n")
                rel_error_log_path = os.path.relpath(error_log_path, BASE_PATH)
                yield f"[{current_time()}] 错误日志已写入：{rel_error_log_path}"
            except Exception as e:
                yield f"[{current_time()}] 写入错误日志出错：{str(e)}"
        yield f"[{current_time()}] 子目录处理完成：{rel_subdir}，共处理 {processed_file_count} 个文件，总耗时 {elapsed_time:.3f} 秒。"
        yield f"[SUBDIR_RESULT] PROCESSED {processed_file_count} {elapsed_time:.3f}"
    # 无论处理还是跳过，都提供查看日志的链接（新标签打开）
    rel_path = os.path.relpath(subdir_path, BASE_PATH)
    encoded_rel = urllib.parse.quote(rel_path)
    yield f'[VIEW LOG] <a href="/log?subdir={encoded_rel}" target="_blank">查看 IP 替换详情</a>'

# ------------------ 总目录处理（流式生成日志） ------------------

def process_base_directory_stream(base_dir):
    # 将总目录路径转换为相对于 BASE_PATH 的相对路径用于显示
    rel_base = os.path.relpath(base_dir, BASE_PATH)
    start_all = datetime.datetime.now()
    total_subdirs = 0
    processed_subdirs = 0
    skipped_subdirs = 0
    yield f"[{current_time()}] 开始处理总目录：{rel_base}"
    yield "----------------------------------------"
    try:
        subdirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    except Exception as e:
        yield f"[{current_time()}] 读取总目录出错：{str(e)}"
        return
    if not subdirs:
        yield f"[{current_time()}] 目录 {rel_base} 下未找到子目录！"
        return
    for subdir in subdirs:
        total_subdirs += 1
        for log in stream_subdirectory_process(subdir):
            if log.startswith("[SUBDIR_RESULT]"):
                if "SKIPPED" in log:
                    skipped_subdirs += 1
                elif "PROCESSED" in log:
                    processed_subdirs += 1
                yield log
            else:
                yield log
        yield "----------------------------------------"
    total_time = (datetime.datetime.now() - start_all).total_seconds()
    yield f"[{current_time()}] 所有子目录处理完成。总子目录数：{total_subdirs}，已处理：{processed_subdirs}，跳过：{skipped_subdirs}，总耗时：{total_time:.3f} 秒。"
    yield "[TASK_COMPLETE]"

# ------------------ Flask 路由 ------------------

INDEX_HTML = """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <title>PCAP 替换处理</title>
  </head>
  <body>
    <h1>选择待处理的总目录</h1>
    <form action="/process" method="post">
      <label for="base_dir">请选择一个目录：</label>
      <select name="base_dir" id="base_dir" required>
        {% for d in dirs %}
          <option value="{{ d }}">{{ d }}</option>
        {% endfor %}
      </select>
      <br><br>
      <input type="submit" value="开始处理">
    </form>
    <hr>
    <h2>IP 地址替换逻辑</h2>
    <div id="markdown-content">
      {{ ip_replacement_summary|safe }}
    </div>
  </body>
</html>
"""

PROCESS_HTML = """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <title>处理进行中...</title>
    <style>
      #log { white-space: pre-wrap; border: 1px solid #ccc; padding: 10px; height: 400px; overflow-y: scroll; }
    </style>
  </head>
  <body>
    <h1 id="header">处理进行中...</h1>
    <div id="log"></div>
    <br>
    <a href="/">返回首页</a>
    <script>
      var source = new EventSource("/stream?base_dir={{ base_dir }}");
      source.onmessage = function(e) {
        if(e.data === "[TASK_COMPLETE]") {
          document.getElementById("header").innerHTML = "处理完成";
          document.title = "处理完成";
          source.close();
        } else {
          var logDiv = document.getElementById("log");
          logDiv.innerHTML += e.data + "\\n";
          logDiv.scrollTop = logDiv.scrollHeight;
        }
      };
      source.onerror = function(e) {
        console.log("EventSource 连接出错：", e);
        source.close();
      };
    </script>
  </body>
</html>
"""

# 新增：用于展示 IP 替换详情的友好页面（美化显示 JSON 日志），标题中显示当前子目录
LOG_HTML = """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <title>IP 替换详情 - 子目录：{{ subdir }}</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 20px; background: #f9f9f9; }
      h1 { color: #333; text-align: center; }
      .section { margin-bottom: 20px; background: #fff; padding: 15px; border: 1px solid #ddd; border-radius: 4px; }
      table { width: 600px; margin: auto; border-collapse: collapse; table-layout: fixed; }
      th, td { padding: 8px 12px; border: 1px solid #ddd; text-align: left; word-wrap: break-word; }
      th { background-color: #f2f2f2; }
    </style>
  </head>
  <body>
    <h1>IP 替换详情 - 子目录：{{ subdir }}</h1>
    <div class="section">
      <h2>整体统计</h2>
      <p><strong>处理文件数量:</strong> {{ processed_file_count }}</p>
      <p><strong>唯一 IP 数量:</strong> {{ total_unique_ips }}</p>
      <p><strong>总耗时 (秒):</strong> {{ total_time_seconds }}</p>
      <p><strong>文件 IP 统计:</strong></p>
      <ul>
      {% for filename, count in file_ip_counts.items() %}
        <li>{{ filename }}: {{ count }}</li>
      {% endfor %}
      </ul>
    </div>
    <div class="section">
      <h2>IP 映射详情</h2>
      <table>
        <tr>
          <th>原始 IP</th>
          <th>替换后 IP</th>
        </tr>
        {% for orig, new in sorted_ip_mapping %}
        <tr>
          <td>{{ orig }}</td>
          <td>{{ new }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    try:
        dirs = [d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d)) and not d.startswith('.')]
    except Exception as e:
        dirs = []
    # 读取同目录下的 IP_Replacement_Summary.md 文件，将 Markdown 格式转换为 HTML 后传递给模板
    summary_path = os.path.join(BASE_PATH, "IP_Replacement_Summary.md")
    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_md = f.read()
        summary_html = markdown.markdown(summary_md)
    except Exception as e:
        summary_html = f"<p>无法读取 IP 替换逻辑文件: {str(e)}</p>"
    return render_template_string(INDEX_HTML, dirs=dirs, ip_replacement_summary=summary_html)

@app.route("/process", methods=["POST"])
def process_page():
    selected_dir = request.form.get("base_dir")
    if not selected_dir:
        return "错误：未选择目录！"
    base_dir = os.path.join(BASE_PATH, selected_dir)
    return render_template_string(PROCESS_HTML, base_dir=base_dir)

@app.route("/stream", methods=["GET"])
def stream():
    base_dir = request.args.get("base_dir")
    if not base_dir:
        return "错误：未提供目录参数！", 400
    def generate():
        for log in process_base_directory_stream(base_dir):
            yield f"data: {log}\n\n"
    return Response(stream_with_context(generate()), mimetype="text/event-stream")

# 日志查看路由，展示 replacement.log，以友好方式显示，并对 IP 映射按排序键排序
@app.route("/log", methods=["GET"])
def view_log():
    subdir = request.args.get("subdir")
    if not subdir:
        return "错误：未提供子目录参数！", 400
    full_subdir = os.path.join(BASE_PATH, subdir)
    log_file = os.path.join(full_subdir, "replacement.log")
    if not os.path.exists(log_file):
        return "未找到日志文件", 404
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            log_data = json.load(f)
        ip_mapping = log_data.get("ip_mapping", {})
        sorted_ip_mapping = sorted(ip_mapping.items(), key=lambda kv: ip_sort_key(kv[0]))
        return render_template_string(LOG_HTML,
                                      subdir=subdir,
                                      processed_file_count=log_data.get("processed_file_count"),
                                      file_ip_counts=log_data.get("file_ip_counts"),
                                      total_unique_ips=log_data.get("total_unique_ips"),
                                      sorted_ip_mapping=sorted_ip_mapping,
                                      total_time_seconds=log_data.get("total_time_seconds"))
    except Exception as e:
        return f"读取日志文件出错：{str(e)}", 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
