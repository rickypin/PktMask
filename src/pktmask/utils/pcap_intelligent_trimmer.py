#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
本模块包含智能裁切 TLS Application Data 的核心逻辑。
代码源自一份历史脚本，并经过重构以适配当前的流水线架构。
"""

import os
from typing import List, Tuple, Dict, Optional

from scapy.all import PcapReader, PcapNgReader, wrpcap, TCP, IP, IPv6

from pktmask.core.base_step import ProcessingStep

# --- 从原始脚本移植的核心算法函数 ---

TLS_SIGNALING_TYPES = {20, 21, 22}

def find_tls_signaling_ranges(payload: bytes) -> list:
    """在完整的重组流中查找 TLS 信令记录的范围。"""
    ranges = []
    i = 0
    while i + 5 <= len(payload):
        record_type = payload[i]
        record_length = int.from_bytes(payload[i+3:i+5], byteorder='big')
        if i + 5 + record_length > len(payload):
            break
        if record_type in TLS_SIGNALING_TYPES:
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


class IntelligentTrimmingStep(ProcessingStep):
    """
    智能裁切处理步骤，用于从pcap文件中裁切TLS应用数据。
    """
    suffix: str = "-Trimmed"
    
    @property
    def name(self) -> str:
        return "Intelligent Trim"

    def process_file(self, input_path: str, output_path: str) -> Optional[Dict]:
        """处理单个pcap文件，执行智能TLS裁切。"""
        try:
            ext = os.path.splitext(input_path)[1].lower()
            reader_cls = PcapNgReader if ext == ".pcapng" else PcapReader
            
            with reader_cls(input_path) as reader:
                all_packets = reader.read_all()
                
            processed_packets, total_count, trimmed_count, error_log = _process_pcap_data(all_packets)
            
            wrpcap(output_path, processed_packets, append=False)
            
            summary = {
                'subdir': os.path.basename(os.path.dirname(input_path)),
                'processed_files': 1,
                'total_packets': total_count,
                'trimmed_packets': trimmed_count,
                'error_log': error_log
            }
            return {'report': summary}

        except Exception as e:
            return {
                'error_log': [f"Fatal error processing {os.path.basename(input_path)}: {e}"]
            } 