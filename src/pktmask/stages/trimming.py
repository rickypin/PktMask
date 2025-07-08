#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
本模块包含智能裁切 TLS Application Data 的核心逻辑。
代码源自一份历史脚本，并经过重构以适配当前的流水线架构。

第三阶段增强：支持多层封装的载荷裁切处理
- 封装内TCP会话识别
- 内层载荷裁切处理
- 保持现有TLS智能裁切算法
"""

import os
from typing import List, Tuple, Dict, Optional

from scapy.all import TCP, IP, IPv6, PcapReader, PcapNgReader, wrpcap
from ..core.base_step import ProcessingStep
from ..common.constants import ProcessingConstants
from ..infrastructure.logging import get_logger

# 导入封装处理组件
from ..core.encapsulation.adapter import ProcessingAdapter
from ..core.encapsulation.types import EncapsulationType

# --- 从原始脚本移植的核心算法函数 ---

# TLS_SIGNALING_TYPES 已移至 common.constants.ProcessingConstants

def find_tls_signaling_ranges(payload: bytes) -> list:
    """在完整的重组流中查找 TLS 信令记录的范围。"""
    ranges = []
    i = 0
    while i + 5 <= len(payload):
        record_type = payload[i]
        record_length = int.from_bytes(payload[i+3:i+5], byteorder='big')
        if i + 5 + record_length > len(payload):
            break
        if record_type in ProcessingConstants.TLS_SIGNALING_TYPES:
            rec_end = i + 5 + record_length
            ranges.append((i, rec_end))
        i += 5 + record_length
    return ranges

def trim_packet_payload(packet):
    """裁切单个报文的 TCP payload 并删除校验和。"""
    if packet.haslayer(TCP):
        tcp_layer = packet.getlayer(TCP)
        if tcp_layer.payload:
            tcp_layer.remove_payload()
            if hasattr(tcp_layer, "chksum"): del tcp_layer.chksum
            if packet.haslayer(IP) and hasattr(packet.getlayer(IP), "chksum"): del packet.getlayer(IP).chksum
            if packet.haslayer(IPv6) and hasattr(packet.getlayer(IPv6), "chksum"): del packet.getlayer(IPv6).chksum
    return packet

def get_tcp_session_key_enhanced(packet, encap_adapter: Optional[ProcessingAdapter] = None) -> Tuple[Optional[tuple], Optional[str]]:
    """
    增强版TCP会话键提取，支持多层封装。
    
    Args:
        packet: 数据包
        encap_adapter: 封装处理适配器
        
    Returns:
        会话键和方向的元组
    """
    # 如果没有提供适配器，则使用原有逻辑
    if not encap_adapter:
        return get_tcp_session_key(packet)
    
    try:
        # 使用封装适配器分析载荷
        payload_analysis = encap_adapter.analyze_packet_for_payload_processing(packet)
        
        # 提取TCP会话信息
        tcp_session = encap_adapter.extract_tcp_session_for_trimming(payload_analysis)
        
        if not tcp_session:
            # 回退到原有逻辑
            return get_tcp_session_key(packet)
        
        # 构建标准化会话键
        src_ip = tcp_session['src_ip']
        dst_ip = tcp_session['dst_ip']
        src_port = tcp_session['src_port']
        dst_port = tcp_session['dst_port']
        
        if (src_ip, src_port) <= (dst_ip, dst_port):
            return (src_ip, src_port, dst_ip, dst_port), "forward"
        else:
            return (dst_ip, dst_port, src_ip, src_port), "reverse"
            
    except Exception as e:
        logger = get_logger('enhanced_trimming')
        logger.warning(f"封装TCP会话提取失败，回退到原有逻辑: {str(e)}")
        return get_tcp_session_key(packet)

def get_tcp_session_key(packet) -> Tuple[Optional[tuple], Optional[str]]:
    """获取 TCP 会话的标准化 key 及报文方向。"""
    if packet.haslayer(TCP):
        if packet.haslayer(IP):
            src, dst = packet[IP].src, packet[IP].dst
        elif packet.haslayer(IPv6):
            src, dst = packet[IPv6].src, packet[IPv6].dst
        else:
            return None, None
        
        sport, dport = packet[TCP].sport, packet[TCP].dport
        
        if (src, sport) <= (dst, dport):
            return (src, sport, dst, dport), "forward"
        else:
            return (dst, dport, src, sport), "reverse"
    return None, None

def _process_pcap_data_enhanced(packets: List, encap_adapter: Optional[ProcessingAdapter] = None) -> Tuple[List, int, int, List[str]]:
    """
    增强版数据处理，支持多层封装的载荷裁切。
    
    Args:
        packets: 数据包列表
        encap_adapter: 封装处理适配器
        
    Returns:
        处理结果元组：(新数据包列表, 总数, 裁切数, 错误日志)
    """
    logger = get_logger('enhanced_trimming')
    
    # 如果没有提供适配器，使用原有逻辑
    if not encap_adapter:
        logger.info("使用原有载荷裁切逻辑")
        return _process_pcap_data(packets)
    
    logger.info("使用增强版载荷裁切逻辑，支持多层封装处理")
    
    new_packets, total, trimmed = [], 0, 0
    error_log = []
    total = len(packets)
    
    # 统计封装信息
    encap_stats = {
        'total_packets': 0,
        'encapsulated_packets': 0,
        'payload_accessible_packets': 0,
        'tcp_packets': 0
    }

    sessions = {}
    
    # 第一遍：收集TCP会话信息（支持封装）
    packet_analysis_cache = {}  # 缓存分析结果，避免重复调用
    
    for pkt in packets:
        encap_stats['total_packets'] += 1
        
        try:
            # 分析封装结构（只调用一次）
            payload_analysis = encap_adapter.analyze_packet_for_payload_processing(pkt)
            packet_analysis_cache[id(pkt)] = payload_analysis  # 缓存结果
            
            if payload_analysis['has_encapsulation']:
                encap_stats['encapsulated_packets'] += 1
            
            if payload_analysis['has_payload']:
                encap_stats['payload_accessible_packets'] += 1
            
            # 提取TCP会话信息（从分析结果中直接提取，不再调用适配器）
            tcp_session = encap_adapter.extract_tcp_session_for_trimming(payload_analysis)
            
            if tcp_session:
                # 构建会话键
                src_ip = tcp_session['src_ip']
                dst_ip = tcp_session['dst_ip']
                src_port = tcp_session['src_port']
                dst_port = tcp_session['dst_port']
                
                if (src_ip, src_port) <= (dst_ip, dst_port):
                    session_id = (src_ip, src_port, dst_ip, dst_port)
                    direction = "forward"
                else:
                    session_id = (dst_ip, dst_port, src_ip, src_port)
                    direction = "reverse"
                    
                encap_stats['tcp_packets'] += 1
                
                if session_id not in sessions:
                    sessions[session_id] = {
                        "packets": [], 
                        "forward_segments": [], 
                        "reverse_segments": [],
                        "encap_context": payload_analysis.get('encap_type', EncapsulationType.PLAIN).value
                    }
                
                sessions[session_id]["packets"].append(pkt)
                
                # 提取TCP载荷（优先使用封装分析结果）
                tcp_payload = tcp_session.get('payload_data')
                seq_num = tcp_session.get('sequence_number', 0)
                
                # 回退到原有TCP载荷提取
                if not tcp_payload and pkt.haslayer(TCP) and pkt[TCP].payload:
                    tcp_payload = bytes(pkt[TCP].payload)
                    seq_num = pkt[TCP].seq
                
                # 添加到对应方向的段列表
                if tcp_payload:
                    segments = sessions[session_id][f"{direction}_segments"]
                    segments.append((seq_num, tcp_payload))
            else:
                # 回退到原有逻辑
                session_id, direction = get_tcp_session_key(pkt)
                if session_id:
                    if session_id not in sessions:
                        sessions[session_id] = {"packets": [], "forward_segments": [], "reverse_segments": []}
                    sessions[session_id]["packets"].append(pkt)
                    if pkt.haslayer(TCP) and pkt[TCP].payload:
                        payload = bytes(pkt[TCP].payload)
                        segments = sessions[session_id][f"{direction}_segments"]
                        segments.append((pkt[TCP].seq, payload))
                
        except Exception as e:
            error_msg = f"封装载荷分析失败: {str(e)}"
            logger.warning(error_msg)
            error_log.append(error_msg)
            
            # 回退到原有逻辑处理此包
            session_id, direction = get_tcp_session_key(pkt)
            if session_id:
                if session_id not in sessions:
                    sessions[session_id] = {"packets": [], "forward_segments": [], "reverse_segments": []}
                sessions[session_id]["packets"].append(pkt)
                if pkt.haslayer(TCP) and pkt[TCP].payload:
                    payload = bytes(pkt[TCP].payload)
                    segments = sessions[session_id][f"{direction}_segments"]
                    segments.append((pkt[TCP].seq, payload))

    # 第二遍：重组TCP流并查找TLS信令范围
    for sess_id, data in sessions.items():
        for direction in ["forward", "reverse"]:
            if data[f"{direction}_segments"]:
                sorted_segs = sorted(data[f"{direction}_segments"], key=lambda x: x[0])
                data[f"{direction}_base"] = sorted_segs[0][0]
                stream = b"".join(seg for _, seg in sorted_segs)
                data[f"{direction}_stream"] = stream
                data[f"{direction}_tls_ranges"] = find_tls_signaling_ranges(stream)
            else:
                data[f"{direction}_base"] = None
                data[f"{direction}_tls_ranges"] = []

    # 第三遍：应用智能裁切逻辑
    for pkt in packets:
            do_trim = False
            
            if pkt.haslayer(TCP):
                tcp_layer = pkt.getlayer(TCP)
                flags = tcp_layer.flags
                
                # 保留控制包（SYN, FIN, RST）
                if flags & 0x02 or flags & 0x01 or flags & 0x04:
                    new_packets.append(pkt)
                    continue
                
                # 处理有载荷的TCP包
                if tcp_layer.payload:
                    try:
                        # 使用增强版会话键（不更新统计，避免重复计数）
                        session_id, direction = get_tcp_session_key_enhanced(pkt, None)  # 传入None避免重复统计
                        if not session_id:
                            session_id, direction = get_tcp_session_key(pkt)
                    except Exception:
                        # 回退到原有逻辑
                        session_id, direction = get_tcp_session_key(pkt)
                    
                    if session_id and session_id in sessions:
                        sess = sessions[session_id]
                        base_seq = sess.get(f"{direction}_base")
                        tls_ranges = sess.get(f"{direction}_tls_ranges", [])
                        
                        if base_seq is not None:
                            offset = tcp_layer.seq - base_seq
                            payload_len = len(bytes(tcp_layer.payload))
                            
                            # 检查是否与TLS信令范围重叠
                            intersects = any(offset < rend and (offset + payload_len) > rstart 
                                           for rstart, rend in tls_ranges)
                            
                            if not intersects:
                                do_trim = True

            # 应用裁切决策
            if do_trim:
                trimmed += 1
                new_packets.append(trim_packet_payload(pkt))
            else:
                new_packets.append(pkt)

    # 记录处理统计
    logger.info(f"封装载荷处理统计: "
               f"总包数={encap_stats['total_packets']}, "
               f"封装包数={encap_stats['encapsulated_packets']}, "
               f"载荷可访问包数={encap_stats['payload_accessible_packets']}, "
               f"TCP包数={encap_stats['tcp_packets']}")
    
    encap_ratio = (encap_stats['encapsulated_packets'] / max(1, encap_stats['total_packets'])) * 100
    logger.info(f"封装比例: {encap_ratio:.1f}%")

    return new_packets, total, trimmed, error_log

def _process_pcap_data(packets: List) -> Tuple[List, int, int, List[str]]:
    """
    处理报文列表，执行智能裁切算法。
    这是从原始脚本移植的核心逻辑。
    """
    new_packets, total, trimmed = [], 0, 0
    error_log = []
    total = len(packets)

    sessions = {}
    for pkt in packets:
        session_id, direction = get_tcp_session_key(pkt)
        if not session_id:
            continue
        if session_id not in sessions:
            sessions[session_id] = {"packets": [], "forward_segments": [], "reverse_segments": []}
        sessions[session_id]["packets"].append(pkt)
        if pkt.haslayer(TCP) and pkt[TCP].payload:
            payload = bytes(pkt[TCP].payload)
            segments = sessions[session_id][f"{direction}_segments"]
            segments.append((pkt[TCP].seq, payload))

    for sess_id, data in sessions.items():
        for direction in ["forward", "reverse"]:
            if data[f"{direction}_segments"]:
                sorted_segs = sorted(data[f"{direction}_segments"], key=lambda x: x[0])
                data[f"{direction}_base"] = sorted_segs[0][0]
                stream = b"".join(seg for _, seg in sorted_segs)
                data[f"{direction}_stream"] = stream
                data[f"{direction}_tls_ranges"] = find_tls_signaling_ranges(stream)
            else:
                data[f"{direction}_base"] = None
                data[f"{direction}_tls_ranges"] = []

    for pkt in packets:
        do_trim = False
        if pkt.haslayer(TCP):
            tcp_layer = pkt.getlayer(TCP)
            flags = tcp_layer.flags
            if flags & 0x02 or flags & 0x01 or flags & 0x04: # SYN, FIN, RST
                new_packets.append(pkt)
                continue
            
            if tcp_layer.payload:
                session_id, direction = get_tcp_session_key(pkt)
                if session_id and session_id in sessions:
                    sess = sessions[session_id]
                    base_seq = sess.get(f"{direction}_base")
                    tls_ranges = sess.get(f"{direction}_tls_ranges", [])
                    
                    if base_seq is not None:
                        offset = tcp_layer.seq - base_seq
                        payload_len = len(bytes(tcp_layer.payload))
                        intersects = any(offset < rend and (offset + payload_len) > rstart for rstart, rend in tls_ranges)
                        if not intersects:
                            do_trim = True

        if do_trim:
            trimmed += 1
            new_packets.append(trim_packet_payload(pkt))
        else:
            new_packets.append(pkt)

    return new_packets, total, trimmed, error_log


class IntelligentTrimmingStage(ProcessingStep):
    """
    智能裁切处理步骤，用于从pcap文件中裁切TLS应用数据。
    第三阶段增强：支持多层封装的载荷裁切处理。
    """
    suffix: str = ProcessingConstants.TRIM_PACKET_SUFFIX
    
    def __init__(self):
        super().__init__()
        self._logger = get_logger('intelligent_trimming')
        # 初始化封装处理适配器
        self._encap_adapter = ProcessingAdapter()
        self._logger.info("智能裁切步骤初始化完成，支持多层封装处理")
    
    @property
    def name(self) -> str:
        return "Intelligent Trim"

    def process_file(self, input_path: str, output_path: str) -> Optional[Dict]:
        """处理单个pcap文件，执行智能TLS裁切。"""
        import time
        from ..infrastructure.logging import log_performance
        
        start_time = time.time()
        
        self._logger.debug(f"开始智能裁切: {input_path}")
        ext = os.path.splitext(input_path)[1].lower()
        reader_cls = PcapNgReader if ext == ".pcapng" else PcapReader
        
        with reader_cls(input_path) as reader:
            all_packets = reader.read_all()
        
        # 重置适配器统计
        self._encap_adapter.reset_stats()
        
        # 使用增强版载荷处理
        processed_packets, total_count, trimmed_count, error_log = _process_pcap_data_enhanced(
            all_packets, self._encap_adapter
        )
        
        # 确保输出文件的目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        wrpcap(output_path, processed_packets, append=False)
        
        trim_rate = (trimmed_count / total_count * ProcessingConstants.PERCENTAGE_MULTIPLIER) if total_count > 0 else 0
        
        # 获取封装处理统计
        encap_stats = self._encap_adapter.get_processing_stats()
        
        # 记录性能指标
        end_time = time.time()
        duration = end_time - start_time
        log_performance('enhanced_trimming_process_file', duration, 'trimming.performance',
                       total_packets=total_count, trimmed_packets=trimmed_count,
                       trim_rate=trim_rate, encapsulated_packets=encap_stats['encapsulated_packets'],
                       encapsulation_ratio=encap_stats['encapsulation_ratio'])
        
        self._logger.info(f"增强智能裁切完成: {input_path} -> {output_path}, "
                         f"裁切包数: {trimmed_count}/{total_count} ({trim_rate:.1f}%), "
                         f"封装包数: {encap_stats['encapsulated_packets']} ({encap_stats['encapsulation_ratio']*100:.1f}%), "
                         f"耗时={duration:.2f}秒")
        
        summary = {
            'subdir': os.path.basename(os.path.dirname(input_path)),
            'input_filename': os.path.basename(input_path),
            'output_filename': os.path.basename(output_path),
            'total_packets': total_count,
            'trimmed_packets': trimmed_count,
            'trim_rate': trim_rate,
            'encapsulated_packets': encap_stats['encapsulated_packets'],
            'encapsulation_ratio': encap_stats['encapsulation_ratio'],
            'multi_ip_packets': encap_stats['multi_ip_packets'],
            'processing_errors': encap_stats['processing_errors']
        }
        return summary 