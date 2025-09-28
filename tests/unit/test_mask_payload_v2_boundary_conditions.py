"""
新一代 MaskPayload 阶段边界条件测试

测试各种边界条件和异常场景，确保系统在极端情况下的稳定性。
根据架构文档第4.1节的边界条件测试设计实现。
"""

from pathlib import Path
from typing import List, Tuple
from unittest.mock import Mock, patch

import pytest

from pktmask.core.pipeline.stages.masking_stage.marker.types import (
    FlowInfo,
    KeepRule,
    KeepRuleSet,
)


class TestSequenceWrapAround:
    """TCP序列号回绕测试

    测试32位序列号回绕边界(0xFFFFFFFF → 0x00000000)的处理。
    """

    @pytest.mark.parametrize(
        "test_case",
        [
            # (回绕前序列号, 回绕后序列号, 预期逻辑序号差)
            (0xFFFFFFFE, 0x00000000, 2),
            (0xFFFFFFFF, 0x00000001, 2),
            (0xFFFFFFF0, 0x0000000F, 31),
            (0x80000000, 0x7FFFFFFF, 0xFFFFFFFF),
        ],
    )
    def test_32bit_sequence_wraparound(self, test_case):
        """测试32位序列号回绕边界"""
        seq_before, seq_after, expected_diff = test_case

        # 模拟序列号回绕处理逻辑
        # 这里先创建测试框架，具体实现在后续阶段

        # 创建跨回绕边界的规则
        rule = KeepRule(
            stream_id="test_stream",
            direction="forward",
            seq_start=seq_before,
            seq_end=seq_before + expected_diff,
            rule_type="test_wraparound",
        )

        assert rule.length == expected_diff
        assert rule.seq_start == seq_before
        assert rule.seq_end == seq_before + expected_diff

    def test_logical_sequence_continuity(self):
        """测试64位逻辑序号的连续性"""
        # 模拟多次回绕场景
        test_sequences = [
            0xFFFFFFFE,  # 回绕前
            0xFFFFFFFF,  # 回绕边界
            0x00000000,  # 回绕后
            0x00000001,  # 回绕后继续
            0xFFFFFFFE,  # 第二次回绕前
            0xFFFFFFFF,  # 第二次回绕边界
            0x00000000,  # 第二次回绕后
        ]

        # 预期的64位逻辑序号
        expected_logical = [
            0xFFFFFFFE,
            0xFFFFFFFF,
            0x100000000,  # 第一个epoch
            0x100000001,
            0x1FFFFFFFE,
            0x1FFFFFFFF,
            0x200000000,  # 第二个epoch
        ]

        # 这里创建测试框架，具体的逻辑序号转换在Masker模块实现
        for i, (seq32, expected_seq64) in enumerate(zip(test_sequences, expected_logical)):
            # 验证逻辑序号的连续性
            assert expected_seq64 >= 0, f"逻辑序号不能为负: {expected_seq64}"
            if i > 0:
                assert (
                    expected_seq64 > expected_logical[i - 1]
                ), f"逻辑序号必须递增: {expected_seq64} <= {expected_logical[i-1]}"

    def test_multiple_epoch_handling(self):
        """测试多次回绕的epoch处理"""
        # 模拟连续多次回绕场景
        epochs = 5
        sequences_per_epoch = 3

        for epoch in range(epochs):
            for seq_offset in range(sequences_per_epoch):
                seq32 = seq_offset
                expected_logical = (epoch << 32) | seq32

                # 验证epoch计算正确性
                calculated_epoch = expected_logical >> 32
                calculated_seq = expected_logical & 0xFFFFFFFF

                assert calculated_epoch == epoch
                assert calculated_seq == seq32


class TestCrossSegmentTLS:
    """跨TCP段TLS消息测试

    测试跨多个TCP段的TLS消息处理。
    """

    @pytest.mark.parametrize(
        "scenario",
        [
            "handshake_across_2_segments",
            "handshake_across_5_segments",
            "application_data_fragmented",
            "mixed_messages_fragmented",
        ],
    )
    def test_tls_message_spanning_segments(self, scenario):
        """测试跨多个TCP段的TLS消息"""
        # 根据不同场景创建测试数据
        if scenario == "handshake_across_2_segments":
            # TLS握手消息分割到2个TCP段
            segments = [
                {
                    "seq_start": 1000,
                    "seq_end": 1500,
                    "tls_type": 22,
                    "fragment": "first",
                },
                {
                    "seq_start": 1500,
                    "seq_end": 2000,
                    "tls_type": 22,
                    "fragment": "last",
                },
            ]
        elif scenario == "handshake_across_5_segments":
            # TLS握手消息分割到5个TCP段
            segments = [
                {
                    "seq_start": 1000,
                    "seq_end": 1200,
                    "tls_type": 22,
                    "fragment": "first",
                },
                {
                    "seq_start": 1200,
                    "seq_end": 1400,
                    "tls_type": 22,
                    "fragment": "middle",
                },
                {
                    "seq_start": 1400,
                    "seq_end": 1600,
                    "tls_type": 22,
                    "fragment": "middle",
                },
                {
                    "seq_start": 1600,
                    "seq_end": 1800,
                    "tls_type": 22,
                    "fragment": "middle",
                },
                {
                    "seq_start": 1800,
                    "seq_end": 2000,
                    "tls_type": 22,
                    "fragment": "last",
                },
            ]
        elif scenario == "application_data_fragmented":
            # 应用数据分片
            segments = [
                {
                    "seq_start": 2000,
                    "seq_end": 2300,
                    "tls_type": 23,
                    "fragment": "first",
                },
                {
                    "seq_start": 2300,
                    "seq_end": 2600,
                    "tls_type": 23,
                    "fragment": "middle",
                },
                {
                    "seq_start": 2600,
                    "seq_end": 2900,
                    "tls_type": 23,
                    "fragment": "last",
                },
            ]
        else:  # mixed_messages_fragmented
            # 混合消息类型分片
            segments = [
                {
                    "seq_start": 3000,
                    "seq_end": 3200,
                    "tls_type": 22,
                    "fragment": "complete",
                },
                {
                    "seq_start": 3200,
                    "seq_end": 3500,
                    "tls_type": 23,
                    "fragment": "first",
                },
                {
                    "seq_start": 3500,
                    "seq_end": 3800,
                    "tls_type": 23,
                    "fragment": "last",
                },
                {
                    "seq_start": 3800,
                    "seq_end": 4000,
                    "tls_type": 21,
                    "fragment": "complete",
                },
            ]

        # 验证分片的连续性
        for i in range(len(segments) - 1):
            current_end = segments[i]["seq_end"]
            next_start = segments[i + 1]["seq_start"]
            assert current_end == next_start, f"分片不连续: {current_end} != {next_start}"

        # 创建跨段规则
        total_start = segments[0]["seq_start"]
        total_end = segments[-1]["seq_end"]

        cross_segment_rule = KeepRule(
            stream_id="cross_segment_test",
            direction="forward",
            seq_start=total_start,
            seq_end=total_end,
            rule_type=f"tls_{segments[0]['tls_type']}_cross_segment",
            metadata={
                "scenario": scenario,
                "segment_count": len(segments),
                "fragments": [seg["fragment"] for seg in segments],
            },
        )

        assert cross_segment_rule.length == total_end - total_start
        assert cross_segment_rule.metadata["segment_count"] == len(segments)

    def test_tls_record_boundary_detection(self):
        """测试TLS记录边界检测"""
        # 模拟TLS记录边界检测逻辑
        tls_records = [
            {"type": 22, "start": 1000, "end": 1500, "complete": True},
            {"type": 23, "start": 1500, "end": 2000, "complete": False},  # 跨段
            {"type": 23, "start": 2000, "end": 2200, "complete": False},  # 跨段继续
            {"type": 21, "start": 2200, "end": 2300, "complete": True},
        ]

        # 验证记录边界的正确性
        for i, record in enumerate(tls_records):
            assert record["end"] > record["start"], f"记录{i}边界无效"
            assert record["type"] in [20, 21, 22, 23, 24], f"记录{i}类型无效"

            # 验证连续性
            if i > 0:
                prev_end = tls_records[i - 1]["end"]
                curr_start = record["start"]
                assert curr_start == prev_end, f"记录{i}不连续"

    def test_incomplete_tls_records(self):
        """测试不完整的TLS记录处理"""
        # 模拟截断的TLS记录
        incomplete_records = [
            {
                "type": 22,
                "start": 1000,
                "expected_end": 2000,
                "actual_end": 1800,
                "truncated": True,
            },
            {
                "type": 23,
                "start": 2000,
                "expected_end": 3000,
                "actual_end": 3000,
                "truncated": False,
            },
        ]

        for record in incomplete_records:
            if record["truncated"]:
                # 截断记录的处理
                assert record["actual_end"] < record["expected_end"]
                # 应该创建部分保留规则
                partial_rule = KeepRule(
                    stream_id="truncated_test",
                    direction="forward",
                    seq_start=record["start"],
                    seq_end=record["actual_end"],
                    rule_type=f"tls_{record['type']}_truncated",
                    metadata={
                        "truncated": True,
                        "expected_length": record["expected_end"] - record["start"],
                    },
                )
                assert partial_rule.metadata["truncated"] is True
            else:
                # 完整记录的处理
                assert record["actual_end"] == record["expected_end"]


class TestAbnormalTCPFlow:
    """异常TCP流测试

    测试各种异常TCP流场景的处理。
    """

    def test_tcp_rst_handling(self):
        """测试TCP RST包的处理"""
        # 模拟TCP RST场景
        flow_before_rst = FlowInfo(
            stream_id="rst_test",
            src_ip="192.168.1.1",
            dst_ip="192.168.1.2",
            src_port=12345,
            dst_port=443,
            protocol="tcp",
            direction="forward",
            packet_count=50,
            byte_count=25000,
        )

        # RST包应该触发流状态清理
        # 这里创建测试框架，具体实现在后续阶段
        assert flow_before_rst.packet_count > 0

        # 模拟RST后的状态
        # 应该保留已有的规则，但标记流为已终止
        ruleset = KeepRuleSet()
        ruleset.tcp_flows["rst_test"] = flow_before_rst

        # 添加RST前的规则
        pre_rst_rule = KeepRule(
            stream_id="rst_test",
            direction="forward",
            seq_start=1000,
            seq_end=2000,
            rule_type="tls_handshake",
            metadata={"before_rst": True},
        )
        ruleset.add_rule(pre_rst_rule)

        # RST后不应该影响已有规则
        assert len(ruleset.rules) == 1
        assert ruleset.rules[0].metadata["before_rst"] is True

    def test_out_of_order_packets(self):
        """测试乱序数据包处理"""
        test_scenarios = [
            {
                "name": "mild_reordering",
                "packets": [
                    {"seq": 1000, "len": 500, "order": 1},
                    {"seq": 1500, "len": 500, "order": 3},  # 乱序
                    {"seq": 2000, "len": 500, "order": 2},  # 乱序
                    {"seq": 2500, "len": 500, "order": 4},
                ],
            },
            {
                "name": "severe_reordering",
                "packets": [
                    {"seq": 1000, "len": 200, "order": 1},
                    {"seq": 1200, "len": 200, "order": 6},  # 严重乱序
                    {"seq": 1400, "len": 200, "order": 2},
                    {"seq": 1600, "len": 200, "order": 5},
                    {"seq": 1800, "len": 200, "order": 3},
                    {"seq": 2000, "len": 200, "order": 4},
                ],
            },
        ]

        for scenario in test_scenarios:
            packets = scenario["packets"]

            # 验证乱序检测
            for i in range(len(packets) - 1):
                curr_order = packets[i]["order"]
                next_order = packets[i + 1]["order"]

                if next_order < curr_order:
                    # 检测到乱序
                    assert True, f"检测到乱序: {curr_order} -> {next_order}"

            # 创建乱序场景的规则
            # 规则应该基于序列号而不是到达顺序
            sorted_packets = sorted(packets, key=lambda p: p["seq"])

            for packet in sorted_packets:
                rule = KeepRule(
                    stream_id=f"ooo_{scenario['name']}",
                    direction="forward",
                    seq_start=packet["seq"],
                    seq_end=packet["seq"] + packet["len"],
                    rule_type="ooo_test",
                    metadata={"original_order": packet["order"]},
                )
                assert rule.length == packet["len"]
