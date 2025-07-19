"""
协议栈解析器

递归解析多层协议栈，提取所有层级的IP地址信息，定位最内层的TCP/UDP载荷。
支持复杂的封装嵌套和多层IP地址处理。
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from scapy.packet import Packet
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.inet6 import IPv6
from scapy.layers.l2 import Ether, Dot1Q
try:
    from scapy.layers.l2 import Dot1AD
except ImportError:
    Dot1AD = None
from scapy.contrib.mpls import MPLS
try:
    from scapy.contrib.vxlan import VXLAN
except ImportError:
    VXLAN = None
from scapy.layers.inet import GRE
from scapy.layers.tls.record import TLS

from .types import (
    LayerInfo, IPLayerInfo, PayloadInfo, VLANInfo, EncapsulationResult,
    EncapsulationType, ParsingError
)
from .detector import EncapsulationDetector
from ...config.settings import get_app_config


class ProtocolStackParser:
    """
    协议栈解析器
    
    负责递归解析多层协议栈，提取：
    - 所有协议层信息
    - 多层IP地址信息  
    - 最内层TCP/UDP载荷
    - VLAN信息
    """
    
    def __init__(self):
        """初始化解析器"""
        self.logger = logging.getLogger(__name__)
        self.detector = EncapsulationDetector()

        # 获取配置以控制日志输出
        try:
            self.config = get_app_config()
            self.enable_parsing_logs = self.config.logging.enable_protocol_parsing_logs
        except Exception as e:
            # 如果配置获取失败，默认关闭详细日志
            self.logger.warning(f"Failed to get configuration, using default log settings: {e}")
            self.enable_parsing_logs = False

        # 协议层解析器映射
        self._layer_parsers = {
            'Ether': self._parse_ethernet,
            'Dot1Q': self._parse_vlan,
            'Dot1AD': self._parse_double_vlan,
            'MPLS': self._parse_mpls,
            'VXLAN': self._parse_vxlan,
            'GRE': self._parse_gre,
            'IP': self._parse_ipv4,
            'IPv6': self._parse_ipv6,
            'TCP': self._parse_tcp,
            'UDP': self._parse_udp,
        }
        
    def parse_packet_layers(self, packet: Packet) -> EncapsulationResult:
        """
        递归解析所有协议层
        
        Args:
            packet: 要解析的数据包
            
        Returns:
            完整的封装解析结果
            
        Raises:
            ParsingError: 解析失败
        """
        try:
            self.logger.debug("Starting protocol stack parsing")
            
            # 检测封装类型
            encap_type = self.detector.detect_encapsulation_type(packet)
            
            # 解析所有层
            layers = []
            ip_layers = []
            vlan_info = []
            current_layer = packet
            depth = 0
            
            while current_layer and depth < 20:  # 防止无限循环
                layer_name = current_layer.__class__.__name__
                
                # 解析当前层
                layer_info = self._parse_single_layer(current_layer, depth, encap_type)
                if layer_info:
                    layers.append(layer_info)
                    
                    # 收集IP层信息
                    if layer_name in ['IP', 'IPv6']:
                        ip_info = self._extract_ip_info(current_layer, depth, encap_type)
                        if ip_info:
                            ip_layers.append(ip_info)
                    
                    # 收集VLAN信息
                    elif layer_name in ['Dot1Q', 'Dot1AD']:
                        vlan = self._extract_vlan_info(current_layer, depth)
                        if vlan:
                            vlan_info.append(vlan)
                
                # 移动到下一层
                if hasattr(current_layer, 'payload') and current_layer.payload:
                    current_layer = current_layer.payload
                    depth += 1
                else:
                    break
            
            # 标记最内层IP
            if ip_layers:
                innermost_ip = max(ip_layers, key=lambda ip: ip.layer_depth)
                innermost_ip.is_innermost = True
            
            # 查找最内层载荷
            innermost_payload = self._find_innermost_payload(packet, layers)
            
            result = EncapsulationResult(
                encap_type=encap_type,
                layers=layers,
                ip_layers=ip_layers,
                innermost_payload=innermost_payload,
                vlan_info=vlan_info,
                total_depth=depth,
                parsing_success=True
            )
            
            # 根据配置决定是否输出详细日志
            if self.enable_parsing_logs:
                self.logger.info(f"Protocol stack parsing completed: {len(layers)} layers, {len(ip_layers)} IP layers")
            return result
            
        except Exception as e:
            error_msg = f"Protocol stack parsing failed: {str(e)}"
            self.logger.error(error_msg)
            
            # 返回失败结果
            return EncapsulationResult(
                encap_type=EncapsulationType.UNKNOWN,
                layers=[],
                ip_layers=[],
                innermost_payload=None,
                vlan_info=[],
                total_depth=0,
                parsing_success=False,
                error_message=error_msg
            )
    
    def extract_all_ip_addresses(self, packet: Packet) -> List[IPLayerInfo]:
        """
        提取所有层级的IP地址
        
        Args:
            packet: 要分析的数据包
            
        Returns:
            所有IP层信息列表
        """
        try:
            result = self.parse_packet_layers(packet)
            return result.ip_layers
        except Exception as e:
            self.logger.warning(f"IP address extraction failed: {str(e)}")
            return []
    
    def find_innermost_payload(self, packet: Packet) -> Optional[PayloadInfo]:
        """
        定位最内层TCP/UDP载荷
        
        Args:
            packet: 要分析的数据包
            
        Returns:
            最内层载荷信息，如果没有则返回None
        """
        try:
            result = self.parse_packet_layers(packet)
            return result.innermost_payload
        except Exception as e:
            self.logger.warning(f"Payload location failed: {str(e)}")
            return None
    
    # === 单层解析方法 ===
    
    def _parse_single_layer(self, layer: Packet, depth: int, encap_type: EncapsulationType) -> Optional[LayerInfo]:
        """解析单个协议层"""
        try:
            layer_name = layer.__class__.__name__
            parser = self._layer_parsers.get(layer_name)
            
            if parser:
                return parser(layer, depth, encap_type)
            else:
                # 通用解析
                return LayerInfo(
                    layer_type=layer_name,
                    layer_object=layer,
                    encap_type=encap_type,
                    depth=depth,
                    properties={}
                )
                
        except Exception as e:
            self.logger.warning(f"Failed to parse layer {layer.__class__.__name__}: {str(e)}")
            return None
    
    def _parse_ethernet(self, layer: Ether, depth: int, encap_type: EncapsulationType) -> LayerInfo:
        """解析以太网层"""
        properties = {
            'src_mac': layer.src,
            'dst_mac': layer.dst,
            'ether_type': hex(layer.type) if hasattr(layer, 'type') else None
        }
        
        return LayerInfo(
            layer_type='Ether',
            layer_object=layer,
            encap_type=encap_type,
            depth=depth,
            properties=properties
        )
    
    def _parse_vlan(self, layer: Dot1Q, depth: int, encap_type: EncapsulationType) -> LayerInfo:
        """解析VLAN层 (802.1Q)"""
        properties = {
            'vlan_id': layer.vlan,
            'priority': layer.prio,
            'dei': bool(layer.id),
            'type': hex(layer.type) if hasattr(layer, 'type') else None
        }
        
        return LayerInfo(
            layer_type='Dot1Q',
            layer_object=layer,
            encap_type=EncapsulationType.VLAN,
            depth=depth,
            properties=properties
        )
    
    def _parse_double_vlan(self, layer, depth: int, encap_type: EncapsulationType) -> LayerInfo:
        """解析双层VLAN层 (802.1ad)"""
        if Dot1AD and isinstance(layer, Dot1AD):
            properties = {
                'outer_vlan_id': getattr(layer, 'vlan', None),
                'outer_priority': getattr(layer, 'prio', None),
                'outer_dei': bool(getattr(layer, 'id', 0)),
                'type': hex(layer.type) if hasattr(layer, 'type') else None
            }
            layer_type = 'Dot1AD'
        else:
            # 处理为连续Dot1Q的情况
            properties = {
                'vlan_id': getattr(layer, 'vlan', None),
                'priority': getattr(layer, 'prio', None),
                'dei': bool(getattr(layer, 'id', 0)),
                'type': hex(layer.type) if hasattr(layer, 'type') else None,
                'is_outer_vlan': True
            }
            layer_type = 'Dot1Q'
        
        return LayerInfo(
            layer_type=layer_type,
            layer_object=layer,
            encap_type=EncapsulationType.DOUBLE_VLAN,
            depth=depth,
            properties=properties
        )
    
    def _parse_mpls(self, layer: MPLS, depth: int, encap_type: EncapsulationType) -> LayerInfo:
        """解析MPLS层"""
        properties = {
            'label': layer.label,
            'cos': layer.cos,
            'bottom_of_stack': bool(layer.s),
            'ttl': layer.ttl
        }
        
        return LayerInfo(
            layer_type='MPLS',
            layer_object=layer,
            encap_type=EncapsulationType.MPLS,
            depth=depth,
            properties=properties
        )
    
    def _parse_vxlan(self, layer, depth: int, encap_type: EncapsulationType) -> LayerInfo:
        """解析VXLAN层"""
        if VXLAN and isinstance(layer, VXLAN):
            properties = {
                'vni': getattr(layer, 'vni', None),
                'flags': getattr(layer, 'flags', None),
                'reserved': getattr(layer, 'reserved1', None)
            }
        else:
            properties = {}
        
        return LayerInfo(
            layer_type='VXLAN',
            layer_object=layer,
            encap_type=EncapsulationType.VXLAN,
            depth=depth,
            properties=properties
        )
    
    def _parse_gre(self, layer: GRE, depth: int, encap_type: EncapsulationType) -> LayerInfo:
        """解析GRE层"""
        properties = {
            'proto': hex(layer.proto) if hasattr(layer, 'proto') else None,
            'chksum_present': bool(getattr(layer, 'chksum_present', 0)),
            'key_present': bool(getattr(layer, 'key_present', 0)),
            'seqnum_present': bool(getattr(layer, 'seqnum_present', 0))
        }
        
        if hasattr(layer, 'key'):
            properties['key'] = layer.key
        
        return LayerInfo(
            layer_type='GRE',
            layer_object=layer,
            encap_type=EncapsulationType.GRE,
            depth=depth,
            properties=properties
        )
    
    def _parse_ipv4(self, layer: IP, depth: int, encap_type: EncapsulationType) -> LayerInfo:
        """解析IPv4层"""
        properties = {
            'src_ip': layer.src,
            'dst_ip': layer.dst,
            'version': layer.version,
            'ihl': layer.ihl,
            'tos': layer.tos,
            'len': layer.len,
            'id': layer.id,
            'flags': layer.flags,
            'frag': layer.frag,
            'ttl': layer.ttl,
            'proto': layer.proto
        }
        
        return LayerInfo(
            layer_type='IP',
            layer_object=layer,
            encap_type=encap_type,
            depth=depth,
            properties=properties
        )
    
    def _parse_ipv6(self, layer: IPv6, depth: int, encap_type: EncapsulationType) -> LayerInfo:
        """解析IPv6层"""
        properties = {
            'src_ip': layer.src,
            'dst_ip': layer.dst,
            'version': layer.version,
            'tc': layer.tc,
            'fl': layer.fl,
            'plen': layer.plen,
            'nh': layer.nh,
            'hlim': layer.hlim
        }
        
        return LayerInfo(
            layer_type='IPv6',
            layer_object=layer,
            encap_type=encap_type,
            depth=depth,
            properties=properties
        )
    
    def _parse_tcp(self, layer: TCP, depth: int, encap_type: EncapsulationType) -> LayerInfo:
        """解析TCP层"""
        properties = {
            'sport': layer.sport,
            'dport': layer.dport,
            'seq': layer.seq,
            'ack': layer.ack,
            'dataofs': layer.dataofs,
            'flags': layer.flags,
            'window': layer.window,
            'chksum': layer.chksum,
            'urgptr': layer.urgptr
        }
        
        return LayerInfo(
            layer_type='TCP',
            layer_object=layer,
            encap_type=encap_type,
            depth=depth,
            properties=properties
        )
    
    def _parse_udp(self, layer: UDP, depth: int, encap_type: EncapsulationType) -> LayerInfo:
        """解析UDP层"""
        properties = {
            'sport': layer.sport,
            'dport': layer.dport,
            'len': layer.len,
            'chksum': layer.chksum
        }
        
        return LayerInfo(
            layer_type='UDP',
            layer_object=layer,
            encap_type=encap_type,
            depth=depth,
            properties=properties
        )
    
    # === 信息提取方法 ===
    
    def _extract_ip_info(self, ip_layer: Packet, depth: int, encap_type: EncapsulationType) -> Optional[IPLayerInfo]:
        """提取IP层信息"""
        try:
            if isinstance(ip_layer, IP):
                return IPLayerInfo(
                    src_ip=ip_layer.src,
                    dst_ip=ip_layer.dst,
                    layer_depth=depth,
                    ip_version=4,
                    encap_context=encap_type.value,
                    layer_object=ip_layer
                )
            elif isinstance(ip_layer, IPv6):
                return IPLayerInfo(
                    src_ip=ip_layer.src,
                    dst_ip=ip_layer.dst,
                    layer_depth=depth,
                    ip_version=6,
                    encap_context=encap_type.value,
                    layer_object=ip_layer
                )
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to extract IP information: {str(e)}")
            return None
    
    def _extract_vlan_info(self, vlan_layer: Packet, depth: int) -> Optional[VLANInfo]:
        """提取VLAN信息"""
        try:
            if isinstance(vlan_layer, Dot1Q):
                return VLANInfo(
                    vlan_id=vlan_layer.vlan,
                    priority=vlan_layer.prio,
                    dei=bool(vlan_layer.id),
                    tpid=0x8100,  # 标准802.1Q
                    is_outer=False
                )
            elif Dot1AD and isinstance(vlan_layer, Dot1AD):
                return VLANInfo(
                    vlan_id=getattr(vlan_layer, 'vlan', 0),
                    priority=getattr(vlan_layer, 'prio', 0),
                    dei=bool(getattr(vlan_layer, 'id', 0)),
                    tpid=0x88a8,  # 802.1ad
                    is_outer=True
                )
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to extract VLAN information: {str(e)}")
            return None
    
    def _find_innermost_payload(self, packet: Packet, layers: List[LayerInfo]) -> Optional[PayloadInfo]:
        """查找最内层载荷"""
        try:
            # 查找最深层的TCP或UDP
            tcp_udp_layers = [layer for layer in layers if layer.layer_type in ['TCP', 'UDP']]
            
            if not tcp_udp_layers:
                return None
            
            # 选择最深层的传输层
            innermost_transport = max(tcp_udp_layers, key=lambda layer: layer.depth)
            transport_layer = innermost_transport.layer_object
            
            # 检查是否有载荷
            if not hasattr(transport_layer, 'payload') or not transport_layer.payload:
                return None
            
            payload_data = bytes(transport_layer.payload)
            if not payload_data:
                return None
            
            # 检查是否为TLS
            is_encrypted = False
            try:
                if transport_layer.payload.haslayer(TLS):
                    is_encrypted = True
            except:
                # 简单的TLS检测 - 检查载荷是否以TLS记录头开始
                if len(payload_data) >= 5:
                    # TLS记录头格式: [类型(1字节)][版本(2字节)][长度(2字节)]
                    record_type = payload_data[0]
                    version = int.from_bytes(payload_data[1:3], 'big')
                    if record_type in [20, 21, 22, 23] and version in [0x0301, 0x0302, 0x0303, 0x0304]:
                        is_encrypted = True
            
            return PayloadInfo(
                payload_data=payload_data,
                layer_depth=innermost_transport.depth + 1,
                protocol=innermost_transport.layer_type,
                src_port=getattr(transport_layer, 'sport', None),
                dst_port=getattr(transport_layer, 'dport', None),
                is_encrypted=is_encrypted,
                layer_object=transport_layer.payload
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to find payload: {str(e)}")
            return None 