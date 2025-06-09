#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
优化版数据包去重算法插件
实现了在Phase 5.3.3中开发的高性能去重算法
"""

import hashlib
import time
from typing import Dict, List, Any, Optional, Iterator
from pathlib import Path

import scapy.all as scapy
from scapy.utils import rdpcap, wrpcap

from ...interfaces.deduplication_interface import (
    DeduplicationInterface, 
    DeduplicationConfig, 
    PacketSignature,
    DeduplicationResult,
    DeduplicationStats
)
from ...interfaces.algorithm_interface import AlgorithmInfo, AlgorithmType, AlgorithmStatus
from ....infrastructure.logging import get_logger
from ....common.exceptions import ProcessingError
from ....infrastructure.error_handling import handle_errors


class OptimizedDeduplicationPlugin(DeduplicationInterface):
    """
    优化版数据包去重算法插件
    基于Phase 5.3.3的性能优化成果
    """
    
    def __init__(self):
        self._logger = get_logger('algorithm.deduplication.optimized')
        self._config: Optional[DeduplicationConfig] = None
        self._status = AlgorithmStatus.IDLE
        
        # 性能优化缓存
        self._packet_hashes: Dict[str, bool] = {}
        self._batch_size = 1000
        self._processed_count = 0
        self._duplicate_count = 0
        self._cache_hits = 0
        
        self._logger.info("优化版去重算法插件初始化完成")
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        """获取算法信息"""
        return AlgorithmInfo(
            name="optimized_deduplication",
            display_name="优化版数据包去重",
            description="基于MD5哈希的高性能数据包去重算法，支持智能哈希和批处理优化",
            version="2.0.0",
            algorithm_type=AlgorithmType.DEDUPLICATION,
            author="PktMask Team",
            requires_config=True,
            config_schema={
                "batch_size": {
                    "type": "integer",
                    "default": 1000,
                    "minimum": 100,
                    "maximum": 10000,
                    "description": "批处理大小"
                },
                "large_packet_threshold": {
                    "type": "integer", 
                    "default": 100,
                    "minimum": 50,
                    "maximum": 1000,
                    "description": "大包阈值（字节）"
                },
                "enable_detailed_logging": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否启用详细日志"
                }
            }
        )
    
    def initialize(self, config: DeduplicationConfig) -> bool:
        """初始化算法"""
        try:
            self._config = config
            self._status = AlgorithmStatus.READY
            
            # 应用配置
            self._batch_size = getattr(config, 'batch_size', 1000)
            self._large_packet_threshold = getattr(config, 'large_packet_threshold', 100)
            self._enable_detailed_logging = getattr(config, 'enable_detailed_logging', False)
            
            # 重置统计信息
            self._reset_statistics()
            
            self._logger.info(f"去重算法初始化完成，批处理大小: {self._batch_size}")
            return True
            
        except Exception as e:
            self._logger.error(f"去重算法初始化失败: {e}")
            self._status = AlgorithmStatus.ERROR
            return False
    
    @handle_errors(auto_recover=True, reraise_on_failure=False)
    def deduplicate_packets(self, packets: List[scapy.Packet]) -> List[scapy.Packet]:
        """去重数据包列表"""
        if not packets:
            return []
        
        self._status = AlgorithmStatus.RUNNING
        start_time = time.time()
        
        try:
            unique_packets = []
            
            # 批处理
            for i in range(0, len(packets), self._batch_size):
                batch = packets[i:i + self._batch_size]
                batch_unique = self._process_batch(batch)
                unique_packets.extend(batch_unique)
                
                if self._enable_detailed_logging:
                    self._logger.debug(f"批次 {i//self._batch_size + 1}: 处理 {len(batch)} 包，保留 {len(batch_unique)} 包")
            
            # 统计信息
            processing_time = time.time() - start_time
            self._processed_count += len(packets)
            original_count = len(packets)
            unique_count = len(unique_packets)
            self._duplicate_count += (original_count - unique_count)
            
            self._logger.info(
                f"去重完成: 原始 {original_count} 包，去重后 {unique_count} 包，"
                f"去除重复 {original_count - unique_count} 包，"
                f"缓存命中 {self._cache_hits} 次，"
                f"耗时 {processing_time:.2f} 秒"
            )
            
            self._status = AlgorithmStatus.READY
            return unique_packets
            
        except Exception as e:
            self._logger.error(f"去重处理失败: {e}")
            self._status = AlgorithmStatus.ERROR
            raise ProcessingError(f"去重处理失败: {e}")
    
    @handle_errors(auto_recover=True, reraise_on_failure=False)
    def deduplicate_file(self, input_file: Path, output_file: Path) -> bool:
        """去重PCAP文件"""
        if not input_file.exists():
            raise ProcessingError(f"输入文件不存在: {input_file}")
        
        self._status = AlgorithmStatus.RUNNING
        start_time = time.time()
        
        try:
            # 读取数据包
            self._logger.info(f"读取文件: {input_file}")
            packets = rdpcap(str(input_file))
            original_count = len(packets)
            
            # 去重处理
            unique_packets = self.deduplicate_packets(packets)
            unique_count = len(unique_packets)
            
            # 写入结果
            self._logger.info(f"写入去重结果到: {output_file}")
            wrpcap(str(output_file), unique_packets)
            
            # 统计信息
            processing_time = time.time() - start_time
            file_size = input_file.stat().st_size
            throughput = file_size / processing_time / (1024 * 1024)  # MB/s
            
            self._logger.info(
                f"文件去重完成: {input_file.name} -> {output_file.name}, "
                f"原始 {original_count} 包，去重后 {unique_count} 包，"
                f"吞吐量 {throughput:.2f} MB/s，"
                f"总耗时 {processing_time:.2f} 秒"
            )
            
            self._status = AlgorithmStatus.READY
            return True
            
        except Exception as e:
            self._logger.error(f"文件去重失败: {e}")
            self._status = AlgorithmStatus.ERROR
            raise ProcessingError(f"文件去重失败: {e}")
    
    def _process_batch(self, batch: List[scapy.Packet]) -> List[scapy.Packet]:
        """处理数据包批次"""
        unique_packets = []
        
        for packet in batch:
            packet_hash = self._compute_packet_hash(packet)
            
            if packet_hash in self._packet_hashes:
                # 缓存命中，跳过重复包
                self._cache_hits += 1
                continue
            
            # 新的唯一包
            self._packet_hashes[packet_hash] = True
            unique_packets.append(packet)
        
        return unique_packets
    
    def _compute_packet_hash(self, packet: scapy.Packet) -> str:
        """
        计算数据包哈希值
        针对大包优化：只哈希前N字节+长度信息
        """
        try:
            raw_bytes = bytes(packet)
            
            if len(raw_bytes) > self._large_packet_threshold:
                # 对于大包，只哈希前N字节 + 长度信息
                hash_input = raw_bytes[:self._large_packet_threshold] + len(raw_bytes).to_bytes(4, 'big')
            else:
                # 小包全量哈希
                hash_input = raw_bytes
            
            return hashlib.md5(hash_input).hexdigest()
            
        except Exception as e:
            self._logger.warning(f"计算包哈希失败: {e}")
            # 回退到简单的字符串哈希
            return hashlib.md5(str(packet).encode()).hexdigest()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "processed_packets": self._processed_count,
            "duplicate_packets": self._duplicate_count,
            "unique_packets": self._processed_count - self._duplicate_count,
            "cache_hits": self._cache_hits,
            "deduplication_rate": (self._duplicate_count / max(self._processed_count, 1)) * 100,
            "cache_efficiency": len(self._packet_hashes),
            "batch_size": self._batch_size,
            "large_packet_threshold": self._large_packet_threshold
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self._reset_statistics()
    
    def _reset_statistics(self):
        """内部重置统计信息"""
        self._processed_count = 0
        self._duplicate_count = 0
        self._cache_hits = 0
        self._packet_hashes.clear()
    
    def get_status(self) -> AlgorithmStatus:
        """获取算法状态"""
        return self._status
    
    def cleanup(self):
        """清理资源"""
        self._reset_statistics()
        self._status = AlgorithmStatus.IDLE
        self._logger.info("优化版去重算法插件清理完成")
    
    def estimate_memory_usage(self, packet_count: int) -> int:
        """估算内存使用量（字节）"""
        # 每个哈希约32字节 + Python对象开销
        hash_memory = packet_count * 50
        # 批处理缓存
        batch_memory = self._batch_size * 1500  # 平均包大小估算
        return hash_memory + batch_memory
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        stats = self.get_statistics()
        return {
            "cache_hit_rate": (self._cache_hits / max(self._processed_count, 1)) * 100,
            "deduplication_efficiency": stats["deduplication_rate"],
            "memory_efficiency": len(self._packet_hashes),
            "batch_processing_enabled": True,
            "optimization_features": [
                "MD5快速哈希",
                "智能大包处理", 
                "批处理优化",
                "缓存机制"
            ]
        }
    
    # === 实现抽象方法 ===
    
    def compute_packet_signature(self, packet) -> PacketSignature:
        """计算数据包签名"""
        try:
            hash_value = self._compute_packet_hash(packet)
            packet_size = len(bytes(packet))
            protocol_info = packet.sprintf("%IP.proto%") if hasattr(packet, 'IP') else "unknown"
            
            return PacketSignature(
                hash_value=hash_value,
                packet_size=packet_size,
                protocol_info=protocol_info
            )
        except Exception as e:
            self._logger.warning(f"计算包签名失败: {e}")
            return PacketSignature(
                hash_value="error",
                packet_size=0,
                protocol_info="error"
            )
    
    def is_duplicate(self, signature: PacketSignature) -> bool:
        """检查是否为重复包"""
        return signature.hash_value in self._packet_hashes
    
    def add_unique_signature(self, signature: PacketSignature):
        """添加唯一包签名到缓存"""
        self._packet_hashes[signature.hash_value] = True
    
    def _do_process_file(self, input_path: str, output_path: str) -> DeduplicationResult:
        """执行具体的文件处理逻辑"""
        result = DeduplicationResult()
        
        try:
            # 调用现有的文件去重逻辑
            success = self.deduplicate_file(Path(input_path), Path(output_path))
            
            # 填充结果
            result.success = success
            stats = self.get_statistics()
            
            result.stats = DeduplicationStats(
                total_packets=stats["processed_packets"],
                unique_packets=stats["unique_packets"],
                duplicate_packets=stats["duplicate_packets"],
                deduplication_rate=stats["deduplication_rate"],
                cache_hits=stats["cache_hits"]
            )
            
            return result
            
        except Exception as e:
            result.success = False
            result.errors = [str(e)]
            return result
    
    def _apply_config(self, config: DeduplicationConfig):
        """应用配置"""
        self._batch_size = getattr(config, 'batch_size', 1000)
        self._large_packet_threshold = getattr(config, 'large_packet_threshold', 100)
        self._enable_detailed_logging = getattr(config, 'enable_detailed_logging', False)
    
    def _do_initialize(self, config: DeduplicationConfig) -> bool:
        """执行初始化逻辑"""
        self._apply_config(config)
        self._reset_statistics()
        return True
    
    def _do_cleanup(self):
        """执行清理逻辑"""
        self._reset_statistics()
    
    def _do_reset_metrics(self):
        """重置性能指标"""
        self._reset_statistics() 