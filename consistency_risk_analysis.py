#!/usr/bin/env python3
"""
混合架构不一致性风险分析

深入分析PyShark载荷提取与Scapy数据包重建之间的潜在不一致问题。
"""

import pyshark
import logging
from typing import Optional, Tuple, Dict, Any, List, Set
from scapy.all import rdpcap, wrpcap, Packet as ScapyPacket, Raw, IP, TCP
from pathlib import Path
import hashlib


class ConsistencyRiskAnalyzer:
    """一致性风险分析器
    
    专门分析PyShark提取和Scapy重建之间的数据一致性风险。
    """
    
    def __init__(self, pcap_file: str, logger: Optional[logging.Logger] = None):
        """初始化风险分析器"""
        self.pcap_file = pcap_file
        self.logger = logger or logging.getLogger(__name__)
        
        # 风险类别统计
        self.risks = {
            'packet_count_mismatch': [],      # 数据包数量不匹配
            'sequence_mismatch': [],          # 序列号不匹配
            'payload_length_mismatch': [],    # 载荷长度不匹配
            'payload_content_mismatch': [],   # 载荷内容不匹配
            'packet_order_mismatch': [],      # 数据包顺序不匹配
            'missing_packets': [],            # 缺失数据包
            'extra_packets': [],              # 多余数据包
            'header_inconsistency': [],       # 头部信息不一致
        }
        
        # 数据收集
        self.pyshark_data = {}  # PyShark提取的数据
        self.scapy_data = {}    # Scapy提取的数据
    
    def analyze_all_risks(self) -> Dict[str, Any]:
        """分析所有潜在的一致性风险"""
        self.logger.info("开始全面一致性风险分析...")
        
        # 1. 收集PyShark数据
        self.logger.info("阶段1: 收集PyShark数据...")
        self._collect_pyshark_data()
        
        # 2. 收集Scapy数据
        self.logger.info("阶段2: 收集Scapy数据...")
        self._collect_scapy_data()
        
        # 3. 进行一致性比较
        self.logger.info("阶段3: 进行一致性比较...")
        self._compare_packet_counts()
        self._compare_packet_sequences()
        self._compare_payload_data()
        self._compare_packet_headers()
        self._analyze_packet_mapping()
        
        # 4. 生成风险报告
        return self._generate_risk_report()
    
    def _collect_pyshark_data(self) -> None:
        """收集PyShark的数据包信息"""
        try:
            cap = pyshark.FileCapture(self.pcap_file)
            
            for packet in cap:
                if hasattr(packet, 'tcp'):
                    packet_info = self._extract_pyshark_packet_info(packet)
                    if packet_info:
                        self.pyshark_data[packet_info['packet_number']] = packet_info
            
            cap.close()
            self.logger.info(f"PyShark收集到 {len(self.pyshark_data)} 个TCP数据包")
            
        except Exception as e:
            self.logger.error(f"PyShark数据收集失败: {e}")
            raise
    
    def _collect_scapy_data(self) -> None:
        """收集Scapy的数据包信息"""
        try:
            packets = rdpcap(self.pcap_file)
            
            for i, packet in enumerate(packets, 1):
                if packet.haslayer(TCP):
                    packet_info = self._extract_scapy_packet_info(packet, i)
                    if packet_info:
                        self.scapy_data[packet_info['packet_number']] = packet_info
            
            self.logger.info(f"Scapy收集到 {len(self.scapy_data)} 个TCP数据包")
            
        except Exception as e:
            self.logger.error(f"Scapy数据收集失败: {e}")
            raise
    
    def _extract_pyshark_packet_info(self, packet) -> Optional[Dict]:
        """提取PyShark数据包的详细信息"""
        try:
            tcp_layer = packet.tcp
            ip_layer = packet.ip if hasattr(packet, 'ip') else packet.ipv6
            
            # 提取载荷
            payload_data = None
            payload_length = 0
            payload_hash = None
            
            if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
                if hasattr(tcp_layer.payload, 'binary_value'):
                    payload_data = tcp_layer.payload.binary_value
                    payload_length = len(payload_data)
                    payload_hash = hashlib.md5(payload_data).hexdigest()
                elif hasattr(tcp_layer.payload, 'raw_value'):
                    payload_data = bytes.fromhex(tcp_layer.payload.raw_value)
                    payload_length = len(payload_data)
                    payload_hash = hashlib.md5(payload_data).hexdigest()
            
            # 尝试从tcp.len获取载荷长度
            tcp_len = None
            if hasattr(tcp_layer, 'len'):
                tcp_len = int(tcp_layer.len)
            
            return {
                'packet_number': int(packet.number),
                'timestamp': float(packet.sniff_timestamp),
                'src_ip': str(ip_layer.src),
                'dst_ip': str(ip_layer.dst),
                'src_port': int(tcp_layer.srcport),
                'dst_port': int(tcp_layer.dstport),
                'sequence': int(tcp_layer.seq),
                'payload_data': payload_data,
                'payload_length': payload_length,
                'payload_hash': payload_hash,
                'tcp_len': tcp_len,
                'has_payload_attr': hasattr(tcp_layer, 'payload'),
                'payload_access_method': self._get_payload_access_method(tcp_layer)
            }
            
        except Exception as e:
            self.logger.debug(f"PyShark数据包信息提取失败: {e}")
            return None
    
    def _extract_scapy_packet_info(self, packet: ScapyPacket, packet_number: int) -> Optional[Dict]:
        """提取Scapy数据包的详细信息"""
        try:
            tcp_layer = packet[TCP]
            ip_layer = packet[IP] if packet.haslayer(IP) else packet[IPv6]
            
            # 提取载荷 - 尝试多种方法
            payload_data = None
            payload_length = 0
            payload_hash = None
            raw_layer_exists = packet.haslayer(Raw)
            
            # 方法1: Raw层
            if raw_layer_exists:
                raw_layer = packet[Raw]
                payload_data = raw_layer.load
                payload_length = len(payload_data)
                payload_hash = hashlib.md5(payload_data).hexdigest()
            
            # 方法2: TCP载荷属性
            elif hasattr(tcp_layer, 'payload') and tcp_layer.payload:
                payload_data = bytes(tcp_layer.payload)
                payload_length = len(payload_data)
                payload_hash = hashlib.md5(payload_data).hexdigest()
            
            return {
                'packet_number': packet_number,
                'timestamp': packet.time,
                'src_ip': str(ip_layer.src),
                'dst_ip': str(ip_layer.dst),
                'src_port': int(tcp_layer.sport),
                'dst_port': int(tcp_layer.dport),
                'sequence': int(tcp_layer.seq),
                'payload_data': payload_data,
                'payload_length': payload_length,
                'payload_hash': payload_hash,
                'raw_layer_exists': raw_layer_exists,
                'tcp_payload_attr': hasattr(tcp_layer, 'payload'),
                'packet_layers': [layer.name for layer in packet.layers()]
            }
            
        except Exception as e:
            self.logger.debug(f"Scapy数据包信息提取失败: {e}")
            return None
    
    def _get_payload_access_method(self, tcp_layer) -> str:
        """获取PyShark载荷访问方法"""
        if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
            if hasattr(tcp_layer.payload, 'binary_value'):
                return 'binary_value'
            elif hasattr(tcp_layer.payload, 'raw_value'):
                return 'raw_value'
            else:
                return 'payload_exists_but_no_access'
        elif hasattr(tcp_layer, 'len'):
            return 'tcp_len_only'
        else:
            return 'no_payload_info'
    
    def _compare_packet_counts(self) -> None:
        """比较数据包数量"""
        pyshark_count = len(self.pyshark_data)
        scapy_count = len(self.scapy_data)
        
        if pyshark_count != scapy_count:
            self.risks['packet_count_mismatch'].append({
                'pyshark_count': pyshark_count,
                'scapy_count': scapy_count,
                'difference': abs(pyshark_count - scapy_count),
                'severity': 'HIGH'
            })
    
    def _compare_packet_sequences(self) -> None:
        """比较数据包序列号"""
        common_packets = set(self.pyshark_data.keys()) & set(self.scapy_data.keys())
        
        for packet_num in common_packets:
            pyshark_seq = self.pyshark_data[packet_num]['sequence']
            scapy_seq = self.scapy_data[packet_num]['sequence']
            
            if pyshark_seq != scapy_seq:
                self.risks['sequence_mismatch'].append({
                    'packet_number': packet_num,
                    'pyshark_sequence': pyshark_seq,
                    'scapy_sequence': scapy_seq,
                    'difference': abs(pyshark_seq - scapy_seq),
                    'severity': 'HIGH'
                })
    
    def _compare_payload_data(self) -> None:
        """比较载荷数据"""
        common_packets = set(self.pyshark_data.keys()) & set(self.scapy_data.keys())
        
        for packet_num in common_packets:
            pyshark_info = self.pyshark_data[packet_num]
            scapy_info = self.scapy_data[packet_num]
            
            # 比较载荷长度
            if pyshark_info['payload_length'] != scapy_info['payload_length']:
                self.risks['payload_length_mismatch'].append({
                    'packet_number': packet_num,
                    'pyshark_length': pyshark_info['payload_length'],
                    'scapy_length': scapy_info['payload_length'],
                    'difference': abs(pyshark_info['payload_length'] - scapy_info['payload_length']),
                    'pyshark_method': pyshark_info['payload_access_method'],
                    'scapy_raw_layer': scapy_info['raw_layer_exists'],
                    'severity': 'HIGH' if abs(pyshark_info['payload_length'] - scapy_info['payload_length']) > 10 else 'MEDIUM'
                })
            
            # 比较载荷内容哈希
            if (pyshark_info['payload_hash'] and scapy_info['payload_hash'] and 
                pyshark_info['payload_hash'] != scapy_info['payload_hash']):
                self.risks['payload_content_mismatch'].append({
                    'packet_number': packet_num,
                    'pyshark_hash': pyshark_info['payload_hash'],
                    'scapy_hash': scapy_info['payload_hash'],
                    'payload_length': pyshark_info['payload_length'],
                    'severity': 'CRITICAL'
                })
    
    def _compare_packet_headers(self) -> None:
        """比较数据包头部信息"""
        common_packets = set(self.pyshark_data.keys()) & set(self.scapy_data.keys())
        
        for packet_num in common_packets:
            pyshark_info = self.pyshark_data[packet_num]
            scapy_info = self.scapy_data[packet_num]
            
            # 比较IP地址
            if (pyshark_info['src_ip'] != scapy_info['src_ip'] or 
                pyshark_info['dst_ip'] != scapy_info['dst_ip']):
                self.risks['header_inconsistency'].append({
                    'packet_number': packet_num,
                    'field': 'ip_addresses',
                    'pyshark_value': f"{pyshark_info['src_ip']}->{pyshark_info['dst_ip']}",
                    'scapy_value': f"{scapy_info['src_ip']}->{scapy_info['dst_ip']}",
                    'severity': 'CRITICAL'
                })
            
            # 比较端口
            if (pyshark_info['src_port'] != scapy_info['src_port'] or 
                pyshark_info['dst_port'] != scapy_info['dst_port']):
                self.risks['header_inconsistency'].append({
                    'packet_number': packet_num,
                    'field': 'tcp_ports',
                    'pyshark_value': f"{pyshark_info['src_port']}->{pyshark_info['dst_port']}",
                    'scapy_value': f"{scapy_info['src_port']}->{scapy_info['dst_port']}",
                    'severity': 'CRITICAL'
                })
    
    def _analyze_packet_mapping(self) -> None:
        """分析数据包映射关系"""
        pyshark_packets = set(self.pyshark_data.keys())
        scapy_packets = set(self.scapy_data.keys())
        
        # 查找缺失的数据包
        missing_in_scapy = pyshark_packets - scapy_packets
        if missing_in_scapy:
            self.risks['missing_packets'].extend([
                {
                    'packet_number': pkt_num,
                    'missing_in': 'scapy',
                    'severity': 'HIGH'
                } for pkt_num in missing_in_scapy
            ])
        
        # 查找多余的数据包
        extra_in_scapy = scapy_packets - pyshark_packets
        if extra_in_scapy:
            self.risks['extra_packets'].extend([
                {
                    'packet_number': pkt_num,
                    'extra_in': 'scapy',
                    'severity': 'HIGH'
                } for pkt_num in extra_in_scapy
            ])
    
    def _generate_risk_report(self) -> Dict[str, Any]:
        """生成详细的风险评估报告"""
        total_risks = sum(len(risks) for risks in self.risks.values())
        critical_risks = sum(1 for risk_category in self.risks.values() 
                           for risk in risk_category 
                           if risk.get('severity') == 'CRITICAL')
        high_risks = sum(1 for risk_category in self.risks.values() 
                        for risk in risk_category 
                        if risk.get('severity') == 'HIGH')
        
        # 计算风险评分
        risk_score = critical_risks * 10 + high_risks * 5
        
        # 确定总体风险等级
        if critical_risks > 0:
            overall_risk = "CRITICAL"
        elif high_risks > 3:
            overall_risk = "HIGH"
        elif total_risks > 5:
            overall_risk = "MEDIUM"
        else:
            overall_risk = "LOW"
        
        report = {
            'summary': {
                'total_risks': total_risks,
                'critical_risks': critical_risks,
                'high_risks': high_risks,
                'risk_score': risk_score,
                'overall_risk_level': overall_risk,
                'pyshark_packets': len(self.pyshark_data),
                'scapy_packets': len(self.scapy_data)
            },
            'detailed_risks': self.risks,
            'recommendations': self._generate_recommendations(overall_risk, self.risks)
        }
        
        return report
    
    def _generate_recommendations(self, risk_level: str, risks: Dict) -> List[str]:
        """生成基于风险分析的建议"""
        recommendations = []
        
        if risk_level == "CRITICAL":
            recommendations.append("❌ 不建议使用混合架构 - 存在严重的数据一致性风险")
            recommendations.append("🔄 建议继续使用单一引擎解决方案")
        
        if risks['payload_content_mismatch']:
            recommendations.append("⚠️  载荷内容不匹配 - 可能导致掩码应用到错误的数据")
            recommendations.append("🔧 考虑在混合架构中添加载荷验证步骤")
        
        if risks['payload_length_mismatch']:
            recommendations.append("📏 载荷长度不匹配 - 可能导致掩码范围计算错误")
            recommendations.append("🔍 建议实施长度一致性检查")
        
        if risks['sequence_mismatch']:
            recommendations.append("🔢 序列号不匹配 - 流ID生成可能出现问题")
            recommendations.append("🎯 需要统一序列号提取逻辑")
        
        if risks['packet_count_mismatch']:
            recommendations.append("📊 数据包数量不匹配 - 可能遗漏或重复处理")
            recommendations.append("🔄 建议实施包数量验证机制")
        
        if len(recommendations) == 0:
            recommendations.append("✅ 混合架构风险可控，可以谨慎实施")
            recommendations.append("🔍 建议实施运行时一致性验证")
        
        return recommendations


def analyze_consistency_risk(pcap_file: str) -> None:
    """执行一致性风险分析"""
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    logger.info("开始混合架构一致性风险分析...")
    
    try:
        # 创建风险分析器
        analyzer = ConsistencyRiskAnalyzer(pcap_file, logger)
        
        # 执行分析
        risk_report = analyzer.analyze_all_risks()
        
        # 打印报告
        print("\n" + "="*80)
        print("🚨 混合架构一致性风险分析报告")
        print("="*80)
        
        summary = risk_report['summary']
        print(f"\n📊 概览:")
        print(f"   总风险数量: {summary['total_risks']}")
        print(f"   严重风险: {summary['critical_risks']}")
        print(f"   高风险: {summary['high_risks']}")
        print(f"   风险评分: {summary['risk_score']}")
        print(f"   总体风险等级: {summary['overall_risk_level']}")
        print(f"   PyShark数据包: {summary['pyshark_packets']}")
        print(f"   Scapy数据包: {summary['scapy_packets']}")
        
        # 详细风险
        print(f"\n🔍 详细风险分析:")
        for risk_type, risk_list in risk_report['detailed_risks'].items():
            if risk_list:
                print(f"   {risk_type}: {len(risk_list)} 个风险")
                for i, risk in enumerate(risk_list[:3]):  # 只显示前3个
                    print(f"     - {risk}")
                if len(risk_list) > 3:
                    print(f"     ... 还有 {len(risk_list)-3} 个风险")
        
        # 建议
        print(f"\n💡 建议:")
        for recommendation in risk_report['recommendations']:
            print(f"   {recommendation}")
        
        print("\n" + "="*80)
        
    except Exception as e:
        logger.error(f"风险分析失败: {e}")
        raise


if __name__ == "__main__":
    # 分析TLS样本的一致性风险
    pcap_file = "tests/data/tls-single/tls_sample.pcap"
    analyze_consistency_risk(pcap_file) 