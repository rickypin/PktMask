"""
多层封装处理基础测试

测试第一阶段开发的核心组件基本功能：
- 封装检测引擎
- 协议栈解析器
- 处理适配器
"""

import pytest
from unittest.mock import Mock, patch
from scapy.packet import Packet
from scapy.layers.inet import IP, TCP
from scapy.layers.l2 import Ether, Dot1Q

# 测试imports
try:
    from src.pktmask.core.encapsulation import (
        EncapsulationType, 
        EncapsulationDetector,
        ProtocolStackParser,
        ProcessingAdapter
    )
except ImportError:
    # 如果导入失败，跳过测试
    pytest.skip("封装模块未找到，跳过测试", allow_module_level=True)


class TestEncapsulationTypes:
    """测试封装类型定义"""
    
    def test_encapsulation_type_enum(self):
        """测试封装类型枚举"""
        assert EncapsulationType.PLAIN.value == "plain"
        assert EncapsulationType.VLAN.value == "vlan"
        assert EncapsulationType.DOUBLE_VLAN.value == "double_vlan"
        assert EncapsulationType.MPLS.value == "mpls"
        assert EncapsulationType.VXLAN.value == "vxlan"
        assert EncapsulationType.GRE.value == "gre"
        assert EncapsulationType.COMPOSITE.value == "composite"
        assert EncapsulationType.UNKNOWN.value == "unknown"


class TestEncapsulationDetector:
    """测试封装检测引擎"""
    
    def setup_method(self):
        """测试初始化"""
        self.detector = EncapsulationDetector()
    
    def test_detector_initialization(self):
        """测试检测器初始化"""
        assert self.detector is not None
        assert hasattr(self.detector, '_detection_patterns')
        assert hasattr(self.detector, '_detection_cache')
    
    def test_detect_plain_packet(self):
        """测试检测无封装数据包"""
        # 创建简单的IP包
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        
        encap_type = self.detector.detect_encapsulation_type(packet)
        assert encap_type == EncapsulationType.PLAIN
    
    def test_detect_vlan_packet(self):
        """测试检测VLAN封装数据包"""
        # 创建VLAN包
        packet = Ether() / Dot1Q(vlan=100) / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        
        encap_type = self.detector.detect_encapsulation_type(packet)
        assert encap_type == EncapsulationType.VLAN
    
    def test_is_encapsulated(self):
        """测试封装检查功能"""
        # 无封装包
        plain_packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        assert not self.detector.is_encapsulated(plain_packet)
        
        # VLAN封装包
        vlan_packet = Ether() / Dot1Q(vlan=100) / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        assert self.detector.is_encapsulated(vlan_packet)
    
    def test_get_encapsulation_depth(self):
        """测试封装深度计算"""
        # 无封装包
        plain_packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        depth = self.detector.get_encapsulation_depth(plain_packet)
        assert depth >= 0
        
        # VLAN封装包
        vlan_packet = Ether() / Dot1Q(vlan=100) / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        vlan_depth = self.detector.get_encapsulation_depth(vlan_packet)
        assert vlan_depth > depth
    
    def test_get_supported_encapsulations(self):
        """测试获取支持的封装类型"""
        supported = self.detector.get_supported_encapsulations()
        assert isinstance(supported, list)
        assert len(supported) > 0
        assert EncapsulationType.PLAIN in supported
        assert EncapsulationType.VLAN in supported
    
    def test_cache_functionality(self):
        """测试缓存功能"""
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        
        # 清除缓存
        self.detector.clear_cache()
        stats_before = self.detector.get_cache_stats()
        assert stats_before['cache_size'] == 0
        
        # 检测数据包（应该缓存结果）
        self.detector.detect_encapsulation_type(packet)
        stats_after = self.detector.get_cache_stats()
        
        # 验证缓存统计
        assert stats_after['cache_size'] >= 0
        assert 'cache_max_size' in stats_after


class TestProtocolStackParser:
    """测试协议栈解析器"""
    
    def setup_method(self):
        """测试初始化"""
        self.parser = ProtocolStackParser()
    
    def test_parser_initialization(self):
        """测试解析器初始化"""
        assert self.parser is not None
        assert hasattr(self.parser, 'detector')
        assert hasattr(self.parser, '_layer_parsers')
    
    def test_parse_plain_packet_layers(self):
        """测试解析无封装数据包层"""
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080)
        
        result = self.parser.parse_packet_layers(packet)
        
        assert result is not None
        assert result.parsing_success
        assert result.encap_type == EncapsulationType.PLAIN
        assert len(result.layers) > 0
        assert len(result.ip_layers) > 0
        
        # 检查IP层信息
        ip_layer = result.ip_layers[0]
        assert ip_layer.src_ip == "192.168.1.1"
        assert ip_layer.dst_ip == "192.168.1.2"
        assert ip_layer.ip_version == 4
    
    def test_parse_vlan_packet_layers(self):
        """测试解析VLAN数据包层"""
        packet = Ether() / Dot1Q(vlan=100) / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        
        result = self.parser.parse_packet_layers(packet)
        
        assert result is not None
        assert result.parsing_success
        assert result.encap_type == EncapsulationType.VLAN
        assert result.has_vlan()
        assert len(result.vlan_info) > 0
        
        # 检查VLAN信息
        vlan = result.vlan_info[0]
        assert vlan.vlan_id == 100
    
    def test_extract_all_ip_addresses(self):
        """测试提取所有IP地址"""
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        
        ip_layers = self.parser.extract_all_ip_addresses(packet)
        
        assert len(ip_layers) >= 1
        assert ip_layers[0].src_ip == "192.168.1.1"
        assert ip_layers[0].dst_ip == "192.168.1.2"
    
    def test_find_innermost_payload(self):
        """测试查找最内层载荷"""
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080) / b"HTTP payload"
        
        payload = self.parser.find_innermost_payload(packet)
        
        if payload is not None:
            assert payload.protocol == "TCP"
            assert payload.src_port == 80
            assert payload.dst_port == 8080
            assert len(payload.payload_data) > 0


class TestProcessingAdapter:
    """测试处理适配器"""
    
    def setup_method(self):
        """测试初始化"""
        self.adapter = ProcessingAdapter()
    
    def test_adapter_initialization(self):
        """测试适配器初始化"""
        assert self.adapter is not None
        assert hasattr(self.adapter, 'detector')
        assert hasattr(self.adapter, 'parser')
        assert hasattr(self.adapter, 'stats')
    
    def test_analyze_packet_for_ip_processing(self):
        """测试IP处理分析"""
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        
        analysis = self.adapter.analyze_packet_for_ip_processing(packet)
        
        assert analysis is not None
        assert 'encap_type' in analysis
        assert 'has_encapsulation' in analysis
        assert 'ip_layers' in analysis
        assert 'total_ips' in analysis
        assert 'processing_hints' in analysis
    
    def test_analyze_packet_for_payload_processing(self):
        """测试载荷处理分析"""
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080) / b"payload"
        
        analysis = self.adapter.analyze_packet_for_payload_processing(packet)
        
        assert analysis is not None
        assert 'encap_type' in analysis
        assert 'has_encapsulation' in analysis
        assert 'innermost_payload' in analysis
        assert 'has_payload' in analysis
        assert 'transport_protocol' in analysis
    
    def test_extract_ips_for_anonymization(self):
        """测试IP地址提取用于匿名化"""
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        analysis = self.adapter.analyze_packet_for_ip_processing(packet)
        
        ip_pairs = self.adapter.extract_ips_for_anonymization(analysis)
        
        assert isinstance(ip_pairs, list)
        if len(ip_pairs) > 0:
            assert len(ip_pairs[0]) == 3  # (src_ip, dst_ip, context)
            assert ip_pairs[0][0] == "192.168.1.1"
            assert ip_pairs[0][1] == "192.168.1.2"
    
    def test_is_packet_encapsulated(self):
        """测试数据包封装检查"""
        # 无封装包
        plain_packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        assert not self.adapter.is_packet_encapsulated(plain_packet)
        
        # VLAN封装包
        vlan_packet = Ether() / Dot1Q(vlan=100) / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        assert self.adapter.is_packet_encapsulated(vlan_packet)
    
    def test_get_encapsulation_summary(self):
        """测试获取封装摘要"""
        packet = Ether() / Dot1Q(vlan=100) / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        
        summary = self.adapter.get_encapsulation_summary(packet)
        
        assert summary is not None
        assert 'encap_type' in summary
        assert 'has_encapsulation' in summary
        assert 'total_layers' in summary
        assert 'ip_count' in summary
        assert 'has_vlan' in summary
        assert 'parsing_success' in summary
    
    def test_get_processing_stats(self):
        """测试获取处理统计"""
        # 处理一些数据包
        packet1 = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        packet2 = Ether() / Dot1Q(vlan=100) / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        
        self.adapter.analyze_packet_for_ip_processing(packet1)
        self.adapter.analyze_packet_for_ip_processing(packet2)
        
        stats = self.adapter.get_processing_stats()
        
        assert stats is not None
        assert 'total_packets' in stats
        assert 'encapsulated_packets' in stats
        assert 'encapsulation_distribution' in stats
        assert 'processing_errors' in stats
        assert stats['total_packets'] >= 2
    
    def test_reset_stats(self):
        """测试重置统计"""
        # 处理一些数据包
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        self.adapter.analyze_packet_for_ip_processing(packet)
        
        # 重置统计
        self.adapter.reset_stats()
        
        stats = self.adapter.get_processing_stats()
        assert stats['total_packets'] == 0
        assert stats['encapsulated_packets'] == 0


# 集成测试
class TestEncapsulationIntegration:
    """测试封装处理集成功能"""
    
    def setup_method(self):
        """测试初始化"""
        self.detector = EncapsulationDetector()
        self.parser = ProtocolStackParser()
        self.adapter = ProcessingAdapter()
    
    def test_end_to_end_plain_packet(self):
        """测试端到端无封装数据包处理"""
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080) / b"payload"
        
        # 检测封装类型
        encap_type = self.detector.detect_encapsulation_type(packet)
        assert encap_type == EncapsulationType.PLAIN
        
        # 解析协议栈
        result = self.parser.parse_packet_layers(packet)
        assert result.parsing_success
        assert len(result.ip_layers) == 1
        
        # 适配器分析
        ip_analysis = self.adapter.analyze_packet_for_ip_processing(packet)
        payload_analysis = self.adapter.analyze_packet_for_payload_processing(packet)
        
        assert not ip_analysis['has_encapsulation']
        assert payload_analysis['has_payload']
    
    def test_end_to_end_vlan_packet(self):
        """测试端到端VLAN数据包处理"""
        packet = Ether() / Dot1Q(vlan=100, prio=3) / IP(src="10.0.1.1", dst="10.0.1.2") / TCP(sport=443, dport=9090)
        
        # 检测封装类型
        encap_type = self.detector.detect_encapsulation_type(packet)
        assert encap_type == EncapsulationType.VLAN
        
        # 解析协议栈
        result = self.parser.parse_packet_layers(packet)
        assert result.parsing_success
        assert result.has_vlan()
        assert len(result.vlan_info) == 1
        assert result.vlan_info[0].vlan_id == 100
        assert result.vlan_info[0].priority == 3
        
        # 适配器分析
        ip_analysis = self.adapter.analyze_packet_for_ip_processing(packet)
        assert ip_analysis['has_encapsulation']
        assert ip_analysis['total_ips'] == 1
        
        # 提取IP用于匿名化
        ip_pairs = self.adapter.extract_ips_for_anonymization(ip_analysis)
        assert len(ip_pairs) == 1
        assert ip_pairs[0][0] == "10.0.1.1"
        assert ip_pairs[0][1] == "10.0.1.2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 