#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
优化版本的智能裁切 TLS Application Data 模块。
基于 trimming.py 原始算法，进行性能优化。
"""

import os
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

from scapy.all import TCP, IP, IPv6, PcapReader, PcapNgReader, wrpcap
from ..core.base_step import ProcessingStep
from ..common.constants import ProcessingConstants
from ..infrastructure.logging import get_logger


class OptimizedIntelligentTrimmingStep(ProcessingStep):
    """
    优化版本的智能裁切处理步骤，用于从pcap文件中裁切TLS应用数据。
    """
    suffix: str = ProcessingConstants.TRIM_PACKET_SUFFIX
    
    def __init__(self):
        super().__init__()
        self._logger = get_logger('optimized_intelligent_trimming')
        
        # 性能优化缓存
        self._tcp_layer_cache = {}  # 缓存TCP层检查结果
        self._session_cache = {}    # 缓存会话ID计算结果
        self._tls_ranges_cache = {} # 缓存TLS范围计算结果
        
        # 预编译正则或常量
        self._tcp_flags_syn_fin_rst = 0x07  # SYN | FIN | RST
    
    @property
    def name(self) -> str:
        return "Optimized Intelligent Trim"

    def _get_tcp_layer_cached(self, packet):
        """缓存版本的TCP层获取"""
        pkt_id = id(packet)
        if pkt_id not in self._tcp_layer_cache:
            has_tcp = packet.haslayer(TCP)
            tcp_layer = packet.getlayer(TCP) if has_tcp else None
            self._tcp_layer_cache[pkt_id] = (has_tcp, tcp_layer)
        return self._tcp_layer_cache[pkt_id]

    def _get_tcp_session_key_cached(self, packet) -> Tuple[Optional[tuple], Optional[str]]:
        """缓存版本的TCP会话密钥获取"""
        pkt_id = id(packet)
        if pkt_id not in self._session_cache:
            has_tcp, tcp_layer = self._get_tcp_layer_cached(packet)
            if not has_tcp:
                self._session_cache[pkt_id] = (None, None)
            else:
                if packet.haslayer(IP):
                    src, dst = packet[IP].src, packet[IP].dst
                elif packet.haslayer(IPv6):
                    src, dst = packet[IPv6].src, packet[IPv6].dst
                else:
                    self._session_cache[pkt_id] = (None, None)
                    return None, None
                
                sport, dport = tcp_layer.sport, tcp_layer.dport
                
                if (src, sport) <= (dst, dport):
                    session_key = (src, sport, dst, dport)
                    direction = "forward"
                else:
                    session_key = (dst, dport, src, sport)
                    direction = "reverse"
                    
                self._session_cache[pkt_id] = (session_key, direction)
        
        return self._session_cache[pkt_id]

    def _find_tls_signaling_ranges_optimized(self, payload: bytes) -> list:
        """优化版本的TLS信令范围查找"""
        payload_id = hash(payload)
        if payload_id not in self._tls_ranges_cache:
            ranges = []
            i = 0
            payload_len = len(payload)
            signaling_types = ProcessingConstants.TLS_SIGNALING_TYPES
            
            while i + 5 <= payload_len:
                record_type = payload[i]
                if record_type in signaling_types:
                    record_length = int.from_bytes(payload[i+3:i+5], byteorder='big')
                    if i + 5 + record_length <= payload_len:
                        ranges.append((i, i + 5 + record_length))
                        i += 5 + record_length
                    else:
                        break
                else:
                    # 跳过非信令记录
                    record_length = int.from_bytes(payload[i+3:i+5], byteorder='big')
                    if i + 5 + record_length <= payload_len:
                        i += 5 + record_length
                    else:
                        break
            
            self._tls_ranges_cache[payload_id] = ranges
        
        return self._tls_ranges_cache[payload_id]

    def _trim_packet_payload_optimized(self, packet):
        """优化版本的数据包裁切"""
        has_tcp, tcp_layer = self._get_tcp_layer_cached(packet)
        if has_tcp and tcp_layer.payload:
            tcp_layer.remove_payload()
            # 批量删除校验和
            if hasattr(tcp_layer, "chksum"): 
                del tcp_layer.chksum
            if packet.haslayer(IP):
                ip_layer = packet.getlayer(IP)
                if hasattr(ip_layer, "chksum"): 
                    del ip_layer.chksum
            elif packet.haslayer(IPv6):
                ipv6_layer = packet.getlayer(IPv6)
                if hasattr(ipv6_layer, "chksum"): 
                    del ipv6_layer.chksum
        return packet

    def _process_pcap_data_optimized(self, packets: List) -> Tuple[List, int, int, List[str]]:
        """
        优化版本的数据包处理算法
        """
        new_packets = []
        total = len(packets)
        trimmed = 0
        error_log = []

        # 使用 defaultdict 优化性能
        sessions = defaultdict(lambda: {
            "packets": [], 
            "forward_segments": [], 
            "reverse_segments": []
        })
        
        # 批处理：分离TCP和非TCP包
        tcp_packets = []
        non_tcp_packets = []
        
        for pkt in packets:
            has_tcp, tcp_layer = self._get_tcp_layer_cached(pkt)
            if has_tcp:
                tcp_packets.append((pkt, tcp_layer))
            else:
                non_tcp_packets.append(pkt)
        
        # 批量处理TCP包的会话构建
        for pkt, tcp_layer in tcp_packets:
            session_id, direction = self._get_tcp_session_key_cached(pkt)
            if session_id:
                session = sessions[session_id]
                session["packets"].append(pkt)
                
                if tcp_layer.payload:
                    payload = bytes(tcp_layer.payload)
                    segments = session[f"{direction}_segments"]
                    segments.append((tcp_layer.seq, payload))

        # 批量处理会话流重组
        for sess_id, session_data in sessions.items():
            for direction in ["forward", "reverse"]:
                segments = session_data[f"{direction}_segments"]
                if segments:
                    # 一次性排序
                    segments.sort(key=lambda x: x[0])
                    session_data[f"{direction}_base"] = segments[0][0]
                    
                    # 高效流拼接
                    stream = b"".join(seg for _, seg in segments)
                    session_data[f"{direction}_stream"] = stream
                    session_data[f"{direction}_tls_ranges"] = self._find_tls_signaling_ranges_optimized(stream)
                else:
                    session_data[f"{direction}_base"] = None
                    session_data[f"{direction}_tls_ranges"] = []

        # 批量处理裁切决策
        for pkt in packets:
            do_trim = False
            has_tcp, tcp_layer = self._get_tcp_layer_cached(pkt)
            
            if has_tcp:
                flags = tcp_layer.flags
                # 使用位操作优化标志检查
                if flags & self._tcp_flags_syn_fin_rst:
                    new_packets.append(pkt)
                    continue
                
                if tcp_layer.payload:
                    session_id, direction = self._get_tcp_session_key_cached(pkt)
                    if session_id and session_id in sessions:
                        session = sessions[session_id]
                        base_seq = session.get(f"{direction}_base")
                        tls_ranges = session.get(f"{direction}_tls_ranges", [])
                        
                        if base_seq is not None:
                            offset = tcp_layer.seq - base_seq
                            payload_len = len(bytes(tcp_layer.payload))
                            
                            # 优化范围交集检查
                            intersects = False
                            for rstart, rend in tls_ranges:
                                if offset < rend and (offset + payload_len) > rstart:
                                    intersects = True
                                    break
                            
                            if not intersects:
                                do_trim = True

            if do_trim:
                trimmed += 1
                new_packets.append(self._trim_packet_payload_optimized(pkt))
            else:
                new_packets.append(pkt)

        return new_packets, total, trimmed, error_log

    def process_file(self, input_path: str, output_path: str) -> Optional[Dict]:
        """处理单个pcap文件，执行智能TLS裁切。"""
        import time
        from ..infrastructure.logging import log_performance
        
        start_time = time.time()
        
        # 清理缓存以避免内存泄漏
        self._tcp_layer_cache.clear()
        self._session_cache.clear()
        self._tls_ranges_cache.clear()
        
        self._logger.debug(f"开始优化智能裁切: {input_path}")
        ext = os.path.splitext(input_path)[1].lower()
        reader_cls = PcapNgReader if ext == ".pcapng" else PcapReader
        
        with reader_cls(input_path) as reader:
            all_packets = reader.read_all()
            
        processed_packets, total_count, trimmed_count, error_log = self._process_pcap_data_optimized(all_packets)
        
        # 确保输出文件的目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        wrpcap(output_path, processed_packets, append=False)
        
        trim_rate = (trimmed_count / total_count * ProcessingConstants.PERCENTAGE_MULTIPLIER) if total_count > 0 else 0
        
        # 记录性能指标 
        end_time = time.time()
        duration = end_time - start_time
        
        # 计算缓存命中率
        cache_hits = sum(1 for _ in self._tcp_layer_cache) + sum(1 for _ in self._session_cache) + sum(1 for _ in self._tls_ranges_cache)
        
        log_performance('optimized_trimming_process_file', duration, 'trimming.performance',
                       total_packets=total_count, trimmed_packets=trimmed_count,
                       trim_rate=trim_rate, cache_hits=cache_hits)
        
        self._logger.info(f"优化智能裁切完成: {input_path} -> {output_path}, 裁切包数: {trimmed_count}/{total_count} ({trim_rate:.1f}%), 缓存命中: {cache_hits}, 耗时={duration:.2f}秒")
        
        summary = {
            'subdir': os.path.basename(os.path.dirname(input_path)),
            'input_filename': os.path.basename(input_path),
            'output_filename': os.path.basename(output_path),
            'total_packets': total_count,
            'trimmed_packets': trimmed_count,
            'trim_rate': trim_rate,
            'cache_hits': cache_hits,
        }
        return summary 