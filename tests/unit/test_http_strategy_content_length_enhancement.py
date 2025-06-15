"""
HTTP策略Content-Length容错增强测试

测试HTTPTrimStrategy的Content-Length解析容错功能，验证异常格式的处理能力。

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

import pytest
from unittest.mock import patch, MagicMock

from src.pktmask.core.trim.strategies.http_strategy import HTTPTrimStrategy


class TestHTTPContentLengthEnhancement:
    """HTTP Content-Length容错增强测试类"""
    
    def setup_method(self):
        """设置测试环境"""
        self.config = {
            'preserve_headers': True,
            'header_only_mode': False,
            'body_preserve_bytes': 64,
            'confidence_threshold': 0.8
        }
        self.strategy = HTTPTrimStrategy(self.config)
        
    def test_parse_content_length_standard_format(self):
        """测试标准Content-Length格式解析"""
        headers = {'content-length': '123'}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result == 123
        
    def test_parse_content_length_with_spaces(self):
        """测试带空格的Content-Length格式"""
        headers = {'content-length': '  456  '}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result == 456
        
    def test_parse_content_length_with_bytes_suffix(self):
        """测试带bytes后缀的Content-Length格式"""
        headers = {'content-length': '789 bytes'}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result == 789
        
    def test_parse_content_length_with_charset(self):
        """测试带字符集的Content-Length格式"""
        headers = {'content-length': '321; charset=utf-8'}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result == 321
        
    def test_parse_content_length_complex_format(self):
        """测试复杂格式的Content-Length"""
        headers = {'content-length': 'Content-Length: 654 bytes; encoding=gzip'}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result == 654
        
    def test_parse_content_length_empty_value(self):
        """测试空Content-Length值"""
        headers = {'content-length': ''}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result is None
        
    def test_parse_content_length_missing_header(self):
        """测试缺失Content-Length头部"""
        headers = {}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result is None
        
    def test_parse_content_length_invalid_format(self):
        """测试无效的Content-Length格式"""
        headers = {'content-length': 'invalid-length'}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result is None
        
    def test_parse_content_length_multiple_numbers(self):
        """测试包含多个数字的Content-Length（选择第一个）"""
        headers = {'content-length': '123 and 456 bytes'}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result == 123
        
    def test_parse_content_length_zero_value(self):
        """测试零值Content-Length"""
        headers = {'content-length': '0'}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result == 0
        
    def test_parse_content_length_large_value(self):
        """测试大数值Content-Length"""
        headers = {'content-length': '1048576'}
        result = self.strategy._parse_content_length_enhanced(headers)
        assert result == 1048576
        
    def test_integration_with_analyze_payload(self):
        """测试与analyze_payload方法的集成"""
        # 构造带有异常Content-Length的HTTP请求
        payload = (
            b'POST /api/upload HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'Content-Type: application/json\r\n'
            b'Content-Length: 25 bytes\r\n'
            b'\r\n'
            b'{"message": "test data"}'
        )
        
        from src.pktmask.core.trim.strategies.base_strategy import ProtocolInfo, TrimContext
        
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
        assert analysis['content_length'] == 25  # 容错解析成功
        assert analysis['method'] == 'POST'
        assert analysis['body_size'] == 24  # 实际消息体大小（JSON字符串长度）
        assert len(analysis['warnings']) == 0  # 无警告信息 