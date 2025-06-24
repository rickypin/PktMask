#!/usr/bin/env python3
"""
混合架构风险重新评估（排除序列号统一处理问题）

重新分析PyShark载荷提取与Scapy数据包重建之间的实际风险，
假设序列号不一致问题已通过统一转换机制解决。
"""

import pyshark
import logging
from typing import Optional, Tuple, Dict, Any, List, Set
from scapy.all import rdpcap, wrpcap, Packet as ScapyPacket, Raw, IP, TCP
from pathlib import Path
import hashlib


class ConsistencyRiskAnalyzerV2:
    """一致性风险分析器 V2
    
    专门分析PyShark提取和Scapy重建之间的实际数据一致性风险，
    排除可通过技术手段解决的序列号统一问题。
    """
    
    def __init__(self, pcap_file: str, logger: Optional[logging.Logger] = None):
        """初始化风险分析器"""
        self.pcap_file = pcap_file
        self.logger = logger or logging.getLogger(__name__)
        
        # 实际风险类别（排除序列号不一致）
        self.actual_risks = {
            'packet_count_mismatch': [],      # 数据包数量不匹配
            'payload_content_mismatch': [],   # 载荷内容不匹配
            'payload_accessibility': [],      # 载荷可访问性差异
            'header_inconsistency': [],       # 头部信息不一致
            'packet_mapping_issues': [],      # 数据包映射问题
            'payload_extraction_failures': [], # 载荷提取失败
        }
        
        # 可解决的风险（通过技术手段）
        self.solvable_risks = {
            'sequence_number_format': [],     # 序列号格式差异（可统一）
            'timestamp_precision': [],        # 时间戳精度差异（可忽略）
        }
        
        # 数据收集
        self.pyshark_data = {}
        self.scapy_data = {}
        
        # 序列号映射表（模拟统一处理）
        self.sequence_mapping = {}
    
    def analyze_actual_risks(self) -> Dict[str, Any]:
        """分析实际的一致性风险（排除可解决问题）"""
        self.logger.info("开始实际风险分析（排除可解决问题）...")
        
        # 1. 收集数据
        self._collect_pyshark_data()
        self._collect_scapy_data()
        
        # 2. 建立序列号映射（模拟统一处理）
        self._build_sequence_mapping()
        
        # 3. 分析实际风险
        self._analyze_packet_counts()
        self._analyze_payload_accessibility()
        self._analyze_payload_content()
        self._analyze_header_consistency()
        self._analyze_packet_mapping()
        self._analyze_extraction_success_rate()
        
        # 4. 生成重新评估的风险报告
        return self._generate_realistic_risk_report()
    
    def _collect_pyshark_data(self) -> None:
        """收集PyShark数据"""
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
        """收集Scapy数据"""
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
    
    def _build_sequence_mapping(self) -> None:
        """建立序列号映射表（模拟统一处理效果）"""
        self.logger.info("建立序列号统一映射...")
        
        # 为每个数据包建立PyShark相对序列号到Scapy绝对序列号的映射
        for packet_num in self.pyshark_data:
            if packet_num in self.scapy_data:
                pyshark_seq = self.pyshark_data[packet_num]['sequence']
                scapy_seq = self.scapy_data[packet_num]['sequence']
                
                # 建立映射关系
                self.sequence_mapping[pyshark_seq] = scapy_seq
                
                # 记录可解决的序列号格式差异
                if pyshark_seq != scapy_seq:
                    self.solvable_risks['sequence_number_format'].append({
                        'packet_number': packet_num,
                        'pyshark_seq': pyshark_seq,
                        'scapy_seq': scapy_seq,
                        'can_be_unified': True,
                        'mapping_established': True
                    })
        
        self.logger.info(f"建立了 {len(self.sequence_mapping)} 个序列号映射")
    
    def _extract_pyshark_packet_info(self, packet) -> Optional[Dict]:
        """提取PyShark数据包信息"""
        try:
            tcp_layer = packet.tcp
            ip_layer = packet.ip if hasattr(packet, 'ip') else packet.ipv6
            
            # 提取载荷
            payload_data = None
            payload_length = 0
            payload_hash = None
            payload_access_method = "none"
            payload_accessible = False
            
            if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
                if hasattr(tcp_layer.payload, 'binary_value'):
                    payload_data = tcp_layer.payload.binary_value
                    payload_length = len(payload_data)
                    payload_hash = hashlib.md5(payload_data).hexdigest()
                    payload_access_method = "binary_value"
                    payload_accessible = True
                elif hasattr(tcp_layer.payload, 'raw_value'):
                    try:
                        payload_data = bytes.fromhex(tcp_layer.payload.raw_value)
                        payload_length = len(payload_data)
                        payload_hash = hashlib.md5(payload_data).hexdigest()
                        payload_access_method = "raw_value"
                        payload_accessible = True
                    except ValueError:
                        payload_access_method = "raw_value_invalid"
            
            # TCP长度信息
            tcp_len = None
            if hasattr(tcp_layer, 'len'):
                tcp_len = int(tcp_layer.len)
                if tcp_len > 0 and not payload_accessible:
                    payload_access_method = "tcp_len_only"
            
            return {
                'packet_number': int(packet.number),
                'timestamp': float(packet.sniff_timestamp),
                'src_ip': str(ip_layer.src),
                'dst_ip': str(ip_layer.dst),
                'src_port': int(tcp_layer.srcport),
                'dst_port': int(tcp_layer.dstport),
                'sequence': int(tcp_layer.seq),  # 相对序列号
                'payload_data': payload_data,
                'payload_length': payload_length,
                'payload_hash': payload_hash,
                'payload_accessible': payload_accessible,
                'payload_access_method': payload_access_method,
                'tcp_len': tcp_len,
                'has_payload_attr': hasattr(tcp_layer, 'payload'),
            }
            
        except Exception as e:
            self.logger.debug(f"PyShark数据包信息提取失败: {e}")
            return None
    
    def _extract_scapy_packet_info(self, packet: ScapyPacket, packet_number: int) -> Optional[Dict]:
        """提取Scapy数据包信息"""
        try:
            tcp_layer = packet[TCP]
            ip_layer = packet[IP] if packet.haslayer(IP) else packet[IPv6]
            
            # 提取载荷
            payload_data = None
            payload_length = 0
            payload_hash = None
            raw_layer_exists = packet.haslayer(Raw)
            payload_accessible = False
            payload_access_method = "none"
            
            # 方法1: Raw层
            if raw_layer_exists:
                raw_layer = packet[Raw]
                payload_data = raw_layer.load
                payload_length = len(payload_data)
                payload_hash = hashlib.md5(payload_data).hexdigest()
                payload_accessible = True
                payload_access_method = "raw_layer"
            
            # 方法2: TCP载荷属性
            elif hasattr(tcp_layer, 'payload') and tcp_layer.payload:
                try:
                    payload_data = bytes(tcp_layer.payload)
                    payload_length = len(payload_data)
                    payload_hash = hashlib.md5(payload_data).hexdigest()
                    payload_accessible = True
                    payload_access_method = "tcp_payload_attr"
                except:
                    payload_access_method = "tcp_payload_failed"
            
            return {
                'packet_number': packet_number,
                'timestamp': packet.time,
                'src_ip': str(ip_layer.src),
                'dst_ip': str(ip_layer.dst),
                'src_port': int(tcp_layer.sport),
                'dst_port': int(tcp_layer.dport),
                'sequence': int(tcp_layer.seq),  # 绝对序列号
                'payload_data': payload_data,
                'payload_length': payload_length,
                'payload_hash': payload_hash,
                'payload_accessible': payload_accessible,
                'payload_access_method': payload_access_method,
                'raw_layer_exists': raw_layer_exists,
                'packet_layers': [layer.name for layer in packet.layers()]
            }
            
        except Exception as e:
            self.logger.debug(f"Scapy数据包信息提取失败: {e}")
            return None
    
    def _analyze_packet_counts(self) -> None:
        """分析数据包数量一致性"""
        pyshark_count = len(self.pyshark_data)
        scapy_count = len(self.scapy_data)
        
        if pyshark_count != scapy_count:
            self.actual_risks['packet_count_mismatch'].append({
                'pyshark_count': pyshark_count,
                'scapy_count': scapy_count,
                'difference': abs(pyshark_count - scapy_count),
                'impact': 'CRITICAL',
                'reason': '数据包数量不一致会导致载荷映射错误'
            })
    
    def _analyze_payload_accessibility(self) -> None:
        """分析载荷可访问性差异"""
        common_packets = set(self.pyshark_data.keys()) & set(self.scapy_data.keys())
        
        for packet_num in common_packets:
            pyshark_info = self.pyshark_data[packet_num]
            scapy_info = self.scapy_data[packet_num]
            
            # 载荷可访问性差异
            if pyshark_info['payload_accessible'] != scapy_info['payload_accessible']:
                self.actual_risks['payload_accessibility'].append({
                    'packet_number': packet_num,
                    'pyshark_accessible': pyshark_info['payload_accessible'],
                    'scapy_accessible': scapy_info['payload_accessible'],
                    'pyshark_method': pyshark_info['payload_access_method'],
                    'scapy_method': scapy_info['payload_access_method'],
                    'impact': 'HIGH',
                    'reason': '载荷可访问性不一致可能导致掩码遗漏'
                })
    
    def _analyze_payload_content(self) -> None:
        """分析载荷内容一致性"""
        common_packets = set(self.pyshark_data.keys()) & set(self.scapy_data.keys())
        
        for packet_num in common_packets:
            pyshark_info = self.pyshark_data[packet_num]
            scapy_info = self.scapy_data[packet_num]
            
            # 只对都能访问载荷的包进行内容比较
            if (pyshark_info['payload_accessible'] and scapy_info['payload_accessible']):
                
                # 载荷长度差异
                if pyshark_info['payload_length'] != scapy_info['payload_length']:
                    self.actual_risks['payload_content_mismatch'].append({
                        'packet_number': packet_num,
                        'type': 'length_mismatch',
                        'pyshark_length': pyshark_info['payload_length'],
                        'scapy_length': scapy_info['payload_length'],
                        'difference': abs(pyshark_info['payload_length'] - scapy_info['payload_length']),
                        'impact': 'HIGH',
                        'reason': '载荷长度不一致会导致掩码范围错误'
                    })
                
                # 载荷内容哈希差异
                if (pyshark_info['payload_hash'] and scapy_info['payload_hash'] and 
                    pyshark_info['payload_hash'] != scapy_info['payload_hash']):
                    self.actual_risks['payload_content_mismatch'].append({
                        'packet_number': packet_num,
                        'type': 'content_mismatch',
                        'pyshark_hash': pyshark_info['payload_hash'],
                        'scapy_hash': scapy_info['payload_hash'],
                        'payload_length': pyshark_info['payload_length'],
                        'impact': 'CRITICAL',
                        'reason': '载荷内容不一致会导致掩码应用到错误数据'
                    })
    
    def _analyze_header_consistency(self) -> None:
        """分析头部信息一致性"""
        common_packets = set(self.pyshark_data.keys()) & set(self.scapy_data.keys())
        
        for packet_num in common_packets:
            pyshark_info = self.pyshark_data[packet_num]
            scapy_info = self.scapy_data[packet_num]
            
            # IP地址一致性
            if (pyshark_info['src_ip'] != scapy_info['src_ip'] or 
                pyshark_info['dst_ip'] != scapy_info['dst_ip']):
                self.actual_risks['header_inconsistency'].append({
                    'packet_number': packet_num,
                    'field': 'ip_addresses',
                    'pyshark_value': f"{pyshark_info['src_ip']}->{pyshark_info['dst_ip']}",
                    'scapy_value': f"{scapy_info['src_ip']}->{scapy_info['dst_ip']}",
                    'impact': 'CRITICAL',
                    'reason': 'IP地址不一致会导致流ID生成错误'
                })
            
            # 端口一致性
            if (pyshark_info['src_port'] != scapy_info['src_port'] or 
                pyshark_info['dst_port'] != scapy_info['dst_port']):
                self.actual_risks['header_inconsistency'].append({
                    'packet_number': packet_num,
                    'field': 'tcp_ports',
                    'pyshark_value': f"{pyshark_info['src_port']}->{pyshark_info['dst_port']}",
                    'scapy_value': f"{scapy_info['src_port']}->{scapy_info['dst_port']}",
                    'impact': 'CRITICAL',
                    'reason': '端口不一致会导致流ID生成错误'
                })
    
    def _analyze_packet_mapping(self) -> None:
        """分析数据包映射关系"""
        pyshark_packets = set(self.pyshark_data.keys())
        scapy_packets = set(self.scapy_data.keys())
        
        # 缺失的数据包
        missing_packets = pyshark_packets.symmetric_difference(scapy_packets)
        if missing_packets:
            self.actual_risks['packet_mapping_issues'].append({
                'missing_packets': list(missing_packets),
                'count': len(missing_packets),
                'impact': 'HIGH',
                'reason': '数据包映射不一致会导致载荷缓存失效'
            })
    
    def _analyze_extraction_success_rate(self) -> None:
        """分析载荷提取成功率"""
        
        # PyShark提取成功率
        pyshark_accessible = sum(1 for info in self.pyshark_data.values() 
                                if info['payload_accessible'])
        pyshark_total = len(self.pyshark_data)
        pyshark_success_rate = pyshark_accessible / pyshark_total if pyshark_total > 0 else 0
        
        # Scapy提取成功率
        scapy_accessible = sum(1 for info in self.scapy_data.values() 
                              if info['payload_accessible'])
        scapy_total = len(self.scapy_data)
        scapy_success_rate = scapy_accessible / scapy_total if scapy_total > 0 else 0
        
        # 如果成功率差异较大，记录为风险
        success_rate_diff = abs(pyshark_success_rate - scapy_success_rate)
        if success_rate_diff > 0.1:  # 超过10%差异
            self.actual_risks['payload_extraction_failures'].append({
                'pyshark_success_rate': pyshark_success_rate,
                'scapy_success_rate': scapy_success_rate,
                'difference': success_rate_diff,
                'pyshark_accessible': pyshark_accessible,
                'scapy_accessible': scapy_accessible,
                'impact': 'HIGH' if success_rate_diff > 0.3 else 'MEDIUM',
                'reason': '载荷提取成功率差异会导致掩码覆盖不一致'
            })
    
    def _generate_realistic_risk_report(self) -> Dict[str, Any]:
        """生成现实的风险评估报告"""
        
        # 计算实际风险
        total_actual_risks = sum(len(risks) for risks in self.actual_risks.values())
        critical_risks = sum(1 for risk_category in self.actual_risks.values() 
                           for risk in risk_category 
                           if risk.get('impact') == 'CRITICAL')
        high_risks = sum(1 for risk_category in self.actual_risks.values() 
                        for risk in risk_category 
                        if risk.get('impact') == 'HIGH')
        
        # 计算可解决的风险
        total_solvable_risks = sum(len(risks) for risks in self.solvable_risks.values())
        
        # 重新计算风险评分（只考虑实际风险）
        actual_risk_score = critical_risks * 10 + high_risks * 5
        
        # 重新确定总体风险等级
        if critical_risks > 0:
            overall_risk = "CRITICAL"
        elif high_risks > 2:
            overall_risk = "HIGH"
        elif total_actual_risks > 3:
            overall_risk = "MEDIUM"
        else:
            overall_risk = "LOW"
        
        # 计算实际载荷提取成功率
        pyshark_success_rate = sum(1 for info in self.pyshark_data.values() 
                                  if info['payload_accessible']) / len(self.pyshark_data)
        scapy_success_rate = sum(1 for info in self.scapy_data.values() 
                                if info['payload_accessible']) / len(self.scapy_data)
        
        report = {
            'summary': {
                'total_actual_risks': total_actual_risks,
                'total_solvable_risks': total_solvable_risks,
                'critical_risks': critical_risks,
                'high_risks': high_risks,
                'actual_risk_score': actual_risk_score,
                'overall_risk_level': overall_risk,
                'pyshark_success_rate': pyshark_success_rate,
                'scapy_success_rate': scapy_success_rate,
                'pyshark_packets': len(self.pyshark_data),
                'scapy_packets': len(self.scapy_data)
            },
            'actual_risks': self.actual_risks,
            'solvable_risks': self.solvable_risks,
            'recommendations': self._generate_realistic_recommendations(overall_risk, self.actual_risks)
        }
        
        return report
    
    def _generate_realistic_recommendations(self, risk_level: str, risks: Dict) -> List[str]:
        """生成基于实际风险的现实建议"""
        recommendations = []
        
        if risk_level == "LOW":
            recommendations.append("✅ 混合架构风险可控，建议谨慎实施")
            recommendations.append("🔧 实施序列号统一转换机制")
            recommendations.append("🔍 添加运行时一致性验证")
            
        elif risk_level == "MEDIUM":
            recommendations.append("⚠️  混合架构存在中等风险，需要额外措施")
            recommendations.append("🔧 实施序列号统一转换机制")
            recommendations.append("🔍 强化载荷一致性检查")
            recommendations.append("📊 监控载荷提取成功率")
            
        elif risk_level == "HIGH":
            recommendations.append("🚨 混合架构存在高风险，需谨慎评估")
            recommendations.append("🔧 必须实施完整的序列号统一机制")
            recommendations.append("🔍 必须实施载荷内容验证")
            recommendations.append("📊 必须监控所有一致性指标")
            
        else:  # CRITICAL
            recommendations.append("❌ 混合架构存在严重风险，强烈不建议使用")
            recommendations.append("🔄 建议继续优化单一引擎方案")
        
        # 针对具体风险的建议
        if risks['payload_content_mismatch']:
            recommendations.append("⚠️  载荷内容不匹配风险需要重点关注")
            
        if risks['header_inconsistency']:
            recommendations.append("🔢 头部信息不一致需要额外验证")
            
        if risks['payload_accessibility']:
            recommendations.append("📏 载荷可访问性差异需要补偿机制")
        
        return recommendations


def analyze_realistic_risk(pcap_file: str) -> None:
    """执行现实的一致性风险分析"""
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    logger.info("开始现实的混合架构风险分析...")
    
    try:
        # 创建风险分析器
        analyzer = ConsistencyRiskAnalyzerV2(pcap_file, logger)
        
        # 执行分析
        risk_report = analyzer.analyze_actual_risks()
        
        # 打印报告
        print("\n" + "="*80)
        print("🔄 混合架构现实风险分析报告（排除可解决问题）")
        print("="*80)
        
        summary = risk_report['summary']
        print(f"\n📊 概览:")
        print(f"   实际风险数量: {summary['total_actual_risks']}")
        print(f"   可解决风险数量: {summary['total_solvable_risks']}")
        print(f"   严重风险: {summary['critical_risks']}")
        print(f"   高风险: {summary['high_risks']}")
        print(f"   实际风险评分: {summary['actual_risk_score']}")
        print(f"   总体风险等级: {summary['overall_risk_level']}")
        print(f"   PyShark载荷成功率: {summary['pyshark_success_rate']:.1%}")
        print(f"   Scapy载荷成功率: {summary['scapy_success_rate']:.1%}")
        
        # 实际风险详情
        print(f"\n🔍 实际风险分析:")
        for risk_type, risk_list in risk_report['actual_risks'].items():
            if risk_list:
                print(f"   {risk_type}: {len(risk_list)} 个风险")
                for i, risk in enumerate(risk_list[:2]):  # 只显示前2个
                    print(f"     - {risk}")
                if len(risk_list) > 2:
                    print(f"     ... 还有 {len(risk_list)-2} 个风险")
        
        # 可解决的风险
        print(f"\n✅ 可解决的风险:")
        for risk_type, risk_list in risk_report['solvable_risks'].items():
            if risk_list:
                print(f"   {risk_type}: {len(risk_list)} 个（可通过技术手段解决）")
        
        # 建议
        print(f"\n💡 现实建议:")
        for recommendation in risk_report['recommendations']:
            print(f"   {recommendation}")
        
        print("\n" + "="*80)
        
    except Exception as e:
        logger.error(f"风险分析失败: {e}")
        raise


if __name__ == "__main__":
    # 分析TLS样本的现实风险
    pcap_file = "tests/data/tls-single/tls_sample.pcap"
    analyze_realistic_risk(pcap_file) 