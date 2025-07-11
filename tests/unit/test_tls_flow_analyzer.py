#!/usr/bin/env python3
"""TLS 流量分析工具单元测试

测试 TLS 流量分析工具的各项功能，包括：
1. 命令行参数解析
2. TLS 消息识别
3. TCP 流分析
4. 输出格式验证
5. 错误处理
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pktmask.tools.tls_flow_analyzer import (
    TLSFlowAnalyzer, 
    _build_arg_parser,
    _apply_type_filter,
    _generate_detailed_message_analysis,
    _get_tls_version_string,
    main,
    TLS_CONTENT_TYPES,
    TLS_PROCESSING_STRATEGIES
)


class TestTLSFlowAnalyzer:
    """TLS 流量分析器测试类"""
    
    def test_init(self):
        """测试分析器初始化"""
        analyzer = TLSFlowAnalyzer(verbose=True)
        assert analyzer.verbose is True
        assert analyzer.tcp_flows == {}
        assert analyzer.tls_messages == []
        assert analyzer.protocol_layers == {}
        assert analyzer.message_statistics == {}
    
    def test_parse_tshark_version(self):
        """测试 tshark 版本解析"""
        analyzer = TLSFlowAnalyzer()
        
        # 正常版本字符串
        version_output = "TShark (Wireshark) 4.2.0 (Git v4.2.0 packaged as 4.2.0-1)"
        version = analyzer._parse_tshark_version(version_output)
        assert version == (4, 2, 0)
        
        # 无效版本字符串
        invalid_output = "Invalid version string"
        version = analyzer._parse_tshark_version(invalid_output)
        assert version is None
    
    def test_get_first_value(self):
        """测试获取第一个值的辅助函数"""
        analyzer = TLSFlowAnalyzer()
        
        # 测试列表
        assert analyzer._get_first_value([1, 2, 3]) == 1
        assert analyzer._get_first_value([]) is None
        
        # 测试单值
        assert analyzer._get_first_value("test") == "test"
        assert analyzer._get_first_value(None) is None
    
    def test_has_tls_content(self):
        """测试 TLS 内容检测"""
        analyzer = TLSFlowAnalyzer()
        
        # 包含 TLS 内容的层
        layers_with_tls = {
            "tls.record.content_type": ["22", "23"],
            "tls.record.opaque_type": []
        }
        assert analyzer._has_tls_content(layers_with_tls) is True
        
        # 不包含 TLS 内容的层
        layers_without_tls = {
            "tcp.payload": "deadbeef"
        }
        assert analyzer._has_tls_content(layers_without_tls) is False
        
        # 包含无效 TLS 类型的层
        layers_invalid_tls = {
            "tls.record.content_type": ["99"],  # 无效类型
        }
        assert analyzer._has_tls_content(layers_invalid_tls) is False


class TestCommandLineInterface:
    """命令行接口测试类"""
    
    def test_arg_parser_creation(self):
        """测试参数解析器创建"""
        parser = _build_arg_parser()
        assert parser.prog == "tls_flow_analyzer"
        assert "TLS 流量分析工具" in parser.description
    
    def test_required_arguments(self):
        """测试必需参数"""
        parser = _build_arg_parser()
        
        # 缺少必需参数应该失败
        with pytest.raises(SystemExit):
            parser.parse_args([])
        
        # 提供必需参数应该成功
        args = parser.parse_args(["--pcap", "test.pcap"])
        assert args.pcap == "test.pcap"
    
    def test_optional_arguments(self):
        """测试可选参数"""
        parser = _build_arg_parser()
        args = parser.parse_args([
            "--pcap", "test.pcap",
            "--decode-as", "8443,tls",
            "--formats", "json",
            "--detailed",
            "--verbose",
            "--filter-types", "22,23",
            "--summary-only"
        ])
        
        assert args.pcap == "test.pcap"
        assert args.decode_as == ["8443,tls"]
        assert args.formats == "json"
        assert args.detailed is True
        assert args.verbose is True
        assert args.filter_types == "22,23"
        assert args.summary_only is True


class TestUtilityFunctions:
    """工具函数测试类"""
    
    def test_get_tls_version_string(self):
        """测试 TLS 版本字符串生成"""
        assert _get_tls_version_string((3, 0)) == "SSL 3.0"
        assert _get_tls_version_string((3, 1)) == "TLS 1.0"
        assert _get_tls_version_string((3, 2)) == "TLS 1.1"
        assert _get_tls_version_string((3, 3)) == "TLS 1.2"
        assert _get_tls_version_string((3, 4)) == "TLS 1.3"
        assert _get_tls_version_string((4, 0)) == "TLS 4.0"
    
    def test_apply_type_filter(self):
        """测试协议类型过滤"""
        # 创建测试数据
        analysis_result = {
            "detailed_frames": [
                {"frame": 1, "protocol_types": [22, 23]},
                {"frame": 2, "protocol_types": [20]},
                {"frame": 3, "protocol_types": [22]}
            ],
            "protocol_type_statistics": {
                20: {"frames": 1, "records": 0},
                22: {"frames": 2, "records": 0},
                23: {"frames": 1, "records": 0}
            },
            "reassembled_messages": [
                {"content_type": 22},
                {"content_type": 23}
            ],
            "global_statistics": {
                "frames_containing_tls": 3,
                "tls_records_total": 2
            },
            "metadata": {
                "total_frames_with_tls": 3,
                "total_tls_records": 2
            }
        }
        
        # 过滤只保留 TLS-22 和 TLS-23
        filter_types = {22, 23}
        filtered_result = _apply_type_filter(analysis_result, filter_types)
        
        # 验证过滤结果
        # 帧 1 包含 [22, 23]，帧 2 包含 [20]（被过滤掉），帧 3 包含 [22]
        # 所以应该有 2 个帧通过过滤
        assert len(filtered_result["detailed_frames"]) == 2  # 帧 1 和帧 3 包含 22 或 23
        assert 20 not in filtered_result["protocol_type_statistics"]
        assert 22 in filtered_result["protocol_type_statistics"]
        assert 23 in filtered_result["protocol_type_statistics"]
        assert len(filtered_result["reassembled_messages"]) == 2
    
    def test_generate_detailed_message_analysis(self):
        """测试详细消息分析生成"""
        analysis_result = {
            "reassembled_messages": [
                {
                    "stream_id": "0",
                    "direction": "forward",
                    "content_type": 22,
                    "content_type_name": "Handshake",
                    "version": (3, 3),
                    "header_start": 0,
                    "header_end": 5,
                    "payload_start": 5,
                    "payload_end": 100,
                    "length": 95,
                    "is_complete": True,
                    "is_cross_segment": False,
                    "processing_strategy": "keep_all"
                }
            ],
            "tcp_flow_analysis": {
                "0": {
                    "packet_count": 5,
                    "directions": {
                        "forward": {
                            "src_ip": "10.0.0.1",
                            "dst_ip": "10.0.0.2",
                            "src_port": "12345",
                            "dst_port": "443",
                            "packet_count": 3,
                            "payload_size": 200
                        },
                        "reverse": {
                            "src_ip": "10.0.0.2",
                            "dst_ip": "10.0.0.1",
                            "src_port": "443",
                            "dst_port": "12345",
                            "packet_count": 2,
                            "payload_size": 150
                        }
                    }
                }
            }
        }
        
        detailed_analysis = _generate_detailed_message_analysis(analysis_result)
        
        assert "message_structure_analysis" in detailed_analysis
        assert "cross_segment_analysis" in detailed_analysis
        assert "sequence_analysis" in detailed_analysis
        
        # 验证消息结构分析
        msg_analysis = detailed_analysis["message_structure_analysis"][0]
        assert msg_analysis["content_type"] == 22
        assert msg_analysis["version_string"] == "TLS 1.2"
        assert msg_analysis["header_info"]["length"] == 5
        assert msg_analysis["payload_info"]["length"] == 95


class TestIntegration:
    """集成测试类"""
    
    @patch('pktmask.tools.tls_flow_analyzer.subprocess.run')
    def test_main_function_success(self, mock_subprocess):
        """测试主函数成功执行"""
        # 模拟 tshark 版本检查
        mock_subprocess.return_value.stdout = "TShark (Wireshark) 4.2.0"
        mock_subprocess.return_value.stderr = ""
        
        # 模拟 tshark JSON 输出
        mock_tshark_output = json.dumps([
            {
                "_source": {
                    "layers": {
                        "frame.number": "1",
                        "frame.protocols": "eth:ethertype:ip:tcp:tls",
                        "tls.record.content_type": ["22"]
                    }
                }
            }
        ])
        
        # 设置不同的返回值
        mock_subprocess.side_effect = [
            Mock(stdout="TShark (Wireshark) 4.2.0", stderr=""),  # 版本检查
            Mock(stdout=mock_tshark_output, stderr=""),  # 第一阶段扫描
            Mock(stdout="[]", stderr="")  # TCP 流分析
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_pcap = Path(temp_dir) / "test.pcap"
            test_pcap.touch()  # 创建空文件
            
            # 测试 summary-only 模式
            main([
                "--pcap", str(test_pcap),
                "--summary-only"
            ])
    
    def test_main_function_invalid_filter_types(self):
        """测试主函数处理无效过滤类型"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_pcap = Path(temp_dir) / "test.pcap"
            test_pcap.touch()
            
            with pytest.raises(SystemExit):
                main([
                    "--pcap", str(test_pcap),
                    "--filter-types", "99,100"  # 无效的 TLS 类型
                ])


@pytest.mark.unit
class TestConstants:
    """常量测试类"""
    
    def test_tls_content_types(self):
        """测试 TLS 内容类型常量"""
        assert TLS_CONTENT_TYPES[20] == "ChangeCipherSpec"
        assert TLS_CONTENT_TYPES[21] == "Alert"
        assert TLS_CONTENT_TYPES[22] == "Handshake"
        assert TLS_CONTENT_TYPES[23] == "ApplicationData"
        assert TLS_CONTENT_TYPES[24] == "Heartbeat"
    
    def test_tls_processing_strategies(self):
        """测试 TLS 处理策略常量"""
        assert TLS_PROCESSING_STRATEGIES[20] == "keep_all"
        assert TLS_PROCESSING_STRATEGIES[21] == "keep_all"
        assert TLS_PROCESSING_STRATEGIES[22] == "keep_all"
        assert TLS_PROCESSING_STRATEGIES[23] == "mask_payload"
        assert TLS_PROCESSING_STRATEGIES[24] == "keep_all"


if __name__ == "__main__":
    pytest.main([__file__])
