#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
优化的IP匿名化策略实现
相比原版本的性能改进：
1. 缓存IP验证结果
2. 优化字符串操作
3. 减少字典查找次数
4. 使用更高效的数据结构
"""

import os
import ipaddress
from typing import Dict, List, Tuple, Set
from collections import defaultdict
from scapy.all import PcapReader, PcapNgReader, IP, IPv6

from pktmask.infrastructure.logging import get_logger
from pktmask.core.strategy import (
    AnonymizationStrategy, ip_sort_key, 
    _generate_new_ipv4_address_hierarchical, 
    _generate_new_ipv6_address_hierarchical
)


class OptimizedHierarchicalAnonymizationStrategy(AnonymizationStrategy):
    """优化的分层IP匿名化策略"""
    
    def __init__(self):
        self._ip_map: Dict[str, str] = {}
        # IP验证缓存
        self._ipv4_cache: Set[str] = set()
        self._ipv6_cache: Set[str] = set()
        self._invalid_ip_cache: Set[str] = set()
    
    def reset(self):
        """重置策略状态"""
        self._ip_map.clear()
        self._ipv4_cache.clear()
        self._ipv6_cache.clear()
        self._invalid_ip_cache.clear()
    
    def get_ip_map(self) -> Dict[str, str]:
        """获取IP映射表"""
        return self._ip_map
    
    def _is_valid_ipv4_cached(self, ip_str: str) -> bool:
        """缓存式IPv4验证"""
        if ip_str in self._ipv4_cache:
            return True
        if ip_str in self._invalid_ip_cache:
            return False
        
        try:
            ipaddress.IPv4Address(ip_str)
            self._ipv4_cache.add(ip_str)
            return True
        except Exception:
            self._invalid_ip_cache.add(ip_str)
            return False
    
    def _is_valid_ipv6_cached(self, ip_str: str) -> bool:
        """缓存式IPv6验证"""
        if ip_str in self._ipv6_cache:
            return True
        if ip_str in self._invalid_ip_cache:
            return False
        
        try:
            ipaddress.IPv6Address(ip_str)
            self._ipv6_cache.add(ip_str)
            return True
        except Exception:
            self._invalid_ip_cache.add(ip_str)
            return False
    
    def _prescan_addresses_optimized(self, files_to_process: List[str], subdir_path: str, error_log: List[str]) -> Tuple:
        """
        优化版本：更高效的IP地址频率统计
        """
        import time
        from pktmask.infrastructure.logging import log_performance
        
        start_time = time.time()
        
        # 使用defaultdict避免get()操作
        freq_ipv4_1 = defaultdict(int)
        freq_ipv4_2 = defaultdict(int)
        freq_ipv4_3 = defaultdict(int)
        
        freq_ipv6_1 = defaultdict(int)
        freq_ipv6_2 = defaultdict(int)
        freq_ipv6_3 = defaultdict(int)
        freq_ipv6_4 = defaultdict(int)
        freq_ipv6_5 = defaultdict(int)
        freq_ipv6_6 = defaultdict(int)
        freq_ipv6_7 = defaultdict(int)
        
        unique_ips = set()
        
        def process_ipv4_address_optimized(ip_str: str):
            """优化的IPv4地址处理"""
            if not self._is_valid_ipv4_cached(ip_str):
                return
                
            unique_ips.add(ip_str)
            
            # 预分割，避免重复split操作
            parts = ip_str.split('.')
            if len(parts) != 4:
                return
                
            # 批量构建段标识符，减少字符串操作
            seg_1 = parts[0]
            seg_2 = f"{parts[0]}.{parts[1]}"
            seg_3 = f"{parts[0]}.{parts[1]}.{parts[2]}"
            
            # 直接递增，利用defaultdict的特性
            freq_ipv4_1[seg_1] += 1
            freq_ipv4_2[seg_2] += 1
            freq_ipv4_3[seg_3] += 1

        def process_ipv6_address_optimized(ip_str: str):
            """优化的IPv6地址处理"""
            if not self._is_valid_ipv6_cached(ip_str):
                return
                
            unique_ips.add(ip_str)
            
            try:
                ip_obj = ipaddress.IPv6Address(ip_str)
                parts = ip_obj.exploded.split(':')
                if len(parts) != 8:
                    return
                    
                # 批量构建前缀，减少重复的join操作
                prefixes = [
                    parts[0],
                    f"{parts[0]}:{parts[1]}",
                    f"{parts[0]}:{parts[1]}:{parts[2]}",
                    f"{parts[0]}:{parts[1]}:{parts[2]}:{parts[3]}",
                    f"{parts[0]}:{parts[1]}:{parts[2]}:{parts[3]}:{parts[4]}",
                    f"{parts[0]}:{parts[1]}:{parts[2]}:{parts[3]}:{parts[4]}:{parts[5]}",
                    f"{parts[0]}:{parts[1]}:{parts[2]}:{parts[3]}:{parts[4]}:{parts[5]}:{parts[6]}"
                ]
                
                # 批量更新频率
                freq_ipv6_1[prefixes[0]] += 1
                freq_ipv6_2[prefixes[1]] += 1
                freq_ipv6_3[prefixes[2]] += 1
                freq_ipv6_4[prefixes[3]] += 1
                freq_ipv6_5[prefixes[4]] += 1
                freq_ipv6_6[prefixes[5]] += 1
                freq_ipv6_7[prefixes[6]] += 1
                
            except Exception:
                pass
        
        # 文件处理循环
        total_packets = 0
        for f in files_to_process:
            file_path = os.path.join(subdir_path, f)
            ext = os.path.splitext(f)[1].lower()
            try:
                reader_class = PcapNgReader if ext == ".pcapng" else PcapReader
                with reader_class(file_path) as reader:
                    for packet in reader:
                        total_packets += 1
                        
                        # 优化：减少重复的haslayer调用
                        ip_layer = packet.getlayer(IP) if packet.haslayer(IP) else None
                        ipv6_layer = packet.getlayer(IPv6) if packet.haslayer(IPv6) else None
                        
                        if ip_layer:
                            process_ipv4_address_optimized(ip_layer.src)
                            process_ipv4_address_optimized(ip_layer.dst)
                        
                        if ipv6_layer:
                            process_ipv6_address_optimized(ipv6_layer.src)
                            process_ipv6_address_optimized(ipv6_layer.dst)
                            
            except Exception as e:
                error_log.append(f"Error scanning file {file_path}: {str(e)}")
        
        # 转换defaultdict为普通dict以保持兼容性
        freq_ipv4_dict = (dict(freq_ipv4_1), dict(freq_ipv4_2), dict(freq_ipv4_3))
        freq_ipv6_dict = (dict(freq_ipv6_1), dict(freq_ipv6_2), dict(freq_ipv6_3), 
                         dict(freq_ipv6_4), dict(freq_ipv6_5), dict(freq_ipv6_6), dict(freq_ipv6_7))
        
        # 记录性能指标
        end_time = time.time()
        duration = end_time - start_time
        log_performance('ip_prescan_addresses_optimized', duration, 'ip_anonymization.optimized.performance', 
                       files_processed=len(files_to_process), unique_ips=len(unique_ips), 
                       total_packets=total_packets, cache_hits_ipv4=len(self._ipv4_cache),
                       cache_hits_ipv6=len(self._ipv6_cache))
        
        logger = get_logger('anonymization.strategy.optimized')
        logger.info(f"优化版频率统计完成: 唯一IP总数={len(unique_ips)}, 总包数={total_packets}, 耗时={duration:.3f}秒")
        logger.info(f"缓存效率: IPv4缓存={len(self._ipv4_cache)}, IPv6缓存={len(self._ipv6_cache)}, 无效IP缓存={len(self._invalid_ip_cache)}")
        
        if freq_ipv4_dict[0]:
            top_ipv4_a = dict(sorted(freq_ipv4_dict[0].items(), key=lambda x: x[1], reverse=True)[:5])
            logger.debug(f"IPv4 A段频率统计(前5): {top_ipv4_a}")
        
        return freq_ipv4_dict, freq_ipv6_dict, unique_ips
    
    def create_mapping(self, files_to_process: List[str], subdir_path: str, error_log: List[str]) -> Dict[str, str]:
        """
        优化版创建IP映射
        """
        import time
        from pktmask.infrastructure.logging import log_performance
        
        start_time = time.time()
        
        freqs_ipv4, freqs_ipv6, all_ips = self._prescan_addresses_optimized(files_to_process, subdir_path, error_log)
        
        mapping = {}
        maps_ipv4 = ({}, {}, {})
        maps_ipv6 = ({}, {}, {}, {}, {}, {}, {})
        
        # 用于跟踪已使用的段值，确保唯一性
        used_segments = (set(), set(), set())  # (A段, A.B段, A.B.C段)
        
        # 优化：预处理IP列表，将IPv4和IPv6分开处理以提高效率
        ipv4_ips = []
        ipv6_ips = []
        
        for ip in all_ips:
            if '.' in ip and ip in self._ipv4_cache:
                ipv4_ips.append(ip)
            elif ':' in ip and ip in self._ipv6_cache:
                ipv6_ips.append(ip)
        
        # 分别排序以提高缓存局部性
        ipv4_ips.sort(key=ip_sort_key)
        ipv6_ips.sort(key=ip_sort_key)
        
        logger = get_logger('anonymization.strategy.optimized')
        logger.info(f"开始优化映射生成 - IPv4地址数: {len(ipv4_ips)}, IPv6地址数: {len(ipv6_ips)}")
        
        # 批量处理IPv4地址
        ipv4_errors = 0
        for ip in ipv4_ips:
            try:
                mapping[ip] = _generate_new_ipv4_address_hierarchical(
                    ip, freqs_ipv4[0], freqs_ipv4[1], freqs_ipv4[2], maps_ipv4, used_segments
                )
            except Exception as e:
                ipv4_errors += 1
                error_log.append(f"IPv4 mapping error for {ip}: {str(e)}")
        
        # 批量处理IPv6地址
        ipv6_errors = 0
        for ip in ipv6_ips:
            try:
                mapping[ip] = _generate_new_ipv6_address_hierarchical(
                    ip, freqs_ipv6, maps_ipv6
                )
            except Exception as e:
                ipv6_errors += 1
                error_log.append(f"IPv6 mapping error for {ip}: {str(e)}")
        
        # 记录性能指标
        end_time = time.time()
        duration = end_time - start_time
        log_performance('ip_create_mapping_optimized', duration, 'ip_anonymization.optimized.performance',
                       total_ips=len(mapping), ipv4_ips=len(ipv4_ips), ipv6_ips=len(ipv6_ips),
                       ipv4_errors=ipv4_errors, ipv6_errors=ipv6_errors, files_processed=len(files_to_process))
        
        logger.info(f"优化版IP映射创建完成: {len(mapping)}个映射 (IPv4:{len(ipv4_ips)}, IPv6:{len(ipv6_ips)}), 耗时={duration:.3f}秒")
        if ipv4_errors > 0 or ipv6_errors > 0:
            logger.warning(f"映射错误: IPv4错误数={ipv4_errors}, IPv6错误数={ipv6_errors}")
        
        self._ip_map = mapping
        return mapping
    
    def build_mapping_from_directory(self, all_pcap_files: List[str]):
        """扫描所有文件并构建完整的IP映射"""
        if not all_pcap_files:
            return
        
        subdir_path = os.path.dirname(all_pcap_files[0])
        filenames = [os.path.basename(p) for p in all_pcap_files]
        error_log = []

        logger = get_logger('anonymization.strategy.optimized')
        logger.info(f"开始构建优化版目录级映射 - 文件数: {len(filenames)}")
        self.create_mapping(filenames, subdir_path, error_log)

    def anonymize_packet(self, pkt) -> Tuple[object, bool]:
        """根据已构建的映射匿名化单个数据包"""
        is_anonymized = False
        
        # 处理IPv4
        if pkt.haslayer(IP):
            layer = pkt.getlayer(IP)
            if layer.src in self._ip_map:
                layer.src = self._ip_map[layer.src]
                is_anonymized = True
            if layer.dst in self._ip_map:
                layer.dst = self._ip_map[layer.dst]
                is_anonymized = True
        
        # 处理IPv6
        if pkt.haslayer(IPv6):
            layer = pkt.getlayer(IPv6)
            if layer.src in self._ip_map:
                layer.src = self._ip_map[layer.src]
                is_anonymized = True
            if layer.dst in self._ip_map:
                layer.dst = self._ip_map[layer.dst]
                is_anonymized = True
        
        return pkt, is_anonymized 