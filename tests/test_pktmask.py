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
from scapy.all import PcapReader, PcapNgReader, IP, IPv6, wrpcap, Ether, TCP
from pktmask.utils.file_selector import select_files

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


def make_files(tmpdir: Path, filenames: List[str]):
    """创建空的pcap文件用于测试"""
    for f in tmpdir.glob('*.*'):
        os.remove(f)
    for name in filenames:
        wrpcap(str(tmpdir / name), [Ether()/IP(src="1.1.1.1",dst="2.2.2.2")/TCP()], append=False)

def test_select_files_for_processing_chain_cases(tmp_path):
    """测试文件选择逻辑，特别是链式处理场景"""
    p = Path(tmp_path)
    suffixes = ['-Deduped', '-Replaced']
    
    # 场景1：只有原始文件
    make_files(p, ['a.pcap', 'b.pcapng'])
    files, info = select_files(str(p), '-Deduped', suffixes)
    assert sorted(files) == ['a.pcap', 'b.pcapng']
    assert info == 'Processing raw files.'

    # 场景2：已有Deduped文件，目标是Deduped -> 跳过
    make_files(p, ['a-Deduped.pcap'])
    files, info = select_files(str(p), '-Deduped', suffixes)
    assert files == []
    assert "already exist" in info
    
    # 场景3：已有Deduped文件，目标是Replaced -> 处理Deduped文件
    files, info = select_files(str(p), '-Replaced', suffixes)
    assert files == ['a-Deduped.pcap']
    assert "from a previous step" in info

    # 场景4：同时有raw和Deduped文件，目标是Deduped -> 跳过
    make_files(p, ['a-Deduped.pcap', 'b.pcap'])
    files, info = select_files(str(p), '-Deduped', suffixes)
    assert files == []
    # 目标是Replaced -> 处理Deduped文件
    files, info = select_files(str(p), '-Replaced', suffixes)
    assert files == ['a-Deduped.pcap']

    # 场景5：同时有raw, Deduped, Replaced文件
    make_files(p, ['a.pcap', 'b-Deduped.pcap', 'c-Replaced.pcapng'])
    # 目标是Deduped -> 跳过
    files, info = select_files(str(p), '-Deduped', suffixes)
    assert files == []
    # 目标是Replaced -> 跳过
    files, info = select_files(str(p), '-Replaced', suffixes)
    assert files == []

    # 场景6：只有Replaced文件
    make_files(p, ['a-Replaced.pcap'])
    # 目标是Replaced -> 跳过
    files, info = select_files(str(p), '-Replaced', suffixes)
    assert files == []
    # 目标是Deduped -> 处理Replaced文件（因为它是唯一的输入）
    files, info = select_files(str(p), '-Deduped', suffixes)
    assert files == ['a-Replaced.pcap']

    # 场景7：什么文件都没有
    make_files(p, [])
    # 目标是Deduped
    files, info = select_files(str(p), '-Deduped', suffixes)
    assert files == []

    # 场景8：有更复杂后缀的文件
    make_files(p, ['a-Deduped-Replaced.pcapng'])
    # 目标是Replaced -> 跳过
    files, info = select_files(str(p), '-Replaced', suffixes)
    assert files == []
    # 目标是Deduped -> 跳过
    files, info = select_files(str(p), '-Deduped', suffixes)
    assert files == []


def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 如果有命令行参数，则执行指定函数
        func_name = sys.argv[1]
        if func_name in globals() and callable(globals()[func_name]):
            # 构造临时目录并执行测试
            if 'test' in func_name:
                # pytest fixture, create a temp dir manually
                temp_dir = Path('./temp_test_dir')
                temp_dir.mkdir(exist_ok=True)
                globals()[func_name](temp_dir)
                shutil.rmtree(temp_dir)
            else:
                globals()[func_name]()
    else:
        # 否则，显示帮助信息
        print("Usage: python test_main.py [function_name]")

if __name__ == "__main__":
    main() 