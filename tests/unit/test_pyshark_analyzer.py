#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyShark分析器测试

测试PyShark分析器的各种功能和场景，包括：
- 协议识别和解析验证
- 流信息提取测试
- 掩码表生成验证
- HTTP和TLS协议处理
- 内存使用优化验证
"""

import pytest
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from src.pktmask.core.trim.stages.pyshark_analyzer import PySharkAnalyzer, StreamInfo, PacketAnalysis
from src.pktmask.core.trim.stages.base_stage import StageContext
from src.pktmask.core.processors.base_processor import ProcessorResult
from src.pktmask.core.trim.models.mask_table import StreamMaskTable
from src.pktmask.core.trim.models.mask_spec import MaskAfter, KeepAll


# Mock PyShark objects for testing
class MockPacket:
    """Mock PyShark数据包对象"""
    def __init__(self, number, timestamp, has_tcp=False, has_udp=False, has_http=False, has_tls=False):
        self.number = number
        self.sniff_timestamp = timestamp
        
        if has_tcp:
            self.tcp = MockTCPLayer()
            self.ip = MockIPLayer()
        
        if has_udp:
            self.udp = MockUDPLayer()
            self.ip = MockIPLayer()
        
        if has_http:
            self.http = MockHTTPLayer()
        
        if has_tls:
            self.tls = MockTLSLayer()

class MockTCPLayer:
    """Mock TCP层"""
    def __init__(self):
        self.srcport = 80
        self.dstport = 12345
        self.seq = 1000
        self.len = 100
        self.hdr_len = 20

class MockUDPLayer:
    """Mock UDP层"""
    def __init__(self):
        self.srcport = 53
        self.dstport = 54321
        self.length = 64

class MockIPLayer:
    """Mock IP层"""
    def __init__(self):
        self.src = "192.168.1.1"
        self.dst = "192.168.1.100"

class MockHTTPLayer:
    """Mock HTTP层"""
    def __init__(self, is_request=True):
        if is_request:
            self.request_method = "GET"
            self.request_full_uri = "http://example.com/path"
            self.request_line = "GET /path HTTP/1.1"
        else:
            self.response_code = "200"
            self.response_line = "HTTP/1.1 200 OK"
        
        self._all_fields = {
            'http.host': 'example.com',
            'http.user_agent': 'TestAgent/1.0'
        }

class MockTLSLayer:
    """Mock TLS层"""
    def __init__(self, content_type=22):
        self.content_type = content_type
        self._all_fields = {
            'tls.record': {
                'tls.record.content_type': str(content_type),
                'tls.record.length': '100'
            }
        }

class MockFileCapture:
    """Mock PyShark文件捕获对象"""
    def __init__(self, packets):
        self.packets = packets
        self._index = 0
    
    def __iter__(self):
        return iter(self.packets)
    
    def close(self):
        pass


class TestPySharkAnalyzer:
    """PyShark分析器测试类"""
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录fixture"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_pcap(self, temp_dir):
        """示例PCAP文件fixture"""
        pcap_file = temp_dir / "sample.pcap"
        # 创建一个最小的PCAP文件
        with open(pcap_file, 'wb') as f:
            # PCAP Global Header
            f.write(b'\xd4\xc3\xb2\xa1')  # Magic number
            f.write(b'\x02\x00\x04\x00')  # Version major/minor
            f.write(b'\x00\x00\x00\x00')  # Timezone offset
            f.write(b'\x00\x00\x00\x00')  # Timestamp accuracy
            f.write(b'\xff\xff\x00\x00')  # Max packet length
            f.write(b'\x01\x00\x00\x00')  # Data link type (Ethernet)
        
        return pcap_file
    
    @pytest.fixture
    def stage_context(self, temp_dir, sample_pcap):
        """Stage上下文fixture"""
        context = StageContext(
            input_file=sample_pcap,
            output_file=temp_dir / "output.pcap",
            work_dir=temp_dir / "work"
        )
        context.tshark_output = str(sample_pcap)
        return context
    
    @pytest.fixture
    def analyzer_config(self):
        """分析器配置fixture"""
        return {
            'analyze_http': True,
            'analyze_tls': True,
            'analyze_tcp': True,
            'analyze_udp': True,
            'http_keep_headers': True,
            'http_mask_body': True,
            'tls_keep_handshake': True,
            'tls_mask_application_data': True,
            'max_packets_per_batch': 1000,
            'memory_cleanup_interval': 5000,
            'analysis_timeout_seconds': 600
        }
    
    def test_init_default_config(self):
        """测试默认配置初始化"""
        analyzer = PySharkAnalyzer()
        
        assert analyzer.name == "PyShark分析器"
        assert analyzer._analyze_http is True
        assert analyzer._analyze_tls is True
        assert analyzer._analyze_tcp is True
        assert analyzer._analyze_udp is True
        assert analyzer._http_keep_headers is True
        assert analyzer._http_mask_body is True
        assert analyzer._tls_keep_handshake is True
        assert analyzer._tls_mask_application_data is True
        assert len(analyzer._streams) == 0
        assert len(analyzer._packet_analyses) == 0
        assert analyzer._mask_table is None
    
    def test_init_custom_config(self, analyzer_config):
        """测试自定义配置初始化"""
        analyzer = PySharkAnalyzer(analyzer_config)
        
        assert analyzer._analyze_http is True
        assert analyzer._analyze_tls is True
        assert analyzer._max_packets_per_batch == 1000
        assert analyzer._memory_cleanup_interval == 5000
        assert analyzer._timeout_seconds == 600
    
    @patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark')
    def test_initialize_impl_success(self, mock_pyshark):
        """测试成功初始化"""
        mock_pyshark.__version__ = "0.4.5"
        
        analyzer = PySharkAnalyzer()
        analyzer._initialize_impl()
        
        assert len(analyzer._streams) == 0
        assert len(analyzer._packet_analyses) == 0
        assert analyzer._mask_table is None
    
    def test_initialize_impl_no_pyshark(self):
        """测试PyShark未安装的情况"""
        with patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark', None):
            analyzer = PySharkAnalyzer()
            
            with pytest.raises(RuntimeError, match="PyShark未安装"):
                analyzer._initialize_impl()
    
    def test_validate_inputs_success(self, stage_context):
        """测试输入验证成功"""
        analyzer = PySharkAnalyzer()
        analyzer._is_initialized = True
        
        result = analyzer.validate_inputs(stage_context)
        
        assert result is True
    
    def test_validate_inputs_no_tshark_output(self, stage_context):
        """测试缺少TShark输出文件"""
        stage_context.tshark_output = None
        analyzer = PySharkAnalyzer()
        analyzer._is_initialized = True
        
        result = analyzer.validate_inputs(stage_context)
        
        assert result is False
    
    def test_validate_inputs_nonexistent_file(self, stage_context):
        """测试TShark输出文件不存在"""
        stage_context.tshark_output = "/nonexistent/file.pcap"
        analyzer = PySharkAnalyzer()
        analyzer._is_initialized = True
        
        result = analyzer.validate_inputs(stage_context)
        
        assert result is False
    
    def test_validate_inputs_empty_file(self, temp_dir, stage_context):
        """测试空TShark输出文件"""
        empty_file = temp_dir / "empty.pcap"
        empty_file.touch()
        stage_context.tshark_output = str(empty_file)
        
        analyzer = PySharkAnalyzer()
        analyzer._is_initialized = True
        
        result = analyzer.validate_inputs(stage_context)
        
        assert result is False
    
    def test_validate_inputs_not_initialized(self, stage_context):
        """测试分析器未初始化"""
        analyzer = PySharkAnalyzer()
        analyzer._is_initialized = False
        
        result = analyzer.validate_inputs(stage_context)
        
        assert result is False
    
    @patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark')
    def test_open_pcap_file_success(self, mock_pyshark, sample_pcap):
        """测试成功打开PCAP文件"""
        mock_capture = Mock()
        mock_pyshark.FileCapture.return_value = mock_capture
        
        analyzer = PySharkAnalyzer()
        result = analyzer._open_pcap_file(sample_pcap)
        
        assert result == mock_capture
        mock_pyshark.FileCapture.assert_called_once_with(
            str(sample_pcap),
            keep_packets=False,
            use_json=True,
            include_raw=False
        )
    
    @patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark')
    def test_open_pcap_file_failure(self, mock_pyshark, sample_pcap):
        """测试打开PCAP文件失败"""
        mock_pyshark.FileCapture.side_effect = Exception("File open error")
        
        analyzer = PySharkAnalyzer()
        
        with pytest.raises(RuntimeError, match="打开PCAP文件失败"):
            analyzer._open_pcap_file(sample_pcap)
    
    def test_generate_stream_id(self):
        """测试流ID生成"""
        analyzer = PySharkAnalyzer()
        
        # 测试正序
        stream_id1 = analyzer._generate_stream_id("192.168.1.1", "192.168.1.100", 80, 12345, "TCP")
        assert stream_id1 == "TCP_192.168.1.1:80_192.168.1.100:12345"
        
        # 测试逆序（应该产生相同的流ID）
        stream_id2 = analyzer._generate_stream_id("192.168.1.100", "192.168.1.1", 12345, 80, "TCP")
        assert stream_id2 == "TCP_192.168.1.1:80_192.168.1.100:12345"
        
        assert stream_id1 == stream_id2
    
    def test_analyze_tcp_packet(self):
        """测试TCP数据包分析"""
        analyzer = PySharkAnalyzer()
        packet = MockPacket(1, 1234567890.0, has_tcp=True)
        
        result = analyzer._analyze_tcp_packet(packet, 1, 1234567890.0)
        
        assert result is not None
        assert result.packet_number == 1
        assert result.timestamp == 1234567890.0
        assert result.stream_id == "TCP_192.168.1.1:80_192.168.1.100:12345"
        assert result.seq_number == 1000
        assert result.payload_length == 80  # 100 - 20 (header)
    
    def test_analyze_udp_packet(self):
        """测试UDP数据包分析"""
        analyzer = PySharkAnalyzer()
        packet = MockPacket(2, 1234567891.0, has_udp=True)
        
        result = analyzer._analyze_udp_packet(packet, 2, 1234567891.0)
        
        assert result is not None
        assert result.packet_number == 2
        assert result.timestamp == 1234567891.0
        assert result.stream_id == "UDP_192.168.1.1:53_192.168.1.100:54321"
        assert result.seq_number is None  # UDP没有序列号
        assert result.payload_length == 56  # 64 - 8 (UDP header)
    
    def test_analyze_http_layer_request(self):
        """测试HTTP请求层分析"""
        analyzer = PySharkAnalyzer()
        packet = MockPacket(1, 1234567890.0, has_tcp=True, has_http=True)
        packet.http = MockHTTPLayer(is_request=True)
        
        analysis = PacketAnalysis(1, 1234567890.0, "test_stream")
        analyzer._analyze_http_layer(packet.http, analysis)
        
        assert analysis.application_layer == 'HTTP'
        assert analysis.is_http_request is True
        assert analysis.is_http_response is False
        assert analysis.http_header_length is not None
        assert analysis.http_header_length > 0
    
    def test_analyze_http_layer_response(self):
        """测试HTTP响应层分析"""
        analyzer = PySharkAnalyzer()
        packet = MockPacket(1, 1234567890.0, has_tcp=True, has_http=True)
        packet.http = MockHTTPLayer(is_request=False)
        
        analysis = PacketAnalysis(1, 1234567890.0, "test_stream")
        analyzer._analyze_http_layer(packet.http, analysis)
        
        assert analysis.application_layer == 'HTTP'
        assert analysis.is_http_request is False
        assert analysis.is_http_response is True
        assert analysis.http_header_length is not None
        assert analysis.http_header_length > 0
    
    def test_analyze_tls_layer_handshake(self):
        """测试TLS握手层分析"""
        analyzer = PySharkAnalyzer()
        packet = MockPacket(1, 1234567890.0, has_tcp=True, has_tls=True)
        packet.tls = MockTLSLayer(content_type=22)  # Handshake
        
        analysis = PacketAnalysis(1, 1234567890.0, "test_stream")
        analyzer._analyze_tls_layer(packet.tls, analysis)
        
        assert analysis.application_layer == 'TLS'
        assert analysis.is_tls_handshake is True
        assert analysis.is_tls_application_data is False
        assert analysis.is_tls_change_cipher_spec is False
        assert analysis.is_tls_alert is False
        assert analysis.is_tls_heartbeat is False
        assert analysis.tls_content_type == 22
        assert analysis.tls_record_length == 105  # 5 + 100
    
    def test_analyze_tls_layer_application_data(self):
        """测试TLS应用数据层分析"""
        analyzer = PySharkAnalyzer()
        packet = MockPacket(1, 1234567890.0, has_tcp=True, has_tls=True)
        packet.tls = MockTLSLayer(content_type=23)  # Application Data
        
        analysis = PacketAnalysis(1, 1234567890.0, "test_stream")
        analyzer._analyze_tls_layer(packet.tls, analysis)
        
        assert analysis.application_layer == 'TLS'
        assert analysis.is_tls_handshake is False
        assert analysis.is_tls_application_data is True
        assert analysis.is_tls_change_cipher_spec is False
        assert analysis.is_tls_alert is False
        assert analysis.is_tls_heartbeat is False
        assert analysis.tls_content_type == 23
        assert analysis.tls_record_length == 105  # 5 + 100

    def test_analyze_tls_layer_change_cipher_spec(self):
        """测试TLS ChangeCipherSpec层分析"""
        analyzer = PySharkAnalyzer()
        packet = MockPacket(1, 1234567890.0, has_tcp=True, has_tls=True)
        packet.tls = MockTLSLayer(content_type=20)  # ChangeCipherSpec
        
        analysis = PacketAnalysis(1, 1234567890.0, "test_stream")
        analyzer._analyze_tls_layer(packet.tls, analysis)
        
        assert analysis.application_layer == 'TLS'
        assert analysis.is_tls_change_cipher_spec is True
        assert analysis.is_tls_handshake is False
        assert analysis.is_tls_application_data is False
        assert analysis.tls_content_type == 20
        assert analysis.tls_record_length == 105  # 5 + 100

    def test_analyze_tls_layer_alert(self):
        """测试TLS Alert层分析"""
        analyzer = PySharkAnalyzer()
        packet = MockPacket(1, 1234567890.0, has_tcp=True, has_tls=True)
        packet.tls = MockTLSLayer(content_type=21)  # Alert
        
        analysis = PacketAnalysis(1, 1234567890.0, "test_stream")
        analyzer._analyze_tls_layer(packet.tls, analysis)
        
        assert analysis.application_layer == 'TLS'
        assert analysis.is_tls_alert is True
        assert analysis.is_tls_handshake is False
        assert analysis.is_tls_application_data is False
        assert analysis.tls_content_type == 21
        assert analysis.tls_record_length == 105  # 5 + 100

    def test_analyze_tls_layer_heartbeat(self):
        """测试TLS Heartbeat层分析"""
        analyzer = PySharkAnalyzer()
        packet = MockPacket(1, 1234567890.0, has_tcp=True, has_tls=True)
        packet.tls = MockTLSLayer(content_type=24)  # Heartbeat
        
        analysis = PacketAnalysis(1, 1234567890.0, "test_stream")
        analyzer._analyze_tls_layer(packet.tls, analysis)
        
        assert analysis.application_layer == 'TLS'
        assert analysis.is_tls_heartbeat is True
        assert analysis.is_tls_handshake is False
        assert analysis.is_tls_application_data is False
        assert analysis.tls_content_type == 24
        assert analysis.tls_record_length == 105  # 5 + 100

    def test_analyze_tls_layer_unknown_content_type(self):
        """测试未知TLS content type分析"""
        analyzer = PySharkAnalyzer()
        packet = MockPacket(1, 1234567890.0, has_tcp=True, has_tls=True)
        packet.tls = MockTLSLayer(content_type=99)  # Unknown type
        
        analysis = PacketAnalysis(1, 1234567890.0, "test_stream")
        analyzer._analyze_tls_layer(packet.tls, analysis)
        
        assert analysis.application_layer == 'TLS'
        assert analysis.is_tls_handshake is False
        assert analysis.is_tls_application_data is False
        assert analysis.is_tls_change_cipher_spec is False
        assert analysis.is_tls_alert is False
        assert analysis.is_tls_heartbeat is False
        assert analysis.tls_content_type == 99
    
    def test_update_stream_info_new_stream(self):
        """测试更新新流信息"""
        analyzer = PySharkAnalyzer()
        analysis = PacketAnalysis(
            packet_number=1,
            timestamp=1234567890.0,
            stream_id="TCP_192.168.1.1:80_192.168.1.100:12345",
            payload_length=100,
            application_layer='HTTP'
        )
        
        analyzer._update_stream_info(analysis)
        
        assert len(analyzer._streams) == 1
        stream_info = analyzer._streams["TCP_192.168.1.1:80_192.168.1.100:12345"]
        assert stream_info.src_ip == "192.168.1.1"
        assert stream_info.dst_ip == "192.168.1.100"
        assert stream_info.src_port == 80
        assert stream_info.dst_port == 12345
        assert stream_info.protocol == "TCP"
        assert stream_info.application_protocol == "HTTP"
        assert stream_info.packet_count == 1
        assert stream_info.total_bytes == 100
        assert stream_info.first_seen == 1234567890.0
        assert stream_info.last_seen == 1234567890.0
    
    def test_update_stream_info_existing_stream(self):
        """测试更新现有流信息"""
        analyzer = PySharkAnalyzer()
        
        # 第一个数据包
        analysis1 = PacketAnalysis(
            packet_number=1,
            timestamp=1234567890.0,
            stream_id="TCP_192.168.1.1:80_192.168.1.100:12345",
            payload_length=100,
            application_layer='HTTP'
        )
        analyzer._update_stream_info(analysis1)
        
        # 第二个数据包
        analysis2 = PacketAnalysis(
            packet_number=2,
            timestamp=1234567891.0,
            stream_id="TCP_192.168.1.1:80_192.168.1.100:12345",
            payload_length=150
        )
        analyzer._update_stream_info(analysis2)
        
        assert len(analyzer._streams) == 1
        stream_info = analyzer._streams["TCP_192.168.1.1:80_192.168.1.100:12345"]
        assert stream_info.packet_count == 2
        assert stream_info.total_bytes == 250
        assert stream_info.first_seen == 1234567890.0
        assert stream_info.last_seen == 1234567891.0
    
    def test_analyze_packets(self):
        """测试数据包分析"""
        analyzer = PySharkAnalyzer()
        
        # 创建模拟数据包
        packets = [
            MockPacket(1, 1234567890.0, has_tcp=True, has_http=True),
            MockPacket(2, 1234567891.0, has_tcp=True, has_tls=True),
            MockPacket(3, 1234567892.0, has_udp=True)
        ]
        
        mock_cap = MockFileCapture(packets)
        
        progress_callback = Mock()
        packet_count = analyzer._analyze_packets(mock_cap, progress_callback)
        
        assert packet_count == 3
        assert len(analyzer._packet_analyses) == 3
        assert len(analyzer._streams) > 0
        progress_callback.assert_called()
    
    def test_generate_mask_table_http(self):
        """测试HTTP掩码表生成"""
        analyzer = PySharkAnalyzer()
        analyzer._http_keep_headers = True
        analyzer._http_mask_body = True
        
        # 添加流信息
        stream_id = "TCP_192.168.1.1:80_192.168.1.100:12345"
        analyzer._streams[stream_id] = StreamInfo(
            stream_id=stream_id,
            src_ip="192.168.1.1",
            dst_ip="192.168.1.100",
            src_port=80,
            dst_port=12345,
            protocol="TCP",
            application_protocol="HTTP"
        )
        
        # 添加数据包分析结果
        analyzer._packet_analyses = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id=stream_id,
                seq_number=1000,
                payload_length=200,
                application_layer='HTTP',
                is_http_request=True,
                http_header_length=80
            )
        ]
        
        mask_table = analyzer._generate_mask_table()
        
        assert mask_table is not None
        assert mask_table.get_total_entry_count() > 0
        
        # 验证掩码规范
        mask_spec = mask_table.lookup(stream_id, 1000, 200)
        assert mask_spec is not None
        assert isinstance(mask_spec, MaskAfter)
        assert mask_spec.keep_bytes == 80
    
    def test_generate_mask_table_tls(self):
        """测试TLS掩码表生成"""
        analyzer = PySharkAnalyzer()
        analyzer._tls_keep_handshake = True
        analyzer._tls_mask_application_data = True
        
        # 添加流信息
        stream_id = "TCP_192.168.1.1:443_192.168.1.100:12345"
        analyzer._streams[stream_id] = StreamInfo(
            stream_id=stream_id,
            src_ip="192.168.1.1",
            dst_ip="192.168.1.100",
            src_port=443,
            dst_port=12345,
            protocol="TCP",
            application_protocol="TLS"
        )
        
        # 添加各种TLS数据包类型
        analyzer._packet_analyses = [
            # TLS Handshake - 应该保留全包
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id=stream_id,
                seq_number=1000,
                payload_length=100,
                application_layer='TLS',
                is_tls_handshake=True,
                tls_content_type=22,
                tls_record_length=105
            ),
            # TLS ApplicationData - 应该掩码应用数据
            PacketAnalysis(
                packet_number=2,
                timestamp=1234567891.0,
                stream_id=stream_id,
                seq_number=1100,
                payload_length=200,
                application_layer='TLS',
                is_tls_application_data=True,
                tls_content_type=23,
                tls_record_length=205
            ),
            # TLS ChangeCipherSpec - 应该保留全包
            PacketAnalysis(
                packet_number=3,
                timestamp=1234567892.0,
                stream_id=stream_id,
                seq_number=1300,
                payload_length=50,
                application_layer='TLS',
                is_tls_change_cipher_spec=True,
                tls_content_type=20,
                tls_record_length=55
            ),
            # TLS Alert - 应该保留全包
            PacketAnalysis(
                packet_number=4,
                timestamp=1234567893.0,
                stream_id=stream_id,
                seq_number=1350,
                payload_length=30,
                application_layer='TLS',
                is_tls_alert=True,
                tls_content_type=21,
                tls_record_length=35
            ),
            # TLS Heartbeat - 应该保留全包
            PacketAnalysis(
                packet_number=5,
                timestamp=1234567894.0,
                stream_id=stream_id,
                seq_number=1380,
                payload_length=60,
                application_layer='TLS',
                is_tls_heartbeat=True,
                tls_content_type=24,
                tls_record_length=65
            )
        ]
        
        mask_table = analyzer._generate_mask_table()
        
        assert mask_table is not None
        assert mask_table.get_total_entry_count() == 5
        
        # 验证Handshake掩码规范 - KeepAll
        handshake_mask = mask_table.lookup(stream_id, 1000, 100)
        assert handshake_mask is not None
        assert isinstance(handshake_mask, KeepAll)
        
        # 验证ApplicationData掩码规范 - MaskAfter(5)
        app_data_mask = mask_table.lookup(stream_id, 1100, 200)
        assert app_data_mask is not None
        assert isinstance(app_data_mask, MaskAfter)
        assert app_data_mask.keep_bytes == 5
        
        # 验证ChangeCipherSpec掩码规范 - KeepAll
        change_cipher_mask = mask_table.lookup(stream_id, 1300, 50)
        assert change_cipher_mask is not None
        assert isinstance(change_cipher_mask, KeepAll)
        
        # 验证Alert掩码规范 - KeepAll
        alert_mask = mask_table.lookup(stream_id, 1350, 30)
        assert alert_mask is not None
        assert isinstance(alert_mask, KeepAll)
        
        # 验证Heartbeat掩码规范 - KeepAll
        heartbeat_mask = mask_table.lookup(stream_id, 1380, 60)
        assert heartbeat_mask is not None
        assert isinstance(heartbeat_mask, KeepAll)
    
    def test_generate_mask_table_generic(self):
        """测试通用协议掩码表生成"""
        analyzer = PySharkAnalyzer()
        
        # 添加流信息（无应用层协议）
        stream_id = "TCP_192.168.1.1:8080_192.168.1.100:12345"
        analyzer._streams[stream_id] = StreamInfo(
            stream_id=stream_id,
            src_ip="192.168.1.1",
            dst_ip="192.168.1.100",
            src_port=8080,
            dst_port=12345,
            protocol="TCP",
            application_protocol=None
        )
        
        # 添加数据包分析结果
        analyzer._packet_analyses = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id=stream_id,
                seq_number=1000,
                payload_length=100
            )
        ]
        
        mask_table = analyzer._generate_mask_table()
        
        assert mask_table is not None
        assert mask_table.get_total_entry_count() == 1
        
        # 验证通用掩码（应该保留全部）
        mask_spec = mask_table.lookup(stream_id, 1000, 100)
        assert mask_spec is not None
        assert isinstance(mask_spec, KeepAll)
    
    def test_generate_statistics(self):
        """测试统计信息生成"""
        analyzer = PySharkAnalyzer()
        
        # 添加流信息
        stream_id = "TCP_192.168.1.1:80_192.168.1.100:12345"
        analyzer._streams[stream_id] = StreamInfo(
            stream_id=stream_id,
            src_ip="192.168.1.1",
            dst_ip="192.168.1.100",
            src_port=80,
            dst_port=12345,
            protocol="TCP",
            application_protocol="HTTP",
            packet_count=2,
            total_bytes=300,
            first_seen=1234567890.0,
            last_seen=1234567891.0
        )
        
        # 添加数据包分析结果
        analyzer._packet_analyses = [
            PacketAnalysis(1, 1234567890.0, stream_id, application_layer='HTTP'),
            PacketAnalysis(2, 1234567891.0, stream_id, application_layer='HTTP')
        ]
        
        stats = analyzer._generate_statistics()
        
        assert stats['total_packets'] == 2
        assert stats['total_streams'] == 1
        assert 'TCP' in stats['protocol_distribution']
        assert stats['protocol_distribution']['TCP'] == 2
        assert 'HTTP' in stats['application_distribution']
        assert stats['application_distribution']['HTTP'] == 2
        assert stream_id in stats['stream_details']
        assert stats['stream_details'][stream_id]['packet_count'] == 2
        assert stats['stream_details'][stream_id]['total_bytes'] == 300
        assert stats['stream_details'][stream_id]['application_protocol'] == 'HTTP'
        assert stats['stream_details'][stream_id]['duration'] == 1.0
    
    def test_get_estimated_duration(self, stage_context):
        """测试处理时间估算"""
        analyzer = PySharkAnalyzer()
        
        duration = analyzer.get_estimated_duration(stage_context)
        
        # 基于文件大小的估算
        assert duration >= 2.0  # 最小2秒
    
    def test_get_estimated_duration_no_file(self, temp_dir):
        """测试无文件时的处理时间估算"""
        context = StageContext(
            input_file=temp_dir / "input.pcap",
            output_file=temp_dir / "output.pcap",
            work_dir=temp_dir / "work"
        )
        context.tshark_output = None
        
        analyzer = PySharkAnalyzer()
        duration = analyzer.get_estimated_duration(context)
        
        assert duration == 10.0  # 默认值
    
    def test_get_required_tools(self):
        """测试获取所需工具列表"""
        analyzer = PySharkAnalyzer()
        tools = analyzer.get_required_tools()
        
        assert tools == ['pyshark']
    
    @patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark')
    def test_check_tool_availability_available(self, mock_pyshark):
        """测试工具可用性检查（可用）"""
        analyzer = PySharkAnalyzer()
        availability = analyzer.check_tool_availability()
        
        assert availability == {'pyshark': True}
    
    def test_check_tool_availability_unavailable(self):
        """测试工具可用性检查（不可用）"""
        with patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark', None):
            analyzer = PySharkAnalyzer()
            availability = analyzer.check_tool_availability()
            
            assert availability == {'pyshark': False}
    
    def test_get_description(self):
        """测试获取描述信息"""
        analyzer = PySharkAnalyzer()
        description = analyzer.get_description()
        
        assert "PyShark" in description
        assert "协议" in description
        assert "HTTP" in description
        assert "TLS" in description
    
    def test_cleanup_memory(self):
        """测试内存清理"""
        analyzer = PySharkAnalyzer()
        
        # 添加一些数据
        analyzer._packet_analyses = [
            PacketAnalysis(1, 1234567890.0, "test_stream"),
            PacketAnalysis(2, 1234567891.0, "test_stream")
        ]
        
        analyzer._cleanup_memory()
        
        assert len(analyzer._packet_analyses) == 0
    
    @patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark')
    def test_execute_success(self, mock_pyshark, stage_context):
        """测试成功执行分析"""
        # Mock PyShark
        mock_packets = [
            MockPacket(1, 1234567890.0, has_tcp=True, has_http=True),
            MockPacket(2, 1234567891.0, has_tcp=True)
        ]
        mock_cap = MockFileCapture(mock_packets)
        mock_pyshark.FileCapture.return_value = mock_cap
        
        analyzer = PySharkAnalyzer()
        analyzer._is_initialized = True
        
        result = analyzer.execute(stage_context)
        
        assert result.success is True
        assert "PyShark分析完成" in result.data
        assert stage_context.mask_table is not None
        assert stage_context.pyshark_results is not None
        assert 'streams' in stage_context.pyshark_results
        assert 'packet_analyses' in stage_context.pyshark_results
        assert 'statistics' in stage_context.pyshark_results
    
    def test_execute_validation_failure(self, stage_context):
        """测试输入验证失败"""
        stage_context.tshark_output = None
        
        analyzer = PySharkAnalyzer()
        analyzer._is_initialized = True
        
        result = analyzer.execute(stage_context)
        
        assert result.success is False
        assert "PyShark分析失败" in result.error
    
    @patch('src.pktmask.core.trim.stages.pyshark_analyzer.pyshark')
    def test_execute_analysis_failure(self, mock_pyshark, stage_context):
        """测试分析过程失败"""
        mock_pyshark.FileCapture.side_effect = Exception("Analysis error")
        
        analyzer = PySharkAnalyzer()
        analyzer._is_initialized = True
        
        result = analyzer.execute(stage_context)
        
        assert result.success is False
        assert "PyShark分析失败" in result.error


class TestPySharkAnalyzerIntegration:
    """PyShark分析器集成测试"""
    
    @pytest.mark.slow
    @pytest.mark.skipif(not shutil.which('tshark'), reason="TShark not available")
    def test_real_pcap_analysis(self, tmp_path):
        """测试真实PCAP文件分析"""
        # 这个测试需要真实的PyShark和有效的PCAP文件
        # 在实际环境中运行时才会执行
        pass
    
    def test_large_pcap_handling(self):
        """测试大型PCAP文件处理"""
        analyzer = PySharkAnalyzer({
            'max_packets_per_batch': 100,
            'memory_cleanup_interval': 500
        })
        
        assert analyzer._max_packets_per_batch == 100
        assert analyzer._memory_cleanup_interval == 500
    
    def test_memory_optimization_settings(self):
        """测试内存优化设置"""
        config = {
            'max_packets_per_batch': 500,
            'memory_cleanup_interval': 1000,
            'analysis_timeout_seconds': 300
        }
        
        analyzer = PySharkAnalyzer(config)
        
        assert analyzer._max_packets_per_batch == 500
        assert analyzer._memory_cleanup_interval == 1000
        assert analyzer._timeout_seconds == 300
    
    def test_protocol_configuration_combinations(self):
        """测试协议配置组合"""
        # 只分析HTTP
        config_http_only = {
            'analyze_http': True,
            'analyze_tls': False,
            'analyze_tcp': True,
            'analyze_udp': False
        }
        
        analyzer = PySharkAnalyzer(config_http_only)
        assert analyzer._analyze_http is True
        assert analyzer._analyze_tls is False
        assert analyzer._analyze_tcp is True
        assert analyzer._analyze_udp is False
        
        # 只分析TLS
        config_tls_only = {
            'analyze_http': False,
            'analyze_tls': True,
            'analyze_tcp': True,
            'analyze_udp': False
        }
        
        analyzer2 = PySharkAnalyzer(config_tls_only)
        assert analyzer2._analyze_http is False
        assert analyzer2._analyze_tls is True 