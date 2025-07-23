"""
第二阶段测试：IP匿名化增强功能

验证多层封装IP匿名化处理：
- 多层IP地址预扫描
- 封装内IP地址提取
- 分层IP匿名化处理
- 封装统计报告
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch
from scapy.packet import Packet
from scapy.layers.inet import IP, TCP
from scapy.layers.l2 import Ether, Dot1Q
from scapy.utils import wrpcap

# 测试imports
try:
    from src.pktmask.core.strategy import HierarchicalAnonymizationStrategy
    from src.pktmask.core.encapsulation import EncapsulationType
except ImportError:
    pytest.skip("IP匿名化模块未找到，跳过测试", allow_module_level=True)


class TestEnhancedIPAnonymization:
    """测试增强的IP匿名化策略"""
    
    def setup_method(self):
        """测试初始化"""
        self.strategy = HierarchicalAnonymizationStrategy()
    
    def test_strategy_initialization_with_encapsulation_support(self):
        """测试策略初始化包含封装支持"""
        assert self.strategy is not None
        assert hasattr(self.strategy, '_encap_adapter')
        assert hasattr(self.strategy, '_encap_stats')
        
        # 验证封装统计初始化
        assert self.strategy._encap_stats['total_packets_scanned'] == 0
        assert self.strategy._encap_stats['encapsulated_packets'] == 0
        assert self.strategy._encap_stats['multi_layer_ip_packets'] == 0
        assert self.strategy._encap_stats['plain_packets'] == 0
    
    def test_reset_with_encapsulation_stats(self):
        """测试重置功能包含封装统计重置"""
        # 设置一些统计数据
        self.strategy._encap_stats['total_packets_scanned'] = 100
        self.strategy._encap_stats['encapsulated_packets'] = 30
        
        # 重置
        self.strategy.reset()
        
        # 验证统计已重置
        assert self.strategy._encap_stats['total_packets_scanned'] == 0
        assert self.strategy._encap_stats['encapsulated_packets'] == 0
        assert len(self.strategy.get_ip_map()) == 0
    
    def test_prescan_plain_packets(self):
        """测试预扫描普通数据包"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建测试pcap文件 - 普通IP包
            test_file = os.path.join(temp_dir, "test_plain.pcap")
            packets = [
                Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(),
                Ether() / IP(src="192.168.1.3", dst="192.168.1.4") / TCP(),
                Ether() / IP(src="10.0.0.1", dst="10.0.0.2") / TCP(),
            ]
            wrpcap(test_file, packets)
            
            # 预扫描地址
            files_to_process = ["test_plain.pcap"]
            error_log = []
            
            freqs_ipv4, freqs_ipv6, unique_ips = self.strategy._prescan_addresses(
                files_to_process, temp_dir, error_log
            )
            
            # 验证扫描结果
            assert len(unique_ips) >= 6  # 至少6个IP地址
            assert len(error_log) == 0
            
            # 验证封装统计
            assert self.strategy._encap_stats['total_packets_scanned'] == 3
            assert self.strategy._encap_stats['plain_packets'] >= 3  # 大部分是普通包
            
            # 验证IP频率统计
            assert '192' in freqs_ipv4[0]  # IPv4 A段
            assert '10' in freqs_ipv4[0]
            assert '192.168' in freqs_ipv4[1]  # IPv4 A.B段
    
    def test_prescan_vlan_packets(self):
        """测试预扫描VLAN封装数据包"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建测试pcap文件 - VLAN包
            test_file = os.path.join(temp_dir, "test_vlan.pcap")
            packets = [
                Ether() / Dot1Q(vlan=100) / IP(src="172.16.1.1", dst="172.16.1.2") / TCP(),
                Ether() / Dot1Q(vlan=200) / IP(src="172.16.2.1", dst="172.16.2.2") / TCP(),
                Ether() / Dot1Q(vlan=100) / IP(src="172.16.1.3", dst="172.16.1.4") / TCP(),
            ]
            wrpcap(test_file, packets)
            
            # 预扫描地址  
            files_to_process = ["test_vlan.pcap"]
            error_log = []
            
            freqs_ipv4, freqs_ipv6, unique_ips = self.strategy._prescan_addresses(
                files_to_process, temp_dir, error_log
            )
            
            # 验证扫描结果
            assert len(unique_ips) >= 6  # 6个IP地址
            assert len(error_log) == 0
            
            # 验证封装统计
            assert self.strategy._encap_stats['total_packets_scanned'] == 3
            assert self.strategy._encap_stats['encapsulated_packets'] >= 3  # 所有包都是封装包
            
            # 验证VLAN内IP被正确提取
            assert '172' in freqs_ipv4[0]  # IPv4 A段
            assert '172.16' in freqs_ipv4[1]  # IPv4 A.B段
    
    def test_prescan_mixed_packets(self):
        """测试预扫描混合数据包（普通+VLAN）"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建测试pcap文件 - 混合包
            test_file = os.path.join(temp_dir, "test_mixed.pcap") 
            packets = [
                # 普通IP包
                Ether() / IP(src="10.1.1.1", dst="10.1.1.2") / TCP(),
                # VLAN包
                Ether() / Dot1Q(vlan=100) / IP(src="10.1.2.1", dst="10.1.2.2") / TCP(),
                # 另一个普通包
                Ether() / IP(src="10.1.1.3", dst="10.1.1.4") / TCP(),
            ]
            wrpcap(test_file, packets)
            
            # 预扫描地址
            files_to_process = ["test_mixed.pcap"]
            error_log = []
            
            freqs_ipv4, freqs_ipv6, unique_ips = self.strategy._prescan_addresses(
                files_to_process, temp_dir, error_log
            )
            
            # 验证扫描结果
            assert len(unique_ips) >= 6
            assert len(error_log) == 0
            
            # 验证混合封装统计
            assert self.strategy._encap_stats['total_packets_scanned'] == 3
            assert self.strategy._encap_stats['plain_packets'] >= 2  # 至少2个普通包
            assert self.strategy._encap_stats['encapsulated_packets'] >= 1  # 至少1个封装包
            
            # 验证所有IP都被正确提取
            assert '10' in freqs_ipv4[0]
            assert '10.1' in freqs_ipv4[1]
    
    def test_create_mapping_with_encapsulation_stats(self):
        """测试映射创建包含封装统计"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建测试数据
            test_file = os.path.join(temp_dir, "test_mapping.pcap")
            packets = [
                Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(),
                Ether() / Dot1Q(vlan=100) / IP(src="10.0.1.1", dst="10.0.1.2") / TCP(),
            ]
            wrpcap(test_file, packets)
            
            # 创建映射
            files_to_process = ["test_mapping.pcap"]
            error_log = []
            
            mapping = self.strategy.create_mapping(files_to_process, temp_dir, error_log)
            
            # 验证映射创建
            assert isinstance(mapping, dict)
            assert len(mapping) >= 4  # 至少4个IP映射
            assert len(error_log) == 0
            
            # 验证原IP存在于映射中
            original_ips = {"192.168.1.1", "192.168.1.2", "10.0.1.1", "10.0.1.2"}
            assert all(ip in mapping for ip in original_ips)
            
            # 验证映射后的IP不同于原IP
            for orig_ip, mapped_ip in mapping.items():
                assert orig_ip != mapped_ip
                assert orig_ip in original_ips
    
    def test_anonymize_plain_packet(self):
        """测试匿名化普通数据包"""
        # 设置映射
        self.strategy._ip_map = {
            "192.168.1.1": "10.0.0.1",
            "192.168.1.2": "10.0.0.2"
        }
        
        # 创建测试包
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        
        # 匿名化
        anonymized_packet, is_anonymized = self.strategy.anonymize_packet(packet)
        
        # 验证匿名化结果
        assert is_anonymized == True
        assert anonymized_packet[IP].src == "10.0.0.1"
        assert anonymized_packet[IP].dst == "10.0.0.2"
    
    def test_anonymize_vlan_packet(self):
        """测试匿名化VLAN封装数据包"""
        # 设置映射
        self.strategy._ip_map = {
            "172.16.1.1": "10.10.1.1", 
            "172.16.1.2": "10.10.1.2"
        }
        
        # 创建VLAN测试包
        packet = Ether() / Dot1Q(vlan=100) / IP(src="172.16.1.1", dst="172.16.1.2") / TCP()
        
        # 匿名化
        anonymized_packet, is_anonymized = self.strategy.anonymize_packet(packet)
        
        # 验证匿名化结果
        assert is_anonymized == True
        assert anonymized_packet[Dot1Q].vlan == 100  # VLAN ID保持不变
        assert anonymized_packet[IP].src == "10.10.1.1"
        assert anonymized_packet[IP].dst == "10.10.1.2"
    
    def test_anonymize_packet_not_in_mapping(self):
        """测试匿名化映射中不存在的IP"""
        # 设置有限映射
        self.strategy._ip_map = {
            "192.168.1.1": "10.0.0.1"
        }
        
        # 创建包含未映射IP的测试包
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.99") / TCP()
        
        # 匿名化
        anonymized_packet, is_anonymized = self.strategy.anonymize_packet(packet)
        
        # 验证匿名化结果
        assert is_anonymized == True  # 因为src被匿名化了
        assert anonymized_packet[IP].src == "10.0.0.1"  # 映射的IP被匿名化
        assert anonymized_packet[IP].dst == "192.168.1.99"  # 未映射的IP保持不变
    
    def test_anonymize_packet_no_mapping(self):
        """测试没有映射时的匿名化"""
        # 清空映射
        self.strategy._ip_map = {}
        
        # 创建测试包
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        
        # 匿名化
        anonymized_packet, is_anonymized = self.strategy.anonymize_packet(packet)
        
        # 验证匿名化结果
        assert is_anonymized == False  # 没有IP被匿名化
        assert anonymized_packet[IP].src == "192.168.1.1"  # IP保持不变
        assert anonymized_packet[IP].dst == "192.168.1.2"


class TestEncapsulationStatistics:
    """测试封装统计功能"""
    
    def setup_method(self):
        """测试初始化"""
        self.strategy = HierarchicalAnonymizationStrategy()
    
    def test_encapsulation_stats_initialization(self):
        """测试封装统计初始化"""
        stats = self.strategy._encap_stats
        assert stats['total_packets_scanned'] == 0
        assert stats['encapsulated_packets'] == 0
        assert stats['multi_layer_ip_packets'] == 0
        assert stats['plain_packets'] == 0
    
    def test_stats_collection_during_prescan(self):
        """测试预扫描期间的统计收集"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建混合测试数据
            test_file = os.path.join(temp_dir, "test_stats.pcap")
            packets = [
                Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(),  # 普通包
                Ether() / Dot1Q(vlan=100) / IP(src="10.0.1.1", dst="10.0.1.2") / TCP(),  # VLAN包  
                Ether() / IP(src="172.16.1.1", dst="172.16.1.2") / TCP(),  # 普通包
            ]
            wrpcap(test_file, packets)
            
            # 执行预扫描
            files_to_process = ["test_stats.pcap"]
            error_log = []
            
            self.strategy._prescan_addresses(files_to_process, temp_dir, error_log)
            
            # 验证统计
            stats = self.strategy._encap_stats
            assert stats['total_packets_scanned'] == 3
            assert stats['plain_packets'] >= 2
            assert stats['encapsulated_packets'] >= 1
            
            # 验证统计总和
            total_categorized = (stats['plain_packets'] + 
                               stats['encapsulated_packets'])
            assert total_categorized == stats['total_packets_scanned']


class TestEncapsulationIntegration:
    """测试封装处理集成功能"""
    
    def setup_method(self):
        """测试初始化"""
        self.strategy = HierarchicalAnonymizationStrategy()
    
    def test_end_to_end_vlan_processing(self):
        """测试端到端VLAN数据包处理"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建VLAN测试数据
            test_file = os.path.join(temp_dir, "test_e2e_vlan.pcap")
            packets = [
                Ether() / Dot1Q(vlan=100, prio=2) / IP(src="192.168.100.1", dst="192.168.100.2") / TCP(sport=80, dport=8080),
                Ether() / Dot1Q(vlan=100, prio=2) / IP(src="192.168.100.2", dst="192.168.100.1") / TCP(sport=8080, dport=80),
            ]
            wrpcap(test_file, packets)
            
            # 1. 创建映射
            files_to_process = ["test_e2e_vlan.pcap"]
            error_log = []
            
            mapping = self.strategy.create_mapping(files_to_process, temp_dir, error_log)
            
            # 验证映射
            assert len(mapping) >= 2
            assert "192.168.100.1" in mapping
            assert "192.168.100.2" in mapping
            
            # 2. 匿名化数据包
            for i, packet in enumerate(packets):
                # 在匿名化前记录原始IP
                orig_src = packet[IP].src
                orig_dst = packet[IP].dst
                
                anonymized_packet, is_anonymized = self.strategy.anonymize_packet(packet)
                
                # 验证匿名化
                assert is_anonymized == True
                assert anonymized_packet[Dot1Q].vlan == 100  # VLAN保持不变
                assert anonymized_packet[Dot1Q].prio == 2   # 优先级保持不变
                assert anonymized_packet[TCP].sport in [80, 8080]  # 端口保持不变
                
                # 验证IP被正确匿名化
                anon_src = anonymized_packet[IP].src
                anon_dst = anonymized_packet[IP].dst
                
                # 验证原始IP存在于映射中并且匿名化正确
                assert orig_src in mapping, f"原始源IP {orig_src} 不在映射中"
                assert orig_dst in mapping, f"原始目标IP {orig_dst} 不在映射中"
                assert anon_src == mapping[orig_src]
                assert anon_dst == mapping[orig_dst]
                assert anon_src != orig_src  # 确保IP被改变
                assert anon_dst != orig_dst
    
    def test_mixed_encapsulation_processing(self):
        """测试混合封装类型处理"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建混合测试数据
            test_file = os.path.join(temp_dir, "test_mixed_encap.pcap")
            packets = [
                # 普通IP包
                Ether() / IP(src="10.1.1.1", dst="10.1.1.2") / TCP(),
                # VLAN包  
                Ether() / Dot1Q(vlan=200) / IP(src="172.20.1.1", dst="172.20.1.2") / TCP(),
                # 另一个普通包，相同网段
                Ether() / IP(src="10.1.1.3", dst="10.1.1.4") / TCP(),
            ]
            wrpcap(test_file, packets)
            
            # 创建映射
            files_to_process = ["test_mixed_encap.pcap"]
            error_log = []
            
            mapping = self.strategy.create_mapping(files_to_process, temp_dir, error_log)
            
            # 验证映射包含所有IP
            expected_ips = {"10.1.1.1", "10.1.1.2", "172.20.1.1", "172.20.1.2", "10.1.1.3", "10.1.1.4"}
            assert all(ip in mapping for ip in expected_ips)
            
            # 验证网段一致性（相同网段的IP应该映射到相同的新网段）
            mapped_10_1_1_1 = mapping["10.1.1.1"]
            mapped_10_1_1_3 = mapping["10.1.1.3"]
            
            # 检查A.B段一致性
            assert mapped_10_1_1_1.split('.')[0] == mapped_10_1_1_3.split('.')[0]  # A段相同
            assert mapped_10_1_1_1.split('.')[1] == mapped_10_1_1_3.split('.')[1]  # B段相同
            
            # 验证封装统计
            stats = self.strategy._encap_stats
            assert stats['total_packets_scanned'] == 3
            assert stats['plain_packets'] >= 2
            assert stats['encapsulated_packets'] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 