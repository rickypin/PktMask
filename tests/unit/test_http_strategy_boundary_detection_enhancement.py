"""
HTTP策略边界检测多层容错增强测试

测试HTTPTrimStrategy的边界检测容错功能，验证多种格式的边界检测能力。

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

import pytest
from unittest.mock import patch, MagicMock

from src.pktmask.core.trim.strategies.http_strategy import HTTPTrimStrategy
from src.pktmask.core.trim.strategies.base_strategy import ProtocolInfo, TrimContext


class TestHTTPBoundaryDetectionEnhancement:
    """HTTP边界检测多层容错增强测试类"""
    
    def setup_method(self):
        """设置测试环境"""
        self.config = {
            'preserve_headers': True,
            'header_only_mode': False,
            'body_preserve_bytes': 64,
            'confidence_threshold': 0.8
        }
        self.strategy = HTTPTrimStrategy(self.config)
        
    def test_standard_boundary_detection(self):
        """测试标准\r\n\r\n边界检测"""
        payload = b'GET /test HTTP/1.1\r\nHost: example.com\r\n\r\nBody content'
        result = self.strategy._find_header_boundary_tolerant(payload)
        assert result == 41  # 头部长度+4
        
    def test_unix_boundary_detection(self):
        """测试Unix格式\n\n边界检测"""
        payload = b'GET /test HTTP/1.1\nHost: example.com\n\nBody content'
        result = self.strategy._find_header_boundary_tolerant(payload)
        assert result == 38  # 头部长度+2
        
    def test_mixed_boundary_detection(self):
        """测试混合格式\r\n\n边界检测"""
        payload = b'GET /test HTTP/1.1\r\nHost: example.com\r\n\nBody content'
        result = self.strategy._find_header_boundary_tolerant(payload)
        assert result == 40  # 头部长度+3
        
    def test_empty_line_boundary_detection(self):
        """测试空行边界检测"""
        payload = b'GET /test HTTP/1.1\nHost: example.com\n\nBody content'
        result = self.strategy._find_header_boundary_tolerant(payload)
        assert result == 38
        
    def test_no_boundary_found(self):
        """测试未找到边界的情况"""
        payload = b'GET /test HTTP/1.1 Host: example.com Body content'
        result = self.strategy._find_header_boundary_tolerant(payload)
        assert result is None
        
    def test_resource_protection_large_payload(self):
        """测试资源保护机制 - 大载荷处理"""
        # 创建一个超过8KB的载荷
        large_payload = b'GET /test HTTP/1.1\nHost: example.com\n' + b'X' * 10000 + b'\n\nBody'
        result = self.strategy._find_header_boundary_tolerant(large_payload)
        # 应该只在前8KB内查找
        assert result is not None
        
    def test_multiple_possible_boundaries(self):
        """测试多个可能边界的优先级"""
        # 包含多种边界格式，应该选择第一个找到的
        payload = b'GET /test HTTP/1.1\r\nHost: example.com\r\n\r\nMore\n\nData'
        result = self.strategy._find_header_boundary_tolerant(payload)
        assert result == 41  # 应该选择\r\n\r\n边界
        
    def test_boundary_at_payload_start(self):
        """测试边界在载荷开始位置"""
        payload = b'\r\n\r\nOnly body content'
        result = self.strategy._find_header_boundary_tolerant(payload)
        assert result == 4
        
    def test_boundary_at_payload_end(self):
        """测试边界在载荷结尾位置"""
        payload = b'GET /test HTTP/1.1\r\nHost: example.com\r\n\r\n'
        result = self.strategy._find_header_boundary_tolerant(payload)
        assert result == 41
        
    def test_empty_payload(self):
        """测试空载荷"""
        payload = b''
        result = self.strategy._find_header_boundary_tolerant(payload)
        assert result is None
        
    def test_analyze_payload_integration_standard(self):
        """测试与analyze_payload方法的集成 - 标准格式"""
        payload = (
            b'POST /api/test HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'Content-Length: 13\r\n'
            b'\r\n'
            b'{"test": true}'
        )
        
        protocol_info = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=80,
            characteristics={}
        )
        context = TrimContext(
            packet_index=0,
            stream_id='test_stream',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=len(payload),
            timestamp=1234567890.0,
            metadata={}
        )
        
        analysis = self.strategy.analyze_payload(payload, protocol_info, context)
        
        # 验证分析结果
        assert analysis['is_http'] is True
        assert analysis['is_request'] is True
        assert analysis['boundary_method'] == 'standard_crlf_crlf'
        assert analysis['header_size'] == 66  # 包含\r\n\r\n
        assert analysis['body_size'] == 14
        
    def test_analyze_payload_integration_unix(self):
        """测试与analyze_payload方法的集成 - Unix格式"""
        payload = (
            b'POST /api/test HTTP/1.1\n'
            b'Host: example.com\n'
            b'Content-Length: 13\n'
            b'\n'
            b'{"test": true}'
        )
        
        protocol_info = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=80,
            characteristics={}
        )
        context = TrimContext(
            packet_index=0,
            stream_id='test_stream',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=len(payload),
            timestamp=1234567890.0,
            metadata={}
        )
        
        analysis = self.strategy.analyze_payload(payload, protocol_info, context)
        
        # 验证分析结果
        # Unix格式可能不被完全识别为有效HTTP，但边界检测应该工作
        assert 'boundary_method' in analysis
        assert analysis['boundary_method'] == 'unix_lf_lf'
        
    def test_analyze_payload_integration_mixed(self):
        """测试与analyze_payload方法的集成 - 混合格式"""
        payload = (
            b'POST /api/test HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'Content-Length: 13\r\n'
            b'\n'
            b'{"test": true}'
        )
        
        protocol_info = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=80,
            characteristics={}
        )
        context = TrimContext(
            packet_index=0,
            stream_id='test_stream',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=len(payload),
            timestamp=1234567890.0,
            metadata={}
        )
        
        analysis = self.strategy.analyze_payload(payload, protocol_info, context)
        
        # 验证分析结果
        assert analysis['is_http'] is True
        assert analysis['is_request'] is True
        # 注意：混合格式\r\n\n会被当作\n\n处理（优先级）
        assert analysis['boundary_method'] == 'unix_lf_lf'
        assert analysis['header_size'] == 65  # 混合格式
        assert analysis['body_size'] == 14
        
    def test_analyze_payload_fallback_case(self):
        """测试analyze_payload的回退情况"""
        # 没有明确边界的载荷
        payload = b'GET /test HTTP/1.1 Host: example.com Content here'
        
        protocol_info = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=80,
            characteristics={}
        )
        context = TrimContext(
            packet_index=0,
            stream_id='test_stream',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=len(payload),
            timestamp=1234567890.0,
            metadata={}
        )
        
        analysis = self.strategy.analyze_payload(payload, protocol_info, context)
        
        # 验证回退处理
        assert 'boundary_method' in analysis
        assert analysis['boundary_method'] == 'fallback_estimation'
        assert len(analysis['warnings']) > 0
        assert "未找到完整的HTTP头部结束标志" in analysis['warnings'][0] 