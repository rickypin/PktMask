#!/usr/bin/env python3
"""
基于PyShark的TCP载荷提取器方案

利用现有的PyShark架构，完全避免Scapy的Raw层协议解析问题。
这个方案与当前的pyshark_analyzer.py完全兼容。
"""

import pyshark
import logging
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path


class PySharkPayloadExtractor:
    """基于PyShark的载荷提取器
    
    完全替代Scapy的Raw层方法，利用PyShark的直接载荷访问能力。
    与现有的PySharkAnalyzer架构兼容。
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化PyShark载荷提取器"""
        self.logger = logger or logging.getLogger(__name__)
        
        # 统计信息
        self.stats = {
            'packets_processed': 0,
            'tcp_packets_found': 0,
            'payloads_extracted': 0,
            'extraction_failures': 0,
            'payload_access_methods': {
                'binary_value': 0,
                'raw_value': 0,
                'tcp_len_fallback': 0
            }
        }
    
    def extract_tcp_payload_from_file(self, pcap_file: str) -> List[Dict[str, Any]]:
        """从PCAP文件中提取所有TCP载荷
        
        Args:
            pcap_file: PCAP文件路径
            
        Returns:
            List[Dict]: TCP载荷信息列表
        """
        extracted_payloads = []
        
        try:
            # 使用PyShark读取PCAP文件
            cap = pyshark.FileCapture(pcap_file)
            
            for packet in cap:
                payload_info = self.extract_single_packet_payload(packet)
                if payload_info:
                    extracted_payloads.append(payload_info)
            
            cap.close()
            
        except Exception as e:
            self.logger.error(f"PCAP文件读取失败: {e}")
            
        return extracted_payloads
    
    def extract_single_packet_payload(self, packet) -> Optional[Dict[str, Any]]:
        """从单个PyShark数据包提取TCP载荷
        
        Args:
            packet: PyShark数据包对象
            
        Returns:
            Optional[Dict]: 载荷信息字典，失败时返回None
        """
        self.stats['packets_processed'] += 1
        
        try:
            # 检查是否是TCP包
            if not hasattr(packet, 'tcp'):
                return None
            
            self.stats['tcp_packets_found'] += 1
            
            # 提取基本信息
            tcp_layer = packet.tcp
            ip_layer = packet.ip if hasattr(packet, 'ip') else packet.ipv6
            
            packet_number = int(packet.number)
            timestamp = float(packet.sniff_timestamp)
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            src_port = int(tcp_layer.srcport)
            dst_port = int(tcp_layer.dstport)
            sequence = int(tcp_layer.seq) if hasattr(tcp_layer, 'seq') else None
            
            # 生成流ID（与现有pyshark_analyzer兼容）
            stream_id = self._generate_stream_id(src_ip, dst_ip, src_port, dst_port)
            
            # 关键：提取TCP载荷 - 这里是解决Raw层问题的核心！
            payload_data, payload_length = self._extract_payload_data(tcp_layer, packet_number)
            
            if payload_data is None:
                return None
            
            self.stats['payloads_extracted'] += 1
            
            return {
                'packet_number': packet_number,
                'timestamp': timestamp,
                'stream_id': stream_id,
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'src_port': src_port,
                'dst_port': dst_port,
                'sequence': sequence,
                'payload_data': payload_data,
                'payload_length': payload_length,
                'payload_preview': payload_data[:16].hex() if len(payload_data) >= 16 else payload_data.hex()
            }
            
        except Exception as e:
            self.stats['extraction_failures'] += 1
            self.logger.warning(f"载荷提取失败 (包 {getattr(packet, 'number', 'unknown')}): {e}")
            return None
    
    def _extract_payload_data(self, tcp_layer, packet_number: int) -> Tuple[Optional[bytes], int]:
        """从TCP层提取载荷数据
        
        这是解决Scapy Raw层问题的核心方法！
        使用PyShark的多种载荷访问方法。
        
        Args:
            tcp_layer: PyShark TCP层对象
            packet_number: 数据包编号（用于日志）
            
        Returns:
            Tuple[Optional[bytes], int]: (载荷数据, 载荷长度)
        """
        # 方法1：尝试binary_value（最佳方法）
        if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
            try:
                if hasattr(tcp_layer.payload, 'binary_value'):
                    payload_data = tcp_layer.payload.binary_value
                    self.stats['payload_access_methods']['binary_value'] += 1
                    self.logger.debug(f"包{packet_number}: 使用binary_value获取载荷 {len(payload_data)}字节")
                    return payload_data, len(payload_data)
            except Exception as e:
                self.logger.debug(f"包{packet_number}: binary_value访问失败: {e}")
        
        # 方法2：尝试raw_value（十六进制字符串）
        if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
            try:
                if hasattr(tcp_layer.payload, 'raw_value'):
                    raw_hex = tcp_layer.payload.raw_value
                    payload_data = bytes.fromhex(raw_hex)
                    self.stats['payload_access_methods']['raw_value'] += 1
                    self.logger.debug(f"包{packet_number}: 使用raw_value获取载荷 {len(payload_data)}字节")
                    return payload_data, len(payload_data)
            except Exception as e:
                self.logger.debug(f"包{packet_number}: raw_value访问失败: {e}")
        
        # 方法3：回退到tcp.len计算（无实际载荷数据，但长度正确）
        if hasattr(tcp_layer, 'len'):
            try:
                payload_length = int(tcp_layer.len)
                if payload_length > 0:
                    self.stats['payload_access_methods']['tcp_len_fallback'] += 1
                    self.logger.debug(f"包{packet_number}: 使用tcp.len回退方法，载荷长度 {payload_length}字节")
                    # 返回零字节作为占位符（表示有载荷但无法提取内容）
                    return b'\x00' * payload_length, payload_length
            except Exception as e:
                self.logger.debug(f"包{packet_number}: tcp.len回退失败: {e}")
        
        # 所有方法都失败
        return None, 0
    
    def _generate_stream_id(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int) -> str:
        """生成流ID（与现有代码兼容）
        
        复制自pyshark_analyzer.py的逻辑，确保一致性。
        """
        # 确定方向（较小的IP:port组合作为"forward"方向）
        if (src_ip, src_port) < (dst_ip, dst_port):
            direction = "forward"
            stream_id = f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_{direction}"
        else:
            direction = "reverse"
            stream_id = f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}_{direction}"
        
        return stream_id
    
    def apply_mask_to_payload(self, payload_info: Dict[str, Any], keep_ranges: List[Tuple[int, int]]) -> bytes:
        """对载荷应用掩码
        
        Args:
            payload_info: 载荷信息字典
            keep_ranges: 保留范围列表 [(start, end), ...]
            
        Returns:
            bytes: 掩码后的载荷数据
        """
        original_payload = payload_info['payload_data']
        payload_length = len(original_payload)
        
        # 创建全零掩码
        masked_payload = bytearray(payload_length)
        
        # 应用保留范围
        for start, end in keep_ranges:
            # 确保范围在载荷长度内
            start = max(0, start)
            end = min(payload_length, end)
            
            if start < end:
                masked_payload[start:end] = original_payload[start:end]
        
        return bytes(masked_payload)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取提取统计信息"""
        stats = self.stats.copy()
        
        # 计算成功率
        if stats['packets_processed'] > 0:
            stats['tcp_packet_rate'] = stats['tcp_packets_found'] / stats['packets_processed']
            stats['extraction_success_rate'] = stats['payloads_extracted'] / stats['packets_processed']
        
        if stats['tcp_packets_found'] > 0:
            stats['tcp_payload_rate'] = stats['payloads_extracted'] / stats['tcp_packets_found']
        
        return stats


class PySharkTcpMasker:
    """基于PyShark的TCP掩码器
    
    完整的TCP载荷掩码处理器，使用PyShark替代Scapy。
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化PyShark TCP掩码器"""
        self.logger = logger or logging.getLogger(__name__)
        self.extractor = PySharkPayloadExtractor(logger)
    
    def process_pcap_with_mask_config(self, input_pcap: str, output_pcap: str, mask_config: Dict[str, Any]) -> Dict[str, Any]:
        """使用掩码配置处理PCAP文件
        
        Args:
            input_pcap: 输入PCAP文件路径
            output_pcap: 输出PCAP文件路径
            mask_config: 掩码配置字典
            
        Returns:
            Dict: 处理结果统计
        """
        try:
            # 1. 使用PyShark提取所有TCP载荷
            self.logger.info("使用PyShark提取TCP载荷...")
            payloads = self.extractor.extract_tcp_payload_from_file(input_pcap)
            self.logger.info(f"提取到 {len(payloads)} 个TCP载荷")
            
            # 2. 应用掩码规则
            modified_count = 0
            masked_bytes = 0
            kept_bytes = 0
            
            for payload_info in payloads:
                # 查找匹配的掩码规则
                mask_rule = self._find_matching_rule(payload_info, mask_config)
                
                if mask_rule:
                    # 应用掩码
                    keep_ranges = mask_rule.get('keep_ranges', [])
                    masked_payload = self.extractor.apply_mask_to_payload(payload_info, keep_ranges)
                    
                    # 更新统计
                    modified_count += 1
                    original_length = len(payload_info['payload_data'])
                    kept_length = sum(min(end, original_length) - max(start, 0) 
                                     for start, end in keep_ranges 
                                     if max(start, 0) < min(end, original_length))
                    
                    masked_bytes += original_length - kept_length
                    kept_bytes += kept_length
                    
                    # 更新载荷信息
                    payload_info['masked_payload'] = masked_payload
                    payload_info['was_modified'] = True
                else:
                    payload_info['was_modified'] = False
            
            # 3. 重建PCAP文件（这里需要与Scapy集成或使用其他方法）
            self._rebuild_pcap_file(input_pcap, output_pcap, payloads)
            
            # 4. 返回处理统计
            return {
                'total_packets': len(payloads),
                'modified_packets': modified_count,
                'masked_bytes': masked_bytes,
                'kept_bytes': kept_bytes,
                'extraction_stats': self.extractor.get_statistics()
            }
            
        except Exception as e:
            self.logger.error(f"PCAP处理失败: {e}")
            raise
    
    def _find_matching_rule(self, payload_info: Dict[str, Any], mask_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """查找匹配的掩码规则"""
        # 实现掩码规则匹配逻辑
        # 这里可以复用现有的keep_range_table逻辑
        pass
    
    def _rebuild_pcap_file(self, input_pcap: str, output_pcap: str, modified_payloads: List[Dict[str, Any]]):
        """重建PCAP文件
        
        这里可能仍需要Scapy进行最终的文件写入，
        但载荷提取完全使用PyShark，避免了Raw层问题。
        """
        # 实现PCAP重建逻辑
        pass


# 使用示例
def demo_pyshark_payload_extraction():
    """演示PyShark载荷提取的使用方法"""
    
    # 创建提取器
    extractor = PySharkPayloadExtractor()
    
    # 提取测试文件的载荷
    test_file = "tests/data/tls-single/tls_sample.pcap"
    payloads = extractor.extract_tcp_payload_from_file(test_file)
    
    print(f"提取到 {len(payloads)} 个TCP载荷:")
    for payload in payloads[:5]:  # 只显示前5个
        print(f"  包{payload['packet_number']}: {payload['stream_id']}")
        print(f"    序列号: {payload['sequence']}")
        print(f"    载荷长度: {payload['payload_length']}字节")
        print(f"    载荷预览: {payload['payload_preview']}")
        print()
    
    # 显示统计信息
    stats = extractor.get_statistics()
    print("提取统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    demo_pyshark_payload_extraction() 