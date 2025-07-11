#!/usr/bin/env python3
"""TLS流量分析器协议层级清理功能的单元测试"""

import unittest
from unittest.mock import Mock

from src.pktmask.tools.tls_flow_analyzer import TLSFlowAnalyzer


class TestTLSFlowAnalyzerProtocolCleanup(unittest.TestCase):
    """测试TLS流量分析器的协议层级清理功能"""

    def setUp(self):
        """设置测试环境"""
        self.analyzer = TLSFlowAnalyzer()

    def test_clean_protocol_layers_basic(self):
        """测试基本协议层级清理"""
        # 正常的协议层级
        protocols = ["eth", "ethertype", "ip", "tcp", "tls"]
        result = self.analyzer._clean_protocol_layers(protocols)
        self.assertEqual(result, protocols)

    def test_clean_protocol_layers_x509sat_dedup(self):
        """测试x509sat协议层去重"""
        # 包含大量重复x509sat的协议层级
        protocols = [
            "eth", "ethertype", "ip", "tcp", "tls",
            "x509sat", "x509sat", "x509sat", "x509sat", "x509sat",
            "x509sat", "x509sat", "x509sat", "x509sat", "x509sat"
        ]
        result = self.analyzer._clean_protocol_layers(protocols)
        expected = ["eth", "ethertype", "ip", "tcp", "tls", "x509sat"]
        self.assertEqual(result, expected)

    def test_clean_protocol_layers_mixed_dedup(self):
        """测试混合协议层去重"""
        protocols = [
            "eth", "ethertype", "ip", "tcp", "tls",
            "x509sat", "x509af", "x509sat", "pkcs1", "x509ce",
            "x509sat", "pkcs1", "x509af"
        ]
        result = self.analyzer._clean_protocol_layers(protocols)
        expected = ["eth", "ethertype", "ip", "tcp", "tls", "x509sat", "x509af", "pkcs1", "x509ce"]
        self.assertEqual(result, expected)

    def test_clean_protocol_layers_empty(self):
        """测试空协议层级"""
        result = self.analyzer._clean_protocol_layers([])
        self.assertEqual(result, [])

    def test_clean_protocol_layers_none(self):
        """测试None输入"""
        result = self.analyzer._clean_protocol_layers(None)
        self.assertEqual(result, [])

    def test_clean_protocol_layers_long_list_simplification(self):
        """测试超长协议层级的简化"""
        # 创建一个超过10层的协议列表
        protocols = [
            "eth", "ethertype", "ip", "tcp", "tls",
            "x509sat", "x509af", "x509ce", "pkcs1", "pkcs7",
            "cms", "extra1", "extra2", "extra3", "extra4", "extra5"
        ]
        result = self.analyzer._clean_protocol_layers(protocols)
        
        # 结果应该被简化，核心协议保留，非核心协议限制数量
        self.assertLessEqual(len(result), 10)
        
        # 核心协议应该被保留
        core_protocols = ["eth", "ethertype", "ip", "tcp", "tls"]
        for core in core_protocols:
            self.assertIn(core, result)

    def test_clean_protocol_layers_case_insensitive(self):
        """测试大小写不敏感的去重"""
        protocols = [
            "eth", "ethertype", "ip", "tcp", "tls",
            "X509SAT", "x509sat", "X509AF", "x509af"
        ]
        result = self.analyzer._clean_protocol_layers(protocols)
        
        # 应该只保留第一次出现的协议（保持原始大小写）
        expected = ["eth", "ethertype", "ip", "tcp", "tls", "X509SAT", "X509AF"]
        self.assertEqual(result, expected)

    def test_clean_protocol_layers_preserve_order(self):
        """测试协议层级顺序保持"""
        protocols = [
            "eth", "x509sat", "ethertype", "x509sat", "ip", 
            "x509sat", "tcp", "tls", "x509sat"
        ]
        result = self.analyzer._clean_protocol_layers(protocols)
        expected = ["eth", "x509sat", "ethertype", "ip", "tcp", "tls"]
        self.assertEqual(result, expected)

    def test_clean_protocol_layers_real_world_example(self):
        """测试真实世界的例子（来自问题描述）"""
        # 模拟第7号数据包的原始协议层级
        protocols = [
            "eth", "ethertype", "ip", "tcp", "tls",
            "x509sat", "x509sat", "x509sat", "x509sat", "x509sat",
            "x509sat", "x509sat", "x509sat", "x509sat", "x509sat",
            "x509sat", "x509sat", "x509sat", "x509sat"
        ]
        result = self.analyzer._clean_protocol_layers(protocols)
        expected = ["eth", "ethertype", "ip", "tcp", "tls", "x509sat"]
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
