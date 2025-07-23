"""
新一代 MaskPayload 阶段基础测试

测试新架构的基础组件和数据结构。
"""

import pytest
from pathlib import Path
from typing import Dict, Any

from pktmask.core.pipeline.stages.mask_payload_v2.marker.types import (
    KeepRule,
    KeepRuleSet,
    FlowInfo,
)


class TestKeepRule:
    """测试 KeepRule 数据结构"""

    def test_valid_rule_creation(self):
        """测试有效规则创建"""
        rule = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=1000,
            seq_end=2000,
            rule_type="tls_header",
        )

        assert rule.stream_id == "stream_1"
        assert rule.direction == "forward"
        assert rule.seq_start == 1000
        assert rule.seq_end == 2000
        assert rule.rule_type == "tls_header"
        assert rule.length == 1000

    def test_invalid_rule_creation(self):
        """测试无效规则创建"""
        # 负序列号
        with pytest.raises(ValueError, match="序列号不能为负数"):
            KeepRule(
                stream_id="stream_1",
                direction="forward",
                seq_start=-1,
                seq_end=1000,
                rule_type="tls_header",
            )

        # 起始序列号大于等于结束序列号
        with pytest.raises(ValueError, match="起始序列号必须小于结束序列号"):
            KeepRule(
                stream_id="stream_1",
                direction="forward",
                seq_start=2000,
                seq_end=1000,
                rule_type="tls_header",
            )

        # 空流标识
        with pytest.raises(ValueError, match="流标识不能为空"):
            KeepRule(
                stream_id="",
                direction="forward",
                seq_start=1000,
                seq_end=2000,
                rule_type="tls_header",
            )

        # 无效方向
        with pytest.raises(ValueError, match="流方向必须是"):
            KeepRule(
                stream_id="stream_1",
                direction="invalid",
                seq_start=1000,
                seq_end=2000,
                rule_type="tls_header",
            )

    def test_rule_overlap_detection(self):
        """测试规则重叠检测"""
        rule1 = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=1000,
            seq_end=2000,
            rule_type="tls_header",
        )

        # 重叠规则
        rule2 = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=1500,
            seq_end=2500,
            rule_type="tls_payload",
        )

        # 不重叠规则
        rule3 = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=3000,
            seq_end=4000,
            rule_type="tls_header",
        )

        # 不同流的规则
        rule4 = KeepRule(
            stream_id="stream_2",
            direction="forward",
            seq_start=1500,
            seq_end=2500,
            rule_type="tls_header",
        )

        assert rule1.overlaps_with(rule2)
        assert not rule1.overlaps_with(rule3)
        assert not rule1.overlaps_with(rule4)

    def test_rule_merging(self):
        """测试规则合并"""
        rule1 = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=1000,
            seq_end=2000,
            rule_type="tls_header",
            metadata={"rule_id": "rule1"},
        )

        rule2 = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=1500,
            seq_end=2500,
            rule_type="tls_payload",
            metadata={"rule_id": "rule2"},
        )

        merged = rule1.merge_with(rule2)

        assert merged is not None
        assert merged.seq_start == 1000
        assert merged.seq_end == 2500
        assert merged.rule_type == "tls_header+tls_payload"
        assert "merged_from" in merged.metadata
        assert merged.metadata["merged_from"] == ["rule1", "rule2"]


class TestKeepRuleSet:
    """测试 KeepRuleSet 数据结构"""

    def test_empty_ruleset_creation(self):
        """测试空规则集创建"""
        ruleset = KeepRuleSet()

        assert len(ruleset.rules) == 0
        assert len(ruleset.tcp_flows) == 0
        assert ruleset.get_total_preserved_bytes() == 0
        assert ruleset.get_stream_count() == 0

    def test_add_rules(self):
        """测试添加规则"""
        ruleset = KeepRuleSet()

        rule1 = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=1000,
            seq_end=2000,
            rule_type="tls_header",
        )

        rule2 = KeepRule(
            stream_id="stream_1",
            direction="reverse",
            seq_start=3000,
            seq_end=4000,
            rule_type="tls_payload",
        )

        ruleset.add_rule(rule1)
        ruleset.add_rule(rule2)

        assert len(ruleset.rules) == 2
        assert ruleset.get_total_preserved_bytes() == 2000

        # 测试按流和方向获取规则
        forward_rules = ruleset.get_rules_for_stream("stream_1", "forward")
        assert len(forward_rules) == 1
        assert forward_rules[0] == rule1

        reverse_rules = ruleset.get_rules_for_stream("stream_1", "reverse")
        assert len(reverse_rules) == 1
        assert reverse_rules[0] == rule2

    def test_rule_optimization(self):
        """测试规则优化"""
        ruleset = KeepRuleSet()

        # 添加重叠规则
        rule1 = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=1000,
            seq_end=2000,
            rule_type="tls_header",
        )

        rule2 = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=1500,
            seq_end=2500,
            rule_type="tls_payload",
        )

        # 添加相邻规则
        rule3 = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=2500,
            seq_end=3000,
            rule_type="tls_header",
        )

        ruleset.add_rule(rule1)
        ruleset.add_rule(rule2)
        ruleset.add_rule(rule3)

        assert len(ruleset.rules) == 3

        # 优化规则
        ruleset.optimize_rules()

        # 应该合并为一个规则
        assert len(ruleset.rules) == 1
        merged_rule = ruleset.rules[0]
        assert merged_rule.seq_start == 1000
        assert merged_rule.seq_end == 3000

    def test_validation(self):
        """测试规则集验证"""
        ruleset = KeepRuleSet()

        # 添加有效规则
        valid_rule = KeepRule(
            stream_id="stream_1",
            direction="forward",
            seq_start=1000,
            seq_end=2000,
            rule_type="tls_header",
        )
        ruleset.add_rule(valid_rule)

        # 添加流信息
        flow_info = FlowInfo(
            stream_id="stream_1",
            src_ip="192.168.1.1",
            dst_ip="192.168.1.2",
            src_port=12345,
            dst_port=443,
            protocol="tcp",
            direction="forward",
        )
        ruleset.tcp_flows["stream_1"] = flow_info

        errors = ruleset.validate()
        assert len(errors) == 0

        # 添加无效规则（通过直接修改绕过验证）
        invalid_rule = KeepRule(
            stream_id="stream_2",
            direction="forward",
            seq_start=1000,
            seq_end=2000,
            rule_type="tls_header",
        )
        # 手动设置无效值
        invalid_rule.seq_start = -1
        ruleset.rules.append(invalid_rule)

        errors = ruleset.validate()
        assert len(errors) > 0
        assert "序列号不能为负数" in errors[0]


class TestFlowInfo:
    """测试 FlowInfo 数据结构"""

    def test_flow_info_creation(self):
        """测试流信息创建"""
        flow = FlowInfo(
            stream_id="stream_1",
            src_ip="192.168.1.1",
            dst_ip="192.168.1.2",
            src_port=12345,
            dst_port=443,
            protocol="tcp",
            direction="forward",
            packet_count=100,
            byte_count=50000,
            first_seen=1234567890.0,
            last_seen=1234567900.0,
        )

        assert flow.stream_id == "stream_1"
        assert flow.src_ip == "192.168.1.1"
        assert flow.dst_ip == "192.168.1.2"
        assert flow.src_port == 12345
        assert flow.dst_port == 443
        assert flow.protocol == "tcp"
        assert flow.direction == "forward"
        assert flow.packet_count == 100
        assert flow.byte_count == 50000
        assert flow.first_seen == 1234567890.0
        assert flow.last_seen == 1234567900.0
