"""
HTTP策略单元测试

测试HTTP协议特定裁切策略的各项功能，包括头部解析、请求/响应识别、
掩码生成等核心功能。

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

import pytest
from unittest.mock import patch, MagicMock

from src.pktmask.core.trim.strategies.http_strategy import HTTPTrimStrategy
from src.pktmask.core.trim.strategies.base_strategy import ProtocolInfo, TrimContext, TrimResult
from src.pktmask.core.trim.models.mask_spec import MaskAfter, KeepAll


class TestHTTPTrimStrategy:
    """HTTP策略测试类"""
    
    def setup_method(self):
        """设置测试环境"""
        self.config = {
            'preserve_headers': True,
            'header_only_mode': False,
            'body_preserve_bytes': 64,
            'confidence_threshold': 0.8
        }
        self.strategy = HTTPTrimStrategy(self.config)
        
    def test_strategy_properties(self):
        """测试策略基本属性"""
        assert self.strategy.strategy_name == 'http'
        assert self.strategy.priority == 80
        assert 'HTTP' in self.strategy.supported_protocols
        assert 'HTTPS' in self.strategy.supported_protocols
        
    def test_can_handle_http_protocol(self):
        """测试HTTP协议处理能力"""
        # HTTP协议
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
            payload_size=1024,
            timestamp=1234567890.0,
            metadata={}
        )
        
        assert self.strategy.can_handle(protocol_info, context) is True
        
    def test_can_handle_https_protocol(self):
        """测试HTTPS协议处理能力"""
        protocol_info = ProtocolInfo(
            name='HTTPS',
            version='1.1', 
            layer=7,
            port=443,
            characteristics={}
        )
        context = TrimContext(
            packet_index=0,
            stream_id='test_stream',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTPS'],
            payload_size=1024,
            timestamp=1234567890.0,
            metadata={}
        )
        
        assert self.strategy.can_handle(protocol_info, context) is True
        
    def test_cannot_handle_non_http_protocol(self):
        """测试非HTTP协议拒绝处理"""
        protocol_info = ProtocolInfo(
            name='FTP',
            version='1.0',
            layer=7,
            port=21,
            characteristics={}
        )
        context = TrimContext(
            packet_index=0,
            stream_id='test_stream',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'FTP'],
            payload_size=1024,
            timestamp=1234567890.0,
            metadata={}
        )
        
        assert self.strategy.can_handle(protocol_info, context) is False
        
    def test_analyze_http_get_request(self):
        """测试HTTP GET请求分析"""
        # 构造HTTP GET请求载荷
        payload = (
            b'GET /index.html HTTP/1.1\r\n'
            b'Host: www.example.com\r\n'
            b'User-Agent: Mozilla/5.0\r\n'
            b'Accept: text/html\r\n'
            b'\r\n'
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
        assert analysis['is_response'] is False
        assert analysis['method'] == 'GET'
        assert analysis['uri'] == '/index.html'
        assert analysis['http_version'] == '1.1'
        assert analysis['header_size'] > 0
        assert analysis['body_size'] == 0
        assert 'host' in analysis['headers']
        assert analysis['headers']['host'] == 'www.example.com'
        assert analysis['confidence'] > 0.8
        
    def test_analyze_http_post_request(self):
        """测试HTTP POST请求分析"""
        # 构造HTTP POST请求载荷
        payload = (
            b'POST /api/data HTTP/1.1\r\n'
            b'Host: api.example.com\r\n'
            b'Content-Type: application/json\r\n'
            b'Content-Length: 25\r\n'
            b'\r\n'
            b'{"name": "test", "id": 1}'
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
        assert analysis['method'] == 'POST'
        assert analysis['uri'] == '/api/data'
        assert analysis['content_type'] == 'application/json'
        assert analysis['content_length'] == 25
        assert analysis['body_size'] == 25
        
    def test_analyze_http_response(self):
        """测试HTTP响应分析"""
        # 构造HTTP响应载荷
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html\r\n'
            b'Content-Length: 13\r\n'
            b'Server: nginx/1.18\r\n'
            b'\r\n'
            b'Hello, World!'
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
            flow_direction='server_to_client',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=len(payload),
            timestamp=1234567890.0,
            metadata={}
        )
        
        analysis = self.strategy.analyze_payload(payload, protocol_info, context)
        
        # 验证分析结果
        assert analysis['is_http'] is True
        assert analysis['is_response'] is True
        assert analysis['is_request'] is False
        assert analysis['status_code'] == 200
        assert analysis['reason_phrase'] == 'OK'
        assert analysis['http_version'] == '1.1'
        assert analysis['content_type'] == 'text/html'
        assert analysis['content_length'] == 13
        assert analysis['body_size'] == 13
        
    def test_analyze_invalid_http(self):
        """测试无效HTTP载荷分析"""
        # 非HTTP载荷
        payload = b'This is not HTTP content at all'
        
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
        assert analysis['is_http'] is False
        assert analysis['confidence'] < 0.5
        assert len(analysis['warnings']) > 0
        
    def test_generate_mask_spec_for_request(self):
        """测试为HTTP请求生成掩码规范"""
        # HTTP GET请求载荷
        payload = (
            b'GET /index.html HTTP/1.1\r\n'
            b'Host: www.example.com\r\n'
            b'User-Agent: Mozilla/5.0\r\n'
            b'\r\n'
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
        
        # 先分析载荷
        analysis = self.strategy.analyze_payload(payload, protocol_info, context)
        
        # 生成掩码规范
        result = self.strategy.generate_mask_spec(payload, protocol_info, context, analysis)
        
        # 验证结果
        assert result.success is True
        assert isinstance(result.mask_spec, MaskAfter)
        assert result.preserved_bytes == len(payload)  # 只有头部，全部保留
        assert result.trimmed_bytes == 0
        assert result.confidence > 0.8
        assert 'HTTP GET 请求' in result.reason
        
    def test_generate_mask_spec_for_post_request(self):
        """测试为HTTP POST请求生成掩码规范"""
        # HTTP POST请求载荷
        payload = (
            b'POST /api/data HTTP/1.1\r\n'
            b'Host: api.example.com\r\n'
            b'Content-Type: application/json\r\n'
            b'Content-Length: 100\r\n'
            b'\r\n'
            + b'A' * 100  # 100字节的消息体
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
        
        # 先分析载荷
        analysis = self.strategy.analyze_payload(payload, protocol_info, context)
        
        # 生成掩码规范
        result = self.strategy.generate_mask_spec(payload, protocol_info, context, analysis)
        
        # 验证结果
        assert result.success is True
        assert isinstance(result.mask_spec, MaskAfter)
        # 应该保留头部 + 部分消息体
        assert result.preserved_bytes < len(payload)
        assert result.trimmed_bytes > 0
        assert result.confidence > 0.8
        
    def test_generate_mask_spec_for_response(self):
        """测试为HTTP响应生成掩码规范"""
        # HTTP响应载荷
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html\r\n'
            b'Content-Length: 200\r\n'
            b'\r\n'
            + b'<html><body>Hello World</body></html>' + b'X' * 162  # 200字节的响应体
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
            flow_direction='server_to_client',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=len(payload),
            timestamp=1234567890.0,
            metadata={}
        )
        
        # 先分析载荷
        analysis = self.strategy.analyze_payload(payload, protocol_info, context)
        
        # 生成掩码规范
        result = self.strategy.generate_mask_spec(payload, protocol_info, context, analysis)
        
        # 验证结果
        assert result.success is True
        assert isinstance(result.mask_spec, MaskAfter)
        assert result.preserved_bytes < len(payload)
        assert result.trimmed_bytes > 0
        assert 'HTTP 200 响应' in result.reason
        
    def test_header_only_mode(self):
        """测试仅保留头部模式"""
        # 启用仅头部模式
        config = self.config.copy()
        config['header_only_mode'] = True
        strategy = HTTPTrimStrategy(config)
        
        # HTTP POST请求载荷
        payload = (
            b'POST /api/data HTTP/1.1\r\n'
            b'Host: api.example.com\r\n'
            b'Content-Length: 50\r\n'
            b'\r\n'
            + b'A' * 50  # 50字节的消息体
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
        
        # 分析并生成掩码
        analysis = strategy.analyze_payload(payload, protocol_info, context)
        result = strategy.generate_mask_spec(payload, protocol_info, context, analysis)
        
        # 验证只保留头部
        header_size = analysis['header_size']
        assert result.preserved_bytes == header_size
        assert result.trimmed_bytes == 50  # 消息体被完全裁切
        
    def test_low_confidence_rejection(self):
        """测试低置信度载荷拒绝处理"""
        # 配置高置信度阈值
        config = self.config.copy()
        config['confidence_threshold'] = 0.9
        strategy = HTTPTrimStrategy(config)
        
        # 模糊的HTTP载荷
        payload = b'GET HTTP\r\n\r\n'  # 不完整的HTTP请求
        
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
        
        # 分析并生成掩码
        analysis = strategy.analyze_payload(payload, protocol_info, context)
        result = strategy.generate_mask_spec(payload, protocol_info, context, analysis)
        
        # 验证拒绝处理
        assert result.success is False
        assert result.mask_spec is None
        assert '不是有效的HTTP载荷' in result.reason
        
    def test_parse_request_line_variations(self):
        """测试各种HTTP请求行格式"""
        test_cases = [
            ('GET / HTTP/1.1', True, 'GET', '/', '1.1'),
            ('POST /api/users HTTP/1.0', True, 'POST', '/api/users', '1.0'),
            ('PUT /data.json HTTP/2.0', True, 'PUT', '/data.json', '2.0'),
            ('INVALID_REQUEST', False, None, None, None),
            ('GET /path', False, None, None, None),  # 缺少HTTP版本
            ('GET /path HTTP/invalid', False, None, None, None)  # 无效版本
        ]
        
        for line, expected_success, expected_method, expected_uri, expected_version in test_cases:
            analysis = {}
            result = self.strategy._parse_request_line(line, analysis)
            
            assert result == expected_success
            if expected_success:
                assert analysis['method'] == expected_method
                assert analysis['uri'] == expected_uri
                assert analysis['http_version'] == expected_version
                
    def test_parse_status_line_variations(self):
        """测试各种HTTP状态行格式"""
        test_cases = [
            ('HTTP/1.1 200 OK', True, 200, 'OK', '1.1'),
            ('HTTP/1.0 404 Not Found', True, 404, 'Not Found', '1.0'),
            ('HTTP/2.0 500 Internal Server Error', True, 500, 'Internal Server Error', '2.0'),
            ('HTTP/1.1 201', True, 201, '', '1.1'),  # 没有reason phrase
            ('INVALID_STATUS', False, None, None, None),
            ('HTTP/1.1', False, None, None, None),  # 缺少状态码
            ('HTTP/1.1 abc', False, None, None, None)  # 无效状态码
        ]
        
        for line, expected_success, expected_code, expected_phrase, expected_version in test_cases:
            analysis = {}
            result = self.strategy._parse_status_line(line, analysis)
            
            assert result == expected_success
            if expected_success:
                assert analysis['status_code'] == expected_code
                assert analysis['reason_phrase'] == expected_phrase
                assert analysis['http_version'] == expected_version
                
    def test_body_preserve_bytes_calculation(self):
        """测试消息体保留字节数计算"""
        test_cases = [
            (0, 0),      # 空消息体
            (10, 20),    # 小于最小保留值，使用最小值
            (100, 64),   # 使用配置的默认值
            (2000, 200), # 使用比例限制 (10%)
            (20000, 1024) # 使用最大限制
        ]
        
        for body_size, expected in test_cases:
            result = self.strategy._calculate_body_preserve_bytes(body_size)
            assert result == expected
            
    def test_header_fields_parsing(self):
        """测试HTTP头部字段解析"""
        lines = [
            'Content-Type: text/html',
            'Content-Length: 1234',
            'Host: www.example.com',
            'User-Agent: Mozilla/5.0 (Test)',
            'Accept: text/html, application/json',
            'Invalid-Header-Without-Colon',  # 无效头部
            'Multi-Value: value1',
            'Multi-Value: value2',  # 多值头部
            ''  # 空行
        ]
        
        analysis = {'warnings': []}
        self.strategy._parse_header_fields(lines, analysis)
        
        headers = analysis['headers']
        
        # 验证正确解析的头部
        assert headers['content-type'] == 'text/html'
        assert headers['content-length'] == '1234'
        assert headers['host'] == 'www.example.com'
        assert headers['accept'] == 'text/html, application/json'
        
        # 验证多值头部合并
        assert headers['multi-value'] == 'value1, value2'
        
        # 验证无效头部产生警告
        assert len(analysis['warnings']) > 0
        
        # 验证提取的关键信息
        assert analysis['content_type'] == 'text/html'
        assert analysis['content_length'] == 1234
        
    def test_chunked_encoding_detection(self):
        """测试分块编码检测"""
        lines = [
            'Transfer-Encoding: chunked',
            'Content-Type: text/html'
        ]
        
        analysis = {'warnings': []}
        self.strategy._parse_header_fields(lines, analysis)
        
        assert analysis['is_chunked'] is True
        
    def test_confidence_calculation(self):
        """测试置信度计算"""
        # 高置信度场景
        high_confidence_analysis = {
            'is_request': True,
            'http_version': '1.1',
            'method': 'GET',
            'uri': '/index.html',
            'headers': {
                'host': 'www.example.com',
                'user-agent': 'Mozilla/5.0',
                'accept': 'text/html',
                'content-type': 'text/html'
            },
            'header_end_offset': 100,
            'warnings': []
        }
        
        confidence = self.strategy._calculate_http_confidence(high_confidence_analysis)
        assert confidence > 0.9
        
        # 低置信度场景
        low_confidence_analysis = {
            'is_request': False,
            'is_response': False,
            'http_version': None,
            'headers': {},
            'header_end_offset': -1,
            'warnings': ['错误1', '错误2', '错误3']
        }
        
        confidence = self.strategy._calculate_http_confidence(low_confidence_analysis)
        assert confidence < 0.3
        
    def test_config_validation(self):
        """测试配置验证"""
        # 有效配置
        valid_config = {
            'max_header_size': 4096,
            'body_preserve_bytes': 128,
            'confidence_threshold': 0.7
        }
        
        strategy = HTTPTrimStrategy(valid_config)
        # 不应该抛出异常
        
        # 无效配置
        invalid_configs = [
            {'max_header_size': 100},  # 太小
            {'body_preserve_bytes': -10},  # 负值
            {'confidence_threshold': 1.5}  # 超出范围
        ]
        
        for invalid_config in invalid_configs:
            with pytest.raises(ValueError):
                HTTPTrimStrategy(invalid_config)


class TestHTTPStrategyIntegration:
    """HTTP策略集成测试"""
    
    def test_full_workflow_get_request(self):
        """测试完整的GET请求处理流程"""
        config = {
            'preserve_headers': True,
            'header_only_mode': False,
            'confidence_threshold': 0.8
        }
        strategy = HTTPTrimStrategy(config)
        
        # 构造完整的HTTP GET请求
        payload = (
            b'GET /api/users?page=1&limit=10 HTTP/1.1\r\n'
            b'Host: api.example.com\r\n'
            b'User-Agent: curl/7.68.0\r\n'
            b'Accept: application/json\r\n'
            b'Authorization: Bearer token123\r\n'
            b'\r\n'
        )
        
        protocol_info = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=80,
            characteristics={}
        )
        context = TrimContext(
            packet_index=1,
            stream_id='stream_001',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=len(payload),
            timestamp=1640995200.0,
            metadata={'session_id': 'sess_123'}
        )
        
        # 执行完整的裁切流程
        result = strategy.trim_payload(payload, protocol_info, context)
        
        # 验证结果
        assert result.success is True
        assert result.confidence > 0.8
        assert isinstance(result.mask_spec, MaskAfter)
        assert result.preserved_bytes == len(payload)  # GET请求无消息体，全部保留
        assert result.trimmed_bytes == 0
        assert 'HTTP GET 请求' in result.reason
        assert result.metadata['strategy'] == 'http'
        assert result.metadata['message_type'] == 'request'
        assert result.metadata['http_version'] == '1.1'
        
    def test_full_workflow_post_request_with_body(self):
        """测试带消息体的POST请求完整处理流程"""
        config = {
            'preserve_headers': True,
            'body_preserve_bytes': 32,
            'confidence_threshold': 0.8
        }
        strategy = HTTPTrimStrategy(config)
        
        # 构造带消息体的HTTP POST请求
        json_body = b'{"username": "testuser", "password": "secret123", "email": "test@example.com"}'
        content_length_value = len(json_body)
        payload = (
            b'POST /api/login HTTP/1.1\r\n'
            b'Host: api.example.com\r\n'
            b'Content-Type: application/json\r\n'
            b'Content-Length: ' + str(content_length_value).encode() + b'\r\n'
            b'Authorization: Bearer token456\r\n'
            b'\r\n'
        ) + json_body
        
        protocol_info = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=443,
            characteristics={'encrypted': True}
        )
        context = TrimContext(
            packet_index=2,
            stream_id='stream_002',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'TLS', 'HTTP'],
            payload_size=len(payload),
            timestamp=1640995260.0,
            metadata={'tls_version': '1.3'}
        )
        
        # 执行完整的裁切流程
        result = strategy.trim_payload(payload, protocol_info, context)
        
        # 验证结果
        assert result.success is True
        assert result.confidence > 0.8
        assert isinstance(result.mask_spec, MaskAfter)
        assert result.preserved_bytes < len(payload)  # 消息体被部分裁切
        assert result.trimmed_bytes > 0
        assert 'HTTP POST 请求' in result.reason
        
        # 验证保留的字节数合理（头部 + 部分消息体）
        header_boundary = payload.find(b'\r\n\r\n')
        header_size = header_boundary + 4
        expected_preserve = header_size + 32  # 头部 + 32字节消息体
        assert result.preserved_bytes == expected_preserve
        
    def test_error_handling_malformed_http(self):
        """测试错误格式HTTP的处理"""
        config = {
            'confidence_threshold': 0.5  # 降低阈值以观察错误处理
        }
        strategy = HTTPTrimStrategy(config)
        
        # 格式错误的HTTP载荷
        payload = b'MALFORMED HTTP REQUEST WITHOUT PROPER FORMATTING'
        
        protocol_info = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=80,
            characteristics={}
        )
        context = TrimContext(
            packet_index=3,
            stream_id='stream_003',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=len(payload),
            timestamp=1640995320.0,
            metadata={}
        )
        
        # 执行裁切流程
        result = strategy.trim_payload(payload, protocol_info, context)
        
        # 验证错误处理
        assert result.success is False
        assert result.mask_spec is None
        assert result.preserved_bytes == len(payload)  # 保持原样
        assert result.trimmed_bytes == 0
        assert result.confidence < 0.5
        assert '不是有效的HTTP载荷' in result.reason
        assert len(result.warnings) > 0