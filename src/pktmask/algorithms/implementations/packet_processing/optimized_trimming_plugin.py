#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
优化版数据包裁切算法插件
实现了在Phase 5.3.3中开发的高性能TLS数据包裁切算法
"""

import time
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

import scapy.all as scapy
from scapy.utils import rdpcap, wrpcap

from ...interfaces.packet_processing_interface import (
    PacketProcessingInterface, 
    PacketProcessingConfig, 
    PacketProcessingResult,
    PacketProcessingStrategy
)
from ...interfaces.algorithm_interface import AlgorithmInfo, AlgorithmType, AlgorithmStatus
from ....infrastructure.logging import get_logger
from ....common.exceptions import ProcessingError
from ....infrastructure.error_handling import handle_errors


class OptimizedTrimmingPlugin(PacketProcessingInterface):
    """
    优化版数据包裁切算法插件
    基于Phase 5.3.3的性能优化成果
    """
    
    def __init__(self):
        self._logger = get_logger('algorithm.packet_processing.optimized')
        self._config: Optional[PacketProcessingConfig] = None
        self._status = AlgorithmStatus.IDLE
        
        # 性能优化缓存
        self._tcp_layer_cache: Dict[int, Tuple[bool, Optional[object]]] = {}
        self._session_cache: Dict[str, str] = {}
        self._tls_ranges_cache: Dict[str, List[Tuple[int, int]]] = {}
        
        # 统计信息
        self._processed_count = 0
        self._trimmed_count = 0
        self._preserved_count = 0
        self._cache_hits = 0
        self._bytes_before = 0
        self._bytes_after = 0
        
        # 性能参数
        self._batch_size = 1000
        self._enable_caching = True
        
        self._logger.info("优化版数据包裁切算法插件初始化完成")
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        """获取算法信息"""
        return AlgorithmInfo(
            name="optimized_trimming",
            display_name="优化版智能裁切",
            description="基于TLS信令检测的高性能数据包载荷裁切算法，支持TCP层缓存和会话缓存优化",
            version="2.0.0",
            algorithm_type=AlgorithmType.PACKET_PROCESSING,
            author="PktMask Team",
            requires_config=True,
            config_schema={
                "trim_payload": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否裁切载荷"
                },
                "preserve_tls_handshake": {
                    "type": "boolean", 
                    "default": True,
                    "description": "保留TLS握手"
                },
                "preserve_certificates": {
                    "type": "boolean",
                    "default": True,
                    "description": "保留证书"
                },
                "batch_size": {
                    "type": "integer",
                    "default": 1000,
                    "minimum": 100,
                    "maximum": 10000,
                    "description": "批处理大小"
                },
                "enable_caching": {
                    "type": "boolean",
                    "default": True,
                    "description": "启用缓存机制"
                }
            }
        )
    
    def initialize(self, config: PacketProcessingConfig) -> bool:
        """初始化算法"""
        try:
            self._config = config
            self._status = AlgorithmStatus.READY
            
            # 应用配置
            self._batch_size = getattr(config, 'batch_size', 1000)
            self._enable_caching = getattr(config, 'enable_caching', True)
            
            # 重置统计信息
            self._reset_statistics()
            
            self._logger.info(f"裁切算法初始化完成，批处理大小: {self._batch_size}, 缓存: {self._enable_caching}")
            return True
            
        except Exception as e:
            self._logger.error(f"裁切算法初始化失败: {e}")
            self._status = AlgorithmStatus.ERROR
            return False
    
    @handle_errors(auto_recover=True, reraise_on_failure=False)
    def process_packet(self, packet) -> Tuple[object, bool]:
        """处理单个数据包"""
        try:
            original_size = len(bytes(packet))
            self._bytes_before += original_size
            
            # 检查是否需要处理
            if not self._should_process_packet(packet):
                self._preserved_count += 1
                self._bytes_after += original_size
                return packet, False
            
            # 裁切处理
            processed_packet = self._trim_packet_intelligent(packet)
            processed_size = len(bytes(processed_packet))
            
            self._processed_count += 1
            self._trimmed_count += 1
            self._bytes_after += processed_size
            
            return processed_packet, True
            
        except Exception as e:
            self._logger.warning(f"处理数据包失败: {e}")
            self._bytes_after += len(bytes(packet))
            return packet, False
    
    @handle_errors(auto_recover=True, reraise_on_failure=False)
    def batch_process_packets(self, packets: List) -> List[Tuple[object, bool]]:
        """批量处理数据包"""
        if not packets:
            return []
        
        self._status = AlgorithmStatus.RUNNING
        results = []
        
        try:
            # 分离TCP和非TCP包，优化缓存局部性
            tcp_packets = []
            non_tcp_packets = []
            
            for i, packet in enumerate(packets):
                has_tcp, tcp_layer = self._get_tcp_layer_cached(packet)
                if has_tcp:
                    tcp_packets.append((i, packet, tcp_layer))
                else:
                    non_tcp_packets.append((i, packet))
            
            # 处理结果数组
            packet_results = [None] * len(packets)
            
            # 批量处理TCP包
            for i, packet, tcp_layer in tcp_packets:
                result, modified = self.process_packet(packet)
                packet_results[i] = (result, modified)
            
            # 批量处理非TCP包
            for i, packet in non_tcp_packets:
                result, modified = self.process_packet(packet)
                packet_results[i] = (result, modified)
            
            self._status = AlgorithmStatus.READY
            return packet_results
            
        except Exception as e:
            self._logger.error(f"批量处理失败: {e}")
            self._status = AlgorithmStatus.ERROR
            # 返回原始数据包
            return [(packet, False) for packet in packets]
    
    def should_preserve_packet(self, packet) -> bool:
        """判断是否应该保留数据包"""
        try:
            # TLS握手包始终保留
            if self._is_tls_handshake_packet(packet):
                return True
            
            # 证书包保留
            if self._config and self._config.preserve_certificates:
                if self._is_certificate_packet(packet):
                    return True
            
            # 小包保留
            if len(bytes(packet)) < 100:
                return True
                
            return False
            
        except Exception:
            return True  # 出错时保守处理
    
    def trim_packet_payload(self, packet, target_size: Optional[int] = None) -> object:
        """裁切数据包载荷"""
        return self._trim_packet_intelligent(packet, target_size)
    
    def _do_process_file(self, input_path: str, output_path: str) -> PacketProcessingResult:
        """处理单个文件"""
        input_file = Path(input_path)
        output_file = Path(output_path)
        
        if not input_file.exists():
            raise ProcessingError(f"输入文件不存在: {input_file}")
        
        start_time = time.time()
        
        try:
            # 读取数据包
            self._logger.info(f"读取文件: {input_file}")
            packets = rdpcap(str(input_file))
            original_count = len(packets)
            
            # 批量处理
            processed_packets = []
            modified_count = 0
            
            for i in range(0, len(packets), self._batch_size):
                batch = packets[i:i + self._batch_size]
                batch_results = self.batch_process_packets(batch)
                
                for packet, modified in batch_results:
                    processed_packets.append(packet)
                    if modified:
                        modified_count += 1
            
            # 写入结果
            self._logger.info(f"写入处理结果到: {output_file}")
            wrpcap(str(output_file), processed_packets)
            
            # 创建结果
            processing_time = time.time() - start_time
            file_size = input_file.stat().st_size
            throughput = file_size / processing_time / (1024 * 1024)  # MB/s
            
            result = PacketProcessingResult(
                success=True,
                original_packets=original_count,
                processed_packets=len(processed_packets),
                trimmed_packets=modified_count,
                preserved_packets=original_count - modified_count,
                bytes_before=self._bytes_before,
                bytes_after=self._bytes_after,
                processing_time=processing_time
            )
            
            result.calculate_compression_ratio()
            
            self._logger.info(
                f"文件处理完成: {input_file.name} -> {output_file.name}, "
                f"原始 {original_count} 包，处理 {len(processed_packets)} 包，"
                f"裁切 {modified_count} 包，压缩率 {result.compression_ratio:.1f}%，"
                f"吞吐量 {throughput:.2f} MB/s，缓存命中 {self._cache_hits} 次"
            )
            
            return result
            
        except Exception as e:
            self._logger.error(f"文件处理失败: {e}")
            raise ProcessingError(f"文件处理失败: {e}")
    
    def _should_process_packet(self, packet) -> bool:
        """判断是否需要处理数据包"""
        if not self._config or not self._config.trim_payload:
            return False
        
        # 保留的包不处理
        if self.should_preserve_packet(packet):
            return False
        
        # 有TCP载荷的包才处理
        has_tcp, tcp_layer = self._get_tcp_layer_cached(packet)
        if not has_tcp or not hasattr(tcp_layer, 'load'):
            return False
        
        return True
    
    def _trim_packet_intelligent(self, packet, target_size: Optional[int] = None) -> object:
        """智能裁切数据包"""
        try:
            has_tcp, tcp_layer = self._get_tcp_layer_cached(packet)
            if not has_tcp or not hasattr(tcp_layer, 'load'):
                return packet
            
            # 获取TLS信令范围
            session_key = self._get_session_key_cached(tcp_layer)
            tls_ranges = self._get_tls_ranges_cached(session_key, tcp_layer.load)
            
            if not tls_ranges:
                # 没有TLS信令，可以安全裁切
                if target_size is None:
                    target_size = 100  # 默认保留100字节
                
                if len(tcp_layer.load) > target_size:
                    # 创建新的TCP层
                    new_tcp = tcp_layer.copy()
                    new_tcp.load = tcp_layer.load[:target_size]
                    
                    # 重新构建包
                    new_packet = packet.copy()
                    new_packet[scapy.TCP] = new_tcp
                    return new_packet
            
            return packet
            
        except Exception as e:
            self._logger.warning(f"智能裁切失败: {e}")
            return packet
    
    def _get_tcp_layer_cached(self, packet) -> Tuple[bool, Optional[object]]:
        """缓存TCP层检查"""
        if not self._enable_caching:
            has_tcp = packet.haslayer(scapy.TCP)
            tcp_layer = packet.getlayer(scapy.TCP) if has_tcp else None
            return has_tcp, tcp_layer
        
        packet_id = id(packet)
        if packet_id in self._tcp_layer_cache:
            self._cache_hits += 1
            return self._tcp_layer_cache[packet_id]
        
        has_tcp = packet.haslayer(scapy.TCP)
        tcp_layer = packet.getlayer(scapy.TCP) if has_tcp else None
        result = (has_tcp, tcp_layer)
        
        self._tcp_layer_cache[packet_id] = result
        return result
    
    def _get_session_key_cached(self, tcp_layer) -> str:
        """缓存会话标识符"""
        if not self._enable_caching:
            return f"{tcp_layer.sport}-{tcp_layer.dport}"
        
        key = f"{tcp_layer.sport}-{tcp_layer.dport}"
        if key in self._session_cache:
            self._cache_hits += 1
            return self._session_cache[key]
        
        self._session_cache[key] = key
        return key
    
    def _get_tls_ranges_cached(self, session_key: str, payload: bytes) -> List[Tuple[int, int]]:
        """缓存TLS范围检测"""
        if not self._enable_caching:
            return self._detect_tls_ranges(payload)
        
        if session_key in self._tls_ranges_cache:
            self._cache_hits += 1
            return self._tls_ranges_cache[session_key]
        
        ranges = self._detect_tls_ranges(payload)
        self._tls_ranges_cache[session_key] = ranges
        return ranges
    
    def _detect_tls_ranges(self, payload: bytes) -> List[Tuple[int, int]]:
        """检测TLS信令范围"""
        ranges = []
        TLS_CONTENT_TYPES = {20, 21, 22}  # Change Cipher Spec, Alert, Handshake
        
        try:
            i = 0
            while i < len(payload) - 5:
                if payload[i] in TLS_CONTENT_TYPES:
                    # 检查TLS版本
                    version = (payload[i+1] << 8) | payload[i+2]
                    if version in {0x0301, 0x0302, 0x0303, 0x0304}:  # TLS 1.0-1.3
                        # 获取长度
                        length = (payload[i+3] << 8) | payload[i+4]
                        if i + 5 + length <= len(payload):
                            ranges.append((i, i + 5 + length))
                            i += 5 + length
                            continue
                i += 1
        except Exception:
            pass
        
        return ranges
    
    def _is_tls_handshake_packet(self, packet) -> bool:
        """检查是否为TLS握手包"""
        try:
            has_tcp, tcp_layer = self._get_tcp_layer_cached(packet)
            if not has_tcp or not hasattr(tcp_layer, 'load'):
                return False
            
            payload = tcp_layer.load
            if len(payload) < 6:
                return False
            
            # 检查TLS握手记录
            return payload[0] == 22 and payload[5] in {1, 2, 11, 12, 13, 14, 15, 16}
            
        except Exception:
            return False
    
    def _is_certificate_packet(self, packet) -> bool:
        """检查是否为证书包"""
        try:
            has_tcp, tcp_layer = self._get_tcp_layer_cached(packet)
            if not has_tcp or not hasattr(tcp_layer, 'load'):
                return False
            
            payload = tcp_layer.load
            if len(payload) < 6:
                return False
            
            # 检查证书消息类型
            return payload[0] == 22 and payload[5] == 11
            
        except Exception:
            return False
    
    def _get_processing_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return {
            "processed_packets": self._processed_count,
            "trimmed_packets": self._trimmed_count,
            "preserved_packets": self._preserved_count,
            "cache_hits": self._cache_hits,
            "bytes_before": self._bytes_before,
            "bytes_after": self._bytes_after,
            "compression_ratio": ((self._bytes_before - self._bytes_after) / max(self._bytes_before, 1)) * 100,
            "cache_efficiency": {
                "tcp_layer_cache_size": len(self._tcp_layer_cache),
                "session_cache_size": len(self._session_cache),
                "tls_ranges_cache_size": len(self._tls_ranges_cache)
            }
        }
    
    def _do_reset_stats(self):
        """重置统计信息"""
        self._processed_count = 0
        self._trimmed_count = 0
        self._preserved_count = 0
        self._cache_hits = 0
        self._bytes_before = 0
        self._bytes_after = 0
        
        if self._enable_caching:
            self._tcp_layer_cache.clear()
            self._session_cache.clear()
            self._tls_ranges_cache.clear()
    
    def _reset_statistics(self):
        """重置统计信息"""
        self._do_reset_stats()
    
    def get_status(self) -> AlgorithmStatus:
        """获取算法状态"""
        return self._status
    
    def cleanup(self):
        """清理资源"""
        self._reset_statistics()
        self._status = AlgorithmStatus.IDLE
        self._logger.info("优化版数据包裁切算法插件清理完成")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        stats = self._get_processing_stats()
        return {
            "cache_hit_rate": (self._cache_hits / max(self._processed_count, 1)) * 100,
            "trimming_rate": (self._trimmed_count / max(self._processed_count, 1)) * 100,
            "compression_efficiency": stats["compression_ratio"],
            "cache_memory_usage": {
                "tcp_cache_entries": len(self._tcp_layer_cache),
                "session_cache_entries": len(self._session_cache),
                "tls_cache_entries": len(self._tls_ranges_cache)
            },
            "optimization_features": [
                "TCP层缓存",
                "会话密钥缓存",
                "TLS范围检测缓存",
                "批处理优化",
                "智能裁切策略"
            ]
        }
    
    # === 实现抽象方法 ===
    
    def _apply_config(self, config: PacketProcessingConfig):
        """应用配置"""
        self._batch_size = getattr(config, 'batch_size', 1000)
        self._enable_caching = getattr(config, 'enable_caching', True)
    
    def _do_initialize(self, config: PacketProcessingConfig) -> bool:
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