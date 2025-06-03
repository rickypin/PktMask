#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask 测试程序
用于测试 IP 替换功能
"""

import sys
import os
import shutil
import pytest
import json
import ipaddress
from pathlib import Path
from typing import Dict, Set, List, Tuple
from scapy.all import PcapReader, PcapNgReader, IP, IPv6

def get_test_dir() -> str:
    """Get test directory path (now always from tests/data/)"""
    return os.path.join(os.path.dirname(__file__), 'data')

@pytest.fixture
def test_data_dir(tmp_path):
    """Copy tests/data/ to a temp dir for isolated testing"""
    data_src = os.path.join(os.path.dirname(__file__), 'data')
    data_dst = tmp_path / "data"
    shutil.copytree(data_src, data_dst)
    return data_dst

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
        print(f"Error reading file {file_path}: {str(e)}")
    return ips

def get_ip_mapping_from_files(original_file: str, replaced_file: str) -> Dict[str, str]:
    """从原始文件和替换文件中获取 IP 映射关系"""
    mapping = {}
    log_path = os.path.join(os.path.dirname(original_file), "replacement.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
                mapping = log_data.get('total_mapping', {})
                return mapping
        except Exception as e:
            print(f"Error reading log file: {str(e)}")
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
            print(f"Warning: Number of IPs in file {os.path.basename(original_file)} and {os.path.basename(replaced_file)} are different")
            print(f"Original file IP count: {len(orig_ips)}")
            print(f"Replaced file IP count: {len(replaced_ips)}")
    except Exception as e:
        print(f"Error getting IP mapping: {str(e)}")
    return mapping

def verify_replacement_log(log_path: str, original_ips: Set[str]) -> Tuple[bool, str]:
    """验证替换日志文件"""
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        # 从日志中获取 IP 映射
        mapping = log_data.get('total_mapping', {})
        if not mapping:
            return False, "IP mapping not found in log file"
        
        # 标准化所有 IP 地址
        normalized_mapping = {normalize_ip(k): normalize_ip(v) for k, v in mapping.items()}
        normalized_original_ips = {normalize_ip(ip) for ip in original_ips}
        
        # 检查映射中的 IP 是否都在原始文件中
        for orig_ip in normalized_mapping.keys():
            if orig_ip not in normalized_original_ips:
                return False, f"Log contains IP not in original file: {orig_ip}"
        
        # 检查原始文件中的 IP 是否都有映射
        for orig_ip in normalized_original_ips:
            if orig_ip not in normalized_mapping:
                return False, f"IP in original file not mapped: {orig_ip}"
        
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
                return False, f"Invalid IP mapping: {orig_ip} -> {new_ip}, error: {str(e)}"
        
        return True, "Verification passed"
    except Exception as e:
        return False, f"Verification process error: {str(e)}"

def verify_ip_consistency(replaced_files: List[str], subdir_path: str) -> List[str]:
    """验证 IP 替换的一致性"""
    if len(replaced_files) <= 1:
        print("\nOnly one replaced file in the directory, no need to check IP replacement consistency")
        return []

    errors = []
    # 使用第一个文件作为基准
    base_file = replaced_files[0]
    print(f"\nChecking IP replacement consistency...")
    print(f"Baseline file: {base_file}")
    
    # 获取基准文件的原始文件
    base_original = base_file.replace('-Replaced.pcap', '.pcap').replace('-Replaced.pcapng', '.pcapng')
    base_original_path = os.path.join(subdir_path, base_original)
    base_replaced_path = os.path.join(subdir_path, base_file)
    
    # 获取基准文件的 IP 映射
    base_mapping = get_ip_mapping_from_files(base_original_path, base_replaced_path)
    if not base_mapping:
        errors.append(f"Failed to get IP mapping from baseline file {base_file}")
        return errors

    # 检查其他文件的映射是否一致
    for filename in replaced_files[1:]:
        print(f"\nCurrent file: {filename}")
        # 获取当前文件的原始文件
        current_original = filename.replace('-Replaced.pcap', '.pcap').replace('-Replaced.pcapng', '.pcapng')
        current_original_path = os.path.join(subdir_path, current_original)
        current_replaced_path = os.path.join(subdir_path, filename)
        
        current_mapping = get_ip_mapping_from_files(current_original_path, current_replaced_path)
        if not current_mapping:
            errors.append(f"Failed to get IP mapping from file {filename}")
            continue

        # 检查每个 IP 的映射是否一致
        for ip, new_ip in base_mapping.items():
            if ip in current_mapping:
                if current_mapping[ip] != new_ip:
                    error_msg = (
                        f"Inconsistent mapping for IP {ip}:\n"
                        f"  Baseline file {base_file} maps to: {new_ip}\n"
                        f"  Current file {filename} maps to: {current_mapping[ip]}"
                    )
                    errors.append(error_msg)
                    print(error_msg)

    return errors

def _test_directory(subdir_path: str) -> None:
    print(f"\n=== Testing subdirectory: {os.path.basename(subdir_path)} ===")
    original_files = []
    replaced_files = []
    for filename in os.listdir(subdir_path):
        if filename.lower().endswith(('.pcap', '.pcapng')):
            if filename.endswith('-Replaced.pcap') or filename.endswith('-Replaced.pcapng'):
                replaced_files.append(filename)
            else:
                original_files.append(filename)
    print(f"  Original files: {original_files}")
    print(f"  Replaced files: {replaced_files}")

    all_original_ips = set()
    for filename in original_files:
        file_path = os.path.join(subdir_path, filename)
        ips = get_all_ips_in_file(file_path)
        print(f"    {filename}: {len(ips)} unique IPs")
        all_original_ips.update(ips)

    log_path = os.path.join(subdir_path, "replacement.log")
    if os.path.exists(log_path):
        print(f"  Checking replacement.log: {log_path}")
        success, message = verify_replacement_log(log_path, all_original_ips)
        print(f"    Log verification: {'PASS' if success else 'FAIL'} - {message}")
        assert success, message
    else:
        print("  replacement.log file not found")

    consistency_errors = verify_ip_consistency(replaced_files, subdir_path)
    if consistency_errors:
        print("  Consistency check: FAIL")
        for err in consistency_errors:
            print("    " + err)
    else:
        print("  Consistency check: PASS")
    assert not consistency_errors, "\n".join(consistency_errors)

def test_all_subdirs(test_data_dir):
    """Test all subdirectories in the isolated test data dir"""
    all_errors = []
    total = 0
    for subdir in os.listdir(test_data_dir):
        subdir_path = os.path.join(test_data_dir, subdir)
        if os.path.isdir(subdir_path):
            total += 1
            try:
                _test_directory(str(subdir_path))
            except AssertionError as e:
                all_errors.append(f"{subdir}: {e}")
    print(f"\nTested {total} subdirectories.")
    if all_errors:
        print("Found the following issues:")
        for error in all_errors:
            print(f"- {error}")
    else:
        print("All tests passed, no issues found")

def main():
    """主函数"""
    test_dir = get_test_dir()
    if not os.path.exists(test_dir):
        print(f"测试目录不存在：{test_dir}")
        return

    test_all_subdirs(test_dir)

if __name__ == "__main__":
    main() 