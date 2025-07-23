"""
智能处理适配器

将封装解析结果适配到现有的处理逻辑，实现：
- 多层IP匿名化处理适配
- 内层载荷裁切处理适配
- 现有功能的无缝集成
"""

import logging
from typing import List, Optional, Dict, Any, Tuple, Callable
from scapy.packet import Packet

from pktmask.core.encapsulation.types import (
    EncapsulationResult,
    IPLayerInfo,
    PayloadInfo,
    EncapsulationType,
    EncapsulationError,
)
from pktmask.core.encapsulation.detector import EncapsulationDetector
from pktmask.core.encapsulation.parser import ProtocolStackParser


class ProcessingAdapter:
    """
    智能处理适配器

    负责将多层封装解析结果适配到现有的处理系统：
    - IP匿名化处理适配
    - 载荷裁切处理适配
    - 统计信息收集适配
    """

    def __init__(self):
        """初始化适配器"""
        self.logger = logging.getLogger(__name__)
        self.detector = EncapsulationDetector()
        self.parser = ProtocolStackParser()

        # 处理统计
        self.stats = {
            "total_packets": 0,
            "encapsulated_packets": 0,
            "multi_ip_packets": 0,
            "encap_type_counts": {},
            "processing_errors": 0,
        }

    def analyze_packet_for_ip_processing(self, packet: Packet) -> Dict[str, Any]:
        """
        分析数据包，准备IP匿名化处理

        Args:
            packet: 要分析的数据包

        Returns:
            IP处理分析结果，包含所有需要匿名化的IP地址信息
        """
        try:
            self.stats["total_packets"] += 1

            # 解析封装结构
            encap_result = self.parser.parse_packet_layers(packet)

            if not encap_result.parsing_success:
                self.logger.warning(
                    f"Packet parsing failed: {encap_result.error_message}"
                )
                self.stats["processing_errors"] += 1
                return self._create_fallback_ip_analysis(packet)

            # 更新统计
            self._update_encap_stats(encap_result)

            # 准备IP处理信息
            ip_analysis = {
                "encap_type": encap_result.encap_type,
                "has_encapsulation": encap_result.encap_type != EncapsulationType.PLAIN,
                "ip_layers": encap_result.ip_layers,
                "total_ips": len(encap_result.ip_layers),
                "has_multiple_ips": encap_result.has_multiple_ips(),
                "innermost_ip": encap_result.get_innermost_ip(),
                "outermost_ip": encap_result.get_outermost_ip(),
                "vlan_info": encap_result.vlan_info,
                "processing_hints": self._generate_ip_processing_hints(encap_result),
                "original_packet": packet,
                "encap_result": encap_result,
            }

            self.logger.debug(
                f"IP processing analysis completed: {len(encap_result.ip_layers)} IP layers"
            )
            return ip_analysis

        except Exception as e:
            error_msg = f"IP processing analysis failed: {str(e)}"
            self.logger.error(error_msg)
            self.stats["processing_errors"] += 1
            return self._create_fallback_ip_analysis(packet)

    def analyze_packet_for_payload_processing(self, packet: Packet) -> Dict[str, Any]:
        """
        分析数据包，准备载荷裁切处理

        Args:
            packet: 要分析的数据包

        Returns:
            载荷处理分析结果，包含最内层载荷信息
        """
        try:
            self.stats["total_packets"] += 1

            # 解析封装结构
            encap_result = self.parser.parse_packet_layers(packet)

            if not encap_result.parsing_success:
                self.logger.warning(
                    f"Packet parsing failed: {encap_result.error_message}"
                )
                self.stats["processing_errors"] += 1
                return self._create_fallback_payload_analysis(packet)

            # 更新统计
            self._update_encap_stats(encap_result)

            # 准备载荷处理信息
            payload_analysis = {
                "encap_type": encap_result.encap_type,
                "has_encapsulation": encap_result.encap_type != EncapsulationType.PLAIN,
                "innermost_payload": encap_result.innermost_payload,
                "has_payload": encap_result.innermost_payload is not None,
                "is_encrypted": (
                    encap_result.innermost_payload.is_encrypted
                    if encap_result.innermost_payload
                    else False
                ),
                "transport_protocol": (
                    encap_result.innermost_payload.protocol
                    if encap_result.innermost_payload
                    else None
                ),
                "payload_depth": (
                    encap_result.innermost_payload.layer_depth
                    if encap_result.innermost_payload
                    else 0
                ),
                "tcp_session_info": self._extract_tcp_session_info(encap_result),
                "processing_hints": self._generate_payload_processing_hints(
                    encap_result
                ),
                "original_packet": packet,
                "encap_result": encap_result,
            }

            self.logger.debug(
                f"Payload processing analysis completed: payload depth={payload_analysis['payload_depth']}"
            )
            return payload_analysis

        except Exception as e:
            error_msg = f"Payload processing analysis failed: {str(e)}"
            self.logger.error(error_msg)
            return self._create_fallback_payload_analysis(packet)

    def extract_ips_for_anonymization(
        self, ip_analysis: Dict[str, Any]
    ) -> List[Tuple[str, str, str]]:
        """
        从IP分析结果中提取需要匿名化的IP地址

        Args:
            ip_analysis: IP处理分析结果

        Returns:
            IP地址列表，每个元素为(src_ip, dst_ip, context)的元组
        """
        try:
            ip_pairs = []
            ip_layers = ip_analysis.get("ip_layers", [])

            for ip_layer in ip_layers:
                context = f"{ip_layer.encap_context}_depth_{ip_layer.layer_depth}"
                ip_pairs.append((ip_layer.src_ip, ip_layer.dst_ip, context))

            # 如果没有找到IP层，尝试回退处理
            if not ip_pairs:
                packet = ip_analysis.get("original_packet")
                if packet:
                    fallback_ips = self._extract_fallback_ips(packet)
                    ip_pairs.extend(fallback_ips)

            self.logger.debug(
                f"Extracted {len(ip_pairs)} IP address pairs for anonymization"
            )
            return ip_pairs

        except Exception as e:
            self.logger.error(f"IP address extraction failed: {str(e)}")
            return []

    def extract_tcp_session_for_trimming(
        self, payload_analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        从载荷分析结果中提取TCP会话信息用于裁切

        Args:
            payload_analysis: 载荷处理分析结果

        Returns:
            TCP会话信息，如果不是TCP或提取失败则返回None
        """
        try:
            session_info = payload_analysis.get("tcp_session_info")
            if not session_info:
                return None

            # 构建兼容现有trimming逻辑的会话信息
            tcp_session = {
                "src_ip": session_info["src_ip"],
                "dst_ip": session_info["dst_ip"],
                "src_port": session_info["src_port"],
                "dst_port": session_info["dst_port"],
                "session_key": self._generate_session_key(session_info),
                "is_encrypted": payload_analysis.get("is_encrypted", False),
                "payload_data": session_info.get("payload_data"),
                "sequence_number": session_info.get("seq", 0),
                "encap_context": payload_analysis.get(
                    "encap_type", EncapsulationType.PLAIN
                ).value,
            }

            self.logger.debug(f"Extracted TCP session: {tcp_session['session_key']}")
            return tcp_session

        except Exception as e:
            self.logger.error(f"TCP session extraction failed: {str(e)}")
            return None

    def is_packet_encapsulated(self, packet: Packet) -> bool:
        """
        检查数据包是否包含封装

        Args:
            packet: 要检查的数据包

        Returns:
            True如果包含封装，False如果是无封装数据包
        """
        try:
            return self.detector.is_encapsulated(packet)
        except Exception:
            return False

    def get_encapsulation_summary(self, packet: Packet) -> Dict[str, Any]:
        """
        获取数据包封装摘要信息

        Args:
            packet: 要分析的数据包

        Returns:
            封装摘要信息
        """
        try:
            encap_result = self.parser.parse_packet_layers(packet)

            return {
                "encap_type": encap_result.encap_type.value,
                "has_encapsulation": encap_result.encap_type != EncapsulationType.PLAIN,
                "total_layers": len(encap_result.layers),
                "ip_count": len(encap_result.ip_layers),
                "has_vlan": encap_result.has_vlan(),
                "has_payload": encap_result.innermost_payload is not None,
                "parsing_success": encap_result.parsing_success,
                "error_message": encap_result.error_message,
            }

        except Exception as e:
            return {
                "encap_type": "unknown",
                "has_encapsulation": False,
                "total_layers": 0,
                "ip_count": 0,
                "has_vlan": False,
                "has_payload": False,
                "parsing_success": False,
                "error_message": str(e),
            }

    def get_processing_stats(self) -> Dict[str, Any]:
        """
        获取处理统计信息

        Returns:
            处理统计信息
        """
        return {
            "total_packets": self.stats["total_packets"],
            "encapsulated_packets": self.stats["encapsulated_packets"],
            "multi_ip_packets": self.stats["multi_ip_packets"],
            "encapsulation_distribution": dict(self.stats["encap_type_counts"]),
            "processing_errors": self.stats["processing_errors"],
            "encapsulation_ratio": (
                self.stats["encapsulated_packets"] / max(1, self.stats["total_packets"])
            ),
            "multi_ip_ratio": (
                self.stats["multi_ip_packets"] / max(1, self.stats["total_packets"])
            ),
            "error_ratio": (
                self.stats["processing_errors"] / max(1, self.stats["total_packets"])
            ),
        }

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            "total_packets": 0,
            "encapsulated_packets": 0,
            "multi_ip_packets": 0,
            "encap_type_counts": {},
            "processing_errors": 0,
        }
        self.logger.debug("Processing statistics reset")

    # === 私有辅助方法 ===

    def _update_encap_stats(self, encap_result: EncapsulationResult):
        """更新封装统计信息"""
        if encap_result.encap_type != EncapsulationType.PLAIN:
            self.stats["encapsulated_packets"] += 1

        if encap_result.has_multiple_ips():
            self.stats["multi_ip_packets"] += 1

        encap_type_name = encap_result.encap_type.value
        self.stats["encap_type_counts"][encap_type_name] = (
            self.stats["encap_type_counts"].get(encap_type_name, 0) + 1
        )

    def _generate_ip_processing_hints(
        self, encap_result: EncapsulationResult
    ) -> Dict[str, Any]:
        """生成IP处理提示"""
        hints = {
            "requires_multi_layer_processing": encap_result.has_multiple_ips(),
            "has_vlan": encap_result.has_vlan(),
            "encap_depth": encap_result.total_depth,
            "is_complex": encap_result.is_complex_encapsulation(),
            "recommended_strategy": self._recommend_ip_strategy(encap_result),
        }

        return hints

    def _generate_payload_processing_hints(
        self, encap_result: EncapsulationResult
    ) -> Dict[str, Any]:
        """生成载荷处理提示"""
        hints = {
            "requires_deep_inspection": encap_result.encap_type
            != EncapsulationType.PLAIN,
            "payload_accessible": encap_result.innermost_payload is not None,
            "is_encrypted": (
                encap_result.innermost_payload.is_encrypted
                if encap_result.innermost_payload
                else False
            ),
            "recommended_approach": self._recommend_payload_approach(encap_result),
        }

        return hints

    def _recommend_ip_strategy(self, encap_result: EncapsulationResult) -> str:
        """推荐IP处理策略"""
        if not encap_result.ip_layers:
            return "skip"
        elif len(encap_result.ip_layers) == 1:
            return "single_layer"
        else:
            return "multi_layer"

    def _recommend_payload_approach(self, encap_result: EncapsulationResult) -> str:
        """推荐载荷处理方法"""
        if not encap_result.innermost_payload:
            return "skip"
        elif encap_result.innermost_payload.is_encrypted:
            return "intelligent_trim"
        else:
            return "standard_trim"

    def _extract_tcp_session_info(
        self, encap_result: EncapsulationResult
    ) -> Optional[Dict[str, Any]]:
        """提取TCP会话信息"""
        if not encap_result.innermost_payload:
            return None

        payload = encap_result.innermost_payload
        if payload.protocol != "TCP":
            return None

        # 查找对应的IP层
        innermost_ip = encap_result.get_innermost_ip()
        if not innermost_ip:
            return None

        return {
            "src_ip": innermost_ip.src_ip,
            "dst_ip": innermost_ip.dst_ip,
            "src_port": payload.src_port,
            "dst_port": payload.dst_port,
            "payload_data": payload.payload_data,
            "seq": (
                getattr(payload.layer_object, "seq", 0) if payload.layer_object else 0
            ),
            "is_encrypted": payload.is_encrypted,
        }

    def _generate_session_key(self, session_info: Dict[str, Any]) -> str:
        """生成TCP会话键"""
        return f"{session_info['src_ip']}:{session_info['src_port']}-{session_info['dst_ip']}:{session_info['dst_port']}"

    def _create_fallback_ip_analysis(self, packet: Packet) -> Dict[str, Any]:
        """创建回退IP分析结果"""
        return {
            "encap_type": EncapsulationType.UNKNOWN,
            "has_encapsulation": False,
            "ip_layers": [],
            "total_ips": 0,
            "has_multiple_ips": False,
            "innermost_ip": None,
            "outermost_ip": None,
            "vlan_info": [],
            "processing_hints": {"requires_multi_layer_processing": False},
            "original_packet": packet,
            "encap_result": None,
        }

    def _create_fallback_payload_analysis(self, packet: Packet) -> Dict[str, Any]:
        """创建回退载荷分析结果"""
        return {
            "encap_type": EncapsulationType.UNKNOWN,
            "has_encapsulation": False,
            "innermost_payload": None,
            "has_payload": False,
            "is_encrypted": False,
            "transport_protocol": None,
            "payload_depth": 0,
            "tcp_session_info": None,
            "processing_hints": {"requires_deep_inspection": False},
            "original_packet": packet,
            "encap_result": None,
        }

    def _extract_fallback_ips(self, packet: Packet) -> List[Tuple[str, str, str]]:
        """回退IP提取方法"""
        try:
            from scapy.layers.inet import IP
            from scapy.layers.inet6 import IPv6

            ip_pairs = []

            # 简单的IP层查找
            if packet.haslayer(IP):
                ip_layer = packet[IP]
                ip_pairs.append((ip_layer.src, ip_layer.dst, "fallback_ipv4"))

            if packet.haslayer(IPv6):
                ipv6_layer = packet[IPv6]
                ip_pairs.append((ipv6_layer.src, ipv6_layer.dst, "fallback_ipv6"))

            return ip_pairs

        except Exception:
            return []
