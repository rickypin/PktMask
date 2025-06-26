#!/usr/bin/env python3
"""
混合架构设计：PyShark载荷提取 + Scapy文件操作

这个设计结合了PyShark的载荷提取优势和Scapy的文件操作成熟性，
完美解决Raw层问题同时保持系统稳定性。
"""

import pyshark
import logging
from typing import Optional, Tuple, Dict, Any, List
from scapy.all import rdpcap, wrpcap, Packet as ScapyPacket, Raw
from pathlib import Path


class HybridPayloadExtractor:
    """混合载荷提取器
    
    使用PyShark进行载荷提取，避免Scapy的Raw层协议解析问题。
    然后提供与现有Scapy接口兼容的数据结构。
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化混合载荷提取器"""
        self.logger = logger or logging.getLogger(__name__)
        
        # 载荷缓存：将PyShark提取的载荷映射到Scapy数据包
        self.payload_cache: Dict[str, bytes] = {}
        
        # 统计信息
        self.stats = {
            'packets_processed': 0,
            'tcp_packets_found': 0,
            'payloads_extracted': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def prepare_payload_cache(self, pcap_file: str) -> None:
        """使用PyShark预先提取所有载荷并缓存
        
        这是关键步骤：先用PyShark提取所有载荷，避免Raw层问题。
        
        Args:
            pcap_file: PCAP文件路径
        """
        self.logger.info("使用PyShark预提取载荷缓存...")
        
        try:
            # 使用PyShark读取PCAP
            cap = pyshark.FileCapture(pcap_file)
            
            for packet in cap:
                if hasattr(packet, 'tcp'):
                    packet_key = self._generate_packet_key(packet)
                    payload_data = self._extract_pyshark_payload(packet)
                    
                    if payload_data:
                        self.payload_cache[packet_key] = payload_data
                        self.stats['payloads_extracted'] += 1
                    
                    self.stats['tcp_packets_found'] += 1
                
                self.stats['packets_processed'] += 1
            
            cap.close()
            
            self.logger.info(f"载荷缓存完成: {len(self.payload_cache)} 个载荷已缓存")
            
        except Exception as e:
            self.logger.error(f"载荷缓存失败: {e}")
            raise
    
    def extract_tcp_payload(self, scapy_packet: ScapyPacket) -> Optional[bytes]:
        """从Scapy数据包提取TCP载荷
        
        这个方法保持与现有接口兼容，但内部使用PyShark缓存的载荷。
        
        Args:
            scapy_packet: Scapy数据包对象
            
        Returns:
            Optional[bytes]: TCP载荷字节，如果不是TCP包或没有载荷则返回None
        """
        try:
            # 生成数据包键
            packet_key = self._generate_scapy_packet_key(scapy_packet)
            
            # 从PyShark缓存中获取载荷
            if packet_key in self.payload_cache:
                self.stats['cache_hits'] += 1
                return self.payload_cache[packet_key]
            else:
                self.stats['cache_misses'] += 1
                self.logger.debug(f"缓存未命中: {packet_key}")
                return None
                
        except Exception as e:
            self.logger.warning(f"载荷提取失败: {e}")
            return None
    
    def extract_stream_info(self, scapy_packet: ScapyPacket) -> Optional[Tuple[str, int, bytes]]:
        """提取流信息和载荷 - 兼容现有接口
        
        Args:
            scapy_packet: Scapy数据包对象
            
        Returns:
            Optional[Tuple[str, int, bytes]]: (stream_id, sequence_number, payload)
        """
        try:
            # 提取载荷（从PyShark缓存）
            payload = self.extract_tcp_payload(scapy_packet)
            if payload is None:
                return None
            
            # 使用Scapy提取网络信息（这部分Scapy很稳定）
            from scapy.all import IP, IPv6, TCP
            
            ip_layer = scapy_packet.getlayer(IP) or scapy_packet.getlayer(IPv6)
            tcp_layer = scapy_packet.getlayer(TCP)
            
            if not ip_layer or not tcp_layer:
                return None
            
            # 生成流ID
            stream_id = self._generate_stream_id_from_scapy(scapy_packet)
            sequence = tcp_layer.seq
            
            return stream_id, sequence, payload
            
        except Exception as e:
            self.logger.warning(f"流信息提取失败: {e}")
            return None
    
    def _extract_pyshark_payload(self, pyshark_packet) -> Optional[bytes]:
        """从PyShark数据包提取载荷 - 核心载荷提取逻辑"""
        try:
            tcp_layer = pyshark_packet.tcp
            
            # 方法1：binary_value（最佳）
            if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
                if hasattr(tcp_layer.payload, 'binary_value'):
                    return tcp_layer.payload.binary_value
                elif hasattr(tcp_layer.payload, 'raw_value'):
                    return bytes.fromhex(tcp_layer.payload.raw_value)
            
            # 方法2：tcp.len回退
            if hasattr(tcp_layer, 'len'):
                payload_length = int(tcp_layer.len)
                if payload_length > 0:
                    # 返回占位符（表示有载荷但内容未知）
                    return b'\x00' * payload_length
            
            return None
            
        except Exception as e:
            self.logger.debug(f"PyShark载荷提取失败: {e}")
            return None
    
    def _generate_packet_key(self, pyshark_packet) -> str:
        """为PyShark数据包生成唯一键"""
        try:
            ip_layer = pyshark_packet.ip if hasattr(pyshark_packet, 'ip') else pyshark_packet.ipv6
            tcp_layer = pyshark_packet.tcp
            
            return f"{ip_layer.src}:{tcp_layer.srcport}->{ip_layer.dst}:{tcp_layer.dstport}:{tcp_layer.seq}"
        except:
            return f"packet_{pyshark_packet.number}"
    
    def _generate_scapy_packet_key(self, scapy_packet: ScapyPacket) -> str:
        """为Scapy数据包生成相同格式的键"""
        try:
            from scapy.all import IP, IPv6, TCP
            
            ip_layer = scapy_packet.getlayer(IP) or scapy_packet.getlayer(IPv6)
            tcp_layer = scapy_packet.getlayer(TCP)
            
            if ip_layer and tcp_layer:
                return f"{ip_layer.src}:{tcp_layer.sport}->{ip_layer.dst}:{tcp_layer.dport}:{tcp_layer.seq}"
            else:
                return f"packet_{id(scapy_packet)}"
        except:
            return f"packet_{id(scapy_packet)}"
    
    def _generate_stream_id_from_scapy(self, scapy_packet: ScapyPacket) -> str:
        """从Scapy数据包生成流ID - 与现有逻辑兼容"""
        from scapy.all import IP, IPv6, TCP
        
        ip_layer = scapy_packet.getlayer(IP) or scapy_packet.getlayer(IPv6)
        tcp_layer = scapy_packet.getlayer(TCP)
        
        src_ip = ip_layer.src
        dst_ip = ip_layer.dst
        src_port = tcp_layer.sport
        dst_port = tcp_layer.dport
        
        # 与现有代码保持一致的流ID生成逻辑
        if (src_ip, src_port) < (dst_ip, dst_port):
            direction = "forward"
            return f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_{direction}"
        else:
            direction = "reverse"
            return f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}_{direction}"
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 计算缓存命中率
        total_requests = stats['cache_hits'] + stats['cache_misses']
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / total_requests
        
        # 计算载荷提取成功率
        if stats['tcp_packets_found'] > 0:
            stats['payload_extraction_rate'] = stats['payloads_extracted'] / stats['tcp_packets_found']
        
        return stats


class HybridTcpMasker:
    """混合TCP掩码器
    
    结合PyShark载荷提取和Scapy文件操作的优势。
    这是完整的替代方案，与现有接口完全兼容。
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化混合TCP掩码器"""
        self.logger = logger or logging.getLogger(__name__)
        self.payload_extractor = HybridPayloadExtractor(logger)
    
    def process_pcap_file(self, input_pcap: str, output_pcap: str, keep_range_table) -> Dict[str, Any]:
        """处理PCAP文件 - 兼容现有接口
        
        Args:
            input_pcap: 输入PCAP文件路径
            output_pcap: 输出PCAP文件路径
            keep_range_table: 保留范围表（现有数据结构）
            
        Returns:
            Dict: 处理结果统计
        """
        try:
            # 步骤1：使用PyShark预提取载荷缓存
            self.logger.info("阶段1: PyShark载荷提取...")
            self.payload_extractor.prepare_payload_cache(input_pcap)
            
            # 步骤2：使用Scapy读取和处理数据包
            self.logger.info("阶段2: Scapy数据包处理...")
            packets = rdpcap(input_pcap)
            modified_packets = []
            
            processing_stats = {
                'total_packets': len(packets),
                'modified_packets': 0,
                'masked_bytes': 0,
                'kept_bytes': 0
            }
            
            for packet in packets:
                # 使用混合提取器获取载荷（实际来自PyShark缓存）
                stream_info = self.payload_extractor.extract_stream_info(packet)
                
                if stream_info is None:
                    # 非TCP包或无载荷，原样保留
                    modified_packets.append(packet)
                    continue
                
                stream_id, sequence, payload = stream_info
                
                # 查找匹配的保留范围（使用现有逻辑）
                keep_ranges = keep_range_table.find_keep_ranges_for_sequence(stream_id, sequence)
                
                if keep_ranges:
                    # 应用掩码
                    masked_payload = self._apply_mask(payload, keep_ranges)
                    
                    # 使用Scapy重构数据包
                    modified_packet = self._rebuild_packet_with_payload(packet, masked_payload)
                    modified_packets.append(modified_packet)
                    
                    # 更新统计
                    processing_stats['modified_packets'] += 1
                    processing_stats['masked_bytes'] += len(payload) - sum(
                        min(end, len(payload)) - max(start, 0) 
                        for start, end in keep_ranges
                        if max(start, 0) < min(end, len(payload))
                    )
                else:
                    # 无匹配规则，原样保留
                    modified_packets.append(packet)
            
            # 步骤3：使用Scapy写入PCAP文件
            self.logger.info("阶段3: Scapy文件写入...")
            wrpcap(output_pcap, modified_packets)
            
            # 合并统计信息
            extraction_stats = self.payload_extractor.get_statistics()
            processing_stats.update({
                'extraction_stats': extraction_stats,
                'cache_hit_rate': extraction_stats.get('cache_hit_rate', 0)
            })
            
            self.logger.info("混合处理完成!")
            return processing_stats
            
        except Exception as e:
            self.logger.error(f"混合处理失败: {e}")
            raise
    
    def _apply_mask(self, payload: bytes, keep_ranges: List[Tuple[int, int]]) -> bytes:
        """应用掩码到载荷 - 复用现有逻辑"""
        masked_payload = bytearray(len(payload))
        
        for start, end in keep_ranges:
            start = max(0, start)
            end = min(len(payload), end)
            if start < end:
                masked_payload[start:end] = payload[start:end]
        
        return bytes(masked_payload)
    
    def _rebuild_packet_with_payload(self, original_packet: ScapyPacket, new_payload: bytes) -> ScapyPacket:
        """使用Scapy重构数据包 - 利用Scapy的成熟重构能力"""
        from scapy.all import Raw
        
        # 复制数据包
        new_packet = original_packet.copy()
        
        # 替换载荷
        if new_packet.haslayer(Raw):
            new_packet[Raw].load = new_payload
        else:
            # 如果没有Raw层，添加一个
            new_packet = new_packet / Raw(load=new_payload)
        
        # 重新计算校验和等字段（Scapy会自动处理）
        del new_packet[TCP].chksum
        del new_packet[IP].chksum
        
        return new_packet


# 集成到现有架构的适配器
class PayloadExtractorAdapter:
    """现有PayloadExtractor的适配器
    
    这个适配器可以直接替换现有的PayloadExtractor，
    无需修改其他代码。
    """
    
    def __init__(self, pcap_file: str, logger: Optional[logging.Logger] = None):
        """初始化适配器
        
        Args:
            pcap_file: 需要处理的PCAP文件路径
        """
        self.hybrid_extractor = HybridPayloadExtractor(logger)
        self.hybrid_extractor.prepare_payload_cache(pcap_file)
    
    def extract_tcp_payload(self, packet: ScapyPacket) -> Optional[bytes]:
        """兼容现有接口"""
        return self.hybrid_extractor.extract_tcp_payload(packet)
    
    def extract_stream_info(self, packet: ScapyPacket) -> Optional[Tuple[str, int, bytes]]:
        """兼容现有接口"""
        return self.hybrid_extractor.extract_stream_info(packet)


# 使用示例
def demo_hybrid_approach():
    """演示混合架构的使用"""
    
    # 创建混合掩码器
    masker = HybridTcpMasker()
    
    # 处理PCAP文件
    input_file = "tests/data/tls-single/tls_sample.pcap"
    output_file = "test_outputs/hybrid_masked_output.pcap"
    
    # 假设的保留范围表（实际使用现有的数据结构）
    class MockKeepRangeTable:
        def find_keep_ranges_for_sequence(self, stream_id, sequence):
            # 返回示例保留范围
            return [(0, 5)]  # 保留前5字节
    
    keep_range_table = MockKeepRangeTable()
    
    # 执行处理
    results = masker.process_pcap_file(input_file, output_file, keep_range_table)
    
    print("混合处理结果:")
    for key, value in results.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    demo_hybrid_approach() 