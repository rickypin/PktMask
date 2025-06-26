#!/usr/bin/env python3
"""
序列号统一转换机制

基于风险重新评估的结果，实现PyShark相对序列号到Scapy绝对序列号的统一转换。
这是混合架构成功实施的关键技术组件。
"""

from typing import Dict, Tuple, Optional
import logging


class SequenceNumberUnifier:
    """序列号统一转换器
    
    解决PyShark相对序列号与Scapy绝对序列号不一致的问题。
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化序列号统一器"""
        self.logger = logger or logging.getLogger(__name__)
        
        # 序列号映射表：{relative_seq: absolute_seq}
        self.seq_mapping: Dict[int, int] = {}
        
        # 流基础序列号：{stream_id: initial_absolute_seq}
        self.stream_base_seq: Dict[str, int] = {}
        
        # 统计信息
        self.stats = {
            'mappings_established': 0,
            'conversions_performed': 0,
            'failed_conversions': 0
        }
    
    def establish_mapping_from_samples(self, pyshark_data: Dict, scapy_data: Dict) -> None:
        """从样本数据建立序列号映射关系
        
        Args:
            pyshark_data: PyShark提取的数据包信息
            scapy_data: Scapy提取的数据包信息
        """
        self.logger.info("建立序列号映射关系...")
        
        # 按流ID分组建立映射
        stream_mappings = {}
        
        for packet_num in pyshark_data:
            if packet_num in scapy_data:
                pyshark_info = pyshark_data[packet_num]
                scapy_info = scapy_data[packet_num]
                
                # 生成流ID（使用Scapy格式）
                stream_id = self._generate_stream_id(scapy_info)
                
                if stream_id not in stream_mappings:
                    stream_mappings[stream_id] = []
                
                stream_mappings[stream_id].append({
                    'packet_num': packet_num,
                    'relative_seq': pyshark_info['sequence'],
                    'absolute_seq': scapy_info['sequence']
                })
        
        # 为每个流建立序列号映射
        for stream_id, mappings in stream_mappings.items():
            self._establish_stream_mapping(stream_id, mappings)
        
        self.logger.info(f"建立了 {len(self.seq_mapping)} 个序列号映射")
    
    def _establish_stream_mapping(self, stream_id: str, mappings: list) -> None:
        """为单个流建立序列号映射"""
        
        # 按相对序列号排序
        mappings.sort(key=lambda x: x['relative_seq'])
        
        if mappings:
            # 获取流的基础序列号
            first_mapping = mappings[0]
            relative_base = first_mapping['relative_seq']
            absolute_base = first_mapping['absolute_seq']
            
            # 计算偏移量
            offset = absolute_base - relative_base
            self.stream_base_seq[stream_id] = offset
            
            # 建立所有映射
            for mapping in mappings:
                relative_seq = mapping['relative_seq']
                absolute_seq = mapping['absolute_seq']
                
                # 验证映射一致性
                expected_absolute = relative_seq + offset
                if expected_absolute == absolute_seq:
                    self.seq_mapping[relative_seq] = absolute_seq
                    self.stats['mappings_established'] += 1
                else:
                    self.logger.warning(
                        f"序列号映射不一致: 流{stream_id}, "
                        f"相对{relative_seq}, 绝对{absolute_seq}, "
                        f"期望{expected_absolute}"
                    )
    
    def convert_relative_to_absolute(self, relative_seq: int, stream_id: str = None) -> Optional[int]:
        """将相对序列号转换为绝对序列号
        
        Args:
            relative_seq: PyShark的相对序列号
            stream_id: 流ID（可选，用于更精确的转换）
            
        Returns:
            Optional[int]: 对应的绝对序列号，失败时返回None
        """
        
        # 方法1: 直接映射查找
        if relative_seq in self.seq_mapping:
            self.stats['conversions_performed'] += 1
            return self.seq_mapping[relative_seq]
        
        # 方法2: 基于流偏移计算
        if stream_id and stream_id in self.stream_base_seq:
            offset = self.stream_base_seq[stream_id]
            absolute_seq = relative_seq + offset
            self.stats['conversions_performed'] += 1
            return absolute_seq
        
        # 转换失败
        self.stats['failed_conversions'] += 1
        self.logger.warning(f"无法转换相对序列号 {relative_seq}")
        return None
    
    def generate_unified_packet_key(self, src_ip: str, src_port: int, 
                                   dst_ip: str, dst_port: int, 
                                   relative_seq: int) -> str:
        """生成统一的数据包键（使用绝对序列号）
        
        Args:
            src_ip: 源IP地址
            src_port: 源端口
            dst_ip: 目标IP地址
            dst_port: 目标端口
            relative_seq: PyShark的相对序列号
            
        Returns:
            str: 统一格式的数据包键
        """
        
        # 生成流ID
        stream_id = self._generate_stream_id_from_ips(src_ip, src_port, dst_ip, dst_port)
        
        # 转换序列号
        absolute_seq = self.convert_relative_to_absolute(relative_seq, stream_id)
        
        if absolute_seq is not None:
            return f"{src_ip}:{src_port}->{dst_ip}:{dst_port}:{absolute_seq}"
        else:
            # 回退到相对序列号（带标记）
            return f"{src_ip}:{src_port}->{dst_ip}:{dst_port}:REL_{relative_seq}"
    
    def _generate_stream_id(self, scapy_info: Dict) -> str:
        """从Scapy信息生成流ID"""
        return self._generate_stream_id_from_ips(
            scapy_info['src_ip'], scapy_info['src_port'],
            scapy_info['dst_ip'], scapy_info['dst_port']
        )
    
    def _generate_stream_id_from_ips(self, src_ip: str, src_port: int, 
                                    dst_ip: str, dst_port: int) -> str:
        """从IP和端口信息生成流ID"""
        if (src_ip, src_port) < (dst_ip, dst_port):
            direction = "forward"
            return f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_{direction}"
        else:
            direction = "reverse"
            return f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}_{direction}"
    
    def get_statistics(self) -> Dict:
        """获取转换统计信息"""
        total_attempts = self.stats['conversions_performed'] + self.stats['failed_conversions']
        success_rate = (self.stats['conversions_performed'] / total_attempts 
                       if total_attempts > 0 else 0)
        
        return {
            **self.stats,
            'total_conversion_attempts': total_attempts,
            'conversion_success_rate': success_rate
        }


class EnhancedHybridPayloadExtractor:
    """增强的混合载荷提取器
    
    整合序列号统一转换机制，解决PyShark和Scapy的序列号不一致问题。
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化增强的混合载荷提取器"""
        self.logger = logger or logging.getLogger(__name__)
        self.sequence_unifier = SequenceNumberUnifier(logger)
        self.payload_cache: Dict[str, bytes] = {}
        
        # 统计信息
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'sequence_conversions': 0,
            'extraction_successes': 0,
            'extraction_failures': 0
        }
    
    def prepare_unified_payload_cache(self, pcap_file: str) -> None:
        """使用统一序列号准备载荷缓存"""
        self.logger.info("使用统一序列号机制准备载荷缓存...")
        
        # 1. 收集PyShark和Scapy数据
        pyshark_data = self._collect_pyshark_data(pcap_file)
        scapy_data = self._collect_scapy_data(pcap_file)
        
        # 2. 建立序列号映射
        self.sequence_unifier.establish_mapping_from_samples(pyshark_data, scapy_data)
        
        # 3. 使用统一键建立载荷缓存
        for packet_num, pyshark_info in pyshark_data.items():
            if pyshark_info['payload_accessible']:
                # 生成统一的缓存键
                unified_key = self.sequence_unifier.generate_unified_packet_key(
                    pyshark_info['src_ip'], pyshark_info['src_port'],
                    pyshark_info['dst_ip'], pyshark_info['dst_port'],
                    pyshark_info['sequence']
                )
                
                # 缓存载荷
                if unified_key and pyshark_info['payload_data']:
                    self.payload_cache[unified_key] = pyshark_info['payload_data']
                    self.stats['extraction_successes'] += 1
                else:
                    self.stats['extraction_failures'] += 1
        
        self.logger.info(f"载荷缓存完成: {len(self.payload_cache)} 个载荷已缓存")
        
        # 打印统计信息
        seq_stats = self.sequence_unifier.get_statistics()
        self.logger.info(f"序列号转换统计: {seq_stats}")
    
    def extract_tcp_payload_unified(self, scapy_packet) -> Optional[bytes]:
        """使用统一键从缓存提取TCP载荷"""
        try:
            from scapy.all import IP, IPv6, TCP
            
            # 提取网络信息
            ip_layer = scapy_packet.getlayer(IP) or scapy_packet.getlayer(IPv6)
            tcp_layer = scapy_packet.getlayer(TCP)
            
            if not ip_layer or not tcp_layer:
                return None
            
            # 生成Scapy格式的数据包键
            scapy_key = (f"{ip_layer.src}:{tcp_layer.sport}->"
                        f"{ip_layer.dst}:{tcp_layer.dport}:{tcp_layer.seq}")
            
            # 从缓存中查找
            if scapy_key in self.payload_cache:
                self.stats['cache_hits'] += 1
                return self.payload_cache[scapy_key]
            else:
                self.stats['cache_misses'] += 1
                return None
                
        except Exception as e:
            self.logger.warning(f"统一载荷提取失败: {e}")
            self.stats['extraction_failures'] += 1
            return None
    
    def _collect_pyshark_data(self, pcap_file: str) -> Dict:
        """收集PyShark数据包信息"""
        import pyshark
        
        data = {}
        cap = pyshark.FileCapture(pcap_file)
        
        for packet in cap:
            if hasattr(packet, 'tcp'):
                packet_info = self._extract_pyshark_info(packet)
                if packet_info:
                    data[packet_info['packet_number']] = packet_info
        
        cap.close()
        return data
    
    def _collect_scapy_data(self, pcap_file: str) -> Dict:
        """收集Scapy数据包信息"""
        from scapy.all import rdpcap, IP, IPv6, TCP
        
        data = {}
        packets = rdpcap(pcap_file)
        
        for i, packet in enumerate(packets, 1):
            if packet.haslayer(TCP):
                ip_layer = packet.getlayer(IP) or packet.getlayer(IPv6)
                tcp_layer = packet.getlayer(TCP)
                
                if ip_layer and tcp_layer:
                    data[i] = {
                        'packet_number': i,
                        'src_ip': str(ip_layer.src),
                        'dst_ip': str(ip_layer.dst),
                        'src_port': int(tcp_layer.sport),
                        'dst_port': int(tcp_layer.dport),
                        'sequence': int(tcp_layer.seq)
                    }
        
        return data
    
    def _extract_pyshark_info(self, packet) -> Optional[Dict]:
        """提取PyShark数据包信息"""
        try:
            tcp_layer = packet.tcp
            ip_layer = packet.ip if hasattr(packet, 'ip') else packet.ipv6
            
            # 提取载荷
            payload_data = None
            payload_accessible = False
            
            if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
                if hasattr(tcp_layer.payload, 'binary_value'):
                    payload_data = tcp_layer.payload.binary_value
                    payload_accessible = True
                elif hasattr(tcp_layer.payload, 'raw_value'):
                    try:
                        payload_data = bytes.fromhex(tcp_layer.payload.raw_value)
                        payload_accessible = True
                    except ValueError:
                        pass
            
            return {
                'packet_number': int(packet.number),
                'src_ip': str(ip_layer.src),
                'dst_ip': str(ip_layer.dst),
                'src_port': int(tcp_layer.srcport),
                'dst_port': int(tcp_layer.dstport),
                'sequence': int(tcp_layer.seq),  # 相对序列号
                'payload_data': payload_data,
                'payload_accessible': payload_accessible
            }
            
        except Exception as e:
            self.logger.debug(f"PyShark信息提取失败: {e}")
            return None


# 使用示例
def demo_sequence_unification():
    """演示序列号统一机制"""
    
    pcap_file = "tests/data/tls-single/tls_sample.pcap"
    
    # 创建增强的混合提取器
    extractor = EnhancedHybridPayloadExtractor()
    
    # 准备统一的载荷缓存
    extractor.prepare_unified_payload_cache(pcap_file)
    
    # 测试载荷提取
    from scapy.all import rdpcap
    packets = rdpcap(pcap_file)
    
    for i, packet in enumerate(packets[:5], 1):  # 测试前5个包
        payload = extractor.extract_tcp_payload_unified(packet)
        print(f"包{i}: 载荷长度 = {len(payload) if payload else 0}")
    
    # 打印统计信息
    stats = extractor.stats
    print(f"\n统计信息:")
    print(f"  缓存命中: {stats['cache_hits']}")
    print(f"  缓存未命中: {stats['cache_misses']}")
    print(f"  提取成功: {stats['extraction_successes']}")
    print(f"  提取失败: {stats['extraction_failures']}")


if __name__ == "__main__":
    demo_sequence_unification() 