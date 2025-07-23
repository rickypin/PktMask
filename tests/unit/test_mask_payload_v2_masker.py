"""
测试 PayloadMasker 核心掩码算法

验证基于 TCP_MARKER_REFERENCE.md 实现的核心掩码算法功能。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

from src.pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import (
    PayloadMasker,
)
from src.pktmask.core.pipeline.stages.mask_payload_v2.masker.memory_optimizer import (
    MemoryOptimizer,
)
from src.pktmask.core.pipeline.stages.mask_payload_v2.masker.error_handler import (
    ErrorRecoveryHandler,
    ErrorSeverity,
    ErrorCategory,
)
from src.pktmask.core.pipeline.stages.mask_payload_v2.masker.data_validator import (
    DataValidator,
)
from src.pktmask.core.pipeline.stages.mask_payload_v2.masker.fallback_handler import (
    FallbackHandler,
    FallbackMode,
)
from src.pktmask.core.pipeline.stages.mask_payload_v2.marker.types import (
    KeepRule,
    KeepRuleSet,
    FlowInfo,
)


# 模拟 scapy 层类型
class MockIP:
    pass


class MockTCP:
    pass


class TestPayloadMasker:
    """测试 PayloadMasker 核心功能"""

    def setup_method(self):
        """测试前准备"""
        self.config = {
            "chunk_size": 100,
            "verify_checksums": True,
            "mask_byte_value": 0x00,
        }
        self.masker = PayloadMasker(self.config)

    def test_masker_initialization(self):
        """测试掩码器初始化"""
        assert self.masker.chunk_size == 100
        assert self.masker.verify_checksums is True
        assert self.masker.mask_byte_value == 0x00
        assert len(self.masker.seq_state) == 0

    def test_logical_seq_normal_case(self):
        """测试正常序列号处理"""
        flow_key = "test_flow"

        # 正常递增序列号
        seq1 = self.masker.logical_seq(1000, flow_key)
        seq2 = self.masker.logical_seq(1100, flow_key)
        seq3 = self.masker.logical_seq(1200, flow_key)

        assert seq1 == 1000
        assert seq2 == 1100
        assert seq3 == 1200

    def test_logical_seq_wraparound(self):
        """测试序列号回绕处理"""
        flow_key = "test_flow"

        # 接近回绕的序列号
        seq1 = self.masker.logical_seq(0xFFFFFFFE, flow_key)
        seq2 = self.masker.logical_seq(0xFFFFFFFF, flow_key)
        seq3 = self.masker.logical_seq(0x00000000, flow_key)  # 回绕
        seq4 = self.masker.logical_seq(0x00000001, flow_key)

        assert seq1 == 0xFFFFFFFE
        assert seq2 == 0xFFFFFFFF
        assert seq3 == 0x100000000  # 第二个epoch
        assert seq4 == 0x100000001

    def test_preprocess_keep_rules(self):
        """测试保留规则预处理"""
        # 创建测试规则
        rules = [
            KeepRule("stream1", "forward", 100, 200, "tls_header"),
            KeepRule("stream1", "forward", 300, 400, "tls_header"),
            KeepRule("stream1", "reverse", 150, 250, "tls_header"),
            KeepRule("stream2", "forward", 500, 600, "tls_header"),
        ]

        keep_rules = KeepRuleSet(rules=rules)

        # 预处理规则
        rule_lookup = self.masker._preprocess_keep_rules(keep_rules)

        # 验证结构
        assert "stream1" in rule_lookup
        assert "stream2" in rule_lookup
        assert "forward" in rule_lookup["stream1"]
        assert "reverse" in rule_lookup["stream1"]
        assert "forward" in rule_lookup["stream2"]

        # 验证边界点
        forward_bounds = rule_lookup["stream1"]["forward"]["bounds"]
        assert forward_bounds == [100, 200, 300, 400]

        # 验证保留集合
        forward_keep_set = rule_lookup["stream1"]["forward"]["keep_set"]
        assert (100, 200) in forward_keep_set
        assert (300, 400) in forward_keep_set

    def test_apply_keep_rules_simple(self):
        """测试简单保留规则应用"""
        # 创建测试载荷
        payload = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # 26字节

        # 创建规则数据
        rule_data = {
            "bounds": [100, 105, 110, 115],
            "keep_set": {(100, 105), (110, 115)},
        }

        # 应用规则 (序列号100-126)
        result = self.masker._apply_keep_rules(payload, 100, 126, rule_data)

        # 验证结果
        assert result is not None
        assert len(result) == len(payload)

        # 前5字节应该保留 (100-105)
        assert result[0:5] == payload[0:5]  # ABCDE

        # 中间5字节应该被掩码 (105-110)
        assert result[5:10] == b"\x00" * 5

        # 后5字节应该保留 (110-115)
        assert result[10:15] == payload[10:15]  # KLMNO

        # 剩余字节应该被掩码
        assert result[15:] == b"\x00" * (len(payload) - 15)

    def test_apply_keep_rules_no_match(self):
        """测试无匹配规则的情况"""
        payload = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        rule_data = {
            "bounds": [200, 205, 210, 215],
            "keep_set": {(200, 205), (210, 215)},
        }

        # 应用规则 (序列号100-126，不匹配)
        result = self.masker._apply_keep_rules(payload, 100, 126, rule_data)

        # 应该返回None，因为没有匹配的规则
        assert result is None

    def test_apply_keep_rules_partial_overlap(self):
        """测试部分重叠的保留规则"""
        payload = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # 26字节

        rule_data = {"bounds": [95, 105, 120, 130], "keep_set": {(95, 105), (120, 130)}}

        # 应用规则 (序列号100-126)
        result = self.masker._apply_keep_rules(payload, 100, 126, rule_data)

        assert result is not None
        assert len(result) == len(payload)

        # 前5字节应该保留 (100-105，部分重叠)
        assert result[0:5] == payload[0:5]

        # 中间部分应该被掩码 (105-120)
        assert result[5:20] == b"\x00" * 15

        # 后6字节应该保留 (120-126，部分重叠)
        assert result[20:26] == payload[20:26]

    @patch(
        "src.pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker.PcapReader"
    )
    @patch(
        "src.pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker.PcapWriter"
    )
    def test_apply_masking_no_scapy(self, mock_writer, mock_reader):
        """测试没有scapy时的错误处理和降级处理"""
        # 模拟scapy不可用
        with patch(
            "src.pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker.PcapReader",
            None,
        ):
            masker = PayloadMasker(self.config)

            keep_rules = KeepRuleSet()

            with (
                tempfile.NamedTemporaryFile(suffix=".pcap") as input_file,
                tempfile.NamedTemporaryFile(suffix=".pcap") as output_file,
            ):

                stats = masker.apply_masking(
                    input_file.name, output_file.name, keep_rules
                )

                # 现在有了降级处理，所以可能成功（通过降级处理）
                if stats.success:
                    # 降级处理成功的情况
                    assert hasattr(stats, "fallback_used")
                    assert stats.fallback_used is True
                    assert len(stats.errors) > 0
                    assert "降级处理成功" in stats.errors[0]
                else:
                    # 降级处理也失败的情况
                    assert len(stats.errors) > 0

    def test_build_stream_id(self):
        """测试流标识构建"""
        # 模拟IP和TCP层
        ip_layer = Mock()
        tcp_layer = Mock()

        # 测试正向流
        ip_layer.src = "10.0.0.1"
        ip_layer.dst = "10.0.0.2"
        tcp_layer.sport = 1234
        tcp_layer.dport = 80

        stream_id = self.masker._build_stream_id(ip_layer, tcp_layer)
        assert stream_id == "10.0.0.1:1234-10.0.0.2:80"

        # 测试反向流（应该标准化为相同的流标识）
        ip_layer.src = "10.0.0.2"
        ip_layer.dst = "10.0.0.1"
        tcp_layer.sport = 80
        tcp_layer.dport = 1234

        stream_id2 = self.masker._build_stream_id(ip_layer, tcp_layer)
        assert stream_id2 == "10.0.0.1:1234-10.0.0.2:80"  # 应该相同

    def test_determine_flow_direction(self):
        """测试流方向判断"""
        ip_layer = Mock()
        tcp_layer = Mock()

        ip_layer.src = "10.0.0.1"
        ip_layer.dst = "10.0.0.2"
        tcp_layer.sport = 1234
        tcp_layer.dport = 80

        stream_id = "10.0.0.1:1234-10.0.0.2:80"

        # 正向流
        direction = self.masker._determine_flow_direction(
            ip_layer, tcp_layer, stream_id
        )
        assert direction == "forward"

        # 反向流
        ip_layer.src = "10.0.0.2"
        ip_layer.dst = "10.0.0.1"
        tcp_layer.sport = 80
        tcp_layer.dport = 1234

        direction = self.masker._determine_flow_direction(
            ip_layer, tcp_layer, stream_id
        )
        assert direction == "reverse"

    def test_find_innermost_tcp_none_packet(self):
        """测试空数据包"""
        tcp_layer, ip_layer = self.masker._find_innermost_tcp(None)

        assert tcp_layer is None
        assert ip_layer is None

    def test_find_innermost_tcp_no_tcp(self):
        """测试没有TCP层的数据包"""
        packet = Mock()
        packet.haslayer = Mock(return_value=False)
        packet.payload = None

        tcp_layer, ip_layer = self.masker._find_innermost_tcp(packet)

        assert tcp_layer is None
        assert ip_layer is None

    def test_find_innermost_tcp_max_depth(self):
        """测试最大递归深度限制"""
        # 创建深度超过限制的嵌套结构
        packet = Mock()
        current = packet

        for i in range(15):  # 超过最大深度10
            current.haslayer = Mock(return_value=False)
            current.name = f"Layer{i}"
            next_layer = Mock()
            current.payload = next_layer
            current = next_layer

        # 最后一层没有payload
        current.payload = None
        current.haslayer = Mock(return_value=False)

        tcp_layer, ip_layer = self.masker._find_innermost_tcp(packet)

        assert tcp_layer is None
        assert ip_layer is None

    def test_performance_optimization_features(self):
        """测试性能优化功能"""
        # 测试内存优化器集成
        assert hasattr(self.masker, "memory_optimizer")
        assert isinstance(self.masker.memory_optimizer, MemoryOptimizer)

        # 测试性能统计
        stats = self.masker.get_performance_stats()
        assert isinstance(stats, dict)
        assert "max_memory_mb" in stats["config"]

    def test_merge_overlapping_ranges(self):
        """测试重叠区间合并"""
        ranges = [(100, 200), (150, 250), (300, 400), (350, 450)]
        merged = self.masker._merge_overlapping_ranges(ranges)

        # 应该合并为两个区间
        expected = [(100, 250), (300, 450)]
        assert merged == expected

    def test_find_overlapping_ranges_binary_search(self):
        """测试二分查找重叠区间"""
        sorted_ranges = [(100, 200), (300, 400), (500, 600), (700, 800)]

        # 测试完全重叠
        overlapping = self.masker._find_overlapping_ranges(sorted_ranges, 150, 250)
        assert overlapping == [(100, 200)]

        # 测试部分重叠
        overlapping = self.masker._find_overlapping_ranges(sorted_ranges, 250, 350)
        assert overlapping == [(300, 400)]

        # 测试无重叠
        overlapping = self.masker._find_overlapping_ranges(sorted_ranges, 50, 90)
        assert overlapping == []

        # 测试跨多个区间
        overlapping = self.masker._find_overlapping_ranges(sorted_ranges, 250, 550)
        assert overlapping == [(300, 400), (500, 600)]

    def test_optimized_vs_simple_rule_application(self):
        """测试优化算法与简单算法的一致性"""
        payload = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 10  # 260字节

        # 创建大量规则以触发优化算法
        ranges = [(i * 10, i * 10 + 5) for i in range(20)]  # 20个小区间
        rule_data = {
            "keep_set": set(ranges),
            "sorted_ranges": sorted(ranges),
            "range_count": len(ranges),
        }

        # 测试优化算法
        result_optimized = self.masker._apply_keep_rules_optimized(
            payload, 0, 260, rule_data
        )

        # 测试简单算法
        result_simple = self.masker._apply_keep_rules_simple(payload, 0, 260, rule_data)

        # 结果应该一致
        assert result_optimized == result_simple


class TestMemoryOptimizer:
    """测试内存优化器"""

    def setup_method(self):
        """测试前准备"""
        self.config = {
            "max_memory_mb": 100,
            "gc_threshold": 0.8,
            "monitoring_interval": 10,
        }
        self.optimizer = MemoryOptimizer(self.config)

    def test_memory_optimizer_initialization(self):
        """测试内存优化器初始化"""
        assert self.optimizer.max_memory_mb == 100
        assert self.optimizer.gc_threshold == 0.8
        assert self.optimizer.monitoring_interval == 10
        assert self.optimizer.operation_count == 0

    def test_memory_stats(self):
        """测试内存统计"""
        stats = self.optimizer.get_memory_stats()
        assert hasattr(stats, "current_usage")
        assert hasattr(stats, "peak_usage")
        assert hasattr(stats, "gc_collections")
        assert hasattr(stats, "memory_pressure")

    def test_memory_pressure_check(self):
        """测试内存压力检查"""
        # 使用更大的内存限制来避免在测试环境中触发内存压力
        config = {
            "max_memory_mb": 10000,  # 10GB，足够大以避免触发
            "gc_threshold": 0.9,  # 90%阈值
            "monitoring_interval": 5,
        }
        optimizer = MemoryOptimizer(config)

        # 模拟多次操作
        for i in range(10):  # 超过monitoring_interval
            triggered = optimizer.check_memory_pressure()
            # 在正常情况下不应该触发优化
            if i < 5:
                assert not triggered

    def test_memory_callback_registration(self):
        """测试内存回调注册"""
        callback_called = False

        def test_callback(stats):
            nonlocal callback_called
            callback_called = True

        self.optimizer.register_memory_callback(test_callback)
        assert len(self.optimizer.memory_callbacks) == 1

    def test_optimization_report(self):
        """测试优化报告"""
        report = self.optimizer.get_optimization_report()
        assert "current_memory_mb" in report
        assert "peak_memory_mb" in report
        assert "memory_pressure" in report
        assert "config" in report


class TestErrorRecoveryHandler:
    """测试错误恢复处理器"""

    def setup_method(self):
        """测试前准备"""
        self.config = {
            "max_retry_attempts": 2,
            "enable_auto_recovery": True,
            "retry_delay": 0.1,
        }
        self.handler = ErrorRecoveryHandler(self.config)

    def test_error_handler_initialization(self):
        """测试错误处理器初始化"""
        assert self.handler.max_retry_attempts == 2
        assert self.handler.enable_auto_recovery is True
        assert self.handler.total_errors == 0

    def test_handle_error(self):
        """测试错误处理"""
        error_info = self.handler.handle_error(
            "测试错误", ErrorSeverity.MEDIUM, ErrorCategory.PROCESSING_ERROR
        )

        assert error_info.severity == ErrorSeverity.MEDIUM
        assert error_info.category == ErrorCategory.PROCESSING_ERROR
        assert error_info.message == "测试错误"
        assert self.handler.total_errors == 1

    def test_retry_operation_success(self):
        """测试重试操作成功"""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("临时错误")
            return "成功"

        result = self.handler.retry_operation(operation, delay=0.01)
        assert result == "成功"
        assert call_count == 2

    def test_retry_operation_failure(self):
        """测试重试操作失败"""

        def operation():
            raise ValueError("持续错误")

        with pytest.raises(ValueError, match="持续错误"):
            self.handler.retry_operation(operation, max_attempts=2, delay=0.01)


class TestDataValidator:
    """测试数据验证器"""

    def setup_method(self):
        """测试前准备"""
        self.config = {"enable_checksum_validation": True, "max_file_size_mb": 100}
        self.validator = DataValidator(self.config)

    def test_validator_initialization(self):
        """测试验证器初始化"""
        assert self.validator.enable_checksum_validation is True
        assert self.validator.max_file_size_mb == 100

    def test_validate_nonexistent_file(self):
        """测试验证不存在的文件"""
        result = self.validator.validate_input_file("/nonexistent/file.pcap")
        assert not result.is_valid
        assert "不存在" in result.error_message

    def test_validate_processing_state_valid(self):
        """测试验证有效的处理状态"""
        result = self.validator.validate_processing_state(100, 50, 0)
        assert result.is_valid
        assert result.details["processed_packets"] == 100
        assert result.details["modified_packets"] == 50

    def test_validate_processing_state_invalid(self):
        """测试验证无效的处理状态"""
        # 修改包数超过处理包数
        result = self.validator.validate_processing_state(50, 100, 0)
        assert not result.is_valid
        assert "不能超过" in result.error_message


class TestFallbackHandler:
    """测试降级处理器"""

    def setup_method(self):
        """测试前准备"""
        self.config = {
            "enable_fallback": True,
            "default_fallback_mode": FallbackMode.COPY_ORIGINAL.value,
        }
        self.handler = FallbackHandler(self.config)

    def test_fallback_handler_initialization(self):
        """测试降级处理器初始化"""
        assert self.handler.enable_fallback is True
        assert self.handler.default_fallback_mode == FallbackMode.COPY_ORIGINAL

    def test_get_recommended_fallback_mode(self):
        """测试推荐降级模式"""
        # 内存错误
        mode = self.handler.get_recommended_fallback_mode(
            {"error_category": "memory_error"}
        )
        assert mode == FallbackMode.MINIMAL_MASKING

        # 输入错误
        mode = self.handler.get_recommended_fallback_mode(
            {"error_category": "input_error"}
        )
        assert mode == FallbackMode.SKIP_PROCESSING

        # 严重错误
        mode = self.handler.get_recommended_fallback_mode(
            {"error_severity": "critical"}
        )
        assert mode == FallbackMode.SAFE_MODE

    def test_fallback_disabled(self):
        """测试禁用降级处理"""
        config = {"enable_fallback": False}
        handler = FallbackHandler(config)

        result = handler.execute_fallback("/tmp/input", "/tmp/output")
        assert not result.success
        assert "已禁用" in result.message


class TestIntegratedErrorHandling:
    """测试集成的错误处理功能"""

    def setup_method(self):
        """测试前准备"""
        self.config = {
            "chunk_size": 10,
            "verify_checksums": True,
            "error_handler": {"max_retry_attempts": 2, "enable_auto_recovery": True},
            "data_validator": {"enable_checksum_validation": False},  # 避免文件系统依赖
            "fallback_handler": {"enable_fallback": True},
        }
        self.masker = PayloadMasker(self.config)

    def test_integrated_error_handling_features(self):
        """测试集成的错误处理功能"""
        # 测试错误处理器集成
        assert hasattr(self.masker, "error_handler")
        assert isinstance(self.masker.error_handler, ErrorRecoveryHandler)

        # 测试数据验证器集成
        assert hasattr(self.masker, "data_validator")
        assert isinstance(self.masker.data_validator, DataValidator)

        # 测试降级处理器集成
        assert hasattr(self.masker, "fallback_handler")
        assert isinstance(self.masker.fallback_handler, FallbackHandler)

    def test_error_summary_integration(self):
        """测试错误摘要集成"""
        summary = self.masker.get_error_summary()
        assert isinstance(summary, dict)
        assert "total_errors" in summary


if __name__ == "__main__":
    pytest.main([__file__])
