#!/usr/bin/env python3
"""
Core Strategy模块全面测试 - Phase 2核心改进
专注于提升Strategy层的测试覆盖率从29%到65%
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from scapy.all import IP, IPv6, TCP, Ether, wrpcap

from src.pktmask.core.strategy import (
    AnonymizationStrategy, HierarchicalAnonymizationStrategy,
    ip_sort_key, _safe_hash, _generate_unique_segment,
    _generate_new_ipv4_address_hierarchical, _generate_new_ipv6_address_hierarchical,
    _generate_unique_ipv6_segment
)
from src.pktmask.common.constants import ProcessingConstants


class TestAnonymizationStrategyAbstract:
    """测试匿名化策略抽象基类"""
    
    def test_strategy_is_abstract(self):
        """测试策略基类是抽象的"""
        with pytest.raises(TypeError):
            AnonymizationStrategy()
    
    def test_abstract_methods_exist(self):
        """测试抽象方法存在"""
        abstract_methods = AnonymizationStrategy.__abstractmethods__
        expected_methods = {
            'create_mapping', 'reset', 'build_mapping_from_directory',
            'anonymize_packet', 'get_ip_map'
        }
        assert expected_methods.issubset(abstract_methods)


class TestUtilityFunctions:
    """测试工具函数"""
    
    def test_ip_sort_key_ipv4(self):
        """测试IPv4排序键生成"""
        ipv4_1 = "192.168.1.1"
        ipv4_2 = "10.0.0.1"
        
        key1 = ip_sort_key(ipv4_1)
        key2 = ip_sort_key(ipv4_2)
        
        assert key1[0] == ProcessingConstants.IPV4_SORT_WEIGHT
        assert key2[0] == ProcessingConstants.IPV4_SORT_WEIGHT
        assert len(key1) == 5  # weight + 4 octets
        assert len(key2) == 5
        
        # 验证排序逻辑：10.0.0.1 < 192.168.1.1
        assert key2 < key1
    
    def test_ip_sort_key_ipv6(self):
        """测试IPv6排序键生成"""
        ipv6 = "2001:db8::1"
        key = ip_sort_key(ipv6)
        
        assert key[0] == ProcessingConstants.IPV6_SORT_WEIGHT
        assert len(key) > 1
    
    def test_ip_sort_key_invalid(self):
        """测试无效IP排序键"""
        invalid_ip = "invalid.ip"
        key = ip_sort_key(invalid_ip)
        
        assert key[0] == ProcessingConstants.UNKNOWN_IP_SORT_WEIGHT
    
    def test_safe_hash_deterministic(self):
        """测试安全哈希函数的确定性"""
        test_string = "test_input"
        
        hash1 = _safe_hash(test_string)
        hash2 = _safe_hash(test_string)
        
        assert hash1 == hash2
        assert isinstance(hash1, int)
        assert hash1 > 0
    
    def test_safe_hash_different_inputs(self):
        """测试不同输入产生不同哈希"""
        hash1 = _safe_hash("input1")
        hash2 = _safe_hash("input2")
        
        assert hash1 != hash2
    
    def test_generate_unique_segment_basic(self):
        """测试唯一段生成基本功能"""
        used_values = set()
        original_seg = "100"
        seed_base = "test_seed"
        
        result = _generate_unique_segment(original_seg, seed_base, used_values)
        
        assert isinstance(result, str)
        assert result.isdigit()
        assert int(result) >= ProcessingConstants.IPV4_MIN_SEGMENT
        assert int(result) <= ProcessingConstants.IPV4_MAX_SEGMENT
        assert result != original_seg
        assert result in used_values
    
    def test_generate_unique_segment_avoids_conflicts(self):
        """测试唯一段生成避免冲突"""
        used_values = {"50", "51", "52"}
        original_used_values = used_values.copy()  # 保存调用前的状态
        original_seg = "100"
        seed_base = "test_seed"
        
        result = _generate_unique_segment(original_seg, seed_base, used_values)
        
        assert result not in original_used_values  # 应该在调用前不存在
        assert result != original_seg
        assert result in used_values  # 函数会将结果添加到used_values中
    
    def test_generate_unique_segment_invalid_input(self):
        """测试无效输入处理"""
        used_values = set()
        
        with pytest.raises(ValueError):
            _generate_unique_segment("invalid", "seed", used_values)
        
        with pytest.raises(ValueError):
            _generate_unique_segment("999", "seed", used_values)  # 超出范围
    
    def test_generate_unique_ipv6_segment_basic(self):
        """测试IPv6段生成"""
        original_seg = "2001"
        seed_base = "test_seed"
        
        result = _generate_unique_ipv6_segment(original_seg, seed_base)
        
        assert isinstance(result, str)
        assert len(result) <= 4  # IPv6段最多4个字符
        # 验证是有效的十六进制
        try:
            int(result, 16)
        except ValueError:
            pytest.fail("Generated IPv6 segment is not valid hex")


class TestIPv4AddressGeneration:
    """测试IPv4地址生成功能"""
    
    def test_generate_new_ipv4_address_hierarchical_basic(self):
        """测试基本IPv4地址生成"""
        original_ip = "192.168.1.1"
        
        # 创建频率字典
        freq1 = {"192": 3}  # 高频A段
        freq2 = {"192.168": 2}  # 高频A.B段
        freq3 = {"192.168.1": 1}  # 低频A.B.C段
        
        # 创建映射字典
        ipv4_first_map = {}
        ipv4_second_map = {}
        ipv4_third_map = {}
        maps = (ipv4_first_map, ipv4_second_map, ipv4_third_map)
        
        # 创建已使用段集合
        used_a = set()
        used_ab = set()
        used_abc = set()
        used_segments = (used_a, used_ab, used_abc)
        
        result = _generate_new_ipv4_address_hierarchical(
            original_ip, freq1, freq2, freq3, maps, used_segments
        )
        
        assert isinstance(result, str)
        parts = result.split('.')
        assert len(parts) == 4
        
        # 验证每个部分都是有效的数字
        for part in parts:
            assert part.isdigit()
            assert 0 <= int(part) <= 255
        
        # 验证结果与原始不同
        assert result != original_ip
    
    def test_generate_new_ipv4_address_high_frequency_consistency(self):
        """测试高频段的一致性映射"""
        original_ip1 = "192.168.1.1"
        original_ip2 = "192.168.1.2"
        
        # 设置高频A段
        freq1 = {"192": 5}
        freq2 = {"192.168": 3}
        freq3 = {}
        
        # 共享映射字典
        ipv4_first_map = {}
        ipv4_second_map = {}
        ipv4_third_map = {}
        maps = (ipv4_first_map, ipv4_second_map, ipv4_third_map)
        
        used_a = set()
        used_ab = set()
        used_abc = set()
        used_segments = (used_a, used_ab, used_abc)
        
        result1 = _generate_new_ipv4_address_hierarchical(
            original_ip1, freq1, freq2, freq3, maps, used_segments
        )
        
        result2 = _generate_new_ipv4_address_hierarchical(
            original_ip2, freq1, freq2, freq3, maps, used_segments
        )
        
        # 验证相同的高频A.B段映射到相同的新A.B段
        result1_parts = result1.split('.')
        result2_parts = result2.split('.')
        
        assert result1_parts[0] == result2_parts[0]  # 相同A段
        assert result1_parts[1] == result2_parts[1]  # 相同B段
    
    def test_generate_new_ipv4_address_invalid_input(self):
        """测试无效IPv4输入处理"""
        freq1, freq2, freq3 = {}, {}, {}
        maps = ({}, {}, {})
        used_segments = (set(), set(), set())
        
        # 无效格式应该返回原值
        result = _generate_new_ipv4_address_hierarchical(
            "invalid.ip", freq1, freq2, freq3, maps, used_segments
        )
        assert result == "invalid.ip"
        
        # 非字符串输入
        result = _generate_new_ipv4_address_hierarchical(
            None, freq1, freq2, freq3, maps, used_segments
        )
        assert result is None


class TestIPv6AddressGeneration:
    """测试IPv6地址生成功能"""
    
    def test_generate_new_ipv6_address_hierarchical_basic(self):
        """测试基本IPv6地址生成"""
        original_ip = "2001:db8::1"
        
        # 创建正确的频率字典和映射（IPv6需要7个频率字典）
        freqs = ({}, {}, {}, {}, {}, {}, {})  # 7个频率字典
        maps = ({}, {}, {}, {}, {}, {}, {})   # 7个映射字典
        
        result = _generate_new_ipv6_address_hierarchical(original_ip, freqs, maps)
        
        assert isinstance(result, str)
        assert ":" in result  # 基本IPv6格式检查


class TestHierarchicalAnonymizationStrategy:
    """测试分层匿名化策略"""
    
    def test_strategy_initialization(self):
        """测试策略初始化"""
        strategy = HierarchicalAnonymizationStrategy()
        
        assert hasattr(strategy, 'reset')
        assert hasattr(strategy, 'get_ip_map')
        assert hasattr(strategy, 'create_mapping')
        assert hasattr(strategy, 'build_mapping_from_directory')
        assert hasattr(strategy, 'anonymize_packet')
    
    def test_strategy_reset(self):
        """测试策略重置"""
        strategy = HierarchicalAnonymizationStrategy()
        
        # 设置一些状态
        strategy._ip_map = {"192.168.1.1": "10.0.0.1"}
        
        strategy.reset()
        
        # 验证状态被重置
        assert len(strategy.get_ip_map()) == 0
    
    def test_get_ip_map_empty(self):
        """测试获取空IP映射"""
        strategy = HierarchicalAnonymizationStrategy()
        ip_map = strategy.get_ip_map()
        
        assert isinstance(ip_map, dict)
        assert len(ip_map) == 0
    
    def test_prescan_addresses_with_files(self, temp_test_dir):
        """测试预扫描地址功能"""
        strategy = HierarchicalAnonymizationStrategy()
        
        # 创建测试数据包
        packets = [
            Ether()/IP(src="192.168.1.1", dst="192.168.1.2")/TCP(),
            Ether()/IP(src="192.168.1.1", dst="10.0.0.1")/TCP(),
            Ether()/IP(src="10.0.0.2", dst="192.168.1.3")/TCP(),
        ]
        
        test_file = os.path.join(temp_test_dir, "test.pcap")
        wrpcap(test_file, packets)
        
        error_log = []
        result = strategy._prescan_addresses([test_file], temp_test_dir, error_log)
        
        assert len(result) == 3  # 返回3个元素的元组
        freqs_ipv4, freqs_ipv6, unique_ips = result
        
        # 验证发现的IP地址
        expected_ips = {"192.168.1.1", "192.168.1.2", "10.0.0.1", "10.0.0.2", "192.168.1.3"}
        assert expected_ips.issubset(unique_ips)
        
        # 验证频率统计 - freqs_ipv4包含3个频率字典
        ipv4_first_freq, ipv4_second_freq, ipv4_third_freq = freqs_ipv4
        assert "192" in ipv4_first_freq
        assert ipv4_first_freq["192"] >= 3  # 至少3个192.x.x.x地址
        assert "10" in ipv4_first_freq
        
        assert len(error_log) == 0
    
    def test_create_mapping_basic(self, temp_test_dir):
        """测试创建基本映射"""
        strategy = HierarchicalAnonymizationStrategy()
        
        # 创建简单的测试数据包
        packets = [
            Ether()/IP(src="192.168.1.1", dst="192.168.1.2")/TCP(),
        ]
        
        test_file = os.path.join(temp_test_dir, "test.pcap")
        wrpcap(test_file, packets)
        
        error_log = []
        ip_mapping = strategy.create_mapping([test_file], temp_test_dir, error_log)
        
        assert isinstance(ip_mapping, dict)
        assert "192.168.1.1" in ip_mapping
        assert "192.168.1.2" in ip_mapping
        
        # 验证映射的IP是有效的
        for original, anonymized in ip_mapping.items():
            assert original != anonymized
            assert isinstance(anonymized, str)
        
        assert len(error_log) == 0
    
    def test_build_mapping_from_directory(self, temp_test_dir):
        """测试从目录构建映射"""
        strategy = HierarchicalAnonymizationStrategy()
        
        # 创建多个测试文件
        packets1 = [Ether()/IP(src="192.168.1.1", dst="10.0.0.1")/TCP()]
        packets2 = [Ether()/IP(src="172.16.1.1", dst="192.168.1.1")/TCP()]
        
        file1 = os.path.join(temp_test_dir, "test1.pcap")
        file2 = os.path.join(temp_test_dir, "test2.pcap")
        wrpcap(file1, packets1)
        wrpcap(file2, packets2)
        
        strategy.build_mapping_from_directory([file1, file2])
        
        ip_map = strategy.get_ip_map()
        
        # 验证所有IP都被映射
        expected_ips = {"192.168.1.1", "10.0.0.1", "172.16.1.1"}
        for ip in expected_ips:
            assert ip in ip_map
    
    def test_anonymize_packet_ipv4(self):
        """测试IPv4包匿名化"""
        strategy = HierarchicalAnonymizationStrategy()
        
        # 手动设置映射
        strategy._ip_map = {
            "192.168.1.1": "10.0.0.100",
            "192.168.1.2": "10.0.0.101"
        }
        
        # 创建测试包
        packet = Ether()/IP(src="192.168.1.1", dst="192.168.1.2")/TCP()
        
        anonymized_packet, was_modified = strategy.anonymize_packet(packet)
        
        assert was_modified is True
        assert anonymized_packet[IP].src == "10.0.0.100"
        assert anonymized_packet[IP].dst == "10.0.0.101"
    
    def test_anonymize_packet_no_mapping(self):
        """测试没有映射的包匿名化"""
        strategy = HierarchicalAnonymizationStrategy()
        
        # 空映射
        strategy._ip_map = {}
        
        packet = Ether()/IP(src="192.168.1.1", dst="192.168.1.2")/TCP()
        
        anonymized_packet, was_modified = strategy.anonymize_packet(packet)
        
        assert was_modified is False
        assert anonymized_packet[IP].src == "192.168.1.1"  # 保持原样
        assert anonymized_packet[IP].dst == "192.168.1.2"
    
    def test_anonymize_packet_non_ip(self):
        """测试非IP包的处理"""
        strategy = HierarchicalAnonymizationStrategy()
        
        # 非IP包
        packet = Ether()/TCP()
        
        anonymized_packet, was_modified = strategy.anonymize_packet(packet)
        
        assert was_modified is False
        assert anonymized_packet == packet


class TestStrategyIntegration:
    """策略模块集成测试"""
    
    def test_strategy_complete_workflow(self, temp_test_dir):
        """测试策略完整工作流程"""
        strategy = HierarchicalAnonymizationStrategy()
        
        # 创建测试数据
        packets = [
            Ether()/IP(src="192.168.1.1", dst="192.168.1.2")/TCP(),
            Ether()/IP(src="10.0.0.1", dst="192.168.1.1")/TCP(),
            Ether()/IP(src="192.168.1.3", dst="10.0.0.2")/TCP(),
        ]
        
        test_file = os.path.join(temp_test_dir, "test.pcap")
        wrpcap(test_file, packets)
        
        # 1. 创建映射
        error_log = []
        ip_mapping = strategy.create_mapping([test_file], temp_test_dir, error_log)
        
        assert len(ip_mapping) >= 4  # 至少4个不同的IP
        assert len(error_log) == 0
        
        # 2. 验证映射一致性
        original_ips = set(ip_mapping.keys())
        anonymized_ips = set(ip_mapping.values())
        
        # 原始IP和匿名IP应该没有重叠
        assert len(original_ips.intersection(anonymized_ips)) == 0
        
        # 3. 匿名化包
        anonymized_packets = []
        for packet in packets:
            anon_packet, modified = strategy.anonymize_packet(packet)
            anonymized_packets.append((anon_packet, modified))
        
        # 验证所有IP包都被修改
        ip_packets_modified = [modified for anon_packet, modified in anonymized_packets if anon_packet.haslayer(IP)]
        assert all(ip_packets_modified)


@pytest.fixture
def temp_test_dir():
    """创建临时测试目录"""
    with tempfile.TemporaryDirectory(prefix="pktmask_strategy_test_") as temp_dir:
        yield temp_dir 