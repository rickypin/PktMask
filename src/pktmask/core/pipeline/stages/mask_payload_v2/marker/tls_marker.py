"""
TLS协议标记器

基于 tls_flow_analyzer 代码逻辑的TLS协议分析器，生成TCP序列号保留规则。
复用核心算法而非直接依赖，保持工具与主程序的独立性。
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import ProtocolMarker
from .types import KeepRule, KeepRuleSet, FlowInfo


# TLS协议类型映射（复用自tls_flow_analyzer）
TLS_CONTENT_TYPES = {
    20: "ChangeCipherSpec",
    21: "Alert",
    22: "Handshake",
    23: "ApplicationData",
    24: "Heartbeat"
}

# TLS处理策略映射（复用自tls_flow_analyzer）
TLS_PROCESSING_STRATEGIES = {
    20: "keep_all",      # ChangeCipherSpec - 完全保留
    21: "keep_all",      # Alert - 完全保留
    22: "keep_all",      # Handshake - 完全保留
    23: "mask_payload",  # ApplicationData - 智能掩码(保留5字节头部)
    24: "keep_all"       # Heartbeat - 完全保留
}

# 最小tshark版本要求
MIN_TSHARK_VERSION: Tuple[int, int, int] = (4, 2, 0)


class TLSProtocolMarker(ProtocolMarker):
    """TLS协议标记器

    复用 tls_flow_analyzer 的核心分析逻辑，生成TLS消息保留规则。
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化TLS协议标记器

        Args:
            config: TLS特定配置
        """
        super().__init__(config)

        # TLS保留策略配置 - 支持多种配置格式
        if 'preserve' in config:
            # GUI格式：直接使用preserve配置
            self.preserve_config = config['preserve']
        elif 'tls' in config:
            # 脚本格式：转换tls配置到内部格式
            tls_config = config['tls']
            self.preserve_config = {
                'handshake': tls_config.get('preserve_handshake', True),
                'application_data': tls_config.get('preserve_application_data', False),
                'alert': tls_config.get('preserve_alert', True),
                'change_cipher_spec': tls_config.get('preserve_change_cipher_spec', True),
                'heartbeat': tls_config.get('preserve_heartbeat', True)
            }
        else:
            # 默认配置
            self.preserve_config = {
                'handshake': True,
                'application_data': False,
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }

        # tshark配置
        self.tshark_path = config.get('tshark_path')
        self.decode_as = config.get('decode_as', [])

        # 注释：移除序列号状态管理，直接使用绝对序列号
        # self.seq_state = {}

    def _initialize_components(self) -> None:
        """初始化TLS分析组件"""
        # 验证tshark可用性
        self.tshark_exec = self._check_tshark_version(self.tshark_path)
        self.logger.info(f"TLS analyzer initialization completed, using tshark: {self.tshark_exec}")

    def analyze_file(self, pcap_path: str, config: Dict[str, Any]) -> KeepRuleSet:
        """分析TLS流量并生成保留规则

        Args:
            pcap_path: PCAP文件路径
            config: 分析配置

        Returns:
            KeepRuleSet: TLS保留规则集合
        """
        self.logger.info(f"Starting TLS traffic analysis: {pcap_path}")
        start_time = time.time()

        # 初始化组件
        try:
            self._initialize_components()
        except Exception as e:
            self.logger.error(f"Component initialization failed: {e}")
            # 返回空的规则集合，但包含错误信息
            return KeepRuleSet(
                rules=[],
                tcp_flows={},
                statistics={},
                metadata={
                    'analyzer': 'TLSProtocolMarker',
                    'version': '1.0.0',
                    'pcap_path': pcap_path,
                    'error': str(e),
                    'analysis_failed': True
                }
            )

        try:
            # 第一阶段：扫描TLS消息（复用tls_flow_analyzer逻辑）
            tls_packets = self._scan_tls_messages(pcap_path)

            # 第二阶段：分析TCP流（复用tls_flow_analyzer逻辑）
            tcp_flows = self._analyze_tcp_flows(pcap_path, tls_packets)

            # 第三阶段：生成保留规则
            ruleset = self._generate_keep_rules(tls_packets, tcp_flows)

            # 设置元数据
            analysis_time = time.time() - start_time
            ruleset.metadata = {
                'analyzer': 'TLSProtocolMarker',
                'version': '1.0.0',
                'pcap_path': pcap_path,
                'preserve_config': self.preserve_config,
                'analysis_time': analysis_time,
                'tls_packets_found': len(tls_packets),
                'tcp_flows_found': len(tcp_flows)
            }

            # 移除规则优化逻辑，采用单条TLS消息粒度的保留规则
            # ruleset.optimize_rules()  # 禁用规则合并优化

            self.logger.info(f"TLS analysis completed, took {analysis_time:.2f} seconds, "
                           f"generated {len(ruleset.rules)} keep rules")

            return ruleset

        except Exception as e:
            self.logger.error(f"TLS traffic analysis failed: {e}")
            # 返回空规则集而不是抛出异常，保持系统稳定性
            ruleset = KeepRuleSet()
            ruleset.metadata = {
                'analyzer': 'TLSProtocolMarker',
                'version': '1.0.0',
                'pcap_path': pcap_path,
                'error': str(e),
                'analysis_failed': True
            }
            return ruleset

    def _check_tshark_version(self, tshark_path: Optional[str]) -> str:
        """验证tshark版本并返回可执行路径（复用自tls_flow_analyzer）"""
        executable = tshark_path or "tshark"

        try:
            completed = self._run_tshark_subprocess(
                [executable, "-v"],
                timeout=10,
                description="TShark version check"
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

        self.logger.debug(f"Detected tshark {'.'.join(map(str, version))} at {executable}")
        return executable

    def _parse_tshark_version(self, output: str) -> Optional[Tuple[int, int, int]]:
        """从tshark -v输出解析版本号（复用自tls_flow_analyzer）"""
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
        if not m:
            return None
        return tuple(map(int, m.groups()))  # type: ignore [return-value]

    def _run_tshark_subprocess(self, cmd: List[str], timeout: int = 60, description: str = "TShark command") -> subprocess.CompletedProcess:
        """Run TShark subprocess with cross-platform optimizations

        Args:
            cmd: TShark command list
            timeout: Command timeout in seconds
            description: Description for logging

        Returns:
            CompletedProcess result

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        # Windows optimization: prepare subprocess kwargs
        subprocess_kwargs = {
            'check': True,
            'text': True,
            'capture_output': True,
            'timeout': timeout
        }

        # Prevent CMD window flashing on Windows
        if platform.system() == 'Windows':
            subprocess_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        self.logger.debug(f"Executing {description}: {' '.join(cmd[:5])}...")  # Log first 5 args
        return subprocess.run(cmd, **subprocess_kwargs)

    def _scan_tls_messages(self, pcap_path: str) -> List[Dict[str, Any]]:
        """扫描PCAP文件中的TLS消息（复用自tls_flow_analyzer）

        使用两阶段扫描方法：
        1. 第一阶段：扫描包含TLS记录头的包（启用TCP重组）
        2. 第二阶段：扫描包含TLS段数据的包（禁用TCP重组，捕获跨分段情况）
        """
        self.logger.debug("Scanning TLS messages")

        # 第一阶段：扫描重组后的TLS消息
        # Ensure cross-platform path handling
        pcap_path_str = str(pcap_path)  # Convert Path object to string if needed

        cmd_reassembled = [
            self.tshark_exec,
            "-2",  # 两遍分析，启用重组
            "-r", pcap_path_str,
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

        # 第二阶段：扫描TLS段数据（禁用重组，捕获分段）
        cmd_segments = [
            self.tshark_exec,
            "-r", pcap_path_str,
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
            "-o", "tcp.desegment_tcp_streams:FALSE",
        ]

        # 添加解码规则
        if self.decode_as:
            for spec in self.decode_as:
                cmd_reassembled.extend(["-d", spec])
                cmd_segments.extend(["-d", spec])

        try:
            # 执行第一阶段扫描
            completed_reassembled = self._run_tshark_subprocess(
                cmd_reassembled,
                timeout=60,
                description="TLS reassembled scan"
            )
            packets_reassembled = json.loads(completed_reassembled.stdout)

            # 执行第二阶段扫描
            completed_segments = self._run_tshark_subprocess(
                cmd_segments,
                timeout=60,
                description="TLS segments scan"
            )
            packets_segments = json.loads(completed_segments.stdout)

        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            self.logger.error(f"TLS message scan failed: {exc}")
            raise RuntimeError(f"TLS消息扫描失败: {exc}") from exc

        # 合并两阶段的结果
        tls_packets = self._merge_tls_scan_results(packets_reassembled, packets_segments)

        self.logger.debug(f"Found {len(tls_packets)} packets containing TLS messages")
        return tls_packets

    def _merge_tls_scan_results(self, packets_reassembled: List[Dict[str, Any]],
                               packets_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并两阶段TLS扫描结果

        Args:
            packets_reassembled: 启用TCP重组的扫描结果
            packets_segments: 禁用TCP重组的扫描结果

        Returns:
            合并后的TLS数据包列表
        """
        # 使用字典存储数据包，以frame.number为键避免重复
        merged_packets = {}

        # 注释：不再需要复杂的序列号范围映射，直接从TLS段数据推断类型

        # 第一阶段：添加包含TLS记录头的包
        for packet in packets_reassembled:
            layers = packet.get("_source", {}).get("layers", {})
            frame_number = self._get_first_value(layers.get("frame.number"))

            if frame_number and self._has_tls_content(layers):
                merged_packets[str(frame_number)] = packet

        # 第二阶段：添加包含TLS段数据的包（跨分段情况）
        for packet in packets_segments:
            layers = packet.get("_source", {}).get("layers", {})
            frame_number = self._get_first_value(layers.get("frame.number"))

            if frame_number and self._has_tls_segment_data(layers):
                # 如果已经存在，优先使用重组后的版本（包含更完整的TLS信息）
                if str(frame_number) not in merged_packets:
                    merged_packets[str(frame_number)] = packet

        # 转换为列表并按frame.number排序
        result_packets = list(merged_packets.values())
        result_packets.sort(key=lambda p: int(self._get_first_value(
            p.get("_source", {}).get("layers", {}).get("frame.number", 0)
        )))

        self.logger.debug(f"Merged scan results: {len(packets_reassembled)} reassembled packets, "
                         f"{len(packets_segments)} segment packets, "
                         f"{len(result_packets)} after merge")

        return result_packets



    def _has_tls_segment_data(self, layers: Dict[str, Any]) -> bool:
        """检查数据包是否包含TLS段数据（用于识别跨分段的TLS消息片段）"""
        segment_data = layers.get("tls.segment.data", [])

        # 统一转换为列表
        if not isinstance(segment_data, list):
            segment_data = [segment_data] if segment_data else []

        # 检查是否有TLS段数据
        return len(segment_data) > 0 and any(data for data in segment_data if data)

    def _infer_tls_type_from_segment_data(self, layers: Dict[str, Any]) -> Optional[int]:
        """通过分析TLS段数据的头部来确定消息类型（复用tls_flow_analyzer逻辑）

        Args:
            layers: 数据包的layers信息

        Returns:
            推断的TLS类型，如果无法推断则返回None
        """
        tls_segment_data = layers.get("tls.segment.data")
        if not tls_segment_data:
            return None

        try:
            # 获取段数据（可能是列表格式）
            segment_data_hex = (tls_segment_data[0] if isinstance(tls_segment_data, list)
                              else tls_segment_data)

            if segment_data_hex and len(segment_data_hex) >= 2:
                # TLS记录的第一个字节是内容类型
                content_type_byte = int(segment_data_hex[:2], 16)
                if content_type_byte in TLS_CONTENT_TYPES:
                    return content_type_byte

        except (ValueError, TypeError, IndexError):
            pass

        return None

    def _has_tls_content(self, layers: Dict[str, Any]) -> bool:
        """检查数据包是否包含TLS记录头（复用自tls_flow_analyzer）"""
        content_types = layers.get("tls.record.content_type", [])
        opaque_types = layers.get("tls.record.opaque_type", [])

        # 统一转换为列表
        if not isinstance(content_types, list):
            content_types = [content_types] if content_types else []
        if not isinstance(opaque_types, list):
            opaque_types = [opaque_types] if opaque_types else []

        # 检查是否包含已知的TLS内容类型
        all_types = content_types + opaque_types
        for content_type in all_types:
            if content_type and str(content_type).isdigit():
                type_num = int(content_type)
                if type_num in TLS_CONTENT_TYPES:
                    return True

        return False

    def _analyze_tcp_flows(self, pcap_path: str, tls_packets: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """分析TCP流（复用自tls_flow_analyzer逻辑）"""
        self.logger.debug("Analyzing TCP flows")

        # 提取唯一的TCP流ID
        stream_ids = set()
        for packet in tls_packets:
            layers = packet.get("_source", {}).get("layers", {})
            stream_id = self._get_first_value(layers.get("tcp.stream"))
            if stream_id is not None:
                stream_ids.add(str(stream_id))

        tcp_flows = {}
        for stream_id in stream_ids:
            flow_info = self._analyze_single_tcp_flow(pcap_path, stream_id)
            if flow_info:
                tcp_flows[stream_id] = flow_info

        self.logger.debug(f"Analyzed {len(tcp_flows)} TCP flows")
        return tcp_flows

    def _analyze_single_tcp_flow(self, pcap_path: str, stream_id: str) -> Optional[Dict[str, Any]]:
        """分析单个TCP流（复用自tls_flow_analyzer逻辑）"""
        # Ensure cross-platform path handling
        pcap_path_str = str(pcap_path)  # Convert Path object to string if needed

        cmd = [
            self.tshark_exec,
            "-r", pcap_path_str,
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
            "-e", "tcp.stream",
            "-e", "tcp.seq",
            "-e", "tcp.seq_raw",
            "-e", "tcp.len",
            "-e", "tcp.flags",
            "-e", "tcp.payload",
            "-E", "occurrence=a",
            "-o", "tcp.desegment_tcp_streams:TRUE",
        ]

        if self.decode_as:
            for spec in self.decode_as:
                cmd.extend(["-d", spec])

        try:
            completed = self._run_tshark_subprocess(
                cmd,
                timeout=30,
                description=f"TCP stream {stream_id} analysis"
            )
            packets = json.loads(completed.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            self.logger.warning(f"TCP flow analysis failed (stream {stream_id}): {exc}")
            return None

        if not packets:
            return None

        # 分析流方向
        flow_directions = self._identify_flow_directions(packets)

        # 重组 TCP 载荷（移植自 tls_flow_analyzer）
        reassembled_payloads = self._reassemble_tcp_payloads(packets, flow_directions)

        return {
            "stream_id": stream_id,
            "packets": packets,
            "directions": flow_directions,
            "reassembled_payloads": reassembled_payloads,
            "packet_count": len(packets)
        }

    def _get_first_value(self, value: Any) -> Any:
        """获取第一个值（处理列表和单值）（复用自tls_flow_analyzer）"""
        if isinstance(value, list):
            return value[0] if value else None
        return value

    def _identify_flow_directions(self, packets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """识别TCP流的两个方向（复用自tls_flow_analyzer）"""
        directions = {
            "forward": {"src_ip": None, "dst_ip": None, "src_port": None, "dst_port": None, "packets": []},
            "reverse": {"src_ip": None, "dst_ip": None, "src_port": None, "dst_port": None, "packets": []}
        }

        # 分析第一个数据包确定正向
        if packets:
            first_packet = packets[0]
            layers = first_packet.get("_source", {}).get("layers", {})

            # 获取IP地址（优先IPv4，然后IPv6）
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

    def _reassemble_tcp_payloads(self, packets: List[Dict[str, Any]],
                                directions: Dict[str, Any]) -> Dict[str, Any]:
        """重组 TCP 载荷并记录序列号映射（移植自 tls_flow_analyzer）"""
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
        """根据TLS记录在重组载荷中的偏移位置，查找对应的实际TCP序列号（移植自 tls_flow_analyzer）"""
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

    def _parse_tls_records_from_payload(self, payload: bytes, stream_id: str,
                                       direction: str, seq_mapping: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从 TCP 载荷中解析 TLS 记录（移植自 tls_flow_analyzer）"""
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
            tls_header_seq_start = self._find_actual_seq_for_offset(offset, seq_mapping)
            tls_header_seq_end = tls_header_seq_start + 5
            tls_payload_seq_start = tls_header_seq_end

            if record_end > len(payload):
                # 记录不完整，可能跨段
                actual_length = len(payload) - offset - 5

                # 【修复1】：验证跨段消息的合理性
                if not self._validate_cross_segment_record(content_type, length, actual_length):
                    self.logger.warning(f"Cross-segment TLS message validation failed: type {content_type}, declared length {length}, actual length {actual_length}")
                    offset += 1  # 跳过这个字节，继续寻找下一个TLS记录
                    continue

                tls_payload_seq_end = self._find_actual_seq_for_offset(len(payload) - 1, seq_mapping) + 1
                records.append({
                    "stream_id": stream_id,
                    "direction": direction,
                    "content_type": content_type,
                    "content_type_name": TLS_CONTENT_TYPES[content_type],
                    "version": (version_major, version_minor),
                    "length": length,
                    "declared_length": length,  # 声明的长度
                    "actual_length": actual_length,  # 实际可用长度
                    "tls_header_seq_start": tls_header_seq_start,
                    "tls_header_seq_end": tls_header_seq_end,
                    "tls_payload_seq_start": tls_payload_seq_start,
                    "tls_payload_seq_end": tls_payload_seq_end,
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
                    "tls_header_seq_start": tls_header_seq_start,
                    "tls_header_seq_end": tls_header_seq_end,
                    "tls_payload_seq_start": tls_payload_seq_start,
                    "tls_payload_seq_end": tls_payload_seq_end,
                    "is_complete": True,
                    "is_cross_segment": False,
                    "processing_strategy": TLS_PROCESSING_STRATEGIES[content_type]
                })
                offset = record_end

        return records

    def _generate_keep_rules(self, tls_packets: List[Dict[str, Any]],
                           tcp_flows: Dict[str, Dict[str, Any]]) -> KeepRuleSet:
        """生成保留规则（重构版本，使用重组载荷和精确序列号计算）"""
        self.logger.debug("Generating keep rules (using reassembled payload analysis)")

        ruleset = KeepRuleSet()

        # 第一阶段：使用重组载荷生成精确的TLS消息规则
        for stream_id, flow_info in tcp_flows.items():
            reassembled_payloads = flow_info.get("reassembled_payloads", {})

            for direction_name, reassembled_info in reassembled_payloads.items():
                payload_data = reassembled_info["payload"]
                seq_mapping = reassembled_info["seq_mapping"]

                if len(payload_data) < 5:  # TLS 记录头至少 5 字节
                    continue

                # 解析 TLS 记录，传入序列号映射信息
                tls_records = self._parse_tls_records_from_payload(
                    payload_data, stream_id, direction_name, seq_mapping
                )

                # 为每个TLS记录生成保留规则
                for record in tls_records:
                    rule = self._create_keep_rule_from_tls_record(record)
                    if rule:
                        # 【修复2】：对跨段消息规则进行合理性验证
                        if self._validate_cross_segment_rule(rule, record):
                            ruleset.add_rule(rule)
                            self.logger.debug(f"Generated precise keep rule: flow {stream_id}-{direction_name} "
                                            f"TLS-{record['content_type']} "
                                            f"seq {rule.seq_start}-{rule.seq_end}")
                        else:
                            self.logger.warning(f"Cross-segment rule validation failed, skipping: flow {stream_id}-{direction_name} "
                                              f"TLS-{record['content_type']} "
                                              f"seq {rule.seq_start}-{rule.seq_end}")

        # 第二阶段：处理无法重组的单包TLS消息（回退机制）
        self._generate_fallback_rules_from_packets(tls_packets, tcp_flows, ruleset)

        # 添加流信息
        for stream_id, flow_info in tcp_flows.items():
            if stream_id not in ruleset.tcp_flows:
                flow_info_obj = self._create_flow_info(stream_id, flow_info)
                if flow_info_obj:
                    ruleset.tcp_flows[stream_id] = flow_info_obj

        return ruleset

    def _create_keep_rule_from_tls_record(self, record: Dict[str, Any]) -> Optional[KeepRule]:
        """从TLS记录创建保留规则（支持精确序列号范围）"""
        try:
            stream_id = record["stream_id"]
            direction = record["direction"]
            content_type = record["content_type"]
            tls_type_name = record["content_type_name"]

            # 检查是否为TLS-23 ApplicationData且配置为只保留头部
            is_application_data = (content_type == 23)
            preserve_full_application_data = self.preserve_config.get('application_data', False)

            if is_application_data and not preserve_full_application_data:
                # TLS-23且配置为False：只保留5字节TLS记录头部
                seq_start = record["tls_header_seq_start"]
                seq_end = record["tls_header_seq_end"]  # 左闭右开区间
                rule_type = "tls_applicationdata_header"
                preserve_strategy = "header_only"
            else:
                # 其他情况：保留整个TLS消息（头部+载荷）
                seq_start = record["tls_header_seq_start"]
                seq_end = record["tls_payload_seq_end"]  # 左闭右开区间
                rule_type = f"tls_{tls_type_name.lower()}"
                preserve_strategy = "full_message"

            rule = KeepRule(
                stream_id=stream_id,
                direction=direction,
                seq_start=seq_start,
                seq_end=seq_end,
                rule_type=rule_type,
                metadata={
                    "tls_content_type": content_type,
                    "tls_type_name": tls_type_name,
                    "tls_header_seq_start": record["tls_header_seq_start"],
                    "tls_header_seq_end": record["tls_header_seq_end"],
                    "tls_payload_seq_start": record["tls_payload_seq_start"],
                    "tls_payload_seq_end": record["tls_payload_seq_end"],
                    "is_complete": record["is_complete"],
                    "is_cross_segment": record["is_cross_segment"],
                    "preserve_strategy": preserve_strategy,
                    "declared_length": record["declared_length"],
                    "actual_length": record["actual_length"]
                }
            )

            return rule

        except Exception as e:
            self.logger.warning(f"Failed to create keep rule from TLS record: {e}")
            return None

    def _generate_fallback_rules_from_packets(self, tls_packets: List[Dict[str, Any]],
                                            tcp_flows: Dict[str, Dict[str, Any]],
                                            ruleset: KeepRuleSet) -> None:
        """从单包TLS消息生成回退规则（保持向后兼容性）"""
        self.logger.debug("Generating fallback keep rules (single-packet TLS messages)")

        for packet in tls_packets:
            layers = packet.get("_source", {}).get("layers", {})

            # 提取基础信息
            stream_id = str(self._get_first_value(layers.get("tcp.stream", "")))
            frame_number = self._get_first_value(layers.get("frame.number"))
            tcp_seq_raw = self._get_first_value(layers.get("tcp.seq_raw"))

            if not all([stream_id, frame_number, tcp_seq_raw is not None]):
                continue

            # 检查是否已经有重组规则覆盖了这个包
            tcp_seq = int(tcp_seq_raw)
            existing_rules = ruleset.get_rules_for_stream(stream_id,
                self._determine_packet_direction(packet, tcp_flows.get(stream_id)) or "forward")

            # 如果已有规则覆盖此序列号范围，跳过
            if any(rule.seq_start <= tcp_seq < rule.seq_end for rule in existing_rules):
                continue

            # 【解决方案1&2&3】：增强TLS片段检测和规则生成逻辑
            # 获取TCP载荷用于TLS记录开始检测
            tcp_payload = self._get_tcp_payload_hex(packet)

            # 检测TLS片段类型
            if self._is_tls_fragment(packet):
                # 这是TLS记录片段，需要特殊处理
                self.logger.debug(f"Detected TLS fragment: Frame {frame_number}")

                if self._is_applicationdata_fragment(packet):
                    # ApplicationData片段：完全掩码（不生成保留规则）
                    self.logger.debug(f"ApplicationData fragment, skipping rule generation: Frame {frame_number}")
                    continue
                else:
                    # 其他类型片段：完全保留
                    rule = self._create_full_preserve_rule(packet, tcp_flows)
                    if rule:
                        ruleset.add_rule(rule)
                        self.logger.debug(f"Generated fragment full preserve rule: Frame {frame_number} "
                                        f"seq {rule.seq_start}-{rule.seq_end}")
                    continue

            elif self._is_tls_record_start(packet, tcp_payload):
                # TLS记录开始：按正常逻辑处理
                self.logger.debug(f"Detected TLS record start: Frame {frame_number}")

                # 【解决方案3A】：验证TLS内容类型与载荷的一致性
                content_types = layers.get("tls.record.content_type", [])
                if content_types and not isinstance(content_types, list):
                    content_types = [content_types]

                for content_type in content_types:
                    if content_type and str(content_type).isdigit():
                        type_num = int(content_type)

                        # 验证TLS类型与载荷头部的一致性
                        if not self._validate_tls_type_consistency(tcp_payload, type_num):
                            self.logger.warning(f"Frame {frame_number}: TLS type {type_num} inconsistent with payload, skipping")
                            continue

                        if self._should_preserve_tls_type(type_num):
                            # 创建简化的单包规则
                            rule = self._create_simple_packet_rule(packet, tcp_flows, type_num)
                            if rule:
                                # 【解决方案3B】：验证规则的合理性
                                if self._validate_rule_reasonableness(rule, packet, tcp_payload):
                                    ruleset.add_rule(rule)
                                    self.logger.debug(f"Generated TLS record rule: Frame {frame_number} "
                                                    f"TLS-{type_num} seq {rule.seq_start}-{rule.seq_end}")
                                else:
                                    self.logger.warning(f"Frame {frame_number}: rule validation failed, skipping")
            else:
                # 非TLS数据或无法识别：完全掩码（不生成保留规则）
                self.logger.debug(f"Non-TLS data, skipping rule generation: Frame {frame_number}")
                continue

    def _create_simple_packet_rule(self, packet: Dict[str, Any],
                                 tcp_flows: Dict[str, Dict[str, Any]],
                                 tls_type: int) -> Optional[KeepRule]:
        """为单包TLS消息创建简化规则"""
        try:
            layers = packet.get("_source", {}).get("layers", {})

            stream_id = str(self._get_first_value(layers.get("tcp.stream", "")))
            frame_number = self._get_first_value(layers.get("frame.number"))
            tcp_seq_raw = self._get_first_value(layers.get("tcp.seq_raw"))
            tcp_len_raw = self._get_first_value(layers.get("tcp.len", 0))

            tcp_seq = int(tcp_seq_raw) if tcp_seq_raw is not None else 0
            tcp_len = int(tcp_len_raw) if tcp_len_raw is not None else 0

            direction = self._determine_packet_direction(packet, tcp_flows.get(stream_id))
            if not direction:
                return None

            # 检查是否为TLS-23 ApplicationData且配置为只保留头部
            tls_type_name = TLS_CONTENT_TYPES.get(tls_type, f"unknown_{tls_type}")
            is_application_data = (tls_type == 23)
            preserve_full_application_data = self.preserve_config.get('application_data', False)

            if is_application_data and not preserve_full_application_data:
                # 只保留5字节头部（左闭右开区间）
                seq_start = tcp_seq
                seq_end = tcp_seq + 5
                rule_type = "tls_applicationdata_header"
                preserve_strategy = "header_only"
            else:
                # 保留整个TCP载荷（左闭右开区间）
                seq_start = tcp_seq
                seq_end = tcp_seq + tcp_len
                rule_type = f"tls_{tls_type_name.lower()}"
                preserve_strategy = "full_message"

            rule = KeepRule(
                stream_id=stream_id,
                direction=direction,
                seq_start=seq_start,
                seq_end=seq_end,
                rule_type=rule_type,
                metadata={
                    "tls_content_type": tls_type,
                    "tls_type_name": tls_type_name,
                    "frame_number": frame_number,
                    "tcp_seq_raw": tcp_seq,
                    "tcp_len": tcp_len,
                    "preserve_strategy": preserve_strategy,
                    "rule_source": "fallback_single_packet"
                }
            )

            return rule

        except Exception as e:
            self.logger.warning(f"Failed to create simplified packet rule: {e}")
            return None

    def _determine_packet_direction(self, packet: Dict[str, Any],
                                  flow_info: Optional[Dict[str, Any]]) -> Optional[str]:
        """确定数据包的流方向"""
        if not flow_info:
            return "forward"  # 默认方向

        layers = packet.get("_source", {}).get("layers", {})
        src_ip = self._get_first_value(layers.get("ip.src")) or self._get_first_value(layers.get("ipv6.src"))
        src_port = self._get_first_value(layers.get("tcp.srcport"))

        directions = flow_info.get("directions", {})
        forward_info = directions.get("forward", {})

        if (src_ip == forward_info.get("src_ip") and
            str(src_port) == str(forward_info.get("src_port"))):
            return "forward"
        else:
            return "reverse"

    def _should_preserve_tls_type(self, tls_type: int) -> bool:
        """判断是否应该保留指定的TLS类型

        注意：对于ApplicationData (TLS-23)，即使配置为False，也需要返回True
        以便生成头部保留规则。具体的保留策略在规则生成时处理。
        """
        type_name = TLS_CONTENT_TYPES.get(tls_type, "").lower()

        # 映射TLS类型到配置键
        type_mapping = {
            "changecipherspec": "change_cipher_spec",
            "alert": "alert",
            "handshake": "handshake",
            "applicationdata": "application_data",
            "heartbeat": "heartbeat"
        }

        config_key = type_mapping.get(type_name.replace(" ", ""))
        if config_key:
            # 特殊处理ApplicationData: 即使配置为False，也需要处理以生成头部保留规则
            if config_key == "application_data":
                return True  # 总是需要处理，但保留策略在规则生成时区分
            return self.preserve_config.get(config_key, True)

        # 默认保留未知类型
        return True

    def _create_keep_rule_with_range(self, stream_id: str, direction: str,
                                   seq_start: int, seq_end: int, tls_type: int,
                                   frame_number: Any, record_length: int) -> Optional[KeepRule]:
        """创建带精确序列号范围的保留规则"""
        try:
            # 根据TLS类型确定规则类型
            tls_type_name = TLS_CONTENT_TYPES.get(tls_type, f"unknown_{tls_type}")
            rule_type = f"tls_{tls_type_name.lower()}"

            rule = KeepRule(
                stream_id=stream_id,
                direction=direction,
                seq_start=seq_start,
                seq_end=seq_end,
                rule_type=rule_type,
                metadata={
                    "tls_content_type": tls_type,
                    "tls_type_name": tls_type_name,
                    "frame_number": frame_number,
                    "tls_seq_start": seq_start,  # TLS消息起始序列号
                    "tls_seq_end": seq_end,      # TLS消息结束序列号
                    "tls_record_length": record_length
                }
            )

            return rule

        except Exception as e:
            self.logger.warning(f"Failed to create keep rule: {e}")
            return None

    def _create_keep_rule(self, stream_id: str, direction: str, tcp_seq: Any,
                         tcp_len: Any, tls_type: int, frame_number: Any) -> Optional[KeepRule]:
        """创建保留规则

        对于TLS-23 ApplicationData，根据配置决定保留策略：
        - application_data=True: 保留整个消息
        - application_data=False: 只保留5字节TLS记录头部
        """
        try:
            # 确保类型转换
            tcp_seq_int = int(tcp_seq) if tcp_seq is not None else 0
            tcp_len_int = int(tcp_len) if tcp_len is not None else 0

            # 检查是否为TLS-23 ApplicationData且配置为只保留头部
            tls_type_name = TLS_CONTENT_TYPES.get(tls_type, f"unknown_{tls_type}")
            is_application_data = (tls_type == 23)
            preserve_full_application_data = self.preserve_config.get('application_data', False)

            if is_application_data and not preserve_full_application_data:
                # TLS-23且配置为False：只保留5字节TLS记录头部
                return self._create_tls23_header_rule(
                    stream_id, direction, tcp_seq_int, frame_number
                )
            else:
                # 其他情况：保留整个TCP载荷
                seq_start = tcp_seq_int
                seq_end = tcp_seq_int + tcp_len_int

                # 根据TLS类型确定规则类型
                rule_type = f"tls_{tls_type_name.lower()}"

                rule = KeepRule(
                    stream_id=stream_id,
                    direction=direction,
                    seq_start=seq_start,
                    seq_end=seq_end,
                    rule_type=rule_type,
                    metadata={
                        "tls_content_type": tls_type,
                        "tls_type_name": tls_type_name,
                        "frame_number": frame_number,
                        "tcp_seq_raw": tcp_seq_int,  # 记录绝对序列号
                        "tcp_len": tcp_len_int
                    }
                )

            return rule

        except Exception as e:
            self.logger.warning(f"Failed to create keep rule: {e}")
            return None

    def _create_tls23_header_rule(self, stream_id: str, direction: str,
                                tcp_seq: int, frame_number: Any) -> Optional[KeepRule]:
        """为TLS-23 ApplicationData创建头部保留规则

        当application_data=False时，只保留TLS记录头部(5字节)，
        这样可以保持TLS消息结构的可识别性，同时掩码敏感的应用数据。

        Args:
            stream_id: TCP流标识
            direction: 流方向
            tcp_seq: TCP序列号
            frame_number: 帧号

        Returns:
            KeepRule: TLS-23头部保留规则
        """
        try:
            # TLS记录头部固定为5字节
            TLS_RECORD_HEADER_SIZE = 5

            seq_start = tcp_seq
            seq_end = tcp_seq + TLS_RECORD_HEADER_SIZE

            rule = KeepRule(
                stream_id=stream_id,
                direction=direction,
                seq_start=seq_start,
                seq_end=seq_end,
                rule_type="tls_applicationdata_header",  # 明确标识为头部保留
                metadata={
                    "tls_content_type": 23,
                    "tls_type_name": "ApplicationData",
                    "frame_number": frame_number,
                    "tcp_seq_raw": tcp_seq,
                    "preserve_reason": "tls_record_header",
                    "header_size": TLS_RECORD_HEADER_SIZE,
                    "preserve_strategy": "header_only"  # 标识保留策略
                }
            )

            self.logger.debug(f"Created TLS-23 header keep rule: Frame {frame_number}, "
                            f"seq {seq_start}-{seq_end} (5-byte header)")

            return rule

        except Exception as e:
            self.logger.warning(f"Failed to create TLS-23 header keep rule: {e}")
            return None

    def _create_keep_rule_for_tls_message(self, stream_id: str, direction: str,
                                        message_start_seq: int, record_length: int,
                                        tls_type: int, frame_number: Any,
                                        message_index: int) -> Optional[KeepRule]:
        """为单个TLS消息创建保留规则

        支持单个TCP数据包中包含多条TLS消息的情况，为每条消息分别生成规则。

        Args:
            stream_id: TCP流标识
            direction: 流方向
            message_start_seq: TLS消息起始序列号
            record_length: TLS记录载荷长度
            tls_type: TLS消息类型
            frame_number: 帧号
            message_index: 消息在数据包中的索引

        Returns:
            KeepRule: TLS消息保留规则
        """
        try:
            # 检查是否为TLS-23 ApplicationData且配置为只保留头部
            tls_type_name = TLS_CONTENT_TYPES.get(tls_type, f"unknown_{tls_type}")
            is_application_data = (tls_type == 23)
            preserve_full_application_data = self.preserve_config.get('application_data', False)

            if is_application_data and not preserve_full_application_data:
                # TLS-23且配置为False：只保留5字节TLS记录头部
                TLS_RECORD_HEADER_SIZE = 5

                rule = KeepRule(
                    stream_id=stream_id,
                    direction=direction,
                    seq_start=message_start_seq,
                    seq_end=message_start_seq + TLS_RECORD_HEADER_SIZE,
                    rule_type="tls_applicationdata_header",
                    metadata={
                        "tls_content_type": tls_type,
                        "tls_type_name": tls_type_name,
                        "frame_number": frame_number,
                        "message_index": message_index,  # 消息在数据包中的索引
                        "message_start_seq": message_start_seq,
                        "record_length": record_length,
                        "preserve_reason": "tls_record_header",
                        "header_size": TLS_RECORD_HEADER_SIZE,
                        "preserve_strategy": "header_only"
                    }
                )

                self.logger.debug(f"Created TLS-23 message #{message_index} header keep rule: "
                                f"Frame {frame_number}, seq {message_start_seq}-"
                                f"{message_start_seq + TLS_RECORD_HEADER_SIZE} (5-byte header)")

                return rule
            else:
                # 其他情况：保留整个TLS消息
                TLS_RECORD_HEADER_SIZE = 5
                total_message_size = TLS_RECORD_HEADER_SIZE + record_length

                rule = KeepRule(
                    stream_id=stream_id,
                    direction=direction,
                    seq_start=message_start_seq,
                    seq_end=message_start_seq + total_message_size,
                    rule_type=f"tls_{tls_type_name.lower()}",
                    metadata={
                        "tls_content_type": tls_type,
                        "tls_type_name": tls_type_name,
                        "frame_number": frame_number,
                        "message_index": message_index,
                        "message_start_seq": message_start_seq,
                        "record_length": record_length,
                        "total_message_size": total_message_size
                    }
                )

                return rule

        except Exception as e:
            self.logger.warning(f"Failed to create TLS message keep rule: {e}")
            return None

    # 注释：移除32位序列号回绕处理，直接使用绝对序列号
    # def _logical_seq(self, seq32: int, flow_key: str) -> int:
    #     """处理32位序列号回绕，返回64位逻辑序号"""
    #     if flow_key not in self.seq_state:
    #         self.seq_state[flow_key] = {"last": None, "epoch": 0}
    #
    #     state = self.seq_state[flow_key]
    #     if state["last"] is not None and (state["last"] - seq32) > 0x7FFFFFFF:
    #         state["epoch"] += 1
    #     state["last"] = seq32
    #     return (state["epoch"] << 32) | seq32

    def _create_flow_info(self, stream_id: str, flow_data: Optional[Dict[str, Any]]) -> Optional[FlowInfo]:
        """创建流信息"""
        if not flow_data:
            return None

        directions = flow_data.get("directions", {})
        forward_info = directions.get("forward", {})

        return FlowInfo(
            stream_id=stream_id,
            src_ip=forward_info.get("src_ip", ""),
            dst_ip=forward_info.get("dst_ip", ""),
            src_port=int(forward_info.get("src_port", 0)) if forward_info.get("src_port") else 0,
            dst_port=int(forward_info.get("dst_port", 0)) if forward_info.get("dst_port") else 0,
            protocol="tcp",
            direction="forward",
            packet_count=flow_data.get("packet_count", 0)
        )

    def get_supported_protocols(self) -> List[str]:
        """获取支持的协议列表"""
        return ['tls', 'ssl']

    def _validate_specific_config(self, config: Dict[str, Any]) -> List[str]:
        """验证TLS特定配置"""
        errors = []

        preserve_config = config.get('preserve', {})
        if not isinstance(preserve_config, dict):
            errors.append("preserve配置必须是字典类型")
            return errors

        # 验证TLS消息类型配置
        valid_tls_types = ['handshake', 'application_data', 'alert', 'change_cipher_spec', 'heartbeat']
        for tls_type, should_preserve in preserve_config.items():
            if tls_type not in valid_tls_types:
                errors.append(f"未知的TLS消息类型: {tls_type}")
            if not isinstance(should_preserve, bool):
                errors.append(f"TLS消息类型{tls_type}的配置必须是布尔值")

        return errors

    def _is_tls_record_start(self, packet_info: Dict[str, Any], payload_hex: str) -> bool:
        """检测是否为TLS记录的开始

        Args:
            packet_info: 包信息字典
            payload_hex: TCP载荷的十六进制字符串

        Returns:
            bool: True如果是TLS记录开始，False如果是片段或非TLS数据
        """
        if not payload_hex or len(payload_hex) < 10:
            return False

        try:
            # 解析前5字节作为TLS记录头
            content_type = int(payload_hex[0:2], 16)
            version_major = int(payload_hex[2:4], 16)
            version_minor = int(payload_hex[4:6], 16)
            length = int(payload_hex[6:10], 16)

            # 验证TLS头的有效性
            valid_types = [20, 21, 22, 23, 24]  # TLS内容类型
            valid_versions = [(3, 0), (3, 1), (3, 2), (3, 3)]  # SSL 3.0, TLS 1.0, 1.1, 1.2

            # 检查内容类型和版本
            if content_type not in valid_types:
                return False
            if (version_major, version_minor) not in valid_versions:
                return False

            # 检查长度合理性（TLS记录最大长度16384字节）
            if length <= 0 or length > 16384:
                return False

            # 检查载荷长度是否足够包含声明的TLS记录
            actual_payload_len = len(payload_hex) // 2
            if length + 5 > actual_payload_len:
                # 载荷不足以包含完整的TLS记录，但这可能是跨段消息的开始
                # 只要头部有效就认为是记录开始
                pass

            return True

        except (ValueError, TypeError):
            return False

    def _is_tls_fragment(self, packet_info: Dict[str, Any]) -> bool:
        """检测是否为TLS记录片段

        Args:
            packet_info: 包信息字典，包含layers信息

        Returns:
            bool: True如果是TLS片段，False如果是完整记录或非TLS数据
        """
        layers = packet_info.get("_source", {}).get("layers", {})

        # 检查Wireshark是否将其标记为tls.segment.data
        if 'tls.segment.data' in layers:
            return True

        # 检查是否有tcp.segments字段（表明TCP层面的重组）
        if 'tcp.segments' in layers:
            # 进一步检查是否有TLS相关的段信息
            return self._has_tls_segment_data(layers)

        return False

    def _is_applicationdata_fragment(self, packet_info: Dict[str, Any]) -> bool:
        """检测是否为ApplicationData记录的片段

        Args:
            packet_info: 包信息字典

        Returns:
            bool: True如果是ApplicationData片段
        """
        layers = packet_info.get("_source", {}).get("layers", {})

        # 如果有明确的TLS内容类型且为23，则是ApplicationData
        content_types = layers.get("tls.record.content_type", [])
        if content_types:
            if not isinstance(content_types, list):
                content_types = [content_types]
            return any(str(ct) == "23" for ct in content_types)

        # 如果是TLS片段，假设是ApplicationData（因为大部分跨段消息都是ApplicationData）
        if self._is_tls_fragment(packet_info):
            return True

        return False

    def _get_tcp_payload_hex(self, packet: Dict[str, Any]) -> str:
        """获取TCP载荷的十六进制字符串

        Args:
            packet: 包信息字典

        Returns:
            str: TCP载荷的十六进制字符串，如果没有载荷则返回空字符串
        """
        layers = packet.get("_source", {}).get("layers", {})
        tcp_payload = layers.get("tcp.payload", "")

        if isinstance(tcp_payload, list):
            # 如果是列表，取第一个元素
            tcp_payload = tcp_payload[0] if tcp_payload else ""

        return str(tcp_payload) if tcp_payload else ""

    def _create_full_preserve_rule(self, packet: Dict[str, Any],
                                 tcp_flows: Dict[str, Dict[str, Any]]) -> Optional[KeepRule]:
        """为TLS片段创建完全保留规则

        Args:
            packet: 包信息字典
            tcp_flows: TCP流信息

        Returns:
            KeepRule: 完全保留规则，如果创建失败则返回None
        """
        try:
            layers = packet.get("_source", {}).get("layers", {})

            stream_id = str(self._get_first_value(layers.get("tcp.stream", "")))
            frame_number = self._get_first_value(layers.get("frame.number"))
            tcp_seq_raw = self._get_first_value(layers.get("tcp.seq_raw"))
            tcp_len_raw = self._get_first_value(layers.get("tcp.len", 0))

            tcp_seq = int(tcp_seq_raw) if tcp_seq_raw is not None else 0
            tcp_len = int(tcp_len_raw) if tcp_len_raw is not None else 0

            direction = self._determine_packet_direction(packet, tcp_flows.get(stream_id))
            if not direction:
                return None

            # 创建完全保留规则（保留整个TCP载荷）
            rule = KeepRule(
                stream_id=stream_id,
                direction=direction,
                seq_start=tcp_seq,
                seq_end=tcp_seq + tcp_len,  # 左闭右开区间
                rule_type="tls_fragment_full_preserve",
                metadata={
                    "frame_number": frame_number,
                    "tcp_seq_raw": tcp_seq,
                    "tcp_len": tcp_len,
                    "preserve_strategy": "full",
                    "rule_source": "tls_fragment_handler"
                }
            )

            return rule

        except Exception as e:
            self.logger.warning(f"Failed to create full preserve rule: {e}")
            return None

    def _validate_tls_type_consistency(self, payload_hex: str, expected_type: int) -> bool:
        """验证TLS类型与载荷头部的一致性

        Args:
            payload_hex: TCP载荷的十六进制字符串
            expected_type: 期望的TLS内容类型

        Returns:
            bool: True如果一致，False如果不一致
        """
        if not payload_hex or len(payload_hex) < 2:
            return False

        try:
            # 解析载荷的第一个字节作为TLS内容类型
            actual_type = int(payload_hex[0:2], 16)

            # 检查是否匹配
            if actual_type == expected_type:
                return True

            # 对于某些特殊情况，允许一定的容错
            # 例如，如果Wireshark解析为TLS-23，但载荷第一字节不是23，
            # 可能是因为这是一个跨段消息的片段
            self.logger.debug(f"TLS type inconsistent: expected {expected_type}, actual {actual_type}")
            return False

        except (ValueError, TypeError):
            return False

    def _validate_rule_reasonableness(self, rule: KeepRule, packet: Dict[str, Any],
                                    payload_hex: str) -> bool:
        """验证规则的合理性

        Args:
            rule: 生成的保留规则
            packet: 原始包信息
            payload_hex: TCP载荷十六进制

        Returns:
            bool: True如果规则合理，False如果不合理
        """
        try:
            layers = packet.get("_source", {}).get("layers", {})
            tcp_len = int(self._get_first_value(layers.get("tcp.len", 0)))

            # 1. 检查规则长度的合理性
            rule_length = rule.seq_end - rule.seq_start

            # 对于header_only规则，长度应该是5字节
            if rule.metadata.get('preserve_strategy') == 'header_only':
                if rule_length != 5:
                    self.logger.warning(f"Header_only rule length abnormal: {rule_length} (expected 5)")
                    return False

            # 对于full_message规则，长度不应该超过TCP载荷长度
            elif rule.metadata.get('preserve_strategy') == 'full_message':
                if rule_length > tcp_len:
                    self.logger.warning(f"Full_message rule length exceeds TCP payload: {rule_length} > {tcp_len}")
                    return False

            # 2. 检查TLS-23规则的特殊性
            if rule.rule_type == 'tls_applicationdata_header':
                # ApplicationData头部规则必须是5字节
                if rule_length != 5:
                    self.logger.warning(f"ApplicationData header rule length incorrect: {rule_length}")
                    return False

                # 验证载荷确实以TLS-23开头
                if payload_hex and len(payload_hex) >= 2:
                    first_byte = int(payload_hex[0:2], 16)
                    if first_byte != 23:
                        self.logger.warning(f"ApplicationData rule but payload does not start with 23: {first_byte}")
                        return False

            # 3. 检查ChangeCipherSpec规则的特殊性
            elif rule.rule_type == 'tls_changecipherspec':
                # ChangeCipherSpec消息通常很短（6字节：5字节头+1字节载荷）
                if rule_length > 50:  # 给一些容错空间
                    self.logger.warning(f"ChangeCipherSpec rule length abnormal: {rule_length}")
                    return False

                # 验证载荷确实以TLS-20开头
                if payload_hex and len(payload_hex) >= 2:
                    first_byte = int(payload_hex[0:2], 16)
                    if first_byte != 20:
                        self.logger.warning(f"ChangeCipherSpec rule but payload does not start with 20: {first_byte}")
                        return False

            return True

        except Exception as e:
            self.logger.warning(f"Rule reasonableness validation failed: {e}")
            return False

    def _validate_cross_segment_record(self, content_type: int, declared_length: int, actual_length: int) -> bool:
        """验证跨段TLS记录的合理性

        Args:
            content_type: TLS内容类型
            declared_length: TLS记录声明的长度
            actual_length: 实际可用的载荷长度

        Returns:
            bool: True如果跨段记录合理，False如果不合理
        """
        try:
            # 1. 检查声明长度是否合理
            MAX_TLS_RECORD_LENGTH = 16384  # TLS标准最大记录长度
            if declared_length > MAX_TLS_RECORD_LENGTH:
                self.logger.warning(f"TLS record declared length too large: {declared_length} > {MAX_TLS_RECORD_LENGTH}")
                return False

            # 2. 针对不同TLS类型的特殊检查
            if content_type == 20:  # ChangeCipherSpec
                # ChangeCipherSpec消息载荷通常只有1字节
                if declared_length > 10:  # 给一些容错空间
                    self.logger.warning(f"ChangeCipherSpec declared length abnormal: {declared_length}")
                    return False

            elif content_type == 21:  # Alert
                # Alert消息载荷通常只有2字节
                if declared_length > 10:  # 给一些容错空间
                    self.logger.warning(f"Alert declared length abnormal: {declared_length}")
                    return False

            # 3. 检查实际长度与声明长度的差异
            if actual_length > declared_length:
                self.logger.warning(f"Actual length exceeds declared length: {actual_length} > {declared_length}")
                return False

            # 4. 检查跨段的合理性（实际长度不应该太小）
            if actual_length < declared_length * 0.1:  # 实际长度不应该小于声明长度的10%
                self.logger.warning(f"Cross-segment record actual length too small: {actual_length} < {declared_length * 0.1}")
                return False

            return True

        except Exception as e:
            self.logger.warning(f"Cross-segment record validation failed: {e}")
            return False

    def _validate_cross_segment_rule(self, rule: KeepRule, record: Dict[str, Any]) -> bool:
        """验证跨段消息生成的规则的合理性

        Args:
            rule: 生成的保留规则
            record: 原始TLS记录信息

        Returns:
            bool: True如果规则合理，False如果不合理
        """
        try:
            rule_length = rule.seq_end - rule.seq_start
            content_type = record.get("content_type", 0)
            is_cross_segment = record.get("is_cross_segment", False)
            declared_length = record.get("declared_length", 0)
            actual_length = record.get("actual_length", 0)

            # 1. 对于跨段消息，进行额外的大小检查
            if is_cross_segment:
                # 跨段规则的长度不应该过大
                MAX_CROSS_SEGMENT_RULE_LENGTH = 2048  # 2KB限制
                if rule_length > MAX_CROSS_SEGMENT_RULE_LENGTH:
                    self.logger.warning(f"Cross-segment rule length too large: {rule_length} > {MAX_CROSS_SEGMENT_RULE_LENGTH}")
                    return False

                # 针对特定TLS类型的严格限制
                if content_type == 20:  # ChangeCipherSpec
                    # ChangeCipherSpec规则不应该超过100字节
                    if rule_length > 100:
                        self.logger.warning(f"Cross-segment ChangeCipherSpec rule length abnormal: {rule_length}")
                        return False

                elif content_type == 21:  # Alert
                    # Alert规则不应该超过50字节
                    if rule_length > 50:
                        self.logger.warning(f"Cross-segment Alert rule length abnormal: {rule_length}")
                        return False

            # 2. 检查声明长度与实际规则长度的一致性
            if rule.metadata.get('preserve_strategy') == 'full_message':
                expected_length = 5 + actual_length  # 5字节头部 + 实际载荷长度
                if abs(rule_length - expected_length) > 10:  # 允许一些误差
                    self.logger.warning(f"Rule length does not match expected: {rule_length} vs {expected_length}")
                    return False

            return True

        except Exception as e:
            self.logger.warning(f"Cross-segment rule validation failed: {e}")
            return False
