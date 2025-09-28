"""
封装处理的类型定义和数据结构

定义了多层封装处理所需的所有数据类型、枚举和数据类。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from scapy.packet import Packet


class EncapsulationType(Enum):
    """支持的封装类型枚举"""

    PLAIN = "plain"  # 无封装 (直接IP)
    VLAN = "vlan"  # VLAN封装 (802.1Q)
    DOUBLE_VLAN = "double_vlan"  # 双层VLAN封装 (QinQ/802.1ad)
    MPLS = "mpls"  # MPLS封装
    VXLAN = "vxlan"  # VXLAN封装
    GRE = "gre"  # GRE隧道
    COMPOSITE = "composite"  # 复合封装(多种封装组合)
    UNKNOWN = "unknown"  # 未知或不支持的封装


@dataclass
class LayerInfo:
    """协议层信息"""

    layer_type: str  # 层类型名称 (如 "Dot1Q", "MPLS", "IP")
    layer_object: Packet  # Scapy层对象
    encap_type: EncapsulationType  # 对应的封装类型
    depth: int  # 层深度 (0为最外层)
    properties: Dict[str, Any]  # 层的额外属性


@dataclass
class IPLayerInfo:
    """IP层信息"""

    src_ip: str  # 源IP地址
    dst_ip: str  # 目标IP地址
    layer_depth: int  # IP层在协议栈中的深度
    ip_version: int  # IP版本 (4 或 6)
    encap_context: str  # IP所在的封装上下文
    layer_object: Packet  # IP层的Scapy对象
    is_innermost: bool = False  # 是否为最内层IP


@dataclass
class PayloadInfo:
    """载荷信息"""

    payload_data: bytes  # 载荷数据
    layer_depth: int  # 载荷所在层深度
    protocol: str  # 载荷协议类型 (TCP/UDP)
    src_port: Optional[int] = None  # 源端口
    dst_port: Optional[int] = None  # 目标端口
    is_encrypted: bool = False  # 是否为加密载荷 (如TLS)
    layer_object: Optional[Packet] = None  # 载荷层的Scapy对象


@dataclass
class VLANInfo:
    """VLAN信息"""

    vlan_id: int  # VLAN ID
    priority: int  # 优先级
    dei: bool  # Drop Eligible Indicator
    tpid: int  # Tag Protocol Identifier
    is_outer: bool = False  # 是否为外层VLAN (用于双层VLAN)


@dataclass
class EncapsulationResult:
    """封装解析结果"""

    encap_type: EncapsulationType  # 检测到的封装类型
    layers: List[LayerInfo]  # 所有协议层信息
    ip_layers: List[IPLayerInfo]  # 所有IP层信息
    innermost_payload: Optional[PayloadInfo]  # 最内层载荷信息
    vlan_info: List[VLANInfo]  # VLAN信息 (如果存在)
    total_depth: int  # 总协议栈深度
    parsing_success: bool  # 解析是否成功
    error_message: Optional[str] = None  # 错误信息 (如果解析失败)

    def get_innermost_ip(self) -> Optional[IPLayerInfo]:
        """获取最内层IP信息"""
        if not self.ip_layers:
            return None
        return max(self.ip_layers, key=lambda ip: ip.layer_depth)

    def get_outermost_ip(self) -> Optional[IPLayerInfo]:
        """获取最外层IP信息"""
        if not self.ip_layers:
            return None
        return min(self.ip_layers, key=lambda ip: ip.layer_depth)

    def has_vlan(self) -> bool:
        """是否包含VLAN封装"""
        return self.encap_type in [
            EncapsulationType.VLAN,
            EncapsulationType.DOUBLE_VLAN,
        ] or any(layer.encap_type in [EncapsulationType.VLAN, EncapsulationType.DOUBLE_VLAN] for layer in self.layers)

    def has_multiple_ips(self) -> bool:
        """是否包含多层IP"""
        return len(self.ip_layers) > 1

    def is_complex_encapsulation(self) -> bool:
        """是否为复杂封装 (多层或复合)"""
        return self.encap_type == EncapsulationType.COMPOSITE or self.total_depth > 3 or self.has_multiple_ips()


class EncapsulationError(Exception):
    """封装处理相关异常"""


class UnsupportedEncapsulationError(EncapsulationError):
    """不支持的封装类型异常"""


class ParsingError(EncapsulationError):
    """协议解析异常"""
