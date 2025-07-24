"""
Next-Generation MaskPayload Stage Main Class Tests

Tests MaskingStage basic functionality and interface compatibility.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from pktmask.core.pipeline.stages.masking_stage.stage import MaskingStage
from pktmask.core.pipeline.models import StageStats


class TestMaskingStage:
    """测试 MaskingStage 主类"""

    def test_stage_creation(self):
        """测试阶段创建"""
        config = {
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "preserve": {"handshake": True, "application_data": False}
            },
            "masker_config": {"chunk_size": 1000, "verify_checksums": True},
        }

        stage = MaskingStage(config)

        assert stage.protocol == "tls"
        assert stage.mode == "enhanced"
        assert stage.marker_config == config["marker_config"]
        assert stage.masker_config == config["masker_config"]
        assert not stage._initialized

    def test_stage_initialization(self):
        """测试阶段初始化"""
        config = {"protocol": "tls", "mode": "enhanced"}

        stage = MaskingStage(config)

        # 初始化应该成功
        assert stage.initialize()
        assert stage._initialized
        assert stage.marker is not None
        assert stage.masker is not None

    def test_unsupported_protocol(self):
        """测试不支持的协议"""
        config = {"protocol": "unsupported", "mode": "enhanced"}

        stage = MaskingStage(config)

        # 初始化应该失败
        assert not stage.initialize()
        assert not stage._initialized

    def test_display_name_and_description(self):
        """测试显示名称和描述"""
        config = {"protocol": "tls", "mode": "enhanced"}
        stage = MaskingStage(config)

        assert stage.get_display_name() == "Mask Payloads (v2)"
        assert "新一代载荷掩码处理器" in stage.get_description()
        assert "tls" in stage.get_description()
        assert "enhanced" in stage.get_description()

    def test_required_tools(self):
        """测试所需工具列表"""
        # TLS协议需要 tshark 和 scapy
        config = {"protocol": "tls"}
        stage = MaskingStage(config)
        tools = stage.get_required_tools()

        assert "scapy" in tools
        assert "tshark" in tools

    def test_cleanup(self):
        """测试资源清理"""
        config = {"protocol": "tls", "mode": "enhanced"}
        stage = MaskingStage(config)

        # 初始化后清理
        stage.initialize()
        assert stage._initialized

        stage.cleanup()
        assert not stage._initialized

    @patch(
        "pktmask.core.pipeline.stages.masking_stage.marker.tls_marker.TLSProtocolMarker"
    )
    @patch(
        "pktmask.core.pipeline.stages.masking_stage.masker.payload_masker.PayloadMasker"
    )
    def test_process_file_integration(self, mock_masker_class, mock_marker_class):
        """测试文件处理集成"""
        # 设置模拟对象
        mock_marker = Mock()
        mock_marker.initialize.return_value = True
        mock_marker.analyze_file.return_value = Mock()  # KeepRuleSet
        mock_marker_class.return_value = mock_marker

        mock_masker = Mock()
        mock_masking_stats = Mock()
        mock_masking_stats.success = True
        mock_masking_stats.processed_packets = 100
        mock_masking_stats.modified_packets = 50
        mock_masking_stats.execution_time = 1.5
        mock_masking_stats.masked_bytes = 5000
        mock_masking_stats.preserved_bytes = 3000
        mock_masking_stats.masking_ratio = 0.625
        mock_masking_stats.preservation_ratio = 0.375
        mock_masking_stats.processing_speed_mbps = 5.0
        mock_masking_stats.errors = []
        mock_masking_stats.warnings = []
        mock_masker.apply_masking.return_value = mock_masking_stats
        mock_masker_class.return_value = mock_masker

        # 创建阶段并初始化
        config = {"protocol": "tls", "mode": "enhanced"}
        stage = MaskingStage(config)
        assert stage.initialize()

        # 模拟文件路径
        input_path = "/tmp/input.pcap"
        output_path = "/tmp/output.pcap"

        # 模拟 validate_inputs 方法
        with patch.object(stage, "validate_inputs"):
            # 处理文件
            stats = stage.process_file(input_path, output_path)

        # 验证调用
        mock_marker.analyze_file.assert_called_once_with(input_path, config)
        mock_masker.apply_masking.assert_called_once()

        # 验证返回的统计信息
        assert isinstance(stats, StageStats)
        assert stats.stage_name == "Mask Payloads (v2)"
        assert stats.packets_processed == 100
        assert stats.packets_modified == 50
        assert stats.duration_ms == 1500  # 1.5s * 1000

        # 验证额外指标
        assert stats.extra_metrics["masked_bytes"] == 5000
        assert stats.extra_metrics["preserved_bytes"] == 3000
        assert stats.extra_metrics["protocol"] == "tls"
        assert stats.extra_metrics["mode"] == "enhanced"
        assert stats.extra_metrics["success"] is True

    def test_process_file_without_initialization(self):
        """测试未初始化时处理文件"""
        config = {"protocol": "tls"}
        stage = MaskingStage(config)

        # 模拟初始化失败
        with patch.object(stage, "initialize", return_value=False):
            # 模拟 validate_inputs 方法以跳过文件存在性检查
            with patch.object(stage, "validate_inputs"):
                # 未初始化时应该抛出异常
                with pytest.raises(RuntimeError, match="未初始化"):
                    stage.process_file("/tmp/input.pcap", "/tmp/output.pcap")

    def test_default_config_values(self):
        """测试默认配置值"""
        # 最小配置
        config = {}
        stage = MaskingStage(config)

        assert stage.protocol == "tls"  # 默认协议
        assert stage.mode == "enhanced"  # 默认模式
        # 默认会填充TLS配置
        assert "tls" in stage.marker_config
        assert "preserve_handshake" in stage.marker_config["tls"]
        # 默认会填充Masker配置
        assert "chunk_size" in stage.masker_config
        assert "verify_checksums" in stage.masker_config
