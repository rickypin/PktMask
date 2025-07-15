#!/usr/bin/env python3
"""TLS 流量分析工具 - 全面的 TLS 协议流量分析器

本模块实现了一个全面的 TLS 流量分析工具，支持：
1. TCP 流向识别：准确区分 TCP 五元组的两个传输方向
2. TLS 消息类型识别：识别并分类所有 TLS 消息类型（20-24）
3. 跨 TCP 段处理：正确处理单个 TLS 消息被分割到多个 TCP 段的情况
4. 协议层级分析：显示每个数据包的协议封装层级
5. 详细的消息结构分析和统计信息

遵循 Context7 标准和项目架构模式。

使用示例：
    python -m pktmask.tools.tls_flow_analyzer --pcap input.pcapng
    python -m pktmask.tools.tls_flow_analyzer --pcap input.pcapng --detailed --output-dir ./results
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

# 项目内部导入
from ..infrastructure.logging.logger import get_logger
from ..utils.path import resource_path

# HTML模板支持
try:
    from jinja2 import Template
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

# 常量定义
MIN_TSHARK_VERSION: Tuple[int, int, int] = (4, 2, 0)

# TLS协议类型映射
TLS_CONTENT_TYPES = {
    20: "ChangeCipherSpec",
    21: "Alert", 
    22: "Handshake",
    23: "ApplicationData",
    24: "Heartbeat"
}

# TLS处理策略映射
TLS_PROCESSING_STRATEGIES = {
    20: "keep_all",      # ChangeCipherSpec - 完全保留
    21: "keep_all",      # Alert - 完全保留
    22: "keep_all",      # Handshake - 完全保留
    23: "mask_payload",  # ApplicationData - 智能掩码(保留5字节头部)
    24: "keep_all"       # Heartbeat - 完全保留
}


class TLSFlowAnalyzer:
    """TLS 流量分析器主类"""
    
    def __init__(self, verbose: bool = False):
        """初始化分析器
        
        Args:
            verbose: 是否启用详细输出
        """
        self.verbose = verbose
        self.logger = get_logger('tls_flow_analyzer')
        
        # 分析结果存储
        self.tcp_flows: Dict[str, Dict[str, Any]] = {}
        self.tls_messages: List[Dict[str, Any]] = []
        self.protocol_layers: Dict[int, List[str]] = {}
        self.message_statistics: Dict[str, Any] = {}
        
    def analyze_pcap(self, pcap_path: str, tshark_path: Optional[str] = None,
                    decode_as: Optional[List[str]] = None) -> Dict[str, Any]:
        """分析 PCAP 文件中的 TLS 流量
        
        Args:
            pcap_path: PCAP 文件路径
            tshark_path: 自定义 tshark 可执行文件路径
            decode_as: 额外的端口解码规则
            
        Returns:
            分析结果字典
        """
        self.logger.info(f"开始分析 PCAP 文件: {pcap_path}")
        start_time = time.time()
        
        try:
            # 验证 tshark 版本
            tshark_exec = self._check_tshark_version(tshark_path)
            
            # 第一阶段：基础 TLS 消息扫描
            tls_packets = self._scan_tls_messages(pcap_path, tshark_exec, decode_as)
            
            # 第二阶段：TCP 流分析
            tcp_flows = self._analyze_tcp_flows(pcap_path, tshark_exec, tls_packets, decode_as)
            
            # 第三阶段：跨段消息重组和单包消息解析
            reassembled_messages = self._reassemble_cross_segment_messages(tcp_flows)

            # 如果没有重组消息，则提取单包消息
            if not reassembled_messages:
                single_packet_messages = self._extract_single_packet_tls_messages(tls_packets)
                all_tls_messages = single_packet_messages
            else:
                # 有重组消息时，使用重组结果（已包含所有TLS消息）
                all_tls_messages = reassembled_messages

            # 第四阶段：生成详细分析结果
            analysis_result = self._generate_analysis_result(
                tls_packets, tcp_flows, all_tls_messages
            )
            
            analysis_time = time.time() - start_time
            self.logger.info(f"TLS 流量分析完成，耗时 {analysis_time:.2f} 秒")
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"TLS 流量分析失败: {e}")
            raise RuntimeError(f"TLS 流量分析失败: {e}") from e
    
    def _check_tshark_version(self, tshark_path: Optional[str]) -> str:
        """验证 tshark 版本并返回可执行路径"""
        executable = tshark_path or "tshark"
        
        try:
            completed = subprocess.run(
                [executable, "-v"], check=True, text=True, capture_output=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise RuntimeError(f"无法执行 tshark '{executable}': {exc}") from exc
        
        version = self._parse_tshark_version(completed.stdout + completed.stderr)
        if version is None:
            raise RuntimeError("无法解析 tshark 版本号")
        
        if version < MIN_TSHARK_VERSION:
            ver_str = ".".join(map(str, version))
            min_str = ".".join(map(str, MIN_TSHARK_VERSION))
            raise RuntimeError(f"tshark 版本过低 ({ver_str})，需要 ≥ {min_str}")
        
        if self.verbose:
            self.logger.info(f"检测到 tshark {'.'.join(map(str, version))} 于 {executable}")
        
        return executable
    
    def _parse_tshark_version(self, output: str) -> Optional[Tuple[int, int, int]]:
        """从 tshark -v 输出解析版本号"""
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
        if not m:
            return None
        return tuple(map(int, m.groups()))  # type: ignore [return-value]
    
    def _scan_tls_messages(self, pcap_path: str, tshark_exec: str,
                          decode_as: Optional[List[str]]) -> List[Dict[str, Any]]:
        """扫描 PCAP 文件中的 TLS 消息"""
        self.logger.info("第一阶段：扫描 TLS 消息")

        # 第一次扫描：使用TCP重组获取完整TLS消息
        self.logger.info("第一阶段-1：扫描重组后的TLS消息")
        cmd_reassembled = [
            tshark_exec,
            "-2",  # 两遍分析，启用重组
            "-r", pcap_path,
            "-T", "json",
            "-e", "frame.number",
            "-e", "frame.protocols",
            "-e", "frame.time_relative",
            "-e", "ip.src",
            "-e", "ip.dst",
            "-e", "ipv6.src",
            "-e", "ipv6.dst",
            "-e", "tcp.srcport",
            "-e", "tcp.dstport",
            "-e", "tcp.stream",
            "-e", "tcp.seq",
            "-e", "tcp.seq_raw",  # 绝对序列号
            "-e", "tcp.len",
            "-e", "tcp.payload",
            "-e", "tls.record.content_type",
            "-e", "tls.record.opaque_type",
            "-e", "tls.record.length",
            "-e", "tls.record.version",
            "-e", "tls.app_data",
            "-E", "occurrence=a",
            "-o", "tcp.desegment_tcp_streams:TRUE",
        ]

        # 第二次扫描：不使用TCP重组获取TLS段数据
        self.logger.info("第一阶段-2：扫描TLS段数据")
        cmd_segments = [
            tshark_exec,
            "-r", pcap_path,
            "-T", "json",
            "-e", "frame.number",
            "-e", "frame.protocols",
            "-e", "frame.time_relative",
            "-e", "ip.src",
            "-e", "ip.dst",
            "-e", "ipv6.src",
            "-e", "ipv6.dst",
            "-e", "tcp.srcport",
            "-e", "tcp.dstport",
            "-e", "tcp.stream",
            "-e", "tcp.seq",
            "-e", "tcp.seq_raw",  # 绝对序列号
            "-e", "tcp.len",
            "-e", "tcp.payload",
            "-e", "tls.segment.data",  # TLS段数据字段
            "-E", "occurrence=a",
        ]

        # 添加解码规则
        if decode_as:
            for spec in decode_as:
                cmd_reassembled.extend(["-d", spec])
                cmd_segments.extend(["-d", spec])

        if self.verbose:
            self.logger.info(f"执行重组命令: {' '.join(cmd_reassembled)}")
            self.logger.info(f"执行段数据命令: {' '.join(cmd_segments)}")

        # 执行第一次扫描（重组）
        try:
            completed_reassembled = subprocess.run(cmd_reassembled, check=True, text=True, capture_output=True)
            packets_reassembled = json.loads(completed_reassembled.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"重组TLS消息扫描失败: {exc}") from exc

        # 执行第二次扫描（段数据）
        try:
            completed_segments = subprocess.run(cmd_segments, check=True, text=True, capture_output=True)
            packets_segments = json.loads(completed_segments.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"TLS段数据扫描失败: {exc}") from exc

        # 合并两次扫描的结果
        tls_packets = self._merge_tls_scan_results(packets_reassembled, packets_segments)

        self.logger.info(f"发现 {len(tls_packets)} 个包含 TLS 消息的数据包")
        return tls_packets

    def _merge_tls_scan_results(self, packets_reassembled: List[Dict[str, Any]],
                               packets_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并两次TLS扫描的结果"""
        # 创建帧号到数据包的映射
        frame_to_packet = {}

        # 首先添加重组扫描的结果（包含完整TLS信息）
        for packet in packets_reassembled:
            layers = packet.get("_source", {}).get("layers", {})
            if self._has_tls_content(layers):
                frame_num = self._get_first_value(layers.get("frame.number"))
                if frame_num:
                    frame_to_packet[frame_num] = packet

        # 然后添加段数据扫描的结果（包含TLS段数据的包）
        for packet in packets_segments:
            layers = packet.get("_source", {}).get("layers", {})
            frame_num = self._get_first_value(layers.get("frame.number"))
            tls_segment_data = layers.get("tls.segment.data")

            if frame_num and tls_segment_data is not None:
                if frame_num not in frame_to_packet:
                    # 这是一个只包含TLS段数据的包（跨包消息的片段）
                    frame_to_packet[frame_num] = packet
                else:
                    # 合并TLS段数据到已存在的包中
                    existing_layers = frame_to_packet[frame_num].get("_source", {}).get("layers", {})
                    existing_layers["tls.segment.data"] = tls_segment_data

        # 按帧号排序并返回
        sorted_packets = []
        for frame_num in sorted(frame_to_packet.keys(), key=int):
            sorted_packets.append(frame_to_packet[frame_num])

        return sorted_packets

    def _has_tls_content(self, layers: Dict[str, Any]) -> bool:
        """检查数据包是否包含 TLS 记录头"""
        content_types = layers.get("tls.record.content_type", [])
        opaque_types = layers.get("tls.record.opaque_type", [])

        # 统一转换为列表
        if not isinstance(content_types, list):
            content_types = [content_types] if content_types else []
        if not isinstance(opaque_types, list):
            opaque_types = [opaque_types] if opaque_types else []

        # 检查是否包含已知的 TLS 内容类型
        all_types = content_types + opaque_types
        for type_val in all_types:
            if type_val is not None:
                try:
                    type_int = int(str(type_val).replace("0x", ""), 16 if str(type_val).startswith("0x") else 10)
                    if type_int in TLS_CONTENT_TYPES:
                        return True
                except (ValueError, TypeError):
                    continue

        return False

    def _has_tls_content_or_segment(self, layers: Dict[str, Any]) -> bool:
        """检查数据包是否包含 TLS 内容或 TLS 段数据"""
        # 首先检查是否有TLS记录头
        content_types = layers.get("tls.record.content_type", [])
        opaque_types = layers.get("tls.record.opaque_type", [])

        # 统一转换为列表
        if not isinstance(content_types, list):
            content_types = [content_types] if content_types else []
        if not isinstance(opaque_types, list):
            opaque_types = [opaque_types] if opaque_types else []

        # 检查是否包含已知的 TLS 内容类型
        all_types = content_types + opaque_types
        for type_val in all_types:
            if type_val is not None:
                try:
                    type_int = int(str(type_val).replace("0x", ""), 16 if str(type_val).startswith("0x") else 10)
                    if type_int in TLS_CONTENT_TYPES:
                        return True
                except (ValueError, TypeError):
                    continue

        # 检查是否包含TLS段数据（跨包消息的片段）
        tls_segment_data = layers.get("tls.segment.data")
        if tls_segment_data is not None:
            return True

        # 检查协议栈中是否包含TLS
        protocols = layers.get("frame.protocols", "")
        if isinstance(protocols, list):
            protocols = protocols[0] if protocols else ""
        if "tls" in str(protocols).lower():
            return True

        return False

    def _analyze_tcp_flows(self, pcap_path: str, tshark_exec: str,
                          tls_packets: List[Dict[str, Any]],
                          decode_as: Optional[List[str]]) -> Dict[str, Dict[str, Any]]:
        """分析 TCP 流信息"""
        self.logger.info("第二阶段：分析 TCP 流")

        # 提取所有涉及的 TCP 流
        tcp_streams = set()
        for packet in tls_packets:
            layers = packet.get("_source", {}).get("layers", {})
            stream_id = layers.get("tcp.stream")
            if stream_id is not None:
                # 处理可能的列表格式
                stream_id_str = self._get_first_value(stream_id)
                if stream_id_str is not None:
                    tcp_streams.add(str(stream_id_str))

        self.logger.info(f"发现 {len(tcp_streams)} 个 TCP 流")

        # 分析每个 TCP 流
        tcp_flows = {}
        for stream_id in tcp_streams:
            flow_info = self._analyze_single_tcp_flow(
                pcap_path, tshark_exec, stream_id, decode_as
            )
            if flow_info:
                tcp_flows[stream_id] = flow_info

        return tcp_flows

    def _analyze_single_tcp_flow(self, pcap_path: str, tshark_exec: str,
                                stream_id: str, decode_as: Optional[List[str]]) -> Optional[Dict[str, Any]]:
        """分析单个 TCP 流"""
        cmd = [
            tshark_exec,
            "-2",
            "-r", pcap_path,
            "-Y", f"tcp.stream == {stream_id}",
            "-T", "json",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "ip.src",
            "-e", "ip.dst",
            "-e", "ipv6.src",
            "-e", "ipv6.dst",
            "-e", "tcp.srcport",
            "-e", "tcp.dstport",
            "-e", "tcp.seq",
            "-e", "tcp.seq_raw",  # 绝对序列号
            "-e", "tcp.ack",
            "-e", "tcp.len",
            "-e", "tcp.flags",
            "-e", "tcp.payload",
            "-E", "occurrence=a",
            "-o", "tcp.desegment_tcp_streams:TRUE",
        ]

        if decode_as:
            for spec in decode_as:
                cmd.extend(["-d", spec])

        try:
            completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
            packets = json.loads(completed.stdout)
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"TCP流分析失败 (stream {stream_id}): {e.stderr}")
            return None
        except json.JSONDecodeError as e:
            self.logger.warning(f"TCP流JSON解析失败 (stream {stream_id}): {e}")
            return None

        if not packets:
            return None

        # 分析流方向
        flow_directions = self._identify_flow_directions(packets)

        # 重组 TCP 载荷
        reassembled_payloads = self._reassemble_tcp_payloads(packets, flow_directions)

        return {
            "stream_id": stream_id,
            "packets": packets,
            "directions": flow_directions,
            "reassembled_payloads": reassembled_payloads,
            "packet_count": len(packets)
        }

    def _identify_flow_directions(self, packets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """识别 TCP 流的两个方向"""
        directions = {
            "forward": {"src_ip": None, "dst_ip": None, "src_port": None, "dst_port": None, "packets": []},
            "reverse": {"src_ip": None, "dst_ip": None, "src_port": None, "dst_port": None, "packets": []}
        }

        # 分析第一个数据包确定正向
        if packets:
            first_packet = packets[0]
            layers = first_packet.get("_source", {}).get("layers", {})

            # 获取 IP 地址（优先 IPv4，然后 IPv6）
            src_ip = self._get_first_value(layers.get("ip.src")) or self._get_first_value(layers.get("ipv6.src"))
            dst_ip = self._get_first_value(layers.get("ip.dst")) or self._get_first_value(layers.get("ipv6.dst"))
            src_port = self._get_first_value(layers.get("tcp.srcport"))
            dst_port = self._get_first_value(layers.get("tcp.dstport"))

            directions["forward"].update({
                "src_ip": src_ip, "dst_ip": dst_ip,
                "src_port": src_port, "dst_port": dst_port
            })
            directions["reverse"].update({
                "src_ip": dst_ip, "dst_ip": src_ip,
                "src_port": dst_port, "dst_port": src_port
            })

        # 分类所有数据包
        for packet in packets:
            layers = packet.get("_source", {}).get("layers", {})
            src_ip = self._get_first_value(layers.get("ip.src")) or self._get_first_value(layers.get("ipv6.src"))
            src_port = self._get_first_value(layers.get("tcp.srcport"))

            if (src_ip == directions["forward"]["src_ip"] and
                src_port == directions["forward"]["src_port"]):
                directions["forward"]["packets"].append(packet)
            else:
                directions["reverse"]["packets"].append(packet)

        return directions

    def _get_first_value(self, value: Any) -> Any:
        """获取第一个值（处理列表和单值）"""
        if isinstance(value, list):
            return value[0] if value else None
        return value

    def _clean_protocol_layers(self, protocol_layers: List[str]) -> List[str]:
        """
        清理协议层级列表，移除冗余和重复的协议层

        Args:
            protocol_layers: 原始协议层级列表

        Returns:
            清理后的协议层级列表
        """
        if not protocol_layers:
            return []

        cleaned = []
        seen_protocols = set()

        # 定义需要去重的协议（保留第一次出现）
        dedup_protocols = {
            'x509sat',      # X.509证书ASN.1结构
            'x509af',       # X.509证书属性框架
            'x509ce',       # X.509证书扩展
            'x509if',       # X.509信息框架
            'pkcs1',        # PKCS#1 RSA加密
            'pkix1explicit', # PKIX证书扩展
            'pkix1implicit', # PKIX隐式证书扩展
            'cms',          # 加密消息语法
            'pkcs7',        # PKCS#7加密消息
        }

        # 定义核心网络协议层级（按优先级排序）
        core_protocols = [
            'eth', 'ethertype',           # 以太网层
            'ip', 'ipv6',                 # 网络层
            'tcp', 'udp',                 # 传输层
            'tls', 'ssl',                 # 安全层
            'http', 'http2',              # 应用层
        ]

        for protocol in protocol_layers:
            protocol_lower = protocol.lower()

            # 对于需要去重的协议，只保留第一次出现
            if protocol_lower in dedup_protocols:
                if protocol_lower not in seen_protocols:
                    cleaned.append(protocol)
                    seen_protocols.add(protocol_lower)
            else:
                # 其他协议直接保留
                cleaned.append(protocol)

        # 如果清理后的协议层级过长（超过10层），进一步简化
        if len(cleaned) > 10:
            # 保留核心协议层级
            core_found = []
            other_found = []

            for protocol in cleaned:
                if protocol.lower() in core_protocols:
                    core_found.append(protocol)
                else:
                    other_found.append(protocol)

            # 限制非核心协议的数量
            if len(other_found) > 3:
                # 保留前3个非核心协议
                other_found = other_found[:3]

            cleaned = core_found + other_found

        return cleaned

    def _reassemble_tcp_payloads(self, packets: List[Dict[str, Any]],
                                directions: Dict[str, Any]) -> Dict[str, Any]:
        """重组 TCP 载荷并记录序列号映射"""
        reassembled = {"forward": {"payload": b"", "seq_mapping": []},
                      "reverse": {"payload": b"", "seq_mapping": []}}

        for direction_name, direction_info in directions.items():
            # 按序列号排序数据包
            direction_packets = sorted(
                direction_info["packets"],
                key=lambda p: int(self._get_first_value(
                    p.get("_source", {}).get("layers", {}).get("tcp.seq", 0)
                ))
            )

            # 重组载荷并记录序列号映射
            payload_data = b""
            seq_mapping = []
            current_offset = 0

            for packet in direction_packets:
                layers = packet.get("_source", {}).get("layers", {})
                tcp_payload = layers.get("tcp.payload")
                tcp_seq_raw = self._get_first_value(layers.get("tcp.seq_raw"))

                if tcp_payload and tcp_seq_raw:
                    payload_hex = self._get_first_value(tcp_payload)
                    if payload_hex:
                        try:
                            # 清理十六进制字符串
                            clean_hex = payload_hex.replace(":", "").replace(" ", "")
                            payload_bytes = bytes.fromhex(clean_hex)

                            # 记录这段载荷在重组数据中的位置和对应的序列号
                            if len(payload_bytes) > 0:
                                seq_mapping.append({
                                    "offset_start": current_offset,
                                    "offset_end": current_offset + len(payload_bytes) - 1,
                                    "tcp_seq_raw": int(tcp_seq_raw),
                                    "payload_length": len(payload_bytes)
                                })

                                payload_data += payload_bytes
                                current_offset += len(payload_bytes)
                        except ValueError:
                            continue

            reassembled[direction_name]["payload"] = payload_data
            reassembled[direction_name]["seq_mapping"] = seq_mapping

        return reassembled

    def _find_actual_seq_for_offset(self, tls_offset: int, seq_mapping: List[Dict[str, Any]]) -> int:
        """根据TLS记录在重组载荷中的偏移位置，查找对应的实际TCP序列号"""
        for mapping in seq_mapping:
            offset_start = mapping["offset_start"]
            offset_end = mapping["offset_end"]
            tcp_seq_raw = mapping["tcp_seq_raw"]

            if offset_start <= tls_offset <= offset_end:
                # TLS记录在这个TCP包的载荷中
                # 计算TLS记录在该TCP包载荷中的相对偏移
                relative_offset = tls_offset - offset_start
                return tcp_seq_raw + relative_offset

        # 如果没有找到匹配的映射，返回0（这种情况不应该发生）
        return 0

    def _reassemble_cross_segment_messages(self, tcp_flows: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """重组跨 TCP 段的 TLS 消息并解析单包中的完整 TLS 消息"""
        self.logger.info("第三阶段：重组跨段 TLS 消息并解析完整消息")

        reassembled_messages = []

        # 处理跨TCP段的重组消息
        for stream_id, flow_info in tcp_flows.items():
            for direction_name, reassembled_info in flow_info["reassembled_payloads"].items():
                payload_data = reassembled_info["payload"]
                seq_mapping = reassembled_info["seq_mapping"]

                if len(payload_data) < 5:  # TLS 记录头至少 5 字节
                    continue

                # 解析 TLS 记录，传入序列号映射信息
                tls_records = self._parse_tls_records_from_payload(
                    payload_data, stream_id, direction_name, seq_mapping=seq_mapping
                )
                reassembled_messages.extend(tls_records)

        self.logger.info(f"重组得到 {len(reassembled_messages)} 个 TLS 消息")
        return reassembled_messages

    def _extract_single_packet_tls_messages(self, tls_packets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从单个数据包中提取完整的 TLS 消息"""
        self.logger.info("提取单包中的完整 TLS 消息")

        single_packet_messages = []

        for packet in tls_packets:
            layers = packet.get("_source", {}).get("layers", {})

            # 获取基本信息
            frame_number = self._get_first_value(layers.get("frame.number"))
            tcp_stream = self._get_first_value(layers.get("tcp.stream"))
            tcp_seq = self._get_first_value(layers.get("tcp.seq"))  # 相对序列号
            tcp_seq_raw = self._get_first_value(layers.get("tcp.seq_raw"))  # 绝对序列号

            # 获取TLS内容类型
            content_types = layers.get("tls.record.content_type", [])
            opaque_types = layers.get("tls.record.opaque_type", [])
            record_lengths = layers.get("tls.record.length", [])
            record_versions = layers.get("tls.record.version", [])

            # 确保是列表格式
            if not isinstance(content_types, list):
                content_types = [content_types] if content_types else []
            if not isinstance(opaque_types, list):
                opaque_types = [opaque_types] if opaque_types else []
            if not isinstance(record_lengths, list):
                record_lengths = [record_lengths] if record_lengths else []
            if not isinstance(record_versions, list):
                record_versions = [record_versions] if record_versions else []

            # 合并所有类型
            all_types = content_types + opaque_types

            # 为每个TLS记录创建消息条目
            tls_offset = 0  # 在TCP payload中的TLS记录偏移
            for i, type_val in enumerate(all_types):
                if type_val is not None:
                    try:
                        # 解析内容类型
                        content_type = int(str(type_val).replace("0x", ""), 16 if str(type_val).startswith("0x") else 10)
                        if content_type not in TLS_CONTENT_TYPES:
                            continue

                        # 获取对应的长度和版本
                        length = int(record_lengths[i]) if i < len(record_lengths) and record_lengths[i] else 0
                        version_str = record_versions[i] if i < len(record_versions) and record_versions[i] else "0x0303"

                        # 解析版本
                        try:
                            version_int = int(str(version_str).replace("0x", ""), 16)
                            version_major = (version_int >> 8) & 0xFF
                            version_minor = version_int & 0xFF
                        except (ValueError, TypeError):
                            version_major, version_minor = 3, 3  # 默认TLS 1.2

                        # 计算TLS消息在TCP流中的绝对序列号位置
                        # 使用绝对序列号作为基础，加上TLS记录在TCP payload中的偏移
                        base_seq = int(tcp_seq_raw) if tcp_seq_raw else (int(tcp_seq) if tcp_seq else 0)
                        tls_header_seq_start = base_seq + tls_offset
                        tls_header_seq_end = tls_header_seq_start + 5  # TLS头部5字节
                        tls_payload_seq_start = tls_header_seq_end
                        tls_payload_seq_end = tls_payload_seq_start + length

                        # 创建TLS消息记录
                        tls_message = {
                            "stream_id": str(tcp_stream) if tcp_stream else "unknown",
                            "direction": "single_packet",  # 单包消息暂时标记为此方向
                            "content_type": content_type,
                            "content_type_name": TLS_CONTENT_TYPES[content_type],
                            "version": (version_major, version_minor),
                            "length": length,
                            "frame_number": int(frame_number) if frame_number else 0,
                            "tcp_seq_base": base_seq,  # TCP段的起始序列号
                            "tls_seq_start": tls_header_seq_start,  # TLS消息起始序列号
                            "tls_seq_end": tls_payload_seq_end,     # TLS消息结束序列号
                            # 新增：分离的头部和载荷序列号范围
                            "tls_header_seq_start": tls_header_seq_start,  # TLS头部起始序列号
                            "tls_header_seq_end": tls_header_seq_end,      # TLS头部结束序列号
                            "tls_payload_seq_start": tls_payload_seq_start,  # TLS载荷起始序列号
                            "tls_payload_seq_end": tls_payload_seq_end,      # TLS载荷结束序列号
                            "header_start": tls_offset,  # TLS头在TCP payload中的偏移
                            "header_end": tls_offset + 5,
                            "payload_start": tls_offset + 5,
                            "payload_end": tls_offset + 5 + length,
                            "is_complete": True,
                            "is_cross_segment": False,
                            "processing_strategy": TLS_PROCESSING_STRATEGIES[content_type]
                        }

                        # 更新下一个TLS记录的偏移
                        tls_offset += 5 + length

                        single_packet_messages.append(tls_message)

                    except (ValueError, TypeError, IndexError):
                        continue

        self.logger.info(f"提取到 {len(single_packet_messages)} 个单包 TLS 消息")
        return single_packet_messages

    def _parse_tls_records_from_payload(self, payload: bytes, stream_id: str,
                                       direction: str, base_seq: int = 0,
                                       seq_mapping: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """从 TCP 载荷中解析 TLS 记录"""
        records = []
        offset = 0

        while offset + 5 <= len(payload):
            # 解析 TLS 记录头 (5 字节)
            content_type = payload[offset]
            version_major = payload[offset + 1]
            version_minor = payload[offset + 2]
            length = int.from_bytes(payload[offset + 3:offset + 5], byteorder='big')

            # 验证内容类型
            if content_type not in TLS_CONTENT_TYPES:
                offset += 1
                continue

            # 检查记录完整性
            record_end = offset + 5 + length

            # 计算TLS消息的绝对序列号位置
            if seq_mapping:
                # 使用序列号映射查找实际的TCP序列号
                tls_header_seq_start = self._find_actual_seq_for_offset(offset, seq_mapping)
            else:
                # 兼容旧的计算方式（用于单包解析）
                tls_header_seq_start = base_seq + offset

            tls_header_seq_end = tls_header_seq_start + 5
            tls_payload_seq_start = tls_header_seq_end

            if record_end > len(payload):
                # 记录不完整，可能跨段
                if seq_mapping:
                    # 使用序列号映射查找实际的结束序列号
                    tls_payload_seq_end = self._find_actual_seq_for_offset(len(payload) - 1, seq_mapping) + 1
                else:
                    # 兼容旧的计算方式
                    tls_payload_seq_end = base_seq + len(payload)
                records.append({
                    "stream_id": stream_id,
                    "direction": direction,
                    "content_type": content_type,
                    "content_type_name": TLS_CONTENT_TYPES[content_type],
                    "version": (version_major, version_minor),
                    "length": length,
                    "declared_length": length,  # 声明的长度
                    "actual_length": len(payload) - offset - 5,  # 实际可用长度
                    "tcp_seq_base": tls_header_seq_start if seq_mapping else base_seq,
                    "tls_seq_start": tls_header_seq_start,
                    "tls_seq_end": tls_header_seq_start + 5 + length,  # 完整消息的预期结束位置
                    "tls_seq_actual_end": tls_payload_seq_end,  # 实际结束位置
                    # 新增：分离的头部和载荷序列号范围
                    "tls_header_seq_start": tls_header_seq_start,
                    "tls_header_seq_end": tls_header_seq_end,
                    "tls_payload_seq_start": tls_payload_seq_start,
                    "tls_payload_seq_end": tls_header_seq_start + 5 + length,  # 预期的载荷结束位置
                    "tls_payload_seq_actual_end": tls_payload_seq_end,  # 实际载荷结束位置
                    "header_start": offset,
                    "header_end": offset + 5,
                    "payload_start": offset + 5,
                    "payload_end": len(payload),  # 实际载荷结束位置
                    "is_complete": False,
                    "is_cross_segment": True,
                    "processing_strategy": TLS_PROCESSING_STRATEGIES[content_type]
                })
                break
            else:
                # 完整记录
                tls_payload_seq_end = tls_payload_seq_start + length
                records.append({
                    "stream_id": stream_id,
                    "direction": direction,
                    "content_type": content_type,
                    "content_type_name": TLS_CONTENT_TYPES[content_type],
                    "version": (version_major, version_minor),
                    "length": length,
                    "declared_length": length,
                    "actual_length": length,
                    "tcp_seq_base": tls_header_seq_start if seq_mapping else base_seq,
                    "tls_seq_start": tls_header_seq_start,
                    "tls_seq_end": tls_payload_seq_end,
                    # 新增：分离的头部和载荷序列号范围
                    "tls_header_seq_start": tls_header_seq_start,
                    "tls_header_seq_end": tls_header_seq_end,
                    "tls_payload_seq_start": tls_payload_seq_start,
                    "tls_payload_seq_end": tls_payload_seq_end,
                    "header_start": offset,
                    "header_end": offset + 5,
                    "payload_start": offset + 5,
                    "payload_end": record_end,
                    "is_complete": True,
                    "is_cross_segment": False,
                    "processing_strategy": TLS_PROCESSING_STRATEGIES[content_type]
                })
                offset = record_end

        return records

    def _generate_analysis_result(self, tls_packets: List[Dict[str, Any]],
                                 tcp_flows: Dict[str, Dict[str, Any]],
                                 reassembled_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成详细的分析结果"""
        self.logger.info("第四阶段：生成分析结果")

        # 基础统计
        total_frames = len(tls_packets)
        total_records = len(reassembled_messages)
        total_tcp_streams = len(tcp_flows)

        # 按协议类型统计
        protocol_type_stats = defaultdict(lambda: {"frames": 0, "records": 0})
        frame_protocol_types = defaultdict(list)

        # 统计原始数据包中的 TLS 类型
        for packet in tls_packets:
            layers = packet.get("_source", {}).get("layers", {})
            frame_number = self._get_first_value(layers.get("frame.number"))

            content_types = layers.get("tls.record.content_type", [])
            opaque_types = layers.get("tls.record.opaque_type", [])

            if not isinstance(content_types, list):
                content_types = [content_types] if content_types else []
            if not isinstance(opaque_types, list):
                opaque_types = [opaque_types] if opaque_types else []

            all_types = content_types + opaque_types
            frame_types = []

            for type_val in all_types:
                if type_val is not None:
                    try:
                        type_int = int(str(type_val).replace("0x", ""), 16 if str(type_val).startswith("0x") else 10)
                        if type_int in TLS_CONTENT_TYPES:
                            frame_types.append(type_int)
                    except (ValueError, TypeError):
                        continue

            if frame_types and frame_number:
                frame_protocol_types[int(frame_number)] = frame_types

        # 统计每种TLS类型的数据帧数（去重）
        for frame_number, frame_types in frame_protocol_types.items():
            # 对于每个帧，每种TLS类型只计算一次帧数
            unique_types = set(frame_types)
            for tls_type in unique_types:
                protocol_type_stats[tls_type]["frames"] += 1

        # 统计重组消息中的 TLS 类型
        for message in reassembled_messages:
            content_type = message["content_type"]
            protocol_type_stats[content_type]["records"] += 1

        # 协议层级分析
        protocol_layers = {}
        for packet in tls_packets:
            layers = packet.get("_source", {}).get("layers", {})
            frame_number = self._get_first_value(layers.get("frame.number"))
            protocols = self._get_first_value(layers.get("frame.protocols"))

            if frame_number and protocols:
                # 清理协议层级，移除重复的x509sat和其他冗余协议层
                cleaned_protocols = self._clean_protocol_layers(protocols.split(":"))
                protocol_layers[int(frame_number)] = cleaned_protocols

        # 生成详细的数据包信息
        detailed_frames = []
        for packet in tls_packets:
            layers = packet.get("_source", {}).get("layers", {})
            frame_number = self._get_first_value(layers.get("frame.number"))

            if frame_number:
                frame_num_int = int(frame_number)

                # 获取协议类型，如果没有TLS记录头但有TLS段数据，则标记为跨包消息片段
                protocol_types = frame_protocol_types.get(frame_num_int, [])
                tls_segment_data = layers.get("tls.segment.data")

                # 如果没有协议类型但有TLS段数据，说明这是跨包消息的片段
                if not protocol_types and tls_segment_data is not None:
                    # 通过分析TLS段数据的头部来确定消息类型
                    try:
                        segment_data_hex = tls_segment_data[0] if isinstance(tls_segment_data, list) else tls_segment_data
                        if segment_data_hex and len(segment_data_hex) >= 2:
                            # TLS记录的第一个字节是内容类型
                            content_type_byte = int(segment_data_hex[:2], 16)
                            if content_type_byte in TLS_CONTENT_TYPES:
                                protocol_types = [content_type_byte]
                    except (ValueError, TypeError, IndexError):
                        # 如果无法解析，标记为未知TLS段
                        protocol_types = [-1]  # 使用-1表示TLS段数据但类型未知

                frame_info = {
                    "frame": frame_num_int,
                    "protocol_layers": protocol_layers.get(frame_num_int, []),
                    "protocol_types": protocol_types,
                    "tcp_stream": self._get_first_value(layers.get("tcp.stream")),
                    "src_ip": (self._get_first_value(layers.get("ip.src")) or
                              self._get_first_value(layers.get("ipv6.src"))),
                    "dst_ip": (self._get_first_value(layers.get("ip.dst")) or
                              self._get_first_value(layers.get("ipv6.dst"))),
                    "src_port": self._get_first_value(layers.get("tcp.srcport")),
                    "dst_port": self._get_first_value(layers.get("tcp.dstport")),
                    "tcp_seq": self._get_first_value(layers.get("tcp.seq")),  # 相对序列号
                    "tcp_seq_raw": self._get_first_value(layers.get("tcp.seq_raw")),  # 绝对序列号
                    "tcp_len": self._get_first_value(layers.get("tcp.len")),
                    "time_relative": self._get_first_value(layers.get("frame.time_relative"))
                }

                # 如果是TLS段数据包，添加特殊标记
                if tls_segment_data is not None:
                    frame_info["is_tls_segment"] = True
                    frame_info["tls_segment_data_length"] = len(tls_segment_data[0]) // 2 if isinstance(tls_segment_data, list) and tls_segment_data else 0

                detailed_frames.append(frame_info)

        # 构建最终结果
        result = {
            "metadata": {
                "analysis_timestamp": time.time(),
                "total_frames_with_tls": total_frames,
                "total_tls_records": total_records,
                "total_tcp_streams": total_tcp_streams,
                "tls_content_types": TLS_CONTENT_TYPES,
                "processing_strategies": TLS_PROCESSING_STRATEGIES
            },
            "global_statistics": {
                "frames_containing_tls": total_frames,
                "tls_records_total": total_records,
                "tcp_streams_analyzed": total_tcp_streams
            },
            "protocol_type_statistics": dict(protocol_type_stats),
            "detailed_frames": detailed_frames,
            "reassembled_messages": reassembled_messages,
            "tcp_flow_analysis": {
                stream_id: {
                    "packet_count": flow_info["packet_count"],
                    "directions": {
                        direction: {
                            "src_ip": dir_info["src_ip"],
                            "dst_ip": dir_info["dst_ip"],
                            "src_port": dir_info["src_port"],
                            "dst_port": dir_info["dst_port"],
                            "packet_count": len(dir_info["packets"]),
                            "payload_size": len(flow_info["reassembled_payloads"][direction])
                        }
                        for direction, dir_info in flow_info["directions"].items()
                    }
                }
                for stream_id, flow_info in tcp_flows.items()
            }
        }

        return result


def _build_arg_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="tls_flow_analyzer",
        description="TLS 流量分析工具 - 全面的 TLS 协议流量分析器",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # 输入选项：支持单个文件或目录
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--pcap", help="待分析的 pcap/pcapng 文件路径")
    input_group.add_argument("--input-dir", type=Path, help="待分析的目录路径，将处理目录下所有 pcap/pcapng 文件")

    parser.add_argument(
        "--decode-as",
        action="append",
        dest="decode_as",
        metavar="PORT,PROTO",
        help="额外端口解码，格式如 8443,tls，可多次指定",
    )
    parser.add_argument(
        "--formats",
        default="json,tsv",
        help="输出格式，逗号分隔，可选 json,tsv,html",
    )
    parser.add_argument(
        "--tshark-path",
        help="自定义 tshark 可执行文件路径 (默认从 PATH 搜索)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="结果文件输出目录 (默认与输入文件同目录)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="启用详细模式，输出更多分析信息"
    )
    parser.add_argument(
        "--filter-types",
        default="20,21,22,23,24",
        help="过滤特定的 TLS 协议类型，逗号分隔 (默认: 20,21,22,23,24)"
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="仅输出统计摘要，不生成详细文件"
    )
    parser.add_argument(
        "--no-tcp-reassembly",
        action="store_true",
        help="禁用 TCP 重组分析，仅分析单个数据包"
    )
    parser.add_argument(
        "--generate-summary-html",
        action="store_true",
        help="批量处理时生成汇总 HTML 报告（包含所有文件的分析结果）"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="输出调试信息"
    )

    return parser


def _find_pcap_files(input_dir: Path) -> List[Path]:
    """Find all pcap/pcapng files in directory"""
    pcap_extensions = {'.pcap', '.pcapng', '.cap'}
    pcap_files = []

    for ext in pcap_extensions:
        pcap_files.extend(input_dir.glob(f"*{ext}"))
        pcap_files.extend(input_dir.glob(f"*{ext.upper()}"))

    # Sort by filename
    return sorted(pcap_files)


def _process_batch_files(pcap_files: List[Path], analyzer: 'TLSFlowAnalyzer',
                        tshark_path: Optional[str], decode_as: Optional[List[str]],
                        filter_types: Optional[Set[int]], output_dir: Optional[Path],
                        formats: str, verbose: bool, detailed: bool,
                        summary_only: bool) -> Dict[str, Dict[str, Any]]:
    """Batch process multiple pcap files"""
    batch_results = {}
    total_files = len(pcap_files)

    print(f"[tls-flow-analyzer] Starting batch processing of {total_files} files...")

    for i, pcap_file in enumerate(pcap_files, 1):
        print(f"[tls-flow-analyzer] Processing file {i}/{total_files}: {pcap_file.name}")

        try:
            # 分析单个文件
            analysis_result = analyzer.analyze_pcap(
                pcap_path=str(pcap_file),
                tshark_path=tshark_path,
                decode_as=decode_as
            )

            # 应用类型过滤
            if filter_types:
                analysis_result = _apply_type_filter(analysis_result, filter_types)

            # 存储结果
            batch_results[str(pcap_file)] = analysis_result

            # 输出单个文件的结果（除非仅输出摘要）
            if not summary_only:
                _output_results(
                    analysis_result=analysis_result,
                    pcap_path=str(pcap_file),
                    output_dir=output_dir,
                    formats=formats,
                    verbose=verbose,
                    detailed=detailed
                )

            # 打印单个文件的简要摘要
            if verbose:
                global_stats = analysis_result["global_statistics"]
                print(f"  ✅ {pcap_file.name}: {global_stats['frames_containing_tls']} frames, "
                     f"{global_stats['tls_records_total']} records, "
                     f"{global_stats['tcp_streams_analyzed']} streams")

        except Exception as e:
            print(f"  ❌ {pcap_file.name}: Analysis failed - {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            continue

    print(f"[tls-flow-analyzer] Batch processing completed, successfully processed {len(batch_results)}/{total_files} files")
    return batch_results


def _generate_summary_html_report(batch_results: Dict[str, Dict[str, Any]],
                                 output_dir: Path, verbose: bool) -> None:
    """Generate summary HTML report"""
    if not JINJA2_AVAILABLE:
        print(f"[tls-flow-analyzer] ⚠️  Jinja2 not installed, skipping summary HTML output")
        return

    if not batch_results:
        print(f"[tls-flow-analyzer] ⚠️  No successfully analyzed files, skipping summary HTML output")
        return

    try:
        # 直接使用内置的汇总模板内容
        template_content = _create_summary_template_content()
        template = Template(template_content)

        # 准备汇总数据
        summary_data = _prepare_summary_data(batch_results)

        # 渲染HTML
        html_content = template.render(**summary_data)

        # 输出汇总HTML文件
        summary_html_path = output_dir / "tls_flow_analysis_summary.html"
        with summary_html_path.open("w", encoding="utf-8") as f:
            f.write(html_content)

        if verbose:
            print(f"[tls-flow-analyzer] Summary HTML output: {summary_html_path}")

    except Exception as e:
        print(f"[tls-flow-analyzer] ⚠️  Failed to generate summary HTML: {e}")
        if verbose:
            import traceback
            traceback.print_exc()


def _prepare_summary_data(batch_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """准备汇总数据"""
    # 汇总统计
    total_files = len(batch_results)
    total_frames = 0
    total_records = 0
    total_streams = 0

    # 按文件组织的数据
    file_summaries = []

    # 全局协议类型统计
    global_protocol_stats = defaultdict(lambda: {"frames": 0, "records": 0})

    for pcap_path, result in batch_results.items():
        pcap_name = Path(pcap_path).name
        global_stats = result["global_statistics"]
        protocol_stats = result["protocol_type_statistics"]

        # 累计全局统计
        total_frames += global_stats["frames_containing_tls"]
        total_records += global_stats["tls_records_total"]
        total_streams += global_stats["tcp_streams_analyzed"]

        # 累计协议类型统计
        for content_type, stats in protocol_stats.items():
            global_protocol_stats[content_type]["frames"] += stats["frames"]
            global_protocol_stats[content_type]["records"] += stats["records"]

        # 生成详细HTML文件的链接路径
        pcap_stem = Path(pcap_name).stem  # 去掉扩展名
        detail_html_filename = f"{pcap_stem}_tls_flow_analysis.html"

        # 准备单个文件的摘要
        file_summary = {
            "pcap_name": pcap_name,
            "pcap_path": pcap_path,
            "detail_html_link": detail_html_filename,
            "analysis_timestamp": datetime.fromtimestamp(
                result["metadata"]["analysis_timestamp"]
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "global_statistics": global_stats,
            "protocol_type_statistics": protocol_stats,
            "detailed_frames": result["detailed_frames"],
            "reassembled_messages": result.get("reassembled_messages", []),
            "tcp_flow_analysis": result.get("tcp_flow_analysis", {})
        }

        file_summaries.append(file_summary)

    # 按文件名排序
    file_summaries.sort(key=lambda x: x["pcap_name"])

    return {
        "summary_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": total_files,
        "global_summary": {
            "total_frames_containing_tls": total_frames,
            "total_tls_records": total_records,
            "total_tcp_streams": total_streams
        },
        "global_protocol_type_statistics": dict(global_protocol_stats),
        "file_summaries": file_summaries,
        "tls_content_types": TLS_CONTENT_TYPES,
        "processing_strategies": TLS_PROCESSING_STRATEGIES
    }


def _create_summary_template_content() -> str:
    """创建汇总HTML模板内容"""
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TLS 流量分析汇总报告</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1, h2, h3 { color: #2c3e50; }
        h1 { border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; margin-top: 30px; }
        .summary-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; margin-bottom: 5px; }
        .stat-label { font-size: 0.9em; opacity: 0.9; }
        .file-section { margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; background: #fafafa; }
        .file-header { background: #34495e; color: white; padding: 15px; margin: -20px -20px 20px -20px; border-radius: 8px 8px 0 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
        .file-title-section { flex: 1; min-width: 300px; }
        .file-link-section { flex-shrink: 0; margin-left: 15px; }
        .detail-link {
            display: inline-flex;
            align-items: center;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 500;
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        .detail-link:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
            text-decoration: none;
            color: white;
        }
        .detail-link:visited { color: white; }
        .detail-link-icon { margin-right: 6px; font-size: 1.1em; }
        .protocol-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 15px 0; }
        .protocol-card { background: white; border: 1px solid #ddd; padding: 15px; border-radius: 6px; text-align: center; }
        .protocol-type-20 { border-left: 4px solid #e74c3c; }
        .protocol-type-21 { border-left: 4px solid #f39c12; }
        .protocol-type-22 { border-left: 4px solid #2ecc71; }
        .protocol-type-23 { border-left: 4px solid #3498db; }
        .protocol-type-24 { border-left: 4px solid #9b59b6; }
        .frames-table { width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 0.9em; }
        .frames-table th, .frames-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .frames-table th { background: #f8f9fa; font-weight: bold; }
        .frames-table tr:nth-child(even) { background: #f8f9fa; }
        .collapsible { cursor: pointer; padding: 10px; background: #ecf0f1; border: none; width: 100%; text-align: left; font-weight: bold; }
        .collapsible:hover { background: #d5dbdb; }
        .content { display: none; padding: 15px; border: 1px solid #ddd; border-top: none; }
        .timestamp { color: #7f8c8d; font-size: 0.9em; }

        /* 响应式设计 */
        @media (max-width: 768px) {
            .file-header { flex-direction: column; align-items: flex-start; }
            .file-link-section { margin-left: 0; margin-top: 10px; }
            .file-title-section { min-width: auto; }
            .detail-link { font-size: 0.8em; padding: 6px 12px; }
        }

        @media (max-width: 480px) {
            .container { margin: 10px; padding: 15px; }
            .summary-stats { grid-template-columns: 1fr; }
            .protocol-stats { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 TLS 流量分析汇总报告</h1>
        <p class="timestamp">生成时间: {{ summary_timestamp }}</p>

        <h2>📊 全局统计</h2>
        <div class="summary-stats">
            <div class="stat-card">
                <div class="stat-value">{{ total_files }}</div>
                <div class="stat-label">分析文件数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ global_summary.total_frames_containing_tls }}</div>
                <div class="stat-label">TLS 数据帧总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ global_summary.total_tls_records }}</div>
                <div class="stat-label">TLS 记录总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ global_summary.total_tcp_streams }}</div>
                <div class="stat-label">TCP 流总数</div>
            </div>
        </div>

        <h2>🔍 全局协议类型统计</h2>
        <div class="protocol-stats">
            {% for content_type, stats in global_protocol_type_statistics.items() %}
            <div class="protocol-card protocol-type-{{ content_type }}">
                <strong>TLS-{{ content_type }}</strong><br>
                <small>{{ tls_content_types[content_type] }}</small><br>
                <div style="margin-top: 10px;">
                    <div>{{ stats.frames }} 帧</div>
                    <div>{{ stats.records }} 记录</div>
                </div>
            </div>
            {% endfor %}
        </div>

        <h2>📁 各文件分析结果</h2>
        {% for file_summary in file_summaries %}
        <div class="file-section">
            <div class="file-header">
                <div class="file-title-section">
                    <h3 style="margin: 0; color: white;">📄 {{ file_summary.pcap_name }}</h3>
                    <p style="margin: 5px 0 0 0; opacity: 0.8;">分析时间: {{ file_summary.analysis_timestamp }}</p>
                </div>
                <div class="file-link-section">
                    <a href="{{ file_summary.detail_html_link }}"
                       target="_blank"
                       class="detail-link"
                       title="在新标签页中查看 {{ file_summary.pcap_name }} 的详细分析报告">
                        <span class="detail-link-icon">🔍</span>
                        查看详情
                    </a>
                </div>
            </div>

            <div class="summary-stats">
                <div class="stat-card" style="background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);">
                    <div class="stat-value">{{ file_summary.global_statistics.frames_containing_tls }}</div>
                    <div class="stat-label">TLS 数据帧</div>
                </div>
                <div class="stat-card" style="background: linear-gradient(135deg, #fd79a8 0%, #e84393 100%);">
                    <div class="stat-value">{{ file_summary.global_statistics.tls_records_total }}</div>
                    <div class="stat-label">TLS 记录</div>
                </div>
                <div class="stat-card" style="background: linear-gradient(135deg, #fdcb6e 0%, #e17055 100%);">
                    <div class="stat-value">{{ file_summary.global_statistics.tcp_streams_analyzed }}</div>
                    <div class="stat-label">TCP 流</div>
                </div>
            </div>

            <button class="collapsible" onclick="toggleContent(this)">📋 详细数据帧信息 ({{ file_summary.detailed_frames|length }} 帧)</button>
            <div class="content">
                <table class="frames-table">
                    <thead>
                        <tr>
                            <th>帧号</th>
                            <th>协议栈</th>
                            <th>TLS类型</th>
                            <th>TCP流</th>
                            <th>源地址</th>
                            <th>目标地址</th>
                            <th>TCP长度</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for frame in file_summary.detailed_frames[:50] %}
                        <tr>
                            <td>{{ frame.frame }}</td>
                            <td>{{ frame.protocol_layers|join(':') }}</td>
                            <td>
                                {% for ptype in frame.protocol_types %}
                                    {% if ptype in tls_content_types %}
                                        <span class="protocol-type-{{ ptype }}">TLS-{{ ptype }}</span>
                                    {% else %}
                                        <span>{{ ptype }}</span>
                                    {% endif %}
                                {% endfor %}
                            </td>
                            <td>{{ frame.tcp_stream }}</td>
                            <td>{{ frame.src_ip }}:{{ frame.src_port }}</td>
                            <td>{{ frame.dst_ip }}:{{ frame.dst_port }}</td>
                            <td>{{ frame.tcp_len }}</td>
                        </tr>
                        {% endfor %}
                        {% if file_summary.detailed_frames|length > 50 %}
                        <tr><td colspan="7" style="text-align: center; font-style: italic;">... 还有 {{ file_summary.detailed_frames|length - 50 }} 帧 (详见单独的分析文件)</td></tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        function toggleContent(element) {
            var content = element.nextElementSibling;
            if (content.style.display === "block") {
                content.style.display = "none";
            } else {
                content.style.display = "block";
            }
        }
    </script>
</body>
</html>'''


def _generate_detailed_message_analysis(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """生成详细的 TLS 消息结构分析"""
    detailed_analysis = {
        "message_structure_analysis": [],
        "cross_segment_analysis": [],
        "sequence_analysis": {}
    }

    # 分析重组的消息
    for message in analysis_result["reassembled_messages"]:
        message_analysis = {
            "stream_id": message["stream_id"],
            "direction": message["direction"],
            "content_type": message["content_type"],
            "content_type_name": message["content_type_name"],
            "version": message["version"],
            "version_string": _get_tls_version_string(message["version"]),
            "header_info": {
                "start_position": message["header_start"],
                "end_position": message["header_end"],
                "length": message["header_end"] - message["header_start"],
                # 新增：头部序列号范围
                "seq_start": message.get("tls_header_seq_start", message["tls_seq_start"]),
                "seq_end": message.get("tls_header_seq_end", message["tls_seq_start"] + 5)
            },
            "payload_info": {
                "start_position": message["payload_start"],
                "end_position": message["payload_end"],
                "length": message["payload_end"] - message["payload_start"],
                "declared_length": message["length"],
                # 新增：载荷序列号范围
                "seq_start": message.get("tls_payload_seq_start", message["tls_seq_start"] + 5),
                "seq_end": message.get("tls_payload_seq_end", message["tls_seq_end"])
            },
            "is_complete": message["is_complete"],
            "is_cross_segment": message["is_cross_segment"],
            "processing_strategy": message["processing_strategy"]
        }

        detailed_analysis["message_structure_analysis"].append(message_analysis)

        # 如果是跨段消息，添加到跨段分析
        if message["is_cross_segment"]:
            detailed_analysis["cross_segment_analysis"].append(message_analysis)

    # 按 TCP 流分组分析序列
    tcp_flows = analysis_result["tcp_flow_analysis"]
    for stream_id, flow_info in tcp_flows.items():
        detailed_analysis["sequence_analysis"][stream_id] = {
            "total_packets": flow_info["packet_count"],
            "directions": {}
        }

        for direction, dir_info in flow_info["directions"].items():
            detailed_analysis["sequence_analysis"][stream_id]["directions"][direction] = {
                "endpoint": f"{dir_info['src_ip']}:{dir_info['src_port']} -> {dir_info['dst_ip']}:{dir_info['dst_port']}",
                "packet_count": dir_info["packet_count"],
                "payload_size": dir_info["payload_size"]
            }

    return detailed_analysis


def _get_tls_version_string(version: Tuple[int, int]) -> str:
    """获取 TLS 版本字符串"""
    major, minor = version
    if major == 3:
        if minor == 0:
            return "SSL 3.0"
        elif minor == 1:
            return "TLS 1.0"
        elif minor == 2:
            return "TLS 1.1"
        elif minor == 3:
            return "TLS 1.2"
        elif minor == 4:
            return "TLS 1.3"
    return f"TLS {major}.{minor}"


def _output_results(analysis_result: Dict[str, Any], pcap_path: str,
                   output_dir: Optional[Path], formats: str, verbose: bool, detailed: bool = False) -> None:
    """输出分析结果到文件"""
    # 设置输出目录
    if output_dir is None:
        output_dir = Path(pcap_path).parent
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    pcap_stem = Path(pcap_path).stem
    formats_list = [f.strip().lower() for f in formats.split(",")]

    # 如果启用详细模式，添加详细分析
    if detailed:
        detailed_analysis = _generate_detailed_message_analysis(analysis_result)
        analysis_result["detailed_analysis"] = detailed_analysis

    # JSON 输出
    if "json" in formats_list:
        json_path = output_dir / f"{pcap_stem}_tls_flow_analysis.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2, default=str)

        if verbose:
            print(f"[tls-flow-analyzer] JSON output: {json_path}")

        # 如果启用详细模式，额外输出详细分析文件
        if detailed:
            detailed_json_path = output_dir / f"{pcap_stem}_tls_detailed_analysis.json"
            with detailed_json_path.open("w", encoding="utf-8") as f:
                json.dump(detailed_analysis, f, ensure_ascii=False, indent=2, default=str)

            if verbose:
                print(f"[tls-flow-analyzer] Detailed analysis JSON output: {detailed_json_path}")

    # TSV 输出
    if "tsv" in formats_list:
        tsv_path = output_dir / f"{pcap_stem}_tls_flow_analysis.tsv"
        with tsv_path.open("w", encoding="utf-8") as f:
            # 写入表头
            f.write("frame\tprotocol_layers\tprotocol_types\tprotocol_type_names\ttcp_stream\tsrc_ip\tdst_ip\tsrc_port\tdst_port\ttcp_seq\ttcp_len\ttime_relative\tprocessing_strategies\n")

            # 写入详细帧信息
            for frame_info in analysis_result["detailed_frames"]:
                protocol_layers_str = ":".join(frame_info.get("protocol_layers", []))
                protocol_types_str = ",".join(map(str, frame_info.get("protocol_types", [])))

                # 生成协议类型名称和处理策略
                protocol_type_names = []
                processing_strategies = []
                for ptype in frame_info.get("protocol_types", []):
                    protocol_type_names.append(TLS_CONTENT_TYPES.get(ptype, f"Unknown-{ptype}"))
                    processing_strategies.append(TLS_PROCESSING_STRATEGIES.get(ptype, "unknown"))

                protocol_type_names_str = ",".join(protocol_type_names)
                processing_strategies_str = ",".join(processing_strategies)

                f.write(f"{frame_info.get('frame', '')}\t"
                       f"{protocol_layers_str}\t"
                       f"{protocol_types_str}\t"
                       f"{protocol_type_names_str}\t"
                       f"{frame_info.get('tcp_stream', '')}\t"
                       f"{frame_info.get('src_ip', '')}\t"
                       f"{frame_info.get('dst_ip', '')}\t"
                       f"{frame_info.get('src_port', '')}\t"
                       f"{frame_info.get('dst_port', '')}\t"
                       f"{frame_info.get('tcp_seq', '')}\t"
                       f"{frame_info.get('tcp_len', '')}\t"
                       f"{frame_info.get('time_relative', '')}\t"
                       f"{processing_strategies_str}\n")

        if verbose:
            print(f"[tls-flow-analyzer] TSV output: {tsv_path}")

        # 如果启用详细模式，输出消息结构分析 TSV
        if detailed and "detailed_analysis" in analysis_result:
            detailed_tsv_path = output_dir / f"{pcap_stem}_tls_message_structure.tsv"
            with detailed_tsv_path.open("w", encoding="utf-8") as f:
                f.write("stream_id\tdirection\tcontent_type\tcontent_type_name\tversion_string\t"
                       f"header_start\theader_end\theader_length\theader_seq_start\theader_seq_end\t"
                       f"payload_start\tpayload_end\tpayload_length\tpayload_seq_start\tpayload_seq_end\t"
                       f"declared_length\tis_complete\tis_cross_segment\tprocessing_strategy\n")

                for msg in analysis_result["detailed_analysis"]["message_structure_analysis"]:
                    f.write(f"{msg['stream_id']}\t"
                           f"{msg['direction']}\t"
                           f"{msg['content_type']}\t"
                           f"{msg['content_type_name']}\t"
                           f"{msg['version_string']}\t"
                           f"{msg['header_info']['start_position']}\t"
                           f"{msg['header_info']['end_position']}\t"
                           f"{msg['header_info']['length']}\t"
                           f"{msg['header_info']['seq_start']}\t"
                           f"{msg['header_info']['seq_end']}\t"
                           f"{msg['payload_info']['start_position']}\t"
                           f"{msg['payload_info']['end_position']}\t"
                           f"{msg['payload_info']['length']}\t"
                           f"{msg['payload_info']['seq_start']}\t"
                           f"{msg['payload_info']['seq_end']}\t"
                           f"{msg['payload_info']['declared_length']}\t"
                           f"{msg['is_complete']}\t"
                           f"{msg['is_cross_segment']}\t"
                           f"{msg['processing_strategy']}\n")

            if verbose:
                print(f"[tls-flow-analyzer] Message structure TSV output: {detailed_tsv_path}")

    # HTML 输出
    if "html" in formats_list:
        _output_html_report(analysis_result, pcap_path, output_dir, pcap_stem, verbose)


def _output_html_report(analysis_result: Dict[str, Any], pcap_path: str,
                       output_dir: Path, pcap_stem: str, verbose: bool) -> None:
    """Generate HTML format analysis report"""
    if not JINJA2_AVAILABLE:
        print(f"[tls-flow-analyzer] ⚠️  Jinja2 not installed, skipping HTML output")
        return

    try:
        # 加载HTML模板
        template_path = resource_path('tls_flow_analysis_template.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        template = Template(template_content)

        # 准备模板数据
        template_data = {
            "pcap_name": Path(pcap_path).name,
            "analysis_timestamp": datetime.fromtimestamp(
                analysis_result["metadata"]["analysis_timestamp"]
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "global_statistics": analysis_result["global_statistics"],
            "protocol_type_statistics": analysis_result["protocol_type_statistics"],
            "tcp_flow_analysis": analysis_result["tcp_flow_analysis"],
            "detailed_frames": analysis_result["detailed_frames"],
            "reassembled_messages": analysis_result["reassembled_messages"],
            "tls_content_types": analysis_result["metadata"]["tls_content_types"],
            "processing_strategies": analysis_result["metadata"]["processing_strategies"]
        }

        # 渲染HTML
        html_content = template.render(**template_data)

        # 保存HTML文件
        html_path = output_dir / f"{pcap_stem}_tls_flow_analysis.html"
        with html_path.open("w", encoding="utf-8") as f:
            f.write(html_content)

        if verbose:
            print(f"[tls-flow-analyzer] HTML output: {html_path}")

    except Exception as e:
        print(f"[tls-flow-analyzer] ⚠️  HTML report generation failed: {e}")


def _apply_type_filter(analysis_result: Dict[str, Any], filter_types: Set[int]) -> Dict[str, Any]:
    """Apply TLS protocol type filtering"""
    # 过滤详细帧信息
    filtered_frames = []
    for frame in analysis_result["detailed_frames"]:
        frame_types = frame.get("protocol_types", [])
        if any(ptype in filter_types for ptype in frame_types):
            # 只保留匹配的协议类型
            filtered_protocol_types = [ptype for ptype in frame_types if ptype in filter_types]
            filtered_frame = frame.copy()
            filtered_frame["protocol_types"] = filtered_protocol_types
            filtered_frames.append(filtered_frame)

    # 过滤协议类型统计
    filtered_protocol_stats = {}
    for ptype, stats in analysis_result["protocol_type_statistics"].items():
        if ptype in filter_types:
            filtered_protocol_stats[ptype] = stats

    # 过滤重组消息
    filtered_messages = []
    for message in analysis_result["reassembled_messages"]:
        if message["content_type"] in filter_types:
            filtered_messages.append(message)

    # 更新结果
    filtered_result = analysis_result.copy()
    filtered_result["detailed_frames"] = filtered_frames
    filtered_result["protocol_type_statistics"] = filtered_protocol_stats
    filtered_result["reassembled_messages"] = filtered_messages

    # 更新全局统计
    filtered_result["global_statistics"]["frames_containing_tls"] = len(filtered_frames)
    filtered_result["global_statistics"]["tls_records_total"] = len(filtered_messages)
    filtered_result["metadata"]["total_frames_with_tls"] = len(filtered_frames)
    filtered_result["metadata"]["total_tls_records"] = len(filtered_messages)

    return filtered_result


def _print_summary(analysis_result: Dict[str, Any], detailed: bool) -> None:
    """Print analysis result summary"""
    metadata = analysis_result["metadata"]
    global_stats = analysis_result["global_statistics"]
    protocol_stats = analysis_result["protocol_type_statistics"]

    print(f"[tls-flow-analyzer] ✅ TLS traffic analysis completed")
    print(f"  Total frames containing TLS messages: {global_stats['frames_containing_tls']}")
    print(f"  Total TLS records: {global_stats['tls_records_total']}")
    print(f"  Total TCP streams analyzed: {global_stats['tcp_streams_analyzed']}")

    print(f"\n  Statistics by TLS message type:")
    for content_type in sorted(protocol_stats.keys()):
        type_name = TLS_CONTENT_TYPES[content_type]
        strategy = TLS_PROCESSING_STRATEGIES[content_type]
        frames = protocol_stats[content_type]["frames"]
        records = protocol_stats[content_type]["records"]
        print(f"    TLS-{content_type} ({type_name}, {strategy}): {frames} frames, {records} records")

    if detailed:
        print(f"\n  TCP flow analysis details:")
        tcp_flow_analysis = analysis_result["tcp_flow_analysis"]
        for stream_id, flow_info in tcp_flow_analysis.items():
            print(f"    TCP stream {stream_id}: {flow_info['packet_count']} packets")
            for direction, dir_info in flow_info["directions"].items():
                print(f"      {direction}: {dir_info['src_ip']}:{dir_info['src_port']} -> "
                     f"{dir_info['dst_ip']}:{dir_info['dst_port']} "
                     f"({dir_info['packet_count']} packets, {dir_info['payload_size']} bytes payload)")

        # Display reassembled message details
        reassembled_messages = analysis_result.get("reassembled_messages", [])
        if reassembled_messages:
            print(f"\n  Reassembled TLS message details ({len(reassembled_messages)} messages):")
            for i, message in enumerate(reassembled_messages[:10]):  # Limit display to first 10 messages
                content_type_name = message.get("content_type_name", "Unknown")
                stream_id = message.get("stream_id", "unknown")
                direction = message.get("direction", "unknown")
                length = message.get("length", 0)

                # 获取头部和载荷序列号范围
                header_seq_start = message.get("tls_header_seq_start", message.get("tls_seq_start", 0))
                header_seq_end = message.get("tls_header_seq_end", header_seq_start + 5)
                payload_seq_start = message.get("tls_payload_seq_start", header_seq_end)
                payload_seq_end = message.get("tls_payload_seq_end", message.get("tls_seq_end", payload_seq_start))

                is_complete = "✓" if message.get("is_complete", False) else "⚠"
                is_cross_segment = "cross-segment" if message.get("is_cross_segment", False) else "single-segment"

                print(f"    [{i+1:2d}] stream{stream_id}-{direction} {content_type_name} ({length}bytes) {is_complete} {is_cross_segment}")
                print(f"         Header sequence: {header_seq_start}-{header_seq_end}")
                print(f"         Payload sequence: {payload_seq_start}-{payload_seq_end}")

            if len(reassembled_messages) > 10:
                print(f"    ... {len(reassembled_messages) - 10} more messages (see output files for details)")
        else:
            print(f"\n  No reassembled TLS messages")


def _print_batch_summary(batch_results: Dict[str, Dict[str, Any]], detailed: bool) -> None:
    """Print batch processing summary"""
    total_files = len(batch_results)
    if total_files == 0:
        print(f"[tls-flow-analyzer] ❌ No successfully analyzed files")
        return

    # Summary statistics
    total_frames = 0
    total_records = 0
    total_streams = 0
    global_protocol_stats = defaultdict(lambda: {"frames": 0, "records": 0})

    for pcap_path, result in batch_results.items():
        global_stats = result["global_statistics"]
        protocol_stats = result["protocol_type_statistics"]

        total_frames += global_stats["frames_containing_tls"]
        total_records += global_stats["tls_records_total"]
        total_streams += global_stats["tcp_streams_analyzed"]

        for content_type, stats in protocol_stats.items():
            global_protocol_stats[content_type]["frames"] += stats["frames"]
            global_protocol_stats[content_type]["records"] += stats["records"]

    print(f"[tls-flow-analyzer] ✅ Batch TLS traffic analysis completed")
    print(f"  Successfully analyzed files: {total_files}")
    print(f"  Total frames containing TLS messages: {total_frames}")
    print(f"  Total TLS records: {total_records}")
    print(f"  Total TCP streams analyzed: {total_streams}")

    print(f"\n  Global TLS message type statistics:")
    for content_type in sorted(global_protocol_stats.keys()):
        type_name = TLS_CONTENT_TYPES[content_type]
        strategy = TLS_PROCESSING_STRATEGIES[content_type]
        frames = global_protocol_stats[content_type]["frames"]
        records = global_protocol_stats[content_type]["records"]
        print(f"    TLS-{content_type} ({type_name}, {strategy}): {frames} frames, {records} records")

    if detailed:
        print(f"\n  Detailed statistics by file:")
        for pcap_path, result in batch_results.items():
            pcap_name = Path(pcap_path).name
            global_stats = result["global_statistics"]
            print(f"    📄 {pcap_name}: {global_stats['frames_containing_tls']} frames, "
                 f"{global_stats['tls_records_total']} records, "
                 f"{global_stats['tcp_streams_analyzed']} streams")


def main(argv: Optional[List[str]] = None) -> None:
    """主函数"""
    argv = argv if argv is not None else sys.argv[1:]
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        # 解析过滤类型
        filter_types = None
        if args.filter_types:
            try:
                filter_types = set(int(t.strip()) for t in args.filter_types.split(",") if t.strip())
                # Validate protocol type range
                invalid_types = filter_types - set(TLS_CONTENT_TYPES.keys())
                if invalid_types:
                    print(f"[tls-flow-analyzer] Error: Invalid TLS protocol types: {invalid_types}", file=sys.stderr)
                    sys.exit(1)
            except ValueError as e:
                print(f"[tls-flow-analyzer] Error: Unable to parse protocol types '{args.filter_types}': {e}", file=sys.stderr)
                sys.exit(1)

        # Create analyzer
        analyzer = TLSFlowAnalyzer(verbose=args.verbose)

        # 设置输出目录
        if args.output_dir is None:
            if args.pcap:
                args.output_dir = Path(args.pcap).parent
            elif args.input_dir:
                args.output_dir = args.input_dir
        else:
            args.output_dir.mkdir(parents=True, exist_ok=True)

        # 判断是单文件处理还是批量处理
        if args.pcap:
            # 单文件处理
            analysis_result = analyzer.analyze_pcap(
                pcap_path=args.pcap,
                tshark_path=args.tshark_path,
                decode_as=args.decode_as
            )

            # 应用类型过滤
            if filter_types:
                analysis_result = _apply_type_filter(analysis_result, filter_types)

            # 输出结果（除非仅输出摘要）
            if not args.summary_only:
                _output_results(
                    analysis_result=analysis_result,
                    pcap_path=args.pcap,
                    output_dir=args.output_dir,
                    formats=args.formats,
                    verbose=args.verbose,
                    detailed=args.detailed
                )

            # 打印摘要
            _print_summary(analysis_result, args.detailed)

        elif args.input_dir:
            # Batch processing
            if not args.input_dir.exists():
                print(f"[tls-flow-analyzer] Error: Input directory does not exist: {args.input_dir}", file=sys.stderr)
                sys.exit(1)

            if not args.input_dir.is_dir():
                print(f"[tls-flow-analyzer] Error: Input path is not a directory: {args.input_dir}", file=sys.stderr)
                sys.exit(1)

            # Find pcap files
            pcap_files = _find_pcap_files(args.input_dir)
            if not pcap_files:
                print(f"[tls-flow-analyzer] Error: No pcap/pcapng files found in directory {args.input_dir}", file=sys.stderr)
                sys.exit(1)

            # Batch process files
            batch_results = _process_batch_files(
                pcap_files=pcap_files,
                analyzer=analyzer,
                tshark_path=args.tshark_path,
                decode_as=args.decode_as,
                filter_types=filter_types,
                output_dir=args.output_dir,
                formats=args.formats,
                verbose=args.verbose,
                detailed=args.detailed,
                summary_only=args.summary_only
            )

            # 生成汇总HTML报告
            if args.generate_summary_html:
                _generate_summary_html_report(batch_results, args.output_dir, args.verbose)

            # Print batch processing summary
            _print_batch_summary(batch_results, args.detailed)

    except Exception as e:
        print(f"[tls-flow-analyzer] ❌ Analysis failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
