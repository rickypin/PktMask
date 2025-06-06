#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
说明：
  本程序用于处理 pcap/pcapng 文件，对每个报文进行处理：
    1. 对于每个 TCP 会话，按会话分组并分别对双向数据进行 TCP 流重组，
       并计算每个方向的 base_seq 和完整流数据。
    2. 对每个方向的重组流，扫描出 TLS 信令记录的范围（即消息在流中的起止偏移），
       TLS 信令记录类型包括 Change Cipher Spec (20)、Alert (21) 和 Handshake (22)。
    3. 遍历每个 TCP 报文，根据其在重组流中的位置判断其 payload 是否与 TLS 信令记录范围有交集，
       若无交集，则认为是 Application Data，进行裁切（删除 TCP payload）。
    4. 同时，对于带有 SYN、FIN 或 RST 的 TCP 报文，不做裁切处理，直接保留。
       
依赖：
  pip install scapy
"""

import os
import sys
import datetime
import logging
import argparse
from scapy.all import PcapReader, PcapNgReader, wrpcap

def current_time():
    """返回当前时间的字符串，用于日志记录。"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 定义 TLS 信令记录类型：Change Cipher Spec (20)、Alert (21)、Handshake (22)
TLS_SIGNALING_TYPES = {20, 21, 22}

def find_tls_signaling_ranges(payload: bytes) -> list:
    """
    在完整的重组流中查找 TLS 信令记录的范围，并返回一个列表，每个元素为 (start, end)。
    TLS 记录格式：5字节头（1字节类型，2字节版本，2字节长度） + payload
    如果记录类型在 TLS_SIGNALING_TYPES 中，则标记该记录的范围。
    """
    ranges = []
    i = 0
    while i + 5 <= len(payload):
        record_type = payload[i]
        record_length = int.from_bytes(payload[i+3:i+5], byteorder='big')
        if i + 5 + record_length > len(payload):
            # 不完整的记录，退出循环
            break
        if record_type in TLS_SIGNALING_TYPES:
            rec_end = i + 5 + record_length
            ranges.append((i, rec_end))
            logging.debug(f"找到TLS信令记录: type={record_type}, range=({i}, {rec_end})")
        i += 5 + record_length
    return ranges

def trim_packet(packet, error_log):
    """
    裁切单个报文的 TCP payload（删除整个 payload），同时删除 TCP 与 IP 层的校验和字段，
    便于写出时重计算。
    """
    if packet.haslayer("TCP"):
        tcp_layer = packet.getlayer("TCP")
        try:
            tcp_payload = bytes(tcp_layer.payload)
        except Exception as e:
            error_log.append(f"{current_time()} - 获取 TCP payload 出错：{str(e)}")
            tcp_payload = b""
        if tcp_payload:
            tcp_layer.remove_payload()
            logging.debug(f"裁切报文，原 payload 长度：{len(tcp_payload)}")
            # 删除校验和字段
            if hasattr(tcp_layer, "chksum"):
                del tcp_layer.chksum
            if packet.haslayer("IP"):
                ip_layer = packet.getlayer("IP")
                if hasattr(ip_layer, "chksum"):
                    del ip_layer.chksum
    return packet

def get_tcp_session_key(packet):
    """
    获取 TCP 会话的标准化 key 及报文方向。
    对于一个 TCP 报文（要求包含 TCP 和 IP/IPv6 层），返回：
      - session_id: 形如 (ip1, port1, ip2, port2)，其中 (ip1, port1) 按字典序不大于 (ip2, port2)
      - direction: 若报文的 (src, sport) 与 session_id 中的 (ip1, port1) 相同，则标记为 "forward"，否则为 "reverse"
    """
    if packet.haslayer("TCP"):
        if packet.haslayer("IP"):
            src = packet["IP"].src
            dst = packet["IP"].dst
        elif packet.haslayer("IPv6"):
            src = packet["IPv6"].src
            dst = packet["IPv6"].dst
        else:
            return None, None
        sport = packet["TCP"].sport
        dport = packet["TCP"].dport
        if (src, sport) <= (dst, dport):
            session_id = (src, sport, dst, dport)
            direction = "forward"
        else:
            session_id = (dst, dport, src, sport)
            direction = "reverse"
        return session_id, direction
    return None, None

def process_file_trim(file_path, error_log):
    """
    处理单个 pcap/pcapng 文件：
      1. 读取所有报文，并按 TCP 会话分组，同时分别收集每个方向的 (seq, payload) 数据。
      2. 对每个会话，重组 forward 与 reverse 两个方向的流数据，计算 base_seq，并提取 TLS 信令记录范围。
      3. 遍历每个报文，根据其在重组流中的位置判断其 payload 是否与 TLS 信令记录范围有交集，
         若无交集，则认为是 Application Data，进行裁切；否则保留。
      4. 同时，对于带有 SYN、FIN 或 RST 标志的报文，直接保留，不进行裁切。
    返回：
      new_packets: 处理后的报文列表
      total: 原始报文总数
      trimmed: 裁切掉 TCP payload 的报文数量
    """
    new_packets = []
    total = 0
    trimmed = 0
    packets = []

    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pcap":
            reader_cls = PcapReader
        elif ext == ".pcapng":
            reader_cls = PcapNgReader
        else:
            raise ValueError("不支持的文件扩展名")
        
        with reader_cls(file_path) as reader:
            for pkt in reader:
                packets.append(pkt)
                total += 1
    except Exception as e:
        error_log.append(f"{current_time()} - 处理文件 {file_path} 出错：{str(e)}")
        return None, total, trimmed

    # 按 TCP 会话分组，并分别收集每个方向的 (seq, payload)
    sessions = {}  # 格式：{session_id: {"packets": [...],
                   #         "forward_segments": [(seq, payload), ...],
                   #         "reverse_segments": [(seq, payload), ...],
                   #         "forward_base": int, "forward_stream": bytes, "forward_tls_ranges": list,
                   #         "reverse_base": int, "reverse_stream": bytes, "reverse_tls_ranges": list }}
    for pkt in packets:
        session_id, direction = get_tcp_session_key(pkt)
        if session_id is None:
            continue
        if session_id not in sessions:
            sessions[session_id] = {"packets": [], "forward_segments": [], "reverse_segments": []}
        sessions[session_id]["packets"].append(pkt)
        if pkt.haslayer("TCP"):
            try:
                payload = bytes(pkt["TCP"].payload)
            except Exception as e:
                error_log.append(f"{current_time()} - 获取 TCP payload 出错：{str(e)}")
                payload = b""
            if payload:
                if direction == "forward":
                    sessions[session_id]["forward_segments"].append((pkt["TCP"].seq, payload))
                elif direction == "reverse":
                    sessions[session_id]["reverse_segments"].append((pkt["TCP"].seq, payload))
    
    # 对每个会话分别重组两个方向的流数据，并计算 base_seq，以及提取 TLS 信令范围
    for sess_id, data in sessions.items():
        # forward方向
        if data["forward_segments"]:
            sorted_forward = sorted(data["forward_segments"], key=lambda x: x[0])
            base_forward = sorted_forward[0][0]
            forward_stream = b"".join(seg for seq, seg in sorted_forward)
            data["forward_base"] = base_forward
            data["forward_stream"] = forward_stream
            data["forward_tls_ranges"] = find_tls_signaling_ranges(forward_stream)
            logging.debug(f"会话 {sess_id} forward: base_seq={base_forward}, stream_len={len(forward_stream)}, tls_ranges={data['forward_tls_ranges']}")
        else:
            data["forward_base"] = None
            data["forward_stream"] = b""
            data["forward_tls_ranges"] = []
        # reverse方向
        if data["reverse_segments"]:
            sorted_reverse = sorted(data["reverse_segments"], key=lambda x: x[0])
            base_reverse = sorted_reverse[0][0]
            reverse_stream = b"".join(seg for seq, seg in sorted_reverse)
            data["reverse_base"] = base_reverse
            data["reverse_stream"] = reverse_stream
            data["reverse_tls_ranges"] = find_tls_signaling_ranges(reverse_stream)
            logging.debug(f"会话 {sess_id} reverse: base_seq={base_reverse}, stream_len={len(reverse_stream)}, tls_ranges={data['reverse_tls_ranges']}")
        else:
            data["reverse_base"] = None
            data["reverse_stream"] = b""
            data["reverse_tls_ranges"] = []

    # 遍历每个报文，根据其 TCP seq 与会话重组流判断是否进行裁切
    for pkt in packets:
        # 若报文带有 SYN、FIN 或 RST 标志，则不做裁切
        if pkt.haslayer("TCP"):
            tcp_layer = pkt.getlayer("TCP")
            flags = tcp_layer.flags
            # SYN:0x02, FIN:0x01, RST:0x04
            if flags & 0x02 or flags & 0x01 or flags & 0x04:
                logging.info(f"报文 seq={tcp_layer.seq} 带有 SYN/FIN/RST 标志，不裁切。")
                new_packets.append(pkt)
                continue

        do_trim = False  # 默认保留
        if pkt.haslayer("TCP"):
            try:
                tcp_payload = bytes(pkt["TCP"].payload)
            except Exception as e:
                error_log.append(f"{current_time()} - 获取 TCP payload 出错：{str(e)}")
                tcp_payload = b""
            if tcp_payload:
                session_id, direction = get_tcp_session_key(pkt)
                if session_id is None:
                    logging.debug("无法获取会话信息，跳过裁切判断。")
                else:
                    sess = sessions.get(session_id, {})
                    if direction == "forward":
                        base_seq = sess.get("forward_base")
                        tls_ranges = sess.get("forward_tls_ranges", [])
                    else:
                        base_seq = sess.get("reverse_base")
                        tls_ranges = sess.get("reverse_tls_ranges", [])
                    if base_seq is None:
                        logging.warning(f"会话 {session_id} 方向 {direction} 无 base_seq，跳过该报文裁切判断。")
                    else:
                        offset = pkt["TCP"].seq - base_seq
                        payload_len = len(tcp_payload)
                        logging.debug(f"报文 seq={pkt['TCP'].seq}, offset={offset}, payload_len={payload_len}")
                        # 判断该报文在重组流中的范围 [offset, offset+payload_len) 是否与任一 TLS 信令记录范围有交集
                        intersects = False
                        for (rstart, rend) in tls_ranges:
                            if offset < rend and (offset + payload_len) > rstart:
                                intersects = True
                                logging.info(f"报文 seq={pkt['TCP'].seq} 与TLS信令范围 ({rstart}, {rend}) 有交集，保留该报文。")
                                break
                        if not intersects:
                            do_trim = True
                            logging.info(f"报文 seq={pkt['TCP'].seq} 判定为 Application Data，无TLS信令交集，执行裁切。")
        if do_trim:
            trimmed += 1
            pkt = trim_packet(pkt, error_log)
        new_packets.append(pkt)
    return new_packets, total, trimmed

def main():
    parser = argparse.ArgumentParser(description="处理 pcap/pcapng 文件，裁切 TLS Application Data 部分")
    parser.add_argument("file_path", help="pcap/pcapng 文件路径")
    parser.add_argument("--debug", action="store_true", help="启用调试日志")
    args = parser.parse_args()

    # 根据参数设置日志级别：有 --debug 则 DEBUG，否则 INFO
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='[%(asctime)s] %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    
    file_path = args.file_path
    if not os.path.isfile(file_path):
        logging.error(f"错误：文件 {file_path} 不存在！")
        sys.exit(1)
    
    error_log = []
    logging.info(f"开始处理文件：{file_path}")
    packets, total, trimmed = process_file_trim(file_path, error_log)
    if packets is None:
        logging.error("处理失败，请检查错误日志。")
        for err in error_log:
            logging.error(err)
        sys.exit(1)
    
    # 构造输出文件路径（在原文件名后添加“-trimmed”后缀）
    dir_name, base_name = os.path.split(file_path)
    name, ext = os.path.splitext(base_name)
    output_file = os.path.join(dir_name, f"{name}-trimmed{ext}")
    
    try:
        wrpcap(output_file, packets)
        logging.info(f"处理完成：原报文数 {total}，裁切报文数 {trimmed}")
        logging.info(f"输出文件已写入：{output_file}")
    except Exception as e:
        error_log.append(f"{current_time()} - 写出文件 {output_file} 出错：{str(e)}")
        logging.error(f"写出文件出错：{str(e)}")
    
    if error_log:
        error_log_file = os.path.join(dir_name, "error.log")
        try:
            with open(error_log_file, "w", encoding="utf-8") as f_error:
                for entry in error_log:
                    f_error.write(entry + "\n")
            logging.info(f"错误日志已写入：{error_log_file}")
        except Exception as e:
            logging.error(f"写入错误日志出错：{str(e)}")

if __name__ == "__main__":
    main()

