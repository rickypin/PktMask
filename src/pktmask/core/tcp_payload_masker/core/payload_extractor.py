"""
独立PCAP掩码处理器载荷提取器

在协议解析禁用的情况下，从数据包中提取TCP载荷和流信息。
这是Phase 4的核心组件之一。
"""

import struct
from typing import Optional, Tuple, Dict, Any
import logging
from scapy.all import Packet, Raw, Ether, IP, IPv6, TCP, UDP

from ..exceptions import ValidationError, IndependentMaskerError


class PayloadExtractor:
    """载荷提取器
    
    专门用于在协议解析禁用情况下提取TCP载荷。
    由于协议解析被禁用，所有上层协议载荷都以Raw格式存在。
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化载荷提取器
        
        Args:
            logger: 可选的日志器实例
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # 统计信息
        self.stats = {
            'packets_processed': 0,
            'tcp_packets_found': 0,
            'payloads_extracted': 0,
            'raw_layers_found': 0,
            'extraction_failures': 0
        }
    
    def extract_tcp_payload(self, packet: Packet) -> Optional[bytes]:
        """从数据包中提取TCP载荷
        
        Args:
            packet: Scapy数据包对象
            
        Returns:
            Optional[bytes]: TCP载荷字节，如果不是TCP包或没有载荷则返回None
        """
        self.stats['packets_processed'] += 1
        
        try:
            # 检查是否是TCP包
            if not self._is_tcp_packet(packet):
                return None
            
            self.stats['tcp_packets_found'] += 1
            
            # 由于协议解析被禁用，载荷应该在Raw层
            raw_layer = packet.getlayer(Raw)
            if raw_layer is None:
                self.logger.debug(f"TCP包没有Raw层，包ID: {self._get_packet_id(packet)}")
                return None
            
            self.stats['raw_layers_found'] += 1
            
            # 提取Raw载荷
            payload = bytes(raw_layer.load)
            
            if len(payload) > 0:
                self.stats['payloads_extracted'] += 1
                self.logger.debug(f"提取到载荷 {len(payload)} 字节，包ID: {self._get_packet_id(packet)}")
            
            return payload if len(payload) > 0 else None
            
        except Exception as e:
            self.stats['extraction_failures'] += 1
            self.logger.warning(f"载荷提取失败: {e}")
            return None
    
    def extract_stream_info(self, packet: Packet) -> Optional[Tuple[str, int, bytes]]:
        """提取流信息和载荷
        
        Args:
            packet: Scapy数据包对象
            
        Returns:
            Optional[Tuple[str, int, bytes]]: (stream_id, sequence_number, payload)
            如果提取失败则返回None
        """
        try:
            # 提取载荷
            payload = self.extract_tcp_payload(packet)
            if payload is None:
                return None
            
            # 生成流ID
            stream_id = self._generate_stream_id(packet)
            if stream_id is None:
                return None
            
            # 获取序列号
            sequence = self._get_sequence_number(packet)
            if sequence is None:
                return None
            
            return stream_id, sequence, payload
            
        except Exception as e:
            self.logger.warning(f"流信息提取失败: {e}")
            return None
    
    def _is_tcp_packet(self, packet: Packet) -> bool:
        """检查是否是TCP包"""
        try:
            # 检查IP层
            ip_layer = packet.getlayer(IP) or packet.getlayer(IPv6)
            if ip_layer is None:
                return False
            
            # 检查TCP层
            tcp_layer = packet.getlayer(TCP)
            return tcp_layer is not None
            
        except Exception:
            return False
    
    def _generate_stream_id(self, packet: Packet) -> Optional[str]:
        """生成TCP流ID
        
        格式: "TCP_src_ip:port_dst_ip:port_direction"
        """
        try:
            # 获取IP信息
            ip_layer = packet.getlayer(IP) or packet.getlayer(IPv6)
            tcp_layer = packet.getlayer(TCP)
            
            if ip_layer is None or tcp_layer is None:
                return None
            
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            src_port = tcp_layer.sport
            dst_port = tcp_layer.dport
            
            # 确定方向（较小的IP:port组合作为"forward"方向）
            if (src_ip, src_port) < (dst_ip, dst_port):
                direction = "forward"
                stream_id = f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_{direction}"
            else:
                direction = "reverse"
                stream_id = f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}_{direction}"
            
            return stream_id
            
        except Exception as e:
            self.logger.warning(f"流ID生成失败: {e}")
            return None
    
    def _get_sequence_number(self, packet: Packet) -> Optional[int]:
        """获取TCP序列号"""
        try:
            tcp_layer = packet.getlayer(TCP)
            if tcp_layer is None:
                return None
            
            return tcp_layer.seq
            
        except Exception as e:
            self.logger.warning(f"序列号获取失败: {e}")
            return None
    
    def _get_packet_id(self, packet: Packet) -> str:
        """获取数据包标识符用于日志"""
        try:
            ip_layer = packet.getlayer(IP) or packet.getlayer(IPv6)
            tcp_layer = packet.getlayer(TCP)
            
            if ip_layer and tcp_layer:
                return f"{ip_layer.src}:{tcp_layer.sport}->{ip_layer.dst}:{tcp_layer.dport}"
            else:
                return f"packet_{id(packet)}"
                
        except Exception:
            return f"packet_{id(packet)}"
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取提取统计信息"""
        stats = self.stats.copy()
        
        # 计算成功率
        if stats['packets_processed'] > 0:
            stats['tcp_packet_rate'] = stats['tcp_packets_found'] / stats['packets_processed']
            stats['extraction_success_rate'] = stats['payloads_extracted'] / stats['packets_processed']
        
        if stats['tcp_packets_found'] > 0:
            stats['raw_layer_availability'] = stats['raw_layers_found'] / stats['tcp_packets_found']
            stats['tcp_payload_rate'] = stats['payloads_extracted'] / stats['tcp_packets_found']
        
        return stats
    
    def reset_statistics(self) -> None:
        """重置统计信息"""
        self.stats = {
            'packets_processed': 0,
            'tcp_packets_found': 0,
            'payloads_extracted': 0,
            'raw_layers_found': 0,
            'extraction_failures': 0
        }
        self.logger.debug("载荷提取器统计信息已重置")
    
    def verify_raw_layer_dominance(self, packets: list) -> Dict[str, Any]:
        """验证Raw层在TCP包中的存在率
        
        这用于验证协议解析禁用的效果。
        
        Args:
            packets: 要验证的数据包列表
            
        Returns:
            Dict: 验证结果
        """
        tcp_count = 0
        raw_count = 0
        
        for packet in packets:
            if self._is_tcp_packet(packet):
                tcp_count += 1
                if packet.getlayer(Raw) is not None:
                    raw_count += 1
        
        raw_rate = raw_count / tcp_count if tcp_count > 0 else 0.0
        
        return {
            'total_packets': len(packets),
            'tcp_packets': tcp_count,
            'tcp_with_raw': raw_count,
            'raw_layer_rate': raw_rate,
            'protocol_parsing_disabled': raw_rate >= 0.95  # 95%以上表示成功禁用
        }


def create_payload_extractor(logger: Optional[logging.Logger] = None) -> PayloadExtractor:
    """创建载荷提取器实例的工厂函数
    
    Args:
        logger: 可选的日志器实例
        
    Returns:
        PayloadExtractor: 配置好的载荷提取器实例
    """
    return PayloadExtractor(logger) 