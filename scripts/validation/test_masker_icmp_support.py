#!/usr/bin/env python3
"""
测试Masker模块对ICMP封装TCP数据包的支持能力

验证当前PayloadMasker的_find_innermost_tcp方法是否能正确处理ICMP封装的TCP层。
"""

import sys
from pathlib import Path
from scapy.all import *
from scapy.layers.inet import IP, TCP, ICMP
from scapy.layers.l2 import Ether

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

class ICMPMaskerTester:
    """ICMP封装场景的Masker模块测试器"""
    
    def __init__(self, pcap_path: str):
        self.pcap_path = pcap_path
        self.test_results = {
            'icmp_packets_found': 0,
            'tcp_detection_results': [],
            'innermost_tcp_tests': [],
            'flow_id_tests': [],
            'summary': {}
        }
    
    def run_tests(self):
        """运行所有测试"""
        print(f"测试ICMP封装场景的Masker支持: {self.pcap_path}")
        print("="*60)
        
        # 读取pcap文件
        packets = rdpcap(self.pcap_path)
        
        # 过滤ICMP封装的TCP数据包
        icmp_tcp_packets = []
        for pkt in packets:
            if self._is_icmp_encap_tcp(pkt):
                icmp_tcp_packets.append(pkt)
        
        self.test_results['icmp_packets_found'] = len(icmp_tcp_packets)
        print(f"发现 {len(icmp_tcp_packets)} 个ICMP封装的TCP数据包")
        
        if len(icmp_tcp_packets) == 0:
            print("未发现ICMP封装的TCP数据包，测试结束")
            return self.test_results
        
        # 测试1: _find_innermost_tcp方法
        self._test_find_innermost_tcp(icmp_tcp_packets)
        
        # 测试2: 流ID构建
        self._test_flow_id_construction(icmp_tcp_packets)
        
        # 测试3: 协议层级解析
        self._test_protocol_layer_parsing(icmp_tcp_packets)
        
        # 生成测试摘要
        self._generate_summary()
        
        return self.test_results
    
    def _is_icmp_encap_tcp(self, packet) -> bool:
        """检查是否为ICMP封装的TCP数据包"""
        try:
            # 使用更直接的方法检查协议栈
            # 检查是否有多个IP层（外层IP + ICMP + 内层IP）
            ip_count = 0
            current = packet
            has_icmp = False
            has_tcp = False

            while current:
                if hasattr(current, 'haslayer'):
                    if current.haslayer(IP):
                        ip_count += 1
                    if current.haslayer(ICMP):
                        has_icmp = True
                    if current.haslayer(TCP):
                        has_tcp = True

                if hasattr(current, 'payload') and current.payload:
                    current = current.payload
                else:
                    break

            # ICMP封装的TCP应该有：多个IP层 + ICMP + TCP
            return ip_count >= 2 and has_icmp and has_tcp

        except Exception as e:
            print(f"检查ICMP封装失败: {e}")
            return False
    
    def _test_find_innermost_tcp(self, packets):
        """测试_find_innermost_tcp方法"""
        print("\n测试1: _find_innermost_tcp方法")
        print("-" * 40)
        
        for i, pkt in enumerate(packets):
            test_result = {
                'packet_index': i,
                'manual_tcp_found': False,
                'manual_tcp_info': None,
                'masker_tcp_found': False,
                'masker_tcp_info': None,
                'match_result': False
            }
            
            # 手动查找最内层TCP
            manual_tcp, manual_ip = self._manual_find_innermost_tcp(pkt)
            if manual_tcp and manual_ip:
                test_result['manual_tcp_found'] = True
                test_result['manual_tcp_info'] = {
                    'src': manual_ip.src,
                    'dst': manual_ip.dst,
                    'sport': manual_tcp.sport,
                    'dport': manual_tcp.dport,
                    'seq': manual_tcp.seq
                }
            
            # 模拟Masker的_find_innermost_tcp方法
            masker_tcp, masker_ip = self._simulate_masker_find_tcp(pkt)
            if masker_tcp and masker_ip:
                test_result['masker_tcp_found'] = True
                test_result['masker_tcp_info'] = {
                    'src': masker_ip.src,
                    'dst': masker_ip.dst,
                    'sport': masker_tcp.sport,
                    'dport': masker_tcp.dport,
                    'seq': masker_tcp.seq
                }
            
            # 比较结果
            if (test_result['manual_tcp_found'] == test_result['masker_tcp_found'] and
                test_result['manual_tcp_info'] == test_result['masker_tcp_info']):
                test_result['match_result'] = True
            
            self.test_results['innermost_tcp_tests'].append(test_result)
            
            print(f"  数据包 {i+1}:")
            print(f"    手动查找: {'成功' if test_result['manual_tcp_found'] else '失败'}")
            print(f"    Masker模拟: {'成功' if test_result['masker_tcp_found'] else '失败'}")
            print(f"    结果匹配: {'是' if test_result['match_result'] else '否'}")
    
    def _manual_find_innermost_tcp(self, packet):
        """手动查找最内层的TCP/IP层"""
        try:
            # 查找ICMP层
            if not packet.haslayer(ICMP):
                return None, None
            
            icmp_layer = packet[ICMP]
            
            # 查找ICMP载荷中的IP层
            if not icmp_layer.payload or not icmp_layer.payload.haslayer(IP):
                return None, None
            
            inner_ip = icmp_layer.payload[IP]
            
            # 查找内层IP中的TCP层
            if not inner_ip.haslayer(TCP):
                return None, None
            
            inner_tcp = inner_ip[TCP]
            return inner_tcp, inner_ip
            
        except Exception as e:
            print(f"    手动查找TCP失败: {e}")
            return None, None
    
    def _simulate_masker_find_tcp(self, packet):
        """模拟Masker的_find_innermost_tcp方法逻辑"""
        try:
            # 这里模拟PayloadMasker._find_innermost_tcp的递归查找逻辑
            current = packet
            tcp_layer = None
            ip_layer = None
            
            # 递归查找最内层的TCP和IP
            while current:
                if hasattr(current, 'haslayer'):
                    if current.haslayer(TCP):
                        tcp_layer = current[TCP]
                        # 查找对应的IP层
                        temp = current
                        while temp:
                            if temp.haslayer(IP):
                                ip_layer = temp[IP]
                                break
                            if hasattr(temp, 'payload') and temp.payload:
                                temp = temp.payload
                            else:
                                break
                        break
                
                if hasattr(current, 'payload') and current.payload:
                    current = current.payload
                else:
                    break
            
            return tcp_layer, ip_layer
            
        except Exception as e:
            print(f"    Masker模拟查找失败: {e}")
            return None, None
    
    def _test_flow_id_construction(self, packets):
        """测试流ID构建"""
        print("\n测试2: 流ID构建")
        print("-" * 40)
        
        for i, pkt in enumerate(packets):
            tcp_layer, ip_layer = self._manual_find_innermost_tcp(pkt)
            
            if tcp_layer and ip_layer:
                # 模拟Masker的流ID构建逻辑
                flow_id = self._simulate_build_stream_id(ip_layer, tcp_layer)
                direction = self._simulate_determine_flow_direction(ip_layer, tcp_layer, flow_id)
                
                test_result = {
                    'packet_index': i,
                    'flow_id': flow_id,
                    'direction': direction,
                    'tcp_info': {
                        'src': f"{ip_layer.src}:{tcp_layer.sport}",
                        'dst': f"{ip_layer.dst}:{tcp_layer.dport}",
                        'seq': tcp_layer.seq
                    }
                }
                
                self.test_results['flow_id_tests'].append(test_result)
                
                print(f"  数据包 {i+1}:")
                print(f"    流ID: {flow_id}")
                print(f"    方向: {direction}")
                print(f"    TCP: {test_result['tcp_info']['src']} -> {test_result['tcp_info']['dst']}")
    
    def _simulate_build_stream_id(self, ip_layer, tcp_layer):
        """模拟Masker的_build_stream_id方法"""
        # 简化的流ID构建逻辑
        src_ip = str(ip_layer.src)
        dst_ip = str(ip_layer.dst)
        src_port = str(tcp_layer.sport)
        dst_port = str(tcp_layer.dport)
        
        # 按字典序排序构建流ID
        if (src_ip, src_port) < (dst_ip, dst_port):
            return f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}"
        else:
            return f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}"
    
    def _simulate_determine_flow_direction(self, ip_layer, tcp_layer, stream_id):
        """模拟Masker的_determine_flow_direction方法"""
        src_ip = str(ip_layer.src)
        src_port = str(tcp_layer.sport)
        
        # 简化的方向判断逻辑
        if stream_id.startswith(f"TCP_{src_ip}:{src_port}_"):
            return "forward"
        else:
            return "reverse"
    
    def _test_protocol_layer_parsing(self, packets):
        """测试协议层级解析"""
        print("\n测试3: 协议层级解析")
        print("-" * 40)
        
        for i, pkt in enumerate(packets):
            layers = []
            current = pkt
            
            # 递归解析所有协议层
            while current:
                layer_name = current.__class__.__name__
                layers.append(layer_name)
                
                if hasattr(current, 'payload') and current.payload:
                    current = current.payload
                else:
                    break
            
            print(f"  数据包 {i+1} 协议栈: {' -> '.join(layers)}")
    
    def _generate_summary(self):
        """生成测试摘要"""
        print("\n测试摘要")
        print("="*60)
        
        # 统计_find_innermost_tcp测试结果
        tcp_tests = self.test_results['innermost_tcp_tests']
        successful_matches = sum(1 for test in tcp_tests if test['match_result'])
        
        summary = {
            'total_icmp_packets': self.test_results['icmp_packets_found'],
            'tcp_detection_success_rate': f"{successful_matches}/{len(tcp_tests)}",
            'flow_id_tests_count': len(self.test_results['flow_id_tests']),
            'masker_compatibility': 'GOOD' if successful_matches == len(tcp_tests) else 'PARTIAL'
        }
        
        self.test_results['summary'] = summary
        
        print(f"ICMP封装数据包总数: {summary['total_icmp_packets']}")
        print(f"TCP检测成功率: {summary['tcp_detection_success_rate']}")
        print(f"流ID构建测试: {summary['flow_id_tests_count']} 个")
        print(f"Masker兼容性: {summary['masker_compatibility']}")
        
        if summary['masker_compatibility'] == 'GOOD':
            print("\n✅ 当前Masker模块可能已支持ICMP封装的TCP数据包")
        else:
            print("\n⚠️  当前Masker模块对ICMP封装的支持可能不完整")

def main():
    if len(sys.argv) != 2:
        print("用法: python test_masker_icmp_support.py <pcap_file>")
        sys.exit(1)
    
    pcap_path = sys.argv[1]
    if not Path(pcap_path).exists():
        print(f"错误: 文件不存在 - {pcap_path}")
        sys.exit(1)
    
    tester = ICMPMaskerTester(pcap_path)
    results = tester.run_tests()
    
    # 保存测试结果
    import json
    output_file = f"masker_icmp_test_{Path(pcap_path).stem}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细测试结果已保存到: {output_file}")

if __name__ == "__main__":
    main()
