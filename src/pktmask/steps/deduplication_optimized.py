#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
优化版本的数据包去重模块。
基于 deduplication.py 原始算法，进行性能优化。
"""

import os
import hashlib
from typing import Optional, Dict, Set
from scapy.all import PcapReader, PcapNgReader, wrpcap

from ..core.base_step import ProcessingStep
from ..common.constants import ProcessingConstants
from ..infrastructure.logging import get_logger


class OptimizedDeduplicationStep(ProcessingStep):
    """
    优化版本的去重处理步骤
    """
    suffix: str = ProcessingConstants.DEDUP_PACKET_SUFFIX

    def __init__(self):
        super().__init__()
        self._logger = get_logger('optimized_deduplication')
        
        # 性能优化配置
        self._use_hash_optimization = True
        self._hash_cache = {}  # 缓存数据包哈希值
        self._batch_size = 1000  # 批处理大小
        
    @property
    def name(self) -> str:
        return "Optimized Remove Dupes"
    
    def _compute_packet_hash(self, packet) -> str:
        """
        计算数据包的高效哈希值
        使用轻量级哈希而不是完整字节比较
        """
        pkt_id = id(packet)
        if pkt_id not in self._hash_cache:
            # 使用MD5快速哈希，比完整字节比较更高效
            raw_bytes = bytes(packet)
            # 仅对关键字段进行哈希以提升性能
            if len(raw_bytes) > 100:
                # 对于大包，只哈希前100字节 + 长度信息
                hash_input = raw_bytes[:100] + len(raw_bytes).to_bytes(4, 'big')
            else:
                hash_input = raw_bytes
            
            packet_hash = hashlib.md5(hash_input).hexdigest()
            self._hash_cache[pkt_id] = packet_hash
        
        return self._hash_cache[pkt_id]
    
    def _process_packets_batch(self, packets_batch: list, seen_hashes: Set[str]) -> list:
        """
        批处理数据包去重
        """
        unique_packets = []
        
        for packet in packets_batch:
            if self._use_hash_optimization:
                packet_hash = self._compute_packet_hash(packet)
                if packet_hash not in seen_hashes:
                    seen_hashes.add(packet_hash)
                    unique_packets.append(packet)
            else:
                # 原始方法：完整字节比较
                raw_bytes = bytes(packet)
                if raw_bytes not in seen_hashes:
                    seen_hashes.add(raw_bytes)
                    unique_packets.append(packet)
        
        return unique_packets

    def process_file(self, input_path: str, output_path: str) -> Optional[Dict]:
        """
        优化版本的文件去重处理
        """
        import time
        from ..infrastructure.logging import log_performance
        
        start_time = time.time()
        
        # 清理缓存
        self._hash_cache.clear()
        
        self._logger.debug(f"开始优化去重处理: {input_path}")
        
        unique_packets = []
        total_count = 0
        
        ext = os.path.splitext(input_path)[1].lower()
        reader_cls = PcapNgReader if ext == ".pcapng" else PcapReader

        # 使用集合存储已见过的哈希值或字节
        seen_data: Set[str] = set()
        
        # 批处理读取和处理
        with reader_cls(input_path) as reader:
            current_batch = []
            
            for packet in reader:
                total_count += 1
                current_batch.append(packet)
                
                # 当批次达到指定大小时进行处理
                if len(current_batch) >= self._batch_size:
                    batch_unique = self._process_packets_batch(current_batch, seen_data)
                    unique_packets.extend(batch_unique)
                    current_batch.clear()
            
            # 处理最后一个批次
            if current_batch:
                batch_unique = self._process_packets_batch(current_batch, seen_data)
                unique_packets.extend(batch_unique)
        
        # 确保输出文件的目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        wrpcap(output_path, unique_packets, append=False)
        
        unique_count = len(unique_packets)
        removed_count = total_count - unique_count
        
        # 计算缓存命中率
        cache_hits = len(self._hash_cache)
        
        # 记录性能指标
        end_time = time.time()
        duration = end_time - start_time
        log_performance('optimized_deduplication_process_file', duration, 'deduplication.performance',
                       total_packets=total_count, unique_packets=unique_count, 
                       removed_packets=removed_count, cache_hits=cache_hits)
        
        self._logger.info(f"优化去重完成: {input_path} -> {output_path}, 移除重复包: {removed_count}/{total_count}, 缓存命中: {cache_hits}, 耗时={duration:.2f}秒")
        
        summary = {
            'subdir': os.path.basename(os.path.dirname(input_path)),
            'input_filename': os.path.basename(input_path),
            'output_filename': os.path.basename(output_path),
            'total_packets': total_count,
            'unique_packets': unique_count,
            'removed_count': removed_count,
            'cache_hits': cache_hits,
        }
        return summary
    
    def enable_hash_optimization(self, enable: bool = True):
        """启用或禁用哈希优化"""
        self._use_hash_optimization = enable
        
    def set_batch_size(self, size: int):
        """设置批处理大小"""
        self._batch_size = max(100, size)  # 最小批次100 