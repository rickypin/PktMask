"""
HTTPScanningStrategy单元测试

测试HTTP扫描式策略的核心功能，包括：
- 基础协议检测
- 消息边界识别
- 掩码生成
- 错误处理
- 数据结构完整性

作者: PktMask Team  
创建时间: 2025-01-16
版本: 1.0.0
"""

import pytest
import unittest
from typing import Dict, Any
from unittest.mock import Mock, patch

from src.pktmask.core.trim.strategies.http_scanning_strategy import HTTPScanningStrategy
from src.pktmask.core.trim.strategies.base_strategy import ProtocolInfo, TrimContext, TrimResult
from src.pktmask.core.trim.models.scan_result import ScanResult, HttpPatterns, ScanConstants
from src.pktmask.core.trim.models.mask_spec import MaskAfter, KeepAll


class TestHTTPScanningStrategy(unittest.TestCase):
    """HTTPScanningStrategy基础测试类"""
    
    def setUp(self):
        """测试初始化"""
        self.config = {
            'max_scan_window': 8192,
            'confidence_threshold': 0.7,
            'enable_scan_logging': False,
            'chunked_sample_size': 1024,
            'fallback_on_error': True
        }
        self.strategy = HTTPScanningStrategy(self.config)
        
        # 测试用协议信息
        self.http_protocol = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=80,
            characteristics={}
        )
        
        # 测试用上下文
        self.context = TrimContext(
            packet_index=1,
            stream_id='test_stream',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=1024,
            timestamp=1234567890.0,
            metadata={}
        )
    
    def test_strategy_initialization(self):
        """测试策略初始化"""
        # 基础属性检查
        self.assertEqual(self.strategy.strategy_name, 'http_scanning')
        self.assertEqual(self.strategy.priority, 75)
        self.assertEqual(self.strategy.supported_protocols, ['HTTP'])
        
        # 配置检查
        self.assertEqual(self.strategy.config['max_scan_window'], 8192)
        self.assertEqual(self.strategy.config['confidence_threshold'], 0.7)
        
    def test_can_handle_valid_protocols(self):
        """测试协议处理能力判断 - 有效协议"""
        # HTTP协议
        self.assertTrue(self.strategy.can_handle(self.http_protocol, self.context))
        
        # 不同端口的HTTP
        http_8080 = ProtocolInfo('HTTP', '1.1', 7, 8080, {})
        self.assertTrue(self.strategy.can_handle(http_8080, self.context))
        
    def test_can_handle_invalid_protocols(self):
        """测试协议处理能力判断 - 无效协议"""
        # HTTPS协议（应该由TLS策略处理）
        https_protocol = ProtocolInfo('HTTPS', '1.1', 7, 443, {})
        self.assertFalse(self.strategy.can_handle(https_protocol, self.context))
        
        # 非应用层协议
        tcp_protocol = ProtocolInfo('HTTP', '1.1', 4, 80, {})
        self.assertFalse(self.strategy.can_handle(tcp_protocol, self.context))
        
        # 其他协议
        ftp_protocol = ProtocolInfo('FTP', '1.0', 7, 21, {})
        self.assertFalse(self.strategy.can_handle(ftp_protocol, self.context))
    
    def test_analyze_http_get_request(self):
        """测试HTTP GET请求分析"""
        payload = (
            b'GET /index.html HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'User-Agent: TestAgent/1.0\r\n'
            b'\r\n'
        )
        
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 检查分析结果
        self.assertTrue(analysis['is_http'])
        self.assertGreater(analysis['confidence'], 0.8)
        self.assertGreater(analysis['header_boundary'], 0)
        self.assertEqual(analysis['scan_method'], 'request_pattern_match_single_message')
        
        # 检查ScanResult
        scan_result = analysis['scan_result']
        self.assertTrue(scan_result.is_http)
        self.assertEqual(scan_result.message_type, 'request')
        self.assertEqual(scan_result.method, 'GET')
    
    def test_analyze_http_response(self):
        """测试HTTP响应分析"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html\r\n'
            b'Content-Length: 27\r\n'
            b'\r\n'
            b'<html><body>Hello</body></html>'
        )
        
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 检查分析结果
        self.assertTrue(analysis['is_http'])
        self.assertGreater(analysis['confidence'], 0.8)
        self.assertGreater(analysis['header_boundary'], 0)
        
        # 检查ScanResult
        scan_result = analysis['scan_result']
        self.assertTrue(scan_result.is_http)
        self.assertEqual(scan_result.message_type, 'response')
        self.assertEqual(scan_result.http_version, 'HTTP/1.1')
        self.assertEqual(scan_result.content_length, 27)
    
    def test_analyze_chunked_response(self):
        """测试Chunked编码响应分析"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'\r\n'
            b'1a\r\n'
            b'abcdefghijklmnopqrstuvwxyz\r\n'
            b'10\r\n'
            b'1234567890abcdef\r\n'
            b'0\r\n'
            b'\r\n'
        )
        
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 检查分析结果
        self.assertTrue(analysis['is_http'])
        self.assertGreater(analysis['confidence'], 0.7)
        
        # 检查ScanResult
        scan_result = analysis['scan_result']
        self.assertTrue(scan_result.is_chunked)
        self.assertIn('chunked', scan_result.scan_method)
    
    def test_analyze_non_http_payload(self):
        """测试非HTTP载荷分析"""
        payload = b'\x16\x03\x01\x00\x01\x01\x00\x00\xfd\x03\x03'  # TLS握手
        
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 应该识别为非HTTP
        self.assertFalse(analysis['is_http'])
        self.assertEqual(analysis['scan_result'].confidence, 0.0)
    
    def test_generate_mask_spec_successful_scan(self):
        """测试成功扫描后的掩码生成"""
        # 创建一个足够大的载荷来触发MaskAfter掩码
        large_body = "A" * 200  # 200字节的消息体，大于64字节样本大小
        payload = (
            b'GET /test HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'Content-Length: 200\r\n'
            b'\r\n'
        ) + large_body.encode()
        
        # 先分析载荷
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 生成掩码
        result = self.strategy.generate_mask_spec(
            payload, self.http_protocol, self.context, analysis
        )
        
        # 检查结果
        self.assertTrue(result.success)
        self.assertIsInstance(result.mask_spec, MaskAfter)
        self.assertGreater(result.preserved_bytes, 0)
        self.assertLess(result.preserved_bytes, len(payload))
        self.assertEqual(result.preserved_bytes + result.trimmed_bytes, len(payload))
        self.assertGreater(result.confidence, 0.8)
    
    def test_generate_mask_spec_failed_scan(self):
        """测试扫描失败后的掩码生成"""
        payload = b'Not HTTP content at all'
        
        # 先分析载荷
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 生成掩码
        result = self.strategy.generate_mask_spec(
            payload, self.http_protocol, self.context, analysis
        )
        
        # 扫描失败时应该返回success=False，但仍然提供保守的掩码
        self.assertFalse(result.success)  # 修正：扫描失败时success应该为False
        self.assertIsInstance(result.mask_spec, KeepAll)
        self.assertEqual(result.preserved_bytes, len(payload))
        self.assertEqual(result.trimmed_bytes, 0)
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("未识别为HTTP协议", result.reason)  # 修正：更新期望的错误信息
    
    def test_error_handling_in_analysis(self):
        """测试分析过程中的错误处理"""
        # 空载荷
        empty_payload = b''
        analysis = self.strategy.analyze_payload(empty_payload, self.http_protocol, self.context)
        self.assertFalse(analysis['is_http'])
        
        # 极小载荷
        tiny_payload = b'GET'
        analysis = self.strategy.analyze_payload(tiny_payload, self.http_protocol, self.context)
        self.assertFalse(analysis['is_http'])
    
    def test_error_handling_in_mask_generation(self):
        """测试掩码生成过程中的错误处理"""
        # 无效分析结果
        invalid_analysis = {'scan_result': None, 'is_http': False}
        
        result = self.strategy.generate_mask_spec(
            b'test', self.http_protocol, self.context, invalid_analysis
        )
        
        # 应该保守回退
        self.assertTrue(result.success)
        self.assertIsInstance(result.mask_spec, KeepAll)
    
    def test_performance_requirements(self):
        """测试性能要求"""
        large_payload = b'GET / HTTP/1.1\r\nHost: example.com\r\n\r\n' + b'x' * 10000
        
        import time
        start_time = time.perf_counter()
        
        analysis = self.strategy.analyze_payload(large_payload, self.http_protocol, self.context)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # 扫描应该在合理时间内完成（<100ms）
        self.assertLess(duration_ms, 100)
        self.assertIn('analysis_duration_ms', analysis)
        self.assertIsInstance(analysis['analysis_duration_ms'], float)


class TestScanResultDataStructure(unittest.TestCase):
    """ScanResult数据结构测试"""
    
    def test_scan_result_creation(self):
        """测试ScanResult创建"""
        # 成功结果
        success_result = ScanResult.create_success(
            header_boundary=50,
            confidence=0.9,
            scan_method='test_method',
            message_type='request'
        )
        
        self.assertTrue(success_result.is_http)
        self.assertTrue(success_result.is_successful)
        self.assertEqual(success_result.header_boundary, 50)
        self.assertEqual(success_result.confidence, 0.9)
        
        # 失败结果
        failure_result = ScanResult.conservative_fallback("test reason")
        self.assertFalse(failure_result.is_http)
        self.assertFalse(failure_result.is_successful)
        self.assertEqual(failure_result.header_boundary, -1)
    
    def test_scan_result_warnings(self):
        """测试ScanResult警告功能"""
        result = ScanResult.create_success(
            header_boundary=10,
            confidence=0.8,
            scan_method='test'
        )
        
        result.add_warning("Test warning")
        result.add_warning("Another warning")
        
        self.assertEqual(len(result.warnings), 2)
        self.assertIn("Test warning", result.warnings)
        
        # 重复警告不应该添加
        result.add_warning("Test warning")
        self.assertEqual(len(result.warnings), 2)
    
    def test_scan_result_debug_info(self):
        """测试ScanResult调试信息"""
        result = ScanResult.create_success(
            header_boundary=10,
            confidence=0.8,
            scan_method='test'
        )
        
        result.add_debug_info("key1", "value1")
        result.add_debug_info("key2", 123)
        
        self.assertEqual(result.debug_info["key1"], "value1")
        self.assertEqual(result.debug_info["key2"], 123)
    
    def test_total_preserve_bytes_calculation(self):
        """测试总保留字节数计算"""
        # 使用preserve_bytes
        result1 = ScanResult.create_success(
            header_boundary=50,
            confidence=0.9,
            scan_method='test',
            preserve_bytes=100
        )
        self.assertEqual(result1.total_preserve_bytes, 100)
        
        # 使用header_boundary + body_preserve_bytes
        result2 = ScanResult.create_success(
            header_boundary=50,
            confidence=0.9,
            scan_method='test',
            body_preserve_bytes=30
        )
        self.assertEqual(result2.total_preserve_bytes, 84)  # 50 + 4 + 30


class TestHttpPatterns(unittest.TestCase):
    """HTTP模式测试"""
    
    def test_request_patterns(self):
        """测试HTTP请求模式"""
        patterns = HttpPatterns.get_all_request_patterns()
        self.assertIn(b'GET ', patterns)
        self.assertIn(b'POST ', patterns)
        self.assertIn(b'PUT ', patterns)
        self.assertIn(b'DELETE ', patterns)
    
    def test_response_patterns(self):
        """测试HTTP响应模式"""
        patterns = HttpPatterns.get_all_response_patterns()
        self.assertIn(b'HTTP/1.0 ', patterns)
        self.assertIn(b'HTTP/1.1 ', patterns)
        # HTTP/2.0不应该在列表中
        self.assertNotIn(b'HTTP/2.0 ', patterns)
    
    def test_all_http_patterns(self):
        """测试所有HTTP模式"""
        all_patterns = HttpPatterns.get_all_http_patterns()
        self.assertGreater(len(all_patterns), 10)  # 应该有足够的模式
        
        # 检查包含请求和响应模式
        self.assertIn(b'GET ', all_patterns)
        self.assertIn(b'HTTP/1.1 ', all_patterns)


class TestScanConstants(unittest.TestCase):
    """扫描常量测试"""
    
    def test_constants_values(self):
        """测试常量值的合理性"""
        # 扫描窗口配置
        self.assertEqual(ScanConstants.MAX_SCAN_WINDOW, 8192)
        self.assertGreater(ScanConstants.MAX_HEADER_SIZE, ScanConstants.MIN_HEADER_SIZE)
        
        # 置信度阈值
        self.assertGreater(ScanConstants.HIGH_CONFIDENCE, ScanConstants.MEDIUM_CONFIDENCE)
        self.assertGreater(ScanConstants.MEDIUM_CONFIDENCE, ScanConstants.LOW_CONFIDENCE)
        
        # 保留策略配置
        self.assertGreater(ScanConstants.CHUNKED_SAMPLE_SIZE, 0)
        self.assertGreater(ScanConstants.CONSERVATIVE_PRESERVE_RATIO, 0.5)
        self.assertLess(ScanConstants.CONSERVATIVE_PRESERVE_RATIO, 1.0)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2) 