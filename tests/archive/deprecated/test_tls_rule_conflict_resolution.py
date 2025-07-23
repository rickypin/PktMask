"""
测试TLS掩码规则冲突解决机制

验证当同一个包有多个冲突的TLS掩码规则时，
冲突解决机制能够正确选择最优规则。
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from pktmask.core.processors.scapy_mask_applier import ScapyMaskApplier
from pktmask.core.trim.models.tls_models import MaskRule, MaskAction


class TestTLSRuleConflictResolution(unittest.TestCase):
    """测试TLS掩码规则冲突解决机制"""
    
    def setUp(self):
        """测试初始化"""
        self.applier = ScapyMaskApplier()
        
    def test_tls22_vs_tls23_conflict_resolution(self):
        """测试TLS-22与TLS-23规则冲突时，优先选择TLS-22保留规则"""

        # 创建冲突的规则：TLS-22保留 vs TLS-23掩码
        tls22_preserve_rule = MaskRule(
            packet_number=8,
            tcp_stream_id="test_stream",
            tls_record_offset=0,
            tls_record_length=1430,
            mask_offset=0,
            mask_length=0,
            action=MaskAction.KEEP_ALL,
            reason="TLS-22跨包完全保留：握手消息保持完整性",
            tls_record_type=22
        )

        tls23_mask_rule = MaskRule(
            packet_number=8,
            tcp_stream_id="test_stream",
            tls_record_offset=0,
            tls_record_length=1430,
            mask_offset=5,
            mask_length=1425,
            action=MaskAction.MASK_PAYLOAD,
            reason="TLS-23跨包分段掩码：应用数据敏感信息保护",
            tls_record_type=23
        )
        
        # 测试冲突解决
        conflicting_rules = [tls22_preserve_rule, tls23_mask_rule]
        resolved_rules = self.applier._resolve_rule_conflicts(conflicting_rules, 8)
        
        # 验证结果
        self.assertEqual(len(resolved_rules), 1, "冲突解决后应该只有1个规则")
        self.assertEqual(resolved_rules[0].tls_record_type, 22, "应该选择TLS-22规则")
        self.assertEqual(resolved_rules[0].action, MaskAction.KEEP_ALL, "应该选择保留规则")
        
    def test_multiple_tls23_rules_conflict_resolution(self):
        """测试多个TLS-23规则冲突时，选择最严格的掩码规则"""

        # 创建多个TLS-23规则
        smart_mask_rule = MaskRule(
            packet_number=14,
            tcp_stream_id="test_stream",
            tls_record_offset=0,
            tls_record_length=1171,
            mask_offset=5,
            mask_length=1166,
            action=MaskAction.MASK_PAYLOAD,  # 使用MASK_PAYLOAD代替SMART_MASK
            reason="TLS-23智能掩码：保留头部5字节",
            tls_record_type=23
        )

        full_mask_rule1 = MaskRule(
            packet_number=14,
            tcp_stream_id="test_stream",
            tls_record_offset=0,
            tls_record_length=1171,
            mask_offset=0,
            mask_length=1171,
            action=MaskAction.MASK_PAYLOAD,
            reason="TLS-23跨包重组掩码：完全掩码载荷",
            tls_record_type=23
        )

        full_mask_rule2 = MaskRule(
            packet_number=14,
            tcp_stream_id="test_stream",
            tls_record_offset=0,
            tls_record_length=1171,
            mask_offset=0,
            mask_length=1171,
            action=MaskAction.MASK_PAYLOAD,
            reason="TLS-23跨包分段掩码：完全掩码载荷",
            tls_record_type=23
        )
        
        # 测试冲突解决
        conflicting_rules = [smart_mask_rule, full_mask_rule1, full_mask_rule2]
        resolved_rules = self.applier._resolve_rule_conflicts(conflicting_rules, 14)
        
        # 验证结果
        self.assertEqual(len(resolved_rules), 1, "冲突解决后应该只有1个规则")
        self.assertEqual(resolved_rules[0].action, MaskAction.MASK_PAYLOAD, "应该选择完全掩码规则")
        self.assertIn("重组", resolved_rules[0].reason, "应该优先选择重组规则")
        
    def test_cross_packet_vs_single_packet_priority(self):
        """测试跨包规则优先于单包规则"""

        # 创建单包规则和跨包规则
        single_packet_rule = MaskRule(
            packet_number=9,
            tcp_stream_id="test_stream",
            tls_record_offset=0,
            tls_record_length=294,
            mask_offset=0,
            mask_length=0,
            action=MaskAction.KEEP_ALL,
            reason="TLS-22单包完全保留：握手消息",
            tls_record_type=22
        )

        cross_packet_rule = MaskRule(
            packet_number=9,
            tcp_stream_id="test_stream",
            tls_record_offset=0,
            tls_record_length=1625,
            mask_offset=0,
            mask_length=0,
            action=MaskAction.KEEP_ALL,
            reason="TLS-22跨包完全保留：握手消息跨包重组",
            tls_record_type=22
        )
        
        # 测试冲突解决
        conflicting_rules = [single_packet_rule, cross_packet_rule]
        resolved_rules = self.applier._resolve_rule_conflicts(conflicting_rules, 9)
        
        # 验证结果
        self.assertEqual(len(resolved_rules), 1, "冲突解决后应该只有1个规则")
        self.assertIn("跨包", resolved_rules[0].reason, "应该选择跨包规则")
        
    def test_no_conflict_single_rule(self):
        """测试单个规则时不需要冲突解决"""

        single_rule = MaskRule(
            packet_number=10,
            tcp_stream_id="test_stream",
            tls_record_offset=0,
            tls_record_length=1460,
            mask_offset=5,
            mask_length=1455,
            action=MaskAction.MASK_PAYLOAD,
            reason="TLS-23智能掩码：保留头部5字节",
            tls_record_type=23
        )
        
        # 测试冲突解决
        resolved_rules = self.applier._resolve_rule_conflicts([single_rule], 10)
        
        # 验证结果
        self.assertEqual(len(resolved_rules), 1, "单个规则应该保持不变")
        self.assertEqual(resolved_rules[0], single_rule, "规则内容应该保持不变")
        
    def test_empty_rules_list(self):
        """测试空规则列表"""
        
        # 测试冲突解决
        resolved_rules = self.applier._resolve_rule_conflicts([], 1)
        
        # 验证结果
        self.assertEqual(len(resolved_rules), 0, "空列表应该返回空列表")


if __name__ == '__main__':
    unittest.main()
