#!/usr/bin/env python3
"""
ICMP封装TCP+TLS场景分析工具

分析ICMP协议内封装TCP+TLS消息的边缘场景，评估当前PktMask双模块架构的支持能力。

测试样本：tls_1_2_single_vlan.pcap
失败帧：807, 857, 859 (协议路径: eth:ethertype:vlan:ethertype:ip:icmp:ip:tcp:tls)
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

class ICMPEncapAnalyzer:
    """ICMP封装场景分析器"""
    
    def __init__(self, pcap_path: str):
        self.pcap_path = pcap_path
        self.analysis_results = {
            'icmp_encap_packets': [],
            'protocol_layers': {},
            'tcp_streams': {},
            'tls_messages': {},
            'architecture_impact': {}
        }
    
    def analyze(self) -> Dict[str, Any]:
        """执行完整分析"""
        print(f"分析ICMP封装场景: {self.pcap_path}")
        
        # 1. 识别ICMP封装的TCP+TLS数据包
        self._identify_icmp_encap_packets()
        
        # 2. 分析协议层级结构
        self._analyze_protocol_layers()
        
        # 3. 分析TCP流特征
        self._analyze_tcp_streams()
        
        # 4. 分析TLS消息特征
        self._analyze_tls_messages()
        
        # 5. 评估架构影响
        self._assess_architecture_impact()
        
        return self.analysis_results
    
    def _identify_icmp_encap_packets(self):
        """识别ICMP封装的TCP+TLS数据包"""
        print("步骤1: 识别ICMP封装的TCP+TLS数据包")
        
        # 使用tshark查找ICMP封装的TLS数据包
        cmd = [
            'tshark', '-r', self.pcap_path,
            '-Y', 'icmp and tcp and tls',
            '-T', 'json'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packets = json.loads(result.stdout)
            
            for packet in packets:
                frame_info = self._extract_frame_info(packet)
                self.analysis_results['icmp_encap_packets'].append(frame_info)
                
            print(f"  发现 {len(packets)} 个ICMP封装的TCP+TLS数据包")
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(f"  错误: 无法分析ICMP封装数据包 - {e}")
    
    def _extract_frame_info(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """提取帧信息"""
        layers = packet.get("_source", {}).get("layers", {})
        
        frame_info = {
            'frame_number': layers.get("frame", {}).get("frame.number"),
            'protocols': layers.get("frame", {}).get("frame.protocols"),
            'frame_len': layers.get("frame", {}).get("frame.len"),
            'outer_ip': self._extract_outer_ip_info(layers),
            'icmp': self._extract_icmp_info(layers),
            'inner_ip': self._extract_inner_ip_info(layers),
            'tcp': self._extract_tcp_info(layers),
            'tls': self._extract_tls_info(layers)
        }
        
        return frame_info
    
    def _extract_outer_ip_info(self, layers: Dict[str, Any]) -> Dict[str, Any]:
        """提取外层IP信息"""
        ip_layer = layers.get("ip", {})
        return {
            'src': ip_layer.get("ip.src"),
            'dst': ip_layer.get("ip.dst"),
            'proto': ip_layer.get("ip.proto"),
            'len': ip_layer.get("ip.len")
        }
    
    def _extract_icmp_info(self, layers: Dict[str, Any]) -> Dict[str, Any]:
        """提取ICMP信息"""
        icmp_layer = layers.get("icmp", {})
        return {
            'type': icmp_layer.get("icmp.type"),
            'code': icmp_layer.get("icmp.code")
        }
    
    def _extract_inner_ip_info(self, layers: Dict[str, Any]) -> Dict[str, Any]:
        """提取内层IP信息（ICMP载荷中的IP）"""
        icmp_layer = layers.get("icmp", {})
        inner_ip = icmp_layer.get("ip", {})
        return {
            'src': inner_ip.get("ip.src"),
            'dst': inner_ip.get("ip.dst"),
            'proto': inner_ip.get("ip.proto"),
            'len': inner_ip.get("ip.len")
        }
    
    def _extract_tcp_info(self, layers: Dict[str, Any]) -> Dict[str, Any]:
        """提取TCP信息（ICMP载荷中的TCP）"""
        icmp_layer = layers.get("icmp", {})
        tcp_layer = icmp_layer.get("tcp", {})
        return {
            'srcport': tcp_layer.get("tcp.srcport"),
            'dstport': tcp_layer.get("tcp.dstport"),
            'seq': tcp_layer.get("tcp.seq"),
            'ack': tcp_layer.get("tcp.ack"),
            'stream': tcp_layer.get("tcp.stream"),
            'payload_len': len(tcp_layer.get("tcp.payload", "").replace(":", "")) // 2 if tcp_layer.get("tcp.payload") else 0
        }
    
    def _extract_tls_info(self, layers: Dict[str, Any]) -> Dict[str, Any]:
        """提取TLS信息（ICMP载荷中的TLS）"""
        icmp_layer = layers.get("icmp", {})
        tls_layer = icmp_layer.get("tls", {})
        tls_record = tls_layer.get("tls.record", {})
        
        return {
            'content_type': tls_record.get("tls.record.content_type"),
            'version': tls_record.get("tls.record.version"),
            'length': tls_record.get("tls.record.length"),
            'is_application_data': tls_record.get("tls.record.content_type") == "23"
        }
    
    def _analyze_protocol_layers(self):
        """分析协议层级结构"""
        print("步骤2: 分析协议层级结构")
        
        layer_patterns = {}
        for packet in self.analysis_results['icmp_encap_packets']:
            protocols = packet.get('protocols', '')
            if protocols not in layer_patterns:
                layer_patterns[protocols] = 0
            layer_patterns[protocols] += 1
        
        self.analysis_results['protocol_layers'] = {
            'patterns': layer_patterns,
            'complexity': len(layer_patterns),
            'most_common': max(layer_patterns.items(), key=lambda x: x[1]) if layer_patterns else None
        }
        
        print(f"  发现 {len(layer_patterns)} 种协议层级模式")
        for pattern, count in layer_patterns.items():
            print(f"    {pattern}: {count} 个数据包")
    
    def _analyze_tcp_streams(self):
        """分析TCP流特征"""
        print("步骤3: 分析TCP流特征")
        
        streams = {}
        for packet in self.analysis_results['icmp_encap_packets']:
            tcp_info = packet.get('tcp', {})
            stream_id = tcp_info.get('stream')
            
            if stream_id:
                if stream_id not in streams:
                    streams[stream_id] = {
                        'packets': [],
                        'seq_numbers': [],
                        'ports': set()
                    }
                
                streams[stream_id]['packets'].append(packet['frame_number'])
                streams[stream_id]['seq_numbers'].append(tcp_info.get('seq'))
                streams[stream_id]['ports'].add(f"{tcp_info.get('srcport')}-{tcp_info.get('dstport')}")

        # 转换set为list以便JSON序列化
        for stream_id in streams:
            streams[stream_id]['ports'] = list(streams[stream_id]['ports'])
        
        self.analysis_results['tcp_streams'] = streams
        print(f"  发现 {len(streams)} 个TCP流")
        for stream_id, info in streams.items():
            print(f"    流 {stream_id}: {len(info['packets'])} 个数据包, 端口 {info['ports']}")
    
    def _analyze_tls_messages(self):
        """分析TLS消息特征"""
        print("步骤4: 分析TLS消息特征")
        
        tls_types = {}
        truncated_messages = 0
        
        for packet in self.analysis_results['icmp_encap_packets']:
            tls_info = packet.get('tls', {})
            content_type = tls_info.get('content_type')
            
            if content_type:
                if content_type not in tls_types:
                    tls_types[content_type] = 0
                tls_types[content_type] += 1
                
                # 检查是否为截断的TLS消息（ICMP通常只包含原始数据包的前几个字节）
                tcp_payload_len = packet.get('tcp', {}).get('payload_len', 0)
                tls_record_len = int(tls_info.get('length', 0)) if tls_info.get('length') else 0
                
                if tcp_payload_len < tls_record_len + 5:  # 5字节TLS头部
                    truncated_messages += 1
        
        self.analysis_results['tls_messages'] = {
            'types': tls_types,
            'truncated_count': truncated_messages,
            'total_count': len(self.analysis_results['icmp_encap_packets'])
        }
        
        print(f"  TLS消息类型分布: {tls_types}")
        print(f"  截断的TLS消息: {truncated_messages}/{len(self.analysis_results['icmp_encap_packets'])}")
    
    def _assess_architecture_impact(self):
        """评估对当前架构的影响"""
        print("步骤5: 评估架构影响")
        
        impact = {
            'marker_module_impact': self._assess_marker_impact(),
            'masker_module_impact': self._assess_masker_impact(),
            'protocol_support_gap': self._assess_protocol_gap(),
            'recommendations': self._generate_recommendations()
        }
        
        self.analysis_results['architecture_impact'] = impact
    
    def _assess_marker_impact(self) -> Dict[str, Any]:
        """评估对Marker模块的影响"""
        return {
            'current_tcp_detection': "仅支持直接TCP流，不支持ICMP封装的TCP",
            'tshark_filter_limitation': "当前tshark过滤器无法处理ICMP内的TCP流",
            'sequence_number_issue': "ICMP载荷中的TCP序列号可能不完整",
            'flow_reconstruction': "无法重组ICMP封装的TCP流"
        }
    
    def _assess_masker_impact(self) -> Dict[str, Any]:
        """评估对Masker模块的影响"""
        return {
            'packet_parsing': "scapy的_find_innermost_tcp可能支持ICMP封装",
            'rule_matching': "保留规则基于TCP流ID，ICMP封装流ID可能不匹配",
            'payload_modification': "ICMP载荷修改需要特殊处理",
            'checksum_recalculation': "需要重新计算ICMP和内层TCP校验和"
        }
    
    def _assess_protocol_gap(self) -> Dict[str, Any]:
        """评估协议支持缺口"""
        return {
            'encapsulation_types': ["ICMP错误消息封装", "可能还有其他隧道协议"],
            'detection_coverage': "当前架构未考虑多层封装场景",
            'processing_complexity': "需要递归解析多层协议栈"
        }
    
    def _generate_recommendations(self) -> List[str]:
        """生成解决方案建议"""
        return [
            "方案1: 将ICMP封装场景排除在支持范围外（推荐）",
            "方案2: 扩展Marker模块支持ICMP封装的TCP流分析",
            "方案3: 在Masker模块中添加ICMP封装检测和处理逻辑",
            "方案4: 创建专门的封装协议处理器"
        ]
    
    def print_summary(self):
        """打印分析摘要"""
        print("\n" + "="*60)
        print("ICMP封装TCP+TLS场景分析摘要")
        print("="*60)
        
        icmp_packets = len(self.analysis_results['icmp_encap_packets'])
        print(f"ICMP封装数据包数量: {icmp_packets}")
        
        if icmp_packets > 0:
            print(f"协议层级模式: {self.analysis_results['protocol_layers']['complexity']} 种")
            print(f"涉及TCP流: {len(self.analysis_results['tcp_streams'])} 个")
            print(f"TLS消息类型: {list(self.analysis_results['tls_messages']['types'].keys())}")
            print(f"截断消息比例: {self.analysis_results['tls_messages']['truncated_count']}/{icmp_packets}")
            
            print("\n架构影响评估:")
            impact = self.analysis_results['architecture_impact']
            print("  Marker模块: 需要扩展ICMP封装支持")
            print("  Masker模块: 可能已有基础支持，需验证")
            
            print("\n推荐方案:")
            for i, rec in enumerate(impact['recommendations'], 1):
                print(f"  {i}. {rec}")
        else:
            print("未发现ICMP封装的TCP+TLS数据包")

def main():
    if len(sys.argv) != 2:
        print("用法: python analyze_icmp_encap_scenario.py <pcap_file>")
        sys.exit(1)
    
    pcap_path = sys.argv[1]
    if not Path(pcap_path).exists():
        print(f"错误: 文件不存在 - {pcap_path}")
        sys.exit(1)
    
    analyzer = ICMPEncapAnalyzer(pcap_path)
    results = analyzer.analyze()
    analyzer.print_summary()
    
    # 保存详细结果
    output_file = f"icmp_encap_analysis_{Path(pcap_path).stem}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细分析结果已保存到: {output_file}")

if __name__ == "__main__":
    main()
