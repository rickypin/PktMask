"""
TLS Protocol Marker Integration Tests

Uses real TLS test files to validate TLS protocol marker functionality.
"""

import pytest
from pathlib import Path

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import (
    TLSProtocolMarker,
)
from pktmask.core.pipeline.stages.mask_payload_v2.marker.types import KeepRuleSet


class TestTLSMarkerIntegration:
    """TLS标记器集成测试"""

    @pytest.fixture
    def tls_marker(self):
        """创建TLS标记器实例"""
        config = {
            "preserve": {
                "handshake": True,
                "application_data": False,
                "alert": True,
                "change_cipher_spec": True,
                "heartbeat": True,
            },
            "tshark_path": "/usr/local/bin/tshark",
        }
        marker = TLSProtocolMarker(config)
        if not marker.initialize():
            pytest.skip("TLS标记器初始化失败，可能缺少tshark")
        return marker

    @pytest.fixture
    def tls_test_files(self):
        """获取TLS测试文件列表"""
        test_data_dir = Path("tests/data/tls")
        if not test_data_dir.exists():
            pytest.skip("TLS测试数据目录不存在")

        pcap_files = list(test_data_dir.glob("*.pcap")) + list(
            test_data_dir.glob("*.pcapng")
        )
        if not pcap_files:
            pytest.skip("没有找到TLS测试文件")

        return pcap_files

    def test_tls_marker_initialization(self, tls_marker):
        """测试TLS标记器初始化"""
        assert tls_marker is not None
        assert tls_marker._initialized is True
        assert hasattr(tls_marker, "tshark_exec")

    def test_analyze_tls_files(self, tls_marker, tls_test_files):
        """测试分析TLS文件"""
        results = {}

        for pcap_file in tls_test_files[:3]:  # 只测试前3个文件，避免测试时间过长
            print(f"\n分析文件: {pcap_file.name}")

            try:
                ruleset = tls_marker.analyze_file(str(pcap_file), {})

                # 验证返回的规则集
                assert isinstance(ruleset, KeepRuleSet)

                # 记录结果
                results[pcap_file.name] = {
                    "success": True,
                    "rules_count": len(ruleset.rules),
                    "flows_count": len(ruleset.tcp_flows),
                    "metadata": ruleset.metadata,
                }

                print(f"  - 生成规则数: {len(ruleset.rules)}")
                print(f"  - TCP流数: {len(ruleset.tcp_flows)}")
                print(f"  - 分析时间: {ruleset.metadata.get('analysis_time', 0):.3f}s")

                # 验证规则有效性
                if ruleset.rules:
                    errors = ruleset.validate()
                    assert len(errors) == 0, f"规则验证失败: {errors}"

            except Exception as e:
                results[pcap_file.name] = {"success": False, "error": str(e)}
                print(f"  - 分析失败: {e}")

        # 验证至少有一个文件分析成功
        successful_analyses = [r for r in results.values() if r["success"]]
        assert len(successful_analyses) > 0, f"所有文件分析都失败了: {results}"

        # 打印总结
        print(f"\n分析总结:")
        print(f"  - 成功分析: {len(successful_analyses)}/{len(results)}")
        total_rules = sum(r["rules_count"] for r in successful_analyses)
        total_flows = sum(r["flows_count"] for r in successful_analyses)
        print(f"  - 总规则数: {total_rules}")
        print(f"  - 总流数: {total_flows}")

    def test_tls_rule_types_coverage(self, tls_marker, tls_test_files):
        """测试TLS规则类型覆盖"""
        if not tls_test_files:
            pytest.skip("没有TLS测试文件")

        # 分析第一个文件
        pcap_file = tls_test_files[0]
        ruleset = tls_marker.analyze_file(str(pcap_file), {})

        if not ruleset.rules:
            pytest.skip("没有生成任何规则")

        # 统计规则类型
        rule_types = {}
        for rule in ruleset.rules:
            rule_type = rule.rule_type
            if rule_type not in rule_types:
                rule_types[rule_type] = 0
            rule_types[rule_type] += 1

        print(f"\n规则类型分布:")
        for rule_type, count in rule_types.items():
            print(f"  - {rule_type}: {count}")

        # 验证至少有一种TLS规则类型
        tls_rule_types = [rt for rt in rule_types.keys() if rt.startswith("tls_")]
        assert len(tls_rule_types) > 0, "没有生成TLS相关的规则"

    def test_sequence_number_handling(self, tls_marker, tls_test_files):
        """测试序列号处理"""
        if not tls_test_files:
            pytest.skip("没有TLS测试文件")

        pcap_file = tls_test_files[0]
        ruleset = tls_marker.analyze_file(str(pcap_file), {})

        if not ruleset.rules:
            pytest.skip("没有生成任何规则")

        # 验证序列号的有效性
        for rule in ruleset.rules:
            assert rule.seq_start >= 0, f"序列号起始值无效: {rule.seq_start}"
            assert rule.seq_end > rule.seq_start, f"序列号结束值无效: {rule.seq_end}"
            assert rule.length > 0, f"规则长度无效: {rule.length}"

        # 检查同一流中规则的序列号是否合理
        stream_rules = {}
        for rule in ruleset.rules:
            key = (rule.stream_id, rule.direction)
            if key not in stream_rules:
                stream_rules[key] = []
            stream_rules[key].append(rule)

        for (stream_id, direction), rules in stream_rules.items():
            if len(rules) > 1:
                # 按序列号排序
                sorted_rules = sorted(rules, key=lambda r: r.seq_start)

                # 验证序列号的合理性（允许重叠，因为TLS消息可能跨段）
                for i in range(len(sorted_rules) - 1):
                    curr_rule = sorted_rules[i]
                    next_rule = sorted_rules[i + 1]

                    # 下一个规则的起始序列号不应该远小于当前规则的起始序列号
                    # （除非发生了序列号回绕）
                    if next_rule.seq_start < curr_rule.seq_start:
                        # 可能是序列号回绕，检查是否合理
                        assert (
                            curr_rule.seq_start - next_rule.seq_start
                        ) > 0x7FFFFFFF, f"序列号顺序异常: {curr_rule.seq_start} -> {next_rule.seq_start}"

    def test_flow_direction_consistency(self, tls_marker, tls_test_files):
        """测试流方向一致性"""
        if not tls_test_files:
            pytest.skip("没有TLS测试文件")

        pcap_file = tls_test_files[0]
        ruleset = tls_marker.analyze_file(str(pcap_file), {})

        if not ruleset.rules:
            pytest.skip("没有生成任何规则")

        # 统计流方向
        directions = {}
        for rule in ruleset.rules:
            key = rule.stream_id
            if key not in directions:
                directions[key] = set()
            directions[key].add(rule.direction)

        print(f"\n流方向统计:")
        for stream_id, direction_set in directions.items():
            print(f"  - 流 {stream_id}: {list(direction_set)}")

        # 验证每个流至少有一个方向
        for stream_id, direction_set in directions.items():
            assert len(direction_set) > 0, f"流 {stream_id} 没有方向信息"
            # 验证方向值有效
            for direction in direction_set:
                assert direction in ["forward", "reverse"], f"无效的流方向: {direction}"
