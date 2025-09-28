"""
TLS协议标记器测试

测试TLS协议标记器的核心功能，包括TLS消息识别、流方向分析和保留规则生成。
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pktmask.core.pipeline.stages.masking_stage.marker.tls_marker import (
    TLSProtocolMarker,
)
from pktmask.core.pipeline.stages.masking_stage.marker.types import (
    KeepRule,
    KeepRuleSet,
)


class TestTLSProtocolMarker:
    """测试TLS协议标记器"""

    def test_marker_creation(self):
        """测试标记器创建"""
        config = {
            "preserve": {"handshake": True, "application_data": False, "alert": True},
            "tshark_path": "/usr/bin/tshark",
        }

        marker = TLSProtocolMarker(config)

        assert marker.preserve_config == config["preserve"]
        assert marker.tshark_path == "/usr/bin/tshark"
        assert marker.get_supported_protocols() == ["tls", "ssl"]

    def test_config_validation(self):
        """测试配置验证"""
        marker = TLSProtocolMarker({})

        # 有效配置
        valid_config = {"preserve": {"handshake": True, "application_data": False}}
        errors = marker.validate_config(valid_config)
        assert len(errors) == 0

        # 无效配置 - preserve不是字典
        invalid_config1 = {"preserve": "invalid"}
        errors = marker.validate_config(invalid_config1)
        assert len(errors) > 0
        assert "preserve配置必须是字典类型" in errors[0]

        # 无效配置 - 未知TLS类型
        invalid_config2 = {"preserve": {"unknown_type": True}}
        errors = marker.validate_config(invalid_config2)
        assert len(errors) > 0
        assert "未知的TLS消息类型" in errors[0]

    @patch("subprocess.run")
    def test_tshark_version_check(self, mock_run):
        """测试tshark版本检查"""
        # 模拟tshark版本输出
        mock_run.return_value.stdout = "TShark (Wireshark) 4.2.0"
        mock_run.return_value.stderr = ""

        marker = TLSProtocolMarker({"tshark_path": "/usr/bin/tshark"})

        # 应该成功检查版本
        tshark_exec = marker._check_tshark_version("/usr/bin/tshark")
        assert tshark_exec == "/usr/bin/tshark"

        # 测试版本过低的情况
        mock_run.return_value.stdout = "TShark (Wireshark) 3.0.0"

        with pytest.raises(RuntimeError, match="tshark 版本过低"):
            marker._check_tshark_version("/usr/bin/tshark")

    def test_tls_content_detection(self):
        """测试TLS内容检测"""
        marker = TLSProtocolMarker({})

        # 包含TLS内容的层
        layers_with_tls = {
            "tls.record.content_type": ["22", "23"],
            "tls.record.length": ["100", "200"],
        }
        assert marker._has_tls_content(layers_with_tls) is True

        # 不包含TLS内容的层
        layers_without_tls = {"tcp.payload": "deadbeef", "ip.src": "192.168.1.1"}
        assert marker._has_tls_content(layers_without_tls) is False

        # 包含无效TLS类型的层
        layers_invalid_tls = {
            "tls.record.content_type": ["99"],  # 无效类型
        }
        assert marker._has_tls_content(layers_invalid_tls) is False

    def test_flow_direction_identification(self):
        """测试流方向识别"""
        marker = TLSProtocolMarker({})

        # 模拟数据包
        packets = [
            {
                "_source": {
                    "layers": {
                        "ip.src": "192.168.1.1",
                        "ip.dst": "192.168.1.2",
                        "tcp.srcport": "12345",
                        "tcp.dstport": "443",
                    }
                }
            },
            {
                "_source": {
                    "layers": {
                        "ip.src": "192.168.1.2",
                        "ip.dst": "192.168.1.1",
                        "tcp.srcport": "443",
                        "tcp.dstport": "12345",
                    }
                }
            },
        ]

        directions = marker._identify_flow_directions(packets)

        # 验证正向流
        assert directions["forward"]["src_ip"] == "192.168.1.1"
        assert directions["forward"]["dst_ip"] == "192.168.1.2"
        assert directions["forward"]["src_port"] == "12345"
        assert directions["forward"]["dst_port"] == "443"
        assert len(directions["forward"]["packets"]) == 1

        # 验证反向流
        assert directions["reverse"]["src_ip"] == "192.168.1.2"
        assert directions["reverse"]["dst_ip"] == "192.168.1.1"
        assert directions["reverse"]["src_port"] == "443"
        assert directions["reverse"]["dst_port"] == "12345"
        assert len(directions["reverse"]["packets"]) == 1

    def test_tls_type_preservation_logic(self):
        """测试TLS类型保留逻辑"""
        config = {
            "preserve": {
                "handshake": True,
                "application_data": False,
                "alert": True,
                "change_cipher_spec": True,
                "heartbeat": True,
            }
        }
        marker = TLSProtocolMarker(config)

        # 测试各种TLS类型
        assert marker._should_preserve_tls_type(20) is True  # ChangeCipherSpec
        assert marker._should_preserve_tls_type(21) is True  # Alert
        assert marker._should_preserve_tls_type(22) is True  # Handshake
        assert marker._should_preserve_tls_type(23) is False  # ApplicationData
        assert marker._should_preserve_tls_type(24) is True  # Heartbeat
        assert marker._should_preserve_tls_type(99) is True  # 未知类型，默认保留

    def test_logical_sequence_number_handling(self):
        """测试逻辑序列号处理"""
        marker = TLSProtocolMarker({})

        flow_key = "stream_1_forward"

        # 正常序列号
        seq1 = marker._logical_seq(1000, flow_key)
        seq2 = marker._logical_seq(1500, flow_key)
        assert seq2 > seq1

        # 序列号回绕
        seq3 = marker._logical_seq(0xFFFFFFFE, flow_key)
        seq4 = marker._logical_seq(0x00000001, flow_key)  # 回绕后
        assert seq4 > seq3  # 逻辑序号应该继续递增

        # 验证epoch增加
        assert seq4 >> 32 == 1  # 第二个epoch

    def test_keep_rule_creation(self):
        """测试保留规则创建"""
        marker = TLSProtocolMarker({})

        # 创建保留规则
        rule = marker._create_keep_rule(
            stream_id="1",
            direction="forward",
            tcp_seq=1000,
            tcp_len=100,
            tls_type=22,  # Handshake
            frame_number=5,
        )

        assert rule is not None
        assert rule.stream_id == "1"
        assert rule.direction == "forward"
        assert rule.seq_start == 1000  # 第一次调用，epoch=0
        assert rule.seq_end == 1100
        assert rule.rule_type == "tls_handshake"
        assert rule.metadata["tls_content_type"] == 22
        assert rule.metadata["frame_number"] == 5

    @patch("subprocess.run")
    def test_analyze_file_error_handling(self, mock_run):
        """测试文件分析错误处理"""
        # 模拟tshark执行失败
        mock_run.side_effect = subprocess.CalledProcessError(1, "tshark")

        marker = TLSProtocolMarker({"tshark_path": "/usr/bin/tshark"})
        marker.tshark_exec = "/usr/bin/tshark"  # 跳过版本检查

        # 分析应该返回空规则集而不是抛出异常
        ruleset = marker.analyze_file("/nonexistent/file.pcap", {})

        assert isinstance(ruleset, KeepRuleSet)
        assert len(ruleset.rules) == 0
        assert ruleset.metadata.get("analysis_failed") is True
        assert "error" in ruleset.metadata
