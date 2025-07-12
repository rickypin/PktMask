"""
TLS协议标记器

基于 tls_flow_analyzer 代码逻辑的TLS协议分析器，生成TCP序列号保留规则。
复用核心算法而非直接依赖，保持工具与主程序的独立性。
"""

from __future__ import annotations

import json
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

        # TLS保留策略配置
        self.preserve_config = config.get('preserve', {
            'handshake': True,
            'application_data': False,
            'alert': True,
            'change_cipher_spec': True,
            'heartbeat': True
        })

        # tshark配置
        self.tshark_path = config.get('tshark_path')
        self.decode_as = config.get('decode_as', [])

        # 序列号状态管理（用于处理32位回绕）
        self.seq_state = {}

    def _initialize_components(self) -> None:
        """初始化TLS分析组件"""
        # 验证tshark可用性
        self.tshark_exec = self._check_tshark_version(self.tshark_path)
        self.logger.info(f"TLS分析器初始化完成，使用tshark: {self.tshark_exec}")

    def analyze_file(self, pcap_path: str, config: Dict[str, Any]) -> KeepRuleSet:
        """分析TLS流量并生成保留规则

        Args:
            pcap_path: PCAP文件路径
            config: 分析配置

        Returns:
            KeepRuleSet: TLS保留规则集合
        """
        self.logger.info(f"开始分析TLS流量: {pcap_path}")
        start_time = time.time()

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

            # 优化规则
            ruleset.optimize_rules()

            self.logger.info(f"TLS分析完成，耗时 {analysis_time:.2f} 秒，"
                           f"生成 {len(ruleset.rules)} 条保留规则")

            return ruleset

        except Exception as e:
            self.logger.error(f"TLS流量分析失败: {e}")
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

        self.logger.debug(f"检测到 tshark {'.'.join(map(str, version))} 于 {executable}")
        return executable

    def _parse_tshark_version(self, output: str) -> Optional[Tuple[int, int, int]]:
        """从tshark -v输出解析版本号（复用自tls_flow_analyzer）"""
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
        if not m:
            return None
        return tuple(map(int, m.groups()))  # type: ignore [return-value]

    def _scan_tls_messages(self, pcap_path: str) -> List[Dict[str, Any]]:
        """扫描PCAP文件中的TLS消息（复用自tls_flow_analyzer）"""
        self.logger.debug("扫描TLS消息")

        # 构建tshark命令（复用tls_flow_analyzer的命令结构）
        cmd = [
            self.tshark_exec,
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

        # 添加解码规则
        if self.decode_as:
            for spec in self.decode_as:
                cmd.extend(["-d", spec])

        try:
            completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
            packets = json.loads(completed.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"TLS消息扫描失败: {exc}") from exc

        # 过滤包含TLS内容的数据包
        tls_packets = []
        for packet in packets:
            layers = packet.get("_source", {}).get("layers", {})
            if self._has_tls_content(layers):
                tls_packets.append(packet)

        self.logger.debug(f"发现 {len(tls_packets)} 个包含TLS消息的数据包")
        return tls_packets

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
        self.logger.debug("分析TCP流")

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

        self.logger.debug(f"分析了 {len(tcp_flows)} 个TCP流")
        return tcp_flows

    def _analyze_single_tcp_flow(self, pcap_path: str, stream_id: str) -> Optional[Dict[str, Any]]:
        """分析单个TCP流（复用自tls_flow_analyzer逻辑）"""
        cmd = [
            self.tshark_exec,
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
            completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
            packets = json.loads(completed.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            self.logger.warning(f"TCP流分析失败 (stream {stream_id})")
            return None

        if not packets:
            return None

        # 分析流方向
        flow_directions = self._identify_flow_directions(packets)

        return {
            "stream_id": stream_id,
            "packets": packets,
            "directions": flow_directions,
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

    def _generate_keep_rules(self, tls_packets: List[Dict[str, Any]],
                           tcp_flows: Dict[str, Dict[str, Any]]) -> KeepRuleSet:
        """生成保留规则"""
        self.logger.debug("生成保留规则")

        ruleset = KeepRuleSet()

        # 为每个TLS数据包生成保留规则
        for packet in tls_packets:
            layers = packet.get("_source", {}).get("layers", {})

            # 提取基础信息
            stream_id = str(self._get_first_value(layers.get("tcp.stream", "")))
            frame_number = self._get_first_value(layers.get("frame.number"))
            tcp_seq = self._get_first_value(layers.get("tcp.seq"))
            tcp_len = self._get_first_value(layers.get("tcp.len", 0))

            if not all([stream_id, frame_number, tcp_seq is not None]):
                continue

            # 确定流方向
            direction = self._determine_packet_direction(packet, tcp_flows.get(stream_id))
            if not direction:
                continue

            # 处理TLS内容类型
            content_types = layers.get("tls.record.content_type", [])
            if not isinstance(content_types, list):
                content_types = [content_types] if content_types else []

            # 为每个TLS内容类型生成规则
            for content_type in content_types:
                if content_type and str(content_type).isdigit():
                    type_num = int(content_type)
                    if self._should_preserve_tls_type(type_num):
                        rule = self._create_keep_rule(
                            stream_id, direction, tcp_seq, tcp_len, type_num, frame_number
                        )
                        if rule:
                            ruleset.add_rule(rule)

                            # 添加流信息
                            if stream_id not in ruleset.tcp_flows:
                                flow_info = self._create_flow_info(stream_id, tcp_flows.get(stream_id))
                                if flow_info:
                                    ruleset.tcp_flows[stream_id] = flow_info

        return ruleset

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
        """判断是否应该保留指定的TLS类型"""
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
            return self.preserve_config.get(config_key, True)

        # 默认保留未知类型
        return True

    def _create_keep_rule(self, stream_id: str, direction: str, tcp_seq: Any,
                         tcp_len: Any, tls_type: int, frame_number: Any) -> Optional[KeepRule]:
        """创建保留规则"""
        try:
            # 确保类型转换
            tcp_seq_int = int(tcp_seq) if tcp_seq is not None else 0
            tcp_len_int = int(tcp_len) if tcp_len is not None else 0

            # 转换为64位逻辑序列号
            flow_key = f"{stream_id}_{direction}"
            logical_seq_start = self._logical_seq(tcp_seq_int, flow_key)
            logical_seq_end = logical_seq_start + tcp_len_int

            # 根据TLS类型确定规则类型
            tls_type_name = TLS_CONTENT_TYPES.get(tls_type, f"unknown_{tls_type}")
            rule_type = f"tls_{tls_type_name.lower()}"

            rule = KeepRule(
                stream_id=stream_id,
                direction=direction,
                seq_start=logical_seq_start,
                seq_end=logical_seq_end,
                rule_type=rule_type,
                metadata={
                    "tls_content_type": tls_type,
                    "tls_type_name": tls_type_name,
                    "frame_number": frame_number,
                    "tcp_seq_32bit": tcp_seq_int,
                    "tcp_len": tcp_len_int
                }
            )

            return rule

        except Exception as e:
            self.logger.warning(f"创建保留规则失败: {e}")
            return None

    def _logical_seq(self, seq32: int, flow_key: str) -> int:
        """处理32位序列号回绕，返回64位逻辑序号"""
        if flow_key not in self.seq_state:
            self.seq_state[flow_key] = {"last": None, "epoch": 0}

        state = self.seq_state[flow_key]
        if state["last"] is not None and (state["last"] - seq32) > 0x7FFFFFFF:
            state["epoch"] += 1
        state["last"] = seq32
        return (state["epoch"] << 32) | seq32

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
