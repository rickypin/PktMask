"""
测试增强掩码规则功能

验证非TLS TCP载荷掩码规则的正确性
"""

import unittest
from unittest.mock import Mock, patch
from src.pktmask.core.trim.models.tls_models import (
    MaskRule, 
    MaskAction, 
    TLSProcessingStrategy,
    create_non_tls_tcp_mask_rule
)
from src.pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator


class TestEnhancedMaskRules(unittest.TestCase):
    """测试增强掩码规则功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = {
            'enable_non_tls_tcp_masking': True,
            'non_tls_tcp_strategy': 'mask_all_payload'
        }
        self.generator = TLSMaskRuleGenerator(self.config)
    
    def test_mask_action_enum_extension(self):
        """测试掩码操作类型枚举扩展"""
        # 验证新增的MASK_ALL_PAYLOAD操作类型
        self.assertEqual(MaskAction.MASK_ALL_PAYLOAD.value, "mask_all_payload")
        
        # 验证所有操作类型
        expected_actions = {"keep_all", "mask_payload", "mask_all_payload"}
        actual_actions = {action.value for action in MaskAction}
        self.assertEqual(actual_actions, expected_actions)
    
    def test_tls_processing_strategy_extension(self):
        """测试TLS处理策略枚举扩展"""
        # 验证新增的MASK_ALL_PAYLOAD策略
        self.assertEqual(TLSProcessingStrategy.MASK_ALL_PAYLOAD.value, "mask_all_payload")
        
        # 验证所有处理策略
        expected_strategies = {"keep_all", "mask_payload", "mask_all_payload"}
        actual_strategies = {strategy.value for strategy in TLSProcessingStrategy}
        self.assertEqual(actual_strategies, expected_strategies)
    
    def test_create_non_tls_tcp_mask_rule(self):
        """测试创建非TLS TCP掩码规则"""
        packet_number = 5
        tcp_stream_id = "TCP_192.168.1.1:80_192.168.1.2:12345"
        
        rule = create_non_tls_tcp_mask_rule(packet_number, tcp_stream_id)
        
        # 验证规则属性
        self.assertEqual(rule.packet_number, packet_number)
        self.assertEqual(rule.tcp_stream_id, tcp_stream_id)
        self.assertEqual(rule.tls_record_offset, 0)
        self.assertEqual(rule.tls_record_length, 0)
        self.assertEqual(rule.mask_offset, 0)
        self.assertEqual(rule.mask_length, -1)
        self.assertEqual(rule.action, MaskAction.MASK_ALL_PAYLOAD)
        self.assertIsNone(rule.tls_record_type)
        self.assertIn("非TLS TCP载荷全掩码策略", rule.reason)
    
    def test_non_tls_rule_is_mask_operation(self):
        """测试非TLS规则的掩码操作判断"""
        rule = create_non_tls_tcp_mask_rule(1, "test_stream")
        
        # 非TLS全掩码规则应该被识别为掩码操作
        self.assertTrue(rule.is_mask_operation)
    
    def test_non_tls_rule_description(self):
        """测试非TLS规则的描述"""
        rule = create_non_tls_tcp_mask_rule(1, "test_stream")
        
        description = rule.get_description()
        self.assertIn("非TLS TCP载荷全掩码", description)
        self.assertIn(rule.reason, description)
    
    def test_generator_config_non_tls_parameters(self):
        """测试规则生成器的非TLS配置参数"""
        # 验证配置参数正确加载
        self.assertTrue(self.generator._enable_non_tls_tcp_masking)
        self.assertEqual(self.generator._non_tls_tcp_strategy, 'mask_all_payload')
    
    def test_generate_non_tls_tcp_rules(self):
        """测试生成非TLS TCP掩码规则"""
        # 模拟TLS规则（覆盖包1和包3）
        tls_rules = [
            Mock(packet_number=1),
            Mock(packet_number=3)
        ]
        
        # 模拟TCP包信息
        tcp_packets_info = {
            1: {'tcp_stream_id': 'stream1', 'has_payload': True},   # 已有TLS规则
            2: {'tcp_stream_id': 'stream2', 'has_payload': True},   # 需要非TLS规则
            3: {'tcp_stream_id': 'stream3', 'has_payload': True},   # 已有TLS规则
            4: {'tcp_stream_id': 'stream4', 'has_payload': False},  # 无载荷，跳过
            5: {'tcp_stream_id': 'stream5', 'has_payload': True},   # 需要非TLS规则
        }
        
        # 生成非TLS规则
        non_tls_rules = self.generator._generate_non_tls_tcp_rules(tls_rules, tcp_packets_info)
        
        # 验证结果
        self.assertEqual(len(non_tls_rules), 2)  # 包2和包5
        
        # 验证包2的规则
        rule_packet_2 = next(r for r in non_tls_rules if r.packet_number == 2)
        self.assertEqual(rule_packet_2.tcp_stream_id, 'stream2')
        self.assertEqual(rule_packet_2.action, MaskAction.MASK_ALL_PAYLOAD)
        
        # 验证包5的规则
        rule_packet_5 = next(r for r in non_tls_rules if r.packet_number == 5)
        self.assertEqual(rule_packet_5.tcp_stream_id, 'stream5')
        self.assertEqual(rule_packet_5.action, MaskAction.MASK_ALL_PAYLOAD)
    
    def test_generate_enhanced_rules_integration(self):
        """测试增强规则生成的集成功能"""
        # 模拟TLS记录
        tls_records = []  # 空TLS记录列表
        
        # 模拟TCP包信息
        tcp_packets_info = {
            1: {'tcp_stream_id': 'http_stream', 'has_payload': True},
            2: {'tcp_stream_id': 'ssh_stream', 'has_payload': True},
            3: {'tcp_stream_id': 'ftp_stream', 'has_payload': True},
        }
        
        # 生成增强规则
        enhanced_rules = self.generator.generate_enhanced_rules(tls_records, tcp_packets_info)
        
        # 验证结果
        self.assertEqual(len(enhanced_rules), 3)  # 3个非TLS规则
        
        # 验证所有规则都是非TLS全掩码规则
        for rule in enhanced_rules:
            self.assertEqual(rule.action, MaskAction.MASK_ALL_PAYLOAD)
            self.assertIsNone(rule.tls_record_type)
            self.assertEqual(rule.mask_length, -1)
    
    def test_disabled_non_tls_masking(self):
        """测试禁用非TLS TCP载荷掩码时的行为"""
        # 创建禁用非TLS掩码的生成器
        disabled_config = {
            'enable_non_tls_tcp_masking': False,
            'non_tls_tcp_strategy': 'mask_all_payload'
        }
        disabled_generator = TLSMaskRuleGenerator(disabled_config)
        
        # 模拟数据
        tls_records = []
        tcp_packets_info = {
            1: {'tcp_stream_id': 'test_stream', 'has_payload': True}
        }
        
        # 生成规则
        rules = disabled_generator.generate_enhanced_rules(tls_records, tcp_packets_info)
        
        # 验证禁用时不生成非TLS规则
        self.assertEqual(len(rules), 0)


if __name__ == '__main__':
    unittest.main()
