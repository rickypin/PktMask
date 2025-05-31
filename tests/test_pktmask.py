#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask 测试程序
用于测试 IP 替换功能
"""

import os
import json
import ipaddress
from pathlib import Path
from typing import Dict, Set, List, Tuple

from scapy.all import PcapReader, PcapNgReader, IP, IPv6

def get_test_dir() -> str:
    """获取测试目录路径"""
    return os.path.expanduser("~/Desktop/TestCases")

def normalize_ip(ip_str: str) -> str:
    """标准化 IP 地址格式"""
    try:
        if '.' in ip_str:  # IPv4
            return str(ipaddress.IPv4Address(ip_str))
        else:  # IPv6
            return str(ipaddress.IPv6Address(ip_str))
    except Exception:
        return ip_str

def get_all_ips_in_file(file_path: str) -> Set[str]:
    """获取文件中所有的 IP 地址"""
    ips = set()
    ext = os.path.splitext(file_path)[1].lower()
    reader_class = PcapNgReader if ext == ".pcapng" else PcapReader
    try:
        with reader_class(file_path) as reader:
            for packet in reader:
                if packet.haslayer(IP):
                    src_ip = normalize_ip(packet.getlayer(IP).src)
                    dst_ip = normalize_ip(packet.getlayer(IP).dst)
                    if src_ip:
                        ips.add(src_ip)
                    if dst_ip:
                        ips.add(dst_ip)
                if packet.haslayer(IPv6):
                    src_ip = normalize_ip(packet.getlayer(IPv6).src)
                    dst_ip = normalize_ip(packet.getlayer(IPv6).dst)
                    if src_ip:
                        ips.add(src_ip)
                    if dst_ip:
                        ips.add(dst_ip)
    except Exception as e:
        print(f"读取文件 {file_path} 出错：{str(e)}")
    return ips

def get_ip_mapping_from_files(original_file: str, replaced_file: str) -> Dict[str, str]:
    """从原始文件和替换文件中获取 IP 映射关系"""
    mapping = {}
    try:
        # 读取原始文件中的 IP
        orig_ips = get_all_ips_in_file(original_file)
        
        # 读取替换文件中的 IP
        replaced_ips = get_all_ips_in_file(replaced_file)
        
        # 如果两个文件中的 IP 数量相同，说明是一一对应的
        if len(orig_ips) == len(replaced_ips):
            # 将 IP 地址排序，确保对应关系正确
            orig_ips_list = sorted(list(orig_ips))
            replaced_ips_list = sorted(list(replaced_ips))
            
            # 创建映射关系
            for orig_ip, replaced_ip in zip(orig_ips_list, replaced_ips_list):
                mapping[orig_ip] = replaced_ip
        else:
            print(f"警告：文件 {os.path.basename(original_file)} 和 {os.path.basename(replaced_file)} 中的 IP 数量不一致")
            print(f"原始文件 IP 数量：{len(orig_ips)}")
            print(f"替换文件 IP 数量：{len(replaced_ips)}")
            
            # 尝试通过日志文件获取映射关系
            log_path = os.path.join(os.path.dirname(original_file), "replacement.log")
            if os.path.exists(log_path):
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        log_mapping = json.load(f)
                        # 只保留原始文件中存在的 IP 的映射
                        for orig_ip in orig_ips:
                            if orig_ip in log_mapping:
                                mapping[orig_ip] = log_mapping[orig_ip]
                except Exception as e:
                    print(f"读取日志文件出错：{str(e)}")
    
    except Exception as e:
        print(f"获取 IP 映射关系出错：{str(e)}")
    
    return mapping

def verify_replacement_log(log_path: str, original_ips: Set[str]) -> Tuple[bool, str]:
    """验证替换日志文件"""
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
        
        # 标准化所有 IP 地址
        normalized_mapping = {normalize_ip(k): normalize_ip(v) for k, v in mapping.items()}
        normalized_original_ips = {normalize_ip(ip) for ip in original_ips}
        
        # 检查映射中的 IP 是否都在原始文件中
        for orig_ip in normalized_mapping.keys():
            if orig_ip not in normalized_original_ips:
                return False, f"日志中包含未在原始文件中出现的 IP：{orig_ip}"
        
        # 检查原始文件中的 IP 是否都有映射
        for orig_ip in normalized_original_ips:
            if orig_ip not in normalized_mapping:
                return False, f"原始文件中的 IP 没有对应的映射：{orig_ip}"
        
        # 检查映射是否有效
        for orig_ip, new_ip in normalized_mapping.items():
            try:
                if '.' in orig_ip:
                    ipaddress.IPv4Address(orig_ip)
                    ipaddress.IPv4Address(new_ip)
                else:
                    ipaddress.IPv6Address(orig_ip)
                    ipaddress.IPv6Address(new_ip)
            except Exception as e:
                return False, f"IP 映射无效：{orig_ip} -> {new_ip}，错误：{str(e)}"
        
        return True, "验证通过"
    except Exception as e:
        return False, f"验证过程出错：{str(e)}"

def verify_ip_consistency(replaced_files: List[str], subdir_path: str) -> List[str]:
    """验证 IP 替换的一致性"""
    if len(replaced_files) <= 1:
        print("\n目录中只有一个替换文件，无需检查 IP 替换一致性")
        return []

    errors = []
    # 使用第一个文件作为基准
    base_file = replaced_files[0]
    print(f"\n检查 IP 替换一致性...")
    print(f"基准文件：{base_file}")
    
    # 获取基准文件的原始文件
    base_original = base_file.replace('-Replaced.pcap', '.pcap').replace('-Replaced.pcapng', '.pcapng')
    base_original_path = os.path.join(subdir_path, base_original)
    base_replaced_path = os.path.join(subdir_path, base_file)
    
    # 获取基准文件的 IP 映射
    base_mapping = get_ip_mapping_from_files(base_original_path, base_replaced_path)
    if not base_mapping:
        errors.append(f"无法从基准文件 {base_file} 获取 IP 映射")
        return errors

    # 检查其他文件的映射是否一致
    for file in replaced_files[1:]:
        print(f"\n当前文件：{file}")
        # 获取当前文件的原始文件
        current_original = file.replace('-Replaced.pcap', '.pcap').replace('-Replaced.pcapng', '.pcapng')
        current_original_path = os.path.join(subdir_path, current_original)
        current_replaced_path = os.path.join(subdir_path, file)
        
        current_mapping = get_ip_mapping_from_files(current_original_path, current_replaced_path)
        if not current_mapping:
            errors.append(f"无法从文件 {file} 获取 IP 映射")
            continue

        # 检查每个 IP 的映射是否一致
        for ip, new_ip in base_mapping.items():
            if ip in current_mapping:
                if current_mapping[ip] != new_ip:
                    error_msg = (
                        f"IP {ip} 的映射不一致：\n"
                        f"  基准文件 {base_file} 映射为：{new_ip}\n"
                        f"  当前文件 {file} 映射为：{current_mapping[ip]}"
                    )
                    errors.append(error_msg)
                    print(error_msg)

    return errors

def test_directory(subdir_path: str) -> List[str]:
    """测试单个目录"""
    print(f"\n测试子目录：{os.path.basename(subdir_path)}")
    errors = []

    # 获取所有原始文件和替换文件
    original_files = []
    replaced_files = []
    for f in os.listdir(subdir_path):
        if f.lower().endswith(('.pcap', '.pcapng')):
            if f.endswith('-Replaced.pcap') or f.endswith('-Replaced.pcapng'):
                replaced_files.append(f)
            else:
                original_files.append(f)

    # 收集所有原始文件中的 IP
    all_original_ips = set()
    for f in original_files:
        file_path = os.path.join(subdir_path, f)
        print(f"\n检查文件：{f}")
        ips = get_all_ips_in_file(file_path)
        print(f"文件中的 IP 数量：{len(ips)}")
        print("文件中的 IP 示例：")
        for ip in sorted(ips)[:5]:  # 只显示前 5 个 IP
            print(f"  - {ip}")
            all_original_ips.add(ip)

        # 检查对应的替换文件
        replaced_file = f.replace('.pcap', '-Replaced.pcap').replace('.pcapng', '-Replaced.pcapng')
        if replaced_file in replaced_files:
            replaced_path = os.path.join(subdir_path, replaced_file)
            replaced_ips = get_all_ips_in_file(replaced_path)
            print(f"\n替换文件：{replaced_file}")
            print(f"替换文件中的 IP 数量：{len(replaced_ips)}")
            print("替换文件中的 IP 示例：")
            for ip in sorted(replaced_ips)[:5]:  # 只显示前 5 个 IP
                print(f"  - {ip}")

    print(f"\n目录中所有原始文件的 IP 数量：{len(all_original_ips)}")
    print("所有原始文件中的 IP 示例：")
    for ip in sorted(all_original_ips)[:5]:  # 只显示前 5 个 IP
        print(f"  - {ip}")

    # 验证日志文件
    log_path = os.path.join(subdir_path, "replacement.log")
    if os.path.exists(log_path):
        if verify_replacement_log(log_path, all_original_ips):
            print("\n日志验证通过")
        else:
            errors.append("日志验证失败")
    else:
        errors.append("未找到 replacement.log 文件")

    # 检查 IP 替换一致性
    consistency_errors = verify_ip_consistency(replaced_files, subdir_path)
    errors.extend(consistency_errors)

    return errors

def main():
    """主函数"""
    test_dir = get_test_dir()
    if not os.path.exists(test_dir):
        print(f"测试目录不存在：{test_dir}")
        return

    all_errors = []
    for subdir in os.listdir(test_dir):
        subdir_path = os.path.join(test_dir, subdir)
        if os.path.isdir(subdir_path):
            errors = test_directory(subdir_path)
            all_errors.extend([f"{subdir}: {error}" for error in errors])

    print("\n测试总结：")
    if all_errors:
        print("发现以下问题：")
        for error in all_errors:
            print(f"- {error}")
    else:
        print("所有测试通过，未发现问题")

if __name__ == "__main__":
    main() 