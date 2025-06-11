#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
第三阶段测试：载荷裁切增强功能测试

测试增强版智能裁切功能，验证多层封装的载荷处理能力：
- 封装内TCP会话识别
- 内层载荷裁切处理
- TLS智能裁切算法的兼容性
- 性能和统计功能
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from scapy.all import Ether, IP, TCP, Raw, Dot1Q, wrpcap

from src.pktmask.steps.trimming import (
    IntelligentTrimmingStep,
    get_tcp_session_key_enhanced,
    get_tcp_session_key,
    _process_pcap_data_enhanced,
    _process_pcap_data,
    find_tls_signaling_ranges,
    trim_packet_payload
)
from src.pktmask.core.encapsulation.adapter import ProcessingAdapter
from src.pktmask.core.encapsulation.types import EncapsulationType


class TestEnhancedPayloadTrimming(unittest.TestCase):
    """测试增强版载荷裁切功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.adapter = ProcessingAdapter()
        self.trimming_step = IntelligentTrimmingStep()
        
    def tearDown(self):
        """清理测试环境"""
        self.adapter.reset_stats()

    def test_enhanced_tcp_session_key_plain_packet(self):
        """测试增强版TCP会话键提取 - 普通数据包"""
        # 创建普通TCP数据包
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080)
        
        # 测试增强版会话键提取
        session_key, direction = get_tcp_session_key_enhanced(packet, self.adapter)
        
        # 验证结果
        self.assertIsNotNone(session_key)
        self.assertIn(direction, ["forward", "reverse"])
        self.assertEqual(len(session_key), 4)  # (src_ip, src_port, dst_ip, dst_port)
        
        # 验证与原有逻辑的一致性
        original_key, original_dir = get_tcp_session_key(packet)
        self.assertEqual(session_key, original_key)
        self.assertEqual(direction, original_dir)

    def test_enhanced_tcp_session_key_vlan_packet(self):
        """测试增强版TCP会话键提取 - VLAN封装数据包"""
        # 创建VLAN封装TCP数据包
        packet = (Ether() / 
                 Dot1Q(vlan=100) / 
                 IP(src="10.1.1.1", dst="10.1.1.2") / 
                 TCP(sport=443, dport=9443) / 
                 Raw(b"test payload"))
        
        # 测试增强版会话键提取
        session_key, direction = get_tcp_session_key_enhanced(packet, self.adapter)
        
        # 验证结果
        self.assertIsNotNone(session_key)
        self.assertIn(direction, ["forward", "reverse"])
        
        # 验证IP地址是内层IP
        self.assertIn("10.1.1.1", str(session_key))
        self.assertIn("10.1.1.2", str(session_key))
        
        # 验证端口号
        self.assertIn(443, session_key)
        self.assertIn(9443, session_key)

    def test_enhanced_tcp_session_key_fallback(self):
        """测试增强版TCP会话键提取的回退机制"""
        # 创建无TCP层的数据包
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2")
        
        # 测试增强版会话键提取
        session_key, direction = get_tcp_session_key_enhanced(packet, self.adapter)
        
        # 验证回退结果
        self.assertIsNone(session_key)
        self.assertIsNone(direction)

    def test_enhanced_tcp_session_key_without_adapter(self):
        """测试增强版TCP会话键提取 - 无适配器时的回退"""
        packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080)
        
        # 不提供适配器
        session_key, direction = get_tcp_session_key_enhanced(packet, None)
        
        # 验证回退到原有逻辑
        original_key, original_dir = get_tcp_session_key(packet)
        self.assertEqual(session_key, original_key)
        self.assertEqual(direction, original_dir)

    def test_process_pcap_data_enhanced_plain_packets(self):
        """测试增强版数据处理 - 普通数据包"""
        # 创建测试数据包
        packets = [
            Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080, seq=1000) / Raw(b"HTTP/1.1 200 OK"),
            Ether() / IP(src="192.168.1.2", dst="192.168.1.1") / TCP(sport=8080, dport=80, seq=2000) / Raw(b"GET / HTTP/1.1"),
        ]
        
        # 使用增强版处理
        result_packets, total, trimmed, errors = _process_pcap_data_enhanced(packets, self.adapter)
        
        # 验证基本结果
        self.assertEqual(total, 2)
        self.assertEqual(len(result_packets), 2)
        self.assertIsInstance(errors, list)
        
        # 验证统计信息
        stats = self.adapter.get_processing_stats()
        self.assertEqual(stats['total_packets'], 2)
        self.assertEqual(stats['encapsulated_packets'], 0)  # 普通包无封装

    def test_process_pcap_data_enhanced_vlan_packets(self):
        """测试增强版数据处理 - VLAN封装数据包"""
        # 创建新的适配器实例避免状态干扰
        test_adapter = ProcessingAdapter()
        
        # 创建VLAN封装测试数据包
        packets = [
            Ether() / Dot1Q(vlan=100) / IP(src="10.1.1.1", dst="10.1.1.2") / TCP(sport=443, dport=9443, seq=1000) / Raw(b"TLS data"),
            Ether() / Dot1Q(vlan=100) / IP(src="10.1.1.2", dst="10.1.1.1") / TCP(sport=9443, dport=443, seq=2000) / Raw(b"TLS response"),
        ]
        
        # 使用增强版处理
        result_packets, total, trimmed, errors = _process_pcap_data_enhanced(packets, test_adapter)
        
        # 验证基本结果
        self.assertEqual(total, 2)
        self.assertEqual(len(result_packets), 2)
        
        # 验证封装统计
        stats = test_adapter.get_processing_stats()
        self.assertEqual(stats['total_packets'], 2)
        self.assertEqual(stats['encapsulated_packets'], 2)  # VLAN封装包
        self.assertGreater(stats['encapsulation_ratio'], 0)

    def test_process_pcap_data_enhanced_mixed_packets(self):
        """测试增强版数据处理 - 混合数据包"""
        # 创建新的适配器实例避免状态干扰
        test_adapter = ProcessingAdapter()
        
        # 创建混合测试数据包（普通 + VLAN）
        packets = [
            Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080, seq=1000) / Raw(b"plain TCP"),
            Ether() / Dot1Q(vlan=200) / IP(src="10.2.2.1", dst="10.2.2.2") / TCP(sport=443, dport=9443, seq=2000) / Raw(b"VLAN TCP"),
        ]
        
        # 使用增强版处理
        result_packets, total, trimmed, errors = _process_pcap_data_enhanced(packets, test_adapter)
        
        # 验证结果
        self.assertEqual(total, 2)
        self.assertEqual(len(result_packets), 2)
        
        # 验证混合统计
        stats = test_adapter.get_processing_stats()
        self.assertEqual(stats['total_packets'], 2)
        self.assertEqual(stats['encapsulated_packets'], 1)  # 只有一个VLAN包
        self.assertEqual(stats['encapsulation_ratio'], 0.5)

    def test_process_pcap_data_enhanced_without_adapter(self):
        """测试增强版数据处理 - 无适配器时的回退"""
        packets = [
            Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080, seq=1000) / Raw(b"test"),
        ]
        
        # 不提供适配器
        result_packets, total, trimmed, errors = _process_pcap_data_enhanced(packets, None)
        
        # 验证回退到原有逻辑
        original_result = _process_pcap_data(packets)
        self.assertEqual(len(result_packets), len(original_result[0]))
        self.assertEqual(total, original_result[1])

    def test_trimming_step_initialization(self):
        """测试裁切步骤的初始化"""
        step = IntelligentTrimmingStep()
        
        # 验证初始化
        self.assertEqual(step.name, "Intelligent Trim")
        self.assertIsNotNone(step._encap_adapter)
        self.assertIsInstance(step._encap_adapter, ProcessingAdapter)

    def test_trimming_step_process_file_with_encapsulation(self):
        """测试处理文件功能 - 包含封装数据包"""
        # 创建临时测试文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_input:
            input_path = tmp_input.name
        
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_output:
            output_path = tmp_output.name
        
        try:
            # 创建测试数据包并写入文件
            test_packets = [
                Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080, seq=1000) / Raw(b"plain"),
                Ether() / Dot1Q(vlan=100) / IP(src="10.1.1.1", dst="10.1.1.2") / TCP(sport=443, dport=9443, seq=2000) / Raw(b"vlan"),
            ]
            wrpcap(input_path, test_packets)
            
            # 处理文件
            step = IntelligentTrimmingStep()
            summary = step.process_file(input_path, output_path)
            
            # 验证处理结果
            self.assertIsNotNone(summary)
            self.assertEqual(summary['total_packets'], 2)
            self.assertIn('encapsulated_packets', summary)
            self.assertIn('encapsulation_ratio', summary)
            self.assertIn('trim_rate', summary)
            
            # 验证输出文件存在
            self.assertTrue(os.path.exists(output_path))
            
        finally:
            # 清理临时文件
            if os.path.exists(input_path):
                os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_tls_signaling_detection_compatibility(self):
        """测试TLS信令检测的兼容性"""
        # 创建模拟TLS载荷 - 确保数据长度与头部声明一致
        tls_handshake_data = b'0123456789abcdef'  # 16字节，匹配长度字段\x00\x10
        tls_handshake = b'\x16\x03\x03\x00\x10' + tls_handshake_data  # TLS Handshake
        tls_app_data_data = b'application_data_32bytes_total!!!'  # 32字节，匹配长度字段\x00\x20  
        tls_app_data = b'\x17\x03\x03\x00\x20' + tls_app_data_data  # TLS Application Data
        
        combined_payload = tls_handshake + tls_app_data
        
        # 测试TLS信令范围检测
        ranges = find_tls_signaling_ranges(combined_payload)
        
        # 验证检测结果
        self.assertEqual(len(ranges), 1)  # 只有handshake是信令
        self.assertEqual(ranges[0], (0, len(tls_handshake)))

    def test_trim_packet_payload_functionality(self):
        """测试数据包载荷裁切功能"""
        # 创建带载荷的TCP数据包
        original_packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080) / Raw(b"payload to trim")
        
        # 裁切载荷
        trimmed_packet = trim_packet_payload(original_packet.copy())
        
        # 验证裁切结果
        self.assertTrue(original_packet.haslayer(Raw))  # 原包有载荷
        self.assertFalse(trimmed_packet.haslayer(Raw))  # 裁切后无载荷
        self.assertTrue(trimmed_packet.haslayer(TCP))   # TCP层保留

    def test_encapsulation_statistics_collection(self):
        """测试封装统计信息收集"""
        # 创建混合数据包
        packets = [
            Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080),  # 普通包
            Ether() / Dot1Q(vlan=100) / IP(src="10.1.1.1", dst="10.1.1.2") / TCP(sport=443, dport=9443),  # VLAN包
            Ether() / Dot1Q(vlan=200) / IP(src="10.2.2.1", dst="10.2.2.2") / TCP(sport=22, dport=2222),   # VLAN包
        ]
        
        # 重置统计
        self.adapter.reset_stats()
        
        # 处理数据包
        _process_pcap_data_enhanced(packets, self.adapter)
        
        # 获取统计信息
        stats = self.adapter.get_processing_stats()
        
        # 验证统计结果
        self.assertEqual(stats['total_packets'], 3)
        self.assertEqual(stats['encapsulated_packets'], 2)  # 2个VLAN包
        self.assertAlmostEqual(stats['encapsulation_ratio'], 2/3, places=2)
        self.assertIn('vlan', stats['encapsulation_distribution'])

    def test_error_handling_and_fallback(self):
        """测试错误处理和回退机制"""
        # 创建可能导致错误的数据包
        invalid_packet = Ether() / Raw(b"invalid packet structure")
        normal_packet = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080)
        
        packets = [invalid_packet, normal_packet]
        
        # 处理数据包（应该优雅处理错误）
        result_packets, total, trimmed, errors = _process_pcap_data_enhanced(packets, self.adapter)
        
        # 验证错误处理
        self.assertEqual(total, 2)
        self.assertEqual(len(result_packets), 2)  # 所有包都应该被处理
        # 可能有错误，但不应该导致崩溃

    def test_tcp_session_consistency(self):
        """测试TCP会话一致性"""
        # 创建同一会话的多个数据包
        base_packet = Ether() / Dot1Q(vlan=100) / IP(src="10.1.1.1", dst="10.1.1.2") / TCP(sport=443, dport=9443)
        
        packets = [
            base_packet / Raw(b"packet1"),
            base_packet / Raw(b"packet2"),
            base_packet / Raw(b"packet3")
        ]
        
        # 提取会话键
        session_keys = []
        for packet in packets:
            key, direction = get_tcp_session_key_enhanced(packet, self.adapter)
            session_keys.append((key, direction))
        
        # 验证会话键一致性
        first_key, first_dir = session_keys[0]
        for key, direction in session_keys[1:]:
            self.assertEqual(key, first_key)
            self.assertEqual(direction, first_dir)

    def test_performance_logging_integration(self):
        """测试性能日志集成"""
        # 创建测试数据包
        packets = [
            Ether() / Dot1Q(vlan=100) / IP(src="10.1.1.1", dst="10.1.1.2") / TCP(sport=443, dport=9443) / Raw(b"test"),
        ]
        
        # 创建临时文件进行完整测试
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_input:
            input_path = tmp_input.name
        
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_output:
            output_path = tmp_output.name
        
        try:
            wrpcap(input_path, packets)
            
            # 模拟性能日志记录
            with patch('src.pktmask.infrastructure.logging.log_performance') as mock_log:
                step = IntelligentTrimmingStep()
                summary = step.process_file(input_path, output_path)
                
                # 验证性能日志被调用
                mock_log.assert_called_once()
                call_args = mock_log.call_args
                
                # 验证日志参数
                self.assertEqual(call_args[0][0], 'enhanced_trimming_process_file')
                self.assertIn('encapsulated_packets', call_args[1])
                self.assertIn('encapsulation_ratio', call_args[1])
                
        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)


if __name__ == '__main__':
    unittest.main() 